"""rqint_leverage_d11.py — 블록 AX (docs/114): D11 레버리지 진단 λ·ρ 봉인 산출 (명세 S2 실행).

동결 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json` 의 **S2_d11_leverage 를 그대로 구현**한다.
k 값·입력 행렬 수·군 수 G·봉인 파일명은 명세 JSON 에서 읽는다(하네스에 재기술 0).
계산 = `rqint_downstream.leverage_profile` · `leverage_profile_verbatim` · `lambda_k` · `rho` 를 import 해
그대로 호출(재구현 0). scaffold 군 = `confirmatory_oof_rep1.scaffold_of`(F-SCAF 재사용) + `sorted(set)` 순서.

⛔ 무결성 (docs/114 §2)
  · λ·ρ 는 **게이트가 아니다**(보고·주석용). 산출값은 전부 `_sealed/leverage_diagnostics.json` 에만 봉인한다.
  · 봉인 «값» 은 `run` stage 안에서만 기계 판독한다. stdout·run.log·manifest_public·예외 메시지에
    e_g·λ·ρ·T_obs·Δ 등 값을 **내보내지 않는다.** 부호를 산출하지 않는다(부호 비교 연산 0).
  · p 계산 0 — `rqint_test`·`holm`·`paired_scaffold_bootstrap`·판정 함수·`emit_sign`·`open_sealed` 호출 0.
  · `rqint_downstream` 의 selftest·main 호출 0(함수 import 만). 네트워크 0 · os.environ 판독 0.

구조 (블록 AW 와 동일)
  stage_run()  = R0 게이트 + compute_lock 만 담당 → core(paths) 호출.
  core(paths)  = R1~R7. 모든 경로를 인자로 받는다. selftest 는 core 만 호출한다(cl.* 호출 0).
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
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── 동결 입력 상수 ───────────────────────────────────────────────────────────
SPEC_PATH = "v3_Multimodal/config/rqint_downstream_spec_v1.json"
SPEC_SHA256 = "fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf"
AMEND_PATH = "v3_Multimodal/config/rqint_downstream_spec_v1_amendment1.json"
AMEND_SHA256 = "63c29d6b6a9e22951f2e2891b54f4251d5e4f679fc1d3b3f110cfdf510aab05c"
DOCS33 = "docs/33_prereg_deviation_log.md"
ITEM67_RE = r"(?m)^67\. \*\*ChatGPT 8차 리뷰 반영"
MASTER_X = ("data/processed/master_X.parquet",
            "788c8a64d19e8c3cc030476e7b2eb7f207246e3af6e73304d97f2fc9aa2ae6e6")
MASTER_Y = ("data/processed/master_Y.parquet",
            "bd23584342de6482e50f218bd409740acc2a00eeac86ee95bd89952bc3d18018")
# import 전 파일 sha 검증 대상 (L1)
PRE_IMPORT_SHA = {
    "v3_Multimodal/src/sap/consensus.py": "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91",
    "v3_Multimodal/src/sap/metrics.py": "a7d3fe4fe9e87983b35b086b0c464bde1e710e013f98813a2f28a2b48c8b2004",
    "v3_Multimodal/src/sap/rqint.py": "eb842bc98140e9c55b67bc1563cd5573c3b294885778f23744468b712c498b26",
    "v3_Multimodal/src/sap/decision.py": "f688b20d816acabe17c2906cfa846c1f794ba45a416248c08aa7e41676e82a92",
    "v3_Multimodal/src/sap/redaction.py": "4d4bf221141fbc793a2bc9c9989906a5c072d7f3e0e49be495cf79d67a5b580c",
    "v3_Multimodal/src/rqint_downstream.py": "3e92a4ded1ea60b777c460b1b120232ae3051fe3a80e2e7c4f12d943c92ea680",
    "v3_Multimodal/src/confirmatory_oof_rep1.py": "afb894c09fdaad6f1c75df789c5e2ede1dbbc2151a8c30b8eda6044cd6f336b6",
    "v3_Multimodal/src/ladder_confirmatory.py": "13a17129db6a6679bd6dbdc28a12c0f31e2e8d6b0811130450add602daf5137c",
    "v3_Multimodal/src/compute_lock.py": "b03a0b0012948b340f410670d6b045f279e1b21b4faa293bb45bbc2e99a6d738",
}
# 입력 행렬 (정본: GIN = consensus manifest_public · RF = first_look_log.json 인덱스 6)
GIN_CONS_DIR = "experiments/runs/v3_gin_confirm_consensus_rep123"
GIN_MANIFEST_PUBLIC_SHA256 = "768f7267bf8c033ccb3830838e7501d18605fb19d2630061723bafebd7a259dd"
GIN_SHA = {
    "consensus_M1b_seed42.npz": "9b5f16ac16c1d857f89291ebec21e2ea15e287d07edd784089db39521973a025",
    "consensus_M1b_seed1.npz": "1bdf93519825873936762d4fe9c4b8e16ab67a543a2921b807ae686a4ae9cf29",
    "consensus_M1b_seed2.npz": "32a5f1bc701e2f102d0726dfaefa86e9ca862ec316ba6964a25bf0494b642425",
    "consensus_M2b_seed42.npz": "b36ff282b410295bb7170ee2f87c3574d0046765c15ee1c76ba62b4a26c1df5b",
    "consensus_M2b_seed1.npz": "9ae11e2d072da87b18b7c5458f9f0b4414600d22179ce674898303b1bc4ebd28",
    "consensus_M2b_seed2.npz": "03a0db458b4d4f4808041f1610e0870b57acaaf5996a5a20b584b82043674265",
    "metrics_full.json": "f08ba2307146160f1548684cb56a47dc49ae84ba653950931fc9c144746f2091",
}
RF_CONS_DIR = "experiments/runs/v3_consensus_rep123"
FIRST_LOOK_LOG = "experiments/provenance/first_look_log.json"
FIRST_LOOK_RF_INDEX = 6
RF_SHA = {
    "consensus_M1b.npz": "f77a69528ebdb88cd0d03c0c87489d6381740e3b9f9746378cc0396618ebfa96",
    "consensus_M2b.npz": "8594592e2afae5835f43be63d6bdc815a6933d25388b9c3c4091637117c435bf",
}
FLAG_FILES = ("v3_Multimodal/config/rqint_procedure_decisions_v1.json",
              "v3_Multimodal/config/gin_seed_freeze.json", "v3_Multimodal/config/gin_inner_valid_freeze.json")
UNBLIND_FILES = ("v3_Multimodal/config/post_interim_freeze_v1_0.status.json",
                 "v3_Multimodal/config/gin_train_contract.json",
                 "experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json")

EXPECTED_SEALED_BEFORE = {"n_sealed_dirs": 30, "n_sealed_files_total": 750,
                          "n_sealed_artifacts": 729, "n_access_log": 21}
EXPECTED_SEALED_AFTER = {"n_sealed_dirs": 31, "n_sealed_files_total": 752,
                         "n_sealed_artifacts": 730, "n_access_log": 22}
CONF_PREFIXES = ["experiments/runs/v3_gin_confirm_rep1_seed201", "experiments/runs/v3_gin_confirm_rep2_seed202",
                 "experiments/runs/v3_gin_confirm_rep3_seed203"]
STABILITY_PREFIX = "experiments/runs/v3_gin_stability"
FP_CONFIRMATORY = "6ed86c86830b664916c80c13fc2b0f355528c963df5b66e9053184316e51a8b9"
FP_STABILITY = "b4b493d265824709a242a12d37334659bf78a75bd51a46f8b0174f058d6e6cec"
FP_EXISTING25 = "8cf3d207a42ed7c247e9de62931f003a075cdc6ac440794c7153cea49c54d1c9"
FP_GIN_CONSENSUS = "66cf4290bf33c9880dfe0e91f440923081cd2a2a6fd3af76346b69e3905f56bf"
OUT_REL = "experiments/runs/v3_rqint_leverage_d11"
LEVERAGE_GLOB = "experiments/runs/v3_rqint_leverage_d11*"
SELFTEST_OUT = "experiments/runs/v3_rqint_leverage_harness_selftest/selftest_leverage.json"
PROVENANCE_RUN = "confirmatory_sealed"
PROVENANCE_SYN = "synthetic_fixture"

N_PT = 370
N_DRUGS = 1092
TOL_DERIVED_VS_VERBATIM = 1e-12
TOL_MONOTONE = 1e-12
FORBIDDEN_KEY_SUBSTR_SEALED = ("sign", "direction", "positive", "negative")
FORBIDDEN_KEY_SUBSTR_PUBLIC = ("macro_ap", "delta", "e_g", "e_profile", "lambda", "rho", "t_obs", "top_",
                               "denom", "p_value", "sign", "direction", "positive", "negative")
KST = datetime.timezone(datetime.timedelta(hours=9))


# ═══════════════════════════════════════════════════════════════════════════
# 공용 유틸
# ═══════════════════════════════════════════════════════════════════════════
def now_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _abs(rel):
    return os.path.join(ROOT, rel)


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class InvalidRun(Exception):
    """무효 규칙(값 무관) 발동. 메시지 = 규칙 이름 + 위치뿐(값 0)."""

    def __init__(self, rule, where=""):
        self.rule = rule
        super().__init__("[무효] %s :: %s" % (rule, where))


class HarnessAbort(Exception):
    """게이트·구조 결함(값 무관)."""


# S2 invalidation_rules 3종 + 구현 무결성 검사 보충 4종(docs/33 항목 67 ② 사전 기록)
RULE_SHA = "입력 sha 불일치"
RULE_ORDER = "행 순서/cid 불일치"
RULE_NONFINITE = "비유한 값"
RULE_G = "군 수 G 불일치"
RULE_NMATS = "행렬 수 불일치"
RULE_VERBATIM = "도출↔축자 불일치"
RULE_CROSS113 = "113 교차 비트 불일치"


def _verify_then_import():
    for rel, sha in PRE_IMPORT_SHA.items():
        if sha256_file(_abs(rel)) != sha:
            raise HarnessAbort("import 전 sha 불일치: " + rel)


_verify_then_import()
from sap import rqint as sap_rqint                     # noqa: E402  _EPS 확인·합성 대조용
import rqint_downstream as rd                          # noqa: E402  함수 4개만 사용
from confirmatory_oof_rep1 import scaffold_of          # noqa: E402  F-SCAF 재사용
import compute_lock as cl                              # noqa: E402


def load_spec():
    b = _read_bytes(_abs(SPEC_PATH))
    if sha256_bytes(b) != SPEC_SHA256:
        raise HarnessAbort("명세 sha 불일치")
    return json.loads(b.decode("utf-8"))


def spec_terms(spec):
    """명세 S1·S2 에서 k·입력 수·G·봉인 파일명·arm·s↔t·GIN 파일 패턴을 읽는다(재기술 0)."""
    s1, s2 = spec["S1_metrics_contract"], spec["S2_d11_leverage"]
    m = re.match(r"\s*(\S+)\s*−\s*(\S+)", s1["cells_frozen_here_no_additions_later"]["delta_direction"])
    hi, lo = m.group(1), m.group(2)
    s_to_t = {int(k): int(v) for k, v in s1["notation_freeze"]["s_is_order_index"].items()}
    return {"k_values": tuple(int(k) for k in s2["lambda_k"]["k_values"]),
            "n_mats": int(s2["inputs"]["consensus_matrices"]),
            "G": int(s2["inputs"]["scaffold_group"]),
            "sealed_name": s2["outputs"]["sealed"],
            "arms": (lo, hi), "s_to_t": s_to_t, "seeds": sorted(s_to_t),
            "gin_file": s1["outputs"]["consensus_files"].split("/", 1)[1],
            "gin_metrics": s1["outputs"]["metrics"].split("/", 1)[1],
            "is_gate": s2["is_gate"], "purpose_verbatim": s2["purpose_verbatim"],
            "T_k_rule": s2["lambda_k"]["T_k"]}


def build_mats(loaded, T):
    """로드한 consensus 로 `sap.rqint` 규약의 mats 를 구성한다. GIN 키 s = 순서 인덱스(학습 시드 t 아님)."""
    lo, hi = T["arms"]
    mats = {}
    for arm in (lo, hi):
        mats[("RF", None, arm)] = loaded[("RF", None, arm)]
        for s in T["seeds"]:
            mats[("GIN", s, arm)] = loaded[("GIN", T["s_to_t"][s], arm)]
    return mats


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


def _keys_recursive(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _keys_recursive(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys_recursive(v)


def _bad_keys(obj, words, exempt_count_keys=False):
    return sorted({k for k in _keys_recursive(obj) for w in words
                   if w in k and not (exempt_count_keys and k.startswith("n_"))})


def _assert_no_key_substr(obj, words, what, exempt_count_keys=False):
    bad = _bad_keys(obj, words, exempt_count_keys)
    if bad:
        raise HarnessAbort("금지 키 부분문자열(%s): %s" % (what, ",".join(bad)))


# ── 봉인 stat (파일을 열지 않는다) ──────────────────────────────────────────
def sealed_counts(root):
    dirs = files = acc = 0
    for dp, _dn, fn in os.walk(root):
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


def sealed_fingerprint(root, prefixes, exclude=False):
    lines = []
    for dp, _dn, fn in os.walk(root):
        parts = dp.split(os.sep)
        if ".git" in parts or "_sealed" not in parts:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            hit = any(rel.startswith(pre + os.sep) for pre in prefixes)
            if hit != exclude:
                lines.append("%s\t%d" % (rel, os.path.getsize(p)))
    lines.sort()
    return sha256_bytes(("\n".join(lines) + "\n").encode("utf-8")), len(lines)


def fingerprints(root):
    return {"conf": sealed_fingerprint(root, CONF_PREFIXES)[0],
            "stab": sealed_fingerprint(root, [STABILITY_PREFIX])[0],
            "old25": sealed_fingerprint(root, CONF_PREFIXES + [STABILITY_PREFIX, GIN_CONS_DIR, OUT_REL],
                                        exclude=True)[0],
            "gincons": sealed_fingerprint(root, [GIN_CONS_DIR])[0]}


def _pycache_dirs(root):
    return sum(1 for dp, _dn, _fn in os.walk(root)
               if ".git" not in dp.split(os.sep) and os.path.basename(dp) == "__pycache__")


# ═══════════════════════════════════════════════════════════════════════════
# core — R1~R7 (모든 경로를 인자로 받는다)
# ═══════════════════════════════════════════════════════════════════════════
def core(paths, fault=None):
    """paths = {root, out_dir, master_x, master_y, master_sha{x,y}, n_rows_expected, n_groups_expected,
               rf_dir, gin_dir, input_sha{name: sha}, spec, provenance, public_meta{}}."""
    t_start = time.perf_counter()
    T = spec_terms(paths["spec"])
    out_dir = paths["out_dir"]
    sealed_out = os.path.join(out_dir, "_sealed")
    log = []

    def step(tag, msg):
        line = "%s\t%s\t%s" % (now_kst(), tag, msg)
        log.append(line)
        print(line, flush=True)

    if os.path.exists(out_dir):
        raise HarnessAbort("출력 디렉터리 선존재 — 덮어쓰기 금지: " + os.path.basename(out_dir.rstrip(os.sep)))
    counts_start = sealed_counts(paths["root"])
    step("R0", "core start · sealed dirs/files/artifacts/access = %d/%d/%d/%d" % tuple(counts_start.values()))

    # ── R1 설계량 (라벨·scaffold 군) ──
    bx, by = _read_bytes(paths["master_x"]), _read_bytes(paths["master_y"])
    if sha256_bytes(bx) != paths["master_sha"]["x"] or sha256_bytes(by) != paths["master_sha"]["y"]:
        raise InvalidRun(RULE_SHA, "master_X/master_Y")
    X = pd.read_parquet(io.BytesIO(bx))
    Y = pd.read_parquet(io.BytesIO(by))
    if list(X["cid"]) != list(Y["cid"]):
        raise InvalidRun(RULE_ORDER, "master_X/master_Y cid")
    cid_list = X["cid"].astype(int).tolist()
    if cid_list != sorted(cid_list):
        raise InvalidRun(RULE_ORDER, "master_X cid 미정렬")
    ycols = [c for c in Y.columns if c != "cid"]
    y = Y[ycols].values.astype(int)                      # 블록 AW 하네스 L312 와 축자 동일
    cid_order = np.asarray(cid_list, dtype=np.int64)
    n_rows = int(paths["n_rows_expected"])
    if y.shape != (n_rows, N_PT):
        raise InvalidRun(RULE_ORDER, "라벨 shape")
    scaf = [scaffold_of(s) for s in X["smiles_canonical"].tolist()]      # F-SCAF 재사용
    uniq = sorted(set(scaf))
    idx = {g: i for i, g in enumerate(uniq)}
    gi = np.array([idx[s] for s in scaf], dtype=int)
    if len(uniq) != int(paths["n_groups_expected"]):
        raise InvalidRun(RULE_G, "scaffold 군 수")
    n_g = np.bincount(gi, minlength=len(uniq))
    step("R1", "design · rows %d · PT %d · groups %d" % (y.shape[0], y.shape[1], len(uniq)))

    # ── 입력 파일 존재·개수 (행렬 수) ──
    lo, hi = T["arms"]
    plan = []
    for arm in (lo, hi):
        plan.append((("RF", None, arm), os.path.join(paths["rf_dir"], "consensus_%s.npz" % arm)))
        for s in T["seeds"]:
            t = T["s_to_t"][s]
            plan.append((("GIN", t, arm), os.path.join(paths["gin_dir"], T["gin_file"].format(model=arm, t=t))))
    if len(plan) != T["n_mats"] or not all(os.path.exists(p) for _k, p in plan):
        raise InvalidRun(RULE_NMATS, "consensus 행렬")
    mpath = os.path.join(paths["gin_dir"], T["gin_metrics"])
    if not os.path.exists(mpath):
        raise InvalidRun(RULE_SHA, "metrics_full 부재")

    # ── R2 판독 기록(먼저 쓴다) ──
    gin_names = ",".join(os.path.splitext(os.path.basename(p))[0] for k, p in plan if k[0] == "GIN")
    rf_names = ",".join(k[2] for k, _p in plan if k[0] == "RF")
    for d, pth in ((paths["rf_dir"], "_sealed/consensus_{%s}.npz" % rf_names),
                   (paths["gin_dir"], "_sealed/{%s}.npz + _sealed/%s" % (gin_names, T["gin_metrics"]))):
        _append_line(os.path.join(d, "access.log"), {
            "ts_kst": now_kst(), "type": "machine_read", "purpose": "D11 leverage input",
            "human_exposure": False, "path": pth, "actor": "vscode-claude",
            "step": "블록 AX(docs/114) R3 입력 판독",
            "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."})
    step("R2", "access.log +1 line · RF consensus 1 · GIN consensus 1")

    try:
        return _core_after_r2(paths, fault, T, plan, mpath, y, cid_order, n_rows, uniq, gi, n_g,
                              counts_start, sealed_out, out_dir, log, step, t_start)
    except (InvalidRun, HarnessAbort):
        raise
    except Exception as e:           # 값 누설 방지 — 예외 메시지를 버리고 형식만 남긴다
        raise HarnessAbort("R2 이후 예외(메시지 비공개): " + type(e).__name__) from None


def _core_after_r2(paths, fault, T, plan, mpath, y, cid_order, n_rows, uniq, gi, n_g,
                   counts_start, sealed_out, out_dir, log, step, t_start):
    # ── R3 입력 판독·검증 ──
    loaded, in_sha, rf_dtype = {}, {}, {}
    for key, p in plan:
        name = os.path.basename(p)
        b = _read_bytes(p)
        if sha256_bytes(b) != paths["input_sha"][name]:
            raise InvalidRun(RULE_SHA, name)
        with np.load(io.BytesIO(b)) as z:
            if set(z.files) != {"consensus", "cid"}:
                raise InvalidRun(RULE_SHA, name + " 키 집합")
            C, cid = z["consensus"], z["cid"]
        if C.shape != (n_rows, N_PT):
            raise InvalidRun(RULE_ORDER, name + " shape")
        if not bool(np.isfinite(C).all()):
            raise InvalidRun(RULE_NONFINITE, name)
        if not np.array_equal(np.asarray(cid, dtype=np.int64), cid_order):
            raise InvalidRun(RULE_ORDER, name + " cid")
        if key[0] == "RF":
            rf_dtype[name] = str(C.dtype)
        loaded[key] = C.astype(np.float64)
        in_sha[("rf/" if key[0] == "RF" else "gin/") + name] = sha256_bytes(b)
    mb = _read_bytes(mpath)
    if sha256_bytes(mb) != paths["input_sha"][os.path.basename(mpath)]:
        raise InvalidRun(RULE_SHA, os.path.basename(mpath))
    MF = json.loads(mb.decode("utf-8"))
    cell2 = MF["cells"]["cell_2_delta_gin_per_seed"]
    ref_seed = [cell2["s%d|seed%d" % (s, T["s_to_t"][s])] for s in T["seeds"]]
    ref_mean = MF["cells"]["cell_3_delta_gin"]
    del MF
    in_sha["gin/" + os.path.basename(mpath)] = sha256_bytes(mb)
    in_sha["master_X"], in_sha["master_Y"] = paths["master_sha"]["x"], paths["master_sha"]["y"]
    mats = build_mats(loaded, T)
    if len(mats) != T["n_mats"]:
        raise InvalidRun(RULE_NMATS, "mats")
    step("R3", "inputs verified · matrices %d · metrics_full 1" % len(mats))

    # ── R4 계산 ──
    eligible = np.arange(N_PT)
    prof = rd.leverage_profile(mats, T["seeds"], y, eligible, gi)
    step("R4", "derived path done · groups %d" % prof["n_groups_G"])
    verb = rd.leverage_profile_verbatim(mats, T["seeds"], y, eligible, gi)
    step("R4", "verbatim path done")
    e, ev = np.asarray(prof["e"], dtype=np.float64), np.asarray(verb["e"], dtype=np.float64)
    if fault == "perturb_verbatim":              # L4 내부 fault-injection 전용
        ev = ev.copy()
        ev[0] = ev[0] + 1e-9
    if prof["n_groups_G"] != len(uniq) or e.shape != (len(uniq),) or ev.shape != e.shape:
        raise InvalidRun(RULE_G, "e 길이")
    finite_all = (bool(np.isfinite(e).all()) and bool(np.isfinite(ev).all())
                  and all(np.isfinite(v) for v in [prof["t_obs"], prof["delta_rf"], prof["delta_gin"]]
                          + list(prof["delta_gin_per_seed"])))
    if not finite_all:
        raise InvalidRun(RULE_NONFINITE, "e/T_obs/Δ")
    max_diff = float(np.max(np.abs(e - ev)))
    if not max_diff <= TOL_DERIVED_VS_VERBATIM:
        raise InvalidRun(RULE_VERBATIM, "e 도출 vs 축자")
    cross = (len(prof["delta_gin_per_seed"]) == len(ref_seed)
             and all(a == b for a, b in zip(prof["delta_gin_per_seed"], ref_seed))
             and prof["delta_gin"] == ref_mean)
    if not cross:
        raise InvalidRun(RULE_CROSS113, "cell_2/cell_3")
    lam = rd.lambda_k(e, T["k_values"])
    rh = rd.rho(prof["t_obs"], e)
    lv = [lam["lambda_k"][k] for k in T["k_values"]]
    if not (all(np.isfinite(v) for v in lv) and np.isfinite(rh["rho"]) and np.isfinite(lam["denom_sum_sq"])):
        raise InvalidRun(RULE_NONFINITE, "λ/ρ")
    chain = [0.0] + lv + [1.0]
    monotone = all(chain[i] <= chain[i + 1] + TOL_MONOTONE for i in range(len(chain) - 1))
    if not monotone:
        raise HarnessAbort("λ 단조성 assert 실패")
    step("R4", "checks · derived≡verbatim · cross-113 bit-equal · monotone")
    step("R5", "invalidation rules: none triggered")

    # ── R6 봉인 쓰기 ──
    _mkdir_new(out_dir)
    _mkdir_new(sealed_out)
    new_access = {
        "ts_kst": now_kst(), "type": "machine_read", "purpose": "D11 leverage build",
        "human_exposure": False, "path": "_sealed/", "actor": "vscode-claude",
        "step": "블록 AX(docs/114) R6",
        "note": "λ·ρ·e_g·T_obs 는 leverage_diagnostics.json 에만 봉인. p 미계산. 부호 미산출. 사람 열람 0."}
    _assert_no_key_substr(new_access, FORBIDDEN_KEY_SUBSTR_SEALED, "access.log")
    _append_line(os.path.join(sealed_out, "access.log"), new_access)
    d_rf_g, d_gin_g = verb["d_rf_g"], verb["d_gin_g"]
    diag = {
        "_doc": ("블록 AX (docs/114) — S2 D11 레버리지 진단 봉인 산출. 개봉 전 사람 열람 금지. "
                 "게이트 아님(보고·주석용). p 미계산. 부호 미산출."),
        "block": "AX (docs/114)", "provenance": paths["provenance"],
        "spec_sha256": SPEC_SHA256, "amendment1_sha256": paths["public_meta"].get("amendment1_sha256"),
        "is_gate": T["is_gate"], "purpose_verbatim": T["purpose_verbatim"],
        "T_obs": prof["t_obs"], "T_obs_hex": float(prof["t_obs"]).hex(),
        "delta_rf": prof["delta_rf"], "delta_gin": prof["delta_gin"],
        "delta_gin_per_seed": {"s%d|seed%d" % (s, T["s_to_t"][s]): prof["delta_gin_per_seed"][i]
                               for i, s in enumerate(T["seeds"])},
        "e_profile": [{"g": int(g), "scaffold": uniq[g], "n_g": int(n_g[g]), "e_g": float(e[g]),
                       "d_rf_g": float(d_rf_g[g]), "d_gin_g": float(d_gin_g[g])} for g in range(len(uniq))],
        "lambda_k": {str(k): lam["lambda_k"][k] for k in T["k_values"]},
        "T_k_rule": "|e_g| 상위 k (동률=군 인덱스 오름차순)",
        "top_indices": {str(k): [int(i) for i in lam["top_indices"][k]] for k in T["k_values"]},
        "denom_sum_sq": lam["denom_sum_sq"],
        "rho": rh["rho"], "rho_numerator_abs": rh["numerator_abs"], "rho_denominator": rh["denominator"],
        "checks": {"derived_vs_verbatim_max_abs_diff": max_diff, "cross_113_bit_equal": True,
                   "lambda_monotone": True},
        "input_sha256": in_sha, "rf_consensus_dtype_original": rf_dtype,
        "n_groups_G": int(prof["n_groups_G"]),
        "n_macro_ap_calls_derived_path": int(prof["n_macro_ap_calls"]),
        "n_macro_ap_calls_total_note": "축자 경로·관측값 포함 실제 호출은 약 2배",
    }
    _assert_no_key_substr(diag, FORBIDDEN_KEY_SUBSTR_SEALED, T["sealed_name"])
    _atomic_bytes(os.path.join(sealed_out, T["sealed_name"]),
                  (json.dumps(diag, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
    step("R6", "sealed written · 1 file + access.log")

    # ── R7 공개 산출 ──
    counts_end = sealed_counts(paths["root"])
    wall = round(time.perf_counter() - t_start, 3)
    rel = "_sealed/" + T["sealed_name"]
    listing = [{"name": rel, "bytes": os.path.getsize(os.path.join(out_dir, rel)),
                "sha256": sha256_file(os.path.join(out_dir, rel))}]
    import sklearn
    pub = {
        "_doc": ("블록 AX (docs/114) 공개 manifest — 개수·환경·게이트 불리언·봉인 파일 이름/바이트/sha256·"
                 "wall_seconds 뿐. 진단 값은 기록하지 않는다."),
        "block": "AX (docs/114)", "provenance": paths["provenance"],
        "n_groups": int(prof["n_groups_G"]), "n_lambda_k": len(T["k_values"]), "n_sealed_files": len(listing),
        "n_input_matrices": len(mats), "completed": True,
        "sealed_files": listing,
        "input_checks": {"input_sha_all_match": True, "cid_order_match": True, "finite_inputs": True,
                         "finite_outputs": True, "derived_equals_verbatim": True,
                         "cross_block113_bit_equal": True, "monotone_check": True},
        "wall_seconds": wall,
        "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
        "pandas": pd.__version__,
        "harness_sha256": paths["public_meta"].get("harness_sha256"),
        "selftest_sha256": paths["public_meta"].get("selftest_sha256"),
        "spec_sha256": SPEC_SHA256,
        "amendment1_sha256": paths["public_meta"].get("amendment1_sha256"),
        "values_disclosed": False, "unblinding_performed": False,
        "sealed_counts_start": counts_start, "sealed_counts_end": counts_end,
        "ts_completed_kst": now_kst(),
    }
    _assert_no_key_substr(pub, FORBIDDEN_KEY_SUBSTR_PUBLIC, "manifest_public", exempt_count_keys=True)
    step("R7", "public manifest + run.log · wall_seconds %.3f" % wall)
    _atomic_bytes(os.path.join(out_dir, "manifest_public.json"),
                  (json.dumps(pub, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    _atomic_bytes(os.path.join(out_dir, "run.log"), ("\n".join(log) + "\n").encode("utf-8"))
    return pub


# ═══════════════════════════════════════════════════════════════════════════
# stage_run — R0 게이트 + compute_lock
# ═══════════════════════════════════════════════════════════════════════════
def stage_run():
    spec = load_spec()
    T = spec_terms(spec)
    # selftest 조건
    st_path = _abs(SELFTEST_OUT)
    if not os.path.exists(st_path):
        raise HarnessAbort("selftest 결과 부재")
    st = json.loads(_read_bytes(st_path).decode("utf-8"))
    me = sha256_file(os.path.abspath(__file__))
    if not (st.get("all_pass") is True and st.get("harness_sha256") == me):
        raise HarnessAbort("selftest 조건 불충족(all_pass·하네스 sha)")
    # 사이드카 · 항목 67
    if not os.path.exists(_abs(AMEND_PATH)) or sha256_file(_abs(AMEND_PATH)) != AMEND_SHA256:
        raise HarnessAbort("amendment 사이드카 부재·sha 불일치")
    d33 = _read_bytes(_abs(DOCS33)).decode("utf-8")
    if not re.search(ITEM67_RE, d33) or AMEND_SHA256 not in d33:
        raise HarnessAbort("docs/33 항목 67 부재 또는 사이드카 sha 미기재")
    # P2
    if sealed_counts(ROOT) != EXPECTED_SEALED_BEFORE:
        raise HarnessAbort("봉인 계수 불일치(착수)")
    fp0 = fingerprints(ROOT)
    if fp0 != {"conf": FP_CONFIRMATORY, "stab": FP_STABILITY, "old25": FP_EXISTING25, "gincons": FP_GIN_CONSENSUS}:
        raise HarnessAbort("봉인 stat 지문 불일치")
    if glob.glob(_abs(LEVERAGE_GLOB)):
        raise HarnessAbort("leverage 디렉터리 선존재")
    if os.path.exists(_abs("experiments/runs/.compute_lock.json")):
        raise HarnessAbort("compute_lock 선존재")
    if [json.loads(_read_bytes(_abs(p)))["gin_start_still_blocked"] for p in FLAG_FILES] != [True] * 3:
        raise HarnessAbort("플래그 3/3 불일치")
    if [json.loads(_read_bytes(_abs(p)))["unblinding_performed"] for p in UNBLIND_FILES] != [False] * 3:
        raise HarnessAbort("unblinding_performed 불일치")
    # P6 (정본 문서 판독 · 봉인 파일은 존재·바이트만)
    mp = _abs(GIN_CONS_DIR + "/manifest_public.json")
    if sha256_file(mp) != GIN_MANIFEST_PUBLIC_SHA256:
        raise HarnessAbort("GIN consensus manifest_public sha 불일치")
    sf = {x["name"]: x for x in json.loads(_read_bytes(mp).decode("utf-8"))["sealed_files"]}
    for name, sha in GIN_SHA.items():
        ent = sf.get("_sealed/" + name)
        p = _abs(GIN_CONS_DIR + "/_sealed/" + name)
        if ent is None or ent["sha256"] != sha or not os.path.exists(p) or os.path.getsize(p) != ent["bytes"]:
            raise HarnessAbort("GIN 입력 정본 불일치: " + name)
    fl = json.loads(_read_bytes(_abs(FIRST_LOOK_LOG)).decode("utf-8"))[FIRST_LOOK_RF_INDEX]
    if fl["sealed_path"] != RF_CONS_DIR + "/_sealed" or any(fl["sealed_sha256"][n] != s for n, s in RF_SHA.items()):
        raise HarnessAbort("RF 입력 정본 불일치")
    if not all(os.path.exists(_abs(RF_CONS_DIR + "/_sealed/" + n)) for n in RF_SHA):
        raise HarnessAbort("RF 입력 부재")
    # P7
    s2 = spec["S2_d11_leverage"]
    if not (s2["executed_in_block"] == 114 and T["n_mats"] == len(GIN_SHA) - 1 + len(RF_SHA)
            and T["sealed_name"].endswith(".json") and T["G"] > 0):
        raise HarnessAbort("명세 S2 결속 불일치")
    paths = {"root": ROOT, "out_dir": _abs(OUT_REL),
             "master_x": _abs(MASTER_X[0]), "master_y": _abs(MASTER_Y[0]),
             "master_sha": {"x": MASTER_X[1], "y": MASTER_Y[1]},
             "n_rows_expected": N_DRUGS, "n_groups_expected": T["G"],
             "rf_dir": _abs(RF_CONS_DIR + "/_sealed"), "gin_dir": _abs(GIN_CONS_DIR + "/_sealed"),
             "input_sha": dict(GIN_SHA, **RF_SHA), "spec": spec, "provenance": PROVENANCE_RUN,
             "public_meta": {"harness_sha256": me, "selftest_sha256": sha256_file(st_path),
                             "amendment1_sha256": AMEND_SHA256}}
    cl.gate_a_load("AX run entry")
    with cl.ComputeLock(script="rqint_leverage_d11.py", role="runner"):
        pub = core(paths, fault=None)
    end = sealed_counts(ROOT)
    fp1 = fingerprints(ROOT)
    ok = end == EXPECTED_SEALED_AFTER and fp1["conf"] == FP_CONFIRMATORY and fp1["stab"] == FP_STABILITY
    print(json.dumps({"stage": "run", "sealed_counts_end_expected": end == EXPECTED_SEALED_AFTER,
                      "confirmatory_fp_unchanged": fp1["conf"] == FP_CONFIRMATORY,
                      "stability_fp_unchanged": fp1["stab"] == FP_STABILITY,
                      "completed": pub["completed"]}, ensure_ascii=False), flush=True)
    return 0 if ok else 3


# ═══════════════════════════════════════════════════════════════════════════
# 합성 자체검사 L1~L12 (확증 입력 판독 0)
# ═══════════════════════════════════════════════════════════════════════════
FIXTURE_SMILES = ["c1ccccc1", "c1ccncc1", "C1CCCCC1", "c1ccc2ccccc2c1", "c1ccoc1", "c1ccsc1", "C1CCNCC1",
                  "C1CCOC1", "c1ccc(-c2ccccc2)cc1", "c1ccc2ncccc2c1", "c1cc[nH]c1", "C1CC1", "c1ncncn1", "CCO"]


def _write_npz(path, **arrays):
    with open(path, "wb") as f:
        np.savez(f, **arrays)


def _fx_metrics(Y, G, T):
    elig = np.arange(N_PT)
    lo, hi = T["arms"]
    d = {}
    dl = []
    for s in T["seeds"]:
        t = T["s_to_t"][s]
        v = (sap_rqint.macro_ap(Y, G[(hi, t)], elig)["macro_ap"] - sap_rqint.macro_ap(Y, G[(lo, t)], elig)["macro_ap"])
        d["s%d|seed%d" % (s, t)] = v
        dl.append(v)
    return {"cells": {"cell_2_delta_gin_per_seed": d, "cell_3_delta_gin": float(np.mean(dl))}}


def _make_fixture(tmp, spec, n=60, rng_seed=20260928):
    T = spec_terms(spec)
    rng = np.random.default_rng(rng_seed)
    os.makedirs(os.path.join(tmp, "data"))
    cids = np.sort(rng.choice(np.arange(1000, 100000), size=n, replace=False)).astype(np.int64)
    smi = list(FIXTURE_SMILES) + [FIXTURE_SMILES[i] for i in rng.integers(0, len(FIXTURE_SMILES), n - len(FIXTURE_SMILES))]
    smi = [smi[i] for i in rng.permutation(n)]
    Y = (rng.random((n, N_PT)) < 0.3).astype(int)
    for j in range(N_PT):
        if Y[:, j].sum() == 0:
            Y[rng.integers(0, n), j] = 1
    mx, my = os.path.join(tmp, "data", "master_X.parquet"), os.path.join(tmp, "data", "master_Y.parquet")
    pd.DataFrame({"cid": cids, "smiles_canonical": smi}).to_parquet(mx)
    ydf = pd.DataFrame(Y, columns=["pt_%04d" % j for j in range(N_PT)])
    ydf.insert(0, "cid", cids)
    ydf.to_parquet(my)
    rf_dir = os.path.join(tmp, "runs", "fx_rf", "_sealed")
    gin_dir = os.path.join(tmp, "runs", "fx_gin", "_sealed")
    os.makedirs(rf_dir)
    os.makedirs(gin_dir)
    for d in (rf_dir, gin_dir):
        with open(os.path.join(d, "access.log"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "machine_read", "actor": "fixture"}) + "\n")
    lo, hi = T["arms"]
    sha, RF, G = {}, {}, {}
    for arm in (lo, hi):
        RF[arm] = rng.random((n, N_PT)).astype(np.float32)          # RF dtype 변환 경로 검증
        p = os.path.join(rf_dir, "consensus_%s.npz" % arm)
        _write_npz(p, consensus=RF[arm], cid=cids)
        sha[os.path.basename(p)] = sha256_file(p)
        for s in T["seeds"]:
            t = T["s_to_t"][s]
            G[(arm, t)] = rng.random((n, N_PT))
            p = os.path.join(gin_dir, T["gin_file"].format(model=arm, t=t))
            _write_npz(p, consensus=G[(arm, t)], cid=cids)
            sha[os.path.basename(p)] = sha256_file(p)
    mp = os.path.join(gin_dir, T["gin_metrics"])
    with open(mp, "w", encoding="utf-8") as f:
        f.write(json.dumps(_fx_metrics(Y, G, T), indent=2) + "\n")
    sha[os.path.basename(mp)] = sha256_file(mp)
    n_groups = len(set(scaffold_of(s) for s in smi))
    paths = {"root": tmp, "out_dir": os.path.join(tmp, "runs", "fx_leverage"),
             "master_x": mx, "master_y": my, "master_sha": {"x": sha256_file(mx), "y": sha256_file(my)},
             "n_rows_expected": n, "n_groups_expected": n_groups, "rf_dir": rf_dir, "gin_dir": gin_dir,
             "input_sha": sha, "spec": spec, "provenance": PROVENANCE_RUN,
             "public_meta": {"harness_sha256": "fixture", "selftest_sha256": "fixture",
                             "amendment1_sha256": AMEND_SHA256}}
    return paths, {"Y": Y, "RF": RF, "G": G, "T": T, "cids": cids, "n_groups": n_groups}


def _run_quiet(paths, fault=None):
    buf = io.StringIO()
    exc = None
    with contextlib.redirect_stdout(buf):
        try:
            core(paths, fault=fault)
        except Exception as e:           # noqa: BLE001 — 시험 대상
            exc = e
    return buf.getvalue(), exc


def _load_fx_diag(paths, T):
    return json.loads(_read_bytes(os.path.join(paths["out_dir"], "_sealed", T["sealed_name"])).decode("utf-8"))


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


def _no_numeric_values(s):
    return re.search(r"\d\.\d", s) is None and "nan" not in s.lower() and "inf" not in s.lower()


def selftest_L1_constants():
    checks = {"spec": sha256_file(_abs(SPEC_PATH)) == SPEC_SHA256,
              "amendment1": sha256_file(_abs(AMEND_PATH)) == AMEND_SHA256}
    for rel, sha in PRE_IMPORT_SHA.items():
        checks["pre_import:" + os.path.basename(rel)] = sha256_file(_abs(rel)) == sha
    C = json.loads(_read_bytes(_abs("v3_Multimodal/config/gin_train_contract.json")).decode("utf-8"))["preconditions"]
    reg = dict(C["f4_authority_chain"], **C["f5_reused_modules"])
    for rel in ("v3_Multimodal/src/ladder_confirmatory.py", "v3_Multimodal/src/confirmatory_oof_rep1.py"):
        checks["registered_f5:" + os.path.basename(rel)] = reg[rel]["sha256"] == PRE_IMPORT_SHA[rel]
    M = json.loads(_read_bytes(_abs("experiments/sap/manifest.json")).decode("utf-8"))["modules"]
    for nm in ("consensus.py", "metrics.py", "decision.py", "redaction.py"):
        checks["registered_sap:" + nm] = M[nm]["sha256"] == PRE_IMPORT_SHA["v3_Multimodal/src/sap/" + nm]
    A = json.loads(_read_bytes(_abs(AMEND_PATH)).decode("utf-8"))
    checks["amendment_binds_spec"] = A["amends"]["spec_sha256"] == SPEC_SHA256
    checks["amendment_eps_source_exists"] = (A["decision"]["eps_source"] == "sap.rqint._EPS"
                                             and hasattr(sap_rqint, "_EPS"))
    checks["rd_functions_present"] = all(callable(getattr(rd, f, None)) for f in
                                         ("leverage_profile", "leverage_profile_verbatim", "lambda_k", "rho"))
    return _res("L1 상수·해시", checks)


def selftest_L2_spec_binding(spec):
    T = spec_terms(spec)
    s2 = spec["S2_d11_leverage"]
    tree = _src_tree()
    lits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and (n.value == s2["inputs"]["scaffold_group"] and type(n.value) is int
                                            or n.value == s2["outputs"]["sealed"]):
            lits.append(n.lineno)
        if isinstance(n, (ast.List, ast.Tuple)) and all(isinstance(x, ast.Constant) for x in n.elts) \
                and [x.value for x in n.elts] == list(s2["lambda_k"]["k_values"]):
            lits.append(n.lineno)
    return _res("L2 S2 결속", {
        "k_values_from_spec": list(T["k_values"]) == s2["lambda_k"]["k_values"],
        "n_mats_from_spec": T["n_mats"] == s2["inputs"]["consensus_matrices"],
        "G_from_spec": T["G"] == s2["inputs"]["scaffold_group"],
        "sealed_name_from_spec": T["sealed_name"] == s2["outputs"]["sealed"],
        "is_gate_false": T["is_gate"] is False,
        "no_literal_restatement_in_source": not lits}, literal_lines=lits)


def selftest_L3_mats(fx):
    T = fx["T"]
    lo, hi = T["arms"]
    loaded = {}
    for arm in (lo, hi):
        loaded[("RF", None, arm)] = fx["RF"][arm].astype(np.float64)
        for s in T["seeds"]:
            loaded[("GIN", T["s_to_t"][s], arm)] = fx["G"][(arm, T["s_to_t"][s])]
    mats = build_mats(loaded, T)
    gin_s = sorted({k[1] for k in mats if k[0] == "GIN"})
    elig = np.arange(N_PT)
    t_obs, d_rf, d_gin, d_gin_s = sap_rqint.observed_statistic(mats, T["seeds"], fx["Y"], elig)
    mac = lambda P: sap_rqint.macro_ap(fx["Y"], P, elig)["macro_ap"]      # noqa: E731
    d_rf_direct = mac(fx["RF"][hi].astype(np.float64)) - mac(fx["RF"][lo].astype(np.float64))
    d_gin_direct = [mac(fx["G"][(hi, T["s_to_t"][s])]) - mac(fx["G"][(lo, T["s_to_t"][s])]) for s in T["seeds"]]
    t_direct = d_rf_direct - float(np.mean(d_gin_direct))
    return _res("L3 mats 구성", {
        "eight_keys": len(mats) == T["n_mats"],
        "gin_keys_are_s_index_123": gin_s == [1, 2, 3] == T["seeds"],
        "s_to_t_42_1_2": [T["s_to_t"][s] for s in T["seeds"]] == [42, 1, 2],
        "rf_key_seed_none": all(k[1] is None for k in mats if k[0] == "RF") and sum(k[0] == "RF" for k in mats) == 2,
        "arms_match_sap": tuple(sorted(T["arms"])) == tuple(sorted(sap_rqint._ARMS)),
        "observed_statistic_equals_direct": abs(t_obs - t_direct) <= 1e-15
                                            and abs(d_rf - d_rf_direct) <= 1e-15,
        "gin_seed_order_matches": all(a == b for a, b in zip(d_gin_s, d_gin_direct))},
        provenance=PROVENANCE_SYN)


def selftest_L4_derived_vs_verbatim(paths, fx, tmp):
    T = fx["T"]
    D = _load_fx_diag(paths, T)
    e = np.array([r["e_g"] for r in D["e_profile"]])
    d = np.array([r["d_rf_g"] - r["d_gin_g"] for r in D["e_profile"]])
    # 규칙 발동 확인 (fault)
    p2, _fx2 = _make_fixture(os.path.join(tmp, "l4_fault"), paths["spec"], rng_seed=4040)
    _o, exc = _run_quiet(p2, fault="perturb_verbatim")
    return _res("L4 도출↔축자", {
        "max_abs_diff_le_1e-12": D["checks"]["derived_vs_verbatim_max_abs_diff"] <= 1e-12,
        "stored_e_vs_d_rf_minus_d_gin_le_1e-12": float(np.max(np.abs(e - d))) <= 1e-12,
        "G_matches_fixture": D["n_groups_G"] == fx["n_groups"] == len(D["e_profile"]),
        "macro_ap_calls_G_times_8": D["n_macro_ap_calls_derived_path"] == fx["n_groups"] * T["n_mats"],
        "verbatim_mismatch_rule_fires": isinstance(exc, InvalidRun) and exc.rule == RULE_VERBATIM
                                        and not os.path.exists(p2["out_dir"])},
        max_abs_diff=D["checks"]["derived_vs_verbatim_max_abs_diff"], provenance=PROVENANCE_SYN)


def selftest_L5_lambda(paths, fx):
    T = fx["T"]
    e = np.array([0.10, -0.50, 0.30, -0.05, 0.20, -0.40, 0.01, 0.02, -0.03, 0.04, 0.06, -0.07])
    lam = rd.lambda_k(e, T["k_values"])
    lv = [lam["lambda_k"][k] for k in T["k_values"]]
    signed_top = int(np.argmax(e))
    D = _load_fx_diag(paths, T)
    ld = [D["lambda_k"][str(k)] for k in T["k_values"]]
    ref = rd.lambda_k(np.array([r["e_g"] for r in D["e_profile"]]), T["k_values"])
    return _res("L5 λ", {
        "monotone": 0.0 <= lv[0] <= lv[1] <= lv[2] <= 1.0,
        "top1_by_abs": lam["top_indices"][T["k_values"][0]] == [1],
        "abs_differs_from_signed": signed_top != 1,
        "top2_by_abs": lam["top_indices"][T["k_values"][1]] == [1, 5],
        "fixture_monotone": 0.0 <= ld[0] <= ld[1] <= ld[2] <= 1.0 and D["checks"]["lambda_monotone"] is True,
        "fixture_equals_rd": ld == [ref["lambda_k"][k] for k in T["k_values"]]},
        provenance=PROVENANCE_SYN)


def selftest_L6_rho(paths, fx):
    T = fx["T"]
    e = np.array([0.375, -0.25, 0.125, 0.0625])          # 이진 유한소수 — 대칭 비교가 정확히 성립
    s = float(np.sum(e))
    delta = 0.125
    rp, rm = rd.rho(s + delta, e)["rho"], rd.rho(s - delta, e)["rho"]
    r0 = rd.rho(s, e)["rho"]
    D = _load_fx_diag(paths, T)
    ed = np.array([r["e_g"] for r in D["e_profile"]])
    ref = rd.rho(D["T_obs"], ed)
    return _res("L6 ρ", {
        "symmetric_abs_numerator": rp == rm and rp > 0,
        "linear_fixture_zero": r0 == 0.0,
        "is_gate_false": rd.rho(s, e)["is_gate"] is False,
        "fixture_equals_rd": D["rho"] == ref["rho"] and D["rho_numerator_abs"] == ref["numerator_abs"],
        "T_obs_hex_roundtrip": float.fromhex(D["T_obs_hex"]) == D["T_obs"]},
        provenance=PROVENANCE_SYN)


def selftest_L7_cross113(tmp, spec):
    ok = {}
    msgs = []
    tdir = os.path.join(tmp, "l7")
    paths, fx = _make_fixture(tdir, spec, rng_seed=7070)
    T = fx["T"]
    mp = os.path.join(paths["gin_dir"], T["gin_metrics"])
    MF = json.loads(_read_bytes(mp).decode("utf-8"))
    MF["cells"]["cell_3_delta_gin"] = float(np.nextafter(MF["cells"]["cell_3_delta_gin"], np.inf))
    with open(mp, "w", encoding="utf-8") as f:
        f.write(json.dumps(MF, indent=2) + "\n")
    paths["input_sha"][os.path.basename(mp)] = sha256_file(mp)
    _o, exc = _run_quiet(paths)
    msgs.append(str(exc))
    ok["one_ulp_cell3_invalidates"] = (isinstance(exc, InvalidRun) and exc.rule == RULE_CROSS113
                                       and not os.path.exists(paths["out_dir"]))
    tdir2 = os.path.join(tmp, "l7b")
    paths2, fx2 = _make_fixture(tdir2, spec, rng_seed=7071)
    mp2 = os.path.join(paths2["gin_dir"], T["gin_metrics"])
    MF2 = json.loads(_read_bytes(mp2).decode("utf-8"))
    k0 = sorted(MF2["cells"]["cell_2_delta_gin_per_seed"])[1]
    MF2["cells"]["cell_2_delta_gin_per_seed"][k0] = float(np.nextafter(MF2["cells"]["cell_2_delta_gin_per_seed"][k0], -np.inf))
    with open(mp2, "w", encoding="utf-8") as f:
        f.write(json.dumps(MF2, indent=2) + "\n")
    paths2["input_sha"][os.path.basename(mp2)] = sha256_file(mp2)
    _o, exc2 = _run_quiet(paths2)
    msgs.append(str(exc2))
    ok["one_ulp_cell2_invalidates"] = (isinstance(exc2, InvalidRun) and exc2.rule == RULE_CROSS113
                                       and not os.path.exists(paths2["out_dir"]))
    ok["messages_value_free"] = all(_no_numeric_values(m) for m in msgs)
    return ok, msgs


def selftest_L8_invalid(tmp_root, spec):
    results, msgs = {}, []
    cases = ("a_sha_tamper", "b_cid_shuffle", "c_nan", "d_G_mismatch", "e_matrix_missing")
    expect = {"a_sha_tamper": RULE_SHA, "b_cid_shuffle": RULE_ORDER, "c_nan": RULE_NONFINITE,
              "d_G_mismatch": RULE_G, "e_matrix_missing": RULE_NMATS}
    for i, case in enumerate(cases):
        tmp = os.path.join(tmp_root, "l8_" + case)
        paths, fx = _make_fixture(tmp, spec, rng_seed=800 + i)
        T = fx["T"]
        lo, hi = T["arms"]
        t = T["s_to_t"][T["seeds"][1]]
        name = T["gin_file"].format(model=hi, t=t)
        fpath = os.path.join(paths["gin_dir"], name)
        if case == "a_sha_tamper":
            _write_npz(fpath, consensus=fx["G"][(hi, t)] * 0.5, cid=fx["cids"])
        elif case == "b_cid_shuffle":
            _write_npz(fpath, consensus=fx["G"][(hi, t)], cid=fx["cids"][::-1].copy())
            paths["input_sha"][name] = sha256_file(fpath)
        elif case == "c_nan":
            P = fx["G"][(hi, t)].copy()
            P[3, 5] = np.nan
            _write_npz(fpath, consensus=P, cid=fx["cids"])
            paths["input_sha"][name] = sha256_file(fpath)
        elif case == "d_G_mismatch":
            paths["n_groups_expected"] = T["G"]            # 명세 G(합성 scaffold 로는 불일치)
        else:
            os.remove(os.path.join(paths["rf_dir"], "consensus_%s.npz" % lo))
        _out, exc = _run_quiet(paths)
        msg = str(exc) if exc is not None else ""
        msgs.append(msg)
        results[case] = (isinstance(exc, InvalidRun) and exc.rule == expect[case]
                         and not os.path.exists(paths["out_dir"]) and _no_numeric_values(msg))
    return _res("L8 무효 5종", results), msgs


def selftest_L9_provenance(paths, fx):
    T = fx["T"]
    txt = _read_bytes(os.path.join(paths["out_dir"], "_sealed", T["sealed_name"])).decode("utf-8")
    D = json.loads(txt)
    return _res("L9 provenance", {
        "synthetic_fixture_zero": txt.count(PROVENANCE_SYN) == 0,
        "confirmatory_sealed_one": txt.count(PROVENANCE_RUN) == 1 and D["provenance"] == PROVENANCE_RUN,
        "rd_returns_synthetic_constant": rd.lambda_k(np.array([1.0, 2.0]), (1,))["provenance"] == PROVENANCE_SYN})


def selftest_L10_leak(paths, fx, base_stdout, exc_msgs):
    T = fx["T"]
    D = _load_fx_diag(paths, T)
    vals = [D["T_obs"], D["delta_rf"], D["delta_gin"], D["rho"], D["rho_numerator_abs"], D["rho_denominator"],
            D["denom_sum_sq"]] + list(D["delta_gin_per_seed"].values()) + list(D["lambda_k"].values()) + \
        [r[k] for r in D["e_profile"] for k in ("e_g", "d_rf_g", "d_gin_g")]
    pats = set()
    for v in vals:
        pats |= {repr(v), "%.4f" % v, "%.6f" % v, "%.4f" % abs(v), "%.6f" % abs(v)}
    pats.discard("0.0000")
    pats.discard("0.000000")
    pub_txt = _read_bytes(os.path.join(paths["out_dir"], "manifest_public.json")).decode("utf-8")
    runlog = _read_bytes(os.path.join(paths["out_dir"], "run.log")).decode("utf-8")
    texts = {"stdout": base_stdout, "run.log": runlog, "manifest_public": pub_txt, "exceptions": "\n".join(exc_msgs)}
    hits = {k: sorted(p for p in pats if p in txt) for k, txt in texts.items()}
    pub = json.loads(pub_txt)
    pub_bad = _bad_keys(pub, FORBIDDEN_KEY_SUBSTR_PUBLIC, exempt_count_keys=True)
    new_objs = [D, pub, json.loads(_read_bytes(os.path.join(paths["out_dir"], "_sealed", "access.log")))]
    for d in (paths["rf_dir"], paths["gin_dir"]):
        new_objs.append(json.loads(_read_bytes(os.path.join(d, "access.log")).decode("utf-8").splitlines()[-1]))
    sealed_bad = sorted({k for o in new_objs for k in _keys_recursive(o)
                         for w in FORBIDDEN_KEY_SUBSTR_SEALED if w in k})
    return _res("L10 누설 가드", {"value_strings_absent": not any(hits.values()),
                                  "public_json_keys_clean": not pub_bad,
                                  "new_file_keys_no_sign_words": not sealed_bad},
                n_patterns=len(pats), hits={k: len(v) for k, v in hits.items()},
                public_bad_keys=pub_bad, sealed_bad_keys=sealed_bad)


def selftest_L11_ast():
    tree = _src_tree()
    forbidden = ("rqint_test", "holm", "paired_scaffold_bootstrap", "emit_sign", "open_sealed",
                 "rq2_decision", "rq3_decision", "rq4_decision")
    hits = [(_call_name(n), n.lineno) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and _call_name(n) in forbidden]
    np_sign = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "sign"
               and isinstance(n.value, ast.Name) and n.value.id == "np"]
    rd_attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "rd"}
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    net = sorted(imported & {"socket", "urllib", "requests", "http", "ftplib", "smtplib", "asyncio",
                             "aiohttp", "httpx", "telnetlib"})
    environ = [n.lineno for n in ast.walk(tree)
               if (isinstance(n, ast.Attribute) and n.attr == "environ")
               or (isinstance(n, ast.Call) and _call_name(n) == "getenv")]
    opts = {a.value for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "add_argument"
            for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    par = _parents(tree)
    cl_fns = {_enclosing(par, n) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name) and n.func.value.id == "cl"}
    return _res("L11 AST", {
        "forbidden_calls_zero": not hits, "np_sign_zero": not np_sign,
        "rd_selftest_main_not_used": not (rd_attrs & {"run_selftest", "main"}),
        "rd_functions_exact": rd_attrs == {"leverage_profile", "leverage_profile_verbatim", "lambda_k", "rho"},
        "network_imports_zero": not net, "os_environ_zero": not environ,
        "cli_options_exact": opts == {"--stage", "--out"},
        "cl_calls_only_in_stage_run": cl_fns == {"stage_run"}},
        forbidden_hits=hits, rd_attrs=sorted(rd_attrs))


def selftest_L12_hygiene(guard_violations, cl_calls, before):
    after = {"sealed_counts": sealed_counts(ROOT), "fp": fingerprints(ROOT), "pycache": _pycache_dirs(ROOT),
             "leverage": len(glob.glob(_abs(LEVERAGE_GLOB)))}
    return _res("L12 위생", {
        "runtime_write_guard_violations_zero": not guard_violations,
        "cl_calls_during_selftest_zero": cl_calls["n"] == 0,
        "real_sealed_counts_unchanged": after["sealed_counts"] == before["sealed_counts"] == EXPECTED_SEALED_BEFORE,
        "fp_confirmatory_unchanged": after["fp"]["conf"] == before["fp"]["conf"] == FP_CONFIRMATORY,
        "fp_stability_unchanged": after["fp"]["stab"] == before["fp"]["stab"] == FP_STABILITY,
        "fp_existing25_unchanged": after["fp"]["old25"] == before["fp"]["old25"] == FP_EXISTING25,
        "fp_gin_consensus_unchanged": after["fp"]["gincons"] == before["fp"]["gincons"] == FP_GIN_CONSENSUS,
        "leverage_dir_not_created": after["leverage"] == 0,
        "pycache_unchanged": after["pycache"] == before["pycache"]},
        guard_violations=guard_violations[:5])


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

    orig = {"open": builtins.open, "savez": np.savez, "savez_compressed": np.savez_compressed,
            "replace": os.replace, "makedirs": os.makedirs, "mkdir": os.mkdir, "remove": os.remove}

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
    np.savez, np.savez_compressed = wrap("savez"), wrap("savez_compressed")
    os.replace, os.makedirs, os.mkdir, os.remove = wrap("replace", 2), wrap("makedirs"), wrap("mkdir"), wrap("remove")
    try:
        yield
    finally:
        builtins.open = orig["open"]
        np.savez, np.savez_compressed = orig["savez"], orig["savez_compressed"]
        os.replace, os.makedirs, os.mkdir, os.remove = orig["replace"], orig["makedirs"], orig["mkdir"], orig["remove"]


def run_selftest():
    spec = load_spec()
    before = {"sealed_counts": sealed_counts(ROOT), "fp": fingerprints(ROOT), "pycache": _pycache_dirs(ROOT)}
    cl_calls = {"n": 0}
    orig_cl = {k: getattr(cl, k) for k in ("gate_a_load", "gate_b_exclusive", "gate_c_settle", "ComputeLock")}

    def _cl_trap(*_a, **_k):
        cl_calls["n"] += 1
        raise RuntimeError("cl 호출 금지(selftest)")

    for k in orig_cl:
        setattr(cl, k, _cl_trap)
    tmp = tempfile.mkdtemp(prefix="ax_selftest_")
    violations = []
    results = []
    try:
        # ★ 쓰기 가드는 모든 import 완료 후(모듈 최상단 import 는 이미 끝남) 설치한다.
        with _write_guard([tmp, os.path.dirname(_abs(SELFTEST_OUT))], violations):
            results.append(selftest_L1_constants())
            results.append(selftest_L2_spec_binding(spec))
            base_paths, fx = _make_fixture(os.path.join(tmp, "base"), spec)
            results.append(selftest_L3_mats(fx))
            acc_before = {d: _read_bytes(os.path.join(d, "access.log")).count(b"\n")
                          for d in (base_paths["rf_dir"], base_paths["gin_dir"])}
            base_stdout, base_exc = _run_quiet(base_paths)
            if base_exc is not None:
                raise RuntimeError("base fixture run 실패: %s %s" % (type(base_exc).__name__, base_exc))
            acc_after = {d: _read_bytes(os.path.join(d, "access.log")).count(b"\n") for d in acc_before}
            results.append(selftest_L4_derived_vs_verbatim(base_paths, fx, tmp))
            results.append(selftest_L5_lambda(base_paths, fx))
            results.append(selftest_L6_rho(base_paths, fx))
            ok7, m7 = selftest_L7_cross113(tmp, spec)
            D = _load_fx_diag(base_paths, fx["T"])
            ok7["base_bit_equal_pass"] = D["checks"]["cross_113_bit_equal"] is True
            results.append(_res("L7 113 교차 대조", ok7, provenance=PROVENANCE_SYN))
            r8, m8 = selftest_L8_invalid(tmp, spec)
            # 선존재 출력 → R2 이전 중단
            pre_paths, _ = _make_fixture(os.path.join(tmp, "l8_pre"), spec, rng_seed=880)
            os.makedirs(os.path.join(pre_paths["out_dir"], "_sealed"))
            a0 = _read_bytes(os.path.join(pre_paths["gin_dir"], "access.log"))
            _o, pexc = _run_quiet(pre_paths)
            r8["checks"]["preexisting_output_aborts_before_r2"] = (
                isinstance(pexc, HarnessAbort) and _read_bytes(os.path.join(pre_paths["gin_dir"], "access.log")) == a0)
            r8["checks"]["base_access_plus_one_each"] = all(acc_after[d] == acc_before[d] + 1 for d in acc_before)
            r8["checks"]["base_new_tree_two_files"] = sorted(os.listdir(os.path.join(base_paths["out_dir"], "_sealed"))) \
                == sorted(["access.log", fx["T"]["sealed_name"]])
            r8["fails"] = [k for k, v in r8["checks"].items() if not v]
            r8["pass"] = not r8["fails"]
            results.append(r8)
            results.append(selftest_L9_provenance(base_paths, fx))
            results.append(selftest_L10_leak(base_paths, fx, base_stdout, m7 + m8))
            results.append(selftest_L11_ast())
    finally:
        for k, v in orig_cl.items():
            setattr(cl, k, v)
        shutil.rmtree(tmp, ignore_errors=True)
    results.append(selftest_L12_hygiene(violations, cl_calls, before))
    order = ["L%d" % i for i in range(1, 13)]
    results.sort(key=lambda r: order.index(r["name"].split()[0]))
    n_pass = sum(1 for r in results if r["pass"])
    return {
        "_doc": "docs/114 블록 AX / AX-5 — 합성 자체검사 L1~L12. 확증 입력 판독 0. 모든 수치는 합성 fixture 산출물.",
        "provenance": PROVENANCE_SYN, "block": "AX (docs/114)",
        "harness_path": "v3_Multimodal/src/rqint_leverage_d11.py",
        "harness_sha256": sha256_file(os.path.abspath(__file__)),
        "spec_path": SPEC_PATH, "spec_sha256": SPEC_SHA256,
        "amendment1_path": AMEND_PATH, "amendment1_sha256": AMEND_SHA256,
        "python": platform.python_version(), "numpy": np.__version__,
        "ts_kst": now_kst(), "n_tests": len(results), "n_pass": n_pass, "n_skip": 0,
        "all_pass": n_pass == len(results) == 12,
        "tests": results, "confirmatory_values_read": 0, "sealed_human_read": 0, "network_calls": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="블록 AX — D11 레버리지 진단 λ·ρ 봉인 산출")
    ap.add_argument("--stage", choices=["selftest", "run"], default="selftest")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.stage == "run":
        if a.out:
            raise SystemExit("--out 은 selftest 전용")
        return stage_run()
    if a.out and os.path.abspath(a.out) != _abs(SELFTEST_OUT):
        raise SystemExit("--out 은 SELFTEST_OUT 만 허용")
    res = run_selftest()
    os.makedirs(os.path.dirname(_abs(SELFTEST_OUT)), exist_ok=True)
    with open(_abs(SELFTEST_OUT), "w", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"stage": "selftest", "all_pass": res["all_pass"], "n_pass": res["n_pass"],
                      "n_tests": res["n_tests"], "fails": {t["name"]: t["fails"] for t in res["tests"] if not t["pass"]}},
                     ensure_ascii=False))
    return 0 if res["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
