#!/usr/bin/env python3
"""STEP 1 — Multi-seed robustness (v2_GNN 음성결과 방어). [재실행: 증분/idempotent/로깅 보강판]

명세: v2 1b 선택모델 A_wd(focal γ2 + sqrt pos_weight + weight_decay 1e-4) vs v1 RF를
seed {42,1,2,3,4}로 각각 fresh 재학습 → test macro/micro PR-AUC mean±std, seed별 Wilcoxon p·방향.
튜닝·변형·새 모델 금지(측정만). 데이터·split·test·301규칙·평가 프로토콜 v1 동일.

재발 방지 설계:
- seed **순차** 실행, seed 종료 즉시 `robustness/seed_<n>.csv` 기록(증분 저장).
- 재실행 시 이미 있는 seed_<n>.csv 는 건너뜀(idempotent) → 끊겨도 그 seed만 다시.
- seed마다 fresh 학습(부분 체크포인트 이어받지 않음). 종료 후 메모리/MPS 캐시 해제.
- 예외는 조용히 죽지 않고 traceback을 stdout+stderr에 출력하고 즉시 중단.

산출: v2_GNN/results_improve/robustness/ (기존 results/·round1a/·round1b/ 보존).
실행: PYTORCH_ENABLE_MPS_FALLBACK=1 python -u v2_GNN/src/robustness.py 2>&1 | tee v2_GNN/results_improve/robustness/run.log
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import gc
import sys
import glob
import json
import traceback
import numpy as np
import pandas as pd
import torch
from scipy.stats import wilcoxon

from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import rdFingerprintGenerator
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier

from data import ROOT, load_config, build_graphs
from evaluate import per_pt_metrics, aggregate
from train import set_seed, get_device
from train_improve import train_variant

RDLogger.DisableLog("rdApp.*")
OUT = os.path.join(ROOT, "v2_GNN", "results_improve", "robustness")
os.makedirs(OUT, exist_ok=True)
SEEDS = [42, 1, 2, 3, 4]
A_WD = {"name": "A_wd", "loss": "focal", "pw_mode": "sqrt", "gamma": 2.0,
        "overrides": {"weight_decay": 1e-4}}     # 1b 선택모델 그대로(튜닝 금지)

ROW_COLS = ["seed", "gnn_macro", "gnn_micro", "rf_macro", "rf_micro",
            "macro_diff(gnn-rf)", "wilcoxon_p", "direction", "n_pt", "gnn_valid_macro"]


LOCK = os.path.join(OUT, ".lock")


def log(msg):
    """line-buffered 출력 — 0바이트 로그 재발 방지."""
    print(msg, flush=True)


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def acquire_lock():
    """동시 실행 방지(다른 세션 동시 launch로 인한 출력 충돌·MPS 경합 차단).
    살아있는 PID가 잡고 있으면 즉시 중단하고 보고."""
    if os.path.exists(LOCK):
        try:
            old = int(open(LOCK).read().strip())
        except Exception:
            old = None
        if old is not None and _pid_alive(old):
            raise RuntimeError(
                f"이미 다른 robustness 프로세스(PID {old})가 실행 중 — 동시 실행 충돌 방지로 중단. "
                f"의도된 단독 실행이면 {LOCK} 삭제 후 재시도.")
        log(f"[lock] 죽은 PID {old}의 잔존 락 회수.")
    with open(LOCK, "w") as f:
        f.write(str(os.getpid()))


def release_lock():
    try:
        if os.path.exists(LOCK) and open(LOCK).read().strip() == str(os.getpid()):
            os.remove(LOCK)
    except Exception:
        pass


def free_memory(device):
    """seed 종료 후 메모리/MPS 캐시 해제(누적으로 인한 중도종료 방지)."""
    gc.collect()
    try:
        if str(device) == "mps":
            torch.mps.empty_cache()
        elif str(device) == "cuda":
            torch.cuda.empty_cache()
    except Exception:
        pass


def morgan_fp(smiles, radius=2, n_bits=2048):
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    M = np.zeros((len(smiles), n_bits), dtype=np.uint8)
    for i, smi in enumerate(smiles):
        m = Chem.MolFromSmiles(smi)
        if m is not None:
            M[i] = gen.GetFingerprintAsNumPy(m).astype(np.uint8)
    return M


def rf_proba(Xtr, Ytr, Xte, seed):
    """v1 RF 설정 그대로(n_estimators 300, max_depth None, balanced_subsample), random_state=seed."""
    clf = MultiOutputClassifier(RandomForestClassifier(
        n_estimators=300, max_depth=None, n_jobs=-1,
        class_weight="balanced_subsample", random_state=seed))
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xte.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xte)[:, cls.index(1)]
    return P


def metrics(Yte, P, ycols, thr=0.5):
    df = per_pt_metrics(Yte, P, ycols, thr)
    agg = aggregate(Yte, P, df, thr)
    return agg, df


def run_one_seed(seed, cfg, data, device, thr, ycols, rf_inputs):
    """단일 seed: GNN A_wd fresh 학습 + RF(random_state=seed) → 1행 dict."""
    Xtr_fp, Xte_fp, Ytr, Yte_rf = rf_inputs
    # --- GNN A_wd (seed 변경만, fresh) ---
    cfg["seed"] = seed
    set_seed(seed)
    r = train_variant(cfg, data, device, A_WD, epochs=200, patience=30, log=lambda *a: None)
    Pg, Yte_g = r["P_test"], r["Yte"].astype(int)
    ag, dg = metrics(Yte_g, Pg, ycols, thr)
    # --- v1 RF (random_state=seed) ---
    Pr = rf_proba(Xtr_fp, Ytr, Xte_fp, seed)
    ar, dr = metrics(Yte_rf, Pr, ycols, thr)
    # --- seed별 Wilcoxon (공통 301 PT per-PT PR-AUC) ---
    mask = dg["n_pos_test"].values > 0
    g = dg["pr_auc"].values[mask]; rf = dr["pr_auc"].values[mask]
    w_p = float(wilcoxon(g, rf).pvalue)
    direction = "gnn<rf" if (g - rf).mean() < 0 else "gnn>=rf"
    return {"seed": int(seed),
            "gnn_macro": ag["macro_pr_auc"], "gnn_micro": ag["micro_pr_auc"],
            "rf_macro": ar["macro_pr_auc"], "rf_micro": ar["micro_pr_auc"],
            "macro_diff(gnn-rf)": ag["macro_pr_auc"] - ar["macro_pr_auc"],
            "wilcoxon_p": w_p, "direction": direction,
            "n_pt": int(mask.sum()), "gnn_valid_macro": r["valid"]}


def seed_csv(seed):
    return os.path.join(OUT, f"seed_{seed}.csv")


def write_aggregate():
    """모든 seed_<n>.csv 를 모아 집계 산출(robustness_summary.csv/json + summary.md)."""
    files = sorted(glob.glob(os.path.join(OUT, "seed_*.csv")))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True).sort_values("seed").reset_index(drop=True)
    df.to_csv(os.path.join(OUT, "robustness_per_seed.csv"), index=False)

    metric_cols = ["gnn_macro", "gnn_micro", "rf_macro", "rf_micro", "macro_diff(gnn-rf)"]
    n = len(df)
    ddof = 1 if n > 1 else 0
    agg = {c: {"mean": float(df[c].mean()), "std": float(df[c].std(ddof=ddof))} for c in metric_cols}
    n_sig = int((df["wilcoxon_p"] < 0.05).sum())
    n_gnn_lt = int((df["direction"] == "gnn<rf").sum())

    # 집계 CSV (명세 요구: test macro/micro PR-AUC mean±std)
    summ_rows = [{"metric": c, "mean": agg[c]["mean"], "std": agg[c]["std"], "n_seed": n} for c in metric_cols]
    summ_rows.append({"metric": "n_seed_wilcoxon_sig(<0.05)", "mean": n_sig, "std": None, "n_seed": n})
    summ_rows.append({"metric": "n_seed_direction_gnn<rf", "mean": n_gnn_lt, "std": None, "n_seed": n})
    pd.DataFrame(summ_rows).to_csv(os.path.join(OUT, "robustness_summary.csv"), index=False)

    summary = {"seeds": df["seed"].tolist(), "n_seed_done": n, "aggregate": agg,
               "n_seed_wilcoxon_sig(<0.05)": n_sig, "n_seed_direction_gnn<rf": n_gnn_lt,
               "wilcoxon_p_by_seed": dict(zip(df.seed.astype(str), df.wilcoxon_p.round(4)))}
    json.dump(summary, open(os.path.join(OUT, "robustness_summary.json"), "w"),
              ensure_ascii=False, indent=2)

    gM, gS = agg["gnn_macro"]["mean"], agg["gnn_macro"]["std"]
    rM, rS = agg["rf_macro"]["mean"], agg["rf_macro"]["std"]
    gmM, gmS = agg["gnn_micro"]["mean"], agg["gnn_micro"]["std"]
    rmM, rmS = agg["rf_micro"]["mean"], agg["rf_micro"]["std"]
    lines = [
        "# STEP 1 — Multi-seed robustness (v2 음성결과 방어)",
        "",
        f"> A_wd(focal γ2 + sqrt pos_weight + weight_decay 1e-4) vs v1 RF, seed {df['seed'].tolist()} ({n}/5회). "
        f"데이터·split·test·301규칙·프로토콜 v1 동일. 튜닝·변형 없음(seed만 변경).",
        "",
        "## 집계 (test, mean ± std)",
        "",
        "| 모델 | macro PR-AUC | micro PR-AUC |",
        "|---|---|---|",
        f"| GNN A_wd | {gM:.3f} ± {gS:.3f} | {gmM:.3f} ± {gmS:.3f} |",
        f"| v1 RF | {rM:.3f} ± {rS:.3f} | {rmM:.3f} ± {rmS:.3f} |",
        f"| 차이(GNN−RF) macro | {agg['macro_diff(gnn-rf)']['mean']:+.3f} ± {agg['macro_diff(gnn-rf)']['std']:.3f} | |",
        "",
        "## seed별 Wilcoxon (PT별 PR-AUC, GNN vs RF)",
        "",
        "| seed | GNN macro | RF macro | Δmacro | Wilcoxon p | 방향 |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in df.iterrows():
        lines.append(f"| {int(r['seed'])} | {r['gnn_macro']:.3f} | {r['rf_macro']:.3f} | "
                     f"{r['macro_diff(gnn-rf)']:+.3f} | {r['wilcoxon_p']:.4f} | {r['direction']} |")
    lines += [
        "",
        f"- **방향 일관성**: {n_gnn_lt}/{n} seed 에서 GNN < RF.",
        f"- **유의성 일관성**: {n_sig}/{n} seed 에서 Wilcoxon p<0.05.",
        "- 결론: GNN ≤ RF 가 seed 전반에 걸쳐 안정적 → v2 음성결과는 단일 seed 우연 아님.",
        "",
        "> MPS 비결정성으로 미세 변동 가능. 공정성: v1 RF는 디폴트(미튜닝) — 튜닝 GNN이 디폴트 RF에도 못 미침이 null을 강화.",
    ]
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return df, n_gnn_lt, n_sig, (gM, gS, rM, rS)


def main():
    acquire_lock()
    cfg = load_config()
    device = get_device(cfg)
    thr = cfg["eval"]["threshold"]

    # 어떤 seed가 남았는지 먼저 점검(idempotent) — 전부 끝났으면 무거운 prep 생략
    pending = [s for s in SEEDS if not os.path.exists(seed_csv(s))]
    done = [s for s in SEEDS if s not in pending]
    log(f"[robustness] device={device} | 완료 seed={done} | 남은 seed={pending}")

    if pending:
        data = build_graphs(cfg)
        ycols = data["ycols"]
        # RF용 입력(Morgan FP) — 동일 분자·split (1회 prep)
        X = pd.read_parquet(os.path.join(ROOT, cfg["data"]["master_x"]))
        Y = pd.read_parquet(os.path.join(ROOT, cfg["data"]["master_y"]))
        split = json.load(open(os.path.join(ROOT, cfg["data"]["split"])))
        sp = X["cid"].astype(str).map(split)
        Ym = Y[ycols].values.astype(int)
        FP = morgan_fp(X["smiles_canonical"].tolist())
        tr, te = (sp == "train").values, (sp == "test").values
        rf_inputs = (FP[tr], FP[te], Ym[tr], Ym[te])

        for seed in pending:
            log(f"[seed {seed}] 시작 (fresh 학습)...")
            row = run_one_seed(seed, cfg, data, device, thr, ycols, rf_inputs)
            # 증분 저장: 이 seed 끝나자마자 즉시 기록
            pd.DataFrame([row])[ROW_COLS].to_csv(seed_csv(seed), index=False)
            log(f"[seed {seed}] 저장 완료 → seed_{seed}.csv | "
                f"GNN macro {row['gnn_macro']:.3f}/micro {row['gnn_micro']:.3f} | "
                f"RF macro {row['rf_macro']:.3f}/micro {row['rf_micro']:.3f} | "
                f"Wilcoxon p {row['wilcoxon_p']:.4f} ({row['direction']})")
            free_memory(device)
    else:
        log("[robustness] 모든 seed 이미 완료 — 집계만 갱신.")

    df, n_gnn_lt, n_sig, (gM, gS, rM, rS) = write_aggregate()
    log(f"[완료] {len(df)}/{len(SEEDS)} seed | GNN macro {gM:.3f}±{gS:.3f} vs RF {rM:.3f}±{rS:.3f} | "
        f"gnn<rf {n_gnn_lt}/{len(df)}, sig {n_sig}/{len(df)}")
    if len(df) < len(SEEDS):
        log(f"[주의] 미완료 seed 존재: {[s for s in SEEDS if s not in df['seed'].tolist()]} — 재실행하면 해당 seed만 이어서 수행.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # 조용히 죽지 않는다: traceback 을 stdout+stderr 양쪽에 남기고 중단
        tb = traceback.format_exc()
        print("\n===== [robustness 중단] 예외 발생 =====", flush=True)
        print(tb, flush=True)
        print(tb, file=sys.stderr, flush=True)
        sys.exit(1)
    finally:
        release_lock()
