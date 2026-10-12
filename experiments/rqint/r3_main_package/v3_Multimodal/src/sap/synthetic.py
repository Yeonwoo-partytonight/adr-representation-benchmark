"""synthetic.py — SAP 검증용 **가짜** 데이터 생성기 (docs/41 §8).

⛔ 무결성: 여기서 만드는 데이터는 확증 데이터와 **완전히 무관**한 난수 산출물이다. 본 모듈은
   master_X/Y·scaffold_split·confirmatory OOF를 로드하지 않는다(전부 np.random 시드 생성).
   목적: 각 SAP 연산자(bootstrap·sign-flip·null·consensus·decision·unseen)를 실행해 calibration
   audit·보존 assert·진리표를 통과시키는 것.

모든 생성기는 seed로 결정적이다.
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "make_labels", "make_predictions", "make_identical", "make_exchangeable",
    "make_consensus_repeats", "make_target_graph", "make_unseen_fixture",
    "make_eligibility_fixture",
]


def _scaffold_groups(rng, N, G):
    """N 약물을 G scaffold group에 배정(크기 불균등, 각 group ≥1)."""
    # 각 group에 최소 1개 배정 후 나머지 무작위 → 크기 편차 존재(현실적).
    base = np.arange(G) % G
    rest = rng.integers(0, G, size=max(0, N - G))
    groups = np.concatenate([base, rest])[:N]
    rng.shuffle(groups)
    return groups.astype(int)


def make_labels(rng, N, K, density=0.08, min_pos=3):
    """희소 0/1 라벨. 각 PT 열에 최소 min_pos 양성 보장(eligible PT = 전 열)."""
    y = (rng.random((N, K)) < density).astype(int)
    for j in range(K):
        col = y[:, j]
        need = min_pos - int(col.sum())
        if need > 0:
            zeros = np.where(col == 0)[0]
            pick = rng.choice(zeros, size=min(need, len(zeros)), replace=False)
            y[pick, j] = 1
    return y


def _scores_from_labels(rng, y, strength):
    """라벨과 상관된 예측 확률(강할수록 AP↑). sigmoid(strength*y_centered + noise)."""
    yc = y.astype(float) - y.mean(axis=0, keepdims=True)
    logits = strength * yc + rng.normal(0, 1.0, size=y.shape)
    return 1.0 / (1.0 + np.exp(-logits))


def make_predictions(seed=0, N=180, K=24, G=45, effect=0.9, base=1.1):
    """positive-effect fixture: cM2b가 cM1b보다 라벨을 잘 랭크(Δ>0 기대).

    반환: (cM1b, cM2b, y, scaffold_group, eligible_pt)."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K)
    cM1b = _scores_from_labels(rng, y, strength=base)
    cM2b = _scores_from_labels(rng, y, strength=base + effect)
    groups = _scaffold_groups(rng, N, G)
    eligible = np.arange(K)
    return cM1b, cM2b, y, groups, eligible


def make_identical(seed=0, N=160, K=20, G=40):
    """zero-effect fixture: cM1b == cM2b (sign-flip p≈1 audit)."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K)
    P = _scores_from_labels(rng, y, strength=1.0)
    groups = _scaffold_groups(rng, N, G)
    return P.copy(), P.copy(), y, groups, np.arange(K)


def make_exchangeable(seed=0, N=140, K=16, G=35):
    """H0-참 fixture: scaffold group마다 fair-coin으로 두 arm 배정 → 교환 가능(sign-flip p uniform).

    두 arm(P0,P1)은 동일 분포·독립 draw. 그룹별 coin이 어느 것이 cM1b/cM2b인지 결정."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K)
    P0 = _scores_from_labels(rng, y, strength=1.0)     # 동일 강도(교환 가능성 위해)
    P1 = _scores_from_labels(rng, y, strength=1.0)
    groups = _scaffold_groups(rng, N, G)
    uniq = np.unique(groups)
    coin = rng.random(len(uniq)) < 0.5
    coin_of_group = dict(zip(uniq.tolist(), coin.tolist()))
    swap_row = np.array([coin_of_group[g] for g in groups])
    sr = swap_row[:, None]
    cM1b = np.where(sr, P1, P0)                          # coin=1인 group은 arm 교환
    cM2b = np.where(sr, P0, P1)
    return cM1b, cM2b, y, groups, np.arange(K)


def make_consensus_repeats(seed=0, N=100, K=12, R=3):
    """consensus 방법A 검증용 반복 OOF 리스트 + 라벨."""
    rng = np.random.default_rng(seed)
    y = make_labels(rng, N, K)
    reps = [_scores_from_labels(rng, y, strength=1.0 + 0.1 * r) for r in range(R)]
    return reps, y, np.arange(K)


def make_target_graph(seed=0, n_targets=30, n_drugs=60, dim=8):
    """null_generator 검증용 target 그래프(embedding·family·drug-target).

    반환 dict: cid_order, cid2targets, target_emb, targets_by_family, unique_targets."""
    rng = np.random.default_rng(seed)
    targets = [f"T{i:03d}" for i in range(n_targets)]
    target_emb = {t: rng.normal(0, 1, size=dim) for t in targets}

    # family: singleton·size-2·size≥3 를 모두 포함(교환 규칙 검증).
    families = {}
    i = 0
    fam_id = 0
    plan = []
    while i < n_targets:
        # 크기 1,2,3,4,5 를 순환 배치
        size = (fam_id % 5) + 1
        members = targets[i:i + size]
        if members:
            families[f"F{fam_id}"] = members
            plan.append(size)
        i += size
        fam_id += 1

    # drug-target: 일부 약물은 target 0개(결측 패턴).
    cid_order = list(range(1000, 1000 + n_drugs))
    cid2targets = {}
    for c in cid_order:
        k = int(rng.integers(0, 4))                      # 0~3 targets
        if k == 0:
            cid2targets[c] = []
        else:
            cid2targets[c] = sorted(rng.choice(targets, size=k, replace=False).tolist())
    return {
        "cid_order": cid_order,
        "cid2targets": cid2targets,
        "target_emb": target_emb,
        "targets_by_family": families,
        "unique_targets": targets,
        "family_size_plan": plan,
    }


def make_eligibility_fixture():
    """A3 pt_eligibility 경계 검증용 결정적 fixture(난수 없음 — 양성 배치 고정).

    N=60 약물, 6 scaffold cluster(각 10행: cluster c = row//10). 5개 PT 열의 양성 배치를
    (양성수, 양성-포함 cluster수) 경계에 맞춰 고정. 기준 = 양성≥10 AND 양성-cluster≥3.

    반환: (y, scaffold_group, expected_eligible).
      col0: 12 pos / 4 cluster → eligible
      col1: 12 pos / 2 cluster → not eligible(cluster<3)
      col2:  8 pos / 4 cluster → not eligible(pos<10)
      col3: 10 pos / 3 cluster → eligible(경계 pos==10, cluster==3)
      col4:  9 pos / 3 cluster → not eligible(경계 pos<10)"""
    N, K = 60, 5
    scaffold_group = np.array([r // 10 for r in range(N)], dtype=int)   # cluster 0..5, 각 10행
    y = np.zeros((N, K), dtype=int)

    def put(col, cluster, k):
        base = cluster * 10
        y[base:base + k, col] = 1

    # col0: clusters 0,1,2,3 각 3 → 12 pos / 4 cluster
    for c in (0, 1, 2, 3):
        put(0, c, 3)
    # col1: clusters 0,1 각 6 → 12 pos / 2 cluster
    for c in (0, 1):
        put(1, c, 6)
    # col2: clusters 0,1,2,3 각 2 → 8 pos / 4 cluster
    for c in (0, 1, 2, 3):
        put(2, c, 2)
    # col3: clusters 0,1,2 = 4,3,3 → 10 pos / 3 cluster
    put(3, 0, 4); put(3, 1, 3); put(3, 2, 3)
    # col4: clusters 0,1,2 각 3 → 9 pos / 3 cluster
    for c in (0, 1, 2):
        put(4, c, 3)

    expected_eligible = [0, 3]
    return y, scaffold_group, expected_eligible


def make_unseen_fixture(seed=0):
    """unseen_target 검증용: T_train_f + 4분류 대표 약물 + seqid_max(층 대표)."""
    T_train = {"P10000", "P10001", "P10002", "P10003"}
    # 대표 약물(canonical accession 집합)
    drugs = {
        "d_all_seen": {"P10000", "P10001"},                     # ⊆ train
        "d_all_unseen": {"P20000", "P20001"},                   # ∩ train = ∅
        "d_mixed": {"P10000", "P20002"},                        # seen+unseen
        "d_no_target": set(),                                   # ∅
        "d_isoform": {"P10000-2", "P10001-3"},                  # canonicalize → all-seen
    }
    # unseen target별 train 최대 identity(%) — 각 novelty bin 대표
    seqid_max = {
        "P20000": 95.0,   # ≥90
        "P20001": 30.0,   # <40 → 보수적 max=95 → ge90 (약물 d_all_unseen)
        "P20002": 55.0,   # 40–70 (mixed엔 무의미)
        "P30000": 82.0,   # 70–90
        "P30001": 50.0,   # 40–70
        "P30002": 20.0,   # <40
    }
    # 층별 단일-target 약물(보수적 bin 검증)
    unseen_drugs = {
        "u_ge90": {"P20000"},      # 95 → unseen_ge90
        "u_70_90": {"P30000"},     # 82 → unseen_70_90
        "u_40_70": {"P30001"},     # 50 → unseen_40_70
        "u_lt40": {"P30002"},      # 20 → unseen_lt40
    }
    return {"T_train": T_train, "drugs": drugs, "seqid_max": seqid_max, "unseen_drugs": unseen_drugs}
