"""metrics.py — macro AP 공유 헬퍼 (사전등록 §7, 동결 정의).

정의는 `ladder_confirmatory.macro_ap`(사전등록 §7)과 **바이트 수준으로 동일**해야 한다:
  macro AP = eval 대상에서 **양성(positive)이 1개 이상인 PT**의 average_precision_score 산술평균.

⚠️ 무결성: 본 모듈은 확증 데이터를 import/로드하지 않는다. `ladder_confirmatory`도 import하지
   않는다(그쪽 모듈이 load_frozen 등 데이터 경로를 참조하므로 SAP 미접근 원칙 유지). 대신 동일한
   `sklearn.metrics.average_precision_score` 정의를 **재기술**한다. freeze.py가 정의 동일성을
   합성 데이터로 교차검증한다.

undefined-AP 규칙(사전등록 §7·§8, bootstrap replicate 규칙과 동일):
   eval 표본에서 test-positive가 0인 PT는 average_precision_score가 미정의 → **macro 평균에서 제외**.
   eligible_pt(원 전체 평가셋에서 고정된 PT 집합, 예: global 양성 ≥10인 370 PT) 안에서만 평가하며,
   그 중 표본 내 양성>0인 PT만 실제 평균에 들어간다. 제외 개수/비율을 함께 반환한다.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score

__all__ = ["macro_ap", "MACRO_AP_DEF", "MACRO_AP_EDGE_RULES"]

MACRO_AP_DEF = (
    "macro AP = average_precision_score over eligible PTs with in-sample positive>0, "
    "arithmetic mean (sklearn.metrics.average_precision_score). Matches "
    "ladder_confirmatory.macro_ap and preregistration §7."
)

# A6(이미 동결·문구/assert 고정): macro AP·Δ 계산 edge 규칙 명문화(동작 불변).
MACRO_AP_EDGE_RULES = (
    "macro-then-subtract: PT별 AP 산출 후 macro 평균, Δ=macroAP_M2b−macroAP_M1b(공통 eligible PT). "
    "tie 처리=sklearn.metrics.average_precision_score 표준(별도 tie-break 없음). "
    "test-positive 0 PT=제외(undefined-AP). "
    "positive-class 점수=P[:, j](PT별 이진; 별도 열 선택 불필요, raw positive-class probability)."
)


def macro_ap(y, P, eligible_pt=None):
    """macro AP + undefined-AP 회계.

    Parameters
    ----------
    y : (n, K) 0/1 array — eval 표본의 라벨.
    P : (n, K) float array — eval 표본의 예측 점수(raw probability).
    eligible_pt : 1-D int array | None
        원 전체 평가셋에서 **고정된** 적격 PT 열 인덱스(§7: global 양성 ≥10인 370 PT).
        None이면 전체 K열을 적격으로 본다. replicate 내부에서 재선정하지 않는다(§A7-2).

    Returns
    -------
    dict: {macro_ap, n_eval(평균에 실제 사용된 PT 수), n_excluded_undefined(표본 내 양성0 제외),
           n_eligible, excl_frac, defined_mask(cols 정렬 bool: 표본 내 양성>0 여부)}
    """
    y = np.asarray(y)
    P = np.asarray(P)
    # A6 assert: y·P 동일 2D shape(공통 eligible PT 위에서 macro-then-subtract 전제).
    if y.ndim != 2 or P.ndim != 2:
        raise ValueError(f"macro_ap는 (n,K) 2D 필요: y.ndim={y.ndim}, P.ndim={P.ndim}")
    if y.shape != P.shape:
        raise ValueError(f"y {y.shape} != P {P.shape}")
    K = y.shape[1]
    if eligible_pt is None:
        cols = np.arange(K)
    else:
        cols = np.asarray(eligible_pt, dtype=int)
    aps = []
    n_excluded = 0
    defined_mask = np.zeros(len(cols), dtype=bool)     # A5: cols별 표본-내 정의 여부
    for ci, j in enumerate(cols):
        yj = y[:, j]
        if yj.sum() > 0:                      # test-positive ≥ 1 → AP 정의됨
            # positive-class 점수 = P[:, j] (PT별 이진, raw prob) · tie=sklearn 표준
            aps.append(average_precision_score(yj, P[:, j]))
            defined_mask[ci] = True
        else:                                  # undefined-AP 규칙 → macro 평균 제외
            n_excluded += 1
    n_eval = len(aps)
    val = float(np.mean(aps)) if n_eval > 0 else float("nan")
    n_eligible = int(len(cols))
    return {
        "macro_ap": val,
        "n_eval": int(n_eval),
        "n_excluded_undefined": int(n_excluded),
        "n_eligible": n_eligible,
        "excl_frac": float(n_excluded / n_eligible) if n_eligible else 0.0,
        "defined_mask": defined_mask.tolist(),
    }
