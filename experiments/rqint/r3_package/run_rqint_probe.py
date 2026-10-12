"""run_rqint_probe.py — R3 제2자 **플랫폼 적합성 프로브** (블록 AG · docs/91 AG-4).

★★ 이것은 R3 판정이 아니다 ★★
   본 스크립트의 산출물은 **플랫폼 적합성 확인 전용**이며 R3 합격·불합격 판정에
   사용하지 않는다. R3 판정 대상은 R2(SAP 1.2 재동결) 이후의 **본 드라이런** 산출물뿐이다.

⛔ 무결성
   · 입력은 **100% 합성**이다(`sap.rqint_synthetic` 의 기존 fixture 생성기 재사용 · 재구현 0).
   · 확증 데이터(`data/**`)·봉인 산출물을 **읽지도 쓰지도 않는다.** AST 스캔으로 증명한다.
   · 네트워크 0 · 모델 학습 0 · 개봉 0.

축소 규모 (docs/91 AG-4 고정)
   N = 60 · K = 8 · G = 12 · n_coin_vectors = 64.  목표 벽시계 60초 이내.

시드 취득 규칙 (새 난수 추첨 0)
   `run_rqint_audit.py` 의 시드 리터럴을 **그대로** 쓴다 —
   fixture: zero-interaction = 11 · exchangeable = 12 · timing = 99,
   검사 시드: R6-n → n (원 스크립트의 자체 관례 R6-2→2 · R6-6→6 · R6-7→7 · R6-9→9 계승).

실행 R6 부분집합 (6항)
   R6-1 · R6-2 · R6-5 · R6-6 · R6-7 · R6-9.
   제외 3항과 사유 —
     R6-3 균등성   : R=200 realization 이 필요해 60초 예산을 초과한다.
     R6-4 여집합감사: 합격기준이 `draws_checked >= 1000` 으로 **규모 의존**이라 축소 규모에서
                     성립하지 않는다(기준을 낮추는 것은 금지이므로 실행하지 않는다).
     R6-8 완전열거 : 2^G 전수열거가 필요하며 G=12 에서 4,096 회 소박 평가라 예산을 초과한다.
   → 세 항목은 **R3 본 드라이런에서 전항 실행**된다.

사용
----
    python3 run_rqint_probe.py
      → probe_result.json · probe_numeric_core.sha256
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
sys.path.insert(0, HERE)

for _k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_k, "1")

import numpy as np                                                  # noqa: E402
import sklearn                                                      # noqa: E402

from canonical import numeric_core_sha256                           # noqa: E402
from sap import rqint as R                                          # noqa: E402
from sap import rqint_audit as A                                    # noqa: E402
from sap import rqint_synthetic as F                                # noqa: E402

KST = timezone(timedelta(hours=9))

# 축소 규모 — docs/91 AG-4 고정
N, K, G, NCOIN = 60, 8, 12, 64

# 시드 — run_rqint_audit.py 리터럴 계승(새 추첨 0)
SEED_FIXTURE_ZERO, SEED_FIXTURE_EXCH, SEED_FIXTURE_TIMING = 11, 12, 99
SEED_R6 = {"R6-1": 1, "R6-2": 2, "R6-6": 6, "R6-7": 7, "R6-9": 9}

R6_SUBSET = ["R6-1", "R6-2", "R6-5", "R6-6", "R6-7", "R6-9"]
R6_EXCLUDED = {
    "R6-3": "균등성 R=200 realization — 60초 예산 초과. R3 본 드라이런에서 실행.",
    "R6-4": ("여집합 감사 합격기준이 draws_checked >= 1000 으로 규모 의존 — 축소 규모에서 "
             "성립 불가. 기준 완화는 금지이므로 실행하지 않는다. R3 본 드라이런에서 실행."),
    "R6-8": "2^G 전수열거(G=12 → 4,096 회 소박 평가) — 예산 초과. R3 본 드라이런에서 실행.",
}

_LOG = []


def logln(msg):
    line = f"[{datetime.now(KST).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _LOG.append(line)


# ═══════════════════════════════════════════════════════════════════════════
# 확증 데이터 미접근 스캔 — 패키지 전 .py 에 적용
#   S1 = 동결 규칙(freeze.py `code_scan` 과 동일): 금지 import · data-load call · open() 리터럴
#   S2 = 비-docstring 문자열 상수 어휘 스캔(참고 — 분류와 함께 보고)
# ═══════════════════════════════════════════════════════════════════════════
FORBIDDEN_IMPORTS = {"ladder_confirmatory", "preconfirm_hardening", "target_pipeline",
                     "train_ladder", "prep_features", "coverage_mapping"}
DATA_LOAD_ATTRS = {"read_parquet", "read_csv", "read_table", "load_frozen", "loadtxt", "genfromtxt"}
NP_LOAD_ROOTS = {"np", "numpy"}
FORBIDDEN_PATH_LITERALS = ["data/processed", "data/raw", "master_X", "master_Y",
                           "scaffold_split.json", "_meanpool.npy", "confirmatory",
                           "oof_M1b", "oof_M2b", "target_mapping",
                           "data/", "_sealed", "master_", "oof_"]


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


def _docstring_nodes(tree):
    """모듈·클래스·함수 docstring 인 Constant 노드 집합(id 기준)."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def package_files():
    rels = sorted(os.path.join("sap", f) for f in os.listdir(os.path.join(HERE, "sap"))
                  if f.endswith(".py"))
    rels += sorted(f for f in os.listdir(HERE) if f.endswith(".py"))
    return rels


def code_scan():
    per_file, s1_ok = {}, True
    s2_hits = []
    for rel in package_files():
        src = open(os.path.join(HERE, rel), encoding="utf-8").read()
        tree = ast.parse(src, filename=rel)
        docs = _docstring_nodes(tree)
        imports, bad_calls, open_lit, str_hits = set(), [], [], []
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
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in docs:
                low = node.value.lower()
                hit = [t for t in FORBIDDEN_PATH_LITERALS if t.lower() in low]
                if hit:
                    str_hits.append({"line": getattr(node, "lineno", -1),
                                     "terms": sorted(set(hit)),
                                     "value": node.value[:90]})
        forb = sorted(imports & FORBIDDEN_IMPORTS)
        ok = (not forb) and (not bad_calls) and (not open_lit)
        s1_ok = s1_ok and ok
        if str_hits:
            s2_hits.append({"file": rel, "hits": str_hits})
        per_file[rel] = {"forbidden_imports": forb, "data_load_calls": sorted(set(bad_calls)),
                         "open_with_data_literal": open_lit,
                         "imports": sorted(i for i in imports if i != "__future__"), "ok": ok}
    logln(f"[스캔] S1 동결규칙 = {s1_ok} (금지 import 0 · data-load call 0 · open() 리터럴 0) · "
          f"S2 비-docstring 문자열 hit 파일 {len(s2_hits)}종")
    assert s1_ok, f"확증 데이터 접근 코드 발견: {per_file}"
    return {"method": "AST walk (freeze.py code_scan 동일 규칙 = S1) + 비-docstring 문자열 어휘(S2)",
            "n_files_scanned": len(per_file),
            "per_file": per_file,
            "no_confirmatory_data_access": s1_ok,
            "s2_string_literal_hits": s2_hits,
            "s2_note": ("S2 는 참고용이다. hit 는 전부 ① 동결 스캐너 자신의 금지어 목록"
                        "(freeze.py FORBIDDEN_PATH_LITERALS) ② 라벨 문자열 ③ sealed **쓰기** API 의 "
                        "경로 조립(redaction.py — 호출자가 run_dir 을 넘겨야 하며 프로브는 import 하지 "
                        "않는다) 이다. 실제 경로 열람은 S1 이 0 으로 증명한다.")}


def import_topology():
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
    rq = open(os.path.join(HERE, "sap/rqint.py"), encoding="utf-8").read()
    sf = open(os.path.join(HERE, "sap/signflip.py"), encoding="utf-8").read()
    res = {
        "assert_eight_matrices": "assert len(mats) == 8" in rq,
        "eps_literal_matches_signflip": ("_EPS = 1e-12" in rq) and ("_EPS = 1e-12" in sf),
        "count_formula_rqint": "count = int(np.sum(np.abs(perm) >= abs(t_obs) - _EPS))" in rq,
        "count_formula_signflip": "count = int(np.sum(np.abs(perm) >= abs(delta_obs) - _EPS))" in sf,
        "p_formula_rqint": "p = (1.0 + count) / (n_perm_values + 1.0)" in rq,
        "p_formula_signflip": "p = (1.0 + count) / (B + 1.0)" in sf,
    }
    res["pass"] = all(res.values())
    logln(f"[텍스트] 축자 대조 pass={res['pass']}")
    return res


def main():
    t_start = time.time()
    logln("═" * 70)
    logln("블록 AG — R3 제2자 프로브 (플랫폼 적합성 전용 · R3 판정 아님 · 합성 전용)")
    logln("═" * 70)

    scan = code_scan()
    topo = import_topology()
    txt = text_checks()
    assert topo["pass"], "import 토폴로지 위반"
    assert txt["pass"], "텍스트 대조 실패"

    # ── fixture (합성 전용 · 축소 규모 · G 는 임의값) ─────────────────────
    fx_zero = F.make_rqint_zero_interaction(seed=SEED_FIXTURE_ZERO, N=N, K=K, G=G)
    fx_exch = F.make_rqint_exchangeable(seed=SEED_FIXTURE_EXCH, N=N, K=K, G=G)
    logln(f"[fixture] N={fx_exch[2].shape[0]} K={fx_exch[2].shape[1]} "
          f"G={len(np.unique(fx_exch[3]))} n_coin_vectors={NCOIN}")

    results = {}

    logln("[R6-1] 가환성")
    results["R6-1"] = A.check_commutativity(fx_exch, n_z=100, seed=SEED_R6["R6-1"])
    logln(f"        pass={results['R6-1']['pass']} max_abs_diff={results['R6-1']['max_abs_diff']:.3e}")

    logln("[R6-2] zero-effect → p = 1.0")
    results["R6-2"] = A.check_zero_effect(R, fx_zero, n_coin_vectors=NCOIN,
                                          seed=SEED_R6["R6-2"])
    logln(f"        pass={results['R6-2']['pass']} p={results['R6-2']['p']}")

    logln("[R6-5] 전체 교환 보존 (z ≡ 1 → T* = −T)")
    results["R6-5"] = A.check_full_swap(R, fx_exch)
    logln(f"        pass={results['R6-5']['pass']} abs_dev={results['R6-5']['abs_dev']:.3e}")

    logln("[R6-6] 군 순서 불변")
    results["R6-6"] = A.check_group_relabel_invariance(R, fx_exch, n_coin_vectors=NCOIN,
                                                       seed=SEED_R6["R6-6"])
    logln(f"        pass={results['R6-6']['pass']} p_base={results['R6-6']['p_base']}")

    logln("[R6-7] 재실행 결정성")
    results["R6-7"] = A.check_rerun_determinism(R, fx_exch, n_coin_vectors=NCOIN,
                                                seed=SEED_R6["R6-7"])
    logln(f"        pass={results['R6-7']['pass']}")

    logln("[R6-9] 독립 구현 대조")
    results["R6-9"] = A.check_independent_reference(R, fx_exch, n_coin_vectors=NCOIN,
                                                    seed=SEED_R6["R6-9"])
    logln(f"        pass={results['R6-9']['pass']} "
          f"max_diff={results['R6-9']['max_abs_diff_t_star_sequence']:.3e}")

    # ── 단가 계측 (실측만 · numeric_core 에서 제외되는 필드) ───────────────
    logln("[계측] per_permutation_seconds 실측")
    timing_fx = F.make_rqint_exchangeable(seed=SEED_FIXTURE_TIMING, N=N, K=K, G=G)
    tm = R.rqint_test(*timing_fx, n_coin_vectors=NCOIN, seed=SEED_FIXTURE_TIMING,
                      pair_complement=True, complement_audit_draws=0)
    timing = {
        "fixture": f"make_rqint_exchangeable(seed={SEED_FIXTURE_TIMING}) — 합성 전용",
        "N": int(timing_fx[2].shape[0]), "K": int(timing_fx[2].shape[1]),
        "G": int(len(np.unique(timing_fx[3]))),
        "n_coin_vectors": tm["n_coin_vectors"],
        "n_permutation_values": tm["n_permutation_values"],
        "per_permutation_seconds": tm["per_permutation_seconds"],
        "per_reference_value_seconds": tm["per_reference_value_seconds"],
        "measured_not_extrapolated": True,
        "scope_note": ("축소 프로브 규모의 실측이다. 확증 규모·본 드라이런 규모로 외삽하지 않는다. "
                       "이 2필드는 numeric_core 에서 제외된다(docs/91 AG-3 규칙 3)."),
    }
    logln(f"        per_permutation_seconds={timing['per_permutation_seconds']:.6f}s")

    # ── D6 반환 dict 필수 키 존재 확인 ────────────────────────────────────
    d6 = R.rqint_test(*fx_exch, n_coin_vectors=NCOIN, seed=61,
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

    all_pass = all(results[i]["pass"] for i in R6_SUBSET)
    logln(f"[종합] R6 부분집합 {len(R6_SUBSET)}항 전항 PASS = {all_pass}")

    # 프로브가 실제로 import 한 sap 하위 모듈(런타임 증명)
    loaded_sap = sorted(m for m in sys.modules if m == "sap" or m.startswith("sap."))

    payload = {
        "_doc": ("블록 AG — R3 제2자 **플랫폼 적합성 프로브**. ★ R3 판정이 아니다. "
                 "본 파일의 모든 수치는 sap.rqint_synthetic 합성 fixture 산출물이며 "
                 "확증 데이터·봉인 수치와 무관하다. G 는 프로브용 임의값이다."),
        "block": "AG-probe",
        "instruction": "docs/91_r3_second_party_prep_prompt_for_vscode.md",
        "run_at_kst": datetime.now(KST).isoformat(timespec="seconds"),
        "is_r3_verdict": False,
        "r3_verdict_note": ("프로브 산출물은 R3 합격·불합격 판정에 사용하지 않는다. "
                            "R3 판정 대상은 R2(SAP 1.2 재동결) 이후의 본 드라이런 산출물뿐이다."),
        "synthetic_only": True,
        "confirmatory_data_accessed": False,
        "unblinding_performed": False,
        "gin_start_still_blocked": True,
        "sap_version_unchanged": "1.1",
        "probe_scale": {"N": N, "K": K, "G": G, "n_coin_vectors": NCOIN},
        "seed_acquisition_rule": ("run_rqint_audit.py 시드 리터럴 계승 — fixture zero=11 · "
                                  "exchangeable=12 · timing=99, 검사 시드 R6-n → n. 새 추첨 0."),
        "seeds_used": {"fixture_zero": SEED_FIXTURE_ZERO, "fixture_exchangeable": SEED_FIXTURE_EXCH,
                       "fixture_timing": SEED_FIXTURE_TIMING, "d6_keys": 61, **SEED_R6},
        "design_basis": {
            "statistic": R.TEST_STATISTIC,
            "H0_imposed": R.H0_IMPOSED,
            "H0_target": R.H0_TARGET,
            "name_caveat": R.NAME_CAVEAT,
            "aggregation": R.AGGREGATION,
            "p_formula": R.P_FORMULA,
            "eps": R._EPS,
        },
        "B_definition_status": R.B_DEFINITION_STATUS,
        "code_scan": scan,
        "import_topology": topo,
        "text_checks": txt,
        "sap_modules_imported_at_runtime": loaded_sap,
        "r6_subset_executed": R6_SUBSET,
        "r6_excluded_with_reason": R6_EXCLUDED,
        "r6": {i: results[i] for i in R6_SUBSET},
        "r6_all_pass": bool(all_pass),
        "d6_conditionality_keys": d6_keys,
        "timing": timing,
        "out_of_scope": ["R3 판정", "R1 캘리브레이션 감사 C0~C4", "B 확정",
                         "SAP 1.2 재동결", "GIN 학습", "개봉"],
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "sklearn": sklearn.__version__, "platform": platform.platform()},
        "wall_clock_seconds": round(time.time() - t_start, 2),
    }

    out_json = os.path.join(HERE, "probe_result.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logln(f"[산출] {out_json}")

    digest, removed, nbytes = numeric_core_sha256(payload)
    out_sha = os.path.join(HERE, "probe_numeric_core.sha256")
    with open(out_sha, "w", encoding="utf-8") as f:
        json.dump({"numeric_core_sha256": digest, "canonical_bytes": nbytes,
                   "excluded_pointers_applied": removed,
                   "source_file": "probe_result.json",
                   "note": "★ R3 판정에 쓰지 않는다 — 플랫폼 적합성 확인 전용."},
                  f, ensure_ascii=False, indent=2)
    logln(f"[산출] {out_sha}")
    logln(f"[numeric_core] sha256 = {digest}")

    with open(os.path.join(HERE, "probe_run.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(_LOG) + "\n")
    logln(f"[완료] {payload['wall_clock_seconds']}s")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
