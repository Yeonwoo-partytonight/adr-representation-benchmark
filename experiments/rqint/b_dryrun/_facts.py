#!/usr/bin/env python3
"""docs/97 §1 FACTS registry — 14행 전건 **실측 소스에서 직접** 대조."""
import os, sys, json, re, hashlib, subprocess, statistics as st
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_dryrun")
rows = []
def add(fid, expect, src, got, ok):
    rows.append({"fact_id": fid, "expect": expect, "source": src, "measured": got, "pass": bool(ok)})

# F-R1
p = "experiments/rqint/calibration_summary.json"
v = json.load(open(os.path.join(ROOT, p)))["r1_passed"]
add("F-R1", "r1_passed = true", p, str(v).lower(), v is True)

# F-ORDER
p = "docs/84_rqint_reviewer_response_triage.md"
t84 = open(os.path.join(ROOT, p), encoding="utf-8").read()
L = t84.splitlines()
l159, l161 = L[158].strip(), L[160].strip()
ok = ("전규모 드라이런 벽시계" in l159 and "B = 100,000 vs 50,000 확정" in l159
      and "SAP 1.2 재동결" in l161 and "R2" in l161)
add("F-ORDER", "⑥ = 전규모 드라이런 벽시계 → B 확정, ⑦ = R2 (⑥ 이 ⑦ 보다 앞)",
    f"{p} §5 (L159·L161)", f"L159={l159!r} | L161={l161!r}", ok)

# F-R2SCOPE
m = [l for l in L if l.startswith("| **R2**")]
ok = bool(m) and "구현 코드·난수시드·B·시드집합·대표폴드·실패처리 규칙" in m[0] and "v1.2 로 동결" in m[0]
add("F-R2SCOPE", "R2 동결 대상에 `B` 포함 (축자)", f"{p} §2 표 R2 행", m[0][:160] if m else "행 없음", ok)

# F-D15
d15 = [l for l in L if l.startswith("| D15 |")]
ok = bool(d15) and "B = 100,000" in d15[0] and "24h 초과 시에만 50,000 으로 하향" in d15[0] \
     and "GIN 예측 생성 이전에" in d15[0] and "몬테카를로 SE 병기" in d15[0]
add("F-D15", "B=100,000 · 24h 초과 시에만 50,000 하향 · GIN 예측 생성 이전 판단 · MC SE 병기",
    f"{p} §1 D15 행 (L{L.index(d15[0])+1})", d15[0][:200] if d15 else "행 없음", ok)

# F-BDEF · F-SERIAL · F-PAIRC
p = "v3_Multimodal/src/sap/rqint.py"
src = open(os.path.join(ROOT, p), encoding="utf-8").read()
sl = src.splitlines()
bd = "\n".join(sl[62:64])
ok = ("still_unspecified" in bd and "n_coin_vectors" in bd and "n_permutation_values" in bd
      and "SAP 1.2 에서 확정 필요" in "\n".join(sl[62:65]))
add("F-BDEF", "B_DEFINITION_STATUS = still_unspecified …", f"{p} L63–64", bd.strip()[:180], ok)

ok = ("for b in range(n_coin_vectors):" in src
      and not re.search(r"def rqint_test\([^)]*n_jobs|workers|processes", src))
sig = src[src.index("def rqint_test("):src.index("def rqint_test(") + 200].splitlines()[0:3]
add("F-SERIAL", "rqint_test 직렬 루프 · 병렬 파라미터 없음", f"{p} def rqint_test 시그니처 + 루프",
    " ".join(x.strip() for x in sig), ok)

ok = "참조분포 크기 = 2 × n_coin_vectors, 평가 비용은 절반" in src
add("F-PAIRC", "pair_complement=True → 참조분포 = 2 × n_coin_vectors, 평가 비용 절반",
    f"{p} rqint_test docstring", "축자 존재" if ok else "축자 부재", ok)

# F-C4UNIT
p = "experiments/rqint/_ckpt/calibration_C4_tau0.01.jsonl"
R = [json.loads(x) for x in open(os.path.join(ROOT, p))]
g = {k: st.median([r[k] for r in R]) for k in
     ("n_coin_vectors", "n_permutation_values", "n_groups_G", "task_seconds",
      "per_permutation_seconds", "threads_limit")}
ok = (g["n_coin_vectors"] == 1000 and g["n_permutation_values"] == 2000 and g["n_groups_G"] == 732
      and abs(g["task_seconds"] - 1508.05) < 0.01 and abs(g["per_permutation_seconds"] - 1.506339) < 1e-6
      and g["threads_limit"] == 1)
add("F-C4UNIT", "n_coin 1000 · n_perm 2000 · G 732 · task_s med 1508.05 · pps med 1.506339 · threads 1",
    p, json.dumps(g), ok)

# F-C4CTX
p = "experiments/rqint/calibration_sessions.jsonl"
S = [json.loads(x) for x in open(os.path.join(ROOT, p))]
w = sorted({r.get("workers") for r in S
            if r.get("cell") == "C4:tau0.01" and r.get("workers") is not None})
w_all = sorted({r.get("workers") for r in S if r.get("workers") is not None})
add("F-C4CTX", "단가는 18워커 동시 실행 하 측정치(단독 실행의 상한 성격)",
    f"{p} 해당 셀(C4:tau0.01) `workers`",
    f"C4:tau0.01 workers = {w} (전 세션 distinct = {w_all} — 2 는 C0:prop 스모크 세션)",
    w == [18])

# F-REVCOST
ok = ("B=100,000 = 단일코어 약 30시간" in t84.replace("\n", " ")
      or "B=100,000 = 단일코어 약 30시간,\n6프로세스 약 5시간" in t84) and "1.08초/코어" in t84
add("F-REVCOST", "검토자 §9-2 단일코어 약 30h / 6프로세스 약 5h → 함의 단가 ≈1.08 s/동전",
    "docs/84 「비용 개산」 문단 (L100–102)", "축자 존재" if ok else "축자 부재", ok)

# F-MANI16
p = "experiments/sap/manifest.json"
h = hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest()[:16]
sv = json.load(open(os.path.join(ROOT, p)))["sap_version"]
add("F-MANI16", "sha16 756d485feb4715e9 · sap_version 1.1", p, f"{h} · {sv}",
    h == "756d485feb4715e9" and sv == "1.1")

# F-SEAL
n_all = int(subprocess.run("find experiments/runs -path '*_sealed*' -type f | wc -l",
                           shell=True, cwd=ROOT, capture_output=True, text=True).stdout.strip())
n_ex = int(subprocess.run("find experiments/runs -path '*_sealed*' -type f ! -name access.log | wc -l",
                          shell=True, cwd=ROOT, capture_output=True, text=True).stdout.strip())
add("F-SEAL", "291 (전 파일) / 275 (access.log 제외)", "find experiments/runs -path '*_sealed*' -type f",
    f"{n_all} / {n_ex}", n_all == 291 and n_ex == 275)

# F-GIT
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
cnt = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
add("F-GIT", "HEAD 566f487 · 커밋 21", "git rev-parse HEAD · git rev-list --count HEAD",
    f"{head[:7]} · {cnt}", head.startswith("566f487") and cnt == "21")

# F-LEDGER
p = "experiments/provenance/ledger.json"
led = json.load(open(os.path.join(ROOT, p)))
g = {"keys": len(led), "timeline": len(led["timeline"]), "correspondence": len(led["correspondence"]),
     "external_reviews": len(led["external_reviews"]), "first_look_register": len(led["first_look_register"]),
     "authoritative_sources": len(led["authoritative_sources"])}
ok = g == {"keys": 11, "timeline": 47, "correspondence": 22, "external_reviews": 6,
           "first_look_register": 6, "authoritative_sources": 24}
add("F-LEDGER", "키 11 · timeline 47 · correspondence 22 · external_reviews 6 · first_look 6 · auth 24",
    p, json.dumps(g), ok)

out = {"rows": rows, "n_pass": sum(1 for r in rows if r["pass"]), "n_total": len(rows),
       "all_facts_pass": all(r["pass"] for r in rows)}
json.dump(out, open(os.path.join(OUT, "facts.json"), "w"), ensure_ascii=False, indent=2)
for r in rows:
    print(f"{'PASS' if r['pass'] else 'FAIL'} {r['fact_id']:<10} src={r['source']}")
    if not r["pass"]:
        print(f"     기대={r['expect']}\n     실측={r['measured']}")
print(f"\n{out['n_pass']}/{out['n_total']} PASS · all_facts_pass={out['all_facts_pass']}")
