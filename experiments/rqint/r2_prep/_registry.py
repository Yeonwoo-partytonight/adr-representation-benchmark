#!/usr/bin/env python3
"""_registry.py — R2P-6 해시 원장 스펙 표 생성(측정 전용). 파일 수정 = 신규 md 1개."""
import hashlib, json, os
from datetime import datetime, timedelta, timezone

ROOT = "<REPO_ROOT>"
KST = timezone(timedelta(hours=9))

def sha(p):
    h = hashlib.sha256()
    with open(os.path.join(ROOT, p), "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

man = json.load(open(os.path.join(ROOT, "experiments/sap/manifest.json"), encoding="utf-8"))
led = json.load(open(os.path.join(ROOT, "experiments/provenance/ledger.json"), encoding="utf-8"))
fa = led["frozen_artifacts"]
mods_reg = {k.replace(".py", ""): v for k, v in fa["sap_modules_v1.1"].items()}
docs45 = open(os.path.join(ROOT, "docs/45_research_integrity_ledger.md"), encoding="utf-8").read()

rows = []
def add(cat, path, note):
    s = sha(path)
    stem = os.path.basename(path).replace(".py", "").replace(".json", "")
    in_man = os.path.basename(path) in man["modules"]
    in_led = (stem in mods_reg) or any(
        isinstance(v, dict) and (v.get("sha16") == s[:16] or v.get("path") == path)
        for v in fa.values())
    in_45 = s[:16] in docs45
    where = []
    if in_man: where.append("manifest.modules")
    if in_led: where.append("ledger.frozen_artifacts")
    if in_45: where.append("docs/45 §3")
    rows.append({"category": cat, "path": path, "sha256": s, "sha16": s[:16],
                 "bytes": os.path.getsize(os.path.join(ROOT, path)),
                 "registered_in": where or [],
                 "in_registry": bool(where), "note": note})

SAP = "v3_Multimodal/src/sap"
for k in man["modules"]:
    add("① SAP 11모듈", f"{SAP}/{k}", "SAP 1.1 등재")
for k in ["rqint.py", "rqint_audit.py", "rqint_synthetic.py"]:
    add("② RQ-int 3모듈", f"{SAP}/{k}", "블록 AC 산출 · SAP 미등재")
CFG = "v3_Multimodal/config"
for fn in sorted(os.listdir(os.path.join(ROOT, CFG))):
    if fn.endswith(".json"):
        add("③ config 동결파일", f"{CFG}/{fn}", "")
add("④ B·시드집합·대표폴드·실패처리 소재", f"{SAP}/rqint.py",
    "`B_DEFINITION_STATUS` L63-64 = `still_unspecified` (B 의 유일한 소재)")
add("④ B·시드집합·대표폴드·실패처리 소재", f"{CFG}/gin_seed_freeze.json",
    "대표 outer unit 3 · training_seeds_ordered 5 · confirmatory_seed_prefix 3 · 예비/안정성 시드")
add("④ B·시드집합·대표폴드·실패처리 소재", f"{CFG}/rqint_procedure_decisions_v0.json",
    "D17 실패처리 규칙 축자(L169) · `status` = decisions_recorded_not_frozen")
add("④ B·시드집합·대표폴드·실패처리 소재", f"{CFG}/b_100k_prespec.json",
    "(가) 해석 실주행 사전명시 — B 판정식 2분기")
add("④ B·시드집합·대표폴드·실패처리 소재", f"{CFG}/b_dryrun_prespec.json",
    "(나) 해석 드라이런 사전명시 · 외삽 정책")
add("④ B·시드집합·대표폴드·실패처리 소재", "experiments/rqint/calibration_design.json",
    "C0~C3 복제수 primary 2,000 / sensitivity 1,000 · A12 · F_ACC")
for p, n in [("docs/30_preregistration_OSF_clean.md", "OSF 사전등록 정본 (immutable)"),
             ("docs/55b_rqint_external_statreview_package_v2.md", "외부검토 패키지 v2 — §8 개정문 원본"),
             ("docs/84_rqint_reviewer_response_triage.md", "D1~D22 · R1~R6 정본"),
             ("docs/33_prereg_deviation_log.md", "이탈기록 (append-only — 원장 등재값 `9399034b66e45aec` 은 동결시점 스냅샷이라 live 와 다른 것이 정상)"),
             ("docs/45_research_integrity_ledger.md", "무결성 원장 (append-only — 고정 해시 동결 대상 아님)"),
             ("experiments/sap/manifest.json", "SAP 1.1 매니페스트"),
             ("experiments/provenance/ledger.json", "기계검증 원장 (append-only)"),
             ("experiments/provenance/sign_disclosure_matrix.json", "부호 인지 기록표(R5 근거)"),
             ("v3_Multimodal/config/reviewer_identity_resolved.json", "amendment 빈칸 4개 값")]:
    add("⑤ 사전등록·개정문·원장 문서", p, n)

out = os.path.join(ROOT, "experiments/rqint/r2_prep/registry.json")
json.dump({"_doc": "R2P-6 해시 원장 스펙 실측 — 측정 전용 · 동결 0",
           "when_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
           "n_rows": len(rows),
           "n_not_in_registry": sum(1 for r in rows if not r["in_registry"]),
           "rows": rows}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# markdown
L = []
cur = None
for r in rows:
    if r["category"] != cur:
        cur = r["category"]
        L.append(f"\n### {cur}\n")
        L.append("| 경로 | sha256[:16] | bytes | 이미 등재된 곳 | 비고 |")
        L.append("|---|---|---|---|---|")
    reg = " · ".join(r["registered_in"]) if r["registered_in"] else "**미등재**"
    L.append(f"| `{r['path']}` | `{r['sha16']}` | {r['bytes']:,} | {reg} | {r['note']} |")
open(os.path.join(ROOT, "experiments/rqint/r2_prep/_registry_tables.md"), "w",
     encoding="utf-8").write("\n".join(L))
print("rows:", len(rows), "not_in_registry:", sum(1 for r in rows if not r["in_registry"]))
