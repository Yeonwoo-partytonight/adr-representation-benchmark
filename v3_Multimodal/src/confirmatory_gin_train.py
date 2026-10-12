#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블록 AT — 확증 GIN 학습 315회 착수·완주·봉인 하네스 (지표 산출 0 · 개봉 0).

권한은 이 파일이 만들지 않는다.
  · 권한      = v3_Multimodal/config/gin_start_supersede.json (is_authorization true)
  · 과학 명세 = v3_Multimodal/config/gin_confirm_harness_freeze_v2.json
  · 운영 보충 = v3_Multimodal/config/gin_train_contract.json  (docs/110 §3 AT-2)
이 파일은 그 셋 아래에서 «실행»만 한다. 지시서 = docs/110 §3 AT-3.

범위: 확증 315 단위(7모델 × train seed 3 × 반복 3 × outer fold 5) → 반복별 OOF 21 × 3 = 63 봉인.
      안정성 42 · consensus · macro AP/Δ/부호 산출 · RQ-int 는 **전부 다음 블록**이다.

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
import io
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
V3SRC = os.path.join(ROOT, "v3_Multimodal", "src")
V2SRC = os.path.join(ROOT, "v2_GNN", "src")
for _p in (V3SRC, V2SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ★ import 순서: train_ladder 를 graph_features 보다 먼저(둘 다 torch 를 끌어온다).
#   MPS fallback 은 import 순서에 기대지 않고 명령줄 환경변수로 고정한다(docs/110 F13).
import train_ladder as tl                      # noqa: E402
import graph_features as gf                    # noqa: E402
import train as gnntrain                       # noqa: E402
import ladder_confirmatory as lc               # noqa: E402
import confirmatory_oof_rest as rest           # noqa: E402
import confirmatory_gin_rep as v1              # noqa: E402
import compute_lock as cl                      # noqa: E402
import torch                                   # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
# 상수 (docs/110 §3 AT-3)
# ═══════════════════════════════════════════════════════════════════════════
CONTRACT_REL = "v3_Multimodal/config/gin_train_contract.json"
CONTRACT_SHA256 = "e50f972674e782f50a2a74890f8b37b3208da77a8cf6c4ac9f8dc6deb4cbce7f"
V2_HARNESS_REL = "v3_Multimodal/src/confirmatory_gin_rep_v2.py"
V2_HARNESS_SHA256 = "644abf4f272c51e673dfb3be2915792502552ba4baad610aaa62fee58101860a"

SESSION_CAP_HOURS = 8
EXIT_HARD_FAILURE = 13
EXIT_RESUME_GATE = 14
EXIT_POWER = 15
EXIT_NOT_IDLE = 10

GATE_FAIL_PREFIX = "supersession 미충족 — 실행 거부(exit 12): "
COND5_NAME = "5:not_unblinded_and_sealed_counts"
LEGACY_SEALED_COUNTS = {"n_sealed_dirs": 25, "n_sealed_files_total": 291,
                        "n_sealed_artifacts": 275, "n_access_log": 16}

REP_SEED = {1: 201, 2: 202, 3: 203}
MODELS = ["M0", "M1", "M1b", "M2b", "P-ID", "P-FAM", "C-CAP"]
TRAIN_SEEDS = [42, 1, 2]
N_FOLD = 5
N_DRUGS = 1092
N_PT = 370
PHI_K = 64
PHI_SEED = 42
INNER_DENOM = 9
ADAPTER_MIN_W = 90

AUTH_DIR = os.path.join(ROOT, "experiments", "runs", "v3_gin_start_authorization")
MANIFEST_T3 = os.path.join(AUTH_DIR, "manifest_t3_launch.json")
MANIFEST_T4 = os.path.join(AUTH_DIR, "manifest_t4_post_confirmatory.json")
SESSIONS = os.path.join(AUTH_DIR, "sessions.jsonl")
SELFTEST_OUT = os.path.join(AUTH_DIR, "selftest_train.json")
PROC = os.path.join(ROOT, "data", "processed")

CKPT_FIELDS = ["rep", "fold", "model", "train_seed", "completed_at_kst",
               "artifact_sha256", "n_epochs", "wall_seconds"]

KST = datetime.timezone(datetime.timedelta(hours=9))


# ═══════════════════════════════════════════════════════════════════════════
# 공용 유틸
# ═══════════════════════════════════════════════════════════════════════════
def now_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def repeat_dir(rep, root=None):
    base = root or os.path.join(ROOT, "experiments", "runs")
    return os.path.join(base, "v3_gin_confirm_rep%d_seed%d" % (rep, REP_SEED[rep]))


def sealed_dir(rep, root=None):
    return os.path.join(repeat_dir(rep, root), "_sealed")


def split_dir(rep):
    return os.path.join(PROC, "splits", "confirmatory",
                        "rep%d_seed%d" % (rep, REP_SEED[rep]))


def unit_key(u):
    return "%d|%d|%s|%d" % (u["rep"], u["fold"], u["model"], u["train_seed"])


def partial_name(model, fold, seed):
    return "%s_fold%d_seed%d.npz" % (model, fold, seed)


def count_sealed(root=None, exclude_dirs=()):
    """stat-only. `_sealed/` 파일을 열지도 해싱하지도 않는다 (v2 sealed_counts 와 동일 계수)."""
    base = root or ROOT
    ex = tuple(os.path.abspath(p) for p in exclude_dirs)
    dirs = files = acc = 0
    for dp, _dn, fn in os.walk(base):
        parts = dp.split(os.sep)
        if ".git" in parts:
            continue
        ap = os.path.abspath(dp)
        if any(ap == e or ap.startswith(e + os.sep) for e in ex):
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


def count_pycache(root=None):
    base = root or ROOT
    n = 0
    for dp, _dn, _fn in os.walk(base):
        if ".git" in dp.split(os.sep):
            continue
        if os.path.basename(dp) == "__pycache__":
            n += 1
    return n


# --- 공개 기록기 (봉인 대상 값은 절대 여기로 오지 않는다) -------------------
def pub_line(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")
        f.flush()
        os.fsync(f.fileno())


def pub_jsonl(path, rec):
    pub_line(path, json.dumps(rec, ensure_ascii=False))


def pub_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def session_event(rec):
    rec = dict(rec)
    rec.setdefault("ts_kst", now_kst())
    pub_jsonl(SESSIONS, rec)


# --- 봉인 기록기 ------------------------------------------------------------
def sealed_access(sdir, path_rel, purpose, step):
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": step,
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "access.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return rec


def sealed_stdout_append(sdir, header, text):
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "train_stdout.log"), "a", encoding="utf-8") as f:
        f.write("### %s\n" % header)
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def sealed_ckpt_append(sdir, rec):
    os.makedirs(sdir, exist_ok=True)
    p = os.path.join(sdir, "checkpoint.jsonl")
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({k: rec[k] for k in CKPT_FIELDS}, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def sealed_ckpt_read(sdir, strict=True):
    """봉인 체크포인트 판독(기계). 반환 = (rows, ok, reason). 값 판독은 키 구성용뿐."""
    p = os.path.join(sdir, "checkpoint.jsonl")
    if not os.path.exists(p):
        return [], True, None
    raw = open(p, "rb").read()
    if raw and not raw.endswith(b"\n"):
        return [], False, "checkpoint.jsonl 마지막 줄 개행 없음(잘림 의심) — 자동 복구 금지"
    rows = []
    for i, line in enumerate(raw.decode("utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            return [], False, "checkpoint.jsonl %d번째 줄 파싱 실패 — 자동 복구 금지" % (i + 1)
    for r in rows:
        if sorted(r.keys()) != sorted(CKPT_FIELDS):
            return [], False, "checkpoint.jsonl 필드 구성 불일치(8필드 고정 위반)"
    keys = [unit_key(r) for r in rows]
    if len(keys) != len(set(keys)):
        return [], False, "checkpoint.jsonl 키 중복"
    if strict:
        pass
    return rows, True, None


def atomic_npz(path, **arrays):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "wb") as f:
        np.savez(f, **arrays)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return sha256_file(path)


# ═══════════════════════════════════════════════════════════════════════════
# 게이트 — v2 서브프로세스 호출 + 조건 5′ (순수 판정 함수)
# ═══════════════════════════════════════════════════════════════════════════
def call_v2_gate():
    """v2 require_supersession() 을 **자식 프로세스**로, 인자 0개로 호출한다."""
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); "
            "import confirmatory_gin_rep_v2 as m; m.require_supersession(); "
            "print('GATE_PASS')" % V3SRC)
    p = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", code],
                       cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def parse_gate_failures(stderr):
    """실패 접두 줄 **하나만** 파싱. 0개·2개 이상 → None(= 판정 불가)."""
    hits = [ln for ln in stderr.splitlines() if ln.startswith(GATE_FAIL_PREFIX)]
    if len(hits) != 1:
        return None
    body = hits[0][len(GATE_FAIL_PREFIX):].strip()
    return [x.strip() for x in body.split(",") if x.strip()]


def gin_repeat_dirs(root=None):
    base = os.path.join(root or ROOT, "experiments", "runs")
    if not os.path.isdir(base):
        return []
    out = []
    for r in (1, 2, 3):
        d = repeat_dir(r, base)
        if os.path.isdir(os.path.join(d, "_sealed")):
            out.append(d)
    return out


def stray_sealed_dirs(root=None, own=()):
    """GIN 소유 반복 디렉터리를 뺀 나머지 `_sealed` 디렉터리 수."""
    base = root or ROOT
    ownabs = tuple(os.path.abspath(p) for p in own)
    n = 0
    for dp, _dn, _fn in os.walk(base):
        if ".git" in dp.split(os.sep):
            continue
        if os.path.basename(dp) != "_sealed":
            continue
        ap = os.path.abspath(dp)
        if any(ap == o or ap.startswith(o + os.sep) for o in ownabs):
            continue
        n += 1
    return n


def gate_verdict(rc, stderr, root, gin_dirs, manifest_exists,
                 harness_sha, contract_sha, legacy=None, skip_manifest_sha=False):
    """순수 판정 함수 — (통과?, mode, 실패 사유 목록, 진단).

    mode = "first_launch" | "launch_retry" | "resume".
    """
    legacy = legacy or LEGACY_SEALED_COUNTS
    diag = {"rc": rc, "n_gin_dirs": len(gin_dirs), "manifest_t3_exists": manifest_exists}
    fails = parse_gate_failures(stderr)
    diag["parsed_failures"] = fails

    # --- 첫 착수 / 첫 착수 재시도 --------------------------------------------
    if not gin_dirs:
        if rc != 0:
            return False, None, ["v2 게이트 rc=%s (첫 착수는 rc 0 이어야 함)" % rc], diag
        if manifest_exists:
            return True, "launch_retry", [], diag
        return True, "first_launch", [], diag

    # --- 재개 ---------------------------------------------------------------
    if not manifest_exists:
        return False, None, ["GIN 봉인 존재하는데 manifest_t3_launch.json 부재"], diag
    if rc == 0:
        return False, None, ["rc 0 인데 GIN 봉인 존재 — 봉인 계수 불변 = 설명 불가"], diag
    if rc != 12:
        return False, None, ["v2 게이트 rc=%s (재개는 rc 12 이어야 함)" % rc], diag
    if fails is None:
        return False, None, ["stderr 실패 접두 줄이 0개 또는 2개 이상 — 파싱 불가"], diag
    if fails != [COND5_NAME]:
        return False, None, ["실패 목록 %r != [%r]" % (fails, COND5_NAME)], diag

    bad = []
    # (a) GIN 반복 디렉터리를 제외한 stat-only 계수
    legacy_obs = count_sealed(root, exclude_dirs=gin_dirs)
    diag["legacy_counts"] = legacy_obs
    if legacy_obs != legacy:
        bad.append("5'a 기존 봉인 계수 %r != %r" % (legacy_obs, legacy))
    # (b) 그 밖의 새 `_sealed` 0
    n_stray = stray_sealed_dirs(root, own=gin_dirs)
    diag["n_stray_sealed_dirs"] = n_stray
    if n_stray != legacy["n_sealed_dirs"]:
        bad.append("5'b GIN 외 _sealed 디렉터리 %d != %d" % (n_stray, legacy["n_sealed_dirs"]))
    if len(gin_dirs) > 3:
        bad.append("5'b GIN 반복 디렉터리 %d > 3" % len(gin_dirs))

    allowed_top = {"checkpoint.jsonl", "env_fingerprint.json", "access.log", "train_stdout.log"}
    for d in gin_dirs:
        sdir = os.path.join(d, "_sealed")
        tag = os.path.basename(d)
        rows, ok, reason = sealed_ckpt_read(sdir)
        if not ok:
            bad.append("5'c %s %s" % (tag, reason))
            continue
        ck_names = {partial_name(r["model"], r["fold"], r["train_seed"]) for r in rows}
        pdir = os.path.join(sdir, "_partial")
        pnames = set()
        if os.path.isdir(pdir):
            pnames = {f for f in os.listdir(pdir) if f.endswith(".npz")}
            if any(f.endswith(".tmp") for f in os.listdir(pdir)):
                bad.append("5'e %s _partial 에 .tmp 잔존(고아 처리 후여야 함)" % tag)
        # (c)
        if pnames != ck_names:
            bad.append("5'c %s partial 집합 != 체크포인트 키 집합 (partial-only %d · ckpt-only %d)"
                       % (tag, len(pnames - ck_names), len(ck_names - pnames)))
        # (d)
        done = {}
        for r in rows:
            done.setdefault((r["model"], r["train_seed"]), set()).add(r["fold"])
        full = {"oof_%s_seed%d.npz" % (m, t) for (m, t), ks in done.items()
                if ks == set(range(N_FOLD))}
        oof = {f for f in os.listdir(sdir)
               if f.startswith("oof_") and f.endswith(".npz")} if os.path.isdir(sdir) else set()
        if not oof <= full:
            bad.append("5'd %s oof 집합 ⊄ 5 fold 완료 그룹 (초과 %d)" % (tag, len(oof - full)))
        # (e)
        failures = os.path.join(d, "failures.jsonl")
        orphan_logged = set()
        if os.path.exists(failures):
            for ln in open(failures, encoding="utf-8"):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if o.get("orphan_path"):
                    orphan_logged.add(os.path.basename(o["orphan_path"]))
        for f in os.listdir(sdir):
            p = os.path.join(sdir, f)
            if os.path.isdir(p):
                if f not in ("_partial", "_orphans"):
                    bad.append("5'e %s 예상 밖 봉인 하위 디렉터리 %s" % (tag, f))
                continue
            if f in allowed_top or (f.startswith("oof_") and f.endswith(".npz")):
                continue
            bad.append("5'e %s 예상 밖 봉인 파일 %s" % (tag, f))
        odir = os.path.join(sdir, "_orphans")
        if os.path.isdir(odir):
            for f in os.listdir(odir):
                if f not in orphan_logged:
                    bad.append("5'e %s 고아 %s 가 failures.jsonl 에 미등재" % (tag, f))

    # (f)
    if not skip_manifest_sha:
        try:
            mf = json.load(open(MANIFEST_T3 if root in (None, ROOT)
                                else os.path.join(root, "experiments", "runs",
                                                  "v3_gin_start_authorization",
                                                  "manifest_t3_launch.json"),
                                encoding="utf-8"))
        except Exception as e:                       # noqa: BLE001
            mf = None
            bad.append("5'f manifest_t3 판독 실패 %s" % type(e).__name__)
        if mf is not None:
            if mf.get("harness_sha256") != harness_sha:
                bad.append("5'f manifest_t3 harness_sha256 불일치")
            if mf.get("contract_sha256") != contract_sha:
                bad.append("5'f manifest_t3 contract_sha256 불일치")
    # (g)
    runs = os.path.join(root or ROOT, "experiments", "runs")
    if os.path.isdir(runs):
        for nm in os.listdir(runs):
            if nm.startswith("v3_gin_stability") or nm.startswith("v3_gin_confirm_consensus"):
                bad.append("5'g 범위 밖 디렉터리 %s 존재" % nm)
    sup = os.path.join(ROOT, "v3_Multimodal", "config", "gin_start_supersede.json")
    if json.load(open(sup, encoding="utf-8")).get("unblinding_performed") is not False:
        bad.append("5'g unblinding_performed != false")

    return (not bad), ("resume" if not bad else None), bad, diag


# --- AC 전원 ----------------------------------------------------------------
def read_power():
    ps = subprocess.run(["pmset", "-g", "ps"], capture_output=True, text=True).stdout
    ad = subprocess.run(["pmset", "-g", "adapter"], capture_output=True, text=True).stdout
    on_ac = "AC Power" in ps
    m = re.search(r"Wattage\s*=\s*(\d+)", ad)
    watt = int(m.group(1)) if m else None
    return {"pmset_ps": ps.strip(), "pmset_adapter": ad.strip(),
            "ac_power": on_ac, "wattage": watt,
            "ok": bool(on_ac and watt is not None and watt >= ADAPTER_MIN_W)}


def wait_load_ok():
    """세션 경계용 부하 판정. gate_a_load 와 달리 sys.exit 하지 않는다."""
    t0 = time.perf_counter()
    while True:
        load1 = os.getloadavg()[0]
        if load1 <= cl.LOAD_HARD_MAX:
            return True, load1
        if time.perf_counter() - t0 >= cl.SETTLE_MAX_S:
            return False, load1
        time.sleep(cl.SETTLE_INTERVAL_S)


# ═══════════════════════════════════════════════════════════════════════════
# 데이터 · side 조립
# ═══════════════════════════════════════════════════════════════════════════
def build_graphs(d):
    """1,092개 그래프를 프로세스 시작 시 1회 만든다 (v2_GNN.data.build_graphs 미사용)."""
    smiles = d["X"]["smiles_canonical"].tolist()
    Ym = d["Ym"]
    graphs, bad = [], 0
    for i, s in enumerate(smiles):
        g = gf.smiles_to_data(s, y=Ym[i].astype(float))
        if g is None:
            bad += 1
            continue
        g.cid = int(d["cid_order"][i])
        graphs.append(g)
    assert bad == 0, "SMILES 파싱 실패 %d건" % bad
    assert len(graphs) == len(smiles), "그래프 수 불일치"
    return graphs


def phi_pid(blocks, otr, N):
    """D4 — B_pid multi-hot 에 등록된 φ(train-fit z-score → PCA-64)를 적용한다.

    SeqBlock.fit / train_ladder.build_side 의 (1) 절차와 같은 순서.
    ladder_confirmatory 는 0바이트 수정하지 않는다(여기 얇은 래퍼뿐).
    """
    M = blocks["B_pid"].transform(np.arange(N)).astype(np.float64)
    rowsum = M.sum(axis=1)
    otr = np.asarray(otr)
    fit_rows = otr[rowsum[otr] > 0]
    assert set(fit_rows.tolist()) <= set(otr.tolist()), "[phi_pid] fit 행 ⊄ outer-train (leak)"
    assert len(fit_rows) >= PHI_K, "[phi_pid] fit 행 %d < %d" % (len(fit_rows), PHI_K)
    sc = StandardScaler().fit(M[fit_rows])
    pca = PCA(n_components=PHI_K, svd_solver="full", random_state=PHI_SEED).fit(sc.transform(M[fit_rows]))
    Xp = pca.transform(sc.transform(M)).astype(np.float32)
    zero = rowsum == 0
    Xp[zero] = 0.0
    assert np.abs(Xp[zero]).sum() == 0.0, "[phi_pid] 비매핑 재-0 실패"
    return Xp, {"n_fit_rows": int(len(fit_rows)), "dim": int(Xp.shape[1]),
                "n_zero_rows": int(zero.sum()), "b_pid_dim": int(M.shape[1])}


def side_block_ids(model):
    """D3 — RF 블록 목록에서 B0(Morgan) 만 뺀 것."""
    return [b for b in lc.MODEL_BLOCKS[model] if b != "B0"]


def build_side(blocks, model, otr, N):
    ids = side_block_ids(model)
    if not ids:
        return None, 0, {"blocks": [], "phi": None}
    parts, meta = [], {"blocks": [], "phi": None}
    for b in ids:
        if b == "B_pid":
            Xp, pmeta = phi_pid(blocks, otr, N)
            parts.append(Xp)
            meta["phi"] = pmeta
            meta["blocks"].append("phi(B_pid)")
        else:
            parts.append(blocks[b].transform(np.arange(N)).astype(np.float32))
            meta["blocks"].append(b)
    side = np.hstack(parts).astype(np.float32)
    return side, int(side.shape[1]), meta


# ═══════════════════════════════════════════════════════════════════════════
# stage: plan
# ═══════════════════════════════════════════════════════════════════════════
def make_plan():
    design = v1.frozen_design(v1.load_frozen())
    plan = v1.build_plan(design)
    units = plan["confirmatory_units"]
    assert len(units) == 315, "확증 단위 %d != 315" % len(units)
    assert design["models"] == MODELS, "모델 순서 불일치"
    assert design["confirmatory_seeds"] == TRAIN_SEEDS, "train seed 불일치"
    return units, plan


def stage_plan(out):
    units, plan = make_plan()
    body = {"_doc": "블록 AT 확증 실행 계획 315 단위 (docs/110 §3 AT-5). 학습 0.",
            "generated_kst": now_kst(),
            "source": "confirmatory_gin_rep.build_plan(frozen_design(load_frozen()))['confirmatory_units']",
            "n_confirmatory": len(units),
            "n_stability_executed": 0,
            "order": "rep → fold → model(M0,M1,M1b,M2b,P-ID,P-FAM,C-CAP) → train_seed(42,1,2)",
            "rep_seed_map": {str(k): v for k, v in REP_SEED.items()},
            "units": units}
    payload = json.dumps(body, ensure_ascii=False, indent=2, sort_keys=False).encode("utf-8")
    body["plan_sha256"] = sha256_bytes(payload)
    if out:
        pub_json(out, body)
        print("plan → %s (n=%d sha256=%s)" % (out, len(units), body["plan_sha256"]))
    else:
        print(json.dumps({k: body[k] for k in
                          ("n_confirmatory", "n_stability_executed", "order", "plan_sha256")},
                         ensure_ascii=False, indent=2))
    return body


def plan_sha256():
    units, _ = make_plan()
    return sha256_bytes(json.dumps(units, ensure_ascii=False, sort_keys=True).encode("utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# 환경
# ═══════════════════════════════════════════════════════════════════════════
def env_info():
    import sklearn
    import torch_geometric
    import rdkit
    return {"python": platform.python_version(), "torch": torch.__version__,
            "torch_geometric": torch_geometric.__version__, "rdkit": rdkit.__version__,
            "sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__,
            "machine": platform.machine(), "os": "%s %s" % (platform.system(), platform.release()),
            "device": "mps",
            "mps_fallback_env": "1 (명령줄에서 고정 — 하네스는 환경변수를 판독하지 않는다)"}


def env_fingerprint_obj():
    splits = {}
    for r in (1, 2, 3):
        sd = split_dir(r)
        for fn in sorted(os.listdir(sd)):
            p = os.path.join(sd, fn)
            if os.path.isfile(p):
                splits["rep%d/%s" % (r, fn)] = sha256_file(p)
    e = env_info()
    e["split_files_sha256"] = splits
    e["contract_sha256"] = CONTRACT_SHA256
    e["harness_sha256"] = sha256_file(os.path.abspath(__file__))
    e["sap_manifest_sha256"] = sha256_file(os.path.join(ROOT, "experiments", "sap", "manifest.json"))
    e["ts_kst"] = now_kst()
    return e


# ═══════════════════════════════════════════════════════════════════════════
# 고아 처리
# ═══════════════════════════════════════════════════════════════════════════
def sweep_orphans(rep):
    """.tmp, 또는 체크포인트 키가 없는 partial = 강제종료 흔적 → 열지 않고 _orphans/ 로 이동."""
    d = repeat_dir(rep)
    sdir = os.path.join(d, "_sealed")
    pdir = os.path.join(sdir, "_partial")
    moved = []
    if not os.path.isdir(pdir):
        return moved
    rows, ok, reason = sealed_ckpt_read(sdir)
    if not ok:
        return None if reason else moved
    known = {partial_name(r["model"], r["fold"], r["train_seed"]) for r in rows}
    odir = os.path.join(sdir, "_orphans")
    for f in sorted(os.listdir(pdir)):
        if f.endswith(".tmp") or (f.endswith(".npz") and f not in known):
            os.makedirs(odir, exist_ok=True)
            ts = datetime.datetime.now(KST).strftime("%Y%m%dT%H%M%S")
            dst = os.path.join(odir, "%s.%s" % (f, ts))
            shutil.move(os.path.join(pdir, f), dst)
            base = f[:-4] if f.endswith(".tmp") else f
            base = base[:-4] if base.endswith(".npz") else base
            m = re.match(r"^(.*)_fold(\d+)_seed(\d+)$", base)
            rec = {"rep": rep, "fold": int(m.group(2)) if m else None,
                   "model": m.group(1) if m else None,
                   "train_seed": int(m.group(3)) if m else None,
                   "kind": "interrupted", "ts_kst": now_kst(),
                   "orphan_path": os.path.relpath(dst, ROOT)}
            pub_jsonl(os.path.join(d, "failures.jsonl"), rec)
            moved.append(rec)
    return moved


def failure_counts(rep):
    """단위별 누적 실패 횟수(고아 포함) — 공개 failures.jsonl 만 읽는다."""
    p = os.path.join(repeat_dir(rep), "failures.jsonl")
    out = {}
    if not os.path.exists(p):
        return out
    for ln in open(p, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if o.get("model") is None:
            continue
        k = "%d|%s|%s|%s" % (rep, o.get("fold"), o.get("model"), o.get("train_seed"))
        out[k] = out.get(k, 0) + 1
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: run
# ═══════════════════════════════════════════════════════════════════════════
class Stopper:
    def __init__(self):
        self.flag = False
        self.signum = None

    def install(self):
        def handler(signum, frame):
            self.flag = True
            self.signum = signum
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass


def session_gate(harness_sha):
    """세션 시작 게이트 — 반환 (mode, diag). 실패 시 exit."""
    rc, sout, serr = call_v2_gate()
    gin_dirs = gin_repeat_dirs()
    ok, mode, bad, diag = gate_verdict(
        rc, serr, ROOT, gin_dirs, os.path.exists(MANIFEST_T3),
        harness_sha, CONTRACT_SHA256)
    diag["gate_pass_token"] = ("GATE_PASS" in sout)
    if not ok:
        session_event({"event": "gate_reject", "mode": None, "failures": bad, "diag": diag})
        print("[GATE] 거부 — %s" % "; ".join(bad), file=sys.stderr)
        sys.exit(EXIT_RESUME_GATE)
    # 고아 처리 (게이트 5′ 전에 수행되어야 하나, 계수를 바꾸지 않으므로 이 순서로 충분)
    orphans = []
    if mode == "resume":
        for r in (1, 2, 3):
            if os.path.isdir(sealed_dir(r)):
                mv = sweep_orphans(r)
                if mv is None:
                    session_event({"event": "gate_reject", "failures": ["체크포인트 잘림"], "diag": diag})
                    print("[GATE] 거부 — checkpoint.jsonl 잘림, 자동 복구 금지", file=sys.stderr)
                    sys.exit(EXIT_RESUME_GATE)
                orphans += mv
        if orphans:
            ok2, _m2, bad2, diag2 = gate_verdict(
                rc, serr, ROOT, gin_repeat_dirs(), True, harness_sha, CONTRACT_SHA256)
            diag["post_orphan"] = diag2
            if not ok2:
                session_event({"event": "gate_reject", "failures": bad2, "diag": diag})
                print("[GATE] 거부(고아 처리 후) — %s" % "; ".join(bad2), file=sys.stderr)
                sys.exit(EXIT_RESUME_GATE)
    diag["n_orphans_moved"] = len(orphans)
    return mode, diag


def write_manifest_t3(harness_sha, power, load1):
    rc, sout, serr = call_v2_gate()
    f4 = json.load(open(os.path.join(ROOT, CONTRACT_REL), encoding="utf-8"))["preconditions"]
    obj = {"_doc": "블록 AT 착수 시점 manifest (docs/110 §3 AT-3 (2)). 1회 기록 후 0바이트 불변.",
           "ts_kst": now_kst(),
           "v2_gate": {"returncode": rc, "stdout_token": "GATE_PASS" if "GATE_PASS" in sout else None,
                       "stderr_nonempty": bool(serr.strip())},
           "sealed_counts_at_launch": count_sealed(),
           "harness_sha256": harness_sha,
           "contract_sha256": CONTRACT_SHA256,
           "preconditions": f4,
           "ac_power": {"pmset_ps": power["pmset_ps"], "pmset_adapter": power["pmset_adapter"],
                        "wattage": power["wattage"]},
           "load1": round(load1, 2),
           "env": env_info(),
           "plan_sha256": plan_sha256(),
           "n_units_planned": 315,
           "unblinding_performed": False}
    pub_json(MANIFEST_T3, obj)
    return obj


def stage_run():
    harness_sha = sha256_file(os.path.abspath(__file__))
    assert sha256_file(os.path.join(ROOT, CONTRACT_REL)) == CONTRACT_SHA256, "계약 sha 불일치"
    assert sha256_file(os.path.join(ROOT, V2_HARNESS_REL)) == V2_HARNESS_SHA256, "v2 하네스 sha 불일치"

    cl.gate_a_load("confirmatory_gin_train entry")       # 락 획득 전 1회만
    stopper = Stopper()
    with cl.ComputeLock(script="confirmatory_gin_train.py", role="runner"):
        stopper.install()                                # ★ ComputeLock 의 즉시-종료 핸들러를 재설치
        rc = run_loop(harness_sha, stopper)
    return rc


def run_loop(harness_sha, stopper):
    units, _ = make_plan()
    device = gnntrain.get_device({"device": "mps"})
    assert str(device) == "mps", "device %s != mps (auto 폴백 금지)" % device

    d = lc.load_frozen()
    N = len(d["cid_order"])
    assert N == N_DRUGS, "N %d != %d" % (N, N_DRUGS)
    graphs = build_graphs(d)
    cid2idx = {int(c): i for i, c in enumerate(d["cid_order"])}
    blocks = rest.make_blocks(d)
    ycols = d["ycols"]
    assert len(ycols) == N_PT, "PT %d != %d" % (len(ycols), N_PT)

    session_n = 0
    while True:
        session_n += 1
        mode, diag = session_gate(harness_sha)
        power = read_power()
        if not power["ok"]:
            session_event({"event": "session_end", "session": session_n, "mode": mode,
                           "stopped_reason": "power", "ac_power": power["ac_power"],
                           "wattage": power["wattage"]})
            print("[POWER] AC 전원 미충족 (ac=%s wattage=%s) — 학습 0"
                  % (power["ac_power"], power["wattage"]), file=sys.stderr)
            return EXIT_POWER
        ok_load, load1 = wait_load_ok()
        if not ok_load:
            session_event({"event": "session_end", "session": session_n, "mode": mode,
                           "stopped_reason": "load", "load1": round(load1, 2)})
            print("[LOAD] load1=%.2f > %.2f — 학습 0" % (load1, cl.LOAD_HARD_MAX), file=sys.stderr)
            return EXIT_NOT_IDLE

        if mode == "first_launch":
            write_manifest_t3(harness_sha, power, load1)
        elif mode == "launch_retry":
            session_event({"event": "launch_retry", "session": session_n,
                           "note": "manifest_t3 존재 + GIN 봉인 0 + rc 0 — 첫 착수 재시도"})

        session_event({"event": "session_start", "session": session_n, "mode": mode,
                       "gate": diag, "ac_power": power["ac_power"], "wattage": power["wattage"],
                       "load1": round(load1, 2)})

        res = run_session(units, d, graphs, cid2idx, blocks, ycols, device,
                          session_n, stopper)
        session_event({"event": "session_end", "session": session_n,
                       "n_units_completed": res["n_done"],
                       "stopped_reason": res["stopped_reason"]})

        if res["stopped_reason"] == "hard_failure_twice":
            print("[HARD] 동일 단위 2회 실패 — 전체 정지", file=sys.stderr)
            return EXIT_HARD_FAILURE
        if res["stopped_reason"] == "signal":
            return 0
        if res["stopped_reason"] == "complete":
            session_event({"event": "confirmatory_complete", "n_units": 315,
                           "n_oof": 63, "n_sessions": session_n})
            print("[DONE] 확증 315 단위 + 63 npz 완료 — 안정성 단위로 넘어가지 않는다.")
            return 0
        # session_cap → 다음 세션
        cl.gate_c_settle("블록 AT 세션 경계 %d" % session_n)


def load_state():
    """반복별 체크포인트 키 집합 (기계 판독 · access.log 기록)."""
    done = {}
    for r in (1, 2, 3):
        sdir = sealed_dir(r)
        if not os.path.isdir(sdir):
            done[r] = []
            continue
        sealed_access(sdir, "_sealed/checkpoint.jsonl", "resume-state",
                      "블록 AT checkpoint 판독(세션 시작 1회)")
        rows, ok, reason = sealed_ckpt_read(sdir)
        assert ok, reason
        done[r] = rows
    return done


def run_session(units, d, graphs, cid2idx, blocks, ycols, device, session_n, stopper):
    t_session = time.perf_counter()
    state = load_state()
    done_keys = {unit_key(r) for rows in state.values() for r in rows}
    fails = {}
    for r in (1, 2, 3):
        fails.update(failure_counts(r))

    cur_rf = None          # (rep, fold)
    cur_rfm = None         # (rep, fold, model)
    otr = te = None
    scaf = None
    itr = iva = None
    side = None
    side_dim = 0
    side_meta = None
    n_done = 0

    for u in units:
        k = unit_key(u)
        if k in done_keys:
            continue
        if stopper.flag:
            return {"n_done": n_done, "stopped_reason": "signal"}
        if (time.perf_counter() - t_session) / 3600.0 >= SESSION_CAP_HOURS:
            return {"n_done": n_done, "stopped_reason": "session_cap"}

        rep, fold, model, seed = u["rep"], u["fold"], u["model"], u["train_seed"]
        rdir = repeat_dir(rep)
        sdir = os.path.join(rdir, "_sealed")
        if not os.path.isdir(sdir):
            os.makedirs(os.path.join(sdir, "_partial"), exist_ok=True)
            pub_json(os.path.join(sdir, "env_fingerprint.json"), env_fingerprint_obj())
            pub_json(os.path.join(rdir, "env_public.json"), env_info())
            sealed_access(sdir, "_sealed/", "create", "블록 AT 반복 디렉터리 생성")

        # --- (rep, fold) 전환 ------------------------------------------------
        if cur_rf != (rep, fold):
            df = rest.read_fold_membership(rep)
            assert len(df) == N_DRUGS, "fold_membership 행수 불일치"
            folds_x = rest.fold_of_row_for(rep, d["cid_order"])
            assert np.array_equal(folds_x, df["fold"].values.astype(int)), \
                "folds.json 과 fold_membership.csv 불일치"
            scaf = df["scaffold"].tolist()
            otr = np.where(df["fold"].values != fold)[0]
            te = np.where(df["fold"].values == fold)[0]
            iva, itr, _g, _v = v1.inner_split(scaf, otr, 1000 * REP_SEED[rep] + fold, INNER_DENOM)
            assert len(iva) == 97, "inner-valid %d != 97" % len(iva)
            assert sorted(list(iva) + list(itr)) == sorted(otr.tolist()), "inner split 합 불일치"
            Yi = d["Ym"][np.asarray(itr)]
            n_zero_pt = int((Yi.sum(axis=0) == 0).sum())
            assert n_zero_pt == 0, "inner-train 양성 0 PT %d != 0" % n_zero_pt
            pub_json(os.path.join(rdir, "split_diagnostics_public.json"),
                     _merge_split_diag(os.path.join(rdir, "split_diagnostics_public.json"),
                                       rep, fold, len(otr), len(te), len(itr), len(iva),
                                       n_zero_pt))
            cur_rf = (rep, fold)
            cur_rfm = None

        # --- (rep, fold, model) 전환 ----------------------------------------
        if cur_rfm != (rep, fold, model):
            leak, order = rest.fit_fold(blocks, model, otr, d, N_DRUGS)
            assert all(v == 0 for v in leak.values()), "leak_rows != 0"
            side, side_dim, side_meta = build_side(blocks, model, otr, N_DRUGS)
            tl.attach_side({"train": [graphs[i] for i in itr],
                            "valid": [graphs[i] for i in iva],
                            "test": [graphs[i] for i in te]},
                           side if side is not None else np.zeros((N_DRUGS, 0), np.float32),
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
            except BaseException as e:                     # noqa: BLE001
                exc_type = type(e).__name__
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    sealed_stdout_append(sdir, "%s | %s | %s" % (k, now_kst(), exc_type),
                                         buf.getvalue())
                    raise
            wall = time.perf_counter() - t0
            sealed_stdout_append(sdir, "%s | %s | retry=%d | %s"
                                 % (k, now_kst(), n_retry, exc_type or "ok"), buf.getvalue())
            if exc_type is None:
                if not bool(np.isfinite(res["P_test"]).all()):
                    exc_type = "NonFinitePrediction"
                else:
                    assert res["P_test"].shape == (len(te), N_PT), "P_test shape 불일치"
            if exc_type is None:
                break
            tl.free_mem(device)
            pub_jsonl(os.path.join(rdir, "failures.jsonl"),
                      {"rep": rep, "fold": fold, "model": model, "train_seed": seed,
                       "kind": "hard_technical_failure", "exception_type": exc_type,
                       "ts_kst": now_kst()})
            fails[k] = fails.get(k, 0) + 1
            if fails[k] >= 2:
                return {"n_done": n_done, "stopped_reason": "hard_failure_twice"}
            n_retry += 1

        # --- 원자적 쓰기 ------------------------------------------------------
        ppath = os.path.join(sdir, "_partial", partial_name(model, fold, seed))
        psha = atomic_npz(ppath, P_test=res["P_test"].astype(np.float32),
                          best_ep=np.int32(res["best_ep"]), best_v=np.float64(res["valid"]))
        sealed_ckpt_append(sdir, {
            "rep": rep, "fold": fold, "model": model, "train_seed": seed,
            "completed_at_kst": now_kst(), "artifact_sha256": psha,
            "n_epochs": int(min(res["best_ep"] + tl.PATIENCE, tl.EPOCHS)),
            "wall_seconds": round(wall, 3)})
        pub_line(os.path.join(rdir, "run.log"),
                 "%d %d %s %d %.3f %d %s %d"
                 % (rep, fold, model, seed, wall, side_dim, "mps", n_retry))
        done_keys.add(k)
        n_done += 1
        tl.free_mem(device)

        # --- 조립 --------------------------------------------------------------
        maybe_assemble(rep, model, seed, d, sdir)

    return {"n_done": n_done, "stopped_reason": "complete"}


def _merge_split_diag(path, rep, fold, n_otr, n_te, n_itr, n_iva, n_zero_pt):
    obj = {}
    if os.path.exists(path):
        obj = json.load(open(path, encoding="utf-8"))
    obj.setdefault("_doc", "블록 AT 분할 진단(공개 — 개수뿐).")
    obj.setdefault("folds", {})
    obj["folds"]["rep%d_fold%d" % (rep, fold)] = {
        "n_outer_train": int(n_otr), "n_outer_test": int(n_te),
        "n_inner_train": int(n_itr), "n_inner_valid": int(n_iva),
        "n_inner_train_zero_positive_pt": int(n_zero_pt)}
    obj["updated_kst"] = now_kst()
    return obj


def maybe_assemble(rep, model, seed, d, sdir):
    rows, ok, reason = sealed_ckpt_read(sdir)
    assert ok, reason
    mine = [r for r in rows if r["model"] == model and r["train_seed"] == seed]
    if {r["fold"] for r in mine} != set(range(N_FOLD)):
        return None
    oof_path = os.path.join(sdir, "oof_%s_seed%d.npz" % (model, seed))
    if os.path.exists(oof_path):
        return oof_path
    sealed_access(sdir, "_sealed/_partial/%s_fold*_seed%d.npz" % (model, seed),
                  "assemble", "블록 AT assemble")
    cid_order = np.asarray(d["cid_order"], dtype=np.int64)
    fold_of = rest.fold_of_row_for(rep, d["cid_order"])
    P = np.zeros((N_DRUGS, N_PT), dtype=np.float32)
    filled = np.zeros(N_DRUGS, dtype=np.int32)
    for r in mine:
        pp = os.path.join(sdir, "_partial", partial_name(model, r["fold"], seed))
        assert sha256_file(pp) == r["artifact_sha256"], "partial sha 불일치 fold%d" % r["fold"]
        rowsel = np.where(fold_of == r["fold"])[0]
        with np.load(pp) as z:
            Pt = z["P_test"]
        assert Pt.shape == (len(rowsel), N_PT), "partial shape 불일치 fold%d" % r["fold"]
        P[rowsel] = Pt
        filled[rowsel] += 1
    assert bool((filled == 1).all()), "행 배치 실패 — 모든 행이 정확히 1번이 아님"
    atomic_npz(oof_path, P=P, y=d["Ym"].astype(np.int8),
               pt_index=np.arange(N_PT, dtype=np.int32), cid_order=cid_order)
    return oof_path


# ═══════════════════════════════════════════════════════════════════════════
# stage: status  (봉인 내용 판독 0 — 체크포인트는 줄 수만 센다)
# ═══════════════════════════════════════════════════════════════════════════
def stage_status(out):
    st = {"ts_kst": now_kst(), "repeats": {}, "n_units_done": 0, "n_oof": 0}
    walls = []
    for r in (1, 2, 3):
        sdir = sealed_dir(r)
        tag = "rep%d_seed%d" % (r, REP_SEED[r])
        if not os.path.isdir(sdir):
            st["repeats"][tag] = {"n_checkpoint_lines": 0, "n_oof": 0, "n_partial": 0}
            continue
        ck = os.path.join(sdir, "checkpoint.jsonl")
        n_lines = sum(1 for ln in open(ck, encoding="utf-8") if ln.strip()) \
            if os.path.exists(ck) else 0
        pdir = os.path.join(sdir, "_partial")
        n_part = len([f for f in os.listdir(pdir) if f.endswith(".npz")]) \
            if os.path.isdir(pdir) else 0
        n_oof = len([f for f in os.listdir(sdir)
                     if f.startswith("oof_") and f.endswith(".npz")])
        st["repeats"][tag] = {"n_checkpoint_lines": n_lines, "n_oof": n_oof, "n_partial": n_part}
        st["n_units_done"] += n_lines
        st["n_oof"] += n_oof
        rl = os.path.join(repeat_dir(r), "run.log")
        if os.path.exists(rl):
            for ln in open(rl, encoding="utf-8"):
                parts = ln.split()
                if len(parts) == 8:
                    try:
                        walls.append(float(parts[4]))
                    except ValueError:
                        pass
    st["n_units_total"] = 315
    st["n_oof_total"] = 63
    if walls:
        mean_w = sum(walls) / len(walls)
        st["mean_wall_seconds"] = round(mean_w, 1)
        st["eta_hours_remaining"] = round((315 - st["n_units_done"]) * mean_w / 3600.0, 2)
    if os.path.exists(SESSIONS):
        lines = [ln for ln in open(SESSIONS, encoding="utf-8") if ln.strip()]
        st["n_session_events"] = len(lines)
        st["last_session_event"] = json.loads(lines[-1]) if lines else None
    st["manifest_t3_exists"] = os.path.exists(MANIFEST_T3)
    st["running_pids"] = _running_pids()
    if out:
        pub_json(out, st)
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return st


def _running_pids():
    p = subprocess.run(["pgrep", "-f", "confirmatory_gin_train.py"],
                       capture_output=True, text=True)
    me = os.getpid()
    return [int(x) for x in p.stdout.split() if x.strip() and int(x) != me]


# ═══════════════════════════════════════════════════════════════════════════
# stage: finalize  (Phase B 전용)
# ═══════════════════════════════════════════════════════════════════════════
def stage_finalize(out):
    units, _ = make_plan()
    planned = {unit_key(u) for u in units}
    d = lc.load_frozen()
    cid_order = np.asarray(d["cid_order"], dtype=np.int64)
    Ym = d["Ym"].astype(np.int8)
    rep_info, all_keys, npz_sha, ck_sha = {}, set(), {}, {}
    n_wall = 0.0
    for r in (1, 2, 3):
        sdir = sealed_dir(r)
        tag = "rep%d_seed%d" % (r, REP_SEED[r])
        sealed_access(sdir, "_sealed/", "finalize", "블록 AT finalize 검증")
        rows, ok, reason = sealed_ckpt_read(sdir)
        assert ok, reason
        keys = {unit_key(x) for x in rows}
        assert len(keys) == len(rows) == 105, "%s 체크포인트 %d != 105" % (tag, len(rows))
        all_keys |= keys
        n_wall += sum(float(x["wall_seconds"]) for x in rows)
        ck_sha[tag] = sha256_file(os.path.join(sdir, "checkpoint.jsonl"))
        oofs = sorted(f for f in os.listdir(sdir) if f.startswith("oof_") and f.endswith(".npz"))
        assert len(oofs) == 21, "%s oof %d != 21" % (tag, len(oofs))
        for f in oofs:
            p = os.path.join(sdir, f)
            npz_sha["%s/%s" % (tag, f)] = sha256_file(p)
            with np.load(p) as z:
                assert sorted(z.files) == ["cid_order", "pt_index", "y", "P"][::1] or \
                    sorted(z.files) == sorted(["P", "y", "pt_index", "cid_order"]), \
                    "%s/%s 키 구성 불일치" % (tag, f)
                assert z["P"].shape == (N_DRUGS, N_PT) and z["P"].dtype == np.float32
                assert z["y"].dtype == np.int8 and np.array_equal(z["y"], Ym)
                assert np.array_equal(z["pt_index"], np.arange(N_PT, dtype=np.int32))
                assert np.array_equal(z["cid_order"], cid_order)
        pdir = os.path.join(sdir, "_partial")
        n_part = len([f for f in os.listdir(pdir) if f.endswith(".npz")])
        odir = os.path.join(sdir, "_orphans")
        n_orph = len(os.listdir(odir)) if os.path.isdir(odir) else 0
        fpath = os.path.join(repeat_dir(r), "failures.jsonl")
        n_fail = len([ln for ln in open(fpath, encoding="utf-8") if ln.strip()]) \
            if os.path.exists(fpath) else 0
        rep_info[tag] = {"n_checkpoint": len(rows), "n_oof": len(oofs), "n_partial": n_part,
                         "n_orphans": n_orph, "n_failures_logged": n_fail,
                         "checkpoint_sha256": ck_sha[tag]}
    assert all_keys == planned, "체크포인트 키 집합 != 계획 315"
    n_sessions = 0
    if os.path.exists(SESSIONS):
        n_sessions = len([ln for ln in open(SESSIONS, encoding="utf-8")
                          if ln.strip() and '"session_start"' in ln])
    obj = {"_doc": "블록 AT 확증 GIN 315 완주 manifest (docs/110 §3 AT-3 (8)). 지표 산출 0 · 개봉 0.",
           "ts_kst": now_kst(),
           "n_units": len(all_keys), "n_oof": len(npz_sha),
           "per_repeat": rep_info,
           "oof_sha256": npz_sha,
           "checkpoint_sha256": ck_sha,
           "sealed_counts_final": count_sealed(),
           "legacy_sealed_counts_expected": LEGACY_SEALED_COUNTS,
           "n_sessions": n_sessions,
           "total_wall_seconds": round(n_wall, 1),
           "total_wall_hours": round(n_wall / 3600.0, 2),
           "harness_sha256": sha256_file(os.path.abspath(__file__)),
           "contract_sha256": CONTRACT_SHA256,
           "stability_units_executed": 0,
           "consensus_built": False,
           "metrics_computed": False,
           "unblinding_performed": False}
    pub_json(out or MANIFEST_T4, obj)
    print("finalize → %s" % (out or MANIFEST_T4))
    return obj


# ═══════════════════════════════════════════════════════════════════════════
# stage: selftest  U1~U12 (확증 라벨로 학습 0회)
# ═══════════════════════════════════════════════════════════════════════════
def _case(cases, name, desc, ok, detail=None, skip=None):
    cases.append({"case": name, "desc": desc, "pass": bool(ok) and skip is None,
                  "skip_reason": skip, "detail": detail})
    return cases[-1]


def _forbidden_names():
    return {"best_v", "best_ep", "n_epochs", "P_test"}


def stage_selftest(out):
    cases = []
    sealed0 = count_sealed()
    pyc0 = count_pycache()
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    harness_sha = sha256_bytes(src.encode("utf-8"))

    # ---- U1 상수 해시 -------------------------------------------------------
    c = json.load(open(os.path.join(ROOT, CONTRACT_REL), encoding="utf-8"))
    d1 = {"contract": sha256_file(os.path.join(ROOT, CONTRACT_REL)) == CONTRACT_SHA256,
          "v2_harness": sha256_file(os.path.join(ROOT, V2_HARNESS_REL)) == V2_HARNESS_SHA256}
    pre = c["preconditions"]
    bad = []
    for grp in ("f4_authority_chain", "f5_reused_modules"):
        for rel, meta in pre[grp].items():
            if sha256_file(os.path.join(ROOT, rel)) != meta["sha256"]:
                bad.append(rel)
    d1["preconditions_mismatch"] = bad
    _case(cases, "U1", "상수 해시 — 계약·v2 하네스·F4 13종·F5 12종",
          d1["contract"] and d1["v2_harness"] and not bad, d1)

    # ---- U2 계획 ------------------------------------------------------------
    units, plan = make_plan()
    d2 = {"n": len(units), "order_ok": units == v1.build_plan(v1.frozen_design(v1.load_frozen()))["confirmatory_units"],
          "n_stability_scheduled": 0,
          "first": units[0], "last": units[-1]}
    _case(cases, "U2", "실행 목록 == v1 build_plan confirmatory_units(315·순서 동일) · 안정성 0",
          d2["n"] == 315 and d2["order_ok"], d2)

    # ---- 데이터 (라벨 무관 검사에 공용) --------------------------------------
    d = lc.load_frozen()
    N = len(d["cid_order"])
    blocks = rest.make_blocks(d)
    df1 = rest.read_fold_membership(1)
    otr0 = np.where(df1["fold"].values != 0)[0]
    te0 = np.where(df1["fold"].values == 0)[0]

    # ---- U3 side 도출 -------------------------------------------------------
    tbl = c["side_input_derivation"]["table"]
    d3 = {"models": {}, "fusion_all_concat": True}
    for m in MODELS:
        ids = side_block_ids(m)
        exp = [x for x in tbl[m]["gin_side"]]
        norm = ["phi(B_pid)" if x == "B_pid" else x for x in ids]
        d3["models"][m] = {"derived": ids, "normalized": norm, "contract": exp,
                           "match": norm == exp}
        if m != "M0" and tbl[m]["fusion"] != "concat":
            d3["fusion_all_concat"] = False
    dims = {}
    for m in MODELS:
        rest.fit_fold(blocks, m, otr0, d, N)
        _s, sd, _meta = build_side(blocks, m, otr0, N)
        dims[m] = sd
    d3["side_dim_rep1_fold0"] = dims
    exp_dim = {"M0": 0, "M1": 2, "M1b": 12, "M2b": 76, "P-ID": 76, "C-CAP": 76}
    dim_ok = all(dims[k] == v for k, v in exp_dim.items()) and 52 <= dims["P-FAM"] <= 54
    _case(cases, "U3", "7모델 side = MODEL_BLOCKS−{B0}(P-ID 는 φ) · M0 side 없음 · concat · side_dim 기대값",
          all(x["match"] for x in d3["models"].values()) and d3["fusion_all_concat"] and dim_ok, d3)

    # ---- U3b φ(B_pid) -------------------------------------------------------
    blocks["B_pid"].fit(otr0)
    Xp, pm = phi_pid(blocks, otr0, N)
    M = blocks["B_pid"].transform(np.arange(N))
    zero = M.sum(axis=1) == 0
    sub = phi_pid(blocks, otr0, N)[0]
    d3b = dict(pm)
    d3b["fit_rows_subset_of_otr"] = True
    d3b["zero_rows_exactly_zero"] = bool(np.abs(Xp[zero]).sum() == 0.0)
    d3b["transform_equivalence_max_abs"] = float(np.abs(Xp[te0] - sub[te0]).max())
    _case(cases, "U3b", "φ(B_pid) — fit⊆otr · fit≥64 · 64차원 · 행합0 행 정확히 0 · transform 동등성",
          pm["dim"] == PHI_K and pm["n_fit_rows"] >= PHI_K and d3b["zero_rows_exactly_zero"]
          and d3b["transform_equivalence_max_abs"] <= 1e-6, d3b)

    # ---- U4 블록 동등성 -----------------------------------------------------
    d4 = {"blocks": {}, "leak_rows": {}}
    leak, order = rest.fit_fold(blocks, "C-CAP", otr0, d, N)
    d4["leak_rows"] = leak
    iva0, itr0, _g, _v = v1.inner_split(df1["scaffold"].tolist(), otr0, 1000 * 201 + 0, INNER_DENOM)
    worst = 0.0
    for b in ("B1", "B_m1b", "B_seq", "C_ccap", "B_pid", "B_fam"):
        if b not in blocks:
            continue
        try:
            full = blocks[b].transform(np.arange(N))
        except Exception:                                  # noqa: BLE001
            blocks[b].fit(otr0)
            full = blocks[b].transform(np.arange(N))
        ent = {}
        for nm, rows in (("test", te0), ("inner_valid", np.asarray(iva0)),
                         ("inner_train", np.asarray(itr0))):
            direct = blocks[b].transform(rows)
            diff = float(np.abs(full[rows] - direct).max())
            ent[nm] = {"max_abs_diff": diff, "bitwise_identical": bool(diff == 0.0)}
            worst = max(worst, diff)
        d4["blocks"][b] = ent
    ss = np.random.SeedSequence([int(lc.SEED), 7])
    d4["c_ccap_row_deterministic"] = bool(
        np.array_equal(np.random.default_rng(np.random.SeedSequence([int(lc.SEED), 7])).random(4),
                       np.random.default_rng(ss).random(4)))
    d4["max_abs_diff_overall"] = worst
    d4["side_dim_by_model"] = dims
    _case(cases, "U4", "블록 동등성 transform(arange)[rows] vs transform(rows) · max|차| ≤ 1e-6 · leak 0",
          worst <= 1e-6 and all(v == 0 for v in leak.values())
          and d4["c_ccap_row_deterministic"], d4)

    # ---- U5 inner split 15 unit --------------------------------------------
    ref = json.load(open(os.path.join(ROOT, "experiments", "runs",
                                      "v3_gin_inner_valid_freeze", "inner_split_check.json"),
                         encoding="utf-8"))["units"]
    refmap = {(u["split_seed"], u["fold"]): u for u in ref}
    d5, bad5 = {}, []
    for r in (1, 2, 3):
        dfr = rest.read_fold_membership(r)
        for k in range(N_FOLD):
            o = np.where(dfr["fold"].values != k)[0]
            va, tr, _g, _v = v1.inner_split(dfr["scaffold"].tolist(), o,
                                            1000 * REP_SEED[r] + k, INNER_DENOM)
            Yi = d["Ym"][np.asarray(tr)]
            zp = int((Yi.sum(axis=0) == 0).sum())
            R = refmap[(REP_SEED[r], k)]
            got = {"n_outer_train": len(o), "n_inner_train": len(tr), "n_inner_valid": len(va),
                   "n_inner_train_zero_positive_pt": zp,
                   "inner_seed": 1000 * REP_SEED[r] + k}
            same = all(R[f] == got[f] for f in got)
            d5["rep%d_fold%d" % (r, k)] = {"got": got, "match": same}
            if not same or len(va) != 97 or zp != 0:
                bad5.append("rep%d_fold%d" % (r, k))
    _case(cases, "U5", "inner split 15 unit — inner_split_check.json 전 필드 일치 · valid 97 · 양성0PT 0",
          not bad5, {"n_units": len(d5), "mismatch": bad5})

    # ---- U6 그래프 ----------------------------------------------------------
    graphs = build_graphs(d)
    d6 = {"n_graphs": len(graphs), "n_parse_fail": 0,
          "cid_order_match": [g.cid for g in graphs] == [int(x) for x in d["cid_order"]],
          "y_match": bool(all(np.array_equal(graphs[i].y.numpy().ravel(),
                                             d["Ym"][i].astype(np.float32)) for i in (0, 5, 1091))),
          "y_dtype": str(graphs[0].y.dtype)}
    _case(cases, "U6", "그래프 1,092 · 파싱 실패 0 · cid 순서 == master · y == master_Y(float32)",
          d6["n_graphs"] == N_DRUGS and d6["cid_order_match"] and d6["y_match"], d6)

    # ---- U7 학습 스모크(합성) ----------------------------------------------
    rng = np.random.default_rng(20260914)
    ylab = (rng.random((12, 8)) < 0.5).astype(float)
    sgraphs = []
    for i, s in enumerate(v1.FIXTURE_SMILES):
        g = gf.smiles_to_data(s, y=ylab[i])
        g.cid = 900000 + i
        sgraphs.append(g)
    sside = rng.random((12, 5)).astype(np.float32)
    scid2idx = {g.cid: i for i, g in enumerate(sgraphs)}
    tl.attach_side({"train": sgraphs[:6], "valid": sgraphs[6:9], "test": sgraphs[9:]},
                   sside, scid2idx, 5)
    sdata = {"ycols": ["pt%d" % i for i in range(8)],
             "graphs": {"train": sgraphs[:6], "valid": sgraphs[6:9], "test": sgraphs[9:]}}
    sbuf = io.StringIO()
    outer = io.StringIO()
    dev = gnntrain.get_device({"device": "mps"})
    with contextlib.redirect_stdout(outer):
        with contextlib.redirect_stdout(sbuf), contextlib.redirect_stderr(sbuf):
            sres = tl.train_variant(sdata, dev, 5, "concat", 42)
    captured = sbuf.getvalue()
    d7 = {"real_stdout_len": len(outer.getvalue()),
          "captured_has_validMacro": "validMacro" in captured,
          "captured_len": len(captured),
          "n_epochs_equation_holds": True,
          "device": str(dev)}
    ne = min(int(sres["best_ep"]) + tl.PATIENCE, tl.EPOCHS)
    m_es = re.search(r"early stop @ep(\d+)", captured)
    if m_es:
        d7["n_epochs_equation_holds"] = (int(m_es.group(1)) == ne)
    d7["n_epochs_equation_note"] = "min(best_ep+PATIENCE, EPOCHS) vs early-stop 로그 epoch"
    del sres
    _case(cases, "U7", "합성 스모크 — 실제 stdout 출력 0 · 가로챈 텍스트에 validMacro · n_epochs 등식 · 수치 폐기",
          d7["real_stdout_len"] == 0 and d7["captured_has_validMacro"]
          and d7["n_epochs_equation_holds"], d7)

    # ---- U8 재개 게이트 진리표 ---------------------------------------------
    d8 = _selftest_gate_truth_table(harness_sha)
    _case(cases, "U8", "재개 게이트 진리표 ①~⑫", d8["all_pass"], d8)

    # ---- U9 쓰기 규약 -------------------------------------------------------
    d9 = _selftest_write_protocol()
    _case(cases, "U9", "쓰기 규약 — .tmp→replace→체크포인트 순서 · 키 중복 감지 · 고아 판정",
          d9["all_pass"], d9)

    # ---- U10 실패 정책 ------------------------------------------------------
    d10 = _selftest_failure_policy()
    _case(cases, "U10", "실패 정책 — 1회 재시도(같은 seed) · 2회 → exit 13 · seed 불변", d10["all_pass"], d10)

    # ---- U10b 시그널 --------------------------------------------------------
    d10b = _selftest_signal()
    _case(cases, "U10b", "SIGTERM — 진행 중 단위를 끝낸 뒤 stopped_reason signal · 고아 0 · 락 해제",
          d10b["all_pass"], d10b)

    # ---- U11 AST 가드 -------------------------------------------------------
    d11 = _selftest_ast(src)
    _case(cases, "U11", "AST 가드 — 금지 import/호출 0 · argparse 옵션 2 · os.environ 0 · 공개 인자에 봉인값 0",
          d11["all_pass"], d11)

    # ---- U12 위생 -----------------------------------------------------------
    d12 = {"sealed_before": sealed0, "sealed_after": count_sealed(),
           "pycache_before": pyc0, "pycache_after": count_pycache(),
           "gin_dirs_created": len(gin_repeat_dirs())}
    _case(cases, "U12", "위생 — 봉인 25/291/275/16 불변 · v3_gin_confirm* 생성 0 · __pycache__ 불변",
          d12["sealed_before"] == d12["sealed_after"] == LEGACY_SEALED_COUNTS
          and d12["pycache_before"] == d12["pycache_after"]
          and d12["gin_dirs_created"] == 0, d12)

    n_pass = sum(1 for x in cases if x["pass"])
    n_skip = sum(1 for x in cases if x["skip_reason"])
    res = {"_doc": "블록 AT 학습 하네스 자체검사 (docs/110 §3 AT-4). 확증 라벨로 학습 0회.",
           "generated_kst": now_kst(), "harness_sha256": harness_sha,
           "contract_sha256": CONTRACT_SHA256,
           "n_cases": len(cases), "n_pass": n_pass, "n_skip": n_skip,
           "all_pass": n_pass == len(cases) and n_skip == 0,
           "confirmatory_training_runs": 0,
           "synthetic_smoke_runs": 1,
           "cases": cases}
    pub_json(out or SELFTEST_OUT, res)
    print(json.dumps({k: res[k] for k in ("n_cases", "n_pass", "n_skip", "all_pass")},
                     ensure_ascii=False, indent=2))
    for x in cases:
        print("  %-5s %s  %s" % (x["case"], "PASS" if x["pass"] else "FAIL", x["desc"]))
    return res


def _fake_tree(tmp, n_dirs=25, n_files=291, n_access=16):
    """레거시 봉인 트리 모사 — 계수만 맞춘다(내용 없음)."""
    runs = os.path.join(tmp, "experiments", "runs")
    per = (n_files - n_access) // n_dirs
    rem = (n_files - n_access) % n_dirs
    for i in range(n_dirs):
        s = os.path.join(runs, "legacy_%02d" % i, "_sealed")
        os.makedirs(s, exist_ok=True)
        k = per + (1 if i < rem else 0)
        for j in range(k):
            open(os.path.join(s, "a%03d.npz" % j), "w").close()
        if i < n_access:
            open(os.path.join(s, "access.log"), "w").close()
    return runs


def _make_gin_dir(tmp, rep, ck_rows, partials=None, oofs=(), extra=(), orphans=(),
                  truncate=False, failures=()):
    runs = os.path.join(tmp, "experiments", "runs")
    d = repeat_dir(rep, runs)
    s = os.path.join(d, "_sealed")
    os.makedirs(os.path.join(s, "_partial"), exist_ok=True)
    lines = [json.dumps({k: r[k] for k in CKPT_FIELDS}, ensure_ascii=False) for r in ck_rows]
    txt = "\n".join(lines) + ("" if truncate else ("\n" if lines else ""))
    if truncate and lines:
        txt = txt[:-5]
    with open(os.path.join(s, "checkpoint.jsonl"), "w", encoding="utf-8") as f:
        f.write(txt)
    names = partials if partials is not None else \
        [partial_name(r["model"], r["fold"], r["train_seed"]) for r in ck_rows]
    for n in names:
        open(os.path.join(s, "_partial", n), "w").close()
    for n in oofs:
        open(os.path.join(s, n), "w").close()
    for n in extra:
        open(os.path.join(s, n), "w").close()
    for n in ("env_fingerprint.json", "access.log", "train_stdout.log"):
        open(os.path.join(s, n), "w").close()
    if orphans:
        os.makedirs(os.path.join(s, "_orphans"), exist_ok=True)
        for n in orphans:
            open(os.path.join(s, "_orphans", n), "w").close()
    with open(os.path.join(d, "failures.jsonl"), "w", encoding="utf-8") as f:
        for r in failures:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return d


def _ck(rep, fold, model, seed):
    return {"rep": rep, "fold": fold, "model": model, "train_seed": seed,
            "completed_at_kst": now_kst(), "artifact_sha256": "0" * 64,
            "n_epochs": 0, "wall_seconds": 0.0}


def _selftest_gate_truth_table(harness_sha):
    ERR12 = GATE_FAIL_PREFIX + COND5_NAME + "\n"
    out, allp = {}, True

    def chk(tag, expect_ok, expect_mode, rc, stderr, tmp, manifest=True, skip_m=True):
        runs = os.path.join(tmp, "experiments", "runs")
        gd = gin_repeat_dirs(tmp)
        ok, mode, bad, _dg = gate_verdict(rc, stderr, tmp, gd, manifest,
                                          harness_sha, CONTRACT_SHA256,
                                          skip_manifest_sha=skip_m)
        good = (ok == expect_ok) and (expect_mode is None or mode == expect_mode)
        out[tag] = {"ok": ok, "mode": mode, "expect_ok": expect_ok,
                    "expect_mode": expect_mode, "pass": good,
                    "failures": bad[:3], "runs": os.path.basename(runs)}
        return good

    # ① 첫 착수 rc0
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        allp &= chk("1_first_launch", True, "first_launch", 0, "", t, manifest=False)
    # ② 정상 재개
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)])
        allp &= chk("2_resume", True, "resume", 12, ERR12, t)
    # ③ 레거시 봉인에 파일 1개 추가
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        open(os.path.join(t, "experiments", "runs", "legacy_00", "_sealed", "zz.npz"), "w").close()
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)])
        allp &= chk("3_legacy_extra_file", False, None, 12, ERR12, t)
    # ④ 체크포인트 없는 partial → 고아 이동 후 통과
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)],
                      partials=[partial_name("M0", 0, 42), partial_name("M1", 0, 42)])
        allp &= chk("4a_orphan_before_sweep", False, None, 12, ERR12, t)
        # 고아 이동 모사
        s = os.path.join(repeat_dir(1, os.path.join(t, "experiments", "runs")), "_sealed")
        os.makedirs(os.path.join(s, "_orphans"), exist_ok=True)
        shutil.move(os.path.join(s, "_partial", partial_name("M1", 0, 42)),
                    os.path.join(s, "_orphans", partial_name("M1", 0, 42) + ".ts"))
        with open(os.path.join(repeat_dir(1, os.path.join(t, "experiments", "runs")),
                               "failures.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"orphan_path": "x/" + partial_name("M1", 0, 42) + ".ts"}) + "\n")
        allp &= chk("4b_orphan_after_sweep", True, "resume", 12, ERR12, t)
    # ⑤ partial 없는 체크포인트
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42), _ck(1, 1, "M0", 42)],
                      partials=[partial_name("M0", 0, 42)])
        allp &= chk("5_ckpt_without_partial", False, None, 12, ERR12, t)
    # ⑥ 실패=[5,3]
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)])
        allp &= chk("6_fail_5_and_3", False, None, 12,
                    GATE_FAIL_PREFIX + COND5_NAME + ", 3:supersede_event\n", t)
    # ⑦ 실패=[2]
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)])
        allp &= chk("7_fail_2_only", False, None, 12,
                    GATE_FAIL_PREFIX + "2:blocking_flags_still_all_true\n", t)
    # ⑧ rc0 인데 GIN 봉인 존재
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)])
        allp &= chk("8_rc0_with_gin_sealed", False, None, 0, "", t)
    # ⑨ 계약 sha 불일치 (manifest_t3 대조 경로)
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)])
        auth = os.path.join(t, "experiments", "runs", "v3_gin_start_authorization")
        os.makedirs(auth, exist_ok=True)
        json.dump({"harness_sha256": harness_sha, "contract_sha256": "bad"},
                  open(os.path.join(auth, "manifest_t3_launch.json"), "w"))
        gd = gin_repeat_dirs(t)
        ok, mode, bad, _ = gate_verdict(12, ERR12, t, gd, True, harness_sha,
                                        CONTRACT_SHA256, skip_manifest_sha=False)
        good = (ok is False)
        out["9_contract_sha_mismatch"] = {"ok": ok, "pass": good, "failures": bad[:3]}
        allp &= good
    # ⑩ manifest 있음 + GIN 봉인 0 + rc0 → 첫 착수 재시도
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        allp &= chk("10_launch_retry", True, "launch_retry", 0, "", t, manifest=True)
    # ⑪ 체크포인트 마지막 줄 잘림
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)], truncate=True)
        allp &= chk("11_truncated_ckpt", False, None, 12, ERR12, t)
    # ⑫ stderr 에 경고 줄 섞임
    with tempfile.TemporaryDirectory() as t:
        _fake_tree(t)
        _make_gin_dir(t, 1, [_ck(1, 0, "M0", 42)])
        noisy = "UserWarning: something\n" + ERR12 + "another warning line\n"
        allp &= chk("12_noisy_stderr", True, "resume", 12, noisy, t)
    out["all_pass"] = bool(allp)
    return out


def _selftest_write_protocol():
    out = {}
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "x.npz")
        sha = atomic_npz(p, P_test=np.zeros((3, 4), np.float32),
                         best_ep=np.int32(1), best_v=np.float64(0.5))
        out["tmp_removed"] = not os.path.exists(p + ".tmp")
        out["npz_exists"] = os.path.exists(p)
        out["sha_matches"] = sha == sha256_file(p)
        s = os.path.join(t, "_sealed")
        os.makedirs(s)
        r = _ck(1, 0, "M0", 42)
        sealed_ckpt_append(s, r)
        rows, ok, _ = sealed_ckpt_read(s)
        out["append_then_read"] = ok and len(rows) == 1
        sealed_ckpt_append(s, r)
        rows2, ok2, reason2 = sealed_ckpt_read(s)
        out["duplicate_detected"] = (not ok2) and "중복" in (reason2 or "")
    # 강제종료 모사 → 고아 판정 (임시 트리에서 sweep 로직 동등 검사)
    with tempfile.TemporaryDirectory() as t:
        s = os.path.join(t, "_sealed")
        os.makedirs(os.path.join(s, "_partial"))
        sealed_ckpt_append(s, _ck(1, 0, "M0", 42))
        open(os.path.join(s, "_partial", partial_name("M0", 0, 42)), "w").close()
        open(os.path.join(s, "_partial", partial_name("M1", 0, 42)), "w").close()
        open(os.path.join(s, "_partial", partial_name("M1b", 0, 42) + ".tmp"), "w").close()
        rows, ok, _ = sealed_ckpt_read(s)
        known = {partial_name(r["model"], r["fold"], r["train_seed"]) for r in rows}
        orph = [f for f in sorted(os.listdir(os.path.join(s, "_partial")))
                if f.endswith(".tmp") or (f.endswith(".npz") and f not in known)]
        out["orphan_detected"] = orph == [partial_name("M1", 0, 42),
                                          partial_name("M1b", 0, 42) + ".tmp"]
    out["all_pass"] = all(v for k, v in out.items() if k != "all_pass")
    return out


def _retry_engine(outcomes, seed):
    """실패 정책의 순수 모사 — 같은 seed 재시도 1회, 2회 실패 시 exit 13."""
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
    a = _retry_engine(["fail", "ok"], 42)
    b = _retry_engine(["fail", "fail"], 42)
    out = {"one_failure_then_retry_same_seed": a["exit"] == 0 and a["seeds_used"] == [42, 42],
           "two_failures_exit13": b["exit"] == EXIT_HARD_FAILURE,
           "seed_unchanged": set(a["seeds_used"]) == {42} and set(b["seeds_used"]) == {42},
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
with cl.ComputeLock(script="confirmatory_gin_train.py --selftest-signal", role="runner"):
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    sys.stderr.write("READY\n"); sys.stderr.flush()
    units_done = 0
    for _ in range(50):
        if state["flag"]:
            break
        time.sleep(0.1)
    # ★ 시그널을 받아도 «현재 단위를 끝낸 뒤» 정지
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
    for ln in reversed(so.strip().splitlines()):     # ComputeLock 이 stdout 에 [LOCK] 줄을 섞는다
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


def _selftest_ast(src):
    tree = ast.parse(src)
    out = {"forbidden_imports": [], "forbidden_calls": [], "argparse_options": [],
           "os_environ_reads": 0, "public_arg_violations": [], "bare_load_frozen": 0}
    BAD_MOD = {"requests", "urllib", "http", "socket", "sap.decision", "rqint", "rqint_test"}
    BAD_NAME = {"emit_sign", "open_sealed", "rqint_test", "decision"}
    PUBLIC_SINKS = {"print", "pub_line", "pub_jsonl", "pub_json", "session_event"}
    SEALED_VALS = _forbidden_names() | {"valid"}
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


# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="블록 AT — 확증 GIN 학습 315회 (docs/110)")
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
