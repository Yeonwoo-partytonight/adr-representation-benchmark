#!/usr/bin/env python3
"""[블록 AJ] 착수 전 소규모 자가시험 — AJ-2-b 체크포인트 계산의 **전제** 검증.

전제 = ① 동전 스트림이 단일 `default_rng(coin_seed)` 직렬이라 큰 run 의 앞부분이
작은 run 과 **prefix 관계**다 ② 여집합 감사(`complement_audit_draws`)는 `t_star` 를 **교란하지 않는다**.

검증법 = n_coin 100(감사 0) 과 n_coin 200(감사 전수) 을 돌려
`t_star_200[:100]` 이 `t_star_100` 과 **바이트 동일**인지 본다.
★ 계측·판정과 무관한 자가시험이며 본런 산출물(`run.json`·`t_star.npy`)을 건드리지 않는다.
"""
import os, sys, json, hashlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))

import b_dryrun as bd
rc, sap_rqint = bd.rc, bd.sap_rqint

F, _ = bd._fixture()
st = bd._null_strengths()
REP = 860260813
SEED = REP + rc.COIN_SEED_OFFSET

def run(n, audit):
    P_RF, P_GIN = rc.synth_scores(F["y"], REP, st)
    r = sap_rqint.rqint_test(P_RF, P_GIN, F["y"], F["groups"], F["eligible"],
                             n_coin_vectors=n, seed=SEED, pair_complement=True,
                             complement_audit_draws=audit, return_perm=True)
    perm = np.asarray(r.pop("perm"))
    return r, perm[:n]

rA, tA = run(100, 0)
rB, tB = run(200, 1000)

hA = hashlib.sha256(tA.tobytes()).hexdigest()
hB = hashlib.sha256(tB[:100].tobytes()).hexdigest()
prefix_ok = bool(np.array_equal(tA, tB[:100])) and hA == hB

# 체크포인트 재현 — B run 안에서 b=100 시점 카운트가 A run 의 count 와 일치하는가
thr = abs(float(rA["T_obs"])) - sap_rqint._EPS
perm100 = np.concatenate([tB[:100], -tB[:100]])
count_from_B = int(np.sum(np.abs(perm100) >= thr))
ckpt_ok = (count_from_B == int(rA["count_abs_ge_obs"]))

obs_ok = (repr(rA["T_obs"]) == repr(rB["T_obs"])
          and repr(rA["delta_rf"]) == repr(rB["delta_rf"])
          and repr(rA["delta_gin"]) == repr(rB["delta_gin"]))

out = {"purpose": "AJ-2-b 전제 자가시험(prefix · 감사 비교란 · 체크포인트 재현)",
       "runA": {"n_coin": 100, "audit": 0, "count_abs_ge_obs": int(rA["count_abs_ge_obs"]),
                "n_permutation_values": int(rA["n_permutation_values"]),
                "wall_note": "자가시험 — 벽시계 판정 미사용"},
       "runB": {"n_coin": 200, "audit_requested": 1000,
                "audit_checked": rB["complement_audit"]["draws_checked"],
                "audit_failures": rB["complement_audit"]["failures"],
                "count_abs_ge_obs": int(rB["count_abs_ge_obs"])},
       "t_star_prefix_sha256_A": hA, "t_star_prefix_sha256_B_first100": hB,
       "prefix_identical": prefix_ok,
       "checkpoint_recomputed_from_B": count_from_B,
       "checkpoint_matches_runA": ckpt_ok,
       "observed_statistic_invariant_to_n_coin": obs_ok,
       "T_obs": float(rA["T_obs"]), "delta_rf": float(rA["delta_rf"]),
       "delta_gin": float(rA["delta_gin"]),
       "matches_block_AI_observed": (repr(float(rA["T_obs"])) == repr(0.0031802114140302242)
                                     and repr(float(rA["delta_rf"])) == repr(0.00038510137913283504)
                                     and repr(float(rA["delta_gin"])) == repr(-0.002795110034897389)),
       "all_pass": bool(prefix_ok and ckpt_ok and obs_ok)}
with open(os.path.join(HERE, "prefix_smoke.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
sys.exit(0 if out["all_pass"] and out["matches_block_AI_observed"] else 1)
