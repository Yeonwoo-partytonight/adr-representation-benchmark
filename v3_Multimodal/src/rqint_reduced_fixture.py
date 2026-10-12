#!/usr/bin/env python3
"""rqint_reduced_fixture.py — [블록 AD] AD-4 축소규모(N=400 · K=60) fixture 구성 규칙.

⛔ 무결성
  · 본 모듈은 **어떤 데이터 파일도 열지 않는다**(순수 함수만). 라벨·군 배열은 호출자
    (`rqint_timing.py`)가 넘긴다. 확증 예측·OOF·`_sealed`·부호 **일절 미참조**.
  · 선정 규칙은 **라벨 유병률과 군 크기**(= result-independent 설계량)만 쓴다.
    성능·예측·부호는 입력으로 받지도 않는다.
  · `sap/` 밖 모듈이다(SAP 등재 대상 아님, 동결 대상 아님).

정본: `docs/90_rqint_timing_calibration_budget_prompt_for_vscode.md` AD-4 ·
      `docs/84` §2 R1 설계(C0~C3 = N=400 · K=60, 군집 불균형 프로파일 재현).

★ 본 모듈은 **규칙을 확정**할 뿐 동결하지 않는다(동결은 SAP 1.2 블록).
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "allocate_rows_proportional", "regroup_ratio_optimal", "select_pts_by_prevalence",
    "group_profile", "min_attainable_ratio", "FIXTURE_RULES", "PT_SELECT_SEED",
]

PT_SELECT_SEED = 20260812          # AD-4-1: PT 선정 seed(고정)
N_STRATA = 6                       # 유병률 분위수 층 수(6층 × 10 PT = 60)

FIXTURE_RULES = {
    "rows": (
        "AD-4-2 규칙 R-ROW — 실제 scaffold 군 크기 분포의 **최대잉여법(largest remainder) 비례축소**. "
        "군 g 의 할당량 q_g = n_g × N_target / N_full, m_g = floor(q_g); 남은 정수는 잉여 내림차순 "
        "→ 군 크기 내림차순 → 군 키 오름차순의 결정적 순서로 1씩 배분. m_g = 0 인 군은 탈락. "
        "군 내부 행은 원본(cid 오름차순) 순서의 앞에서 m_g 개."
    ),
    "pts": (
        "AD-4-1 규칙 R-PT — 선정된 행 안에서의 **라벨 유병률만** 사용. 표본 내 양성 ≥ 1 인 PT 만 적격 "
        "(AP 정의 가능). 적격 PT 를 유병률 오름차순(동률은 PT 컬럼명 오름차순)으로 정렬해 "
        "**6 등분위 층**으로 나누고 층마다 10개를 seed 고정 RNG 로 비복원 추출. "
        "가장 낮은 층이 극희귀 PT 를 포함하므로 극희귀 포함이 규칙상 보장된다. "
        "성능·예측·부호 **일절 미참조**."
    ),
    "regroup_variant": (
        "AD-4-2 규칙 R-GRP(대안) — `G_eff/G` 를 실제값에 최대한 붙이기 위한 **군 재배정 변형**. "
        "상위 2군(비례축소분)은 그대로 두고, 잔여 행의 싱글톤을 크기 s 인 j 개 블록으로 병합한다. "
        "(s, j)는 `s ≤ 상위2군의 작은 쪽`, `j·s ≤ 잔여행` 범위의 **전수 탐색**으로 "
        "|G_eff/G − target| 최소화. 라벨행렬·행 집합은 **불변**이며 군 라벨만 달라진다."
    ),
}


# ── AD-4-2 : 행/군 구성 ──────────────────────────────────────────────────────
def allocate_rows_proportional(group_of_row, n_target=400):
    """규칙 R-ROW. 실제 군 배열 → 축소 행 인덱스 + 축소 군 라벨.

    Parameters
    ----------
    group_of_row : (N,) int array — 행별 군 인덱스(호출자가 실제 scaffold 군에서 산출).
    n_target : 축소 표본 행 수.

    Returns
    -------
    (row_idx, group_reduced, alloc) — row_idx 는 원본 행 인덱스(오름차순),
    group_reduced 는 row_idx 와 같은 길이의 군 라벨, alloc 은 군별 할당 행 수.
    """
    g = np.asarray(group_of_row)
    n_full = len(g)
    uniq, inv = np.unique(g, return_inverse=True)
    sizes = np.bincount(inv, minlength=len(uniq))

    quota = sizes * (n_target / n_full)
    base = np.floor(quota).astype(int)
    rem = quota - base
    short = int(n_target - base.sum())
    if short < 0:
        raise ValueError("최대잉여법 전제 위반: floor 합이 목표를 초과")
    # 결정적 순서: 잉여 내림차순 → 군 크기 내림차순 → 군 키 오름차순
    order = sorted(range(len(uniq)), key=lambda i: (-rem[i], -int(sizes[i]), str(uniq[i])))
    alloc = base.copy()
    for i in order[:short]:
        alloc[i] += 1
    if alloc.sum() != n_target:
        raise ValueError(f"할당 합 {alloc.sum()} != 목표 {n_target}")

    rows, labels = [], []
    for gi in range(len(uniq)):
        if alloc[gi] == 0:
            continue
        member = np.where(inv == gi)[0]          # 원본 순서(=cid 오름차순) 보존
        take = member[: alloc[gi]]
        rows.append(take)
        labels.append(np.full(len(take), gi, dtype=int))
    row_idx = np.concatenate(rows)
    lab = np.concatenate(labels)
    srt = np.argsort(row_idx, kind="stable")
    return row_idx[srt], lab[srt], alloc


def min_attainable_ratio(n_target, top_sizes, n_rest, max_part=None):
    """상위군을 고정했을 때 잔여행 배치로 **도달 가능한 최소 `G_eff/G`** 와 그 구성.

    `G_eff/G = (Σm)² / (G · Σm²)` 이므로 `G · Σm²` 를 최대화하는 문제다.
    잔여를 「크기 s 인 j 블록 + 싱글톤」으로 두는 족(族) 위에서 전수 탐색한다.
    """
    top = list(top_sizes)
    s_top = sum(v * v for v in top)
    cap = int(max_part if max_part is not None else min(top))
    best = None
    for s in range(2, cap + 1):                      # s=1 은 j=0 케이스와 동일
        for j in range(0, n_rest // s + 1):
            r = n_rest - j * s                       # 싱글톤 수
            G = len(top) + j + r
            sum_sq = s_top + j * s * s + r
            prod = G * sum_sq
            if best is None or prod > best[0]:
                best = (prod, s, j, r, G, sum_sq)
    prod, s, j, r, G, sum_sq = best
    return {"min_ratio": float(n_target ** 2 / prod), "block_size": int(s),
            "n_blocks": int(j), "n_singletons": int(r), "G": int(G), "sum_sq": int(sum_sq),
            "note": "상위군 고정 + 잔여를 「크기 s 인 j 블록 + 싱글톤」으로 두는 족 위의 전수 탐색 하한"}


def regroup_ratio_optimal(group_reduced, target_ratio, n_top=2):
    """규칙 R-GRP(대안). 라벨·행 불변, **군 라벨만** 재배정해 `G_eff/G` 를 target 에 근접시킨다.

    상위 `n_top` 군은 유지하고, 나머지 행을 크기 `s` 인 `j` 블록 + 싱글톤으로 재배정한다.
    (s, j) 는 전수 탐색으로 |G_eff/G − target| 최소화(결정적, 동률은 s 큰 쪽 → j 큰 쪽).
    """
    lab = np.asarray(group_reduced)
    n = len(lab)
    uniq, inv = np.unique(lab, return_inverse=True)
    sizes = np.bincount(inv, minlength=len(uniq))
    top_gi = np.argsort(-sizes, kind="stable")[:n_top]
    top_sizes = [int(sizes[i]) for i in top_gi]
    keep_mask = np.isin(inv, top_gi)
    rest_rows = np.where(~keep_mask)[0]
    n_rest = len(rest_rows)
    cap = int(min(top_sizes))

    s_top2 = sum(v * v for v in top_sizes)
    best = None
    for s in range(1, cap + 1):
        for j in range(0, n_rest // s + 1):
            r = n_rest - j * s
            G = n_top + (j + r)
            sum_sq = s_top2 + j * s * s + r
            ratio = (n ** 2) / (G * sum_sq)
            key = (abs(ratio - target_ratio), -s, -j)
            if best is None or key < best[0]:
                best = (key, s, j, r, G, ratio)
    _, s, j, r, G, ratio = best

    new = np.empty(n, dtype=int)
    for k, gi in enumerate(top_gi):
        new[inv == gi] = k
    nxt = n_top
    pos = 0
    for _ in range(j):                       # 크기 s 블록
        new[rest_rows[pos:pos + s]] = nxt
        pos += s
        nxt += 1
    for idx in rest_rows[pos:]:              # 싱글톤
        new[idx] = nxt
        nxt += 1
    assert nxt == G, f"군 수 불일치 {nxt} != {G}"
    return new, {"block_size": int(s), "n_blocks": int(j), "n_singletons": int(r),
                 "G": int(G), "ratio": float(ratio), "top_sizes": top_sizes}


# ── AD-4-1 : PT 선정 ────────────────────────────────────────────────────────
def select_pts_by_prevalence(y_rows, pt_names, k_target=60, n_strata=N_STRATA,
                             seed=PT_SELECT_SEED, min_pos=1):
    """규칙 R-PT. 선정된 행의 라벨 유병률만으로 K 개 PT 를 층화선정(결정적).

    Returns (cols, info). cols 는 원본 PT 열 인덱스(오름차순 정렬).
    """
    y = np.asarray(y_rows)
    prev = y.sum(axis=0).astype(int)
    elig = np.where(prev >= min_pos)[0]
    if len(elig) < k_target:
        raise ValueError(f"적격 PT {len(elig)} < 목표 {k_target}")
    names = [str(pt_names[c]) for c in elig]
    order = sorted(range(len(elig)), key=lambda i: (int(prev[elig[i]]), names[i]))
    elig_sorted = elig[order]

    per = k_target // n_strata
    if per * n_strata != k_target:
        raise ValueError("k_target 이 층 수로 나누어떨어져야 한다")
    bounds = np.linspace(0, len(elig_sorted), n_strata + 1).astype(int)
    rng = np.random.default_rng(seed)
    picked, strata_info = [], []
    for s in range(n_strata):
        seg = elig_sorted[bounds[s]:bounds[s + 1]]
        take = rng.choice(len(seg), size=per, replace=False)
        take = np.sort(take)
        sel = seg[take]
        picked.append(sel)
        strata_info.append({
            "stratum": s + 1,
            "n_candidates": int(len(seg)),
            "prevalence_range": [int(prev[seg].min()), int(prev[seg].max())],
            "selected_prevalence": sorted(int(prev[c]) for c in sel),
        })
    cols = np.sort(np.concatenate(picked))
    info = {
        "rule": FIXTURE_RULES["pts"],
        "seed": int(seed), "n_strata": int(n_strata), "per_stratum": int(per),
        "n_eligible": int(len(elig)), "min_pos_required": int(min_pos),
        "selected_prevalence_min": int(prev[cols].min()),
        "selected_prevalence_median": float(np.median(prev[cols])),
        "selected_prevalence_max": int(prev[cols].max()),
        "n_selected_prevalence_le_2": int((prev[cols] <= 2).sum()),
        "strata": strata_info,
    }
    return cols, info


# ── 프로파일 ────────────────────────────────────────────────────────────────
def group_profile(group_labels):
    """군 크기 분포 · Kish `G_eff` · 상위2군 점유율 · 왜도 등(설계량만)."""
    lab = np.asarray(group_labels)
    uniq, inv = np.unique(lab, return_inverse=True)
    sizes = np.bincount(inv, minlength=len(uniq)).astype(float)
    n = float(sizes.sum())
    g = int(len(sizes))
    sum_sq = float((sizes ** 2).sum())
    g_eff = float(n ** 2 / sum_sq)
    ss = np.sort(sizes)[::-1]
    mu, sd = sizes.mean(), sizes.std(ddof=0)
    skew = float(((sizes - mu) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    return {
        "N": int(n), "G": g,
        "size_min": int(sizes.min()), "size_median": float(np.median(sizes)),
        "size_max": int(sizes.max()),
        "n_singletons": int((sizes == 1).sum()),
        "singleton_frac": float((sizes == 1).mean()),
        "sum_sq": sum_sq,
        "G_eff_kish": g_eff, "G_eff_over_G": float(g_eff / g),
        "top1_row_share": float(ss[0] / n),
        "top2_row_share": float(ss[:2].sum() / n),
        "top5_sizes": [int(v) for v in ss[:5]],
        "max_nsq_over_sum_nsq": float(ss[0] ** 2 / sum_sq),
        "size_skewness": skew,
    }
