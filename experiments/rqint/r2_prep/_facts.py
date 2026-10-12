#!/usr/bin/env python3
"""_facts.py — 블록 AK(docs/99) §2 FACTS registry 17행 실측 대조. 읽기 전용."""
import ast, hashlib, json, os, re, subprocess, sys
from datetime import datetime, timedelta, timezone

ROOT = "<REPO_ROOT>"
KST = timezone(timedelta(hours=9))
OUT = os.path.join(ROOT, "experiments", "rqint", "r2_prep", "facts.json")
rows = []


def sha(p):
    h = hashlib.sha256()
    with open(os.path.join(ROOT, p), "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def J(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


def T(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def add(fid, expect, src, observed, ok):
    rows.append({"fact_id": fid, "expected": expect, "source": src,
                 "observed": observed, "match": bool(ok)})


# F-VERLIT
fz = "v3_Multimodal/src/sap/freeze.py"
t = T(fz)
lines = t.splitlines()
verlit = [i + 1 for i, l in enumerate(lines) if '"sap_version": "1.1"' in l]
cli = [i + 1 for i, l in enumerate(lines)
       if re.search(r"argparse|sys\.argv|os\.environ|getenv", l)]
add("F-VERLIT", 'sap_version 리터럴 "1.1" 이 L581 단 1곳 · CLI/env 경로 0', fz,
    {"literal_lines": verlit, "cli_env_lines": cli}, verlit == [581] and cli == [])

# F-MODFILES
m = re.search(r"MODULE_FILES = \[(.*?)\]", t, re.S)
mods = re.findall(r'"([^"]+)"', m.group(1))
mf_line = t[:m.start()].count("\n") + 1
add("F-MODFILES", "MODULE_FILES 11개이고 freeze.py 포함", fz + " L47-49",
    {"n": len(mods), "starts_at_line": mf_line, "modules": mods,
     "freeze_py_included": "freeze.py" in mods},
    len(mods) == 11 and "freeze.py" in mods)

# F-MFSRC
dc = "v3_Multimodal/src/sap/decision.py"
dt = T(dc)
MFSTR = "RF primary confirmatory (RF-Morgan+seq)"
mf_lines = [i + 1 for i, l in enumerate(dt.splitlines()) if MFSTR in l]
add("F-MFSRC", f'"{MFSTR}" = decision.py 7행 (L61·65·69·73·77·81·85)', dc,
    {"lines": mf_lines, "n": len(mf_lines)},
    mf_lines == [61, 65, 69, 73, 77, 81, 85])

# F-MFMANI
MAN = "experiments/sap/manifest.json"
man = J(MAN)
hits = []


def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            walk(v, p + "/" + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, p + "[" + str(i) + "]")
    else:
        if o == MFSTR:
            hits.append(p)


walk(man)
exp_paths = ([f"/frozen_parameters/decision_A11/multiplicity_manifest[{i}]/model_family" for i in range(7)] +
             [f"/validation/decision_A11/multiplicity_manifest[{i}]/model_family" for i in range(7)])
add("F-MFMANI", "manifest.json 14곳 (frozen_parameters/validation × multiplicity_manifest[0..6])",
    MAN, {"n": len(hits), "paths": hits}, sorted(hits) == sorted(exp_paths))

# F-REPRO
add("F-REPRO", ".venv/bin/python3 v3_Multimodal/src/sap/freeze.py", MAN,
    man.get("reproduce"),
    man.get("reproduce") == ".venv/bin/python3 v3_Multimodal/src/sap/freeze.py")

# F-AMEND8
A8 = "docs/55b_rqint_external_statreview_package_v2.md"
at = T(A8)
blanks = {b: [i + 1 for i, l in enumerate(at.splitlines()) if b in l]
          for b in ("[DATE]", "[NAME]", "[DEGREE]", "[AFFILIATION]")}
verb = "all pre-existing module hashes remain unchanged"
vl = [i + 1 for i, l in enumerate(at.splitlines()) if verb in l]
add("F-AMEND8", "§8 빈칸 4개 + 축자 'all pre-existing module hashes remain unchanged' 존재", A8,
    {"blanks": blanks, "verbatim_lines": vl},
    all(v for v in blanks.values()) and len(blanks) == 4 and len(vl) == 1)

# F-R5GAP
d0727 = [i + 1 for i, l in enumerate(at.splitlines()) if "2026-07-27" in l]
s8 = at.split("## 8. Amendment")[1].split("## 9.")[0]
add("F-R5GAP", "§8 개정문에 공개일자 2026-07-27 없음 · 노출 인원 없음 · 문서 전체 07-27 은 §2 본문 1곳",
    A8, {"lines_with_2026_07_27": d0727, "in_section8": "2026-07-27" in s8,
         "persons_count_in_section8": bool(re.search(r"\b(two|2)\s+(persons|people|individuals)", s8, re.I))},
    d0727 == [137] and "2026-07-27" not in s8)

# F-FLR
LED = "experiments/provenance/ledger.json"
led = J(LED)
flr = led["first_look_register"]
r = flr["rows"]
add("F-FLR", "first_look_register.rows 4행 · 전건 2026-07-27 · delta_sign negative · viewer vscode-claude(runner)",
    LED, {"type": type(flr).__name__, "keys": list(flr.keys()), "n_rows": len(r),
          "all_20260727": all(x["ts_kst"].startswith("2026-07-27") for x in r),
          "all_negative": all(x["delta_sign"] == "negative" for x in r),
          "all_viewer": all(x["viewer"] == "vscode-claude(runner)" for x in r)},
    isinstance(flr, dict) and len(r) == 4
    and all(x["ts_kst"].startswith("2026-07-27") for x in r)
    and all(x["delta_sign"] == "negative" for x in r)
    and all(x["viewer"] == "vscode-claude(runner)" for x in r))

# F-SU / F-V0STATUS
V0 = "v3_Multimodal/config/rqint_procedure_decisions_v0.json"
v0 = J(V0)
su = v0["still_unspecified"]
su_st = {x["id"]: x["status"] for x in su}
add("F-SU", "still_unspecified 5건 (y1·y2 resolved / b·c0c3 still_unspecified / r3 escalated + confirmed_second_party null)",
    V0, {"n": len(su), "statuses": su_st,
         "confirmed_second_party": next(x for x in su if x["id"] == "r3_second_party").get("confirmed_second_party")},
    len(su) == 5
    and su_st["y1_replacement_count_unit"] == "resolved_by_our_pre_specified_reading_2026-08-12"
    and su_st["y2_r1_failure_fallback_decision_rule"] == "resolved_by_our_pre_specified_reading_2026-08-12"
    and su_st["b_monte_carlo_sample_size_and_definition"] == "still_unspecified"
    and su_st["c0_c3_replicates"] == "still_unspecified"
    and su_st["r3_second_party"] == "escalated_awaiting_advisor_reply"
    and next(x for x in su if x["id"] == "r3_second_party").get("confirmed_second_party") is None)

add("F-V0STATUS", "status=decisions_recorded_not_frozen · is_sap_freeze false", V0,
    {"status": v0["status"], "is_sap_freeze": v0["is_sap_freeze"]},
    v0["status"] == "decisions_recorded_not_frozen" and v0["is_sap_freeze"] is False)

# F-BMEAS
b100 = J("experiments/rqint/b_100k/run.json")
bdry = J("experiments/rqint/b_dryrun/decisive.json")
h1, h2 = b100["wall_hours_total"], bdry["wall_hours_total"]
add("F-BMEAS", "(가) 동전 100,000 → 참조 200,000 · 19.4887 h / (나) 50,000 → 100,000 · 9.8848 h · 둘 다 ≤24 h",
    "experiments/rqint/b_100k/run.json · experiments/rqint/b_dryrun/decisive.json",
    {"ga": {"n_coin": b100["run_config"]["n_coin_vectors"],
            "ref": b100["run_config"]["reference_distribution"], "wall_hours": h1},
     "na": {"n_coin": bdry["decisive_config"]["n_coin_vectors"],
            "ref": bdry["decisive_config"]["reference_distribution"], "wall_hours": h2}},
    abs(h1 - 19.4887) < 5e-4 and abs(h2 - 9.8848) < 5e-4 and h1 <= 24 and h2 <= 24)

# F-C0C3
CD = "experiments/rqint/calibration_design.json"
cd = J(CD)
cd_sha = sha(CD)
first_sim = None
with open(os.path.join(ROOT, "experiments/rqint/calibration_sessions.jsonl"), encoding="utf-8") as f:
    for l in f:
        e = json.loads(l)
        if e.get("event") == "session_start":
            first_sim = e["when_kst"]
            break
add("F-C0C3", "primary 2,000 / sensitivity 1,000 이 calibration_design.json(42e2f8f9f3f24ec1…)에 2026-08-12 22:25:21 KST 동결 = 첫 시뮬(22:46:44)보다 앞섬",
    CD + " · experiments/rqint/calibration_sessions.jsonl",
    {"primary_R": cd["replication_plan"]["primary_R"],
     "sensitivity_R": cd["replication_plan"]["sensitivity_R"],
     "design_sha256": cd_sha, "frozen_at_kst": cd["frozen_at_kst"],
     "first_session_start_kst": first_sim,
     "design_precedes_first_sim": cd["frozen_at_kst"] < first_sim},
    cd["replication_plan"]["primary_R"] == 2000 and cd["replication_plan"]["sensitivity_R"] == 1000
    and cd_sha.startswith("42e2f8f9f3f24ec1")
    and cd["frozen_at_kst"] == "2026-08-12T22:25:21+09:00"
    and first_sim == "2026-08-12T22:46:44+09:00")

# F-R3
c19 = led["correspondence"][19]
R3F = "v3_Multimodal/config/r3_second_party_freeze.json"
add("F-R3", "교수님 승인 <GMAIL-MSGID> (2026-08-12 18:34:47 KST) · r3_second_party_freeze.json 존재",
    LED + " correspondence[19] · " + R3F,
    {"message_id": c19.get("message_id"), "ts_kst": c19.get("ts_kst"),
     "approval_scope": c19.get("approval_scope"),
     "freeze_exists": os.path.exists(os.path.join(ROOT, R3F)),
     "freeze_sha16": sha(R3F)[:16]},
    c19.get("message_id") == "<GMAIL-MSGID>"
    and c19.get("ts_kst") == "2026-08-12 18:34:47 KST"
    and os.path.exists(os.path.join(ROOT, R3F)))

# F-KS
cs = J("experiments/rqint/calibration_summary.json")
ksp = cs["acceptance_detail"]["C0:prop"]["ks_p"]
add("F-KS", "C0:prop KS p = 0.052447 (기준 0.05 바로 위)", "experiments/rqint/calibration_summary.json",
    {"ks_p": ksp, "above_0_05": ksp > 0.05, "margin": ksp - 0.05},
    abs(ksp - 0.052446940943157605) < 1e-12)

# F-MANI16
ms = sha(MAN)
add("F-MANI16", "manifest sha16 756d485feb4715e9 · sap_version 1.1", MAN,
    {"sha256": ms, "sha16": ms[:16], "sap_version": man["sap_version"]},
    ms[:16] == "756d485feb4715e9" and man["sap_version"] == "1.1")

# F-SEAL
allf, nolog = [], []
for rt, ds, fs in os.walk(os.path.join(ROOT, "experiments", "runs")):
    if "_sealed" not in rt:
        continue
    for fn in fs:
        allf.append(os.path.join(rt, fn))
        if fn != "access.log":
            nolog.append(fn)
add("F-SEAL", "291 전체 / 275 (access.log 제외)", "find experiments/runs -path '*_sealed*' -type f",
    {"n_all": len(allf), "n_excl_accesslog": len(nolog),
     "n_accesslog": len(allf) - len(nolog)},
    len(allf) == 291 and len(nolog) == 275)

# F-GIT
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
ncom = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
add("F-GIT", "HEAD 566f487 · 커밋 21", "git rev-parse HEAD · git rev-list --count HEAD",
    {"head": head, "head_short": head[:7], "n_commits": int(ncom)},
    head.startswith("566f487") and int(ncom) == 21)

# F-LEDGER
add("F-LEDGER", "키 11 · timeline 49 · correspondence 22 · external_reviews 6 · authoritative_sources 26",
    LED, {"n_top_keys": len(led), "top_keys": list(led.keys()),
          "timeline": len(led["timeline"]), "correspondence": len(led["correspondence"]),
          "external_reviews": len(led["external_reviews"]),
          "authoritative_sources": len(led["authoritative_sources"])},
    len(led) == 11 and len(led["timeline"]) == 49 and len(led["correspondence"]) == 22
    and len(led["external_reviews"]) == 6 and len(led["authoritative_sources"]) == 26)

out = {"_doc": "블록 AK(docs/99) §2 FACTS registry 실측 대조 — 읽기 전용 · 계산 0 · 동결 0",
       "when_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
       "n_facts": len(rows), "all_match": all(x["match"] for x in rows),
       "mismatches": [x["fact_id"] for x in rows if not x["match"]],
       "facts": rows}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"n_facts={out['n_facts']} all_match={out['all_match']} mismatches={out['mismatches']}")
for x in rows:
    print(("PASS " if x["match"] else "FAIL ") + x["fact_id"])
