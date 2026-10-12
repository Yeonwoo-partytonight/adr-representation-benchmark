#!/usr/bin/env python3
"""null_main_run.py — 블록 F: §13-4 재배치 null **본런** (2,110 permutation).

성격
----
확증 산출(새 `T_b` 생성). **공개는 개수·해시·시간·메모리·게이트 PASS/FAIL 뿐**이다
(블록 F-0-3 redaction 사전확정 — `docs/33` 항목18). `p_emp`·MC SE·유의 여부·null 분포·
`T_obs`·`T_b`·macro AP·Δ 는 전부 `_sealed/` 에 두고, 개봉은 **성공판정 단계**에서
Holm/BH 다중성과 함께 일괄 수행한다.

구성(동결 — 블록 D 실측 + 블록 F-0 정정)
  워커 **18** · `rf_n_jobs=1` · `moc_n_jobs=1` · `cores_per_worker=1` · spawn ·
  스레드 환경변수 5종 = "1". `ladder_freeze.json` 은 **파일 무수정**, 병렬 인자만
  메모리상 복사본에서 override(통계적 비-파라미터 — D-2/D-3 G1/D-4 로 0-diff 증명).

작업 목록(결정적 · seed 로 완전 결정 · 상태 공유 0)
  primary global      seed 1000 + b,  b=0..999      (1000)
  primary family      seed 11000 + b, b=0..999      (1000)
  family_ALT (마지막)  seed 11000..11099             ( 100)  enters_p_emp=false
  global_ALT (마지막)  seed 1000..1009               (  10)  enters_p_emp=false · 음성대조

게이트
  G0  동결 검증(ladder_freeze·SAP manifest·11모듈·null_generator·파티션 CSV 2종·NULL_B)
  G3  identity permutation → §13-3 sealed `oof_M2b.npz` 와 **바이트 동일**(불일치 원소 0/404,040)
  G1+G2  global seed 1000 을 단독(w=1)·풀(w=18) 각 1회 → `oof_sha256` 동일
  G4  라이브 RAM 게이트 — 10초 주기 전 워커 RSS 합계 샘플, 예산 초과 시 워커 하향(18→12→9)
  sealed 12종 불변(시작·종료) · 전원 감시(60초 주기 `pmset`)

분할 실행
  `STOP` 파일 → 신규 디스패치 중단 · 진행 중 task 완주 · checkpoint 기록 · 정상 종료.
  재개 = 동일 명령 재실행(락 재획득 + 완료 seed skip). 환경 지문 일치 시 G3/G1/G2 축약.
  permutation 은 seed 로 완전 결정되고 상태 공유가 0 이므로 **분할은 산출물에 무영향**이다
  (G1 워커수 불변성으로 증명). 분할은 **실행 로지스틱스**이며 통계 정의·가설·집계·
  성공기준·`NULL_B=1000`·`p_emp` 공식 불변이다.

집계는 **반드시 별도 실행**: `--stage aggregate` (부분집계 물리 차단).

실행
  .venv/bin/python3 v3_Multimodal/src/null_main_run.py                 # 본런(재개 포함)
  .venv/bin/python3 v3_Multimodal/src/null_main_run.py --stage aggregate
  touch experiments/runs/v3_null_MAIN/STOP                             # 정상 정지
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import platform
import re
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

# ── 스레드 환경변수: numpy/BLAS import **이전**에 고정(자식은 spawn 으로 상속) ──────
THREAD_ENV_KEYS = ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                   "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]
for _k in THREAD_ENV_KEYS:
    os.environ[_k] = "1"

import multiprocessing as mp                                            # noqa: E402
import numpy as np                                                     # noqa: E402
import pandas as pd                                                    # noqa: E402
from sklearn.ensemble import RandomForestClassifier                    # noqa: E402
from sklearn.multioutput import MultiOutputClassifier                  # noqa: E402

from ladder_confirmatory import (                                      # noqa: E402
    load_frozen, MorganBlock, CountMaskBlock, SeqBlock, M1bCovariateBlock,
    MODEL_BLOCKS, RF_KW, SEED, PCA_K,
)
from confirmatory_oof_rep1 import gate0_verify, sha256_file            # noqa: E402
from null_timing_probe import (                                        # noqa: E402
    load_target_structure, meanpool_from_mapping, F_EMB_FROZEN,
    REP1_SEALED, REP1_ACCESS_LOG, SPLIT_DIR, EXPECT_M2B_SHA,
)
from sap import null_generator as sap_null                             # noqa: E402
from sap import metrics as sap_metrics                                 # noqa: E402
from sap import consensus as sap_consensus                             # noqa: E402
from compute_lock import ComputeLock, gate_a_load, gate_b_exclusive    # noqa: E402

KST = timezone(timedelta(hours=9))

# ═══════════════════════════════════════════════════════════════════════════
# 동결 상수 (결과 무참조 · 실행 전 고정)
# ═══════════════════════════════════════════════════════════════════════════
N_FOLD = 5
RF_SEED = SEED                                   # 42 = NULL_RF_COMMON_SEED
WORKERS_START = 18
WORKER_LADDER = [18, 12, 9]                      # G4 하향 사다리
RF_N_JOBS = 1
MOC_N_JOBS = 1
CORES_PER_WORKER = 1

B_PRIMARY = 1000
SEED_BASE = {"global": 1000, "family": 11000}
ALT_N = {"family_ALT": 100, "global_ALT": 10}    # paired — primary 와 동일 seed 재사용
AUDIT_KEEP_FIRST_N_OOF = 3                       # 모드별 최초 3개만 full OOF 보관

RESERVED_SEEDS = set(range(201, 206)) | {42}
PROBE1_SEEDS = {9000001, 9000002}
PROBE2_SEEDS = set(range(9000101, 9000119))
MAIN_SEED_NAMESPACE_MAX = 1_000_000              # 참고: family 계열은 11xxx (≤1e6)

RAM_SAMPLE_INTERVAL_S = 10.0
POWER_SAMPLE_INTERVAL_S = 60.0
BATTERY_ABORT_S = 300.0                          # 배터리 5분 연속 → 정상 정지 경로
PROGRESS_INTERVAL_S = 60.0
ROLLING_WINDOW = 50                              # 직전 50개 롤링 처리량
SESSION_EDGE_N = 20                              # F-3b 세션 내 감쇠: 첫/마지막 20개

EXPECT_LADDER_FREEZE_SHA16 = "b885585aefbabb32"
EXPECT_SAP_MANIFEST_SHA16 = "756d485feb4715e9"
EXPECT_NULL_GENERATOR_SHA16 = "90886abce256a130"
EXPECT_PARTITION_SHA256 = "a95e26f9a527e9451ee12f9bccf851e0c8912f57ea7b36920d91d6c7281b0a51"
EXPECT_PARTITION_ALT_SHA256 = "aee6c742c52ce77c0ef50b1c629b3501fa4441fb5a3c0b38cf194b107ca0e1a7"
EXPECT_OOF_ELEMENTS = 404_040                    # 1,092 × 370

# ── 경로 ──────────────────────────────────────────────────────────────────────
PROC = os.path.join(ROOT, "data", "processed")
TM = os.path.join(PROC, "target_mapping")
F_PARTITION = os.path.join(TM, "11_null_family_partition.csv")
F_PARTITION_ALT = os.path.join(TM, "11b_null_family_partition_ALT.csv")
SAP_DIR = os.path.join(HERE, "sap")
SAP_MANIFEST = os.path.join(ROOT, "experiments", "sap", "manifest.json")
CONFIG_FREEZE = os.path.join(ROOT, "v3_Multimodal", "config", "ladder_freeze.json")

RUN_DIR = os.path.join(ROOT, "experiments", "runs", "v3_null_MAIN")
SEALED_DIR = os.path.join(RUN_DIR, "_sealed")
CKPT = os.path.join(SEALED_DIR, "checkpoint.jsonl")
ENV_FP = os.path.join(SEALED_DIR, "env_fingerprint.json")
ACCESS_LOG = os.path.join(SEALED_DIR, "access.log")
NULL_RESULT = os.path.join(SEALED_DIR, "null_result.json")
G3_SEALED = os.path.join(SEALED_DIR, "g3_identity.json")
GATES_FIRST = os.path.join(SEALED_DIR, "gates_first_session.json")
PROGRESS = os.path.join(RUN_DIR, "progress_public.json")
GATES_PUB = os.path.join(RUN_DIR, "gates_public.json")
AGG_PUB = os.path.join(RUN_DIR, "aggregate_public.json")
STOP_FILE = os.path.join(RUN_DIR, "STOP")
RUN_LOG = os.path.join(RUN_DIR, "run.log")

SEALED_GUARD_DIRS = [
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep1_seed201", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep2_seed202", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep3_seed203", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_consensus_rep123", "_sealed"),
]
EXPECT_GUARD_MIN_FILES = 12


# ═══════════════════════════════════════════════════════════════════════════
# 유틸 (공개 로그에 AP·Δ·T_b·p 를 절대 쓰지 않는다)
# ═══════════════════════════════════════════════════════════════════════════
def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    try:
        os.makedirs(RUN_DIR, exist_ok=True)
        with open(RUN_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def native(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=native)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def arr_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def log_machine_read(path_rel, purpose, step="§13-4 null 본런"):
    """sealed 파일 **기계 판독**(사람 노출 0) — `open_sealed`(사람 열람)와 구분."""
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": step,
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    for p in (REP1_ACCESS_LOG, ACCESS_LOG):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def rss_sum_of_descendants(root_pid):
    """전 워커(후손) RSS 합계 — `ps` 판독(외부 의존성 없음). 반환 (bytes, n_procs)."""
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,ppid=,rss="], capture_output=True,
                             text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return None, 0
    rows = []
    for ln in out.splitlines():
        parts = ln.split()
        if len(parts) >= 3:
            try:
                rows.append((int(parts[0]), int(parts[1]), int(parts[2])))
            except ValueError:
                continue
    children = collections.defaultdict(list)
    rss_of = {}
    for pid, ppid, rss in rows:
        children[ppid].append(pid)
        rss_of[pid] = rss
    seen, stack = set(), list(children.get(root_pid, []))
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(children.get(p, []))
    total_kb = sum(rss_of.get(p, 0) for p in seen)
    return total_kb * 1024, len(seen)


def power_state():
    """전원 상태 1회 샘플 — AC/배터리 · powermode · 시각."""
    def _run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
        except (OSError, subprocess.SubprocessError):
            return ""
    ps_out = _run(["pmset", "-g", "ps"])
    g_out = _run(["pmset", "-g"])
    on_ac = "AC Power" in ps_out
    m = re.search(r"powermode\s+(\d+)", g_out)
    return {"ts_kst": now_kst(), "on_ac_power": bool(on_ac),
            "powermode_live": int(m.group(1)) if m else None,
            "raw_pmset_ps_head": ps_out.splitlines()[0] if ps_out.splitlines() else ""}


def guard_snapshot():
    """블록 C sealed 산출물 파일별 sha256 — 값은 열지 않고 지문만."""
    snap = {}
    for d in SEALED_GUARD_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if os.path.isfile(p) and fn != "access.log":
                snap[os.path.relpath(p, ROOT)] = sha256_file(p)
    return snap


# ═══════════════════════════════════════════════════════════════════════════
# 작업 목록 (결정적 · seed 로 완전 결정)
# ═══════════════════════════════════════════════════════════════════════════
def build_task_list():
    """primary global → primary family → family_ALT → global_ALT (ALT 는 마지막)."""
    tasks = []
    for b in range(B_PRIMARY):
        tasks.append({"mode": "global", "seed": SEED_BASE["global"] + b, "enters_p_emp": True})
    for b in range(B_PRIMARY):
        tasks.append({"mode": "family", "seed": SEED_BASE["family"] + b, "enters_p_emp": True})
    for b in range(ALT_N["family_ALT"]):                 # paired — primary 와 동일 seed 재사용
        tasks.append({"mode": "family_ALT", "seed": SEED_BASE["family"] + b, "enters_p_emp": False})
    for b in range(ALT_N["global_ALT"]):
        tasks.append({"mode": "global_ALT", "seed": SEED_BASE["global"] + b, "enters_p_emp": False})
    return tasks


def audit_seed_set(tasks):
    """모드별 **최초 3개** seed — 결정적(작업 순서 기준)이라 재개해도 동일."""
    first = collections.defaultdict(list)
    for t in tasks:
        if len(first[t["mode"]]) < AUDIT_KEEP_FIRST_N_OOF:
            first[t["mode"]].append(t["seed"])
    return {(m, s) for m, ss in first.items() for s in ss}


def seed_isolation_assert(tasks):
    used = {t["seed"] for t in tasks}
    forbidden = RESERVED_SEEDS | PROBE1_SEEDS | PROBE2_SEEDS
    inter = sorted(used & forbidden)
    assert not inter, f"[seed 격리 FAIL] 본실행 seed 가 예약/프로브 seed 와 충돌: {inter}"
    keys = [(t["mode"], t["seed"]) for t in tasks]
    assert len(keys) == len(set(keys)), "[seed 격리 FAIL] 작업 목록에 중복 (mode, seed) 존재"
    assert max(used) <= MAIN_SEED_NAMESPACE_MAX, "본실행 seed 가 namespace 상한 초과"
    return {"n_tasks": len(tasks), "n_unique_seeds": len(used),
            "intersection_with_reserved_and_probe": 0,
            "forbidden_checked": sorted(forbidden), "asserted": True}


# ═══════════════════════════════════════════════════════════════════════════
# 게이트 0 — 동결 검증
# ═══════════════════════════════════════════════════════════════════════════
def gate0_full():
    g0 = gate0_verify()
    assert g0["ladder_freeze_sha16"] == EXPECT_LADDER_FREEZE_SHA16
    assert g0["sap_manifest_sha16"] == EXPECT_SAP_MANIFEST_SHA16

    ng_sha = sha256_file(os.path.join(SAP_DIR, "null_generator.py"))
    assert ng_sha[:16] == EXPECT_NULL_GENERATOR_SHA16, \
        f"null_generator.py sha16 불일치: {ng_sha[:16]}"
    part_sha = sha256_file(F_PARTITION)
    part_alt_sha = sha256_file(F_PARTITION_ALT)
    assert part_sha == EXPECT_PARTITION_SHA256, "파티션 CSV(primary) sha256 불일치"
    assert part_alt_sha == EXPECT_PARTITION_ALT_SHA256, "파티션 CSV(ALT) sha256 불일치"
    assert sap_null.NULL_B == B_PRIMARY == 1000, f"NULL_B={sap_null.NULL_B} != 1000"
    assert sap_null.NULL_RF_COMMON_SEED == RF_SEED == 42, "NULL_RF_COMMON_SEED != 42"

    out = {
        "ladder_freeze_sha16": g0["ladder_freeze_sha16"],
        "sap_manifest_sha16": g0["sap_manifest_sha16"],
        "sap_n_modules_verified": g0["sap_n_modules_verified"],
        "sap_modules_all_match": all(g0["sap_modules_match"].values()),
        "null_generator_sha16": ng_sha[:16],
        "partition_primary_sha256": part_sha,
        "partition_alt_sha256": part_alt_sha,
        "NULL_B": sap_null.NULL_B,
        "NULL_RF_COMMON_SEED": sap_null.NULL_RF_COMMON_SEED,
        "primary_B_m1b_dim": g0["primary_B_m1b_dim"],
        "pass": True,
    }
    logln(f"[G0] PASS — ladder_freeze {out['ladder_freeze_sha16']} · SAP manifest "
          f"{out['sap_manifest_sha16']} · 11모듈 일치={out['sap_modules_all_match']}"
          f"({out['sap_n_modules_verified']}) · null_generator {out['null_generator_sha16']} · "
          f"파티션 CSV 2종 일치 · NULL_B={out['NULL_B']}")
    return out


def env_fingerprint():
    import joblib
    import scipy
    import sklearn
    split_shas = {fn: sha256_file(os.path.join(SPLIT_DIR, fn))
                  for fn in sorted(os.listdir(SPLIT_DIR))
                  if os.path.isfile(os.path.join(SPLIT_DIR, fn))}
    return {
        "python_version": sys.version.split()[0],
        "numpy": np.__version__, "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__, "joblib": joblib.__version__,
        "pandas": pd.__version__,
        "ladder_freeze_sha256": sha256_file(CONFIG_FREEZE),
        "sap_manifest_sha256": sha256_file(SAP_MANIFEST),
        "split_files_sha256": split_shas,
        "partition_sha256": sha256_file(F_PARTITION),
        "partition_alt_sha256": sha256_file(F_PARTITION_ALT),
        "machine": platform.machine(),
        "os": f"{platform.system()} {platform.release()}",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 워커 (모듈 최상위 — spawn 가능해야 함)
# ═══════════════════════════════════════════════════════════════════════════
_W = {}          # 프로세스 로컬 캐시 (setup 1회 → 이후 task 마다 재사용)


def rf_fit_predict_null(Xtr, Ytr, Xeval):
    """`ladder_confirmatory.rf_fit_predict` 와 **동일 절차**. 병렬 인자만 런타임 override.

    `ladder_freeze.json` **파일은 무수정** — 메모리상 dict 복사본의 n_jobs 만 바꾼다.
    통계적 비-파라미터(n_estimators·max_depth·class_weight·random_state 불변)이며
    0-diff 는 D-2/D-3 G1/D-4 및 본런 G3 로 증명한다."""
    kw = dict(RF_KW)
    kw["n_jobs"] = RF_N_JOBS
    clf = MultiOutputClassifier(RandomForestClassifier(random_state=RF_SEED, **kw),
                                n_jobs=MOC_N_JOBS)
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xeval.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xeval)[:, cls.index(1)]
    return P


def _alt_family_structure(ts):
    """ALT 사양 = **이중소속 14 표적을 permutation 에서 제외**(동결 CSV 판독).

    제외 표적은 고정점(mapping[t]=t)으로 두고, 남은 표적으로 family 크기를 재계산한다
    (제외로 |family|<3 이 되면 그 family 도 고정 — 동결 CSV 의 `exchangeable` 과 일치 assert)."""
    alt = pd.read_csv(F_PARTITION_ALT)
    excluded = set(alt.loc[alt["excluded"] == 1, "target_id"].astype(str))
    tbf = {}
    for fam, members in ts["targets_by_family"].items():
        keep = [t for t in members if t not in excluded]
        if keep:
            tbf[fam] = keep
    n_exch_expected = int(alt["exchangeable"].sum())
    return tbf, excluded, n_exch_expected


def _worker_init():
    """프로세스당 1회 — 동결 입력 로드(본실행에서 permutation 수로 상각).

    워커는 `SIGINT` 를 무시한다 — Ctrl-C 는 **부모의 신규 디스패치만** 멈추고
    진행 중 permutation 은 끝까지 완주시켜야 하기 때문이다(F-1b 정상 정지)."""
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        pass
    for k in THREAD_ENV_KEYS:
        assert os.environ.get(k) == "1", f"워커 스레드 환경변수 {k}={os.environ.get(k)} != 1"
    d = load_frozen()
    cid_order = d["cid_order"]
    ts = load_target_structure(cid_order)
    cid2fold = json.load(open(os.path.join(SPLIT_DIR, "folds.json")))
    fold_of_row = np.array([cid2fold[str(int(c))] for c in cid_order], dtype=int)
    tbf_alt, excluded_alt, n_exch_alt = _alt_family_structure(ts)
    _W.update({"d": d, "ts": ts, "fold_of_row": fold_of_row,
               "tbf_alt": tbf_alt, "excluded_alt": excluded_alt, "n_exch_alt": n_exch_alt,
               "pid": os.getpid()})


def _build_mapping(mode, seed):
    ts = _W["ts"]
    if mode == "identity":
        return {u: u for u in ts["unique_targets"]}, {"mode": "identity"}
    if mode in ("global", "global_ALT"):
        # global 은 family partition·tie-break 와 **무관** → ALT 도 동일 연산(음성대조).
        m = sap_null.build_global_permutation(ts["unique_targets"], seed)
        return m, {"mode": mode, "n_exchange_units": len(ts["unique_targets"]),
                   "n_fixed_points": int(sum(1 for k, v in m.items() if k == v))}
    if mode == "family":
        m, rep = sap_null.build_family_permutation(ts["targets_by_family"], seed)
        return m, {"mode": mode, **rep,
                   "n_fixed_points": int(sum(1 for k, v in m.items() if k == v))}
    if mode == "family_ALT":
        m, rep = sap_null.build_family_permutation(_W["tbf_alt"], seed)
        assert rep["n_exchangeable_targets"] == _W["n_exch_alt"], \
            f"ALT 교환가능 표적 수 {rep['n_exchangeable_targets']} != 동결 CSV {_W['n_exch_alt']}"
        for t in _W["excluded_alt"]:                       # 제외 표적 = 고정점
            m[t] = t
        return m, {"mode": mode, **rep, "n_excluded": len(_W["excluded_alt"]),
                   "n_fixed_points": int(sum(1 for k, v in m.items() if k == v))}
    raise ValueError(f"unknown mode {mode}")


def _task(job):
    """1 permutation 완주 — 재배치 → mean-pool → M2b 5-fold OOF → macro AP.

    반환 레코드의 `macro_AP`·`delta` 는 **sealed 전용**이다(공개 파일 기입 금지)."""
    if not _W:
        _worker_init()
    mode, seed = job["mode"], int(job["seed"])
    t0 = time.perf_counter()
    ru0 = resource.getrusage(resource.RUSAGE_SELF)
    cpu0 = ru0.ru_utime + ru0.ru_stime

    d, ts, fold_of_row = _W["d"], _W["ts"], _W["fold_of_row"]
    cid_order, Y = d["cid_order"], d["Ym"]
    N, K = len(cid_order), Y.shape[1]

    mapping, rep = _build_mapping(mode, seed)
    pres = sap_null.assert_preservation(ts["cid2targets"], ts["target_emb"], mapping, cid_order)
    emb_p, mask_p, ntgt_p = meanpool_from_mapping(ts, cid_order, mapping)
    assert np.array_equal(mask_p, d["mask"]) and np.array_equal(ntgt_p, d["ntgt"]), \
        "재배치가 mask/degree 를 바꿈(보존 위반)"
    if mode == "identity":
        assert np.array_equal(emb_p.view(np.uint8), np.load(F_EMB_FROZEN).view(np.uint8)), \
            "identity mean-pool 이 동결 npy 와 바이트 불일치"

    blocks = {"B0": MorganBlock(d["X"]["smiles_canonical"].tolist(), cid_order),
              "B1": CountMaskBlock(d["ntgt"], d["mask"]),
              "B_seq": SeqBlock(emb_p, d["mask"], pca_k=PCA_K),
              "B_m1b": M1bCovariateBlock(d["cov_by_cid"], cid_order,
                                         include_pchembl=False, name="B_m1b")}
    assert blocks["B_m1b"].dim == 10, f"primary B_m1b dim={blocks['B_m1b'].dim} != 10"
    assert MODEL_BLOCKS["M2b"] == ["B0", "B1", "B_m1b", "B_seq"]

    oof = np.full((N, K), np.nan, dtype=np.float64)
    fold_wall = []
    for kf in range(N_FOLD):
        tf0 = time.perf_counter()
        te = np.where(fold_of_row == kf)[0]
        tr = np.where(fold_of_row != kf)[0]
        for b in blocks.values():
            b.fit(tr)                                  # permutation·fold 마다 PCA 재적합
        expect = np.zeros(N, dtype=bool)
        expect[tr] = True
        expect &= d["mask"].astype(bool)
        assert np.array_equal(blocks["B_seq"]._fit_rows_mask, expect), \
            f"[fold {kf}] B_seq fit 모집단 != train∩매핑"
        for b in ("B0", "B1", "B_seq", "B_m1b"):
            assert blocks[b].leakage_assert(tr)["leak_rows"] == 0, f"[fold {kf}] {b} leak_rows != 0"
        Xtr = np.hstack([blocks[b].transform(tr) for b in MODEL_BLOCKS["M2b"]]).astype(np.float32)
        Xte = np.hstack([blocks[b].transform(te) for b in MODEL_BLOCKS["M2b"]]).astype(np.float32)
        oof[te] = rf_fit_predict_null(Xtr, Y[tr], Xte)
        fold_wall.append(time.perf_counter() - tf0)
        del Xtr, Xte
    assert not np.isnan(oof).any(), "OOF 미완성(NaN)"

    # T = 관측 M2b macro AP (rep1 확증과 **동일 절차**: eligible = 370 PT 전체, 단일반복 consensus)
    ap = sap_metrics.macro_ap(Y, sap_consensus.build_consensus([oof]), np.arange(K))["macro_ap"]

    ru1 = resource.getrusage(resource.RUSAGE_SELF)
    peak = int(ru1.ru_maxrss) if sys.platform == "darwin" else int(ru1.ru_maxrss * 1024)
    rec = {"mode": mode, "seed": seed,
           "oof_sha256": arr_sha(oof),
           "macro_AP": float(ap),
           "delta": float(ap - job["ap_m1b"]),
           "wall_s": time.perf_counter() - t0,
           "cpu_s": (ru1.ru_utime + ru1.ru_stime) - cpu0,
           "peak_rss": peak,
           "ts_kst": now_kst(),
           "enters_p_emp": bool(job["enters_p_emp"]),
           "worker_pid": os.getpid(),
           "fold_wall_s": fold_wall,
           "permutation_report": rep,
           "n_shared_target_checks": pres["n_shared_target_checks"]}
    if job.get("return_oof"):
        rec["_oof"] = oof
    return rec


# ═══════════════════════════════════════════════════════════════════════════
# 체크포인트 (부모 = 단일 writer · append-only · fsync)
# ═══════════════════════════════════════════════════════════════════════════
CKPT_FIELDS = ["mode", "seed", "oof_sha256", "macro_AP", "delta", "wall_s", "cpu_s",
               "peak_rss", "ts_kst", "enters_p_emp", "session_seq", "workers"]


def ckpt_append(rec, session_seq, workers):
    os.makedirs(SEALED_DIR, exist_ok=True)
    row = {k: rec.get(k) for k in CKPT_FIELDS if k not in ("session_seq", "workers")}
    row["session_seq"] = session_seq
    row["workers"] = workers
    with open(CKPT, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=native) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return row


def ckpt_load():
    """유효 접두만 판독(마지막 줄이 잘렸으면 그 줄은 버린다 — append-only 보존)."""
    if not os.path.exists(CKPT):
        return [], 0
    rows, bad_tail = [], 0
    with open(CKPT, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                bad_tail = 1
            else:
                raise AssertionError(f"[checkpoint] {i + 1}번째 줄 파손 — 수동 확인 필요")
    keys = [(r["mode"], int(r["seed"])) for r in rows]
    dup = [k for k, c in collections.Counter(keys).items() if c > 1]
    assert not dup, f"[checkpoint] 중복 (mode, seed) 검출 {dup[:5]} — 즉시 중단"
    return rows, bad_tail


# ═══════════════════════════════════════════════════════════════════════════
# 감시 스레드 — RAM(10s) · 전원(60s)
# ═══════════════════════════════════════════════════════════════════════════
class Watchers:
    def __init__(self, budget_gib):
        self.budget_bytes = budget_gib * (1024 ** 3)
        self.budget_gib = budget_gib
        self.stop_evt = threading.Event()
        self.lock = threading.Lock()
        self.ram_peak = 0
        self.ram_samples = 0
        self.ram_exceeded = False
        self.ram_exceed_obs = None
        self.ram_exceed_ts = None
        self.power_samples = 0
        self.power_excursion = 0
        self.power_last = None
        self.battery_since = None
        self.battery_sustained = False
        self._threads = []

    def start(self):
        for fn in (self._ram_loop, self._power_loop):
            t = threading.Thread(target=fn, daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def stop(self):
        self.stop_evt.set()
        for t in self._threads:
            t.join(timeout=5)

    def _ram_loop(self):
        while not self.stop_evt.wait(RAM_SAMPLE_INTERVAL_S):
            total, n = rss_sum_of_descendants(os.getpid())
            if total is None:
                continue
            with self.lock:
                self.ram_samples += 1
                if total > self.ram_peak:
                    self.ram_peak = total
                if total > self.budget_bytes and not self.ram_exceeded:
                    self.ram_exceeded = True
                    self.ram_exceed_obs = total
                    self.ram_exceed_ts = now_kst()
                    logln(f"[G4] ❗ RAM 예산 초과 관측 — 워커 합계 {total / 1024 ** 3:.2f} GiB > "
                          f"{self.budget_gib} GiB (워커 프로세스 {n}개). 워커 수 하향 절차 진입.")

    def _power_loop(self):
        while not self.stop_evt.wait(POWER_SAMPLE_INTERVAL_S):
            st = power_state()
            with self.lock:
                self.power_samples += 1
                self.power_last = st
                bad = (not st["on_ac_power"]) or (st["powermode_live"] not in (0, None))
                if bad:
                    self.power_excursion += 1
                    if not st["on_ac_power"]:
                        if self.battery_since is None:
                            self.battery_since = time.time()
                            logln("[전원] ❗ AC 이탈 관측 — wall-clock 무효 구간 시작"
                                  "(바이트 동일성은 무영향). 5분 연속 시 정상 정지.")
                        elif (time.time() - self.battery_since >= BATTERY_ABORT_S
                                and not self.battery_sustained):
                            self.battery_sustained = True
                            logln(f"[전원] ❗ 배터리 {BATTERY_ABORT_S / 60:.0f}분 연속 — "
                                  f"정상 정지 경로로 전환(진행 중 task 완주 후 종료).")
                    if st["powermode_live"] not in (0, None):
                        logln(f"[전원] powermode={st['powermode_live']} 관측 "
                              f"(excursion 누계 {self.power_excursion})")
                else:
                    if self.battery_since is not None:
                        logln("[전원] AC 복귀 관측 — 배터리 연속 카운터 리셋")
                    self.battery_since = None

    def clear_exceeded(self):
        """워커 수 하향 후 게이트 재무장(관측값·시각은 보존)."""
        with self.lock:
            self.ram_exceeded = False

    def snapshot(self):
        with self.lock:
            return {"ram_peak_bytes": self.ram_peak,
                    "ram_peak_gib": self.ram_peak / 1024 ** 3,
                    "ram_samples": self.ram_samples,
                    "ram_budget_gib": self.budget_gib,
                    "ram_exceeded": self.ram_exceeded,
                    "ram_exceed_observed_gib": (self.ram_exceed_obs / 1024 ** 3
                                                if self.ram_exceed_obs else None),
                    "ram_exceed_ts_kst": self.ram_exceed_ts,
                    "power_samples": self.power_samples,
                    "power_excursion": self.power_excursion,
                    "power_last": self.power_last,
                    "battery_sustained_abort": self.battery_sustained}


# ═══════════════════════════════════════════════════════════════════════════
# 정지 스위치
# ═══════════════════════════════════════════════════════════════════════════
_SIGNAL_STOP = {"requested": False, "reason": None}
_SESSION = {"start_ts": None, "cid_order": None, "t0_perf": None}


def _install_stop_signals():
    def handler(signum, frame):                                     # noqa: ARG001
        if not _SIGNAL_STOP["requested"]:
            _SIGNAL_STOP["requested"] = True
            _SIGNAL_STOP["reason"] = f"signal_{signal.Signals(signum).name}"
            print(f"\n[STOP] {signal.Signals(signum).name} 수신 — 신규 디스패치 중단, "
                  f"진행 중 task 완주 후 정상 종료합니다(즉시 kill 아님).", flush=True)
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, handler)


def stop_requested(watch):
    if _SIGNAL_STOP["requested"]:
        return _SIGNAL_STOP["reason"]
    if os.path.exists(STOP_FILE):
        return "stop_file"
    if watch.snapshot()["battery_sustained_abort"]:
        return "battery_sustained_5min"
    return None


# ═══════════════════════════════════════════════════════════════════════════
# 단독(w=1) 1 task 실행 — G3 identity · G1 단독 기준
# ═══════════════════════════════════════════════════════════════════════════
def run_solo(job):
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=1, initializer=_worker_init) as pool:
        return pool.apply(_task, (job,))


# ═══════════════════════════════════════════════════════════════════════════
# 본런
# ═══════════════════════════════════════════════════════════════════════════
def stage_run():
    t_session0 = time.perf_counter()
    os.makedirs(RUN_DIR, exist_ok=True)
    os.makedirs(SEALED_DIR, exist_ok=True)
    _install_stop_signals()
    _SESSION["start_ts"] = now_kst()
    _SESSION["t0_perf"] = time.perf_counter()

    logln("=" * 78)
    logln("[블록 F] §13-4 재배치 null **본런** 시작 — 공개는 개수·해시·시간·메모리·PASS/FAIL 뿐")
    logln("[redaction] p_emp·MC SE·유의 여부·null 분포·T_obs·T_b·AP·Δ 는 전부 _sealed/ "
          "(개봉 = 성공판정 단계 일괄 · docs/33 항목18)")

    # ── caffeinate 로 감싼다(우리 pid 를 기다리는 형태) ──────────────────────
    caff = None
    try:
        caff = subprocess.Popen(["caffeinate", "-dimsu", "-w", str(os.getpid())])
        logln(f"[caffeinate] -dimsu -w {os.getpid()} 기동(pid={caff.pid})")
    except OSError as e:
        logln(f"[caffeinate] 기동 실패({e}) — 절전 진입 위험. 계속 진행하되 기록한다.")

    # ── STOP 파일은 **재개 시 드라이버가 삭제**(정지 상태 잔류 방지) ──────────
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)
        logln("[STOP] 이전 세션의 STOP 파일 삭제(재개) — 정지하려면 다시 touch 하십시오.")

    # ── G-IDLE A(1회) + B(시작) ───────────────────────────────────────────────
    ga = gate_a_load("null-main-run entry")
    gb_start = gate_b_exclusive("null-main-run start")

    # ── G0 · sealed 12종 · 환경 지문 ─────────────────────────────────────────
    g0 = gate0_full()
    guard_start = guard_snapshot()
    assert len(guard_start) >= EXPECT_GUARD_MIN_FILES, \
        f"sealed 보호 대상 {len(guard_start)}종 < {EXPECT_GUARD_MIN_FILES}"
    logln(f"[sealed guard] 시작 스냅샷 {len(guard_start)}종 기록")

    fp_now = env_fingerprint()
    fp_prev = json.load(open(ENV_FP)) if os.path.exists(ENV_FP) else None
    fp_match = (fp_prev == fp_now) if fp_prev else None
    fp_diff = ([] if fp_match or fp_prev is None
               else sorted(k for k in set(fp_prev) | set(fp_now)
                           if fp_prev.get(k) != fp_now.get(k)))

    tasks_all = build_task_list()
    iso = seed_isolation_assert(tasks_all)
    audit_keys = audit_seed_set(tasks_all)
    logln(f"[seed 격리] PASS — 총 {iso['n_tasks']} task · 예약/프로브 seed 와 교집합 0")

    done_rows, bad_tail = ckpt_load()
    done_keys = {(r["mode"], int(r["seed"])) for r in done_rows}
    if bad_tail:
        logln("[checkpoint] 마지막 줄이 불완전 — 유효 접두까지만 인수(원문 무수정)")
    remaining = [t for t in tasks_all if (t["mode"], t["seed"]) not in done_keys]
    session_seq = (max((r.get("session_seq", 0) for r in done_rows), default=0) + 1)
    is_resume = bool(done_rows)

    # ── M1b 재사용(기계 판독 — 사람 노출 0) ──────────────────────────────────
    log_machine_read(os.path.relpath(os.path.join(REP1_SEALED, "oof_M1b.npz"), ROOT),
                     "null M1b reuse (permutation 불변 상수항)")
    d0 = load_frozen()
    Y0 = d0["Ym"]
    _SESSION["cid_order"] = np.array([int(c) for c in d0["cid_order"]])
    with np.load(os.path.join(REP1_SEALED, "oof_M1b.npz")) as z:
        _oof_m1b = z["oof"]
    ap_m1b = float(sap_metrics.macro_ap(Y0, sap_consensus.build_consensus([_oof_m1b]),
                                        np.arange(Y0.shape[1]))["macro_ap"])
    del _oof_m1b
    logln("[M1b] §13-3 sealed oof_M1b.npz 1회 기계 판독 — 전 permutation 재사용(값 미출력)")

    for t in tasks_all:
        t["ap_m1b"] = ap_m1b
        t["return_oof"] = (t["mode"], t["seed"]) in audit_keys

    # ── 게이트 요약(공개) 준비 ────────────────────────────────────────────────
    gates = {"ts_kst": now_kst(), "session_seq": session_seq, "resume": is_resume,
             "G_IDLE_A": ga, "G_IDLE_B_start": gb_start, "G0": g0,
             "sealed_guard_n_files_start": len(guard_start),
             "env_fingerprint_match": fp_match, "env_fingerprint_diff_keys": fp_diff,
             "seed_isolation": iso}

    # ── G3 / G1 / G2 — 첫 실행이거나 지문 불일치면 반드시 실행 ────────────────
    skip_heavy_gates = bool(is_resume and fp_match)
    if skip_heavy_gates:
        # 인용 원본은 **첫 실행 결과를 고정 보관한 파일**(중첩 인용 방지).
        assert os.path.exists(GATES_FIRST), \
            "[게이트 축약 불가] 첫 실행 게이트 기록(gates_first_session.json) 부재 — G3 재실행 필요"
        first = json.load(open(GATES_FIRST))
        assert first.get("G3_identity", {}).get("verdict") == "PASS", "첫 실행 G3 가 PASS 아님"
        gates["G3_identity"] = {"skipped": True, "reason": "재개 + 환경 지문 완전 일치",
                                "cited_from_first_session": first["G3_identity"]}
        gates["G1_G2_concurrency"] = {"skipped": True, "reason": "재개 + 환경 지문 완전 일치",
                                      "cited_from_first_session": first.get("G1_G2_concurrency")}
        g3c = first["G3_identity"]
        logln(f"[게이트 축약] 재개 + 환경 지문 완전 일치 → G3 identity · G1/G2 재실행 생략 "
              f"(첫 실행 인용: 불일치 원소 {g3c['n_elements_differing']}/"
              f"{g3c['n_elements_total']} · {g3c['ts_kst']})")
    else:
        if is_resume and not fp_match:
            logln(f"[게이트 축약 불가] 환경 지문 불일치 항목 {fp_diff} → G3 identity 재실행")

        # G3 identity — 단독 1회
        logln("[G3] identity permutation 단독 실행 시작 — §13-3 sealed oof_M2b.npz 와 바이트 동일해야 함")
        gb_g3 = gate_b_exclusive("G3 identity 직전")
        rec_id = run_solo({"mode": "identity", "seed": 0, "ap_m1b": ap_m1b,
                           "enters_p_emp": False, "return_oof": True})
        oof_id = rec_id.pop("_oof")
        log_machine_read(os.path.relpath(os.path.join(REP1_SEALED, "oof_M2b.npz"), ROOT),
                         "identity control byte-comparison")
        with np.load(os.path.join(REP1_SEALED, "oof_M2b.npz")) as z:
            oof_sealed = z["oof"]
        n_diff = int(np.sum(oof_sealed != oof_id))
        n_elem = int(oof_sealed.size)
        sha_match = (arr_sha(oof_id) == arr_sha(oof_sealed))
        g3 = {"n_elements_differing": n_diff, "n_elements_total": n_elem,
              "array_bitwise_match": bool(sha_match),
              "sealed_file_sha256_expected": EXPECT_M2B_SHA,
              "sealed_file_sha256_live": sha256_file(os.path.join(REP1_SEALED, "oof_M2b.npz")),
              "wall_s": rec_id["wall_s"], "ts_kst": now_kst(),
              "verdict": "PASS" if (n_diff == 0 and sha_match) else "FAIL",
              "gate_b": gb_g3}
        assert n_elem == EXPECT_OOF_ELEMENTS, f"OOF 원소 수 {n_elem} != {EXPECT_OOF_ELEMENTS}"
        gates["G3_identity"] = g3
        dump_json(G3_SEALED, {"_warning": "SEALED — identity control 상세",
                              **g3, "identity_record": {k: v for k, v in rec_id.items()}})
        logln(f"[G3] identity control = **{g3['verdict']}** "
              f"(불일치 원소 {n_diff}/{n_elem} · 배열 sha 일치={sha_match}) | {rec_id['wall_s']:.1f}s")
        del oof_id, oof_sealed
        if g3["verdict"] != "PASS":
            dump_json(GATES_PUB, gates)
            logln("[G3] ❌ FAIL — 즉시 중단. null 하네스가 동결 파이프라인과 불일치.")
            sys.exit(3)

        # G1 단독 기준 — global seed 1000 을 w=1 로 1회
        logln("[G1] global seed 1000 단독(w=1) 실행 — 풀(w=18) 첫 task 와 oof_sha256 비교 예정")
        solo_job = dict(tasks_all[0])
        solo_job["return_oof"] = False
        rec_solo = run_solo(solo_job)
        gates["G1_G2_concurrency"] = {"solo_workers": 1, "solo_oof_sha256": rec_solo["oof_sha256"],
                                      "solo_wall_s": rec_solo["wall_s"],
                                      "pool_oof_sha256": None, "match": None,
                                      "note": "풀 첫 task 수신 시 비교·확정. 중복 checkpoint 금지."}
        logln(f"[G1] 단독 결과 확보 (oof_sha256 {rec_solo['oof_sha256'][:16]}…) | "
              f"{rec_solo['wall_s']:.1f}s — checkpoint 미기록(풀 결과 1건만 기록)")
        # 첫 실행 게이트 결과를 **고정 보관**(재개 시 인용 원본 — 중첩 인용 방지)
        dump_json(GATES_FIRST, {"_note": "첫 실행 게이트 원본 — 재개 세션이 인용한다(무수정).",
                                "ts_kst": now_kst(), "env_fingerprint": fp_now,
                                "G3_identity": gates["G3_identity"],
                                "G1_G2_concurrency": gates["G1_G2_concurrency"]})

    dump_json(ENV_FP, fp_now)
    dump_json(GATES_PUB, gates)

    # ── 사용자 안내(시작) ────────────────────────────────────────────────────
    n_total, n_done, n_left = len(tasks_all), len(done_keys), len(remaining)
    prev_rate = _rolling_rate_from_rows(done_rows)
    eta_h = (n_left / prev_rate) if prev_rate else None
    print("\n" + "─" * 78, flush=True)
    print(f"총 {n_total:,} permutation · 완주 {n_done:,} · 남은 {n_left:,}개"
          + (f" · 현재 처리량 기준 예상 잔여 {eta_h:.1f}h" if eta_h else " · 예상 잔여 = 첫 라운드 후 산출"),
          flush=True)
    print(f"중단하려면  touch {os.path.relpath(STOP_FILE, ROOT)}", flush=True)
    print("─" * 78 + "\n", flush=True)
    logln(f"[본런] 총 {n_total} · 완주 {n_done} · 남은 {n_left} · 세션 #{session_seq} 시작")

    if not remaining:
        logln("[본런] 남은 task 0 — 실행할 것이 없습니다. 집계는 --stage aggregate 로 별도 실행하십시오.")
        _finish_session(gates, guard_start, session_seq, t_session0, 0, "nothing_to_do",
                        WORKERS_START, None, caff)
        return

    # ── RAM 예산 판독(블록 F-0-2 정정치 기준) ────────────────────────────────
    pub_path = os.path.join(ROOT, "experiments", "runs", "v3_null_probe2_compute",
                            "compute_public.json")
    budget_gib = json.load(open(pub_path))["hardware"]["ram_budget_gib"]
    watch = Watchers(budget_gib).start()
    logln(f"[G4] 라이브 RAM 게이트 가동 — 예산 {budget_gib} GiB · {RAM_SAMPLE_INTERVAL_S:.0f}초 주기 샘플")
    logln(f"[전원] 감시 가동 — {POWER_SAMPLE_INTERVAL_S:.0f}초 주기 pmset 샘플 "
          f"(배터리 {BATTERY_ABORT_S / 60:.0f}분 연속 시 정상 정지)")

    workers = WORKERS_START
    worker_changes = []
    completed_this_session = 0
    stop_reason = None
    crashed = None

    while remaining and stop_reason is None:
        n_before_pool = completed_this_session
        stop_reason, crashed, n_done_pool = _pool_session(
            remaining, workers, watch, session_seq, gates, guard_start, budget_gib)
        completed_this_session += n_done_pool
        done_rows, _ = ckpt_load()
        done_keys = {(r["mode"], int(r["seed"])) for r in done_rows}
        remaining = [t for t in tasks_all if (t["mode"], t["seed"]) not in done_keys]
        if crashed:
            break
        if stop_reason == "ram_gate" and remaining:
            idx = WORKER_LADDER.index(workers) if workers in WORKER_LADDER else 0
            if idx + 1 < len(WORKER_LADDER):
                new_w = WORKER_LADDER[idx + 1]
                snap = watch.snapshot()
                worker_changes.append({
                    "ts_kst": now_kst(), "from": workers, "to": new_w,
                    "reason": "G4 RAM 예산 초과 관측",
                    "observed_sum_peak_rss_gib": snap["ram_exceed_observed_gib"],
                    "budget_gib": budget_gib,
                    "statistical_neutrality": "G1 워커수 불변성으로 증명된 축 — 산출물 무영향"})
                logln(f"[G4] 워커 수 하향 {workers} → {new_w} "
                      f"(관측 {snap['ram_exceed_observed_gib']:.2f} GiB > {budget_gib} GiB). 재개.")
                workers = new_w
                watch.clear_exceeded()
                stop_reason = None
                continue
            logln("[G4] ❗ 하향 사다리 소진 — 정상 정지합니다.")
            stop_reason = "ram_gate_ladder_exhausted"
        _ = n_before_pool

    watch.stop()
    graceful = stop_reason in (None, "stop_file", "signal_SIGINT", "signal_SIGTERM",
                               "battery_sustained_5min", "ram_gate_ladder_exhausted", "done")
    if crashed:
        _isolate_crash(crashed)
    _finish_session(gates, guard_start, session_seq, t_session0, completed_this_session,
                    stop_reason or "done", workers, watch, caff, worker_changes, crashed)

    print("\n" + "─" * 78, flush=True)
    if crashed:
        print(f"❌ 비정상 종료({crashed['type']}). checkpoint 는 보존되었습니다. "
              f"부분 산출물은 _crashed_*/ 로 격리했습니다.", flush=True)
        print("재개는 동일 명령 재실행.", flush=True)
        print("─" * 78 + "\n", flush=True)
        sys.exit(4)
    n_now = len(ckpt_load()[0])
    print(f"정상 정지. 완주 {n_now:,}/{n_total:,}. 재개는 동일 명령 재실행.", flush=True)
    if n_now >= n_total:
        print("전량 완주 — 집계는 반드시 별도 실행:", flush=True)
        print("  .venv/bin/python3 v3_Multimodal/src/null_main_run.py --stage aggregate", flush=True)
    print("─" * 78 + "\n", flush=True)
    _ = graceful


def _pool_session(remaining, workers, watch, session_seq, gates, guard_start, budget_gib,
                  task_fn=None, init_fn=None):
    """워커 수 고정 1구간. 반환 (stop_reason|None, crashed|None, 완주 수).

    `task_fn`/`init_fn` 은 **디스패치 기계장치 테스트 전용** 훅이다(기본 = 실제 `_task`).
    본런 경로에서는 절대 지정하지 않는다.

    **task 단위 디스패치**(apply_async 윈도) — 정적 분할이 아닌 이유는 부하 균형이 아니라
    (편차 3.3% 로 무관) **크래시·정지 재시작의 정확성** 때문이다: 완료 단위가 permutation
    1개와 정확히 일치하므로 버려지는 계산이 없다."""
    ctx = mp.get_context("spawn")
    task_fn = task_fn or _task
    init_fn = init_fn or _worker_init
    logln(f"[풀] 워커 {workers} × (RF n_jobs={RF_N_JOBS}, MOC n_jobs={MOC_N_JOBS}) · spawn · "
          f"스레드 환경변수 5종=1 · 남은 {len(remaining)} task")
    n_done = 0
    stop_reason = None
    crashed = None
    completions = collections.deque(maxlen=ROLLING_WINDOW)
    t_last_progress = 0.0
    g1 = gates.get("G1_G2_concurrency") or {}
    need_g1_compare = bool(g1.get("solo_oof_sha256") and g1.get("match") is None)

    pool = ctx.Pool(processes=workers, initializer=init_fn)
    try:
        it = iter(remaining)
        inflight = {}
        while True:
            while len(inflight) < workers and stop_reason is None:
                job = next(it, None)
                if job is None:
                    break
                inflight[pool.apply_async(task_fn, (job,))] = job
            if not inflight:
                break
            ready = [r for r in list(inflight) if r.ready()]
            if not ready:
                time.sleep(0.5)
                if time.perf_counter() - t_last_progress >= PROGRESS_INTERVAL_S:
                    _write_progress(gates, watch, session_seq, workers, completions,
                                    n_done, budget_gib, stop_reason)
                    t_last_progress = time.perf_counter()
                continue
            for r in ready:
                job = inflight.pop(r)
                try:
                    rec = r.get()
                except Exception as e:                                  # noqa: BLE001
                    crashed = {"type": type(e).__name__, "message": str(e)[:500],
                               "mode": job["mode"], "seed": job["seed"], "ts_kst": now_kst()}
                    logln(f"[크래시] {job['mode']} seed {job['seed']} — {type(e).__name__}: "
                          f"{str(e)[:200]}")
                    stop_reason = "crash"
                    break
                oof = rec.pop("_oof", None)
                if oof is not None:
                    p = os.path.join(SEALED_DIR, f"oof_M2b_{rec['mode']}_seed{rec['seed']}.npz")
                    if not os.path.exists(p):          # 감사 예외 = 모드별 최초 3개만
                        np.savez_compressed(p, oof=oof, cid=_SESSION["cid_order"])
                    del oof
                if need_g1_compare and rec["mode"] == "global" and rec["seed"] == 1000:
                    same = (rec["oof_sha256"] == g1["solo_oof_sha256"])
                    g1["pool_oof_sha256"] = rec["oof_sha256"]
                    g1["pool_workers"] = workers
                    g1["match"] = bool(same)
                    g1["verdict"] = "PASS" if same else "FAIL"
                    gates["G1_G2_concurrency"] = g1
                    dump_json(GATES_PUB, gates)
                    if os.path.exists(GATES_FIRST):     # 인용 원본에도 판정 확정
                        gf = json.load(open(GATES_FIRST))
                        gf["G1_G2_concurrency"] = g1
                        dump_json(GATES_FIRST, gf)
                    need_g1_compare = False
                    logln(f"[G1+G2] 단독(w=1) vs 풀(w={workers}) oof_sha256 동일 = **{same}** "
                          f"— 중복 방지를 위해 풀 결과 1건만 checkpoint 기록")
                    if not same:
                        logln("[G1+G2] ❌ FAIL — 프로세스 병렬 경로 폐기 후 중단.")
                        stop_reason = "G1_FAIL"
                        crashed = {"type": "G1ConcurrencyMismatch",
                                   "message": "워커 수에 따라 예측 sha256 상이", "ts_kst": now_kst()}
                        break
                ckpt_append(rec, session_seq, workers)
                completions.append(rec["wall_s"])
                n_done += 1
                if n_done % 25 == 0 or n_done == 1:
                    snap = watch.snapshot()
                    _r = _rate(completions, workers)
                    _rtxt = (f"{_r:.1f}" if _r else
                             f"{_rate_session(n_done, _SESSION['t0_perf']):.1f}(세션평균)")
                    logln(f"[진행] 세션 완주 {n_done} · 처리량 "
                          f"{_rtxt} perm/h · 워커 합계 peak RSS "
                          f"{snap['ram_peak_gib']:.2f}/{budget_gib} GiB · "
                          f"power_excursion {snap['power_excursion']}")
            if stop_reason is None:
                stop_reason = stop_requested(watch)
                if stop_reason:
                    logln(f"[정지] 사유={stop_reason} — 신규 디스패치 중단, 진행 중 "
                          f"{len(inflight)}개 완주 대기(최대 ≈23분)")
                elif watch.snapshot()["ram_exceeded"]:
                    stop_reason = "ram_gate"
                    logln(f"[G4] 예산 초과 → 신규 디스패치 중단, 진행 중 {len(inflight)}개 완주 대기")
            if time.perf_counter() - t_last_progress >= PROGRESS_INTERVAL_S:
                _write_progress(gates, watch, session_seq, workers, completions, n_done,
                                budget_gib, stop_reason)
                t_last_progress = time.perf_counter()
            if stop_reason == "crash" or stop_reason == "G1_FAIL":
                break
        if stop_reason in ("crash", "G1_FAIL"):
            pool.terminate()
        else:
            pool.close()
        pool.join()
    finally:
        try:
            pool.terminate()
        except Exception:                                               # noqa: BLE001
            pass
    _write_progress(gates, watch, session_seq, workers, completions, n_done, budget_gib,
                    stop_reason)
    return stop_reason, crashed, n_done


def _rate(walls, workers):
    """직전 N개 롤링 처리량(perm/h) = **`w / wall_max`** — 블록 D 동결 정의 그대로.

    도착 **시각** 기반 `(N-1)/span` 은 이 작업부하에서 쓸 수 없다: 18 워커가 함께
    디스패치돼 수 초 내에 같이 끝나므로 윈도 경계가 배치 중간에 걸리면 값이 크게
    왜곡된다(1배치만 덮으면 배치 내부 산포를 재어 2,265 perm/h, 2배치를 덮어도
    간격 1개에 구간 35개를 세어 95.8 — 실측 48 대비 2배). permutation **단가**
    기반은 배치 정렬과 무관하므로 그 함정이 없다.

    `wall_max`(마지막 완료) 기준인 것은 블록 D 보정(`compute_public.json`
    `throughput_definition`)이 평균·중앙값 기반 계산을 금지했기 때문이다 — 워커 간
    불균등을 낙관적으로 상쇄하지 않는다."""
    if not walls:
        return None
    return workers / max(walls) * 3600.0


def _rate_session(n_done_session, t0_perf):
    """세션 평균 처리량(perm/h) — 풀 기동·배치 대기까지 포함한 **정직한 하한**."""
    el = time.perf_counter() - t0_perf
    return (n_done_session / el * 3600.0) if el > 0 and n_done_session else 0.0


def _rolling_rate_from_rows(rows):
    """재개 시 ETA 용 — 직전 세션 checkpoint 의 wall_s 기반 보수적 추정(perm/h)."""
    if len(rows) < 5:
        return None
    ws = [r["wall_s"] for r in rows[-ROLLING_WINDOW:] if r.get("wall_s")]
    if not ws:
        return None
    w = max(rows[-ROLLING_WINDOW:], key=lambda r: r.get("workers", 1)).get("workers", 1)
    return w / (sum(ws) / len(ws)) * 3600.0


def _write_progress(gates, watch, session_seq, workers, completions, n_done_session,
                    budget_gib, stop_reason):
    """공개 진행 파일 — **T_b·AP·Δ 절대 금지**."""
    rows, _ = ckpt_load()
    total = B_PRIMARY * 2 + sum(ALT_N.values())
    rate = _rate(completions, workers)                    # w / wall_max (블록 D 정의)
    rate_sess = _rate_session(n_done_session, _SESSION["t0_perf"])
    eta_rate = rate or rate_sess                          # ETA 는 신뢰 가능한 값으로만
    left = total - len(rows)
    snap = watch.snapshot() if watch else {}
    try:
        prev = json.load(open(PROGRESS)) if os.path.exists(PROGRESS) else {}
    except json.JSONDecodeError:
        prev = {}
    sessions = prev.get("sessions", [])
    cur = {"seq": session_seq, "start_ts": _SESSION["start_ts"] or now_kst(),
           "stop_ts": None, "completed_delta": n_done_session, "workers": workers,
           "power_state": snap.get("power_last"), "graceful_stop": None,
           "stop_reason": stop_reason}
    sessions = [s for s in sessions if s.get("seq") != session_seq] + [cur]
    by_mode = collections.Counter(r["mode"] for r in rows)
    dump_json(PROGRESS, {
        "_scope": ("공개 진행 파일 — 개수·시간·메모리·해시·PASS/FAIL 만. "
                   "T_b·macro AP·Δ·p_emp·null 분포 **기입 금지**(docs/33 항목18 redaction)."),
        "ts_kst": now_kst(),
        "_session_start_ts": cur["start_ts"],
        "completed": len(rows), "total": total, "remaining": left,
        "completed_by_mode": dict(by_mode),
        "expected_by_mode": {"global": B_PRIMARY, "family": B_PRIMARY, **ALT_N},
        "session_seq": session_seq, "session_completed": n_done_session,
        "workers": workers,
        "rolling_throughput_perm_per_hour": rate,
        "rolling_window": min(len(completions), ROLLING_WINDOW),
        "rolling_valid": rate is not None,
        "rolling_definition": ("w / wall_max — 직전 %d개 permutation 단가의 최댓값 기준"
                               "(블록 D 동결 정의; 평균·중앙값 기반 계산 금지)." % ROLLING_WINDOW),
        "rolling_note": ("도착 시각 기반 (N-1)/span 은 18 워커가 동시에 끝나 배치 경계에서 "
                         "크게 왜곡되므로 쓰지 않는다 — permutation 단가 기반은 배치 정렬과 무관하다."),
        "session_throughput_perm_per_hour": rate_sess,
        "eta_hours": (left / eta_rate) if eta_rate else None,
        "eta_basis": ("rolling" if rate else ("session_average" if rate_sess else "미산출")),
        "sum_peak_rss_gib_observed": snap.get("ram_peak_gib"),
        "ram_budget_gib": budget_gib,
        "ram_gate_G4": {"exceeded": snap.get("ram_exceeded"),
                        "observed_gib": snap.get("ram_exceed_observed_gib"),
                        "ts_kst": snap.get("ram_exceed_ts_kst"),
                        "samples": snap.get("ram_samples")},
        "power": {"samples": snap.get("power_samples"),
                  "excursion": snap.get("power_excursion"),
                  "battery_sustained_abort": snap.get("battery_sustained_abort"),
                  "last": snap.get("power_last")},
        "gates": {"G0": gates.get("G0", {}).get("pass"),
                  "G3_identity": (gates.get("G3_identity") or {}).get("verdict")
                  or (gates.get("G3_identity") or {}).get("skipped"),
                  "G1_G2": (gates.get("G1_G2_concurrency") or {}).get("verdict")
                  or (gates.get("G1_G2_concurrency") or {}).get("skipped"),
                  "env_fingerprint_match": gates.get("env_fingerprint_match")},
        "stop_reason": stop_reason,
        "sessions": sessions,
        "stop_hint": f"touch {os.path.relpath(STOP_FILE, ROOT)}",
    })


def _close_session_in_progress(session_seq, stop_reason, graceful, n_done, workers):
    """F-1c — 종료 시 `sessions` 항목에 `stop_ts`·`graceful_stop` 을 확정 기입."""
    if not os.path.exists(PROGRESS):
        return
    try:
        prog = json.load(open(PROGRESS))
    except json.JSONDecodeError:
        return
    for s in prog.get("sessions", []):
        if s.get("seq") == session_seq:
            s["stop_ts"] = now_kst()
            s["stop_reason"] = stop_reason
            s["graceful_stop"] = bool(graceful)
            s["completed_delta"] = n_done
            s["workers"] = workers
    prog["ts_kst"] = now_kst()
    prog["stop_reason"] = stop_reason
    prog["graceful_stop"] = bool(graceful)
    dump_json(PROGRESS, prog)


def _session_decay(rows, session_seq):
    """F-3b — 세션 내 첫 20 / 마지막 20 permutation 평균 wall 과 감쇠율."""
    ws = [r["wall_s"] for r in rows if r.get("session_seq") == session_seq and r.get("wall_s")]
    if len(ws) < 2 * SESSION_EDGE_N:
        return {"session_seq": session_seq, "n": len(ws), "insufficient": True,
                "note": f"세션 내 permutation < {2 * SESSION_EDGE_N} — 감쇠율 미산출"}
    a = sum(ws[:SESSION_EDGE_N]) / SESSION_EDGE_N
    b = sum(ws[-SESSION_EDGE_N:]) / SESSION_EDGE_N
    return {"session_seq": session_seq, "n": len(ws),
            "first20_mean_wall_s": a, "last20_mean_wall_s": b,
            "decay_frac": (b - a) / a, "insufficient": False}


def _isolate_crash(crashed):
    """F-3 — checkpoint 는 보존, 그 외 부분 산출물만 격리(기존 파일 덮어쓰기 금지)."""
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(RUN_DIR, f"_crashed_{ts}")
    os.makedirs(dst, exist_ok=True)
    dump_json(os.path.join(dst, "crash.json"), crashed)
    for fn in ("progress_public.json", "gates_public.json"):
        src = os.path.join(RUN_DIR, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst, fn))
    logln(f"[크래시] 부분 산출물 격리 → {os.path.relpath(dst, ROOT)} "
          f"(checkpoint 는 원위치 보존 · 덮어쓰기 없음)")
    return dst


def _finish_session(gates, guard_start, session_seq, t0, n_done, reason, workers, watch,
                    caff, worker_changes=None, crashed=None):
    guard_end = guard_snapshot()
    guard_ok = (guard_end == guard_start)
    gb_end = None
    try:
        gb_end = gate_b_exclusive("null-main-run end")
    except SystemExit:
        gb_end = {"gate": "B", "label": "end", "pass": False,
                  "note": "종료 시 경쟁 프로세스 관측 — 기록만(산출물 영향 없음)"}
    rows, _ = ckpt_load()
    snap = watch.snapshot() if watch else {}
    wall = time.perf_counter() - t0
    gates.update({
        "sealed_guard_n_files_end": len(guard_end),
        "sealed_guard_unchanged": guard_ok,
        "G_IDLE_B_end": gb_end,
        "session_end_ts_kst": now_kst(),
        "session_wall_s": wall,
        "session_completed": n_done,
        "session_stop_reason": reason,
        "session_graceful_stop": crashed is None,
        "worker_changes": worker_changes or [],
        "session_decay_F3b": _session_decay(rows, session_seq),
        "observed_sum_peak_rss_gib": snap.get("ram_peak_gib"),
        "power_excursion": snap.get("power_excursion"),
        "ladder_freeze_sha16_end": sha256_file(CONFIG_FREEZE)[:16],
        "sap_manifest_sha16_end": sha256_file(SAP_MANIFEST)[:16],
    })
    assert gates["ladder_freeze_sha16_end"] == EXPECT_LADDER_FREEZE_SHA16, \
        "종료 시 ladder_freeze.json 변동 검출"
    assert gates["sap_manifest_sha16_end"] == EXPECT_SAP_MANIFEST_SHA16, \
        "종료 시 SAP manifest 변동 검출"
    dump_json(GATES_PUB, gates)
    _close_session_in_progress(session_seq, reason, crashed is None, n_done, workers)
    if not guard_ok:
        logln("[sealed guard] ❗ 종료 스냅샷이 시작과 불일치 — 즉시 조사 필요")
    logln(f"[세션 #{session_seq}] 종료 — 사유={reason} · 세션 완주 {n_done} · "
          f"누계 {len(rows)}/{B_PRIMARY * 2 + sum(ALT_N.values())} · wall {wall / 3600:.2f}h · "
          f"워커 {workers} · sealed 불변={guard_ok} · power_excursion={snap.get('power_excursion')}")
    if reason != "nothing_to_do":
        logln(f"[세션 #{session_seq}] graceful_stop={crashed is None}")
    if caff is not None:
        try:
            caff.terminate()
        except Exception:                                               # noqa: BLE001
            pass


# ═══════════════════════════════════════════════════════════════════════════
# 집계 — **반드시 별도 실행**(부분집계 물리 차단)
# ═══════════════════════════════════════════════════════════════════════════
def stage_aggregate():
    logln("=" * 78)
    logln("[집계] §13-4 — 하드 assert 전항 통과 시에만 empirical_p 호출(부분집계 금지)")

    # ── 재집계 차단(1회성) ────────────────────────────────────────────────────
    # 결과를 본 뒤 다시 집계하는 경로를 **물리적으로** 막는다. 재집계가 필요하면
    # 사유를 docs/33 에 먼저 기록하고 이 파일을 수동 이동한 뒤 별도 지시로만 한다.
    if os.path.exists(NULL_RESULT):
        prev_sha = sha256_file(NULL_RESULT)
        logln(f"[집계] ❌ 이미 집계된 산출물이 존재한다 — {os.path.relpath(NULL_RESULT, ROOT)} "
              f"(sha256 {prev_sha}). **덮어쓰지 않고 중단**한다. 재집계는 사유를 docs/33 에 "
              f"기록한 뒤 별도 지시로만 수행한다(결과 조회 후 재집계 = selective 분석 위험).")
        sys.exit(6)

    g0 = gate0_full()
    guard = guard_snapshot()
    assert len(guard) >= EXPECT_GUARD_MIN_FILES, "sealed 보호 대상 부족"

    rows, bad_tail = ckpt_load()
    assert not bad_tail, "[집계] checkpoint 마지막 줄 불완전 — 본런을 먼저 정상 종료하십시오."

    by_mode = collections.defaultdict(list)
    for r in rows:
        by_mode[r["mode"]].append(r)

    expected = {"global": (B_PRIMARY, SEED_BASE["global"]),
                "family": (B_PRIMARY, SEED_BASE["family"]),
                "family_ALT": (ALT_N["family_ALT"], SEED_BASE["family"]),
                "global_ALT": (ALT_N["global_ALT"], SEED_BASE["global"])}
    checks = {}
    ok = True
    for mode, (n_exp, base) in expected.items():
        got = by_mode.get(mode, [])
        seeds = [int(r["seed"]) for r in got]
        uniq = set(seeds)
        exp_seeds = set(range(base, base + n_exp))
        c = {"n_records": len(got), "n_unique": len(uniq), "expected": n_exp,
             "n_duplicates": len(seeds) - len(uniq),
             "n_missing": len(exp_seeds - uniq), "n_unexpected": len(uniq - exp_seeds),
             "pass": (len(uniq) == n_exp and len(seeds) == len(uniq)
                      and not (exp_seeds - uniq) and not (uniq - exp_seeds))}
        ok = ok and c["pass"]
        checks[mode] = c
        logln(f"[집계 assert] {mode:11s} unique {c['n_unique']}/{n_exp} · 중복 {c['n_duplicates']} · "
              f"누락 {c['n_missing']} · 범위밖 {c['n_unexpected']} → {'PASS' if c['pass'] else 'FAIL'}")

    b_ok = (checks["global"]["n_unique"] == checks["family"]["n_unique"]
            == sap_null.NULL_B == B_PRIMARY == 1000)
    checks["B_equals_NULL_B"] = {"NULL_B": sap_null.NULL_B, "pass": bool(b_ok)}
    ok = ok and b_ok
    logln(f"[집계 assert] B == NULL_B == {sap_null.NULL_B} → {'PASS' if b_ok else 'FAIL'}")

    if not ok:
        dump_json(AGG_PUB, {"_scope": "공개 — 개수·해시·시간만", "ts_kst": now_kst(),
                            "aggregation_asserts": checks, "all_pass": False,
                            "empirical_p_called": False,
                            "verdict": "ABORT — 부분집계 차단(empirical_p 미호출)"})
        logln("[집계] ❌ assert 실패 — `empirical_p` 를 **호출조차 하지 않고** 중단합니다.")
        sys.exit(5)
    logln("[집계 assert] 전항 PASS — empirical_p 호출 진입")

    # ── T_obs = 반복1(seed 201) sealed OOF 기준 M2b macro AP (machine_read) ──
    log_machine_read(os.path.relpath(os.path.join(REP1_SEALED, "oof_M2b.npz"), ROOT),
                     "T_obs computation (machine_read, human_exposure=false)", "§13-4 집계")
    d = load_frozen()
    Y = d["Ym"]
    with np.load(os.path.join(REP1_SEALED, "oof_M2b.npz")) as z:
        oof_obs = z["oof"]
    t_obs = float(sap_metrics.macro_ap(Y, sap_consensus.build_consensus([oof_obs]),
                                       np.arange(Y.shape[1]))["macro_ap"])
    del oof_obs
    logln("[T_obs] 반복1(seed 201) sealed OOF 기준 M2b macro AP 산출 — 값 미출력(sealed)")

    # ── primary p_emp (global·family 각 1회) ────────────────────────────────
    sealed = {"_warning": "SEALED — §13-4 null 결과. 개봉은 성공판정 단계에서 Holm/BH 와 일괄.",
              "ts_kst": now_kst(),
              "T_definition": "observed M2b macro AP (rep1 seed201 절차와 동일: eligible=370 PT 전체)",
              "sidedness": "one-sided-upper",
              "p_emp_formula": "(1 + #{T_b >= T_obs}) / (B + 1)",
              "T_obs": t_obs, "T_obs_basis": "rep1_seed201 sealed OOF (machine_read)",
              "primary": {}, "ALT": {}, "aggregation_asserts": checks, "G0": g0}
    for mode in ("global", "family"):
        stats = [float(r["macro_AP"]) for r in by_mode[mode]]
        res = sap_null.empirical_p(t_obs, stats)
        assert res["b_equals_null_b"], f"[{mode}] B != NULL_B"
        sealed["primary"][mode] = {**res, "n_permutations": len(stats),
                                   "enters_p_emp": True}
        logln(f"[p_emp] {mode} — empirical_p 호출 1회 완료 (B={res['B']}) · 값은 sealed")

    # ── ALT 는 **별도 집계**(primary null 분포 편입 금지) ────────────────────
    for mode in ("family_ALT", "global_ALT"):
        stats = [float(r["macro_AP"]) for r in by_mode[mode]]
        res = sap_null.empirical_p(t_obs, stats)
        sealed["ALT"][mode] = {**res, "n_permutations": len(stats), "enters_p_emp": False,
                               "note": "사전지정 민감도 — primary null 분포 편입 금지"}
    # global_ALT = 음성대조: partition·tie-break 무관 → primary global 과 sha 동일해야 함
    prim_g = {int(r["seed"]): r["oof_sha256"] for r in by_mode["global"]}
    alt_g = {int(r["seed"]): r["oof_sha256"] for r in by_mode["global_ALT"]}
    neg = {s: (prim_g.get(s) == sha) for s, sha in alt_g.items()}
    neg_pass = all(neg.values())
    sealed["ALT"]["global_ALT_negative_control"] = {"n_compared": len(neg),
                                                    "all_identical": bool(neg_pass)}
    logln(f"[음성대조] global_ALT vs primary global oof_sha256 동일 = **{neg_pass}** "
          f"({len(neg)}개 비교) — 불일치는 하네스 버그 신호")

    # paired ALT — family_ALT 는 primary family 와 동일 seed 재사용
    paired = sorted(set(alt_g) & set(prim_g))
    sealed["ALT"]["paired_seeds_note"] = (
        "family_ALT 는 primary family 와 동일 seed 재사용(몬테카를로 잡음 상쇄)")
    dump_json(NULL_RESULT, sealed)
    _ = paired

    result_sha = sha256_file(NULL_RESULT)
    wall_total = sum(r.get("wall_s", 0.0) for r in rows)
    cpu_total = sum(r.get("cpu_s", 0.0) for r in rows)
    peak_max = max((r.get("peak_rss", 0) for r in rows), default=0)
    sessions = sorted({r.get("session_seq", 1) for r in rows})
    decay = [_session_decay(rows, s) for s in sessions]
    dvals = sorted(x["decay_frac"] for x in decay if not x["insufficient"])
    decay_median = (dvals[len(dvals) // 2] if len(dvals) % 2 else
                    (dvals[len(dvals) // 2 - 1] + dvals[len(dvals) // 2]) / 2) if dvals else None

    dump_json(AGG_PUB, {
        "_scope": ("공개 — 개수·해시·시간·메모리·PASS/FAIL 만. p_emp·유의 여부·null 분포·"
                   "T_obs·T_b·AP·Δ 는 _sealed/null_result.json (개봉 = 성공판정 단계 일괄)."),
        "ts_kst": now_kst(),
        "aggregation_asserts": checks, "all_pass": True, "empirical_p_called": True,
        "empirical_p_calls": {"global": 1, "family": 1, "ALT_separate": 2},
        "n_permutations": {m: checks[m]["n_unique"] for m in expected},
        "null_result_sealed_sha256": result_sha,
        "global_ALT_negative_control_all_identical": bool(neg_pass),
        "total_wall_s_sum_of_permutations": wall_total,
        "total_wall_hours_sum_of_permutations": wall_total / 3600.0,
        "total_cpu_s": cpu_total,
        "max_worker_peak_rss_bytes": peak_max,
        "n_sessions": len(sessions),
        "session_decay_F3b": decay,
        "session_decay_median_frac": decay_median,
        "decay_reporting_rule": ("분할 실행에서는 세션 경계가 섞이므로 세션 **내부** 첫 20 / 마지막 20 "
                                 "permutation 평균 wall 로 감쇠를 보고하고, 전체는 세션 내 감쇠율의 "
                                 "**중앙값**으로 보고한다. 세션 간 비교는 하지 않는다."),
        "sealed_guard_n_files": len(guard),
        "ladder_freeze_sha16": g0["ladder_freeze_sha16"],
        "sap_manifest_sha16": g0["sap_manifest_sha16"],
        "redaction": "공개 파일에 p_emp·유의 여부·null 분포·T_obs·T_b·AP·Δ 없음",
    })
    logln(f"[집계] 완료 — _sealed/null_result.json sha256 {result_sha} (값은 비공개)")
    print("\n" + "=" * 78, flush=True)
    print(f"[집계 완료] assert 전항 PASS · empirical_p global 1회 + family 1회 + ALT 별도 2회", flush=True)
    print(f"  _sealed/null_result.json sha256 = {result_sha}", flush=True)
    print(f"  공개 산출 = {os.path.relpath(AGG_PUB, ROOT)} (개수·해시·시간·메모리만)", flush=True)
    print("  다음 단계(성공판정)는 별도 지시.", flush=True)
    print("=" * 78 + "\n", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["run", "aggregate"], default="run")
    args = ap.parse_args()
    if args.stage == "run":
        stage_run()
    else:
        stage_aggregate()


if __name__ == "__main__":
    mp.freeze_support()
    with ComputeLock(script="null_main_run.py", role="runner"):
        main()
