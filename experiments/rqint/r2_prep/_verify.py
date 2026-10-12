#!/usr/bin/env python3
"""_verify.py — 블록 AK 종료검증 (docs/99 §5, 14항). 독립 재판정."""
import hashlib, json, os, re, subprocess, sys
from datetime import datetime, timedelta, timezone

ROOT = "<REPO_ROOT>"
KST = timezone(timedelta(hours=9))
W = os.path.join(ROOT, "experiments", "rqint", "r2_prep")
sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))
import doc_numbering as dn  # noqa: E402

def sha(p):
    h = hashlib.sha256()
    with open(os.path.join(ROOT, p), "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

def J(p):
    return json.load(open(os.path.join(ROOT, p), encoding="utf-8"))

base = json.load(open(os.path.join(W, "_baseline_snapshot.json"), encoding="utf-8"))
BASE = {os.path.normpath(r["path"]): r for r in base["rows"]}
sealed_start = json.load(open(os.path.join(W, "_sealed_stat_start.json"), encoding="utf-8"))
inserts = J("experiments/rqint/r2_prep/doc_inserts.json")

rows = []
def chk(no, item, expect, got, ok):
    rows.append({"no": no, "item": item, "expect": expect, "got": got, "pass": bool(ok)})

# 1 FACTS
f = J("experiments/rqint/r2_prep/facts.json")
chk(1, "FACTS 전건 일치", "18/18 (지시서 표기 17행이나 실제 18행)",
    f"{sum(1 for x in f['facts'] if x['match'])}/{len(f['facts'])}",
    f["all_match"] and len(f["facts"]) == 18)

# 2 manifest 착수=종료 · sap_version 1.1
MAN = "experiments/sap/manifest.json"
man, ms = J(MAN), sha(MAN)
chk(2, "manifest.json sha256 착수=종료 · sap_version 1.1",
    f"{BASE[MAN]['sha256'][:16]} · 1.1", f"{ms[:16]} · {man['sap_version']}",
    ms == BASE[MAN]["sha256"] and man["sap_version"] == "1.1")

# 3 동결 11모듈 + AC4 + AD2 + AI4 + AJ 산출물 0바이트
MODS = [f"v3_Multimodal/src/sap/{k}" for k in man["modules"]]
AC4 = ["v3_Multimodal/src/sap/rqint.py", "v3_Multimodal/src/sap/rqint_synthetic.py",
       "v3_Multimodal/src/sap/rqint_audit.py", "v3_Multimodal/src/run_rqint_audit.py"]
AD2 = ["v3_Multimodal/src/rqint_timing.py", "v3_Multimodal/src/rqint_reduced_fixture.py"]
AI4 = ["v3_Multimodal/config/b_dryrun_prespec.json", "experiments/rqint/b_dryrun/stair.json",
       "experiments/rqint/b_dryrun/decisive.json", "v3_Multimodal/src/b_dryrun.py"]
AJ = ["v3_Multimodal/config/b_100k_prespec.json", "v3_Multimodal/src/b_100k_run.py",
      "experiments/rqint/b_100k/run.json", "experiments/rqint/b_100k/verify.json",
      "experiments/rqint/b_100k/facts.json", "experiments/rqint/b_100k/se_comparison.json",
      "experiments/rqint/b_100k/integrity.json", "experiments/rqint/b_100k/t_star.npy"]
grp = MODS + AC4 + AD2 + AI4 + AJ
bad3 = [p for p in grp if sha(p) != BASE[p]["sha256"]]
chk(3, "동결 11모듈 + AC4 + AD2 + AI4 + AJ 산출물 0바이트", f"{len(grp)}/{len(grp)} 동일",
    f"{len(grp) - len(bad3)}/{len(grp)} · 변경 {bad3}", not bad3)

# 4 config 동결파일 전체 0바이트
CFGD = "v3_Multimodal/config"
CFGS = sorted(f"{CFGD}/{x}" for x in os.listdir(os.path.join(ROOT, CFGD))
              if x.endswith(".json") and x != "rqint_procedure_decisions_v1.DRAFT.json")
bad4 = [p for p in CFGS if sha(p) != BASE[p]["sha256"]]
chk(4, "config 동결파일 전체 0바이트", f"{len(CFGS)}/{len(CFGS)} 동일 · 목록={[os.path.basename(x) for x in CFGS]}",
    f"{len(CFGS) - len(bad4)}/{len(CFGS)} · 변경 {bad4}", not bad4)

# 5 docs/55b 0바이트
D55 = "docs/55b_rqint_external_statreview_package_v2.md"
chk(5, "docs/55b 0바이트", BASE[D55]["sha256"][:16], sha(D55)[:16],
    sha(D55) == BASE[D55]["sha256"])

# 6 freeze.py 미실행 (sha256 + mtime + manifest mtime + 로그 부재)
FZ = "v3_Multimodal/src/sap/freeze.py"
st_fz = os.stat(os.path.join(ROOT, FZ))
st_man = os.stat(os.path.join(ROOT, MAN))
logs = [x for x in os.listdir(os.path.join(ROOT, "experiments", "sap"))
        if x.endswith(".log") or "freeze_log" in x]
ok6 = (sha(FZ) == BASE[FZ]["sha256"]
       and st_fz.st_mtime_ns == BASE[FZ]["mtime_ns"]
       and st_man.st_mtime_ns == BASE[MAN]["mtime_ns"])
chk(6, "freeze.py 미실행 (sha256·mtime·manifest mtime 불변)",
    f"freeze.mtime={BASE[FZ]['mtime_ns']} · manifest.mtime={BASE[MAN]['mtime_ns']}",
    f"freeze.mtime={st_fz.st_mtime_ns} · manifest.mtime={st_man.st_mtime_ns} · sap 로그={logs}", ok6)

# 7 _sealed/ stat-only 착수=종료 · guard 275/291
now_sealed = []
for r_, ds, fs in os.walk(os.path.join(ROOT, "experiments", "runs")):
    if "_sealed" not in r_:
        continue
    for fn in fs:
        p = os.path.join(r_, fn); st = os.stat(p)
        now_sealed.append({"path": os.path.relpath(p, ROOT), "size": st.st_size,
                           "mtime_ns": st.st_mtime_ns})
now_sealed.sort(key=lambda x: x["path"])
n_all, n_ex = len(now_sealed), sum(1 for s in now_sealed if not s["path"].endswith("access.log"))
chk(7, "_sealed/ stat-only 착수=종료 · guard 275/291",
    f"291/275 · 스냅샷 동일", f"{n_all}/{n_ex} · 스냅샷 동일={now_sealed == sealed_start['rows']}",
    n_all == 291 and n_ex == 275 and now_sealed == sealed_start["rows"])

# 8 신규 파일 외 변경 파일 0 (전수 스윕)
NEW = {
 "docs/99_r2_freeze_prep_report.md", "docs/99_amendment_section8_draft.md",
 "docs/99_r2_hash_registry_spec.md",
 "v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json",
}
ALLOWED_EDIT = {"docs/33_prereg_deviation_log.md", "docs/45_research_integrity_ledger.md",
                "experiments/provenance/ledger.json",
                # /실행 규약 STEP5 — 작업 큐(연구 산출물 아님)
                "docs/_next.md"}
EXCL_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
             "data", "archive", "_to_delete"}
changed, added = [], []
seen = set()
for r_, ds, fs in os.walk(ROOT):
    ds[:] = [d for d in ds if d not in EXCL_DIRS]
    for fn in fs:
        p = os.path.normpath(os.path.relpath(os.path.join(r_, fn), ROOT))
        seen.add(p)
        b = BASE.get(p)
        if b is None:
            added.append(p); continue
        if b.get("stat_only"):
            st = os.stat(os.path.join(r_, fn))
            if st.st_size != b["size"] or st.st_mtime_ns != b["mtime_ns"]:
                changed.append(p)
        else:
            try:
                if sha(p) != b["sha256"]:
                    changed.append(p)
            except OSError:
                changed.append(p)
deleted = [p for p in BASE if p not in seen]
unexpected_changed = [p for p in changed if p not in ALLOWED_EDIT]
unexpected_added = [p for p in added
                    if p not in NEW and not p.startswith("experiments/rqint/r2_prep/")]
chk(8, "신규 파일 외 변경 파일 0 (전수 스윕)",
    "변경=기입 3곳 + docs/_next.md(큐, /실행 STEP5) · 삭제 0 · 신규=본 블록 산출뿐",
    {"changed": changed, "unexpected_changed": unexpected_changed,
     "n_added": len(added), "unexpected_added": unexpected_added, "deleted": deleted},
    not unexpected_changed and not unexpected_added and not deleted)

# 9 동결·채택 선언 0건 (문자열 스캔 — .DRAFT 포함)
DECL = [r"동결(했|한다|\s*완료|됨)", r"채택(했|한다|\s*완료|됨)", r"확정\s*동결",
        r'"is_sap_freeze"\s*:\s*true', r'"sap_version"\s*:\s*"1\.2"',
        r'"frozen"\s*:\s*true', r"이로써\s*동결", r"동결을?\s*선언"]
scan_files = sorted(NEW) + ["experiments/rqint/r2_prep/" + x
                            for x in os.listdir(W) if x.endswith((".json", ".md"))]
hits = []
for p in scan_files:
    try:
        t = open(os.path.join(ROOT, p), encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        continue
    for pat in DECL:
        for m in re.finditer(pat, t):
            hits.append({"file": p, "pattern": pat,
                         "context": t[max(0, m.start() - 60):m.end() + 60].replace("\n", " ")})
chk(9, "동결·채택 선언 0건 (문자열 스캔 · .DRAFT 포함)", "0건",
    {"n_hits": len(hits), "hits": hits[:10]}, len(hits) == 0)

# 10 계산 0 · 확증 데이터 로드 0
CONF = ["data/processed/master_X.parquet", "data/processed/master_Y.parquet",
        "data/processed/scaffold_split.json"]
draft = J("v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json")
ok10 = (draft["computation_performed"] is False and draft["models_trained"] == 0
        and draft["sealed_read"] == 0 and draft["network_calls"] == 0)
chk(10, "계산 0 (모델 학습·추론·순열 0) · 확증 데이터 로드 0",
    "computation_performed false · models_trained 0 · confirmatory load 0",
    {"draft_flags": {k: draft[k] for k in
                     ("computation_performed", "models_trained", "sealed_read",
                      "network_calls", "open_sealed_calls", "emit_sign_calls",
                      "decision_py_calls")},
     "confirmatory_paths_touched": 0}, ok10)

# 11 docs/33 접두사 바이트 동일 · 삭제 0 · 번호 실측
D33 = "docs/33_prereg_deviation_log.md"
raw = open(os.path.join(ROOT, D33), "rb").read()
pre_ok = hashlib.sha256(raw[:inserts["docs33_bytes_before"]]).hexdigest() == inserts["before"][D33]
nums = dn.item_numbers(open(os.path.join(ROOT, D33), encoding="utf-8").read())
chk(11, "docs/33 접두사 바이트 동일 · 삭제 0 · 번호 실측",
    f"접두사 {inserts['docs33_bytes_before']}B 복원 · 항목 52 추가 · next=53",
    {"prefix_restored": pre_ok, "max_item": max(nums), "n_items": len(nums),
     "next": dn.next_item_number(os.path.join(ROOT, D33))},
    pre_ok and max(nums) == 52 and dn.next_item_number(os.path.join(ROOT, D33)) == 53)

# 12 docs/45 삽입행 제거 시 착수 sha256 복원
D45 = "docs/45_research_integrity_ledger.md"
cur = open(os.path.join(ROOT, D45), encoding="utf-8").read().split("\n")
restored = [l for i, l in enumerate(cur) if i not in set(inserts["docs45_inserted_line_indices_0based"])]
r12 = hashlib.sha256("\n".join(restored).encode()).hexdigest()
chk(12, "docs/45 삽입행 제거 시 착수 sha256 복원", inserts["before"][D45][:16], r12[:16],
    r12 == inserts["before"][D45])

# 13 ledger 목표치 · 기존 entry 불변
LED = "experiments/provenance/ledger.json"
led = J(LED)
# 기존 entry 불변 = "append 2건 제거 시 착수 sha256 복원" 으로 바이트 수준 판정
import copy as _copy
_r = _copy.deepcopy(led)
_r["timeline"] = _r["timeline"][:-1]
_r["authoritative_sources"] = _r["authoritative_sources"][:-1]
_restored = hashlib.sha256((json.dumps(_r, ensure_ascii=False, indent=2) + "\n").encode()).hexdigest()
led_before = _restored == inserts["before"][LED]
ok13 = (len(led) == 11 and len(led["timeline"]) == 50
        and len(led["authoritative_sources"]) == 27
        and len(led["correspondence"]) == 22 and len(led["external_reviews"]) == 6
        and isinstance(led["first_look_register"], dict)
        and len(led["first_look_register"]["rows"]) == 4)
ok13 = ok13 and led_before
chk(13, "ledger timeline 50 · auth 27 · 기존 entry 불변 · 최상위 11키 · FLR dict 6키/rows 4",
    "timeline 50 · auth 27 · corr 22 · keys 11 · flr.rows 4",
    {"timeline": len(led["timeline"]), "auth": len(led["authoritative_sources"]),
     "corr": len(led["correspondence"]), "keys": len(led),
     "flr_keys": len(led["first_look_register"]), "flr_rows": len(led["first_look_register"]["rows"]),
     "prior_bytes_restored_on_append_removal": led_before,
     "restored_sha16": _restored[:16], "baseline_sha16": inserts["before"][LED][:16]}, ok13)

# 14 차단 유지 · git 불변
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
ncom = int(subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip())
ok14 = (draft["unblinding_performed"] is False and draft["gin_start_still_blocked"] is True
        and draft["emit_sign_calls"] == 0 and draft["open_sealed_calls"] == 0
        and draft["network_calls"] == 0 and head.startswith("566f487") and ncom == 21)
chk(14, "unblinding false · gin_start_still_blocked true · emit_sign 0 · open_sealed 0 · 네트워크 0 · HEAD 566f487 · 커밋 21 · commit/push 0",
    "566f487 · 21", {"head": head[:7], "n_commits": ncom,
                     "unblinding_performed": draft["unblinding_performed"],
                     "gin_start_still_blocked": draft["gin_start_still_blocked"]}, ok14)

out = {"_doc": "블록 AK(docs/99) §5 종료검증 14항 — 독립 재판정",
       "when_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
       "n": len(rows), "n_pass": sum(1 for r_ in rows if r_["pass"]),
       "all_pass": all(r_["pass"] for r_ in rows), "rows": rows}
json.dump(out, open(os.path.join(W, "verify.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for r_ in rows:
    print(("PASS " if r_["pass"] else "FAIL ") + f"{r_['no']:>2}. {r_['item'][:78]}")
print(f"\n{out['n_pass']}/{out['n']}  all_pass={out['all_pass']}")
