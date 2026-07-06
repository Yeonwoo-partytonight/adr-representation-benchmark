#!/usr/bin/env python3
"""STEP D — 평가 (v1_RF).

명세 docs/08_v1_rf_spec.md §2 STEP D.
- test split 라벨별 + 집계 지표:
  - PR-AUC(average precision): macro(라벨 평균) + micro(전체 펼침). ★핵심
  - ROC-AUC(macro/micro), F1(threshold=0.5), Accuracy(hamming + subset 둘 다 — A5).
- test 양성 0 라벨은 macro 평균에서 제외하고 그 수를 보고(A4).
- 출력:
  - results/metrics_overall.csv   (모델 × 지표)
  - results/metrics_per_pt.csv    (PT별 PR-AUC 등)
  - results/pr_curves.png         (micro PR curve + 대표 PT)
  - results/summary.md            (RF vs XGB 비교 요약)

실행: python v1_RF/src/evaluate.py   (train.py 이후)
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

RESULTS = os.path.join(ROOT, "v1_RF", "results")


def per_pt_metrics(Yte, P, ycols, thr):
    """라벨별 지표 DataFrame. test 양성 0 라벨은 pr/roc=NaN."""
    rows = []
    for j, pt in enumerate(ycols):
        yt = Yte[:, j]
        ys = P[:, j]
        npos = int(yt.sum())
        row = {"meddra_pt": pt, "n_pos_test": npos, "prevalence": float(yt.mean()),
               "pr_auc": np.nan, "roc_auc": np.nan, "f1": np.nan}
        if npos > 0:
            row["pr_auc"] = average_precision_score(yt, ys)
            if 0 < npos < len(yt):          # 한 클래스만 있으면 ROC 정의 불가
                row["roc_auc"] = roc_auc_score(yt, ys)
            row["f1"] = f1_score(yt, (ys >= thr).astype(int), zero_division=0)
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate(Yte, P, df, thr):
    """집계 지표(macro/micro 등). test 양성>0 라벨만 macro 평균."""
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
        "random_baseline_pr_auc(mean_prevalence)": float(ev["prevalence"].mean()),
    }


def plot_pr_curves(Yte, preds, df_ref, n_repr, path):
    """micro PR curve(모델별) + 대표 PT(빈도 상위) PR curve(첫 모델)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # (1) micro PR curve — 모델 비교
    ax = axes[0]
    for name, P in preds.items():
        prec, rec, _ = precision_recall_curve(Yte.ravel(), P.ravel())
        ap = average_precision_score(Yte.ravel(), P.ravel())
        ax.plot(rec, prec, label=f"{name} (micro AP={ap:.3f})")
    base = Yte.mean()
    ax.axhline(base, ls="--", c="gray", label=f"random (prev={base:.3f})")
    ax.set(xlabel="Recall", ylabel="Precision", title="Micro-averaged PR curve")
    ax.legend(loc="upper right", fontsize=8)

    # (2) 대표 PT(test 양성 상위 n_repr) — 첫 모델
    ax = axes[1]
    first = next(iter(preds))
    P = preds[first]
    top = df_ref.sort_values("n_pos_test", ascending=False).head(n_repr)
    name_to_idx = {pt: i for i, pt in enumerate(df_ref["meddra_pt"])}
    for _, r in top.iterrows():
        j = name_to_idx[r["meddra_pt"]]
        prec, rec, _ = precision_recall_curve(Yte[:, j], P[:, j])
        ax.plot(rec, prec, label=f"{r['meddra_pt'][:24]} (n+={int(r['n_pos_test'])}, AP={r['pr_auc']:.2f})")
    ax.set(xlabel="Recall", ylabel="Precision",
           title=f"Top-{n_repr} frequent PT PR curve ({first})")
    ax.legend(loc="upper right", fontsize=7)

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def write_summary(overall, meta, ev_excluded, path):
    rf = overall.get("RandomForest", {})
    xgb = overall.get("XGBoost")
    base = rf.get("random_baseline_pr_auc(mean_prevalence)", float("nan"))
    lines = [
        "# v1_RF 베이스라인 결과 요약",
        "",
        f"> 1단계(논문 비교 대상 baseline). 데이터: master_X/Y "
        f"({meta['n_train']+meta['n_valid']+meta['n_test']} 분자 × {meta['n_pt']} PT), "
        f"scaffold split {meta['n_train']}/{meta['n_valid']}/{meta['n_test']}, seed={meta['seed']}.",
        f"> 특징: Morgan(ECFP4, r={meta['fp_radius']}/{meta['fp_bits']}bit). "
        f"평가: test {meta['n_test']} 분자. mol 변환 실패 {meta['n_failed_mol']}개.",
        "",
        "## 성능 (test) — ★PR-AUC 핵심",
        "",
        "| 모델 | macro PR-AUC | micro PR-AUC | macro ROC-AUC | micro ROC-AUC | macro F1@0.5 | hamming acc | subset acc |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, m in overall.items():
        lines.append(
            f"| **{name}** | **{m['macro_pr_auc']:.3f}** | **{m['micro_pr_auc']:.3f}** | "
            f"{m['macro_roc_auc']:.3f} | {m['micro_roc_auc']:.3f} | {m['macro_f1@0.5']:.3f} | "
            f"{m['hamming_accuracy']:.3f} | {m['subset_accuracy']:.3f} |")
    lines.append(f"| 무작위 기준선(평균 prevalence) | {base:.3f} | — | 0.500 | 0.500 | — | — | — |")
    lines += [
        "",
        f"- 평가 대상 PT = {rf.get('n_pt_evaluated','?')}개 "
        f"(test 양성 ≥1). test 양성 0 이라 제외된 PT = {rf.get('n_pt_excluded_0pos','?')}개(A4).",
    ]
    if not np.isnan(rf.get("macro_pr_auc", np.nan)) and base > 0:
        lines.append(f"- **핵심 해석**: RandomForest macro PR-AUC "
                     f"{rf['macro_pr_auc']:.3f} = 무작위 기준선({base:.3f})의 "
                     f"약 **{rf['macro_pr_auc']/base:.1f}배**. 엄격한 scaffold split에서 구조 정보만으로 예측력 확보.")
    if xgb:
        better = "RandomForest" if rf["macro_pr_auc"] >= xgb["macro_pr_auc"] else "XGBoost"
        lines.append(f"- RF vs XGBoost: macro PR-AUC {rf['macro_pr_auc']:.3f} vs "
                     f"{xgb['macro_pr_auc']:.3f} → **{better}** 우세.")
    lines += [
        "",
        "## 캐비엇 (논문에 명시)",
        "- **F1@0.5 낮음**: 임계값 0.5는 희소 멀티라벨에 보수적. 임계값-무관 **PR-AUC를 핵심 지표**로 사용. 운영 임계값 최적화는 후속.",
        "- **subset accuracy ~0**: 370개 라벨 동시 정확 일치 기준이라 멀티라벨에서 자연스러운 결과(hamming accuracy 병기). 보고만.",
        "- 데이터 규모 작음(train ~870분자) → 분산 큼. 통계적 유의성 검정은 v2 비교 시 수행.",
        "",
        "## 다음 단계에서의 의미",
        "이 표가 **v2_GNN / v3_Multimodal 의 비교 기준선**. 동일 master_X/Y + scaffold_split.json 으로 공정 비교.",
        "",
        "## 산출물",
        "- `metrics_overall.csv` — 모델 × 집계 지표",
        "- `metrics_per_pt.csv` — PT별 PR-AUC/ROC-AUC/F1(양성 많은 순)",
        "- `pr_curves.png` — micro PR curve(모델 비교) + 대표 PT PR curve",
        "- 코드: `v1_RF/src/{features,data,train,evaluate}.py`, 설정: `config.yaml`",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    cfg = load_config()
    thr = cfg["eval"]["threshold"]
    n_repr = cfg["eval"].get("n_repr_pt", 3)

    npz = np.load(os.path.join(RESULTS, "_preds.npz"), allow_pickle=True)
    Yte = npz["Yte"].astype(int)
    ycols = list(npz["ycols"])
    model_names = list(npz["models"])
    preds = {name: npz[f"P_{name}"] for name in model_names}
    with open(os.path.join(RESULTS, "_train_meta.json")) as f:
        meta = json.load(f)

    overall = {}
    per_pt_frames = {}
    for name, P in preds.items():
        df = per_pt_metrics(Yte, P, ycols, thr)
        overall[name] = aggregate(Yte, P, df, thr)
        per_pt_frames[name] = df
        m = overall[name]
        print(f"[eval] {name}: macro PR-AUC {m['macro_pr_auc']:.3f} | micro PR-AUC {m['micro_pr_auc']:.3f} "
              f"| macro ROC-AUC {m['macro_roc_auc']:.3f} | macro F1 {m['macro_f1@0.5']:.3f}")

    # metrics_overall.csv (모델 × 지표)
    ov = pd.DataFrame(overall).T
    ov.index.name = "model"
    ov.to_csv(os.path.join(RESULTS, "metrics_overall.csv"))

    # metrics_per_pt.csv (모델별 컬럼 접두어 합본, 양성 많은 순)
    ref = per_pt_frames[model_names[0]]
    base = ref[["meddra_pt", "n_pos_test", "prevalence"]].copy()
    for name, df in per_pt_frames.items():
        base[f"{name}_pr_auc"] = df["pr_auc"].values
        base[f"{name}_roc_auc"] = df["roc_auc"].values
        base[f"{name}_f1"] = df["f1"].values
    base.sort_values("n_pos_test", ascending=False).to_csv(
        os.path.join(RESULTS, "metrics_per_pt.csv"), index=False)

    # pr_curves.png
    plot_pr_curves(Yte, preds, ref, n_repr, os.path.join(RESULTS, "pr_curves.png"))

    # summary.md
    write_summary(overall, meta, None, os.path.join(RESULTS, "summary.md"))

    print(f"[저장] metrics_overall.csv, metrics_per_pt.csv, pr_curves.png, summary.md")
    print(json.dumps(overall, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
