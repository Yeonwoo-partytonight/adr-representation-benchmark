#!/usr/bin/env python3
"""rqint_facts_M1.py — 블록 M-1: RQ-int 외부검토 패키지 v2 의 **결과-독립 설계량** 추출.

성격
----
**설계량 재계산 + synthetic 타이밍 전용.** 모델학습 0 · 새 OOF 0 · 새 추정 0 ·
`_sealed/` 접근 0 · `decision.py` 성공판정 호출 0 · Δ/AP/CI/p 산출 0.

입력은 **라벨(`master_Y.parquet`)과 split 구조(`fold_membership.csv`)** 뿐이며,
예측(OOF)은 한 바이트도 읽지 않는다 → 산출 전량이 **결과-독립**이다.
macro AP 타이밍은 **synthetic 난수 예측**(shape·dtype 만 실제와 동일)으로 측정한다.

실행: .venv/bin/python3 v3_Multimodal/src/rqint_facts_M1.py
산출: experiments/runs/v3_rqint_package_v2/facts_public.json
"""
from __future__ import annotations

import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KST = timezone(timedelta(hours=9))

sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))
from sap.metrics import macro_ap                                       # noqa: E402
from sap.bootstrap import n_eff_clusters                                # noqa: E402
from sap.decision import (PT_MIN_POSITIVE,                             # noqa: E402
                          PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS, pt_eligibility)

Y_PATH = os.path.join(ROOT, "data", "processed", "master_Y.parquet")
SPLIT_DIR = os.path.join(ROOT, "data", "processed", "splits", "confirmatory")
REPEATS = [("rep1", 201), ("rep2", 202), ("rep3", 203)]
OUT_DIR = os.path.join(ROOT, "experiments", "runs", "v3_rqint_package_v2")
OUT = os.path.join(OUT_DIR, "facts_public.json")

# 공개 파일에 절대 나타나면 안 되는 필드(방어 assert; 블록 I·K 목록 재사용)
FORBIDDEN_KEYS = ("macro_ap", "delta", "sign", "ci_bca", "ci_percentile", "ci_",
                  "p_two_sided", "p_emp", "per_pt_ap", "boot_summary", "null_summary")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def load_folds(rep_dir):
    """fold_membership.csv → cid·fold·scaffold(빈 문자열 그룹 보존)."""
    df = pd.read_csv(os.path.join(rep_dir, "fold_membership.csv"),
                     keep_default_na=False, na_values=[])
    df["scaffold"] = df["scaffold"].astype(str)
    return df[["cid", "fold", "scaffold"]]


def main():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    facts = {
        "_doc": "블록 M-1 결과-독립 설계량 (docs/58). 예측·봉인 미접근, synthetic 타이밍만 계산.",
        "generated_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "inputs": {},
        "loadavg_at_start": os.getloadavg(),
    }

    # ---------- 입력 지문 ----------
    facts["inputs"]["master_Y"] = {"path": "data/processed/master_Y.parquet",
                                   "sha256_16": sha256(Y_PATH)[:16]}
    Ydf = pd.read_parquet(Y_PATH)
    cids = Ydf["cid"].to_numpy()
    pt_cols = [c for c in Ydf.columns if c != "cid"]
    Y = Ydf[pt_cols].to_numpy().astype(np.int8)
    n_drug, K = Y.shape
    facts["dataset"] = {"n_drug": int(n_drug), "n_pt_columns": int(K),
                        "n_positive_total": int(Y.sum()),
                        "label_density": round(float(Y.mean()), 6)}

    # ---------- M-1-2: eligible PT 재계산 ----------
    n_pos = Y.sum(axis=0)
    rule_a_mask = n_pos >= PT_MIN_POSITIVE                      # §7: global 양성 ≥10
    per_repeat = {}
    a3_masks = {}
    for name, seed in REPEATS:
        rep_dir = os.path.join(SPLIT_DIR, f"{name}_seed{seed}")
        fm = load_folds(rep_dir)
        assert list(fm["cid"]) == list(cids), f"{name}: cid 순서 불일치"
        groups = fm["scaffold"].to_numpy()
        elig = pt_eligibility(Y, groups)                        # A3(결과-독립)
        a3_mask = np.zeros(K, dtype=bool)
        a3_mask[np.array(elig["eligible_pt"], dtype=int)] = True
        a3_masks[name] = a3_mask
        n_clusters_pos = np.array([elig["per_pt"][j]["n_positive_scaffold_clusters"]
                                   for j in range(K)])
        per_repeat[name] = {
            "split_seed": seed,
            "n_pt_rule_A_pos_ge_10": int(rule_a_mask.sum()),
            "n_pt_rule_A3_both": int(a3_mask.sum()),
            "n_pt_failing_cluster_condition_only": int((rule_a_mask & ~a3_mask).sum()),
            "min_positive_scaffold_clusters_over_pts": int(n_clusters_pos.min()),
            "fold_membership_sha256_16": sha256(
                os.path.join(rep_dir, "fold_membership.csv"))[:16],
        }
    identical = all(np.array_equal(a3_masks["rep1"], a3_masks[n]) for n, _ in REPEATS)
    facts["eligible_pt"] = {
        "rule_A_source": "사전등록 §5.2/§7: global 양성 ≥10인 PT (master_Y 열 자체가 이 규칙으로 사전 확정)",
        "rule_A3_source": "docs/43 A3 / sap/decision.py pt_eligibility — 양성≥10 AND 양성-포함 scaffold cluster ≥3",
        "PT_MIN_POSITIVE": int(PT_MIN_POSITIVE),
        "PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS": int(PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS),
        "min_positive_over_all_pts": int(n_pos.min()),
        "n_pt_rule_A_pos_ge_10": int(rule_a_mask.sum()),
        "per_repeat": per_repeat,
        "a3_identical_across_repeats": bool(identical),
        "note_scope": ("A3 는 코드·docs/43 모두 'PT별 BH-FDR eligibility' 로 한정 기술된다. "
                       "macro AP 의 eligible_pt 는 확증·층화 런 모두 None(=370 전열)으로 호출됐다 "
                       "(docs/33 항목 §13-6 판독확정 ③, docs/33 블록 I 기록)."),
    }

    # ---------- M-1-3: scaffold group 구조 ----------
    fm1 = load_folds(os.path.join(SPLIT_DIR, "rep1_seed201"))
    sizes = fm1.groupby("scaffold").size()
    n_groups = int(sizes.size)
    size_hist = {"size_1": int((sizes == 1).sum()), "size_2": int((sizes == 2).sum()),
                 "size_3": int((sizes == 3).sum()), "size_4plus": int((sizes >= 4).sum())}
    grid = {}
    group_sets = {}
    for name, seed in REPEATS:
        fm = load_folds(os.path.join(SPLIT_DIR, f"{name}_seed{seed}"))
        s = fm.groupby("scaffold").size()
        group_sets[name] = set(s.index)
        crossing = int(fm.groupby("scaffold")["fold"].nunique().gt(1).sum())
        cells = {}
        for f in sorted(fm["fold"].unique()):
            sub = fm[fm["fold"] == f]
            cells[f"fold{int(f)}"] = {"n_drugs": int(sub.shape[0]),
                                      "n_groups": int(sub["scaffold"].nunique())}
        grid[name] = {"split_seed": seed, "n_groups": int(s.size),
                      "groups_crossing_folds": crossing, "folds": cells}
    facts["scaffold_structure"] = {
        "n_groups": n_groups,
        "n_drugs": int(fm1.shape[0]),
        "size_hist": size_hist,
        "max_group_size": int(sizes.max()),
        "max_group_share_of_drugs": round(float(sizes.max() / fm1.shape[0]), 4),
        "n_eff_clusters_kish": round(n_eff_clusters(sizes.to_numpy()), 1),
        "singleton_ratio": round(float((sizes == 1).sum() / n_groups), 4),
        "group_partition_identical_across_repeats":
            bool(group_sets["rep1"] == group_sets["rep2"] == group_sets["rep3"]),
        "per_repeat_fold_grid": grid,
    }

    # ---------- M-1-4: permutation 공간 ----------
    fold_tuples = None
    for name, seed in REPEATS:
        fm = load_folds(os.path.join(SPLIT_DIR, f"{name}_seed{seed}"))
        col = fm.set_index("cid")["fold"].reindex(cids).to_numpy()
        fold_tuples = col.reshape(-1, 1) if fold_tuples is None else \
            np.concatenate([fold_tuples, col.reshape(-1, 1)], axis=1)
    n_intersect_cells = int(len({tuple(r) for r in fold_tuples}))
    B = 10000
    facts["permutation_space"] = {
        "B": B,
        "min_two_sided_p_with_B": round(1.0 / (B + 1), 6),
        "unit_scaffold_group": {"n_units": n_groups,
                                "n_sign_assignments": f"2^{n_groups} ≈ {2.0 ** n_groups:.1e}",
                                "min_achievable_two_sided_p": round(1.0 / (B + 1), 6),
                                "binding_constraint": "B (공간이 아니라 표본수가 하한을 정함)"},
        "unit_outer_fold_single_repeat": {"n_units": 5, "n_sign_assignments": str(2 ** 5),
                                          "min_achievable_two_sided_p": round(1.0 / (2 ** 5 + 1), 6),
                                          "binding_constraint": "공간(2^5=32)이 하한을 정함"},
        "unit_outer_fold_intersection_3repeats": {
            "n_units": n_intersect_cells,
            "n_sign_assignments": f"2^{n_intersect_cells} ≈ {2.0 ** n_intersect_cells:.1e}",
            "min_achievable_two_sided_p": f"{1.0 / (2.0 ** n_intersect_cells + 1):.1e}",
            "assumption": "consensus OOF 는 반복별 fold 배정이 달라 단일 fold 라벨이 없다. "
                          "세 반복의 fold 배정 튜플로 만든 교집합 셀을 교환 단위로 본 경우."},
        "assumption_note": "sign-flip 은 consensus OOF(1,092×370) 한 장 위에서 수행되므로 "
                           "교환 단위 수는 반복 수와 무관하다. fold 단위 상향 시 반복 1개 기준 2^5.",
        "complement_symmetry": {
            "claim": "후보 A·B 모두 전(全) 단위 flip 은 T*=−T 를 준다(A: 두 family 전면 교환, "
                     "B: 두 family 에서 arm 전면 교환) → |T*| 는 상보쌍에서 동일.",
            "implication": "항등 배열과 그 상보 배열 2개는 항상 |T*| ≥ |T_obs| 를 만족하므로, "
                           "양측 p 의 하한은 2 / 2^(단위 수) 이다(몬테카를로 기대값 기준).",
            "min_two_sided_p_fold_unit_5": round(2.0 / 32, 6),
            "min_two_sided_p_fold_unit_5_enumeration_formula": round(3.0 / 33, 6),
            "min_two_sided_p_group_unit_732": "2/2^732 ≪ 1/(B+1) → B 가 하한을 정함",
            "holm_implication_fold_unit": {
                "alpha": 0.05,
                "verdict": "fold(5) 단위에서는 무보정 p 하한(≈0.0625)이 이미 α=0.05 를 넘어 "
                           "Holm 보정 이전에도 RQ-int 기각이 불가능하다.",
                "holm_worst_case_multiplier": 7,
            },
        },
    }

    # ---------- M-1-5: macro AP 1회 호출 wall (synthetic 예측) ----------
    rng = np.random.default_rng(20260804)
    P_syn = rng.random((n_drug, K), dtype=np.float64)          # synthetic — 실제 OOF 아님
    macro_ap(Y[:8], P_syn[:8], None)                            # warm-up(작은 슬라이스)
    times = []
    for _ in range(10):
        t = time.perf_counter()
        macro_ap(Y, P_syn, None)
        times.append(time.perf_counter() - t)
    # permutation 1회의 block-swap 오버헤드(AP 재계산 비용과 대비용)
    swap_mask = rng.random(n_drug) < 0.5
    P2_syn = rng.random((n_drug, K), dtype=np.float64)
    swap_times = []
    for _ in range(10):
        t = time.perf_counter()
        _a = np.where(swap_mask[:, None], P2_syn, P_syn)
        _b = np.where(swap_mask[:, None], P_syn, P2_syn)
        swap_times.append(time.perf_counter() - t)
    times_sorted = sorted(times)
    med = statistics.median(times)
    q1 = statistics.median(times_sorted[:5])
    q3 = statistics.median(times_sorted[5:])
    calls_rf = 2                    # M1b·M2b
    calls_gin = 3 * 2               # 3 seed × (M1b·M2b)
    calls_per_perm = calls_rf + calls_gin
    facts["macro_ap_timing"] = {
        "input": "synthetic uniform random predictions (실제 OOF 미사용), 실제 라벨 y 사용",
        "shape": [int(n_drug), int(K)], "dtype": "float64", "n_calls_measured": 10,
        "median_s": round(med, 4), "iqr_s": [round(q1, 4), round(q3, 4)],
        "min_s": round(min(times), 4), "max_s": round(max(times), 4),
        "block_swap_median_s": round(statistics.median(swap_times), 4),
        "block_swap_note": "scaffold block 교환(1,092×370 두 장 재구성) 1회 비용. AP 재계산 대비 오버헤드 비교용.",
        "calls_per_permutation": {"RF": calls_rf, "GIN_3seed": calls_gin,
                                  "total_if_seed_average_inside": calls_per_perm},
        "calls_per_permutation_variant_ii": {
            "RF": 2, "GIN_3seed_x_3repeat": 3 * 3 * 2, "total": 2 + 3 * 3 * 2,
            "note": "GIN 을 (seed, 반복) 셀마다 metric 산출(=(ii)형)로 두는 경우.",
        },
        "cost_estimate_B10000": {
            "serial_hours": round(med * calls_per_perm * B / 3600.0, 2),
            "hours_at_6_parallel_workers": round(med * calls_per_perm * B / 3600.0 / 6, 2),
            "hours_at_18_parallel_workers": round(med * calls_per_perm * B / 3600.0 / 18, 2),
            "serial_hours_variant_ii": round(med * (2 + 18) * B / 3600.0, 2),
            "parallel_note": "블록 D 실측 실효 병렬도(2.05/18)는 RF 학습 부하 기준이며 "
                             "본 추정(순수 AP 재계산)에는 그대로 적용하지 않는다 — 상·하한만 제시.",
        },
        "multiplier_note": "반복 축을 permutation 안쪽에서 다시 도는 구성이면 위 호출 수에 반복 수가 곱해진다 "
                           "(예: (ii)형 15셀 → RF 2×3 + GIN 3seed×2×3).",
        "loadavg_at_measure": os.getloadavg(),
    }

    # ---------- M-2-3: macro_ap 의 eligible_pt 의존성 ----------
    facts["macro_ap_signature"] = {
        "signature": "macro_ap(y, P, eligible_pt=None)",
        "eligible_pt_depends_on_predictions": False,
        "evidence": "sap/metrics.py — eligible_pt 는 호출자가 주는 열 인덱스이며, 내부 undefined-AP "
                    "판정은 y[:, j].sum() > 0 만 본다(P 미참조).",
    }

    facts["integrity"] = {
        "sealed_accessed": False, "open_sealed_calls": 0, "decision_functions_called": [],
        "models_trained": 0, "new_oof": 0, "delta_or_ap_computed_on_real_predictions": False,
        "network_calls": 0,
    }
    facts["elapsed_s"] = round(time.time() - t0, 2)

    blob = json.dumps(facts, ensure_ascii=False)
    for k in FORBIDDEN_KEYS:
        assert f'"{k}"' not in blob.replace('"macro_ap_timing"', '"TIMING"') \
                                   .replace('"macro_ap_signature"', '"SIG"'), \
            f"공개 파일에 봉인 대상 필드 {k} 노출"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)
    back = json.load(open(OUT, encoding="utf-8"))
    assert back == json.loads(json.dumps(facts)), "roundtrip FAIL"
    print(json.dumps(facts, ensure_ascii=False, indent=2))
    print(f"\n[OK] {os.path.relpath(OUT, ROOT)} sha16={sha256(OUT)[:16]}")


if __name__ == "__main__":
    main()
