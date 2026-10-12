"""confirmatory_oof_sens.py — 블록 BB (docs/117): 사전지정 민감도 RF OOF 3종 학습·봉인 (개봉 0 · 지표 0).

모델 정의 정본 = `v3_Multimodal/config/ladder_freeze.json` 의 `sensitivity_models`(sha 검증 후 **읽어서** 사용 · J2).
과학 경로(블록 클래스 · `rf_fit_predict` · `RF_KW` · `SEED` · `PCA_K` · `load_frozen`)는 `ladder_confirmatory` 에서
**import 그대로** 쓰고, 오케스트레이션(fit 순서 · 누수 assert · hstack)만 블록 I(`confirmatory_oof_rest`
`fit_fold`/`predict_fold`)와 같은 논리를 블록 목록 인자로 일반화해 둔다(J3).

⛔ 무결성 (docs/117 §2)
  · 지표·통계 계산 0: AP·Δ·부호·p·CI 를 계산하지 않는다(J1). 산출은 예측 행렬(OOF·consensus)뿐이며 전부 `_sealed/`.
  · 봉인 «값»의 사람 노출 0: stdout·run.log·manifest_public 에는 개수·시각·차원·wall·sha·불리언만.
  · 확증 봉인 판독 = verify 의 1파일(`v3_confirm_rep1_seed201/_sealed/oof_M2b.npz`)뿐 · 판독 전 access.log 1줄.
  · 네트워크 0 · 환경변수 판독 0 · git 0.

구조
  gate(root, expected, state)   = 상태별(S0·S1·S2) 착수 검사(순수 함수 · 읽기만).
  stage_verify()                = gate S0 → ComputeLock → I-3 정합 + J6(a)(b) + F6 바이트 동일성 → `_equivalence/` 2파일.
  stage_run()                   = gate S1|S2 → ComputeLock → core().
  core(d, fold_of_row_by_rep, out_root, expected, fault)
                                = 45 fit(체크포인트) → 반복 OOF 9 → consensus 3 → 공개 2종.
                                  데이터 로드·fold 판독은 core 밖(합성 자체검사가 같은 core 를 tempdir 에서 태운다).
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
import resource
import shutil
import tempfile
import time

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))

# ── F4 동결물 (sha256 전문) ────────────────────────────────────────────────
LADDER_FREEZE = ("v3_Multimodal/config/ladder_freeze.json",
                 "b885585aefbabb32f432b2e60141f6b12ac8bdf971066a9434021762e6ef0868")
SMOKE_STATS = ("data/processed/_ladder_smoke_stats.json",
               "724685376479ae494f4c2580012753dcce907d0e523a2be01fa6132697947606")
IMPORT_TARGETS = {
    "v3_Multimodal/src/ladder_confirmatory.py": "13a17129db6a6679bd6dbdc28a12c0f31e2e8d6b0811130450add602daf5137c",
    "v3_Multimodal/src/confirmatory_oof_rest.py": "78de238ff2fac8e22ab09618bb67388ec86e4872acd44ee9456150d4c9ecbdfa",
    "v3_Multimodal/src/confirmatory_oof_rep1.py": "afb894c09fdaad6f1c75df789c5e2ede1dbbc2151a8c30b8eda6044cd6f336b6",
    "v3_Multimodal/src/compute_lock.py": "b03a0b0012948b340f410670d6b045f279e1b21b4faa293bb45bbc2e99a6d738",
    "v3_Multimodal/src/sap/consensus.py": "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91",
    "v3_Multimodal/src/sap/__init__.py": "8dc63e28ffcf93dcdfde7facd0cf1d51b6e6c15ac4de2304de61c12ccb7a5306",
}
FROZEN = dict(IMPORT_TARGETS)
FROZEN.update({
    LADDER_FREEZE[0]: LADDER_FREEZE[1],
    SMOKE_STATS[0]: SMOKE_STATS[1],
    "experiments/sap/manifest.json": "d08dcedf2a22e1c8493c842507422de1f6c705ce54ce995e038e09f604706e10",
    "data/processed/target_mapping/08_m1b_covariates.csv":
        "c302399f32c71083a8947971fdb0826f91234be93dd6ee7483b82fd633597256",
    "data/processed/target_mapping/09_target_family_clusters.csv":
        "7f938d036edefdbcafaccb698fba65085b6ce813e42d9642e69f07e8d61e835f",
})
N_INPUTS16 = 10
REST_PUBLIC = ("experiments/runs/v3_confirm_rest/rest_public.json",
               "ccfb7b9b8986ffd3d57f55ffe1e27213ba2b08fc8af7d3ce0c95fc2d50b0abf3")
SPLIT_DIR = "data/processed/splits/confirmatory/rep%d_seed%d"
AUDIT = ("experiments/provenance/sealing_completeness_audit.json", "b189f77f30dce9b5")    # sha16
EQUIV_REF = "experiments/runs/v3_confirm_rep1_seed201/_sealed/oof_M2b.npz"
EQUIV_REF_SHA = "350fa12fac84ef4ca1355d256665c333d9cd8ca34de257e7321aefa36d8a3260"
EQUIV_MODEL, EQUIV_REP, EQUIV_FOLD = "M2b", 1, 0          # 확증 primary 모델(블록 I I-2 선례)
XCHECK_MODEL = "P-FAM"                                     # J6(b) 메모리 교차 대조(primary FamilyBlock 경로)
FLAG_FILES = ["v3_Multimodal/config/rqint_procedure_decisions_v1.json",
              "v3_Multimodal/config/gin_seed_freeze.json",
              "v3_Multimodal/config/gin_inner_valid_freeze.json"]
UNBLIND_FILES = ["v3_Multimodal/config/post_interim_freeze_v1_0.status.json",
                 "v3_Multimodal/config/gin_train_contract.json",
                 "experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json"]
DOCS33 = "docs/33_prereg_deviation_log.md"
DOCS33_ITEM = 76
LOCK_REL = "experiments/runs/.compute_lock.json"

# ── 학습 설계 (F5) ──────────────────────────────────────────────────────────
SEED_MAP = {1: 201, 2: 202, 3: 203}
N_FOLD = 5
N_PT = 370
N_DRUGS = 1092
N_SCAFFOLD_GROUPS = 732
FIT_ORDER = ["B0", "B1", "B_seq", "B_m1b", "B_m1b_pchembl", "B_fam_selfclust"]   # 블록 I FIT_ORDER 상대순서 + 신규 2
DIM_ASSERT = {"B_m1b": 10, "B_m1b_pchembl": 13}
J6A_EXPECT = {"B_m1b_pchembl": 13, "B_fam_selfclust": 835,
              "M1b_pchembl": 2063, "M2b_pchembl": 2127, "P-FAM_selfclust": 2895}
CKPT_FIELDS = ["repeat", "model", "fold", "n_train", "n_test", "dim", "wall_s", "peak_rss_gib",
               "sha256_partial", "ts_kst", "session_seq", "leak_rows", "blocks_fit"]
MAX_SESSIONS = 4

# ── 출력 (J4) ───────────────────────────────────────────────────────────────
_RUNS = "experiments/runs/"
OUT_ROOT = _RUNS + "v3_confirm_sens"
OUT_GLOB = _RUNS + "v3_confirm_sens*"
REP_TREE = _RUNS + "v3_confirm_sens_rep{r}_seed{s}"
CONS_TREE = _RUNS + "v3_confirm_sens_consensus_rep123"
SELFTEST_OUT = _RUNS + "v3_sensoof_harness_selftest/selftest_sensoof.json"
SELFTEST_GLOB = _RUNS + "v3_sensoof_*"
EQ_DIR = "_sealed/_equivalence"
EQ_NPY = "repro_M2b_rep1_fold0.npy"
EQ_JSON = "equivalence.json"

# ── 봉인 상태 기대값 (F2) ───────────────────────────────────────────────────
GROUP_PREFIXES = {
    "confirm": [_RUNS + "v3_gin_confirm_rep1_seed201", _RUNS + "v3_gin_confirm_rep2_seed202",
                _RUNS + "v3_gin_confirm_rep3_seed203"],
    "stability": [_RUNS + "v3_gin_stability"],
    "gin_consensus": [_RUNS + "v3_gin_confirm_consensus_rep123"],
    "leverage": [_RUNS + "v3_rqint_leverage_d11"],
    "holm8": [_RUNS + "v3_rqint_holm8"],
    "d12": [_RUNS + "v3_rqint_d12"],
    "s6": [_RUNS + "v3_stability_ss15"],
    "sens": [OUT_ROOT] + [REP_TREE.format(r=r, s=s) for r, s in SEED_MAP.items()] + [CONS_TREE],
}
FP_STAT = {
    "existing25": "7c585d25a78988fe01358cb33f5edb6935827d9b6bf815bfd0899103b166c0fa",
    "confirm": "54db739fd07cae92b7665267f28720d52645ff19784777d4b4b3752148ac6776",
    "stability": "01578eda438edce87ce30dfabb89d242b55ddf3cd0e3ebefa06e29f3f222d7ec",
    "gin_consensus": "2d52c9ac03961a6a7610ff7cfee6758fd957c6584867e47e44cb7f62548d11df",
    "leverage": "f0829db7e97b7fa37722265f311388c2d592b2458b2dbf514fe4748c0dc5a836",
    "holm8": "4177f61de8f3fd60a59d537b0683634a21e3dbe0e508c60da5dc4ee1ebcafc5e",
    "d12": "33a9e057a7786722cb5a7dc640dd63700855eeb7977be8d883f722290bcfd93d",
    "s6": "19a79b7f57c3febd5493d650c500c2fabeb5e4ed89b725aa6ec58c7eb5c70735",
}
FP_NOACC = {
    "existing25": "7b617e1ccf2b3f377204df5c8504906a60cdb06269aa268d813179df7fcbb7d3",
    "confirm": "1992ab00977b3afd18ce42a678adacd28e2233f5a58dbd1baa05d65289d8287d",
    "stability": "65f08361b640c5ebdfab3e9a97f7b235b7e09d77be1c22e32060a46ff5b97843",
    "gin_consensus": "d061293d808f8e216d5bc08322eee19929573eba94f14407a0c8e6d68f2ebe95",
    "leverage": "ed9b860561880707c500e49f8d01c8bf4e3e5a263502b79c79d6e7335b3c179c",
}
REP1_ACCESS = _RUNS + "v3_confirm_rep1_seed201/_sealed/access.log"
ACCESS_S0 = {
    REP1_ACCESS: 17,
    _RUNS + "v3_confirm_rest_consensus_rep123/_sealed/access.log": 9,
    _RUNS + "v3_confirm_rest_rep1_seed201/_sealed/access.log": 9,
    _RUNS + "v3_confirm_rest_rep2_seed202/_sealed/access.log": 7,
    _RUNS + "v3_confirm_rest_rep3_seed203/_sealed/access.log": 7,
    _RUNS + "v3_confirm_rftuned_rep1_seed201/_sealed/access.log": 1,
    _RUNS + "v3_confirm_rftuned_rep2_seed202/_sealed/access.log": 1,
    _RUNS + "v3_confirm_rftuned_rep3_seed203/_sealed/access.log": 1,
    _RUNS + "v3_consensus_rep123/_sealed/access.log": 23,
    _RUNS + "v3_gin_confirm_consensus_rep123/_sealed/access.log": 5,
    _RUNS + "v3_gin_confirm_rep1_seed201/_sealed/access.log": 26,
    _RUNS + "v3_gin_confirm_rep2_seed202/_sealed/access.log": 26,
    _RUNS + "v3_gin_confirm_rep3_seed203/_sealed/access.log": 25,
    _RUNS + "v3_gin_stability/_sealed/access.log": 5,
    _RUNS + "v3_latefusion_rep1_seed201/_sealed/access.log": 5,
    _RUNS + "v3_latefusion_rep2_seed202/_sealed/access.log": 5,
    _RUNS + "v3_latefusion_rep3_seed203/_sealed/access.log": 5,
    _RUNS + "v3_null_MAIN/_sealed/access.log": 8,
    _RUNS + "v3_rqint_d12/_sealed/access.log": 3,
    _RUNS + "v3_rqint_holm8/_sealed/access.log": 2,
    _RUNS + "v3_rqint_leverage_d11/_sealed/access.log": 4,
    _RUNS + "v3_stability_ss15/_sealed/access.log": 1,
    _RUNS + "v3_stratification/_sealed/access.log": 6,
    _RUNS + "v3_stratification_axes/_sealed/access.log": 15,
    _RUNS + "v3_stratification_pid/_sealed/access.log": 6,
}
COUNT_KEYS = ("n_sealed_dirs", "n_sealed_files_total", "n_sealed_artifacts", "n_access_log")
SEALED_S0 = dict(zip(COUNT_KEYS, (34, 765, 740, 25)))
SEALED_S1 = dict(zip(COUNT_KEYS, (35, 767, 742, 25)))
SEALED_AFTER = dict(zip(COUNT_KEYS, (39, 826, 801, 25)))

PUBLIC_TOP_KEYS = {"_doc", "block", "completed", "ts_completed_kst", "models", "n_fits", "n_repeats", "n_folds",
                   "fold_sizes", "block_dims", "equivalence_byte_identical", "input_checks", "sealed_files",
                   "sealed_counts_start", "sealed_counts_end", "wall_seconds", "peak_rss_gib", "n_sessions",
                   "python", "numpy", "sklearn", "pandas", "harness_sha256", "selftest_sha256",
                   "ladder_freeze_sha256", "values_disclosed", "unblinding_performed"}
PUBLIC_FILE_KEYS = {"name", "bytes", "sha256"}
PUBLIC_CHECK_KEYS = {"ladder_freeze_sha_match", "models_from_ladder_freeze_json", "fold_rows_match",
                     "leak_rows_zero_all_fits", "train_positive_ge1_all_folds", "oof_nan_zero",
                     "checkpoint_integrity", "equivalence_verified_before_run", "no_overwrite"}
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


def _read_json(path):
    return json.loads(_read_bytes(path).decode("utf-8"))


def peak_rss_gib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 3)       # macOS: bytes


class HarnessAbort(Exception):
    """구조·무결성 결함(값 무관). 메시지 = 사유 문자열(값 0)."""


class GateFail(Exception):
    """착수 게이트 실패. 메시지 = 사유 문자열(값 0)."""


class FaultStop(Exception):
    """합성 자체검사 S7 전용 강제 중단."""


def _verify_then_import():
    for rel, sha in IMPORT_TARGETS.items():
        if sha256_file(os.path.join(ROOT, rel)) != sha:
            raise HarnessAbort("import 전 sha 불일치: " + rel)


_verify_then_import()
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from ladder_confirmatory import (load_frozen, MorganBlock, CountMaskBlock, SeqBlock,  # noqa: E402
                                 M1bCovariateBlock, FamilyBlock, rf_fit_predict, MODEL_BLOCKS,
                                 RF_KW, SEED, PCA_K)
from confirmatory_oof_rest import fold_of_row_for, read_fold_membership          # noqa: E402
import confirmatory_oof_rest as cor                                               # noqa: E402  (J6(b) 교차 대조 전용)
from sap.consensus import build_consensus                                         # noqa: E402
import compute_lock as cl                                                         # noqa: E402


def _atomic_bytes(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_npy(path, arr):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        np.save(f, arr)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _npz_bytes(**arrays):
    buf = io.BytesIO()
    np.savez_compressed(buf, **arrays)
    return buf.getvalue()


def _json_bytes(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _append_line(path, text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")
        f.flush()
        os.fsync(f.fileno())


def _ends_with_newline(path):
    if os.path.getsize(path) == 0:
        return False
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) == b"\n"


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
    body = None
    for i, (num, pos) in enumerate(starts):
        if num == n:
            body = text[pos:starts[i + 1][1] if i + 1 < len(starts) else len(text)]
    return starts[-1][0], body


def partial_name(r, model, k):
    return "rep%d_%s_fold%d.npy" % (r, model.replace("-", ""), k)


# ── 봉인 stat (파일을 열지 않는다) ─────────────────────────────────────────
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


def _in_prefixes(rel, prefixes):
    return any(rel == p or rel.startswith(p + os.sep) for p in prefixes)


def sealed_counts(root, exclude=()):
    dirs = 0
    for dp, _dn, _fn in os.walk(root):
        if ".git" in dp.split(os.sep) or os.path.basename(dp) != "_sealed":
            continue
        if not _in_prefixes(os.path.relpath(dp, root), exclude):
            dirs += 1
    lines = [x for x in sealed_lines(root) if not _in_prefixes(x[0], exclude)]
    acc = sum(1 for x in lines if x[2])
    return dict(zip(COUNT_KEYS, (dirs, len(lines), len(lines) - acc, acc)))


def _fp(sel):
    s = sorted("%s\t%d" % (rel, b) for rel, b, _a in sel)
    return sha256_bytes(("\n".join(s) + "\n").encode("utf-8"))


def sealed_fingerprints(root, groups):
    lines = sealed_lines(root)
    allpre = [x for v in groups.values() for x in v]
    res = {}
    for g, pres in groups.items():
        sel = [x for x in lines if _in_prefixes(x[0], pres)]
        res[g] = (_fp(sel), _fp([x for x in sel if not x[2]]))
    sel = [x for x in lines if not _in_prefixes(x[0], allpre)]
    res["existing25"] = (_fp(sel), _fp([x for x in sel if not x[2]]))
    return res


# ═══════════════════════════════════════════════════════════════════════════
# 체크포인트·환경 지문 (gate·core 공용)
# ═══════════════════════════════════════════════════════════════════════════
def read_ckpt_verified(ckpt_path, pdir):
    """체크포인트 무결: 각 줄 필드·키 중복 0·sha256_partial == partial 실파일·orphan partial 0."""
    done = {}
    if os.path.exists(ckpt_path):
        b = _read_bytes(ckpt_path)
        if b and not b.endswith(b"\n"):
            raise HarnessAbort("checkpoint 말미 개행 아님(불완전 줄)")
        for line in b.decode("utf-8").splitlines():
            rec = json.loads(line)
            if set(rec) != set(CKPT_FIELDS):
                raise HarnessAbort("checkpoint 필드 불일치")
            key = (int(rec["repeat"]), rec["model"], int(rec["fold"]))
            if key in done:
                raise HarnessAbort("checkpoint 키 중복")
            pp = os.path.join(pdir, partial_name(*key))
            if not os.path.isfile(pp) or sha256_file(pp) != rec["sha256_partial"]:
                raise HarnessAbort("checkpoint sha 와 partial 실파일 불일치: " + os.path.basename(pp))
            done[key] = rec
    present = set(os.listdir(pdir)) if os.path.isdir(pdir) else set()
    if present != {partial_name(*k) for k in done}:
        raise HarnessAbort("partial 디렉터리 ↔ checkpoint 집합 불일치(orphan·tmp)")
    return done


def env_fingerprint(expected):
    import joblib
    import rdkit
    import scipy
    import sklearn
    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__, "joblib": joblib.__version__, "pandas": pd.__version__,
            "rdkit": rdkit.__version__, "machine": platform.machine(),
            "os": "%s %s" % (platform.system(), platform.release()),
            "ladder_freeze_sha256": expected["ladder"][1], "harness_sha256": expected["harness_sha256"]}


# ═══════════════════════════════════════════════════════════════════════════
# gate — 상태별 착수 검사 (순수 함수 · 디스크 읽기만)
# ═══════════════════════════════════════════════════════════════════════════
def _sens_dirs(root, expected):
    return sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, expected["out_glob"])))


def _eq_check(root, expected, need):
    base = os.path.join(root, expected["out_root"])
    eqd = os.path.join(base, EQ_DIR)
    need(os.path.isdir(eqd) and sorted(os.listdir(eqd)) == sorted([EQ_NPY, EQ_JSON]), "_equivalence 파일 집합 불일치")
    eq = _read_json(os.path.join(eqd, EQ_JSON))
    need(eq.get("byte_identical") is True, "equivalence byte_identical 아님")
    need(eq.get("sha256_repro_npy") == sha256_file(os.path.join(eqd, EQ_NPY)), "repro npy sha 불일치")
    need(eq.get("harness_sha256") == expected["harness_sha256"], "equivalence 기록 하네스 sha 불일치")
    for k in ("i3_consistency_ok", "j6a_dims_ok", "j6b_pfam_crosscheck_identical"):
        need(eq.get(k) is True, "equivalence 검증 불리언 실패: " + k)
    return eq


def detect_state(root, expected):
    dirs = _sens_dirs(root, expected)
    if not dirs:
        return "S0"
    sealed = os.path.join(root, expected["out_root"], "_sealed")
    if os.path.isdir(sealed) and sorted(os.listdir(sealed)) == ["_equivalence"]:
        return "S1"
    return "S2"


def gate(root, expected, state):
    def need(cond, reason):
        if not cond:
            raise GateFail("[gate %s] %s" % (state, reason))

    def j(rel):
        return os.path.join(root, rel)

    need(state in ("S0", "S1", "S2"), "상태 표기")
    # P4 동결물·입력
    for rel, sha in expected["frozen"].items():
        need(os.path.isfile(j(rel)) and sha256_file(j(rel)) == sha, "동결물 sha 불일치: " + rel)
    lf = _read_json(j(expected["ladder"][0]))
    need(sha256_file(j(expected["ladder"][0])) == expected["ladder"][1], "ladder_freeze sha 불일치")
    ins = lf["inputs_sha16"]
    need(len(ins) == expected["n_inputs16"], "inputs_sha16 개수 불일치")
    for rel, v in ins.items():
        need(os.path.isfile(j(rel)) and sha256_file(j(rel))[:16] == v["sha16"], "inputs_sha16 불일치: " + rel)
    need(sha256_file(j(expected["rest_public"][0])) == expected["rest_public"][1], "rest_public sha 불일치")
    rp = _read_json(j(expected["rest_public"][0]))
    for r, s in expected["seed_map"].items():
        ent = rp["inputs_sha256"]["splits"]["rep%d_seed%d" % (r, s)]
        sd = j(expected["split_dir"] % (r, s))
        need(sha256_file(os.path.join(sd, "folds.json")) == ent["folds_json_sha256"], "folds.json sha rep%d" % r)
        need(sha256_file(os.path.join(sd, "fold_membership.csv")) == ent["fold_membership_sha256"],
             "fold_membership sha rep%d" % r)
    # P5 모델 정의 결속
    sm = lf["sensitivity_models"]
    need(list(sm.items()) == list(expected["models"].items()), "sensitivity_models ≠ 하네스 모델 목록")
    for m, ids in sm.items():
        if m in MODEL_BLOCKS:
            need(MODEL_BLOCKS[m] == ids, "MODEL_BLOCKS 불일치: " + m)
        need(all(b in FIT_ORDER for b in ids), "FIT_ORDER 밖 블록: " + m)
    rh = lf["rf_hyperparameters"]
    need(set(RF_KW) == {"n_estimators", "max_depth", "n_jobs", "class_weight"}
         and all(rh[k] == RF_KW[k] for k in RF_KW), "RF_KW ≠ rf_hyperparameters")
    need(lf["seed"] == SEED == 42 and lf["pca_k"] == PCA_K == 64, "seed/pca_k 불일치")
    # P7 F6 기대 sha
    need(sha256_file(j(expected["audit"][0]))[:16] == expected["audit"][1], "감사 기준선 sha16 불일치")
    aud = _read_json(j(expected["audit"][0]))
    need(aud["hashes"]["sha256_all_sealed_artifacts"].get(expected["equiv_ref"]) == expected["equiv_ref_sha"],
         "감사 기준선의 equivalence 대상 sha 불일치")
    # selftest · docs/33
    st_path = j(expected["selftest_out"])
    need(os.path.isfile(st_path), "selftest 결과 부재")
    st = _read_json(st_path)
    need(st.get("all_pass") is True, "selftest all_pass 아님")
    need(st.get("harness_sha256") == expected["harness_sha256"], "selftest 기록 하네스 sha 불일치")
    last, body = _docs33_item_body(_read_bytes(j(expected["docs33"])).decode("utf-8"), expected["docs33_item"])
    need(last == expected["docs33_item"], "docs/33 마지막 항목 번호 불일치")
    need(body is not None and expected["harness_sha256"] in body, "docs/33 항목 본문에 하네스 sha 없음")
    # 플래그
    for f in expected["flag_files"]:
        v = list(_find_key(_read_json(j(f)), "gin_start_still_blocked"))
        need(bool(v) and all(x is True for x in v), "플래그 불일치: " + os.path.basename(f))
    for f in expected["unblind_files"]:
        v = list(_find_key(_read_json(j(f)), "unblinding_performed"))
        need(bool(v) and all(x is False for x in v), "unblinding 플래그 불일치: " + os.path.basename(f))
    # 락
    lk = j(expected["lock"])
    if state == "S2" and os.path.exists(lk):
        pid = _read_json(lk).get("pid")
        alive = True
        try:
            os.kill(int(pid), 0)
        except (ProcessLookupError, TypeError, ValueError):
            alive = False
        except PermissionError:
            alive = True
        need(not alive, "compute lock 보유자 생존")
    else:
        need(not os.path.exists(lk), "compute lock 선존재")
    # 봉인 — 계수
    sens_pre = expected["groups"]["sens"]
    need(sealed_counts(root, exclude=sens_pre) == expected["sealed_s0"], "봉인 계수(sens 제외) 불일치")
    if state == "S0":
        need(sealed_counts(root) == expected["sealed_s0"], "봉인 계수 불일치")
    elif state == "S1":
        need(sealed_counts(root) == expected["sealed_s1"], "봉인 계수 불일치")
    # 봉인 — 지문
    fps = sealed_fingerprints(root, expected["groups"])
    for g, v in expected["fp_stat"].items():
        if g == "existing25" and state != "S0":
            continue
        need(fps[g][0] == v, "stat 지문 불일치: " + g)
    for g, v in expected["fp_noacc"].items():
        need(fps[g][1] == v, "access 제외 지문 불일치: " + g)
    # access.log 개행 수
    lines = sealed_lines(root)
    accs = sorted(x[0] for x in lines if x[2])
    need(not any(_in_prefixes(a, sens_pre) for a in accs), "sens 트리에 access.log 존재")
    need(accs == sorted(expected["access_s0"]), "access.log 집합 불일치")
    for rel, n in expected["access_s0"].items():
        exp_n = n + (1 if (rel == expected["rep1_access"] and state != "S0") else 0)
        need(_newlines(j(rel)) == exp_n, "access.log 개행 수 불일치: " + rel.split("/")[2])
    # 디렉터리 집합
    need(sorted(glob.glob(j(expected["selftest_glob"]))) == [os.path.dirname(j(expected["selftest_out"]))],
         "selftest 디렉터리 집합 불일치")
    dirs = _sens_dirs(root, expected)
    base = j(expected["out_root"])
    if state == "S0":
        need(dirs == [], "sens 출력 디렉터리 선존재")
        return {"state": state}
    need(expected["out_root"] in dirs and set(dirs) <= set(sens_pre), "sens 디렉터리 집합 불일치")
    need(set(os.listdir(base)) <= {"_sealed", "run.log"} and "_sealed" in os.listdir(base),
         "sens 최상위 항목 불일치(완료 manifest 선존재 포함)")
    eq = _eq_check(root, expected, need)
    sealed = os.path.join(base, "_sealed")
    if state == "S1":
        need(dirs == [expected["out_root"]], "S1 인데 sens 디렉터리 추가 존재")
        need(sorted(os.listdir(sealed)) == ["_equivalence"], "S1 _sealed 항목 불일치")
        return {"state": state, "equivalence": eq}
    need(set(os.listdir(sealed)) == {"_equivalence", "_partial", "checkpoint.jsonl", "env_fingerprint.json"},
         "S2 _sealed 항목 불일치")
    try:
        done = read_ckpt_verified(os.path.join(sealed, "checkpoint.jsonl"), os.path.join(sealed, "_partial"))
    except HarnessAbort as e:
        need(False, "체크포인트 무결 실패 — " + str(e))
    sess = max((int(x["session_seq"]) for x in done.values()), default=0)
    need(sess < expected["max_sessions"], "세션 상한 초과")
    names = list(expected["models"])
    for rel in dirs:
        if rel == expected["out_root"]:
            continue
        tdir = j(rel)
        need(os.listdir(tdir) == ["_sealed"], "rep/consensus 트리 항목 불일치")
        allowed = {("consensus_%s.npz" if rel == expected["cons_tree"] else "oof_%s.npz") % m for m in names}
        need(set(os.listdir(os.path.join(tdir, "_sealed"))) <= allowed, "rep/consensus 트리에 비완료·이외 파일")
    return {"state": state, "equivalence": eq, "n_done": len(done)}


# ═══════════════════════════════════════════════════════════════════════════
# 오케스트레이션 (J3 — 블록 I fit_fold/predict_fold 와 같은 논리 · 블록 목록 인자)
# ═══════════════════════════════════════════════════════════════════════════
def check_dims(blocks, order=None):
    for b, n in DIM_ASSERT.items():
        if b in blocks and (order is None or b in order):
            assert blocks[b].dim == n, "%s dim 불일치" % b


def make_blocks_h(d):
    """F5 — 블록 I make_blocks 와 같은 생성자·인자 + 신규 2블록(B_m1b_pchembl · B_fam_selfclust)."""
    blocks = {
        "B0": MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"]),
        "B1": CountMaskBlock(d["ntgt"], d["mask"]),
        "B_seq": SeqBlock(d["emb"], d["mask"], pca_k=PCA_K),
        "B_m1b": M1bCovariateBlock(d["cov_by_cid"], d["cid_order"], include_pchembl=False, name="B_m1b"),
        "B_m1b_pchembl": M1bCovariateBlock(d["cov_by_cid"], d["cid_order"], include_pchembl=True,
                                           name="B_m1b_pchembl"),
        "B_fam_selfclust": FamilyBlock(d["cid2families_sc"], d["cid_order"], name="B_fam_selfclust"),
    }
    assert set(blocks) == set(FIT_ORDER)
    check_dims(blocks)
    return blocks


def fit_blocks_h(blocks, ids, tr, mask, fit_order=FIT_ORDER):
    """fold train 에서만 fit + 누수 assert(하드) + B_seq fit 모집단 == train ∩ mask."""
    assert all(b in fit_order for b in ids), "fit 순서 밖 블록"
    order = [b for b in fit_order if b in ids]
    for b in order:
        blocks[b].fit(tr)
    leak = {}
    for b in order:
        rec = blocks[b].leakage_assert(tr)
        assert rec["leak_rows"] == 0, "%s leak_rows != 0" % b
        leak[b] = int(rec["leak_rows"])
    if "B_seq" in order:
        expect = np.zeros(len(mask), dtype=bool)
        expect[tr] = True
        expect &= np.asarray(mask).astype(bool)
        assert np.array_equal(blocks["B_seq"]._fit_rows_mask, expect), "B_seq fit 모집단 != train∩매핑"
    check_dims(blocks, order)
    return leak, order


def predict_h(blocks, ids, tr, te, Y):
    """블록 I predict_fold 축자 — hstack 순서 = ids(JSON 리스트) 순서 · float32 · rf_fit_predict(seed=42)."""
    Xtr = np.hstack([blocks[b].transform(tr) for b in ids]).astype(np.float32)
    Xte = np.hstack([blocks[b].transform(te) for b in ids]).astype(np.float32)
    assert SEED == 42, "RF random_state != 42"
    P = rf_fit_predict(Xtr, Y[tr], Xte, seed=SEED)
    return P, int(Xtr.shape[1])


def _write_once(path, data):
    """완료 파일 선존재 시 덮어쓰기 0 — 같은 바이트면 건너뜀, 다르면 중단."""
    if os.path.exists(path):
        if sha256_file(path) != sha256_bytes(data):
            raise HarnessAbort("완료 파일 선존재·바이트 불일치 — 덮어쓰기 금지: " + os.path.basename(path))
        return False
    _atomic_bytes(path, data)
    return True


# ═══════════════════════════════════════════════════════════════════════════
# core — 45 fit → OOF 9 → consensus 3 → 공개 2종
# ═══════════════════════════════════════════════════════════════════════════
def core(d, fold_of_row_by_rep, out_root, expected, fault=None):
    t_start = time.perf_counter()
    models = expected["models"]
    names = list(models)
    seed_map = expected["seed_map"]
    reps = list(seed_map)
    nf = expected["n_fold"]
    base = os.path.join(out_root, expected["out_root"])
    sealed = os.path.join(base, "_sealed")
    pdir = os.path.join(sealed, "_partial")
    ckpt = os.path.join(sealed, "checkpoint.jsonl")
    envp = os.path.join(sealed, "env_fingerprint.json")
    runlog = os.path.join(base, "run.log")
    log = []

    def step(tag, msg):
        line = "%s\t%s\t%s" % (now_kst(), tag, msg)
        log.append(line)
        print(line, flush=True)

    if reps != sorted(reps):
        raise HarnessAbort("반복 순서 1→2→3 아님")
    if os.path.exists(os.path.join(base, "manifest_public.json")):
        raise HarnessAbort("완료 manifest 선존재 — 재실행 금지")
    eq = _read_json(os.path.join(base, EQ_DIR, EQ_JSON))
    if eq.get("byte_identical") is not True:
        raise HarnessAbort("equivalence 미통과 — run 금지")
    cid_arr = np.asarray(d["cid_order"], dtype=np.int64)
    Y = d["Ym"]
    N, K = Y.shape
    if (N, K) != (expected["n_drugs"], expected["n_pt"]) or len(cid_arr) != N:
        raise HarnessAbort("라벨 shape 불일치")
    for r in reps:
        fr = fold_of_row_by_rep[r]
        if fr.shape != (N,) or set(np.unique(fr).tolist()) != set(range(nf)):
            raise HarnessAbort("fold 배정 형식 불일치")
    counts_start = sealed_counts(out_root)

    # 환경 지문 · 체크포인트
    env_now = env_fingerprint(expected)
    if os.path.exists(envp):
        if _read_json(envp) != env_now:
            raise HarnessAbort("환경 지문 불일치 — 재개 금지")
    else:
        os.makedirs(pdir, exist_ok=False)
        _atomic_bytes(envp, _json_bytes(env_now))
    done = read_ckpt_verified(ckpt, pdir)
    session_seq = max((int(x["session_seq"]) for x in done.values()), default=0) + 1
    if session_seq > expected["max_sessions"]:
        raise HarnessAbort("세션 상한 초과")
    total = len(names) * len(reps) * nf
    step("start", "session %d · done %d/%d · models %d · repeats %d · folds %d"
         % (session_seq, len(done), total, len(names), len(reps), nf))

    blocks = make_blocks_h(d)
    n_new = 0
    for model in names:
        ids = models[model]
        for r in reps:
            fr = fold_of_row_by_rep[r]
            for k in range(nf):
                key = (r, model, k)
                if key in done:
                    continue
                if fault is not None and n_new >= fault["stop_after"]:
                    raise FaultStop("fault stop")
                te = np.where(fr == k)[0]
                tr = np.where(fr != k)[0]
                if not bool((Y[tr].sum(0) >= 1).all()):
                    raise HarnessAbort("outer train PT 양성 0 존재")
                pp = os.path.join(pdir, partial_name(r, model, k))
                if os.path.exists(pp):
                    raise HarnessAbort("orphan partial 선존재")
                t1 = time.perf_counter()
                leak, order = fit_blocks_h(blocks, ids, tr, d["mask"])
                P, dim = predict_h(blocks, ids, tr, te, Y)
                wall = time.perf_counter() - t1
                if P.shape != (len(te), K) or P.dtype != np.float32 or not bool(np.isfinite(P).all()):
                    raise HarnessAbort("예측 행렬 형식 불일치")
                _atomic_npy(pp, P)
                rec = {"repeat": r, "model": model, "fold": k, "n_train": int(len(tr)), "n_test": int(len(te)),
                       "dim": dim, "wall_s": round(wall, 3), "peak_rss_gib": round(peak_rss_gib(), 3),
                       "sha256_partial": sha256_file(pp), "ts_kst": now_kst(), "session_seq": session_seq,
                       "leak_rows": leak, "blocks_fit": [[b, int(blocks[b].dim)] for b in order]}
                _append_line(ckpt, json.dumps({f: rec[f] for f in CKPT_FIELDS}, ensure_ascii=False))
                done[key] = rec
                n_new += 1
                step("fit", "%s rep%d fold%d · train %d test %d · dim %d · leak 0 · wall %ds · %d/%d"
                     % (model, r, k, len(tr), len(te), dim, int(round(wall)), len(done), total))
    if len(done) != total:
        raise HarnessAbort("완주 수 불일치")
    step("fits", "all %d fits complete · new this session %d" % (total, n_new))

    # 반복 OOF 조립
    oof = {}
    for model in names:
        for r in reps:
            fr = fold_of_row_by_rep[r]
            A = np.full((N, K), np.nan, dtype=np.float64)
            for k in range(nf):
                pp = os.path.join(pdir, partial_name(r, model, k))
                pb = _read_bytes(pp)
                if sha256_bytes(pb) != done[(r, model, k)]["sha256_partial"]:
                    raise HarnessAbort("partial sha 불일치(조립): " + os.path.basename(pp))
                A[np.where(fr == k)[0]] = np.load(io.BytesIO(pb), allow_pickle=False)
            if np.isnan(A).any():
                raise HarnessAbort("OOF NaN 존재")
            oof[(model, r)] = A
    n_written = 0
    for r, s in seed_map.items():
        sd = os.path.join(out_root, expected["rep_tree"].format(r=r, s=s), "_sealed")
        os.makedirs(sd, exist_ok=True)
        for model in names:
            n_written += _write_once(os.path.join(sd, "oof_%s.npz" % model),
                                     _npz_bytes(oof=oof[(model, r)], cid=cid_arr, fold=fold_of_row_by_rep[r]))
    step("seal", "repeat OOF files %d" % (len(names) * len(reps)))
    cdir = os.path.join(out_root, expected["cons_tree"], "_sealed")
    os.makedirs(cdir, exist_ok=True)
    for model in names:
        cons = build_consensus([oof[(model, r)] for r in reps])
        n_written += _write_once(os.path.join(cdir, "consensus_%s.npz" % model),
                                 _npz_bytes(consensus=cons, cid=cid_arr))
    step("seal", "consensus files %d · newly written %d" % (len(names), n_written))

    # 공개 산출
    sealed_files = []
    for pre in expected["groups"]["sens"]:
        for dp, _dn, fn in os.walk(os.path.join(out_root, pre, "_sealed")):
            for f in fn:
                p = os.path.join(dp, f)
                sealed_files.append({"name": os.path.relpath(p, out_root), "bytes": os.path.getsize(p),
                                     "sha256": sha256_file(p)})
    sealed_files.sort(key=lambda x: x["name"])
    if any(x["name"].endswith(".tmp") for x in sealed_files):
        raise HarnessAbort("tmp 잔존")
    per_fit = {}
    for (r, model, k), rec in sorted(done.items(), key=lambda kv: (names.index(kv[0][1]), kv[0][0], kv[0][2])):
        ent = {b: int(n) for b, n in rec["blocks_fit"]}
        ent["total"] = int(rec["dim"])
        per_fit["%s|rep%d|fold%d" % (model, r, k)] = ent
    counts_end = sealed_counts(out_root)
    import sklearn
    pub = {
        "_doc": ("블록 BB (docs/117) 공개 manifest — 개수·시각·차원·wall·RSS·불리언·봉인 파일 이름/바이트/sha256 뿐. "
                 "AP·Δ·부호·p·CI·예측값 요약은 계산하지도 기록하지도 않았다."),
        "block": "BB (docs/117)", "completed": True, "ts_completed_kst": now_kst(),
        "models": names, "n_fits": total, "n_repeats": len(reps), "n_folds": nf,
        "fold_sizes": {"rep%d" % r: [int((fold_of_row_by_rep[r] == k).sum()) for k in range(nf)] for r in reps},
        "block_dims": {"per_fit": per_fit},
        "equivalence_byte_identical": True,
        "input_checks": {"ladder_freeze_sha_match": True, "models_from_ladder_freeze_json": True,
                         "fold_rows_match": True, "leak_rows_zero_all_fits": True,
                         "train_positive_ge1_all_folds": True, "oof_nan_zero": True,
                         "checkpoint_integrity": True, "equivalence_verified_before_run": True,
                         "no_overwrite": True},
        "sealed_files": sealed_files,
        "sealed_counts_start": counts_start, "sealed_counts_end": counts_end,
        "wall_seconds": round(time.perf_counter() - t_start, 3),
        "peak_rss_gib": round(max([peak_rss_gib()] + [float(x["peak_rss_gib"]) for x in done.values()]), 3),
        "n_sessions": session_seq,
        "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
        "pandas": pd.__version__,
        "harness_sha256": expected["harness_sha256"], "selftest_sha256": expected["selftest_sha256"],
        "ladder_freeze_sha256": expected["ladder"][1],
        "values_disclosed": False, "unblinding_performed": False,
    }
    if set(pub) != PUBLIC_TOP_KEYS or set(pub["input_checks"]) != PUBLIC_CHECK_KEYS \
            or any(set(f) != PUBLIC_FILE_KEYS for f in sealed_files) \
            or set(counts_start) != set(COUNT_KEYS) or set(counts_end) != set(COUNT_KEYS):
        raise HarnessAbort("manifest_public 화이트리스트 불일치")
    step("public", "manifest_public · sealed files %d · sessions %d" % (len(sealed_files), session_seq))
    for line in log:
        _append_line(runlog, line)
    _atomic_bytes(os.path.join(base, "manifest_public.json"), _json_bytes(pub))
    return pub


# ═══════════════════════════════════════════════════════════════════════════
# stage_verify · stage_run (실저장소)
# ═══════════════════════════════════════════════════════════════════════════
def load_models(root):
    rel, sha = LADDER_FREEZE
    b = _read_bytes(os.path.join(root, rel))
    if sha256_bytes(b) != sha:
        raise HarnessAbort("ladder_freeze sha 불일치")
    return json.loads(b.decode("utf-8"))["sensitivity_models"]


def expected_real(harness_sha, selftest_sha):
    return {
        "models": load_models(ROOT), "seed_map": SEED_MAP, "n_fold": N_FOLD, "n_pt": N_PT, "n_drugs": N_DRUGS,
        "out_root": OUT_ROOT, "out_glob": OUT_GLOB, "rep_tree": REP_TREE, "cons_tree": CONS_TREE,
        "selftest_out": SELFTEST_OUT, "selftest_glob": SELFTEST_GLOB,
        "frozen": FROZEN, "ladder": LADDER_FREEZE, "n_inputs16": N_INPUTS16, "rest_public": REST_PUBLIC,
        "split_dir": SPLIT_DIR, "audit": AUDIT, "equiv_ref": EQUIV_REF, "equiv_ref_sha": EQUIV_REF_SHA,
        "docs33": DOCS33, "docs33_item": DOCS33_ITEM, "flag_files": FLAG_FILES, "unblind_files": UNBLIND_FILES,
        "lock": LOCK_REL, "groups": GROUP_PREFIXES, "fp_stat": FP_STAT, "fp_noacc": FP_NOACC,
        "access_s0": ACCESS_S0, "rep1_access": REP1_ACCESS,
        "sealed_s0": SEALED_S0, "sealed_s1": SEALED_S1, "sealed_after": SEALED_AFTER,
        "max_sessions": MAX_SESSIONS,
        "harness_sha256": harness_sha, "selftest_sha256": selftest_sha,
    }


def _expected_now():
    me = sha256_file(os.path.abspath(__file__))
    st = os.path.join(ROOT, SELFTEST_OUT)
    return expected_real(me, sha256_file(st) if os.path.isfile(st) else None)


def real_fold_rows(d):
    """확증 split 판독(재생성 0) — folds.json ↔ fold_membership.csv 일치 assert."""
    cids = [int(c) for c in d["cid_order"]]
    out = {}
    for r in SEED_MAP:
        fr = fold_of_row_for(r, d["cid_order"])
        fm = read_fold_membership(r)
        assert list(fm["cid"].astype(int)) == cids, "fold_membership cid 정렬 불일치"
        assert np.array_equal(fm["fold"].values, fr), "folds.json != fold_membership"
        out[r] = fr
    return out


def _i3_consistency(d, fobr):
    Y = d["Ym"]
    assert Y.shape == (N_DRUGS, N_PT), "master 규모 불일치"
    sizes = {}
    for r in SEED_MAP:
        fm = read_fold_membership(r)
        by_group = fm.groupby("scaffold")["fold"].nunique()
        assert len(by_group) == N_SCAFFOLD_GROUPS, "scaffold 그룹 수 불일치"
        assert int((by_group > 1).sum()) == 0, "scaffold 그룹 fold 교차"
        fr = fobr[r]
        for k in range(N_FOLD):
            assert int((Y[fr != k].sum(0) < 1).sum()) == 0, "rare-PT 위반"
        sizes["rep%d" % r] = [int((fr == k).sum()) for k in range(N_FOLD)]
    return sizes


def _j6a_dev_dims(d, E):
    """J6(a) — seed-42 개발 split train 에서 블록만 fit → 차원 정확 대조(라벨 미사용)."""
    smoke = json.loads(_read_bytes(os.path.join(ROOT, SMOKE_STATS[0])).decode("utf-8"))
    lf = json.loads(_read_bytes(os.path.join(ROOT, LADDER_FREEZE[0])).decode("utf-8"))
    bd, ss = smoke["block_dims_seed42_dev"], smoke["sensitivity_smoke"]
    tr = np.where(d["sp"] == "train")[0]
    blocks = make_blocks_h(d)
    got = {}
    for m, ids in E["models"].items():
        fit_blocks_h(blocks, ids, tr, d["mask"])
        got[m] = int(np.hstack([blocks[b].transform(tr[:8]) for b in ids]).astype(np.float32).shape[1])
        for b in ids:
            got[b] = int(blocks[b].dim)
    exp = {"B_m1b_pchembl": bd["B_m1b_pchembl"], "B_fam_selfclust": bd["B_fam_selfclust"]}
    exp.update({m: int(ss[m]["side_dim"]) for m in E["models"]})
    ok = (lf["blocks_frozen"]["B_fam_selfclust"]["dim_seed42_dev"] == bd["B_fam_selfclust"]
          and all(got[k] == exp[k] == J6A_EXPECT[k] for k in J6A_EXPECT))
    return ok, {k: got[k] for k in J6A_EXPECT}, int(len(tr))


def _j6b_pfam_crosscheck(d, fobr):
    """J6(b) — 확증 rep1 fold0 primary P-FAM 을 하네스 오케스트레이션 vs 블록 I fit_fold/predict_fold 로
    각각 계산해 P.tobytes() 동일 확인(메모리 내 · 저장·출력 0 · 봉인 판독 0)."""
    Y = d["Ym"]
    fr = fobr[EQUIV_REP]
    te, tr = np.where(fr == EQUIV_FOLD)[0], np.where(fr != EQUIV_FOLD)[0]
    hb = make_blocks_h(d)
    hb["B_fam"] = FamilyBlock(d["cid2families_bio"], d["cid_order"], name="B_fam")
    ids = MODEL_BLOCKS[XCHECK_MODEL]
    fit_blocks_h(hb, ids, tr, d["mask"], fit_order=FIT_ORDER + ["B_fam"])
    P_h, dim_h = predict_h(hb, ids, tr, te, Y)
    rb = cor.make_blocks(d)
    cor.fit_fold(rb, XCHECK_MODEL, tr, d, len(d["cid_order"]))
    P_r, dim_r = cor.predict_fold(rb, XCHECK_MODEL, tr, te, Y)
    same = P_h.dtype == P_r.dtype and P_h.shape == P_r.shape and P_h.tobytes() == P_r.tobytes()
    return bool(same and dim_h == dim_r), dim_h


def stage_verify():
    E = _expected_now()
    gate(ROOT, E, "S0")
    cl.gate_a_load("BB verify entry")
    log = []

    def step(tag, msg):
        line = "%s\tverify\t%s\t%s" % (now_kst(), tag, msg)
        log.append(line)
        print(line, flush=True)

    with cl.ComputeLock(script="confirmatory_oof_sens.py --stage verify", role="runner"):
        t0 = time.perf_counter()
        step("start", "gate S0 passed · lock acquired")
        d = load_frozen()
        fobr = real_fold_rows(d)
        sizes = _i3_consistency(d, fobr)
        step("I-3", "consistency PASS · drugs %d · scaffold groups %d · cross 0 · rare-PT 0 · fold sizes %s"
             % (N_DRUGS, N_SCAFFOLD_GROUPS, json.dumps(sizes)))
        j6a_ok, j6a_dims, n_dev = _j6a_dev_dims(d, E)
        step("J6a", "dev split train %d · dims %s · match %s" % (n_dev, json.dumps(j6a_dims), j6a_ok))
        if not j6a_ok:
            raise HarnessAbort("J6(a) 차원 불일치 — run 금지")
        j6b_ok, j6b_dim = _j6b_pfam_crosscheck(d, fobr)
        step("J6b", "P-FAM rep1 fold0 harness vs block-I bytes identical %s · dim %d" % (j6b_ok, j6b_dim))
        if not j6b_ok:
            raise HarnessAbort("J6(b) 교차 대조 불일치 — run 금지")
        # F6 바이트 동일성
        Y = d["Ym"]
        fr = fobr[EQUIV_REP]
        te, tr = np.where(fr == EQUIV_FOLD)[0], np.where(fr != EQUIV_FOLD)[0]
        blocks = make_blocks_h(d)
        ids = MODEL_BLOCKS[EQUIV_MODEL]
        leak, order = fit_blocks_h(blocks, ids, tr, d["mask"])
        P, dim = predict_h(blocks, ids, tr, te, Y)
        repro = np.zeros((len(te), Y.shape[1]), dtype=np.float64)
        repro[:] = P
        acc = os.path.join(ROOT, REP1_ACCESS)
        if not _ends_with_newline(acc) or _newlines(acc) != ACCESS_S0[REP1_ACCESS]:
            raise HarnessAbort("rep1 access.log 상태 불일치")
        ts_read = now_kst()
        _append_line(acc, json.dumps({
            "ts_kst": ts_read, "type": "machine_read",
            "purpose": "블록 BB F6 코드경로 바이트 동일성 증명(M2b rep1 fold0 슬라이스 비교)",
            "human_exposure": False, "path": EQUIV_REF, "actor": "vscode-claude",
            "step": "블록 BB(docs/117) BB-5 verify",
            "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}, ensure_ascii=False))
        step("F6", "access.log +1 line (machine_read) · ts %s" % ts_read)
        rb = _read_bytes(os.path.join(ROOT, EQUIV_REF))
        ref_sha = sha256_bytes(rb)
        if ref_sha != EQUIV_REF_SHA:
            raise HarnessAbort("판독 바이트 sha ≠ 감사 기준선 — 보류")
        with np.load(io.BytesIO(rb), allow_pickle=False) as z:
            ref_oof, ref_fold, ref_cid = z["oof"], z["fold"], z["cid"]
        if not np.array_equal(ref_fold, fr) or not np.array_equal(ref_cid, np.asarray(d["cid_order"], dtype=np.int64)):
            raise HarnessAbort("봉인 npz 의 fold/cid 배열 불일치")
        ref_slice = np.ascontiguousarray(ref_oof[te])
        byte_identical = bool(repro.dtype == ref_slice.dtype and repro.shape == ref_slice.shape
                              and repro.tobytes() == ref_slice.tobytes())
        del ref_oof, ref_slice
        step("F6", "M2b rep1 fold0 (%d rows · dim %d) byte_identical %s" % (len(te), dim, byte_identical))
        if not byte_identical:
            raise HarnessAbort("F6 바이트 동일성 FAIL — run 금지 · 보류·상신")
        base = os.path.join(ROOT, OUT_ROOT)
        os.mkdir(base)
        os.mkdir(os.path.join(base, "_sealed"))
        eqd = os.path.join(base, EQ_DIR)
        os.mkdir(eqd)
        _atomic_npy(os.path.join(eqd, EQ_NPY), repro)
        eq = {"_doc": "블록 BB (docs/117) verify 결과 — run 은 이 파일과 repro sha 대조 후에만 착수한다.",
              "model": EQUIV_MODEL, "repeat": EQUIV_REP, "fold": EQUIV_FOLD, "n_test_rows": int(len(te)),
              "n_pt": int(Y.shape[1]), "dim": dim, "dtype": str(repro.dtype), "blocks_fit": order,
              "leak_rows": leak, "byte_identical": byte_identical,
              "sha256_repro_npy": sha256_file(os.path.join(eqd, EQ_NPY)),
              "sha256_repro_slice_bytes": sha256_bytes(repro.tobytes()),
              "ref_path": EQUIV_REF, "ref_npz_sha256": ref_sha, "ts_read_kst": ts_read,
              "i3_consistency_ok": True, "j6a_dims_ok": bool(j6a_ok), "j6a_dims": j6a_dims,
              "j6b_pfam_crosscheck_identical": bool(j6b_ok),
              "harness_sha256": E["harness_sha256"], "selftest_sha256": E["selftest_sha256"],
              "wall_seconds": round(time.perf_counter() - t0, 3)}
        _atomic_bytes(os.path.join(eqd, EQ_JSON), _json_bytes(eq))
        step("done", "_equivalence 2 files written · wall %ds" % int(round(time.perf_counter() - t0)))
        for line in log:
            _append_line(os.path.join(base, "run.log"), line)
    gate(ROOT, E, "S1")
    print(json.dumps({"stage": "verify", "pass": True, "state_after": "S1"}), flush=True)
    return 0


def stage_run():
    E = _expected_now()
    state = detect_state(ROOT, E)
    if state == "S0":
        raise GateFail("verify 미수행(S0) — run 금지")
    info = gate(ROOT, E, state)
    if state == "S1":
        cl.gate_a_load("BB run entry")
    else:
        cl.gate_c_settle("BB run resume")
        print("[resume] state S2 · done %d" % info["n_done"], flush=True)
    with cl.ComputeLock(script="confirmatory_oof_sens.py --stage run", role="runner"):
        d = load_frozen()
        fobr = real_fold_rows(d)
        pub = core(d, fobr, ROOT, E, fault=None)
    end = sealed_counts(ROOT)
    fps = sealed_fingerprints(ROOT, GROUP_PREFIXES)
    fp_ok = {g: fps[g][0] == FP_STAT[g] for g in FP_STAT if g != "existing25"}
    fp_ok["existing25_noacc"] = fps["existing25"][1] == FP_NOACC["existing25"]
    ok = end == SEALED_AFTER and all(fp_ok.values()) and len(pub["sealed_files"]) == 61
    print(json.dumps({"stage": "run", "sealed_counts_end_expected": end == SEALED_AFTER, "fp_ok": fp_ok,
                      "n_sealed_files": len(pub["sealed_files"]), "n_sessions": pub["n_sessions"]},
                     ensure_ascii=False), flush=True)
    return 0 if ok else 3


def stage_status():
    E = _expected_now()
    state = detect_state(ROOT, E)
    ck = os.path.join(ROOT, OUT_ROOT, "_sealed", "checkpoint.jsonl")
    n = _newlines(ck) if os.path.exists(ck) else 0
    print(json.dumps({"state": state, "sealed_counts": sealed_counts(ROOT), "checkpoint_lines": n}), flush=True)
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# 합성 자체검사 S1~S11 (확증 입력 판독 0 · tempdir)
# ═══════════════════════════════════════════════════════════════════════════
PROVENANCE_SYN = "synthetic_fixture"
FX_HARNESS_SHA = "fixture-harness-sha-0000"
CORE_SCOPE = {"core", "make_blocks_h", "fit_blocks_h", "predict_h", "check_dims", "_write_once",
              "read_ckpt_verified", "env_fingerprint"}


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


def _docstring_ids(tree):
    ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant) \
                and isinstance(n.body[0].value.value, str):
            ids.add(id(n.body[0].value))
    return ids


def _no_decimal(s):
    return re.search(r"\d+\.\d+", s) is None


def _fx_data(n=140, K=4, rng_seed=20261004):
    """load_frozen 반환과 같은 키 구조의 합성 데이터(약물 ≥120 · 유효 SMILES · 가짜 공변량·family)."""
    rng = np.random.default_rng(rng_seed)
    cids = np.arange(5001, 5001 + n, dtype=np.int64)
    smiles = ["C" * (1 + i % 17) + "O" + ("c1ccccc1" if (i // 17) % 2 else "N") for i in range(n)]
    X = pd.DataFrame({"cid": cids, "smiles_canonical": smiles})
    Ym = (rng.random((n, K)) < 0.3).astype(int)
    mask = (rng.random(n) < 0.93).astype(np.float32)
    cov = {}
    for c in cids:
        if rng.random() < 0.8:
            cov[int(c)] = {"evidence_count": int(rng.integers(0, 50)), "mechanism_target_n": int(rng.integers(0, 4)),
                           "binding_target_n": int(rng.integers(0, 6)), "confidence_mean": float(rng.uniform(0, 9)),
                           "confidence_max": float(rng.uniform(0, 9)),
                           "first_approval_year": float(rng.integers(1950, 2020)),
                           "pchembl_mean": float(rng.uniform(4, 9)), "pchembl_max": float(rng.uniform(4, 10)),
                           "confidence_missing": int(rng.random() < 0.2), "year_missing": int(rng.random() < 0.2),
                           "pchembl_missing": int(rng.random() < 0.2)}
    fam = {int(c): set(int(x) for x in rng.integers(0, 60, size=int(rng.integers(1, 4))))
           for c, m in zip(cids, mask) if m > 0}
    d = {"X": X, "cid_order": [int(c) for c in cids], "ycols": ["pt_%d" % j for j in range(K)], "Ym": Ym,
         "sp": np.array(["train"] * n), "emb": rng.standard_normal((n, 1024)), "mask": mask,
         "ntgt": rng.integers(0, 6, n).astype(np.float64), "cid2targets": {}, "split": {},
         "cov_by_cid": cov, "cid2families_bio": {}, "n_families_total_bio": 0,
         "cid2families_sc": fam, "n_families_total_sc": 60}
    fobr = {r: rng.permutation(np.arange(n) % N_FOLD).astype(np.int64) for r in SEED_MAP}
    for r in SEED_MAP:
        for k in range(N_FOLD):
            assert (Ym[fobr[r] != k].sum(0) >= 1).all()
            assert (mask[fobr[r] != k] > 0).sum() >= PCA_K
    return d, fobr


def _fx_expected(models, n, K):
    E = expected_real(FX_HARNESS_SHA, "fixture-selftest-sha")
    E.update({"models": models, "n_drugs": n, "n_pt": K})
    return E


def _fx_prepare_s1(root, E):
    eqd = os.path.join(root, E["out_root"], EQ_DIR)
    os.makedirs(eqd)
    with open(os.path.join(eqd, EQ_NPY), "wb") as f:
        np.save(f, np.zeros((2, 2)))
    _fx_wj(os.path.join(eqd, EQ_JSON), {"byte_identical": True, "provenance": PROVENANCE_SYN,
                                         "sha256_repro_npy": sha256_file(os.path.join(eqd, EQ_NPY)),
                                         "harness_sha256": E["harness_sha256"], "i3_consistency_ok": True,
                                         "j6a_dims_ok": True, "j6b_pfam_crosscheck_identical": True})


def _fx_w(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def _fx_wj(path, obj):
    _fx_w(path, (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def _run_quiet(fn, *a, **k):
    buf = io.StringIO()
    exc = None
    with contextlib.redirect_stdout(buf):
        try:
            fn(*a, **k)
        except Exception as e:           # noqa: BLE001 — 시험 대상
            exc = e
    return buf.getvalue(), exc


def _tree_shas(root, rels):
    out = {}
    for rel in rels:
        top = os.path.join(root, rel)
        for dp, _dn, fn in os.walk(top):
            for f in fn:
                p = os.path.join(dp, f)
                out[os.path.relpath(p, root)] = sha256_file(p)
    return out


def _sealed_out_shas(root, E):
    rels = [E["rep_tree"].format(r=r, s=s) for r, s in E["seed_map"].items()] + [E["cons_tree"]]
    return _tree_shas(root, rels)


def selftest_S1_constants():
    checks = {"ladder_freeze": sha256_file(os.path.join(ROOT, LADDER_FREEZE[0])) == LADDER_FREEZE[1]}
    for rel, sha in FROZEN.items():
        checks["frozen:" + os.path.basename(rel)] = sha256_file(os.path.join(ROOT, rel)) == sha
    for rel, sha in IMPORT_TARGETS.items():
        checks["import:" + os.path.basename(rel)] = sha256_file(os.path.join(ROOT, rel)) == sha
    checks["rest_public"] = sha256_file(os.path.join(ROOT, REST_PUBLIC[0])) == REST_PUBLIC[1]
    checks["audit_sha16"] = sha256_file(os.path.join(ROOT, AUDIT[0]))[:16] == AUDIT[1]
    return _res("S1 상수·해시", checks)


def selftest_S2_binding(base_pub):
    lf = json.loads(_read_bytes(os.path.join(ROOT, LADDER_FREEZE[0])).decode("utf-8"))
    sm = lf["sensitivity_models"]
    tree = _src_tree()
    par = _parents(tree)
    docs = _docstring_ids(tree)
    lists = [list(v) for v in sm.values()] + [list(sm)]
    lit_lists, lit_names = [], []
    for n in ast.walk(tree):
        if _enclosing(par, n) not in CORE_SCOPE:
            continue
        if isinstance(n, (ast.List, ast.Tuple, ast.Set)) and len(n.elts) >= 2 and \
                all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in n.elts):
            vals = [e.value for e in n.elts]
            if vals in lists or any(set(vals) == set(x) for x in lists):
                lit_lists.append(n.lineno)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and n.value in sm:
            lit_names.append(n.lineno)
    core_reads_models = any(isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                            and n.slice.value == "models" and _enclosing(par, n) == "core" for n in ast.walk(tree))
    return _res("S2 모델 결속", {
        "harness_models_eq_json": load_models(ROOT) == sm and list(load_models(ROOT)) == list(sm),
        "three_models": len(sm) == 3,
        "model_blocks_match_for_m1b_m2b": all(MODEL_BLOCKS[m] == sm[m] for m in sm if m in MODEL_BLOCKS),
        "all_blocks_in_fit_order": all(b in FIT_ORDER for v in sm.values() for b in v),
        "fixture_public_models_eq_json_order": base_pub["models"] == list(sm),
        "core_reads_expected_models": core_reads_models,
        "no_model_block_list_literals_in_core_scope": not lit_lists,
        "no_model_name_literals_in_core_scope": not lit_names}, list_literal_lines=lit_lists,
        name_literal_lines=lit_names)


def selftest_S3_fit_order(d, fobr, models):
    blocks = make_blocks_h(d)
    calls = []
    for b, obj in blocks.items():
        orig = obj.fit

        def spy(tr, _b=b, _o=orig):
            calls.append(_b)
            return _o(tr)
        obj.fit = spy
    fr = fobr[1]
    te, tr = np.where(fr == 0)[0], np.where(fr != 0)[0]
    order_ok = True
    for _m, ids in models.items():
        calls.clear()
        leak, order = fit_blocks_h(blocks, ids, tr, d["mask"])
        order_ok &= calls == [b for b in FIT_ORDER if b in ids] and set(calls) == set(ids) and order == calls
        order_ok &= all(v == 0 for v in leak.values())
    # 누수 주입
    blocks2 = make_blocks_h(d)
    o1 = blocks2["B1"].fit

    def leaky(trr):
        o1(trr)
        blocks2["B1"]._fit_rows_mask[te[0]] = True
        return blocks2["B1"]
    blocks2["B1"].fit = leaky
    leak_caught = False
    try:
        fit_blocks_h(blocks2, ["B0", "B1"], tr, d["mask"])
    except AssertionError:
        leak_caught = True
    # B_seq fit 모집단 주입(train 의 부분집합 → 누수 assert 는 통과, 모집단 assert 가 잡아야 함)
    blocks3 = make_blocks_h(d)
    o3 = blocks3["B_seq"].fit

    def shrink(trr):
        o3(trr)
        idx = np.where(blocks3["B_seq"]._fit_rows_mask)[0]
        blocks3["B_seq"]._fit_rows_mask[idx[0]] = False
        return blocks3["B_seq"]
    blocks3["B_seq"].fit = shrink
    pop_caught = False
    try:
        fit_blocks_h(blocks3, ["B0", "B_seq"], tr, d["mask"])
    except AssertionError:
        pop_caught = True
    tree = _src_tree()
    par = _parents(tree)
    core_calls = {_call_name(n) for n in ast.walk(tree) if isinstance(n, ast.Call) and _enclosing(par, n) == "core"}
    rf_calls = {_enclosing(par, n) for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "rf_fit_predict"}
    return _res("S3 fit 순서·누수", {"fit_only_required_in_fit_order": order_ok,
                                    "leak_injection_aborts": leak_caught,
                                    "bseq_population_injection_aborts": pop_caught,
                                    "core_uses_fit_blocks_h_predict_h": {"fit_blocks_h", "predict_h"} <= core_calls,
                                    "rf_fit_predict_only_in_predict_h": rf_calls == {"predict_h"}})


def selftest_S4_dims(d):
    blocks = make_blocks_h(d)
    ok_dims = blocks["B_m1b"].dim == 10 and blocks["B_m1b_pchembl"].dim == 13
    caught = {}
    for b in ("B_m1b", "B_m1b_pchembl"):
        old = blocks[b].dim
        blocks[b].dim = old - 1
        try:
            check_dims(blocks)
            caught[b] = False
        except AssertionError:
            caught[b] = True
        blocks[b].dim = old
    return _res("S4 블록 차원", {"m1b_10_pchembl_13": ok_dims, "assert_B_m1b": caught["B_m1b"],
                               "assert_B_m1b_pchembl": caught["B_m1b_pchembl"]})


def selftest_S5_oof(root, E, d, fobr):
    pdir = os.path.join(root, E["out_root"], "_sealed", "_partial")
    ok = {"keys": True, "dtype": True, "shape": True, "nan0": True, "fold_assign": True, "cid": True, "fold_arr": True}
    N, K = d["Ym"].shape
    for r, s in E["seed_map"].items():
        for m in E["models"]:
            with np.load(os.path.join(root, E["rep_tree"].format(r=r, s=s), "_sealed", "oof_%s.npz" % m)) as z:
                ok["keys"] &= set(z.files) == {"oof", "cid", "fold"}
                A = z["oof"]
                ok["dtype"] &= A.dtype == np.float64 and z["cid"].dtype == np.int64
                ok["shape"] &= A.shape == (N, K)
                ok["nan0"] &= not np.isnan(A).any()
                ok["cid"] &= np.array_equal(z["cid"], np.asarray(d["cid_order"], dtype=np.int64))
                ok["fold_arr"] &= np.array_equal(z["fold"], fobr[r])
                for k in range(E["n_fold"]):
                    P = np.load(os.path.join(pdir, partial_name(r, m, k)))
                    ok["fold_assign"] &= np.array_equal(A[fobr[r] == k], P.astype(np.float64))
    return _res("S5 OOF 조립", ok, provenance=PROVENANCE_SYN)


def selftest_S6_consensus(root, E):
    worst_b, worst_m = 0.0, 0.0
    for m in E["models"]:
        reps = []
        for r, s in E["seed_map"].items():
            with np.load(os.path.join(root, E["rep_tree"].format(r=r, s=s), "_sealed", "oof_%s.npz" % m)) as z:
                reps.append(z["oof"])
        with np.load(os.path.join(root, E["cons_tree"], "_sealed", "consensus_%s.npz" % m)) as z:
            got, keys = z["consensus"], set(z.files)
        worst_b = max(worst_b, float(np.abs(got - build_consensus(reps)).max()))
        worst_m = max(worst_m, float(np.abs(got - np.mean(np.stack(reps), axis=0)).max()))
    tree = _src_tree()
    par = _parents(tree)
    bc = [_enclosing(par, n) for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "build_consensus"]
    own_mean = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and _enclosing(par, n) in CORE_SCOPE
                and _call_name(n) in ("mean", "average", "nanmean")]
    return _res("S6 consensus", {"equals_build_consensus_exact": worst_b == 0.0,
                                 "equals_np_mean_stack_exact": worst_m == 0.0,
                                 "keys_consensus_cid": keys == {"consensus", "cid"},
                                 "core_calls_build_consensus": "core" in bc,
                                 "no_own_mean_in_core_scope": not own_mean}, own_mean_lines=own_mean,
                provenance=PROVENANCE_SYN)


def selftest_S7_resume(tmp, E, d, fobr, base_shas):
    res, outs = {}, []
    ck_rel = os.path.join(E["out_root"], "_sealed", "checkpoint.jsonl")
    # (a) 강제 중단 → 재개 → 무중단과 바이트 동일
    ra = os.path.join(tmp, "s7a")
    _fx_prepare_s1(ra, E)
    o1, e1 = _run_quiet(core, d, fobr, ra, E, fault={"stop_after": 7})
    n_mid = _newlines(os.path.join(ra, ck_rel))
    o2, e2 = _run_quiet(core, d, fobr, ra, E)
    outs += [o1, o2]
    rows = [json.loads(x) for x in _read_bytes(os.path.join(ra, ck_rel)).decode("utf-8").splitlines()]
    res["stop_raises_faultstop"] = isinstance(e1, FaultStop) and n_mid == 7
    res["resume_completes"] = e2 is None and len(rows) == 45
    res["resume_skips_done"] = sum(1 for x in rows if x["session_seq"] == 2) == 38 \
        and sum(1 for x in rows if x["session_seq"] == 1) == 7
    res["resume_bytes_equal_uninterrupted"] = _sealed_out_shas(ra, E) == base_shas and len(base_shas) == 12
    pub = _read_json(os.path.join(ra, E["out_root"], "manifest_public.json"))
    res["n_sessions_2"] = pub["n_sessions"] == 2
    # (b) 환경 지문 불일치 → 중단
    rb = os.path.join(tmp, "s7b")
    _fx_prepare_s1(rb, E)
    _o, _e = _run_quiet(core, d, fobr, rb, E, fault={"stop_after": 3})
    envp = os.path.join(rb, E["out_root"], "_sealed", "env_fingerprint.json")
    env = _read_json(envp)
    env["numpy"] = "0.0.0-fixture"
    _fx_wj(envp, env)
    o3, e3 = _run_quiet(core, d, fobr, rb, E)
    outs += [_o, o3]
    res["env_mismatch_aborts"] = isinstance(e3, HarnessAbort) and _newlines(os.path.join(rb, ck_rel)) == 3
    # (c) partial 변조 → 재개 중단
    rc = os.path.join(tmp, "s7c")
    _fx_prepare_s1(rc, E)
    _o, _e = _run_quiet(core, d, fobr, rc, E, fault={"stop_after": 3})
    pp = os.path.join(rc, E["out_root"], "_sealed", "_partial", partial_name(1, list(E["models"])[0], 1))
    with open(pp, "wb") as f:
        np.save(f, np.ones((3, 3), dtype=np.float32))
    o4, e4 = _run_quiet(core, d, fobr, rc, E)
    outs += [_o, o4]
    res["partial_tamper_aborts"] = isinstance(e4, HarnessAbort) and _newlines(os.path.join(rc, ck_rel)) == 3
    return _res("S7 체크포인트 재개", res), outs


def selftest_S8_atomic(tmp, E, d, fobr, base_root):
    res = {}
    first = list(E["models"])[0]
    rel_oof = os.path.join(E["rep_tree"].format(r=1, s=E["seed_map"][1]), "_sealed", "oof_%s.npz" % first)
    # (a) 완료 파일 선존재(다른 바이트) → 중단 · 덮어쓰기 0
    ra = os.path.join(tmp, "s8a")
    shutil.copytree(os.path.join(base_root, E["out_root"], "_sealed"), os.path.join(ra, E["out_root"], "_sealed"))
    _fx_w(os.path.join(ra, rel_oof), b"pre-existing-garbage")
    _o, ea = _run_quiet(core, d, fobr, ra, E)
    res["preexisting_diff_aborts"] = isinstance(ea, HarnessAbort)
    res["preexisting_not_overwritten"] = _read_bytes(os.path.join(ra, rel_oof)) == b"pre-existing-garbage"
    res["no_manifest_after_abort"] = not os.path.exists(os.path.join(ra, E["out_root"], "manifest_public.json"))
    # (b) 완료 파일 선존재(같은 바이트) → 건너뛰고 완주(봉인 쓰기 중 중단 후 재개)
    rb = os.path.join(tmp, "s8b")
    shutil.copytree(os.path.join(base_root, E["out_root"], "_sealed"), os.path.join(rb, E["out_root"], "_sealed"))
    _fx_w(os.path.join(rb, rel_oof), _read_bytes(os.path.join(base_root, rel_oof)))
    _o, eb = _run_quiet(core, d, fobr, rb, E)
    res["preexisting_same_skips_and_completes"] = eb is None and \
        _sealed_out_shas(rb, E) == _sealed_out_shas(base_root, E)
    # (c) 완료 run 재실행 → 중단
    before = _tree_shas(base_root, [E["out_root"]])
    _o, ec = _run_quiet(core, d, fobr, base_root, E)
    res["rerun_after_complete_aborts"] = isinstance(ec, HarnessAbort) and _tree_shas(base_root, [E["out_root"]]) == before
    # tmp 잔존 0
    tmps = [p for p in glob.glob(os.path.join(tmp, "**", "*"), recursive=True) if p.endswith(".tmp")]
    res["no_tmp_left"] = not tmps
    return _res("S8 원자성·덮어쓰기 금지", res)


def selftest_S9_leak(base_root, E, texts_extra):
    pdir = os.path.join(base_root, E["out_root"], "_sealed", "_partial")
    vals = set()
    for f in os.listdir(pdir):
        vals |= set(np.unique(np.load(os.path.join(pdir, f))).astype(np.float64).tolist())
    for m in E["models"]:
        with np.load(os.path.join(base_root, E["cons_tree"], "_sealed", "consensus_%s.npz" % m)) as z:
            vals |= set(np.unique(z["consensus"]).tolist())
    vals -= {0.0, 1.0}
    pats = set()
    for v in vals:
        pats |= {repr(float(v)), "%.4f" % v, "%.6f" % v}
    rx = [re.compile(r"(?<![0-9.])" + re.escape(p) + r"(?![0-9])") for p in sorted(pats)]
    base = os.path.join(base_root, E["out_root"])
    pub_txt = _read_bytes(os.path.join(base, "manifest_public.json")).decode("utf-8")
    texts = {"run.log": _read_bytes(os.path.join(base, "run.log")).decode("utf-8"), "manifest_public": pub_txt,
             "stdout_and_exceptions": "\n".join(texts_extra)}
    hits = {k: sum(1 for x in rx if x.search(t)) for k, t in texts.items()}
    pub = json.loads(pub_txt)
    wl = (set(pub) == PUBLIC_TOP_KEYS and set(pub["input_checks"]) == PUBLIC_CHECK_KEYS
          and all(set(f) == PUBLIC_FILE_KEYS for f in pub["sealed_files"])
          and set(pub["sealed_counts_start"]) == set(pub["sealed_counts_end"]) == set(COUNT_KEYS))
    four = {k: len(re.findall(r"\d+\.\d{4,}", t)) for k, t in texts.items()}
    return _res("S9 누설 가드", {"nondegenerate_fixture": len(vals) > 20, "value_strings_absent": not any(hits.values()),
                               "public_keys_whitelist_exact": wl, "no_4plus_decimal_strings": not any(four.values()),
                               "values_disclosed_false": pub["values_disclosed"] is False},
                n_patterns=len(pats), hits=hits, four_decimal=four)


def selftest_S10_ast():
    tree = _src_tree()
    par = _parents(tree)
    forbidden = {"macro_ap", "average_precision_score", "emit_sign", "open_sealed", "signflip", "sign_flip",
                 "bootstrap", "paired_scaffold_bootstrap", "rq2_decision", "rq3_decision", "rq4_decision", "holm",
                 "bh_fdr", "tost_equivalence", "rqint_test", "observed_statistic", "repeat_macro_aps"}
    hits = [(_call_name(n), n.lineno) for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) in forbidden]
    bad_mods = {"sap.metrics", "sap.signflip", "sap.bootstrap", "sap.decision", "sap.rqint", "sap.redaction",
                "sklearn.metrics"}
    imp_mods, imp_names = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imp_mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imp_mods.add(n.module)
            imp_names |= {a.name for a in n.names}
            if n.module == "sap":
                imp_mods |= {"sap." + a.name for a in n.names}
    bad_import = sorted((imp_mods & bad_mods) | (imp_names & forbidden))
    net = sorted({m.split(".")[0] for m in imp_mods} & {"socket", "urllib", "requests", "http", "ftplib", "smtplib",
                                                        "asyncio", "aiohttp", "httpx", "telnetlib", "subprocess"})
    environ = [n.lineno for n in ast.walk(tree) if (isinstance(n, ast.Attribute) and n.attr == "environ")
               or (isinstance(n, ast.Call) and _call_name(n) == "getenv")]
    opts = {a.value for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "add_argument"
            for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    cl_outside = {_enclosing(par, n) for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "cl"}
    return {"forbidden_calls_zero": not hits, "forbidden_imports_zero": not bad_import,
            "network_imports_zero": not net, "os_environ_zero": not environ,
            "cli_options_exact": opts == {"--stage", "--out"},
            "cl_calls_only_in_stage_verify_run": cl_outside <= {"stage_verify", "stage_run"}}, \
        {"forbidden_hits": hits, "bad_imports": bad_import, "net": net}


@contextlib.contextmanager
def _write_guard(allowed_dirs, violations):
    allowed = [os.path.realpath(x) for x in allowed_dirs]

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
    return {"counts": sealed_counts(ROOT), "fp": {g: fps[g][0] for g in FP_STAT},
            "sens": len(glob.glob(os.path.join(ROOT, OUT_GLOB))), "pycache": _pycache_dirs(ROOT)}


# ── S11 합성 저장소 (gate 상태 판별) ────────────────────────────────────────
def _fx_repo(tmp):
    E = _fx_expected(load_models(ROOT), 10, 4)
    E["frozen"], ins = {}, {}
    for rel in FROZEN:
        if rel == LADDER_FREEZE[0]:
            continue
        _fx_w(os.path.join(tmp, rel), ("fixture:" + rel).encode())
        E["frozen"][rel] = sha256_file(os.path.join(tmp, rel))
    for i in range(N_INPUTS16):
        rel = "data/processed/fx_input_%d.bin" % i
        _fx_w(os.path.join(tmp, rel), ("in%d" % i).encode())
        ins[rel] = {"sha16": sha256_file(os.path.join(tmp, rel))[:16]}
    real = json.loads(_read_bytes(os.path.join(ROOT, LADDER_FREEZE[0])).decode("utf-8"))
    _fx_wj(os.path.join(tmp, LADDER_FREEZE[0]), {"sensitivity_models": real["sensitivity_models"],
                                                 "rf_hyperparameters": real["rf_hyperparameters"],
                                                 "seed": real["seed"], "pca_k": real["pca_k"], "inputs_sha16": ins})
    E["ladder"] = (LADDER_FREEZE[0], sha256_file(os.path.join(tmp, LADDER_FREEZE[0])))
    E["frozen"][LADDER_FREEZE[0]] = E["ladder"][1]
    splits = {}
    for r, s in SEED_MAP.items():
        sd = os.path.join(tmp, SPLIT_DIR % (r, s))
        _fx_w(os.path.join(sd, "folds.json"), b"{}")
        _fx_w(os.path.join(sd, "fold_membership.csv"), b"cid,fold\n")
        splits["rep%d_seed%d" % (r, s)] = {"folds_json_sha256": sha256_file(os.path.join(sd, "folds.json")),
                                           "fold_membership_sha256": sha256_file(os.path.join(sd, "fold_membership.csv"))}
    _fx_wj(os.path.join(tmp, REST_PUBLIC[0]), {"inputs_sha256": {"splits": splits}})
    E["rest_public"] = (REST_PUBLIC[0], sha256_file(os.path.join(tmp, REST_PUBLIC[0])))
    E["equiv_ref_sha"] = "ab" * 32
    _fx_wj(os.path.join(tmp, AUDIT[0]), {"hashes": {"sha256_all_sealed_artifacts": {EQUIV_REF: "cd" * 32,
                                                                                     "other": E["equiv_ref_sha"]}}})
    aud = _read_json(os.path.join(tmp, AUDIT[0]))
    aud["hashes"]["sha256_all_sealed_artifacts"][EQUIV_REF] = E["equiv_ref_sha"]
    _fx_wj(os.path.join(tmp, AUDIT[0]), aud)
    E["audit"] = (AUDIT[0], sha256_file(os.path.join(tmp, AUDIT[0]))[:16])
    _fx_wj(os.path.join(tmp, SELFTEST_OUT), {"all_pass": True, "harness_sha256": FX_HARNESS_SHA})
    _fx_w(os.path.join(tmp, DOCS33), ("# fx\n\n75. **a**:\nx\n\n76. **b**:\n하네스 `%s`\n" % FX_HARNESS_SHA).encode())
    for f in FLAG_FILES:
        _fx_wj(os.path.join(tmp, f), {"gin_start_still_blocked": True})
    for f in UNBLIND_FILES:
        _fx_wj(os.path.join(tmp, f), {"unblinding_performed": False})
    for g, pres in GROUP_PREFIXES.items():
        if g == "sens":
            continue
        _fx_w(os.path.join(tmp, pres[0], "_sealed", "x.bin"), b"x" * (len(g) + 1))
        _fx_w(os.path.join(tmp, pres[0], "_sealed", "access.log"), b"{}\n")
    _fx_w(os.path.join(tmp, _RUNS, "fx_old", "_sealed", "y.bin"), b"yyy")
    _fx_w(os.path.join(tmp, REP1_ACCESS), b"{}\n{}\n")
    _fx_w(os.path.join(os.path.dirname(os.path.join(tmp, REP1_ACCESS)), "oof_M2b.npz"), b"zz")
    E["sealed_s0"] = sealed_counts(tmp)
    E["sealed_s1"] = dict(E["sealed_s0"])
    E["sealed_s1"]["n_sealed_dirs"] += 1
    E["sealed_s1"]["n_sealed_files_total"] += 2
    E["sealed_s1"]["n_sealed_artifacts"] += 2
    fps = sealed_fingerprints(tmp, GROUP_PREFIXES)
    E["fp_stat"] = {g: fps[g][0] for g in FP_STAT}
    E["fp_noacc"] = {g: fps[g][1] for g in FP_NOACC}
    E["access_s0"] = {x[0]: _newlines(os.path.join(tmp, x[0])) for x in sealed_lines(tmp) if x[2]}
    return E


def _fx_to_s1(tmp, E):
    _fx_prepare_s1(tmp, E)
    with open(os.path.join(tmp, REP1_ACCESS), "a") as f:
        f.write("{}\n")


def _fx_to_s2(tmp, E):
    sealed = os.path.join(tmp, E["out_root"], "_sealed")
    os.makedirs(os.path.join(sealed, "_partial"))
    m = list(E["models"])[0]
    pp = os.path.join(sealed, "_partial", partial_name(1, m, 0))
    with open(pp, "wb") as f:
        np.save(f, np.zeros((2, 2), dtype=np.float32))
    rec = {k: 0 for k in CKPT_FIELDS}
    rec.update({"repeat": 1, "model": m, "fold": 0, "sha256_partial": sha256_file(pp), "session_seq": 1})
    _fx_w(os.path.join(sealed, "checkpoint.jsonl"), (json.dumps(rec) + "\n").encode())
    _fx_wj(os.path.join(sealed, "env_fingerprint.json"), {"fixture": True})


def selftest_S11_gate(tmp_root):
    res, msgs = {}, []

    def attempt(tag, prep, state, expect_pass, expect_detect=None):
        tmp = os.path.join(tmp_root, "s11_" + tag)
        os.makedirs(tmp)
        E = _fx_repo(tmp)
        prep(tmp, E)
        try:
            gate(tmp, E, state)
            passed, msg = True, ""
        except GateFail as e:
            passed, msg = False, str(e)
        msgs.append(msg)
        ok = passed == expect_pass and _no_decimal(msg)
        if expect_detect is not None:
            ok &= detect_state(tmp, E) == expect_detect
        res[tag] = ok

    def p_none(t, E):
        return None

    def p_s1(t, E):
        _fx_to_s1(t, E)

    def p_s2(t, E):
        _fx_to_s1(t, E)
        _fx_to_s2(t, E)

    def p_s1_eq1(t, E):
        _fx_to_s1(t, E)
        os.remove(os.path.join(t, E["out_root"], EQ_DIR, EQ_NPY))

    def p_s1_acc19(t, E):
        _fx_to_s1(t, E)
        with open(os.path.join(t, REP1_ACCESS), "a") as f:
            f.write("{}\n")

    def p_s0_two_selftest(t, E):
        os.makedirs(os.path.join(t, _RUNS, "v3_sensoof_other"))

    def p_s2_orphan(t, E):
        p_s2(t, E)
        with open(os.path.join(t, E["out_root"], "_sealed", "_partial", "rep9_X_fold0.npy"), "wb") as f:
            f.write(b"x")

    def p_s2_ckpt_sha(t, E):
        p_s2(t, E)
        m = list(E["models"])[0]
        with open(os.path.join(t, E["out_root"], "_sealed", "_partial", partial_name(1, m, 0)), "wb") as f:
            f.write(b"tampered")

    def p_s0_docs77(t, E):
        with open(os.path.join(t, DOCS33), "a", encoding="utf-8") as f:
            f.write("\n77. **later**:\nx\n")

    def p_s1_manifest(t, E):
        _fx_to_s1(t, E)
        _fx_w(os.path.join(t, E["out_root"], "manifest_public.json"), b"{}")

    attempt("a_S0_pass", p_none, "S0", True, "S0")
    attempt("b_S1_pass", p_s1, "S1", True, "S1")
    attempt("c_S1_state_as_S0_fail", p_s1, "S0", False)
    attempt("d_S2_pass", p_s2, "S2", True, "S2")
    attempt("e_S2_state_as_S1_fail", p_s2, "S1", False)
    attempt("f_equivalence_one_file_fail", p_s1_eq1, "S1", False, "S1")
    attempt("g_rep1_access_plus2_fail", p_s1_acc19, "S1", False)
    attempt("h_two_selftest_dirs_fail", p_s0_two_selftest, "S0", False)
    attempt("i_orphan_partial_fail", p_s2_orphan, "S2", False)
    attempt("j_ckpt_sha_mismatch_fail", p_s2_ckpt_sha, "S2", False)
    attempt("k_docs33_last_77_fail", p_s0_docs77, "S0", False)
    attempt("l_manifest_preexist_fail", p_s1_manifest, "S1", False)
    res["messages_no_decimal"] = all(_no_decimal(m) for m in msgs)
    return _res("S11 gate 상태 판별", res), msgs


def run_selftest():
    before = _real_state()
    cl_calls = {"n": 0}
    orig_cl = {k: getattr(cl, k) for k in ("gate_a_load", "gate_b_exclusive", "gate_c_settle", "ComputeLock")}

    def _cl_trap(*_a, **_k):
        cl_calls["n"] += 1
        raise RuntimeError("cl 호출 금지(selftest)")

    for k in orig_cl:
        setattr(cl, k, _cl_trap)
    tmp = tempfile.mkdtemp(prefix="bb_selftest_")
    violations, results, msgs = [], [], []
    t0 = time.perf_counter()
    try:
        with _write_guard([tmp], violations):
            results.append(selftest_S1_constants())
            d, fobr = _fx_data()
            models = load_models(ROOT)
            E = _fx_expected(models, *d["Ym"].shape)
            base = os.path.join(tmp, "base")
            _fx_prepare_s1(base, E)
            base_out, base_exc = _run_quiet(core, d, fobr, base, E)
            if base_exc is not None:
                raise RuntimeError("base fixture run 실패: %s %s" % (type(base_exc).__name__, base_exc))
            base_pub = _read_json(os.path.join(base, E["out_root"], "manifest_public.json"))
            base_shas = _sealed_out_shas(base, E)
            results.append(selftest_S2_binding(base_pub))
            results.append(selftest_S3_fit_order(d, fobr, models))
            results.append(selftest_S4_dims(d))
            results.append(selftest_S5_oof(base, E, d, fobr))
            results.append(selftest_S6_consensus(base, E))
            r7, outs7 = selftest_S7_resume(tmp, E, d, fobr, base_shas)
            results.append(r7)
            results.append(selftest_S8_atomic(tmp, E, d, fobr, base))
            results.append(selftest_S9_leak(base, E, [base_out] + outs7))
            ast_checks, ast_detail = selftest_S10_ast()
            r11, msgs = selftest_S11_gate(tmp)
    finally:
        for k, v in orig_cl.items():
            setattr(cl, k, v)
        shutil.rmtree(tmp, ignore_errors=True)
    after = _real_state()
    hyg = dict(ast_checks)
    hyg.update({"runtime_write_guard_violations_zero": not violations,
                "cl_calls_during_selftest_zero": cl_calls["n"] == 0,
                "real_sealed_counts_unchanged": after["counts"] == before["counts"],
                "real_fp_unchanged": after["fp"] == before["fp"],
                "sens_dir_not_created": after["sens"] == before["sens"] == 0,
                "pycache_unchanged": after["pycache"] == before["pycache"]})
    results.append(_res("S10 AST·위생", hyg, guard_violations=violations[:5], **ast_detail))
    results.append(r11)
    order = {"S%d" % i: i for i in range(1, 12)}
    results.sort(key=lambda x: order[x["name"].split()[0]])
    n_pass = sum(1 for x in results if x["pass"])
    return {
        "_doc": "docs/117 블록 BB / BB-3 — 합성 자체검사 S1~S11. 확증 입력 판독 0. 모든 수치는 합성 fixture 산출물.",
        "provenance": PROVENANCE_SYN, "block": "BB (docs/117)",
        "harness_path": "v3_Multimodal/src/confirmatory_oof_sens.py",
        "harness_sha256": sha256_file(os.path.abspath(__file__)),
        "ladder_freeze_sha256": LADDER_FREEZE[1],
        "python": platform.python_version(), "numpy": np.__version__,
        "ts_kst": now_kst(), "wall_seconds": round(time.perf_counter() - t0, 3),
        "n_tests": len(results), "n_pass": n_pass, "n_skip": 0, "all_pass": n_pass == len(results) == 11,
        "tests": results, "s11_messages": msgs,
        "confirmatory_values_read": 0, "sealed_human_read": 0, "network_calls": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="블록 BB — 사전지정 민감도 RF OOF 3종 학습·봉인")
    ap.add_argument("--stage", choices=["selftest", "verify", "run", "status"], default="selftest")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.stage != "selftest":
        if a.out:
            raise SystemExit("--out 은 selftest 전용")
        return {"verify": stage_verify, "run": stage_run, "status": stage_status}[a.stage]()
    if a.out and os.path.abspath(a.out) != os.path.join(ROOT, SELFTEST_OUT):
        raise SystemExit("--out 은 SELFTEST_OUT 만 허용")
    res = run_selftest()
    out = os.path.join(ROOT, SELFTEST_OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    _atomic_bytes(out, (json.dumps(res, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"stage": "selftest", "all_pass": res["all_pass"], "n_pass": res["n_pass"],
                      "n_tests": res["n_tests"], "fails": {t["name"]: t["fails"] for t in res["tests"] if not t["pass"]}},
                     ensure_ascii=False))
    return 0 if res["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
