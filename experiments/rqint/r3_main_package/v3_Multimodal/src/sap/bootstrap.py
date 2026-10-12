"""bootstrap.py — A7: paired scaffold-cluster bootstrap (docs/41 §2, 사전등록 §8).

Primary contrast = consensus OOF `Δ(macro AP M2b − macro AP M1b)`의 신뢰구간을,
**scaffold cluster 단위 복원추출(paired)** 로 추정한다.

절차(고정)
  1. scaffold cluster 단위 복원추출 — 같은 cluster가 두 번 뽑히면 그 drug 행들도 두 번 복제.
  2. eligible PT = **원 전체 평가셋에서 고정**(§7: global 양성 ≥10인 370 PT). replicate 내 재선정 금지.
  3. 각 replicate에서 M1b·M2b의 **PT별 AP 재계산 → macro 평균**, Δ_b = macroAP_M2b − macroAP_M1b
     (동일 draw 공유 = paired).
  4. undefined-AP 규칙(고정): replicate에서 test-positive 0 PT는 그 replicate macro 평균에서 제외,
     제외율 기록(분모 변동 허용 방식 하나로 고정).
  5. CI 방법 = **사전 하나로 고정**: PRIMARY_CI_METHOD = "BCa"(percentile은 동시 산출·sensitivity).
     BCa jackknife = **scaffold delete-one 단위**(primary/size_weighted; 약물 단위 혼용 금지).
  6. B(≥10,000)·seed 고정. estimand = **conditional OOF evaluation**(고정 consensus 예측 위 평가).

primary/sensitivity 분리(unit)
  - "scaffold_cluster" : primary — cluster 균등 복원추출.
  - "drug"             : sensitivity — 약물 행 균등 복원추출(clustering 무시; jackknife=drug delete-one).
  - "size_weighted"    : sensitivity — cluster를 크기 비례 확률로 복원추출(jackknife=scaffold delete-one).

⚠️ 무결성: 입력 consensus_M1b/consensus_M2b/y는 호출자가 넘긴 배열(확증 값은 확증 단계에서만 채워짐).
   본 모듈은 확증 split·OOF·master_X/Y를 로드하지 않는 순수 함수다.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

from .metrics import macro_ap

__all__ = ["paired_scaffold_bootstrap", "PRIMARY_CI_METHOD", "ESTIMAND", "n_eff_clusters"]

# 사전고정 CI 방법(SAP 동결 — 결과 조회 전 확정). percentile은 동시 산출하되 판정은 BCa로.
# A1(★): BCa 불능 시 ci_primary=not_estimable(퍼센타일 무단 대체 금지). percentile은 sensitivity로만 보고,
#        성공판정에 절대 투입하지 않는다(decision.py가 status 게이트로 강제).
PRIMARY_CI_METHOD = "BCa"
ESTIMAND = ("conditional OOF evaluation — 고정된 consensus OOF 예측 위에서의 macro AP Δ. "
            "모델 재학습 미포함(예측을 고정한 조건부 평가). "
            "A6: cluster 복원추출→멤버 약물행 복제→pooled AP = drug-weighted macro AP.")


def _cluster_index(scaffold_group):
    """scaffold group 라벨 배열 → (unique 라벨, cluster별 행 인덱스 리스트)."""
    groups = np.asarray(scaffold_group)
    uniq = np.unique(groups)
    rows_by_cluster = [np.where(groups == g)[0] for g in uniq]
    return uniq, rows_by_cluster


def n_eff_clusters(sizes):
    """effective number of clusters = (Σs)²/Σs² (Kish)."""
    s = np.asarray(sizes, dtype=float)
    return float((s.sum() ** 2) / (s ** 2).sum()) if s.sum() > 0 else 0.0


def _delta_on_rows(consensus_M1b, consensus_M2b, y, rows, eligible_pt):
    """행 인덱스 집합에서 Δ = macroAP(M2b) − macroAP(M1b) + 제외율."""
    y_s = y[rows]
    m1 = macro_ap(y_s, consensus_M1b[rows], eligible_pt)
    m2 = macro_ap(y_s, consensus_M2b[rows], eligible_pt)
    return m2["macro_ap"] - m1["macro_ap"], m1, m2


def _bca_ci(boot, theta_hat, jack, alpha=0.05):
    """BCa 95% CI. jack = jackknife θ 값 배열(재표본 단위 delete-one).

    A1(★): BCa 불능 시 **percentile 대체 금지** — (low,high)=NaN + 사유 status만 반환한다.
    percentile CI는 호출자가 별도로(ci_percentile) sensitivity 보고용으로 산출한다.
    반환 dict: {low, high, status, acceleration, acceleration_finite, z0,
               adj_q_low, adj_q_high, quantile_saturated}."""
    def _fail(status):
        return {"low": float("nan"), "high": float("nan"), "status": status,
                "acceleration": float("nan"), "acceleration_finite": False, "z0": float("nan"),
                "adj_q_low": float("nan"), "adj_q_high": float("nan"), "quantile_saturated": False}

    boot = np.asarray(boot, dtype=float)
    boot = boot[~np.isnan(boot)]
    B = len(boot)
    if B < 2:
        return _fail("bca_failed_too_few_B")
    # bias-correction z0
    prop = float(np.mean(boot < theta_hat))
    if prop <= 0.0 or prop >= 1.0:
        return _fail("bca_failed_z0_degenerate")     # z0=±inf → 불능(percentile 대체 안 함)
    z0 = norm.ppf(prop)
    # acceleration a (jackknife) — undefined(NaN) jackknife 발생 시 BCa 불능(A1)
    jack = np.asarray(jack, dtype=float)
    if jack.size < 2 or np.isnan(jack).any():
        return _fail("bca_failed_jackknife_undefined")
    jbar = jack.mean()
    num = np.sum((jbar - jack) ** 3)
    den = 6.0 * (np.sum((jbar - jack) ** 2) ** 1.5)
    a = num / den if den != 0 else 0.0               # den=0(모든 jack 동일) → a=0(정상 BCa)
    if not np.isfinite(a):
        return _fail("bca_failed_accel_degenerate")
    z_lo, z_hi = norm.ppf(alpha / 2), norm.ppf(1 - alpha / 2)

    def adj(z):
        denom = 1 - a * (z0 + z)
        if denom == 0:
            return None
        return norm.cdf(z0 + (z0 + z) / denom)

    a1, a2 = adj(z_lo), adj(z_hi)
    if a1 is None or a2 is None:
        return _fail("bca_failed_accel_degenerate")
    saturated = bool(a1 <= 0.0 or a1 >= 1.0 or a2 <= 0.0 or a2 >= 1.0)  # A5: 조정분위 0/1 포화
    lo = float(np.percentile(boot, 100 * a1))
    hi = float(np.percentile(boot, 100 * a2))
    return {"low": lo, "high": hi, "status": "bca", "acceleration": float(a),
            "acceleration_finite": True, "z0": float(z0),
            "adj_q_low": float(a1), "adj_q_high": float(a2), "quantile_saturated": saturated}


def paired_scaffold_bootstrap(consensus_M1b, consensus_M2b, y, scaffold_group,
                              eligible_pt=None, B=10000, seed=0,
                              unit="scaffold_cluster", alpha=0.05,
                              return_boot=False):
    """paired scaffold-cluster bootstrap → Δ의 95% CI(BCa primary + percentile).

    Returns dict: delta_obs, ci_bca(low,high,status,...), ci_percentile(low,high),
    ci_primary(=BCa, status∈{estimable,not_estimable}), B, seed, unit, n_clusters, n_eff_clusters,
    undefined_ap_exclusion, pt_diagnostics(A5), bca_diagnostics(A5),
    fixed_intersection_sensitivity(A5·optional), boot_summary(mean/sd), [boot(옵션·sealed용)].

    A1: ci_primary는 BCa가 성공("bca")일 때만 estimable. 실패 시 low/high=NaN·status="not_estimable"
        (percentile 값을 primary에 넣지 않음 — decision.py가 status로 성공판정을 차단)."""
    consensus_M1b = np.asarray(consensus_M1b, dtype=np.float64)
    consensus_M2b = np.asarray(consensus_M2b, dtype=np.float64)
    y = np.asarray(y)
    N = y.shape[0]
    for a_ in (consensus_M1b, consensus_M2b):
        if a_.shape != y.shape:
            raise ValueError("consensus/y shape 불일치")
    uniq, rows_by_cluster = _cluster_index(scaffold_group)
    n_clusters = len(uniq)
    sizes = np.array([len(r) for r in rows_by_cluster])

    # 관측 Δ (전체 데이터)
    all_rows = np.arange(N)
    delta_obs, _, _ = _delta_on_rows(consensus_M1b, consensus_M2b, y, all_rows, eligible_pt)

    # A5 진단용 누적기: cols_arr = 고정 eligible PT 열(replicate 내 재선정 금지).
    cols_arr = np.arange(y.shape[1]) if eligible_pt is None else np.asarray(eligible_pt, dtype=int)
    n_elig = len(cols_arr)
    pt_undef_count = np.zeros(n_elig, dtype=np.int64)     # PT별 undefined replicate 수
    included_pt_counts = np.empty(B, dtype=np.int64)      # replicate당 포함(정의) PT 수

    rng = np.random.default_rng(seed)
    boot = np.empty(B, dtype=np.float64)
    excl_fracs = np.empty(B, dtype=np.float64)

    def _accumulate(b, m1):
        dm = np.asarray(m1["defined_mask"], dtype=bool)
        included_pt_counts[b] = int(dm.sum())
        pt_undef_count[~dm] += 1

    if unit == "drug":
        for b in range(B):
            rows = rng.integers(0, N, size=N)  # 약물 행 균등 복원추출
            d, m1, m2 = _delta_on_rows(consensus_M1b, consensus_M2b, y, rows, eligible_pt)
            boot[b] = d
            excl_fracs[b] = max(m1["excl_frac"], m2["excl_frac"])
            _accumulate(b, m1)
    else:
        if unit == "size_weighted":
            probs = sizes / sizes.sum()
        elif unit == "scaffold_cluster":
            probs = None  # 균등
        else:
            raise ValueError(f"unknown unit: {unit}")
        idx_range = np.arange(n_clusters)
        for b in range(B):
            picks = rng.choice(idx_range, size=n_clusters, replace=True, p=probs)
            rows = np.concatenate([rows_by_cluster[i] for i in picks])
            d, m1, m2 = _delta_on_rows(consensus_M1b, consensus_M2b, y, rows, eligible_pt)
            boot[b] = d
            excl_fracs[b] = max(m1["excl_frac"], m2["excl_frac"])
            _accumulate(b, m1)

    # jackknife (BCa acceleration) — 재표본 단위 delete-one
    if unit == "drug":
        # drug delete-one (표본 크다면 비쌈 → 본 단위는 sensitivity; jackknife도 drug 단위로 일관)
        jack = np.empty(N, dtype=np.float64)
        for i in range(N):
            rows = np.delete(all_rows, i)
            jack[i], _, _ = _delta_on_rows(consensus_M1b, consensus_M2b, y, rows, eligible_pt)
    else:
        # scaffold delete-one (primary/size_weighted 공통; 약물 단위 혼용 금지)
        jack = np.empty(n_clusters, dtype=np.float64)
        for i in range(n_clusters):
            keep = np.concatenate([rows_by_cluster[k] for k in range(n_clusters) if k != i])
            jack[i], _, _ = _delta_on_rows(consensus_M1b, consensus_M2b, y, keep, eligible_pt)

    bca = _bca_ci(boot, delta_obs, jack, alpha=alpha)
    bca_status = bca["status"]
    bca_ok = (bca_status == "bca")
    pct_lo, pct_hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])

    # A1: PRIMARY_CI_METHOD="BCa" 고정 → ci_primary는 BCa 성공시에만 estimable.
    #     BCa 불능 시 not_estimable(NaN) — percentile 값을 primary에 절대 넣지 않는다.
    assert PRIMARY_CI_METHOD == "BCa", "SAP 동결: primary CI 방법은 BCa로 고정(변경 금지)"
    if bca_ok:
        ci_primary = {"low": bca["low"], "high": bca["high"],
                      "status": "estimable", "bca_status": bca_status}
    else:
        ci_primary = {"low": float("nan"), "high": float("nan"),
                      "status": "not_estimable", "bca_status": bca_status}

    # A5: PT별 undefined 진단(estimand 불변, 보고만).
    pt_undef_frac = pt_undef_count / float(B)
    n_repl_excl_any = int(np.sum(included_pt_counts < n_elig))
    # 고정 교집합 PT = 모든 replicate에서 정의된 eligible PT → optional sensitivity macro Δ.
    always_defined = cols_arr[pt_undef_count == 0]
    if len(always_defined) > 0:
        fi_m1 = macro_ap(y, consensus_M1b, always_defined)
        fi_m2 = macro_ap(y, consensus_M2b, always_defined)
        fi_delta = float(fi_m2["macro_ap"] - fi_m1["macro_ap"])
    else:
        fi_delta = float("nan")

    out = {
        "estimand": ESTIMAND,
        "unit": unit,
        "delta_obs": float(delta_obs),
        "B": int(B),
        "seed": int(seed),
        "alpha": float(alpha),
        "n_clusters": int(n_clusters),
        "n_eff_clusters": n_eff_clusters(sizes),
        "cluster_size": {"median": float(np.median(sizes)), "max": int(sizes.max()),
                         "min": int(sizes.min())},
        "ci_bca": {"low": bca["low"], "high": bca["high"], "status": bca_status,
                   "jackknife_unit": "drug delete-one" if unit == "drug" else "scaffold delete-one"},
        "ci_percentile": {"low": float(pct_lo), "high": float(pct_hi),
                          "note": "sensitivity 보고용 — 성공판정에 사용하지 않음(A1)"},
        "primary_ci_method": PRIMARY_CI_METHOD,
        "ci_primary": ci_primary,
        "boot_summary": {"mean": float(np.mean(boot)), "sd": float(np.std(boot, ddof=1))},
        "undefined_ap_exclusion": {"mean_frac": float(np.mean(excl_fracs)),
                                   "max_frac": float(np.max(excl_fracs)),
                                   "rule": "replicate test-positive 0 PT는 그 replicate macro에서 제외(분모 변동 허용)"},
        "pt_diagnostics": {                                       # A5
            "n_eligible_pt": int(n_elig),
            "included_pt_per_replicate": {"min": int(included_pt_counts.min()),
                                          "median": float(np.median(included_pt_counts)),
                                          "max": int(included_pt_counts.max())},
            "pt_undefined_replicate_frac": {"min": float(pt_undef_frac.min()),
                                            "median": float(np.median(pt_undef_frac)),
                                            "max": float(pt_undef_frac.max())},
            "n_pt_ever_undefined": int(np.sum(pt_undef_count > 0)),
            "frac_replicates_excluding_ge1_pt": float(n_repl_excl_any / B),
        },
        "bca_diagnostics": {                                      # A5
            "acceleration": bca["acceleration"],
            "acceleration_finite": bool(bca["acceleration_finite"]),
            "z0": bca["z0"],
            "adj_quantile_low": bca["adj_q_low"],
            "adj_quantile_high": bca["adj_q_high"],
            "adj_quantile_saturated_01": bool(bca["quantile_saturated"]),
        },
        "fixed_intersection_sensitivity": {                       # A5 optional(primary 대체 아님)
            "n_pt_always_defined": int(len(always_defined)),
            "macro_delta_fixed_intersection": fi_delta,
            "note": "모든 replicate에서 정의된 PT로만 계산한 Δ — variable-domain 안정성 점검용. "
                    "primary는 고정 370 eligible PT 불변.",
        },
    }
    if return_boot:
        out["boot"] = boot  # sealed 경로 저장용(공개 금지)
    return out
