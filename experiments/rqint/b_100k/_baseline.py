#!/usr/bin/env python3
"""[블록 AJ] 착수 baseline 스냅샷 — `_sealed/` 는 **stat-only**(내용 읽기 0).

블록 AI `_baseline_snapshot.json` 과 동일 규격. 종료검증 11·12·13·14 의 대조 기준이 된다.
"""
import os, sys, json, hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_100k")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

# ── _sealed/ : os.stat 만. 파일 내용은 열지 않는다. ────────────────────────
rows = []
for dp, dn, fn in os.walk(os.path.join(ROOT, "experiments", "runs")):
    if "_sealed" not in dp:
        continue
    for n in sorted(fn):
        p = os.path.join(dp, n)
        st = os.stat(p)
        rows.append({"path": os.path.relpath(p, ROOT), "size": st.st_size,
                     "mtime_ns": st.st_mtime_ns})
rows.sort(key=lambda r: r["path"])
blob = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
sealed = {"n_files_all": len(rows),
          "n_files_excl_access_log": len([r for r in rows
                                          if not r["path"].endswith("access.log")]),
          "snapshot_sha256": hashlib.sha256(blob).hexdigest(), "rows": rows}
with open(os.path.join(OUT, "_sealed_stat_start.json"), "w", encoding="utf-8") as f:
    json.dump(sealed, f, ensure_ascii=False, indent=1)

# ── 동결 baseline (11 sap 모듈 + AC 4 + AD 2 + manifest·freeze config) ─────
SAP = os.path.join(ROOT, "v3_Multimodal", "src", "sap")
sap_mods = {n: sha(os.path.join(SAP, n))
            for n in sorted(os.listdir(SAP)) if n.endswith(".py")
            and n not in ("rqint.py", "rqint_synthetic.py", "rqint_audit.py")}
OTHER = ["experiments/sap/manifest.json",
         "v3_Multimodal/config/ladder_freeze.json",
         "v3_Multimodal/config/gin_seed_freeze.json",
         "v3_Multimodal/src/sap/rqint.py",
         "v3_Multimodal/src/sap/rqint_synthetic.py",
         "v3_Multimodal/src/sap/rqint_audit.py",
         "v3_Multimodal/src/run_rqint_audit.py",
         "v3_Multimodal/src/rqint_timing.py",
         "v3_Multimodal/src/rqint_reduced_fixture.py"]
other = {p: sha(os.path.join(ROOT, p)) for p in OTHER}

# ── 블록 AI 산출물 4종 (본 블록은 읽기만 — 0바이트 보존 대조 기준) ────────
AI4 = ["v3_Multimodal/config/b_dryrun_prespec.json",
       "experiments/rqint/b_dryrun/stair.json",
       "experiments/rqint/b_dryrun/decisive.json",
       "v3_Multimodal/src/b_dryrun.py"]
ai4 = {p: {"sha256": sha(os.path.join(ROOT, p)),
           "size": os.path.getsize(os.path.join(ROOT, p))} for p in AI4}

DOCS = ["docs/33_prereg_deviation_log.md", "docs/45_research_integrity_ledger.md",
        "experiments/provenance/ledger.json"]
docs = {p: {"sha256": sha(os.path.join(ROOT, p)),
            "size": os.path.getsize(os.path.join(ROOT, p))} for p in DOCS}

out = {"block": "AJ (docs/98)",
       "sealed": {k: sealed[k] for k in ("n_files_all", "n_files_excl_access_log",
                                         "snapshot_sha256")},
       "freeze_baseline": {"sap_modules": sap_mods, "other": other,
                           "sap_dir_listing": sorted(os.listdir(SAP))},
       "block_AI_artifacts": ai4,
       "docs": docs}
with open(os.path.join(OUT, "_baseline_snapshot.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps({"sealed": out["sealed"],
                  "n_sap_modules": len(sap_mods), "n_other": len(other),
                  "ai4": {k: v["sha256"][:16] for k, v in ai4.items()},
                  "docs": {k: v["sha256"][:16] for k, v in docs.items()}},
                 ensure_ascii=False, indent=2))
