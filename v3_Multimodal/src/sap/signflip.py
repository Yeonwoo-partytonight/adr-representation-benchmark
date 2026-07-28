"""signflip.py — A6: scaffold-group sign-flip randomization (docs/41 §3, 사전등록 §8).

검정통계량 = **관측 macro AP Δ 그 자체**(additive surrogate로 대체 금지 — bootstrap CI와 동일
estimand 보장). 교환 단위 = **Bemis–Murcko scaffold group**. 각 group에 대해 확률 1/2로 그 group에
속한 모든 약물 × 전체 PT의 M1b·M2b 예측 block을 **통째 교환**한다. 매 permutation마다 370 PT AP·
macro AP를 **처음부터 재계산**(비선형 지표)한다. 양측 p, B(≥10,000)·seed 고정.

귀무가설: "두 알고리즘의 예측 block이 scaffold 단위로 교환 가능"(conditional randomization;
**모델 재학습 미포함**임을 SAP·논문에 명시).

A6 명칭 caveat(동작 불변): 이 검정은 **scaffold-blocked paired prediction-swap test**이다 —
  고정 OOF 예측 block을 scaffold 단위로 교환하는 conditional exchangeability null이며,
  **contribution sign-flip(기여도 부호 뒤집기)이 아니고 모델 재학습을 포함하지 않는다.**
  논문·SAP에서 "distribution-free exact test of equal algorithm performance"로 표기 금지.

calibration audit(필수, synthetic — 프로토콜 불변, 실패 시 구현 수정)
  (i)  M1b=M2b 동일 예측 입력 → p ≈ 1   (audit_zero_effect)
  (ii) scaffold별 fair-coin 대칭 배정 → p 분포 ≈ uniform   (audit_uniform)

⚠️ 무결성: 입력 예측/라벨은 호출자 제공(확증 값은 확증 단계에서만). 확증 데이터 미로드 순수 함수.
"""
from __future__ import annotations

import numpy as np

from .metrics import macro_ap

__all__ = ["scaffold_signflip", "audit_zero_effect", "audit_uniform",
           "TEST_STATISTIC", "H0", "NAME_CAVEAT"]

TEST_STATISTIC = "관측 macro AP Δ 그 자체 (M2b − M1b); additive surrogate 대체 금지 = CI와 동일 estimand"
H0 = ("두 알고리즘의 예측 block이 scaffold group 단위로 교환 가능(conditional randomization). "
      "모델 재학습 미포함.")
# A6(동작 불변·문구): 명칭 caveat.
NAME_CAVEAT = ("scaffold-blocked paired prediction-swap test (contribution sign-flip 아님), "
               "conditional exchangeability null, 모델 재학습 미포함. "
               "'distribution-free exact test of equal algorithm performance' 표기 금지.")

# 양측 카운트의 float 동률 허용 tolerance(zero-effect에서 정확히 p=1이 되도록 = 판정 안정).
_EPS = 1e-12


def _macro(y, P, eligible_pt):
    return macro_ap(y, P, eligible_pt)["macro_ap"]


def _perm_deltas(cM1b, cM2b, y, scaffold_group, eligible_pt, B, seed):
    """B개 permuted Δ 생성 + 관측 Δ. (재사용: 검정·audit 공통)."""
    cM1b = np.asarray(cM1b, dtype=np.float64)
    cM2b = np.asarray(cM2b, dtype=np.float64)
    y = np.asarray(y)
    groups = np.asarray(scaffold_group)
    uniq = np.unique(groups)
    # group → row 위치(벡터화용 그룹 인덱스)
    gi_of_row = np.searchsorted(uniq, groups)
    n_groups = len(uniq)

    delta_obs = _macro(y, cM2b, eligible_pt) - _macro(y, cM1b, eligible_pt)

    rng = np.random.default_rng(seed)
    perm = np.empty(B, dtype=np.float64)
    for b in range(B):
        flip_group = rng.random(n_groups) < 0.5            # group별 fair coin
        swap_row = flip_group[gi_of_row]                    # (N,) 행 단위 교환 여부
        sr = swap_row[:, None]
        M1p = np.where(sr, cM2b, cM1b)                      # 교환 group은 arm 통째 교환
        M2p = np.where(sr, cM1b, cM2b)
        perm[b] = _macro(y, M2p, eligible_pt) - _macro(y, M1p, eligible_pt)
    return delta_obs, perm


def scaffold_signflip(cM1b, cM2b, y, scaffold_group, eligible_pt=None,
                      B=10000, seed=0, return_perm=False):
    """양측 sign-flip p. Returns dict: delta_obs, p_two_sided, B, seed, null_summary, [perm]."""
    delta_obs, perm = _perm_deltas(cM1b, cM2b, y, scaffold_group, eligible_pt, B, seed)
    count = int(np.sum(np.abs(perm) >= abs(delta_obs) - _EPS))     # 양측
    p = (1.0 + count) / (B + 1.0)
    out = {
        "test_statistic": TEST_STATISTIC,
        "H0": H0,
        "delta_obs": float(delta_obs),
        "p_two_sided": float(p),
        "B": int(B),
        "seed": int(seed),
        "exchange_unit": "Bemis–Murcko scaffold group",
        "null_summary": {"mean": float(np.mean(perm)), "sd": float(np.std(perm, ddof=1)),
                         "abs_ge_obs": count},
    }
    if return_perm:
        out["perm"] = perm  # sealed 경로 저장용(공개 금지)
    return out


# ── calibration audit (i): zero-effect → p ≈ 1 ──────────────────────────────
def audit_zero_effect(cM1b, y, scaffold_group, eligible_pt=None, B=2000, seed=0):
    """M1b=M2b 동일 예측 입력 → Δ_obs=0, 모든 permuted Δ=0 → p는 정확히 1.0 이어야 함."""
    res = scaffold_signflip(cM1b, cM1b, y, scaffold_group, eligible_pt, B=B, seed=seed)
    ok = abs(res["p_two_sided"] - 1.0) < 1e-9 and abs(res["delta_obs"]) < 1e-12
    return {"p": res["p_two_sided"], "delta_obs": res["delta_obs"], "pass": bool(ok),
            "expected": "p == 1.0 (동일 예측 → 모든 permutation Δ=0)"}


# ── calibration audit (ii): fair-coin 대칭 배정 → p 분포 ≈ uniform ────────────
def _ks_uniform(pvals):
    """단측 아닌 양측 KS 통계량 vs Uniform(0,1)."""
    p = np.sort(np.asarray(pvals, dtype=float))
    n = len(p)
    i = np.arange(1, n + 1)
    d_plus = np.max(i / n - p)
    d_minus = np.max(p - (i - 1) / n)
    return float(max(d_plus, d_minus))


def audit_uniform(make_exchangeable, R=300, B=300, seed=0,
                  mean_tol=0.10, ks_tol=0.16):
    """H0가 참인 exchangeable 데이터에서 sign-flip p가 ≈ uniform 인지 검정.

    make_exchangeable(realization_seed) -> (cM1b, cM2b, y, scaffold_group, eligible_pt)
      각 realization은 scaffold별 fair-coin으로 두 arm을 배정 → 교환 가능(H0 참).
    PASS ⟺ mean(p) ∈ [0.5−mean_tol, 0.5+mean_tol] AND KS(vs Uniform) < ks_tol."""
    ps = np.empty(R, dtype=float)
    for r in range(R):
        cM1b, cM2b, y, sg, elig = make_exchangeable(seed * 100003 + r)
        res = scaffold_signflip(cM1b, cM2b, y, sg, elig, B=B, seed=seed * 7 + r)
        ps[r] = res["p_two_sided"]
    mean_p = float(np.mean(ps))
    ks = _ks_uniform(ps)
    frac = {f"le_{t}": float(np.mean(ps <= t)) for t in (0.05, 0.10, 0.25, 0.50)}
    ok = abs(mean_p - 0.5) <= mean_tol and ks < ks_tol
    return {"R": int(R), "B": int(B), "mean_p": mean_p, "ks_vs_uniform": ks,
            "frac_le": frac, "pass": bool(ok),
            "expected": "mean(p)≈0.5 · KS<tol (fair-coin 배정은 교환가능 → p uniform)"}
