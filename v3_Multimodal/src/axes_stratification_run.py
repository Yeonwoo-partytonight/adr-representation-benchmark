#!/usr/bin/env python3
"""axes_stratification_run.py — 블록 Z: 등록 §11 **세 번째 축** A3·A4·A5·A6 층화.

성격
----
블록 H(`stratification_run.py`)·블록 L(`pid_stratification_run.py`)과 **같은 성격의 확증 조회**다.
두 러너의 층 배정·집계·재표집 경로를 **import 재사용**하고 층 정의만 A3·A4·A5·A6 으로 바꾼다.
`stratification_run.py`·`pid_stratification_run.py` 는 **한 줄도 수정하지 않는다**.

  · 모델학습·재추론 0 — consensus 는 기존 산출(블록 C·블록 I)을 **기계 판독**만 한다.
  · 새 seed·B·CI 방법·재표집 단위 추첨 0 — 전부 `stratification_run` 에서 import 재사용.
  · 산출은 **전량 `_sealed/`**. 공개는 표본수·라벨·B·seed·시간·해시·게이트 PASS/FAIL 뿐이며
    **Δ 의 부호조차 공개하지 않는다.**
  · 개봉(`open_sealed`) 0 · 성공판정(`decision.py`) 0 · 다중성 보정 0 · `emit_sign` 0 · 네트워크 0.

스테이지
  verify     Z-1 게이트 + Z-3 입력 판정(pchembl 정본 · A5 canonicalization) → gates_public.json
  strata     Z-4 4축 fold-local 층 배정 + 회계 assert + A5×847 분해 → axes_assignment.csv
  pilot      Z-5 계측(층별 Δ 직접 실측 + B=100 보정) → pilot_timing.json
  estimate   Z-6 본계산 → _sealed/axes_result.json + axes_public.json
  recheck    공개 산출물 교차 redaction 스캔(재계산 0)
  all        위 5개를 순서대로

실행: .venv/bin/python3 v3_Multimodal/src/axes_stratification_run.py --stage all
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

for _k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_k, "1")

import numpy as np                                                      # noqa: E402
import pandas as pd                                                     # noqa: E402

from compute_lock import ComputeLock, gate_a_load, gate_b_exclusive     # noqa: E402
import stratification_run as H                                          # noqa: E402  (블록 H — 무수정 재사용)
from sap import bootstrap as sap_bootstrap                              # noqa: E402
from sap import metrics as sap_metrics                                  # noqa: E402
from sap import redaction as sap_redaction                              # noqa: E402
from sap import signflip as sap_signflip                                # noqa: E402
from sap import unseen_target as sap_unseen                             # noqa: E402

KST = timezone(timedelta(hours=9))

# ═══════════════════════════════════════════════════════════════════════════
# 동결 상수 — **전부 블록 H 에서 그대로 가져온다**(새 값·새 seed 를 뽑지 않는다, §0)
#   ⚠️ 아래 이름들에 리터럴을 대입하면 종료검증 #6(AST) 이 실패한다.
# ═══════════════════════════════════════════════════════════════════════════
SEED_BOOTSTRAP = H.SEED_BOOTSTRAP        # 6001
SEED_SIGNFLIP = H.SEED_SIGNFLIP          # 6002
B_MAIN = H.B_MAIN                        # 10000
B_PILOT = H.B_PILOT                      # 100
BOOT_UNIT = H.BOOT_UNIT                  # "scaffold_cluster"
ELIGIBLE_PT = H.ELIGIBLE_PT              # None — 370 PT 전열

EXPECT_N_DRUGS = H.EXPECT_N_DRUGS
EXPECT_N_PT = H.EXPECT_N_PT
EXPECT_DENOM = H.EXPECT_DENOM            # 847
EXPECT_N_NO_TARGET = H.EXPECT_N_NO_TARGET  # 245
EXPECT_N_SCAFFOLD_GROUPS = H.EXPECT_N_SCAFFOLD_GROUPS
EXPECT_LADDER_FREEZE_SHA16 = H.EXPECT_LADDER_FREEZE_SHA16
EXPECT_SAP_MANIFEST_SHA16 = H.EXPECT_SAP_MANIFEST_SHA16
WALL_ABORT_DAYS = H.WALL_ABORT_DAYS      # 7.0

# AST 검사 대상 — 이 이름들은 `H.<NAME>` 참조로만 정의돼야 한다.
IMPORTED_CONSTANT_NAMES = [
    "SEED_BOOTSTRAP", "SEED_SIGNFLIP", "B_MAIN", "B_PILOT", "BOOT_UNIT", "ELIGIBLE_PT",
    "EXPECT_N_DRUGS", "EXPECT_N_PT", "EXPECT_DENOM", "EXPECT_N_NO_TARGET",
    "EXPECT_N_SCAFFOLD_GROUPS", "EXPECT_LADDER_FREEZE_SHA16", "EXPECT_SAP_MANIFEST_SHA16",
    "WALL_ABORT_DAYS",
]

EXPECT_GUARD_N_FILES = 273               # 블록 Y 종료 기준(`_sealed/**`, access.log 제외)
EXPECT_A5_POPULATION = 943               # `02_chembl.csv` chembl_id 매칭 약물
EXPECT_PAIR_COVERED = 12514              # 동결 coverage_denominators.pair_level 분자
EXPECT_PAIR_TOTAL = 12613                # 〃 분모
EXPECT_DRUG_NO_PCHEMBL = 16              # 〃 drug_level "16 of 847"

# 입력 지문(값은 열지 않고 sha256 만 대조)
EXPECT_SHA = {
    "experiments/runs/v3_consensus_rep123/_sealed/consensus_M1b.npz":
        "f77a69528ebdb88c",
    "experiments/runs/v3_consensus_rep123/_sealed/consensus_M2b.npz":
        "8594592e2afae583",
    "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_P-ID.npz":
        "9598da3498b1d3ce",
    "experiments/runs/v3_stratification/strata_assignment.csv":
        "8247f4318150414b",
    "v3_Multimodal/config/a5_mechanism_freeze.json":
        "3419b2f793d74051",
    "experiments/provenance/a5_requery_manifest.json":
        "66023c1d4403bbb2",
    "data/processed/target_mapping/a5_mechanism_targets.csv":
        "62fb85d013a15d15",
}

AXES_BINS = {
    "A3": ["{0}", "(0,0.5)", "[0.5,1)", "{1}"],
    "A4": ["{0}", "(0,0.5)", "[0.5,1)", "{1}", "no_evidence"],
    "A5": ["{0}", "{1}", "no_mechanism", "not_estimable"],
    "A6": ["{0}", "{1}", "no_evidence"],
}
AXIS_LABEL = {
    "A3": "unseen target count / total target count",
    "A4": "pChEMBL-weighted unseen proportion",
    "A5": "mechanism-target indicator",
    "A6": "dominant-target unseen indicator",
}
CONTRASTS = [
    {"id": "C1", "base": "M1b", "comp": "M2b", "holm_family": "① M2b-M1b"},
    {"id": "C2", "base": "P-ID", "comp": "M2b", "holm_family": "② M2b-P-ID"},
]
BIN_MID_BOUNDARY = 0.5                   # 동결 구간 경계(`(0,0.5)` / `[0.5,1)`)
NO_TARGET_LABEL = "no_target"            # 사전 정의 제외 집합 라벨(층 아님)

# ═══════════════════════════════════════════════════════════════════════════
# 경로
# ═══════════════════════════════════════════════════════════════════════════
RUNS = os.path.join(ROOT, "experiments", "runs")
RUN_DIR = os.path.join(RUNS, "v3_stratification_axes")
SEALED_DIR = os.path.join(RUN_DIR, "_sealed")
RUN_LOG = os.path.join(RUN_DIR, "run.log")
F_GATES = os.path.join(RUN_DIR, "gates_public.json")
F_ASSIGN = os.path.join(RUN_DIR, "axes_assignment.csv")
F_ASSIGN_SUM = os.path.join(RUN_DIR, "axes_summary.json")
F_PILOT = os.path.join(RUN_DIR, "pilot_timing.json")
F_PUBLIC = os.path.join(RUN_DIR, "axes_public.json")
F_SCAN = os.path.join(RUN_DIR, "redaction_scan_public.json")
F_CKPT = os.path.join(SEALED_DIR, "checkpoint.jsonl")
F_ENVFP = os.path.join(RUN_DIR, "env_fingerprint.json")

CONS_MAIN_DIR = os.path.join(RUNS, "v3_consensus_rep123", "_sealed")
CONS_PID_DIR = os.path.join(RUNS, "v3_confirm_rest_consensus_rep123", "_sealed")
F_CONS = {"M1b": os.path.join(CONS_MAIN_DIR, "consensus_M1b.npz"),
          "M2b": os.path.join(CONS_MAIN_DIR, "consensus_M2b.npz"),
          "P-ID": os.path.join(CONS_PID_DIR, "consensus_P-ID.npz")}

TM = os.path.join(ROOT, "data", "processed", "target_mapping")
F_TARGETS = os.path.join(TM, "06_targets_human.csv")
F_CHEMBL = os.path.join(TM, "02_chembl.csv")
F_AFF05B = os.path.join(TM, "05b_affinity_values.csv")
F_AGG07 = os.path.join(TM, "07_agg_topk.csv")
F_A5 = os.path.join(TM, "a5_mechanism_targets.csv")

CFG = os.path.join(ROOT, "v3_Multimodal", "config")
F_A5_FREEZE = os.path.join(CFG, "a5_mechanism_freeze.json")
F_A5_AMEND = os.path.join(CFG, "a5_boundary_amendment.json")
F_POST_FREEZE = os.path.join(CFG, "post_interim_freeze_v1_0.json")
F_STRATA_H = H.F_STRATA


# ═══════════════════════════════════════════════════════════════════════════
# 유틸 — 공개 로그에 AP·Δ·CI·p·부호를 절대 쓰지 않는다
# ═══════════════════════════════════════════════════════════════════════════
def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    try:
        os.makedirs(RUN_DIR, exist_ok=True)
        with open(RUN_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def dump_json(path, obj):
    return H.dump_json(path, obj)


def guard_snapshot():
    """`experiments/runs/**/_sealed/**` 전 트리 sha256 — 본 블록 신규 디렉터리·access.log 제외."""
    snap = {}
    own = os.path.abspath(SEALED_DIR) + os.sep
    for dirpath, _dn, filenames in os.walk(RUNS):
        if "_sealed" not in os.path.relpath(dirpath, RUNS).split(os.sep):
            continue
        if (os.path.abspath(dirpath) + os.sep).startswith(own):
            continue
        for fn in sorted(filenames):
            if fn == "access.log":
                continue
            p = os.path.join(dirpath, fn)
            if os.path.isfile(p):
                snap[os.path.relpath(p, ROOT)] = sha256_file(p)
    return dict(sorted(snap.items()))


def log_machine_read(access_dir, path_rel, purpose):
    """sealed 파일 **기계 판독**(사람 노출 0) — `open_sealed`(사람 열람)와 구분."""
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": "등록 §11 세 번째 축 — A3·A4·A5·A6 층화(블록 Z)",
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    for dd in (access_dir, SEALED_DIR):
        os.makedirs(dd, exist_ok=True)
        with open(os.path.join(dd, "access.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def count_open_sealed():
    n = 0
    for dirpath, _dn, fns in os.walk(RUNS):
        if "access.log" not in fns:
            continue
        with open(os.path.join(dirpath, "access.log"), encoding="utf-8") as f:
            n += sum(1 for ln in f if "OPEN sealed" in ln)
    return n


def assert_constants_imported():
    """종료검증 #6 — 동결 상수가 `H.<NAME>` 참조로만 정의됐는지 **AST** 로 확인."""
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id in IMPORTED_CONSTANT_NAMES:
                v = node.value
                ok = (isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name)
                      and v.value.id == "H" and v.attr == t.id)
                assert ok, (f"[AST FAIL] `{t.id}` 이 `H.{t.id}` 재사용이 아니다 "
                            f"— 상수 재정의 금지(§0)")
                found[t.id] = f"H.{v.attr}"
    missing = [n for n in IMPORTED_CONSTANT_NAMES if n not in found]
    assert not missing, f"[AST FAIL] import 재사용 확인 실패: {missing}"
    return {"n_constants_checked": len(found), "bindings": found,
            "literal_redefinitions": 0, "new_seed_drawn": 0, "pass": True}


# ═══════════════════════════════════════════════════════════════════════════
# Z-3-1  pchembl_median 정본 파일 판정 (비순환 — 동결 커버리지 상수로 결정)
# ═══════════════════════════════════════════════════════════════════════════
def determine_pchembl_source(est_cids):
    """동결 `coverage_denominators` 12,514/12,613 · drug 16/847 을 **재현하는 파일**을 정본으로."""
    tg = pd.read_csv(F_TARGETS)
    pairs = set(zip(tg["cid"].astype(int), tg["uniprot"].astype(str)))
    assert len(pairs) == EXPECT_PAIR_TOTAL, \
        f"06_targets_human (cid,uniprot) pair {len(pairs)} != {EXPECT_PAIR_TOTAL}"

    ch = pd.read_csv(F_CHEMBL)
    ch = ch[ch["chembl_id"].notna()][["cid", "chembl_id"]]
    aff = pd.read_csv(F_AFF05B)
    m = aff.merge(ch, on="chembl_id", how="inner")
    m = m[m["pchembl_median"].notna()]
    cand = {
        "05b_affinity_values.csv": {
            "key": "(chembl_id, uniprot) → 02_chembl.csv 로 cid 결합",
            "pairs": {(int(c), str(u)): float(v) for c, u, v in
                      zip(m["cid"], m["uniprot"], m["pchembl_median"])},
        },
    }
    top = pd.read_csv(F_AGG07)
    t2 = top[top["pchembl_median"].notna()]
    cand["07_agg_topk.csv"] = {
        "key": "(cid, uniprot) 직접",
        "pairs": {(int(c), str(u)): float(v) for c, u, v in
                  zip(t2["cid"], t2["uniprot"], t2["pchembl_median"])},
    }

    evidence, chosen = {}, None
    for name, info in cand.items():
        covered = pairs & set(info["pairs"])
        have = {c for (c, _u) in covered}
        n_no_pchembl = sum(1 for c in est_cids if c not in have)
        ev = {"key_rule": info["key"], "n_pairs_filled": len(covered),
              "n_pairs_total": len(pairs), "n_drugs_without_any_pchembl_of_847": n_no_pchembl,
              "reproduces_frozen_pair_level": bool(len(covered) == EXPECT_PAIR_COVERED),
              "reproduces_frozen_drug_level": bool(n_no_pchembl == EXPECT_DRUG_NO_PCHEMBL)}
        ev["reproduces_frozen_coverage"] = bool(ev["reproduces_frozen_pair_level"]
                                                and ev["reproduces_frozen_drug_level"])
        evidence[name] = ev
        if ev["reproduces_frozen_coverage"]:
            assert chosen is None, "정본 후보가 2개 이상 커버리지를 재현했다 — 판정 불가, 중단"
            chosen = name
    assert chosen is not None, (
        f"[중단] 어느 후보도 동결 커버리지 {EXPECT_PAIR_COVERED}/{EXPECT_PAIR_TOTAL} · "
        f"drug {EXPECT_DRUG_NO_PCHEMBL}/847 을 재현하지 못했다: {evidence}")

    # 정본 파일의 pair 가중치 — key 는 **canonical** accession
    raw_w = {k: v for k, v in cand[chosen]["pairs"].items() if k in pairs}
    weights, collisions = {}, []
    for (c, u), v in raw_w.items():
        cu = sap_unseen.canonicalize_accession(u, None, None)
        if (c, cu) in weights and weights[(c, cu)] != v:
            collisions.append({"cid": c, "canonical": cu})
        weights[(c, cu)] = v
    assert not collisions, f"canonicalization 이 서로 다른 pchembl 을 충돌시켰다: {collisions[:5]}"

    verdict = {
        "_rule": ("동결 문면은 파일을 지목하지 않는다(`pchembl_median as produced by the existing "
                  "frozen pipeline`). 러너가 임의로 고르지 않고 **동결 커버리지 상수를 재현하는 "
                  "파일**로 판정했다 — 비순환 판정."),
        "frozen_coverage_verbatim": {"pair_level": f"{EXPECT_PAIR_COVERED} of {EXPECT_PAIR_TOTAL}",
                                     "drug_level": f"{EXPECT_DRUG_NO_PCHEMBL} of 847 mapped drugs "
                                                   f"have no pChEMBL at all"},
        "candidates": evidence,
        "canonical_file": chosen,
        "canonical_file_sha256": sha256_file(os.path.join(TM, chosen)),
        "n_weight_pairs_after_canonicalization": len(weights),
        "canonicalization_collisions": 0,
    }
    return weights, verdict


# ═══════════════════════════════════════════════════════════════════════════
# Z-3-2  A5 표적 — canonicalize_set(t, None, None) 필수 통과
# ═══════════════════════════════════════════════════════════════════════════
def load_a5(est_cids):
    """A5 mechanism 표적 + Z-2 A/B/C/D 분해. **canonicalize_set 통과 강제.**"""
    am = json.load(open(F_A5_AMEND, encoding="utf-8"))
    assert am["supersedes_nothing"] is True
    assert am["bins_final"] == AXES_BINS["A5"], "amendment bins_final 과 러너 구간 불일치"
    assert set(am["cases"]) == {"A", "B", "C", "D"}

    df = pd.read_csv(F_A5)
    pop = set(df["cid"].astype(int).unique())
    assert len(pop) == EXPECT_A5_POPULATION, f"A5 모집단 {len(pop)} != {EXPECT_A5_POPULATION}"

    def _nonempty(x):
        return isinstance(x, str) and x.strip() != ""

    cat, targets_raw = {}, {}
    for c, sub in df.groupby(df["cid"].astype(int)):
        rec = sub[sub["resolution_source"] != "no_mechanism"]
        if len(rec) == 0:
            cat[c] = "A"                                  # mechanism 레코드 없음
            targets_raw[c] = set()
            continue
        with_t = rec[rec["target_chembl_id"].map(_nonempty)]
        if len(with_t) == 0:
            cat[c] = "B"                                  # 레코드는 있으나 표적 없음
            targets_raw[c] = set()
            continue
        uni = {str(u).strip() for u in with_t["uniprot"] if _nonempty(u)}
        if not uni:
            cat[c] = "C"                                  # 표적은 있으나 UniProt 전부 미해석
            targets_raw[c] = set()
        else:
            cat[c] = "D"
            targets_raw[c] = uni

    # ★ Z-3-2 — 블록 H 와 **같은 함수·같은 인자**로 정규화(생략 시 unseen 과대계상)
    all_raw = set().union(*targets_raw.values()) if targets_raw else set()
    all_canon = sap_unseen.canonicalize_set(all_raw, None, None)
    targets = {c: sap_unseen.canonicalize_set(t, None, None) for c, t in targets_raw.items()}

    est = set(est_cids)
    dec_943 = {k: sum(1 for c in pop if cat[c] == k) for k in "ABCD"}
    dec_847 = {k: sum(1 for c in est if cat.get(c) == k) for k in "ABCD"}
    assert sum(dec_847.values()) == EXPECT_DENOM, \
        f"[중단] 847 내부 A/B/C/D 합 {sum(dec_847.values())} != {EXPECT_DENOM}"
    assert sum(dec_943.values()) == EXPECT_A5_POPULATION

    info = {
        "population_chembl_matched": len(pop),
        "estimation_denominator": EXPECT_DENOM,
        "intersection_943_and_847": len(pop & est),
        "in_847_not_in_943": len(est - pop),
        "in_943_not_in_847": len(pop - est),
        "in_943_not_in_847_note": ("847 밖 = 비매핑 245(no_target) 사전 제외 집합의 일부. "
                                   "A5 모집단(943)과 추정 모수(847)는 서로 다른 집합이다."),
        "decomposition_943": dec_943,
        "decomposition_847": dec_847,
        "decomposition_847_sum": sum(dec_847.values()),
        "decomposition_case_map": {"A": "no_mechanism", "B": "no_mechanism",
                                   "C": "not_estimable", "D": "{0}/{1}"},
        "canonicalization": {
            "function": "sap.unseen_target.canonicalize_set(t, None, None)",
            "args": "secondary_to_primary=None, seq_representative=None (isoform 절단만)",
            "identical_to_block_H": ("stratification_run.py:284-285 와 동일 함수·동일 인자"),
            "n_unique_uniprot_before": len(all_raw),
            "n_unique_uniprot_after": len(all_canon),
            "applied_before_unseen_comparison": True,
        },
        "amendment_sha256": sha256_file(F_A5_AMEND),
        "amendment_at_kst": am["amended_at_kst"],
        "analysis_label": am["analysis_label"],
        "analysis_label_applies_to": am["analysis_label_scope"]["applies_to"],
    }
    assert info["intersection_943_and_847"] == EXPECT_DENOM, "943 ∩ 847 != 847"
    assert info["in_847_not_in_943"] == 0, "847 중 A5 모집단 밖 약물이 있다"
    return cat, targets, info


# ═══════════════════════════════════════════════════════════════════════════
# Z-4  층 배정 (4축 · fold-local)
# ═══════════════════════════════════════════════════════════════════════════
def _bin4(n_unseen_w, n_all_w, all_unseen, none_unseen):
    """A3·A4 공통 4구간. 0/1 은 **집합 판정**으로 확정(부동소수 오차 배제)."""
    if none_unseen:
        return "{0}"
    if all_unseen:
        return "{1}"
    p = n_unseen_w / n_all_w
    return "(0,0.5)" if p < BIN_MID_BOUNDARY else "[0.5,1)"


def assign_axes(d, weights, a5_cat, a5_targets):
    rows = []
    for r in (1, 2, 3):
        fold_arr = d["folds"][r]
        T_train = H.train_targets_by_fold(d["cid_order"], d["cid2targets"], fold_arr)
        for i, c in enumerate(d["cid_order"]):
            c = int(c)
            f = int(fold_arr[i])
            T_d = d["cid2targets"].get(c, set())
            Ttr = T_train[f]
            if len(T_d) == 0:
                rows.append({"cid": c, "rep": r, "fold": f, "A3": NO_TARGET_LABEL,
                             "A4": NO_TARGET_LABEL, "A5": NO_TARGET_LABEL,
                             "A6": NO_TARGET_LABEL, "n_targets": 0, "n_unseen_targets": 0,
                             "n_pairs_with_pchembl": 0})
                continue
            unseen = T_d - Ttr

            # A3 — 개수 비율(정수 연산, 정확)
            a3 = _bin4(len(unseen), len(T_d), all_unseen=(len(unseen) == len(T_d)),
                       none_unseen=(len(unseen) == 0))

            # A4 — pchembl 가중 비율. 결측 pair 는 분자·분모 양쪽에서 제외.
            obs = {t: weights[(c, t)] for t in T_d if (c, t) in weights}
            if not obs:
                a4, a6 = "no_evidence", "no_evidence"
            else:
                obs_unseen = {t for t in obs if t in unseen}
                a4 = _bin4(sum(obs[t] for t in obs_unseen), sum(obs.values()),
                           all_unseen=(len(obs_unseen) == len(obs)),
                           none_unseen=(len(obs_unseen) == 0))
                # A6 — dominant = pchembl 최대, 동점 시 UniProt 사전순 최소
                dom = min(obs, key=lambda t: (-obs[t], t))
                a6 = "{1}" if dom in unseen else "{0}"

            # A5 — Z-2 amendment 4구분
            k = a5_cat.get(c)
            if k in ("A", "B"):
                a5 = "no_mechanism"
            elif k == "C":
                a5 = "not_estimable"
            elif k == "D":
                tm = a5_targets[c]
                assert tm, "case D 인데 mechanism 표적 집합이 비어 있다"
                a5 = "{1}" if (tm - Ttr) else "{0}"
            else:
                a5 = "not_estimable"                    # A5 모집단 밖(847 내부에는 없음)

            rows.append({"cid": c, "rep": r, "fold": f, "A3": a3, "A4": a4, "A5": a5, "A6": a6,
                         "n_targets": len(T_d), "n_unseen_targets": len(unseen),
                         "n_pairs_with_pchembl": len(obs)})
    df = pd.DataFrame(rows)
    for ax in AXES_BINS:
        piv = df.pivot(index="cid", columns="rep", values=ax)
        df[f"stable_{ax}"] = df["cid"].map(piv.nunique(axis=1) == 1)
    return df


def stratum_members(df, axis, value):
    piv = df.pivot(index="cid", columns="rep", values=axis)
    sel = (piv.nunique(axis=1) == 1) & (piv[1] == value)
    return sorted(int(c) for c in piv.index[sel])


def unstable_members(df, axis):
    piv = df.pivot(index="cid", columns="rep", values=axis)
    return sorted(int(c) for c in piv.index[piv.nunique(axis=1) > 1])


def assert_axes_accounting(df, excl):
    """Z-4 회계 하드 게이트 — 축마다 Σ stable + unstable == 847 · 847+245 == 1,092 · 네 축 집합 동일."""
    assert len(df) == EXPECT_N_DRUGS * 3, f"행수 {len(df)} != {EXPECT_N_DRUGS * 3}"
    assert len(excl) == EXPECT_N_NO_TARGET, f"no-target {len(excl)} != {EXPECT_N_NO_TARGET}"
    denoms, sets = {}, {}
    for axis, values in AXES_BINS.items():
        stable = [c for v in values for c in stratum_members(df, axis, v) if c not in excl]
        unstable = [c for c in unstable_members(df, axis) if c not in excl]
        assert len(set(stable)) == len(stable), f"{axis} stable 중복"
        denoms[axis] = len(stable) + len(unstable)
        sets[axis] = set(stable) | set(unstable)
        assert denoms[axis] == EXPECT_DENOM, (
            f"[회계 FAIL] {axis}: stable {len(stable)} + unstable {len(unstable)} "
            f"= {denoms[axis]} != {EXPECT_DENOM}")
        assert denoms[axis] + len(excl) == EXPECT_N_DRUGS, (
            f"[회계 FAIL] {axis}: {denoms[axis]} + {len(excl)} != {EXPECT_N_DRUGS}")
    base = sets["A3"]
    for a in AXES_BINS:
        assert sets[a] == base, f"[회계 FAIL] 축별 추정 대상 약물 집합 불일치: {a}"
    return {"n_total_drugs": EXPECT_N_DRUGS, "n_excluded_no_target": len(excl),
            "denominator_estimated": EXPECT_DENOM, "per_axis": denoms,
            "axes_estimation_sets_identical": True, "pass": True}


def estimation_units(df, excl):
    """추정 대상 층 — (axis, stratum, cids). 비어 있는 층은 만들지 않는다."""
    units = []
    for axis, values in AXES_BINS.items():
        for v in values:
            cids = [c for c in stratum_members(df, axis, v) if c not in excl]
            if cids:
                units.append({"axis": axis, "stratum": v, "kind": "stable", "cids": cids})
        cids = [c for c in unstable_members(df, axis) if c not in excl]
        if cids:
            units.append({"axis": axis, "stratum": "unstable_stratum", "kind": "unstable",
                          "cids": cids})
    return units


def support_stats(cids, d):
    idx = H.row_index(d, cids)
    y = d["Ym"][idx]
    sc = d["scaffold"][idx]
    pos = y.sum(axis=0)
    return {"n_drugs": len(cids),
            "n_scaffold_clusters": int(len(np.unique(sc))),
            "n_pt_meeting_positive_support":
                int((pos >= sap_unseen.MIN_SUPPORT["min_positive_pt_support"]).sum())}


def inference_label(st):
    ok = (st["n_drugs"] >= sap_unseen.MIN_SUPPORT["min_drugs"]
          and st["n_pt_meeting_positive_support"]
          >= sap_unseen.MIN_SUPPORT["min_positive_pt_support"])
    return "formal" if ok else "descriptive"


# ═══════════════════════════════════════════════════════════════════════════
# consensus 판독 · 대비 계산
# ═══════════════════════════════════════════════════════════════════════════
def load_consensus(d):
    for key, path in F_CONS.items():
        log_machine_read(os.path.dirname(path), os.path.relpath(path, ROOT),
                         f"등록 §11 세 번째 축 층화 입력(consensus {key}) — 기계 판독")
    out = {}
    for key, path in F_CONS.items():
        with np.load(path) as z:
            out[key] = z["consensus"]
            out[key + "_cid"] = z["cid"].astype(int)
        assert out[key].shape == (EXPECT_N_DRUGS, EXPECT_N_PT), f"{key} shape {out[key].shape}"
        assert np.array_equal(out[key + "_cid"], np.array(d["cid_order"], dtype=int)), \
            f"{key} cid 정렬이 master_X 와 다르다"
        assert not np.isnan(out[key]).any() and not np.isinf(out[key]).any(), f"{key} NaN/inf"
    return out


def run_unit(cids, d, base_arr, comp_arr, B, seed_boot, seed_flip):
    """블록 L 과 동일 슬롯 매핑 — 인자 순서 (기준 arm, 비교 arm), Δ = AP(비교) − AP(기준)."""
    idx = H.row_index(d, cids)
    y_s = d["Ym"][idx]
    base_s = base_arr[idx]
    comp_s = comp_arr[idx]
    sg_s = d["scaffold"][idx]

    t0 = time.perf_counter()
    ap_base = sap_metrics.macro_ap(y_s, base_s, ELIGIBLE_PT)
    ap_comp = sap_metrics.macro_ap(y_s, comp_s, ELIGIBLE_PT)
    t_ap = time.perf_counter() - t0

    t0 = time.perf_counter()
    boot = sap_bootstrap.paired_scaffold_bootstrap(
        base_s, comp_s, y_s, sg_s, eligible_pt=ELIGIBLE_PT, B=B, seed=seed_boot, unit=BOOT_UNIT)
    t_boot = time.perf_counter() - t0

    t0 = time.perf_counter()
    flip = sap_signflip.scaffold_signflip(
        base_s, comp_s, y_s, sg_s, eligible_pt=ELIGIBLE_PT, B=B, seed=seed_flip)
    t_flip = time.perf_counter() - t0

    return {"macro_ap_baseline": ap_base, "macro_ap_comparison": ap_comp,
            "delta": float(ap_comp["macro_ap"] - ap_base["macro_ap"]),
            "bootstrap": boot, "signflip": flip,
            "timing_s": {"macro_ap": t_ap, "bootstrap": t_boot, "signflip": t_flip}}


# ═══════════════════════════════════════════════════════════════════════════
# 공개 산출물 방어 (Z-7) — 키 스캔 + **값 스캔**
# ═══════════════════════════════════════════════════════════════════════════
FORBIDDEN_EXACT = {"macro_ap", "delta", "sign", "boot", "null_summary", "per_pt_ap",
                   "delta_obs", "delta_sign", "p_two_sided", "macro_ap_baseline",
                   "macro_ap_comparison"}
FORBIDDEN_PREFIX = ("ci_", "p_", "null_", "delta_", "macro_ap", "sign_", "per_pt_ap", "boot_")
FORBIDDEN_VALUES = {"positive", "negative", "zero", "양수", "음수", "양의", "음의",
                    "양의 방향", "음의 방향"}

# ※ 허용 실수 — 지시서 Z-7 문면 그대로. 이 외의 float 는 공개 파일에 실을 수 없다.
ALLOWED_FLOAT_KEYS = {
    # (a) 층 경계 정의값
    "bin_mid_boundary",
    # (b) 계측 시간(초·시·일)
    "wall_s", "total_wall_s", "total_wall_hours", "session_wall_s", "est_wall_s",
    "t_delta_once_s", "estimated_total_wall_s", "estimated_total_wall_hours",
    "estimated_total_wall_days", "abort_threshold_days", "measured_total_wall_hours",
    "bootstrap_pilot_s", "permutation_pilot_s", "elapsed_s",
    # (c) 계측 보정상수(시간 비율 — 무차원)
    "c_bootstrap", "c_permutation",
    # (d) load1 · (e) RSS
    "load1", "load1_entry", "rss_mb", "peak_rss_mb",
}
ALLOWED_FLOAT_VALUES = {0.0, 0.5, 1.0}      # 구간 경계 정의값


def assert_public_redacted(obj, path="$"):
    """공개 산출물에 Δ·AP·CI·p 계열 키·부호 값·미허용 실수가 부재함을 강제."""
    khits, vhits, fhits = [], [], []

    def walk(o, p, key=None):
        if isinstance(o, dict):
            for k, v in o.items():
                ks = str(k)
                if ks in FORBIDDEN_EXACT or ks.startswith(FORBIDDEN_PREFIX):
                    khits.append(f"{p}.{ks}")
                if ks.startswith("forbidden_") or ks.startswith("allowed_float"):
                    continue          # 규칙 **선언** 자체는 데이터가 아니다
                walk(v, f"{p}.{ks}", ks)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{p}[{i}]", key)
        elif isinstance(o, bool):
            return
        elif isinstance(o, float):
            if key not in ALLOWED_FLOAT_KEYS and o not in ALLOWED_FLOAT_VALUES:
                fhits.append(f"{p}")
        elif isinstance(o, str) and o.strip().lower() in FORBIDDEN_VALUES:
            vhits.append(p)

    walk(obj, path)
    assert not khits, f"[방어 FAIL] 봉인 계열 키 검출: {khits[:10]}"
    assert not vhits, f"[방어 FAIL] 부호 라벨 값 검출: {vhits[:10]}"
    assert not fhits, f"[방어 FAIL] 허용목록 밖 실수 검출: {fhits[:10]}"
    return {"forbidden_exact_keys": sorted(FORBIDDEN_EXACT),
            "forbidden_key_prefixes": list(FORBIDDEN_PREFIX),
            "forbidden_values": sorted(FORBIDDEN_VALUES),
            "allowed_float_keys": sorted(ALLOWED_FLOAT_KEYS),
            "allowed_float_values": sorted(ALLOWED_FLOAT_VALUES),
            "allowed_float_rule": ("허용 실수 = 층 경계 정의값(0.5)·계측 시간·계측 보정상수·"
                                   "load1·RSS 뿐. 그 밖의 float 는 값 기준으로 차단된다 "
                                   "(키 이름이 아니라 **값**으로 판정)."),
            "key_hits": 0, "value_hits": 0, "float_hits": 0, "pass": True}


# ═══════════════════════════════════════════════════════════════════════════
# stage: verify
# ═══════════════════════════════════════════════════════════════════════════
def env_fingerprint(sha_obs):
    import scipy
    import sklearn
    return {"ts_kst": now_kst(), "python": sys.version.split()[0], "numpy": np.__version__,
            "scipy": scipy.__version__, "sklearn": sklearn.__version__, "pandas": pd.__version__,
            "machine": platform.machine(), "os": platform.platform(),
            "ladder_freeze_sha16": EXPECT_LADDER_FREEZE_SHA16,
            "sap_manifest_sha16": EXPECT_SAP_MANIFEST_SHA16, "inputs_sha256": sha_obs}


def stage_verify():
    logln("[verify] Z-1 게이트 + Z-3 입력 판정")
    checks = {"constants_ast": assert_constants_imported()}

    g0 = H.gate0_verify()
    assert g0["ladder_freeze_sha16"] == EXPECT_LADDER_FREEZE_SHA16
    assert g0["sap_manifest_sha16"] == EXPECT_SAP_MANIFEST_SHA16
    checks["G0"] = {k: v for k, v in g0.items() if not isinstance(v, dict)}

    frozen = {}
    for rel in ("v3_Multimodal/config/ladder_freeze.json",
                "v3_Multimodal/config/gin_seed_freeze.json",
                "v3_Multimodal/config/gin_inner_valid_freeze.json",
                "v3_Multimodal/config/gin_inner_valid_freeze.status.json",
                "v3_Multimodal/config/post_interim_freeze_v1_0.json",
                "v3_Multimodal/config/rf_tuned_freeze.json",
                "v3_Multimodal/config/holm7_latefusion_freeze.json",
                "v3_Multimodal/config/a5_mechanism_freeze.json",
                "experiments/sap/manifest.json"):
        frozen[rel] = sha256_file(os.path.join(ROOT, rel))[:16]
    checks["frozen_sha16"] = frozen

    guard = guard_snapshot()
    assert len(guard) == EXPECT_GUARD_N_FILES, f"sealed guard {len(guard)}종 != {EXPECT_GUARD_N_FILES}"
    n_open = count_open_sealed()
    assert n_open == 0, f"open_sealed {n_open}건 — 개봉 금지 위반"
    checks["sealed_guard_n_files"] = len(guard)
    checks["open_sealed_events"] = n_open
    checks["seed_isolation"] = H.seed_isolation()

    st = json.load(open(os.path.join(CFG, "post_interim_freeze_v1_0.status.json"), encoding="utf-8"))
    assert st["unblinding_performed"] is False, "unblinding_performed 가 false 가 아니다"
    assert st["a5_requery_executed"] is True, "a5_requery_executed 가 true 가 아니다(재조회 승인 소진 상태)"
    checks["status_flags"] = {"unblinding_performed": st["unblinding_performed"],
                              "a5_requery_executed": st["a5_requery_executed"],
                              "gin_start_still_blocked": st["gin_start_still_blocked"]}

    sha_obs = {}
    for rel, exp16 in EXPECT_SHA.items():
        p = os.path.join(ROOT, rel)
        assert os.path.exists(p), f"입력 부재: {rel}"
        got = sha256_file(p)
        assert got[:16] == exp16, f"입력 sha16 불일치 {rel}: 기대 {exp16} 실측 {got[:16]}"
        sha_obs[rel] = got
    a5man = json.load(open(os.path.join(ROOT, "experiments/provenance/a5_requery_manifest.json"),
                           encoding="utf-8"))
    assert a5man["label_join_performed"] is False
    checks["inputs_sha256"] = sha_obs
    checks["a5_cache_label_join_performed"] = a5man["label_join_performed"]

    d = H.load_common()
    dfh = pd.read_csv(F_STRATA_H)
    excl = set(H.excluded_no_target(dfh))
    est = sorted(set(int(c) for c in d["cid_order"]) - excl)
    assert len(est) == EXPECT_DENOM

    weights, pchembl_verdict = determine_pchembl_source(est)
    checks["pchembl_source"] = pchembl_verdict
    logln(f"[verify] pchembl 정본 = {pchembl_verdict['canonical_file']} "
          f"({pchembl_verdict['candidates'][pchembl_verdict['canonical_file']]['n_pairs_filled']}"
          f"/{EXPECT_PAIR_TOTAL})")

    a5_cat, a5_targets, a5_info = load_a5(est)
    checks["a5"] = a5_info
    logln(f"[verify] A5 — 943∩847={a5_info['intersection_943_and_847']} · "
          f"847 분해 {a5_info['decomposition_847']} · canonical UniProt "
          f"{a5_info['canonicalization']['n_unique_uniprot_before']}→"
          f"{a5_info['canonicalization']['n_unique_uniprot_after']}")

    cons = load_consensus(d)
    checks["consensus"] = {"shape": list(cons["M1b"].shape), "n_nan": 0, "n_inf": 0,
                           "cid_equals_master_X_order": True,
                           "arms": sorted(F_CONS), "y_shape": list(d["Ym"].shape)}

    env = env_fingerprint(sha_obs)
    dump_json(F_ENVFP, env)
    out = {"_scope": "공개 — 게이트 PASS/FAIL·개수·해시·판정 근거 뿐. Δ·AP·CI·p·부호 없음.",
           "ts_kst": now_kst(), "block": "Z (docs/81)", "Z1_Z3_checks": checks,
           "sealed_guard_start": guard, "all_pass": True}
    dump_json(F_GATES, out)
    logln(f"[verify] PASS — G0 · sealed guard {len(guard)}종 · open_sealed {n_open} · "
          f"AST 상수 재사용 {checks['constants_ast']['n_constants_checked']}종 · 입력 7종 sha 일치")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: strata
# ═══════════════════════════════════════════════════════════════════════════
def stage_strata():
    logln("[strata] Z-4 4축 fold-local 층 배정 + 회계 assert")
    d = H.load_common()
    dfh = pd.read_csv(F_STRATA_H)
    excl = set(H.excluded_no_target(dfh))
    est = sorted(set(int(c) for c in d["cid_order"]) - excl)
    weights, pchembl_verdict = determine_pchembl_source(est)
    a5_cat, a5_targets, a5_info = load_a5(est)

    df = assign_axes(d, weights, a5_cat, a5_targets)
    df.to_csv(F_ASSIGN, index=False)
    logln(f"[strata] {os.path.relpath(F_ASSIGN, ROOT)} — {len(df)}행 (1,092 × 3반복)")

    acct = assert_axes_accounting(df, excl)
    logln(f"[strata] 회계 assert PASS — 축별 {acct['per_axis']} · "
          f"{EXPECT_DENOM}+{len(excl)}={EXPECT_N_DRUGS} · 네 축 집합 동일")

    # A5 층 배정 ↔ A/B/C/D 분해 교차 확인 (종료검증 #9)
    a5_c_cids = {c for c in est if a5_cat.get(c) == "C"}
    for v in ("{0}", "{1}", "no_mechanism"):
        leak = set(stratum_members(df, "A5", v)) & a5_c_cids
        assert not leak, f"[중단] case C 약물이 A5 `{v}` 에 유입: {sorted(leak)[:5]}"
    ne = set(stratum_members(df, "A5", "not_estimable")) - excl
    assert ne == a5_c_cids, "not_estimable 층 == case C 집합이 아니다"
    a5_ab = {c for c in est if a5_cat.get(c) in ("A", "B")}
    assert set(stratum_members(df, "A5", "no_mechanism")) - excl == a5_ab, \
        "no_mechanism 층 == case A∪B 집합이 아니다"

    units = estimation_units(df, excl)
    axes_out = {}
    for axis, values in AXES_BINS.items():
        items = {}
        for v in values:
            cids = [c for c in stratum_members(df, axis, v) if c not in excl]
            if not cids:
                items[v] = {"n_drugs": 0, "n_scaffold_clusters": 0,
                            "n_pt_meeting_positive_support": 0, "inference_mode": "empty",
                            "estimable": False}
                continue
            stt = support_stats(cids, d)
            items[v] = {**stt, "inference_mode": inference_label(stt), "estimable": True}
        cids = [c for c in unstable_members(df, axis) if c not in excl]
        if cids:
            stt = support_stats(cids, d)
            items["unstable_stratum"] = {**stt, "inference_mode": inference_label(stt),
                                         "estimable": True}
        else:
            items["unstable_stratum"] = {"n_drugs": 0, "n_scaffold_clusters": 0,
                                         "n_pt_meeting_positive_support": 0,
                                         "inference_mode": "empty", "estimable": False}
        axes_out[axis] = items

    summary = {
        "_scope": ("공개 — 층 배정·표본수·클러스터수·formal/descriptive 라벨 뿐. "
                   "층별 macro AP·Δ·CI·p 는 `_sealed/`(본 파일에 없음)."),
        "ts_kst": now_kst(), "block": "Z (docs/81)",
        "axis_labels": AXIS_LABEL,
        "axis_bins_frozen": AXES_BINS,
        "bin_rule": ("A3·A4 = `{0}` p==0 · `(0,0.5)` 0<p<0.5 · `[0.5,1)` 0.5<=p<1 · `{1}` p==1. "
                     "0·1 은 부동소수 비교가 아니라 **집합 판정**으로 확정한다."),
        "bin_mid_boundary": BIN_MID_BOUNDARY,
        "a4_missing_rule": ("결측 pair 는 분자·분모 **양쪽에서 제외**. 약물의 모든 pair 가 결측이면 "
                            "`no_evidence`(동결 문면)."),
        "a6_rule": "dominant = pchembl_median 최대 · 동점 시 UniProt 사전순 최소",
        "a5_boundary_amendment": a5_info,
        "pchembl_source": pchembl_verdict,
        "min_support": sap_unseen.MIN_SUPPORT,
        "eligible_pt": "None (370 PT 전열 · 층 내부 재선정 금지)",
        "excluded_no_target_drugs": len(excl),
        "denominator_estimated": EXPECT_DENOM,
        "accounting": acct,
        "axes": axes_out,
        "n_units": len(units),
        "unstable_note": ("3반복에서 층이 일치하는 약물만 primary 층화 대상. 불일치 약물은 제외가 "
                          "아니라 `unstable_stratum` 으로 분리 집계·별도 보고(H-0-1 계승)."),
        "boundary_adjustment": "층별 표본수를 보고 구간을 조정하지 않았다(동결 구간 그대로).",
    }
    dump_json(F_ASSIGN_SUM, summary)
    for axis in AXES_BINS:
        logln(f"[strata] {axis}: " + " · ".join(
            f"{k} n={v['n_drugs']}" for k, v in axes_out[axis].items() if v["n_drugs"]))
    logln(f"[strata] 추정 층 {len(units)}개 × 대비 2종 = {len(units) * len(CONTRASTS)} unit-run")
    return summary


# ═══════════════════════════════════════════════════════════════════════════
# stage: pilot  (Z-5 — 층별 Δ **직접 실측**. 선형 가정 금지.)
# ═══════════════════════════════════════════════════════════════════════════
def stage_pilot():
    logln(f"[pilot] Z-5 계측 — B={B_PILOT}. 파일럿 통계 산출은 전량 폐기(봉인 저장 0).")
    d = H.load_common()
    dfh = pd.read_csv(F_STRATA_H)
    excl = set(H.excluded_no_target(dfh))
    df = pd.read_csv(F_ASSIGN)
    cons = load_consensus(d)
    units = estimation_units(df, excl)

    # (a) 층 × 대비마다 Δ **1회 직접 실측** (블록 L 방식 — 약물수 선형 가정 금지)
    per_unit = []
    for u in units:
        idx = H.row_index(d, u["cids"])
        y_s, sg_s = d["Ym"][idx], d["scaffold"][idx]
        for ct in CONTRASTS:
            t0 = time.perf_counter()
            a1 = sap_metrics.macro_ap(y_s, cons[ct["base"]][idx], ELIGIBLE_PT)
            a2 = sap_metrics.macro_ap(y_s, cons[ct["comp"]][idx], ELIGIBLE_PT)
            t_ap = time.perf_counter() - t0
            n_pt = int(a1["n_eval"])
            assert a1["n_eval"] == a2["n_eval"], "arm 간 정의 PT 수 불일치(동일 y 이므로 불가능)"
            del a1, a2                                  # 값 폐기 — 시간·개수만 유지
            per_unit.append({"axis": u["axis"], "stratum": u["stratum"], "kind": u["kind"],
                             "contrast": ct["id"], "n_drugs": len(u["cids"]),
                             "n_clusters": int(len(set(sg_s.tolist()))),
                             "n_pt_with_positive": n_pt, "t_delta_once_s": t_ap})

    # (b) 최대 표본 층 × 대비 C1 에서 B=100 → replicate/jackknife 비례상수 보정
    biggest = max(units, key=lambda u: len(u["cids"]))
    pu = next(p for p in per_unit if p["axis"] == biggest["axis"]
              and p["stratum"] == biggest["stratum"] and p["contrast"] == "C1")
    logln(f"[pilot] 보정 대상 = {biggest['axis']}/{biggest['stratum']} (n_drugs={pu['n_drugs']})")
    res = run_unit(biggest["cids"], d, cons["M1b"], cons["M2b"], B_PILOT,
                   SEED_BOOTSTRAP, SEED_SIGNFLIP)
    t = res["timing_s"]
    n_clu = int(res["bootstrap"]["n_clusters"])
    t_delta_p = pu["t_delta_once_s"]
    del res                                             # 파일럿 산출 폐기(봉인 저장 금지)

    c_boot = t["bootstrap"] / ((B_PILOT + n_clu) * t_delta_p)
    c_flip = t["signflip"] / (B_PILOT * t_delta_p)

    est, total = [], 0.0
    for p in per_unit:
        s = (c_boot * (B_MAIN + p["n_clusters"]) + c_flip * B_MAIN) * p["t_delta_once_s"]
        est.append({**p, "est_wall_s": s})
        total += s

    out = {
        "_scope": "공개 — 시간·표본수 뿐. 파일럿 통계 산출은 전량 폐기(봉인 저장 없음).",
        "ts_kst": now_kst(), "block": "Z (docs/81)",
        "B_pilot": B_PILOT, "B_main": B_MAIN,
        "measurement_rule": (
            "층 wall ≈ [c_bootstrap × (B + n_clusters) + c_permutation × B] × t_delta_once(층,대비). "
            "**t_delta_once 는 층 × 대비마다 직접 실측**한다 — 블록 H 는 이를 약물수 선형으로 "
            "**가정**해 1.74배 과소추정했고, 블록 L 이 직접 실측으로 0.96배로 맞췄다(docs/57 §4). "
            "본 블록은 블록 L 방식을 따른다. 선형 가정 코드는 존재하지 않는다."),
        "linear_assumption_used": False,
        "pilot_unit": {"axis": biggest["axis"], "stratum": biggest["stratum"], "contrast": "C1",
                       "n_drugs": pu["n_drugs"], "n_clusters": n_clu,
                       "n_pt_with_positive": pu["n_pt_with_positive"]},
        "pilot_timing_s": {"t_delta_once_s": t_delta_p, "bootstrap_pilot_s": t["bootstrap"],
                           "permutation_pilot_s": t["signflip"]},
        "calibration_constants": {"c_bootstrap": c_boot, "c_permutation": c_flip},
        "n_units": len(units), "n_unit_runs": len(per_unit),
        "estimate_per_unit_run": est,
        "estimated_total_wall_s": total,
        "estimated_total_wall_hours": total / 3600.0,
        "estimated_total_wall_days": total / 86400.0,
        "abort_threshold_days": WALL_ABORT_DAYS,
        "exceeds_threshold": bool(total / 86400.0 > WALL_ABORT_DAYS),
        "pilot_artifacts_discarded": True,
    }
    assert_public_redacted(out, path="pilot_timing.json")
    dump_json(F_PILOT, out)
    logln(f"[pilot] 전 층×대비({len(per_unit)}) × B={B_MAIN} 총 추정 wall = {total / 3600:.2f}h "
          f"({total / 86400:.3f}일) · {WALL_ABORT_DAYS}일 초과 = {out['exceeds_threshold']}")
    assert not out["exceeds_threshold"], \
        f"[중단] 추정 총 wall {total / 86400:.2f}일 > {WALL_ABORT_DAYS}일 — 실행하지 않는다."
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: estimate  (Z-6 — 산출 전량 `_sealed/`) · (축,층,대비) 체크포인트 재개
# ═══════════════════════════════════════════════════════════════════════════
def load_checkpoint():
    done = {}
    if not os.path.exists(F_CKPT):
        return done
    with open(F_CKPT, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            rec = json.loads(ln)
            assert rec["key"] not in done, f"체크포인트 중복 키: {rec['key']}"
            done[rec["key"]] = rec
    return done


def append_checkpoint(rec):
    os.makedirs(SEALED_DIR, exist_ok=True)
    with open(F_CKPT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=H.native) + "\n")
        f.flush()
        os.fsync(f.fileno())


def stage_estimate():
    logln(f"[estimate] Z-6 본계산 — B={B_MAIN}, seed boot={SEED_BOOTSTRAP} "
          f"flip={SEED_SIGNFLIP}. 산출 전량 `_sealed/`.")
    d = H.load_common()
    dfh = pd.read_csv(F_STRATA_H)
    excl = set(H.excluded_no_target(dfh))
    df = pd.read_csv(F_ASSIGN)
    summ = json.load(open(F_ASSIGN_SUM, encoding="utf-8"))
    cons = load_consensus(d)
    units = estimation_units(df, excl)
    assert_axes_accounting(df, excl)

    if os.path.exists(F_ENVFP):
        prev = json.load(open(F_ENVFP, encoding="utf-8"))
        cur = env_fingerprint(prev["inputs_sha256"])
        for k in ("python", "numpy", "scipy", "sklearn", "pandas", "machine",
                  "ladder_freeze_sha16", "sap_manifest_sha16"):
            assert prev[k] == cur[k], f"세션 간 환경 불일치: {k}"

    done = load_checkpoint()
    if done:
        logln(f"[estimate] 체크포인트 재개 — 완주 {len(done)}/{len(units) * len(CONTRASTS)}")

    ordered = [f"{u['axis']}::{u['stratum']}::{ct['id']}" for u in units for ct in CONTRASTS]
    t_all = time.perf_counter()
    k = 0
    for u in units:
        src = summ["axes"][u["axis"]][u["stratum"]]
        for ct in CONTRASTS:
            k += 1
            key = f"{u['axis']}::{u['stratum']}::{ct['id']}"
            if key in done:
                logln(f"[estimate] {k}/{len(ordered)} {key} — 체크포인트 존재, SKIP")
                continue
            gate_b_exclusive(f"unit={key}:before")
            t0 = time.perf_counter()
            res = run_unit(u["cids"], d, cons[ct["base"]], cons[ct["comp"]],
                           B_MAIN, SEED_BOOTSTRAP, SEED_SIGNFLIP)
            wall = time.perf_counter() - t0
            b = res["bootstrap"]
            rec = {"key": key, "ts_kst": now_kst(),
                   "sealed": {"axis": u["axis"], "stratum": u["stratum"], "kind": u["kind"],
                              "contrast": ct["id"], "holm_family_id": ct["holm_family"],
                              "contrast_definition":
                                  f"macro AP({ct['comp']}) − macro AP({ct['base']})",
                              "n_drugs": len(u["cids"]), "cids": u["cids"], **res},
                   "public": {"axis": u["axis"], "axis_label": AXIS_LABEL[u["axis"]],
                              "stratum": u["stratum"], "kind": u["kind"],
                              "contrast": ct["id"], "holm_family_id": ct["holm_family"],
                              "n_drugs": len(u["cids"]),
                              "n_clusters": int(b["n_clusters"]),
                              "n_pt_meeting_positive_support":
                                  src["n_pt_meeting_positive_support"],
                              "inference_mode": src["inference_mode"],
                              "primary_ci_estimability": b["ci_primary"]["status"],
                              "bca_estimability": b["ci_bca"]["status"],
                              "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP,
                              "seed_signflip": SEED_SIGNFLIP, "wall_s": wall}}
            append_checkpoint(rec)
            done[key] = rec
            gate_b_exclusive(f"unit={key}:after")
            logln(f"[estimate] {k}/{len(ordered)} {key} n={len(u['cids'])} "
                  f"clusters={b['n_clusters']} primary_ci={b['ci_primary']['status']} "
                  f"wall={wall:.1f}s")
    session_wall = time.perf_counter() - t_all

    assert set(done) == set(ordered), f"완주 불일치, 미완: {sorted(set(ordered) - set(done))[:5]}"

    sealed = {"_warning": "SEALED — 성공판정(개봉) 단계 전 열람 금지.",
              "step": "등록 §11 세 번째 축 — A3·A4·A5·A6 unseen-target proportion 층화(블록 Z)",
              "ts_kst": now_kst(),
              "contrasts": {c["id"]: {"definition": f"macro AP({c['comp']}) − macro AP({c['base']})",
                                      "holm_family_id": c["holm_family"]} for c in CONTRASTS},
              "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
              "unit": BOOT_UNIT, "eligible_pt": "None(370 PT 전열)",
              "multiplicity": "미적용 — Holm/BH 는 성공판정 단계 일괄(본 단계 raw 산출만)",
              "inputs_sha256": {k2: sha256_file(v) for k2, v in F_CONS.items()},
              "strata": {kk: done[kk]["sealed"] for kk in ordered}}

    store = sap_redaction.SealedStore(RUN_DIR)
    sealed_path = os.path.join(SEALED_DIR, "axes_result.json")
    if os.path.exists(sealed_path):
        # 본 스테이지 재진입(= 공개요약 재구성) — 봉인 바이트를 **건드리지 않는다**.
        # 내용은 `_sealed/checkpoint.jsonl` 전건이 결정하고 위 완주 assert 가 동일성을 보장한다.
        # 재작성하면 ts_kst 만 달라져 sha 가 바뀌므로 재작성도, 판독도 하지 않는다.
        logln("[estimate] 봉인 결과 파일 기존재 — 재작성 0 · 판독 0(공개요약만 재구성)")
        sealed_rewritten = False
    else:
        sealed_path = store.write_sealed("axes_result.json", json.loads(
            json.dumps(sealed, ensure_ascii=False, default=H.native)))
        sealed_rewritten = True
    sealed_sha = sha256_file(sealed_path)

    guard_end = guard_snapshot()
    guard_start = json.load(open(F_GATES, encoding="utf-8"))["sealed_guard_start"]
    assert guard_end == guard_start, "sealed guard 변경 감지 — 기존 sealed 산출물이 수정되었다"
    n_open = count_open_sealed()
    assert n_open == 0, f"open_sealed {n_open}건"

    public_units = [done[kk]["public"] for kk in ordered]
    total_wall = sum(p["wall_s"] for p in public_units)
    not_est = [{"key": kk, "axis": done[kk]["public"]["axis"],
                "stratum": done[kk]["public"]["stratum"],
                "contrast": done[kk]["public"]["contrast"],
                "primary_ci_estimability": done[kk]["public"]["primary_ci_estimability"],
                "bca_estimability": done[kk]["public"]["bca_estimability"],
                "n_drugs": done[kk]["public"]["n_drugs"],
                "n_clusters": done[kk]["public"]["n_clusters"],
                "reason": ("BCa 산출 불능 — percentile 자동대체 **금지**(SAP A1 동결 · 블록 L 선례). "
                           "estimability 부재이지 효과 부재가 아니다.")}
               for kk in ordered
               # ★ 판정 필드는 `ci_primary.status`(∈ estimable/not_estimable) 다.
               #   `ci_bca.status` 의 성공 토큰은 `"estimable"` 이 아니라 **`"bca"`** 이므로
               #   그 필드로 `!= "estimable"` 을 걸면 전건이 거짓 not_estimable 이 된다
               #   (`sap/bootstrap.py:197-209`·`_bca_ci` 반환 규약).
               if done[kk]["public"]["primary_ci_estimability"] != "estimable"]

    pilot = json.load(open(F_PILOT, encoding="utf-8"))
    pub = {
        "_scope": ("공개 — 축·층 이름·층별 표본수·클러스터수·formal/descriptive 라벨·회계 assert·"
                   "판정 근거·B·seed·소요시간·해시·게이트 PASS/FAIL 뿐. **층별 macro AP·Δ·CI·"
                   "sign-flip p 는 물론 Δ 의 부호도 본 파일에 없다**(전량 `_sealed/`)."),
        "ts_kst": now_kst(), "block": "Z (docs/81)",
        "axis_labels": AXIS_LABEL,
        "axis_bins_frozen": AXES_BINS,
        "bin_mid_boundary": BIN_MID_BOUNDARY,
        "definition_sources": {
            "A3_A4_A6": "v3_Multimodal/config/post_interim_freeze_v1_0.json axes_a3_a4_a6",
            "A5": "v3_Multimodal/config/a5_mechanism_freeze.json",
            "A5_boundary": "v3_Multimodal/config/a5_boundary_amendment.json",
        },
        "a5_boundary_amendment": summ["a5_boundary_amendment"],
        "pchembl_source": summ["pchembl_source"],
        "accounting": summ["accounting"],
        "axes": summ["axes"],
        "excluded_no_target_drugs": summ["excluded_no_target_drugs"],
        "denominator_estimated": EXPECT_DENOM,
        "contrast_labels": {c["id"]: {"arms": f"{c['comp']} vs {c['base']}",
                                      "holm_family_id": c["holm_family"]} for c in CONTRASTS},
        "n_units": len(units), "n_unit_runs": len(public_units),
        "units": public_units,
        "n_units_formal": sum(1 for p in public_units if p["inference_mode"] == "formal"),
        "n_units_descriptive": sum(1 for p in public_units if p["inference_mode"] == "descriptive"),
        "not_estimable_units": not_est,
        "n_not_estimable_units": len(not_est),
        "not_estimable_semantics": ("`not_estimable` = estimability 부재이지 효과 부재가 아니다"
                                    "(교수님 2026-08-03 결정 취지). 대리지표 대체 0."),
        "estimability_rule": (
            "판정 필드 = `ci_primary.status` ∈ {`estimable`,`not_estimable`} 이며 SAP A1 동결에 따라 "
            "**BCa 가 성공했을 때만** `estimable` 이다(`sap/bootstrap.py:201-209`). 참고로 "
            "`ci_bca.status` 의 성공 토큰은 `estimable` 이 아니라 **`bca`** 이고 실패는 "
            "`bca_failed_*` 다 — 이 두 필드를 혼동하면 전건이 거짓 `not_estimable` 이 된다."),
        "sealed_result_rewritten_this_run": sealed_rewritten,
        "bca_fallback_rule": "BCa 실패 시 percentile 대체 **금지** — not_estimable 그대로 봉인",
        "percentile_auto_substitutions": 0,
        "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
        "bootstrap_unit": BOOT_UNIT, "primary_ci_method": sap_bootstrap.PRIMARY_CI_METHOD,
        "seed_reuse_note": ("블록 H/L 과 **동일 seed·B·단위·CI 방법 재사용**(새 추첨 0) — "
                            "`stratification_run.py` 에서 import 재사용하며 상수를 다시 쓰지 않는다."),
        "constants_ast_check": assert_constants_imported(),
        "timing_estimate_vs_measured": {
            "estimated_total_wall_hours": pilot["estimated_total_wall_hours"],
            "measured_total_wall_hours": total_wall / 3600.0,
            "measurement_rule": pilot["measurement_rule"],
            "linear_assumption_used": False,
        },
        "total_wall_s": total_wall, "total_wall_hours": total_wall / 3600.0,
        "session_wall_s": session_wall,
        "sealed_result_sha256": sealed_sha,
        "sealed_result_path": os.path.relpath(sealed_path, ROOT),
        "sealed_guard_n_files_end": len(guard_end),
        "sealed_guard_unchanged": True,
        "ladder_freeze_sha16": EXPECT_LADDER_FREEZE_SHA16,
        "sap_manifest_sha16": EXPECT_SAP_MANIFEST_SHA16,
        "decision_functions_called": [],
        "multiplicity_applied": False,
        "open_sealed_calls": n_open,
        "emit_sign_called": False,
        "models_trained": 0, "new_oof_generated": 0, "network_calls": 0, "git_commit": False,
        "recomputed_nothing": ["consensus OOF(M1b·M2b·P-ID)", "a5_mechanism_targets.csv",
                               "05b_affinity_values.csv", "strata_assignment.csv(블록 H)"],
        "redaction": "공개 파일에 층별 macro AP·Δ·CI·sign-flip p·부트스트랩 분포·**Δ 부호** 없음",
        "all_pass": True,
    }
    pub["public_redaction_assert"] = assert_public_redacted(pub, path="axes_public.json")
    dump_json(F_PUBLIC, pub)
    assert_public_redacted(json.load(open(F_PUBLIC, encoding="utf-8")), path="axes_public.json")

    logln(f"[estimate] 완료 — unit-run {len(public_units)} · 총 계산 wall {total_wall / 3600:.2f}h · "
          f"not_estimable {len(not_est)} · sealed sha16 {sealed_sha[:16]} · guard {len(guard_end)}종 불변")
    return pub


# ═══════════════════════════════════════════════════════════════════════════
# stage: recheck — 공개 산출물 교차 스캔 (재계산 0)
# ═══════════════════════════════════════════════════════════════════════════
def stage_recheck():
    logln("[recheck] 공개 산출물 교차 redaction 스캔 + 무결성 재확인 (재계산 0)")
    scanned = {}
    for f in (F_GATES, F_ASSIGN_SUM, F_PILOT, F_PUBLIC):
        assert os.path.exists(f), f"공개 산출물 부재: {os.path.relpath(f, ROOT)}"
        obj = json.load(open(f, encoding="utf-8"))
        assert_public_redacted(obj, path=os.path.basename(f))
        scanned[os.path.basename(f)] = {"sha256": sha256_file(f), "hits": 0}

    pub = json.load(open(F_PUBLIC, encoding="utf-8"))
    sealed_path = os.path.join(ROOT, pub["sealed_result_path"])
    assert sha256_file(sealed_path) == pub["sealed_result_sha256"], "봉인 sha256 불일치"
    guard_end = guard_snapshot()
    guard_start = json.load(open(F_GATES, encoding="utf-8"))["sealed_guard_start"]
    assert guard_end == guard_start, "sealed guard 변경 감지"
    n_open = count_open_sealed()
    assert n_open == 0
    n_ckpt = sum(1 for ln in open(F_CKPT, encoding="utf-8") if ln.strip())
    assert n_ckpt == pub["n_unit_runs"], f"체크포인트 {n_ckpt}행 != {pub['n_unit_runs']}"

    out = {"_scope": "공개 — 교차검사 PASS/FAIL·해시·개수 뿐.",
           "ts_kst": now_kst(), "block": "Z (docs/81) — recheck",
           "files_scanned": scanned,
           "forbidden_exact_keys": sorted(FORBIDDEN_EXACT),
           "forbidden_key_prefixes": list(FORBIDDEN_PREFIX),
           "forbidden_values": sorted(FORBIDDEN_VALUES),
           "allowed_float_keys": sorted(ALLOWED_FLOAT_KEYS),
           "allowed_float_values": sorted(ALLOWED_FLOAT_VALUES),
           "allowed_float_rule": ("허용 실수 = 층 경계 정의값(0.5)·계측 시간·계측 보정상수·load1·"
                                  "RSS 뿐. 그 밖의 float 는 **값 기준**으로 차단."),
           "total_hits": 0,
           "sealed_result_sha256_matches_public_record": True,
           "sealed_guard_n_files": len(guard_end), "sealed_guard_unchanged": True,
           "open_sealed_calls": n_open, "checkpoint_rows": n_ckpt,
           "recomputed_statistics": 0, "sealed_artifacts_modified": 0,
           "all_pass": True}
    assert_public_redacted(out, path="redaction_scan_public.json")
    dump_json(F_SCAN, out)
    assert_public_redacted(json.load(open(F_SCAN, encoding="utf-8")),
                           path="redaction_scan_public.json")
    logln(f"[recheck] PASS — 공개 4파일 검출 0 · 봉인 sha 일치 · guard {len(guard_end)}종 불변 · "
          f"open_sealed {n_open} · 체크포인트 {n_ckpt}행")
    return out


# ═══════════════════════════════════════════════════════════════════════════
STAGES = {"verify": stage_verify, "strata": stage_strata, "pilot": stage_pilot,
          "estimate": stage_estimate, "recheck": stage_recheck}
ORDER = ["verify", "strata", "pilot", "estimate", "recheck"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=list(STAGES) + ["all"])
    a = ap.parse_args()
    os.makedirs(RUN_DIR, exist_ok=True)
    stages = ORDER if a.stage == "all" else [a.stage]
    out = None
    with ComputeLock(script="axes_stratification_run.py", role="runner"):
        gate_a_load(f"stage={a.stage}")
        for s in stages:
            gate_b_exclusive(f"stage={s}:before")
            out = STAGES[s]()
            gate_b_exclusive(f"stage={s}:after")
    return out


if __name__ == "__main__":
    main()
