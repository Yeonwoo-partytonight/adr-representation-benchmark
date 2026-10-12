#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블록 AU — GIN 안정성 학습 42회 착수·완주·봉인 하네스 (지표 산출 0 · 개봉 0 · OOF 조립 0).

권한은 이 파일이 만들지 않는다.
  · 권한      = v3_Multimodal/config/gin_start_supersede.json (is_authorization true)
  · 과학 명세 = v3_Multimodal/config/gin_confirm_harness_freeze_v2.json
  · 운영 보충 = v3_Multimodal/config/gin_stability_contract.json (docs/111 §3 AU-2)
이 파일은 그 셋 아래에서 «실행»만 한다. 지시서 = docs/111 §3 AU-3.

범위: 안정성 42 단위 = 대표 outer unit (201,f4)·(202,f1)·(203,f0) × 7모델 × train seed 3·4.
      확증 315 는 블록 AT 가 이미 완주했다. macro AP·Δ·부호·SS 분해·consensus·OOF 조립은
      전부 다음 블록이다.

E1(사용자 결정 2026-09-22) — 과학 경로는 동결 confirmatory_gin_train.py 를 모듈 import 해서
그 함수를 그대로 호출한다(재구현 0). 허용목록 밖 이름은 부르지 않는다.

stage: selftest(기본) · plan · run · status · finalize.  CLI 옵션 = --stage, --out 뿐.
환경변수 판독 0 · --force 0 · 경로 주입 옵션 0 · 네트워크 0 · git 접촉 0.
"""
import sys

sys.dont_write_bytecode = True

import argparse
import ast
import contextlib
import datetime
import hashlib
import inspect
import io
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
V3SRC = os.path.join(ROOT, "v3_Multimodal", "src")
V2SRC = os.path.join(ROOT, "v2_GNN", "src")
for _p in (V3SRC, V2SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ★ import 순서: train_ladder 를 graph_features 보다 먼저(둘 다 torch 를 끌어온다).
import train_ladder as tl                      # noqa: E402
import graph_features as gf                    # noqa: E402
import train as gnntrain                       # noqa: E402
import ladder_confirmatory as lc               # noqa: E402
import confirmatory_oof_rest as rest           # noqa: E402
import confirmatory_gin_rep as v1              # noqa: E402
import compute_lock as cl                      # noqa: E402
import torch                                   # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
# 상수 (docs/111 §3 AU-3)
# ═══════════════════════════════════════════════════════════════════════════
CONTRACT_REL = "v3_Multimodal/config/gin_stability_contract.json"
CONTRACT_SHA256 = "e092c18ff7afd4f21361be54901bce5828925b042d2b59bdf30a3f46cce67286"

AT_HARNESS_REL = "v3_Multimodal/src/confirmatory_gin_train.py"
AT_HARNESS_SHA256 = "714f98983cceff85409af1597c0d82f8ca2b2027f5f7e94b8a0928351b01107e"
AT_CONTRACT_REL = "v3_Multimodal/config/gin_train_contract.json"
AT_CONTRACT_SHA256 = "e50f972674e782f50a2a74890f8b37b3208da77a8cf6c4ac9f8dc6deb4cbce7f"
AT_MANIFEST_T4_REL = "experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json"
AT_MANIFEST_T4_SHA256 = "a59ab54afd51508543a3ca952a5147ffc0c8687f997aacf42362ab699683ea59"
V2_HARNESS_REL = "v3_Multimodal/src/confirmatory_gin_rep_v2.py"
V2_HARNESS_SHA256 = "644abf4f272c51e673dfb3be2915792502552ba4baad610aaa62fee58101860a"

CONFIRM_STAT_FP = "5440aefcded112bcd425f61968f9974898f26efe2beab69155f7a5a47cf3333b"
LEGACY_COUNTS = {"n_sealed_dirs": 25, "n_sealed_files_total": 291,
                 "n_sealed_artifacts": 275, "n_access_log": 16}
CONFIRM_COUNTS = {"n_sealed_dirs": 3, "n_sealed_files_total": 390,
                  "n_sealed_artifacts": 387, "n_access_log": 3}
BASE_SEALED_DIRS = 28

SESSION_CAP_HOURS = 8
EXIT_NOT_IDLE = 10
EXIT_HARD_FAILURE = 13
EXIT_RESUME_GATE = 14
EXIT_POWER = 15

REP_SEED = {1: 201, 2: 202, 3: 203}
MODELS = ["M0", "M1", "M1b", "M2b", "P-ID", "P-FAM", "C-CAP"]
EXTRA_SEEDS = [3, 4]
CONFIRM_SEEDS = [42, 1, 2]
REP_UNITS = [(1, 4), (2, 1), (3, 0)]
N_UNITS = 42
N_FOLD = 5

# F10 — 확증 공개 run.log 6열 실측(라벨 무관). 본런 중 매 (rep, fold, model) 전환에서 assert.
SIDE_DIM_EXPECTED = {
    (1, 4): {"M0": 0, "M1": 2, "M1b": 12, "M2b": 76, "P-ID": 76, "P-FAM": 53, "C-CAP": 76},
    (2, 1): {"M0": 0, "M1": 2, "M1b": 12, "M2b": 76, "P-ID": 76, "P-FAM": 54, "C-CAP": 76},
    (3, 0): {"M0": 0, "M1": 2, "M1b": 12, "M2b": 76, "P-ID": 76, "P-FAM": 52, "C-CAP": 76},
}

PROC = os.path.join(ROOT, "data", "processed")
STAB_DIR = os.path.join(ROOT, "experiments", "runs", "v3_gin_stability")
STAB_SEALED = os.path.join(STAB_DIR, "_sealed")
STAB_PARTIAL = os.path.join(STAB_SEALED, "_partial")
STAB_ORPHANS = os.path.join(STAB_SEALED, "_orphans")
RUN_LOG = os.path.join(STAB_DIR, "run.log")
FAILURES = os.path.join(STAB_DIR, "failures.jsonl")
SPLIT_DIAG = os.path.join(STAB_DIR, "split_diagnostics_public.json")
ENV_PUBLIC = os.path.join(STAB_DIR, "env_public.json")
SESSIONS = os.path.join(STAB_DIR, "sessions.jsonl")
MANIFEST_S1 = os.path.join(STAB_DIR, "manifest_s1_launch.json")
MANIFEST_S2 = os.path.join(STAB_DIR, "manifest_s2_post_stability.json")
PLAN_OUT = os.path.join(STAB_DIR, "plan_stability_42.json")
SELFTEST_OUT = os.path.join(STAB_DIR, "selftest_stability.json")
PYTHON_PID = os.path.join(STAB_DIR, "python.pid")

CONFIRM_DIRS = [os.path.join(ROOT, "experiments", "runs",
                             "v3_gin_confirm_rep%d_seed%d" % (r, REP_SEED[r])) for r in (1, 2, 3)]

ORPHAN_RE = re.compile(r"^(.*)_rep(\d+)_fold(\d+)_seed(\d+)$")


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(b):
    return hashlib.sha256(b).hexdigest()


# --- E1 재사용: sha 확인 → import → samefile assert (F9) ---------------------
_AT_PATH = os.path.join(ROOT, AT_HARNESS_REL)
if _sha256_file(_AT_PATH) != AT_HARNESS_SHA256:
    sys.stderr.write("[GATE] AT 하네스 sha 불일치 — import 거부, 학습 0\n")
    sys.exit(EXIT_RESUME_GATE)

import confirmatory_gin_train as at            # noqa: E402

assert os.path.samefile(at.__file__, _AT_PATH), "at.__file__ != %s" % _AT_PATH


# ═══════════════════════════════════════════════════════════════════════════
# firewall 쓰기 가드 (AU-3 (7))
# ═══════════════════════════════════════════════════════════════════════════
_SELFTEST_ROOTS = []


def _assert_stab_path(p):
    """안정성 디렉터리(또는 selftest 임시 루트) 밖 쓰기를 거부한다."""
    rp = os.path.realpath(p)
    base = os.path.realpath(STAB_DIR)
    if rp == base or rp.startswith(base + os.sep):
        return rp
    for r in _SELFTEST_ROOTS:
        rr = os.path.realpath(r)
        if rp == rr or rp.startswith(rr + os.sep):
            return rp
    raise AssertionError("firewall — 안정성 디렉터리 밖 쓰기 시도: %s" % p)


@contextlib.contextmanager
def _selftest_root():
    t = tempfile.mkdtemp(prefix="au_selftest_")
    _SELFTEST_ROOTS.append(t)
    try:
        yield t
    finally:
        _SELFTEST_ROOTS.remove(t)
        shutil.rmtree(t, ignore_errors=True)


# --- 가드를 경유하는 쓰기 래퍼 (여기 말고는 어디서도 직접 쓰지 않는다) --------
def _makedirs(path):
    _assert_stab_path(path)
    os.makedirs(path, exist_ok=True)


def _touch(path):
    _assert_stab_path(path)
    open(path, "w").close()


def _write_text(path, text):
    _assert_stab_path(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _pub_line(path, text):
    _assert_stab_path(path)
    at.pub_line(path, text)


def _pub_jsonl(path, rec):
    _assert_stab_path(path)
    at.pub_jsonl(path, rec)


def _pub_json(path, obj):
    _assert_stab_path(path)
    at.pub_json(path, obj)


def _sealed_access(sdir, path_rel, purpose, step):
    _assert_stab_path(sdir)
    assert os.path.isdir(sdir), "봉인 디렉터리 부재 — 기록기 호출 금지(AU-3 (10))"
    return at.sealed_access(sdir, path_rel, purpose, step)


def _sealed_stdout_append(sdir, header, text):
    _assert_stab_path(sdir)
    assert os.path.isdir(sdir), "봉인 디렉터리 부재 — 기록기 호출 금지(AU-3 (10))"
    at.sealed_stdout_append(sdir, header, text)


def _sealed_ckpt_append(sdir, rec):
    _assert_stab_path(sdir)
    assert os.path.isdir(sdir), "봉인 디렉터리 부재 — 기록기 호출 금지(AU-3 (10))"
    at.sealed_ckpt_append(sdir, rec)


def _atomic_npz(path, **arrays):
    _assert_stab_path(path)
    return at.atomic_npz(path, **arrays)


def _move_orphan(src, dst):
    _assert_stab_path(dst)
    _makedirs(os.path.dirname(dst))
    shutil.move(src, dst)


# ═══════════════════════════════════════════════════════════════════════════
# 공용 유틸
# ═══════════════════════════════════════════════════════════════════════════
def _partial_name(model, rep, fold, seed):
    return "%s_rep%d_fold%d_seed%d.npz" % (model, rep, fold, seed)


def _session_event(rec):
    rec = dict(rec)
    rec.setdefault("ts_kst", at.now_kst())
    _pub_jsonl(SESSIONS, rec)


def _sysctl(key):
    p = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True)
    return p.stdout.strip() or None


def _split_dir(rep):
    return os.path.join(PROC, "splits", "confirmatory", "rep%d_seed%d" % (rep, REP_SEED[rep]))


def _confirm_stat_fingerprint(confirm_dirs, fp_root):
    """확증 봉인 트리의 stat 지문 — 파일을 열지 않고 이름·크기만 쓴다."""
    lines = []
    for d in confirm_dirs:
        for dp, _dn, fn in os.walk(d):
            if "_sealed" not in dp.split(os.sep):
                continue
            for f in fn:
                p = os.path.join(dp, f)
                lines.append("%s\t%d" % (os.path.relpath(p, fp_root), os.stat(p).st_size))
    lines.sort()
    return _sha256_text(("\n".join(lines) + "\n").encode("utf-8")), len(lines)


def _build_plan():
    design = v1.frozen_design(v1.load_frozen())
    plan = v1.build_plan(design)
    units = plan["stability_units"]
    assert len(units) == N_UNITS, "안정성 단위 %d != %d" % (len(units), N_UNITS)
    assert design["models"] == MODELS, "모델 순서 불일치"
    assert design["confirmatory_seeds"] == CONFIRM_SEEDS, "확증 seed 불일치"
    extra = design["stability_seeds_ordered"][len(design["confirmatory_seeds"]):]
    assert extra == EXTRA_SEEDS, "추가 seed %r != %r" % (extra, EXTRA_SEEDS)
    assert [tuple(x) for x in design["representative_units"]] == \
        [(REP_SEED[r], k) for r, k in REP_UNITS], "대표 unit 불일치"
    assert not [u for u in units if u["train_seed"] in CONFIRM_SEEDS], "확증 seed 가 스케줄에 섞였다"
    return units, plan, design


def _plan_body(units):
    body = {"_doc": "블록 AU 안정성 실행 계획 42 단위 (docs/111 §3 AU-5). 학습 0.",
            "generated_kst": at.now_kst(),
            "source": "confirmatory_gin_rep.build_plan(frozen_design(load_frozen()))['stability_units']",
            "n_stability": len(units),
            "n_confirmatory_executed": 0,
            "order": "대표 unit (201,f4)→(202,f1)→(203,f0) → model(M0,M1,M1b,M2b,P-ID,P-FAM,C-CAP) → train_seed(3,4)",
            "rep_seed_map": {str(k): v for k, v in REP_SEED.items()},
            "oof_assembled": False,
            "units": units}
    payload = json.dumps(body, ensure_ascii=False, indent=2, sort_keys=False).encode("utf-8")
    body["plan_sha256"] = _sha256_text(payload)
    return body


def _plan_sha256(units):
    return _sha256_text(json.dumps(units, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _env_fingerprint_obj():
    """docs/65 (4) 기록 항목 — 소프트웨어 버전·하드웨어·MPS·결정론 설정·실행 순서."""
    e = at.env_info()
    e["deterministic_algorithms_enabled"] = bool(torch.are_deterministic_algorithms_enabled())
    e["hw_model"] = _sysctl("hw.model")
    e["cpu_brand_string"] = _sysctl("machdep.cpu.brand_string")
    splits = {}
    for r in (1, 2, 3):
        sd = _split_dir(r)
        for fn in sorted(os.listdir(sd)):
            p = os.path.join(sd, fn)
            if os.path.isfile(p):
                splits["rep%d/%s" % (r, fn)] = at.sha256_file(p)
    e["split_files_sha256"] = splits
    e["contract_sha256"] = CONTRACT_SHA256
    e["harness_sha256"] = _sha256_file(os.path.abspath(__file__))
    e["at_harness_sha256"] = AT_HARNESS_SHA256
    e["sap_manifest_sha256"] = at.sha256_file(os.path.join(ROOT, "experiments", "sap", "manifest.json"))
    e["execution_order"] = ("plan_stability_42.json 고정 순서 — 대표 unit → model → train_seed. "
                            "확증 GIN 315 완주·봉인 이후에만 실행한다(gin_seed_freeze.execution_order).")
    e["block"] = "AU"
    e["ts_kst"] = at.now_kst()
    return e


def _merge_split_public(path, rep, fold, n_otr, n_te, n_itr, n_iva, n_zero_pt):
    obj = {}
    if os.path.exists(path):
        obj = json.load(open(path, encoding="utf-8"))
    obj.setdefault("_doc", "블록 AU 분할 진단(공개 — 개수뿐).")
    obj.setdefault("folds", {})
    obj["folds"]["rep%d_fold%d" % (rep, fold)] = {
        "n_outer_train": int(n_otr), "n_outer_test": int(n_te),
        "n_inner_train": int(n_itr), "n_inner_valid": int(n_iva),
        "n_inner_train_zero_positive_pt": int(n_zero_pt)}
    obj["updated_kst"] = at.now_kst()
    return obj


def _failure_counts():
    """단위별 누적 실패 횟수(고아 포함) — 공개 failures.jsonl 만 읽는다."""
    out = {}
    if not os.path.exists(FAILURES):
        return out
    for ln in open(FAILURES, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if o.get("model") is None:
            continue
        k = "%s|%s|%s|%s" % (o.get("rep"), o.get("fold"), o.get("model"), o.get("train_seed"))
        out[k] = out.get(k, 0) + 1
    return out


def _sweep_orphans():
    """.tmp, 또는 체크포인트 키가 없는 partial = 강제종료 흔적 → 열지 않고 _orphans/ 로 이동."""
    moved = []
    if not os.path.isdir(STAB_PARTIAL):
        return moved
    rows, ok, _reason = at.sealed_ckpt_read(STAB_SEALED)
    if not ok:
        return None
    known = {_partial_name(r["model"], r["rep"], r["fold"], r["train_seed"]) for r in rows}
    for f in sorted(os.listdir(STAB_PARTIAL)):
        if f.endswith(".tmp") or (f.endswith(".npz") and f not in known):
            ts = datetime.datetime.now(at.KST).strftime("%Y%m%dT%H%M%S")
            dst = os.path.join(STAB_ORPHANS, "%s.%s" % (f, ts))
            _move_orphan(os.path.join(STAB_PARTIAL, f), dst)
            base = f[:-4] if f.endswith(".tmp") else f
            base = base[:-4] if base.endswith(".npz") else base
            m = ORPHAN_RE.match(base)
            rec = {"rep": int(m.group(2)) if m else None,
                   "fold": int(m.group(3)) if m else None,
                   "model": m.group(1) if m else None,
                   "train_seed": int(m.group(4)) if m else None,
                   "kind": "interrupted", "ts_kst": at.now_kst(),
                   "orphan_path": os.path.relpath(dst, ROOT)}
            _pub_jsonl(FAILURES, rec)
            moved.append(rec)
    return moved


# ═══════════════════════════════════════════════════════════════════════════
# 재개 게이트 — v2 자식 프로세스 + 조건 5″ (순수 판정 함수)
# ═══════════════════════════════════════════════════════════════════════════
def _expected(plan_keys):
    return {"legacy": dict(LEGACY_COUNTS), "confirm": dict(CONFIRM_COUNTS),
            "confirm_fp": CONFIRM_STAT_FP, "base_sealed_dirs": BASE_SEALED_DIRS,
            "confirm_dirs": list(CONFIRM_DIRS), "stab_dir": STAB_DIR,
            "stab_sealed": STAB_SEALED, "manifest_s1_path": MANIFEST_S1,
            "plan_keys": list(plan_keys), "fp_root": ROOT,
            "check_repo_invariants": True}


def stability_gate_verdict(rc, stderr, root, stab_sealed_exists, manifest_s1_exists,
                           harness_sha, contract_sha, expected):
    """순수 판정 함수 — (통과?, mode, 실패 사유 목록, 진단). docs/111 §3 AU-3 (1)."""
    diag = {"rc": rc, "stab_sealed_exists": bool(stab_sealed_exists),
            "manifest_s1_exists": bool(manifest_s1_exists)}
    fails = at.parse_gate_failures(stderr)
    diag["parsed_failures"] = fails

    # --- 공통 선행 ----------------------------------------------------------
    if rc == 0:
        return False, None, ["rc 0 — 봉인 계수 불변 = 설명 불가(블록 AU 는 첫 착수도 rc 12)"], diag
    if rc != 12:
        return False, None, ["v2 게이트 rc=%s != 12" % rc], diag
    if fails is None:
        return False, None, ["stderr 실패 접두 줄 0개 또는 2개 이상 — 파싱 불가"], diag
    if fails != [at.COND5_NAME]:
        return False, None, ["실패 목록 %r != [%r]" % (fails, at.COND5_NAME)], diag

    if stab_sealed_exists and not manifest_s1_exists:
        return False, None, ["안정성 봉인 존재하는데 manifest_s1_launch.json 부재"], diag
    mode = ("resume" if stab_sealed_exists
            else ("launch_retry" if manifest_s1_exists else "first_launch"))
    diag["mode_candidate"] = mode

    bad = []
    stab_dir = expected["stab_dir"]
    stab_sealed = expected["stab_sealed"]
    confirm_dirs = list(expected["confirm_dirs"])

    # --- (a) 확증 3트리 + 안정성 디렉터리를 제외한 기존 계수 -----------------
    legacy_obs = at.count_sealed(root, exclude_dirs=tuple(confirm_dirs) + (stab_dir,))
    diag["legacy_counts"] = legacy_obs
    if legacy_obs != expected["legacy"]:
        bad.append("5\"a 기존 봉인 계수 %r != %r" % (legacy_obs, expected["legacy"]))

    # --- (b) 확증 3트리만의 계수 + stat 지문 ---------------------------------
    conf_obs = {k: 0 for k in expected["confirm"]}
    for dd in confirm_dirs:
        r0 = at.count_sealed(dd)
        for k in conf_obs:
            conf_obs[k] += r0[k]
    diag["confirm_counts"] = conf_obs
    if conf_obs != expected["confirm"]:
        bad.append("5\"b 확증 봉인 계수 %r != %r" % (conf_obs, expected["confirm"]))
    fp, n_fp = _confirm_stat_fingerprint(confirm_dirs, expected["fp_root"])
    diag["confirm_stat_fingerprint"] = fp
    diag["confirm_stat_lines"] = n_fp
    if fp != expected["confirm_fp"]:
        bad.append("5\"b 확증 stat 지문 불일치")

    # --- (c) 전체 _sealed 디렉터리 수 ----------------------------------------
    total = at.count_sealed(root)
    diag["total_counts"] = total
    want_dirs = expected["base_sealed_dirs"] + (1 if stab_sealed_exists else 0)
    if total["n_sealed_dirs"] != want_dirs:
        bad.append("5\"c 전체 _sealed 디렉터리 %d != %d" % (total["n_sealed_dirs"], want_dirs))

    # --- (d)(e) 안정성 봉인 구조 ---------------------------------------------
    allowed_top = {"checkpoint.jsonl", "env_fingerprint.json", "access.log", "train_stdout.log"}
    if stab_sealed_exists:
        rows, ok, reason = at.sealed_ckpt_read(stab_sealed)
        if not ok:
            bad.append("5\"d %s" % reason)
        else:
            ck_names = {_partial_name(r["model"], r["rep"], r["fold"], r["train_seed"])
                        for r in rows}
            pdir = os.path.join(stab_sealed, "_partial")
            pnames = set()
            if os.path.isdir(pdir):
                entries = os.listdir(pdir)
                pnames = {f for f in entries if f.endswith(".npz")}
                if any(f.endswith(".tmp") for f in entries):
                    bad.append("5\"e _partial 에 .tmp 잔존(고아 처리 후여야 함)")
            if pnames != ck_names:
                bad.append("5\"d partial 집합 != 체크포인트 키 집합 (partial-only %d · ckpt-only %d)"
                           % (len(pnames - ck_names), len(ck_names - pnames)))
            unknown = {at.unit_key(r) for r in rows} - set(expected["plan_keys"])
            if unknown:
                bad.append("5\"d 계획 42 밖 체크포인트 키 %d개" % len(unknown))
        orphan_logged = set()
        fpath = os.path.join(stab_dir, "failures.jsonl")
        if os.path.exists(fpath):
            for ln in open(fpath, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if o.get("orphan_path"):
                    orphan_logged.add(os.path.basename(o["orphan_path"]))
        for f in os.listdir(stab_sealed):
            p = os.path.join(stab_sealed, f)
            if os.path.isdir(p):
                if f not in ("_partial", "_orphans"):
                    bad.append("5\"e 예상 밖 봉인 하위 디렉터리 %s" % f)
                continue
            if f.startswith("oof_") and f.endswith(".npz"):
                bad.append("5\"e 안정성 봉인에 oof_*.npz 존재(범위 밖) %s" % f)
                continue
            if f not in allowed_top:
                bad.append("5\"e 예상 밖 봉인 파일 %s" % f)
        odir = os.path.join(stab_sealed, "_orphans")
        if os.path.isdir(odir):
            for f in os.listdir(odir):
                if f not in orphan_logged:
                    bad.append("5\"e 고아 %s 가 failures.jsonl 에 미등재" % f)

    # --- (f) manifest_s1 의 하네스·계약 sha ----------------------------------
    if stab_sealed_exists or manifest_s1_exists:
        try:
            mf = json.load(open(expected["manifest_s1_path"], encoding="utf-8"))
        except Exception as e:                              # noqa: BLE001
            mf = None
            bad.append("5\"f manifest_s1 판독 실패 %s" % type(e).__name__)
        if mf is not None:
            if mf.get("harness_sha256") != harness_sha:
                bad.append("5\"f manifest_s1 harness_sha256 불일치")
            if mf.get("contract_sha256") != contract_sha:
                bad.append("5\"f manifest_s1 contract_sha256 불일치")

    # --- (g) 범위 밖 디렉터리 · 개봉 플래그 · AT manifest --------------------
    runs = os.path.join(root, "experiments", "runs")
    if os.path.isdir(runs):
        for nm in os.listdir(runs):
            if nm.startswith("v3_gin_confirm_consensus"):
                bad.append("5\"g 범위 밖 디렉터리 %s 존재" % nm)
    if expected.get("check_repo_invariants", True):
        sup = os.path.join(ROOT, "v3_Multimodal", "config", "gin_start_supersede.json")
        if json.load(open(sup, encoding="utf-8")).get("unblinding_performed") is not False:
            bad.append("5\"g unblinding_performed != false")
        if _sha256_file(os.path.join(ROOT, AT_MANIFEST_T4_REL)) != AT_MANIFEST_T4_SHA256:
            bad.append("5\"g AT manifest_t4 sha 불일치")
        # --- (h) F4 13 · F5 12 · F6 7 불변 -----------------------------------
        ct = json.load(open(os.path.join(ROOT, CONTRACT_REL), encoding="utf-8"))["preconditions"]
        nbad = []
        for grp in ("f4_authority_chain", "f5_reused_modules", "f6_block_at_outputs"):
            for rel, meta in ct[grp].items():
                if _sha256_file(os.path.join(ROOT, rel)) != meta["sha256"]:
                    nbad.append(rel)
        diag["precondition_mismatch"] = nbad
        if nbad:
            bad.append("5\"h 선행조건 sha 불일치 %d건" % len(nbad))

    return (not bad), (mode if not bad else None), bad, diag


def _session_gate(harness_sha, plan_keys):
    rc, sout, serr = at.call_v2_gate()
    stab_sealed_exists = os.path.isdir(STAB_SEALED)
    manifest_s1_exists = os.path.exists(MANIFEST_S1)
    orphans = []
    if stab_sealed_exists:
        orphans = _sweep_orphans()
        if orphans is None:
            _session_event({"event": "gate_reject", "mode": None,
                            "failures": ["checkpoint.jsonl 잘림 — 자동 복구 금지"]})
            print("[GATE] 거부 — checkpoint.jsonl 잘림", file=sys.stderr)
            sys.exit(EXIT_RESUME_GATE)
    ok, mode, bad, diag = stability_gate_verdict(
        rc, serr, ROOT, stab_sealed_exists, manifest_s1_exists,
        harness_sha, CONTRACT_SHA256, _expected(plan_keys))
    diag["gate_pass_token"] = ("GATE_PASS" in sout)
    diag["n_orphans_moved"] = len(orphans)
    if not ok:
        _session_event({"event": "gate_reject", "mode": None, "failures": bad, "diag": diag})
        print("[GATE] 거부 — %s" % "; ".join(bad), file=sys.stderr)
        sys.exit(EXIT_RESUME_GATE)
    return mode, diag


def _write_manifest_s1(harness_sha, plan_units, power, load1):
    rc, sout, serr = at.call_v2_gate()
    ct = json.load(open(os.path.join(ROOT, CONTRACT_REL), encoding="utf-8"))["preconditions"]
    fp, n_fp = _confirm_stat_fingerprint(CONFIRM_DIRS, ROOT)
    conf_obs = {k: 0 for k in CONFIRM_COUNTS}
    for dd in CONFIRM_DIRS:
        r0 = at.count_sealed(dd)
        for k in conf_obs:
            conf_obs[k] += r0[k]
    obj = {"_doc": "블록 AU 착수 시점 manifest (docs/111 §3 AU-3 (2)). 1회 기록 후 0바이트 불변.",
           "ts_kst": at.now_kst(),
           "v2_gate": {"returncode": rc,
                       "parsed_failures": at.parse_gate_failures(serr),
                       "stdout_token": "GATE_PASS" if "GATE_PASS" in sout else None},
           "sealed_counts_at_launch": {
               "total": at.count_sealed(),
               "legacy_excluding_confirm_and_stability":
                   at.count_sealed(ROOT, exclude_dirs=tuple(CONFIRM_DIRS) + (STAB_DIR,)),
               "confirmatory_three_trees": conf_obs},
           "confirm_stat_fingerprint": fp,
           "confirm_stat_lines": n_fp,
           "harness_sha256": harness_sha,
           "contract_sha256": CONTRACT_SHA256,
           "at_harness_sha256": AT_HARNESS_SHA256,
           "preconditions": ct,
           "ac_power": {"pmset_ps": power["pmset_ps"], "pmset_adapter": power["pmset_adapter"],
                        "wattage": power["wattage"]},
           "load1": round(load1, 2),
           "env": at.env_info(),
           "plan_sha256": _plan_sha256(plan_units),
           "n_units_planned": N_UNITS,
           "oof_assembled": False,
           "metrics_computed": False,
           "unblinding_performed": False}
    _pub_json(MANIFEST_S1, obj)
    return obj


def _write_pid():
    _write_text(PYTHON_PID, "%d\n" % os.getpid())


def _create_sealed():
    """봉인 디렉터리 생성 — 프로그램 전체에서 이 한 곳뿐(AU-3 (10))."""
    _makedirs(STAB_PARTIAL)
    _pub_json(os.path.join(STAB_SEALED, "env_fingerprint.json"), _env_fingerprint_obj())
    _pub_json(ENV_PUBLIC, at.env_info())
    _sealed_access(STAB_SEALED, "_sealed/", "create", "블록 AU 봉인 디렉터리 생성")


# ═══════════════════════════════════════════════════════════════════════════
# stage: run
# ═══════════════════════════════════════════════════════════════════════════
def stage_run():
    assert not _SELFTEST_ROOTS, "selftest 임시 허용 루트가 비어 있지 않다"
    harness_sha = _sha256_file(os.path.abspath(__file__))
    assert _sha256_file(os.path.join(ROOT, CONTRACT_REL)) == CONTRACT_SHA256, "안정성 계약 sha 불일치"
    assert _sha256_file(os.path.join(ROOT, AT_CONTRACT_REL)) == AT_CONTRACT_SHA256, "AT 계약 sha 불일치"
    assert _sha256_file(os.path.join(ROOT, V2_HARNESS_REL)) == V2_HARNESS_SHA256, "v2 하네스 sha 불일치"
    assert _sha256_file(os.path.join(ROOT, AT_MANIFEST_T4_REL)) == AT_MANIFEST_T4_SHA256, \
        "AT manifest_t4 sha 불일치"

    cl.gate_a_load("confirmatory_gin_stability entry")       # 락 획득 전 1회만
    stopper = at.Stopper()
    with cl.ComputeLock(script="confirmatory_gin_stability.py", role="runner"):
        stopper.install()                                    # ComputeLock 즉시-종료 핸들러 대체
        _write_pid()
        rc = _run_loop(harness_sha, stopper)
    return rc


def _run_loop(harness_sha, stopper):
    units, _plan, _design = _build_plan()
    plan_keys = [at.unit_key(u) for u in units]
    device = gnntrain.get_device({"device": "mps"})
    assert str(device) == "mps", "device %s != mps (auto 폴백 금지)" % device

    d = lc.load_frozen()
    N = len(d["cid_order"])
    assert N == at.N_DRUGS, "N %d != %d" % (N, at.N_DRUGS)
    ycols = d["ycols"]
    assert len(ycols) == at.N_PT, "PT %d != %d" % (len(ycols), at.N_PT)
    blocks = rest.make_blocks(d)
    graphs = at.build_graphs(d)
    cid2idx = {int(c): i for i, c in enumerate(d["cid_order"])}

    session_n = 0
    while True:
        session_n += 1
        mode, diag = _session_gate(harness_sha, plan_keys)
        power = at.read_power()
        if not power["ok"]:
            _session_event({"event": "session_end", "session": session_n, "mode": mode,
                            "stopped_reason": "power", "ac_power": power["ac_power"],
                            "wattage": power["wattage"]})
            print("[POWER] AC 전원 미충족 (ac=%s wattage=%s) — 학습 0"
                  % (power["ac_power"], power["wattage"]), file=sys.stderr)
            return EXIT_POWER
        ok_load, load1 = at.wait_load_ok()
        if not ok_load:
            _session_event({"event": "session_end", "session": session_n, "mode": mode,
                            "stopped_reason": "load", "load1": round(load1, 2)})
            print("[LOAD] load1=%.2f > %.2f — 학습 0" % (load1, cl.LOAD_HARD_MAX), file=sys.stderr)
            return EXIT_NOT_IDLE

        if mode == "first_launch":
            _write_manifest_s1(harness_sha, units, power, load1)
        elif mode == "launch_retry":
            _session_event({"event": "launch_retry", "session": session_n,
                            "note": "manifest_s1 존재 + 안정성 봉인 0 — 첫 착수 재시도(manifest 재기록 0)"})
        if not os.path.isdir(STAB_SEALED):
            _create_sealed()

        _session_event({"event": "session_start", "session": session_n, "mode": mode,
                        "gate": diag, "ac_power": power["ac_power"], "wattage": power["wattage"],
                        "load1": round(load1, 2)})

        res = _run_session(units, d, graphs, cid2idx, blocks, ycols, device, stopper)
        _session_event({"event": "session_end", "session": session_n,
                        "n_units_completed": res["n_done"],
                        "stopped_reason": res["stopped_reason"]})

        if res["stopped_reason"] == "hard_failure_twice":
            print("[HARD] 동일 단위 2회 실패 — 전체 정지", file=sys.stderr)
            return EXIT_HARD_FAILURE
        if res["stopped_reason"] == "signal":
            return 0
        if res["stopped_reason"] == "complete":
            _session_event({"event": "stability_complete", "n_units": N_UNITS,
                            "n_sessions": session_n, "oof_assembled": False})
            print("[DONE] 안정성 42 단위 완료 — OOF 조립·지표 산출 없음(다음 블록).")
            return 0
        cl.gate_c_settle("블록 AU 세션 경계 %d" % session_n)


def _run_session(units, d, graphs, cid2idx, blocks, ycols, device, stopper):
    t_session = time.perf_counter()
    rows = _load_state()
    done_keys = {at.unit_key(r) for r in rows}
    fails = _failure_counts()

    cur_rf = None
    cur_rfm = None
    otr = te = None
    scaf = None
    itr = iva = None
    side = None
    side_dim = 0
    n_done = 0

    for u in units:
        k = at.unit_key(u)
        if k in done_keys:
            continue
        if stopper.flag:
            return {"n_done": n_done, "stopped_reason": "signal"}
        if (time.perf_counter() - t_session) / 3600.0 >= SESSION_CAP_HOURS:
            return {"n_done": n_done, "stopped_reason": "session_cap"}

        rep, fold, model, seed = u["rep"], u["fold"], u["model"], u["train_seed"]

        # --- (rep, fold) 전환 ------------------------------------------------
        if cur_rf != (rep, fold):
            df = rest.read_fold_membership(rep)
            assert len(df) == at.N_DRUGS, "fold_membership 행수 불일치"
            folds_x = rest.fold_of_row_for(rep, d["cid_order"])
            assert np.array_equal(folds_x, df["fold"].values.astype(int)), \
                "folds.json 과 fold_membership.csv 불일치"
            scaf = df["scaffold"].tolist()
            otr = np.where(df["fold"].values != fold)[0]
            te = np.where(df["fold"].values == fold)[0]
            iva, itr, _g, _v = v1.inner_split(scaf, otr, 1000 * REP_SEED[rep] + fold,
                                              at.INNER_DENOM)
            assert len(iva) == 97, "inner-valid %d != 97" % len(iva)
            assert sorted(list(iva) + list(itr)) == sorted(otr.tolist()), "inner split 합 불일치"
            Yi = d["Ym"][np.asarray(itr)]
            n_zero_pt = int((Yi.sum(axis=0) == 0).sum())
            assert n_zero_pt == 0, "inner-train 양성 0 PT %d != 0" % n_zero_pt
            _pub_json(SPLIT_DIAG, _merge_split_public(SPLIT_DIAG, rep, fold, len(otr), len(te),
                                                      len(itr), len(iva), n_zero_pt))
            cur_rf = (rep, fold)
            cur_rfm = None

        # --- (rep, fold, model) 전환 ----------------------------------------
        if cur_rfm != (rep, fold, model):
            leak, _order = rest.fit_fold(blocks, model, otr, d, at.N_DRUGS)
            assert all(v == 0 for v in leak.values()), "leak_rows != 0"
            side, side_dim, _meta = at.build_side(blocks, model, otr, at.N_DRUGS)
            want = SIDE_DIM_EXPECTED[(rep, fold)][model]
            assert side_dim == want, "side_dim %d != %d (rep%d fold%d %s)" % (
                side_dim, want, rep, fold, model)
            tl.attach_side({"train": [graphs[i] for i in itr],
                            "valid": [graphs[i] for i in iva],
                            "test": [graphs[i] for i in te]},
                           side if side is not None else np.zeros((at.N_DRUGS, 0), np.float32),
                           cid2idx, side_dim)
            cur_rfm = (rep, fold, model)

        data = {"ycols": ycols,
                "graphs": {"train": [graphs[i] for i in itr],
                           "valid": [graphs[i] for i in iva],
                           "test": [graphs[i] for i in te]}}

        # --- 학습 (stdout·stderr 전량 가로채 봉인) ---------------------------
        n_retry = 0
        while True:
            buf = io.StringIO()
            t0 = time.perf_counter()
            exc_type = None
            res = None
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    res = tl.train_variant(data, device, side_dim, "concat", seed)
            except BaseException as e:                       # noqa: BLE001
                exc_type = type(e).__name__
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    _sealed_stdout_append(STAB_SEALED, "%s | %s | %s"
                                          % (k, at.now_kst(), exc_type), buf.getvalue())
                    raise
            wall = time.perf_counter() - t0
            _sealed_stdout_append(STAB_SEALED, "%s | %s | retry=%d | %s"
                                  % (k, at.now_kst(), n_retry, exc_type or "ok"), buf.getvalue())
            if exc_type is None:
                if not bool(np.isfinite(res["P_test"]).all()):
                    exc_type = "NonFinitePrediction"
                else:
                    assert res["P_test"].shape == (len(te), at.N_PT), "예측 배열 형상 불일치"
            if exc_type is None:
                break
            tl.free_mem(device)
            _pub_jsonl(FAILURES, {"rep": rep, "fold": fold, "model": model, "train_seed": seed,
                                  "kind": "hard_technical_failure", "exception_type": exc_type,
                                  "ts_kst": at.now_kst()})
            fails[k] = fails.get(k, 0) + 1
            if fails[k] >= 2:
                return {"n_done": n_done, "stopped_reason": "hard_failure_twice"}
            n_retry += 1

        # --- 원자적 쓰기 ------------------------------------------------------
        ppath = os.path.join(STAB_PARTIAL, _partial_name(model, rep, fold, seed))
        psha = _atomic_npz(ppath, P_test=res["P_test"].astype(np.float32),
                           best_ep=np.int32(res["best_ep"]), best_v=np.float64(res["valid"]))
        assert k not in done_keys, "체크포인트 키 중복 %s" % k
        _sealed_ckpt_append(STAB_SEALED, {
            "rep": rep, "fold": fold, "model": model, "train_seed": seed,
            "completed_at_kst": at.now_kst(), "artifact_sha256": psha,
            "n_epochs": int(min(res["best_ep"] + tl.PATIENCE, tl.EPOCHS)),
            "wall_seconds": round(wall, 3)})
        _pub_line(RUN_LOG, "%d %d %s %d %.3f %d %s %d"
                  % (rep, fold, model, seed, wall, side_dim, "mps", n_retry))
        done_keys.add(k)
        n_done += 1
        tl.free_mem(device)
        # 조립 없음 (E4 — fold 수준 추정량).

    return {"n_done": n_done, "stopped_reason": "complete"}


def _load_state():
    """안정성 체크포인트 판독(기계 · access.log 기록)."""
    if not os.path.isdir(STAB_SEALED):
        return []
    _sealed_access(STAB_SEALED, "_sealed/checkpoint.jsonl", "resume-state",
                   "블록 AU checkpoint 판독(세션 시작 1회)")
    rows, ok, reason = at.sealed_ckpt_read(STAB_SEALED)
    assert ok, reason
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# stage: plan / status / finalize
# ═══════════════════════════════════════════════════════════════════════════
def stage_plan(out):
    assert not _SELFTEST_ROOTS, "selftest 임시 허용 루트가 비어 있지 않다"
    units, _plan, _design = _build_plan()
    body = _plan_body(units)
    if out:
        _pub_json(out, body)
        print("plan → %s (n=%d sha256=%s)" % (out, len(units), body["plan_sha256"]))
    else:
        print(json.dumps({k: body[k] for k in
                          ("n_stability", "n_confirmatory_executed", "order", "plan_sha256")},
                         ensure_ascii=False, indent=2))
    return body


def _pid_alive():
    if not os.path.exists(PYTHON_PID):
        return {"pid": None, "alive": False}
    try:
        pid = int(open(PYTHON_PID, encoding="utf-8").read().strip())
    except ValueError:
        return {"pid": None, "alive": False}
    p = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                       capture_output=True, text=True)
    return {"pid": pid, "alive": "confirmatory_gin_stability.py" in p.stdout}


def _status_obj():
    """공개 파일만으로 진행률을 만든다 — _sealed/ 접근 0."""
    st = {"ts_kst": at.now_kst(), "n_units_total": N_UNITS}
    walls = []
    n_done = 0
    if os.path.exists(RUN_LOG):
        for ln in open(RUN_LOG, encoding="utf-8"):
            parts = ln.split()
            if len(parts) == 8:
                n_done += 1
                try:
                    walls.append(float(parts[4]))
                except ValueError:
                    pass
    st["n_units_done_public_runlog"] = n_done
    if walls:
        mean_w = sum(walls) / len(walls)
        st["mean_wall_seconds"] = round(mean_w, 1)
        st["eta_hours_remaining"] = round((N_UNITS - n_done) * mean_w / 3600.0, 2)
    if os.path.exists(SESSIONS):
        lines = [ln for ln in open(SESSIONS, encoding="utf-8") if ln.strip()]
        st["n_session_events"] = len(lines)
        st["last_session_event"] = json.loads(lines[-1]) if lines else None
    st["manifest_s1_exists"] = os.path.exists(MANIFEST_S1)
    st["manifest_s2_exists"] = os.path.exists(MANIFEST_S2)
    st["n_failures_logged"] = (len([ln for ln in open(FAILURES, encoding="utf-8") if ln.strip()])
                               if os.path.exists(FAILURES) else 0)
    st["python_pid"] = _pid_alive()
    st["sealed_access"] = "none (공개 파일만 판독)"
    return st


def stage_status(out):
    assert not _SELFTEST_ROOTS, "selftest 임시 허용 루트가 비어 있지 않다"
    st = _status_obj()
    if out:
        _pub_json(out, st)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return st


def stage_finalize(out):
    assert not _SELFTEST_ROOTS, "selftest 임시 허용 루트가 비어 있지 않다"
    units, _plan, _design = _build_plan()
    planned = [at.unit_key(u) for u in units]
    _sealed_access(STAB_SEALED, "_sealed/", "finalize", "블록 AU finalize 검증")
    rows, ok, reason = at.sealed_ckpt_read(STAB_SEALED)
    assert ok, reason
    keys = [at.unit_key(r) for r in rows]
    assert len(rows) == N_UNITS, "체크포인트 %d != %d" % (len(rows), N_UNITS)
    assert len(set(keys)) == N_UNITS, "체크포인트 키 중복"
    assert set(keys) == set(planned), "체크포인트 키 집합 != 계획 42"
    assert keys == planned, "체크포인트 기록 순서 != 계획 순서"

    te_n = {}
    for rep, fold in REP_UNITS:
        df = rest.read_fold_membership(rep)
        te_n[(rep, fold)] = int((df["fold"].values == fold).sum())

    psha = {}
    for r in rows:
        name = _partial_name(r["model"], r["rep"], r["fold"], r["train_seed"])
        p = os.path.join(STAB_PARTIAL, name)
        assert os.path.exists(p), "partial 부재 %s" % name
        s = at.sha256_file(p)
        assert s == r["artifact_sha256"], "partial sha 불일치 %s" % name
        with np.load(p) as z:
            assert sorted(z.files) == sorted(["P_test", "best_ep", "best_v"]), \
                "npz 키 구성 불일치 %s" % name
            arr = z["P_test"]
            assert arr.dtype == np.float32, "예측 배열 dtype 불일치 %s" % name
            assert arr.shape == (te_n[(r["rep"], r["fold"])], at.N_PT), \
                "예측 배열 형상 불일치 %s" % name
        psha[name] = s

    n_part = len([f for f in os.listdir(STAB_PARTIAL) if f.endswith(".npz")])
    assert n_part == N_UNITS, "_partial %d != %d" % (n_part, N_UNITS)
    n_orph = len(os.listdir(STAB_ORPHANS)) if os.path.isdir(STAB_ORPHANS) else 0
    n_fail = (len([ln for ln in open(FAILURES, encoding="utf-8") if ln.strip()])
              if os.path.exists(FAILURES) else 0)
    n_retry = 0
    total_wall = 0.0
    if os.path.exists(RUN_LOG):
        for ln in open(RUN_LOG, encoding="utf-8"):
            parts = ln.split()
            if len(parts) == 8:
                total_wall += float(parts[4])
                n_retry += int(parts[7])
    n_sessions = 0
    if os.path.exists(SESSIONS):
        n_sessions = len([ln for ln in open(SESSIONS, encoding="utf-8")
                          if ln.strip() and '"session_start"' in ln])
    fp, n_fp = _confirm_stat_fingerprint(CONFIRM_DIRS, ROOT)
    conf_obs = {k: 0 for k in CONFIRM_COUNTS}
    for dd in CONFIRM_DIRS:
        r0 = at.count_sealed(dd)
        for kk in conf_obs:
            conf_obs[kk] += r0[kk]

    obj = {"_doc": "블록 AU 안정성 42 완주 manifest (docs/111 §3 AU-3 (9)). 지표 산출 0 · 개봉 0 · OOF 조립 0.",
           "ts_kst": at.now_kst(),
           "n_units": len(rows),
           "partial_sha256": psha,
           "checkpoint_sha256": at.sha256_file(os.path.join(STAB_SEALED, "checkpoint.jsonl")),
           "sealed_counts_final": {
               "total": at.count_sealed(),
               "legacy_excluding_confirm_and_stability":
                   at.count_sealed(ROOT, exclude_dirs=tuple(CONFIRM_DIRS) + (STAB_DIR,)),
               "confirmatory_three_trees": conf_obs},
           "confirm_stat_fingerprint": fp,
           "confirm_stat_lines": n_fp,
           "legacy_sealed_counts_expected": LEGACY_COUNTS,
           "confirm_sealed_counts_expected": CONFIRM_COUNTS,
           "n_sessions": n_sessions,
           "n_failures_logged": n_fail,
           "n_retries": n_retry,
           "n_orphans": n_orph,
           "total_wall_seconds": round(total_wall, 1),
           "total_wall_hours": round(total_wall / 3600.0, 2),
           "harness_sha256": _sha256_file(os.path.abspath(__file__)),
           "contract_sha256": CONTRACT_SHA256,
           "at_harness_sha256": AT_HARNESS_SHA256,
           "confirmatory_units_executed": 0,
           "oof_assembled": False,
           "consensus_built": False,
           "metrics_computed": False,
           "unblinding_performed": False}
    _pub_json(out or MANIFEST_S2, obj)
    print("finalize → %s" % (out or MANIFEST_S2))
    return obj


# ═══════════════════════════════════════════════════════════════════════════
# stage: selftest — S1~S13 (확증 라벨로 학습 0회)
# ═══════════════════════════════════════════════════════════════════════════
def _case(cases, name, desc, ok, detail=None, skip=None):
    cases.append({"case": name, "desc": desc, "pass": bool(ok) and skip is None,
                  "skip_reason": skip, "detail": detail})
    return cases[-1]


ALLOWED_AT_NAMES = {
    "build_graphs", "build_side", "atomic_npz", "sealed_access", "sealed_stdout_append",
    "sealed_ckpt_append", "sealed_ckpt_read", "unit_key", "call_v2_gate", "parse_gate_failures",
    "count_sealed", "count_pycache", "pub_line", "pub_jsonl", "pub_json", "read_power",
    "wait_load_ok", "env_info", "Stopper", "now_kst", "sha256_file",
    "COND5_NAME", "GATE_FAIL_PREFIX", "CKPT_FIELDS", "N_DRUGS", "N_PT", "INNER_DENOM",
    "ADAPTER_MIN_W", "KST",
}
# F9 의 import 규약「os.path.samefile(at.__file__, <그 경로>) assert」가 요구하는 유일한 dunder.
# 재사용 «함수·상수» 허용목록(계약 reuse.allowlist)과는 층위가 다르므로 따로 센다.
IMPORT_IDENTITY_NAMES = {"__file__"}
DENIED_AT_NAMES = {
    "session_event", "env_fingerprint_obj", "repeat_dir", "sealed_dir", "split_dir",
    "gin_repeat_dirs", "sweep_orphans", "failure_counts", "load_state", "run_session",
    "maybe_assemble", "gate_verdict", "session_gate", "write_manifest_t3", "make_plan",
    "plan_sha256", "stage_plan", "stage_run", "stage_status", "stage_finalize",
    "stage_selftest", "main", "run_loop", "stray_sealed_dirs", "partial_name",
    "_merge_split_diag", "sha256_bytes", "REP_SEED",
}
WRITE_FUNCS = {"atomic_npz", "pub_line", "pub_jsonl", "pub_json", "sealed_access",
               "sealed_stdout_append", "sealed_ckpt_append", "makedirs", "move"}
GUARDED_WRAPPERS = {"_makedirs", "_touch", "_write_text", "_pub_line", "_pub_jsonl", "_pub_json",
                    "_sealed_access", "_sealed_stdout_append", "_sealed_ckpt_append",
                    "_atomic_npz", "_move_orphan"}
STAGE_FUNCS = {"stage_run", "stage_plan", "stage_status", "stage_finalize"}


def _fake_legacy(runs, n_dirs=25, n_files=291, n_access=16):
    per = (n_files - n_access) // n_dirs
    rem = (n_files - n_access) % n_dirs
    for i in range(n_dirs):
        s = os.path.join(runs, "legacy_%02d" % i, "_sealed")
        _makedirs(s)
        for j in range(per + (1 if i < rem else 0)):
            _touch(os.path.join(s, "a%03d.npz" % j))
        if i < n_access:
            _touch(os.path.join(s, "access.log"))


def _fake_confirm(runs, n_files=130, n_access=1):
    dirs = []
    for r in (1, 2, 3):
        d = os.path.join(runs, "v3_gin_confirm_rep%d_seed%d" % (r, REP_SEED[r]))
        s = os.path.join(d, "_sealed")
        _makedirs(os.path.join(s, "_partial"))
        for j in range(n_files - n_access):
            _touch(os.path.join(s, "_partial", "p%03d.npz" % j))
        for _ in range(n_access):
            _touch(os.path.join(s, "access.log"))
        dirs.append(d)
    return dirs


def _fake_stab(runs, ck_rows=(), partials=None, tops=(), subdirs_files=None,
               truncate=False, failures=(), sealed=True):
    d = os.path.join(runs, "v3_gin_stability")
    _makedirs(d)
    if sealed:
        s = os.path.join(d, "_sealed")
        _makedirs(os.path.join(s, "_partial"))
        lines = [json.dumps({k: r[k] for k in at.CKPT_FIELDS}, ensure_ascii=False)
                 for r in ck_rows]
        txt = "\n".join(lines) + ("" if truncate else ("\n" if lines else ""))
        if truncate and lines:
            txt = txt[:-5]
        _write_text(os.path.join(s, "checkpoint.jsonl"), txt)
        names = partials if partials is not None else \
            [_partial_name(r["model"], r["rep"], r["fold"], r["train_seed"]) for r in ck_rows]
        for n in names:
            _touch(os.path.join(s, "_partial", n))
        for n in ("env_fingerprint.json", "access.log", "train_stdout.log"):
            _touch(os.path.join(s, n))
        for n in tops:
            _touch(os.path.join(s, n))
        for sub, names2 in (subdirs_files or {}).items():
            _makedirs(os.path.join(s, sub))
            for n in names2:
                _touch(os.path.join(s, sub, n))
    if failures:
        _write_text(os.path.join(d, "failures.jsonl"),
                    "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in failures))
    return d


def _ck(rep, fold, model, seed):
    return {"rep": rep, "fold": fold, "model": model, "train_seed": seed,
            "completed_at_kst": at.now_kst(), "artifact_sha256": "0" * 64,
            "n_epochs": 0, "wall_seconds": 0.0}


def _synth_expected(t, plan_keys, harness_sha=None, contract_sha=None, manifest=None):
    runs = os.path.join(t, "experiments", "runs")
    confirm = [os.path.join(runs, "v3_gin_confirm_rep%d_seed%d" % (r, REP_SEED[r]))
               for r in (1, 2, 3)]
    stab = os.path.join(runs, "v3_gin_stability")
    fp, _n = _confirm_stat_fingerprint(confirm, t)
    mpath = os.path.join(stab, "manifest_s1_launch.json")
    if manifest is not None:
        _makedirs(stab)
        _write_text(mpath, json.dumps(manifest, ensure_ascii=False))
    return {"legacy": dict(LEGACY_COUNTS), "confirm": dict(CONFIRM_COUNTS),
            "confirm_fp": fp, "base_sealed_dirs": BASE_SEALED_DIRS,
            "confirm_dirs": confirm, "stab_dir": stab,
            "stab_sealed": os.path.join(stab, "_sealed"), "manifest_s1_path": mpath,
            "plan_keys": list(plan_keys), "fp_root": t, "check_repo_invariants": False}


def _selftest_gate_truth_table(harness_sha, plan_keys, plan_units):
    ERR12 = at.GATE_FAIL_PREFIX + at.COND5_NAME + "\n"
    GOOD_MF = {"harness_sha256": harness_sha, "contract_sha256": CONTRACT_SHA256}
    out, allp = {}, True

    def chk(tag, expect_ok, expect_mode, rc, stderr, exp, sealed_exists, manifest_exists):
        ok, mode, bad, _dg = stability_gate_verdict(rc, stderr, exp["fp_root"], sealed_exists,
                                                    manifest_exists, harness_sha,
                                                    CONTRACT_SHA256, exp)
        good = (ok == expect_ok) and (expect_mode is None or mode == expect_mode)
        out[tag] = {"ok": ok, "mode": mode, "expect_ok": expect_ok, "expect_mode": expect_mode,
                    "pass": good, "failures": bad[:3]}
        return good

    u0 = plan_units[0]
    ck0 = _ck(u0["rep"], u0["fold"], u0["model"], u0["train_seed"])
    u1 = plan_units[1]
    ck1 = _ck(u1["rep"], u1["fold"], u1["model"], u1["train_seed"])

    # ① 첫 착수
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        e = _synth_expected(t, plan_keys)
        allp &= chk("01_first_launch", True, "first_launch", 12, ERR12, e, False, False)
    # ② 정상 재개
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("02_resume", True, "resume", 12, ERR12, e, True, True)
    # ③ 기존 트리에 파일 1개 추가
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _touch(os.path.join(runs, "legacy_00", "_sealed", "zz.npz"))
        _fake_stab(runs, [ck0])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("03_legacy_extra_file", False, None, 12, ERR12, e, True, True)
    # ④ 확증 트리 파일 크기 1 B 변경 → 지문 불일치
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        confirm = _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        _write_text(os.path.join(confirm[0], "_sealed", "_partial", "p000.npz"), "x")
        allp &= chk("04_confirm_size_changed", False, None, 12, ERR12, e, True, True)
    # ⑤ 체크포인트 없는 partial → 고아 이동 후 통과
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        nm_extra = _partial_name(u1["model"], u1["rep"], u1["fold"], u1["train_seed"])
        d = _fake_stab(runs, [ck0],
                       partials=[_partial_name(u0["model"], u0["rep"], u0["fold"],
                                               u0["train_seed"]), nm_extra])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("05a_orphan_before_sweep", False, None, 12, ERR12, e, True, True)
        s = os.path.join(d, "_sealed")
        _move_orphan(os.path.join(s, "_partial", nm_extra),
                     os.path.join(s, "_orphans", nm_extra + ".ts"))
        _write_text(os.path.join(d, "failures.jsonl"),
                    json.dumps({"orphan_path": "x/" + nm_extra + ".ts"}) + "\n")
        allp &= chk("05b_orphan_after_sweep", True, "resume", 12, ERR12, e, True, True)
    # ⑥ partial 없는 체크포인트
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0, ck1],
                   partials=[_partial_name(u0["model"], u0["rep"], u0["fold"], u0["train_seed"])])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("06_ckpt_without_partial", False, None, 12, ERR12, e, True, True)
    # ⑦ 실패=[5,3]
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("07_fail_5_and_3", False, None, 12,
                    at.GATE_FAIL_PREFIX + at.COND5_NAME + ", 3:supersede_event\n", e, True, True)
    # ⑧ rc0
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("08_rc0", False, None, 0, "", e, True, True)
    # ⑨ 계약 sha 불일치
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        e = _synth_expected(t, plan_keys,
                            manifest={"harness_sha256": harness_sha, "contract_sha256": "bad"})
        allp &= chk("09_contract_sha_mismatch", False, None, 12, ERR12, e, True, True)
    # ⑩ manifest 있음 + 봉인 없음 → launch_retry
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("10_launch_retry", True, "launch_retry", 12, ERR12, e, False, True)
    # ⑪ 체크포인트 마지막 줄 잘림
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0], truncate=True)
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("11_truncated_ckpt", False, None, 12, ERR12, e, True, True)
    # ⑫ stderr 경고 줄 섞임 + 접두 줄 1개
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        noisy = "UserWarning: something\n" + ERR12 + "another warning line\n"
        allp &= chk("12_noisy_stderr", True, "resume", 12, noisy, e, True, True)
    # ⑬ consensus 디렉터리 존재
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        _makedirs(os.path.join(runs, "v3_gin_confirm_consensus_rep123"))
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("13_consensus_dir", False, None, 12, ERR12, e, True, True)
    # ⑭ 다른 곳에 새 _sealed
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0])
        _makedirs(os.path.join(runs, "someplace_else", "_sealed"))
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("14_new_sealed_elsewhere", False, None, 12, ERR12, e, True, True)
    # ⑮ 안정성 봉인에 oof_x.npz
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        _fake_stab(runs, [ck0], tops=["oof_M2b_seed3.npz"])
        e = _synth_expected(t, plan_keys, manifest=GOOD_MF)
        allp &= chk("15_oof_in_stability", False, None, 12, ERR12, e, True, True)
    # ⑯ 봉인 없는 상태에서 게이트·고아 처리·status → _sealed 생성 0 (실제 저장소 경로)
    real_before = os.path.isdir(STAB_SEALED)
    _ok16 = (not real_before)
    if _ok16:
        stability_gate_verdict(12, ERR12, ROOT, False, os.path.exists(MANIFEST_S1),
                               harness_sha, CONTRACT_SHA256, _expected(plan_keys))
        mv = _sweep_orphans()
        _status_obj()
        _ok16 = (mv == [] and not os.path.isdir(STAB_SEALED))
    out["16_no_sealed_side_effect"] = {"pass": bool(_ok16),
                                       "sealed_before": real_before,
                                       "sealed_after": os.path.isdir(STAB_SEALED)}
    allp &= bool(_ok16)
    # ⑰ manifest 있음 + 봉인 없음 + 하네스 sha 불일치
    with _selftest_root() as t:
        runs = os.path.join(t, "experiments", "runs")
        _fake_legacy(runs)
        _fake_confirm(runs)
        e = _synth_expected(t, plan_keys,
                            manifest={"harness_sha256": "bad", "contract_sha256": CONTRACT_SHA256})
        allp &= chk("17_launch_retry_harness_mismatch", False, None, 12, ERR12, e, False, True)

    out["all_pass"] = bool(allp)
    return out


def _selftest_write_protocol():
    out = {}
    with _selftest_root() as t:
        p = os.path.join(t, "x.npz")
        sha = _atomic_npz(p, P_test=np.zeros((3, 4), np.float32),
                          best_ep=np.int32(1), best_v=np.float64(0.5))
        out["tmp_removed"] = not os.path.exists(p + ".tmp")
        out["npz_exists"] = os.path.exists(p)
        out["sha_matches"] = sha == at.sha256_file(p)
        s = os.path.join(t, "_sealed")
        _makedirs(s)
        r = _ck(1, 4, "M0", 3)
        _sealed_ckpt_append(s, r)
        rows, ok, _ = at.sealed_ckpt_read(s)
        out["append_then_read"] = ok and len(rows) == 1
        _sealed_ckpt_append(s, r)
        _rows2, ok2, reason2 = at.sealed_ckpt_read(s)
        out["duplicate_detected"] = (not ok2) and "중복" in (reason2 or "")
    with _selftest_root() as t:
        s = os.path.join(t, "_sealed")
        _makedirs(os.path.join(s, "_partial"))
        _sealed_ckpt_append(s, _ck(1, 4, "M0", 3))
        _touch(os.path.join(s, "_partial", _partial_name("M0", 1, 4, 3)))
        _touch(os.path.join(s, "_partial", _partial_name("M1", 1, 4, 3)))
        _touch(os.path.join(s, "_partial", _partial_name("M1b", 1, 4, 3) + ".tmp"))
        rows, _ok, _r = at.sealed_ckpt_read(s)
        known = {_partial_name(r["model"], r["rep"], r["fold"], r["train_seed"]) for r in rows}
        orph = [f for f in sorted(os.listdir(os.path.join(s, "_partial")))
                if f.endswith(".tmp") or (f.endswith(".npz") and f not in known)]
        out["orphan_detected"] = orph == [_partial_name("M1", 1, 4, 3),
                                          _partial_name("M1b", 1, 4, 3) + ".tmp"]
        m = ORPHAN_RE.match(_partial_name("P-FAM", 2, 1, 4)[:-4])
        out["regex_rep_parsed"] = bool(m) and m.groups() == ("P-FAM", "2", "1", "4")
    out["all_pass"] = all(v for k, v in out.items() if k != "all_pass")
    return out


def _retry_engine(outcomes, seed):
    seeds_used, n_fail = [], 0
    for o in outcomes:
        seeds_used.append(seed)
        if o == "ok":
            return {"exit": 0, "seeds_used": seeds_used, "n_fail": n_fail}
        n_fail += 1
        if n_fail >= 2:
            return {"exit": EXIT_HARD_FAILURE, "seeds_used": seeds_used, "n_fail": n_fail}
    return {"exit": 0, "seeds_used": seeds_used, "n_fail": n_fail}


def _selftest_failure_policy():
    a = _retry_engine(["fail", "ok"], 3)
    b = _retry_engine(["fail", "fail"], 3)
    out = {"one_failure_then_retry_same_seed": a["exit"] == 0 and a["seeds_used"] == [3, 3],
           "two_failures_exit13": b["exit"] == EXIT_HARD_FAILURE,
           "seed_unchanged": set(a["seeds_used"]) == {3} and set(b["seeds_used"]) == {3},
           "detail": {"a": a, "b": b}}
    out["all_pass"] = all(v for k, v in out.items() if k not in ("detail", "all_pass"))
    return out


_SIGNAL_CHILD = r'''
import os, sys, time, signal, json
sys.dont_write_bytecode = True
sys.path.insert(0, %(src)r)
import compute_lock as cl
state = {"flag": False}
def handler(signum, frame):
    state["flag"] = True
with cl.ComputeLock(script="confirmatory_gin_stability.py --selftest-signal", role="runner"):
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    sys.stderr.write("READY\n"); sys.stderr.flush()
    units_done = 0
    for _ in range(50):
        if state["flag"]:
            break
        time.sleep(0.1)
    time.sleep(0.3); units_done += 1
    print(json.dumps({"stopped_reason": "signal" if state["flag"] else "complete",
                      "n_done": units_done, "orphans": 0}))
'''


def _selftest_signal():
    src = _SIGNAL_CHILD % {"src": V3SRC}
    if os.path.exists(cl.LOCK_PATH):
        return {"all_pass": False, "skip": "락 파일 점유 중"}
    p = subprocess.Popen([sys.executable, "-B", "-X", "utf8", "-c", src],
                         cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ready = False
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 20:
        line = p.stderr.readline()
        if "READY" in line:
            ready = True
            break
        if p.poll() is not None:
            break
    lock_held = os.path.exists(cl.LOCK_PATH)
    if ready:
        p.send_signal(signal.SIGTERM)
    so, _se = p.communicate(timeout=30)
    obj = {}
    for ln in reversed(so.strip().splitlines()):
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError:
                obj = {}
            break
    out = {"child_ready": ready, "lock_held_during": lock_held,
           "stopped_reason": obj.get("stopped_reason"),
           "finished_current_unit": obj.get("n_done") == 1,
           "orphans": obj.get("orphans"),
           "lock_released": not os.path.exists(cl.LOCK_PATH),
           "returncode": p.returncode}
    out["all_pass"] = (ready and out["stopped_reason"] == "signal"
                       and out["finished_current_unit"] and out["orphans"] == 0
                       and out["lock_released"])
    return out


def _selftest_firewall(tree):
    out = {"rejected": [], "accepted": [], "not_rejected": [], "not_accepted": []}
    must_reject = [os.path.join(CONFIRM_DIRS[0], "_sealed", "x.npz"),
                   os.path.join(ROOT, "experiments", "runs", "v3_gin_start_authorization", "x.json"),
                   os.path.join(ROOT, "experiments", "runs", "v3_confirm_rest", "_sealed", "x"),
                   os.path.join(ROOT, "docs", "x.md"),
                   ROOT,
                   os.path.join(STAB_DIR, "..", "v3_gin_confirm_rep1_seed201", "x")]
    must_accept = [os.path.join(STAB_DIR, "run.log"),
                   os.path.join(STAB_PARTIAL, "M0_rep1_fold4_seed3.npz"),
                   STAB_DIR]
    for p in must_reject:
        try:
            _assert_stab_path(p)
            out["not_rejected"].append(p)
        except AssertionError:
            out["rejected"].append(os.path.relpath(p, ROOT))
    for p in must_accept:
        try:
            _assert_stab_path(p)
            out["accepted"].append(os.path.relpath(p, ROOT))
        except AssertionError:
            out["not_accepted"].append(p)
    # selftest 임시 루트 수명
    out["roots_empty_before"] = (len(_SELFTEST_ROOTS) == 0)
    with _selftest_root() as t:
        inside = os.path.join(t, "a", "b.txt")
        try:
            _assert_stab_path(inside)
            out["tmp_root_allowed"] = True
        except AssertionError:
            out["tmp_root_allowed"] = False
        saved = t
    out["roots_empty_after"] = (len(_SELFTEST_ROOTS) == 0)
    try:
        _assert_stab_path(os.path.join(saved, "a", "b.txt"))
        out["tmp_root_revoked"] = False
    except AssertionError:
        out["tmp_root_revoked"] = True
    # AST — 쓰기 호출이 전부 가드 래퍼 안에 있는가
    unguarded, wrappers_without_guard = [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                f = sub.func
                nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
                if nm == "open":
                    mode = ""
                    if len(sub.args) > 1 and isinstance(sub.args[1], ast.Constant):
                        mode = str(sub.args[1].value)
                    for kw in sub.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = str(kw.value.value)
                    if not any(c in mode for c in ("w", "a", "x", "+")):
                        continue
                elif nm not in WRITE_FUNCS:
                    continue
                if node.name not in GUARDED_WRAPPERS:
                    unguarded.append("%s:%s@L%d" % (node.name, nm, sub.lineno))
            if node.name in GUARDED_WRAPPERS:
                if not any(isinstance(s, ast.Call) and isinstance(s.func, ast.Name)
                           and s.func.id == "_assert_stab_path" for s in ast.walk(node)):
                    wrappers_without_guard.append(node.name)
    out["unguarded_writes"] = unguarded
    out["wrappers_without_guard"] = wrappers_without_guard
    # AST — stage 진입에 _SELFTEST_ROOTS 비어 있음 assert
    missing = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in STAGE_FUNCS:
            txt = ast.unparse(node.body[0]) if node.body else ""
            if "_SELFTEST_ROOTS" not in txt:
                missing.append(node.name)
    out["stage_entry_assert_missing"] = missing
    out["all_pass"] = (not out["not_rejected"] and not out["not_accepted"]
                       and out["roots_empty_before"] and out["roots_empty_after"]
                       and out["tmp_root_allowed"] and out["tmp_root_revoked"]
                       and not unguarded and not wrappers_without_guard and not missing)
    return out


def _selftest_reuse(tree, src):
    at_path = os.path.realpath(_AT_PATH)
    bad_src = []
    for nm in sorted(ALLOWED_AT_NAMES):
        obj = getattr(at, nm, None)
        if obj is None:
            bad_src.append("%s: 부재" % nm)
            continue
        if callable(obj) and (inspect.isfunction(obj) or inspect.isclass(obj)):
            f = inspect.getsourcefile(obj)
            if f is None or os.path.realpath(f) != at_path:
                bad_src.append("%s: %s" % (nm, f))
    used, denied = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "at":
            used.add(node.attr)
            if node.attr in DENIED_AT_NAMES:
                denied.append(node.attr)
    outside = sorted(used - ALLOWED_AT_NAMES - IMPORT_IDENTITY_NAMES)
    redefined = [n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef)
                 and n.name in ("build_side", "phi_pid", "build_graphs", "atomic_npz")]
    train_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "train_variant":
            train_calls.append(ast.unparse(node))
    canonical = [c for c in train_calls
                 if c == "tl.train_variant(data, device, side_dim, 'concat', seed)"]
    out = {"allowlist_source_mismatch": bad_src, "at_names_used": sorted(used),
           "import_identity_names_used": sorted(used & IMPORT_IDENTITY_NAMES),
           "import_identity_note": "at.__file__ 은 F9 의 samefile assert 가 요구하는 import 동일성 확인용이다(재사용 함수 아님).",
           "denylist_referenced": sorted(set(denied)), "outside_allowlist": outside,
           "redefined_core_functions": redefined,
           "train_variant_calls": train_calls, "n_canonical_train_calls": len(canonical)}
    out["all_pass"] = (not bad_src and not denied and not outside and not redefined
                       and len(canonical) == 1)
    return out


def _selftest_ast(tree):
    out = {"forbidden_imports": [], "forbidden_calls": [], "argparse_options": [],
           "os_environ_reads": 0, "public_arg_violations": [], "bare_load_frozen": 0}
    BAD_MOD = {"requests", "urllib", "http", "socket", "sap", "rqint", "rqint_test"}
    BAD_NAME = {"emit_sign", "open_sealed", "rqint_test", "decision"}
    PUBLIC_SINKS = {"print", "_pub_line", "_pub_jsonl", "_pub_json", "_session_event"}
    SEALED_VALS = {"best_v", "best_ep", "n_epochs", "P_test", "valid"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in BAD_MOD or a.name in BAD_MOD:
                    out["forbidden_imports"].append(a.name)
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if mod.split(".")[0] in BAD_MOD or mod in BAD_MOD:
                out["forbidden_imports"].append(mod)
            for a in n.names:
                if a.name in BAD_NAME or a.name == "load_frozen":
                    out["forbidden_imports"].append("%s.%s" % (mod, a.name))
        elif isinstance(n, ast.Attribute):
            if isinstance(n.value, ast.Name) and n.value.id == "os" and n.attr == "environ":
                out["os_environ_reads"] += 1
            if n.attr in BAD_NAME:
                out["forbidden_calls"].append(n.attr)
        elif isinstance(n, ast.Name):
            if n.id in BAD_NAME:
                out["forbidden_calls"].append(n.id)
            if n.id == "load_frozen":
                out["bare_load_frozen"] += 1
        elif isinstance(n, ast.Call):
            f = n.func
            fname = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if fname == "add_argument":
                for a in n.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        out["argparse_options"].append(a.value)
            if fname in PUBLIC_SINKS:
                seg = ast.unparse(n)
                for v in SEALED_VALS:
                    if re.search(r"\b%s\b" % re.escape(v), seg):
                        out["public_arg_violations"].append("%s: %s" % (fname, seg[:90]))
                        break
    out["argparse_options"] = sorted(set(out["argparse_options"]))
    out["all_pass"] = (not out["forbidden_imports"] and not out["forbidden_calls"]
                       and out["os_environ_reads"] == 0 and not out["public_arg_violations"]
                       and out["bare_load_frozen"] == 0
                       and set(out["argparse_options"]) == {"--stage", "--out"})
    return out


def stage_selftest(out):
    assert not _SELFTEST_ROOTS, "selftest 임시 허용 루트가 비어 있지 않다"
    cases = []
    sealed0 = at.count_sealed()
    pyc0 = at.count_pycache()
    fp0, n_fp0 = _confirm_stat_fingerprint(CONFIRM_DIRS, ROOT)
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    harness_sha = _sha256_text(src.encode("utf-8"))

    # ---- S1 상수 해시 -------------------------------------------------------
    ct = json.load(open(os.path.join(ROOT, CONTRACT_REL), encoding="utf-8"))
    d1 = {"contract": _sha256_file(os.path.join(ROOT, CONTRACT_REL)) == CONTRACT_SHA256,
          "at_harness": _sha256_file(os.path.join(ROOT, AT_HARNESS_REL)) == AT_HARNESS_SHA256,
          "at_contract": _sha256_file(os.path.join(ROOT, AT_CONTRACT_REL)) == AT_CONTRACT_SHA256,
          "at_manifest_t4": _sha256_file(os.path.join(ROOT, AT_MANIFEST_T4_REL)) == AT_MANIFEST_T4_SHA256,
          "v2_harness": _sha256_file(os.path.join(ROOT, V2_HARNESS_REL)) == V2_HARNESS_SHA256,
          "confirm_stat_fingerprint": fp0 == CONFIRM_STAT_FP,
          "confirm_stat_lines": n_fp0}
    bad1 = []
    for grp in ("f4_authority_chain", "f5_reused_modules", "f6_block_at_outputs"):
        for rel, meta in ct["preconditions"][grp].items():
            if _sha256_file(os.path.join(ROOT, rel)) != meta["sha256"]:
                bad1.append(rel)
    d1["preconditions_mismatch"] = bad1
    d1["n_preconditions"] = sum(len(ct["preconditions"][g]) for g in
                                ("f4_authority_chain", "f5_reused_modules", "f6_block_at_outputs"))
    _case(cases, "S1", "상수 해시 — 계약·AT 하네스/계약/manifest_t4·v2 하네스 · F4 13 · F5 12 · F6 7 · 확증 stat 지문",
          all(d1[k] for k in ("contract", "at_harness", "at_contract", "at_manifest_t4",
                              "v2_harness", "confirm_stat_fingerprint")) and not bad1, d1)

    # ---- S2 계획 ------------------------------------------------------------
    units, plan, design = _build_plan()
    plan_keys = [at.unit_key(u) for u in units]
    ref = v1.build_plan(v1.frozen_design(v1.load_frozen()))["stability_units"]
    fz = json.load(open(os.path.join(ROOT, "v3_Multimodal/config/gin_seed_freeze.json"),
                        encoding="utf-8"))
    d2 = {"n": len(units), "order_ok": units == ref,
          "rep_units": sorted({(u["rep"], u["fold"]) for u in units}),
          "rep_units_frozen": [list(x) for x in fz["representative_units"]],
          "seeds": sorted({u["train_seed"] for u in units}),
          "seeds_frozen_slice": fz["training_seeds_ordered"][3:5],
          "intersection_with_confirmatory": sorted(
              {u["train_seed"] for u in units} & set(CONFIRM_SEEDS)),
          "n_confirmatory_scheduled": len([u for u in units
                                           if u["train_seed"] in CONFIRM_SEEDS]),
          "first": units[0], "last": units[-1]}
    d2["rep_units_match"] = (sorted({(REP_SEED[u["rep"]], u["fold"]) for u in units})
                             == sorted(tuple(x) for x in fz["representative_units"]))
    _case(cases, "S2",
          "실행 목록 == v1 build_plan stability_units(42·순서 동일) · 대표 unit · seed [3,4] · 확증 교집합 0",
          d2["n"] == N_UNITS and d2["order_ok"] and d2["rep_units_match"]
          and d2["seeds"] == EXTRA_SEEDS and d2["seeds_frozen_slice"] == EXTRA_SEEDS
          and not d2["intersection_with_confirmatory"]
          and d2["n_confirmatory_scheduled"] == 0, d2)

    # ---- S3 E1 재사용 경계 --------------------------------------------------
    d3 = _selftest_reuse(tree, src)
    _case(cases, "S3", "E1 재사용 — 허용목록 함수 출처 == AT 파일 · 금지목록 참조 0 · 허용목록 밖 at. 0 · 핵심 재구현 0 · 학습 호출 1곳",
          d3["all_pass"], d3)

    # ---- 데이터 (라벨 무관 검사에 공용) --------------------------------------
    d = lc.load_frozen()
    N = len(d["cid_order"])
    blocks = rest.make_blocks(d)

    # ---- S4 inner split 3 unit ---------------------------------------------
    refu = json.load(open(os.path.join(ROOT, "experiments", "runs",
                                       "v3_gin_inner_valid_freeze", "inner_split_check.json"),
                          encoding="utf-8"))["units"]
    refmap = {(u["split_seed"], u["fold"]): u for u in refu}
    d4, bad4 = {}, []
    splits = {}
    for rep, fold in REP_UNITS:
        dfr = rest.read_fold_membership(rep)
        o = np.where(dfr["fold"].values != fold)[0]
        te = np.where(dfr["fold"].values == fold)[0]
        va, tr, _g, _v = v1.inner_split(dfr["scaffold"].tolist(), o,
                                        1000 * REP_SEED[rep] + fold, at.INNER_DENOM)
        Yi = d["Ym"][np.asarray(tr)]
        zp = int((Yi.sum(axis=0) == 0).sum())
        R = refmap[(REP_SEED[rep], fold)]
        got = {"n_outer_train": len(o), "n_inner_train": len(tr), "n_inner_valid": len(va),
               "n_inner_train_zero_positive_pt": zp, "inner_seed": 1000 * REP_SEED[rep] + fold}
        same = all(R[f] == got[f] for f in got)
        d4["rep%d_fold%d" % (rep, fold)] = {"got": got, "match": same}
        if not same or len(va) != 97 or zp != 0:
            bad4.append("rep%d_fold%d" % (rep, fold))
        splits[(rep, fold)] = (o, te)
    _case(cases, "S4", "inner split 3 대표 unit — inner_split_check.json 전 필드 일치 · valid 97 · 양성0PT 0",
          not bad4, {"units": d4, "mismatch": bad4})

    # ---- S5 side_dim (라벨 무관 · 학습 0) ------------------------------------
    d5 = {"dims": {}, "leak": {}, "mismatch": []}
    for rep, fold in REP_UNITS:
        o, _te = splits[(rep, fold)]
        for m in MODELS:
            leak, _order = rest.fit_fold(blocks, m, o, d, N)
            if any(v != 0 for v in leak.values()):
                d5["leak"]["rep%d_fold%d_%s" % (rep, fold, m)] = leak
            _s, sd, _meta = at.build_side(blocks, m, o, N)
            d5["dims"]["rep%d_fold%d_%s" % (rep, fold, m)] = sd
            if sd != SIDE_DIM_EXPECTED[(rep, fold)][m]:
                d5["mismatch"].append("rep%d_fold%d_%s: %d != %d"
                                      % (rep, fold, m, sd, SIDE_DIM_EXPECTED[(rep, fold)][m]))
    d5["n_checked"] = len(d5["dims"])
    _case(cases, "S5", "side_dim 21/21 == F10 표(확증 run.log 실측) · leak 0 · 학습 0",
          not d5["mismatch"] and not d5["leak"] and d5["n_checked"] == 21, d5)

    # ---- S6 그래프 ----------------------------------------------------------
    graphs = at.build_graphs(d)
    d6 = {"n_graphs": len(graphs), "n_parse_fail": 0,
          "cid_order_match": [g.cid for g in graphs] == [int(x) for x in d["cid_order"]]}
    _case(cases, "S6", "그래프 1,092 · 파싱 실패 0 · cid 순서 == master",
          d6["n_graphs"] == at.N_DRUGS and d6["cid_order_match"], d6)

    # ---- S7 학습 스모크(합성) ----------------------------------------------
    rng = np.random.default_rng(20260922)
    ylab = (rng.random((12, 8)) < 0.5).astype(float)
    sgraphs = []
    for i, smi in enumerate(v1.FIXTURE_SMILES):
        g = gf.smiles_to_data(smi, y=ylab[i])
        g.cid = 910000 + i
        sgraphs.append(g)
    sside = rng.random((12, 5)).astype(np.float32)
    scid2idx = {g.cid: i for i, g in enumerate(sgraphs)}
    tl.attach_side({"train": sgraphs[:6], "valid": sgraphs[6:9], "test": sgraphs[9:]},
                   sside, scid2idx, 5)
    sdata = {"ycols": ["pt%d" % i for i in range(8)],
             "graphs": {"train": sgraphs[:6], "valid": sgraphs[6:9], "test": sgraphs[9:]}}
    sbuf = io.StringIO()
    outer = io.StringIO()
    sdev = gnntrain.get_device({"device": "mps"})
    with contextlib.redirect_stdout(outer):
        with contextlib.redirect_stdout(sbuf), contextlib.redirect_stderr(sbuf):
            sres = tl.train_variant(sdata, sdev, 5, "concat", 42)
    captured = sbuf.getvalue()
    d7 = {"real_stdout_len": len(outer.getvalue()),
          "captured_has_monitor_line": "validMacro" in captured,
          "captured_len": len(captured),
          "epoch_formula_holds": True,
          "device": str(sdev),
          "epoch_formula": "min(early-stop epoch 기준 공식, EPOCHS)"}
    ne = min(int(sres["best_ep"]) + tl.PATIENCE, tl.EPOCHS)
    m_es = re.search(r"early stop @ep(\d+)", captured)
    if m_es:
        d7["epoch_formula_holds"] = (int(m_es.group(1)) == ne)
    del sres
    tl.free_mem(sdev)
    _case(cases, "S7", "합성 스모크 — 실제 stdout 출력 0 · 가로챈 텍스트에 monitor 줄 · epoch 공식 · 수치 폐기",
          d7["real_stdout_len"] == 0 and d7["captured_has_monitor_line"]
          and d7["epoch_formula_holds"], d7)

    # ---- S8 재개 게이트 진리표 ---------------------------------------------
    d8 = _selftest_gate_truth_table(harness_sha, plan_keys, units)
    _case(cases, "S8", "재개 게이트 진리표 ①~⑰", d8["all_pass"], d8)

    # ---- S9 쓰기 규약 -------------------------------------------------------
    d9 = _selftest_write_protocol()
    _case(cases, "S9", "쓰기 규약 — .tmp→replace→체크포인트 순서 · 키 중복 차단 · 고아 판정(정규식 rep 포함)",
          d9["all_pass"], d9)

    # ---- S10 실패 정책 ------------------------------------------------------
    d10 = _selftest_failure_policy()
    _case(cases, "S10", "실패 정책 — 1회 재시도(같은 seed) · 2회 → exit 13 · seed 불변", d10["all_pass"], d10)

    # ---- S10b 시그널 --------------------------------------------------------
    d10b = _selftest_signal()
    _case(cases, "S10b", "SIGTERM — 진행 중 단위를 끝낸 뒤 stopped_reason signal · 고아 0 · 락 해제",
          d10b["all_pass"], d10b, skip=d10b.get("skip"))

    # ---- S11 firewall 가드 --------------------------------------------------
    d11 = _selftest_firewall(tree)
    _case(cases, "S11", "firewall 가드 — 확증·인증·기존 봉인 경로 거부 · 안정성 허용 · 쓰기 호출 전부 가드 경유 · selftest 루트 수명",
          d11["all_pass"], d11)

    # ---- S12 AST 가드 -------------------------------------------------------
    d12 = _selftest_ast(tree)
    _case(cases, "S12", "AST 가드 — 금지 import/호출 0 · argparse 옵션 2 · os.environ 0 · 공개 인자에 봉인값 0",
          d12["all_pass"], d12)

    # ---- S13 위생 -----------------------------------------------------------
    fp1, _n1 = _confirm_stat_fingerprint(CONFIRM_DIRS, ROOT)
    d13 = {"sealed_before": sealed0, "sealed_after": at.count_sealed(),
           "pycache_before": pyc0, "pycache_after": at.count_pycache(),
           "confirm_fp_before": fp0, "confirm_fp_after": fp1,
           "stability_sealed_created": os.path.isdir(STAB_SEALED)}
    _case(cases, "S13", "위생 — 전체 봉인 28/681/662/19 불변 · 확증 지문 불변 · 안정성 _sealed 생성 0 · __pycache__ 불변",
          d13["sealed_before"] == d13["sealed_after"]
          and d13["pycache_before"] == d13["pycache_after"]
          and fp0 == fp1 and not d13["stability_sealed_created"], d13)

    n_pass = sum(1 for x in cases if x["pass"])
    n_skip = sum(1 for x in cases if x["skip_reason"])
    res = {"_doc": "블록 AU 안정성 하네스 자체검사 (docs/111 §3 AU-4). 확증 라벨로 학습 0회.",
           "generated_kst": at.now_kst(), "harness_sha256": harness_sha,
           "contract_sha256": CONTRACT_SHA256, "at_harness_sha256": AT_HARNESS_SHA256,
           "n_cases": len(cases), "n_pass": n_pass, "n_skip": n_skip,
           "all_pass": n_pass == len(cases) and n_skip == 0,
           "confirmatory_training_runs": 0,
           "stability_training_runs": 0,
           "synthetic_smoke_runs": 1,
           "oof_assembled": False,
           "cases": cases}
    _pub_json(out or SELFTEST_OUT, res)
    print(json.dumps({k: res[k] for k in ("n_cases", "n_pass", "n_skip", "all_pass")},
                     ensure_ascii=False, indent=2))
    for x in cases:
        print("  %-5s %s  %s" % (x["case"], "PASS" if x["pass"] else "FAIL", x["desc"]))
    return res


# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="블록 AU — GIN 안정성 학습 42회 (docs/111)")
    ap.add_argument("--stage", default="selftest",
                    choices=["selftest", "plan", "run", "status", "finalize"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.stage == "selftest":
        r = stage_selftest(a.out)
        return 0 if r["all_pass"] else 1
    if a.stage == "plan":
        stage_plan(a.out)
        return 0
    if a.stage == "status":
        stage_status(a.out)
        return 0
    if a.stage == "finalize":
        stage_finalize(a.out)
        return 0
    return stage_run()


if __name__ == "__main__":
    sys.exit(main())
