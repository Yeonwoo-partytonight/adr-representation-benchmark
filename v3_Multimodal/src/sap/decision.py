"""decision.py — A11: 성공판정 함수 + 다중성 + SESOI/TOST (docs/41 §4, 사전등록 §8).

★ primary 판정 대상(2026-07-24 확정, 안 B) = **pChEMBL 제외판(10차원 B_m1b)** M1b·M2b **하나로만**.
  pChEMBL 포함판(13차원 B_m1b_pchembl → M1b_pchembl·M2b_pchembl)은 **동일 함수로 sensitivity 재현**
  (primary 판정 미포함). cherry-pick 금지. 근거 = docs/33(19:45)·docs/40 §3.

순수 함수(입력=요약통계, 출력=판정 라벨). 확증 값 미포함.

성공기준(사전 고정 — 사후 완화 금지)
  RQ2(primary) 성공 ⟺ consensus OOF Δ(M2b−M1b)가
     (1) scaffold cluster bootstrap 95% CI 하한 > 0 AND
     (2) scaffold-group sign-flip 양측 p < 0.05 AND
     (3) SESOI(|Δ|≥0.01) 충족.  (intersection-union; 방향성은 (1)이 이미 보장 = D1)
  RQ3 성공 ⟺ Δ(M2b−P-ID) **및** Δ(M2b−P-FAM) 각각 (1)·(2) 충족(max 비교 금지).
  RQ4 성공 ⟺ 관측 M2b가 재배치 null 대비 p_emp<0.05 (global·family-constrained 둘 다).

다중성
  ① M2b−M1b(primary) = **무보정**.
  ②~⑧ = **Holm family**(fixed-sequence gatekeeping 아님; 7개 p 동시 Holm).
     "M2b−RF"의 RF = **tuned-RF baseline**(primary family의 RF-Morgan과 명칭 구분).
  PT별 검정 = **별도 BH-FDR family**(양성 충분 PT만).

TOST/3분판정(D2): 등록 95%CI ⊂ [−SESOI,+SESOI] 기반 **별도 등가규칙**("표준 α=0.05 TOST와 동일"
  표기 회피). Positive / Equivalent / Inconclusive.
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "SESOI", "ALPHA", "HOLM_FAMILY", "HOLM_UNDEFINED_FILL", "MULTIPLICITY_MANIFEST",
    "PT_MIN_POSITIVE", "PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS", "PRIMARY_TARGET",
    "rq2_decision", "rq3_decision", "rq4_decision",
    "holm", "bh_fdr", "tost_equivalence", "pt_eligibility",
]

SESOI = 0.01          # 등록 §8: |Δ macro AP| ≥ 0.01 (등가구간 정의에 절대값 필요)
ALPHA = 0.05

PRIMARY_TARGET = ("primary = pChEMBL 제외판(10차원 B_m1b) M1b·M2b 하나로만. "
                  "pChEMBL 포함판(13차원)은 동일 함수로 sensitivity(판정 미포함).")

# ②~⑧ Holm family (① M2b−M1b 무보정은 제외). 순서는 라벨용(Holm은 순서 무관·p 크기순 처리).
HOLM_FAMILY = [
    "M2b-P-ID",       # ②
    "M2b-P-FAM",      # ③
    "M2b-realloc_null",  # ④ (재배치 null)
    "M2b-M0",         # ⑤
    "M2b-RF_tuned",   # ⑥ RF = tuned-RF baseline (primary RF-Morgan과 구분)
    "RFseq-RF",       # ⑦
    "RQ-int",         # ⑧
]
# A2: Holm family는 **크기 7 고정**. undefined/결측 p는 아래 값으로 채움(드롭 금지 → 유리한 축소 방지).
HOLM_UNDEFINED_FILL = 1.0

# A2: 다중성 매니페스트(freeze 시 manifest에 기록·hash). id ②~⑧ = HOLM_FAMILY 순서.
#   metric·sidedness는 "template default(macro AP·two-sided) 또는 해당(applicable)"으로 정직 기록:
#   ④ 재배치 null만 upper-tail empirical p(one-sided), 나머지는 sign-flip two-sided.
MULTIPLICITY_MANIFEST = [
    {"id": "②", "label": "M2b-P-ID", "contrast": "M2b − P-ID",
     "model_family": "RF primary confirmatory (RF-Morgan+seq)", "metric": "macro AP",
     "test": "scaffold-group sign-flip", "sidedness": "two-sided",
     "undefined_fill": HOLM_UNDEFINED_FILL},
    {"id": "③", "label": "M2b-P-FAM", "contrast": "M2b − P-FAM",
     "model_family": "RF primary confirmatory (RF-Morgan+seq)", "metric": "macro AP",
     "test": "scaffold-group sign-flip", "sidedness": "two-sided",
     "undefined_fill": HOLM_UNDEFINED_FILL},
    {"id": "④", "label": "M2b-realloc_null", "contrast": "M2b vs 자연 임베딩 재배치 null",
     "model_family": "RF primary confirmatory (RF-Morgan+seq)", "metric": "macro AP",
     "test": "empirical reallocation p (global·family-constrained)",
     "sidedness": "one-sided (upper-tail empirical p)", "undefined_fill": HOLM_UNDEFINED_FILL},
    {"id": "⑤", "label": "M2b-M0", "contrast": "M2b − M0",
     "model_family": "RF primary confirmatory (RF-Morgan+seq)", "metric": "macro AP",
     "test": "scaffold-group sign-flip", "sidedness": "two-sided",
     "undefined_fill": HOLM_UNDEFINED_FILL},
    {"id": "⑥", "label": "M2b-RF_tuned", "contrast": "M2b − tuned-RF baseline",
     "model_family": "RF primary confirmatory (RF-Morgan+seq)", "metric": "macro AP",
     "test": "scaffold-group sign-flip", "sidedness": "two-sided",
     "undefined_fill": HOLM_UNDEFINED_FILL},
    {"id": "⑦", "label": "RFseq-RF", "contrast": "RF-seq − RF",
     "model_family": "RF primary confirmatory (RF-Morgan+seq)", "metric": "macro AP",
     "test": "scaffold-group sign-flip", "sidedness": "two-sided",
     "undefined_fill": HOLM_UNDEFINED_FILL},
    {"id": "⑧", "label": "RQ-int", "contrast": "interaction (RQ-int)",
     "model_family": "RF primary confirmatory (RF-Morgan+seq)", "metric": "macro AP",
     "test": "scaffold-group sign-flip", "sidedness": "two-sided",
     "undefined_fill": HOLM_UNDEFINED_FILL},
]

# A3: PT별 BH-FDR eligibility = **결과-독립 수치 정의**(label·scaffold만; 효과크기·p 무참조).
PT_MIN_POSITIVE = 10                   # 등록 §7 평가셋 정의와 정합(global 양성 ≥ 10)
PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS = 3  # 초과 제약(결과 무참조 사전 고정): 양성-포함 scaffold cluster ≥ 3

# A1: primary CI status 게이트 — estimable로 인정되는 status 집합.
_ESTIMABLE_STATUSES = {"estimable", "bca"}


def _read_ci(ci):
    """CI 입력 → (ci_low, estimable). dict(ci_primary)면 status로 estimability 판정,
    (low,high) 튜플이면 legacy estimable로 간주(A1)."""
    if isinstance(ci, dict):
        low = ci.get("low")
        low = float(low) if low is not None else float("nan")
        status = ci.get("status", "estimable")
    else:
        low, status = float(ci[0]), "estimable"
    return low, (status in _ESTIMABLE_STATUSES)


def rq2_decision(bootstrap_ci, signflip_p, delta_obs, sesoi=SESOI, alpha=ALPHA):
    """RQ2 primary 성공판정(intersection-union).

    bootstrap_ci : ci_primary dict(low,high,status) 또는 (low,high) — scaffold cluster bootstrap 95% CI(primary=BCa).
    signflip_p   : scaffold-group sign-flip 양측 p.
    delta_obs    : 관측 Δ(M2b−M1b).

    A1: primary CI가 not_estimable(BCa 불능)이면 success=False로 강제(percentile 대체 판정 금지)."""
    ci_low, estimable = _read_ci(bootstrap_ci)
    if not estimable:
        return {
            "rq": "RQ2 (M2b>M1b, primary)",
            "cond1_ci_lower_gt0": False, "cond2_signflip_p_lt_alpha": False, "cond3_sesoi": False,
            "ci_low": ci_low, "ci_estimable": False, "signflip_p": float(signflip_p),
            "delta_obs": float(delta_obs), "sesoi": sesoi, "alpha": alpha,
            "success": False, "reason": "primary CI not estimable (BCa failed)",
            "rule": "성공 ⟺ (1)&(2)&(3) 모두(IU). primary CI 불능 시 성공 불가(A1).",
        }
    cond1 = ci_low > 0.0
    cond2 = float(signflip_p) < alpha
    cond3 = abs(float(delta_obs)) >= sesoi   # SESOI; 방향은 cond1이 보장
    success = bool(cond1 and cond2 and cond3)
    return {
        "rq": "RQ2 (M2b>M1b, primary)",
        "cond1_ci_lower_gt0": bool(cond1),
        "cond2_signflip_p_lt_alpha": bool(cond2),
        "cond3_sesoi": bool(cond3),
        "ci_low": ci_low, "ci_estimable": True, "signflip_p": float(signflip_p),
        "delta_obs": float(delta_obs), "sesoi": sesoi, "alpha": alpha,
        "success": success,
        "rule": "성공 ⟺ (1)&(2)&(3) 모두(IU). 방향성은 (1) CI 하한>0가 보장(D1).",
    }


def _contrast_pass(ci, p, alpha=ALPHA):
    """A1: CI not_estimable → pass=False(성공 불가). percentile 대체 판정 금지."""
    ci_low, estimable = _read_ci(ci)
    if not estimable:
        return {"cond1_ci_lower_gt0": False, "cond2_p_lt_alpha": False,
                "ci_low": ci_low, "ci_estimable": False, "p": float(p), "pass": False,
                "reason": "primary CI not estimable (BCa failed)"}
    c1 = ci_low > 0.0
    c2 = float(p) < alpha
    return {"cond1_ci_lower_gt0": bool(c1), "cond2_p_lt_alpha": bool(c2),
            "ci_low": ci_low, "ci_estimable": True, "p": float(p), "pass": bool(c1 and c2)}


def rq3_decision(ci_pid, p_pid, ci_fam, p_fam, alpha=ALPHA):
    """RQ3 성공 ⟺ (M2b−P-ID) 및 (M2b−P-FAM) 각각 (1)·(2). max 비교 금지(각각 개별 충족)."""
    pid = _contrast_pass(ci_pid, p_pid, alpha)
    fam = _contrast_pass(ci_fam, p_fam, alpha)
    return {
        "rq": "RQ3 (M2b>P-ID 및 M2b>P-FAM)",
        "M2b_vs_PID": pid, "M2b_vs_PFAM": fam,
        "success": bool(pid["pass"] and fam["pass"]),
        "rule": "성공 ⟺ 두 대비 각각 (1) CI 하한>0 & (2) p<α. co-primary 통제(max 금지).",
    }


def rq4_decision(p_emp_global, p_emp_family, alpha=ALPHA):
    """RQ4 성공 ⟺ 재배치 null p_emp<α (global·family-constrained 둘 다)."""
    g = float(p_emp_global) < alpha
    f = float(p_emp_family) < alpha
    return {
        "rq": "RQ4 (M2b > 재배치 null)",
        "global": {"p_emp": float(p_emp_global), "pass": bool(g)},
        "family_constrained": {"p_emp": float(p_emp_family), "pass": bool(f)},
        "success": bool(g and f),
        "rule": "성공 ⟺ global·family-constrained 재배치 null 둘 다 p_emp<α.",
    }


def holm(pvalues, alpha=ALPHA):
    """Holm–Bonferroni step-down over the **fixed 7-label family**(A2).

    pvalues = {label: p} — HOLM_FAMILY(7) 하위집합. 존재하지 않거나 undefined/None/NaN인 p는
    HOLM_UNDEFINED_FILL(=1.0)로 채운다(family_size는 **항상 7**, 축소 금지 → 유리한 보정 방지).
    입력에 HOLM_FAMILY 밖 라벨이 있으면 AssertionError.

    ②~⑧ 7개 동시 Holm(fixed-sequence gatekeeping 아님). ① M2b−M1b은 이 family에 넣지 않는다."""
    extra = set(pvalues.keys()) - set(HOLM_FAMILY)
    assert not extra, f"[A2] Holm family(7) 밖 라벨: {sorted(extra)} — family는 HOLM_FAMILY로 고정"

    labels = list(HOLM_FAMILY)                          # 정본 순서·고정 크기 7
    filled = {}
    p_list = []
    for k in labels:
        v = pvalues.get(k, None)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            pv = HOLM_UNDEFINED_FILL                     # 결측/undefined → 1.0
            filled[k] = True
        else:
            fv = float(v)
            if np.isnan(fv):
                pv, filled[k] = HOLM_UNDEFINED_FILL, True
            else:
                pv, filled[k] = fv, False
        p_list.append(pv)
    p = np.array(p_list, dtype=float)
    m = len(p)                                          # == 7 (고정)
    assert m == len(HOLM_FAMILY) == 7, "[A2] Holm family_size는 7로 고정"
    order = np.argsort(p, kind="stable")               # 오름차순
    adj_sorted = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p[idx]                       # Holm 가중
        running = max(running, val)                     # 단조 보정
        adj_sorted[idx] = min(1.0, running)
    reject = {labels[i]: bool(adj_sorted[i] < alpha) for i in range(m)}
    return {
        "method": "Holm step-down",
        "family_size": int(m),
        "family_size_fixed": 7,
        "alpha": alpha,
        "raw_p": {labels[i]: float(p[i]) for i in range(m)},
        "undefined_filled": filled,
        "undefined_fill_value": HOLM_UNDEFINED_FILL,
        "adjusted_p": {labels[i]: float(adj_sorted[i]) for i in range(m)},
        "reject": reject,
        "note": "②~⑧ 동시 Holm(family=7 고정). ① M2b−M1b(primary)는 무보정(이 family 제외). "
                "결측/undefined p → 1.0(드롭 금지).",
    }


def pt_eligibility(y, scaffold_group,
                   min_positive=PT_MIN_POSITIVE,
                   min_pos_clusters=PT_MIN_POSITIVE_SCAFFOLD_CLUSTERS):
    """A3: PT별 BH-FDR eligibility — **결과-독립**(label·scaffold만; 효과크기·p 무참조).

    적격 ⟺ (global 양성 ≥ min_positive) AND (양성-포함 scaffold cluster 수 ≥ min_pos_clusters).

    Parameters
    ----------
    y : (n, K) 0/1 array — 평가셋 라벨.
    scaffold_group : (n,) — 약물별 scaffold cluster id.

    Returns
    -------
    dict: {eligible_pt(적격 PT 열 인덱스 리스트), n_eligible, per_pt{j:{n_positive,
           n_positive_scaffold_clusters, eligible}}, min_positive, min_pos_clusters}."""
    y = np.asarray(y)
    g = np.asarray(scaffold_group)
    if y.ndim != 2:
        raise ValueError(f"y는 (n,K) 2D 필요: ndim={y.ndim}")
    if g.shape[0] != y.shape[0]:
        raise ValueError(f"scaffold_group 길이 {g.shape[0]} != n {y.shape[0]}")
    K = y.shape[1]
    per_pt = {}
    eligible = []
    for j in range(K):
        pos_rows = np.where(y[:, j] > 0)[0]
        n_pos = int(pos_rows.size)
        n_clusters = int(np.unique(g[pos_rows]).size) if n_pos else 0
        ok = (n_pos >= min_positive) and (n_clusters >= min_pos_clusters)
        per_pt[j] = {"n_positive": n_pos, "n_positive_scaffold_clusters": n_clusters,
                     "eligible": bool(ok)}
        if ok:
            eligible.append(j)
    return {
        "eligible_pt": eligible,
        "n_eligible": len(eligible),
        "per_pt": per_pt,
        "min_positive": int(min_positive),
        "min_pos_clusters": int(min_pos_clusters),
        "rule": "결과-독립: global 양성 ≥ min_positive AND 양성-포함 scaffold cluster ≥ min_pos_clusters "
                "(효과크기·p 무참조; 사전 고정).",
    }


def bh_fdr(pvalues, q=0.05):
    """Benjamini–Hochberg FDR. pvalues = {label: p}. Returns adj p(q-value) + reject.

    입력은 **pt_eligibility()를 통과한 PT만**(A3: 결과-독립 eligibility) — caller가 사전 필터링한다."""
    labels = list(pvalues.keys())
    p = np.array([float(pvalues[k]) for k in labels], dtype=float)
    m = len(p)
    if m == 0:
        return {"method": "BH-FDR", "family_size": 0, "q": q, "adjusted_p": {}, "reject": {}}
    order = np.argsort(p, kind="stable")               # 오름차순
    adj_sorted = np.empty(m, dtype=float)
    running = 1.0
    # 뒤에서부터 단조(비감소 q-value) 보정
    for rank in range(m - 1, -1, -1):
        idx = order[rank]
        val = p[idx] * m / (rank + 1)
        running = min(running, val)
        adj_sorted[idx] = min(1.0, running)
    reject = {labels[i]: bool(adj_sorted[i] <= q) for i in range(m)}
    return {
        "method": "BH-FDR",
        "family_size": int(m),
        "q": q,
        "adjusted_p": {labels[i]: float(adj_sorted[i]) for i in range(m)},
        "reject": reject,
        "note": "PT별 검정 = M2b−M1b Holm family와 별도. 양성 충분 PT만 포함.",
    }


def tost_equivalence(ci_low, ci_high, delta_obs, sesoi=SESOI, ci_status="estimable"):
    """3분판정(D2) — 95%CI 기반 등가규칙(표준 α=0.05 TOST 표기 회피).

    Positive     : CI 하한 > 0 AND |Δ| ≥ SESOI.
    Equivalent   : CI ⊂ [−SESOI, +SESOI].
    Inconclusive : 그 외(CI가 0과 ±SESOI 경계를 모두 초과) → "효과 없음" 아닌 "불확실".

    A1: primary CI가 not_estimable(BCa 불능)이면 label="Not-estimable"(등가/양성 판정 불가)."""
    if ci_status not in _ESTIMABLE_STATUSES:
        return {
            "label": "Not-estimable",
            "ci_low": float(ci_low), "ci_high": float(ci_high), "delta_obs": float(delta_obs),
            "sesoi": sesoi, "ci_estimable": False,
            "reason": "primary CI not estimable (BCa failed)",
            "note": "BCa 불능 → 등가/양성 판정 불가(percentile 대체 금지, A1).",
        }
    lo, hi, d = float(ci_low), float(ci_high), float(delta_obs)
    if lo > 0.0 and abs(d) >= sesoi:
        label = "Positive"
    elif lo >= -sesoi and hi <= sesoi:
        label = "Equivalent"
    else:
        label = "Inconclusive"
    return {
        "label": label,
        "ci_low": lo, "ci_high": hi, "delta_obs": d, "sesoi": sesoi, "ci_estimable": True,
        "rule": "Positive: CI하한>0 & |Δ|≥SESOI / Equivalent: CI⊂[−SESOI,+SESOI] / else Inconclusive",
        "note": "등록 95%CI 기반 별도 등가규칙(D2). '표준 α=0.05 TOST와 동일' 표기 회피.",
    }
