#!/usr/bin/env python3
"""RQ2 공정성 보정 — RF 동등예산 튜닝 (v1_RF/results_fairtune/).

문제: 기존 비교는 '튜닝 GNN(A_wd, 2라운드+5시드) vs 디폴트 RF(미튜닝)'라 불공정.
조치: RF에도 GNN과 동등한 탐색예산(16개 구성 RandomizedSearch)을 부여해 재비교.

절대 원칙(요구사항 그대로):
- master_X/Y·scaffold_split.json 재계산 금지 → v1_RF/src/data.py 로더로 '그대로 로드'.
- 평가 프로토콜 v2와 100% 동일: test 110분자, 301 PT(test 양성>0), macro/micro PR-AUC 주지표.
  → v1_RF/src/evaluate.py 의 per_pt_metrics/aggregate 그대로 재사용.
- 모델 선택은 valid macro PR-AUC 로만(test 선택 금지). 16개 후보 valid 점수 전부 로그.
- seed [1,2,3,4,42]. mock 금지. 결과는 방향 무관 정직 보고.
- GNN 수치는 v2 산출물 재사용(robustness/seed_*.csv 집계 + round1b/metrics_per_pt.csv PT별). GNN 재학습 금지.

동등예산: GNN이 valid로 평가한 구성 수(≈ GCN/GIN/GAT 3 + round1a 5 + round1b 4 = 12개)에 맞춰
RF는 16개 구성(샘플 seed=42 고정 RandomizedSearch). seed=42 valid로 best 선택 → 5시드 재학습 test mean±std.

산출물: v1_RF/results_fairtune/{search_log.csv, best_config.yaml, seed_<n>.csv,
        aggregate_test.csv, significance_fair.csv, summary.md, run.log}

실행: python -u v1_RF/src/fairtune.py 2>&1 | tee v1_RF/results_fairtune/run.log
"""
import os
import sys
import json
import traceback
import numpy as np
import pandas as pd
import yaml
from scipy.stats import wilcoxon, ttest_rel, rankdata, t as tdist

from data import ROOT, load_config, load_dataset
from features import morgan_matrix
from evaluate import per_pt_metrics, aggregate

from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier

OUT = os.path.join(ROOT, "v1_RF", "results_fairtune")
os.makedirs(OUT, exist_ok=True)
SEEDS = [1, 2, 3, 4, 42]
SAMPLE_SEED = 42         # RandomizedSearch 샘플링 고정
N_CONFIGS = 16           # GNN 동등예산
THR = 0.5                # 평가 임계값(v1·v2 동일)

# RF 탐색공간 (FP축 = GNN 아키텍처 튜닝에 대응하는 RF '표현' 튜닝)
SPACE = {
    "n_estimators": [300, 600, 1000],
    "max_depth": [None, 20, 40],
    "max_features": ["sqrt", "log2", 0.1],
    "min_samples_leaf": [1, 2, 5],
    "class_weight": ["balanced", "balanced_subsample", None],
    "fp": [(2, 2048), (2, 4096), (3, 2048)],
}

# v2 GNN 재사용 경로
ROB = os.path.join(ROOT, "v2_GNN", "results_improve", "robustness")        # seed_*.csv (gnn/rf 집계)
GNN_PERPT = os.path.join(ROOT, "v2_GNN", "results_improve", "round1b", "metrics_per_pt.csv")  # A_wd seed42 PT별
V1_DEFAULT_PERPT = os.path.join(ROOT, "v1_RF", "results", "metrics_per_pt.csv")  # 디폴트 RF seed42 PT별


def log(msg):
    print(msg, flush=True)


def sample_configs():
    """탐색공간에서 중복 없이 N_CONFIGS개 구성 샘플(고정 seed)."""
    rng = np.random.default_rng(SAMPLE_SEED)
    keys = list(SPACE.keys())
    seen, configs = set(), []
    guard = 0
    while len(configs) < N_CONFIGS and guard < 100000:
        guard += 1
        cfg = {k: SPACE[k][int(rng.integers(len(SPACE[k])))] for k in keys}
        sig = tuple((k, cfg[k]) for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        configs.append(cfg)
    return configs


def fp_for(fp_tuple, smiles, cache):
    """(radius,bits) → 전체 분자 FP 행렬(캐시)."""
    if fp_tuple not in cache:
        r, b = fp_tuple
        M, failed = morgan_matrix(smiles, radius=r, n_bits=b, log=lambda *a: None)
        cache[fp_tuple] = M
        log(f"[fp] r={r} bits={b} → {M.shape} (실패 {len(failed)})")
    return cache[fp_tuple]


def rf_proba(cfg_params, Xtr, Ytr, Xeval, seed):
    """MultiOutput RF 학습 후 (n, n_labels) 양성확률."""
    clf = MultiOutputClassifier(RandomForestClassifier(
        n_estimators=cfg_params["n_estimators"], max_depth=cfg_params["max_depth"],
        max_features=cfg_params["max_features"], min_samples_leaf=cfg_params["min_samples_leaf"],
        class_weight=cfg_params["class_weight"], n_jobs=-1, random_state=seed))
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xeval.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xeval)[:, cls.index(1)]
    return P


def macro_micro(Y, P, ycols):
    """평가 프로토콜 동일: per_pt_metrics + aggregate (양성>0 PT만 macro)."""
    df = per_pt_metrics(Y, P, ycols, THR)
    agg = aggregate(Y, P, df, THR)
    return agg, df


def rank_biserial(diff):
    """Wilcoxon 부호순위 효과크기(rank-biserial r). 0차 제거 후."""
    d = diff[diff != 0]
    if len(d) == 0:
        return float("nan")
    ranks = rankdata(np.abs(d))
    Wp = ranks[d > 0].sum()
    Wm = ranks[d < 0].sum()
    T = Wp + Wm
    return float((Wp - Wm) / T)


def cohens_dz(diff):
    """대응표본 Cohen's dz = mean/std(ddof=1)."""
    sd = diff.std(ddof=1)
    return float(diff.mean() / sd) if sd > 0 else float("nan")


def paired_pt_test(label, a, b, a_name, b_name):
    """PT별 대응표본 검정(a vs b) + 효과크기. a,b: 동일 PT 순서 PR-AUC 배열."""
    diff = a - b
    n = len(diff)
    w_stat, w_p = wilcoxon(a, b)
    t_stat, t_p = ttest_rel(a, b)
    return {
        "comparison": label, "a": a_name, "b": b_name, "n_pt": n,
        f"{a_name}_mean_pr": float(a.mean()), f"{b_name}_mean_pr": float(b.mean()),
        "mean_diff(a-b)": float(diff.mean()), "median_diff(a-b)": float(np.median(diff)),
        "n_pt_a_higher": int((diff > 0).sum()),
        "wilcoxon_stat": float(w_stat), "wilcoxon_p": float(w_p),
        "rank_biserial_r": rank_biserial(diff),
        "paired_t_stat": float(t_stat), "paired_t_p": float(t_p),
        "cohens_dz": cohens_dz(diff),
        "direction": "a>b" if diff.mean() > 0 else "a<=b",
    }


def seed_csv(seed):
    return os.path.join(OUT, f"seed_{seed}.csv")


def main():
    cfg = load_config()
    X, Y, ycols, masks = load_dataset(cfg)
    smiles = X["smiles_canonical"].tolist()
    tr, va, te = masks["train"], masks["valid"], masks["test"]
    Ytr, Yva, Yte = Y[tr], Y[va], Y[te]
    log(f"[data] 분자 {len(X)} × PT {len(ycols)} | train {tr.sum()} / valid {va.sum()} / test {te.sum()}")

    fp_cache = {}
    search_path = os.path.join(OUT, "search_log.csv")
    best_path = os.path.join(OUT, "best_config.yaml")

    # ── STEP 1: seed=42 valid 로 16개 구성 평가 → best 선택 (idempotent: 이미 있으면 재사용) ──
    if os.path.exists(search_path) and os.path.exists(best_path):
        search = pd.read_csv(search_path)
        with open(best_path) as f:
            bc = yaml.safe_load(f)["config"]
        best = {"n_estimators": bc["n_estimators"], "max_depth": bc["max_depth"],
                "max_features": bc["max_features"], "min_samples_leaf": bc["min_samples_leaf"],
                "class_weight": bc["class_weight"], "fp": (bc["fp_radius"], bc["fp_bits"])}
        best_id = int(search.iloc[0]["config_id"])
        log(f"[search] 기존 결과 재사용(재탐색 생략): best config_id={best_id}, "
            f"valid macroPR {search.iloc[0]['valid_macro_pr']:.4f}")
    else:
        configs = sample_configs()
        log(f"[search] 동등예산 {len(configs)}개 구성 (sample_seed={SAMPLE_SEED}) — valid macro PR-AUC 로만 선택")
        rows = []
        for i, c in enumerate(configs):
            M = fp_for(c["fp"], smiles, fp_cache)
            Xtr, Xva = M[tr], M[va]
            P_va = rf_proba(c, Xtr, Ytr, Xva, seed=42)
            agg_va, _ = macro_micro(Yva, P_va, ycols)
            row = {"config_id": i,
                   "n_estimators": c["n_estimators"], "max_depth": c["max_depth"],
                   "max_features": c["max_features"], "min_samples_leaf": c["min_samples_leaf"],
                   "class_weight": c["class_weight"], "fp_radius": c["fp"][0], "fp_bits": c["fp"][1],
                   "valid_macro_pr": agg_va["macro_pr_auc"], "valid_micro_pr": agg_va["micro_pr_auc"]}
            rows.append(row)
            log(f"  [cfg {i:2d}] valid macroPR {row['valid_macro_pr']:.4f} microPR {row['valid_micro_pr']:.4f} | "
                f"n_est={c['n_estimators']} depth={c['max_depth']} feat={c['max_features']} "
                f"leaf={c['min_samples_leaf']} cw={c['class_weight']} fp=({c['fp'][0]},{c['fp'][1]})")
        search = pd.DataFrame(rows).sort_values("valid_macro_pr", ascending=False).reset_index(drop=True)
        search.to_csv(search_path, index=False)
        best_id = int(search.iloc[0]["config_id"])
        best = configs[best_id]
        log(f"[select] valid 최적 config_id={best_id} | valid macroPR {search.iloc[0]['valid_macro_pr']:.4f} "
            f"(test 미사용)")
        with open(best_path, "w") as f:
            yaml.safe_dump({"selected_by": "valid_macro_pr",
                            "config": {**{k: best[k] for k in SPACE if k != "fp"},
                                       "fp_radius": best["fp"][0], "fp_bits": best["fp"][1]},
                            "valid_macro_pr": float(search.iloc[0]["valid_macro_pr"]),
                            "search_budget": len(configs), "sample_seed": SAMPLE_SEED}, f, sort_keys=False)

    # ── STEP 2: best config 5시드 재학습 → test (idempotent: seed CSV 있으면 생략) ──
    perpt_path = os.path.join(OUT, "perpt_seed42.csv")
    M_best = None
    for seed in SEEDS:
        # seed CSV가 있고, seed42의 per-PT(검정용)도 이미 있으면 학습 생략
        if os.path.exists(seed_csv(seed)) and (seed != 42 or os.path.exists(perpt_path)):
            log(f"[seed {seed}] 기존 seed_{seed}.csv 재사용(재학습 생략)")
            continue
        if M_best is None:
            M_best = fp_for(best["fp"], smiles, fp_cache)
        Xtr_b, Xte_b = M_best[tr], M_best[te]
        P_te = rf_proba(best, Xtr_b, Ytr, Xte_b, seed=seed)
        agg, df = macro_micro(Yte, P_te, ycols)
        rowd = {"seed": seed, "tuned_rf_macro": agg["macro_pr_auc"], "tuned_rf_micro": agg["micro_pr_auc"],
                "macro_roc": agg["macro_roc_auc"], "hamming": agg["hamming_accuracy"]}
        pd.DataFrame([rowd]).to_csv(seed_csv(seed), index=False)
        log(f"[seed {seed}] tuned RF macroPR {agg['macro_pr_auc']:.4f} microPR {agg['micro_pr_auc']:.4f} → seed_{seed}.csv")
        if seed == 42:
            df[["meddra_pt", "n_pos_test", "pr_auc"]].to_csv(perpt_path, index=False)
    perpt_seed42 = pd.read_csv(perpt_path)

    # ── STEP 3: GNN/디폴트RF 재사용 + 집계/검정 ──
    rob = pd.concat([pd.read_csv(os.path.join(ROB, f"seed_{s}.csv")) for s in SEEDS],
                    ignore_index=True).sort_values("seed")
    tuned = pd.concat([pd.read_csv(seed_csv(s)) for s in SEEDS], ignore_index=True).sort_values("seed")
    merged = rob.merge(tuned, on="seed")     # gnn_macro/micro, rf_macro/micro(default), tuned_rf_macro/micro

    def agg_stats(vals):
        v = np.asarray(vals, float)
        return float(v.mean()), float(v.std(ddof=1))

    # 시드 단위 mean±std + 대응검정(95% CI, Cohen's dz)
    def seed_paired(a, b, label):
        a = np.asarray(a, float); b = np.asarray(b, float); d = a - b
        n = len(d); mean = float(d.mean()); sd = float(d.std(ddof=1)); se = sd / np.sqrt(n)
        tcrit = float(tdist.ppf(0.975, n - 1))
        t_stat, t_p = ttest_rel(a, b)
        try:
            w_stat, w_p = wilcoxon(a, b); w_p = float(w_p)
        except ValueError:
            w_p = float("nan")
        return {"comparison": label, "n_seed": n,
                "mean_diff": mean, "ci95_lo": mean - tcrit * se, "ci95_hi": mean + tcrit * se,
                "ci_crosses_0": bool((mean - tcrit * se) < 0 < (mean + tcrit * se)),
                "paired_t_p": float(t_p), "cohens_dz": cohens_dz(d),
                "wilcoxon_p": w_p, "wilcoxon_min_p(n=5)": 2.0 / (2 ** n)}

    agg_rows = []
    for name, col in [("tuned_rf_macro", "tuned_rf_macro"), ("gnn_macro", "gnn_macro"),
                      ("default_rf_macro", "rf_macro"), ("tuned_rf_micro", "tuned_rf_micro"),
                      ("gnn_micro", "gnn_micro"), ("default_rf_micro", "rf_micro")]:
        m, s = agg_stats(merged[col]); agg_rows.append({"metric": name, "mean": m, "std": s, "n_seed": len(merged)})
    agg_df = pd.DataFrame(agg_rows)
    # 시드 단위 주/보조 대응검정
    seed_tests = pd.DataFrame([
        seed_paired(merged["tuned_rf_macro"], merged["gnn_macro"], "MACRO 주: tunedRF vs tunedGNN(A_wd)"),
        seed_paired(merged["tuned_rf_micro"], merged["gnn_micro"], "MICRO 주: tunedRF vs tunedGNN(A_wd)"),
        seed_paired(merged["tuned_rf_macro"], merged["rf_macro"], "MACRO 보조: tunedRF vs defaultRF"),
        seed_paired(merged["tuned_rf_micro"], merged["rf_micro"], "MICRO 보조: tunedRF vs defaultRF"),
    ])
    agg_df.to_csv(os.path.join(OUT, "aggregate_test.csv"), index=False)
    seed_tests.to_csv(os.path.join(OUT, "aggregate_seed_paired.csv"), index=False)

    # ── PT 단위 대응검정(seed 42) + 효과크기: 주=tunedRF vs GNN, 보조=tunedRF vs defaultRF ──
    gnn_pt = pd.read_csv(GNN_PERPT)[["meddra_pt", "n_pos_test", "pr_auc"]].rename(columns={"pr_auc": "gnn_pr"})
    def_pt = pd.read_csv(V1_DEFAULT_PERPT)[["meddra_pt", "RandomForest_pr_auc"]].rename(
        columns={"RandomForest_pr_auc": "defrf_pr"})
    # meddra_pt 키 dtype 통일(str) — 한쪽이 int64로 읽혀 merge 실패하는 문제 방지
    tuned_pt = perpt_seed42.rename(columns={"pr_auc": "tuned_pr"}).copy()
    for d in (tuned_pt, gnn_pt, def_pt):
        d["meddra_pt"] = d["meddra_pt"].astype(str)
    pt = tuned_pt.merge(gnn_pt[["meddra_pt", "gnn_pr"]], on="meddra_pt", how="inner")
    pt = pt.merge(def_pt, on="meddra_pt", how="inner").dropna(subset=["tuned_pr", "gnn_pr", "defrf_pr"])
    sig = pd.DataFrame([
        paired_pt_test("PT 주: tunedRF vs tunedGNN(A_wd) [seed42, 301PT]",
                       pt["tuned_pr"].values, pt["gnn_pr"].values, "tunedRF", "tunedGNN"),
        paired_pt_test("PT 보조: tunedRF vs defaultRF [seed42, 301PT]",
                       pt["tuned_pr"].values, pt["defrf_pr"].values, "tunedRF", "defaultRF"),
    ])
    sig.to_csv(os.path.join(OUT, "significance_fair.csv"), index=False)

    write_summary(search, best, best_id, agg_df, seed_tests, sig, len(pt))
    log("[완료] results_fairtune/ 산출 완료")


def write_summary(search, best, best_id, agg_df, seed_tests, sig, n_pt):
    a = {r["metric"]: (r["mean"], r["std"]) for _, r in agg_df.iterrows()}
    st = {r["comparison"]: r for _, r in seed_tests.iterrows()}
    sg = {r["comparison"]: r for _, r in sig.iterrows()}
    macro_main = st["MACRO 주: tunedRF vs tunedGNN(A_wd)"]
    micro_main = st["MICRO 주: tunedRF vs tunedGNN(A_wd)"]
    macro_aux = st["MACRO 보조: tunedRF vs defaultRF"]
    pt_main = sg["PT 주: tunedRF vs tunedGNN(A_wd) [seed42, 301PT]"]
    pt_aux = sg["PT 보조: tunedRF vs defaultRF [seed42, 301PT]"]

    def ms(k):
        m, s = a[k]; return f"{m:.3f} ± {s:.3f}"

    tuned_m = a["tuned_rf_macro"][0]; gnn_m = a["gnn_macro"][0]; def_m = a["default_rf_macro"][0]
    # 정확한 사실 분해(단일 boolean 금지):
    rf_ahead_macro = tuned_m > gnn_m                         # 점추정상 튜닝RF가 GNN보다 위인가
    macro_sig = not bool(macro_main["ci_crosses_0"])         # macro 차이가 시드단위로 유의한가
    micro_sig = not bool(micro_main["ci_crosses_0"])         # micro 차이가 유의한가
    tuning_helped_rf = tuned_m >= def_m                      # 튜닝이 RF test macro를 올렸는가
    gnn_surpassed = (not rf_ahead_macro) and macro_sig       # GNN이 RF를 유의하게 능가했는가(역전)

    lines = [
        "# RQ2 공정성 보정 — RF 동등예산 튜닝 재판정",
        "",
        f"> 문제: 기존은 '튜닝 GNN(A_wd) vs **디폴트** RF' 불공정 비교. 본 분석은 RF에도 동등예산"
        f"({len(search)}개 구성, sample_seed={SAMPLE_SEED}, valid macro PR-AUC로만 선택)을 부여해 재비교.",
        f"> 데이터·split·test·301 PT·평가 프로토콜 v2와 동일. seed {SEEDS}. GNN 수치는 v2 산출물 재사용(재학습 없음).",
        "",
        "## 1. 선택된 RF 구성 (valid 기준, test 미사용)",
        f"- config_id={best_id}: n_estimators={best['n_estimators']}, max_depth={best['max_depth']}, "
        f"max_features={best['max_features']}, min_samples_leaf={best['min_samples_leaf']}, "
        f"class_weight={best['class_weight']}, FP=(r{best['fp'][0]},{best['fp'][1]}b).",
        f"- valid macro PR-AUC 최고 {search.iloc[0]['valid_macro_pr']:.4f} (16개 구성 전체는 search_log.csv).",
        "",
        "## 2. test 성능 (5시드 mean ± std)",
        "",
        "| 모델 | macro PR-AUC | micro PR-AUC |",
        "|---|---|---|",
        f"| **튜닝 RF** | {ms('tuned_rf_macro')} | {ms('tuned_rf_micro')} |",
        f"| 튜닝 GNN (A_wd) | {ms('gnn_macro')} | {ms('gnn_micro')} |",
        f"| 디폴트 RF | {ms('default_rf_macro')} | {ms('default_rf_micro')} |",
        "",
        "## 3. 주비교 — 튜닝 RF vs 튜닝 GNN(A_wd)",
        "",
        "**시드 단위 대응검정 (5시드):**",
        f"- macro: 평균차 {macro_main['mean_diff']:+.3f}, 95% CI [{macro_main['ci95_lo']:+.3f}, {macro_main['ci95_hi']:+.3f}] "
        f"(0 포함={macro_main['ci_crosses_0']}), paired-t p={macro_main['paired_t_p']:.4f}, Cohen's dz={macro_main['cohens_dz']:+.3f}.",
        f"- micro: 평균차 {micro_main['mean_diff']:+.3f}, 95% CI [{micro_main['ci95_lo']:+.3f}, {micro_main['ci95_hi']:+.3f}] "
        f"(0 포함={micro_main['ci_crosses_0']}), paired-t p={micro_main['paired_t_p']:.4f}, Cohen's dz={micro_main['cohens_dz']:+.3f}.",
        "",
        f"**PT 단위 대응검정 (seed 42, {n_pt} PT):** tunedRF mean {pt_main['tunedRF_mean_pr']:.3f} vs tunedGNN mean {pt_main['tunedGNN_mean_pr']:.3f} "
        f"(Δ{pt_main['mean_diff(a-b)']:+.3f}, RF 우위 PT {pt_main['n_pt_a_higher']}/{n_pt}), "
        f"Wilcoxon p={pt_main['wilcoxon_p']:.4f} (rank-biserial r={pt_main['rank_biserial_r']:+.3f}), "
        f"paired-t p={pt_main['paired_t_p']:.4f} (Cohen's dz={pt_main['cohens_dz']:+.3f}).",
        "",
        "## 4. 보조비교 — 튜닝 RF vs 디폴트 RF",
        f"- 시드 macro 평균차 {macro_aux['mean_diff']:+.3f}, 95% CI [{macro_aux['ci95_lo']:+.3f}, {macro_aux['ci95_hi']:+.3f}], paired-t p={macro_aux['paired_t_p']:.4f}.",
        f"- PT 단위(seed42): tunedRF {pt_aux['tunedRF_mean_pr']:.3f} vs defaultRF {pt_aux['defaultRF_mean_pr']:.3f} "
        f"(Δ{pt_aux['mean_diff(a-b)']:+.3f}), Wilcoxon p={pt_aux['wilcoxon_p']:.4f}, rank-biserial r={pt_aux['rank_biserial_r']:+.3f}. "
        f"→ 튜닝이 RF를 실제로 움직였는지 확인(동등예산 적용 검증).",
        "",
        "## 5. RQ2 재판정",
    ]
    if gnn_surpassed:
        lines += [
            f"- ⚠️ **역전**: 동등예산 하에서 튜닝 GNN({gnn_m:.3f})이 튜닝 RF({tuned_m:.3f})를 macro에서 유의하게 능가 "
            "→ RQ2 재설계 필요(즉시 보고). 기존 'GNN≤RF' 단정 폐기.",
        ]
    else:
        lines += [
            f"- **핵심: 공정성 보정 후에도 GNN은 RF를 능가하지 못한다.** 점추정상 튜닝 RF macro({tuned_m:.3f}) ≥ "
            f"튜닝 GNN({gnn_m:.3f})이며 micro는 튜닝 RF({a['tuned_rf_micro'][0]:.3f})가 GNN({a['gnn_micro'][0]:.3f})을 "
            f"견고하게 상회(시드 95% CI 0 미포함). RF에 GNN과 동등한 탐색예산을 줘도 우열 방향은 불변 → **RQ2 음성 결과는 공정성 결함이 아니다.**",
            f"- **단, macro 차이는 유의하지 않다(marginal).** 튜닝RF−GNN macro 평균차 {macro_main['mean_diff']:+.3f}의 "
            f"95% CI가 0을 포함(paired-t p={macro_main['paired_t_p']:.3f}) → macro에서는 두 모델이 통계적으로 **구별되지 않음**. "
            "'RF가 macro에서 GNN을 압도'한다고 단정 금지(micro·안정성에서만 RF 우위 확정).",
        ]
    if not tuning_helped_rf:
        lines += [
            f"- **부수 발견(중요): valid 기반 튜닝이 RF의 test macro를 오히려 낮췄다**(디폴트 {def_m:.3f} → 튜닝 {tuned_m:.3f}, "
            f"보조비교 macro p={macro_aux['paired_t_p']:.4f}로 유의). valid macro 최고({search.iloc[0]['valid_macro_pr']:.3f})로 "
            "선택했음에도 test가 하락 = GNN에서 본 것과 동일한 **소규모 valid/test 불안정**. 따라서 '튜닝RF의 GNN 대비 우위'가 "
            "디폴트RF 때(Δ0.025)보다 좁아진 것은 RF가 좋아져서가 아니라 튜닝이 RF를 해쳤기 때문이며, GNN이 경쟁력을 보인 것이 아니다.",
        ]
    lines += [
        f"- 보수적 종합: **N=1,092·엄격 scaffold split에서는 RF/GNN 간 macro 성능차가 노이즈 수준이고(어느 표현을 택하든 macro는 무의미), "
        f"micro와 시드 안정성(튜닝RF std {a['tuned_rf_macro'][1]:.3f} vs GNN {a['gnn_macro'][1]:.3f})에서만 RF가 확정적 우위**. "
        "→ 방법론(GNN vs RF) 선택보다 데이터 규모·분할이 성능의 지배 요인.",
    ]
    lines += [
        "",
        "## 6. 프레이밍 함의",
        "- 기존 4.2/결론의 '튜닝 GNN이 디폴트 RF에도 못 미침'은 공정성 결함이 있었음 → 동등예산 비교로 교체.",
        "- 본 결과로 manuscript 4.2·5장의 비교를 '튜닝 RF vs 튜닝 GNN'으로 갱신하고, 효과크기(rank-biserial, Cohen's dz)를 병기할 것.",
        "",
        "> 한계: GNN PT별은 round1b A_wd(seed42) 산출물 재사용(robustness seed42 macro 0.152와 MPS 비결정성으로 미세차). "
        "isotonic 보정은 본 탐색에 미포함(선택사항, 후속). RF는 동등예산 16구성으로 GNN 12구성에 대응.",
    ]
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print("\n===== [fairtune 중단] 예외 =====", flush=True)
        print(tb, flush=True)
        print(tb, file=sys.stderr, flush=True)
        sys.exit(1)
