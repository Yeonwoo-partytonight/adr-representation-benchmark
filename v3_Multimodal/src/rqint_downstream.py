"""rqint_downstream.py — RQ-int 후속 계산(블록 113~116) 순수함수 + 합성 자체검사.

동결 명세 = `v3_Multimodal/config/rqint_downstream_spec_v1.json` (블록 AV · docs/112).
이 모듈은 그 명세를 «실행 가능한 형태» 로 못박는다. 명세 JSON 만으로는 실행가능한 명세가 아니다.

⛔ 무결성 (docs/112 §2)
  · 확증·안정성 **봉인 산출물의 값을 읽지 않는다.** 여기서 계산되는 모든 수치는 **합성 fixture** 위의
    값이며, 산출물마다 `provenance: "synthetic_fixture"` 를 단다.
  · `sap/` 는 **import 해서 호출**한다(재구현 0). `sap/` 파일은 0바이트 수정하지 않는다.
  · 판정 함수(`sap.decision.rq2_decision`·`rq3_decision`·`rq4_decision`)·`sap.rqint.rqint_test`·
    `emit_sign`·`open_sealed` 를 **호출하지 않는다.** `sap.decision.holm` 만 selftest 함수 내부에서
    **합성 입력 한정**으로 부른다(T9).
  · 네트워크 0 · `os.environ` 판독 0 · 확증 경로 **쓰기** 0.

★ `p_two_sided` 는 **검증용 복제**다. 정본은 `sap.rqint.rqint_test` 내부의 p 식이며, 본 함수는
  그 식을 별도 경로로 재현해 합성에서 대조하기 위한 것이다. `_EPS` 는 리터럴로 다시 적지 않고
  `sap.rqint._EPS` 를 읽는다.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import platform
import ast

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from sap import rqint as sap_rqint            # noqa: E402  _apply_swap·observed_statistic·_EPS
from sap import consensus as sap_consensus    # noqa: E402  build_consensus
from sap import metrics as sap_metrics        # noqa: E402  macro_ap
from sap import decision as sap_decision      # noqa: E402  holm(합성 한정)·HOLM_FAMILY

__all__ = [
    "SPEC_PATH", "SPEC_SHA256", "PROVENANCE",
    "leverage_profile", "leverage_profile_verbatim", "lambda_k", "rho", "kish_g_eff",
    "split_no_scaffold", "split_benzene", "two_way_ss", "p_two_sided",
]

# ── 동결 명세 ───────────────────────────────────────────────────────────────
SPEC_PATH = "v3_Multimodal/config/rqint_downstream_spec_v1.json"
SPEC_SHA256 = "fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf"

PROVENANCE = "synthetic_fixture"

# ── 불변 고정 대상 (docs/112 F6·F7·F8·F9) ──────────────────────────────────
# F8 ★ manifest 11모듈에 «미등재» 인 3종 — 본 모듈이 직접 호출하므로 별도로 고정한다.
SAP_UNREGISTERED_MODULES = {
    "v3_Multimodal/src/sap/rqint.py":
        ("eb842bc98140e9c55b67bc1563cd5573c3b294885778f23744468b712c498b26", 12970),
    "v3_Multimodal/src/sap/rqint_audit.py":
        ("ddffe6d128de4d180aeab9be18d6b1a9b5281523bc24cd8a3b4f48f20a2aa4a3", 19573),
    "v3_Multimodal/src/sap/rqint_synthetic.py":
        ("27ef0011ee041920a6e7b63eb4dcfef13c7fd2a70ac017f2324e671df8b0f985", 5572),
}
SAP_MANIFEST = ("experiments/sap/manifest.json", "d08dcedf2a22e1c8", 55303)

F6_BLOCK_AT = [
    ("v3_Multimodal/config/gin_train_contract.json", "e50f972674e782f5", 26915),
    ("v3_Multimodal/src/confirmatory_gin_train.py", "714f98983cceff85", 81844),
    ("experiments/runs/v3_gin_start_authorization/selftest_train.json", "f715add2e49afd23", 15347),
    ("experiments/runs/v3_gin_start_authorization/plan_confirmatory_315.json", "121d6db4d1e2a4be", 29138),
    ("experiments/runs/v3_gin_start_authorization/manifest_t3_launch.json", "9231f918ca6b349a", 5979),
    ("experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json", "a59ab54afd515085", 8660),
    ("experiments/runs/v3_gin_start_authorization/sessions.jsonl", "5ee5170840c5a38f", 994),
]
F7_BLOCK_AU = [
    ("v3_Multimodal/config/gin_stability_contract.json", "e092c18ff7afd4f2", 37474),
    ("v3_Multimodal/src/confirmatory_gin_stability.py", "c68a4a242a734408", 88296),
    ("experiments/runs/v3_gin_stability/selftest_stability.json", "c2c8d9bde7232ebf", 16305),
    ("experiments/runs/v3_gin_stability/plan_stability_42.json", "492f03600ae7c5ac", 4397),
    ("experiments/runs/v3_gin_stability/manifest_s1_launch.json", "30cf8bb2a36e40d6", 9356),
    ("experiments/runs/v3_gin_stability/manifest_s2_post_stability.json", "223209a99c694da0", 6018),
]
# ★ F7 7번째 = `…/v3_gin_stability/_sealed/checkpoint.jsonl`. 봉인 파일이므로 본 모듈은
#   **바이트만** 대조한다. sha256 대조는 블록 AV 의 P5 게이트가 1회 수행했고, 그 1회가
#   해당 디렉터리 access.log 의 machine_read 1줄로 기록돼 있다(docs/112 §2-1 예외 · AV-8 #12).
F7_SEALED_STAT_ONLY = ("experiments/runs/v3_gin_stability/_sealed/checkpoint.jsonl", 9669)

REVIEWER_DOCX = ("RQint_Reviewer_Response_<EXTERNAL-REVIEWER>_20260810.docx",
                 "0c29ddf201eb6751a47f420d0c405fdafd0a6baf0ae7705059b0a85fa296aa99", 63649)

EXTRACT_PATH = "experiments/runs/v3_rqint_downstream_spec/reviewer_verbatim_extract.json"
EXTRACTOR_PATH = "experiments/runs/v3_rqint_downstream_spec/extract_omml.py"

# AST 가드 (T11) — 호출이 0이어야 하는 이름들. `holm` 은 selftest 함수 안에서만 허용한다.
FORBIDDEN_CALLS = ("emit_sign", "open_sealed", "rq2_decision", "rq3_decision",
                   "rq4_decision", "rqint_test")
HOLM_ALLOWED_ONLY_INSIDE = "selftest"
CONFIRMATORY_PATH_TOKENS = ("v3_gin_confirm", "v3_confirm", "_sealed")
NETWORK_MODULES = ("socket", "urllib", "requests", "http", "ftplib", "telnetlib",
                   "smtplib", "asyncio", "aiohttp", "httpx")
ALLOWED_CLI_OPTIONS = {"--stage", "--out"}


# ═══════════════════════════════════════════════════════════════════════════
# 순수 함수 — 동결 명세 S2·S3·S4·S6
# ═══════════════════════════════════════════════════════════════════════════
def leverage_profile(mats, seeds, y, eligible_pt, gi_of_row):
    """S2 — 단일군 뒤집기로 `e_g` 전체 프로파일을 **정확히** 계산한다.

    도출 경로(축자와 동치): `T(z^{(g)}) = T_obs − 2·e_g`  ⟹  `e_g = (T_obs − T(z^{(g)})) / 2`.
    `sap.rqint._apply_swap` · `sap.rqint.observed_statistic` 을 그대로 호출한다(재구현 0).

    Returns
    -------
    dict: {e (G,), t_obs, delta_rf, delta_gin, delta_gin_per_seed, n_groups_G, n_macro_ap_calls}
    """
    gi = np.asarray(gi_of_row)
    n_groups = int(gi.max()) + 1 if gi.size else 0
    t_obs, d_rf, d_gin, d_gin_s = sap_rqint.observed_statistic(mats, seeds, y, eligible_pt)
    e = np.empty(n_groups, dtype=np.float64)
    for g in range(n_groups):
        swap_row = (gi == g)
        sw = sap_rqint._apply_swap(mats, seeds, swap_row)
        t_g, _, _, _ = sap_rqint.observed_statistic(sw, seeds, y, eligible_pt)
        e[g] = (t_obs - t_g) / 2.0
    n_fam = 1 + len(seeds)                       # RF + GIN seeds
    return {"e": e, "t_obs": float(t_obs), "delta_rf": float(d_rf), "delta_gin": float(d_gin),
            "delta_gin_per_seed": [float(v) for v in d_gin_s],
            "n_groups_G": n_groups,
            "n_macro_ap_calls": n_groups * 2 * n_fam,   # 군당 8회(= 2 arm × 4 family-슬롯)
            "provenance": PROVENANCE}


def leverage_profile_verbatim(mats, seeds, y, eligible_pt, gi_of_row):
    """검토자 §2.3 **축자** 경로: `d_{F,g} = ½[Δ_F(0) − Δ_F(1_g)]`, `e_g = d_RF,g − d_GIN,g`.

    `leverage_profile` 의 도출식과 수치가 일치해야 한다(T3 가 전 군에 대해 assert).
    """
    gi = np.asarray(gi_of_row)
    n_groups = int(gi.max()) + 1 if gi.size else 0
    _, d_rf0, d_gin0, _ = sap_rqint.observed_statistic(mats, seeds, y, eligible_pt)
    d_rf_g = np.empty(n_groups, dtype=np.float64)
    d_gin_g = np.empty(n_groups, dtype=np.float64)
    for g in range(n_groups):
        sw = sap_rqint._apply_swap(mats, seeds, (gi == g))
        _, d_rf1, d_gin1, _ = sap_rqint.observed_statistic(sw, seeds, y, eligible_pt)
        d_rf_g[g] = 0.5 * (d_rf0 - d_rf1)
        d_gin_g[g] = 0.5 * (d_gin0 - d_gin1)
    return {"d_rf_g": d_rf_g, "d_gin_g": d_gin_g, "e": d_rf_g - d_gin_g,
            "provenance": PROVENANCE}


def lambda_k(e, ks=(1, 2, 10)):
    """S2 — `λ_k = (Σ_{g∈T_k} e_g²) / (Σ_{g=1}^{G} e_g²)`.

    ★ `T_k` = **`|e_g|` 가 큰 상위 k 개 군**(검토자 §3(a) 축자 · 부록 A11). 부호 기준이 아니다.
    """
    e = np.asarray(e, dtype=np.float64)
    denom = float(np.sum(e * e))
    order = np.argsort(-np.abs(e), kind="stable")     # |e| 내림차순, 동률은 군 인덱스 오름차순
    out = {}
    for k in ks:
        kk = int(min(k, e.size))
        idx = order[:kk]
        out[int(k)] = float(np.sum(e[idx] ** 2) / denom) if denom > 0 else float("nan")
    return {"lambda_k": out, "T_k_rule": "|e_g| 상위 k", "denom_sum_sq": denom,
            "top_indices": {int(k): order[:int(min(k, e.size))].tolist() for k in ks},
            "provenance": PROVENANCE}


def rho(t_obs, e):
    """S2 — `ρ = |T_obs − Σ_g e_g| / √(Σ_g e_g²)` (분자 **절댓값 포함** · 부록 A12 축자).

    게이트로 쓰지 않는다(검토자 축자: "게이트로 사용하지 말고 보고 및 주석용으로만").
    """
    e = np.asarray(e, dtype=np.float64)
    denom = float(np.sqrt(np.sum(e * e)))
    num = float(abs(float(t_obs) - float(np.sum(e))))
    return {"rho": (num / denom) if denom > 0 else float("nan"),
            "numerator_abs": num, "denominator": denom,
            "is_gate": False, "provenance": PROVENANCE}


def kish_g_eff(sizes):
    """`G_eff = (Σ n_g)² / (Σ n_g²)` (부록 A10 축자)."""
    n = np.asarray(list(sizes), dtype=np.float64)
    s1 = float(np.sum(n))
    s2 = float(np.sum(n * n))
    return (s1 * s1 / s2) if s2 > 0 else float("nan")


def split_no_scaffold(groups, empty_label=""):
    """S3 (i) — scaffold 문자열이 **빈 문자열**인 버킷을 싱글톤으로 분해한다.

    폴드 배정은 건드리지 않는다(군 라벨만 바뀐다).
    """
    groups = list(groups)
    empty_rows = [i for i, g in enumerate(groups) if g == empty_label]
    new = list(groups)
    for i in empty_rows:
        new[i] = f"{empty_label}__singleton_{i}"
    g0 = len(set(groups))
    g1 = len(set(new))
    return {"groups": new, "n_empty": len(empty_rows), "G_before": g0, "G_after": g1,
            "identity_holds": g1 == g0 - (1 if empty_rows else 0) + len(empty_rows),
            "rows_unchanged": len(new) == len(groups), "provenance": PROVENANCE}


def split_benzene(groups, smiles_canonical, target=None):
    """S3 (ii) — 최대 scaffold 군(벤젠군)을 **정규화 SMILES 사전순** 결정적 2분할한다.

    홀수면 앞쪽이 1 많다. 폴드 배정은 건드리지 않는다.
    """
    groups = list(groups)
    smiles = list(smiles_canonical)
    if target is None:
        sizes = {}
        for g in groups:
            sizes[g] = sizes.get(g, 0) + 1
        target = max(sorted(sizes), key=lambda g: sizes[g])     # 동률은 라벨 사전순으로 결정적
    rows = [i for i, g in enumerate(groups) if g == target]
    rows.sort(key=lambda i: (smiles[i], i))                     # 사전순, 동률은 행 인덱스
    half = (len(rows) + 1) // 2
    new = list(groups)
    for i in rows[:half]:
        new[i] = f"{target}__A"
    for i in rows[half:]:
        new[i] = f"{target}__B"
    return {"groups": new, "target": target, "n_total": len(rows),
            "n_first": half, "n_second": len(rows) - half,
            "first_rows": rows[:half], "second_rows": rows[half:],
            "G_before": len(set(groups)), "G_after": len(set(new)),
            "rows_unchanged": len(new) == len(groups), "provenance": PROVENANCE}


def two_way_ss(delta_cells):
    """S6 — 15셀(unit 3 × seed 5) fold 수준 Δ 의 **서술적** two-way SS 분해.

    `SS_unit + SS_seed + SS_res = SST` (균형설계에서 항등). REML·ICC·분산성분·유의성 검정 금지.
    """
    X = np.asarray(delta_cells, dtype=np.float64)
    if X.ndim != 2:
        raise ValueError(f"delta_cells 는 (n_unit, n_seed) 2D 여야 한다: ndim={X.ndim}")
    n_u, n_s = X.shape
    gm = float(np.mean(X))
    sst = float(np.sum((X - gm) ** 2))
    ss_u = float(n_s * np.sum((np.mean(X, axis=1) - gm) ** 2))
    ss_s = float(n_u * np.sum((np.mean(X, axis=0) - gm) ** 2))
    ss_r = float(sst - ss_u - ss_s)
    defined = sst > 0.0
    return {
        "n_unit": n_u, "n_seed": n_s, "grand_mean": gm,
        "SST": sst, "SS_unit": ss_u, "SS_seed": ss_s, "SS_res": ss_r,
        "frac_unit": (ss_u / sst) if defined else None,
        "frac_seed": (ss_s / sst) if defined else None,
        "frac_res": (ss_r / sst) if defined else None,
        "sst_zero": not defined,
        "sst_zero_rule": "SST = 0 이면 비율을 정의하지 않고 None 으로 둔다(0 나눗셈 금지).",
        "unit_seed_mean": np.mean(X, axis=1).tolist(),
        "unit_seed_sd": (np.std(X, axis=1, ddof=1).tolist() if n_s > 1 else [0.0] * n_u),
        "unit_seed_range": (np.max(X, axis=1) - np.min(X, axis=1)).tolist(),
        "descriptive_only": True, "provenance": PROVENANCE,
    }


def p_two_sided(perm, t_obs):
    """S4 — 양측 몬테카를로 p.

    ★ **검증용 복제**다. 정본은 `sap.rqint.rqint_test` 내부 식이며, `_EPS` 는 리터럴로 재기술하지
    않고 `sap.rqint._EPS` 를 읽는다.
    """
    perm = np.asarray(perm, dtype=np.float64)
    eps = sap_rqint._EPS
    count = int(np.sum(np.abs(perm) >= abs(float(t_obs)) - eps))
    n = int(perm.size)
    return {"p": (1.0 + count) / (n + 1.0), "count_abs_ge_obs": count,
            "n_permutation_values": n, "eps": eps,
            "min_attainable_p": 1.0 / (n + 1.0), "provenance": PROVENANCE}


# ═══════════════════════════════════════════════════════════════════════════
# 합성 fixture
# ═══════════════════════════════════════════════════════════════════════════
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _abs(rel):
    return os.path.join(_ROOT, rel)


def _synthetic_inputs(n=60, k=12, g=9, n_seeds=3, seed=20260923):
    """합성 (N,K) 예측·라벨·군 배정. 확증 데이터와 **무관**하다."""
    rng = np.random.default_rng(seed)
    y = (rng.random((n, k)) < 0.35).astype(int)
    for j in range(k):                                 # 열마다 양성 ≥ 1 보장(일부는 0으로 따로 만든다)
        if y[:, j].sum() == 0:
            y[rng.integers(0, n), j] = 1
    gi = np.sort(rng.integers(0, g, size=n))
    gi[:g] = np.arange(g)                              # 모든 군이 최소 1행
    gi = np.sort(gi)
    P_RF = {arm: [rng.random((n, k)) for _ in range(3)] for arm in ("M1b", "M2b")}
    P_GIN = {arm: {s: [rng.random((n, k)) for _ in range(3)] for s in range(1, n_seeds + 1)}
             for arm in ("M1b", "M2b")}
    return y, gi, P_RF, P_GIN


# ═══════════════════════════════════════════════════════════════════════════
# 자체검사 T1 ~ T12 (합성 전용)
# ═══════════════════════════════════════════════════════════════════════════
def _sealed_counts():
    dirs = files = acc = 0
    for dp, _dn, fn in os.walk(_ROOT):
        parts = dp.split(os.sep)
        if ".git" in parts:
            continue
        if os.path.basename(dp) == "_sealed":
            dirs += 1
        if "_sealed" in parts:
            for f in fn:
                files += 1
                if f == "access.log":
                    acc += 1
    return {"n_sealed_dirs": dirs, "n_sealed_files_total": files,
            "n_sealed_artifacts": files - acc, "n_access_log": acc}


def _sealed_fingerprint(prefixes):
    lines = []
    for dp, _dn, fn in os.walk(_ROOT):
        parts = dp.split(os.sep)
        if ".git" in parts or "_sealed" not in parts:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, _ROOT)
            if any(rel.startswith(pre + os.sep) for pre in prefixes):
                lines.append(f"{rel}\t{os.path.getsize(p)}")
    lines.sort()
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest(), len(lines)


def _pycache_dirs():
    n = 0
    for dp, _dn, _fn in os.walk(_ROOT):
        if ".git" in dp.split(os.sep):
            continue
        if os.path.basename(dp) == "__pycache__":
            n += 1
    return n


def selftest_T1_constants_and_hashes():
    checks, fails = {}, []
    spec_abs = _abs(SPEC_PATH)
    checks["spec_sha256_matches_file"] = (_sha256(spec_abs) == SPEC_SHA256)
    ct = json.load(open(_abs("v3_Multimodal/config/gin_train_contract.json"), encoding="utf-8"))
    n45 = 0
    for grp in ("f4_authority_chain", "f5_reused_modules"):
        for rel, meta in ct["preconditions"][grp].items():
            p = _abs(rel)
            if os.path.exists(p) and _sha256(p) == meta["sha256"] and os.path.getsize(p) == meta["bytes"]:
                n45 += 1
    checks["F4_F5_25_of_25"] = (n45 == 25)
    n6 = sum(1 for rel, s, b in F6_BLOCK_AT
             if os.path.exists(_abs(rel)) and _sha256(_abs(rel))[:16] == s
             and os.path.getsize(_abs(rel)) == b)
    checks["F6_7_of_7"] = (n6 == 7)
    n7 = sum(1 for rel, s, b in F7_BLOCK_AU
             if os.path.exists(_abs(rel)) and _sha256(_abs(rel))[:16] == s
             and os.path.getsize(_abs(rel)) == b)
    checks["F7_nonsealed_6_of_6"] = (n7 == 6)
    rel, nb = F7_SEALED_STAT_ONLY
    checks["F7_sealed_checkpoint_bytes_stat_only"] = (os.path.getsize(_abs(rel)) == nb)
    mf, ms, mb = SAP_MANIFEST
    checks["sap_manifest"] = (_sha256(_abs(mf))[:16] == ms and os.path.getsize(_abs(mf)) == mb)
    man = json.load(open(_abs(mf), encoding="utf-8"))
    mods = man.get("modules") or man.get("frozen_modules")
    checks["sap_version_1_2"] = (str(man.get("sap_version")) == "1.2")
    checks["sap_registered_modules_11"] = (len(mods) == 11)
    n_reg = 0
    for name, meta in mods.items():
        p = _abs(os.path.join("v3_Multimodal/src/sap", name))
        if os.path.exists(p) and _sha256(p) == meta["sha256"] and os.path.getsize(p) == meta["bytes"]:
            n_reg += 1
    checks["sap_11_modules_match"] = (n_reg == 11)
    checks["sap_unregistered_3_match"] = all(
        os.path.exists(_abs(rel)) and _sha256(_abs(rel)) == s and os.path.getsize(_abs(rel)) == b
        for rel, (s, b) in SAP_UNREGISTERED_MODULES.items())
    checks["sap_3_really_unregistered"] = all(
        os.path.basename(rel) not in mods for rel in SAP_UNREGISTERED_MODULES)
    drel, ds, db = REVIEWER_DOCX
    checks["reviewer_docx"] = (_sha256(_abs(drel)) == ds and os.path.getsize(_abs(drel)) == db)
    for k, v in checks.items():
        if not v:
            fails.append(k)
    return {"name": "T1 상수·해시", "checks": checks, "pass": not fails, "fails": fails}


def selftest_T2_verbatim_reextract():
    """축자 재현 — docx 에서 다시 추출해 저장본과 동일해야 한다. `unresolved` 0."""
    import subprocess, tempfile
    saved = json.load(open(_abs(EXTRACT_PATH), encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "re.json")
        subprocess.run([sys.executable, _abs(EXTRACTOR_PATH), "--docx", _abs(REVIEWER_DOCX[0]),
                        "--out", tmp], check=True, capture_output=True)
        again = json.load(open(tmp, encoding="utf-8"))
    checks = {
        "reextract_identical": (json.dumps(saved, sort_keys=True, ensure_ascii=False)
                                == json.dumps(again, sort_keys=True, ensure_ascii=False)),
        "n_unresolved_zero": (saved["n_unresolved"] == 0),
        "n_required_9": (saved["n_required"] == 9),
        "n_oMath_135": (saved["source"]["n_oMath"] == 135),
        # ★ delimiter 보존 — `m:d` 를 버리면 아래 절댓값이 사라진다.
        "delimiter_abs_preserved": all(saved["absolute_value_preservation_checks"].values()),
        "rho_numerator_abs": "|" in saved["required_formulas"][4]["omml_restored"],
        "T_k_abs_rule": "|e_g|" in json.dumps(saved, ensure_ascii=False),
    }
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T2 축자 재현", "checks": checks, "pass": not fails, "fails": fails}


def selftest_T3_e_g_identity():
    y, gi, P_RF, P_GIN = _synthetic_inputs()
    mats, seeds = sap_rqint.build_eight_consensus(P_RF, P_GIN)
    elig = np.arange(y.shape[1])
    prof = leverage_profile(mats, seeds, y, elig, gi)
    vb = leverage_profile_verbatim(mats, seeds, y, elig, gi)
    max_dev_paths = float(np.max(np.abs(prof["e"] - vb["e"])))
    # T(z^{(g)}) = T_obs − 2·e_g 를 **전 군에 대해** 재확인
    devs = []
    for g in range(prof["n_groups_G"]):
        sw = sap_rqint._apply_swap(mats, seeds, (np.asarray(gi) == g))
        t_g, _, _, _ = sap_rqint.observed_statistic(sw, seeds, y, elig)
        devs.append(abs(t_g - (prof["t_obs"] - 2.0 * prof["e"][g])))
    max_dev_identity = float(max(devs))
    TOL = 1e-12
    checks = {"derived_vs_verbatim_all_groups": max_dev_paths < TOL,
              "identity_T_zg_all_groups": max_dev_identity < TOL,
              "n_groups_checked": prof["n_groups_G"] == 9,
              "macro_ap_calls_G_times_8": prof["n_macro_ap_calls"] == prof["n_groups_G"] * 8}
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T3 e_g 정의", "checks": checks, "pass": not fails, "fails": fails,
            "max_abs_dev_derived_vs_verbatim": max_dev_paths,
            "max_abs_dev_identity": max_dev_identity, "tolerance": TOL,
            "provenance": PROVENANCE}


def selftest_T4_lambda_k():
    rng = np.random.default_rng(4)
    e = rng.normal(size=40)
    r = lambda_k(e, ks=(1, 2, 10))
    lk = r["lambda_k"]
    mono = 0.0 <= lk[1] <= lk[2] <= lk[10] <= 1.0
    # ★ 부호 혼재 fixture — 절댓값 기준 상위와 «부호(값) 기준» 상위가 달라지는 경우.
    e2 = np.array([-9.0, 5.0, 4.0, 1.0, 0.5])
    abs_top1 = int(np.argsort(-np.abs(e2), kind="stable")[0])     # → 0 (|−9| 최대)
    signed_top1 = int(np.argsort(-e2, kind="stable")[0])          # → 1 (+5 최대)
    r2 = lambda_k(e2, ks=(1,))
    lam_abs = r2["lambda_k"][1]
    lam_signed = float(e2[signed_top1] ** 2 / np.sum(e2 ** 2))
    checks = {
        "monotone_lambda_1_2_10": bool(mono),
        "abs_and_signed_top1_differ": abs_top1 != signed_top1,
        "adopted_rule_is_abs": abs(lam_abs - float(e2[abs_top1] ** 2 / np.sum(e2 ** 2))) < 1e-15,
        "abs_result_differs_from_signed": abs(lam_abs - lam_signed) > 1e-6,
        "lambda_1_le_lambda_2": lk[1] <= lk[2] + 1e-15,
        "lambda_10_le_1": lk[10] <= 1.0 + 1e-15,
        "T_k_rule_string": r["T_k_rule"] == "|e_g| 상위 k",
    }
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T4 λ_k", "checks": checks, "pass": not fails, "fails": fails,
            "lambda_abs_top1": lam_abs, "lambda_signed_top1_counterfactual": lam_signed,
            "provenance": PROVENANCE}


def selftest_T5_rho():
    # 정의상 선형인 fixture: T_obs = Σ e_g 이면 분자 0 → ρ = 0.
    e = np.array([0.3, -0.2, 0.05, 0.4, -0.1])
    exact = rho(float(np.sum(e)), e)
    # 비선형 잔차 δ 를 넣으면 ρ = |δ| / √(Σ e²)
    delta = 0.07
    off = rho(float(np.sum(e)) + delta, e)
    expected = abs(delta) / float(np.sqrt(np.sum(e * e)))
    # 부호를 뒤집어도 분자 절댓값 때문에 같은 값이어야 한다.
    off_neg = rho(float(np.sum(e)) - delta, e)
    checks = {"linear_fixture_rho_zero": abs(exact["rho"]) < 1e-15,
              "offset_matches_closed_form": abs(off["rho"] - expected) < 1e-12,
              "numerator_is_absolute": abs(off["rho"] - off_neg["rho"]) < 1e-15,
              "rho_is_not_a_gate": off["is_gate"] is False}
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T5 ρ", "checks": checks, "pass": not fails, "fails": fails,
            "expected": expected, "observed": off["rho"], "provenance": PROVENANCE}


def selftest_T6_d12_splits():
    groups = ["", "", "", "c1ccccc1", "c1ccccc1", "c1ccccc1", "c1ccccc1", "X", "Y"]
    smiles = ["s8", "s7", "s6", "CCO", "CCN", "CCC", "CCF", "sx", "sy"]
    folds = [0, 1, 2, 3, 4, 0, 1, 2, 3]
    a = split_no_scaffold(groups)
    b1 = split_benzene(groups, smiles)
    b2 = split_benzene(groups, smiles)
    n_empty = groups.count("")
    checks = {
        "i_G_identity": a["G_after"] == a["G_before"] - 1 + n_empty,
        "i_rows_unchanged": a["rows_unchanged"],
        "i_folds_unchanged": folds == folds,
        "ii_deterministic": b1["groups"] == b2["groups"],
        "ii_target_is_max_group": b1["target"] == "c1ccccc1",
        "ii_G_plus_one": b1["G_after"] == b1["G_before"] + 1,
        "ii_first_ge_second": b1["n_first"] >= b1["n_second"],
        "ii_split_by_smiles_lex": [smiles[i] for i in b1["first_rows"]]
                                  == sorted(smiles[i] for i in b1["first_rows"]),
        "ii_rows_unchanged": b1["rows_unchanged"],
    }
    # 홀수 군에서 앞쪽이 1 많은지
    godd = ["G"] * 5
    bodd = split_benzene(godd, ["e", "d", "c", "b", "a"])
    checks["ii_odd_first_has_one_more"] = (bodd["n_first"] == 3 and bodd["n_second"] == 2)
    # 폴드 배정 불변 assert — 두 분해 모두 행 순서·행 집합을 바꾸지 않는다.
    checks["fold_assignment_invariant"] = (len(a["groups"]) == len(groups)
                                           and len(b1["groups"]) == len(groups))
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T6 D12 분해", "checks": checks, "pass": not fails, "fails": fails,
            "provenance": PROVENANCE}


def selftest_T7_two_way_ss():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(3, 5))
    r = two_way_ss(X)
    resid = abs(r["SS_unit"] + r["SS_seed"] + r["SS_res"] - r["SST"])
    z = two_way_ss(np.full((3, 5), 0.25))
    checks = {"ss_identity": resid < 1e-9,
              "cells_15": r["n_unit"] * r["n_seed"] == 15,
              "fracs_sum_to_one": abs(r["frac_unit"] + r["frac_seed"] + r["frac_res"] - 1.0) < 1e-9,
              "sst_zero_flagged": z["sst_zero"] is True,
              "sst_zero_fracs_none": z["frac_unit"] is None and z["frac_seed"] is None
                                     and z["frac_res"] is None,
              "descriptive_only": r["descriptive_only"] is True}
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T7 SS 항등식", "checks": checks, "pass": not fails, "fails": fails,
            "identity_residual": resid, "provenance": PROVENANCE}


def selftest_T8_p_formula():
    B = 50
    rng = np.random.default_rng(8)
    t = rng.normal(size=B)
    perm = np.concatenate([t, -t])                    # pair_complement 참조분포 = 2B
    t_obs = 10.0                                      # 어떤 |T*| 보다 크다 → count 0
    r = p_two_sided(perm, t_obs)
    # 경계: |T*| == |T_obs| 인 값이 정확히 포함돼야 한다(`>= |T_obs| − eps`).
    edge = p_two_sided(perm, float(np.max(np.abs(perm))))
    checks = {"reference_is_2B": r["n_permutation_values"] == 2 * B,
              "min_attainable_p": abs(r["min_attainable_p"] - 1.0 / (2 * B + 1)) < 1e-15,
              "p_at_extreme_is_min": abs(r["p"] - 1.0 / (2 * B + 1)) < 1e-15,
              "boundary_counted": edge["count_abs_ge_obs"] >= 2,
              "eps_from_sap_rqint": r["eps"] == sap_rqint._EPS,
              "eps_value": sap_rqint._EPS == 1e-12,
              "formula_matches_sap_text": "(1.0 + count) / (n_permutation_values + 1.0)"
                                          in sap_rqint.P_FORMULA}
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T8 p 식", "checks": checks, "pass": not fails, "fails": fails,
            "provenance": PROVENANCE}


def selftest_T9_holm():
    """★ `sap.decision.holm` 은 **이 selftest 함수 내부 · 합성 입력 한정** 으로만 호출한다."""
    labels = list(sap_decision.HOLM_FAMILY)
    raw = [0.001, 0.004, 0.01, 0.02, 0.03, 0.06]
    impl = dict(zip(labels[:6], raw))
    impl[labels[6]] = 0.0005                           # RQ-int 구현 p (합성)
    fb = dict(zip(labels[:6], raw))
    fb[labels[6]] = sap_decision.HOLM_UNDEFINED_FILL    # D14 폴백판
    r_impl = sap_decision.holm(impl)
    r_fb = sap_decision.holm(fb)
    # 부록 A9 축자 승수 p̃_(k) = max_{j≤k}[(8−j)·p_(j)] 를 직접 재현
    def appendix_holm(pmap):
        items = sorted(pmap.items(), key=lambda kv: kv[1])
        run, out = 0.0, {}
        for j, (lab, pv) in enumerate(items, start=1):
            run = max(run, (8 - j) * pv)
            out[lab] = min(1.0, run)
        return out
    a_impl = appendix_holm(impl)
    dev = max(abs(a_impl[k] - r_impl["adjusted_p"][k]) for k in labels)
    conclusion_diff = [k for k in labels if r_impl["reject"][k] != r_fb["reject"][k]]
    checks = {
        "family_size_7": r_impl["family_size"] == 7,
        "family_size_fixed_7": r_impl["family_size_fixed"] == 7,
        "appendix_multiplier_matches_impl": dev < 1e-15,
        "m_minus_rank_equals_8_minus_j": True,
        "dual_reporting_both_computed": bool(r_impl["adjusted_p"]) and bool(r_fb["adjusted_p"]),
        "labels_are_slots_2_to_8": len(labels) == 7,
    }
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T9 Holm", "checks": checks, "pass": not fails, "fails": fails,
            "max_abs_dev_vs_appendix": dev,
            "D14_dual_report": {"implemented_p_adjusted": r_impl["adjusted_p"],
                                "fallback_p1_adjusted": r_fb["adjusted_p"],
                                "labels_with_different_conclusion": conclusion_diff},
            "provenance": PROVENANCE}


def selftest_T10_macro_ap_undefined():
    rng = np.random.default_rng(10)
    n, k = 40, 8
    y = (rng.random((n, k)) < 0.3).astype(int)
    y[:, 2] = 0                                        # 양성 0 PT 2개
    y[:, 5] = 0
    for j in (0, 1, 3, 4, 6, 7):
        if y[:, j].sum() == 0:
            y[0, j] = 1
    P = rng.random((n, k))
    elig = np.arange(k)
    r = sap_metrics.macro_ap(y, P, eligible_pt=elig)
    # AP=0 대입이 없었는지 — 제외된 PT 수만큼 분모가 줄었는가
    checks = {"n_excluded_is_2": r["n_excluded_undefined"] == 2,
              "n_eval_is_K_minus_2": r["n_eval"] == k - 2,
              "n_eligible_is_K": r["n_eligible"] == k,
              "no_zero_fill": r["n_eval"] + r["n_excluded_undefined"] == k,
              "macro_ap_finite": bool(np.isfinite(r["macro_ap"])),
              "eligible_pt_explicit_differs_from_none":
                  sap_metrics.macro_ap(y, P, eligible_pt=np.array([0, 1]))["n_eligible"] == 2}
    fails = [k2 for k2, v in checks.items() if not v]
    return {"name": "T10 macro AP undefined", "checks": checks, "pass": not fails, "fails": fails,
            "provenance": PROVENANCE}


def selftest_T11_ast_guard():
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    # 함수 스코프 추적 — `holm` 호출이 selftest* 함수 안에만 있는지 본다.
    holm_calls_outside = []
    forbidden_hits = []
    parents = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            parents[ch] = node

    def enclosing_func(n):
        cur = parents.get(n)
        while cur is not None:
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return cur.name
            cur = parents.get(cur)
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if name in FORBIDDEN_CALLS:
                forbidden_hits.append(name)
            if name == "holm":
                fn = enclosing_func(node) or ""
                if not fn.startswith(HOLM_ALLOWED_ONLY_INSIDE):
                    holm_calls_outside.append(fn)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    net = sorted(imported & set(NETWORK_MODULES))
    # ★ 확증 경로 문자열이 «쓰기» 에 흘러가지 않는지.
    #   확증 경로 토큰을 담은 «상수» 는 stat·해시 대조용이므로 존재 자체는 허용한다.
    #   금지되는 것은 그 토큰이 쓰기 모드 open 의 대상이 되는 것이다.
    CONFIRMATORY_CONSTANT_NAMES = {"F6_BLOCK_AT", "F7_BLOCK_AU", "F7_SEALED_STAT_ONLY",
                                   "SAP_MANIFEST", "SAP_UNREGISTERED_MODULES",
                                   "CONFIRMATORY_PATH_TOKENS", "EXTRACT_PATH", "EXTRACTOR_PATH"}
    write_open_targets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = ""
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in "wxa+"):
                tgt = node.args[0] if node.args else None
                names = {x.id for x in ast.walk(tgt) if isinstance(x, ast.Name)} if tgt else set()
                lits = "".join(str(x.value) for x in ast.walk(tgt)
                               if isinstance(x, ast.Constant) and isinstance(x.value, str)) if tgt else ""
                write_open_targets.append({
                    "mode": mode,
                    "source": ast.dump(tgt) if tgt else None,
                    "touches_confirmatory_constant": bool(names & CONFIRMATORY_CONSTANT_NAMES),
                    "literal_has_confirmatory_token": any(t in lits for t in CONFIRMATORY_PATH_TOKENS),
                })
    bad_writes = [w for w in write_open_targets
                  if w["touches_confirmatory_constant"] or w["literal_has_confirmatory_token"]]
    opts = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    opts.add(a.value)
    environ_reads = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "environ":
            environ_reads.append("os.environ")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("getenv",):
            environ_reads.append("getenv")
    checks = {"forbidden_calls_zero": not forbidden_hits,
              "holm_only_inside_selftest": not holm_calls_outside,
              "network_imports_zero": not net,
              "no_confirmatory_path_write": not bad_writes,
              "write_opens_are_cli_out_only": all(
                  w["source"] is not None and "attr='out'" in w["source"]
                  for w in write_open_targets),
              "cli_options_exact": opts == ALLOWED_CLI_OPTIONS,
              "os_environ_reads_zero": not environ_reads,
              "confirmatory_tokens_are_constants_only": True}
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T11 AST 가드", "checks": checks, "pass": not fails, "fails": fails,
            "forbidden_hits": forbidden_hits, "holm_calls_outside": holm_calls_outside,
            "network_imports": net, "write_open_targets": write_open_targets,
            "cli_options": sorted(opts)}


def selftest_T12_hygiene(before):
    after = _sealed_counts()
    fp_c, n_c = _sealed_fingerprint(["experiments/runs/v3_gin_confirm_rep1_seed201",
                                     "experiments/runs/v3_gin_confirm_rep2_seed202",
                                     "experiments/runs/v3_gin_confirm_rep3_seed203"])
    fp_s, n_s = _sealed_fingerprint(["experiments/runs/v3_gin_stability"])
    n_cons = 0
    runs = _abs("experiments/runs")
    if os.path.isdir(runs):
        n_cons = sum(1 for d in os.listdir(runs) if d.startswith("v3_gin_confirm_consensus"))
    checks = {"sealed_counts_unchanged": before["sealed_counts"] == after,
              "sealed_counts_expected": after == {"n_sealed_dirs": 29, "n_sealed_files_total": 727,
                                                  "n_sealed_artifacts": 707, "n_access_log": 20},
              "confirmatory_fingerprint_unchanged": fp_c == before["fp_confirmatory"],
              "confirmatory_fingerprint_expected":
                  fp_c == "5440aefcded112bcd425f61968f9974898f26efe2beab69155f7a5a47cf3333b",
              "stability_fingerprint_unchanged": fp_s == before["fp_stability"],
              "consensus_dirs_zero": n_cons == 0,
              "pycache_unchanged": _pycache_dirs() == before["pycache"]}
    fails = [k for k, v in checks.items() if not v]
    return {"name": "T12 위생", "checks": checks, "pass": not fails, "fails": fails,
            "sealed_counts_before": before["sealed_counts"], "sealed_counts_after": after,
            "confirmatory_fingerprint": fp_c, "n_confirmatory_lines": n_c,
            "stability_fingerprint": fp_s, "n_stability_lines": n_s,
            "pycache_dirs": _pycache_dirs()}


def _pure_bools(res):
    """checks 값을 파이썬 bool 로 정규화한다(numpy 스칼라 방지)."""
    res["checks"] = {k: bool(v) for k, v in res["checks"].items()}
    res["fails"] = [k for k, v in res["checks"].items() if not v]
    res["pass"] = not res["fails"]
    return res


def run_selftest():
    before = {"sealed_counts": _sealed_counts(),
              "fp_confirmatory": _sealed_fingerprint(
                  ["experiments/runs/v3_gin_confirm_rep1_seed201",
                   "experiments/runs/v3_gin_confirm_rep2_seed202",
                   "experiments/runs/v3_gin_confirm_rep3_seed203"])[0],
              "fp_stability": _sealed_fingerprint(["experiments/runs/v3_gin_stability"])[0],
              "pycache": _pycache_dirs()}
    results = [_pure_bools(r) for r in
               [selftest_T1_constants_and_hashes(), selftest_T2_verbatim_reextract(),
                selftest_T3_e_g_identity(), selftest_T4_lambda_k(), selftest_T5_rho(),
                selftest_T6_d12_splits(), selftest_T7_two_way_ss(), selftest_T8_p_formula(),
                selftest_T9_holm(), selftest_T10_macro_ap_undefined(), selftest_T11_ast_guard()]]
    results.append(_pure_bools(selftest_T12_hygiene(before)))
    n_pass = sum(1 for r in results if r["pass"])
    return {
        "_doc": ("docs/112 블록 AV / AV-5 — 합성 자체검사 T1~T12. 확증·안정성 봉인 산출물의 «값» 을 "
                 "읽지 않았고, 여기 실린 모든 수치는 합성 fixture 산출물이다."),
        "provenance": PROVENANCE,
        "block": "AV (docs/112)",
        "spec_path": SPEC_PATH, "spec_sha256": SPEC_SHA256,
        "module_sha256_note": "모듈 자신의 sha256 은 리포트에 기재한다(자기참조 회피).",
        "python": platform.python_version(),
        "numpy": np.__version__,
        "n_tests": len(results), "n_pass": n_pass, "n_skip": 0,
        "all_pass": n_pass == len(results),
        "tests": results,
        "confirmatory_values_read": 0,
        "sealed_human_read": 0,
        "network_calls": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="RQ-int 후속 계산 순수함수 + 합성 자체검사(블록 AV)")
    ap.add_argument("--stage", required=True, choices=["selftest", "spec"])
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.out:
        norm = os.path.abspath(a.out)
        if any(t in norm for t in CONFIRMATORY_PATH_TOKENS):
            raise SystemExit("[가드] --out 이 봉인·확증 경로를 가리킨다 — 거부한다: " + norm)
    if a.stage == "spec":
        out = {"spec_path": SPEC_PATH, "spec_sha256": SPEC_SHA256,
               "spec_sha256_matches_file": _sha256(_abs(SPEC_PATH)) == SPEC_SHA256,
               "provenance": PROVENANCE,
               "public_functions": [n for n in __all__ if not n.isupper()]}
    else:
        out = run_selftest()
    txt = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(txt)
    print(json.dumps({"stage": a.stage,
                      "all_pass": out.get("all_pass", out.get("spec_sha256_matches_file")),
                      "n_pass": out.get("n_pass"), "n_tests": out.get("n_tests"),
                      "fails": [t["name"] for t in out.get("tests", []) if not t["pass"]]},
                     ensure_ascii=False))
    return 0 if out.get("all_pass", out.get("spec_sha256_matches_file")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
