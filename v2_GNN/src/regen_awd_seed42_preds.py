#!/usr/bin/env python3
"""표 8·표 9 정합성 수정용 — A_wd(검증선택 최종모델) seed-42 test 예측 재생성.

배경: results_improve/_ckpt_A_wd.pt 는 robustness.py 가 seed 순차 실행(마지막 seed=4)하며
매 seed 덮어써서 현재 seed-4 인스턴스(test macro≈0.174)임. 원고 표 8·표 9 캡션은
"seed-42"라고 명시하나 실제로는 seed-4 예측을 사용한 불일치가 있었음.

이 스크립트는 round1b 와 동일 구성(A_wd = focal γ2 + sqrt pos_weight + weight_decay 1e-4,
epochs=200 patience=30, SEED=42)으로 A_wd 를 재학습하여 seed-42 test 예측행렬(110×370)을
저장한다(test macro≈0.151/0.152 = 표3 seed42·표4·round1b 와 정합).

산출: v2_GNN/results_improve/paper_tables/awd_seed42_preds.npz
      (Yte, P_awd_seed42, ycols, valid_macro, test_macro, test_micro)
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import json
import numpy as np
import torch

import sys
sys.path.insert(0, os.path.dirname(__file__))
from data import ROOT, load_config, build_graphs
from train import set_seed, get_device
from train_improve import train_variant
from evaluate import per_pt_metrics, aggregate

A_WD = {"name": "A_wd_seed42_papertable", "loss": "focal", "pw_mode": "sqrt", "gamma": 2.0,
        "overrides": {"weight_decay": 1e-4}}
OUT = os.path.join(ROOT, "v2_GNN", "results_improve", "paper_tables")
os.makedirs(OUT, exist_ok=True)


def main():
    cfg = load_config()
    cfg["seed"] = 42
    device = get_device(cfg)
    set_seed(42)
    data = build_graphs(cfg)
    ycols = data["ycols"]
    print(f"[regen] device={device} seed=42 | A_wd 재학습(epochs=200 patience=30)...", flush=True)
    r = train_variant(cfg, data, device, A_WD, epochs=200, patience=30, log=print)
    P = r["P_test"].astype(np.float32)          # (110, 370)
    Yte = r["Yte"].astype(np.int8)
    df = per_pt_metrics(Yte, P, ycols, cfg["eval"]["threshold"])
    agg = aggregate(Yte, P, df, cfg["eval"]["threshold"])
    print(f"[regen] valid_macro={r['valid']:.4f} | test macro={agg['macro_pr_auc']:.4f} "
          f"micro={agg['micro_pr_auc']:.4f} | n_pt={agg['n_pt_evaluated']}", flush=True)
    np.savez_compressed(
        os.path.join(OUT, "awd_seed42_preds.npz"),
        Yte=Yte, P_awd_seed42=P, ycols=np.array([str(c) for c in ycols]),
        valid_macro=np.float64(r["valid"]),
        test_macro=np.float64(agg["macro_pr_auc"]),
        test_micro=np.float64(agg["micro_pr_auc"]),
    )
    json.dump({"seed": 42, "valid_macro": float(r["valid"]),
               "test_macro": float(agg["macro_pr_auc"]),
               "test_micro": float(agg["micro_pr_auc"]),
               "best_ep": int(r["best_ep"]), "n_pt": int(agg["n_pt_evaluated"])},
              open(os.path.join(OUT, "awd_seed42_meta.json"), "w"), indent=2)
    print("[regen] 저장 완료 →", os.path.join(OUT, "awd_seed42_preds.npz"), flush=True)


if __name__ == "__main__":
    main()
