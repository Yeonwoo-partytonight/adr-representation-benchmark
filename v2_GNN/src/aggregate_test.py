#!/usr/bin/env python3
"""STEP1 보강 — seed-단위 집계 검정 (재학습 없음, 기존 seed_<n>.csv 재사용).

robustness/seed_*.csv 의 5개 seed macro/micro PR-AUC 쌍(GNN A_wd vs v1 RF)에 대해
paired test(Wilcoxon signed-rank + paired t)와 평균차 95% CI 를 산출한다.
산출: robustness/aggregate_test.csv

주의: n=5 Wilcoxon signed-rank 는 최소 양측 p=0.0625(2/2^5)라 α=0.05 도달 불가(검정력 한계).
이 한계를 결과에 함께 보고한다.
"""
import os
import glob
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, ttest_rel, t as tdist

from data import ROOT

OUT = os.path.join(ROOT, "v2_GNN", "results_improve", "robustness")


def paired_row(metric, g, r):
    """g, r: seed별 GNN/RF 값 배열(동일 seed 순서). GNN-RF 평균차·CI·검정."""
    d = g - r
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    se = sd / np.sqrt(n)
    tcrit = float(tdist.ppf(0.975, n - 1))
    ci_lo, ci_hi = mean - tcrit * se, mean + tcrit * se
    # paired t
    t_stat, t_p = ttest_rel(g, r)
    # Wilcoxon signed-rank (양측). 동률 전부면 예외 → NaN 처리
    try:
        w_stat, w_p = wilcoxon(g, r)
        w_stat, w_p = float(w_stat), float(w_p)
    except ValueError:
        w_stat, w_p = float("nan"), float("nan")
    return {
        "metric": metric, "n_seed": n,
        "gnn_mean": float(g.mean()), "gnn_std": float(g.std(ddof=1)),
        "rf_mean": float(r.mean()), "rf_std": float(r.std(ddof=1)),
        "mean_diff(gnn-rf)": mean, "diff_std": sd,
        "ci95_lo": float(ci_lo), "ci95_hi": float(ci_hi),
        "ci_crosses_0": bool(ci_lo < 0 < ci_hi),
        "paired_t_stat": float(t_stat), "paired_t_p": float(t_p),
        "wilcoxon_stat": w_stat, "wilcoxon_p": w_p,
        "wilcoxon_min_possible_p": 2.0 / (2 ** n),  # n=5 → 0.0625 (검정력 한계 표시)
    }


def main():
    files = sorted(glob.glob(os.path.join(OUT, "seed_*.csv")))
    if not files:
        raise SystemExit(f"seed_*.csv 없음: {OUT} — robustness 먼저 완주할 것.")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).sort_values("seed").reset_index(drop=True)
    print(f"[집계검정] {len(df)} seed: {df['seed'].tolist()}")

    rows = [
        paired_row("macro_pr_auc", df["gnn_macro"].values, df["rf_macro"].values),
        paired_row("micro_pr_auc", df["gnn_micro"].values, df["rf_micro"].values),
    ]
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "aggregate_test.csv"), index=False)

    for r in rows:
        print(f"[{r['metric']}] GNN {r['gnn_mean']:.3f}±{r['gnn_std']:.3f} vs "
              f"RF {r['rf_mean']:.3f}±{r['rf_std']:.3f} | "
              f"Δ {r['mean_diff(gnn-rf)']:+.4f} 95%CI[{r['ci95_lo']:+.4f},{r['ci95_hi']:+.4f}] "
              f"(0 포함={r['ci_crosses_0']}) | paired-t p={r['paired_t_p']:.4f} | "
              f"Wilcoxon p={r['wilcoxon_p']:.4f} (min가능 {r['wilcoxon_min_possible_p']:.4f})")
    print(f"[저장] {os.path.join(OUT, 'aggregate_test.csv')}")


if __name__ == "__main__":
    main()
