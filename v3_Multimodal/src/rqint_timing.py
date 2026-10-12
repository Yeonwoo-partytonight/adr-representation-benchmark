#!/usr/bin/env python3
"""rqint_timing.py — [블록 AD] RQ-int 계측: 단가·병렬·축소프로파일·예산.

⛔ 무결성 (지시서 `docs/90_rqint_timing_calibration_budget_prompt_for_vscode.md` §0)
  · **확증 예측·OOF·`_sealed/`·부호·`p_emp`·`T_obs` 는 한 번도 열지 않는다.**
    본 스크립트가 여는 데이터 경로는 `data/processed/master_X.parquet` 과
    `data/processed/master_Y.parquet` **두 개뿐**이며, 둘 다 `docs/84` §2 R1 설계가
    "result-independent 설계량"으로 명시 허용한 **라벨행렬·스캐폴드 군집구조** 용이다.
  · **예측행렬은 100% 합성**이다(`sap.synthetic._scores_from_labels` 를 실제 라벨을 조건으로 호출).
  · 본 파일은 **`sap/` 밖**에 있다 — `sap/*.py` 의 "데이터 미접근 순수 함수" 불변식을 깨지 않는다.
  · 계측 전용: **1종오류·검정력 판정 0 · `B` 확정 0 · GIN 학습 0 · 개봉 0 · 네트워크 0.**

★ `scaffold_of` 는 확증 러너의 함수를 **그대로 재사용**한다(F-SCAF, 재구현 금지).
  `from confirmatory_oof_rep1 import scaffold_of` 는 **모듈 import** 이며 데이터 경로가 아니다.
  해당 모듈은 import 시점에 데이터를 읽지 않는다(모듈 최상위 = 상수·함수 정의뿐).

실행:
  .venv/bin/python3 v3_Multimodal/src/rqint_timing.py --stage profile
  ... unit | sweep | fixture | bridge | weaknull | assemble
"""
from __future__ import annotations

import os

# ── BLAS 스레드 명시 고정 (AD-2) — numpy import **이전**이어야 효력이 있다 ──────────
_THREADS = os.environ.get("RQINT_THREADS", "1")
_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
for _v in _THREAD_VARS:
    os.environ[_v] = _THREADS

import sys                                                          # noqa: E402
import json                                                         # noqa: E402
import time                                                         # noqa: E402
import math                                                         # noqa: E402
import hashlib                                                      # noqa: E402
import argparse                                                     # noqa: E402
import platform                                                     # noqa: E402
import subprocess                                                   # noqa: E402
import threading                                                    # noqa: E402
import multiprocessing as mp                                        # noqa: E402
from datetime import datetime, timezone, timedelta                  # noqa: E402

import numpy as np                                                  # noqa: E402
import pandas as pd                                                 # noqa: E402
import psutil                                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from sap import rqint as sap_rqint                                  # noqa: E402
from sap.synthetic import _scores_from_labels                       # noqa: E402
from confirmatory_oof_rep1 import scaffold_of                       # noqa: E402  (F-SCAF 재사용)
import rqint_reduced_fixture as rfix                                # noqa: E402

KST = timezone(timedelta(hours=9))

PROC = os.path.join(ROOT, "data", "processed")
F_MASTER_X = os.path.join(PROC, "master_X.parquet")     # ← 허용 데이터 경로 1/2
F_MASTER_Y = os.path.join(PROC, "master_Y.parquet")     # ← 허용 데이터 경로 2/2
OUT_DIR = os.path.join(ROOT, "experiments", "rqint")
PARTS = os.path.join(OUT_DIR, "_parts")

# ── 사전 고정 상수 (실행 전 확정 — 결과를 보고 바꾸지 않는다) ─────────────────────
EXPECT_N, EXPECT_K, EXPECT_G = 1092, 370, 732
SEEDS_S = (1, 2, 3)                 # 시드 인덱스 s (D16) — 확증 학습시드 값이 아님
N_REPS = 3                          # repeat 축(D3)
BASE_STRENGTH = 1.1                 # 합성 예측 기저 강도(rqint_synthetic 규약 계승)
N_TARGET, K_TARGET = 400, 60        # F-C03 축소규모
WORKERS = (1, 3, 6, 9, 12, 18)      # AD-3 스윕
SWEEP_R = 36                        # 1·3·6·9·12·18 로 나누어떨어짐(워커당 동일 부하)
SWEEP_NCOIN_SMALL = 60
SWEEP_NCOIN_FULL = 9
THERMAL_MIN_SECONDS = 600.0         # AD-2 지속부하 하한
WEAKNULL_R = 200                    # AD-5 복제 수(지시 하한 ≥200)
WEAKNULL_NCOIN = 300                # AD-5 내부 순열 수(지시 하한 ≥300)
BRIDGE_R = 10                       # AD-4-4 bridge smoke 복제 수
BRIDGE_NCOIN = 300
TARGET_DELTAS = (0.01, 0.03)        # AD-5 공통효과 목표 Δ
RAM_BUDGET_GIB = 38.4               # F-CORE (docs/33 블록 D)
RAM_GATE_FRAC = 0.80                # AD-3 RAM 게이트

NOT_ANALYSIS = "NOT_AN_ANALYSIS_RESULT"


def now_kst():
    return datetime.now(KST).isoformat(timespec="seconds")


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=_native)
    return path


def _native(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(str(type(o)))


def load_part(name):
    with open(os.path.join(PARTS, f"{name}.json")) as f:
        return json.load(f)


# ── 환경 실측 ────────────────────────────────────────────────────────────────
def env_snapshot():
    def _sh(cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                  timeout=20).stdout.strip()
        except Exception as e:                                  # pragma: no cover
            return f"<err {e}>"
    try:
        from threadpoolctl import threadpool_info
        tp = [{k: v for k, v in d.items() if k in ("user_api", "internal_api", "num_threads", "prefix")}
              for d in threadpool_info()]
    except Exception as e:                                      # pragma: no cover
        tp = f"<threadpoolctl unavailable: {e}>"
    la = os.getloadavg()
    return {
        "when_kst": now_kst(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": __import__("sklearn").__version__,
        "logical_cores": os.cpu_count(),
        "physical_cores": int(_sh("sysctl -n hw.physicalcpu") or 0),
        "mem_total_gib": round(psutil.virtual_memory().total / 2**30, 3),
        "ram_budget_gib": RAM_BUDGET_GIB,
        "pmset_powermode": _sh("pmset -g | awk '/powermode/{print $2}'"),
        "pmset_ps": _sh("pmset -g ps | head -3"),
        "thermal_pressure": _sh("sysctl -n machdep.xcpm.cpu_thermal_level 2>/dev/null || echo n/a"),
        "loadavg_1_5_15": [round(v, 2) for v in la],
        "env_threads_requested": _THREADS,
        "env_thread_vars": {v: os.environ.get(v) for v in _THREAD_VARS},
        "threadpool_info": tp,
    }


# ── AD-1 : 확증 형상 입력 (라벨·군만 실제) ────────────────────────────────────
def load_design():
    """실제 라벨행렬 + 실제 scaffold 군집구조만 로드. 예측·OOF·봉인 **미접근**."""
    X = pd.read_parquet(F_MASTER_X).sort_values("cid").reset_index(drop=True)
    Y = pd.read_parquet(F_MASTER_Y).sort_values("cid").reset_index(drop=True)
    if not np.array_equal(X["cid"].values, Y["cid"].values):
        raise SystemExit("중단: master_X/master_Y 의 cid 정렬 불일치")
    smiles = X["smiles_canonical"].tolist()
    pt_names = [c for c in Y.columns if c != "cid"]
    y = Y[pt_names].to_numpy(dtype=np.int8)
    n, k = y.shape
    if n != EXPECT_N or k != EXPECT_K:
        raise SystemExit(f"중단: 형상 불일치 N={n}(기대 {EXPECT_N}) K={k}(기대 {EXPECT_K})")

    scaf = [scaffold_of(s) for s in smiles]            # F-SCAF 그대로 재사용
    uniq = sorted(set(scaf))
    idx = {g: i for i, g in enumerate(uniq)}
    g_of_row = np.array([idx[s] for s in scaf], dtype=int)
    n_groups = len(uniq)
    if n_groups != EXPECT_G:                            # 중단 조건: 군 정의 분기
        raise SystemExit(f"중단: scaffold group {n_groups} != {EXPECT_G} (군 정의가 확증과 갈라짐)")
    return {"y": y, "g_of_row": g_of_row, "scaffold_keys": uniq, "pt_names": pt_names,
            "cid": X["cid"].to_numpy(), "n_groups": n_groups,
            "no_scaffold_key_index": idx.get("", None),
            "benzene_key_index": idx.get("c1ccccc1", None)}


# ── 합성 예측행렬 8×3 (100% 합성) ─────────────────────────────────────────────
def synth_common_effect(y, seed, effect, base=BASE_STRENGTH):
    """`rqint_synthetic.make_rqint_common_effect` 와 **동일 형식**을 실제 라벨 위에서 생성.

    Δ_RF ≈ Δ_GIN ≈ (공통 서열효과), 상호작용 0. 예측은 전부 합성이다."""
    rng = np.random.default_rng(seed)
    P_RF = {"M1b": [_scores_from_labels(rng, y, strength=base) for _ in range(N_REPS)],
            "M2b": [_scores_from_labels(rng, y, strength=base + effect) for _ in range(N_REPS)]}
    P_GIN = {"M1b": {}, "M2b": {}}
    for s in SEEDS_S:
        P_GIN["M1b"][s] = [_scores_from_labels(rng, y, strength=base) for _ in range(N_REPS)]
        P_GIN["M2b"][s] = [_scores_from_labels(rng, y, strength=base + effect) for _ in range(N_REPS)]
    return P_RF, P_GIN


def synth_exchangeable(y, groups, seed, base=BASE_STRENGTH):
    """`rqint_synthetic.make_rqint_exchangeable` 와 동일 형식(공유 동전 → H0^B 참)."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    coin = rng.random(len(uniq)) < 0.5
    sr = coin[np.searchsorted(uniq, groups)][:, None]

    def _pair(strength):
        A = _scores_from_labels(rng, y, strength=strength)
        B = _scores_from_labels(rng, y, strength=strength)
        return np.where(sr, B, A), np.where(sr, A, B)

    P_RF = {"M1b": [], "M2b": []}
    for _ in range(N_REPS):
        m1, m2 = _pair(base)
        P_RF["M1b"].append(m1)
        P_RF["M2b"].append(m2)
    P_GIN = {"M1b": {s: [] for s in SEEDS_S}, "M2b": {s: [] for s in SEEDS_S}}
    for s in SEEDS_S:
        for _ in range(N_REPS):
            m1, m2 = _pair(base)
            P_GIN["M1b"][s].append(m1)
            P_GIN["M2b"][s].append(m2)
    return P_RF, P_GIN


# ── 공통: 1 복제 = fixture 생성 + rqint_test ────────────────────────────────
def run_replicate(y, groups, eligible, rep_seed, n_coin, effect, kind="common",
                  test_seed_base=10_000):
    if kind == "common":
        P_RF, P_GIN = synth_common_effect(y, rep_seed, effect)
    elif kind == "exchangeable":
        P_RF, P_GIN = synth_exchangeable(y, groups, rep_seed)
    else:
        raise ValueError(kind)
    res = sap_rqint.rqint_test(P_RF, P_GIN, y, groups, eligible,
                               n_coin_vectors=n_coin, seed=test_seed_base + rep_seed,
                               pair_complement=True, complement_audit_draws=0,
                               return_perm=True)
    perm = res.pop("perm")
    t_star = np.asarray(perm[:n_coin], dtype=np.float64)
    res["t_star_sha256"] = hashlib.sha256(t_star.tobytes()).hexdigest()
    return res


def observed_only(y, groups, eligible, rep_seed, effect):
    """순열 없이 관측 통계량만(효과 보정용). macro-AP 8회."""
    P_RF, P_GIN = synth_common_effect(y, rep_seed, effect)
    mats, seeds = sap_rqint.build_eight_consensus(P_RF, P_GIN)
    t, d_rf, d_gin, _ = sap_rqint.observed_statistic(mats, seeds, y, eligible)
    return t, d_rf, d_gin


# ── 워커(멀티프로세싱) ───────────────────────────────────────────────────────
_W = {}


def _init_worker(y, groups, eligible, kind, effect, n_coin, threads, t0):
    for v in _THREAD_VARS:
        os.environ[v] = str(threads)
    tpl = None
    try:                                   # import 이후에도 실효 스레드를 강제하는 경로
        from threadpoolctl import threadpool_limits
        tpl = threadpool_limits(limits=int(threads))
    except Exception:
        pass
    _W.update(y=y, groups=groups, eligible=eligible, kind=kind, effect=effect,
              n_coin=n_coin, t0=t0, threads=int(threads), _tpl=tpl)


def _effective_threads():
    try:
        from threadpoolctl import threadpool_info
        return {d.get("prefix") or d.get("internal_api"): int(d.get("num_threads", -1))
                for d in threadpool_info()}
    except Exception as e:                                        # pragma: no cover
        return {"error": str(e)}


def _work(rep_seed):
    s = time.time()
    r = run_replicate(_W["y"], _W["groups"], _W["eligible"], rep_seed, _W["n_coin"],
                      _W["effect"], kind=_W["kind"])
    e = time.time()
    return {
        "rep_seed": int(rep_seed), "pid": os.getpid(),
        "threads_limit": _W["threads"], "effective_threads": _effective_threads(),
        "start_rel": s - _W["t0"], "end_rel": e - _W["t0"], "task_seconds": e - s,
        "t_star_sha256": r["t_star_sha256"],
        "p_two_sided": r["p_two_sided"], "T_obs": r["T_obs"],
        "delta_rf": r["delta_rf"], "delta_gin": r["delta_gin"],
        "per_permutation_seconds": r["per_permutation_seconds"],
        "n_coin_vectors": r["n_coin_vectors"], "n_permutation_values": r["n_permutation_values"],
        "n_groups_G": r["n_groups_G"],
    }


class RamSampler(threading.Thread):
    """10초 주기 전 워커 RSS 합계 샘플(AD-3 RAM 게이트)."""

    def __init__(self, period=10.0):
        super().__init__(daemon=True)
        self.period = period
        self.samples = []
        self._stop = threading.Event()

    def run(self):
        me = psutil.Process()
        while not self._stop.is_set():
            tot = 0.0
            try:
                for c in me.children(recursive=True):
                    try:
                        tot += c.memory_info().rss
                    except Exception:
                        pass
                tot += me.memory_info().rss
            except Exception:
                pass
            self.samples.append(tot / 2**30)
            self._stop.wait(self.period)

    def stop(self):
        self._stop.set()


def run_pool(y, groups, eligible, rep_seeds, n_coin, effect, kind, workers, threads,
             sample_ram=True):
    ctx = mp.get_context("spawn")
    # spawn 자식은 부모 os.environ 을 물려받아 **numpy import 이전에** 스레드 상한을 본다.
    saved = {v: os.environ.get(v) for v in _THREAD_VARS}
    for v in _THREAD_VARS:
        os.environ[v] = str(threads)
    t0 = time.time()
    sampler = RamSampler() if sample_ram else None
    if sampler:
        sampler.start()
    try:
        # w=1 도 동일하게 자식 프로세스에서 실행한다(스레드 환경·결정성 조건 통일).
        with ctx.Pool(processes=workers, initializer=_init_worker,
                      initargs=(y, groups, eligible, kind, effect, n_coin, threads, t0)) as pool:
            rows = pool.map(_work, list(rep_seeds), chunksize=max(1, len(rep_seeds) // workers))
    finally:
        for v, val in saved.items():
            if val is None:
                os.environ.pop(v, None)
            else:
                os.environ[v] = val
    wall = time.time() - t0
    if sampler:
        sampler.stop()
        sampler.join(timeout=2)
    ram = sampler.samples if sampler else []
    return rows, wall, ram


def worker_wall_stats(rows, wall):
    """F-THR: 처리량 = w / wall_max (워커 중 마지막 완료 기준). 평균 기반 계산 금지."""
    by_pid = {}
    for r in rows:
        b = by_pid.setdefault(r["pid"], {"start": r["start_rel"], "end": r["end_rel"], "n": 0,
                                         "busy": 0.0})
        b["start"] = min(b["start"], r["start_rel"])
        b["end"] = max(b["end"], r["end_rel"])
        b["busy"] += r["task_seconds"]
        b["n"] += 1
    walls = sorted(b["end"] for b in by_pid.values())
    w = len(by_pid)
    wall_max = max(walls) if walls else wall
    med = float(np.median(walls)) if walls else 0.0
    return {
        "n_workers_observed": w,
        "worker_wall_min": float(min(walls)) if walls else 0.0,
        "worker_wall_median": med,
        "worker_wall_max": float(wall_max),
        "worker_wall_imbalance": float((max(walls) - min(walls)) / med) if med > 0 else 0.0,
        "pool_wall_seconds": float(wall),
        "tasks_per_worker": sorted(b["n"] for b in by_pid.values()),
    }


# ═══════════════════════════════════════════════════════════════════════════
# STAGES
# ═══════════════════════════════════════════════════════════════════════════
def stage_profile(_a):
    """AD-1 + AD-1-1."""
    d = load_design()
    y, g = d["y"], d["g_of_row"]
    prof = rfix.group_profile(g)
    sizes = np.bincount(g, minlength=d["n_groups"])
    eligible = np.arange(EXPECT_K)

    # 형상 assert (중단 조건)
    from sap.metrics import macro_ap
    P_RF, P_GIN = synth_common_effect(y, 7, 0.02)
    m = macro_ap(y, P_RF["M1b"][0], eligible)
    if m["n_eligible"] != EXPECT_K:
        raise SystemExit(f"중단: n_eligible={m['n_eligible']} != {EXPECT_K}")

    out = {
        "_doc": "블록 AD / AD-1 · AD-1-1 — 확증 형상 입력 구성과 군 프로파일 실측. "
                "라벨·군만 실제(설계량), **예측행렬은 100% 합성**.",
        "block": "AD",
        "when_kst": now_kst(),
        "predictions_are_synthetic": True,
        "confirmatory_predictions_loaded": False,
        "sealed_accessed": False,
        "data_paths_opened": [os.path.relpath(F_MASTER_X, ROOT), os.path.relpath(F_MASTER_Y, ROOT)],
        "shape": {"N": int(y.shape[0]), "K": int(y.shape[1]), "G": int(d["n_groups"])},
        "asserts": {
            "n_groups_eq_732": bool(d["n_groups"] == EXPECT_G),
            "n_eligible_eq_370": bool(m["n_eligible"] == EXPECT_K),
            "n_eval_eq_370": bool(m["n_eval"] == EXPECT_K),
            "n_excluded_undefined": int(m["n_excluded_undefined"]),
        },
        "group_profile_full": prof,
        "special_buckets": {
            "no_scaffold_bucket_size": int(sizes[d["no_scaffold_key_index"]])
            if d["no_scaffold_key_index"] is not None else None,
            "benzene_group_size": int(sizes[d["benzene_key_index"]])
            if d["benzene_key_index"] is not None else None,
            "note": "no-scaffold = Bemis–Murcko 결과가 빈 문자열인 버킷(무고리·파싱실패). "
                    "벤젠군 = 'c1ccccc1'. D12 민감도 2종의 대상이다(본 블록에서 실행 0).",
        },
        "size_histogram": {str(int(s)): int(c) for s, c in
                           zip(*np.unique(sizes, return_counts=True))},
        "D13_reference": {"G_eff": 85.3, "top2_row_share": 0.142, "G_eff_over_G": 0.117,
                          "source": "docs/84 §1 D13"},
        "D13_check": {
            "G_eff_measured": prof["G_eff_kish"],
            "G_eff_abs_diff_vs_85_3": abs(prof["G_eff_kish"] - 85.3),
            "top2_share_measured": prof["top2_row_share"],
            "G_eff_over_G_measured": prof["G_eff_over_G"],
            "matches_D13": bool(abs(prof["G_eff_kish"] - 85.3) < 0.1
                                and abs(prof["top2_row_share"] - 0.142) < 0.001),
        },
        "env": env_snapshot(),
    }
    dump(os.path.join(PARTS, "profile.json"), out)
    print(json.dumps({k: out[k] for k in ("shape", "asserts", "D13_check")},
                     ensure_ascii=False, indent=2))


def _unit_cost(y, groups, eligible, n_coin, seed, effect, kind="common"):
    t0 = time.perf_counter()
    r = run_replicate(y, groups, eligible, seed, n_coin, effect, kind=kind)
    wall = time.perf_counter() - t0
    return {
        "n_coin_vectors": r["n_coin_vectors"],
        "n_permutation_values": r["n_permutation_values"],
        "per_permutation_seconds": r["per_permutation_seconds"],
        "per_reference_value_seconds": r["per_reference_value_seconds"],
        "replicate_wall_seconds": float(wall),
        "fixture_build_seconds": float(wall - r["per_permutation_seconds"] * n_coin),
        "n_groups_G": r["n_groups_G"],
        "measured_not_extrapolated": True,
    }


def stage_unit(a):
    """AD-2 — 단독(w=1) baseline 단가 + 참조규모 재현 + ≥600s 지속부하 열감쇠."""
    d = load_design()
    y, g = d["y"], d["g_of_row"]
    eligible_full = np.arange(EXPECT_K)

    # 축소 fixture (AD-4 규칙)
    row_idx, lab, _alloc = rfix.allocate_rows_proportional(g, N_TARGET)
    y_rows = y[row_idx]
    cols, _pinfo = rfix.select_pts_by_prevalence(y_rows, d["pt_names"], K_TARGET)
    y_small = np.ascontiguousarray(y_rows[:, cols])
    eligible_small = np.arange(K_TARGET)

    res = {"_doc": "블록 AD / AD-2 — 단독(w=1) 단가 실측. 배터리·저전력 측정치 미사용.",
           "when_kst": now_kst(), "threads_requested": _THREADS,
           "env": env_snapshot(), "scales": {}}

    # 전규모
    res["scales"]["full"] = dict(N=EXPECT_N, K=EXPECT_K, G=EXPECT_G,
                                 **_unit_cost(y, g, eligible_full, a.n_full, 101, 0.02))
    # 축소
    res["scales"]["small"] = dict(N=N_TARGET, K=K_TARGET, G=int(len(np.unique(lab))),
                                  **_unit_cost(y_small, lab, eligible_small, a.n_small, 102, 0.02))
    # 참조(블록 AC 조건 재현) — 합성 fixture 전용, 실제 라벨 미사용
    from sap.rqint_synthetic import make_rqint_exchangeable
    P_RF, P_GIN, y_ref, g_ref, el_ref = make_rqint_exchangeable(seed=99)
    t0 = time.perf_counter()
    rr = sap_rqint.rqint_test(P_RF, P_GIN, y_ref, g_ref, el_ref, n_coin_vectors=a.n_ref,
                              seed=7, pair_complement=True, complement_audit_draws=0)
    res["scales"]["reference_AC"] = {
        "N": 100, "K": 10, "G": 20, "fixture": "make_rqint_exchangeable(seed=99) — 합성 전용",
        "n_coin_vectors": rr["n_coin_vectors"],
        "per_permutation_seconds": rr["per_permutation_seconds"],
        "replicate_wall_seconds": float(time.perf_counter() - t0),
        "F_PPS_block_AC": 0.015305511464939628,
        "ratio_vs_F_PPS": float(rr["per_permutation_seconds"] / 0.015305511464939628),
        "same_order_of_magnitude": bool(0.2 <= rr["per_permutation_seconds"] / 0.015305511464939628 <= 5.0),
        "measured_not_extrapolated": True,
    }

    if a.thermal_seconds <= 0:
        res["thermal"] = {"skipped": True,
                          "reason": "지속부하 열감쇠는 **단독 baseline(threads=1) 런에서 1회** 측정한다. "
                                    "본 런은 스레드 감도 대조용이라 열감쇠를 재측정하지 않았다.",
                          "meets_600s_minimum": None}
        dump(os.path.join(PARTS, f"unit_t{_THREADS}.json"), res)
        print(json.dumps({"full": res["scales"]["full"], "small": res["scales"]["small"],
                          "ref": res["scales"]["reference_AC"]}, ensure_ascii=False, indent=2))
        return

    # 열감쇠 — 단독 지속부하 ≥600s
    seg = []
    t_start = time.time()
    P_RF, P_GIN = synth_common_effect(y, 999, 0.02)
    k = 0
    while time.time() - t_start < a.thermal_seconds:
        s0 = time.time()
        r = sap_rqint.rqint_test(P_RF, P_GIN, y, g, eligible_full,
                                 n_coin_vectors=a.thermal_seg, seed=50_000 + k,
                                 pair_complement=True, complement_audit_draws=0)
        seg.append({"i": k, "t_rel": s0 - t_start,
                    "per_permutation_seconds": r["per_permutation_seconds"],
                    "rate_evals_per_s": 1.0 / r["per_permutation_seconds"]})
        k += 1
    dur = time.time() - t_start
    q = max(1, len(seg) // 4)
    first = float(np.median([s["rate_evals_per_s"] for s in seg[:q]]))
    last = float(np.median([s["rate_evals_per_s"] for s in seg[-q:]]))
    res["thermal"] = {
        "scale": "full", "sustained_seconds": float(dur),
        "meets_600s_minimum": bool(dur >= THERMAL_MIN_SECONDS),
        "requested_seconds": float(a.thermal_seconds),
        "n_segments": len(seg), "segment_n_coin": a.thermal_seg,
        "first_quarter_median_rate": first, "last_quarter_median_rate": last,
        "throughput_change_frac": float(last / first - 1.0),
        "decay_frac_for_budget": float(max(0.0, first / last - 1.0)),
        "decay_note": "decay_frac_for_budget = 처리율 저하로 인한 **소요시간 증가율**"
                      "(= first/last − 1, 음수는 0 으로 절단). AD-6 총시간에 (1+이 값)으로 반영.",
        "segments": seg,
        "loadavg_after": [round(v, 2) for v in os.getloadavg()],
        "pmset_ps_after": env_snapshot()["pmset_ps"],
    }
    dump(os.path.join(PARTS, f"unit_t{_THREADS}.json"), res)
    print(json.dumps({"full": res["scales"]["full"], "small": res["scales"]["small"],
                      "ref": res["scales"]["reference_AC"],
                      "thermal": {k: res["thermal"][k] for k in
                                  ("sustained_seconds", "meets_600s_minimum", "n_segments",
                                   "throughput_change_frac", "decay_frac_for_budget")}},
                     ensure_ascii=False, indent=2))


def stage_sweep(a):
    """AD-3 — 워커 스윕 → W_BEST(+ 결정성·RAM 게이트)."""
    d = load_design()
    y, g = d["y"], d["g_of_row"]
    row_idx, lab, _ = rfix.allocate_rows_proportional(g, N_TARGET)
    y_rows = y[row_idx]
    cols, _ = rfix.select_pts_by_prevalence(y_rows, d["pt_names"], K_TARGET)
    y_small = np.ascontiguousarray(y_rows[:, cols])

    out = {"_doc": "블록 AD / AD-3 — 병렬 스윕. 처리량 = w / wall_max (F-THR, 평균 기반 금지).",
           "when_kst": now_kst(), "env": env_snapshot(),
           "logical_cores": os.cpu_count(), "workers_swept": list(WORKERS),
           "ram_budget_gib": RAM_BUDGET_GIB, "ram_gate_frac": RAM_GATE_FRAC,
           "determinism_note": "같은 seed·같은 입력에서 워커 수와 무관하게 T* 수열이 바이트 동일해야 한다(G1 상당).",
           "scales": {}}

    for scale, (yy, gg, el, ncoin) in {
        "small": (y_small, lab, np.arange(K_TARGET), SWEEP_NCOIN_SMALL),
        "full": (y, g, np.arange(EXPECT_K), SWEEP_NCOIN_FULL),
    }.items():
        rep_seeds = list(range(200_000, 200_000 + SWEEP_R))
        rows_by_w, per_w = {}, {}
        for w in WORKERS:
            threads = max(1, os.cpu_count() // w)
            rows, wall, ram = run_pool(yy, gg, el, rep_seeds, ncoin, 0.02, "common", w, threads)
            rows = sorted(rows, key=lambda r: r["rep_seed"])
            rows_by_w[w] = [r["t_star_sha256"] for r in rows]
            st = worker_wall_stats(rows, wall)
            total_evals = SWEEP_R * ncoin
            peak = float(max(ram)) if ram else float("nan")
            per_w[w] = {
                "workers": w, "threads_per_worker_env": threads,
                "effective_threads_observed": rows[0]["effective_threads"],
                **st,
                "throughput_w_over_wallmax": float(w / st["worker_wall_max"]),
                "evals_per_second": float(total_evals / st["worker_wall_max"]),
                "total_evals": total_evals,
                "ram_samples": len(ram), "ram_sum_peak_gib": peak,
                "ram_gate_threshold_gib": RAM_BUDGET_GIB * RAM_GATE_FRAC,
                "ram_gate_exceeded": bool(peak > RAM_BUDGET_GIB * RAM_GATE_FRAC) if ram else False,
                "eliminated": bool(peak > RAM_BUDGET_GIB * RAM_GATE_FRAC) if ram else False,
                "ram_series_gib": [round(v, 3) for v in ram],
            }
        ref = rows_by_w[1]
        det = {str(w): bool(rows_by_w[w] == ref) for w in WORKERS}
        alive = {w: v for w, v in per_w.items() if not v["eliminated"]}
        best = max(alive, key=lambda w: alive[w]["evals_per_second"]) if alive else 1
        out["scales"][scale] = {
            "N": int(yy.shape[0]), "K": int(yy.shape[1]), "G": int(len(np.unique(gg))),
            "n_coin_per_replicate": ncoin, "n_replicates": SWEEP_R,
            "per_worker_count": per_w,
            "determinism_tstar_sha_identical_to_w1": det,
            "determinism_all_pass": bool(all(det.values())),
            "W_BEST": int(best),
            "W_BEST_basis": "RAM 게이트 통과 워커 중 evals_per_second(= total_evals / wall_max) 최대",
        }
        if not out["scales"][scale]["determinism_all_pass"]:
            dump(os.path.join(PARTS, "sweep.json"), out)
            raise SystemExit(f"중단: 병렬 결정성 위반(scale={scale}) — {det}")
    dump(os.path.join(PARTS, "sweep.json"), out)
    print(json.dumps({s: {"W_BEST": v["W_BEST"], "determinism_all_pass": v["determinism_all_pass"],
                          "eps": {w: round(x["evals_per_second"], 3)
                                  for w, x in v["per_worker_count"].items()}}
                      for s, v in out["scales"].items()}, ensure_ascii=False, indent=2))


def _pt_positive_group_counts(y_sub, groups):
    uniq, inv = np.unique(groups, return_inverse=True)
    out = []
    for j in range(y_sub.shape[1]):
        pos = np.where(y_sub[:, j] > 0)[0]
        out.append(len(np.unique(inv[pos])))
    return np.array(out)


def _tie_rate(P):
    """열별 점수 동률 비율 = 1 − (고유값 수 / 행 수) 의 평균."""
    n = P.shape[0]
    return float(np.mean([1.0 - len(np.unique(P[:, j])) / n for j in range(P.shape[1])]))


def _leverage_profile(y, groups, eligible, seed, effect):
    """단일군 교환 레버리지 δ_g = T*(z = 1_g) − T_obs (합성 예측 위에서만 정의).

    ★ D11 의 λ_k·ρ 진단이 **아니다**(그쪽은 확증 GIN 예측 필요 · 본 블록 범위 밖).
    여기서는 축소↔전규모 **설계 프로파일 대조**용으로만 쓴다."""
    P_RF, P_GIN = synth_common_effect(y, seed, effect)
    mats, seeds = sap_rqint.build_eight_consensus(P_RF, P_GIN)
    t_obs, _, _, _ = sap_rqint.observed_statistic(mats, seeds, y, eligible)
    uniq = np.unique(groups)
    gi = np.searchsorted(uniq, groups)
    dg = np.empty(len(uniq))
    for k in range(len(uniq)):
        swap_row = (gi == k)
        sw = sap_rqint._apply_swap(mats, seeds, swap_row)
        t, _, _, _ = sap_rqint.observed_statistic(sw, seeds, y, eligible)
        dg[k] = t - t_obs
    sq = dg ** 2
    return {"n_groups": int(len(uniq)), "T_obs_synthetic": float(t_obs),
            "max_esq_over_sum_esq": float(sq.max() / sq.sum()),
            "top5_esq_share": float(np.sort(sq)[::-1][:5].sum() / sq.sum()),
            "definition": "δ_g = T*(z=1_g) − T_obs on the synthetic fixture; NOT D11 λ_k/ρ",
            "predictions_are_synthetic": True}


def stage_fixture(a):
    """AD-4 — 축소 fixture 구성 + 프로파일 일치 검증표."""
    d = load_design()
    y, g = d["y"], d["g_of_row"]
    full_prof = rfix.group_profile(g)
    target_ratio = full_prof["G_eff_over_G"]

    row_idx, lab, alloc = rfix.allocate_rows_proportional(g, N_TARGET)
    y_rows = y[row_idx]
    cols, pinfo = rfix.select_pts_by_prevalence(y_rows, d["pt_names"], K_TARGET)
    y_small = np.ascontiguousarray(y_rows[:, cols])
    prop_prof = rfix.group_profile(lab)

    lab_opt, opt_info = rfix.regroup_ratio_optimal(lab, target_ratio, n_top=2)
    opt_prof = rfix.group_profile(lab_opt)
    top2 = sorted(np.bincount(np.unique(lab, return_inverse=True)[1]).tolist(), reverse=True)[:2]
    bound = rfix.min_attainable_ratio(N_TARGET, top2, N_TARGET - sum(top2))

    # 프로파일 대조 항목
    P_RF_f, _ = synth_common_effect(y, 5, 0.02)
    P_RF_s, _ = synth_common_effect(y_small, 5, 0.02)
    cmp_rows = {
        "full": {**full_prof,
                 "pt_positive_group_count": _describe(_pt_positive_group_counts(y, g)),
                 "score_tie_rate": _tie_rate(P_RF_f["M1b"][0]),
                 "leverage": _leverage_profile(y, g, np.arange(EXPECT_K), 5, 0.02)},
        "reduced_proportional": {**prop_prof,
                                 "pt_positive_group_count": _describe(_pt_positive_group_counts(y_small, lab)),
                                 "score_tie_rate": _tie_rate(P_RF_s["M1b"][0]),
                                 "leverage": _leverage_profile(y_small, lab, np.arange(K_TARGET), 5, 0.02)},
        "reduced_ratio_optimal": {**opt_prof,
                                  "pt_positive_group_count": _describe(_pt_positive_group_counts(y_small, lab_opt)),
                                  "score_tie_rate": _tie_rate(P_RF_s["M1b"][0]),
                                  "leverage": _leverage_profile(y_small, lab_opt, np.arange(K_TARGET), 5, 0.02)},
    }

    out = {
        "_doc": "블록 AD / AD-4 — 축소규모(N=400·K=60) fixture 규칙 확정 + 프로파일 일치 검증. "
                "라벨·군은 실제 설계량, 예측은 합성. **동결 아님**(동결은 SAP 1.2 블록).",
        "when_kst": now_kst(),
        "predictions_are_synthetic": True, "confirmatory_predictions_loaded": False,
        "rules": rfix.FIXTURE_RULES,
        "pt_selection": pinfo,
        "row_selection": {"n_rows": int(len(row_idx)), "n_groups_kept": int(len(np.unique(lab))),
                          "n_groups_dropped": int(EXPECT_G - len(np.unique(lab))),
                          "row_idx_sha256": hashlib.sha256(np.asarray(row_idx).tobytes()).hexdigest(),
                          "pt_cols_sha256": hashlib.sha256(np.asarray(cols).tobytes()).hexdigest()},
        "regroup_ratio_optimal_info": opt_info,
        "target_ratio_G_eff_over_G": target_ratio,
        "attainability": {
            "claim": "N=400 에서 상위 2군 행 점유율을 실제값(14.2%)에 맞추면 `G_eff/G = 0.117` 은 "
                     "**도달 불가능**하다. `G_eff/G = (Σm)²/(G·Σm²)` 이고 상위2군이 Σm² 를 지배하므로 "
                     "G·Σm² 의 상한이 목표에 못 미친다.",
            "min_attainable_ratio_given_top2": bound,
            "target": target_ratio,
            "gap": float(bound["min_ratio"] - target_ratio),
            "consequence": "본 블록은 **형상 충실(비례축소)** 을 primary 로 확정하고, "
                           "비율 최적 변형을 sensitivity 로 함께 산출한다. 두 변형은 라벨행렬·행 집합이 "
                           "동일하고 **군 라벨만** 다르다.",
        },
        "primary_variant": "reduced_proportional",
        "profile_comparison": cmp_rows,
        "match_summary": {
            "G_eff_over_G": {"full": full_prof["G_eff_over_G"],
                             "reduced_proportional": prop_prof["G_eff_over_G"],
                             "reduced_ratio_optimal": opt_prof["G_eff_over_G"]},
            "top2_row_share": {"full": full_prof["top2_row_share"],
                               "reduced_proportional": prop_prof["top2_row_share"],
                               "reduced_ratio_optimal": opt_prof["top2_row_share"]},
            "max_nsq_over_sum_nsq": {"full": full_prof["max_nsq_over_sum_nsq"],
                                     "reduced_proportional": prop_prof["max_nsq_over_sum_nsq"],
                                     "reduced_ratio_optimal": opt_prof["max_nsq_over_sum_nsq"]},
            "size_skewness": {"full": full_prof["size_skewness"],
                              "reduced_proportional": prop_prof["size_skewness"],
                              "reduced_ratio_optimal": opt_prof["size_skewness"]},
        },
        "alloc_head": {"kept_groups": int((alloc > 0).sum()),
                       "alloc_top10": sorted(alloc.tolist(), reverse=True)[:10]},
    }
    dump(os.path.join(PARTS, "fixture.json"), out)
    print(json.dumps(out["match_summary"], ensure_ascii=False, indent=2))
    print(json.dumps(out["attainability"]["min_attainable_ratio_given_top2"], ensure_ascii=False))


def _describe(v):
    v = np.asarray(v, dtype=float)
    return {"min": float(v.min()), "median": float(np.median(v)), "mean": float(v.mean()),
            "max": float(v.max())}


def _calibrate_effect(y, groups, eligible, targets, probe_effects, n_probe, seed0):
    """공통효과 강도(logit) → 실현 Δ 보정. 라벨·설계량만 사용(성능·부호 미참조)."""
    curve = []
    for e in probe_effects:
        ds = [observed_only(y, groups, eligible, seed0 + i, e)[1] for i in range(n_probe)]
        curve.append({"effect": float(e), "mean_delta_rf": float(np.mean(ds)),
                      "sd": float(np.std(ds, ddof=1))})
    xs = np.array([c["effect"] for c in curve])
    ys = np.array([c["mean_delta_rf"] for c in curve])
    slope = float(np.sum(xs * ys) / np.sum(xs * xs))       # 원점 통과 선형 적합(Δ(0)=0)
    chosen = {str(t): float(t / slope) for t in targets}
    return {"probe_curve": curve, "slope_delta_per_effect": slope,
            "chosen_effect_for_target_delta": chosen,
            "fit": "origin-through linear least squares (Δ(0)=0 by construction)",
            "n_probe_replicates": int(n_probe)}


def _pdist(rows):
    p = np.array([r["p_two_sided"] for r in rows])
    drf = np.array([r["delta_rf"] for r in rows])
    dgin = np.array([r["delta_gin"] for r in rows])
    gap = np.abs(np.array([r["T_obs"] for r in rows]))
    return {
        "R": int(len(rows)),
        "mean_p": float(p.mean()),
        "frac_p_le_0.05": float((p <= 0.05).mean()),
        "frac_p_le_0.05_over_7": float((p <= 0.05 / 7).mean()),
        "frac_p_le_0.05_over_4": float((p <= 0.05 / 4).mean()),
        "mean_delta_rf": float(drf.mean()),
        "mean_delta_gin": float(dgin.mean()),
        "mean_abs_gap": float(gap.mean()),
        "mc_se_frac_p_le_0.05": float(math.sqrt(max((p <= 0.05).mean() * (1 - (p <= 0.05).mean()), 0)
                                                / len(rows))),
    }


def stage_weaknull(a):
    """AD-5 — 약한-null 재측정(Δ 0.01·0.03). ★ 계측 · 판정 아님."""
    d = load_design()
    y, g = d["y"], d["g_of_row"]
    row_idx, lab, _ = rfix.allocate_rows_proportional(g, N_TARGET)
    y_rows = y[row_idx]
    cols, _ = rfix.select_pts_by_prevalence(y_rows, d["pt_names"], K_TARGET)
    y_small = np.ascontiguousarray(y_rows[:, cols])
    lab_opt, _ = rfix.regroup_ratio_optimal(lab, rfix.group_profile(g)["G_eff_over_G"], 2)
    el = np.arange(K_TARGET)

    sweep = load_part("sweep")
    w = int(sweep["scales"]["small"]["W_BEST"])
    threads = max(1, os.cpu_count() // w)

    cal = _calibrate_effect(y_small, lab, el, TARGET_DELTAS, (0.01, 0.02, 0.05, 0.10), 40, 300_000)
    out = {
        "_doc": "블록 AD / AD-5 — 약한-null(H0^int 참·H0^B 거짓) p 분포 재측정. "
                "예측 100% 합성 · 라벨/군만 실제.",
        "status": "계측 · 판정 아님 (정식 판정 = R1 의 C1~C3)",
        NOT_ANALYSIS: True,
        "acceptance_criterion_applied": False,
        "acceptance_criterion_note": "R1 의 합격기준(기각률 ≤ α + 2·SE)은 **여기서 적용하지 않는다**. "
                                     "이 수치로 후보 B 를 채택·기각하지 않는다.",
        "when_kst": now_kst(), "env": env_snapshot(),
        "design": {"scale": f"N={N_TARGET}·K={K_TARGET}", "R": WEAKNULL_R,
                   "n_coin_vectors": WEAKNULL_NCOIN,
                   "n_permutation_values": 2 * WEAKNULL_NCOIN,
                   "workers": w, "threads_per_worker": threads,
                   "generator": "make_rqint_common_effect 형식(공통 서열효과, 상호작용 0)"},
        "effect_calibration": cal,
        "cells": {},
    }
    variants = {"reduced_proportional": lab, "reduced_ratio_optimal": lab_opt}
    rep_seeds = list(range(400_000, 400_000 + WEAKNULL_R))
    drift = {}
    for vname, groups in variants.items():
        for tgt in TARGET_DELTAS:
            eff = cal["chosen_effect_for_target_delta"][str(tgt)]
            rows, wall, ram = run_pool(y_small, groups, el, rep_seeds, WEAKNULL_NCOIN, eff,
                                       "common", w, threads)
            rows = sorted(rows, key=lambda r: r["rep_seed"])
            key = f"{vname}__target_delta_{tgt}"
            out["cells"][key] = {
                "variant": vname, "target_delta": tgt, "effect_strength_logit": eff,
                **_pdist(rows),
                "wall_seconds": float(wall),
                "ram_sum_peak_gib": float(max(ram)) if ram else None,
                "per_permutation_seconds_median": float(
                    np.median([r["per_permutation_seconds"] for r in rows])),
            }
            # 병렬 조건 처리율 드리프트(추가 비용 0 — AD-2 단독 열감쇠의 보완 관측)
            pps = [r["per_permutation_seconds"] for r in sorted(rows, key=lambda r: r["start_rel"])]
            q = max(1, len(pps) // 4)
            drift[key] = {"first_quarter_median_pps": float(np.median(pps[:q])),
                          "last_quarter_median_pps": float(np.median(pps[-q:])),
                          "slowdown_frac": float(np.median(pps[-q:]) / np.median(pps[:q]) - 1.0),
                          "wall_seconds": float(wall), "workers": w}
    out["parallel_throughput_drift"] = {
        "note": "AD-5 본 런 중 관측(추가 비용 0). AD-2 의 단독 열감쇠와 달리 **W_BEST 병렬 부하** 조건이다.",
        "cells": drift,
        "max_slowdown_frac": float(max(v["slowdown_frac"] for v in drift.values())),
    }
    ac = {"source": "experiments/rqint/audit_r6.json weak_null_diagnostic (블록 AC)",
          "scale": "N=100·K=10·G=20 (합성 라벨)", "R": 200, "n_coin_vectors": 150,
          "mean_p": 0.4585, "frac_p_le_0.05": 0.0950,
          "frac_p_le_0.05_over_7": 0.0150, "frac_p_le_0.05_over_4": 0.0350,
          "mean_delta_rf": 0.3251, "mean_delta_gin": 0.3313, "mean_abs_gap": 0.0535}
    out["contrast_with_AC_diagnostic"] = {
        "AC": ac,
        "why": "AC 진단의 공통효과는 Δ≈0.33 으로 C1(0.01)·C2(0.03)보다 10~30배 크다. "
               "공유 동전 arm-swap 의 anti-conservativeness 는 공통효과 크기에 의존하므로 "
               "AC 의 1.9~2.8배는 **상한에 가깝고 예측치가 아니다**.",
        "ratio_vs_nominal": {k: {"at_0.05": v["frac_p_le_0.05"] / 0.05,
                                 "at_0.05/7": v["frac_p_le_0.05_over_7"] / (0.05 / 7),
                                 "at_0.05/4": v["frac_p_le_0.05_over_4"] / (0.05 / 4)}
                             for k, v in out["cells"].items()},
        "AC_ratio_vs_nominal": {"at_0.05": ac["frac_p_le_0.05"] / 0.05,
                                "at_0.05/7": ac["frac_p_le_0.05_over_7"] / (0.05 / 7),
                                "at_0.05/4": ac["frac_p_le_0.05_over_4"] / (0.05 / 4)},
    }
    dump(os.path.join(PARTS, "weaknull.json"), out)
    print(json.dumps({k: {kk: v[kk] for kk in ("mean_p", "frac_p_le_0.05", "mean_delta_rf",
                                               "mean_delta_gin", "mean_abs_gap")}
                      for k, v in out["cells"].items()}, ensure_ascii=False, indent=2))


def stage_bridge(a):
    """AD-4-4 — bridge smoke test(전규모 소수 복제). 기술통계만 · 판정 아님."""
    d = load_design()
    y, g = d["y"], d["g_of_row"]
    el = np.arange(EXPECT_K)
    sweep = load_part("sweep")
    w = int(sweep["scales"]["full"]["W_BEST"])
    threads = max(1, os.cpu_count() // w)
    cal = _calibrate_effect(y, g, el, TARGET_DELTAS, (0.01, 0.02, 0.05, 0.10), 12, 310_000)

    out = {"_doc": "블록 AD / AD-4-4 — 축소↔전규모 p 분포 형상 대조(bridge smoke). "
                   "**판정 아님 · 기술통계만** · 예측 100% 합성.",
           "status": "계측 · 판정 아님", NOT_ANALYSIS: True,
           "when_kst": now_kst(),
           "design": {"scale": f"N={EXPECT_N}·K={EXPECT_K}·G={EXPECT_G}", "R": BRIDGE_R,
                      "n_coin_vectors": BRIDGE_NCOIN, "workers": w},
           "effect_calibration_full_scale": cal, "cells": {}}
    rep_seeds = list(range(500_000, 500_000 + BRIDGE_R))
    for tgt in TARGET_DELTAS:
        eff = cal["chosen_effect_for_target_delta"][str(tgt)]
        rows, wall, ram = run_pool(y, g, el, rep_seeds, BRIDGE_NCOIN, eff, "common", w, threads)
        rows = sorted(rows, key=lambda r: r["rep_seed"])
        out["cells"][f"full__target_delta_{tgt}"] = {
            "target_delta": tgt, "effect_strength_logit": eff, **_pdist(rows),
            "p_values": [r["p_two_sided"] for r in rows],
            "wall_seconds": float(wall),
            "ram_sum_peak_gib": float(max(ram)) if ram else None,
            "per_permutation_seconds_median": float(
                np.median([r["per_permutation_seconds"] for r in rows])),
        }
    dump(os.path.join(PARTS, "bridge.json"), out)
    print(json.dumps({k: {kk: v[kk] for kk in ("mean_p", "frac_p_le_0.05", "mean_delta_rf",
                                               "mean_abs_gap")}
                      for k, v in out["cells"].items()}, ensure_ascii=False, indent=2))


# ── AD-6 예산 ────────────────────────────────────────────────────────────────
def stage_budget(a):
    u1 = load_part("unit_t1")
    uall = load_part(f"unit_t{a.threads_all}")
    sw = load_part("sweep")
    fx = load_part("fixture")
    wn = load_part("weaknull")
    br = load_part("bridge")

    t_small = u1["scales"]["small"]["per_permutation_seconds"]
    t_full = u1["scales"]["full"]["per_permutation_seconds"]
    decay = u1["thermal"]["decay_frac_for_budget"]
    drift_cells = wn["parallel_throughput_drift"]["cells"]
    drift_vals = sorted(v["slowdown_frac"] for v in drift_cells.values())
    par_drift = wn["parallel_throughput_drift"]["max_slowdown_frac"]
    # ★ 보수적 선택: 단독 열감쇠(0)와 병렬 드리프트 4셀 중 **최댓값**을 쓴다.
    #   블록 I 교훈(추정이 1.39배 과소)상 시간 예산은 과대 쪽으로 잡는다.
    decay_used = max(decay, par_drift, 0.0)

    w_small = int(sw["scales"]["small"]["W_BEST"])
    w_full = int(sw["scales"]["full"]["W_BEST"])
    raw_small = sw["scales"]["small"]["per_worker_count"][str(w_small)]["evals_per_second"]
    raw_full = sw["scales"]["full"]["per_worker_count"][str(w_full)]["evals_per_second"]
    raw1_small = sw["scales"]["small"]["per_worker_count"]["1"]["evals_per_second"]
    raw1_full = sw["scales"]["full"]["per_worker_count"]["1"]["evals_per_second"]
    # 스윕의 evals_per_second 에는 **복제당 fixture 생성 오버헤드**가 섞여 있다
    # (스윕은 복제당 순열 수가 작아 그 비중이 크다). 실효 병렬 배수는 같은 오버헤드를 가진
    # w=1 대비 비율로 잡고, 단가는 AD-2 의 단독 실측 t 를 쓴다 → 오버헤드 중립.
    speedup_small = raw_small / raw1_small
    speedup_full = raw_full / raw1_full
    eps_small = speedup_small / t_small
    eps_full = speedup_full / t_full

    def hours(total_evals, scale):
        eps = eps_small if scale == "small" else eps_full
        sec = total_evals / eps * (1.0 + decay_used)
        return {"total_evals": int(total_evals), "scale": scale,
                "evals_per_second_at_W_BEST": eps,
                "wall_seconds": float(sec), "wall_hours": float(sec / 3600),
                "wall_days": float(sec / 86400),
                "estimate_not_measurement": True,
                "anchors": {
                    "unit_cost_seconds_per_eval_w1": t_small if scale == "small" else t_full,
                    "measured_throughput_evals_per_second": eps,
                    "thermal_inflation_applied": decay_used,
                }}

    # C0~C3 = 축소, C4 = 전규모. 단가만으로 확정(기각률·검정력 **미참조**).
    C_R = 2000              # F-C03 범위 1,000~2,000 의 **상한** — 단가상 7일 예산 안에 들어오므로
                            # 범위 내 최대 정밀도를 택한다(결과 미참조)
    C_PERM = 2000
    C4_R = 400              # F-C4 범위 200~400 (A12 적응적 중지 규칙 병기)
    C4_PERM = 1000
    C4_TAU = [0.01, 0.02, 0.03]

    scen = {}
    for name in ("C0", "C1", "C2", "C3"):
        scen[name] = {"replicates": C_R, "n_coin_vectors": C_PERM,
                      "n_permutation_values": 2 * C_PERM, "scale": "small",
                      **hours(C_R * C_PERM, "small")}
    scen["C4"] = {"replicates": C4_R, "n_coin_vectors": C4_PERM,
                  "n_permutation_values": 2 * C4_PERM, "scale": "full",
                  "tau_grid": C4_TAU, "tau_prespecified": 0.02,
                  "n_tau_arms": len(C4_TAU),
                  **hours(C4_R * C4_PERM * len(C4_TAU), "full")}
    total_sec = sum(v["wall_seconds"] for v in scen.values())

    dry = {}
    for b in (100_000, 50_000):
        dry[str(b)] = {"n_coin_vectors": b, "scale": "full", **hours(b, "full")}

    out = {
        "_doc": "블록 AD / AD-6 — 비용 모델 + C0~C4 복제·순열 확정 + B 드라이런 추정. "
                "확정 근거는 **단가뿐**이며 기각률·검정력은 일절 참조하지 않았다.",
        "when_kst": now_kst(),
        "cost_model": {
            "formula_evals": "총 평가 횟수 = Σ_시나리오 (복제 수 × 내부 순열 수)   # 순열 수 = n_coin_vectors",
            "formula_wall": "총 벽시계 = 총 평가 횟수 / 처리량(W_BEST) × (1 + 열감쇠율)",
            "cost_axis": "n_coin_vectors (F-COIN)",
            "footnote_complement": "★ 여집합 항등식 T*(z̄) = −T*(z) 때문에 **참조분포 크기는 평가 횟수의 2배**"
                                   "(n_permutation_values = 2 × n_coin_vectors)다. 비용에는 "
                                   "**n_coin_vectors 를 쓴다** — 여집합 값은 평가 0회로 도출된다.",
            "footnote_audit": "여집합 항등식 감사(`complement_audit_draws`)는 감사 draw 당 평가 1회를 "
                              "**추가**한다. 블록 AC 가 1,000 draw 전건 편차 0.0 으로 항등식을 이미 "
                              "실증했으므로, R1 본런은 감사 draw 를 복제마다 반복하지 말고 "
                              "**시나리오당 1회(예: 1,000 draw)** 로 두는 것을 권한다. 위 추정은 "
                              "감사 비용을 **제외**한 값이다.",
            "one_eval_definition": "T* 1회 평가 = consensus 8행렬 위의 macro-AP 8회(D5).",
        },
        "measured_anchors": {
            "t_full_seconds_per_eval_w1": t_full,
            "t_small_seconds_per_eval_w1": t_small,
            "reference_scale_check": u1["scales"]["reference_AC"],
            "W_BEST_small": w_small, "W_BEST_full": w_full,
            "evals_per_second_small_at_W_BEST": eps_small,
            "evals_per_second_full_at_W_BEST": eps_full,
            "effective_parallel_speedup_small": float(speedup_small),
            "effective_parallel_speedup_full": float(speedup_full),
            "thermal_decay_single_worker": decay,
            "throughput_drift_parallel_W_BEST": par_drift,
            "throughput_drift_parallel_cells_sorted": drift_vals,
            "throughput_drift_parallel_median": float(np.median(drift_vals)),
            "thermal_inflation_used_in_budget": decay_used,
            "thermal_inflation_choice": "보수적 — 단독 열감쇠(≥600s 지속부하)와 병렬 4셀 드리프트 중 최댓값. "
                                        "중앙값을 썼다면 총 벽시계는 약 "
                                        f"{(1 + float(np.median(drift_vals))) / (1 + decay_used):.3f} 배가 된다.",
            "threads_1_vs_all": {
                "t_full_threads_1": t_full,
                "t_full_threads_all": uall["scales"]["full"]["per_permutation_seconds"],
                "t_small_threads_1": t_small,
                "t_small_threads_all": uall["scales"]["small"]["per_permutation_seconds"],
            },
            "measured_not_extrapolated": True,
        },
        "scenarios_confirmed": scen,
        "confirmation_basis": "단가(t_small·t_full)와 실측 처리량만으로 F-C03(1,000~2,000)·F-C4(200~400) "
                              "범위 안에서 선택했다. **기각률·검정력·p 분포를 근거로 쓰지 않았다.**",
        "A12_adaptive_stopping_prespecified": {
            "applies_to": "C4",
            "rule": "최대 400 복제. 200 복제 시점에 검정력 추정의 신뢰구간을 산출해 "
                    "0.50·0.80 경계를 **가로지르지 않으면 중단**, 가로지르면 400 까지 진행. "
                    "400 에서도 가로지르면 D19 사다리의 **낮은 지위**를 채택한다.",
            "interval_type": "Wilson score interval (이항 비율)",
            "confidence_level": 0.95,
            "note": "사전 기술이며 본 블록에서 적용·실행하지 않았다.",
        },
        "total": {
            "wall_seconds": float(total_sec), "wall_hours": float(total_sec / 3600),
            "wall_days": float(total_sec / 86400),
            "exceeds_7d": bool(total_sec > 7 * 86400),
            "estimate_not_measurement": True,
        },
        "B_dryrun_estimate": {
            "status": "추정만 — **B 는 본 블록에서 확정하지 않는다**(SAP 1.2 블록의 일).",
            "B_definition_status": sap_rqint.B_DEFINITION_STATUS,
            "estimates": dry,
            "threshold_hours": 24.0,
            "verdict_preview": {b: ("24h 이내" if v["wall_hours"] <= 24 else "24h 초과")
                                for b, v in dry.items()},
            "F_BREC": "docs/84 §1 D15 — B 권고 100,000, 전규모 드라이런 24h 초과 시에만 50,000",
            "estimate_not_measurement": True,
        },
        "range_sensitivity_not_a_choice": {
            "note": "F-C03 범위의 **하한**(복제 1,000)을 택했을 때의 참고 추정. 확정값은 위 "
                    "`scenarios_confirmed`(2,000)이며, 본 항목은 범위 감도를 보이기 위한 참고치다.",
            "C0_C3_replicates_1000_each_hours": float(1000 * C_PERM / eps_small
                                                      * (1 + decay_used) / 3600),
            "total_with_C0_C3_at_1000_hours": float(
                (4 * 1000 * C_PERM / eps_small + C4_R * C4_PERM * len(C4_TAU) / eps_full)
                * (1 + decay_used) / 3600),
            "estimate_not_measurement": True,
        },
        "alternatives_if_over_7d": [
            "워커 재조정(W_BEST 상향 또는 스레드 재배분)",
            "C4 복제 하향(400 → 200, A12 적응적 중지의 하한)",
            "C4 τ 격자 축소(사전지정 τ=0.02 우선 실행 후 나머지 분할)",
            "분할 실행(세션 분할 — 블록 D 선례)",
        ],
        "inputs_used": {
            "unit_t1": "experiments/rqint/_parts/unit_t1.json",
            "unit_tall": f"experiments/rqint/_parts/unit_t{a.threads_all}.json",
            "sweep": "experiments/rqint/_parts/sweep.json",
            "fixture": "experiments/rqint/_parts/fixture.json",
            "weaknull": "experiments/rqint/_parts/weaknull.json",
            "bridge": "experiments/rqint/_parts/bridge.json",
        },
        "fixture_primary_variant": fx["primary_variant"],
        "bridge_summary": {k: {"mean_p": v["mean_p"], "frac_p_le_0.05": v["frac_p_le_0.05"]}
                           for k, v in br["cells"].items()},
        "not_decided_here": ["B 값", "B 정의(n_coin_vectors vs n_permutation_values)",
                             "SAP 1.2 동결", "축소 fixture 규칙 동결", "R1 착수 허가"],
    }
    dump(os.path.join(PARTS, "budget.json"), out)
    print(json.dumps({"total": out["total"], "scen_hours": {k: round(v["wall_hours"], 2)
                                                           for k, v in scen.items()},
                      "B": {k: round(v["wall_hours"], 2) for k, v in dry.items()}},
                     ensure_ascii=False, indent=2))


def stage_assemble(a):
    """AD-8 산출물 4종 조립."""
    prof = load_part("profile")
    u1 = load_part("unit_t1")
    uall = load_part(f"unit_t{a.threads_all}")
    sw = load_part("sweep")
    fx = load_part("fixture")
    wn = load_part("weaknull")
    br = load_part("bridge")
    bg = load_part("budget")

    common = {
        "block": "AD",
        "instruction": "docs/90_rqint_timing_calibration_budget_prompt_for_vscode.md",
        "predictions_are_synthetic": True,
        "confirmatory_predictions_loaded": False,
        "confirmatory_data_accessed": False,
        "sealed_accessed": False,
        "unblinding_performed": False,
        "gin_start_still_blocked": True,
        "sap_version_unchanged": "1.1",
        "manifest_sha16": "756d485feb4715e9",
        "B_definition_status": sap_rqint.B_DEFINITION_STATUS,
    }

    timing = {
        "_doc": "블록 AD — 단가·병렬 스윕·열감쇠·RAM·환경. **계측 전용 · 판정 0**. "
                "예측행렬 100% 합성(라벨·scaffold 군만 실제 설계량).",
        **common,
        "when_kst": now_kst(),
        "power_gate": {
            "pmset_powermode": u1["env"]["pmset_powermode"],
            "pmset_ps": u1["env"]["pmset_ps"],
            "on_ac_power": bool("AC Power" in u1["env"]["pmset_ps"]),
            "low_power_mode_off": bool(str(u1["env"]["pmset_powermode"]).strip() == "0"),
            "battery_or_lowpower_measurements_used_in_budget": False,
        },
        "unit_costs_single_worker_w1": {
            "threads_1": u1["scales"],
            f"threads_{a.threads_all}": uall["scales"],
            "baseline_definition": "단독(w=1) 실행만 baseline. 병렬 배치의 워커0 wall 은 baseline 금지.",
        },
        "thermal": {"threads_1": u1["thermal"],
                    f"threads_{a.threads_all}": uall["thermal"],
                    "parallel_drift_from_AD5": wn["parallel_throughput_drift"]},
        "parallel_sweep": sw["scales"],
        "throughput_definition": "w / wall_max (F-THR) · wall_max = 워커 중 마지막 완료. 평균·중앙값 기반 계산 0건.",
        "ram_gate": {"budget_gib": RAM_BUDGET_GIB, "gate_frac": RAM_GATE_FRAC,
                     "sample_period_seconds": 10.0,
                     "eliminated_worker_counts": {
                         s: [w for w, v in d["per_worker_count"].items() if v["eliminated"]]
                         for s, d in sw["scales"].items()}},
        "timing_proxy_used": False,
        "timing_proxy_note": "본 블록은 프록시(축소 K 등)를 단가 표에 섞지 않았다. 축소규모(N=400·K=60)는 "
                             "프록시가 아니라 **C0~C3 의 실제 실행 규모**이며 별도 행으로 보고한다.",
        "env": prof["env"],
    }

    profile_match = {
        "_doc": "블록 AD — AD-1-1(전규모 군 프로파일 실측) / AD-4(축소 fixture 프로파일 대조).",
        **common, "when_kst": now_kst(),
        "AD_1_1_full_profile": prof["group_profile_full"],
        "AD_1_1_special_buckets": prof["special_buckets"],
        "AD_1_1_size_histogram": prof["size_histogram"],
        "D13_check": prof["D13_check"],
        "asserts": prof["asserts"],
        "AD_4_rules": fx["rules"],
        "AD_4_pt_selection": fx["pt_selection"],
        "AD_4_row_selection": fx["row_selection"],
        "AD_4_profile_comparison": fx["profile_comparison"],
        "AD_4_match_summary": fx["match_summary"],
        "AD_4_attainability": fx["attainability"],
        "AD_4_primary_variant": fx["primary_variant"],
        "AD_4_regroup_info": fx["regroup_ratio_optimal_info"],
        "AD_4_4_bridge_smoke": br,
        "frozen_here": False,
        "freeze_note": "축소 fixture 규칙은 **본 블록에서 확정하되 동결하지 않는다**(동결 = SAP 1.2 블록).",
    }

    weak = {**wn, **common, "_assembled_kst": now_kst()}
    budget = {**bg, **common, "_assembled_kst": now_kst()}

    dump(os.path.join(OUT_DIR, "timing.json"), timing)
    dump(os.path.join(OUT_DIR, "profile_match.json"), profile_match)
    dump(os.path.join(OUT_DIR, "weak_null_scaled.json"), weak)
    dump(os.path.join(OUT_DIR, "budget.json"), budget)
    print("assembled: timing.json profile_match.json weak_null_scaled.json budget.json")


STAGES = {"profile": stage_profile, "unit": stage_unit, "sweep": stage_sweep,
          "fixture": stage_fixture, "weaknull": stage_weaknull, "bridge": stage_bridge,
          "budget": stage_budget, "assemble": stage_assemble}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    ap.add_argument("--n-full", type=int, default=60)
    ap.add_argument("--n-small", type=int, default=400)
    ap.add_argument("--n-ref", type=int, default=200)
    ap.add_argument("--thermal-seg", type=int, default=40)
    ap.add_argument("--thermal-seconds", type=float, default=THERMAL_MIN_SECONDS)
    ap.add_argument("--threads-all", type=str, default="18")
    a = ap.parse_args()
    os.makedirs(PARTS, exist_ok=True)
    t0 = time.time()
    STAGES[a.stage](a)
    print(f"[stage={a.stage}] wall={time.time() - t0:.2f}s threads={_THREADS}")


if __name__ == "__main__":
    main()
