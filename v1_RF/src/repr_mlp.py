#!/usr/bin/env python3
"""Arm ① — Morgan 지문 + MLP (표현 고정, 학습기 변경).

지시서 `docs/903_kci_repr_learner_separation_prompt_for_vscode.md` §2-B.
심사의견서1 항목 1(표현·학습기 분리) 대응.

설계 고정(변경 금지):
- 표현 = Morgan r=2 / 2,048비트 — `features.morgan_matrix` 그대로(디폴트 RF와 동일 설정).
- 데이터·분할 = `data.load_dataset` 로 그대로 로드(재계산·무작위 분할 금지).
- 평가 = `evaluate.per_pt_metrics` / `aggregate` 그대로 재사용, 임계값 0.5.
- 시드 [1,2,3,4,42]. 모델 선택은 **검증 macro AP 단독**(test 는 선택·early stopping 에 일절 미사용).

A_wd 레시피 준수 — v2_GNN 산출물과 "표현만" 다르게 하기 위한 핵심 제약:
- 손실 = v2_GNN/src/train.py 의 `FocalLoss`(γ=2.0) + pos_weight = sqrt(neg/pos)
  (= train_improve.make_pos_weight(mode="sqrt") 산식). 두 정의 모두 v2 소스에서 직접 import 한다.
- 최적화 = Adam, weight_decay 1e-4 / epochs 200 / patience 30
- early stopping 기준 = 검증 macro AP
- 출력층 = 370 로짓(전 PT 동시 학습)
- ★ sklearn MLPClassifier 사용 금지(초점 손실·클래스 가중 부재 → "표현만 바꿨다"가 성립하지 않음).

실행: .venv/bin/python -u v1_RF/src/repr_mlp.py
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import sys
import json
import time
import importlib.util

import numpy as np
import pandas as pd
import yaml
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
V2SRC = os.path.join(ROOT_DIR, "v2_GNN", "src")


def _load_v2_train():
    """v2_GNN/src/train.py 의 FocalLoss·set_seed·get_device·macro_pr_auc 를 원본에서 직접 로드.

    v2 의 train.py 는 `from data import ...` 처럼 평문 모듈명을 쓰므로, v1_RF/src 의 동명
    모듈과 충돌하지 않도록 v2 의존 모듈을 먼저 적재한 뒤 곧바로 sys.modules 에서 제거한다.
    (v2 소스를 복사하지 않고 그대로 재사용 — 레시피 동일성이 코드 수준에서 보장된다.)
    """
    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        return m

    for n in ("graph_features", "models", "data"):
        _load(n, os.path.join(V2SRC, f"{n}.py"))
    v2t = _load("v2_train", os.path.join(V2SRC, "train.py"))
    for n in ("graph_features", "models", "data", "v2_train"):
        sys.modules.pop(n, None)
    assert os.path.abspath(v2t.__file__) == os.path.join(V2SRC, "train.py")
    return v2t


V2 = _load_v2_train()
FocalLoss, set_seed, macro_pr_auc = V2.FocalLoss, V2.set_seed, V2.macro_pr_auc

sys.path.insert(0, HERE)
from data import load_config, load_dataset          # noqa: E402  (v1_RF/src)
from features import morgan_matrix                  # noqa: E402
from evaluate import per_pt_metrics, aggregate      # noqa: E402

OUT = os.path.join(ROOT_DIR, "v1_RF", "results_repr")
os.makedirs(OUT, exist_ok=True)

SEEDS = [1, 2, 3, 4, 42]
SAMPLE_SEED = 42          # RandomizedSearch 샘플링 고정 (fairtune 과 동일)
N_CONFIGS = 16            # fairtune 동등예산
THR = 0.5                 # v1·v2 평가 임계값
EPOCHS = 200              # A_wd 레시피
PATIENCE = 30             # A_wd 레시피
WEIGHT_DECAY = 1e-4       # A_wd 레시피
FOCAL_GAMMA = 2.0         # A_wd 레시피
FP_RADIUS, FP_BITS = 2, 2048   # 디폴트 RF 와 동일 표현

SPACE = {
    "hidden_dims": [(512,), (1024,), (512, 256), (1024, 512), (2048, 512)],
    "dropout": [0.2, 0.4, 0.5],
    "lr": [1e-3, 5e-4, 1e-4],
    "batch_size": [32, 64, 128],
}


def log(msg):
    print(msg, flush=True)


def sample_configs():
    """탐색공간에서 중복 없이 N_CONFIGS 개 구성 샘플(고정 seed) — fairtune.sample_configs 와 동일 방식."""
    rng = np.random.default_rng(SAMPLE_SEED)
    keys = list(SPACE.keys())
    seen, configs = set(), []
    guard = 0
    while len(configs) < N_CONFIGS and guard < 100000:
        guard += 1
        c = {k: SPACE[k][int(rng.integers(len(SPACE[k])))] for k in keys}
        sig = tuple((k, c[k]) for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        configs.append(c)
    return configs


def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def sqrt_pos_weight(Ytr, n_out):
    """train 라벨만으로 pos_weight = sqrt(neg/pos). 양성 0 라벨은 1.0.

    v2_GNN compute_pos_weight(neg/pos, pos==0 → 1.0) + make_pos_weight(mode="sqrt") 와 동일 산식.
    """
    pos = Ytr.sum(axis=0).astype(np.float64)
    neg = Ytr.shape[0] - pos
    pw = np.ones(n_out, dtype=np.float32)
    nz = pos > 0
    pw[nz] = (neg[nz] / pos[nz]).astype(np.float32)
    return torch.sqrt(torch.tensor(pw))


class MLP(nn.Module):
    """Morgan 비트 → 은닉층 스택 → 370 로짓(전 PT 동시 출력)."""

    def __init__(self, in_dim, hidden_dims, n_out, dropout):
        super().__init__()
        layers, d = [], in_dim
        for h in hidden_dims:
            layers += [nn.Linear(d, h), nn.ReLU(), nn.Dropout(dropout)]
            d = h
        layers.append(nn.Linear(d, n_out))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


@torch.no_grad()
def predict(model, X, device, batch_size=256):
    model.eval()
    out = []
    for i in range(0, X.shape[0], batch_size):
        xb = torch.from_numpy(X[i:i + batch_size]).float().to(device)
        out.append(torch.sigmoid(model(xb)).float().cpu().numpy())
    return np.concatenate(out)


def train_one(cfg_params, Xtr, Ytr, Xva, Yva, seed, device, tag=""):
    """A_wd 레시피로 1회 학습. best = 검증 macro AP 최댓값 시점 state."""
    set_seed(seed)
    n_out = Ytr.shape[1]
    model = MLP(Xtr.shape[1], cfg_params["hidden_dims"], n_out, cfg_params["dropout"]).to(device)
    pw = sqrt_pos_weight(Ytr, n_out).to(device)
    criterion = FocalLoss(gamma=FOCAL_GAMMA, pos_weight=pw)
    opt = torch.optim.Adam(model.parameters(), lr=cfg_params["lr"], weight_decay=WEIGHT_DECAY)

    Xtr_t = torch.from_numpy(Xtr).float().to(device)
    Ytr_t = torch.from_numpy(Ytr).float().to(device)
    n = Xtr_t.shape[0]
    bs = cfg_params["batch_size"]
    g = torch.Generator().manual_seed(seed)

    best_v, best_state, best_ep, wait = -1.0, None, 0, 0
    for ep in range(1, EPOCHS + 1):
        model.train()
        perm = torch.randperm(n, generator=g)
        for i in range(0, n, bs):
            idx = perm[i:i + bs].to(device)
            opt.zero_grad()
            loss = criterion(model(Xtr_t[idx]), Ytr_t[idx])
            loss.backward()
            opt.step()
        vmac = macro_pr_auc(Yva, predict(model, Xva, device))     # ★ 검증 macro AP 단독
        if vmac > best_v:
            best_v, best_ep, wait = vmac, ep, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
        if ep % 50 == 0:
            log(f"    [{tag}] ep {ep:3d} validMacro {vmac:.4f} best {best_v:.4f}@{best_ep}")
        if wait >= PATIENCE:
            log(f"    [{tag}] early stop @ep{ep} (best {best_v:.4f}@{best_ep})")
            break
    model.load_state_dict(best_state)
    return model, best_v, best_ep


def main():
    t_start = time.time()
    cfg = load_config()
    X, Y, ycols, masks = load_dataset(cfg, log=log)
    M, failed = morgan_matrix(X["smiles_canonical"].tolist(), FP_RADIUS, FP_BITS, log=log)
    tr, va, te = masks["train"], masks["valid"], masks["test"]
    Xtr, Xva, Xte = M[tr].astype(np.float32), M[va].astype(np.float32), M[te].astype(np.float32)
    Ytr, Yva, Yte = Y[tr], Y[va], Y[te]
    device = get_device()
    log(f"[arm1] device={device} | X {M.shape} | train {tr.sum()} valid {va.sum()} test {te.sum()} "
        f"| n_out {len(ycols)}")

    search_path = os.path.join(OUT, "search_log_mlp.csv")
    best_path = os.path.join(OUT, "best_config_mlp.yaml")

    # ── STEP 1: 16구성 탐색 (seed 42 학습 · 검증 macro AP 로만 선택) ─────────────
    if os.path.exists(search_path) and os.path.exists(best_path):
        search = pd.read_csv(search_path)
        bc = yaml.safe_load(open(best_path))["config"]
        best = {"hidden_dims": tuple(bc["hidden_dims"]), "dropout": bc["dropout"],
                "lr": bc["lr"], "batch_size": bc["batch_size"]}
        log(f"[search] 기존 결과 재사용 — best config_id={int(search.iloc[0]['config_id'])}")
    else:
        configs = sample_configs()
        log(f"[search] 동등예산 {len(configs)}개 구성 (sample_seed={SAMPLE_SEED}) — 검증 macro AP 로만 선택")
        rows = []
        for i, c in enumerate(configs):
            t0 = time.time()
            _, vmac, bep = train_one(c, Xtr, Ytr, Xva, Yva, seed=42, device=device, tag=f"cfg{i:02d}")
            rows.append({"config_id": i, "hidden_dims": str(c["hidden_dims"]), "dropout": c["dropout"],
                         "lr": c["lr"], "batch_size": c["batch_size"],
                         "valid_macro_ap": vmac, "best_epoch": bep, "seconds": round(time.time() - t0, 1)})
            log(f"  [cfg {i:2d}] valid macroAP {vmac:.4f} @ep{bep} | hidden={c['hidden_dims']} "
                f"drop={c['dropout']} lr={c['lr']} bs={c['batch_size']} ({time.time()-t0:.0f}s)")
        search = pd.DataFrame(rows).sort_values("valid_macro_ap", ascending=False).reset_index(drop=True)
        search.to_csv(search_path, index=False)
        best_id = int(search.iloc[0]["config_id"])
        best = configs[best_id]
        log(f"[select] 검증 최적 config_id={best_id} | valid macroAP {search.iloc[0]['valid_macro_ap']:.4f} (test 미사용)")
        yaml.safe_dump({"arm": "morgan_mlp", "selected_by": "valid_macro_ap",
                        "config": {"hidden_dims": list(best["hidden_dims"]), "dropout": best["dropout"],
                                   "lr": best["lr"], "batch_size": best["batch_size"]},
                        "recipe": {"loss": "FocalLoss(gamma=2.0)", "pos_weight": "sqrt(neg/pos)",
                                   "optimizer": "Adam", "weight_decay": WEIGHT_DECAY,
                                   "epochs": EPOCHS, "patience": PATIENCE,
                                   "early_stopping_metric": "valid_macro_ap",
                                   "representation": f"Morgan r={FP_RADIUS}/{FP_BITS}bit"},
                        "valid_macro_ap": float(search.iloc[0]["valid_macro_ap"]),
                        "search_budget": len(configs), "sample_seed": SAMPLE_SEED},
                       open(best_path, "w"), sort_keys=False, allow_unicode=True)

    # ── STEP 2: best config 5시드 재학습 → test ────────────────────────────────
    perpt_path = os.path.join(OUT, "perpt_mlp_seed42.csv")
    for seed in SEEDS:
        sp = os.path.join(OUT, f"seed_{seed}_mlp.csv")
        if os.path.exists(sp) and (seed != 42 or os.path.exists(perpt_path)):
            log(f"[seed {seed}] 기존 seed_{seed}_mlp.csv 재사용")
            continue
        model, vmac, bep = train_one(best, Xtr, Ytr, Xva, Yva, seed=seed, device=device, tag=f"seed{seed}")
        P_te = predict(model, Xte, device)
        df = per_pt_metrics(Yte, P_te, ycols, THR)
        agg = aggregate(Yte, P_te, df, THR)
        pd.DataFrame([{"seed": seed, "mlp_macro": agg["macro_pr_auc"], "mlp_micro": agg["micro_pr_auc"],
                       "macro_roc": agg["macro_roc_auc"], "hamming": agg["hamming_accuracy"],
                       "n_pt_evaluated": agg["n_pt_evaluated"], "valid_macro_ap": vmac,
                       "best_epoch": bep}]).to_csv(sp, index=False)
        log(f"[seed {seed}] test macroAP {agg['macro_pr_auc']:.4f} microAP {agg['micro_pr_auc']:.4f} "
            f"| n_pt {agg['n_pt_evaluated']} | valid {vmac:.4f}@ep{bep}")
        if seed == 42:
            df[["meddra_pt", "n_pos_test", "pr_auc"]].to_csv(perpt_path, index=False)
            np.savez_compressed(os.path.join(OUT, "_preds_mlp_seed42.npz"),
                                P=P_te.astype(np.float32), Yte=Yte.astype(np.int8),
                                ycols=np.array(ycols))

    d = pd.concat([pd.read_csv(os.path.join(OUT, f"seed_{s}_mlp.csv")) for s in SEEDS], ignore_index=True)
    log(f"[arm1] macro {d['mlp_macro'].mean():.4f} ± {d['mlp_macro'].std(ddof=1):.4f} | "
        f"micro {d['mlp_micro'].mean():.4f} ± {d['mlp_micro'].std(ddof=1):.4f} "
        f"({(time.time()-t_start)/60:.1f}분)")


if __name__ == "__main__":
    main()
