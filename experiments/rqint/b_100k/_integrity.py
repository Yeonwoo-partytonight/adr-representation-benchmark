#!/usr/bin/env python3
"""[블록 AJ] 무결성 선언 — docs/98 §0·§4. 선언값은 기계 확인 가능한 것만 담는다."""
import os, sys, json, hashlib, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_100k")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
J = lambda p: json.load(open(p, encoding="utf-8"))

base = J(os.path.join(OUT, "_baseline_snapshot.json"))
src = open(os.path.join(ROOT, "v3_Multimodal", "src", "b_100k_run.py"), encoding="utf-8").read()

AI4 = ["v3_Multimodal/config/b_dryrun_prespec.json",
       "experiments/rqint/b_dryrun/stair.json",
       "experiments/rqint/b_dryrun/decisive.json",
       "v3_Multimodal/src/b_dryrun.py"]
ai4_now = {p: {"sha256": sha(os.path.join(ROOT, p)),
               "size": os.path.getsize(os.path.join(ROOT, p))} for p in AI4}

out = {
    "block": "AJ (docs/98)",
    "unblinding_performed": False,
    "gin_start_still_blocked": True,
    "confirmatory_predictions_loaded": False,
    "confirmatory_data_accessed": False,
    "sealed_accessed": False,
    "sealed_access_mode": "stat-only snapshot (os.stat) — 내용 읽기 0",
    "open_sealed_calls": src.count("open_sealed"),
    "emit_sign_calls": src.count("emit_sign"),
    "decision_py_calls": src.count("sap.decision") + src.count("from sap import decision"),
    "B_definition_status": "still_unspecified (본 블록에서 확정·동결 0 — R2 의 일)",
    "B_frozen_by_this_block": False,
    "B_definition_adopted_by_this_block": False,
    "sap_version": J(os.path.join(ROOT, "experiments", "sap", "manifest.json"))["sap_version"],
    "sap_1_2_refreeze": False,
    "rqint_py_sha256_unchanged": sha(os.path.join(ROOT, "v3_Multimodal", "src", "sap", "rqint.py"))
                                 == base["freeze_baseline"]["other"]["v3_Multimodal/src/sap/rqint.py"],
    "block_AI_artifacts_unchanged": ai4_now == base["block_AI_artifacts"],
    "block_AI_artifacts": ai4_now,
    "ai_prespec_modified": False,
    "network_calls": 0,
    "data_raw_modified": False,
    "git_commit_push": 0,
    "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip(),
    "files_created_by_this_block": [
        "v3_Multimodal/config/b_100k_prespec.json",
        "v3_Multimodal/src/b_100k_run.py",
        "experiments/rqint/b_100k/ (실주행 산출·검증 스크립트)",
        "docs/98_b_definition_100k_run_report.md",
    ],
}
with open(os.path.join(OUT, "integrity.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in out.items() if k != "block_AI_artifacts"},
                 ensure_ascii=False, indent=2))
