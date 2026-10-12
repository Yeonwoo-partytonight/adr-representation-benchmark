"""rqint.py — RQ-int(⑧) 상호작용 검정: shared-coin scaffold-blocked arm-swap test.

⛔ 무결성(sap 패키지 원칙 1·2 계승): 본 모듈은 확증용 split·confirmatory OOF·master_X/master_Y·
   scaffold_split·_sealed 를 **생성/조회/import 하지 않는다.** 모든 입력은 **호출자가 넘긴 배열**이며,
   본 모듈은 결정적 순수 함수다. 감사에 쓰인 수치는 전부 합성 fixture 산출물이다.

★ 명칭 caveat (signflip.NAME_CAVEAT 와 동일 규격 — docs/89 AC-3-1)
  · 이 검정은 **shared-coin scaffold-blocked arm-swap interaction test** 이다.
  · 부과되는 귀무 **H0^B** = "각 family 내부에서 arm 라벨(M1b/M2b)이 scaffold group 단위로
    교환 가능" = Δ_RF = 0 **이고** Δ_GIN = 0 (**강한 null**).
  · 검정 대상 가설 **H0^int: Δ_RF = Δ_GIN** (공통값이 0 이 아니어도 됨 = **약한 null**).
  · 두 null 은 **일치하지 않는다**(H0^B ⊊ H0^int).
    → **"약한 null 에 대한 정확검정"으로 표기 금지.** 약한 null 하 1종오류 통제는
      **R1 캘리브레이션 감사(C0~C3)로 실증**되어야 하며, 그 전에는 주장하지 않는다.
  · **모델 재학습 미포함** — 고정 OOF 예측의 conditional randomization.

설계 정본: `docs/55b` §5 후보 B(sharp null 형식) · `docs/84` §1 D3·D4·D5·D16 · `docs/89`(블록 AC).

집계 형식(D3)
  · repeat 축 = **prediction-then-metric**(양 family 공통) — 3 반복 OOF 를 consensus 평균한 뒤 지표.
  · seed 축   = **metric-then-average**(GIN 전용) — 시드별 Δ 를 먼저 낸 뒤 평균.

동전 공유 범위(D4): 동일 동전 벡터 `z^(b) ∈ {0,1}^G` 를 **3 seed × 3 repeat 전체에 공동 적용**.
표기(D16): 동전 벡터 = `z`, 시드 인덱스 = `s`.

★ `G`(scaffold group 수)는 호출자가 넘긴 `scaffold_group` 에서 결정된다. 합성 감사에서 쓰는 `G` 는
  **감사용 임의값**이며 확증 분할의 `G` 와 무관하다(확증 `G` 는 본 모듈에서 알 수 없다).
"""
from __future__ import annotations

import time

import numpy as np

from .consensus import build_consensus       # F-CONS: repeat 축 집계는 동결 정의를 그대로 사용
from .metrics import macro_ap                # F-MACRO: 지표 정의 재사용(재구현 금지)

__all__ = [
    "rqint_test", "build_eight_consensus", "observed_statistic",
    "NAME_CAVEAT", "TEST_STATISTIC", "H0_IMPOSED", "H0_TARGET",
    "AGGREGATION", "P_FORMULA", "B_DEFINITION_STATUS",
]

# F-EPS: signflip.py `_EPS` 와 **같은 값**을 신규 모듈에 리터럴로 재기술한다.
# (signflip.py 를 import 하지 않는다 — 동결 모듈에 대한 의존을 늘리지 않기 위함.)
# 보수적 방향(카운트 증가 → p 증가).
_EPS = 1e-12
assert _EPS == 1e-12, "F-EPS 불일치: signflip.py `_EPS = 1e-12` 와 같아야 한다"

TEST_STATISTIC = ("T = Δ_RF − Δ_GIN, Δ_F = macroAP(y, P_F^{M2b}) − macroAP(y, P_F^{M1b}); 양측. "
                  "additive surrogate 대체 금지(A6 계승).")
H0_IMPOSED = ("H0^B(강한 null): 각 family 내부에서 arm 라벨(M1b/M2b)이 scaffold group 단위로 "
              "교환 가능 = Δ_RF = 0 이고 Δ_GIN = 0. 모델 재학습 미포함.")
H0_TARGET = "H0^int(약한 null): Δ_RF = Δ_GIN (공통값 ≠ 0 허용). H0^B ⊊ H0^int."
NAME_CAVEAT = ("shared-coin scaffold-blocked arm-swap interaction test. "
               "부과 귀무=강한 null(H0^B) ≠ 검정 대상 가설=약한 null(H0^int). "
               "'약한 null 에 대한 정확검정' 표기 금지 — 1종오류 통제는 R1 캘리브레이션 감사로 실증. "
               "모델 재학습 미포함(고정 OOF 의 conditional randomization).")
AGGREGATION = ("D3: repeat 축 = prediction-then-metric(consensus 평균 후 지표, 양 family 공통); "
               "seed 축 = metric-then-average(시드별 Δ 산출 후 평균, GIN 전용).")
P_FORMULA = ("p = (1.0 + count) / (n_permutation_values + 1.0), "
             "count = sum(abs(perm) >= abs(T_obs) - _EPS)   # F-PFORM 축자 계승")
B_DEFINITION_STATUS = ("still_unspecified — `B` 가 n_coin_vectors 인지 n_permutation_values 인지 "
                       "본 모듈에서 정하지 않는다. SAP 1.2 에서 확정 필요.")

_ARMS = ("M1b", "M2b")


def _macro(y, P, eligible_pt):
    return macro_ap(y, P, eligible_pt)["macro_ap"]


def _seed_keys(P_GIN):
    ks1 = sorted(P_GIN["M1b"].keys())
    ks2 = sorted(P_GIN["M2b"].keys())
    if ks1 != ks2:
        raise ValueError(f"GIN seed 키 불일치: M1b={ks1} vs M2b={ks2}")
    return ks1


def build_eight_consensus(P_RF, P_GIN):
    """D5 Step 1 — consensus **8행렬**을 순열 루프 **밖에서 1회** 산출한다.

    Parameters
    ----------
    P_RF  : {"M1b": [rep0, rep1, rep2], "M2b": [...]}      각 원소 (N,K)
    P_GIN : {"M1b": {s: [rep0, rep1, rep2]}, "M2b": {s: [...]}}   s = 시드 인덱스(D16)

    Returns
    -------
    (mats, seeds) — mats 는 key `(family, seed|None, arm)` → (N,K) consensus 행렬.
    RF 2 + GIN 3seed×2 = **정확히 8개**.
    """
    seeds = _seed_keys(P_GIN)
    mats = {}
    for arm in _ARMS:
        mats[("RF", None, arm)] = build_consensus(P_RF[arm])       # F-CONS 그대로 호출
        for s in seeds:
            mats[("GIN", s, arm)] = build_consensus(P_GIN[arm][s])
    # D5: 참조분포 1개당 macro-AP 8회 = 이 8행렬 위에서만 계산한다.
    assert len(mats) == 8, f"consensus 행렬은 정확히 8개여야 한다(RF 2 + GIN 3seed×2), 실측={len(mats)}"
    return mats, seeds


def observed_statistic(mats, seeds, y, eligible_pt):
    """D3 Step 2 — Δ_RF, 시드별 Δ_GIN,s, Δ_GIN, T."""
    d_rf = (_macro(y, mats[("RF", None, "M2b")], eligible_pt)
            - _macro(y, mats[("RF", None, "M1b")], eligible_pt))
    # metric-then-average (D3): 시드축은 지표 산출 후 평균 — 행렬을 먼저 평균하면 D3 위반이다.
    d_gin_s = [(_macro(y, mats[("GIN", s, "M2b")], eligible_pt)
                - _macro(y, mats[("GIN", s, "M1b")], eligible_pt)) for s in seeds]
    d_gin = float(np.mean(d_gin_s))
    return float(d_rf - d_gin), float(d_rf), d_gin, [float(v) for v in d_gin_s]


def _apply_swap(mats, seeds, swap_row):
    """후보 B sharp null(F-CANDB) — z_g=1 인 군의 행에 대해 **각 family·각 시드 내부에서** M1b↔M2b 교환.

    family 간·시드 간 예측은 **절대 섞이지 않는다**(후보 B 의 핵심: 스케일 혼입 방지).
    """
    sr = swap_row[:, None]
    out = {}
    for fam, s in [("RF", None)] + [("GIN", s) for s in seeds]:
        A = mats[(fam, s, "M1b")]
        Bm = mats[(fam, s, "M2b")]
        out[(fam, s, "M1b")] = np.where(sr, Bm, A)
        out[(fam, s, "M2b")] = np.where(sr, A, Bm)
    return out


def rqint_test(P_RF, P_GIN, y, scaffold_group, eligible_pt=None,
               n_coin_vectors=1000, seed=0, pair_complement=True,
               complement_audit_draws=1000, return_perm=False):
    """RQ-int 양측 검정.

    Parameters
    ----------
    n_coin_vectors : 뽑는 동전 벡터 `z` 의 개수.
    pair_complement : True 면 여집합 `z̄ = 1 − z` 의 통계량을 **항등식 `T*(z̄) = −T*(z)`** 로 도출해
        참조분포에 함께 넣는다(참조분포 크기 = 2 × n_coin_vectors, 평가 비용은 절반).
        `complement_audit_draws` 개 draw 에 대해 여집합을 **명시적으로 재계산**해 항등식을 전건 검증하며,
        하나라도 실패하면 **항등식 경로를 끄고 명시적 계산으로 폴백**한다.
    ★ `B` 의 의미(동전 수 vs 참조분포 크기)는 **still_unspecified** — 본 함수는 둘 다 기록만 한다.
    """
    y = np.asarray(y)
    groups = np.asarray(scaffold_group)
    uniq = np.unique(groups)
    gi_of_row = np.searchsorted(uniq, groups)          # 군 → 행 인덱스(라벨 무관, 정렬 위치 기준)
    n_groups = len(uniq)

    mats, seeds = build_eight_consensus(P_RF, P_GIN)
    t_obs, d_rf, d_gin, d_gin_s = observed_statistic(mats, seeds, y, eligible_pt)

    rng = np.random.default_rng(seed)                  # 동전 생성기(signflip 규약과 동일 형태)
    audit_rng = np.random.default_rng(seed + 1_000_003)
    n_audit = int(min(complement_audit_draws, n_coin_vectors)) if pair_complement else 0
    audit_idx = set(audit_rng.choice(n_coin_vectors, size=n_audit, replace=False).tolist()) \
        if n_audit > 0 else set()

    t_star = np.empty(n_coin_vectors, dtype=np.float64)
    audit_max_abs = 0.0
    audit_done = 0
    audit_fail = 0
    loop_seconds = 0.0
    audit_seconds = 0.0

    for b in range(n_coin_vectors):
        z = rng.random(n_groups) < 0.5                 # 동전 벡터 z^(b) ∈ {0,1}^G (D4: 8행렬 공동 적용)
        swap_row = z[gi_of_row]
        t0 = time.perf_counter()
        sw = _apply_swap(mats, seeds, swap_row)
        t_star[b], _, _, _ = observed_statistic(sw, seeds, y, eligible_pt)
        loop_seconds += time.perf_counter() - t0
        if b in audit_idx:                             # 여집합 명시적 재계산(항등식 감사)
            ta = time.perf_counter()
            sw_c = _apply_swap(mats, seeds, ~swap_row)
            t_c, _, _, _ = observed_statistic(sw_c, seeds, y, eligible_pt)
            audit_seconds += time.perf_counter() - ta
            dev = abs(t_c + t_star[b])
            audit_max_abs = max(audit_max_abs, dev)
            audit_done += 1
            if not dev < 1e-12:
                audit_fail += 1

    identity_used = bool(pair_complement and audit_fail == 0)
    if pair_complement and audit_fail > 0:
        # 폴백 — 항등식 경로를 끄고 여집합을 명시적으로 계산한다.
        rng_fb = np.random.default_rng(seed)
        comp = np.empty(n_coin_vectors, dtype=np.float64)
        for b in range(n_coin_vectors):
            z = rng_fb.random(n_groups) < 0.5
            swap_row = z[gi_of_row]
            sw_c = _apply_swap(mats, seeds, ~swap_row)
            comp[b], _, _, _ = observed_statistic(sw_c, seeds, y, eligible_pt)
        perm = np.concatenate([t_star, comp])
    elif pair_complement:
        perm = np.concatenate([t_star, -t_star])       # 항등식 T*(z̄) = −T*(z)
    else:
        perm = t_star

    n_perm_values = int(perm.size)
    count = int(np.sum(np.abs(perm) >= abs(t_obs) - _EPS))          # 양측 (F-PFORM)
    p = (1.0 + count) / (n_perm_values + 1.0)

    out = {
        "test_name": "RQ-int shared-coin scaffold-blocked arm-swap interaction test",
        "name_caveat": NAME_CAVEAT,
        "test_statistic": TEST_STATISTIC,
        "H0_imposed": H0_IMPOSED,
        "H0_target": H0_TARGET,
        "aggregation": AGGREGATION,
        "model_retraining_included": False,
        "T_obs": float(t_obs),
        "delta_rf": float(d_rf),
        "delta_gin": float(d_gin),
        # D6-ii: 고정 시드집합 조건부성 — 유의성과 무관하게 **항상** 보고.
        "delta_gin_per_seed": d_gin_s,
        "delta_gin_seed_mean": float(np.mean(d_gin_s)),
        "delta_gin_seed_sd": float(np.std(d_gin_s, ddof=1)) if len(d_gin_s) > 1 else 0.0,
        "gin_seed_keys": [str(s) for s in seeds],
        "inference_conditional_on": "pre-specified GIN training seed set",
        "p_two_sided": float(p),
        "p_formula": P_FORMULA,
        "eps": _EPS,
        "count_abs_ge_obs": count,
        "n_coin_vectors": int(n_coin_vectors),
        "n_permutation_values": n_perm_values,
        "B_definition": B_DEFINITION_STATUS,
        "seed": int(seed),
        "n_groups_G": int(n_groups),
        "G_note": "합성 감사에서 G 는 감사용 임의값 — 확증 분할의 G 와 무관",
        "exchange_unit": "scaffold group (shared coin across both families and all seeds)",
        "pair_complement": bool(pair_complement),
        "complement_identity_used": identity_used,
        "complement_audit": {
            "draws_checked": audit_done,
            "failures": audit_fail,
            "max_abs_dev": float(audit_max_abs),
            "tol": 1e-12,
            "fallback_to_explicit": bool(pair_complement and audit_fail > 0),
        },
        "n_consensus_matrices": 8,
        "null_summary": {"mean": float(np.mean(perm)), "sd": float(np.std(perm, ddof=1)),
                         "abs_ge_obs": count},
        # AC-3-4: 실측만(외삽 없음). 분모 = 명시적으로 평가한 T* 횟수(= 동전 벡터 수).
        "per_permutation_seconds": float(loop_seconds / n_coin_vectors),
        "per_reference_value_seconds": float(loop_seconds / n_perm_values),
        "complement_audit_seconds": float(audit_seconds),
        "timing_note": ("per_permutation_seconds = macro-AP 8회를 포함한 T* 1회 평가의 벽시계 실측 평균. "
                        "여집합 감사 시간은 별도(complement_audit_seconds), 외삽값 없음."),
    }
    if return_perm:
        out["perm"] = perm
    return out
