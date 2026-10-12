"""rq8_external_validation.py — 블록 BI (docs/123) RQ8 외부(라벨 출처 이식성) 검증. 정본 = docs/118b.

  --stage e1 : 외부 라벨 행렬(EU∪UK · EU · UK) 구성. **예측 판독 0** — `_sealed` 경로 open 은 audit hook 이 차단·계수.
               118b §2 규칙 1~11 = pipeline/src/step2_labels.py · step5_assemble_master.py 와 같은 식(출처 필터만 교체).
  --stage e2 : docs/33 항목 89(E1 기록) 존재 확인 후에만 실행. 두 봉인 트리 access.log 1줄씩 append →
               예측 8파일 sha 대조 → 6행(R8-main · eu · uk · pt1 · gin · int) 채점 → R8-main 판정(118b §4).
               p 미계산(sign-flip 미수행) · CI = sap.bootstrap.paired_scaffold_bootstrap 의 ci_primary 그대로.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import io
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PLAN = "docs/118b_external_validation_plan.md"
PLAN_SHA = "4f06d39e9aa827bd63a2ac28e6dbedbedec2430bbde10aaadd567c81c726f60e"
RAW = "data/raw/onsides-v3.1.1/csv"
OUT = "experiments/runs/v3_rq8_external"

INPUT_SHA = {  # 118b §1-1 · §1-2 표 그대로
    f"{RAW}/product_label.csv": "77586d3895dd826744912f604c8eca9eef44181d66171c5650b9dc28ba93e329",
    f"{RAW}/product_adverse_effect.csv": "167354272565e7df8eccdfa9592aa4d863999382a01ea438902154663713039b",
    f"{RAW}/product_to_rxnorm.csv": "0fdd5237a136f1086dcde3ddac56e77847b3e80e7bfafdb540c2e1bd0cc40fc7",
    f"{RAW}/vocab_rxnorm_ingredient_to_product.csv": "3b07b2f34ba665be6f14cbce3f7c54c25daa8946868470ca868e1d55f9447632",
    f"{RAW}/vocab_meddra_adverse_effect.csv": "fddc123742cfd3beb215ea0dbfe0bb4edb977792b6c87c949eb66587c90b2661",
    f"{RAW}/vocab_rxnorm_ingredient.csv": "84e37e2b6b96cd96de556b9bcf4359a7eb322ba8ef3a627fe9666890524e5f7a",
    "data/processed/ingredient_to_cid.parquet": "693dc17c6ae11fc81e568451b7c3ab57a6722e2540b84c8fc27b205e42d8a3fb",
    "data/processed/cid_to_smiles.parquet": "bc410f2e7f50c5ec5ba2790bc0bcec36f0acfdbe336cf09c2ff9a9643e781c6e",
    "data/processed/master_X.parquet": "788c8a64d19e8c3cc030476e7b2eb7f207246e3af6e73304d97f2fc9aa2ae6e6",
    "data/processed/master_Y.parquet": "bd23584342de6482e50f218bd409740acc2a00eeac86ee95bd89952bc3d18018",
    "pipeline/src/step2_labels.py": "533cda042b5827523877af58968c24609972d91c658f40cbb4085a96c110787e",
    "pipeline/src/step5_assemble_master.py": "b245f31b2c7499f79ef9ef37e99a59dc583662915edfce343afa52cfabc4fff4",
}
SOURCES = {"euuk": ("EU", "UK"), "eu": ("EU",), "uk": ("UK",)}
COVERAGE_EXPECTED = {"eu": 327, "uk": 478, "euuk": 681}  # 118b §2-4
MIN_POS = 10

RF = {"M1b": "experiments/runs/v3_consensus_rep123/_sealed/consensus_M1b.npz",
      "M2b": "experiments/runs/v3_consensus_rep123/_sealed/consensus_M2b.npz"}
GIN_SEEDS = [42, 1, 2]
GIN = {(m, t): f"experiments/runs/v3_gin_confirm_consensus_rep123/_sealed/consensus_{m}_seed{t}.npz"
       for m in ("M1b", "M2b") for t in GIN_SEEDS}
ACCESS_LOGS = ["experiments/runs/v3_consensus_rep123/_sealed/access.log",
               "experiments/runs/v3_gin_confirm_consensus_rep123/_sealed/access.log"]
AUDIT = "experiments/provenance/pre_unblinding_audit_v3.json"
RESULTS_FULL = "experiments/runs/v3_unblinding/results/results_full.json"
RESULTS_FULL_SHA = "372cce5d1be9f3772996284fc651fe0ff23310a61d79cb0a1bf6716c5b5a1414"
BOOT = dict(B=10000, seed=6001, unit="scaffold_cluster", alpha=0.05)


def now_kst():
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " KST"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


# ───────────────────────── E1 ─────────────────────────
SEALED_OPEN_ATTEMPTS = []


def _guard(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.fsdecode(args[0])
        if "_sealed" in p.split(os.sep) or "/_sealed/" in p:
            SEALED_OPEN_ATTEMPTS.append(p)
            raise PermissionError(f"E1 guard: _sealed open 금지 ({p})")


def build_external(src, pl, pae, p2r, i2p, vm, i2c, c2s, xcid, ycols):
    """118b §2 규칙 1~10 (step2 · step5 와 같은 식, 출처 필터만 S)."""
    n = {}
    labels = set(pl[pl["source"].isin(src)]["label_id"])                         # 규칙 1
    n["n_label_docs"] = len(labels)
    m = pae[pae["product_label_id"].isin(labels)]
    n["rows_source"] = len(m)
    n["rows_non_pmb_dropped"] = int((m["match_method"] != "PMB").sum())             # 규칙 2
    m = m[m["match_method"] == "PMB"]
    n["rows_pmb"] = len(m)
    pt_ids = set(vm[vm["meddra_term_type"] == "PT"]["meddra_id"])                   # 규칙 3
    m = m[m["effect_meddra_id"].isin(pt_ids)]
    n["rows_pt"] = len(m)
    ning = i2p.groupby("product_id")["ingredient_id"].nunique()                     # 규칙 4
    single = set(ning[ning == 1].index)
    bridge = (p2r[p2r["rxnorm_product_id"].isin(single)]
              .merge(i2p[i2p["product_id"].isin(single)], left_on="rxnorm_product_id", right_on="product_id")
              [["label_id", "ingredient_id"]].drop_duplicates())
    df = m.merge(bridge, left_on="product_label_id", right_on="label_id")
    n["rows_single_ingredient"] = len(df)
    lab = df[["ingredient_id", "effect_meddra_id"]].drop_duplicates().rename(      # 규칙 5
        columns={"effect_meddra_id": "meddra_pt"})
    n["ingredient_pt_pairs"] = len(lab)
    n["ingredients"] = int(lab["ingredient_id"].nunique())
    c2v = c2s[c2s.valid_flag]                                                        # 규칙 6
    j = lab.merge(i2c[i2c.mapping_status == "ok"][["ingredient_id", "cid"]], on="ingredient_id")
    j = j.merge(c2v[["cid", "smiles_canonical"]], on="cid")
    rep = (c2v.dropna(subset=["smiles_canonical"]).sort_values("cid")
           .groupby("smiles_canonical")["cid"].first().rename("rep_cid"))
    j = j.merge(rep, on="smiles_canonical")
    n["drugs_rep_cid"] = int(j["rep_cid"].nunique())
    j = j[j["rep_cid"].isin(set(xcid))]                                              # 규칙 7
    drugs = np.array(sorted(set(j["rep_cid"])), dtype=np.int64)
    assert np.all(np.isin(drugs, xcid)) and list(drugs) == [c for c in xcid if c in set(drugs)]
    n["drugs_rule7"] = int(len(drugs))
    col = {p: k for k, p in enumerate(ycols)}                                        # 규칙 8
    j8 = j[j["meddra_pt"].isin(col)]
    row = {c: i for i, c in enumerate(drugs)}
    y = np.zeros((len(drugs), len(ycols)), dtype=np.int8)
    y[j8["rep_cid"].map(row).values, j8["meddra_pt"].map(col).values] = 1          # OR 결합
    n["positive_pairs_370"] = int(y.sum())
    ev = y.sum(1) > 0                                                                # 규칙 9
    n["eval_drugs"] = int(ev.sum())
    n["drugs_zero_pos_in_370_excluded"] = int((~ev).sum())
    ye = y[ev]
    pos, neg = ye.sum(0), (1 - ye).sum(0)
    el10 = np.where((pos >= MIN_POS) & (neg >= 1))[0]                                # 규칙 10
    el1 = np.where((pos >= 1) & (neg >= 1))[0]
    n["eligible_pt_ge10"] = int(len(el10))
    n["eligible_pt_ge1"] = int(len(el1))
    return y, drugs, ev, el10, el1, n


def coverage_rules_1467(src, pl, p2r, i2p, i2c, c2s, xcid):
    """118b §2-4 cowork 실측 정의(규칙 1·4·6·7 · 부작용 행 무관) — 진단용."""
    labels = set(pl[pl["source"].isin(src)]["label_id"])
    ning = i2p.groupby("product_id")["ingredient_id"].nunique()
    single = set(ning[ning == 1].index)
    br = (p2r[p2r["label_id"].isin(labels) & p2r["rxnorm_product_id"].isin(single)]
          .merge(i2p, left_on="rxnorm_product_id", right_on="product_id"))
    c2v = c2s[c2s.valid_flag]
    j = br[["ingredient_id"]].drop_duplicates().merge(
        i2c[i2c.mapping_status == "ok"][["ingredient_id", "cid"]], on="ingredient_id")
    j = j.merge(c2v[["cid", "smiles_canonical"]], on="cid")
    rep = (c2v.dropna(subset=["smiles_canonical"]).sort_values("cid")
           .groupby("smiles_canonical")["cid"].first().rename("rep_cid"))
    j = j.merge(rep, on="smiles_canonical")
    return int(len(set(j["rep_cid"]) & set(xcid)))


def stage_e1(root):
    os.chdir(root)
    if os.path.exists(OUT):
        sys.exit(f"STOP: {OUT} 이미 존재(덮어쓰기 금지)")
    sys.addaudithook(_guard)
    t0 = now_kst()
    got = {p: sha_file(p) for p in INPUT_SHA}
    bad = {p: (INPUT_SHA[p], got[p]) for p in INPUT_SHA if got[p] != INPUT_SHA[p]}
    if bad or sha_file(PLAN) != PLAN_SHA:
        sys.exit(f"STOP: 입력 sha 불일치 {bad}")
    pl = pd.read_csv(f"{RAW}/product_label.csv", dtype=str)[["label_id", "source"]]
    p2r = pd.read_csv(f"{RAW}/product_to_rxnorm.csv", dtype=str)
    i2p = pd.read_csv(f"{RAW}/vocab_rxnorm_ingredient_to_product.csv", dtype=str)
    vm = pd.read_csv(f"{RAW}/vocab_meddra_adverse_effect.csv", dtype=str)
    pae = pd.read_csv(f"{RAW}/product_adverse_effect.csv",
                      usecols=["product_label_id", "effect_meddra_id", "match_method"], dtype=str)
    i2c = pd.read_parquet("data/processed/ingredient_to_cid.parquet")
    c2s = pd.read_parquet("data/processed/cid_to_smiles.parquet")
    X = pd.read_parquet("data/processed/master_X.parquet")
    Y = pd.read_parquet("data/processed/master_Y.parquet")
    assert list(X["cid"]) == list(Y["cid"]) == sorted(X["cid"])
    xcid = X["cid"].astype(np.int64).values
    ycols = [c for c in Y.columns if c != "cid"]
    assert len(xcid) == 1092 and len(ycols) == 370

    built = {}
    for key, src in SOURCES.items():
        y, drugs, ev, el10, el1, n = build_external(src, pl, pae, p2r, i2p, vm, i2c, c2s, xcid, ycols)
        n["coverage_rules_1467_diag"] = coverage_rules_1467(src, pl, p2r, i2p, i2c, c2s, xcid)
        print(key, json.dumps(n, ensure_ascii=False))
        # 커버리지 assert = 118b §2-4 정의(「규칙 1·4·6·7 까지 적용한 master_X 약물 수」) — 118b 우선(docs/123 §0).
        # 규칙 1~7 전부(2 PMB · 3 PT 포함) 적용 수 drugs_rule7 은 실행 블록에서 처음 산출되는 값으로 함께 보고.
        if n["coverage_rules_1467_diag"] != COVERAGE_EXPECTED[key]:
            sys.exit(f"STOP: 커버리지 불일치 {key}: 기대 {COVERAGE_EXPECTED[key]} "
                     f"실측(규칙1·4·6·7) {n['coverage_rules_1467_diag']} · 규칙1~7 {n['drugs_rule7']}")
        built[key] = (src, y, drugs, ev, el10, el1, n)

    os.makedirs(OUT)
    man = {"block": "BI (docs/123) E1", "plan": PLAN, "plan_sha256": PLAN_SHA, "started_kst": t0,
           "input_sha256": got, "pt_axis": "master_Y 열 순서 370", "drug_axis": "master_X cid 오름차순 부분열(규칙 7)",
           "npz_keys": {"y": "int8 (규칙 7 약물 × 370 PT) — 평가 약물 = y 행합 > 0", "cid": "int64",
                        "pt": "unicode str (master_Y 열 순서)"},
           "sources": {}}
    for key, (src, y, drugs, ev, el10, el1, n) in built.items():
        path = f"{OUT}/labels_{key}.npz"
        np.savez(path, y=y, cid=drugs, pt=np.array(ycols, dtype=str))
        man["sources"][key] = {
            "source_filter": list(src), "counts": n, "npz": path, "npz_sha256": sha_file(path),
            "array_sha256": {"y": sha_bytes(y.tobytes()), "cid": sha_bytes(drugs.tobytes()),
                             "pt": sha_bytes(np.array(ycols, dtype=str).tobytes())},
            "eval_drug_cids": [int(c) for c in drugs[ev]],
            "eligible_pt_ge10": [ycols[k] for k in el10], "eligible_pt_ge1": [ycols[k] for k in el1]}
    man["sealed_open_attempts"] = len(SEALED_OPEN_ATTEMPTS)
    man["sealed_guard"] = "sys.addaudithook('open') — `_sealed` 경로 open 시 PermissionError + 계수"
    man["finished_kst"] = now_kst()
    with open(f"{OUT}/e1_manifest.json", "w") as f:
        f.write(json.dumps(man, indent=2, ensure_ascii=False) + "\n")
    print("e1_manifest sha", sha_file(f"{OUT}/e1_manifest.json"), "sealed_open_attempts", len(SEALED_OPEN_ATTEMPTS))


# ───────────────────────── E2 ─────────────────────────
def _boot_job(args):
    from sap.bootstrap import paired_scaffold_bootstrap
    rid, M1, M2, y, g, el = args
    r = paired_scaffold_bootstrap(M1, M2, y, g, eligible_pt=el, **BOOT)
    return rid, r


def _load_pred(blob, xcid):
    with np.load(io.BytesIO(blob), allow_pickle=False) as z:
        assert set(z.files) == {"consensus", "cid"}
        C, cid = z["consensus"], z["cid"]
    assert C.shape == (1092, 370) and np.array_equal(np.asarray(cid, dtype=np.int64), xcid), "행 순서 불일치"
    assert np.isfinite(C).all()
    return C.astype(np.float64)


def stage_e2(root):
    os.chdir(root)
    from sap.metrics import macro_ap
    from confirmatory_oof_rep1 import scaffold_of

    man = json.load(open(f"{OUT}/e1_manifest.json"))
    if "89. **RQ8 외부 라벨 행렬 구성" not in open("docs/33_prereg_deviation_log.md", encoding="utf-8").read():
        sys.exit("STOP: docs/33 항목 89(E1 기록) 부재 — E2 착수 불가")
    for key, s in man["sources"].items():
        assert sha_file(s["npz"]) == s["npz_sha256"], key
    for p in (OUT + "/results_rq8.json", OUT + "/results_rq8_table.md"):
        if os.path.exists(p):
            sys.exit(f"STOP: {p} 존재")
    assert sha_file(RESULTS_FULL) == RESULTS_FULL_SHA
    d1 = json.load(open(RESULTS_FULL))["items"]["C1"]["delta_obs"]
    assert d1 == -0.006324167855457974

    # 4-1 판독 기록 (예측 open 전)
    t_access = now_kst()
    line = {"ts_kst": t_access, "type": "machine_read", "purpose": "rq8_external_validation",
            "human_exposure": True, "step": "블록 BI(docs/123) E2", "plan_ref": PLAN, "plan_sha256": PLAN_SHA,
            "actor": "vscode-claude", "note": "개봉 후 tier-3 외부 검증. 예측 파일 무수정 판독."}
    for p in ACCESS_LOGS:
        b = open(p, "rb").read()
        assert b.endswith(b"\n")
        with open(p, "ab") as f:
            f.write((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8"))
        assert open(p, "rb").read()[:len(b)] == b

    exp = json.load(open(AUDIT))["sealed_sha256"]
    blobs = {}
    for p in list(RF.values()) + list(GIN.values()):
        b = open(p, "rb").read()
        assert sha_bytes(b) == exp[p], f"sha 불일치 {p}"
        blobs[p] = b

    X = pd.read_parquet("data/processed/master_X.parquet")
    Y = pd.read_parquet("data/processed/master_Y.parquet")
    xcid = X["cid"].astype(np.int64).values
    ycols = [c for c in Y.columns if c != "cid"]
    yint = Y[ycols].values.astype(int)
    scaf = [scaffold_of(s) for s in X["smiles_canonical"].tolist()]
    gidx = {g: i for i, g in enumerate(sorted(set(scaf)))}
    gi = np.array([gidx[s] for s in scaf], dtype=int)

    P = {m: _load_pred(blobs[p], xcid) for m, p in RF.items()}
    PG = {k: _load_pred(blobs[p], xcid) for k, p in GIN.items()}

    ext = {}
    for key in SOURCES:
        with np.load(man["sources"][key]["npz"], allow_pickle=False) as z:
            y, cid, pt = z["y"].astype(int), z["cid"], z["pt"]
        assert list(pt) == ycols
        ev = y.sum(1) > 0
        rows = np.searchsorted(xcid, cid[ev])
        assert np.array_equal(xcid[rows], cid[ev])
        ext[key] = {"y": y[ev], "rows": rows}

    def elig(ye, k):
        pos, neg = ye.sum(0), (1 - ye).sum(0)
        return np.where((pos >= k) & (neg >= 1))[0]

    main = ext["euuk"]
    specs = {  # id: (정답 y, 행, 적격 PT, 모델)
        "R8-main": (main["y"], main["rows"], elig(main["y"], 10), "RF"),
        "R8-eu": (ext["eu"]["y"], ext["eu"]["rows"], elig(ext["eu"]["y"], 10), "RF"),
        "R8-uk": (ext["uk"]["y"], ext["uk"]["rows"], elig(ext["uk"]["y"], 10), "RF"),
        "R8-pt1": (main["y"], main["rows"], elig(main["y"], 1), "RF"),
        "R8-gin": (main["y"], main["rows"], elig(main["y"], 10), "GIN"),
        "R8-int": (yint[main["rows"]], main["rows"], elig(yint[main["rows"]], 10), "RF"),
    }
    assert [ycols[j] for j in specs["R8-main"][2]] == man["sources"]["euuk"]["eligible_pt_ge10"]
    assert [ycols[j] for j in specs["R8-pt1"][2]] == man["sources"]["euuk"]["eligible_pt_ge1"]

    rows_out, jobs = {}, []
    for rid, (ye, rows, el, model) in specs.items():
        r = {"answer": {"R8-int": "US(master_Y)", "R8-eu": "EU", "R8-uk": "UK"}.get(rid, "EU∪UK"),
             "model": model, "n_eval_drugs": int(len(rows)), "n_eligible_pt": int(len(el)),
             "eligible_rule": "pos≥1 & neg≥1" if rid == "R8-pt1" else "pos≥10 & neg≥1"}
        if len(el) == 0:
            r["status"] = "no_eligible_pt"
            rows_out[rid] = r
            continue
        if model == "RF":
            a1 = macro_ap(ye, P["M1b"][rows], el)
            a2 = macro_ap(ye, P["M2b"][rows], el)
            r.update(ap_M1b=a1["macro_ap"], ap_M2b=a2["macro_ap"], delta=a2["macro_ap"] - a1["macro_ap"],
                     undefined_ap={"M1b": a1["n_excluded_undefined"], "M2b": a2["n_excluded_undefined"],
                                   "n_eval_pt": a1["n_eval"]})
            jobs.append((rid, P["M1b"][rows], P["M2b"][rows], ye, gi[rows], el))
        else:
            per = {}
            for t in GIN_SEEDS:
                a1 = macro_ap(ye, PG[("M1b", t)][rows], el)
                a2 = macro_ap(ye, PG[("M2b", t)][rows], el)
                per[f"seed{t}"] = {"ap_M1b": a1["macro_ap"], "ap_M2b": a2["macro_ap"],
                                   "delta": a2["macro_ap"] - a1["macro_ap"],
                                   "undefined_ap": {"M1b": a1["n_excluded_undefined"],
                                                    "M2b": a2["n_excluded_undefined"]}}
            r.update(per_seed=per, delta=float(np.mean([per[f"seed{t}"]["delta"] for t in GIN_SEEDS])),
                     aggregation="S-GIN cell_3: Δ_t = macroAP(M2b_seed t) − macroAP(M1b_seed t), Δ_GIN = mean_t (metric-then-average)",
                     ci={"status": "not_computed", "reason": "S-GIN 은 CI 없이 방향만 보고 — 새 절차 신설 금지(docs/123 §4-3)"})
        rows_out[rid] = r

    t_boot0 = now_kst()
    with ProcessPoolExecutor(max_workers=len(jobs)) as ex:
        for rid, b in ex.map(_boot_job, jobs):
            assert abs(b["delta_obs"] - rows_out[rid]["delta"]) <= 1e-15
            rows_out[rid]["ci"] = {"low": b["ci_primary"]["low"], "high": b["ci_primary"]["high"],
                                   "status": b["ci_primary"]["status"], "bca_status": b["ci_primary"]["bca_status"],
                                   "method": "BCa (ci_primary)"}
            rows_out[rid]["bootstrap"] = {k: b[k] for k in ("B", "seed", "unit", "alpha", "n_clusters",
                                                             "n_eff_clusters", "cluster_size", "ci_percentile",
                                                             "undefined_ap_exclusion", "pt_diagnostics",
                                                             "bca_diagnostics", "boot_summary")}
    t_boot1 = now_kst()

    # 판정 (R8-main 만 · 118b §4)
    m = rows_out["R8-main"]
    if m["n_eligible_pt"] < 20 or m["n_eval_drugs"] < 100:
        verdict, reason = "not_estimable", f"적격 PT {m['n_eligible_pt']} · 평가 약물 {m['n_eval_drugs']}"
    elif np.sign(m["delta"]) == np.sign(d1) and m["delta"] != 0 and d1 != 0:
        verdict, reason = "방향 재현", "sign(Δ_ext) == sign(Δ_①) = negative"
    else:
        verdict, reason = "방향 비재현", "sign(Δ_ext) != sign(Δ_①) 또는 Δ = 0"

    ye_ext, yi = main["y"], yint[main["rows"]]
    both = int(((ye_ext == 1) & (yi == 1)).sum())
    eo, io_ = int(((ye_ext == 1) & (yi == 0)).sum()), int(((ye_ext == 0) & (yi == 1)).sum())
    conc = {"scope": "R8-main 평가 약물 × 370 PT", "both": both, "external_only": eo, "internal_only": io_,
            "jaccard": both / (both + eo + io_)}

    res = {"block": "BI (docs/123) E2", "plan": PLAN, "plan_sha256": PLAN_SHA, "tier": "tier-3 · 비판정 · 다중성 보정 없음",
           "access_log_ts_kst": t_access, "bootstrap_started_kst": t_boot0, "bootstrap_finished_kst": t_boot1,
           "reference_delta_C1": d1, "reference_sign": "negative", "p_computed": False,
           "bootstrap_spec": BOOT, "rows": rows_out,
           "verdict_R8_main": {"category": verdict, "reason": reason,
                               "rule": "118b §4 — sign 일치 & ≠0 → 방향 재현 / 그 밖 → 방향 비재현 / 적격 PT<20 또는 평가 약물<100 → not_estimable · CI 0 포함 여부 미사용"},
           "delta_sign_R8_main": "negative" if m["delta"] < 0 else ("positive" if m["delta"] > 0 else "zero"),
           "label_concordance": conc, "e1_manifest_sha256": sha_file(f"{OUT}/e1_manifest.json"),
           "prediction_sha256": {p: sha_bytes(b) for p, b in blobs.items()}}
    with open(f"{OUT}/results_rq8.json", "w") as f:
        f.write(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: (v.get("delta"), v.get("ci", {}).get("status")) for k, v in rows_out.items()}))
    print("verdict", verdict)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["e1", "e2"], required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    {"e1": stage_e1, "e2": stage_e2}[a.stage](os.path.abspath(a.root))
