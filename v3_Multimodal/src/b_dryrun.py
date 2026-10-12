#!/usr/bin/env python3
"""b_dryrun.py — [블록 AI · docs/97] 전규모 합성 드라이런 벽시계 계측 → `B` 후보 산출.

⛔ 무결성 (`docs/97` §0)
  · **`B` 문면 동결 0** — 본 스크립트는 계측만 한다. `sap/rqint.py` 는 **0바이트 수정**이며
    `B_DEFINITION_STATUS` 리터럴을 읽지도 쓰지도 않는다(결과 dict 에 실려 오는 것만 기록).
  · **예측행렬 100% 합성** — 확증 예측·OOF·`_sealed/` 미접근. 데이터 경로는
    `data/processed/master_X.parquet` · `master_Y.parquet` 두 개뿐(`rqint_calibration` 재사용).
  · **SAP 1.2 재동결 0 · manifest 0바이트 · GIN 착수 0 · 네트워크 0 · commit/push 0.**

★ 재구현 0 — fixture·합성점수·시드규칙·RAM 게이트·전원 게이트는 모두
  `rqint_calibration.py` 를 **import 재사용**한다. 새 fixture 생성 0.
★ 사전명시 = `v3_Multimodal/config/b_dryrun_prespec.json` (측정 이전 동결). 본 스크립트는
  그 파일을 **읽어 대조만** 하고 수정하지 않는다.

실행:
  .venv/bin/python3 v3_Multimodal/src/b_dryrun.py --stage stair
  .venv/bin/python3 v3_Multimodal/src/b_dryrun.py --stage decisive
"""
from __future__ import annotations

import os

_THREADS = os.environ.get("RQINT_THREADS", "1")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = _THREADS

import sys                                                          # noqa: E402
import json                                                         # noqa: E402
import time                                                         # noqa: E402
import math                                                         # noqa: E402
import hashlib                                                      # noqa: E402
import argparse                                                     # noqa: E402
import multiprocessing as mp                                        # noqa: E402

import numpy as np                                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import rqint_calibration as rc                                      # noqa: E402
from sap import rqint as sap_rqint                                  # noqa: E402

OUT = os.path.join(ROOT, "experiments", "rqint", "b_dryrun")
PRESPEC = os.path.join(ROOT, "v3_Multimodal", "config", "b_dryrun_prespec.json")
STAIR_N = (200, 500, 1000)
CAP_SECONDS = 24 * 3600.0
LINEARITY_TOL = 0.10


def _prespec():
    with open(PRESPEC, "rb") as f:
        raw = f.read()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def _null_strengths():
    """효과 주입 0 = C0 강도표(전 arm BASE_STRENGTH)."""
    st = rc.strengths_for("C0", 0.0)
    rc._assert_scenario("C0", st)
    return st


def _one_run(n_coin, rep_seed, audit_draws, st, F, q=None):
    """rqint_test 1회. 벽시계는 합성점수 생성부터 반환까지."""
    t0 = time.time()
    P_RF, P_GIN = rc.synth_scores(F["y"], rep_seed, st)
    t_synth = time.time() - t0
    res = sap_rqint.rqint_test(P_RF, P_GIN, F["y"], F["groups"], F["eligible"],
                               n_coin_vectors=int(n_coin),
                               seed=int(rep_seed) + rc.COIN_SEED_OFFSET,
                               pair_complement=True,
                               complement_audit_draws=int(audit_draws),
                               return_perm=False)
    wall = time.time() - t0
    p = float(res["p_two_sided"])
    nperm = int(res["n_permutation_values"])
    row = {
        "n_coin_vectors": int(res["n_coin_vectors"]),
        "n_permutation_values": nperm,
        "n_groups_G": int(res["n_groups_G"]),
        "rep_seed": int(rep_seed),
        "coin_seed": int(rep_seed) + rc.COIN_SEED_OFFSET,
        "complement_audit_draws_requested": int(audit_draws),
        "wall_seconds": wall,
        "synth_seconds": t_synth,
        "per_permutation_seconds": float(res["per_permutation_seconds"]),
        "per_reference_value_seconds": float(res["per_reference_value_seconds"]),
        "complement_audit_seconds": float(res["complement_audit_seconds"]),
        "complement_audit": res["complement_audit"],
        "complement_identity_used": bool(res["complement_identity_used"]),
        "T_obs": float(res["T_obs"]),
        "delta_rf": float(res["delta_rf"]),
        "delta_gin": float(res["delta_gin"]),
        "count_abs_ge_obs": int(res["count_abs_ge_obs"]),
        "p_two_sided": p,
        "p_formula": res["p_formula"],
        "se_mc_formula": "SE_MC = sqrt( p*(1-p) / n_permutation_values )",
        "se_mc": math.sqrt(p * (1.0 - p) / nperm),
        "B_definition_reported_by_module": res["B_definition"],
        "u_wall_per_coin": wall / float(n_coin),
        "u_loop_per_coin": float(res["per_permutation_seconds"]),
        "threads_limit": int(_THREADS),
    }
    if q is not None:
        q.put(row)
    return row


def _fixture():
    d = rc.load_design_arrays()
    fx = rc.build_fixtures(d)
    F = fx["full"]
    assert F["y"].shape == (rc.EXPECT_N, rc.EXPECT_K), F["y"].shape
    assert int(F["profile"]["G"]) == rc.EXPECT_G
    return F, fx


def _gate(stage):
    env = rc.require_ac_power()
    if not env["caffeinate_running"]:
        raise SystemExit("★중단★ `caffeinate -dimsu` 미실행 — 장시간 런 전 필수.")
    pre, sha = _prespec()
    return {"stage": stage, "env": env, "prespec_sha256": sha,
            "prespec_frozen_at_kst": pre["frozen_at_kst"], "prespec": pre}


def stage_stair(a):
    g = _gate("stair")
    pre = g.pop("prespec")
    F, fx = _fixture()
    st = _null_strengths()
    seeds = pre["seed_rule"]["stair_seeds"]
    rows = []
    for n in STAIR_N:
        rs = int(seeds[str(n)])
        print(f"[stair] n_coin={n} rep_seed={rs} …", flush=True)
        r = _one_run(n, rs, 0, st, F)
        print(f"[stair] n_coin={n} wall={r['wall_seconds']:.2f}s "
              f"u_wall={r['u_wall_per_coin']:.6f} u_loop={r['u_loop_per_coin']:.6f}", flush=True)
        rows.append(r)
    u_wall = [r["u_wall_per_coin"] for r in rows]
    u_loop = [r["u_loop_per_coin"] for r in rows]

    def disp(v):
        m = float(np.median(v))
        return {"median": m, "min": float(min(v)), "max": float(max(v)),
                "relative_spread": float((max(v) - min(v)) / m)}

    dw, dl = disp(u_wall), disp(u_loop)
    ok = dw["relative_spread"] <= LINEARITY_TOL
    u = dw["median"]
    t_synth = float(np.median([r["synth_seconds"] for r in rows]))
    A = 1000

    def that(n):
        return t_synth + n * u + min(A, n) * u

    band = pre["extrapolation_policy"]["band_hours"]

    def verdict(n):
        h = that(n) / 3600.0
        inside = band[0] <= h <= band[1]
        return {"n_coin_vectors": n, "T_hat_seconds": that(n), "T_hat_hours": h,
                "inside_band": inside,
                "extrapolation_allowed": (not inside),
                "vs_24h": ("exceeds" if h > 24.0 else "within")}

    out = {**g, "prespec_frozen_at_kst": g["prespec_frozen_at_kst"],
           "stair_rows": rows,
           "u_wall_stats": dw, "u_loop_stats": dl,
           "linearity_tol": LINEARITY_TOL, "linearity_pass": bool(ok),
           "u_hat_primary": u, "u_hat_basis": "median of wall_k / n_k (audit 0, solo)",
           "t_synth_median_seconds": t_synth,
           "cost_model": pre["cost_model"]["formula"],
           "F_C4UNIT_reference_s": 1.5063390654338291,
           "ratio_u_hat_over_C4": u / 1.5063390654338291,
           "F_UNIT_FULL_reference_s": rc.F_UNIT_FULL,
           "ratio_u_hat_over_F_UNIT_FULL": u / rc.F_UNIT_FULL,
           "projection": {"interp_a_100000": verdict(100000),
                          "interp_b_50000": verdict(50000)},
           "fixture": {"N": int(F["y"].shape[0]), "K": int(F["y"].shape[1]),
                       "G": int(F["profile"]["G"]),
                       "row_idx_sha256": fx["row_idx_sha256"]},
           "confirmatory_predictions_loaded": False,
           "effect_injection": 0.0}
    rc.dump(os.path.join(OUT, "stair.json"), out)
    print(json.dumps({k: out[k] for k in
                      ("linearity_pass", "u_hat_primary", "u_wall_stats", "u_loop_stats",
                       "ratio_u_hat_over_C4", "projection")},
                     ensure_ascii=False, indent=2, default=str), flush=True)
    if not ok:
        raise SystemExit(f"★중단★ 선형성 상대 산포 {dw['relative_spread']:.4f} > {LINEARITY_TOL} "
                         "— 외삽 근거 붕괴. 자체 판단으로 진행하지 않는다(docs/97 AI-2).")


def stage_decisive(a):
    g = _gate("decisive")
    pre = g.pop("prespec")
    cfg = pre["decisive_config"]
    n_coin = int(cfg["n_coin_vectors"])
    rep_seed = int(pre["seed_rule"]["decisive_seed"])
    F, fx = _fixture()
    st = _null_strengths()

    hb = os.path.join(OUT, "decisive_heartbeat.jsonl")
    ram = rc.RamSampler()
    ram.start()
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    t0 = time.time()
    proc = ctx.Process(target=_one_run,
                       args=(n_coin, rep_seed, rc.AUDIT_DRAWS, st, F, q))
    proc.start()
    print(f"[decisive] pid={proc.pid} n_coin={n_coin} rep_seed={rep_seed} "
          f"cap={CAP_SECONDS/3600:.0f}h started", flush=True)
    row, cap_hit, ac_lost = None, False, False
    while True:
        proc.join(timeout=60.0)
        el = time.time() - t0
        alive = proc.is_alive()
        env = rc.env_snapshot()
        with open(hb, "a", encoding="utf-8") as f:
            f.write(json.dumps({"when_kst": rc.now_kst(), "elapsed_s": el,
                                "elapsed_h": el / 3600.0, "alive": alive,
                                "on_ac_power": env["on_ac_power"],
                                "loadavg": env["loadavg_1_5_15"],
                                "rss_gib": (ram.samples[-1] if ram.samples else None)},
                               ensure_ascii=False) + "\n")
        if not alive:
            break
        if not env["on_ac_power"]:
            ac_lost = True
            proc.terminate()
            proc.join(30)
            break
        if el >= CAP_SECONDS:
            cap_hit = True
            proc.terminate()
            proc.join(30)
            break
    wall_total = time.time() - t0
    ram.stop()
    if not q.empty():
        row = q.get()
    out = {**g, "decisive_config": cfg, "rep_seed": rep_seed,
           "cap_seconds": CAP_SECONDS, "cap_hit": cap_hit, "ac_power_lost": ac_lost,
           "wall_seconds_total": wall_total, "wall_hours_total": wall_total / 3600.0,
           "completed": bool(row is not None and not cap_hit and not ac_lost),
           "result": row,
           "ram_samples_max_gib": (max(ram.samples) if ram.samples else None),
           "ram_gate_gib": rc.RAM_GATE_GIB, "ram_breaches": ram.breaches,
           "d15_verdict": None,
           "confirmatory_predictions_loaded": False,
           "effect_injection": 0.0,
           "fixture": {"N": int(F["y"].shape[0]), "K": int(F["y"].shape[1]),
                       "G": int(F["profile"]["G"])}}
    if cap_hit:
        out["d15_verdict"] = "exceeds_24h (hard cap reached — 유효 판정)"
    elif row is not None:
        out["d15_verdict"] = ("exceeds_24h" if wall_total > CAP_SECONDS else "within_24h")
    rc.dump(os.path.join(OUT, "decisive.json"), out)
    print(json.dumps({k: out[k] for k in ("completed", "cap_hit", "ac_power_lost",
                                          "wall_hours_total", "d15_verdict")},
                     ensure_ascii=False, indent=2), flush=True)
    if ac_lost:
        raise SystemExit("★중단★ AC 전원 이탈 — 측정치 무효(docs/97 AI-3 중단 조건).")
    if row is not None and row["complement_audit"]["failures"] > 0:
        raise SystemExit("★중단★ 여집합 항등식 감사 실패 ≥ 1 (docs/97 AI-3 중단 조건).")


STAGES = {"stair": stage_stair, "decisive": stage_decisive}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    STAGES[ap.parse_args().stage](ap.parse_args())
