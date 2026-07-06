#!/usr/bin/env python3
"""STEP 0 — 진단 (v2_GNN 개선 사이클). 튜닝 전 필수.

명세 docs/10_v2_gnn_improve_spec.md §1.
- GIN(기존 best 설정)을 early stopping 없이 길게(diagnose epochs) 재학습하며
  epoch별 train/valid macro·micro PR-AUC + train loss 기록 → 학습곡선.
- 과적합(train≫valid) vs 과소적합(train도 낮음) 판정.
- PT 양성빈도 3분위(저/중/고, 전체 데이터셋 기준)별 GIN vs v1 RF PR-AUC 비교.
- 출력: v2_GNN/results_improve/{learning_curve.png, diagnose.md, freq_tertile.csv}

공정비교 불변: 데이터·split·test·301규칙 고정. 기존 results/는 건드리지 않음.
실행: PYTORCH_ENABLE_MPS_FALLBACK=1 python v2_GNN/src/diagnose.py
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from torch_geometric.loader import DataLoader
from sklearn.metrics import average_precision_score

from data import ROOT, load_config, build_graphs
from graph_features import ATOM_FDIM
from models import build_model
from train import set_seed, get_device, compute_pos_weight, predict_proba

OUT = os.path.join(ROOT, "v2_GNN", "results_improve")
os.makedirs(OUT, exist_ok=True)
DIAG_EPOCHS = 250          # early stop 없이 길게 → 수렴 전 중단 여부 직접 확인


def macro_micro(Y, P):
    aps = [average_precision_score(Y[:, j], P[:, j])
           for j in range(Y.shape[1]) if Y[:, j].sum() > 0]
    macro = float(np.mean(aps)) if aps else float("nan")
    micro = float(average_precision_score(Y.ravel(), P.ravel()))
    return macro, micro


def main():
    cfg = load_config()
    set_seed(cfg["seed"])
    device = get_device(cfg)
    print(f"[diag] device={device} seed={cfg['seed']} | GIN 재학습 {DIAG_EPOCHS}ep (no early stop)")
    data = build_graphs(cfg)
    ycols = data["ycols"]; n_out = len(ycols)

    tr = DataLoader(data["graphs"]["train"], batch_size=cfg["train"]["batch_size"], shuffle=True)
    tr_eval = DataLoader(data["graphs"]["train"], batch_size=cfg["train"]["batch_size"])
    va = DataLoader(data["graphs"]["valid"], batch_size=cfg["train"]["batch_size"])

    model = build_model(cfg, ATOM_FDIM, n_out, conv_type="gin", pool="mean").to(device)
    pw = compute_pos_weight(data["graphs"]["train"], n_out).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pw)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["train"]["lr"],
                           weight_decay=cfg["train"]["weight_decay"])

    hist = []
    best_v, best_ep = -1, 0
    for ep in range(1, DIAG_EPOCHS + 1):
        model.train(); tot = 0.0
        for batch in tr:
            batch = batch.to(device)
            opt.zero_grad()
            loss = criterion(model(batch), batch.y.view(-1, n_out))
            loss.backward(); opt.step()
            tot += loss.item() * batch.num_graphs
        Pva, Yva = predict_proba(model, va, device, n_out)
        vmac, vmic = macro_micro(Yva, Pva)
        row = {"epoch": ep, "train_loss": tot / len(data["graphs"]["train"]),
               "valid_macro": vmac, "valid_micro": vmic}
        if ep % 5 == 0 or ep == 1:               # train PR-AUC 는 5ep 마다(비용)
            Ptr, Ytr = predict_proba(model, tr_eval, device, n_out)
            tmac, tmic = macro_micro(Ytr, Ptr)
            row["train_macro"], row["train_micro"] = tmac, tmic
        if vmac > best_v:
            best_v, best_ep = vmac, ep
        hist.append(row)
        if ep % 10 == 0 or ep == 1:
            print(f"[diag] ep {ep:3d} loss {row['train_loss']:.4f} "
                  f"validMacro {vmac:.4f} validMicro {vmic:.4f} | best {best_v:.4f}@{best_ep}")

    H = pd.DataFrame(hist)
    H.to_csv(os.path.join(OUT, "learning_curve.csv"), index=False)

    # ── 학습곡선 png ──
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    tr_pts = H.dropna(subset=["train_macro"])
    ax[0].plot(H.epoch, H.valid_macro, label="valid")
    ax[0].plot(tr_pts.epoch, tr_pts.train_macro, label="train", ls="--")
    ax[0].axvline(best_ep, c="r", ls=":", lw=1, label=f"valid best @ {best_ep}")
    ax[0].axhline(0.188, c="g", ls=":", lw=1, label="v1 RF macro 0.188")
    ax[0].set(title="macro PR-AUC", xlabel="epoch"); ax[0].legend(fontsize=8)
    ax[1].plot(H.epoch, H.valid_micro, label="valid")
    ax[1].plot(tr_pts.epoch, tr_pts.train_micro, label="train", ls="--")
    ax[1].axhline(0.320, c="g", ls=":", lw=1, label="v1 RF micro 0.320")
    ax[1].set(title="micro PR-AUC", xlabel="epoch"); ax[1].legend(fontsize=8)
    ax[2].plot(H.epoch, H.train_loss); ax[2].set(title="train loss (BCE)", xlabel="epoch")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "learning_curve.png"), dpi=130); plt.close(fig)

    # ── 빈도 3분위별 GIN vs RF ──
    Yall = pd.read_parquet(os.path.join(ROOT, "data/processed/master_Y.parquet"))
    pos_total = {c: int(Yall[c].sum()) for c in ycols}            # 전체 데이터셋 PT 양성수
    v1 = pd.read_csv(os.path.join(ROOT, "v1_RF/results/metrics_per_pt.csv"))
    v2 = pd.read_csv(os.path.join(ROOT, "v2_GNN/results/metrics_per_pt.csv"))  # 기존 GIN(null)
    m = v2[["meddra_pt", "n_pos_test", "pr_auc"]].rename(columns={"pr_auc": "gin"}).merge(
        v1[["meddra_pt", "RandomForest_pr_auc"]].rename(columns={"RandomForest_pr_auc": "rf"}),
        on="meddra_pt", how="inner").dropna(subset=["gin", "rf"])
    m["pos_total"] = m["meddra_pt"].map(pos_total)
    m["tertile"] = pd.qcut(m["pos_total"], 3, labels=["저빈도", "중빈도", "고빈도"])
    g = m.groupby("tertile", observed=True).agg(
        n_pt=("meddra_pt", "count"),
        pos_total_min=("pos_total", "min"), pos_total_max=("pos_total", "max"),
        gin_mean_pr=("gin", "mean"), rf_mean_pr=("rf", "mean")).reset_index()
    g["diff(gin-rf)"] = g["gin_mean_pr"] - g["rf_mean_pr"]
    g.to_csv(os.path.join(OUT, "freq_tertile.csv"), index=False)

    # ── 판정 텍스트 ──
    final = H.iloc[-1]
    last_tr = tr_pts.iloc[-1]
    gap = float(last_tr["train_macro"] - final["valid_macro"])
    if last_tr["train_macro"] < 0.30 and final["valid_macro"] < 0.25:
        verdict = "과소적합(underfit) 우세 — train·valid 모두 낮음. 표현력/최적화 부족 신호."
    elif gap > 0.20:
        verdict = "과적합(overfit) 우세 — train≫valid. 정규화/구조 보강 필요."
    else:
        verdict = "경계적 — 뚜렷한 과적합/과소적합 아님. 최적화·수렴 여지 점검."
    still_rising = bool(H.valid_macro.iloc[-1] >= H.valid_macro.iloc[-20:-1].max() - 1e-4)

    md = [
        "# v2_GNN 개선 — STEP 0 진단",
        "",
        f"> GIN(기존 best 설정: hidden128×3, BCE+pos_weight, lr1e-3) early stop 없이 {DIAG_EPOCHS}ep 재학습. "
        f"데이터·split·test·301규칙 고정(공정비교 불변). seed=42, device={device}.",
        "",
        "## 1. 학습곡선 요약",
        "",
        f"- valid macro PR-AUC 최고 **{best_v:.4f} @ epoch {best_ep}** (기존 1사이클 best_epoch=111과 비교).",
        f"- 최종(epoch {int(final['epoch'])}): train macro {last_tr['train_macro']:.4f} / valid macro {final['valid_macro']:.4f} "
        f"(gap {gap:+.4f}), valid micro {final['valid_micro']:.4f}.",
        f"- v1 RF 기준선: macro 0.188 / micro 0.320.",
        f"- 후반 20ep 내 valid 신기록 갱신 여부(수렴 전 중단 의심): **{'예(아직 상승 여지)' if still_rising else '아니오(정체/수렴)'}**.",
        "",
        f"## 2. 과적합/과소적합 판정\n\n**{verdict}**",
        "",
        "## 3. PT 양성빈도 3분위별 GIN(기존) vs v1 RF (test PR-AUC 평균)",
        "",
        "| 구간 | PT수 | 양성수범위 | GIN 평균 PR | RF 평균 PR | 차이(GIN-RF) |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in g.iterrows():
        md.append(f"| {r['tertile']} | {int(r['n_pt'])} | {int(r['pos_total_min'])}–{int(r['pos_total_max'])} | "
                  f"{r['gin_mean_pr']:.3f} | {r['rf_mean_pr']:.3f} | {r['diff(gin-rf)']:+.3f} |")
    md += ["",
           "> 해석 가이드: 고빈도 구간에서 GIN-RF 차이가 크게 음수면 '고빈도 PT 학습 실패(미최적화)' 가설 지지.",
           "",
           "## 산출물",
           "- learning_curve.png / learning_curve.csv",
           "- freq_tertile.csv",
           ]
    with open(os.path.join(OUT, "diagnose.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"[저장] results_improve/diagnose.md, learning_curve.png, freq_tertile.csv")
    print("판정:", verdict, "| 수렴여지:", still_rising)


if __name__ == "__main__":
    main()
