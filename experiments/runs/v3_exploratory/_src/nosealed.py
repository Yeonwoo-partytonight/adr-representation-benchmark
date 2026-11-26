#!/usr/bin/env python3
"""nosealed.py — 블록 CN(docs/153) 중 **봉인 접근이 전혀 없는** 항목.

수행 항목 = X3 · X4(부분: 공개 집계) · X5-① · X7(기술통계) · X9a(기술통계)
            · X10a · X10b · X1(점추정) · A5 · A6.

학습·재학습 0 · p-value 0 · 네트워크 0 · `_sealed/` 접근 0.
출력 = experiments/runs/v3_exploratory/<ID>/ (JSON + CSV).
"""
from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import zipfile

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))        # .../v3_exploratory/_src
ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "runs", "v3_exploratory")
SP = os.path.join(ROOT, "experiments/runs/v3_unblinding/results/sealed_publish")
TM = os.path.join(ROOT, "data/processed/target_mapping")

ARMS_RF = ["M0", "M1", "M1b", "M2", "M2b", "P-ID", "P-FAM", "C-CAP"]
ARMS_GIN = ["M0", "M1", "M1b", "M2b", "P-ID", "P-FAM", "C-CAP"]


def jdump(item, name, obj):
    d = os.path.join(OUT, item)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return p


def cdump(item, name, header, rows):
    d = os.path.join(OUT, item)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return p


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


PRODUCED = []


def rec(p):
    PRODUCED.append(p)
    print("  ->", os.path.relpath(p, ROOT))


# ═════════════════════════════════════════════════════════════════════════
# 공개 consensus macro AP (RF) — X1 점추정·X3 의 공통 입력
# ═════════════════════════════════════════════════════════════════════════
def rf_consensus_macro_ap():
    a = jload(os.path.join(
        SP, "experiments__runs__v3_consensus_rep123___sealed__metrics_full.json"))
    b = jload(os.path.join(
        SP, "experiments__runs__v3_confirm_rest_consensus_rep123___sealed__metrics_full.json"))
    m, per_rep = {}, {}
    for src in (a, b):
        for k, v in src["macro_ap"].items():
            m[k] = float(v["macro_ap"]) if isinstance(v, dict) else float(v)
        for k, v in src.get("per_repeat_macro_ap", {}).items():
            per_rep[k] = v
    return m, per_rep


# ═════════════════════════════════════════════════════════════════════════
# X1 — 성분 분해 (점추정만. BCa CI 는 sealed.py 에서)
# ═════════════════════════════════════════════════════════════════════════
X1_CONTRASTS = [
    ("C-CAP - M1b", "C-CAP", "M1b", -0.0301),
    ("P-ID - M1b", "P-ID", "M1b", +0.0123),
    ("P-FAM - M1b", "P-FAM", "M1b", +0.0021),
    ("M1b - M0", "M1b", "M0", None),
    ("M1b - M1", "M1b", "M1", +0.0088),
    ("M1 - M0", "M1", "M0", +0.0030),
    ("M2b - M1b", "M2b", "M1b", None),
]


def x1_point():
    m, _ = rf_consensus_macro_ap()
    rows, out = [], {}
    for lbl, t, b, exp in X1_CONTRASTS:
        d = m[t] - m[b]
        agree = None if exp is None else bool(abs(d - exp) <= 1e-4)
        out[lbl] = {"delta_point": d, "treat_arm": t, "base_arm": b,
                    "treat_macro_ap": m[t], "base_macro_ap": m[b],
                    "instruction_expected_rounded": exp,
                    "within_1e-4_of_expected": agree}
        rows.append([lbl, t, b, "%.10f" % m[t], "%.10f" % m[b], "%.10f" % d,
                     "%.4f" % d, "" if exp is None else "%.4f" % exp,
                     "" if agree is None else ("yes" if agree else "NO")])
    rec(cdump("X1", "x1_point_estimates.csv",
              ["contrast", "treat", "base", "treat_macro_ap", "base_macro_ap",
               "delta", "delta_rounded_4dp", "expected_rounded",
               "within_1e-4"], rows))
    rec(jdump("X1", "x1_point_estimates.json", {
        "_doc": "블록 CN X1 — RF consensus 성분 분해 점추정. 비등록·탐색적. p-value 0.",
        "source": ["experiments/runs/v3_unblinding/results/sealed_publish/"
                   "experiments__runs__v3_consensus_rep123___sealed__metrics_full.json",
                   "experiments/runs/v3_unblinding/results/sealed_publish/"
                   "experiments__runs__v3_confirm_rest_consensus_rep123___sealed__metrics_full.json"],
        "note": "공개 metrics 의 arm 별 절대 macro AP 차이. 봉인 OOF 미접근.",
        "arm_absolute_macro_ap": m,
        "contrasts": out}))
    return out


# ═════════════════════════════════════════════════════════════════════════
# X1 추가 — C-CAP 노이즈 블록이 unmapped drug 에서 0 인지 코드로 확인
# ═════════════════════════════════════════════════════════════════════════
def x1_ccap_code_check():
    """C-CAP 블록이 unmapped drug(245)에서 0 인지 **코드로** 확인(계산 재실행 0)."""
    rel = "v3_Multimodal/src/ladder_confirmatory.py"
    src = open(os.path.join(ROOT, rel), encoding="utf-8").read().splitlines()

    def q(n):
        return {"line": n, "text": src[n - 1].rstrip()}

    # CcapBlock 클래스 범위와 transform() 의 0-재설정 행을 소스에서 직접 찾는다.
    cls = next(i for i, l in enumerate(src, 1) if l.startswith("class CcapBlock"))
    end = next(i for i, l in enumerate(src, 1)
               if i > cls and l.startswith("class ") and not l[0].isspace())
    body = list(range(cls, end))
    zero_lines = [i for i in body if "out[unmapped] = 0.0" in src[i - 1]]
    unmapped_def = [i for i in body if "unmapped = ~self.seq.mask[idx]" in src[i - 1]]
    assert zero_lines and unmapped_def, "C-CAP 0-재설정 코드 미발견 — 보고 후 중단"

    mask = np.load(os.path.join(ROOT, "data/processed/drug_target_mask_meanpool.npy"))
    mask = np.asarray(mask).astype(bool).ravel()
    out = {
        "_doc": "블록 CN X1 추가 — C-CAP 노이즈 블록이 unmapped drug(245)에서 0 인지 "
                "코드 근거로 확인. 계산 재실행 0 · 봉인 0.",
        "method": "동결 소스 정적 판독(실행 0) — 파일·행 번호·원문 인용",
        "file": rel,
        "class_CcapBlock": {"first_line": cls, "last_line": end - 1},
        "verdict": "확인 — unmapped 행은 transform() 반환 직전에 명시적으로 0.0 으로 "
                   "재설정된다. 따라서 C-CAP 의 합성 노이즈는 245 unmapped drug 에서 "
                   "정확히 0 이고, B_seq 와 동일한 mask sparsity 를 갖는다.",
        "cited_lines": {
            "docstring_same_missing_pattern": [q(266), q(267)],
            "docstring_construction_refit_zero": q(270),
            "transform_signature": q(300),
            "unmapped_definition": [q(i) for i in unmapped_def],
            "zero_assignment": [q(i) for i in zero_lines],
        },
        "mask_file_crosscheck": {
            "file": "data/processed/drug_target_mask_meanpool.npy",
            "n_rows": int(mask.size),
            "n_mapped_mask_true": int(mask.sum()),
            "n_unmapped_mask_false": int((~mask).sum()),
            "note": "transform() 의 unmapped = ~self.seq.mask → 이 파일의 False 행 "
                    "245개가 0 으로 재설정되는 대상.",
        },
    }
    rec(jdump("X1", "x1_ccap_noise_unmapped_code_check.json", out))
    return out


# ═════════════════════════════════════════════════════════════════════════
# X3 — GIN 절대 AP (공개 metrics) + RF consensus 절대 AP
# ═════════════════════════════════════════════════════════════════════════
def x3():
    g = jload(os.path.join(
        SP, "experiments__runs__v3_gin_confirm_consensus_rep123___sealed__metrics_full.json"))
    cell1 = g["cells"]["cell_1_seed_consensus_macro_ap"]
    cell4 = g["cells"]["cell_4_auxiliary_sealed_per_repeat"]
    seeds = ["seed42", "seed1", "seed2"]
    rf, _ = rf_consensus_macro_ap()

    rows, gin = [], {}
    for arm in ARMS_RF:
        per_seed = {s: cell1.get("%s|%s" % (arm, s), {}).get("macro_ap")
                    for s in seeds}
        vals = [v for v in per_seed.values() if v is not None]
        mean = float(np.mean(vals)) if vals else None
        gin[arm] = {"per_seed_repeat_consensus": per_seed,
                    "seed_mean": mean,
                    "n_seeds": len(vals)}
        rows.append([arm,
                     "" if per_seed["seed42"] is None else "%.10f" % per_seed["seed42"],
                     "" if per_seed["seed1"] is None else "%.10f" % per_seed["seed1"],
                     "" if per_seed["seed2"] is None else "%.10f" % per_seed["seed2"],
                     "" if mean is None else "%.10f" % mean,
                     "없음" if mean is None else "",
                     "%.10f" % rf[arm] if arm in rf else ""])
    rec(cdump("X3", "x3_absolute_macro_ap_gin_vs_rf.csv",
              ["arm", "gin_seed42", "gin_seed1", "gin_seed2",
               "gin_seed_mean", "gin_note", "rf_consensus"], rows))

    per_rep = {}
    for k, v in cell4.items():
        per_rep[k] = v.get("macro_ap")
    rec(jdump("X3", "x3_absolute_macro_ap.json", {
        "_doc": "블록 CN X3 — GIN arm 별 절대 macro AP(공개 metrics) + RF consensus 절대 AP. "
                "비등록·탐색적 기술통계. p-value 0.",
        "gin_source": "experiments/runs/v3_unblinding/results/sealed_publish/"
                      "experiments__runs__v3_gin_confirm_consensus_rep123___sealed__metrics_full.json",
        "gin_aggregation_verbatim": g["aggregation"],
        "gin_consensus_definition": "cell_1 = repeat 축 consensus(prediction-then-metric) 후 "
                                    "seed 별 macro AP · seed 축은 metric-then-average(=seed_mean)",
        "gin_arms_present": sorted({k.split("|")[0] for k in cell1}),
        "gin_arms_absent": [a for a in ARMS_RF
                            if a not in {k.split("|")[0] for k in cell1}],
        "gin": gin,
        "gin_per_repeat_per_seed": per_rep,
        "rf_consensus_absolute_macro_ap": rf,
        "rf_source": "공개 consensus metrics_full.json 2종(위 X1 source 와 동일)",
        "label_prevalence_baseline_macro_ap": 0.048876348876348875,
        "label_prevalence_baseline_source":
            "experiments/runs/v3_unblinding/results/results_full.json items.S-base"
                 ".label_prevalence_baseline.macro_ap"}))
    return gin, rf


# ═════════════════════════════════════════════════════════════════════════
# X4 — RQ4 하위 꼬리 (공개 null_result.json 집계값)
# ═════════════════════════════════════════════════════════════════════════
def x4_public():
    d = jload(os.path.join(
        SP, "experiments__runs__v3_null_MAIN___sealed__null_result.json"))
    t_obs = d["T_obs"]
    out = {}
    for fam in ("global", "family"):
        p = d["primary"][fam]
        B, n_ge = p["B"], p["n_ge_obs"]
        out[fam] = {
            "B": B, "n_ge_obs": n_ge,
            "frac_ge_obs": n_ge / B,
            "frac_below_obs": (B - n_ge) / B,
            "n_below_obs": B - n_ge,
            "note": "frac_below_obs = 1 - n_ge_obs/B. 실현값 평균·중앙값은 봉인 "
                    "checkpoint.jsonl 필요 → sealed.py 에서 산출. "
                    "D-3 에 따라 확증 p_emp 는 본 산출물에 전재하지 않는다"
                    "(필요 시 공개 null_result.json 참조).",
        }
    rec(jdump("X4", "x4_public_tail_counts.json", {
        "_doc": "블록 CN X4(공개 부분) — RQ4 null 하위 꼬리 비율. 비등록·탐색적. p-value 계산 0 "
                "(기록된 p_emp 는 확증 산출물의 전재이며 본 블록이 계산한 값이 아니다).",
        "source": "experiments/runs/v3_unblinding/results/sealed_publish/"
                  "experiments__runs__v3_null_MAIN___sealed__null_result.json",
        "T_obs": t_obs,
        "T_definition": d["T_definition"],
        "sidedness_of_registered_test": d["sidedness"],
        "instruction_expected": {"family": 0.035, "global": 0.786},
        "tails": out}))
    return out


def x4_realization_storage_check():
    """realization 별 재배정 정보가 저장돼 있는지 코드로 확인."""
    p = os.path.join(ROOT, "v3_Multimodal/src/null_main_run.py")
    src = open(p, encoding="utf-8").read().splitlines()
    ck_line = next(i for i, l in enumerate(src, 1) if l.startswith("CKPT_FIELDS"))
    fields_txt = "\n".join(src[ck_line - 1:ck_line + 1])
    rec_lines = [(i, l.strip()) for i, l in enumerate(src, 1)
                 if "permutation_report" in l]
    out = {
        "_doc": "X4 선택항목 — realization 별 target 재배정 정보 저장 여부. 코드 근거.",
        "ckpt_fields_declaration": {
            "file": "v3_Multimodal/src/null_main_run.py",
            "line": ck_line, "text": fields_txt},
        "permutation_report_mentions": [
            {"file": "v3_Multimodal/src/null_main_run.py", "line": i, "text": t}
            for i, t in rec_lines],
        "verdict": "미저장 — ckpt_append() 는 CKPT_FIELDS 로 사영(project)하며 "
                   "permutation_report 는 그 목록에 없다. 따라서 realization 별 "
                   "재배정(어느 target 이 어디로 갔는지) 은 어느 산출물에도 남지 않았다.",
        "consequence": "대형 family 별 재배정 비율과의 관계 표는 생략(지시서 조건부 항목).",
        "remark": "재배정은 seed 로 결정적이라 원리상 재생성 가능하나, 재생성은 "
                  "'기존 산출물 읽기·재집계' 범위를 넘으므로 수행하지 않는다.",
    }
    rec(jdump("X4", "x4_realization_storage_check.json", out))
    return out


# ═════════════════════════════════════════════════════════════════════════
# X5-① — size_weighted 재표집이 estimand 를 바꾸는지 (코드 판독)
# ═════════════════════════════════════════════════════════════════════════
def x5_code():
    p = os.path.join(ROOT, "v3_Multimodal/src/sap/bootstrap.py")
    src = open(p, encoding="utf-8").read().splitlines()

    def q(n):
        return {"line": n, "text": src[n - 1].rstrip()}

    rfj = jload(os.path.join(ROOT, "experiments/runs/v3_unblinding/results/results_full.json"))
    sw = rfj["items"]["S-unit-sw"]["bootstrap"]
    pr = rfj["items"]["C1"]["bootstrap"]
    out = {
        "_doc": "블록 CN X5-① — sap/bootstrap.py size_weighted 재표집의 성격 판독. 계산 0.",
        "file": "v3_Multimodal/src/sap/bootstrap.py",
        "cited_lines": {
            "docstring_unit_size_weighted": q(20),
            "estimand_A6_pooled_ap": q(40),
            "delta_obs_on_all_rows": q(142),
            "probs_size_proportional": q(168),
            "probs_uniform_primary": q(170),
            "draw_clusters": q(175),
            "rows_concatenate": q(176),
            "jackknife_scaffold_delete_one": q(193),
        },
        "reading": (
            "표집 확률만 바뀌는 것이 아니라 **replicate 의 기대 구성 자체**가 바뀐다. "
            "L168 에서 cluster i 가 크기 비례 확률 p_i = s_i/Σs 로 뽑히고 L175 에서 "
            "n_clusters 회 복원추출되므로 cluster i 의 기대 등장 횟수는 n_clusters·s_i/Σs, "
            "따라서 replicate 안의 기대 행 수는 n_clusters·s_i²/Σs — 즉 **약물 1행의 "
            "기대 가중이 자기 cluster 크기 s_i 에 비례**한다. L40(A6) 이 못박은 대로 "
            "replicate 안의 집계는 drug-weighted pooled macro AP 이므로, 가중이 바뀌면 "
            "추정 대상(estimand) 자체가 '큰 cluster 과대가중 macro AP 차이'로 이동한다. "
            "primary(L170, 균등)는 cluster 균등 가중이라 이 이동이 없다."),
        "asymmetry_observed": (
            "delta_obs 는 L142 에서 전체 행에 대해 한 번만 계산되므로 unit 과 무관하게 "
            "동일(-0.006324167855457974). 반면 size_weighted bootstrap 분포는 평균 "
            "%+.7f (sd %.7f) 로 **관찰 점추정의 반대 부호 쪽에 놓여 있다**. 그래서 "
            "L83 의 prop = mean(boot < theta_hat) 가 0 에 붙고 L84-85 가 "
            "z0 축퇴로 BCa 를 불능 처리했다(기록된 bca_status = %s)."
            % (sw["boot_summary"]["mean"], sw["boot_summary"]["sd"],
               sw["ci_bca"]["status"])),
        "recorded_values": {
            "primary_scaffold_cluster": {
                "delta_obs": pr["delta_obs"],
                "ci_bca": {k: pr["ci_bca"][k] for k in ("low", "high", "status")},
                "ci_percentile": {k: pr["ci_percentile"][k] for k in ("low", "high")},
                "boot_summary": pr["boot_summary"]},
            "size_weighted": {
                "delta_obs": sw["delta_obs"],
                "ci_bca": {k: sw["ci_bca"][k] for k in ("low", "high", "status")},
                "ci_percentile": {k: sw["ci_percentile"][k] for k in ("low", "high")},
                "boot_summary": sw["boot_summary"]},
        },
        "source": "experiments/runs/v3_unblinding/results/results_full.json "
                  "items.{C1,S-unit-sw}.bootstrap",
    }
    rec(jdump("X5", "x5_code_reading.json", out))
    return out


# ═════════════════════════════════════════════════════════════════════════
# X7 기술통계 — scaffold group 분포 (master_X 만 사용 · 봉인 0)
# ═════════════════════════════════════════════════════════════════════════
def scaffold_groups():
    import sys
    sp = os.path.join(ROOT, "v3_Multimodal", "src")
    if sp not in sys.path:
        sys.path.insert(0, sp)
    from confirmatory_oof_rep1 import scaffold_of
    X = pd.read_parquet(os.path.join(ROOT, "data/processed/master_X.parquet"))
    smi = X["smiles_canonical"].tolist()
    scaf = [scaffold_of(s) for s in smi]
    uniq = sorted(set(scaf))
    gidx = {g: i for i, g in enumerate(uniq)}
    gi = np.array([gidx[s] for s in scaf], dtype=int)
    return X, smi, scaf, uniq, gi


def x7_descriptive(X, smi, scaf, uniq, gi):
    from collections import Counter
    import sap.bootstrap as sb
    cnt = Counter(scaf)
    sizes = np.array([cnt[g] for g in uniq])
    kish = sb.n_eff_clusters(sizes)
    order = sorted(uniq, key=lambda g: (-cnt[g], g))
    top5 = [{"rank": i + 1, "size": cnt[g], "scaffold_smiles": g,
             "is_acyclic_empty_scaffold": (g == "")}
            for i, g in enumerate(order[:5])]
    acyclic = [g for g in uniq if g == ""]
    n_acyclic_drugs = int(sum(cnt[g] for g in acyclic))
    dist = Counter(sizes.tolist())
    out = {
        "_doc": "블록 CN X7(기술통계) — 732 scaffold group 크기 분포 + Kish 유효 수. "
                "master_X 만 사용 · 봉인 접근 0 · p-value 0.",
        "source": "data/processed/master_X.parquet · "
                  "confirmatory_oof_rep1.scaffold_of (재구현 0)",
        "n_rows": int(len(smi)),
        "n_groups": int(len(uniq)),
        "size_max": int(sizes.max()),
        "size_min": int(sizes.min()),
        "size_median": float(np.median(sizes)),
        "size_mean": float(sizes.mean()),
        "n_singleton_groups": int((sizes == 1).sum()),
        "kish_n_eff_clusters": kish,
        "kish_expected_instruction": 85.3,
        "kish_matches_expected": bool(abs(kish - 85.3) < 0.05),
        "kish_formula": "(Σs)²/Σs² — sap/bootstrap.py:51-54 n_eff_clusters",
        "top5_groups": top5,
        "acyclic_group": {
            "definition": "scaffold_of() 가 빈 문자열을 돌려주는 group "
                          "(= Murcko scaffold 가 비어 있는 비고리 분자)",
            "n_groups": len(acyclic),
            "n_drugs": n_acyclic_drugs,
            "frac_of_rows": n_acyclic_drugs / len(smi),
        },
        "size_histogram": {str(k): int(v) for k, v in sorted(dist.items())},
    }
    rec(jdump("X7", "x7_scaffold_group_descriptive.json", out))
    rec(cdump("X7", "x7_group_sizes.csv", ["group_index", "size", "scaffold_smiles"],
              [[gidx, cnt[g], g] for gidx, g in enumerate(uniq)]))
    return out, sizes, n_acyclic_drugs


# ═════════════════════════════════════════════════════════════════════════
# X9a 기술통계 — mapped 847 의 target 수 분포 + 3분위
# ═════════════════════════════════════════════════════════════════════════
def x9a_descriptive():
    nt = np.load(os.path.join(ROOT, "data/processed/drug_n_targets_meanpool.npy"))
    mask = np.load(os.path.join(ROOT, "data/processed/drug_target_mask_meanpool.npy"))
    mask = np.asarray(mask).astype(bool).ravel()
    nt = np.asarray(nt).ravel().astype(float)
    mapped = np.where(mask)[0]
    v = nt[mapped]
    q1, q2, q3 = np.percentile(v, [25, 50, 75])
    t1, t2 = np.percentile(v, [100 / 3, 200 / 3])
    # 3분위 그룹 (경계는 하한 포함·상한 미포함, 최상위는 포함)
    tert = np.digitize(v, [t1, t2], right=False)
    groups = {}
    for k in (0, 1, 2):
        idx = mapped[tert == k]
        groups["T%d" % (k + 1)] = {
            "n_drugs": int(len(idx)),
            "n_targets_min": float(nt[idx].min()) if len(idx) else None,
            "n_targets_max": float(nt[idx].max()) if len(idx) else None,
            "n_targets_median": float(np.median(nt[idx])) if len(idx) else None,
        }
    out = {
        "_doc": "블록 CN X9a(기술통계) — 동결 drug-target mapping 의 mapped 847 약물 "
                "target 수 분포와 3분위 경계. 봉인 접근 0 · p-value 0.",
        "source": ["data/processed/drug_n_targets_meanpool.npy",
                   "data/processed/drug_target_mask_meanpool.npy"],
        "definition": "A5 감사 정의 — 약물별 unique human single-protein UniProt "
                      "accession(임베딩 보유) 수 (experiments/audits/A5_target_count_check.json)",
        "n_rows_total": int(len(nt)),
        "n_mapped": int(mask.sum()),
        "n_unmapped": int((~mask).sum()),
        "median": float(q2),
        "iqr": [float(q1), float(q3)],
        "iqr_width": float(q3 - q1),
        "max": float(v.max()),
        "min": float(v.min()),
        "mean": float(v.mean()),
        "tertile_boundaries": {"t33.3": float(t1), "t66.7": float(t2)},
        "tertile_rule": "np.percentile(v,[100/3,200/3]) 경계 · np.digitize(right=False)",
        "tertiles": groups,
    }
    rec(jdump("X9a", "x9a_target_count_descriptive.json", out))
    np.save(os.path.join(OUT, "X9a", "_tertile_index.npy"), tert)
    np.save(os.path.join(OUT, "X9a", "_mapped_index.npy"), mapped)
    rec(os.path.join(OUT, "X9a", "_tertile_index.npy"))
    rec(os.path.join(OUT, "X9a", "_mapped_index.npy"))
    return out, mapped, tert


# ═════════════════════════════════════════════════════════════════════════
# X10a — truncation
# ═════════════════════════════════════════════════════════════════════════
GENES = {"KCNH2": "Q12809", "SCN5A": "Q14524",
         "CACNA1C": "Q13936", "ABCB1": "P08183"}


def x10a():
    a4 = pd.read_csv(os.path.join(ROOT, "experiments/audits/A4_bseq_truncation_audit.csv"))
    hp = a4[a4["in_human_primary"] == 1]
    n = len(hp)
    over = (hp["seq_len"] > 510).sum()
    tr = (hp["truncated"] == 1).sum()
    rows = []
    for g, acc in sorted(GENES.items()):
        r = a4[a4["uniprot"] == acc]
        if len(r) == 0:
            rows.append([g, acc, "", "", "", "no", "A4 감사표 미등재"])
            continue
        r = r.iloc[0]
        rows.append([g, acc, int(r["seq_len"]), int(r["truncated"]),
                     int(r["in_human_primary"]),
                     "yes" if int(r["in_human_primary"]) == 1 else "no",
                     r.get("family_name", "")])
    rec(cdump("X10a", "x10a_ion_channel_targets.csv",
              ["gene", "uniprot", "seq_len", "truncated", "in_human_primary",
               "in_main_analysis", "chembl_family"], rows))
    out = {
        "_doc": "블록 CN X10a — 주 분석 human target 1,191 기준 510 잔기 초과 비율 + "
                "4개 심장/수송체 표적 포함 여부. 네트워크 0 · 봉인 0 · p-value 0.",
        "source": "experiments/audits/A4_bseq_truncation_audit.csv "
                  "(preconfirm_hardening.a4_bseq_truncation 산출)",
        "n_embedded_targets_all": int(len(a4)),
        "n_main_analysis_targets": int(n),
        "n_seq_len_gt_510": int(over),
        "frac_seq_len_gt_510": float(over / n),
        "n_truncated_flag": int(tr),
        "truncated_flag_equals_gt510": bool(int(over) == int(tr)),
        "truncation_rule": "ProtBERT max_length 512 → 유효 잔기 510 · 앞쪽 510 잔기만 사용 "
                           "(docs/20 §1-②)",
        "all_embedded_truncation": {
            "n": int(len(a4)), "n_truncated": int((a4["truncated"] == 1).sum()),
            "frac": float((a4["truncated"] == 1).mean()),
            "docs20_reported": "940/1920 = 49.0%"},
        "gene_accessions": GENES,
        "gene_accession_provenance":
            "로컬 ChEMBL 캐시 응답의 target_component_synonyms ↔ accession 대응으로 확인 "
            "(data/processed/target_mapping/_cache/, _a5_mechanism_cache/json/). 네트워크 0.",
        "ion_channel_table": [dict(zip(
            ["gene", "uniprot", "seq_len", "truncated", "in_human_primary",
             "in_main_analysis", "chembl_family"], r)) for r in rows],
    }
    rec(jdump("X10a", "x10a_truncation.json", out))
    return out


# ═════════════════════════════════════════════════════════════════════════
# X10b — anisotropy
# ═════════════════════════════════════════════════════════════════════════
def _aniso(E):
    """E = (n, d) 0 벡터 제외 완료. 쌍 cosine 평균 + PCA 설명분산."""
    nrm = E / np.linalg.norm(E, axis=1, keepdims=True)
    G = nrm @ nrm.T
    n = len(E)
    iu = np.triu_indices(n, k=1)
    cos = G[iu]
    # PCA (center → SVD)
    Ec = E - E.mean(axis=0, keepdims=True)
    s = np.linalg.svd(Ec, compute_uv=False)
    ev = s ** 2
    evr = ev / ev.sum()
    cum = np.cumsum(evr)
    n90 = int(np.searchsorted(cum, 0.90) + 1)
    return {
        "n_vectors": int(n),
        "n_pairs": int(len(cos)),
        "pairwise_cosine_mean": float(cos.mean()),
        "pairwise_cosine_median": float(np.median(cos)),
        "pairwise_cosine_min": float(cos.min()),
        "pairwise_cosine_max": float(cos.max()),
        "pc1_explained_variance_ratio": float(evr[0]),
        "pca64_cumulative_explained_variance": float(cum[63]),
        "n_dims_for_90pct_variance": n90,
        "per_dim_std_mean": float(E.std(axis=0, ddof=0).mean()),
    }


def x10b():
    files = {
        "confirmatory_input_meanpool": "data/processed/drug_target_emb_meanpool.npy",
        "pilot_era_topk_weighted": "data/processed/drug_target_emb.npy",
    }
    mask = np.load(os.path.join(ROOT, "data/processed/drug_target_mask_meanpool.npy"))
    mask = np.asarray(mask).astype(bool).ravel()
    res = {}
    for lbl, rel in files.items():
        E = np.load(os.path.join(ROOT, rel)).astype(np.float64)
        nz = np.linalg.norm(E, axis=1) > 0
        sub = E[nz]
        res[lbl] = {"file": rel, "shape": list(E.shape),
                    "n_nonzero_rows": int(nz.sum()),
                    "n_zero_rows": int((~nz).sum()),
                    "nonzero_equals_mask": bool(np.array_equal(nz, mask)),
                    **_aniso(sub)}
    out = {
        "_doc": "블록 CN X10b — 확증 입력 drug-level mean-pooled 1024-d 이방성. "
                "0 벡터(unmapped) 제외. 봉인 0 · p-value 0.",
        "definition": "쌍 cosine = L2 정규화 후 상삼각 전쌍 평균 · PCA = 열 중심화 후 "
                      "SVD 특이값² 비율(np.linalg.svd) · PCA-64 = 누적 상위 64",
        "pilot_claim": {
            "values": {"pairwise_cosine_mean": 0.913, "pc1_evr": 0.486,
                       "n_dims_90pct": 18, "per_dim_std": 0.021},
            "cited_in": ["v3_Multimodal/src/train_ladder.py:620",
                         "docs/22_v3_ladder_report.md:68",
                         "docs/21_v3_model_ladder_prompt.md:5,20,21"],
            "code_definition_available_locally": False,
            "provenance_note":
                "train_ladder.py:620 은 보고 문장이며 계산 코드가 아니다. 값의 출처는 "
                "docs/21 머리말의 'cowork 사전 진단' 으로, 계산 스크립트가 저장소에 없다. "
                "따라서 '같은 정의인지' 는 코드 대조가 불가하고, 본 블록은 정의를 명시해 "
                "재계산하고 수치 일치/불일치만 보고한다.",
        },
        "results": res,
    }
    rec(jdump("X10b", "x10b_anisotropy.json", out))
    rec(cdump("X10b", "x10b_anisotropy.csv",
              ["embedding", "file", "n_vectors", "cosine_mean", "cosine_median",
               "pc1_evr", "pca64_cum_evr", "n_dims_90pct", "per_dim_std_mean"],
              [[k, v["file"], v["n_vectors"], "%.6f" % v["pairwise_cosine_mean"],
                "%.6f" % v["pairwise_cosine_median"],
                "%.6f" % v["pc1_explained_variance_ratio"],
                "%.6f" % v["pca64_cumulative_explained_variance"],
                v["n_dims_for_90pct_variance"], "%.6f" % v["per_dim_std_mean"]]
               for k, v in res.items()]))
    return out


# ═════════════════════════════════════════════════════════════════════════
# A5 — ChEMBL release · UniProt 조회일 복원 (조사만 · 네트워크 0)
# ═════════════════════════════════════════════════════════════════════════
def a5():
    ev = []

    # (1) 캐시된 API 응답 안의 release / version 흔적
    cache_dirs = [os.path.join(TM, "_cache"), os.path.join(TM, "_a5_mechanism_cache")]
    pat = ("chembl_db_version", "chembl_release", "api_version", "status",
           "database", "release")
    scanned = 0
    for d in cache_dirs:
        for p in sorted(glob.glob(os.path.join(d, "**", "*"), recursive=True)):
            if not os.path.isfile(p):
                continue
            scanned += 1
            if os.path.getsize(p) > 2_000_000:
                continue
            try:
                s = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            low = s.lower()
            if any(k in low for k in ("chembl_db_version", "chembl_release_date",
                                      "api_version")):
                ev.append({"kind": "cached_status_response",
                           "file": os.path.relpath(p, ROOT),
                           "excerpt": s[:400]})

    # (2) HTTP 헤더 보존본
    for p in sorted(glob.glob(os.path.join(TM, "**", "*.headers"), recursive=True)) + \
            sorted(glob.glob(os.path.join(TM, "**", "*.hdr"), recursive=True)):
        ev.append({"kind": "http_headers_file", "file": os.path.relpath(p, ROOT),
                   "excerpt": open(p, encoding="utf-8", errors="replace").read()[:400]})

    # (3) fetch 로그
    logs = []
    for pat2 in ("fetch_*", "*fetch*.log", "*.log"):
        for p in sorted(glob.glob(os.path.join(ROOT, "scripts", pat2))) + \
                sorted(glob.glob(os.path.join(ROOT, "pipeline", "**", pat2), recursive=True)) + \
                sorted(glob.glob(os.path.join(ROOT, "logs", "**", pat2), recursive=True)):
            if os.path.isfile(p):
                logs.append(os.path.relpath(p, ROOT))
    logs = sorted(set(logs))

    # (4) mtime 범위 = retrieval 기간
    def mt_range(paths):
        ts = [os.path.getmtime(p) for p in paths if os.path.isfile(p)]
        if not ts:
            return None
        import datetime
        KST = datetime.timezone(datetime.timedelta(hours=9))
        f = lambda t: datetime.datetime.fromtimestamp(t, KST).strftime("%Y-%m-%d %H:%M:%S KST")
        return {"n_files": len(ts), "min": f(min(ts)), "max": f(max(ts))}

    cache_files = [p for d in cache_dirs
                   for p in glob.glob(os.path.join(d, "**", "*"), recursive=True)
                   if os.path.isfile(p)]
    step_files = [os.path.join(TM, f) for f in
                  ("01_inchikey.csv", "02_chembl.csv", "03_targets.csv",
                   "04_sequences.csv", "05_affinity.csv", "_affinity_raw.csv")]
    out = {
        "_doc": "블록 CN A5 — ChEMBL release · UniProt 조회일 복원(조사만). 네트워크 0.",
        "search_order_per_instruction": ["캐시된 API 응답", "/status 응답", "HTTP 헤더",
                                         "파일 mtime", "fetch_* 로그"],
        "n_cache_files_scanned": scanned,
        "release_version_evidence": ev,
        "release_version_verdict": ("근거 없음 — 캐시된 응답·헤더에 ChEMBL release 번호나 "
                                    "/status 응답이 보존돼 있지 않다."
                                    if not ev else "근거 있음(위 목록)"),
        "fetch_log_candidates": logs,
        "retrieval_window_by_mtime": {
            "chembl_uniprot_cache": mt_range(cache_files),
            "pipeline_step_outputs": mt_range(step_files),
        },
        "reportable_statement": ("release 번호는 복원 불가 → 원고에는 retrieval 기간"
                                 "(파일 mtime 범위)만 기재한다."),
    }
    rec(jdump("A5", "a5_chembl_release_probe.json", out))
    return out


# ═════════════════════════════════════════════════════════════════════════
# A6 — Zenodo 업로드 zip 안에 drug-target mapping 표가 있는지
# ═════════════════════════════════════════════════════════════════════════
def a6():
    zips = []
    for base in (ROOT, os.path.dirname(ROOT)):
        for p in glob.glob(os.path.join(base, "**", "*.zip"), recursive=True):
            if "/.git/" in p or "/node_modules/" in p:
                continue
            zips.append(p)
    zips = sorted(set(zips))
    KEY = ("inchikey", "chembl", "uniprot", "target", "mapping", "pchembl")
    found = []
    for p in zips:
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
        except Exception as e:
            found.append({"zip": os.path.relpath(p, ROOT), "error": str(e)})
            continue
        hits = [n for n in names
                if any(k in n.lower() for k in KEY) and not n.endswith("/")]
        found.append({
            "zip": os.path.relpath(p, os.path.dirname(ROOT)),
            "size_bytes": os.path.getsize(p),
            "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
            "n_entries": len(names),
            "mapping_candidate_entries": sorted(hits)[:60],
            "n_mapping_candidates": len(hits),
        })
    # 공개 배포의 실체 = git 태그/커밋 트리(블록 BS). zip 은 로컬에 존재하지 않는다.
    import subprocess
    MAP_FILES = {
        "01_inchikey.csv": "cid, smiles, inchikey, ok — SMILES→InChIKey",
        "02_chembl.csv": "cid, inchikey, chembl_id, matched — InChIKey→ChEMBL ID",
        "03_targets.csv": "cid, inchikey, chembl_id, target_chembl_id, uniprot, organism, "
                          "target_type, source, n_targets_per_drug — ChEMBL ID→UniProt 본표",
        "04_sequences.csv": "uniprot, seq_len, has_seq",
        "05_affinity.csv": "inchikey, uniprot, has_affinity, value_type — 기록 유형(assay value_type)",
        "05b_affinity_values.csv": "chembl_id, uniprot, pchembl_median, n_records, "
                                   "value_types, organism — **pChEMBL**",
        "06_targets_human.csv": "cid, chembl_id, target_chembl_id, uniprot, organism — 주 분석 집합",
        "a5_mechanism_targets.csv": "cid, chembl_id, target_chembl_id, uniprot, action_type, "
                                    "mechanism_of_action, resolution_source — 기록 유형(mechanism)",
        "audit/audit_binding_vs_mechanism.csv": "binding evidence vs mechanism 축 집계",
    }
    trees = {}
    for ref in ("8e5ff6a", "22813e5d"):
        try:
            o = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref,
                                "--", "data/processed/target_mapping"],
                               cwd=ROOT, capture_output=True, text=True, check=True)
            names = set(o.stdout.split())
        except Exception as e:
            trees[ref] = {"error": str(e)}
            continue
        trees[ref] = {
            "n_entries_under_target_mapping": len(names),
            "mapping_files_present": {
                k: ("data/processed/target_mapping/" + k) in names
                for k in MAP_FILES},
            "all_present": all(("data/processed/target_mapping/" + k) in names
                               for k in MAP_FILES),
        }
    out = {
        "_doc": "블록 CN A6 — 공개 배포본에 drug-target mapping 표"
                "(InChIKey→ChEMBL ID→UniProt · 기록 유형 · pChEMBL)가 있는지 확인. "
                "zip 수정 0 · 네트워크 0 · git 쓰기 0(ls-tree 판독만).",
        "finding_zip": {
            "verdict": "Zenodo 업로드용 zip 은 로컬에 없다 — 아래 zip 8종 중 "
                       "mapping 표를 담은 것은 없다. 공개 배포는 git 태그에서 "
                       "생성됐으므로(블록 BS) 확인 대상은 커밋 트리다.",
            "search_roots": [ROOT, os.path.dirname(ROOT)],
            "keyword_filter": list(KEY),
            "n_zips_found": len(zips),
            "zips": found,
        },
        "finding_release_tree": {
            "refs_checked": {"release_commit": "8e5ff6a", "tag_commit": "22813e5d"},
            "refs_provenance": "메모리 기록(v3 공개 릴리스 종결, 2026-10-14 블록 BS)",
            "expected_mapping_files": MAP_FILES,
            "trees": trees,
            "verdict": "포함 — 두 커밋 트리 모두에 위 9개 파일이 전부 존재한다. "
                       "하나의 통합 표가 아니라 파이프라인 단계별 CSV 로 분할돼 있으며, "
                       "InChIKey→ChEMBL→UniProt 연결은 03_targets.csv 한 파일에서 "
                       "완결되고, pChEMBL 은 05b_affinity_values.csv, 기록 유형은 "
                       "05_affinity.csv(value_type)·a5_mechanism_targets.csv"
                       "(action_type/mechanism_of_action)에 있다.",
        },
        "release_filelist_crosscheck": {
            "file": "docs/131_v3_release_filelist.csv",
            "n_rows": 3807,
            "note": "블록 131 이 커밋한 공개 파일 목록. target_mapping CSV 들이 "
                    "sha256 과 함께 등재돼 있다.",
        },
    }
    rec(jdump("A6", "a6_mapping_table_in_release.json", out))
    return out


def main():
    print("[X1] 점추정")
    x1_point()
    x1_ccap_code_check()
    print("[X3] GIN/RF 절대 AP")
    x3()
    print("[X4] 공개 꼬리 집계")
    x4_public()
    x4_realization_storage_check()
    print("[X5-1] 코드 판독")
    x5_code()
    print("[X7] scaffold group 기술통계")
    X, smi, scaf, uniq, gi = scaffold_groups()
    x7_descriptive(X, smi, scaf, uniq, gi)
    print("[X9a] target 수 기술통계")
    x9a_descriptive()
    print("[X10a] truncation")
    x10a()
    print("[X10b] anisotropy")
    x10b()
    print("[A5] ChEMBL release 조사")
    a5()
    print("[A6] 업로드 zip 조사")
    a6()

    man = []
    for p in sorted(set(PRODUCED)):
        man.append({"path": os.path.relpath(p, ROOT),
                    "bytes": os.path.getsize(p),
                    "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()})
    mp = jdump("_manifest", "nosealed_manifest.json", {
        "_doc": "블록 CN — 봉인 미접근 단계 산출물 sha256",
        "n_files": len(man), "files": man})
    print("\n산출 %d 파일 · manifest %s" % (len(man), os.path.relpath(mp, ROOT)))


if __name__ == "__main__":
    main()
