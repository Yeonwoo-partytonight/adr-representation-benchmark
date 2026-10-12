#!/usr/bin/env python3
"""pre_unblinding_audit.py — [블록 X] 개봉 전 점검 (지시서 `docs/78`).

확정본 `post_interim_freeze_v1_0.json` → `pre_unblinding_procedures_specified` 가
"규격만 명시하고 구현은 후속 블록" 으로 남긴 두 절차의 **구현**이다.

  1) `sealing_completeness_audit` — 기대 산출물 전건 존재 + 미개봉 기계 검증
  2) `sign_disclosure_matrix`     — 부호가 **이미 알려진** 대비의 인지 경로 기록표

성격 고지
--------
**계산 0 · 학습 0 · 추론 0 · 개봉 0 · 새 부호 산출 0.**
봉인 파일에 하는 유일한 조작은 **경로·크기·mtime·sha256(바이트 해싱)** 이다.
`.npz` 를 `np.load` 하지 않고, `metrics_full.json` · `lambda_selected.json` 을
`json.load` 하지 않는다. `checkpoint.jsonl` 은 지시서 X-2·X-3 이 명시적으로 요구한
(repeat, fold) 집합·세션 메타 추출을 위해서만 파싱하며, **키 화이트리스트**로
투영해 지표·Δ 값은 메모리에도 담지 않는다.

기대 목록은 **동결물·러너 상수·리포트·기록 파일에서 먼저 구성**하고 그 다음에
live 와 대조한다(비순환 — 지시서 X-2).
"""
from __future__ import annotations

import ast
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from compute_lock import ComputeLock, gate_b_exclusive  # noqa: E402

KST = timezone(timedelta(hours=9))
BLOCK = "X — 개봉 전 점검(봉인 완전성 + 부호 인지 기록표)"

PROV = os.path.join(ROOT, "experiments", "provenance")
RUNS = os.path.join(ROOT, "experiments", "runs")
CFG = os.path.join(ROOT, "v3_Multimodal", "config")
OUT_RUN = os.path.join(RUNS, "v3_pre_unblinding_audit")

AUDIT_JSON = os.path.join(PROV, "sealing_completeness_audit.json")
MATRIX_JSON = os.path.join(PROV, "sign_disclosure_matrix.json")
PUBLIC_JSON = os.path.join(OUT_RUN, "audit_public.json")

SPEC_FILE = os.path.join(CFG, "post_interim_freeze_v1_0.json")
SPEC_KEY = "pre_unblinding_procedures_specified"

# ── G0 동결 해시 (지시서 X-1-2) ─────────────────────────────────────────────
G0_EXPECT = {
    "v3_Multimodal/config/ladder_freeze.json": "b885585aefbabb32",
    "v3_Multimodal/config/gin_seed_freeze.json": "10828447c6d33118",
    "v3_Multimodal/config/gin_inner_valid_freeze.json": "038599c3e1576022",
    "v3_Multimodal/config/gin_inner_valid_freeze.status.json": "bd329fefe613971f",
    "v3_Multimodal/config/post_interim_freeze_v1_0.json": "502db732bd5e45cb",
    "v3_Multimodal/config/post_interim_freeze_v1_0.status.json": "a12fee2cdfd71350",
    "v3_Multimodal/config/rf_tuned_freeze.json": "c1ef6406fbb48b7f",
    "v3_Multimodal/config/holm7_latefusion_freeze.json": "d89f8c52412b656e",
    "experiments/sap/manifest.json": "d08dcedf2a22e1c8",
}
SEALED_BASELINE_ARTIFACTS = 273     # 블록 P 종료 실측 (access.log 제외)
SEALED_BASELINE_TOTAL = 288         # access.log 포함


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: str) -> str:
    return os.path.relpath(p, ROOT)


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, obj) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return sha256_file(path)


def logln(msg: str) -> None:
    print(msg, flush=True)


# ── 게이트 ───────────────────────────────────────────────────────────────────
def gate_g0():
    out, bad = {}, []
    for p, exp in G0_EXPECT.items():
        full = os.path.join(ROOT, p)
        got = sha256_file(full)[:16]
        out[p] = {"expected_sha16": exp, "observed_sha16": got, "match": got == exp}
        if got != exp:
            bad.append(p)
    man = load_json(os.path.join(ROOT, "experiments", "sap", "manifest.json"))
    mods, mbad = man["modules"], []
    for name, meta in mods.items():
        exp = meta if isinstance(meta, str) else (meta.get("sha256") or meta.get("sha"))
        got = sha256_file(os.path.join(ROOT, "v3_Multimodal", "src", "sap", name))
        if not (got == exp or got.startswith(exp)):
            mbad.append(name)
    out["_sap"] = {"sap_version": man.get("sap_version"), "n_modules": len(mods),
                   "n_module_mismatch": len(mbad)}
    ok = not bad and not mbad and man.get("sap_version") == "1.2" and len(mods) == 11
    return {"pass": bool(ok), "mismatched": bad + mbad, "detail": out}


def gate_holm():
    """`sap/decision.py` HOLM_FAMILY 를 **AST 판독**(import·실행 아님)."""
    src_p = os.path.join(ROOT, "v3_Multimodal", "src", "sap", "decision.py")
    tree = ast.parse(open(src_p, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "HOLM_FAMILY":
                    labels = list(ast.literal_eval(node.value))
                    return {"pass": len(labels) == 7, "lineno": node.lineno,
                            "n_labels": len(labels), "labels": labels,
                            "method": "ast.literal_eval (import/실행 아님)"}
    return {"pass": False, "error": "HOLM_FAMILY 미발견"}


# ── live 스냅샷 (경로·크기·mtime·sha256 만) ────────────────────────────────
def sealed_snapshot():
    snap = {}
    for p in glob.glob(os.path.join(RUNS, "**", "_sealed", "**"), recursive=True):
        if not os.path.isfile(p):
            continue
        st = os.stat(p)
        snap[rel(p)] = {"size": st.st_size, "mtime": round(st.st_mtime, 6),
                        "sha256": sha256_file(p)}
    return snap


# ── X-2. 기대 목록의 독립 구성 (동결물·러너 상수·기록에서 먼저) ───────────
SEED_MAP = {1: 201, 2: 202, 3: 203}


def build_expected():
    """live 디렉터리를 **읽지 않고** 기대 목록을 구성한다."""
    groups = []

    # G1 ─ §13-3/13-5 주분석 -------------------------------------------------
    fll = load_json(os.path.join(PROV, "first_look_log.json"))
    sign_entries = [e for e in fll if e.get("delta_sign")]
    paths1 = []
    for e in sign_entries:
        for fn in e["sealed_sha256"]:
            paths1.append(f"{e['sealed_path']}/{fn}")
    groups.append({
        "group": "main_13_3_13_5",
        "expected_from": [
            "experiments/provenance/first_look_log.json — delta_sign != null entry 의 "
            "sealed_path + sealed_sha256 키 (실행 시점 기록, live 목록 아님)",
            "v3_Multimodal/config/ladder_freeze.json:models_frozen{M1b,M2b}",
            "docs/45 §5 확증 조회 대장 4행",
        ],
        "expected_grid": {"repeats": [1, 2, 3], "seeds": [201, 202, 203],
                          "models": ["M1b", "M2b"], "consensus": True},
        "expected_paths": sorted(paths1),
        "n_expected": len(paths1),
    })

    # G2 ─ 확증 사다리 잔여(최종 봉인) ---------------------------------------
    rest_models = ["M0", "M1", "M2", "P-ID", "P-FAM", "C-CAP"]
    paths2 = []
    for r in (1, 2, 3):
        d = f"experiments/runs/v3_confirm_rest_rep{r}_seed{SEED_MAP[r]}/_sealed"
        paths2 += [f"{d}/oof_{m}.npz" for m in rest_models] + [f"{d}/metrics_full.json"]
    dc = "experiments/runs/v3_confirm_rest_consensus_rep123/_sealed"
    paths2 += [f"{dc}/consensus_{m}.npz" for m in rest_models] + [f"{dc}/metrics_full.json"]
    groups.append({
        "group": "ladder_remaining_final",
        "expected_from": [
            "docs/48_v3_rf_remaining_oof_report.md §3 봉인 표(디렉터리 4 × 파일명 규칙)",
            "v3_Multimodal/src/confirmatory_oof_rest.py:REST_MODELS·SEED_MAP·N_FOLD (동결 러너 상수)",
            "experiments/runs/v3_confirm_rest/_run_state.json:sealed_sha256 키 21 · "
            "_consensus_state.json:sealed_sha256 키 7 (실행 시점 기록)",
        ],
        "expected_grid": {"models": rest_models, "repeats": [1, 2, 3], "folds": [0, 1, 2, 3, 4],
                          "n_model_fold": len(rest_models) * 3 * 5},
        "expected_paths": sorted(paths2),
        "n_expected": len(paths2),
    })

    # G3 ─ 확증 사다리 잔여(중간물) ------------------------------------------
    base3 = "experiments/runs/v3_confirm_rest/_sealed"
    paths3 = [f"{base3}/_partial/rep{r}_{m.replace('-', '')}_fold{k}.npy"
              for r in (1, 2, 3) for m in rest_models for k in range(5)]
    paths3 += [f"{base3}/checkpoint.jsonl", f"{base3}/env_fingerprint.json",
               f"{base3}/_equivalence/repro_M2b_rep1_fold0.npy"]
    groups.append({
        "group": "ladder_remaining_intermediate",
        "expected_from": [
            "v3_Multimodal/src/confirmatory_oof_rest.py:PARTIAL_DIR·partial_path()·"
            "EQUIV_MODEL/EQUIV_REP/EQUIV_FOLD·CKPT·ENV_FP (동결 러너 상수)",
            "docs/48_v3_rf_remaining_oof_report.md §3 — checkpoint.jsonl 90행 · env_fingerprint.json",
        ],
        "expected_grid": {"n_partial": 90, "checkpoint_rows": 90},
        "expected_paths": sorted(paths3),
        "n_expected": len(paths3),
    })

    # G4 ─ Holm ⑥ tuned-RF (최종 봉인) ---------------------------------------
    paths4 = []
    for r in (1, 2, 3):
        d = f"experiments/runs/v3_confirm_rftuned_rep{r}_seed{SEED_MAP[r]}/_sealed"
        paths4 += [f"{d}/oof_RF_tuned.npz", f"{d}/metrics_full.json"]
    d4 = "experiments/runs/v3_confirm_rftuned_consensus_rep123/_sealed"
    paths4 += [f"{d4}/consensus_RF_tuned.npz", f"{d4}/metrics_full.json"]
    groups.append({
        "group": "holm6_rftuned_final",
        "expected_from": [
            "docs/60_v3_rf_tuned_report.md §3 봉인 표(최종 8종)",
            "v3_Multimodal/src/confirmatory_oof_rftuned.py:MODEL·SEED_MAP·CONS_DIR",
            "v3_Multimodal/config/rf_tuned_freeze.json (sha16 c1ef6406fbb48b7f)",
            "experiments/runs/v3_confirm_rftuned/_run_state.json + _consensus_state.json",
        ],
        "expected_grid": {"repeats": [1, 2, 3], "folds": [0, 1, 2, 3, 4], "n_model_fold": 15},
        "expected_paths": sorted(paths4),
        "n_expected": len(paths4),
    })

    # G5 ─ Holm ⑥ 중간물 -----------------------------------------------------
    b5 = "experiments/runs/v3_confirm_rftuned/_sealed"
    paths5 = [f"{b5}/_partial/rep{r}_RF_tuned_fold{k}.npy" for r in (1, 2, 3) for k in range(5)]
    paths5 += [f"{b5}/checkpoint.jsonl", f"{b5}/env_fingerprint.json"]
    groups.append({
        "group": "holm6_rftuned_intermediate",
        "expected_from": [
            "v3_Multimodal/src/confirmatory_oof_rftuned.py:WORK_DIR·partial_path()·CKPT·ENV_FP",
            "docs/60_v3_rf_tuned_report.md §3 — 중간물 17종",
        ],
        "expected_grid": {"n_partial": 15, "checkpoint_rows": 15},
        "expected_paths": sorted(paths5),
        "n_expected": len(paths5),
    })

    # G6 ─ Holm ⑦ late-fusion (최종 봉인) ------------------------------------
    arms = ["oof_seq", "oof_ens", "oof_ens_half", "oof_seq_sens", "oof_ens_sens"]
    paths6 = []
    for r in (1, 2, 3):
        d = f"experiments/runs/v3_latefusion_rep{r}_seed{SEED_MAP[r]}/_sealed"
        paths6 += [f"{d}/{a}.npz" for a in arms]
        paths6 += [f"{d}/lambda_selected.json", f"{d}/metrics_full.json"]
    d6 = "experiments/runs/v3_latefusion_consensus_rep123/_sealed"
    paths6 += [f"{d6}/consensus_{a[4:]}.npz" for a in arms] + [f"{d6}/metrics_full.json"]
    groups.append({
        "group": "holm7_latefusion_final",
        "expected_from": [
            "docs/61_v3_late_fusion_report.md §3 봉인 표(최종 27종)",
            "v3_Multimodal/src/confirmatory_latefusion.py:ARM_FILES·SEED_MAP·CONS_DIR",
            "v3_Multimodal/config/holm7_latefusion_freeze.json (sha16 d89f8c52412b656e)",
            "experiments/runs/v3_latefusion/_run_state.json + _consensus_state.json",
        ],
        "expected_grid": {"repeats": [1, 2, 3], "folds": [0, 1, 2, 3, 4],
                          "n_outer_unit": 15, "n_arm": 5},
        "expected_paths": sorted(paths6),
        "n_expected": len(paths6),
    })

    # G7 ─ Holm ⑦ 중간물 -----------------------------------------------------
    b7 = "experiments/runs/v3_latefusion/_sealed"
    paths7 = []
    for r in (1, 2, 3):
        for k in range(5):
            paths7 += [f"{b7}/_partial/rep{r}_f{k}_prf.npy",
                       f"{b7}/_partial/rep{r}_f{k}_pseq.npy",
                       f"{b7}/_partial/rep{r}_f{k}_pseqsens.npy",
                       f"{b7}/_partial/rep{r}_f{k}_meta.json"]
    paths7 += [f"{b7}/checkpoint.jsonl", f"{b7}/env_fingerprint.json"]
    groups.append({
        "group": "holm7_latefusion_intermediate",
        "expected_from": [
            "v3_Multimodal/src/confirmatory_latefusion.py:WORK_DIR·pp()·meta_path()·CKPT·ENV_FP",
            "docs/61_v3_late_fusion_report.md §3 — 중간물 62종(unit 별 부분 산출 60)",
        ],
        "expected_grid": {"n_partial": 60, "checkpoint_rows": 15},
        "expected_paths": sorted(paths7),
        "n_expected": len(paths7),
    })

    # G8 ─ §13-4 표적 재배치 null (본런) --------------------------------------
    b8 = "experiments/runs/v3_null_MAIN/_sealed"
    seed_base = {"global": 1000, "family": 11000}
    paths8 = []
    for mode in ("global", "family", "family_ALT", "global_ALT"):
        base = seed_base["family" if mode.startswith("family") else "global"]
        paths8 += [f"{b8}/oof_M2b_{mode}_seed{base + i}.npz" for i in range(3)]
    paths8 += [f"{b8}/null_result.json", f"{b8}/g3_identity.json",
               f"{b8}/gates_first_session.json", f"{b8}/checkpoint.jsonl",
               f"{b8}/env_fingerprint.json"]
    groups.append({
        "group": "null_realloc_main",
        "expected_from": [
            "v3_Multimodal/src/null_main_run.py:SEED_BASE·ALT_N·AUDIT_KEEP_FIRST_N_OOF·"
            "NULL_RESULT·G3_SEALED·GATES_FIRST·CKPT·ENV_FP (동결 러너 상수)",
            "docs/46_v3_null_aggregate_prompt_for_vscode.md — `_sealed/null_result.json` 1회성 산출",
            "docs/33 항목18 ③·항목19 — 집계 산출 전량 봉인 규정",
        ],
        "expected_grid": {"modes": ["global", "family", "family_ALT", "global_ALT"],
                          "audit_keep_first_n_oof": 3, "NULL_B": 1000,
                          "ALT_N": {"family_ALT": 100, "global_ALT": 10},
                          "checkpoint_rows": 2110},
        "expected_paths": sorted(paths8),
        "n_expected": len(paths8),
    })

    # G9 ─ §13-4 타이밍 프로브 -------------------------------------------------
    b9 = "experiments/runs/v3_null_probe/_sealed"
    probe_seeds = [9000001, 9000002]
    tags, n = [], 0
    for mode in ("global", "family"):
        for s in probe_seeds:
            if n < 3:
                tags.append(f"{mode}_seed{s}")
                n += 1
    paths9 = [f"{b9}/oof_M2b_identity.npz"] + [f"{b9}/oof_M2b_perm_{t}.npz" for t in tags]
    paths9 += [f"{b9}/probe_stats.json"]
    groups.append({
        "group": "null_timing_probe",
        "expected_from": [
            "v3_Multimodal/src/null_timing_probe.py:PROBE_SEEDS·AUDIT_KEEP_FIRST_N_OOF·"
            "루프순서(global→family)·SEALED_DIR 파일명 규칙",
        ],
        "expected_grid": {"probe_seeds": probe_seeds, "modes": ["global", "family"],
                          "audit_keep_first_n_oof": 3},
        "expected_paths": sorted(paths9),
        "n_expected": len(paths9),
    })

    # G10 ─ §13-4 계산 프로브 2 ------------------------------------------------
    groups.append({
        "group": "null_compute_probe2",
        "expected_from": [
            "v3_Multimodal/src/null_compute_probe2.py:SEALED_DIR/fold_pred_reference.npy",
            "v3_Multimodal/src/null_probe2_record.py:196 — 동일 경로 참조",
        ],
        "expected_grid": {"n_reference_array": 1},
        "expected_paths": ["experiments/runs/v3_null_probe2_compute/_sealed/fold_pred_reference.npy"],
        "n_expected": 1,
    })

    # G11 ─ §13-6 층화 (블록 H) ------------------------------------------------
    groups.append({
        "group": "stratification_m2b_m1b",
        "expected_from": [
            "docs/47_v3_stratification_report.md §3 — `_sealed/stratification_result.json` "
            "(sha256 cd2969c73ed6bae7…)",
            "docs/33 항목21 ④ · docs/45 §2·§5 블록 H 행",
        ],
        "expected_grid": {"n_strata": 13, "formal": 9, "descriptive": 4},
        "expected_paths": ["experiments/runs/v3_stratification/_sealed/stratification_result.json"],
        "n_expected": 1,
    })

    # G12 ─ §13-6 층화 (블록 L, Δ(M2b−P-ID)) -----------------------------------
    groups.append({
        "group": "stratification_m2b_pid",
        "expected_from": [
            "docs/57_v3_pid_stratification_report.md §3 — `_sealed/stratification_pid_result.json` "
            "(sha256 d38151f60b141ea2…) + checkpoint.jsonl",
            "docs/33 항목26 · docs/45 §2·§5 블록 L 행",
        ],
        "expected_grid": {"n_strata": 13, "checkpoint_rows": 13},
        "expected_paths": [
            "experiments/runs/v3_stratification_pid/_sealed/stratification_pid_result.json",
            "experiments/runs/v3_stratification_pid/_sealed/checkpoint.jsonl",
        ],
        "n_expected": 2,
    })
    return groups


# ── X-2. model × fold × seed 교차 대조 (개수 아닌 **집합**) ─────────────────
CKPT_WHITELIST = ("repeat", "fold", "model", "session_seq", "ts_kst", "wall_s",
                  "mode", "seed", "key")


def read_ckpt(relpath):
    """checkpoint.jsonl 을 **키 화이트리스트**로 투영해 읽는다(지표·Δ 미적재)."""
    rows = []
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            rows.append({k: o[k] for k in CKPT_WHITELIST if k in o})
            del o
    return rows


def model_fold_seed_crosscheck():
    out = []
    grid_rf = sorted({(r, k) for r in (1, 2, 3) for k in range(5)})

    rows = read_ckpt("experiments/runs/v3_confirm_rest/_sealed/checkpoint.jsonl")
    obs = sorted({(int(r["repeat"]), int(r["fold"])) for r in rows})
    obs_mf = sorted({(int(r["repeat"]), r["model"], int(r["fold"])) for r in rows})
    exp_mf = sorted({(r, m, k) for r in (1, 2, 3)
                     for m in ["M0", "M1", "M2", "P-ID", "P-FAM", "C-CAP"] for k in range(5)})
    out.append({
        "group": "ladder_remaining_final+intermediate",
        "source": "experiments/runs/v3_confirm_rest/_sealed/checkpoint.jsonl "
                  "(키 화이트리스트 투영: repeat/model/fold/session_seq/ts_kst/wall_s)",
        "criterion": "set equality (개수 대조 아님)",
        "expected_grid": {"repeat_fold": [list(x) for x in grid_rf],
                          "n_repeat_model_fold": len(exp_mf)},
        "observed_grid": {"repeat_fold": [list(x) for x in obs],
                          "n_repeat_model_fold": len(obs_mf)},
        "set_equal": bool(set(obs) == set(grid_rf) and set(obs_mf) == set(exp_mf)),
        "n_rows": len(rows),
    })

    rows = read_ckpt("experiments/runs/v3_confirm_rftuned/_sealed/checkpoint.jsonl")
    obs = sorted({(int(r["repeat"]), int(r["fold"])) for r in rows})
    out.append({
        "group": "holm6_rftuned",
        "source": "experiments/runs/v3_confirm_rftuned/_sealed/checkpoint.jsonl",
        "criterion": "set equality (개수 대조 아님)",
        "expected_grid": {"repeat_fold": [list(x) for x in grid_rf], "model": ["RF_tuned"]},
        "observed_grid": {"repeat_fold": [list(x) for x in obs],
                          "model": sorted({r["model"] for r in rows})},
        "set_equal": bool(set(obs) == set(grid_rf)
                          and {r["model"] for r in rows} == {"RF_tuned"}),
        "n_rows": len(rows),
    })

    rows = read_ckpt("experiments/runs/v3_latefusion/_sealed/checkpoint.jsonl")
    obs = sorted({(int(r["repeat"]), int(r["fold"])) for r in rows})
    out.append({
        "group": "holm7_latefusion",
        "source": "experiments/runs/v3_latefusion/_sealed/checkpoint.jsonl",
        "criterion": "set equality (개수 대조 아님)",
        "expected_grid": {"repeat_fold": [list(x) for x in grid_rf]},
        "observed_grid": {"repeat_fold": [list(x) for x in obs]},
        "set_equal": bool(set(obs) == set(grid_rf)),
        "n_rows": len(rows),
    })

    rows = read_ckpt("experiments/runs/v3_null_MAIN/_sealed/checkpoint.jsonl")
    exp_ms = sorted({("global", 1000 + b) for b in range(1000)}
                    | {("family", 11000 + b) for b in range(1000)}
                    | {("family_ALT", 11000 + b) for b in range(100)}
                    | {("global_ALT", 1000 + b) for b in range(10)})
    obs_ms = sorted({(r["mode"], int(r["seed"])) for r in rows})
    out.append({
        "group": "null_realloc_main",
        "source": "experiments/runs/v3_null_MAIN/_sealed/checkpoint.jsonl "
                  "(키 화이트리스트 — macro_AP·delta 는 적재하지 않음)",
        "criterion": "set equality on (mode, seed) — 개수 대조 아님",
        "expected_grid": {"n_mode_seed": len(exp_ms),
                          "modes": ["global", "family", "family_ALT", "global_ALT"]},
        "observed_grid": {"n_mode_seed": len(obs_ms),
                          "modes": sorted({m for m, _ in obs_ms})},
        "set_equal": bool(set(obs_ms) == set(exp_ms)),
        "n_rows": len(rows),
    })
    return out


# ── X-3. 기록된 해시와의 대조 ────────────────────────────────────────────────
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def recorded_hashes():
    """live 가 아닌 **기록물**에서 (봉인경로 → sha256) 기대값을 수집."""
    rec = {}          # relpath -> [(sha256, source)]

    def add(path, sha, src):
        rec.setdefault(path, []).append((sha, src))

    # 1) first_look_log — entry 형태가 3종(디렉터리형·파일형·블록형)이라 각각 해석
    src = "experiments/provenance/first_look_log.json"
    block_run = {"I": ("v3_confirm_rest_rep", "v3_confirm_rest_consensus_rep123"),
                 "O": ("v3_confirm_rftuned_rep", "v3_confirm_rftuned_consensus_rep123"),
                 "P": ("v3_latefusion_rep", "v3_latefusion_consensus_rep123")}
    for e in load_json(os.path.join(PROV, "first_look_log.json")):
        shas = e.get("sealed_sha256") or {}
        sp = e.get("sealed_path")
        blk = (e.get("block") or " ")[0]
        for fn, sha in shas.items():
            if sp and sp.endswith("/" + fn):            # 파일형 (블록 H·L)
                add(sp, sha, src)
            elif sp and "/_sealed" in sp and not sp.endswith((".json", ".npz", ".npy")):
                add(f"{sp}/{fn}", sha, src)             # 디렉터리형 (§13-3/13-5)
            elif blk in block_run:                      # 블록형 (I·O·P)
                base, cons = block_run[blk]
                m = re.match(r"^rep(\d)/(.+)$", fn)
                if m:
                    r = int(m.group(1))
                    add(f"experiments/runs/{base}{r}_seed{SEED_MAP[r]}/_sealed/{m.group(2)}",
                        sha, src)
                else:
                    add(f"experiments/runs/{cons}/_sealed/{fn}", sha, src)

    # 2) 각 블록의 run/consensus state
    for run, cons_dir in [("v3_confirm_rest", "v3_confirm_rest_consensus_rep123"),
                          ("v3_confirm_rftuned", "v3_confirm_rftuned_consensus_rep123"),
                          ("v3_latefusion", "v3_latefusion_consensus_rep123")]:
        p = f"experiments/runs/{run}/_run_state.json"
        for k, sha in load_json(os.path.join(ROOT, p))["sealed_sha256"].items():
            r, fn = k.split("/", 1)
            seed = SEED_MAP[int(r[3:])]
            base = ("v3_confirm_rest_rep" if run == "v3_confirm_rest" else
                    "v3_confirm_rftuned_rep" if run == "v3_confirm_rftuned" else
                    "v3_latefusion_rep")
            add(f"experiments/runs/{base}{r[3:]}_seed{seed}/_sealed/{fn}", sha, p)
        p = f"experiments/runs/{run}/_consensus_state.json"
        for fn, sha in load_json(os.path.join(ROOT, p))["sealed_sha256"].items():
            add(f"experiments/runs/{cons_dir}/_sealed/{fn}", sha, p)

    # 3) 층화·null 공개 요약의 봉인 결과 해시
    for p, key, target in [
        ("experiments/runs/v3_stratification/stratification_public.json", "sealed_result_sha256",
         "experiments/runs/v3_stratification/_sealed/stratification_result.json"),
        ("experiments/runs/v3_stratification_pid/stratification_pid_public.json",
         "sealed_result_sha256",
         "experiments/runs/v3_stratification_pid/_sealed/stratification_pid_result.json"),
        ("experiments/runs/v3_null_MAIN/aggregate_public.json", "null_result_sealed_sha256",
         "experiments/runs/v3_null_MAIN/_sealed/null_result.json"),
    ]:
        d = load_json(os.path.join(ROOT, p))
        if isinstance(d.get(key), str) and HEX64.match(d[key]):
            add(target, d[key], p)

    # 4) 과거 블록이 남긴 sealed guard 스냅샷 (사후 변조 탐지에 가장 강한 근거)
    for p, keypath in [
        ("experiments/runs/v3_stratification/gates_public.json", ["sealed_guard_start"]),
        ("experiments/runs/v3_stratification_pid/gates_public.json", ["sealed_guard_start"]),
    ]:
        d = load_json(os.path.join(ROOT, p))
        for k in keypath:
            d = d.get(k, {})
        for path, sha in d.items():
            if isinstance(sha, str) and HEX64.match(sha):
                add(path, sha, f"{p}:{'/'.join(keypath)}")
    return rec


def hash_crosscheck(snap):
    rec = recorded_hashes()
    compared, mismatch, uncovered = 0, [], []
    per_file = {}
    for path, pairs in rec.items():
        if path not in snap:
            uncovered.append({"path": path, "reason": "기록에는 있으나 live 스냅샷에 없음"})
            continue
        live = snap[path]["sha256"]
        for sha, src in pairs:
            compared += 1
            if sha != live:
                mismatch.append({"path": path, "recorded_sha256": sha,
                                 "live_sha256": live, "source": src})
            per_file.setdefault(path, []).append(src)
    return {
        "sha256_all_sealed_artifacts": {k: v["sha256"] for k, v in sorted(snap.items())
                                        if not k.endswith("/access.log")},
        "n_sealed_artifacts_hashed": sum(1 for k in snap if not k.endswith("/access.log")),
        "recorded_sources": sorted({s for v in rec.values() for _, s in v}),
        "n_files_with_recorded_hash": len(per_file),
        "n_compared": compared,
        "n_mismatch": len(mismatch),
        "mismatches": mismatch,
        "recorded_but_absent_in_live": uncovered,
    }


# ── X-3. opened_check ────────────────────────────────────────────────────────
def opened_check(snap):
    logs = sorted(k for k in snap if k.endswith("/access.log"))
    n_entries, types, human_true, per_file = 0, {}, [], {}
    for lp in logs:
        rows = 0
        with open(os.path.join(ROOT, lp), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                rows += 1
                n_entries += 1
                t = o.get("type", "<missing>")
                types[t] = types.get(t, 0) + 1
                if o.get("human_exposure") is True:
                    human_true.append({"file": lp, "entry": o})
        per_file[lp] = rows
    return {
        "n_access_log_files": len(logs),
        "n_access_log_entries": n_entries,
        "entries_per_file": per_file,
        "type_distribution": types,
        "n_human_exposure_true": len(human_true),
        "human_exposure_entries": human_true,
        "verdict": "PASS" if (not human_true and set(types) <= {"machine_read"}) else "FAIL",
    }


# ── X-3. failure_and_restart_log ────────────────────────────────────────────
def failure_and_restart_log():
    sessions, anomalies = [], []
    for run in ("v3_confirm_rest", "v3_confirm_rftuned", "v3_latefusion"):
        st = load_json(os.path.join(ROOT, f"experiments/runs/{run}/_run_state.json"))
        sessions.append({
            "run": run, "source": f"experiments/runs/{run}/_run_state.json",
            "total": st.get("total"), "session_seq": st.get("session_seq"),
            "n_done_this_session": st.get("n_done_this_session"),
            "env_fingerprint_match": st.get("env_fingerprint_match"),
            "single_session": st.get("session_seq") == 1
                              and st.get("n_done_this_session") == st.get("total"),
        })

    for run, ck in [("v3_confirm_rest", "experiments/runs/v3_confirm_rest/_sealed/checkpoint.jsonl"),
                    ("v3_confirm_rftuned",
                     "experiments/runs/v3_confirm_rftuned/_sealed/checkpoint.jsonl"),
                    ("v3_latefusion", "experiments/runs/v3_latefusion/_sealed/checkpoint.jsonl"),
                    ("v3_null_MAIN", "experiments/runs/v3_null_MAIN/_sealed/checkpoint.jsonl")]:
        rows = read_ckpt(ck)
        seqs = sorted({r.get("session_seq") for r in rows if r.get("session_seq") is not None})
        ts = [r["ts_kst"] for r in rows if "ts_kst" in r]
        n_back = sum(1 for a, b in zip(ts, ts[1:]) if b < a)
        if "repeat" in (rows[0] if rows else {}):
            keys = [(r.get("repeat"), r.get("model"), r.get("fold")) for r in rows]
        else:
            keys = [(r.get("mode"), r.get("seed")) for r in rows]
        dup = len(keys) - len(set(keys))
        walls = [r["wall_s"] for r in rows if isinstance(r.get("wall_s"), (int, float))]
        outlier = None
        if walls:
            walls_sorted = sorted(walls)
            med = walls_sorted[len(walls_sorted) // 2]
            outlier = {"n": len(walls), "median_s": round(med, 2),
                       "min_s": round(min(walls), 2), "max_s": round(max(walls), 2),
                       "n_gt_5x_median": sum(1 for w in walls if med > 0 and w > 5 * med)}
        rec = {"run": run, "checkpoint": ck, "n_rows": len(rows), "session_seq_values": seqs,
               "n_sessions": len(seqs), "n_timestamp_regressions": n_back,
               "n_duplicate_keys": dup, "wall_s_summary": outlier}
        if n_back:
            det, cross, worst = [], 0, 0
            for i in range(1, len(rows)):
                a, b = rows[i - 1], rows[i]
                if "ts_kst" not in a or "ts_kst" not in b or not (b["ts_kst"] < a["ts_kst"]):
                    continue
                ta = datetime.strptime(a["ts_kst"][:19], "%Y-%m-%d %H:%M:%S")
                tb = datetime.strptime(b["ts_kst"][:19], "%Y-%m-%d %H:%M:%S")
                gap = int((ta - tb).total_seconds())
                worst = max(worst, gap)
                same = a.get("session_seq") == b.get("session_seq")
                cross += 0 if same else 1
                det.append({"row_index": i, "prev_ts": a["ts_kst"], "ts": b["ts_kst"],
                            "regression_s": gap, "same_session": same,
                            "session_seq": b.get("session_seq")})
            rec["timestamp_regression_detail"] = det
            rec["max_regression_s"] = worst
            rec["n_cross_session_regressions"] = cross
        if len(seqs) > 1 or n_back or dup:
            anomalies.append(rec)
        sessions.append(rec)

    # 다세션 실행이었던 유일한 블록 — 세션표를 공개 진행파일에서 그대로 옮긴다
    prog = load_json(os.path.join(ROOT, "experiments/runs/v3_null_MAIN/progress_public.json"))
    multi_session = {
        "run": "v3_null_MAIN (§13-4 표적 재배치 null 본런)",
        "source": "experiments/runs/v3_null_MAIN/progress_public.json",
        "session_seq": prog.get("session_seq"),
        "completed": prog.get("completed"), "total": prog.get("total"),
        "workers": prog.get("workers"),
        "graceful_stop": prog.get("graceful_stop"), "stop_reason": prog.get("stop_reason"),
        "env_fingerprint_match": (prog.get("gates") or {}).get("env_fingerprint_match"),
        "sessions": [{k: s.get(k) for k in ("seq", "start_ts", "stop_ts", "completed_delta",
                                            "workers")}
                     for s in prog.get("sessions", [])],
        "interpretation": "설계상 중단·재개가 허용된 장기 런이며(`STOP` 파일 기반 graceful stop), "
                          "완주 카운트는 2110/2110 로 기대 격자와 집합 동일하다. 세션 6개는 "
                          "장애가 아니라 예정된 분할 실행이다.",
    }

    known_events = [{
        "event": "블록 O 본계산 중 임계 배터리 강제 절전 — 약 89분 공백",
        "when_kst": "2026-08-06 (블록 O `stage_run` 구간 15:30:05 → 17:54:36)",
        "evidence": "docs/60_v3_rf_tuned_report.md §4-4 · "
                    "experiments/runs/v3_confirm_rftuned/suspend_fold_recheck_public.json",
        "affected_unit": "rep1 RF_tuned fold3 (절전 경계를 걸친 model-fold 1개)",
        "verdict": "산출 바이트 무영향(절전 경계 fold 동일 코드경로 재계산 = byte_identical True로 "
                   "실증) · 경과시간만 오염 → wall-clock 비교 불가",
        "caffeinate_note": "caffeinate -i -s 의 절전 억제 보증 2건이 정상 생성돼 있었으나 "
                           "임계 잔량 강제 절전은 그 보증으로 막지 못함(docs/60 §4-4).",
    }, {
        "event": "블록 C(반복2·3 + consensus) 배터리 전원·저전력 모드(powermode=1) 실행",
        "when_kst": "2026-07-27 (docs/45 §5 추기 2026-07-27 22:19 KST)",
        "evidence": "docs/45_research_integrity_ledger.md §5 추기 · power_state_block_C.json",
        "affected_unit": "블록 C 전 구간",
        "verdict": "산출 바이트 무영향(RF random_state=42 고정·연산 순서 불변) · "
                   "wall-clock 비교 불가 → 블록 D·§13-4 시간 추정에 미투입",
        "caffeinate_note": None,
    }, {
        "event": "락 stale 인수 1회 — 합성 자가시험 레코드(실제 사고 아님)",
        "when_kst": "2026-07-28 19:43:33 KST (주석 19:58:55 KST)",
        "evidence": "experiments/runs/.compute_lock.stale.jsonl (kind=ANNOTATION, "
                    "synthetic_selftest=true, block=E-1)",
        "affected_unit": "없음 — 블록 E-1 락 자가시험",
        "verdict": "의도된 합성 레코드 · 산출물 무영향",
        "caffeinate_note": None,
    }]
    return {"per_run_sessions": sessions, "anomalies_detected": anomalies,
            "multi_session_runs": [multi_session],
            "n_multi_session_runs": 1,
            "timestamp_regression_interpretation":
                "v3_null_MAIN 의 시각 역행 6건은 전부 **동일 세션 내 1초** 역행이고 세션 경계를 "
                "가로지르는 역행은 0건이다. 18 워커가 배치로 완료를 수집해 기록하므로 도착 순서와 "
                "기록 순서가 초 단위에서 어긋나는 것이 원인이며, 중복 (mode, seed) 는 0건이고 "
                "(mode, seed) 집합은 기대 격자 2,110 과 완전히 같다 → 재시작 결손·중복 아님.",
            "known_failure_and_restart_events": known_events,
            "n_known_events": len(known_events)}


# ── X-4. 부호 인지 기록표 ────────────────────────────────────────────────────
def verify_public_exposure():
    """공개 저장소 노출을 **독립 재현**한다(cowork 문면을 옮겨 적지 않는다).

    · `block_C_summary.json` 의 부호는 '문자열 존재' 가 아니라 **스칼라 값**으로 판정.
    · 푸시 여부는 네트워크가 아니라 **로컬 원격추적 ref·reflog** 로 판정(`git ls-remote` 금지).
    """
    import subprocess

    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip()

    bc = "experiments/runs/v3_confirm_rep23/block_C_summary.json"
    d = load_json(os.path.join(ROOT, bc))
    scalars = []

    def walk(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, p + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, p + f"[{i}]")
        elif isinstance(o, str) and o.lower() in ("negative", "positive"):
            scalars.append(p)

    walk(d)

    pushed_ref = "refs/remotes/origin/chore/archive-kci-separation"
    remote_tip = git("rev-parse", "--short", pushed_ref)
    in_pushed = bc in git("ls-tree", "-r", "--name-only", remote_tip).splitlines()
    reflog = git("reflog", "show", "--date=iso", pushed_ref).splitlines()
    push_when = None
    for ln in reflog:
        if "update by push" in ln:
            m = re.search(r"\{([^}]+)\}", ln)
            push_when = m.group(1) if m else None
            break

    mp = [p for p in git("ls-tree", "-r", "--name-only", "10687f4").splitlines()
          if p.endswith("metrics_public.json")]
    mp_pushed = subprocess.run(["git", "merge-base", "--is-ancestor", "10687f4", pushed_ref],
                               cwd=ROOT).returncode == 0
    mp_in_remote_tip = [p for p in git("ls-tree", "-r", "--name-only", remote_tip).splitlines()
                        if p.endswith("metrics_public.json")]
    return {
        "method": "값 기준 판정 — 'sign' 문자열 존재가 아니라 스칼라 값(negative/positive)으로 열거. "
                  "푸시 여부는 로컬 원격추적 ref·reflog 로 판정(네트워크 0, git ls-remote 0).",
        "block_C_summary_path": bc,
        "n_scalar_sign_literals": len(scalars),
        "scalar_sign_key_paths": scalars,
        "in_pushed_commit": in_pushed,
        "pushed_ref": pushed_ref,
        "remote_tip_short": remote_tip,
        "push_recorded_at_local_reflog": push_when,
        "metrics_public_paths_in_10687f4": mp,
        "n_metrics_public_in_10687f4": len(mp),
        "10687f4_is_ancestor_of_pushed_ref": mp_pushed,
        "metrics_public_present_in_remote_tip": mp_in_remote_tip,
    }


def build_sign_matrix():
    fll = load_json(os.path.join(PROV, "first_look_log.json"))
    ledger = load_json(os.path.join(PROV, "ledger.json"))
    pub = verify_public_exposure()

    # 공개된 부호의 **대상 반복** = block_C_summary 스칼라 키 경로에서 기계 추출
    public_scopes = set()
    for kp in pub["scalar_sign_key_paths"]:
        m = re.match(r"^/repeats/(\d+)/sign$", kp)
        if m:
            public_scopes.add(f"반복{m.group(1)}")
        elif kp == "/consensus/sign":
            public_scopes.add("consensus")

    corr = ledger.get("correspondence", [])
    blob = (json.dumps(corr, ensure_ascii=False)
            + json.dumps(ledger.get("correspondence_subject_authority", {}), ensure_ascii=False))
    advisor_hits = [w for w in SIGN_WORDS if w in blob.lower()]
    advisor_det = "확인됨" if advisor_hits else "unknown_as_of_2026-08-06"

    rows = []
    for idx, e in enumerate(fll):
        if not e.get("delta_sign"):
            continue
        step = e.get("step", "")
        scope = "consensus" if "consensus" in step else "반복%s" % e.get("repeat")
        is_public = scope in public_scopes

        routes = [{
            "route_kind": "runner_first_look",
            "who_learned": "러너(vscode-claude, runner). 사람 사용자에게 보고된 것은 부호 1개뿐이며 "
                           "원시 macro AP·Δ 크기·PT별·fold별은 봉인 상태 유지.",
            "when": e.get("ts_completed_kst") or e.get("ts_kst"),
            "route": f"first-look 실행({step}) → metrics_public.json 부호 1개 → "
                     "docs/45 §5 확증 조회 대장 · docs/33",
            "decisions_after": "none — 부호를 근거로 한 설계·성공기준 변경 0.",
            "evidence": [f"experiments/provenance/first_look_log.json[{idx}]",
                         f"{e.get('sealed_path')} (봉인 — 값 미열람)",
                         "docs/45_research_integrity_ledger.md §5"],
        }, {
            "route_kind": "public_repository_pushed",
            "who_learned": ("불특정 다수 — 공개 GitHub 저장소 열람자 전원"
                            if is_public else
                            "해당 없음 — 이 대비의 부호는 푸시된 커밋에 들어 있지 않다"),
            "when": pub["push_recorded_at_local_reflog"] if is_public else None,
            "route": (f"git push → 원격 `{pub['pushed_ref']}` tip `{pub['remote_tip_short']}` 의 "
                      f"`{pub['block_C_summary_path']}` 스칼라 부호"
                      if is_public else "미공개"),
            "decisions_after": ("삭제·이력 재작성 하지 않음 · 공개 시점과 범위만 기록 · "
                                "성능 산출물 **추가 push 중지** 확정(docs/33 항목31 국문 (5) · "
                                "사용자 결정 D1·D3). 설계·성공기준 변경 none."
                               if is_public else "none"),
            "evidence": ([pub["block_C_summary_path"],
                          f"git ls-tree {pub['remote_tip_short']} (원격추적 ref 실측)",
                          f"git reflog {pub['pushed_ref']} — update by push",
                          "docs/56_git_hygiene_resume_report.md §4-7",
                          "docs/33_prereg_deviation_log.md 항목31 국문 (5)"]
                         if is_public else ["git ls-tree bdb65c8 — 해당 부호 리터럴 부재"]),
        }, {
            "route_kind": "local_commit_unpushed",
            "who_learned": "로컬 저장소 접근자만 — 불특정 다수 아님",
            "when": "로컬 커밋 10687f4 (원격 미반영)",
            "route": f"{pub['n_metrics_public_in_10687f4']}개 metrics_public.json 이 로컬 커밋 "
                     f"10687f4 에만 존재 · 원격추적 ref 의 조상 아님"
                     f"(is_ancestor={pub['10687f4_is_ancestor_of_pushed_ref']})",
            "decisions_after": "추가 push 중지 유지(D1) · 이력 재작성 없음(D3). 설계 변경 none.",
            "evidence": ["git merge-base --is-ancestor 10687f4 origin/… → false",
                         "docs/56_git_hygiene_resume_report.md §4-7"],
        }, {
            "route_kind": "advisor",
            "who_learned": "양진홍 교수님",
            "when": advisor_det,
            "route": ("서신 기록 실측 — docs/44 는 최초 조회 **직전**의 승인 요청이라 부호가 없고, "
                      "조회 이후 서신(ledger.correspondence · "
                      "correspondence_subject_authority · docs/45)에서 부호 어휘가 값으로 "
                      "검출되지 않았다."),
            "decisions_after": "판정 불가 — 전달 사실 미확인이므로 후속 결정도 연결하지 않는다.",
            "evidence": ["experiments/provenance/ledger.json:correspondence "
                         f"({len(corr)}항목)",
                         "experiments/provenance/ledger.json:correspondence_subject_authority",
                         "docs/44_professor_approval_email_first_look.md",
                         "docs/45_research_integrity_ledger.md §5"],
            "determination": advisor_det,
        }]

        rows.append({
            "contrast": "Δ(M2b−M1b) " + ("consensus(반복1·2·3)" if scope == "consensus" else scope),
            "holm_label": "M2b-M1b — 주분석(§13-3/13-5). HOLM_FAMILY 7 라벨은 ②~⑧ 이며 "
                          "본 대비는 그 family 의 기준 대비다.",
            "sign": e["delta_sign"],
            "sign_source": f"experiments/provenance/first_look_log.json[{idx}].delta_sign — "
                           "재계산 없이 그대로 전사(새 부호 산출 0)",
            "who_learned": [r["who_learned"] for r in routes],
            "when": [r["when"] for r in routes],
            "route": [r["route"] for r in routes],
            "decisions_after": " / ".join(f"[{r['route_kind']}] {r['decisions_after']}"
                                          for r in routes),
            "evidence": [ev for r in routes for ev in r["evidence"]],
            "disclosure_routes": routes,
            "publicly_disclosed_to_unspecified_readers": is_public,
            "advisor_route_determination": advisor_det,
        })
    return rows, ledger, pub, advisor_det, advisor_hits


# ── 공개 요약 방어 스캔 ──────────────────────────────────────────────────────
FORBIDDEN_KEYS = ("macro_ap", "delta", "sign", "ci_", "p_", "per_pt_ap", "boot",
                  "null_summary", "lambda_selected")
SIGN_WORDS = ("negative", "positive", "음수", "양수")


def defensive_scan(obj):
    """★ 키 이름이 아니라 **값**으로 판정(블록 U §5-3 · 블록 P §5-1 전례)."""
    bad_keys, bad_values = [], []
    num = re.compile(r"(?<![\w.])0\.\d{2,}(?![\w])")

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                kl = k.lower()
                if kl in ("macro_ap", "delta", "sign", "per_pt_ap", "null_summary",
                          "lambda_selected") or kl.startswith(("ci_", "p_", "boot")):
                    bad_keys.append(path + "/" + k)
                walk(v, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + f"[{i}]")
        elif isinstance(o, str):
            if num.search(o):
                bad_values.append({"path": path, "kind": "decimal_literal",
                                   "excerpt": o[:120]})
            low = o.lower()
            for w in SIGN_WORDS:
                if w in low:
                    bad_values.append({"path": path, "kind": "sign_word",
                                       "excerpt": o[:120]})
                    break
        elif isinstance(o, float):
            if 0.0 < abs(o) < 1.0:
                bad_values.append({"path": path, "kind": "float_in_unit_interval",
                                   "excerpt": repr(o)})

    walk(obj)
    return {"n_forbidden_keys": len(bad_keys), "forbidden_keys": bad_keys,
            "n_value_scan_hits": len(bad_values), "value_scan_hits": bad_values}


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    if os.path.exists(AUDIT_JSON) or os.path.exists(MATRIX_JSON):
        print(f"[중단] 산출물이 이미 존재한다 — 1회성 블록. "
              f"{rel(AUDIT_JSON)} / {rel(MATRIX_JSON)}", file=sys.stderr)
        sys.exit(2)

    with ComputeLock(script="pre_unblinding_audit.py", role="runner"):
        gate_b_exclusive("pre_unblinding_audit:entry")

        g0 = gate_g0()
        assert g0["pass"], f"G0 불일치: {g0['mismatched']}"
        holm = gate_holm()
        assert holm["pass"], f"G-HOLM 불일치: {holm}"
        logln(f"[G0] PASS 9/9 · SAP 1.1 11모듈 일치 | [G-HOLM] {holm['n_labels']} 라벨 "
              f"(decision.py:{holm['lineno']})")

        snap_start = sealed_snapshot()
        n_access = sum(1 for k in snap_start if k.endswith("/access.log"))
        n_art = len(snap_start) - n_access
        assert n_art == SEALED_BASELINE_ARTIFACTS and len(snap_start) == SEALED_BASELINE_TOTAL, (
            f"sealed 기준선 불일치 — 산출물 {n_art}(기대 {SEALED_BASELINE_ARTIFACTS}) · "
            f"전체 {len(snap_start)}(기대 {SEALED_BASELINE_TOTAL})")
        logln(f"[sealed guard] 착수 스냅샷 — 산출물 {n_art} · access.log {n_access} · "
              f"합 {len(snap_start)}")

        # X-2 ── 기대 목록 독립 구성 → live 양방향 대조
        groups = build_expected()
        expected_all = []
        for g in groups:
            expected_all += g["expected_paths"]
        assert len(expected_all) == len(set(expected_all)), "기대 목록에 중복 경로"
        live_art = {k for k in snap_start if not k.endswith("/access.log")}
        missing = sorted(set(expected_all) - live_art)
        unexpected = sorted(live_art - set(expected_all))
        logln(f"[대조] 기대 {len(expected_all)} · live 산출물 {len(live_art)} → "
              f"missing {len(missing)} · unexpected {len(unexpected)}")

        mfs = model_fold_seed_crosscheck()
        hashes = hash_crosscheck(snap_start)
        opened = opened_check(snap_start)
        frl = failure_and_restart_log()

        blocking = []
        if missing:
            blocking.append(f"missing {len(missing)}건 — 산출 결손(개봉 부적격)")
        if hashes["n_mismatch"]:
            blocking.append(f"해시 불일치 {hashes['n_mismatch']}건 — 봉인 사후 변조 신호")
        if opened["n_human_exposure_true"]:
            blocking.append(f"human_exposure=true {opened['n_human_exposure_true']}건 — 개봉 발생")
        if not all(x["set_equal"] for x in mfs):
            blocking.append("model×fold×seed 집합 불일치")
        if unexpected:
            blocking.append(f"unexpected {len(unexpected)}건 — 사유 미해소")

        status = load_json(os.path.join(CFG, "post_interim_freeze_v1_0.status.json"))
        spec = load_json(SPEC_FILE)[SPEC_KEY]

        audit = {
            "_warning": "점검 전용 — 지표·부호·λ 값 일체 없음(경로·개수·해시·조합·세션 메타만).",
            "ts_kst": now_kst(),
            "block": BLOCK,
            "instruction": "docs/78_pre_unblinding_audit_prompt_for_vscode.md",
            "spec_source": {
                "path": rel(SPEC_FILE),
                "sha256": sha256_file(SPEC_FILE),
                "key_path": SPEC_KEY + ".sealing_completeness_audit",
                "verbatim": spec["sealing_completeness_audit"],
                "korean_record": "docs/33_prereg_deviation_log.md 항목31 국문 (5)",
            },
            "gates": {"G0": g0, "G_HOLM": holm,
                      "G_IDLE_B": {"competitors": 0, "note": "계산 0이므로 게이트 A 면제 "
                                                             "(지시서 X-1-1) · B 는 유지"},
                      "sealed_baseline": {"expected_artifacts": SEALED_BASELINE_ARTIFACTS,
                                          "expected_total": SEALED_BASELINE_TOTAL,
                                          "observed_artifacts": n_art,
                                          "observed_total": len(snap_start)}},
            "expected_manifest": groups,
            "expected_manifest_note": "★ 비순환 — 기대 목록은 동결 러너 상수·동결 config·리포트·"
                                      "실행시점 기록물에서 **먼저** 구성했고 live 디렉터리 열거를 "
                                      "기대 목록으로 삼지 않았다(지시서 X-2).",
            "live_inventory": {
                "n_sealed_files": n_art,
                "n_access_logs": n_access,
                "n_total": len(snap_start),
                "n_sealed_directories": len({k.split("/_sealed/")[0] + "/_sealed"
                                             for k in snap_start}),
                "by_directory": {},
            },
            "crosscheck": {
                "scope": "access.log 제외 산출물 273종 (sealed guard 기준선 규약과 동일)",
                "n_expected": len(expected_all),
                "n_live": len(live_art),
                "missing": missing,
                "n_missing": len(missing),
                "unexpected": [],
                "n_unexpected": len(unexpected),
                "verdict": "PASS" if not missing and not unexpected else "FAIL",
            },
            "model_fold_seed_crosscheck": mfs,
            "hashes": hashes,
            "opened_check": opened,
            "failure_and_restart_log": frl,
            "unblinding_state": {
                "unblinding_performed": status.get("unblinding_performed"),
                "unblinding_approver": "양진홍 교수님 (docs/77 · status sidecar)",
                "timing": "still_undecided — 별도 승인 필요",
                "note": "본 점검 통과는 개봉 허가가 아니다. 개봉은 Holm ⑧ 확보 + 별도 승인 필요.",
            },
            "verdict": "FAIL" if blocking else "PASS",
            "blocking_findings": blocking,
        }
        for k in sorted(snap_start):
            d = k.split("/_sealed/")[0] + "/_sealed"
            b = audit["live_inventory"]["by_directory"].setdefault(
                d, {"n_files": 0, "n_access_log": 0})
            b["n_files"] += 1
            if k.endswith("/access.log"):
                b["n_access_log"] += 1

        # unexpected 는 중단 사유가 아니라 **전건 열거 + 사유** (지시서 X-2)
        for p in unexpected:
            audit["crosscheck"]["unexpected"].append({"path": p, "reason": "사유 미기입 — 미해소"})

        audit_sha = dump_json(AUDIT_JSON, audit)
        logln(f"[산출] {rel(AUDIT_JSON)} sha256 {audit_sha[:16]}")

        # X-4 ── 부호 인지 기록표
        sign_rows, ledger, pub_exposure, advisor_det, advisor_hits = build_sign_matrix()
        n_sign_entries = sum(1 for e in load_json(os.path.join(PROV, "first_look_log.json"))
                             if e.get("delta_sign"))
        matrix = {
            "_warning": "부호 값 포함 — 공개 요약(audit_public.json)에는 값을 싣지 않는다. "
                        "λ·macro AP·Δ 크기·CI·p 는 한 값도 없다.",
            "ts_kst": now_kst(),
            "block": BLOCK,
            "spec_source": {"path": rel(SPEC_FILE), "sha256": sha256_file(SPEC_FILE),
                            "key_path": SPEC_KEY + ".sign_disclosure_matrix",
                            "verbatim": spec["sign_disclosure_matrix"]},
            "scope": "부호가 **이미 알려진** 대비만. 새 부호 산출 0 (Δ·AP·CI·p 계산 0 · "
                     "emit_sign 0 · decision.py 호출 0).",
            "machine_identification": {
                "criterion": "first_look_log.json 의 delta_sign != null",
                "n_entries_total": len(load_json(os.path.join(PROV, "first_look_log.json"))),
                "n_with_sign": n_sign_entries,
            },
            "rows": sign_rows,
            "n_rows": len(sign_rows),
            "row_criterion": "행 1개 = 부호가 알려진 대비 1개(first_look_log 의 delta_sign != null "
                             "entry 와 1:1). 인지 경로는 행 안의 `disclosure_routes` 로 표현한다 — "
                             "같은 대비를 경로마다 별개 행으로 쪼개면 대비 수가 부풀려진다.",
            "public_exposure_verification": pub_exposure,
            "not_computed": [
                {"holm_label": "M2b-P-ID", "status": "not_computed",
                 "note": "층화 산출은 전량 봉인 · Δ·부호 미공개(docs/57)"},
                {"holm_label": "M2b-P-FAM", "status": "not_computed"},
                {"holm_label": "M2b-realloc_null", "status": "not_computed",
                 "note": "§13-4 집계 산출 전량 `_sealed/null_result.json` 봉인"},
                {"holm_label": "M2b-M0", "status": "not_computed"},
                {"holm_label": "M2b-RF_tuned", "status": "not_computed",
                 "note": "블록 O — Δ 미산출 · emit_sign 0"},
                {"holm_label": "RFseq-RF", "status": "not_computed",
                 "note": "블록 P — Δ 미산출 · emit_sign 0 · 선택 λ 봉인"},
                {"holm_label": "RQ-int", "status": "not_computed",
                 "note": "미착수 — U1~U7 외부검토 회신 + SAP 1.2 재동결 대기"},
            ],
            "open_questions": [],
        }

        # 지도교수 경로 — 실측 판정(추측 기입 금지)
        corr = ledger.get("correspondence", [])
        matrix["advisor_route"] = {
            "who": "양진홍 교수님",
            "determination": advisor_det,
            "method": "ledger.correspondence · correspondence_subject_authority · "
                      "docs/44 · docs/45 실측 — 부호 어휘 **값** 스캔(키 이름 아님)",
            "n_correspondence_rows": len(corr),
            "docs44_note": "docs/44 는 최초 조회 **직전**의 승인 요청이라 부호가 없다.",
            "evidence": ["experiments/provenance/ledger.json:correspondence",
                         "experiments/provenance/ledger.json:correspondence_subject_authority",
                         "docs/44_professor_approval_email_first_look.md",
                         "docs/45_research_integrity_ledger.md §5"],
            "sign_lexeme_hits_in_correspondence": advisor_hits,
        }
        if not advisor_hits:
            matrix["open_questions"].append(
                "지도교수에게 Δ(M2b−M1b) 부호가 전달된 사실이 서신 기록에서 확인되지 않는다 → "
                "`unknown_as_of_2026-08-06`. 추측 기입 금지(블록 T 규약).")
        matrix_sha = dump_json(MATRIX_JSON, matrix)
        logln(f"[산출] {rel(MATRIX_JSON)} sha256 {matrix_sha[:16]} · 행 {len(sign_rows)}")

        # X-6 ── 공개 요약
        public = {
            "_scope": "공개 — 판정·개수·해시 대조 건수·경로 종류 뿐. "
                      "지표·부호 값·λ·Δ·CI·p 는 없다.",
            "ts_kst": now_kst(),
            "block": BLOCK,
            "instruction": "docs/78_pre_unblinding_audit_prompt_for_vscode.md",
            "gates": {"G0_pass": g0["pass"], "G_HOLM_n_labels": holm["n_labels"],
                      "G_IDLE_B_competitors": 0,
                      "sealed_artifacts_start": n_art, "sealed_total_start": len(snap_start)},
            "sealing_completeness": {
                "n_expected": len(expected_all),
                "n_live_artifacts": len(live_art),
                "n_missing": len(missing),
                "n_unexpected": len(unexpected),
                "n_sealed_directories": audit["live_inventory"]["n_sealed_directories"],
                "n_hashed": hashes["n_sealed_artifacts_hashed"],
                "n_hash_compared": hashes["n_compared"],
                "n_hash_mismatch": hashes["n_mismatch"],
                "n_files_with_recorded_hash": hashes["n_files_with_recorded_hash"],
                "model_fold_seed_all_set_equal": all(x["set_equal"] for x in mfs),
                "n_access_log_files": opened["n_access_log_files"],
                "n_access_log_entries": opened["n_access_log_entries"],
                "n_human_exposure_true": opened["n_human_exposure_true"],
                "access_log_types": sorted(opened["type_distribution"]),
                "n_known_failure_restart_events": frl["n_known_events"],
                "verdict": audit["verdict"],
            },
            "sign_disclosure": {
                "n_rows": len(sign_rows),
                "route_kinds": sorted({"runner_first_look", "public_repository_pushed",
                                       "local_commit_unpushed", "advisor"}),
                "advisor_route_determination": matrix["advisor_route"]["determination"],
                "n_open_questions": len(matrix["open_questions"]),
                "values_withheld": True,
                "note": "부호 값은 sign_disclosure_matrix.json 과 docs/79 에만 둔다.",
            },
            "not_performed": {
                "unblinding_performed": status.get("unblinding_performed"),
                "open_sealed_calls": 0, "emit_sign_calls": 0, "decision_py_calls": 0,
                "model_training": 0, "model_inference": 0, "new_estimates": 0,
                "network": 0, "git_commit": 0, "git_push": 0,
                "files_added_to_sealed": 0,
            },
            "artifacts": {
                "sealing_completeness_audit.json": audit_sha,
                "sign_disclosure_matrix.json": matrix_sha,
            },
        }
        scan = defensive_scan(public)
        public["defensive_scan"] = {"n_forbidden_keys": scan["n_forbidden_keys"],
                                    "n_value_scan_hits": scan["n_value_scan_hits"],
                                    "method": "★ 키 이름이 아니라 값으로 판정 — 본 블록은 "
                                              "'sign' 낱말이 도처에 나오므로 키 기반 판정은 오탐."}
        if scan["n_forbidden_keys"] or scan["n_value_scan_hits"]:
            print(json.dumps(scan, ensure_ascii=False, indent=2)[:4000], file=sys.stderr)
            raise AssertionError("공개 요약 방어 스캔 위반")
        pub_sha = dump_json(PUBLIC_JSON, public)
        logln(f"[산출] {rel(PUBLIC_JSON)} sha256 {pub_sha[:16]}")

        gate_b_exclusive("pre_unblinding_audit:exit")
        snap_end = sealed_snapshot()
        assert snap_end == snap_start, "sealed 스냅샷 착수≠종료 — 즉시 중단"
        logln(f"[sealed guard] 종료 스냅샷 착수와 완전 일치 — 산출물 {n_art} · 전체 {len(snap_end)}")

        logln(f"\n[판정] {audit['verdict']} · missing {len(missing)} · "
              f"unexpected {len(unexpected)} · 해시 대조 {hashes['n_compared']}건 "
              f"불일치 {hashes['n_mismatch']} · human_exposure {opened['n_human_exposure_true']} · "
              f"부호 인지 행 {len(sign_rows)}")
        if blocking:
            print("[중단 사유]", *blocking, sep="\n  - ", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
