#!/usr/bin/env python3
"""블록 AI 종료검증 — docs/97 §4 (18항). 본런 산출을 읽어 기계 판정한다."""
import os, sys, json, hashlib, subprocess
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_dryrun")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
J = lambda p: json.load(open(p, encoding="utf-8"))

base = J(os.path.join(OUT, "_baseline_snapshot.json"))
stair = J(os.path.join(OUT, "stair.json"))
dec_p = os.path.join(OUT, "decisive.json")
dec = J(dec_p) if os.path.exists(dec_p) else None

import importlib.util
spec = importlib.util.spec_from_file_location("rc", os.path.join(ROOT, "v3_Multimodal", "src", "rqint_calibration.py"))
rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
spec2 = importlib.util.spec_from_file_location("rv", os.path.join(ROOT, "v3_Multimodal", "src", "rqint_calibration_verify.py"))
rv = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(rv)

rows = []
def chk(no, name, expect, got, ok):
    rows.append({"no": no, "item": name, "expect": expect, "got": got, "pass": bool(ok)})

# 1 FACTS
facts = J(os.path.join(OUT, "facts.json"))
chk(1, "FACTS 14행 전건 일치", "14/14 pass", f"{sum(1 for r in facts['rows'] if r['pass'])}/{len(facts['rows'])}",
    all(r["pass"] for r in facts["rows"]) and len(facts["rows"]) == 14)

# 2 prespec 동결 시각 < 첫 측정 · sha256 불변
pre_p = os.path.join(ROOT, "v3_Multimodal", "config", "b_dryrun_prespec.json")
pre = J(pre_p); pre_sha = sha(pre_p)
first_meas = stair["env"]["when_kst"]
chk(2, "prespec 동결 < 첫 측정 · sha256 불변", f"{pre['frozen_at_kst']} < {first_meas} · {stair['prespec_sha256'][:16]}",
    f"{pre_sha[:16]}", pre_sha == stair["prespec_sha256"] and pre["frozen_at_kst"].replace("T", " ")[:19] < first_meas[:19])

# 3 선형성
chk(3, "선형성 3점 상대 산포 ≤ 10%", "≤ 0.10", f"{stair['u_wall_stats']['relative_spread']:.6f}", stair["linearity_pass"])

# 4·5·6 결정적 드라이런
if dec and dec.get("result"):
    r = dec["result"]
    chk(4, "실현 참조분포 = 2 × 동전 수", f"{2*r['n_coin_vectors']}", f"{r['n_permutation_values']}",
        r["n_permutation_values"] == 2 * r["n_coin_vectors"])
    chk(5, "여집합 항등식 감사 실패 0", "0", f"{r['complement_audit']['failures']}", r["complement_audit"]["failures"] == 0)
    chk(6, "SE_MC 식 축자 + p 병기", "both present", f"p={r['p_two_sided']:.6f} SE={r['se_mc']:.6g}",
        bool(r.get("se_mc_formula")) and r.get("p_two_sided") is not None)
else:
    for n, t in ((4, "실현 참조분포 = 2 × 동전 수"), (5, "여집합 항등식 감사 실패 0"), (6, "SE_MC 식 축자 + p 병기")):
        chk(n, t, "결정적 드라이런 산출", "미완(캡·중단)", False)

# 7 시드 파생 · 교집합 0
af = set()
for c in rc.cells_spec():
    for rr in range(c["R"]):
        af.add(rc.rep_seed_of(c["scenario"], c["variant"], c["gi"] if "gi" in c else c["grid_index"], rr))
conf = rc.confirmatory_seed_space()
newseeds = set(int(v) for v in pre["seed_rule"]["stair_seeds"].values()) | {int(pre["seed_rule"]["decisive_seed"])}
chk(7, "시드 결정적 파생 · 확증/AF 13,200 교집합 0", "0 · 0 · |AF|=13200",
    f"{len(newseeds & conf)} · {len(newseeds & af)} · |AF|={len(af)}",
    not (newseeds & conf) and not (newseeds & af) and len(af) == 13200)

# 8 예측 100% 합성
c8 = (stair.get("confirmatory_predictions_loaded") is False
      and (dec is None or dec.get("confirmatory_predictions_loaded") is False))
chk(8, "confirmatory_predictions_loaded false", "false", "false" if c8 else "true/missing", c8)

# 9 AST 스캔
scan = rv.ast_scan(["v3_Multimodal/src/b_dryrun.py"])["v3_Multimodal/src/b_dryrun.py"]
chk(9, "AST — 데이터 경로 master_X·master_Y 뿐 · 금지리터럴 0",
    "data_literals ⊆ {master_X,master_Y} · forbidden 0",
    f"{scan['data_file_literals']} · forbidden {scan['forbidden_literals']}",
    scan["data_literals_only_allowed"] and not scan["forbidden_literals"])

# 10 sealed
snap = rc.sealed_stat_snapshot()
b = base["sealed"]
chk(10, "_sealed stat-only 착수=종료 · guard 275/291",
    f"{b['n_files_excl_access_log']}/{b['n_files_all']} · {b['snapshot_sha256'][:16]}",
    f"{snap['n_files_excl_access_log']}/{snap['n_files_all']} · {snap['snapshot_sha256'][:16]}",
    snap["snapshot_sha256"] == b["snapshot_sha256"] and snap["n_files_all"] == 291
    and snap["n_files_excl_access_log"] == 275)

# 11 동결 모듈 0바이트
fb = rc.freeze_baseline(); bf = base["freeze_baseline"]
same = (fb["sap_modules"] == bf["sap_modules"] and fb["other"] == bf["other"])
mani = fb["other"]["experiments/sap/manifest.json"][:16]
sapv = J(os.path.join(ROOT, "experiments", "sap", "manifest.json"))["sap_version"]
chk(11, "동결 11모듈 + AC4 + AD2 0바이트 · manifest sha16 · sap_version",
    "동일 · 756d485feb4715e9 · 1.1", f"{'동일' if same else '변경'} · {mani} · {sapv}",
    same and mani == "756d485feb4715e9" and sapv == "1.1")

# 12 rqint.py 0바이트
rq = sha(os.path.join(ROOT, "v3_Multimodal", "src", "sap", "rqint.py"))
chk(12, "sap/rqint.py 0바이트 (B_DEFINITION_STATUS 무수정)",
    bf["other"]["v3_Multimodal/src/sap/rqint.py"][:16], rq[:16],
    rq == bf["other"]["v3_Multimodal/src/sap/rqint.py"])

# 13 docs/33
import doc_numbering as dn
p33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
t33 = open(p33, encoding="utf-8").read()
pre33 = base["docs"]["docs/33_prereg_deviation_log.md"]
raw33 = open(p33, "rb").read()
prefix_same = hashlib.sha256(raw33[:pre33["size"]]).hexdigest() == pre33["sha256"]
dup = dn.assert_no_duplicate_item_numbers(p33)
last_no = dn.item_numbers(t33)[-1]
chk(13, "docs/33 접두사 바이트 동일 · 삭제 0 · 번호 실측 · 중복 assert",
    f"prefix {pre33['size']}B 동일 · 최종 항목번호 50 · dup {{16:2}} (기존 허용) · unexpected {{}}",
    f"prefix {'동일' if prefix_same else '상이'} · 최종 항목번호 {last_no} · dup {dup['duplicates']} · "
    f"unexpected {dup['unexpected']}",
    prefix_same and len(raw33) > pre33["size"] and last_no == 50 and dup["pass"])

# 14 docs/45
p45 = os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")
pre45 = base["docs"]["docs/45_research_integrity_ledger.md"]
ins = J(os.path.join(OUT, "doc_inserts.json")) if os.path.exists(os.path.join(OUT, "doc_inserts.json")) else None
t45 = open(p45, encoding="utf-8").read()
ok14 = False; got14 = "미기입"
if ins:
    # 삽입분 = §2 표 1행(row45) + §5 문서이력 1행(hist45) + 그 뒤 공백 1행.
    # 행 단위로 정확히 제거해야 개행까지 원상복구된다.
    row45, hist45 = ins["docs45_inserted_lines"]
    ls = t45.split("\n")
    i_h = ls.index(hist45)
    assert ls[i_h + 1] == "", repr(ls[i_h + 1])
    del ls[i_h:i_h + 2]
    i_r = ls.index(row45)
    del ls[i_r]
    restored = "\n".join(ls)
    got14 = hashlib.sha256(restored.encode()).hexdigest()[:16]
    ok14 = (hashlib.sha256(restored.encode()).hexdigest() == pre45["sha256"]
            and len(restored.encode()) == pre45["size"])
chk(14, "docs/45 삽입행 제거 시 착수 sha256 복원", pre45["sha256"][:16], got14, ok14)

# 15 ledger
led = J(os.path.join(ROOT, "experiments", "provenance", "ledger.json"))
chk(15, "ledger 목표치 · 기존 entry 불변",
    "keys 11 · timeline 48 · auth 25 · corr 22 · first_look 6",
    f"keys {len(led)} · timeline {len(led['timeline'])} · auth {len(led['authoritative_sources'])} · "
    f"corr {len(led['correspondence'])} · first_look {len(led['first_look_register'])}",
    len(led) == 11 and len(led["timeline"]) == 48 and len(led["authoritative_sources"]) == 25
    and len(led["correspondence"]) == 22 and len(led["first_look_register"]) == 6)

# 16 B 동결·확정 선언 0
BAD = ("B 를 동결", "B 확정한다", "B = 100,000 으로 동결", "B 동결 완료", "B_DEFINITION_STATUS = ")
newtext = ""
for p in [os.path.join(OUT, "stair.json"), pre_p] + ([dec_p] if dec else []):
    newtext += open(p, encoding="utf-8").read()
hits = [b for b in BAD if b in newtext]
chk(16, "`B` 동결·확정 선언 0건(문자열 스캔)", "0", f"{hits}", not hits)

# 17 개봉 플래그 — 선언 + 소스 실측(호출 0건)
integ = J(os.path.join(OUT, "integrity.json"))
bsrc = open(os.path.join(ROOT, "v3_Multimodal", "src", "b_dryrun.py"), encoding="utf-8").read()
calls = {k: bsrc.count(k) for k in ("emit_sign", "open_sealed", "decision.py", "decision import",
                                    "from sap import decision", "sap.decision")}
ok17 = (integ["unblinding_performed"] is False and integ["gin_start_still_blocked"] is True
        and all(v == 0 for v in calls.values()))
chk(17, "unblinding_performed false · gin_start_still_blocked true · emit_sign 0 · open_sealed 0 · decision.py 0",
    "false / true / 0 / 0 / 0",
    f"{integ['unblinding_performed']} / {integ['gin_start_still_blocked']} / "
    f"emit_sign {calls['emit_sign']} / open_sealed {calls['open_sealed']} / "
    f"decision {calls['sap.decision'] + calls['from sap import decision']}", ok17)

# 18 git
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
cnt = subprocess.run(["git", "rev-list", "--count", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
chk(18, "git HEAD·커밋 불변 · commit/push 0", "566f487… · 21", f"{head[:7]} · {cnt}",
    head.startswith("566f487") and cnt == "21")

out = {"rows": rows, "n_pass": sum(1 for r in rows if r["pass"]), "n_total": len(rows),
       "all_pass": all(r["pass"] for r in rows)}
json.dump(out, open(os.path.join(OUT, "verify.json"), "w"), ensure_ascii=False, indent=2)
for r in rows:
    print(f"{r['no']:>2}. {'PASS' if r['pass'] else 'FAIL'} | {r['item']} | 기대={r['expect']} | 실측={r['got']}")
print(f"\n{out['n_pass']}/{out['n_total']} PASS")
