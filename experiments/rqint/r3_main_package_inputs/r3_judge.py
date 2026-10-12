#!/usr/bin/env python3
"""r3_judge.py — R3(제2자 독립 재실행) 판정기 (블록 AP · docs/104).

★ 트리거 사건(메일 3 = 본 드라이런 패키지 발송) **이전에** 작성·자기검사·해시 동결한다.

판정 규칙의 정본은 `v3_Multimodal/config/r3_second_party_freeze.json`(sha256 0624d3dd…)이다.
본 파일은 그 규칙의 **기계적 구현**일 뿐 규칙을 바꾸지 않는다. 운용화 선언 = `docs/33` 항목55.

  1차  numeric_core sha256 바이트 동일                          → R3_satisfied_stage1
  G-ENV 5필드(python_version·numpy·sklearn·machine·BLAS/LAPACK) 중 1개 이상 상이해야 2차 진입
       동일하면                                                  → stage2_forbidden_same_environment
  2차  numeric_core 전 리프를 타입으로 판정 + 패키지 파일 sha256 전건 일치
       bool/int/str/null = 완전 일치 · float = 상대오차 ≤ 1e-9 · 키 집합·리스트 길이 = 완전 일치
       단 RESIDUAL_POINTERS(구현 간 잔차 7개)는 상대오차로 비교하지 않고, 소속 R6 의 `pass`
       불리언(freeze 「판정 불리언」 목록 항목 · 완전 일치)이 판정한다 — 타입·존재만 확인.
       전부 성립                                                 → R3_satisfied_stage2
       하나라도 불성립                                           → R3_not_satisfied
  입력 결속·형식 문제(실제 판정 모드)                             → input_invalid (판정 아님 · 재회수)

⛔ 계산 0(비교만) · numpy/sap import 0 · 네트워크 0 · 봉인 접근 0.

사용
----
    python3 v3_Multimodal/src/r3_judge.py --selftest                 # 자기검사 16건 — 출력만
    python3 v3_Multimodal/src/r3_judge.py --selftest --write         # judge_selftest.json 기록(1회성)
    python3 v3_Multimodal/src/r3_judge.py --audit A --env E --hashes H           # 판정 출력만
    python3 v3_Multimodal/src/r3_judge.py --audit A --env E --hashes H --write   # r3_verdict.json 기록(1회성)
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True      # canonical.py 경로 로드 시 스테이징에 __pycache__ 가 생기지 않게

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KST = timezone(timedelta(hours=9))

FREEZE_PATH = os.path.join(ROOT, "v3_Multimodal", "config", "r3_second_party_freeze.json")
FREEZE_SHA256 = "0624d3ddb852c4e9a2f7f070024814653264eb49c2652dd3e7a947ac38ff27d0"
CANONICAL_PATH = os.path.join(ROOT, "experiments", "rqint", "r3_main_package", "canonical.py")
CANONICAL_SHA256 = "d58e0f4320c01149b535ffa468c34b93a51213ed1ac9716306775ec20804ba1d"
META = os.path.join(ROOT, "experiments", "rqint", "r3_main_package_meta")
REFERENCE_PATH = os.path.join(META, "r3_main_reference.json")
LOCAL_AUDIT_PATH = os.path.join(META, "audit_r6_local_main.json")
LOCAL_ENV_PATH = os.path.join(META, "env_local_main.json")
LOCAL_HASHES_PATH = os.path.join(META, "package_hashes_local_main.json")
MANIFEST_PATH = os.path.join(META, "package_manifest.json")
SELFTEST_OUT = os.path.join(META, "judge_selftest.json")
VERDICT_OUT = os.path.join(META, "r3_verdict.json")
# 자기검사 전용 「다른 환경」 명세 = 프로브 회수물(실제 Windows 환경)
SELFTEST_OTHER_ENV_PATH = os.path.join(ROOT, "experiments", "rqint", "r3_package_meta",
                                       "env_second_party_e2c3a7fa6723.json")
SELFTEST_OTHER_ENV_SHA256 = "7a404edba225af64be7c4f3dbcf9014b2aaf39bd04c3fe8023e0df8a31065106"

REL_TOL = 1e-9          # freeze: 연속량 relative_error_tolerance
DENOM_FLOOR = 1e-12     # freeze: |a−b| / max(|a|,|b|,1e-12)
PACKAGE_PREFIX = "r3_main_package/"
# 구현 간 잔차(같은 양을 두 경로로 계산한 차이) — freeze 연속량 목록 밖이며, 각 소속 R6 의 pass 가 판정한다.
RESIDUAL_POINTERS = (
    "/r6/R6-1/max_abs_diff",
    "/r6/R6-4/max_abs_dev",
    "/r6/R6-5/abs_dev",
    "/r6/R6-6/abs_dT",
    "/r6/R6-8/abs_dT_vs_naive",
    "/r6/R6-9/max_abs_diff_t_star_sequence",
    "/r6/R6-9/abs_diff_T_obs",
)

VERDICTS = ("R3_satisfied_stage1", "R3_satisfied_stage2",
            "R3_not_satisfied", "stage2_forbidden_same_environment")


# ── 입출력 ─────────────────────────────────────────────────────────────────
def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:      # BOM 유무 모두 허용(해시는 바이트로 따로 계산)
        return json.load(f)


def load_canonical():
    got = sha256_file(CANONICAL_PATH)
    if got != CANONICAL_SHA256:
        raise SystemExit(f"[중단] canonical.py sha256 불일치: {got}")
    spec = importlib.util.spec_from_file_location("r3_canonical", CANONICAL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_freeze(canonical):
    """판정 규칙 정본이 동결 당시 그대로이고, 본 파일 상수와 어긋나지 않는지 확인한다."""
    got = sha256_file(FREEZE_PATH)
    if got != FREEZE_SHA256:
        raise SystemExit(f"[중단] r3_second_party_freeze.json sha256 불일치: {got}")
    fz = load_json(FREEZE_PATH)
    s2 = fz["acceptance_criteria"]["stage_2_pre_specified_tolerance"]
    tol = [c.get("relative_error_tolerance") for c in s2["criteria_all_must_hold"]
           if c.get("category") == "연속량"]
    if tol != [REL_TOL]:
        raise SystemExit(f"[중단] 허용오차 상수 불일치: freeze={tol} judge={REL_TOL}")
    fz_ptrs = [p for r in fz["numeric_core"]["exclude_rules"] for p in r.get("pointers", [])]
    if fz_ptrs != list(canonical.EXCLUDE_POINTERS):
        raise SystemExit(f"[중단] 제외 pointer 불일치: freeze={fz_ptrs} "
                         f"canonical={canonical.EXCLUDE_POINTERS}")
    fields = s2["gate_G_ENV"]["fields_compared"]
    if len(fields) != 5:
        raise SystemExit(f"[중단] G-ENV 필드 수 불일치: {fields}")
    return {"freeze_sha256": got, "rel_tol": REL_TOL, "exclude_pointers": fz_ptrs,
            "g_env_fields": fields}


# ── G-ENV ──────────────────────────────────────────────────────────────────
def _blas_lapack(env):
    cfg = ((env.get("numpy_build_config") or {}).get("config") or {})
    deps = cfg.get("Build Dependencies") or {}
    return [(deps.get("blas") or {}).get("name"), (deps.get("lapack") or {}).get("name")]


def gate_g_env(env_ours, env_sp):
    pairs = {
        "python_version": (env_ours.get("python_version"), env_sp.get("python_version")),
        "numpy": (env_ours.get("numpy"), env_sp.get("numpy")),
        "sklearn": (env_ours.get("sklearn"), env_sp.get("sklearn")),
        "machine": (env_ours.get("machine"), env_sp.get("machine")),
        "numpy_build_config(BLAS/LAPACK 구현)": (_blas_lapack(env_ours), _blas_lapack(env_sp)),
    }
    def _known(v):
        return v is not None and not (isinstance(v, list) and any(x is None for x in v))

    # 「실제로 다름을 입증」— 양쪽 값이 모두 알려진 경우에만 상이로 센다(누락·None 은 상이 아님).
    fields = {k: {"ours": a, "second_party": b, "differs": _known(a) and _known(b) and a != b}
              for k, (a, b) in pairs.items()}
    n_differ = sum(1 for v in fields.values() if v["differs"])
    return {"fields": fields, "n_differ": n_differ, "pass": n_differ >= 1,
            "info_host_id": {"ours": env_ours.get("host_id"), "second_party": env_sp.get("host_id")}}


# ── 입력 검증(실제 판정 모드) ────────────────────────────────────────────────
def env_problems(env):
    if not isinstance(env, dict):
        return ["env 가 JSON 객체가 아님"]
    out = []
    if not str(env.get("collected_by", "")).startswith("collect_env.py"):
        out.append("collected_by 가 collect_env.py 산출물이 아님")
    for k in ("python_version", "numpy", "sklearn", "machine", "platform", "host_id"):
        if not (isinstance(env.get(k), str) and env.get(k)):
            out.append(f"{k} 누락")
    if any(x is None for x in _blas_lapack(env)):
        out.append("numpy_build_config BLAS/LAPACK 이름 누락")
    return out


def binding_problems(env_ours, ref_audit_sha, sp_audit, sp_audit_sha, sp_env, sp_hashes):
    out = []
    if not isinstance(sp_audit, dict):
        return ["audit 가 JSON 객체가 아님"]
    if sp_audit_sha == ref_audit_sha:
        out.append("제2자 audit 파일이 우리 기준 audit 와 바이트 동일(사본)")
    ver = sp_audit.get("versions") if isinstance(sp_audit.get("versions"), dict) else {}
    for vk, ek in (("python", "python_version"), ("numpy", "numpy"), ("sklearn", "sklearn"),
                   ("platform", "platform")):
        if ver.get(vk) != (sp_env or {}).get(ek):
            out.append(f"audit versions.{vk}={ver.get(vk)!r} ≠ env {ek}={(sp_env or {}).get(ek)!r}")
    if isinstance(sp_env, dict) and sp_env.get("host_id") == env_ours.get("host_id"):
        out.append("제2자 host_id 가 우리 host_id 와 같음")
    if not (isinstance(sp_hashes, dict) and isinstance(sp_hashes.get("files"), dict)):
        out.append("package_hashes.json 형식 오류(files 객체 없음)")
    return out


# ── 패키지 파일 해시 (freeze 2차 「문자열 — 모듈 sha256」) ─────────────────────
def check_package_hashes(manifest, sp_hashes):
    expected = {}
    for k, v in manifest["files"].items():
        if not k.startswith(PACKAGE_PREFIX):
            raise SystemExit(f"[중단] manifest 경로 접두 불일치: {k}")
        expected[k[len(PACKAGE_PREFIX):]] = v["sha256"]
    got_files = (sp_hashes or {}).get("files") or {}
    got = {k: (v.get("sha256") if isinstance(v, dict) else None) for k, v in got_files.items()}
    mismatch = sorted(k for k in expected if got.get(k) != expected[k])
    unexpected = sorted(set(got) - set(expected))
    return {"n_expected": len(expected), "n_mismatch_or_missing": len(mismatch),
            "mismatch_or_missing": mismatch, "unexpected": unexpected,
            "pass": (not mismatch) and (not unexpected)}


# ── 2차 리프 비교 ──────────────────────────────────────────────────────────
def _leaf_type(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, dict):
        return "dict"
    if isinstance(v, list):
        return "list"
    return type(v).__name__


_KIND = {"bool": "boolean", "int": "discrete", "str": "string", "null": "null"}


def compare_tree(a, b, path=""):
    """ours=a, second_party=b. 불일치 목록을 돌려준다(빈 목록 = 전 리프 합격)."""
    fails = []
    if isinstance(a, dict) and isinstance(b, dict):
        ka, kb = set(a), set(b)
        if ka != kb:
            fails.append({"path": path or "/", "kind": "keys",
                          "only_ours": sorted(ka - kb), "only_second_party": sorted(kb - ka)})
        for k in sorted(ka & kb):
            fails += compare_tree(a[k], b[k], f"{path}/{k}")
        return fails
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            fails.append({"path": path, "kind": "length", "ours": len(a), "second_party": len(b)})
            return fails
        for i, (x, y) in enumerate(zip(a, b)):
            fails += compare_tree(x, y, f"{path}[{i}]")
        return fails
    ta, tb = _leaf_type(a), _leaf_type(b)
    if ta != tb:
        fails.append({"path": path, "kind": "type", "ours": ta, "second_party": tb})
        return fails
    if ta == "float":
        if path in RESIDUAL_POINTERS:
            return fails            # 소속 R6 의 pass 불리언이 판정(이 함수의 bool 규칙으로 완전 일치)
        if (math.isnan(a) and math.isnan(b)) or a == b:
            return fails
        rel = abs(a - b) / max(abs(a), abs(b), DENOM_FLOOR)
        if not (rel <= REL_TOL):
            fails.append({"path": path, "kind": "continuous", "ours": a, "second_party": b,
                          "rel_err": rel})
        return fails
    if a != b:
        fails.append({"path": path, "kind": _KIND.get(ta, ta), "ours": a, "second_party": b})
    return fails


# ── 판정 ───────────────────────────────────────────────────────────────────
def judge(canonical, ref_audit, ref_core_sha, env_ours, manifest, sp_audit, sp_env, sp_hashes):
    ref_sha = canonical.numeric_core_sha256(ref_audit)[0]
    if ref_sha != ref_core_sha:
        raise SystemExit(f"[중단] 기준 audit 의 numeric_core 가 기준값과 다름: {ref_sha}")
    sp_sha, _removed, sp_nbytes = canonical.numeric_core_sha256(sp_audit)
    g_env = gate_g_env(env_ours, sp_env)
    pk = check_package_hashes(manifest, sp_hashes)
    out = {"stage1": {"ours": ref_sha, "second_party": sp_sha,
                      "second_party_canonical_bytes": sp_nbytes,
                      "byte_identical": sp_sha == ref_sha},
           "g_env": g_env, "package_hashes": pk}
    if sp_sha == ref_sha:
        out["stage2"] = "not_run — 1차 통과(freeze stage_1_byte_identity.on_pass)"
        out["verdict"] = "R3_satisfied_stage1"
        return out
    if not g_env["pass"]:
        out["stage2"] = "forbidden — G-ENV 실패(freeze gate_G_ENV.on_fail: 즉시 중단·원인 규명·재자문)"
        out["verdict"] = "stage2_forbidden_same_environment"
        return out
    ref_core, _ = canonical.strip_excluded(ref_audit)
    sp_core, _ = canonical.strip_excluded(sp_audit)
    fails = compare_tree(ref_core, sp_core)
    out["stage2"] = {"n_leaf_failures": len(fails), "leaf_failures": fails[:200],
                     "leaf_failures_truncated": len(fails) > 200,
                     "package_hashes_pass": pk["pass"]}
    out["verdict"] = "R3_satisfied_stage2" if (not fails and pk["pass"]) else "R3_not_satisfied"
    return out


# ── 자기검사 ────────────────────────────────────────────────────────────────
def _get(obj, pointer):
    cur = obj
    for p in [x for x in pointer.split("/") if x]:
        cur = cur[p]
    return cur


def _set(obj, pointer, value):
    parts = [x for x in pointer.split("/") if x]
    cur = obj
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value


def _del(obj, pointer):
    parts = [x for x in pointer.split("/") if x]
    cur = obj
    for p in parts[:-1]:
        cur = cur[p]
    del cur[parts[-1]]


def selftest(canonical):
    ref_audit = load_json(LOCAL_AUDIT_PATH)
    env_ours = load_json(LOCAL_ENV_PATH)
    hashes_ours = load_json(LOCAL_HASHES_PATH)
    manifest = load_json(MANIFEST_PATH)
    if sha256_file(SELFTEST_OTHER_ENV_PATH) != SELFTEST_OTHER_ENV_SHA256:
        raise SystemExit("[중단] 자기검사용 다른-환경 명세 sha256 불일치")
    env_other = load_json(SELFTEST_OTHER_ENV_PATH)
    ref_sha = canonical.numeric_core_sha256(ref_audit)[0]

    def perturb_float(obj, pointer, factor):
        v = _get(obj, pointer)
        nv = v * factor
        if not (isinstance(v, float) and nv != v):
            raise SystemExit(f"[중단] 자기검사 교란 실패: {pointer}")
        _set(obj, pointer, nv)

    def case(name, expect, mutate_audit=None, env="other", mutate_hashes=None):
        a = copy.deepcopy(ref_audit)
        h = copy.deepcopy(hashes_ours)
        if mutate_audit:
            mutate_audit(a)
        if mutate_hashes:
            mutate_hashes(h)
        e = env_other if env == "other" else env_ours
        r = judge(canonical, ref_audit, ref_sha, env_ours, manifest, a, e, h)
        return {"case": name, "expected": expect, "got": r["verdict"], "pass": r["verdict"] == expect,
                "n_leaf_failures": (r["stage2"]["n_leaf_failures"]
                                    if isinstance(r["stage2"], dict) else None),
                "failure_kinds": (sorted({f["kind"] for f in r["stage2"]["leaf_failures"]})
                                  if isinstance(r["stage2"], dict) else None),
                "package_hashes_pass": r["package_hashes"]["pass"]}

    def invalid_case(name, problems):
        got = "input_invalid" if problems else "valid"
        return {"case": name, "expected": "input_invalid", "got": got, "pass": got == "input_invalid",
                "problems": problems}

    ref_audit_sha = sha256_file(LOCAL_AUDIT_PATH)

    def sp_like_audit(versions_from_env):
        a = copy.deepcopy(ref_audit)
        _set(a, "/run_at_kst", "2099-01-01T00:00:00+09:00")       # 제외 필드만 바꿔 파일 바이트를 다르게
        _set(a, "/versions", {"python": versions_from_env.get("python_version"),
                              "numpy": versions_from_env.get("numpy"),
                              "sklearn": versions_from_env.get("sklearn"),
                              "platform": versions_from_env.get("platform")})
        return a

    def _sha_obj(o):
        return hashlib.sha256(json.dumps(o, ensure_ascii=False, indent=2).encode("utf-8")).hexdigest()

    def bump_hash(h):
        k = "v3_Multimodal/src/sap/rqint.py"
        h["files"][k]["sha256"] = "0" * 64

    results = [
        case("T1 identical", "R3_satisfied_stage1", env="ours"),
        case("T2 float 1e-12 rel · 다른 환경", "R3_satisfied_stage2",
             lambda a: perturb_float(a, "/r6/R6-3/mean_p", 1 + 1e-12)),
        case("T3 float 1e-6 rel · 다른 환경", "R3_not_satisfied",
             lambda a: perturb_float(a, "/r6/R6-3/mean_p", 1 + 1e-6)),
        case("T4 bool 반전 /r6_all_pass", "R3_not_satisfied",
             lambda a: _set(a, "/r6_all_pass", not _get(a, "/r6_all_pass"))),
        case("T5 float 1e-12 rel · 같은 환경", "stage2_forbidden_same_environment",
             lambda a: perturb_float(a, "/r6/R6-3/mean_p", 1 + 1e-12), env="ours"),
        case("T6 float 1e-12 rel · 패키지 해시 1건 불일치", "R3_not_satisfied",
             lambda a: perturb_float(a, "/r6/R6-3/mean_p", 1 + 1e-12), mutate_hashes=bump_hash),
        case("T7 키 삭제 /weak_null_diagnostic/note", "R3_not_satisfied",
             lambda a: _del(a, "/weak_null_diagnostic/note")),
        case("T8 int +1 /r6/R6-8/count_abs_ge_obs", "R3_not_satisfied",
             lambda a: _set(a, "/r6/R6-8/count_abs_ge_obs", _get(a, "/r6/R6-8/count_abs_ge_obs") + 1)),
        case("T9 제외 필드만 변경", "R3_satisfied_stage1",
             lambda a: (_set(a, "/run_at_kst", "2000-01-01T00:00:00+09:00"),
                        _set(a, "/wall_clock_seconds", 1.0),
                        _set(a, "/versions", {"python": "x"}),
                        _set(a, "/timing/per_permutation_seconds", 9.9),
                        _set(a, "/timing/per_reference_value_seconds", 9.9),
                        _set(a, "/_doc", "x"), _set(a, "/block", "x"), _set(a, "/instruction", "x")),
             env="ours"),
        case("T14 잔차 리프 0.0→1.1e-16 · 다른 환경", "R3_satisfied_stage2",
             lambda a: (perturb_float(a, "/r6/R6-3/mean_p", 1 + 1e-12),
                        _set(a, "/r6/R6-9/abs_diff_T_obs", 1.1e-16))),
        case("T15 목록 항목 /r6/R6-2/T_obs 0.0→1e-17 · 다른 환경", "R3_not_satisfied",
             lambda a: _set(a, "/r6/R6-2/T_obs", 1e-17)),
    ]
    good_sp = sp_like_audit(env_other)
    env_no_blas = copy.deepcopy(env_ours)
    env_no_blas["numpy_build_config"] = {"available": False}
    bad_ver = sp_like_audit(env_other)
    _set(bad_ver, "/versions/numpy", "0.0.0")
    results += [
        invalid_case("T10 env 빈 객체", env_problems({})),
        invalid_case("T11 env BLAS 정보 없음", env_problems(env_no_blas)),
        invalid_case("T12 audit 가 기준 사본", binding_problems(env_ours, ref_audit_sha, ref_audit,
                                                            ref_audit_sha, env_other, hashes_ours)),
        invalid_case("T13 audit versions ≠ env", binding_problems(env_ours, ref_audit_sha, bad_ver,
                                                               _sha_obj(bad_ver), env_other, hashes_ours)),
    ]
    control = env_problems(env_other) + binding_problems(env_ours, ref_audit_sha, good_sp,
                                                         _sha_obj(good_sp), env_other, hashes_ours)
    results.append({"case": "T16 정상 입력 대조군", "expected": "valid",
                    "got": "valid" if not control else "input_invalid",
                    "pass": not control, "problems": control})
    n_pass = sum(1 for r in results if r["pass"])
    return {"reference_numeric_core_sha256": ref_sha, "cases": results,
            "n_cases": len(results), "n_pass": n_pass, "all_pass": n_pass == len(results)}


# ── CLI ────────────────────────────────────────────────────────────────────
def _write_once(path, payload):
    if os.path.exists(path):
        raise SystemExit(f"[중단] 1회성 산출물이 이미 있음: {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--audit")
    ap.add_argument("--env")
    ap.add_argument("--hashes")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    canonical = load_canonical()
    freeze_info = check_freeze(canonical)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    judge_sha = sha256_file(os.path.abspath(__file__))

    if args.selftest:
        st = selftest(canonical)
        payload = {"_doc": "r3_judge.py 자기검사 — 교란은 메모리 사본에서만 수행(원본 파일 무수정).",
                   "run_at_kst": now, "judge_sha256": judge_sha, "freeze": freeze_info, **st}
        for r in st["cases"]:
            print(f"[{'PASS' if r['pass'] else 'FAIL'}] {r['case']} → {r['got']} (기대 {r['expected']})")
        print(f"[자기검사] {st['n_pass']}/{st['n_cases']} all_pass={st['all_pass']}")
        if args.write:
            _write_once(SELFTEST_OUT, payload)
            print(f"[산출] {SELFTEST_OUT}")
        return 0 if st["all_pass"] else 1

    if not (args.audit and args.env and args.hashes):
        ap.error("--selftest 또는 --audit/--env/--hashes 3개가 필요하다")
    ref = load_json(REFERENCE_PATH)
    if ref["judge"]["sha256"] != judge_sha:
        raise SystemExit(f"[중단] 판정기 sha256 이 기준 파일 등재값과 다름: {judge_sha}")
    if sha256_file(LOCAL_AUDIT_PATH) != ref["local_run"]["audit_sha256"]:
        raise SystemExit("[중단] 기준 audit 파일 sha256 이 기준 파일 등재값과 다름")
    if sha256_file(LOCAL_ENV_PATH) != ref["local_run"]["env_sha256"]:
        raise SystemExit("[중단] 기준 env 파일 sha256 이 기준 파일 등재값과 다름")
    if sha256_file(MANIFEST_PATH) != ref["package"]["manifest_sha256"]:
        raise SystemExit("[중단] package_manifest.json sha256 이 기준 파일 등재값과 다름")
    try:
        sp_audit, sp_env, sp_hashes = load_json(args.audit), load_json(args.env), load_json(args.hashes)
        sp_audit_sha = sha256_file(args.audit)
    except (OSError, ValueError, UnicodeDecodeError) as e:
        print(f"[input_invalid] 입력 파일 판독 실패: {e}")
        return 2
    env_ours = load_json(LOCAL_ENV_PATH)
    problems = env_problems(sp_env) + binding_problems(
        env_ours, ref["local_run"]["audit_sha256"], sp_audit, sp_audit_sha, sp_env, sp_hashes)
    if problems:
        print("[input_invalid] 판정하지 않는다(재회수 필요):")
        for p in problems:
            print(f"  - {p}")
        return 2
    result = judge(canonical, load_json(LOCAL_AUDIT_PATH), ref["local_run"]["numeric_core_sha256"],
                   env_ours, load_json(MANIFEST_PATH), sp_audit, sp_env, sp_hashes)
    payload = {"_doc": "R3 판정 결과 — r3_judge.py(트리거 이전 동결본) 산출.",
               "run_at_kst": now, "judge_sha256": judge_sha, "freeze": freeze_info,
               "inputs": {"audit": {"path": args.audit, "sha256": sha256_file(args.audit)},
                          "env": {"path": args.env, "sha256": sha256_file(args.env)},
                          "hashes": {"path": args.hashes, "sha256": sha256_file(args.hashes)}},
               **result}
    print(json.dumps({k: payload[k] for k in ("verdict", "stage1")}, ensure_ascii=False, indent=2))
    if args.write:
        _write_once(VERDICT_OUT, payload)
        print(f"[산출] {VERDICT_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
