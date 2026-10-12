"""rqint_audit.py — RQ-int 구현에 대한 **독립 검사 코드**(A21) · R6-1 ~ R6-9.

⛔ 무결성: 합성 fixture 만 사용한다. 확증 데이터를 로드하지 않는다.

★ 독립성 규약(docs/89 종료검증 #8 · R6-9)
  · 본 모듈은 **`rqint.py` 를 import 하지 않는다.** 검사 대상 구현은 **호출자가 주입**한다(`impl`).
  · R6-9 참조 구현(`naive_t_star_sequence`)은 8행렬 사전산출·여집합 항등식·벡터화를 쓰지 않는
    **소박한 이중 루프**로 별도 작성했다. 동전열은 **같은 seed 를 주되 각자 생성**한다
    (같은 함수를 호출해 같은 답이 나오는 것은 검증이 아니다).
  · 지표·집계 정의만은 갈라지면 estimand 가 달라지므로 `metrics.macro_ap` 를 공유한다.
  · 균등성 허용오차는 A6 `audit_uniform` 과 **동일 규격**을 쓰기 위해 `signflip._ks_uniform` 을
    그대로 import 한다(F-A6TOL: mean_tol=0.10 · ks_tol=0.16).
"""
from __future__ import annotations

import numpy as np

from .metrics import macro_ap
from .signflip import _ks_uniform            # F-A6TOL 동일 규격(KS 정의 공유). 수정 0.

__all__ = [
    "naive_t_star_sequence", "naive_observed", "enumerate_exact_p",
    "check_commutativity", "check_zero_effect", "check_uniformity",
    "check_complement_antisymmetry", "check_full_swap", "check_group_relabel_invariance",
    "check_rerun_determinism", "check_full_enumeration", "check_independent_reference",
    "weak_null_diagnostic", "MEAN_TOL", "KS_TOL",
]

MEAN_TOL = 0.10        # F-A6TOL — 늘리는 것 금지
KS_TOL = 0.16          # F-A6TOL — 늘리는 것 금지
_EPS = 1e-12           # F-EPS


# ═══════════════════════════════════════════════════════════════════════════
# 소박한 참조 구현 (R6-9) — 8행렬 사전산출 없음 · 여집합 항등식 없음 · 벡터화 없음
# ═══════════════════════════════════════════════════════════════════════════
def _mean_of_list(arrs):
    """반복 축 평균을 명시적 누산으로 계산(np.stack 사용 안 함)."""
    acc = np.array(arrs[0], dtype=np.float64)
    for a in arrs[1:]:
        acc = acc + np.asarray(a, dtype=np.float64)
    return acc / float(len(arrs))


def _swap_rows(A, B, swap_row):
    """행 단위 교환을 파이썬 루프로 수행(np.where 사용 안 함)."""
    A2 = np.array(A, dtype=np.float64)
    B2 = np.array(B, dtype=np.float64)
    for i in range(A2.shape[0]):
        if swap_row[i]:
            tmp = A2[i, :].copy()
            A2[i, :] = B2[i, :]
            B2[i, :] = tmp
    return A2, B2


def _naive_stat(P_RF, P_GIN, y, eligible_pt, swap_row, seeds):
    """반복별·시드별 이중 루프로 T* 산출. 교환은 **반복 배열 각각에** 먼저 적용한다."""
    def fam_delta(m1_reps, m2_reps):
        sw1, sw2 = [], []
        for r in range(len(m1_reps)):                       # 반복 루프
            a, b = _swap_rows(m1_reps[r], m2_reps[r], swap_row)
            sw1.append(a)
            sw2.append(b)
        c1 = _mean_of_list(sw1)
        c2 = _mean_of_list(sw2)
        return (macro_ap(y, c2, eligible_pt)["macro_ap"]
                - macro_ap(y, c1, eligible_pt)["macro_ap"])

    d_rf = fam_delta(P_RF["M1b"], P_RF["M2b"])
    d_each = []
    for s in seeds:                                          # 시드 루프
        d_each.append(fam_delta(P_GIN["M1b"][s], P_GIN["M2b"][s]))
    d_gin = sum(d_each) / float(len(d_each))                 # metric-then-average
    return d_rf - d_gin, d_rf, d_gin, d_each


def naive_observed(P_RF, P_GIN, y, scaffold_group, eligible_pt, seeds):
    """교환 없음(z ≡ 0) 상태의 관측 통계량."""
    no_swap = np.zeros(len(np.asarray(scaffold_group)), dtype=bool)
    return _naive_stat(P_RF, P_GIN, y, eligible_pt, no_swap, seeds)


def naive_t_star_sequence(P_RF, P_GIN, y, scaffold_group, eligible_pt, seeds,
                          n_coin_vectors, seed):
    """동전 seed 만 공유하고 **동전열을 자체 생성**해 T* 수열을 소박하게 계산한다."""
    groups = np.asarray(scaffold_group)
    uniq = np.unique(groups)
    n_groups = len(uniq)
    row_group_pos = [int(np.where(uniq == g)[0][0]) for g in groups]   # 루프로 군 위치 산출
    rng = np.random.default_rng(seed)                                  # 같은 seed, 각자 생성
    out = []
    for _ in range(n_coin_vectors):
        z = rng.random(n_groups) < 0.5
        swap_row = np.array([z[row_group_pos[i]] for i in range(len(groups))], dtype=bool)
        t, _, _, _ = _naive_stat(P_RF, P_GIN, y, eligible_pt, swap_row, seeds)
        out.append(float(t))
    return np.asarray(out, dtype=np.float64)


def enumerate_exact_p(P_RF, P_GIN, y, scaffold_group, eligible_pt, seeds):
    """G 가 작을 때 2^G 동전 벡터를 **전수 열거**해 exact 양측 p 를 계산한다(R6-8 정답표)."""
    groups = np.asarray(scaffold_group)
    uniq = np.unique(groups)
    G = len(uniq)
    if G > 12:
        raise ValueError(f"전수열거는 G<=12 에서만: G={G}")
    pos = np.searchsorted(uniq, groups)
    t_obs, _, _, _ = naive_observed(P_RF, P_GIN, y, scaffold_group, eligible_pt, seeds)
    vals = np.empty(2 ** G, dtype=np.float64)
    for m in range(2 ** G):
        z = np.array([(m >> k) & 1 for k in range(G)], dtype=bool)
        swap_row = z[pos]
        t, _, _, _ = _naive_stat(P_RF, P_GIN, y, eligible_pt, swap_row, seeds)
        vals[m] = t
    count = int(np.sum(np.abs(vals) >= abs(t_obs) - _EPS))
    return {"T_obs": float(t_obs), "n_enumerated": int(2 ** G),
            "count_abs_ge_obs": count, "p_exact": float(count / (2 ** G))}


# ═══════════════════════════════════════════════════════════════════════════
# R6-1 ~ R6-9
# ═══════════════════════════════════════════════════════════════════════════
def _consensus(arrs):
    return np.mean(np.stack([np.asarray(a, dtype=np.float64) for a in arrs], axis=0), axis=0)


def check_commutativity(fixture, n_z=100, seed=0):
    """R6-1 — (교환 ∘ repeat 평균) == (repeat 평균 ∘ 교환). 임의 z 100개 전건."""
    P_RF, P_GIN, y, groups, elig = fixture
    seeds = sorted(P_GIN["M1b"].keys())
    uniq = np.unique(groups)
    pos = np.searchsorted(uniq, groups)
    rng = np.random.default_rng(seed)
    max_diff = 0.0
    all_equal = True
    n_pairs = 0
    fam_list = [("RF", None, P_RF)] + [("GIN", s, None) for s in seeds]
    for _ in range(n_z):
        z = rng.random(len(uniq)) < 0.5
        sr = z[pos][:, None]
        for fam, s, _blk in fam_list:
            m1 = P_RF["M1b"] if fam == "RF" else P_GIN["M1b"][s]
            m2 = P_RF["M2b"] if fam == "RF" else P_GIN["M2b"][s]
            # ① 반복별로 먼저 교환한 뒤 평균
            a_first = _consensus([np.where(sr, m2[r], m1[r]) for r in range(len(m1))])
            b_first = _consensus([np.where(sr, m1[r], m2[r]) for r in range(len(m1))])
            # ② 평균한 뒤 교환
            c1, c2 = _consensus(m1), _consensus(m2)
            a_after = np.where(sr, c2, c1)
            b_after = np.where(sr, c1, c2)
            for u, v in ((a_first, a_after), (b_first, b_after)):
                n_pairs += 1
                if not np.array_equal(u, v):
                    all_equal = False
                max_diff = max(max_diff, float(np.max(np.abs(u - v))))
    ok = all_equal or max_diff < 1e-15
    return {"id": "R6-1", "name": "가환성(교환 연산자 ∘ repeat 평균)", "n_z": int(n_z),
            "n_matrix_pairs": n_pairs, "all_array_equal": bool(all_equal),
            "max_abs_diff": max_diff, "criterion": "np.array_equal 또는 max abs diff < 1e-15",
            "pass": bool(ok)}


def check_zero_effect(impl, fixture, n_coin_vectors=300, seed=0):
    """R6-2 — 동일 입력(M1b == M2b) → T = 0 이고 모든 T* = 0 → p 는 정확히 1.0."""
    P_RF, P_GIN, y, groups, elig = fixture
    res = impl.rqint_test(P_RF, P_GIN, y, groups, elig, n_coin_vectors=n_coin_vectors,
                          seed=seed, pair_complement=True, complement_audit_draws=0,
                          return_perm=True)
    perm = res.pop("perm")
    ok = (abs(res["p_two_sided"] - 1.0) < 1e-9 and abs(res["T_obs"]) < 1e-12
          and float(np.max(np.abs(perm))) < 1e-12)
    return {"id": "R6-2", "name": "zero-effect → p = 1.0", "T_obs": res["T_obs"],
            "p": res["p_two_sided"], "max_abs_t_star": float(np.max(np.abs(perm))),
            "criterion": "|p−1| < 1e-9 AND T=0 AND 모든 T*=0", "pass": bool(ok)}


def check_uniformity(impl, make_exchangeable, R=200, n_coin_vectors=150, seed=0):
    """R6-3 — H0^B 참(공유 동전 배정) 데이터에서 p 분포 ≈ Uniform. F-A6TOL 동일 규격."""
    ps = np.empty(R, dtype=float)
    for r in range(R):
        P_RF, P_GIN, y, groups, elig = make_exchangeable(seed * 100003 + r)
        res = impl.rqint_test(P_RF, P_GIN, y, groups, elig,
                              n_coin_vectors=n_coin_vectors, seed=seed * 7 + r,
                              pair_complement=True, complement_audit_draws=0)
        ps[r] = res["p_two_sided"]
    mean_p = float(np.mean(ps))
    ks = _ks_uniform(ps)
    ok = abs(mean_p - 0.5) <= MEAN_TOL and ks < KS_TOL
    return {"id": "R6-3", "name": "대칭 할당 균등성", "R": int(R),
            "n_coin_vectors": int(n_coin_vectors), "mean_p": mean_p, "ks_vs_uniform": float(ks),
            "frac_le": {f"le_{t}": float(np.mean(ps <= t)) for t in (0.05, 0.10, 0.25, 0.50)},
            "criterion": f"mean(p) ∈ [{0.5-MEAN_TOL:.2f}, {0.5+MEAN_TOL:.2f}] AND KS < {KS_TOL}",
            "pass": bool(ok)}


def check_complement_antisymmetry(impl, fixture, n_coin_vectors=1000, seed=0):
    """R6-4 — 여집합 반대칭 |T*(z̄) + T*(z)| < 1e-12 을 ≥1,000 draw 전건 검증(명시적 재계산)."""
    P_RF, P_GIN, y, groups, elig = fixture
    res = impl.rqint_test(P_RF, P_GIN, y, groups, elig, n_coin_vectors=n_coin_vectors,
                          seed=seed, pair_complement=True, complement_audit_draws=1000)
    ca = res["complement_audit"]
    ok = ca["draws_checked"] >= 1000 and ca["failures"] == 0
    return {"id": "R6-4", "name": "여집합 반대칭(complement_audit)", **ca,
            "identity_path_used": res["complement_identity_used"],
            "criterion": "≥1,000 draw 명시적 재계산 · 전건 |T*(z̄)+T*(z)| < 1e-12", "pass": bool(ok)}


def check_full_swap(impl, fixture):
    """R6-5 — z ≡ 1(전체 교환)이면 T* = −T 가 정확히 성립."""
    P_RF, P_GIN, y, groups, elig = fixture
    seeds = sorted(P_GIN["M1b"].keys())
    mats, sk = impl.build_eight_consensus(P_RF, P_GIN)
    t_obs, _, _, _ = impl.observed_statistic(mats, sk, y, elig)
    all_swap = np.ones(len(np.asarray(groups)), dtype=bool)
    sw = {}
    for fam, s in [("RF", None)] + [("GIN", s) for s in seeds]:
        sw[(fam, s, "M1b")] = mats[(fam, s, "M2b")]
        sw[(fam, s, "M2b")] = mats[(fam, s, "M1b")]
    t_full, _, _, _ = impl.observed_statistic(sw, sk, y, elig)
    dev = abs(t_full + t_obs)
    return {"id": "R6-5", "name": "전체 교환 보존(z ≡ 1 → T* = −T)", "T_obs": float(t_obs),
            "T_full_swap": float(t_full), "abs_dev": float(dev),
            "n_rows_swapped": int(all_swap.sum()),
            "criterion": "|T*(1) + T| == 0 (정확)", "pass": bool(dev == 0.0)}


def check_group_relabel_invariance(impl, fixture, n_coin_vectors=300, seed=0):
    """R6-6 — 군 ID 를 **순서보존** 재라벨링하고 행 순서를 동일 치환해도 동일 seed 에서 p·T 동일.

    ★ 비단조 재라벨링은 동전↔군 짝짓기(= 몬테카를로 실현)를 바꾸므로 정확 동일성을 요구하지 않는다.
      불변인 것은 검정의 귀무분포이지 특정 난수 실현이 아니다. 그 경우의 |Δp| 는 참고로만 기록한다."""
    P_RF, P_GIN, y, groups, elig = fixture
    seeds = sorted(P_GIN["M1b"].keys())
    base = impl.rqint_test(P_RF, P_GIN, y, groups, elig, n_coin_vectors=n_coin_vectors,
                           seed=seed, pair_complement=True, complement_audit_draws=0)
    rng = np.random.default_rng(seed + 77)
    perm_rows = rng.permutation(len(np.asarray(groups)))
    g2 = (np.asarray(groups) * 3 + 5)[perm_rows]                 # 순서보존(단조) 재라벨 + 행 치환
    y2 = np.asarray(y)[perm_rows]
    RF2 = {a: [np.asarray(m)[perm_rows] for m in P_RF[a]] for a in ("M1b", "M2b")}
    GIN2 = {a: {s: [np.asarray(m)[perm_rows] for m in P_GIN[a][s]] for s in seeds}
            for a in ("M1b", "M2b")}
    rel = impl.rqint_test(RF2, GIN2, y2, g2, elig, n_coin_vectors=n_coin_vectors,
                          seed=seed, pair_complement=True, complement_audit_draws=0)
    d_t = abs(rel["T_obs"] - base["T_obs"])
    ok = (rel["p_two_sided"] == base["p_two_sided"]) and d_t < 1e-12
    # 참고: 비단조 재라벨(역순) — 동전 짝짓기가 바뀌므로 MC 실현만 달라진다.
    g3 = (int(np.max(groups)) - np.asarray(groups))[perm_rows]
    nm = impl.rqint_test(RF2, GIN2, y2, g3, elig, n_coin_vectors=n_coin_vectors,
                         seed=seed, pair_complement=True, complement_audit_draws=0)
    return {"id": "R6-6", "name": "군 순서 불변(순서보존 재라벨 + 행 치환)",
            "p_base": base["p_two_sided"], "p_relabeled": rel["p_two_sided"],
            "abs_dT": float(d_t),
            "informational_nonmonotone_relabel_p": nm["p_two_sided"],
            "informational_note": "비단조 재라벨은 동전↔군 짝짓기(MC 실현)를 바꾼다 — 합격기준 아님",
            "criterion": "p 정확 동일 AND |ΔT| < 1e-12", "pass": bool(ok)}


def check_rerun_determinism(impl, fixture, n_coin_vectors=300, seed=0):
    """R6-7 — 동일 입력·동일 seed 2회 실행 → T·p·참조분포 바이트 동일."""
    P_RF, P_GIN, y, groups, elig = fixture
    kw = dict(n_coin_vectors=n_coin_vectors, seed=seed, pair_complement=True,
              complement_audit_draws=0, return_perm=True)
    a = impl.rqint_test(P_RF, P_GIN, y, groups, elig, **kw)
    b = impl.rqint_test(P_RF, P_GIN, y, groups, elig, **kw)
    pa, pb = a.pop("perm"), b.pop("perm")
    same_bytes = pa.tobytes() == pb.tobytes()
    ok = same_bytes and a["T_obs"] == b["T_obs"] and a["p_two_sided"] == b["p_two_sided"]
    return {"id": "R6-7", "name": "재실행 결정성", "perm_bytes_identical": bool(same_bytes),
            "T_identical": bool(a["T_obs"] == b["T_obs"]),
            "p_identical": bool(a["p_two_sided"] == b["p_two_sided"]),
            "criterion": "T·p·참조분포 바이트 동일", "pass": bool(ok)}


def check_full_enumeration(impl, fixture, n_coin_vectors=4000, seed=0):
    """R6-8 — 2^G 전수열거 exact p vs 몬테카를로 p, 차이가 MC SE 의 3배 이내."""
    P_RF, P_GIN, y, groups, elig = fixture
    seeds = sorted(P_GIN["M1b"].keys())
    ex = enumerate_exact_p(P_RF, P_GIN, y, groups, elig, seeds)
    mc = impl.rqint_test(P_RF, P_GIN, y, groups, elig, n_coin_vectors=n_coin_vectors,
                         seed=seed, pair_complement=True, complement_audit_draws=0)
    pe = ex["p_exact"]
    # ★ MC 오차는 **독립 동전 draw 수**가 지배한다. 여집합 값은 |T*| 가 같아 양측 p 에 정보를
    #   더하지 않으므로(|T*(z̄)| = |T*(z)|) SE 분모에 n_permutation_values 를 쓰지 않는다.
    se = float(np.sqrt(max(pe * (1.0 - pe), 0.0) / n_coin_vectors))
    diff = abs(mc["p_two_sided"] - pe)
    ok = diff <= 3.0 * se + 1e-12
    return {"id": "R6-8", "name": "완전열거 정답표", **ex,
            "p_monte_carlo": mc["p_two_sided"], "n_coin_vectors": int(n_coin_vectors),
            "n_permutation_values": mc["n_permutation_values"],
            "mc_se": se, "abs_diff": float(diff), "three_se": float(3.0 * se),
            "T_obs_impl": mc["T_obs"], "abs_dT_vs_naive": float(abs(mc["T_obs"] - ex["T_obs"])),
            "criterion": "|p_MC − p_exact| ≤ 3 × MC SE (SE 분모 = 독립 동전 draw 수)",
            "pass": bool(ok)}


def check_independent_reference(impl, fixture, n_coin_vectors=200, seed=0):
    """R6-9 — 소박한 참조 구현과 T* 수열 대조(max abs diff < 1e-12). 동전열은 각자 생성."""
    P_RF, P_GIN, y, groups, elig = fixture
    seeds = sorted(P_GIN["M1b"].keys())
    res = impl.rqint_test(P_RF, P_GIN, y, groups, elig, n_coin_vectors=n_coin_vectors,
                          seed=seed, pair_complement=True, complement_audit_draws=0,
                          return_perm=True)
    impl_t = np.asarray(res.pop("perm"))[:n_coin_vectors]          # 앞쪽 = 실제 평가한 T*(z)
    naive_t = naive_t_star_sequence(P_RF, P_GIN, y, groups, elig, seeds, n_coin_vectors, seed)
    nt_obs, nd_rf, nd_gin, _ = naive_observed(P_RF, P_GIN, y, groups, elig, seeds)
    d_seq = float(np.max(np.abs(impl_t - naive_t)))
    d_obs = float(abs(res["T_obs"] - nt_obs))
    ok = d_seq < 1e-12 and d_obs < 1e-12
    return {"id": "R6-9", "name": "독립 구현 대조", "n_coin_vectors": int(n_coin_vectors),
            "max_abs_diff_t_star_sequence": d_seq, "abs_diff_T_obs": d_obs,
            "T_obs_impl": res["T_obs"], "T_obs_naive": float(nt_obs),
            "delta_rf_naive": float(nd_rf), "delta_gin_naive": float(nd_gin),
            "criterion": "max abs diff < 1e-12 (구현·참조 모두)", "pass": bool(ok)}


def weak_null_diagnostic(impl, make_common_effect, R=200, n_coin_vectors=150, seed=0):
    """AC-3-3 — 약한 null(Δ_RF ≈ Δ_GIN ≠ 0) 하 p 분포 **예비 진단**.

    ★ 판정 아님. 합격/불합격 기준으로 쓰지 않는다. 정식 판정은 R1 의 C1~C3 이며
      그때는 α=0.05 뿐 아니라 0.05/7 · 0.05/4 에서도 본다(A10)."""
    ps = np.empty(R, dtype=float)
    d_rf = np.empty(R, dtype=float)
    d_gin = np.empty(R, dtype=float)
    for r in range(R):
        P_RF, P_GIN, y, groups, elig = make_common_effect(seed * 100003 + r)
        res = impl.rqint_test(P_RF, P_GIN, y, groups, elig, n_coin_vectors=n_coin_vectors,
                              seed=seed * 7 + r, pair_complement=True, complement_audit_draws=0)
        ps[r] = res["p_two_sided"]
        d_rf[r] = res["delta_rf"]
        d_gin[r] = res["delta_gin"]
    return {
        "status": "예비 진단 · 판정 아님 (정식 판정 = R1 의 C1~C3)",
        "R": int(R), "n_coin_vectors": int(n_coin_vectors),
        "mean_p": float(np.mean(ps)),
        "frac_p_le_0.05": float(np.mean(ps <= 0.05)),
        "frac_p_le_0.05_over_7": float(np.mean(ps <= 0.05 / 7)),
        "frac_p_le_0.05_over_4": float(np.mean(ps <= 0.05 / 4)),
        "mean_delta_rf": float(np.mean(d_rf)), "mean_delta_gin": float(np.mean(d_gin)),
        "mean_abs_delta_gap": float(np.mean(np.abs(d_rf - d_gin))),
        "note": ("합성 fixture 는 두 family 의 base·effect 를 같게 두어 Δ_RF ≈ Δ_GIN ≠ 0 을 만든 것이다. "
                 "이 수치는 R1 설계에 넣을 예상 규모를 잡기 위한 것이며 게이트가 아니다."),
    }
