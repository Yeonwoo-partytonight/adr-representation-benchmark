#!/usr/bin/env python3
"""[블록 AJ · docs/98 AJ-3] 양 해석 SE_MC 나란히 — R2 의 정의 선택 근거.

★ 정의 채택 선언 0 — (가)/(나) 각각의 실측과 그 함의까지만 적는다.
★ 이 p 는 **100% 합성 예측 위의 값**이라 확증 결과가 아니다.
"""
import os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
J = lambda p: json.load(open(p, encoding="utf-8"))

a = J(os.path.join(HERE, "run.json"))["result"]                          # (가) 동전 100,000
b = J(os.path.join(ROOT, "experiments", "rqint", "b_dryrun", "decisive.json"))["result"]  # (나) 동전 50,000

FORMULA = "SE_MC = sqrt( p·(1−p) / n_permutation_values )"

def side(tag, name, r, wall_h, src):
    p, n = float(r["p_two_sided"]), int(r["n_permutation_values"])
    return {"interpretation": tag, "meaning": name,
            "n_coin_vectors": int(r["n_coin_vectors"]),
            "n_permutation_values": n,
            "wall_hours": wall_h,
            "p_two_sided": p,
            "se_mc": math.sqrt(p * (1.0 - p) / n),
            "se_mc_recorded_by_runner": float(r["se_mc"]),
            "count_abs_ge_obs": int(r["count_abs_ge_obs"]),
            "source": src}

run = J(os.path.join(HERE, "run.json"))
A = side("(가)", "B = 동전 수 (n_coin_vectors)", a, run["wall_hours_total"],
         "experiments/rqint/b_100k/run.json (블록 AJ 실측)")
B = side("(나)", "B = 참조분포 크기 (n_permutation_values)", b,
         J(os.path.join(ROOT, "experiments", "rqint", "b_dryrun", "decisive.json"))["wall_hours_total"],
         "experiments/rqint/b_dryrun/decisive.json (블록 AI 실측)")

ratio = A["se_mc"] / B["se_mc"]
out = {
    "formula_verbatim": FORMULA,
    "interpretation_a": A,
    "interpretation_b": B,
    "se_ratio_a_over_b": ratio,
    "one_over_sqrt2": 1.0 / math.sqrt(2.0),
    "se_ratio_matches_1_over_sqrt2_within_1pct": abs(ratio - 1.0 / math.sqrt(2.0)) < 0.01,
    "quantitative_note": (
        f"참조분포가 2배({B['n_permutation_values']:,} → {A['n_permutation_values']:,})면 "
        f"SE_MC 는 1/√2 = {1.0/math.sqrt(2.0):.5f} 배가 된다 — 실측 비 {ratio:.5f}. "
        f"즉 (가) 를 택하면 SE_MC {A['se_mc']:.5g}, (나) 를 택하면 {B['se_mc']:.5g} 로 "
        f"정밀도는 √2 배 좋아지고 비용은 2배가 된다. **이 정량 대비가 R2 의 정의 선택 근거다.**"),
    "synthetic_only_caveat": (
        "★ 양쪽 p·SE_MC 는 모두 **100% 합성 예측 위의 값**이며 효과 주입 0 의 귀무 구성에서 나온 "
        "타이밍·정밀도 계측용 산출이다. **확증 결과가 아니고** 어떤 가설 판정에도 쓰지 않는다."),
    "definition_adoption": (
        "**본 블록은 정의를 채택하지 않는다.** (가)/(나) 양쪽 실측을 갖춰 주는 데까지이며, "
        "어느 쪽을 `B` 로 삼을지는 **R2(SAP 1.2 재동결) 소관**이다."),
}
with open(os.path.join(HERE, "se_comparison.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
