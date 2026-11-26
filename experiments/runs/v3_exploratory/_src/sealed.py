#!/usr/bin/env python3
"""sealed.py — 블록 CN(docs/153) 중 **봉인 consensus OOF 를 필요로 하는** 항목.

수행 = S0-2 하네스 자기검사 · X1 CI · X4(실현값 평균·중앙값) · X5-②③ · X7-Δ · X9a-Δ · X12.

규약(지시서 §0·§2·§3)
  - D-6: `unblinding_run.py` 의 `_load_inputs`·`_matrix`·`_eligible` 를 **import 재사용**.
    재구현 0. ctx 는 읽기전용 shim(쓰기 경로 없음).
  - D-5: 봉인 파일을 **열기 직전** 해당 `_sealed/access.log` 에 1줄 append
    (`sap/redaction.py:SealedStore.open_sealed` 형식). `allow_pickle=False` · 읽기 전용.
  - 학습·재학습 0 (`fit`·`rf_fit_predict`·GIN 학습 호출 0) · p-value 0 · 네트워크 0.
  - bootstrap = `sap/bootstrap.py` primary 단위 · B=10,000 · seed 6001 · consensus OOF.

운용: 계약(contract)당 1파일 체크포인트 → 중단 후 재개 시 완료분 재계산 0.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

# numpy import 전에 스레드 1 고정 (fork 안전 · 선례 unblinding_run.py:30-33)
for _tv in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_tv] = "1"

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
SRC = os.path.join(ROOT, "v3_Multimodal", "src")
OUT = os.path.join(ROOT, "experiments", "runs", "v3_exploratory")
CKPT = os.path.join(OUT, "_ckpt")
KST = datetime.timezone(datetime.timedelta(hours=9))
ACCESSOR = "block_CN_docs153_exploratory"

B_BOOT, SEED_BOOT = 10000, 6001

NPZ = {
    "M1b": "experiments/runs/v3_consensus_rep123/_sealed/consensus_M1b.npz",
    "M2b": "experiments/runs/v3_consensus_rep123/_sealed/consensus_M2b.npz",
    "M0": "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_M0.npz",
    "M1": "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_M1.npz",
    "P-ID": "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_P-ID.npz",
    "P-FAM": "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_P-FAM.npz",
    "C-CAP": "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/consensus_C-CAP.npz",
}
NULL_CKPT = "experiments/runs/v3_null_MAIN/_sealed/checkpoint.jsonl"

MTIME_GUARD_GLOBS = ["paper", "v3_Multimodal/src/sap",
                     "v3_Multimodal/src/unblinding_run.py"]


def now_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def log(*a):
    print(*a, flush=True)


# ═════════════════════════════════════════════════════════════════════════
# 전원 게이트 — 장시간 계산이므로 AC 필수(배터리 강제절전 사고 방지)
# ═════════════════════════════════════════════════════════════════════════
def power_ok():
    try:
        ps = subprocess.run(["pmset", "-g", "ps"], capture_output=True,
                            text=True, check=True).stdout
    except Exception as e:
        return False, "pmset 실패: %s" % e
    if "AC Power" not in ps:
        return False, ps.strip().splitlines()[0] if ps.strip() else "unknown"
    try:
        ad = subprocess.run(["pmset", "-g", "adapter"], capture_output=True,
                            text=True, check=True).stdout
    except Exception:
        ad = ""
    return True, (ps.strip().splitlines()[0] + " | " + " ".join(ad.split()))


# ═════════════════════════════════════════════════════════════════════════
# mtime 가드 (종료검증 4)
# ═════════════════════════════════════════════════════════════════════════
def mtime_snapshot():
    snap = {}
    for rel in MTIME_GUARD_GLOBS:
        p = os.path.join(ROOT, rel)
        if os.path.isfile(p):
            snap[rel] = os.path.getmtime(p)
        elif os.path.isdir(p):
            for d, _, fs in os.walk(p):
                for f in sorted(fs):
                    fp = os.path.join(d, f)
                    snap[os.path.relpath(fp, ROOT)] = os.path.getmtime(fp)
    return snap


# ═════════════════════════════════════════════════════════════════════════
# D-5 access.log append
# ═════════════════════════════════════════════════════════════════════════
APPENDS = []


def log_open(rel):
    """봉인 파일 열기 직전 1줄 append. 형식 = sap/redaction.py:75 축자."""
    sealed_dir = os.path.dirname(os.path.join(ROOT, rel))
    assert os.path.basename(sealed_dir) == "_sealed", rel
    line = "%s | OPEN sealed/%s | accessor=%s" % (
        now_kst(), os.path.basename(rel), ACCESSOR)
    ap = os.path.join(sealed_dir, "access.log")
    with open(ap, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())
    APPENDS.append({"access_log": os.path.relpath(ap, ROOT), "line": line,
                    "for_file": rel})
    log("  [access.log +1] %s" % os.path.relpath(ap, ROOT))


# ═════════════════════════════════════════════════════════════════════════
# D-6 로더 재사용 — 읽기전용 ctx shim
# ═════════════════════════════════════════════════════════════════════════
class LoadFail(Exception):
    pass


class RoCtx:
    """`_load_inputs`/`_matrix` 가 요구하는 최소 인터페이스. 쓰기 경로 없음."""

    def __init__(self, root, plan, expected):
        self.root, self.plan, self.expected = root, plan, expected

    def fail(self, code, item="", file=""):
        raise LoadFail("%s|%s|%s" % (code, item, file))


def build_inputs(want_arms):
    """want_arms 의 npz 만 read_scope 로 좁혀 `_load_inputs` 를 호출한다.

    좁히기는 **봉인 접근을 줄이는 방향**이며 estimand·로더 코드에 영향이 없다.
    """
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    import unblinding_run as ur                      # import 시 쓰기 0 (검증済)

    plan = json.loads(open(os.path.join(ROOT, ur.PLAN_REL), "rb").read())
    assert ur.sha256_file(os.path.join(ROOT, ur.PLAN_REL)) == ur.PLAN_SHA256, \
        "plan sha 불일치"
    AU = json.loads(open(os.path.join(
        ROOT, plan["expected_hash_source"]["audit_path"]), "rb").read())
    expected = {"sealed_sha256": AU["sealed_sha256"],
                "labels_sha256": {k: v["sha256"] for k, v in plan["labels"].items()
                                  if isinstance(v, dict)}}
    files = [NPZ[a] for a in want_arms]
    narrowed = dict(plan)
    narrowed["read_scope"] = dict(plan["read_scope"], files=files)
    ctx = RoCtx(ROOT, narrowed, expected)

    for rel in files:                                # D-5 — 열기 직전 append
        log_open(rel)
    data = ur._load_inputs(ctx)
    mats = {a: ur._matrix(ctx, data, NPZ[a], "CN:" + a) for a in want_arms}
    el = ur._eligible(ctx)
    return ur, data, mats, el


# ═════════════════════════════════════════════════════════════════════════
# 계약 정의
# ═════════════════════════════════════════════════════════════════════════
def contracts(n_rows, gi, acyclic_rows, mapped_idx, tert, mapped_mask):
    """(id, treat, base, unit, row_subset|None, meta) 목록."""
    C = []
    C.append(("S0-2_C1", "M2b", "M1b", "scaffold_cluster", None,
              {"purpose": "하네스 자기검사 — results_full.json C1 전 자릿수 대조"}))
    C.append(("S0-2_C2", "M2b", "P-ID", "scaffold_cluster", None,
              {"purpose": "하네스 자기검사 — results_full.json C2 전 자릿수 대조"}))
    for t, b in [("C-CAP", "M1b"), ("P-ID", "M1b"), ("P-FAM", "M1b"),
                 ("M1b", "M0"), ("M1b", "M1"), ("M1", "M0")]:
        C.append(("X1_%s_minus_%s" % (t, b), t, b, "scaffold_cluster", None,
                  {"purpose": "X1 성분 분해"}))
    C.append(("X5_sizeweighted", "M2b", "M1b", "size_weighted", None,
              {"purpose": "X5-③ 기존 size_weighted 구간 재현(B·seed 동일)"}))
    keep = np.setdiff1d(np.arange(n_rows), acyclic_rows)
    for t, b in [("M2b", "M1b"), ("M2b", "P-ID")]:
        C.append(("X7_excl_acyclic_%s_minus_%s" % (t, b), t, b,
                  "scaffold_cluster", keep,
                  {"purpose": "X7 — 비고리 group 약물 제외 subset",
                   "n_rows": int(len(keep))}))
    for k in (0, 1, 2):
        rows = mapped_idx[tert == k]
        for t, b in [("M2b", "M1b"), ("M2b", "P-ID")]:
            C.append(("X9a_T%d_%s_minus_%s" % (k + 1, t, b), t, b,
                      "scaffold_cluster", rows,
                      {"purpose": "X9a — target 수 3분위 %d" % (k + 1),
                       "n_rows": int(len(rows))}))
    for t, b in [("M2b", "M1b"), ("M2b", "P-ID")]:
        C.append(("X12_mapped847_%s_minus_%s" % (t, b), t, b, "scaffold_cluster",
                  np.where(mapped_mask)[0],
                  {"purpose": "X12 — mapped 847 subset",
                   "n_rows": int(mapped_mask.sum())}))
    return C


# ═════════════════════════════════════════════════════════════════════════
# worker
# ═════════════════════════════════════════════════════════════════════════
_G = {}


def _run_one(spec):
    cid, treat, base, unit, rows, meta = spec
    import sap.bootstrap as sb
    mats, y, gi, el = _G["mats"], _G["y"], _G["gi"], _G["el"]
    if rows is None:
        cT, cB, yy, gg = mats[treat], mats[base], y, gi
    else:
        cT, cB, yy, gg = mats[treat][rows], mats[base][rows], y[rows], gi[rows]
    r = sb.paired_scaffold_bootstrap(cB, cT, yy, gg, eligible_pt=el,
                                     B=B_BOOT, seed=SEED_BOOT, unit=unit,
                                     alpha=0.05, return_boot=False)
    r["_id"] = cid
    r["_treat_arm"] = treat
    r["_base_arm"] = base
    r["_n_rows_evaluated"] = int(len(yy))
    r["_subset"] = "all" if rows is None else "subset"
    r["_meta"] = meta
    return r


def _init(mats, y, gi, el):
    _G.update(mats=mats, y=y, gi=gi, el=el)


# ═════════════════════════════════════════════════════════════════════════
def jdump(sub, name, obj):
    d = os.path.join(OUT, sub)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=float)
        f.write("\n")
    return p


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--allow-battery", action="store_true",
                    help="전원 게이트 우회(권장하지 않음)")
    a = ap.parse_args()

    ok, info = power_ok()
    log("[전원] %s" % info)
    if not ok and not a.allow_battery:
        log("[전원] ❌ AC 전원 아님 — 본 계산은 CPU 약 11.5시간이라 배터리로는 완주 불가. "
            "어댑터 연결 후 재실행하십시오(완료분은 _ckpt 에 보존되어 재계산 0).")
        return 15

    os.makedirs(CKPT, exist_ok=True)
    mt0 = mtime_snapshot()

    # ── 입력 적재 (봉인 1회 열람) ─────────────────────────────────────────
    log("[적재] 봉인 consensus 7종 + master_X/Y")
    arms = ["M0", "M1", "M1b", "M2b", "P-ID", "P-FAM", "C-CAP"]
    ur, data, mats, el = build_inputs(arms)
    y, gi = data["y"], data["gi"]
    log("  y %s · groups %d · eligible %d" % (y.shape, len(set(gi.tolist())), len(el)))

    # ── X7/X9a/X12 subset 정의 (봉인 무관 입력) ──────────────────────────
    import pandas as pd
    from confirmatory_oof_rep1 import scaffold_of
    X = pd.read_parquet(os.path.join(ROOT, "data/processed/master_X.parquet"))
    scaf = [scaffold_of(s) for s in X["smiles_canonical"].tolist()]
    acyclic_rows = np.array([i for i, s in enumerate(scaf) if s == ""], dtype=int)
    mapped_mask = np.asarray(np.load(os.path.join(
        ROOT, "data/processed/drug_target_mask_meanpool.npy"))).astype(bool).ravel()
    mapped_idx = np.load(os.path.join(OUT, "X9a", "_mapped_index.npy"))
    tert = np.load(os.path.join(OUT, "X9a", "_tertile_index.npy"))
    log("  비고리 제외 행 %d · mapped %d" % (len(acyclic_rows), mapped_mask.sum()))

    # ── X5-② 가중 점추정 (bootstrap 아님 · 즉시) ────────────────────────
    import sap.metrics as sm
    import sap.bootstrap as sb
    uniq_g = np.unique(gi)
    rows_by_c = [np.where(gi == g)[0] for g in uniq_g]
    sizes = np.array([len(r) for r in rows_by_c])
    expanded = np.concatenate([np.repeat(r, len(r)) for r in rows_by_c])
    w_m1 = sm.macro_ap(y[expanded], mats["M1b"][expanded], el)["macro_ap"]
    w_m2 = sm.macro_ap(y[expanded], mats["M2b"][expanded], el)["macro_ap"]
    w_delta = float(w_m2 - w_m1)
    jdump("X5", "x5_weighted_point_estimate.json", {
        "_doc": "블록 CN X5-② — size_weighted 재표집이 함의하는 가중을 반영한 "
                "**가중 점추정**. bootstrap 아님(결정적) · p-value 0.",
        "definition_formula": (
            "size_weighted 추출에서 cluster i 의 기대 등장 횟수는 G·s_i/Σs 이므로 "
            "replicate 안 cluster i 의 기대 행 수 = G·s_i²/Σs → 약물 1행의 기대 가중 "
            "w_j = s_{c(j)}. 이를 결정적으로 실현한 평가셋은 각 cluster 의 행을 "
            "s_i 번 복제한 집합이며(총 Σs_i² 행), 그 위에서 "
            "Δ_w = macroAP(M2b) − macroAP(M1b) (sap/metrics.py:macro_ap, "
            "eligible 370 고정)."),
        "n_clusters": int(len(uniq_g)),
        "sum_sizes": int(sizes.sum()),
        "sum_sizes_squared": int((sizes ** 2).sum()),
        "n_expanded_rows": int(len(expanded)),
        "n_eff_clusters_kish": sb.n_eff_clusters(sizes),
        "weighted_macro_ap_M1b": float(w_m1),
        "weighted_macro_ap_M2b": float(w_m2),
        "weighted_delta": w_delta,
        "unweighted_delta_obs_recorded": -0.006324167855457974,
        "size_weighted_percentile_ci_recorded": [0.0054142690067430655,
                                                 0.010192215823900916],
        "weighted_delta_inside_recorded_percentile_ci": bool(
            0.0054142690067430655 <= w_delta <= 0.010192215823900916),
    })
    log("[X5-②] 가중 Δ = %+.7f (확장 %d 행)" % (w_delta, len(expanded)))

    # ── X4 실현값 (봉인 checkpoint.jsonl) ───────────────────────────────
    x4p = os.path.join(CKPT, "X4_realizations.json")
    if not os.path.exists(x4p):
        # 무결성: 감사 등재 sha256 과 대조한 뒤에만 판독한다.
        AU = json.loads(open(os.path.join(
            ROOT, "experiments/provenance/pre_unblinding_audit_v3.json"), "rb").read())
        want = AU["sealed_sha256"].get(NULL_CKPT)
        got = hashlib.sha256(open(os.path.join(ROOT, NULL_CKPT), "rb").read()).hexdigest()
        if want is None or want != got:
            log("[X4] ❌ checkpoint.jsonl sha256 불일치 — 기대 %s 실측 %s"
                % (want, got))
            return 13
        log("[X4] checkpoint.jsonl sha256 대조 OK (%s…)" % got[:16])
        log_open(NULL_CKPT)
        rows = []
        with open(os.path.join(ROOT, NULL_CKPT), encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    rows.append(json.loads(ln))
        pub = json.loads(open(os.path.join(
            ROOT, "experiments/runs/v3_unblinding/results/sealed_publish/"
            "experiments__runs__v3_null_MAIN___sealed__null_result.json"),
            encoding="utf-8").read())
        t_obs = pub["T_obs"]
        res = {}
        for mode in ("global", "family", "global_ALT", "family_ALT"):
            v = np.array([r["macro_AP"] for r in rows if r["mode"] == mode],
                         dtype=float)
            if len(v) == 0:
                continue
            res[mode] = {
                "n_realizations": int(len(v)),
                "null_mean": float(v.mean()),
                "null_median": float(np.median(v)),
                "null_sd": float(v.std(ddof=1)),
                "null_min": float(v.min()),
                "null_max": float(v.max()),
                "T_obs": t_obs,
                "n_below_obs": int((v < t_obs).sum()),
                "frac_below_obs": float((v < t_obs).mean()),
                "n_ge_obs": int((v >= t_obs).sum()),
                "frac_ge_obs": float((v >= t_obs).mean()),
                "enters_p_emp": bool(mode in ("global", "family")),
            }
        with open(x4p, "w", encoding="utf-8") as f:
            json.dump({"source": NULL_CKPT, "modes": res}, f,
                      ensure_ascii=False, indent=2)
        log("[X4] 실현값 집계 완료 (%d mode)" % len(res))

    # ── bootstrap 계약 ──────────────────────────────────────────────────
    specs = contracts(y.shape[0], gi, acyclic_rows, mapped_idx, tert, mapped_mask)
    todo = [s for s in specs if not os.path.exists(
        os.path.join(CKPT, s[0] + ".json"))]
    log("[계약] 전체 %d · 완료 %d · 남은 %d · workers %d"
        % (len(specs), len(specs) - len(todo), len(todo), a.workers))

    if todo:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor, as_completed
        ctxmp = mp.get_context("fork")
        _init(mats, y, gi, el)                       # fork 상속용
        import time
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=a.workers, mp_context=ctxmp) as ex:
            fut = {ex.submit(_run_one, s): s[0] for s in todo}
            done = 0
            for f in as_completed(fut):
                cid = fut[f]
                r = f.result()
                with open(os.path.join(CKPT, cid + ".json"), "w",
                          encoding="utf-8") as fh:
                    json.dump(r, fh, ensure_ascii=False, indent=2, default=float)
                done += 1
                log("  [%2d/%2d] %-36s Δ=%+.7f  CI[%s] %.0fs"
                    % (done, len(todo), cid, r["delta_obs"],
                       "nan,nan" if r["ci_primary"]["status"] != "estimable"
                       else "%+.7f,%+.7f" % (r["ci_primary"]["low"],
                                             r["ci_primary"]["high"]),
                       time.time() - t0))

    # ── mtime 가드 ──────────────────────────────────────────────────────
    mt1 = mtime_snapshot()
    drift = sorted(k for k in set(mt0) | set(mt1) if mt0.get(k) != mt1.get(k))
    jdump("_manifest", "sealed_guard.json", {
        "_doc": "블록 CN — 봉인 단계 가드. mtime 불변 + access.log append 목록.",
        "mtime_guard_targets": MTIME_GUARD_GLOBS,
        "n_files_watched": len(mt0),
        "mtime_drift": drift,
        "mtime_drift_count": len(drift),
        "access_log_appends": APPENDS,
        "n_access_log_appends_this_launch": len(APPENDS),
        "power": info,
        "finished_at_kst": now_kst(),
    })
    log("[가드] mtime drift %d · access.log append %d" % (len(drift), len(APPENDS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
