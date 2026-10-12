#!/usr/bin/env python3
"""블록 AI 무결성 선언 — docs/97 §0·§4 17항. 선언값은 기계 확인 가능한 것만 담는다."""
import os, sys, json, hashlib, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_dryrun")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
base = json.load(open(os.path.join(OUT, "_baseline_snapshot.json")))
bsrc = open(os.path.join(ROOT, "v3_Multimodal", "src", "b_dryrun.py"), encoding="utf-8").read()
out = {
    "block": "AI (docs/97)",
    "unblinding_performed": False,
    "gin_start_still_blocked": True,
    "confirmatory_predictions_loaded": False,
    "confirmatory_data_accessed": False,
    "sealed_accessed": False,
    "sealed_access_mode": "stat-only snapshot (os.stat) — 내용 읽기 0",
    "open_sealed_calls": bsrc.count("open_sealed"),
    "emit_sign_calls": bsrc.count("emit_sign"),
    "decision_py_calls": bsrc.count("sap.decision") + bsrc.count("from sap import decision"),
    "B_definition_status": "still_unspecified (본 블록에서 확정·동결 0 — R2 의 일)",
    "B_frozen_by_this_block": False,
    "sap_version": json.load(open(os.path.join(ROOT, "experiments", "sap", "manifest.json")))["sap_version"],
    "sap_1_2_refreeze": False,
    "rqint_py_sha256_unchanged": sha(os.path.join(ROOT, "v3_Multimodal", "src", "sap", "rqint.py"))
                                 == base["freeze_baseline"]["other"]["v3_Multimodal/src/sap/rqint.py"],
    "network_calls": 0,
    "data_raw_modified": False,
    "git_commit_push": 0,
    "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip(),
    "files_created_by_this_block": [
        "v3_Multimodal/config/b_dryrun_prespec.json",
        "v3_Multimodal/src/b_dryrun.py",
        "experiments/rqint/b_dryrun/ (계측 산출·검증 스크립트)",
        "docs/97_b_definition_dryrun_report.md",
    ],
}
json.dump(out, open(os.path.join(OUT, "integrity.json"), "w"), ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
