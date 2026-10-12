#!/usr/bin/env python3
"""null_compute_probe2.py — 블록 D(개정): Mac wall-clock 최적화 **측정 전용** 프로브2.

⚠️ 이것은 §13-4 본실행이 아니다. `enters_null_distribution=false` · `empirical_p` 미호출 ·
   p 미계산 · T_obs 비교 없음 · 성공판정 없음. `ladder_freeze.json` **파일 수정 금지**
   (병렬 인자는 읽어온 dict 의 **메모리상 복사본**에서만 변경).

목적: 2,000 permutation 총 wall 을 7일 이내로 줄이는 구성 1개를 **실측**으로 특정.
      7일 초과면 "Mac 단독 부적합" 판정 후 정지(§13-4 본런 프롬프트 요청 금지).

D-0  사전 확인 — 게이트0 + rep1 sealed 3종 + 반복2·3·consensus sealed sha256 불변 + 전원 상태
D-1  진짜 CPU-시간 — identity permutation 1 fold, RUSAGE_SELF + RUSAGE_CHILDREN
     → 실효 병렬도 = cpu_sec / wall_sec (18 logical · 6 P코어 각 기준 효율)
D-2  병렬축 스윕 A~E (각 구성 1 fold, 300 trees) — **비트동일 게이트**(sha256 전원 일치)
D-3  워커 수 스윕 {1,3,6,9,12,18} — **타이밍 프록시 n_estimators=60**(분석 미투입) · G1 · RAM 게이트
D-4  단독 baseline(1 permutation 완주) + (CFG_BEST, W_BEST) 병렬 전량 → 프록시 오차율 · 0-diff · 열 감쇠
D-5  재산정 표(열감쇠 반영) + 권장 구성 1개 + 7일 정지 조건
D-6  산출·기록

── 보정 3건(지시 반영) ────────────────────────────────────────────────────────
D-3 보정: **처리량 = w / wall_max**(워커 중 **마지막 완료** 시각 기준). 평균/중앙값 기반
          처리량 계산 금지(중앙값은 **기술통계 보고용**으로만 남긴다). 워커 수마다
          워커별 wall `min / median / max / (max−min)/median` 을 보고한다.
          코어 배정 규칙 `워커당 = logical // w`(RF 우선 배정, 잔여 슬롯 MOC)를
          `compute_public.json` 과 `docs/33` 에 명시하고, P/E 코어 비대칭으로 워커 간
          실제 코어 배치가 불균등할 수 있음을 **한계**로 함께 기록한다.
D-4 보정: 열감쇠·지속부하 baseline 은 **단독(w=1) 1 permutation 완주 값만** 사용한다.
          병렬 배치의 워커 0(identity) wall 은 오버서브스크립션 상태 측정치이므로
          baseline 금지 — **0-diff 검증 용도로만** 쓴다.
          지속부하 구간의 **전원 상태(AC/배터리)·powermode 값·시각**을 로그에 기록한다.
블록 C 보정: 블록 C(§13-5 반복2·3)는 배터리·저전력 모드에서 실행되어 **wall-clock 비교 불가**
          (바이트 동일성에는 영향 없음). 블록 C wall-clock 은 블록 D·§13-4 추정에
          **투입 금지** — 본 스크립트는 블록 C 시간값을 일절 읽지 않는다(D-6 에서 선언·검증).

실행: caffeinate -dimsu .venv/bin/python3 v3_Multimodal/src/null_compute_probe2.py --stage all
"""
from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import argparse
import platform
import resource
import subprocess
import threading
import multiprocessing as mp
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from sklearn.ensemble import RandomForestClassifier                 # noqa: E402
from sklearn.multioutput import MultiOutputClassifier               # noqa: E402

from ladder_confirmatory import (                                   # noqa: E402
    load_frozen, MorganBlock, CountMaskBlock, SeqBlock, M1bCovariateBlock,
    MODEL_BLOCKS, RF_KW, SEED, PCA_K,
)
from confirmatory_oof_rep1 import gate0_verify, sha256_file         # noqa: E402
from null_timing_probe import (                                     # noqa: E402
    load_target_structure, meanpool_from_mapping, build_mapping, F_EMB_FROZEN,
)
from sap import null_generator as sap_null                          # noqa: E402
from compute_lock import (ComputeLock, gate_a_load,                 # noqa: E402
                          gate_b_exclusive, gate_c_settle)

KST = timezone(timedelta(hours=9))

# ── 프로브2 전용 상수 (결과 무참조·실행 전 고정) ────────────────────────────────
PROBE2_SEED_BASE = 9000101                  # 본실행 namespace(≤1,000,000) 및 프로브1(9000001·2)과 분리
MAIN_SEED_NAMESPACE_MAX = 1_000_000
PROBE1_SEEDS = {9000001, 9000002}
RESERVED_SEEDS = set(range(201, 206)) | {42}
PROBE_ONLY = True
ENTERS_NULL_DISTRIBUTION = False
FOLD_FOR_BENCH = 0                          # 마이크로벤치는 fold 0 고정(구성 간 동일 조건)
N_FOLD = 5
RF_SEED = SEED                              # 42 = NULL_RF_COMMON_SEED
RF_N_ESTIMATORS_FULL = RF_KW["n_estimators"]        # 300 — 동결값
RF_N_ESTIMATORS_PROXY = 60                          # D-3 **타이밍 전용** 프록시
PROXY_ERROR_TOL = 0.30                              # 프록시 오차 30% 초과 → 프록시 기각
RAM_BUDGET_FRAC = 0.60                              # 합계 peak RSS > 물리 RAM 60%(=38.4GiB) → 후보 제외
STOP_DAYS = 7.0                                     # 예상 wall > 7일 → Mac 단독 부적합
WORKER_SWEEP = (1, 3, 6, 9, 12, 18)
SUSTAINED_LOAD_MIN_SEC = 600.0                      # D-4 지속부하 하한(10분) — **단독 런 기준**
POWER_SAMPLE_INTERVAL_S = 60.0                      # D-4 지속부하 구간 전원 상태 샘플 주기
SOLO_WORKERS = 1                                    # D-4 baseline = 단독 1 permutation 완주
EXPECT_FREEZE_SHA16 = "b885585aefbabb32"
THREAD_ENV_KEYS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                   "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")

RUN_DIR = os.path.join(ROOT, "experiments", "runs", "v3_null_probe2_compute")
SEALED_DIR = os.path.join(RUN_DIR, "_sealed")
PROXY_DIR = os.path.join(RUN_DIR, "_proxy")
STATE_F = os.path.join(RUN_DIR, "_state.json")
SPLIT_DIR = os.path.join(ROOT, "data", "processed", "splits", "confirmatory", "rep1_seed201")
CONFIG_FREEZE = os.path.join(ROOT, "v3_Multimodal", "config", "ladder_freeze.json")
HARDWARE = os.path.join(ROOT, "experiments", "runs", "v3_null_probe", "hardware.json")
MANIFEST_DRAFT = os.path.join(ROOT, "experiments", "runs", "v3_null_MAIN", "run_manifest_draft.json")

# 블록 C 산출물 보호 — 존재하는 것만 검증(반복3·consensus 경로는 실행 시점에 탐색)
SEALED_GUARD_GLOBS = [
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep1_seed201", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep2_seed202", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep3_seed203", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_consensus_rep123", "_sealed"),
]
EXPECT_GUARD_MIN_FILES = 12          # rep1·rep2·rep3 각 3종 + consensus ≥3 — 미만이면 블록 C 미완결

_LOG = []


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    _LOG.append(line)


def flush_log():
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "run.log"), "a") as f:
        f.write("\n".join(_LOG) + "\n")
    _LOG.clear()


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
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=native)
    return path


def load_state():
    return json.load(open(STATE_F)) if os.path.exists(STATE_F) else {}


def save_state(st):
    dump_json(STATE_F, st)


def rss_bytes(who=resource.RUSAGE_SELF):
    ru = resource.getrusage(who).ru_maxrss
    return int(ru) if sys.platform == "darwin" else int(ru * 1024)


def cpu_sec_total():
    """RUSAGE_SELF + RUSAGE_CHILDREN 의 utime+stime 합 (진짜 CPU-시간)."""
    s = resource.getrusage(resource.RUSAGE_SELF)
    c = resource.getrusage(resource.RUSAGE_CHILDREN)
    return (s.ru_utime + s.ru_stime + c.ru_utime + c.ru_stime,
            s.ru_utime + s.ru_stime, c.ru_utime + c.ru_stime)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def arr_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# D-0 전원·열 조건 게이트
# ═══════════════════════════════════════════════════════════════════════════
def power_state():
    """전원 연결·저전력 모드 상태 실측(로그 기록 필수). 네트워크 호출 아님."""
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
        except Exception as e:                                   # noqa: BLE001
            return f"<unavailable: {e}>"
    ps = sh(["pmset", "-g", "ps"])
    live = sh(["pmset", "-g", "live"])
    powermode = None
    for ln in live.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0] == "powermode":
            powermode = int(p[1])
    on_ac = "AC Power" in ps
    caffeinated = bool(os.environ.get("PROBE2_CAFFEINATE") == "1") or \
        ("caffeinate" in sh(["pgrep", "-l", "caffeinate"]))
    return {"raw_pmset_ps": ps.strip(), "on_ac_power": on_ac,
            "powermode_live": powermode,
            "low_power_mode_off": (powermode == 0),
            "caffeinate_detected": caffeinated,
            "thermal_pressure": sh(["sh", "-c",
                                    "pmset -g therm 2>/dev/null | head -20"]).strip()}


class PowerWatcher:
    """D-4 보정 — 지속부하 구간의 전원 상태·powermode·**시각**을 주기 샘플로 기록.

    부모 프로세스가 `pool.map` 에서 블로킹되는 동안에도 샘플이 남도록 데몬 스레드로 돈다.
    샘플 1건 = `pmset` 서브프로세스 2회(수십 ms) → 측정 대상 부하에 실질 영향 없음."""

    def __init__(self, phase, interval=POWER_SAMPLE_INTERVAL_S):
        self.phase = phase
        self.interval = interval
        self.samples = []
        self._stop = threading.Event()
        self._t = None

    def _snap(self, kind):
        p = power_state()
        self.samples.append({"ts_kst": now_kst(), "phase": self.phase, "kind": kind,
                             "on_ac_power": p["on_ac_power"],
                             "powermode_live": p["powermode_live"],
                             "low_power_mode_off": p["low_power_mode_off"],
                             "raw_pmset_ps_head": (p["raw_pmset_ps"].splitlines() or [""])[0]})
        return self.samples[-1]

    def _loop(self):
        while not self._stop.wait(self.interval):
            self._snap("during")

    def __enter__(self):
        s = self._snap("start")
        logln(f"[D-4 전원 {self.phase} 시작] {s['ts_kst']} · AC={s['on_ac_power']} · "
              f"powermode={s['powermode_live']}")
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join(timeout=5)
        s = self._snap("end")
        logln(f"[D-4 전원 {self.phase} 종료] {s['ts_kst']} · AC={s['on_ac_power']} · "
              f"powermode={s['powermode_live']} · 샘플 {len(self.samples)}건")
        return False

    def report(self):
        """구간 내내 AC·저전력해제 유지되었는지 판정 + 전 샘플(시각 포함) 반환."""
        ac_all = all(s["on_ac_power"] for s in self.samples)
        lpm_off_all = all(s["low_power_mode_off"] for s in self.samples)
        return {"phase": self.phase, "n_samples": len(self.samples),
                "interval_s": self.interval, "samples": self.samples,
                "ac_power_held_entire_phase": bool(ac_all),
                "low_power_mode_off_entire_phase": bool(lpm_off_all),
                "powermode_values_seen": sorted({str(s["powermode_live"])
                                                 for s in self.samples}),
                "measurement_valid": bool(ac_all and lpm_off_all)}


def guard_snapshot():
    """블록 C 산출물(_sealed) 파일별 sha256 스냅샷 — 값은 열지 않고 지문만."""
    snap = {}
    for d in SEALED_GUARD_GLOBS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if os.path.isfile(p) and fn != "access.log":
                snap[os.path.relpath(p, ROOT)] = sha256_file(p)
    return snap


# ═══════════════════════════════════════════════════════════════════════════
# 런타임 override RF (ladder_freeze.json **파일 무수정** — 메모리상 dict 복사본만 변경)
# ═══════════════════════════════════════════════════════════════════════════
def rf_fit_predict_cfg(Xtr, Ytr, Xeval, seed, rf_n_jobs, moc_n_jobs, n_estimators=None):
    """`ladder_confirmatory.rf_fit_predict` 와 **동일 절차**. 병렬 인자만 런타임 override.

    통계적 비-파라미터: max_depth·class_weight·random_state 불변.
    `n_estimators` 는 **D-3 타이밍 프록시 전용**으로만 다른 값을 받는다(분석 산출물 미생성)."""
    kw = dict(RF_KW)                       # 동결 dict 의 **복사본** — 원본 미변경
    kw["n_jobs"] = rf_n_jobs
    if n_estimators is not None:
        kw["n_estimators"] = int(n_estimators)
    clf = MultiOutputClassifier(RandomForestClassifier(random_state=seed, **kw), n_jobs=moc_n_jobs)
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xeval.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xeval)[:, cls.index(1)]
    return P


def build_blocks(d, emb_matrix):
    """permutation당 1회 — 동결 블록 인스턴스 생성(probe1 run_m2b_oof 와 동일 구조)."""
    b = {"B0": MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"]),
         "B1": CountMaskBlock(d["ntgt"], d["mask"]),
         "B_seq": SeqBlock(emb_matrix, d["mask"], pca_k=PCA_K),
         "B_m1b": M1bCovariateBlock(d["cov_by_cid"], d["cid_order"],
                                    include_pchembl=False, name="B_m1b")}
    assert b["B_m1b"].dim == 10, f"primary B_m1b dim={b['B_m1b'].dim} != 10"
    assert MODEL_BLOCKS["M2b"] == ["B0", "B1", "B_m1b", "B_seq"]
    return b


def build_fold_matrices(d, blocks, fold_of_row, kf):
    """fold kf 의 M2b 학습·평가 행렬 조립 — fold-train fit 규칙·누수 assert 그대로."""
    N = len(d["cid_order"])
    te = np.where(fold_of_row == kf)[0]
    tr = np.where(fold_of_row != kf)[0]
    for b in blocks.values():
        b.fit(tr)
    expect = np.zeros(N, dtype=bool)
    expect[tr] = True
    expect &= d["mask"].astype(bool)
    assert np.array_equal(blocks["B_seq"]._fit_rows_mask, expect), "B_seq fit 모집단 != train∩매핑"
    for b in ("B0", "B1", "B_seq", "B_m1b"):
        assert blocks[b].leakage_assert(tr)["leak_rows"] == 0, f"{b} leak_rows != 0"
    Xtr = np.hstack([blocks[b].transform(tr) for b in MODEL_BLOCKS["M2b"]]).astype(np.float32)
    Xte = np.hstack([blocks[b].transform(te) for b in MODEL_BLOCKS["M2b"]]).astype(np.float32)
    return Xtr, Xte, tr, te


def shutdown_loky():
    """loky 재사용 executor 를 종료해 자식 CPU-시간이 RUSAGE_CHILDREN 에 **반영(reap)** 되게 한다.
    (미종료 시 MultiOutputClassifier(n_jobs>1) 구성의 CPU-시간이 과소계상된다.)"""
    try:
        from joblib.externals.loky import get_reusable_executor
        get_reusable_executor().shutdown(wait=True)
        return True
    except Exception:                                       # noqa: BLE001
        return False


# ═══════════════════════════════════════════════════════════════════════════
# 구성 정의 — 개정 블록 D 표 그대로 (P코어 6 / logical 18 실측 반영)
# ═══════════════════════════════════════════════════════════════════════════
def make_configs(p_cores, logical):
    return [
        {"name": "A", "label": "MOC=None / RF=-1(18)", "moc_n_jobs": None, "rf_n_jobs": -1,
         "intent": "현행 기준"},
        {"name": "B", "label": f"MOC=None / RF={p_cores}", "moc_n_jobs": None, "rf_n_jobs": p_cores,
         "intent": "P코어만 → E코어 혼입 효과 분리"},
        {"name": "C", "label": f"MOC={p_cores} / RF=1", "moc_n_jobs": p_cores, "rf_n_jobs": 1,
         "intent": "PT 축 병렬 · P코어 수"},
        {"name": "D", "label": f"MOC={logical} / RF=1", "moc_n_jobs": logical, "rf_n_jobs": 1,
         "intent": "PT 축 병렬 · logical 전량"},
        {"name": "E", "label": f"MOC={p_cores} / RF=3", "moc_n_jobs": p_cores, "rf_n_jobs": 3,
         "intent": "하이브리드"},
    ]


# ── 코어 배정 규칙(D-3 보정: 공개 산출물·docs/33 에 명시) ──────────────────────
CORE_ASSIGNMENT_RULE = {
    "formula": "워커당 배정 코어 = logical // w  (logical=18, w=워커 수; 최소 1)",
    "allocation_order": ("RF 우선 배정(rf_n_jobs = min(요청, 배정코어); -1 이면 배정코어 전량) → "
                         "남은 슬롯을 MOC 에(moc_n_jobs = max(1, 배정코어 // rf_n_jobs); "
                         "원 구성이 MOC=None 이면 None 유지)"),
    "thread_env": ("워커 프로세스의 BLAS 스레드 상한도 동일하게 배정코어 수로 설정 "
                   "(OMP/OPENBLAS/MKL/VECLIB/NUMEXPR — 부모에서 설정 후 spawn 상속)"),
    "rationale": ("축소 없이 w 워커 × 내부 18스레드를 띄우면 최대 324-way 오버서브스크립션이 되어 "
                  "'처리량'이 아니라 '스래싱'을 측정하게 된다."),
    "numerical_invariance": "병렬 인자는 통계적 비-파라미터 — D-2 비트동일 게이트·D-3 G1 로 0-diff 증명.",
    "limitation_pe_asymmetry": (
        "**한계** — Apple Silicon 은 P코어(6)·E코어(12)가 비대칭이고, 코어 배정은 macOS 스케줄러가 "
        "QoS 기준으로 수행한다. 본 규칙은 워커당 **스레드 수 상한**만 균등 분배할 뿐 물리 코어를 "
        "고정(affinity pinning)하지 못한다(macOS 는 사용자 수준 CPU affinity API 미제공). "
        "따라서 워커별 실제 코어 배치가 P/E 혼합 비율 면에서 불균등할 수 있고, 이는 워커 간 "
        "wall 편차((max−min)/median)로 관측된다. 처리량을 wall_max(마지막 완료) 기준으로 "
        "정의한 것은 이 불균등을 낙관적으로 상쇄하지 않기 위함이다."),
}


def scale_cfg(cfg, cores):
    """워커당 배정 코어 수에 맞춰 구성의 **내부 병렬도만** 축소(수치 불변 — D-2에서 비트동일 증명됨).

    규칙 = `CORE_ASSIGNMENT_RULE` (워커당 = logical // w · RF 우선 배정 → 잔여 슬롯 MOC).
    P/E 비대칭 한계도 같은 dict 에 기록되어 `compute_public.json` 으로 방출된다."""
    rf, moc = cfg["rf_n_jobs"], cfg["moc_n_jobs"]
    rf_eff = cores if rf == -1 else max(1, min(int(rf), cores))
    moc_eff = None if moc is None else max(1, cores // rf_eff)
    return {"rf_n_jobs": rf_eff, "moc_n_jobs": moc_eff,
            "cores_assigned": cores,
            "intra_worker_threads_nominal": rf_eff * (moc_eff or 1)}


# ═══════════════════════════════════════════════════════════════════════════
# 워커 (모듈 최상위 — spawn 가능해야 함)
# ═══════════════════════════════════════════════════════════════════════════
def _worker(payload):
    """1 permutation × 지정 fold 들. 반환 = 단계별 시간 + fold별 예측 sha256 + peak RSS.

    ⚠️ `setup_s`(프로세스당 1회 데이터 로드)는 본실행에서 **permutation 수로 상각**되므로
       투영에는 `recurring_s`(= permutation 빌드 + mean-pool + fold별 조립 + RF)만 쓴다."""
    import time as _t
    seed = payload["seed"]
    mode = payload["mode"]
    cfg = payload["cfg"]
    folds = payload["folds"]
    n_est = payload["n_estimators"]

    t0 = _t.perf_counter()
    d = load_frozen()
    cid_order = d["cid_order"]
    ts = load_target_structure(cid_order)
    cid2fold = json.load(open(os.path.join(SPLIT_DIR, "folds.json")))
    fold_of_row = np.array([cid2fold[str(int(c))] for c in cid_order], dtype=int)
    t_setup = _t.perf_counter() - t0

    t_r0 = _t.perf_counter()
    if mode == "identity":
        mapping = {u: u for u in ts["unique_targets"]}
    else:
        mapping, _rep = build_mapping(mode, ts, seed)
    emb_p, mask_p, ntgt_p = meanpool_from_mapping(ts, cid_order, mapping)
    assert np.array_equal(mask_p, d["mask"]) and np.array_equal(ntgt_p, d["ntgt"]), "보존 위반"
    blocks = build_blocks(d, emb_p)
    t_perm = _t.perf_counter() - t_r0

    fold_recs = []
    for kf in folds:
        tf0 = _t.perf_counter()
        Xtr, Xte, tr, te = build_fold_matrices(d, blocks, fold_of_row, kf)
        t_asm = _t.perf_counter() - tf0
        tr0 = _t.perf_counter()
        P = rf_fit_predict_cfg(Xtr, d["Ym"][tr], Xte, RF_SEED,
                               cfg["rf_n_jobs"], cfg["moc_n_jobs"], n_estimators=n_est)
        t_rf = _t.perf_counter() - tr0
        fold_recs.append({"fold": int(kf), "assemble_s": t_asm, "rf_s": t_rf,
                          "fold_wall_s": _t.perf_counter() - tf0,
                          "pred_sha256": arr_sha(P),
                          "n_train": int(len(tr)), "n_test": int(len(te)),
                          "dim": int(Xtr.shape[1])})
        del P, Xtr, Xte
    shutdown_loky()
    ru = resource.getrusage(resource.RUSAGE_SELF)
    rc = resource.getrusage(resource.RUSAGE_CHILDREN)
    recurring = t_perm + sum(f["fold_wall_s"] for f in fold_recs)
    return {"seed": seed, "mode": mode, "n_estimators": n_est,
            "wall_s": _t.perf_counter() - t0, "setup_s": t_setup,
            "perm_build_s": t_perm, "recurring_s": recurring,
            "folds": fold_recs,
            "cpu_s": ru.ru_utime + ru.ru_stime + rc.ru_utime + rc.ru_stime,
            "peak_rss_bytes": (int(ru.ru_maxrss) if sys.platform == "darwin"
                               else int(ru.ru_maxrss * 1024)),
            "thread_env": {k: os.environ.get(k) for k in THREAD_ENV_KEYS}}


def run_pool(nw, payloads, cores_per_worker):
    """spawn Pool 실행. 스레드 환경변수는 **부모에서 설정 → spawn 자식이 상속**(numpy import 이전)."""
    saved = {k: os.environ.get(k) for k in THREAD_ENV_KEYS}
    for k in THREAD_ENV_KEYS:
        os.environ[k] = str(cores_per_worker)
    try:
        ctx = mp.get_context("spawn")
        c0 = cpu_sec_total()
        w0 = time.perf_counter()
        with ctx.Pool(processes=nw) as pool:
            res = pool.map(_worker, payloads)
        wall = time.perf_counter() - w0
        c1 = cpu_sec_total()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return res, wall, c1[0] - c0[0]


# ═══════════════════════════════════════════════════════════════════════════
# 스테이지
# ═══════════════════════════════════════════════════════════════════════════
def stage_d0(st):
    logln("=" * 78)
    logln("[블록 D 개정] Mac wall-clock 최적화 **측정 전용** — enters_null_distribution=false · "
          "empirical_p 미호출 · p 미계산 · T_obs 비교 없음 · ladder_freeze.json 파일 수정 금지")

    g0 = gate0_verify()
    logln(f"[D-0 게이트0] PASS — ladder_freeze={g0.get('ladder_freeze_sha16', '?')} "
          f"sap_manifest={g0.get('sap_manifest_sha16', '?')}")

    snap = guard_snapshot()
    logln(f"[D-0 sealed 보호] 블록 C 산출물 {len(snap)}개 파일 sha256 스냅샷 (값 미열람)")
    for k in sorted(snap):
        logln(f"        {k} = {snap[k][:16]}")

    pw = power_state()
    logln(f"[D-0 전원] AC 연결={pw['on_ac_power']} · powermode(live)={pw['powermode_live']} "
          f"(0=저전력 해제) · caffeinate 감지={pw['caffeinate_detected']}")
    logln(f"[D-0 전원 raw] {pw['raw_pmset_ps'].splitlines()[0] if pw['raw_pmset_ps'] else 'n/a'}")
    assert pw["on_ac_power"], "전원 미연결(배터리) — 블록 D 측정 무효. 어댑터 연결 후 재실행."
    assert pw["low_power_mode_off"], f"저전력 모드 ON(powermode={pw['powermode_live']}) — 측정 무효."
    assert pw["caffeinate_detected"], "caffeinate 미감지 — `caffeinate -dimsu` 로 감싸 재실행."

    hw = json.load(open(HARDWARE))
    st["d0"] = {"gate0": g0, "sealed_guard": snap, "power": pw,
                "hardware": hw, "ts_kst": now_kst()}
    save_state(st)
    return st


def stage_d12(st):
    hw = st["d0"]["hardware"]
    p_cores = hw["cpu"]["performance_cores_physical"]
    logical = hw["cpu"]["logical_total"]
    ram = hw["memory"]["bytes"]

    d = load_frozen()
    cid_order = d["cid_order"]
    Y = d["Ym"]
    ts = load_target_structure(cid_order)
    cid2fold = json.load(open(os.path.join(SPLIT_DIR, "folds.json")))
    fold_of_row = np.array([cid2fold[str(int(c))] for c in cid_order], dtype=int)

    ident = {u: u for u in ts["unique_targets"]}
    emb_id, mask_id, _ = meanpool_from_mapping(ts, cid_order, ident)
    assert np.array_equal(emb_id.view(np.uint8), np.load(F_EMB_FROZEN).view(np.uint8)), \
        "identity mean-pool != 동결본"
    logln("[전제] identity mean-pool == 동결 drug_target_emb_meanpool.npy 바이트 동일")

    blocks = build_blocks(d, emb_id)
    Xtr, Xte, tr, te = build_fold_matrices(d, blocks, fold_of_row, FOLD_FOR_BENCH)
    logln(f"[벤치 대상] fold {FOLD_FOR_BENCH}: train={len(tr)} test={len(te)} dim={Xtr.shape[1]} "
          f"· identity permutation · 300 trees · 구성 간 동일 입력")

    configs = make_configs(p_cores, logical)
    bench, ref_sha = [], None
    for cfg in configs:
        rss_before = rss_bytes()
        c0 = cpu_sec_total()
        w0 = time.perf_counter()
        P = rf_fit_predict_cfg(Xtr, Y[tr], Xte, RF_SEED, cfg["rf_n_jobs"], cfg["moc_n_jobs"])
        wall = time.perf_counter() - w0
        reaped = shutdown_loky()          # 자식 CPU-시간 reap 후 계측
        c1 = cpu_sec_total()
        cpu = c1[0] - c0[0]
        sha = arr_sha(P)
        if ref_sha is None:
            ref_sha = sha
            np.save(os.path.join(SEALED_DIR, "fold_pred_reference.npy"), P)
        rss = rss_bytes()
        rss_child = rss_bytes(resource.RUSAGE_CHILDREN)
        rec = {**cfg, "wall_s": wall, "cpu_s": cpu,
               "cpu_self_s": c1[1] - c0[1], "cpu_children_s": c1[2] - c0[2],
               "loky_reaped": reaped,
               "effective_parallelism": cpu / wall if wall > 0 else float("nan"),
               "eff_vs_p_cores": (cpu / wall) / p_cores if wall > 0 else None,
               "eff_vs_logical": (cpu / wall) / logical if wall > 0 else None,
               "peak_rss_self_bytes_cumulative": rss,
               "peak_rss_self_delta_bytes": rss - rss_before,
               "peak_rss_max_child_bytes": rss_child,
               "peak_rss_note": "ru_maxrss(SELF)는 프로세스 최고수위(단조증가) = 누적치; "
                                "CHILDREN 은 자식 중 최대 1개 값",
               "pred_sha256": sha, "bitwise_identical_to_A": bool(sha == ref_sha)}
        bench.append(rec)
        logln(f"[D-2 구성 {cfg['name']}] {cfg['label']:22s}: wall {wall:8.1f}s · CPU {cpu:9.1f}s · "
              f"실효병렬도 {rec['effective_parallelism']:5.2f} · 자식 최대 RSS {rss_child/1e9:.2f}GB · "
              f"pred sha={sha[:16]} · A와 비트동일={rec['bitwise_identical_to_A']}")

    base = bench[0]
    logln(f"[D-1] 현행 구성 A 진짜 CPU-시간 = {base['cpu_s']:.1f}s / wall {base['wall_s']:.1f}s "
          f"→ **실효 병렬도 {base['effective_parallelism']:.2f}** "
          f"(logical {logical} 기준 {base['eff_vs_logical']*100:.0f}% · "
          f"P코어 {p_cores} 기준 {base['eff_vs_p_cores']*100:.0f}%)")

    for r in bench:
        r["excluded_reason"] = None if r["bitwise_identical_to_A"] else \
            "비트동일 게이트 FAIL — 후보 영구 제외"
    survivors = [r for r in bench if r["excluded_reason"] is None]
    excluded = [r["name"] for r in bench if r["excluded_reason"]]
    logln(f"[D-2 비트동일 게이트] 통과 {len(survivors)}/{len(bench)} · 제외={excluded or '없음'} "
          f"(기준=구성 A, §13-3 sealed 와 이미 0-diff)")

    freeze_sha_after = sha256_file(CONFIG_FREEZE)[:16]
    assert freeze_sha_after == EXPECT_FREEZE_SHA16, f"ladder_freeze.json 변경됨: {freeze_sha_after}"
    logln(f"[D-2] ladder_freeze.json sha16 재확인 = {freeze_sha_after} (파일 무수정)")

    best = min(survivors, key=lambda r: r["wall_s"])
    logln(f"[D-2] **CFG_BEST = 구성 {best['name']}** ({best['label']}) wall {best['wall_s']:.1f}s "
          f"— 구성 A 대비 {base['wall_s']/best['wall_s']:.2f}× 가속")

    st["d12"] = {"configs": configs, "bench": bench, "ref_sha256": ref_sha,
                 "cfg_best": best["name"], "excluded": excluded,
                 "freeze_sha16_after": freeze_sha_after,
                 "bench_fold": {"fold": FOLD_FOR_BENCH, "n_train": int(len(tr)),
                                "n_test": int(len(te)), "dim_M2b": int(Xtr.shape[1]),
                                "permutation": "identity", "n_estimators": RF_N_ESTIMATORS_FULL},
                 "p_cores": p_cores, "logical": logical, "ram_bytes": ram, "ts_kst": now_kst()}
    save_state(st)
    return st


def stage_d3(st):
    logical = st["d12"]["logical"]
    ram = st["d12"]["ram_bytes"]
    best = [c for c in st["d12"]["bench"] if c["name"] == st["d12"]["cfg_best"]][0]

    logln("=" * 78)
    logln(f"[D-3] 워커 수 스윕 {list(WORKER_SWEEP)} — ⚠️ **타이밍 프록시** "
          f"n_estimators={RF_N_ESTIMATORS_PROXY}(동결값 {RF_N_ESTIMATORS_FULL} 아님). "
          f"OOF 미저장 · 어떤 분석·판정·null 분포에도 미투입 · D-4에서 전량 재확인.")

    n_max = max(WORKER_SWEEP)
    probe2_seeds = [PROBE2_SEED_BASE + i for i in range(n_max)]
    for s in probe2_seeds:
        assert s > MAIN_SEED_NAMESPACE_MAX and s not in PROBE1_SEEDS and s not in RESERVED_SEEDS
    logln(f"[seed 격리] PROBE2 {probe2_seeds[0]}~{probe2_seeds[-1]} — 본실행 namespace"
          f"(≤{MAIN_SEED_NAMESPACE_MAX})·프로브1{sorted(PROBE1_SEEDS)}·예약 seed 교집합 0 (assert PASS)")

    proc, g1 = [], {}
    for nw in WORKER_SWEEP:
        cores = max(1, logical // nw)
        scaled = scale_cfg(best, cores)
        seeds = [PROBE2_SEED_BASE + i for i in range(nw)]
        payloads = [{"seed": s, "mode": "global", "cfg": scaled, "folds": [FOLD_FOR_BENCH],
                     "n_estimators": RF_N_ESTIMATORS_PROXY} for s in seeds]
        res, wall, cpu = run_pool(nw, payloads, cores)

        walls = [r["wall_s"] for r in res]
        recurring = [r["recurring_s"] for r in res]
        setups = [r["setup_s"] for r in res]
        fold_walls = [r["folds"][0]["fold_wall_s"] for r in res]
        perm_builds = [r["perm_build_s"] for r in res]
        rss_sum = sum(r["peak_rss_bytes"] for r in res)
        for r in res:
            g1.setdefault(r["seed"], []).append({"workers": nw, "sha": r["folds"][0]["pred_sha256"]})

        # ── D-3 보정: 처리량 = w / wall_max (마지막 워커 완료 기준). 평균 기반 금지. ──
        wall_max = float(max(walls))
        wall_med = float(np.median(walls))
        wall_min = float(min(walls))
        recurring_max = float(max(recurring))          # setup 상각 후에도 **max** 기준
        rec = {"workers": nw, "cores_per_worker": cores, "scaled_cfg": scaled,
               "thread_env_value": cores, "seeds": seeds,
               "wall_total_s": wall, "cpu_total_s": cpu,
               "per_worker_wall_s": walls, "per_worker_setup_s": setups,
               "per_worker_recurring_s": recurring,
               # 워커별 wall 분포 — 워커 수마다 보고(D-3 보정)
               "worker_wall_min_s": wall_min,
               "worker_wall_median_s": wall_med,
               "worker_wall_max_s": wall_max,
               "worker_wall_spread_s": wall_max - wall_min,
               "worker_wall_spread_over_median": (wall_max - wall_min) / wall_med if wall_med else None,
               "worker_wall_stat_note": ("min/median 은 **기술통계**(워커 간 불균등 진단)일 뿐 "
                                         "처리량·투영에 투입하지 않는다."),
               # 처리량 = w / wall_max — 정의 1개만 사용
               "wall_max_s": wall_max,
               "recurring_max_s": recurring_max,
               "throughput_perm_per_sec": nw / wall_max,
               "throughput_perm_per_sec_amortized": nw / max(recurring_max, 1e-9),
               "throughput_definition": ("w / wall_max — wall_max = 워커 중 **마지막 완료** wall. "
                                         "평균·중앙값 기반 처리량 계산 금지(D-3 보정)."),
               "amortized_definition": ("w / max(per_worker_recurring_s) — recurring = 워커 자신의 "
                                        "wall − 자신의 setup(프로세스당 1회 데이터 로드, 본실행에서 "
                                        "permutation 수로 상각). 워커별 값에서 max 를 취하므로 "
                                        "평균 기반이 아니다."),
               # 투영용 fold 단가·permutation 빌드도 max 기준(평균 금지)
               "max_fold_wall_s": float(max(fold_walls)),
               "max_perm_build_s": float(max(perm_builds)),
               "per_worker_fold_wall_s": fold_walls,
               "median_fold_wall_s": float(np.median(fold_walls)),
               "median_perm_build_s": float(np.median(perm_builds)),
               "sum_peak_rss_bytes": rss_sum, "sum_peak_rss_gb": rss_sum / 1e9,
               "sum_peak_rss_gib": rss_sum / 2**30,
               "ram_budget_ok": bool(rss_sum <= ram * RAM_BUDGET_FRAC),
               "pred_sha256": {str(r["seed"]): r["folds"][0]["pred_sha256"] for r in res},
               "timing_proxy": True, "n_estimators_proxy": RF_N_ESTIMATORS_PROXY}
        proc.append(rec)
        logln(f"[D-3 워커 {nw:2d}] 코어/워커 {cores} (env={cores}) · RF n_jobs={scaled['rf_n_jobs']} "
              f"MOC n_jobs={scaled['moc_n_jobs']} · 풀 wall {wall:7.1f}s · "
              f"**처리량 = w/wall_max = {rec['throughput_perm_per_sec']*3600:6.2f} perm/h** "
              f"(상각 {rec['throughput_perm_per_sec_amortized']*3600:6.2f}) · "
              f"워커 wall min/med/max {wall_min:.0f}/{wall_med:.0f}/{wall_max:.0f}s · "
              f"(max−min)/median = {rec['worker_wall_spread_over_median']*100:.1f}% · "
              f"합계 peak RSS {rss_sum/2**30:.2f}GiB (예산 {ram*RAM_BUDGET_FRAC/2**30:.1f}GiB "
              f"내={rec['ram_budget_ok']})")

    g1_detail = []
    for s, obs in sorted(g1.items()):
        shas = {o["sha"] for o in obs}
        g1_detail.append({"seed": s, "n_observations": len(obs), "n_distinct_sha": len(shas),
                          "invariant": len(shas) == 1,
                          "workers_seen": sorted(o["workers"] for o in obs)})
    multi = [x for x in g1_detail if x["n_observations"] > 1]
    g1_pass = all(x["invariant"] for x in multi)
    logln(f"[D-3 G1 동시성 불변성] 복수 워커수에서 관측된 seed {len(multi)}개 · 전부 sha 동일={g1_pass}")
    if not g1_pass:
        logln("[D-3] ❌ G1 위반 — 프로세스 병렬 경로 **전체 폐기**, 단일 프로세스 구성으로 회귀 후 보고")

    eligible = [p for p in proc if p["ram_budget_ok"]]
    w_best = max(eligible, key=lambda p: p["throughput_perm_per_sec_amortized"])["workers"] \
        if (eligible and g1_pass) else 1
    logln(f"[D-3] **W_BEST = {w_best}** (RAM 게이트 통과 중 상각 처리량 최대 — w/max(recurring) 기준)")

    dump_json(os.path.join(PROXY_DIR, "worker_sweep_proxy.json"), {
        "NOT_AN_ANALYSIS_RESULT": True,
        "timing_proxy": True, "n_estimators_proxy": RF_N_ESTIMATORS_PROXY,
        "frozen_n_estimators": RF_N_ESTIMATORS_FULL,
        "warning": ("이 파일은 **타이밍 전용**이다. OOF 미저장 · 어떤 분석·판정·null 분포에도 "
                    "투입되지 않는다. 예측 sha256 은 G1 동시성 불변성 검사용 지문일 뿐이며 "
                    "동결 레시피(300 trees)의 예측이 아니다."),
        "throughput_definition": "w / wall_max (마지막 워커 완료 기준) — 평균 기반 계산 금지",
        "core_assignment_rule": CORE_ASSIGNMENT_RULE,
        "ts_kst": now_kst(), "sweep": proc, "G1": {"pass": g1_pass, "detail": g1_detail},
    })
    st["d3"] = {"sweep": proc, "g1_pass": g1_pass, "g1_detail": g1_detail,
                "w_best": w_best, "probe2_seeds": probe2_seeds, "ts_kst": now_kst()}
    save_state(st)
    return st


def stage_d4(st):
    logical = st["d12"]["logical"]
    ram = st["d12"]["ram_bytes"]
    best = [c for c in st["d12"]["bench"] if c["name"] == st["d12"]["cfg_best"]][0]
    w_best = st["d3"]["w_best"]
    cores = max(1, logical // w_best)
    scaled = scale_cfg(best, cores)

    logln("=" * 78)
    logln(f"[D-4] 전량 재확인 — 구성 {best['name']} × n_estimators={RF_N_ESTIMATORS_FULL}(동결값). "
          f"**D-4a 단독(w=1) baseline** → **D-4b 병렬(w={w_best}) 처리량** 2단 측정.")

    # ── D-4a 단독 baseline (열감쇠·지속부하 baseline은 이 값**만** 사용) ─────────────
    solo_cores = logical
    solo_cfg = scale_cfg(best, solo_cores)
    logln(f"[D-4a 단독] w={SOLO_WORKERS} · 코어 {solo_cores} · identity permutation 1건 완주"
          f"({N_FOLD} fold) — 열감쇠·지속부하 baseline 전용 + 0-diff 증명")
    with PowerWatcher("D-4a 단독 baseline") as pw_solo:
        solo_res, solo_wall, solo_cpu = run_pool(
            SOLO_WORKERS,
            [{"seed": 0, "mode": "identity", "cfg": solo_cfg, "folds": list(range(N_FOLD)),
              "n_estimators": RF_N_ESTIMATORS_FULL}],
            solo_cores)
    solo = solo_res[0]
    solo_folds = [f["fold_wall_s"] for f in solo["folds"]]
    solo_fold0_sha = solo["folds"][FOLD_FOR_BENCH]["pred_sha256"]
    solo_zero_diff = bool(solo_fold0_sha == st["d12"]["ref_sha256"])
    solo_rss = int(solo["peak_rss_bytes"])

    # 열 감쇠·지속부하 = **단독 런 값만**
    decay = (solo_folds[-1] - solo_folds[0]) / solo_folds[0]
    sustained_s = solo["recurring_s"]
    sustained_ok = bool(sustained_s >= SUSTAINED_LOAD_MIN_SEC)
    logln(f"[D-4a 0-diff] 단독 identity fold {FOLD_FOR_BENCH} sha={solo_fold0_sha[:16]} vs "
          f"D-2 구성 A 기준 {st['d12']['ref_sha256'][:16]} → 비트동일={solo_zero_diff}")
    logln(f"[D-4a 열감쇠 baseline] fold별 wall {[f'{x:.0f}s' for x in solo_folds]} → "
          f"첫→마지막 **{decay*100:+.1f}%** · 지속부하 {sustained_s:.0f}s "
          f"(하한 {SUSTAINED_LOAD_MIN_SEC:.0f}s 충족={sustained_ok}) · "
          f"peak RSS {solo_rss/2**30:.2f}GiB")
    if not sustained_ok:
        logln(f"[D-4a] ⚠️ 단독 지속부하 {sustained_s:.0f}s < 하한 {SUSTAINED_LOAD_MIN_SEC:.0f}s — "
              "열감쇠 추정 신뢰구간 넓음(한계로 기록).")

    # ── D-4b 병렬 처리량 (baseline 아님) ──────────────────────────────────────────
    if w_best > 1:
        logln(f"[D-4b 병렬] 워커 {w_best} × 코어/워커 {cores} · 워커0=identity(**0-diff 검증 전용**, "
              f"열감쇠·지속부하 baseline 미투입) · 워커1~{w_best-1}=global permutation")
        payloads = [{"seed": 0, "mode": "identity", "cfg": scaled, "folds": list(range(N_FOLD)),
                     "n_estimators": RF_N_ESTIMATORS_FULL}]
        for i in range(1, w_best):
            payloads.append({"seed": PROBE2_SEED_BASE + i, "mode": "global", "cfg": scaled,
                             "folds": list(range(N_FOLD)), "n_estimators": RF_N_ESTIMATORS_FULL})
        with PowerWatcher(f"D-4b 병렬 w={w_best}") as pw_par:
            res, wall, cpu = run_pool(w_best, payloads, cores)
        par_report = pw_par.report()
        parallel_measured = True
    else:
        logln("[D-4b 병렬] W_BEST=1 → 병렬 배치가 단독 런과 동일 구성. 재실행 없이 D-4a 결과를 "
              "처리량 산출에 재사용(전원 샘플·0-diff 동일 근거).")
        res, wall, cpu = solo_res, solo_wall, solo_cpu
        par_report = pw_solo.report()
        parallel_measured = False

    ident = res[0]
    fold0_sha = ident["folds"][FOLD_FOR_BENCH]["pred_sha256"]
    zero_diff = bool(fold0_sha == st["d12"]["ref_sha256"])
    logln(f"[D-4b 0-diff] 병렬 워커0(identity) fold {FOLD_FOR_BENCH} sha={fold0_sha[:16]} → "
          f"비트동일={zero_diff} (이 워커의 wall 은 오버서브 상태 측정치 — baseline 미사용)")

    # 처리량 = w / wall_max (마지막 워커 완료 기준) — 평균 기반 금지(D-3 보정과 동일 정의)
    per_perm_walls = [r["recurring_s"] for r in res]
    perm_wall_max = float(max(per_perm_walls))
    rss_sum = sum(r["peak_rss_bytes"] for r in res)
    ram_ok = bool(rss_sum <= ram * RAM_BUDGET_FRAC)
    logln(f"[D-4b 실측] permutation당 wall(**max**, setup 제외) {perm_wall_max:.1f}s · "
          f"min/med {min(per_perm_walls):.1f}/{np.median(per_perm_walls):.1f}s · "
          f"풀 wall {wall:.1f}s · 총 CPU {cpu:.1f}s · "
          f"처리량 = {len(res)}/{perm_wall_max:.1f}s = "
          f"{len(res)/perm_wall_max*3600:.2f} perm/h · "
          f"합계 peak RSS {rss_sum/2**30:.2f}GiB (예산내={ram_ok})")

    # 프록시 오차율 — D-3 W_BEST 라운드 fold 단가(max) × (300/60) vs 전량 실측 fold 단가(max)
    row = [p for p in st["d3"]["sweep"] if p["workers"] == w_best][0]
    scale = RF_N_ESTIMATORS_FULL / RF_N_ESTIMATORS_PROXY
    proxy_fold_pred = row["max_fold_wall_s"] * scale
    meas_folds = [f["fold_wall_s"] for r in res for f in r["folds"]]
    meas_fold_max = float(max(meas_folds))
    proxy_err = (proxy_fold_pred - meas_fold_max) / meas_fold_max
    proxy_ok = bool(abs(proxy_err) <= PROXY_ERROR_TOL)
    logln(f"[D-4 프록시 검증] 프록시 예측 fold 단가 {proxy_fold_pred:.1f}s "
          f"(= 60-tree fold max {row['max_fold_wall_s']:.1f}s × {scale:.0f}) vs "
          f"전량 실측 fold max {meas_fold_max:.1f}s → **오차 {proxy_err*100:+.1f}%** "
          f"(허용 ±{PROXY_ERROR_TOL*100:.0f}% · 통과={proxy_ok})")
    if not proxy_ok:
        logln("[D-4] ⚠️ 프록시 오차 허용치 초과 — 프록시 기각. 투영은 **전량 실측치만** 사용한다.")

    solo_report = pw_solo.report()
    power_valid = bool(solo_report["measurement_valid"] and par_report["measurement_valid"])
    logln(f"[D-4 전원 구간] 단독: AC유지={solo_report['ac_power_held_entire_phase']} "
          f"powermode={solo_report['powermode_values_seen']} 샘플{solo_report['n_samples']}건 · "
          f"병렬: AC유지={par_report['ac_power_held_entire_phase']} "
          f"powermode={par_report['powermode_values_seen']} 샘플{par_report['n_samples']}건 → "
          f"측정 유효={power_valid}")
    if not power_valid:
        logln("[D-4] ⚠️ 지속부하 구간 중 전원/저전력 상태 변동 — 이 구간 wall-clock 은 비교 불가. "
              "AC 연결·powermode=0 확인 후 D-4 재실행 필요.")

    st["d4"] = {"config": best["name"], "workers": w_best, "cores_per_worker": cores,
                "scaled_cfg": scaled, "n_estimators": RF_N_ESTIMATORS_FULL,
                "baseline_rule": ("열감쇠·지속부하 baseline = **D-4a 단독(w=1) 1 permutation 완주 값만**. "
                                  "D-4b 병렬 워커0(identity)의 wall 은 오버서브스크립션 상태 측정치이므로 "
                                  "baseline 금지 — 0-diff 검증 용도로만 사용."),
                "solo_baseline": {
                    "workers": SOLO_WORKERS, "cores": solo_cores, "scaled_cfg": solo_cfg,
                    "mode": "identity", "wall_total_s": solo_wall, "cpu_total_s": solo_cpu,
                    "setup_s": solo["setup_s"], "perm_build_s": solo["perm_build_s"],
                    "recurring_s": solo["recurring_s"], "fold_walls_s": solo_folds,
                    "peak_rss_bytes": solo_rss, "peak_rss_gib": solo_rss / 2**30,
                    "fold0_sha256": solo_fold0_sha,
                    "zero_diff_vs_d2_configA": solo_zero_diff,
                    "power": solo_report},
                "parallel": {
                    "measured_separately": parallel_measured,
                    "wall_total_s": wall, "cpu_total_s": cpu,
                    "n_workers_run": len(res),
                    "per_permutation_recurring_s": per_perm_walls,
                    "permutation_recurring_max_s": perm_wall_max,
                    "permutation_recurring_min_s": float(min(per_perm_walls)),
                    "permutation_recurring_median_s": float(np.median(per_perm_walls)),
                    "throughput_perm_per_sec": len(res) / perm_wall_max,
                    "throughput_definition": "w / max(per_worker_recurring_s) — 마지막 완료 기준",
                    "worker0_identity_role": "0-diff 검증 전용 — baseline·열감쇠 미투입",
                    "power": par_report},
                "wall_total_s": wall, "cpu_total_s": cpu,
                "per_permutation_recurring_s": per_perm_walls,
                "max_permutation_recurring_s": perm_wall_max,
                "per_worker_setup_s": [r["setup_s"] for r in res],
                "fold_walls": [[f["fold_wall_s"] for f in r["folds"]] for r in res],
                "max_fold_wall_s": meas_fold_max,
                "median_fold_wall_s": float(np.median(meas_folds)),
                "sum_peak_rss_bytes": rss_sum, "sum_peak_rss_gib": rss_sum / 2**30,
                "ram_budget_ok": ram_ok,
                "zero_diff_vs_d2_configA": bool(zero_diff and solo_zero_diff),
                "identity_fold0_sha256": fold0_sha,
                "proxy_check": {"proxy_predicted_fold_s": proxy_fold_pred,
                                "measured_fold_s": meas_fold_max,
                                "basis": "max fold wall (평균 기반 아님)",
                                "error_frac": proxy_err, "tolerance": PROXY_ERROR_TOL,
                                "proxy_accepted": proxy_ok},
                "thermal": {"source": "D-4a 단독(w=1) 1 permutation 완주 — baseline 규칙 준수",
                            "solo_fold_walls_s": solo_folds,
                            "decay_frac": float(decay), "median_decay_frac": float(decay),
                            "sustained_load_s": float(sustained_s),
                            "sustained_min_s": SUSTAINED_LOAD_MIN_SEC,
                            "sustained_ok": sustained_ok,
                            "excluded_from_baseline": ("D-4b 병렬 전 워커(워커0 identity 포함) — "
                                                       "오버서브스크립션 상태 측정치")},
                "power_measurement_valid": power_valid,
                "power_phases": ([solo_report, par_report] if parallel_measured
                                 else [solo_report]),
                "power_after": par_report["samples"][-1] if par_report["samples"] else None,
                "ts_kst": now_kst()}
    save_state(st)
    return st


def stage_d5(st):
    logical, ram = st["d12"]["logical"], st["d12"]["ram_bytes"]
    p_cores = st["d12"]["p_cores"]
    base = st["d12"]["bench"][0]
    best_name = st["d12"]["cfg_best"]
    best = [c for c in st["d12"]["bench"] if c["name"] == best_name][0]
    d4 = st["d4"]
    B = sap_null.NULL_B
    n_perm_total = 2 * B
    decay = d4["thermal"]["median_decay_frac"]
    decay_factor = 1.0 + max(decay, 0.0)          # 감쇠(느려짐)만 보수적으로 반영

    logln("=" * 78)
    logln(f"[D-5] 재산정 — NULL_B={B} × 2모드 = {n_perm_total} permutation × {N_FOLD} fold. "
          f"열 감쇠 계수 {decay_factor:.3f} 적용(감쇠율 {decay*100:+.1f}% · "
          f"출처={d4['thermal']['source']})")
    logln("[D-5] 처리량 정의 = w / wall_max(마지막 워커 완료) — 평균 기반 계산 미사용. "
          "블록 C wall-clock(배터리·저전력 구간) 미투입.")

    table = []
    # (a) 구성 A × 워커 1 = 현행 기준 (D-2 실측 fold 단가 × 5)
    a_perm_s = base["wall_s"] * N_FOLD
    table.append({
        "config": "A", "workers": 1, "source": "D-2 실측(fold 단가 × 5)",
        "wall_per_permutation_s": a_perm_s,
        "throughput_perm_per_hour": 1 / a_perm_s * 3600,
        "total_wall_days_raw": a_perm_s * n_perm_total / 86400,
        "total_wall_days_thermal": a_perm_s * n_perm_total * decay_factor / 86400,
        "total_cpu_hours": base["cpu_s"] * N_FOLD * n_perm_total / 3600,
        "sum_peak_rss_gib": base["peak_rss_self_bytes_cumulative"] / 2**30,
        "ram_budget_ok": True, "bitwise_gate": True, "measured_full": True,
    })
    # (b) CFG_BEST × 각 워커 수 — D-3 프록시(fold 단가 **max**) 스케일링 + D-4 전량 실측 앵커 보정
    tree_scale = RF_N_ESTIMATORS_FULL / RF_N_ESTIMATORS_PROXY
    anchor_row = [p for p in st["d3"]["sweep"] if p["workers"] == d4["workers"]][0]
    anchor = d4["max_fold_wall_s"] / (anchor_row["max_fold_wall_s"] * tree_scale)
    logln(f"[D-5] 프록시→전량 앵커 보정계수 = {anchor:.3f} "
          f"(W_BEST={d4['workers']} 지점 전량 실측 fold max {d4['max_fold_wall_s']:.1f}s / "
          f"프록시 예측 {anchor_row['max_fold_wall_s'] * tree_scale:.1f}s)")
    cpu_per_fold_best = d4["cpu_total_s"] / (max(1, d4["parallel"]["n_workers_run"]) * N_FOLD)
    for p in st["d3"]["sweep"]:
        if p["workers"] == d4["workers"]:
            full_perm_s = d4["max_permutation_recurring_s"]        # 전량 실측치(max) 우선
            src, measured = "D-4 전량 실측(wall_max)", True
        else:
            fold_s = p["max_fold_wall_s"] * tree_scale * anchor
            full_perm_s = p["max_perm_build_s"] + N_FOLD * fold_s
            src, measured = "D-3 프록시(wall_max) × 앵커 보정", False
        thr_perm_per_s = p["workers"] / full_perm_s
        total_s = n_perm_total / thr_perm_per_s
        table.append({
            "config": best_name, "workers": p["workers"],
            "cores_per_worker": p["cores_per_worker"],
            "source": src,
            "wall_per_permutation_s": full_perm_s,
            "throughput_perm_per_hour": thr_perm_per_s * 3600,
            "total_wall_days_raw": total_s / 86400,
            "total_wall_days_thermal": total_s * decay_factor / 86400,
            "total_cpu_hours": (cpu_per_fold_best * N_FOLD * n_perm_total / 3600
                                if measured else None),
            "total_cpu_hours_note": (None if measured else
                                     "CPU-시간은 전량 실측 지점(W_BEST)에서만 보고 — "
                                     "프록시 행은 wall 투영만 유효"),
            "sum_peak_rss_gib": p["sum_peak_rss_gib"],
            "ram_budget_ok": p["ram_budget_ok"],
            "bitwise_gate": bool(st["d3"]["g1_pass"] and best["bitwise_identical_to_A"]),
            "measured_full": measured,
            # 워커 간 불균등(P/E 비대칭) 진단 — 투영 근거의 산포
            "worker_wall_min_s": p["worker_wall_min_s"],
            "worker_wall_median_s": p["worker_wall_median_s"],
            "worker_wall_max_s": p["worker_wall_max_s"],
            "worker_wall_spread_over_median": p["worker_wall_spread_over_median"],
            "throughput_basis": "w / wall_max (마지막 워커 완료) — 평균 기반 아님",
        })

    for t in table:
        spread = t.get("worker_wall_spread_over_median")
        logln(f"[D-5] 구성 {t['config']} × 워커 {t['workers']:2d}: perm당 "
              f"{t['wall_per_permutation_s']:8.1f}s · 처리량 {t['throughput_perm_per_hour']:6.2f} perm/h · "
              f"총 wall **{t['total_wall_days_thermal']:6.2f}일**(열감쇠 반영, raw "
              f"{t['total_wall_days_raw']:.2f}일) · 합계 RSS {t['sum_peak_rss_gib']:.2f}GiB · "
              f"RAM게이트={t['ram_budget_ok']} · 비트동일={t['bitwise_gate']} · "
              f"워커wall 산포={'n/a' if spread is None else f'{spread*100:.1f}%'} · "
              f"[{t['source']}]")

    eligible = [t for t in table if t["ram_budget_ok"] and t["bitwise_gate"]]
    rec = min(eligible, key=lambda t: t["total_wall_days_thermal"]) if eligible else None
    over_7d = (rec is None) or (rec["total_wall_days_thermal"] > STOP_DAYS)

    total_cpu_hours_A = base["cpu_s"] * N_FOLD * n_perm_total / 3600.0
    total_wall_hours_A = base["wall_s"] * N_FOLD * n_perm_total / 3600.0
    logln(f"[D-1 정정] 프로브1 기록 '374시간'은 `n_jobs=-1` 18스레드 **wall-clock**이며 CPU-시간이 아님. "
          f"실측 재산정: 구성 A fold당 CPU {base['cpu_s']:.1f}s → 2,000 permutation 총 "
          f"**CPU-시간 {total_cpu_hours_A:.0f}h**; fold당 wall {base['wall_s']:.1f}s → 총 "
          f"**wall {total_wall_hours_A:.0f}h ({total_wall_hours_A/24:.1f}일)**")

    if rec:
        logln(f"[D-5 권장] 구성 **{rec['config']}** × 워커 **{rec['workers']}** → 예상 총 wall "
              f"**{rec['total_wall_days_thermal']:.2f}일** · 7일 초과={over_7d}")
    if over_7d:
        logln("[D-5 정지조건] 권장 구성 예상 wall > 7일 → **Mac 단독 부적합** 판정. "
              "§13-4 본런 프롬프트 요청 없이 근거 표만 보고하고 정지.")
    if not d4["power_measurement_valid"]:
        logln("[D-5] ⚠️ D-4 지속부하 구간 전원 상태 불안정 — 본 투영표의 wall-clock 은 **비교 불가**. "
              "권장 구성은 잠정이며 AC·powermode=0 조건에서 D-4 재측정 후 확정한다.")

    st["d5"] = {"table": table, "recommendation": rec, "over_7_days": bool(over_7d),
                "decay_factor": decay_factor, "n_perm_total": n_perm_total,
                "anchor_correction": anchor,
                "throughput_definition": ("w / wall_max — 워커 중 마지막 완료 wall 기준. "
                                          "평균·중앙값 기반 처리량 계산 금지(D-3 보정)."),
                "thermal_baseline_source": d4["thermal"]["source"],
                "power_measurement_valid": d4["power_measurement_valid"],
                "projection_valid": bool(d4["power_measurement_valid"]),
                "excluded_inputs": ["블록 C(§13-5 반복2·3·consensus) wall-clock — 배터리·저전력 "
                                    "모드 구간 측정치라 비교 불가(바이트 동일성에는 영향 없음)"],
                "d1_correction": {"total_cpu_hours_A": total_cpu_hours_A,
                                  "total_wall_hours_A": total_wall_hours_A,
                                  "total_wall_days_A": total_wall_hours_A / 24},
                "ts_kst": now_kst()}
    save_state(st)
    return st


def stage_d6(st):
    """산출 파일 + run_manifest_draft parallel_policy 갱신. 문서 기입은 별도 스크립트."""
    d0, d12, d3, d4, d5 = st["d0"], st["d12"], st["d3"], st["d4"], st["d5"]
    hw = d0["hardware"]

    # sealed 불변 재확인
    snap_after = guard_snapshot()
    unchanged = (snap_after == d0["sealed_guard"])
    changed = [k for k in set(snap_after) | set(d0["sealed_guard"])
               if snap_after.get(k) != d0["sealed_guard"].get(k)]
    logln(f"[D-6 sealed 불변] 블록 C 산출물 {len(snap_after)}개 sha256 불변={unchanged} "
          f"{'· 변동=' + str(changed) if changed else ''}")
    freeze_after = sha256_file(CONFIG_FREEZE)[:16]
    assert freeze_after == EXPECT_FREEZE_SHA16
    logln(f"[D-6] ladder_freeze.json sha16 = {freeze_after} (불변)")

    pub = {
        "_scope": "블록 D(개정) — 측정 전용. 시간·메모리·코어 수·해시·PASS/FAIL만. AP·Δ·T_b·p 없음.",
        "ts_kst": now_kst(), "probe_only": PROBE_ONLY,
        "enters_null_distribution": ENTERS_NULL_DISTRIBUTION,
        "power_state": {"start": d0["power"], "end": d4["power_after"],
                        "sustained_load_phases": d4["power_phases"],
                        "measurement_valid": d4["power_measurement_valid"],
                        "rule": ("D-4 보정 — 지속부하 구간의 전원 상태(AC/배터리)·powermode·시각을 "
                                 f"{POWER_SAMPLE_INTERVAL_S:.0f}s 주기로 샘플해 기록한다.")},
        "throughput_definition": {
            "formula": "처리량 = w / wall_max",
            "wall_max": "워커 중 **마지막 완료** 시각 기준 wall (= max(per_worker_wall_s))",
            "banned": "평균·중앙값 기반 처리량 계산 금지 — min/median 은 기술통계 보고용으로만 사용",
            "amortized": ("setup(프로세스당 1회 데이터 로드)을 뺀 recurring 기준 처리량도 "
                          "max(per_worker_recurring_s) 로 계산 — 본실행에서 setup 은 "
                          "permutation 수로 상각되므로 투영에는 recurring 기준을 쓴다."),
        },
        "core_assignment_rule": CORE_ASSIGNMENT_RULE,
        "excluded_inputs": {
            "block_C_wallclock": {
                "excluded": True,
                "reason": ("블록 C(§13-5 반복2·3 + consensus)는 배터리 전원·저전력 모드"
                           "(powermode=1)에서 실행되어 wall-clock 비교 불가. 블록 D 및 §13-4 "
                           "총시간 추정에 투입 금지."),
                "byte_identity_note": ("전원·클럭 상태는 산출물 **바이트 동일성에 영향 없음** — "
                                       "RF random_state·연산 순서·부동소수 결과가 전원 상태에 "
                                       "의존하지 않으므로 sealed sha256 및 부호 판정은 유효하다."),
                "evidence": "experiments/runs/v3_confirm_rep23/power_state_block_C.json",
                "verified_no_ingest": True,
            },
        },
        "hardware": {"performance_cores": hw["cpu"]["performance_cores_physical"],
                     "efficiency_cores": hw["cpu"]["efficiency_cores_physical"],
                     "logical": hw["cpu"]["logical_total"],
                     "ram_bytes": hw["memory"]["bytes"],
                     "ram_budget_frac": RAM_BUDGET_FRAC,
                     "ram_budget_gib": hw["memory"]["bytes"] * RAM_BUDGET_FRAC / 2**30},
        "seed_isolation": {"probe2_seeds": d3["probe2_seeds"],
                           "main_namespace_max": MAIN_SEED_NAMESPACE_MAX,
                           "probe1_seeds": sorted(PROBE1_SEEDS),
                           "reserved_seeds": sorted(RESERVED_SEEDS),
                           "intersection": 0, "asserted": True},
        "bench_fold": d12["bench_fold"],
        "D1_true_cpu_time": {
            "config": "A (현행)", "wall_s": d12["bench"][0]["wall_s"],
            "cpu_s": d12["bench"][0]["cpu_s"],
            "cpu_self_s": d12["bench"][0]["cpu_self_s"],
            "cpu_children_s": d12["bench"][0]["cpu_children_s"],
            "effective_parallelism_cpu_over_wall": d12["bench"][0]["effective_parallelism"],
            "efficiency_vs_logical_18": d12["bench"][0]["eff_vs_logical"],
            "efficiency_vs_p_cores_6": d12["bench"][0]["eff_vs_p_cores"],
            **d5["d1_correction"],
            "correction_statement": ("프로브1 기록의 '374시간'은 n_jobs=-1 18스레드 **wall-clock**이며 "
                                     "CPU-시간이 아니다. 본 측정으로 CPU-시간을 분리 산출해 정정한다."),
        },
        "D2_config_sweep": d12["bench"],
        "D2_bitwise_gate": {
            "reference_config": "A", "reference_sha256": d12["ref_sha256"],
            "all_identical": all(r["bitwise_identical_to_A"] for r in d12["bench"]),
            "excluded_configs": d12["excluded"],
            "rule": "예측 배열 sha256 불일치 구성은 후보에서 영구 제외(docs/33·ledger 기록)",
        },
        "D3_worker_sweep": {
            "TIMING_PROXY": True, "n_estimators_proxy": RF_N_ESTIMATORS_PROXY,
            "frozen_n_estimators": RF_N_ESTIMATORS_FULL,
            "proxy_disclosure": ("워커 스윕은 n_estimators=60 타이밍 프록시로 측정했다. OOF 미저장·"
                                 "분석/판정/null 분포 미투입. D-4에서 전량 300 trees 1회로 재확인."),
            "cfg_best": d12["cfg_best"], "sweep": d3["sweep"],
            "w_best": d3["w_best"],
            "w_best_criterion": "RAM 게이트 통과 후보 중 w/max(recurring) 처리량 최대",
            "scaling_rule": ("워커당 배정 코어 = logical // workers. 내부 병렬도를 그에 맞춰 축소 "
                             "(RF 우선 배정 → 남은 슬롯 MOC). 축소 없이는 최대 324-way "
                             "오버서브스크립션이 되어 처리량이 아니라 스래싱을 측정하게 된다."),
            "core_assignment_rule": CORE_ASSIGNMENT_RULE,
            "worker_wall_distribution": [
                {"workers": p["workers"],
                 "min_s": p["worker_wall_min_s"], "median_s": p["worker_wall_median_s"],
                 "max_s": p["worker_wall_max_s"],
                 "spread_over_median": p["worker_wall_spread_over_median"],
                 "throughput_perm_per_hour": p["throughput_perm_per_sec"] * 3600,
                 "throughput_perm_per_hour_amortized": p["throughput_perm_per_sec_amortized"] * 3600}
                for p in d3["sweep"]],
        },
        "D3_G1_concurrency_invariance": {"pass": bool(d3["g1_pass"]), "detail": d3["g1_detail"],
                                         "rule": "워커 수를 바꿔도 같은 seed 예측 sha256 동일(0-diff)"},
        "D3_ram_gate": {"budget_gib": hw["memory"]["bytes"] * RAM_BUDGET_FRAC / 2**30,
                        "excluded_workers": [p["workers"] for p in d3["sweep"]
                                             if not p["ram_budget_ok"]]},
        "D4_baseline_rule": {
            "thermal_and_sustained_baseline": d4["baseline_rule"],
            "solo_baseline": d4["solo_baseline"],
            "worker0_identity": ("병렬 배치 워커0(identity)의 wall 은 오버서브스크립션 상태 "
                                 "측정치 — baseline 금지, 0-diff 검증 용도로만 사용"),
        },
        "D4_full_verification": d4,
        "D5_projection_table": d5["table"],
        "D5_recommendation": {
            "config": d5["recommendation"]["config"] if d5["recommendation"] else None,
            "workers": d5["recommendation"]["workers"] if d5["recommendation"] else None,
            "expected_total_wall_days_thermal": (d5["recommendation"]["total_wall_days_thermal"]
                                                 if d5["recommendation"] else None),
            "sum_peak_rss_gib": (d5["recommendation"]["sum_peak_rss_gib"]
                                 if d5["recommendation"] else None),
            "over_7_days": d5["over_7_days"], "stop_threshold_days": STOP_DAYS,
            "power_measurement_valid": d4["power_measurement_valid"],
            "verdict": ("전원 상태 불안정 — wall-clock 비교 불가, 권장 구성 잠정(재측정 필요)"
                        if not d4["power_measurement_valid"] else
                        "Mac 단독 부적합 — §13-4 본런 착수 금지, 근거 표만 보고 후 정지"
                        if d5["over_7_days"] else
                        "Mac 단독 실행 가능 — 본런 구성 채택은 별도 지시로만"),
            "thermal_decay_applied": d5["decay_factor"],
            "thermal_baseline_source": d5["thermal_baseline_source"],
            "throughput_definition": d5["throughput_definition"],
        },
        "sealed_guard": {"files": len(snap_after), "unchanged": unchanged, "changed": changed},
        "ladder_freeze_sha16": freeze_after,
        "not_performed": ["empirical_p 호출", "p 계산", "T_obs 비교", "null 분포", "bootstrap",
                          "sign-flip", "SESOI/TOST", "성공판정", "ladder_freeze.json 수정",
                          "§13-4 본런", "sealed 값 사람 열람", "네트워크", "data/raw 변경", "git commit"],
    }
    dump_json(os.path.join(RUN_DIR, "compute_public.json"), pub)

    dump_json(os.path.join(RUN_DIR, "config.json"), {
        "step": "§13-4 사전작업 — 블록 D(개정) Mac wall-clock 최적화 프로브2(측정 전용)",
        "probe_only": PROBE_ONLY, "enters_null_distribution": ENTERS_NULL_DISTRIBUTION,
        "probe2_seed_base": PROBE2_SEED_BASE, "seeds_used": d3["probe2_seeds"],
        "configs": d12["configs"], "worker_sweep": list(WORKER_SWEEP),
        "fold_for_bench": FOLD_FOR_BENCH,
        "rf_frozen_hyperparams": {k: v for k, v in RF_KW.items() if k != "n_jobs"},
        "rf_random_state": RF_SEED,
        "timing_proxy": {"used_in": "D-3 워커 스윕만", "n_estimators": RF_N_ESTIMATORS_PROXY,
                         "oof_saved": False, "enters_analysis": False,
                         "reverified_full_in": "D-4"},
        "runtime_override_note": ("병렬 인자(n_jobs)만 메모리상 복사본에서 override. "
                                  "ladder_freeze.json 및 RF_KW 원본 dict 는 미변경."),
        "gate0": d0["gate0"],
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__,
                     "platform": platform.platform()},
        "integrity": {"network_calls": 0, "raw_data_modified": False, "docs30_modified": False,
                      "ladder_freeze_modified": False, "sealed_values_human_read": False,
                      "empirical_p_called": False, "git_commit": False},
        "outputs": {"public": ["config.json", "compute_public.json", "run.log"],
                    "proxy": ["_proxy/worker_sweep_proxy.json (NOT_AN_ANALYSIS_RESULT)"],
                    "sealed": ["_sealed/fold_pred_reference.npy (구성 A 기준 예측 배열)"]},
    })

    # run_manifest_draft.json parallel_policy 확정 — 7일 이내일 때만
    if not d5["over_7_days"] and d5["recommendation"]:
        m = json.load(open(MANIFEST_DRAFT))
        r = d5["recommendation"]
        cfg_row = [c for c in d12["bench"] if c["name"] == r["config"]][0]
        m["parallel_policy"] = (f"CONFIRMED — 구성 {r['config']}({cfg_row['label']}) × "
                                f"워커 {r['workers']} (0-diff 증명 완료)")
        m["parallel_detail"]["confirmed_config"] = {
            "config": r["config"], "label": cfg_row["label"],
            "moc_n_jobs": cfg_row["moc_n_jobs"], "rf_n_jobs": cfg_row["rf_n_jobs"],
            "workers": r["workers"],
            "cores_per_worker": r.get("cores_per_worker"),
            "thread_env": {k: str(r.get("cores_per_worker")) for k in THREAD_ENV_KEYS},
            "expected_total_wall_days_thermal": r["total_wall_days_thermal"],
            "zero_diff_proof_hashes": {
                "D2_reference_configA_fold0_sha256": d12["ref_sha256"],
                "D4_full_identity_fold0_sha256": d4["identity_fold0_sha256"],
                "D3_G1_seed_invariant_sha256": d3["sweep"][0]["pred_sha256"][
                    str(d3["probe2_seeds"][0])],
            },
            "measured_by": "블록 D(개정) — experiments/runs/v3_null_probe2_compute/compute_public.json",
            "ts_kst": now_kst(),
        }
        dump_json(MANIFEST_DRAFT, m)
        rt = json.load(open(MANIFEST_DRAFT))
        assert rt["parallel_detail"]["confirmed_config"]["workers"] == r["workers"]
        assert rt["parallel_policy"].startswith("CONFIRMED")
        logln(f"[D-6] run_manifest_draft.json parallel_policy 확정 갱신 + 라운드트립 assert PASS")
    else:
        logln("[D-6] 7일 초과(또는 후보 없음) → run_manifest_draft.json 미갱신(초안 유지)")

    st["d6"] = {"sealed_unchanged": unchanged, "changed": changed,
                "freeze_sha16": freeze_after, "ts_kst": now_kst()}
    save_state(st)
    return st


# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["all", "d0", "d12", "d3", "d4", "d5", "d6"], default="all")
    args = ap.parse_args()
    t_all = time.perf_counter()
    os.makedirs(SEALED_DIR, exist_ok=True)
    os.makedirs(PROXY_DIR, exist_ok=True)

    st = load_state()
    order = ["d0", "d12", "d3", "d4", "d5", "d6"]
    todo = order if args.stage == "all" else [args.stage]
    fns = {"d0": stage_d0, "d12": stage_d12, "d3": stage_d3,
           "d4": stage_d4, "d5": stage_d5, "d6": stage_d6}

    # ── 블록 E-1 G-IDLE ─────────────────────────────────────────────────────
    #   A(하드) 최초 진입 1회 · B(하드) 모든 스테이지 직전·직후 · C(soft) 스테이지 사이.
    #   락은 **부모만** 획득한다(spawn 자식 워커는 락 로직에 접근하지 않는다).
    gidle = st.setdefault("gidle", [])
    gidle.append(gate_a_load(label="probe2:entry"))
    logln(f"[G-IDLE] A 통과 — load1={gidle[-1]['load1']:.2f}")

    try:
        for i, s in enumerate(todo):
            if i > 0:
                c = gate_c_settle(label=f"probe2:before:{s}")
                gidle.append(c)
                if c["settle_caveat"]:
                    logln(f"[G-IDLE] C settle_caveat=true (before {s}, "
                          f"load1={c['load1']:.2f}) — 측정 해석 시 유의")
            gidle.append(gate_b_exclusive(label=f"probe2:before:{s}"))
            st = fns[s](st)
            gidle.append(gate_b_exclusive(label=f"probe2:after:{s}"))
            st["gidle"] = gidle          # 스테이지가 st 를 재생성해도 게이트 기록 유지
            save_state(st)
            flush_log()
    finally:
        flush_log()

    logln(f"[블록 D] 총 경과 {time.perf_counter() - t_all:.0f}s")
    flush_log()

    if "d5" in st:
        print("\n=== 블록 D 요약 ===")
        b = st["d12"]["bench"]
        print(f"실효 병렬도(구성 A) = {b[0]['effective_parallelism']:.2f} "
              f"(logical 18 대비 {b[0]['eff_vs_logical']*100:.0f}%, P코어 6 대비 "
              f"{b[0]['eff_vs_p_cores']*100:.0f}%)")
        for r in b:
            print(f"  구성 {r['name']} {r['label']:22s} wall {r['wall_s']:8.1f}s cpu {r['cpu_s']:9.1f}s "
                  f"비트동일={r['bitwise_identical_to_A']}")
        print(f"G1 = {st['d3']['g1_pass']} · W_BEST = {st['d3']['w_best']} · "
              f"프록시 오차 {st['d4']['proxy_check']['error_frac']*100:+.1f}% · "
              f"열감쇠 {st['d4']['thermal']['median_decay_frac']*100:+.1f}%")
        for t in st["d5"]["table"]:
            print(f"  {t['config']}×{t['workers']:2d}: perm {t['wall_per_permutation_s']:8.1f}s → "
                  f"총 {t['total_wall_days_thermal']:6.2f}일 (RSS {t['sum_peak_rss_gib']:.2f}GiB, "
                  f"RAM={t['ram_budget_ok']})")
        print(f"권장 = {st['d5']['recommendation']}")
        print(f"7일 초과 = {st['d5']['over_7_days']}")


if __name__ == "__main__":
    # 배타 락은 **부모 프로세스에서만** 획득한다 (블록 E-1).
    with ComputeLock(script="null_compute_probe2.py", role="runner"):
        main()
