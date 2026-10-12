#!/usr/bin/env python3
"""[블록 AJ] 종료검증 — docs/98 §4 (16항). 본런 산출을 읽어 기계 판정한다.

★ A21 정신 계승 — 본 스크립트는 러너(`b_100k_run.py`)를 import 하지 않고
  산출 파일과 정본 대조 함수만 읽어 **독립적으로** 재판정한다.
"""
import os, sys, json, hashlib, subprocess, importlib.util
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_100k")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
J = lambda p: json.load(open(p, encoding="utf-8"))

def _load(name, rel):
    s = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "v3_Multimodal", "src", rel))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
rc = _load("rc", "rqint_calibration.py")
rv = _load("rv", "rqint_calibration_verify.py")

base = J(os.path.join(OUT, "_baseline_snapshot.json"))
run_p = os.path.join(OUT, "run.json")
run = J(run_p) if os.path.exists(run_p) else None
r = run["result"] if run and run.get("result") else None

rows = []
def chk(no, name, expect, got, ok):
    rows.append({"no": no, "item": name, "expect": expect, "got": got, "pass": bool(ok)})

# 1 FACTS 14행
f = J(os.path.join(OUT, "facts.json"))
chk(1, "FACTS 14행 전건 일치", "14/14 pass",
    f"{sum(1 for x in f['rows'] if x['pass'])}/{len(f['rows'])}",
    all(x["pass"] for x in f["rows"]) and len(f["rows"]) == 14)

# 2 델타 prespec 동결 < 실주행 시작 · sha256 불변
pre_p = os.path.join(ROOT, "v3_Multimodal", "config", "b_100k_prespec.json")
pre, pre_sha = J(pre_p), sha(pre_p)
started = run["started_kst"] if run else ""
ok2 = (run is not None and pre_sha == run["prespec_sha256"]
       and pre["frozen_at_kst"][:19] < started[:19])
chk(2, "델타 prespec 동결 < 실주행 시작 · 이후 sha256 불변",
    f"{pre['frozen_at_kst']} < {started} · {pre_sha[:16]}",
    f"{pre_sha[:16]} · run.prespec_sha256 {run['prespec_sha256'][:16] if run else '?'}", ok2)

# 3 블록 AI 산출물 4종 0바이트
AI4 = list(base["block_AI_artifacts"])
now4 = {p: {"sha256": sha(os.path.join(ROOT, p)),
            "size": os.path.getsize(os.path.join(ROOT, p))} for p in AI4}
chk(3, "블록 AI 산출물 4종 0바이트", "4/4 동일",
    f"{sum(1 for p in AI4 if now4[p] == base['block_AI_artifacts'][p])}/4",
    now4 == base["block_AI_artifacts"])

# 4 b=50,000 러닝 카운트 = 67,262  (★ 산출 배열에서 독립 재계산)
ok4, got4 = False, "미완"
if r:
    import numpy as np
    ts = np.load(os.path.join(OUT, "t_star.npy"))
    from sap import rqint as _sr                      # 동결 모듈 — 읽기만(수정 0)
    eps = _sr._EPS
    ts50 = ts[:50000]
    c50 = int(np.sum(np.abs(np.concatenate([ts50, -ts50])) >= abs(float(r["T_obs"])) - eps))
    got4 = f"러너 {r['checkpoint_b50000']['count_abs_ge_obs']} · 독립재계산 {c50}"
    ok4 = (c50 == 67262 == r["checkpoint_b50000"]["count_abs_ge_obs"]
           and len(ts) == r["n_coin_vectors"])
chk(4, "b=50,000 러닝 카운트 = 67,262 (독립 재계산)", "67262", got4, ok4)

# 5 관측통계량 = F-AIOBS 바이트 동일
EOBS = {"T_obs": 0.0031802114140302242, "delta_rf": 0.00038510137913283504,
        "delta_gin": -0.002795110034897389}
ok5 = bool(r) and all(repr(r[k]) == repr(v) for k, v in EOBS.items())
chk(5, "T_obs·delta_rf·delta_gin = F-AIOBS 바이트 동일", json.dumps(EOBS),
    json.dumps({k: r[k] for k in EOBS}) if r else "미완", ok5)

# 6 실현 참조분포 = 2 × 동전 수 = 200,000
ok6 = bool(r) and r["n_permutation_values"] == 2 * r["n_coin_vectors"] == 200000
chk(6, "실현 참조분포 = 2 × 동전 수(200,000)", "200000",
    str(r["n_permutation_values"]) if r else "미완", ok6)

# 7 여집합 항등식 감사 실패 0
ok7 = bool(r) and r["complement_audit"]["failures"] == 0
chk(7, "여집합 항등식 감사 실패 0", "0",
    (f"{r['complement_audit']['draws_checked']} draw · 실패 {r['complement_audit']['failures']} · "
     f"max_abs_dev {r['complement_audit']['max_abs_dev']}") if r else "미완", ok7)

# 8 SE_MC 식 축자 + 양 해석 병기
se_p = os.path.join(OUT, "se_comparison.json")
ok8, got8 = False, "미생성"
if os.path.exists(se_p):
    se = J(se_p)
    ok8 = (se["formula_verbatim"] == "SE_MC = sqrt( p·(1−p) / n_permutation_values )"
           and se["interpretation_a"]["se_mc"] > 0 and se["interpretation_b"]["se_mc"] > 0
           and se["se_ratio_matches_1_over_sqrt2_within_1pct"])
    got8 = (f"(가) {se['interpretation_a']['se_mc']:.6g} · (나) {se['interpretation_b']['se_mc']:.6g} · "
            f"비 {se['se_ratio_a_over_b']:.5f} (1/√2 = {se['one_over_sqrt2']:.5f})")
chk(8, "SE_MC 식 축자 + 양 해석 병기", "식 축자 일치 · 양쪽 존재 · 비 ≈ 1/√2", got8, ok8)

# 9 예측 100% 합성 · 효과 주입 0
ok9 = bool(run) and run["confirmatory_predictions_loaded"] is False and run["effect_injection"] == 0.0
chk(9, "예측 100% 합성 · 효과 주입 0", "false · 0.0",
    f"{run['confirmatory_predictions_loaded']} · {run['effect_injection']}" if run else "미완", ok9)

# 10 AST 스캔
#    ★ `t_star.npy` 는 **본 블록이 쓰는 산출물**(합성 귀무 통계량 배열)인데 `ast_scan` 은
#      확장자(.npy ∈ DATA_EXT)만 보고 `data_file_literals` 로 분류한다. 따라서
#      ⓐ 금지 리터럴 0 ⓑ **입력** 데이터 리터럴 ⊆ {master_X, master_Y}
#      ⓒ `t_star.npy` 가 `np.save` 로만 쓰이고 러너가 그것을 **읽지 않음**(np.load 0건)
#      세 조건으로 나눠 판정한다. 판정을 느슨하게 한 게 아니라 **분해해 강화**한 것이다.
scan = rv.ast_scan(["v3_Multimodal/src/b_100k_run.py"])["v3_Multimodal/src/b_100k_run.py"]
OWN_OUTPUTS = {"t_star.npy"}
input_data_lits = [x for x in scan["data_file_literals"] if x not in OWN_OUTPUTS]
src10 = open(os.path.join(ROOT, "v3_Multimodal", "src", "b_100k_run.py"), encoding="utf-8").read()
save_only = (src10.count("t_star.npy") == 1 and "np.save(os.path.join(OUT, \"t_star.npy\")" in src10
             and "np.load" not in src10)
ok10 = (not scan["forbidden_literals"]
        and set(input_data_lits) <= {"master_X.parquet", "master_Y.parquet"}
        and save_only)
chk(10, "AST — 입력 데이터 경로 master_X·master_Y 뿐 · 금지리터럴 0 · 산출 t_star.npy 는 쓰기전용",
    "input_data_literals ⊆ {master_X,master_Y} · forbidden 0 · np.save 전용(np.load 0)",
    f"input {input_data_lits} · own_output {sorted(set(scan['data_file_literals']) & OWN_OUTPUTS)} · "
    f"forbidden {scan['forbidden_literals']} · save_only {save_only}", ok10)

# 11 _sealed stat-only 착수=종료 · guard 275/291
snap = rc.sealed_stat_snapshot(); b11 = base["rc_sealed"]
chk(11, "_sealed stat-only 착수=종료 동일 · guard 275/291",
    f"{b11['n_files_excl_access_log']}/{b11['n_files_all']} · {b11['snapshot_sha256'][:16]}",
    f"{snap['n_files_excl_access_log']}/{snap['n_files_all']} · {snap['snapshot_sha256'][:16]}",
    snap["snapshot_sha256"] == b11["snapshot_sha256"] and snap["n_files_all"] == 291
    and snap["n_files_excl_access_log"] == 275)

# 12 동결 11모듈 + AC4 + AD2 0바이트 · manifest · sap_version · sap/rqint.py
fb, bf = rc.freeze_baseline(), base["rc_freeze"]
same = (fb["sap_modules"] == bf["sap_modules"] and fb["other"] == bf["other"])
mani = fb["other"]["experiments/sap/manifest.json"][:16]
sapv = J(os.path.join(ROOT, "experiments", "sap", "manifest.json"))["sap_version"]
rq16 = sha(os.path.join(ROOT, "v3_Multimodal", "src", "sap", "rqint.py"))[:16]
chk(12, "동결 11모듈 + AC4 + AD2 0바이트 · manifest sha16 · sap_version · sap/rqint.py",
    "동일 · 756d485feb4715e9 · 1.1 · eb842bc98140e9c5",
    f"{'동일' if same else '변경'} · {mani} · {sapv} · {rq16}",
    same and mani == "756d485feb4715e9" and sapv == "1.1" and rq16 == "eb842bc98140e9c5")

# 13 docs/33
import doc_numbering as dn
p33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
pre33 = base["docs"]["docs/33_prereg_deviation_log.md"]
raw33 = open(p33, "rb").read()
prefix_same = hashlib.sha256(raw33[:pre33["size"]]).hexdigest() == pre33["sha256"]
dup = dn.assert_no_duplicate_item_numbers(p33)
nums = dn.item_numbers(open(p33, encoding="utf-8").read())
ins_p = os.path.join(OUT, "doc_inserts.json")
exp_no = J(ins_p)["docs33_item_number"] if os.path.exists(ins_p) else None
chk(13, "docs/33 접두사 바이트 동일 · 삭제 0 · 번호 실측 · 중복 assert",
    f"prefix {pre33['size']}B 동일 · 최종 항목번호 {exp_no}(실측) · unexpected {{}}",
    f"prefix {'동일' if prefix_same else '상이'} · 최종 항목번호 {nums[-1]} · "
    f"dup {dup['duplicates']} · unexpected {dup['unexpected']}",
    prefix_same and len(raw33) > pre33["size"] and dup["pass"] and nums[-1] == exp_no)

# 14 docs/45 삽입행 제거 시 착수 sha256 복원
p45 = os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")
pre45 = base["docs"]["docs/45_research_integrity_ledger.md"]
ok14, got14 = False, "미기입"
if os.path.exists(ins_p):
    row45, hist45 = J(ins_p)["docs45_inserted_lines"]
    ls = open(p45, encoding="utf-8").read().split("\n")
    i_h = ls.index(hist45); assert ls[i_h + 1] == ""
    del ls[i_h:i_h + 2]
    i_r = ls.index(row45); del ls[i_r]
    restored = "\n".join(ls)
    got14 = hashlib.sha256(restored.encode()).hexdigest()[:16]
    ok14 = (hashlib.sha256(restored.encode()).hexdigest() == pre45["sha256"]
            and len(restored.encode()) == pre45["size"])
chk(14, "docs/45 삽입행 제거 시 착수 sha256 복원", pre45["sha256"][:16], got14, ok14)

# 15 ledger 목표치 · 기존 entry 불변
led = J(os.path.join(ROOT, "experiments", "provenance", "ledger.json"))
base_led = J(os.path.join(OUT, "_ledger_before.json")) if os.path.exists(
    os.path.join(OUT, "_ledger_before.json")) else None
unchanged = (base_led is not None
             and json.dumps(led["timeline"][:-1], ensure_ascii=False, sort_keys=True)
                 == json.dumps(base_led["timeline"], ensure_ascii=False, sort_keys=True)
             and led["authoritative_sources"][:-1] == base_led["authoritative_sources"])
chk(15, "ledger 목표치(timeline 49 · auth 26) · 기존 entry 불변",
    "keys 11 · timeline 49 · auth 26 · corr 22 · first_look 6 · 기존 entry 불변",
    f"keys {len(led)} · timeline {len(led['timeline'])} · auth {len(led['authoritative_sources'])} · "
    f"corr {len(led['correspondence'])} · first_look {len(led['first_look_register'])} · "
    f"기존 entry {'불변' if unchanged else '변경/미대조'}",
    len(led) == 11 and len(led["timeline"]) == 49 and len(led["authoritative_sources"]) == 26
    and len(led["correspondence"]) == 22 and len(led["first_look_register"]) == 6 and unchanged)

# 16 `B` 정의 채택·동결 선언 0건 + 개봉/네트워크/git
BAD = ("B 를 동결", "B 확정한다", "B 를 채택", "정의를 채택한다", "B 동결 완료",
       "B_DEFINITION_STATUS = ", "채택 확정", "B = 100,000 으로 동결")
newtext = ""
for p in [pre_p, os.path.join(ROOT, "v3_Multimodal", "src", "b_100k_run.py")] + \
         ([run_p] if run else []) + ([se_p] if os.path.exists(se_p) else []):
    newtext += open(p, encoding="utf-8").read()
hits = [b for b in BAD if b in newtext]
integ = J(os.path.join(OUT, "integrity.json"))
src = open(os.path.join(ROOT, "v3_Multimodal", "src", "b_100k_run.py"), encoding="utf-8").read()
calls = {k: src.count(k) for k in ("emit_sign", "open_sealed", "sap.decision",
                                   "from sap import decision", "requests", "urllib", "http")}
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                      text=True).stdout.strip()
cnt = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True,
                     text=True).stdout.strip()
ok16 = (not hits and integ["unblinding_performed"] is False
        and integ["gin_start_still_blocked"] is True
        and integ["B_definition_adopted_by_this_block"] is False
        and all(calls[k] == 0 for k in calls)
        and head.startswith("566f487") and cnt == "21")
chk(16, "`B` 정의 채택·동결 선언 0건 · 개봉 0 · 네트워크 0 · HEAD·커밋 불변 · commit/push 0",
    "hits [] · false/true · 전 호출 0 · 566f487 · 21",
    f"hits {hits} · unblinding {integ['unblinding_performed']} · gin_blocked {integ['gin_start_still_blocked']} · "
    f"adopted {integ['B_definition_adopted_by_this_block']} · calls {calls} · {head[:7]} · {cnt}", ok16)

out = {"block": "AJ (docs/98)", "rows": rows, "n_pass": sum(1 for x in rows if x["pass"]),
       "n_total": len(rows), "all_pass": all(x["pass"] for x in rows)}
with open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, indent=2)
for x in rows:
    print(f"{x['no']:>2}. {'PASS' if x['pass'] else 'FAIL'} | {x['item']} | 기대={x['expect']} | 실측={x['got']}")
print(f"\n{out['n_pass']}/{out['n_total']} PASS")
