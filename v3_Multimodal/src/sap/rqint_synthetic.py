"""rqint_synthetic.py — RQ-int 전용 합성 fixture (`synthetic.py` 는 0바이트 무수정).

⛔ 무결성: 여기서 만드는 데이터는 **합성 전용 · 확증 데이터와 무관 · G 는 임의값**이다.
   master_X/master_Y·scaffold_split·확증 OOF 를 로드하지 않는다(전부 np.random 시드 산출물).

모든 생성기는 seed 로 결정적이며, 반환 형식은 `rqint.rqint_test` 입력 규약과 같다:
    (P_RF, P_GIN, y, scaffold_group, eligible_pt)
      P_RF  = {"M1b": [rep0, rep1, rep2], "M2b": [...]}
      P_GIN = {"M1b": {s: [rep0, rep1, rep2]}, "M2b": {s: [...]}}   s ∈ {1,2,3}
"""
from __future__ import annotations

import numpy as np

from .synthetic import _scores_from_labels, make_labels     # synthetic.py 재사용(수정 0)

__all__ = [
    "make_rqint_zero_interaction", "make_rqint_exchangeable",
    "make_rqint_common_effect", "make_rqint_tiny", "SEEDS",
]

SEEDS = (1, 2, 3)          # 시드 인덱스 s (D16). 확증 학습시드 값이 아니라 **인덱스**다.
_REPS = 3


def _groups(rng, N, G):
    """N 행을 G 군에 배정(각 군 ≥1). 합성 전용 · G 는 임의값(확증 G 와 무관)."""
    base = np.arange(G) % G
    rest = rng.integers(0, G, size=max(0, N - G))
    g = np.concatenate([base, rest])[:N]
    rng.shuffle(g)
    return g.astype(int)


def make_rqint_zero_interaction(seed=0, N=100, K=10, G=20):
    """합성 전용 · 확증 데이터와 무관 · G 는 임의값. 양 family 모두 M1b == M2b → Δ_RF = Δ_GIN = 0.

    zero-effect 감사(R6-2)용: 모든 순열에서 T* = 0 이므로 p 는 정확히 1.0 이어야 한다."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K)
    rf = [_scores_from_labels(rng, y, strength=1.1) for _ in range(_REPS)]
    P_RF = {"M1b": [a.copy() for a in rf], "M2b": [a.copy() for a in rf]}
    P_GIN = {"M1b": {}, "M2b": {}}
    for s in SEEDS:
        gin = [_scores_from_labels(rng, y, strength=0.9) for _ in range(_REPS)]
        P_GIN["M1b"][s] = [a.copy() for a in gin]
        P_GIN["M2b"][s] = [a.copy() for a in gin]
    return P_RF, P_GIN, y, _groups(rng, N, G), np.arange(K)


def make_rqint_exchangeable(seed=0, N=100, K=10, G=20):
    """합성 전용 · 확증 데이터와 무관 · G 는 임의값. **공유 동전**으로 군마다 arm 배정 → H0^B 참.

    두 arm(A,B)은 동일 강도의 독립 draw 이고, 하나의 동전 `c_g` 가 **RF·GIN 전 시드·전 반복에
    동시에** 어느 쪽이 M1b/M2b 인지 결정한다. 임의 z 를 추가로 적용해도 c XOR z ~ c 이므로
    결합분포가 불변 = 후보 B 의 sharp null(H0^B)이 참이다. 균등성 감사(R6-3)용."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K)
    groups = _groups(rng, N, G)
    uniq = np.unique(groups)
    coin = rng.random(len(uniq)) < 0.5
    sr = coin[np.searchsorted(uniq, groups)][:, None]        # 공유 동전 → 행 단위 교환 여부

    def _pair(strength):
        A = _scores_from_labels(rng, y, strength=strength)
        B = _scores_from_labels(rng, y, strength=strength)   # 동일 강도·독립 draw
        return np.where(sr, B, A), np.where(sr, A, B)

    P_RF = {"M1b": [], "M2b": []}
    for _ in range(_REPS):
        m1, m2 = _pair(1.1)
        P_RF["M1b"].append(m1)
        P_RF["M2b"].append(m2)
    P_GIN = {"M1b": {s: [] for s in SEEDS}, "M2b": {s: [] for s in SEEDS}}
    for s in SEEDS:
        for _ in range(_REPS):
            m1, m2 = _pair(0.9)
            P_GIN["M1b"][s].append(m1)
            P_GIN["M2b"][s].append(m2)
    return P_RF, P_GIN, y, groups, np.arange(K)


def make_rqint_common_effect(seed=0, N=100, K=10, G=20, effect=0.9, base=1.1):
    """합성 전용 · 확증 데이터와 무관 · G 는 임의값. Δ_RF ≈ Δ_GIN ≠ 0 (공통 서열효과, 상호작용 0).

    **진단 전용**(docs/89 AC-3-3) — 약한 null(H0^int 참, H0^B 거짓) 영역이다. 여기서 나오는
    p 분포는 **판정에 쓰지 않는다.** 정식 판정은 R1 의 C1~C3."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K)
    P_RF = {"M1b": [_scores_from_labels(rng, y, strength=base) for _ in range(_REPS)],
            "M2b": [_scores_from_labels(rng, y, strength=base + effect) for _ in range(_REPS)]}
    P_GIN = {"M1b": {}, "M2b": {}}
    for s in SEEDS:
        # 동일 base·동일 effect → 두 family 의 기대 Δ 가 같다(= 상호작용 0, 주효과 0).
        P_GIN["M1b"][s] = [_scores_from_labels(rng, y, strength=base) for _ in range(_REPS)]
        P_GIN["M2b"][s] = [_scores_from_labels(rng, y, strength=base + effect) for _ in range(_REPS)]
    return P_RF, P_GIN, y, _groups(rng, N, G), np.arange(K)


def make_rqint_tiny(seed=0, N=64, K=8, G=8, effect=0.6, base=1.0):
    """합성 전용 · 확증 데이터와 무관 · G 는 임의값. G=8 → 동전 벡터 2^8 = 256 전수열거 가능.

    완전열거 정답표(R6-8)용 — 작은 fixture 라 exact p 를 직접 계산할 수 있다."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K, density=0.15, min_pos=4)
    P_RF = {"M1b": [_scores_from_labels(rng, y, strength=base) for _ in range(_REPS)],
            "M2b": [_scores_from_labels(rng, y, strength=base + effect) for _ in range(_REPS)]}
    P_GIN = {"M1b": {}, "M2b": {}}
    for s in SEEDS:
        P_GIN["M1b"][s] = [_scores_from_labels(rng, y, strength=base) for _ in range(_REPS)]
        P_GIN["M2b"][s] = [_scores_from_labels(rng, y, strength=base) for _ in range(_REPS)]
    return P_RF, P_GIN, y, _groups(rng, N, G), np.arange(K)
