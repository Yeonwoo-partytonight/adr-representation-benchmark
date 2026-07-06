#!/usr/bin/env python3
"""데이터 스케일링(learning curve) 분석 — v1 RF vs v2 GNN.

목적(리뷰어 반박 대응): "RF>GNN 결과가 단지 데이터셋이 작아서(=데이터 부족) 생긴 것 아니냐"에 답한다.
train(873분자)을 {20,40,60,80,100}% 로 stratified subsample 하며 두 모델의 test 성능 곡선을 그려,
GNN 곡선이 아직 상승 중(=데이터 더 필요)인지 vs 평탄화(=RF 우위가 데이터 양 문제 아님)인지 판단한다.

설계(기존 코드/전처리/split 그대로 재사용 — 새 파이프라인 없음):
- 데이터·split: data/processed 의 master_X/Y + scaffold_split.json (재계산 금지).
- RF = v1 설정 그대로: Morgan(ECFP4, r2/2048) + MultiOutputClassifier(RandomForest,
  n_estimators 300, max_depth None, class_weight balanced_subsample, random_state=seed).
- GNN = v2 best(GCN/GIN/GAT 중 valid 최고 = GIN) + 동등예산 공정성 보정 조건 그대로:
  robustness.py 의 A_wd (GIN, focal γ2 + sqrt pos_weight + weight_decay 1e-4, epochs 200 / patience 30).
- valid(고정 109) / test(고정 110) 은 subsample 하지 않는다. subsample 은 train 에만 적용.
- subsample = 멀티라벨 분포(370 PT) 보존을 위한 iterative stratification(Sechidis et al. 2011)로 선택.
  * iterative-stratification 패키지 미설치 → 알고리즘을 직접 구현(시드 고정, 재현 가능, 새 의존성 없음).
- 각 비율 × seed{42,1,2,3,4}(총 5회) 반복 → test macro PR-AUC(주지표) / macro ROC-AUC 를 mean±std 로.
- 평가 프로토콜은 v2 evaluate.py 와 동일(test 양성>0 PT 만 macro 평균).

재현성/견고성:
- 전역 seed 고정, subsample 인덱스(cid)·하이퍼파라미터를 로그(JSON)로 저장.
- 증분/idempotent: (model, fraction, seed) 조합 단위로 learning_curve.csv 에 즉시 기록,
  재실행 시 이미 있는 조합은 건너뜀(끊겨도 이어서). GNN 학습이 길기 때문에 필수.

산출물:
- experiments/results/learning_curve.csv  (model, train_fraction, n_train, seed, macro_pr_auc, macro_roc_auc)
- experiments/results/subsample_indices.json  (fraction→seed→선택된 train cid 목록)
- experiments/results/hyperparams.json         (RF/GNN 설정·seed·fraction 등)
- experiments/results/learning_curve_summary.md (기울기·격차 분석 + 결론 3~4줄)
- experiments/figures/learning_curve.png       (x=train 크기, y=macro PR-AUC, RF/GNN + std 음영)

실행: PYTORCH_ENABLE_MPS_FALLBACK=1 python -u experiments/learning_curve.py \
        2>&1 | tee experiments/results/run.log
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # torch import 전에 (일부 op MPS 미지원 대비)
import sys
import gc
import json
import traceback
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "v2_GNN", "src"))   # 기존 v2 모듈 재사용

import torch
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import rdFingerprintGenerator
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier

from data import load_config, build_graphs                # v2 데이터 로더(그래프 빌드)
from evaluate import per_pt_metrics, aggregate            # v2 평가 프로토콜(그대로)
from train import set_seed, get_device                    # v2 시드/디바이스
from train_improve import train_variant                   # v2 A_wd 학습 루틴(동등예산 조건)

RDLogger.DisableLog("rdApp.*")

OUT = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

CSV_PATH = os.path.join(OUT, "learning_curve.csv")
IDX_PATH = os.path.join(OUT, "subsample_indices.json")
HP_PATH = os.path.join(OUT, "hyperparams.json")
FIG_PATH = os.path.join(FIG, "learning_curve.png")
SUMMARY_PATH = os.path.join(OUT, "learning_curve_summary.md")

# ── 실험 격자 ──────────────────────────────────────────────────────────────
FRACTIONS = [0.2, 0.4, 0.6, 0.8, 1.0]
SEEDS = [42, 1, 2, 3, 4]                                   # robustness.py 와 동일 seed 집합
CSV_COLS = ["model", "train_fraction", "n_train", "seed", "macro_pr_auc", "macro_roc_auc"]

# GNN 동등예산 공정성 조건(= robustness.py 의 1b 선택모델 A_wd, 튜닝 금지)
A_WD = {"name": "A_wd", "loss": "focal", "pw_mode": "sqrt", "gamma": 2.0,
        "overrides": {"weight_decay": 1e-4}}
GNN_EPOCHS, GNN_PATIENCE = 200, 30
RF_PARAMS = dict(n_estimators=300, max_depth=None, n_jobs=-1,
                 class_weight="balanced_subsample")
FP_RADIUS, FP_NBITS = 2, 2048


def log(msg):
    print(msg, flush=True)


# ── Morgan FP + RF (v1 설정 그대로) ─────────────────────────────────────────
def morgan_fp(smiles, radius=FP_RADIUS, n_bits=FP_NBITS):
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    M = np.zeros((len(smiles), n_bits), dtype=np.uint8)
    for i, smi in enumerate(smiles):
        m = Chem.MolFromSmiles(smi)
        if m is not None:
            M[i] = gen.GetFingerprintAsNumPy(m).astype(np.uint8)
    return M


def rf_proba(Xtr, Ytr, Xte, seed):
    clf = MultiOutputClassifier(RandomForestClassifier(random_state=seed, **RF_PARAMS))
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xte.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xte)[:, cls.index(1)]
    return P


# ── Iterative stratification (Sechidis, Tsoumakas & Vlahavas, ECML PKDD 2011) ──
def iterative_stratification_subsample(Y, fraction, seed):
    """멀티라벨 분포를 보존하며 fraction 비율의 train 부분집합 인덱스를 선택.

    2-fold(비율 [fraction, 1-fraction]) iterative stratification 을 수행하고
    fold 0(=subsample)에 배정된 표본 인덱스를 반환한다. fraction=1.0 이면 전체.
    Y: (n, L) 0/1 멀티라벨 행렬. 반환: 정렬된 인덱스 ndarray (len ≈ fraction*n).
    """
    rng = np.random.RandomState(seed)
    n, L = Y.shape
    ratios = [fraction, 1.0 - fraction]
    F = len(ratios)                                        # fold 수 = 2
    c = [ratios[k] * n for k in range(F)]                  # fold별 목표 표본 수
    cj = [[ratios[k] * float(Y[:, j].sum()) for j in range(L)] for k in range(F)]  # fold×label 목표
    assign = np.full(n, -1, dtype=int)
    remaining = np.ones(n, dtype=bool)

    def choose_fold(lbl):
        # 용량(목표 표본 수)이 남은 fold 만 후보 → subsample 크기가 목표(fraction)에서 크게
        # 벗어나지 않도록 강제(iterative stratification 은 크기를 보장하지 않기 때문).
        elig = [k for k in range(F) if c[k] > 0]
        if not elig:
            elig = list(range(F))
        vals = [cj[k][lbl] for k in elig]
        mx = max(vals)
        cand = [elig[t] for t in range(len(elig)) if vals[t] == mx]
        if len(cand) > 1:                                  # 동점 → 목표 표본 수 c 가 큰 fold
            cmx = max(c[k] for k in cand)
            cand = [k for k in cand if c[k] == cmx]
        return cand[rng.randint(len(cand))] if len(cand) > 1 else cand[0]

    while remaining.any():
        rem_idx = np.where(remaining)[0]
        label_counts = Y[rem_idx].sum(0)                   # 남은 표본의 label별 개수
        pos = np.where(label_counts > 0)[0]
        if pos.size == 0:                                  # 라벨 없는 잔여 표본 → c 큰 fold 로
            for i in rem_idx:
                k = int(np.argmax(c))
                assign[i] = k
                c[k] -= 1
                remaining[i] = False
            break
        # 남은 개수가 가장 적은(>0) 라벨 선택(동점 → 무작위)
        mn = label_counts[pos].min()
        cand_lbl = pos[label_counts[pos] == mn]
        lbl = int(cand_lbl[rng.randint(len(cand_lbl))])
        # 그 라벨을 가진 잔여 표본을 모두 배정
        samples = rem_idx[Y[rem_idx, lbl] == 1]
        rng.shuffle(samples)                               # 배정 순서 무작위(재현: seed 고정)
        for i in samples:
            k = choose_fold(lbl)
            assign[i] = k
            remaining[i] = False
            c[k] -= 1
            for j in np.where(Y[i] == 1)[0]:               # 표본이 가진 모든 라벨의 목표 감소
                cj[k][j] -= 1
    return np.sort(np.where(assign == 0)[0])


# ── 데이터 준비(1회) ────────────────────────────────────────────────────────
def prepare(cfg):
    """전체 train/valid/test 를 한 번만 준비. FP·그래프·라벨을 동일 순서로 정렬해 둔다.

    build_graphs 는 X 행 순서대로 split 별 그래프 리스트를 만든다(실패 0 확인됨).
    따라서 train 그래프 리스트 k번째 ↔ FP_train[k] ↔ Ytr[k] ↔ train_cids[k] 가 정렬 일치.
    """
    data = build_graphs(cfg)                               # graphs{train,valid,test}, ycols, Y, n_failed
    if data["n_failed"] != 0:
        raise SystemExit(f"[중단] SMILES→graph 실패 {data['n_failed']}개 — 정렬 가정 위반, 점검 필요.")
    ycols = data["ycols"]

    X = pd.read_parquet(os.path.join(ROOT, cfg["data"]["master_x"]))
    Y = pd.read_parquet(os.path.join(ROOT, cfg["data"]["master_y"]))
    assert list(X["cid"]) == list(Y["cid"]), "X/Y cid 정렬 불일치"
    split = json.load(open(os.path.join(ROOT, cfg["data"]["split"])))
    sp = X["cid"].astype(str).map(split)
    Ym = Y[ycols].values.astype(int)
    smiles = X["smiles_canonical"].tolist()
    cids = X["cid"].tolist()

    tr = (sp == "train").values
    te = (sp == "test").values
    FP = morgan_fp(smiles)

    prep = {
        "ycols": ycols,
        "graphs_valid": data["graphs"]["valid"],
        "graphs_test": data["graphs"]["test"],
        "graphs_train": data["graphs"]["train"],           # X train-행 순서
        "FP_train": FP[tr], "FP_test": FP[te],
        "Ytr": Ym[tr], "Yte": Ym[te],
        "train_cids": [cids[i] for i in np.where(tr)[0]],
    }
    # 정렬 일치 검증 (그래프 수 ↔ FP/Y train 수)
    assert len(prep["graphs_train"]) == prep["FP_train"].shape[0] == prep["Ytr"].shape[0], \
        "train 그래프/FP/Y 개수 불일치 — 정렬 가정 위반"
    log(f"[prep] train {prep['Ytr'].shape[0]} / valid {len(prep['graphs_valid'])} / "
        f"test {len(prep['graphs_test'])} | PT {len(ycols)} | FP {prep['FP_train'].shape[1]}bit")
    return prep


def eval_macro(Yte, P, ycols, thr):
    """v2 평가 프로토콜: test 양성>0 PT 만 macro 평균 → (macro_pr_auc, macro_roc_auc)."""
    df = per_pt_metrics(Yte, P, ycols, thr)
    agg = aggregate(Yte, P, df, thr)
    return agg["macro_pr_auc"], agg["macro_roc_auc"]


# ── CSV 증분 I/O ────────────────────────────────────────────────────────────
def load_done():
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame(columns=CSV_COLS), set()
    df = pd.read_csv(CSV_PATH)
    done = {(r["model"], round(float(r["train_fraction"]), 4), int(r["seed"]))
            for _, r in df.iterrows()}
    return df, done


def append_rows(df, rows):
    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    df = df.sort_values(["model", "train_fraction", "seed"]).reset_index(drop=True)
    df.to_csv(CSV_PATH, index=False)
    return df


# ── 메인 ────────────────────────────────────────────────────────────────────
def main():
    cfg = load_config()
    device = get_device(cfg)
    thr = cfg["eval"]["threshold"]
    log(f"[env] device={device} | fractions={FRACTIONS} | seeds={SEEDS} | "
        f"GNN=A_wd(GIN, focal γ2+sqrt pw+wd1e-4, ep{GNN_EPOCHS}/pat{GNN_PATIENCE}) | "
        f"fallback={os.environ.get('PYTORCH_ENABLE_MPS_FALLBACK')}")

    prep = prepare(cfg)
    ycols = prep["ycols"]
    n_train_full = prep["Ytr"].shape[0]

    # 하이퍼파라미터·설정 로그(재현성)
    json.dump({
        "fractions": FRACTIONS, "seeds": SEEDS, "n_train_full": int(n_train_full),
        "n_valid": len(prep["graphs_valid"]), "n_test": len(prep["graphs_test"]),
        "n_pt": len(ycols), "eval_threshold": thr, "device": str(device),
        "rf": {**RF_PARAMS, "fingerprint": {"type": "morgan_ecfp4", "radius": FP_RADIUS, "n_bits": FP_NBITS}},
        "gnn": {"model": "GIN", "fairness_condition": "A_wd", **A_WD,
                "epochs": GNN_EPOCHS, "patience": GNN_PATIENCE,
                "hidden": cfg["model"]["hidden"], "n_layers": cfg["model"]["n_layers"],
                "pool": "mean", "lr": cfg["train"]["lr"], "batch_size": cfg["train"]["batch_size"]},
        "stratification": "iterative (Sechidis et al. 2011), self-implemented, multilabel-preserving",
        "eval_protocol": "test 양성>0 PT 만 macro 평균 (v2 evaluate.py 동일)",
    }, open(HP_PATH, "w"), ensure_ascii=False, indent=2)

    # 기존 진행분 로드(idempotent) + subsample 인덱스 로그 로드
    df, done = load_done()
    idx_log = json.load(open(IDX_PATH)) if os.path.exists(IDX_PATH) else {}
    log(f"[resume] 이미 완료된 (model,frac,seed) 조합 {len(done)}개 — 건너뜀.")

    total = len(FRACTIONS) * len(SEEDS)
    step = 0
    for frac in FRACTIONS:
        fkey = f"{frac:.2f}"
        idx_log.setdefault(fkey, {})
        for seed in SEEDS:
            step += 1
            need_rf = ("RF", round(frac, 4), seed) not in done
            need_gnn = ("GNN", round(frac, 4), seed) not in done
            if not (need_rf or need_gnn):
                log(f"[{step}/{total}] frac {frac:.0%} seed {seed}: 이미 완료 — 건너뜀.")
                continue

            # subsample 인덱스(멀티라벨 iterative stratification) — RF/GNN 동일 표본 사용
            sub = iterative_stratification_subsample(prep["Ytr"], frac, seed)
            n_sub = int(len(sub))
            idx_log[fkey][str(seed)] = [int(prep["train_cids"][i]) for i in sub]
            json.dump(idx_log, open(IDX_PATH, "w"), ensure_ascii=False)
            log(f"[{step}/{total}] frac {frac:.0%} (n_train={n_sub}) seed {seed} "
                f"| RF={'run' if need_rf else 'skip'} GNN={'run' if need_gnn else 'skip'}")

            rows = []
            # --- RF (v1 설정, random_state=seed) ---
            if need_rf:
                Pr = rf_proba(prep["FP_train"][sub], prep["Ytr"][sub], prep["FP_test"], seed)
                pr, roc = eval_macro(prep["Yte"], Pr, ycols, thr)
                rows.append({"model": "RF", "train_fraction": frac, "n_train": n_sub,
                             "seed": seed, "macro_pr_auc": pr, "macro_roc_auc": roc})
                log(f"    RF : macro PR-AUC {pr:.4f} | macro ROC-AUC {roc:.4f}")

            # --- GNN A_wd (동등예산 조건, fresh, seed) ---
            if need_gnn:
                cfg["seed"] = seed
                set_seed(seed)
                sub_graphs = [prep["graphs_train"][i] for i in sub]
                sub_data = {"graphs": {"train": sub_graphs,
                                       "valid": prep["graphs_valid"],
                                       "test": prep["graphs_test"]},
                            "ycols": ycols}
                r = train_variant(cfg, sub_data, device, A_WD,
                                  epochs=GNN_EPOCHS, patience=GNN_PATIENCE, log=lambda *a: None)
                Pg = r["P_test"]
                Yte_g = r["Yte"].astype(int)
                pr, roc = eval_macro(Yte_g, Pg, ycols, thr)
                rows.append({"model": "GNN", "train_fraction": frac, "n_train": n_sub,
                             "seed": seed, "macro_pr_auc": pr, "macro_roc_auc": roc})
                log(f"    GNN: macro PR-AUC {pr:.4f} | macro ROC-AUC {roc:.4f} "
                    f"(valid {r['valid']:.4f} @ep{r['best_ep']})")
                # 메모리/MPS 캐시 정리(누적 방지)
                del r, sub_graphs, sub_data
                gc.collect()
                try:
                    if str(device) == "mps":
                        torch.mps.empty_cache()
                    elif str(device) == "cuda":
                        torch.cuda.empty_cache()
                except Exception:
                    pass

            if rows:
                df = append_rows(df, rows)
                for row in rows:
                    done.add((row["model"], round(frac, 4), seed))

    # 전부 완료 → 그림 + 분석 요약
    analyze_and_plot(df)


# ── 분석(기울기·격차) + 그림 ────────────────────────────────────────────────
def _agg_by_fraction(df, model, metric):
    g = df[df.model == model].groupby("train_fraction")
    m = g[metric].mean()
    s = g[metric].std(ddof=1)
    n = g["n_train"].mean()
    fr = sorted(m.index)
    return (np.array(fr),
            np.array([n[f] for f in fr]),
            np.array([m[f] for f in fr]),
            np.array([s[f] if not np.isnan(s[f]) else 0.0 for f in fr]))


def analyze_and_plot(df):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fr_rf, n_rf, m_rf, s_rf = _agg_by_fraction(df, "RF", "macro_pr_auc")
    fr_g, n_g, m_g, s_g = _agg_by_fraction(df, "GNN", "macro_pr_auc")

    # ── 그림: x=train 크기, y=macro PR-AUC, RF/GNN + std 음영 ──
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    for n, m, s, color, name in [(n_rf, m_rf, s_rf, "#1f77b4", "RF (v1, Morgan+RandomForest)"),
                                 (n_g, m_g, s_g, "#d62728", "GNN (v2, GIN A_wd)")]:
        ax.plot(n, m, "o-", color=color, label=name, lw=2, ms=6)
        ax.fill_between(n, m - s, m + s, color=color, alpha=0.18)
    ax.set(xlabel="Training set size (number of molecules)", ylabel="Test macro PR-AUC",
           title="Data-scaling (learning) curve: RF vs GNN\n"
                 "valid=109 / test=110 fixed; only train iterative-stratified subsampled (5 seeds)")
    ax.grid(alpha=0.3)
    ax.legend(loc="best", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_PATH, dpi=140)
    plt.close(fig)
    log(f"[그림] 저장 → {FIG_PATH}")

    # ── 기울기 분석(마지막 구간 80%→100%) ──
    def last_slope(n, m):
        dn, dm = n[-1] - n[-2], m[-1] - m[-2]
        return dm / dn if dn != 0 else float("nan")

    def full_slope(n, m):
        dn, dm = n[-1] - n[0], m[-1] - m[0]
        return dm / dn if dn != 0 else float("nan")

    ls_rf, ls_g = last_slope(n_rf, m_rf), last_slope(n_g, m_g)
    fs_rf, fs_g = full_slope(n_rf, m_rf), full_slope(n_g, m_g)
    gap = m_rf - m_g                                    # RF - GNN (양수 = RF 우위)

    # 평탄화 판정: 마지막 구간 성능 증가폭(Δ per 100 분자)이 전체 평균 증가폭 대비 작으면 plateau
    def per100(slope):
        return slope * 100.0
    gnn_last_delta = m_g[-1] - m_g[-2]
    gnn_rising = (per100(ls_g) > 0.005)                 # 100분자당 macro PR-AUC +0.005 초과면 "상승 중"
    gap_narrowing = gap[-1] < gap[0]

    lines = [
        "# 데이터 스케일링(learning curve) 분석 — RF vs GNN",
        "",
        "> 목적: \"RF>GNN 이 데이터셋이 작아서 생긴 것 아니냐\"는 반박 대응. "
        "train(873)을 20/40/60/80/100% 로 iterative-stratified subsample(멀티라벨 분포 보존), "
        "seed 5개 반복. valid(109)·test(110) 고정. GNN=동등예산 A_wd(GIN), RF=v1 설정. "
        "주지표=test macro PR-AUC.",
        "",
        "## 비율별 test macro PR-AUC (mean ± std, seed=5)",
        "",
        "| train_fraction | n_train | RF macro PR-AUC | GNN macro PR-AUC | 격차(RF−GNN) |",
        "|---|---|---|---|---|",
    ]
    for i, f in enumerate(fr_rf):
        lines.append(f"| {f:.0%} | {int(round(n_rf[i]))} | {m_rf[i]:.3f} ± {s_rf[i]:.3f} | "
                     f"{m_g[i]:.3f} ± {s_g[i]:.3f} | {gap[i]:+.3f} |")

    lines += [
        "",
        "## 곡선 기울기 (macro PR-AUC 증가율)",
        "",
        "| 모델 | 마지막 구간(80→100%) Δ/100분자 | 전체(20→100%) Δ/100분자 |",
        "|---|---|---|",
        f"| RF  | {per100(ls_rf):+.4f} | {per100(fs_rf):+.4f} |",
        f"| GNN | {per100(ls_g):+.4f} | {per100(fs_g):+.4f} |",
        "",
        f"- GNN 마지막 구간 실제 성능 변화(80%→100%): {gnn_last_delta:+.4f} macro PR-AUC.",
        "",
        "## 결론 (3~4줄)",
        "",
        f"1. **GNN 곡선이 아직 상승 중인가?** → {'예, 마지막 구간에서도 상승 중' if gnn_rising else '아니오, 사실상 평탄화'} "
        f"(80→100% 기울기 {per100(ls_g):+.4f}/100분자). "
        f"{'데이터를 더 주면 개선 여지 있음 → 규모 한계 가능성.' if gnn_rising else '데이터를 더 줘도 추가 이득이 작음 → RF 우위는 데이터 양 문제로 보기 어려움.'}",
        f"2. **두 모델 격차가 데이터 증가에 따라 좁혀지는가?** → "
        f"{'예, 좁혀지는 추세' if gap_narrowing else '아니오, 좁혀지지 않음(오히려 유지/확대)'} "
        f"(격차 {gap[0]:+.3f}@20% → {gap[-1]:+.3f}@100%).",
        f"3. 전 구간에서 RF macro PR-AUC 가 GNN 을 {'상회' if (m_rf >= m_g).all() else '대체로 상회'}"
        f"({int((m_rf >= m_g).sum())}/{len(fr_rf)} 비율). "
        f"{'격차가 데이터가 늘어도 유지 → RF 우위는 데이터 규모의 산물이 아니라 이 과제(희소 멀티라벨·소분자)에서의 구조적 특성일 가능성.' if not gap_narrowing else '격차가 좁혀지므로 대규모 데이터에서는 역전 가능성을 배제할 수 없음(한계로 명시).'}",
        "4. (한계) MPS 비결정성·소표본으로 절대 수치는 ±소폭 변동 가능. scaffold split 은 v1/v2 와 동일 고정본 사용.",
        "",
        "## 재현성 / 산출물",
        "- 전역 seed 고정(42,1,2,3,4), subsample 은 iterative stratification(직접 구현, 시드 고정).",
        "- `results/learning_curve.csv` (model, train_fraction, n_train, seed, macro_pr_auc, macro_roc_auc)",
        "- `results/subsample_indices.json` (fraction→seed→선택 train cid), `results/hyperparams.json`",
        "- `figures/learning_curve.png`",
    ]
    with open(SUMMARY_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    log("\n".join(lines))
    log(f"[요약] 저장 → {SUMMARY_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print("\n===== [learning_curve 중단] 예외 발생 =====", flush=True)
        print(tb, flush=True)
        print(tb, file=sys.stderr, flush=True)
        sys.exit(1)
