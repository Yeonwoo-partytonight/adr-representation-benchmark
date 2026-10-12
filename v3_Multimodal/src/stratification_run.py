#!/usr/bin/env python3
"""stratification_run.py — 블록 H: §13-6 연속 유사도 층화.

성격
----
확증 OOF(consensus)를 **기계 판독**해 층별 추정을 만든다. 산출은 **전량 `_sealed/`**.
공개는 설계 자산(identity 산출물·층 배정표)·표본수·라벨·시간·해시·게이트 PASS/FAIL 뿐이다.
**성공판정(decision.py) 호출 없음 · 개봉(open_sealed) 없음 · 다중성 보정 없음.**

스테이지
  bounds    구조축(H-0-5) max Tanimoto 분위 경계 산출 — 구조 전용(sealed 미접근)
  identity  mmseqs2 easy-search all-vs-all → 양방향 best identity (H-2)
  strata    fold-local 층 배정 → strata_assignment.csv (H-3)
  verify    정합 하드 assert (H-4)
  pilot     B=100 계측 → 전 층 × B=10000 총 wall 추정 (H-5-0)
  estimate  본계산 → _sealed/stratification_result.json (H-5-1)

실행: .venv/bin/python3 v3_Multimodal/src/stratification_run.py --stage <stage>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

for _k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_k, "1")

import numpy as np                                                      # noqa: E402
import pandas as pd                                                     # noqa: E402
from rdkit import Chem, RDLogger                                        # noqa: E402
from rdkit.Chem import rdFingerprintGenerator                           # noqa: E402
from rdkit import DataStructs                                           # noqa: E402

from compute_lock import ComputeLock, gate_a_load, gate_b_exclusive     # noqa: E402
from confirmatory_oof_rep1 import gate0_verify                          # noqa: E402
from sap import bootstrap as sap_bootstrap                              # noqa: E402
from sap import metrics as sap_metrics                                  # noqa: E402
from sap import redaction as sap_redaction                              # noqa: E402
from sap import signflip as sap_signflip                                # noqa: E402
from sap import unseen_target as sap_unseen                             # noqa: E402

RDLogger.DisableLog("rdApp.*")
KST = timezone(timedelta(hours=9))

# ═══════════════════════════════════════════════════════════════════════════
# 동결 상수 (H-0 판독확정 · 결과 무참조 · 실행 전 고정)
# ═══════════════════════════════════════════════════════════════════════════
MORGAN_RADIUS = 2                 # ladder_freeze.json morgan.radius
MORGAN_BITS = 2048                # ladder_freeze.json morgan.n_bits
STRUCT_QUANTILES = [25, 50, 75]   # H-0-5 분위 경계(반복1 기준 산출 → 3반복 공통)
STRUCT_BINS = ["struct_q1", "struct_q2", "struct_q3", "struct_q4"]

SEED_BOOTSTRAP = 6001             # H-0-4
SEED_SIGNFLIP = 6002              # H-0-4
B_MAIN = 10000                    # SAP 동결 기본값
B_PILOT = 100                     # H-5-0 계측 전용(산출 폐기)
BOOT_UNIT = "scaffold_cluster"    # SAP primary
ELIGIBLE_PT = None                # H-0-3 — 370 PT 전열, 층 내부 재선정 금지

EXPECT_N_DRUGS = 1092
EXPECT_N_NO_TARGET = 245          # docs/54 K-2 — INFERENCE_MODE 상 excluded
EXPECT_DENOM = 847                # docs/54 K-2 — 1,092 − 245 = 층화 추정 모수
EXPECT_N_PT = 370
EXPECT_N_SCAFFOLD_GROUPS = 732
EXPECT_N_FASTA = 1191
EXPECT_LADDER_FREEZE_SHA16 = "b885585aefbabb32"
EXPECT_SAP_MANIFEST_SHA16 = "756d485feb4715e9"
EXPECT_GUARD_N_FILES = 12
WALL_ABORT_DAYS = 7.0             # H-5-0 중단 임계

# seed 격리(H-0-4) — 예약·확증·프로브·null 본런 seed 전량
RESERVED_SEEDS = set(range(201, 206)) | {42}
PROBE1_SEEDS = {9000001, 9000002}
PROBE2_SEEDS = set(range(9000101, 9000119))
NULL_MAIN_SEEDS = set(range(1000, 2000)) | set(range(11000, 12000))
SAP_DRYRUN_SEEDS = {1, 2, 7, 11, 5, 13, 14}

MMSEQS = "/opt/homebrew/bin/mmseqs"
MMSEQS_ARGS = ["-s", "7.5", "--max-seqs", "2000", "-e", "10000", "--threads", "8"]
MMSEQS_FORMAT = "query,target,fident,alnlen,evalue,bits"

# ═══════════════════════════════════════════════════════════════════════════
# 경로
# ═══════════════════════════════════════════════════════════════════════════
PROC = os.path.join(ROOT, "data", "processed")
TM = os.path.join(PROC, "target_mapping")
MMDIR = os.path.join(TM, "_mmseqs")
FASTA = os.path.join(MMDIR, "targets_human.fasta")
IDENT_TSV = os.path.join(MMDIR, "identity_pairs.tsv")
IDENT_SHA = IDENT_TSV + ".sha256"
IDENT_MANIFEST = os.path.join(MMDIR, "identity_manifest.json")
IDENT_RAW = os.path.join(MMDIR, "_easy_search_raw.tsv")

F_MASTER_X = os.path.join(PROC, "master_X.parquet")
F_MASTER_Y = os.path.join(PROC, "master_Y.parquet")
F_TARGETS = os.path.join(TM, "06_targets_human.csv")
F_FAMBIO = os.path.join(TM, "10_target_family_biological.csv")
SPLITS = {1: os.path.join(PROC, "splits", "confirmatory", "rep1_seed201"),
          2: os.path.join(PROC, "splits", "confirmatory", "rep2_seed202"),
          3: os.path.join(PROC, "splits", "confirmatory", "rep3_seed203")}

CONS_DIR = os.path.join(ROOT, "experiments", "runs", "v3_consensus_rep123")
CONS_SEALED = os.path.join(CONS_DIR, "_sealed")
CONS_ACCESS = os.path.join(CONS_SEALED, "access.log")

RUN_DIR = os.path.join(ROOT, "experiments", "runs", "v3_stratification")
SEALED_DIR = os.path.join(RUN_DIR, "_sealed")
RUN_LOG = os.path.join(RUN_DIR, "run.log")
F_BOUNDS = os.path.join(RUN_DIR, "struct_bounds.json")
F_STRATA = os.path.join(RUN_DIR, "strata_assignment.csv")
F_STRATA_SUM = os.path.join(RUN_DIR, "strata_summary.json")
F_GATES = os.path.join(RUN_DIR, "gates_public.json")
F_PILOT = os.path.join(RUN_DIR, "pilot_timing.json")
F_PUBLIC = os.path.join(RUN_DIR, "stratification_public.json")

SEALED_GUARD_DIRS = [
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep1_seed201", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep2_seed202", "_sealed"),
    os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep3_seed203", "_sealed"),
    CONS_SEALED,
]


# ═══════════════════════════════════════════════════════════════════════════
# 유틸 — 공개 로그에 AP·Δ·CI·p 를 절대 쓰지 않는다
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


def native(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=native)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def guard_snapshot():
    """블록 C sealed 산출물 파일별 sha256 — 값은 열지 않고 지문만."""
    snap = {}
    for d in SEALED_GUARD_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if os.path.isfile(p) and fn != "access.log":
                snap[os.path.relpath(p, ROOT)] = sha256_file(p)
    return snap


def log_machine_read(path_rel, purpose):
    """sealed 파일 **기계 판독**(사람 노출 0) — `open_sealed`(사람 열람)와 구분."""
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": "§13-6 연속 유사도 층화(블록 H)",
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    for p in (CONS_ACCESS, os.path.join(SEALED_DIR, "access.log")):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ═══════════════════════════════════════════════════════════════════════════
# 게이트 (H-1)
# ═══════════════════════════════════════════════════════════════════════════
def seed_isolation():
    used = {SEED_BOOTSTRAP, SEED_SIGNFLIP}
    forbidden = RESERVED_SEEDS | PROBE1_SEEDS | PROBE2_SEEDS | NULL_MAIN_SEEDS | SAP_DRYRUN_SEEDS
    inter = sorted(used & forbidden)
    assert not inter, f"[seed 격리 FAIL] 층화 seed 가 예약/확증/null/프로브 seed 와 충돌: {inter}"
    return {"stratification_seeds": sorted(used), "n_forbidden_checked": len(forbidden),
            "intersection": inter, "intersection_size": 0, "pass": True}


def gate_h1():
    """H-1 착수 전 확인 — G0 · sealed 12종 · 입력 존재 (판독 전용, 값 미열람)."""
    g0 = gate0_verify()
    assert g0["ladder_freeze_sha16"] == EXPECT_LADDER_FREEZE_SHA16
    assert g0["sap_manifest_sha16"] == EXPECT_SAP_MANIFEST_SHA16

    guard = guard_snapshot()
    assert len(guard) == EXPECT_GUARD_N_FILES, f"sealed guard {len(guard)}종 != {EXPECT_GUARD_N_FILES}"

    cons_sha = {fn: sha256_file(os.path.join(CONS_SEALED, fn))
                for fn in ("consensus_M1b.npz", "consensus_M2b.npz", "metrics_full.json")}

    inputs = {}
    for r, d in SPLITS.items():
        p = os.path.join(d, "fold_membership.csv")
        assert os.path.exists(p), f"입력 부재: {p}"
        n = sum(1 for _ in open(p, encoding="utf-8")) - 1
        assert n == EXPECT_N_DRUGS, f"rep{r} fold_membership 행 {n} != {EXPECT_N_DRUGS}"
        inputs[f"rep{r}_fold_membership_rows"] = n
    for p in (F_TARGETS, F_FAMBIO, F_MASTER_X, F_MASTER_Y, FASTA):
        assert os.path.exists(p), f"입력 부재: {p}"
    n_fasta = sum(1 for ln in open(FASTA, encoding="utf-8") if ln.startswith(">"))
    assert n_fasta == EXPECT_N_FASTA, f"FASTA 서열 {n_fasta} != {EXPECT_N_FASTA}"
    inputs["targets_human_fasta_sequences"] = n_fasta

    # open_sealed(사람 열람) 이력 0건
    n_open = 0
    for d in SEALED_GUARD_DIRS + [SEALED_DIR]:
        p = os.path.join(d, "access.log")
        if os.path.exists(p):
            n_open += sum(1 for ln in open(p, encoding="utf-8") if "OPEN sealed" in ln)
    assert n_open == 0, f"open_sealed 이력 {n_open}건 — 개봉 금지 위반"

    iso = seed_isolation()
    out = {"ts_kst": now_kst(), "G0": g0, "sealed_guard_n_files": len(guard),
           "sealed_guard": guard, "consensus_sha256": cons_sha, "inputs": inputs,
           "open_sealed_events": n_open, "seed_isolation": iso, "pass": True}
    logln(f"[H-1] PASS — ladder_freeze {g0['ladder_freeze_sha16']} · SAP manifest "
          f"{g0['sap_manifest_sha16']} · 11모듈 일치 · sealed guard {len(guard)}종 · "
          f"입력 전건 존재(FASTA {n_fasta}) · open_sealed {n_open}건 · seed 교집합 0")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 공통 로더
# ═══════════════════════════════════════════════════════════════════════════
def load_common():
    X = pd.read_parquet(F_MASTER_X)
    Y = pd.read_parquet(F_MASTER_Y)
    assert list(X["cid"]) == list(Y["cid"]), "master_X/Y cid 정렬 불일치"
    cid_order = X["cid"].astype(int).tolist()
    assert len(cid_order) == EXPECT_N_DRUGS
    ycols = [c for c in Y.columns if c != "cid"]
    assert len(ycols) == EXPECT_N_PT
    Ym = Y[ycols].values.astype(int)

    tdf = pd.read_csv(F_TARGETS)
    cid2targets_raw = tdf.groupby("cid")["uniprot"].apply(
        lambda s: set(str(u) for u in s.dropna())).to_dict()
    # H-0-2: canonicalize(secondary_to_primary=None, seq_representative=None) — isoform 절단만
    cid2targets = {int(c): sap_unseen.canonicalize_set(t, None, None)
                   for c, t in cid2targets_raw.items()}

    folds, scaffolds = {}, None
    for r, d in SPLITS.items():
        fm = pd.read_csv(os.path.join(d, "fold_membership.csv"))
        fm["scaffold"] = fm["scaffold"].fillna("")
        fm = fm.set_index("cid").reindex(cid_order)
        assert not fm["fold"].isna().any(), f"rep{r} fold_membership 이 cid_order 를 덮지 못함"
        folds[r] = fm["fold"].astype(int).values
        sc = fm["scaffold"].astype(str).values
        if scaffolds is None:
            scaffolds = sc
        else:
            assert (scaffolds == sc).all(), "반복 간 scaffold 라벨 불일치"
    assert len(set(scaffolds)) == EXPECT_N_SCAFFOLD_GROUPS
    return {"cid_order": cid_order, "cid_pos": {int(c): i for i, c in enumerate(cid_order)},
            "ycols": ycols, "Ym": Ym,
            "cid2targets": cid2targets, "folds": folds, "scaffold": scaffolds,
            "smiles": X["smiles_canonical"].astype(str).tolist()}


def train_targets_by_fold(cid_order, cid2targets, fold_arr):
    """fold f 의 T_train_f = train(=fold != f) 약물들의 표적 합집합."""
    out = {}
    for f in sorted(set(fold_arr.tolist())):
        acc = set()
        for i, c in enumerate(cid_order):
            if fold_arr[i] != f:
                acc |= cid2targets.get(int(c), set())
        out[int(f)] = acc
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: bounds — 구조축 분위 경계 (H-0-5) · 구조 전용, sealed 미접근
# ═══════════════════════════════════════════════════════════════════════════
def morgan_matrix(smiles):
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)
    fps, n_fail = [], 0
    for smi in smiles:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            fps.append(None)
            n_fail += 1
        else:
            fps.append(gen.GetFingerprint(mol))
    return fps, n_fail


def max_tanimoto_to_train(fps, fold_arr):
    """약물 d 의 fold-train 약물집합에 대한 max Morgan Tanimoto (H-0-5)."""
    N = len(fps)
    out = np.full(N, np.nan, dtype=float)
    by_fold = defaultdict(list)
    for i, f in enumerate(fold_arr):
        by_fold[int(f)].append(i)
    for f, test_idx in by_fold.items():
        train_idx = [i for i in range(N) if int(fold_arr[i]) != f and fps[i] is not None]
        train_fps = [fps[i] for i in train_idx]
        for i in test_idx:
            if fps[i] is None:
                continue
            sims = DataStructs.BulkTanimotoSimilarity(fps[i], train_fps)
            out[i] = float(max(sims)) if sims else float("nan")
    return out


def stage_bounds():
    logln("[bounds] 구조축(H-0-5) max Morgan Tanimoto 분위 경계 — 구조 전용(sealed 미접근)")
    d = load_common()
    fps, n_fail = morgan_matrix(d["smiles"])
    logln(f"[bounds] Morgan r={MORGAN_RADIUS} bits={MORGAN_BITS} 생성 — 파싱실패 {n_fail}")
    maxtan = {r: max_tanimoto_to_train(fps, d["folds"][r]) for r in (1, 2, 3)}
    ref = maxtan[1]
    assert not np.isnan(ref).any(), "반복1 max Tanimoto 에 NaN 존재"
    qs = [float(np.percentile(ref, q)) for q in STRUCT_QUANTILES]
    out = {
        "_scope": "공개 — 설계 자산(구조축 경계). 결과(AP·Δ·CI·p) 아님.",
        "ts_kst": now_kst(),
        "rule": ("H-0-5 사전확정 — 약물 d 의 구조 유사도 = fold-train 약물집합에 대한 max Morgan "
                 "Tanimoto(동결 fingerprint: ladder_freeze.json morgan r=2, 2048bit; 재계산·파라미터 "
                 "변경 없음). 층 경계 = 반복1 기준 25/50/75 분위 → 3반복 공통 적용. 결과를 본 뒤 조정 금지."),
        "fingerprint": {"radius": MORGAN_RADIUS, "n_bits": MORGAN_BITS,
                        "source": "ladder_freeze.json morgan (v1_RF pilot 정의)",
                        "generator": "rdFingerprintGenerator.GetMorganGenerator",
                        "n_parse_fail": int(n_fail)},
        "reference_repeat": 1,
        "quantiles": STRUCT_QUANTILES,
        "boundaries": {"q25": qs[0], "q50": qs[1], "q75": qs[2]},
        "bins": STRUCT_BINS,
        "bin_rule": "q1: x<q25 · q2: q25<=x<q50 · q3: q50<=x<q75 · q4: x>=q75",
        "max_tanimoto_summary_by_repeat": {
            str(r): {"n": int(len(maxtan[r])), "min": float(np.nanmin(maxtan[r])),
                     "median": float(np.nanmedian(maxtan[r])), "max": float(np.nanmax(maxtan[r]))}
            for r in (1, 2, 3)},
    }
    dump_json(F_BOUNDS, out)
    np.save(os.path.join(RUN_DIR, "_max_tanimoto.npy"),
            np.stack([maxtan[1], maxtan[2], maxtan[3]], axis=1))
    logln(f"[bounds] 경계 q25={qs[0]:.4f} q50={qs[1]:.4f} q75={qs[2]:.4f} → {F_BOUNDS}")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: identity — mmseqs2 easy-search all-vs-all (H-2)
# ═══════════════════════════════════════════════════════════════════════════
def stage_identity():
    logln("[identity] mmseqs2 easy-search all-vs-all (IDENTITY_METHOD 동결 문면 그대로)")
    assert os.path.exists(MMSEQS), f"mmseqs2 미설치: {MMSEQS}"
    ver = subprocess.run([MMSEQS, "version"], capture_output=True, text=True,
                         timeout=60).stdout.strip()
    binpath = os.path.realpath(MMSEQS)
    bin_sha = sha256_file(binpath)
    logln(f"[identity] mmseqs {ver} · {binpath} · sha256 {bin_sha[:16]}")

    tmpdir = os.path.join(MMDIR, "tmp_search")
    t0 = time.perf_counter()
    cmd = [MMSEQS, "easy-search", FASTA, FASTA, IDENT_RAW, tmpdir,
           "--format-output", MMSEQS_FORMAT] + MMSEQS_ARGS
    logln("[identity] " + " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"mmseqs easy-search 실패(rc={res.returncode}):\n{res.stderr[-2000:]}"
    wall = time.perf_counter() - t0

    accs = [ln[1:].strip().split()[0] for ln in open(FASTA, encoding="utf-8") if ln.startswith(">")]
    assert len(accs) == EXPECT_N_FASTA
    assert len(set(accs)) == EXPECT_N_FASTA, "FASTA accession 중복"

    # 양방향 best identity 로 대칭화 (A→B, B→A 중 큰 값). 자기 자신 제외.
    best = {}
    n_rows, n_self = 0, 0
    with open(IDENT_RAW, encoding="utf-8") as f:
        for ln in f:
            p = ln.rstrip("\n").split("\t")
            if len(p) < 3:
                continue
            q, t, fident = p[0], p[1], float(p[2])
            n_rows += 1
            if q == t:
                n_self += 1
                continue
            key = (q, t) if q < t else (t, q)
            pct = fident * 100.0
            if pct > best.get(key, -1.0):
                best[key] = pct

    total_pairs = EXPECT_N_FASTA * (EXPECT_N_FASTA - 1) // 2
    with open(IDENT_TSV, "w", encoding="utf-8") as f:
        f.write("acc1\tacc2\tidentity_pct\n")
        for (a, b) in sorted(best):
            f.write(f"{a}\t{b}\t{best[(a, b)]:.4f}\n")
    tsv_sha = sha256_file(IDENT_TSV)
    with open(IDENT_SHA, "w", encoding="utf-8") as f:
        f.write(f"{tsv_sha}  {os.path.basename(IDENT_TSV)}\n")

    man = {
        "_scope": ("공개 — **설계 자산**(층 정의의 전제)이며 결과가 아니다. AP·Δ·CI·p 없음."),
        "ts_kst": now_kst(),
        "identity_method_frozen": sap_unseen.IDENTITY_METHOD,
        "tool": {"name": "mmseqs2", "version": ver, "path": binpath, "binary_sha256": bin_sha,
                 "install": "brew (사전 설치 상태 — 본 블록에서 네트워크 사용 0)"},
        "command": cmd,
        "input_fasta": {"path": os.path.relpath(FASTA, ROOT), "n_sequences": len(accs),
                        "sha256": sha256_file(FASTA)},
        "symmetrization": "양방향 best identity — max(identity(A→B), identity(B→A)); 자기 자신 제외",
        "identity_definition": "alignment percent identity = mmseqs fident × 100",
        "coverage": {"n_aligned_pairs": len(best), "n_total_pairs": total_pairs,
                     "aligned_fraction": len(best) / total_pairs,
                     "n_raw_rows": n_rows, "n_self_hits_dropped": n_self,
                     "missing_rule": ("미정렬 쌍은 identity 0 으로 대체하지 않고 `missing` 으로 유지 — "
                                      "seqid_max 는 관측된 값만으로 max 를 취한다(H-2-4).")},
        "wall_s": wall,
        "outputs": {"identity_pairs.tsv": {"path": os.path.relpath(IDENT_TSV, ROOT),
                                           "sha256": tsv_sha, "rows": len(best)}},
    }
    dump_json(IDENT_MANIFEST, man)
    logln(f"[identity] 정렬쌍 {len(best):,}/{total_pairs:,} "
          f"({len(best) / total_pairs * 100:.2f}%) · self {n_self} · wall {wall:.1f}s · "
          f"tsv sha16 {tsv_sha[:16]}")
    return man


def load_identity():
    """identity_pairs.tsv → {acc: {acc2: pct}} (관측된 쌍만)."""
    idmap = defaultdict(dict)
    with open(IDENT_TSV, encoding="utf-8") as f:
        next(f)
        for ln in f:
            a, b, v = ln.rstrip("\n").split("\t")
            v = float(v)
            idmap[a][b] = v
            idmap[b][a] = v
    return idmap


# ═══════════════════════════════════════════════════════════════════════════
# stage: strata — fold-local 층 배정 (H-3)
# ═══════════════════════════════════════════════════════════════════════════
def struct_bin_of(x, bnd):
    if x < bnd["q25"]:
        return STRUCT_BINS[0]
    if x < bnd["q50"]:
        return STRUCT_BINS[1]
    if x < bnd["q75"]:
        return STRUCT_BINS[2]
    return STRUCT_BINS[3]


def stage_strata():
    logln("[strata] fold-local 층 배정 (sap/unseen_target.py 호출만)")
    d = load_common()
    bnd = json.load(open(F_BOUNDS, encoding="utf-8"))["boundaries"]
    idmap = load_identity()
    maxtan = np.load(os.path.join(RUN_DIR, "_max_tanimoto.npy"))
    cid_order = d["cid_order"]

    rows = []
    for r in (1, 2, 3):
        fold_arr = d["folds"][r]
        T_train = train_targets_by_fold(cid_order, d["cid2targets"], fold_arr)
        for i, c in enumerate(cid_order):
            f = int(fold_arr[i])
            T_d = d["cid2targets"].get(int(c), set())
            Ttr = T_train[f]
            drug_class = sap_unseen.classify_drug(T_d, Ttr)
            # seqid_max — **관측된 값만**으로 target 별 max(0 채움 금지)
            seqid_max, n_obs = {}, 0
            for t in T_d:
                if t in Ttr:
                    continue                       # exact-seen → identity 축 무관
                cand = [idmap[t][u] for u in Ttr if t in idmap and u in idmap[t]]
                if cand:
                    seqid_max[t] = max(cand)
                    n_obs += 1
            seq_stratum = sap_unseen.drug_sequence_stratum(T_d, Ttr, seqid_max)
            rows.append({"cid": int(c), "rep": r, "fold": f,
                         "drug_class": drug_class, "seq_stratum": seq_stratum,
                         "n_targets": len(T_d), "n_unseen_targets": len(T_d - Ttr),
                         "n_seqid_observed": n_obs,
                         "struct_bin": struct_bin_of(float(maxtan[i, r - 1]), bnd),
                         "max_tanimoto": float(maxtan[i, r - 1])})
    df = pd.DataFrame(rows)

    # H-0-1: 3반복 층 일치 여부 → stable / unstable_stratum (축별)
    stab = {}
    for axis in ("drug_class", "seq_stratum", "struct_bin"):
        piv = df.pivot(index="cid", columns="rep", values=axis)
        stab[axis] = (piv.nunique(axis=1) == 1)
        df[f"stable_{axis}"] = df["cid"].map(stab[axis])
    df.to_csv(F_STRATA, index=False)
    logln(f"[strata] {F_STRATA} — {len(df)}행 (1,092 × 3반복)")

    acct = assert_strata_accounting(df)
    logln(f"[strata] 회계 assert PASS — 축별 Σ stable + unstable = "
          f"{acct['denominator_estimated']} · + no-target {acct['n_excluded_no_target']} = "
          f"{acct['n_total_drugs']}")

    summary = build_strata_summary(df, d)
    dump_json(F_STRATA_SUM, summary)
    for axis, items in summary["axes"].items():
        logln(f"[strata] {axis}: " + " · ".join(
            f"{k} n={v['n_drugs']}({v['inference_mode']})" for k, v in items.items()))
    logln(f"[strata] unstable — " + " · ".join(
        f"{a}: {summary['unstable'][a]['n_drugs']}" for a in summary["unstable"]))
    logln(f"[strata] seqid 관측 0건 약물(반복별) = {summary['seqid_zero_observation_drugs']}")
    return summary


AXES = {
    "drug_class": ["all-seen", "all-unseen", "mixed"],          # no-target 은 excluded
    "seq_stratum": ["seen", "unseen_ge90", "unseen_70_90", "unseen_40_70", "unseen_lt40"],
    "struct_bin": list(STRUCT_BINS),
}


def stratum_members(df, axis, value):
    """3반복 전부 동일 층인 약물(cid 리스트) — H-0-1 primary."""
    piv = df.pivot(index="cid", columns="rep", values=axis)
    same = piv.nunique(axis=1) == 1
    sel = same & (piv[1] == value)
    return sorted(piv.index[sel].tolist())


def unstable_members(df, axis):
    piv = df.pivot(index="cid", columns="rep", values=axis)
    return sorted(piv.index[piv.nunique(axis=1) > 1].tolist())


def excluded_no_target(df):
    """no-target 약물(어느 반복에서든) — INFERENCE_MODE 상 excluded (H-4-3)."""
    return sorted(df.loc[df["drug_class"] == "no-target", "cid"].unique().tolist())


def assert_strata_accounting(df):
    """층 회계 하드 assert (docs/54 K-2 — 향후 재실행 시 자동 강제).

    축마다 `Σ stable(no-target 제외) + unstable == 847` **AND**
    `847 + no-target 245 == 1,092`, 그리고 세 축의 추정 모수·대상 약물 집합이 서로 같아야 한다.
    (`docs/51` 메일에서 `unstable_stratum` 을 적지 않아 합이 837 로 보인 **보고 누락**을 코드로 차단.)"""
    assert len(df) == EXPECT_N_DRUGS * 3, f"행수 {len(df)} != {EXPECT_N_DRUGS * 3}"
    excl = set(excluded_no_target(df))
    assert len(excl) == EXPECT_N_NO_TARGET, f"no-target {len(excl)} != {EXPECT_N_NO_TARGET}"
    denoms, sets = {}, {}
    for axis, values in AXES.items():
        stable = [c for v in values for c in stratum_members(df, axis, v) if c not in excl]
        unstable = [c for c in unstable_members(df, axis) if c not in excl]
        denoms[axis] = len(stable) + len(unstable)
        sets[axis] = set(stable) | set(unstable)
        assert denoms[axis] == EXPECT_DENOM, (
            f"[회계 FAIL] {axis}: stable {len(stable)} + unstable {len(unstable)} "
            f"= {denoms[axis]} != {EXPECT_DENOM}")
        assert denoms[axis] + len(excl) == EXPECT_N_DRUGS, (
            f"[회계 FAIL] {axis}: {denoms[axis]} + no-target {len(excl)} != {EXPECT_N_DRUGS}")
    assert len(set(denoms.values())) == 1, f"[회계 FAIL] 축별 모수 불일치: {denoms}"
    base = sets[next(iter(AXES))]
    assert all(sets[a] == base for a in AXES), "[회계 FAIL] 축별 추정 대상 약물 집합 불일치"
    return {"n_total_drugs": EXPECT_N_DRUGS, "n_excluded_no_target": len(excl),
            "denominator_estimated": EXPECT_DENOM, "per_axis": denoms, "pass": True}


def support_stats(cids, d):
    idx = row_index(d, cids)
    y = d["Ym"][idx]
    sc = d["scaffold"][idx]
    pos = y.sum(axis=0)
    n_pt_ok = int((pos >= sap_unseen.MIN_SUPPORT["min_positive_pt_support"]).sum())
    sizes = np.array([int((sc == g).sum()) for g in np.unique(sc)], dtype=float)
    return {"n_drugs": len(cids), "n_scaffold_clusters": int(len(np.unique(sc))),
            "n_eff_clusters": sap_bootstrap.n_eff_clusters(sizes),
            "n_pt_meeting_positive_support": n_pt_ok,
            "row_index": idx}


def infer_mode(stats, axis, value):
    """MIN_SUPPORT 대조 → formal / descriptive 라벨링만(해석하지 않는다)."""
    ok = (stats["n_drugs"] >= sap_unseen.MIN_SUPPORT["min_drugs"]
          and stats["n_pt_meeting_positive_support"]
          >= sap_unseen.MIN_SUPPORT["min_positive_pt_support"])
    frozen = sap_unseen.INFERENCE_MODE.get(value)
    return {"meets_min_support": bool(ok),
            "label": "formal" if ok else "descriptive",
            "frozen_inference_mode": frozen,
            "rule": sap_unseen.INFERENCE_MODE["rule"]}


def build_strata_summary(df, d):
    excl = set(excluded_no_target(df))
    axes_out = {}
    for axis, values in AXES.items():
        items = {}
        for v in values:
            cids = [c for c in stratum_members(df, axis, v) if c not in excl]
            if not cids:
                items[v] = {"n_drugs": 0, "n_scaffold_clusters": 0, "n_eff_clusters": 0.0,
                            "n_pt_meeting_positive_support": 0, "inference_mode": "empty",
                            "estimable": False}
                continue
            st = support_stats(cids, d)
            im = infer_mode(st, axis, v)
            items[v] = {"n_drugs": st["n_drugs"], "n_scaffold_clusters": st["n_scaffold_clusters"],
                        "n_eff_clusters": st["n_eff_clusters"],
                        "n_pt_meeting_positive_support": st["n_pt_meeting_positive_support"],
                        "inference_mode": im["label"], "meets_min_support": im["meets_min_support"],
                        "frozen_inference_mode": im["frozen_inference_mode"], "estimable": True}
        axes_out[axis] = items
    unstable = {}
    for axis in AXES:
        cids = [c for c in unstable_members(df, axis) if c not in excl]
        if cids:
            st = support_stats(cids, d)
            unstable[axis] = {"n_drugs": st["n_drugs"],
                              "n_scaffold_clusters": st["n_scaffold_clusters"],
                              "n_eff_clusters": st["n_eff_clusters"],
                              "n_pt_meeting_positive_support": st["n_pt_meeting_positive_support"],
                              "inference_mode": infer_mode(st, axis, None)["label"]}
        else:
            unstable[axis] = {"n_drugs": 0, "n_scaffold_clusters": 0, "n_eff_clusters": 0.0,
                              "n_pt_meeting_positive_support": 0, "inference_mode": "empty"}
    zero_obs = {}
    for r in (1, 2, 3):
        sub = df[df["rep"] == r]
        zero_obs[str(r)] = int(((sub["drug_class"] == "all-unseen")
                                & (sub["n_seqid_observed"] == 0)).sum())
    return {
        "_scope": ("공개 — 층 배정·표본수·클러스터수·formal/descriptive 라벨 뿐. "
                   "층별 macro AP·Δ·CI·p 는 `_sealed/` (본 파일에 없음)."),
        "ts_kst": now_kst(),
        "min_support": sap_unseen.MIN_SUPPORT,
        "seqid_boundaries": sap_unseen.SEQID_BOUNDARIES,
        "seqid_strata": sap_unseen.SEQID_STRATA,
        "struct_bins": STRUCT_BINS,
        "eligible_pt": "None (370 PT 전열 · 층 내부 재선정 금지 — H-0-3)",
        "excluded_no_target_drugs": len(excl),
        "axes": axes_out,
        "unstable": unstable,
        "unstable_note": ("H-0-1 — 3반복에서 층이 일치하는 약물만 primary 층화 대상. 불일치 약물은 "
                          "제외가 아니라 `unstable_stratum` 으로 분리 집계·별도 보고."),
        "seqid_zero_observation_drugs": zero_obs,
        "seqid_zero_observation_note": (
            "all-unseen 약물 중 train 표적과의 identity 가 한 건도 관측되지 않은 약물 수(반복별). "
            "미정렬 쌍은 0 으로 채우지 않았으며(H-2-4), 이 약물들은 동결 연산자 "
            "`drug_sequence_stratum` 의 내부 규칙에 따라 배정된다(연산자 수정 없음). 한계로 명시한다."),
    }


# ═══════════════════════════════════════════════════════════════════════════
# stage: verify — 정합 하드 assert (H-4)
# ═══════════════════════════════════════════════════════════════════════════
def load_consensus():
    log_machine_read(os.path.relpath(os.path.join(CONS_SEALED, "consensus_M1b.npz"), ROOT),
                     "§13-6 층화 추정 입력(consensus M1b) — 기계 판독")
    log_machine_read(os.path.relpath(os.path.join(CONS_SEALED, "consensus_M2b.npz"), ROOT),
                     "§13-6 층화 추정 입력(consensus M2b) — 기계 판독")
    out = {}
    for m in ("M1b", "M2b"):
        with np.load(os.path.join(CONS_SEALED, f"consensus_{m}.npz")) as z:
            out[m] = z["consensus"].astype(np.float64)
            out[m + "_cid"] = z["cid"].astype(int)
    return out


def stage_verify():
    logln("[verify] H-4 정합 하드 assert")
    d = load_common()
    df = pd.read_csv(F_STRATA)
    checks = {}

    # 1. 약물 1,092 전수 · scaffold group 732 전수 · fold 교차 0
    checks["n_drugs"] = int(df["cid"].nunique())
    checks["n_scaffold_groups"] = int(len(set(d["scaffold"])))
    cross = 0
    for r in (1, 2, 3):
        m = pd.DataFrame({"scaffold": d["scaffold"], "fold": d["folds"][r]})
        cross += int((m.groupby("scaffold")["fold"].nunique() > 1).sum())
    checks["scaffold_fold_cross"] = cross
    assert checks["n_drugs"] == EXPECT_N_DRUGS, checks
    assert checks["n_scaffold_groups"] == EXPECT_N_SCAFFOLD_GROUPS, checks
    assert cross == 0, checks

    # 2. 층 배정 합계 = 각 반복·fold 에서 1,092
    per_rep = df.groupby("rep").size().to_dict()
    assert all(v == EXPECT_N_DRUGS for v in per_rep.values()), per_rep
    for axis in AXES:
        assert not df[axis].isna().any(), f"{axis} 결측"
        tot = df.groupby("rep")[axis].count().to_dict()
        assert all(v == EXPECT_N_DRUGS for v in tot.values()), (axis, tot)
    checks["assign_total_per_repeat"] = {str(k): int(v) for k, v in per_rep.items()}

    # 3. no-target 약물이 층화 추정에서 제외되었는지
    excl = set(excluded_no_target(df))
    checks["n_excluded_no_target"] = len(excl)
    est_targets = set()
    for u in estimation_units(df, d):
        est_targets |= set(u["cids"])
    checks["n_estimation_target_drugs"] = len(est_targets)
    checks["no_target_in_estimation_set"] = len(est_targets & excl)
    assert checks["no_target_in_estimation_set"] == 0, "no-target 약물이 층화 추정에 포함됨"

    # 4. consensus 배열 shape · NaN 0건
    cons = load_consensus()
    for m in ("M1b", "M2b"):
        assert cons[m].shape == (EXPECT_N_DRUGS, EXPECT_N_PT), f"{m} shape {cons[m].shape}"
        assert not np.isnan(cons[m]).any(), f"{m} NaN 존재"
        assert list(cons[m + "_cid"]) == d["cid_order"], f"{m} cid 정렬 불일치"
    assert d["Ym"].shape == (EXPECT_N_DRUGS, EXPECT_N_PT)
    checks["consensus_shape"] = list(cons["M1b"].shape)
    checks["consensus_nan"] = 0
    checks["y_shape"] = list(d["Ym"].shape)

    # 5. seed 교집합 0
    checks["seed_isolation"] = seed_isolation()

    # 6. 층 회계 정합 (docs/54 K-2) — 축별 847 · 847 + 245 = 1,092
    checks["accounting"] = assert_strata_accounting(df)

    out = {"_scope": "공개 — 게이트 PASS/FAIL·개수·해시 뿐.", "ts_kst": now_kst(),
           "H4_checks": checks, "sealed_guard_start": guard_snapshot(), "all_pass": True}
    dump_json(F_GATES, out)
    logln(f"[verify] PASS — 약물 {checks['n_drugs']} · scaffold {checks['n_scaffold_groups']} · "
          f"fold 교차 {cross} · no-target 제외 {len(excl)} · consensus shape "
          f"{checks['consensus_shape']} NaN 0 · seed 교집합 0")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# stage: pilot / estimate (H-5)
# ═══════════════════════════════════════════════════════════════════════════
def estimation_units(df, d):
    """추정 대상 층 목록 — (axis, value, cids). no-target 제외(H-4-3)."""
    excl = set(excluded_no_target(df))
    units = []
    for axis, values in AXES.items():
        for v in values:
            cids = [c for c in stratum_members(df, axis, v) if c not in excl]
            if cids:
                units.append({"axis": axis, "stratum": v, "kind": "stable", "cids": cids})
        cids = [c for c in unstable_members(df, axis) if c not in excl]
        if cids:
            units.append({"axis": axis, "stratum": "unstable_stratum", "kind": "unstable",
                          "cids": cids})
    return units


def row_index(d, cids):
    pos = d["cid_pos"]
    return np.array([pos[int(c)] for c in cids], dtype=int)


def run_unit(unit, d, cons, B, seed_boot, seed_flip):
    idx = row_index(d, unit["cids"])
    y_s = d["Ym"][idx]
    m1_s = cons["M1b"][idx]
    m2_s = cons["M2b"][idx]
    sg_s = d["scaffold"][idx]

    t0 = time.perf_counter()
    ap1 = sap_metrics.macro_ap(y_s, m1_s, ELIGIBLE_PT)
    ap2 = sap_metrics.macro_ap(y_s, m2_s, ELIGIBLE_PT)
    t_ap = time.perf_counter() - t0

    t0 = time.perf_counter()
    boot = sap_bootstrap.paired_scaffold_bootstrap(
        m1_s, m2_s, y_s, sg_s, eligible_pt=ELIGIBLE_PT, B=B, seed=seed_boot, unit=BOOT_UNIT)
    t_boot = time.perf_counter() - t0

    t0 = time.perf_counter()
    flip = sap_signflip.scaffold_signflip(
        m1_s, m2_s, y_s, sg_s, eligible_pt=ELIGIBLE_PT, B=B, seed=seed_flip)
    t_flip = time.perf_counter() - t0

    return {"macro_ap_M1b": ap1, "macro_ap_M2b": ap2,
            "delta": float(ap2["macro_ap"] - ap1["macro_ap"]),
            "bootstrap": boot, "signflip": flip,
            "timing_s": {"macro_ap": t_ap, "bootstrap": t_boot, "signflip": t_flip}}


def stage_pilot():
    logln(f"[pilot] H-5-0 계측 — B={B_PILOT}, 최대 표본 층 1개. 산출은 전량 폐기(시간만 기록).")
    d = load_common()
    df = pd.read_csv(F_STRATA)
    cons = load_consensus()
    units = estimation_units(df, d)
    biggest = max(units, key=lambda u: len(u["cids"]))
    n = len(biggest["cids"])
    logln(f"[pilot] 대상 = {biggest['axis']}/{biggest['stratum']} (n_drugs={n})")

    res = run_unit(biggest, d, cons, B_PILOT, SEED_BOOTSTRAP, SEED_SIGNFLIP)
    t = res["timing_s"]
    n_clu = res["bootstrap"]["n_clusters"]
    # B 의존 성분 / B 비의존(jackknife) 성분 분리
    #   bootstrap wall = B * t_repl + n_clusters * t_delta ;  t_delta ≈ t_ap
    t_delta = t["macro_ap"]
    t_jack = n_clu * t_delta
    t_repl_boot = max((t["bootstrap"] - t_jack) / B_PILOT, 1e-9)
    t_repl_flip = t["signflip"] / B_PILOT
    del res                                            # 파일럿 산출 폐기(봉인 저장 금지)

    per_row_boot = t_repl_boot / n
    per_row_flip = t_repl_flip / n
    per_row_delta = t_delta / n

    est, total = [], 0.0
    for u in units:
        m = len(u["cids"])
        c_u = len(set(d["scaffold"][row_index(d, u["cids"])]))
        s = B_MAIN * m * (per_row_boot + per_row_flip) + c_u * m * per_row_delta
        est.append({"axis": u["axis"], "stratum": u["stratum"], "n_drugs": m,
                    "n_clusters": c_u, "est_wall_s": s})
        total += s

    out = {
        "_scope": "공개 — 시간·표본수 뿐. 파일럿 통계 산출은 전량 폐기(봉인 저장 없음).",
        "ts_kst": now_kst(), "B_pilot": B_PILOT, "B_main": B_MAIN,
        "pilot_unit": {"axis": biggest["axis"], "stratum": biggest["stratum"],
                       "n_drugs": n, "n_clusters": n_clu},
        "pilot_timing_s": {"macro_ap_once": t_delta, "bootstrap_B100": t["bootstrap"],
                           "signflip_B100": t["signflip"],
                           "jackknife_component_s": t_jack,
                           "per_replicate_bootstrap_s": t_repl_boot,
                           "per_replicate_signflip_s": t_repl_flip},
        "n_units": len(units),
        "estimate_per_unit": est,
        "estimated_total_wall_s": total,
        "estimated_total_wall_hours": total / 3600.0,
        "estimated_total_wall_days": total / 86400.0,
        "abort_threshold_days": WALL_ABORT_DAYS,
        "exceeds_threshold": bool(total / 86400.0 > WALL_ABORT_DAYS),
        "scaling_model": ("층 wall ≈ B × n_drugs × (per-row bootstrap + per-row sign-flip) + "
                          "n_clusters × n_drugs × per-row macro_ap(jackknife). "
                          "per-row 단가는 최대 표본 층 B=100 실측에서 산출."),
        "pilot_artifacts_discarded": True,
    }
    dump_json(F_PILOT, out)
    logln(f"[pilot] 전 층({len(units)}) × B={B_MAIN} 총 추정 wall = {total / 3600:.2f}h "
          f"({total / 86400:.3f}일) · 7일 초과 = {out['exceeds_threshold']}")
    assert not out["exceeds_threshold"], \
        f"[중단] 추정 총 wall {total / 86400:.2f}일 > {WALL_ABORT_DAYS}일 — 실행하지 않는다."
    return out


def stage_estimate():
    logln(f"[estimate] H-5-1 본계산 — B={B_MAIN}, seed boot={SEED_BOOTSTRAP} "
          f"flip={SEED_SIGNFLIP}. 산출 전량 `_sealed/`.")
    d = load_common()
    df = pd.read_csv(F_STRATA)
    summ = json.load(open(F_STRATA_SUM, encoding="utf-8"))
    cons = load_consensus()
    units = estimation_units(df, d)

    sealed = {"_warning": "SEALED — 성공판정(개봉) 단계 전 열람 금지.",
              "step": "§13-6 연속 유사도 층화(블록 H)", "ts_kst": now_kst(),
              "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
              "unit": BOOT_UNIT, "eligible_pt": "None(370 PT 전열)",
              "multiplicity": "미적용 — Holm/BH 는 성공판정 단계 일괄(본 단계 raw 산출만)",
              "strata": {}}
    public_units, t_all = [], time.perf_counter()

    for k, u in enumerate(units, 1):
        key = f"{u['axis']}::{u['stratum']}"
        t0 = time.perf_counter()
        res = run_unit(u, d, cons, B_MAIN, SEED_BOOTSTRAP, SEED_SIGNFLIP)
        wall = time.perf_counter() - t0
        sealed["strata"][key] = {"axis": u["axis"], "stratum": u["stratum"], "kind": u["kind"],
                                 "n_drugs": len(u["cids"]), "cids": u["cids"], **res}
        b = res["bootstrap"]
        src = (summ["unstable"][u["axis"]] if u["kind"] == "unstable"
               else summ["axes"][u["axis"]][u["stratum"]])
        public_units.append({
            "axis": u["axis"], "stratum": u["stratum"], "kind": u["kind"],
            "n_drugs": len(u["cids"]), "n_clusters": b["n_clusters"],
            "n_eff_clusters": b["n_eff_clusters"],
            "n_pt_meeting_positive_support": src["n_pt_meeting_positive_support"],
            "inference_mode": src["inference_mode"],
            "ci_primary_status": b["ci_primary"]["status"],
            "bca_status": b["ci_bca"]["status"],
            "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
            "wall_s": wall})
        logln(f"[estimate] {k}/{len(units)} {key} n={len(u['cids'])} "
              f"clusters={b['n_clusters']} ci_primary={b['ci_primary']['status']} "
              f"wall={wall:.1f}s")

    store = sap_redaction.SealedStore(RUN_DIR)
    sealed_path = store.write_sealed("stratification_result.json", json.loads(
        json.dumps(sealed, ensure_ascii=False, default=native)))
    sealed_sha = sha256_file(sealed_path)
    total_wall = time.perf_counter() - t_all

    guard_end = guard_snapshot()
    guard_start = json.load(open(F_GATES, encoding="utf-8"))["sealed_guard_start"]
    guard_ok = (guard_end == guard_start)
    assert guard_ok, "sealed guard 변경 감지 — 확증 sealed 산출물이 수정되었다"

    pub = {
        "_scope": ("공개 — 층별 표본수·클러스터수·formal/descriptive 라벨·B·seed·소요시간·해시·"
                   "게이트 PASS/FAIL 뿐. **층별 macro AP·Δ·CI·p 는 본 파일에 없다**(전량 `_sealed/`)."),
        "ts_kst": now_kst(),
        "n_units": len(units),
        "units": public_units,
        "unstable_stratum_counts": {a: summ["unstable"][a]["n_drugs"] for a in summ["unstable"]},
        "excluded_no_target_drugs": summ["excluded_no_target_drugs"],
        "seqid_zero_observation_drugs": summ["seqid_zero_observation_drugs"],
        "B": B_MAIN, "seed_bootstrap": SEED_BOOTSTRAP, "seed_signflip": SEED_SIGNFLIP,
        "bootstrap_unit": BOOT_UNIT, "primary_ci_method": sap_bootstrap.PRIMARY_CI_METHOD,
        "bca_fallback_rule": "BCa 실패 시 percentile 대체 금지 — not_estimable 그대로 봉인",
        "total_wall_s": total_wall, "total_wall_hours": total_wall / 3600.0,
        "sealed_result_sha256": sealed_sha,
        "sealed_result_path": os.path.relpath(sealed_path, ROOT),
        "sealed_guard_n_files_end": len(guard_end),
        "sealed_guard_unchanged": bool(guard_ok),
        "ladder_freeze_sha16": EXPECT_LADDER_FREEZE_SHA16,
        "sap_manifest_sha16": EXPECT_SAP_MANIFEST_SHA16,
        "decision_functions_called": [],
        "multiplicity_applied": False,
        "open_sealed_calls": 0,
        "redaction": "공개 파일에 층별 macro AP·Δ·CI·p·null 요약·부트스트랩 분포 없음",
        "all_pass": True,
    }
    dump_json(F_PUBLIC, pub)
    logln(f"[estimate] 완료 — 층 {len(units)} · 총 wall {total_wall / 3600:.2f}h · "
          f"sealed sha16 {sealed_sha[:16]} · guard {len(guard_end)}종")
    return pub


# ═══════════════════════════════════════════════════════════════════════════
STAGES = {"bounds": stage_bounds, "identity": stage_identity, "strata": stage_strata,
          "verify": stage_verify, "pilot": stage_pilot, "estimate": stage_estimate}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=list(STAGES))
    ap.add_argument("--skip-gate", action="store_true",
                    help="H-1 게이트 재실행 생략(직전 스테이지에서 통과한 경우)")
    a = ap.parse_args()
    os.makedirs(RUN_DIR, exist_ok=True)
    with ComputeLock(script="stratification_run.py", role="runner"):
        gate_a_load(f"stage={a.stage}")
        gate_b_exclusive(f"stage={a.stage}:before")
        if not a.skip_gate:
            g = gate_h1()
            if a.stage == "verify":
                dump_json(os.path.join(RUN_DIR, "gate_h1.json"), g)
        out = STAGES[a.stage]()
        gate_b_exclusive(f"stage={a.stage}:after")
    return out


if __name__ == "__main__":
    main()
