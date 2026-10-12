#!/usr/bin/env python3
"""confirmatory_oof_rftuned.py — 블록 O: Holm ⑥ `RF_tuned` baseline 확증 OOF (arm 1개).

정본 스펙: `docs/60_v3_rf_tuned_prompt_for_vscode.md` (개정판 v2, 2026-08-06)
확정본  : `v3_Multimodal/config/post_interim_freeze_v1_0.json` → `holm6_rf_tuned`
실행동결: `v3_Multimodal/config/rf_tuned_freeze.json` (블록 O-0 이 생성 — 수정 금지)

⛔ 무결성 최상위
  - **개봉 없음**: `SealedStore.open_sealed` 미호출 · `_sealed/` 값의 사람 판독형 출력 0.
  - **성공판정·다중성 없음**: `sap/decision.py` 의 `rq*_decision`·`holm`·`bh_fdr`·
    `tost_equivalence` 미호출(import 조차 하지 않는다).
  - **Δ·부호 없음**: `emit_sign` 미호출. 본 블록은 **arm 하나의 OOF 산출물만** 만든다.
    ⑥ 은 Holm family 이므로 부호 노출도 조각 개봉이다.
  - **재튜닝 없음**: 하이퍼파라미터·지문 반경을 확증 데이터로 고르거나 바꾸지 않는다.
  - **기존 동결물 무수정**: `ladder_freeze.json`·`ladder_confirmatory.py`·`confirmatory_oof_*.py`·
    `sap/*`·`docs/29`·`docs/30`. 기존 `_sealed/` 덮어쓰기 0(신규 디렉터리에만 쓴다).
  - split·fold·seed 재추첨 0(`folds.json` 판독만) · 네트워크 0 · git commit·push 0.

★ 원본 무수정 원칙 하의 **복사** (지시서 O-5 — 리포트에 열거)
  `confirmatory_oof_rest.py` 의 다음 함수는 `REST_MODELS`/`MODEL_BLOCKS`/`RF_KW` 하드코딩에
  막혀 그대로 재사용할 수 없어 최소 로직만 본 파일에 복사했다(원본은 한 바이트도 고치지 않음):
    · `rf_fit_predict` (ladder_confirmatory) → `rf_fit_predict_tuned`
        사유: `RF_KW` 가 모듈 상수(n_estimators=300 · class_weight="balanced_subsample")라
              tuned 하이퍼셋(1000 · 40 · sqrt · 2 · balanced)을 주입할 수 없다.
    · `predict_fold` → `predict_fold_tuned`
        사유: `MODEL_BLOCKS[model]` 을 참조하는데 `RF_tuned` 는 동결 사다리 모델이 아니다.
    · `stage_run` / `stage_consensus` / `write_public`
        사유: `REST_MODELS` 순회 + `v3_confirm_rest*` 경로 하드코딩.
    · `sealed_guard_snapshot`
        사유: 원본은 6개 디렉터리 고정 목록. 지시서 O-1-3 은 `experiments/runs/**/_sealed/**`
              **실측 전수**(access.log 제외, 159종)를 요구한다 → glob 판(더 강함)으로 대체.
  그 외 게이트·로더·정합·봉인·기록 경로는 전부 **import 재사용**한다.

실행:
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rftuned.py --stage verify
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rftuned.py --stage measure
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rftuned.py --stage run
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rftuned.py --stage consensus
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rftuned.py --stage all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier

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
    log_machine_read, append_first_look, fit_fold, predict_fold, needed_blocks,
)
from ladder_confirmatory import (                                        # noqa: E402
    load_frozen, MorganBlock, MODEL_BLOCKS, FROZEN_MODELS, SEED,
)
import ladder_confirmatory as LC                                         # noqa: E402
from sap import consensus as sap_consensus                               # noqa: E402
from sap import metrics as sap_metrics                                   # noqa: E402
from sap import redaction as sap_redaction                               # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
# 사전 고정 상수 (결과 조회 전 확정 — 실행 중 변경 금지)
# ═══════════════════════════════════════════════════════════════════════════
MODEL = "RF_tuned"
EQUIV_MODEL = "M0"                 # 코드경로 동일성 증명 대상(동결 사다리·기존 sealed 존재)
EQUIV_REP, EQUIV_FOLD = 1, 0
ABORT_DAYS = 7.0
N_MODEL_FOLD = N_FOLD * len(SEED_MAP)          # 15

CONFIG_DIR = os.path.join(ROOT, "v3_Multimodal", "config")
RF_TUNED_FREEZE = os.path.join(CONFIG_DIR, "rf_tuned_freeze.json")
RUNS = os.path.join(ROOT, "experiments", "runs")
BASE_DIR = os.path.join(RUNS, "v3_confirm_rftuned")
SEALED_BASE = os.path.join(BASE_DIR, "_sealed")
# 부분 산출물은 **원시 예측**이므로 블록 I 관례대로 `_sealed/` 안에 둔다(공개 경로 금지).
WORK_DIR = os.path.join(SEALED_BASE, "_partial")
CKPT = os.path.join(SEALED_BASE, "checkpoint.jsonl")
ENV_FP = os.path.join(SEALED_BASE, "env_fingerprint.json")
CONS_DIR = os.path.join(RUNS, "v3_confirm_rftuned_consensus_rep123")
PROMPT = os.path.join(ROOT, "docs", "60_v3_rf_tuned_prompt_for_vscode.md")
DOC33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")

# 기존 M0 봉인 산출물(블록 I) — 코드경로 동일성 대조용 (읽기만)
def rest_sealed_of(r):
    return os.path.join(RUNS, f"v3_confirm_rest_rep{r}_seed{SEED_MAP[r]}", "_sealed")


def run_dir_of(r):
    return os.path.join(RUNS, f"v3_confirm_rftuned_rep{r}_seed{SEED_MAP[r]}")


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


OWN_PREFIXES = ("experiments/runs/v3_confirm_rftuned",)


def sealed_guard_snapshot():
    """`experiments/runs/**/_sealed/**` 전수(access.log 제외) 경로→sha256."""
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
    """선재 봉인물은 **전건 불변**, 신규 추가는 **본 블록 디렉터리에서만** 발생해야 한다."""
    changed = [k for k in start if end.get(k) != start[k]]
    assert not changed, f"[{label}] 기존 봉인 산출물 변경/삭제 {len(changed)}건: {changed[:3]}"
    added = [k for k in end if k not in start]
    foreign = [k for k in added if not k.startswith(OWN_PREFIXES)]
    assert not foreign, f"[{label}] 본 블록 밖 봉인 신규 생성 {len(foreign)}건: {foreign[:3]}"
    return {"n_preexisting": len(start), "n_added_own": len(added), "n_foreign": 0,
            "preexisting_unchanged": True}


# ═══════════════════════════════════════════════════════════════════════════
# B0_r3 — MorganBlock 상속. 동일 코드경로, **반경 상수만** 일시 치환 후 원복.
# ═══════════════════════════════════════════════════════════════════════════
class MorganBlockR3(MorganBlock):
    """B0_r3 — 동결 `MorganBlock.__init__` 을 그대로 실행하되 radius 만 3.

    `ladder_confirmatory.py` 를 수정하지 않기 위해 모듈 상수 `MORGAN_RADIUS` 를
    호출 구간에만 3 으로 치환하고 finally 에서 원복한다(단일 스레드·동기 실행).
    결과적으로 생성기 인자·지문 추출 호출·dtype 이 r=2 와 **완전히 동일**하고
    반경 하나만 다르다(O-0-4 가 AST 로 이미 검증).
    """
    name = "B0_r3_morgan"
    RADIUS = 3

    def __init__(self, smiles, cid_order):
        old = LC.MORGAN_RADIUS
        assert old == 2, f"동결 MORGAN_RADIUS 실측 {old} != 2"
        try:
            LC.MORGAN_RADIUS = self.RADIUS
            super().__init__(smiles, cid_order)
        finally:
            LC.MORGAN_RADIUS = old
        assert LC.MORGAN_RADIUS == 2, "MORGAN_RADIUS 원복 실패"
        self.radius = self.RADIUS


# ═══════════════════════════════════════════════════════════════════════════
# tuned RF 하네스 (복사 — 사유는 모듈 docstring)
# ═══════════════════════════════════════════════════════════════════════════
def load_freeze():
    fz = json.load(open(RF_TUNED_FREEZE, encoding="utf-8"))
    e = fz["estimator"]
    assert e["n_estimators"] == 1000 and e["max_depth"] == 40
    assert e["max_features"] == "sqrt" and e["min_samples_leaf"] == 2
    assert e["class_weight"] == "balanced" and e["random_state"] == 42
    assert fz["block"]["radius"] == 3 and fz["block"]["n_bits"] == 2048
    assert fz["provenance"]["retuned"] is False and fz["provenance"]["test_used"] is False
    return fz


def tuned_rf_kw(fz):
    e = fz["estimator"]
    return dict(n_estimators=e["n_estimators"], max_depth=e["max_depth"],
                max_features=e["max_features"], min_samples_leaf=e["min_samples_leaf"],
                class_weight=e["class_weight"], n_jobs=e["n_jobs"])


def rf_fit_predict_tuned(Xtr, Ytr, Xeval, rf_kw, seed=SEED):
    """`ladder_confirmatory.rf_fit_predict` 와 **동일 구조**, 하이퍼셋만 tuned."""
    clf = MultiOutputClassifier(RandomForestClassifier(random_state=seed, **rf_kw))
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xeval.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xeval)[:, cls.index(1)]
    return P


def predict_fold_tuned(block, tr, te, Y, rf_kw):
    """RF_tuned 1 fold — 피처는 `B0_r3` 단독(표적 유래 블록 없음)."""
    Xtr = block.transform(tr).astype(np.float32)
    Xte = block.transform(te).astype(np.float32)
    assert RF_SEED == 42, "RF random_state != 42"
    P = rf_fit_predict_tuned(Xtr, Y[tr], Xte, rf_kw, seed=RF_SEED)
    return P, int(Xtr.shape[1])


# ═══════════════════════════════════════════════════════════════════════════
# 게이트
# ═══════════════════════════════════════════════════════════════════════════
def gate_prelook_recorded():
    txt = open(DOC33, encoding="utf-8").read()
    assert "판독확정(pre-look, 블록 O-0)" in txt, "[O-0] docs/33 pre-look 기입 없음 — 착수 금지"
    logln("[O-0] docs/33 판독확정(pre-look) 기입 확인 — 착수 허용")
    return {"prelook_recorded": True, "docs33_sha16": sha256_file(DOC33)[:16]}


def gate_block():
    """G-BLOCK — 착수 차단 플래그가 해제됐는지 실측."""
    st = json.load(open(os.path.join(CONFIG_DIR, "post_interim_freeze_v1_0.status.json"),
                        encoding="utf-8"))
    blocked = st["holm67_start_still_blocked_until_reply"]
    assert blocked is False, "holm67_start_still_blocked_until_reply == true → 보류"
    pi_sha = sha256_file(os.path.join(CONFIG_DIR, "post_interim_freeze_v1_0.json"))
    assert pi_sha[:16] == "502db732bd5e45cb", f"post_interim sha16 {pi_sha[:16]} 불일치"
    logln("[G-BLOCK] PASS — holm67_start_still_blocked_until_reply=False · "
          f"post_interim sha16={pi_sha[:16]}")
    return {"holm67_start_still_blocked_until_reply": False,
            "post_interim_sha256": pi_sha,
            "post_interim_status_sha256": sha256_file(
                os.path.join(CONFIG_DIR, "post_interim_freeze_v1_0.status.json"))}


def gate_holm_family():
    """G-HOLM — decision.py 를 **소스 판독**(import·실행 아님)."""
    import ast
    src = open(os.path.join(HERE, "sap", "decision.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    node = next(n for n in tree.body
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", None) == "HOLM_FAMILY" for t in n.targets))
    labels = [ast.literal_eval(e) for e in node.value.elts]
    assert len(labels) == 7, f"HOLM_FAMILY {len(labels)} 라벨 (기대 7)"
    assert "M2b-RF_tuned" in labels, "HOLM_FAMILY 에 M2b-RF_tuned 부재"
    logln(f"[G-HOLM] PASS — decision.py:{node.lineno} · 7 라벨 · M2b-RF_tuned 포함")
    return {"line": node.lineno, "n_labels": len(labels), "labels": labels}


def gate_no_existing_outputs():
    """지시서 O-1: ⑥ 산출물이 이미 있으면 중단(1회성 조건)."""
    existing = []
    for r in (1, 2, 3):
        p = os.path.join(run_dir_of(r), "_sealed", f"oof_{MODEL}.npz")
        if os.path.exists(p):
            existing.append(os.path.relpath(p, ROOT))
    p = os.path.join(CONS_DIR, "_sealed", f"consensus_{MODEL}.npz")
    if os.path.exists(p):
        existing.append(os.path.relpath(p, ROOT))
    assert not existing, f"⑥ 산출물이 이미 존재 — 덮어쓰기 금지: {existing}"
    return {"preexisting_rftuned_outputs": 0}


# ═══════════════════════════════════════════════════════════════════════════
# O-3  정합 · 바이트 동일성 (하드 게이트)
# ═══════════════════════════════════════════════════════════════════════════
def stage_verify(d, g0, fz):
    N = len(d["cid_order"])
    Y = d["Ym"]
    inputs = gate_inputs()
    guard = sealed_guard_snapshot()
    n_foreign = sum(1 for k in guard if not k.startswith(OWN_PREFIXES))
    logln(f"[O-1-3] sealed guard 스냅샷 {len(guard)}종 기록(착수) — 선재 봉인 {n_foreign}종")
    assert n_foreign == 159, f"선재 sealed guard 실측 {n_foreign} != 159"

    # ── O-3-3 fold 정합 (블록 I 와 동일 검사) ──
    checks = {"n_drugs": N, "n_pt": int(Y.shape[1]), "reps": {}}
    assert N == EXPECT_N_DRUGS and Y.shape[1] == EXPECT_N_PT, "master_X/Y 규모 불일치"
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
    logln(f"[O-3-3] fold 정합 PASS — 약물 {N} · scaffold group "
          f"{checks['reps']['rep1']['n_scaffold_groups']} · fold 교차 0 · rare-PT 위반 0 (3반복)")

    # ── O-3-1 코드경로 동일성: M0 rep1 fold0 재계산 → 기존 봉인 슬라이스와 바이트 비교 ──
    b0 = MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    blocks_m0 = {"B0": b0}
    assert EQUIV_MODEL in MODEL_BLOCKS and EQUIV_MODEL in FROZEN_MODELS
    assert MODEL_BLOCKS[EQUIV_MODEL] == ["B0"], "M0 블록 정의가 [B0] 가 아니다"
    fr = fold_of_row_for(EQUIV_REP, d["cid_order"])
    te = np.where(fr == EQUIV_FOLD)[0]
    tr = np.where(fr != EQUIV_FOLD)[0]
    t0 = time.perf_counter()
    leak, order = fit_fold(blocks_m0, EQUIV_MODEL, tr, d, N)
    P, dim = predict_fold(blocks_m0, EQUIV_MODEL, tr, te, Y)   # 동결 RF 하네스(재사용)
    wall_equiv = time.perf_counter() - t0
    repro = np.zeros((len(te), Y.shape[1]), dtype=np.float64)
    repro[:] = P

    ref_dir = rest_sealed_of(EQUIV_REP)
    ref_path = os.path.join(ref_dir, f"oof_{EQUIV_MODEL}.npz")
    log_machine_read(ref_dir, os.path.relpath(ref_path, ROOT),
                     "O-3-1 코드경로 바이트 동일성 증명(M0 fold0 슬라이스 비교)", "블록 O-3")
    with np.load(ref_path) as z:
        ref_oof, ref_fold, ref_cid = z["oof"], z["fold"], z["cid"]
    assert np.array_equal(ref_fold, fr), "봉인 npz fold 배열이 rep1 folds.json 과 불일치"
    assert np.array_equal(ref_cid, np.array([int(c) for c in d["cid_order"]])), \
        "봉인 npz cid 배열이 master_X 정렬과 불일치"
    ref_slice = np.ascontiguousarray(ref_oof[te])
    byte_identical = (repro.dtype == ref_slice.dtype
                      and repro.shape == ref_slice.shape
                      and repro.tobytes() == ref_slice.tobytes())
    equiv = {"model": EQUIV_MODEL, "repeat": EQUIV_REP, "fold": EQUIV_FOLD,
             "n_test_rows": int(len(te)), "n_pt": int(Y.shape[1]), "dim": dim,
             "dtype": str(repro.dtype), "blocks_fit": order, "leak_rows": leak,
             "byte_identical": bool(byte_identical), "wall_s": wall_equiv,
             "ref_npz": os.path.relpath(ref_path, ROOT),
             "ref_npz_sha256": sha256_file(ref_path),
             "note": ("재계산 산출물은 어디에도 저장하지 않고 폐기했다(지시서 O-3-1). "
                      "기존 봉인은 읽기만 했다(machine_read).")}
    logln(f"[O-3-1] 코드경로 동일성 — {EQUIV_MODEL} rep{EQUIV_REP} fold{EQUIV_FOLD} "
          f"({len(te)}행 × {Y.shape[1]}PT, dim={dim}) 바이트 동일 = {byte_identical} "
          f"| wall {wall_equiv:.1f}s (수치 미기록 — redaction)")
    if not byte_identical:
        logln("[O-3-1] ❌ 바이트 동일성 FAIL — 본계산 착수 금지, 즉시 중단")
        flush_log()
        sys.exit(11)
    del repro, ref_oof, ref_slice

    # ── O-3-2 B0_r3 정합 ──
    b3 = MorganBlockR3(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    assert b3.M.shape == (EXPECT_N_DRUGS, 2048), f"B0_r3 shape {b3.M.shape}"
    assert b3.M.dtype == b0.M.dtype, f"dtype {b3.M.dtype} != {b0.M.dtype}"
    assert b3.M.shape == b0.M.shape, "B0_r3 / B0 shape 불일치"
    assert b3.n_fail == b0.n_fail, f"SMILES→mol 실패 수 {b3.n_fail} != {b0.n_fail}"
    assert b3.dim == b0.dim == 2048
    same = bool(np.array_equal(b3.M, b0.M))
    assert not same, "B0_r3 가 B0(r=2) 와 동일 행렬 — 반경 인자 미적용 버그. 즉시 중단"
    dens_r2 = float(b0.M.mean())
    dens_r3 = float(b3.M.mean())
    n_rows_differ = int((b3.M != b0.M).any(axis=1).sum())
    # 행 순서 동일성: 두 블록 모두 master_X cid 정렬 그대로 (동일 입력 리스트·동일 루프)
    row_order_ok = list(d["X"]["cid"].astype(int)) == [int(c) for c in d["cid_order"]]
    assert row_order_ok, "master_X 행 순서 불일치"
    # O-3-4 누수 assert: 결정적 지문 → fit 모집단 공집합
    b3.fit(tr)
    rec = b3.leakage_assert(tr)
    assert rec["leak_rows"] == 0 and int(b3._fit_rows_mask.sum()) == 0, \
        "B0_r3 fit 모집단이 공집합이 아니다(결정적 지문이어야 함)"
    fp = {"shape": list(b3.M.shape), "dtype": str(b3.M.dtype), "n_fail_r3": int(b3.n_fail),
          "n_fail_r2": int(b0.n_fail), "identical_to_r2": same,
          "n_rows_differing_from_r2": n_rows_differ,
          "bit_density_r2": dens_r2, "bit_density_r3": dens_r3,
          "row_order_matches_master_X": row_order_ok,
          "fit_rows_mask_empty": True, "leak_rows": 0,
          "note": ("비트 밀도는 결과 계열이 아니라 지문 자체의 성질이므로 공개 가능"
                   "(지시서 O-3-2).")}
    logln(f"[O-3-2] B0_r3 정합 PASS — shape {b3.M.shape} dtype {b3.M.dtype} · "
          f"mol 실패 {b3.n_fail}(=r2) · r2 와 동일행렬 아님(차이 행 {n_rows_differ}/"
          f"{EXPECT_N_DRUGS}) · 비트밀도 r2 {dens_r2:.4f} → r3 {dens_r3:.4f}")
    logln("[O-3-4] 누수 assert PASS — B0_r3 는 fit 없음(_fit_rows_mask 공집합)")

    guard_end = sealed_guard_snapshot()
    gchk = assert_guard_unchanged(guard, guard_end, "O-3 verify")
    out = {"ts_kst": now_kst(), "gate0": g0, "inputs": inputs, "sealed_guard_check": gchk,
           "consistency_checks": checks, "equivalence": equiv, "b0_r3": fp,
           "freeze_sha256": sha256_file(RF_TUNED_FREEZE),
           "sealed_guard_n_files": len(guard), "sealed_guard_unchanged": True}
    dump_json(os.path.join(BASE_DIR, "verify_public.json"), out)
    return out, b3


# ═══════════════════════════════════════════════════════════════════════════
# O-4  계측 (필수 · 7일 초과 시 중단)
# ═══════════════════════════════════════════════════════════════════════════
def stage_measure(d, b3, fz):
    Y = d["Ym"]
    rf_kw = tuned_rf_kw(fz)
    fr = fold_of_row_for(1, d["cid_order"])
    te = np.where(fr == 0)[0]
    tr = np.where(fr != 0)[0]
    t0 = time.perf_counter()
    P, dim = predict_fold_tuned(b3, tr, te, Y, rf_kw)
    wall = time.perf_counter() - t0
    del P
    total_s = wall * N_MODEL_FOLD
    est = {"measured_model": MODEL, "measured_dim": dim, "measured_wall_s": wall,
           "n_model_fold_total": N_MODEL_FOLD,
           "estimated_total_wall_s": total_s,
           "estimated_total_wall_hours": total_s / 3600.0,
           "estimated_total_wall_days": total_s / 86400.0,
           "abort_threshold_days": ABORT_DAYS,
           "exceeds_threshold": bool(total_s / 86400.0 > ABORT_DAYS),
           "peak_rss_gib": peak_rss_gib(),
           "docs48_prior_estimate_note": (
               "docs/48 §7 의 '약 24분' 은 동결 RF(n_estimators=300) 단가 외삽값이라 "
               "본 모델(n_estimators=1000·min_samples_leaf=2)에 적용하지 않는다 — 실측으로 대체."),
           "scaling_note": ("본 블록은 arm 1개·차원 고정(2048)이라 model-fold 단가가 균일하다. "
                            "따라서 차원비 스케일 없이 실측 단가 × 15 로 추정한다."),
           }
    logln(f"[O-4] 계측 — {MODEL} 1 model-fold(dim={dim}) wall {wall:.1f}s → "
          f"{N_MODEL_FOLD} model-fold 총 추정 {est['estimated_total_wall_hours']:.2f}h "
          f"({est['estimated_total_wall_days']:.4f}일) · 임계 {ABORT_DAYS}일 · "
          f"초과 = {est['exceeds_threshold']} | peak RSS {est['peak_rss_gib']:.2f} GiB")
    dump_json(os.path.join(BASE_DIR, "measure_public.json"), est)
    if est["exceeds_threshold"]:
        logln("[O-4] ❌ 추정 wall 7일 초과 — 실행하지 않고 중단(지시서 중단 조건)")
        flush_log()
        sys.exit(12)
    return est


# ═══════════════════════════════════════════════════════════════════════════
# O-5  본계산 (체크포인트 · 세션 분할 재개)
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
    return {"python_version": sys.version.split()[0], "numpy": np.__version__,
            "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__, "pandas": pd.__version__,
            "rdkit": __import__("rdkit").__version__,
            "ladder_freeze_sha256": sha256_file(
                os.path.join(CONFIG_DIR, "ladder_freeze.json")),
            "rf_tuned_freeze_sha256": sha256_file(RF_TUNED_FREEZE),
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
    keys = [(r["repeat"], r["model"], r["fold"]) for r in rows]
    dup = {k for k in keys if keys.count(k) > 1}
    assert not dup, f"[checkpoint] 중복 {sorted(dup)[:5]} — 즉시 중단"
    return rows


def ckpt_append(rec):
    os.makedirs(WORK_DIR, exist_ok=True)
    with open(CKPT, "a", encoding="utf-8") as f:
        f.write(json.dumps({k: rec.get(k) for k in CKPT_FIELDS}, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def partial_path(r, k):
    return os.path.join(WORK_DIR, f"rep{r}_{MODEL}_fold{k}.npy")


def stage_run(d, b3, fz):
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]
    rf_kw = tuned_rf_kw(fz)
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
    done_keys = {(r["repeat"], r["model"], r["fold"]) for r in done}
    session_seq = max((r.get("session_seq", 0) for r in done), default=0) + 1
    if done:
        logln(f"[재개] 세션 #{session_seq} · 기완주 {len(done_keys)}/{N_MODEL_FOLD} · "
              f"환경지문 일치={fp_match} {('차이=' + str(fp_diff)) if fp_diff else ''}")
        assert fp_match, f"[재개] 환경 지문 불일치 {fp_diff} — 중단"
        gate_c_settle("세션 재개 직전")

    guard_start = sealed_guard_snapshot()
    n_done_session = 0
    t_session = time.perf_counter()

    for r in (1, 2, 3):
        fr = fold_of_row_for(r, d["cid_order"])
        gate_b_exclusive(f"rep{r}/{MODEL}:before")
        for k in range(N_FOLD):
            if (r, MODEL, k) in done_keys:
                continue
            te = np.where(fr == k)[0]
            tr = np.where(fr != k)[0]
            t0 = time.perf_counter()
            b3.fit(tr)
            leak = b3.leakage_assert(tr)
            assert leak["leak_rows"] == 0 and int(b3._fit_rows_mask.sum()) == 0
            P, dim = predict_fold_tuned(b3, tr, te, Y, rf_kw)
            wall = time.perf_counter() - t0
            pp = partial_path(r, k)
            np.save(pp, P)
            rec = {"repeat": r, "model": MODEL, "fold": k,
                   "n_train": int(len(tr)), "n_test": int(len(te)), "dim": dim,
                   "wall_s": wall, "peak_rss_gib": peak_rss_gib(),
                   "sha256_partial": sha256_file(pp), "ts_kst": now_kst(),
                   "session_seq": session_seq, "leak_rows": 0}
            ckpt_append(rec)
            done_keys.add((r, MODEL, k))
            n_done_session += 1
            logln(f"[본계산] rep{r} {MODEL} fold{k} — train={len(tr)} test={len(te)} "
                  f"dim={dim} leak_rows=0 | wall {wall:.1f}s | 누계 "
                  f"{len(done_keys)}/{N_MODEL_FOLD} (수치 미기록 — redaction)")
        gate_b_exclusive(f"rep{r}/{MODEL}:after")

    assert len(done_keys) == N_MODEL_FOLD, f"완주 {len(done_keys)} != {N_MODEL_FOLD}"
    logln(f"[본계산] 전 {N_MODEL_FOLD} (rep,fold) 완주 — 세션 #{session_seq} "
          f"신규 {n_done_session}건")

    sealed_sha = {}
    for r in (1, 2, 3):
        fr = fold_of_row_for(r, d["cid_order"])
        store = sap_redaction.SealedStore(run_dir_of(r))
        os.makedirs(store.sealed_dir, exist_ok=True)
        oof = np.full((N, K), np.nan, dtype=np.float64)
        for k in range(N_FOLD):
            te = np.where(fr == k)[0]
            oof[te] = np.load(partial_path(r, k))
        assert not np.isnan(oof).any(), f"rep{r} {MODEL} OOF NaN 존재"
        assert oof.shape == (EXPECT_N_DRUGS, EXPECT_N_PT), f"rep{r} shape {oof.shape}"
        fn = f"oof_{MODEL}.npz"
        np.savez_compressed(os.path.join(store.sealed_dir, fn), oof=oof,
                            cid=np.array([int(c) for c in d["cid_order"]]), fold=fr)
        sealed_sha[f"rep{r}/{fn}"] = sha256_file(os.path.join(store.sealed_dir, fn))
        store.write_sealed("metrics_full.json", {
            "_warning": "SEALED — 성공판정(개봉) 전 열람 금지. Δ·부호 미산출(docs/60 §0).",
            "step": f"블록 O — Holm ⑥ RF_tuned 확증 OOF 반복{r}(seed {SEED_MAP[r]})",
            "ts_kst": now_kst(),
            "estimand": "사전등록 §7 primary — global 양성≥10 PT(370) macro AP, eligible_pt=None",
            "models": [MODEL],
            "macro_ap": {MODEL: sap_metrics.macro_ap(Y, oof, None)},
            "per_fold_macro_ap": {MODEL: [sap_metrics.macro_ap(Y[fr == k], oof[fr == k], None)
                                          for k in range(N_FOLD)]},
            "pt_columns": d["ycols"],
            "delta_not_computed": ("Δ·부호는 이 블록에서 산출하지 않는다. ⑥ 은 개봉 단계에서 "
                                   "M2b 와 대비한다."),
        })
        sealed_sha[f"rep{r}/metrics_full.json"] = sha256_file(
            os.path.join(store.sealed_dir, "metrics_full.json"))
        logln(f"[봉인] rep{r} — oof_{MODEL}.npz + metrics_full.json 저장 "
              f"({os.path.relpath(store.sealed_dir, ROOT)})")

    guard_end = sealed_guard_snapshot()
    gchk = assert_guard_unchanged(guard_start, guard_end, "O-5 run")
    return {"total": N_MODEL_FOLD, "session_seq": session_seq,
            "n_done_this_session": n_done_session,
            "session_wall_s": time.perf_counter() - t_session,
            "sealed_sha256": sealed_sha, "env_fingerprint_match": fp_match,
            "sealed_guard_check": gchk,
            "sealed_guard_n_files": len(guard_start), "sealed_guard_unchanged": True}


# ═══════════════════════════════════════════════════════════════════════════
# O-5  consensus (방법 A · 반복 순서 1→2→3 고정)
# ═══════════════════════════════════════════════════════════════════════════
def stage_consensus(d):
    Y = d["Ym"]
    t0 = time.perf_counter()
    store = sap_redaction.SealedStore(CONS_DIR)
    os.makedirs(store.sealed_dir, exist_ok=True)
    seq = []
    for r in (1, 2, 3):
        p = os.path.join(run_dir_of(r), "_sealed", f"oof_{MODEL}.npz")
        log_machine_read(os.path.join(run_dir_of(r), "_sealed"), os.path.relpath(p, ROOT),
                         f"consensus 입력(rep{r} {MODEL})", "블록 O consensus")
        with np.load(p) as z:
            seq.append(z["oof"])
    assert all(a.shape == (EXPECT_N_DRUGS, EXPECT_N_PT) for a in seq), "반복 OOF shape 불일치"
    cons = sap_consensus.build_consensus(seq)
    fn = f"consensus_{MODEL}.npz"
    np.savez_compressed(os.path.join(store.sealed_dir, fn), consensus=cons,
                        cid=np.array([int(c) for c in d["cid_order"]]))
    sealed_sha = {fn: sha256_file(os.path.join(store.sealed_dir, fn))}
    store.write_sealed("metrics_full.json", {
        "_warning": "SEALED — 성공판정(개봉) 전 열람 금지. Δ·부호 미산출(docs/60 §0).",
        "step": "블록 O — RF_tuned consensus(반복1·2·3)", "ts_kst": now_kst(),
        "method": sap_consensus.CONSENSUS_METHOD, "models": [MODEL],
        "macro_ap": {MODEL: sap_metrics.macro_ap(Y, cons, None)},
        "per_repeat_macro_ap": {MODEL: sap_consensus.repeat_macro_aps(
            seq, Y, sap_metrics.macro_ap, None)},
        "pt_columns": d["ycols"],
        "delta_not_computed": "Δ·부호 미산출 — 개봉 단계에서 일괄.",
    })
    sealed_sha["metrics_full.json"] = sha256_file(
        os.path.join(store.sealed_dir, "metrics_full.json"))
    wall = time.perf_counter() - t0
    logln(f"[consensus] {MODEL} — 반복 3개 산술평균(방법A) 봉인 저장 "
          f"({os.path.relpath(CONS_DIR, ROOT)}) | wall {wall:.1f}s (수치 미기록)")
    return {"n_models": 1, "method": sap_consensus.CONSENSUS_METHOD,
            "dir": os.path.relpath(CONS_DIR, ROOT), "sealed_sha256": sealed_sha,
            "wall_s": wall}


# ═══════════════════════════════════════════════════════════════════════════
# O-6  공개 요약 + 방어 assert
# ═══════════════════════════════════════════════════════════════════════════
SIGN_LITERALS = ("positive", "negative", "zero")
# 결과 계열이 아닌 **공개 허용** 실수 — 지문 비트 밀도(지시서 O-3-2 가 명시 허용)
FLOAT_ALLOW_KEYS = ("bit_density_r2", "bit_density_r3", "wall_s", "measured_wall_s",
                    "estimated_total_wall_s", "estimated_total_wall_hours",
                    "estimated_total_wall_days", "abort_threshold_days",
                    "peak_rss_gib", "session_wall_s", "load1")


def write_public(g0, gates, verify, measure, run, cons):
    pub = {
        "_scope": ("블록 O 공개 요약 — 형상·개수·차원·해시·소요시간·게이트 판정뿐. "
                   "Δ·macro AP·CI·p·부호 전량 봉인(docs/60 §0·O-0-2 4)."),
        "ts_kst": now_kst(),
        "spec": "docs/60_v3_rf_tuned_prompt_for_vscode.md (개정판 v2)",
        "model": MODEL,
        "hypothesis": "Holm ⑥ (M2b − RF_tuned) 의 comparator arm 산출 — 대비는 본 블록 범위 밖",
        "freeze_file": "v3_Multimodal/config/rf_tuned_freeze.json",
        "freeze_sha256": verify["freeze_sha256"],
        "feature_dim": 2048,
        "n_repeats": len(SEED_MAP), "n_fold": N_FOLD,
        "gate0": {"ladder_freeze_sha16": g0["ladder_freeze_sha16"],
                  "sap_manifest_sha16": g0["sap_manifest_sha16"],
                  "sap_version": g0["sap_version"],
                  "sap_n_modules_verified": g0["sap_n_modules_verified"],
                  "sap_modules_all_match": all(g0["sap_modules_match"].values()),
                  "pass": bool(g0["gate0_pass"])},
        "gates": gates,
        "inputs_sha256": verify["inputs"],
        "consistency_checks": verify["consistency_checks"],
        "b0_r3": verify["b0_r3"],
        "code_path_equivalence_byte_identical": verify["equivalence"]["byte_identical"],
        "code_path_equivalence_detail": {
            k: v for k, v in verify["equivalence"].items()
            if k in ("model", "repeat", "fold", "n_test_rows", "dim", "dtype",
                     "leak_rows", "wall_s", "ref_npz")},
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
            "rf_random_state": RF_SEED,
            "note": "확증 반복1·2·3 및 블록 I 와 동일 조건(스레드 환경변수 미설정)."},
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__,
                     "scipy": __import__("scipy").__version__,
                     "rdkit": __import__("rdkit").__version__,
                     "platform": platform.platform()},
        "not_performed": ["개봉(open_sealed)", "성공판정(rq*_decision)", "Holm/BH 다중성",
                          "TOST/SESOI", "bootstrap CI", "sign-flip", "p-value",
                          "Δ 산출", "부호 산출(emit_sign)", "재튜닝·재탐색",
                          "기존 동결물 수정", "기존 _sealed 덮어쓰기",
                          "M1b·M2b·M0·M1·M2·P-ID·P-FAM·C-CAP 재계산",
                          "split·fold·seed 재추첨", "⑦ late-fusion", "⑧ GIN·RQ-int",
                          "A3·A4·A6 층화", "네트워크", "data/raw 변경", "git commit·push"],
        "open_sealed_calls": 0, "decision_functions_called": [],
        "multiplicity_applied": False, "emit_sign_called": False,
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
    keys = {p.rsplit(".", 1)[-1].split("[")[0] for p, _ in items}
    keys |= {k for k in _all_keys(parsed)}
    bad_keys = sorted(k for k in keys
                      if any(k == f or k.startswith(f) for f in FORBIDDEN_PUBLIC_KEYS))
    assert not bad_keys, f"공개 파일에 봉인 대상 키 노출: {bad_keys}"
    # 값 기준 스캔 — 실수는 허용목록 키에서만, 부호 어휘는 값으로 등장 금지
    bad_vals = []
    for p, v in items:
        leaf = p.rsplit(".", 1)[-1].split("[")[0]
        if isinstance(v, float) and leaf not in FLOAT_ALLOW_KEYS:
            bad_vals.append((p, v))
        if isinstance(v, str) and v.strip().lower() in SIGN_LITERALS:
            bad_vals.append((p, v))
    assert not bad_vals, f"공개 파일 값 스캔 위반: {bad_vals[:5]}"
    # 금지어 목록 자체가 스캔에 걸리는 오탐 방지(블록 L §5 전례) — 목록은 코드 상수이며
    # 공개 JSON 에 직렬화되지 않음을 확인한다.
    assert "FORBIDDEN_PUBLIC_KEYS" not in blob and "SIGN_LITERALS" not in blob
    dump_json(os.path.join(BASE_DIR, "rftuned_public.json"), pub)
    logln(f"[공개] rftuned_public.json 기록 — 봉인 대상 키 검출 0 "
          f"(키 {len(keys)}개·리프 {len(items)}개 스캔, 실수 허용목록 {len(FLOAT_ALLOW_KEYS)}종)")
    return pub


def _all_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _all_keys(v)


# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["verify", "measure", "run", "consensus", "all"],
                    default="all")
    ap.add_argument("--viewer", default="vscode-claude(runner)")
    args = ap.parse_args()

    os.makedirs(BASE_DIR, exist_ok=True)
    logln("=" * 78)
    logln(f"[블록 O] stage={args.stage} — Holm ⑥ tuned-RF baseline 확증 OOF "
          f"(arm 1개 · {N_MODEL_FOLD} model-fold). Δ·AP·CI·p·부호 전량 봉인.")

    gates = {}
    gates["A_entry"] = gate_a_load("블록 O 진입")
    gates["B_start"] = gate_b_exclusive("블록 O 시작")
    gates["prelook"] = gate_prelook_recorded()
    gates["G_BLOCK"] = gate_block()
    gates["G_HOLM"] = gate_holm_family()
    gates["no_existing_outputs"] = gate_no_existing_outputs()
    g0 = gate0_verify()
    fz = load_freeze()
    logln(f"[동결] rf_tuned_freeze.json sha256 {sha256_file(RF_TUNED_FREEZE)[:16]} 판독 — "
          f"estimator 6필드·block radius/bits assert PASS")

    d = load_frozen()
    logln(f"[data] N={len(d['cid_order'])} PT={d['Ym'].shape[1]} (동결 master_X/Y 읽기 전용)")

    verify = measure = run = cons = b3 = None
    if args.stage in ("verify", "all"):
        verify, b3 = stage_verify(d, g0, fz)
        dump_json(os.path.join(BASE_DIR, "_verify_state.json"), verify)
    else:
        p = os.path.join(BASE_DIR, "_verify_state.json")
        verify = json.load(open(p)) if os.path.exists(p) else None

    if b3 is None and args.stage in ("measure", "run", "all"):
        b3 = MorganBlockR3(d["X"]["smiles_canonical"].tolist(), d["cid_order"])

    if args.stage in ("measure", "all"):
        assert verify and verify["equivalence"]["byte_identical"], \
            "O-3-1 바이트 동일성 미확인 — 계측·본계산 금지"
        measure = stage_measure(d, b3, fz)
    else:
        p = os.path.join(BASE_DIR, "measure_public.json")
        measure = json.load(open(p)) if os.path.exists(p) else None

    if args.stage in ("run", "all"):
        assert verify and verify["equivalence"]["byte_identical"], \
            "O-3-1 바이트 동일성 미확인 — 본계산 금지"
        assert measure and not measure["exceeds_threshold"], \
            "O-4 계측 미수행 또는 7일 초과 — 본계산 금지"
        run = stage_run(d, b3, fz)
        dump_json(os.path.join(BASE_DIR, "_run_state.json"), run)
    else:
        p = os.path.join(BASE_DIR, "_run_state.json")
        run = json.load(open(p)) if os.path.exists(p) else None

    if args.stage in ("consensus", "all"):
        assert run and run["total"] == N_MODEL_FOLD, "본계산 미완주 — consensus 금지"
        cons = stage_consensus(d)
        dump_json(os.path.join(BASE_DIR, "_consensus_state.json"), cons)
    else:
        p = os.path.join(BASE_DIR, "_consensus_state.json")
        cons = json.load(open(p)) if os.path.exists(p) else None

    gates["B_end"] = gate_b_exclusive("블록 O 종료")
    if all(x is not None for x in (verify, measure, run, cons)):
        pub = write_public(g0, gates, verify, measure, run, cons)
        append_first_look({
            "ts_kst": now_kst(), "viewer": args.viewer, "step": "블록 O (Holm ⑥ arm 산출)",
            "block": "O — tuned-RF baseline 확증 OOF", "status": "completed",
            "models": [MODEL], "repeats": [1, 2, 3], "seeds": [201, 202, 203],
            "delta_sign": None,
            "delta_sign_note": ("Δ·부호를 산출하지도 공개하지도 않았다(docs/60 §0). "
                                "⑥ 은 Holm family 이므로 부호 노출도 조각 개봉이다."),
            "sealed_sha256": {**run["sealed_sha256"], **cons["sealed_sha256"]},
            "runner_asserts_passed": {
                "g0_freeze": True,
                "byte_identity_M0_rep1_fold0": bool(verify["equivalence"]["byte_identical"]),
                "b0_r3_not_identical_to_b0_r2": True,
                "b0_r3_fit_rows_empty": True,
                "leak_rows_zero": True,
                "oof_shape_1092x370_no_nan": True,
                "rf_seed42_all_folds": True,
                "sealed_guard_unchanged": bool(run["sealed_guard_unchanged"]),
                "open_sealed_zero": True, "emit_sign_not_called": True,
                "decision_functions_not_called": True},
            "confirmatory": "Y",
            "note": ("확증 조회 = Y(값 미열람) — RF_tuned OOF 를 생성하고 기존 M0 sealed 를 "
                     "machine_read 로 대조했다. open_sealed 0건 · Δ·AP·CI·p·부호 공개 0."),
        })
        print("\n" + "=" * 78)
        print("=== 블록 O 요약(개수·해시·게이트만) ===")
        print(f"완주 (rep,fold) = {pub['n_completed_model_folds']}/{N_MODEL_FOLD}")
        print(f"봉인 파일 = OOF {len(run['sealed_sha256'])}종 · "
              f"consensus {len(cons['sealed_sha256'])}종")
        print(f"코드경로 동일성(M0 rep1 fold0) = "
              f"{pub['code_path_equivalence_byte_identical']}")
        print(f"동결파일 sha256 = {pub['freeze_sha256']}")
        print(f"sealed guard {pub['sealed_guard_n_files']}종 불변 = "
              f"{pub['sealed_guard_unchanged']}")
        print("Δ·AP·CI·p·부호 = 전량 봉인 (공개 0)")
    flush_log()


if __name__ == "__main__":
    with ComputeLock(script="confirmatory_oof_rftuned.py", role="runner"):
        main()
