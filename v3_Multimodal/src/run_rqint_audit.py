"""run_rqint_audit.py — 블록 AC 실행 스크립트: RQ-int 구현 R6-1~R6-9 감사 (합성 전용).

⛔ 확증 데이터 접근 0 · 개봉 0 · 모델 학습 0 · 네트워크 0 · 동결 모듈 수정 0.
   모든 수치는 `sap.rqint_synthetic` 합성 fixture 산출물이다.

산출: `experiments/rqint/audit_r6.json` + `experiments/rqint/run.log`
사용: python3 v3_Multimodal/src/run_rqint_audit.py
"""
from __future__ import annotations

import ast
import json
import os
import platform
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

for _k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_k, "1")

import numpy as np                                                 # noqa: E402
import sklearn                                                     # noqa: E402

from sap import rqint as R                                         # noqa: E402  (검사 대상 구현)
from sap import rqint_audit as A                                   # noqa: E402  (독립 검사 코드)
from sap import rqint_synthetic as F                               # noqa: E402  (합성 fixture)

KST = timezone(timedelta(hours=9))
OUT_DIR = os.path.join(ROOT, "experiments", "rqint")
NEW_FILES = ["sap/rqint.py", "sap/rqint_synthetic.py", "sap/rqint_audit.py",
             "run_rqint_audit.py"]

_LOG = []


def logln(msg):
    line = f"[{datetime.now(KST).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG.append(line)


# ═══════════════════════════════════════════════════════════════════════════
# 확증 데이터 미접근 AST 스캔 — freeze.py `code_scan` 과 **동일 규칙**을 신규 4파일에 적용
# ═══════════════════════════════════════════════════════════════════════════
FORBIDDEN_IMPORTS = {"ladder_confirmatory", "preconfirm_hardening", "target_pipeline",
                     "train_ladder", "prep_features", "coverage_mapping"}
DATA_LOAD_ATTRS = {"read_parquet", "read_csv", "read_table", "load_frozen", "loadtxt", "genfromtxt"}
NP_LOAD_ROOTS = {"np", "numpy"}
FORBIDDEN_PATH_LITERALS = ["data/processed", "data/raw", "master_X", "master_Y",
                           "scaffold_split.json", "_meanpool.npy", "confirmatory",
                           "oof_M1b", "oof_M2b", "target_mapping"]


def _call_desc(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id, None
    if isinstance(f, ast.Attribute):
        root = f.value
        while isinstance(root, ast.Attribute):
            root = root.value
        return f.attr, (root.id if isinstance(root, ast.Name) else None)
    return None, None


def _is_data_load(node):
    attr, root = _call_desc(node)
    if attr in DATA_LOAD_ATTRS:
        return attr
    if attr == "load" and root in NP_LOAD_ROOTS:
        return f"{root}.load"
    return None


def code_scan():
    per_file, all_ok = {}, True
    for rel in NEW_FILES:
        src = open(os.path.join(HERE, rel), encoding="utf-8").read()
        tree = ast.parse(src, filename=rel)
        imports, bad_calls, open_lit = set(), [], []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imports.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                dl = _is_data_load(node)
                if dl:
                    bad_calls.append(dl)
                attr, _r = _call_desc(node)
                if attr == "open":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            low = arg.value.lower()
                            if any(t.lower() in low for t in FORBIDDEN_PATH_LITERALS):
                                open_lit.append(arg.value)
        forb = sorted(imports & FORBIDDEN_IMPORTS)
        ok = (not forb) and (not bad_calls) and (not open_lit)
        all_ok = all_ok and ok
        per_file[rel] = {"forbidden_imports": forb, "data_load_calls": sorted(set(bad_calls)),
                         "open_with_data_literal": open_lit,
                         "imports": sorted(i for i in imports if i != "__future__"), "ok": ok}
    logln(f"[스캔] AST 확증데이터 미접근 = {all_ok} (금지 import 0 · data-load call 0 · open 리터럴 0)")
    assert all_ok, f"확증 데이터 접근 코드 발견: {per_file}"
    return {"method": "AST walk (freeze.py code_scan 동일 규칙)", "per_file": per_file,
            "no_confirmatory_data_access": all_ok}


def import_topology():
    """종료검증 #7·#8 — rqint 는 signflip 미import, rqint_audit 는 rqint 미import."""
    def mods(rel):
        tree = ast.parse(open(os.path.join(HERE, rel), encoding="utf-8").read(), filename=rel)
        out = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                out |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                out.add(n.module or "")
                out |= {f"{n.module or ''}.{a.name}" for a in n.names}
        return sorted(out)

    m_rq = mods("sap/rqint.py")
    m_au = mods("sap/rqint_audit.py")
    res = {
        "rqint_imports": m_rq,
        "rqint_audit_imports": m_au,
        "rqint_imports_signflip": any("signflip" in x for x in m_rq),
        "rqint_imports_metrics": any("metrics" in x for x in m_rq),
        "rqint_imports_consensus": any("consensus" in x for x in m_rq),
        "rqint_audit_imports_rqint": any(x == ".rqint" or x.endswith(".rqint")
                                         or x == "rqint" for x in m_au),
    }
    res["pass"] = (not res["rqint_imports_signflip"] and res["rqint_imports_metrics"]
                   and res["rqint_imports_consensus"] and not res["rqint_audit_imports_rqint"])
    logln(f"[토폴로지] rqint←signflip={res['rqint_imports_signflip']} · "
          f"rqint_audit←rqint={res['rqint_audit_imports_rqint']} · pass={res['pass']}")
    return res


def text_checks():
    """종료검증 #9·#10 — assert 8 존재 · _EPS 리터럴 · p 공식 축자 대조."""
    rq = open(os.path.join(HERE, "sap/rqint.py"), encoding="utf-8").read()
    sf = open(os.path.join(HERE, "sap/signflip.py"), encoding="utf-8").read()
    has8 = "assert len(mats) == 8" in rq
    eps_ok = ("_EPS = 1e-12" in rq) and ("_EPS = 1e-12" in sf)
    pform_rq = "count = int(np.sum(np.abs(perm) >= abs(t_obs) - _EPS))" in rq
    pform_sf = "count = int(np.sum(np.abs(perm) >= abs(delta_obs) - _EPS))" in sf
    pdiv_rq = "p = (1.0 + count) / (n_perm_values + 1.0)" in rq
    pdiv_sf = "p = (1.0 + count) / (B + 1.0)" in sf
    res = {"assert_eight_matrices": has8, "eps_literal_matches_signflip": eps_ok,
           "count_formula_rqint": pform_rq, "count_formula_signflip": pform_sf,
           "p_formula_rqint": pdiv_rq, "p_formula_signflip": pdiv_sf}
    res["pass"] = all(res.values())
    logln(f"[텍스트] assert8={has8} · _EPS 일치={eps_ok} · p 공식 축자 계승={pform_rq and pdiv_rq}")
    return res


def main():
    t_start = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    logln("═" * 70)
    logln("블록 AC — RQ-int 검정 구현 + R6 검증 (합성 전용 · 확증 접근 0)")
    logln("═" * 70)

    scan = code_scan()
    topo = import_topology()
    txt = text_checks()
    assert topo["pass"], "import 토폴로지 위반"
    assert txt["pass"], "텍스트 대조 실패"

    # ── fixture (합성 전용 · G 는 감사용 임의값) ───────────────────────────
    fx_zero = F.make_rqint_zero_interaction(seed=11)
    fx_exch = F.make_rqint_exchangeable(seed=12)
    fx_tiny = F.make_rqint_tiny(seed=13)
    logln(f"[fixture] zero N={fx_zero[2].shape[0]} K={fx_zero[2].shape[1]} "
          f"G={len(np.unique(fx_zero[3]))} · tiny G={len(np.unique(fx_tiny[3]))} (임의값)")

    results = {}

    # R6-1 가환성 — 실패 시 중단(설계 전제 붕괴)
    logln("[R6-1] 가환성 단위테스트 (임의 z 100개)")
    results["R6-1"] = A.check_commutativity(fx_exch, n_z=100, seed=1)
    logln(f"        pass={results['R6-1']['pass']} max_abs_diff={results['R6-1']['max_abs_diff']:.3e}")
    assert results["R6-1"]["pass"], "R6-1 실패 → 중단(F-D5 설계 전제 붕괴, 임의 우회 금지)"

    # R6-2 zero-effect → p=1 — 실패 시 중단
    logln("[R6-2] zero-effect → p = 1.0")
    results["R6-2"] = A.check_zero_effect(R, fx_zero, n_coin_vectors=300, seed=2)
    logln(f"        pass={results['R6-2']['pass']} p={results['R6-2']['p']}")
    assert results["R6-2"]["pass"], "R6-2 실패 → 중단(공식·tolerance 계승 오류)"

    # R6-4 여집합 반대칭 (≥1,000 draw)
    logln("[R6-4] 여집합 반대칭 complement_audit (≥1,000 draw 명시적 재계산)")
    results["R6-4"] = A.check_complement_antisymmetry(R, fx_exch, n_coin_vectors=1000, seed=4)
    logln(f"        pass={results['R6-4']['pass']} draws={results['R6-4']['draws_checked']} "
          f"max_dev={results['R6-4']['max_abs_dev']:.3e}")

    # R6-5 전체 교환
    logln("[R6-5] 전체 교환 보존 (z ≡ 1 → T* = −T)")
    results["R6-5"] = A.check_full_swap(R, fx_exch)
    logln(f"        pass={results['R6-5']['pass']} abs_dev={results['R6-5']['abs_dev']:.3e}")

    # R6-6 군 순서 불변
    logln("[R6-6] 군 순서 불변 (순서보존 재라벨 + 행 치환)")
    results["R6-6"] = A.check_group_relabel_invariance(R, fx_exch, n_coin_vectors=300, seed=6)
    logln(f"        pass={results['R6-6']['pass']} p_base={results['R6-6']['p_base']}")

    # R6-7 재실행 결정성
    logln("[R6-7] 재실행 결정성 (참조분포 바이트 동일)")
    results["R6-7"] = A.check_rerun_determinism(R, fx_exch, n_coin_vectors=300, seed=7)
    logln(f"        pass={results['R6-7']['pass']}")

    # R6-9 독립 구현 대조 — 실패 시 중단
    logln("[R6-9] 독립 구현 대조 (소박한 이중 루프 참조 구현)")
    results["R6-9"] = A.check_independent_reference(R, fx_tiny, n_coin_vectors=200, seed=9)
    logln(f"        pass={results['R6-9']['pass']} "
          f"max_diff={results['R6-9']['max_abs_diff_t_star_sequence']:.3e}")
    assert results["R6-9"]["pass"], "R6-9 불일치 → 중단(어느 쪽이 맞는지 임의 판단 금지)"

    # R6-8 완전열거 정답표
    logln("[R6-8] 완전열거 정답표 (2^8 = 256 전수 vs 몬테카를로)")
    results["R6-8"] = A.check_full_enumeration(R, fx_tiny, n_coin_vectors=4000, seed=8)
    logln(f"        pass={results['R6-8']['pass']} p_exact={results['R6-8']['p_exact']:.5f} "
          f"p_MC={results['R6-8']['p_monte_carlo']:.5f} 3SE={results['R6-8']['three_se']:.5f}")

    # R6-3 균등성 (마지막 — 가장 오래 걸림)
    logln("[R6-3] 대칭 할당 균등성 (R=200 realization · F-A6TOL 동일 규격)")
    results["R6-3"] = A.check_uniformity(R, lambda s: F.make_rqint_exchangeable(seed=s),
                                         R=200, n_coin_vectors=150, seed=3)
    logln(f"        pass={results['R6-3']['pass']} mean_p={results['R6-3']['mean_p']:.4f} "
          f"KS={results['R6-3']['ks_vs_uniform']:.4f}")
    if not results["R6-3"]["pass"]:
        logln("        [재측정 1회] R·B 를 늘려 재측정 (허용오차는 고정 — 늘리지 않음)")
        results["R6-3_remeasure"] = A.check_uniformity(
            R, lambda s: F.make_rqint_exchangeable(seed=s), R=400, n_coin_vectors=300, seed=33)
        logln(f"        재측정 pass={results['R6-3_remeasure']['pass']} "
              f"mean_p={results['R6-3_remeasure']['mean_p']:.4f}")

    # ── 단가 계측 (실측만) ────────────────────────────────────────────────
    logln("[계측] per_permutation_seconds 실측 (macro-AP 8회 포함)")
    timing_fx = F.make_rqint_exchangeable(seed=99)
    tm = R.rqint_test(*timing_fx, n_coin_vectors=200, seed=99,
                      pair_complement=True, complement_audit_draws=0)
    timing = {
        "fixture": "make_rqint_exchangeable(seed=99) — 합성 전용",
        "N": int(timing_fx[2].shape[0]), "K": int(timing_fx[2].shape[1]),
        "G": int(len(np.unique(timing_fx[3]))),
        "n_coin_vectors": tm["n_coin_vectors"],
        "n_permutation_values": tm["n_permutation_values"],
        "per_permutation_seconds": tm["per_permutation_seconds"],
        "per_reference_value_seconds": tm["per_reference_value_seconds"],
        "measured_not_extrapolated": True,
        "scope_note": ("합성 fixture 규모(N·K·G)의 실측이다. 확증 규모로의 외삽은 하지 않는다 "
                       "— 계측 블록의 일."),
    }
    logln(f"        per_permutation_seconds={timing['per_permutation_seconds']:.6f}s "
          f"(N={timing['N']} K={timing['K']} G={timing['G']})")

    # ── 약한-null 예비 진단 (판정 아님) ───────────────────────────────────
    logln("[진단] 약한-null (Δ_RF ≈ Δ_GIN ≠ 0) — 예비 진단 · 판정 아님")
    diag = A.weak_null_diagnostic(R, lambda s: F.make_rqint_common_effect(seed=s),
                                  R=200, n_coin_vectors=150, seed=5)
    logln(f"        mean_p={diag['mean_p']:.4f} frac(p≤0.05)={diag['frac_p_le_0.05']:.4f} "
          "(판정 아님)")

    # ── D6 반환 dict 필수 키 존재 확인 ────────────────────────────────────
    d6 = R.rqint_test(*fx_exch, n_coin_vectors=100, seed=61,
                      pair_complement=True, complement_audit_draws=0)
    d6_keys = {
        "inference_conditional_on": d6["inference_conditional_on"],
        "delta_gin_per_seed": d6["delta_gin_per_seed"],
        "delta_gin_seed_mean": d6["delta_gin_seed_mean"],
        "delta_gin_seed_sd": d6["delta_gin_seed_sd"],
        "n_coin_vectors": d6["n_coin_vectors"],
        "n_permutation_values": d6["n_permutation_values"],
        "B_definition": d6["B_definition"],
        "present": all(k in d6 for k in ("inference_conditional_on", "delta_gin_per_seed",
                                         "delta_gin_seed_mean", "delta_gin_seed_sd",
                                         "n_coin_vectors", "n_permutation_values")),
    }

    r6_ids = ["R6-1", "R6-2", "R6-3", "R6-4", "R6-5", "R6-6", "R6-7", "R6-8", "R6-9"]
    all_pass = all(results[i]["pass"] for i in r6_ids)
    logln(f"[종합] R6 전항 PASS = {all_pass}")

    payload = {
        "_doc": ("블록 AC — RQ-int 검정 구현 R6 검증. **합성 데이터 전용**: 본 파일의 모든 수치는 "
                 "sap.rqint_synthetic 합성 fixture 산출물이며 확증 데이터·봉인 수치와 무관하다. "
                 "G 는 감사용 임의값(확증 scaffold group 수 아님)."),
        "block": "AC",
        "instruction": "docs/89_rqint_implementation_r6_prompt_for_vscode.md",
        "run_at_kst": datetime.now(KST).isoformat(timespec="seconds"),
        "synthetic_only": True,
        "confirmatory_data_accessed": False,
        "unblinding_performed": False,
        "gin_start_still_blocked": True,
        "sap_version_unchanged": "1.1",
        "design_basis": {
            "sharp_null": "docs/55b §5 후보 B (F-CANDB)",
            "statistic": R.TEST_STATISTIC,
            "H0_imposed": R.H0_IMPOSED,
            "H0_target": R.H0_TARGET,
            "name_caveat": R.NAME_CAVEAT,
            "aggregation": R.AGGREGATION,
            "p_formula": R.P_FORMULA,
            "eps": R._EPS,
        },
        "B_definition_status": R.B_DEFINITION_STATUS,
        "complement_pairing_cost_note": (
            "여집합 항등식 T*(z̄) = −T*(z) 를 쓰면 참조분포 크기의 **절반만 평가**하면 된다 "
            "→ 계측 블록의 단가 추정이 그만큼 달라진다. "
            "★ 단 양측 p 는 |T*| 를 쓰므로 |T*(z̄)| = |T*(z)| 이며, 여집합 값은 양측 p 에 "
            "추가 정보를 주지 않는다(몬테카를로 오차는 독립 동전 draw 수가 지배). "
            "여집합 쌍의 효용은 참조분포의 **정확한 대칭성** 확보이지 p 의 정밀도 향상이 아니다."),
        "code_scan": scan,
        "import_topology": topo,
        "text_checks": txt,
        "r6": {i: results[i] for i in r6_ids},
        "r6_all_pass": bool(all_pass),
        "r6_3_remeasure": results.get("R6-3_remeasure"),
        "timing": timing,
        "weak_null_diagnostic": diag,
        "d6_conditionality_keys": d6_keys,
        "out_of_scope": ["R1 캘리브레이션 감사 C0~C4", "B 확정", "C0~C3 복제 수 확정",
                         "SAP 1.2 재동결·MODULE_FILES·__init__ 갱신", "GIN 학습", "개봉"],
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "sklearn": sklearn.__version__, "platform": platform.platform()},
        "wall_clock_seconds": round(time.time() - t_start, 2),
    }

    out_json = os.path.join(OUT_DIR, "audit_r6.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logln(f"[산출] {out_json}")
    with open(os.path.join(OUT_DIR, "run.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(_LOG) + "\n")
    logln(f"[완료] {payload['wall_clock_seconds']}s")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
