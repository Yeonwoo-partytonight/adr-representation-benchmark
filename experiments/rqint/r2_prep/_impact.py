#!/usr/bin/env python3
"""_impact.py — R2P-1 충돌 A·B 정적 영향 분석. 파일 수정 0(가상 해시는 메모리 내 치환)."""
import ast, hashlib, json, os, re, subprocess
from datetime import datetime, timedelta, timezone

ROOT = "<REPO_ROOT>"
KST = timezone(timedelta(hours=9))
OUT = os.path.join(ROOT, "experiments", "rqint", "r2_prep", "impact.json")

def sha(p):
    h = hashlib.sha256()
    with open(os.path.join(ROOT, p), "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

SRC = "v3_Multimodal/src/sap"
man = json.load(open(os.path.join(ROOT, "experiments/sap/manifest.json"), encoding="utf-8"))
MODS = list(man["modules"].keys())

# ── (1) 11모듈 현재 sha256 vs manifest 등재값
modtab = []
for k in MODS:
    p = f"{SRC}/{k}"
    s = sha(p)
    modtab.append({"module": k, "live_sha256": s, "live_sha16": s[:16],
                   "manifest_sha16": man["modules"][k]["sha16"],
                   "match": s[:16] == man["modules"][k]["sha16"],
                   "bytes": os.path.getsize(os.path.join(ROOT, p))})

# ── (2) 충돌 A: freeze.py L581 단독 수정의 가상 해시 (파일 미수정)
fzp = os.path.join(ROOT, SRC, "freeze.py")
b = open(fzp, "rb").read()
cur = hashlib.sha256(b).hexdigest()
old_line = ('        "sap_version": "1.1",  # 1.0(docs/41) → 1.1(docs/43 amendment A1~A6)\n').encode()
new_line = ('        "sap_version": "1.2",  # 1.0(docs/41) → 1.1(docs/43 amendment A1~A6)'
            ' → 1.2(docs/55b §8 amendment)\n').encode()
assert b.count(old_line) == 1
va = b.replace(b'"sap_version": "1.1",', b'"sap_version": "1.2",', 1)   # 리터럴 1문자만
vb = b.replace(old_line, new_line, 1)                                    # 리터럴 + 주석
hypo_freeze = {
    "current_sha256": cur, "current_bytes": len(b),
    "variant_literal_only": {"sha256": hashlib.sha256(va).hexdigest(), "bytes": len(va),
                             "diff": '1 char: L581 "1.1" -> "1.2"'},
    "variant_literal_plus_comment": {"sha256": hashlib.sha256(vb).hexdigest(), "bytes": len(vb),
                                     "diff": "L581 literal + trailing comment extended"},
    "note": "가상 산출 — 파일은 0바이트 수정이다. 해시는 메모리 내 치환으로 계산했다.",
}

# ── (3) sap_version 리터럴이 실제로 쓰이는 곳 (freeze.py 내부)
fz = open(fzp, encoding="utf-8").read()
sv_uses = [{"line": i + 1, "text": l.strip()} for i, l in enumerate(fz.splitlines())
           if "sap_version" in l]

# ── (4) MULTIPLICITY_MANIFEST / model_family 가 계산에 쓰이는가 (AST)
def ast_refs(path, name):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    tree = ast.parse(src)
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == name:
            out.append({"kind": "Name", "line": n.lineno, "ctx": type(n.ctx).__name__})
        if isinstance(n, ast.Attribute) and n.attr == name:
            out.append({"kind": "Attribute", "line": n.lineno, "ctx": type(n.ctx).__name__})
    return out

mm_dec = ast_refs(f"{SRC}/decision.py", "MULTIPLICITY_MANIFEST")
mm_fz = ast_refs(f"{SRC}/freeze.py", "MULTIPLICITY_MANIFEST")
hf_dec = ast_refs(f"{SRC}/decision.py", "HOLM_FAMILY")

# freeze.py L372·L650 이 dict 리터럴 값 위치(= 기록)인지 확인
def is_record_only(path, lineno):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            for v in n.values:
                if isinstance(v, ast.Attribute) and v.attr == "MULTIPLICITY_MANIFEST" and v.lineno == lineno:
                    return True
    return False

# 저장소 전역: model_family 를 **읽는** 코드가 있는가
grep = subprocess.run(
    ["grep", "-rn", "model_family", "--include=*.py", "."],
    cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
grep = [g for g in grep if not g.startswith("./.venv/") and not g.startswith("./archive/")
        and not g.startswith("./_to_delete/")]
mf_reads = [g for g in grep if re.search(r'\[["\']model_family|\.get\(["\']model_family|model_family\s*==', g)]

conflict_b = {
    "decision_py_MULTIPLICITY_MANIFEST_refs": mm_dec,
    "freeze_py_MULTIPLICITY_MANIFEST_refs": mm_fz,
    "freeze_L372_is_dict_value_record_only": is_record_only(f"{SRC}/freeze.py", 372),
    "freeze_L650_is_dict_value_record_only": is_record_only(f"{SRC}/freeze.py", 650),
    "holm_uses_HOLM_FAMILY_not_manifest": {
        "HOLM_FAMILY_refs_in_decision_py": hf_dec,
        "holm_signature_reads": "holm(pvalues, alpha) — labels = list(HOLM_FAMILY); "
                                "MULTIPLICITY_MANIFEST 는 참조되지 않는다",
    },
    "repo_wide_model_family_lines": len(grep),
    "repo_wide_model_family_READ_sites": mf_reads,
    "verdict": ("MULTIPLICITY_MANIFEST 는 decision.py 에서 **정의(Store) 1회**뿐이고 읽히지 않는다. "
                "freeze.py 는 L372·L650 에서 **dict 값으로 직렬화**할 때만 Load 한다. "
                "`model_family` 키를 **읽는** 코드는 저장소 전역에 0곳이다. "
                "Holm 계산은 HOLM_FAMILY(라벨 7개)만 쓴다 → D20 의 「비실질 메타데이터」 주장은 코드로 뒷받침된다."),
}

# ── (5) 하드코딩 게이트: sap_version=="1.1" / manifest sha16 을 기대하는 곳
def grep_repo(pat):
    r = subprocess.run(["grep", "-rn", "-E", pat, "--include=*.py", "."],
                       cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    return [x for x in r if not x.startswith("./.venv/") and not x.startswith("./archive/")
            and not x.startswith("./_to_delete/")]

gate_sv = grep_repo(r'sap_version.*==\s*"1\.1"|"sap_version_unchanged":\s*"1\.1"|"sap_version":\s*"1\.1"')
gate_mani = grep_repo(r"756d485feb4715e9")

# ── (6) r3_package 복사본 동기화 상태
R3P = "experiments/rqint/r3_package/sap"
r3sync = []
if os.path.isdir(os.path.join(ROOT, R3P)):
    for k in MODS:
        p = f"{R3P}/{k}"
        if os.path.exists(os.path.join(ROOT, p)):
            r3sync.append({"module": k, "sha16": sha(p)[:16],
                           "identical_to_live": sha(p) == sha(f"{SRC}/{k}")})

# ── (7) manifest 재현성: 비결정 필드
nondet = [{"field": "frozen_at_kst", "source": "freeze.py L582 datetime.now(KST)",
           "current": man["frozen_at_kst"]},
          {"field": "versions", "source": "freeze.py L674 sys.version / np.__version__ 등",
           "current": man.get("versions")}]

out = {
    "_doc": "블록 AK(docs/99) R2P-1 — 충돌 A·B 정적 영향 분석. 파일 수정 0 · 계산 0 · 동결 0.",
    "when_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
    "module_hash_table": modtab,
    "module_hash_all_match_manifest": all(x["match"] for x in modtab),
    "conflict_A": {
        "sap_version_literal_lines_in_freeze_py": sv_uses,
        "hypothetical_freeze_py_hashes": hypo_freeze,
        "hardcoded_sap_version_1_1_gates": gate_sv,
        "hardcoded_manifest_sha16_sites": gate_mani,
        "n_hardcoded_manifest_sha16_files": len(set(g.split(":")[0] for g in gate_mani)),
    },
    "conflict_B": conflict_b,
    "r3_package_sap_copies": r3sync,
    "manifest_nondeterministic_fields": nondet,
    "manifest_is_byte_reproducible": False,
    "integrity": {"files_modified": 0, "network_calls": 0, "sealed_read": 0,
                  "freeze_py_executed": False, "decision_py_imported": False},
}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("module_hash_all_match:", out["module_hash_all_match_manifest"])
print("hypothetical freeze.py (literal only):", hypo_freeze["variant_literal_only"]["sha256"][:16])
print("hardcoded sap_version==1.1 gate sites:", len(gate_sv))
print("hardcoded manifest sha16 sites:", len(gate_mani), "files:", out["conflict_A"]["n_hardcoded_manifest_sha16_files"])
print("model_family READ sites:", len(mf_reads))
print("r3_package copies identical:", all(x["identical_to_live"] for x in r3sync), len(r3sync))
