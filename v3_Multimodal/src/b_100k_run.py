#!/usr/bin/env python3
"""b_100k_run.py — [블록 AJ · docs/98] (가) 해석 실주행: 동전 100,000 · 24h 하드 캡.

⛔ 무결성 (`docs/98` §0)
  · **`B` 문면 동결 0** — 계측·판정까지만. `sap/rqint.py` 는 **0바이트 수정**이며 정의 채택 선언 0.
  · **블록 AI 산출물 4종 0바이트** — `b_dryrun_prespec.json`·`stair.json`·`decisive.json`·`b_dryrun.py`.
    본 파일은 `b_dryrun` 을 **읽기 전용 import** 로만 쓴다(수정 0).
  · **예측행렬 100% 합성** · 효과 주입 0 · `_sealed/` 접근 0 · 네트워크 0 · commit/push 0.

★ 왜 신규 파일인가 — `b_dryrun.py` 의 `--stage decisive` 는 동전 수를 AI prespec 의
  `decisive_config`(50,000, **측정 전 동결**) 에서 읽고 `--n-coin` 류 인자가 없다.
  AI prespec 을 고치면 `docs/98` §0(AI 산출물 0바이트) 위반이므로, `docs/98` AJ-2 가 허용한 대로
  **신규 파일로 분리**하고 fixture·합성점수·시드규칙·RAM/전원 게이트는 전부 import 재사용한다(재구현 0).

★ 사전명시 = `v3_Multimodal/config/b_100k_prespec.json` (실주행 이전 동결). 읽어 대조만 하고 수정 0.

실행:
  .venv/bin/python3 v3_Multimodal/src/b_100k_run.py --stage run
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

import b_dryrun as bd                                               # noqa: E402  (읽기 전용)
rc = bd.rc                                                          # rqint_calibration
sap_rqint = bd.sap_rqint                                            # sap.rqint (동결 모듈)

OUT = os.path.join(ROOT, "experiments", "rqint", "b_100k")
PRESPEC = os.path.join(ROOT, "v3_Multimodal", "config", "b_100k_prespec.json")
CKPT_B = 50000                                                      # AJ-2-b 결정성 체크포인트


def _prespec():
    with open(PRESPEC, "rb") as f:
        raw = f.read()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def _run_child(n_coin, rep_seed, audit_draws, st, F, q):
    """rqint_test 1회 (동전 n_coin). 자식 프로세스에서 실행.

    `return_perm=True` 는 기존 인자이며 계산에 영향이 없다(`out['perm'] = perm` 만 추가).
    체크포인트·표준편차 계산은 **자식 안에서** 끝내고 큐에는 스칼라만 싣는다.
    """
    t0 = time.time()
    P_RF, P_GIN = rc.synth_scores(F["y"], rep_seed, st)
    t_synth = time.time() - t0
    res = sap_rqint.rqint_test(P_RF, P_GIN, F["y"], F["groups"], F["eligible"],
                               n_coin_vectors=int(n_coin),
                               seed=int(rep_seed) + rc.COIN_SEED_OFFSET,
                               pair_complement=True,
                               complement_audit_draws=int(audit_draws),
                               return_perm=True)
    wall = time.time() - t0
    perm = np.asarray(res.pop("perm"))
    n_coin = int(res["n_coin_vectors"])
    t_star = perm[:n_coin]                       # 항등식 경로: perm = concat([t_star, -t_star])
    np.save(os.path.join(OUT, "t_star.npy"), t_star)

    t_obs = float(res["T_obs"])
    thr = abs(t_obs) - sap_rqint._EPS

    # ── AJ-2-b: b = 50,000 시점 러닝 카운트(참조분포 100,000 기준) ────────
    ts50 = t_star[:CKPT_B]
    perm50 = np.concatenate([ts50, -ts50])
    count50 = int(np.sum(np.abs(perm50) >= thr))
    p50 = (1.0 + count50) / (perm50.size + 1.0)

    # 감사 draw 중 b < 50,000 인 개수(파생 경과시간 산출용) — audit_rng 규칙 재현
    n_audit = int(min(audit_draws, n_coin))
    aidx = np.random.default_rng(int(rep_seed) + rc.COIN_SEED_OFFSET + 1_000_003) \
             .choice(n_coin, size=n_audit, replace=False)
    n_audit_before = int(np.sum(aidx < CKPT_B))

    p = float(res["p_two_sided"])
    nperm = int(res["n_permutation_values"])
    u_audit = (float(res["complement_audit_seconds"]) / n_audit) if n_audit else 0.0
    row = {
        "n_coin_vectors": n_coin,
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
        "checkpoint_b50000": {
            "b": CKPT_B,
            "reference_distribution_at_b": int(perm50.size),
            "count_abs_ge_obs": count50,
            "p_two_sided": p50,
            "elapsed_seconds_derived": (t_synth + CKPT_B * float(res["per_permutation_seconds"])
                                        + n_audit_before * u_audit),
            "elapsed_derivation": ("t_synth + 50000·per_permutation_seconds + "
                                   "(b<50000 인 감사 draw 수)·(complement_audit_seconds/n_audit) — "
                                   "**파생값**(루프 내 직접 계측은 동결 모듈 계측 삽입을 요구하므로 하지 않았다). "
                                   "판정에 쓰지 않는다."),
            "n_audit_draws_before_b": n_audit_before,
        },
    }
    q.put(row)
    return row


def stage_run(a):
    pre, sha = _prespec()
    cfg = pre["run_config"]
    n_coin = int(cfg["n_coin_vectors"])
    audit = int(cfg["complement_audit_draws"])
    cap = float(cfg["cap_seconds"])
    rep_seed = int(pre["seed_policy"]["rep_seed"])

    env = rc.require_ac_power()
    if not env["caffeinate_running"]:
        raise SystemExit("★중단★ `caffeinate -dimsu` 미실행 — 장시간 런 전 필수.")
    if str(env["env_thread_vars"].get("OMP_NUM_THREADS")) != "1":
        raise SystemExit("★중단★ threads_limit 1 위반.")

    F, fx = bd._fixture()
    st = bd._null_strengths()

    hb = os.path.join(OUT, "run_heartbeat.jsonl")
    ram = rc.RamSampler()
    ram.start()
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    t0 = time.time()
    started_kst = rc.now_kst()
    proc = ctx.Process(target=_run_child, args=(n_coin, rep_seed, audit, st, F, q))
    proc.start()
    print(f"[run] pid={proc.pid} n_coin={n_coin} rep_seed={rep_seed} "
          f"cap={cap/3600:.0f}h started {started_kst}", flush=True)
    u_ref = 0.6976782551174681                    # F-AI50K 실측 단가(진행 추정 전용, 판정 미사용)
    row, cap_hit, ac_lost = None, False, False
    while True:
        proc.join(timeout=60.0)
        el = time.time() - t0
        alive = proc.is_alive()
        e = rc.env_snapshot()
        with open(hb, "a", encoding="utf-8") as f:
            f.write(json.dumps({"when_kst": rc.now_kst(), "elapsed_s": el,
                                "elapsed_h": el / 3600.0, "alive": alive,
                                "coins_estimated": min(n_coin, int(el / u_ref)),
                                "progress_estimated": min(1.0, el / u_ref / n_coin),
                                "on_ac_power": e["on_ac_power"],
                                "loadavg": e["loadavg_1_5_15"],
                                "rss_gib": (ram.samples[-1] if ram.samples else None)},
                               ensure_ascii=False) + "\n")
        if not alive:
            break
        if not e["on_ac_power"]:
            ac_lost = True
            proc.terminate(); proc.join(30)
            break
        if el >= cap:
            cap_hit = True
            proc.terminate(); proc.join(30)
            break
    wall_total = time.time() - t0
    ram.stop()
    if not q.empty():
        row = q.get()
    proc.join(30)

    out = {"stage": "run", "block": "AJ (docs/98)",
           "env": env, "started_kst": started_kst, "ended_kst": rc.now_kst(),
           "prespec_sha256": sha, "prespec_frozen_at_kst": pre["frozen_at_kst"],
           "ai_prespec_sha256": "9a2545eb0d897f304f23350e1363415bc9642a7895fca87b8306f1eadcfa7939",
           "run_config": cfg, "rep_seed": rep_seed,
           "cap_seconds": cap, "cap_hit": cap_hit, "ac_power_lost": ac_lost,
           "wall_seconds_total": wall_total, "wall_hours_total": wall_total / 3600.0,
           "completed": bool(row is not None and not cap_hit and not ac_lost),
           "result": row,
           "ram_samples_max_gib": (max(ram.samples) if ram.samples else None),
           "ram_gate_gib": rc.RAM_GATE_GIB, "ram_breaches": ram.breaches,
           "d15_verdict": None, "d15_branch": None,
           "confirmatory_predictions_loaded": False,
           "effect_injection": 0.0,
           "fixture": {"N": int(F["y"].shape[0]), "K": int(F["y"].shape[1]),
                       "G": int(F["profile"]["G"]), "row_idx_sha256": fx["row_idx_sha256"]}}

    # ── d15_decision_rule (측정 전 동결 · 2분기) ───────────────────────────
    if cap_hit:
        out["d15_verdict"] = "exceeds_24h (hard cap reached — 유효 판정)"
        out["d15_branch"] = "캡 도달(미완주) → (가) 24h 초과 확정 → D15 에 따라 50,000 하향"
    elif row is not None and not ac_lost:
        exceeded = wall_total > cap
        out["d15_verdict"] = "exceeds_24h" if exceeded else "within_24h"
        out["d15_branch"] = ("캡 도달(미완주) → (가) 24h 초과 확정 → 50,000 하향" if exceeded else
                             "완주 & 벽시계 ≤ 24h → (가) 하향 조건 미충족 → "
                             "B = 동전 100,000(참조분포 200,000) 후보 성립")

    # ── AJ-2-b / AJ-2-c 검증 ──────────────────────────────────────────────
    chk = {"ckpt_expected_count": 67262, "ckpt_expected_p": 0.6726232737672623,
           "obs_expected": pre["observed_statistic_check"]["expect_byte_identical_to_block_AI"]}
    if row is not None:
        c = row["checkpoint_b50000"]
        chk["ckpt_actual_count"] = c["count_abs_ge_obs"]
        chk["ckpt_match"] = (c["count_abs_ge_obs"] == 67262)
        chk["ckpt_p_match"] = (repr(c["p_two_sided"]) == repr(0.6726232737672623))
        chk["obs_actual"] = {k: row[k] for k in ("T_obs", "delta_rf", "delta_gin")}
        chk["obs_match"] = all(repr(row[k]) == repr(v)
                               for k, v in chk["obs_expected"].items())
        chk["reference_distribution_realized"] = row["n_permutation_values"]
        chk["reference_distribution_match"] = (row["n_permutation_values"] == 2 * n_coin)
    out["determinism_checks"] = chk

    rc.dump(os.path.join(OUT, "run.json"), out)
    print(json.dumps({k: out[k] for k in ("completed", "cap_hit", "ac_power_lost",
                                          "wall_hours_total", "d15_verdict",
                                          "d15_branch", "determinism_checks")},
                     ensure_ascii=False, indent=2, default=str), flush=True)

    if ac_lost:
        raise SystemExit("★중단★ AC 전원 이탈 — 측정치 무효(docs/98 AJ-2 중단 조건).")
    if row is not None:
        if row["complement_audit"]["failures"] > 0:
            raise SystemExit("★중단★ 여집합 항등식 감사 실패 ≥ 1 (docs/98 AJ-2 중단 조건).")
        if not chk.get("ckpt_match"):
            raise SystemExit(f"★중단★ AJ-2-b 결정성 위반 — b=50,000 러닝 카운트 "
                             f"{chk.get('ckpt_actual_count')} ≠ 67262.")
        if not chk.get("obs_match"):
            raise SystemExit("★중단★ AJ-2-c 관측통계량 불일치 — fixture 재현성 붕괴.")
    if out["ram_breaches"]:
        raise SystemExit("★중단★ RAM 게이트 브리치.")


STAGES = {"run": stage_run}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    a = ap.parse_args()
    STAGES[a.stage](a)
