#!/usr/bin/env python3
"""표 8(테스트 support별 PT 층화)·표 9(분자/스캐폴드 부트스트랩) 재계산 — A_wd seed-42 정합.

입력:
  - v1_RF/results/_preds.npz              : Yte, P_RandomForest (디폴트 RF, seed 42)
  - results_improve/paper_tables/awd_seed42_preds.npz : P_awd_seed42 (A_wd seed 42 재생성)
평가 프로토콜: 301 PT(테스트 양성 ≥1), AP=average_precision_score, std=ddof0.
부트스트랩: B=2000, 분자(110) 재표집 + 스캐폴드 군집 재표집(seed 고정). diff = RF − A_wd.
산출: results_improve/paper_tables/{table8_support.csv, table9_bootstrap.csv, tables_8_9.md}
"""
import os
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import json
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from rdkit import Chem, RDLogger
from rdkit.Chem.Scaffolds import MurckoScaffold

import sys
sys.path.insert(0, os.path.dirname(__file__))
from data import ROOT, load_config

RDLogger.DisableLog("rdApp.*")
PT = os.path.join(ROOT, "v2_GNN", "results_improve", "paper_tables")


def ap_per_pt(Y, P):
    """열별 AP; 양성 없으면 nan."""
    n = Y.shape[1]
    out = np.full(n, np.nan)
    for j in range(n):
        if Y[:, j].sum() > 0:
            out[j] = average_precision_score(Y[:, j], P[:, j])
    return out


def macro_micro(Y, P):
    """macro=평가 가능한 PT(양성≥1) 기준; micro=논문 관례대로 전체 열(370) ravel."""
    ev = Y.sum(0) > 0
    ap = ap_per_pt(Y[:, ev], P[:, ev])
    macro = np.nanmean(ap)
    micro = average_precision_score(Y.ravel(), P.ravel())      # 전체 370열 ravel(표1·2·5·6 관례)
    return macro, micro


def main():
    # ---- 로드 ----
    d1 = np.load(os.path.join(ROOT, "v1_RF/results/_preds.npz"), allow_pickle=True)
    Yte_full = d1["Yte"].astype(int)                 # (110, 370)
    P_rf_full = d1["P_RandomForest"].astype(float)
    ycols = [str(c) for c in d1["ycols"]]

    da = np.load(os.path.join(PT, "awd_seed42_preds.npz"), allow_pickle=True)
    P_awd_full = da["P_awd_seed42"].astype(float)
    awd_test_macro = float(da["test_macro"]); awd_test_micro = float(da["test_micro"])
    awd_valid = float(da["valid_macro"])
    # 열 정합 확인
    assert P_awd_full.shape == P_rf_full.shape == Yte_full.shape, "shape mismatch"

    ev = Yte_full.sum(0) > 0
    n_ev = int(ev.sum())
    supp_full = Yte_full.sum(0)                        # PT별 테스트 양성수
    N = Yte_full.shape[0]

    # 점추정(전체표본)
    rf_macro, rf_micro = macro_micro(Yte_full, P_rf_full)
    aw_macro, aw_micro = macro_micro(Yte_full, P_awd_full)
    print(f"[점추정] n_ev={n_ev} | RF macro {rf_macro:.4f} micro {rf_micro:.4f} | "
          f"A_wd macro {aw_macro:.4f} micro {aw_micro:.4f} "
          f"(regen valid {awd_valid:.4f} test macro {awd_test_macro:.4f})")

    # ================= 표 8: support 층화 =================
    ap_rf = ap_per_pt(Yte_full, P_rf_full)
    ap_aw = ap_per_pt(Yte_full, P_awd_full)
    bins = [(1, 2), (3, 5), (6, 10), (11, 20), (21, 10**9)]
    labels = ["1–2", "3–5", "6–10", "11–20", "21+"]
    rows8 = []
    for (lo, hi), lab in zip(bins, labels):
        m = (supp_full >= lo) & (supp_full <= hi)
        base = float((supp_full[m] / N).mean())
        rows8.append({
            "Test positives": lab, "#PT": int(m.sum()),
            "Random baseline": round(base, 3),
            "RF AP mean": round(float(np.nanmean(ap_rf[m])), 3),
            "RF AP std": round(float(np.nanstd(ap_rf[m], ddof=0)), 3),
            "A_wd AP mean": round(float(np.nanmean(ap_aw[m])), 3),
            "A_wd AP std": round(float(np.nanstd(ap_aw[m], ddof=0)), 3),
        })
    t8 = pd.DataFrame(rows8)
    t8.to_csv(os.path.join(PT, "table8_support.csv"), index=False)
    # support 1-2 구간 통계(본문 인용)
    m12 = (supp_full >= 1) & (supp_full <= 2)
    print("\n[표 8]"); print(t8.to_string(index=False))
    print(f"  support 1-2: #PT={int(m12.sum())} base={float((supp_full[m12]/N).mean()):.3f} "
          f"RF {np.nanmean(ap_rf[m12]):.3f}±{np.nanstd(ap_rf[m12]):.3f} "
          f"A_wd {np.nanmean(ap_aw[m12]):.3f}±{np.nanstd(ap_aw[m12]):.3f}")

    # ================= 표 9: 부트스트랩 =================
    # 스캐폴드(Bemis–Murcko) 계산 — 테스트 분자
    cfg = load_config()
    X = pd.read_parquet(os.path.join(ROOT, cfg["data"]["master_x"]))
    split = json.load(open(os.path.join(ROOT, cfg["data"]["split"])))
    X["split"] = X["cid"].astype(str).map(split)
    Xte = X[X["split"] == "test"].reset_index(drop=True)
    assert len(Xte) == N, f"test rows {len(Xte)} != {N}"
    scaffs = []
    for smi in Xte["smiles_canonical"]:
        mol = Chem.MolFromSmiles(smi)
        s = MurckoScaffold.MurckoScaffoldSmiles(mol=mol) if mol else ""
        scaffs.append(s)
    scaffs = np.array(scaffs)
    uniq = np.unique(scaffs)
    print(f"\n[스캐폴드] 테스트 {N}분자 → 고유 골격 {len(uniq)}개")

    Yev = Yte_full[:, ev]                 # macro용 301 평가열
    Prf_ev = P_rf_full[:, ev]
    Paw_ev = P_awd_full[:, ev]

    def boot(diff_unit, B=2000, seed=42):
        """diff_unit='mol' → 분자 재표집; 'scaffold' → 골격 군집 재표집.
        macro=301 평가열(resample nonempty), micro=전체 370열 ravel(표1·2·5·6 관례)."""
        rng = np.random.default_rng(seed)
        if diff_unit == "scaffold":
            groups = [np.where(scaffs == u)[0] for u in uniq]
            n_units = len(groups)
        macro_d, micro_d = [], []
        for _ in range(B):
            if diff_unit == "mol":
                idx = rng.integers(0, N, size=N)
            else:
                pick = rng.integers(0, n_units, size=n_units)
                idx = np.concatenate([groups[k] for k in pick])
            Yb = Yev[idx]
            keep = Yb.sum(0) > 0
            if keep.sum() == 0:
                continue
            Yk = Yb[:, keep]
            rf_mac = np.nanmean(ap_per_pt(Yk, Prf_ev[idx][:, keep]))
            aw_mac = np.nanmean(ap_per_pt(Yk, Paw_ev[idx][:, keep]))
            rf_mic = average_precision_score(Yte_full[idx].ravel(), P_rf_full[idx].ravel())
            aw_mic = average_precision_score(Yte_full[idx].ravel(), P_awd_full[idx].ravel())
            macro_d.append(rf_mac - aw_mac)
            micro_d.append(rf_mic - aw_mic)
        macro_d = np.array(macro_d); micro_d = np.array(micro_d)
        return {
            "macro_mean": float(macro_d.mean()),
            "macro_lo": float(np.percentile(macro_d, 2.5)),
            "macro_hi": float(np.percentile(macro_d, 97.5)),
            "micro_mean": float(micro_d.mean()),
            "micro_lo": float(np.percentile(micro_d, 2.5)),
            "micro_hi": float(np.percentile(micro_d, 97.5)),
        }

    rows9 = []
    for unit, name in [("mol", f"Molecule ({N})"), ("scaffold", f"Scaffold cluster ({len(uniq)})")]:
        r = boot(unit, B=2000, seed=42 if unit == "mol" else 43)
        rows9.append({
            "Resampling unit": name,
            "macro diff (mean)": round(r["macro_mean"], 3),
            "macro 95% CI": f"[{r['macro_lo']:+.3f}, {r['macro_hi']:+.3f}]",
            "macro CI incl. 0": "Yes" if (r["macro_lo"] <= 0 <= r["macro_hi"]) else "No",
            "micro diff (mean)": round(r["micro_mean"], 3),
            "micro 95% CI": f"[{r['micro_lo']:+.3f}, {r['micro_hi']:+.3f}]",
            "micro CI incl. 0": "Yes" if (r["micro_lo"] <= 0 <= r["micro_hi"]) else "No",
        })
    t9 = pd.DataFrame(rows9)
    t9.to_csv(os.path.join(PT, "table9_bootstrap.csv"), index=False)
    print("\n[표 9]"); print(t9.to_string(index=False))

    # markdown 요약
    with open(os.path.join(PT, "tables_8_9.md"), "w") as f:
        f.write("# 표 8·표 9 재계산 (A_wd seed-42 정합)\n\n")
        f.write(f"- 점추정: RF macro {rf_macro:.4f} micro {rf_micro:.4f} | "
                f"A_wd macro {aw_macro:.4f} micro {aw_micro:.4f} "
                f"(regen valid {awd_valid:.4f})\n")
        f.write(f"- 고유 스캐폴드 {len(uniq)}/{N}\n\n")
        f.write("## 표 8\n\n"); f.write(t8.to_markdown(index=False)); f.write("\n\n")
        f.write("## 표 9\n\n"); f.write(t9.to_markdown(index=False)); f.write("\n")
    print("\n[저장]", PT)


if __name__ == "__main__":
    main()
