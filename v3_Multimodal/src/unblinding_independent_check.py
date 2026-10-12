"""unblinding_independent_check.py — 블록 BC (docs/118 BC-3 · 결정 X3) 독립 소형 검산기.

개봉 스크립트(`unblinding_run.py`)·SAP(`sap.*`)·프로젝트 모듈을 **import 하지 않는다**(selftest·U10 AST).
동결 문면(계획 JSON `independent_check` · docs/118 BC-3)만 보고 다시 구현한 계산으로 개봉 staging 을 대조한다.
허용 import = 표준 라이브러리 · numpy · pandas · pyarrow(pandas 경유) · sklearn · scipy · rdkit.

  --stage check      : --root --plan --staging → `<staging>/independent_check.json`(all_match · 항목별 불리언 ·
                       불일치 항목 id 만 · 값 0). 개봉 스크립트 R6 이 별도 프로세스로 호출한다.
  --stage holm_probe : stdin {"labels", "cases"} → stdout 자체 Holm 결과(합성 검사 U3 전용 · 실데이터 무관).
  --stage selftest   : import 금지 AST + 자체 함수 손계산 대조 → --out.

대조 항목 (BC-3 1~7)
  1 scaffold 군 rdkit 독립 재구성 → G · 분할 동일   2 Δ 자체 macro AP |차| ≤ tol
  3 perm 앞 n 개 독립 재생성 |차| ≤ tol · 전체 perm 으로 p 정확 일치(기준 Δ = 검산기 자체 Δ)
  4 BCa: staging boot + 독립 jackknife → ci_bca |차| ≤ tol · status 일치
  5 ④ max · ⑧ (1+c)/(B+1)   6 Holm 판1·판2 자체 구현 정확 일치   7 판정·TOST·BH 라벨 일치
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import ast
import hashlib
import json
import os

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy.stats import norm
from sklearn.metrics import average_precision_score


# ── 동결 문면 재구현 ─────────────────────────────────────────────────────────
def scaffold_str(smi):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False)
    except Exception:            # noqa: BLE001 — 문면: 실패 → ''
        return ""


def my_macro_ap(y, P, cols):
    vals = []
    for j in cols:
        if y[:, j].sum() > 0:
            vals.append(average_precision_score(y[:, j], P[:, j]))
    return float(np.mean(vals)) if vals else float("nan")


def my_perm(cB, cT, y, groups, cols, seed, n):
    """동결 프로토콜: default_rng(seed) · 군 순서 = np.unique · 동전 = rng.random(G) < 0.5 · 교환 군은 arm 통째 교환."""
    uniq = np.unique(groups)
    gi = np.searchsorted(uniq, groups)
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for b in range(n):
        flip = rng.random(len(uniq)) < 0.5
        sr = flip[gi][:, None]
        out[b] = my_macro_ap(y, np.where(sr, cB, cT), cols) - my_macro_ap(y, np.where(sr, cT, cB), cols)
    return out


def my_p(perm, delta, eps):
    return (1.0 + float(np.sum(np.abs(perm) >= abs(delta) - eps))) / (len(perm) + 1.0)


def my_jackknife(cB, cT, y, groups, cols, unit):
    N = y.shape[0]
    if unit == "drug":
        units = [np.delete(np.arange(N), i) for i in range(N)]
    else:
        uniq = np.unique(groups)
        units = [np.where(groups != g)[0] for g in uniq]
    return np.array([my_macro_ap(y[r], cT[r], cols) - my_macro_ap(y[r], cB[r], cols) for r in units])


def my_bca(boot, theta, jack, alpha):
    boot = np.asarray(boot, dtype=float)
    boot = boot[~np.isnan(boot)]
    if len(boot) < 2:
        return None, None, "bca_failed_too_few_B"
    prop = float(np.mean(boot < theta))
    if prop <= 0.0 or prop >= 1.0:
        return None, None, "bca_failed_z0_degenerate"
    if jack.size < 2 or np.isnan(jack).any():
        return None, None, "bca_failed_jackknife_undefined"
    z0 = norm.ppf(prop)
    jb = jack.mean()
    den = 6.0 * (np.sum((jb - jack) ** 2) ** 1.5)
    a = np.sum((jb - jack) ** 3) / den if den != 0 else 0.0
    if not np.isfinite(a):
        return None, None, "bca_failed_accel_degenerate"
    qs = []
    for z in (norm.ppf(alpha / 2), norm.ppf(1 - alpha / 2)):
        d = 1 - a * (z0 + z)
        if d == 0:
            return None, None, "bca_failed_accel_degenerate"
        qs.append(norm.cdf(z0 + (z0 + z) / d))
    return float(np.percentile(boot, 100 * qs[0])), float(np.percentile(boot, 100 * qs[1])), "bca"


def my_holm(pv, alpha):
    """오름차순 안정 정렬 · 가중 (m − rank) · 누적 max · min 1 · reject = 조정 p < α."""
    m = len(pv)
    order = sorted(range(m), key=lambda i: (pv[i], i))
    adj = [0.0] * m
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * pv[i])
        adj[i] = min(1.0, run)
    return adj, [a < alpha for a in adj]


def my_bh(pv, q):
    """BH: 오름차순 안정 정렬 · 뒤에서부터 누적 min(p·m/rank) · min 1 · reject = q값 ≤ q."""
    m = len(pv)
    order = sorted(range(m), key=lambda i: (pv[i], i))
    adj = [0.0] * m
    run = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        run = min(run, pv[i] * m / (rank + 1))
        adj[i] = min(1.0, run)
    return adj, [a <= q for a in adj]


def my_tost(low, high, delta, estimable, sesoi):
    if not estimable:
        return "Not-estimable"
    if low > 0.0 and abs(delta) >= sesoi:
        return "Positive"
    if low >= -sesoi and high <= sesoi:                   # 닫힌 구간 [−SESOI, +SESOI]
        return "Equivalent"
    return "Inconclusive"


def _est(ci):
    return ci.get("status") == "estimable" and ci.get("low") is not None


def _get(o, path):
    for k in path:
        o = o[k]
    return o


# ── check ───────────────────────────────────────────────────────────────────
def run_check(root, plan_path, staging):
    P = json.loads(open(plan_path, "rb").read())
    IC = P["independent_check"]
    C = IC["constants"]
    O = P["outputs"]
    tol_d, tol_perm, tol_bca = C["tol_delta"], C["tol_perm"], C["tol_bca"]
    checks, bad = {}, set()

    def rec(name, ok, item=""):
        checks[name] = bool(ok)
        if not ok:
            bad.add(item or name)

    lab = P["labels"]
    X = pd.read_parquet(os.path.join(root, lab["master_x"]["path"]))
    Y = pd.read_parquet(os.path.join(root, lab["master_y"]["path"]))
    ycols = [c for c in Y.columns if c != "cid"]
    y = Y[ycols].values.astype(int)
    cid = X["cid"].astype(np.int64).values
    sc = [scaffold_str(s) for s in X[lab["smiles_column"]].tolist()]
    uq = sorted(set(sc))
    mine = np.array([uq.index(s) for s in sc])
    theirs = np.load(os.path.join(staging, O["design_groups_file"]), allow_pickle=False)
    rec("1_scaffold_groups", len(uq) == P["design"]["n_groups"] and np.array_equal(mine, theirs), "design")
    groups = mine
    cols = np.arange(P["design"]["n_pt"])
    NZ = P["npz_schema"]
    cache = {}

    def mat(rel):
        if rel not in cache:
            with np.load(os.path.join(root, rel), allow_pickle=False) as z:
                M, cc = z[NZ["matrix_key"]].astype(np.float64), z[NZ["cid_key"]]
            if not np.array_equal(np.asarray(cc, dtype=np.int64), cid):
                rec("order_" + rel, False, rel)
            cache[rel] = M
        return cache[rel]

    idir = os.path.join(staging, O["items_subdir"])
    R = {i["id"]: json.loads(open(os.path.join(idir, i["id"] + ".json"), "rb").read()) for i in P["items"]}
    own = {}
    for it in P["items"]:
        iid, r = it["id"], R[it["id"]]
        if it["kind"] in ("contrast", "ci_only", "sub_metrics", "pt_tests"):
            cB, cT = mat(it["base"]["path"]), mat(it["treat"]["path"])
        if it["kind"] in ("contrast", "ci_only"):
            d = my_macro_ap(y, cT, cols) - my_macro_ap(y, cB, cols)
            own[iid] = d
            rec("2_delta:" + iid, abs(d - r["delta_obs"]) <= tol_d, iid)
        if it["kind"] == "contrast":
            sf = it["signflip"]
            perm = np.load(os.path.join(idir, iid + ".perm.npy"), allow_pickle=False)
            n = min(C["n_perm_regenerate"], sf["B"])
            mp = my_perm(cB, cT, y, groups, cols, sf["seed"], n)
            rec("3_perm_regen:" + iid, len(perm) == sf["B"] and float(np.max(np.abs(mp - perm[:n]))) <= tol_perm, iid)
            rec("3_p_exact:" + iid, my_p(perm, own[iid], C["eps"]) == r["p_raw"], iid)
        if it["kind"] in ("contrast", "ci_only"):
            bs = it["bootstrap"]
            boot = np.load(os.path.join(idir, iid + ".boot.npy"), allow_pickle=False)
            jack = my_jackknife(cB, cT, y, groups, cols, bs["unit"])
            lo, hi, st = my_bca(boot, own[iid], jack, bs["alpha"])
            cb = r["bootstrap"]["ci_bca"]
            ok = st == cb["status"]
            if ok and st == "bca":
                ok = abs(lo - cb["low"]) <= tol_bca and abs(hi - cb["high"]) <= tol_bca
            rec("4_bca:" + iid, ok and len(boot) == bs["B"], iid)
        if it["kind"] == "contrast":
            ci = r["bootstrap"]["ci_primary"]
            lab_ = my_tost(ci.get("low"), ci.get("high"), own[iid], _est(ci), C["sesoi"]) if _est(ci) else "Not-estimable"
            rec("7_tost:" + iid, lab_ == r["tost"]["label"], iid)
        if it["kind"] == "sealed_p_null":
            J = json.loads(open(os.path.join(root, it["source"]), "rb").read())
            pg, pf = float(_get(J, it["keys"]["p_global"])), float(_get(J, it["keys"]["p_family"]))
            rec("5_null_max:" + iid, max(pg, pf) == r["p_slot"] and pg == r["p_emp_global"] and pf == r["p_emp_family"],
                iid)
        if it["kind"] == "sealed_p_holm8":
            J = json.loads(open(os.path.join(root, it["source"]), "rb").read())
            k = it["keys"]
            c, B = _get(J, k["c_abs_ge_obs_first_B"]), _get(J, k["B"])
            rec("5_holm8_p:" + iid, (1.0 + c) / (B + 1.0) == _get(J, k["p_primary"]) == r["p_slot"], iid)
        if it["kind"] == "pt_tests":
            ok = True
            labs = sorted(r["per_pt"])
            for L_ in labs:
                v = r["per_pt"][L_]
                j = v["col"]
                d = my_macro_ap(y, cT, [j]) - my_macro_ap(y, cB, [j])
                ok &= abs(d - v["delta_obs"]) <= tol_d and ycols[j] == L_
            pos = y.sum(0)
            elig = [j for j in range(y.shape[1]) if pos[j] >= C["pt_min_positive"]
                    and len(np.unique(groups[y[:, j] > 0])) >= C["pt_min_positive_clusters"]]
            ok &= sorted(ycols[j] for j in elig) == labs
            adj, rej = my_bh([r["per_pt"][L_]["p_two_sided"] for L_ in labs], it["bh"]["q"])
            ok &= all(adj[i] == r["bh"]["adjusted_p"][L_] and rej[i] == r["bh"]["reject"][L_] for i, L_ in enumerate(labs))
            rec("7_pt_bh:" + iid, ok, iid)
    D = json.loads(open(os.path.join(staging, O["decisions_file"]), "rb").read())
    HP = P["holm"]
    alpha = HP["alpha"]
    adjs = {}
    for pname, ps in HP["panels"].items():
        labels = list(ps["slots"])
        pv = [ps["slots"][L_]["fixed_value"] if "fixed_value" in ps["slots"][L_] else
              float(_get(R[ps["slots"][L_]["item"]], ps["slots"][L_]["field"])) for L_ in labels]
        adj, rej = my_holm(pv, alpha)
        h = D["holm"][pname]
        rec("6_holm:" + pname, len(labels) == C["holm_m"] and all(
            h["raw_p"][L_] == pv[i] and h["adjusted_p"][L_] == adj[i] and h["reject"][L_] == rej[i]
            for i, L_ in enumerate(labels)), pname)
        adjs[pname] = dict(zip(labels, adj))
    a1 = adjs[HP["adjudication_panel"]]
    DE = P["decisions"]
    c1 = R[DE["RQ2"]["item"]]
    ci = c1["bootstrap"]["ci_primary"]
    rq2 = _est(ci) and ci["low"] > 0 and c1["p_raw"] < alpha and abs(own[DE["RQ2"]["item"]]) >= C["sesoi"]
    rec("7_RQ2", rq2 == D["RQ2"]["success"], "RQ2")
    ok3 = True
    for iid, L_ in zip(DE["RQ3"]["items"], DE["RQ3"]["holm_labels"]):
        ci = R[iid]["bootstrap"]["ci_primary"]
        ok3 = ok3 and _est(ci) and ci["low"] > 0 and a1[L_] < alpha
    rec("7_RQ3", ok3 == D["RQ3"]["success"], "RQ3")
    rq4 = a1[DE["RQ4"]["holm_label"]] < alpha
    rec("7_RQ4", rq4 == D["RQ4"]["success"], "RQ4")
    rqi = a1[DE["RQ_int"]["holm_label"]] < alpha
    rec("7_RQ_int", rqi == D["RQ_int"]["success"], "RQ_int")
    k = R[DE["C_CAP"]["item"]]
    ci = k["bootstrap"]["ci_primary"]
    cc = _est(ci) and ci["low"] > 0 and k["p_raw"] < alpha
    rec("7_C_CAP", cc == D["C_CAP"]["pass"], "C_CAP")
    rec("7_minimum_establishment", (rq2 and (ok3 or cc) and rq4) == D["minimum_establishment"]["success"],
        "minimum_establishment")
    out = {"all_match": not bad and all(checks.values()), "n_checks": len(checks),
           "n_match": sum(checks.values()), "checks": checks, "mismatch_items": sorted(bad)}
    with open(os.path.join(staging, IC["output_file"]), "wb") as f:
        f.write((json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    return 0


# ── selftest ────────────────────────────────────────────────────────────────
BANNED = ("sap", "unblinding_run", "rqint_", "confirmatory_", "ladder_", "compute_lock", "null_", "stability_",
          "stratification", "pid_", "axes_")
ALLOWED_TOP = {"__future__", "sys", "argparse", "ast", "hashlib", "json", "os", "numpy", "pandas", "rdkit",
               "scipy", "sklearn"}


def selftest(out):
    res = {"stage": "selftest", "script_sha256": hashlib.sha256(open(__file__, "rb").read()).hexdigest()}
    c = {}
    tree = ast.parse(open(__file__, encoding="utf-8").read())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
    c["K1_import_ban"] = not any(m.startswith(BANNED) for m in mods) and all(m.split(".")[0] in ALLOWED_TOP
                                                                           for m in mods)
    adj, rej = my_holm([0.01, 0.04, 0.03, 0.005, 0.5, 0.2, 0.01], 0.05)
    hand = [0.06, 0.12, 0.12, 0.035, 0.5, 0.4, 0.06]
    c["K2_holm_hand"] = all(abs(a - h) < 1e-15 for a, h in zip(adj, hand)) and rej == [False, False, False, True,
                                                                                         False, False, False]
    adj, rej = my_holm([0.01] * 7, 0.05)
    c["K3_holm_ties_boundary"] = all(abs(a - 0.07) < 1e-15 for a in adj) and rej == [False] * 7 and my_holm([0.05 / 7 - 1e-9] + [0.9] * 6,
                                                                                      0.05)[1][0] is True
    adj, rej = my_bh([0.01, 0.04, 0.03, 0.005], 0.05)
    c["K4_bh_hand"] = all(abs(a - h) < 1e-15 for a, h in zip(adj, [0.02, 0.04, 0.04, 0.02])) and all(rej)
    c["K5_tost"] = (my_tost(-0.01, 0.01, 0.0, True, 0.01) == "Equivalent" and my_tost(0.001, 0.05, 0.02, True, 0.01)
                    == "Positive" and my_tost(-0.02, 0.03, 0.0, True, 0.01) == "Inconclusive"
                    and my_tost(0.001, 0.05, 0.005, True, 0.01) == "Inconclusive"
                    and my_tost(0, 0, 0, False, 0.01) == "Not-estimable")
    y = np.array([[1, 0], [0, 1], [1, 1], [0, 0]])
    P = np.array([[0.9, 0.1], [0.2, 0.8], [0.7, 0.6], [0.1, 0.3]])
    c["K6_macro_ap_hand"] = my_macro_ap(y, P, [0, 1]) == 1.0 and np.isnan(my_macro_ap(np.zeros((4, 1), int),
                                                                                      P[:, :1], [0]))
    rng = np.random.default_rng(0)
    yy = (rng.random((40, 3)) < 0.3).astype(int)
    A, B_ = rng.random((40, 3)), rng.random((40, 3))
    g = np.repeat(np.arange(8), 5)
    p1, p2 = my_perm(A, B_, yy, g, [0, 1, 2], 7, 20), my_perm(A, B_, yy, g, [0, 1, 2], 7, 20)
    c["K7_perm_deterministic_antisym"] = bool(np.array_equal(p1, p2)) and float(
        np.max(np.abs(my_perm(A, A, yy, g, [0, 1, 2], 7, 5)))) == 0.0
    c["K8_p_formula"] = my_p(np.array([0.1, -0.3, 0.05]), 0.1, 1e-12) == 3.0 / 4.0
    jack = my_jackknife(A, B_, yy, g, [0, 1, 2], "scaffold_cluster")
    c["K9_jackknife_units"] = jack.shape == (8,) and my_jackknife(A, B_, yy, g, [0, 1, 2], "drug").shape == (40,)
    lo, hi, st = my_bca(np.linspace(-1, 1, 1000), 0.0, np.array([0.1, -0.1, 0.2, -0.2]), 0.05)
    c["K10_bca_symmetric"] = st == "bca" and abs(lo + hi) < 1e-9 and my_bca(np.ones(10), 5.0, jack, 0.05)[2] == \
        "bca_failed_z0_degenerate"
    c["K11_scaffold"] = scaffold_str("CCc1ccccc1") == "c1ccccc1" and scaffold_str("CCCC") == "" and \
        scaffold_str("not_a_smiles") == ""
    c = {k: bool(v) for k, v in c.items()}
    res["checks"] = c
    res["n_pass"] = sum(c.values())
    res["n_checks"] = len(c)
    res["all_pass"] = all(c.values())
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write((json.dumps(res, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"stage": "selftest", "all_pass": res["all_pass"], "n_pass": res["n_pass"],
                      "n_checks": res["n_checks"]}), flush=True)
    return 0 if res["all_pass"] else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["check", "holm_probe", "selftest"], required=True)
    ap.add_argument("--root")
    ap.add_argument("--plan")
    ap.add_argument("--staging")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.stage == "check":
        return run_check(a.root, a.plan, a.staging)
    if a.stage == "holm_probe":
        d = json.loads(sys.stdin.read())
        out = {}
        for nm, pv in d["cases"].items():
            adj, rej = my_holm([float(x) for x in pv], 0.05)
            out[nm] = {"adjusted_p": adj, "reject": rej}
        print(json.dumps(out))
        return 0
    return selftest(a.out)


if __name__ == "__main__":
    raise SystemExit(main())
