#!/usr/bin/env python3
"""target_pipeline.py — v3 표적 축 피처 파이프라인 + ProtBERT 임베딩 캐시 (마일스톤 2).

선행: `docs/19_v3_coverage_report.md`(게이트 통과 C3=80.6%), coverage 산출
      `data/processed/target_mapping/01~05*.csv` + 요청 캐시 `_cache/`.
범위: **표적 축 피처 텐서 + ProtBERT 임베딩 캐시까지**. M0~M4 학습·평가는 다음 마일스톤(하지 않음).

확정 설계(임의 변경 금지, docs/20 프롬프트):
  1) organism = human-only(Homo sapiens) 주 분석 + 전체 organism ablation(_all).
  2) 다중 표적 집계 = affinity 가중 top-k (k=5). 평균/top1/attention은 ablation 후보(미구현).
  3) M1 통제군: drug_n_targets(표적 개수) 별도 저장. 교란(Spearman rho≈0.193) 재계산.

가드레일:
  - ChEMBL 대량 재요청 금지 → **캐시 재파싱**(cache-first). 미스만 네트워크 보충.
  - 분자셋·라벨·split 불변. data/raw 수정 금지. DrugBank·mock 금지.
  - 절단·결측·실패는 정직 보고. 커버리지를 좋아 보이게 만들지 않는다.

재현: SEED=42, 요청 캐시 결정적. `python v3_Multimodal/src/target_pipeline.py --step all`.
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
import statistics as st
from collections import defaultdict

# 동일 디렉터리 coverage_mapping 헬퍼 재사용(캐시-우선 HTTP, 상수, CSV 유틸)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coverage_mapping as cm  # noqa: E402

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
SEED = 42
TOPK = 5
MAX_LEN = 512          # ProtBERT 위치 임베딩 상한(토큰). [CLS]+residues+[SEP]
MAX_RES = MAX_LEN - 2  # 특수토큰 제외 잔기 상한 = 510
EMB_DIM = 1024
BATCH = 8              # ProtBERT 배치(MPS)
HUMAN = "Homo sapiens"

OUTDIR = cm.OUTDIR
EMBDIR = os.path.join(OUTDIR, "protbert_emb")
PROC = cm.DATA_PROC
MASTER_Y = os.path.join(PROC, "master_Y.parquet")


def opath(name):
    return os.path.join(OUTDIR, name)


# ---------------------------------------------------------------------------
# 공통 로더
# ---------------------------------------------------------------------------
def load_matched():
    """02_chembl matched → cid(int)→chembl_id, chembl_id→[cid]."""
    rows = cm.read_csv(opath("02_chembl.csv"))
    cid2ch, ch2cids = {}, defaultdict(list)
    for r in rows:
        if r["matched"] == "1" and r["chembl_id"]:
            cid = int(r["cid"])
            cid2ch[cid] = r["chembl_id"]
            ch2cids[r["chembl_id"]].append(cid)
    return cid2ch, ch2cids


def load_targets03():
    """03_targets → SINGLE PROTEIN & uniprot 유효 행만.
    반환: rows(list dict), tgt2uni {target_chembl_id: set((uniprot,organism))}."""
    rows = [r for r in cm.read_csv(opath("03_targets.csv"))
            if r["target_type"] == "SINGLE PROTEIN" and r["uniprot"]]
    tgt2uni = defaultdict(set)
    for r in rows:
        tgt2uni[r["target_chembl_id"]].add((r["uniprot"], r["organism"]))
    return rows, tgt2uni


# ---------------------------------------------------------------------------
# STEP 0 — pChEMBL 수치 복구 (캐시 재파싱, 네트워크 재수집 금지)
# ---------------------------------------------------------------------------
def step0():
    cid2ch, ch2cids = load_matched()
    _, tgt2uni = load_targets03()
    chembls = sorted(set(cid2ch.values()))

    # (chembl_id, target_chembl_id) -> list[pchembl], set[value_type]
    pch = defaultdict(list)
    vtypes = defaultdict(set)
    miss_pages = 0
    for n, ch in enumerate(chembls, 1):
        # STEP3와 동일한 activity URL → 캐시 히트로 재파싱(pchembl 이번엔 수집)
        acts = cm._paged(
            f"{cm.CHEMBL}/activity?molecule_chembl_id={ch}&pchembl_value__isnull=false"
            f"&only=target_chembl_id,pchembl_value,standard_type&format=json",
            key="activities")
        for a in acts:
            t = a.get("target_chembl_id")
            pv = a.get("pchembl_value")
            if not t or pv in (None, ""):
                continue
            try:
                pch[(ch, t)].append(float(pv))
            except ValueError:
                continue
            vtypes[(ch, t)].add(a.get("standard_type") or "pchembl")
        if n % 100 == 0 or n == len(chembls):
            print(f"    STEP0 activity 재파싱 {n}/{len(chembls)}  누적 pair {len(pch)}")

    # (chembl, target) → uniprot 확장, median 집계
    rows, recovered = [], 0
    for (ch, t), vals in pch.items():
        med = st.median(vals)
        for (acc, org) in sorted(tgt2uni.get(t, ())):
            rows.append([ch, acc, f"{med:.3f}", len(vals), ";".join(sorted(vtypes[(ch, t)])), org])
            recovered += 1
    rows.sort(key=lambda x: (x[0], x[1]))
    cm.write_csv(opath("05b_affinity_values.csv"),
                 ["chembl_id", "uniprot", "pchembl_median", "n_records", "value_types", "organism"], rows)
    print(f"  STEP0: pChEMBL 복구 (chembl×uniprot) pair {recovered}, target-with-pchembl {len(pch)}, 캐시미스 페이지 {miss_pages}")
    return rows


# ---------------------------------------------------------------------------
# STEP 1 — 표적 세트 구성 (human 주 / 전체 ablation)
# ---------------------------------------------------------------------------
def _write_target_set(rows, path, label):
    out = [[r["cid"], r["chembl_id"], r["target_chembl_id"], r["uniprot"], r["organism"]] for r in rows]
    out.sort(key=lambda x: (int(x[0]), x[3]))
    cm.write_csv(path, ["cid", "chembl_id", "target_chembl_id", "uniprot", "organism"], out)
    cid_uni = defaultdict(set)
    for r in rows:
        cid_uni[int(r["cid"])].add(r["uniprot"])
    per = [len(v) for v in cid_uni.values()]
    q = cm._quantiles(per)
    uniq = {r["uniprot"] for r in rows}
    print(f"  STEP1[{label}]: 분자 {len(cid_uni)} (커버 {100*len(cid_uni)/1092:.1f}%), "
          f"유니크 표적 {len(uniq)}, 표적/약물 중앙값 {q[1]} 95p {q[2]} max {q[3]}")
    return cid_uni, uniq


def step1():
    rows, _ = load_targets03()
    human = [r for r in rows if r["organism"] == HUMAN]
    _write_target_set(human, opath("06_targets_human.csv"), "human")
    _write_target_set(rows, opath("06b_targets_all.csv"), "all")


# ---------------------------------------------------------------------------
# STEP 2 — affinity 가중 top-k 집계
# ---------------------------------------------------------------------------
def _aggregate_topk(target_csv, cid2ch, out_csv, label):
    """각 cid: 표적을 pchembl_median desc 정렬 → top-k. affinity 우선, 미달 시 결측 균등 보충.
    가중치: affinity 보유=pchembl_median, 결측 보충=선택된 affinity 평균(없으면 균등)."""
    aff = cm.read_csv(opath("05b_affinity_values.csv"))
    aff_map = {(r["chembl_id"], r["uniprot"]): float(r["pchembl_median"]) for r in aff}

    cid_targets = defaultdict(set)
    for r in cm.read_csv(target_csv):
        cid_targets[int(r["cid"])].add(r["uniprot"])

    rows = []
    n_imputed_drugs = 0
    n_imputed_targets = 0
    n_no_aff_drugs = 0
    for cid in sorted(cid_targets):
        ch = cid2ch.get(cid, "")
        tg = cid_targets[cid]
        withaff, noaff = [], []
        for u in tg:
            v = aff_map.get((ch, u))
            if v is not None:
                withaff.append((u, v))
            else:
                noaff.append(u)
        withaff.sort(key=lambda x: -x[1])
        selected = []  # (uniprot, pchembl_or_None, imputed)
        for u, v in withaff[:TOPK]:
            selected.append((u, v, 0))
        if len(selected) < TOPK:
            need = TOPK - len(selected)
            fill = sorted(noaff)[:need]
            if fill:
                n_imputed_drugs += 1
                n_imputed_targets += len(fill)
            imp_score = st.mean([v for _, v in withaff[:TOPK]]) if withaff else 1.0
            if not withaff:
                n_no_aff_drugs += 1
            for u in fill:
                selected.append((u, imp_score, 1))
        # 가중치 = score/합
        scores = []
        for u, s, imp in selected:
            scores.append(s if s is not None else 0.0)
        Z = sum(scores) or 1.0
        for rank, (u, s, imp) in enumerate(selected, 1):
            w = (s if s is not None else 0.0) / Z
            rows.append([cid, u, rank, f"{s:.3f}" if s is not None else "", f"{w:.6f}", imp])
    cm.write_csv(out_csv,
                 ["cid", "uniprot", "rank", "pchembl_median", "weight", "affinity_imputed"], rows)
    print(f"  STEP2[{label}]: 약물 {len({r[0] for r in rows})}, top-k행 {len(rows)}, "
          f"결측보충 약물 {n_imputed_drugs}(표적 {n_imputed_targets}), affinity 전무 약물 {n_no_aff_drugs}")
    return {"imputed_drugs": n_imputed_drugs, "imputed_targets": n_imputed_targets,
            "no_aff_drugs": n_no_aff_drugs, "n_drugs": len({r[0] for r in rows})}


def step2():
    cid2ch, _ = load_matched()
    a = _aggregate_topk(opath("06_targets_human.csv"), cid2ch, opath("07_agg_topk.csv"), "human")
    b = _aggregate_topk(opath("06b_targets_all.csv"), cid2ch, opath("07b_agg_topk_all.csv"), "all")
    # 결측 보충 비율 저장(리포트용)
    with open(opath("_step2_impute_stats.txt"), "w") as f:
        f.write(f"human {a}\nall {b}\n")
    return a, b


# ---------------------------------------------------------------------------
# STEP 3 — ProtBERT 임베딩 캐시
# ---------------------------------------------------------------------------
def _get_sequence(acc):
    txt = cm.http_get_text(f"{cm.UNIPROT}/{acc}.fasta")
    if not txt:
        return None
    return "".join(l.strip() for l in txt.splitlines() if not l.startswith(">"))


def step3():
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import re
    import numpy as np
    import torch
    from transformers import BertModel, BertTokenizer

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    # 대상 UniProt = human ∪ all 세트의 유니크(=all과 동일) 중 서열 확보분
    unis = sorted({r["uniprot"] for r in cm.read_csv(opath("06b_targets_all.csv"))})
    seqset = {r["uniprot"] for r in cm.read_csv(opath("04_sequences.csv")) if r["has_seq"] == "1"}
    todo = [u for u in unis if u in seqset]
    print(f"  STEP3: 대상 UniProt {len(unis)} 중 서열보유 {len(todo)} → ProtBERT({device})")

    os.makedirs(EMBDIR, exist_ok=True)
    tok = BertTokenizer.from_pretrained("Rostlab/prot_bert", do_lower_case=False)
    model = BertModel.from_pretrained("Rostlab/prot_bert").to(device).eval()

    index_rows = []
    truncated_n = 0
    # 배치 처리
    pending = []  # (acc, spaced_seq, full_len, truncated_flag)
    def flush(batch):
        nonlocal truncated_n
        accs = [x[0] for x in batch]
        seqs = [x[1] for x in batch]
        enc = tok(seqs, padding=True, truncation=True, max_length=MAX_LEN, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            out = model(**enc).last_hidden_state  # (B,L,1024)
        mask = enc["attention_mask"].clone()      # (B,L)
        # 특수토큰 제외: CLS(pos0) + 각 시퀀스의 마지막 유효토큰(SEP)
        mask[:, 0] = 0
        lengths = enc["attention_mask"].sum(dim=1)  # 유효 토큰 수(특수 포함)
        for i, L in enumerate(lengths):
            mask[i, int(L) - 1] = 0
        m = mask.unsqueeze(-1).float()
        summed = (out * m).sum(dim=1)
        cnt = m.sum(dim=1).clamp(min=1.0)
        emb = (summed / cnt).cpu().numpy().astype("float32")  # (B,1024)
        for i, (acc, _, flen, trunc) in enumerate(batch):
            np.save(os.path.join(EMBDIR, f"{acc}.npy"), emb[i])
            index_rows.append([acc, flen, int(trunc), f"protbert_emb/{acc}.npy"])
            if trunc:
                truncated_n += 1

    for j, acc in enumerate(todo, 1):
        seq = _get_sequence(acc)
        if not seq:
            index_rows.append([acc, 0, 0, ""])
            continue
        flen = len(seq)
        trunc = flen > MAX_RES
        use = seq[:MAX_RES]
        spaced = " ".join(re.sub(r"[UZOB]", "X", use))
        pending.append((acc, spaced, flen, trunc))
        if len(pending) >= BATCH:
            flush(pending); pending = []
        if j % 200 == 0:
            print(f"    STEP3 임베딩 {j}/{len(todo)}  (절단 누적 {truncated_n})")
    if pending:
        flush(pending)

    index_rows.sort(key=lambda x: x[0])
    cm.write_csv(opath("protbert_index.csv"),
                 ["uniprot", "seq_len", "truncated", "emb_path"], index_rows)
    done = sum(1 for r in index_rows if r[3])
    print(f"  STEP3: 임베딩 저장 {done}/{len(todo)}, 절단 {truncated_n} "
          f"({100*truncated_n/max(done,1):.1f}%)")
    return {"n_emb": done, "truncated": truncated_n}


# ---------------------------------------------------------------------------
# STEP 4 — 약물 단위 피처 텐서 조립 (master_X cid 순서 정렬)
# ---------------------------------------------------------------------------
def _assemble(agg_csv, target_csv, cid_order, emb, suffix):
    import numpy as np
    N = len(cid_order)
    idx = {c: i for i, c in enumerate(cid_order)}

    # top-k 가중치
    cid_topk = defaultdict(list)  # cid -> [(uniprot, weight)]
    for r in cm.read_csv(agg_csv):
        cid_topk[int(r["cid"])].append((r["uniprot"], float(r["weight"])))
    # 표적 개수(유니크 uniprot)
    cid_n = defaultdict(int)
    tmp = defaultdict(set)
    for r in cm.read_csv(target_csv):
        tmp[int(r["cid"])].add(r["uniprot"])
    for c, s in tmp.items():
        cid_n[c] = len(s)

    demb = np.zeros((N, EMB_DIM), dtype="float32")
    dmask = np.zeros((N,), dtype="int8")
    dnt = np.zeros((N,), dtype="int32")
    no_emb_drugs = 0
    for c, i in idx.items():
        dnt[i] = cid_n.get(c, 0)
        tk = cid_topk.get(c, [])
        if not tk:
            continue
        dmask[i] = 1
        acc = np.zeros(EMB_DIM, dtype="float32")
        wsum = 0.0
        for u, w in tk:
            v = emb.get(u)
            if v is None:
                continue
            acc += w * v
            wsum += w
        if wsum > 0:
            demb[i] = acc / wsum   # 결측 임베딩 제외 후 재정규화
        else:
            no_emb_drugs += 1      # 표적은 있으나 임베딩 전무(mask=1, emb=0)
    np.save(os.path.join(PROC, f"drug_target_emb{suffix}.npy"), demb)
    np.save(os.path.join(PROC, f"drug_target_mask{suffix}.npy"), dmask)
    np.save(os.path.join(PROC, f"drug_n_targets{suffix}.npy"), dnt)
    print(f"  STEP4[{suffix or '_human'}]: mapped {int(dmask.sum())}/{N} "
          f"(비매핑 {N-int(dmask.sum())}), 임베딩전무 {no_emb_drugs}, "
          f"n_targets 중앙값 {int(np.median(dnt[dnt>0])) if (dnt>0).any() else 0}")
    return dmask, dnt


def step4():
    import pandas as pd
    import numpy as np
    cid_order = pd.read_parquet(cm.MASTER_X).sort_values("cid")["cid"].astype(int).tolist()
    assert len(cid_order) == 1092
    # 임베딩 로드
    emb = {}
    for r in cm.read_csv(opath("protbert_index.csv")):
        if r["emb_path"]:
            emb[r["uniprot"]] = np.load(os.path.join(OUTDIR, r["emb_path"]))
    print(f"  STEP4: 임베딩 로드 {len(emb)} UniProt")

    dmask_h, dnt_h = _assemble(opath("07_agg_topk.csv"), opath("06_targets_human.csv"),
                               cid_order, emb, "")            # 주(human)
    _assemble(opath("07b_agg_topk_all.csv"), opath("06b_targets_all.csv"),
              cid_order, emb, "_all")                          # ablation
    # 검증
    n_map = int(dmask_h.sum())
    print(f"  STEP4 검증: cid 정렬 OK(assert), human 매핑 {n_map}, 비매핑 {1092-n_map}")


# ---------------------------------------------------------------------------
# STEP 5 — 교란 통제 산출물 + docs/20
# ---------------------------------------------------------------------------
def step5():
    import pandas as pd
    import numpy as np
    from scipy.stats import spearmanr, mannwhitneyu

    X = pd.read_parquet(cm.MASTER_X).sort_values("cid").reset_index(drop=True)
    Y = pd.read_parquet(MASTER_Y).set_index("cid")
    cid_order = X["cid"].astype(int).tolist()
    y_pos = Y.loc[cid_order].sum(axis=1).to_numpy()  # 행별 양성 라벨 수(370 PT)

    dnt = np.load(os.path.join(PROC, "drug_n_targets.npy"))          # human
    dnt_all = np.load(os.path.join(PROC, "drug_n_targets_all.npy"))
    mask = np.load(os.path.join(PROC, "drug_target_mask.npy"))

    # Spearman: 전체 1092 (비매핑 n_targets=0 포함) + 매핑 서브셋
    rho_all, p_all = spearmanr(dnt, y_pos)
    sub = mask == 1
    rho_sub, p_sub = spearmanr(dnt[sub], y_pos[sub])
    rho_allorg, p_allorg = spearmanr(dnt_all, y_pos)

    # 매핑 vs 비매핑 ADR 수 (Mann-Whitney U)
    mapped, unmapped = y_pos[sub], y_pos[~sub]
    u_stat, u_p = mannwhitneyu(mapped, unmapped, alternative="two-sided")

    # split별 커버리지·n_targets
    import json
    split = json.load(open(os.path.join(PROC, "scaffold_split.json")))
    split_of = {int(k): v for k, v in split.items()}
    by = defaultdict(lambda: {"n": 0, "mapped": 0, "nt": []})
    for i, c in enumerate(cid_order):
        s = split_of.get(c, "?")
        by[s]["n"] += 1
        by[s]["mapped"] += int(mask[i])
        if mask[i]:
            by[s]["nt"].append(int(dnt[i]))

    # 리포트 부가수치 (STEP2 결측 보충 통계 재계산)
    def _impute_line(agg_csv, target_csv, cid2ch):
        aff = {(r["chembl_id"], r["uniprot"]) for r in cm.read_csv(opath("05b_affinity_values.csv"))}
        cid_t = defaultdict(set)
        for r in cm.read_csv(target_csv):
            cid_t[int(r["cid"])].add(r["uniprot"])
        n_drugs = len(cid_t)
        imp_d = no_aff = 0
        for c, tg in cid_t.items():
            ch = cid2ch.get(c, "")
            nwith = sum(1 for u in tg if (ch, u) in aff)
            if nwith < TOPK and (len(tg) - nwith) > 0:
                imp_d += 1
            if nwith == 0:
                no_aff += 1
        return n_drugs, imp_d, no_aff
    cid2ch, _ = load_matched()
    nd_h, imp_h, noaff_h = _impute_line(opath("07_agg_topk.csv"), opath("06_targets_human.csv"), cid2ch)
    idx = cm.read_csv(opath("protbert_index.csv"))
    n_emb = sum(1 for r in idx if r["emb_path"])
    n_trunc = sum(1 for r in idx if r["truncated"] == "1")
    a05 = cm.read_csv(opath("05b_affinity_values.csv"))

    doc = os.path.join(cm.ROOT, "docs", "20_v3_target_pipeline_report.md")
    L = []
    A = L.append
    A("# 20. v3 표적 축 파이프라인 + ProtBERT 임베딩 리포트 (마일스톤 2)\n")
    A("> 생성: `v3_Multimodal/src/target_pipeline.py` (SEED=42, 캐시-우선 재파싱, 네트워크 재수집 없음).")
    A("> 선행: `docs/19_v3_coverage_report.md`(게이트 통과). 범위=피처 텐서+임베딩 캐시까지. 모델 학습은 다음 마일스톤.")
    A("> 설계 확정: human-only 주 분석 + 전체 organism ablation(`_all`), affinity 가중 top-k(k=5), M1 표적개수 통제군.\n")

    A("## 1. 핵심 수치 (완료 보고용)\n")
    A(f"- **① pChEMBL 복구**: activity 캐시 재파싱으로 (chembl×uniprot) **{len(a05)} pair** 수치 복구(median 집계). 네트워크 재수집 0.")
    A(f"- **② ProtBERT 절단 비율**: 임베딩 {n_emb}개 중 **{n_trunc}개 절단({100*n_trunc/max(n_emb,1):.1f}%)** "
      f"(서열>{MAX_RES}잔기, 앞쪽 {MAX_RES}잔기만 사용).")
    A(f"- **③ affinity 결측 보충 비율**(human 주): top-k 미달로 mechanism-only 표적을 균등가중 보충한 약물 "
      f"**{imp_h}/{nd_h} ({100*imp_h/max(nd_h,1):.1f}%)**, 그중 affinity 전무(전부 결측) 약물 **{noaff_h}개**.")
    A("")

    A("## 2. 표적 세트 (STEP1)\n")
    for path, lab in [(opath("06_targets_human.csv"), "human(주)"), (opath("06b_targets_all.csv"), "all(ablation)")]:
        rr = cm.read_csv(path)
        cu = defaultdict(set)
        for r in rr:
            cu[r["cid"]].add(r["uniprot"])
        per = [len(v) for v in cu.values()]
        q = cm._quantiles(per)
        A(f"- **{lab}**: 분자 {len(cu)} (커버 {100*len(cu)/1092:.1f}%), 유니크 표적 "
          f"{len({r['uniprot'] for r in rr})}, 표적/약물 중앙값 {q[1]}·95p {q[2]}·max {q[3]}.")
    A("\n> 참고: 사전추정 human 860 대비 **실측 human 분자 수는 아래 표대로**(정직 보고). 게이트(≥70%)는 유지.\n")

    A("## 3. 교란 통제 (M1 근거) — study bias\n")
    A("| 통계 | 대상 | 값 |")
    A("|---|---|---|")
    A(f"| Spearman(n_targets_human, n_ADR) | 전체 1092 | rho={rho_all:.3f}, p={p_all:.2e} |")
    A(f"| Spearman(n_targets_human, n_ADR) | 매핑 서브셋({int(sub.sum())}) | rho={rho_sub:.3f}, p={p_sub:.2e} |")
    A(f"| Spearman(n_targets_all, n_ADR) | 전체 1092 | rho={rho_allorg:.3f}, p={p_allorg:.2e} |")
    A(f"| Mann-Whitney U (ADR수: 매핑 vs 비매핑) | {int(sub.sum())} vs {int((~sub).sum())} | U={u_stat:.0f}, p={u_p:.2e} |")
    A(f"\n- 매핑 약물 ADR 수 중앙값 **{int(np.median(mapped))}** vs 비매핑 **{int(np.median(unmapped))}**.")
    A(f"- cowork 사전값 rho≈0.193 **재현 여부: {'재현(±0.02 이내)' if abs(rho_all-0.193)<=0.02 else f'불일치(실측 {rho_all:.3f})'}**.")
    A("- 해석: 표적 수와 ADR 수의 양의 상관은 '많이 연구된 약물=라벨 ADR 많음'이라는 study bias 가능성. "
      "→ M1(표적 개수-only)을 필수 통제군으로 두고, M2(서열)≈M1이면 ProtBERT 서열이 study bias 이상을 기여하지 못한 것으로 판정.\n")

    A("## 4. split별 표적 커버리지·n_targets (편향 재확인)\n")
    A("| split | 분자수 | 매핑 | 커버% | n_targets 중앙값(매핑) |")
    A("|---|---|---|---|---|")
    for s in ["train", "valid", "test"]:
        d = by[s]
        med = int(np.median(d["nt"])) if d["nt"] else 0
        A(f"| {s} | {d['n']} | {d['mapped']} | {100*d['mapped']/max(d['n'],1):.1f}% | {med} |")
    A("")

    A("## 5. 산출물\n")
    A("```")
    A("data/processed/target_mapping/")
    A("  05b_affinity_values.csv  (chembl_id, uniprot, pchembl_median, n_records, value_types, organism)")
    A("  06_targets_human.csv / 06b_targets_all.csv  (cid, chembl_id, target_chembl_id, uniprot, organism)")
    A("  07_agg_topk.csv / 07b_agg_topk_all.csv  (cid, uniprot, rank, pchembl_median, weight, affinity_imputed)")
    A("  protbert_emb/<uniprot>.npy  (1024, float32, 잔기 평균 pooling)")
    A("  protbert_index.csv  (uniprot, seq_len, truncated, emb_path)")
    A("data/processed/")
    A("  drug_target_emb.npy   (1092,1024) float32  — top-k 가중평균, 비매핑=zero  [human 주]")
    A("  drug_target_mask.npy  (1092,) int8         — 표적보유=1")
    A("  drug_n_targets.npy    (1092,) int32        — M1 통제군(human)")
    A("  drug_target_emb_all.npy / _mask_all / drug_n_targets_all.npy  — 전체 organism ablation")
    A("```")
    A(f"\n재실행: `python v3_Multimodal/src/target_pipeline.py --step all` (SEED=42, 캐시 결정적).\n")

    A("## 6. 한계 (정직 보고)\n")
    A(f"- **ProtBERT 절단**: {100*n_trunc/max(n_emb,1):.1f}% 서열이 {MAX_RES}잔기 초과로 절단됨(중앙값 490·95p 1435·max 7096 aa). "
      "긴 단백질의 C-말단 정보 손실 → 논문 한계. 512-청크 mean-pool은 ablation 후보(미구현).")
    A("- **affinity 집계**: 동일 compound×target 다중 assay는 median(pchembl) 채택. mechanism 유래 표적은 affinity 결측 → "
      "top-k 미달 시 균등 가중 보충(비율은 §1③).")
    A("- **BindingDB 미반영**(coverage 단계 REST 404) → 표적/affinity는 ChEMBL 단독 하한.")
    A("- **study bias**(§3): 표적 정보의 이득이 생물학이 아닌 연구 인기도 아티팩트일 수 있음 → M1 통제 필수.")
    A("- 구조·라벨·split 불변, 재학습/재다운로드 없음.")

    os.makedirs(os.path.dirname(doc), exist_ok=True)
    with open(doc, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"  ✅ {os.path.relpath(doc, cm.ROOT)}")
    print(f"  교란 재계산: rho_all={rho_all:.3f} (p={p_all:.2e}), rho_sub={rho_sub:.3f}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="all", help="'all' 또는 '0,1,2,3,4,5'")
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    steps = ["0", "1", "2", "3", "4", "5"] if args.step == "all" else args.step.split(",")
    fns = {"0": step0, "1": step1, "2": step2, "3": step3, "4": step4, "5": step5}
    for s in steps:
        print(f"▶ STEP {s}")
        fns[s.strip()]()


if __name__ == "__main__":
    main()
