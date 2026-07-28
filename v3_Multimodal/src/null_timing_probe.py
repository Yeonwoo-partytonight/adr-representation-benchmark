#!/usr/bin/env python3
"""null_timing_probe.py — §13-4 **사전작업**: 재배치 null 타이밍 프로브 (B=2, probe seed 격리).

⚠️ 이것은 §13-4 **본실행이 아니다.** 목적은 단 하나: permutation 1회당 실측 wall-clock·메모리·디스크를
   확보해 2,000 permutation(=global 1000 + family 1000) 인프라를 결정하는 것.
   **경험적 p·관측 Δ와의 비교·성공판정·B 조정은 일절 없다.**

동결값 무수정(SAP null_A9): NULL_B=1000(하향·상향·조기중단·재시도 영구 금지), global+family 둘 다,
  pass_rule=둘 다 p_emp<α, p_emp=(1+#{T_b≥T_obs})/(B+1), NULL_RF_COMMON_SEED=42,
  pca_rf_refit_scope=permutation마다 B_seq PCA를 fold-train에서 재적합 + RF fold별 재학습.

seed 격리(selective precision 차단):
  PROBE_SEEDS = [9000001, 9000002] — §13-4 본실행 seed namespace(≤1,000,000)와 **교집합 0**(runner assert).
  프로브 T_b는 본실행 null 분포에 **절대 편입하지 않는다**(_sealed/ 보관 후 폐기).

실행:
  .venv/bin/python3 v3_Multimodal/src/null_timing_probe.py --stage precheck   # OOF 미실행(빠름)
  .venv/bin/python3 v3_Multimodal/src/null_timing_probe.py --stage full       # identity control + 4 permutation
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
import resource
import collections
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from ladder_confirmatory import (                     # noqa: E402  (동결 레시피 재사용)
    load_frozen, MorganBlock, CountMaskBlock, SeqBlock, M1bCovariateBlock,
    rf_fit_predict, MODEL_BLOCKS, RF_KW, SEED, PCA_K,
)
from confirmatory_oof_rep1 import gate0_verify, sha256_file   # noqa: E402  (게이트0 동일 코드)
from sap import null_generator as sap_null             # noqa: E402
from sap import metrics as sap_metrics                 # noqa: E402
from sap import consensus as sap_consensus             # noqa: E402

KST = timezone(timedelta(hours=9))

# ── 프로브 전용 상수 (결과 무참조·실행 전 고정) ────────────────────────────────
PROBE_SEEDS = [9000001, 9000002]
PROBE_ONLY = True
ENTERS_NULL_DISTRIBUTION = False
# §13-4 본실행 seed namespace 상한(본실행은 b=0..NULL_B-1 계열 = ≤1e6). 프로브는 그 위 9e6대.
MAIN_SEED_NAMESPACE_MAX = 1_000_000
RESERVED_SEEDS = set(range(201, 206)) | {42}           # 확증 split seed·RF seed
N_FOLD = 5
RF_SEED = SEED                                          # 42 = NULL_RF_COMMON_SEED
AUDIT_KEEP_FIRST_N_OOF = 3                              # 감사용 예외 보관(그 외 T_b 스칼라만)

# family-constrained 교환 단위 partition 규칙 (결과 무참조·사전 고정).
# 10_target_family_biological.csv는 표적당 다중 family 허용(1,191 표적 중 14개가 2 family) →
# build_family_permutation은 **분할(partition)** 을 요구하므로 결정적 단일배정 규칙이 필요하다.
# 규칙: family_id 문자열 **사전순 최소** 1개를 그 표적의 교환 family로 배정(라벨·결과와 무관).
FAMILY_TIEBREAK_RULE = ("표적이 복수 family에 속하면 family_id 문자열 사전순 최소값 1개를 교환 family로 "
                        "배정(결정적·결과 무참조). B_fam(P-FAM) multi-hot 정의는 불변 — 본 규칙은 "
                        "null 교환 단위 partition 전용.")

# ── 경로 ──────────────────────────────────────────────────────────────────────
PROC = os.path.join(ROOT, "data", "processed")
TM = os.path.join(PROC, "target_mapping")
EMBDIR = os.path.join(TM, "protbert_emb")
F_TARGETS = os.path.join(TM, "06_targets_human.csv")
F_FAMBIO = os.path.join(TM, "10_target_family_biological.csv")
F_EMB_FROZEN = os.path.join(PROC, "drug_target_emb_meanpool.npy")

RUN_DIR = os.path.join(ROOT, "experiments", "runs", "v3_null_probe")
SEALED_DIR = os.path.join(RUN_DIR, "_sealed")
REP1_DIR = os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep1_seed201")
REP1_SEALED = os.path.join(REP1_DIR, "_sealed")
REP1_ACCESS_LOG = os.path.join(REP1_SEALED, "access.log")
SPLIT_DIR = os.path.join(PROC, "splits", "confirmatory", "rep1_seed201")

# §13-3 sealed 산출물 sha256 (docs/36 · rep1 config.json 기록값)
EXPECT_M1B_SHA = "b2a61ba846eead5f66bc89bc22275ea3fe35fee950930fbdc38f07ad7e4a3f1d"
EXPECT_M2B_SHA = "350fa12fac84ef4ca1355d256665c333d9cd8ca34de257e7321aefa36d8a3260"

_LOG = []


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    _LOG.append(line)


def flush_log():
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "run.log"), "a") as f:
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


def peak_rss_gb():
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS = bytes, Linux = kilobytes
    return float(ru / 1e9) if sys.platform == "darwin" else float(ru / 1e6)


def log_machine_read(path_rel, purpose):
    """sealed 파일 **기계 판독**(사람 노출 0) 기록 — open_sealed(사람 열람)와 구분."""
    os.makedirs(REP1_SEALED, exist_ok=True)
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": "§13-4 timing probe",
           "note": "값·요약통계는 어떤 공개 파일에도 기록하지 않음. open_sealed(사람 열람) 아님."}
    with open(REP1_ACCESS_LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ═══════════════════════════════════════════════════════════════════════════
# 표적·family 구조 (동결 입력 읽기 전용)
# ═══════════════════════════════════════════════════════════════════════════
def load_target_structure(cid_order):
    """cid→표적셋(임베딩 보유분), target→embedding, family partition 을 결정적으로 구성."""
    tdf = pd.read_csv(F_TARGETS)
    emb_files = {f[:-4] for f in os.listdir(EMBDIR) if f.endswith(".npy")}
    cidset = set(int(c) for c in cid_order)
    cid2t_raw = collections.defaultdict(set)
    for c, u in zip(tdf["cid"].astype(int), tdf["uniprot"]):
        if c in cidset and isinstance(u, str) and u:
            cid2t_raw[c].add(u)
    # 교환 단위 = mean-pool에 실제 참여하는 unique target(=임베딩 보유). 없는 표적은 B_seq에 미기여.
    cid2targets = {c: sorted(u for u in ts if u in emb_files) for c, ts in cid2t_raw.items()}
    cid2targets = {c: ts for c, ts in cid2targets.items() if ts}
    unique_targets = sorted({u for ts in cid2targets.values() for u in ts})
    n_no_emb = len({u for ts in cid2t_raw.values() for u in ts}) - len(unique_targets)
    target_emb = {u: np.load(os.path.join(EMBDIR, u + ".npy")) for u in unique_targets}

    fbio = pd.read_csv(F_FAMBIO)
    u2f = collections.defaultdict(set)
    for u, fid in zip(fbio["uniprot"], fbio["family_id"]):
        if isinstance(u, str) and u:
            u2f[u].add(str(fid))
    n_multi = sum(1 for u in unique_targets if len(u2f.get(u, ())) > 1)
    n_nofam = sum(1 for u in unique_targets if not u2f.get(u))
    fam_of = {}
    for u in unique_targets:
        fs = sorted(u2f.get(u, ()))
        fam_of[u] = fs[0] if fs else f"__NOFAMILY__{u}"   # family 미배정 → 자기 자신 singleton(고정)
    targets_by_family = collections.defaultdict(list)
    for u in unique_targets:
        targets_by_family[fam_of[u]].append(u)
    targets_by_family = {k: sorted(v) for k, v in sorted(targets_by_family.items())}

    return {
        "cid2targets": cid2targets, "unique_targets": unique_targets, "target_emb": target_emb,
        "targets_by_family": targets_by_family,
        "family_stats": {
            "n_unique_targets": len(unique_targets),
            "n_targets_without_embedding_dropped": int(n_no_emb),
            "n_families": len(targets_by_family),
            "n_targets_multi_family_in_source": int(n_multi),
            "n_targets_without_family": int(n_nofam),
            "tiebreak_rule": FAMILY_TIEBREAK_RULE,
            "source": os.path.relpath(F_FAMBIO, ROOT),
        },
    }


def meanpool_from_mapping(ts, cid_order, mapping):
    """재배치 mapping 하에서 약물별 mean-pool 재계산 — target_audit_meanpool.build_meanpool과
    **수치적으로 동일한 절차**(정렬된 표적 순서, float64 순차 누적, /k, float32 저장).
    identity mapping이면 동결 drug_target_emb_meanpool.npy 와 **바이트 동일**해야 한다(assert)."""
    cid2targets, emb = ts["cid2targets"], ts["target_emb"]
    N, D = len(cid_order), 1024
    out = np.zeros((N, D), dtype="float32")
    mask = np.zeros(N, dtype="int8")
    ntgt = np.zeros(N, dtype="int32")
    for i, c in enumerate(cid_order):
        used = cid2targets.get(int(c), [])         # 이미 sorted·임베딩 보유
        k = len(used)
        ntgt[i] = k
        if k == 0:
            continue
        acc = np.zeros(D, dtype="float64")
        for u in used:
            acc += emb[mapping[u]].astype("float64")
        out[i] = (acc / k).astype("float32")
        mask[i] = 1
    return out, mask, ntgt


# ═══════════════════════════════════════════════════════════════════════════
# M2b 5-fold OOF (동결 파이프라인과 동일 경로 — permutation된 emb만 주입)
# ═══════════════════════════════════════════════════════════════════════════
def run_m2b_oof(d, fold_of_row, emb_matrix, label):
    """M2b만 5-fold OOF 재계산. fold마다 B_seq PCA 재적합·RF random_state=42 (SAP A9 refit scope).
    반환: (oof float64 (N,K), per-fold 시간, 진단)."""
    N = len(d["cid_order"])
    Y = d["Ym"]
    K = Y.shape[1]

    t_blocks0 = time.perf_counter()
    b_morgan = MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    b_count = CountMaskBlock(d["ntgt"], d["mask"])
    b_seq = SeqBlock(emb_matrix, d["mask"], pca_k=PCA_K)
    b_m1b = M1bCovariateBlock(d["cov_by_cid"], d["cid_order"], include_pchembl=False, name="B_m1b")
    blocks = {"B0": b_morgan, "B1": b_count, "B_seq": b_seq, "B_m1b": b_m1b}
    assert b_m1b.dim == 10, f"primary B_m1b dim={b_m1b.dim} != 10"
    assert MODEL_BLOCKS["M2b"] == ["B0", "B1", "B_m1b", "B_seq"]
    t_blocks = time.perf_counter() - t_blocks0

    oof = np.full((N, K), np.nan, dtype=np.float64)
    fold_times, fold_diag = [], []
    for kf in range(N_FOLD):
        t0 = time.perf_counter()
        te = np.where(fold_of_row == kf)[0]
        tr = np.where(fold_of_row != kf)[0]
        b_morgan.fit(tr)
        b_count.fit(tr)
        t_fit0 = time.perf_counter()
        b_seq.fit(tr)                      # ★ permutation마다·fold마다 PCA 재적합
        t_pca = time.perf_counter() - t_fit0
        b_m1b.fit(tr)
        leak = {b: blocks[b].leakage_assert(tr) for b in ("B0", "B1", "B_seq", "B_m1b")}
        expect = np.zeros(N, dtype=bool)
        expect[tr] = True
        expect &= d["mask"].astype(bool)
        assert np.array_equal(b_seq._fit_rows_mask, expect), f"[fold {kf}] B_seq fit 모집단 != train∩매핑"
        assert all(v["leak_rows"] == 0 for v in leak.values()), f"[fold {kf}] leak_rows != 0"

        t_x0 = time.perf_counter()
        Xtr = np.hstack([blocks[b].transform(tr) for b in MODEL_BLOCKS["M2b"]]).astype(np.float32)
        Xte = np.hstack([blocks[b].transform(te) for b in MODEL_BLOCKS["M2b"]]).astype(np.float32)
        t_assemble = time.perf_counter() - t_x0

        t_rf0 = time.perf_counter()
        assert RF_SEED == sap_null.NULL_RF_COMMON_SEED == 42, "RF common seed != 42"
        oof[te] = rf_fit_predict(Xtr, Y[tr], Xte, seed=RF_SEED)
        t_rf = time.perf_counter() - t_rf0

        dt = time.perf_counter() - t0
        fold_times.append(dt)
        fold_diag.append({"fold": kf, "n_train": int(len(tr)), "n_test": int(len(te)),
                          "bseq_fit_rows": int(b_seq._fit_rows_mask.sum()),
                          "dim_M2b": int(Xtr.shape[1]), "rf_random_state": RF_SEED,
                          "sec_total": dt, "sec_pca_fit": t_pca,
                          "sec_assemble": t_assemble, "sec_rf": t_rf})
        logln(f"  [{label}] fold {kf} {dt:6.1f}s (PCA {t_pca:.1f}s · 조립 {t_assemble:.1f}s · RF {t_rf:6.1f}s) "
              f"| train={len(tr)} test={len(te)} bseq_fit={int(b_seq._fit_rows_mask.sum())} dim={Xtr.shape[1]}")
    assert not np.isnan(oof).any(), "OOF 미완성(NaN)"
    return oof, {"sec_block_build": t_blocks, "folds": fold_diag,
                 "sec_total": float(sum(fold_times) + t_blocks)}


# ═══════════════════════════════════════════════════════════════════════════
# 프로브
# ═══════════════════════════════════════════════════════════════════════════
def seed_isolation_assert():
    for s in PROBE_SEEDS:
        assert s > MAIN_SEED_NAMESPACE_MAX, f"PROBE seed {s} 가 본실행 namespace(≤{MAIN_SEED_NAMESPACE_MAX}) 침범"
        assert s not in RESERVED_SEEDS, f"PROBE seed {s} 예약 seed와 충돌"
    assert len(set(PROBE_SEEDS)) == len(PROBE_SEEDS), "PROBE seed 중복"
    return {"probe_seeds": PROBE_SEEDS, "main_seed_namespace_max": MAIN_SEED_NAMESPACE_MAX,
            "reserved_seeds": sorted(RESERVED_SEEDS),
            "intersection_with_main_namespace": 0,
            "rule": "PROBE seed > 본실행 namespace 상한 → 교집합 공집합(범위 비교로 증명)",
            "asserted": True}


def build_mapping(mode, ts, seed):
    if mode == "global":
        m = sap_null.build_global_permutation(ts["unique_targets"], seed)
        rep = {"mode": "global", "n_exchange_units": len(ts["unique_targets"]),
               "n_fixed_points": int(sum(1 for k, v in m.items() if k == v)),
               "rule": "full permutation(fixed point 허용, derangement 아님)"}
        return m, rep
    m, rep = sap_null.build_family_permutation(ts["targets_by_family"], seed)
    rep = {"mode": "family", **rep,
           "n_fixed_points": int(sum(1 for k, v in m.items() if k == v))}
    return m, rep


def stage_precheck(args):
    logln("=" * 78)
    logln("[probe] §13-4 타이밍 프로브 — precheck(게이트0·구조·permutation assert, OOF 미실행)")
    logln("[무결성] p 계산·T_obs 비교·성공판정·B 조정 없음 · 네트워크 0 · data/raw 불변 · git 커밋 없음")

    g0 = gate0_verify()
    iso = seed_isolation_assert()
    logln(f"[seed 격리] PROBE_SEEDS={PROBE_SEEDS} · 본실행 namespace(≤{MAIN_SEED_NAMESPACE_MAX})와 교집합 0 — assert PASS")
    logln(f"[SAP 동결값] NULL_B={sap_null.NULL_B} · NULL_RF_COMMON_SEED={sap_null.NULL_RF_COMMON_SEED} "
          f"(무수정 확인; 프로브는 B=2로 시간만 측정, 본 분포 미편입)")

    d = load_frozen()
    cid_order = d["cid_order"]
    ts = load_target_structure(cid_order)
    logln(f"[구조] unique target(교환 단위)={ts['family_stats']['n_unique_targets']} · "
          f"family={ts['family_stats']['n_families']} · "
          f"복수 family 표적={ts['family_stats']['n_targets_multi_family_in_source']}(사전순 최소로 단일배정) · "
          f"family 미배정={ts['family_stats']['n_targets_without_family']}")

    # mean-pool 재계산 절차가 동결 산출물과 바이트 동일한지 (identity mapping) — OOF 전 필수 전제
    ident = {u: u for u in ts["unique_targets"]}
    emb_id, mask_id, ntgt_id = meanpool_from_mapping(ts, cid_order, ident)
    frozen_emb = np.load(F_EMB_FROZEN)
    bit_ok = bool(np.array_equal(emb_id.view(np.uint8), frozen_emb.view(np.uint8)))
    mask_ok = bool(np.array_equal(mask_id, d["mask"]))
    ntgt_ok = bool(np.array_equal(ntgt_id, d["ntgt"]))
    assert bit_ok and mask_ok and ntgt_ok, \
        f"identity mean-pool 재계산이 동결본과 불일치 (emb={bit_ok} mask={mask_ok} ntgt={ntgt_ok})"
    logln(f"[전제] identity mean-pool 재계산 == 동결 drug_target_emb_meanpool.npy **바이트 동일** "
          f"(mask·n_targets 동일) → 재배치 하네스가 동결 입력을 정확히 재현")

    # incidence·family 보고 (SAP 연산자)
    inc = sap_null.null_incidence_report(ts["cid2targets"], cid_order, ts["unique_targets"])
    _, fam_rep = sap_null.build_family_permutation(ts["targets_by_family"], PROBE_SEEDS[0])
    logln(f"[incidence] eligible target={inc['n_targets']} · drugs={inc['n_drugs']} · edges={inc['n_edges']} · "
          f"incidence_ratio={inc['incidence_ratio']:.5f} · 매핑 약물 {inc['n_drugs_with_target']}"
          f"({inc['frac_drugs_with_target']:.3f})")
    logln(f"[family] family={fam_rep['n_families']} · 교환가능 family={fam_rep['n_exchangeable_families']} "
          f"· 고정(|family|≤2) family={fam_rep['n_fixed_families_singleton_or_size2']} "
          f"· **고정 target={fam_rep['n_fixed_targets']}**({fam_rep['fixed_target_frac']:.3f}) "
          f"· 교환가능 target={fam_rep['n_exchangeable_targets']}")

    # permutation 보존 assert + 결정성(같은 seed → 같은 permutation)
    perm_checks = []
    for mode in ("global", "family"):
        for s in PROBE_SEEDS:
            m, rep = build_mapping(mode, ts, s)
            pres = sap_null.assert_preservation(ts["cid2targets"], ts["target_emb"], m, cid_order)
            m2, _ = build_mapping(mode, ts, s)
            deterministic = bool(m == m2)
            assert deterministic, f"[{mode} seed {s}] 같은 seed 재현 실패"
            perm_checks.append({"mode": mode, "seed": s, "preservation": pres, "report": rep,
                                "seed_determinism_same_mapping": deterministic})
            logln(f"[permutation {mode} seed={s}] assert_preservation PASS "
                  f"(bijection·target별 embedding 공유·degree/incidence/결측 보존, "
                  f"shared checks={pres['n_shared_target_checks']}) | 고정점={rep['n_fixed_points']} | 재현성 PASS")

    # permutation 간 독립성(교차 seed mapping 상이) 확인
    indep = {}
    for mode in ("global", "family"):
        ma, _ = build_mapping(mode, ts, PROBE_SEEDS[0])
        mb, _ = build_mapping(mode, ts, PROBE_SEEDS[1])
        n_same = sum(1 for k in ma if ma[k] == mb[k])
        indep[mode] = {"n_targets": len(ma), "n_identical_assignments_across_seeds": int(n_same),
                       "frac_identical": float(n_same / len(ma))}
    logln(f"[병렬화] permutation은 seed만으로 완전 결정 → b별 독립 생성 가능. "
          f"교차 seed 동일배정 global {indep['global']['n_identical_assignments_across_seeds']}/"
          f"{indep['global']['n_targets']} · family {indep['family']['n_identical_assignments_across_seeds']}/"
          f"{indep['family']['n_targets']}")

    # sealed 산출물 무결성(파일 sha) — 값 미판독
    sealed_sha = {fn: sha256_file(os.path.join(REP1_SEALED, fn))
                  for fn in ("oof_M1b.npz", "oof_M2b.npz")}
    m1b_ok = sealed_sha["oof_M1b.npz"] == EXPECT_M1B_SHA
    m2b_ok = sealed_sha["oof_M2b.npz"] == EXPECT_M2B_SHA
    assert m1b_ok and m2b_ok, f"§13-3 sealed 산출물 sha 불일치 (M1b={m1b_ok} M2b={m2b_ok})"
    logln(f"[sealed] §13-3 oof_M1b.npz·oof_M2b.npz sha256 기대값 일치 (파일 무결성만 확인, 값 미판독)")

    out = {
        "stage": "precheck", "ts_kst": now_kst(), "gate0": g0, "seed_isolation": iso,
        "target_structure": ts["family_stats"], "null_incidence_report": inc, "family_report": fam_rep,
        "identity_meanpool_bitwise_equals_frozen": bit_ok,
        "permutation_checks": perm_checks, "cross_seed_independence": indep,
        "sealed_sha256_verified": {"oof_M1b.npz": m1b_ok, "oof_M2b.npz": m2b_ok},
    }
    dump_json(os.path.join(RUN_DIR, "_precheck.json"), out)
    logln("[precheck] 완료 — OOF 미실행. 다음: --stage full")
    flush_log()
    return out


def build_timing(per_perm, ident_ctl, diag_ident, pre, t_start, n_saved_oof):
    """타이밍 집계(결과-독립 = 공개 가능). 순수 함수 — 합성 입력으로 단위검증 가능(_selftest)."""
    tot = [p["sec_total"] for p in per_perm]
    g = [p["sec_total"] for p in per_perm if p["mode"] == "global"]
    f = [p["sec_total"] for p in per_perm if p["mode"] == "family"]
    med = float(np.median(tot))
    lo, hi = float(min(tot)), float(max(tot))
    B = sap_null.NULL_B
    n_perm_total = 2 * B                       # global B + family B
    oof_bytes = next((p["oof_npz_bytes_if_saved"] for p in per_perm
                      if p["oof_npz_bytes_if_saved"]), 0)
    try:
        import threadpoolctl
        pools = [{"internal_api": q["internal_api"], "prefix": q.get("prefix"),
                  "num_threads": q["num_threads"]} for q in threadpoolctl.threadpool_info()]
    except Exception as e:                                  # noqa: BLE001
        pools = [{"unavailable": str(e)}]

    rf_share = [x["sec_rf"] / x["sec_total"] for p in per_perm for x in p["fold_breakdown"]]
    return {
        "_scope": "§13-4 타이밍 프로브(B=2) — 결과-독립 계측치만. AP·Δ·T_b·p 없음.",
        "ts_kst": now_kst(),
        "probe_only": PROBE_ONLY, "enters_null_distribution": ENTERS_NULL_DISTRIBUTION,
        "per_permutation": [{k: v for k, v in p.items() if k != "fold_breakdown"} for p in per_perm],
        "fold_breakdown": {f"{p['mode']}_seed{p['seed']}": p["fold_breakdown"] for p in per_perm},
        "identity_control": {"sec_wall_clock": ident_ctl["sec_wall_clock"],
                             "verdict": ident_ctl["verdict"],
                             "fold_breakdown": diag_ident["folds"]},
        "wall_clock_sec": {
            "per_permutation_all": tot, "global": g, "family": f,
            "median_all": med, "min": lo, "max": hi,
            "median_global": float(np.median(g)), "median_family": float(np.median(f)),
        },
        "projection_2000_permutations": {
            "definition": f"NULL_B={B} × 2 모드(global·family) = {n_perm_total} permutation, 단일 프로세스 순차",
            "n_permutations": n_perm_total,
            "median_sec_per_perm": med,
            "total_sec_median": med * n_perm_total,
            "total_hours_median": med * n_perm_total / 3600.0,
            "total_days_median": med * n_perm_total / 86400.0,
            "total_hours_lower_bound_min": lo * n_perm_total / 3600.0,
            "total_hours_upper_bound_max": hi * n_perm_total / 3600.0,
            "note": "프로브 B=2의 표본이 작아 구간은 관측 min/max 기반의 거친 경계임.",
        },
        "memory": {"peak_rss_gb": peak_rss_gb(),
                   "platform_rss_unit": "bytes" if sys.platform == "darwin" else "kB"},
        "compute": {
            "cpu_count": os.cpu_count(),
            "rf_n_jobs_config": RF_KW["n_jobs"],
            "rf_n_jobs_effective": os.cpu_count() if RF_KW["n_jobs"] == -1 else RF_KW["n_jobs"],
            "multioutput_wrapper": "MultiOutputClassifier(n_jobs=None → 370 PT 순차, 각 RF는 n_jobs=-1 병렬)",
            "rf_share_of_fold_time": {"min": float(min(rf_share)), "max": float(max(rf_share)),
                                      "median": float(np.median(rf_share))},
            "blas_env": {k: os.environ.get(k) for k in
                         ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                          "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "threadpool_info": pools,
        },
        "disk": {
            "oof_npz_bytes_per_permutation": oof_bytes,
            "design_T_b_scalar_only": True,
            "projected_bytes_T_b_only": n_perm_total * 64,
            "projected_bytes_if_all_oof_saved": oof_bytes * n_perm_total,
            "projected_gb_if_all_oof_saved": oof_bytes * n_perm_total / 1e9,
            "audit_exception": f"최초 {AUDIT_KEEP_FIRST_N_OOF}개 permutation OOF만 감사용 보관, 나머지는 T_b 스칼라만 저장",
            "actual_audit_oof_saved": n_saved_oof,
        },
        "null_incidence_report": pre["null_incidence_report"],
        "family_report": pre["family_report"],
        "target_structure": pre["target_structure"],
        "cross_seed_independence": pre["cross_seed_independence"],
        "parallelization_diagnosis": {
            "permutations_independent": True,
            "evidence": ("permutation은 seed만으로 결정(같은 seed→같은 mapping, assert 확인)되고 "
                         "M1b는 permutation 불변이며 fold split은 고정 → b 간 상태 공유 0."),
            "seed_determinism_verified": True,
            "rf_dominates": ("RF 학습이 fold 시간의 대부분(rf_share_of_fold_time) — PCA 재적합·행렬조립은 무시 가능. "
                             "따라서 permutation-불변 블록 캐싱은 실효 없음(측정으로 기각)."),
            "intra_rf_parallelism": "RF n_jobs=-1이 이미 전 코어 사용 → permutation 병렬화 시 코어 분할 필요(초선형 이득 없음)",
            "unused_axis_multioutput_njobs": (
                "MultiOutputClassifier(n_jobs=None) = 370 PT 순차 학습이 현재 미활용 병렬 축. "
                "각 PT RF는 random_state=42 고정·상호 독립이므로 n_jobs 상향은 **수치 불변**(identity control로 재검증 가능). "
                "본실행 전 1-permutation 마이크로벤치로 실측 권장 — 프로브에서는 미변경."),
        },
        "not_performed": [
            "empirical_p 호출·p 계산", "T_obs와 T_b 비교", "null 분포 시각화",
            "NULL_B 변경·조기중단·재시도", "bootstrap CI", "sign-flip", "SESOI/TOST", "성공판정",
            "반복 2·3 split 생성", "M0/M1/M2/P-ID/P-FAM/C-CAP·GIN·late-fusion·shift",
            "sealed 수치의 사람 열람", "docs/30 수정", "RF/PCA 하이퍼 변경",
        ],
        "elapsed_total_sec": time.perf_counter() - t_start,
    }


def _selftest():
    """build_timing 의 키·산술 경로를 합성 입력으로 검증(실데이터·파일 쓰기 없음)."""
    fb = [{"fold": k, "sec_total": 100.0 + k, "sec_pca_fit": 0.1, "sec_assemble": 0.01,
           "sec_rf": 99.0 + k, "n_train": 874, "n_test": 218, "bseq_fit_rows": 689,
           "dim_M2b": 2124, "rf_random_state": 42} for k in range(5)]
    per_perm = [{"mode": m, "seed": s, "sec_total": 600.0 + i * 10,
                 "sec_permutation_build_and_assert": 1.0, "sec_meanpool_recompute": 0.5,
                 "sec_block_build": 2.0, "sec_folds": [x["sec_total"] for x in fb],
                 "fold_breakdown": fb, "permutation_report": {"mode": m},
                 "preservation_shared_checks": 11422,
                 "oof_npz_bytes_if_saved": 554534 if i < 3 else None}
                for i, (m, s) in enumerate([("global", 1), ("global", 2), ("family", 1), ("family", 2)])]
    pre = {"null_incidence_report": {"n_targets": 1191}, "family_report": {"n_families": 42},
           "target_structure": {"n_unique_targets": 1191}, "cross_seed_independence": {}}
    t = build_timing(per_perm, {"sec_wall_clock": 677.9, "verdict": "PASS"},
                     {"folds": fb}, pre, time.perf_counter(), 3)
    assert t["projection_2000_permutations"]["n_permutations"] == 2 * sap_null.NULL_B
    assert t["disk"]["oof_npz_bytes_per_permutation"] == 554534
    assert len(t["wall_clock_sec"]["global"]) == 2 and len(t["wall_clock_sec"]["family"]) == 2
    assert 0.0 < t["compute"]["rf_share_of_fold_time"]["median"] <= 1.0
    json.dumps(t, ensure_ascii=False, default=native)          # 직렬화 가능성
    print("[_selftest] build_timing PASS — 키·산술·직렬화 정상")
    return True


def stage_full(args):
    t_start = time.perf_counter()
    logln("=" * 78)
    logln("[probe] §13-4 타이밍 프로브 — full(identity control + permutation 4회). p·비교·판정 없음.")
    pre = stage_precheck(args)

    d = load_frozen()
    cid_order = d["cid_order"]
    Y = d["Ym"]
    K = Y.shape[1]
    ts = load_target_structure(cid_order)
    cid2fold = json.load(open(os.path.join(SPLIT_DIR, "folds.json")))
    fold_of_row = np.array([cid2fold[str(int(c))] for c in cid_order], dtype=int)
    logln(f"[split] §13-3 확증 split(seed 201) 재사용 — fold 크기 "
          f"{[int((fold_of_row == k).sum()) for k in range(N_FOLD)]} (재생성 없음)")

    os.makedirs(SEALED_DIR, exist_ok=True)
    eligible = np.arange(K)

    # ── 2-A: M1b 재사용(기계 판독, 사람 노출 0) ──
    log_machine_read(os.path.relpath(os.path.join(REP1_SEALED, "oof_M1b.npz"), ROOT),
                     "null M1b reuse")
    with np.load(os.path.join(REP1_SEALED, "oof_M1b.npz")) as z:
        oof_m1b = z["oof"]
    ap_m1b = sap_metrics.macro_ap(Y, sap_consensus.build_consensus([oof_m1b]), eligible)["macro_ap"]
    logln("[2-A] §13-3 sealed oof_M1b.npz sha 검증 후 **1회 로드** — 전 permutation 재사용 "
          "(target 재배치는 B_seq만 교란 → M1b OOF는 permutation 불변). 값 미출력.")

    # ── 2-B: identity permutation 하네스 정합성 control ──
    logln("[2-B] identity permutation control 시작 — 결과가 §13-3 sealed oof_M2b.npz와 바이트 동일해야 함")
    ident = {u: u for u in ts["unique_targets"]}
    emb_id, mask_id, _ = meanpool_from_mapping(ts, cid_order, ident)
    assert np.array_equal(emb_id.view(np.uint8), np.load(F_EMB_FROZEN).view(np.uint8))
    t0 = time.perf_counter()
    oof_ident, diag_ident = run_m2b_oof(d, fold_of_row, emb_id, "identity")
    t_ident = time.perf_counter() - t0

    ident_npz = os.path.join(SEALED_DIR, "oof_M2b_identity.npz")
    np.savez_compressed(ident_npz, oof=oof_ident,
                        cid=np.array([int(c) for c in cid_order]), fold=fold_of_row)
    file_sha = sha256_file(ident_npz)
    log_machine_read(os.path.relpath(os.path.join(REP1_SEALED, "oof_M2b.npz"), ROOT),
                     "identity control byte-comparison")
    with np.load(os.path.join(REP1_SEALED, "oof_M2b.npz")) as z:
        arr_sealed = z["oof"]
    arr_sha_sealed = hashlib.sha256(np.ascontiguousarray(arr_sealed).tobytes()).hexdigest()
    arr_sha_probe = hashlib.sha256(np.ascontiguousarray(oof_ident).tobytes()).hexdigest()
    file_match = (file_sha == EXPECT_M2B_SHA)
    array_match = (arr_sha_probe == arr_sha_sealed)
    ident_ctl = {
        "control": "identity permutation (모든 표적 원위치) → M2b 5-fold OOF 재계산",
        "sealed_file_sha256_expected": EXPECT_M2B_SHA,
        "probe_file_sha256": file_sha,
        "file_sha256_match": bool(file_match),
        "array_sha256_sealed": arr_sha_sealed,
        "array_sha256_probe": arr_sha_probe,
        "array_bitwise_match": bool(array_match),
        "n_elements_differing": int(np.sum(arr_sealed != oof_ident)),
        "verdict": "PASS" if (file_match and array_match) else "FAIL",
        "sec_wall_clock": t_ident,
        "note": ("null 하네스가 §13-3 동결 파이프라인과 동일함을 증명하는 유일한 검증. "
                 "값 노출 0(sha256 비교만)."),
    }
    dump_json(os.path.join(RUN_DIR, "identity_control.json"), ident_ctl)
    logln(f"[2-B] identity control = **{ident_ctl['verdict']}** "
          f"(파일 sha 일치={file_match} · 배열 sha 일치={array_match} · 불일치 원소={ident_ctl['n_elements_differing']}) "
          f"| {t_ident:.1f}s")
    if ident_ctl["verdict"] != "PASS":
        logln("[2-B] ❌ FAIL — 즉시 정지. null 하네스가 동결 파이프라인과 불일치.")
        flush_log()
        sys.exit(3)

    # ── permutation 4회(모드 2 × seed 2) — 시간만 측정 ──
    per_perm, sealed_T = [], []
    n_saved_oof = 0
    for mode in ("global", "family"):
        for s in PROBE_SEEDS:
            tag = f"{mode}_seed{s}"
            logln(f"[perm] {tag} 시작 (probe_only — 본 null 분포 미편입)")
            t_p0 = time.perf_counter()
            mapping, rep = build_mapping(mode, ts, s)
            pres = sap_null.assert_preservation(ts["cid2targets"], ts["target_emb"], mapping, cid_order)
            t_map = time.perf_counter() - t_p0
            t_mp0 = time.perf_counter()
            emb_p, mask_p, ntgt_p = meanpool_from_mapping(ts, cid_order, mapping)
            t_mp = time.perf_counter() - t_mp0
            assert np.array_equal(mask_p, d["mask"]) and np.array_equal(ntgt_p, d["ntgt"]), \
                "재배치가 mask/degree를 바꿈(보존 위반)"
            oof_p, diag_p = run_m2b_oof(d, fold_of_row, emb_p, tag)
            t_perm = time.perf_counter() - t_p0

            ap_p = sap_metrics.macro_ap(Y, sap_consensus.build_consensus([oof_p]), eligible)["macro_ap"]
            sealed_T.append({"mode": mode, "seed": s, "T_b": float(ap_p - ap_m1b),
                             "probe_only": True, "enters_null_distribution": False})

            disk_bytes = None
            if n_saved_oof < AUDIT_KEEP_FIRST_N_OOF:
                p = os.path.join(SEALED_DIR, f"oof_M2b_perm_{tag}.npz")
                np.savez_compressed(p, oof=oof_p, cid=np.array([int(c) for c in cid_order]),
                                    fold=fold_of_row)
                disk_bytes = os.path.getsize(p)
                n_saved_oof += 1
            per_perm.append({
                "mode": mode, "seed": s, "sec_total": t_perm,
                "sec_permutation_build_and_assert": t_map, "sec_meanpool_recompute": t_mp,
                "sec_block_build": diag_p["sec_block_build"],
                "sec_folds": [f["sec_total"] for f in diag_p["folds"]],
                "fold_breakdown": diag_p["folds"],
                "permutation_report": rep,
                "preservation_shared_checks": pres["n_shared_target_checks"],
                "oof_npz_bytes_if_saved": disk_bytes,
            })
            logln(f"[perm] {tag} 완료 — **{t_perm:.1f}s** "
                  f"(재배치+assert {t_map:.1f}s · mean-pool {t_mp:.1f}s · 블록 {diag_p['sec_block_build']:.1f}s · "
                  f"5-fold {sum(x['sec_total'] for x in diag_p['folds']):.1f}s) | T_b는 _sealed 기록(값 미출력)")

    # ── sealed T_b (폐기 예정) ──
    dump_json(os.path.join(SEALED_DIR, "probe_stats.json"), {
        "_warning": "SEALED · PROBE ONLY — 본 §13-4 null 분포에 편입 금지(폐기 예정).",
        "probe_only": PROBE_ONLY, "enters_null_distribution": ENTERS_NULL_DISTRIBUTION,
        "probe_seeds": PROBE_SEEDS, "T_b": sealed_T,
        "note": "T_obs와 비교하지 않았고 p_emp를 계산하지 않았음(empirical_p 미호출).",
    })

    timing = build_timing(per_perm, ident_ctl, diag_ident, pre, t_start, n_saved_oof)
    dump_json(os.path.join(RUN_DIR, "timing_public.json"), timing)
    w = timing["wall_clock_sec"]
    med, lo, hi = w["median_all"], w["min"], w["max"]
    g, f = w["global"], w["family"]
    n_perm_total = timing["projection_2000_permutations"]["n_permutations"]
    B = sap_null.NULL_B
    oof_bytes = timing["disk"]["oof_npz_bytes_per_permutation"]

    dump_json(os.path.join(RUN_DIR, "config.json"), {
        "step": "§13-4 사전작업 — 재배치 null 타이밍 프로브(B=2, probe seed 격리)",
        "purpose": "permutation 1회당 실측 wall-clock·메모리·디스크 확보 → 2,000 permutation 인프라 결정",
        "probe_only": PROBE_ONLY, "enters_null_distribution": ENTERS_NULL_DISTRIBUTION,
        "probe_seeds": PROBE_SEEDS, "seed_isolation": pre["seed_isolation"],
        "sap_frozen_values_used": {
            "NULL_B": sap_null.NULL_B, "NULL_RF_COMMON_SEED": sap_null.NULL_RF_COMMON_SEED,
            "PRESERVED": sap_null.PRESERVED, "PCA_RF_REFIT_SCOPE": sap_null.PCA_RF_REFIT_SCOPE,
            "modes": ["global", "family-constrained"],
            "pass_rule": "둘 다 p_emp<α (본실행에서 적용 — 프로브에서는 미적용)",
            "p_emp_formula": "(1 + #{T_b ≥ T_obs}) / (B+1)",
            "modified_by_probe": False,
        },
        "family_partition_rule_for_null": FAMILY_TIEBREAK_RULE,
        "models": {"recomputed": ["M2b"], "reused_from_sealed": ["M1b"]},
        "m1b_reuse": {
            "path": os.path.relpath(os.path.join(REP1_SEALED, "oof_M1b.npz"), ROOT),
            "sha256_expected": EXPECT_M1B_SHA, "sha256_verified": True,
            "rationale": "target-embedding 재배치는 B_seq만 교란 → M1b OOF는 permutation 불변",
            "access_type": "machine_read (human_exposure=false) — open_sealed(사람 열람) 아님",
        },
        "split": {"reused": os.path.relpath(SPLIT_DIR, ROOT), "seed": 201, "n_fold": N_FOLD,
                  "regenerated": False},
        "rf": {**RF_KW, "random_state": RF_SEED, "retuned": False},
        "pca": {"k": PCA_K, "svd_solver": "full", "random_state": SEED,
                "refit_scope": "permutation마다 fold-train(∩매핑)에서 재적합"},
        "gate0": pre["gate0"],
        "identity_control": {"verdict": ident_ctl["verdict"],
                             "file_sha256_match": ident_ctl["file_sha256_match"],
                             "array_bitwise_match": ident_ctl["array_bitwise_match"]},
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "sklearn": __import__("sklearn").__version__,
                     "scipy": __import__("scipy").__version__, "rdkit": __import__("rdkit").__version__,
                     "platform": platform.platform()},
        "not_performed": timing["not_performed"],
        "integrity": {"network_calls": 0, "raw_data_modified": False, "docs30_modified": False,
                      "frozen_blocks_recomputed": False, "confirmatory_split_regenerated": False,
                      "sealed_values_human_read": False, "git_commit": False},
        "outputs": {"public": ["config.json", "timing_public.json", "identity_control.json", "run.log"],
                    "sealed": ["_sealed/probe_stats.json (T_b 4개, 폐기 예정)",
                               f"_sealed/oof_M2b_identity.npz", "_sealed/oof_M2b_perm_*.npz (감사용 3개)"]},
    })

    logln(f"[집계] permutation 중앙값 {med:.1f}s (global {np.median(g):.1f}s · family {np.median(f):.1f}s) "
          f"| min {lo:.1f}s max {hi:.1f}s")
    logln(f"[추정] 2,000 permutation({B}×2 모드) 단일 프로세스 순차 = "
          f"{med * n_perm_total / 3600:.1f}h (구간 {lo * n_perm_total / 3600:.1f}~{hi * n_perm_total / 3600:.1f}h)")
    logln(f"[자원] peak RSS {timing['memory']['peak_rss_gb']:.2f} GB · cores {os.cpu_count()} · "
          f"RF n_jobs 실효 {timing['compute']['rf_n_jobs_effective']}")
    logln(f"[디스크] permutation당 OOF npz {oof_bytes / 1e3:.0f} KB → 전량 저장 시 "
          f"{timing['disk']['projected_gb_if_all_oof_saved']:.2f} GB / T_b 스칼라만 저장 시 "
          f"{timing['disk']['projected_bytes_T_b_only'] / 1e3:.0f} KB")
    logln("[무결성] empirical_p 미호출 · T_obs 비교 없음 · 성공판정 없음 · NULL_B 무수정 · "
          "프로브 T_b는 본 분포 미편입(_sealed 격리)")
    flush_log()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["precheck", "full", "selftest"], required=True)
    args = ap.parse_args()
    if args.stage == "selftest":
        _selftest()
        return
    os.makedirs(RUN_DIR, exist_ok=True)
    if args.stage == "precheck":
        stage_precheck(args)
    else:
        stage_full(args)


if __name__ == "__main__":
    main()
