#!/usr/bin/env python3
"""strata_accounting_check.py — 블록 K: 층 회계 정합 재현 + assertion 고정 + §13-6 커버리지 감사.

성격
----
**판독 전용.** 모델학습 0 · permutation 0 · bootstrap 0 · sign-flip 0 · 네트워크 0.
기존 산출물(`strata_assignment.csv` · `strata_summary.json` · `stratification_public.json` ·
`_sealed/*`)은 **읽기만** 하고 신규 파일만 쓴다. 개봉(`open_sealed`) 없음 ·
성공판정 함수 호출 없음 · 다중성 보정 없음 · 층별 AP·Δ·CI·p 산출 없음.

단계
  K-2  회계 재현 + 하드 assert (축별 Σ stable + unstable == 847, 847 + 245 == 1,092)
  K-3  unstable·경계 사례 사유 분류 → unstable_cases.csv
  K-4  공개 요약 보강(신규) → strata_accounting_public.json
  K-5  §13-6 커버리지 감사(계산 없음 · 명세만) → coverage_audit.json

실행: .venv/bin/python3 v3_Multimodal/src/strata_accounting_check.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

for _k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_k, "1")

import numpy as np                                                      # noqa: E402
import pandas as pd                                                     # noqa: E402

import stratification_run as sr                                         # noqa: E402
from compute_lock import ComputeLock, gate_a_load                       # noqa: E402
from sap import unseen_target as sap_unseen                             # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
# 회계 상수 — 결과 무참조(표본수 회계 전용)
# ═══════════════════════════════════════════════════════════════════════════
EXPECT_N_ROWS = 3276               # 1,092 약물 × 3반복
EXPECT_N_DRUGS = 1092
EXPECT_N_NO_TARGET = 245           # INFERENCE_MODE 상 excluded
EXPECT_DENOM = 847                 # 1,092 − 245 = 층화 추정 모수
AXES = ("drug_class", "seq_stratum", "struct_bin")

# 축별 위상 라벨 (교수님 2026-08-03 결정 · `docs/53` §1·§4)
AXIS_ROLE = {
    "struct_bin": {
        "role": "confirmatory",
        "basis": "docs/53 §1 — 사전등록된 '연속 표적 유사도' 축은 확증 분석으로 유지",
    },
    "seq_stratum": {
        "role": "confirmatory",
        "basis": "docs/53 §1 — 사전등록된 '연속 표적 유사도' 축은 확증 분석으로 유지",
    },
    "drug_class": {
        "role": "data_characteristic",
        "basis": ("docs/53 §1 — all-seen/mixed/all-unseen 세 집단의 **구조적 분포 자체는 "
                  "데이터 특성으로 보고**하되, **재분할 결과 분석은 exploratory**."),
        "resplit_result_analysis": "exploratory",
    },
}

RUN_DIR = os.path.join(ROOT, "experiments", "runs", "v3_stratification")
F_STRATA = os.path.join(RUN_DIR, "strata_assignment.csv")
F_STRATA_SUM = os.path.join(RUN_DIR, "strata_summary.json")
F_PUBLIC = os.path.join(RUN_DIR, "stratification_public.json")
F_BOUNDS = os.path.join(RUN_DIR, "struct_bounds.json")
RUN_LOG = os.path.join(RUN_DIR, "run.log")

OUT_CASES = os.path.join(RUN_DIR, "unstable_cases.csv")
OUT_CHECK = os.path.join(RUN_DIR, "accounting_check.json")
OUT_PUBLIC = os.path.join(RUN_DIR, "strata_accounting_public.json")
OUT_COVERAGE = os.path.join(RUN_DIR, "coverage_audit.json")

# 공개 파일 방어 assert — 결과 계열 키 부재 강제
FORBIDDEN_KEY_PREFIXES = ("macro_ap", "delta", "sign", "ci_", "p_", "boot_")


def logln(m):
    line = f"{sr.now_kst()} | [K] {m}"
    print(line, flush=True)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def guard_snapshot_all():
    """`experiments/runs/**/_sealed/` 전 파일의 sha256 — 값은 열지 않고 지문만."""
    snap = {}
    base = os.path.join(ROOT, "experiments", "runs")
    for dirpath, dirnames, filenames in os.walk(base):
        if "_sealed" not in os.path.relpath(dirpath, base).split(os.sep):
            continue                                # `_sealed/` 하위 트리 전체 포함
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            if os.path.isfile(p) and fn != "access.log":
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                snap[os.path.relpath(p, ROOT)] = h.hexdigest()
    return snap


def assert_no_result_keys(obj, path="$"):
    """공개 산출물에 결과 계열 키(AP·Δ·부호·CI·p·부트스트랩)가 없음을 강제."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(kl.startswith(pfx) for pfx in FORBIDDEN_KEY_PREFIXES):
                hits.append(f"{path}.{k}")
            hits += assert_no_result_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += assert_no_result_keys(v, f"{path}[{i}]")
    if path == "$":
        assert not hits, f"[방어 assert FAIL] 결과 계열 키 검출: {hits}"
        return {"forbidden_prefixes": list(FORBIDDEN_KEY_PREFIXES), "hits": [], "pass": True}
    return hits


# ═══════════════════════════════════════════════════════════════════════════
# K-2-a. 층 배정 독립 재현 (동결 연산자 그대로 · 기존 CSV 와 대조)
# ═══════════════════════════════════════════════════════════════════════════
def reproduce_assignment():
    """`strata_assignment.csv` 를 동결 입력·동결 연산자로 재계산하고 대조한다.

    부수 산출 `s_drug` = `drug_sequence_stratum` 이 층 결정에 실제로 쓴 drug-level
    identity 값(설계 진단치). 경계까지의 거리 계산(K-3)에 필요하다."""
    d = sr.load_common()
    bnd = json.load(open(F_BOUNDS, encoding="utf-8"))["boundaries"]
    idmap = sr.load_identity()
    maxtan = np.load(os.path.join(RUN_DIR, "_max_tanimoto.npy"))
    cid_order = d["cid_order"]

    rows = []
    for r in (1, 2, 3):
        fold_arr = d["folds"][r]
        T_train = sr.train_targets_by_fold(cid_order, d["cid2targets"], fold_arr)
        for i, c in enumerate(cid_order):
            f = int(fold_arr[i])
            T_d = d["cid2targets"].get(int(c), set())
            Ttr = T_train[f]
            drug_class = sap_unseen.classify_drug(T_d, Ttr)
            seqid_max, n_obs = {}, 0
            for t in T_d:
                if t in Ttr:
                    continue
                cand = [idmap[t][u] for u in Ttr if t in idmap and u in idmap[t]]
                if cand:
                    seqid_max[t] = max(cand)
                    n_obs += 1
            seq_stratum = sap_unseen.drug_sequence_stratum(T_d, Ttr, seqid_max)
            if len(T_d) == 0:
                s_drug = float("nan")
            elif len(T_d & Ttr) > 0:
                s_drug = 100.0                      # exact-seen → 정의상 s_drug=100
            else:
                s_drug = max(float(seqid_max.get(t, 0.0)) for t in T_d)
            rows.append({"cid": int(c), "rep": r, "fold": f,
                         "drug_class": drug_class, "seq_stratum": seq_stratum,
                         "n_targets": len(T_d), "n_unseen_targets": len(T_d - Ttr),
                         "n_seqid_observed": n_obs,
                         "struct_bin": sr.struct_bin_of(float(maxtan[i, r - 1]), bnd),
                         "max_tanimoto": float(maxtan[i, r - 1]),
                         "s_drug": s_drug})
    rep = pd.DataFrame(rows)

    df = pd.read_csv(F_STRATA)
    key = ["cid", "rep"]
    a = df.sort_values(key).reset_index(drop=True)
    b = rep.sort_values(key).reset_index(drop=True)
    mismatch = {}
    for col in ("fold", "drug_class", "seq_stratum", "n_targets", "n_unseen_targets",
                "n_seqid_observed", "struct_bin"):
        n_bad = int((a[col].values != b[col].values).sum())
        if n_bad:
            mismatch[col] = n_bad
    n_tan_bad = int((~np.isclose(a["max_tanimoto"].values, b["max_tanimoto"].values,
                                 rtol=0, atol=1e-12)).sum())
    if n_tan_bad:
        mismatch["max_tanimoto"] = n_tan_bad
    assert not mismatch, f"[재현 FAIL] 기존 strata_assignment.csv 와 불일치: {mismatch}"
    logln(f"독립 재현 PASS — {len(rep)}행 전 컬럼 일치(불일치 0)")
    return b, {"n_rows": len(rep), "columns_checked": 8, "mismatch": {}, "pass": True}


# ═══════════════════════════════════════════════════════════════════════════
# K-2-b. 회계 재현 + 하드 assert
# ═══════════════════════════════════════════════════════════════════════════
def stability_table(df, axis):
    """축별 3반복 층 일치 여부 → (pivot, stable bool Series)."""
    piv = df.pivot(index="cid", columns="rep", values=axis)
    return piv, (piv.nunique(axis=1) == 1)


def accounting(df):
    """K-2 회계 — 축별 stable 층 표본수 · unstable · 모수 847 · 전체 1,092."""
    excl = sorted(df.loc[df["drug_class"] == "no-target", "cid"].unique().tolist())
    n_total = int(df["cid"].nunique())

    # 형식 assert (K-2-1)
    assert len(df) == EXPECT_N_ROWS, f"행수 {len(df)} != {EXPECT_N_ROWS}"
    assert n_total == EXPECT_N_DRUGS, f"고유 cid {n_total} != {EXPECT_N_DRUGS}"
    assert sorted(df["rep"].unique().tolist()) == [1, 2, 3], "반복 집합 != {1,2,3}"
    assert not df.duplicated(["cid", "rep"]).any(), "(cid, rep) 중복"
    assert df.groupby("rep").size().eq(EXPECT_N_DRUGS).all(), "반복별 행수 != 1,092"
    assert len(excl) == EXPECT_N_NO_TARGET, f"no-target {len(excl)} != {EXPECT_N_NO_TARGET}"

    exclset = set(excl)
    out, stable_flags, est_sets = {}, {}, {}
    for axis in AXES:
        piv, same = stability_table(df, axis)
        stable_flags[axis] = same
        strata = {}
        for v in sorted(piv[1][same].unique().tolist()):
            cids = [c for c in piv.index[same & (piv[1] == v)] if c not in exclset]
            if cids:
                strata[v] = len(cids)
        unstable_cids = [c for c in piv.index[~same] if c not in exclset]
        n_stable = sum(strata.values())
        n_unstable = len(unstable_cids)
        denom = n_stable + n_unstable

        # ── 하드 회계 assert (K-2-3 핵심) ─────────────────────────────────
        assert denom == EXPECT_DENOM, \
            f"[회계 FAIL] {axis}: Σ stable({n_stable}) + unstable({n_unstable}) = {denom} != {EXPECT_DENOM}"
        assert denom + len(excl) == n_total == EXPECT_N_DRUGS, \
            f"[회계 FAIL] {axis}: {denom} + no-target {len(excl)} != {EXPECT_N_DRUGS}"

        est_sets[axis] = set(int(c) for c in unstable_cids) | {
            int(c) for v in strata for c in piv.index[same & (piv[1] == v)] if c not in exclset}
        out[axis] = {"strata_stable": strata, "n_stable_total": n_stable,
                     "unstable_stratum": n_unstable, "denominator_estimated": denom,
                     "sum_check": True}

    # 축 간 모수 동일성 (K-2-3 후단)
    denoms = {a: out[a]["denominator_estimated"] for a in AXES}
    assert len(set(denoms.values())) == 1, f"[회계 FAIL] 축별 모수 불일치: {denoms}"
    base = est_sets[AXES[0]]
    for a in AXES[1:]:
        assert est_sets[a] == base, f"[회계 FAIL] {a} 추정 대상 약물 집합이 {AXES[0]} 과 다름"

    # 파일에 저장된 stable_* 컬럼과 재계산 결과 일치 (K-2-2)
    stored_df = pd.read_csv(F_STRATA)
    col_mismatch = {}
    for axis in AXES:
        stored = stored_df.drop_duplicates("cid").set_index("cid")[f"stable_{axis}"].astype(bool)
        recomputed = stable_flags[axis].reindex(stored.index).astype(bool)
        n_bad = int((stored.values != recomputed.values).sum())
        if n_bad:
            col_mismatch[axis] = n_bad
    assert not col_mismatch, f"[stable 컬럼 FAIL] {col_mismatch}"

    return {"n_total_drugs": n_total, "n_excluded_no_target": len(excl),
            "denominator_estimated": EXPECT_DENOM, "axes": out,
            "axis_denominators_equal": True,
            "estimation_drug_set_identical_across_axes": True,
            "stable_column_matches_recomputation": True,
            "excluded_no_target_cids": excl}, stable_flags, exclset


def crosscheck_public(acc):
    """K-2-4 — `stratification_public.json` units 의 n_drugs 합계 대조."""
    pub = json.load(open(F_PUBLIC, encoding="utf-8"))
    per_axis = {}
    for u in pub["units"]:
        per_axis.setdefault(u["axis"], 0)
        per_axis[u["axis"]] += int(u["n_drugs"])
    for axis, s in per_axis.items():
        assert s == EXPECT_DENOM, f"[public 대조 FAIL] {axis} units 합 {s} != {EXPECT_DENOM}"
    assert int(pub["excluded_no_target_drugs"]) == EXPECT_N_NO_TARGET
    unst = {k: int(v) for k, v in pub["unstable_stratum_counts"].items()}
    for axis in AXES:
        assert unst[axis] == acc["axes"][axis]["unstable_stratum"], \
            f"[public 대조 FAIL] {axis} unstable {unst[axis]} != {acc['axes'][axis]['unstable_stratum']}"
    logln("stratification_public.json 대조 PASS — 축별 units 합 847 · unstable 일치")
    return {"units_sum_per_axis": per_axis, "excluded_no_target_drugs": EXPECT_N_NO_TARGET,
            "unstable_stratum_counts": unst, "pass": True}


# ═══════════════════════════════════════════════════════════════════════════
# K-3. 불일치·경계 사례 분류
# ═══════════════════════════════════════════════════════════════════════════
SEEN_CLASSES = {"all-seen", "mixed"}


def crossed(values, bounds):
    """반복 간 값이 넘나든 경계 목록 + 최소 |값 − 경계| 거리."""
    lo, hi = min(values), max(values)
    cb = [b for b in bounds if lo < b <= hi]
    if not cb:
        return [], None
    dist = min(abs(v - b) for v in values for b in cb)
    return cb, float(dist)


def classify_cases(rep_df, stable_flags, exclset):
    """축별 unstable 약물 전건의 사유 분류 (경계 인접 / 집합 변동 / 관측 결손 / 분류 불가)."""
    bnd = json.load(open(F_BOUNDS, encoding="utf-8"))["boundaries"]
    struct_bounds = [bnd["q25"], bnd["q50"], bnd["q75"]]
    seq_bounds = [sap_unseen.SEQID_BOUNDARIES["low"], sap_unseen.SEQID_BOUNDARIES["mid"],
                  sap_unseen.SEQID_BOUNDARIES["high"]]

    by_cid = {int(c): g.sort_values("rep") for c, g in rep_df.groupby("cid")}
    dc_stable = stable_flags["drug_class"]
    rows, summary = [], {}

    for axis in AXES:
        piv, same = stability_table(rep_df, axis)
        unstable_cids = [int(c) for c in piv.index[~same] if c not in exclset]
        counts = {}
        for cid in unstable_cids:
            g = by_cid[cid]
            labels = g[axis].tolist()
            classes = g["drug_class"].tolist()
            flags, cb, dist, value_col = [], [], None, None

            if axis == "struct_bin":
                value_col = "max_tanimoto"
                vals = [float(v) for v in g[value_col]]
                cb, dist = crossed(vals, struct_bounds)
                if cb:
                    flags.append("boundary_adjacent")
            elif axis == "drug_class":
                # T_d 는 반복 불변이므로 분류 변동의 원인은 fold-train 표적 집합뿐이다.
                # 그 사실을 가정하지 않고 `n_unseen_targets` 변동으로 실제 확인한다.
                if int(g["n_unseen_targets"].nunique()) > 1:
                    flags.append("set_change")
            else:                                     # seq_stratum
                value_col = "s_drug"
                if int(((g["drug_class"] == "all-unseen") & (g["n_seqid_observed"] == 0)).sum()):
                    flags.append("observation_deficit")
                if bool(set(classes) & SEEN_CLASSES) and "all-unseen" in classes:
                    flags.append("set_change")        # exact-seen 여부가 반복마다 바뀜
                unseen_vals = [float(v) for v, c in zip(g["s_drug"], classes) if c == "all-unseen"]
                if len(unseen_vals) >= 2:
                    cb, dist = crossed(unseen_vals, seq_bounds)
                    if cb:
                        flags.append("boundary_adjacent")
            if not flags:
                flags.append("unclassified")

            primary = ("observation_deficit" if "observation_deficit" in flags else
                       "set_change" if "set_change" in flags else
                       "boundary_adjacent" if "boundary_adjacent" in flags else "unclassified")
            counts[primary] = counts.get(primary, 0) + 1
            # drug_class 가 3반복 stable `all-unseen` 인데 서열축만 unstable 인 사례
            # (docs/53 §4 의 "18 vs 17" 차이 1건).
            special = bool(axis == "seq_stratum" and dc_stable.get(cid, False)
                           and set(classes) == {"all-unseen"})

            for _, r in g.iterrows():
                rows.append({
                    "axis": axis, "cid": cid, "rep": int(r["rep"]), "fold": int(r["fold"]),
                    "stratum": r[axis], "drug_class_rep": r["drug_class"],
                    "axis_value": (None if value_col is None else float(r[value_col])),
                    "axis_value_name": (value_col or ""),
                    "n_targets": int(r["n_targets"]),
                    "n_unseen_targets": int(r["n_unseen_targets"]),
                    "n_seqid_observed": int(r["n_seqid_observed"]),
                    "primary_reason": primary, "reason_flags": "|".join(flags),
                    "crossed_boundaries": "|".join(f"{b:.6g}" for b in cb),
                    "min_distance_to_boundary": dist,
                    "all_unseen_stable_seq_unstable_case": special,
                })
        summary[axis] = {"n_unstable": len(unstable_cids), "reason_counts": counts}
        logln(f"K-3 {axis}: unstable {len(unstable_cids)} — " +
              " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    cases = pd.DataFrame(rows)
    cases.to_csv(OUT_CASES, index=False)

    n_unclassified = int((cases["primary_reason"] == "unclassified").sum())
    zero_obs = {}
    for r in (1, 2, 3):
        sub = rep_df[rep_df["rep"] == r]
        zero_obs[str(r)] = int(((sub["drug_class"] == "all-unseen")
                                & (sub["n_seqid_observed"] == 0)).sum())
    special = cases[cases["all_unseen_stable_seq_unstable_case"]]
    logln(f"K-3 관측 결손(all-unseen & n_seqid_observed==0) 반복별 = {zero_obs} · "
          f"분류 불가 {n_unclassified}행 · 특수 사례 약물 {special['cid'].nunique()}건")
    return cases, {"by_axis": summary, "n_rows": len(cases),
                   "n_unclassified_rows": n_unclassified,
                   "seqid_zero_observation_drugs": zero_obs,
                   "special_case_cids": sorted(special["cid"].unique().tolist()),
                   "special_case_rows": json.loads(
                       special.drop(columns=["all_unseen_stable_seq_unstable_case"])
                       .to_json(orient="records"))}


# ═══════════════════════════════════════════════════════════════════════════
# K-4. 공개 요약 보강 (신규 파일)
# ═══════════════════════════════════════════════════════════════════════════
def axis_label(rep_df, axis, exclset):
    """추정 대상 847 약물의 축별 라벨(stable 값 또는 `unstable_stratum`)."""
    piv, same = stability_table(rep_df, axis)
    lab = {}
    for cid in piv.index:
        if int(cid) in exclset:
            continue
        lab[int(cid)] = piv.loc[cid, 1] if same.loc[cid] else "unstable_stratum"
    return lab


def build_public(acc, pubchk, cases_sum, rep_df, exclset):
    lab_dc = axis_label(rep_df, "drug_class", exclset)
    lab_sq = axis_label(rep_df, "seq_stratum", exclset)
    cross = {}
    for cid, a in lab_dc.items():
        b = lab_sq[cid]
        cross.setdefault(a, {}).setdefault(b, 0)
        cross[a][b] += 1
    assert sum(sum(v.values()) for v in cross.values()) == EXPECT_DENOM

    axes_out = {}
    for axis in AXES:
        a = acc["axes"][axis]
        axes_out[axis] = {
            "n_drugs_by_stratum": a["strata_stable"],
            "unstable_stratum": a["unstable_stratum"],
            "denominator_estimated": a["denominator_estimated"],
            "sum_check": a["sum_check"],
            "unstable_reason_counts": cases_sum["by_axis"][axis]["reason_counts"],
            **AXIS_ROLE[axis],
        }

    out = {
        "_scope": ("공개 — **표본수 회계 전용**. 층별 macro AP·Δ·CI·sign-flip p 는 본 파일에 "
                   "한 값도 없다(전량 `_sealed/`). 개봉·성공판정·다중성 보정 없음."),
        "_relation": ("`strata_summary.json`·`stratification_public.json` 을 **덮어쓰지 않는 "
                      "신규 보강 파일**. 원본은 바이트 불변."),
        "ts_kst": sr.now_kst(),
        "block": "K (docs/54)",
        "n_total_drugs": acc["n_total_drugs"],
        "n_excluded_no_target": acc["n_excluded_no_target"],
        "denominator_estimated": acc["denominator_estimated"],
        "accounting_identity": "Σ stable(no-target 제외) + unstable_stratum = 847 · 847 + 245 = 1,092",
        "axes": axes_out,
        "cross_tab_drug_class_x_seq_stratum": cross,
        "cross_tab_note": ("표본수만. 라벨 = 3반복 일치 시 해당 층, 불일치 시 `unstable_stratum`. "
                           "행·열 합계는 각각 847."),
        "boundary_cases": {
            "n_rows": cases_sum["n_rows"],
            "n_unclassified_rows": cases_sum["n_unclassified_rows"],
            "seqid_zero_observation_drugs": cases_sum["seqid_zero_observation_drugs"],
            "special_case_cids": cases_sum["special_case_cids"],
            "detail_file": os.path.relpath(OUT_CASES, ROOT),
        },
        "asserts": {
            "row_count_3276": "PASS", "unique_drugs_1092": "PASS", "repeats_123_complete": "PASS",
            "no_target_245": "PASS", "stable_column_matches_recomputation": "PASS",
            "sum_stable_plus_unstable_eq_847_per_axis": "PASS",
            "847_plus_245_eq_1092": "PASS", "axis_denominators_equal": "PASS",
            "estimation_drug_set_identical_across_axes": "PASS",
            "stratification_public_units_sum_847": "PASS",
            "independent_reproduction_of_assignment": "PASS",
            "no_result_keys_in_public_output": "PASS",
        },
        "axis_role_basis": "docs/53 §1·§4 (교수님 2026-08-03 회신) — 라벨만 부착, 해석·판정 없음",
        "not_performed": ["개봉(open_sealed)", "성공판정 함수 호출", "다중성 보정",
                          "층별 AP·Δ·CI·p 재산출", "기존 sealed 산출물 수정",
                          "미실행 축(unseen-target proportion 등) 계산"],
        "public_units_crosscheck": pubchk,
    }
    return out


# ═══════════════════════════════════════════════════════════════════════════
# K-5. §13-6 커버리지 감사 (계산 금지 · 명세만)
# ═══════════════════════════════════════════════════════════════════════════
def build_coverage_audit(rep_df):
    R = lambda p: os.path.relpath(p, ROOT)                              # noqa: E731
    tm = os.path.join(ROOT, "data", "processed", "target_mapping")
    n_prop_computable = int((rep_df["n_targets"] > 0).sum())

    items = [
        {
            "id": "A1", "registered_axis": "max Morgan Tanimoto (구조 유사도)",
            "executed": True, "executed_where": "블록 H — struct_bin q1~q4 (`struct_bounds.json`)",
            "inputs_available": {"status": "available",
                                 "evidence": [R(F_STRATA), R(os.path.join(RUN_DIR, "_max_tanimoto.npy"))]},
            "definition_frozen": {"status": "frozen",
                                  "evidence": "struct_bounds.json (반복1 기준 25/50/75 분위, 결과 무참조 사전확정)"},
            "prerequisites": [], "phase": "confirmatory",
            "note": "블록 H 에서 층별 추정까지 완료(산출 전량 `_sealed/`).",
        },
        {
            "id": "A2", "registered_axis": "표적 max sequence identity",
            "executed": True, "executed_where": "블록 H — seq_stratum (seen/≥90/70–90/40–70/<40)",
            "inputs_available": {"status": "available",
                                 "evidence": [R(F_STRATA),
                                              "data/processed/target_mapping/_mmseqs/identity_pairs.tsv"]},
            "definition_frozen": {"status": "frozen",
                                  "evidence": "sap/unseen_target.py — SEQID_BOUNDARIES · drug_sequence_stratum"},
            "prerequisites": [], "phase": "confirmatory",
            "note": "층별 추정까지 완료. `unseen_40_70`·`unseen_lt40` 은 stable 표본 0 (추정 불가능성).",
        },
        {
            "id": "A3", "registered_axis": "unseen-target proportion — unweighted",
            "executed": False, "executed_where": None,
            "inputs_available": {
                "status": "available",
                "evidence": [f"{R(F_STRATA)} — `n_unseen_targets` / `n_targets` (분모>0 인 "
                             f"약물-반복 {n_prop_computable}행)"]},
            "definition_frozen": {
                "status": "not_frozen",
                "detail": ("비율 자체는 산술적으로 즉시 계산되나, **층 경계(bin)·연속축 처리 방식**이 "
                           "SAP·등록 어디에도 동결돼 있지 않다. `sap/unseen_target.py` 에 proportion "
                           "관련 상수·연산자 없음(A2 의 SEQID_BOUNDARIES 에 해당하는 것이 부재).")},
            "prerequisites": ["층 경계(또는 연속축 모형) 동결 amendment — post-interim"],
            "phase": "confirmatory",
            "note": "docs/53 §1 — '미관찰 표적 비율' 분석은 확증으로 유지 결정.",
        },
        {
            "id": "A4", "registered_axis": "unseen-target proportion — evidence-weighted",
            "executed": False, "executed_where": None,
            "inputs_available": {
                "status": "partial",
                "evidence": [f"{R(os.path.join(tm, '07_agg_topk.csv'))} — 표적별 `weight`·"
                             "`pchembl_median`·`affinity_imputed`(top-k 한정, 3,436행)",
                             f"{R(os.path.join(tm, '08_m1b_covariates.csv'))} — 약물수준 "
                             "`evidence_count`·`confidence_mean/max`·`pchembl_mean/max`"],
                "gap": "표적별 evidence 가중은 top-k(≤5) 표적에만 존재 — 전 표적 가중은 재생성 필요"},
            "definition_frozen": {"status": "not_frozen",
                                  "detail": "'evidence' 의 정의(assay 수 · confidence · pChEMBL · MoA 여부)와 "
                                            "가중 함수가 미동결. 층 경계도 미동결."},
            "prerequisites": ["가중 정의 동결 amendment", "층 경계 동결 amendment"],
            "phase": "confirmatory",
        },
        {
            "id": "A5", "registered_axis": "unseen-target proportion — mechanism-target indicator",
            "executed": False, "executed_where": None,
            "inputs_available": {
                "status": "regeneration_required",
                "evidence": [f"{R(os.path.join(tm, '08_m1b_covariates.csv'))} — **약물 수준** "
                             "`mechanism_target_n` 만 보유",
                             f"{R(os.path.join(tm, '03_targets.csv'))} — `source` 열이 전건 "
                             "'chembl' 단일값 → **표적 수준 mechanism/activity 구분 없음**",
                             "data/processed/target_mapping/_cache/ — ChEMBL `mechanism` 응답 "
                             "1,009 파일 존재(네트워크 없이 재파싱 가능)"],
                "gap": "표적 수준 mechanism 플래그가 현 산출물에 없음 → 캐시 재파싱으로 재생성 필요"},
            "definition_frozen": {"status": "not_frozen",
                                  "detail": "indicator 판정 기준(MoA 표적만 대상인지, 지표를 층 축으로 쓸지 "
                                            "공변량으로 쓸지)이 미동결."},
            "prerequisites": ["표적 수준 mechanism 플래그 재생성(캐시 재파싱)",
                              "판정 기준 동결 amendment"],
            "phase": "confirmatory",
        },
        {
            "id": "A6", "registered_axis": "unseen-target proportion — dominant-target-cold",
            "executed": False, "executed_where": None,
            "inputs_available": {
                "status": "partial",
                "evidence": [f"{R(os.path.join(tm, '07_agg_topk.csv'))} — `rank`(1~5)·"
                             "`pchembl_median` 로 '지배 표적' 후보 산출 가능",
                             f"{R(F_STRATA)} — fold-local seen/unseen 판정 입력"],
                "gap": "top-k 밖 표적의 순위·친화도 부재"},
            "definition_frozen": {"status": "not_frozen",
                                  "detail": "'dominant target' 정의(rank=1 / pChEMBL 임계 / MoA 우선)와 "
                                            "'cold' 임계가 미동결."},
            "prerequisites": ["dominant 정의·임계 동결 amendment"],
            "phase": "confirmatory",
        },
        {
            "id": "C1", "registered_axis": "각 축에서 Δ(M2b−M1b) 층화",
            "executed": True,
            "executed_where": "블록 H — 수행 축(A1·A2 + drug_class) 13 층 전건, 산출 전량 `_sealed/`",
            "inputs_available": {"status": "available",
                                 "evidence": ["experiments/runs/v3_consensus_rep123/_sealed/"
                                              "consensus_M1b.npz · consensus_M2b.npz"]},
            "definition_frozen": {"status": "frozen", "evidence": "SAP manifest 756d485feb4715e9 (v1.1)"},
            "prerequisites": [], "phase": "confirmatory",
            "note": "미실행 축(A3~A6)에 대해서는 당연히 미수행.",
        },
        {
            "id": "C2", "registered_axis": "각 축에서 Δ(M2b−P-ID) 층화",
            "executed": False, "executed_where": None,
            "inputs_available": {
                "status": "available",
                "evidence": ["experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/"
                             "consensus_P-ID.npz (블록 I, 2026-08-04 완료)",
                             "experiments/runs/v3_consensus_rep123/_sealed/consensus_M2b.npz"]},
            "definition_frozen": {"status": "frozen",
                                  "evidence": "대비 자체는 `sap/decision.py` HOLM_FAMILY ② 로 동결"},
            "prerequisites": [],
            "status_note": ("★ 선행 조건 **해소됨** — 블록 I 완료로 P-ID consensus OOF 확보. "
                            "'블록 I 이후 가능'이 아니라 **지금 계산 가능**이며, 다만 **본 블록(K) 범위 밖**이다. "
                            "후속 블록 후보로 제안한다."),
            "phase": "confirmatory",
        },
        {
            "id": "X1", "registered_axis": "(등록 §11 연속축 목록 밖) drug_class — all-seen/mixed/all-unseen",
            "executed": True, "executed_where": "블록 H — 3 층 + unstable_stratum",
            "inputs_available": {"status": "available", "evidence": [R(F_STRATA)]},
            "definition_frozen": {"status": "frozen",
                                  "evidence": "sap/unseen_target.py — classify_drug (등록 §9 범주 정의)"},
            "prerequisites": [], "phase": "data_characteristic",
            "note": ("docs/53 §1 — 세 집단의 구조적 **분포 자체는 데이터 특성으로 보고**하되 "
                     "**재분할 결과 분석은 exploratory**. §11 의 '연속 유사도 축'에는 포함되지 않는다."),
        },
    ]

    n_exec = sum(1 for i in items if i["executed"])
    return {
        "_scope": "공개 — 커버리지 감사(수행/미수행 표)뿐. 계산·추정 없음. 결과 수치 없음.",
        "ts_kst": sr.now_kst(),
        "block": "K-5 (docs/54)",
        "registered_section": ("docs/29 §11 — 연속 유사도 층화(primary): max Morgan Tanimoto / "
                              "표적 max sequence identity / unseen-target proportion(unweighted · "
                              "evidence-weighted · mechanism-target indicator · dominant-target-cold). "
                              "각 축에서 성능 · Δ(M2b−M1b) 및 Δ(M2b−P-ID) 층화."),
        "n_items": len(items), "n_executed": n_exec, "n_not_executed": len(items) - n_exec,
        "items": items,
        "definition_freeze_caveat": ("미동결 항목(A3 경계 · A4 가중 정의 · A5 판정 기준 · A6 임계)은 "
                                     "**본 블록에서 정하지 않는다**. Δ 부호 4건이 이미 공개된 뒤이므로 "
                                     "확정은 **post-interim amendment** 로만 가능하다."),
        "not_performed": ["미실행 축 계산 착수", "정의 확정", "개봉", "성공판정", "다중성 보정"],
    }


# ═══════════════════════════════════════════════════════════════════════════
def main():
    with ComputeLock(script="strata_accounting_check.py", role="recorder"):
        gate_a_load("block-K:strata_accounting_check")
        guard_start = guard_snapshot_all()
        logln(f"착수 — sealed guard {len(guard_start)}종 스냅샷")

        rep_df, repro = reproduce_assignment()
        acc, stable_flags, exclset = accounting(rep_df)
        logln("K-2 회계 assert PASS — 축별 Σ stable + unstable = "
              f"{EXPECT_DENOM} · {EXPECT_DENOM} + {acc['n_excluded_no_target']} = "
              f"{acc['n_total_drugs']} · 축 간 모수 동일")
        pubchk = crosscheck_public(acc)
        cases, cases_sum = classify_cases(rep_df, stable_flags, exclset)

        public = build_public(acc, pubchk, cases_sum, rep_df, exclset)
        guard_defense = assert_no_result_keys(public)
        public["public_redaction_assert"] = guard_defense
        sr.dump_json(OUT_PUBLIC, public)

        coverage = build_coverage_audit(rep_df)
        assert_no_result_keys(coverage)
        sr.dump_json(OUT_COVERAGE, coverage)

        guard_end = guard_snapshot_all()
        guard_ok = (guard_end == guard_start)
        assert guard_ok, "[중단] sealed guard 변경 감지 — 봉인 산출물 바이트가 바뀌었다"

        check = {
            "_scope": "공개 — 회계 assert·사유 분류·게이트 결과뿐. 층별 AP·Δ·CI·p 없음.",
            "ts_kst": sr.now_kst(), "block": "K (docs/54)",
            "independent_reproduction": repro,
            "accounting": acc,
            "public_units_crosscheck": pubchk,
            "unstable_cases": cases_sum,
            "sealed_guard_n_files": len(guard_start),
            "sealed_guard_unchanged": bool(guard_ok),
            "decision_functions_called": [], "multiplicity_applied": False,
            "open_sealed_calls": 0,
            "outputs": {os.path.relpath(p, ROOT): True
                        for p in (OUT_CASES, OUT_CHECK, OUT_PUBLIC, OUT_COVERAGE)},
            "all_pass": True,
        }
        assert_no_result_keys(check)
        sr.dump_json(OUT_CHECK, check)
        logln(f"완료 — sealed guard {len(guard_end)}종 불변({guard_ok}) · 신규 4파일")
    return check


if __name__ == "__main__":
    main()
