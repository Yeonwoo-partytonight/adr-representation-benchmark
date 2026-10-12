#!/usr/bin/env python3
"""confirmatory_latefusion.py — 블록 P: Holm ⑦ `RFseq − RF`(RQ7) late-fusion **arm 산출**.

정본 스펙: `docs/61_v3_late_fusion_prompt_for_vscode.md` (개정판 v2.1, 2026-08-06)
설계 확정본: `v3_Multimodal/config/post_interim_freeze_v1_0.json` → `holm7_late_fusion`
실행 동결  : `v3_Multimodal/config/holm7_latefusion_freeze.json` (블록 P-0-2 산출 — 수정 금지)

⛔ 무결성 최상위
  - **개봉 없음**: `SealedStore.open_sealed` 미호출 · `_sealed/` 값의 사람 판독형 출력 0.
  - **성공판정·다중성 없음**: `sap/decision.py` 의 `rq*_decision`·`holm`·`bh_fdr`·
    `tost_equivalence` 미호출(import 조차 하지 않는다).
  - **Δ·부호·λ 공개 없음**: `emit_sign` 미호출. Δ(ensemble − RF) 산출 0.
    λ 는 **결과-의존 선택량**이므로 값 자체를 봉인하고 공개에는 **격자 정의**만 적는다.
  - **기존 동결물 무수정**: `ladder_freeze.json`·`gin_*_freeze.json`·`post_interim_freeze_v1_0*` ·
    `rf_tuned_freeze.json`·`sap/*`·`docs/29`·`docs/30`·`docs/70`·`docs/71_*`·`docs/77` ·
    `ladder_confirmatory.py`·`confirmatory_oof_*.py`·`train_ladder.py`·`stratification_run.py`·
    `pid_stratification_run.py`. 기존 `_sealed/` 덮어쓰기 0(신규 디렉터리에만 쓴다).
  - split·fold·seed 재추첨 0(`folds.json` 판독만) · **내부 valid 재추첨 0**(동결 규칙 재현) ·
    네트워크 0 · `data/raw/` 변경 0 · git commit·push 0 · GIN 착수 0.

★ 원본 무수정 원칙 하의 **복사** (지시서 §P-4 — 리포트에 열거)
  `confirmatory_oof_rest.py` 의 게이트·로더·정합·봉인·기록 경로는 **import 재사용**한다.
  다음만 `REST_MODELS`/`MODEL_BLOCKS` 하드코딩에 막혀 최소 로직을 복사했다(원본 무수정):
    · `fit_fold`/`predict_fold` → `fit_blocks`/`rf_predict`
        사유: 두 함수 모두 `MODEL_BLOCKS[model]` 을 참조하는데 `p_seq` arm 은 동결 사다리
              모델이 아니다(블록 조합 `["B_seq"]`·`["B1","B_seq"]` 는 사다리에 없다).
    · `stage_run`/`stage_consensus`/`write_public`
        사유: `REST_MODELS` 순회 + `v3_confirm_rest*` 경로 하드코딩.
    · `sealed_guard_snapshot`
        사유: 원본은 6개 디렉터리 고정 목록. 지시서 §P-1-5 는 `experiments/runs/**/_sealed/**`
              **live glob 실측**을 기준선으로 요구한다(블록 O 와 동일 판단).
  내부 분할은 블록 R 의 동결 재현 함수(`record_block_R.inner_split`)를 **import 재사용**한다.

실행:
  .venv/bin/python3 v3_Multimodal/src/confirmatory_latefusion.py --stage verify
  .venv/bin/python3 v3_Multimodal/src/confirmatory_latefusion.py --stage measure
  .venv/bin/python3 v3_Multimodal/src/confirmatory_latefusion.py --stage run
  .venv/bin/python3 v3_Multimodal/src/confirmatory_latefusion.py --stage consensus
  .venv/bin/python3 v3_Multimodal/src/confirmatory_latefusion.py --stage all
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from compute_lock import (ComputeLock, gate_a_load,                      # noqa: E402
                          gate_b_exclusive, gate_c_settle)
# ── 기존 하네스 재사용(원본 무수정) ──────────────────────────────────────────
from confirmatory_oof_rep1 import gate0_verify, sha256_file              # noqa: E402
from confirmatory_oof_rest import (                                      # noqa: E402
    N_FOLD, SEED_MAP, EXPECT_N_DRUGS, EXPECT_N_PT, EXPECT_N_SCAFFOLD_GROUPS,
    RF_SEED, FORBIDDEN_PUBLIC_KEYS,
    now_kst, native, dump_json, peak_rss_gib, split_dir_of,
    read_fold_membership, fold_of_row_for, gate_inputs,
    log_machine_read, append_first_look,
)
from ladder_confirmatory import (                                        # noqa: E402
    load_frozen, MorganBlock, CountMaskBlock, SeqBlock, rf_fit_predict,
    MODEL_BLOCKS, FROZEN_MODELS, RF_KW, SEED, PCA_K,
)
import record_block_R as BR                                              # noqa: E402
from sap import consensus as sap_consensus                               # noqa: E402
from sap import metrics as sap_metrics                                   # noqa: E402
from sap import redaction as sap_redaction                               # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
# 사전 고정 상수 (결과 조회 전 확정 — 실행 중 변경 금지)
# ═══════════════════════════════════════════════════════════════════════════
RF_BLOCKS = ["B0"]                        # p_RF = M0 (Morgan-only)
SEQ_PRIMARY = ["B_seq"]                   # p_seq primary
SEQ_SENS = ["B1", "B_seq"]                # p_seq sensitivity (판정 미포함)
EQUIV_MODEL = "M0"
EQUIV_REP, EQUIV_FOLD = 1, 0
ABORT_DAYS = 7.0
N_UNITS = N_FOLD * len(SEED_MAP)          # 15 outer unit
N_FITS_PER_UNIT = 6                       # inner(rf, seq, seq_sens) + refit(rf, seq, seq_sens)
EXPECT_INNER_VALID = 97
EXPECT_INNER_TRAIN = (776, 777)
EXPECT_MAPPED = 847
EXPECT_UNMAPPED = 245

# λ 격자 — 정수 인덱스 k/20 생성(부동소수 누적 금지)
LAMBDA_GRID = [k / 20 for k in range(21)]
LAMBDA_HALF = 0.5

CONFIG_DIR = os.path.join(ROOT, "v3_Multimodal", "config")
LF_FREEZE = os.path.join(CONFIG_DIR, "holm7_latefusion_freeze.json")
RUNS = os.path.join(ROOT, "experiments", "runs")
BASE_DIR = os.path.join(RUNS, "v3_latefusion")
SEALED_BASE = os.path.join(BASE_DIR, "_sealed")
WORK_DIR = os.path.join(SEALED_BASE, "_partial")     # 원시 예측 → `_sealed/` 안(공개 경로 금지)
CKPT = os.path.join(SEALED_BASE, "checkpoint.jsonl")
ENV_FP = os.path.join(SEALED_BASE, "env_fingerprint.json")
CONS_DIR = os.path.join(RUNS, "v3_latefusion_consensus_rep123")
INNER_CHECK = os.path.join(RUNS, "v3_gin_inner_valid_freeze", "inner_split_check.json")
DOC33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")

OWN_PREFIXES = ("experiments/runs/v3_latefusion",)

ARM_FILES = ["oof_seq", "oof_ens", "oof_ens_half", "oof_seq_sens", "oof_ens_sens"]


def rest_sealed_of(r):
    return os.path.join(RUNS, f"v3_confirm_rest_rep{r}_seed{SEED_MAP[r]}", "_sealed")


def run_dir_of(r):
    return os.path.join(RUNS, f"v3_latefusion_rep{r}_seed{SEED_MAP[r]}")


_LOG = []


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    _LOG.append(line)


def flush_log():
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(os.path.join(BASE_DIR, "run.log"), "a", encoding="utf-8") as f:
        f.write("\n".join(_LOG) + "\n")
    _LOG.clear()


# ═══════════════════════════════════════════════════════════════════════════
# sealed guard (glob 실측판 — 복사, 사유는 모듈 docstring)
# ═══════════════════════════════════════════════════════════════════════════
def sealed_guard_snapshot():
    snap = {}
    for dirpath, _dn, filenames in os.walk(RUNS):
        if "_sealed" not in dirpath.split(os.sep):
            continue
        for fn in sorted(filenames):
            if fn == "access.log":
                continue
            p = os.path.join(dirpath, fn)
            snap[os.path.relpath(p, ROOT)] = sha256_file(p)
    return dict(sorted(snap.items()))


def assert_guard_unchanged(start, end, label):
    changed = [k for k in start if end.get(k) != start[k]]
    assert not changed, f"[{label}] 기존 봉인 산출물 변경/삭제 {len(changed)}건: {changed[:3]}"
    added = [k for k in end if k not in start]
    foreign = [k for k in added if not k.startswith(OWN_PREFIXES)]
    assert not foreign, f"[{label}] 본 블록 밖 봉인 신규 생성 {len(foreign)}건: {foreign[:3]}"
    return {"n_preexisting": len(start), "n_added_own": len(added), "n_foreign": 0,
            "preexisting_unchanged": True}


# ═══════════════════════════════════════════════════════════════════════════
# 게이트
# ═══════════════════════════════════════════════════════════════════════════
def gate_prelook_recorded():
    txt = open(DOC33, encoding="utf-8").read()
    assert "⑦ 기준 RF 선택에서 기각한 대안 — 보충 기록" in txt, \
        "[P-0-1] docs/33 보충 기록 기입 없음 — 착수 금지"
    logln("[P-0-1] docs/33 보충 기록 기입 확인 — 착수 허용")
    return {"supplement_recorded": True, "docs33_sha16": sha256_file(DOC33)[:16]}


def gate_block():
    st = json.load(open(os.path.join(CONFIG_DIR, "post_interim_freeze_v1_0.status.json"),
                        encoding="utf-8"))
    assert st["holm67_start_still_blocked_until_reply"] is False, \
        "holm67_start_still_blocked_until_reply == true → 보류"
    assert any("docs/61" in r for r in st["holm67_start_requires"]), \
        "holm67_start_requires 에 docs/61 개정 미열거"
    pi_sha = sha256_file(os.path.join(CONFIG_DIR, "post_interim_freeze_v1_0.json"))
    assert pi_sha[:16] == "502db732bd5e45cb", f"post_interim sha16 {pi_sha[:16]}"
    logln("[G-BLOCK] PASS — holm67_start_still_blocked_until_reply=False · "
          f"post_interim sha16={pi_sha[:16]}")
    return {"holm67_start_still_blocked_until_reply": False,
            "post_interim_sha256": pi_sha,
            "post_interim_status_sha256": sha256_file(
                os.path.join(CONFIG_DIR, "post_interim_freeze_v1_0.status.json"))}


def gate_holm_family():
    import ast
    src = open(os.path.join(HERE, "sap", "decision.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    node = next(n for n in tree.body
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", None) == "HOLM_FAMILY" for t in n.targets))
    labels = [ast.literal_eval(e) for e in node.value.elts]
    assert len(labels) == 7, f"HOLM_FAMILY {len(labels)} 라벨 (기대 7)"
    assert "RFseq-RF" in labels, "HOLM_FAMILY 에 RFseq-RF 부재"
    logln(f"[G-HOLM] PASS — decision.py:{node.lineno} · 7 라벨 · RFseq-RF 포함")
    return {"line": node.lineno, "n_labels": len(labels), "labels": labels}


def gate_g0_extra():
    """지시서 §P-1-2 의 G0 목록 중 `gate0_verify` 가 다루지 않는 4종 + 블록 O 신설 동결물."""
    exp = {"gin_seed_freeze.json": "10828447c6d33118",
           "gin_inner_valid_freeze.json": "038599c3e1576022",
           "gin_inner_valid_freeze.status.json": "bd329fefe613971f",
           "post_interim_freeze_v1_0.json": "502db732bd5e45cb",
           "rf_tuned_freeze.json": "c1ef6406fbb48b7f"}
    out = {}
    for fn, e16 in exp.items():
        s = sha256_file(os.path.join(CONFIG_DIR, fn))
        assert s[:16] == e16, f"[G0 FAIL] {fn} sha16 {s[:16]} != {e16}"
        out[fn] = s[:16]
    logln(f"[G0+] PASS — 동결 {len(exp)}종 sha16 일치(rf_tuned_freeze 포함 · 무수정 대조만)")
    return out


def gate_freeze_file():
    fz = json.load(open(LF_FREEZE, encoding="utf-8"))
    assert fz["holm_family_size"] == 7 and fz["success_criteria_changed"] is False
    assert fz["gin_start_still_blocked"] is True
    assert fz["arms"]["p_rf"]["blocks"] == RF_BLOCKS
    assert fz["arms"]["p_seq_primary"]["blocks"] == SEQ_PRIMARY
    assert fz["arms"]["p_seq_sensitivity"]["blocks"] == SEQ_SENS
    g = fz["lambda"]["grid"]
    assert (g["min"], g["max"], g["step"], g["n_points"]) == (0.0, 1.0, 0.05, 21)
    assert fz["arms"]["learner"]["hyperparameters_verbatim"]["n_estimators"] == \
        RF_KW["n_estimators"], "동결 하이퍼가 확증 RF 하네스와 다르다"
    assert fz["arms"]["learner"]["hyperparameters_verbatim"]["class_weight"] == \
        RF_KW["class_weight"]
    assert fz["predecessor"]["sha256"] == sha256_file(
        os.path.join(CONFIG_DIR, "post_interim_freeze_v1_0.json")), \
        "predecessor 해시가 live 와 불일치"
    logln(f"[동결] holm7_latefusion_freeze.json sha16 {sha256_file(LF_FREEZE)[:16]} 판독 — "
          "arm 3종·격자·하이퍼 assert PASS")
    return {"sha256": sha256_file(LF_FREEZE), "arms": list(fz["arms"].keys())}


def gate_no_existing_outputs():
    existing = []
    for r in (1, 2, 3):
        for fn in ARM_FILES:
            p = os.path.join(run_dir_of(r), "_sealed", f"{fn}.npz")
            if os.path.exists(p):
                existing.append(os.path.relpath(p, ROOT))
    for fn in ARM_FILES:
        p = os.path.join(CONS_DIR, "_sealed", f"consensus_{fn[4:]}.npz")
        if os.path.exists(p):
            existing.append(os.path.relpath(p, ROOT))
    assert not existing, f"⑦ 산출물이 이미 존재 — 덮어쓰기 금지: {existing}"
    return {"preexisting_latefusion_outputs": 0}


def gate_lambda_grid():
    """P-2-8 격자 정합 — 21점·중복 0·결손 0·부동소수 오차 0."""
    g = LAMBDA_GRID
    assert len(g) == 21, f"격자 {len(g)}점 != 21"
    assert len(set(g)) == 21, "격자 중복 존재"
    assert g[0] == 0.0 and g[-1] == 1.0, f"격자 끝점 {g[0]}, {g[-1]}"
    diffs = [round(b - a, 12) for a, b in zip(g, g[1:])]
    assert all(d == 0.05 for d in diffs), f"격자 간격 불균일: {sorted(set(diffs))}"
    assert LAMBDA_HALF in g, "λ=0.5 고정판이 격자에 없다"
    logln("[P-2-8] 격자 정합 PASS — 21점 · 중복·결손 0 · 정수 인덱스 k/20 생성")
    return {"n_points": 21, "min": 0.0, "max": 1.0, "step": 0.05,
            "construction": "k/20 for k in 0..20", "duplicates": 0, "gaps": 0}


# ═══════════════════════════════════════════════════════════════════════════
# 블록 조립 · 적합 (복사 — 사유는 모듈 docstring)
# ═══════════════════════════════════════════════════════════════════════════
def make_blocks(d):
    blocks = {
        "B0": MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"]),
        "B1": CountMaskBlock(d["ntgt"], d["mask"]),
        "B_seq": SeqBlock(d["emb"], d["mask"], pca_k=PCA_K),
    }
    assert MODEL_BLOCKS[EQUIV_MODEL] == RF_BLOCKS and EQUIV_MODEL in FROZEN_MODELS
    return blocks


def fit_blocks(blocks, ids, train_idx, d, N, label):
    """train_idx 에서만 fit + 누수 assert(하드) + B_seq fit 모집단 assert(§P-2-5)."""
    leak = {}
    for b in ids:
        blocks[b].fit(train_idx)
    for b in ids:
        rec = blocks[b].leakage_assert(train_idx)
        assert rec["leak_rows"] == 0, f"[{label}] {b} leak_rows != 0"
        leak[b] = int(rec["leak_rows"])
    if "B_seq" in ids:
        expect = np.zeros(N, dtype=bool)
        expect[np.asarray(train_idx)] = True
        expect &= d["mask"].astype(bool)
        assert np.array_equal(blocks["B_seq"]._fit_rows_mask, expect), \
            f"[{label}] B_seq fit 모집단 != train∩매핑"
    return leak


def design(blocks, ids, idx):
    return np.hstack([blocks[b].transform(idx) for b in ids]).astype(np.float32)


def rf_predict(blocks, ids, tr, ev, Y):
    """동결 확증 RF 하네스 그대로(`rf_fit_predict`, random_state=42) — 피처만 바꾼다."""
    Xtr = design(blocks, ids, tr)
    Xev = design(blocks, ids, ev)
    assert RF_SEED == 42, "RF random_state != 42"
    P = rf_fit_predict(Xtr, Y[tr], Xev, seed=RF_SEED)
    return P, int(Xtr.shape[1])


def to_f64(P, n_rows, K):
    """봉인 OOF 관례 — float64 배열에 float32 예측을 대입(블록 I 와 동일)."""
    out = np.zeros((n_rows, K), dtype=np.float64)
    out[:] = P
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 내부 분할 재현 (§P-2-3 · 새 추첨 0)
# ═══════════════════════════════════════════════════════════════════════════
def inner_units(d):
    """15 outer unit 전건 내부 분할 재현 + `inner_split_check.json` 전건 일치 assert."""
    chk = json.load(open(INNER_CHECK, encoding="utf-8"))
    assert chk["n_units"] == N_UNITS, f"inner_split_check n_units {chk['n_units']}"
    Ym = d["Ym"]
    out, rows = {}, []
    for rep, s in BR.REPS.items():
        df = BR.read_fold_membership(rep)
        assert list(df["cid"].astype(int)) == [int(c) for c in d["cid_order"]], \
            f"rep{rep} fold_membership cid 정렬 != master_X"
        scaf = df["scaffold"].tolist()
        fr = df["fold"].values
        for f in range(N_FOLD):
            r = BR.inner_split(scaf, fr, s, f)
            va, itr, tro = r["valid"], r["train"], r["outer_train"]
            # ── 하드 assert (지시서 §P-2-3) ──
            assert not (set(va) & set(itr)), f"({s},f{f}) bucket 행 교차"
            gv = {scaf[i] for i in va}
            gt = {scaf[i] for i in itr}
            assert not (gv & gt), f"({s},f{f}) scaffold group 이 두 bucket 에 걸침"
            assert len(va) + len(itr) == len(tro), f"({s},f{f}) 행 합 != outer-train"
            assert len(va) == EXPECT_INNER_VALID, f"({s},f{f}) inner-valid {len(va)}"
            assert len(itr) in EXPECT_INNER_TRAIN, f"({s},f{f}) inner-train {len(itr)}"
            assert int((Ym[itr].sum(0) == 0).sum()) == 0, \
                f"({s},f{f}) inner-train 양성 0 PT (등록 §6 위반)"
            u = next(x for x in chk["units"]
                     if x["split_seed"] == s and x["fold"] == f)
            got = (len(tro), len(itr), len(va), len(r["valid_groups"]),
                   int((Ym[va].sum(0) > 0).sum()))
            exp = (u["n_outer_train"], u["n_inner_train"], u["n_inner_valid"],
                   u["n_valid_scaffold_groups"], u["n_valid_defined_pt"])
            assert got == exp, f"[§P-2-3 FAIL] ({s},f{f}) 실측 {got} != 동결 검증표 {exp}"
            out[(rep, f)] = {"valid": np.asarray(sorted(va), dtype=int),
                             "train": np.asarray(sorted(itr), dtype=int),
                             "outer_train": np.asarray(sorted(tro), dtype=int),
                             "inner_seed": r["inner_seed"]}
            rows.append({"split_seed": s, "fold": f, "inner_seed": r["inner_seed"],
                         "n_outer_train": len(tro), "n_inner_train": len(itr),
                         "n_inner_valid": len(va),
                         "n_valid_scaffold_groups": len(r["valid_groups"]),
                         "group_cross_between_buckets": 0,
                         "matches_frozen_check": True})
    assert len(out) == N_UNITS
    logln(f"[P-2-3] 내부 분할 재현 PASS — {N_UNITS} outer unit 전건 · inner-valid "
          f"{EXPECT_INNER_VALID} · inner-train {EXPECT_INNER_TRAIN[0]}/{EXPECT_INNER_TRAIN[1]} · "
          f"bucket 간 group 교차 0 · 동결 검증표 전건 일치 (새 추첨 0)")
    return out, rows, chk["outer_split_reproduction_calibration"]


# ═══════════════════════════════════════════════════════════════════════════
# λ 선택 (내부 valid 전용 · 동점 2단계)
# ═══════════════════════════════════════════════════════════════════════════
def select_lambda(Yva, p_rf_va, p_seq_va):
    scores = []
    for lam in LAMBDA_GRID:
        P = lam * p_rf_va.astype(np.float64) + (1.0 - lam) * p_seq_va.astype(np.float64)
        m = sap_metrics.macro_ap(Yva, P, None)
        assert not np.isnan(m["macro_ap"]), "내부 valid macro AP 미정의 — 중단"
        scores.append(m["macro_ap"])
    best = max(scores)
    cand = [i for i, s in enumerate(scores) if s == best]
    cand.sort(key=lambda i: (abs(LAMBDA_GRID[i] - 0.5), LAMBDA_GRID[i]))
    return LAMBDA_GRID[cand[0]], len(cand), scores


# ═══════════════════════════════════════════════════════════════════════════
# P-2  정합 assert + 재적합 바이트 동일성 (하드 게이트)
# ═══════════════════════════════════════════════════════════════════════════
def stage_verify(d, blocks, g0):
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]
    inputs = gate_inputs()
    # P-1-6 추가 입력 — 기존 봉인 consensus_M0 (해시 대조만, 값 미판독)
    cons_m0 = os.path.join(RUNS, "v3_confirm_rest_consensus_rep123", "_sealed",
                           "consensus_M0.npz")
    assert os.path.exists(cons_m0), "consensus_M0.npz 부재"
    log_machine_read(os.path.dirname(cons_m0), os.path.relpath(cons_m0, ROOT),
                     "P-1-6 입력 sha256 대조(값 미판독)", "블록 P-1")
    inputs["sources"]["consensus_M0.npz"] = {
        "path": os.path.relpath(cons_m0, ROOT), "sha256": sha256_file(cons_m0)}

    guard = sealed_guard_snapshot()
    n_foreign = sum(1 for k in guard if not k.startswith(OWN_PREFIXES))
    logln(f"[P-1-5] sealed guard live 실측 {len(guard)}종(access.log 제외) — 선재 {n_foreign}종")
    assert abs(n_foreign - 184) <= 0, \
        f"선재 sealed guard 실측 {n_foreign} 이 지시서 기준선 184 와 어긋남 — 중단·보고"

    # ── P-2-6 fold 정합 ──
    checks = {"n_drugs": N, "n_pt": K, "reps": {}}
    assert N == EXPECT_N_DRUGS and K == EXPECT_N_PT, "master_X/Y 규모 불일치"
    for r in (1, 2, 3):
        fr = fold_of_row_for(r, d["cid_order"])
        fm = read_fold_membership(r)
        assert list(fm["cid"].astype(int)) == [int(c) for c in d["cid_order"]], \
            f"rep{r} fold_membership cid 정렬 불일치"
        assert np.array_equal(fm["fold"].values, fr), f"rep{r} folds.json != fold_membership"
        by_group = fm.groupby("scaffold")["fold"].nunique()
        assert len(by_group) == EXPECT_N_SCAFFOLD_GROUPS, \
            f"rep{r} 그룹 {len(by_group)} != {EXPECT_N_SCAFFOLD_GROUPS}"
        cross = int((by_group > 1).sum())
        assert cross == 0, f"rep{r} scaffold group fold 교차 {cross}건"
        lt1 = sum(int((Y[fr != k].sum(0) < 1).sum()) for k in range(N_FOLD))
        assert lt1 == 0, f"rep{r} rare-PT 위반 {lt1}건"
        checks["reps"][f"rep{r}"] = {
            "n_scaffold_groups": int(len(by_group)), "scaffold_fold_cross": cross,
            "n_pt_train_positive_lt1": lt1,
            "fold_sizes": [int((fr == k).sum()) for k in range(N_FOLD)]}
    logln(f"[P-2-6] fold 정합 PASS — 약물 {N} · scaffold group {EXPECT_N_SCAFFOLD_GROUPS} · "
          f"fold 교차 0 · rare-PT 위반 0 (3반복)")

    # ── P-2-7 비매핑 245 행의 B_seq 정확히 0 ──
    mask = d["mask"].astype(bool)
    assert int(mask.sum()) == EXPECT_MAPPED and int((~mask).sum()) == EXPECT_UNMAPPED, \
        f"매핑 {int(mask.sum())} / 비매핑 {int((~mask).sum())}"
    fr1 = fold_of_row_for(1, d["cid_order"])
    tr1 = np.where(fr1 != 0)[0]
    fit_blocks(blocks, ["B_seq"], tr1, d, N, "P-2-7 probe")
    Zall = blocks["B_seq"].transform(np.arange(N))
    unmapped_rows = np.where(~mask)[0]
    assert np.abs(Zall[unmapped_rows]).max() == 0.0, "비매핑 행 B_seq 가 정확히 0 이 아니다"
    zero_check = {"n_mapped": EXPECT_MAPPED, "n_unmapped": EXPECT_UNMAPPED,
                  "unmapped_bseq_exactly_zero": True}
    logln(f"[P-2-7] PASS — 비매핑 {EXPECT_UNMAPPED} 행의 B_seq 정확히 0 "
          f"(매핑 {EXPECT_MAPPED} 행이 상보성 추정을 이끈다 — 한계로 보고)")

    # ── P-2-3 내부 분할 재현 ──
    units, unit_rows, outer_calib = inner_units(d)

    # ── P-2-1 재적합 바이트 동일성 (대표 unit: rep1 fold0) ──
    te = np.where(fr1 == EQUIV_FOLD)[0]
    tro = np.where(fr1 != EQUIV_FOLD)[0]
    t0 = time.perf_counter()
    fit_blocks(blocks, RF_BLOCKS, tro, d, N, "P-2-1")
    P_rf, dim_rf = rf_predict(blocks, RF_BLOCKS, tro, te, Y)
    wall_rf = time.perf_counter() - t0
    repro = to_f64(P_rf, len(te), K)

    ref_dir = rest_sealed_of(EQUIV_REP)
    ref_path = os.path.join(ref_dir, f"oof_{EQUIV_MODEL}.npz")
    log_machine_read(ref_dir, os.path.relpath(ref_path, ROOT),
                     "P-2-1 재적합 바이트 동일성 증명(M0 fold0 슬라이스 비교)", "블록 P-2")
    with np.load(ref_path) as z:
        ref_oof, ref_fold, ref_cid = z["oof"], z["fold"], z["cid"]
    assert np.array_equal(ref_fold, fr1), "봉인 npz fold 배열이 rep1 folds.json 과 불일치"
    assert np.array_equal(ref_cid, np.array([int(c) for c in d["cid_order"]])), \
        "봉인 npz cid 배열이 master_X 정렬과 불일치"
    ref_slice = np.ascontiguousarray(ref_oof[te])
    byte_identical = (repro.dtype == ref_slice.dtype
                      and repro.shape == ref_slice.shape
                      and repro.tobytes() == ref_slice.tobytes())
    equiv = {"model": EQUIV_MODEL, "repeat": EQUIV_REP, "fold": EQUIV_FOLD,
             "n_test_rows": int(len(te)), "n_pt": K, "dim": dim_rf,
             "dtype": str(repro.dtype), "byte_identical": bool(byte_identical),
             "wall_s": wall_rf, "ref_npz": os.path.relpath(ref_path, ROOT),
             "ref_npz_sha256": sha256_file(ref_path),
             "note": ("재적합 p_RF 는 outer-train 전체로 적합했고 결정적 RF·동일 학습행·동일 "
                      "하이퍼이므로 봉인 M0 과 동일해야 정상이다. 재계산본은 저장하지 않고 "
                      "폐기했으며 기존 봉인은 기계 판독만 했다.")}
    logln(f"[P-2-1] 재적합 바이트 동일성 — {EQUIV_MODEL} rep{EQUIV_REP} fold{EQUIV_FOLD} "
          f"({len(te)}행 × {K}PT, dim={dim_rf}) = {byte_identical} | wall {wall_rf:.1f}s "
          f"(수치 미기록 — redaction)")
    if not byte_identical:
        logln("[P-2-1] ❌ 재적합 바이트 불일치 — 하네스 경로 이상. 중단·산출 폐기.")
        flush_log()
        sys.exit(11)

    # ── P-2-2 행 정렬 (원소 단위) ──
    row_align = {"p_rf_rows_equal_test_idx": bool(np.array_equal(
                     np.asarray(sorted(te)), te)),
                 "master_X_cid_sorted": bool(
                     list(d["X"]["cid"].astype(int)) == sorted(
                         int(c) for c in d["cid_order"])),
                 "sealed_cid_matches_master_X": True}
    assert all(row_align.values()), f"[P-2-2] 행 정렬 위반 {row_align}"

    # ── P-2-4 λ 무누수 (15 unit 전건) ──
    for (rep, f), u in units.items():
        frx = fold_of_row_for(rep, d["cid_order"])
        tex = set(np.where(frx == f)[0].tolist())
        assert not (set(u["valid"].tolist()) & tex), f"({rep},f{f}) inner-valid ∩ test != 0"
        assert not (set(u["train"].tolist()) & tex), f"({rep},f{f}) inner-train ∩ test != 0"
    logln(f"[P-2-4] λ 무누수 PASS — {N_UNITS} unit 전건 inner-valid/-train ∩ test = 0")

    del repro, ref_oof, ref_slice

    guard_end = sealed_guard_snapshot()
    gchk = assert_guard_unchanged(guard, guard_end, "P-2 verify")
    out = {"ts_kst": now_kst(), "gate0": g0, "inputs": inputs,
           "sealed_guard_check": gchk, "consistency_checks": checks,
           "zero_vector_check": zero_check, "row_alignment": row_align,
           "inner_split_units": unit_rows,
           "outer_split_reproduction_calibration": outer_calib,
           "equivalence": equiv, "lambda_no_leak": True,
           "sealed_guard_n_files": len(guard), "sealed_guard_unchanged": True}
    dump_json(os.path.join(BASE_DIR, "verify_public.json"), out)
    return out, units


# ═══════════════════════════════════════════════════════════════════════════
# P-3  계측 (필수 · 7일 초과 시 중단)
# ═══════════════════════════════════════════════════════════════════════════
def stage_measure(d, blocks, units, verify):
    N = len(d["cid_order"])
    Y = d["Ym"]
    u = units[(1, 0)]
    itr, va = u["train"], u["valid"]

    # p_seq 1 model-fold (내부-train 적합 → 내부-valid 예측)
    t0 = time.perf_counter()
    fit_blocks(blocks, SEQ_PRIMARY, itr, d, N, "measure p_seq")
    P_seq, dim_seq = rf_predict(blocks, SEQ_PRIMARY, itr, va, Y)
    wall_seq = time.perf_counter() - t0

    # 내부 valid 1회(격자 21점 탐색) — p_RF 내부 예측이 필요
    t1 = time.perf_counter()
    fit_blocks(blocks, RF_BLOCKS, itr, d, N, "measure p_rf(inner)")
    P_rf_in, dim_rf = rf_predict(blocks, RF_BLOCKS, itr, va, Y)
    wall_rf_inner = time.perf_counter() - t1
    t2 = time.perf_counter()
    _lam, _nt, _sc = select_lambda(Y[va], P_rf_in, P_seq)
    wall_grid = time.perf_counter() - t2
    del P_seq, P_rf_in, _lam, _sc

    dim_seq_sens = blocks["B1"].dim + PCA_K
    wall_rf_refit = verify["equivalence"]["wall_s"]      # P-2-1 실측(outer-train 전체)
    # unit 당 = inner(rf, seq, seq_sens) + refit(rf, seq, seq_sens) + 격자 2회
    per_unit = (wall_rf_inner + 2 * wall_seq) + (wall_rf_refit + 2 * wall_seq) + 2 * wall_grid
    total_s = per_unit * N_UNITS
    est = {"measured_model_folds": ["p_seq(inner)", "p_RF(inner)", "p_RF(refit, P-2-1)"],
           "measured_wall_s_p_seq_inner": wall_seq,
           "measured_wall_s_p_rf_inner": wall_rf_inner,
           "measured_wall_s_p_rf_refit": wall_rf_refit,
           "measured_wall_s_lambda_grid_21": wall_grid,
           "dims": {"p_rf": dim_rf, "p_seq_primary": dim_seq,
                    "p_seq_sensitivity": dim_seq_sens},
           "n_units": N_UNITS, "n_rf_fits_per_unit": N_FITS_PER_UNIT,
           "n_rf_fits_total": N_UNITS * N_FITS_PER_UNIT,
           "estimated_per_unit_wall_s": per_unit,
           "estimated_total_wall_s": total_s,
           "estimated_total_wall_hours": total_s / 3600.0,
           "estimated_total_wall_days": total_s / 86400.0,
           "abort_threshold_days": ABORT_DAYS,
           "exceeds_threshold": bool(total_s / 86400.0 > ABORT_DAYS),
           "peak_rss_gib": peak_rss_gib(),
           "scaling_note": ("비용 지배변수 = RF 적합 횟수(지시서 §P-3). 확정본이 재적합을 "
                            "요구하므로 unit 당 6 fit(내부 rf·seq·seq_sens + 재적합 "
                            "rf·seq·seq_sens)로 세고, sensitivity 를 별도로 더하지 않고 "
                            "이미 포함해 셌다. v1 의 '45' 추정은 재적합 미반영이라 쓰지 않았다. "
                            "λ 격자 탐색은 행렬 가중합이라 무시 가능 수준임을 실측으로 확인했다."),
           }
    logln(f"[P-3] 계측 — p_seq(inner) {wall_seq:.1f}s · p_RF(inner) {wall_rf_inner:.1f}s · "
          f"p_RF(refit) {wall_rf_refit:.1f}s · 격자21 {wall_grid:.2f}s → "
          f"{N_UNITS} unit × {N_FITS_PER_UNIT} fit 총 추정 "
          f"{est['estimated_total_wall_hours']:.2f}h ({est['estimated_total_wall_days']:.4f}일) · "
          f"임계 {ABORT_DAYS}일 · 초과 = {est['exceeds_threshold']} | "
          f"peak RSS {est['peak_rss_gib']:.2f} GiB")
    dump_json(os.path.join(BASE_DIR, "measure_public.json"), est)
    if est["exceeds_threshold"]:
        logln("[P-3] ❌ 추정 wall 7일 초과 — 실행하지 않고 중단(지시서 중단 조건)")
        flush_log()
        sys.exit(12)
    return est


# ═══════════════════════════════════════════════════════════════════════════
# P-4  본계산 (체크포인트 · (반복, fold) 단위 재개)
# ═══════════════════════════════════════════════════════════════════════════
CKPT_FIELDS = ["repeat", "fold", "n_outer_train", "n_inner_train", "n_inner_valid",
               "n_test", "dim_rf", "dim_seq", "dim_seq_sens", "wall_s", "peak_rss_gib",
               "refit_byte_identical", "sha256_partial_rf", "sha256_partial_seq",
               "sha256_partial_seq_sens", "ts_kst", "session_seq"]


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
    return {"python_version": sys.version.split()[0], "numpy": np.__version__,
            "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__, "pandas": pd.__version__,
            "rdkit": __import__("rdkit").__version__,
            "ladder_freeze_sha256": sha256_file(
                os.path.join(CONFIG_DIR, "ladder_freeze.json")),
            "latefusion_freeze_sha256": sha256_file(LF_FREEZE),
            "gin_inner_valid_freeze_sha256": sha256_file(
                os.path.join(CONFIG_DIR, "gin_inner_valid_freeze.json")),
            "sap_manifest_sha256": sha256_file(
                os.path.join(ROOT, "experiments", "sap", "manifest.json")),
            "split_files_sha256": splits, "machine": platform.machine(),
            "os": f"{platform.system()} {platform.release()}"}


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
                break
            raise AssertionError(f"[checkpoint] {i + 1}번째 줄 파손 — 수동 확인 필요")
    keys = [(r["repeat"], r["fold"]) for r in rows]
    dup = {k for k in keys if keys.count(k) > 1}
    assert not dup, f"[checkpoint] 중복 {sorted(dup)[:5]} — 즉시 중단"
    return rows


def ckpt_append(rec):
    os.makedirs(WORK_DIR, exist_ok=True)
    with open(CKPT, "a", encoding="utf-8") as f:
        f.write(json.dumps({k: rec.get(k) for k in CKPT_FIELDS}, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def pp(r, k, name):
    return os.path.join(WORK_DIR, f"rep{r}_f{k}_{name}.npy")


def meta_path(r, k):
    return os.path.join(WORK_DIR, f"rep{r}_f{k}_meta.json")


def run_unit(d, blocks, units, r, k, ref_oof):
    """한 outer unit — 내부 분할 재현 → λ 선택 → 재적합 → test 예측."""
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]
    fr = fold_of_row_for(r, d["cid_order"])
    te = np.where(fr == k)[0]
    u = units[(r, k)]
    tro, itr, va = u["outer_train"], u["train"], u["valid"]
    assert np.array_equal(np.asarray(sorted(np.where(fr != k)[0])), tro), \
        f"({r},f{k}) outer-train 재현 불일치"
    assert not (set(va.tolist()) & set(te.tolist())), f"({r},f{k}) λ 누수"

    # ── 1) 내부 단계: inner-train 적합 → inner-valid 예측 → 격자 21점 λ 선택 ──
    fit_blocks(blocks, RF_BLOCKS, itr, d, N, f"({r},f{k}) inner rf")
    P_rf_in, dim_rf = rf_predict(blocks, RF_BLOCKS, itr, va, Y)
    fit_blocks(blocks, SEQ_PRIMARY, itr, d, N, f"({r},f{k}) inner seq")
    P_seq_in, dim_seq = rf_predict(blocks, SEQ_PRIMARY, itr, va, Y)
    lam, n_tied, _sc = select_lambda(Y[va], P_rf_in, P_seq_in)
    fit_blocks(blocks, SEQ_SENS, itr, d, N, f"({r},f{k}) inner seq_sens")
    P_ss_in, dim_ss = rf_predict(blocks, SEQ_SENS, itr, va, Y)
    lam_s, n_tied_s, _sc2 = select_lambda(Y[va], P_rf_in, P_ss_in)
    del P_rf_in, P_seq_in, P_ss_in, _sc, _sc2

    # ── 2) 재적합 단계: outer-train 전체 적합 → test 예측 + 바이트 동일성 assert ──
    fit_blocks(blocks, RF_BLOCKS, tro, d, N, f"({r},f{k}) refit rf")
    P_rf, dim_rf2 = rf_predict(blocks, RF_BLOCKS, tro, te, Y)
    assert dim_rf2 == dim_rf
    repro = to_f64(P_rf, len(te), K)
    ref_slice = np.ascontiguousarray(ref_oof[te])
    ok = (repro.dtype == ref_slice.dtype and repro.shape == ref_slice.shape
          and repro.tobytes() == ref_slice.tobytes())
    assert ok, (f"[P-2-1 FAIL] ({r},f{k}) 재적합 p_RF 가 봉인 M0 와 바이트 불일치 — "
                "하네스 경로 이상. 중단·산출 폐기.")
    fit_blocks(blocks, SEQ_PRIMARY, tro, d, N, f"({r},f{k}) refit seq")
    P_seq, _ = rf_predict(blocks, SEQ_PRIMARY, tro, te, Y)
    fit_blocks(blocks, SEQ_SENS, tro, d, N, f"({r},f{k}) refit seq_sens")
    P_ss, _ = rf_predict(blocks, SEQ_SENS, tro, te, Y)

    np.save(pp(r, k, "prf"), P_rf)
    np.save(pp(r, k, "pseq"), P_seq)
    np.save(pp(r, k, "pseqsens"), P_ss)
    with open(meta_path(r, k), "w", encoding="utf-8") as f:
        json.dump({"_warning": "SEALED — λ 는 결과-의존 선택량이다. 개봉 전 열람 금지.",
                   "repeat": r, "fold": k, "split_seed": SEED_MAP[r],
                   "inner_seed": u["inner_seed"],
                   "lambda_selected": lam, "lambda_n_tied": n_tied,
                   "lambda_selected_sensitivity": lam_s,
                   "lambda_n_tied_sensitivity": n_tied_s,
                   "n_inner_train": int(len(itr)), "n_inner_valid": int(len(va)),
                   "n_outer_train": int(len(tro)), "n_test": int(len(te)),
                   "refit_byte_identical": True}, f, indent=2, ensure_ascii=False)
    return {"repeat": r, "fold": k, "n_outer_train": int(len(tro)),
            "n_inner_train": int(len(itr)), "n_inner_valid": int(len(va)),
            "n_test": int(len(te)), "dim_rf": dim_rf, "dim_seq": dim_seq,
            "dim_seq_sens": dim_ss, "refit_byte_identical": True,
            "sha256_partial_rf": sha256_file(pp(r, k, "prf")),
            "sha256_partial_seq": sha256_file(pp(r, k, "pseq")),
            "sha256_partial_seq_sens": sha256_file(pp(r, k, "pseqsens"))}


def aux_indicators(Y, oof_rf, oof_seq, oof_ens, fr):
    """등록 §12 보조 지표 — **봉인 파일 전용**. Δ(ens−RF) 통계량·CI·p·부호는 산출하지 않는다."""
    from scipy.stats import spearmanr
    defined = Y.sum(0) > 0
    cols = np.where(defined)[0]
    # (a) 상관 — PT별 Pearson/Spearman(p_RF vs p_seq) 의 평균
    pear, spear = [], []
    for j in cols:
        a, b = oof_rf[:, j], oof_seq[:, j]
        if a.std() > 0 and b.std() > 0:
            pear.append(float(np.corrcoef(a, b)[0, 1]))
            spear.append(float(spearmanr(a, b).statistic))
    # (b) rank disagreement — 1 − |Spearman| 평균 + 상위 k 집합 비중복
    # (c) 상호 정오분석 — PT별 상위 n_pos 포착 양성 집합의 비중복
    only_rf = only_seq = both = 0
    jac = []
    for j in cols:
        npos = int(Y[:, j].sum())
        if npos == 0:
            continue
        top_rf = set(np.argsort(-oof_rf[:, j], kind="stable")[:npos].tolist())
        top_sq = set(np.argsort(-oof_seq[:, j], kind="stable")[:npos].tolist())
        pos = set(np.where(Y[:, j] == 1)[0].tolist())
        hr, hs = top_rf & pos, top_sq & pos
        only_rf += len(hr - hs)
        only_seq += len(hs - hr)
        both += len(hr & hs)
        un = len(hr | hs)
        jac.append(len(hr & hs) / un if un else 1.0)
    # (d) 개선 fold 비율 — 봉인 전용(지시서 §P-4 가 명시 지정). 공개 노출 0.
    imp = 0
    for k in range(N_FOLD):
        m_rf = sap_metrics.macro_ap(Y[fr == k], oof_rf[fr == k], None)["macro_ap"]
        m_en = sap_metrics.macro_ap(Y[fr == k], oof_ens[fr == k], None)["macro_ap"]
        imp += int(m_en > m_rf)
    return {"_note": ("등록 §12 보조 지표. **봉인 전용** — 공개 요약에는 존재 여부만 적는다. "
                      "Holm ⑦ 의 Δ·CI·p·부호는 본 블록에서 산출하지 않았다."),
            "n_defined_pt": int(len(cols)),
            "mean_pearson_rf_vs_seq": float(np.mean(pear)) if pear else None,
            "mean_spearman_rf_vs_seq": float(np.mean(spear)) if spear else None,
            "mean_rank_disagreement_1_minus_abs_spearman":
                float(np.mean([1 - abs(s) for s in spear])) if spear else None,
            "captured_positives_only_rf": only_rf,
            "captured_positives_only_seq": only_seq,
            "captured_positives_both": both,
            "mean_jaccard_captured_positives": float(np.mean(jac)) if jac else None,
            "n_folds_ensemble_above_rf": imp, "n_folds": N_FOLD}


def stage_run(d, blocks, units):
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]
    os.makedirs(WORK_DIR, exist_ok=True)

    fp_now = env_fingerprint()
    fp_match, fp_diff = True, []
    if os.path.exists(ENV_FP):
        fp_prev = json.load(open(ENV_FP))
        fp_diff = [k for k in fp_now if fp_prev.get(k) != fp_now[k]]
        fp_match = not fp_diff
    else:
        dump_json(ENV_FP, fp_now)
    done = ckpt_load()
    done_keys = {(x["repeat"], x["fold"]) for x in done}
    session_seq = max((x.get("session_seq", 0) for x in done), default=0) + 1
    if done:
        logln(f"[재개] 세션 #{session_seq} · 기완주 {len(done_keys)}/{N_UNITS} · "
              f"환경지문 일치={fp_match} {('차이=' + str(fp_diff)) if fp_diff else ''}")
        assert fp_match, f"[재개] 환경 지문 불일치 {fp_diff} — 중단"
        gate_c_settle("세션 재개 직전")

    guard_start = sealed_guard_snapshot()
    n_done_session = 0
    t_session = time.perf_counter()

    for r in (1, 2, 3):
        ref_path = os.path.join(rest_sealed_of(r), f"oof_{EQUIV_MODEL}.npz")
        log_machine_read(rest_sealed_of(r), os.path.relpath(ref_path, ROOT),
                         f"P-2-1 재적합 바이트 동일성 대조(rep{r} 전 fold)", "블록 P-4")
        with np.load(ref_path) as z:
            ref_oof = z["oof"]
            assert np.array_equal(z["cid"],
                                  np.array([int(c) for c in d["cid_order"]])), \
                f"rep{r} 봉인 cid 정렬 불일치"
        gate_b_exclusive(f"rep{r}:before")
        for k in range(N_FOLD):
            if (r, k) in done_keys:
                continue
            t0 = time.perf_counter()
            rec = run_unit(d, blocks, units, r, k, ref_oof)
            rec["wall_s"] = time.perf_counter() - t0
            rec["peak_rss_gib"] = peak_rss_gib()
            rec["ts_kst"] = now_kst()
            rec["session_seq"] = session_seq
            ckpt_append(rec)
            done_keys.add((r, k))
            n_done_session += 1
            logln(f"[본계산] rep{r} fold{k} — outer_train={rec['n_outer_train']} "
                  f"inner_train={rec['n_inner_train']} inner_valid={rec['n_inner_valid']} "
                  f"test={rec['n_test']} dim(rf/seq/sens)="
                  f"{rec['dim_rf']}/{rec['dim_seq']}/{rec['dim_seq_sens']} "
                  f"refit_byte_identical={rec['refit_byte_identical']} leak_rows=0 | "
                  f"wall {rec['wall_s']:.1f}s | 누계 {len(done_keys)}/{N_UNITS} "
                  f"(λ·수치 미기록 — redaction)")
        gate_b_exclusive(f"rep{r}:after")
        del ref_oof

    assert len(done_keys) == N_UNITS, f"완주 {len(done_keys)} != {N_UNITS}"
    logln(f"[본계산] 전 {N_UNITS} outer unit 완주 — 세션 #{session_seq} 신규 {n_done_session}건")

    # ── 반복별 OOF 조립 + 봉인 ──
    sealed_sha = {}
    cid_arr = np.array([int(c) for c in d["cid_order"]])
    for r in (1, 2, 3):
        fr = fold_of_row_for(r, d["cid_order"])
        store = sap_redaction.SealedStore(run_dir_of(r))
        os.makedirs(store.sealed_dir, exist_ok=True)
        oof = {n: np.full((N, K), np.nan, dtype=np.float64) for n in ARM_FILES}
        oof_rf = np.full((N, K), np.nan, dtype=np.float64)
        lams = []
        for k in range(N_FOLD):
            te = np.where(fr == k)[0]
            m = json.load(open(meta_path(r, k), encoding="utf-8"))
            lam, lam_s = m["lambda_selected"], m["lambda_selected_sensitivity"]
            lams.append(m)
            prf = to_f64(np.load(pp(r, k, "prf")), len(te), K)
            psq = to_f64(np.load(pp(r, k, "pseq")), len(te), K)
            pss = to_f64(np.load(pp(r, k, "pseqsens")), len(te), K)
            oof_rf[te] = prf
            oof["oof_seq"][te] = psq
            oof["oof_ens"][te] = lam * prf + (1.0 - lam) * psq
            oof["oof_ens_half"][te] = LAMBDA_HALF * prf + (1.0 - LAMBDA_HALF) * psq
            oof["oof_seq_sens"][te] = pss
            oof["oof_ens_sens"][te] = lam_s * prf + (1.0 - lam_s) * pss
        for n, a in oof.items():
            assert not np.isnan(a).any(), f"rep{r} {n} OOF NaN 존재"
            assert a.shape == (EXPECT_N_DRUGS, EXPECT_N_PT), f"rep{r} {n} shape {a.shape}"
            np.savez_compressed(os.path.join(store.sealed_dir, f"{n}.npz"),
                                oof=a, cid=cid_arr, fold=fr)
            sealed_sha[f"rep{r}/{n}.npz"] = sha256_file(
                os.path.join(store.sealed_dir, f"{n}.npz"))
        assert not np.isnan(oof_rf).any(), f"rep{r} p_RF OOF NaN 존재"
        store.write_sealed("lambda_selected.json", {
            "_warning": "SEALED — λ 는 결과-의존 선택량이다. 개봉 전 열람 금지.",
            "step": f"블록 P — Holm ⑦ late-fusion 반복{r}(seed {SEED_MAP[r]})",
            "ts_kst": now_kst(), "grid": {"min": 0.0, "max": 1.0, "step": 0.05,
                                          "n_points": 21},
            "tie_break": ["|lambda-0.5| 최소", "그래도 동점이면 작은 lambda"],
            "selection_metric": "inner-valid macro AP (eligible_pt=None, 동결 미정의-AP 제외)",
            "per_unit": lams})
        sealed_sha[f"rep{r}/lambda_selected.json"] = sha256_file(
            os.path.join(store.sealed_dir, "lambda_selected.json"))
        store.write_sealed("metrics_full.json", {
            "_warning": "SEALED — 성공판정(개봉) 전 열람 금지. Δ·CI·p·부호 미산출(docs/61 §1).",
            "step": f"블록 P — Holm ⑦ late-fusion arm 반복{r}(seed {SEED_MAP[r]})",
            "ts_kst": now_kst(),
            "estimand": "사전등록 §7 primary — global 양성≥10 PT(370) macro AP, eligible_pt=None",
            "arms": ARM_FILES + ["p_RF(=M0, 재적합 바이트 동일)"],
            "macro_ap": {**{n: sap_metrics.macro_ap(Y, oof[n], None) for n in ARM_FILES},
                         "p_rf": sap_metrics.macro_ap(Y, oof_rf, None)},
            "per_fold_macro_ap": {
                **{n: [sap_metrics.macro_ap(Y[fr == k], oof[n][fr == k], None)
                       for k in range(N_FOLD)] for n in ARM_FILES},
                "p_rf": [sap_metrics.macro_ap(Y[fr == k], oof_rf[fr == k], None)
                         for k in range(N_FOLD)]},
            "auxiliary_registered_s12": aux_indicators(Y, oof_rf, oof["oof_seq"],
                                                       oof["oof_ens"], fr),
            "pt_columns": d["ycols"],
            "delta_not_computed": ("Δ(ensemble − RF) 와 그 CI·p·부호는 본 블록에서 산출하지 "
                                   "않는다. Holm ⑦ 는 개봉 단계에서 consensus 위 "
                                   "bootstrap/sign-flip 으로 일괄 계산한다."),
            "sensitivity_firewall": ("oof_seq_sens·oof_ens_sens 는 ⑦ 성공판정에 쓰지 않으며 "
                                     "primary 를 대체하지 않는다."),
        })
        sealed_sha[f"rep{r}/metrics_full.json"] = sha256_file(
            os.path.join(store.sealed_dir, "metrics_full.json"))
        logln(f"[봉인] rep{r} — {len(ARM_FILES)}종 OOF + lambda_selected.json + "
              f"metrics_full.json 저장 ({os.path.relpath(store.sealed_dir, ROOT)})")

    guard_end = sealed_guard_snapshot()
    gchk = assert_guard_unchanged(guard_start, guard_end, "P-4 run")
    return {"total": N_UNITS, "session_seq": session_seq,
            "n_done_this_session": n_done_session,
            "session_wall_s": time.perf_counter() - t_session,
            "sealed_sha256": sealed_sha, "env_fingerprint_match": fp_match,
            "sealed_guard_check": gchk,
            "sealed_guard_n_files": len(guard_start), "sealed_guard_unchanged": True}


# ═══════════════════════════════════════════════════════════════════════════
# P-4  consensus (방법 A · 반복 순서 1→2→3 고정)
# ═══════════════════════════════════════════════════════════════════════════
def stage_consensus(d):
    Y = d["Ym"]
    t0 = time.perf_counter()
    store = sap_redaction.SealedStore(CONS_DIR)
    os.makedirs(store.sealed_dir, exist_ok=True)
    cid_arr = np.array([int(c) for c in d["cid_order"]])
    sealed_sha, res = {}, {}
    for n in ARM_FILES:
        seq = []
        for r in (1, 2, 3):
            p = os.path.join(run_dir_of(r), "_sealed", f"{n}.npz")
            log_machine_read(os.path.join(run_dir_of(r), "_sealed"),
                             os.path.relpath(p, ROOT),
                             f"consensus 입력(rep{r} {n})", "블록 P consensus")
            with np.load(p) as z:
                seq.append(z["oof"])
        assert all(a.shape == (EXPECT_N_DRUGS, EXPECT_N_PT) for a in seq), \
            "반복 OOF shape 불일치"
        cons = sap_consensus.build_consensus(seq)
        fn = f"consensus_{n[4:]}.npz"
        np.savez_compressed(os.path.join(store.sealed_dir, fn),
                            consensus=cons, cid=cid_arr)
        sealed_sha[fn] = sha256_file(os.path.join(store.sealed_dir, fn))
        res[n] = {"macro_ap": sap_metrics.macro_ap(Y, cons, None),
                  "per_repeat": sap_consensus.repeat_macro_aps(
                      seq, Y, sap_metrics.macro_ap, None)}
        logln(f"[consensus] {n} — 반복 3개 산술평균(방법A) 봉인 저장 (수치 미기록)")
    store.write_sealed("metrics_full.json", {
        "_warning": "SEALED — 성공판정(개봉) 전 열람 금지. Δ·CI·p·부호 미산출(docs/61 §1).",
        "step": "블록 P — Holm ⑦ late-fusion consensus(반복1·2·3)", "ts_kst": now_kst(),
        "method": sap_consensus.CONSENSUS_METHOD, "arms": ARM_FILES,
        "macro_ap": {n: res[n]["macro_ap"] for n in ARM_FILES},
        "per_repeat_macro_ap": {n: res[n]["per_repeat"] for n in ARM_FILES},
        "pt_columns": d["ycols"],
        "delta_not_computed": "Δ·CI·p·부호 미산출 — 개봉 단계에서 일괄.",
    })
    sealed_sha["metrics_full.json"] = sha256_file(
        os.path.join(store.sealed_dir, "metrics_full.json"))
    wall = time.perf_counter() - t0
    logln(f"[consensus] {len(ARM_FILES)} arm 완료 — {os.path.relpath(CONS_DIR, ROOT)} "
          f"(기존 consensus 디렉터리 불변) | wall {wall:.1f}s")
    return {"n_arms": len(ARM_FILES), "method": sap_consensus.CONSENSUS_METHOD,
            "dir": os.path.relpath(CONS_DIR, ROOT), "sealed_sha256": sealed_sha,
            "wall_s": wall}


# ═══════════════════════════════════════════════════════════════════════════
# P-5  공개 요약 + 방어 assert
# ═══════════════════════════════════════════════════════════════════════════
SIGN_LITERALS = ("positive", "negative", "zero")
# 결과 계열이 아닌 **공개 허용** 실수 — 지시서 §P-5 허용목록(λ 격자 정의값·시간·메모리)
FLOAT_ALLOW_KEYS = ("min", "max", "step", "wall_s", "session_wall_s",
                    "measured_wall_s_p_seq_inner", "measured_wall_s_p_rf_inner",
                    "measured_wall_s_p_rf_refit", "measured_wall_s_lambda_grid_21",
                    "estimated_per_unit_wall_s", "estimated_total_wall_s",
                    "estimated_total_wall_hours", "estimated_total_wall_days",
                    "abort_threshold_days", "peak_rss_gib", "load1")
FORBIDDEN_EXTRA = ("lambda_selected",)
# ★ 오탐 방지 허용목록(지시서 §P-5 — 블록 L §5·블록 U §5-3 전례).
#   `FORBIDDEN_PUBLIC_KEYS` 의 `"p_"` 는 **p-value** 를 잡으려는 접두사인데, ⑦ 의 arm 이름이
#   확정본 문면 그대로 `p_rf`·`p_seq_primary`·`p_seq_sensitivity` 여서 키 이름만으로 걸린다.
#   이들은 **arm 라벨**이며 값은 블록 목록·차원 정수뿐이다(성능 수치 0). 실제 방어는 아래
#   **값 기준 스캔**이 수행한다 — 키 이름이 아니라 값으로 판정한다.
KEY_ALLOW = ("p_rf", "p_seq_primary", "p_seq_sensitivity", "p_rf_rows_equal_test_idx")


def _all_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _all_keys(v)


def write_public(g0, gates, verify, measure, run, cons, grid):
    pub = {
        "_scope": ("블록 P 공개 요약 — arm 이름·차원·개수·형상·해시·시간·게이트 판정뿐. "
                   "Δ·macro AP·CI·p·부호·**λ 값** 전량 봉인(docs/61 §1·§P-5)."),
        "ts_kst": now_kst(),
        "spec": "docs/61_v3_late_fusion_prompt_for_vscode.md (개정판 v2.1)",
        "hypothesis": ("Holm ⑦ (RF+seq − RF, RQ7) 의 arm 산출 — 대비(Δ)는 본 블록 범위 밖"),
        "holm_label": "RFseq-RF",
        "freeze_file": "v3_Multimodal/config/holm7_latefusion_freeze.json",
        "freeze_sha256": sha256_file(LF_FREEZE),
        "arms": {"p_rf": {"blocks": RF_BLOCKS, "model": "M0",
                          "feature_dim": verify["equivalence"]["dim"]},
                 "p_seq_primary": {"blocks": SEQ_PRIMARY,
                                   "feature_dim": measure["dims"]["p_seq_primary"]},
                 "p_seq_sensitivity": {"blocks": SEQ_SENS,
                                       "feature_dim": measure["dims"]["p_seq_sensitivity"],
                                       "used_for_adjudication": False}},
        "sealed_arm_files": ARM_FILES,
        "n_repeats": len(SEED_MAP), "n_fold": N_FOLD, "n_outer_units": N_UNITS,
        "n_completed_units": run["total"],
        "n_rf_fits_total": N_UNITS * N_FITS_PER_UNIT,
        "inner_validation": {
            "size": EXPECT_INNER_VALID,
            "inner_train_sizes": list(EXPECT_INNER_TRAIN),
            "scaffold_group_cross_between_buckets": 0,
            "shared_rule": "gin_inner_valid_freeze.json (1/9 scaffold-group · 새 추첨 0)",
            "reproduction_matches_frozen_check": True,
            "units": verify["inner_split_units"]},
        "lambda_grid_definition": grid,
        "lambda_values_public": False,
        "lambda_note": "λ 는 결과-의존 선택량이라 값 전량 봉인 — 공개는 격자 정의뿐.",
        "gate0": {"ladder_freeze_sha16": g0["ladder_freeze_sha16"],
                  "sap_manifest_sha16": g0["sap_manifest_sha16"],
                  "sap_version": g0["sap_version"],
                  "sap_n_modules_verified": g0["sap_n_modules_verified"],
                  "sap_modules_all_match": all(g0["sap_modules_match"].values()),
                  "pass": bool(g0["gate0_pass"])},
        "gates": gates,
        "inputs_sha256": verify["inputs"],
        "consistency_checks": verify["consistency_checks"],
        "zero_vector_check": verify["zero_vector_check"],
        "row_alignment": verify["row_alignment"],
        "outer_split_reproduction_calibration":
            verify["outer_split_reproduction_calibration"],
        "refit_byte_identity_assert": {
            "verify_stage": verify["equivalence"]["byte_identical"],
            "every_unit": True,
            "n_units_asserted": run["total"],
            "reference": verify["equivalence"]["ref_npz"],
            "detail": {k: v for k, v in verify["equivalence"].items()
                       if k in ("model", "repeat", "fold", "n_test_rows", "dim",
                                "dtype", "wall_s")}},
        "oof_shape": [EXPECT_N_DRUGS, EXPECT_N_PT], "oof_nan_count": 0, "leak_rows": 0,
        "measure": measure,
        "run": {k: v for k, v in run.items() if k != "sealed_sha256"},
        "sealed_sha256_oof": run["sealed_sha256"],
        "consensus": cons,
        "auxiliary_registered_s12_computed_into_sealed_only": True,
        "auxiliary_registered_s12_items": ["상관", "rank disagreement", "정오 비중복",
                                           "개선 fold 비율"],
        "peak_rss_gib": peak_rss_gib(),
        "sealed_guard_n_files": run["sealed_guard_n_files"],
        "sealed_guard_unchanged": run["sealed_guard_unchanged"],
        "compute_conditions": {
            "blas_env": {k: os.environ.get(k) for k in
                         ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "rf_n_jobs": RF_KW["n_jobs"], "rf_random_state": RF_SEED,
            "note": "블록 I·O 와 동일 조건(스레드 환경변수 미설정·병렬 인자 무변경)."},
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__,
                     "scipy": __import__("scipy").__version__,
                     "rdkit": __import__("rdkit").__version__,
                     "platform": platform.platform()},
        "not_performed": ["개봉(open_sealed)", "성공판정(rq*_decision)", "Holm/BH 다중성",
                          "TOST/SESOI", "bootstrap CI", "sign-flip", "p-value",
                          "Δ(ensemble − RF) 산출", "부호 산출(emit_sign)",
                          "λ 값 공개", "λ 를 test·OOF·Δ·p 로 선택",
                          "기존 동결물 수정", "기존 _sealed 덮어쓰기",
                          "동결 8모델·RF_tuned 재계산", "split·fold·seed 재추첨",
                          "내부 valid 재추첨", "⑧ GIN·RQ-int", "A3·A4·A6 층화",
                          "A5 재조회", "네트워크", "data/raw 변경", "git commit·push"],
        "open_sealed_calls": 0, "decision_functions_called": [],
        "multiplicity_applied": False, "emit_sign_called": False,
        "gin_start_still_blocked": True,
    }
    blob = json.dumps(pub, ensure_ascii=False, default=native)
    parsed = json.loads(blob)

    def walk(o, path="$"):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from walk(v, f"{path}[{i}]")
        else:
            yield path, o

    items = list(walk(parsed))
    keys = set(_all_keys(parsed))
    bad_keys = sorted(k for k in keys
                      if k not in KEY_ALLOW
                      and any(k == f or k.startswith(f)
                              for f in FORBIDDEN_PUBLIC_KEYS + FORBIDDEN_EXTRA))
    assert not bad_keys, f"공개 파일에 봉인 대상 키 노출: {bad_keys}"
    bad_vals = []
    for p, v in items:
        leaf = p.rsplit(".", 1)[-1].split("[")[0]
        if isinstance(v, float) and leaf not in FLOAT_ALLOW_KEYS:
            bad_vals.append((p, v))
        if isinstance(v, str) and v.strip().lower() in SIGN_LITERALS:
            bad_vals.append((p, v))
    assert not bad_vals, f"공개 파일 값 스캔 위반: {bad_vals[:5]}"
    # 금지어 목록 자체가 스캔에 걸리는 오탐 방지(블록 L §5 전례) — 목록은 코드 상수다.
    assert "FORBIDDEN_PUBLIC_KEYS" not in blob and "SIGN_LITERALS" not in blob
    dump_json(os.path.join(BASE_DIR, "latefusion_public.json"), pub)
    logln(f"[공개] latefusion_public.json 기록 — 봉인 대상 키 검출 0 "
          f"(키 {len(keys)}개·리프 {len(items)}개 스캔, 실수 허용목록 {len(FLOAT_ALLOW_KEYS)}종)")
    return pub


# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage",
                    choices=["verify", "measure", "run", "consensus", "all", "public"],
                    default="all")
    ap.add_argument("--viewer", default="vscode-claude(runner)")
    args = ap.parse_args()

    os.makedirs(BASE_DIR, exist_ok=True)
    logln("=" * 78)
    logln(f"[블록 P] stage={args.stage} — Holm ⑦ RFseq−RF late-fusion arm 산출 "
          f"({N_UNITS} outer unit). Δ·AP·CI·p·부호·λ 전량 봉인.")

    gates = {}
    gates["A_entry"] = gate_a_load("블록 P 진입")
    gates["B_start"] = gate_b_exclusive("블록 P 시작")
    gates["prelook"] = gate_prelook_recorded()
    gates["G_BLOCK"] = gate_block()
    gates["G_HOLM"] = gate_holm_family()
    gates["G0_extra"] = gate_g0_extra()
    gates["freeze"] = gate_freeze_file()
    if args.stage == "public":
        # `public` = 이미 완주·봉인된 산출물 위에 **공개 요약만** 다시 쓰는 스테이지.
        # 산출물이 존재하는 것이 정상이므로 1회성 착수 조건은 적용하지 않고, 대신
        # 봉인 무결성(선재 184종 불변 + 본 블록 산출 sha 일치)을 재확인한다.
        gates["no_existing_outputs"] = {"skipped_for_public_stage": True}
    else:
        gates["no_existing_outputs"] = gate_no_existing_outputs()
    grid = gate_lambda_grid()
    gates["lambda_grid"] = grid
    g0 = gate0_verify()

    d = load_frozen()
    logln(f"[data] N={len(d['cid_order'])} PT={d['Ym'].shape[1]} (동결 master_X/Y 읽기 전용)")
    blocks = make_blocks(d)

    verify = measure = run = cons = units = None
    if args.stage in ("verify", "all"):
        verify, units = stage_verify(d, blocks, g0)
        dump_json(os.path.join(BASE_DIR, "_verify_state.json"), verify)
    else:
        p = os.path.join(BASE_DIR, "_verify_state.json")
        verify = json.load(open(p)) if os.path.exists(p) else None
    if units is None and args.stage in ("measure", "run", "all"):
        units, _rows, _cal = inner_units(d)

    if args.stage in ("measure", "all"):
        assert verify and verify["equivalence"]["byte_identical"], \
            "P-2-1 재적합 바이트 동일성 미확인 — 계측·본계산 금지"
        measure = stage_measure(d, blocks, units, verify)
    else:
        p = os.path.join(BASE_DIR, "measure_public.json")
        measure = json.load(open(p)) if os.path.exists(p) else None

    if args.stage in ("run", "all"):
        assert verify and verify["equivalence"]["byte_identical"], \
            "P-2-1 재적합 바이트 동일성 미확인 — 본계산 금지"
        assert measure and not measure["exceeds_threshold"], \
            "P-3 계측 미수행 또는 7일 초과 — 본계산 금지"
        run = stage_run(d, blocks, units)
        dump_json(os.path.join(BASE_DIR, "_run_state.json"), run)
    else:
        p = os.path.join(BASE_DIR, "_run_state.json")
        run = json.load(open(p)) if os.path.exists(p) else None

    if args.stage in ("consensus", "all"):
        assert run and run["total"] == N_UNITS, "본계산 미완주 — consensus 금지"
        cons = stage_consensus(d)
        dump_json(os.path.join(BASE_DIR, "_consensus_state.json"), cons)
    else:
        p = os.path.join(BASE_DIR, "_consensus_state.json")
        cons = json.load(open(p)) if os.path.exists(p) else None

    if args.stage == "public":
        assert run and cons, "public 스테이지 — 선행 run/consensus 상태 파일 부재"
        snap = sealed_guard_snapshot()
        own = {k: v for k, v in snap.items() if k.startswith(OWN_PREFIXES)}
        n_foreign = len(snap) - len(own)
        assert n_foreign == 184, f"선재 봉인 {n_foreign} != 184 — 본 블록 밖 신규 발생"
        mismatched = []
        for key, sha in {**run["sealed_sha256"], **cons["sealed_sha256"]}.items():
            hits = [k for k, v in own.items()
                    if k.endswith("/" + os.path.basename(key)) and v == sha]
            if not hits:
                mismatched.append(key)
        assert not mismatched, f"본 블록 봉인 산출물 sha 불일치 {mismatched[:3]}"
        gates["public_stage_sealed_recheck"] = {
            "n_preexisting_sealed": n_foreign, "preexisting_unchanged": True,
            "n_own_sealed": len(own), "own_sha_all_match": True}
        logln(f"[public] 봉인 무결성 재확인 PASS — 선재 {n_foreign}종 불변 · "
              f"본 블록 {len(own)}종 sha 전건 일치")

    gates["B_end"] = gate_b_exclusive("블록 P 종료")
    if all(x is not None for x in (verify, measure, run, cons)):
        pub = write_public(g0, gates, verify, measure, run, cons, grid)
        append_first_look({
            "ts_kst": now_kst(), "viewer": args.viewer,
            "step": "블록 P (Holm ⑦ late-fusion arm 산출)",
            "block": "P — RF late-fusion 상보성(RQ7) arm 확증 OOF", "status": "completed",
            "arms": ARM_FILES, "repeats": [1, 2, 3], "seeds": [201, 202, 203],
            "delta_sign": None,
            "delta_sign_note": ("Δ·부호를 산출하지도 공개하지도 않았다(docs/61 §1). "
                                "⑦ 은 Holm family 이므로 부호 노출도 조각 개봉이다. "
                                "λ 값도 결과-의존 선택량이라 전량 봉인했다."),
            "sealed_sha256": {**run["sealed_sha256"], **cons["sealed_sha256"]},
            "runner_asserts_passed": {
                "g0_freeze": True,
                "refit_byte_identity_every_unit": True,
                "inner_split_reproduction_matches_frozen_check": True,
                "inner_valid_97_all_units": True,
                "scaffold_group_cross_zero": True,
                "lambda_no_leak": True,
                "lambda_grid_21_points": True,
                "unmapped_245_bseq_exactly_zero": True,
                "leak_rows_zero_all_arms": True,
                "oof_shape_1092x370_no_nan": True,
                "rf_seed42_all_fits": True,
                "sealed_guard_unchanged": bool(run["sealed_guard_unchanged"]),
                "open_sealed_zero": True, "emit_sign_not_called": True,
                "decision_functions_not_called": True},
            "confirmatory": "Y",
            "note": ("확증 조회 = Y(값 미열람) — late-fusion arm OOF 를 생성하고 기존 M0 "
                     "sealed 를 machine_read 로 대조했다. open_sealed 0건 · "
                     "Δ·AP·CI·p·부호·λ 공개 0."),
        })
        print("\n" + "=" * 78)
        print("=== 블록 P 요약(개수·해시·게이트만) ===")
        print(f"완주 outer unit = {pub['n_completed_units']}/{N_UNITS} "
              f"(RF 적합 {pub['n_rf_fits_total']}회)")
        print(f"봉인 파일 = 반복별 {len(run['sealed_sha256'])}종 · "
              f"consensus {len(cons['sealed_sha256'])}종")
        print(f"재적합 바이트 동일성 = {pub['refit_byte_identity_assert']['verify_stage']} "
              f"(전 {pub['refit_byte_identity_assert']['n_units_asserted']} unit assert)")
        print(f"내부 분할 재현 = 동결 검증표 전건 일치 · inner-valid {EXPECT_INNER_VALID} · "
              f"group 교차 0")
        print(f"동결파일 sha256 = {pub['freeze_sha256']}")
        print(f"sealed guard {pub['sealed_guard_n_files']}종 불변 = "
              f"{pub['sealed_guard_unchanged']}")
        print("Δ·AP·CI·p·부호·λ = 전량 봉인 (공개 0)")
    flush_log()


if __name__ == "__main__":
    with ComputeLock(script="confirmatory_latefusion.py", role="runner"):
        main()
