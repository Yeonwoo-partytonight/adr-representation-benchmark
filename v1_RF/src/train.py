#!/usr/bin/env python3
"""STEP C — 학습 (v1_RF).

명세 docs/08_v1_rf_spec.md §2 STEP C.
- 멀티라벨(370 타깃) 분류. 두 모델:
  - RandomForest: MultiOutputClassifier(RandomForestClassifier) — 멀티라벨 native.
    class_weight="balanced_subsample" 로 불균형 보정.
  - XGBoost: 라벨 루프(OvR). 라벨별 scale_pos_weight = neg/pos 로 불균형 보정.
- 전역 SEED=42. valid 로 가벼운 점검(과한 튜닝 금지 — 빠른 사이클 우선).
- test 예측확률 + 메타를 results/_preds.npz 로 저장 → evaluate.py 가 소비.

실행: python v1_RF/src/train.py   (프로젝트 루트 또는 src 어디서든)
"""
import os
import json
import numpy as np

from data import HERE, ROOT, load_config, load_dataset
from features import morgan_matrix

from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import average_precision_score

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
    XGB_ERR = None
except Exception as e:  # libomp 미설치 등
    HAS_XGB = False
    XGB_ERR = f"{type(e).__name__}: {e}"

RESULTS = os.path.join(ROOT, "v1_RF", "results")
os.makedirs(RESULTS, exist_ok=True)


def _proba_from_multioutput(model, X, n_labels):
    """MultiOutputClassifier → (n, n_labels) 양성확률. 단일클래스 학습 라벨은 0."""
    P = np.zeros((X.shape[0], n_labels), dtype=np.float32)
    for j, est in enumerate(model.estimators_):
        classes = list(est.classes_)
        if 1 in classes:
            P[:, j] = est.predict_proba(X)[:, classes.index(1)]
    return P


def train_random_forest(Xtr, Ytr, Xte, cfg, seed, log=print):
    params = dict(cfg["models"]["random_forest"])
    log(f"[train] RandomForest {params}")
    clf = MultiOutputClassifier(RandomForestClassifier(random_state=seed, **params))
    clf.fit(Xtr, Ytr)
    return _proba_from_multioutput(clf, Xte, Ytr.shape[1])


def train_xgboost(Xtr, Ytr, Xte, cfg, seed, log=print):
    """라벨 루프 OvR. 라벨별 scale_pos_weight = neg/pos 로 불균형 보정.

    양성 0 라벨은 학습 불가 → 예측확률 0 (test 평가에서도 정의 불가로 제외됨).
    """
    params = dict(cfg["models"]["xgboost"])
    n_labels = Ytr.shape[1]
    P = np.zeros((Xte.shape[0], n_labels), dtype=np.float32)
    n_trained = 0
    for j in range(n_labels):
        yj = Ytr[:, j]
        pos = int(yj.sum())
        if pos == 0:
            continue  # 학습 데이터 양성 없음 → 0 확률
        neg = len(yj) - pos
        spw = (neg / pos) if pos > 0 else 1.0
        clf = XGBClassifier(
            random_state=seed, eval_metric="logloss", tree_method="hist",
            scale_pos_weight=spw, **params,
        )
        clf.fit(Xtr, yj)
        P[:, j] = clf.predict_proba(Xte)[:, list(clf.classes_).index(1)]
        n_trained += 1
    log(f"[train] XGBoost OvR 라벨 {n_trained}/{n_labels} 학습(양성>0), 라벨별 scale_pos_weight 적용")
    return P


def quick_valid_check(name, P_va, Yva, log=print):
    """valid 가벼운 점검 — micro PR-AUC 만 로깅(튜닝 아님)."""
    micro = average_precision_score(Yva.ravel(), P_va.ravel())
    log(f"[valid] {name} micro PR-AUC(점검용) {micro:.4f}")


def main():
    cfg = load_config()
    seed = cfg["seed"]
    np.random.seed(seed)

    X, Y, ycols, masks = load_dataset(cfg)
    fp = cfg["fingerprint"]
    M, failed = morgan_matrix(X["smiles_canonical"].tolist(), fp["radius"], fp["n_bits"])

    tr, va, te = masks["train"], masks["valid"], masks["test"]
    Xtr, Xva, Xte = M[tr], M[va], M[te]
    Ytr, Yva, Yte = Y[tr], Y[va], Y[te]

    if not HAS_XGB:
        print(f"[경고] XGBoost 미사용: {XGB_ERR}. RandomForest 만 실행. "
              f"Mac 이면 `brew install libomp` 후 재실행.")

    preds = {}
    # --- RandomForest ---
    P_rf_te = train_random_forest(Xtr, Ytr, Xte, cfg, seed)
    P_rf_va = train_random_forest(Xtr, Ytr, Xva, cfg, seed)
    quick_valid_check("RandomForest", P_rf_va, Yva)
    preds["RandomForest"] = P_rf_te

    # --- XGBoost ---
    if HAS_XGB:
        P_xgb_te = train_xgboost(Xtr, Ytr, Xte, cfg, seed)
        P_xgb_va = train_xgboost(Xtr, Ytr, Xva, cfg, seed)
        quick_valid_check("XGBoost", P_xgb_va, Yva)
        preds["XGBoost"] = P_xgb_te

    # test 예측 + 메타 저장 → evaluate.py 소비 (results/*.npz: 중간물, git 미커밋)
    out = os.path.join(RESULTS, "_preds.npz")
    np.savez_compressed(
        out,
        Yte=Yte.astype(np.int8),
        ycols=np.array(ycols),
        models=np.array(list(preds.keys())),
        **{f"P_{k}": v for k, v in preds.items()},
    )
    # train 양성 수(라벨별)도 메타로 — 보고용
    with open(os.path.join(RESULTS, "_train_meta.json"), "w") as f:
        json.dump({
            "seed": seed, "n_train": int(tr.sum()), "n_valid": int(va.sum()),
            "n_test": int(te.sum()), "n_pt": len(ycols),
            "fp_radius": fp["radius"], "fp_bits": fp["n_bits"],
            "n_failed_mol": len(failed), "has_xgb": HAS_XGB,
        }, f, ensure_ascii=False, indent=2)
    print(f"[저장] {out} (모델: {list(preds.keys())})")


if __name__ == "__main__":
    main()
