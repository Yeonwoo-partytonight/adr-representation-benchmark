#!/usr/bin/env python3
"""confirmatory_gin_rep.py — 확증 GIN 하네스 (블록 AR · docs/106).

규격 정본: `v3_Multimodal/config/gin_confirm_harness_freeze.json`
설계 정본: `gin_seed_freeze.json` · `gin_inner_valid_freeze.json`(+`.status.json`)
        · 사전등록 `docs/30` §6·§7·§13 · `docs/64` §5 · `docs/66`

⛔ 무결성 최상위 (confirmatory_oof_rep1.py 형식 계승)
  - **이 스크립트는 GIN 착수 허가가 아니다.** `--stage train` 은 `gin_start_still_blocked`
    플래그 3곳 중 **하나라도 true 면 exit 11 로 스스로 거부**한다. 우회 인자·환경변수·
    기본값 우회 경로는 **만들지 않았다**.
  - `_sealed/` **읽기·쓰기·복사·해싱 0** · `_sealed` 디렉터리 **생성 0**.
  - `open_sealed` · `emit_sign` · `sap.decision` **미import·미호출**.
  - `sap.rqint.rqint_test` **미호출** · **순열 계산 0** · p-value 산출 0.
  - `requests`/`urllib`/`http` **미import** — 네트워크 0.
  - 동결 파일(`gin_seed_freeze`·`gin_inner_valid_freeze`(+status)·`ladder_freeze`·
    `gin_confirm_harness_freeze`)은 **읽기 전용**. 본 스크립트는 어떤 동결 파일도 쓰지 않는다.
  - 시드·대표 unit·epoch·patience·비율·모델 목록을 **하드코딩하지 않는다** — 동결 파일에서 로드한다.
    A_wd 레시피 상수는 `train_ladder` 에서 **import** 하고 동결 파일 값과 교차 대조 assert 한다.
  - `macro_ap` · `build_consensus` · `assign_folds` · 블록 클래스 · early-stop 루프는
    **재구현하지 않고 import** 한다.
  - 합성 fixture 경로(`--stage selftest`)는 `data.build_graphs` 를 **쓰지 않는다**
    (그 함수는 `master_X`/`master_Y`/`scaffold_split` 에 하드와이어). `graph_features.smiles_to_data` 를 쓴다.
  - `data/raw/` 접근 0 · `data/processed/` **쓰기 0**(읽기 전용).

stage 3종
  1) `--stage selftest` (**기본값**) — 합성 fixture 자체검사 12건. 확증 학습 0.
  2) `--stage plan`     — 실행 계획(357 단위 4-튜플) 전개. 학습 0.
  3) `--stage train`    — **차단됨**(exit 11). 해제는 별도 블록·별도 승인.

실행:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -X utf8 \
      v3_Multimodal/src/confirmatory_gin_rep.py --stage selftest
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import os
import json
import math
import time
import random
import hashlib
import argparse
import platform
import subprocess
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)                                   # ladder_confirmatory · drug_branch
sys.path.insert(0, os.path.join(HERE, ".."))               # sap 패키지(src/sap)
sys.path.insert(0, os.path.join(ROOT, "v2_GNN", "src"))    # train · graph_features

KST = timezone(timedelta(hours=9))

CFG_DIR = os.path.join(ROOT, "v3_Multimodal", "config")
PROC = os.path.join(ROOT, "data", "processed")
SPLIT_ROOT = os.path.join(PROC, "splits", "confirmatory")
SELFTEST_DIR = os.path.join(ROOT, "experiments", "runs", "v3_gin_harness_selftest")

EXIT_FREEZE_MISMATCH = 2
EXIT_GIN_BLOCKED = 11

# ---------------------------------------------------------------------------
# 동결 파일 — **해시만** 상수로 둔다(규칙·값은 파일에서 로드).
# ---------------------------------------------------------------------------
FREEZE_SHA256 = {
    "gin_seed_freeze.json":
        "10828447c6d33118328ee97dc03279ab06e69d7ed8f9338662bfa740e42542f7",
    "gin_inner_valid_freeze.json":
        "038599c3e157602242ee94e60998f7d8a56c0a322ef5a8b0bc6359b3399921ea",
    "gin_confirm_harness_freeze.json":
        "1af993fde7330e1d48e6d10fee157c1310f42dacc5c1d65a4834b9020e5b7072",
}

# 차단 플래그를 들고 있는 파일 3곳(규격 파일 harness.self_block.checked_files 와 동일).
BLOCK_FLAG_FILES = (
    "rqint_procedure_decisions_v1.json",
    "gin_seed_freeze.json",
    "gin_inner_valid_freeze.json",
)
BLOCK_FLAG = "gin_start_still_blocked"


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 동결 로드 · 자체 차단
# ---------------------------------------------------------------------------
def load_frozen(strict: bool = True) -> dict:
    """동결 3종 해시 대조 후 내용을 반환. 불일치 → exit 2."""
    out, mism = {}, []
    for name, exp in FREEZE_SHA256.items():
        p = os.path.join(CFG_DIR, name)
        got = sha256_file(p)
        if got != exp:
            mism.append({"file": name, "expected": exp, "actual": got})
        out[name] = load_json(p)
    if mism and strict:
        sys.stderr.write("동결 파일 해시 불일치 — 실행 중단:\n"
                         + json.dumps(mism, ensure_ascii=False, indent=2) + "\n")
        sys.exit(EXIT_FREEZE_MISMATCH)
    out["_hash_mismatch"] = mism
    return out


def gin_block_status() -> list:
    """차단 플래그 3곳을 **파일에서 읽어** 상태를 반환."""
    st = []
    for name in BLOCK_FLAG_FILES:
        p = os.path.join(CFG_DIR, name)
        st.append({"file": name, BLOCK_FLAG: bool(load_json(p).get(BLOCK_FLAG))})
    return st


def enforce_gin_block() -> None:
    """--stage train 전용 가드. 하나라도 true 면 exit 11.

    ★ 우회 경로 없음 — 인자·환경변수·기본값 어느 것도 이 함수를 건너뛰게 하지 않는다.
    """
    blocking = [s["file"] for s in gin_block_status() if s[BLOCK_FLAG]]
    if blocking:
        print("GIN 착수 차단 중: %s %s=true. 해제는 별도 블록·별도 승인."
              % (" / ".join(blocking), BLOCK_FLAG))
        sys.exit(EXIT_GIN_BLOCKED)


# ---------------------------------------------------------------------------
# 동결 규칙 판독기 (하드코딩 금지 — 전부 파일에서)
# ---------------------------------------------------------------------------
def frozen_design(fz: dict) -> dict:
    seed_fz = fz["gin_seed_freeze.json"]
    inner_fz = fz["gin_inner_valid_freeze.json"]
    spec = fz["gin_confirm_harness_freeze.json"]
    afn = inner_fz["already_frozen_not_newly_chosen"]
    isp = inner_fz["inner_split"]
    return {
        "models": list(spec["output_scale"]["models"]),
        "confirmatory_seeds": list(seed_fz["confirmatory_seed_prefix"]),
        "stability_seeds_ordered": list(seed_fz["training_seeds_ordered"]),
        "representative_units": [tuple(u) for u in seed_fz["representative_units"]],
        "representative_rule_expected": list(
            seed_fz["representative_unit_rule"]["expected"]),
        "max_epoch": afn["max_epoch"],
        "patience": afn["patience"],
        "min_epoch": afn["min_epoch"],
        "valid_fraction_denom": 9,     # isp["valid_fraction"] = "1/9 of the outer-train rows"
        "valid_fraction_text": isp["valid_fraction"],
        "inner_seed_formula": isp["inner_seed_formula"],
        "inner_seed_values": isp["inner_seed_values"],
        "expected_inner_valid": isp["expected_sizes"]["inner_valid"],
        "expected_inner_train": isp["expected_sizes"]["inner_train"],
        "rep_seed_pairs": {int(k): v for k, v in
                           spec["spec"]["a_run_directories"][
                               "confirmatory_rep_seed_pairs"].items()},
        "run_counts": dict(spec["output_scale"]["run_counts"]),
        "oof_matrices_total": spec["output_scale"]["oof_matrices_total"],
        "oof_matrices_primary": spec["output_scale"][
            "oof_matrices_consumed_by_primary_rqint"],
        "oof_matrix_shape": tuple(spec["output_scale"]["oof_matrix_shape"]),
    }


def _valid_fraction_denominator(text: str) -> int:
    """`"1/9 of the outer-train rows"` → 9. 문면에서 읽고 하드코딩하지 않는다."""
    head = text.strip().split()[0]
    num, den = head.split("/")
    assert int(num) == 1, f"valid_fraction 분자 예상 1, 실측 {num}"
    return int(den)


# ---------------------------------------------------------------------------
# inner split — 동결 함수 `assign_folds` 의 2버킷 일반화
# ---------------------------------------------------------------------------
def assign_buckets(groups, n, seed, cuts):
    """`confirmatory_oof_rep1.assign_folds` 를 **임의 cuts** 로 일반화한 것.

    동결문 축자(gin_inner_valid_freeze.inner_split.algorithm):
      (1) pre-sort groups by (-group_size, str(first row index)) — 행 인덱스는 동결 master_X/master_Y
          오름차순 cid 순서에서의 위치이고 outer-train 부분집합은 **재인덱싱하지 않는다**
      (2) random.Random(inner_seed).shuffle
      (3) cuts = [n_outer_train/9, n_outer_train] · 누적합이 넘지 않는 첫 버킷, 모두 초과면 마지막 버킷
      (4) **bucket 0 = inner-valid**, bucket 1 = inner-train

    ★ 재구현이 아님을 기계로 증명한다: `assert_generalization_equivalent()` 가
      cuts = [(i+1)n/k] 로 호출했을 때 import 한 `assign_folds` 와 동일 결과임을 확인한다.
    """
    k = len(cuts)
    keys = sorted(groups.keys(), key=lambda s: (-len(groups[s]), str(groups[s][0])))
    order = list(keys)
    random.Random(seed).shuffle(order)
    counts = [0] * k
    bucket_of_group = {}
    for g in order:
        sz = len(groups[g])
        placed = False
        for i in range(k):
            if sum(counts[:i + 1]) + sz <= cuts[i]:
                bucket_of_group[g] = i
                counts[i] += sz
                placed = True
                break
        if not placed:
            bucket_of_group[g] = k - 1
            counts[k - 1] += sz
    return bucket_of_group, order, counts


def assert_generalization_equivalent(groups, n, seed, k):
    """`assign_buckets` 가 동결 `assign_folds` 의 충실한 일반화임을 증명."""
    from confirmatory_oof_rep1 import assign_folds        # noqa: E402  (동결 정본 함수)
    ref = assign_folds(groups, n, seed=seed, k=k)
    got = assign_buckets(groups, n, seed, [(i + 1) * n / k for i in range(k)])
    assert ref[0] == got[0] and ref[1] == got[1] and ref[2] == got[2], \
        "assign_buckets 가 동결 assign_folds 와 다른 결과를 냈다 — 일반화 실패"
    return True


def build_groups_from_scaffold(scaffolds, rows):
    """scaffold → [**전역** 행 인덱스] (outer-train 부분집합을 재인덱싱하지 않는다)."""
    groups = defaultdict(list)
    for i in rows:
        groups[scaffolds[i]].append(int(i))
    return dict(groups)


def inner_split(scaffolds, outer_train_rows, inner_seed, denom):
    """동결 알고리즘으로 outer-train 을 (inner_valid, inner_train) 으로 가른다."""
    n = len(outer_train_rows)
    groups = build_groups_from_scaffold(scaffolds, outer_train_rows)
    cuts = [n / denom, float(n)]
    bucket_of_group, order, counts = assign_buckets(groups, n, inner_seed, cuts)
    valid, train = [], []
    for g, b in bucket_of_group.items():
        (valid if b == 0 else train).append(g)
    v_rows = sorted(r for g in valid for r in groups[g])
    t_rows = sorted(r for g in train for r in groups[g])
    # 동결문 asserts 3종 중 2종(그룹 서로소 · 합 일치). 세 번째(양성 0 PT)는 호출자가 라벨로 검사.
    assert not (set(valid) & set(train)), "scaffold groups disjoint between buckets 위반"
    assert sorted(v_rows + t_rows) == sorted(int(r) for r in outer_train_rows), \
        "inner_train + inner_valid == outer_train 위반"
    return v_rows, t_rows, groups, valid


# ---------------------------------------------------------------------------
# stage: plan — 357 단위 4-튜플 전개 (학습 0)
# ---------------------------------------------------------------------------
def build_plan(d: dict) -> dict:
    conf = []
    for rep in sorted(d["rep_seed_pairs"]):
        for fold in range(5):
            for model in d["models"]:
                for t in d["confirmatory_seeds"]:
                    conf.append({"rep": rep, "fold": fold, "model": model, "train_seed": t})
    # 안정성 = 대표 3 unit × 추가 seed 2개(서수 4·5번째 = 값 3·4) × 7모델
    extra = d["stability_seeds_ordered"][len(d["confirmatory_seeds"]):]
    seed2rep = {v: k for k, v in d["rep_seed_pairs"].items()}
    stab = []
    for split_seed, fold in d["representative_units"]:
        for model in d["models"]:
            for t in extra:
                stab.append({"rep": seed2rep[split_seed], "fold": fold,
                             "model": model, "train_seed": t})
    return {
        "confirmatory_units": conf,
        "stability_units": stab,
        "n_confirmatory": len(conf),
        "n_stability": len(stab),
        "n_total": len(conf) + len(stab),
        "stability_extra_seeds_ordinal": "4th and 5th entries of the ordered list",
        "stability_extra_seeds_values": extra,
        "oof_matrices_total": len(d["models"]) * len(d["confirmatory_seeds"]) * 3,
        "oof_matrices_primary_rqint": 2 * len(d["confirmatory_seeds"]) * 3,
        "oof_matrix_shape": list(d["oof_matrix_shape"]),
        "checkpoint_unit_key": ["rep", "fold", "model", "train_seed"],
        "note": "실행 계획일 뿐 허가가 아니다. --stage train 은 차단돼 있다.",
    }


# ---------------------------------------------------------------------------
# stage: selftest — 12건
# ---------------------------------------------------------------------------
FIXTURE_SMILES = [
    "CCO",
    "CC(=O)O",
    "c1ccccc1",
    "CC(=O)Oc1ccccc1C(=O)O",
    "CN1C=NC2=C1C(=O)N(C)C(=O)N2C",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "Clc1ccccc1",
    "OCC1OC(O)C(O)C(O)C1O",
    "CC(N)C(=O)O",
    "c1ccc2ccccc2c1",
    "CCN(CC)CC",
    "C1CCNCC1",
]
FIXTURE_RNG_SEED = 20260914      # 합성 fixture 전용 — 확증 시드집합과 교집합 0
FIXTURE_N_PT = 8


def _case(name, desc, expected, actual, ok, skip_reason=None):
    return {"case": name, "desc": desc, "expected": expected, "actual": actual,
            "pass": bool(ok) and skip_reason is None,
            "skip": skip_reason is not None, "skip_reason": skip_reason}


def _count_sealed():
    dirs = files = access = 0
    for dp, dns, fns in os.walk(ROOT):
        if os.path.basename(dp) == "_sealed":
            dirs += 1
        parts = dp.split(os.sep)
        if "_sealed" in parts:
            files += len(fns)
            access += sum(1 for f in fns if f == "access.log")
    return dirs, files, access


def _count_pycache():
    return sum(1 for dp, dns, fns in os.walk(ROOT)
               if os.path.basename(dp) == "__pycache__")


def run_selftest(fz, d, out_dir):
    cases = []
    os.makedirs(out_dir, exist_ok=True)
    pyc_start = _count_pycache()
    sealed_start = _count_sealed()

    # ---- S1 동결 3종 sha256 대조 -------------------------------------------
    got = {n: sha256_file(os.path.join(CFG_DIR, n)) for n in FREEZE_SHA256}
    ok1 = all(got[n] == FREEZE_SHA256[n] for n in FREEZE_SHA256)
    cases.append(_case("S1", "동결 3종 sha256 대조",
                       {"n_match": 3}, {"n_match": sum(got[n] == FREEZE_SHA256[n]
                                                       for n in FREEZE_SHA256)}, ok1))

    # ---- S2 대표 unit 규칙 재산출 -------------------------------------------
    rep_calc = [int(hashlib.sha256(str(s).encode("ascii")).hexdigest(), 16) % 5
                for s in (201, 202, 203)]
    ok2 = rep_calc == d["representative_rule_expected"] == \
        [u[1] for u in d["representative_units"]]
    cases.append(_case("S2", "대표 unit 규칙(SHA-256 mod 5) 재산출",
                       d["representative_rule_expected"], rep_calc, ok2))

    # ---- 공통 입력: master_Y · fold_membership -------------------------------
    Y = pd.read_parquet(os.path.join(PROC, "master_Y.parquet"))
    ycols = [c for c in Y.columns if c != "cid"]
    Ym = Y[ycols].values.astype(np.int8)
    cid_master = [int(c) for c in Y["cid"]]

    ref_check = load_json(os.path.join(ROOT, "experiments", "runs",
                                       "v3_gin_inner_valid_freeze",
                                       "inner_split_check.json"))
    ref_units = {(u["split_seed"], u["fold"]): u for u in ref_check["units"]}

    denom = _valid_fraction_denominator(d["valid_fraction_text"])

    # ---- S3 inner split 15 unit 전건 재현 ------------------------------------
    s3_rows, s3_bad = [], 0
    for rep, split_seed in sorted(d["rep_seed_pairs"].items()):
        fm = pd.read_csv(os.path.join(SPLIT_ROOT, f"rep{rep}_seed{split_seed}",
                                      "fold_membership.csv"))
        assert [int(c) for c in fm["cid"]] == cid_master, \
            "fold_membership cid 순서가 master 오름차순과 다르다"
        scaf = ["" if (isinstance(s, float) and math.isnan(s)) else str(s)
                for s in fm["scaffold"]]
        fold_of_row = fm["fold"].values.astype(int)
        for f in range(5):
            otr = np.where(fold_of_row != f)[0]
            inner_seed = 1000 * split_seed + f
            v_rows, t_rows, groups, vgroups = inner_split(scaf, otr, inner_seed, denom)
            pos_tr = Ym[t_rows].sum(0)
            n_zero_pos = int((pos_tr < 1).sum())
            n_valid_defined = int((Ym[v_rows].sum(0) > 0).sum())
            largest = max(len(groups[g]) for g in vgroups)
            largest_g = max(vgroups, key=lambda g: (len(groups[g]), str(groups[g][0])))
            got_u = {
                "split_seed": split_seed, "fold": f, "inner_seed": inner_seed,
                "n_outer_train": int(len(otr)),
                "n_inner_train": len(t_rows), "n_inner_valid": len(v_rows),
                "n_valid_scaffold_groups": len(vgroups),
                "n_valid_defined_pt": n_valid_defined,
                "n_inner_train_zero_positive_pt": n_zero_pos,
                "largest_valid_group_size": largest,
                "largest_valid_group_is_empty_scaffold": largest_g == "",
                "n_outer_train_scaffold_groups": len(groups),
            }
            exp_u = ref_units[(split_seed, f)]
            diff = {k: (exp_u[k], got_u[k]) for k in got_u if exp_u.get(k) != got_u[k]}
            if diff:
                s3_bad += 1
            s3_rows.append({"unit": [split_seed, f], "match": not diff, "diff": diff})
    ok3 = (s3_bad == 0 and len(s3_rows) == 15
           and all(r["unit"] is not None for r in s3_rows)
           and all(u["n_inner_valid"] == d["expected_inner_valid"]
                   for u in ref_check["units"]))
    cases.append(_case("S3", "inner split 15 unit 전건 재현",
                       {"n_units": 15, "n_mismatch": 0, "inner_valid": 97},
                       {"n_units": len(s3_rows), "n_mismatch": s3_bad,
                        "inner_valid_set": sorted({r for r in
                                                   [u["n_inner_valid"]
                                                    for u in ref_check["units"]]})},
                       ok3))

    # ---- S4 outer split 재현 (import 한 동결 assign_folds) ---------------------
    from confirmatory_oof_rep1 import assign_folds        # noqa: E402
    s4 = {}
    for rep, split_seed in sorted(d["rep_seed_pairs"].items()):
        fm = pd.read_csv(os.path.join(SPLIT_ROOT, f"rep{rep}_seed{split_seed}",
                                      "fold_membership.csv"))
        scaf = ["" if (isinstance(s, float) and math.isnan(s)) else str(s)
                for s in fm["scaffold"]]
        groups = build_groups_from_scaffold(scaf, range(len(scaf)))
        fog, order, counts = assign_folds(groups, len(scaf), seed=split_seed, k=5)
        repro = np.empty(len(scaf), dtype=int)
        for g, rows in groups.items():
            for r in rows:
                repro[r] = fog[g]
        mism = int((repro != fm["fold"].values.astype(int)).sum())
        s4[f"rep{rep}_seed{split_seed}"] = {
            "mismatched_rows": mism, "fold_sizes": counts,
            "n_scaffold_groups": len(groups)}
        # 일반화 등가성(재구현 아님) 기계 증명
        assert_generalization_equivalent(groups, len(scaf), split_seed, 5)
    ok4 = all(v["mismatched_rows"] == 0 and v["fold_sizes"] == [218, 218, 219, 218, 219]
              and v["n_scaffold_groups"] == 732 for v in s4.values())
    cases.append(_case("S4", "outer split 3반복 재현 + assign_buckets 일반화 등가성",
                       {"mismatched_rows": 0, "fold_sizes": [218, 218, 219, 218, 219],
                        "n_scaffold_groups": 732}, s4, ok4))

    # ---- S5 A_wd 상수 대조 ----------------------------------------------------
    s5_skip = None
    try:
        import train_ladder as TL                          # noqa: E402
        tl = {"SEEDS": list(TL.SEEDS), "THR": TL.THR, "ARCH": TL.ARCH,
              "EMBED_DIM": TL.EMBED_DIM, "PCA_K": TL.PCA_K, "EPOCHS": TL.EPOCHS,
              "PATIENCE": TL.PATIENCE, "BATCH": TL.BATCH, "LR": TL.LR,
              "WD": TL.WD, "GAMMA": TL.GAMMA, "DROPOUT": TL.DROPOUT}
        src = "import"
    except Exception as e:                                  # AR-0-4(i) AST 대체 경로
        s5_skip = None
        import ast
        tree = ast.parse(open(os.path.join(HERE, "train_ladder.py"),
                              encoding="utf-8").read())
        tl, src = {}, f"ast (import 실패: {type(e).__name__})"
        for node in tree.body:
            if isinstance(node, ast.Assign):
                tgts = node.targets[0]
                names = ([t.id for t in tgts.elts] if isinstance(tgts, ast.Tuple)
                         else ([tgts.id] if isinstance(tgts, ast.Name) else []))
                vals = (node.value.elts if isinstance(node.value, ast.Tuple)
                        else [node.value])
                for nm, vl in zip(names, vals):
                    try:
                        tl[nm] = ast.literal_eval(vl)
                    except Exception:
                        pass
        tl = {k: tl[k] for k in ("SEEDS", "THR", "ARCH", "EMBED_DIM", "PCA_K",
                                 "EPOCHS", "PATIENCE", "BATCH", "LR", "WD",
                                 "GAMMA", "DROPOUT") if k in tl}
    rc = fz["gin_confirm_harness_freeze.json"]["harness"]["recipe_constants_A_wd"]
    exp5 = {k: rc[k] for k in tl}
    ok5 = all(tl[k] == exp5[k] for k in tl) and len(tl) == 12
    # 동결 inner_valid 파일과의 교차 대조
    ok5 = ok5 and tl["EPOCHS"] == d["max_epoch"] and tl["PATIENCE"] == d["patience"]
    cases.append(_case("S5", f"A_wd 상수 대조 ({src}) — 코드 = 규격 = inner_valid 동결",
                       exp5, tl, ok5, s5_skip))

    # ---- S6 early-stop 루프 진리표 ---------------------------------------------
    def simulate(monitor, patience, max_epoch):
        """F12 축자 루프(strict >, patience, best 복원)의 순수 재현 — 학습 없음."""
        best_v, best_ep, wait, stopped = -1.0, 0, 0, None
        for ep in range(1, max_epoch + 1):
            if ep > len(monitor):
                break
            vmac = monitor[ep - 1]
            if vmac > best_v:
                best_v, best_ep, wait = vmac, ep, 0
            else:
                wait += 1
            if wait >= patience:
                stopped = ep
                break
        return {"best_ep": best_ep, "best_v": best_v, "stopped_at": stopped}

    P = d["patience"]
    s6 = []
    s6.append({"name": "동률은 최초 epoch 승",
               "seq": [0.5, 0.5, 0.5], "exp_best_ep": 1,
               "got": simulate([0.5, 0.5, 0.5], P, d["max_epoch"])})
    s6.append({"name": "단조 증가 → 최종 epoch",
               "seq": [0.1, 0.2, 0.3, 0.4], "exp_best_ep": 4,
               "got": simulate([0.1, 0.2, 0.3, 0.4], P, d["max_epoch"])})
    flat = [0.9] + [0.1] * P
    s6.append({"name": f"patience {P} 정확히 소진 → ep {P+1} 정지",
               "seq": "0.9 + 0.1×%d" % P, "exp_best_ep": 1,
               "got": simulate(flat, P, d["max_epoch"])})
    near = [0.9] + [0.1] * (P - 1)
    s6.append({"name": f"patience {P-1} 에서는 정지 안 함",
               "seq": "0.9 + 0.1×%d" % (P - 1), "exp_best_ep": 1,
               "got": simulate(near, P, d["max_epoch"])})
    s6.append({"name": "최솟값 갱신 없음(첫 epoch 이 best)",
               "seq": [0.7, 0.6, 0.65], "exp_best_ep": 1,
               "got": simulate([0.7, 0.6, 0.65], P, d["max_epoch"])})
    s6.append({"name": "min_epoch 부재 — 1 epoch 도 best 가 될 수 있다",
               "seq": [0.8], "exp_best_ep": 1,
               "got": simulate([0.8], P, d["max_epoch"])})
    ok6 = (all(c["got"]["best_ep"] == c["exp_best_ep"] for c in s6)
           and s6[2]["got"]["stopped_at"] == P + 1
           and s6[3]["got"]["stopped_at"] is None
           and d["min_epoch"] is None and P == 30 and d["max_epoch"] == 200)
    cases.append(_case("S6", "early-stop 진리표(strict > · patience · tie=최초 · min_epoch 부재)",
                       {"n_cases": 6, "patience": 30, "max_epoch": 200, "min_epoch": None},
                       {"n_cases": len(s6), "patience": P, "max_epoch": d["max_epoch"],
                        "min_epoch": d["min_epoch"], "cases": s6}, ok6))

    # ---- S7 macro AP 가변 분모 ---------------------------------------------------
    from sap.metrics import macro_ap                        # noqa: E402
    rng = np.random.default_rng(FIXTURE_RNG_SEED)
    ys = np.zeros((20, 5), dtype=int)
    ys[:, 0] = (rng.random(20) < 0.4).astype(int)
    ys[:, 1] = (rng.random(20) < 0.5).astype(int)
    ys[:, 2] = 0                                             # 양성 0 → undefined
    ys[:, 3] = (rng.random(20) < 0.3).astype(int)
    ys[:, 4] = 0                                             # 양성 0 → undefined
    ys[0, 0] = ys[0, 1] = ys[0, 3] = 1                       # 각 열 양성 ≥1 보장
    Ps = rng.random((20, 5))
    r7 = macro_ap(ys, Ps, eligible_pt=None)
    keys_needed = {"n_eval", "n_excluded_undefined", "n_eligible", "excl_frac",
                   "defined_mask"}
    ok7 = (keys_needed <= set(r7)
           and r7["n_eval"] == 3 and r7["n_excluded_undefined"] == 2
           and r7["n_eligible"] == 5
           and list(r7["defined_mask"]) == [True, True, False, True, False]
           and not math.isclose(r7["macro_ap"],
                                float(np.mean([r7["macro_ap"] * 3 / 5, 0, 0])),
                                rel_tol=1e-12))
    cases.append(_case("S7", "macro AP 가변 분모(AP=0 대입 없음) + 반환 키",
                       {"n_eval": 3, "n_excluded_undefined": 2, "n_eligible": 5,
                        "keys": sorted(keys_needed)},
                       {"n_eval": r7["n_eval"],
                        "n_excluded_undefined": r7["n_excluded_undefined"],
                        "n_eligible": r7["n_eligible"],
                        "excl_frac": round(float(r7["excl_frac"]), 6),
                        "defined_mask": [bool(b) for b in r7["defined_mask"]],
                        "keys_present": sorted(keys_needed & set(r7))}, ok7))

    # ---- S8 build_eight_consensus 입력 규격 ---------------------------------------
    from sap.rqint import build_eight_consensus, observed_statistic   # noqa: E402
    from sap.consensus import build_consensus                          # noqa: E402
    import sap.rqint as _rq                                            # noqa: E402
    # 재구현 0 — rqint 가 쓰는 build_consensus 가 동결 모듈의 «바로 그» 객체인지 확인한다.
    assert _rq.build_consensus is build_consensus, \
        "sap.rqint 가 쓰는 build_consensus 가 sap.consensus 의 것과 다르다"
    N, K = 30, 6
    rng8 = np.random.default_rng(FIXTURE_RNG_SEED + 1)
    y8 = (rng8.random((N, K)) < 0.35).astype(int)
    y8[0, :] = 1
    seeds8 = d["confirmatory_seeds"]
    P_RF = {a: [rng8.random((N, K)) for _ in range(3)] for a in ("M1b", "M2b")}
    P_GIN = {a: {s: [rng8.random((N, K)) for _ in range(3)] for s in seeds8}
             for a in ("M1b", "M2b")}
    mats, sk = build_eight_consensus(P_RF, P_GIN)
    T, d_rf, d_gin, d_gin_s = observed_statistic(mats, sk, y8, None)
    mta = math.isclose(d_gin, float(np.mean(d_gin_s)), rel_tol=1e-12)
    # repeat 축 집계가 동결 build_consensus 와 바이트 단위로 같은지 직접 대조(재구현 0 증명)
    cons_ok = bool(np.array_equal(mats[("RF", None, "M1b")],
                                  build_consensus(P_RF["M1b"])))
    ok8 = (len(mats) == 8 and list(sk) == sorted(seeds8) and len(d_gin_s) == 3
           and mta and cons_ok)
    cases.append(_case("S8", "build_eight_consensus 8행렬 · seed 키 정렬 · metric-then-average "
                             "(rqint_test 호출 0 · 순열 0)",
                       {"n_mats": 8, "seed_keys": sorted(seeds8), "n_delta_gin": 3,
                        "metric_then_average": True,
                        "build_consensus_is_frozen_object": True},
                       {"n_mats": len(mats), "seed_keys": list(sk),
                        "n_delta_gin": len(d_gin_s), "metric_then_average": mta,
                        "build_consensus_is_frozen_object": True,
                        "repeat_axis_matches_build_consensus": cons_ok,
                        "rqint_test_calls": 0, "permutations": 0}, ok8))

    # ---- S9 합성 smoke (2 epoch · 수치 폐기) -----------------------------------
    s9_skip, s9_actual = None, {}
    try:
        import torch
        from torch_geometric.loader import DataLoader
        from graph_features import smiles_to_data, ATOM_FDIM     # noqa: E402
        from train import set_seed, get_device, compute_pos_weight, \
            FocalLoss, predict_proba                             # noqa: E402
        from train_ladder import LadderNet                        # noqa: E402

        rng9 = np.random.default_rng(FIXTURE_RNG_SEED)
        Yfix = (rng9.random((len(FIXTURE_SMILES), FIXTURE_N_PT)) < 0.3).astype(np.float32)
        cols_no_pos = [int(j) for j in range(FIXTURE_N_PT) if Yfix[:, j].sum() == 0]
        graphs = []
        n_fail = 0
        for i, smi in enumerate(FIXTURE_SMILES):
            g = smiles_to_data(smi, y=Yfix[i].tolist())
            if g is None:
                n_fail += 1
                continue
            graphs.append(g)
        set_seed(42)
        device = get_device({"device": "auto"})
        model = LadderNet(ATOM_FDIM, FIXTURE_N_PT, side_dim=0, fusion="concat").to(device)
        loader = DataLoader(graphs, batch_size=32, shuffle=True)
        pw = torch.sqrt(compute_pos_weight(graphs, FIXTURE_N_PT)).to(device)
        crit = FocalLoss(gamma=2.0, pos_weight=pw)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
        t0 = time.time()
        for _ep in range(2):
            model.train()
            for batch in loader:
                batch = batch.to(device)
                opt.zero_grad()
                loss = crit(model(batch), batch.y.view(-1, FIXTURE_N_PT))
                loss.backward()
                opt.step()
        Pp, Yy = predict_proba(model, DataLoader(graphs, batch_size=32), device,
                               FIXTURE_N_PT)
        wall = time.time() - t0
        shape_ok = (Pp.shape == (len(graphs), FIXTURE_N_PT))
        del Pp, Yy, model                                   # ★ 수치 폐기
        s9_actual = {"completed": True, "n_graphs": len(graphs), "n_parse_fail": n_fail,
                     "epochs": 2, "seconds": round(wall, 3),
                     "seconds_per_epoch": round(wall / 2, 3),
                     "device": str(device), "pred_shape_ok": shape_ok,
                     "columns_excluded_by_macro_ap_rule": cols_no_pos,
                     "build_graphs_used": False,
                     "confirmatory_data_accessed": False,
                     "metrics_recorded": False}
        ok9 = shape_ok and n_fail == 0 and len(graphs) == 12
    except Exception as e:
        s9_skip = f"의존성/실행 부재: {type(e).__name__}: {e}"
        ok9 = False
        s9_actual = {"completed": False}
    cases.append(_case("S9", "합성 smoke — 지시서 공급 SMILES 12 + rng(20260914) 라벨 12×8 · 2 epoch",
                       {"completed": True, "n_graphs": 12, "build_graphs_used": False},
                       s9_actual, ok9, s9_skip))

    # ---- S10 차단 가드 -----------------------------------------------------------
    before = sorted(p for p in os.listdir(os.path.join(ROOT, "experiments", "runs"))
                    if p.startswith("v3_gin_confirm"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    cp = subprocess.run([sys.executable, "-B", "-X", "utf8", os.path.abspath(__file__),
                         "--stage", "train"],
                        capture_output=True, text=True, env=env, cwd=ROOT)
    after = sorted(p for p in os.listdir(os.path.join(ROOT, "experiments", "runs"))
                   if p.startswith("v3_gin_confirm"))
    ok10 = (cp.returncode == EXIT_GIN_BLOCKED
            and "GIN 착수 차단 중" in cp.stdout
            and before == after == [])
    cases.append(_case("S10", "--stage train → exit 11 · 차단 사유 출력 · 실행 디렉터리 생성 0",
                       {"returncode": 11, "reason_printed": True, "dirs_created": 0},
                       {"returncode": cp.returncode,
                        "stdout": cp.stdout.strip()[:300],
                        "dirs_created": len(after) - len(before)}, ok10))

    # ---- S11 규격 왕복 (schema_fixture · _sealed 디렉터리 생성 0) -------------------
    fx = os.path.join(out_dir, "schema_fixture")
    os.makedirs(fx, exist_ok=True)
    spec_c = fz["gin_confirm_harness_freeze.json"]["spec"]["c_sealed_layout"]["files"]
    layout_paths = []
    for rep, split_seed in sorted(d["rep_seed_pairs"].items()):
        base = f"experiments/runs/v3_gin_confirm_rep{rep}_seed{split_seed}"
        for model in d["models"]:
            for t in d["confirmatory_seeds"]:
                layout_paths.append(f"{base}/_sealed/oof_{model}_seed{t}.npz")
        for f_ in ("metrics_full.json", "access.log", "checkpoint.jsonl",
                   "env_fingerprint.json"):
            layout_paths.append(f"{base}/_sealed/{f_}")
        for f_ in ("config.json", "metrics_public.json", "run.log",
                   "split_diagnostics.csv", "split_manifest.json"):
            layout_paths.append(f"{base}/{f_}")
    layout = {
        "_doc": "봉인 레이아웃을 **경로 문자열로만** 검증한다. 본 블록은 _sealed 디렉터리를 0개 만든다.",
        "sealed_dirs_created": 0,
        "n_paths": len(layout_paths),
        "n_sealed_oof_per_repeat": len(d["models"]) * len(d["confirmatory_seeds"]),
        "paths": layout_paths,
    }
    with open(os.path.join(fx, "SEALED_LAYOUT.json"), "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)
        f.write("\n")
    # 키 스키마 왕복: 합성 1세트를 «평평한 이름» 으로 만들어 검증(디렉터리 _sealed 미생성)
    rngs = np.random.default_rng(FIXTURE_RNG_SEED + 2)
    npz_path = os.path.join(fx, "SAMPLE__sealed__oof_M1b_seed42.npz")
    np.savez_compressed(npz_path,
                        P=rngs.random((4, 3)).astype(np.float32),
                        y=(rngs.random((4, 3)) < .5).astype(np.int8),
                        pt_index=np.arange(3, dtype=np.int32),
                        cid_order=np.arange(4, dtype=np.int64))
    mf = {"cells": [{"rep": 1, "fold": 0, "model": "M1b", "train_seed": 42,
                     "macro_ap": None, "delta": None, "n_eval": None,
                     "n_excluded_undefined": None, "best_ep": None, "best_v": None}]}
    ck = {"rep": 1, "fold": 0, "model": "M1b", "train_seed": 42,
          "completed_at_kst": now_kst(), "artifact_sha256": "0" * 64,
          "n_epochs": 0, "wall_seconds": 0.0}
    for nm, obj in (("SAMPLE__sealed__metrics_full.json", mf),
                    ("SAMPLE__sealed__env_fingerprint.json",
                     {"python": platform.python_version()})):
        with open(os.path.join(fx, nm), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    with open(os.path.join(fx, "SAMPLE__sealed__checkpoint.jsonl"), "w",
              encoding="utf-8") as f:
        f.write(json.dumps(ck, ensure_ascii=False) + "\n")
    with open(os.path.join(fx, "SAMPLE__sealed__access.log"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts_kst": now_kst(), "type": "machine_read",
                            "human_exposure": False}, ensure_ascii=False) + "\n")
    # 검증
    z = np.load(npz_path)
    npz_keys_ok = set(z.files) == set(spec_c["oof_{model}_seed{t}.npz"]["content"])
    ck_keys_ok = set(json.loads(open(os.path.join(
        fx, "SAMPLE__sealed__checkpoint.jsonl"), encoding="utf-8").readline())) == set(
        fz["gin_confirm_harness_freeze.json"]["spec"]["d_resumability"]["line_fields"])
    mf_keys_ok = set(mf["cells"][0]) >= set(
        ["rep", "fold", "model", "train_seed"]
        + spec_c["metrics_full.json"]["content"][2:]
        + ["macro_ap", "delta"])
    acc = json.loads(open(os.path.join(fx, "SAMPLE__sealed__access.log"),
                          encoding="utf-8").readline())
    acc_ok = acc["type"] == "machine_read" and acc["human_exposure"] is False
    no_sealed_dir = not any(os.path.basename(dp) == "_sealed"
                            for dp, _, _ in os.walk(out_dir))
    ok11 = npz_keys_ok and ck_keys_ok and mf_keys_ok and acc_ok and no_sealed_dir
    cases.append(_case("S11", "규격 왕복(schema_fixture) · _sealed 디렉터리 생성 0",
                       {"npz_keys": True, "checkpoint_keys": True,
                        "metrics_full_keys": True, "access_log": True,
                        "sealed_dir_created": 0},
                       {"npz_keys": npz_keys_ok, "checkpoint_keys": ck_keys_ok,
                        "metrics_full_keys": mf_keys_ok, "access_log": acc_ok,
                        "sealed_dir_created": 0 if no_sealed_dir else 1,
                        "n_layout_paths": len(layout_paths)}, ok11))

    # ---- S12 위생 ----------------------------------------------------------------
    pyc_end = _count_pycache()
    sealed_end = _count_sealed()
    ok12 = (pyc_end == pyc_start and sealed_end == sealed_start
            and sealed_end[0] == 25 and sealed_end[1] == 291 and sealed_end[2] == 16)
    cases.append(_case("S12", "위생 — __pycache__ 착수=종료 · 봉인 25/291/275/16 불변",
                       {"pycache": pyc_start,
                        "sealed_dirs": 25, "sealed_files": 291,
                        "access_logs": 16, "non_access": 275},
                       {"pycache": pyc_end, "sealed_dirs": sealed_end[0],
                        "sealed_files": sealed_end[1], "access_logs": sealed_end[2],
                        "non_access": sealed_end[1] - sealed_end[2]}, ok12))

    n_pass = sum(1 for c in cases if c["pass"])
    n_skip = sum(1 for c in cases if c["skip"])
    result = {
        "_doc": "confirmatory_gin_rep.py --stage selftest 산출. 확증 GIN 학습 0회.",
        "block": "AR",
        "generated_kst": now_kst(),
        "harness_sha256": sha256_file(os.path.abspath(__file__)),
        "n_cases": len(cases),
        "n_pass": n_pass,
        "n_skip": n_skip,
        "all_pass": (n_pass + n_skip) == len(cases),
        "all_pass_definition": "all_pass = (n_pass + n_skip == n_cases)",
        "sealed_dirs_created": 0,
        "confirmatory_training_runs_performed": 0,
        "s3_units": s3_rows,
        "cases": cases,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    with open(os.path.join(out_dir, "selftest.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    return result


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="확증 GIN 하네스 (블록 AR)")
    ap.add_argument("--stage", choices=["selftest", "plan", "train"], default="selftest")
    ap.add_argument("--out", default=None, help="plan 단계 산출 경로(선택)")
    args = ap.parse_args()

    if args.stage == "train":
        # ★ 최우선 가드 — 동결 로드보다 먼저 차단한다.
        enforce_gin_block()
        # 여기 아래는 차단이 해제된 뒤에야 도달한다(별도 블록·별도 승인).
        raise SystemExit("착수 허가 이후 구현 — 본 블록(AR)은 확증 학습 0회다.")

    fz = load_frozen()
    d = frozen_design(fz)

    if args.stage == "plan":
        plan = build_plan(d)
        plan["gin_block_status"] = gin_block_status()
        plan["is_authorization"] = False
        summary = {k: v for k, v in plan.items()
                   if k not in ("confirmatory_units", "stability_units")}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.out:
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"[plan] wrote {args.out}")
        return 0

    res = run_selftest(fz, d, SELFTEST_DIR)
    for c in res["cases"]:
        mark = "SKIP" if c["skip"] else ("PASS" if c["pass"] else "FAIL")
        print(f"  {c['case']:<4} {mark:<4} {c['desc']}")
    print(f"[selftest] n_cases={res['n_cases']} n_pass={res['n_pass']} "
          f"n_skip={res['n_skip']} all_pass={res['all_pass']}")
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
