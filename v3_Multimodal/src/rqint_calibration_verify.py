#!/usr/bin/env python3
"""rqint_calibration_verify.py — [블록 AE] A21 **독립 검증 스크립트**.

⛔ 독립성 규약 (지시서 `docs/93` AE-7)
  · 본 스크립트는 **`rqint_calibration.py` 를 import 하지 않는다.** `sap/` 도 import 하지 않는다.
  · 본런 산출(JSON·JSONL)의 **복제별 p 원값만** 읽어 기각률·Wilson CI·KS 를 **독립 구현**으로
    재계산하고, 본런이 기록한 값과 대조한다.
  · 시드 규칙·셀 정의도 **문면(지시서 AE-1·AE-2)에서 재구성**해 본런 rep_seed 와 대조한다.
  · 데이터 파일·확증 산출물·`_sealed/` 를 **일절 열지 않는다**(합성 p 값만 다룬다).
  · 판정을 바꾸지 않는다 — 불일치는 보고한다.

실행:
  .venv/bin/python3 v3_Multimodal/src/rqint_calibration_verify.py
"""
from __future__ import annotations

import os
import sys
import ast
import json
import math
import hashlib
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(ROOT, "experiments", "rqint")
CKPT_DIR = os.path.join(OUT_DIR, "_ckpt")

ALPHA = 0.05
POINTS = {"alpha": ALPHA, "alpha_over_7": ALPHA / 7.0, "alpha_over_4": ALPHA / 4.0}
Z95 = 1.959963984540054

# ── 지시서 문면에서 재구성한 셀·시드 규약 (본런 코드 미참조) ──────────────────────
BASE_SEED = 20260813
SCEN_IDX = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4}
VAR_OFF = {"prop": 0, "ratio": 500_000, "full": 0}
TAU_GRID = (0.01, 0.02, 0.03)
CELLS = ([{"cell": f"{s}:{v}", "scen": s, "var": v, "gi": 0,
           "R": (2000 if v == "prop" else 1000), "ncoin": 2000}
          for s in ("C0", "C1", "C2", "C3") for v in ("prop", "ratio")]
         + [{"cell": f"C4:tau{t}", "scen": "C4", "var": "full", "gi": i, "R": 400, "ncoin": 1000}
            for i, t in enumerate(TAU_GRID)])

ALLOWED_DATA_LITERALS = ("master_X.parquet", "master_Y.parquet")
FORBIDDEN_LITERAL_TOKENS = ("oof_", "_sealed", "confirmatory_oof_rep1.py", "p_emp", "T_obs.json",
                            "scaffold_split.json")
DATA_EXT = (".parquet", ".npy", ".pt", ".csv", ".pkl", ".feather")
ARTIFACT_EXT = (".json", ".jsonl", ".log", ".md", ".py")
# 본 검증 스크립트 자신의 **가드 토큰 상수**는 스캔에서 제외한다(선언적 예외 · 출력에 명시).
GUARD_CONST_NAMES = ("ALLOWED_DATA_LITERALS", "FORBIDDEN_LITERAL_TOKENS", "DATA_EXT",
                     "ARTIFACT_EXT", "GUARD_CONST_NAMES")


# ══════════════════════════════════════════════════════════════════════════════
# 독립 통계 구현
# ══════════════════════════════════════════════════════════════════════════════
def wilson(k, n, z=Z95):
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    den = 1.0 + z * z / n
    ctr = (ph + z * z / (2.0 * n)) / den
    hw = (z / den) * math.sqrt(ph * (1.0 - ph) / n + z * z / (4.0 * n * n))
    return (ctr - hw, ctr + hw)


def rejection(pvals, thr):
    k = sum(1 for v in pvals if v <= thr)
    n = len(pvals)
    r = k / n
    se = math.sqrt(max(r * (1.0 - r), 0.0) / n)
    return {"k": k, "n": n, "rate": r, "se": se, "bound": ALPHA + 2.0 * se,
            "wilson95": list(wilson(k, n))}


def ks_uniform(pvals):
    """독립 구현 — 단측 D 통계량 + Kolmogorov 점근 p (scipy 미사용)."""
    x = sorted(pvals)
    n = len(x)
    d = 0.0
    for i, v in enumerate(x, start=1):
        d = max(d, i / n - v, v - (i - 1) / n)
    lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * d
    s, k = 0.0, 1
    while k <= 200:
        s += ((-1) ** (k - 1)) * math.exp(-2.0 * k * k * lam * lam)
        k += 1
    p = max(0.0, min(1.0, 2.0 * s))
    return {"statistic": d, "p_value": p, "lambda": lam,
            "implementation": "hand-rolled two-sided KS + Kolmogorov asymptotic Q(λ) (no scipy)"}


# ══════════════════════════════════════════════════════════════════════════════
def read_ckpt(cell):
    p = os.path.join(CKPT_DIR, f"calibration_{cell.replace(':', '_')}.jsonl")
    if not os.path.exists(p):
        return []
    rows = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def verify_cells():
    out, sumf = {}, os.path.join(OUT_DIR, "calibration_summary.json")
    summary = json.load(open(sumf)) if os.path.exists(sumf) else {"cells": {}}
    for c in CELLS:
        rows = read_ckpt(c["cell"])
        rec = {"n_rows": len(rows), "expected_R": c["R"]}
        if not rows:
            rec["status"] = "not_run"
            out[c["cell"]] = rec
            continue
        seeds = [r["rep_seed"] for r in rows]
        rec["duplicate_rep_seeds"] = len(seeds) - len(set(seeds))
        expect = [BASE_SEED + 1_000_000 * SCEN_IDX[c["scen"]] + VAR_OFF[c["var"]]
                  + 100_000 * c["gi"] + r for r in range(c["R"])]
        rec["seed_rule_conformant"] = set(seeds).issubset(set(expect))
        rec["ncoin_all_expected"] = all(r["n_coin_vectors"] == c["ncoin"] for r in rows)
        rec["nperm_is_2x_ncoin"] = all(r["n_permutation_values"] == 2 * c["ncoin"] for r in rows)
        p = [r["p_two_sided"] for r in rows]
        rec["p_in_unit_interval"] = all(0.0 < v <= 1.0 for v in p)
        rec["rates_recomputed"] = {k: rejection(p, thr) for k, thr in POINTS.items()}
        if c["scen"] == "C0":
            rec["ks_recomputed"] = ks_uniform(p)
        if c["scen"] == "C4":
            k = sum(1 for v in p if v <= ALPHA)
            rec["power_recomputed"] = {"power": k / len(p), "wilson95": list(wilson(k, len(p)))}
            if len(p) >= 200:
                k2 = sum(1 for v in p[:200] if v <= ALPHA)
                lo, hi = wilson(k2, 200)
                rec["A12_interim_recomputed"] = {
                    "power": k2 / 200, "wilson95": [lo, hi],
                    "crosses_0.50": bool(lo < 0.50 < hi), "crosses_0.80": bool(lo < 0.80 < hi)}
        # 본런 기록과 대조
        mine = summary.get("cells", {}).get(c["cell"])
        if mine and mine.get("status") != "not_run":
            diffs = {}
            for k in POINTS:
                a = mine["rates"][k]["rejection_rate"]
                b = rec["rates_recomputed"][k]["rate"]
                if abs(a - b) > 1e-12:
                    diffs[f"rate:{k}"] = [a, b]
                a = mine["rates"][k]["acceptance_bound_alpha_plus_2SE"]
                b = rec["rates_recomputed"][k]["bound"]
                if abs(a - b) > 1e-12:
                    diffs[f"bound:{k}"] = [a, b]
                a = mine["rates"][k]["wilson95"]
                b = rec["rates_recomputed"][k]["wilson95"]
                if max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 1e-10:
                    diffs[f"wilson:{k}"] = [a, b]
            if "ks_recomputed" in rec and "ks_uniform" in mine:
                if abs(mine["ks_uniform"]["statistic"] - rec["ks_recomputed"]["statistic"]) > 1e-10:
                    diffs["ks_statistic"] = [mine["ks_uniform"]["statistic"],
                                             rec["ks_recomputed"]["statistic"]]
                diffs["ks_pvalue_two_implementations"] = [mine["ks_uniform"]["p_value"],
                                                          rec["ks_recomputed"]["p_value"]]
            if set(mine.get("p_values_raw", [])) != set(p):
                diffs["p_array_mismatch"] = True
            rec["mismatches_vs_main_run"] = diffs
        rec["status"] = "complete" if len(rows) >= c["R"] else "partial"
        out[c["cell"]] = rec
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 종료검증 #7 — AST 스캔(신규 파일이 여는 데이터 경로)
# ══════════════════════════════════════════════════════════════════════════════
def _guard_const_strings(tree):
    """가드 토큰 상수(모듈 최상위 할당)에 들어 있는 문자열 — 스캔 제외 대상."""
    out = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if not (names & set(GUARD_CONST_NAMES)):
            continue
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                out.add(sub.value)
    return out


def _path_like(s):
    """경로 리터럴 판정 — 공백·개행이 없고(=산문 아님) 경로 구분자나 파일 확장자를 갖는다."""
    if not s or any(ch.isspace() for ch in s):
        return False
    return ("/" in s) or s.endswith(DATA_EXT + ARTIFACT_EXT)


def ast_scan(paths):
    res = {}
    for rel in paths:
        fp = os.path.join(ROOT, rel)
        src = open(fp, encoding="utf-8").read()
        tree = ast.parse(src, filename=rel)
        guard = _guard_const_strings(tree)
        lits = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        paths_lit = sorted(s for s in lits if _path_like(s) and s not in guard)
        data_lits = sorted(s for s in paths_lit if s.endswith(DATA_EXT))
        forbidden = sorted({s for s in paths_lit
                            if any(t in s for t in FORBIDDEN_LITERAL_TOKENS)})
        imports = sorted({(n.module or "") for n in ast.walk(tree)
                          if isinstance(n, ast.ImportFrom)}
                         | {al.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                            for al in n.names})
        res[rel] = {
            "data_file_literals": data_lits,
            "data_literals_only_allowed": (set(data_lits) <= set(ALLOWED_DATA_LITERALS)),
            "artifact_path_literals": sorted(s for s in paths_lit if s not in data_lits),
            "forbidden_literals": forbidden,
            "excluded_guard_constant_strings": sorted(guard),
            "scaffold_of_import_exception": "confirmatory_oof_rep1" in imports,
            "sap_imported": any(i == "sap" or i.startswith("sap.") for i in imports),
            "main_run_module_imported": "rqint_calibration" in imports,
            "imports": imports,
        }
    return res


# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "calibration_verify.json"))
    a = ap.parse_args()

    design_p = os.path.join(OUT_DIR, "calibration_design.json")
    side_p = os.path.join(OUT_DIR, "calibration_design.sha256.json")
    design_sha = hashlib.sha256(open(design_p, "rb").read()).hexdigest() \
        if os.path.exists(design_p) else None
    side = json.load(open(side_p)) if os.path.exists(side_p) else {}

    scan_targets = ["v3_Multimodal/src/rqint_calibration.py",
                    "v3_Multimodal/src/rqint_calibration_verify.py"]
    out = {
        "_doc": "블록 AE / A21 독립 검증 — 본런 함수 미import, p 원값만 읽어 독립 재계산.",
        "block": "AE", "independent_of_main_run": True,
        "main_run_module_imported": False,
        "sap_imported": False,
        "design_sha256_now": design_sha,
        "design_sha256_at_freeze": side.get("sha256"),
        "design_unchanged_since_freeze": (design_sha == side.get("sha256")),
        "design_frozen_at_kst": side.get("frozen_at_kst"),
        "cells": verify_cells(),
        "ast_scan": ast_scan(scan_targets),
    }
    any_mismatch = any(bool(v.get("mismatches_vs_main_run", {}).get(k))
                       for v in out["cells"].values()
                       for k in (v.get("mismatches_vs_main_run") or {})
                       if k != "ks_pvalue_two_implementations")
    out["any_mismatch_vs_main_run"] = bool(any_mismatch)
    out["all_ast_clean"] = all(v["data_literals_only_allowed"] and not v["forbidden_literals"]
                               for v in out["ast_scan"].values())
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({"design_unchanged_since_freeze": out["design_unchanged_since_freeze"],
                      "all_ast_clean": out["all_ast_clean"],
                      "any_mismatch_vs_main_run": out["any_mismatch_vs_main_run"],
                      "cells": {k: {"status": v["status"], "n": v["n_rows"]}
                                for k, v in out["cells"].items()}},
                     ensure_ascii=False, indent=2))
    print("→", a.out)


if __name__ == "__main__":
    main()
