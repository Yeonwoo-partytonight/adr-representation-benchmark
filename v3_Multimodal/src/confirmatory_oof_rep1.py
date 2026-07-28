#!/usr/bin/env python3
"""confirmatory_oof_rep1.py — v3 §13-3 확증 OOF **반복1(seed 201)**: M1b·M2b Δ **부호만**.

정본 스펙: `docs/36_v3_confirmatory_oof_prompt_for_vscode.md` (사전등록 `docs/30` §6·§7·§8·§13 준수).

⛔ 무결성 최상위
  - 이 스크립트는 확증용 scaffold-그룹 CV split을 **최초 생성**하고, 그 OOF 예측을 **프로젝트 역사상
    처음 조회**한다. 되돌릴 수 없는 무결성 이벤트다.
  - 사람에게 노출되는 값 = **Δ(M2b−M1b)의 부호 1개**뿐(`positive`/`zero`/`negative`).
    원시 macro AP·Δ 크기·PT별·fold별·확률분포는 전부 `_sealed/`에만 저장(docs/36 §4-R).
  - bootstrap·sign-flip·p-value·SESOI·성공판정 **미실행**(§13-4/§13-5 이후 단계).
  - 반복 2·3(seed 202·203…) 미생성. 다른 모델(M0/M1/M2/P-ID/P-FAM/C-CAP) 미조회.
  - 네트워크 0. `data/raw/`·라벨·분자셋·구조·mean-pool·동결 블록 불변(읽기 전용).

2단 실행(Gate A를 사람 확인 지점으로 강제):
  1) `--stage split` : scaffold 그룹 5-fold split 생성 + 진단표만 산출. **OOF 미조회.**
  2) `--stage oof`   : (split 재검증 후) Gate B 로그 기록 → OOF 학습·예측 → 부호 1개 방출.

실행:
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rep1.py --stage split
  .venv/bin/python3 v3_Multimodal/src/confirmatory_oof_rep1.py --stage oof --viewer <이름>
"""
from __future__ import annotations

import os
import sys
import json
import random
import hashlib
import argparse
import platform
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)          # ladder_confirmatory (동결 레시피)
sys.path.insert(0, os.path.join(HERE, ".."))   # sap 패키지(src.sap 아님 — src 아래 sap/)

from rdkit import Chem                       # noqa: E402
from rdkit import RDLogger                   # noqa: E402
from rdkit.Chem.Scaffolds import MurckoScaffold   # noqa: E402

RDLogger.DisableLog("rdApp.*")

# ── 동결 레시피 재사용(재정의·재튜닝 금지) ─────────────────────────────────────
from ladder_confirmatory import (            # noqa: E402
    load_frozen, MorganBlock, CountMaskBlock, SeqBlock, M1bCovariateBlock,
    rf_fit_predict, MODEL_BLOCKS, RF_KW, SEED, PCA_K,
)
from sap import metrics as sap_metrics       # noqa: E402
from sap import redaction as sap_redaction   # noqa: E402
from sap import consensus as sap_consensus   # noqa: E402

KST = timezone(timedelta(hours=9))

# ── 사전 고정 상수 (결과 조회 전 확정 — 실행 중 변경 금지) ──────────────────────
SPLIT_SEED = 201            # 사전등록 §6: 반복1 = seed 201
N_FOLD = 5                  # 5 outer fold
RF_SEED = SEED              # 42 — 전 fold 공통(common random numbers, SAP A4)
ZERO_TOL = sap_redaction.ZERO_TOL   # 1e-6 (동결 redaction 모듈 상수)

# 게이트 A 하드 기준(결과-독립, 실행 전 고정)
GATE_A = {
    "scaffold_group_disjoint": "모든 scaffold group이 정확히 1개 fold에만 속함",
    "fold_size_band": "각 fold 크기 ∈ [0.10N, 0.30N]",
    "rare_pt_min_train_positive": 1,     # §6: 가능한 모든 outer training set에 PT별 최소 1개
    "rare_pt_soft_target": 3,            # §6: '가능하면 3개+' (보고만, 하드 실패 아님)
    "bseq_fit_rows_min": PCA_K,          # train∩매핑 ≥ PCA 성분 수
}

# ── 경로 ──────────────────────────────────────────────────────────────────────
PROC = os.path.join(ROOT, "data", "processed")
RUN_DIR = os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep1_seed201")
SPLIT_DIR = os.path.join(PROC, "splits", "confirmatory", "rep1_seed201")
PROV_DIR = os.path.join(ROOT, "experiments", "provenance")
FIRST_LOOK_LOG = os.path.join(PROV_DIR, "first_look_log.json")
DOCS33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
DOCS29 = os.path.join(ROOT, "docs", "29_v3.3_preregistration_advisor_approved.md")

CONFIG_FREEZE = os.path.join(ROOT, "v3_Multimodal", "config", "ladder_freeze.json")
SAP_MANIFEST = os.path.join(ROOT, "experiments", "sap", "manifest.json")
SAP_DIR = os.path.join(HERE, "sap")
AUDIT_DIR = os.path.join(ROOT, "experiments", "audits")

EXPECT_CONFIG_SHA16 = "b885585aefbabb32"     # docs/36 §0-3
EXPECT_MANIFEST_SHA16 = "756d485feb4715e9"   # docs/36 §5 게이트 0 (docs/43 v1.1)

_LOG_LINES = []


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    _LOG_LINES.append(line)


def flush_log():
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "run.log"), "a") as f:
        f.write("\n".join(_LOG_LINES) + "\n")
    _LOG_LINES.clear()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def native(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=native)
    return path


# ═══════════════════════════════════════════════════════════════════════════
# 게이트 0 — 선행 동결 검증 (docs/38 A0~A5 · docs/41 SAP v1.0 · docs/43 v1.1)
# ═══════════════════════════════════════════════════════════════════════════
def gate0_verify():
    logln("[게이트0] 선행 동결 검증 시작 — docs/38(A0~A5) + docs/41(SAP) + docs/43(재-동결 v1.1)")
    out = {}

    cfg_sha = sha256_file(CONFIG_FREEZE)
    out["ladder_freeze_sha256"] = cfg_sha
    out["ladder_freeze_sha16"] = cfg_sha[:16]
    out["ladder_freeze_match"] = (cfg_sha[:16] == EXPECT_CONFIG_SHA16)
    assert out["ladder_freeze_match"], f"ladder_freeze.json sha16 불일치: {cfg_sha[:16]} != {EXPECT_CONFIG_SHA16}"

    man_sha = sha256_file(SAP_MANIFEST)
    out["sap_manifest_sha256"] = man_sha
    out["sap_manifest_sha16"] = man_sha[:16]
    out["sap_manifest_match"] = (man_sha[:16] == EXPECT_MANIFEST_SHA16)
    assert out["sap_manifest_match"], f"SAP manifest sha16 불일치: {man_sha[:16]} != {EXPECT_MANIFEST_SHA16}"

    man = json.load(open(SAP_MANIFEST))
    out["sap_version"] = man["sap_version"]
    assert man["sap_version"] == "1.1", f"sap_version {man['sap_version']} != 1.1"
    out["sap_all_validation_pass"] = bool(man["all_validation_pass"])
    assert out["sap_all_validation_pass"], "SAP all_validation_pass=False"
    # SAP 모듈 live sha == manifest sha (11 모듈)
    mod_ok = {}
    for name, info in man["modules"].items():
        live = sha256_file(os.path.join(SAP_DIR, name))
        mod_ok[name] = (live == info["sha256"])
    out["sap_modules_match"] = mod_ok
    assert all(mod_ok.values()), f"SAP 모듈 sha 불일치: {[k for k, v in mod_ok.items() if not v]}"
    out["sap_n_modules_verified"] = len(mod_ok)
    # SAP 동결 시점 = 확증 미접근
    out["sap_integrity_confirmatory_untouched"] = bool(
        man["integrity"]["confirmatory_oof_accessed"] is False
        and man["integrity"]["confirmatory_split_generated"] is False)
    assert out["sap_integrity_confirmatory_untouched"], "SAP manifest integrity 플래그 위반"
    # primary 결합
    out["primary_B_m1b_dim"] = man["config_binding"]["primary_B_m1b_dim"]
    assert out["primary_B_m1b_dim"] == 10, "primary B_m1b dim != 10 (pChEMBL 제외판이어야 함)"

    # docs/38 하드닝 A0~A5 산출물 존재 + 핵심 PASS 플래그
    a1 = json.load(open(os.path.join(AUDIT_DIR, "A1_nested_fit_assert.json")))
    a5 = json.load(open(os.path.join(AUDIT_DIR, "A5_target_count_check.json")))
    a0 = json.load(open(os.path.join(AUDIT_DIR, "A0_m1b_reprimary_manifest.json")))
    out["A0_primary_dim"] = a0["primary_B_m1b"]["dim"]
    out["A1_all_blocks_train_only_fit"] = bool(a1["all_blocks_train_only_fit"])
    out["A1_bseq_pca_fit_rows"] = a1["b_seq_pca"]["n_fit_drug_rows"]
    out["A5_target_count_mismatch"] = a5["independent_recompute_mismatch"]
    assert out["A0_primary_dim"] == 10, "A0 primary dim != 10"
    assert out["A1_all_blocks_train_only_fit"], "A1 fold-only fit assert 실패"
    assert out["A5_target_count_mismatch"] == 0, "A5 target count mismatch != 0"
    for f in ["A2_split_diagnostics.json", "A3_rf_maxfeatures_note.md",
              "A4_bseq_truncation_audit_summary.json"]:
        assert os.path.exists(os.path.join(AUDIT_DIR, f)), f"docs/38 산출물 누락: {f}"

    out["gate0_pass"] = True
    logln(f"[게이트0] PASS — ladder_freeze={out['ladder_freeze_sha16']} "
          f"sap_manifest={out['sap_manifest_sha16']}(v{out['sap_version']}) "
          f"모듈 {out['sap_n_modules_verified']}/11 sha 일치 · A0~A5 PASS · primary B_m1b dim=10")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Split 생성 (사전등록 §6) — Bemis–Murcko scaffold group, 5 fold, seed 201
# ═══════════════════════════════════════════════════════════════════════════
def scaffold_of(smi):
    """Bemis–Murcko scaffold — pipeline/src/step6_scaffold_split.py와 **동일 정의**
    (MurckoScaffoldSmiles, includeChirality=False; 실패·무고리 → '')."""
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False)
    except Exception:
        return ""


def build_scaffold_groups(smiles, cids):
    groups = defaultdict(list)      # scaffold -> [row idx]
    for i, smi in enumerate(smiles):
        groups[scaffold_of(smi)].append(i)
    return dict(groups)


def assign_folds(groups, n, seed=SPLIT_SEED, k=N_FOLD):
    """사전등록 §6: '스캐폴드 그룹 셔플 후 목표비율(각 fold ≈20%) 순차배정'.

    - 사전 정렬(결정성 확보) = step6과 동일 키 (-size, 첫 cid 문자열) → `random.Random(seed).shuffle`.
    - 배정 = step6의 누적 cut 방식을 5 fold로 일반화: 누적합이 (i+1)N/k 를 넘지 않는 첫 fold에 배정,
      모두 초과하면 마지막 fold. (크기 재정렬 없음 — 셔플이 반복 간 유일한 무작위원.)
    """
    keys = sorted(groups.keys(), key=lambda s: (-len(groups[s]), str(groups[s][0])))
    order = list(keys)
    random.Random(seed).shuffle(order)
    cuts = [(i + 1) * n / k for i in range(k)]
    counts = [0] * k
    fold_of_group = {}
    for g in order:
        sz = len(groups[g])
        placed = False
        for i in range(k):
            if sum(counts[:i + 1]) + sz <= cuts[i]:
                fold_of_group[g] = i
                counts[i] += sz
                placed = True
                break
        if not placed:
            fold_of_group[g] = k - 1
            counts[k - 1] += sz
    return fold_of_group, order, counts


def split_diagnostics(d, fold_of_row, groups, fold_of_group):
    """§3 필수 리포트: fold별 약물·scaffold group 수, rare-PT 최소 train-positive,
    train/test 표적 Jaccard, fold 간 label density. (라벨·매핑은 고정 입력 = 결과 아님)"""
    N = len(fold_of_row)
    Y = d["Ym"]
    K = Y.shape[1]
    cid_order = d["cid_order"]
    cid2t = d["cid2targets"]
    mask = d["mask"].astype(bool)

    # scaffold 무누수 assert
    for g, rows in groups.items():
        f = {fold_of_row[i] for i in rows}
        assert len(f) == 1, f"scaffold group '{g[:40]}' 이 {sorted(f)} 여러 fold에 걸침"

    folds = []
    rare_hard_fail = 0
    for kf in range(N_FOLD):
        te = np.where(fold_of_row == kf)[0]
        tr = np.where(fold_of_row != kf)[0]
        pos_tr = Y[tr].sum(0)
        pos_te = Y[te].sum(0)
        tset_tr = set().union(*[cid2t.get(int(cid_order[i]), set()) for i in tr]) if len(tr) else set()
        tset_te = set().union(*[cid2t.get(int(cid_order[i]), set()) for i in te]) if len(te) else set()
        inter, union = len(tset_tr & tset_te), len(tset_tr | tset_te)
        n_lt1 = int((pos_tr < 1).sum())
        rare_hard_fail += n_lt1
        folds.append({
            "fold": kf,
            "n_test_drugs": int(len(te)),
            "n_train_drugs": int(len(tr)),
            "n_test_scaffold_groups": int(len({g for g, f in fold_of_group.items() if f == kf})),
            "n_test_mapped_drugs": int(mask[te].sum()),
            "n_train_mapped_drugs": int(mask[tr].sum()),
            "train_positive_per_pt": {
                "min": int(pos_tr.min()), "median": float(np.median(pos_tr)), "max": int(pos_tr.max()),
                "n_pt_lt1": n_lt1, "n_pt_lt3": int((pos_tr < 3).sum()),
            },
            "test_positive_per_pt": {
                "min": int(pos_te.min()), "median": float(np.median(pos_te)),
                "n_pt_zero_positive": int((pos_te == 0).sum()),
            },
            "label_density_test": float(Y[te].sum() / (len(te) * K)),
            "label_density_train": float(Y[tr].sum() / (len(tr) * K)),
            "target_jaccard_train_test": float(inter / union) if union else 0.0,
            "n_targets_train": len(tset_tr), "n_targets_test": len(tset_te),
        })

    dens = [f["label_density_test"] for f in folds]
    sizes = [f["n_test_drugs"] for f in folds]
    gate = {
        "scaffold_group_disjoint": True,      # 위 assert 통과
        "fold_size_band_ok": all(0.10 * N <= s <= 0.30 * N for s in sizes),
        "rare_pt_min1_all_train_folds": rare_hard_fail == 0,
        "n_pt_lt3_max_over_folds": max(f["train_positive_per_pt"]["n_pt_lt3"] for f in folds),
        "bseq_fit_rows_ok": all(f["n_train_mapped_drugs"] >= GATE_A["bseq_fit_rows_min"] for f in folds),
    }
    gate["gate_A_pass"] = bool(gate["scaffold_group_disjoint"] and gate["fold_size_band_ok"]
                               and gate["rare_pt_min1_all_train_folds"] and gate["bseq_fit_rows_ok"])
    return {
        "n_drugs": N, "n_pt": K, "n_scaffold_groups": len(groups),
        "fold_sizes": sizes,
        "label_density_test_spread": {"min": float(min(dens)), "max": float(max(dens)),
                                      "range": float(max(dens) - min(dens))},
        "folds": folds,
        "gate_A": gate,
    }


def stage_split(args):
    g0 = gate0_verify()
    logln("[stage=split] 확증용 scaffold-그룹 5-fold split **최초 생성** (OOF 미조회)")
    d = load_frozen()
    N = len(d["cid_order"])
    smiles = d["X"]["smiles_canonical"].tolist()
    logln(f"[data] N={N} PT={d['Ym'].shape[1]} (동결 master_X/master_Y 읽기 전용)")

    groups = build_scaffold_groups(smiles, d["cid_order"])
    empty_sz = len(groups.get("", []))
    sizes = sorted((len(v) for v in groups.values()), reverse=True)
    # A2(docs/38) 진단과 동일성 교차검증 — scaffold 정의가 동결본과 일치함을 증명
    a2 = json.load(open(os.path.join(AUDIT_DIR, "A2_split_diagnostics.json")))
    a2_inc = a2["scaffold_groups"]["including_empty_scaffold"]
    scaffold_match = {
        "n_groups": len(groups), "n_groups_A2": a2_inc["n_groups"],
        "empty_group_size": empty_sz, "empty_group_size_A2": a2["scaffold_groups"]["including_empty_scaffold"].get("empty_scaffold_group_size"),
        "max_group": sizes[0], "max_group_A2": a2_inc["max"],
    }
    scaffold_match["identical_to_A2"] = bool(
        scaffold_match["n_groups"] == scaffold_match["n_groups_A2"]
        and scaffold_match["empty_group_size"] == scaffold_match["empty_group_size_A2"]
        and scaffold_match["max_group"] == scaffold_match["max_group_A2"])
    assert scaffold_match["identical_to_A2"], f"scaffold 그룹 구조가 A2 동결 진단과 불일치: {scaffold_match}"
    logln(f"[scaffold] group={len(groups)} (A2 일치=True) · max={sizes[0]} · 빈 scaffold group size={empty_sz}")

    fold_of_group, shuffled_order, counts = assign_folds(groups, N)
    fold_of_row = np.full(N, -1, dtype=int)
    for g, rows in groups.items():
        for i in rows:
            fold_of_row[i] = fold_of_group[g]
    assert (fold_of_row >= 0).all(), "미배정 행 존재"
    logln(f"[split] seed={SPLIT_SEED} · fold 크기 {list(counts)} (목표 ≈{N/N_FOLD:.0f}/fold)")

    diag = split_diagnostics(d, fold_of_row, groups, fold_of_group)
    for f in diag["folds"]:
        logln(f"[fold {f['fold']}] test drugs={f['n_test_drugs']} groups={f['n_test_scaffold_groups']} "
              f"| train PT-positive min={f['train_positive_per_pt']['min']} "
              f"(<1: {f['train_positive_per_pt']['n_pt_lt1']}, <3: {f['train_positive_per_pt']['n_pt_lt3']}) "
              f"| target Jaccard(train,test)={f['target_jaccard_train_test']:.3f} "
              f"| label density test={f['label_density_test']:.5f} train={f['label_density_train']:.5f}")
    logln(f"[게이트A] scaffold 무누수={diag['gate_A']['scaffold_group_disjoint']} "
          f"fold 크기대역={diag['gate_A']['fold_size_band_ok']} "
          f"rare-PT(모든 train fold에 PT별 ≥1 양성)={diag['gate_A']['rare_pt_min1_all_train_folds']} "
          f"B_seq fit행 충분={diag['gate_A']['bseq_fit_rows_ok']} → PASS={diag['gate_A']['gate_A_pass']}")

    # ── 저장: split 파일 + 매니페스트 + 멤버십 CSV ──
    os.makedirs(SPLIT_DIR, exist_ok=True)
    cid_order = d["cid_order"]
    cid2fold = {str(int(c)): int(fold_of_row[i]) for i, c in enumerate(cid_order)}
    dump_json(os.path.join(SPLIT_DIR, "folds.json"), cid2fold)
    scaf_of_row = [None] * N
    for g, rows in groups.items():
        for i in rows:
            scaf_of_row[i] = g
    pd.DataFrame({
        "cid": [int(c) for c in cid_order],
        "fold": fold_of_row,
        "scaffold": scaf_of_row,
        "scaffold_group_size": [len(groups[s]) for s in scaf_of_row],
        "target_mapped": d["mask"].astype(bool),
    }).to_csv(os.path.join(SPLIT_DIR, "fold_membership.csv"), index=False)

    manifest = {
        "step": "docs/30 §13 실행순서 3 — 확증 OOF 반복1(seed 201) split 생성",
        "created_kst": now_kst(),
        "prereg": "docs/30_preregistration_OSF_clean.md §6",
        "repeat": 1, "split_seed": SPLIT_SEED, "n_fold": N_FOLD,
        "seed_scheme_note": (
            "§6은 'split seed = {201…205} × 3 반복'으로 5개 seed 풀을 선언한다. 반복1은 그 순서열의 "
            "첫 원소 = 201로 일의적(docs/36 §1·§3도 '반복1 = seed 201'로 명시). 반복 2·3의 seed 배정은 "
            "본 단계 범위 밖(§13 실행순서 5)이며 여기서 물질화하지 않는다."),
        "scaffold_definition": ("RDKit MurckoScaffold.MurckoScaffoldSmiles(includeChirality=False); "
                                "파싱불가·무고리 → '' 단일 그룹 — pipeline/src/step6_scaffold_split.py 및 "
                                "docs/38 A2와 동일 정의(교차검증 완료)"),
        "scaffold_group_structure_vs_A2": scaffold_match,
        "assignment_algorithm": (
            "사전등록 §6 '스캐폴드 그룹 셔플 후 목표비율 순차배정': 결정적 사전정렬(-size, 첫 cid) → "
            "random.Random(201).shuffle → 누적합이 (i+1)N/5 이하인 첫 fold에 배정(초과 시 마지막 fold). "
            "크기 재정렬 없음."),
        "dev_split_excluded": "seed-42 dev split(scaffold_split.json)은 확증 분석에서 제외(§6) — 미사용",
        "fold_sizes": diag["fold_sizes"],
        "diagnostics": diag,
        "gate0": g0,
        "integrity": {
            "confirmatory_oof_accessed": False,
            "models_trained": 0,
            "network_calls": 0,
            "note": "split·진단만 산출. OOF 예측 미조회(stage=oof에서 최초 조회).",
        },
    }
    dump_json(os.path.join(SPLIT_DIR, "split_manifest.json"), manifest)
    dump_json(os.path.join(RUN_DIR, "split_manifest.json"), manifest)
    pd.DataFrame(diag["folds"]).to_csv(os.path.join(RUN_DIR, "split_diagnostics.csv"), index=False)
    logln(f"[저장] {os.path.relpath(SPLIT_DIR, ROOT)}/(folds.json·fold_membership.csv·split_manifest.json) "
          f"+ {os.path.relpath(RUN_DIR, ROOT)}/(split_manifest.json·split_diagnostics.csv)")

    if not diag["gate_A"]["gate_A_pass"]:
        logln("[게이트A] ❌ FAIL — OOF 미조회 상태로 정지. 사람 보고 후 결정(seed 재추첨 금지 = seed shopping).")
        flush_log()
        sys.exit(2)
    logln("[stage=split] 완료 — 게이트A PASS. OOF 미조회 유지. 다음: --stage oof (되돌릴 수 없는 최초 조회)")
    flush_log()


# ═══════════════════════════════════════════════════════════════════════════
# OOF 실행 (§4) — 여기서부터 확증 OOF **최초 조회**
# ═══════════════════════════════════════════════════════════════════════════
def append_first_look(entry):
    os.makedirs(PROV_DIR, exist_ok=True)
    log = json.load(open(FIRST_LOOK_LOG)) if os.path.exists(FIRST_LOOK_LOG) else []
    if isinstance(log, dict):
        log = [log]
    log.append(entry)
    dump_json(FIRST_LOOK_LOG, log)


def stage_oof(args):
    viewer = args.viewer
    g0 = gate0_verify()

    # ── split 재검증(생성 stage 산출물 재사용 — 재생성 금지) ──
    man_path = os.path.join(SPLIT_DIR, "split_manifest.json")
    assert os.path.exists(man_path), "split 미생성 — 먼저 --stage split 실행"
    split_man = json.load(open(man_path))
    assert split_man["diagnostics"]["gate_A"]["gate_A_pass"], "게이트A 미통과 split — OOF 금지"
    assert split_man["split_seed"] == SPLIT_SEED and split_man["repeat"] == 1

    d = load_frozen()
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]
    cid2fold = json.load(open(os.path.join(SPLIT_DIR, "folds.json")))
    fold_of_row = np.array([cid2fold[str(int(c))] for c in d["cid_order"]], dtype=int)
    assert list(split_man["fold_sizes"]) == [int((fold_of_row == k).sum()) for k in range(N_FOLD)], \
        "split 파일이 매니페스트와 불일치"
    logln(f"[stage=oof] split 재검증 PASS — N={N} PT={K} fold 크기={split_man['fold_sizes']}")

    # ── 게이트 B: OOF를 읽기 **직전** 무결성 로그 기록 (되돌릴 수 없음) ──
    t_first_look = now_kst()
    line = (f"{datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST | 확증 OOF 반복1(seed 201) "
            f"M1b·M2b 최초 조회 | §13 실행순서 3 | 새 split test/OOF 조회 = Y")
    with open(DOCS33, "a") as f:
        f.write("\n---\n\n- **" + line + "**\n")
    # docs/29 §20 미러 — 파일 말미 각주 앞(=§20 마지막 항목 뒤)에 삽입(append-only 의미 보존)
    src29 = open(DOCS29).read()
    marker = "\n\n---\n\n*근거:"
    assert marker in src29, "docs/29 §20 미러 지점(각주 마커) 미발견"
    head, tail = src29.split(marker, 1)
    with open(DOCS29, "w") as f:
        f.write(head + "\n- " + line + marker + tail)
    append_first_look({
        "ts_kst": t_first_look, "viewer": viewer, "step": "§13-3", "repeat": 1, "seed": SPLIT_SEED,
        "status": "first_look_opened", "delta_sign": None, "confirmatory": "Y",
        "note": "게이트B — OOF 예측을 읽기 직전 기록(docs/36 §6). 부호는 완료 후 별도 append.",
    })
    logln(f"[게이트B] 무결성 로그 기록 완료 (docs/33·docs/29 §20 append, first_look_log 'opened') "
          f"| 조회자={viewer} | 시각={t_first_look}")
    logln("[게이트B] ⚠️ 여기서부터 확증 OOF **최초 조회** — 되돌릴 수 없음")

    # ── 블록 인스턴스(B0는 결정적·fit 불필요 → 1회 생성 후 전 fold 재사용) ──
    b_morgan = MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    b_count = CountMaskBlock(d["ntgt"], d["mask"])
    b_seq = SeqBlock(d["emb"], d["mask"], pca_k=PCA_K)
    b_m1b = M1bCovariateBlock(d["cov_by_cid"], d["cid_order"], include_pchembl=False, name="B_m1b")
    blocks = {"B0": b_morgan, "B1": b_count, "B_seq": b_seq, "B_m1b": b_m1b}
    assert b_m1b.dim == 10, f"primary B_m1b dim={b_m1b.dim} != 10"
    assert MODEL_BLOCKS["M1b"] == ["B0", "B1", "B_m1b"]
    assert MODEL_BLOCKS["M2b"] == ["B0", "B1", "B_m1b", "B_seq"]

    oof = {"M1b": np.full((N, K), np.nan, dtype=np.float64),
           "M2b": np.full((N, K), np.nan, dtype=np.float64)}
    fold_records, rf_seeds_used, leak_records = [], [], []

    for kf in range(N_FOLD):
        te = np.where(fold_of_row == kf)[0]
        tr = np.where(fold_of_row != kf)[0]
        # fold train에서만 fit (StandardScaler·PCA) — fold마다 재생성
        b_morgan.fit(tr)          # no-op(결정적)
        b_count.fit(tr)
        b_seq.fit(tr)
        b_m1b.fit(tr)
        leak = {b: blocks[b].leakage_assert(tr) for b in ["B0", "B1", "B_seq", "B_m1b"]}
        # runner assert (ii): B_seq PCA fit 모집단 == outer-fold train ∩ 매핑 약물
        expect = np.zeros(N, dtype=bool)
        expect[tr] = True
        expect &= d["mask"].astype(bool)
        assert np.array_equal(b_seq._fit_rows_mask, expect), \
            f"[fold {kf}] B_seq fit 모집단 != train∩매핑"
        assert all(v["leak_rows"] == 0 for v in leak.values()), f"[fold {kf}] leak_rows != 0"
        leak_records.append({"fold": kf, **{b: leak[b]["leak_rows"] for b in leak}})

        Xtr = {m: np.hstack([blocks[b].transform(tr) for b in MODEL_BLOCKS[m]]).astype(np.float32)
               for m in ("M1b", "M2b")}
        Xte = {m: np.hstack([blocks[b].transform(te) for b in MODEL_BLOCKS[m]]).astype(np.float32)
               for m in ("M1b", "M2b")}
        for m in ("M1b", "M2b"):
            # runner assert (i): 전 fold RF random_state=42 동일(common random numbers)
            rf_seeds_used.append(RF_SEED)
            assert RF_SEED == 42, "RF random_state != 42"
            oof[m][te] = rf_fit_predict(Xtr[m], Y[tr], Xte[m], seed=RF_SEED)
        fold_records.append({
            "fold": kf, "n_train": int(len(tr)), "n_test": int(len(te)),
            "bseq_fit_rows": int(b_seq._fit_rows_mask.sum()), "bseq_pca_evr64": float(b_seq.evr),
            "dim_M1b": int(Xtr["M1b"].shape[1]), "dim_M2b": int(Xtr["M2b"].shape[1]),
            "rf_random_state": RF_SEED,
        })
        logln(f"[fold {kf}] train={len(tr)} test={len(te)} | leak_rows=0(전 블록) | "
              f"B_seq fit행={int(b_seq._fit_rows_mask.sum())} EVR64={b_seq.evr:.4f} | "
              f"dim M1b={Xtr['M1b'].shape[1]} M2b={Xtr['M2b'].shape[1]} | RF random_state={RF_SEED} "
              f"(수치 미기록 — redaction)")

    for m in ("M1b", "M2b"):
        assert not np.isnan(oof[m]).any(), f"{m} OOF 미완성(NaN 존재)"
    assert len(set(rf_seeds_used)) == 1 and rf_seeds_used[0] == 42, "RF seed 불일치"
    logln(f"[OOF] 전체 {N}×{K} OOF 완성 (M1b·M2b) — 반복1 단일이므로 consensus=자기자신(SAP A8)")

    # ── 지표(§7) — 동결 SAP 연산자 사용, 값은 sealed ──
    eligible = np.arange(K)                      # §7: global 양성≥10 = 본 370 PT 전체
    cons = {m: sap_consensus.build_consensus([oof[m]]) for m in ("M1b", "M2b")}
    res = {m: sap_metrics.macro_ap(Y, cons[m], eligible) for m in ("M1b", "M2b")}
    delta = res["M2b"]["macro_ap"] - res["M1b"]["macro_ap"]
    sign = sap_redaction.emit_sign(delta, ZERO_TOL)     # 공개 가능한 유일한 산출

    # per-PT AP·per-fold macro AP (전부 sealed)
    from sklearn.metrics import average_precision_score
    per_pt = {m: [float(average_precision_score(Y[:, j], cons[m][:, j])) for j in range(K)]
              for m in ("M1b", "M2b")}
    per_fold = []
    for kf in range(N_FOLD):
        te = np.where(fold_of_row == kf)[0]
        per_fold.append({
            "fold": kf,
            "M1b": sap_metrics.macro_ap(Y[te], cons["M1b"][te], eligible)["macro_ap"],
            "M2b": sap_metrics.macro_ap(Y[te], cons["M2b"][te], eligible)["macro_ap"],
            "n_eval_M1b": sap_metrics.macro_ap(Y[te], cons["M1b"][te], eligible)["n_eval"],
        })

    # ── 산출물 저장: sealed / public 경로 분리 (runner assert iii) ──
    store = sap_redaction.SealedStore(RUN_DIR)
    os.makedirs(store.sealed_dir, exist_ok=True)
    np.savez_compressed(os.path.join(store.sealed_dir, "oof_M1b.npz"),
                        oof=oof["M1b"], cid=np.array([int(c) for c in d["cid_order"]]),
                        fold=fold_of_row)
    np.savez_compressed(os.path.join(store.sealed_dir, "oof_M2b.npz"),
                        oof=oof["M2b"], cid=np.array([int(c) for c in d["cid_order"]]),
                        fold=fold_of_row)
    store.write_sealed("metrics_full.json", {
        "_warning": "SEALED — 성공판정 단계(3반복+null 완료) 전 열람 금지(docs/36 §4-R).",
        "step": "§13-3 반복1(seed 201)", "ts_kst": t_first_look, "viewer": viewer,
        "estimand": "사전등록 §7 primary — global 양성≥10 PT(370)의 macro AP (consensus OOF, 반복1=자기자신)",
        "macro_ap": {m: res[m] for m in ("M1b", "M2b")},
        "delta_M2b_minus_M1b": float(delta),
        "delta_sign": sign, "zero_tol": ZERO_TOL,
        "per_pt_ap": per_pt, "per_fold_macro_ap": per_fold,
        "pt_columns": d["ycols"],
    })
    public_path = store.write_public("metrics_public.json", delta)

    sealed_sha = {fn: sha256_file(os.path.join(store.sealed_dir, fn))
                  for fn in sorted(os.listdir(store.sealed_dir)) if fn != "access.log"}

    dump_json(os.path.join(RUN_DIR, "config.json"), {
        "step": "docs/30 §13 실행순서 3 — 확증 OOF 반복1(seed 201), Δ 부호만",
        "spec": "docs/36_v3_confirmatory_oof_prompt_for_vscode.md",
        "ts_first_look_kst": t_first_look, "viewer": viewer,
        "models": {"M1b": MODEL_BLOCKS["M1b"], "M2b": MODEL_BLOCKS["M2b"]},
        "primary_B_m1b_dim": int(b_m1b.dim),
        "B_m1b_cont": b_m1b.cont_names, "B_m1b_ind": b_m1b.ind_names,
        "rf": {**RF_KW, "random_state": RF_SEED, "retuned": False,
               "wrapper": "MultiOutputClassifier(one-vs-rest, 370 PT)"},
        "pca": {"k": PCA_K, "svd_solver": "full", "random_state": SEED,
                "fit_population": "outer-fold train ∩ 매핑 약물 행"},
        "split": {"seed": SPLIT_SEED, "n_fold": N_FOLD, "repeat": 1,
                  "dir": os.path.relpath(SPLIT_DIR, ROOT)},
        "metric": {"primary_estimand": sap_metrics.MACRO_AP_DEF,
                   "edge_rules": sap_metrics.MACRO_AP_EDGE_RULES,
                   "eligible_pt": "global 양성≥10 = master_Y 370 PT 전체",
                   "zero_tol": ZERO_TOL},
        "consensus": sap_consensus.CONSENSUS_METHOD,
        "folds": fold_records, "leakage": leak_records,
        "runner_asserts_passed": {"rf_seed42_all_folds": True,
                                  "bseq_pca_fit_outer_train_mapped": True,
                                  "redaction_sign_only": True,
                                  "leak_rows_zero_all_folds": True},
        "gate0": g0,
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__,
                     "scipy": __import__("scipy").__version__, "rdkit": __import__("rdkit").__version__,
                     "platform": platform.platform()},
        "not_performed": ["bootstrap CI", "sign-flip randomization", "p-value", "SESOI/TOST",
                          "성공판정", "재배치 null(§13-4)", "반복2·3(§13-5)",
                          "M0/M1/M2/P-ID/P-FAM/C-CAP OOF", "GIN", "late-fusion", "shift 층화"],
        "integrity": {"network_calls": 0, "raw_data_modified": False,
                      "docs30_modified": False, "frozen_blocks_recomputed": False},
        "sealed_sha256": sealed_sha,
        "public_output": {"path": os.path.relpath(public_path, ROOT), "fields": ["sign"]},
    })

    append_first_look({
        "ts_kst": t_first_look, "ts_completed_kst": now_kst(), "viewer": viewer,
        "step": "§13-3", "repeat": 1, "seed": SPLIT_SEED, "status": "completed",
        "delta_sign": sign,
        "sealed_path": os.path.relpath(store.sealed_dir, ROOT),
        "sealed_sha256": sealed_sha,
        "runner_asserts_passed": {"rf_seed42": True, "pca_foldtrain": True,
                                  "redaction_signonly": True, "leak_rows_zero": True},
        "confirmatory": "Y",
        "note": "원시 macro AP·Δ크기·PT별·fold별은 sealed. 공개=부호 1개(metrics_public.json).",
    })

    logln(f"[지표] macro AP 산출 완료 — 원시값·Δ크기 미출력(sealed, {len(sealed_sha)}개 파일 sha 기록)")
    logln(f"[결과·공개] Δ(M2b−M1b) 부호 = {sign}")
    logln("[무결성] 통계검정(bootstrap/sign-flip/p/SESOI) 미실행 · 반복2·3 미생성 · 타 모델 미조회 · 네트워크 0")
    flush_log()
    print(f"\n=== 공개 산출(부호만) ===\nΔ(M2b − M1b) sign = {sign}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["split", "oof"], required=True)
    ap.add_argument("--viewer", default="vscode-claude(runner)")
    args = ap.parse_args()
    os.makedirs(RUN_DIR, exist_ok=True)
    logln("=" * 78)
    logln(f"[confirm_rep1] stage={args.stage} — docs/36 정본 스펙 실행 (사전등록 §13-3)")
    if args.stage == "split":
        stage_split(args)
    else:
        stage_oof(args)


if __name__ == "__main__":
    main()
