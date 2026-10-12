#!/usr/bin/env python3
"""post_unblinding_rftuned_overlap.py — [블록 BH] RF_tuned v1 분할 ↔ v3 확증 fold 약물 겹침 실측 (지시서 `docs/122` BH-4 · 121c §2-4 · Z4).

성격: 메타데이터만 · 학습 0 · 예측 0 · 라벨 판독 0 · `_sealed/` 접근 0 · 네트워크 0 · import = 표준 라이브러리만.
입력
  data/processed/scaffold_split.json                          {cid: "train"|"valid"|"test"} (v1 분할)
  data/processed/splits/confirmatory/rep{1,2,3}_seed20{1,2,3}/folds.json   {cid: outer fold 0..4} (v3 확증)
  v1_RF/results_fairtune/best_config.yaml                     selected_by · search_budget 키만(성능 값 미판독)
산출
  experiments/runs/v3_post_unblinding/rftuned_overlap.json (공개 · 봉인 아님)

실행
  PYTHONDONTWRITEBYTECODE=1 python3 -B v3_Multimodal/src/post_unblinding_rftuned_overlap.py
"""
import sys

sys.dont_write_bytecode = True

import datetime                                                     # noqa: E402
import hashlib                                                      # noqa: E402
import json                                                         # noqa: E402
import os                                                           # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
V1_SPLIT = "data/processed/scaffold_split.json"
FAIRTUNE_YAML = "v1_RF/results_fairtune/best_config.yaml"
REPS = [("rep1", 201), ("rep2", 202), ("rep3", 203)]
OUT = "experiments/runs/v3_post_unblinding/rftuned_overlap.json"
V1_GROUPS = ["train", "valid", "test"]
INTERPRETATION_FIXED = (
    "RF_tuned 하이퍼파라미터는 v1 valid 분할 성능으로 선택됐고, 그 과정의 학습·선택에 쓰인 약물(train+valid)이 "
    "v3 확증 test fold 에 포함된다. 영향 방향은 RF_tuned 기준선에 유리 → ⑥ Δ(M2b − RF_tuned)를 보수적으로 만든다. "
    "⑥ 판정(기각 0)에는 영향 없음."
)


def _sha256(rel):
    h = hashlib.sha256()
    with open(os.path.join(ROOT, rel), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _yaml_top_keys(rel, keys):
    """최상위 `key: value` 줄에서 지정 키만 읽는다(성능 키는 읽지 않음)."""
    out = {}
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        for line in f:
            if line[:1].isspace() or ":" not in line:
                continue
            k, v = line.split(":", 1)
            if k.strip() in keys:
                v = v.strip()
                out[k.strip()] = int(v) if v.isdigit() else v
    assert set(out) == set(keys), out
    return out


def main():
    with open(os.path.join(ROOT, V1_SPLIT)) as f:
        v1 = json.load(f)
    assert set(v1.values()) == set(V1_GROUPS)
    v1_sizes = {g: sum(1 for x in v1.values() if x == g) for g in V1_GROUPS}

    inputs = {V1_SPLIT: {"bytes": os.path.getsize(os.path.join(ROOT, V1_SPLIT)), "sha256": _sha256(V1_SPLIT)}}
    reps = {}
    for rep, seed in REPS:
        rel = f"data/processed/splits/confirmatory/{rep}_seed{seed}/folds.json"
        inputs[rel] = {"bytes": os.path.getsize(os.path.join(ROOT, rel)), "sha256": _sha256(rel)}
        with open(os.path.join(ROOT, rel)) as f:
            folds = json.load(f)
        assert set(folds) == set(v1), f"{rel}: cid 집합 != v1 분할 cid 집합"
        per_fold = {}
        for k in sorted(set(folds.values())):
            test = [c for c, fk in folds.items() if fk == k]
            cnt = {g: sum(1 for c in test if v1[c] == g) for g in V1_GROUPS}
            per_fold[str(k)] = {
                "n_test": len(test),
                "in_v1_train": cnt["train"],
                "in_v1_valid": cnt["valid"],
                "in_v1_test": cnt["test"],
                "in_v1_train_or_valid": cnt["train"] + cnt["valid"],
            }
        tot = {key: sum(v[key] for v in per_fold.values()) for key in next(iter(per_fold.values()))}
        assert tot["n_test"] == len(v1), "각 rep 에서 전 약물이 test 로 정확히 1회가 아님"
        assert {key: tot[f"in_v1_{g}"] for key, g in zip(V1_GROUPS, V1_GROUPS)} == v1_sizes
        reps[f"{rep}_seed{seed}"] = {"fold_key_structure": "{cid(str): outer_fold(int 0..4)}",
                                     "per_fold": per_fold, "total": tot}

    sel = _yaml_top_keys(FAIRTUNE_YAML, ["selected_by", "search_budget"])
    result = {
        "block": "BH (docs/122 BH-4)",
        "generated_kst": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime(
            "%Y-%m-%d %H:%M:%S KST"),
        "nature": "metadata only — training 0 · prediction 0 · label read 0 · _sealed access 0",
        "inputs": inputs,
        "v1_split": {"key": "cid", "n_drugs": len(v1), "group_sizes": v1_sizes},
        "v3_confirmatory": reps,
        "fairtune_selection": {
            "selected_by": sel["selected_by"],
            "search_budget": sel["search_budget"],
            "best_config_path": FAIRTUNE_YAML,
            "best_config_sha256": _sha256(FAIRTUNE_YAML),
        },
        "interpretation_fixed": INTERPRETATION_FIXED,
    }
    os.makedirs(os.path.join(ROOT, os.path.dirname(OUT)), exist_ok=True)
    tmp = os.path.join(ROOT, OUT + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, os.path.join(ROOT, OUT))
    print(json.dumps({"out": OUT, "v1": v1_sizes,
                      "totals": {r: v["total"] for r, v in reps.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
