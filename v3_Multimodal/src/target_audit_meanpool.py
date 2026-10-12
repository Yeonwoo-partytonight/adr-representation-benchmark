#!/usr/bin/env python3
"""target_audit_meanpool.py — 사전등록서(docs/30) §13 실행순서 1번.

(A) 표적 mapping 정밀 audit 표 산출 + (B) 표적 단순평균(mean-pool) 임베딩 재계산.

이 스크립트는 **데이터 준비 전용**이다. 모델 학습·성능 조회·확증 split(seed 201~205) 접근을
일절 하지 않는다. 모든 산출은 **기존 동결 산출물의 결정적 재계산**이며
재다운로드·재임베딩·mock·DrugBank 사용이 전혀 없다(네트워크 호출 0).

근거 문서: docs/30_preregistration_OSF_clean.md (§2 audit, §4 집계, §5, §13),
           docs/20_v3_target_pipeline_report.md, docs/19_v3_coverage_report.md.

입력(모두 기존 산출물 재사용):
  data/processed/master_X.parquet                       — 분자셋 1,092 (cid 인덱스; 배열 행순서 기준)
  data/processed/scaffold_split.json                    — seed-42 개발 split (A-6 서술 감사 전용)
  data/processed/target_mapping/03_targets.csv          — target_type/source (A-1/A-3 gap)
  data/processed/target_mapping/05b_affinity_values.csv — binding 근거 (A-2/A-3)
  data/processed/target_mapping/06_targets_human.csv    — ★ primary: human single-protein 표적
  data/processed/target_mapping/06b_targets_all.csv     — sensitivity: 전체 organism
  data/processed/target_mapping/07_agg_topk.csv         — affinity_imputed (A-2 mechanism-only proxy)
  data/processed/target_mapping/protbert_index.csv      — per-target ProtBERT 임베딩 경로
  data/processed/target_mapping/protbert_emb/<uni>.npy  — per-target 1024-d 임베딩(재사용만)
  data/processed/target_mapping/_cache/<hash>.json.txt  — UniProt FASTA 캐시(A-6, 네트워크 금지)

산출:
  data/processed/target_mapping/audit/*.csv             — audit 표 7종
  data/processed/drug_target_emb_meanpool.npy 외 human 4종 + all 4종
  docs/31_v3_target_audit_meanpool_report.md            — (이 스크립트가 아니라 별도로 채움; 여기선 stats.json)

재현:  python v3_Multimodal/src/target_audit_meanpool.py
결정적: 모든 무작위 seed=42 고정, 부동소수 집계 순서 고정(uniprot 정렬 후 누적).
"""
from __future__ import annotations
import csv
import hashlib
import json
import os
import sys
import statistics as st
from collections import defaultdict, Counter

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 경로/상수
# ---------------------------------------------------------------------------
SEED = 42
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROC = os.path.join(ROOT, "data", "processed")
TM = os.path.join(PROC, "target_mapping")
CACHE = os.path.join(TM, "_cache")
AUDIT = os.path.join(TM, "audit")
EMBDIR = os.path.join(TM, "protbert_emb")
UNIPROT = "https://rest.uniprot.org/uniprotkb"
EMB_DIM = 1024
N_TOTAL = 1092
HUMAN = "Homo sapiens"


def rd(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def wr(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  ✅ {os.path.relpath(path, ROOT)}  ({len(rows)} rows)")


def cache_fasta(acc):
    """UniProt FASTA를 _cache/에서만 읽는다(네트워크 금지). 미존재=None."""
    url = f"{UNIPROT}/{acc}.fasta"
    h = hashlib.sha1(url.encode()).hexdigest()[:20]
    p = os.path.join(CACHE, h + ".json.txt")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        txt = f.read()
    return "".join(l.strip() for l in txt.splitlines() if not l.startswith(">"))


# ---------------------------------------------------------------------------
# 공통 로더
# ---------------------------------------------------------------------------
def load_cid_order():
    X = pd.read_parquet(os.path.join(PROC, "master_X.parquet")).sort_values("cid")
    order = X["cid"].astype(int).tolist()
    assert len(order) == N_TOTAL, f"master_X rows {len(order)} != {N_TOTAL}"
    return order


def load_split():
    sp = json.load(open(os.path.join(PROC, "scaffold_split.json")))
    return {int(k): v for k, v in sp.items()}


def cid_target_sets(csv_path):
    """cid(int) -> set(uniprot).  06_/06b_ 표적셋 로더."""
    d = defaultdict(set)
    for r in rd(csv_path):
        d[int(r["cid"])].add(r["uniprot"])
    return d


def load_emb_dict():
    """protbert_index → {uniprot: np.array(1024,)}.  임베딩 확보 표적만."""
    emb = {}
    for r in rd(os.path.join(TM, "protbert_index.csv")):
        if r["emb_path"]:
            emb[r["uniprot"]] = np.load(os.path.join(TM, r["emb_path"]))
    return emb


# ===========================================================================
# PART A — 표적 mapping 정밀 audit
# ===========================================================================
def audit_A1_target_types(stats):
    """A-1. 표적 유형 분해 (03_targets.csv target_type).  primary(06_human) vs all(06b) 대조."""
    t3 = rd(os.path.join(TM, "03_targets.csv"))
    by_type_rows = Counter()
    by_type_uni = defaultdict(set)
    by_type_drug = defaultdict(set)
    for r in t3:
        tt = r["target_type"] or "(빈값)"
        by_type_rows[tt] += 1
        if r["uniprot"]:
            by_type_uni[tt].add(r["uniprot"])
        by_type_drug[tt].add(r["cid"])

    rows = []
    for tt, _ in sorted(by_type_rows.items(), key=lambda x: -x[1]):
        rows.append(["03_raw", tt, by_type_rows[tt], len(by_type_uni[tt]), len(by_type_drug[tt])])

    # primary / all 요약
    h = cid_target_sets(os.path.join(TM, "06_targets_human.csv"))
    a = cid_target_sets(os.path.join(TM, "06b_targets_all.csv"))
    h_uni = {u for s in h.values() for u in s}
    a_uni = {u for s in a.values() for u in s}
    h_rows = len(rd(os.path.join(TM, "06_targets_human.csv")))
    a_rows = len(rd(os.path.join(TM, "06b_targets_all.csv")))
    rows.append(["primary_06_human (SINGLE PROTEIN ∩ human)", "SINGLE PROTEIN", h_rows, len(h_uni), len(h)])
    rows.append(["all_06b (SINGLE PROTEIN, all organism)", "SINGLE PROTEIN", a_rows, len(a_uni), len(a)])

    wr(os.path.join(AUDIT, "audit_target_types.csv"),
       ["category", "target_type", "n_target_rows", "n_unique_uniprot", "n_drugs"], rows)
    stats["A1"] = {"by_type_rows": dict(by_type_rows),
                   "primary_uni": len(h_uni), "all_uni": len(a_uni),
                   "primary_drugs": len(h), "all_drugs": len(a),
                   "primary_rows": h_rows, "all_rows": a_rows}


def audit_A2_binding_vs_mechanism(stats):
    """A-2. binding 근거(05b 존재) vs mechanism-only(07 affinity_imputed=1).
    gap: 03 source가 전부 'chembl' 단일값 → ChEMBL mechanism(MoA) endpoint 명시 구분 불가."""
    # 02_chembl: cid -> chembl_id
    cid2ch = {int(r["cid"]): r["chembl_id"] for r in rd(os.path.join(TM, "02_chembl.csv"))
              if r["matched"] == "1" and r["chembl_id"]}
    # binding 근거: (chembl_id, uniprot) in 05b
    aff = {(r["chembl_id"], r["uniprot"]) for r in rd(os.path.join(TM, "05b_affinity_values.csv"))}

    # human primary 표적셋 기준으로 두 축 계산
    h = cid_target_sets(os.path.join(TM, "06_targets_human.csv"))
    binding_targets = set()   # (cid, uniprot) with affinity evidence
    mechonly_targets = set()  # (cid, uniprot) mapped human target lacking affinity evidence
    binding_drugs, mechonly_drugs = set(), set()
    for cid, us in h.items():
        ch = cid2ch.get(cid, "")
        for u in us:
            if (ch, u) in aff:
                binding_targets.add((cid, u)); binding_drugs.add(cid)
            else:
                mechonly_targets.add((cid, u)); mechonly_drugs.add(cid)

    # 07 affinity_imputed=1 (top-k 보충된 mechanism-only 표적) — 별도 proxy
    t7 = rd(os.path.join(TM, "07_agg_topk.csv"))
    imp_targets = {(int(r["cid"]), r["uniprot"]) for r in t7 if r["affinity_imputed"] == "1"}
    imp_drugs = {int(r["cid"]) for r in t7 if r["affinity_imputed"] == "1"}

    rows = [
        ["binding_evidence (05b affinity 존재)", "human_primary",
         len(binding_targets), len(binding_drugs)],
        ["affinity_missing (매핑 human 표적 중 05b 부재)", "human_primary",
         len(mechonly_targets), len(mechonly_drugs)],
        ["affinity_imputed=1 (07 top-k 보충 표적)", "human_primary",
         len(imp_targets), len(imp_drugs)],
    ]
    wr(os.path.join(AUDIT, "audit_binding_vs_mechanism.csv"),
       ["axis", "scope", "n_drug_target_pairs", "n_drugs"], rows)
    stats["A2"] = {"binding_pairs": len(binding_targets), "binding_drugs": len(binding_drugs),
                   "affmiss_pairs": len(mechonly_targets), "affmiss_drugs": len(mechonly_drugs),
                   "imputed_pairs": len(imp_targets), "imputed_drugs": len(imp_drugs),
                   "sources_in_03": sorted({r["source"] for r in rd(os.path.join(TM, "03_targets.csv"))})}


def audit_A3_value_types(stats):
    """A-3. confidence/action은 gap(캐시 미수집). 대체로 05b value_types(assay 유형) 분포."""
    a5 = rd(os.path.join(TM, "05b_affinity_values.csv"))
    vt_pairs = Counter()   # value_type -> (chembl,uniprot) pair 수(개별 type 분해)
    vt_combo = Counter()   # 원본 value_types 조합 문자열
    for r in a5:
        vt_combo[r["value_types"]] += 1
        for v in r["value_types"].split(";"):
            if v:
                vt_pairs[v] += 1
    rows = [["single_assay_type", v, n] for v, n in vt_pairs.most_common()]
    rows += [["value_types_combo", v, n] for v, n in vt_combo.most_common(15)]
    wr(os.path.join(AUDIT, "audit_value_types.csv"),
       ["grouping", "value_type", "n_chembl_uniprot_pairs"], rows)
    stats["A3"] = {"value_type_counts": dict(vt_pairs),
                   "gap": "target confidence·action_type(agonist/antagonist/inhibitor)는 "
                          "mechanism/action endpoint 미수집으로 현재 캐시에 없음 → 재다운로드 없이 도출 불가."}


def audit_A4_targets_per_drug(stats):
    """A-4. 약물당 표적 수 분포 (primary 06_human 기준 + all 06b 병기).  분모=전체 1,092."""
    def dist(csv_path):
        d = cid_target_sets(csv_path)
        per = {c: len(s) for c, s in d.items()}
        vals = list(per.values())  # 매핑된 약물만(>0)
        # 전체 1,092 기준 구간(0 포함)
        n0 = N_TOTAL - len(vals)
        n1 = sum(1 for v in vals if v == 1)
        n2_5 = sum(1 for v in vals if 2 <= v <= 5)
        n6 = sum(1 for v in vals if v >= 6)
        med = int(np.median(vals)) if vals else 0
        q1 = int(np.percentile(vals, 25)) if vals else 0
        q3 = int(np.percentile(vals, 75)) if vals else 0
        return {"n_mapped": len(vals), "median": med, "q1": q1, "q3": q3,
                "min": min(vals) if vals else 0, "max": max(vals) if vals else 0,
                "bin_0": n0, "bin_1": n1, "bin_2_5": n2_5, "bin_6plus": n6}

    ph = dist(os.path.join(TM, "06_targets_human.csv"))
    pa = dist(os.path.join(TM, "06b_targets_all.csv"))
    hdr = ["scope", "n_mapped_drugs", "median", "IQR_q1", "IQR_q3", "min", "max",
           "drugs_0_targets", "drugs_1_target", "drugs_2_5_targets", "drugs_6plus_targets"]
    rows = [
        ["human_primary", ph["n_mapped"], ph["median"], ph["q1"], ph["q3"], ph["min"], ph["max"],
         ph["bin_0"], ph["bin_1"], ph["bin_2_5"], ph["bin_6plus"]],
        ["all_organism", pa["n_mapped"], pa["median"], pa["q1"], pa["q3"], pa["min"], pa["max"],
         pa["bin_0"], pa["bin_1"], pa["bin_2_5"], pa["bin_6plus"]],
    ]
    wr(os.path.join(AUDIT, "audit_targets_per_drug.csv"), hdr, rows)
    stats["A4"] = {"human": ph, "all": pa}


def audit_A5_mapping_failures(stats):
    """A-5. mapping 실패·제외 사유별 약물 수.  19/20 리포트 C2~C5와 교차확인."""
    r2 = rd(os.path.join(TM, "02_chembl.csv"))
    matched_cids = {int(r["cid"]) for r in r2 if r["matched"] == "1"}
    unmatched_cids = N_TOTAL - len(matched_cids)  # ChEMBL compound 미매칭

    t3 = rd(os.path.join(TM, "03_targets.csv"))
    # SINGLE PROTEIN uniprot 표적 (all organism / human)
    sp_all = defaultdict(set)
    sp_hum = defaultdict(set)
    for r in t3:
        if r["target_type"] == "SINGLE PROTEIN" and r["uniprot"]:
            sp_all[int(r["cid"])].add(r["uniprot"])
            if r["organism"] == HUMAN:
                sp_hum[int(r["cid"])].add(r["uniprot"])
    no_sp_all = len(matched_cids) - sum(1 for c in matched_cids if sp_all.get(c))
    no_sp_hum = len(matched_cids) - sum(1 for c in matched_cids if sp_hum.get(c))

    # 서열 미확보: 약물의 매핑 human 표적이 모두 서열 없음(04_sequences has_seq=0)
    seqset = {r["uniprot"] for r in rd(os.path.join(TM, "04_sequences.csv")) if r["has_seq"] == "1"}
    h = cid_target_sets(os.path.join(TM, "06_targets_human.csv"))
    no_seq_hum = sum(1 for c, us in h.items() if not (us & seqset))
    # 임베딩 미확보(human): 매핑 human 표적 중 임베딩 있는 게 하나도 없음
    emb = load_emb_dict()
    embset = set(emb.keys())
    no_emb_hum = sum(1 for c, us in h.items() if not (us & embset))

    # affinity 전무(human): 매핑 human 표적 중 05b 근거가 하나도 없음
    cid2ch = {int(r["cid"]): r["chembl_id"] for r in r2 if r["matched"] == "1" and r["chembl_id"]}
    aff = {(r["chembl_id"], r["uniprot"]) for r in rd(os.path.join(TM, "05b_affinity_values.csv"))}
    no_aff_hum = 0
    for c, us in h.items():
        ch = cid2ch.get(c, "")
        if not any((ch, u) in aff for u in us):
            no_aff_hum += 1

    rows = [
        ["ChEMBL_compound_미매칭", "all(1092)", unmatched_cids],
        ["matched이나_SINGLE_PROTEIN_UniProt_표적0", "all_organism(matched 943)", no_sp_all],
        ["matched이나_human_SINGLE_PROTEIN_표적0", "human(matched 943)", no_sp_hum],
        ["human매핑이나_서열_전무", "human_primary(847)", no_seq_hum],
        ["human매핑이나_ProtBERT임베딩_전무", "human_primary(847)", no_emb_hum],
        ["human매핑이나_affinity근거_전무", "human_primary(847)", no_aff_hum],
    ]
    # excluded target type별 수(SINGLE PROTEIN 아닌 유형의 drug×target 행)
    excl = Counter()
    for r in t3:
        if r["target_type"] and r["target_type"] != "SINGLE PROTEIN":
            excl[r["target_type"]] += 1
    for tt, n in sorted(excl.items(), key=lambda x: -x[1]):
        rows.append([f"excluded_target_type::{tt}", "03_raw rows", n])

    wr(os.path.join(AUDIT, "audit_mapping_failures.csv"),
       ["failure_reason", "scope", "n"], rows)
    stats["A5"] = {"unmatched": unmatched_cids, "no_sp_all": no_sp_all, "no_sp_hum": no_sp_hum,
                   "no_seq_hum": no_seq_hum, "no_emb_hum": no_emb_hum, "no_aff_hum": no_aff_hum,
                   "matched": len(matched_cids)}


def audit_A6_train_test_overlap(stats):
    """A-6. seed-42 개발 split 위 train/test 표적 overlap (서술적 감사).
    Jaccard(표적 union) + test 표적별 train 표적과의 max sequence identity
    (biopython PairwiseAligner, BLOSUM62 local, gap -11/-1, identities/min(len)). FASTA=캐시."""
    from Bio.Align import PairwiseAligner, substitution_matrices
    split = load_split()
    h = cid_target_sets(os.path.join(TM, "06_targets_human.csv"))
    a = cid_target_sets(os.path.join(TM, "06b_targets_all.csv"))

    def unis(d, name):
        s = set()
        for c, us in d.items():
            if split.get(c) == name:
                s |= us
        return s

    def jaccard(s1, s2):
        return len(s1 & s2) / len(s1 | s2) if (s1 | s2) else 0.0

    tr_h, va_h, te_h = unis(h, "train"), unis(h, "valid"), unis(h, "test")
    tr_a, va_a, te_a = unis(a, "train"), unis(a, "valid"), unis(a, "test")
    j_h = jaccard(tr_h, te_h)
    j_a = jaccard(tr_a, te_a)

    # ---- test(human) 표적별 max sequence identity vs train(human) ----
    aligner = PairwiseAligner()
    aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
    aligner.mode = "local"
    aligner.open_gap_score = -11
    aligner.extend_gap_score = -1

    seqs = {}
    def seq(u):
        if u not in seqs:
            seqs[u] = cache_fasta(u)
        return seqs[u]

    train_list = sorted(tr_h)
    train_seqs = [(u, seq(u)) for u in train_list]
    train_seqs = [(u, s) for u, s in train_seqs if s]  # 서열 확보분만

    rows = []
    test_only_max = []
    n_align = 0
    test_sorted = sorted(te_h)
    for i, tu in enumerate(test_sorted, 1):
        if tu in tr_h:
            rows.append(["human_primary", tu, 1, "1.0000", tu])
            continue
        ts = seq(tu)
        if not ts:
            rows.append(["human_primary", tu, 0, "", ""])
            continue
        best_id, best_u = 0.0, ""
        for u, s in train_seqs:
            try:
                aln = aligner.align(ts, s)[0]
                ident = aln.counts().identities / min(len(ts), len(s))
            except Exception:
                continue
            n_align += 1
            if ident > best_id:
                best_id, best_u = ident, u
        rows.append(["human_primary", tu, 0, f"{best_id:.4f}", best_u])
        test_only_max.append(best_id)
        if i % 10 == 0 or i == len(test_sorted):
            print(f"    A-6 test 표적 {i}/{len(test_sorted)} (누적 alignment {n_align})")

    wr(os.path.join(AUDIT, "audit_train_test_overlap.csv"),
       ["scope", "test_uniprot", "in_train", "max_seq_identity", "closest_train_uniprot"], rows)

    to_arr = np.array(test_only_max) if test_only_max else np.array([0.0])
    stats["A6"] = {
        "jaccard_human": j_h, "jaccard_all": j_a,
        "n_train_targets_human": len(tr_h), "n_test_targets_human": len(te_h),
        "n_test_in_train_human": len(te_h & tr_h), "n_test_only_human": len(te_h - tr_h),
        "n_train_targets_all": len(tr_a), "n_test_targets_all": len(te_a),
        "n_test_in_train_all": len(te_a & tr_a), "n_test_only_all": len(te_a - tr_a),
        "test_only_maxid_median": float(np.median(to_arr)),
        "test_only_maxid_max": float(to_arr.max()),
        "test_only_ge90": int((to_arr >= 0.90).sum()),
        "test_only_lt40": int((to_arr < 0.40).sum()),
        "n_alignments": n_align,
    }


def audit_A7_manual_sample(stats):
    """A-7. 수동 audit worksheet: seed=42 무작위 8%(ceil=88) + 빈 양식 컬럼.
    에이전트가 직접 판정하지 않는다 — 빈 양식만."""
    order = load_cid_order()
    n = int(np.ceil(0.08 * N_TOTAL))  # ceil(87.36)=88
    rng = np.random.RandomState(SEED)
    idx = sorted(rng.choice(N_TOTAL, size=n, replace=False).tolist())
    sample_cids = [order[i] for i in idx]

    # 보조 정보
    ik = {int(r["cid"]): (r["smiles"], r["inchikey"]) for r in rd(os.path.join(TM, "01_inchikey.csv"))}
    ch = {int(r["cid"]): r["chembl_id"] for r in rd(os.path.join(TM, "02_chembl.csv"))
          if r["matched"] == "1"}
    h = cid_target_sets(os.path.join(TM, "06_targets_human.csv"))
    # cid -> ingredient_id (약물명 대체 식별자; 큐레이션 약물명 문자열은 동결 산출물에 없음)
    ing = defaultdict(list)
    for r in rd_ing():
        ing[int(r["cid"])].append(str(r["ingredient_id"]))

    rows = []
    for c in sample_cids:
        smi, ikey = ik.get(c, ("", ""))
        tgts = ";".join(sorted(h.get(c, [])))
        rows.append([
            c, ";".join(sorted(set(ing.get(c, [])))), smi, ikey, ch.get(c, ""),
            tgts, len(h.get(c, [])),
            "", "", "", "", "",  # 빈 양식: salt/prodrug/stereoisomer/wrong_target/note
        ])
    wr(os.path.join(AUDIT, "audit_manual_sample.csv"),
       ["cid", "onsides_ingredient_id", "smiles_canonical", "inchikey", "chembl_id",
        "mapped_human_targets_uniprot", "n_human_targets",
        "salt_mismatch", "prodrug_mismatch", "stereoisomer_mismatch", "wrong_target", "note"],
       rows)
    stats["A7"] = {"n_sample": n, "seed": SEED}


def rd_ing():
    df = pd.read_parquet(os.path.join(PROC, "ingredient_to_cid.parquet"))
    return df.to_dict("records")


# ===========================================================================
# PART B — mean-pool 집계 재계산
# ===========================================================================
def build_meanpool(target_csv, emb, cid_order, suffix, stats):
    """각 약물의 매핑 표적 **전체**에 대해 per-target ProtBERT의 단순 산술평균(비가중).
    top-k 자르기·가중 없음. 임베딩 없는 표적은 평균에서 제외하되 개수 기록.
    부동소수 결정성: 표적 uniprot 정렬 후 누적."""
    tgt = cid_target_sets(target_csv)  # cid -> set(uniprot)  (전체 표적)
    N = len(cid_order)
    demb = np.zeros((N, EMB_DIM), dtype="float32")
    dmask = np.zeros((N,), dtype="int8")
    dcov = np.zeros((N,), dtype="float32")
    dnt = np.zeros((N,), dtype="int32")

    n_mapped = 0
    n_zero_no_emb = 0  # 매핑 표적은 있으나 임베딩 전무
    for i, c in enumerate(cid_order):
        us = sorted(tgt.get(c, set()))   # 정렬 → 결정적 누적
        n_map = len(us)
        if n_map == 0:
            continue  # 비매핑: 전부 0 유지
        used = [u for u in us if u in emb]
        k = len(used)
        dcov[i] = k / n_map  # coverage_ratio
        dnt[i] = k
        if k == 0:
            n_zero_no_emb += 1
            continue  # 매핑되나 임베딩 전무: emb=0, mask=0
        acc = np.zeros(EMB_DIM, dtype="float64")  # 누적은 f64로(정밀), 저장은 f32
        for u in used:
            acc += emb[u].astype("float64")
        demb[i] = (acc / k).astype("float32")
        dmask[i] = 1
        n_mapped += 1

    np.save(os.path.join(PROC, f"drug_target_emb_meanpool{suffix}.npy"), demb)
    np.save(os.path.join(PROC, f"drug_target_mask_meanpool{suffix}.npy"), dmask)
    np.save(os.path.join(PROC, f"drug_target_coverage_meanpool{suffix}.npy"), dcov)
    np.save(os.path.join(PROC, f"drug_n_targets_meanpool{suffix}.npy"), dnt)
    cov_med = float(np.median(dcov[dcov > 0])) if (dcov > 0).any() else 0.0
    print(f"  STEP-B[{suffix or '_human'}]: mask=1 {int(dmask.sum())}/{N} "
          f"(매핑 표적有·임베딩전무 {n_zero_no_emb}), coverage 중앙값(매핑>0) {cov_med:.3f}")
    stats[f"B{suffix or '_human'}"] = {
        "mask_sum": int(dmask.sum()),
        "n_zero_no_emb": n_zero_no_emb,
        "cov_mean_mapped": float(dcov[dmask == 1].mean()) if (dmask == 1).any() else 0.0,
        "n_targets_used_median": int(np.median(dnt[dmask == 1])) if (dmask == 1).any() else 0,
        "n_targets_used_max": int(dnt.max()),
        "shape": list(demb.shape), "dtype": str(demb.dtype),
    }
    return demb, dmask


def diff_report(meanpool_h, dmask_h, stats):
    """mean-pool(human) vs 기존 top-k 가중(drug_target_emb) 및 기존 mean(drug_target_emb_mean) diff."""
    def cmp(other_path, key):
        if not os.path.exists(other_path):
            stats.setdefault("diff", {})[key] = {"missing": True}
            return
        other = np.load(other_path)
        both = (dmask_h == 1) & (np.linalg.norm(other, axis=1) > 0)
        cos = []
        for i in np.where(both)[0]:
            a, b = meanpool_h[i], other[i]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na > 0 and nb > 0:
                cos.append(float(np.dot(a, b) / (na * nb)))
        cos = np.array(cos) if cos else np.array([0.0])
        max_abs = float(np.abs(meanpool_h[both] - other[both]).max()) if both.any() else 0.0
        stats.setdefault("diff", {})[key] = {
            "n_compared_rows": int(both.sum()),
            "cos_mean": float(cos.mean()), "cos_median": float(np.median(cos)),
            "cos_min": float(cos.min()), "frac_cos_ge_0999": float((cos >= 0.999).mean()),
            "max_abs_elem_diff": max_abs,
        }
        print(f"  diff vs {os.path.basename(other_path)}: rows {int(both.sum())} "
              f"cos_mean {cos.mean():.4f} cos_min {cos.min():.4f} max|Δ| {max_abs:.4f}")

    cmp(os.path.join(PROC, "drug_target_emb.npy"), "vs_topk_weighted")
    cmp(os.path.join(PROC, "drug_target_emb_mean.npy"), "vs_existing_mean")


# --- (선택) split별 train-fit scaler·PCA 훅 스텁 — 실제 실행 금지(사전등록서 §4) ---
def fit_scaler_pca(train_idx):  # noqa: D401  (STUB ONLY — 호출 금지)
    """z-score·PCA-64는 fold별 train에서만 적합해야 하므로 이 데이터 준비 단계에서는
    적합·변환을 실행하지 않는다. 본 함수는 후속 모델링 단계용 시그니처 스텁일 뿐이며
    이 스크립트에서 호출되지 않는다(사전등록서 §4: raw mean까지만)."""
    raise NotImplementedError("데이터 준비 단계에서 scaler/PCA 적합 금지 (사전등록서 §4).")


# ===========================================================================
def main():
    os.makedirs(AUDIT, exist_ok=True)
    stats = {"seed": SEED, "n_total": N_TOTAL}
    cid_order = load_cid_order()

    print("▶ PART A — mapping audit")
    audit_A1_target_types(stats)
    audit_A2_binding_vs_mechanism(stats)
    audit_A3_value_types(stats)
    audit_A4_targets_per_drug(stats)
    audit_A5_mapping_failures(stats)
    audit_A6_train_test_overlap(stats)
    audit_A7_manual_sample(stats)

    print("\n▶ PART B — mean-pool 재계산")
    emb = load_emb_dict()
    print(f"  임베딩 로드 {len(emb)} UniProt")
    meanpool_h, dmask_h = build_meanpool(os.path.join(TM, "06_targets_human.csv"),
                                         emb, cid_order, "", stats)          # human primary
    build_meanpool(os.path.join(TM, "06b_targets_all.csv"),
                   emb, cid_order, "_all", stats)                            # all-organism sensitivity

    # 정렬 일치 assert: meanpool 행순서 == 기존 drug_target_emb 행순서(둘 다 master_X cid 정렬)
    assert meanpool_h.shape == (N_TOTAL, EMB_DIM)
    assert dmask_h.shape == (N_TOTAL,)

    print("\n▶ diff vs 기존 임베딩")
    diff_report(meanpool_h, dmask_h, stats)

    with open(os.path.join(AUDIT, "_audit_meanpool_stats.json"), "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  ✅ stats → {os.path.relpath(os.path.join(AUDIT, '_audit_meanpool_stats.json'), ROOT)}")
    print("  (z-score·PCA·모델학습·확증 split 조회 없음 — 사전등록서 §4/§5 준수)")


if __name__ == "__main__":
    main()
