#!/usr/bin/env python3
"""pid_stratification_run.py — 블록 L: §13-6 커버리지 C2 `Δ(M2b−P-ID)` 층화.

성격
----
블록 H(`stratification_run.py`)의 층 배정·집계 경로를 **import 재사용**하고 arm 만
`(P-ID, M2b)` 로 바꾼다. `stratification_run.py` 는 **한 줄도 수정하지 않는다**.

  · 모델학습 0 · 새 OOF 생성 0 — consensus 는 기존 산출(블록 C · 블록 I)을 그대로 읽는다.
  · 층 배정·구조축 경계·identity 도 전부 기존 산출 그대로(재계산 0).
  · 산출은 **전량 `_sealed/`**. 공개는 표본수·라벨·B·seed·시간·해시·게이트 PASS/FAIL 뿐이며
    **Δ 의 부호조차 공개하지 않는다**(Holm family ② = 부호 노출도 조각 개봉).
  · 개봉(`open_sealed`) 0 · 성공판정(`decision.py`) 0 · 다중성 보정 0.

스테이지
  verify     L-1 게이트 + L-2 정합 하드 assert  → gates_public.json
  signcheck  부호 방향 **합성 데이터** 검증 1회 → signcheck_public.json (확증값 미사용)
  pilot      L-3 계측(B=100) → 13층 × B=10000 총 wall 추정 → pilot_timing.json
  estimate   L-4 본계산 → _sealed/stratification_pid_result.json + 공개 요약
  all        위 4개를 순서대로

실행: .venv/bin/python3 v3_Multimodal/src/pid_stratification_run.py --stage all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

for _k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_k, "1")

import numpy as np                                                      # noqa: E402
import pandas as pd                                                     # noqa: E402

from compute_lock import ComputeLock, gate_a_load, gate_b_exclusive     # noqa: E402
import stratification_run as H                                          # noqa: E402  (블록 H — 무수정 재사용)
from sap import bootstrap as sap_bootstrap                              # noqa: E402
from sap import metrics as sap_metrics                                  # noqa: E402
from sap import redaction as sap_redaction                              # noqa: E402
from sap import signflip as sap_signflip                                # noqa: E402

KST = timezone(timedelta(hours=9))

# ═══════════════════════════════════════════════════════════════════════════
# 동결 상수 — **전부 블록 H 에서 그대로 가져온다**(새 값·새 seed 를 뽑지 않는다, L-0-2)
# ═══════════════════════════════════════════════════════════════════════════
SEED_BOOTSTRAP = H.SEED_BOOTSTRAP        # 6001
SEED_SIGNFLIP = H.SEED_SIGNFLIP          # 6002
B_MAIN = H.B_MAIN                        # 10000
B_PILOT = H.B_PILOT                      # 100
BOOT_UNIT = H.BOOT_UNIT                  # "scaffold_cluster"
ELIGIBLE_PT = H.ELIGIBLE_PT              # None — 370 PT 전열

EXPECT_N_DRUGS = H.EXPECT_N_DRUGS
EXPECT_N_PT = H.EXPECT_N_PT
EXPECT_DENOM = H.EXPECT_DENOM
EXPECT_N_NO_TARGET = H.EXPECT_N_NO_TARGET
EXPECT_N_SCAFFOLD_GROUPS = H.EXPECT_N_SCAFFOLD_GROUPS
EXPECT_LADDER_FREEZE_SHA16 = H.EXPECT_LADDER_FREEZE_SHA16
EXPECT_SAP_MANIFEST_SHA16 = H.EXPECT_SAP_MANIFEST_SHA16
WALL_ABORT_DAYS = H.WALL_ABORT_DAYS      # 7.0

EXPECT_N_UNITS = 13                      # L-2-6 — 축 3종 + 축별 unstable
EXPECT_GUARD_N_FILES = 157               # 블록 K 기준(`experiments/runs/**/_sealed/`, access.log 제외)

# L-1-3 입력 지문(지시서 명시분) — 값은 열지 않고 sha256 만 대조
EXPECT_SHA = {
    "experiments/runs/v3_consensus_rep123/_sealed/consensus_M2b.npz":
        "8594592e2afae5835f43be63d6bdc815a6933d25388b9c3c4091637117c435bf",
    "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_P-ID.npz":
        "9598da3498b1d3cecb1119950e58e43a5f9a7be9981740f0f315de85f56b1f0c",
    "experiments/runs/v3_stratification/strata_assignment.csv":
        "8247f4318150414bbdbcd05d577287e771a539447cf57e78e1b1df5dd319250c",
}

# 축 위상 라벨 (블록 K `strata_accounting_public.json` `axes[*].role` — 라벨만, 해석 없음)
AXIS_ROLE = {"struct_bin": "confirmatory", "seq_stratum": "confirmatory",
             "drug_class": "data_characteristic"}

# ═══════════════════════════════════════════════════════════════════════════
# 경로
# ═══════════════════════════════════════════════════════════════════════════
RUNS = os.path.join(ROOT, "experiments", "runs")
RUN_DIR = os.path.join(RUNS, "v3_stratification_pid")          # 신규 디렉터리
SEALED_DIR = os.path.join(RUN_DIR, "_sealed")
RUN_LOG = os.path.join(RUN_DIR, "run.log")
F_GATES = os.path.join(RUN_DIR, "gates_public.json")
F_SIGNCHECK = os.path.join(RUN_DIR, "signcheck_public.json")
F_PILOT = os.path.join(RUN_DIR, "pilot_timing.json")
F_PUBLIC = os.path.join(RUN_DIR, "stratification_pid_public.json")
F_CKPT = os.path.join(SEALED_DIR, "checkpoint.jsonl")
F_ENVFP = os.path.join(RUN_DIR, "env_fingerprint.json")

CONS_M2B_DIR = os.path.join(RUNS, "v3_consensus_rep123", "_sealed")
CONS_PID_DIR = os.path.join(RUNS, "v3_confirm_rest_consensus_rep123", "_sealed")
F_CONS_M2B = os.path.join(CONS_M2B_DIR, "consensus_M2b.npz")
F_CONS_PID = os.path.join(CONS_PID_DIR, "consensus_P-ID.npz")

F_STRATA = H.F_STRATA                    # 블록 H 층 배정(읽기 전용)
F_STRATA_SUM = H.F_STRATA_SUM
F_BOUNDS = H.F_BOUNDS
F_MASTER_Y = H.F_MASTER_Y
F_ACCT_PUB = os.path.join(RUNS, "v3_stratification", "strata_accounting_public.json")
F_REST_PUB = os.path.join(RUNS, "v3_confirm_rest", "rest_public.json")
F_BLOCKC_SUM = os.path.join(RUNS, "v3_confirm_rep23", "block_C_summary.json")
SPLIT_DIRS = {1: os.path.join(ROOT, "data", "processed", "splits", "confirmatory", "rep1_seed201"),
              2: os.path.join(ROOT, "data", "processed", "splits", "confirmatory", "rep2_seed202"),
              3: os.path.join(ROOT, "data", "processed", "splits", "confirmatory", "rep3_seed203")}


# ═══════════════════════════════════════════════════════════════════════════
# 유틸 — 공개 로그에 AP·Δ·CI·p·부호를 절대 쓰지 않는다
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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def dump_json(path, obj):
    return H.dump_json(path, obj)


def guard_snapshot():
    """`experiments/runs/**/_sealed/**` 전 트리 sha256 지문(하위 디렉터리 포함) — 본 블록
    신규 디렉터리와 `access.log`(machine_read append 로 변함)는 제외. 시작=종료 대조용."""
    snap = {}
    own = os.path.abspath(SEALED_DIR) + os.sep
    for dirpath, _dirnames, filenames in os.walk(RUNS):
        if "_sealed" not in os.path.relpath(dirpath, RUNS).split(os.sep):
            continue                                     # _sealed 하위 트리만
        if (os.path.abspath(dirpath) + os.sep).startswith(own):
            continue                                     # 본 블록 신규 산출은 guard 대상 아님
        for fn in sorted(filenames):
            if fn == "access.log":
                continue
            p = os.path.join(dirpath, fn)
            if os.path.isfile(p):
                snap[os.path.relpath(p, ROOT)] = sha256_file(p)
    return dict(sorted(snap.items()))


def log_machine_read(access_dir, path_rel, purpose):
    """sealed 파일 **기계 판독**(사람 노출 0) — `open_sealed`(사람 열람)와 구분."""
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": "§13-6 커버리지 C2 — Δ(M2b−P-ID) 층화(블록 L)",
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    for d in (access_dir, SEALED_DIR):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "access.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def count_open_sealed():
    n = 0
    for dirpath, _dn, fns in os.walk(RUNS):
        if "access.log" not in fns:
            continue
        with open(os.path.join(dirpath, "access.log"), encoding="utf-8") as f:
            n += sum(1 for ln in f if "OPEN sealed" in ln)
    return n


# ═══════════════════════════════════════════════════════════════════════════
# stage: verify — L-1 게이트 + L-2 정합 하드 assert
# ═══════════════════════════════════════════════════════════════════════════
def load_consensus_pair(d):
    """(P-ID, M2b) consensus 를 **기계 판독**으로 로드. cid 배열도 함께 반환."""
    log_machine_read(CONS_M2B_DIR, os.path.relpath(F_CONS_M2B, ROOT),
                     "§13-6 C2 층화 입력(consensus M2b, 블록 C 산출) — 기계 판독")
    log_machine_read(CONS_PID_DIR, os.path.relpath(F_CONS_PID, ROOT),
                     "§13-6 C2 층화 입력(consensus P-ID, 블록 I 산출) — 기계 판독")
    out = {}
    for key, path in (("M2b", F_CONS_M2B), ("P-ID", F_CONS_PID)):
        with np.load(path) as z:
            out[key] = z["consensus"]
            out[key + "_cid"] = z["cid"].astype(int)
    return out


CID_ARG_RE = re.compile(r"cid=np\.array\(\[int\(c\) for c in d\[\"cid_order\"\]\]\)")
CID_ORDER_RE = re.compile(r"cid_order = X\[\"cid\"\]\.astype\(int\)\.tolist\(\)")
XY_ALIGN_RE = re.compile(r"assert list\(X\[\"cid\"\]\) == list\(Y\[\"cid\"\]\)")
IMPORT_RE = re.compile(r"from ladder_confirmatory import \([^\n]*\n\s*load_frozen,")
CALL_RE = re.compile(r"d = load_frozen\(\)")


def _same_load_frozen():
    """두 러너가 참조하는 `load_frozen` 이 **같은 함수 객체**인지 런타임 확인(가장 강한 증명)."""
    import importlib
    c = importlib.import_module("confirmatory_oof_rep23")
    i = importlib.import_module("confirmatory_oof_rest")
    lc = importlib.import_module("ladder_confirmatory")
    same = (c.load_frozen is i.load_frozen is lc.load_frozen)
    assert same, "두 러너의 load_frozen 이 서로 다른 함수 객체다"
    return {"block_C_module": c.__name__, "block_I_module": i.__name__,
            "shared_function": f"{lc.__name__}.load_frozen",
            "identical_function_object": bool(same)}


def _cid_rules(path):
    """consensus 의 cid 축을 만든 코드 규칙을 **소스에서 직접 발췌**(L-2-2 코드 증명).

    두 러너(블록 C `confirmatory_oof_rep23.py` · 블록 I `confirmatory_oof_rest.py`)는
    **같은 동결 함수** `ladder_confirmatory.load_frozen()` 을 import 해 호출하며, 그 함수가
    ① master_X/Y 정렬 일치를 assert 하고 ② `cid_order` 를 master_X 의 cid 열(파일 순서)로
    정의한다. 두 러너는 ③ 그 `cid_order` 를 그대로 consensus npz 에 저장한다.
    """
    src = open(path, encoding="utf-8").read()
    rules = {}
    for name, rx in (("imports_shared_load_frozen", IMPORT_RE),
                     ("calls_load_frozen", CALL_RE),
                     ("consensus_cid_storage", CID_ARG_RE)):
        hits = rx.findall(src)
        assert len(hits) >= 1, f"{os.path.basename(path)} 에서 `{name}` 규칙을 특정하지 못함"
        rules[name] = re.sub(r"\s+", " ", hits[0]).strip()
    return rules


def _shared_cid_order_rules():
    """공유 동결 로더 `ladder_confirmatory.load_frozen()` 의 cid 축 정의를 발췌."""
    p = os.path.join(HERE, "ladder_confirmatory.py")
    src = open(p, encoding="utf-8").read()
    out = {}
    for name, rx in (("xy_alignment_assert", XY_ALIGN_RE),
                     ("cid_order_definition", CID_ORDER_RE)):
        hits = rx.findall(src)
        assert len(hits) >= 1, f"ladder_confirmatory.py 에서 `{name}` 규칙을 특정하지 못함"
        out[name] = hits[0]
    out["source_file"] = "v3_Multimodal/src/ladder_confirmatory.py"
    out["source_sha256"] = sha256_file(p)
    return out


def row_order_proof(cons, d):
    """L-2-2 — 두 consensus 의 행(약물) 순서 동일성 증명."""
    cid_m2b, cid_pid = cons["M2b_cid"], cons["P-ID_cid"]
    assert cid_m2b.shape == (EXPECT_N_DRUGS,) and cid_pid.shape == (EXPECT_N_DRUGS,)
    elementwise = bool(np.array_equal(cid_m2b, cid_pid))
    assert elementwise, "두 consensus 의 cid 배열이 원소 단위로 다르다 — 행 정렬 불일치"
    master_match = bool(np.array_equal(cid_m2b, np.array(d["cid_order"], dtype=int)))
    assert master_match, "consensus cid 가 master_X 정렬과 다르다"
    assert len(set(cid_m2b.tolist())) == EXPECT_N_DRUGS, "cid 중복"

    # 코드경로 증명 — 두 러너(블록 C·블록 I)가 **같은 동결 로더**로 cid 축을 만든다.
    r_c = _cid_rules(os.path.join(HERE, "confirmatory_oof_rep23.py"))
    r_i = _cid_rules(os.path.join(HERE, "confirmatory_oof_rest.py"))
    code_identical = (r_c == r_i)
    assert code_identical, f"cid 코드경로 불일치:\n  C: {r_c}\n  I: {r_i}"
    shared = _shared_cid_order_rules()
    shared["runtime_identity"] = _same_load_frozen()

    # master_X.parquet 지문이 두 런의 provenance 에서 동일한지
    mx_live = sha256_file(os.path.join(ROOT, "data", "processed", "master_X.parquet"))
    mx_rest = json.load(open(F_REST_PUB, encoding="utf-8"))[
        "inputs_sha256"]["sources"]["master_X.parquet"]["sha256"]
    assert mx_live == mx_rest, "master_X.parquet sha256 가 블록 I 기록과 다르다"

    return {"elementwise_cid_equal": elementwise,
            "cid_equals_master_X_order": master_match,
            "cid_unique": True,
            "cid_code_rules_identical": code_identical,
            "cid_code_rules": r_c,
            "shared_loader_rules": shared,
            "master_X_sha256": mx_live,
            "master_X_sha256_matches_block_I_record": True,
            "code_note": ("두 런은 **같은 동결 함수** `ladder_confirmatory.load_frozen()` 을 import 해 "
                          "호출한다(텍스트가 같은 별개 구현이 아니라 동일 함수). 그 함수가 "
                          "master_X.parquet 의 cid 열을 파일 순서로 읽고 master_Y 와의 정렬 일치를 "
                          "assert 한 뒤, 두 러너가 그 순서를 그대로 consensus npz 에 저장한다. 입력 "
                          "master_X.parquet 의 sha256 도 동일하므로 두 cid 축은 같을 수밖에 없으며, "
                          "실제로 원소 단위 비교로도 동일함을 확인했다. 추가로 블록 I 는 자체 검증에서 "
                          "기존 블록 C sealed npz 의 cid 배열이 master_X 정렬과 같음을 이미 assert 했다"
                          "(`confirmatory_oof_rest.py` I-2 바이트 동일성 스테이지).")}


def repeat_fold_provenance():
    """L-2-3 — 두 consensus 가 동일 반복{1,2,3}=seed{201,202,203}·5-fold·동일 folds.json 에서 산출."""
    live = {r: sha256_file(os.path.join(SPLIT_DIRS[r], "folds.json")) for r in (1, 2, 3)}
    rest = json.load(open(F_REST_PUB, encoding="utf-8"))["inputs_sha256"]["splits"]
    blockc = json.load(open(F_BLOCKC_SUM, encoding="utf-8"))
    key = {1: "rep1_seed201", 2: "rep2_seed202", 3: "rep3_seed203"}
    for r in (1, 2, 3):
        assert rest[key[r]]["folds_json_sha256"] == live[r], f"rep{r} folds.json sha 불일치(블록 I 기록)"
        assert rest[key[r]]["n_rows"] == EXPECT_N_DRUGS
        assert rest[key[r]]["fold_sizes"] == [218, 218, 219, 218, 219], f"rep{r} fold 크기 불일치"
        assert rest[key[r]]["n_scaffold_groups"] == EXPECT_N_SCAFFOLD_GROUPS
    assert blockc["code_path_equivalence"]["rep1_folds_sha256"] == live[1], \
        "블록 C 가 기록한 rep1 folds.json sha 와 불일치"
    cfg_c = {}
    for r, seed in ((1, 201), (2, 202), (3, 203)):
        p = os.path.join(RUNS, f"v3_confirm_rep{r}_seed{seed}", "config.json")
        s = json.load(open(p, encoding="utf-8"))["split"]
        assert s["seed"] == seed and s["n_fold"] == 5 and s["repeat"] == r
        assert s["dir"].endswith(key[r]), f"블록 C rep{r} split dir 불일치: {s['dir']}"
        cfg_c[f"rep{r}"] = {"seed": s["seed"], "n_fold": s["n_fold"], "dir": s["dir"]}
    assert blockc["seed_map"]["2"] == 202 and blockc["seed_map"]["3"] == 203
    return {"folds_json_sha256_live": live,
            "block_C_rep_split_config": cfg_c,
            "block_I_recorded_folds_sha_match": True,
            "block_C_rep1_folds_sha_match": True,
            "repeats": [1, 2, 3], "seeds": [201, 202, 203], "n_fold": 5,
            "fold_sizes": [218, 218, 219, 218, 219]}


def stage_verify():
    logln("[verify] L-1 게이트 + L-2 정합 하드 assert")
    checks = {}

    # ── L-1-2  G0 · sealed guard 157 · open_sealed 0
    g0 = H.gate0_verify()
    assert g0["ladder_freeze_sha16"] == EXPECT_LADDER_FREEZE_SHA16
    assert g0["sap_manifest_sha16"] == EXPECT_SAP_MANIFEST_SHA16
    guard = guard_snapshot()
    assert len(guard) == EXPECT_GUARD_N_FILES, f"sealed guard {len(guard)}종 != {EXPECT_GUARD_N_FILES}"
    n_open = count_open_sealed()
    assert n_open == 0, f"open_sealed 이력 {n_open}건 — 개봉 금지 위반"
    checks["G0"] = {k: v for k, v in g0.items() if not isinstance(v, dict)}
    checks["sealed_guard_n_files"] = len(guard)
    checks["open_sealed_events"] = n_open
    checks["seed_isolation"] = H.seed_isolation()

    # ── L-1-3  입력 지문 대조(값 미열람)
    sha_obs = {}
    for rel, exp in EXPECT_SHA.items():
        p = os.path.join(ROOT, rel)
        assert os.path.exists(p), f"입력 부재: {rel}"
        got = sha256_file(p)
        assert got == exp, f"입력 sha256 불일치 {rel}: 기대 {exp[:16]} 실측 {got[:16]}"
        sha_obs[rel] = got
    for rel in ("experiments/runs/v3_stratification/struct_bounds.json",
                "data/processed/master_Y.parquet",
                "data/processed/master_X.parquet",
                "experiments/runs/v3_stratification/strata_summary.json"):
        p = os.path.join(ROOT, rel)
        assert os.path.exists(p), f"입력 부재: {rel}"
        sha_obs[rel] = sha256_file(p)
    checks["inputs_sha256"] = sha_obs

    # ── 공통 로더(블록 H 무수정 재사용) + 층 배정 판독
    d = H.load_common()
    df = pd.read_csv(F_STRATA)
    cons = load_consensus_pair(d)

    # ── L-2-1  shape · dtype · y 정합
    for m in ("M2b", "P-ID"):
        assert cons[m].shape == (EXPECT_N_DRUGS, EXPECT_N_PT), f"{m} shape {cons[m].shape}"
    assert cons["M2b"].dtype == cons["P-ID"].dtype, \
        f"dtype 불일치 {cons['M2b'].dtype} vs {cons['P-ID'].dtype}"
    assert d["Ym"].shape == (EXPECT_N_DRUGS, EXPECT_N_PT)
    checks["shape"] = {"consensus": list(cons["M2b"].shape), "y": list(d["Ym"].shape),
                       "dtype": str(cons["M2b"].dtype), "dtype_equal": True}

    # ── L-2-2  행(약물) 순서 동일성
    checks["row_order"] = row_order_proof(cons, d)

    # ── L-2-3  동일 반복·동일 fold
    checks["repeat_fold_provenance"] = repeat_fold_provenance()

    # ── L-2-4  NaN 0 · 확률 범위(검사 결과만 기록)
    rng_ok = {}
    for m in ("M2b", "P-ID"):
        a = cons[m]
        assert not np.isnan(a).any(), f"{m} NaN 존재"
        assert not np.isinf(a).any(), f"{m} inf 존재"
        assert bool((a >= 0.0).all() and (a <= 1.0).all()), f"{m} 확률 범위 이탈"
        rng_ok[m] = {"n_nan": 0, "n_inf": 0, "within_0_1": True}
    checks["value_range"] = rng_ok

    # ── L-2-5  회계 재확인(블록 K assert 를 그대로 호출)
    checks["accounting"] = H.assert_strata_accounting(df)

    # ── L-2-6  층 정의·필터가 블록 H 와 완전 동일한지
    units = H.estimation_units(df, d)
    assert len(units) == EXPECT_N_UNITS, f"층 수 {len(units)} != {EXPECT_N_UNITS}"
    hpub = json.load(open(os.path.join(RUNS, "v3_stratification",
                                       "stratification_public.json"), encoding="utf-8"))
    h_units = {f"{u['axis']}::{u['stratum']}": u["n_drugs"] for u in hpub["units"]}
    mine = {f"{u['axis']}::{u['stratum']}": len(u["cids"]) for u in units}
    assert mine == h_units, f"블록 H 층 구성과 불일치: {set(mine.items()) ^ set(h_units.items())}"

    # 블록 K 회계 공개표와도 층별 표본수 대조(L-5 사전 확인)
    acct = json.load(open(F_ACCT_PUB, encoding="utf-8"))["axes"]
    for axis, a in acct.items():
        for st, n in a["n_drugs_by_stratum"].items():
            assert mine[f"{axis}::{st}"] == n, f"블록 K 표본수 불일치 {axis}/{st}"
        assert mine[f"{axis}::unstable_stratum"] == a["unstable_stratum"], \
            f"블록 K unstable 표본수 불일치 {axis}"
    checks["units"] = {"n_units": len(units), "matches_block_H": True,
                       "matches_block_K_accounting": True,
                       "eligible_pt": "None(370 PT 전열 · 층 내부 재선정 금지)",
                       "config_source": "stratification_run.py (무수정 import 재사용)"}
    checks["frozen_constants_from_block_H"] = {
        "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
        "unit": BOOT_UNIT, "primary_ci_method": sap_bootstrap.PRIMARY_CI_METHOD,
        "excluded_no_target": EXPECT_N_NO_TARGET, "denominator": EXPECT_DENOM}

    env = env_fingerprint(sha_obs)
    dump_json(F_ENVFP, env)
    out = {"_scope": "공개 — 게이트 PASS/FAIL·개수·해시 뿐. Δ·AP·CI·p·부호 없음.",
           "ts_kst": now_kst(), "block": "L (docs/57)", "L1_L2_checks": checks,
           "sealed_guard_start": guard, "all_pass": True}
    dump_json(F_GATES, out)
    logln(f"[verify] PASS — G0 · sealed guard {len(guard)}종 · open_sealed {n_open} · "
          f"행순서 동일 True · shape {checks['shape']['consensus']} NaN 0 · "
          f"회계 847/1092 · 층 {len(units)}개(블록 H·K 와 일치)")
    return out


def env_fingerprint(sha_obs):
    import scipy
    import sklearn
    return {"ts_kst": now_kst(),
            "python": sys.version.split()[0], "numpy": np.__version__,
            "scipy": scipy.__version__, "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
            "machine": platform.machine(), "os": platform.platform(),
            "ladder_freeze_sha16": EXPECT_LADDER_FREEZE_SHA16,
            "sap_manifest_sha16": EXPECT_SAP_MANIFEST_SHA16,
            "inputs_sha256": sha_obs}


# ═══════════════════════════════════════════════════════════════════════════
# 대비 계산 — 인자 순서 = (기준 arm = P-ID, 비교 arm = M2b)
#   두 동결 연산자 모두 Δ = macroAP(둘째 인자) − macroAP(첫째 인자) 로 정의돼 있으므로
#   Δ_PID = macro AP(M2b) − macro AP(P-ID) 가 되고, 블록 H 의 Δ(M2b−M1b) 와 동일 방향이다.
# ═══════════════════════════════════════════════════════════════════════════
def run_unit(unit, d, cons, B, seed_boot, seed_flip):
    idx = H.row_index(d, unit["cids"])
    y_s = d["Ym"][idx]
    base_s = cons["P-ID"][idx]                  # 기준 arm
    comp_s = cons["M2b"][idx]                   # 비교 arm
    sg_s = d["scaffold"][idx]

    t0 = time.perf_counter()
    ap_base = sap_metrics.macro_ap(y_s, base_s, ELIGIBLE_PT)
    ap_comp = sap_metrics.macro_ap(y_s, comp_s, ELIGIBLE_PT)
    t_ap = time.perf_counter() - t0

    t0 = time.perf_counter()
    boot = sap_bootstrap.paired_scaffold_bootstrap(
        base_s, comp_s, y_s, sg_s, eligible_pt=ELIGIBLE_PT, B=B, seed=seed_boot, unit=BOOT_UNIT)
    t_boot = time.perf_counter() - t0

    t0 = time.perf_counter()
    flip = sap_signflip.scaffold_signflip(
        base_s, comp_s, y_s, sg_s, eligible_pt=ELIGIBLE_PT, B=B, seed=seed_flip)
    t_flip = time.perf_counter() - t0

    return {"macro_ap_P-ID": ap_base, "macro_ap_M2b": ap_comp,
            "delta": float(ap_comp["macro_ap"] - ap_base["macro_ap"]),
            "delta_definition": "macro AP(M2b) − macro AP(P-ID)",
            "bootstrap": boot, "signflip": flip,
            "timing_s": {"macro_ap": t_ap, "bootstrap": t_boot, "signflip": t_flip}}


# ═══════════════════════════════════════════════════════════════════════════
# stage: signcheck — 부호 방향 **합성 데이터** 검증 1회 (확증값 미사용)
# ═══════════════════════════════════════════════════════════════════════════
def _synthetic(n=200, K=20, n_groups=60, seed=20260804):
    rng = np.random.default_rng(seed)
    y = (rng.random((n, K)) < 0.25).astype(int)
    for j in range(K):                                   # 각 PT 에 양성 ≥2 보장
        if y[:, j].sum() < 2:
            y[rng.choice(n, 2, replace=False), j] = 1
    strong = np.clip(0.8 * y + 0.2 * rng.random((n, K)), 0, 1)      # 라벨과 강상관 → 높은 AP
    weak = rng.random((n, K))                                        # 무정보 → 낮은 AP
    groups = np.array([f"g{i % n_groups:03d}" for i in range(n)])
    return y, strong, weak, groups


def stage_signcheck():
    logln("[signcheck] 부호 방향 검증 — **합성 데이터만** 사용(확증 consensus 미사용)")
    import inspect
    y, strong, weak, groups = _synthetic()

    # (1) 동결 연산자 시그니처 = (기준 arm, 비교 arm) 슬롯인지
    sig_b = list(inspect.signature(sap_bootstrap.paired_scaffold_bootstrap).parameters)[:2]
    sig_f = list(inspect.signature(sap_signflip.scaffold_signflip).parameters)[:2]
    assert sig_b == ["consensus_M1b", "consensus_M2b"], sig_b
    assert sig_f == ["cM1b", "cM2b"], sig_f

    # (2) 비교 arm 이 우수하면 Δ > 0 이어야 한다 (규약 방향)
    ap_strong = sap_metrics.macro_ap(y, strong, None)["macro_ap"]
    ap_weak = sap_metrics.macro_ap(y, weak, None)["macro_ap"]
    assert ap_strong > ap_weak, "합성 데이터 구성 실패 — strong arm 이 우수하지 않다"

    fake_d = {"Ym": y, "scaffold": groups, "cid_pos": {i: i for i in range(len(y))}}
    fake_unit = {"cids": list(range(len(y)))}
    res_fwd = run_unit(fake_unit, fake_d, {"P-ID": weak, "M2b": strong}, 50,
                       SEED_BOOTSTRAP, SEED_SIGNFLIP)
    res_rev = run_unit(fake_unit, fake_d, {"P-ID": strong, "M2b": weak}, 50,
                       SEED_BOOTSTRAP, SEED_SIGNFLIP)
    assert res_fwd["delta"] > 0, "비교 arm(M2b 슬롯)이 우수한데 Δ 가 양수가 아니다"
    assert res_rev["delta"] < 0, "기준 arm(P-ID 슬롯)이 우수한데 Δ 가 음수가 아니다"
    assert abs(res_fwd["delta"] + res_rev["delta"]) < 1e-12, "Δ 반대칭성 실패"
    assert abs(res_fwd["bootstrap"]["delta_obs"] - res_fwd["delta"]) < 1e-12
    assert abs(res_fwd["signflip"]["delta_obs"] - res_fwd["delta"]) < 1e-12

    # (3) 블록 H `run_unit` 과 **동일 슬롯 매핑**인지 — 같은 합성 입력에서 Δ 가 정확히 일치
    h_res = H.run_unit(fake_unit, fake_d, {"M1b": weak, "M2b": strong}, 50,
                       SEED_BOOTSTRAP, SEED_SIGNFLIP)
    same = (h_res["delta"] == res_fwd["delta"]
            and h_res["bootstrap"]["delta_obs"] == res_fwd["bootstrap"]["delta_obs"]
            and h_res["signflip"]["p_two_sided"] == res_fwd["signflip"]["p_two_sided"])
    assert same, "블록 H run_unit 과 arm 슬롯 매핑이 다르다"

    out = {"_scope": ("공개 — **합성 데이터** 위의 부호 규약 검증 결과(PASS/FAIL)뿐. "
                      "확증 consensus 는 본 스테이지에서 읽지 않는다."),
           "ts_kst": now_kst(),
           "synthetic_only": True, "confirmatory_data_used": False,
           "convention": "Δ_PID = macro AP(M2b) − macro AP(P-ID) (HOLM_FAMILY ② `M2b-P-ID`)",
           "operator_signature_first_two_args": {"paired_scaffold_bootstrap": sig_b,
                                                 "scaffold_signflip": sig_f},
           "slot_mapping": {"arg1_baseline_arm": "P-ID", "arg2_comparison_arm": "M2b"},
           # ⚠️ 검사 **이름**도 L-5 금지 접두사(`delta`·`sign`·`ci_`·`p_`·`boot_`·`null_`)를 피한다.
           #    (값이 아닌 플래그 이름이라도 공개 파일 키 스캔에 걸리면 안 된다.)
           "checks": {
               "better_comparison_arm_gives_positive_contrast": True,
               "better_baseline_arm_gives_negative_contrast": True,
               "antisymmetric_on_arm_swap": True,
               "bootstrap_observed_matches_point_estimate": True,
               "permutation_test_observed_matches_point_estimate": True,
               "identical_to_block_H_run_unit_slot_mapping": bool(same)},
           "all_pass": True}
    dump_json(F_SIGNCHECK, out)
    logln("[signcheck] PASS — 슬롯 (arg1=P-ID 기준, arg2=M2b 비교) · 방향 규약 일치 · "
          "블록 H run_unit 과 동일 매핑(합성 입력에서 Δ 완전 일치)")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: pilot — L-3 계측 (산출 전량 폐기 · 시간만 기록)
# ═══════════════════════════════════════════════════════════════════════════
def stage_pilot():
    logln(f"[pilot] L-3 계측 — B={B_PILOT}. 파일럿 통계 산출은 전량 폐기(봉인 저장 0).")
    d = H.load_common()
    df = pd.read_csv(F_STRATA)
    cons = load_consensus_pair(d)
    units = H.estimation_units(df, d)

    # (a) 층마다 Δ 1회 실측 — 비용 지배변수(층 내 양성≥1 PT 수)를 **가정하지 않고 직접 측정**
    per_unit = []
    for u in units:
        idx = H.row_index(d, u["cids"])
        y_s, sg_s = d["Ym"][idx], d["scaffold"][idx]
        t0 = time.perf_counter()
        a1 = sap_metrics.macro_ap(y_s, cons["P-ID"][idx], ELIGIBLE_PT)
        a2 = sap_metrics.macro_ap(y_s, cons["M2b"][idx], ELIGIBLE_PT)
        t_ap = time.perf_counter() - t0
        n_pt_defined = int(a1["n_eval"])
        assert a1["n_eval"] == a2["n_eval"], "arm 간 정의 PT 수 불일치(동일 y 이므로 불가능)"
        del a1, a2                                    # 값 폐기 — 시간·개수만 유지
        per_unit.append({"axis": u["axis"], "stratum": u["stratum"], "kind": u["kind"],
                         "n_drugs": len(u["cids"]),
                         "n_clusters": int(len(set(sg_s.tolist()))),
                         "n_pt_with_positive": n_pt_defined,
                         "t_delta_once_s": t_ap})

    # (b) 최대 표본 층에서 B=100 파일럿 → replicate/jackknife 단가 보정계수
    biggest = max(units, key=lambda u: len(u["cids"]))
    pu = next(p for p in per_unit
              if p["axis"] == biggest["axis"] and p["stratum"] == biggest["stratum"])
    logln(f"[pilot] 대상 = {biggest['axis']}/{biggest['stratum']} (n_drugs={pu['n_drugs']})")
    res = run_unit(biggest, d, cons, B_PILOT, SEED_BOOTSTRAP, SEED_SIGNFLIP)
    t = res["timing_s"]
    n_clu = int(res["bootstrap"]["n_clusters"])
    t_delta_p = pu["t_delta_once_s"]
    del res                                            # 파일럿 산출 폐기(봉인 저장 금지)

    # bootstrap wall = (B replicate + n_clusters jackknife) × Δ 1회 비용 ; sign-flip = B × Δ 1회 비용.
    # 파일럿은 그 **비례상수만** 보정한다(음수 분해가 나올 수 없는 형태).
    c_boot = t["bootstrap"] / ((B_PILOT + n_clu) * t_delta_p)
    c_flip = t["signflip"] / (B_PILOT * t_delta_p)

    est, total = [], 0.0
    for p in per_unit:
        s = (c_boot * (B_MAIN + p["n_clusters"]) + c_flip * B_MAIN) * p["t_delta_once_s"]
        est.append({**p, "est_wall_s": s})
        total += s

    out = {
        "_scope": "공개 — 시간·표본수 뿐. 파일럿 통계 산출은 전량 폐기(봉인 저장 없음).",
        "ts_kst": now_kst(), "B_pilot": B_PILOT, "B_main": B_MAIN,
        "pilot_unit": {"axis": biggest["axis"], "stratum": biggest["stratum"],
                       "n_drugs": pu["n_drugs"], "n_clusters": n_clu,
                       "n_pt_with_positive": pu["n_pt_with_positive"]},
        "pilot_timing_s": {"t_delta_once_s": t_delta_p, "bootstrap_B100": t["bootstrap"],
                           "signflip_B100": t["signflip"]},
        "calibration_constants": {"c_bootstrap": c_boot, "c_signflip": c_flip},
        "scaling_model": (
            "층 wall ≈ [c_bootstrap × (B + n_clusters) + c_signflip × B] × t_delta_once(층). "
            "**t_delta_once 는 층마다 직접 실측**한다 — 블록 H 는 이를 n_drugs 선형으로 **가정**해 "
            "1.74배 과소추정했다. 실제 지배변수는 층 내 **양성≥1 PT 수**(동결 undefined-AP 규칙상 "
            "양성 0 PT 는 건너뛴다)이며, 층마다 Δ 1회를 실측하면 그 변수를 가정 없이 반영한다. "
            "c_* 는 최대 표본 층 B=100 실측에서 보정한 비례상수(1 근처면 모형 적합)."),
        "n_units": len(units),
        "estimate_per_unit": est,
        "estimated_total_wall_s": total,
        "estimated_total_wall_hours": total / 3600.0,
        "estimated_total_wall_days": total / 86400.0,
        "abort_threshold_days": WALL_ABORT_DAYS,
        "exceeds_threshold": bool(total / 86400.0 > WALL_ABORT_DAYS),
        "pilot_artifacts_discarded": True,
    }
    dump_json(F_PILOT, out)
    logln(f"[pilot] 전 층({len(units)}) × B={B_MAIN} 총 추정 wall = {total / 3600:.2f}h "
          f"({total / 86400:.3f}일) · 7일 초과 = {out['exceeds_threshold']}")
    assert not out["exceeds_threshold"], \
        f"[중단] 추정 총 wall {total / 86400:.2f}일 > {WALL_ABORT_DAYS}일 — 실행하지 않는다."
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: estimate — L-4 본계산 (산출 전량 `_sealed/`) · (축,층) 체크포인트 재개
# ═══════════════════════════════════════════════════════════════════════════
def load_checkpoint():
    done = {}
    if not os.path.exists(F_CKPT):
        return done
    with open(F_CKPT, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            rec = json.loads(ln)
            assert rec["key"] not in done, f"체크포인트 중복 키: {rec['key']}"
            done[rec["key"]] = rec
    return done


def append_checkpoint(rec):
    os.makedirs(SEALED_DIR, exist_ok=True)
    with open(F_CKPT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=H.native) + "\n")
        f.flush()
        os.fsync(f.fileno())


# L-5 방어 규칙 — 지시서 문면 그대로 해석한다:
#   `macro_ap`·`delta`·`sign` = **정확한 키 이름**(별표 없음) · `ci_*`·`p_*`·`boot_*`·`null_*` = 접두사.
#   여기에 실제 값을 담는 파생 키(`delta_obs`·`macro_ap_M2b`·`sign_flip_p` …)를 막기 위해
#   `delta_`·`macro_ap`·`sign_` 접두사를 **추가로** 금지한다.
#   ⚠️ `sign` 을 통짜 접두사로 쓰면 `signflip_B100`(= sign-flip **소요시간**) 같은 **방법 이름**까지
#      잡혀 정당한 시간 기록을 막는다 → `sign_` 로 좁힌다. 부호 자체는 아래 **값 검사**가 막는다.
FORBIDDEN_EXACT = {"macro_ap", "delta", "sign", "delta_obs", "delta_sign", "p_two_sided"}
FORBIDDEN_PREFIX = ("ci_", "p_", "boot_", "null_", "delta_", "macro_ap", "sign_")
FORBIDDEN_VALUES = {"positive", "negative", "zero"}      # `emit_sign` 출력 = 부호 라벨


def assert_public_redacted(obj, path="$"):
    """공개 산출물에 Δ·AP·CI·p 계열 키와 **부호 값**이 부재함을 강제(L-5 방어 assert)."""
    hits, vhits = [], []

    def walk(o, p):
        if isinstance(o, dict):
            for k, v in o.items():
                ks = str(k)
                if ks in FORBIDDEN_EXACT or ks.startswith(FORBIDDEN_PREFIX):
                    hits.append(f"{p}.{ks}")
                if ks.startswith("forbidden_"):
                    continue          # 규칙 **선언** 자체는 데이터가 아니다(자기참조 오탐 방지)
                walk(v, f"{p}.{ks}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{p}[{i}]")
        elif isinstance(o, str) and o.strip().lower() in FORBIDDEN_VALUES:
            vhits.append(p)

    walk(obj, path)
    assert not hits, f"[방어 FAIL] 공개 산출물에 봉인 계열 키 검출: {hits[:10]}"
    assert not vhits, f"[방어 FAIL] 공개 산출물에 부호 라벨 값 검출: {vhits[:10]}"
    return {"forbidden_exact": sorted(FORBIDDEN_EXACT),
            "forbidden_prefixes": list(FORBIDDEN_PREFIX),
            "forbidden_values": sorted(FORBIDDEN_VALUES),
            "key_hits": [], "value_hits": [], "pass": True}


def stage_estimate():
    logln(f"[estimate] L-4 본계산 — B={B_MAIN}, seed boot={SEED_BOOTSTRAP} "
          f"flip={SEED_SIGNFLIP}. 산출 전량 `_sealed/`.")
    d = H.load_common()
    df = pd.read_csv(F_STRATA)
    summ = json.load(open(F_STRATA_SUM, encoding="utf-8"))
    acct = json.load(open(F_ACCT_PUB, encoding="utf-8"))["axes"]
    cons = load_consensus_pair(d)
    units = H.estimation_units(df, d)
    assert len(units) == EXPECT_N_UNITS

    # 세션 분할 대비 — 환경 지문 일치 확인
    if os.path.exists(F_ENVFP):
        prev = json.load(open(F_ENVFP, encoding="utf-8"))
        cur = env_fingerprint(prev["inputs_sha256"])
        for k in ("python", "numpy", "scipy", "sklearn", "pandas", "machine",
                  "ladder_freeze_sha16", "sap_manifest_sha16"):
            assert prev[k] == cur[k], f"세션 간 환경 불일치: {k} {prev[k]} != {cur[k]}"

    done = load_checkpoint()
    if done:
        logln(f"[estimate] 체크포인트 재개 — 완주 층 {len(done)}/{len(units)}")

    t_all = time.perf_counter()
    for k, u in enumerate(units, 1):
        key = f"{u['axis']}::{u['stratum']}"
        if key in done:
            logln(f"[estimate] {k}/{len(units)} {key} — 체크포인트 존재, SKIP")
            continue
        gate_b_exclusive(f"unit={key}:before")
        t0 = time.perf_counter()
        res = run_unit(u, d, cons, B_MAIN, SEED_BOOTSTRAP, SEED_SIGNFLIP)
        wall = time.perf_counter() - t0
        b = res["bootstrap"]
        src = (summ["unstable"][u["axis"]] if u["kind"] == "unstable"
               else summ["axes"][u["axis"]][u["stratum"]])
        rec = {"key": key, "ts_kst": now_kst(),
               "sealed": {"axis": u["axis"], "stratum": u["stratum"], "kind": u["kind"],
                          "n_drugs": len(u["cids"]), "cids": u["cids"], **res},
               "public": {"axis": u["axis"], "stratum": u["stratum"], "kind": u["kind"],
                          "role": AXIS_ROLE[u["axis"]],
                          "n_drugs": len(u["cids"]),
                          "n_clusters": int(b["n_clusters"]),
                          "n_eff_clusters": float(b["n_eff_clusters"]),
                          "n_pt_meeting_positive_support": src["n_pt_meeting_positive_support"],
                          "inference_mode": src["inference_mode"],
                          "primary_ci_estimability": b["ci_primary"]["status"],
                          "bca_estimability": b["ci_bca"]["status"],
                          "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP,
                          "seed_signflip": SEED_SIGNFLIP, "wall_s": wall}}
        append_checkpoint(rec)
        done[key] = rec
        gate_b_exclusive(f"unit={key}:after")
        logln(f"[estimate] {k}/{len(units)} {key} n={len(u['cids'])} "
              f"clusters={b['n_clusters']} primary_ci={b['ci_primary']['status']} "
              f"wall={wall:.1f}s")
    session_wall = time.perf_counter() - t_all

    ordered = [f"{u['axis']}::{u['stratum']}" for u in units]
    assert set(done) == set(ordered), f"완주 층 불일치: {set(ordered) - set(done)}"

    sealed = {"_warning": "SEALED — 성공판정(개봉) 단계 전 열람 금지.",
              "step": "§13-6 커버리지 C2 — Δ(M2b−P-ID) 층화(블록 L)", "ts_kst": now_kst(),
              "contrast": "Δ_PID = macro AP(M2b) − macro AP(P-ID)",
              "holm_family_id": "② M2b-P-ID",
              "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
              "unit": BOOT_UNIT, "eligible_pt": "None(370 PT 전열)",
              "multiplicity": "미적용 — Holm/BH 는 성공판정 단계 일괄(본 단계 raw 산출만)",
              "inputs": {"consensus_M2b": EXPECT_SHA[
                             "experiments/runs/v3_consensus_rep123/_sealed/consensus_M2b.npz"],
                         "consensus_P-ID": EXPECT_SHA[
                             "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_P-ID.npz"]},
              "strata": {k: done[k]["sealed"] for k in ordered}}

    store = sap_redaction.SealedStore(RUN_DIR)
    sealed_path = store.write_sealed("stratification_pid_result.json", json.loads(
        json.dumps(sealed, ensure_ascii=False, default=H.native)))
    sealed_sha = sha256_file(sealed_path)

    guard_end = guard_snapshot()
    guard_start = json.load(open(F_GATES, encoding="utf-8"))["sealed_guard_start"]
    assert guard_end == guard_start, "sealed guard 변경 감지 — 기존 sealed 산출물이 수정되었다"
    n_open = count_open_sealed()
    assert n_open == 0, f"open_sealed {n_open}건 — 개봉 금지 위반"

    public_units = [done[k]["public"] for k in ordered]

    # L-5 — 블록 K 회계 공개표와 층별 표본수 일치
    by_key = {f"{p['axis']}::{p['stratum']}": p["n_drugs"] for p in public_units}
    for axis, a in acct.items():
        for st, n in a["n_drugs_by_stratum"].items():
            assert by_key[f"{axis}::{st}"] == n, f"블록 K 표본수 불일치 {axis}/{st}"
        assert by_key[f"{axis}::unstable_stratum"] == a["unstable_stratum"], \
            f"블록 K unstable 표본수 불일치 {axis}"

    total_wall = sum(p["wall_s"] for p in public_units)
    n_not_est = sum(1 for p in public_units if p["primary_ci_estimability"] != "estimable")
    n_formal = sum(1 for p in public_units if p["inference_mode"] == "formal")
    n_desc = sum(1 for p in public_units if p["inference_mode"] == "descriptive")

    pub = {
        "_scope": ("공개 — 층별 표본수·클러스터수·formal/descriptive 라벨·축 위상·B·seed·소요시간·"
                   "해시·게이트 PASS/FAIL 뿐. **층별 macro AP·Δ·CI·sign-flip p 는 물론 Δ 의 부호도 "
                   "본 파일에 없다**(전량 `_sealed/`)."),
        "ts_kst": now_kst(), "block": "L (docs/57)",
        "contrast_label": "M2b vs P-ID (HOLM_FAMILY ② `M2b-P-ID`)",
        "n_units": len(public_units),
        "units": public_units,
        "n_units_formal": n_formal, "n_units_descriptive": n_desc,
        "n_units_primary_ci_not_estimable": n_not_est,
        "unstable_stratum_counts": {a: summ["unstable"][a]["n_drugs"] for a in summ["unstable"]},
        "excluded_no_target_drugs": summ["excluded_no_target_drugs"],
        "denominator_estimated": EXPECT_DENOM,
        "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
        "seed_reuse_note": ("블록 H 와 **동일 seed 재사용**(새 seed 미추첨) — 층·B·재표집 인덱스를 "
                            "M1b 대비와 동일 조건으로 두어 두 대비의 차이가 재표집 난수에서 "
                            "생기지 않게 한다."),
        "bootstrap_unit": BOOT_UNIT, "primary_ci_method": sap_bootstrap.PRIMARY_CI_METHOD,
        "bca_fallback_rule": "BCa 실패 시 percentile 대체 금지 — not_estimable 그대로 봉인",
        "sample_counts_match_block_K": True,
        "strata_definition_source": "블록 H `stratification_run.py` 무수정 import 재사용(층 13개 동일)",
        "recomputed_nothing": ["consensus OOF(M2b·P-ID·M1b)", "strata_assignment.csv",
                               "struct_bounds.json", "identity_pairs.tsv"],
        "total_wall_s": total_wall, "total_wall_hours": total_wall / 3600.0,
        "session_wall_s": session_wall,
        "sealed_result_sha256": sealed_sha,
        "sealed_result_path": os.path.relpath(sealed_path, ROOT),
        "sealed_guard_n_files_end": len(guard_end),
        "sealed_guard_unchanged": True,
        "ladder_freeze_sha16": EXPECT_LADDER_FREEZE_SHA16,
        "sap_manifest_sha16": EXPECT_SAP_MANIFEST_SHA16,
        "decision_functions_called": [],
        "multiplicity_applied": False,
        "open_sealed_calls": n_open,
        "emit_sign_called": False,
        "models_trained": 0, "new_oof_generated": 0, "network_calls": 0, "git_commit": False,
        "redaction": ("공개 파일에 층별 macro AP·Δ·CI·sign-flip p·부트스트랩 분포·**Δ 부호** 없음"),
        "all_pass": True,
    }
    pub["public_redaction_assert"] = assert_public_redacted(pub)
    dump_json(F_PUBLIC, pub)
    # 기록 후 파일 자체를 다시 읽어 재검사(직렬화 경로까지 커버).
    # 공개 4파일 전체 교차 스캔은 `recheck` 스테이지가 담당한다.
    assert_public_redacted(json.load(open(F_PUBLIC, encoding="utf-8")))

    logln(f"[estimate] 완료 — 층 {len(public_units)} · 총 계산 wall {total_wall / 3600:.2f}h · "
          f"not_estimable {n_not_est} · sealed sha16 {sealed_sha[:16]} · guard {len(guard_end)}종 불변")
    return pub


# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# stage: recheck — 공개 4파일 **교차** redaction 스캔 + 무결성 재확인 (재계산 0)
# ═══════════════════════════════════════════════════════════════════════════
F_SCAN = os.path.join(RUN_DIR, "redaction_scan_public.json")


def stage_recheck():
    """본계산 이후 공개 산출물 전건 교차검사. 통계 재계산 0 · 봉인 산출물 무수정.

    `signcheck` 를 먼저 다시 돌려 공개 파일을 재생성한다(합성 데이터 전용이라 확증값 미접근).
    """
    logln("[recheck] 공개 4파일 교차 redaction 스캔 + 무결성 재확인 (재계산 0)")
    stage_signcheck()                                    # 합성 전용 · 확증 consensus 미사용

    scanned = {}
    for f in (F_GATES, F_SIGNCHECK, F_PILOT, F_PUBLIC):
        assert os.path.exists(f), f"공개 산출물 부재: {os.path.relpath(f, ROOT)}"
        obj = json.load(open(f, encoding="utf-8"))
        assert_public_redacted(obj, path=os.path.basename(f))
        scanned[os.path.basename(f)] = {"sha256": sha256_file(f), "hits": 0}

    pub = json.load(open(F_PUBLIC, encoding="utf-8"))
    sealed_path = os.path.join(ROOT, pub["sealed_result_path"])
    assert sha256_file(sealed_path) == pub["sealed_result_sha256"], \
        "봉인 산출물 sha256 이 공개 요약 기록과 다르다"
    guard_end = guard_snapshot()
    guard_start = json.load(open(F_GATES, encoding="utf-8"))["sealed_guard_start"]
    assert guard_end == guard_start, "sealed guard 변경 감지"
    n_open = count_open_sealed()
    assert n_open == 0, f"open_sealed {n_open}건"
    n_ckpt = sum(1 for ln in open(F_CKPT, encoding="utf-8") if ln.strip())
    assert n_ckpt == EXPECT_N_UNITS, f"체크포인트 {n_ckpt}행 != {EXPECT_N_UNITS}"

    out = {"_scope": "공개 — 교차검사 PASS/FAIL·해시·개수 뿐.",
           "ts_kst": now_kst(), "block": "L (docs/57) — recheck",
           "note": ("본계산 종료 직후의 자체 교차검사가 두 번 실패했다. 둘 다 **내 검사코드 결함**이며 "
                    "봉인 산출물·통계량과 무관하다. ① `signcheck_public.json` 의 **검사 이름** 2개"
                    "(`delta_…`·`signflip_…`)가 금지어에 걸렸다 → assert 를 완화하지 않고 검사 이름을 "
                    "바꿔 재생성했다. ② `pilot_timing.json` 의 `signflip_B100`(= sign-flip **소요시간**)이 "
                    "걸렸다 → 원인은 내가 `sign` 을 통짜 접두사로 쓴 것이다. 지시서 L-5 목록은 "
                    "`macro_ap`·`delta`·`sign` 이 **정확한 키 이름**이고 별표가 붙은 `ci_*`·`p_*`·`boot_*`·"
                    "`null_*` 만 접두사이므로, 규칙을 그 문면대로 되돌리고 파생 키 접두사"
                    "(`delta_`·`macro_ap`·`sign_`)를 추가했다. 대신 부호 유출은 **값 검사**"
                    "(`positive`/`negative`/`zero` 값 부재)로 직접 막는다 — 이전보다 좁아진 것이 아니라 "
                    "부호에 대해서는 더 정확해졌다. 통계량·봉인 산출물은 재계산하지 않았다."),
           "files_scanned": scanned,
           "forbidden_exact": sorted(FORBIDDEN_EXACT),
           "forbidden_prefixes": list(FORBIDDEN_PREFIX),
           "forbidden_values": sorted(FORBIDDEN_VALUES),
           "total_hits": 0,
           "sealed_result_sha256_matches_public_record": True,
           "sealed_guard_n_files": len(guard_end), "sealed_guard_unchanged": True,
           "open_sealed_calls": n_open, "checkpoint_rows": n_ckpt,
           "recomputed_statistics": 0, "sealed_artifacts_modified": 0,
           "all_pass": True}
    assert_public_redacted(out, path="redaction_scan_public.json")
    dump_json(F_SCAN, out)
    assert_public_redacted(json.load(open(F_SCAN, encoding="utf-8")), path="redaction_scan_public.json")
    logln(f"[recheck] PASS — 공개 4파일 검출 0 · 봉인 sha 일치 · guard {len(guard_end)}종 불변 · "
          f"open_sealed {n_open} · 체크포인트 {n_ckpt}행")
    return out


# ═══════════════════════════════════════════════════════════════════════════
STAGES = {"verify": stage_verify, "signcheck": stage_signcheck,
          "pilot": stage_pilot, "estimate": stage_estimate, "recheck": stage_recheck}
ORDER = ["verify", "signcheck", "pilot", "estimate", "recheck"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=list(STAGES) + ["all"])
    a = ap.parse_args()
    os.makedirs(RUN_DIR, exist_ok=True)
    stages = ORDER if a.stage == "all" else [a.stage]
    out = None
    with ComputeLock(script="pid_stratification_run.py", role="runner"):
        gate_a_load(f"stage={a.stage}")
        for s in stages:
            gate_b_exclusive(f"stage={s}:before")
            out = STAGES[s]()
            gate_b_exclusive(f"stage={s}:after")
    return out


if __name__ == "__main__":
    main()
