#!/usr/bin/env python3
"""개선 사이클 공용 라운드 평가기 (v2_GNN). Round 1a/1b 공유.

- valid macro PR-AUC 로 best 선택(★ test 로 고르지 않음).
- v1과 동일 프로토콜로 test 지표(macro/micro PR-AUC, ROC, F1, hamming), 301 PT 검증.
- best vs v1 RF: PT별 PR-AUC Wilcoxon(주)+paired t(보조), p<0.05.
- 빈도 3분위(전체 양성수)별 best GNN vs v1 RF.
- 산출: <outdir>/{metrics_overall.csv, metrics_per_pt.csv, significance.csv, freq_tertile.csv, summary.md}
"""
import os
import json
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, ttest_rel

from data import ROOT
from evaluate import per_pt_metrics, aggregate

V1_OVERALL = os.path.join(ROOT, "v1_RF/results/metrics_overall.csv")
V1_PER_PT = os.path.join(ROOT, "v1_RF/results/metrics_per_pt.csv")
MASTER_Y = os.path.join(ROOT, "data/processed/master_Y.parquet")


def evaluate_round(preds, valids, Yte, ycols, outdir, label, thr=0.5, expected_pt=301, alpha=0.05):
    os.makedirs(outdir, exist_ok=True)
    overall, per_pt = {}, {}
    for name, P in preds.items():
        df = per_pt_metrics(Yte, P, ycols, thr)
        m = aggregate(Yte, P, df, thr)
        m["valid_macro_pr_auc"] = valids[name]
        overall[name] = m; per_pt[name] = df

    best = max(valids, key=valids.get)            # valid 기준 선택
    got = overall[best]["n_pt_evaluated"]
    if got != expected_pt:
        raise SystemExit(f"[중단] 평가 PT {got} != {expected_pt} — v1과 프로토콜 불일치")

    # metrics_overall: 변형들 + v1 RF/XGB 병기
    v1 = pd.read_csv(V1_OVERALL).set_index("model")
    cols = ["macro_pr_auc", "micro_pr_auc", "macro_roc_auc", "micro_roc_auc",
            "macro_f1@0.5", "hamming_accuracy", "subset_accuracy", "valid_macro_pr_auc", "n_pt_evaluated"]
    rows = []
    for name, m in overall.items():
        rows.append({"model": f"{label}-{name}", **{k: m.get(k) for k in cols}})
    for vn in v1.index:
        r = {"model": f"v1-{vn}"}
        for k in cols:
            r[k] = float(v1.loc[vn, k]) if k in v1.columns else np.nan
        rows.append(r)
    ov = pd.DataFrame(rows).set_index("model")
    ov.to_csv(os.path.join(outdir, "metrics_overall.csv"))

    # per-PT (best) 저장
    pp_best = per_pt[best].sort_values("n_pos_test", ascending=False)
    pp_best.to_csv(os.path.join(outdir, "metrics_per_pt.csv"), index=False)

    # 유의성: best vs v1 RF (meddra_pt 타입 str 통일 후 merge)
    v1pp = pd.read_csv(V1_PER_PT)
    v1pp["meddra_pt"] = v1pp["meddra_pt"].astype(str)
    left = per_pt[best][["meddra_pt", "n_pos_test", "pr_auc"]].rename(columns={"pr_auc": "gnn"}).copy()
    left["meddra_pt"] = left["meddra_pt"].astype(str)
    m = left.merge(
        v1pp[["meddra_pt", "RandomForest_pr_auc"]].rename(columns={"RandomForest_pr_auc": "rf"}),
        on="meddra_pt").dropna(subset=["gnn", "rf"])
    g, r = m["gnn"].values, m["rf"].values
    diff = g - r
    w_stat, w_p = wilcoxon(g, r)
    t_stat, t_p = ttest_rel(g, r)
    sig = pd.DataFrame([{
        "comparison": f"{label}-{best} vs v1 RandomForest (PT별 PR-AUC)",
        "n_pt": len(m), "gnn_mean_pr": float(g.mean()), "rf_mean_pr": float(r.mean()),
        "mean_diff(gnn-rf)": float(diff.mean()), "median_diff": float(np.median(diff)),
        "n_pt_gnn_higher": int((diff > 0).sum()),
        "wilcoxon_p": float(w_p), "paired_t_p": float(t_p), "alpha": alpha,
        "significant": bool(w_p < alpha), "direction": "gnn>rf" if diff.mean() > 0 else "gnn<=rf",
    }])
    sig.to_csv(os.path.join(outdir, "significance.csv"), index=False)

    # 빈도 3분위
    Yall = pd.read_parquet(MASTER_Y)
    pos_total = {str(c): int(Yall[c].sum()) for c in ycols}
    m2 = m.copy()
    m2["pos_total"] = m2["meddra_pt"].astype(str).map(pos_total)
    m2["tertile"] = pd.qcut(m2["pos_total"], 3, labels=["저빈도", "중빈도", "고빈도"])
    tert = m2.groupby("tertile", observed=True).agg(
        n_pt=("meddra_pt", "count"), pmin=("pos_total", "min"), pmax=("pos_total", "max"),
        gnn=("gnn", "mean"), rf=("rf", "mean")).reset_index()
    tert["diff"] = tert["gnn"] - tert["rf"]
    tert.to_csv(os.path.join(outdir, "freq_tertile.csv"), index=False)

    return {"overall": overall, "best": best, "ov": ov, "sig": sig.iloc[0].to_dict(),
            "tert": tert, "per_pt_best": per_pt[best]}


def write_round_summary(res, meta, outdir, label, title, extra_lines=None):
    ov, best, sig, tert = res["ov"], res["best"], res["sig"], res["tert"]
    bm = res["overall"][best]
    lines = [f"# {title}", "",
             f"> {meta}", "",
             "## 성능 (test) — valid 선택 모델 ★, v1 병기", "",
             "| 모델 | valid macroPR | test macroPR | test microPR | macroROC | hamming |",
             "|---|---|---|---|---|---|"]
    for name in ov.index:
        r = ov.loc[name]
        vpr = "—" if pd.isna(r["valid_macro_pr_auc"]) else f"{r['valid_macro_pr_auc']:.3f}"
        star = " ★" if name == f"{label}-{best}" else ""
        lines.append(f"| {name}{star} | {vpr} | {r['macro_pr_auc']:.3f} | {r['micro_pr_auc']:.3f} | "
                     f"{r['macro_roc_auc']:.3f} | {r['hamming_accuracy']:.3f} |")
    lines += ["", "## RQ2 판정 (best vs v1 RF)",
              f"- mean PR-AUC {sig['gnn_mean_pr']:.3f} vs {sig['rf_mean_pr']:.3f} "
              f"(Δ{sig['mean_diff(gnn-rf)']:+.3f}, {sig['n_pt_gnn_higher']}/{sig['n_pt']} PT 우위)",
              f"- **Wilcoxon p={sig['wilcoxon_p']:.3g}** (paired t p={sig['paired_t_p']:.3g}), "
              f"α={sig['alpha']} → **{'유의' if sig['significant'] else '비유의'}**, 방향 {sig['direction']}",
              "", "## 빈도 3분위별 best GNN vs v1 RF",
              "| 구간 | PT수 | 양성수 | GNN | RF | 차이 |", "|---|---|---|---|---|---|"]
    for _, t in tert.iterrows():
        lines.append(f"| {t['tertile']} | {int(t['n_pt'])} | {int(t['pmin'])}–{int(t['pmax'])} | "
                     f"{t['gnn']:.3f} | {t['rf']:.3f} | {t['diff']:+.3f} |")
    if extra_lines:
        lines += [""] + extra_lines
    lines += ["", "> MPS(Apple Silicon) 비결정성으로 run 간 소수점 미세 변동 가능. "
              "공정성: 비교 대상 v1 RF는 디폴트 설정(미튜닝) — 최종 판정 시 RF 동등예산 튜닝 필요(한계로 기록)."]
    with open(os.path.join(outdir, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
