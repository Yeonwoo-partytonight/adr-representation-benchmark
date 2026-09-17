#!/usr/bin/env python3
"""Arm ② — RDKit 2D descriptor + RandomForest (학습기 고정, 표현 변경).

지시서 `docs/903_kci_repr_learner_separation_prompt_for_vscode.md` §2-C.
심사의견서1 항목 1(표현·학습기 분리) 대응.

설계 고정(변경 금지):
- 데이터·분할 = `data.load_dataset` 로 그대로 로드(재계산·무작위 분할 금지).
- 평가 = `evaluate.per_pt_metrics` / `aggregate` 그대로 재사용, 임계값 0.5.
- 학습기 = `fairtune.py` 의 SPACE 에서 `fp` 축만 제거하고 나머지 유지 → 표현만 바뀐 비교가 성립.
- MultiOutputClassifier 로 370 PT 동시 학습 · 16구성 · SAMPLE_SEED=42 · 검증 macro AP 단독 선택 · 5시드.

표현:
- RDKit 2D descriptor 전량 = `rdkit.Chem.Descriptors.descList`.
- ★ 누수 금지 — ① inf → NaN 치환 ② **train split 중앙값만으로** 대치(valid/test 에 train 통계만 적용)
  ③ train 분산 0 열 제거(제거 열 수·목록 로그).
- 표준화는 train fit → valid/test transform(RF 는 스케일 불변이나 절차를 명시 기록).

실행: .venv/bin/python -u v1_RF/src/repr_desc_rf.py
"""
import os
import sys
import json
import time

import numpy as np
import pandas as pd
import yaml

from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from data import ROOT, load_config, load_dataset       # noqa: E402
from evaluate import per_pt_metrics, aggregate         # noqa: E402

RDLogger.DisableLog("rdApp.*")

OUT = os.path.join(ROOT, "v1_RF", "results_repr")
os.makedirs(OUT, exist_ok=True)

SEEDS = [1, 2, 3, 4, 42]
SAMPLE_SEED = 42       # fairtune 과 동일
N_CONFIGS = 16         # fairtune 동등예산
THR = 0.5

# fairtune.SPACE 에서 `fp` 축만 제거(나머지 값·순서 동일)
SPACE = {
    "n_estimators": [300, 600, 1000],
    "max_depth": [None, 20, 40],
    "max_features": ["sqrt", "log2", 0.1],
    "min_samples_leaf": [1, 2, 5],
    "class_weight": ["balanced", "balanced_subsample", None],
}


def log(msg):
    print(msg, flush=True)


def sample_configs():
    """fairtune.sample_configs 와 동일 방식(고정 seed, 중복 제외)."""
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


def descriptor_matrix(smiles_list):
    """RDKit 2D descriptor 전량 → (N, D) float64 + 이름 목록. 계산 실패 원소는 NaN."""
    names = [n for n, _ in Descriptors.descList]
    funcs = [f for _, f in Descriptors.descList]
    M = np.full((len(smiles_list), len(names)), np.nan, dtype=np.float64)
    n_fail_mol, n_fail_cell = 0, 0
    for i, smi in enumerate(smiles_list):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            n_fail_mol += 1
            continue
        for j, f in enumerate(funcs):
            try:
                M[i, j] = float(f(mol))
            except Exception:
                n_fail_cell += 1
    log(f"[desc] RDKit descList {len(names)}종 → {M.shape} | mol 실패 {n_fail_mol} · 계산 예외 {n_fail_cell}")
    return M, names


def preprocess(M, names, tr, va, te):
    """① inf→NaN ② train 중앙값 대치 ③ train 분산 0 열 제거 ④ train fit 표준화.

    valid/test 에는 train 통계만 적용한다(누수 0).
    """
    prov = {}
    M = M.copy()
    n_inf = int(np.isinf(M).sum())
    M[np.isinf(M)] = np.nan
    prov["n_inf_to_nan"] = n_inf
    prov["n_nan_total_after_inf"] = int(np.isnan(M).sum())
    prov["n_nan_train"] = int(np.isnan(M[tr]).sum())

    # ② train 중앙값만으로 대치
    med = np.nanmedian(M[tr], axis=0)
    all_nan_train = np.isnan(med)
    prov["n_col_all_nan_in_train"] = int(all_nan_train.sum())
    prov["col_all_nan_in_train"] = [names[j] for j in np.where(all_nan_train)[0]]
    med = np.where(all_nan_train, 0.0, med)        # train 전체 NaN 열 → 0 (③에서 분산 0 으로 제거됨)
    idx = np.where(np.isnan(M))
    M[idx] = np.take(med, idx[1])

    # ③ train 분산 0 열 제거
    var_tr = M[tr].var(axis=0)
    keep = var_tr > 0.0
    prov["n_col_before"] = len(names)
    prov["n_col_zero_variance_train"] = int((~keep).sum())
    prov["col_zero_variance_train"] = [names[j] for j in np.where(~keep)[0]]
    M = M[:, keep]
    kept_names = [n for n, k in zip(names, keep) if k]
    prov["n_col_after"] = len(kept_names)
    log(f"[desc] inf→NaN {n_inf} | train 중앙값 대치 후 분산 0 열 {prov['n_col_zero_variance_train']}개 제거 "
        f"→ {prov['n_col_before']} → {prov['n_col_after']}열")
    if prov["col_zero_variance_train"]:
        log(f"[desc] 제거 열: {prov['col_zero_variance_train']}")

    # ③-b 표현범위 초과 열의 순서보존 압축 (float32 한계 대응)
    #
    #   ★ RDKit `Ipc`(특성다항식 계수의 정보량)는 분자 크기에 따라 초지수적으로 커져 본 데이터에서
    #     |max| ≈ 1.2e169 에 이른다(다음으로 큰 descriptor 는 1.7e4). 이는 ① 편차 제곱이 float64
    #     범위를 넘어 분산 계산이 불가하고, ② sklearn 이 내부적으로 X 를 float32(최대 3.4e38)로
    #     캐스팅하므로 RF 학습 자체가 불가능하다.
    #     열을 버리면 심사위원이 요구한 "RDKit descriptor 전량" 표현이 훼손되므로, 대신
    #     **부호보존 log1p** (`sign(x)·log1p(|x|)`) 를 적용한다. 이는 전 실수에서 **순증가 함수**라
    #     RF 의 분할 기준(순서 비교)이 전혀 바뀌지 않는다 — 즉 표현범위만 압축할 뿐 모델은 동일하다.
    #     고정 함수이므로 train 통계에 의존하지 않아 누수도 없다(적용 대상 판정만 train 으로 한다).
    F32MAX = float(np.finfo(np.float32).max)
    over = np.abs(M[tr]).max(axis=0) > F32MAX
    prov["n_col_log1p_compressed"] = int(over.sum())
    prov["col_log1p_compressed"] = [kept_names[j] for j in np.where(over)[0]]
    if over.any():
        cols = np.where(over)[0]
        M[:, cols] = np.sign(M[:, cols]) * np.log1p(np.abs(M[:, cols]))
        log(f"[desc] float32 표현범위 초과 열 {int(over.sum())}개 = {prov['col_log1p_compressed']} "
            f"→ 부호보존 log1p 적용(순증가 변환, RF 분할 기준 불변)")

    # ④ 표준화: train fit → 전 split transform (train 통계만 사용)
    mean = M[tr].mean(axis=0)
    std = M[tr].std(axis=0)
    assert np.isfinite(mean).all() and np.isfinite(std).all() and (std > 0).all(), \
        "표준화 통계 비정상 — 전처리 순서 확인 필요"
    Z = (M - mean) / std
    prov["scaler"] = "train fit(mean/std) → valid/test transform (train 통계만)"
    assert np.isfinite(Z).all(), "전처리 후 NaN/inf 잔존"
    assert np.abs(Z).max() < F32MAX, "전처리 후 float32 표현범위 초과"
    return Z, kept_names, prov


def rf_proba(params, Xtr, Ytr, Xev, seed):
    """fairtune.rf_proba 와 동일 구조(MultiOutput RF → 양성확률)."""
    clf = MultiOutputClassifier(RandomForestClassifier(
        n_estimators=params["n_estimators"], max_depth=params["max_depth"],
        max_features=params["max_features"], min_samples_leaf=params["min_samples_leaf"],
        class_weight=params["class_weight"], n_jobs=-1, random_state=seed))
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xev.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xev)[:, cls.index(1)]
    return P


def main():
    t_start = time.time()
    cfg = load_config()
    X, Y, ycols, masks = load_dataset(cfg, log=log)
    tr, va, te = masks["train"], masks["valid"], masks["test"]
    Ytr, Yva, Yte = Y[tr], Y[va], Y[te]

    M, names = descriptor_matrix(X["smiles_canonical"].tolist())
    Z, kept_names, prov = preprocess(M, names, tr, va, te)
    json.dump({**prov, "kept_columns": kept_names},
              open(os.path.join(OUT, "descriptor_preprocess.json"), "w"), indent=2, ensure_ascii=False)
    Xtr, Xva, Xte = Z[tr], Z[va], Z[te]
    log(f"[arm2] X {Z.shape} | train {tr.sum()} valid {va.sum()} test {te.sum()} | n_out {len(ycols)}")

    search_path = os.path.join(OUT, "search_log_descrf.csv")
    best_path = os.path.join(OUT, "best_config_descrf.yaml")

    # ── STEP 1: 16구성 탐색 (seed 42 · 검증 macro AP 로만 선택) ────────────────
    if os.path.exists(search_path) and os.path.exists(best_path):
        search = pd.read_csv(search_path)
        bc = yaml.safe_load(open(best_path))["config"]
        best = {k: bc[k] for k in SPACE}
        log(f"[search] 기존 결과 재사용 — best config_id={int(search.iloc[0]['config_id'])}")
    else:
        configs = sample_configs()
        log(f"[search] 동등예산 {len(configs)}개 구성 (sample_seed={SAMPLE_SEED}) — 검증 macro AP 로만 선택")
        rows = []
        for i, c in enumerate(configs):
            t0 = time.time()
            P_va = rf_proba(c, Xtr, Ytr, Xva, seed=42)
            dfv = per_pt_metrics(Yva, P_va, ycols, THR)
            aggv = aggregate(Yva, P_va, dfv, THR)
            rows.append({"config_id": i, **{k: str(c[k]) for k in SPACE},
                         "valid_macro_ap": aggv["macro_pr_auc"], "valid_micro_ap": aggv["micro_pr_auc"],
                         "seconds": round(time.time() - t0, 1)})
            log(f"  [cfg {i:2d}] valid macroAP {aggv['macro_pr_auc']:.4f} microAP {aggv['micro_pr_auc']:.4f} | "
                f"n_est={c['n_estimators']} depth={c['max_depth']} feat={c['max_features']} "
                f"leaf={c['min_samples_leaf']} cw={c['class_weight']} ({time.time()-t0:.0f}s)")
        search = pd.DataFrame(rows).sort_values("valid_macro_ap", ascending=False).reset_index(drop=True)
        search.to_csv(search_path, index=False)
        best_id = int(search.iloc[0]["config_id"])
        best = configs[best_id]
        log(f"[select] 검증 최적 config_id={best_id} | valid macroAP {search.iloc[0]['valid_macro_ap']:.4f} (test 미사용)")
        yaml.safe_dump({"arm": "rdkit_descriptor_rf", "selected_by": "valid_macro_ap",
                        "config": {k: best[k] for k in SPACE},
                        "representation": {"source": "rdkit.Chem.Descriptors.descList",
                                           "n_descriptors_raw": prov["n_col_before"],
                                           "n_descriptors_used": prov["n_col_after"],
                                           "nan_policy": "inf→NaN → train median impute (train 통계만)",
                                           "zero_variance_dropped": prov["n_col_zero_variance_train"],
                                           "log1p_compressed": prov["col_log1p_compressed"],
                                           "scaler": prov["scaler"]},
                        "valid_macro_ap": float(search.iloc[0]["valid_macro_ap"]),
                        "search_budget": len(configs), "sample_seed": SAMPLE_SEED},
                       open(best_path, "w"), sort_keys=False, allow_unicode=True)

    # ── STEP 2: best config 5시드 재학습 → test ────────────────────────────────
    perpt_path = os.path.join(OUT, "perpt_descrf_seed42.csv")
    for seed in SEEDS:
        sp = os.path.join(OUT, f"seed_{seed}_descrf.csv")
        if os.path.exists(sp) and (seed != 42 or os.path.exists(perpt_path)):
            log(f"[seed {seed}] 기존 seed_{seed}_descrf.csv 재사용")
            continue
        t0 = time.time()
        P_te = rf_proba(best, Xtr, Ytr, Xte, seed=seed)
        df = per_pt_metrics(Yte, P_te, ycols, THR)
        agg = aggregate(Yte, P_te, df, THR)
        pd.DataFrame([{"seed": seed, "descrf_macro": agg["macro_pr_auc"], "descrf_micro": agg["micro_pr_auc"],
                       "macro_roc": agg["macro_roc_auc"], "hamming": agg["hamming_accuracy"],
                       "n_pt_evaluated": agg["n_pt_evaluated"]}]).to_csv(sp, index=False)
        log(f"[seed {seed}] test macroAP {agg['macro_pr_auc']:.4f} microAP {agg['micro_pr_auc']:.4f} "
            f"| n_pt {agg['n_pt_evaluated']} ({time.time()-t0:.0f}s)")
        if seed == 42:
            df[["meddra_pt", "n_pos_test", "pr_auc"]].to_csv(perpt_path, index=False)
            np.savez_compressed(os.path.join(OUT, "_preds_descrf_seed42.npz"),
                                P=P_te.astype(np.float32), Yte=Yte.astype(np.int8),
                                ycols=np.array(ycols))

    d = pd.concat([pd.read_csv(os.path.join(OUT, f"seed_{s}_descrf.csv")) for s in SEEDS], ignore_index=True)
    log(f"[arm2] macro {d['descrf_macro'].mean():.4f} ± {d['descrf_macro'].std(ddof=1):.4f} | "
        f"micro {d['descrf_micro'].mean():.4f} ± {d['descrf_micro'].std(ddof=1):.4f} "
        f"({(time.time()-t_start)/60:.1f}분)")


if __name__ == "__main__":
    main()
