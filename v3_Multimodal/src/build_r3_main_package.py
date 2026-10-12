#!/usr/bin/env python3
"""build_r3_main_package.py — R3 본 드라이런 패키지 생성·로컬 기준값 산출 (블록 AP · docs/104).

서브커맨드 3개. 각자 **자기 산출물이 이미 있으면 exit 4**(1회성).

    --build       AP-2~AP-4  스테이징 20파일 · 패키지 검사 · zip · package_manifest.json
    --local-run   AP-5       zip 을 저장소 밖 임시 디렉터리에 풀어 드라이버 1회 실행 → 로컬 기준값
    --reference   AP-7       r3_main_reference.json

⛔ numpy · sklearn · sap import 0(무거운 계산은 --local-run 의 자식 프로세스에서만).
⛔ 네트워크 0 · 봉인 읽기 0(경로 나열로 개수만) · 저장소 원본 드라이버 직접 실행 0.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True      # 스테이징 canonical.py 를 경로로 로드해도 __pycache__ 가 생기지 않게

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
import zlib
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import compute_lock as CL                                          # noqa: E402

KST = timezone(timedelta(hours=9))

RQINT = os.path.join(ROOT, "experiments", "rqint")
INPUTS = os.path.join(RQINT, "r3_main_package_inputs")
STAGING_PARENT = RQINT
STAGING = os.path.join(RQINT, "r3_main_package")
ZIP_PATH = os.path.join(RQINT, "r3_main_package.zip")
META = os.path.join(RQINT, "r3_main_package_meta")
JUDGE_DST = os.path.join(ROOT, "v3_Multimodal", "src", "r3_judge.py")

MANIFEST_PATH = os.path.join(META, "package_manifest.json")
ENV_LOCAL = os.path.join(META, "env_local_main.json")
AUDIT_LOCAL = os.path.join(META, "audit_r6_local_main.json")
RUNLOG_LOCAL = os.path.join(META, "run_local_main.log")
CORE_LOCAL = os.path.join(META, "numeric_core_local_main.json")
HASHES_LOCAL = os.path.join(META, "package_hashes_local_main.json")
RECORD_LOCAL = os.path.join(META, "local_run_record.json")
REFERENCE_PATH = os.path.join(META, "r3_main_reference.json")
SELFTEST_PATH = os.path.join(META, "judge_selftest.json")

INSTRUCTION = "docs/104_r3_main_package_prompt_for_vscode.md"
BLOCK = "AP"

# ── F2 · 패키지 20파일 (패키지 내 경로, 복사 원본(저장소 상대), sha256, bytes) ────────
PACKAGE_FILES_SPEC = [
    ("README_R3_MAIN.md",
     "experiments/rqint/r3_main_package_inputs/README_R3_MAIN.md",
     "34bdd25fa6957bee0554e868ca775784334288d394542eb04f7a2a1dc02a34b1", 3770),
    ("canonical.py", "experiments/rqint/r3_package/canonical.py",
     "d58e0f4320c01149b535ffa468c34b93a51213ed1ac9716306775ec20804ba1d", 5098),
    ("collect_env.py", "experiments/rqint/r3_package/collect_env.py",
     "948cac55a6337c47f12948631d906fae551563eb22ae05d2c28569d2113f7b64", 4199),
    ("package_hashes.py",
     "experiments/rqint/r3_main_package_inputs/package_hashes.py",
     "91b660eb8278b3e2e735285e6be998c26622bd7cba0fca3a4605d6cc247d14de", 2296),
    ("requirements_r3.txt",
     "experiments/rqint/r3_main_package_inputs/requirements_r3.txt",
     "7b1969d0cc3bead0d10764c6ac2b3246cbba7f1aebe451bce8f3ad4c0a3968c5", 338),
    ("v3_Multimodal/src/run_rqint_audit.py", "v3_Multimodal/src/run_rqint_audit.py",
     "ab831c2726a36e8a671fc412b06072d5fb267d0de3ef38cd5b1b98eee8e80b5f", 18191),
    ("v3_Multimodal/src/sap/__init__.py", "v3_Multimodal/src/sap/__init__.py",
     "8dc63e28ffcf93dcdfde7facd0cf1d51b6e6c15ac4de2304de61c12ccb7a5306", 1635),
    ("v3_Multimodal/src/sap/bootstrap.py", "v3_Multimodal/src/sap/bootstrap.py",
     "05437c516e606a053e02acefb23c2597365472201b6c70ff2814278d6597a31e", 14214),
    ("v3_Multimodal/src/sap/consensus.py", "v3_Multimodal/src/sap/consensus.py",
     "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91", 3124),
    ("v3_Multimodal/src/sap/decision.py", "v3_Multimodal/src/sap/decision.py",
     "f688b20d816acabe17c2906cfa846c1f794ba45a416248c08aa7e41676e82a92", 16353),
    ("v3_Multimodal/src/sap/freeze.py", "v3_Multimodal/src/sap/freeze.py",
     "8bef5f70d168c50d7860d5e1d70f78b771d76405fafe2c4d256ac04d08078bc9", 42927),
    ("v3_Multimodal/src/sap/metrics.py", "v3_Multimodal/src/sap/metrics.py",
     "a7d3fe4fe9e87983b35b086b0c464bde1e710e013f98813a2f28a2b48c8b2004", 4256),
    ("v3_Multimodal/src/sap/null_generator.py", "v3_Multimodal/src/sap/null_generator.py",
     "90886abce256a130531a0ab0cd8edd17abc27ff1b62ee56f24248aa76fa204c7", 11119),
    ("v3_Multimodal/src/sap/redaction.py", "v3_Multimodal/src/sap/redaction.py",
     "4d4bf221141fbc793a2bc9c9989906a5c072d7f3e0e49be495cf79d67a5b580c", 3647),
    ("v3_Multimodal/src/sap/rqint.py", "v3_Multimodal/src/sap/rqint.py",
     "eb842bc98140e9c55b67bc1563cd5573c3b294885778f23744468b712c498b26", 12970),
    ("v3_Multimodal/src/sap/rqint_audit.py", "v3_Multimodal/src/sap/rqint_audit.py",
     "ddffe6d128de4d180aeab9be18d6b1a9b5281523bc24cd8a3b4f48f20a2aa4a3", 19573),
    ("v3_Multimodal/src/sap/rqint_synthetic.py", "v3_Multimodal/src/sap/rqint_synthetic.py",
     "27ef0011ee041920a6e7b63eb4dcfef13c7fd2a70ac017f2324e671df8b0f985", 5572),
    ("v3_Multimodal/src/sap/signflip.py", "v3_Multimodal/src/sap/signflip.py",
     "3de1223585ae0f978438bacfdd8e439c7f0ce95b776d615d098a5881e6ce06d2", 6772),
    ("v3_Multimodal/src/sap/synthetic.py", "v3_Multimodal/src/sap/synthetic.py",
     "ddf715e6fba7503e817c6435c9220f7a83a5e5e31375603fddd522570f2a27d7", 8444),
    ("v3_Multimodal/src/sap/unseen_target.py", "v3_Multimodal/src/sap/unseen_target.py",
     "96c0c87911e8c93d6032f3f5be09b46f0cc61ab9a36c39fe7bef1b731df76c89", 5610),
]

JUDGE_SRC = "experiments/rqint/r3_main_package_inputs/r3_judge.py"
JUDGE_SHA = "df26e946d17cd0b5ea20c741008bbdfbe19ee8b2b7d92b0de7664943ea4bcd12"

# AP-3-3 · 기대값 미동봉 검사 — 이 6개 문자열이 패키지 20파일 바이트에 1건도 없어야 한다.
FORBIDDEN_SUBSTRINGS = ("fd488eb4", "3745438643aa", "8b5fb0bf28c4",
                        "921e16ea8191", "a94b04f53ba5", "4b474b3d7f09")

# L2 · 로컬 기준값이 반드시 일치해야 하는 블록 AC 값
AC_AUDIT_REL = "experiments/rqint/audit_r6.json"
AC_RUNLOG_REL = "experiments/rqint/run.log"
AC_AUDIT_SHA = "921e16ea8191bc9b5ecdeeab7f40a42df89e6e4bdc3cd180273b6c91da8e6dfd"
AC_RUNLOG_SHA = "43f395828040f2b57f213aa72792edcf1ca705fbf906d1011643beca87285208"
AC_NUMERIC_CORE_SHA = "fd488eb429a71990d47ebf321efeb1f34083bbeb4813730a76777262b1ba878b"
AC_CANONICAL_BYTES = 7493

ZIP_DATE_TIME = (2026, 9, 11, 0, 0, 0)
ZIP_PREDICTED_SHA = "4b474b3d7f098c67fa3bae1c1d8a9dadb0bce3ad7f978ae911ad450307999948"
ZIP_PREDICTED_BYTES = 73746

THREAD_ENVVARS = ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                  "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]

EXIT_ALREADY = 4


# ── 공용 ────────────────────────────────────────────────────────────────────
def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def die(msg, code=1):
    print(f"[중단] {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def once(path):
    if os.path.exists(path):
        print(f"[중단] 1회성 산출물이 이미 있음: {os.path.relpath(path, ROOT)}",
              file=sys.stderr, flush=True)
        sys.exit(EXIT_ALREADY)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sealed_counts():
    """봉인 계수 — **경로 나열만**(내용 읽기·해싱 0)."""
    dirs, files, access = 0, 0, 0
    for root, dnames, fnames in os.walk(os.path.join(ROOT, "experiments")):
        if os.path.basename(root) == "_sealed":
            dirs += 1
        if "_sealed" in root.split(os.sep):
            for fn in fnames:
                if fn == "access.log":
                    access += 1
                else:
                    files += 1
    return {"sealed_dirs": dirs, "files_excl_access_log": files,
            "access_log": access, "total": files + access}


def list_tree(base):
    out = []
    for root, dnames, fnames in os.walk(base):
        for fn in fnames:
            p = os.path.join(root, fn)
            out.append(os.path.relpath(p, base).replace(os.sep, "/"))
    return sorted(out)


# ── AP-2 · 스테이징 ─────────────────────────────────────────────────────────
def stage():
    src_sha_start = {}
    os.makedirs(STAGING, exist_ok=False)
    for rel, src_rel, esha, ebytes in PACKAGE_FILES_SPEC:
        src = os.path.join(ROOT, *src_rel.split("/"))
        got = sha256_file(src)
        if got != esha or os.path.getsize(src) != ebytes:
            die(f"복사 원본 sha256/bytes 불일치: {src_rel} {got}")
        src_sha_start[src_rel] = got
        dst = os.path.join(STAGING, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    rows = []
    for rel, src_rel, esha, ebytes in PACKAGE_FILES_SPEC:
        dst = os.path.join(STAGING, *rel.split("/"))
        got, nb = sha256_file(dst), os.path.getsize(dst)
        if got != esha or nb != ebytes:
            die(f"복사본 sha256/bytes 불일치: {rel} {got} {nb}")
        rows.append({"package_path": rel, "source_path": src_rel, "sha256": got, "bytes": nb})
    for rel, src_rel, esha, _b in PACKAGE_FILES_SPEC:      # 원본 착수=종료
        if sha256_file(os.path.join(ROOT, *src_rel.split("/"))) != src_sha_start[src_rel]:
            die(f"복사 원본이 변했다: {src_rel}")
    print(f"[AP-2] 스테이징 20/20 복사·해시 일치")
    return rows


def copy_judge():
    once(JUDGE_DST)
    src = os.path.join(ROOT, *JUDGE_SRC.split("/"))
    if sha256_file(src) != JUDGE_SHA:
        die(f"판정기 입력 sha256 불일치: {JUDGE_SRC}")
    shutil.copyfile(src, JUDGE_DST)
    got = sha256_file(JUDGE_DST)
    if got != JUDGE_SHA:
        die(f"판정기 복사본 sha256 불일치: {got}")
    print(f"[AP-2-3] r3_judge.py 복사 · sha256 {got[:16]}")
    return got


# ── AP-3 · 패키지 검사 ──────────────────────────────────────────────────────
def package_files_from_ast():
    """package_hashes.py 의 PACKAGE_FILES 리스트 리터럴을 **AST 로** 판독(import·실행 0)."""
    path = os.path.join(STAGING, "package_hashes.py")
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PACKAGE_FILES":
                    return list(ast.literal_eval(node.value))
    die("package_hashes.py 에서 PACKAGE_FILES 리스트를 찾지 못함")


def package_hashes_ast_constraints():
    """AP-3-4 — import 5종뿐 · open() 은 'rb' 1곳 + 'w' 1곳 · 네트워크 모듈 0."""
    path = os.path.join(STAGING, "package_hashes.py")
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    modes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            m = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                m = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    m = kw.value.value
            modes.append(m if m is not None else "r")
    net = {"socket", "http", "urllib", "requests", "ftplib", "smtplib", "ssl",
           "asyncio", "subprocess", "telnetlib", "xmlrpc"}
    res = {"imports": sorted(mods), "open_modes": sorted(modes),
           "imports_ok": mods == {"__future__", "hashlib", "json", "os", "sys"},
           "open_ok": sorted(modes) == ["rb", "w"],
           "network_modules": sorted(mods & net)}
    res["pass"] = res["imports_ok"] and res["open_ok"] and not res["network_modules"]
    if not res["pass"]:
        die(f"package_hashes.py AST 제약 위반: {res}")
    print(f"[AP-3-4] package_hashes.py AST 제약 PASS · import {res['imports']} · open {res['open_modes']}")
    return res


def inspect_package():
    tree = list_tree(STAGING)
    spec_paths = sorted(r[0] for r in PACKAGE_FILES_SPEC)
    if tree != spec_paths:
        die(f"스테이징 파일 목록 불일치: 여분={sorted(set(tree)-set(spec_paths))} "
            f"누락={sorted(set(spec_paths)-set(tree))}")
    junk = [p for p in tree if "__pycache__" in p or os.path.basename(p) in (".DS_Store",)]
    if junk:
        die(f"스테이징 부산물: {junk}")
    ast_list = package_files_from_ast()
    if ast_list != spec_paths:
        die(f"PACKAGE_FILES(AST) 와 경로 목록 불일치")
    hits = []
    for rel in tree:
        data = open(os.path.join(STAGING, *rel.split("/")), "rb").read()
        for s in FORBIDDEN_SUBSTRINGS:
            if s.encode("ascii") in data:
                hits.append({"file": rel, "needle": s})
    if hits:
        die(f"기대값 문자열 동봉: {hits}")
    forbidden_dirs = [p for p in tree
                      if p.startswith("data/") or "_sealed" in p.split("/")
                      or p.split("/")[0] == "experiments"]
    if forbidden_dirs:
        die(f"패키지 안에 data/ · _sealed · experiments/ 경로: {forbidden_dirs}")
    ast_res = package_hashes_ast_constraints()
    print(f"[AP-3] 파일 {len(tree)} · 부산물 0 · PACKAGE_FILES 일치 · 기대값 문자열 0건 · "
          f"금지경로 0")
    return {"n_files": len(tree), "paths": tree, "package_files_ast": ast_list,
            "junk": junk, "forbidden_substring_hits": hits,
            "forbidden_dir_hits": forbidden_dirs, "package_hashes_ast": ast_res}


# ── AP-4 · zip · manifest ──────────────────────────────────────────────────
def build_zip(rows):
    package_files = [r["package_path"] for r in rows]
    names = sorted("r3_main_package/" + rel for rel in package_files)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            zi = zipfile.ZipInfo(name, date_time=ZIP_DATE_TIME)
            zi.external_attr = 0o644 << 16
            zi.create_system = 3
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(STAGING_PARENT, *name.split("/")), "rb") as f:
                z.writestr(zi, f.read())
    # 재열람 검증
    by_pkg = {"r3_main_package/" + r["package_path"]: r for r in rows}
    checks = {"n_entries": None, "names_match": None, "date_time_all": True,
              "external_attr_all": True, "create_system_all": True,
              "compress_type_all": True, "member_sha_match": True, "members": []}
    with zipfile.ZipFile(ZIP_PATH) as z:
        infos = z.infolist()
        checks["n_entries"] = len(infos)
        checks["names_match"] = [i.filename for i in infos] == names
        for i in infos:
            if tuple(i.date_time) != ZIP_DATE_TIME:
                checks["date_time_all"] = False
            if (i.external_attr >> 16) != 0o644:
                checks["external_attr_all"] = False
            if i.create_system != 3:
                checks["create_system_all"] = False
            if i.compress_type != zipfile.ZIP_DEFLATED:
                checks["compress_type_all"] = False
            got = hashlib.sha256(z.read(i.filename)).hexdigest()
            exp = by_pkg[i.filename]["sha256"]
            if got != exp:
                checks["member_sha_match"] = False
                checks["members"].append({"name": i.filename, "got": got, "expected": exp})
    if not (checks["n_entries"] == 20 and checks["names_match"] and checks["date_time_all"]
            and checks["external_attr_all"] and checks["create_system_all"]
            and checks["compress_type_all"]):
        die(f"zip 재열람 검증 실패: {checks}")
    if not checks["member_sha_match"]:
        die(f"zip 멤버 바이트 불일치: {checks['members']}")
    zsha, zbytes = sha256_file(ZIP_PATH), os.path.getsize(ZIP_PATH)
    checks["zip_sha256"] = zsha
    checks["zip_bytes"] = zbytes
    checks["predicted_sha256"] = ZIP_PREDICTED_SHA
    checks["predicted_bytes"] = ZIP_PREDICTED_BYTES
    checks["matches_prediction"] = (zsha == ZIP_PREDICTED_SHA and zbytes == ZIP_PREDICTED_BYTES)
    checks["zlib_version"] = zlib.ZLIB_VERSION
    print(f"[AP-4] zip sha256 {zsha} · {zbytes} B · 예측일치={checks['matches_prediction']} "
          f"(zlib {zlib.ZLIB_VERSION})")
    return checks


def write_manifest(rows, zchecks):
    once(MANIFEST_PATH)
    os.makedirs(META, exist_ok=True)
    payload = {
        "_doc": ("R3 본 드라이런 배포 패키지 매니페스트 — 블록 AP. "
                 "기대값(로컬 기준 numeric_core 등)은 패키지에도 이 파일에도 넣지 않는다."),
        "zip_path": "experiments/rqint/r3_main_package.zip",
        "zip_sha256": zchecks["zip_sha256"],
        "zip_bytes": zchecks["zip_bytes"],
        "n_files": 20,
        "files": {"r3_main_package/" + r["package_path"]:
                  {"sha256": r["sha256"], "bytes": r["bytes"], "source_path": r["source_path"]}
                  for r in rows},
        "zip_recipe": {"date_time": list(ZIP_DATE_TIME), "external_attr": "0o644<<16",
                       "create_system": 3, "compression": "ZIP_DEFLATED",
                       "ordering": "sorted names", "dir_entries": 0},
        "built_by": {"block": BLOCK, "instruction": INSTRUCTION},
        "built_at_kst": now_kst(),
        "expected_values_included": False,
        "externally_distributed": False,
    }
    write_json(MANIFEST_PATH, payload)
    print(f"[AP-4] manifest {sha256_file(MANIFEST_PATH)[:16]}")
    return payload


def cmd_build():
    once(STAGING)
    once(ZIP_PATH)
    once(MANIFEST_PATH)
    once(JUDGE_DST)
    rows = stage()
    judge_sha = copy_judge()
    insp = inspect_package()
    zchecks = build_zip(rows)
    write_manifest(rows, zchecks)
    # 메타 산출물은 0-3 의 9종뿐이다 → 검사 내역은 파일로 남기지 않고 콘솔로만 보고한다.
    print(json.dumps({"staging": insp, "zip": zchecks,
                      "judge_copy": {"path": "v3_Multimodal/src/r3_judge.py",
                                     "sha256": judge_sha},
                      "files": rows}, ensure_ascii=False, indent=2))
    print("[AP-4] 종료")
    return 0


# ── AP-5 · 로컬 기준 실행 ───────────────────────────────────────────────────
def load_canonical_from_staging():
    path = os.path.join(STAGING, "canonical.py")
    spec = importlib.util.spec_from_file_location("r3_canonical_staging", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def g_env_fields(env):
    cfg = ((env.get("numpy_build_config") or {}).get("config") or {})
    deps = cfg.get("Build Dependencies") or {}
    return {"python_version": env.get("python_version"), "numpy": env.get("numpy"),
            "sklearn": env.get("sklearn"), "machine": env.get("machine"),
            "numpy_build_config(BLAS/LAPACK 구현)": [(deps.get("blas") or {}).get("name"),
                                                   (deps.get("lapack") or {}).get("name")]}


def cmd_local_run():
    for p in (ENV_LOCAL, AUDIT_LOCAL, RUNLOG_LOCAL, CORE_LOCAL, HASHES_LOCAL, RECORD_LOCAL):
        once(p)
    if not os.path.exists(ZIP_PATH) or not os.path.exists(MANIFEST_PATH):
        die("--build 산출물(zip·manifest)이 없다")
    manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))

    unmodified = {"staging": {r: sha256_file(os.path.join(STAGING, *r.split("/")))
                              for r in list_tree(STAGING)},
                  "zip": sha256_file(ZIP_PATH),
                  AC_AUDIT_REL: sha256_file(os.path.join(ROOT, *AC_AUDIT_REL.split("/"))),
                  AC_RUNLOG_REL: sha256_file(os.path.join(ROOT, *AC_RUNLOG_REL.split("/")))}
    if unmodified[AC_AUDIT_REL] != AC_AUDIT_SHA or unmodified[AC_RUNLOG_REL] != AC_RUNLOG_SHA:
        die("블록 AC 산출물 sha256 이 F5 와 다르다")
    sealed_start = sealed_counts()

    started = now_kst()
    with CL.ComputeLock(script="build_r3_main_package.py", role="runner"):
        gate_entry = CL.gate_b_exclusive("ap5:entry")            # gate_a_load 면제(AP-5)
        tmp = tempfile.mkdtemp(prefix="r3_main_local_")
        if os.path.realpath(tmp).startswith(os.path.realpath(ROOT) + os.sep):
            die("임시 디렉터리가 저장소 안이다")
        print(f"[AP-5] tmp={os.path.basename(tmp)}", flush=True)
        with zipfile.ZipFile(ZIP_PATH) as z:
            z.extractall(tmp)
        work = os.path.join(tmp, "r3_main_package")
        extracted = list_tree(work)
        if len(extracted) != 20:
            die(f"풀린 파일 {len(extracted)}개")
        for rel in extracted:
            got = sha256_file(os.path.join(work, *rel.split("/")))
            if got != manifest["files"]["r3_main_package/" + rel]["sha256"]:
                die(f"풀린 파일 sha256 불일치: {rel}")
        print("[AP-5] 풀린 20파일 = manifest 20/20", flush=True)

        child = dict(os.environ)
        removed = [k for k in THREAD_ENVVARS if child.pop(k, None) is not None]
        child["PYTHONDONTWRITEBYTECODE"] = "1"
        assert not any(k in child for k in THREAD_ENVVARS)
        exe = sys.executable
        cmds = [
            ("c1", [exe, "-B", "collect_env.py", "env_local_main.json"]),
            ("c2", [exe, "-B", "-X", "utf8", "v3_Multimodal/src/run_rqint_audit.py"]),
            ("c3", [exe, "-B", "canonical.py", "experiments/rqint/audit_r6.json",
                    "audit_numeric_core.sha256"]),
            ("c4", [exe, "-B", "package_hashes.py"]),
        ]
        cmd_records = []
        for tag, argv in cmds:
            t0 = time.time()
            print(f"[AP-5] {tag} 시작 {now_kst()}", flush=True)
            p = subprocess.run(argv, cwd=work, env=child, capture_output=True, text=True)
            wall = round(time.time() - t0, 2)
            cmd_records.append({"tag": tag,
                                "argv": [".venv/bin/python3"] + argv[1:],
                                "returncode": p.returncode, "wall_seconds": wall,
                                "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]})
            print(f"[AP-5] {tag} rc={p.returncode} {wall}s", flush=True)
            if p.returncode != 0:
                print(p.stdout[-3000:], flush=True)
                print(p.stderr[-3000:], file=sys.stderr, flush=True)
                die(f"{tag} returncode {p.returncode}", 5)

        # L6 · 임시 디렉터리 신규 파일
        after = list_tree(work)
        new_files = sorted(set(after) - set(extracted))
        expected_new = ["audit_numeric_core.sha256", "env_local_main.json",
                        "experiments/rqint/audit_r6.json", "experiments/rqint/run.log",
                        "package_hashes.json"]
        if new_files != expected_new:
            die(f"임시 디렉터리 신규 파일 불일치: {new_files}")
        for rel in extracted:
            if sha256_file(os.path.join(work, *rel.split("/"))) != \
                    manifest["files"]["r3_main_package/" + rel]["sha256"]:
                die(f"실행 후 원래 20파일이 변했다: {rel}")
        pyc = [p for p in after if "__pycache__" in p]
        if pyc:
            die(f"임시 디렉터리에 __pycache__: {pyc}")

        # L1 · L2 · L3
        audit = json.load(open(os.path.join(work, "experiments", "rqint", "audit_r6.json"),
                               encoding="utf-8"))
        l1 = {"r6_all_pass": audit.get("r6_all_pass"),
              "r6_keys": sorted(audit.get("r6", {}).keys()),
              "r6_pass_all": all(v.get("pass") is True for v in audit.get("r6", {}).values()),
              "synthetic_only": audit.get("synthetic_only"),
              "confirmatory_data_accessed": audit.get("confirmatory_data_accessed"),
              "unblinding_performed": audit.get("unblinding_performed"),
              "gin_start_still_blocked": audit.get("gin_start_still_blocked")}
        l1["pass"] = (l1["r6_all_pass"] is True and len(l1["r6_keys"]) == 9
                      and l1["r6_pass_all"] and l1["synthetic_only"] is True
                      and l1["confirmatory_data_accessed"] is False
                      and l1["unblinding_performed"] is False
                      and l1["gin_start_still_blocked"] is True)
        if not l1["pass"]:
            die(f"L1 불성립: {l1}")

        core_file = json.load(open(os.path.join(work, "audit_numeric_core.sha256"),
                                   encoding="utf-8"))
        canonical = load_canonical_from_staging()
        recomputed_sha, _rm, recomputed_bytes = canonical.numeric_core_sha256(audit)
        l2 = {"from_c3_file": {"sha256": core_file.get("numeric_core_sha256"),
                               "canonical_bytes": core_file.get("canonical_bytes")},
              "recomputed_via_staging_canonical": {"sha256": recomputed_sha,
                                                   "canonical_bytes": recomputed_bytes},
              "expected_sha256": AC_NUMERIC_CORE_SHA,
              "expected_canonical_bytes": AC_CANONICAL_BYTES}
        l2["pass"] = (core_file.get("numeric_core_sha256") == AC_NUMERIC_CORE_SHA
                      and core_file.get("canonical_bytes") == AC_CANONICAL_BYTES
                      and recomputed_sha == AC_NUMERIC_CORE_SHA
                      and recomputed_bytes == AC_CANONICAL_BYTES)
        pkg_hashes = json.load(open(os.path.join(work, "package_hashes.json"), encoding="utf-8"))
        l3 = {"n_missing": pkg_hashes.get("n_missing"),
              "n_files_listed": pkg_hashes.get("n_files_listed")}
        l3["n_mismatch"] = sum(
            1 for rel, v in (pkg_hashes.get("files") or {}).items()
            if not isinstance(v, dict)
            or v.get("sha256") != manifest["files"]["r3_main_package/" + rel]["sha256"])
        l3["pass"] = l3["n_missing"] == 0 and l3["n_files_listed"] == 20 and l3["n_mismatch"] == 0

        env_local = json.load(open(os.path.join(work, "env_local_main.json"), encoding="utf-8"))
        ag_env_path = os.path.join(RQINT, "r3_package_meta", "env_local.json")
        ag_env = json.load(open(ag_env_path, encoding="utf-8"))
        ours, theirs = g_env_fields(env_local), g_env_fields(ag_env)
        l7 = {"ap_env": ours, "ag_env": theirs,
              "per_field_equal": {k: ours[k] == theirs[k] for k in ours}}
        l7["five_fields_equal"] = all(l7["per_field_equal"].values())

        if not l2["pass"]:
            # 진단은 콘솔로만 — 메타 산출물은 0-3 의 9종뿐이고, 이 경로는 메타 복사 이전이다.
            print(json.dumps({"L2": l2, "tmp_dir_basename": os.path.basename(tmp)},
                             ensure_ascii=False, indent=2), flush=True)
            CL.gate_b_exclusive("ap5:exit")
            die("L2 불일치 — AP-6~AP-8 미실행 · 기준 파일 미작성 · 원장 기입 0", 5)
        if not l3["pass"]:
            die(f"L3 불성립: {l3}")

        # 메타 복사 (c1~c4 전부 성공 뒤에만)
        os.makedirs(META, exist_ok=True)
        shutil.copyfile(os.path.join(work, "env_local_main.json"), ENV_LOCAL)
        shutil.copyfile(os.path.join(work, "experiments", "rqint", "audit_r6.json"), AUDIT_LOCAL)
        shutil.copyfile(os.path.join(work, "experiments", "rqint", "run.log"), RUNLOG_LOCAL)
        shutil.copyfile(os.path.join(work, "audit_numeric_core.sha256"), CORE_LOCAL)
        shutil.copyfile(os.path.join(work, "package_hashes.json"), HASHES_LOCAL)

        gate_exit = CL.gate_b_exclusive("ap5:exit")

    sealed_end = sealed_counts()
    if sealed_end != sealed_start:
        die(f"봉인 계수 변화: {sealed_start} → {sealed_end}")
    l4 = {"pass": True, "diff": []}
    for rel, s in unmodified["staging"].items():
        if sha256_file(os.path.join(STAGING, *rel.split("/"))) != s:
            l4["pass"] = False
            l4["diff"].append("staging/" + rel)
    for label, path, s in (("zip", ZIP_PATH, unmodified["zip"]),
                           (AC_AUDIT_REL, os.path.join(ROOT, *AC_AUDIT_REL.split("/")),
                            unmodified[AC_AUDIT_REL]),
                           (AC_RUNLOG_REL, os.path.join(ROOT, *AC_RUNLOG_REL.split("/")),
                            unmodified[AC_RUNLOG_REL])):
        if sha256_file(path) != s:
            l4["pass"] = False
            l4["diff"].append(label)
    if not l4["pass"]:
        die(f"L4 불성립(무수정 위반): {l4}")

    record = {
        "_doc": "AP-5 로컬 기준 실행 기록(블록 AP · docs/104). 절대경로는 남기지 않는다.",
        "instruction": INSTRUCTION, "block": BLOCK,
        "tmp_dir_basename": os.path.basename(tmp),
        "python_executable": ".venv/bin/python3",
        "python_version": env_local.get("python_version"),
        "numpy": env_local.get("numpy"), "sklearn": env_local.get("sklearn"),
        "blas_name": g_env_fields(env_local)["numpy_build_config(BLAS/LAPACK 구현)"],
        "child_env_removed_vars": THREAD_ENVVARS,
        "child_env_removed_actually_present": removed,
        # ★ stdout/stderr 원문은 기록하지 않는다 — c2 출력에 임시 디렉터리 절대경로가 섞인다
        #   (AP-2 「기록물에 절대경로 0」. 원문은 run_local_main.log 와 콘솔 로그에만 남는다).
        "commands": [{k: v for k, v in c.items() if not k.endswith("_tail")}
                     for c in cmd_records],
        "gate_b": [gate_entry, gate_exit],
        "sealed_guard": {"start": sealed_start, "end": sealed_end},
        "started_at_kst": started, "finished_at_kst": now_kst(),
        "new_files_in_tmp": new_files,
        "attempt": int(os.environ.get("AP5_ATTEMPT", "1")),
        "checks": {"L1": l1, "L2": l2, "L3": l3, "L4": l4,
                   "L5": {"start": sealed_start, "end": sealed_end, "pass": True},
                   "L6": {"new_files": new_files, "n_pycache": 0, "pass": True},
                   "L7": l7},
        "wall_clock_seconds": audit.get("wall_clock_seconds"),
    }
    write_json(RECORD_LOCAL, record)
    print(f"[AP-5] L2 numeric_core {l2['from_c3_file']['sha256']} "
          f"({l2['from_c3_file']['canonical_bytes']} B) · AC 일치={l2['pass']}")
    print(f"[AP-5] L7 five_fields_equal={l7['five_fields_equal']}")
    print(f"[AP-5] 종료 {now_kst()}")
    return 0


# ── AP-7 · 기준 파일 ────────────────────────────────────────────────────────
def cmd_reference():
    once(REFERENCE_PATH)
    for p in (MANIFEST_PATH, ENV_LOCAL, AUDIT_LOCAL, CORE_LOCAL, HASHES_LOCAL,
              RECORD_LOCAL, SELFTEST_PATH, JUDGE_DST):
        if not os.path.exists(p):
            die(f"선행 산출물 부재: {os.path.relpath(p, ROOT)}")
    manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
    core = json.load(open(CORE_LOCAL, encoding="utf-8"))
    record = json.load(open(RECORD_LOCAL, encoding="utf-8"))
    selftest = json.load(open(SELFTEST_PATH, encoding="utf-8"))
    freeze_rel = "v3_Multimodal/config/r3_second_party_freeze.json"

    payload = {
        "_doc": "R3 본 드라이런 기준값 — 트리거(메일 3 발송) 이전 등록. 제2자에게 공유하지 않는다.",
        "block": BLOCK, "instruction": INSTRUCTION,
        "registered_at_kst": now_kst(),
        "trigger_event_status": "not_yet — 메일 3 미발송",
        "package": {"zip_path": manifest["zip_path"], "zip_sha256": manifest["zip_sha256"],
                    "zip_bytes": manifest["zip_bytes"], "n_files": 20,
                    "manifest_sha256": sha256_file(MANIFEST_PATH)},
        "local_run": {
            "audit_sha256": sha256_file(AUDIT_LOCAL),
            "audit_path": "experiments/rqint/r3_main_package_meta/audit_r6_local_main.json",
            "numeric_core_sha256": core["numeric_core_sha256"],
            "canonical_bytes": core["canonical_bytes"],
            "env_sha256": sha256_file(ENV_LOCAL),
            "env_path": "experiments/rqint/r3_main_package_meta/env_local_main.json",
            "package_hashes_sha256": sha256_file(HASHES_LOCAL),
            "wall_clock_seconds": record["wall_clock_seconds"],
            "python_version": record["python_version"], "numpy": record["numpy"],
            "sklearn": record["sklearn"], "blas_name": record["blas_name"]},
        "consistency_with_block_AC": {
            "ac_audit_path": AC_AUDIT_REL, "ac_audit_sha256": AC_AUDIT_SHA,
            "ac_numeric_core_sha256": AC_NUMERIC_CORE_SHA,
            "equal": core["numeric_core_sha256"] == AC_NUMERIC_CORE_SHA},
        "g_env_reference": {
            "path": "experiments/rqint/r3_main_package_meta/env_local_main.json",
            "supersedes_for_R3_main": "experiments/rqint/r3_package_meta/env_local.json",
            "five_fields_equal": record["checks"]["L7"]["five_fields_equal"]},
        "acceptance_criteria": {"path": freeze_rel,
                                "sha256": sha256_file(os.path.join(ROOT, *freeze_rel.split("/")))},
        "judge": {"path": "v3_Multimodal/src/r3_judge.py", "sha256": sha256_file(JUDGE_DST),
                  "selftest_path": "experiments/rqint/r3_main_package_meta/judge_selftest.json",
                  "selftest_sha256": sha256_file(SELFTEST_PATH),
                  "selftest_n_pass": selftest["n_pass"]},
        "operationalization": ("docs/33 항목55 — 전 리프 타입 규칙 · 잔차 7개는 소속 R6 pass · "
                               "G-ENV 알려진 값만 · 입력 결속 검사 · package_hashes 대조 · "
                               "freeze 목록 항목 대비 느슨해지는 방향 0"),
        "not_shared_with_second_party": True,
    }
    if not payload["consistency_with_block_AC"]["equal"]:
        die("기준 numeric_core 가 블록 AC 값과 다르다")
    write_json(REFERENCE_PATH, payload)
    print(f"[AP-7] r3_main_reference.json sha256 {sha256_file(REFERENCE_PATH)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--local-run", action="store_true")
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args(argv)
    n = sum([a.build, a.local_run, a.reference])
    if n != 1:
        ap.error("--build · --local-run · --reference 중 정확히 1개")
    if a.build:
        return cmd_build()
    if a.local_run:
        return cmd_local_run()
    return cmd_reference()


if __name__ == "__main__":
    sys.exit(main())
