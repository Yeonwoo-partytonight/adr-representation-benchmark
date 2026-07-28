#!/usr/bin/env python3
"""prep_features.py — v3 사다리(M0~M4) + ablation 용 파생 피처 사전계산 (학습 아님).

선행 산출물(재계산 금지)만 소비해 파생 텐서를 만든다:
  data/processed/drug_target_emb.npy (1092,1024)  — affinity 가중 top-k(human, 주)
  data/processed/target_mapping/07_agg_topk.csv    — cid×uniprot top-k(rank,weight,pchembl,imputed)
  data/processed/target_mapping/06_targets_human.csv — cid×uniprot(human 전체 표적)
  data/processed/target_mapping/protbert_emb/<uni>.npy — UniProt 잔기평균 임베딩(1024)
  data/processed/target_mapping/protbert_index.csv — (uniprot, seq_len, truncated, emb_path)

산출(모두 master_X cid 정렬, N=1092):
  data/processed/drug_affinity_stats.npy (1092,2) float32 — [top-k 실측 pchembl 평균, 최대] (M3)
  data/processed/drug_affinity_present.npy (1092,) int8  — 실측 affinity 보유=1
  data/processed/drug_target_emb_mean.npy (1092,1024)    — 무가중 평균 pooling (ablation5)
  data/processed/drug_target_emb_top1.npy (1092,1024)    — top-1(최고 pchembl) (ablation5)
  data/processed/target_mapping/protbert_emb_chunk/<uni>.npy — 절단(940) 청크 mean-pool 재임베딩
  data/processed/drug_target_emb_chunk.npy (1092,1024)   — 청크 임베딩으로 동일 top-k 가중집계 (ablation4)

★ 표준화/PCA는 여기서 하지 않는다 — 그것은 train split에서만 fit해야 하므로 train_ladder.py에서 수행.
   여기서는 누수와 무관한 '원자 임베딩 집계'와 'affinity 요약 통계'만 만든다.

재현: SEED=42 고정, 캐시-우선(청크 임베딩만 최초 1회 ProtBERT 연산). 네트워크 재수집 없음.
실행: PYTORCH_ENABLE_MPS_FALLBACK=1 python v3_Multimodal/src/prep_features.py
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import csv
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PROC = os.path.join(ROOT, "data", "processed")
TMAP = os.path.join(PROC, "target_mapping")
EMBDIR = os.path.join(TMAP, "protbert_emb")
CHUNKDIR = os.path.join(TMAP, "protbert_emb_chunk")
EMB_DIM = 1024
TOPK = 5
MAX_RES = 510        # ProtBERT 잔기 상한(특수토큰 제외) — target_pipeline과 동일
SEED = 42


def log(m):
    print(m, flush=True)


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def cid_order():
    """master_X를 cid 오름차순으로 — target_pipeline STEP4와 동일 정렬(임베딩 행 정렬 기준)."""
    order = pd.read_parquet(os.path.join(PROC, "master_X.parquet")).sort_values("cid")["cid"].astype(int).tolist()
    assert len(order) == 1092, f"master_X 분자 수 {len(order)} != 1092"
    return order


def load_emb(dirpath=EMBDIR):
    """protbert_index.csv 기준 UniProt→임베딩(1024) dict."""
    emb = {}
    for r in read_csv(os.path.join(TMAP, "protbert_index.csv")):
        if r["emb_path"]:
            emb[r["uniprot"]] = np.load(os.path.join(TMAP, r["emb_path"]))
    return emb


# ---------------------------------------------------------------------------
# 1) affinity 요약 통계 (M3) — top-k 실측 pchembl 평균/최대
# ---------------------------------------------------------------------------
def build_affinity_stats():
    order = cid_order()
    idx = {c: i for i, c in enumerate(order)}
    # cid → 실측(affinity_imputed==0) pchembl 값들 (top-k rank 내)
    cid_vals = defaultdict(list)
    for r in read_csv(os.path.join(TMAP, "07_agg_topk.csv")):
        if r["affinity_imputed"] == "0" and r["pchembl_median"] not in ("", None):
            cid_vals[int(r["cid"])].append(float(r["pchembl_median"]))
    stats = np.zeros((len(order), 2), dtype="float32")
    present = np.zeros((len(order),), dtype="int8")
    for c, vals in cid_vals.items():
        if c not in idx or not vals:
            continue
        stats[idx[c], 0] = float(np.mean(vals))
        stats[idx[c], 1] = float(np.max(vals))
        present[idx[c]] = 1
    np.save(os.path.join(PROC, "drug_affinity_stats.npy"), stats)
    np.save(os.path.join(PROC, "drug_affinity_present.npy"), present)
    log(f"[affinity] present {int(present.sum())}/1092, "
        f"pchembl mean(among present) {stats[present==1,0].mean():.2f}, max {stats[present==1,1].mean():.2f}")


# ---------------------------------------------------------------------------
# 2) 집계 변형 (ablation5): 무가중 평균 / top-1
# ---------------------------------------------------------------------------
def _cid_targets_human():
    cid_t = defaultdict(list)   # cid → [uniprot] (human 전체 표적, 순서보존·중복제거)
    for r in read_csv(os.path.join(TMAP, "06_targets_human.csv")):
        u = r["uniprot"]
        if u not in cid_t[int(r["cid"])]:
            cid_t[int(r["cid"])].append(u)
    return cid_t


def build_aggregation_variants():
    order = cid_order()
    idx = {c: i for i, c in enumerate(order)}
    emb = load_emb()
    cid_t = _cid_targets_human()

    # top-1 = 07_agg_topk.csv에서 rank==1 uniprot (pchembl desc 정렬됨)
    cid_rank1 = {}
    for r in read_csv(os.path.join(TMAP, "07_agg_topk.csv")):
        if r["rank"] == "1":
            cid_rank1[int(r["cid"])] = r["uniprot"]

    mean_emb = np.zeros((len(order), EMB_DIM), dtype="float32")
    top1_emb = np.zeros((len(order), EMB_DIM), dtype="float32")
    n_mean = n_top1 = 0
    for c, targets in cid_t.items():
        if c not in idx:
            continue
        vs = [emb[u] for u in targets if u in emb]
        if vs:
            mean_emb[idx[c]] = np.mean(vs, axis=0)
            n_mean += 1
        u1 = cid_rank1.get(c)
        if u1 is not None and u1 in emb:
            top1_emb[idx[c]] = emb[u1]
            n_top1 += 1
    np.save(os.path.join(PROC, "drug_target_emb_mean.npy"), mean_emb)
    np.save(os.path.join(PROC, "drug_target_emb_top1.npy"), top1_emb)
    log(f"[agg-variants] mean-pool mapped {n_mean}, top1 mapped {n_top1} (주 weighted top-k=847 대비)")


# ---------------------------------------------------------------------------
# 3) 절단 ablation (ablation4): 절단(940) 단백질만 청크 mean-pool 재임베딩 → 동일 가중집계
# ---------------------------------------------------------------------------
def _chunk_embed_truncated():
    """protbert_index truncated==1 (940) 서열을 510잔기 청크로 분할→각 청크 임베딩→청크 평균.
    캐시 CHUNKDIR/<uni>.npy 있으면 스킵. UniProt FASTA는 coverage_mapping 캐시-우선 HTTP 사용."""
    import re
    import torch
    from transformers import BertModel, BertTokenizer
    sys.path.insert(0, HERE)
    import coverage_mapping as cm  # 캐시-우선 UniProt FASTA

    trunc = [r["uniprot"] for r in read_csv(os.path.join(TMAP, "protbert_index.csv"))
             if r["truncated"] == "1"]
    os.makedirs(CHUNKDIR, exist_ok=True)
    todo = [u for u in trunc if not os.path.exists(os.path.join(CHUNKDIR, f"{u}.npy"))]
    log(f"[chunk] 절단 단백질 {len(trunc)}개 중 재임베딩 필요 {len(todo)} (캐시 {len(trunc)-len(todo)})")
    if not todo:
        return

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = BertTokenizer.from_pretrained("Rostlab/prot_bert", do_lower_case=False)
    model = BertModel.from_pretrained("Rostlab/prot_bert").to(device).eval()
    log(f"[chunk] ProtBERT({device}) 로드 완료 — 청크 mean-pool 재임베딩 시작")

    def emb_one_chunk(spaced_list):
        """spaced_list: 공백구분 잔기문자열 리스트(각 ≤510잔기). 각 청크 잔기평균 임베딩 (n,1024)."""
        enc = tok(spaced_list, padding=True, truncation=True, max_length=MAX_RES + 2, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            out = model(**enc).last_hidden_state
        mask = enc["attention_mask"].clone()
        mask[:, 0] = 0
        lengths = enc["attention_mask"].sum(dim=1)
        for i, L in enumerate(lengths):
            mask[i, int(L) - 1] = 0            # SEP 제외
        m = mask.unsqueeze(-1).float()
        summed = (out * m).sum(dim=1)
        cnt = m.sum(dim=1).clamp(min=1.0)
        return (summed / cnt).cpu().numpy().astype("float32")

    for j, acc in enumerate(todo, 1):
        txt = cm.http_get_text(f"{cm.UNIPROT}/{acc}.fasta")
        seq = "".join(l.strip() for l in txt.splitlines() if not l.startswith(">")) if txt else ""
        if not seq:
            log(f"    [chunk] {acc} 서열 없음 → 건너뜀")
            continue
        chunks = [seq[i:i + MAX_RES] for i in range(0, len(seq), MAX_RES)]
        spaced = [" ".join(re.sub(r"[UZOB]", "X", ch)) for ch in chunks]
        # 청크가 많으면 8개씩 나눠 임베딩
        parts = []
        for b in range(0, len(spaced), 8):
            parts.append(emb_one_chunk(spaced[b:b + 8]))
        chunk_embs = np.concatenate(parts, axis=0)     # (n_chunk, 1024)
        np.save(os.path.join(CHUNKDIR, f"{acc}.npy"), chunk_embs.mean(axis=0).astype("float32"))
        if j % 50 == 0 or j == len(todo):
            log(f"    [chunk] {j}/{len(todo)}  ({acc}: {len(seq)}aa, {len(chunks)}청크)")


def build_chunk_drug_emb():
    """청크 임베딩(절단 940 교체) + 비절단 980 원본 → 동일 top-k 가중집계로 drug_target_emb_chunk.npy."""
    _chunk_embed_truncated()
    order = cid_order()
    idx = {c: i for i, c in enumerate(order)}
    # 임베딩 dict: 절단은 청크판, 나머지는 원본
    trunc = {r["uniprot"] for r in read_csv(os.path.join(TMAP, "protbert_index.csv"))
             if r["truncated"] == "1"}
    emb = load_emb()
    n_swap = 0
    for u in list(emb.keys()):
        cp = os.path.join(CHUNKDIR, f"{u}.npy")
        if u in trunc and os.path.exists(cp):
            emb[u] = np.load(cp)
            n_swap += 1
    log(f"[chunk] 임베딩 교체 {n_swap}/{len(trunc)} (절단 단백질)")

    # 동일 top-k 가중집계(07_agg_topk.csv weight) — target_pipeline._assemble와 동일 논리
    cid_topk = defaultdict(list)
    for r in read_csv(os.path.join(TMAP, "07_agg_topk.csv")):
        cid_topk[int(r["cid"])].append((r["uniprot"], float(r["weight"])))
    demb = np.zeros((len(order), EMB_DIM), dtype="float32")
    for c, tk in cid_topk.items():
        if c not in idx:
            continue
        acc = np.zeros(EMB_DIM, dtype="float32")
        wsum = 0.0
        for u, w in tk:
            v = emb.get(u)
            if v is None:
                continue
            acc += w * v
            wsum += w
        if wsum > 0:
            demb[idx[c]] = acc / wsum
    np.save(os.path.join(PROC, "drug_target_emb_chunk.npy"), demb)
    # 원본과의 차이 sanity(절단 반영되면 0이 아니어야)
    base = np.load(os.path.join(PROC, "drug_target_emb.npy"))
    diff = np.abs(demb - base).sum(1)
    log(f"[chunk] drug_target_emb_chunk.npy 저장. 원본과 달라진 약물 {int((diff>1e-6).sum())}/847")


def main():
    log(f"[prep] ROOT={ROOT}")
    build_affinity_stats()
    build_aggregation_variants()
    build_chunk_drug_emb()
    log("[prep] 완료 — 파생 피처 저장 (표준화/PCA는 train_ladder에서 train-only fit)")


if __name__ == "__main__":
    main()
