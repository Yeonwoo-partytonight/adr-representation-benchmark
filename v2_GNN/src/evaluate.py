#!/usr/bin/env python3
"""STEP E — 평가 (v2_GNN). v1과 동일 프로토콜.

명세 docs/09_v2_gnn_spec.md §3 STEP E.
- test split: PR-AUC(macro+micro) ★핵심, ROC-AUC(macro/micro), F1@0.5, hamming/subset accuracy.
- test 양성 0 PT 는 macro 제외 + 개수 보고(v1과 동일 → 301 기대; 불일치 시 멈추고 보고).
- 출력: metrics_overall.csv(GNN 3종+ablation, v1 RF/XGB 병기), metrics_per_pt.csv(valid-최적 GNN),
  pr_curves.png(최적 GNN vs v1 RF micro PR), summary.md.
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data import ROOT, load_config
from sklearn.metrics import (
    average_precision_score, roc_auc_score, f1_score,
    accuracy_score, hamming_loss, precision_recall_curve,
)

RESULTS = os.path.join(ROOT, "v2_GNN", "results")


def per_pt_metrics(Yte, P, ycols, thr):
    rows = []
    for j, pt in enumerate(ycols):
        yt = Yte[:, j]; ys = P[:, j]; npos = int(yt.sum())
        row = {"meddra_pt": pt, "n_pos_test": npos, "prevalence": float(yt.mean()),
               "pr_auc": np.nan, "roc_auc": np.nan, "f1": np.nan}
        if npos > 0:
            row["pr_auc"] = average_precision_score(yt, ys)
            if 0 < npos < len(yt):
                row["roc_auc"] = roc_auc_score(yt, ys)
            row["f1"] = f1_score(yt, (ys >= thr).astype(int), zero_division=0)
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate(Yte, P, df, thr):
    ev = df[df.n_pos_test > 0]
    Yhat = (P >= thr).astype(int)
    return {
        "macro_pr_auc": float(ev["pr_auc"].mean()),
        "micro_pr_auc": float(average_precision_score(Yte.ravel(), P.ravel())),
        "macro_roc_auc": float(ev["roc_auc"].mean()),
        "micro_roc_auc": float(roc_auc_score(Yte.ravel(), P.ravel())),
        "macro_f1@0.5": float(ev["f1"].mean()),
        "micro_f1@0.5": float(f1_score(Yte.ravel(), Yhat.ravel(), zero_division=0)),
        "hamming_accuracy": float(1.0 - hamming_loss(Yte, Yhat)),
        "subset_accuracy": float(accuracy_score(Yte, Yhat)),
        "n_pt_evaluated": int(len(ev)),
        "n_pt_excluded_0pos": int((df.n_pos_test == 0).sum()),
    }


def main():
    cfg = load_config()
    thr = cfg["eval"]["threshold"]
    npz = np.load(os.path.join(RESULTS, "_preds_v2.npz"), allow_pickle=True)
    Yte = npz["Yte"].astype(int)
    ycols = list(npz["ycols"])
    model_names = list(npz["models"])
    best = str(npz["best_by_valid"])
    valids = {k: float(v) for k, v in zip(model_names, npz["valids"])}
    preds = {k: npz[f"P_{k}"] for k in model_names}
    with open(os.path.join(RESULTS, "_train_meta_v2.json")) as f:
        meta = json.load(f)

    overall, per_pt = {}, {}
    for name, P in preds.items():
        df = per_pt_metrics(Yte, P, ycols, thr)
        m = aggregate(Yte, P, df, thr)
        m["valid_macro_pr_auc"] = valids[name]
        overall[name] = m
        per_pt[name] = df
        print(f"[eval] {name}: test macroPR {m['macro_pr_auc']:.3f} microPR {m['micro_pr_auc']:.3f} "
              f"macroROC {m['macro_roc_auc']:.3f} | valid macroPR {valids[name]:.3f} "
              f"| evalPT {m['n_pt_evaluated']}")

    # 평가 PT 수 v1과 동일성 검증 (B8)
    exp = cfg["eval"]["expected_eval_pt"]
    got = overall[best]["n_pt_evaluated"]
    if got != exp:
        raise SystemExit(f"[중단] 평가 PT {got} != 기대 {exp}. v1과 test/제외규칙 불일치 — 점검 필요.")

    # v1 행 병기
    v1 = pd.read_csv(os.path.join(ROOT, cfg["data"]["v1_overall"])).set_index("model")
    rows = []
    for name, m in overall.items():
        r = {"model": f"GNN-{name}", **{k: m.get(k) for k in
             ["macro_pr_auc", "micro_pr_auc", "macro_roc_auc", "micro_roc_auc",
              "macro_f1@0.5", "hamming_accuracy", "subset_accuracy",
              "valid_macro_pr_auc", "n_pt_evaluated"]}}
        rows.append(r)
    for vname in v1.index:                      # v1 RF/XGB 병기
        r = {"model": f"v1-{vname}"}
        for k in ["macro_pr_auc", "micro_pr_auc", "macro_roc_auc", "micro_roc_auc",
                  "macro_f1@0.5", "hamming_accuracy", "subset_accuracy", "n_pt_evaluated"]:
            r[k] = float(v1.loc[vname, k]) if k in v1.columns else np.nan
        r["valid_macro_pr_auc"] = np.nan
        rows.append(r)
    ov = pd.DataFrame(rows).set_index("model")
    ov.to_csv(os.path.join(RESULTS, "metrics_overall.csv"))

    # per-PT: valid-최적 GNN
    per_pt[best].sort_values("n_pos_test", ascending=False).to_csv(
        os.path.join(RESULTS, "metrics_per_pt.csv"), index=False)

    # pr_curves: 최적 GNN micro vs v1 RF micro
    plot_pr(Yte, preds[best], best, cfg, os.path.join(RESULTS, "pr_curves.png"))

    write_summary(overall, meta, best, valids, ov, os.path.join(RESULTS, "summary.md"))
    print(f"[저장] metrics_overall.csv, metrics_per_pt.csv, pr_curves.png, summary.md "
          f"| best(valid)={best}")


def plot_pr(Yte, P_best, best, cfg, path):
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    prec, rec, _ = precision_recall_curve(Yte.ravel(), P_best.ravel())
    ap = average_precision_score(Yte.ravel(), P_best.ravel())
    ax.plot(rec, prec, label=f"v2 GNN-{best} (micro AP={ap:.3f})")
    # v1 RF 비교 곡선 (v1 _preds.npz 가 있으면)
    v1npz = os.path.join(ROOT, "v1_RF", "results", "_preds.npz")
    if os.path.exists(v1npz):
        z = np.load(v1npz, allow_pickle=True)
        if "P_RandomForest" in z.files:
            Prf = z["P_RandomForest"]; Yrf = z["Yte"].astype(int)
            p2, r2, _ = precision_recall_curve(Yrf.ravel(), Prf.ravel())
            ap2 = average_precision_score(Yrf.ravel(), Prf.ravel())
            ax.plot(r2, p2, ls="--", label=f"v1 RF (micro AP={ap2:.3f})")
    ax.axhline(Yte.mean(), ls=":", c="gray", label=f"random (prev={Yte.mean():.3f})")
    ax.set(xlabel="Recall", ylabel="Precision",
           title="Micro-averaged PR curve: v2 GNN vs v1 RF")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def write_summary(overall, meta, best, valids, ov, path):
    bm = overall[best]
    v1rf = ov.loc["v1-RandomForest"] if "v1-RandomForest" in ov.index else None
    lines = [
        "# v2_GNN 결과 요약 (RQ2)",
        "",
        f"> 분자 그래프 GNN(GCN/GIN/GAT) 멀티라벨 부작용 예측. v1과 동일 master_X/Y + scaffold_split.json "
        f"+ 동일 평가 프로토콜(test 110분자 / 평가 PT {bm['n_pt_evaluated']}). device={meta['device']}, seed={meta['seed']}, "
        f"loss={meta['loss']}, hidden={meta['hidden']}×{meta['n_layers']}층.",
        f"> **모델 선택은 valid macro PR-AUC 로만** 수행(테스트로 선택하지 않음 — leakage/cherry-picking 방지). "
        f"valid 기준 최적 = **{best}**.",
        "",
        "## 성능 (test) — ★PR-AUC 핵심, v1 병기",
        "",
        "| 모델 | valid macroPR | test macro PR-AUC | test micro PR-AUC | macro ROC-AUC | macro F1@0.5 | hamming |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in ov.index:
        r = ov.loc[name]
        vpr = "—" if pd.isna(r["valid_macro_pr_auc"]) else f"{r['valid_macro_pr_auc']:.3f}"
        star = " ★" if name == f"GNN-{best}" else ""
        lines.append(f"| {name}{star} | {vpr} | {r['macro_pr_auc']:.3f} | {r['micro_pr_auc']:.3f} | "
                     f"{r['macro_roc_auc']:.3f} | {r['macro_f1@0.5']:.3f} | {r['hamming_accuracy']:.3f} |")
    lines += ["", "## 관찰"]
    if v1rf is not None:
        diff = bm["macro_pr_auc"] - float(v1rf["macro_pr_auc"])
        rel = diff / float(v1rf["macro_pr_auc"]) * 100
        lines.append(f"- valid-최적 GNN({best}) test macro PR-AUC {bm['macro_pr_auc']:.3f} vs "
                     f"v1 RF {float(v1rf['macro_pr_auc']):.3f} → 차이 {diff:+.3f} ({rel:+.1f}%). "
                     f"통계적 유의성은 stats.py(Wilcoxon, RQ2 판정) 참조.")
    lines += [
        f"- GNN 3종 valid: " + ", ".join(f"{k} {valids[k]:.3f}" for k in valids
                                         if "pool" not in k) + ".",
        "- Ablation: GNN(v2) vs Fingerprint+RF(v1) [위 표], GCN/GIN/GAT 3종 비교, pooling(mean vs add) 변형 포함.",
        "",
        "## 재현성 / 한계",
        "- 전역 SEED=42(torch/numpy/random) 고정, 설정 config.yaml 분리.",
        "- **MPS(Apple Silicon) 비결정성으로 run 간 소수점 미세 변동이 있을 수 있음**(GPU 비결정적 누적). "
        "결론(모델 순위·유의성)은 안정적이나 절대 수치는 ±소폭 변동 가능.",
        "- 데이터 규모 작음(train ~870분자) → 분산 큼. RQ2 판정은 PT 단위 Wilcoxon 검정으로.",
        "",
        "## 산출물",
        "- metrics_overall.csv (GNN 3종+ablation, v1 RF/XGB 병기)",
        "- metrics_per_pt.csv (valid-최적 GNN PT별)",
        "- pr_curves.png (최적 GNN vs v1 RF micro PR)",
        "- significance_v1_vs_v2.csv (stats.py — RQ2)",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
