#!/usr/bin/env python3
"""개선 사이클 라운드 러너 (v2_GNN). Round 1a=(다) 손실/불균형, Round 1b=(라) 정규화/구조.

명세 docs/10_v2_gnn_improve_spec.md. 사용법:
  python train_improve.py 1a    # (다) 단독: 손실/불균형 변형, 정규화 현행 유지
  python train_improve.py 1b    # (라): 1a 최적 손실 위에 정규화/구조 보강

공정비교 불변(데이터·split·test·301·프로토콜 v1 동일), 모델 선택 valid macro PR-AUC,
SEED=42, MPS fallback. 산출은 results_improve/round<라운드>/ 에만(기존 results/ 보존).
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import sys
import json
import numpy as np
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader

from data import ROOT, load_config, build_graphs
from graph_features import ATOM_FDIM
from models import build_model
from train import set_seed, get_device, compute_pos_weight, predict_proba, FocalLoss, macro_pr_auc
from eval_improve import evaluate_round, write_round_summary

OUT_ROOT = os.path.join(ROOT, "v2_GNN", "results_improve")


def make_pos_weight(graphs_train, n_out, mode, cap=10.0):
    """mode: raw | sqrt | clip | none → pos_weight 텐서(or None)."""
    if mode == "none":
        return None
    pw = compute_pos_weight(graphs_train, n_out)        # neg/pos
    if mode == "sqrt":
        pw = torch.sqrt(pw)
    elif mode == "clip":
        pw = torch.clamp(pw, max=cap)
    return pw


def make_criterion(loss, pw, gamma):
    if loss == "focal":
        return FocalLoss(gamma=gamma, pos_weight=pw)
    return nn.BCEWithLogitsLoss(pos_weight=pw)


def train_variant(cfg, data, device, v, epochs, patience, log=print):
    """v: dict(name, loss, pw_mode, gamma, overrides). returns valid/test 결과."""
    n_out = len(data["ycols"])
    set_seed(cfg["seed"])
    tr = DataLoader(data["graphs"]["train"], batch_size=cfg["train"]["batch_size"], shuffle=True)
    tr_eval = DataLoader(data["graphs"]["train"], batch_size=cfg["train"]["batch_size"])
    va = DataLoader(data["graphs"]["valid"], batch_size=cfg["train"]["batch_size"])
    te = DataLoader(data["graphs"]["test"], batch_size=cfg["train"]["batch_size"])

    model = build_model(cfg, ATOM_FDIM, n_out, conv_type="gin", pool="mean",
                        overrides=v.get("overrides")).to(device)
    pw = make_pos_weight(data["graphs"]["train"], n_out, v["pw_mode"])
    pw = pw.to(device) if pw is not None else None
    criterion = make_criterion(v["loss"], pw, v.get("gamma", 2.0))
    wd = v.get("overrides", {}).get("weight_decay", cfg["train"]["weight_decay"])
    opt = torch.optim.Adam(model.parameters(), lr=cfg["train"]["lr"], weight_decay=wd)

    best_v, best_state, best_ep, wait = -1.0, None, 0, 0
    for ep in range(1, epochs + 1):
        model.train(); tot = 0.0
        for batch in tr:
            batch = batch.to(device)
            opt.zero_grad()
            loss = criterion(model(batch), batch.y.view(-1, n_out))
            loss.backward(); opt.step()
            tot += loss.item() * batch.num_graphs
        Pva, Yva = predict_proba(model, va, device, n_out)
        vmac = macro_pr_auc(Yva, Pva)
        if vmac > best_v:
            best_v, best_ep = vmac, ep
            best_state = {k: val.detach().cpu().clone() for k, val in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
        if ep % 20 == 0 or ep == 1:
            log(f"  [{v['name']}] ep {ep:3d} loss {tot/len(data['graphs']['train']):.4f} "
                f"validMacro {vmac:.4f} best {best_v:.4f}@{best_ep}")
        if wait >= patience:
            log(f"  [{v['name']}] early stop @ ep {ep} (best {best_v:.4f}@{best_ep})")
            break
    model.load_state_dict(best_state)
    Pte, Yte = predict_proba(model, te, device, n_out)
    Ptr, Ytr = predict_proba(model, tr_eval, device, n_out)      # gap 측정용 train macro
    train_macro = macro_pr_auc(Ytr, Ptr)
    torch.save(best_state, os.path.join(OUT_ROOT, f"_ckpt_{v['name']}.pt"))
    return {"valid": best_v, "best_ep": best_ep, "train_macro": train_macro,
            "P_test": Pte.astype(np.float32), "Yte": Yte.astype(np.int8)}


# ── Round 1a: (다) 손실/불균형만 (정규화 현행: dropout 0.2, weight_decay 0, 3층) ──
ROUND1A = [
    {"name": "raw",          "loss": "bce",   "pw_mode": "raw"},     # 대조군 = 기존 null 재현
    {"name": "sqrt",         "loss": "bce",   "pw_mode": "sqrt"},    # pos_weight 완화
    {"name": "clip10",       "loss": "bce",   "pw_mode": "clip"},    # pos_weight 상한 10
    {"name": "focal_g2",     "loss": "focal", "pw_mode": "none", "gamma": 2.0},
    {"name": "focal_g2_sqrt","loss": "focal", "pw_mode": "sqrt", "gamma": 2.0},
]

# ── Round 1b: (라) 정규화/구조. 손실 고정 = 1a 최적(focal γ=2 + sqrt pos_weight). ──
_FIX = {"loss": "focal", "pw_mode": "sqrt", "gamma": 2.0}    # 전 변형 공통 고정
ROUND1B = [
    {"name": "A_wd",          **_FIX, "overrides": {"weight_decay": 1e-4}},
    {"name": "B_wd_drop",     **_FIX, "overrides": {"weight_decay": 1e-4, "dropout": 0.4}},
    {"name": "C_wd_drop_jk",  **_FIX, "overrides": {"weight_decay": 1e-4, "dropout": 0.4, "jk": "cat"}},
    {"name": "D_wd_drop_res", **_FIX, "overrides": {"weight_decay": 1e-4, "dropout": 0.4, "residual": True}},
]


def run_round(round_id, variants, epochs, patience, label, title):
    cfg = load_config()
    set_seed(cfg["seed"])
    device = get_device(cfg)
    outdir = os.path.join(OUT_ROOT, f"round{round_id}")
    os.makedirs(outdir, exist_ok=True)
    print(f"[round {round_id}] device={device} | 변형 {len(variants)}개 | epochs {epochs} patience {patience}")
    data = build_graphs(cfg)
    ycols = data["ycols"]

    preds, valids, best_eps, train_macros = {}, {}, {}, {}
    for v in variants:
        print(f"=== {v['name']} (loss={v['loss']} pw={v['pw_mode']}"
              f"{' γ=' + str(v.get('gamma')) if v['loss'] == 'focal' else ''} "
              f"ovr={v.get('overrides', {})}) ===")
        r = train_variant(cfg, data, device, v, epochs, patience)
        preds[v["name"]] = r["P_test"]; valids[v["name"]] = r["valid"]
        best_eps[v["name"]] = r["best_ep"]; train_macros[v["name"]] = r["train_macro"]
        print(f"  → valid macroPR {r['valid']:.4f} @ep{r['best_ep']} | train macroPR {r['train_macro']:.4f} "
              f"(gap {r['train_macro']-r['valid']:+.4f})")
    Yte = list(preds.values()) and r["Yte"]

    res = evaluate_round(preds, valids, Yte, ycols, outdir, label,
                         thr=cfg["eval"]["threshold"], expected_pt=cfg["eval"]["expected_eval_pt"],
                         alpha=cfg["stats"]["alpha"])
    best = res["best"]
    # gap 표 (train↔valid, 0.53 기준선 대비) — 보고 필수
    gap_lines = ["## train↔valid gap (과적합 추적, 기존 raw GIN gap≈0.53)",
                 "| 변형 | train macroPR | valid macroPR | gap |", "|---|---|---|---|"]
    for name in valids:
        star = " ★" if name == best else ""
        gap_lines.append(f"| {name}{star} | {train_macros[name]:.3f} | {valids[name]:.3f} | "
                         f"{train_macros[name]-valids[name]:+.3f} |")
    meta = (f"GIN, {label} 변형 비교(손실 고정=focal γ2+sqrt pos_weight). 데이터·split·test·301규칙 v1 동일. "
            f"seed={cfg['seed']}, device={device}. valid 기준 선택 = **{best}**.")
    write_round_summary(res, meta, outdir, label, title, extra_lines=gap_lines)
    json.dump({"valids": valids, "best_ep": best_eps, "train_macros": train_macros,
               "gap": {k: train_macros[k]-valids[k] for k in valids},
               "best": best, "significance": res["sig"]},
              open(os.path.join(outdir, "_round_meta.json"), "w"), ensure_ascii=False, indent=2)
    print(f"[저장] {outdir}/ | best(valid)={res['best']} | Wilcoxon p={res['sig']['wilcoxon_p']:.3g}")
    return res


def main():
    rid = sys.argv[1] if len(sys.argv) > 1 else "1a"
    if rid == "1a":
        run_round("1a", ROUND1A, epochs=150, patience=20, label="1a",
                  title="v2_GNN 개선 Round 1a — (다) 손실/불균형 단독")
    elif rid == "1b":
        run_round("1b", ROUND1B, epochs=200, patience=30, label="1b",
                  title="v2_GNN 개선 Round 1b — (라) 정규화/구조 (손실 고정 focal γ2+sqrt)")
    else:
        raise SystemExit(f"알 수 없는 라운드: {rid}")


if __name__ == "__main__":
    main()
