#!/usr/bin/env python3
"""rqint_calibration.py — [블록 AE] R1 캘리브레이션 감사 C0~C4 본런 하네스.

⛔ 무결성 (지시서 `docs/93_r1_calibration_audit_prompt_for_vscode.md` §0)
  · **확증 예측·OOF·`_sealed/`·부호·`p_emp`·`T_obs` 는 한 번도 열지 않는다.**
    본 스크립트가 여는 데이터 경로는 `data/processed/master_X.parquet` 과
    `data/processed/master_Y.parquet` **두 개뿐**이며, 둘 다 `docs/84` §2 R1 설계가
    "result-independent 설계량"으로 명시 허용한 **라벨행렬·스캐폴드 군집구조** 용이다.
  · **예측행렬은 100% 합성**이다(`sap.synthetic._scores_from_labels` 를 실제 라벨을 조건으로 호출).
  · 본 파일은 **`sap/` 밖**에 있다 — `sap/*.py` 의 "데이터 미접근 순수 함수" 불변식을 깨지 않는다.
  · **`B` 확정 0 · SAP 1.2 동결 0 · GIN 학습 0 · 개봉 0 · 네트워크 0 · commit/push 0.**

★ `scaffold_of` 는 확증 러너의 함수를 **그대로 재사용**한다(F-SCAF, 재구현 금지).
  `from confirmatory_oof_rep1 import scaffold_of` 는 **모듈 import** 이며 데이터 경로가 아니다.
★ AP 계산은 `sap.metrics.macro_ap` 를 `sap.rqint` 경유로 **재사용**한다(재구현 0).
★ 판정(기각률·CI·KS)의 **독립 재계산**은 `rqint_calibration_verify.py` 가 담당한다(A21).

실행:
  .venv/bin/python3 v3_Multimodal/src/rqint_calibration.py --stage facts
  ...                                                       --stage design
  ...                                                       --stage run --cell C0:prop [--max-seconds N]
  ...                                                       --stage summary
"""
from __future__ import annotations

import os

# ── BLAS 스레드 명시 고정 — numpy import **이전**이어야 효력이 있다 (AD-2 계승) ─────
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
CKPT_DIR = os.path.join(OUT_DIR, "_ckpt")
SAP_DIR = os.path.join(HERE, "sap")
CFG_DIR = os.path.join(ROOT, "v3_Multimodal", "config")
RUNS_DIR = os.path.join(ROOT, "experiments", "runs")

F_FACTS = os.path.join(OUT_DIR, "calibration_facts.json")
F_DESIGN = os.path.join(OUT_DIR, "calibration_design.json")
F_SUMMARY = os.path.join(OUT_DIR, "calibration_summary.json")
F_SESSIONS = os.path.join(OUT_DIR, "calibration_sessions.jsonl")

# ══════════════════════════════════════════════════════════════════════════════
# 사전 고정 상수 — 착수 전 확정. 결과를 보고 바꾸지 않는다(§0 절대금지 2).
# ══════════════════════════════════════════════════════════════════════════════
EXPECT_N, EXPECT_K, EXPECT_G = 1092, 370, 732        # F-N · F-K · F-G
N_TARGET, K_TARGET = 400, 60                         # F-C03 축소규모
SEEDS_S = (1, 2, 3)                                  # 시드 인덱스 s (D16)
N_REPS = 3                                           # repeat 축(D3)
BASE_STRENGTH = 1.1                                  # 합성 예측 기저 강도(AD 계승)

# AE-2 시드 규약
BASE_SEED = 20260813
SCEN_INDEX = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4}
VARIANT_OFFSET = {"prop": 0, "ratio": 500_000}
COIN_SEED_OFFSET = 900_000_000                       # 동전 RNG 시드 = rep_seed + 이 상수
PROBE_SEED_SMALL = BASE_SEED + 800_000_000
PROBE_SEED_FULL = BASE_SEED + 810_000_000
SELFTEST_SEED = BASE_SEED + 820_000_000

# AE-1 규모·복제
R_PRIMARY, R_SENS = 2000, 1000                       # primary=범위 상한 · sensitivity=범위 하한
NCOIN_SMALL = 2000                                   # C0~C3 내부 순열(동전 벡터) 수
R_C4, NCOIN_FULL = 400, 1000                         # C4
TAU_GRID = (0.01, 0.02, 0.03)                        # F-C4TAU
TAU_PRESPEC = 0.02
A12_INTERIM = 200                                    # A12 적응적 중지 중간 점검 시점
AUDIT_DRAWS = 1000                                   # 여집합 항등식 감사 — 셀당 1회

# AE-1-3 판정 지점 (A10)
ALPHA = 0.05
HOLM_M = 7                                           # F-HOLM
POINTS = {"alpha": ALPHA, "alpha_over_7": ALPHA / 7.0, "alpha_over_4": ALPHA / 4.0}
OFFICIAL_POINT = "alpha"                             # ★ 공식 합격 판정 지점은 이것 하나뿐

# 시나리오별 효과 (macro-AP 척도 목표값 — logit 강도로는 slope 로 환산)
C1_DELTA, C2_DELTA = 0.01, 0.03                      # 공통 서열효과
C3_GIN_DROP = 0.03                                   # GIN 전반 성능 하향

# AE-6 운용
W_BEST = 18
RAM_BUDGET_GIB = 38.4
RAM_GATE_GIB = 30.72
CKPT_FLUSH = 1

# 블록 AD 확정 예산 입력 (F-UNIT · F-THRU · F-DECAY) — 재계산 입력값
F_UNIT_SMALL = 0.09966293053515983
F_UNIT_FULL = 0.7166503799495937
F_THRU_SMALL = 89.25498762598825
F_THRU_FULL = 8.932070676515567
F_DECAY = 0.24885474349420722
COWORK_REF_HOURS = {"c03_primary": 62.19, "c03_sensitivity": 31.09, "c4": 46.61, "total": 139.93}

# 블록 AD 보정계수 기준값 (규모별 **분리** — 섞지 않는다)
AD5_SLOPE_SMALL = 0.5002369486829041                 # AD-5, 축소 규모
AD44_SLOPE_FULL = 0.591610555379263                  # AD-4-4 bridge, 전규모(R=10 해상도)

# FACTS registry §1 기대값
FACTS_EXPECT = {
    "F-ROWIDX": "c659db38abbd8154",
    "F-PTCOL": "b24f0588c9f0c53c",
    "F-PROF-P": {"G": 313, "G_eff": 77.595, "ratio": 0.24791, "top2": 0.14250},
    "F-PROF-R": {"G": 210, "G_eff": 27.836, "ratio": 0.13255, "sum_sq": 5748},
    "F-GEFF": {"G_eff": 85.34669, "ratio": 0.116594, "top2": 0.14194},
    "F-MANI16": {"sha16": "756d485feb4715e9", "sap_version": "1.1"},
    "F-SEALED": {"excl_access_log": 275, "all": 291},
    "F-CORE": {"logical": 18, "ram_budget_gib": 38.4, "ram_gate_gib": 30.72},
}

FREEZE_SAP_MODULES = ["__init__.py", "metrics.py", "redaction.py", "consensus.py", "bootstrap.py",
                      "signflip.py", "decision.py", "null_generator.py", "unseen_target.py",
                      "synthetic.py", "freeze.py"]
FREEZE_OTHER = [
    "experiments/sap/manifest.json",
    "v3_Multimodal/config/ladder_freeze.json",
    "v3_Multimodal/config/gin_seed_freeze.json",
    # 블록 AC 산출 4파일
    "v3_Multimodal/src/sap/rqint.py",
    "v3_Multimodal/src/sap/rqint_synthetic.py",
    "v3_Multimodal/src/sap/rqint_audit.py",
    "v3_Multimodal/src/run_rqint_audit.py",
    # 블록 AD 산출 2파일
    "v3_Multimodal/src/rqint_timing.py",
    "v3_Multimodal/src/rqint_reduced_fixture.py",
]


# ══════════════════════════════════════════════════════════════════════════════
# 유틸
# ══════════════════════════════════════════════════════════════════════════════
def now_kst():
    return datetime.now(KST).isoformat(timespec="seconds")


def _native(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(str(type(o)))


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=_native)
    return path


def load_json(path):
    with open(path) as f:
        return json.load(f)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception as e:                                           # pragma: no cover
        return f"<err {e}>"


def env_snapshot():
    try:
        from threadpoolctl import threadpool_info
        tp = [{k: v for k, v in d.items() if k in ("user_api", "num_threads", "prefix")}
              for d in threadpool_info()]
    except Exception as e:                                           # pragma: no cover
        tp = f"<threadpoolctl unavailable: {e}>"
    vm = psutil.virtual_memory()
    ps = sh("pmset -g ps | head -3")
    return {
        "when_kst": now_kst(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__, "pandas": pd.__version__,
        "scipy": __import__("scipy").__version__,
        "logical_cores": os.cpu_count(),
        "mem_total_gib": round(vm.total / 2**30, 3),
        "mem_available_gib": round(vm.available / 2**30, 3),
        "pmset_powermode": sh("pmset -g | awk '/powermode/{print $2}'"),
        "pmset_ps": ps,
        "on_ac_power": ("AC Power" in ps),
        "caffeinate_running": bool(sh("pgrep -f 'caffeinate -dimsu' | head -1")),
        "loadavg_1_5_15": [round(v, 2) for v in os.getloadavg()],
        "env_thread_vars": {v: os.environ.get(v) for v in _THREAD_VARS},
        "threadpool_info": tp,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 설계량 로드 — 라벨행렬 + scaffold 군집구조만 (예측·OOF·봉인 **미접근**)
# ══════════════════════════════════════════════════════════════════════════════
def load_design_arrays():
    X = pd.read_parquet(F_MASTER_X).sort_values("cid").reset_index(drop=True)
    Y = pd.read_parquet(F_MASTER_Y).sort_values("cid").reset_index(drop=True)
    if not np.array_equal(X["cid"].values, Y["cid"].values):
        raise SystemExit("중단: master_X/master_Y 의 cid 정렬 불일치")
    pt_names = [c for c in Y.columns if c != "cid"]
    y = Y[pt_names].to_numpy(dtype=np.int8)
    n, k = y.shape
    if n != EXPECT_N or k != EXPECT_K:
        raise SystemExit(f"중단: 형상 불일치 N={n}(기대 {EXPECT_N}) K={k}(기대 {EXPECT_K})")
    scaf = [scaffold_of(s) for s in X["smiles_canonical"].tolist()]      # F-SCAF 재사용
    uniq = sorted(set(scaf))
    idx = {g: i for i, g in enumerate(uniq)}
    g_of_row = np.array([idx[s] for s in scaf], dtype=int)
    if len(uniq) != EXPECT_G:
        raise SystemExit(f"중단: scaffold group {len(uniq)} != {EXPECT_G} (군 정의 분기)")
    return {"y": y, "g_of_row": g_of_row, "pt_names": pt_names, "n_groups": len(uniq)}


def build_fixtures(d):
    """축소 fixture(두 변형) + 전규모. 규칙 모듈은 import 재사용(재구현 0)."""
    y, g = d["y"], d["g_of_row"]
    full_prof = rfix.group_profile(g)
    row_idx, lab_prop, _ = rfix.allocate_rows_proportional(g, N_TARGET)
    y_rows = y[row_idx]
    cols, pinfo = rfix.select_pts_by_prevalence(y_rows, d["pt_names"], K_TARGET)
    y_small = np.ascontiguousarray(y_rows[:, cols])
    lab_ratio, opt_info = rfix.regroup_ratio_optimal(lab_prop, full_prof["G_eff_over_G"], n_top=2)
    return {
        "full": {"y": y, "groups": g, "eligible": np.arange(EXPECT_K), "profile": full_prof},
        "prop": {"y": y_small, "groups": lab_prop, "eligible": np.arange(K_TARGET),
                 "profile": rfix.group_profile(lab_prop)},
        "ratio": {"y": y_small, "groups": lab_ratio, "eligible": np.arange(K_TARGET),
                  "profile": rfix.group_profile(lab_ratio)},
        "row_idx": row_idx, "pt_cols": cols, "pt_info": pinfo, "regroup_info": opt_info,
        "row_idx_sha256": hashlib.sha256(np.asarray(row_idx).tobytes()).hexdigest(),
        "pt_cols_sha256": hashlib.sha256(np.asarray(cols).tobytes()).hexdigest(),
        "lab_prop_sha256": hashlib.sha256(np.asarray(lab_prop).tobytes()).hexdigest(),
        "lab_ratio_sha256": hashlib.sha256(np.asarray(lab_ratio).tobytes()).hexdigest(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# AE-1-2 · 효과 주입 (동결 5요소) — 단일 생성기 + 시나리오별 강도표
# ══════════════════════════════════════════════════════════════════════════════
INJECTION_SPEC = {
    "1_shift_mechanism": (
        "합성 점수행렬의 **logit 척도 상수 가산**. 블록 AD `synth_common_effect` 기전을 **그대로 계승** — "
        "`_scores_from_labels(rng, y, strength)` 가 `logit = strength·(y − colmean(y)) + N(0,1)` 을 만들고 "
        "점수는 `sigmoid(logit)`. 강도를 `base → base + d` 로 올리면 PT j 의 **양성 라벨 원소** logit 에 "
        "상수 `+d·(1 − prev_j)` 가, **음성 원소** logit 에 상수 `−d·prev_j` 가 가산된다(행 내 상수, 열별 고정). "
        "결측 없음(라벨행렬은 0/1 조밀행렬, NaN 0건). 클리핑 없음(sigmoid 치역이 (0,1) 로 자연 유계, "
        "점수 절단·재정규화 0). ★ 사후 변경 0."),
    "2_attribution": (
        "C1·C2 = **양 family 의 M2b arm 에 동일한 δ**(RF·GIN 공통) → E[Δ_RF] = E[Δ_GIN] = δ, E[T] = 0. "
        "C3 = **GIN family 의 두 arm(M1b·M2b)을 동일 크기로 하향** → 수준만 낮아지고 Δ_GIN 불변, E[T] = 0 "
        "(arm 간 차등 이동 금지 — 코드 assert). "
        "C4 = **RF family 의 M2b arm 에만 τ** 가산, 공통 성분 0 → E[T] = +τ. 부호 **양(+) 사전 고정**."),
    "3_heterogeneity": (
        "**동질(homogeneous) 주입**을 primary 로 동결 — 모든 PT·모든 scaffold 군에 동일 강도 상수를 준다. "
        "군별·PT별 이질 주입은 본 블록 범위 밖이며 사후 도입 0."),
    "4_ties": (
        "합성 점수는 연속(sigmoid of 연속 logit) — 블록 AD 실측 tie 율 0.0. "
        "**jitter·난수 tie-break 추가 0.** AP 는 `sap.metrics.macro_ap` 를 import 재사용(재구현 0, "
        "tie 처리 = sklearn `average_precision_score` 표준). tie 가 1건이라도 관측되면 값을 그대로 두고 보고."),
    "5_slot_mapping": (
        "arm 슬롯은 `sap/rqint.py` 인터페이스 그대로 — P_RF={'M1b':[rep×3],'M2b':[rep×3]}, "
        "P_GIN={'M1b':{s:[rep×3]},'M2b':{s:[rep×3]}}, s ∈ (1,2,3). "
        "**합성 자가시험 1건**(큰 τ 를 RF M2b 에만 주입 → Δ_RF − Δ_GIN 의 부호·크기가 기대와 일치)으로 "
        "매핑을 확인한 뒤 본런에 들어간다."),
}


def strengths_for(scen, effect_logit, tau_logit=None):
    """시나리오별 arm 강도표. **여기가 효과 주입의 유일한 지점**이다."""
    b = BASE_STRENGTH
    if scen == "C0":
        st = {"RF": {"M1b": b, "M2b": b}, "GIN": {"M1b": b, "M2b": b}}
    elif scen in ("C1", "C2"):
        st = {"RF": {"M1b": b, "M2b": b + effect_logit},
              "GIN": {"M1b": b, "M2b": b + effect_logit}}
    elif scen == "C3":
        st = {"RF": {"M1b": b, "M2b": b},
              "GIN": {"M1b": b - effect_logit, "M2b": b - effect_logit}}
    elif scen == "C4":
        st = {"RF": {"M1b": b, "M2b": b + tau_logit},
              "GIN": {"M1b": b, "M2b": b}}
    else:
        raise ValueError(scen)
    _assert_scenario(scen, st)
    return st


def _assert_scenario(scen, st):
    """중단 조건 — 시나리오 정의 붕괴 감지 (C3 arm 차등 주입 0 등)."""
    d_rf = st["RF"]["M2b"] - st["RF"]["M1b"]
    d_gin = st["GIN"]["M2b"] - st["GIN"]["M1b"]
    if scen == "C0":
        assert d_rf == 0.0 and d_gin == 0.0, "C0: 양 family arm 차이 0 이어야 한다"
    elif scen in ("C1", "C2"):
        assert d_rf == d_gin and d_rf > 0.0, f"{scen}: 양 family M2b 에 공통 δ (E[T]=0)"
    elif scen == "C3":
        assert d_gin == 0.0, "★중단★ C3 에서 Δ_GIN 이 이동(arm 간 차등 주입) — 시나리오 정의 붕괴"
        assert d_rf == 0.0, "C3: RF arm 차이 0 이어야 한다"
        assert st["GIN"]["M1b"] < st["RF"]["M1b"], "C3: GIN 수준이 하향돼야 한다"
    elif scen == "C4":
        assert d_gin == 0.0, "C4: GIN arm 차이 0(상호작용만 이식)"
        assert d_rf > 0.0, "C4: RF M2b 에만 양(+) τ"
        assert st["GIN"]["M1b"] == st["RF"]["M1b"] == BASE_STRENGTH, "C4: 공통 성분 0 고정"


def synth_scores(y, seed, st):
    """합성 예측행렬 8×3 (100% 합성). 추첨 순서는 AD `synth_common_effect` 와 **동일**."""
    rng = np.random.default_rng(seed)
    P_RF = {"M1b": [_scores_from_labels(rng, y, strength=st["RF"]["M1b"]) for _ in range(N_REPS)],
            "M2b": [_scores_from_labels(rng, y, strength=st["RF"]["M2b"]) for _ in range(N_REPS)]}
    P_GIN = {"M1b": {}, "M2b": {}}
    for s in SEEDS_S:
        P_GIN["M1b"][s] = [_scores_from_labels(rng, y, strength=st["GIN"]["M1b"])
                           for _ in range(N_REPS)]
        P_GIN["M2b"][s] = [_scores_from_labels(rng, y, strength=st["GIN"]["M2b"])
                           for _ in range(N_REPS)]
    return P_RF, P_GIN


def observed_only(y, eligible, seed, st):
    """순열 없이 관측 통계량만(효과 보정 probe 용). macro-AP 8회."""
    P_RF, P_GIN = synth_scores(y, seed, st)
    mats, seeds = sap_rqint.build_eight_consensus(P_RF, P_GIN)
    return sap_rqint.observed_statistic(mats, seeds, y, eligible)


def level_macro(y, eligible, seed, st, family, arm):
    """단일 arm 의 macro-AP 수준(계측 — C3 하향폭 확인용)."""
    P_RF, P_GIN = synth_scores(y, seed, st)
    mats, seeds = sap_rqint.build_eight_consensus(P_RF, P_GIN)
    key = ("RF", None, arm) if family == "RF" else ("GIN", seeds[0], arm)
    from sap.metrics import macro_ap
    return macro_ap(y, mats[key], eligible)["macro_ap"]


def calibrate_slope(y, eligible, seed0, probe_effects, n_probe):
    """강도(logit) → 실현 Δ 의 원점통과 최소제곱 기울기 (AD `_calibrate_effect` 규격 계승)."""
    curve = []
    for e in probe_effects:
        ds = []
        for i in range(n_probe):
            st = {"RF": {"M1b": BASE_STRENGTH, "M2b": BASE_STRENGTH + e},
                  "GIN": {"M1b": BASE_STRENGTH, "M2b": BASE_STRENGTH + e}}
            ds.append(observed_only(y, eligible, seed0 + i, st)[1])       # Δ_RF
        curve.append({"effect": float(e), "mean_delta_rf": float(np.mean(ds)),
                      "sd": float(np.std(ds, ddof=1))})
    xs = np.array([c["effect"] for c in curve])
    ys = np.array([c["mean_delta_rf"] for c in curve])
    slope = float(np.sum(xs * ys) / np.sum(xs * xs))
    return {"probe_curve": curve, "slope_delta_per_effect": slope,
            "fit": "origin-through linear least squares (Δ(0)=0 by construction)",
            "n_probe_replicates": int(n_probe), "seed0": int(seed0),
            "probe_effects": [float(v) for v in probe_effects]}


def tie_rate(P):
    n = P.shape[0]
    return float(np.mean([1.0 - len(np.unique(P[:, j])) / n for j in range(P.shape[1])]))


# ══════════════════════════════════════════════════════════════════════════════
# 셀 정의 · 시드 규약
# ══════════════════════════════════════════════════════════════════════════════
def cells_spec():
    out = []
    for scen in ("C0", "C1", "C2", "C3"):
        for variant, R in (("prop", R_PRIMARY), ("ratio", R_SENS)):
            out.append({"cell": f"{scen}:{variant}", "scenario": scen, "variant": variant,
                        "scale": "small", "R": R, "n_coin": NCOIN_SMALL,
                        "role": "primary" if variant == "prop" else "sensitivity",
                        "grid_index": 0, "tau": None})
    for gi, tau in enumerate(TAU_GRID):
        out.append({"cell": f"C4:tau{tau}", "scenario": "C4", "variant": "full",
                    "scale": "full", "R": R_C4, "n_coin": NCOIN_FULL,
                    "role": "power", "grid_index": gi, "tau": float(tau)})
    return out


def rep_seed_of(scen, variant, grid_index, r):
    """AE-2 시드 규칙. 신규 추첨 0 · 재추첨 0."""
    return (BASE_SEED + 1_000_000 * SCEN_INDEX[scen]
            + VARIANT_OFFSET.get(variant, 0) + 100_000 * grid_index + r)


SEED_RULE_TEXT = ("rep_seed = 20260813 + 1_000_000·scenario_index + variant_offset "
                  "+ 100_000·grid_index + r  (scenario_index C0..C4 = 0..4; "
                  "variant_offset prop=0 / ratio=500_000 / full=0; grid_index = τ 격자 위치). "
                  "동전 RNG 시드 = rep_seed + 900_000_000 (결정적 파생, 신규 추첨 0). "
                  "probe/자가시험 시드 = 20260813 + 800/810/820 × 1_000_000 (결정적 파생).")


def confirmatory_seed_space():
    """확증 시드 공간 — 교집합 0 assert 용."""
    gsf = load_json(os.path.join(CFG_DIR, "gin_seed_freeze.json"))
    seeds = set(int(v) for v in gsf.get("training_seeds_ordered", []))
    seeds |= set(int(v) for v in gsf.get("stability_seeds", []))
    seeds |= set(int(v) for v in gsf.get("confirmatory_seed_prefix", []))
    seeds |= {201, 202, 203}                       # split seeds (확증 3반복)
    seeds |= {42}                                  # 개발 split seed
    return seeds


# ══════════════════════════════════════════════════════════════════════════════
# 워커
# ══════════════════════════════════════════════════════════════════════════════
_W = {}


def _init_worker(y, groups, eligible, st, n_coin, threads, t0):
    for v in _THREAD_VARS:
        os.environ[v] = str(threads)
    tpl = None
    try:
        from threadpoolctl import threadpool_limits
        tpl = threadpool_limits(limits=int(threads))
    except Exception:
        pass
    _W.update(y=y, groups=groups, eligible=eligible, st=st, n_coin=n_coin, t0=t0,
              threads=int(threads), _tpl=tpl)


def _work(task):
    rep_seed, audit_draws = task
    s = time.time()
    P_RF, P_GIN = synth_scores(_W["y"], rep_seed, _W["st"])
    res = sap_rqint.rqint_test(P_RF, P_GIN, _W["y"], _W["groups"], _W["eligible"],
                               n_coin_vectors=_W["n_coin"],
                               seed=rep_seed + COIN_SEED_OFFSET,
                               pair_complement=True,
                               complement_audit_draws=int(audit_draws),
                               return_perm=True)
    perm = res.pop("perm")
    t_star = np.asarray(perm[:_W["n_coin"]], dtype=np.float64)
    e = time.time()
    row = {
        "rep_seed": int(rep_seed), "pid": os.getpid(),
        "start_rel": s - _W["t0"], "end_rel": e - _W["t0"], "task_seconds": e - s,
        "p_two_sided": float(res["p_two_sided"]),
        "T_obs": float(res["T_obs"]),
        "delta_rf": float(res["delta_rf"]), "delta_gin": float(res["delta_gin"]),
        "abs_gap": float(abs(res["T_obs"])),
        "count_abs_ge_obs": int(res["count_abs_ge_obs"]),
        "n_coin_vectors": int(res["n_coin_vectors"]),
        "n_permutation_values": int(res["n_permutation_values"]),
        "n_groups_G": int(res["n_groups_G"]),
        "t_star_sha256": hashlib.sha256(t_star.tobytes()).hexdigest(),
        "per_permutation_seconds": float(res["per_permutation_seconds"]),
        "threads_limit": _W["threads"],
    }
    if audit_draws:
        row["complement_audit"] = res["complement_audit"]
        row["complement_identity_used"] = bool(res["complement_identity_used"])
        row["score_tie_rate_m1b_rf"] = tie_rate(P_RF["M1b"][0])
    return row


class RamSampler(threading.Thread):
    """10초 주기 워커 RSS 합계 샘플 + 라이브 게이트(임계 30.72 GiB)."""

    def __init__(self, threshold_gib=RAM_GATE_GIB, period=10.0):
        super().__init__(daemon=True)
        self.period, self.threshold = period, threshold_gib
        self.samples, self.breaches = [], []
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
            g = tot / 2**30
            self.samples.append(g)
            if g > self.threshold:
                self.breaches.append({"when_kst": now_kst(), "rss_sum_gib": g})
            self._stop.wait(self.period)

    def stop(self):
        self._stop.set()


# ══════════════════════════════════════════════════════════════════════════════
# 체크포인트
# ══════════════════════════════════════════════════════════════════════════════
def ckpt_path(cell):
    return os.path.join(CKPT_DIR, f"calibration_{cell.replace(':', '_')}.jsonl")


def ckpt_load(cell):
    p = ckpt_path(cell)
    if not os.path.exists(p):
        return []
    rows, seen = [], set()
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r["rep_seed"] in seen:                 # 재개 시 중복 복제 0 (종료검증 25)
                continue
            seen.add(r["rep_seed"])
            rows.append(r)
    return rows


def ckpt_append(cell, rows):
    os.makedirs(CKPT_DIR, exist_ok=True)
    with open(ckpt_path(cell), "a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=_native) + "\n")
        f.flush()
        os.fsync(f.fileno())


def session_log(rec):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(F_SESSIONS, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=_native) + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# 통계 (본런 측) — ★ 독립 재계산은 rqint_calibration_verify.py 가 별도로 수행(A21)
# ══════════════════════════════════════════════════════════════════════════════
def wilson_ci(k, n, z=1.959963984540054):
    if n == 0:
        return [float("nan"), float("nan")]
    ph = k / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    hw = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return [float((c - hw) / d), float((c + hw) / d)]


def rate_table(p):
    p = np.asarray(p, dtype=float)
    R = int(p.size)
    out = {}
    for name, thr in POINTS.items():
        k = int((p <= thr).sum())
        r = k / R
        se = math.sqrt(max(r * (1 - r), 0.0) / R)
        out[name] = {"threshold": float(thr), "n_reject": k, "R": R,
                     "rejection_rate": float(r), "SE_rhat": float(se),
                     "acceptance_bound_alpha_plus_2SE": float(ALPHA + 2 * se),
                     "wilson95": wilson_ci(k, R),
                     "is_official_decision_point": (name == OFFICIAL_POINT)}
    return out


def ks_uniform(p):
    from scipy.stats import kstest
    r = kstest(np.asarray(p, dtype=float), "uniform")
    return {"statistic": float(r.statistic), "p_value": float(r.pvalue),
            "implementation": "scipy.stats.kstest(p,'uniform')"}


# ══════════════════════════════════════════════════════════════════════════════
# STAGE: facts — FACTS registry §1 전건 실측 대조 + 동결물 baseline
# ══════════════════════════════════════════════════════════════════════════════
def sealed_stat_snapshot():
    rows = []
    for dirpath, _, files in os.walk(RUNS_DIR):
        if "_sealed" not in dirpath.split(os.sep):
            continue
        for fn in sorted(files):
            fp = os.path.join(dirpath, fn)
            stt = os.stat(fp)                    # stat-only — 내용 읽기 0
            rows.append({"path": os.path.relpath(fp, ROOT), "size": stt.st_size,
                         "mtime_ns": stt.st_mtime_ns})
    rows.sort(key=lambda r: r["path"])
    blob = json.dumps(rows, ensure_ascii=False).encode()
    return {"n_files_all": len(rows),
            "n_files_excl_access_log": sum(1 for r in rows if not r["path"].endswith("access.log")),
            "snapshot_sha256": hashlib.sha256(blob).hexdigest(), "rows": rows}


def freeze_baseline():
    out = {"sap_modules": {}, "other": {}}
    for fn in FREEZE_SAP_MODULES:
        out["sap_modules"][fn] = sha256_file(os.path.join(SAP_DIR, fn))
    for rel in FREEZE_OTHER:
        out["other"][rel] = sha256_file(os.path.join(ROOT, rel))
    out["sap_dir_listing"] = sorted(f for f in os.listdir(SAP_DIR) if f.endswith(".py"))
    return out


def stage_facts(a):
    env = env_snapshot()
    d = load_design_arrays()
    fx = build_fixtures(d)
    from sap.decision import HOLM_FAMILY
    from sap.metrics import macro_ap
    mani_path = os.path.join(ROOT, "experiments", "sap", "manifest.json")
    mani = load_json(mani_path)
    mani_sha = sha256_file(mani_path)

    # macro_ap n_eligible 실측(중단 조건)
    st0 = strengths_for("C0", 0.0)
    P_RF_s, _ = synth_scores(fx["prop"]["y"], SELFTEST_SEED, st0)
    m_small = macro_ap(fx["prop"]["y"], P_RF_s["M1b"][0], fx["prop"]["eligible"])
    P_RF_f, _ = synth_scores(fx["full"]["y"], SELFTEST_SEED, st0)
    m_full = macro_ap(fx["full"]["y"], P_RF_f["M1b"][0], fx["full"]["eligible"])

    sealed = sealed_stat_snapshot()
    ex = FACTS_EXPECT
    pp, pr, pf = fx["prop"]["profile"], fx["ratio"]["profile"], fx["full"]["profile"]

    def chk(fid, expect, got, ok):
        return {"fact": fid, "expect": expect, "measured": got, "pass": bool(ok)}

    tol = 5e-4
    facts = [
        chk("F-N", EXPECT_N, int(d["y"].shape[0]), d["y"].shape[0] == EXPECT_N),
        chk("F-K", EXPECT_K, int(d["y"].shape[1]), d["y"].shape[1] == EXPECT_K),
        chk("F-G", EXPECT_G, int(d["n_groups"]), d["n_groups"] == EXPECT_G),
        chk("F-SCAF", "confirmatory_oof_rep1.scaffold_of (import 재사용)",
            f"{scaffold_of.__module__}.{scaffold_of.__name__}",
            scaffold_of.__module__ == "confirmatory_oof_rep1"),
        chk("F-ROWIDX", ex["F-ROWIDX"], fx["row_idx_sha256"][:16],
            fx["row_idx_sha256"][:16] == ex["F-ROWIDX"]),
        chk("F-PTCOL", ex["F-PTCOL"], fx["pt_cols_sha256"][:16],
            fx["pt_cols_sha256"][:16] == ex["F-PTCOL"]),
        chk("F-PROF-P", ex["F-PROF-P"],
            {"G": pp["G"], "G_eff": round(pp["G_eff_kish"], 3),
             "ratio": round(pp["G_eff_over_G"], 5), "top2": round(pp["top2_row_share"], 5)},
            pp["G"] == 313 and abs(pp["G_eff_kish"] - 77.595) < 1e-2
            and abs(pp["G_eff_over_G"] - 0.24791) < tol
            and abs(pp["top2_row_share"] - 0.14250) < tol),
        chk("F-PROF-R", ex["F-PROF-R"],
            {"G": pr["G"], "G_eff": round(pr["G_eff_kish"], 3),
             "ratio": round(pr["G_eff_over_G"], 5), "sum_sq": int(pr["sum_sq"])},
            pr["G"] == 210 and abs(pr["G_eff_kish"] - 27.836) < 1e-2
            and abs(pr["G_eff_over_G"] - 0.13255) < tol and int(pr["sum_sq"]) == 5748),
        chk("F-GEFF", ex["F-GEFF"],
            {"G_eff": round(pf["G_eff_kish"], 5), "ratio": round(pf["G_eff_over_G"], 6),
             "top2": round(pf["top2_row_share"], 5)},
            abs(pf["G_eff_kish"] - 85.34669) < 1e-4
            and abs(pf["G_eff_over_G"] - 0.116594) < 1e-5
            and abs(pf["top2_row_share"] - 0.14194) < 1e-4),
        chk("F-UNIT", {"full": F_UNIT_FULL, "small": F_UNIT_SMALL},
            {k: load_json(os.path.join(OUT_DIR, "timing.json"))
             ["unit_costs_single_worker_w1"]["threads_1"][k]["per_permutation_seconds"]
             for k in ("full", "small")},
            abs(load_json(os.path.join(OUT_DIR, "timing.json"))["unit_costs_single_worker_w1"]
                ["threads_1"]["full"]["per_permutation_seconds"] - F_UNIT_FULL) < 1e-12
            and abs(load_json(os.path.join(OUT_DIR, "timing.json"))["unit_costs_single_worker_w1"]
                    ["threads_1"]["small"]["per_permutation_seconds"] - F_UNIT_SMALL) < 1e-12),
        chk("F-THRU", {"small": F_THRU_SMALL, "full": F_THRU_FULL, "W_BEST": W_BEST},
            {k: load_json(os.path.join(OUT_DIR, "budget.json"))["measured_anchors"][k]
             for k in ("evals_per_second_small_at_W_BEST", "evals_per_second_full_at_W_BEST",
                       "W_BEST_small")},
            abs(load_json(os.path.join(OUT_DIR, "budget.json"))["measured_anchors"]
                ["evals_per_second_small_at_W_BEST"] - F_THRU_SMALL) < 1e-9),
        chk("F-DECAY", 0.2489,
            load_json(os.path.join(OUT_DIR, "budget.json"))["measured_anchors"]
            ["thermal_inflation_used_in_budget"],
            abs(load_json(os.path.join(OUT_DIR, "budget.json"))["measured_anchors"]
                ["thermal_inflation_used_in_budget"] - F_DECAY) < 1e-12),
        chk("F-HOLM", 7, len(HOLM_FAMILY), len(HOLM_FAMILY) == 7),
        chk("F-CORE", ex["F-CORE"],
            {"logical": os.cpu_count(), "mem_total_gib": env["mem_total_gib"]},
            os.cpu_count() == 18),
        chk("F-MANI16", ex["F-MANI16"],
            {"sha16": mani_sha[:16], "sap_version": mani.get("sap_version")},
            mani_sha[:16] == ex["F-MANI16"]["sha16"] and mani.get("sap_version") == "1.1"),
        chk("F-SEALED", ex["F-SEALED"],
            {"excl_access_log": sealed["n_files_excl_access_log"], "all": sealed["n_files_all"]},
            sealed["n_files_excl_access_log"] == 275 and sealed["n_files_all"] == 291),
        chk("macro_ap.n_eligible(small)", K_TARGET, m_small["n_eligible"],
            m_small["n_eligible"] == K_TARGET and m_small["n_excluded_undefined"] == 0),
        chk("macro_ap.n_eligible(full)", EXPECT_K, m_full["n_eligible"],
            m_full["n_eligible"] == EXPECT_K and m_full["n_excluded_undefined"] == 0),
    ]
    out = {
        "_doc": "블록 AE / §1 FACTS registry (A20) 착수 실측 대조 + 동결물 baseline. "
                "예측 100% 합성 · 확증/봉인 미접근.",
        "block": "AE", "instruction": "docs/93_r1_calibration_audit_prompt_for_vscode.md",
        "when_kst": now_kst(), "env": env,
        "predictions_are_synthetic": True, "confirmatory_predictions_loaded": False,
        "confirmatory_data_accessed": False, "sealed_accessed": False,
        "unblinding_performed": False, "gin_start_still_blocked": True,
        "facts": facts,
        "all_facts_pass": all(f["pass"] for f in facts),
        "fixture_hashes": {k: fx[k] for k in ("row_idx_sha256", "pt_cols_sha256",
                                              "lab_prop_sha256", "lab_ratio_sha256")},
        "profiles": {"full": pf, "reduced_proportional": pp, "reduced_ratio_optimal": pr},
        "regroup_info": fx["regroup_info"],
        "freeze_baseline": freeze_baseline(),
        "sealed_snapshot": sealed,
    }
    dump(F_FACTS, out)
    print(json.dumps([{k: f[k] for k in ("fact", "pass")} for f in facts],
                     ensure_ascii=False, indent=1))
    print("ALL FACTS PASS =", out["all_facts_pass"])
    if not out["all_facts_pass"]:
        raise SystemExit("중단: FACTS registry 불일치")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE: design — AE-0 · AE-1 · AE-2 착수 전 동결
# ══════════════════════════════════════════════════════════════════════════════
def budget_recompute():
    rows = []

    def add(name, evals, thru):
        base_s = evals / thru
        wall_s = base_s * (1.0 + F_DECAY)
        rows.append({"block": name, "evals": int(evals), "throughput_evals_per_s": thru,
                     "wall_seconds_before_decay": base_s, "wall_hours": wall_s / 3600.0})
    add("C0~C3 primary (4 × 2,000복제 × 2,000순열)", 4 * R_PRIMARY * NCOIN_SMALL, F_THRU_SMALL)
    add("C0~C3 sensitivity (4 × 1,000복제 × 2,000순열)", 4 * R_SENS * NCOIN_SMALL, F_THRU_SMALL)
    add("C4 (3τ × 400복제 × 1,000순열)", len(TAU_GRID) * R_C4 * NCOIN_FULL, F_THRU_FULL)
    audit_evals = 8 * AUDIT_DRAWS + 3 * AUDIT_DRAWS
    audit_h = ((8 * AUDIT_DRAWS) / F_THRU_SMALL + (3 * AUDIT_DRAWS) / F_THRU_FULL) \
        * (1 + F_DECAY) / 3600.0
    rows.append({"block": "여집합 감사 (11셀 × 1,000 draw)", "evals": int(audit_evals),
                 "throughput_evals_per_s": None, "wall_seconds_before_decay": None,
                 "wall_hours": audit_h})
    total_ev = sum(r["evals"] for r in rows)
    total_h = sum(r["wall_hours"] for r in rows)
    ref = COWORK_REF_HOURS
    dev = {"c03_primary": rows[0]["wall_hours"] / ref["c03_primary"] - 1,
           "c03_sensitivity": rows[1]["wall_hours"] / ref["c03_sensitivity"] - 1,
           "c4": rows[2]["wall_hours"] / ref["c4"] - 1,
           "total": total_h / ref["total"] - 1}
    return {
        "inputs": {"F_UNIT_small": F_UNIT_SMALL, "F_UNIT_full": F_UNIT_FULL,
                   "F_THRU_small": F_THRU_SMALL, "F_THRU_full": F_THRU_FULL,
                   "F_DECAY": F_DECAY, "W_BEST": W_BEST},
        "formula": "wall = evals / throughput(W_BEST) × (1 + F_DECAY);  "
                   "throughput 정의 = w / wall_max (평균 기반 금지)",
        "rows": rows, "total_evals": int(total_ev), "total_wall_hours": total_h,
        "total_wall_days": total_h / 24.0, "exceeds_7d": bool(total_h / 24.0 > 7.0),
        "cowork_reference_hours": ref, "deviation_frac_vs_cowork": dev,
        "max_abs_deviation_frac": max(abs(v) for v in dev.values()),
        "within_5pct": bool(max(abs(v) for v in dev.values()) <= 0.05),
        "note": "A12 발동 시 C4 는 이보다 줄어든다(상한 기준).",
    }


def stage_design(a):
    if os.path.exists(F_DESIGN) and not a.force:
        raise SystemExit(f"중단: {F_DESIGN} 이 이미 존재한다(동결본 재기입 금지). "
                         "의도적 재생성이면 --force.")
    t_start = now_kst()
    facts = load_json(F_FACTS)
    if not facts["all_facts_pass"]:
        raise SystemExit("중단: FACTS 미통과 상태에서 design 동결 불가")
    d = load_design_arrays()
    fx = build_fixtures(d)

    # ── AE-1-2 · probe (계측 · 판정 아님) ────────────────────────────────────
    probe_effects = (0.01, 0.02, 0.05, 0.10)
    cal_small = calibrate_slope(fx["prop"]["y"], fx["prop"]["eligible"],
                                PROBE_SEED_SMALL, probe_effects, 40)
    cal_small["reference_AD5_slope"] = AD5_SLOPE_SMALL
    cal_small["ratio_vs_reference"] = cal_small["slope_delta_per_effect"] / AD5_SLOPE_SMALL
    cal_full = calibrate_slope(fx["full"]["y"], fx["full"]["eligible"],
                               PROBE_SEED_FULL, probe_effects, 40)
    cal_full["reference_AD44_slope"] = AD44_SLOPE_FULL
    cal_full["reference_resolution_note"] = "AD-4-4 는 R=10 해상도 → 본 probe 는 R=40 으로 재산출"
    cal_full["ratio_vs_reference"] = cal_full["slope_delta_per_effect"] / AD44_SLOPE_FULL

    s_small = cal_small["slope_delta_per_effect"]
    s_full = cal_full["slope_delta_per_effect"]

    chosen = {
        "C0": {"effect_logit": 0.0, "target_macro_ap_shift": 0.0, "slope_scale": "small"},
        "C1": {"effect_logit": C1_DELTA / s_small, "target_macro_ap_shift": C1_DELTA,
               "slope_scale": "small"},
        "C2": {"effect_logit": C2_DELTA / s_small, "target_macro_ap_shift": C2_DELTA,
               "slope_scale": "small"},
        "C3": {"effect_logit": C3_GIN_DROP / s_small, "target_macro_ap_shift": -C3_GIN_DROP,
               "slope_scale": "small"},
        "C4": {"tau_logit": {str(t): t / s_full for t in TAU_GRID},
               "target_macro_ap_shift": {str(t): t for t in TAU_GRID},
               "slope_scale": "full"},
    }

    # ── AE-1-2 #5 · 슬롯 매핑 합성 자가시험 (블록 L 선례) ──────────────────────
    big_tau = 0.10 / s_small
    st_big = strengths_for("C4", 0.0, tau_logit=big_tau)
    gaps = []
    for i in range(12):
        t, drf, dgin, _ = observed_only(fx["prop"]["y"], fx["prop"]["eligible"],
                                        SELFTEST_SEED + i, st_big)
        gaps.append({"T": t, "delta_rf": drf, "delta_gin": dgin})
    mT = float(np.mean([g["T"] for g in gaps]))
    self_test = {
        "design": "RF M2b 에만 큰 τ(logit %.6f ≈ macro-AP 0.10) 주입 → T = Δ_RF − Δ_GIN 이 "
                  "명확히 양(+)이고 크기가 기대와 일치해야 한다." % big_tau,
        "R": len(gaps), "mean_T": mT,
        "mean_delta_rf": float(np.mean([g["delta_rf"] for g in gaps])),
        "mean_delta_gin": float(np.mean([g["delta_gin"] for g in gaps])),
        "expected_T_approx": 0.10,
        "sign_ok": bool(mT > 0), "magnitude_ratio_vs_expected": float(mT / 0.10),
        "pass": bool(mT > 0 and 0.5 < mT / 0.10 < 1.5),
    }
    if not self_test["pass"]:
        raise SystemExit(f"중단: 슬롯 매핑 자가시험 실패 — {self_test}")

    # ── C3 수준 하향폭 확인 (계측) ────────────────────────────────────────────
    st_c3 = strengths_for("C3", chosen["C3"]["effect_logit"])
    st_c0 = strengths_for("C0", 0.0)
    lv = [(level_macro(fx["prop"]["y"], fx["prop"]["eligible"], SELFTEST_SEED + 100 + i,
                       st_c0, "GIN", "M1b"),
           level_macro(fx["prop"]["y"], fx["prop"]["eligible"], SELFTEST_SEED + 100 + i,
                       st_c3, "GIN", "M1b")) for i in range(12)]
    c3_check = {"mean_level_C0": float(np.mean([a0 for a0, _ in lv])),
                "mean_level_C3": float(np.mean([a1 for _, a1 in lv])),
                "realized_drop": float(np.mean([a0 - a1 for a0, a1 in lv])),
                "target_drop": C3_GIN_DROP,
                "delta_gin_invariant_assert": "strengths['GIN']['M2b'] == strengths['GIN']['M1b']"}

    # ── tie 실측 ──────────────────────────────────────────────────────────────
    P_s, _ = synth_scores(fx["prop"]["y"], SELFTEST_SEED, st_c0)
    P_f, _ = synth_scores(fx["full"]["y"], SELFTEST_SEED, st_c0)
    ties = {"reduced_M1b_rep0": tie_rate(P_s["M1b"][0]), "full_M1b_rep0": tie_rate(P_f["M1b"][0])}

    # ── AE-2 시드 · 교집합 0 ─────────────────────────────────────────────────
    conf = confirmatory_seed_space()
    all_rep_seeds = []
    for c in cells_spec():
        all_rep_seeds += [rep_seed_of(c["scenario"], c["variant"], c["grid_index"], r)
                          for r in range(c["R"])]
    inter = sorted(set(all_rep_seeds) & conf)
    coin_seeds = [s + COIN_SEED_OFFSET for s in all_rep_seeds]
    assert not inter, f"★중단★ 확증 시드 공간과 교집합 {inter}"
    assert len(set(all_rep_seeds)) == len(all_rep_seeds), "★중단★ rep_seed 중복"
    assert not (set(coin_seeds) & conf), "★중단★ 동전 시드가 확증 시드와 충돌"

    out = {
        "_doc": "블록 AE / AE-0·AE-1·AE-2 — R1 캘리브레이션 감사 **착수 전 동결본**. "
                "기입 이후 변경 0. 예측 100% 합성 · 확증/봉인 미접근.",
        "block": "AE", "instruction": "docs/93_r1_calibration_audit_prompt_for_vscode.md",
        "frozen_at_kst": now_kst(), "stage_started_kst": t_start,
        "predictions_are_synthetic": True, "confirmatory_predictions_loaded": False,
        "confirmatory_data_accessed": False, "sealed_accessed": False,
        "unblinding_performed": False, "gin_start_still_blocked": True,
        "sap_version_unchanged": "1.1", "manifest_sha16": "756d485feb4715e9",
        "B_definition_status": "still_unspecified — 본 블록에서 확정하지 않는다(SAP 1.2 의 일).",
        "facts_snapshot_sha256": sha256_file(F_FACTS),

        # ── AE-0 ────────────────────────────────────────────────────────────
        "geff_unreachability": {
            "fact": "docs/84 §2 R1 의 '축소규모에서 G_eff/G ≈ 0.117 재현 필수'는 N=400 에서 "
                    "**수학적으로 도달 불가**하다(블록 AD 전수 탐색). cowork 도 더 넓은 족에서 "
                    "독립 전수 탐색해 동일 최적을 확인했다.",
            "target_full_scale": 0.11659384342455403,
            "min_attainable_at_N400": 0.13255128077675052,
            "gap": 0.015957437352196485,
            "bound_source": "experiments/rqint/profile_match.json AD_4_attainability "
                            "(블록 AD 산출 인용 — 재탐색 불필요)",
            "handling": [
                "1. primary = 비례축소 변형(F-PROF-P). 근거 = AD-4 프로파일 대조 6지표 중 5개"
                "(상위2군 점유율·max n²/Σn²·크기 왜도·PT별 양성 군 수·레버리지 상위5 점유)가 "
                "전규모에 더 가깝다.",
                "2. sensitivity = 비율최적 변형(F-PROF-R) — G_eff/G 하나만 목표에 더 가까운 변형. "
                "C0~C3 를 **두 변형 모두** 실행한다(검토자 조건에 최대한 가깝게 가려는 보수적 선택).",
                "3. 합격 판정은 **두 변형 모두**에 적용한다(완화 아님·강화). 한쪽이라도 미달이면 "
                "합격 처리 금지, 중단·보고 → 검토자 재자문 대상.",
                "4. 검토자 통지(도달불가 사실 + 상한 계산 + 채택 변형 + 감도분석 설계)는 "
                "**서명본 회수 편에 동봉**하는 별도 사안이며 본 블록의 범위 밖이다. "
                "본 블록은 통지 문안을 쓰지 않는다.",
            ],
            "substitution_by_runner": "금지 — 검토자 조건이므로 임의 대체하지 않는다.",
        },

        # ── AE-1 ────────────────────────────────────────────────────────────
        "scenarios": {
            "C0": {"desc": "양 family 서열효과 0, 상호작용 0", "scale": "reduced N400·K60"},
            "C1": {"desc": "서열효과 0.01 공통, 상호작용 0", "scale": "reduced N400·K60"},
            "C2": {"desc": "서열효과 0.03 공통, 상호작용 0", "scale": "reduced N400·K60"},
            "C3": {"desc": "GIN 전반 성능 −0.03(주효과 존재), 상호작용 0",
                   "scale": "reduced N400·K60"},
            "C4": {"desc": "상호작용 τ ∈ {0.01,0.02,0.03} 이식",
                   "scale": "full N1092·K370·G732 (예측만 합성)"},
        },
        "replication_plan": {
            "primary_variant": "reduced_proportional (prop)", "primary_R": R_PRIMARY,
            "sensitivity_variant": "reduced_ratio_optimal (ratio)", "sensitivity_R": R_SENS,
            "n_coin_vectors_small": NCOIN_SMALL, "n_permutation_values_small": 2 * NCOIN_SMALL,
            "C4_R": R_C4, "n_coin_vectors_full": NCOIN_FULL,
            "n_permutation_values_full": 2 * NCOIN_FULL,
            "tau_grid": list(TAU_GRID), "tau_prespecified": TAU_PRESPEC,
            "basis": "primary 2,000 = F-C03 범위 상한 · sensitivity 1,000 = 범위 하한. "
                     "하한 선택 근거는 **단가뿐**(AE-6 예산). "
                     "기각률·검정력을 보고 복제 수를 정하는 행위 금지.",
            "cells": cells_spec(),
        },
        "injection_freeze_A11": INJECTION_SPEC,
        "effect_calibration": {
            "scale_separation": "규모별 계수를 섞지 않는다 — 축소 slope 와 전규모 slope 는 다르다.",
            "reduced": cal_small, "full": cal_full,
            "chosen_effect_strengths": chosen,
            "probe_is_measurement_not_decision": True,
            "recalibration_during_main_run": "금지",
        },
        "slot_mapping_self_test": self_test,
        "c3_level_shift_check": c3_check,
        "tie_rates_measured": ties,
        "tie_policy": "jitter 0 · 난수 tie-break 0. tie 1건이라도 관측되면 값 그대로 두고 보고.",
        "decision_points_A10": {
            "points": {k: {"threshold": v,
                           "status": ("R1 공식 합격 판정 지점" if k == OFFICIAL_POINT
                                      else "보고·상신용 보조 근거(임계 신설 금지)")}
                       for k, v in POINTS.items()},
            "official_point": OFFICIAL_POINT,
            "rule": "α/7·α/4 지점에 새 합격기준을 만들지 않는다. 초과 시 상신 사항으로 기록만 한다.",
            "holm_family_size": HOLM_M,
        },
        "acceptance_criterion_F_ACC": {
            "rule": "기각률 ≤ α + 2·SE, SE = √(r̂(1−r̂)/R_sim) — **관측 r̂ 로 매번 계산**",
            "C0_extra": "p 균등성 KS p > 0.05",
            "applies_to": "C0~C3 의 primary·sensitivity 두 변형 모두",
            "C4_note": "C4 는 1종오류 시나리오가 아니므로 합격기준 미적용 — 산출은 검정력 곡선.",
            "reference_only_thresholds_at_rhat_0.05": {
                "primary_R2000": ALPHA + 2 * math.sqrt(0.05 * 0.95 / R_PRIMARY),
                "sensitivity_R1000": ALPHA + 2 * math.sqrt(0.05 * 0.95 / R_SENS),
                "warning": "상수로 박지 말 것 — 관측 r̂ 로 매번 계산한다.",
            },
        },
        "A12_adaptive_stopping": {
            "applies_to": "C4", "interim_at": A12_INTERIM, "max_R": R_C4,
            "interval": "Wilson score 95% CI (이항 비율)",
            "rule": "200 복제 시점 CI 가 0.50·0.80 경계를 가로지르지 않으면 해당 τ 중단, "
                    "가로지르면 400 까지 진행. 400 에서도 가로지르면 D19 사다리의 낮은 지위 채택.",
            "tau_002_low_power_prefrozen_handling":
                "τ=0.02 검정력 <0.50 이면 **사전등록 D19 사다리 최하단 지위를 그대로 채택하고 정직 보고**. "
                "τ 격자 확대·복제 증가·SESOI 조정·판정규칙 변경 전부 금지.",
        },
        "complement_audit_policy": {
            "draws": AUDIT_DRAWS, "frequency": "시나리오·변형당 **정확히 1회**(복제 반복 0)",
            "which_replicate": "각 셀의 r=0 복제(결정적 선택)",
            "basis": "블록 AC 가 1,000 draw 전건 편차 0.0 으로 항등식을 이미 실증",
        },

        # ── AE-2 ────────────────────────────────────────────────────────────
        "seed_regime": {
            "rule": SEED_RULE_TEXT, "base": BASE_SEED,
            "scenario_index": SCEN_INDEX, "variant_offset": VARIANT_OFFSET,
            "coin_seed_offset": COIN_SEED_OFFSET,
            "probe_seed_small": PROBE_SEED_SMALL, "probe_seed_full": PROBE_SEED_FULL,
            "selftest_seed": SELFTEST_SEED,
            "n_rep_seeds_total": len(all_rep_seeds),
            "rep_seed_min": int(min(all_rep_seeds)), "rep_seed_max": int(max(all_rep_seeds)),
            "confirmatory_seed_space": sorted(conf),
            "intersection_with_confirmatory": inter,
            "intersection_is_empty": True,
            "new_draws": 0, "redraws": 0,
        },
        "determinism_policy": {
            "requirement": "워커 수와 무관하게 결과가 같아야 한다. 다르면 중단.",
            "evidence": "시나리오·변형마다 첫 3복제의 T* 수열 sha256 기록 + 세션 재개 시 "
                        "동일 시드 바이트 동일 재현 1회 확인.",
        },

        # ── AE-6 ────────────────────────────────────────────────────────────
        "budget_recomputation": budget_recompute(),
        "ops": {"W_BEST": W_BEST, "threads_per_worker": max(1, (os.cpu_count() or 18) // W_BEST),
                "ram_budget_gib": RAM_BUDGET_GIB, "ram_gate_gib": RAM_GATE_GIB,
                "ram_sampler_period_s": 10.0,
                "power": "AC 연결 · 저전력 해제 · caffeinate -dimsu. "
                         "배터리·저전력 구간 측정치는 예산·처리량 표에 투입 금지.",
                "throughput_definition": "w / wall_max (평균 기반 금지)"},
        "out_of_scope": ["SAP 1.2 재동결", "B 확정", "MODULE_FILES·sap/__init__.py 갱신",
                         "manifest model_family erratum", "축소 fixture 규칙 동결",
                         "검토자 통지 문안", "R1 실패 폴백(후보 C 회귀)", "GIN 학습", "개봉"],
    }
    dump(F_DESIGN, out)
    sha = sha256_file(F_DESIGN)
    # 자기참조 없이 sha256 을 별도 사이드카에 기록(design.json 은 이후 0바이트 불변)
    dump(os.path.join(OUT_DIR, "calibration_design.sha256.json"),
         {"file": "calibration_design.json", "sha256": sha, "sha16": sha[:16],
          "frozen_at_kst": out["frozen_at_kst"],
          "note": "이 시각 이후 첫 본런 시뮬레이션이 시작된다(기입 시각 < 첫 시뮬레이션 시각)."})
    session_log({"event": "design_frozen", "when_kst": out["frozen_at_kst"],
                 "design_sha256": sha})
    print("design frozen:", out["frozen_at_kst"], "sha256:", sha)
    print("slope small =", s_small, "ratio vs AD-5 =", cal_small["ratio_vs_reference"])
    print("slope full  =", s_full, "ratio vs AD-4-4 =", cal_full["ratio_vs_reference"])
    print("self-test:", self_test["pass"], "mean_T =", self_test["mean_T"])
    print("budget within 5% =", out["budget_recomputation"]["within_5pct"],
          "total_h =", out["budget_recomputation"]["total_wall_hours"])


# ══════════════════════════════════════════════════════════════════════════════
# STAGE: run — 본런 (세션 분할 · 체크포인트 · 라이브 RAM 게이트)
# ══════════════════════════════════════════════════════════════════════════════
def cell_by_id(cid):
    for c in cells_spec():
        if c["cell"] == cid:
            return c
    raise SystemExit(f"중단: 알 수 없는 셀 {cid} (가능: {[c['cell'] for c in cells_spec()]})")


def require_ac_power():
    env = env_snapshot()
    if not env["on_ac_power"]:
        raise SystemExit(
            "★중단★ AE-6 전원 규정 위반 — AC 전원이 연결돼 있지 않다.\n"
            f"  pmset: {env['pmset_ps']}\n"
            "  배터리·저전력 구간 측정치는 예산·처리량 표에 투입 금지(중단 조건).\n"
            "  전원 연결 후 재실행하라.")
    return env


def stage_run(a):
    design = load_json(F_DESIGN)
    design_sha = sha256_file(F_DESIGN)
    side = load_json(os.path.join(OUT_DIR, "calibration_design.sha256.json"))
    if design_sha != side["sha256"]:
        raise SystemExit("★중단★ calibration_design.json 이 동결 이후 변경됐다(sha256 불일치)")
    env = require_ac_power() if not a.allow_battery else env_snapshot()

    c = cell_by_id(a.cell)
    d = load_design_arrays()
    fx = build_fixtures(d)
    if fx["row_idx_sha256"][:16] != FACTS_EXPECT["F-ROWIDX"] or \
       fx["pt_cols_sha256"][:16] != FACTS_EXPECT["F-PTCOL"]:
        raise SystemExit("★중단★ 축소 fixture 정체 분기 — row_idx/pt_cols sha16 불일치")

    key = "full" if c["scale"] == "full" else c["variant"]
    F = fx[key]
    if c["variant"] == "ratio":
        pr = F["profile"]
        assert pr["G"] == 210 and int(pr["sum_sq"]) == 5748 \
            and abs(pr["G_eff_over_G"] - 0.13255) < 5e-4, "★중단★ sensitivity 변형 3지표 재현 실패"

    ch = design["effect_calibration"]["chosen_effect_strengths"]
    if c["scenario"] == "C4":
        st = strengths_for("C4", 0.0, tau_logit=ch["C4"]["tau_logit"][str(c["tau"])])
    else:
        st = strengths_for(c["scenario"], ch[c["scenario"]]["effect_logit"])

    done = ckpt_load(a.cell)
    done_seeds = {r["rep_seed"] for r in done}
    todo = []
    for r in range(c["R"]):
        rs = rep_seed_of(c["scenario"], c["variant"], c["grid_index"], r)
        if rs in done_seeds:
            continue
        todo.append((rs, AUDIT_DRAWS if r == 0 else 0))
    if a.limit:
        todo = todo[:a.limit]

    workers = a.workers or W_BEST
    threads = max(1, (os.cpu_count() or 18) // workers)
    sess = {"event": "session_start", "cell": a.cell, "when_kst": now_kst(),
            "n_done_before": len(done), "n_todo": len(todo), "workers": workers,
            "threads_per_worker": threads, "on_ac_power": env["on_ac_power"],
            "pmset_ps": env["pmset_ps"], "powermode": env["pmset_powermode"],
            "loadavg": env["loadavg_1_5_15"], "design_sha256": design_sha}
    session_log(sess)
    print(f"[{a.cell}] done={len(done)} todo={len(todo)} workers={workers} threads={threads}")
    if not todo:
        print("이미 완주 — 할 일 없음")
        return

    ctx = mp.get_context("spawn")
    saved = {v: os.environ.get(v) for v in _THREAD_VARS}
    for v in _THREAD_VARS:
        os.environ[v] = str(threads)
    t0 = time.time()
    sampler = RamSampler()
    sampler.start()
    n_new, stopped = 0, None
    buf = []
    try:
        with ctx.Pool(processes=workers, initializer=_init_worker,
                      initargs=(F["y"], F["groups"], F["eligible"], st, c["n_coin"],
                                threads, t0)) as pool:
            for row in pool.imap_unordered(_work, todo, chunksize=1):
                buf.append(row)
                n_new += 1
                if len(buf) >= CKPT_FLUSH:
                    ckpt_append(a.cell, buf)
                    buf = []
                if n_new % 25 == 0:
                    el = time.time() - t0
                    print(f"  {n_new}/{len(todo)}  {el/60:.1f} min  "
                          f"({n_new/el*3600:.0f} rep/h)", flush=True)
                if sampler.breaches:
                    stopped = "ram_gate"
                    pool.terminate()
                    break
                if a.max_seconds and (time.time() - t0) > a.max_seconds:
                    stopped = "max_seconds"
                    pool.terminate()
                    break
    finally:
        if buf:
            ckpt_append(a.cell, buf)
        sampler.stop()
        sampler.join(timeout=3)
        for v, val in saved.items():
            if val is None:
                os.environ.pop(v, None)
            else:
                os.environ[v] = val
    wall = time.time() - t0
    session_log({"event": "session_end", "cell": a.cell, "when_kst": now_kst(),
                 "n_completed_this_session": n_new, "wall_seconds": wall,
                 "throughput_rep_per_hour": (n_new / wall * 3600) if wall > 0 else None,
                 "stopped_reason": stopped, "workers": workers,
                 "ram_peak_gib": float(max(sampler.samples)) if sampler.samples else None,
                 "ram_gate_breaches": sampler.breaches,
                 "on_ac_power": env["on_ac_power"]})
    print(f"[{a.cell}] +{n_new} in {wall/3600:.2f} h  stop={stopped}  "
          f"ram_peak={max(sampler.samples) if sampler.samples else None:.2f} GiB")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE: determinism — AE-2 워커 수 무관 결정성 + 바이트 동일 재현
#   ★ 체크포인트에 쓰지 않는다(본런 오염 0). 본런이 같은 시드를 계산하면 바이트 동일해야 한다.
#   ★ 벽시계는 결정성 판정과 무관하며 **예산·처리량 표에 투입하지 않는다**.
# ══════════════════════════════════════════════════════════════════════════════
def _run_reps(F, st, n_coin, seeds, workers):
    threads = max(1, (os.cpu_count() or 18) // workers)
    ctx = mp.get_context("spawn")
    saved = {v: os.environ.get(v) for v in _THREAD_VARS}
    for v in _THREAD_VARS:
        os.environ[v] = str(threads)
    t0 = time.time()
    try:
        with ctx.Pool(processes=workers, initializer=_init_worker,
                      initargs=(F["y"], F["groups"], F["eligible"], st, n_coin, threads, t0)) as p:
            rows = p.map(_work, [(s, 0) for s in seeds])
    finally:
        for v, val in saved.items():
            if val is None:
                os.environ.pop(v, None)
            else:
                os.environ[v] = val
    return sorted(rows, key=lambda r: r["rep_seed"]), time.time() - t0


def stage_determinism(a):
    design = load_json(F_DESIGN)
    d = load_design_arrays()
    fx = build_fixtures(d)
    cid = a.cell or "C0:prop"
    c = cell_by_id(cid)
    key = "full" if c["scale"] == "full" else c["variant"]
    F = fx[key]
    ch = design["effect_calibration"]["chosen_effect_strengths"]
    st = (strengths_for("C4", 0.0, tau_logit=ch["C4"]["tau_logit"][str(c["tau"])])
          if c["scenario"] == "C4" else
          strengths_for(c["scenario"], ch[c["scenario"]]["effect_logit"]))
    seeds = [rep_seed_of(c["scenario"], c["variant"], c["grid_index"], r) for r in range(3)]
    runs = {}
    for tag, w in (("A_w3", 3), ("B_w1", 1), ("C_w3_repeat", 3)):
        rows, wall = _run_reps(F, st, c["n_coin"], seeds, w)
        runs[tag] = {"workers": w, "wall_seconds": wall,
                     "rep_seeds": [r["rep_seed"] for r in rows],
                     "t_star_sha256": [r["t_star_sha256"] for r in rows],
                     "p_two_sided": [r["p_two_sided"] for r in rows],
                     "T_obs": [r["T_obs"] for r in rows]}
        print(f"  {tag} w={w} wall={wall:.1f}s sha={[s[:12] for s in runs[tag]['t_star_sha256']]}")
    ref = runs["A_w3"]
    same_hash = all(runs[t]["t_star_sha256"] == ref["t_star_sha256"] for t in runs)
    same_p = all(runs[t]["p_two_sided"] == ref["p_two_sided"] for t in runs)
    out = {
        "_doc": "블록 AE / AE-2 — 결정성 검증. 워커 수 무관 + 바이트 동일 재현. "
                "★ 체크포인트 미기록(본런 오염 0) · 벽시계는 예산·처리량 표에 투입 금지.",
        "block": "AE", "when_kst": now_kst(), "cell": cid,
        "predictions_are_synthetic": True, "confirmatory_predictions_loaded": False,
        "design_sha256": sha256_file(F_DESIGN),
        "runs": runs,
        "worker_count_invariant": bool(same_hash and same_p),
        "byte_identical_reproduction": bool(
            runs["C_w3_repeat"]["t_star_sha256"] == runs["A_w3"]["t_star_sha256"]),
        "first3_t_star_sha256": ref["t_star_sha256"],
        "env": env_snapshot(),
        "wall_clock_excluded_from_budget": True,
        "wall_clock_exclusion_reason": "결정성 확인 전용 실행 · 전원 상태 무관하게 바이트 동일성만 판정",
    }
    dump(os.path.join(OUT_DIR, f"calibration_determinism_{cid.replace(':', '_')}.json"), out)
    print("worker_count_invariant =", out["worker_count_invariant"],
          "| byte_identical_reproduction =", out["byte_identical_reproduction"])
    if not (out["worker_count_invariant"] and out["byte_identical_reproduction"]):
        raise SystemExit("★중단★ 병렬 결정성 위반")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE: summary
# ══════════════════════════════════════════════════════════════════════════════
def stage_summary(a):
    design = load_json(F_DESIGN)
    cells, per_cell = cells_spec(), {}
    for c in cells:
        rows = sorted(ckpt_load(c["cell"]), key=lambda r: r["rep_seed"])
        if not rows:
            per_cell[c["cell"]] = {**c, "status": "not_run", "n_done": 0}
            continue
        p = [r["p_two_sided"] for r in rows]
        rec = {**c, "status": "complete" if len(rows) >= c["R"] else "partial",
               "n_done": len(rows),
               "p_values_raw": p,
               "rep_seeds": [r["rep_seed"] for r in rows],
               "first3_t_star_sha256": [r["t_star_sha256"] for r in rows[:3]],
               "rates": rate_table(p),
               "mean_p": float(np.mean(p)),
               "mean_delta_rf": float(np.mean([r["delta_rf"] for r in rows])),
               "mean_delta_gin": float(np.mean([r["delta_gin"] for r in rows])),
               "mean_abs_gap": float(np.mean([r["abs_gap"] for r in rows])),
               "tie_rate_observed": next((r.get("score_tie_rate_m1b_rf") for r in rows
                                          if "score_tie_rate_m1b_rf" in r), None),
               "complement_audit": next((r.get("complement_audit") for r in rows
                                         if "complement_audit" in r), None),
               }
        if c["scenario"] == "C0":
            rec["ks_uniform"] = ks_uniform(p)
        if c["scenario"] == "C4":
            k200 = int(np.sum(np.asarray(p[:A12_INTERIM]) <= ALPHA)) if len(p) >= A12_INTERIM else None
            rec["A12"] = {
                "interim_at": A12_INTERIM,
                "interim_power": (k200 / A12_INTERIM) if k200 is not None else None,
                "interim_wilson95": wilson_ci(k200, A12_INTERIM) if k200 is not None else None,
                "final_power": float(np.mean(np.asarray(p) <= ALPHA)),
                "final_wilson95": wilson_ci(int(np.sum(np.asarray(p) <= ALPHA)), len(p)),
            }
            if rec["A12"]["interim_wilson95"]:
                lo, hi = rec["A12"]["interim_wilson95"]
                crosses = (lo < 0.50 < hi) or (lo < 0.80 < hi)
                rec["A12"]["crosses_boundary_at_interim"] = bool(crosses)
                rec["A12"]["stop_at_interim"] = bool(not crosses)
        per_cell[c["cell"]] = rec

    # 합격 판정 — C0~C3 두 변형 모두
    judge_cells = [c["cell"] for c in cells if c["scenario"] != "C4"]
    detail, statuses = {}, []
    for cid in judge_cells:
        r = per_cell[cid]
        if r["status"] != "complete":
            detail[cid] = {"verdict": "incomplete", "n_done": r["n_done"]}
            statuses.append("incomplete")
            continue
        pt = r["rates"][OFFICIAL_POINT]
        ok = pt["rejection_rate"] <= pt["acceptance_bound_alpha_plus_2SE"]
        ks_ok = True
        if "ks_uniform" in r:
            ks_ok = r["ks_uniform"]["p_value"] > 0.05
        detail[cid] = {"verdict": "pass" if (ok and ks_ok) else "fail",
                       "rejection_rate": pt["rejection_rate"],
                       "bound": pt["acceptance_bound_alpha_plus_2SE"],
                       "rate_ok": bool(ok), "ks_ok": bool(ks_ok),
                       "ks_p": r.get("ks_uniform", {}).get("p_value")}
        statuses.append(detail[cid]["verdict"])

    if "incomplete" in statuses:
        r1 = "incomplete"
    elif all(s == "pass" for s in statuses):
        r1 = True
    elif all(s == "fail" for s in statuses):
        r1 = False
    else:
        prim = [detail[c]["verdict"] for c in judge_cells if c.endswith(":prop")]
        sens = [detail[c]["verdict"] for c in judge_cells if c.endswith(":ratio")]
        r1 = "split" if (set(prim) != set(sens)) else False

    aux_exceed = {cid: {k: per_cell[cid]["rates"][k]["rejection_rate"]
                        for k in ("alpha_over_7", "alpha_over_4")
                        if per_cell[cid]["rates"][k]["rejection_rate"]
                        > POINTS[k] + 2 * per_cell[cid]["rates"][k]["SE_rhat"]}
                  for cid in judge_cells if per_cell[cid]["status"] == "complete"}
    aux_exceed = {k: v for k, v in aux_exceed.items() if v}

    out = {
        "_doc": "블록 AE / R1 캘리브레이션 감사 요약 — 3지점 기각률표 · 검정력 곡선 · 합격 판정. "
                "예측 100% 합성 · 확증/봉인 미접근.",
        "block": "AE", "when_kst": now_kst(),
        "predictions_are_synthetic": True, "confirmatory_predictions_loaded": False,
        "confirmatory_data_accessed": False, "sealed_accessed": False,
        "unblinding_performed": False, "gin_start_still_blocked": True,
        "sap_version_unchanged": "1.1", "manifest_sha16": "756d485feb4715e9",
        "design_sha256": sha256_file(F_DESIGN),
        "design_frozen_at_kst": design["frozen_at_kst"],
        "cells": per_cell,
        "acceptance_detail": detail,
        "r1_passed": r1,
        "official_decision_point": OFFICIAL_POINT,
        "auxiliary_points_exceeding": aux_exceed,
        "auxiliary_points_note": "α/7·α/4 는 보고·상신용 보조 근거일 뿐 합격 판정을 뒤집지 않는다. "
                                 "임계 신설 0.",
        "on_fail_policy": "불합격·엇갈림 시 러너의 자체 구제 금지 — 후보 C 회귀·폴백·재실행 0, "
                          "즉시 중단·보고(승인 무효 → 검토자 재자문 의무).",
        "fallback_applied": False, "reruns_after_fail": 0, "seed_changes_after_fail": 0,
    }
    dump(F_SUMMARY, out)
    for cid in [c["cell"] for c in cells]:
        r = per_cell[cid]
        if r["status"] == "not_run":
            print(f"{cid:16s} not_run")
            continue
        pt = r["rates"][OFFICIAL_POINT]
        print(f"{cid:16s} n={r['n_done']:5d} r̂={pt['rejection_rate']:.4f} "
              f"bound={pt['acceptance_bound_alpha_plus_2SE']:.5f} "
              f"{detail.get(cid, {}).get('verdict', '-')}")
    print("r1_passed =", r1)


# ══════════════════════════════════════════════════════════════════════════════
STAGES = {"facts": stage_facts, "design": stage_design, "determinism": stage_determinism,
          "run": stage_run, "summary": stage_summary}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    ap.add_argument("--cell", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--max-seconds", type=float, default=None, dest="max_seconds")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-battery", action="store_true", dest="allow_battery",
                    help="AE-6 전원 규정 우회(측정치는 예산·처리량 표 투입 금지 — 결정성 확인 전용)")
    a = ap.parse_args()
    if a.stage == "run" and not a.cell:
        raise SystemExit("--stage run 은 --cell 이 필요하다")
    STAGES[a.stage](a)


if __name__ == "__main__":
    main()
