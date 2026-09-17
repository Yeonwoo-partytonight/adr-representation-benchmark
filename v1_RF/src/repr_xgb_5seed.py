#!/usr/bin/env python3
"""§2-E — XGBoost 5시드 (심사 항목 6: 표 2 에 5시드 평균 열 추가).

지시서 `docs/903_kci_repr_learner_separation_prompt_for_vscode.md` §2-E.

- **표 2 의 XGBoost 행을 산출한 설정을 그대로** 재사용한다: `v1_RF/src/train.py::train_xgboost`
  (라벨별 OvR · 라벨별 scale_pos_weight=neg/pos · config.yaml 의 xgboost 파라미터).
  ★ 설정 변경 금지 — 시드만 바꾼다.
- 표현·데이터·분할·평가는 디폴트 RF 와 동일(Morgan r=2/2,048, scaffold split, THR 0.5, 301 PT).
- 시드 [1,2,3,4,42] → test mean±std.

실행: .venv/bin/python -u v1_RF/src/repr_xgb_5seed.py
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from data import ROOT, load_config, load_dataset      # noqa: E402
from features import morgan_matrix                    # noqa: E402
from evaluate import per_pt_metrics, aggregate        # noqa: E402
from train import train_xgboost                       # noqa: E402  ★ 표 2 산출 경로 그대로 재사용

OUT = os.path.join(ROOT, "v1_RF", "results_repr")
os.makedirs(OUT, exist_ok=True)
SEEDS = [1, 2, 3, 4, 42]
THR = 0.5


def log(msg):
    print(msg, flush=True)


def main():
    t_start = time.time()
    cfg = load_config()
    X, Y, ycols, masks = load_dataset(cfg, log=log)
    fp = cfg["fingerprint"]
    M, failed = morgan_matrix(X["smiles_canonical"].tolist(), fp["radius"], fp["n_bits"], log=log)
    tr, te = masks["train"], masks["test"]
    Xtr, Xte, Ytr, Yte = M[tr], M[te], Y[tr], Y[te]

    rows = []
    for seed in SEEDS:
        t0 = time.time()
        P = train_xgboost(Xtr, Ytr, Xte, cfg, seed, log=log)     # 설정 불변, 시드만 변경
        df = per_pt_metrics(Yte, P, ycols, THR)
        agg = aggregate(Yte, P, df, THR)
        rows.append({"seed": seed, "xgb_macro": agg["macro_pr_auc"], "xgb_micro": agg["micro_pr_auc"],
                     "macro_roc": agg["macro_roc_auc"], "macro_f1@0.5": agg["macro_f1@0.5"],
                     "hamming": agg["hamming_accuracy"], "n_pt_evaluated": agg["n_pt_evaluated"]})
        log(f"[seed {seed}] XGB test macroAP {agg['macro_pr_auc']:.4f} microAP {agg['micro_pr_auc']:.4f} "
            f"| n_pt {agg['n_pt_evaluated']} ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(os.path.join(OUT, "xgb_5seed.csv"), index=False)

    d = pd.DataFrame(rows)
    log(f"[xgb] macro {d['xgb_macro'].mean():.4f} ± {d['xgb_macro'].std(ddof=1):.4f} | "
        f"micro {d['xgb_micro'].mean():.4f} ± {d['xgb_micro'].std(ddof=1):.4f} "
        f"({(time.time()-t_start)/60:.1f}분)")


if __name__ == "__main__":
    main()
