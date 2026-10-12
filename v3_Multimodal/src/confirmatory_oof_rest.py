#!/usr/bin/env python3
"""confirmatory_oof_rest.py — 블록 I: 확증 RF 사다리 **잔여 6모델** OOF (M0·M1·M2·P-ID·P-FAM·C-CAP).

정본 스펙: `docs/48_v3_rf_remaining_oof_prompt_for_vscode.md`
(사전등록 `docs/30` §4·§6·§7 준수 · `docs/33` 항목22 판독확정 = pre-look 기입 완료 후에만 실행).

⛔ 무결성 최상위
  - **개봉 없음**: `SealedStore.open_sealed` 미호출 · `_sealed/` 값의 사람 판독형 출력 0.
  - **성공판정·다중성 없음**: `sap/decision.py` 의 `rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence` 미호출.
  - **부호도 비공개**(docs/48 I-0-3): `emit_sign` **미호출**, Δ·AP·CI·p 를 공개 파일에 기입 0.
    공개 산출 = **완주 개수·해시·시간·메모리·게이트 PASS/FAIL 뿐**(방어 assert 로 강제).
  - **기존 sealed 불변**: `v3_confirm_rep{1,2,3}_seed{201,202,203}` · `v3_consensus_rep123` ·
    `v3_null_MAIN` · `v3_stratification` 의 `_sealed/` 는 읽기만 한다(access.log append 제외).
    `M1b`·`M2b` 는 **재계산하지 않는다**. 신규 산출은 **별도 디렉터리**에만 쓴다.
  - **split 재추첨 없음**: `data/processed/splits/confirmatory/rep{r}_seed{s}/folds.json` 을 그대로 읽는다.
  - `ladder_freeze.json`·SAP 11모듈·`sap/manifest.json`·`docs/30` 무수정 · 네트워크 0 ·
    `data/raw/` 변경 0 · git commit·push 0.

동일성 요구(docs/48 I-2)
  - `confirmatory_oof_rep1` 의 fold 로더·블록 클래스·봉인 경로 함수를 **import 재사용**(두 파일 무수정).
  - RF `random_state=42` 전 fold 공통 · `eligible_pt=None` · undefined-AP 는 `sap/metrics.macro_ap` 위임.
  - **재현성 증명**: 본 러너로 rep1 `M2b` **fold 0** 을 재계산해 기존 sealed `oof_M2b.npz` 의
    해당 행과 **바이트 동일**함을 확인한다. 실패 시 본계산 착수 금지.

실행:
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rest.py --stage verify
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rest.py --stage measure
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rest.py --stage run
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rest.py --stage consensus
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rest.py --stage all      # 위 4단계 순차
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from compute_lock import (ComputeLock, gate_a_load,                      # noqa: E402
                          gate_b_exclusive, gate_c_settle)
# ── 반복1 하네스 재사용(수정 금지) ────────────────────────────────────────────
from confirmatory_oof_rep1 import gate0_verify, sha256_file              # noqa: E402
from ladder_confirmatory import (                                        # noqa: E402
    load_frozen, MorganBlock, CountMaskBlock, SeqBlock, M1bCovariateBlock,
    PidBlock, FamilyBlock, CcapBlock, rf_fit_predict,
    MODEL_BLOCKS, FROZEN_MODELS, RF_KW, SEED, PCA_K,
)
from sap import consensus as sap_consensus                               # noqa: E402
from sap import metrics as sap_metrics                                   # noqa: E402
from sap import redaction as sap_redaction                               # noqa: E402

KST = timezone(timedelta(hours=9))

# ═══════════════════════════════════════════════════════════════════════════
# 사전 고정 상수 (결과 조회 전 확정 — 실행 중 변경 금지)
# ═══════════════════════════════════════════════════════════════════════════
REST_MODELS = ["M0", "M1", "M2", "P-ID", "P-FAM", "C-CAP"]   # docs/48 I-0-1
REUSE_MODELS = ["M1b", "M2b"]                                # 기존 산출 재사용(재계산 금지)
SEED_MAP = {1: 201, 2: 202, 3: 203}
N_FOLD = 5
RF_SEED = SEED                     # 42
EXPECT_N_DRUGS = 1092
EXPECT_N_PT = 370
EXPECT_N_SCAFFOLD_GROUPS = 732
ABORT_DAYS = 7.0                   # docs/48 I-4-0 정지 임계
MEASURE_MODEL = "P-ID"             # 최고차원(고차원 multi-hot 블록) → 계측 대상
EQUIV_MODEL = "M2b"                # 재현성 증명 대상(기존 sealed 존재)
EQUIV_REP, EQUIV_FOLD = 1, 0

# 블록 fit 표준 순서 (ladder_confirmatory.main 과 동일; C_ccap 은 B_seq 이후)
FIT_ORDER = ["B0", "B1", "B_seq", "C_ccap", "B_pid", "B_m1b", "B_fam"]

EXPECT_CONFIG_SHA16 = "b885585aefbabb32"
EXPECT_MANIFEST_SHA16 = "756d485feb4715e9"

PROC = os.path.join(ROOT, "data", "processed")
RUNS = os.path.join(ROOT, "experiments", "runs")
BASE_DIR = os.path.join(RUNS, "v3_confirm_rest")
SEALED_BASE = os.path.join(BASE_DIR, "_sealed")
PARTIAL_DIR = os.path.join(SEALED_BASE, "_partial")
CKPT = os.path.join(SEALED_BASE, "checkpoint.jsonl")
ENV_FP = os.path.join(SEALED_BASE, "env_fingerprint.json")
CONS_DIR = os.path.join(RUNS, "v3_confirm_rest_consensus_rep123")
PROV_DIR = os.path.join(ROOT, "experiments", "provenance")
FIRST_LOOK_LOG = os.path.join(PROV_DIR, "first_look_log.json")
DOC33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")

# 불변 확인 대상 sealed 디렉터리 (access.log 은 machine_read append 로 변하므로 제외)
SEALED_GUARD_DIRS = [
    os.path.join(RUNS, "v3_confirm_rep1_seed201", "_sealed"),
    os.path.join(RUNS, "v3_confirm_rep2_seed202", "_sealed"),
    os.path.join(RUNS, "v3_confirm_rep3_seed203", "_sealed"),
    os.path.join(RUNS, "v3_consensus_rep123", "_sealed"),
    os.path.join(RUNS, "v3_null_MAIN", "_sealed"),
    os.path.join(RUNS, "v3_stratification", "_sealed"),
]

# 공개 파일에 절대 나타나면 안 되는 키(방어 assert)
FORBIDDEN_PUBLIC_KEYS = ("macro_ap", "delta", "sign", "ci_", "p_", "per_pt_ap",
                         "per_fold_macro_ap", "boot", "null_summary")

_LOG = []


# ═══════════════════════════════════════════════════════════════════════════
# 유틸
# ═══════════════════════════════════════════════════════════════════════════
def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    _LOG.append(line)


def flush_log():
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(os.path.join(BASE_DIR, "run.log"), "a", encoding="utf-8") as f:
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=native)
    return path


def peak_rss_gib():
    """macOS: ru_maxrss = bytes."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 3)


def run_dir_of(r):
    return os.path.join(RUNS, f"v3_confirm_rest_rep{r}_seed{SEED_MAP[r]}")


def split_dir_of(r):
    return os.path.join(PROC, "splits", "confirmatory", f"rep{r}_seed{SEED_MAP[r]}")


def ref_sealed_of(r):
    return os.path.join(RUNS, f"v3_confirm_rep{r}_seed{SEED_MAP[r]}", "_sealed")


def sealed_guard_snapshot():
    """기존 sealed 산출물의 sha256 스냅샷 (access.log 제외)."""
    out = {}
    for d in SEALED_GUARD_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if os.path.isfile(p) and fn != "access.log":
                out[os.path.relpath(p, ROOT)] = sha256_file(p)
    return out


def log_machine_read(sealed_dir, path_rel, purpose, step):
    """봉인 산출물의 **기계 판독** 기록(사람 열람 아님)."""
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": step,
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    with open(os.path.join(sealed_dir, "access.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def append_first_look(entry):
    os.makedirs(PROV_DIR, exist_ok=True)
    log = json.load(open(FIRST_LOOK_LOG)) if os.path.exists(FIRST_LOOK_LOG) else []
    if isinstance(log, dict):
        log = [log]
    log.append(entry)
    dump_json(FIRST_LOOK_LOG, log)


# ═══════════════════════════════════════════════════════════════════════════
# I-1  착수 전 확인 (판독 전용)
# ═══════════════════════════════════════════════════════════════════════════
def gate_prelook_recorded():
    """docs/48 I-0: 판독확정이 docs/33 에 기입돼 있어야 본계산 착수 가능."""
    txt = open(DOC33, encoding="utf-8").read()
    ok = "판독확정(pre-look, 블록 I-0)" in txt
    assert ok, "[I-0] docs/33 에 판독확정 기입이 없음 — 계산 착수 금지"
    logln("[I-0] docs/33 판독확정(pre-look) 기입 확인 — 착수 허용")
    return {"prelook_recorded": True, "docs33_sha16": sha256_file(DOC33)[:16]}


def read_fold_membership(r):
    """`fold_membership.csv` 판독 — **빈 scaffold 그룹 복원 필수**.

    `scaffold_of()` 는 파싱불가·무고리 분자에 빈 문자열 `""` 을 부여하고
    `build_scaffold_groups` 는 그것을 **하나의 정당한 그룹**으로 센다(3반복 각 77분자).
    그런데 CSV 는 그 값을 빈 필드로 적고 `pd.read_csv` 는 **NaN 으로 되돌린다**.
    `nunique()`·`groupby()` 는 기본적으로 NaN 을 버리므로, 보정하지 않으면
    (i) 그룹 수가 732 → 731 로 보이고 (ii) **최대 그룹이 fold 교차 검사에서 통째로 빠진다**.
    따라서 판독 즉시 `""` 로 되돌려 동결 정의와 일치시킨다.
    """
    df = pd.read_csv(os.path.join(split_dir_of(r), "fold_membership.csv"))
    df["scaffold"] = df["scaffold"].fillna("")
    return df


def gate_inputs():
    """docs/48 I-1-3: split·master·블록 소스 존재·행수·sha."""
    out = {"splits": {}, "sources": {}}
    for r in (1, 2, 3):
        sd = split_dir_of(r)
        fj, fm = os.path.join(sd, "folds.json"), os.path.join(sd, "fold_membership.csv")
        assert os.path.exists(fj) and os.path.exists(fm), f"rep{r} split 파일 부재"
        j = json.load(open(fj))
        df = read_fold_membership(r)
        n_groups = int(df["scaffold"].nunique())
        # 동결 split_manifest 의 진단값과 교차검증(단일 출처에 의존하지 않는다)
        man = json.load(open(os.path.join(sd, "split_manifest.json")))
        n_groups_man = int(man["diagnostics"]["n_scaffold_groups"])
        assert len(j) == EXPECT_N_DRUGS, f"rep{r} folds.json {len(j)} != {EXPECT_N_DRUGS}"
        assert len(df) == EXPECT_N_DRUGS, f"rep{r} fold_membership {len(df)} != {EXPECT_N_DRUGS}"
        assert n_groups == n_groups_man == EXPECT_N_SCAFFOLD_GROUPS, \
            f"rep{r} scaffold group CSV {n_groups} · manifest {n_groups_man} " \
            f"!= {EXPECT_N_SCAFFOLD_GROUPS}"
        out["splits"][f"rep{r}_seed{SEED_MAP[r]}"] = {
            "folds_json_sha256": sha256_file(fj), "fold_membership_sha256": sha256_file(fm),
            "n_rows": len(j), "n_scaffold_groups": n_groups,
            "n_scaffold_groups_split_manifest": n_groups_man,
            "n_rows_empty_scaffold": int((df["scaffold"] == "").sum()),
            "fold_sizes": [int((df["fold"] == k).sum()) for k in range(N_FOLD)]}
    srcs = {
        "master_X.parquet": os.path.join(PROC, "master_X.parquet"),
        "master_Y.parquet": os.path.join(PROC, "master_Y.parquet"),
        "B_seq_emb": os.path.join(PROC, "drug_target_emb_meanpool.npy"),
        "B_seq_mask": os.path.join(PROC, "drug_target_mask_meanpool.npy"),
        "B1_ntargets": os.path.join(PROC, "drug_n_targets_meanpool.npy"),
        "B_pid_src": os.path.join(PROC, "target_mapping", "06_targets_human.csv"),
        "B_m1b_src": os.path.join(PROC, "target_mapping", "08_m1b_covariates.csv"),
        "B_fam_src": os.path.join(PROC, "target_mapping", "10_target_family_biological.csv"),
    }
    for k, p in srcs.items():
        assert os.path.exists(p), f"블록 소스 부재: {p}"
        out["sources"][k] = {"path": os.path.relpath(p, ROOT), "sha256": sha256_file(p)}
    logln(f"[I-1-3] 입력 확인 PASS — split 3반복(각 {EXPECT_N_DRUGS}행·scaffold "
          f"{EXPECT_N_SCAFFOLD_GROUPS}) · 블록 소스 {len(srcs)}종 존재·sha 기록")
    return out


def fold_of_row_for(rep, cid_order):
    cid2fold = json.load(open(os.path.join(split_dir_of(rep), "folds.json")))
    return np.array([cid2fold[str(int(c))] for c in cid_order], dtype=int)


# ═══════════════════════════════════════════════════════════════════════════
# 블록 조립 (동결 정의 그대로 — 재정의 금지)
# ═══════════════════════════════════════════════════════════════════════════
def make_blocks(d):
    b_morgan = MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    b_count = CountMaskBlock(d["ntgt"], d["mask"])
    b_seq = SeqBlock(d["emb"], d["mask"], pca_k=PCA_K)
    b_ccap = CcapBlock(b_seq, master_seed=SEED)
    b_pid = PidBlock(d["cid2targets"], d["cid_order"])
    b_m1b = M1bCovariateBlock(d["cov_by_cid"], d["cid_order"],
                              include_pchembl=False, name="B_m1b")
    b_fam = FamilyBlock(d["cid2families_bio"], d["cid_order"], name="B_fam")
    blocks = {"B0": b_morgan, "B1": b_count, "B_seq": b_seq, "C_ccap": b_ccap,
              "B_pid": b_pid, "B_m1b": b_m1b, "B_fam": b_fam}
    assert b_m1b.dim == 10, f"primary B_m1b dim={b_m1b.dim} != 10"
    for m in REST_MODELS + REUSE_MODELS:
        assert m in MODEL_BLOCKS and m in FROZEN_MODELS, f"{m} 이 동결 사다리에 없음"
    return blocks


def needed_blocks(model):
    """모델이 요구하는 블록 + 의존(C_ccap ← B_seq)을 FIT_ORDER 순서로."""
    req = set(MODEL_BLOCKS[model])
    if "C_ccap" in req:
        req.add("B_seq")            # CcapBlock.fit 은 fit 된 B_seq 를 참조
    return [b for b in FIT_ORDER if b in req]


def fit_fold(blocks, model, tr, d, N):
    """fold-train 에서만 fit + 누수 assert(하드). 반환 = 누수 레코드."""
    order = needed_blocks(model)
    for b in order:
        blocks[b].fit(tr)
    leak = {}
    for b in order:
        rec = blocks[b].leakage_assert(tr)
        assert rec["leak_rows"] == 0, f"[{model}] {b} leak_rows != 0"
        leak[b] = int(rec["leak_rows"])
    if "B_seq" in order:            # B_seq PCA fit 모집단 == outer-fold train ∩ 매핑
        expect = np.zeros(N, dtype=bool)
        expect[tr] = True
        expect &= d["mask"].astype(bool)
        assert np.array_equal(blocks["B_seq"]._fit_rows_mask, expect), \
            f"[{model}] B_seq fit 모집단 != train∩매핑"
    return leak, order


def predict_fold(blocks, model, tr, te, Y):
    """RF fit/predict 1 fold — rf_fit_predict(동결) 그대로, random_state=42."""
    ids = MODEL_BLOCKS[model]
    Xtr = np.hstack([blocks[b].transform(tr) for b in ids]).astype(np.float32)
    Xte = np.hstack([blocks[b].transform(te) for b in ids]).astype(np.float32)
    assert RF_SEED == 42, "RF random_state != 42"
    P = rf_fit_predict(Xtr, Y[tr], Xte, seed=RF_SEED)
    return P, int(Xtr.shape[1])


# ═══════════════════════════════════════════════════════════════════════════
# I-2  재현성 증명 (M2b rep1 fold0 바이트 동일성)
# ═══════════════════════════════════════════════════════════════════════════
def stage_verify(d, blocks, g0):
    N = len(d["cid_order"])
    Y = d["Ym"]
    inputs = gate_inputs()
    guard = sealed_guard_snapshot()
    logln(f"[I-1-2] sealed guard 스냅샷 {len(guard)}종 기록(시작)")

    # ── I-3 정합 검증 (하드) ──
    checks = {"n_drugs": N, "n_pt": int(Y.shape[1]), "reps": {}}
    assert N == EXPECT_N_DRUGS and Y.shape[1] == EXPECT_N_PT, "master_X/Y 규모 불일치"
    for r in (1, 2, 3):
        fr = fold_of_row_for(r, d["cid_order"])
        fm = read_fold_membership(r)          # 빈 scaffold 그룹 복원(NaN → "")
        assert list(fm["cid"].astype(int)) == [int(c) for c in d["cid_order"]], \
            f"rep{r} fold_membership cid 정렬 불일치"
        assert np.array_equal(fm["fold"].values, fr), f"rep{r} folds.json != fold_membership"
        # scaffold group 이 정확히 1 fold 에만 속하는가 (fold 교차 0)
        #   ★ 빈 scaffold 그룹(최대 그룹)이 groupby 에서 누락되지 않도록 위에서 "" 로 복원해 둔다.
        by_group = fm.groupby("scaffold")["fold"].nunique()
        assert len(by_group) == EXPECT_N_SCAFFOLD_GROUPS, \
            f"rep{r} 교차검사 대상 그룹 {len(by_group)} != {EXPECT_N_SCAFFOLD_GROUPS} (그룹 누락)"
        cross = int((by_group > 1).sum())
        assert cross == 0, f"rep{r} scaffold group fold 교차 {cross}건"
        # rare-PT: 모든 outer train fold 에서 PT별 양성 ≥1
        lt1 = 0
        for k in range(N_FOLD):
            lt1 += int((Y[fr != k].sum(0) < 1).sum())
        assert lt1 == 0, f"rep{r} rare-PT 위반(train 양성 0인 PT) {lt1}건"
        checks["reps"][f"rep{r}"] = {
            "n_scaffold_groups": int(fm["scaffold"].nunique()),
            "scaffold_fold_cross": cross, "n_pt_train_positive_lt1": lt1,
            "fold_sizes": [int((fr == k).sum()) for k in range(N_FOLD)]}
    logln(f"[I-3] 정합 PASS — 약물 {N} 전수 · scaffold group "
          f"{checks['reps']['rep1']['n_scaffold_groups']} 전수 · fold 교차 0 · "
          f"rare-PT 위반 0 (3반복 전부)")

    # ── I-2 바이트 동일성 증명 ──
    fr = fold_of_row_for(EQUIV_REP, d["cid_order"])
    te = np.where(fr == EQUIV_FOLD)[0]
    tr = np.where(fr != EQUIV_FOLD)[0]
    t0 = time.perf_counter()
    leak, order = fit_fold(blocks, EQUIV_MODEL, tr, d, N)
    P, dim = predict_fold(blocks, EQUIV_MODEL, tr, te, Y)
    wall = time.perf_counter() - t0
    repro = np.zeros((len(te), Y.shape[1]), dtype=np.float64)
    repro[:] = P                          # rep1 과 동일: float64 배열에 float32 대입

    ref_dir = ref_sealed_of(EQUIV_REP)
    ref_path = os.path.join(ref_dir, f"oof_{EQUIV_MODEL}.npz")
    log_machine_read(ref_dir, os.path.relpath(ref_path, ROOT),
                     "I-2 코드경로 바이트 동일성 증명(fold 0 슬라이스 비교)", "블록 I-2")
    with np.load(ref_path) as z:
        ref_oof = z["oof"]
        ref_fold = z["fold"]
        ref_cid = z["cid"]
    assert np.array_equal(ref_fold, fr), "sealed npz 의 fold 배열이 rep1 folds.json 과 불일치"
    assert np.array_equal(ref_cid, np.array([int(c) for c in d["cid_order"]])), \
        "sealed npz 의 cid 배열이 master_X 정렬과 불일치"
    ref_slice = np.ascontiguousarray(ref_oof[te])
    byte_identical = (repro.dtype == ref_slice.dtype
                      and repro.shape == ref_slice.shape
                      and repro.tobytes() == ref_slice.tobytes())
    # 임시 경로에만 기록(기존 sealed 무수정)
    tmp = os.path.join(SEALED_BASE, "_equivalence")
    os.makedirs(tmp, exist_ok=True)
    np.save(os.path.join(tmp, f"repro_{EQUIV_MODEL}_rep{EQUIV_REP}_fold{EQUIV_FOLD}.npy"), repro)
    equiv = {
        "model": EQUIV_MODEL, "repeat": EQUIV_REP, "fold": EQUIV_FOLD,
        "n_test_rows": int(len(te)), "n_pt": int(Y.shape[1]), "dim": dim,
        "dtype": str(repro.dtype), "blocks_fit": order, "leak_rows": leak,
        "byte_identical": bool(byte_identical),
        "sha256_reproduced_slice": hashlib.sha256(repro.tobytes()).hexdigest(),
        "sha256_sealed_slice": hashlib.sha256(ref_slice.tobytes()).hexdigest(),
        "ref_npz_sha256": sha256_file(ref_path),
        "wall_s": wall,
        "note": ("기존 sealed npz 는 5 fold 전체 OOF 를 담으므로 파일 단위 비교가 불가능하다. "
                 "따라서 fold 0 의 test 행 슬라이스를 **원시 바이트**로 비교했다 "
                 "(dtype·shape·tobytes 3중 일치). 재현본은 임시 경로에만 기록하고 "
                 "기존 sealed 는 읽기만 했다(machine_read)."),
    }
    logln(f"[I-2] 재현성 증명 — {EQUIV_MODEL} rep{EQUIV_REP} fold{EQUIV_FOLD} "
          f"({len(te)}행 × {Y.shape[1]}PT, dim={dim}) 바이트 동일 = {byte_identical} "
          f"| wall {wall:.1f}s (수치 미기록 — redaction)")
    if not byte_identical:
        logln("[I-2] ❌ 바이트 동일성 FAIL — 본계산 착수 금지, 즉시 중단")
        flush_log()
        sys.exit(11)

    guard_end = sealed_guard_snapshot()
    assert guard_end == guard, "sealed guard 변동 — 기존 산출물이 수정됐다"
    out = {"ts_kst": now_kst(), "gate0": g0, "inputs": inputs,
           "consistency_checks": checks, "equivalence": equiv,
           "sealed_guard_n_files": len(guard), "sealed_guard_unchanged": True}
    dump_json(os.path.join(BASE_DIR, "verify_public.json"),
              {k: v for k, v in out.items() if k != "equivalence"} |
              {"equivalence": {k: v for k, v in equiv.items()
                               if k not in ("sha256_reproduced_slice", "sha256_sealed_slice")}})
    return out


# ═══════════════════════════════════════════════════════════════════════════
# I-4-0  계측
# ═══════════════════════════════════════════════════════════════════════════
def stage_measure(d, blocks, verify):
    """최고차원 모델 1 fold 실측 → 6모델 × 5fold × 3반복 총 wall 추정."""
    N = len(d["cid_order"])
    Y = d["Ym"]
    fr = fold_of_row_for(1, d["cid_order"])
    te = np.where(fr == 0)[0]
    tr = np.where(fr != 0)[0]

    dims, per_model = {}, {}
    # 모델별 차원 수(조립만 — RF 학습 없음)
    for m in REST_MODELS:
        fit_fold(blocks, m, tr, d, N)
        dim = sum(blocks[b].dim for b in MODEL_BLOCKS[m])
        dims[m] = int(dim)
    logln(f"[I-4-0] 모델별 차원(rep1 fold0 train fit 기준) = {dims}")

    # 최고비용 후보 1 fold 실측
    t0 = time.perf_counter()
    fit_fold(blocks, MEASURE_MODEL, tr, d, N)
    _P, dim_meas = predict_fold(blocks, MEASURE_MODEL, tr, te, Y)
    wall_meas = time.perf_counter() - t0
    per_model[MEASURE_MODEL] = wall_meas
    logln(f"[I-4-0] 계측 — {MEASURE_MODEL} 1 fold(dim={dim_meas}) wall {wall_meas:.1f}s "
          f"| peak RSS {peak_rss_gib():.2f} GiB")

    # 차원 비례 스케일로 나머지 모델 추정(보수적: 하한 0.5×)
    est_per_model_fold = {m: wall_meas * max(dims[m] / dim_meas, 0.5) for m in REST_MODELS}
    total_s = sum(est_per_model_fold.values()) * N_FOLD * len(SEED_MAP)
    est = {
        "measured_model": MEASURE_MODEL, "measured_dim": dim_meas,
        "measured_wall_s": wall_meas, "model_dims": dims,
        "estimated_per_model_fold_s": est_per_model_fold,
        "n_model_fold_total": len(REST_MODELS) * N_FOLD * len(SEED_MAP),
        "estimated_total_wall_s": total_s,
        "estimated_total_wall_hours": total_s / 3600.0,
        "estimated_total_wall_days": total_s / 86400.0,
        "abort_threshold_days": ABORT_DAYS,
        "exceeds_threshold": bool(total_s / 86400.0 > ABORT_DAYS),
        "peak_rss_gib": peak_rss_gib(),
        "scaling_note": ("RF 비용은 피처 차원에 대략 선형(후보 분할 탐색). 계측 모델 대비 "
                         "차원비로 스케일하되 하한 0.5× 를 둬 과소추정을 막았다. "
                         "계측·추정 시간은 결과-독립 계측치이며 통계량과 무관하다."),
    }
    logln(f"[I-4-0] 총 wall 추정 = {est['estimated_total_wall_hours']:.2f}h "
          f"({est['estimated_total_wall_days']:.3f}일) · 정지 임계 {ABORT_DAYS}일 · "
          f"초과 = {est['exceeds_threshold']}")
    dump_json(os.path.join(BASE_DIR, "measure_public.json"), est)
    if est["exceeds_threshold"]:
        logln("[I-4-0] ❌ 추정 wall 이 7일 초과 — 실행하지 않고 중단(docs/48 중단 조건)")
        flush_log()
        sys.exit(12)
    return est


# ═══════════════════════════════════════════════════════════════════════════
# I-4-1  본계산 (체크포인트 · 세션 분할 허용)
# ═══════════════════════════════════════════════════════════════════════════
CKPT_FIELDS = ["repeat", "model", "fold", "n_train", "n_test", "dim",
               "wall_s", "peak_rss_gib", "sha256_partial", "ts_kst", "session_seq"]


def env_fingerprint():
    import joblib
    import scipy
    import sklearn
    splits = {}
    for r in (1, 2, 3):
        sd = split_dir_of(r)
        for fn in sorted(os.listdir(sd)):
            p = os.path.join(sd, fn)
            if os.path.isfile(p):
                splits[f"rep{r}/{fn}"] = sha256_file(p)
    return {
        "python_version": sys.version.split()[0], "numpy": np.__version__,
        "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__, "pandas": pd.__version__,
        "ladder_freeze_sha256": sha256_file(
            os.path.join(ROOT, "v3_Multimodal", "config", "ladder_freeze.json")),
        "sap_manifest_sha256": sha256_file(
            os.path.join(ROOT, "experiments", "sap", "manifest.json")),
        "split_files_sha256": splits,
        "machine": platform.machine(),
        "os": f"{platform.system()} {platform.release()}",
    }


def ckpt_load():
    rows = []
    if not os.path.exists(CKPT):
        return rows
    with open(CKPT, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                break                   # 마지막 줄 불완전 → 유효 접두까지만 인수
            raise AssertionError(f"[checkpoint] {i + 1}번째 줄 파손 — 수동 확인 필요")
    keys = [(r["repeat"], r["model"], r["fold"]) for r in rows]
    dup = {k for k in keys if keys.count(k) > 1}
    assert not dup, f"[checkpoint] 중복 (rep, model, fold) {sorted(dup)[:5]} — 즉시 중단"
    return rows


def ckpt_append(rec):
    os.makedirs(SEALED_BASE, exist_ok=True)
    with open(CKPT, "a", encoding="utf-8") as f:
        f.write(json.dumps({k: rec.get(k) for k in CKPT_FIELDS}, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def partial_path(r, model, k):
    return os.path.join(PARTIAL_DIR, f"rep{r}_{model.replace('-', '')}_fold{k}.npy")


def stage_run(d, blocks):
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]
    os.makedirs(PARTIAL_DIR, exist_ok=True)

    fp_now = env_fingerprint()
    fp_match, fp_diff = True, []
    if os.path.exists(ENV_FP):
        fp_prev = json.load(open(ENV_FP))
        fp_diff = [k for k in fp_now if fp_prev.get(k) != fp_now[k]]
        fp_match = not fp_diff
    else:
        dump_json(ENV_FP, fp_now)
    done = ckpt_load()
    done_keys = {(r["repeat"], r["model"], r["fold"]) for r in done}
    session_seq = max((r.get("session_seq", 0) for r in done), default=0) + 1
    is_resume = bool(done)
    if is_resume:
        logln(f"[재개] 세션 #{session_seq} · 기완주 {len(done_keys)}/"
              f"{len(REST_MODELS) * N_FOLD * len(SEED_MAP)} · 환경지문 일치={fp_match} "
              f"{('차이=' + str(fp_diff)) if fp_diff else ''}")
        assert fp_match, f"[재개] 환경 지문 불일치 {fp_diff} — 중단"
        gate_c_settle("세션 재개 직전")

    guard_start = sealed_guard_snapshot()
    total = len(REST_MODELS) * N_FOLD * len(SEED_MAP)
    n_done_session = 0
    t_session = time.perf_counter()

    for r in (1, 2, 3):
        fr = fold_of_row_for(r, d["cid_order"])
        for model in REST_MODELS:
            gate_b_exclusive(f"rep{r}/{model}:before")
            for k in range(N_FOLD):
                if (r, model, k) in done_keys:
                    continue
                te = np.where(fr == k)[0]
                tr = np.where(fr != k)[0]
                t0 = time.perf_counter()
                leak, order = fit_fold(blocks, model, tr, d, N)
                P, dim = predict_fold(blocks, model, tr, te, Y)
                wall = time.perf_counter() - t0
                pp = partial_path(r, model, k)
                np.save(pp, P)
                rec = {"repeat": r, "model": model, "fold": k,
                       "n_train": int(len(tr)), "n_test": int(len(te)), "dim": dim,
                       "wall_s": wall, "peak_rss_gib": peak_rss_gib(),
                       "sha256_partial": sha256_file(pp), "ts_kst": now_kst(),
                       "session_seq": session_seq, "leak_rows": leak,
                       "blocks_fit": order}
                ckpt_append(rec)
                done_keys.add((r, model, k))
                n_done_session += 1
                logln(f"[본계산] rep{r} {model} fold{k} — train={len(tr)} test={len(te)} "
                      f"dim={dim} leak_rows=0 | wall {wall:.1f}s | 누계 "
                      f"{len(done_keys)}/{total} (수치 미기록 — redaction)")
            gate_b_exclusive(f"rep{r}/{model}:after")

    assert len(done_keys) == total, f"완주 {len(done_keys)} != {total}"
    logln(f"[본계산] 전 {total} (rep,model,fold) 완주 — 세션 #{session_seq} 신규 {n_done_session}건")

    # ── 반복별 OOF 조립 + 봉인 ──
    sealed_sha = {}
    metrics_by_rep = {}
    for r in (1, 2, 3):
        fr = fold_of_row_for(r, d["cid_order"])
        rd = run_dir_of(r)
        store = sap_redaction.SealedStore(rd)
        os.makedirs(store.sealed_dir, exist_ok=True)
        res, per_fold = {}, {}
        for model in REST_MODELS:
            oof = np.full((N, K), np.nan, dtype=np.float64)
            for k in range(N_FOLD):
                te = np.where(fr == k)[0]
                oof[te] = np.load(partial_path(r, model, k))
            assert not np.isnan(oof).any(), f"rep{r} {model} OOF NaN 존재"
            assert oof.shape == (EXPECT_N_DRUGS, EXPECT_N_PT), \
                f"rep{r} {model} shape {oof.shape}"
            fn = f"oof_{model}.npz"
            np.savez_compressed(os.path.join(store.sealed_dir, fn), oof=oof,
                                cid=np.array([int(c) for c in d["cid_order"]]), fold=fr)
            sealed_sha[f"rep{r}/{fn}"] = sha256_file(os.path.join(store.sealed_dir, fn))
            # 지표는 봉인 전용 — Δ·부호는 계산하지 않는다(docs/48 I-0-3).
            res[model] = sap_metrics.macro_ap(Y, oof, None)
            per_fold[model] = [sap_metrics.macro_ap(Y[fr == k], oof[fr == k], None)
                               for k in range(N_FOLD)]
        store.write_sealed("metrics_full.json", {
            "_warning": "SEALED — 성공판정(개봉) 전 열람 금지. Δ·부호 미산출(docs/48 I-0-3).",
            "step": f"블록 I — 확증 OOF 잔여 6모델 반복{r}(seed {SEED_MAP[r]})",
            "ts_kst": now_kst(),
            "estimand": "사전등록 §7 primary — global 양성≥10 PT(370) macro AP, eligible_pt=None",
            "models": REST_MODELS, "macro_ap": res, "per_fold_macro_ap": per_fold,
            "pt_columns": d["ycols"],
            "delta_not_computed": ("Δ·부호는 이 블록에서 산출하지 않는다. Holm family "
                                   "②③⑤⑥ 은 개봉 단계에서 consensus 위 bootstrap/sign-flip 으로 "
                                   "일괄 계산한다."),
        })
        sealed_sha[f"rep{r}/metrics_full.json"] = sha256_file(
            os.path.join(store.sealed_dir, "metrics_full.json"))
        metrics_by_rep[r] = {"n_models": len(REST_MODELS)}
        logln(f"[봉인] rep{r} — oof_*.npz {len(REST_MODELS)}종 + metrics_full.json 저장 "
              f"({os.path.relpath(store.sealed_dir, ROOT)})")

    guard_end = sealed_guard_snapshot()
    assert guard_end == guard_start, "sealed guard 변동 — 기존 산출물이 수정됐다"
    return {"total": total, "session_seq": session_seq,
            "n_done_this_session": n_done_session,
            "session_wall_s": time.perf_counter() - t_session,
            "sealed_sha256": sealed_sha, "env_fingerprint_match": fp_match,
            "sealed_guard_n_files": len(guard_start), "sealed_guard_unchanged": True}


# ═══════════════════════════════════════════════════════════════════════════
# I-0-4  consensus (SAP A8 방법A) — 기존 v3_consensus_rep123 과 **별도 디렉터리**
# ═══════════════════════════════════════════════════════════════════════════
def stage_consensus(d):
    Y = d["Ym"]
    K = Y.shape[1]
    t0 = time.perf_counter()
    store = sap_redaction.SealedStore(CONS_DIR)
    os.makedirs(store.sealed_dir, exist_ok=True)
    sealed_sha, res = {}, {}
    for model in REST_MODELS:
        seq = []
        for r in (1, 2, 3):
            p = os.path.join(run_dir_of(r), "_sealed", f"oof_{model}.npz")
            log_machine_read(os.path.join(run_dir_of(r), "_sealed"),
                             os.path.relpath(p, ROOT),
                             f"consensus 입력(rep{r} {model})", "블록 I consensus")
            with np.load(p) as z:
                seq.append(z["oof"])
        assert all(a.shape == (EXPECT_N_DRUGS, EXPECT_N_PT) for a in seq), "반복 OOF shape 불일치"
        cons = sap_consensus.build_consensus(seq)      # 방법A · 반복 순서 1→2→3 고정
        fn = f"consensus_{model}.npz"
        np.savez_compressed(os.path.join(store.sealed_dir, fn), consensus=cons,
                            cid=np.array([int(c) for c in d["cid_order"]]))
        sealed_sha[fn] = sha256_file(os.path.join(store.sealed_dir, fn))
        res[model] = {"macro_ap": sap_metrics.macro_ap(Y, cons, None),
                      "per_repeat": sap_consensus.repeat_macro_aps(
                          seq, Y, sap_metrics.macro_ap, None)}
        logln(f"[consensus] {model} — 반복 3개 산술평균(방법A) 봉인 저장 (수치 미기록)")
    store.write_sealed("metrics_full.json", {
        "_warning": "SEALED — 성공판정(개봉) 전 열람 금지. Δ·부호 미산출(docs/48 I-0-3).",
        "step": "블록 I — 잔여 6모델 consensus(반복1·2·3)", "ts_kst": now_kst(),
        "method": sap_consensus.CONSENSUS_METHOD,
        "models": REST_MODELS, "macro_ap": {m: res[m]["macro_ap"] for m in REST_MODELS},
        "per_repeat_macro_ap": {m: res[m]["per_repeat"] for m in REST_MODELS},
        "pt_columns": d["ycols"],
        "delta_not_computed": "Δ·부호 미산출 — 개봉 단계에서 일괄.",
    })
    sealed_sha["metrics_full.json"] = sha256_file(
        os.path.join(store.sealed_dir, "metrics_full.json"))
    wall = time.perf_counter() - t0
    logln(f"[consensus] 6모델 완료 — 별도 디렉터리 "
          f"{os.path.relpath(CONS_DIR, ROOT)} (기존 v3_consensus_rep123 불변) | wall {wall:.1f}s")
    return {"n_models": len(REST_MODELS), "method": sap_consensus.CONSENSUS_METHOD,
            "dir": os.path.relpath(CONS_DIR, ROOT), "sealed_sha256": sealed_sha,
            "wall_s": wall}


# ═══════════════════════════════════════════════════════════════════════════
# 공개 산출 (개수·해시·시간·메모리·게이트 PASS/FAIL 뿐)
# ═══════════════════════════════════════════════════════════════════════════
def write_public(g0, verify, measure, run, cons, gates):
    pub = {
        "_scope": ("블록 I 공개 요약 — 완주 개수·해시·시간·메모리·게이트 PASS/FAIL 뿐. "
                   "Δ·AP·CI·p·부호 전부 봉인(docs/48 I-0-3)."),
        "ts_kst": now_kst(),
        "spec": "docs/48_v3_rf_remaining_oof_prompt_for_vscode.md",
        "models": REST_MODELS, "models_reused_not_recomputed": REUSE_MODELS,
        "gate0": {"ladder_freeze_sha16": g0["ladder_freeze_sha16"],
                  "sap_manifest_sha16": g0["sap_manifest_sha16"],
                  "sap_version": g0["sap_version"],
                  "sap_n_modules_verified": g0["sap_n_modules_verified"],
                  "sap_modules_all_match": all(g0["sap_modules_match"].values()),
                  "pass": bool(g0["gate0_pass"])},
        "gates": gates,
        "inputs_sha256": verify["inputs"],
        "consistency_checks": verify["consistency_checks"],
        "equivalence_byte_identical": verify["equivalence"]["byte_identical"],
        "equivalence_detail": {k: v for k, v in verify["equivalence"].items()
                               if k in ("model", "repeat", "fold", "n_test_rows",
                                        "dim", "dtype", "leak_rows", "wall_s")},
        "measure": measure,
        "run": {k: v for k, v in run.items() if k != "sealed_sha256"},
        "n_completed_model_folds": run["total"],
        "sealed_sha256_oof": run["sealed_sha256"],
        "consensus": cons,
        "peak_rss_gib": peak_rss_gib(),
        "sealed_guard_n_files": run["sealed_guard_n_files"],
        "sealed_guard_unchanged": run["sealed_guard_unchanged"],
        "compute_conditions": {
            "blas_env": {k: os.environ.get(k) for k in
                         ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "rf_n_jobs": RF_KW["n_jobs"], "rf_random_state": RF_SEED,
            "note": "반복1·2·3 과 동일 조건(스레드 환경변수 미설정·병렬 인자 무변경)."},
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__,
                     "scipy": __import__("scipy").__version__,
                     "rdkit": __import__("rdkit").__version__,
                     "platform": platform.platform()},
        "not_performed": ["개봉(open_sealed)", "성공판정(rq*_decision)", "Holm/BH 다중성",
                          "TOST/SESOI", "bootstrap CI", "sign-flip", "p-value",
                          "Δ 산출", "부호 산출(emit_sign)", "RF_tuned 계산",
                          "GIN", "late-fusion", "interaction", "외부/temporal 검증",
                          "split·fold·seed 재추첨", "기존 sealed 수정", "네트워크",
                          "data/raw 변경", "git commit·push"],
        "open_sealed_calls": 0, "decision_functions_called": [],
        "multiplicity_applied": False, "emit_sign_called": False,
    }
    # 방어 assert — 공개 파일에 봉인 대상 키가 없어야 한다.
    blob = json.dumps(pub, ensure_ascii=False, default=native)
    parsed = json.loads(blob)

    def walk_keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from walk_keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk_keys(v)

    keys = set(walk_keys(parsed))
    bad = sorted(k for k in keys
                 if any(k == f or k.startswith(f) for f in FORBIDDEN_PUBLIC_KEYS))
    assert not bad, f"공개 파일에 봉인 대상 키 노출: {bad}"
    dump_json(os.path.join(BASE_DIR, "rest_public.json"), pub)
    logln(f"[공개] rest_public.json 기록 — 봉인 대상 키 검출 0 "
          f"(검사 {len(FORBIDDEN_PUBLIC_KEYS)}종, 키 {len(keys)}개 스캔)")
    return pub


# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["verify", "measure", "run", "consensus", "all"],
                    default="all")
    ap.add_argument("--viewer", default="vscode-claude(runner)")
    args = ap.parse_args()

    os.makedirs(BASE_DIR, exist_ok=True)
    logln("=" * 78)
    logln(f"[블록 I] stage={args.stage} — 확증 RF 사다리 잔여 6모델 OOF "
          f"({' · '.join(REST_MODELS)}). Δ·AP·CI·p·**부호** 전부 봉인.")

    gates = {}
    gates["A_entry"] = gate_a_load("블록 I 진입")
    gates["B_start"] = gate_b_exclusive("블록 I 시작")
    gates["prelook"] = gate_prelook_recorded()
    g0 = gate0_verify()

    d = load_frozen()
    logln(f"[data] N={len(d['cid_order'])} PT={d['Ym'].shape[1]} "
          f"(동결 master_X/master_Y 읽기 전용)")
    blocks = make_blocks(d)

    verify = measure = run = cons = None
    if args.stage in ("verify", "all"):
        verify = stage_verify(d, blocks, g0)
        dump_json(os.path.join(BASE_DIR, "_verify_state.json"), verify)
    else:
        p = os.path.join(BASE_DIR, "_verify_state.json")
        verify = json.load(open(p)) if os.path.exists(p) else None

    if args.stage in ("measure", "all"):
        assert verify and verify["equivalence"]["byte_identical"], \
            "I-2 바이트 동일성 미확인 — 계측·본계산 금지"
        measure = stage_measure(d, blocks, verify)
    else:
        p = os.path.join(BASE_DIR, "measure_public.json")
        measure = json.load(open(p)) if os.path.exists(p) else None

    if args.stage in ("run", "all"):
        assert verify and verify["equivalence"]["byte_identical"], \
            "I-2 바이트 동일성 미확인 — 본계산 금지"
        assert measure and not measure["exceeds_threshold"], \
            "I-4-0 계측 미수행 또는 7일 초과 — 본계산 금지"
        run = stage_run(d, blocks)
        dump_json(os.path.join(BASE_DIR, "_run_state.json"), run)
    else:
        p = os.path.join(BASE_DIR, "_run_state.json")
        run = json.load(open(p)) if os.path.exists(p) else None

    if args.stage in ("consensus", "all"):
        assert run and run["total"] == len(REST_MODELS) * N_FOLD * len(SEED_MAP), \
            "본계산 미완주 — consensus 금지"
        cons = stage_consensus(d)
        dump_json(os.path.join(BASE_DIR, "_consensus_state.json"), cons)
    else:
        p = os.path.join(BASE_DIR, "_consensus_state.json")
        cons = json.load(open(p)) if os.path.exists(p) else None

    gates["B_end"] = gate_b_exclusive("블록 I 종료")
    if all(x is not None for x in (verify, measure, run, cons)):
        pub = write_public(g0, verify, measure, run, cons, gates)
        append_first_look({
            "ts_kst": now_kst(), "viewer": args.viewer, "step": "블록 I (§13-3/13-5 확장)",
            "block": "I — 확증 RF 사다리 잔여 6모델 OOF", "status": "completed",
            "models": REST_MODELS, "repeats": [1, 2, 3], "seeds": [201, 202, 203],
            "delta_sign": None,
            "delta_sign_note": ("Δ·부호를 산출하지도 공개하지도 않았다(docs/48 I-0-3). "
                                "②③⑤⑥ 부호는 등록에 없는 추가 노출이므로 전량 봉인."),
            "sealed_sha256": {**run["sealed_sha256"], **cons["sealed_sha256"]},
            "runner_asserts_passed": {
                "g0_freeze": True,
                "byte_identity_M2b_fold0": bool(verify["equivalence"]["byte_identical"]),
                "leak_rows_zero_all_models": True,
                "oof_shape_1092x370_no_nan": True,
                "rf_seed42_all_folds": True,
                "sealed_guard_unchanged": bool(run["sealed_guard_unchanged"]),
                "open_sealed_zero": True, "emit_sign_not_called": True,
                "decision_functions_not_called": True},
            "confirmatory": "Y",
            "note": ("확증 조회 = Y(값 미열람) — 잔여 6모델 OOF 를 생성하고 기존 M1b/M2b sealed 를 "
                     "machine_read 로 대조했다. open_sealed 0건 · Δ·AP·CI·p·부호 공개 0."),
        })
        print("\n" + "=" * 78)
        print("=== 블록 I 요약(개수·해시·게이트만) ===")
        print(f"완주 (rep,model,fold) = {pub['n_completed_model_folds']}")
        print(f"봉인 OOF 파일 = {len(run['sealed_sha256'])}종 · "
              f"consensus = {len(cons['sealed_sha256'])}종")
        print(f"바이트 동일성(M2b rep1 fold0) = {pub['equivalence_byte_identical']}")
        print(f"sealed guard {pub['sealed_guard_n_files']}종 불변 = "
              f"{pub['sealed_guard_unchanged']}")
        print("Δ·AP·CI·p·부호 = 전량 봉인 (공개 0)")
    flush_log()


if __name__ == "__main__":
    with ComputeLock(script="confirmatory_oof_rest.py", role="runner"):
        main()
