#!/usr/bin/env python3
"""train_ladder.py — v3 멀티모달 모델 사다리 M0~M4 + ablation (마일스톤 3).

설계(임의 변경 금지, docs/21):
  약물 인코더 = GraphDTA GIN 브랜치(valid 선택된 arch) 재사용, 학습레시피 = A_wd 승계
  (focal γ2 + sqrt pos_weight + weight_decay 1e-4, Adam lr 1e-3, batch 32, ep 200, patience 30).
  동일 split(scaffold_split.json) · 시드 {42,1,2,3,4} · valid macro PR-AUC로만 early stopping/선택.
  지표: macro/micro PR-AUC 주(평가 PT 301, micro는 370 ravel) + ROC/F1 보조.

★ 누수 방지(리뷰어 1순위): 단백질 z-score scaler와 PCA-64는 **train split의 매핑 약물에서만 fit**.
   valid/test에는 transform만. unmapped(zero) 약물은 결측 placeholder라 fit에서 제외하고,
   transform 후 mask로 **다시 0**으로 되돌린다(표준화 → 마스크 재적용). 코드에서 assert로 검증.

사다리:
  M0 구조만 | M1 +n_targets 스칼라(교란 통제군) | M2 +ProtBERT PCA-64(concat, RQ1 주모델)
  M3 +affinity 통계(top-k pchembl 평균/최대) | M4 +게이트 융합(단일 집계벡터→cross-attn 대신 gated)

ablation(M2 기준): raw-1024(z만) / 청크 mean-pool 절단 / 평균·top1 집계 / 전체 organism.

산출: v3_Multimodal/results/ladder/ (config×seed metrics, 요약표, 통계, seed42 예측 npz),
      docs/22_v3_ladder_report.md, experiments/runs/v3_ladder/.
실행: PYTORCH_ENABLE_MPS_FALLBACK=1 python -u v3_Multimodal/src/train_ladder.py \
        2>&1 | tee v3_Multimodal/results/ladder/run.log
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import sys
import json
import platform
import traceback
from collections import defaultdict

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy.stats import wilcoxon, ttest_rel, rankdata, t as tdist
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from torch_geometric.loader import DataLoader

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "v2_GNN", "src"))     # v2 모듈 재사용
sys.path.insert(0, HERE)

from data import load_config, build_graphs                  # noqa: E402
from graph_features import ATOM_FDIM                         # noqa: E402
from train import (set_seed, get_device, compute_pos_weight, # noqa: E402
                   FocalLoss, predict_proba, macro_pr_auc)
from evaluate import per_pt_metrics, aggregate              # noqa: E402
from drug_branch import GINDrugEncoder, GATGCNDrugEncoder   # noqa: E402

PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "v3_Multimodal", "results", "ladder")
RUNDIR = os.path.join(ROOT, "experiments", "runs", "v3_ladder")
os.makedirs(OUT, exist_ok=True)
os.makedirs(RUNDIR, exist_ok=True)

SEEDS = [42, 1, 2, 3, 4]
THR = 0.5
ARCH = "gin"          # GraphDTA valid 선택(graphdta_baseline/_best.json = graphdta_gin)
EMBED_DIM = 128
PCA_K = 64
# A_wd 레시피(아키텍처/레시피 고정 — 변수는 '모달'뿐)
EPOCHS, PATIENCE, BATCH, LR, WD, GAMMA, DROPOUT = 200, 30, 32, 1e-3, 1e-4, 2.0, 0.2

RANDOM_BASELINE = 0.053   # docs 명세: random baseline macro·micro (병기, 재계산 금지)
RF_DEFAULT = 0.191        # 승계 베이스라인(재계산·변조 금지)
RF_TUNED = 0.182
GNN_A_WD = 0.166
GRAPHDTA = 0.140

# 승계 산출물(재학습 없음)
ROB = os.path.join(ROOT, "v2_GNN", "results_improve", "robustness")          # gnn(A_wd)/rf(default)
FAIR = os.path.join(ROOT, "v1_RF", "results_fairtune")                       # tuned RF
GDTA = os.path.join(ROOT, "v3_Multimodal", "results", "graphdta_baseline")   # GraphDTA


def log(m):
    print(m, flush=True)


def free_mem(device):
    import gc
    gc.collect()
    try:
        if str(device) == "mps":
            torch.mps.empty_cache()
        elif str(device) == "cuda":
            torch.cuda.empty_cache()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 피처 빌드 — train-only fit (누수 방지)
# ---------------------------------------------------------------------------
def cid_order_and_split(cfg):
    order = pd.read_parquet(os.path.join(PROC, "master_X.parquet")).sort_values("cid")["cid"].astype(int).tolist()
    split = json.load(open(os.path.join(PROC, "scaffold_split.json")))
    split_of = np.array([split[str(c)] for c in order])
    return order, split_of


def build_side(config, order, split_of):
    """config에 따른 side-feature 행렬 (N, side_dim). ★모든 fit은 train split에서만.

    config keys: emb(str|None), mask(str), pca(int|0), ntargets(bool), affinity(bool)
    반환: (side[N,side_dim] float32, side_dim, meta)
    """
    N = len(order)
    is_train = split_of == "train"
    parts, meta = [], {}

    # (1) 단백질 임베딩 z-score(+PCA) — train 매핑에서만 fit, 이후 unmapped 재-0
    if config.get("emb"):
        raw = np.load(os.path.join(PROC, config["emb"])).astype(np.float64)          # (N,1024)
        m = np.load(os.path.join(PROC, config["mask"])).astype(bool)                  # (N,)
        fit_rows = is_train & m               # ★ train ∩ 매핑(zero 결측 제외 = 여전히 train-only)
        assert fit_rows.sum() >= (config["pca"] or 1), f"fit rows {fit_rows.sum()} 부족"
        scaler = StandardScaler().fit(raw[fit_rows])
        Xs = scaler.transform(raw)
        if config["pca"]:
            pca = PCA(n_components=config["pca"], svd_solver="full", random_state=42).fit(Xs[fit_rows])
            Xp = pca.transform(Xs).astype(np.float32)
            meta["pca_evr"] = float(pca.explained_variance_ratio_.sum())
        else:
            Xp = Xs.astype(np.float32)
        Xp[~m] = 0.0                          # ★ 표준화→마스크 재적용: unmapped은 정확히 0
        assert np.abs(Xp[~m]).sum() == 0.0, "unmapped 재-0 실패(누수/결측처리 오류)"
        meta["n_fit"] = int(fit_rows.sum()); meta["n_mapped"] = int(m.sum())
        parts.append(Xp)

    # (2) n_targets 스칼라(M1 통제군) — 0은 '표적 없음' 실측값이라 전체 train으로 표준화
    if config.get("ntargets"):
        nt = np.load(os.path.join(PROC, "drug_n_targets.npy")).astype(np.float64)[:, None]
        sc = StandardScaler().fit(nt[is_train])
        parts.append(sc.transform(nt).astype(np.float32))

    # (3) affinity 통계(top-k 실측 pchembl 평균/최대, M3) — 실측 보유 train에서 fit, 미보유 재-0
    if config.get("affinity"):
        aff = np.load(os.path.join(PROC, "drug_affinity_stats.npy")).astype(np.float64)   # (N,2)
        present = np.load(os.path.join(PROC, "drug_affinity_present.npy")).astype(bool)
        fit_rows = is_train & present
        sc = StandardScaler().fit(aff[fit_rows])
        A = sc.transform(aff).astype(np.float32)
        A[~present] = 0.0
        parts.append(A)

    if not parts:
        return np.zeros((N, 0), dtype=np.float32), 0, meta
    side = np.hstack(parts).astype(np.float32)
    return side, side.shape[1], meta


def attach_side(graphs, side, cid2idx, side_dim):
    """각 그래프에 d.side(shape [1,side_dim]) 부착. side_dim==0이면 제거."""
    for split in graphs:
        for d in graphs[split]:
            if side_dim > 0:
                d.side = torch.from_numpy(side[cid2idx[d.cid]]).float().view(1, side_dim)
            elif hasattr(d, "side"):
                del d.side


# ---------------------------------------------------------------------------
# 모델 — GraphDTA GIN 약물 브랜치 + side(concat) / gated 융합
# ---------------------------------------------------------------------------
class LadderNet(nn.Module):
    def __init__(self, in_dim, n_out, arch=ARCH, embed_dim=EMBED_DIM, dropout=DROPOUT,
                 side_dim=0, fusion="concat"):
        super().__init__()
        if arch == "gin":
            self.drug = GINDrugEncoder(in_dim, embed_dim=embed_dim, dropout=dropout)
        elif arch == "gatgcn":
            self.drug = GATGCNDrugEncoder(in_dim, embed_dim=embed_dim, dropout=dropout)
        else:
            raise ValueError(arch)
        self.side_dim = side_dim
        self.fusion = fusion
        if fusion == "gated" and side_dim > 0:
            # 게이트 융합: 단백질을 embed_dim으로 사영 후 약물과 게이트 가중합.
            # (표적 임베딩이 약물당 단일 집계벡터라 토큰 cross-attention이 자명 → gated로 구현; 한계 보고)
            self.p_proj = nn.Linear(side_dim, embed_dim)
            self.gate = nn.Linear(embed_dim * 2, embed_dim)
            head_in = embed_dim
        else:
            head_in = embed_dim + side_dim
        self.head = nn.Sequential(
            nn.Linear(head_in, embed_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(embed_dim, n_out),
        )

    def forward(self, data):
        d = self.drug(data.x, data.edge_index, data.batch)          # [B, embed_dim]
        if self.side_dim > 0:
            s = data.side.view(d.size(0), self.side_dim)
            if self.fusion == "gated":
                p = F.relu(self.p_proj(s))
                g = torch.sigmoid(self.gate(torch.cat([d, p], dim=1)))
                d = g * d + (1 - g) * p
            else:
                d = torch.cat([d, s], dim=1)
        return self.head(d)


def train_variant(data, device, side_dim, fusion, seed):
    """A_wd 레시피로 LadderNet 학습. valid macro PR-AUC early stopping → best로 test 예측."""
    n_out = len(data["ycols"])
    set_seed(seed)
    tr = DataLoader(data["graphs"]["train"], batch_size=BATCH, shuffle=True)
    va = DataLoader(data["graphs"]["valid"], batch_size=BATCH)
    te = DataLoader(data["graphs"]["test"], batch_size=BATCH)

    model = LadderNet(ATOM_FDIM, n_out, side_dim=side_dim, fusion=fusion).to(device)
    # side 배치 정합 방어검증(첫 배치)
    if side_dim > 0:
        b0 = next(iter(va)).to(device)
        assert b0.side.view(b0.num_graphs, side_dim).shape == (b0.num_graphs, side_dim), "side 배치 정합 실패"
    pw = torch.sqrt(compute_pos_weight(data["graphs"]["train"], n_out)).to(device)   # sqrt pos_weight
    criterion = FocalLoss(gamma=GAMMA, pos_weight=pw)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WD)

    best_v, best_state, best_ep, wait = -1.0, None, 0, 0
    for ep in range(1, EPOCHS + 1):
        model.train(); tot = 0.0
        for batch in tr:
            batch = batch.to(device)
            opt.zero_grad()
            loss = criterion(model(batch), batch.y.view(-1, n_out))
            loss.backward(); opt.step()
            tot += float(loss) * batch.num_graphs
        Pva, Yva = predict_proba(model, va, device, n_out)
        vmac = macro_pr_auc(Yva, Pva)
        if vmac > best_v:
            best_v, best_ep = vmac, ep
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
        if ep % 40 == 0 or ep == 1:
            log(f"      ep {ep:3d} loss {tot/len(data['graphs']['train']):.4f} validMacro {vmac:.4f} best {best_v:.4f}@{best_ep}")
        if wait >= PATIENCE:
            log(f"      early stop @ep{ep} (best {best_v:.4f}@{best_ep})")
            break
    model.load_state_dict(best_state)
    Pte, Yte = predict_proba(model, te, device, n_out)
    return {"valid": best_v, "best_ep": best_ep,
            "P_test": Pte.astype(np.float32), "Yte": Yte.astype(np.int8)}


# ---------------------------------------------------------------------------
# 통계 헬퍼
# ---------------------------------------------------------------------------
def rank_biserial(diff):
    d = diff[diff != 0]
    if len(d) == 0:
        return float("nan")
    r = rankdata(np.abs(d))
    return float((r[d > 0].sum() - r[d < 0].sum()) / r.sum())


def cohens_dz(diff):
    sd = diff.std(ddof=1)
    return float(diff.mean() / sd) if sd > 0 else float("nan")


def seed_paired(a, b, label):
    a, b = np.asarray(a, float), np.asarray(b, float); d = a - b; n = len(d)
    se = d.std(ddof=1) / np.sqrt(n); tc = float(tdist.ppf(0.975, n - 1))
    _, tp = ttest_rel(a, b)
    try:
        _, wp = wilcoxon(a, b); wp = float(wp)
    except ValueError:
        wp = float("nan")
    return {"comparison": label, "n_seed": n, "mean_a": float(a.mean()), "mean_b": float(b.mean()),
            "mean_diff(a-b)": float(d.mean()), "ci95_lo": float(d.mean() - tc * se),
            "ci95_hi": float(d.mean() + tc * se),
            "ci_crosses_0": bool((d.mean() - tc * se) < 0 < (d.mean() + tc * se)),
            "paired_t_p": float(tp), "wilcoxon_p": wp, "cohens_dz": cohens_dz(d)}


# ---------------------------------------------------------------------------
# 실행 구성 (사다리 + ablation)
# ---------------------------------------------------------------------------
LADDER = [
    {"id": "M0", "emb": None,                       "mask": None,                     "pca": 0,     "ntargets": False, "affinity": False, "fusion": "concat"},
    {"id": "M1", "emb": None,                       "mask": None,                     "pca": 0,     "ntargets": True,  "affinity": False, "fusion": "concat"},
    {"id": "M2", "emb": "drug_target_emb.npy",      "mask": "drug_target_mask.npy",   "pca": PCA_K, "ntargets": False, "affinity": False, "fusion": "concat"},
    {"id": "M3", "emb": "drug_target_emb.npy",      "mask": "drug_target_mask.npy",   "pca": PCA_K, "ntargets": False, "affinity": True,  "fusion": "concat"},
    {"id": "M4", "emb": "drug_target_emb.npy",      "mask": "drug_target_mask.npy",   "pca": PCA_K, "ntargets": False, "affinity": False, "fusion": "gated"},
]
ABLATION = [
    {"id": "A_raw1024", "emb": "drug_target_emb.npy",       "mask": "drug_target_mask.npy",     "pca": 0,     "ntargets": False, "affinity": False, "fusion": "concat", "note": "차원: raw-1024(z만) vs PCA-64(M2)"},
    {"id": "A_chunk",   "emb": "drug_target_emb_chunk.npy", "mask": "drug_target_mask.npy",     "pca": PCA_K, "ntargets": False, "affinity": False, "fusion": "concat", "note": "절단: 청크 mean-pool vs 앞510(M2)"},
    {"id": "A_mean",    "emb": "drug_target_emb_mean.npy",  "mask": "drug_target_mask.npy",     "pca": PCA_K, "ntargets": False, "affinity": False, "fusion": "concat", "note": "집계: 평균 pooling vs top-k가중(M2)"},
    {"id": "A_top1",    "emb": "drug_target_emb_top1.npy",  "mask": "drug_target_mask.npy",     "pca": PCA_K, "ntargets": False, "affinity": False, "fusion": "concat", "note": "집계: top-1 vs top-k가중(M2)"},
    {"id": "A_allorg",  "emb": "drug_target_emb_all.npy",   "mask": "drug_target_mask_all.npy", "pca": PCA_K, "ntargets": False, "affinity": False, "fusion": "concat", "note": "organism: 전체 vs human(M2)"},
]


def run_config(cfg, data, device, cid2idx, order, split_of, config, seeds=SEEDS):
    """config를 seeds에 대해 학습(idempotent). 각 seed metrics CSV + seed42 예측/perpt 저장."""
    cid = config["id"]
    side, side_dim, meta = build_side(config, order, split_of)
    attach_side(data["graphs"], side, cid2idx, side_dim)
    log(f"  === {cid} (side_dim={side_dim}, fusion={config['fusion']}) {meta} ===")
    ycols = data["ycols"]
    rows = []
    for seed in seeds:
        cpath = os.path.join(OUT, f"{cid}_seed{seed}.csv")
        if os.path.exists(cpath):
            rows.append(pd.read_csv(cpath).iloc[0].to_dict())
            log(f"    [seed {seed}] 재사용 {cid}_seed{seed}.csv")
            continue
        r = train_variant(data, device, side_dim, config["fusion"], seed)
        df = per_pt_metrics(r["Yte"].astype(int), r["P_test"], ycols, THR)
        agg = aggregate(r["Yte"].astype(int), r["P_test"], df, THR)
        row = {"model": cid, "seed": seed, "macro_pr": agg["macro_pr_auc"], "micro_pr": agg["micro_pr_auc"],
               "macro_roc": agg["macro_roc_auc"], "macro_f1": agg["macro_f1@0.5"],
               "hamming": agg["hamming_accuracy"], "valid_macro": r["valid"], "best_ep": r["best_ep"],
               "n_pt_eval": agg["n_pt_evaluated"], "side_dim": side_dim}
        pd.DataFrame([row]).to_csv(cpath, index=False)
        rows.append(row)
        log(f"    [seed {seed}] {cid} macroPR {agg['macro_pr_auc']:.4f} microPR {agg['micro_pr_auc']:.4f} "
            f"validMacro {r['valid']:.4f} evalPT {agg['n_pt_evaluated']} → 저장")
        if seed == 42:
            df[["meddra_pt", "n_pos_test", "pr_auc"]].to_csv(os.path.join(OUT, f"{cid}_perpt_seed42.csv"), index=False)
            test_cids = np.array([d.cid for d in data["graphs"]["test"]], dtype=int)  # 예측 행 순서와 정합
            np.savez_compressed(os.path.join(OUT, f"{cid}_pred_seed42.npz"),
                                P=r["P_test"], Y=r["Yte"], ycols=np.array(ycols), cids=test_cids)
        free_mem(device)
    return pd.DataFrame(rows), side_dim, meta


# ---------------------------------------------------------------------------
# 부트스트랩 (seed42 예측 기반, 분자·스캐폴드 층)
# ---------------------------------------------------------------------------
def _fast_ap(Y, P, cols):
    """열별 average precision을 numpy로 벡터화(부트스트랩 고속화). sklearn AP 공식과 동치(동점은 정렬순).
    반환: (ap[m], npos[m])."""
    Yc = Y[:, cols].astype(np.float64)
    order = np.argsort(-P[:, cols], axis=0)
    Ys = np.take_along_axis(Yc, order, axis=0)
    tp = np.cumsum(Ys, axis=0)
    denom = np.arange(1, Ys.shape[0] + 1)[:, None]        # 1-indexed rank = tp+fp
    precision = tp / denom
    npos = Ys.sum(0)
    ap = np.where(npos > 0, (precision * Ys).sum(0) / np.maximum(npos, 1.0), np.nan)
    return ap, npos


def _macro_micro(Y, P, eval_idx):
    """macro=eval PT(양성>0) AP 평균, micro=370 전체 ravel AP (v2 프로토콜과 동일 정신)."""
    ap, npos = _fast_ap(Y, P, np.asarray(eval_idx))
    macro = float(np.nanmean(ap[npos > 0])) if (npos > 0).any() else float("nan")
    yr, pr = Y.ravel().astype(np.float64), P.ravel()
    o = np.argsort(-pr); ys = yr[o]
    tp = np.cumsum(ys); denom = np.arange(1, len(ys) + 1); npq = ys.sum()
    micro = float(((tp / denom) * ys).sum() / npq) if npq > 0 else float("nan")
    return macro, micro


def bootstrap_diff(a_npz, b_npz, order, split_of, n_boot=2000, seed=42):
    """seed42 예측으로 (A-B) macro/micro diff의 분자/스캐폴드 부트스트랩 95% CI."""
    za = np.load(os.path.join(OUT, a_npz)); zb = np.load(os.path.join(OUT, b_npz))
    Pa, Pb, Y = za["P"], zb["P"], za["Y"].astype(int)
    assert (za["Y"] == zb["Y"]).all(), "A/B test 라벨 불일치"
    n, K = Y.shape
    eval_idx = [j for j in range(K) if Y[:, j].sum() > 0]
    rng = np.random.default_rng(seed)

    # test 분자 scaffold(Murcko generic) — 예측 행 순서(npz cids)와 정확 정합
    scaf = _test_scaffolds(list(za["cids"].astype(int)))   # 길이 n, Y행과 동일 순서

    def ci(func):
        ds = []
        for _ in range(n_boot):
            idx = func(rng)
            ma, mia = _macro_micro(Y[idx], Pa[idx], eval_idx)
            mb, mib = _macro_micro(Y[idx], Pb[idx], eval_idx)
            ds.append((ma - mb, mia - mib))
        ds = np.array(ds)
        lo, hi = np.percentile(ds, [2.5, 97.5], axis=0)
        return {"macro_ci": (float(lo[0]), float(hi[0])), "micro_ci": (float(lo[1]), float(hi[1]))}

    mol = ci(lambda r: r.integers(0, n, n))
    out = {"molecule": mol, "n_test": n}
    if scaf is not None and len(scaf) == n:
        groups = defaultdict(list)
        for i, s in enumerate(scaf):
            groups[s].append(i)
        gkeys = list(groups.keys())

        def scaf_sample(r):
            chosen = r.integers(0, len(gkeys), len(gkeys))
            idx = []
            for g in chosen:
                idx.extend(groups[gkeys[g]])
            return np.array(idx)
        out["scaffold"] = ci(scaf_sample)
        out["n_scaffold"] = len(gkeys)
    return out


def _test_scaffolds(test_cids):
    """test cid → Murcko generic scaffold SMILES. RDKit 실패 시 None."""
    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
    except Exception:
        return None
    X = pd.read_parquet(os.path.join(PROC, "master_X.parquet"))
    smi = dict(zip(X["cid"].astype(int), X["smiles_canonical"]))
    scaf = []
    for c in test_cids:
        try:
            m = Chem.MolFromSmiles(smi[c])
            s = MurckoScaffold.MurckoScaffoldSmiles(mol=MurckoScaffold.GetScaffoldForMol(m))
            scaf.append(s or "NONE")
        except Exception:
            scaf.append("NONE")
    return scaf


# ---------------------------------------------------------------------------
# 집계 + 리포트
# ---------------------------------------------------------------------------
def load_baseline_seeds():
    """승계 5시드 배열(재계산 없음): default_RF, tuned_RF, GNN(A_wd), GraphDTA."""
    rob = pd.concat([pd.read_csv(os.path.join(ROB, f"seed_{s}.csv")) for s in SEEDS]).sort_values("seed")
    fair = pd.concat([pd.read_csv(os.path.join(FAIR, f"seed_{s}.csv")) for s in SEEDS]).sort_values("seed")
    gd = pd.concat([pd.read_csv(os.path.join(GDTA, f"seed_{s}.csv")) for s in SEEDS]).sort_values("seed")
    return {
        "default_RF": (rob["rf_macro"].values, rob["rf_micro"].values),
        "tuned_RF":   (fair["tuned_rf_macro"].values, fair["tuned_rf_micro"].values),
        "GNN_A_wd":   (rob["gnn_macro"].values, rob["gnn_micro"].values),
        "GraphDTA":   (gd["gdta_macro"].values, gd["gdta_micro"].values),
        "_seeds":     rob["seed"].values,
    }


def analyze(ladder_metrics, abl_metrics, metas, order, split_of, device):
    # 사다리 시드 배열
    L = {cid: ladder_metrics[cid].sort_values("seed") for cid in ladder_metrics}

    def arr(cid, col):
        return L[cid][col].values.astype(float)

    base = load_baseline_seeds()

    # ── 비교표 (5시드 mean±std) ──
    def ms(v):
        return float(np.mean(v)), float(np.std(v, ddof=1))
    table_rows = []
    for cid in ["M0", "M1", "M2", "M3", "M4"]:
        if cid not in L:
            continue
        mm = ms(arr(cid, "macro_pr")); mi = ms(arr(cid, "micro_pr"))
        table_rows.append({"model": cid, "macro_mean": mm[0], "macro_std": mm[1],
                           "micro_mean": mi[0], "micro_std": mi[1]})
    for name in ["GraphDTA", "GNN_A_wd", "tuned_RF", "default_RF"]:
        mm = ms(base[name][0]); mi = ms(base[name][1])
        table_rows.append({"model": name, "macro_mean": mm[0], "macro_std": mm[1],
                           "micro_mean": mi[0], "micro_std": mi[1]})
    comp = pd.DataFrame(table_rows)
    comp.to_csv(os.path.join(OUT, "comparison_table.csv"), index=False)

    # ── 사다리 인접 대응검정 + vs 최고 RF ──
    tests = []
    pairs = [("M1", "M0"), ("M2", "M1"), ("M2", "M0"), ("M3", "M2"), ("M4", "M2")]
    for a, b in pairs:
        if a in L and b in L:
            tests.append(seed_paired(arr(a, "macro_pr"), arr(b, "macro_pr"), f"MACRO: {a} vs {b}"))
            tests.append(seed_paired(arr(a, "micro_pr"), arr(b, "micro_pr"), f"MICRO: {a} vs {b}"))
    # vs 승계 RF(표적정보 없는 최고): 실질 성패 = RF 0.191 초과 여부
    for cid in ["M2", "M3", "M4"]:
        if cid in L:
            tests.append(seed_paired(arr(cid, "macro_pr"), base["default_RF"][0], f"MACRO: {cid} vs default_RF"))
            tests.append(seed_paired(arr(cid, "macro_pr"), base["tuned_RF"][0], f"MACRO: {cid} vs tuned_RF"))
    stat = pd.DataFrame(tests)
    stat.to_csv(os.path.join(OUT, "seed_paired_tests.csv"), index=False)

    # ── ablation 표 (M2 기준, 5시드 mean±std + M2 대비 seed 검정) ──
    abl_rows = []
    m2_macro = arr("M2", "macro_pr")
    abl_rows.append({"ablation": "M2 (주: PCA-64·앞510·top-k가중·human·concat)",
                     "macro_mean": ms(m2_macro)[0], "macro_std": ms(m2_macro)[1],
                     "micro_mean": ms(arr('M2', 'micro_pr'))[0], "vs_M2_macro_diff": 0.0,
                     "vs_M2_wilcoxon_p": np.nan})
    for cid, A in abl_metrics.items():
        A = A.sort_values("seed")
        am = A["macro_pr"].values.astype(float)
        sp = seed_paired(am, m2_macro, f"{cid} vs M2")
        abl_rows.append({"ablation": f"{cid}: {next(x['note'] for x in ABLATION if x['id']==cid)}",
                         "macro_mean": ms(am)[0], "macro_std": ms(am)[1],
                         "micro_mean": ms(A['micro_pr'].values.astype(float))[0],
                         "vs_M2_macro_diff": sp["mean_diff(a-b)"], "vs_M2_wilcoxon_p": sp["wilcoxon_p"]})
    abl = pd.DataFrame(abl_rows)
    os.makedirs(os.path.join(ROOT, "v3_Multimodal", "results", "ablation"), exist_ok=True)
    abl.to_csv(os.path.join(ROOT, "v3_Multimodal", "results", "ablation", "ablation_table.csv"), index=False)

    # ── 부트스트랩(seed42): M2 vs M1, M2 vs M0 ──
    boot = {}
    try:
        boot["M2_vs_M1"] = bootstrap_diff("M2_pred_seed42.npz", "M1_pred_seed42.npz", order, split_of)
        boot["M2_vs_M0"] = bootstrap_diff("M2_pred_seed42.npz", "M0_pred_seed42.npz", order, split_of)
        json.dump(boot, open(os.path.join(OUT, "bootstrap_ci.json"), "w"), indent=2)
    except Exception as e:
        log(f"[warn] 부트스트랩 스킵: {e}")

    write_report(comp, stat, abl, boot, metas, base, device)
    return comp, stat, abl, boot


def _verdict(stat, comp):
    """해석 규칙(사전등록) 판정: M1>M0 & M2≈M1 → study bias; M2>M1 유의 → 서열 고유기여."""
    S = {r["comparison"]: r for _, r in stat.iterrows()}
    C = {r["model"]: r for _, r in comp.iterrows()}
    m1m0 = S.get("MACRO: M1 vs M0"); m2m1 = S.get("MACRO: M2 vs M1"); m2m0 = S.get("MACRO: M2 vs M0")
    m1_gain = (m1m0 is not None) and (m1m0["mean_diff(a-b)"] > 0) and (not m1m0["ci_crosses_0"])
    m2_over_m1 = (m2m1 is not None) and (m2m1["mean_diff(a-b)"] > 0) and (not m2m1["ci_crosses_0"])
    m2_over_m0 = (m2m0 is not None) and (m2m0["mean_diff(a-b)"] > 0) and (not m2m0["ci_crosses_0"])
    if m2_over_m1:
        v = "RQ1 **양성**: M2가 M1을 유의하게 상회 → ProtBERT 서열의 고유 기여로 판정."
    elif m2_over_m0 and m1_gain:
        v = "이득의 정체 = **연구 편향(인기도 대리)**: M1>M0 유의이나 M2≈M1 → 서열은 study bias 이상 기여 못함."
    elif m2_over_m0 and not m1_gain:
        v = "M2>M0이나 M1은 무이득 → 서열 concat이 이득을 냈으나 통제군(M1) 대비 우위는 미확정(추가검토)."
    else:
        v = "표적 축 **전체 무기여**: M2≈M0≈M1 → 표적 정보(개수·서열 모두)가 구조-only를 넘지 못함."
    rf = C.get("default_RF"); m2 = C.get("M2")
    rf_line = ""
    if rf is not None and m2 is not None:
        beat = m2["macro_mean"] > rf["macro_mean"]
        rf_line = (f"실질 성패(표적정보 없는 최고 RF {rf['macro_mean']:.3f} 초과): "
                   f"M2 {m2['macro_mean']:.3f} → **{'초과' if beat else '미달'}**.")
    return v, rf_line


def write_report(comp, stat, abl, boot, metas, base, device):
    v, rf_line = _verdict(stat, comp)
    S = {r["comparison"]: r for _, r in stat.iterrows()}

    def fmt_row(r):
        return f"| {r['model']} | {r['macro_mean']:.3f} ± {r['macro_std']:.3f} | {r['micro_mean']:.3f} ± {r['micro_std']:.3f} |"

    def fmt_test(key):
        if key not in S:
            return f"| {key} | — |"
        r = S[key]
        return (f"| {key.split(':')[1].strip()} | Δ{r['mean_diff(a-b)']:+.3f} "
                f"95%CI[{r['ci95_lo']:+.3f},{r['ci95_hi']:+.3f}] (0포함={r['ci_crosses_0']}) "
                f"Wilcoxon p={r['wilcoxon_p']:.3f} dz={r['cohens_dz']:+.2f} |")

    m2_meta = metas.get("M2", {})
    L = []
    A = L.append
    A("# 22. v3 멀티모달 모델 사다리 M0~M4 리포트 (마일스톤 3)\n")
    A("> 생성: `v3_Multimodal/src/train_ladder.py` (SEED {42,1,2,3,4}, 동일 scaffold split, A_wd 레시피, arch=GIN 고정).")
    A(f"> 약물 인코더=GraphDTA GIN 브랜치 재사용, 변수=**모달뿐**. device={device}. "
      f"단백질 z-score+PCA-64는 **train 매핑 약물에서만 fit**(누수 방지), unmapped은 transform 후 재-0.")
    A(f"> PCA-64 설명분산 {m2_meta.get('pca_evr', float('nan')):.3f} (train-fit {m2_meta.get('n_fit','?')} 매핑, "
      f"전체 매핑 {m2_meta.get('n_mapped','?')}/1092).\n")

    A("## 1. 완료 보고 (핵심)\n")
    C = {r["model"]: r for _, r in comp.iterrows()}
    for cid in ["M0", "M1", "M2", "M3", "M4"]:
        if cid in C:
            A(f"- **{cid}** macro PR-AUC {C[cid]['macro_mean']:.3f} ± {C[cid]['macro_std']:.3f} "
              f"(micro {C[cid]['micro_mean']:.3f}).")
    A(f"- **해석 규칙 판정**: {v}")
    A(f"- {rf_line}")
    if "M2_vs_M1" in boot:
        b = boot["M2_vs_M1"]
        A(f"- 부트스트랩(seed42, M2−M1) 분자층 macro 95%CI[{b['molecule']['macro_ci'][0]:+.3f},{b['molecule']['macro_ci'][1]:+.3f}]"
          + (f", 스캐폴드층 [{b['scaffold']['macro_ci'][0]:+.3f},{b['scaffold']['macro_ci'][1]:+.3f}]" if "scaffold" in b else "") + ".")
    A("")

    A("## 2. 사다리 비교표 (test, 5시드 mean ± std)\n")
    A("| 모델 | macro PR-AUC | micro PR-AUC |")
    A("|---|---|---|")
    for cid in ["M0", "M1", "M2", "M3", "M4"]:
        if cid in C:
            A(fmt_row(C[cid]))
    A("| GraphDTA(승계) | " + f"{C.get('GraphDTA',{}).get('macro_mean',float('nan')):.3f} ± {C.get('GraphDTA',{}).get('macro_std',float('nan')):.3f}"
      + f" | {C.get('GraphDTA',{}).get('micro_mean',float('nan')):.3f} ± {C.get('GraphDTA',{}).get('micro_std',float('nan')):.3f} |")
    for name, disp in [("GNN_A_wd", "튜닝GNN(A_wd)"), ("tuned_RF", "튜닝RF"), ("default_RF", "디폴트RF")]:
        r = C.get(name, {})
        A(f"| {disp}(승계) | {r.get('macro_mean',float('nan')):.3f} ± {r.get('macro_std',float('nan')):.3f} | "
          f"{r.get('micro_mean',float('nan')):.3f} ± {r.get('micro_std',float('nan')):.3f} |")
    A(f"| random baseline | {RANDOM_BASELINE:.3f} | {RANDOM_BASELINE:.3f} |")
    A("\n> 승계 베이스라인(디폴트RF·튜닝RF·GNN·GraphDTA)은 v1/v2/graphdta 산출물 5시드 그대로 인용(재학습 없음).\n")

    A("## 3. 대응검정 (시드 단위 5회, macro) — 사전등록 해석 규칙\n")
    A("| 비교 | 검정 |")
    A("|---|---|")
    for a, b in [("M1", "M0"), ("M2", "M1"), ("M2", "M0"), ("M3", "M2"), ("M4", "M2")]:
        A(fmt_test(f"MACRO: {a} vs {b}"))
    for cid in ["M2", "M3", "M4"]:
        A(fmt_test(f"MACRO: {cid} vs default_RF"))
    A("\n해석 규칙(결과 후 불변): M1>M0 & M2≈M1 → 이득=연구편향; M2>M1 유의 → 서열 고유기여; "
      "M2≈M0≈M1 → 표적축 무기여.\n")

    A("## 4. Ablation (M2 기준)\n")
    A("| 변형 | macro PR-AUC | micro | M2 대비 Δmacro | Wilcoxon p |")
    A("|---|---|---|---|---|")
    for _, r in abl.iterrows():
        dd = "—" if pd.isna(r["vs_M2_macro_diff"]) else f"{r['vs_M2_macro_diff']:+.3f}"
        pp = "—" if pd.isna(r["vs_M2_wilcoxon_p"]) else f"{r['vs_M2_wilcoxon_p']:.3f}"
        A(f"| {r['ablation']} | {r['macro_mean']:.3f} ± {r['macro_std']:.3f} | {r['micro_mean']:.3f} | {dd} | {pp} |")
    A("\n> ablation 항목: (1)단백질 제거=M2→M0, (2)교란 통제=M2→M1[3절], (3)차원 PCA-64 vs raw-1024, "
      "(4)절단 앞510 vs 청크 mean-pool, (5)집계 top-k가중 vs 평균 vs top1, (6)organism human vs 전체.\n")

    A("## 5. 한계 (정직 보고)\n")
    A("- **study bias**: n_targets↔n_ADR 양의 상관(Spearman rho=0.191) → M1 통제군 필수. M2가 M1을 넘지 못하면 서열 무용이 아니라 '인기도 이상 기여 없음'으로만 해석.")
    A(f"- **ProtBERT 절단 49%**(940 서열>510잔기): 청크 mean-pool ablation으로 아티팩트 여부를 데이터로 점검(4절).")
    A("- **임베딩 유효차원 ~18–30**(PC1 48.6%, 약물쌍 코사인 평균 0.913): 약물 간 단백질 신호 차이가 작음 → concat 시 표준화 없이는 단백질 축 무시 위험(그래서 z-score 필수).")
    A("- **ChEMBL 단독 하한**(BindingDB 404 미반영), affinity median 집계, top-k=5. 단일 scaffold split(repeated split은 후속).")
    A("- **M4=게이트 융합**: 표적 임베딩이 약물당 단일 집계벡터라 완전 cross-attention이 자명해져 gated로 구현(top-k 개별표적 토큰 attention은 후속).")
    A("- 구조·라벨·split 불변, 승계 베이스라인 재학습·변조 없음. MPS 비결정성으로 절대수치 ±소폭 변동 가능(결론=순위·유의성).")

    doc = os.path.join(ROOT, "docs", "22_v3_ladder_report.md")
    with open(doc, "w") as f:
        f.write("\n".join(L) + "\n")
    log(f"[리포트] {os.path.relpath(doc, ROOT)} 저장")


# ---------------------------------------------------------------------------
def main():
    cfg = load_config()
    device = get_device(cfg)
    log(f"[ladder] device={device} | arch={ARCH} | seeds={SEEDS} | A_wd(focal γ{GAMMA}+sqrt pw+wd {WD})")
    data = build_graphs(cfg)
    order, split_of = cid_order_and_split(cfg)
    cid2idx = {c: i for i, c in enumerate(order)}
    # 그래프 test 순서 ↔ order test 정합(부트스트랩 scaffold 정합용) 확인
    test_cids_graph = [d.cid for d in data["graphs"]["test"]]
    test_cids_order = [c for c, s in zip(order, split_of) if s == "test"]
    if test_cids_graph != test_cids_order:
        log(f"[주의] test 그래프순서≠order순서 → 부트스트랩 scaffold는 그래프순서 기준으로 재정렬 필요"
            f"(graph {len(test_cids_graph)} / order {len(test_cids_order)})")

    # 재현 메타 저장
    json.dump({"seeds": SEEDS, "arch": ARCH, "recipe": {"epochs": EPOCHS, "patience": PATIENCE,
              "batch": BATCH, "lr": LR, "wd": WD, "gamma": GAMMA, "dropout": DROPOUT, "pca_k": PCA_K},
              "device": str(device), "torch": torch.__version__, "python": platform.python_version(),
              "numpy": np.__version__, "pandas": pd.__version__},
              open(os.path.join(RUNDIR, "config.json"), "w"), indent=2)

    # ── 사다리 M0~M4 ──
    ladder_metrics, metas = {}, {}
    for config in LADDER:
        m, sd, meta = run_config(cfg, data, device, cid2idx, order, split_of, config)
        ladder_metrics[config["id"]] = m
        metas[config["id"]] = meta

    # ── ablation (M2 기준) ──
    abl_metrics = {}
    for config in ABLATION:
        # 파일 없으면 스킵(예: 청크 임베딩 미완)
        if config["emb"] and not os.path.exists(os.path.join(PROC, config["emb"])):
            log(f"[ablation] {config['id']} 스킵 — {config['emb']} 없음")
            continue
        m, sd, meta = run_config(cfg, data, device, cid2idx, order, split_of, config)
        abl_metrics[config["id"]] = m

    analyze(ladder_metrics, abl_metrics, metas, order, split_of, str(device))
    log("[완료] v3 사다리 M0~M4 + ablation 산출 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print("\n===== [ladder 중단] 예외 =====", flush=True)
        print(tb, flush=True)
        print(tb, file=sys.stderr, flush=True)
        sys.exit(1)
