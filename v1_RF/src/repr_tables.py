#!/usr/bin/env python3
"""§2-D — 표 3 확장(6모델) + 쌍별 비교.

지시서 `docs/903_kci_repr_learner_separation_prompt_for_vscode.md` §2-D.

- 기존 4모델(GraphDTA-GIN / 튜닝 GNN A_wd / 튜닝 RF / 디폴트 RF) 수치는 **기존 산출물에서 재사용**
  (재학습 0). 신규 2모델(① Morgan+MLP · ② descriptor+RF)만 더해 6모델 표로 확장한다.
- 쌍별 비교 3쌍(§0): ①vs A_wd(표현만) · ①vs 디폴트RF(학습기만) · ②vs 디폴트RF(표현만).
- ★ 유의성 주장 금지 — 동일 분할 내 시드 변동일 뿐. 차이·방향·부호 일관성만 기록한다.

실행: .venv/bin/python -u v1_RF/src/repr_tables.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from data import ROOT                                  # noqa: E402

OUT = os.path.join(ROOT, "v1_RF", "results_repr")
SEEDS = [1, 2, 3, 4, 42]

ROB = os.path.join(ROOT, "v2_GNN", "results_improve", "robustness", "robustness_per_seed.csv")
FAIR = os.path.join(ROOT, "v1_RF", "results_fairtune")
GDTA = os.path.join(ROOT, "v3_Multimodal", "results", "graphdta_baseline")

# 표시명 → (macro 시드별 Series, micro 시드별 Series)
MODEL_ORDER = [
    "GraphDTA-GIN (DTA-adapted architecture)",
    "Tuned GNN (A_wd)",
    "Morgan FP + MLP (Arm 1, new)",
    "RDKit descriptor + RF (Arm 2, new)",
    "Tuned RF",
    "Default RF",
]


def _by_seed(paths, mac, mic):
    d = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True).sort_values("seed")
    return (d.set_index("seed")[mac].reindex(SEEDS),
            d.set_index("seed")[mic].reindex(SEEDS))


def collect():
    rob = pd.read_csv(ROB).sort_values("seed").set_index("seed")
    out = {}
    out["Default RF"] = (rob["rf_macro"].reindex(SEEDS), rob["rf_micro"].reindex(SEEDS))
    out["Tuned GNN (A_wd)"] = (rob["gnn_macro"].reindex(SEEDS), rob["gnn_micro"].reindex(SEEDS))
    out["Tuned RF"] = _by_seed([os.path.join(FAIR, f"seed_{s}.csv") for s in SEEDS],
                               "tuned_rf_macro", "tuned_rf_micro")
    out["GraphDTA-GIN (DTA-adapted architecture)"] = _by_seed(
        [os.path.join(GDTA, f"seed_{s}.csv") for s in SEEDS], "gdta_macro", "gdta_micro")
    out["Morgan FP + MLP (Arm 1, new)"] = _by_seed(
        [os.path.join(OUT, f"seed_{s}_mlp.csv") for s in SEEDS], "mlp_macro", "mlp_micro")
    out["RDKit descriptor + RF (Arm 2, new)"] = _by_seed(
        [os.path.join(OUT, f"seed_{s}_descrf.csv") for s in SEEDS], "descrf_macro", "descrf_micro")
    return out


def main():
    m = collect()

    # ── 시드별 원자료 (aggregate_test.csv) ─────────────────────────────────────
    rows = []
    for name in MODEL_ORDER:
        mac, mic = m[name]
        for s in SEEDS:
            rows.append({"model": name, "seed": s,
                         "macro_ap": float(mac.loc[s]), "micro_ap": float(mic.loc[s])})
    per_seed = pd.DataFrame(rows)
    per_seed.to_csv(os.path.join(OUT, "aggregate_test.csv"), index=False)

    # ── 표 3 확장 (6모델 mean ± std) ───────────────────────────────────────────
    t3 = []
    for name in MODEL_ORDER:
        mac, mic = m[name]
        t3.append({"model": name, "n_seed": len(SEEDS),
                   "macro_ap_mean": float(mac.mean()), "macro_ap_std": float(mac.std(ddof=1)),
                   "micro_ap_mean": float(mic.mean()), "micro_ap_std": float(mic.std(ddof=1)),
                   "source": "new (903)" if "new" in name else "reused (no retraining)"})
    t3 = pd.DataFrame(t3)
    t3.to_csv(os.path.join(OUT, "table3_extended.csv"), index=False)

    # ── 쌍별 비교 3쌍 ─────────────────────────────────────────────────────────
    PAIRS = [
        ("Morgan FP + MLP (Arm 1, new)", "Tuned GNN (A_wd)",
         "표현만 다름 (둘 다 신경망 학습기) — 그래프 표현의 순효과"),
        ("Morgan FP + MLP (Arm 1, new)", "Default RF",
         "학습기만 다름 (둘 다 Morgan 지문) — 신경망 학습기의 순효과"),
        ("RDKit descriptor + RF (Arm 2, new)", "Default RF",
         "표현만 다름 (둘 다 RF) — descriptor 표현의 순효과"),
    ]
    prs = []
    for a, b, why in PAIRS:
        amac, amic = m[a]
        bmac, bmic = m[b]
        dmac = (amac - bmac).astype(float)
        dmic = (amic - bmic).astype(float)
        prs.append({
            "contrast": f"{a} − {b}", "held_constant": why, "n_seed": len(SEEDS),
            "a_macro_mean": float(amac.mean()), "b_macro_mean": float(bmac.mean()),
            "macro_diff_mean": float(dmac.mean()), "macro_diff_std": float(dmac.std(ddof=1)),
            "macro_direction": "a>b" if dmac.mean() > 0 else "a<b",
            "macro_sign_consistency": f"{int((dmac > 0).sum())}/{len(SEEDS)} a>b",
            "a_micro_mean": float(amic.mean()), "b_micro_mean": float(bmic.mean()),
            "micro_diff_mean": float(dmic.mean()), "micro_diff_std": float(dmic.std(ddof=1)),
            "micro_direction": "a>b" if dmic.mean() > 0 else "a<b",
            "micro_sign_consistency": f"{int((dmic > 0).sum())}/{len(SEEDS)} a>b",
            "note": "동일 분할 내 시드 변동. 유의성 주장 아님.",
        })
    pd.DataFrame(prs).to_csv(os.path.join(OUT, "pairwise_contrasts.csv"), index=False)

    pd.set_option("display.width", 200)
    print("=== table3_extended.csv ===")
    print(t3.to_string(index=False))
    print("\n=== pairwise_contrasts.csv ===")
    print(pd.DataFrame(prs)[["contrast", "macro_diff_mean", "macro_direction", "macro_sign_consistency",
                             "micro_diff_mean", "micro_direction", "micro_sign_consistency"]].to_string(index=False))


if __name__ == "__main__":
    main()
