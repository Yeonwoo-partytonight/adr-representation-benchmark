#!/usr/bin/env python3
"""STEP D — 학습 (v2_GNN).

명세 docs/09_v2_gnn_spec.md §3 STEP D.
- 손실: BCEWithLogitsLoss(pos_weight=라벨별 neg/pos) 기본 + Focal Loss 옵션(config 토글).
- Adam, valid macro PR-AUC 로 early stopping + best 체크포인트.
- 3종(GCN/GIN/GAT) 동일 예산 학습 + ablation(최적 conv 의 pool=add) 1건.
- 전역 SEED=42(torch/numpy/random). MPS 사용(PYTORCH_ENABLE_MPS_FALLBACK 권장).
- test 예측확률 + valid 점수 + 메타를 results/_preds_v2.npz / _train_meta_v2.json 로 저장.

★ 모델 선택은 valid macro PR-AUC 로만(테스트로 고르지 않음 — leakage 방지).
실행: PYTORCH_ENABLE_MPS_FALLBACK=1 python v2_GNN/src/train.py
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # torch import 전에 설정
import json
import random
import numpy as np
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader
from sklearn.metrics import average_precision_score

from data import ROOT, load_config, build_graphs
from graph_features import ATOM_FDIM
from models import build_model

RESULTS = os.path.join(ROOT, "v2_GNN", "results")
os.makedirs(RESULTS, exist_ok=True)


def set_seed(seed):
    random.seed(seed); np.random.seed(seed)
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    try:
        torch.mps.manual_seed(seed)
    except Exception:
        pass


def get_device(cfg):
    d = cfg["device"]
    if d == "auto":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(d)


def compute_pos_weight(graphs_train, n_out):
    Y = np.stack([g.y.numpy().ravel() for g in graphs_train])   # [n_train, 370]
    pos = Y.sum(0)
    neg = Y.shape[0] - pos
    pw = np.ones(n_out, dtype=np.float32)
    nz = pos > 0
    pw[nz] = (neg[nz] / pos[nz]).astype(np.float32)
    return torch.tensor(pw)


class FocalLoss(nn.Module):
    """멀티라벨 focal loss(logits). pos_weight 동시 적용 가능."""
    def __init__(self, gamma=2.0, pos_weight=None):
        super().__init__()
        self.gamma = gamma
        self.pos_weight = pos_weight

    def forward(self, logits, target):
        bce = nn.functional.binary_cross_entropy_with_logits(
            logits, target, pos_weight=self.pos_weight, reduction="none")
        p = torch.sigmoid(logits)
        pt = torch.where(target == 1, p, 1 - p)
        return ((1 - pt) ** self.gamma * bce).mean()


@torch.no_grad()
def predict_proba(model, loader, device, n_out):
    model.eval()
    ps, ys = [], []
    for batch in loader:
        batch = batch.to(device)
        logits = model(batch)
        ps.append(torch.sigmoid(logits).float().cpu().numpy())
        ys.append(batch.y.view(-1, n_out).cpu().numpy())
    return np.concatenate(ps), np.concatenate(ys)


def macro_pr_auc(Y, P):
    """양성>0 라벨만 평균(평가 프로토콜과 동일 정신)."""
    aps = [average_precision_score(Y[:, j], P[:, j])
           for j in range(Y.shape[1]) if Y[:, j].sum() > 0]
    return float(np.mean(aps)) if aps else float("nan")


def train_one(cfg, data, device, conv_type, pool, log=print):
    n_out = len(data["ycols"])
    set_seed(cfg["seed"])                         # 변형마다 동일 초기화 예산
    tr = DataLoader(data["graphs"]["train"], batch_size=cfg["train"]["batch_size"], shuffle=True)
    va = DataLoader(data["graphs"]["valid"], batch_size=cfg["train"]["batch_size"])
    te = DataLoader(data["graphs"]["test"], batch_size=cfg["train"]["batch_size"])

    model = build_model(cfg, ATOM_FDIM, n_out, conv_type=conv_type, pool=pool).to(device)
    pw = compute_pos_weight(data["graphs"]["train"], n_out).to(device) if cfg["train"]["pos_weight"] else None
    if cfg["train"]["loss"] == "focal":
        criterion = FocalLoss(gamma=cfg["train"]["focal_gamma"], pos_weight=pw)
    else:
        criterion = nn.BCEWithLogitsLoss(pos_weight=pw)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["train"]["lr"],
                           weight_decay=cfg["train"]["weight_decay"])

    best_valid, best_state, best_epoch, patience = -1.0, None, 0, 0
    tag = f"{conv_type}/{pool}"
    for epoch in range(1, cfg["train"]["epochs"] + 1):
        model.train()
        tot = 0.0
        for batch in tr:
            batch = batch.to(device)
            opt.zero_grad()
            loss = criterion(model(batch), batch.y.view(-1, n_out))
            loss.backward(); opt.step()
            tot += float(loss) * batch.num_graphs
        Pva, Yva = predict_proba(model, va, device, n_out)
        vscore = macro_pr_auc(Yva, Pva)
        if vscore > best_valid:
            best_valid, best_epoch = vscore, epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
        if epoch % 10 == 0 or epoch == 1:
            log(f"[{tag}] epoch {epoch:3d} | train loss {tot/len(data['graphs']['train']):.4f} "
                f"| valid macroPR {vscore:.4f} | best {best_valid:.4f}@{best_epoch}")
        if patience >= cfg["train"]["early_stop_patience"]:
            log(f"[{tag}] early stop @ epoch {epoch} (best valid macroPR {best_valid:.4f}@{best_epoch})")
            break

    model.load_state_dict(best_state)
    Pte, Yte = predict_proba(model, te, device, n_out)
    torch.save(best_state, os.path.join(RESULTS, f"best_{conv_type}_{pool}.pt"))
    return {"valid_macro_pr_auc": best_valid, "best_epoch": best_epoch,
            "P_test": Pte.astype(np.float32), "Yte": Yte.astype(np.int8)}


def main():
    cfg = load_config()
    set_seed(cfg["seed"])
    device = get_device(cfg)
    print(f"[env] device={device} | seed={cfg['seed']} | loss={cfg['train']['loss']} "
          f"| fallback={os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK')}")
    data = build_graphs(cfg)
    n_out = len(data["ycols"])

    runs = {}          # key → result
    valids = {}
    # 3종 conv (pool=mean 통제)
    for conv in cfg["model"]["convs"]:
        key = conv.upper()
        print(f"=== 학습 {key} (pool={cfg['model']['pool']}) ===")
        runs[key] = train_one(cfg, data, device, conv, cfg["model"]["pool"])
        valids[key] = runs[key]["valid_macro_pr_auc"]
        print(f"  {key}: valid macroPR {valids[key]:.4f}")

    # valid 기준 최적 conv 선택 (★ test 로 선택 금지)
    best_conv = max(valids, key=valids.get)
    print(f"[선택] valid 기준 최적 conv = {best_conv} (valid macroPR {valids[best_conv]:.4f})")

    # ablation: 최적 conv 에 pool=add 1건
    if cfg["ablation"]["run_pooling"] and cfg["ablation"]["pooling_variant"] != cfg["model"]["pool"]:
        pv = cfg["ablation"]["pooling_variant"]
        key = f"{best_conv}_{pv}pool"
        print(f"=== ablation {key} ===")
        runs[key] = train_one(cfg, data, device, best_conv.lower(), pv)
        valids[key] = runs[key]["valid_macro_pr_auc"]

    # 저장: test 예측 + valid 점수 + 메타
    Yte = runs[best_conv]["Yte"]
    np.savez_compressed(
        os.path.join(RESULTS, "_preds_v2.npz"),
        Yte=Yte,
        ycols=np.array(data["ycols"]),
        models=np.array(list(runs.keys())),
        valids=np.array([valids[k] for k in runs.keys()], dtype=np.float32),
        best_by_valid=np.array(best_conv),
        **{f"P_{k}": runs[k]["P_test"] for k in runs.keys()},
    )
    with open(os.path.join(RESULTS, "_train_meta_v2.json"), "w") as f:
        json.dump({
            "seed": cfg["seed"], "device": str(device), "loss": cfg["train"]["loss"],
            "convs": cfg["model"]["convs"], "hidden": cfg["model"]["hidden"],
            "n_layers": cfg["model"]["n_layers"], "pool": cfg["model"]["pool"],
            "n_failed_graph": data["n_failed"],
            "valid_macro_pr_auc": {k: float(valids[k]) for k in runs.keys()},
            "best_by_valid": best_conv,
            "best_epoch": {k: int(runs[k]["best_epoch"]) for k in runs.keys()},
        }, f, ensure_ascii=False, indent=2)
    print(f"[저장] _preds_v2.npz | 변형 {list(runs.keys())} | best(valid)={best_conv}")


if __name__ == "__main__":
    main()
