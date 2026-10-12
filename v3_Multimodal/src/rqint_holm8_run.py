"""rqint_holm8_run.py — 블록 AY (docs/115): Holm ⑧ RQ-int 본런(B = 동전 벡터 수) + D9 BCa 봉인 산출.

동결 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json` 의 **S4_holm8_main_run · S5_d9_delta_bca** 를
사이드카 1호(주 p 식 U2) · 사이드카 2호(동전 시드 V1 · GIN 복합 BCa V2 · 분할 V3)와 함께 그대로 구현한다.
B·참조분포·S5 호출 규약·주 p 식은 명세·사이드카에서 읽는다(하네스에 재기술 0).
계산 = `sap.rqint`(build_eight_consensus · observed_statistic · _apply_swap · _EPS) · `sap.bootstrap`
(paired_scaffold_bootstrap · _cluster_index · _delta_on_rows · _bca_ci) 를 import 해 그대로 호출(재구현 0).
동전 루프는 `sap.rqint.rqint_test` 의 루프를 **같은 난수열로** 청크 실행하고 체크포인트에서 재개한다.

⛔ 무결성 (docs/115 §2)
  · p·T*·BCa 는 전부 `_sealed/` 에만 봉인한다. Holm 조정·판정·개봉 0 · `open_sealed`·`emit_sign`·판정 함수 호출 0.
  · 봉인 «값» 은 `run` stage 안에서만 기계 판독한다. stdout·run.log·heartbeat·manifest_public·예외 메시지에
    값을 내보내지 않는다. 진행 표시 = 동전 개수·시간뿐. 결과 의존 분기 0(집계는 루프 완료 후 1회).
  · S3(D12) 실행 0 · 네트워크 0 · 환경변수 판독 0(스레드 변수 «설정»만 — numpy import 전).

구조
  stage_run()  = R0 게이트(모드 판별 first/reentry) · 전원 · 부하 · compute_lock → core(paths) 호출.
  core(paths)  = R0′~R7. 모든 경로·상수를 인자로 받는다. selftest 는 core 만 호출한다(cl.*·pmset 0).
종료 코드 = 0 완료 · 1 비정상(재기동 대상) · 9 락 바쁨 · 10 부하 · 13 무결성/무효 · 15 전원.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import os

for _tv in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS"):
    os.environ[_tv] = "1"                    # 블록 AJ 속도 조건 재현 · numpy import 전 «설정»(판독 0)

import argparse
import ast
import builtins
import contextlib
import datetime
import glob
import hashlib
import importlib.util
import inspect
import io
import json
import platform
import re
import shutil
import subprocess
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
AMEND1_PATH = "v3_Multimodal/config/rqint_downstream_spec_v1_amendment1.json"
AMEND1_SHA256 = "63c29d6b6a9e22951f2e2891b54f4251d5e4f679fc1d3b3f110cfdf510aab05c"
AMEND2_PATH = "v3_Multimodal/config/rqint_downstream_spec_v1_amendment2.json"
AMEND2_SHA256 = "c8e1e2569e7f62fe14a49bdd5581baf3d2d9da9fb411e15099cd85a01bf1a3d8"
DECISIONS_PATH = "v3_Multimodal/config/rqint_procedure_decisions_v1.json"
DECISIONS_SHA256 = "16776f21df6ae29b8805272ba39b59b522693217ee113e307a3b3cd3819a96ca"
B100K_PRESPEC = ("v3_Multimodal/config/b_100k_prespec.json",
                 "e7406c23b8d61b0c4d04638395f4c7803e1e0dc32501baa8dae5047c4d169625")
DOCS33 = "docs/33_prereg_deviation_log.md"
ITEM69_RE = r"(?m)^69\. \*\*Holm ⑧ 본런 착수 전 결정"
WATCHDOG_PATH = "v3_Multimodal/src/rqint_holm8_watchdog.py"
MASTER_X = ("data/processed/master_X.parquet",
            "788c8a64d19e8c3cc030476e7b2eb7f207246e3af6e73304d97f2fc9aa2ae6e6")
MASTER_Y = ("data/processed/master_Y.parquet",
            "bd23584342de6482e50f218bd409740acc2a00eeac86ee95bd89952bc3d18018")
# import 전 파일 sha 검증 대상 (Q1)
PRE_IMPORT_SHA = {
    "v3_Multimodal/src/sap/__init__.py": "8dc63e28ffcf93dcdfde7facd0cf1d51b6e6c15ac4de2304de61c12ccb7a5306",
    "v3_Multimodal/src/sap/consensus.py": "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91",
    "v3_Multimodal/src/sap/metrics.py": "a7d3fe4fe9e87983b35b086b0c464bde1e710e013f98813a2f28a2b48c8b2004",
    "v3_Multimodal/src/sap/rqint.py": "eb842bc98140e9c55b67bc1563cd5573c3b294885778f23744468b712c498b26",
    "v3_Multimodal/src/sap/bootstrap.py": "05437c516e606a053e02acefb23c2597365472201b6c70ff2814278d6597a31e",
    "v3_Multimodal/src/sap/decision.py": "f688b20d816acabe17c2906cfa846c1f794ba45a416248c08aa7e41676e82a92",
    "v3_Multimodal/src/sap/redaction.py": "4d4bf221141fbc793a2bc9c9989906a5c072d7f3e0e49be495cf79d67a5b580c",
    "v3_Multimodal/src/confirmatory_oof_rep1.py": "afb894c09fdaad6f1c75df789c5e2ede1dbbc2151a8c30b8eda6044cd6f336b6",
    "v3_Multimodal/src/ladder_confirmatory.py": "13a17129db6a6679bd6dbdc28a12c0f31e2e8d6b0811130450add602daf5137c",
    "v3_Multimodal/src/compute_lock.py": "b03a0b0012948b340f410670d6b045f279e1b21b4faa293bb45bbc2e99a6d738",
}
# 입력 (정본: GIN = consensus manifest_public · RF = first_look_log.json 인덱스 6 · leverage = manifest_public)
GIN_CONS_DIR = "experiments/runs/v3_gin_confirm_consensus_rep123"
GIN_MANIFEST_PUBLIC_SHA256 = "768f7267bf8c033ccb3830838e7501d18605fb19d2630061723bafebd7a259dd"
GIN_SHA = {
    "consensus_M1b_seed42.npz": "9b5f16ac16c1d857f89291ebec21e2ea15e287d07edd784089db39521973a025",
    "consensus_M1b_seed1.npz": "1bdf93519825873936762d4fe9c4b8e16ab67a543a2921b807ae686a4ae9cf29",
    "consensus_M1b_seed2.npz": "32a5f1bc701e2f102d0726dfaefa86e9ca862ec316ba6964a25bf0494b642425",
    "consensus_M2b_seed42.npz": "b36ff282b410295bb7170ee2f87c3574d0046765c15ee1c76ba62b4a26c1df5b",
    "consensus_M2b_seed1.npz": "9ae11e2d072da87b18b7c5458f9f0b4414600d22179ce674898303b1bc4ebd28",
    "consensus_M2b_seed2.npz": "03a0db458b4d4f4808041f1610e0870b57acaaf5996a5a20b584b82043674265",
}
RF_CONS_DIR = "experiments/runs/v3_consensus_rep123"
FIRST_LOOK_LOG = "experiments/provenance/first_look_log.json"
FIRST_LOOK_RF_INDEX = 6
RF_SHA = {
    "consensus_M1b.npz": "f77a69528ebdb88cd0d03c0c87489d6381740e3b9f9746378cc0396618ebfa96",
    "consensus_M2b.npz": "8594592e2afae5835f43be63d6bdc815a6933d25388b9c3c4091637117c435bf",
}
LEV_DIR = "experiments/runs/v3_rqint_leverage_d11"
LEV_MANIFEST_PUBLIC_SHA256 = "d799e7e89a599704b699b76cbac1237f3c7297aaade07c748db69179ea5ab965"
LEV_NAME = "leverage_diagnostics.json"
LEV_SHA256 = "0832ef65aa59c16973f5776c9dbcd917cb9e0b4b76202a64e271f357fb5206ac"
LEV_HEX_KEY = "T_obs_hex"
FLAG_FILES = ("v3_Multimodal/config/rqint_procedure_decisions_v1.json",
              "v3_Multimodal/config/gin_seed_freeze.json", "v3_Multimodal/config/gin_inner_valid_freeze.json")
UNBLIND_FILES = ("v3_Multimodal/config/post_interim_freeze_v1_0.status.json",
                 "v3_Multimodal/config/gin_train_contract.json",
                 "experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json")

OUT_REL = "experiments/runs/v3_rqint_holm8"
OUT_GLOB = "experiments/runs/v3_rqint_holm8*"
SELFTEST_OUT = "experiments/runs/v3_holm8_harness_selftest/selftest_holm8.json"
CONF_PREFIXES = ["experiments/runs/v3_gin_confirm_rep1_seed201", "experiments/runs/v3_gin_confirm_rep2_seed202",
                 "experiments/runs/v3_gin_confirm_rep3_seed203"]
STABILITY_PREFIX = "experiments/runs/v3_gin_stability"
GROUPS = {"conf": CONF_PREFIXES, "stab": [STABILITY_PREFIX], "gincons": [GIN_CONS_DIR], "lev": [LEV_DIR],
          "new": [OUT_REL]}
INPUT_ACCESS_LOGS = {"rf": RF_CONS_DIR + "/_sealed/access.log", "gincons": GIN_CONS_DIR + "/_sealed/access.log",
                     "lev": LEV_DIR + "/_sealed/access.log"}
RUN_CONSTS = {
    "counts_before": {"n_sealed_dirs": 31, "n_sealed_files_total": 752, "n_sealed_artifacts": 730, "n_access_log": 22},
    "counts_after": {"n_sealed_dirs": 32, "n_sealed_files_total": 757, "n_sealed_artifacts": 734, "n_access_log": 23},
    "fp_start": {"old25": "6fe853b31a987660593171acb660c4c5a97b5b6b952d96f39ff05e9e781fd9b8",
                 "conf": "6ed86c86830b664916c80c13fc2b0f355528c963df5b66e9053184316e51a8b9",
                 "stab": "b4b493d265824709a242a12d37334659bf78a75bd51a46f8b0174f058d6e6cec",
                 "gincons": "dac246845ed2fbc6b29518c816a39c029478ff14b1550b9de6475d56f9df9ebf",
                 "lev": "b19c3e9c369a8f6bb236d324b440024e07adeb67bb718bd30bd52f72fcc3fd4f"},
    "fp_noacc": {"old25": "7b617e1ccf2b3f377204df5c8504906a60cdb06269aa268d813179df7fcbb7d3",
                 "gincons": "d061293d808f8e216d5bc08322eee19929573eba94f14407a0c8e6d68f2ebe95",
                 "lev": "ed9b860561880707c500e49f8d01c8bf4e3e5a263502b79c79d6e7335b3c179c"},
    "old25_acc_other": "440226aa6e4cb4de49d80ba118fabff74855059606340d719f1372b1b957afe4",
    "acc_start_bytes": {"rf": 8946, "gincons": 895, "lev": 323},
}
NEW_SEALED_NAMES = ("access.log", "checkpoint.npz", "t_star.npy", "holm8_result.json", "d9_bca_result.json")
PROVENANCE_RUN = "confirmatory_sealed"
PROVENANCE_SYN = "synthetic_fixture"

COIN_SEED = 2967772708
AUDIT_SEED_OFFSET = 1_000_003              # sap.rqint.rqint_test 규약 (seed + 1_000_003)
CKPT_EVERY = 1000
ADAPTER_MIN_W = 90
AUDIT_TOL = 1e-12                          # sap.rqint.rqint_test 축자
EXIT_OK, EXIT_CRASH, EXIT_LOCK_BUSY, EXIT_LOAD, EXIT_HARD, EXIT_POWER = 0, 1, 9, 10, 13, 15
N_PT = 370
N_DRUGS = 1092
FORBIDDEN_TOKENS_SEALED = ("sign", "direction", "positive", "negative")
FORBIDDEN_TOKENS_PUBLIC = ("delta", "obs", "p", "pvalue", "sign", "direction", "positive", "negative", "ci", "bca",
                           "boot", "star", "macro", "ap", "se", "count", "lambda", "rho", "perm")
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


def _abs(rel, root=None):
    return os.path.join(root or ROOT, rel)


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class InvalidRun(Exception):
    """무효 규칙(값 무관) 발동 → EXIT_HARD. 메시지 = 규칙 이름 + 위치뿐(값 0)."""

    def __init__(self, rule, where=""):
        self.rule = rule
        super().__init__("[무효] %s :: %s" % (rule, where))


class HarnessAbort(Exception):
    """게이트·구조 결함(값 무관) → EXIT_HARD."""


class HarnessCrash(Exception):
    """R2 이후 비-무효 예외(메시지 비공개) → EXIT_CRASH(감시 래퍼 재기동 대상)."""


class PowerLoss(Exception):
    """체크포인트·BCa 경계에서 AC 아님 → EXIT_POWER."""


class _Fault(BaseException):
    """selftest 전용 강제 중단(크래시 모의)."""


RULE_SHA = "입력 sha 불일치"
RULE_ORDER = "행 순서/cid 불일치"
RULE_NONFINITE = "비유한 값"
RULE_G = "군 수 G 불일치"
RULE_NMATS = "행렬 수 불일치"
RULE_TOBS = "T_obs 비트 불일치"
RULE_CKPT = "체크포인트 무결성"
RULE_IDENTITY = "항등식 경로 count != 2c"
RULE_REDO = "재진입 재계산 바이트 불일치"
RULE_END = "종료 봉인 계수·지문 불일치"


def _faults(fault):
    if fault is None:
        return ()
    return (fault,) if isinstance(fault, str) else tuple(fault)


def _fault_int(fault, prefix):
    for f in _faults(fault):
        if f.startswith(prefix + ":"):
            return int(f.split(":", 1)[1])
    return None


def exit_code_for(exc):
    if isinstance(exc, (InvalidRun, HarnessAbort)):
        return EXIT_HARD
    if isinstance(exc, PowerLoss):
        return EXIT_POWER
    if isinstance(exc, SystemExit):
        return exc.code if isinstance(exc.code, int) else EXIT_CRASH
    return EXIT_CRASH


def _verify_then_import():
    for rel, sha in PRE_IMPORT_SHA.items():
        if sha256_file(_abs(rel)) != sha:
            raise HarnessAbort("import 전 sha 불일치: " + rel)


_verify_then_import()
from sap import rqint as sr                           # noqa: E402
from sap import bootstrap as sb                       # noqa: E402
from confirmatory_oof_rep1 import scaffold_of         # noqa: E402  F-SCAF 재사용
import compute_lock as cl                             # noqa: E402


def load_json_checked(rel, sha, root=None):
    b = _read_bytes(_abs(rel, root))
    if sha256_bytes(b) != sha:
        raise HarnessAbort("sha 불일치: " + rel)
    return json.loads(b.decode("utf-8"))


def spec_terms(spec, a1, a2, decisions, b100k):
    """명세·사이드카에서 B·참조분포·감사 수·S5 호출 규약·주 p 식·arm·s↔t·G 를 읽는다(재기술 0)."""
    s1, s2, s4, s5 = (spec["S1_metrics_contract"], spec["S2_d11_leverage"], spec["S4_holm8_main_run"],
                      spec["S5_d9_delta_bca"])
    m = re.match(r"\s*(\S+)\s*−\s*(\S+)", s1["cells_frozen_here_no_additions_later"]["delta_direction"])
    hi, lo = m.group(1), m.group(2)
    s_to_t = {int(k): int(v) for k, v in s1["notation_freeze"]["s_is_order_index"].items()}
    closure = [c for c in decisions["closures"] if c["id"] == "b_monte_carlo_sample_size_and_definition"][0]
    n_audit_default = inspect.signature(sr.rqint_test).parameters["complement_audit_draws"].default
    return {"B": int(s4["B"]), "n_reference": int(s4["reference_distribution"]),
            "pair_complement": bool(s4["pair_complement"]),
            "B_amend1": int(a1["decision"]["B"]), "closure": closure,
            "n_audit": int(n_audit_default),
            "n_audit_b100k": int(b100k["run_config"]["complement_audit_draws"]),
            "bca": dict(s5["call_convention"]), "bca_operator": s5["operator"],
            "primary_p_rule": a1["decision"]["primary_p"], "secondary_rule": a1["decision"]["secondary_sealed"],
            "mc_se_rule": a1["decision"]["mc_se"],
            "coin_seed": int(a2["coin_seed"]["value"]), "audit_seed": int(a2["coin_seed"]["audit_seed"]),
            "coin_label": a2["coin_seed"]["label"],
            "arms": (lo, hi), "s_to_t": s_to_t, "seeds": sorted(s_to_t),
            "gin_file": s1["outputs"]["consensus_files"].split("/", 1)[1],
            "n_mats": int(s2["inputs"]["consensus_matrices"]), "G": int(s2["inputs"]["scaffold_group"]),
            "executed_S4": s4["executed_in_block"], "executed_S5": s5["executed_in_block"],
            "d14": s4["adjudication"]["D14_dual_reporting"], "d17": s4["adjudication"]["D17"]}


def coin_seed_from_label(label):
    return int(hashlib.sha256(label.encode("ascii")).hexdigest(), 16) % 2 ** 32


def _append_line(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _atomic_via_tmp(tmp_dir, dest, data):
    tmp = os.path.join(tmp_dir, os.path.basename(dest) + ".partial")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)


def _keys_recursive(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _keys_recursive(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys_recursive(v)


def _bad_keys(obj, tokens):
    return sorted({k for k in _keys_recursive(obj) if set(k.lower().split("_")) & set(tokens)})


def _assert_no_key_tokens(obj, tokens, what):
    bad = _bad_keys(obj, tokens)
    if bad:
        raise HarnessAbort("금지 키 토큰(%s): %s" % (what, ",".join(bad)))


def _json_safe(o):
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _json_bytes(obj):
    return (json.dumps(_json_safe(obj), indent=2, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
            ).encode("utf-8")


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


def _sealed_lines(root, prefixes, exclude, access="all", skip=()):
    out = []
    for dp, _dn, fn in os.walk(root):
        parts = dp.split(os.sep)
        if ".git" in parts or "_sealed" not in parts:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            hit = any(rel.startswith(pre + os.sep) for pre in prefixes)
            if hit == exclude:
                continue
            if access == "exclude" and f == "access.log":
                continue
            if access == "only" and f != "access.log":
                continue
            if rel in skip:
                continue
            out.append("%s\t%d" % (rel, os.path.getsize(p)))
    out.sort()
    return out


def _fp(lines):
    return sha256_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def fingerprints(root, groups=GROUPS):
    allg = [p for v in groups.values() for p in v]
    return {"old25": _fp(_sealed_lines(root, allg, exclude=True)),
            "conf": _fp(_sealed_lines(root, groups["conf"], exclude=False)),
            "stab": _fp(_sealed_lines(root, groups["stab"], exclude=False)),
            "gincons": _fp(_sealed_lines(root, groups["gincons"], exclude=False)),
            "lev": _fp(_sealed_lines(root, groups["lev"], exclude=False))}


def snapshot_consts(root, groups=GROUPS, access_logs=INPUT_ACCESS_LOGS):
    """착수 상수 스냅샷(run 상수와 같은 규칙). selftest 는 fixture 에, Q1 은 실저장소에 적용한다."""
    allg = [p for v in groups.values() for p in v]
    before = sealed_counts(root)
    after = dict(before)
    after["n_sealed_dirs"] += 1
    after["n_sealed_files_total"] += len(NEW_SEALED_NAMES)
    after["n_sealed_artifacts"] += len(NEW_SEALED_NAMES) - 1
    after["n_access_log"] += 1
    return {"counts_before": before, "counts_after": after, "fp_start": fingerprints(root, groups),
            "fp_noacc": {"old25": _fp(_sealed_lines(root, allg, True, "exclude")),
                         "gincons": _fp(_sealed_lines(root, groups["gincons"], False, "exclude")),
                         "lev": _fp(_sealed_lines(root, groups["lev"], False, "exclude"))},
            "old25_acc_other": _fp(_sealed_lines(root, allg, True, "only", skip=(access_logs["rf"],))),
            "acc_start_bytes": {k: os.path.getsize(_abs(v, root)) for k, v in access_logs.items()}}


def _lock_holder_alive(root):
    p = os.path.join(root, "experiments", "runs", ".compute_lock.json")
    if not os.path.exists(p):
        return False
    try:
        pid = json.loads(_read_bytes(p).decode("utf-8")).get("pid")
    except ValueError:
        return False
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def r0_gate(root, mode, K, groups=GROUPS, access_logs=INPUT_ACCESS_LOGS, out_rel=OUT_REL):
    """R0 봉인 게이트 → (fails 리스트, busy 불리언). 파일 내용 열기 0(stat·이름·바이트)."""
    fails = []
    fp = fingerprints(root, groups)
    allg = [p for v in groups.values() for p in v]
    others = [g for g in glob.glob(os.path.join(root, out_rel) + "*") if os.path.abspath(g) != _abs(out_rel, root)]
    if others:
        fails.append("접두어 디렉터리 선존재")
    if mode == "first":
        if sealed_counts(root) != K["counts_before"]:
            fails.append("봉인 계수(착수)")
        for k in ("old25", "conf", "stab", "gincons", "lev"):
            if fp[k] != K["fp_start"][k]:
                fails.append("지문 " + k)
        return fails, _lock_holder_alive(root)
    # reentry — 락 부재 검사 생략(stale 락은 ComputeLock 의 dead-pid 인수에 맡긴다)
    for k in ("conf", "stab"):
        if fp[k] != K["fp_start"][k]:
            fails.append("지문 " + k)
    if _fp(_sealed_lines(root, allg, True, "exclude")) != K["fp_noacc"]["old25"]:
        fails.append("기존 25트리 access 제외 지문")
    for k in ("gincons", "lev"):
        if _fp(_sealed_lines(root, groups[k], False, "exclude")) != K["fp_noacc"][k]:
            fails.append(k + " access 제외 지문")
    if _fp(_sealed_lines(root, allg, True, "only", skip=(access_logs["rf"],))) != K["old25_acc_other"]:
        fails.append("기존 25트리 기타 access.log")
    for k, rel in access_logs.items():
        if os.path.getsize(_abs(rel, root)) < K["acc_start_bytes"][k]:
            fails.append("access.log 바이트 감소 " + k)
    sealed = os.path.join(_abs(out_rel, root), "_sealed")
    names = set(os.listdir(sealed)) if os.path.isdir(sealed) else set()
    if "access.log" not in names or not names <= set(NEW_SEALED_NAMES):
        fails.append("신규 트리 파일 이름 집합")
    c, b = sealed_counts(root), K["counts_before"]
    if not (c["n_sealed_dirs"] == b["n_sealed_dirs"] + 1 and c["n_access_log"] == b["n_access_log"] + 1
            and 0 <= c["n_sealed_artifacts"] - b["n_sealed_artifacts"] <= len(NEW_SEALED_NAMES) - 1):
        fails.append("봉인 계수(재진입)")
    return fails, False


def power_status():
    """pmset 판독 — AC 이고 어댑터 Wattage ≥ 90 이면 ok. (stage_run·status 전용)"""
    ps = subprocess.run(["pmset", "-g", "ps"], capture_output=True, text=True, timeout=30).stdout
    ad = subprocess.run(["pmset", "-g", "adapter"], capture_output=True, text=True, timeout=30).stdout
    m = re.search(r"Wattage\s*=\s*(\d+)", ad)
    watt = int(m.group(1)) if m else None
    return {"ac": "AC Power" in ps, "wattage": watt,
            "ok": bool("AC Power" in ps and watt is not None and watt >= ADAPTER_MIN_W)}


# ═══════════════════════════════════════════════════════════════════════════
# V2 — GIN 복합 부트스트랩 (동결 내부 함수의 조립 · 재구현 0)
# ═══════════════════════════════════════════════════════════════════════════
def gin_composite_bca(pairs, y, scaffold_group, eligible_pt, B, seed, unit, alpha, progress=None,
                      return_boot=False):
    """pairs = [(C_M1b_s, C_M2b_s) for s in 1..S] (s 순서 고정). 사이드카 2호 `gin_bca_composite` 축자 구현."""
    if unit != "scaffold_cluster":
        raise HarnessAbort("GIN 복합 BCa 는 scaffold_cluster 전용")
    pairs = [(np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)) for a, b in pairs]
    y = np.asarray(y)
    N = y.shape[0]
    uniq, rows_by_cluster = sb._cluster_index(scaffold_group)
    n_clusters = len(uniq)
    all_rows = np.arange(N)
    obs_s = [sb._delta_on_rows(a, b, y, all_rows, eligible_pt)[0] for a, b in pairs]
    delta_obs = float(np.mean(obs_s))
    rng = np.random.default_rng(seed)
    idx_range = np.arange(n_clusters)
    boot = np.empty(B, dtype=np.float64)
    for bb in range(B):
        picks = rng.choice(idx_range, size=n_clusters, replace=True, p=None)
        rows = np.concatenate([rows_by_cluster[i] for i in picks])
        boot[bb] = np.mean([sb._delta_on_rows(a, b, y, rows, eligible_pt)[0] for a, b in pairs])
        if progress is not None and (bb + 1) % 1000 == 0:
            progress("boot", bb + 1)
    jack = np.empty(n_clusters, dtype=np.float64)
    for i in range(n_clusters):
        keep = np.concatenate([rows_by_cluster[k] for k in range(n_clusters) if k != i])
        jack[i] = np.mean([sb._delta_on_rows(a, b, y, keep, eligible_pt)[0] for a, b in pairs])
    bca = sb._bca_ci(boot, delta_obs, jack, alpha=alpha)
    pct_lo, pct_hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    ok = bca["status"] == "bca"
    out = {"unit": unit, "B": int(B), "seed": int(seed), "alpha": float(alpha), "n_clusters": int(n_clusters),
           "n_seeds": len(pairs), "delta_obs": delta_obs, "delta_obs_per_seed": [float(v) for v in obs_s],
           "ci_bca": {"low": bca["low"], "high": bca["high"], "status": bca["status"],
                      "jackknife_unit": "scaffold delete-one"},
           "ci_percentile": {"low": float(pct_lo), "high": float(pct_hi),
                             "note": "sensitivity 보고용 — primary 대체 금지(사이드카 2호)"},
           "primary_ci_method": sb.PRIMARY_CI_METHOD,
           "ci_primary": ({"low": bca["low"], "high": bca["high"], "status": "estimable", "bca_status": bca["status"]}
                          if ok else {"low": float("nan"), "high": float("nan"), "status": "not_estimable",
                                      "bca_status": bca["status"]}),
           "boot_summary": {"mean": float(np.mean(boot)), "sd": float(np.std(boot, ddof=1))},
           "bca_diagnostics": {"acceleration": bca["acceleration"],
                               "acceleration_finite": bool(bca["acceleration_finite"]), "z0": bca["z0"],
                               "adj_quantile_low": bca["adj_q_low"], "adj_quantile_high": bca["adj_q_high"],
                               "adj_quantile_saturated_01": bool(bca["quantile_saturated"])}}
    if return_boot:
        out["boot"] = boot
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 체크포인트
# ═══════════════════════════════════════════════════════════════════════════
CKPT_BASE_KEYS = {"phase", "t_star", "t_star_sha", "b_done", "rng_state_json", "audit_done", "audit_fail",
                  "audit_max_abs", "coin_seed", "run_id", "input_sha_json"}
CKPT_FB_KEYS = {"comp", "comp_sha", "k_done", "rng_fb_state_json"}


def _rng_state_json(rng):
    return json.dumps(rng.bit_generator.state, sort_keys=True)


def _load_ckpt(path, run_id, coin_seed, in_sha_json, B):
    """내부 무결성만으로 판정(heartbeat sha 와의 일치는 요구하지 않는다)."""
    try:
        with np.load(path, allow_pickle=False) as z:
            d = {k: z[k] for k in z.files}
    except Exception:              # noqa: BLE001
        raise InvalidRun(RULE_CKPT, "판독 불가") from None
    phase = d["phase"].item() if "phase" in d else None
    if phase not in ("coins", "fallback"):
        raise InvalidRun(RULE_CKPT, "phase")
    if set(d) != (CKPT_BASE_KEYS | (CKPT_FB_KEYS if phase == "fallback" else set())):
        raise InvalidRun(RULE_CKPT, "키 집합")
    b_done = int(d["b_done"])
    t = d["t_star"]
    if t.dtype != np.float64 or t.shape != (b_done,) or not 0 <= b_done <= B:
        raise InvalidRun(RULE_CKPT, "t_star 길이")
    if sha256_bytes(t.tobytes()) != d["t_star_sha"].item():
        raise InvalidRun(RULE_CKPT, "t_star sha")
    if int(d["coin_seed"]) != coin_seed or d["run_id"].item() != run_id:
        raise InvalidRun(RULE_CKPT, "coin_seed/run_id")
    if d["input_sha_json"].item() != in_sha_json:
        raise InvalidRun(RULE_CKPT, "입력 sha")
    out = {"phase": phase, "b_done": b_done, "t_star": t, "rng_state_json": d["rng_state_json"].item(),
           "audit_done": int(d["audit_done"]), "audit_fail": int(d["audit_fail"]),
           "audit_max_abs": float(d["audit_max_abs"])}
    if phase == "fallback":
        k_done = int(d["k_done"])
        c = d["comp"]
        if b_done != B or c.dtype != np.float64 or c.shape != (k_done,) or not 0 <= k_done <= B:
            raise InvalidRun(RULE_CKPT, "comp 길이")
        if sha256_bytes(c.tobytes()) != d["comp_sha"].item():
            raise InvalidRun(RULE_CKPT, "comp sha")
        out.update({"k_done": k_done, "comp": c, "rng_fb_state_json": d["rng_fb_state_json"].item()})
    return out


# ═══════════════════════════════════════════════════════════════════════════
# core — R0′~R7 (모든 경로를 인자로 받는다)
# ═══════════════════════════════════════════════════════════════════════════
class _Ctx:
    def __init__(self, paths):
        self.paths = paths
        self.t0 = time.perf_counter()
        self.out_dir = paths["out_dir"]
        self.sealed = os.path.join(self.out_dir, "_sealed")
        self.tmpd = os.path.join(self.out_dir, "_tmp")
        self.hb = os.path.join(self.out_dir, "heartbeat.jsonl")
        self.runlog = os.path.join(self.out_dir, "run.log")
        self.buf = []
        self.run_id = None
        self.launch = None

    def elapsed(self):
        return round(time.perf_counter() - self.t0, 1)

    def step(self, tag, msg):
        line = "%s\t%s\t%s" % (now_kst(), tag, msg)
        print(line, flush=True)
        self.buf.append(line)
        if os.path.isdir(self.out_dir):
            with open(self.runlog, "a", encoding="utf-8") as f:
                f.write("\n".join(self.buf) + "\n")
            self.buf = []

    def heartbeat(self, event, **kw):
        rec = {"ts_kst": now_kst(), "run_id": self.run_id, "event": event}
        if self.launch is not None:
            rec["launch"] = self.launch
        rec.update(kw)
        _append_line(self.hb, rec)

    def sealed_access(self, purpose, step, note):
        _append_line(os.path.join(self.sealed, "access.log"), {
            "ts_kst": now_kst(), "type": "machine_read", "purpose": purpose, "human_exposure": False,
            "path": "_sealed/", "actor": "vscode-claude", "step": step, "run_id": self.run_id, "note": note})


def _hb_events(hb_path):
    if not os.path.exists(hb_path):
        return []
    out = []
    with open(hb_path, encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                out.append(json.loads(ln))
    return out


def core(paths, fault=None):
    """paths = {root, out_dir, mode, run_id, master_x, master_y, master_sha{x,y}, n_rows, n_pt, n_groups,
               rf_dir, gin_dir, lev_dir, input_sha{name: sha}, lev_sha, T, B, n_audit, ckpt_every,
               coin_seed, audit_seed, bca{unit,alpha,B,seed}, power_check, consts, groups, access_logs,
               provenance, public_meta{}}."""
    ctx = _Ctx(paths)
    T = paths["T"]
    mode = paths["mode"]
    # ── R0′ / 재진입 준비 ──
    if mode == "first":
        if os.path.exists(ctx.out_dir):
            raise HarnessAbort("first 모드인데 출력 디렉터리 선존재")
        ctx.run_id = paths["run_id"]
        os.mkdir(ctx.out_dir)
        ctx.heartbeat("tree_created", mode="first")
        os.mkdir(ctx.sealed)
        os.mkdir(ctx.tmpd)
        ctx.sealed_access("Holm8 main run tree created", "블록 AY(docs/115) R0′",
                          "신규 봉인 트리 생성. 값 0. 사람 열람 0.")
        ctx.step("R0'", "mode first · tree created (out/_sealed/_tmp)")
    else:
        if not os.path.isdir(ctx.out_dir) or not os.path.isdir(ctx.sealed):
            raise HarnessAbort("reentry 모드인데 출력 트리 부재")
        ev = _hb_events(ctx.hb)
        if not ev or not ev[0].get("run_id"):
            raise HarnessAbort("heartbeat run_id 부재")
        ctx.run_id = ev[0]["run_id"]
        os.makedirs(ctx.tmpd, exist_ok=True)
        n_clean = 0
        for f in sorted(os.listdir(ctx.tmpd)):
            p = os.path.join(ctx.tmpd, f)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except PermissionError:
                    os.makedirs(os.path.join(ctx.tmpd, "_stale"), exist_ok=True)
                    os.replace(p, os.path.join(ctx.tmpd, "_stale", f))
                n_clean += 1
        names = set(os.listdir(ctx.sealed))
        if not names <= set(NEW_SEALED_NAMES) or "access.log" not in names:
            raise HarnessAbort("신규 봉인 트리 파일 이름 집합 불일치")
        ctx.heartbeat("reentry", tmp_cleaned=n_clean)
        ctx.step("R0", "mode reentry · tmp cleaned %d" % n_clean)

    # ── R1 설계량 ──
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
    y = Y[ycols].values.astype(int)                    # 블록 AW·AX 축자 동일
    cid_order = np.asarray(cid_list, dtype=np.int64)
    n_rows, n_pt = int(paths["n_rows"]), int(paths["n_pt"])
    if y.shape != (n_rows, n_pt):
        raise InvalidRun(RULE_ORDER, "라벨 shape")
    scaf = [scaffold_of(s) for s in X["smiles_canonical"].tolist()]
    groups = np.array(scaf)                            # rqint_test 경로(np.unique 정렬)
    uniq = sorted(set(scaf))
    gidx = {g: i for i, g in enumerate(uniq)}
    gi = np.array([gidx[s] for s in scaf], dtype=int)  # bootstrap 경로(sorted(set) 정렬 — 동일 순서)
    if len(uniq) != int(paths["n_groups"]) or len(np.unique(groups)) != len(uniq):
        raise InvalidRun(RULE_G, "scaffold 군 수")
    ctx.step("R1", "design · rows %d · PT %d · groups %d" % (y.shape[0], y.shape[1], len(uniq)))

    lo, hi = T["arms"]
    plan = []
    for arm in (lo, hi):
        plan.append((("RF", None, arm), os.path.join(paths["rf_dir"], "consensus_%s.npz" % arm)))
        for s in T["seeds"]:
            t = T["s_to_t"][s]
            plan.append((("GIN", t, arm), os.path.join(paths["gin_dir"], T["gin_file"].format(model=arm, t=t))))
    lev_path = os.path.join(paths["lev_dir"], LEV_NAME)
    if len(plan) != T["n_mats"] or not all(os.path.exists(p) for _k, p in plan):
        raise InvalidRun(RULE_NMATS, "consensus 행렬")
    if not os.path.exists(lev_path):
        raise InvalidRun(RULE_SHA, "leverage 부재")

    # ── R2 판독 기록 (R2 에 도달한 실행마다) ──
    ctx.launch = 1 + sum(1 for e in _hb_events(ctx.hb) if e.get("event") == "r2_started")
    ctx.heartbeat("r2_started")
    for d in (paths["rf_dir"], paths["gin_dir"], paths["lev_dir"]):
        _append_line(os.path.join(d, "access.log"), {
            "ts_kst": now_kst(), "type": "machine_read", "purpose": "Holm8 main run input",
            "human_exposure": False, "path": "_sealed/", "actor": "vscode-claude",
            "step": "블록 AY(docs/115) R3 · launch %d" % ctx.launch, "run_id": ctx.run_id,
            "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."})
    ctx.heartbeat("r2_complete")
    ctx.step("R2", "access.log +1 line · RF consensus 1 · GIN consensus 1 · leverage 1 · launch %d" % ctx.launch)
    if "crash_after_r2" in _faults(fault):
        raise _Fault()
    try:
        return _core_after_r2(ctx, paths, fault, T, plan, lev_path, y, cid_order, n_rows, n_pt, groups, gi)
    except (InvalidRun, HarnessAbort, PowerLoss, _Fault):
        raise
    except Exception as e:           # 값 누설 방지 — 예외 메시지를 버리고 형식만 남긴다
        raise HarnessCrash("R2 이후 예외(메시지 비공개): " + type(e).__name__) from None


def _core_after_r2(ctx, paths, fault, T, plan, lev_path, y, cid_order, n_rows, n_pt, groups, gi):
    lo, hi = T["arms"]
    # ── R3 입력 ──
    loaded, in_sha = {}, {}
    for key, p in plan:
        name = os.path.basename(p)
        b = _read_bytes(p)
        if sha256_bytes(b) != paths["input_sha"][name]:
            raise InvalidRun(RULE_SHA, name)
        with np.load(io.BytesIO(b), allow_pickle=False) as z:
            if set(z.files) != {"consensus", "cid"}:
                raise InvalidRun(RULE_SHA, name + " 키 집합")
            C, cid = z["consensus"], z["cid"]
        if C.shape != (n_rows, n_pt):
            raise InvalidRun(RULE_ORDER, name + " shape")
        if not bool(np.isfinite(C).all()):
            raise InvalidRun(RULE_NONFINITE, name)
        if not np.array_equal(np.asarray(cid, dtype=np.int64), cid_order):
            raise InvalidRun(RULE_ORDER, name + " cid")
        loaded[key] = C.astype(np.float64)
        in_sha[("rf/" if key[0] == "RF" else "gin/") + name] = sha256_bytes(b)
    P_RF = {arm: [loaded[("RF", None, arm)]] for arm in (lo, hi)}
    P_GIN = {arm: {s: [loaded[("GIN", T["s_to_t"][s], arm)]] for s in T["seeds"]} for arm in (lo, hi)}
    mats, seeds = sr.build_eight_consensus(P_RF, P_GIN)
    if len(mats) != T["n_mats"] or list(seeds) != list(T["seeds"]):
        raise InvalidRun(RULE_NMATS, "mats")
    lb = _read_bytes(lev_path)
    if sha256_bytes(lb) != paths["lev_sha"]:
        raise InvalidRun(RULE_SHA, LEV_NAME)
    LD = json.loads(lb.decode("utf-8"))
    t_obs_hex_ref = LD[LEV_HEX_KEY]
    del LD, lb                                       # T_obs_hex 1키 외 즉시 폐기
    in_sha["leverage/" + LEV_NAME] = paths["lev_sha"]
    in_sha["master_X"], in_sha["master_Y"] = paths["master_sha"]["x"], paths["master_sha"]["y"]
    in_sha_json = json.dumps(in_sha, sort_keys=True)
    ctx.step("R3", "inputs verified · matrices %d · leverage 1" % len(mats))

    # ── R4a T_obs 비트 대조 ──
    eligible = np.arange(n_pt)
    t_obs, d_rf, d_gin, d_gin_s = sr.observed_statistic(mats, seeds, y, eligible)
    if not all(np.isfinite(v) for v in [t_obs, d_rf, d_gin] + list(d_gin_s)):
        raise InvalidRun(RULE_NONFINITE, "T_obs/Δ")
    if float(t_obs).hex() != float.fromhex(t_obs_hex_ref).hex():
        raise InvalidRun(RULE_TOBS, "블록 AX T_obs_hex")
    ctx.heartbeat("t_obs_verified")
    ctx.step("R4a", "T_obs bit-equal to block AX record")

    # ── R4b 동전 루프 (재개 가능) ──
    B, ck_every = int(paths["B"]), int(paths["ckpt_every"])
    coin_seed, audit_seed = int(paths["coin_seed"]), int(paths["audit_seed"])
    uniq = np.unique(groups)
    gi_of_row = np.searchsorted(uniq, groups)
    G = len(uniq)
    n_audit = int(min(paths["n_audit"], B))
    audit_rng = np.random.default_rng(audit_seed)
    audit_idx = set(audit_rng.choice(B, size=n_audit, replace=False).tolist()) if n_audit > 0 else set()
    ck_path = os.path.join(ctx.sealed, "checkpoint.npz")
    t_star = np.empty(B, dtype=np.float64)
    comp = np.empty(B, dtype=np.float64)
    st = {"phase": "coins", "b_done": 0, "k_done": 0, "audit_done": 0, "audit_fail": 0, "audit_max_abs": 0.0}
    rng = np.random.default_rng(coin_seed)
    rng_fb = None
    if os.path.exists(ck_path):
        ctx.sealed_access("checkpoint resume", "블록 AY(docs/115) R4b · launch %d" % ctx.launch,
                          "체크포인트 기계 판독(재개). 값 0 공개. 사람 열람 0.")
        ck = _load_ckpt(ck_path, ctx.run_id, coin_seed, in_sha_json, B)
        for _ in range(ck["b_done"]):
            rng.random(G)
        if _rng_state_json(rng) != ck["rng_state_json"]:
            raise InvalidRun(RULE_CKPT, "난수 state")
        t_star[:ck["b_done"]] = ck["t_star"]
        st.update({k: ck[k] for k in ("phase", "b_done", "audit_done", "audit_fail", "audit_max_abs")})
        if ck["phase"] == "fallback":
            rng_fb = np.random.default_rng(coin_seed)
            for _ in range(ck["k_done"]):
                rng_fb.random(G)
            if _rng_state_json(rng_fb) != ck["rng_fb_state_json"]:
                raise InvalidRun(RULE_CKPT, "폴백 난수 state")
            comp[:ck["k_done"]] = ck["comp"]
            st["k_done"] = ck["k_done"]
        del ck
        ctx.heartbeat("checkpoint_resume", phase=st["phase"], b_done=st["b_done"], k_done=st["k_done"])
        ctx.step("R4b", "resume · phase %s · coins %d/%d · fallback %d" % (st["phase"], st["b_done"], B, st["k_done"]))
    else:
        ctx.step("R4b", "start · coins 0/%d" % B)

    def save_ckpt():
        arr = {"phase": np.array(st["phase"]), "t_star": t_star[:st["b_done"]].copy(),
               "t_star_sha": np.array(sha256_bytes(t_star[:st["b_done"]].tobytes())),
               "b_done": np.array(st["b_done"], dtype=np.int64), "rng_state_json": np.array(_rng_state_json(rng)),
               "audit_done": np.array(st["audit_done"], dtype=np.int64),
               "audit_fail": np.array(st["audit_fail"], dtype=np.int64),
               "audit_max_abs": np.array(st["audit_max_abs"], dtype=np.float64),
               "coin_seed": np.array(coin_seed, dtype=np.int64), "run_id": np.array(ctx.run_id),
               "input_sha_json": np.array(in_sha_json)}
        if st["phase"] == "fallback":
            arr.update({"comp": comp[:st["k_done"]].copy(),
                        "comp_sha": np.array(sha256_bytes(comp[:st["k_done"]].tobytes())),
                        "k_done": np.array(st["k_done"], dtype=np.int64),
                        "rng_fb_state_json": np.array(_rng_state_json(rng_fb))})
        tmp = os.path.join(ctx.tmpd, "checkpoint.npz.partial")
        with open(tmp, "wb") as f:
            np.savez(f, **arr)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ck_path)
        mark = st["b_done"] if st["phase"] == "coins" else B + st["k_done"]
        if _fault_int(fault, "crash_after_replace") == mark:
            raise _Fault()
        chk = _load_ckpt(ck_path, ctx.run_id, coin_seed, in_sha_json, B)       # 저장 직후 재로드 검증
        if chk["b_done"] != st["b_done"] or chk["phase"] != st["phase"]:
            raise InvalidRun(RULE_CKPT, "재로드")
        del chk
        pw = bool(paths["power_check"]())
        ctx.heartbeat("checkpoint", phase=st["phase"], b_done=st["b_done"], k_done=st["k_done"],
                      elapsed_s=ctx.elapsed(), power_ac=pw, load1=round(os.getloadavg()[0], 2),
                      ckpt_sha256=sha256_file(ck_path))
        ctx.step("R4b", "checkpoint · phase %s · coins %d/%d · fallback %d · elapsed %.1fs"
                 % (st["phase"], st["b_done"], B, st["k_done"], ctx.elapsed()))
        if not pw:
            ctx.heartbeat("power_lost")
            raise PowerLoss()

    crash_b = _fault_int(fault, "crash_at_b")
    for b in range(st["b_done"], B):
        if crash_b is not None and b == crash_b:
            raise _Fault()
        z = rng.random(G) < 0.5                        # 동전 벡터 z^(b) (rqint_test 축자)
        swap_row = z[gi_of_row]
        t_star[b] = sr.observed_statistic(sr._apply_swap(mats, seeds, swap_row), seeds, y, eligible)[0]
        if b in audit_idx:                             # 여집합 명시적 재계산(항등식 감사)
            t_c = sr.observed_statistic(sr._apply_swap(mats, seeds, ~swap_row), seeds, y, eligible)[0]
            dev = abs(t_c + t_star[b])
            if "audit_fail" in _faults(fault) and st["audit_done"] == 0:
                dev = float("nan")
            st["audit_max_abs"] = max(st["audit_max_abs"], dev)
            st["audit_done"] += 1
            if not dev < AUDIT_TOL:
                st["audit_fail"] += 1
        st["b_done"] = b + 1
        if st["b_done"] % ck_every == 0 or st["b_done"] == B:
            save_ckpt()

    identity_used = bool(T["pair_complement"] and st["audit_fail"] == 0)
    if T["pair_complement"] and st["audit_fail"] > 0:
        # 폴백 — 항등식 경로를 끄고 여집합을 명시적으로 계산한다(rqint_test 축자 · 값 무관 분기).
        if st["phase"] != "fallback":
            st["phase"], st["k_done"] = "fallback", 0
            rng_fb = np.random.default_rng(coin_seed)
        crash_k = _fault_int(fault, "crash_fb_at_k")
        for k in range(st["k_done"], B):
            if crash_k is not None and k == crash_k:
                raise _Fault()
            z = rng_fb.random(G) < 0.5
            swap_row = z[gi_of_row]
            comp[k] = sr.observed_statistic(sr._apply_swap(mats, seeds, ~swap_row), seeds, y, eligible)[0]
            st["k_done"] = k + 1
            if st["k_done"] % ck_every == 0 or st["k_done"] == B:
                save_ckpt()
    ctx.step("R4b", "coin loop complete · coins %d/%d" % (B, B))

    # ── R4c ⑧ 집계 (루프 완료 후 1회) ──
    if identity_used:
        perm = np.concatenate([t_star, -t_star])       # 항등식 T*(z̄) = −T*(z)
    else:
        perm = np.concatenate([t_star, comp])
    n_perm_values = int(perm.size)
    count = int(np.sum(np.abs(perm) >= abs(t_obs) - sr._EPS))
    c = int(np.sum(np.abs(t_star) >= abs(t_obs) - sr._EPS))
    if identity_used and count != 2 * c:
        raise InvalidRun(RULE_IDENTITY, "R4c")
    p_primary = (1.0 + c) / (B + 1.0)
    p_secondary = (1.0 + count) / (n_perm_values + 1.0)
    se_primary = float(np.sqrt(p_primary * (1.0 - p_primary) / B))
    se_secondary = float(np.sqrt(p_secondary * (1.0 - p_secondary) / B))
    ctx.step("R4c", "aggregation done (sealed only)")

    # ── R4d D9 BCa (재시작 시 처음부터 — 결정적) ──
    cc = paths["bca"]
    if not paths["power_check"]():
        ctx.heartbeat("power_lost")
        raise PowerLoss()
    ctx.heartbeat("bca_rf_started")
    ctx.step("R4d", "BCa RF start")
    rf_res = sb.paired_scaffold_bootstrap(mats[("RF", None, lo)], mats[("RF", None, hi)], y, gi,
                                          eligible_pt=eligible, B=cc["B"], seed=cc["seed"], unit=cc["unit"],
                                          alpha=cc["alpha"])
    ctx.heartbeat("bca_rf_done")
    if not paths["power_check"]():
        ctx.heartbeat("power_lost")
        raise PowerLoss()
    ctx.heartbeat("bca_gin_started")
    ctx.step("R4d", "BCa RF done · GIN composite start")

    def _prog(_what, n):
        ctx.heartbeat("bca_gin_progress", n_done=n)

    gin_res = gin_composite_bca([(mats[("GIN", s, lo)], mats[("GIN", s, hi)]) for s in seeds], y, gi, eligible,
                                cc["B"], cc["seed"], cc["unit"], cc["alpha"], progress=_prog)
    ctx.heartbeat("bca_gin_done")
    ctx.step("R4d", "BCa GIN composite done")

    # ── R6 봉인 최종 쓰기 ──
    holm = {
        "_doc": ("블록 AY (docs/115) — Holm ⑧ RQ-int 본런 봉인 산출. 개봉 전 사람 열람 금지. "
                 "Holm 조정·판정 미수행(개봉·판정 블록)."),
        "block": "AY (docs/115)", "provenance": paths["provenance"], "run_id": ctx.run_id,
        "spec_sha256": SPEC_SHA256, "amendment1_sha256": AMEND1_SHA256, "amendment2_sha256": AMEND2_SHA256,
        "t_obs": float(t_obs), "t_obs_hex": float(t_obs).hex(), "t_obs_bit_equal_block_ax": True,
        "delta_rf": float(d_rf), "delta_gin": float(d_gin),
        "delta_gin_per_seed": {"s%d|seed%d" % (s, T["s_to_t"][s]): float(d_gin_s[i]) for i, s in enumerate(seeds)},
        "B": B, "n_coin_vectors": B, "n_permutation_values": n_perm_values,
        "count_abs_ge_obs": count, "c_abs_ge_obs_first_B": c,
        "p_primary": p_primary, "p_primary_rule": T["primary_p_rule"],
        "p_secondary": p_secondary, "p_secondary_rule": T["secondary_rule"],
        "se_primary": se_primary, "se_secondary": se_secondary, "mc_se_rule": T["mc_se_rule"],
        "eps": sr._EPS, "eps_source": "sap.rqint._EPS",
        "complement_identity_used": identity_used,
        "complement_audit": {"draws_checked": st["audit_done"], "failures": st["audit_fail"],
                             "max_abs_dev": float(st["audit_max_abs"]), "tol": AUDIT_TOL,
                             "fallback_to_explicit": bool(T["pair_complement"] and st["audit_fail"] > 0)},
        "d14_dual_reporting": {"panel_1_primary_p": p_primary, "panel_2_fallback_p": 1.0,
                               "panel_1_refers_to": "주 p (사이드카 1호 U2-a)"},
        "d17_applies_if": ("D17(「실패 시 슬롯 p = 1.0」)은 개봉·판정 블록이 적용한다 — 본 블록이 EXIT_HARD·재시작 상한으로 "
                           "⑧ 을 산출하지 못한 경우에 한한다. 본 파일이 존재하면 본런은 완주한 것이다."),
        "coin_seed": coin_seed, "audit_seed": audit_seed, "n_audit": n_audit,
        "n_groups_G": int(G), "n_consensus_matrices": len(mats),
        "input_sha256": in_sha,
        "holm_adjustment_performed": False, "adjudication_performed": False,
    }
    d9 = {
        "_doc": ("블록 AY (docs/115) — D9 Δ_RF·Δ_GIN BCa 봉인 산출(S5 + 사이드카 2호 V2). 판정 미사용 · "
                 "유의성과 무관하게 항상 병기."),
        "block": "AY (docs/115)", "provenance": paths["provenance"], "run_id": ctx.run_id,
        "operator_rf": T["bca_operator"], "call_convention": cc, "eligible_pt": "np.arange(%d)" % n_pt,
        "cluster_sample_stream_shared_rf_gin": True,
        "rf": rf_res, "gin_composite": gin_res,
        "rf_delta_matches_observed_statistic": bool(float(rf_res["delta_obs"]) == float(d_rf)),
        "gin_delta_matches_observed_statistic": bool(float(gin_res["delta_obs"]) == float(d_gin)),
        "amendment2_sha256": AMEND2_SHA256,
    }
    for o, nm in ((holm, "holm8_result.json"), (d9, "d9_bca_result.json")):
        _assert_no_key_tokens(o, FORBIDDEN_TOKENS_SEALED, nm)
    buf = io.BytesIO()
    np.save(buf, t_star, allow_pickle=False)
    outputs = [("t_star.npy", buf.getvalue()), ("holm8_result.json", _json_bytes(holm)),
               ("d9_bca_result.json", _json_bytes(d9))]
    for name, data in outputs:
        dest = os.path.join(ctx.sealed, name)
        if os.path.exists(dest):
            if _read_bytes(dest) != data:
                raise InvalidRun(RULE_REDO, name)
        else:
            _atomic_via_tmp(ctx.tmpd, dest, data)
    ctx.heartbeat("sealed_written")
    ctx.step("R6", "sealed written · %d files + checkpoint + access.log" % len(outputs))

    # ── R7 공개 ──
    K = paths["consts"]
    counts_end = sealed_counts(paths["root"])
    fp_end = fingerprints(paths["root"], paths["groups"])
    if (counts_end != K["counts_after"] or fp_end["conf"] != K["fp_start"]["conf"]
            or fp_end["stab"] != K["fp_start"]["stab"]):
        raise InvalidRun(RULE_END, "R7")
    ev = _hb_events(ctx.hb)
    listing = []
    for name in NEW_SEALED_NAMES[1:]:
        p = os.path.join(ctx.sealed, name)
        listing.append({"name": "_sealed/" + name, "bytes": os.path.getsize(p), "sha256": sha256_file(p)})
    import sklearn
    try:
        from threadpoolctl import threadpool_info
        tp = [{k: d.get(k) for k in ("user_api", "internal_api", "num_threads", "version")} for d in threadpool_info()]
    except Exception:                  # noqa: BLE001
        tp = "unavailable"
    ck_ev = [e for e in ev if e.get("event") == "checkpoint"]
    pub = {
        "_doc": ("블록 AY (docs/115) 공개 manifest — 개수·환경·검증 불리언·봉인 파일 이름/바이트/sha256·시간뿐. "
                 "값은 기록하지 않는다."),
        "block": "AY (docs/115)", "provenance": paths["provenance"], "run_id": ctx.run_id,
        "n_coin_vectors": B, "n_reference": 2 * B, "n_audit": n_audit,
        "n_launches": sum(1 for e in ev if e.get("event") == "r2_started"),
        "n_resumes": sum(1 for e in ev if e.get("event") == "checkpoint_resume"),
        "n_checkpoints": len(ck_ev), "n_sealed_files": len(listing), "n_groups": int(G),
        "n_input_matrices": len(mats), "completed": True, "sealed_files": listing,
        "input_checks": {"input_sha_all_match": True, "cid_order_match": True, "finite_inputs": True,
                         "observed_hex_match_block_ax": True, "checkpoint_integrity_ok": True,
                         "sealed_end_counts_expected": True, "conf_stab_fingerprints_unchanged": True},
        "power_history": {"n_checkpoints_on_ac": sum(1 for e in ck_ev if e.get("power_ac") is True),
                          "n_power_lost": sum(1 for e in ev if e.get("event") == "power_lost")},
        "wall_seconds_last_launch": ctx.elapsed(),
        "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
        "pandas": pd.__version__, "threadpool_info": tp,
        "harness_sha256": paths["public_meta"].get("harness_sha256"),
        "watchdog_sha256": paths["public_meta"].get("watchdog_sha256"),
        "selftest_sha256": paths["public_meta"].get("selftest_sha256"),
        "spec_sha256": SPEC_SHA256, "amendment1_sha256": AMEND1_SHA256, "amendment2_sha256": AMEND2_SHA256,
        "values_disclosed": False, "unblinding_performed": False,
        "sealed_counts_end": counts_end, "ts_completed_kst": now_kst(),
    }
    _assert_no_key_tokens(pub, FORBIDDEN_TOKENS_PUBLIC, "manifest_public")
    ctx.step("R7", "public manifest · wall_seconds_last_launch %.1f" % ctx.elapsed())
    _atomic_via_tmp(ctx.tmpd, os.path.join(ctx.out_dir, "manifest_public.json"),
                    (json.dumps(pub, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    ctx.heartbeat("completed")
    return pub


# ═══════════════════════════════════════════════════════════════════════════
# stage_run — R0 게이트 + 전원 + 부하 + compute_lock
# ═══════════════════════════════════════════════════════════════════════════
def load_all_terms(root=None):
    spec = load_json_checked(SPEC_PATH, SPEC_SHA256, root)
    a1 = load_json_checked(AMEND1_PATH, AMEND1_SHA256, root)
    a2 = load_json_checked(AMEND2_PATH, AMEND2_SHA256, root)
    dec = load_json_checked(DECISIONS_PATH, DECISIONS_SHA256, root)
    b100 = load_json_checked(B100K_PRESPEC[0], B100K_PRESPEC[1], root)
    return spec, a1, a2, dec, spec_terms(spec, a1, a2, dec, b100)


def check_terms(T):
    """명세·사이드카 결속(P7) — 불일치면 HarnessAbort."""
    ok = (T["executed_S4"] == 115 and T["executed_S5"] == 115 and T["B"] == T["B_amend1"]
          and T["B"] == int(T["closure"]["proposed_resolution"]["B_value"])
          and T["n_reference"] == 2 * T["B"] and T["pair_complement"] is True
          and T["n_audit"] == T["n_audit_b100k"]
          and T["coin_seed"] == COIN_SEED == coin_seed_from_label(T["coin_label"])
          and T["audit_seed"] == COIN_SEED + AUDIT_SEED_OFFSET
          and T["bca_operator"] == "sap.bootstrap.paired_scaffold_bootstrap"
          and set(T["bca"]) == {"unit", "alpha", "B", "seed"}
          and T["primary_p_rule"] == "(1 + c) / (B + 1)" and T["n_mats"] == 8)
    if not ok:
        raise HarnessAbort("명세·사이드카 결속 불일치")


def make_paths(root, T, mode, run_id, consts, input_sha, lev_sha, master_sha, n_rows, n_pt, n_groups, power_check,
               public_meta, provenance=PROVENANCE_RUN, B=None, n_audit=None, ckpt_every=CKPT_EVERY, bca=None):
    return {"root": root, "out_dir": _abs(OUT_REL, root), "mode": mode, "run_id": run_id,
            "master_x": _abs(MASTER_X[0], root), "master_y": _abs(MASTER_Y[0], root), "master_sha": master_sha,
            "n_rows": n_rows, "n_pt": n_pt, "n_groups": n_groups,
            "rf_dir": _abs(RF_CONS_DIR + "/_sealed", root), "gin_dir": _abs(GIN_CONS_DIR + "/_sealed", root),
            "lev_dir": _abs(LEV_DIR + "/_sealed", root), "input_sha": input_sha, "lev_sha": lev_sha, "T": T,
            "B": T["B"] if B is None else B, "n_audit": T["n_audit"] if n_audit is None else n_audit,
            "ckpt_every": ckpt_every, "coin_seed": T["coin_seed"], "audit_seed": T["audit_seed"],
            "bca": dict(T["bca"]) if bca is None else bca, "power_check": power_check, "consts": consts,
            "groups": GROUPS, "access_logs": INPUT_ACCESS_LOGS, "provenance": provenance, "public_meta": public_meta}


def stage_run():
    out_dir = _abs(OUT_REL)
    mp_path = os.path.join(out_dir, "manifest_public.json")
    if os.path.exists(mp_path) and json.loads(_read_bytes(mp_path).decode("utf-8")).get("completed") is True:
        print(json.dumps({"stage": "run", "already_completed": True}, ensure_ascii=False), flush=True)
        return EXIT_OK
    _spec, _a1, _a2, _dec, T = load_all_terms()
    check_terms(T)
    # selftest 조건 (하네스·감시 래퍼 sha)
    st_path = _abs(SELFTEST_OUT)
    if not os.path.exists(st_path):
        raise HarnessAbort("selftest 결과 부재")
    st = json.loads(_read_bytes(st_path).decode("utf-8"))
    me = sha256_file(os.path.abspath(__file__))
    if not (st.get("all_pass") is True and st.get("harness_sha256") == me
            and st.get("watchdog_sha256") == sha256_file(_abs(WATCHDOG_PATH))):
        raise HarnessAbort("selftest 조건 불충족(all_pass·하네스·감시 래퍼 sha)")
    d33 = _read_bytes(_abs(DOCS33)).decode("utf-8")
    if not re.search(ITEM69_RE, d33) or AMEND2_SHA256 not in d33:
        raise HarnessAbort("docs/33 항목 69 부재 또는 사이드카 2호 sha 미기재")
    # R0 모드 판별 + 봉인 게이트
    mode = "reentry" if os.path.exists(out_dir) else "first"
    fails, busy = r0_gate(ROOT, mode, RUN_CONSTS)
    if fails:
        raise HarnessAbort("R0 게이트 실패(%s): %s" % (mode, " · ".join(fails)))
    if busy:
        print("[R0] 살아 있는 락 보유자 존재 — 대기", flush=True)
        return EXIT_LOCK_BUSY
    if [json.loads(_read_bytes(_abs(p)))["gin_start_still_blocked"] for p in FLAG_FILES] != [True] * 3:
        raise HarnessAbort("플래그 3/3 불일치")
    if [json.loads(_read_bytes(_abs(p)))["unblinding_performed"] for p in UNBLIND_FILES] != [False] * 3:
        raise HarnessAbort("unblinding_performed 불일치")
    # P6 정본 문서 3종 (봉인 파일은 존재·바이트만)
    mp = load_json_checked(GIN_CONS_DIR + "/manifest_public.json", GIN_MANIFEST_PUBLIC_SHA256)
    sf = {x["name"]: x for x in mp["sealed_files"]}
    for name, sha in GIN_SHA.items():
        ent, p = sf.get("_sealed/" + name), _abs(GIN_CONS_DIR + "/_sealed/" + name)
        if ent is None or ent["sha256"] != sha or not os.path.exists(p) or os.path.getsize(p) != ent["bytes"]:
            raise HarnessAbort("GIN 입력 정본 불일치: " + name)
    fl = json.loads(_read_bytes(_abs(FIRST_LOOK_LOG)).decode("utf-8"))[FIRST_LOOK_RF_INDEX]
    if fl["sealed_path"] != RF_CONS_DIR + "/_sealed" or any(fl["sealed_sha256"][n] != s for n, s in RF_SHA.items()):
        raise HarnessAbort("RF 입력 정본 불일치")
    lm = load_json_checked(LEV_DIR + "/manifest_public.json", LEV_MANIFEST_PUBLIC_SHA256)
    le = {x["name"]: x for x in lm["sealed_files"]}.get("_sealed/" + LEV_NAME)
    lp = _abs(LEV_DIR + "/_sealed/" + LEV_NAME)
    if le is None or le["sha256"] != LEV_SHA256 or os.path.getsize(lp) != le["bytes"]:
        raise HarnessAbort("leverage 정본 불일치")
    import sklearn
    if (np.__version__, sklearn.__version__) != (lm["numpy"], lm["sklearn"]):
        raise HarnessAbort("numpy/sklearn 버전이 블록 AX 기록과 다름(T_obs 비트 대조 전제)")
    # 전원 → 부하 → 락 (모두 R2 이전)
    pw = power_status()
    if not pw["ok"]:
        print("[POWER] AC + ≥%dW 아님 — 종료(%d)" % (ADAPTER_MIN_W, EXIT_POWER), flush=True)
        return EXIT_POWER
    cl.gate_a_load("AY run entry")
    run_id = "AY-" + datetime.datetime.now(KST).isoformat(timespec="seconds")
    paths = make_paths(ROOT, T, mode, run_id, RUN_CONSTS, dict(GIN_SHA, **RF_SHA), LEV_SHA256,
                       {"x": MASTER_X[1], "y": MASTER_Y[1]}, N_DRUGS, N_PT, T["G"],
                       lambda: power_status()["ok"],
                       {"harness_sha256": me, "watchdog_sha256": sha256_file(_abs(WATCHDOG_PATH)),
                        "selftest_sha256": sha256_file(st_path)})
    with cl.ComputeLock(script="rqint_holm8_run.py", role="runner"):
        pub = core(paths, fault=None)
    print(json.dumps({"stage": "run", "completed": pub["completed"], "mode_at_entry": mode}, ensure_ascii=False),
          flush=True)
    return EXIT_OK


def stage_status():
    """공개 진행 정보만(동전 수·경과 시간·마지막 체크포인트 시각·전원·부하)."""
    ev = _hb_events(os.path.join(_abs(OUT_REL), "heartbeat.jsonl"))
    ck = [e for e in ev if e.get("event") == "checkpoint"]
    last = ck[-1] if ck else {}
    out = {"tree_exists": os.path.isdir(_abs(OUT_REL)), "run_id": ev[0].get("run_id") if ev else None,
           "n_launches": sum(1 for e in ev if e.get("event") == "r2_started"),
           "phase": last.get("phase"), "b_done": last.get("b_done"), "k_done": last.get("k_done"),
           "last_checkpoint_ts": last.get("ts_kst"), "last_event": ev[-1].get("event") if ev else None,
           "last_event_ts": ev[-1].get("ts_kst") if ev else None,
           "power": power_status(), "load1": round(os.getloadavg()[0], 2)}
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    return EXIT_OK


# ═══════════════════════════════════════════════════════════════════════════
# 합성 자체검사 Q1~Q14 (확증 입력 판독 0)
# ═══════════════════════════════════════════════════════════════════════════
FIXTURE_SMILES = ["c1ccccc1", "c1ccncc1", "C1CCCCC1", "c1ccc2ccccc2c1", "c1ccoc1", "c1ccsc1", "C1CCNCC1",
                  "C1CCOC1", "CCO"]
FX_N, FX_K, FX_B, FX_AUDIT, FX_CK, FX_BCA_B = 60, 12, 300, 50, 50, 200


def _write_npz(path, **arrays):
    with open(path, "wb") as f:
        np.savez(f, **arrays)


def _write_text(path, s):
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


def _fx_mats(fx, T, n_rep=1):
    lo, hi = T["arms"]
    P_RF = {arm: [fx["RF"][arm].astype(np.float64)] for arm in (lo, hi)}
    P_GIN = {arm: {s: [fx["G"][(arm, T["s_to_t"][s])]] for s in T["seeds"]} for arm in (lo, hi)}
    return P_RF, P_GIN


def _make_fixture(root, T, rng_seed=20260928, n=FX_N, k=FX_K):
    """실저장소와 같은 상대 경로 구조의 합성 저장소."""
    rng = np.random.default_rng(rng_seed)
    os.makedirs(os.path.join(root, "data", "processed"))
    cids = np.sort(rng.choice(np.arange(1000, 90000), size=n, replace=False)).astype(np.int64)
    smi = list(FIXTURE_SMILES) + [FIXTURE_SMILES[i] for i in rng.integers(0, len(FIXTURE_SMILES),
                                                                           n - len(FIXTURE_SMILES))]
    smi = [smi[i] for i in rng.permutation(n)]
    Y = (rng.random((n, k)) < 0.3).astype(int)
    for j in range(k):
        if Y[:, j].sum() < 2:
            Y[rng.choice(n, 2, replace=False), j] = 1
    pd.DataFrame({"cid": cids, "smiles_canonical": smi}).to_parquet(_abs(MASTER_X[0], root))
    ydf = pd.DataFrame(Y, columns=["pt_%04d" % j for j in range(k)])
    ydf.insert(0, "cid", cids)
    ydf.to_parquet(_abs(MASTER_Y[0], root))

    def tree(rel, files):
        d = _abs(rel + "/_sealed", root)
        os.makedirs(d)
        _write_text(os.path.join(d, "access.log"), json.dumps({"type": "machine_read", "actor": "fixture"}) + "\n")
        for nm, data in files.items():
            with open(os.path.join(d, nm), "wb") as f:
                f.write(data)
        return d

    for i, pre in enumerate(CONF_PREFIXES):
        tree(pre, {"oof_fixture_%d.npz" % i: b"x" * (10 + i)})
    tree(STABILITY_PREFIX, {"checkpoint.jsonl": b"y" * 7})
    tree("experiments/runs/v3_other_fixture", {"other.json": b"z" * 5})
    lo, hi = T["arms"]
    rf_dir = tree(RF_CONS_DIR, {})
    gin_dir = tree(GIN_CONS_DIR, {})
    sha, RF, G = {}, {}, {}
    for arm in (lo, hi):
        RF[arm] = rng.random((n, k)).astype(np.float32)          # RF dtype 변환 경로 검증
        p = os.path.join(rf_dir, "consensus_%s.npz" % arm)
        _write_npz(p, consensus=RF[arm], cid=cids)
        sha[os.path.basename(p)] = sha256_file(p)
        for s in T["seeds"]:
            t = T["s_to_t"][s]
            G[(arm, t)] = rng.random((n, k))
            p = os.path.join(gin_dir, T["gin_file"].format(model=arm, t=t))
            _write_npz(p, consensus=G[(arm, t)], cid=cids)
            sha[os.path.basename(p)] = sha256_file(p)
    fx = {"Y": Y, "RF": RF, "G": G, "cids": cids, "smi": smi}
    P_RF, P_GIN = _fx_mats(fx, T)
    mats, seeds = sr.build_eight_consensus(P_RF, P_GIN)
    t_obs = sr.observed_statistic(mats, seeds, Y, np.arange(k))[0]
    lev = {"T_obs": t_obs, LEV_HEX_KEY: float(t_obs).hex(), "e_profile": [{"g": 0, "e_g": 0.0}], "note": "fixture"}
    lev_dir = tree(LEV_DIR, {LEV_NAME: (json.dumps(lev, indent=2) + "\n").encode("utf-8")})
    groups = [scaffold_of(s) for s in smi]
    fx.update({"groups": np.array(groups), "n_groups": len(set(groups)), "t_obs": t_obs,
               "input_sha": sha, "lev_sha": sha256_file(os.path.join(lev_dir, LEV_NAME)),
               "master_sha": {"x": sha256_file(_abs(MASTER_X[0], root)), "y": sha256_file(_abs(MASTER_Y[0], root))}})
    fx["consts"] = snapshot_consts(root)
    return fx


def _fx_paths(root, T, fx, mode="first", run_id="AY-fixture", power=None, ckpt_every=FX_CK, B=FX_B):
    return make_paths(root, T, mode, run_id, fx["consts"], fx["input_sha"], fx["lev_sha"], fx["master_sha"], FX_N,
                      FX_K, fx["n_groups"], power or (lambda: True),
                      {"harness_sha256": "fixture", "watchdog_sha256": "fixture", "selftest_sha256": "fixture"},
                      provenance=PROVENANCE_RUN, B=B, n_audit=FX_AUDIT, ckpt_every=ckpt_every,
                      bca={"unit": T["bca"]["unit"], "alpha": T["bca"]["alpha"], "B": FX_BCA_B,
                           "seed": T["bca"]["seed"]})


def _run_quiet(paths, fault=None):
    buf = io.StringIO()
    exc = None
    with contextlib.redirect_stdout(buf):
        try:
            core(paths, fault=fault)
        except (Exception, _Fault) as e:            # noqa: BLE001 — 시험 대상
            exc = e
    return buf.getvalue(), exc


def _sealed_file(root, name):
    return os.path.join(_abs(OUT_REL, root), "_sealed", name)


def _load_result(root):
    return (np.load(_sealed_file(root, "t_star.npy"), allow_pickle=False),
            json.loads(_read_bytes(_sealed_file(root, "holm8_result.json")).decode("utf-8")),
            json.loads(_read_bytes(_sealed_file(root, "d9_bca_result.json")).decode("utf-8")))


def _bits_equal(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return a.shape == b.shape and np.array_equal(a.view(np.uint64), b.view(np.uint64))


def _res(name, checks, **extra):
    checks = {k: bool(v) for k, v in checks.items()}
    fails = [k for k, v in checks.items() if not v]
    return dict({"name": name, "checks": checks, "pass": not fails, "fails": fails}, **extra)


def _src_tree(path=None):
    return ast.parse(_read_bytes(path or os.path.abspath(__file__)).decode("utf-8"))


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


def selftest_Q1_constants(T):
    checks = {"spec": sha256_file(_abs(SPEC_PATH)) == SPEC_SHA256,
              "amendment1": sha256_file(_abs(AMEND1_PATH)) == AMEND1_SHA256,
              "amendment2": sha256_file(_abs(AMEND2_PATH)) == AMEND2_SHA256,
              "decisions_v1": sha256_file(_abs(DECISIONS_PATH)) == DECISIONS_SHA256,
              "b100k_prespec": sha256_file(_abs(B100K_PRESPEC[0])) == B100K_PRESPEC[1]}
    for rel, sha in PRE_IMPORT_SHA.items():
        checks["pre_import:" + rel.split("src/", 1)[1]] = sha256_file(_abs(rel)) == sha
    M = json.loads(_read_bytes(_abs("experiments/sap/manifest.json")).decode("utf-8"))["modules"]
    for nm in ("__init__.py", "consensus.py", "metrics.py", "bootstrap.py", "decision.py", "redaction.py"):
        checks["registered_sap:" + nm] = M[nm]["sha256"] == PRE_IMPORT_SHA["v3_Multimodal/src/sap/" + nm]
    C = json.loads(_read_bytes(_abs("v3_Multimodal/config/gin_train_contract.json")).decode("utf-8"))["preconditions"]
    reg = dict(C["f4_authority_chain"], **C["f5_reused_modules"])
    for rel in ("v3_Multimodal/src/ladder_confirmatory.py", "v3_Multimodal/src/confirmatory_oof_rep1.py",
                "v3_Multimodal/src/compute_lock.py"):
        checks["registered_f5:" + os.path.basename(rel)] = reg[rel]["sha256"] == PRE_IMPORT_SHA[rel]
    checks["coin_seed_recomputed"] = coin_seed_from_label(T["coin_label"]) == COIN_SEED == T["coin_seed"]
    checks["coin_label_57_ascii"] = len(T["coin_label"]) == 57 and T["coin_label"].isascii()
    checks["audit_seed_rule"] = T["audit_seed"] == COIN_SEED + AUDIT_SEED_OFFSET
    checks["audit_offset_matches_rqint_source"] = "seed + 1_000_003" in inspect.getsource(sr.rqint_test)
    checks["run_consts_equal_repo_snapshot"] = snapshot_consts(ROOT) == RUN_CONSTS
    return _res("Q1 상수·해시", checks)


def selftest_Q2_binding(T):
    tree = _src_tree()
    bad = []
    targets_int = {T["B"], T["n_reference"], int(T["bca"]["B"]), int(T["bca"]["seed"])}
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant):
            if type(n.value) is int and n.value in targets_int:
                bad.append(n.lineno)
            if isinstance(n.value, str) and n.value in (T["secondary_rule"], T["mc_se_rule"]):
                bad.append(n.lineno)
    checks = {"B_spec_eq_amend1_eq_closure": T["B"] == T["B_amend1"]
              == int(T["closure"]["proposed_resolution"]["B_value"]),
              "reference_eq_2B": T["n_reference"] == 2 * T["B"],
              "pair_complement_true": T["pair_complement"] is True,
              "n_audit_rqint_default_eq_b100k": T["n_audit"] == T["n_audit_b100k"],
              "s5_call_convention_keys": set(T["bca"]) == {"unit", "alpha", "B", "seed"}
              and T["bca"]["unit"] == "scaffold_cluster",
              "primary_p_rule_from_amend1": T["primary_p_rule"] == "(1 + c) / (B + 1)",
              "executed_in_block_115": T["executed_S4"] == 115 == T["executed_S5"],
              "no_literal_restatement_B_ref_bcaB_seed": not bad}
    try:
        check_terms(T)
        checks["check_terms_pass"] = True
    except HarnessAbort:
        checks["check_terms_pass"] = False
    return _res("Q2 명세·사이드카 결속", checks, literal_lines=bad,
                note="감사 수 리터럴은 CKPT_EVERY(지시서 지정 상수)와 같은 값이라 AST 대상에서 제외 — 값은 "
                     "rqint_test 기본값에서 판독하고 b_100k_prespec 과 교차 확인. 주 p 식 문자열은 계산에 쓰지 않고 "
                     "P7 결속 assert(check_terms)에만 1회 등장한다.")


def selftest_Q3_equivalence(tmp, T):
    root = os.path.join(tmp, "q3")
    fx = _make_fixture(root, T)
    out, exc = _run_quiet(_fx_paths(root, T, fx))
    if exc is not None:
        return _res("Q3 rqint_test 동치", {"base_run_completed": False}, error=type(exc).__name__), None, out
    ts, H, _D = _load_result(root)
    P_RF, P_GIN = _fx_mats(fx, T)
    R = sr.rqint_test(P_RF, P_GIN, fx["Y"], fx["groups"], eligible_pt=np.arange(FX_K), n_coin_vectors=FX_B,
                      seed=T["coin_seed"], pair_complement=True, complement_audit_draws=FX_AUDIT, return_perm=True)
    checks = {"t_star_bit_equal_perm_first_B": _bits_equal(ts, R["perm"][:FX_B]),
              "t_obs_equal": float(H["t_obs"]) == R["T_obs"],
              "count_equal": H["count_abs_ge_obs"] == R["count_abs_ge_obs"],
              "audit_draws_equal": H["complement_audit"]["draws_checked"] == R["complement_audit"]["draws_checked"],
              "audit_failures_equal": H["complement_audit"]["failures"] == R["complement_audit"]["failures"],
              "audit_max_abs_equal": H["complement_audit"]["max_abs_dev"] == R["complement_audit"]["max_abs_dev"],
              "identity_flag_equal": H["complement_identity_used"] == R["complement_identity_used"],
              "p_secondary_equals_rqint_p": H["p_secondary"] == R["p_two_sided"],
              "n_perm_equal": H["n_permutation_values"] == R["n_permutation_values"]}
    return _res("Q3 rqint_test 동치", checks, provenance=PROVENANCE_SYN), (root, fx, ts, R), out


def selftest_Q4_resume(tmp, T, base):
    _root0, _fx0, ts0, R0 = base
    checks, stdouts, msgs = {}, [], []

    def fresh(name, ck=FX_CK):
        root = os.path.join(tmp, name)
        fx = _make_fixture(root, T)
        return root, fx

    # (1) b = 137 강제 중단 → 재개 (체크포인트 50 간격 → 100 에서 재개)
    root, fx = fresh("q4_main")
    o1, e1 = _run_quiet(_fx_paths(root, T, fx), fault="crash_at_b:137")
    stdouts.append(o1)
    o2, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
    stdouts.append(o2)
    ts, H, _D = _load_result(root) if e2 is None else (None, None, None)
    ev = _hb_events(os.path.join(_abs(OUT_REL, root), "heartbeat.jsonl"))
    res_ev = [e for e in ev if e.get("event") == "checkpoint_resume"]
    checks["crash137_fault_raised"] = isinstance(e1, _Fault)
    checks["crash137_resume_completed"] = e2 is None
    checks["crash137_t_star_bit_equal_uninterrupted"] = ts is not None and _bits_equal(ts, ts0)
    checks["crash137_t_star_bit_equal_rqint_test"] = ts is not None and _bits_equal(ts, R0["perm"][:FX_B])
    checks["crash137_resumed_from_100"] = len(res_ev) == 1 and res_ev[0].get("b_done") == 100
    acc = _read_bytes(_sealed_file(root, "access.log")).decode("utf-8").splitlines()
    checks["crash137_new_tree_access_1_plus_resume"] = len(acc) == 2 and "checkpoint resume" in acc[1]
    # (1b) 체크포인트 137 간격 → 정확히 137 에서 재개
    root, fx = fresh("q4_ck137")
    _o, e1 = _run_quiet(_fx_paths(root, T, fx, ckpt_every=137), fault="crash_at_b:140")
    _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry", ckpt_every=137))
    ts = _load_result(root)[0] if e2 is None else None
    ev = [e for e in _hb_events(os.path.join(_abs(OUT_REL, root), "heartbeat.jsonl"))
          if e.get("event") == "checkpoint_resume"]
    checks["ck137_resume_exact_137_bit_equal"] = (isinstance(e1, _Fault) and e2 is None and _bits_equal(ts, ts0)
                                                  and ev and ev[0].get("b_done") == 137)
    # (a) SIGKILL 모의 — 락 파일 잔존(dead pid) → reentry 게이트 통과(락 검사 생략) → 완주
    root, fx = fresh("q4_a")
    _o, e1 = _run_quiet(_fx_paths(root, T, fx), fault="crash_at_b:77")
    lock = os.path.join(root, "experiments", "runs", ".compute_lock.json")
    _write_text(lock, json.dumps({"pid": 999999, "script": "rqint_holm8_run.py"}))
    f_re, busy_re = r0_gate(root, "reentry", fx["consts"])
    _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
    ts = _load_result(root)[0] if e2 is None else None
    checks["a_sigkill_reentry_gate_passes_with_stale_lock"] = f_re == [] and busy_re is False
    checks["a_sigkill_resume_bit_equal"] = e2 is None and _bits_equal(ts, ts0)
    rootf, fxf = fresh("q4_a_first")
    _write_text(os.path.join(rootf, "experiments", "runs", ".compute_lock.json"), json.dumps({"pid": os.getpid()}))
    f1, busy1 = r0_gate(rootf, "first", fxf["consts"])
    checks["a_first_mode_live_lock_is_busy"] = f1 == [] and busy1 is True
    _write_text(os.path.join(rootf, "experiments", "runs", ".compute_lock.json"), json.dumps({"pid": 999999}))
    f2, busy2 = r0_gate(rootf, "first", fxf["consts"])
    checks["a_first_mode_dead_lock_deferred_to_computelock"] = f2 == [] and busy2 is False
    # (b) R2 직후·트리 생성 후·체크포인트 전 크래시 → b = 0 재시작
    root, fx = fresh("q4_b")
    _o, e1 = _run_quiet(_fx_paths(root, T, fx), fault="crash_after_r2")
    ck_absent = not os.path.exists(_sealed_file(root, "checkpoint.npz"))
    _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
    ts = _load_result(root)[0] if e2 is None else None
    ev = _hb_events(os.path.join(_abs(OUT_REL, root), "heartbeat.jsonl"))
    checks["b_crash_before_first_ckpt_restart_b0"] = (isinstance(e1, _Fault) and ck_absent and e2 is None
                                                      and _bits_equal(ts, ts0)
                                                      and not any(e.get("event") == "checkpoint_resume" for e in ev)
                                                      and sum(e.get("event") == "r2_started" for e in ev) == 2)
    # (c) os.replace 직후 heartbeat 전 크래시 → 내부 무결성으로 통과
    root, fx = fresh("q4_c")
    _o, e1 = _run_quiet(_fx_paths(root, T, fx), fault="crash_after_replace:150")
    ev1 = [e for e in _hb_events(os.path.join(_abs(OUT_REL, root), "heartbeat.jsonl")) if e.get("event") == "checkpoint"]
    _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
    ts = _load_result(root)[0] if e2 is None else None
    ev2 = [e for e in _hb_events(os.path.join(_abs(OUT_REL, root), "heartbeat.jsonl"))
           if e.get("event") == "checkpoint_resume"]
    checks["c_replace_before_heartbeat_resume"] = (isinstance(e1, _Fault) and ev1[-1].get("b_done") == 100
                                                   and e2 is None and _bits_equal(ts, ts0)
                                                   and ev2 and ev2[0].get("b_done") == 150)
    # (d) _tmp 잔존 파일 정리 · 봉인 트리에 .tmp/.partial 0
    root, fx = fresh("q4_d")
    _o, e1 = _run_quiet(_fx_paths(root, T, fx), fault="crash_at_b:60")
    junk = os.path.join(_abs(OUT_REL, root), "_tmp", "checkpoint.npz.partial")
    _write_text(junk, "junk")
    _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
    sealed_names = os.listdir(os.path.join(_abs(OUT_REL, root), "_sealed"))
    tmp_left = [f for f in os.listdir(os.path.join(_abs(OUT_REL, root), "_tmp")) if f != "_stale"]
    checks["d_tmp_cleaned_and_no_tmp_in_sealed"] = (e2 is None and not os.path.exists(junk) and not tmp_left
                                                    and not any(f.endswith((".tmp", ".partial")) for f in sealed_names)
                                                    and sorted(sealed_names) == sorted(NEW_SEALED_NAMES))
    # 전원 상실 → PowerLoss(체크포인트 후) → 재개
    root, fx = fresh("q4_power")
    calls = {"n": 0}

    def power_flaky():
        calls["n"] += 1
        return calls["n"] != 3

    _o, e1 = _run_quiet(_fx_paths(root, T, fx, power=power_flaky))
    _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
    ts = _load_result(root)[0] if e2 is None else None
    checks["power_loss_exit15_then_resume_bit_equal"] = (isinstance(e1, PowerLoss) and exit_code_for(e1) == EXIT_POWER
                                                         and e2 is None and _bits_equal(ts, ts0))
    msgs += [str(e) for e in (e1, e2) if e is not None]
    return _res("Q4 재개 동치", checks, provenance=PROVENANCE_SYN), stdouts, msgs


def _rewrite_ckpt(path, mutate):
    with np.load(path, allow_pickle=False) as z:
        d = {k: z[k] for k in z.files}
    mutate(d)
    _write_npz(path, **d)


def selftest_Q5_tamper(tmp, T):
    checks, msgs = {}, []

    def m_len(d):
        d["t_star"] = d["t_star"][:-1].copy()

    def m_state(d):
        r = np.random.default_rng(12345)
        d["rng_state_json"] = np.array(_rng_state_json(r))

    def m_sha(d):
        t = d["t_star"].copy()
        t[3] = np.nextafter(t[3], np.inf)
        d["t_star"] = t

    for nm, mut in (("length", m_len), ("rng_state", m_state), ("sha", m_sha)):
        root = os.path.join(tmp, "q5_" + nm)
        fx = _make_fixture(root, T)
        _o, e1 = _run_quiet(_fx_paths(root, T, fx), fault="crash_at_b:137")
        ck = _sealed_file(root, "checkpoint.npz")
        _rewrite_ckpt(ck, mut)
        _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
        msgs.append(str(e2))
        checks[nm + "_tamper_exit_hard"] = (isinstance(e2, InvalidRun) and e2.rule == RULE_CKPT
                                           and exit_code_for(e2) == EXIT_HARD)
        checks[nm + "_checkpoint_not_deleted"] = os.path.exists(ck)
        checks[nm + "_no_result_written"] = not os.path.exists(_sealed_file(root, "holm8_result.json"))
    checks["messages_value_free"] = all(_no_numeric_values(m) for m in msgs)
    return _res("Q5 체크포인트 변조", checks, provenance=PROVENANCE_SYN), msgs


def selftest_Q6_commutativity(T):
    rng = np.random.default_rng(606)
    n, k = FX_N, FX_K
    lo, hi = T["arms"]
    Y = (rng.random((n, k)) < 0.3).astype(int)
    for j in range(k):
        if Y[:, j].sum() < 2:
            Y[rng.choice(n, 2, replace=False), j] = 1
    groups = np.array([FIXTURE_SMILES[i % len(FIXTURE_SMILES)] for i in rng.permutation(n)])
    reps = {("RF", None, a): [rng.random((n, k)) for _ in range(3)] for a in (lo, hi)}
    reps.update({("GIN", s, a): [rng.random((n, k)) for _ in range(3)] for s in T["seeds"] for a in (lo, hi)})
    from sap.consensus import build_consensus
    cons = {key: build_consensus(v) for key, v in reps.items()}
    P3 = ({a: reps[("RF", None, a)] for a in (lo, hi)},
          {a: {s: reps[("GIN", s, a)] for s in T["seeds"]} for a in (lo, hi)})
    P1 = ({a: [cons[("RF", None, a)]] for a in (lo, hi)},
          {a: {s: [cons[("GIN", s, a)]] for s in T["seeds"]} for a in (lo, hi)})
    m3, s3 = sr.build_eight_consensus(*P3)
    m1, s1 = sr.build_eight_consensus(*P1)
    el = np.arange(k)
    o3, o1 = sr.observed_statistic(m3, s3, Y, el), sr.observed_statistic(m1, s1, Y, el)
    swap = np.zeros(n, dtype=bool)
    swap[::3] = True
    sw_cons = sr._apply_swap(m1, s1, swap)
    comm = True
    for (fam, s, arm), R3 in reps.items():
        other = hi if arm == lo else lo
        swapped_reps = [np.where(swap[:, None], reps[(fam, s, other)][i], R3[i]) for i in range(3)]
        comm = comm and _bits_equal(build_consensus(swapped_reps), sw_cons[(fam, s, arm)])
    r3 = sr.rqint_test(*P3, Y, groups, eligible_pt=el, n_coin_vectors=100, seed=T["coin_seed"],
                       complement_audit_draws=20, return_perm=True)
    r1 = sr.rqint_test(*P1, Y, groups, eligible_pt=el, n_coin_vectors=100, seed=T["coin_seed"],
                       complement_audit_draws=20, return_perm=True)
    return _res("Q6 consensus 1원소 vs 3반복 가환성", {
        "observed_statistic_equal": o3[0] == o1[0] and o3[1] == o1[1] and o3[2] == o1[2],
        "swap_then_average_eq_average_then_swap": comm,
        "t_star_bit_equal": _bits_equal(r3["perm"], r1["perm"]),
        "count_equal": r3["count_abs_ge_obs"] == r1["count_abs_ge_obs"]}, provenance=PROVENANCE_SYN)


def selftest_Q7_tobs(tmp, T):
    root = os.path.join(tmp, "q7")
    fx = _make_fixture(root, T)
    lp = os.path.join(_abs(LEV_DIR + "/_sealed", root), LEV_NAME)
    D = json.loads(_read_bytes(lp).decode("utf-8"))
    D[LEV_HEX_KEY] = float(np.nextafter(float.fromhex(D[LEV_HEX_KEY]), np.inf)).hex()
    _write_text(lp, json.dumps(D, indent=2) + "\n")
    fx["lev_sha"] = sha256_file(lp)
    fx["consts"] = snapshot_consts(root)
    _o, exc = _run_quiet(_fx_paths(root, T, fx))
    return _res("Q7 T_obs 1ulp 변조", {
        "invalid_tobs": isinstance(exc, InvalidRun) and exc.rule == RULE_TOBS,
        "exit_hard": exit_code_for(exc) == EXIT_HARD,
        "no_checkpoint": not os.path.exists(_sealed_file(root, "checkpoint.npz")),
        "message_value_free": _no_numeric_values(str(exc))}, provenance=PROVENANCE_SYN), [str(exc)]


def selftest_Q8_pformula(tmp, T, base):
    _root0, _fx0, ts0, _R0 = base
    _t, H, _D = _load_result(_root0)
    B = FX_B
    thr = abs(H["t_obs"]) - sr._EPS
    c = int(np.sum(np.abs(ts0) >= thr))
    checks = {"c_definition_first_B": H["c_abs_ge_obs_first_B"] == c,
              "identity_count_eq_2c": H["complement_identity_used"] is True and H["count_abs_ge_obs"] == 2 * c,
              "p_primary_formula": H["p_primary"] == (1.0 + c) / (B + 1.0),
              "p_secondary_formula": H["p_secondary"] == (1.0 + H["count_abs_ge_obs"]) / (2 * B + 1.0),
              "se_formula": H["se_primary"] == float(np.sqrt(H["p_primary"] * (1 - H["p_primary"]) / B)),
              "d14_panels": H["d14_dual_reporting"]["panel_1_primary_p"] == H["p_primary"]
              and H["d14_dual_reporting"]["panel_2_fallback_p"] == 1.0}
    # 폴백 경로(감사 실패 주입) — 중단·재개 포함
    root = os.path.join(tmp, "q8_fb")
    fx = _make_fixture(root, T)
    _o, e1 = _run_quiet(_fx_paths(root, T, fx), fault="audit_fail")
    ok_fb = e1 is None
    if ok_fb:
        tsf, HF, _D = _load_result(root)
        comp_expected = []
        P_RF, P_GIN = _fx_mats(fx, T)
        mats, seeds = sr.build_eight_consensus(P_RF, P_GIN)
        uniq = np.unique(fx["groups"])
        gi_of_row = np.searchsorted(uniq, fx["groups"])
        rng_fb = np.random.default_rng(T["coin_seed"])
        for _b in range(B):
            z = rng_fb.random(len(uniq)) < 0.5
            comp_expected.append(sr.observed_statistic(sr._apply_swap(mats, seeds, ~z[gi_of_row]), seeds, fx["Y"],
                                                       np.arange(FX_K))[0])
        comp_expected = np.array(comp_expected)
        perm = np.concatenate([tsf, comp_expected])
        cf = int(np.sum(np.abs(tsf) >= abs(HF["t_obs"]) - sr._EPS))
        cnt = int(np.sum(np.abs(perm) >= abs(HF["t_obs"]) - sr._EPS))
        checks.update({"fallback_identity_false": HF["complement_identity_used"] is False
                       and HF["complement_audit"]["fallback_to_explicit"] is True,
                       "fallback_t_star_unchanged": _bits_equal(tsf, ts0),
                       "fallback_c_first_B": HF["c_abs_ge_obs_first_B"] == cf,
                       "fallback_count_explicit": HF["count_abs_ge_obs"] == cnt,
                       "fallback_p_primary": HF["p_primary"] == (1.0 + cf) / (B + 1.0),
                       "fallback_p_secondary": HF["p_secondary"] == (1.0 + cnt) / (2 * B + 1.0)})
    checks["fallback_run_completed"] = ok_fb
    # 폴백 단계 중단·재개
    root = os.path.join(tmp, "q8_fb_resume")
    fx = _make_fixture(root, T)
    _o, e1 = _run_quiet(_fx_paths(root, T, fx), fault=("audit_fail", "crash_fb_at_k:120"))
    ev = [e for e in _hb_events(os.path.join(_abs(OUT_REL, root), "heartbeat.jsonl")) if e.get("event") == "checkpoint"]
    fb_ck_seen = any(e.get("phase") == "fallback" and e.get("k_done") == 100 for e in ev)
    _o, e2 = _run_quiet(_fx_paths(root, T, fx, mode="reentry"))
    if ok_fb and e2 is None:
        _t2, H2, _D2 = _load_result(root)
        checks["fallback_resume_same_result"] = (isinstance(e1, _Fault) and fb_ck_seen
                                                 and H2["complement_identity_used"] is False
                                                 and H2["count_abs_ge_obs"] == HF["count_abs_ge_obs"]
                                                 and H2["p_primary"] == HF["p_primary"])
    else:
        checks["fallback_resume_same_result"] = False
    return _res("Q8 p 식·폴백", checks, provenance=PROVENANCE_SYN)


def selftest_Q9_composite_bca(T):
    rng = np.random.default_rng(909)
    n, k = FX_N, FX_K
    Y = (rng.random((n, k)) < 0.3).astype(int)
    for j in range(k):
        if Y[:, j].sum() < 2:
            Y[rng.choice(n, 2, replace=False), j] = 1
    gi = np.array([i % 9 for i in rng.permutation(n)])
    A1, B1 = rng.random((n, k)), rng.random((n, k))
    el = np.arange(k)
    cc = T["bca"]
    ref = sb.paired_scaffold_bootstrap(A1, B1, Y, gi, eligible_pt=el, B=FX_BCA_B, seed=cc["seed"], unit=cc["unit"],
                                       alpha=cc["alpha"], return_boot=True)
    mine = gin_composite_bca([(A1, B1)], Y, gi, el, FX_BCA_B, cc["seed"], cc["unit"], cc["alpha"], return_boot=True)
    same = lambda a, b: (a == b) or (np.isnan(a) and np.isnan(b))    # noqa: E731
    checks = {"S1_boot_bit_equal": _bits_equal(mine["boot"], ref["boot"]),
              "S1_delta_obs_equal": mine["delta_obs"] == ref["delta_obs"],
              "S1_ci_bca_equal": same(mine["ci_bca"]["low"], ref["ci_bca"]["low"])
              and same(mine["ci_bca"]["high"], ref["ci_bca"]["high"])
              and mine["ci_bca"]["status"] == ref["ci_bca"]["status"],
              "S1_acceleration_z0_equal": same(mine["bca_diagnostics"]["acceleration"],
                                               ref["bca_diagnostics"]["acceleration"])
              and same(mine["bca_diagnostics"]["z0"], ref["bca_diagnostics"]["z0"]),
              "S1_percentile_equal": mine["ci_percentile"]["low"] == ref["ci_percentile"]["low"]
              and mine["ci_percentile"]["high"] == ref["ci_percentile"]["high"],
              "S1_ci_primary_status_equal": mine["ci_primary"]["status"] == ref["ci_primary"]["status"]}
    lo, hi = T["arms"]
    pairs = [(rng.random((n, k)), rng.random((n, k))) for _ in T["seeds"]]
    rfm = (rng.random((n, k)), rng.random((n, k)))
    mats = {("RF", None, lo): rfm[0], ("RF", None, hi): rfm[1]}
    for s, (a, b) in zip(T["seeds"], pairs):
        mats[("GIN", s, lo)], mats[("GIN", s, hi)] = a, b
    d_gin = sr.observed_statistic(mats, T["seeds"], Y, el)[2]
    m3 = gin_composite_bca(pairs, Y, gi, el, FX_BCA_B, cc["seed"], cc["unit"], cc["alpha"])
    pre = sb.paired_scaffold_bootstrap(np.mean([a for a, _b in pairs], axis=0), np.mean([b for _a, b in pairs], axis=0),
                                       Y, gi, eligible_pt=el, B=20, seed=cc["seed"], unit=cc["unit"], alpha=cc["alpha"])
    checks["S3_delta_obs_equals_observed_d_gin"] = m3["delta_obs"] == d_gin
    checks["S3_differs_from_matrix_premean"] = m3["delta_obs"] != pre["delta_obs"]
    return _res("Q9 V2 복합 BCa", checks, provenance=PROVENANCE_SYN)


def selftest_Q10_invalid(tmp, T):
    results, msgs = {}, []
    expect = {"a_sha_tamper": RULE_SHA, "b_cid_shuffle": RULE_ORDER, "c_nan": RULE_NONFINITE,
              "d_G_mismatch": RULE_G, "e_matrix_missing": RULE_NMATS}
    lo, hi = T["arms"]
    for i, case in enumerate(expect):
        root = os.path.join(tmp, "q10_" + case)
        fx = _make_fixture(root, T, rng_seed=1000 + i)
        t = T["s_to_t"][T["seeds"][1]]
        name = T["gin_file"].format(model=hi, t=t)
        fpath = os.path.join(_abs(GIN_CONS_DIR + "/_sealed", root), name)
        if case == "a_sha_tamper":
            _write_npz(fpath, consensus=fx["G"][(hi, t)] * 0.5, cid=fx["cids"])
        elif case == "b_cid_shuffle":
            _write_npz(fpath, consensus=fx["G"][(hi, t)], cid=fx["cids"][::-1].copy())
            fx["input_sha"][name] = sha256_file(fpath)
        elif case == "c_nan":
            P = fx["G"][(hi, t)].copy()
            P[3, 5] = np.nan
            _write_npz(fpath, consensus=P, cid=fx["cids"])
            fx["input_sha"][name] = sha256_file(fpath)
        elif case == "d_G_mismatch":
            fx["n_groups"] = T["G"]
        else:
            os.remove(os.path.join(_abs(RF_CONS_DIR + "/_sealed", root), "consensus_%s.npz" % lo))
        fx["consts"] = snapshot_consts(root)
        _out, exc = _run_quiet(_fx_paths(root, T, fx))
        msg = str(exc) if exc is not None else ""
        msgs.append(msg)
        sealed = os.path.join(_abs(OUT_REL, root), "_sealed")
        results[case] = (isinstance(exc, InvalidRun) and exc.rule == expect[case]
                         and exit_code_for(exc) == EXIT_HARD
                         and sorted(os.listdir(sealed)) == ["access.log"] and _no_numeric_values(msg))
    return _res("Q10 무효 규칙", results, note="「출력 미생성」= 결과 봉인 파일·체크포인트 미생성 "
                                          "(first 모드는 R0′ 에서 트리·access.log 를 R2 이전에 만든다)"), msgs


def selftest_Q11_leak(base, texts_extra, exc_msgs):
    root, _fx, ts, _R = base
    _t, H, D = _load_result(root)
    vals = [H["t_obs"], H["delta_rf"], H["delta_gin"], H["p_primary"], H["p_secondary"], H["se_primary"],
            H["se_secondary"], H["complement_audit"]["max_abs_dev"]] + list(H["delta_gin_per_seed"].values())
    for fam in ("rf", "gin_composite"):
        r = D[fam]
        vals += [r["delta_obs"], r["ci_bca"]["low"], r["ci_bca"]["high"], r["ci_percentile"]["low"],
                 r["ci_percentile"]["high"], r["boot_summary"]["mean"], r["boot_summary"]["sd"]]
    vals += [float(v) for v in ts]
    pats = set()
    for v in vals:
        if v is None or not np.isfinite(v):
            continue
        for p in (repr(float(v)), "%.4f" % v, "%.6f" % v, "%.4f" % abs(v), "%.6f" % abs(v)):
            if len(p) >= 6 and p not in ("0.0000", "0.000000", "1.0000", "1.000000", "-0.0000", "-0.000000"):
                pats.add(p)
    out_dir = _abs(OUT_REL, root)
    texts = {"run.log": _read_bytes(os.path.join(out_dir, "run.log")).decode("utf-8"),
             "heartbeat": _read_bytes(os.path.join(out_dir, "heartbeat.jsonl")).decode("utf-8"),
             "manifest_public": _read_bytes(os.path.join(out_dir, "manifest_public.json")).decode("utf-8"),
             "exceptions": "\n".join(exc_msgs)}
    texts.update(texts_extra)
    hits = {k: sorted(p for p in pats if p in txt) for k, txt in texts.items()}
    pub = json.loads(texts["manifest_public"])
    hb_objs = [json.loads(ln) for ln in texts["heartbeat"].splitlines() if ln.strip()]
    wd_objs = [json.loads(ln) for ln in texts.get("watchdog_events", "").splitlines() if ln.strip()]
    pub_bad = _bad_keys(pub, FORBIDDEN_TOKENS_PUBLIC)
    hb_bad = _bad_keys(hb_objs, FORBIDDEN_TOKENS_PUBLIC)
    wd_bad = _bad_keys(wd_objs, FORBIDDEN_TOKENS_PUBLIC)
    sealed_bad = _bad_keys([H, D], FORBIDDEN_TOKENS_SEALED)
    return _res("Q11 누설 가드", {"value_strings_absent": not any(hits.values()),
                                  "public_keys_clean": not pub_bad and not hb_bad and not wd_bad,
                                  "sealed_keys_no_sign_tokens": not sealed_bad,
                                  "texts_scanned_include_watchdog": "watchdog_events" in texts},
                n_patterns=len(pats), hits={k: len(v) for k, v in hits.items()}, public_bad_keys=pub_bad + hb_bad + wd_bad)


def _load_watchdog_module():
    spec = importlib.util.spec_from_file_location("rqint_holm8_watchdog_st", _abs(WATCHDOG_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def selftest_Q12_watchdog(tmp):
    W = _load_watchdog_module()
    checks = {}
    texts = []

    class Clock:
        def __init__(self):
            self.t = 0.0
            self.sleeps = []

        def now(self):
            return self.t

        def sleep(self, s):
            self.sleeps.append(s)
            self.t += s

    def mk(name, codes, power_seq=None, load_seq=None, pre_events=None):
        d = os.path.join(tmp, "q12_" + name)
        os.makedirs(d)
        ev = os.path.join(d, "watchdog_events.jsonl")
        hb = os.path.join(d, "heartbeat.jsonl")
        _write_text(hb, json.dumps({"event": "checkpoint", "b_done": 1000, "k_done": 0, "phase": "coins",
                                    "ckpt_sha256": "ab" * 32}) + "\n")
        if pre_events:
            _write_text(ev, "".join(json.dumps(e) + "\n" for e in pre_events))
        clk = Clock()
        seq = list(codes)
        calls = {"n": 0}

        def spawn():
            calls["n"] += 1
            return seq.pop(0)

        pw = list(power_seq or [])
        ld = list(load_seq or [])
        wd = W.Watchdog(ev, hb, spawn=spawn, power=lambda: pw.pop(0) if pw else True,
                        load1=lambda: ld.pop(0) if ld else 0.5, clock=clk.now, sleep=clk.sleep)
        return wd, ev, clk, calls

    def events(ev):
        return [json.loads(ln) for ln in _read_bytes(ev).decode("utf-8").splitlines() if ln.strip()]

    wd, ev, clk, calls = mk("ok", [0])
    checks["code0_completes"] = wd.run() == 0 and calls["n"] == 1 and events(ev)[-1]["event"] == "completed"
    texts.append(_read_bytes(ev).decode("utf-8"))
    wd, ev, clk, calls = mk("hard", [13, 0])
    checks["code13_stops_no_relaunch"] = wd.run() == 13 and calls["n"] == 1 and events(ev)[-1]["event"] == "hard_stop"
    wd2 = W.Watchdog(ev, os.path.join(os.path.dirname(ev), "heartbeat.jsonl"), spawn=lambda: 0,
                     power=lambda: True, load1=lambda: 0.5, clock=clk.now, sleep=clk.sleep)
    checks["manual_restart_after_hard_stop_refused"] = wd2.run() == 13 and events(ev)[-1]["event"] == "refused_start"
    wd, ev, clk, calls = mk("wait", [15, 10, 0], power_seq=[False, False, True], load_seq=[2.5, 0.5, 0.5, 0.5])
    rc = wd.run()
    checks["codes_15_10_wait_uncounted"] = (rc == 0 and calls["n"] == 3 and wd.restarts == 0
                                            and not any(e["event"] == "restart_counted" for e in events(ev)))
    checks["power_wait_logged_uncounted"] = any(e["event"] == "power_wait" for e in events(ev))
    texts.append(_read_bytes(ev).decode("utf-8"))
    wd, ev, clk, calls = mk("busy", [9] * 40)
    checks["code9_30_consecutive_stops"] = (wd.run() == 9 and calls["n"] == 30
                                            and events(ev)[-1]["event"] == "busy_limit")
    wd, ev, clk, calls = mk("abn", [1] * 20)
    rc = wd.run()
    gaps = [s for s in clk.sleeps if s >= 60]
    checks["abnormal_11_stops"] = rc == 13 and calls["n"] == 11 and events(ev)[-1]["event"] == "restart_limit"
    checks["backoff_ge_60s_mock_clock"] = len(gaps) >= 10 and min(s for s in clk.sleeps
                                                                   if s not in (W.LOAD_POLL_S,)) >= 60
    texts.append(_read_bytes(ev).decode("utf-8"))
    pre = [{"ts_kst": "x", "event": "restart_counted", "restarts": i + 1} for i in range(4)]
    wd, ev, clk, calls = mk("restore", [1] * 20, pre_events=pre)
    rc = wd.run()
    checks["counter_restored_from_log"] = rc == 13 and calls["n"] == 7
    wd, ev, clk, calls = mk("loadlong", [0], load_seq=[5.0] * 600)
    rc = wd.run()
    checks["load_wait_long_logged_and_continues"] = rc == 0 and any(e["event"] == "load_wait_long" for e in events(ev))
    texts.append(_read_bytes(ev).decode("utf-8"))
    allowed = set(W.EVENT_KEYS)
    all_keys_ok = all(set(e) <= allowed for t in texts for e in (json.loads(x) for x in t.splitlines() if x.strip()))
    checks["event_keys_whitelisted"] = all_keys_ok
    try:
        wd.event("x", t_star=1)
        checks["non_whitelisted_key_rejected"] = False
    except KeyError:
        checks["non_whitelisted_key_rejected"] = True
    checks["watchdog_paths_not_run_prefix"] = (not W.EVENTS_REL.startswith(OUT_REL)
                                               and not os.path.basename(W.WATCHDOG_DIR_REL).startswith("v3_rqint_holm8")
                                               and W.MAX_RESTARTS == 10 and W.BACKOFF_S >= 60)
    return _res("Q12 감시 래퍼", checks), "\n".join(texts)


def selftest_Q13_ast():
    tree = _src_tree()
    forbidden = ("holm", "rq2_decision", "rq3_decision", "rq4_decision", "open_sealed", "emit_sign")
    hits = [(_call_name(n), n.lineno) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and _call_name(n) in forbidden]
    np_sign = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "sign"
               and isinstance(n.value, ast.Name) and n.value.id == "np"]
    par = _parents(tree)
    rq_fns = {_enclosing(par, n) for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "rqint_test"}
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    net = sorted(imported & {"socket", "urllib", "requests", "http", "ftplib", "smtplib", "asyncio",
                             "aiohttp", "httpx", "telnetlib"})
    env_bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr == "environ":
            p = par.get(n)
            if not (isinstance(p, ast.Subscript) and isinstance(p.ctx, ast.Store) and _enclosing(par, n) is None):
                env_bad.append(n.lineno)
        if isinstance(n, ast.Call) and _call_name(n) == "getenv":
            env_bad.append(n.lineno)
    opts = {a.value for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "add_argument"
            for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    cl_fns = {_enclosing(par, n) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name) and n.func.value.id == "cl"}
    sp_fns = {_enclosing(par, n) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"}
    wtree = _src_tree(_abs(WATCHDOG_PATH))
    w_imp = set()
    for n in ast.walk(wtree):
        if isinstance(n, ast.Import):
            w_imp |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            w_imp.add(n.module.split(".")[0])
    w_bad = sorted(w_imp & {"numpy", "pandas", "sap", "socket", "urllib", "requests", "http"})
    w_sealed = [n.lineno for n in ast.walk(wtree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and "_sealed" in n.value]
    return _res("Q13 AST", {
        "forbidden_calls_zero": not hits, "np_sign_zero": not np_sign,
        "rqint_test_only_in_selftest": all(f and f.startswith("selftest_") for f in rq_fns) and bool(rq_fns),
        "network_imports_zero": not net, "environ_set_only_module_level_no_read": not env_bad,
        "cli_options_exact": opts == {"--stage", "--out"},
        "cl_calls_only_in_stage_run": cl_fns == {"stage_run"},
        "subprocess_only_in_power_status": sp_fns == {"power_status"},
        "watchdog_no_compute_or_network_imports": not w_bad,
        "watchdog_no_sealed_path_literal": not w_sealed},
        forbidden_hits=hits, env_lines=env_bad, rq_fns=sorted(f for f in rq_fns if f))


def selftest_Q14_hygiene(guard_violations, traps, before):
    after = {"sealed_counts": sealed_counts(ROOT), "fp": fingerprints(ROOT), "pycache": _pycache_dirs(ROOT),
             "out": len(glob.glob(_abs(OUT_GLOB)))}
    return _res("Q14 위생", {
        "runtime_write_guard_violations_zero": not guard_violations,
        "cl_calls_during_selftest_zero": traps["cl"] == 0,
        "pmset_calls_during_selftest_zero": traps["pmset"] == 0,
        "real_sealed_counts_unchanged": after["sealed_counts"] == before["sealed_counts"]
        == RUN_CONSTS["counts_before"],
        "fingerprints_5_unchanged": after["fp"] == before["fp"] == RUN_CONSTS["fp_start"],
        "run_dir_not_created": after["out"] == 0,
        "pycache_unchanged": after["pycache"] == before["pycache"]},
        guard_violations=guard_violations[:5])


def _pycache_dirs(root):
    return sum(1 for dp, _dn, _fn in os.walk(root)
               if ".git" not in dp.split(os.sep) and os.path.basename(dp) == "__pycache__")


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

    orig = {"open": builtins.open, "savez": np.savez, "savez_compressed": np.savez_compressed, "save": np.save,
            "replace": os.replace, "makedirs": os.makedirs, "mkdir": os.mkdir, "remove": os.remove}

    def g_open(file, mode="r", *a, **k):
        if any(c in mode for c in "wax+") and not ok(file):
            violations.append(("open", str(file)))
            raise PermissionError("selftest write guard")
        return orig["open"](file, mode, *a, **k)

    def wrap(name, nargs=1):
        def f(*a, **k):
            for p in a[:nargs]:
                if isinstance(p, io.BytesIO):
                    continue
                if not ok(p):
                    violations.append((name, str(p)))
                    raise PermissionError("selftest write guard")
            return orig[name](*a, **k)
        return f

    builtins.open = g_open
    np.savez, np.savez_compressed, np.save = wrap("savez"), wrap("savez_compressed"), wrap("save")
    os.replace, os.makedirs, os.mkdir, os.remove = wrap("replace", 2), wrap("makedirs"), wrap("mkdir"), wrap("remove")
    try:
        yield
    finally:
        builtins.open = orig["open"]
        np.savez, np.savez_compressed, np.save = orig["savez"], orig["savez_compressed"], orig["save"]
        os.replace, os.makedirs, os.mkdir, os.remove = orig["replace"], orig["makedirs"], orig["mkdir"], orig["remove"]


def run_selftest():
    _spec, _a1, _a2, _dec, T = load_all_terms()
    before = {"sealed_counts": sealed_counts(ROOT), "fp": fingerprints(ROOT), "pycache": _pycache_dirs(ROOT)}
    traps = {"cl": 0, "pmset": 0}
    orig_cl = {k: getattr(cl, k) for k in ("gate_a_load", "gate_b_exclusive", "gate_c_settle", "ComputeLock")}
    orig_sp_run, orig_sp_popen = subprocess.run, subprocess.Popen

    def _cl_trap(*_a, **_k):
        traps["cl"] += 1
        raise RuntimeError("cl 호출 금지(selftest)")

    def _sp_trap(*a, **_k):
        if a and "pmset" in str(a[0]):
            traps["pmset"] += 1
        raise RuntimeError("subprocess 호출 금지(selftest)")

    for k in orig_cl:
        setattr(cl, k, _cl_trap)
    subprocess.run, subprocess.Popen = _sp_trap, _sp_trap
    tmp = tempfile.mkdtemp(prefix="ay_selftest_")
    violations, results = [], []
    try:
        with _write_guard([tmp, os.path.dirname(_abs(SELFTEST_OUT))], violations):
            results.append(selftest_Q1_constants(T))
            results.append(selftest_Q2_binding(T))
            r3, base, base_out = selftest_Q3_equivalence(tmp, T)
            results.append(r3)
            if base is None:
                raise RuntimeError("Q3 base run 실패")
            r4, outs4, msgs4 = selftest_Q4_resume(tmp, T, base)
            results.append(r4)
            r5, msgs5 = selftest_Q5_tamper(tmp, T)
            results.append(r5)
            results.append(selftest_Q6_commutativity(T))
            r7, msgs7 = selftest_Q7_tobs(tmp, T)
            results.append(r7)
            results.append(selftest_Q8_pformula(tmp, T, base))
            results.append(selftest_Q9_composite_bca(T))
            r10, msgs10 = selftest_Q10_invalid(tmp, T)
            results.append(r10)
            r12, wd_text = selftest_Q12_watchdog(tmp)
            results.append(selftest_Q11_leak(base, {"stdout": base_out + "\n".join(outs4), "watchdog_events": wd_text},
                                             msgs4 + msgs5 + msgs7 + msgs10))
            results.append(r12)
            results.append(selftest_Q13_ast())
    finally:
        for k, v in orig_cl.items():
            setattr(cl, k, v)
        subprocess.run, subprocess.Popen = orig_sp_run, orig_sp_popen
        shutil.rmtree(tmp, ignore_errors=True)
    results.append(selftest_Q14_hygiene(violations, traps, before))
    order = ["Q%d" % i for i in range(1, 15)]
    results.sort(key=lambda r: order.index(r["name"].split()[0]))
    n_pass = sum(1 for r in results if r["pass"])
    return {
        "_doc": "docs/115 블록 AY / AY-6 — 합성 자체검사 Q1~Q14. 확증 입력 판독 0. 모든 수치는 합성 fixture 산출물.",
        "provenance": PROVENANCE_SYN, "block": "AY (docs/115)",
        "harness_path": "v3_Multimodal/src/rqint_holm8_run.py",
        "harness_sha256": sha256_file(os.path.abspath(__file__)),
        "watchdog_path": WATCHDOG_PATH, "watchdog_sha256": sha256_file(_abs(WATCHDOG_PATH)),
        "spec_sha256": SPEC_SHA256, "amendment1_sha256": AMEND1_SHA256, "amendment2_sha256": AMEND2_SHA256,
        "fixture": {"n_rows": FX_N, "n_pt": FX_K, "B": FX_B, "n_audit": FX_AUDIT, "ckpt_every": FX_CK,
                    "bca_B": FX_BCA_B},
        "python": platform.python_version(), "numpy": np.__version__,
        "ts_kst": now_kst(), "n_tests": len(results), "n_pass": n_pass, "n_skip": 0,
        "all_pass": n_pass == len(results) == 14,
        "tests": results, "confirmatory_values_read": 0, "sealed_human_read": 0, "network_calls": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="블록 AY — Holm ⑧ RQ-int 본런 + D9 BCa 봉인 산출")
    ap.add_argument("--stage", choices=["selftest", "run", "status"], default="selftest")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.stage in ("run", "status"):
        if a.out:
            raise SystemExit("--out 은 selftest 전용")
        if a.stage == "status":
            return stage_status()
        try:
            return stage_run()
        except (InvalidRun, HarnessAbort, PowerLoss, HarnessCrash) as e:
            print("[중단] %s · 종료 코드 %d" % (e, exit_code_for(e)), flush=True)
            return exit_code_for(e)
        except SystemExit:
            raise
        except Exception as e:           # noqa: BLE001 — 메시지 비공개
            print("[비정상] %s · 종료 코드 %d" % (type(e).__name__, EXIT_CRASH), flush=True)
            return EXIT_CRASH
    if a.out and os.path.abspath(a.out) != _abs(SELFTEST_OUT):
        raise SystemExit("--out 은 SELFTEST_OUT 만 허용")
    res = run_selftest()
    os.makedirs(os.path.dirname(_abs(SELFTEST_OUT)), exist_ok=True)
    with open(_abs(SELFTEST_OUT), "w", encoding="utf-8") as f:
        f.write(json.dumps(_json_safe(res), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"stage": "selftest", "all_pass": res["all_pass"], "n_pass": res["n_pass"],
                      "n_tests": res["n_tests"], "fails": {t["name"]: t["fails"] for t in res["tests"] if not t["pass"]}},
                     ensure_ascii=False))
    return 0 if res["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
