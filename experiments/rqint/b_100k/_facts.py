#!/usr/bin/env python3
"""[블록 AJ · docs/98 §2] FACTS registry 14행 — 착수 시 전건 **실측 대조**.

기억값·타 문서 전재 금지. 각 행은 지정된 실측 소스에서 직접 읽어 비교한다.
불일치 1건이라도 있으면 all_facts_pass = false → 작업하지 않고 보류.
"""
import os, sys, json, hashlib, subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_100k")

def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def rd(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()

rows = []
def add(fid, expect, source, actual, ok):
    rows.append({"fact_id": fid, "expect": expect, "source": source,
                 "actual": actual, "pass": bool(ok)})

# ── F-PRESPEC ─────────────────────────────────────────────────────────────
P_PRE = os.path.join(ROOT, "v3_Multimodal", "config", "b_dryrun_prespec.json")
pre = json.load(open(P_PRE, encoding="utf-8"))
s_pre = sha(P_PRE)
E_PRE = "9a2545eb0d897f304f23350e1363415bc9642a7895fca87b8306f1eadcfa7939"
E_FROZ = "2026-08-22T00:56:14+09:00"
add("F-PRESPEC", f"sha256 {E_PRE} · frozen_at_kst {E_FROZ}",
    "v3_Multimodal/config/b_dryrun_prespec.json",
    f"sha256 {s_pre} · frozen_at_kst {pre.get('frozen_at_kst')}",
    s_pre == E_PRE and pre.get("frozen_at_kst") == E_FROZ)

# ── F-POLICY ──────────────────────────────────────────────────────────────
ep = pre["extrapolation_policy"]
E_RULE = "밴드 안이면 외삽 금지 → 실주행 + 24h 하드 캡으로 판정한다."
add("F-POLICY", f"band_hours [18.0, 30.0] · rule_inside_band 축자 = \"{E_RULE}\"",
    "동 파일 extrapolation_policy",
    f"band_hours {ep['band_hours']} · rule_inside_band = \"{ep['rule_inside_band']}\"",
    ep["band_hours"] == [18.0, 30.0] and ep["rule_inside_band"] == E_RULE)

# ── F-CONTIN ──────────────────────────────────────────────────────────────
ct = pre["contingency_if_premise_fails"]
a3 = [a for a in ct["action"] if a.startswith("③")]
ok3 = (len(a3) == 1 and "상신 사항으로 보고" in a3[0]
       and "자체 판단으로 구성을 바꾸지 않는다" in a3[0])
add("F-CONTIN", "action③ 축자(상신 사항 · 자체 구성 변경 금지)",
    "동 파일 contingency_if_premise_fails",
    (a3[0] if a3 else "(부재)"), ok3)

# ── F-AI50K / F-AIOBS ─────────────────────────────────────────────────────
P_DEC = os.path.join(ROOT, "experiments", "rqint", "b_dryrun", "decisive.json")
dec = json.load(open(P_DEC, encoding="utf-8"))
r = dec["result"]
E50 = {"n_coin_vectors": 50000, "n_permutation_values": 100000,
       "wall_seconds": 35585.03730940819,
       "per_permutation_seconds": 0.6976782551174681,
       "complement_audit_seconds": 697.7373139844276}
got50 = {k: r[k] for k in E50}
add("F-AI50K",
    "동전 50,000 · 참조분포 100,000 · wall_seconds 35585.03730940819 · "
    "u_loop_per_coin 0.6976782551174681 · complement_audit_seconds 697.7373139844276",
    "experiments/rqint/b_dryrun/decisive.json result",
    json.dumps(got50, ensure_ascii=False), got50 == E50)

EOBS = {"T_obs": 0.0031802114140302242, "delta_rf": 0.00038510137913283504,
        "delta_gin": -0.002795110034897389, "count_abs_ge_obs": 67262,
        "rep_seed": 860260813, "coin_seed": 1760260813}
gotobs = {k: r[k] for k in EOBS}
add("F-AIOBS",
    "T_obs 0.0031802114140302242 · delta_rf 0.00038510137913283504 · "
    "delta_gin -0.002795110034897389 · count_abs_ge_obs 67262 · "
    "rep_seed 860260813 · coin_seed 1760260813",
    "동 파일 result", json.dumps(gotobs, ensure_ascii=False), gotobs == EOBS)

# ── F-AIUNIT ──────────────────────────────────────────────────────────────
st = json.load(open(os.path.join(ROOT, "experiments", "rqint", "b_dryrun", "stair.json"),
                    encoding="utf-8"))
med = st["u_wall_stats"]["median"]; rsp = st["u_wall_stats"]["relative_spread"]
add("F-AIUNIT", "계단 û 중앙값 0.694588 · 선형성 상대 산포 0.031628",
    "experiments/rqint/b_dryrun/stair.json",
    f"median {med!r} · relative_spread {rsp!r}",
    round(med, 6) == 0.694588 and round(rsp, 6) == 0.031628)

# ── F-D15 ─────────────────────────────────────────────────────────────────
d84 = rd("docs/84_rqint_reviewer_response_triage.md")
l_d15 = [l for l in d84.splitlines() if l.startswith("| D15 ")]
E_D15_PARTS = ["**B = 100,000**", "24h 초과 시에만 50,000 으로 하향",
               "**GIN 예측 생성 이전에** 판단", "몬테카를로 SE 병기"]
ok_d15 = len(l_d15) == 1 and all(p in l_d15[0] for p in E_D15_PARTS)
add("F-D15", "축자 4요소(B=100,000 · 24h 초과 시에만 50,000 하향 · GIN 예측 생성 이전 판단 · MC SE 병기)",
    "docs/84 §1 D15 행", (l_d15[0][:220] if l_d15 else "(부재)"), ok_d15)

# ── F-BDEF / F-SERIAL / F-RQINT16 ─────────────────────────────────────────
P_RQ = os.path.join(ROOT, "v3_Multimodal", "src", "sap", "rqint.py")
rq = open(P_RQ, encoding="utf-8").read()
rq_lines = rq.splitlines()
bdef_line = [i + 1 for i, l in enumerate(rq_lines) if l.startswith("B_DEFINITION_STATUS")]
ok_bdef = bool(bdef_line) and 'B_DEFINITION_STATUS = ("still_unspecified' in rq
add("F-BDEF", "B_DEFINITION_STATUS = still_unspecified …",
    f"v3_Multimodal/src/sap/rqint.py L{bdef_line[0] if bdef_line else '?'}–",
    " ".join(rq_lines[bdef_line[0] - 1: bdef_line[0] + 1]).strip()[:180] if bdef_line else "(부재)",
    ok_bdef)

sig_i = [i for i, l in enumerate(rq_lines) if l.startswith("def rqint_test(")]
sig = " ".join(rq_lines[sig_i[0]:sig_i[0] + 3]) if sig_i else ""
PARALLEL = ("n_jobs", "workers", "n_workers", "Pool", "ProcessPool", "ThreadPool",
            "concurrent.futures", "joblib")
body_from = rq[rq.index("def rqint_test("):]
body = body_from[:body_from.index("\ndef ", 1)] if "\ndef " in body_from[1:] else body_from
found_par = [k for k in PARALLEL if k in body]
ok_ser = ("for b in range(n_coin_vectors):" in body) and not found_par
add("F-SERIAL", "rqint_test 직렬 루프 · 병렬 파라미터 없음", "동 파일 def rqint_test",
    f"sig={sig[:120]} · serial_loop={'for b in range(n_coin_vectors):' in body} · parallel_tokens={found_par}",
    ok_ser)

s_rq16 = sha(P_RQ)[:16]
add("F-RQINT16", "sha16 eb842bc98140e9c5", "동 파일", s_rq16, s_rq16 == "eb842bc98140e9c5")

# ── F-MANI16 ──────────────────────────────────────────────────────────────
P_MAN = os.path.join(ROOT, "experiments", "sap", "manifest.json")
s_man16 = sha(P_MAN)[:16]
sv = json.load(open(P_MAN, encoding="utf-8"))["sap_version"]
add("F-MANI16", "manifest sha16 756d485feb4715e9 · sap_version 1.1",
    "experiments/sap/manifest.json", f"{s_man16} · {sv}",
    s_man16 == "756d485feb4715e9" and str(sv) == "1.1")

# ── F-SEAL ────────────────────────────────────────────────────────────────
sealed = subprocess.run(["find", "experiments/runs", "-path", "*_sealed*", "-type", "f"],
                        cwd=ROOT, capture_output=True, text=True).stdout.split()
n_all = len(sealed)
n_ex = len([p for p in sealed if os.path.basename(p) != "access.log"])
add("F-SEAL", "291 / 275(access.log 제외)",
    "find experiments/runs -path '*_sealed*' -type f", f"{n_all} / {n_ex}",
    n_all == 291 and n_ex == 275)

# ── F-GIT ─────────────────────────────────────────────────────────────────
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                      capture_output=True, text=True).stdout.strip()
ncommit = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
add("F-GIT", "HEAD 566f487 · 커밋 21", "git rev-parse HEAD · git rev-list --count HEAD",
    f"{head[:7]} · {ncommit}", head.startswith("566f487") and ncommit == "21")

# ── F-LEDGER ──────────────────────────────────────────────────────────────
led = json.load(open(os.path.join(ROOT, "experiments", "provenance", "ledger.json"),
                     encoding="utf-8"))
gotl = {"keys": len(led), "timeline": len(led["timeline"]),
        "correspondence": len(led["correspondence"]),
        "external_reviews": len(led["external_reviews"]),
        "first_look_register": len(led["first_look_register"]),
        "authoritative_sources": len(led["authoritative_sources"])}
El = {"keys": 11, "timeline": 48, "correspondence": 22, "external_reviews": 6,
      "first_look_register": 6, "authoritative_sources": 25}
add("F-LEDGER", json.dumps(El, ensure_ascii=False), "experiments/provenance/ledger.json",
    json.dumps(gotl, ensure_ascii=False), gotl == El)

out = {"block": "AJ (docs/98)", "n_rows": len(rows),
       "n_pass": sum(r["pass"] for r in rows),
       "all_facts_pass": all(r["pass"] for r in rows), "rows": rows}
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "facts.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
for r in rows:
    print(("✅" if r["pass"] else "❌"), r["fact_id"], "|", str(r["actual"])[:150])
print(f"\n{out['n_pass']}/{out['n_rows']} PASS · all_facts_pass = {out['all_facts_pass']}")
sys.exit(0 if out["all_facts_pass"] else 1)
