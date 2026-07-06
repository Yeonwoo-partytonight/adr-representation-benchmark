#!/usr/bin/env python3
"""GraphDTA SOTA 베이스라인 — v2 ADR 멀티라벨(구조-only) 동등조건 비교 + v3 약물축 검증.

교수님 지정 SOTA(GraphDTA, Nguyen 2021)의 약물 그래프 브랜치 2종(GIN / GAT-GCN)을
v2와 100% 동일한 데이터·split·라벨·평가 PT(301)·프로토콜·5시드[1,2,3,4,42]로 비교한다.

[아키텍처 효과 분리]
- 입력 그래프 피처 = v2 graph_features.py 그대로(동일 atom/bond) → 차이는 '아키텍처'로만.
- 학습 레시피 = v2 최적 A_wd와 동일(focal γ2 + sqrt pos_weight + weight_decay 1e-4,
  Adam lr 1e-3, batch 32, epochs 200, patience 30) → 차이는 네트워크 구조뿐.
- 모델 선택 = valid macro PR-AUC 로만(seed 42), 선택 구성을 5시드 재학습. test로 선택 금지.

[판정] GraphDTA가 (i) v2 GIN(A_wd)을 능가하는지, (ii) 튜닝 RF를 능가하는지 둘 다.
PT별 대응검정(Wilcoxon+paired t) + 효과크기(rank-biserial r, Cohen's dz). 방향 무관 정직 보고.

[재사용] v2_GNN/src(data, graph_features, train, evaluate) + v1 결과 CSV. GNN/RF 재학습 없음.
GraphDTA 약물 인코더는 drug_branch.GraphDTAClassifier로 v3 멀티모달 약물 축에 그대로 재사용
(단백질 축은 ProteinEncoderStub 인터페이스로 배선만, 현재 비활성).

산출: v3_Multimodal/results/graphdta_baseline/
실행: PYTORCH_ENABLE_MPS_FALLBACK=1 python -u v3_Multimodal/src/train_graphdta.py 2>&1 | tee \
        v3_Multimodal/results/graphdta_baseline/run.log
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import sys
import json
import glob
import traceback
import numpy as np
import pandas as pd
import torch
from scipy.stats import wilcoxon, ttest_rel, rankdata, t as tdist
from torch_geometric.loader import DataLoader

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "v2_GNN", "src"))   # v2 모듈 재사용

from data import load_config, build_graphs                # noqa: E402  (v2_GNN/src)
from graph_features import ATOM_FDIM                       # noqa: E402
from train import set_seed, get_device, compute_pos_weight, FocalLoss, predict_proba, macro_pr_auc  # noqa: E402
from evaluate import per_pt_metrics, aggregate            # noqa: E402  (v2 평가 프로토콜 동일)
from drug_branch import build_graphdta                    # noqa: E402

OUT = os.path.join(ROOT, "v3_Multimodal", "results", "graphdta_baseline")
os.makedirs(OUT, exist_ok=True)
SEEDS = [1, 2, 3, 4, 42]
THR = 0.5
# 학습 레시피 = v2 A_wd 동일(아키텍처만 변수)
EPOCHS, PATIENCE, BATCH, LR, WD, GAMMA = 200, 30, 32, 1e-3, 1e-4, 2.0
VARIANTS = [
    {"name": "graphdta_gin",    "arch": "gin"},      # GraphDTA GINConvNet (Davis 최적)
    {"name": "graphdta_gatgcn", "arch": "gatgcn"},   # GraphDTA GAT_GCN (KIBA 최적)
]

# v2/v1 재사용 산출물(재학습 없음)
ROB = os.path.join(ROOT, "v2_GNN", "results_improve", "robustness")               # gnn(A_wd)/rf(default) 5시드
GNN_PERPT = os.path.join(ROOT, "v2_GNN", "results_improve", "round1b", "metrics_per_pt.csv")  # A_wd seed42 PT별
TUNED_PERPT = os.path.join(ROOT, "v1_RF", "results_fairtune", "perpt_seed42.csv")             # 튜닝RF seed42 PT별
FAIR = os.path.join(ROOT, "v1_RF", "results_fairtune")                            # tuned RF 5시드


def log(m):
    print(m, flush=True)


def free_mem(device):
    import gc
    gc.collect()
    try:
        if str(device) == "mps":
            torch.mps.empty_cache()
        elif str(device) == "cuda":
            torch.cuda.empty_cache()
    except Exception:
        pass


def train_graphdta_variant(cfg, data, device, arch, seed, log=log):
    """A_wd 레시피로 GraphDTA(arch) 학습. valid macro PR-AUC early stopping → best로 test 예측."""
    n_out = len(data["ycols"])
    set_seed(seed)
    tr = DataLoader(data["graphs"]["train"], batch_size=BATCH, shuffle=True)
    va = DataLoader(data["graphs"]["valid"], batch_size=BATCH)
    te = DataLoader(data["graphs"]["test"], batch_size=BATCH)

    model = build_graphdta(arch, ATOM_FDIM, n_out, dropout=0.2).to(device)
    pw = torch.sqrt(compute_pos_weight(data["graphs"]["train"], n_out)).to(device)   # sqrt pos_weight
    criterion = FocalLoss(gamma=GAMMA, pos_weight=pw)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WD)

    best_v, best_state, best_ep, wait = -1.0, None, 0, 0
    for ep in range(1, EPOCHS + 1):
        model.train(); tot = 0.0
        for batch in tr:
            batch = batch.to(device)
            opt.zero_grad()
            loss = criterion(model(batch), batch.y.view(-1, n_out))
            loss.backward(); opt.step()
            tot += float(loss) * batch.num_graphs
        Pva, Yva = predict_proba(model, va, device, n_out)
        vmac = macro_pr_auc(Yva, Pva)
        if vmac > best_v:
            best_v, best_ep = vmac, ep
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
        if ep % 20 == 0 or ep == 1:
            log(f"    [{arch} s{seed}] ep {ep:3d} loss {tot/len(data['graphs']['train']):.4f} "
                f"validMacro {vmac:.4f} best {best_v:.4f}@{best_ep}")
        if wait >= PATIENCE:
            log(f"    [{arch} s{seed}] early stop @ep{ep} (best {best_v:.4f}@{best_ep})")
            break
    model.load_state_dict(best_state)
    Pte, Yte = predict_proba(model, te, device, n_out)
    return {"valid": best_v, "best_ep": best_ep,
            "P_test": Pte.astype(np.float32), "Yte": Yte.astype(np.int8)}


# ---------- 통계 헬퍼(효과크기 병기) ----------
def rank_biserial(diff):
    d = diff[diff != 0]
    if len(d) == 0:
        return float("nan")
    r = rankdata(np.abs(d))
    Wp, Wm = r[d > 0].sum(), r[d < 0].sum()
    return float((Wp - Wm) / (Wp + Wm))


def cohens_dz(diff):
    sd = diff.std(ddof=1)
    return float(diff.mean() / sd) if sd > 0 else float("nan")


def pt_paired(label, a, b, a_name, b_name):
    diff = a - b
    w_stat, w_p = wilcoxon(a, b)
    t_stat, t_p = ttest_rel(a, b)
    return {"comparison": label, "a": a_name, "b": b_name, "n_pt": len(diff),
            f"{a_name}_mean_pr": float(a.mean()), f"{b_name}_mean_pr": float(b.mean()),
            "mean_diff(a-b)": float(diff.mean()), "median_diff(a-b)": float(np.median(diff)),
            "n_pt_a_higher": int((diff > 0).sum()),
            "wilcoxon_p": float(w_p), "rank_biserial_r": rank_biserial(diff),
            "paired_t_p": float(t_p), "cohens_dz": cohens_dz(diff),
            "direction": "a>b" if diff.mean() > 0 else "a<=b"}


def seed_csv(name):
    return os.path.join(OUT, f"seed_{name}.csv")


def main():
    cfg = load_config()
    device = get_device(cfg)
    log(f"[graphdta] device={device} | 학습레시피=A_wd(focal γ2+sqrt pw+wd 1e-4, lr {LR}, ep {EPOCHS}) | seeds {SEEDS}")
    data = build_graphs(cfg)
    ycols = data["ycols"]

    # ── STEP 1: seed 42 valid 로 GraphDTA 2종 비교 → best 선택(test 미사용) ──
    sel_path = os.path.join(OUT, "valid_selection.csv")
    if os.path.exists(sel_path) and os.path.exists(os.path.join(OUT, "_best.json")):
        sel = pd.read_csv(sel_path)
        best = json.load(open(os.path.join(OUT, "_best.json")))["best"]
        log(f"[select] 기존 선택 재사용: best={best}")
    else:
        rows = []
        for v in VARIANTS:
            log(f"  === valid 선택: {v['name']} (seed 42) ===")
            r = train_graphdta_variant(cfg, data, device, v["arch"], 42)
            rows.append({"variant": v["name"], "arch": v["arch"],
                         "valid_macro_pr": r["valid"], "best_ep": r["best_ep"]})
            log(f"  → {v['name']} valid macroPR {r['valid']:.4f} @ep{r['best_ep']}")
            free_mem(device)
        sel = pd.DataFrame(rows).sort_values("valid_macro_pr", ascending=False).reset_index(drop=True)
        sel.to_csv(sel_path, index=False)
        best = sel.iloc[0]["variant"]
        json.dump({"best": best, "selected_by": "valid_macro_pr"},
                  open(os.path.join(OUT, "_best.json"), "w"))
        log(f"[select] valid 최적 = {best} (test 미사용)")
    best_arch = {v["name"]: v["arch"] for v in VARIANTS}[best]

    # ── STEP 2: best 5시드 재학습 → test (idempotent) ──
    perpt_path = os.path.join(OUT, "perpt_seed42.csv")
    for seed in SEEDS:
        if os.path.exists(seed_csv(seed)) and (seed != 42 or os.path.exists(perpt_path)):
            log(f"[seed {seed}] 기존 seed_{seed}.csv 재사용")
            continue
        log(f"  === {best} 5시드 재학습: seed {seed} ===")
        r = train_graphdta_variant(cfg, data, device, best_arch, seed)
        agg, df = (lambda d: (aggregate(r["Yte"].astype(int), r["P_test"], d, THR), d))(
            per_pt_metrics(r["Yte"].astype(int), r["P_test"], ycols, THR))
        pd.DataFrame([{"seed": seed, "gdta_macro": agg["macro_pr_auc"], "gdta_micro": agg["micro_pr_auc"],
                       "macro_roc": agg["macro_roc_auc"], "hamming": agg["hamming_accuracy"]}]
                     ).to_csv(seed_csv(seed), index=False)
        log(f"[seed {seed}] {best} macroPR {agg['macro_pr_auc']:.4f} microPR {agg['micro_pr_auc']:.4f} → seed_{seed}.csv")
        if seed == 42:
            df[["meddra_pt", "n_pos_test", "pr_auc"]].to_csv(perpt_path, index=False)
        free_mem(device)

    # ── STEP 3: 집계 + 4모델 비교표 + PT별 대응검정(효과크기) ──
    gdta = pd.concat([pd.read_csv(seed_csv(s)) for s in SEEDS], ignore_index=True).sort_values("seed")
    rob = pd.concat([pd.read_csv(os.path.join(ROB, f"seed_{s}.csv")) for s in SEEDS], ignore_index=True).sort_values("seed")
    tuned = pd.concat([pd.read_csv(os.path.join(FAIR, f"seed_{s}.csv")) for s in SEEDS], ignore_index=True).sort_values("seed")
    m = gdta.merge(rob, on="seed").merge(tuned, on="seed")

    def ms(col):
        v = m[col].values.astype(float)
        return float(v.mean()), float(v.std(ddof=1))

    table = {  # 모델 → (macro mean,std), (micro mean,std)
        f"GraphDTA-{best}": (ms("gdta_macro"), ms("gdta_micro")),
        "tuned_RF":         (ms("tuned_rf_macro"), ms("tuned_rf_micro")),
        "tuned_GNN(A_wd)":  (ms("gnn_macro"), ms("gnn_micro")),
        "default_RF":       (ms("rf_macro"), ms("rf_micro")),
    }
    pd.DataFrame([{"model": k, "macro_pr_mean": v[0][0], "macro_pr_std": v[0][1],
                   "micro_pr_mean": v[1][0], "micro_pr_std": v[1][1], "n_seed": len(m)}
                  for k, v in table.items()]).to_csv(os.path.join(OUT, "comparison_table.csv"), index=False)

    # 시드 단위 대응검정(주: GraphDTA vs A_wd, GraphDTA vs tunedRF) — macro/micro
    def seed_paired(a, b, label):
        a, b = np.asarray(a, float), np.asarray(b, float); d = a - b; n = len(d)
        se = d.std(ddof=1) / np.sqrt(n); tc = float(tdist.ppf(0.975, n - 1))
        _, tp = ttest_rel(a, b)
        try:
            _, wp = wilcoxon(a, b); wp = float(wp)
        except ValueError:
            wp = float("nan")
        return {"comparison": label, "n_seed": n, "mean_diff(a-b)": float(d.mean()),
                "ci95_lo": float(d.mean() - tc * se), "ci95_hi": float(d.mean() + tc * se),
                "ci_crosses_0": bool((d.mean() - tc * se) < 0 < (d.mean() + tc * se)),
                "paired_t_p": float(tp), "cohens_dz": cohens_dz(d), "wilcoxon_p": wp}
    seed_tests = pd.DataFrame([
        seed_paired(m["gdta_macro"], m["gnn_macro"], "MACRO: GraphDTA vs tunedGNN(A_wd)"),
        seed_paired(m["gdta_micro"], m["gnn_micro"], "MICRO: GraphDTA vs tunedGNN(A_wd)"),
        seed_paired(m["gdta_macro"], m["tuned_rf_macro"], "MACRO: GraphDTA vs tunedRF"),
        seed_paired(m["gdta_micro"], m["tuned_rf_micro"], "MICRO: GraphDTA vs tunedRF"),
    ])
    seed_tests.to_csv(os.path.join(OUT, "aggregate_seed_paired.csv"), index=False)

    # PT 단위(seed 42) 대응검정 + 효과크기: vs A_wd, vs tunedRF
    g_pt = pd.read_csv(perpt_path)[["meddra_pt", "n_pos_test", "pr_auc"]].rename(columns={"pr_auc": "gdta"})
    awd = pd.read_csv(GNN_PERPT)[["meddra_pt", "pr_auc"]].rename(columns={"pr_auc": "awd"})
    trf = pd.read_csv(TUNED_PERPT)[["meddra_pt", "pr_auc"]].rename(columns={"pr_auc": "trf"})
    for d in (g_pt, awd, trf):
        d["meddra_pt"] = d["meddra_pt"].astype(str)
    pt = g_pt.merge(awd, on="meddra_pt").merge(trf, on="meddra_pt").dropna(subset=["gdta", "awd", "trf"])
    sig = pd.DataFrame([
        pt_paired(f"PT: GraphDTA vs tunedGNN(A_wd) [seed42, {len(pt)}PT]", pt["gdta"].values, pt["awd"].values, "GraphDTA", "tunedGNN"),
        pt_paired(f"PT: GraphDTA vs tunedRF [seed42, {len(pt)}PT]", pt["gdta"].values, pt["trf"].values, "GraphDTA", "tunedRF"),
    ])
    sig.to_csv(os.path.join(OUT, "significance_graphdta.csv"), index=False)

    write_summary(best, sel, table, seed_tests, sig, len(pt), len(m), str(device))
    log("[완료] graphdta_baseline/ 산출 완료")


def write_summary(best, sel, table, seed_tests, sig, n_pt, n_seed, device):
    st = {r["comparison"]: r for _, r in seed_tests.iterrows()}
    sg = {r["comparison"]: r for _, r in sig.iterrows()}
    gmac = table[f"GraphDTA-{best}"][0]; gmic = table[f"GraphDTA-{best}"][1]
    awd_mac = table["tuned_GNN(A_wd)"][0]; trf_mac = table["tuned_RF"][0]
    s_awd = st["MACRO: GraphDTA vs tunedGNN(A_wd)"]; s_trf = st["MACRO: GraphDTA vs tunedRF"]
    s_awd_mi = st["MICRO: GraphDTA vs tunedGNN(A_wd)"]; s_trf_mi = st["MICRO: GraphDTA vs tunedRF"]
    pt_awd = [r for _, r in sig.iterrows() if "A_wd" in r["comparison"]][0]
    pt_trf = [r for _, r in sig.iterrows() if "tunedRF" in r["comparison"]][0]

    def fmt(t):
        return f"{t[0]:.3f} ± {t[1]:.3f}"

    # 판정: GraphDTA가 A_wd / tunedRF를 능가했나(점추정 + macro 유의)
    beats_awd = gmac[0] > awd_mac[0]
    beats_awd_sig = beats_awd and not bool(s_awd["ci_crosses_0"])
    beats_trf = gmac[0] > trf_mac[0]
    beats_trf_sig = beats_trf and not bool(s_trf["ci_crosses_0"])

    lines = [
        "# GraphDTA SOTA 베이스라인 — v2 ADR 멀티라벨(구조-only) 동등조건 비교",
        "",
        f"> 교수님 지정 SOTA(GraphDTA, Nguyen 2021) 약물 그래프 브랜치 2종(GIN/GAT-GCN)을 "
        f"v2와 동일 데이터·split·라벨·평가 PT(301)·프로토콜·5시드{SEEDS}로 비교. "
        f"입력 피처=v2 graph_features 재사용, 학습레시피=A_wd 동일(focal γ2+sqrt pw+wd 1e-4) → **차이는 아키텍처뿐**. "
        f"device={device}.",
        f"> valid 기준 선택(seed42, test 미사용) = **{best}**. (선택 로그: valid_selection.csv)",
        "",
        "## valid 선택 로그 (seed 42, valid macro PR-AUC)",
        "",
        "| GraphDTA 변형 | arch | valid macro PR-AUC |",
        "|---|---|---|",
    ]
    for _, r in sel.iterrows():
        star = " ★" if r["variant"] == best else ""
        lines.append(f"| {r['variant']}{star} | {r['arch']} | {r['valid_macro_pr']:.4f} |")
    lines += [
        "",
        f"## 비교표 (test, {n_seed}시드 mean ± std)",
        "",
        "| 모델 | macro PR-AUC | micro PR-AUC |",
        "|---|---|---|",
        f"| **GraphDTA-{best}** | {fmt(gmac)} | {fmt(gmic)} |",
        f"| 튜닝 RF | {fmt(table['tuned_RF'][0])} | {fmt(table['tuned_RF'][1])} |",
        f"| 튜닝 GNN (A_wd) | {fmt(awd_mac)} | {fmt(table['tuned_GNN(A_wd)'][1])} |",
        f"| 디폴트 RF | {fmt(table['default_RF'][0])} | {fmt(table['default_RF'][1])} |",
        "",
        "## 대응검정 + 효과크기",
        "",
        "**시드 단위(5시드):**",
        f"- vs 튜닝 GNN(A_wd) — macro Δ{s_awd['mean_diff(a-b)']:+.3f} 95%CI[{s_awd['ci95_lo']:+.3f},{s_awd['ci95_hi']:+.3f}] "
        f"(0포함={s_awd['ci_crosses_0']}, t p={s_awd['paired_t_p']:.3f}, dz={s_awd['cohens_dz']:+.2f}); "
        f"micro Δ{s_awd_mi['mean_diff(a-b)']:+.3f} (0포함={s_awd_mi['ci_crosses_0']}, t p={s_awd_mi['paired_t_p']:.3f}).",
        f"- vs 튜닝 RF — macro Δ{s_trf['mean_diff(a-b)']:+.3f} 95%CI[{s_trf['ci95_lo']:+.3f},{s_trf['ci95_hi']:+.3f}] "
        f"(0포함={s_trf['ci_crosses_0']}, t p={s_trf['paired_t_p']:.3f}, dz={s_trf['cohens_dz']:+.2f}); "
        f"micro Δ{s_trf_mi['mean_diff(a-b)']:+.3f} (0포함={s_trf_mi['ci_crosses_0']}, t p={s_trf_mi['paired_t_p']:.3f}).",
        "",
        f"**PT 단위(seed 42, {n_pt}PT):**",
        f"- vs A_wd: GraphDTA {pt_awd['GraphDTA_mean_pr']:.3f} vs {pt_awd['tunedGNN_mean_pr']:.3f} "
        f"(Δ{pt_awd['mean_diff(a-b)']:+.3f}, GraphDTA 우위 {pt_awd['n_pt_a_higher']}/{n_pt}), "
        f"Wilcoxon p={pt_awd['wilcoxon_p']:.4f}, rank-biserial r={pt_awd['rank_biserial_r']:+.3f}, dz={pt_awd['cohens_dz']:+.3f}.",
        f"- vs 튜닝RF: GraphDTA {pt_trf['GraphDTA_mean_pr']:.3f} vs {pt_trf['tunedRF_mean_pr']:.3f} "
        f"(Δ{pt_trf['mean_diff(a-b)']:+.3f}, GraphDTA 우위 {pt_trf['n_pt_a_higher']}/{n_pt}), "
        f"Wilcoxon p={pt_trf['wilcoxon_p']:.4f}, rank-biserial r={pt_trf['rank_biserial_r']:+.3f}, dz={pt_trf['cohens_dz']:+.3f}.",
        "",
        "## 판정 (방향 무관 정직 보고)",
    ]
    # (i) vs v2 GIN(A_wd)
    if beats_awd_sig:
        lines.append(f"- (i) **GraphDTA가 v2 GIN(A_wd)을 macro에서 유의하게 능가**(Δ{s_awd['mean_diff(a-b)']:+.3f}). v2 결론 함의 즉시 검토 필요.")
    elif beats_awd:
        lines.append(f"- (i) GraphDTA가 v2 GIN(A_wd)보다 macro 점추정 우위이나 비유의(95%CI 0 포함) → 구별 불가 수준.")
    else:
        lines.append(f"- (i) **GraphDTA도 v2 GIN(A_wd)을 능가하지 못함**(macro Δ{s_awd['mean_diff(a-b)']:+.3f}).")
    # (ii) vs tuned RF
    if beats_trf_sig:
        lines.append(f"- (ii) ⚠️ **GraphDTA가 튜닝 RF를 macro에서 유의하게 능가**(Δ{s_trf['mean_diff(a-b)']:+.3f}) → 원고 4.2 'SOTA 미비교' 한계 갱신 후보. 즉시 보고.")
    elif beats_trf:
        lines.append(f"- (ii) GraphDTA가 튜닝 RF보다 macro 점추정 우위이나 비유의 → 구별 불가.")
    else:
        lines.append(f"- (ii) **GraphDTA도 튜닝 RF(지문)를 능가하지 못함**(macro Δ{s_trf['mean_diff(a-b)']:+.3f}). "
                     "→ 최신 SOTA 아키텍처조차 이 규모·분할에서 지문 RF를 못 넘음 = 음성결과·데이터지배 논지 강화.")
    lines += [
        "",
        "> 과장 금지: macro(구별 가능 여부)와 micro·안정성을 구분해 해석. GraphDTA PT별은 seed42 기준, "
        "A_wd/튜닝RF PT별 산출물 재사용(robustness/round1b·fairtune; MPS 비결정성으로 미세차 가능).",
        "",
        "## v3 약물 축 재사용 인터페이스",
        "- `drug_branch.GraphDTAClassifier(protein_encoder=None)` = 본 약물-only 베이스라인.",
        "- v3: `ProteinEncoderStub`를 ProtBERT/1D-CNN 인코더로 교체해 `protein_encoder=`에 주입하면 "
        "약물 embed ⊕ 단백질 embed → head로 멀티모달이 활성화된다(현재 배선만, 비활성).",
    ]
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print("\n===== [graphdta 중단] 예외 =====", flush=True)
        print(tb, flush=True)
        print(tb, file=sys.stderr, flush=True)
        sys.exit(1)
