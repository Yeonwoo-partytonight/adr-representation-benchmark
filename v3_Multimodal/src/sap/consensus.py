"""consensus.py — A8: consensus OOF 정의 (사전등록 §6 방법A 고정, docs/41 §1).

정의(등록 §6-(ii)): 각 약물-PT에 대해 **3 반복 OOF score를 산술평균 → consensus score(N×PT)** →
**그 위에서** 모든 통계 추론(bootstrap·sign-flip)을 수행한다. 반복별 macro AP 3개는 **반복 간 변동
보고용**이며 **판정을 대체하지 않는다**(방법B 아님).

고정 규칙
  - 평균 대상 = **raw RF probability**(calibration 후 아님).
  - 반복당 약물 1 OOF 예측, RF `random_state=42`가 전 반복 동일, fold별 독립 transform 유지.
  - 반복이 1개뿐이면(§13-3 방향 조회 단계) 그 자체를 반환(consensus 평균 대상 없음).
  - 3개 반복을 3,276행처럼 단순 pool하지 않는다(약물 독립성 과대평가 방지) — 본 함수는 평균만 한다.

⚠️ 무결성: 입력은 이미 산출된 OOF score 배열 리스트일 뿐(확증 값은 확증 단계에서만 채워짐).
   본 모듈은 확증 데이터를 로드하지 않는 순수 함수다.
"""
from __future__ import annotations

import numpy as np

__all__ = ["build_consensus", "repeat_macro_aps", "CONSENSUS_METHOD"]

CONSENSUS_METHOD = "A (등록 §6-(ii)): drug-PT별 raw OOF probability 산술평균 → consensus → 그 위에서 추론"


def build_consensus(oof_by_repeat):
    """반복별 OOF score 배열 리스트 → consensus score(산술평균).

    Parameters
    ----------
    oof_by_repeat : list of (N, K) float array
        각 원소 = 한 반복의 전체 N 약물 OOF 예측(raw probability). 모두 동일 shape.

    Returns
    -------
    (N, K) float array. 리스트 길이 1이면 그 배열을 그대로 반환(§13-3 방향용).
    """
    if not isinstance(oof_by_repeat, (list, tuple)) or len(oof_by_repeat) == 0:
        raise ValueError("oof_by_repeat는 비어있지 않은 배열 리스트여야 함")
    arrs = [np.asarray(a, dtype=np.float64) for a in oof_by_repeat]
    shp = arrs[0].shape
    for a in arrs:
        if a.shape != shp:
            raise ValueError(f"반복 배열 shape 불일치: {a.shape} != {shp}")
        if np.isnan(a).any():
            raise ValueError("OOF score에 NaN 존재 — consensus 평균 전에 완성 필요")
    if len(arrs) == 1:
        return arrs[0].copy()
    # 산술평균 = 방법A. (약물별 반복 score 평균; 반복 축은 axis=0의 stack)
    return np.mean(np.stack(arrs, axis=0), axis=0)


def repeat_macro_aps(oof_by_repeat, y, macro_ap_fn, eligible_pt=None):
    """반복별 macro AP 3개(변동 보고용) — 판정 대체 금지(방법B 아님).

    macro_ap_fn = sap.metrics.macro_ap (주입식). 반환 = 반복별 macro AP 리스트 + (mean, sd)."""
    vals = [macro_ap_fn(y, a, eligible_pt)["macro_ap"] for a in oof_by_repeat]
    vals = [float(v) for v in vals]
    return {
        "per_repeat_macro_ap": vals,
        "mean": float(np.mean(vals)),
        "sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
        "note": "반복 간 변동 보고용. 성공판정은 consensus 위 bootstrap/sign-flip으로만(방법A).",
    }
