#!/usr/bin/env python3
"""STEP F — 통계적 유의성 (v2_GNN). ★RQ2 판정.

명세 docs/09_v2_gnn_spec.md §3 STEP F.
- PT 단위 대응표본 검정: **valid-선택된 단일 GNN**의 PT별 PR-AUC vs v1 RF의 PT별 PR-AUC.
  (★ test 성능으로 모델을 고르지 않음 — train.py 에서 valid macro PR-AUC 로 선택된 모델만 사용)
- Wilcoxon 부호순위 검정(주) + 대응 t-검정(보조), p<0.05. 301개 공통 PT.
- 입력: v2 metrics_per_pt.csv(valid-최적 GNN), v1_RF/results/metrics_per_pt.csv(RandomForest_pr_auc).
- 출력: significance_v1_vs_v2.csv (검정통계량·p값·중앙값/평균 차이·n).
"""
import os
import json
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, ttest_rel

from data import ROOT, load_config

RESULTS = os.path.join(ROOT, "v2_GNN", "results")


def main():
    cfg = load_config()
    alpha = cfg["stats"]["alpha"]
    with open(os.path.join(RESULTS, "_train_meta_v2.json")) as f:
        best = json.load(f)["best_by_valid"]

    v2 = pd.read_csv(os.path.join(RESULTS, "metrics_per_pt.csv"))          # valid-최적 GNN
    v1 = pd.read_csv(os.path.join(ROOT, cfg["data"]["v1_per_pt"]))         # v1 RF/XGB per-PT
    v1col = "RandomForest_pr_auc"

    m = v2[["meddra_pt", "n_pos_test", "pr_auc"]].merge(
        v1[["meddra_pt", v1col]], on="meddra_pt", how="inner")
    m = m.dropna(subset=["pr_auc", v1col])                                 # 양쪽 정의된 301 PT
    g = m["pr_auc"].values          # v2 GNN
    r = m[v1col].values             # v1 RF
    n = len(m)
    diff = g - r

    w_stat, w_p = wilcoxon(g, r)                  # 주 검정
    t_stat, t_p = ttest_rel(g, r)                 # 보조 검정
    n_win = int((diff > 0).sum())

    out = pd.DataFrame([{
        "comparison": f"v2 GNN-{best} vs v1 RandomForest (PT별 PR-AUC, 대응표본)",
        "n_pt": n,
        "v2_mean_pr_auc": float(g.mean()),
        "v1_mean_pr_auc": float(r.mean()),
        "mean_diff(v2-v1)": float(diff.mean()),
        "median_diff(v2-v1)": float(np.median(diff)),
        "n_pt_v2_higher": n_win,
        "wilcoxon_stat": float(w_stat),
        "wilcoxon_p": float(w_p),
        "paired_t_stat": float(t_stat),
        "paired_t_p": float(t_p),
        "alpha": alpha,
        "significant(wilcoxon)": bool(w_p < alpha),
        "direction": "v2>v1" if diff.mean() > 0 else "v2<=v1",
    }])
    out.to_csv(os.path.join(RESULTS, "significance_v1_vs_v2.csv"), index=False)

    verdict = "유의" if w_p < alpha else "비유의"
    sign = "향상" if diff.mean() > 0 else "저하/동등"
    print(f"[stats] RQ2: GNN-{best} vs v1 RF | n={n} PT | "
          f"mean PR-AUC {g.mean():.3f} vs {r.mean():.3f} (Δ{diff.mean():+.3f}, {n_win}/{n} PT 우위)")
    print(f"        Wilcoxon p={w_p:.2e} ({verdict}, α={alpha}) | paired t p={t_p:.2e} | 방향 {sign}")
    print(f"[저장] significance_v1_vs_v2.csv")


if __name__ == "__main__":
    main()
