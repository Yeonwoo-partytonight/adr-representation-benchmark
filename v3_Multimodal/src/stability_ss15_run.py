"""stability_ss15_run.py — 블록 BA (docs/116): 안정성 15셀 fold 수준 Δ + 서술적 two-way SS 분해 봉인 산출.

동결 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json` 의 **S6_stability_15cell_ss 를 그대로 구현**한다.
unit 목록·학습 시드 도메인·두 partial 경로 패턴·셀 수·대비 방향은 명세/계약/seed_freeze JSON 에서 읽는다(재기술 0).

⛔ 무결성 (docs/116 §2)
  · 봉인 «값» 은 `run` stage 안에서만 기계 판독한다. stdout·run.log·manifest_public·예외 메시지에
    Δ·SS·비율·평균·SD·범위·n_eval·n_excluded_undefined·best_ep·best_v 등 값을 **내보내지 않는다.**
  · Δ 의 부호를 따로 산출하지 않는다(emit_sign 0 · 부호 비교 0). 값은 ss15_result.json 에만 봉인.
  · AP = `sap.metrics.macro_ap`, SS = `rqint_downstream.two_way_ss` 를 import 해 그대로 호출(재구현 0).
  · S6 금지 분석(REML·ICC·분산성분·유의성 검정·CI) 0 · 판정 함수·rqint_test·bootstrap·open_sealed 호출 0.
  · 네트워크 0 · 환경변수 판독 0.

구조
  gate(root, expected)          = R0 검사(순수 함수 · 디스크 읽기만 · 쓰기 0 · cl.* 0).
  stage_run()                   = gate(ROOT, EXPECTED_REAL) + cl.gate_a_load + ComputeLock → core().
  core(root, expected, fault)   = R1~R7. 모든 경로는 os.path.join(root, <저장소 기준 상대경로>).
  selftest 는 gate·core 만 호출한다(cl.* 호출 0).
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import ast
import builtins
import contextlib
import datetime
import glob
import hashlib
import io
import json
import os
import platform
import re
import shutil
import tempfile
import time

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))

# ── 동결 입력 상수 (F4·F5·F6) ──────────────────────────────────────────────
SPEC_PATH = "v3_Multimodal/config/rqint_downstream_spec_v1.json"
SPEC_SHA256 = "fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf"
MODULE_PATH = "v3_Multimodal/src/rqint_downstream.py"
MODULE_SHA256 = "3e92a4ded1ea60b777c460b1b120232ae3051fe3a80e2e7c4f12d943c92ea680"
SEED_FREEZE = ("v3_Multimodal/config/gin_seed_freeze.json",
               "10828447c6d33118328ee97dc03279ab06e69d7ed8f9338662bfa740e42542f7")
STAB_CONTRACT = ("v3_Multimodal/config/gin_stability_contract.json",
                 "e092c18ff7afd4f21361be54901bce5828925b042d2b59bdf30a3f46cce67286")
COMPUTE_LOCK = ("v3_Multimodal/src/compute_lock.py",
                "b03a0b0012948b340f410670d6b045f279e1b21b4faa293bb45bbc2e99a6d738")
SAP_MODULES = {
    "v3_Multimodal/src/sap/__init__.py": "8dc63e28ffcf93dcdfde7facd0cf1d51b6e6c15ac4de2304de61c12ccb7a5306",
    "v3_Multimodal/src/sap/metrics.py": "a7d3fe4fe9e87983b35b086b0c464bde1e710e013f98813a2f28a2b48c8b2004",
    "v3_Multimodal/src/sap/consensus.py": "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91",
    "v3_Multimodal/src/sap/decision.py": "f688b20d816acabe17c2906cfa846c1f794ba45a416248c08aa7e41676e82a92",
    "v3_Multimodal/src/sap/rqint.py": "eb842bc98140e9c55b67bc1563cd5573c3b294885778f23744468b712c498b26",
}
MANIFEST_T4 = ("experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json",
               "a59ab54afd51508543a3ca952a5147ffc0c8687f997aacf42362ab699683ea59")
MANIFEST_S2 = ("experiments/runs/v3_gin_stability/manifest_s2_post_stability.json",
               "223209a99c694da0ddb03b4e5da021adae6c7eaaec75a89ffe553d0ffcf036cd")
REST_PUBLIC = ("experiments/runs/v3_confirm_rest/rest_public.json",
               "ccfb7b9b8986ffd3d57f55ffe1e27213ba2b08fc8af7d3ce0c95fc2d50b0abf3")
MASTER_X = ("data/processed/master_X.parquet",
            "788c8a64d19e8c3cc030476e7b2eb7f207246e3af6e73304d97f2fc9aa2ae6e6")
MASTER_Y = ("data/processed/master_Y.parquet",
            "bd23584342de6482e50f218bd409740acc2a00eeac86ee95bd89952bc3d18018")
SPLIT_DIR = "data/processed/splits/confirmatory/rep%d_seed%d"
SPLITS = {
    1: ("3c1a5d68bfcc6ddfa1de17990194c5beb3c4fe365ee0a123d04c4a34bed871b2",
        "7047606f76562ba54b1dadef0518cb8e18ed22dad5b588d22b298bcb892284ad"),
    2: ("786feeca045f603685e190a252636f3815695d2c9e61812c8db1daf063abccfa",
        "27f2e01dcb392be4873dc2820fdbb9bb8d0f5c8c85139878f523de6a74056b33"),
    3: ("9db08cf96298b47e182e286fa4ef4b94f74605c6f31f0f9f841bc723c638b4e4",
        "45762346d825a9f3a630ea34a423c10b49039275f5d4ef28a264e6ae2aa0ad23"),
}
SPLIT_DIAG = "experiments/runs/v3_gin_stability/split_diagnostics_public.json"
N_TE = {1: 219, 2: 218, 3: 218}
FLAG_FILES = ["v3_Multimodal/config/rqint_procedure_decisions_v1.json",
              "v3_Multimodal/config/gin_seed_freeze.json",
              "v3_Multimodal/config/gin_inner_valid_freeze.json"]
UNBLIND_FILES = ["v3_Multimodal/config/post_interim_freeze_v1_0.status.json",
                 "v3_Multimodal/config/gin_train_contract.json",
                 "experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json"]
DOCS33 = "docs/33_prereg_deviation_log.md"
DOCS33_ITEM = 74

OUT_REL = "experiments/runs/v3_stability_ss15"
OUT_GLOB = "experiments/runs/v3_stability_ss15*"
SELFTEST_OUT = "experiments/runs/v3_ss15_harness_selftest/selftest_ss15.json"
EXPECTED_SEALED_BEFORE = {"n_sealed_dirs": 33, "n_sealed_files_total": 763,
                          "n_sealed_artifacts": 739, "n_access_log": 24}
EXPECTED_SEALED_AFTER = {"n_sealed_dirs": 34, "n_sealed_files_total": 765,
                         "n_sealed_artifacts": 740, "n_access_log": 25}
_RUNS = "experiments/runs/"
GROUP_PREFIXES = {
    "confirm": [_RUNS + "v3_gin_confirm_rep1_seed201", _RUNS + "v3_gin_confirm_rep2_seed202",
                _RUNS + "v3_gin_confirm_rep3_seed203"],
    "stability": [_RUNS + "v3_gin_stability"],
    "gin_consensus": [_RUNS + "v3_gin_confirm_consensus_rep123"],
    "leverage": [_RUNS + "v3_rqint_leverage_d11"],
    "holm8": [_RUNS + "v3_rqint_holm8"],
    "d12": [_RUNS + "v3_rqint_d12"],
    "ss15": [OUT_REL],
}
FP_STAT = {
    "existing25": "7c585d25a78988fe01358cb33f5edb6935827d9b6bf815bfd0899103b166c0fa",
    "confirm": "6ed86c86830b664916c80c13fc2b0f355528c963df5b66e9053184316e51a8b9",
    "stability": "b4b493d265824709a242a12d37334659bf78a75bd51a46f8b0174f058d6e6cec",
    "gin_consensus": "2d52c9ac03961a6a7610ff7cfee6758fd957c6584867e47e44cb7f62548d11df",
    "leverage": "f0829db7e97b7fa37722265f311388c2d592b2458b2dbf514fe4748c0dc5a836",
    "holm8": "4177f61de8f3fd60a59d537b0683634a21e3dbe0e508c60da5dc4ee1ebcafc5e",
    "d12": "33a9e057a7786722cb5a7dc640dd63700855eeb7977be8d883f722290bcfd93d",
}
FP_NOACC = {
    "existing25": "7b617e1ccf2b3f377204df5c8504906a60cdb06269aa268d813179df7fcbb7d3",
    "confirm": "1992ab00977b3afd18ce42a678adacd28e2233f5a58dbd1baa05d65289d8287d",
    "stability": "65f08361b640c5ebdfab3e9a97f7b235b7e09d77be1c22e32060a46ff5b97843",
    "gin_consensus": "d061293d808f8e216d5bc08322eee19929573eba94f14407a0c8e6d68f2ebe95",
    "leverage": "ed9b860561880707c500e49f8d01c8bf4e3e5a263502b79c79d6e7335b3c179c",
}
CONF_ACCESS_BEFORE = {1: 25, 2: 25, 3: 24}
STAB_ACCESS_BEFORE = 4
HOLM8_TS = (_RUNS + "v3_rqint_holm8/manifest_public.json", "2026-10-01 02:50:35 KST")
D12_TS = (_RUNS + "v3_rqint_d12/manifest_public.json", "2026-10-04 04:52:31 KST")

N_PT = 370
N_DRUGS = 1092
N_FOLD = 5
CKPT_FIELDS = ["rep", "fold", "model", "train_seed", "completed_at_kst",
               "artifact_sha256", "n_epochs", "wall_seconds"]
PARTIAL_KEYS = {"P_test", "best_ep", "best_v"}
FORBIDDEN_KEY_SUBSTR = ("sign", "direction", "positive", "negative")
PUBLIC_TOP_KEYS = {"_doc", "block", "provenance", "run_id", "completed", "ts_completed_kst", "n_cells",
                   "n_units", "n_seeds", "n_partials_read", "n_checkpoints_read", "sealed_files",
                   "input_checks", "sealed_counts_start", "sealed_counts_end", "wall_seconds", "python",
                   "numpy", "sklearn", "pandas", "harness_sha256", "selftest_sha256", "spec_sha256",
                   "implementation_module_sha256", "values_disclosed", "unblinding_performed"}
PUBLIC_FILE_KEYS = {"name", "bytes", "sha256"}
PUBLIC_CHECK_KEYS = {"input_sha_all_match", "cid_order_match", "fold_rows_match", "finite_inputs",
                     "cells_complete", "structural_checks_ok"}
PUBLIC_COUNT_KEYS = {"n_sealed_dirs", "n_sealed_files_total", "n_sealed_artifacts", "n_access_log"}
KST = datetime.timezone(datetime.timedelta(hours=9))


# ═══════════════════════════════════════════════════════════════════════════
# 공용 유틸
# ═══════════════════════════════════════════════════════════════════════════
def now_kst():
    d = datetime.datetime.now(KST)
    return d.strftime("%Y-%m-%d %H:%M:%S.") + "%03d KST" % (d.microsecond // 1000)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class InvalidRun(Exception):
    """I4 무효 규칙(값 무관) 발동. 메시지 = 규칙 이름 + 파일명뿐(값 0)."""

    def __init__(self, rule, where=""):
        self.rule = rule
        super().__init__("[무효] %s :: %s" % (rule, where))


class HarnessAbort(Exception):
    """게이트·구조 결함(값 무관)."""


class GateFail(Exception):
    """R0 게이트 실패. 메시지 = 사유 문자열(값 0)."""


RULE_SHA = "입력 sha 불일치"
RULE_ORDER = "행 순서/cid 불일치"
RULE_NONFINITE = "비유한 값"
RULE_MISSING = "입력 결손"
RULE_COUNT = "셀 수 불일치"
RULE_KEYS = "partial 키 집합 불일치"
RULE_SHAPE = "P_test shape 불일치"
RULE_NEVAL = "M1b/M2b n_eval 불일치"


def _verify_then_import():
    """F4·F5 sha 를 파일로 검증한 뒤 sap·rqint_downstream·compute_lock 을 import 한다."""
    for rel, sha in list(SAP_MODULES.items()) + [(MODULE_PATH, MODULE_SHA256), COMPUTE_LOCK]:
        if sha256_file(os.path.join(ROOT, rel)) != sha:
            raise HarnessAbort("import 전 sha 불일치: " + rel)


_verify_then_import()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from sap.metrics import macro_ap                   # noqa: E402
from rqint_downstream import two_way_ss            # noqa: E402
import compute_lock as cl                          # noqa: E402


def _json_sha(root, rel_sha, where):
    b = _read_bytes(os.path.join(root, rel_sha[0]))
    if sha256_bytes(b) != rel_sha[1]:
        raise HarnessAbort("sha 불일치: " + where)
    return json.loads(b.decode("utf-8"))


def load_terms(root, expected):
    """명세 S6 · gin_seed_freeze · 안정성 계약에서 unit·시드·패턴·대비·셀 수를 읽는다(재기술 0)."""
    spec = _json_sha(root, expected["spec"], "명세")
    s6 = spec["S6_stability_15cell_ss"]
    sf = _json_sha(root, expected["seed_freeze"], "gin_seed_freeze")
    ct = _json_sha(root, expected["contract"], "gin_stability_contract")["stability_design"]
    conf_t = [int(t) for t in s6["inputs"]["confirmatory_t_domain"]]
    stab_t = [int(t) for t in s6["inputs"]["stability_t_domain"]]
    seeds = [int(t) for t in sf["training_seeds_ordered"]]
    if seeds != conf_t + stab_t or len(seeds) != int(s6["cells"]["seeds"]):
        raise HarnessAbort("시드 열 순서 결속 불일치")
    rmap = {int(s): int(r) for r, s in ct["rep_seed_map"].items()}
    units = []
    for s, f in s6["cells"]["representative_units"]:
        k = int(f[1:])
        if f != "f%d" % k:
            raise HarnessAbort("unit 표기 형식")
        units.append({"r": rmap[int(s)], "s": int(s), "k": k})
    if [[u["s"], u["k"]] for u in units] != [[int(a), int(b)] for a, b in ct["representative_units"]]:
        raise HarnessAbort("대표 unit 결속 불일치")
    if len(units) * len(seeds) != int(s6["cells"]["n_cells"]):
        raise HarnessAbort("셀 수 결속 불일치")
    arms = re.findall(r"macroAP_ij\((\S+?)\)", s6["fold_level_delta"])
    arms_sf = re.findall(r"macroAP_ij\((\S+?)\)", sf["delta_definition"])
    if len(arms) != 2 or arms != arms_sf:
        raise HarnessAbort("대비 방향 결속 불일치")
    hi, lo = arms
    models = list(ct["models"])
    if hi not in models or lo not in models:
        raise HarnessAbort("대비 arm 이 계약 모델 목록 밖")
    return {"s6": s6, "sf": sf, "units": units, "seeds": seeds, "conf_t": conf_t, "stab_t": stab_t,
            "arm_hi": hi, "arm_lo": lo, "arms": [lo, hi], "models": models,
            "conf_pattern": s6["inputs"]["confirmatory_partial"],
            "stab_pattern": s6["inputs"]["stability_partial"],
            "n_cells": int(s6["cells"]["n_cells"]),
            "source": {t: ("confirmatory" if t in conf_t else "stability") for t in seeds}}


def conf_tree(T, u):
    return T["conf_pattern"].split("/_sealed/")[0].format(r=u["r"], s=u["s"])


def stab_tree(T):
    return T["stab_pattern"].split("/_sealed/")[0]


def partial_rel(T, u, model, t):
    pat = T["conf_pattern"] if T["source"][t] == "confirmatory" else T["stab_pattern"]
    return pat.format(r=u["r"], s=u["s"], model=model, k=u["k"], t=t)


def cell_key(u, t):
    return "rep%d|fold%d|seed%d" % (u["r"], u["k"], t)


def _append_line(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _atomic_bytes(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _mkdir_new(path):
    os.mkdir(path)              # 이미 있으면 FileExistsError — 덮어쓰기 금지


def _ends_with_newline(path):
    """마지막 1바이트만 본다(비어 있으면 False)."""
    if os.path.getsize(path) == 0:
        return False
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) == b"\n"


def _keys_recursive(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _keys_recursive(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys_recursive(v)


def _assert_no_key_substr(obj, what):
    bad = sorted({k for k in _keys_recursive(obj) for w in FORBIDDEN_KEY_SUBSTR if w in k})
    if bad:
        raise HarnessAbort("금지 키 부분문자열(%s): %s" % (what, ",".join(bad)))


# ── 봉인 stat (파일을 열지 않는다 · access.log 는 개행 수만) ──────────────────
def sealed_lines(root):
    out = []
    for dp, _dn, fn in os.walk(root):
        parts = dp.split(os.sep)
        if ".git" in parts or "_sealed" not in parts:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            out.append((os.path.relpath(p, root), os.path.getsize(p), f == "access.log"))
    return out


def sealed_counts(root):
    dirs = sum(1 for dp, _dn, _fn in os.walk(root)
               if ".git" not in dp.split(os.sep) and os.path.basename(dp) == "_sealed")
    lines = sealed_lines(root)
    acc = sum(1 for x in lines if x[2])
    return {"n_sealed_dirs": dirs, "n_sealed_files_total": len(lines),
            "n_sealed_artifacts": len(lines) - acc, "n_access_log": acc}


def _fp(sel):
    s = sorted("%s\t%d" % (rel, b) for rel, b, _a in sel)
    return sha256_bytes(("\n".join(s) + "\n").encode("utf-8"))


def sealed_fingerprints(root, groups):
    """그룹별 stat 지문 + access.log 제외 지문. existing25 = 어느 그룹에도 속하지 않는 나머지."""
    lines = sealed_lines(root)
    allpre = [x for v in groups.values() for x in v]
    res = {}
    for g, pres in groups.items():
        sel = [x for x in lines if any(x[0].startswith(pp + os.sep) for pp in pres)]
        res[g] = (_fp(sel), _fp([x for x in sel if not x[2]]))
    sel = [x for x in lines if not any(x[0].startswith(pp + os.sep) for pp in allpre)]
    res["existing25"] = (_fp(sel), _fp([x for x in sel if not x[2]]))
    return res


def _newlines(path):
    return _read_bytes(path).count(b"\n")


def _pycache_dirs(root):
    return sum(1 for dp, _dn, _fn in os.walk(root)
               if ".git" not in dp.split(os.sep) and os.path.basename(dp) == "__pycache__")


def _find_key(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from _find_key(v, key)
    elif isinstance(o, list):
        for v in o:
            yield from _find_key(v, key)


def _docs33_item_body(text, n):
    starts = [(int(m.group(1)), m.start()) for m in re.finditer(r"^(\d+)\. \*\*", text, re.M)]
    if not starts:
        return None, None
    last = starts[-1][0]
    body = None
    for i, (num, pos) in enumerate(starts):
        if num == n:
            end = starts[i + 1][1] if i + 1 < len(starts) else len(text)
            body = text[pos:end]
    return last, body


# ═══════════════════════════════════════════════════════════════════════════
# gate — R0 (순수 함수 · 디스크 읽기만)
# ═══════════════════════════════════════════════════════════════════════════
def gate(root, expected):
    def need(cond, reason):
        if not cond:
            raise GateFail("[R0 게이트] " + reason)

    def j(rel):
        return os.path.join(root, rel)

    # 출력 부재(OUT_GLOB 만) · selftest 결과 존재
    need(not glob.glob(j(expected["out_glob"])), "출력 디렉터리 선존재")
    st_path = j(expected["selftest_out"])
    need(os.path.isfile(st_path), "selftest 결과 부재")
    st = json.loads(_read_bytes(st_path).decode("utf-8"))
    need(st.get("all_pass") is True, "selftest all_pass 아님")
    need(st.get("harness_sha256") == expected["harness_sha256"], "selftest 기록 하네스 sha 불일치")
    # docs/33 항목 74 (BA-4 선행 증거)
    last, body = _docs33_item_body(_read_bytes(j(expected["docs33"])).decode("utf-8"), expected["docs33_item"])
    need(last == expected["docs33_item"], "docs/33 마지막 항목 번호 불일치")
    need(body is not None and expected["harness_sha256"] in body, "docs/33 항목 본문에 하네스 sha 없음")
    # P2 봉인
    need(sealed_counts(root) == expected["sealed_before"], "봉인 계수 불일치")
    fps = sealed_fingerprints(root, expected["groups"])
    for g, v in expected["fp_stat"].items():
        need(fps[g][0] == v, "stat 지문 불일치: " + g)
    for g, v in expected["fp_noacc"].items():
        need(fps[g][1] == v, "access 제외 지문 불일치: " + g)
    T = load_terms(root, expected)
    for u in T["units"]:
        need(_newlines(j(conf_tree(T, u) + "/_sealed/access.log")) == expected["conf_access_before"][u["r"]],
             "확증 access.log 개행 수 불일치: rep%d" % u["r"])
    need(_newlines(j(stab_tree(T) + "/_sealed/access.log")) == expected["stab_access_before"],
         "안정성 access.log 개행 수 불일치")
    for f in expected["flag_files"]:
        v = list(_find_key(json.loads(_read_bytes(j(f)).decode("utf-8")), "gin_start_still_blocked"))
        need(bool(v) and all(x is True for x in v), "플래그 불일치: " + os.path.basename(f))
    for f in expected["unblind_files"]:
        v = list(_find_key(json.loads(_read_bytes(j(f)).decode("utf-8")), "unblinding_performed"))
        need(bool(v) and all(x is False for x in v), "unblinding 플래그 불일치: " + os.path.basename(f))
    # P3 시간 순서
    now = datetime.datetime.now(KST)
    for rel, ts in (expected["holm8_ts"], expected["d12_ts"]):
        m = json.loads(_read_bytes(j(rel)).decode("utf-8"))
        need(m.get("completed") is True, "선행 봉인 completed 아님: " + rel)
        need(m.get("ts_completed_kst") == ts, "선행 봉인 시각 불일치: " + rel)
        need(now > datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S KST").replace(tzinfo=KST),
             "현재 시각이 선행 봉인 이전")
    # P7 입력 사전 대조(봉인 파일은 열지 않음 — 존재·이름만)
    for u in T["units"]:
        for m in T["arms"]:
            for t in T["seeds"]:
                need(os.path.isfile(j(partial_rel(T, u, m, t))), "partial 부재: " + os.path.basename(partial_rel(T, u, m, t)))
        need(os.path.isfile(j(conf_tree(T, u) + "/_sealed/checkpoint.jsonl")), "확증 checkpoint 부재")
    need(os.path.isfile(j(stab_tree(T) + "/_sealed/checkpoint.jsonl")), "안정성 checkpoint 부재")
    _json_sha(root, expected["manifest_t4"], "manifest_t4")
    ms2 = _json_sha(root, expected["manifest_s2"], "manifest_s2")
    rp = _json_sha(root, expected["rest_public"], "rest_public")
    for u in T["units"]:
        for m in T["arms"]:
            for t in T["stab_t"]:
                need(os.path.basename(partial_rel(T, u, m, t)) in ms2["partial_sha256"], "manifest_s2 partial 키 부재")
    need(sha256_file(j(expected["master_x"][0])) == expected["master_x"][1], "master_X sha")
    need(sha256_file(j(expected["master_y"][0])) == expected["master_y"][1], "master_Y sha")
    diag = json.loads(_read_bytes(j(expected["split_diag"])).decode("utf-8"))["folds"]
    for u in T["units"]:
        sd = expected["split_dir"] % (u["r"], u["s"])
        fj_sha, fm_sha = expected["splits"][u["r"]]
        ent = rp["inputs_sha256"]["splits"]["rep%d_seed%d" % (u["r"], u["s"])]
        need((ent["folds_json_sha256"], ent["fold_membership_sha256"]) == (fj_sha, fm_sha), "rest_public split sha 불일치")
        need(sha256_file(j(sd + "/folds.json")) == fj_sha, "folds.json sha")
        need(sha256_file(j(sd + "/fold_membership.csv")) == fm_sha, "fold_membership.csv sha")
        fj = json.loads(_read_bytes(j(sd + "/folds.json")).decode("utf-8"))
        n_k = sum(1 for v in fj.values() if int(v) == u["k"])
        need(n_k == expected["n_te"][u["r"]] == diag["rep%d_fold%d" % (u["r"], u["k"])]["n_outer_test"],
             "fold k 행 수 불일치: rep%d" % u["r"])
    # P8 명세 결속(load_terms 가 sha·결속을 검증) + 금지 목록
    need(list(T["s6"]["forbidden"]) == expected["s6_forbidden"], "S6 forbidden 불일치")
    return T


# ═══════════════════════════════════════════════════════════════════════════
# core — R1~R7
# ═══════════════════════════════════════════════════════════════════════════
def fold_rows(root, expected, u, cid_order):
    """R1 — 하네스가 기록한 fold 배정을 그대로 쓴다(재생성 금지). te 오름차순 인덱스."""
    sd = os.path.join(root, expected["split_dir"] % (u["r"], u["s"]))
    fj_sha, fm_sha = expected["splits"][u["r"]]
    bj, bc = _read_bytes(os.path.join(sd, "folds.json")), _read_bytes(os.path.join(sd, "fold_membership.csv"))
    if sha256_bytes(bj) != fj_sha or sha256_bytes(bc) != fm_sha:
        raise InvalidRun(RULE_SHA, "split rep%d" % u["r"])
    fj = json.loads(bj.decode("utf-8"))
    fold_of_row = np.array([int(fj[str(int(c))]) for c in cid_order], dtype=np.int64)
    csv = pd.read_csv(io.BytesIO(bc), usecols=["cid", "fold"])
    if not np.array_equal(csv["cid"].to_numpy().astype(np.int64), cid_order):
        raise InvalidRun(RULE_ORDER, "fold_membership cid rep%d" % u["r"])
    if not np.array_equal(csv["fold"].to_numpy().astype(np.int64), fold_of_row):
        raise InvalidRun(RULE_ORDER, "fold_membership fold rep%d" % u["r"])
    return np.where(fold_of_row == u["k"])[0]


def core(root, expected, fault=None):
    t_start = time.perf_counter()
    T = load_terms(root, expected)
    out_dir = os.path.join(root, expected["out_rel"])
    sealed_out = os.path.join(out_dir, "_sealed")
    log = []

    def step(tag, msg):
        rec = (len(log) + 1, now_kst(), tag, msg)
        log.append(rec)
        print("%d\t%s\t%s\t%s" % rec, flush=True)

    if os.path.exists(out_dir):
        raise HarnessAbort("출력 디렉터리 선존재 — 덮어쓰기 금지")
    counts_start = sealed_counts(root)
    step("R0", "gate passed · core start · sealed dirs/files/artifacts/access = %d/%d/%d/%d"
         % tuple(counts_start[k] for k in ("n_sealed_dirs", "n_sealed_files_total", "n_sealed_artifacts", "n_access_log")))

    # ── R1 라벨·fold ──
    bx = _read_bytes(os.path.join(root, expected["master_x"][0]))
    by = _read_bytes(os.path.join(root, expected["master_y"][0]))
    if sha256_bytes(bx) != expected["master_x"][1] or sha256_bytes(by) != expected["master_y"][1]:
        raise InvalidRun(RULE_SHA, "master_X/master_Y")
    X = pd.read_parquet(io.BytesIO(bx))
    Y = pd.read_parquet(io.BytesIO(by))
    cid_list = X["cid"].astype(int).tolist()
    if cid_list != Y["cid"].astype(int).tolist() or cid_list != sorted(cid_list):
        raise InvalidRun(RULE_ORDER, "master_X/master_Y cid")
    ycols = [c for c in Y.columns if c != "cid"]
    Ym = Y[ycols].values.astype(int)
    cid_order = np.asarray(cid_list, dtype=np.int64)
    if Ym.shape != (expected["n_rows"], N_PT):
        raise InvalidRun(RULE_ORDER, "라벨 shape")
    brp = _read_bytes(os.path.join(root, expected["rest_public"][0]))
    if sha256_bytes(brp) != expected["rest_public"][1]:
        raise InvalidRun(RULE_SHA, "rest_public")
    rp = json.loads(brp.decode("utf-8"))
    TE = {}
    for u in T["units"]:
        ent = rp["inputs_sha256"]["splits"]["rep%d_seed%d" % (u["r"], u["s"])]
        if (ent["folds_json_sha256"], ent["fold_membership_sha256"]) != tuple(expected["splits"][u["r"]]):
            raise InvalidRun(RULE_SHA, "rest_public split rep%d" % u["r"])
        te = fold_rows(root, expected, u, cid_order)
        if len(te) != expected["n_te"][u["r"]]:
            raise InvalidRun(RULE_ORDER, "fold 행 수 rep%d" % u["r"])
        TE[u["r"]] = te
    step("R1", "labels %d x %d · fold rows %s" % (Ym.shape[0], Ym.shape[1],
                                                   "/".join(str(len(TE[u["r"]])) for u in T["units"])))

    # ── manifest (공개) ──
    bt4 = _read_bytes(os.path.join(root, expected["manifest_t4"][0]))
    bs2 = _read_bytes(os.path.join(root, expected["manifest_s2"][0]))
    if sha256_bytes(bt4) != expected["manifest_t4"][1]:
        raise InvalidRun(RULE_SHA, "manifest_t4")
    if sha256_bytes(bs2) != expected["manifest_s2"][1]:
        raise InvalidRun(RULE_SHA, "manifest_s2")
    MT4 = json.loads(bt4.decode("utf-8"))
    MS2 = json.loads(bs2.decode("utf-8"))

    # ── R2 판독 기록(먼저 쓴다 · 트리당 1줄) ──
    acc_targets = [(os.path.join(root, conf_tree(T, u), "_sealed", "access.log"), 1 + len(T["arms"]) * len(T["conf_t"]))
                   for u in T["units"]]
    acc_targets.append((os.path.join(root, stab_tree(T), "_sealed", "access.log"),
                        1 + len(T["units"]) * len(T["arms"]) * len(T["stab_t"])))
    for path, _n in acc_targets:
        if not _ends_with_newline(path):
            raise HarnessAbort("access.log 말미 개행 아님 또는 빈 파일: " + os.path.relpath(path, root))
    for path, n_files in acc_targets:
        _append_line(path, {
            "ts_kst": now_kst(), "type": "machine_read", "purpose": "S6 stability 15-cell input",
            "human_exposure": False,
            "path": "_sealed/{checkpoint.jsonl,_partial/%s_*,_partial/%s_*}" % (T["arm_lo"], T["arm_hi"]),
            "n_files": n_files, "actor": "vscode-claude", "step": "블록 BA(docs/116) R3 입력 판독",
            "delta_status": "not_computed_at_read",
            "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."})
    step("R2", "access.log +1 line per tree · %d trees" % len(acc_targets))

    try:
        return _core_after_r2(root, expected, fault, T, Ym, cid_order, TE, MT4, MS2, counts_start,
                              out_dir, sealed_out, log, step, t_start)
    except (InvalidRun, HarnessAbort):
        raise
    except Exception as e:           # 값 누설 방지 — 예외 메시지를 버리고 형식만 남긴다
        raise HarnessAbort("R2 이후 예외(메시지 비공개): " + type(e).__name__) from None


def _read_ckpt(path, exp_sha, where, exp_lines):
    if not os.path.isfile(path):
        raise InvalidRun(RULE_MISSING, where)
    cb = _read_bytes(path)
    if sha256_bytes(cb) != exp_sha:
        raise InvalidRun(RULE_SHA, where)
    if not cb.endswith(b"\n"):
        raise InvalidRun(RULE_MISSING, where + " 말미 개행")
    rows = [json.loads(x) for x in cb.decode("utf-8").splitlines()]
    if len(rows) != exp_lines or any(sorted(x.keys()) != sorted(CKPT_FIELDS) for x in rows):
        raise InvalidRun(RULE_MISSING, where + " 행·필드")
    return rows, sha256_bytes(cb)


def _load_partial(path, exp_shas, where, n_te):
    if not os.path.isfile(path):
        raise InvalidRun(RULE_MISSING, where)
    pb = _read_bytes(path)
    h = sha256_bytes(pb)
    if any(h != e for e in exp_shas):
        raise InvalidRun(RULE_SHA, where)
    with np.load(io.BytesIO(pb)) as z:
        if set(z.files) != PARTIAL_KEYS:
            raise InvalidRun(RULE_KEYS, where)
        P = np.array(z["P_test"])
    if P.ndim != 2 or P.shape != (n_te, N_PT):
        raise InvalidRun(RULE_SHAPE, where)
    if not bool(np.isfinite(P).all()):
        raise InvalidRun(RULE_NONFINITE, where)
    return P, h


def _core_after_r2(root, expected, fault, T, Ym, cid_order, TE, MT4, MS2, counts_start,
                   out_dir, sealed_out, log, step, t_start):
    PT = {}
    in_sha = {"partials": {}, "checkpoints": {}}
    # ── R3-1 checkpoint ──
    CK = {}
    for u in T["units"]:
        repkey = "rep%d_seed%d" % (u["r"], u["s"])
        rel = conf_tree(T, u) + "/_sealed/checkpoint.jsonl"
        rows, h = _read_ckpt(os.path.join(root, rel), MT4["checkpoint_sha256"][repkey], repkey + "/checkpoint.jsonl",
                             len(T["models"]) * N_FOLD * len(T["conf_t"]))
        ck = {}
        for x in rows:
            key = (int(x["fold"]), x["model"], int(x["train_seed"]))
            if key in ck or int(x["rep"]) != u["r"]:
                raise InvalidRun(RULE_MISSING, repkey + "/checkpoint.jsonl 키 중복·rep")
            ck[key] = x["artifact_sha256"]
        CK[u["r"]] = ck
        in_sha["checkpoints"][rel] = h
    rel = stab_tree(T) + "/_sealed/checkpoint.jsonl"
    rows, h = _read_ckpt(os.path.join(root, rel), MS2["checkpoint_sha256"], "stability/checkpoint.jsonl",
                         len(T["units"]) * len(T["models"]) * len(T["stab_t"]))
    CKS = {}
    for x in rows:
        key = (int(x["rep"]), int(x["fold"]), x["model"], int(x["train_seed"]))
        if key in CKS:
            raise InvalidRun(RULE_MISSING, "stability/checkpoint.jsonl 키 중복")
        CKS[key] = x["artifact_sha256"]
    in_sha["checkpoints"][rel] = h
    # ── R3-2 partial ──
    for u in T["units"]:
        for m in T["arms"]:
            for t in T["seeds"]:
                prel = partial_rel(T, u, m, t)
                name = os.path.basename(prel)
                if T["source"][t] == "confirmatory":
                    exp = [CK[u["r"]].get((u["k"], m, t))]
                else:
                    exp = [CKS.get((u["r"], u["k"], m, t)), MS2["partial_sha256"].get(name)]
                if any(e is None for e in exp):
                    raise InvalidRun(RULE_MISSING, name + " 기대 sha 부재")
                P, h = _load_partial(os.path.join(root, prel), exp, name, len(TE[u["r"]]))
                PT[(u["r"], m, t)] = P
                in_sha["partials"][prel] = h
    step("R3", "inputs verified · checkpoint %d · partial %d" % (len(in_sha["checkpoints"]), len(in_sha["partials"])))

    # ── R4 셀 계산 (fold 수준 Δ · P_test 끼리 섞는 연산 0) ──
    eligible = np.arange(N_PT)
    cells = {}
    for u in T["units"]:
        y_te = Ym[TE[u["r"]]]
        for t in T["seeds"]:
            a_lo = macro_ap(y_te, PT[(u["r"], T["arm_lo"], t)], eligible)
            a_hi = macro_ap(y_te, PT[(u["r"], T["arm_hi"], t)], eligible)
            if (a_lo["n_eval"], a_lo["n_excluded_undefined"], a_lo["n_eligible"]) != \
                    (a_hi["n_eval"], a_hi["n_excluded_undefined"], a_hi["n_eligible"]):
                raise InvalidRun(RULE_NEVAL, cell_key(u, t))
            for a in (a_lo, a_hi):
                if not np.isfinite(a["macro_ap"]):
                    raise InvalidRun(RULE_NONFINITE, "macro_ap " + cell_key(u, t))
            cells[cell_key(u, t)] = {"delta": float(a_hi["macro_ap"]) - float(a_lo["macro_ap"]),
                                     "n_eval": int(a_hi["n_eval"]),
                                     "n_excluded_undefined": int(a_hi["n_excluded_undefined"]),
                                     "n_eligible": int(a_hi["n_eligible"])}
    if fault == "drop_cell":                     # K7(h) 내부 fault-injection 전용
        cells.pop(sorted(cells)[0])
    exp_keys = [cell_key(u, t) for u in T["units"] for t in T["seeds"]]
    if len(cells) != T["n_cells"] or set(cells) != set(exp_keys):
        raise InvalidRun(RULE_COUNT, "cells")
    delta_cells = [[cells[cell_key(u, t)]["delta"] for t in T["seeds"]] for u in T["units"]]   # I6 (unit 행 × 시드 열)
    ss = two_way_ss(delta_cells)
    step("R4", "cells computed · %d cells · two_way_ss called once" % len(cells))

    # ── R5 무효 판정(I4 · 값 무관) ──
    fin = [c["delta"] for c in cells.values()] + [ss[k] for k in ("grand_mean", "SST", "SS_unit", "SS_seed", "SS_res")]
    fin += list(ss["unit_seed_mean"]) + list(ss["unit_seed_sd"]) + list(ss["unit_seed_range"])
    fin += [ss[k] for k in ("frac_unit", "frac_seed", "frac_res") if ss[k] is not None]
    if not all(np.isfinite(v) for v in fin):
        raise InvalidRun(RULE_NONFINITE, "delta/two_way_ss")
    if (ss["n_unit"], ss["n_seed"]) != (len(T["units"]), len(T["seeds"])):
        raise InvalidRun(RULE_COUNT, "two_way_ss shape")
    step("R5", "invalidation rules: none triggered")

    # ── R6 봉인 쓰기 ──
    _mkdir_new(out_dir)
    _mkdir_new(sealed_out)
    new_access = {
        "ts_kst": now_kst(), "type": "machine_read",
        "purpose": "S6 stability 15-cell fold-level Δ + descriptive two-way SS (sealed)",
        "human_exposure": False, "path": "_sealed/", "actor": "vscode-claude",
        "step": "블록 BA(docs/116) R6",
        "delta_status": "value_sealed_in_ss15_result__sign_not_computed", "emit_calls": 0,
        "note": "15셀 Δ·SS 는 ss15_result.json 에만 봉인. 부호 미산출. 사람 열람 0."}
    _assert_no_key_substr(new_access, "access.log")
    _append_line(os.path.join(sealed_out, "access.log"), new_access)
    ss_out = dict(ss)
    module_rule = ss_out["sst_zero_rule"]
    module_prov = ss_out["provenance"]
    ss_out["provenance"] = "confirmatory_sealed"
    ss_out["sst_zero_rule"] = T["s6"]["sst_zero_rule"]
    if ss_out["sst_zero"]:
        for k in ("frac_unit", "frac_seed", "frac_res"):
            ss_out[k] = "not_defined"
    result = {
        "_doc": ("블록 BA (docs/116) — S6 안정성 15셀 fold 수준 Δ + 서술적 two-way SS 분해 봉인 산출. "
                 "개봉 전 사람 열람 금지. 부호는 따로 산출하지 않았다. 서술 전용(REML·ICC·검정·CI 0)."),
        "block": "BA (docs/116)", "provenance": "confirmatory_sealed",
        "spec_sha256": expected["spec"][1], "implementation_module_sha256": expected["module_sha256"],
        "module_function": "rqint_downstream.two_way_ss",
        "module_provenance_constant": module_prov,
        "contrast_definition": "%s − %s" % (T["arm_hi"], T["arm_lo"]),
        "estimand_level": "fold (held-out fold of outer unit i under training seed j)",
        "delta_definition_verbatim": T["sf"]["delta_definition"],
        "delta_unit_caveat_verbatim": T["sf"]["delta_unit_caveat"],
        "firewall_verbatim": T["s6"]["firewall_verbatim"],
        "eligible_pt": "np.arange(%d) explicit" % N_PT,
        "orientation": {"rows_units": ["rep%d|fold%d|split_seed%d" % (u["r"], u["k"], u["s"]) for u in T["units"]],
                        "cols_train_seed_values": list(T["seeds"]),
                        "source_by_train_seed": {str(t): T["source"][t] for t in T["seeds"]}},
        "cells": {k: cells[k] for k in exp_keys},
        "two_way_ss": ss_out,
        "module_sst_zero_rule": module_rule,
        "not_computed": list(T["s6"]["forbidden"]),
        "input_sha256": {"partials": dict(sorted(in_sha["partials"].items())),
                         "checkpoints": dict(sorted(in_sha["checkpoints"].items())),
                         "master_X": expected["master_x"][1], "master_Y": expected["master_y"][1],
                         "splits": {"rep%d_seed%d/%s" % (u["r"], u["s"], nm): sh for u in T["units"]
                                    for nm, sh in zip(("folds.json", "fold_membership.csv"), expected["splits"][u["r"]])},
                         "manifest_t4": expected["manifest_t4"][1], "manifest_s2": expected["manifest_s2"][1],
                         "rest_public": expected["rest_public"][1]},
        "counts": {"cells": len(cells), "partials_read": len(in_sha["partials"]),
                   "checkpoints_read": len(in_sha["checkpoints"])},
    }
    _assert_no_key_substr(result, "ss15_result")
    rrel = "_sealed/ss15_result.json"
    _atomic_bytes(os.path.join(out_dir, rrel),
                  (json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
    step("R6", "sealed written · 1 file + access.log")

    # ── R7 공개 산출 ──
    counts_end = sealed_counts(root)
    wall = round(time.perf_counter() - t_start, 3)
    import sklearn
    ts_done = now_kst()
    pub = {
        "_doc": ("블록 BA (docs/116) 공개 manifest — 개수·환경·검증 불리언·봉인 파일 이름/바이트/sha256·시간뿐. "
                 "Δ·SS·비율·평균·SD·범위·n_eval 등 값은 기록하지 않는다."),
        "block": "BA (docs/116)", "provenance": expected["provenance"],
        "run_id": "BA-" + datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "completed": True, "ts_completed_kst": ts_done,
        "n_cells": len(cells), "n_units": len(T["units"]), "n_seeds": len(T["seeds"]),
        "n_partials_read": len(in_sha["partials"]), "n_checkpoints_read": len(in_sha["checkpoints"]),
        "sealed_files": [{"name": rrel, "bytes": os.path.getsize(os.path.join(out_dir, rrel)),
                          "sha256": sha256_file(os.path.join(out_dir, rrel))}],
        "input_checks": {"input_sha_all_match": True, "cid_order_match": True, "fold_rows_match": True,
                         "finite_inputs": True, "cells_complete": True, "structural_checks_ok": True},
        "sealed_counts_start": counts_start, "sealed_counts_end": counts_end,
        "wall_seconds": wall,
        "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
        "pandas": pd.__version__,
        "harness_sha256": expected["public_meta"]["harness_sha256"],
        "selftest_sha256": expected["public_meta"]["selftest_sha256"],
        "spec_sha256": expected["spec"][1],
        "implementation_module_sha256": expected["module_sha256"],
        "values_disclosed": False, "unblinding_performed": False,
    }
    if set(pub) != PUBLIC_TOP_KEYS or any(set(f) != PUBLIC_FILE_KEYS for f in pub["sealed_files"]) \
            or set(pub["input_checks"]) != PUBLIC_CHECK_KEYS \
            or set(pub["sealed_counts_start"]) != PUBLIC_COUNT_KEYS or set(pub["sealed_counts_end"]) != PUBLIC_COUNT_KEYS:
        raise HarnessAbort("manifest_public 화이트리스트 불일치")
    _assert_no_key_substr(pub, "manifest_public")
    step("R7", "public manifest + run.log · wall_seconds %.3f" % wall)
    _atomic_bytes(os.path.join(out_dir, "manifest_public.json"),
                  (json.dumps(pub, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    _atomic_bytes(os.path.join(out_dir, "run.log"),
                  ("".join("seq=%d\t%s\t%s\t%s\n" % rec for rec in log)).encode("utf-8"))
    return pub


# ═══════════════════════════════════════════════════════════════════════════
# stage_run — gate + compute_lock → core
# ═══════════════════════════════════════════════════════════════════════════
def expected_real(harness_sha, selftest_sha):
    return {
        "spec": (SPEC_PATH, SPEC_SHA256), "seed_freeze": SEED_FREEZE, "contract": STAB_CONTRACT,
        "module_sha256": MODULE_SHA256,
        "manifest_t4": MANIFEST_T4, "manifest_s2": MANIFEST_S2, "rest_public": REST_PUBLIC,
        "master_x": MASTER_X, "master_y": MASTER_Y, "n_rows": N_DRUGS,
        "split_dir": SPLIT_DIR, "splits": SPLITS, "split_diag": SPLIT_DIAG, "n_te": N_TE,
        "flag_files": FLAG_FILES, "unblind_files": UNBLIND_FILES,
        "docs33": DOCS33, "docs33_item": DOCS33_ITEM,
        "out_rel": OUT_REL, "out_glob": OUT_GLOB, "selftest_out": SELFTEST_OUT,
        "sealed_before": EXPECTED_SEALED_BEFORE, "sealed_after": EXPECTED_SEALED_AFTER,
        "groups": GROUP_PREFIXES, "fp_stat": FP_STAT, "fp_noacc": FP_NOACC,
        "conf_access_before": CONF_ACCESS_BEFORE, "stab_access_before": STAB_ACCESS_BEFORE,
        "holm8_ts": HOLM8_TS, "d12_ts": D12_TS,
        "s6_forbidden": ["REML", "ICC", "분산성분 추정", "유의성 검정", "확증 CI"],
        "harness_sha256": harness_sha, "provenance": "confirmatory_sealed",
        "public_meta": {"harness_sha256": harness_sha, "selftest_sha256": selftest_sha},
    }


def stage_run():
    me = sha256_file(os.path.abspath(__file__))
    st_path = os.path.join(ROOT, SELFTEST_OUT)
    st_sha = sha256_file(st_path) if os.path.isfile(st_path) else None
    E = expected_real(me, st_sha)
    gate(ROOT, E)
    cl.gate_a_load("BA run entry")
    with cl.ComputeLock(script="stability_ss15_run.py", role="runner"):
        pub = core(ROOT, E, fault=None)
    end = sealed_counts(ROOT)
    fps = sealed_fingerprints(ROOT, GROUP_PREFIXES)
    unchanged = {g: fps[g][0] == FP_STAT[g] for g in ("existing25", "gin_consensus", "leverage", "holm8", "d12")}
    noacc = {g: fps[g][1] == FP_NOACC[g] for g in ("confirm", "stability")}
    ok = end == EXPECTED_SEALED_AFTER and all(unchanged.values()) and all(noacc.values())
    print(json.dumps({"stage": "run", "sealed_counts_end_expected": end == EXPECTED_SEALED_AFTER,
                      "fp_unchanged_5": unchanged, "fp_noacc_unchanged": noacc,
                      "n_cells": pub["n_cells"], "n_partials_read": pub["n_partials_read"]}, ensure_ascii=False), flush=True)
    return 0 if ok else 3


# ═══════════════════════════════════════════════════════════════════════════
# 합성 자체검사 K1~K13 (확증 입력 판독 0)
# ═══════════════════════════════════════════════════════════════════════════
PROVENANCE_SYN = "synthetic_fixture"
FX_HARNESS_SHA = "fixture-harness-sha-0000"


def _w(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _wj(path, obj, indent=2):
    _w(path, (json.dumps(obj, indent=indent, ensure_ascii=False) + "\n").encode("utf-8"))


def _save_npz(path, **arrays):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        np.savez(f, **arrays)


def _make_fixture(tmp, n=60, rng_seed=20261004, zero_cols=(), equal_arms=False):
    """저장소와 같은 상대 레이아웃의 합성 저장소. 명세·계약·seed_freeze 는 실파일 사본(공개 config)."""
    rng = np.random.default_rng(rng_seed)
    E = expected_real(FX_HARNESS_SHA, "fixture")
    for key in ("spec", "seed_freeze", "contract"):
        _w(os.path.join(tmp, E[key][0]), _read_bytes(os.path.join(ROOT, E[key][0])))
    T = load_terms(tmp, E)
    cids = np.sort(rng.choice(np.arange(1000, 100000), size=n, replace=False)).astype(np.int64)
    Yv = (rng.random((n, N_PT)) < 0.3).astype(int)
    folds = {}
    for u in T["units"]:
        folds[u["r"]] = rng.permutation(np.arange(n) % N_FOLD)
    for u in T["units"]:                       # 모든 대표 fold 의 test 에 열마다 양성 ≥1 (zero_cols 제외)
        te = np.where(folds[u["r"]] == u["k"])[0]
        for j in range(N_PT):
            if Yv[te, j].sum() == 0:
                Yv[te[0], j] = 1
    for j in zero_cols:
        Yv[:, j] = 0
    mx, my = os.path.join(tmp, MASTER_X[0]), os.path.join(tmp, MASTER_Y[0])
    os.makedirs(os.path.dirname(mx), exist_ok=True)
    pd.DataFrame({"cid": cids, "smiles": ["C"] * n}).to_parquet(mx)
    ydf = pd.DataFrame(Yv, columns=["pt_%04d" % j for j in range(N_PT)])
    ydf.insert(0, "cid", cids)
    ydf.to_parquet(my)
    E["master_x"] = (MASTER_X[0], sha256_file(mx))
    E["master_y"] = (MASTER_Y[0], sha256_file(my))
    E["n_rows"] = n
    splits, n_te, diag, rest = {}, {}, {}, {}
    for u in T["units"]:
        sd = os.path.join(tmp, SPLIT_DIR % (u["r"], u["s"]))
        _wj(os.path.join(sd, "folds.json"), {str(int(c)): int(f) for c, f in zip(cids, folds[u["r"]])})
        os.makedirs(sd, exist_ok=True)
        pd.DataFrame({"cid": cids, "fold": folds[u["r"]], "scaffold": ["x"] * n}).to_csv(
            os.path.join(sd, "fold_membership.csv"), index=False)
        splits[u["r"]] = (sha256_file(os.path.join(sd, "folds.json")), sha256_file(os.path.join(sd, "fold_membership.csv")))
        n_te[u["r"]] = int((folds[u["r"]] == u["k"]).sum())
        diag["rep%d_fold%d" % (u["r"], u["k"])] = {"n_outer_test": n_te[u["r"]]}
        rest["rep%d_seed%d" % (u["r"], u["s"])] = {"folds_json_sha256": splits[u["r"]][0],
                                                   "fold_membership_sha256": splits[u["r"]][1]}
    E["splits"], E["n_te"] = splits, n_te
    _wj(os.path.join(tmp, SPLIT_DIAG), {"folds": diag})
    _wj(os.path.join(tmp, REST_PUBLIC[0]), {"inputs_sha256": {"splits": rest}})
    E["rest_public"] = (REST_PUBLIC[0], sha256_file(os.path.join(tmp, REST_PUBLIC[0])))
    # 확증 rep 트리 + 안정성 트리
    P = {}
    t4_ck, s2_part = {}, {}
    stab_rows = []
    for u in T["units"]:
        sdir = os.path.join(tmp, conf_tree(T, u), "_sealed")
        os.makedirs(os.path.join(sdir, "_partial"))
        _w(os.path.join(sdir, "access.log"), (json.dumps({"type": "machine_read", "actor": "fixture"}) + "\n").encode())
        te_n = n_te[u["r"]]
        for t in T["seeds"]:
            base = rng.random((te_n, N_PT)).astype(np.float32)
            for m in T["arms"]:
                P[(u["r"], m, t)] = base.copy() if (equal_arms or m == T["arm_lo"]) else \
                    rng.random((te_n, N_PT)).astype(np.float32)
        rows = []
        for m in T["models"]:
            for k in range(N_FOLD):
                for t in T["conf_t"]:
                    sh = "0" * 64
                    if m in T["arms"] and k == u["k"]:
                        pp = os.path.join(tmp, partial_rel(T, u, m, t))
                        _save_npz(pp, P_test=P[(u["r"], m, t)], best_ep=np.int32(rng.integers(3, 60)),
                                  best_v=np.float64(rng.random()))
                        sh = sha256_file(pp)
                    rows.append(json.dumps({"rep": u["r"], "fold": k, "model": m, "train_seed": t,
                                            "completed_at_kst": "fixture", "artifact_sha256": sh,
                                            "n_epochs": 10, "wall_seconds": 1}))
        cp = os.path.join(sdir, "checkpoint.jsonl")
        _w(cp, ("\n".join(rows) + "\n").encode())
        t4_ck["rep%d_seed%d" % (u["r"], u["s"])] = sha256_file(cp)
        for m in T["models"]:
            for t in T["stab_t"]:
                name = os.path.basename(partial_rel(T, u, m, t))
                sh = "0" * 64
                if m in T["arms"]:
                    pp = os.path.join(tmp, partial_rel(T, u, m, t))
                    _save_npz(pp, P_test=P[(u["r"], m, t)], best_ep=np.int32(rng.integers(3, 60)),
                              best_v=np.float64(rng.random()))
                    sh = sha256_file(pp)
                s2_part[name] = sh
                stab_rows.append(json.dumps({"rep": u["r"], "fold": u["k"], "model": m, "train_seed": t,
                                             "completed_at_kst": "fixture", "artifact_sha256": sh,
                                             "n_epochs": 10, "wall_seconds": 1}))
    ssd = os.path.join(tmp, stab_tree(T), "_sealed")
    _w(os.path.join(ssd, "access.log"), (json.dumps({"type": "machine_read", "actor": "fixture"}) + "\n").encode())
    _w(os.path.join(ssd, "checkpoint.jsonl"), ("\n".join(stab_rows) + "\n").encode())
    _wj(os.path.join(tmp, MANIFEST_T4[0]), {"checkpoint_sha256": t4_ck, "unblinding_performed": False})
    _wj(os.path.join(tmp, MANIFEST_S2[0]), {"checkpoint_sha256": sha256_file(os.path.join(ssd, "checkpoint.jsonl")),
                                            "partial_sha256": s2_part})
    E["manifest_t4"] = (MANIFEST_T4[0], sha256_file(os.path.join(tmp, MANIFEST_T4[0])))
    E["manifest_s2"] = (MANIFEST_S2[0], sha256_file(os.path.join(tmp, MANIFEST_S2[0])))
    # 나머지 봉인 그룹 · 플래그 · 선행 봉인 manifest · docs/33 · selftest 결과
    for g in ("gin_consensus", "leverage", "holm8", "d12"):
        _w(os.path.join(tmp, GROUP_PREFIXES[g][0], "_sealed", "access.log"), b"{}\n")
        _w(os.path.join(tmp, GROUP_PREFIXES[g][0], "_sealed", "x.bin"), b"xx")
    _w(os.path.join(tmp, _RUNS, "fx_old", "_sealed", "access.log"), b"{}\n")
    _w(os.path.join(tmp, _RUNS, "fx_old", "_sealed", "y.bin"), b"yyy")
    for f in FLAG_FILES:
        if f not in (E["seed_freeze"][0],):
            _wj(os.path.join(tmp, f), {"gin_start_still_blocked": True})
    for f in UNBLIND_FILES:
        if f != MANIFEST_T4[0]:
            _wj(os.path.join(tmp, f), {"unblinding_performed": False})
    for rel, ts in (HOLM8_TS, D12_TS):
        _wj(os.path.join(tmp, rel), {"completed": True, "ts_completed_kst": ts})
    _w(os.path.join(tmp, DOCS33), ("# fixture\n\n73. **이전 항목**:\n본문\n\n74. **착수 전 결정**:\n하네스 `%s`\n"
                                   % FX_HARNESS_SHA).encode("utf-8"))
    _wj(os.path.join(tmp, SELFTEST_OUT), {"all_pass": True, "harness_sha256": FX_HARNESS_SHA})
    E["sealed_before"] = sealed_counts(tmp)
    E["sealed_after"] = {k: E["sealed_before"][k] + d for k, d in
                         zip(("n_sealed_dirs", "n_sealed_files_total", "n_sealed_artifacts", "n_access_log"), (1, 2, 1, 1))}
    fps = sealed_fingerprints(tmp, GROUP_PREFIXES)
    E["fp_stat"] = {g: fps[g][0] for g in FP_STAT}
    E["fp_noacc"] = {g: fps[g][1] for g in FP_NOACC}
    E["conf_access_before"] = {u["r"]: 1 for u in T["units"]}
    E["stab_access_before"] = 1
    E["provenance"] = PROVENANCE_SYN
    return E, {"T": T, "Y": Yv, "folds": folds, "P": P, "cids": cids}


def _run_quiet(root, E, fault=None):
    buf = io.StringIO()
    exc = None
    with contextlib.redirect_stdout(buf):
        try:
            core(root, E, fault=fault)
        except Exception as e:           # noqa: BLE001 — 시험 대상
            exc = e
    return buf.getvalue(), exc


def _load_result(root, E):
    return json.loads(_read_bytes(os.path.join(root, E["out_rel"], "_sealed", "ss15_result.json")).decode("utf-8"))


def _res(name, checks, **extra):
    checks = {k: bool(v) for k, v in checks.items()}
    fails = [k for k, v in checks.items() if not v]
    return dict({"name": name, "checks": checks, "pass": not fails, "fails": fails}, **extra)


def _src_tree():
    return ast.parse(_read_bytes(os.path.abspath(__file__)).decode("utf-8"))


def _parents(tree):
    par = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            par[ch] = node
    return par


def _enclosing(par, n):
    cur = par.get(n)
    while cur is not None:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
        cur = par.get(cur)
    return None


def _call_name(node):
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)


def _docstring_nodes(tree):
    ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant) \
                and isinstance(n.body[0].value.value, str):
            ids.add(id(n.body[0].value))
    return ids


def _no_decimal(s):
    return re.search(r"\d+\.\d+", s) is None


def selftest_K1_constants():
    checks = {"spec": sha256_file(os.path.join(ROOT, SPEC_PATH)) == SPEC_SHA256,
              "module": sha256_file(os.path.join(ROOT, MODULE_PATH)) == MODULE_SHA256,
              "seed_freeze": sha256_file(os.path.join(ROOT, SEED_FREEZE[0])) == SEED_FREEZE[1],
              "contract": sha256_file(os.path.join(ROOT, STAB_CONTRACT[0])) == STAB_CONTRACT[1],
              "compute_lock": sha256_file(os.path.join(ROOT, COMPUTE_LOCK[0])) == COMPUTE_LOCK[1]}
    for rel, sha in SAP_MODULES.items():
        checks["sap:" + os.path.basename(rel)] = sha256_file(os.path.join(ROOT, rel)) == sha
    for key, (rel, sha) in (("manifest_t4", MANIFEST_T4), ("manifest_s2", MANIFEST_S2), ("rest_public", REST_PUBLIC),
                            ("master_X", MASTER_X), ("master_Y", MASTER_Y)):
        checks[key] = sha256_file(os.path.join(ROOT, rel)) == sha
    for r, (a, b) in SPLITS.items():
        sd = None
        for s in (json.loads(_read_bytes(os.path.join(ROOT, STAB_CONTRACT[0])).decode("utf-8"))
                  ["stability_design"]["rep_seed_map"].items()):
            if int(s[0]) == r:
                sd = os.path.join(ROOT, SPLIT_DIR % (r, int(s[1])))
        checks["split_rep%d" % r] = (sha256_file(os.path.join(sd, "folds.json")),
                                     sha256_file(os.path.join(sd, "fold_membership.csv"))) == (a, b)
    return _res("K1 상수·해시", checks)


def selftest_K2_spec_binding():
    E = expected_real("x", "x")
    T = load_terms(ROOT, E)
    spec = json.loads(_read_bytes(os.path.join(ROOT, SPEC_PATH)).decode("utf-8"))["S6_stability_15cell_ss"]
    sf = json.loads(_read_bytes(os.path.join(ROOT, SEED_FREEZE[0])).decode("utf-8"))
    ct = json.loads(_read_bytes(os.path.join(ROOT, STAB_CONTRACT[0])).decode("utf-8"))["stability_design"]
    tree = _src_tree()
    docs = _docstring_nodes(tree)
    seed_lists = [list(sf["training_seeds_ordered"]), list(spec["inputs"]["confirmatory_t_domain"]),
                  list(spec["inputs"]["stability_t_domain"])]
    lit_lists = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.List, ast.Tuple, ast.Set)) and n.elts and \
                all(isinstance(e, ast.Constant) and type(e.value) is int for e in n.elts):
            vals = [e.value for e in n.elts]
            if vals in seed_lists:
                lit_lists.append((vals, n.lineno))
    needles = [spec["inputs"]["confirmatory_partial"], spec["inputs"]["stability_partial"]]
    needles += [os.path.basename(x) for x in needles]
    pat_lits = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docs and any(x in n.value for x in needles)]
    # 봉인 JSON orientation 이 읽은 JSON 에서 생성되는지 — 합성 run 결과로 확인(K4 에서 base 결과 재사용)
    checks = {
        "units_from_spec": [[u["s"], "f%d" % u["k"]] for u in T["units"]] == spec["cells"]["representative_units"],
        "rep_map_from_contract": all(str(u["r"]) in ct["rep_seed_map"] and ct["rep_seed_map"][str(u["r"])] == u["s"]
                                     for u in T["units"]),
        "seeds_from_seed_freeze": T["seeds"] == sf["training_seeds_ordered"]
                                  == spec["inputs"]["confirmatory_t_domain"] + spec["inputs"]["stability_t_domain"],
        "n_units_3_seeds_5": (len(T["units"]), len(T["seeds"])) == (3, spec["cells"]["seeds"]),
        "patterns_from_spec": (T["conf_pattern"], T["stab_pattern"]) == (spec["inputs"]["confirmatory_partial"],
                                                                         spec["inputs"]["stability_partial"]),
        "n_cells_15": T["n_cells"] == spec["cells"]["n_cells"] == 15,
        "forbidden_5": list(T["s6"]["forbidden"]) == spec["forbidden"] and len(spec["forbidden"]) == 5,
        "contrast_from_spec": (T["arm_hi"], T["arm_lo"]) == tuple(re.findall(r"macroAP_ij\((\S+?)\)", spec["fold_level_delta"])),
        "no_seed_list_literals": not lit_lists,
        "no_path_pattern_literals": not pat_lits,
    }
    return _res("K2 S6 결속", checks, seed_list_literals=lit_lists, pattern_literals=pat_lits)


def selftest_K2b_orientation(root, E, fx):
    R = _load_result(root, E)
    T = fx["T"]
    sf = json.loads(_read_bytes(os.path.join(ROOT, SEED_FREEZE[0])).decode("utf-8"))
    spec = json.loads(_read_bytes(os.path.join(ROOT, SPEC_PATH)).decode("utf-8"))["S6_stability_15cell_ss"]
    o = R["orientation"]
    src = {str(t): "confirmatory" for t in spec["inputs"]["confirmatory_t_domain"]}
    src.update({str(t): "stability" for t in spec["inputs"]["stability_t_domain"]})
    return {"orientation_cols_from_json": o["cols_train_seed_values"] == sf["training_seeds_ordered"],
            "orientation_source_from_json": o["source_by_train_seed"] == src,
            "orientation_rows_from_json": o["rows_units"] == ["rep%d|fold%d|split_seed%d" % (u["r"], u["k"], u["s"])
                                                              for u in T["units"]]}


def selftest_K3_fold_rows(tmp_root):
    res, msgs = {}, []
    tmp = os.path.join(tmp_root, "k3_rows")
    os.makedirs(tmp)
    E, fx = _make_fixture(tmp, rng_seed=31)
    T = fx["T"]
    ok = True
    for u in T["units"]:
        te = fold_rows(tmp, E, u, fx["cids"])
        ok &= bool(np.array_equal(te, np.where(fx["folds"][u["r"]] == u["k"])[0]))
    res["te_equals_where_fold_k"] = ok
    # folds.json ↔ CSV 불일치
    tmp = os.path.join(tmp_root, "k3_csv")
    os.makedirs(tmp)
    E, fx = _make_fixture(tmp, rng_seed=32)
    u = fx["T"]["units"][1]
    sd = os.path.join(tmp, SPLIT_DIR % (u["r"], u["s"]))
    fj = json.loads(_read_bytes(os.path.join(sd, "folds.json")).decode("utf-8"))
    c0 = str(int(fx["cids"][0]))
    fj[c0] = (int(fj[c0]) + 1) % N_FOLD
    _wj(os.path.join(sd, "folds.json"), fj)
    E["splits"] = dict(E["splits"])
    E["splits"][u["r"]] = (sha256_file(os.path.join(sd, "folds.json")), E["splits"][u["r"]][1])
    rp = json.loads(_read_bytes(os.path.join(tmp, REST_PUBLIC[0])).decode("utf-8"))
    rp["inputs_sha256"]["splits"]["rep%d_seed%d" % (u["r"], u["s"])]["folds_json_sha256"] = E["splits"][u["r"]][0]
    _wj(os.path.join(tmp, REST_PUBLIC[0]), rp)
    E["rest_public"] = (REST_PUBLIC[0], sha256_file(os.path.join(tmp, REST_PUBLIC[0])))
    E["n_te"] = dict(E["n_te"])
    E["n_te"][u["r"]] = sum(1 for v in fj.values() if int(v) == u["k"])
    _o, exc = _run_quiet(tmp, E)
    msgs.append(str(exc))
    res["folds_csv_mismatch_aborts"] = isinstance(exc, InvalidRun) and exc.rule == RULE_ORDER \
        and not os.path.exists(os.path.join(tmp, E["out_rel"]))
    # P_test 행 수 ≠ len(te)
    tmp = os.path.join(tmp_root, "k3_rows_bad")
    os.makedirs(tmp)
    E, fx = _make_fixture(tmp, rng_seed=33)
    T = fx["T"]
    u, t = T["units"][0], T["conf_t"][0]
    _rewrite_partial_chain(tmp, E, T, u, T["arm_hi"], t, P_test=fx["P"][(u["r"], T["arm_hi"], t)][:-1])
    _o, exc = _run_quiet(tmp, E)
    msgs.append(str(exc))
    res["rows_mismatch_aborts"] = isinstance(exc, InvalidRun) and exc.rule == RULE_SHAPE \
        and not os.path.exists(os.path.join(tmp, E["out_rel"]))
    res["messages_no_decimal"] = all(_no_decimal(m) for m in msgs)
    return _res("K3 fold 행", res), msgs


def _rewrite_partial_chain(root, E, T, u, m, t, update_chain=True, update_manifest_s2_partial=True, **over):
    """partial 을 다시 쓰고(키 덮어쓰기/추가) 필요하면 checkpoint·manifest sha 사슬을 갱신한다."""
    pp = os.path.join(root, partial_rel(T, u, m, t))
    with np.load(pp) as z:
        d = {k: z[k] for k in z.files}
    d.update(over)
    with open(pp, "wb") as f:
        np.savez(f, **d)
    if not update_chain:
        return
    new = sha256_file(pp)
    if T["source"][t] == "confirmatory":
        cp = os.path.join(root, conf_tree(T, u), "_sealed", "checkpoint.jsonl")
        rows = [json.loads(x) for x in _read_bytes(cp).decode("utf-8").splitlines()]
        for x in rows:
            if (x["fold"], x["model"], x["train_seed"]) == (u["k"], m, t):
                x["artifact_sha256"] = new
        _w(cp, ("\n".join(json.dumps(x) for x in rows) + "\n").encode())
        mt = json.loads(_read_bytes(os.path.join(root, MANIFEST_T4[0])).decode("utf-8"))
        mt["checkpoint_sha256"]["rep%d_seed%d" % (u["r"], u["s"])] = sha256_file(cp)
        _wj(os.path.join(root, MANIFEST_T4[0]), mt)
        E["manifest_t4"] = (MANIFEST_T4[0], sha256_file(os.path.join(root, MANIFEST_T4[0])))
    else:
        cp = os.path.join(root, stab_tree(T), "_sealed", "checkpoint.jsonl")
        rows = [json.loads(x) for x in _read_bytes(cp).decode("utf-8").splitlines()]
        for x in rows:
            if (x["rep"], x["fold"], x["model"], x["train_seed"]) == (u["r"], u["k"], m, t):
                x["artifact_sha256"] = new
        _w(cp, ("\n".join(json.dumps(x) for x in rows) + "\n").encode())
        ms = json.loads(_read_bytes(os.path.join(root, MANIFEST_S2[0])).decode("utf-8"))
        ms["checkpoint_sha256"] = sha256_file(cp)
        if update_manifest_s2_partial:
            ms["partial_sha256"][os.path.basename(pp)] = new
        _wj(os.path.join(root, MANIFEST_S2[0]), ms)
        E["manifest_s2"] = (MANIFEST_S2[0], sha256_file(os.path.join(root, MANIFEST_S2[0])))


def selftest_K4_delta(root, E, fx):
    R = _load_result(root, E)
    T = fx["T"]
    elig = np.arange(N_PT)
    worst = 0.0
    distinct = True
    for u in T["units"]:
        te = np.where(fx["folds"][u["r"]] == u["k"])[0]
        for t in T["seeds"]:
            a2 = macro_ap(fx["Y"][te], fx["P"][(u["r"], T["arm_hi"], t)], elig)["macro_ap"]
            a1 = macro_ap(fx["Y"][te], fx["P"][(u["r"], T["arm_lo"], t)], elig)["macro_ap"]
            got = R["cells"][cell_key(u, t)]["delta"]
            worst = max(worst, abs(got - (a2 - a1)))
            distinct &= abs(got - (a1 - a2)) > 1e-9
    exp_keys = {cell_key(u, t) for u in T["units"] for t in T["seeds"]}
    checks = {"delta_equals_macro_ap_diff_exact": worst == 0.0,
              "distinct_from_reversed_direction": distinct,
              "cell_keys_15": set(R["cells"]) == exp_keys and len(exp_keys) == 15,
              "contrast_label": R["contrast_definition"] == "%s − %s" % (T["arm_hi"], T["arm_lo"])}
    checks.update(selftest_K2b_orientation(root, E, fx))
    return _res("K4 Δ 정의", checks, max_abs_diff=worst, provenance=PROVENANCE_SYN)


def selftest_K5_ss(root, E, fx):
    R = _load_result(root, E)
    T = fx["T"]
    M = [[R["cells"][cell_key(u, t)]["delta"] for t in T["seeds"]] for u in T["units"]]
    direct = two_way_ss(M)
    got = dict(R["two_way_ss"])
    same = all(got[k] == direct[k] for k in direct if k not in ("provenance", "sst_zero_rule"))
    alt = two_way_ss(np.asarray(M).T.tolist())
    tree = _src_tree()
    par = _parents(tree)
    imported = any(isinstance(n, ast.ImportFrom) and n.module == "rqint_downstream"
                   and any(a.name == "two_way_ss" for a in n.names) for n in ast.walk(tree))
    calls = [_enclosing(par, n) for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "two_way_ss"]
    core_calls = [c for c in calls if not (c or "").startswith("selftest")]
    # 자체 SS 구현 0 — 비-selftest 함수에서 제곱합(** 2)·mean(axis) 연산 0
    pow2 = [_enclosing(par, n) for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow)]
    self_ss = [fn for fn in pow2 if not (fn or "").startswith("selftest")]
    means = [_enclosing(par, n) for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) in ("mean", "var", "std")]
    self_mean = [fn for fn in means if not (fn or "").startswith("selftest")]
    return _res("K5 SS", {
        "equals_direct_two_way_ss": same,
        "provenance_overwritten": got["provenance"] == "confirmatory_sealed",
        "orientation_distinct_from_transpose": abs(got["frac_unit"] - alt["frac_unit"]) > 1e-9
                                               and abs(direct["frac_unit"] - alt["frac_seed"]) < 1e-12,
        "two_way_ss_imported": imported,
        "two_way_ss_called_once_in_core": core_calls == ["_core_after_r2"],
        "no_self_ss_impl": not self_ss and not self_mean}, provenance=PROVENANCE_SYN)


def selftest_K6_undefined(tmp_root):
    from sklearn.metrics import average_precision_score
    tmp = os.path.join(tmp_root, "k6")
    os.makedirs(tmp)
    E, fx = _make_fixture(tmp, rng_seed=66, zero_cols=(0, 1))
    _o, exc = _run_quiet(tmp, E)
    if exc is not None:
        return _res("K6 undefined", {"run_ok": False}, error=type(exc).__name__)
    R = _load_result(tmp, E)
    T = fx["T"]
    u, t = T["units"][0], T["seeds"][0]
    te = np.where(fx["folds"][u["r"]] == u["k"])[0]
    def aps(P):
        return [average_precision_score(fx["Y"][te][:, j], P[:, j]) for j in range(2, N_PT)]
    a_hi, a_lo = aps(fx["P"][(u["r"], T["arm_hi"], t)]), aps(fx["P"][(u["r"], T["arm_lo"], t)])
    got = R["cells"][cell_key(u, t)]["delta"]
    var_den = float(np.mean(a_hi)) - float(np.mean(a_lo))
    zero_sub = float(np.sum(a_hi)) / N_PT - float(np.sum(a_lo)) / N_PT
    cells = list(R["cells"].values())
    return _res("K6 undefined", {"run_ok": True,
                                 "n_eval_368_all": all(c["n_eval"] == N_PT - 2 for c in cells),
                                 "n_excluded_2_all": all(c["n_excluded_undefined"] == 2 for c in cells),
                                 "n_eligible_370_all": all(c["n_eligible"] == N_PT for c in cells),
                                 "variable_denominator": abs(got - var_den) <= 1e-15,
                                 "no_zero_substitution": abs(got - zero_sub) > 1e-12},
                provenance=PROVENANCE_SYN)


def selftest_K7_invalid(tmp_root):
    results, msgs, vals = {}, [], []
    cases = ("a_conf_sha", "b_stab_manifest", "c_ckpt_sha", "d_cid_shuffle", "e_nan", "f_missing", "g_keys", "h_drop_cell")
    expect = {"a_conf_sha": RULE_SHA, "b_stab_manifest": RULE_SHA, "c_ckpt_sha": RULE_SHA, "d_cid_shuffle": RULE_ORDER,
              "e_nan": RULE_NONFINITE, "f_missing": RULE_MISSING, "g_keys": RULE_KEYS, "h_drop_cell": RULE_COUNT}
    for i, case in enumerate(cases):
        tmp = os.path.join(tmp_root, "k7_" + case)
        os.makedirs(tmp)
        E, fx = _make_fixture(tmp, rng_seed=700 + i)
        T = fx["T"]
        u = T["units"][1]
        tc, ts = T["conf_t"][1], T["stab_t"][0]
        acc0 = {p: _newlines(p) for p in glob.glob(os.path.join(tmp, _RUNS, "*", "_sealed", "access.log"))}
        fault = None
        if case == "a_conf_sha":
            _rewrite_partial_chain(tmp, E, T, u, T["arm_hi"], tc, update_chain=False,
                                   P_test=fx["P"][(u["r"], T["arm_hi"], tc)] * np.float32(0.5))
        elif case == "b_stab_manifest":
            _rewrite_partial_chain(tmp, E, T, u, T["arm_lo"], ts, update_manifest_s2_partial=False,
                                   P_test=fx["P"][(u["r"], T["arm_lo"], ts)] * np.float32(0.5))
        elif case == "c_ckpt_sha":
            cp = os.path.join(tmp, conf_tree(T, u), "_sealed", "checkpoint.jsonl")
            b = _read_bytes(cp)
            _w(cp, b.replace(b'"n_epochs": 10', b'"n_epochs": 11', 1))
        elif case == "d_cid_shuffle":
            for key in ("master_x", "master_y"):
                pth = os.path.join(tmp, E[key][0])
                df = pd.read_parquet(pth).iloc[::-1].reset_index(drop=True)
                df.to_parquet(pth)
                E[key] = (E[key][0], sha256_file(pth))
        elif case == "e_nan":
            P = fx["P"][(u["r"], T["arm_hi"], tc)].copy()
            P[1, 5] = np.nan
            _rewrite_partial_chain(tmp, E, T, u, T["arm_hi"], tc, P_test=P)
        elif case == "f_missing":
            os.remove(os.path.join(tmp, partial_rel(T, u, T["arm_lo"], tc)))
        elif case == "g_keys":
            _rewrite_partial_chain(tmp, E, T, u, T["arm_lo"], ts, extra=np.int32(1))
        else:
            fault = "drop_cell"
        out, exc = _run_quiet(tmp, E, fault=fault)
        msg = str(exc) if exc is not None else ""
        msgs.append(msg)
        results[case] = (isinstance(exc, InvalidRun) and exc.rule == expect[case]
                         and not os.path.exists(os.path.join(tmp, E["out_rel"])) and _no_decimal(msg))
    results["messages_no_decimal"] = all(_no_decimal(m) for m in msgs)
    return _res("K7 무효 8종", results), msgs


def selftest_K8_sst_zero(tmp_root):
    tmp = os.path.join(tmp_root, "k8")
    os.makedirs(tmp)
    E, fx = _make_fixture(tmp, rng_seed=88, equal_arms=True)
    _o, exc = _run_quiet(tmp, E)
    if exc is not None:
        return _res("K8 SST=0", {"run_ok": False}, error=type(exc).__name__)
    R = _load_result(tmp, E)
    S = R["two_way_ss"]
    spec_rule = json.loads(_read_bytes(os.path.join(ROOT, SPEC_PATH)).decode("utf-8"))["S6_stability_15cell_ss"]["sst_zero_rule"]
    return _res("K8 SST=0", {
        "run_ok": True, "all_delta_exact_zero": all(c["delta"] == 0.0 for c in R["cells"].values()),
        "sst_zero_true": S["sst_zero"] is True,
        "frac_not_defined": all(S[k] == "not_defined" for k in ("frac_unit", "frac_seed", "frac_res")),
        "sst_zero_rule_spec_verbatim": S["sst_zero_rule"] == spec_rule,
        "module_sst_zero_rule_present": isinstance(R.get("module_sst_zero_rule"), str) and R["module_sst_zero_rule"] != spec_rule,
        "provenance_confirmatory_sealed": S["provenance"] == "confirmatory_sealed" == R["provenance"],
        "module_provenance_constant": R["module_provenance_constant"] == PROVENANCE_SYN}, provenance=PROVENANCE_SYN)


def selftest_K9_atomic(tmp_root, base_root, base_E, acc_before, acc_after):
    tmp = os.path.join(tmp_root, "k9_pre")
    os.makedirs(tmp)
    E, fx = _make_fixture(tmp, rng_seed=99)
    os.makedirs(os.path.join(tmp, E["out_rel"], "_sealed"))
    accs = glob.glob(os.path.join(tmp, _RUNS, "*", "_sealed", "access.log"))
    b = {p: _newlines(p) for p in accs}
    _o, exc = _run_quiet(tmp, E)
    a = {p: _newlines(p) for p in accs}
    out = os.path.join(base_root, base_E["out_rel"])
    tmp_left = [p for p in glob.glob(os.path.join(out, "**", "*"), recursive=True) if p.endswith(".tmp")]
    new_acc = _newlines(os.path.join(out, "_sealed", "access.log"))
    nf = []
    for p in sorted(acc_after):
        last = json.loads(_read_bytes(p).decode("utf-8").splitlines()[-1])
        nf.append(last.get("n_files"))
    T = load_terms(base_root, base_E)
    exp_nf = sorted([1 + len(T["arms"]) * len(T["conf_t"])] * len(T["units"])
                    + [1 + len(T["units"]) * len(T["arms"]) * len(T["stab_t"])])
    return _res("K9 덮어쓰기 금지·원자성", {
        "preexisting_output_aborts": isinstance(exc, HarnessAbort),
        "preexisting_abort_before_r2": a == b,
        "no_tmp_left": not tmp_left,
        "tree_access_log_plus_one": len(acc_before) == 4 and all(acc_after[p] == acc_before[p] + 1 for p in acc_before),
        "new_access_log_one_line": new_acc == 1,
        "sealed_names": sorted(os.listdir(os.path.join(out, "_sealed"))) == ["access.log", "ss15_result.json"],
        "n_files_7_7_7_13": sorted(nf) == exp_nf == [7, 7, 7, 13]})


def selftest_K10_leak(base_root, base_E, base_stdout, exc_msgs):
    R = _load_result(base_root, base_E)
    S = R["two_way_ss"]
    vals = [c["delta"] for c in R["cells"].values()]
    vals += [S[k] for k in ("grand_mean", "SST", "SS_unit", "SS_seed", "SS_res", "frac_unit", "frac_seed", "frac_res")]
    vals += list(S["unit_seed_mean"]) + list(S["unit_seed_sd"]) + list(S["unit_seed_range"])
    pats = set()
    for v in vals:
        pats |= {repr(v), "%.4f" % v, "%.6f" % v, "%.4f" % abs(v), "%.6f" % abs(v)}
    out = os.path.join(base_root, base_E["out_rel"])
    pub_txt = _read_bytes(os.path.join(out, "manifest_public.json")).decode("utf-8")
    runlog = _read_bytes(os.path.join(out, "run.log")).decode("utf-8")
    texts = {"stdout": base_stdout, "run.log": runlog, "manifest_public": pub_txt, "exceptions": "\n".join(exc_msgs)}
    hits = {k: sorted(p for p in pats if p in txt) for k, txt in texts.items()}
    pub = json.loads(pub_txt)
    whitelist = (set(pub) == PUBLIC_TOP_KEYS and all(set(f) == PUBLIC_FILE_KEYS for f in pub["sealed_files"])
                 and set(pub["input_checks"]) == PUBLIC_CHECK_KEYS
                 and set(pub["sealed_counts_start"]) == set(pub["sealed_counts_end"]) == PUBLIC_COUNT_KEYS)
    new_objs = [R, pub, json.loads(_read_bytes(os.path.join(out, "_sealed", "access.log")))]
    for p in glob.glob(os.path.join(base_root, _RUNS, "*", "_sealed", "access.log")):
        new_objs.append(json.loads(_read_bytes(p).decode("utf-8").splitlines()[-1]))
    bad = sorted({k for o in new_objs for k in _keys_recursive(o) for w in FORBIDDEN_KEY_SUBSTR if w in k})
    return _res("K10 누설 가드", {"nondegenerate_fixture": S["sst_zero"] is False,
                                  "value_strings_absent": not any(hits.values()),
                                  "public_keys_whitelist_exact": whitelist,
                                  "new_file_keys_no_sign_words": not bad},
                n_patterns=len(pats), hits={k: len(v) for k, v in hits.items()}, bad_keys=bad)


def selftest_K11_ast():
    tree = _src_tree()
    forbidden = ("emit_sign", "open_sealed", "rqint_test", "observed_statistic", "rq2_decision", "rq3_decision",
                 "rq4_decision", "holm", "paired_scaffold_bootstrap", "sign")
    hits = [(_call_name(n), n.lineno) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and _call_name(n) in forbidden]
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    stats = sorted(imported & {"scipy", "statsmodels", "pingouin"})
    net = sorted(imported & {"socket", "urllib", "requests", "http", "ftplib", "smtplib", "asyncio",
                             "aiohttp", "httpx", "telnetlib"})
    environ = [n.lineno for n in ast.walk(tree)
               if (isinstance(n, ast.Attribute) and n.attr == "environ")
               or (isinstance(n, ast.Call) and _call_name(n) == "getenv")]
    opts = {a.value for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "add_argument"
            for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    held = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Return, ast.NamedExpr)):
            v = getattr(n, "value", None)
            tg = getattr(n, "targets", None) or ([n.target] if hasattr(n, "target") else [])
            for sub in ([v] if v is not None else []) + list(tg):
                for x in ast.walk(sub):
                    if isinstance(x, ast.Subscript) and isinstance(x.slice, ast.Constant) \
                            and x.slice.value in ("best_ep", "best_v"):
                        held.append(n.lineno)
                    if isinstance(x, ast.Name) and x.id in ("best_ep", "best_v"):
                        held.append(n.lineno)
    return _res("K11 AST", {"forbidden_calls_zero": not hits, "stat_test_imports_zero": not stats,
                            "network_imports_zero": not net, "os_environ_zero": not environ,
                            "cli_options_exact": opts == {"--stage", "--out"},
                            "best_ep_best_v_not_held": not held},
                forbidden_hits=hits, held_lines=sorted(set(held)))


@contextlib.contextmanager
def _write_guard(allowed_dirs, violations):
    allowed = [os.path.realpath(d) for d in allowed_dirs]

    def ok(p):
        if hasattr(p, "name"):
            p = p.name
        if isinstance(p, int):
            return True
        rp = os.path.realpath(os.fspath(p))
        return any(rp == a or rp.startswith(a + os.sep) for a in allowed)

    orig = {"open": builtins.open, "replace": os.replace, "makedirs": os.makedirs, "mkdir": os.mkdir,
            "remove": os.remove}

    def g_open(file, mode="r", *a, **k):
        if any(c in mode for c in "wax+") and not ok(file):
            violations.append(("open", str(file)))
            raise PermissionError("selftest write guard")
        return orig["open"](file, mode, *a, **k)

    def wrap(name, nargs=1):
        def f(*a, **k):
            for p in a[:nargs]:
                if not ok(p):
                    violations.append((name, str(p)))
                    raise PermissionError("selftest write guard")
            return orig[name](*a, **k)
        return f

    builtins.open = g_open
    os.replace, os.makedirs, os.mkdir, os.remove = wrap("replace", 2), wrap("makedirs"), wrap("mkdir"), wrap("remove")
    try:
        yield
    finally:
        builtins.open = orig["open"]
        os.replace, os.makedirs, os.mkdir, os.remove = orig["replace"], orig["makedirs"], orig["mkdir"], orig["remove"]


def _real_state():
    fps = sealed_fingerprints(ROOT, GROUP_PREFIXES)
    return {"counts": sealed_counts(ROOT), "fp7": {g: fps[g][0] for g in FP_STAT},
            "ss15": len(glob.glob(os.path.join(ROOT, OUT_GLOB))), "pycache": _pycache_dirs(ROOT)}


def selftest_K12_hygiene(violations, cl_calls, before):
    tree = _src_tree()
    par = _parents(tree)
    # 보조 AST: core 계열 쓰기 헬퍼의 경로 인자는 root 에서 파생된 이름(out_dir·sealed_out·path)뿐
    write_fns = {"_append_line", "_atomic_bytes", "_mkdir_new"}
    core_fns = {"core", "_core_after_r2"}
    assigns = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and _enclosing(par, n) in core_fns:
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    assigns.setdefault(tg.id, []).append(n.value)
        elif isinstance(n, ast.For) and _enclosing(par, n) in core_fns:
            for x in ast.walk(n.target):
                if isinstance(x, ast.Name):
                    assigns.setdefault(x.id, []).append(n.iter)
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _call_name(n) in write_fns and _enclosing(par, n) in core_fns:
            arg = n.args[0]
            names = {x.id for x in ast.walk(arg) if isinstance(x, ast.Name)}
            roots, frontier = set(), set(names)
            for _ in range(3):                      # 이름 → 대입식 → 이름 (최대 3단)
                nxt = set()
                for nm in frontier:
                    for v in assigns.get(nm, []):
                        nxt |= {x.id for x in ast.walk(v) if isinstance(x, ast.Name)}
                roots |= nxt
                frontier = nxt
            if not ({"root", "out_dir", "sealed_out"} & (names | roots)):
                bad.append(n.lineno)
    cl_outside = {_enclosing(par, n) for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "cl"}
    after = _real_state()
    return _res("K12 위생", {
        "runtime_write_guard_violations_zero": not violations,
        "core_write_paths_root_derived": not bad,
        "cl_calls_only_in_stage_run": cl_outside == {"stage_run"},
        "cl_calls_during_selftest_zero": cl_calls["n"] == 0,
        "real_sealed_counts_unchanged": after["counts"] == before["counts"] == EXPECTED_SEALED_BEFORE,
        "real_fp7_unchanged": after["fp7"] == before["fp7"] == FP_STAT,
        "ss15_dir_not_created": after["ss15"] == before["ss15"] == 0,
        "pycache_unchanged": after["pycache"] == before["pycache"]},
        bad_write_lines=bad, guard_violations=violations[:5])


def selftest_K13_gate(tmp_root):
    res, msgs = {}, []

    def attempt(tag, mutate, expect_pass):
        tmp = os.path.join(tmp_root, "k13_" + tag)
        os.makedirs(tmp)
        E, fx = _make_fixture(tmp, n=30, rng_seed=1300 + len(res))
        mutate(tmp, E, fx)
        try:
            gate(tmp, E)
            passed, msg = True, ""
        except GateFail as e:
            passed, msg = False, str(e)
        msgs.append(msg)
        res[tag] = (passed == expect_pass) and _no_decimal(msg)

    def m_docs_last(tmp, E, fx):
        p = os.path.join(tmp, DOCS33)
        _w(p, _read_bytes(p) + b"\n75. **later**:\nx\n")

    def m_docs_sha(tmp, E, fx):
        _w(os.path.join(tmp, DOCS33), b"73. **a**:\nx\n\n74. **b**:\nno sha here\n")

    def m_selftest_dir(tmp, E, fx):
        os.makedirs(os.path.join(tmp, os.path.dirname(SELFTEST_OUT)), exist_ok=True)

    def m_out_dir(tmp, E, fx):
        os.makedirs(os.path.join(tmp, OUT_REL))

    def m_fp(tmp, E, fx):
        _w(os.path.join(tmp, GROUP_PREFIXES["leverage"][0], "_sealed", "x.bin"), b"xxx")
        E["sealed_before"] = sealed_counts(tmp)

    def m_holm(tmp, E, fx):
        _wj(os.path.join(tmp, HOLM8_TS[0]), {"completed": False, "ts_completed_kst": HOLM8_TS[1]})

    attempt("a_normal_pass", lambda *_: None, True)
    attempt("b_docs33_last_not_74_fail", m_docs_last, False)
    attempt("c_item74_no_sha_fail", m_docs_sha, False)
    attempt("d_selftest_dir_exists_pass", m_selftest_dir, True)
    attempt("e_out_dir_exists_fail", m_out_dir, False)
    attempt("f_fp_mismatch_fail", m_fp, False)
    attempt("g_holm8_incomplete_fail", m_holm, False)
    return _res("K13 gate", res), msgs


def run_selftest():
    before = _real_state()
    cl_calls = {"n": 0}
    orig_cl = {k: getattr(cl, k) for k in ("gate_a_load", "gate_b_exclusive", "gate_c_settle", "ComputeLock")}

    def _cl_trap(*_a, **_k):
        cl_calls["n"] += 1
        raise RuntimeError("cl 호출 금지(selftest)")

    for k in orig_cl:
        setattr(cl, k, _cl_trap)
    tmp = tempfile.mkdtemp(prefix="ba_selftest_")
    violations = []
    results = []
    try:
        with _write_guard([tmp], violations):
            results.append(selftest_K1_constants())
            results.append(selftest_K2_spec_binding())
            base = os.path.join(tmp, "base")
            os.makedirs(base)
            base_E, fx = _make_fixture(base, rng_seed=20261004)
            accs = [os.path.join(base, conf_tree(fx["T"], u), "_sealed", "access.log") for u in fx["T"]["units"]]
            accs.append(os.path.join(base, stab_tree(fx["T"]), "_sealed", "access.log"))
            acc_before = {p: _newlines(p) for p in accs}
            base_stdout, base_exc = _run_quiet(base, base_E)
            if base_exc is not None:
                raise RuntimeError("base fixture run 실패: %s %s" % (type(base_exc).__name__, base_exc))
            acc_after = {p: _newlines(p) for p in accs}
            r3, m3 = selftest_K3_fold_rows(tmp)
            results.append(r3)
            results.append(selftest_K4_delta(base, base_E, fx))
            results.append(selftest_K5_ss(base, base_E, fx))
            results.append(selftest_K6_undefined(tmp))
            r7, m7 = selftest_K7_invalid(tmp)
            results.append(r7)
            results.append(selftest_K8_sst_zero(tmp))
            results.append(selftest_K9_atomic(tmp, base, base_E, acc_before, acc_after))
            results.append(selftest_K10_leak(base, base_E, base_stdout, m3 + m7))
            results.append(selftest_K11_ast())
            r13, _m13 = selftest_K13_gate(tmp)
    finally:
        for k, v in orig_cl.items():
            setattr(cl, k, v)
        shutil.rmtree(tmp, ignore_errors=True)
    results.append(selftest_K12_hygiene(violations, cl_calls, before))
    results.append(r13)
    n_pass = sum(1 for r in results if r["pass"])
    return {
        "_doc": "docs/116 블록 BA / BA-3 — 합성 자체검사 K1~K13. 확증 입력 판독 0. 모든 수치는 합성 fixture 산출물.",
        "provenance": PROVENANCE_SYN, "block": "BA (docs/116)",
        "harness_path": "v3_Multimodal/src/stability_ss15_run.py",
        "harness_sha256": sha256_file(os.path.abspath(__file__)),
        "spec_path": SPEC_PATH, "spec_sha256": SPEC_SHA256,
        "implementation_module_path": MODULE_PATH, "implementation_module_sha256": MODULE_SHA256,
        "python": platform.python_version(), "numpy": np.__version__,
        "ts_kst": now_kst(), "n_tests": len(results), "n_pass": n_pass, "n_skip": 0,
        "all_pass": n_pass == len(results) == 13,
        "tests": results, "confirmatory_values_read": 0, "sealed_human_read": 0, "network_calls": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="블록 BA — 안정성 15셀 fold 수준 Δ + 서술적 two-way SS 봉인 산출")
    ap.add_argument("--stage", choices=["selftest", "run"], default="selftest")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.stage == "run":
        if a.out:
            raise SystemExit("--out 은 selftest 전용")
        return stage_run()
    if a.out and os.path.abspath(a.out) != os.path.join(ROOT, SELFTEST_OUT):
        raise SystemExit("--out 은 SELFTEST_OUT 만 허용")
    res = run_selftest()
    os.makedirs(os.path.dirname(os.path.join(ROOT, SELFTEST_OUT)), exist_ok=True)
    with open(os.path.join(ROOT, SELFTEST_OUT), "w", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"stage": "selftest", "all_pass": res["all_pass"], "n_pass": res["n_pass"],
                      "n_tests": res["n_tests"], "fails": {t["name"]: t["fails"] for t in res["tests"] if not t["pass"]}},
                     ensure_ascii=False))
    return 0 if res["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
