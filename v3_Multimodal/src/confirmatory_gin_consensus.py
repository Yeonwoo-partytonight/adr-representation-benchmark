"""confirmatory_gin_consensus.py — 블록 AW (docs/113): GIN consensus 조립 + 셀별 macro AP·Δ 봉인 산출.

동결 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json` 의 **S1_metrics_contract 를 그대로 구현**한다.
모델 목록·학습 시드 값 t·rep 쌍·경로 패턴·셀 수는 명세 JSON 에서 읽는다(하네스에 재기술 0).

⛔ 무결성 (docs/113 §2)
  · 봉인 «값» 은 `run` stage 안에서만 기계 판독한다. stdout·run.log·manifest_public·예외 메시지에
    AP·Δ·n_eval·n_excluded_undefined·best_ep·best_v 등 값을 **내보내지 않는다.**
  · Δ 의 부호를 따로 산출하지 않는다(emit_sign 0 · 부호 비교 0 · H2). Δ 값은 metrics_full.json 에만 봉인.
  · consensus = `sap.consensus.build_consensus`, AP = `sap.metrics.macro_ap` 를 import 해 그대로 호출(재구현 0).
  · 판정 함수·rqint_test·bootstrap·open_sealed 호출 0. 네트워크 0 · os.environ 판독 0.

구조
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
import fnmatch
import glob
import hashlib
import io
import itertools
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
MANIFEST_T4 = "experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json"
MANIFEST_T4_SHA256 = "a59ab54afd51508543a3ca952a5147ffc0c8687f997aacf42362ab699683ea59"
MASTER_X = ("data/processed/master_X.parquet",
            "788c8a64d19e8c3cc030476e7b2eb7f207246e3af6e73304d97f2fc9aa2ae6e6")
MASTER_Y = ("data/processed/master_Y.parquet",
            "bd23584342de6482e50f218bd409740acc2a00eeac86ee95bd89952bc3d18018")
SAP_MODULES = {
    "v3_Multimodal/src/sap/consensus.py":
        "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91",
    "v3_Multimodal/src/sap/metrics.py":
        "a7d3fe4fe9e87983b35b086b0c464bde1e710e013f98813a2f28a2b48c8b2004",
    "v3_Multimodal/src/sap/rqint.py":
        "eb842bc98140e9c55b67bc1563cd5573c3b294885778f23744468b712c498b26",
}
COMPUTE_LOCK = ("v3_Multimodal/src/compute_lock.py",
                "b03a0b0012948b340f410670d6b045f279e1b21b4faa293bb45bbc2e99a6d738")

EXPECTED_SEALED_BEFORE = {"n_sealed_dirs": 29, "n_sealed_files_total": 727,
                          "n_sealed_artifacts": 707, "n_access_log": 20}
EXPECTED_SEALED_AFTER = {"n_sealed_dirs": 30, "n_sealed_files_total": 750,
                         "n_sealed_artifacts": 729, "n_access_log": 21}
FP_CONFIRMATORY = "5440aefcded112bcd425f61968f9974898f26efe2beab69155f7a5a47cf3333b"
FP_STABILITY = "b4b493d265824709a242a12d37334659bf78a75bd51a46f8b0174f058d6e6cec"
FP_EXISTING25 = "8cf3d207a42ed7c247e9de62931f003a075cdc6ac440794c7153cea49c54d1c9"
STABILITY_PREFIX = "experiments/runs/v3_gin_stability"
CONSENSUS_GLOB = "experiments/runs/v3_gin_confirm_consensus*"
SELFTEST_OUT = "experiments/runs/v3_gin_consensus_harness_selftest/selftest_consensus.json"

N_PT = 370
N_DRUGS = 1092
N_FOLD = 5                      # 확증 5-fold (confirmatory_gin_train.N_FOLD 와 동일)
CKPT_FIELDS = ["rep", "fold", "model", "train_seed", "completed_at_kst",
               "artifact_sha256", "n_epochs", "wall_seconds"]
OOF_KEYS = {"P", "y", "pt_index", "cid_order"}
PARTIAL_KEYS = {"P_test", "best_ep", "best_v"}
FORBIDDEN_KEY_SUBSTR_SEALED = ("sign", "direction", "positive", "negative")
FORBIDDEN_KEY_SUBSTR_PUBLIC = ("macro_ap", "delta", "n_eval", "n_excluded_undefined",
                               "best_ep", "best_v", "sign", "direction", "positive", "negative")
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
    """S1 무효 규칙(값 무관) 발동. 메시지 = 규칙 이름 + 파일명뿐(값 0)."""

    def __init__(self, rule, where=""):
        self.rule = rule
        super().__init__("[무효] %s :: %s" % (rule, where))


class HarnessAbort(Exception):
    """게이트·구조 결함(값 무관)."""


RULE_SHA = "입력 sha 불일치"
RULE_ORDER = "행 순서/cid_order 불일치"
RULE_NONFINITE = "비유한 값"
RULE_MISSING = "OOF 결손"
RULE_COUNT = "셀 수 불일치"


def _verify_then_import():
    """F5 sha 를 파일로 검증한 뒤 sap·compute_lock 을 import 한다."""
    for rel, sha in SAP_MODULES.items():
        if sha256_file(_abs(rel)) != sha:
            raise HarnessAbort("SAP 모듈 sha 불일치: " + rel)
    if sha256_file(_abs(COMPUTE_LOCK[0])) != COMPUTE_LOCK[1]:
        raise HarnessAbort("compute_lock sha 불일치")


_verify_then_import()
from sap.consensus import build_consensus          # noqa: E402
from sap.metrics import macro_ap                   # noqa: E402
import compute_lock as cl                          # noqa: E402


def load_spec():
    b = _read_bytes(_abs(SPEC_PATH))
    if sha256_bytes(b) != SPEC_SHA256:
        raise HarnessAbort("명세 sha 불일치")
    return json.loads(b.decode("utf-8"))["S1_metrics_contract"]


def spec_terms(s1):
    """명세 S1 에서 모델·t·rep 쌍·s↔t·대비 arm·셀 수를 읽는다(재기술 0)."""
    g = s1["inputs"]["gin_oof"]
    models = list(g["models"])
    t_values = [int(t) for t in g["t_values"]]
    reps = [(int(r), int(s)) for r, s in g["rep_seed_pairs"].items()]
    s_to_t = {int(k): int(v) for k, v in s1["notation_freeze"]["s_is_order_index"].items()}
    cells = s1["cells_frozen_here_no_additions_later"]
    m = re.match(r"\s*(\S+)\s*−\s*(\S+)", cells["delta_direction"])
    hi, lo = m.group(1), m.group(2)
    counts = {"cell_1": cells["cell_1_seed_consensus_macro_ap"]["count"],
              "cell_2": cells["cell_2_delta_gin_per_seed"]["count"],
              "cell_3": cells["cell_3_delta_gin"]["count"],
              "cell_4": cells["cell_4_auxiliary_sealed_per_repeat"]["count"]}
    assert hi in models and lo in models
    assert [s_to_t[k] for k in sorted(s_to_t)] == t_values
    assert s1["notation_freeze"]["confirmatory_t_domain"] == t_values
    return {"models": models, "t_values": t_values, "reps": reps, "s_to_t": s_to_t,
            "arm_hi": hi, "arm_lo": lo, "contrast": "%s − %s" % (hi, lo), "counts": counts,
            "n_training_meta": len(models) * N_FOLD * len(t_values) * len(reps),
            "oof_pattern": g["pattern"], "outputs": s1["outputs"],
            "aggregation": s1["aggregation"]}


def _ap(y, P, eligible):
    """S1 macro_ap_rules — eligible_pt 명시 호출 + 열 수 assert."""
    assert P.shape[1] == N_PT, "열 수 불일치"
    return macro_ap(y, P, eligible)


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


def _atomic_npz(path, **arrays):
    """AT atomic_npz 패턴 — 파일 핸들에 쓰므로 numpy 가 .npz 를 덧붙이지 않는다."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        np.savez_compressed(f, **arrays)
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


def _assert_no_key_substr(obj, words, what):
    bad = sorted({k for k in _keys_recursive(obj) for w in words if w in k})
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


def _pycache_dirs(root):
    return sum(1 for dp, _dn, _fn in os.walk(root)
               if ".git" not in dp.split(os.sep) and os.path.basename(dp) == "__pycache__")


# ═══════════════════════════════════════════════════════════════════════════
# core — R1~R7 (모든 경로를 인자로 받는다)
# ═══════════════════════════════════════════════════════════════════════════
def core(paths, fault=None):
    """paths = {root, out_dir, manifest_t4, manifest_t4_sha256, master_x, master_y, master_sha{x,y},
               rep_dirs{r: sealed_dir}, n_rows_expected, spec(S1 dict), public_meta{}}."""
    t_start = time.perf_counter()
    T = spec_terms(paths["spec"])
    models, t_values, reps = T["models"], T["t_values"], T["reps"]
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

    # ── R1 라벨 ──
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
    Ym = Y[ycols].values.astype(int)
    cid_order = np.asarray(cid_list, dtype=np.int64)
    n_rows = int(paths["n_rows_expected"])
    if Ym.shape != (n_rows, N_PT):
        raise InvalidRun(RULE_ORDER, "라벨 shape")
    step("R1", "labels loaded · rows %d · PT %d" % Ym.shape)

    # ── manifest ──
    bm = _read_bytes(paths["manifest_t4"])
    if sha256_bytes(bm) != paths["manifest_t4_sha256"]:
        raise InvalidRun(RULE_SHA, "manifest_t4")
    MT = json.loads(bm.decode("utf-8"))
    exp_oof_keys = {"rep%d_seed%d/oof_%s_seed%d.npz" % (r, s, m, t)
                    for r, s in reps for m in models for t in t_values}
    if set(MT["oof_sha256"]) != exp_oof_keys:
        raise InvalidRun(RULE_SHA, "manifest_t4 oof_sha256 키 집합")
    if set(MT["checkpoint_sha256"]) != {"rep%d_seed%d" % (r, s) for r, s in reps}:
        raise InvalidRun(RULE_SHA, "manifest_t4 checkpoint_sha256 키 집합")

    # ── R2 판독 기록(먼저 쓴다 · rep 당 1줄) ──
    for r, s in reps:
        _append_line(os.path.join(paths["rep_dirs"][r], "access.log"), {
            "ts_kst": now_kst(), "type": "machine_read", "purpose": "consensus+metrics input",
            "human_exposure": False,
            "path": "_sealed/{checkpoint.jsonl,oof_*_seed*.npz,_partial/*.npz}",
            "actor": "vscode-claude", "step": "블록 AW(docs/113) R3 입력 판독",
            "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."})
    step("R2", "access.log +1 line per repeat · %d repeats" % len(reps))

    try:
        return _core_after_r2(paths, fault, T, Ym, cid_order, n_rows, MT, counts_start,
                              sealed_out, out_dir, log, step, t_start)
    except (InvalidRun, HarnessAbort):
        raise
    except Exception as e:           # 값 누설 방지 — 예외 메시지를 버리고 형식만 남긴다
        raise HarnessAbort("R2 이후 예외(메시지 비공개): " + type(e).__name__) from None


def _core_after_r2(paths, fault, T, Ym, cid_order, n_rows, MT, counts_start,
                   sealed_out, out_dir, log, step, t_start):
    models, t_values, reps = T["models"], T["t_values"], T["reps"]
    pt_index_exp = np.arange(N_PT)
    OOF = {}
    meta = {}
    n_oof_ok = n_part_ok = n_ckpt_ok = 0

    # ── R3 입력 판독·검증 ──
    for r, s in reps:
        sdir = paths["rep_dirs"][r]
        repkey = "rep%d_seed%d" % (r, s)
        # 3-1 checkpoint
        cpath = os.path.join(sdir, "checkpoint.jsonl")
        if not os.path.exists(cpath):
            raise InvalidRun(RULE_MISSING, repkey + "/checkpoint.jsonl")
        cb = _read_bytes(cpath)
        if sha256_bytes(cb) != MT["checkpoint_sha256"][repkey]:
            raise InvalidRun(RULE_SHA, repkey + "/checkpoint.jsonl")
        if not cb.endswith(b"\n"):
            raise InvalidRun(RULE_MISSING, repkey + "/checkpoint.jsonl 말미 개행")
        rows = [json.loads(x) for x in cb.decode("utf-8").splitlines()]
        exp_units = {(m, k, t) for m in models for k in range(N_FOLD) for t in t_values}
        if len(rows) != len(exp_units) or any(sorted(x.keys()) != sorted(CKPT_FIELDS) for x in rows):
            raise InvalidRun(RULE_MISSING, repkey + "/checkpoint.jsonl 행·필드")
        ck = {}
        for x in rows:
            key = (x["model"], int(x["fold"]), int(x["train_seed"]))
            if key in ck or int(x["rep"]) != r:
                raise InvalidRun(RULE_MISSING, repkey + "/checkpoint.jsonl 키 중복·rep")
            ck[key] = x
        if set(ck) != exp_units:
            raise InvalidRun(RULE_MISSING, repkey + "/checkpoint.jsonl 단위 집합")
        n_ckpt_ok += 1
        # 3-2 partial (fold 는 파일명에서만)
        pdir = os.path.join(sdir, "_partial")
        names = sorted(n for n in os.listdir(pdir) if n.endswith(".npz")) if os.path.isdir(pdir) else []
        parsed = {}
        for n in names:
            mm = re.fullmatch(r"(.+)_fold(\d+)_seed(\d+)\.npz", n)
            if mm is None:
                raise InvalidRun(RULE_MISSING, repkey + "/_partial 파일명 형식")
            parsed[(mm.group(1), int(mm.group(2)), int(mm.group(3)))] = n
        if set(parsed) != exp_units:
            raise InvalidRun(RULE_MISSING, repkey + "/_partial 단위 집합")
        rowsum = {(m, t): 0 for m in models for t in t_values}
        for (m, k, t), n in sorted(parsed.items()):
            pb = _read_bytes(os.path.join(pdir, n))
            if sha256_bytes(pb) != ck[(m, k, t)]["artifact_sha256"]:
                raise InvalidRun(RULE_SHA, repkey + "/_partial/" + n)
            with np.load(io.BytesIO(pb)) as z:
                if set(z.files) != PARTIAL_KEYS:
                    raise InvalidRun(RULE_SHA, repkey + "/_partial/" + n + " 키 집합")
                be, bv, Pt = z["best_ep"], z["best_v"], z["P_test"]
                if be.ndim != 0 or not np.issubdtype(be.dtype, np.integer):
                    raise InvalidRun(RULE_SHA, repkey + "/_partial/" + n + " best_ep 형식")
                if bv.ndim != 0 or not np.isfinite(bv):
                    raise InvalidRun(RULE_NONFINITE, repkey + "/_partial/" + n + " best_v")
                if Pt.ndim != 2 or Pt.shape[1] != N_PT:
                    raise InvalidRun(RULE_ORDER, repkey + "/_partial/" + n + " P_test 형식")
                rowsum[(m, t)] += int(Pt.shape[0])
                meta["rep%d|%s|fold%d|seed%d" % (r, m, k, t)] = {"best_ep": int(be), "best_v": float(bv)}
                del Pt
            n_part_ok += 1
        if any(v != n_rows for v in rowsum.values()):
            raise InvalidRun(RULE_ORDER, repkey + "/_partial 행 수 합")
        # 3-3 OOF
        for m in models:
            for t in t_values:
                fname = "oof_%s_seed%d.npz" % (m, t)
                okey = "%s/%s" % (repkey, fname)
                fpath = os.path.join(sdir, fname)
                if not os.path.exists(fpath):
                    raise InvalidRun(RULE_MISSING, okey)
                ob = _read_bytes(fpath)
                if sha256_bytes(ob) != MT["oof_sha256"][okey]:
                    raise InvalidRun(RULE_SHA, okey)
                with np.load(io.BytesIO(ob)) as z:
                    if set(z.files) != OOF_KEYS:
                        raise InvalidRun(RULE_SHA, okey + " 키 집합")
                    P, yy, pti, co = z["P"], z["y"], z["pt_index"], z["cid_order"]
                if P.shape != (n_rows, N_PT) or P.dtype != np.float32:
                    raise InvalidRun(RULE_ORDER, okey + " P 형식")
                if not bool(np.isfinite(P).all()):
                    raise InvalidRun(RULE_NONFINITE, okey + " P")
                if yy.dtype != np.int8 or not np.array_equal(yy, Ym):
                    raise InvalidRun(RULE_ORDER, okey + " y ≠ master_Y")
                if not np.array_equal(pti, pt_index_exp):
                    raise InvalidRun(RULE_ORDER, okey + " pt_index")
                if co.dtype != np.int64 or not np.array_equal(co, cid_order):
                    raise InvalidRun(RULE_ORDER, okey + " cid_order")
                OOF[(r, m, t)] = P
                n_oof_ok += 1
    step("R3", "inputs verified · checkpoint %d · partial %d · oof %d" % (n_ckpt_ok, n_part_ok, n_oof_ok))

    # ── R4 셀 계산 ──
    eligible = np.arange(N_PT)
    cell_4 = {}
    for r, _s in reps:
        for m in models:
            for t in t_values:
                a = _ap(Ym, OOF[(r, m, t)], eligible)
                cell_4["rep%d|%s|seed%d" % (r, m, t)] = {
                    "macro_ap": a["macro_ap"], "n_eval": a["n_eval"],
                    "n_excluded_undefined": a["n_excluded_undefined"], "n_eligible": a["n_eligible"]}
    CONS = {}
    cell_1 = {}
    for m in models:
        for t in t_values:
            C = build_consensus([OOF[(r, m, t)] for r, _s in reps])      # rep 순서 1,2,3 고정
            CONS[(m, t)] = C
            a = _ap(Ym, C, eligible)
            cell_1["%s|seed%d" % (m, t)] = {
                "macro_ap": a["macro_ap"], "n_eval": a["n_eval"],
                "n_excluded_undefined": a["n_excluded_undefined"], "n_eligible": a["n_eligible"]}
    cell_2 = {}
    dl = []
    for sidx in sorted(T["s_to_t"]):
        t = T["s_to_t"][sidx]
        d = (cell_1["%s|seed%d" % (T["arm_hi"], t)]["macro_ap"]
             - cell_1["%s|seed%d" % (T["arm_lo"], t)]["macro_ap"])
        cell_2["s%d|seed%d" % (sidx, t)] = d
        dl.append(d)
    cell_3 = float(np.mean(dl))                  # metric-then-average: Δ 먼저, 평균은 나중
    step("R4", "cells computed · c1 %d · c2 %d · c3 1 · c4 %d · consensus %d"
         % (len(cell_1), len(cell_2), len(cell_4), len(CONS)))

    if fault == "drop_cell":                     # K8(e) 내부 fault-injection 전용
        cell_1.pop(sorted(cell_1)[0])

    # ── R5 무효 판정(값 무관) ──
    c = T["counts"]
    if (len(cell_1), len(cell_2), 1, len(cell_4)) != (c["cell_1"], c["cell_2"], c["cell_3"], c["cell_4"]) \
            or len(meta) != T["n_training_meta"] or len(CONS) != c["cell_1"]:
        raise InvalidRun(RULE_COUNT, "cells/training_meta")
    vals = [v["macro_ap"] for v in cell_1.values()] + [v["macro_ap"] for v in cell_4.values()] \
        + list(cell_2.values()) + [cell_3]
    if not all(np.isfinite(v) for v in vals):
        raise InvalidRun(RULE_NONFINITE, "macro_ap/Δ")
    if not all(np.isfinite(C).all() for C in CONS.values()):
        raise InvalidRun(RULE_NONFINITE, "consensus")
    step("R5", "invalidation rules: none triggered")

    # ── R6 봉인 쓰기 ──
    _mkdir_new(out_dir)
    _mkdir_new(sealed_out)
    new_access = {
        "ts_kst": now_kst(), "type": "machine_read",
        "purpose": "consensus+metrics build (first GIN confirmatory metrics)",
        "human_exposure": False, "path": "_sealed/", "actor": "vscode-claude",
        "step": "블록 AW(docs/113) R6",
        "delta_status": "value_sealed_in_metrics_full__sign_not_computed", "emit_calls": 0,
        "note": "Δ 값은 metrics_full.json 에만 봉인. 부호 미산출. 사람 열람 0."}
    _assert_no_key_substr(new_access, FORBIDDEN_KEY_SUBSTR_SEALED, "access.log")
    _append_line(os.path.join(out_dir, T["outputs"]["access_log"]), new_access)
    sealed_files = []
    for m in models:
        for t in t_values:
            rel = T["outputs"]["consensus_files"].format(model=m, t=t)
            _atomic_npz(os.path.join(out_dir, rel), consensus=CONS[(m, t)], cid=cid_order)
            sealed_files.append(rel)
    metrics = {
        "_doc": ("블록 AW (docs/113) — S1 셀 봉인 산출. 개봉 전 사람 열람 금지. "
                 "Δ 값은 여기에만 봉인되고 부호는 따로 산출하지 않았다(H2)."),
        "block": "AW (docs/113)", "provenance": paths.get("provenance", "confirmatory_sealed"),
        "spec_sha256": paths["public_meta"].get("spec_sha256", SPEC_SHA256),
        "manifest_t4_sha256": paths["manifest_t4_sha256"],
        "contrast_definition": T["contrast"],
        "eligible_pt": "np.arange(%d) explicit" % N_PT,
        "aggregation": T["aggregation"],
        "notation": {"t": "training seed value", "s_to_t": {str(k): v for k, v in T["s_to_t"].items()}},
        "cells": {"cell_1_seed_consensus_macro_ap": cell_1,
                  "cell_2_delta_gin_per_seed": cell_2,
                  "cell_3_delta_gin": cell_3,
                  "cell_4_auxiliary_sealed_per_repeat": cell_4},
        "training_meta_not_cells": meta,
        "input_sha256": {"oof": dict(sorted(MT["oof_sha256"].items())),
                         "checkpoint": dict(sorted(MT["checkpoint_sha256"].items())),
                         "master_X": paths["master_sha"]["x"], "master_Y": paths["master_sha"]["y"]},
        "counts": {"cell_1": len(cell_1), "cell_2": len(cell_2), "cell_3": 1, "cell_4": len(cell_4),
                   "training_meta": len(meta)},
    }
    _assert_no_key_substr(metrics, FORBIDDEN_KEY_SUBSTR_SEALED, "metrics_full")
    mrel = T["outputs"]["metrics"]
    _atomic_bytes(os.path.join(out_dir, mrel),
                  (json.dumps(metrics, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
    sealed_files.append(mrel)
    step("R6", "sealed written · %d files + access.log" % len(sealed_files))

    # ── R7 공개 산출 ──
    counts_end = sealed_counts(paths["root"])
    wall = round(time.perf_counter() - t_start, 3)
    listing = [{"name": rel, "bytes": os.path.getsize(os.path.join(out_dir, rel)),
                "sha256": sha256_file(os.path.join(out_dir, rel))} for rel in sealed_files]
    import sklearn
    pub = {
        "_doc": ("블록 AW (docs/113) 공개 manifest — 개수·환경·게이트 불리언·봉인 파일 이름/바이트/sha256 뿐. "
                 "지표 값·학습 메타 값은 기록하지 않는다."),
        "block": "AW (docs/113)", "provenance": paths.get("provenance", "confirmatory_sealed"),
        "n_cells_c1": len(cell_1), "n_cells_c2": len(cell_2), "n_cells_c3": 1, "n_cells_c4": len(cell_4),
        "n_training_meta": len(meta), "n_consensus_files": len(CONS),
        "sealed_files": listing,
        "input_checks": {
            "oof_sha_match": n_oof_ok, "checkpoint_sha_match": n_ckpt_ok,
            "partial_sha_equals_checkpoint_artifact": n_part_ok,
            "oof_sha_all_match": n_oof_ok == len(MT["oof_sha256"]),
            "checkpoint_sha_all_match": n_ckpt_ok == len(MT["checkpoint_sha256"]),
            "partial_sha_all_match": n_part_ok == T["n_training_meta"],
            "cid_order_match": True, "label_identity": True, "finite_inputs": True, "finite_outputs": True},
        "wall_seconds": wall,
        "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
        "pandas": pd.__version__,
        "harness_sha256": paths["public_meta"].get("harness_sha256"),
        "spec_sha256": paths["public_meta"].get("spec_sha256"),
        "selftest_sha256": paths["public_meta"].get("selftest_sha256"),
        "manifest_t4_sha256": paths["manifest_t4_sha256"],
        "values_disclosed": False, "unblinding_performed": False,
        "sealed_counts_start": counts_start, "sealed_counts_end": counts_end,
        "ts_completed_kst": now_kst(),
    }
    _assert_no_key_substr(pub, FORBIDDEN_KEY_SUBSTR_PUBLIC, "manifest_public")
    step("R7", "public manifest + run.log · wall_seconds %.3f" % wall)
    _atomic_bytes(os.path.join(out_dir, "manifest_public.json"),
                  (json.dumps(pub, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    _atomic_bytes(os.path.join(out_dir, "run.log"), ("\n".join(log) + "\n").encode("utf-8"))
    return pub


# ═══════════════════════════════════════════════════════════════════════════
# stage_run — R0 게이트 + compute_lock
# ═══════════════════════════════════════════════════════════════════════════
def _confirmatory_prefixes(T):
    base = T["oof_pattern"].split("/_sealed/")[0]
    return {r: base.format(r=r, s=s) for r, s in T["reps"]}


def stage_run():
    s1 = load_spec()
    T = spec_terms(s1)
    conf = _confirmatory_prefixes(T)
    out_rel = T["outputs"]["dir"].rstrip("/")
    if not fnmatch.fnmatch(out_rel, CONSENSUS_GLOB):
        raise HarnessAbort("명세 outputs.dir 이 consensus glob 과 불일치")
    # selftest 조건
    st_path = _abs(SELFTEST_OUT)
    if not os.path.exists(st_path):
        raise HarnessAbort("selftest 결과 부재")
    st = json.loads(_read_bytes(st_path).decode("utf-8"))
    me = sha256_file(os.path.abspath(__file__))
    if not (st.get("all_pass") is True and st.get("harness_sha256") == me):
        raise HarnessAbort("selftest 조건 불충족(all_pass·하네스 sha)")
    # R0 — P2
    if sealed_counts(ROOT) != EXPECTED_SEALED_BEFORE:
        raise HarnessAbort("봉인 계수 불일치(착수)")
    fpc = sealed_fingerprint(ROOT, list(conf.values()))[0]
    fps = sealed_fingerprint(ROOT, [STABILITY_PREFIX])[0]
    fpo = sealed_fingerprint(ROOT, list(conf.values()) + [STABILITY_PREFIX, out_rel], exclude=True)[0]
    if (fpc, fps, fpo) != (FP_CONFIRMATORY, FP_STABILITY, FP_EXISTING25):
        raise HarnessAbort("봉인 stat 지문 불일치")
    if glob.glob(_abs(CONSENSUS_GLOB)):
        raise HarnessAbort("consensus 디렉터리 선존재")
    # R0 — P6 (이름·개수만)
    if sha256_file(_abs(MANIFEST_T4)) != MANIFEST_T4_SHA256:
        raise HarnessAbort("manifest_t4 sha 불일치")
    for r, pre in conf.items():
        sd = _abs(pre + "/_sealed")
        n_oof = len([n for n in os.listdir(sd) if re.fullmatch(r"oof_.+_seed\d+\.npz", n)])
        n_par = len([n for n in os.listdir(os.path.join(sd, "_partial")) if n.endswith(".npz")])
        if (n_oof, n_par) != (len(T["models"]) * len(T["t_values"]),
                              len(T["models"]) * len(T["t_values"]) * N_FOLD):
            raise HarnessAbort("확증 rep 구성 불일치")
    # R0 — P7
    if (len(T["models"]), sum(T["counts"].values())) != (7, 88):
        raise HarnessAbort("명세 셀 수 결속 불일치")
    paths = {"root": ROOT, "out_dir": _abs(out_rel),
             "manifest_t4": _abs(MANIFEST_T4), "manifest_t4_sha256": MANIFEST_T4_SHA256,
             "master_x": _abs(MASTER_X[0]), "master_y": _abs(MASTER_Y[0]),
             "master_sha": {"x": MASTER_X[1], "y": MASTER_Y[1]},
             "rep_dirs": {r: _abs(pre + "/_sealed") for r, pre in conf.items()},
             "n_rows_expected": N_DRUGS, "spec": s1, "provenance": "confirmatory_sealed",
             "public_meta": {"harness_sha256": me, "spec_sha256": SPEC_SHA256,
                             "selftest_sha256": sha256_file(st_path)}}
    cl.gate_a_load("AW run entry")
    with cl.ComputeLock(script="confirmatory_gin_consensus.py", role="runner"):
        pub = core(paths, fault=None)
    end = sealed_counts(ROOT)
    fps2 = sealed_fingerprint(ROOT, [STABILITY_PREFIX])[0]
    fpo2 = sealed_fingerprint(ROOT, list(conf.values()) + [STABILITY_PREFIX, out_rel], exclude=True)[0]
    ok = (end == EXPECTED_SEALED_AFTER and fps2 == FP_STABILITY and fpo2 == FP_EXISTING25)
    print(json.dumps({"stage": "run", "sealed_counts_end_expected": end == EXPECTED_SEALED_AFTER,
                      "stability_fp_unchanged": fps2 == FP_STABILITY,
                      "existing25_fp_unchanged": fpo2 == FP_EXISTING25,
                      "n_consensus_files": pub["n_consensus_files"]}, ensure_ascii=False), flush=True)
    return 0 if ok else 3


# ═══════════════════════════════════════════════════════════════════════════
# 합성 자체검사 K1~K12 (확증 입력 판독 0)
# ═══════════════════════════════════════════════════════════════════════════
PROVENANCE_SYN = "synthetic_fixture"


def _make_fixture(tmp, s1, n=40, rng_seed=20260923, zero_cols=()):
    T = spec_terms(s1)
    rng = np.random.default_rng(rng_seed)
    os.makedirs(os.path.join(tmp, "data"))
    cids = np.sort(rng.choice(np.arange(1000, 100000), size=n, replace=False)).astype(np.int64)
    Y = (rng.random((n, N_PT)) < 0.3).astype(int)
    for j in range(N_PT):
        if Y[:, j].sum() == 0:
            Y[rng.integers(0, n), j] = 1
    for j in zero_cols:
        Y[:, j] = 0
    mx, my = os.path.join(tmp, "data", "master_X.parquet"), os.path.join(tmp, "data", "master_Y.parquet")
    pd.DataFrame({"cid": cids, "smiles": ["C"] * n}).to_parquet(mx)
    ydf = pd.DataFrame(Y, columns=["pt_%04d" % j for j in range(N_PT)])
    ydf.insert(0, "cid", cids)
    ydf.to_parquet(my)
    folds = rng.permutation(np.arange(n) % N_FOLD)
    rep_dirs, oof_sha, ck_sha, OOF = {}, {}, {}, {}
    for r, s in T["reps"]:
        sd = os.path.join(tmp, "runs", "fx_rep%d_seed%d" % (r, s), "_sealed")
        os.makedirs(os.path.join(sd, "_partial"))
        with open(os.path.join(sd, "access.log"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "machine_read", "actor": "fixture"}) + "\n")
        lines = []
        for m in T["models"]:
            for t in T["t_values"]:
                P = rng.random((n, N_PT)).astype(np.float32)
                OOF[(r, m, t)] = P
                fp = os.path.join(sd, "oof_%s_seed%d.npz" % (m, t))
                with open(fp, "wb") as f:
                    np.savez(f, P=P, y=Y.astype(np.int8), pt_index=np.arange(N_PT, dtype=np.int32),
                             cid_order=cids)
                oof_sha["rep%d_seed%d/oof_%s_seed%d.npz" % (r, s, m, t)] = sha256_file(fp)
                for k in range(N_FOLD):
                    pp = os.path.join(sd, "_partial", "%s_fold%d_seed%d.npz" % (m, k, t))
                    with open(pp, "wb") as f:
                        np.savez(f, P_test=P[folds == k], best_ep=np.int32(rng.integers(3, 60)),
                                 best_v=np.float64(rng.random()))
                    lines.append(json.dumps({"rep": r, "fold": k, "model": m, "train_seed": t,
                                             "completed_at_kst": "fixture", "artifact_sha256": sha256_file(pp),
                                             "n_epochs": 10, "wall_seconds": 1.0}))
        cp = os.path.join(sd, "checkpoint.jsonl")
        with open(cp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ck_sha["rep%d_seed%d" % (r, s)] = sha256_file(cp)
        rep_dirs[r] = sd
    mt = os.path.join(tmp, "manifest_t4.json")
    with open(mt, "w", encoding="utf-8") as f:
        f.write(json.dumps({"oof_sha256": oof_sha, "checkpoint_sha256": ck_sha}, indent=2))
    paths = {"root": tmp, "out_dir": os.path.join(tmp, "runs", "fx_consensus"),
             "manifest_t4": mt, "manifest_t4_sha256": sha256_file(mt),
             "master_x": mx, "master_y": my, "master_sha": {"x": sha256_file(mx), "y": sha256_file(my)},
             "rep_dirs": rep_dirs, "n_rows_expected": n, "spec": s1, "provenance": PROVENANCE_SYN,
             "public_meta": {"harness_sha256": "fixture", "spec_sha256": SPEC_SHA256,
                             "selftest_sha256": "fixture"}}
    return paths, {"Y": Y, "OOF": OOF, "T": T}


def _refresh_manifest_oof(paths, okey, fpath):
    MT = json.loads(_read_bytes(paths["manifest_t4"]).decode("utf-8"))
    MT["oof_sha256"][okey] = sha256_file(fpath)
    with open(paths["manifest_t4"], "w", encoding="utf-8") as f:
        f.write(json.dumps(MT, indent=2))
    paths["manifest_t4_sha256"] = sha256_file(paths["manifest_t4"])


def _rewrite_oof(path, **over):
    with np.load(path) as z:
        d = {k: z[k] for k in z.files}
    d.update(over)
    with open(path, "wb") as f:
        np.savez(f, **d)


def _run_quiet(paths, fault=None):
    buf = io.StringIO()
    exc = None
    with contextlib.redirect_stdout(buf):
        try:
            core(paths, fault=fault)
        except Exception as e:           # noqa: BLE001 — 시험 대상
            exc = e
    return buf.getvalue(), exc


def _load_fx_metrics(paths):
    return json.loads(_read_bytes(os.path.join(paths["out_dir"], "_sealed", "metrics_full.json")).decode("utf-8"))


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


def selftest_K1_constants():
    checks = {"spec": sha256_file(_abs(SPEC_PATH)) == SPEC_SHA256,
              "manifest_t4": sha256_file(_abs(MANIFEST_T4)) == MANIFEST_T4_SHA256,
              "compute_lock": sha256_file(_abs(COMPUTE_LOCK[0])) == COMPUTE_LOCK[1]}
    for rel, sha in SAP_MODULES.items():
        checks["sap:" + os.path.basename(rel)] = sha256_file(_abs(rel)) == sha
    return _res("K1 상수·해시", checks)


def selftest_K2_spec_binding(s1):
    T = spec_terms(s1)
    g = s1["inputs"]["gin_oof"]
    tree = _src_tree()
    model_lits = [n.value for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in set(g["models"])]
    checks = {"models_from_spec": T["models"] == g["models"] and len(T["models"]) == 7,
              "t_values_from_spec": T["t_values"] == g["t_values"],
              "rep_pairs_from_spec": {str(r): s for r, s in T["reps"]} == g["rep_seed_pairs"],
              "outputs_from_spec": T["outputs"] == s1["outputs"],
              "cell_counts_from_spec": [T["counts"][k] for k in ("cell_1", "cell_2", "cell_3", "cell_4")]
                                       == [21, 3, 1, 63],
              "contrast_from_spec": T["contrast"] + " 고정"
                                    == s1["cells_frozen_here_no_additions_later"]["delta_direction"],
              "no_model_name_literals_in_source": not model_lits}
    return _res("K2 S1 결속", checks, model_name_literals=model_lits)


def selftest_K3_consensus(paths, fx):
    T = fx["T"]
    worst_bc = worst_mean = 0.0
    for m in T["models"]:
        for t in T["t_values"]:
            with np.load(os.path.join(paths["out_dir"], "_sealed", "consensus_%s_seed%d.npz" % (m, t))) as z:
                C = z["consensus"]
                cid = z["cid"]
            reps = [fx["OOF"][(r, m, t)] for r, _s in T["reps"]]
            bc = build_consensus(reps)
            am = np.mean(np.stack([a.astype(np.float64) for a in reps], axis=0), axis=0)
            worst_bc = max(worst_bc, float(np.max(np.abs(C - bc))))
            worst_mean = max(worst_mean, float(np.max(np.abs(C - am))))
    tree = _src_tree()
    par = _parents(tree)
    bc_calls = [_enclosing(par, n) for n in ast.walk(tree)
                if isinstance(n, ast.Call) and _call_name(n) == "build_consensus"]
    imported = any(isinstance(n, ast.ImportFrom) and n.module == "sap.consensus"
                   and any(a.name == "build_consensus" for a in n.names) for n in ast.walk(tree))
    # 자체 평균 구현 0 — 비-selftest 함수의 mean/stack/sum 호출은 cell_3 의 리스트 평균 1건뿐
    agg = [(n, _enclosing(par, n)) for n in ast.walk(tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr in ("mean", "stack", "sum", "average", "nanmean")]
    outside = [(n, fn) for n, fn in agg if not (fn or "").startswith("selftest")
               and fn not in ("_make_fixture",)]
    ok_outside = (len(outside) == 1 and _call_name(outside[0][0]) == "mean"
                  and isinstance(outside[0][0].args[0], ast.Name)
                  and not any(k.arg == "axis" for k in outside[0][0].keywords))
    return _res("K3 consensus", {"equals_build_consensus_exact": worst_bc == 0.0,
                                 "equals_arith_mean_exact": worst_mean == 0.0,
                                 "cid_saved": bool(np.array_equal(cid, np.asarray(
                                     pd.read_parquet(paths["master_x"])["cid"], dtype=np.int64))),
                                 "build_consensus_imported": imported,
                                 "build_consensus_called_in_core": "_core_after_r2" in bc_calls,
                                 "no_self_mean_outside_selftest": ok_outside},
                max_abs_diff_vs_build_consensus=worst_bc, max_abs_diff_vs_mean=worst_mean,
                provenance=PROVENANCE_SYN)


def selftest_K4_repeat_axis(paths, fx):
    T = fx["T"]
    M = _load_fx_metrics(paths)
    c1, c4 = M["cells"]["cell_1_seed_consensus_macro_ap"], M["cells"]["cell_4_auxiliary_sealed_per_repeat"]
    elig = np.arange(N_PT)
    eq, distinct = [], []
    for m in T["models"]:
        for t in T["t_values"]:
            reps = [fx["OOF"][(r, m, t)] for r, _s in T["reps"]]
            ref = macro_ap(fx["Y"], build_consensus(reps), elig)["macro_ap"]
            eq.append(c1["%s|seed%d" % (m, t)]["macro_ap"] == ref)
            mean_rep = float(np.mean([c4["rep%d|%s|seed%d" % (r, m, t)]["macro_ap"] for r, _s in T["reps"]]))
            distinct.append(abs(c1["%s|seed%d" % (m, t)]["macro_ap"] - mean_rep) > 1e-6)
    return _res("K4 repeat 축 prediction-then-metric",
                {"cell_1_equals_ap_of_consensus": all(eq), "distinct_from_mean_of_repeat_aps": all(distinct)},
                provenance=PROVENANCE_SYN)


def selftest_K5_seed_axis(paths, fx):
    from sap.rqint import build_eight_consensus, observed_statistic
    T = fx["T"]
    M = _load_fx_metrics(paths)
    rng = np.random.default_rng(7)
    n = fx["Y"].shape[0]
    arms = (T["arm_lo"], T["arm_hi"])
    P_RF = {a: [rng.random((n, N_PT)) for _ in T["reps"]] for a in arms}
    P_GIN = {a: {sidx: [fx["OOF"][(r, a, T["s_to_t"][sidx])] for r, _s in T["reps"]]
                 for sidx in T["s_to_t"]} for a in arms}
    mats, seeds = build_eight_consensus(P_RF, P_GIN)
    elig = np.arange(N_PT)
    _t, _drf, d_gin, d_gin_s = observed_statistic(mats, seeds, fx["Y"], elig)
    c2 = M["cells"]["cell_2_delta_gin_per_seed"]
    ours = [c2["s%d|seed%d" % (sidx, T["s_to_t"][sidx])] for sidx in seeds]
    diff_s = max(abs(a - b) for a, b in zip(ours, d_gin_s))
    diff_3 = abs(M["cells"]["cell_3_delta_gin"] - d_gin)
    avg = {a: np.mean(np.stack([mats[("GIN", sidx, a)] for sidx in seeds]), axis=0) for a in arms}
    alt = macro_ap(fx["Y"], avg[T["arm_hi"]], elig)["macro_ap"] - macro_ap(fx["Y"], avg[T["arm_lo"]], elig)["macro_ap"]
    return _res("K5 seed 축 metric-then-average",
                {"seed_keys_are_s_index": list(seeds) == sorted(T["s_to_t"]),
                 "cell_2_matches_observed_statistic": diff_s <= 1e-12,
                 "cell_3_matches_observed_statistic": diff_3 <= 1e-12,
                 "distinct_from_matrix_preaverage": abs(M["cells"]["cell_3_delta_gin"] - alt) > 1e-6},
                max_diff_cell2=diff_s, max_diff_cell3=diff_3, provenance=PROVENANCE_SYN)


def selftest_K6_eligible_explicit():
    tree = _src_tree()
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "macro_ap"]
    bad = []
    for n in calls:
        third = n.args[2] if len(n.args) >= 3 else next((k.value for k in n.keywords if k.arg == "eligible_pt"), None)
        if third is None or (isinstance(third, ast.Constant) and third.value is None):
            bad.append(n.lineno)
    raised = False
    try:
        _ap(np.zeros((4, N_PT + 1), dtype=int), np.zeros((4, N_PT + 1)), np.arange(N_PT))
    except AssertionError:
        raised = True
    return _res("K6 eligible_pt 명시", {"all_macro_ap_calls_have_eligible": bool(calls) and not bad,
                                        "runtime_shape_assert_fires": raised}, n_macro_ap_calls=len(calls))


def selftest_K7_undefined(tmp, s1):
    from sklearn.metrics import average_precision_score
    paths, fx = _make_fixture(tmp, s1, rng_seed=77, zero_cols=(0, 1))
    out, exc = _run_quiet(paths)
    if exc is not None:
        return _res("K7 undefined", {"run_ok": False}, error=type(exc).__name__)
    M = _load_fx_metrics(paths)
    cells = list(M["cells"]["cell_1_seed_consensus_macro_ap"].values()) + \
        list(M["cells"]["cell_4_auxiliary_sealed_per_repeat"].values())
    T = fx["T"]
    m0, t0 = T["models"][0], T["t_values"][0]
    C = build_consensus([fx["OOF"][(r, m0, t0)] for r, _s in T["reps"]])
    aps = [average_precision_score(fx["Y"][:, j], C[:, j]) for j in range(2, N_PT)]
    got = M["cells"]["cell_1_seed_consensus_macro_ap"]["%s|seed%d" % (m0, t0)]["macro_ap"]
    return _res("K7 undefined", {"run_ok": True,
                                 "n_eval_368_all": all(c["n_eval"] == N_PT - 2 for c in cells),
                                 "n_excluded_2_all": all(c["n_excluded_undefined"] == 2 for c in cells),
                                 "variable_denominator": abs(got - float(np.mean(aps))) <= 1e-15,
                                 "no_zero_substitution": abs(got - float(np.sum(aps)) / N_PT) > 1e-9},
                provenance=PROVENANCE_SYN)


def _no_numeric_values(s):
    return re.search(r"\d\.\d", s) is None and "nan" not in s.lower() and "inf" not in s.lower()


def selftest_K8_invalid(tmp_root, s1):
    results, msgs = {}, []
    cases = ("a_sha_tamper", "b_cid_shuffle", "c_nan", "d_missing", "e_drop_cell")
    expect = {"a_sha_tamper": RULE_SHA, "b_cid_shuffle": RULE_ORDER, "c_nan": RULE_NONFINITE,
              "d_missing": RULE_MISSING, "e_drop_cell": RULE_COUNT}
    for i, case in enumerate(cases):
        tmp = os.path.join(tmp_root, "k8_" + case)
        os.makedirs(tmp)
        paths, fx = _make_fixture(tmp, s1, rng_seed=800 + i)
        T = fx["T"]
        r, s = T["reps"][1]
        m, t = T["models"][2], T["t_values"][1]
        okey = "rep%d_seed%d/oof_%s_seed%d.npz" % (r, s, m, t)
        fpath = os.path.join(paths["rep_dirs"][r], "oof_%s_seed%d.npz" % (m, t))
        fault = None
        if case == "a_sha_tamper":
            _rewrite_oof(fpath, P=(fx["OOF"][(r, m, t)] * np.float32(0.5)))
        elif case == "b_cid_shuffle":
            with np.load(fpath) as z:
                co = z["cid_order"].copy()
            _rewrite_oof(fpath, cid_order=co[::-1].copy())
            _refresh_manifest_oof(paths, okey, fpath)
        elif case == "c_nan":
            P = fx["OOF"][(r, m, t)].copy()
            P[3, 5] = np.nan
            _rewrite_oof(fpath, P=P)
            _refresh_manifest_oof(paths, okey, fpath)
        elif case == "d_missing":
            os.remove(fpath)
        else:
            fault = "drop_cell"
        _out, exc = _run_quiet(paths, fault=fault)
        msg = str(exc) if exc is not None else ""
        msgs.append(msg)
        results[case] = (isinstance(exc, InvalidRun) and exc.rule == expect[case]
                         and not os.path.exists(paths["out_dir"]) and _no_numeric_values(msg))
    return _res("K8 무효 5종", results), msgs


def selftest_K9_partial(tmp_root, s1):
    res, msgs = {}, []
    # (a) partial sha ≠ checkpoint artifact_sha256
    tmp = os.path.join(tmp_root, "k9_sha")
    os.makedirs(tmp)
    paths, fx = _make_fixture(tmp, s1, rng_seed=901)
    T = fx["T"]
    r = T["reps"][0][0]
    pp = os.path.join(paths["rep_dirs"][r], "_partial", "%s_fold1_seed%d.npz" % (T["models"][0], T["t_values"][0]))
    _rewrite_oof(pp, best_ep=np.int32(99))
    _o, exc = _run_quiet(paths)
    msgs.append(str(exc))
    res["sha_mismatch_aborts"] = (isinstance(exc, InvalidRun) and exc.rule == RULE_SHA
                                  and not os.path.exists(paths["out_dir"]))
    # (b) 키 집합 불일치 (sha 는 checkpoint·manifest 에 맞춰 갱신)
    tmp = os.path.join(tmp_root, "k9_keys")
    os.makedirs(tmp)
    paths, fx = _make_fixture(tmp, s1, rng_seed=902)
    T = fx["T"]
    r, s = T["reps"][0]
    sd = paths["rep_dirs"][r]
    m, t = T["models"][0], T["t_values"][0]
    pp = os.path.join(sd, "_partial", "%s_fold1_seed%d.npz" % (m, t))
    _rewrite_oof(pp, extra=np.int32(1))
    cp = os.path.join(sd, "checkpoint.jsonl")
    rows = [json.loads(x) for x in _read_bytes(cp).decode("utf-8").splitlines()]
    for x in rows:
        if (x["model"], x["fold"], x["train_seed"]) == (m, 1, t):
            x["artifact_sha256"] = sha256_file(pp)
    with open(cp, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(x) for x in rows) + "\n")
    MT = json.loads(_read_bytes(paths["manifest_t4"]).decode("utf-8"))
    MT["checkpoint_sha256"]["rep%d_seed%d" % (r, s)] = sha256_file(cp)
    with open(paths["manifest_t4"], "w", encoding="utf-8") as f:
        f.write(json.dumps(MT, indent=2))
    paths["manifest_t4_sha256"] = sha256_file(paths["manifest_t4"])
    _o, exc = _run_quiet(paths)
    msgs.append(str(exc))
    res["key_mismatch_aborts"] = (isinstance(exc, InvalidRun) and "키 집합" in str(exc)
                                  and not os.path.exists(paths["out_dir"]))
    res["messages_value_free"] = all(_no_numeric_values(x) for x in msgs)
    return _res("K9 partial 대조", res), msgs


def selftest_K10_atomic(tmp_root, s1, base_paths, base_counts_before, base_counts_after):
    tmp = os.path.join(tmp_root, "k10_pre")
    os.makedirs(tmp)
    paths, _fx = _make_fixture(tmp, s1, rng_seed=1001)
    os.makedirs(os.path.join(paths["out_dir"], "_sealed"))
    acc_before = {r: _read_bytes(os.path.join(d, "access.log")).count(b"\n") for r, d in paths["rep_dirs"].items()}
    _o, exc = _run_quiet(paths)
    acc_after = {r: _read_bytes(os.path.join(d, "access.log")).count(b"\n") for r, d in paths["rep_dirs"].items()}
    tmp_left = [p for p in glob.glob(os.path.join(base_paths["out_dir"], "**", "*"), recursive=True)
                if p.endswith(".tmp") or ".tmp." in os.path.basename(p)]
    new_acc = _read_bytes(os.path.join(base_paths["out_dir"], "_sealed", "access.log")).count(b"\n")
    sealed_names = sorted(os.listdir(os.path.join(base_paths["out_dir"], "_sealed")))
    return _res("K10 덮어쓰기 금지·원자성", {
        "preexisting_output_aborts": isinstance(exc, HarnessAbort),
        "preexisting_abort_before_r2": acc_before == acc_after,
        "no_tmp_left": not tmp_left,
        "rep_access_log_plus_one": all(base_counts_after[r] == base_counts_before[r] + 1 for r in base_counts_before),
        "new_access_log_one_line": new_acc == 1,
        "sealed_file_count_23": len(sealed_names) == 23})


def selftest_K11_leak(base_paths, base_stdout, exc_msgs):
    M = _load_fx_metrics(base_paths)
    vals = [v["macro_ap"] for v in M["cells"]["cell_1_seed_consensus_macro_ap"].values()] + \
        [v["macro_ap"] for v in M["cells"]["cell_4_auxiliary_sealed_per_repeat"].values()] + \
        list(M["cells"]["cell_2_delta_gin_per_seed"].values()) + [M["cells"]["cell_3_delta_gin"]] + \
        [v["best_v"] for v in M["training_meta_not_cells"].values()]
    pats = set()
    for v in vals:
        pats |= {repr(v), "%.4f" % v, "%.6f" % v, "%.4f" % abs(v), "%.6f" % abs(v)}
    pub_txt = _read_bytes(os.path.join(base_paths["out_dir"], "manifest_public.json")).decode("utf-8")
    runlog = _read_bytes(os.path.join(base_paths["out_dir"], "run.log")).decode("utf-8")
    texts = {"stdout": base_stdout, "run.log": runlog, "manifest_public": pub_txt, "exceptions": "\n".join(exc_msgs)}
    hits = {k: sorted(p for p in pats if p in txt) for k, txt in texts.items()}
    pub = json.loads(pub_txt)
    pub_bad = sorted({k for k in _keys_recursive(pub) for w in FORBIDDEN_KEY_SUBSTR_PUBLIC if w in k})
    new_objs = [M, pub, json.loads(_read_bytes(os.path.join(base_paths["out_dir"], "_sealed", "access.log")))]
    for d in base_paths["rep_dirs"].values():
        new_objs.append(json.loads(_read_bytes(os.path.join(d, "access.log")).decode("utf-8").splitlines()[-1]))
    with np.load(os.path.join(base_paths["out_dir"], "_sealed", sorted(
            n for n in os.listdir(os.path.join(base_paths["out_dir"], "_sealed")) if n.endswith(".npz"))[0])) as z:
        new_objs.append({k: 0 for k in z.files})
    sealed_bad = sorted({k for o in new_objs for k in _keys_recursive(o)
                         for w in FORBIDDEN_KEY_SUBSTR_SEALED if w in k})
    return _res("K11 누설 가드", {"value_strings_absent": not any(hits.values()),
                                  "public_json_keys_clean": not pub_bad,
                                  "new_file_keys_no_sign_words": not sealed_bad},
                n_patterns=len(pats), hits={k: len(v) for k, v in hits.items()},
                public_bad_keys=pub_bad, sealed_bad_keys=sealed_bad)


def selftest_K12_ast_hygiene(guard_violations, cl_calls, before):
    tree = _src_tree()
    par = _parents(tree)
    forbidden = ("emit_sign", "open_sealed", "rqint_test", "rq2_decision", "rq3_decision", "rq4_decision",
                 "holm", "paired_scaffold_bootstrap", "sign")
    hits = [(_call_name(n), n.lineno) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and _call_name(n) in forbidden]
    only_selftest = [(_call_name(n), _enclosing(par, n)) for n in ast.walk(tree)
                     if isinstance(n, ast.Call) and _call_name(n) in ("observed_statistic", "build_eight_consensus")]
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
    # 쓰기 원시 호출의 위치 — 헬퍼·fixture·selftest·main 에만
    write_fns = {"_append_line", "_atomic_bytes", "_atomic_npz", "_mkdir_new"}
    prim = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        nm = _call_name(n)
        is_w = nm in ("savez", "savez_compressed", "replace", "makedirs", "mkdir", "remove")
        if nm == "open" and len(n.args) > 1 and isinstance(n.args[1], ast.Constant) \
                and any(c in str(n.args[1].value) for c in "wax+"):
            is_w = True
        if is_w:
            prim.append(_enclosing(par, n))
    allowed_w = write_fns | {"main", "_make_fixture", "_refresh_manifest_oof", "_rewrite_oof"}
    bad_w = sorted({fn for fn in prim if fn not in allowed_w and not (fn or "").startswith("selftest")
                    and fn != "run_selftest"})
    # stage_run 정적 쓰기 대상 — 직접 쓰기 0 · core 호출의 out_dir = 명세 outputs.dir · rep_dirs = 확증 접두
    sr = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "stage_run")
    sr_direct = [_call_name(n) for n in ast.walk(sr) if isinstance(n, ast.Call)
                 and _call_name(n) in write_fns | {"savez", "savez_compressed", "replace", "makedirs", "mkdir"}]
    sr_dict = next(n for n in ast.walk(sr) if isinstance(n, ast.Dict)
                   and any(isinstance(k, ast.Constant) and k.value == "out_dir" for k in n.keys))
    dd = {k.value: v for k, v in zip(sr_dict.keys, sr_dict.values) if isinstance(k, ast.Constant)}
    out_ok = "out_rel" in ast.dump(dd["out_dir"])
    rep_ok = "conf" in ast.dump(dd["rep_dirs"])
    cl_outside = [_enclosing(par, n) for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "cl"]
    after = {"sealed_counts": sealed_counts(ROOT),
             "fp_conf": sealed_fingerprint(ROOT, list(_confirmatory_prefixes(spec_terms(load_spec())).values()))[0],
             "fp_stab": sealed_fingerprint(ROOT, [STABILITY_PREFIX])[0],
             "fp_old": before["fp_old_fn"](), "pycache": _pycache_dirs(ROOT),
             "consensus": len(glob.glob(_abs(CONSENSUS_GLOB)))}
    return _res("K12 AST·위생", {
        "forbidden_calls_zero": not hits,
        "rqint_calls_only_in_selftest": all((fn or "").startswith("selftest") for _nm, fn in only_selftest),
        "network_imports_zero": not net, "os_environ_zero": not environ,
        "cli_options_exact": opts == {"--stage", "--out"},
        "write_primitives_in_allowed_functions": not bad_w,
        "stage_run_no_direct_write": not sr_direct,
        "stage_run_out_dir_from_spec": out_ok, "stage_run_rep_dirs_confirmatory": rep_ok,
        "cl_calls_only_in_stage_run": set(cl_outside) == {"stage_run"},
        "runtime_write_guard_violations_zero": not guard_violations,
        "cl_calls_during_selftest_zero": cl_calls["n"] == 0,
        "real_sealed_counts_unchanged": after["sealed_counts"] == before["sealed_counts"] == EXPECTED_SEALED_BEFORE,
        "fp_confirmatory_unchanged": after["fp_conf"] == before["fp_conf"] == FP_CONFIRMATORY,
        "fp_stability_unchanged": after["fp_stab"] == before["fp_stab"] == FP_STABILITY,
        "fp_existing25_unchanged": after["fp_old"] == before["fp_old"] == FP_EXISTING25,
        "consensus_dir_not_created": after["consensus"] == 0,
        "pycache_unchanged": after["pycache"] == before["pycache"]},
        forbidden_hits=hits, bad_write_functions=bad_w, guard_violations=guard_violations[:5])


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
    s1 = load_spec()
    T = spec_terms(s1)
    conf = list(_confirmatory_prefixes(T).values())
    out_rel = T["outputs"]["dir"].rstrip("/")

    def fp_old():
        return sealed_fingerprint(ROOT, conf + [STABILITY_PREFIX, out_rel], exclude=True)[0]

    before = {"sealed_counts": sealed_counts(ROOT), "fp_conf": sealed_fingerprint(ROOT, conf)[0],
              "fp_stab": sealed_fingerprint(ROOT, [STABILITY_PREFIX])[0], "fp_old": fp_old(),
              "fp_old_fn": fp_old, "pycache": _pycache_dirs(ROOT)}
    cl_calls = {"n": 0}
    orig_cl = {k: getattr(cl, k) for k in ("gate_a_load", "gate_b_exclusive", "gate_c_settle", "ComputeLock")}

    def _cl_trap(*_a, **_k):
        cl_calls["n"] += 1
        raise RuntimeError("cl 호출 금지(selftest)")

    for k in orig_cl:
        setattr(cl, k, _cl_trap)
    tmp = tempfile.mkdtemp(prefix="aw_selftest_")
    violations = []
    results = []
    try:
        with _write_guard([tmp], violations):
            results.append(selftest_K1_constants())
            results.append(selftest_K2_spec_binding(s1))
            base_tmp = os.path.join(tmp, "base")
            os.makedirs(base_tmp)
            base_paths, fx = _make_fixture(base_tmp, s1, rng_seed=20260923)
            acc_before = {r: _read_bytes(os.path.join(d, "access.log")).count(b"\n")
                          for r, d in base_paths["rep_dirs"].items()}
            base_stdout, base_exc = _run_quiet(base_paths)
            if base_exc is not None:
                raise RuntimeError("base fixture run 실패: %s %s" % (type(base_exc).__name__, base_exc))
            acc_after = {r: _read_bytes(os.path.join(d, "access.log")).count(b"\n")
                         for r, d in base_paths["rep_dirs"].items()}
            results.append(selftest_K3_consensus(base_paths, fx))
            results.append(selftest_K4_repeat_axis(base_paths, fx))
            results.append(selftest_K5_seed_axis(base_paths, fx))
            results.append(selftest_K6_eligible_explicit())
            k7 = os.path.join(tmp, "k7")
            os.makedirs(k7)
            results.append(selftest_K7_undefined(k7, s1))
            r8, m8 = selftest_K8_invalid(tmp, s1)
            results.append(r8)
            r9, m9 = selftest_K9_partial(tmp, s1)
            results.append(r9)
            results.append(selftest_K10_atomic(tmp, s1, base_paths, acc_before, acc_after))
            results.append(selftest_K11_leak(base_paths, base_stdout, m8 + m9))
    finally:
        for k, v in orig_cl.items():
            setattr(cl, k, v)
        shutil.rmtree(tmp, ignore_errors=True)
    results.append(selftest_K12_ast_hygiene(violations, cl_calls, before))
    n_pass = sum(1 for r in results if r["pass"])
    return {
        "_doc": "docs/113 블록 AW / AW-3 — 합성 자체검사 K1~K12. 확증 입력 판독 0. 모든 수치는 합성 fixture 산출물.",
        "provenance": PROVENANCE_SYN, "block": "AW (docs/113)",
        "harness_path": "v3_Multimodal/src/confirmatory_gin_consensus.py",
        "harness_sha256": sha256_file(os.path.abspath(__file__)),
        "spec_path": SPEC_PATH, "spec_sha256": SPEC_SHA256,
        "python": platform.python_version(), "numpy": np.__version__,
        "ts_kst": now_kst(), "n_tests": len(results), "n_pass": n_pass, "n_skip": 0,
        "all_pass": n_pass == len(results) == 12,
        "tests": results, "confirmatory_values_read": 0, "sealed_human_read": 0, "network_calls": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="블록 AW — GIN consensus + 셀별 macro AP·Δ 봉인 산출")
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
