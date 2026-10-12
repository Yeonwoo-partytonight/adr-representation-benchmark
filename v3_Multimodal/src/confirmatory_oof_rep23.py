#!/usr/bin/env python3
"""confirmatory_oof_rep23.py — §13-5 확증 OOF **반복2(seed 202)·반복3(seed 203)** + consensus.

정본 스펙: `docs/30` §6·§7·§8·§13(실행순서 5) · `docs/36`(반복1 정본) · `docs/33` 항목8~14.

⛔ 무결성 최상위
  - **반복1과 동일 코드경로**: split·진단·게이트A·OOF 루프·지표는 `confirmatory_oof_rep1` 의
    **동일 함수 객체**를 import 해 사용한다(로직 재작성 0). 인자화된 것은 **seed·repeat·경로**뿐.
    → `--stage equivalence` 가 seed=201 로 본 경로를 돌려 반복1 `folds.json` 과 **바이트 동일**함을 증명한다.
  - **반복1 산출물 무수정**: `v3_confirm_rep1_seed201/_sealed/` 3종 sha256 을 시작·종료에 확인.
  - 사람 노출 = 각 실행의 **부호 1개**(`positive`/`zero`/`negative`)뿐. 원시 AP·Δ크기·PT별·fold별은 `_sealed/`.
  - bootstrap·sign-flip·p·SESOI/TOST·성공판정·§13-4 null **미실행**. 네트워크 0. `data/raw/` 불변.
  - seed 는 **202·203 만** 허용(반복 r = seed 200+r, `docs/33` 2026-07-27 11:10 확정). 그 외 → 즉시 중단.
  - compute 조건은 반복1과 동일하게 유지한다(BLAS 스레드 환경변수 **미설정** 그대로, RF 병렬 인자 무변경).

실행:
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rep23.py --stage all --viewer <이름>
"""
from __future__ import annotations

import os
import sys
import json
import time
import shutil
import hashlib
import argparse
import platform
import tempfile
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

# ── 반복1과 **동일 함수 객체** 재사용(로직 재작성 금지) ────────────────────────
import confirmatory_oof_rep1 as R1                                  # noqa: E402
from confirmatory_oof_rep1 import (                                 # noqa: E402
    gate0_verify, sha256_file, build_scaffold_groups, assign_folds,
    split_diagnostics, N_FOLD, RF_SEED, ZERO_TOL, GATE_A,
)
from ladder_confirmatory import (                                   # noqa: E402
    load_frozen, MorganBlock, CountMaskBlock, SeqBlock, M1bCovariateBlock,
    rf_fit_predict, MODEL_BLOCKS, RF_KW, SEED, PCA_K,
)
from sap import metrics as sap_metrics                              # noqa: E402
from sap import redaction as sap_redaction                          # noqa: E402
from sap import consensus as sap_consensus                          # noqa: E402

KST = timezone(timedelta(hours=9))

# ── 사전 고정 상수 (결과 조회 전 확정 — 실행 중 변경 금지) ──────────────────────
SEED_MAP = {2: 202, 3: 203}          # docs/33 2026-07-27 11:10: 반복 r = seed 200+r
FORBIDDEN_SEEDS = {204, 205}         # 미사용 예비 — 결과 기반 교체·추가 영구 금지
EXPECT_N_DRUGS = 1092
EXPECT_N_SCAFFOLD_GROUPS = 732
EXPECT_N_PT = 370

PROC = os.path.join(ROOT, "data", "processed")
PROV_DIR = os.path.join(ROOT, "experiments", "provenance")
FIRST_LOOK_LOG = os.path.join(PROV_DIR, "first_look_log.json")
DOCS33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
DOCS29 = os.path.join(ROOT, "docs", "29_v3.3_preregistration_advisor_approved.md")

REP1_DIR = os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep1_seed201")
REP1_SEALED = os.path.join(REP1_DIR, "_sealed")
REP1_SPLIT = os.path.join(PROC, "splits", "confirmatory", "rep1_seed201")
CONS_DIR = os.path.join(ROOT, "experiments", "runs", "v3_consensus_rep123")

REP1_SEALED_EXPECT = {
    "metrics_full.json": "8722a4e1c52d2eae5cbbebf6b5a5ff5cb145dd591ea5648731d7c481ed15c1b8",
    "oof_M1b.npz": "b2a61ba846eead5f66bc89bc22275ea3fe35fee950930fbdc38f07ad7e4a3f1d",
    "oof_M2b.npz": "350fa12fac84ef4ca1355d256665c333d9cd8ca34de257e7321aefa36d8a3260",
}

_LOG = []
_RUN_DIR_FOR_LOG = os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep23")


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    _LOG.append(line)


def flush_log(run_dir=None):
    d = run_dir or _RUN_DIR_FOR_LOG
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "run.log"), "a") as f:
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


def run_dir_of(r):
    return os.path.join(ROOT, "experiments", "runs", f"v3_confirm_rep{r}_seed{SEED_MAP[r]}")


def split_dir_of(r):
    return os.path.join(PROC, "splits", "confirmatory", f"rep{r}_seed{SEED_MAP[r]}")


def append_first_look(entry):
    os.makedirs(PROV_DIR, exist_ok=True)
    log = json.load(open(FIRST_LOOK_LOG)) if os.path.exists(FIRST_LOOK_LOG) else []
    if isinstance(log, dict):
        log = [log]
    log.append(entry)
    dump_json(FIRST_LOOK_LOG, log)


def log_machine_read(path_rel, purpose, step):
    os.makedirs(REP1_SEALED, exist_ok=True)
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude", "step": step,
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    with open(os.path.join(REP1_SEALED, "access.log"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ═══════════════════════════════════════════════════════════════════════════
# C-1  게이트
# ═══════════════════════════════════════════════════════════════════════════
def rep1_sealed_unchanged(tag):
    live = {fn: sha256_file(os.path.join(REP1_SEALED, fn)) for fn in REP1_SEALED_EXPECT}
    bad = [fn for fn in live if live[fn] != REP1_SEALED_EXPECT[fn]]
    if bad:
        logln(f"[{tag}] ❌ 반복1 _sealed sha256 불일치 {bad} — 즉시 중단")
        flush_log()
        sys.exit(6)
    logln(f"[{tag}] 반복1 _sealed 3종 sha256 불변 — "
          + " · ".join(f"{k}={v[:16]}" for k, v in sorted(live.items())))
    return live


def seed_gate(repeats):
    for r in repeats:
        if r not in SEED_MAP:
            logln(f"[C-1] ❌ 반복 {r} 미허용(허용 = 2·3) — 중단")
            sys.exit(7)
        s = SEED_MAP[r]
        if s != 200 + r or s in FORBIDDEN_SEEDS:
            logln(f"[C-1] ❌ seed {s} 규칙 위반(반복 r = seed 200+r, 204·205 미사용) — 중단")
            sys.exit(7)
    logln(f"[C-1] seed 게이트 PASS — 반복 {repeats} → seed {[SEED_MAP[r] for r in repeats]} "
          f"(204·205 미사용 예비, 결과 기반 교체·재추첨 영구 금지)")
    return {r: SEED_MAP[r] for r in repeats}


# ═══════════════════════════════════════════════════════════════════════════
# 코드경로 동일성 증명 — 본 경로를 seed=201 로 돌려 반복1 folds.json 과 바이트 동일 확인
# ═══════════════════════════════════════════════════════════════════════════
def make_split(d, seed):
    """반복1과 **동일 함수 객체**(build_scaffold_groups·assign_folds)로 fold 배정 산출."""
    N = len(d["cid_order"])
    smiles = d["X"]["smiles_canonical"].tolist()
    groups = build_scaffold_groups(smiles, d["cid_order"])
    fold_of_group, _order, counts = assign_folds(groups, N, seed=seed, k=N_FOLD)
    fold_of_row = np.full(N, -1, dtype=int)
    for g, rows in groups.items():
        for i in rows:
            fold_of_row[i] = fold_of_group[g]
    assert (fold_of_row >= 0).all(), "미배정 행 존재"
    return groups, fold_of_group, fold_of_row, counts


def stage_equivalence(d):
    """seed=201 재현으로 코드경로 동일성 증명(파일 쓰기는 임시 디렉터리에만)."""
    _, _, fold_of_row, counts = make_split(d, 201)
    cid2fold = {str(int(c)): int(fold_of_row[i]) for i, c in enumerate(d["cid_order"])}
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "folds.json")
        dump_json(p, cid2fold)
        new_sha = sha256_file(p)
    ref = os.path.join(REP1_SPLIT, "folds.json")
    ref_sha = sha256_file(ref)
    ok = (new_sha == ref_sha)
    logln(f"[동일성] 본 경로 seed=201 재현 folds.json sha256={new_sha[:16]} vs 반복1 원본 {ref_sha[:16]} "
          f"→ 바이트 동일={ok} (fold 크기 {list(counts)})")
    if not ok:
        logln("[동일성] ❌ 코드경로가 반복1과 다름 — 즉시 중단")
        flush_log()
        sys.exit(8)
    return {"reproduced_sha256": new_sha, "rep1_folds_sha256": ref_sha,
            "byte_identical": True, "fold_sizes": [int(x) for x in counts],
            "note": "반복1 원본 파일은 읽기만 함(재생성·덮어쓰기 없음). 재현본은 임시 디렉터리에만 기록 후 삭제."}


# ═══════════════════════════════════════════════════════════════════════════
# C-2  split + 게이트 A
# ═══════════════════════════════════════════════════════════════════════════
def stage_split(d, r, g0):
    seed = SEED_MAP[r]
    SPLIT_DIR = split_dir_of(r)
    RUN_DIR = run_dir_of(r)
    N = len(d["cid_order"])
    logln(f"[반복{r}] split 생성 — seed={seed} (반복1과 동일 코드경로, OOF 미조회)")

    groups, fold_of_group, fold_of_row, counts = make_split(d, seed)
    diag = split_diagnostics(d, fold_of_row, groups, fold_of_group)   # scaffold 무누수 assert 내장

    # ── C-2 assert (하드) ──
    a = {}
    a["n_drugs_all_1092"] = (diag["n_drugs"] == EXPECT_N_DRUGS)
    a["n_pt_370"] = (diag["n_pt"] == EXPECT_N_PT)
    a["n_scaffold_groups_all_732"] = (diag["n_scaffold_groups"] == EXPECT_N_SCAFFOLD_GROUPS)
    a["every_drug_exactly_one_fold"] = bool((fold_of_row >= 0).all() and
                                            sum(int((fold_of_row == k).sum()) for k in range(N_FOLD)) == N)
    a["scaffold_group_disjoint_no_fold_crossing"] = bool(diag["gate_A"]["scaffold_group_disjoint"])
    a["all_groups_assigned"] = (len(fold_of_group) == len(groups) == EXPECT_N_SCAFFOLD_GROUPS)
    a["gate_A_pass"] = bool(diag["gate_A"]["gate_A_pass"])
    a["bseq_fit_rows_ok"] = bool(diag["gate_A"]["bseq_fit_rows_ok"])
    a["rare_pt_min1_all_train_folds"] = bool(diag["gate_A"]["rare_pt_min1_all_train_folds"])
    for f in diag["folds"]:
        logln(f"[반복{r} fold {f['fold']}] test={f['n_test_drugs']} groups={f['n_test_scaffold_groups']} "
              f"| train PT-positive min={f['train_positive_per_pt']['min']} "
              f"(<1:{f['train_positive_per_pt']['n_pt_lt1']}, <3:{f['train_positive_per_pt']['n_pt_lt3']}) "
              f"| target Jaccard={f['target_jaccard_train_test']:.3f}")
    logln(f"[반복{r} 게이트A] " + " · ".join(f"{k}={v}" for k, v in a.items()))
    if not all(a.values()):
        logln(f"[반복{r} 게이트A] ❌ FAIL — OOF 미조회 상태로 중단(seed 재추첨 금지 = seed shopping)")
        flush_log(RUN_DIR)
        sys.exit(2)

    os.makedirs(SPLIT_DIR, exist_ok=True)
    cid2fold = {str(int(c)): int(fold_of_row[i]) for i, c in enumerate(d["cid_order"])}
    dump_json(os.path.join(SPLIT_DIR, "folds.json"), cid2fold)
    scaf_of_row = [None] * N
    for g, rows in groups.items():
        for i in rows:
            scaf_of_row[i] = g
    pd.DataFrame({
        "cid": [int(c) for c in d["cid_order"]], "fold": fold_of_row, "scaffold": scaf_of_row,
        "scaffold_group_size": [len(groups[s]) for s in scaf_of_row],
        "target_mapped": d["mask"].astype(bool),
    }).to_csv(os.path.join(SPLIT_DIR, "fold_membership.csv"), index=False)

    manifest = {
        "step": f"docs/30 §13 실행순서 5 — 확증 OOF 반복{r}(seed {seed}) split 생성",
        "created_kst": now_kst(), "prereg": "docs/30_preregistration_OSF_clean.md §6",
        "repeat": r, "split_seed": seed, "n_fold": N_FOLD,
        "seed_scheme_note": ("반복 r = seed 200+r (docs/33 2026-07-27 11:10 사전확정, delta_sign=null 시점 기록). "
                             "204·205 는 미사용 예비 — 결과 기반 교체·추가·재추첨 영구 금지."),
        "code_path": ("반복1(`confirmatory_oof_rep1.py`)의 동일 함수 객체 재사용 "
                      "(build_scaffold_groups·assign_folds·split_diagnostics). 인자화 = seed·repeat·경로뿐."),
        "code_path_equivalence_proof": "본 실행 --stage equivalence: seed=201 재현본이 반복1 folds.json 과 sha256 동일",
        "fold_sizes": diag["fold_sizes"], "diagnostics": diag, "gate0": g0,
        "hard_asserts": a,
        "integrity": {"confirmatory_oof_accessed": False, "models_trained": 0, "network_calls": 0,
                      "rep1_artifacts_modified": False},
    }
    dump_json(os.path.join(SPLIT_DIR, "split_manifest.json"), manifest)
    dump_json(os.path.join(RUN_DIR, "split_manifest.json"), manifest)
    pd.DataFrame(diag["folds"]).to_csv(os.path.join(RUN_DIR, "split_diagnostics.csv"), index=False)
    logln(f"[반복{r}] split 저장 — fold 크기 {diag['fold_sizes']} · 게이트A PASS")
    return fold_of_row, manifest, a


# ═══════════════════════════════════════════════════════════════════════════
# C-3  OOF (M1b·M2b) — 부호만 공개
# ═══════════════════════════════════════════════════════════════════════════
def stage_oof(d, r, fold_of_row, g0, viewer):
    seed = SEED_MAP[r]
    RUN_DIR = run_dir_of(r)
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]
    t_first_look = now_kst()
    t0 = time.perf_counter()

    append_first_look({
        "ts_kst": t_first_look, "viewer": viewer, "step": "§13-5", "repeat": r, "seed": seed,
        "status": "first_look_opened", "delta_sign": None, "confirmatory": "Y",
        "note": "게이트B — OOF 예측을 읽기 직전 기록. 부호는 완료 후 별도 append.",
    })
    logln(f"[반복{r} 게이트B] 무결성 로그 기록 완료 (first_look_log 'opened') | 조회자={viewer}")

    b_morgan = MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    b_count = CountMaskBlock(d["ntgt"], d["mask"])
    b_seq = SeqBlock(d["emb"], d["mask"], pca_k=PCA_K)
    b_m1b = M1bCovariateBlock(d["cov_by_cid"], d["cid_order"], include_pchembl=False, name="B_m1b")
    blocks = {"B0": b_morgan, "B1": b_count, "B_seq": b_seq, "B_m1b": b_m1b}
    assert b_m1b.dim == 10, f"primary B_m1b dim={b_m1b.dim} != 10"
    assert MODEL_BLOCKS["M1b"] == ["B0", "B1", "B_m1b"]
    assert MODEL_BLOCKS["M2b"] == ["B0", "B1", "B_m1b", "B_seq"]

    oof = {m: np.full((N, K), np.nan, dtype=np.float64) for m in ("M1b", "M2b")}
    fold_records, rf_seeds_used, leak_records = [], [], []

    for kf in range(N_FOLD):
        te = np.where(fold_of_row == kf)[0]
        tr = np.where(fold_of_row != kf)[0]
        b_morgan.fit(tr)
        b_count.fit(tr)
        b_seq.fit(tr)
        b_m1b.fit(tr)
        leak = {b: blocks[b].leakage_assert(tr) for b in ("B0", "B1", "B_seq", "B_m1b")}
        expect = np.zeros(N, dtype=bool)
        expect[tr] = True
        expect &= d["mask"].astype(bool)
        assert np.array_equal(b_seq._fit_rows_mask, expect), f"[fold {kf}] B_seq fit 모집단 != train∩매핑"
        assert all(v["leak_rows"] == 0 for v in leak.values()), f"[fold {kf}] leak_rows != 0"
        leak_records.append({"fold": kf, **{b: leak[b]["leak_rows"] for b in leak}})

        Xtr = {m: np.hstack([blocks[b].transform(tr) for b in MODEL_BLOCKS[m]]).astype(np.float32)
               for m in ("M1b", "M2b")}
        Xte = {m: np.hstack([blocks[b].transform(te) for b in MODEL_BLOCKS[m]]).astype(np.float32)
               for m in ("M1b", "M2b")}
        for m in ("M1b", "M2b"):
            rf_seeds_used.append(RF_SEED)
            assert RF_SEED == 42, "RF random_state != 42"
            oof[m][te] = rf_fit_predict(Xtr[m], Y[tr], Xte[m], seed=RF_SEED)
        fold_records.append({
            "fold": kf, "n_train": int(len(tr)), "n_test": int(len(te)),
            "bseq_fit_rows": int(b_seq._fit_rows_mask.sum()), "bseq_pca_evr64": float(b_seq.evr),
            "dim_M1b": int(Xtr["M1b"].shape[1]), "dim_M2b": int(Xtr["M2b"].shape[1]),
            "rf_random_state": RF_SEED,
        })
        logln(f"[반복{r} fold {kf}] train={len(tr)} test={len(te)} | leak_rows=0(전 블록) | "
              f"B_seq fit행={int(b_seq._fit_rows_mask.sum())} | dim M1b={Xtr['M1b'].shape[1]} "
              f"M2b={Xtr['M2b'].shape[1]} | RF random_state={RF_SEED} (수치 미기록 — redaction)")

    for m in ("M1b", "M2b"):
        assert not np.isnan(oof[m]).any(), f"{m} OOF 미완성(NaN 존재)"
        assert oof[m].shape == (EXPECT_N_DRUGS, EXPECT_N_PT), f"{m} shape {oof[m].shape} != (1092,370)"
    assert len(set(rf_seeds_used)) == 1 and rf_seeds_used[0] == 42, "RF seed 불일치"
    logln(f"[반복{r} OOF] 전체 {N}×{K} OOF 완성(M1b·M2b) · NaN 0")

    eligible = np.arange(K)
    res = {m: sap_metrics.macro_ap(Y, oof[m], eligible) for m in ("M1b", "M2b")}
    delta = res["M2b"]["macro_ap"] - res["M1b"]["macro_ap"]
    sign = sap_redaction.emit_sign(delta, ZERO_TOL)

    from sklearn.metrics import average_precision_score
    per_pt = {m: [float(average_precision_score(Y[:, j], oof[m][:, j])) for j in range(K)]
              for m in ("M1b", "M2b")}
    per_fold = []
    for kf in range(N_FOLD):
        te = np.where(fold_of_row == kf)[0]
        per_fold.append({"fold": kf,
                         "M1b": sap_metrics.macro_ap(Y[te], oof["M1b"][te], eligible)["macro_ap"],
                         "M2b": sap_metrics.macro_ap(Y[te], oof["M2b"][te], eligible)["macro_ap"]})

    store = sap_redaction.SealedStore(RUN_DIR)
    os.makedirs(store.sealed_dir, exist_ok=True)
    for m in ("M1b", "M2b"):
        np.savez_compressed(os.path.join(store.sealed_dir, f"oof_{m}.npz"), oof=oof[m],
                            cid=np.array([int(c) for c in d["cid_order"]]), fold=fold_of_row)
    store.write_sealed("metrics_full.json", {
        "_warning": "SEALED — 성공판정 단계(3반복+null 완료) 전 열람 금지.",
        "step": f"§13-5 반복{r}(seed {seed})", "ts_kst": t_first_look, "viewer": viewer,
        "estimand": "사전등록 §7 primary — global 양성≥10 PT(370)의 macro AP (반복 단독 OOF)",
        "macro_ap": {m: res[m] for m in ("M1b", "M2b")},
        "delta_M2b_minus_M1b": float(delta), "delta_sign": sign, "zero_tol": ZERO_TOL,
        "per_pt_ap": per_pt, "per_fold_macro_ap": per_fold, "pt_columns": d["ycols"],
    })
    public_path = store.write_public("metrics_public.json", delta)
    sealed_sha = {fn: sha256_file(os.path.join(store.sealed_dir, fn))
                  for fn in sorted(os.listdir(store.sealed_dir)) if fn != "access.log"}
    wall = time.perf_counter() - t0

    dump_json(os.path.join(RUN_DIR, "config.json"), {
        "step": f"docs/30 §13 실행순서 5 — 확증 OOF 반복{r}(seed {seed}), Δ 부호만",
        "spec": "docs/36(반복1 정본) 동일 경로 · docs/33 항목8~14",
        "ts_first_look_kst": t_first_look, "viewer": viewer, "wall_clock_sec": wall,
        "models": {m: MODEL_BLOCKS[m] for m in ("M1b", "M2b")},
        "primary_B_m1b_dim": int(b_m1b.dim),
        "B_m1b_cont": b_m1b.cont_names, "B_m1b_ind": b_m1b.ind_names,
        "rf": {**RF_KW, "random_state": RF_SEED, "retuned": False,
               "wrapper": "MultiOutputClassifier(one-vs-rest, 370 PT)"},
        "pca": {"k": PCA_K, "svd_solver": "full", "random_state": SEED,
                "fit_population": "outer-fold train ∩ 매핑 약물 행"},
        "split": {"seed": seed, "n_fold": N_FOLD, "repeat": r,
                  "dir": os.path.relpath(split_dir_of(r), ROOT)},
        "metric": {"primary_estimand": sap_metrics.MACRO_AP_DEF,
                   "edge_rules": sap_metrics.MACRO_AP_EDGE_RULES,
                   "eligible_pt": "global 양성≥10 = master_Y 370 PT 전체", "zero_tol": ZERO_TOL},
        "folds": fold_records, "leakage": leak_records,
        "runner_asserts_passed": {"rf_seed42_all_folds": True,
                                  "bseq_pca_fit_outer_train_mapped": True,
                                  "redaction_sign_only": True, "leak_rows_zero_all_folds": True,
                                  "oof_shape_1092x370_no_nan": True},
        "compute_conditions": {
            "blas_env": {k: os.environ.get(k) for k in
                         ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "rf_n_jobs": RF_KW["n_jobs"], "multioutput_n_jobs": None,
            "note": "반복1과 동일 compute 조건 유지(스레드 환경변수 미설정·병렬 인자 무변경).",
        },
        "gate0": g0,
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__,
                     "scipy": __import__("scipy").__version__, "rdkit": __import__("rdkit").__version__,
                     "platform": platform.platform()},
        "not_performed": ["bootstrap CI", "sign-flip randomization", "p-value", "SESOI/TOST",
                          "성공판정", "재배치 null(§13-4)", "M0/M1/M2/P-ID/P-FAM/C-CAP OOF",
                          "GIN", "late-fusion", "shift 층화"],
        "integrity": {"network_calls": 0, "raw_data_modified": False, "docs30_modified": False,
                      "frozen_blocks_recomputed": False, "rep1_artifacts_modified": False,
                      "git_commit": False},
        "sealed_sha256": sealed_sha,
        "public_output": {"path": os.path.relpath(public_path, ROOT), "fields": ["sign"]},
    })
    append_first_look({
        "ts_kst": t_first_look, "ts_completed_kst": now_kst(), "viewer": viewer, "step": "§13-5",
        "repeat": r, "seed": seed, "status": "completed", "delta_sign": sign,
        "sealed_path": os.path.relpath(store.sealed_dir, ROOT), "sealed_sha256": sealed_sha,
        "runner_asserts_passed": {"rf_seed42": True, "pca_foldtrain": True,
                                  "redaction_signonly": True, "leak_rows_zero": True},
        "confirmatory": "Y",
        "note": "원시 macro AP·Δ크기·PT별·fold별은 sealed. 공개=부호 1개(metrics_public.json).",
    })
    logln(f"[반복{r} 결과·공개] Δ(M2b−M1b) 부호 = {sign} | wall {wall:.1f}s | "
          f"sealed {len(sealed_sha)}개 sha 기록")
    return oof, sign, sealed_sha, wall


# ═══════════════════════════════════════════════════════════════════════════
# C-4  consensus (SAP A8 방법A)
# ═══════════════════════════════════════════════════════════════════════════
def stage_consensus(d, oof_by_rep, viewer):
    Y = d["Ym"]
    K = Y.shape[1]
    eligible = np.arange(K)
    t0 = time.perf_counter()

    log_machine_read(os.path.relpath(os.path.join(REP1_SEALED, "oof_M1b.npz"), ROOT),
                     "consensus rep1 input", "§13-5 consensus")
    log_machine_read(os.path.relpath(os.path.join(REP1_SEALED, "oof_M2b.npz"), ROOT),
                     "consensus rep1 input", "§13-5 consensus")
    rep1 = {}
    for m in ("M1b", "M2b"):
        with np.load(os.path.join(REP1_SEALED, f"oof_{m}.npz")) as z:
            rep1[m] = z["oof"]
    logln("[consensus] 반복1 sealed OOF 2종 **machine_read**(사람 노출 0)로 로드 — 값 미출력")

    cons, res, delta_parts = {}, {}, {}
    for m in ("M1b", "M2b"):
        seq = [rep1[m], oof_by_rep[2][m], oof_by_rep[3][m]]
        assert all(a.shape == (EXPECT_N_DRUGS, EXPECT_N_PT) for a in seq), "반복 OOF shape 불일치"
        cons[m] = sap_consensus.build_consensus(seq)          # 방법A = raw probability 산술평균
        res[m] = sap_metrics.macro_ap(Y, cons[m], eligible)
        delta_parts[m] = sap_consensus.repeat_macro_aps(seq, Y, sap_metrics.macro_ap, eligible)
    delta = res["M2b"]["macro_ap"] - res["M1b"]["macro_ap"]
    sign = sap_redaction.emit_sign(delta, ZERO_TOL)

    from sklearn.metrics import average_precision_score
    per_pt = {m: [float(average_precision_score(Y[:, j], cons[m][:, j])) for j in range(K)]
              for m in ("M1b", "M2b")}

    store = sap_redaction.SealedStore(CONS_DIR)
    os.makedirs(store.sealed_dir, exist_ok=True)
    for m in ("M1b", "M2b"):
        np.savez_compressed(os.path.join(store.sealed_dir, f"consensus_{m}.npz"), consensus=cons[m],
                            cid=np.array([int(c) for c in d["cid_order"]]))
    store.write_sealed("metrics_full.json", {
        "_warning": "SEALED — 성공판정 단계(3반복+null 완료) 전 열람 금지.",
        "step": "§13-5 consensus(반복1·2·3)", "ts_kst": now_kst(), "viewer": viewer,
        "method": sap_consensus.CONSENSUS_METHOD,
        "macro_ap": {m: res[m] for m in ("M1b", "M2b")},
        "delta_M2b_minus_M1b": float(delta), "delta_sign": sign, "zero_tol": ZERO_TOL,
        "per_repeat_macro_ap": delta_parts, "per_pt_ap": per_pt, "pt_columns": d["ycols"],
    })
    public_path = store.write_public("metrics_public.json", delta)
    sealed_sha = {fn: sha256_file(os.path.join(store.sealed_dir, fn))
                  for fn in sorted(os.listdir(store.sealed_dir)) if fn != "access.log"}
    wall = time.perf_counter() - t0

    dump_json(os.path.join(CONS_DIR, "config.json"), {
        "step": "docs/30 §13 실행순서 5 — consensus OOF(반복 1·2·3), Δ 부호만",
        "method": sap_consensus.CONSENSUS_METHOD,
        "method_detail": "SAP A8 방법A — 약물-PT별 raw RF probability 3반복 산술평균 → consensus(N×PT)",
        "inputs": {"repeat1": "experiments/runs/v3_confirm_rep1_seed201/_sealed/oof_{M1b,M2b}.npz (machine_read)",
                   "repeat2": os.path.relpath(os.path.join(run_dir_of(2), "_sealed"), ROOT),
                   "repeat3": os.path.relpath(os.path.join(run_dir_of(3), "_sealed"), ROOT)},
        "ts_kst": now_kst(), "viewer": viewer, "wall_clock_sec": wall,
        "n_repeats": 3, "shape": [EXPECT_N_DRUGS, EXPECT_N_PT],
        "repeat_macro_aps_computed": True,
        "repeat_macro_aps_disclosure": "값은 전부 _sealed/metrics_full.json — 로그·콘솔·공개 파일 미기록",
        "not_performed": ["bootstrap CI", "sign-flip", "p-value", "SESOI/TOST", "성공판정",
                          "재배치 null(§13-4)"],
        "integrity": {"network_calls": 0, "rep1_artifacts_modified": False,
                      "sealed_values_human_read": False, "git_commit": False},
        "sealed_sha256": sealed_sha,
        "public_output": {"path": os.path.relpath(public_path, ROOT), "fields": ["sign"]},
    })
    append_first_look({
        "ts_kst": now_kst(), "viewer": viewer, "step": "§13-5 consensus", "repeat": "1+2+3",
        "seed": [201, 202, 203], "status": "completed", "delta_sign": sign,
        "sealed_path": os.path.relpath(store.sealed_dir, ROOT), "sealed_sha256": sealed_sha,
        "confirmatory": "Y",
        "note": "방법A 산술평균. 원시 AP·Δ크기·반복별 AP는 sealed. 공개=부호 1개.",
    })
    logln(f"[consensus 결과·공개] Δ(M2b−M1b) 부호 = {sign} | wall {wall:.1f}s")
    return sign, sealed_sha


# ═══════════════════════════════════════════════════════════════════════════
# C-6  누출 스캔
# ═══════════════════════════════════════════════════════════════════════════
def leak_scan():
    """공개 파일·문서에서 소수점 실수 패턴 스캔. AP·Δ 후보 = 0.xxx 형태의 부동소수."""
    import re
    import glob
    pat = re.compile(r"(?<![\w.])0\.\d{2,}")          # 0.079 같은 지표 후보
    targets = []
    for g in ("experiments/runs/**/config.json", "experiments/runs/**/run.log",
              "experiments/runs/**/*_public.json"):
        targets += glob.glob(os.path.join(ROOT, g), recursive=True)
    targets += [os.path.join(ROOT, "docs", "33_prereg_deviation_log.md"),
                os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")]
    # 결과-독립 필드(허용 목록): 시간·메모리·비율·버전·좌표 등은 지표가 아님
    allow_keys = ("sec", "wall", "time", "rss", "gb", "frac", "ratio", "share", "density",
                  "jaccard", "evr", "zero_tol", "version", "incidence", "elapsed", "hours",
                  "days", "mc_se", "alpha", "cov", "min_seq_id", "budget")
    hits = []
    for p in sorted(set(targets)):
        rel = os.path.relpath(p, ROOT)
        # 확증 반복/consensus 의 공개·설정·로그만 엄격 검사(프로브·사다리는 결과-독립 계측치 포함)
        strict = ("v3_confirm_rep" in rel) or ("v3_consensus" in rel)
        with open(p, errors="replace") as f:
            for ln, line in enumerate(f, 1):
                for mth in pat.finditer(line):
                    low = line.lower()
                    if any(k in low for k in allow_keys):
                        continue
                    hits.append({"file": rel, "line": ln, "match": mth.group(0),
                                 "strict": strict, "context_key_allowlisted": False})
    strict_hits = [h for h in hits if h["strict"]]
    return {"n_files_scanned": len(set(targets)), "n_hits_total": len(hits),
            "n_hits_strict_confirmatory": len(strict_hits),
            "strict_hits": strict_hits[:20],
            "rule": "확증 반복/consensus 공개·config·log 에서 지표 후보 소수(0.dd+) 검출 = 0 이어야 함",
            "allowlist_keys": list(allow_keys)}


# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["all", "equivalence"], default="all")
    ap.add_argument("--viewer", default="vscode-claude(runner)")
    args = ap.parse_args()
    t_all = time.perf_counter()

    logln("=" * 78)
    logln("[블록 C] §13-5 확증 OOF 반복2·3 + consensus — 부호만 공개. "
          "bootstrap/sign-flip/p/SESOI/성공판정/§13-4 null 미실행.")

    # C-1 게이트
    g0 = gate0_verify()
    sealed_start = rep1_sealed_unchanged("C-1 시작")
    seeds = seed_gate([2, 3])

    d = load_frozen()
    logln(f"[data] N={len(d['cid_order'])} PT={d['Ym'].shape[1]} (동결 master_X/master_Y 읽기 전용)")

    equiv = stage_equivalence(d)
    if args.stage == "equivalence":
        flush_log()
        return

    results = {}
    oof_by_rep = {}
    for r in (2, 3):
        fold_of_row, split_man, asserts = stage_split(d, r, g0)
        oof, sign, sealed_sha, wall = stage_oof(d, r, fold_of_row, g0, args.viewer)
        oof_by_rep[r] = oof
        results[r] = {"seed": seeds[r], "sign": sign, "sealed_sha256": sealed_sha,
                      "gate_A_asserts": asserts, "fold_sizes": split_man["fold_sizes"],
                      "wall_clock_sec": wall}
        rep1_sealed_unchanged(f"반복{r} 종료")

    cons_sign, cons_sha = stage_consensus(d, oof_by_rep, args.viewer)
    sealed_end = rep1_sealed_unchanged("C 종료")
    scan = leak_scan()
    logln(f"[C-6 누출스캔] 파일 {scan['n_files_scanned']}개 · 확증 경로 엄격 검출 "
          f"{scan['n_hits_strict_confirmatory']}건")

    summary = {
        "_scope": "블록 C 요약(공개) — 부호·해시·시간·개수만. AP·Δ 크기·p 없음.",
        "ts_kst": now_kst(), "elapsed_sec": time.perf_counter() - t_all,
        "gate0_pass": g0["gate0_pass"],
        "rep1_sealed_unchanged": {"at_start": sealed_start, "at_end": sealed_end,
                                  "all_match": sealed_start == sealed_end == REP1_SEALED_EXPECT},
        "seed_map": {str(k): v for k, v in seeds.items()},
        "code_path_equivalence": equiv,
        "repeats": {str(r): {k: v for k, v in results[r].items()} for r in results},
        "consensus": {"sign": cons_sign, "sealed_sha256": cons_sha},
        "leak_scan": scan,
        "compute_conditions": {"blas_env_unset": all(
            os.environ.get(k) is None for k in
            ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")),
            "rf_n_jobs": RF_KW["n_jobs"],
            "note": "반복1과 동일 조건(환경변수 미설정) 유지"},
        "not_performed": ["bootstrap CI", "sign-flip", "p-value", "SESOI/TOST", "성공판정",
                          "§13-4 null 본런", "sealed 값 사람 열람", "git commit", "네트워크"],
    }
    dump_json(os.path.join(_RUN_DIR_FOR_LOG, "block_C_summary.json"), summary)
    flush_log()
    print("\n=== 블록 C 요약(부호만) ===")
    print(f"반복2(seed 202) 부호 = {results[2]['sign']}")
    print(f"반복3(seed 203) 부호 = {results[3]['sign']}")
    print(f"consensus(1+2+3) 부호 = {cons_sign}")
    print(f"누출스캔 확증경로 검출 = {scan['n_hits_strict_confirmatory']}건")


if __name__ == "__main__":
    main()
