#!/usr/bin/env python3
"""freeze.py — SAP 동결 드라이버 (docs/41 §8·§10).

synthetic dry-run으로 각 연산자를 검증 → 확증 데이터 미접근 코드 스캔(AST) → 모듈별 sha256·파라미터·
seed·패키지버전·검증 로그를 `experiments/sap/manifest.json`에 기록 = **SAP 동결**.

검증
  metrics   macro AP 정의(undefined-AP 제외 회계) sanity + sklearn 정의 일치
  consensus A8 방법A 수치 일치(build_consensus == 산술평균; 단일 반복=자기 자신)
  bootstrap A7 실행·CI 유한·제외율 기록(units 3종)
  signflip  A6 calibration audit — (i) zero-effect p==1.0, (ii) fair-coin 배정 p≈uniform
  null      A9 보존 assert(bijection·target embedding 공유·degree/incidence) + family 고정규칙 + p_emp 공식
  decision  A11 진리표(RQ2/RQ3/RQ4/Holm/BH-FDR/TOST)
  unseen    A10 4분류·canonicalize·sequence-novelty 보수적 bin
  redaction emit_sign 도메인·zero 임계

⛔ 무결성: 확증 split·OOF·master_X/Y 일절 미접근(입력 = synthetic 뿐). 네트워크 0.
실행: .venv/bin/python3 v3_Multimodal/src/sap/freeze.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import numpy as np
import scipy
import sklearn
from sklearn.metrics import average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))     # .../v3_Multimodal/src/sap
SRC = os.path.dirname(HERE)                            # .../v3_Multimodal/src
ROOT = os.path.abspath(os.path.join(SRC, "..", ".."))
sys.path.insert(0, SRC)

from sap import (metrics, consensus, bootstrap, signflip, decision,  # noqa: E402
                 null_generator, unseen_target, redaction, synthetic)

OUT_DIR = os.path.join(ROOT, "experiments", "sap")
os.makedirs(OUT_DIR, exist_ok=True)
CONFIG = os.path.join(ROOT, "v3_Multimodal", "config", "ladder_freeze.json")

KST = timezone(timedelta(hours=9))
MODULE_FILES = ["__init__.py", "metrics.py", "redaction.py", "consensus.py", "bootstrap.py",
                "signflip.py", "decision.py", "null_generator.py", "unseen_target.py",
                "synthetic.py", "freeze.py"]

_LOG = []


def logln(m):
    line = f"{datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')} | {m}"
    print(line, flush=True)
    _LOG.append(line)


def native(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else None   # NaN/inf(예: not_estimable CI) → null(유효 JSON)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, dict):
        return {k: native(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [native(v) for v in o]
    return o


def sha256_file(path):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return h


# ═══════════════════════════════════════════════════════════════════════════
# 검증 (synthetic dry-run)
# ═══════════════════════════════════════════════════════════════════════════
def validate_metrics():
    logln("[검증] metrics — macro AP 정의(undefined-AP 회계) + sklearn 일치")
    rng = np.random.default_rng(1)
    y = synthetic.make_labels(rng, 80, 6)
    P = rng.random((80, 6))
    r = metrics.macro_ap(y, P)
    # sklearn 직접 평균과 일치(양성>0 열만)
    aps = [average_precision_score(y[:, j], P[:, j]) for j in range(6) if y[:, j].sum() > 0]
    match = abs(r["macro_ap"] - float(np.mean(aps))) < 1e-12
    # undefined-AP: 한 열을 전부 0으로 → 제외 카운트 +1
    y2 = y.copy(); y2[:, 0] = 0
    r2 = metrics.macro_ap(y2, P)
    excl_ok = (r2["n_excluded_undefined"] == 1)
    ok = bool(match and excl_ok and 0.0 <= r["macro_ap"] <= 1.0)
    assert ok, f"[metrics] 실패 match={match} excl_ok={excl_ok}"
    logln(f"[검증] metrics PASS (sklearn 일치={match}, undefined 제외={r2['n_excluded_undefined']})")
    return {"sklearn_mean_match": match, "undefined_excluded_when_zero_positive": excl_ok,
            "macro_ap_in_unit_interval": True, "pass": ok, "definition": metrics.MACRO_AP_DEF}


def validate_consensus():
    logln("[검증] consensus — A8 방법A 산술평균 일치")
    reps, y, elig = synthetic.make_consensus_repeats(seed=2, R=3)
    c = consensus.build_consensus(reps)
    manual = np.mean(np.stack(reps, axis=0), axis=0)
    mean_match = bool(np.allclose(c, manual, atol=0))
    single = consensus.build_consensus([reps[0]])
    single_match = bool(np.array_equal(single, reps[0]))
    rep_ap = consensus.repeat_macro_aps(reps, y, metrics.macro_ap, elig)
    three = (len(rep_ap["per_repeat_macro_ap"]) == 3)
    ok = bool(mean_match and single_match and three)
    assert ok, f"[consensus] mean_match={mean_match} single={single_match} three={three}"
    logln(f"[검증] consensus PASS (평균 일치={mean_match}, 단일반복=자기자신={single_match}, 반복 macroAP 3개={three})")
    return {"method": consensus.CONSENSUS_METHOD, "arithmetic_mean_match": mean_match,
            "single_repeat_identity": single_match, "per_repeat_count": 3, "pass": ok}


def validate_bootstrap():
    logln("[검증] bootstrap — A7 실행·CI 유한(units 3종) + A5 진단필드 + A1 not_estimable")
    cM1b, cM2b, y, sg, elig = synthetic.make_predictions(seed=3)
    res = {}
    for unit in ("scaffold_cluster", "drug", "size_weighted"):
        r = bootstrap.paired_scaffold_bootstrap(cM1b, cM2b, y, sg, elig, B=800, seed=7, unit=unit)
        finite = np.isfinite([r["delta_obs"], r["ci_bca"]["low"], r["ci_bca"]["high"],
                              r["ci_percentile"]["low"], r["ci_percentile"]["high"]]).all()
        ordered = r["ci_percentile"]["low"] <= r["ci_percentile"]["high"]
        # A1: 효과-있는 fixture에서 BCa 성공 → ci_primary estimable(= BCa 값).
        prim = r["ci_primary"]
        prim_ok = (prim["status"] == "estimable" and prim["bca_status"] == "bca"
                   and abs(prim["low"] - r["ci_bca"]["low"]) < 1e-12)
        # A5: 진단 필드 존재.
        a5_ok = all(k in r for k in ("pt_diagnostics", "bca_diagnostics", "fixed_intersection_sensitivity"))
        res[unit] = {"delta_obs": r["delta_obs"], "ci_bca": r["ci_bca"],
                     "ci_percentile": r["ci_percentile"], "ci_primary": prim,
                     "primary_ci_method": r["primary_ci_method"],
                     "n_eff_clusters": r["n_eff_clusters"],
                     "undefined_ap_exclusion": r["undefined_ap_exclusion"],
                     "pt_diagnostics": r["pt_diagnostics"], "bca_diagnostics": r["bca_diagnostics"],
                     "fixed_intersection_sensitivity": r["fixed_intersection_sensitivity"],
                     "finite": bool(finite), "ci_ordered": bool(ordered),
                     "ci_primary_estimable_ok": bool(prim_ok), "a5_diag_fields_ok": bool(a5_ok)}
        assert finite and ordered, f"[bootstrap:{unit}] CI 비유한/역전"
        assert prim_ok, f"[bootstrap:{unit}] ci_primary estimable 규칙 위반: {prim}"
        assert a5_ok, f"[bootstrap:{unit}] A5 진단 필드 누락"

    # A1 강제 실패 케이스: cM1b==cM2b(make_identical) → 모든 Δ=0 → BCa z0 degenerate → not_estimable.
    ci, _, yi, sgi, eli = synthetic.make_identical(seed=4)
    rf = bootstrap.paired_scaffold_bootstrap(ci, ci, yi, sgi, eli, B=400, seed=7)
    a1_ok = (rf["ci_primary"]["status"] == "not_estimable"
             and np.isnan(rf["ci_primary"]["low"]) and np.isnan(rf["ci_primary"]["high"])
             and str(rf["ci_primary"]["bca_status"]).startswith("bca_failed"))
    assert a1_ok, f"[bootstrap A1] not_estimable 전파 실패: {rf['ci_primary']}"
    # not_estimable ci_primary → rq2 성공 불가(A1 게이트 확인).
    rq2_ne = decision.rq2_decision(rf["ci_primary"], 0.001, 0.04)
    assert rq2_ne["success"] is False and rq2_ne.get("ci_estimable") is False, \
        f"[bootstrap A1→decision] not_estimable인데 rq2 success={rq2_ne['success']}"
    logln(f"[검증] bootstrap PASS (primary_ci={bootstrap.PRIMARY_CI_METHOD}; "
          f"scaffold Δ_obs={res['scaffold_cluster']['delta_obs']:.4f}, "
          f"BCa=[{res['scaffold_cluster']['ci_bca']['low']:.4f},{res['scaffold_cluster']['ci_bca']['high']:.4f}]; "
          f"A1 not_estimable={rf['ci_primary']['bca_status']} → rq2 success={rq2_ne['success']})")
    return {"units": res, "estimand": bootstrap.ESTIMAND, "primary_ci_method": bootstrap.PRIMARY_CI_METHOD,
            "frozen_B_confirmatory": 10000, "dry_run_B": 800,
            "a1_not_estimable_case": {"ci_primary": rf["ci_primary"], "rq2_success": rq2_ne["success"],
                                      "rq2_reason": rq2_ne.get("reason")},
            "not_estimable_rule": ("BCa status≠'bca'(z0/accel degenerate·유효B<2·jackknife undefined) → "
                                   "ci_primary=not_estimable(NaN); rq2/rq3/tost 성공 불가; percentile 대체 금지"),
            "pass": True}


def validate_signflip():
    logln("[검증] signflip — A6 calibration audit (zero-effect p==1 · fair-coin p≈uniform)")
    # (i) zero-effect
    cM1b, _, y, sg, elig = synthetic.make_identical(seed=4)
    ze = signflip.audit_zero_effect(cM1b, y, sg, elig, B=1500, seed=11)
    assert ze["pass"], f"[signflip] zero-effect audit 실패: p={ze['p']}"
    logln(f"[검증]   (i) zero-effect: p={ze['p']:.4f} (기대 1.0) PASS")
    # (ii) uniform
    def gen(rseed):
        return synthetic.make_exchangeable(seed=rseed, N=120, K=12, G=30)
    uni = signflip.audit_uniform(gen, R=200, B=160, seed=5)
    assert uni["pass"], (f"[signflip] uniform audit 실패: mean_p={uni['mean_p']:.3f} "
                         f"KS={uni['ks_vs_uniform']:.3f}")
    logln(f"[검증]   (ii) uniform: mean_p={uni['mean_p']:.3f} KS={uni['ks_vs_uniform']:.3f} "
          f"frac≤0.05={uni['frac_le']['le_0.05']:.3f} PASS")
    return {"test_statistic": signflip.TEST_STATISTIC, "H0": signflip.H0,
            "zero_effect_audit": ze, "uniform_audit": uni,
            "frozen_B_confirmatory": 10000, "pass": True}


def validate_null():
    logln("[검증] null_generator — A9 보존 assert·family 고정규칙·p_emp 공식")
    g = synthetic.make_target_graph(seed=6)
    # global
    gmap = null_generator.build_global_permutation(g["unique_targets"], seed=13)
    gpres = null_generator.assert_preservation(g["cid2targets"], g["target_emb"], gmap, g["cid_order"])
    # family-constrained
    fmap, frep = null_generator.build_family_permutation(g["targets_by_family"], seed=14)
    fpres = null_generator.assert_preservation(g["cid2targets"], g["target_emb"], fmap, g["cid_order"])
    # apply → 동일 target 공유 검증(두 약물이 공유하는 target의 재배치 embedding 동일)
    emb = null_generator.apply_target_embedding_permutation(g["cid2targets"], g["target_emb"], gmap, g["cid_order"])
    share_ok = _check_target_share(g, gmap)
    # family 고정규칙: |family|≤2 는 원위치 고정(mapping[t]==t)
    fixed_rule_ok = _check_family_fixed(g, fmap)
    # 보존 guard가 non-bijection을 잡는지(음성 통제)
    guard_ok = _check_bijection_guard(g)
    # p_emp 공식 + A4 MC standard error
    ep = null_generator.empirical_p(observed_stat=1.0, null_stats=[0.5, 0.9, 1.0, 1.2])
    p_formula_ok = abs(ep["p_emp"] - (1 + 2) / (4 + 1)) < 1e-12  # #{≥1.0}=2 (1.0,1.2)
    p_val = ep["p_emp"]                                          # 0.6
    mc_se_ok = abs(ep["mc_se"] - (p_val * (1 - p_val) / 4) ** 0.5) < 1e-12 and ("mc_se" in ep)
    # A4 상수 동결
    b_const_ok = (null_generator.NULL_B == 1000 and null_generator.NULL_RF_COMMON_SEED == 42
                  and ep["expected_B"] == null_generator.NULL_B)
    # A4 family report: 고정/교환 target 수·incidence 로깅
    fam_report_ok = (frep["n_fixed_targets"] + frep["n_exchangeable_targets"] == frep["n_targets"]
                     and "fixed_target_frac" in frep)
    inc = null_generator.null_incidence_report(g["cid2targets"], g["cid_order"], g["unique_targets"])
    inc_ok = (inc["n_targets"] == len(g["unique_targets"]) and 0.0 <= inc["incidence_ratio"] <= 1.0)

    ok = bool(share_ok and fixed_rule_ok and guard_ok and p_formula_ok
              and mc_se_ok and b_const_ok and fam_report_ok and inc_ok)
    assert ok, (f"[null] share={share_ok} fixed={fixed_rule_ok} guard={guard_ok} pemp={p_formula_ok} "
                f"mcse={mc_se_ok} bconst={b_const_ok} famrep={fam_report_ok} inc={inc_ok}")
    logln(f"[검증] null_generator PASS (global bijection·공유={share_ok}, family 고정 "
          f"{frep['n_fixed_families_singleton_or_size2']}개/{frep['n_fixed_targets']}target, "
          f"NULL_B={null_generator.NULL_B}, MC_SE={ep['mc_se']:.4f}, incidence={inc['incidence_ratio']:.3f})")
    return {"preserved": null_generator.PRESERVED, "pca_rf_refit_scope": null_generator.PCA_RF_REFIT_SCOPE,
            "global_preservation": gpres, "family_preservation": fpres, "family_report": frep,
            "incidence_report": inc,
            "target_embedding_shared": share_ok, "family_fixed_rule_ok": fixed_rule_ok,
            "bijection_guard_catches_bad_null": guard_ok, "p_emp_formula_ok": p_formula_ok,
            "mc_se_ok": mc_se_ok, "null_b_const_ok": b_const_ok, "family_report_ok": fam_report_ok,
            "incidence_report_ok": inc_ok,
            "p_emp_formula": "(1 + #{T_b ≥ T_obs}) / (B+1)",
            "NULL_B": null_generator.NULL_B, "NULL_RF_COMMON_SEED": null_generator.NULL_RF_COMMON_SEED,
            "global_permutation": "full permutation (fixed point 허용, derangement 아님)",
            "pass_global_and_family_rule": "global·family-constrained 둘 다 p_emp<α 요구", "pass": ok}


def _check_target_share(g, mapping):
    # 두 약물이 공유하는 target t → apply 후 그 target의 재배치 embedding이 동일해야(target별 공유)
    per_target_vec = {}
    for c in g["cid_order"]:
        for t in g["cid2targets"][c]:
            v = g["target_emb"][mapping[t]]
            if t in per_target_vec and not np.allclose(per_target_vec[t], v):
                return False
            per_target_vec[t] = v
    return True


def _check_family_fixed(g, fmap):
    for fam, members in g["targets_by_family"].items():
        if len(members) <= 2:
            for t in members:
                if fmap[t] != t:
                    return False
        # |family|≥3 은 family 내로만(원소 집합 보존)
        else:
            srcs = {fmap[t] for t in members}
            if srcs != set(members):
                return False
    return True


def _check_bijection_guard(g):
    # 고의로 non-bijection mapping(두 target이 같은 source) → assert_preservation이 AssertionError
    tgts = g["unique_targets"]
    bad = {t: t for t in tgts}
    bad[tgts[1]] = tgts[0]  # tgts[0],tgts[1] 모두 source=tgts[0] → bijection 파괴
    try:
        null_generator.assert_preservation(g["cid2targets"], g["target_emb"], bad, g["cid_order"])
        return False  # 잡지 못하면 guard 실패
    except AssertionError:
        return True


def validate_decision():
    logln("[검증] decision — A11 진리표 (RQ2/RQ3/RQ4/Holm/BH-FDR/TOST)")
    cases = {}
    # RQ2
    rq2 = {
        "all_pass": decision.rq2_decision((0.02, 0.06), 0.001, 0.04),
        "ci_low_le0": decision.rq2_decision((-0.01, 0.05), 0.001, 0.04),
        "p_ge_alpha": decision.rq2_decision((0.02, 0.06), 0.2, 0.04),
        "sesoi_fail": decision.rq2_decision((0.001, 0.006), 0.001, 0.005),
    }
    exp_rq2 = {"all_pass": True, "ci_low_le0": False, "p_ge_alpha": False, "sesoi_fail": False}
    rq2_ok = all(rq2[k]["success"] == v for k, v in exp_rq2.items())
    # RQ3
    rq3 = {
        "both_pass": decision.rq3_decision((0.01, 0.05), 0.01, (0.02, 0.06), 0.02),
        "pid_fail": decision.rq3_decision((-0.01, 0.05), 0.01, (0.02, 0.06), 0.02),
    }
    rq3_ok = (rq3["both_pass"]["success"] is True and rq3["pid_fail"]["success"] is False)
    # RQ4
    rq4 = {
        "both_pass": decision.rq4_decision(0.001, 0.01),
        "family_fail": decision.rq4_decision(0.001, 0.2),
    }
    rq4_ok = (rq4["both_pass"]["success"] is True and rq4["family_fail"]["success"] is False)
    # A1 not_estimable 게이트: primary CI 불능이면 CI 하한>0라도 성공 불가.
    ne_ci = {"low": 0.02, "high": 0.06, "status": "not_estimable", "bca_status": "bca_failed_z0_degenerate"}
    rq2_ne = decision.rq2_decision(ne_ci, 0.001, 0.04)          # 조건상 통과처럼 보이나 not_estimable
    rq3_ne = decision.rq3_decision(ne_ci, 0.01, (0.02, 0.06), 0.02)
    tost_ne = decision.tost_equivalence(float("nan"), float("nan"), 0.04, ci_status="not_estimable")["label"]
    a1_ok = (rq2_ne["success"] is False and rq2_ne.get("ci_estimable") is False
             and rq3_ne["success"] is False and tost_ne == "Not-estimable")

    # A2 Holm: family 크기 **7 고정**, 6개만 주고 7번째(RQ-int) 결측→1.0 채움.
    holm = decision.holm({
        "M2b-P-ID": 0.001, "M2b-P-FAM": 0.004, "M2b-realloc_null": 0.011,
        "M2b-M0": 0.02, "M2b-RF_tuned": 0.03, "RFseq-RF": 0.5,   # "RQ-int" 결측 → 1.0
    })
    holm_exp = {"M2b-P-ID": 0.007, "M2b-P-FAM": 0.024, "M2b-realloc_null": 0.055,
                "M2b-M0": 0.08, "M2b-RF_tuned": 0.09, "RFseq-RF": 1.0, "RQ-int": 1.0}
    holm_ok = (holm["family_size"] == 7 and holm["undefined_filled"]["RQ-int"] is True
               and all(abs(holm["adjusted_p"][k] - v) < 1e-12 for k, v in holm_exp.items())
               and holm["reject"] == {"M2b-P-ID": True, "M2b-P-FAM": True, "M2b-realloc_null": False,
                                      "M2b-M0": False, "M2b-RF_tuned": False, "RFseq-RF": False,
                                      "RQ-int": False})
    # A2 negative: family 밖 라벨 → assert.
    try:
        decision.holm({"M2b-P-ID": 0.01, "bogus": 0.02}); holm_guard_ok = False
    except AssertionError:
        holm_guard_ok = True

    # A3 pt_eligibility 경계(label·scaffold만; 결과-독립).
    y_e, sg_e, exp_elig = synthetic.make_eligibility_fixture()
    elig = decision.pt_eligibility(y_e, sg_e)
    elig_ok = (elig["eligible_pt"] == exp_elig and elig["min_positive"] == 10
               and elig["min_pos_clusters"] == 3
               and elig["per_pt"][1]["n_positive_scaffold_clusters"] == 2   # col1: cluster<3
               and elig["per_pt"][2]["n_positive"] == 8)                    # col2: pos<10

    # BH-FDR (eligible PT만 입력받는다는 계약 하 알고리즘 검증)
    bh = decision.bh_fdr({"a": 0.01, "b": 0.02, "c": 0.2})
    bh_exp = {"a": 0.03, "b": 0.03, "c": 0.2}
    bh_ok = all(abs(bh["adjusted_p"][k] - v) < 1e-12 for k, v in bh_exp.items()) and \
        bh["reject"] == {"a": True, "b": True, "c": False}
    # TOST (estimable 경로)
    tost = {
        "positive": decision.tost_equivalence(0.02, 0.06, 0.04)["label"],
        "equivalent": decision.tost_equivalence(-0.005, 0.008, 0.001)["label"],
        "inconclusive": decision.tost_equivalence(-0.03, 0.05, 0.01)["label"],
        "not_estimable": tost_ne,
    }
    tost_ok = tost == {"positive": "Positive", "equivalent": "Equivalent",
                       "inconclusive": "Inconclusive", "not_estimable": "Not-estimable"}

    cases = {"rq2": {k: v["success"] for k, v in rq2.items()},
             "rq3": {k: v["success"] for k, v in rq3.items()},
             "rq4": {k: v["success"] for k, v in rq4.items()},
             "a1_not_estimable": {"rq2": rq2_ne["success"], "rq3": rq3_ne["success"], "tost": tost_ne},
             "holm_family_size": holm["family_size"], "holm_adjusted_p": holm["adjusted_p"],
             "holm_reject": holm["reject"], "holm_undefined_filled": holm["undefined_filled"],
             "pt_eligibility": {"eligible_pt": elig["eligible_pt"], "n_eligible": elig["n_eligible"]},
             "bh_adjusted_p": bh["adjusted_p"], "bh_reject": bh["reject"], "tost": tost}
    ok = bool(rq2_ok and rq3_ok and rq4_ok and a1_ok and holm_ok and holm_guard_ok
              and elig_ok and bh_ok and tost_ok)
    assert ok, (f"[decision] rq2={rq2_ok} rq3={rq3_ok} rq4={rq4_ok} a1={a1_ok} "
                f"holm={holm_ok} holm_guard={holm_guard_ok} elig={elig_ok} bh={bh_ok} tost={tost_ok}")
    logln(f"[검증] decision PASS (RQ2={rq2_ok} RQ3={rq3_ok} RQ4={rq4_ok} A1_not_estimable={a1_ok} "
          f"Holm7={holm_ok} eligibility={elig_ok} BH={bh_ok} TOST={tost_ok})")
    return {"SESOI": decision.SESOI, "ALPHA": decision.ALPHA, "primary_target": decision.PRIMARY_TARGET,
            "holm_family": decision.HOLM_FAMILY, "holm_family_size_fixed": 7,
            "holm_undefined_fill": decision.HOLM_UNDEFINED_FILL,
            "multiplicity_manifest": decision.MULTIPLICITY_MANIFEST,
            "pt_eligibility_constants": {"PT_MIN_POSITIVE": decision.PT_MIN_POSITIVE,
                                         "PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS":
                                             decision.PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS},
            "truth_table": cases,
            "rq2_ok": rq2_ok, "rq3_ok": rq3_ok, "rq4_ok": rq4_ok, "a1_not_estimable_ok": a1_ok,
            "holm_ok": holm_ok, "holm_guard_ok": holm_guard_ok, "pt_eligibility_ok": elig_ok,
            "bh_ok": bh_ok, "tost_ok": tost_ok, "pass": ok}


def validate_unseen():
    logln("[검증] unseen_target — A10 4분류·canonicalize·sequence-novelty 보수적 bin")
    fx = synthetic.make_unseen_fixture()
    T = fx["T_train"]; drugs = fx["drugs"]; seqid = fx["seqid_max"]
    cls = {
        "d_all_seen": unseen_target.classify_drug(drugs["d_all_seen"], T),
        "d_all_unseen": unseen_target.classify_drug(drugs["d_all_unseen"], T),
        "d_mixed": unseen_target.classify_drug(drugs["d_mixed"], T),
        "d_no_target": unseen_target.classify_drug(drugs["d_no_target"], T),
        "d_isoform_canon": unseen_target.classify_drug(unseen_target.canonicalize_set(drugs["d_isoform"]), T),
    }
    cls_exp = {"d_all_seen": "all-seen", "d_all_unseen": "all-unseen", "d_mixed": "mixed",
               "d_no_target": "no-target", "d_isoform_canon": "all-seen"}
    cls_ok = (cls == cls_exp)
    canon_ok = (unseen_target.canonicalize_accession("P12345-2") == "P12345")
    # sequence-novelty 보수적 bin
    strat = {name: unseen_target.drug_sequence_stratum(td, T, seqid)
             for name, td in fx["unseen_drugs"].items()}
    strat["d_all_seen"] = unseen_target.drug_sequence_stratum(drugs["d_all_seen"], T, seqid)
    strat["d_no_target"] = unseen_target.drug_sequence_stratum(drugs["d_no_target"], T, seqid)
    strat["d_all_unseen_conservative"] = unseen_target.drug_sequence_stratum(drugs["d_all_unseen"], T, seqid)
    strat_exp = {"u_ge90": "unseen_ge90", "u_70_90": "unseen_70_90", "u_40_70": "unseen_40_70",
                 "u_lt40": "unseen_lt40", "d_all_seen": "seen", "d_no_target": "no-target",
                 "d_all_unseen_conservative": "unseen_ge90"}  # max(95,30)=95 → ge90 (보수적)
    strat_ok = (strat == strat_exp)
    ok = bool(cls_ok and canon_ok and strat_ok)
    assert ok, f"[unseen] cls={cls_ok} canon={canon_ok} strat={strat_ok} | cls={cls} strat={strat}"
    logln(f"[검증] unseen_target PASS (4분류={cls_ok}, canonicalize={canon_ok}, novelty bin={strat_ok})")
    return {"classify": cls, "classify_ok": cls_ok, "canonicalize_ok": canon_ok,
            "sequence_stratum": strat, "stratum_ok": strat_ok,
            "boundaries": unseen_target.SEQID_BOUNDARIES, "strata": unseen_target.SEQID_STRATA,
            "identity_method": unseen_target.IDENTITY_METHOD, "min_support": unseen_target.MIN_SUPPORT,
            "inference_mode": unseen_target.INFERENCE_MODE, "pass": ok}


def validate_redaction():
    logln("[검증] redaction — emit_sign 도메인·zero 임계")
    a = redaction.emit_sign(0.04) == "positive"
    b = redaction.emit_sign(-0.04) == "negative"
    c = redaction.emit_sign(5e-7) == "zero"      # |.|<1e-6
    try:
        redaction.emit_sign(float("nan")); nan_ok = False
    except ValueError:
        nan_ok = True
    ok = bool(a and b and c and nan_ok)
    assert ok, f"[redaction] pos={a} neg={b} zero={c} nan={nan_ok}"
    logln(f"[검증] redaction PASS (positive/negative/zero + NaN 거부)")
    return {"zero_tol": redaction.ZERO_TOL, "emit_sign_domain": ["positive", "zero", "negative"],
            "nan_rejected": nan_ok, "pass": ok}


# ═══════════════════════════════════════════════════════════════════════════
# 확증 데이터 미접근 스캔 (AST — 하드 증명)
# ═══════════════════════════════════════════════════════════════════════════
FORBIDDEN_IMPORTS = {"ladder_confirmatory", "preconfirm_hardening", "target_pipeline",
                     "train_ladder", "prep_features", "coverage_mapping"}
# pandas/numpy 데이터 로드 계열만 금지. json.load(sealed 파일 read)·loads 등은 확증 데이터 아님 → 제외.
DATA_LOAD_ATTRS = {"read_parquet", "read_csv", "read_table", "load_frozen", "loadtxt", "genfromtxt"}
NP_LOAD_ROOTS = {"np", "numpy"}   # np.load/numpy.load 만 금지(json.load 제외)
FORBIDDEN_PATH_LITERALS = ["data/processed", "data/raw", "master_X", "master_Y",
                           "scaffold_split.json", "_meanpool.npy", "confirmatory",
                           "oof_M1b", "oof_M2b", "target_mapping"]


def _call_desc(node):
    """Call 노드 → (last_attr, root_name). root_name = 속성 체인 최상위 Name(예: json.load → ('load','json'))."""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id, None
    if isinstance(f, ast.Attribute):
        root = f.value
        while isinstance(root, ast.Attribute):
            root = root.value
        root_name = root.id if isinstance(root, ast.Name) else None
        return f.attr, root_name
    return None, None


def _is_data_load(node):
    """확증 데이터 로드 호출인가? read_parquet/read_csv/load_frozen/loadtxt/genfromtxt 또는 np.load."""
    attr, root = _call_desc(node)
    if attr in DATA_LOAD_ATTRS:
        return attr
    if attr == "load" and root in NP_LOAD_ROOTS:   # np.load (json.load 제외)
        return f"{root}.load"
    return None


def code_scan():
    logln("[스캔] 확증 데이터 미접근 (AST: import·data-load call·open 인자 리터럴)")
    per_file = {}
    all_ok = True
    for fn in MODULE_FILES:
        path = os.path.join(HERE, fn)
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src, filename=fn)
        imports = set()
        bad_calls = []
        open_data_literals = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imports.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                dl = _is_data_load(node)
                if dl:
                    # pd.read_parquet / np.load 등 = 확증 데이터 로드 경로 → 금지
                    bad_calls.append(dl)
                attr, _root = _call_desc(node)
                if attr == "open":
                    # open()의 문자열 리터럴 인자가 확증 데이터 경로면 금지(redaction의 run_dir join은 리터럴 아님)
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            low = arg.value.lower()
                            if any(tok.lower() in low for tok in FORBIDDEN_PATH_LITERALS):
                                open_data_literals.append(arg.value)
        forbidden_imp = sorted(imports & FORBIDDEN_IMPORTS)
        file_ok = (not forbidden_imp) and (not bad_calls) and (not open_data_literals)
        all_ok = all_ok and file_ok
        per_file[fn] = {
            "forbidden_imports": forbidden_imp,
            "data_load_calls": sorted(set(bad_calls)),
            "open_with_data_literal": open_data_literals,
            "third_party_imports": sorted(i for i in imports if i not in {"__future__"}),
            "ok": file_ok,
        }
    # 텍스트상 확증-데이터 명칭은 '미접근 선언' docstring에만 존재(코드 경로 아님) — AST가 하드 증명.
    logln(f"[스캔] AST 미접근 증명 = {all_ok} (금지 import 0·data-load call 0·open 데이터리터럴 0)")
    assert all_ok, f"[스캔] 확증 데이터 접근 코드 발견: {per_file}"
    return {
        "method": "AST walk over sap/*.py — import·call·open-literal 검사",
        "forbidden_imports_checked": sorted(FORBIDDEN_IMPORTS),
        "data_load_calls_checked": sorted(DATA_LOAD_ATTRS) + ["np.load"],
        "forbidden_path_literals_checked": FORBIDDEN_PATH_LITERALS,
        "per_file": per_file,
        "no_confirmatory_data_access": all_ok,
        "note": ("확증 split(seed 201~205)·OOF·master_X/Y·scaffold_split·meanpool npy 를 import/load/open "
                 "하는 코드 경로 없음. docstring 내 해당 명칭은 '미접근 선언'일 뿐 실행 경로 아님(AST 증명)."),
    }


# ═══════════════════════════════════════════════════════════════════════════
def main():
    logln("=" * 80)
    logln("[SAP 재-동결] docs/41 A6~A11 + docs/43 amendment(A1~A6) — synthetic 재검증 → 코드 스캔 → sha256 재-hash")

    validation = {
        "metrics": validate_metrics(),
        "consensus_A8": validate_consensus(),
        "bootstrap_A7": validate_bootstrap(),
        "signflip_A6": validate_signflip(),
        "null_generator_A9": validate_null(),
        "decision_A11": validate_decision(),
        "unseen_target_A10": validate_unseen(),
        "redaction": validate_redaction(),
    }
    all_pass = all(v.get("pass", False) for v in validation.values())
    assert all_pass, "[SAP 동결] 검증 미통과 — 동결 금지"

    scan = code_scan()

    # 재-동결 amendment: 이전 manifest의 모듈 sha 회수(있으면) → before→after diff 기록.
    prev_module_sha = {}
    prev_path = os.path.join(OUT_DIR, "manifest.json")
    if os.path.exists(prev_path):
        try:
            prev = json.load(open(prev_path, encoding="utf-8"))
            prev_module_sha = {k: v.get("sha256") for k, v in prev.get("modules", {}).items()}
        except Exception:
            prev_module_sha = {}

    # 모듈 sha256 (before→after diff 포함)
    modules = {}
    n_changed = 0
    for fn in MODULE_FILES:
        p = os.path.join(HERE, fn)
        h = sha256_file(p)
        before = prev_module_sha.get(fn)
        changed = bool(before is not None and before != h)
        n_changed += int(changed)
        modules[fn] = {"sha256": h, "sha16": h[:16], "bytes": os.path.getsize(p),
                       "sha256_before": before, "changed_by_amendment": changed}

    # config 바인딩
    cfg_sha = sha256_file(CONFIG)
    cfg_bind = {"path": os.path.relpath(CONFIG, ROOT), "sha256": cfg_sha, "sha16": cfg_sha[:16],
                "expected_sha16_docs41": "b885585aefbabb32",
                "sha16_match": cfg_sha[:16] == "b885585aefbabb32",
                "primary_B_m1b_dim": 10, "sensitivity_B_m1b_pchembl_dim": 13,
                # A6(문구·ladder_freeze.json 정합): B_seq PCA fitting 모집단 참조.
                "b_seq_pca_population": ("train∩mapped per-drug mean-pool rows(약물당 1행, "
                                         "svd_solver=full, random_state=42)")}

    manifest = {
        "_doc": ("v3 SAP(A6~A11 + redaction) 동결 매니페스트 — docs/41 동결 + docs/43 재-동결 amendment(A1~A6). "
                 "확증 OOF 미조회 시점 동결(설계·가설·집계·성공기준 불변, 구현 자유도만 제거)."),
        "sap_version": "1.2",  # 1.0(docs/41) → 1.1(docs/43 amendment A1~A6)
        "frozen_at_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "basis": ["docs/30 §5~§9 (등록 설계·불변)", "docs/40 §2·§6 (2차 리뷰 필터링)", "docs/41 (SAP 스펙)",
                  "docs/42 (3차 리뷰 A버킷 triage)", "docs/43 (재-동결 amendment 스펙)"],
        "sap_amendment": {
            "amendment_id": "docs/43 A1~A6 (확증 조회 전 재-동결)",
            "confirmatory_accessed_at_amendment": False,
            "design_hypothesis_criteria_unchanged": True,
            "items": {
                "A1": "BCa 불능 → ci_primary=not_estimable(NaN); rq2/rq3/tost 성공 불가; percentile 대체 금지",
                "A2": "Holm family 크기 7 고정; 결측 p→1.0(드롭 금지); MULTIPLICITY_MANIFEST hash 포함",
                "A3": "PT별 BH-FDR eligibility=결과-독립 수치정의(양성≥10 AND 양성-scaffold-cluster≥3)",
                "A4": "NULL_B 정확값 동결(1000)·MC SE 반환·full permutation·common RF seed 42·결과-기반 상향 금지",
                "A5": "bootstrap undefined-PT 진단(min/median/max·undefined 비율·BCa accel/quantile)·고정교집합 sensitivity",
                "A6": "ESTIMAND(drug-weighted macro AP)·sign-flip prediction-swap caveat·metrics edge assert·B_seq PCA 모집단",
            },
            "module_sha_before": prev_module_sha,  # 이전(docs/41) 동결 sha → modules(아래)가 이후 sha
            "n_modules_changed": int(n_changed),
        },
        "primary_target": decision.PRIMARY_TARGET,
        "config_binding": cfg_bind,
        "frozen_parameters": {
            "consensus_A8": {"method": consensus.CONSENSUS_METHOD,
                             "average_target": "raw RF probability (calibration 후 아님)",
                             "rf_random_state_all_repeats": 42, "single_repeat": "그 자체 반환"},
            "bootstrap_A7": {"B": 10000, "primary_ci_method": bootstrap.PRIMARY_CI_METHOD,
                             "units": {"primary": "scaffold_cluster",
                                       "sensitivity": ["drug", "size_weighted"]},
                             "jackknife_unit_primary": "scaffold delete-one (약물 단위 혼용 금지)",
                             "undefined_ap_rule": "replicate test-positive 0 PT는 macro에서 제외(제외율 기록)",
                             "eligible_pt": "원 전체 평가셋 고정(§7 global 양성≥10 370 PT); replicate 재선정 금지",
                             "estimand": bootstrap.ESTIMAND,
                             "ci_primary_status_rule": (  # A1
                                 "ci_primary는 BCa 성공('bca')시에만 estimable. BCa 불능(z0/accel degenerate·"
                                 "유효 B<2·jackknife undefined) → not_estimable(NaN). percentile은 sensitivity로만 "
                                 "보고(ci_percentile), 성공판정에 절대 투입 금지."),
                             "a5_diagnostics": (  # A5(estimand 불변, 보고만)
                                 "pt_diagnostics(replicate당 포함PT min/median/max·PT별 undefined replicate 비율·"
                                 "≥1 PT 제외 replicate 비율), bca_diagnostics(acceleration finite·adjusted-quantile "
                                 "0/1 포화), fixed_intersection_sensitivity(고정교집합 PT macro Δ, primary 대체 아님)")},
            "signflip_A6": {"B": 10000, "test_statistic": signflip.TEST_STATISTIC, "two_sided": True,
                            "exchange_unit": "Bemis–Murcko scaffold group", "H0": signflip.H0,
                            "name_caveat": signflip.NAME_CAVEAT,  # A6(문구): prediction-swap test
                            "calibration_audit": "zero-effect p==1 · fair-coin p≈uniform (필수·프로토콜 불변)"},
            "null_A9": {"NULL_B": null_generator.NULL_B,  # A4: 정확값 동결("≥1000" 제거)
                        "B_note": "결과 조회 후 B 상향·조기중단·재시도 금지(selective precision); 한 값으로 잠금",
                        "mc_se": "empirical_p가 sqrt(p(1−p)/B) 반환(A4)",
                        "rf_seed": "42 (common random numbers, all permutations & repeats)",  # A4
                        "rf_seed_assert": "docs/36 runner가 전 permutation·전 반복 random_state=42 동일을 assert",
                        "preserved": null_generator.PRESERVED,
                        "exchange": "target identity ↔ embedding 대응만; 동일 target 공유",
                        "global_unit": "unique target",
                        "global_permutation": "full permutation (fixed point 허용, derangement 아님)",  # A4
                        "family_unit": ("family 내 unique target; |family|≤2 고정"
                                        "(가능 permutation ≤2!·서열 미파괴)"),
                        "logging": "eligible target 수·고정 target 수·incidence 비율(null_incidence_report·family_report)",
                        "pca_rf_refit_scope": null_generator.PCA_RF_REFIT_SCOPE,
                        "p_emp": "(1 + #{T_b ≥ T_obs}) / (B+1)",
                        "pass_rule": "global·family-constrained 둘 다 p_emp<α"},
            "decision_A11": {"SESOI": decision.SESOI, "ALPHA": decision.ALPHA,
                             "rq2": "IU: (1) CI하한>0 & (2) sign-flip p<α & (3) |Δ|≥SESOI",
                             "rq3": "(M2b−P-ID) 및 (M2b−P-FAM) 각각 (1)·(2) (max 금지)",
                             "rq4": "재배치 null global·family 둘 다 p_emp<α",
                             "not_estimable_rule": (  # A1
                                 "primary CI not_estimable(BCa 불능) → rq2/rq3/tost 성공 불가; percentile 대체 금지"),
                             "multiplicity": "① M2b−M1b 무보정; ②~⑧ Holm(family=7 고정); PT별 BH-FDR 별도",
                             "holm_family": decision.HOLM_FAMILY,
                             "holm_family_size_fixed": 7,  # A2
                             "holm_undefined_fill": decision.HOLM_UNDEFINED_FILL,  # A2: 결측 p→1.0(드롭 금지)
                             "multiplicity_manifest": decision.MULTIPLICITY_MANIFEST,  # A2
                             "pt_eligibility": {  # A3: 결과-독립 수치 정의
                                 "PT_MIN_POSITIVE": decision.PT_MIN_POSITIVE,
                                 "PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS": decision.PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS,
                                 "rule": "global 양성 ≥ PT_MIN_POSITIVE AND 양성-포함 scaffold cluster ≥ "
                                         "PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS (효과크기·p 무참조)"},
                             "M2b_RF_naming": "RF = tuned-RF baseline (primary RF-Morgan과 구분)",
                             "tost": "95%CI 기반 등가규칙(D2): Positive/Equivalent/Inconclusive/Not-estimable"},
            "unseen_A10": {"classes": ["all-seen", "all-unseen", "mixed", "no-target(별도)"],
                           "canonicalization": "isoform suffix 제거·secondary→primary·동일서열 대표 병합",
                           "seqid_boundaries": unseen_target.SEQID_BOUNDARIES,
                           "strata": unseen_target.SEQID_STRATA,
                           "identity_method": unseen_target.IDENTITY_METHOD,
                           "drug_aggregation": "보수적: all-unseen 且 s_drug=max_t s(t) 로 bin",
                           "min_support": unseen_target.MIN_SUPPORT,
                           "inference_mode": unseen_target.INFERENCE_MODE},
            "redaction": {"emit_sign_domain": ["positive", "zero", "negative"],
                          "zero_tol": redaction.ZERO_TOL,
                          "sealed_separation": "원시 AP·Δ크기·per-PT·per-fold·확률 = sealed 경로; 공개=sign만",
                          "access_logging": "sealed 최초 접근 시각·조회자 로깅"},
        },
        "modules": modules,
        "validation": validation,
        "code_scan": scan,
        "versions": {"python": sys.version.split()[0], "numpy": np.__version__,
                     "scipy": scipy.__version__, "sklearn": sklearn.__version__},
        "seeds": {"note": "모든 연산자 seed는 호출 인자(결정적). 확증 B·seed list는 frozen_parameters·docs/30 §8 준수.",
                  "dry_run_seeds": {"metrics": 1, "consensus": 2, "bootstrap": 7, "signflip_zero": 11,
                                    "signflip_uniform": 5, "null_global": 13, "null_family": 14}},
        "integrity": {
            "confirmatory_split_accessed": False,
            "confirmatory_split_generated": False,
            "confirmatory_oof_accessed": False,
            "master_XY_accessed": False,
            "inputs": "synthetic (np.random 시드 생성) 뿐",
            "network_calls": 0,
            "mock": "synthetic = SAP 검증 전용(확증 데이터 아님)",
            "no_confirmatory_data_access_ast_proven": scan["no_confirmatory_data_access"],
        },
        "all_validation_pass": all_pass,
        "reproduce": ".venv/bin/python3 v3_Multimodal/src/sap/freeze.py",
        "next": "docs/36 확증 OOF 반복1(seed 201) — 성공판정 함수는 3반복+null 완료 후에만 호출",
    }

    out_path = os.path.join(OUT_DIR, "manifest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(native(manifest), f, indent=2, ensure_ascii=False)
    logln(f"[재-동결] {os.path.relpath(out_path, ROOT)} 저장 (all_validation_pass={all_pass}, "
          f"sap_version={manifest['sap_version']}, 변경 모듈={n_changed})")
    logln(f"[재-동결] config sha16={cfg_bind['sha16']} (docs41 기대 일치={cfg_bind['sha16_match']}, primary B_m1b.dim=10)")
    logln("[SAP 재-동결] 완료 — docs/43 A1~A6 반영, 확증 split·OOF 미조회, 네트워크 0. docs/36 진입 게이트 충족.")
    logln("=" * 80)
    with open(os.path.join(OUT_DIR, "freeze.log"), "a", encoding="utf-8") as f:
        f.write("\n".join(_LOG) + "\n")
    return manifest


if __name__ == "__main__":
    main()
