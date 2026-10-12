"""rq8_independent_check.py — 블록 BI (docs/123 §4-5 · X3 방식) 독립 검산기.

`sap.*` · `rq8_external_validation` · `unblinding_*` · `confirmatory_*` 를 import 하지 않는다.
허용 import = __future__ sys argparse hashlib json os numpy pandas rdkit scipy sklearn.
  ① OnSIDES 원자료에서 EU∪UK 라벨 행렬을 처음부터 다시 만들어 labels_euuk.npz 의 y·cid·pt 와 바이트 비교
  ② sklearn average_precision_score 로 R8-main AP(M1b)·AP(M2b)·Δ 재계산 → |차| ≤ 1e-12
  ③ 판정 범주(118b §4) 자체 산출 → results_rq8.json 과 일치
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

RAW = "data/raw/onsides-v3.1.1/csv"
OUT = "experiments/runs/v3_rq8_external"
RF_M1b = "experiments/runs/v3_consensus_rep123/_sealed/consensus_M1b.npz"
RF_M2b = "experiments/runs/v3_consensus_rep123/_sealed/consensus_M2b.npz"
TOL = 1e-12


def rebuild_euuk():
    """118b §2 규칙 1~8 을 dict/set 로 다시 구현(파이프라인 merge 체인과 독립)."""
    pl = pd.read_csv(f"{RAW}/product_label.csv", dtype=str)
    labels = set(pl.loc[pl["source"].isin(["EU", "UK"]), "label_id"])
    vm = pd.read_csv(f"{RAW}/vocab_meddra_adverse_effect.csv", dtype=str)
    pts = set(vm.loc[vm["meddra_term_type"] == "PT", "meddra_id"])
    i2p = pd.read_csv(f"{RAW}/vocab_rxnorm_ingredient_to_product.csv", dtype=str)
    ings_of = {}
    for p, i in zip(i2p["product_id"], i2p["ingredient_id"]):
        ings_of.setdefault(p, set()).add(i)
    p2r = pd.read_csv(f"{RAW}/product_to_rxnorm.csv", dtype=str)
    label_ings = {}
    for lab, prod in zip(p2r["label_id"], p2r["rxnorm_product_id"]):
        s = ings_of.get(prod)
        if s is not None and len(s) == 1:
            label_ings.setdefault(lab, set()).update(s)
    pae = pd.read_csv(f"{RAW}/product_adverse_effect.csv",
                      usecols=["product_label_id", "effect_meddra_id", "match_method"], dtype=str)
    pae = pae[pae["product_label_id"].isin(labels)]
    pairs = set()
    for lab, pt, mm in zip(pae["product_label_id"], pae["effect_meddra_id"], pae["match_method"]):
        if mm == "PMB" and pt in pts:
            for ing in label_ings.get(lab, ()):
                pairs.add((ing, pt))
    i2c = pd.read_parquet("data/processed/ingredient_to_cid.parquet")
    ing2cid = {}
    for ing, cid, st in zip(i2c["ingredient_id"], i2c["cid"], i2c["mapping_status"]):
        if st == "ok":
            ing2cid.setdefault(ing, []).append(int(cid))
    c2s = pd.read_parquet("data/processed/cid_to_smiles.parquet")
    c2s = c2s[c2s["valid_flag"]]
    smi_of = {int(c): s for c, s in zip(c2s["cid"], c2s["smiles_canonical"]) if isinstance(s, str)}
    rep_of_smi = {}
    for c, s in smi_of.items():
        rep_of_smi[s] = min(c, rep_of_smi.get(s, c))
    X = pd.read_parquet("data/processed/master_X.parquet")
    Y = pd.read_parquet("data/processed/master_Y.parquet")
    xcid = [int(c) for c in X["cid"]]
    xset = set(xcid)
    ycols = [c for c in Y.columns if c != "cid"]
    pos = {}
    for ing, pt in pairs:
        for c in ing2cid.get(ing, ()):
            if c in smi_of:
                r = rep_of_smi[smi_of[c]]
                if r in xset:
                    pos.setdefault(r, set()).add(pt)
    drugs = [c for c in xcid if c in pos]
    col = {p: k for k, p in enumerate(ycols)}
    y = np.zeros((len(drugs), len(ycols)), dtype=np.int8)
    for i, c in enumerate(drugs):
        for pt in pos[c]:
            if pt in col:
                y[i, col[pt]] = 1
    return y, np.array(drugs, dtype=np.int64), np.array(ycols, dtype=str), X


def main(root):
    os.chdir(root)
    out = {"block": "BI (docs/123) 독립 검산", "tol": TOL}
    y, cid, pt, X = rebuild_euuk()
    with np.load(f"{OUT}/labels_euuk.npz", allow_pickle=False) as z:
        ry, rc, rp = z["y"], z["cid"], z["pt"]
    out["1_labels_bytes_identical"] = {
        "y": bool(y.dtype == ry.dtype and y.shape == ry.shape and y.tobytes() == ry.tobytes()),
        "cid": bool(cid.dtype == rc.dtype and cid.shape == rc.shape and cid.tobytes() == rc.tobytes()),
        "pt": bool(pt.dtype == rp.dtype and pt.shape == rp.shape and pt.tobytes() == rp.tobytes()),
        "sha256": {"y": hashlib.sha256(y.tobytes()).hexdigest(), "cid": hashlib.sha256(cid.tobytes()).hexdigest(),
                   "pt": hashlib.sha256(pt.tobytes()).hexdigest()}}

    ev = y.sum(axis=1) > 0
    ye = y[ev].astype(int)
    el = [j for j in range(ye.shape[1]) if ye[:, j].sum() >= 10 and (ye.shape[0] - ye[:, j].sum()) >= 1]
    xcid = X["cid"].astype(np.int64).values
    rows = np.array([int(np.where(xcid == c)[0][0]) for c in cid[ev]])
    preds = {}
    for name, p in (("M1b", RF_M1b), ("M2b", RF_M2b)):
        with np.load(p, allow_pickle=False) as z:
            assert np.array_equal(np.asarray(z["cid"], dtype=np.int64), xcid)
            preds[name] = np.asarray(z["consensus"], dtype=np.float64)[rows]
    ap = {m: float(np.mean([average_precision_score(ye[:, j], preds[m][:, j]) for j in el])) for m in preds}
    d = ap["M2b"] - ap["M1b"]
    R = json.load(open(f"{OUT}/results_rq8.json"))
    m = R["rows"]["R8-main"]
    out["2_R8_main"] = {"n_eval_drugs": int(ev.sum()), "n_eligible_pt": len(el),
                        "n_match": bool(int(ev.sum()) == m["n_eval_drugs"] and len(el) == m["n_eligible_pt"]),
                        "abs_diff_ap_M1b": abs(ap["M1b"] - m["ap_M1b"]), "abs_diff_ap_M2b": abs(ap["M2b"] - m["ap_M2b"]),
                        "abs_diff_delta": abs(d - m["delta"])}
    out["2_R8_main"]["within_tol"] = bool(max(out["2_R8_main"][k] for k in
                                              ("abs_diff_ap_M1b", "abs_diff_ap_M2b", "abs_diff_delta")) <= TOL)
    d1 = json.load(open("experiments/runs/v3_unblinding/results/results_full.json"))["items"]["C1"]["delta_obs"]
    if len(el) < 20 or int(ev.sum()) < 100:
        cat = "not_estimable"
    elif d != 0 and d1 != 0 and np.sign(d) == np.sign(d1):
        cat = "방향 재현"
    else:
        cat = "방향 비재현"
    out["3_verdict"] = {"independent": cat, "runner": R["verdict_R8_main"]["category"],
                        "match": cat == R["verdict_R8_main"]["category"]}
    out["all_match"] = bool(all(out["1_labels_bytes_identical"][k] for k in ("y", "cid", "pt"))
                            and out["2_R8_main"]["n_match"] and out["2_R8_main"]["within_tol"]
                            and out["3_verdict"]["match"])
    with open(f"{OUT}/independent_check.json", "w") as f:
        f.write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--root", default=".")
    main(os.path.abspath(ap_.parse_args().root))
