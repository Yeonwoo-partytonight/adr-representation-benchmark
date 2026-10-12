#!/usr/bin/env python3
"""preconfirm_hardening.py — v3 확증 직전 하드닝 감사 A1~A5 (docs/38 §3~§7, docs/37 §2-1).

A0(primary B_m1b 10차원 재지정·재동결)는 ladder_confirmatory.py에서 수행됨(선행). 본 스크립트는
그 **재동결 상태**를 대상으로 step-3 게이트 감사 A1~A5를 산출한다.

  A1  전처리 fold-only fit assert (특히 B_seq PCA fit 범위 = outer-train-drug 표적) — 표현누수 차단.
  A2  split 진단 사전 동결(결과 무참조): scaffold group 통계·N_eff·PT positive-scaffold·undefined-AP 규칙.
  A3  RF max_features 감사(설정 변경 금지·문서화).
  A4  B_seq truncation/pooling/isoform 감사표.
  A5  target count 정의 일관성.

⛔ 무결성: 확증용 split(seed 201~205×3)·OOF **생성/조회 금지.** A2의 seed-201 fold-level 진단은
   **의도적으로 유보**(확증 split 미생성). 네트워크 0. 라벨·구조·mean-pool·split(seed-42 dev 외) 불변.

산출: experiments/audits/A1_nested_fit_assert.json, A2_split_diagnostics.json,
      A3_rf_maxfeatures_note.md, A4_bseq_truncation_audit.csv, A5_target_count_check.json,
      experiments/audits/run.log (assert 결과·시각).

실행: .venv/bin/python3 v3_Multimodal/src/preconfirm_hardening.py   (A0 재동결 이후)
"""
import os
import sys
import json
import math
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.ensemble import RandomForestClassifier

RDLogger.DisableLog("rdApp.*")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PROC = os.path.join(ROOT, "data", "processed")
TM = os.path.join(PROC, "target_mapping")
AUDIT = os.path.join(ROOT, "experiments", "audits")
os.makedirs(AUDIT, exist_ok=True)

# 동결 블록·하네스 재사용(단일 정의 소스). main()은 __name__ 가드라 import 시 미실행.
sys.path.insert(0, HERE)
import ladder_confirmatory as L  # noqa: E402

KST = timezone(timedelta(hours=9))
_LOGLINES = []


def logln(m):
    line = f"{datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')} | {m}"
    print(line, flush=True)
    _LOGLINES.append(line)


def native(o):
    """numpy → python 기본형(json 직렬화)."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, dict):
        return {k: native(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [native(v) for v in o]
    return o


def dump(name, obj):
    p = os.path.join(AUDIT, name)
    json.dump(native(obj), open(p, "w"), indent=2, ensure_ascii=False)
    logln(f"[산출] {os.path.relpath(p, ROOT)} 저장")
    return p


def _scaffold(smi):
    """Bemis–Murcko scaffold — step6_scaffold_split.py와 동일 정의(includeChirality=False)."""
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════
# A1 — nested fit-scope assert (특히 B_seq PCA fit 범위)
# ═══════════════════════════════════════════════════════════════════════════
def a1_nested_fit_assert(d):
    logln("[A1] 전처리 fold-only fit assert (B_seq PCA fit 범위 포함)")
    N = len(d["cid_order"])
    train_idx = np.where(d["sp"] == "train")[0]
    valid_idx = np.where(d["sp"] == "valid")[0]
    test_idx = np.where(d["sp"] == "test")[0]

    # 블록 인스턴스화 + seed-42 dev train fit (확증 하네스가 fold마다 재사용하는 레시피)
    b_morgan = L.MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    b_count = L.CountMaskBlock(d["ntgt"], d["mask"])
    b_seq = L.SeqBlock(d["emb"], d["mask"], pca_k=L.PCA_K)
    b_pid = L.PidBlock(d["cid2targets"], d["cid_order"])
    b_ccap = L.CcapBlock(b_seq, master_seed=L.SEED)
    b_m1b = L.M1bCovariateBlock(d["cov_by_cid"], d["cid_order"], include_pchembl=False, name="B_m1b")
    b_m1b_pch = L.M1bCovariateBlock(d["cov_by_cid"], d["cid_order"], include_pchembl=True, name="B_m1b_pchembl")
    b_fam = L.FamilyBlock(d["cid2families_bio"], d["cid_order"], name="B_fam")
    b_fam_sc = L.FamilyBlock(d["cid2families_sc"], d["cid_order"], name="B_fam_selfclust")
    blocks = {"B0": b_morgan, "B1": b_count, "B_seq": b_seq, "B_pid": b_pid, "C_ccap": b_ccap,
              "B_m1b": b_m1b, "B_m1b_pchembl": b_m1b_pch, "B_fam": b_fam, "B_fam_selfclust": b_fam_sc}
    for b in [b_morgan, b_count, b_seq, b_ccap, b_pid, b_m1b, b_m1b_pch, b_fam, b_fam_sc]:
        b.fit(train_idx)

    train_mask = L._mask_from_idx(train_idx, N)
    fit_scope = {}
    for k, b in blocks.items():
        la = b.leakage_assert(train_idx)  # fit rows ⊆ train (leak_rows==0), 아니면 AssertionError
        fit_rows = np.where(b._fit_rows_mask)[0]
        # fit 객체 종류
        obj = []
        if hasattr(b, "sc"):
            obj.append("StandardScaler")
        if hasattr(b, "pca"):
            obj.append("PCA")
        if hasattr(b, "vocab") and getattr(b, "vocab"):
            obj.append(f"vocab(dim={b.dim})")
        if hasattr(b, "L") and k == "C_ccap":
            obj.append("mean/cov(chol)")
        fit_scope[k] = {
            "fit_objects": obj or ["none(deterministic)"],
            "n_fit_rows": int(b._fit_rows_mask.sum()),
            "fit_rows_subset_of_train": bool(np.all(train_mask[fit_rows])) if fit_rows.size else True,
            "n_non_train_fit_rows": int((b._fit_rows_mask & ~train_mask).sum()),
            "leak_rows": la["leak_rows"],
            "dim": b.dim,
        }

    # ── B_seq PCA fit 범위(핵심): fit 모집단 = train ∩ 매핑 약물의 drug-level mean-pool 행 ──
    #    → PCA는 test-drug 표적·전체 UniProt per-target pool이 아니라 train-drug mean-pool 벡터로만 fit.
    fit_mask_seq = train_mask & b_seq.mask          # train ∩ 매핑
    assert np.array_equal(b_seq._fit_rows_mask, fit_mask_seq), "[A1] B_seq fit rows != train∩mapped"
    assert (b_seq._fit_rows_mask & ~train_mask).sum() == 0, "[A1] B_seq PCA fit이 non-train 행 참조(누수)"
    # PCA fit에 실제로 기여한 '표적' 집합(= train-mapped 약물의 embedded human 표적 union)
    embedded = _embedded_target_set()
    train_mapped_cids = [d["cid_order"][i] for i in np.where(b_seq._fit_rows_mask)[0]]
    targets_in_fit = set()
    for c in train_mapped_cids:
        targets_in_fit |= (set(d["cid2targets"].get(int(c), set())) & embedded)
    # 전체 pool(모든 약물의 embedded human 표적) 대비
    all_mapped_cids = [d["cid_order"][i] for i in np.where(b_seq.mask)[0]]
    targets_pool = set()
    for c in all_mapped_cids:
        targets_pool |= (set(d["cid2targets"].get(int(c), set())) & embedded)

    bseq = {
        "fit_population": "train ∩ 매핑 약물의 drug-level mean-pool 벡터(비매핑 zero 제외)",
        "n_fit_drug_rows": int(b_seq._fit_rows_mask.sum()),
        "pca_evr_64": float(b_seq.evr),
        "pca_fit_scope_check": "z-score(StandardScaler) + PCA-64 모두 emb[train∩mapped] 행으로만 fit",
        "representation_leakage": "none — 전체 per-target UniProt pool·test-drug 표적으로 fit하지 않음",
        "correction_applied": False,
        "correction_reason": "현 구현이 이미 outer-train-drug mean-pool 한정(전체 pool fit 아님) → 수정 불요",
        "b_seq_pca_fit_target_count_train": len(targets_in_fit),   # ★ PCA fit 대상 표적 수(train-drug 도달)
        "b_seq_target_pool_all_drugs": len(targets_pool),
        "note": ("drug_target_emb_meanpool.npy는 약물별 mean-pool(표적 임베딩의 약물수준 평균). "
                 "표적 임베딩 자체는 split-무관 서열 특징이며, PCA basis는 train-drug 벡터로만 적합 → "
                 "test-drug 표적이 공유되어도 PCA fit 모집단에 raw로 들어가지 않음."),
    }
    logln(f"[A1] B_seq PCA fit rows(train∩mapped)={bseq['n_fit_drug_rows']} EVR64={bseq['pca_evr_64']:.4f} | "
          f"fit 대상 표적수(train)={bseq['b_seq_pca_fit_target_count_train']} / 전체 pool={bseq['b_seq_target_pool_all_drugs']} "
          f"| 표현누수=none(수정 불요)")

    all_leak0 = all(v["leak_rows"] == 0 and v["n_non_train_fit_rows"] == 0 for v in fit_scope.values())
    logln(f"[A1] 전처리 fold-only fit assert PASS (전 블록 leak_rows=0, non-train fit rows=0) = {all_leak0}")

    out = {
        "task": "A1 — nested outer-train-only fit assert (fold별 재생성 원칙; 확증 하네스가 재사용하는 레시피)",
        "split_used": "seed-42 dev split (레시피 검증용; 확증 split 미생성)",
        "split_counts": {"train": int(len(train_idx)), "valid": int(len(valid_idx)), "test": int(len(test_idx))},
        "per_block_fit_scope": fit_scope,
        "all_blocks_train_only_fit": bool(all_leak0),
        "b_seq_pca": bseq,
        "fold_regeneration_principle": ("확증 outer-fold마다 StandardScaler·PCA·vocab(B_pid/B_fam)·C-CAP mean/cov·"
                                        "imputation 통계를 해당 fold train에서만 새로 생성(fit) — 본 레시피가 fold마다 재호출됨. "
                                        "seed-42 dev에서 fit-scope·누수 assert로 구조 검증."),
        "integrity": {"confirmatory_split_generated": False, "confirmatory_split_accessed": False, "network_calls": 0},
    }
    dump("A1_nested_fit_assert.json", out)
    return blocks, train_idx, valid_idx, test_idx


def _embedded_target_set():
    pi = pd.read_csv(os.path.join(TM, "protbert_index.csv"))
    return set(pi.loc[pi["emb_path"].astype(str).str.len() > 0, "uniprot"].astype(str))


# ═══════════════════════════════════════════════════════════════════════════
# A2 — split 진단 사전 동결 (결과 무참조)
# ═══════════════════════════════════════════════════════════════════════════
def a2_split_diagnostics(d):
    logln("[A2] split 진단 사전 동결 (결과 무참조 — 확증 split 미생성)")
    X = d["X"]
    cid_order = d["cid_order"]
    smiles = X["smiles_canonical"].tolist()
    # ── Bemis–Murcko scaffold group (step6 정의 동일) ──
    groups = defaultdict(list)
    for cid, smi in zip(cid_order, smiles):
        groups[_scaffold(smi)].append(int(cid))
    empty_group_size = len(groups.get("", []))
    # 비어있지 않은 scaffold group만(빈 scaffold=파싱불가/무고리 → 별도 보고)
    sizes_all = np.array([len(g) for g in groups.values()])
    nonempty_sizes = np.array([len(g) for k, g in groups.items() if k != ""])
    N = len(cid_order)

    def size_stats(sizes):
        if sizes.size == 0:
            return {}
        return {
            "n_groups": int(sizes.size),
            "median": float(np.median(sizes)),
            "p90": float(np.percentile(sizes, 90)),
            "p95": float(np.percentile(sizes, 95)),
            "p99": float(np.percentile(sizes, 99)),
            "max": int(sizes.max()),
            "max_group_frac_of_all": float(sizes.max() / N),
        }

    def n_eff(sizes):
        s = sizes.astype(float)
        return float((s.sum() ** 2) / (s ** 2).sum()) if s.sum() > 0 else 0.0

    scaffold_block = {
        "n_drugs": int(N),
        "including_empty_scaffold": {
            **size_stats(sizes_all), "N_eff": n_eff(sizes_all),
            "empty_scaffold_group_size": int(empty_group_size),
            "note": "빈 scaffold('' = 무고리/파싱불가)는 step6에서 단일 그룹으로 묶임 — 포함 통계",
        },
        "excluding_empty_scaffold": {
            **size_stats(nonempty_sizes), "N_eff": n_eff(nonempty_sizes),
            "note": "빈 scaffold 그룹 제외(실질 ring-scaffold 그룹만)",
        },
    }
    logln(f"[A2] scaffold group(빈값 포함) n={scaffold_block['including_empty_scaffold']['n_groups']} "
          f"N_eff={scaffold_block['including_empty_scaffold']['N_eff']:.1f} "
          f"max_group={scaffold_block['including_empty_scaffold']['max']}({100*scaffold_block['including_empty_scaffold']['max_group_frac_of_all']:.1f}%) "
          f"| 빈 scaffold group size={empty_group_size}")

    # ── cid → scaffold ──
    cid2sc = {}
    for sc, g in groups.items():
        for c in g:
            cid2sc[int(c)] = sc

    # ── PT별 positive-scaffold 분포 (master_Y; 라벨은 고정 입력 = 결과 아님) ──
    Ym = d["Ym"]                     # (N, PT)
    ycols = d["ycols"]
    pos_scaffold_counts = []         # PT별 distinct positive-scaffold 수
    max_concentration = []           # PT별 최대 단일 scaffold positive 집중도
    pt_pos_total = []
    for j in range(Ym.shape[1]):
        pos_rows = np.where(Ym[:, j] == 1)[0]
        pt_pos_total.append(int(len(pos_rows)))
        sc_of_pos = Counter(cid2sc[int(cid_order[i])] for i in pos_rows)
        pos_scaffold_counts.append(len(sc_of_pos))
        if len(pos_rows) > 0:
            max_concentration.append(max(sc_of_pos.values()) / len(pos_rows))
        else:
            max_concentration.append(0.0)
    psc = np.array(pos_scaffold_counts)
    mc = np.array(max_concentration)
    pt_positive_scaffold = {
        "n_pt": int(Ym.shape[1]),
        "positive_scaffold_count": {
            "median": float(np.median(psc)), "min": int(psc.min()), "max": int(psc.max()),
            "frac_pt_gt0": float((psc > 0).mean()),
            "frac_pt_ge3": float((psc >= 3).mean()),
        },
        "max_single_scaffold_positive_concentration": {
            "median": float(np.median(mc)), "p90": float(np.percentile(mc, 90)), "max": float(mc.max()),
            "note": "PT별 (최대 단일 scaffold의 양성 수)/(PT 총 양성 수) — 1.0에 가까울수록 한 scaffold에 양성 집중",
        },
        "pt_positive_total": {"median": float(np.median(pt_pos_total)), "min": int(min(pt_pos_total))},
    }
    logln(f"[A2] PT positive-scaffold: median={pt_positive_scaffold['positive_scaffold_count']['median']:.0f} "
          f"min={pt_positive_scaffold['positive_scaffold_count']['min']} "
          f"PT중 >0 scaffold 비율={100*pt_positive_scaffold['positive_scaffold_count']['frac_pt_gt0']:.1f}%")

    # ── undefined-PT AP 처리 규칙(사전 고정) ──
    undefined_ap_rule = {
        "rule": ("bootstrap/OOF 평가에서 특정 draw·fold의 test-positive가 0인 PT는 그 draw·fold의 macro 평균에서 제외"
                 "(average_precision_score 미정의). 제외율(draw별 제외 PT 비율)을 확증 단계에서 보고."),
        "smoke_metric_consistency": "ladder_confirmatory.macro_ap()도 fold test 양성>0 PT만 평균(동일 규칙).",
        "frozen_before_oof": True,
    }

    # ── 확증(seed 201) fold-level 진단 — 의도적 유보(무결성) ──
    deferred = {
        "status": "DEFERRED — 확증 split(seed 201) 미생성(무결성). fold별 PT 양성 0/1/2/≥3 분포·"
                  "fold 간 label density·train/test 표적 Jaccard·rare-PT 제약 충족 여부는 docs/36 실행 시 split 생성 후 산출.",
        "reason": "본 하드닝은 확증 OOF 조회 전 = 확증 split 생성/조회 금지(docs/38 §8).",
    }

    out = {
        "task": "A2 — split 진단 사전 동결(결과 무참조; 확증 split 미생성)",
        "scaffold_definition": "RDKit MurckoScaffold.MurckoScaffoldSmiles(includeChirality=False) — step6과 동일",
        "scaffold_groups": scaffold_block,
        "pt_positive_scaffold": pt_positive_scaffold,
        "undefined_ap_rule": undefined_ap_rule,
        "confirmatory_fold_level_diagnostics": deferred,
        "integrity": {"confirmatory_split_generated": False, "labels_are_fixed_input_not_result": True},
    }
    dump("A2_split_diagnostics.json", out)
    # 요약 표(md)
    inc = scaffold_block["including_empty_scaffold"]
    exc = scaffold_block["excluding_empty_scaffold"]
    md = [
        "# A2 — Split 진단 요약 (결과 무참조; 확증 split 미생성)\n",
        f"- 분자 수 N = {N}\n",
        "## Scaffold group (Bemis–Murcko, step6 정의)\n",
        "| 지표 | 빈 scaffold 포함 | 빈 scaffold 제외 |",
        "|---|---|---|",
        f"| group 수 | {inc['n_groups']} | {exc['n_groups']} |",
        f"| size median | {inc['median']:.0f} | {exc['median']:.0f} |",
        f"| size p90/p95/p99 | {inc['p90']:.0f}/{inc['p95']:.0f}/{inc['p99']:.0f} | {exc['p90']:.0f}/{exc['p95']:.0f}/{exc['p99']:.0f} |",
        f"| size max | {inc['max']} ({100*inc['max_group_frac_of_all']:.1f}%) | {exc['max']} ({100*exc['max_group_frac_of_all']:.1f}%) |",
        f"| **N_eff** | {inc['N_eff']:.1f} | {exc['N_eff']:.1f} |",
        f"\n- 빈 scaffold('' 무고리/파싱불가) 그룹 크기 = {empty_group_size}\n",
        "## PT positive-scaffold 분포 (370 PT)\n",
        f"- distinct positive-scaffold 수: median {np.median(psc):.0f}, min {int(psc.min())}, max {int(psc.max())}\n",
        f"- PT 중 positive-scaffold>0 비율: {100*(psc>0).mean():.1f}% · ≥3 비율: {100*(psc>=3).mean():.1f}%\n",
        f"- 최대 단일 scaffold 양성 집중도: median {np.median(mc):.3f}, max {mc.max():.3f}\n",
        "## undefined-PT AP 규칙 (사전 고정)\n",
        f"- {undefined_ap_rule['rule']}\n",
        "## 확증 fold-level 진단\n",
        f"- {deferred['status']}\n",
    ]
    with open(os.path.join(AUDIT, "A2_split_diagnostics_summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    logln(f"[산출] experiments/audits/A2_split_diagnostics_summary.md 저장")
    return out


# ═══════════════════════════════════════════════════════════════════════════
# A3 — RF max_features 감사 (문서화만)
# ═══════════════════════════════════════════════════════════════════════════
def a3_rf_maxfeatures(smoke_dims):
    logln("[A3] RF max_features 감사(설정 변경 금지·문서화)")
    rf = RandomForestClassifier(**L.RF_KW)
    default_mf = rf.max_features   # RF_KW에 미지정 → sklearn 기본값
    def resolved(nfeat):
        # 'sqrt' → max(1, int(sqrt(nfeat)))
        if default_mf == "sqrt":
            return max(1, int(math.sqrt(nfeat)))
        if default_mf == "log2":
            return max(1, int(math.log2(nfeat)))
        if isinstance(default_mf, float):
            return max(1, int(default_mf * nfeat))
        if isinstance(default_mf, int):
            return default_mf
        return nfeat  # None → all
    rows = []
    for mid in ["M1b", "M2b", "P-ID", "P-FAM", "C-CAP", "M0", "M1", "M2"]:
        D = smoke_dims.get(mid)
        if D is None:
            continue
        m = resolved(D)
        rows.append((mid, D, m, m / D))
    # M1b→M2b 대비(핵심)
    d_m1b = smoke_dims.get("M1b"); d_m2b = smoke_dims.get("M2b")
    m_m1b = resolved(d_m1b); m_m2b = resolved(d_m2b)
    md = []
    md.append("# A3 — RF max_features 감사 (설정 변경 금지 · 문서화)\n")
    md.append(f"- 동결 RF 하이퍼: `{L.RF_KW}` — **max_features 미지정 → sklearn 기본값 = `{default_mf}`**.")
    md.append("- 즉 각 트리 노드 split마다 후보 = `max(1, int(sqrt(D)))` 개 feature를 무작위 표집(D=전체 feature 차원).\n")
    md.append("## 모델별 max_features 해석 (seed-42 dev side_dim 기준)\n")
    md.append("| 모델 | 전체 D | max_features(sqrt) | m/D (임의 feature가 후보일 확률≈) |")
    md.append("|---|---|---|---|")
    for mid, D, m, r in rows:
        md.append(f"| {mid} | {D} | {m} | {r:.4f} |")
    md.append("")
    md.append("## primary contrast M1b → M2b (B_seq 64차원 추가) 영향\n")
    md.append(f"- M1b: D={d_m1b}, max_features={m_m1b}, 임의 feature 후보확률 ≈ {m_m1b/d_m1b:.4f}")
    md.append(f"- M2b: D={d_m2b}, max_features={m_m2b}, 임의 feature 후보확률 ≈ {m_m2b/d_m2b:.4f}")
    md.append(f"- **Morgan/covariate feature가 특정 split의 후보로 뽑힐 확률**은 M1b {m_m1b/d_m1b:.4f} → "
              f"M2b {m_m2b/d_m2b:.4f} 로 소폭 변한다(D 증가 → 1/√D 감소). 절대 변화폭 {abs(m_m1b/d_m1b - m_m2b/d_m2b):.5f}.")
    md.append(f"- 후보 개수 자체는 {m_m1b} → {m_m2b} (√D 증가).")
    md.append("")
    md.append("## 해석(문서화 — 설정 불변)\n")
    md.append("- 따라서 **M2b − M1b** 는 '서열 블록(B_seq) 정보' + 'RF feature-subsampling regime의 미세 변화(√D·1/√D)'의 합이다.")
    md.append("- 이는 순수 정보량 인과식별이 아니라 **전체 RF pipeline 증분**임을 명시한다(docs/37 §4 Bucket B 정합).")
    md.append("- **max_features 설정은 pilot 레시피 그대로 유지**(재튜닝 0). 본 감사는 문서화 목적이며 어떤 값도 변경하지 않는다.\n")
    p = os.path.join(AUDIT, "A3_rf_maxfeatures_note.md")
    with open(p, "w") as f:
        f.write("\n".join(md) + "\n")
    logln(f"[A3] RF max_features 기본값='{default_mf}' | M1b {m_m1b}/{d_m1b} → M2b {m_m2b}/{d_m2b} (설정 불변)")
    logln(f"[산출] {os.path.relpath(p, ROOT)} 저장")
    return {"default_max_features": default_mf,
            "per_model": [{"model": mid, "D": D, "max_features": m, "ratio": r} for mid, D, m, r in rows]}


# ═══════════════════════════════════════════════════════════════════════════
# A4 — B_seq truncation/pooling/isoform 감사표
# ═══════════════════════════════════════════════════════════════════════════
def a4_bseq_truncation():
    logln("[A4] B_seq truncation/pooling/isoform 감사")
    pi = pd.read_csv(os.path.join(TM, "protbert_index.csv"))
    pi = pi[pi["emb_path"].astype(str).str.len() > 0].copy()
    pi["seq_len"] = pi["seq_len"].astype(int)
    pi["truncated"] = pi["truncated"].astype(int)
    # human single-protein 표적(06_human) — B_seq human primary
    human_uni = set(pd.read_csv(os.path.join(TM, "06_targets_human.csv"))["uniprot"].astype(str))
    pi["in_human_primary"] = pi["uniprot"].astype(str).isin(human_uni).astype(int)
    # family join(생물학 family; human 표적)
    fb = pd.read_csv(os.path.join(TM, "10_target_family_biological.csv"))
    uni2fam = fb.drop_duplicates("uniprot").set_index("uniprot")[["family_id", "family_name"]]
    pi = pi.merge(uni2fam, left_on="uniprot", right_index=True, how="left")

    MAX_RES = 510  # ProtBERT [CLS]+510잔기+[SEP] = 512 토큰(target_pipeline.MAX_RES)
    n_emb = len(pi)
    n_trunc = int(pi["truncated"].sum())
    hp = pi[pi["in_human_primary"] == 1]
    n_hp = len(hp); n_hp_trunc = int(hp["truncated"].sum())

    # family별 절단율(human primary)
    fam_rows = []
    for fam, g in hp.dropna(subset=["family_name"]).groupby("family_name"):
        fam_rows.append({"family_name": fam, "n_targets": int(len(g)),
                         "n_truncated": int(g["truncated"].sum()),
                         "trunc_rate": float(g["truncated"].mean())})
    fam_rows.sort(key=lambda x: -x["n_targets"])

    # isoform 중복 감사: '-' suffix(예: P12345-2) + base accession 중복
    accs = pi["uniprot"].astype(str)
    isoform_suffixed = sorted(accs[accs.str.contains("-")].tolist())
    base = accs.str.split("-").str[0]
    dup_base = sorted([b for b, n in Counter(base).items() if n > 1])

    # ── mean-pool special-token/padding 제외 코드 검증(정적 assert) ──
    tp_src = open(os.path.join(HERE, "target_pipeline.py")).read()
    pooling_checks = {
        "cls_excluded (mask[:, 0] = 0)": "mask[:, 0] = 0" in tp_src,
        "sep_excluded (mask[i, L-1] = 0)": "mask[i, int(L) - 1] = 0" in tp_src,
        "padding_excluded (attention_mask)": 'enc["attention_mask"]' in tp_src,
        "truncation_maxlen_512 (max_length=MAX_LEN)": "truncation=True, max_length=MAX_LEN" in tp_src,
        "mean_over_residues (summed / cnt)": "summed / cnt" in tp_src,
    }
    pooling_ok = all(pooling_checks.values())
    assert pooling_ok, f"[A4] mean-pool special-token/padding 제외 코드 검증 실패: {pooling_checks}"

    # 감사표 CSV(per-target)
    cols = ["uniprot", "seq_len", "truncated", "in_human_primary", "family_id", "family_name"]
    pi_out = pi[cols].sort_values(["in_human_primary", "seq_len"], ascending=[False, False])
    csv_path = os.path.join(AUDIT, "A4_bseq_truncation_audit.csv")
    pi_out.to_csv(csv_path, index=False)
    logln(f"[산출] {os.path.relpath(csv_path, ROOT)} 저장 ({len(pi_out)} targets)")

    summary = {
        "task": "A4 — B_seq truncation/pooling/isoform 감사",
        "max_residues": MAX_RES,
        "all_embedded_targets": {"n": n_emb, "n_truncated": n_trunc, "trunc_rate": n_trunc / n_emb,
                                 "prereg_49pct_match": abs(n_trunc / n_emb - 0.49) < 0.01},
        "human_primary_targets": {"n": n_hp, "n_truncated": n_hp_trunc,
                                  "trunc_rate": (n_hp_trunc / n_hp) if n_hp else 0.0},
        "seq_len_stats_embedded": {"median": float(pi["seq_len"].median()),
                                   "p95": float(pi["seq_len"].quantile(0.95)),
                                   "max": int(pi["seq_len"].max())},
        "family_truncation_human_primary": fam_rows,
        "isoform_audit": {
            "isoform_suffixed_accessions": isoform_suffixed,
            "n_isoform_suffixed": len(isoform_suffixed),
            "duplicate_base_accessions": dup_base,
            "n_duplicate_base": len(dup_base),
            "note": "isoform suffix(-N) 및 동일 base accession 중복 없음이면 canonical accession 단일 매핑 확인."},
        "mean_pool_special_token_exclusion": {
            "code_source": "v3_Multimodal/src/target_pipeline.py step3.flush()",
            "checks": pooling_checks, "all_pass": pooling_ok,
            "detail": "잔기 mean-pool = Σ(last_hidden * mask)/Σmask, mask는 CLS(pos0)·SEP(마지막 유효토큰)·padding(attention_mask=0) 제외."},
        "seen_unseen_split_truncation": {
            "status": "DEFERRED — seen/unseen별 절단율은 확증 split(seed 201) 생성 후 산출(무결성상 미생성).",
        },
        "integrity": {"network_calls": 0, "reused_frozen_protbert_index": True},
    }
    dump("A4_bseq_truncation_audit_summary.json", summary)
    logln(f"[A4] 절단(embedded) {n_trunc}/{n_emb}={100*n_trunc/n_emb:.1f}% (사전등록 49% 정합={summary['all_embedded_targets']['prereg_49pct_match']}) "
          f"| human primary {n_hp_trunc}/{n_hp}={100*n_hp_trunc/max(n_hp,1):.1f}% | pooling 제외 검증 PASS "
          f"| isoform suffix {len(isoform_suffixed)} · dup base {len(dup_base)}")
    return summary


# ═══════════════════════════════════════════════════════════════════════════
# A5 — target count 정의 일관성
# ═══════════════════════════════════════════════════════════════════════════
def a5_target_count(d):
    logln("[A5] target count 정의 일관성")
    cid_order = d["cid_order"]
    ntgt = np.asarray(d["ntgt"]).astype(int)     # drug_n_targets_meanpool.npy (B1 표적수)
    mask = np.asarray(d["mask"]).astype(int)     # drug_target_mask_meanpool.npy (표적-present)
    N = len(cid_order)

    # 독립 재계산: 약물별 unique human single-protein accession(임베딩 보유) 수
    embedded = _embedded_target_set()
    cid2t = d["cid2targets"]
    recomputed = np.array([len(set(cid2t.get(int(c), set())) & embedded) for c in cid_order], dtype=int)
    mismatch = int((recomputed != ntgt).sum())

    n_unmapped = int((mask == 0).sum())
    # missing(unmapped) 규칙: n_targets=0 & mask=0 (present-mask). 'missing indicator' = 1 - mask.
    unmapped_dnt0 = bool((ntgt[mask == 0] == 0).all())
    mask_iff_present = bool(np.array_equal((ntgt >= 1), (mask == 1)))

    # B1 log1p 값 확인: unmapped → log1p(0)=0 (표준화 전)
    log1p0_zero = bool(math.isclose(math.log1p(0), 0.0))

    # ── M1(log 표적수) vs M1b(evidence_count) 중복성 note ──
    mdf = pd.read_csv(os.path.join(TM, "08_m1b_covariates.csv"))
    ev_by_cid = {int(r["cid"]): float(r["evidence_count"]) for r in mdf.to_dict("records")}
    log_ntgt = np.log1p(ntgt.astype(float))
    log_ev = np.log1p(np.array([ev_by_cid.get(int(c), 0.0) for c in cid_order]))
    # 두 매핑 존재 약물에서 Spearman(간이) — 순위상관
    both = (ntgt > 0) & np.array([int(c) in ev_by_cid for c in cid_order])
    from scipy.stats import spearmanr
    rho, pval = spearmanr(log_ntgt[both], log_ev[both]) if both.sum() > 2 else (float("nan"), float("nan"))

    assert mask_iff_present, "[A5] mask=1 ⟺ n_targets≥1 불일치"
    assert n_unmapped == 245, f"[A5] unmapped {n_unmapped} != 245"
    assert unmapped_dnt0, "[A5] unmapped 약물의 n_targets != 0"

    out = {
        "task": "A5 — target count 정의 일관성 (B1 표적수·mask·M1↔M1b 중복성)",
        "b1_target_count_definition": "drug_n_targets_meanpool.npy = 약물별 unique human single-protein UniProt accession(임베딩 보유) 수(중복 제거)",
        "independent_recompute_mismatch": mismatch,
        "recompute_note": "cid2targets(06_targets_human) ∩ embedded(protbert_index) 로 재계산 → drug_n_targets_meanpool.npy와 비교",
        "n_total": N,
        "n_unmapped": n_unmapped,
        "unmapped_rule": {
            "n_targets_zero": unmapped_dnt0,
            "log1p_zero_equals_0": log1p0_zero,
            "mask_convention": "B1 mask = present-indicator(1=표적有). 245 unmapped → mask=0, n_targets=0, log1p(0)=0.",
            "missing_indicator_is_complement": "‘missing’ 지시자는 (1 − mask). docs/38 §7의 'mask=1' 표현은 missing-지시자 관점이며, "
                                               "구현 저장값은 present-mask(unmapped=0). 두 표기 모두 동일 정보(상보).",
            "mask_iff_present": mask_iff_present,
        },
        "m1_vs_m1b_redundancy": {
            "note": ("B1 log1p(표적수)와 B_m1b log1p(evidence_count)는 둘 다 연구량/폴리파마콜로지 규모의 대리변수라 부분 중복 가능. "
                     "M1b(=M1+study-intensity)에서 이미 함께 통제되며, primary contrast는 M2b−M1b(서열 순증분)라 중복이 처치효과를 부풀리지 않음."),
            "spearman_log_ntgt_vs_log_evidence": {"rho": float(rho), "p": float(pval),
                                                  "n_pairs": int(both.sum()),
                                                  "scope": "양쪽 매핑 존재 약물"},
        },
        "integrity": {"network_calls": 0, "reused_frozen_npy": True},
    }
    dump("A5_target_count_check.json", out)
    logln(f"[A5] B1 표적수 재계산 mismatch={mismatch} | unmapped={n_unmapped}(n_tgt=0·mask=0) | "
          f"mask⟺present={mask_iff_present} | Spearman(log표적수,log evidence)={rho:.3f}(n={int(both.sum())})")
    return out


# ═══════════════════════════════════════════════════════════════════════════
def main():
    logln("=" * 78)
    logln("[하드닝] A1~A5 (docs/38 §3~§7) — A0 재동결 상태 대상. 확증 OOF 미조회·확증 split 미생성.")
    d = L.load_frozen()
    # A1 (블록 fit 검증) — 반환 blocks/idx 재사용
    blocks, train_idx, valid_idx, test_idx = a1_nested_fit_assert(d)
    # A2
    a2_split_diagnostics(d)
    # A3 — smoke side_dim (seed-42 dev, 결과 아님) 로 max_features 문서화
    smoke_dims = {}
    Ytr = d["Ym"][train_idx]
    for mid in ["M0", "M1", "M2", "M1b", "M2b", "P-ID", "P-FAM", "C-CAP"]:
        X = L.assemble_matrix(mid, blocks, train_idx[:4])
        smoke_dims[mid] = int(X.shape[1])
    a3_rf_maxfeatures(smoke_dims)
    # A4
    a4_bseq_truncation()
    # A5
    a5_target_count(d)

    logln("[하드닝] A1~A5 완료. 무결성: 확증 split 미생성·OOF 미조회, 네트워크 0.")
    logln("=" * 78)
    # run.log append
    with open(os.path.join(AUDIT, "run.log"), "a") as f:
        f.write("\n".join(_LOGLINES) + "\n")
    print(f"[run.log] {os.path.relpath(os.path.join(AUDIT, 'run.log'), ROOT)} append")


if __name__ == "__main__":
    main()
