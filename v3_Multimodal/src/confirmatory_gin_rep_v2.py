#!/usr/bin/env python3
"""confirmatory_gin_rep_v2.py — GIN 착수 «권한 supersession» 하네스 (블록 AS · docs/109).

규격 정본: `v3_Multimodal/config/gin_confirm_harness_freeze_v2.json`
권한 정본: `v3_Multimodal/config/gin_start_supersede.json`  ★ 이 파일 하나만 권한을 만든다.
과학 정본: v1 `gin_confirm_harness_freeze.json` — v2 는 과학 명세를 **바꾸지 않는다**(T4 기계 diff).

⛔ 무결성 최상위
  - v1 `confirmatory_gin_rep.py` 를 **import** 한다. 복사·재구현 0. 과학 함수는 전부 v1 것을 쓴다.
  - ★ 차단 플래그 ①②③ 의 `gin_start_still_blocked` 는 **true 인 채로 보존**된다. v2 는 그것을
    해제하지 않고, 「여전히 true 인가」를 **요구 조건으로** 확인한 뒤 실행한다
    (= legacy block was valid, then superseded).
  - ★ `v1.enforce_gin_block()` 은 train·verify 경로에서 **호출하지 않는다** — 그 함수는
    「①②③ 중 하나라도 true 면 exit 11」이고 ①②③ 은 앞으로도 true 이므로 영구 차단이 된다.
    대신 `require_supersession()` 6조건을 쓰고, 불충족 시 **exit 12**(v1 의 11 과 구분)로 멈춘다.
  - ★★ 이것은 가드 «완화»도 «축소»도 아니며 v1 과 논리적으로 «비교 불가»다. v1 은
    「플래그 **false** ⇒ 실행」, v2 는 「플래그 **true** + 6조건 ⇒ 실행」이므로 두 허용집합은
    **서로소**다. 안전성 근거는 다음 문장이다:
        v1 의 단일 플래그 조건을, **해시 고정 + 외부 승인 이벤트 + 봉인 계수 + 비개봉을 함께
        요구하는 조건으로 «교체»했고, 교체된 조건이 요구하는 증거가 더 많다.**
  - `_sealed/` 읽기·쓰기·복사·해싱 0 · `_sealed` 디렉터리 생성 0.
  - `open_sealed` · `emit_sign` · `sap.decision` 미import·미호출 · `rqint_test` 미호출 · 순열 0.
  - `requests`/`urllib`/`http` 미import — 네트워크 0.
  - ★ `--stage train` 은 **스텁**이다. 본 블록(AS)은 확증 GIN 학습을 **0회** 한다.
    실제 구현은 다음 블록이다.

stage 4종
  1) `--stage selftest` (**기본값**) — 자체검사 10건(T1~T10). 확증 학습 0.
  2) `--stage verify`   — `require_supersession()` 6조건만 검사하고 판정을 출력. 학습 0.
  3) `--stage plan`     — v1 `build_plan` 재실행(357 단위). 학습 0.
  4) `--stage train`    — `require_supersession()` 통과 후 **스텁**으로 정지. 학습 0.

실행:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -X utf8 \
      v3_Multimodal/src/confirmatory_gin_rep_v2.py --stage selftest
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

# ★ v2 의 모든 import 문은 `import confirmatory_gin_rep` «앞» 에 둔다 —
#   v1 의 모듈 스코프 `sys.path.insert` 3건이 경로 순서를 바꾸기 때문이다(docs/109 AS-4).
import os
import ast
import json
import shutil
import argparse
import tempfile
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import confirmatory_gin_rep as v1          # ★ 복사·재구현 0 — v1 을 그대로 쓴다.

SYS_PATH_AFTER_V1_IMPORT = list(sys.path[:3])

SUPERSEDE_NAME = "gin_start_supersede.json"
SUPERSEDE_PATH = os.path.join(v1.CFG_DIR, SUPERSEDE_NAME)
V2_SPEC_NAME = "gin_confirm_harness_freeze_v2.json"
RUN_DIR = os.path.join(_ROOT, "experiments", "runs", "v3_gin_start_authorization")

EXIT_SUPERSESSION_UNMET = 12           # ★ 신규 — v1 의 11(EXIT_GIN_BLOCKED)과 구분한다.

# ---------------------------------------------------------------------------
# 상수 — 해시 고정. ★ v2 자기 규격 파일의 해시는 넣지 않는다(순환 방지).
# ---------------------------------------------------------------------------
PINNED_SHA256 = {
    "v3_Multimodal/src/confirmatory_gin_rep.py":
        "1e6642bf9ecac5a272fdb49c441668d2f6f3ec97e87528831aad75a9c40d995a",
    "v3_Multimodal/config/gin_confirm_harness_freeze.json":
        "1af993fde7330e1d48e6d10fee157c1310f42dacc5c1d65a4834b9020e5b7072",
    "v3_Multimodal/config/rqint_procedure_decisions_v1.json":
        "16776f21df6ae29b8805272ba39b59b522693217ee113e307a3b3cd3819a96ca",
    "v3_Multimodal/config/gin_seed_freeze.json":
        "10828447c6d33118328ee97dc03279ab06e69d7ed8f9338662bfa740e42542f7",
    "v3_Multimodal/config/gin_inner_valid_freeze.json":
        "038599c3e157602242ee94e60998f7d8a56c0a322ef5a8b0bc6359b3399921ea",
    "v3_Multimodal/config/gin_start_supersede.json":
        "c061d033ae35bea3df269d37c1a45174fc48f70bfe37ace4f159a8cb36d4a32c",
}

SEALED_COUNTS_EXPECTED = {
    "n_sealed_dirs": 25,
    "n_sealed_files_total": 291,
    "n_sealed_artifacts": 275,
    "n_access_log": 16,
}

# v1 산출물 6종 + gin_inner_valid_freeze.status.json (T1)
V1_ARTIFACT_SHA256 = {
    "v3_Multimodal/config/gin_confirm_harness_freeze.json":
        "1af993fde7330e1d48e6d10fee157c1310f42dacc5c1d65a4834b9020e5b7072",
    "v3_Multimodal/config/gin_confirm_harness_freeze.status.json":
        "5df9a7c4bfa64749f2b37f5b1984cfcca85d8f609e6c8c444097ff78e24c819a",
    "v3_Multimodal/src/confirmatory_gin_rep.py":
        "1e6642bf9ecac5a272fdb49c441668d2f6f3ec97e87528831aad75a9c40d995a",
    "experiments/runs/v3_gin_harness_selftest/selftest.json":
        "37b0af4d2ef74ad410c76603a143c7089161c6f35a75d68271a8a8cf94c78e09",
    "experiments/runs/v3_gin_budget/gin_budget_estimate.json":
        "f42e839d154611f2050124fdf2902cbec5a02988860de185622236113b139605",
    "experiments/runs/v3_gin_budget/README.md":
        "6fd60d4a59c48b49341bd3cd41f92f5c620d1789b20995e44c68205b31c51796",
    "v3_Multimodal/config/gin_inner_valid_freeze.status.json":
        "bd329fefe613971f59bde8b13ea3f1c4929be04541655ad8e27e9922aa6cb0d0",
}

# ★ v1↔v2 사이에서 **바이트 동일이어야 하는** 과학 명세 키(docs/109 AS-5).
#   `harness.stages` · `harness.default_stage` 는 대상이 아니다.
SCIENCE_KEYS = [
    "spec",
    "output_scale",
    "harness.inner_split",
    "harness.feature_block_fit_population",
    "harness.rng_scope",
    "harness.recipe_constants_A_wd",
    "harness.early_stopping",
    "harness.reuse_import_not_reimplement",
    "harness.code_level_prohibition_guards",
]


# ---------------------------------------------------------------------------
# 유틸 — 과학 함수는 v1 것을 쓰고, 여기엔 경로·계수 도우미만 둔다.
# ---------------------------------------------------------------------------
def _abs(rel: str) -> str:
    return os.path.join(_ROOT, rel)


def sealed_counts() -> dict:
    """stat-only. `_sealed/` 파일을 **열지도 해싱하지도 않는다** — 열거와 stat 만 쓴다."""
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


def pycache_dirs() -> int:
    n = 0
    for dp, _dn, _fn in os.walk(_ROOT):
        if ".git" in dp.split(os.sep):
            continue
        if os.path.basename(dp) == "__pycache__":
            n += 1
    return n


def _dig(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def science_diff(v1_spec: dict, v2_spec: dict) -> list:
    """지정 키를 `json.dumps(..., sort_keys=True, ensure_ascii=False)` 로 비교한다."""
    out = []
    for k in SCIENCE_KEYS:
        a = json.dumps(_dig(v1_spec, k), sort_keys=True, ensure_ascii=False)
        b = json.dumps(_dig(v2_spec, k), sort_keys=True, ensure_ascii=False)
        out.append({"key": k, "identical": a == b,
                    "v1_bytes": len(a.encode("utf-8")), "v2_bytes": len(b.encode("utf-8"))})
    return out


# ---------------------------------------------------------------------------
# ★★ v2 자체 게이트 — 6조건. v1 의 enforce_gin_block() 을 쓰지 않는다.
# ---------------------------------------------------------------------------
def require_supersession(cfg_dir=None, supersede_path=None) -> dict:
    """6조건(docs/108 §2-3 축자 순서)을 검사한다. 하나라도 불충족 → exit 12.

    ★ 두 인자는 **`--stage selftest` 의 음성 검사(T5~T7) 전용**이다. `train`·`verify` 분기는
      반드시 **인자 없이** 호출하며, CLI 에 이 두 값을 받는 옵션을 만들지 않고 환경변수도
      읽지 않는다(블록 AR 의 `bypass_paths_explicitly_absent` 규약 계승).

    조건 0  v1 산출물 2종(하네스·규격) sha256 일치
    조건 1  ①②③ sha256 이 PINNED_SHA256 과 일치
    조건 2  ①②③ 의 gin_start_still_blocked 가 **전부 true** (false 면 거부)
    조건 3  승인 이벤트 존재 · sha256 일치 · is_authorization == true
    조건 4  승인 이벤트의 blocking_artifacts_verified 3건이 조건 1·2 실측과 일치
    조건 5  unblinding_performed == false **그리고** 봉인 계수 25/291/275/16 일치(stat-only)
    """
    cfg = cfg_dir if cfg_dir is not None else v1.CFG_DIR
    sup = supersede_path if supersede_path is not None else SUPERSEDE_PATH
    checks, fails = [], []

    def rec(cond, name, ok, detail):
        checks.append({"condition": cond, "name": name, "pass": bool(ok), "detail": detail})
        if not ok:
            fails.append("%d:%s" % (cond, name))

    # --- 조건 0 -------------------------------------------------------------
    d0 = {}
    for rel in ("v3_Multimodal/src/confirmatory_gin_rep.py",
                "v3_Multimodal/config/gin_confirm_harness_freeze.json"):
        got = v1.sha256_file(_abs(rel))
        d0[rel] = {"expected": PINNED_SHA256[rel], "actual": got, "match": got == PINNED_SHA256[rel]}
    rec(0, "v1_artifacts_sha256", all(x["match"] for x in d0.values()), d0)

    # --- 조건 1·2 -----------------------------------------------------------
    d1, d2 = {}, {}
    for name in v1.BLOCK_FLAG_FILES:
        rel = "v3_Multimodal/config/" + name
        p = os.path.join(cfg, name)
        if not os.path.exists(p):
            d1[rel] = {"expected": PINNED_SHA256[rel], "actual": None, "match": False,
                       "note": "파일 부재"}
            d2[rel] = {"gin_start_still_blocked": None, "is_true": False, "note": "파일 부재"}
            continue
        got = v1.sha256_file(p)
        d1[rel] = {"expected": PINNED_SHA256[rel], "actual": got,
                   "match": got == PINNED_SHA256[rel]}
        flag = v1.load_json(p).get(v1.BLOCK_FLAG)
        d2[rel] = {"gin_start_still_blocked": flag, "is_true": flag is True}
    rec(1, "blocking_flag_files_sha256", all(x["match"] for x in d1.values()), d1)
    rec(2, "blocking_flags_still_all_true", all(x["is_true"] for x in d2.values()), d2)

    # --- 조건 3 -------------------------------------------------------------
    ev = None
    if not os.path.exists(sup):
        rec(3, "supersede_event", False, {"path": sup, "note": "승인 이벤트 파일 부재"})
    else:
        got = v1.sha256_file(sup)
        exp = PINNED_SHA256["v3_Multimodal/config/gin_start_supersede.json"]
        ev = v1.load_json(sup)
        ok = (got == exp) and (ev.get("is_authorization") is True)
        rec(3, "supersede_event", ok,
            {"path": sup, "expected": exp, "actual": got, "sha_match": got == exp,
             "is_authorization": ev.get("is_authorization")})

    # --- 조건 4 -------------------------------------------------------------
    if ev is None:
        rec(4, "blocking_artifacts_verified_consistent", False, {"note": "승인 이벤트 없음"})
    else:
        bav = {b.get("path"): b for b in ev.get("blocking_artifacts_verified", [])}
        d4, ok4 = {}, len(bav) == 3
        for rel, obs in d1.items():
            claim = bav.get(rel)
            same = bool(claim) and claim.get("sha256") == obs["actual"] \
                and claim.get("gin_start_still_blocked") is True \
                and d2[rel]["is_true"]
            d4[rel] = {"claimed_sha256": (claim or {}).get("sha256"),
                       "observed_sha256": obs["actual"],
                       "claimed_flag": (claim or {}).get("gin_start_still_blocked"),
                       "observed_flag": d2[rel]["gin_start_still_blocked"],
                       "consistent": same}
            ok4 = ok4 and same
        rec(4, "blocking_artifacts_verified_consistent", ok4, d4)

    # --- 조건 5 -------------------------------------------------------------
    sc = sealed_counts()
    unb = (ev or {}).get("unblinding_performed")
    ok5 = (unb is False) and (sc == SEALED_COUNTS_EXPECTED)
    rec(5, "not_unblinded_and_sealed_counts", ok5,
        {"unblinding_performed": unb, "sealed_counts_observed": sc,
         "sealed_counts_expected": SEALED_COUNTS_EXPECTED,
         "sealed_files_opened": 0, "sealed_files_hashed": 0, "method": "stat-only"})

    res = {"n_conditions": 6, "n_pass": sum(1 for c in checks if c["pass"]),
           "all_pass": not fails, "failed": fails, "checks": checks,
           "cfg_dir": cfg, "supersede_path": sup}
    if fails:
        sys.stderr.write("supersession 미충족 — 실행 거부(exit %d): %s\n"
                         % (EXIT_SUPERSESSION_UNMET, ", ".join(fails)))
        sys.exit(EXIT_SUPERSESSION_UNMET)
    return res


def _gate_verdict(cfg_dir=None, supersede_path=None) -> dict:
    """require_supersession 을 **exit 없이** 판정만 얻는다(T5~T7 음성 검사용)."""
    code = (
        "import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r);"
        "import confirmatory_gin_rep_v2 as m;"
        "r = m.require_supersession(%r, %r);"
        "print('GATE_PASS')" % (_HERE, cfg_dir, supersede_path)
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", code],
                       capture_output=True, text=True, env=env, cwd=_ROOT)
    return {"returncode": p.returncode, "stderr": p.stderr.strip()[:400],
            "rejected": p.returncode == EXIT_SUPERSESSION_UNMET}


# ---------------------------------------------------------------------------
# stage: selftest — 10건 (T1~T10)
# ---------------------------------------------------------------------------
def _synthetic_cfg_dir(tmp: str, *, include_supersede: bool,
                       tamper_bav: bool = False, flip_flag_1: bool = False) -> str:
    """★ 원본 ①②③ 과 승인 이벤트를 **이동·개명·삭제하지 않는다.** 합성 «사본» 만 만든다."""
    d = os.path.join(tmp, "cfg")
    os.makedirs(d, exist_ok=True)
    for name in v1.BLOCK_FLAG_FILES:
        src = os.path.join(v1.CFG_DIR, name)
        dst = os.path.join(d, name)
        if flip_flag_1 and name == v1.BLOCK_FLAG_FILES[0]:
            obj = v1.load_json(src)
            obj[v1.BLOCK_FLAG] = False
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
                f.write("\n")
        else:
            shutil.copy2(src, dst)
    sup = None
    if include_supersede:
        sup = os.path.join(d, SUPERSEDE_NAME)
        if tamper_bav:
            obj = v1.load_json(SUPERSEDE_PATH)
            obj["blocking_artifacts_verified"][0]["sha256"] = "0" * 64
            with open(sup, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
                f.write("\n")
        else:
            shutil.copy2(SUPERSEDE_PATH, sup)
    return d, sup


def run_selftest() -> dict:
    cases = []

    def add(t, desc, ok, detail=None, skip=False):
        cases.append({"case": t, "desc": desc, "pass": bool(ok), "skip": bool(skip),
                      "detail": detail})

    pyc0 = pycache_dirs()
    sealed0 = sealed_counts()

    # --- T1 -----------------------------------------------------------------
    d = {}
    for rel, exp in V1_ARTIFACT_SHA256.items():
        got = v1.sha256_file(_abs(rel))
        d[rel] = {"expected": exp, "actual": got, "match": got == exp,
                  "bytes": os.stat(_abs(rel)).st_size}
    add("T1", "v1 산출물 6종 + gin_inner_valid_freeze.status.json sha256 = F5",
        all(x["match"] for x in d.values()), d)

    # --- T2 -----------------------------------------------------------------
    st = v1.gin_block_status()
    d = {}
    for name in v1.BLOCK_FLAG_FILES:
        rel = "v3_Multimodal/config/" + name
        got = v1.sha256_file(os.path.join(v1.CFG_DIR, name))
        d[rel] = {"expected": PINNED_SHA256[rel], "actual": got,
                  "match": got == PINNED_SHA256[rel]}
    ok = all(x["match"] for x in d.values()) and all(s[v1.BLOCK_FLAG] for s in st) and len(st) == 3
    add("T2", "①②③ sha256 = F4 및 v1.gin_block_status() 3/3 true",
        ok, {"sha256": d, "v1_gin_block_status": st,
             "n_true": sum(1 for s in st if s[v1.BLOCK_FLAG])})

    # --- T3 -----------------------------------------------------------------
    got = v1.sha256_file(SUPERSEDE_PATH)
    exp = PINNED_SHA256["v3_Multimodal/config/gin_start_supersede.json"]
    ev = v1.load_json(SUPERSEDE_PATH)
    bav = {b["path"]: b for b in ev.get("blocking_artifacts_verified", [])}
    cons = {}
    for name in v1.BLOCK_FLAG_FILES:
        rel = "v3_Multimodal/config/" + name
        obs = v1.sha256_file(os.path.join(v1.CFG_DIR, name))
        c = bav.get(rel, {})
        cons[rel] = {"claimed": c.get("sha256"), "observed": obs,
                     "claimed_flag": c.get("gin_start_still_blocked"),
                     "consistent": c.get("sha256") == obs
                                   and c.get("gin_start_still_blocked") is True}
    ok = (got == exp) and (ev.get("is_authorization") is True) \
        and all(x["consistent"] for x in cons.values()) and len(bav) == 3
    add("T3", "승인 이벤트 sha256 = PINNED_SHA256 · is_authorization true · "
              "blocking_artifacts_verified 3건 = T2 실측",
        ok, {"expected": exp, "actual": got, "is_authorization": ev.get("is_authorization"),
             "consistency": cons})

    # --- T4 -----------------------------------------------------------------
    s1 = v1.load_json(os.path.join(v1.CFG_DIR, "gin_confirm_harness_freeze.json"))
    s2 = v1.load_json(os.path.join(v1.CFG_DIR, V2_SPEC_NAME))
    diff = science_diff(s1, s2)
    add("T4", "v1↔v2 과학 명세 기계 diff — 지정 9키 전건 바이트 동일 "
              "(harness.stages·default_stage 는 대상 아님)",
        all(x["identical"] for x in diff),
        {"keys": diff, "n_identical": sum(1 for x in diff if x["identical"]),
         "excluded_from_diff": ["harness.stages", "harness.default_stage"]})

    # --- T5~T7 (음성 검사) ---------------------------------------------------
    orig = {}
    for name in v1.BLOCK_FLAG_FILES:
        orig["v3_Multimodal/config/" + name] = v1.sha256_file(os.path.join(v1.CFG_DIR, name))
    orig["v3_Multimodal/config/" + SUPERSEDE_NAME] = v1.sha256_file(SUPERSEDE_PATH)

    tmp = tempfile.mkdtemp(prefix="as_selftest_", dir=RUN_DIR)
    try:
        cfg5, _ = _synthetic_cfg_dir(tmp + "/t5", include_supersede=False)
        r5 = _gate_verdict(cfg5, os.path.join(tmp, "t5", "cfg", "__absent__.json"))
        add("T5", "음성 1 — 승인 이벤트 부재 합성 cfg → exit 12 거부 (원본 이동·개명·삭제 0)",
            r5["rejected"], r5)

        cfg6, sup6 = _synthetic_cfg_dir(tmp + "/t6", include_supersede=True, tamper_bav=True)
        r6 = _gate_verdict(cfg6, sup6)
        add("T6", "음성 2 — blocking_artifacts_verified 변조 합성 사본 → 거부 (원본 무수정)",
            r6["rejected"], r6)

        cfg7, sup7 = _synthetic_cfg_dir(tmp + "/t7", include_supersede=True, flip_flag_1=True)
        r7 = _gate_verdict(cfg7, sup7)
        add("T7", "음성 3 — ①의 플래그를 false 로 만든 합성 사본 → 거부"
                  "(조건 2 = 여전히 true 여야 함 · 원본 무수정)",
            r7["rejected"], r7)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    after = {}
    for name in v1.BLOCK_FLAG_FILES:
        after["v3_Multimodal/config/" + name] = v1.sha256_file(os.path.join(v1.CFG_DIR, name))
    after["v3_Multimodal/config/" + SUPERSEDE_NAME] = v1.sha256_file(SUPERSEDE_PATH)
    originals_intact = (orig == after) and all(
        os.path.exists(os.path.join(v1.CFG_DIR, n)) for n in v1.BLOCK_FLAG_FILES) \
        and os.path.exists(SUPERSEDE_PATH)

    # --- T8 -----------------------------------------------------------------
    fz = v1.load_frozen()
    plan = v1.build_plan(v1.frozen_design(fz))
    ok = (plan["n_confirmatory"] == 315 and plan["n_stability"] == 42
          and plan["n_total"] == 357 and plan["oof_matrices_total"] == 63
          and plan["oof_matrices_primary_rqint"] == 18
          and plan["oof_matrix_shape"] == [1092, 370])
    add("T8", "v1.build_plan(v1.frozen_design(...)) = 315/42/357 · OOF 63/primary 18 · [1092,370]",
        ok, {k: plan[k] for k in ("n_confirmatory", "n_stability", "n_total",
                                  "oof_matrices_total", "oof_matrices_primary_rqint",
                                  "oof_matrix_shape")})

    # --- T9 (AST 금지 가드) ---------------------------------------------------
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)

    banned = ("open_sealed", "emit_sign", "sap.decision", "decision",
              "requests", "urllib", "http")
    imported, import_nodes = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            import_nodes.append(n)
            imported += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            import_nodes.append(n)
            mod = n.module or ""
            imported += [mod] + ["%s.%s" % (mod, a.name) for a in n.names]
    a9 = [m for m in imported
          if any(m == b or m.startswith(b + ".") or m.endswith("." + b) for b in banned)]

    def _fn(name):
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == name:
                return n
        return None

    main_fn = _fn("main")
    b9 = [ast.unparse(x.func) for x in ast.walk(tree)
          if isinstance(x, ast.Call) and "enforce_gin_block" in ast.unparse(x.func)]

    # (c) train 분기의 require_supersession 호출 인자 0개
    c9 = {"found": False, "n_args": None, "n_kwargs": None}
    for n in ast.walk(main_fn) if main_fn else []:
        if isinstance(n, ast.If) and "train" in ast.unparse(n.test):
            for x in ast.walk(n):
                if isinstance(x, ast.Call) and ast.unparse(x.func) == "require_supersession":
                    c9 = {"found": True, "n_args": len(x.args), "n_kwargs": len(x.keywords)}
    # (d) 모든 import 문이 `import confirmatory_gin_rep` 앞
    v1_import_line = min(n.lineno for n in import_nodes
                         if isinstance(n, ast.Import)
                         and any(a.name == "confirmatory_gin_rep" for a in n.names))
    later = [ast.unparse(n) for n in import_nodes if n.lineno > v1_import_line]

    ok = (not a9) and (not b9) and c9["found"] and c9["n_args"] == 0 and c9["n_kwargs"] == 0 \
        and not later
    add("T9", "금지 가드 AST — (a) 금지 import 0 · (b) enforce_gin_block 호출 0(모듈 전역 — "
              "train·verify 경로 포함 부재) · (c) train 분기 require_supersession 인자 0개 · "
              "(d) 모든 import 가 v1 import 앞",
        ok, {"a_banned_imports": a9, "b_enforce_gin_block_calls_module_wide": b9,
             "c_train_require_supersession": c9,
             "d_v1_import_lineno": v1_import_line, "d_imports_after_v1": later,
             "imported": sorted(set(imported))})

    # --- T10 ----------------------------------------------------------------
    pyc1 = pycache_dirs()
    sealed1 = sealed_counts()
    ok = (pyc0 == pyc1) and (sealed0 == sealed1 == SEALED_COUNTS_EXPECTED)
    add("T10", "위생 — __pycache__ 착수=종료 · 봉인 25/291/275/16 불변 · _sealed 디렉터리 생성 0",
        ok, {"pycache_dirs_before": pyc0, "pycache_dirs_after": pyc1,
             "sealed_before": sealed0, "sealed_after": sealed1,
             "sealed_dirs_created": 0,
             "counting_convention": "__pycache__ = archive/ 포함 (블록 AR 4,541 규약)"})

    n_pass = sum(1 for c in cases if c["pass"] and not c["skip"])
    n_skip = sum(1 for c in cases if c["skip"])
    return {
        "_doc": "블록 AS — v2 supersession 하네스 자체검사 10건(docs/109 AS-6).",
        "block": "AS",
        "harness": "v3_Multimodal/src/confirmatory_gin_rep_v2.py",
        "as_of_kst": v1.now_kst(),
        "confirmatory_training_runs_performed": 0,
        "unblinding_performed": False,
        "is_authorization": False,
        "sys_path_after_v1_import": SYS_PATH_AFTER_V1_IMPORT,
        "originals_intact_after_T5_T7": {
            "sha256_before": orig, "sha256_after": after, "intact": originals_intact,
            "note": "T5~T7 은 합성 cfg 디렉터리로만 수행했다. 원본 ①②③ 과 승인 이벤트는 "
                    "읽기 외 접근 0 · 이동·개명·삭제·수정 0.",
        },
        "n_cases": len(cases), "n_pass": n_pass, "n_skip": n_skip,
        "all_pass": (n_pass + n_skip) == len(cases),
        "all_pass_definition": "all_pass = (n_pass + n_skip == n_cases)",
        "cases": cases,
    }


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="GIN 착수 권한 supersession 하네스 (블록 AS)")
    ap.add_argument("--stage", choices=["selftest", "verify", "plan", "train"],
                    default="selftest")
    ap.add_argument("--out", default=None, help="plan/selftest 산출 경로(선택)")
    args = ap.parse_args()

    if args.stage == "train":
        # ★ require_supersession 은 **인자 없이** 호출한다(기본값 = v1 CFG_DIR + 저장소 승인 이벤트).
        require_supersession()
        raise SystemExit("착수 구현은 다음 블록 — 블록 AS 는 확증 학습 0회다.")

    if args.stage == "verify":
        res = require_supersession()
        print(json.dumps({k: res[k] for k in ("n_conditions", "n_pass", "all_pass", "failed")},
                         ensure_ascii=False, indent=2))
        return 0

    if args.stage == "plan":
        plan = v1.build_plan(v1.frozen_design(v1.load_frozen()))
        plan["gin_block_status"] = v1.gin_block_status()
        plan["is_authorization"] = False
        summary = {k: v for k, v in plan.items()
                   if k not in ("confirmatory_units", "stability_units")}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.out:
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print("[plan] wrote %s" % args.out)
        return 0

    res = run_selftest()
    for c in res["cases"]:
        mark = "SKIP" if c["skip"] else ("PASS" if c["pass"] else "FAIL")
        print("  %-4s %-4s %s" % (c["case"], mark, c["desc"]))
    print("[selftest] n_cases=%d n_pass=%d n_skip=%d all_pass=%s"
          % (res["n_cases"], res["n_pass"], res["n_skip"], res["all_pass"]))
    out = args.out or os.path.join(RUN_DIR, "selftest_v2.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("[selftest] wrote %s" % out)
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
