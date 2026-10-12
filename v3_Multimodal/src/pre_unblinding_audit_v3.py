#!/usr/bin/env python3
"""pre_unblinding_audit_v3.py — [블록 BD] 개봉 전 전수 감사 v3 (지시서 `docs/119`) · r2 = [블록 BE] 재실행 보정
(지시서 `docs/119b` — 열람 대장 대응 규칙 (b) 문서화 수동 게이트 줄 · 블록 AV 등록 · spec_item 71 · Z5 1회차 대조).

성격: 계산 0 · 학습 0 · 추론 0 · 개봉 0 · 새 부호 0 · 네트워크 0 · git 쓰기 0 · `git status` 0.
봉인 파일 조작 = 경로·크기·mtime_ns·sha256(1 MiB 청크 바이트 스트림) 뿐. 역직렬화 예외 2종만 허용:
  ⓐ 확증 GIN `checkpoint.jsonl` 3파일 — 키 화이트리스트 투영(§2-3 · `object_pairs_hook`)
  ⓑ `access.log` — 메타데이터라 전체 파싱 허용.
access.log 쓰기 0. import = 표준 라이브러리만(sap·numpy·pandas·unblinding_run import 0 — selftest U11 의
오라클 대조는 별도 서브프로세스가 `unblinding_run.stat_summary` 를 호출하고 JSON 만 돌려준다).

단계 (순서 고정)
  --stage selftest        합성 결함 U1~U18 (tempfile 가짜 저장소 · 실저장소 쓰기 0) → selftest_audit_v3r2.json
  --stage build-expected  독립 기대목록 801 (기록물 + 동결 설계 격자 + writer 소스 · live 열거 0 · 봉인 I/O 가드)
  --stage run             1회 실행(Phase B) → pre_unblinding_audit_v3.json(9키) + audit_details_v3.json + run.log
                          전제: selftest r2 all_pass · selftest r2 의 script sha == 현재 · docs/33 마커
                          (expected_manifest_v3 = 항목 79·81 · audit_script_r2 · selftest_r2 = 항목 81) == 현재
                          · 출력 디렉터리 = selftest(1회차) · selftest r2 · expected_manifest · run1_FAIL/(5파일 sha 고정)

실행
  PYTHONDONTWRITEBYTECODE=1 python3 -B v3_Multimodal/src/pre_unblinding_audit_v3.py --stage selftest
  PYTHONDONTWRITEBYTECODE=1 python3 -B v3_Multimodal/src/pre_unblinding_audit_v3.py --stage build-expected
  PYTHONDONTWRITEBYTECODE=1 python3 -B v3_Multimodal/src/pre_unblinding_audit_v3.py --stage run
"""
import sys

sys.dont_write_bytecode = True

import argparse                                                     # noqa: E402
import ast                                                          # noqa: E402
import builtins                                                     # noqa: E402
import contextlib                                                   # noqa: E402
import datetime                                                     # noqa: E402
import fnmatch                                                      # noqa: E402
import hashlib                                                      # noqa: E402
import json                                                         # noqa: E402
import os                                                           # noqa: E402
import re                                                           # noqa: E402
import shutil                                                       # noqa: E402
import subprocess                                                   # noqa: E402
import tempfile                                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SELF = os.path.abspath(__file__)

BLOCK = "BE — 개봉 전 전수 감사 v3 재실행"
INSTRUCTION = "docs/119b_pre_unblinding_reaudit_prompt_for_vscode.md"

# ── 경로 상수 (한곳) ─────────────────────────────────────────────────────────
OUT_REL = "experiments/runs/v3_preaudit_v3"
SELFTEST_NAME = "selftest_audit_v3.json"                           # 1회차(블록 BD) — 보존 · run 이 읽지 않음
SELFTEST_R2_NAME = "selftest_audit_v3r2.json"
RUN1_DIR = "run1_FAIL"
RUN1_ARCHIVE = {                                                   # docs/119b Z4 — 1회차 보관 5파일 (sha 고정)
    "pre_unblinding_audit_v3.json": "65c5bfb2ca141a515d91e3ec51ecfe090bdd349941409515ff4c688810a0e1b8",
    "audit_details_v3.json": "d033df07dc6f6b28db40f45ccc0df0a1ba2de1e8cca01868e2a8a0a49ff6a1b6",
    "run.log": "cd941fe610066b0765dfd882eb93d67f8f5b526e0608ef5a72e0b6902d2b59ca",
    "pre_unblinding_audit_v3_run1.py": "f750f457e254fce0f285339b5f0f8dc16a65140b668c18572e8ed7f74fad121e",
    "selftest_audit_v3_run1.json": "0206118188c544258d8513a29752da8d3cd65fb2a7ecaf29f33c5317a54052b8",
}
EXPECTED_NAME = "expected_manifest_v3.json"
DETAILS_NAME = "audit_details_v3.json"
RUNLOG_NAME = "run.log"
AUDIT_REL = "experiments/provenance/pre_unblinding_audit_v3.json"
REPORT_REL = "docs/119_pre_unblinding_audit_v3_report.md"
PLAN_REL = "v3_Multimodal/config/unblinding_plan_v1.json"
DOC33_REL = "docs/33_prereg_deviation_log.md"
FREEZE_MANIFEST_REL = "experiments/runs/v3_unblind_freeze/freeze_manifest.json"
AO_REL = "experiments/provenance/sealing_completeness_audit_v2.json"
RUNS_REL = "experiments/runs"
SRC_REL = "v3_Multimodal/src"
CFG_REL = "v3_Multimodal/config"

TOP_KEYS = ["audit_version", "verdict", "audited_at_kst", "sealed_sha256", "sealed_counts",
            "stat_fingerprints", "access_log_lines", "frozen_118_sha256", "report_path"]
COUNT_KEYS = ["n_sealed_dirs", "n_sealed_files_total", "n_sealed_artifacts", "n_access_log"]
MARKER_RE = {
    "expected_manifest_v3": re.compile(r"^\s*expected_manifest_v3 sha256: ([0-9a-f]{64})\s*$"),
    "audit_script": re.compile(r"^\s*audit_script sha256: ([0-9a-f]{64})\s*$"),
    "selftest": re.compile(r"^\s*selftest sha256: ([0-9a-f]{64})\s*$"),
    "audit_script_r2": re.compile(r"^\s*audit_script_r2 sha256: ([0-9a-f]{64})\s*$"),
    "selftest_r2": re.compile(r"^\s*selftest_r2 sha256: ([0-9a-f]{64})\s*$"),
}
KST = datetime.timezone(datetime.timedelta(hours=9))
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")
CHUNK = 1 << 20

# ── 기대 상수 (F1~F5 · 블록 BC 종료본 · cowork 재측정 2026-10-05) ─────────────────
REAL_EXPECTED = {
    "git": {"head": "566f487", "n_commits": 21, "n_modified": 5},
    "counts": {"n_sealed_dirs": 39, "n_sealed_files_total": 826, "n_sealed_artifacts": 801, "n_access_log": 25},
    "sealed_bytes_total": 433719423,
    "fingerprints": {
        "existing": "d984c66b898dcbeebf305a16ded5b7036f277d2c77f3eec35995f7f1153dea84",
        "existing__no_access": "7b617e1ccf2b3f377204df5c8504906a60cdb06269aa268d813179df7fcbb7d3",
        "confirm_gin": "54db739fd07cae92b7665267f28720d52645ff19784777d4b4b3752148ac6776",
        "confirm_gin__no_access": "1992ab00977b3afd18ce42a678adacd28e2233f5a58dbd1baa05d65289d8287d",
        "stability": "01578eda438edce87ce30dfabb89d242b55ddf3cd0e3ebefa06e29f3f222d7ec",
        "stability__no_access": "65f08361b640c5ebdfab3e9a97f7b235b7e09d77be1c22e32060a46ff5b97843",
        "gin_consensus": "2d52c9ac03961a6a7610ff7cfee6758fd957c6584867e47e44cb7f62548d11df",
        "gin_consensus__no_access": "d061293d808f8e216d5bc08322eee19929573eba94f14407a0c8e6d68f2ebe95",
        "leverage": "f0829db7e97b7fa37722265f311388c2d592b2458b2dbf514fe4748c0dc5a836",
        "leverage__no_access": "ed9b860561880707c500e49f8d01c8bf4e3e5a263502b79c79d6e7335b3c179c",
        "holm8": "4177f61de8f3fd60a59d537b0683634a21e3dbe0e508c60da5dc4ee1ebcafc5e",
        "holm8__no_access": "5f91169f431972f95fca05a8cb1742789810a3dc987658930d5e26f61356ac6d",
        "d12": "33a9e057a7786722cb5a7dc640dd63700855eeb7977be8d883f722290bcfd93d",
        "d12__no_access": "0ce62d855f64461fcb775267ae4adaf8bd72a778ff60aeb11612a047c92783da",
        "s6": "19a79b7f57c3febd5493d650c500c2fabeb5e4ed89b725aa6ec58c7eb5c70735",
        "s6__no_access": "bf0c166796fd5d8153090cc0a1ea2cead439ee71b86b12126871ea3d7b0230fc",
        "sens": "6e9a581d7181d5283e599d41661d9588bbd4ab6988f3b87af0a8026bb714e083",
        "sens__no_access": "6e9a581d7181d5283e599d41661d9588bbd4ab6988f3b87af0a8026bb714e083",
    },
    "access_lines": {
        "experiments/runs/v3_confirm_rep1_seed201": 18,
        "experiments/runs/v3_confirm_rest_consensus_rep123": 9,
        "experiments/runs/v3_confirm_rest_rep1_seed201": 9,
        "experiments/runs/v3_confirm_rest_rep2_seed202": 7,
        "experiments/runs/v3_confirm_rest_rep3_seed203": 7,
        "experiments/runs/v3_confirm_rftuned_rep1_seed201": 1,
        "experiments/runs/v3_confirm_rftuned_rep2_seed202": 1,
        "experiments/runs/v3_confirm_rftuned_rep3_seed203": 1,
        "experiments/runs/v3_consensus_rep123": 23,
        "experiments/runs/v3_gin_confirm_consensus_rep123": 5,
        "experiments/runs/v3_gin_confirm_rep1_seed201": 26,
        "experiments/runs/v3_gin_confirm_rep2_seed202": 26,
        "experiments/runs/v3_gin_confirm_rep3_seed203": 25,
        "experiments/runs/v3_gin_stability": 5,
        "experiments/runs/v3_latefusion_rep1_seed201": 5,
        "experiments/runs/v3_latefusion_rep2_seed202": 5,
        "experiments/runs/v3_latefusion_rep3_seed203": 5,
        "experiments/runs/v3_null_MAIN": 8,
        "experiments/runs/v3_rqint_d12": 3,
        "experiments/runs/v3_rqint_holm8": 2,
        "experiments/runs/v3_rqint_leverage_d11": 4,
        "experiments/runs/v3_stability_ss15": 1,
        "experiments/runs/v3_stratification": 6,
        "experiments/runs/v3_stratification_axes": 15,
        "experiments/runs/v3_stratification_pid": 6,
    },
    "freeze_manifest_sha256": "4ed6a5e4a9df67347d7dc1441b25c4e15441838981237741bb5a66b8f8665a9c",
    "f4_other": {
        "docs/118b_external_validation_plan.md": "4f06d39e9aa827bd63a2ac28e6dbedbedec2430bbde10aaadd567c81c726f60e",
        "data/processed/master_X.parquet": "788c8a64d19e8c3cc030476e7b2eb7f207246e3af6e73304d97f2fc9aa2ae6e6",
        "data/processed/master_Y.parquet": "bd23584342de6482e50f218bd409740acc2a00eeac86ee95bd89952bc3d18018",
        "v3_Multimodal/src/pre_unblinding_audit.py": "224a5c8b81cf0b58ebb79560f566470b4792af030f0865a3d0910855dbfdf996",
        "v3_Multimodal/src/pre_unblinding_audit_v2.py": "13cf681aab2a5e94b7e77976e30e98524545182d76e59ac7f5fd120ca796539b",
        "v3_Multimodal/src/sap/decision.py": "f688b20d816acabe17c2906cfa846c1f794ba45a416248c08aa7e41676e82a92",
        "v3_Multimodal/src/sap/signflip.py": "3de1223585ae0f978438bacfdd8e439c7f0ce95b776d615d098a5881e6ce06d2",
        "v3_Multimodal/src/sap/bootstrap.py": "05437c516e606a053e02acefb23c2597365472201b6c70ff2814278d6597a31e",
        "v3_Multimodal/src/sap/metrics.py": "a7d3fe4fe9e87983b35b086b0c464bde1e710e013f98813a2f28a2b48c8b2004",
        "v3_Multimodal/src/sap/consensus.py": "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91",
        "v3_Multimodal/src/sap/__init__.py": "8dc63e28ffcf93dcdfde7facd0cf1d51b6e6c15ac4de2304de61c12ccb7a5306",
        "v3_Multimodal/src/sap/rqint.py": "eb842bc98140e9c55b67bc1563cd5573c3b294885778f23744468b712c498b26",
        "v3_Multimodal/src/sap/null_generator.py": "90886abce256a130531a0ab0cd8edd17abc27ff1b62ee56f24248aa76fa204c7",
        "experiments/sap/manifest.json": "d08dcedf2a22e1c8493c842507422de1f6c705ce54ce995e038e09f604706e10",
        "v3_Multimodal/config/rqint_downstream_spec_v1.json": "fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf",
        "v3_Multimodal/config/rqint_downstream_spec_v1_amendment1.json": "63c29d6b6a9e22951f2e2891b54f4251d5e4f679fc1d3b3f110cfdf510aab05c",
        "v3_Multimodal/config/rqint_downstream_spec_v1_amendment2.json": "c8e1e2569e7f62fe14a49bdd5581baf3d2d9da9fb411e15099cd85a01bf1a3d8",
        "v3_Multimodal/config/rqint_downstream_spec_v1_amendment3.json": "ed054b4a374d8cce69163ff3c3913c3188ad1f436253068ba65dd682198b3fd2",
        "v3_Multimodal/config/post_interim_freeze_v1_0.json": "502db732bd5e45cbe0d1da78106f639c0f65261e1215af9912250e1ffa284258",
        "v3_Multimodal/config/holm7_latefusion_freeze.json": "d89f8c52412b656e467accbda4e1e9a36aaba14830be5b3d81ca756e54b357c1",
        "v3_Multimodal/config/rqint_procedure_decisions_v1.json": "16776f21df6ae29b8805272ba39b59b522693217ee113e307a3b3cd3819a96ca",
        "v3_Multimodal/config/ladder_freeze.json": "b885585aefbabb32f432b2e60141f6b12ac8bdf971066a9434021762e6ef0868",
        "v3_Multimodal/src/confirmatory_oof_rep1.py": "afb894c09fdaad6f1c75df789c5e2ede1dbbc2151a8c30b8eda6044cd6f336b6",
        "v3_Multimodal/src/confirmatory_oof_sens.py": "967f3749cb0796e7202de6723e1694d96c4605dc2e5374972f739c6f812e76d9",
        "experiments/runs/v3_confirm_sens/manifest_public.json": "9a1b9230fdc3b66a072a6b2de13875199b6cd6f3a26037bb612c8db25a284752",
    },
    "egroup_counts": {"E-A": 275, "E-B": 387, "E-C": 45, "E-D": 22, "E-E": 11, "E-F": 61},
    "n_total": 801,
    "n_no_creation_hash": 8,
    "pycache_dirs": 4541,
    "stale_lock_lines": 3,
}


class GuardViolation(Exception):
    pass


class PreconditionFail(Exception):
    pass


# ═══════════════════════════════════════════════════════════════════════════
# 공용 유틸
# ═══════════════════════════════════════════════════════════════════════════
_STATE = {"fixture_root": None}


def now_kst():
    t = datetime.datetime.now(KST)
    return t.strftime("%Y-%m-%d %H:%M:%S.") + "%03d KST" % (t.microsecond // 1000)


def ns_to_kst(ns):
    t = datetime.datetime.fromtimestamp(ns // 1000000000, KST)
    return t.strftime("%Y-%m-%d %H:%M:%S.") + "%03d KST" % ((ns % 1000000000) // 1000000)


def parse_kst(s):
    m = re.match(r"^(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d(?::\d\d)?)(?:\.\d+)?(?:\s*KST|\+09:00)?$", s.strip())
    if not m:
        return None
    hm = m.group(2) if m.group(2).count(":") == 2 else m.group(2) + ":00"
    return datetime.datetime.strptime(m.group(1) + " " + hm, "%Y-%m-%d %H:%M:%S")


def _is_sealed_path(p):
    return "_sealed" in os.path.abspath(os.fsdecode(p)).split(os.sep)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(CHUNK), b""):
            h.update(c)
    return h.hexdigest()


def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


def read_json_public(p):
    """공개 JSON 판독 — 봉인 경로면 즉시 실패."""
    if _is_sealed_path(p):
        raise GuardViolation("sealed json read refused")
    return json.loads(read_bytes(p).decode("utf-8"))


def read_jsonl_public(p):
    if _is_sealed_path(p):
        raise GuardViolation("sealed jsonl read refused")
    return [json.loads(ln) for ln in read_bytes(p).decode("utf-8").split("\n") if ln.strip()]


def read_text_public(p):
    if _is_sealed_path(p):
        raise GuardViolation("sealed text read refused")
    return read_bytes(p).decode("utf-8")


def _safe_write(path, data):
    """유일한 쓰기 경로. `_sealed` 대상 쓰기는 selftest 가짜 저장소 안에서만 허용."""
    ap = os.path.abspath(path)
    fr = _STATE["fixture_root"]
    if _is_sealed_path(ap) and not (fr and ap.startswith(fr + os.sep)):
        raise GuardViolation("sealed write refused")
    if isinstance(data, str):
        data = data.encode("utf-8")
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    tmp = ap + ".partial"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ap)


def dumps(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


@contextlib.contextmanager
def no_sealed_io():
    """build-expected 가드 — `_sealed` 경로의 open·walk·listdir·scandir 가 일어나면 즉시 실패(Y6 비순환)."""
    o_open, o_listdir, o_scandir = builtins.open, os.listdir, os.scandir

    def _chk(p):
        if isinstance(p, (str, bytes, os.PathLike)) and _is_sealed_path(p):
            raise GuardViolation("sealed io during build-expected")

    def g_open(file, *a, **k):
        _chk(file)
        return o_open(file, *a, **k)

    def g_listdir(path="."):
        _chk(path)
        return o_listdir(path)

    def g_scandir(path="."):
        _chk(path)
        return o_scandir(path)

    builtins.open, os.listdir, os.scandir = g_open, g_listdir, g_scandir
    try:
        yield
    finally:
        builtins.open, os.listdir, os.scandir = o_open, o_listdir, o_scandir


def _dig(o, dotted):
    for k in dotted.split("."):
        o = o[k]
    return o


# ── writer 소스 근거 (AST · file:line) ───────────────────────────────────────
def ast_assign(root, rel, name):
    """모듈 안 첫 `name = <literal>` 의 값과 줄 번호."""
    tree = ast.parse(read_text_public(os.path.join(root, rel)))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            try:
                return ast.literal_eval(node.value), "%s:%d" % (rel, node.lineno)
            except ValueError:
                continue
    return None, None


def literal_line(root, rel, literal):
    """소스에 문자열 상수 `literal` 이 처음 나오는 줄 (AST Constant)."""
    tree = ast.parse(read_text_public(os.path.join(root, rel)))
    best = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == literal:
            best = node.lineno if best is None else min(best, node.lineno)
    return None if best is None else "%s:%d" % (rel, best)


def str_constants(root, rel):
    tree = ast.parse(read_text_public(os.path.join(root, rel)))
    return {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def text_line(root, rel, needle):
    for i, ln in enumerate(read_text_public(os.path.join(root, rel)).split("\n"), 1):
        if needle in ln:
            return "%s:%d" % (rel, i)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# stat (unblinding_run.stat_summary 와 같은 규칙 — 독립 구현 · U11 오라클 대조)
# ═══════════════════════════════════════════════════════════════════════════
def sealed_stat_v3(root):
    lines, dirs = [], 0
    for dp, _dn, fn in os.walk(root):
        parts = dp.split(os.sep)
        if ".git" in parts:
            continue
        if os.path.basename(dp) == "_sealed":
            dirs += 1
        if "_sealed" not in parts:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            lines.append((os.path.relpath(p, root), os.path.getsize(p), f == "access.log"))
    return dirs, lines


def _fp(sel):
    s = sorted("%s\t%d" % (r, b) for r, b, _a in sel)
    return sha_bytes(("\n".join(s) + "\n").encode("utf-8"))


def stat_summary_v3(root, groups):
    dirs, lines = sealed_stat_v3(root)
    named = [p for g, ps in groups.items() if g != "__rest__" for p in ps]
    fps = {}
    for g, ps in groups.items():
        if g == "__rest__":
            sel = [x for x in lines if not any(x[0].startswith(p + os.sep) for p in named)]
        else:
            sel = [x for x in lines if any(x[0].startswith(p + os.sep) for p in ps)]
        name = "existing" if g == "__rest__" else g
        fps[name] = _fp(sel)
        fps[name + "__no_access"] = _fp([x for x in sel if not x[2]])
    acc = {}
    for r, _b, a in lines:
        if a:
            acc[os.path.dirname(os.path.dirname(r))] = read_bytes(os.path.join(root, r)).count(b"\n")
    n_acc = sum(1 for x in lines if x[2])
    counts = {"n_sealed_dirs": dirs, "n_sealed_files_total": len(lines), "n_sealed_artifacts": len(lines) - n_acc,
              "n_access_log": n_acc}
    return counts, fps, acc


def group_of(rel, groups):
    for g, ps in groups.items():
        if g != "__rest__" and any(rel.startswith(p + os.sep) for p in ps):
            return g
    return "existing"


def scan_live(root):
    """B-1 1 — 저장소 전역 walk(.git 제외 · 링크 미추적) · basename `_sealed` 디렉터리 재귀 · stat 만."""
    dirs, files = [], {}
    for dp, dn, fn in os.walk(root):
        rel_dp = os.path.relpath(dp, root)
        parts = rel_dp.split(os.sep)
        if ".git" in parts:
            dn[:] = []
            continue
        if os.path.basename(dp) == "_sealed":
            dirs.append(rel_dp)
        if "_sealed" not in parts:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            st = os.lstat(p)
            files[os.path.relpath(p, root)] = {"bytes": st.st_size, "mtime_ns": st.st_mtime_ns,
                                               "access": f == "access.log"}
    glob_equal = all(re.fullmatch(r"experiments/runs/[^/]+/_sealed", d) for d in dirs)
    return sorted(dirs), files, glob_equal


# ═══════════════════════════════════════════════════════════════════════════
# A-3 독립 기대목록 (기록물 + 설계 격자 + writer 소스 · live 열거 0 · 봉인 판독 0)
# ═══════════════════════════════════════════════════════════════════════════
CTX_KEYS = ("sealed_path", "path", "name", "tree", "run_dir", "sealed_dir")


SIB_KEYS = ("name", "path")


def _walk_refs(o, path, ctx, out, sib=()):
    """(키 경로 · 조상 문맥 · 직속 형제 name/path · sha · 종류). 형제는 hex 를 직접 담은 dict 의 것만."""
    if isinstance(o, dict):
        c2 = ctx + [v for k, v in o.items() if k in CTX_KEYS and isinstance(v, str)]
        s2 = [v for k, v in o.items() if k in SIB_KEYS and isinstance(v, str)]
        for k, v in o.items():
            _walk_refs(v, path + [str(k)], c2, out, s2)
    elif isinstance(o, list):
        for v in o:
            _walk_refs(v, path + ["#"], ctx, out)
    elif isinstance(o, str):
        if HEX64.match(o):
            out.append((path, ctx, o, 64, list(sib)))
        elif HEX16.match(o) and any("sha16" in p for p in path):
            out.append((path, ctx, o, 16, list(sib)))


def _resolve(path_tokens, ctx, source_rel, items, by_base, sib=()):
    toks = path_tokens + ctx
    for t in list(path_tokens) + list(sib):   # 직결 = 키 경로 · 직속 형제만 (조상 `sealed_path` 는 산출 파일이라 제외)
        m = re.search(r"(experiments/runs/[^\s'\"{}]+?/_sealed/[^\s'\"{}]+)", t)
        if m and m.group(1) in items:
            return [m.group(1)], "direct"
    base = None
    for t in list(reversed(path_tokens)) + list(sib):
        b = t.rsplit("/", 1)[-1]
        if b in by_base:
            base = b
            break
    if base is None:
        return [], "unresolved"
    cands = list(by_base[base])
    m = re.match(r"experiments/runs/([^/]+)/", source_rel)
    if m:
        c = [p for p in cands if p.startswith("experiments/runs/" + m.group(1))]
        if c:
            cands = c
    for t in ctx:
        t2 = t.rstrip("/")
        if t2.startswith("experiments/runs/"):
            c = [p for p in cands if p.startswith(t2 + "/") or p.startswith(t2 + "_")]
            if c:
                cands = c
    reps = set()
    for t in toks:
        reps |= {int(x) for x in re.findall(r"(?:^|[/_])rep(\d)(?=$|[/_])", t)}
    if len(reps) == 1:
        r = reps.pop()
        c = [p for p in cands if ("rep%d_" % r) in p]
        if c:
            cands = c
    return sorted(cands), "basename"


def secondary_scan(root, sec, items):
    """Y5 — 보조 기록원(FLL · ledger · 트리 *_public/config/_run_state/_consensus_state · AO v1)의 sha 항목이
    기대 파일을 가리키면 일치 의무. 불일치 = source_conflict(차단)."""
    by_base = {}
    for p in items:
        by_base.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    files = list(sec.get("files", []))
    rd = os.path.join(root, sec["runs_dir"])
    for d in sorted(os.listdir(rd)):
        dp = os.path.join(rd, d)
        if d.startswith(".") or not os.path.isdir(dp):
            continue
        for f in sorted(os.listdir(dp)):
            if any(fnmatch.fnmatch(f, pat) for pat in sec["patterns"]) and os.path.isfile(os.path.join(dp, f)):
                files.append("%s/%s/%s" % (sec["runs_dir"], d, f))
    stats = {"n_sources": 0, "n_refs": 0, "n_resolved": 0, "n_consistent": 0, "n_unresolved": 0,
             "n_unresolved_value_match": 0, "n_deferred_via_checkpoint": 0}
    conflicts, per_source, unreadable, deferred = [], {}, [], []
    known_sha = {it["expected_sha256"] for it in items.values()
                 if it["expected_sha256"] and HEX64.match(it["expected_sha256"])}
    for rel in files:
        try:
            obj = read_json_public(os.path.join(root, rel))
        except (ValueError, UnicodeDecodeError, OSError):
            unreadable.append(rel)
            continue
        refs = []
        _walk_refs(obj, [], [], refs)
        stats["n_sources"] += 1
        ps = {"n_refs": 0, "n_consistent": 0, "n_unresolved": 0, "n_conflict": 0}
        for path, ctx, hx, kind, sib in refs:
            cands, how = _resolve(path, ctx, rel, items, by_base, sib)
            stats["n_refs"] += 1
            ps["n_refs"] += 1
            if not cands:
                stats["n_unresolved"] += 1
                ps["n_unresolved"] += 1
                if (hx in known_sha) if kind == 64 else any(k.startswith(hx) for k in known_sha):
                    stats["n_unresolved_value_match"] += 1
                continue
            stats["n_resolved"] += 1
            known = [c for c in cands if items[c]["expected_sha256"] and HEX64.match(items[c]["expected_sha256"])]
            if not known:
                y4 = [c for c in cands if items[c]["class"] == "no_creation_hash"]
                if y4:
                    conflicts.append({"code": "y4_has_record", "source": rel, "key_path": "/".join(path),
                                      "candidates": y4[:5]})
                via = [c for c in cands if items[c]["class"] == "recorded_via_checkpoint"]
                if via and kind == 64:
                    stats["n_deferred_via_checkpoint"] += 1
                    deferred.append({"source": rel, "key_path": "/".join(path), "targets": via[:5], "sha256": hx})
                continue
            ok = any((items[c]["expected_sha256"] == hx) if kind == 64 else items[c]["expected_sha256"].startswith(hx)
                     for c in known)
            if ok:
                stats["n_consistent"] += 1
                ps["n_consistent"] += 1
                for c in known:
                    if (items[c]["expected_sha256"] == hx) if kind == 64 else items[c]["expected_sha256"].startswith(hx):
                        src = "%s:%s" % (rel, "/".join(path))
                        if src not in items[c]["secondary_sources"]:
                            items[c]["secondary_sources"].append(src)
            else:
                ps["n_conflict"] += 1
                conflicts.append({"code": "source_conflict", "source": rel, "key_path": "/".join(path),
                                  "resolution": how, "n_candidates": len(known), "candidates": known[:5],
                                  "recorded_sha16": hx[:16]})
        per_source[rel] = ps
    stats["n_conflicts"] = len(conflicts)
    return {"stats": stats, "per_source": per_source, "conflicts": conflicts, "unreadable": unreadable,
            "deferred_via_checkpoint": deferred,
            "patterns": sec["patterns"], "files_fixed": sec.get("files", [])}


def build_expected(root, spec):
    with no_sealed_io():
        return _build_expected(root, spec)


def _build_expected(root, spec):
    J = lambda rel: os.path.join(root, rel)                         # noqa: E731
    groups, R, G = spec["groups"], spec["recorders"], spec["grid"]
    inputs, blocking, items = {}, [], {}

    def load(rel, exp_sha=None):
        b = read_bytes(J(rel))
        s = sha_bytes(b)
        inputs[rel] = {"bytes": len(b), "sha256": s}
        if exp_sha and s != exp_sha:
            blocking.append({"code": "recorder_sha_mismatch", "path": rel})
        return json.loads(b.decode("utf-8"))

    def add(path, sha, source, cls, nbytes=None, rule=None):
        g = group_of(path, groups)
        it = items.get(path)
        if it is None:
            it = items[path] = {"path": path, "expected_sha256": sha, "expected_bytes": nbytes, "sources": [],
                                "secondary_sources": [], "class": cls, "group": g, "egroup": spec["egroup_of"][g]}
            if rule:
                it["rule"] = rule
        else:
            if sha and it["expected_sha256"] and sha != it["expected_sha256"]:
                blocking.append({"code": "source_conflict", "path": path, "sources": it["sources"] + [source]})
            if nbytes is not None and it["expected_bytes"] is not None and nbytes != it["expected_bytes"]:
                blocking.append({"code": "source_conflict_bytes", "path": path})
            if sha and not it["expected_sha256"]:
                it["expected_sha256"] = sha
            if nbytes is not None and it["expected_bytes"] is None:
                it["expected_bytes"] = nbytes
        it["sources"].append(source)

    # E-A — AO v2 (블록 AO 시점 전 봉인)
    ao = R["ao"]
    A = load(ao["path"], ao.get("sha256"))
    for p, s in sorted(_dig(A, ao["key"]).items()):
        add(p, s, "%s:%s" % (ao["path"], ao["key"]), "recorded")

    # E-B — 확증 GIN (manifest_t4 · 격자 · checkpoint 투영은 Phase B)
    cf = R["confirm"]
    T4 = load(cf["path"], cf.get("sha256"))
    tree_of = lambda r, s: cf["tree_fmt"].format(r=r, s=s)          # noqa: E731
    keyre = re.compile(r"^rep(\d+)_seed(\d+)$")
    rec_oof = {}
    for k, s in sorted(T4["oof_sha256"].items()):
        rk, fn = k.split("/", 1)
        m = keyre.match(rk)
        t = tree_of(int(m.group(1)), int(m.group(2)))
        rec_oof.setdefault(t, set()).add(fn)
        add("%s/_sealed/%s" % (t, fn), s, "%s:oof_sha256/%s" % (cf["path"], k), "recorded")
    for k, s in sorted(T4["checkpoint_sha256"].items()):
        m = keyre.match(k)
        add("%s/_sealed/checkpoint.jsonl" % tree_of(int(m.group(1)), int(m.group(2))), s,
            "%s:checkpoint_sha256/%s" % (cf["path"], k), "recorded")
    for k, v in sorted((T4.get("per_repeat") or {}).items()):
        m = keyre.match(k)
        if m and isinstance(v, dict) and v.get("checkpoint_sha256"):
            add("%s/_sealed/checkpoint.jsonl" % tree_of(int(m.group(1)), int(m.group(2))), v["checkpoint_sha256"],
                "%s:per_repeat/%s/checkpoint_sha256" % (cf["path"], k), "recorded")

    wc, ws = G["writer_confirm"], G["writer_stab"]
    models, models_at = ast_assign(root, wc, "MODELS")
    ckpt_fields, ckpt_at = ast_assign(root, wc, "CKPT_FIELDS")
    allowed_c, allowed_c_at = ast_assign(root, wc, "allowed_top")
    allowed_s, allowed_s_at = ast_assign(root, ws, "allowed_top")
    part_fmt_at = literal_line(root, wc, G["confirm_partial_fmt"])
    oof_fmt_at = literal_line(root, wc, G["confirm_oof_fmt"])
    stab_fmt_at = literal_line(root, ws, G["stab_partial_fmt"])
    gsf = load(G["gin_seed_freeze"])
    ladder = load(G["ladder"])
    pc = load(G["plan_confirm"])
    pst = load(G["plan_stab"])
    seeds = list(gsf["confirmatory_seed_prefix"])
    rep_seed = {int(k): int(v) for k, v in pc["rep_seed_map"].items()}
    folds = list(range(G["n_folds"]))
    grid_units = {(r, f, m, t) for r in rep_seed for f in folds for m in models for t in seeds}
    plan_units = {(u["rep"], u["fold"], u["model"], u["train_seed"]) for u in pc["units"]}
    lf_models = ladder["models_frozen"]
    grid_checks = {
        "writer_rules_found": all([models_at, ckpt_at, allowed_c_at, allowed_s_at, part_fmt_at, oof_fmt_at,
                                   stab_fmt_at]),
        "confirm_models_eq_gin_seed_freeze_scope": list(models) == list(gsf["model_scope_stability"]),
        "confirm_models_subset_ladder": set(models) <= set(lf_models),
        "confirm_grid_eq_plan_units": grid_units == plan_units and len(pc["units"]) == len(plan_units),
        "confirm_n_units": len(grid_units),
    }
    grid_oof = {tree_of(r, s): {G["confirm_oof_fmt"] % (m, t) for m in models for t in seeds}
                for r, s in rep_seed.items()}
    grid_checks["confirm_oof_recorder_eq_grid"] = rec_oof == grid_oof
    if not grid_checks["confirm_oof_recorder_eq_grid"]:
        blocking.append({"code": "grid_mismatch", "group": "confirm_gin", "what": "oof"})
    ck_keys = list(G["projection_keys"])
    for (r, f, m, t) in sorted(grid_units):
        tr = tree_of(r, rep_seed[r])
        add("%s/_sealed/_partial/%s" % (tr, G["confirm_partial_fmt"] % (m, f, t)), "via_checkpoint",
            "%s/_sealed/checkpoint.jsonl:artifact_sha256(rep=%d,fold=%d,model=%s,train_seed=%d)" % (tr, r, f, m, t),
            "recorded_via_checkpoint",
            rule={"checkpoint": "%s/_sealed/checkpoint.jsonl" % tr, "projection_keys": ck_keys,
                  "ckpt_fields_at": ckpt_at, "filename_rule_at": part_fmt_at})
    y4 = []
    for r, s in sorted(rep_seed.items()):
        for nm in G["y4_names"]:
            p = "%s/_sealed/%s" % (tree_of(r, s), nm)
            y4.append(p)
            add(p, None, "none — %s" % ("allowed_top" if nm in allowed_c else "NOT_IN_allowed_top"), "no_creation_hash",
                rule={"existence_evidence_at": allowed_c_at if nm in allowed_c else None,
                      "mtime_bound_kst": T4["ts_kst"], "mtime_bound_source": "%s:ts_kst" % cf["path"],
                      "history_group": "confirm_gin"})

    # E-C — 안정성 (manifest_s2 · 격자)
    sb = R["stability"]
    S2 = load(sb["path"], sb.get("sha256"))
    rec_stab = set()
    for bn, s in sorted(S2["partial_sha256"].items()):
        rec_stab.add(bn)
        add("%s/_sealed/_partial/%s" % (sb["tree"], bn), s, "%s:partial_sha256/%s" % (sb["path"], bn), "recorded")
    add("%s/_sealed/checkpoint.jsonl" % sb["tree"], S2["checkpoint_sha256"], "%s:checkpoint_sha256" % sb["path"],
        "recorded")
    inv = {v: k for k, v in {int(k): int(v) for k, v in pst["rep_seed_map"].items()}.items()}
    stab_seeds = list(gsf["training_seeds_ordered"])[len(seeds):]
    grid_stab = {G["stab_partial_fmt"] % (m, inv[ss], f, t) for ss, f in gsf["representative_units"]
                 for m in gsf["model_scope_stability"] for t in stab_seeds}
    plan_stab = {G["stab_partial_fmt"] % (u["model"], u["rep"], u["fold"], u["train_seed"]) for u in pst["units"]}
    grid_checks["stab_grid_eq_plan_units"] = grid_stab == plan_stab and len(pst["units"]) == len(plan_stab)
    grid_checks["stab_recorder_eq_grid"] = rec_stab == grid_stab
    grid_checks["stab_n_units"] = len(grid_stab)
    if not (grid_checks["stab_recorder_eq_grid"] and grid_checks["stab_grid_eq_plan_units"]):
        blocking.append({"code": "grid_mismatch", "group": "stability", "what": "partial"})
    if not (grid_checks["confirm_grid_eq_plan_units"] and grid_checks["writer_rules_found"]
            and grid_checks["confirm_models_eq_gin_seed_freeze_scope"] and grid_checks["confirm_models_subset_ladder"]):
        blocking.append({"code": "grid_mismatch", "group": "confirm_gin", "what": "design"})
    for nm in G["y4_names"]:
        p = "%s/_sealed/%s" % (sb["tree"], nm)
        y4.append(p)
        add(p, None, "none — %s" % ("allowed_top" if nm in allowed_s else "NOT_IN_allowed_top"), "no_creation_hash",
            rule={"existence_evidence_at": allowed_s_at if nm in allowed_s else None,
                  "mtime_bound_kst": S2["ts_kst"], "mtime_bound_source": "%s:ts_kst" % sb["path"],
                  "history_group": "stability"})
    for p in y4:
        if items[p]["rule"]["existence_evidence_at"] is None:
            blocking.append({"code": "y4_no_existence_evidence", "path": p})

    # E-D/E-E/E-F — manifest_public sealed_files
    for pm in R["public"]:
        M = load(pm["path"], pm.get("sha256"))
        for x in M["sealed_files"]:
            p = x["name"] if pm["mode"] == "repo" else "%s/%s" % (pm["tree"], x["name"])
            add(p, x["sha256"], "%s:sealed_files[%s]" % (pm["path"], x["name"]), "recorded", nbytes=x["bytes"])

    # Y4 이력 근거 — 그룹 __no_access 지문이 블록 완료 이후 기록에 실려 있는지(값 = 기대 상수)
    y4_history = {}
    for g, hrel in spec["y4_history"].items():
        fp = spec["expected"]["fingerprints"].get(g + "__no_access")
        y4_history[g] = {"source": hrel, "fingerprint": fp, "at": text_line(root, hrel, fp) if fp else None}

    sec = secondary_scan(root, spec["secondary"], items)
    blocking.extend(sec["conflicts"])
    rows = [items[p] for p in sorted(items)]
    eg = {}
    for it in rows:
        eg[it["egroup"]] = eg.get(it["egroup"], 0) + 1
    exp = spec["expected"]
    summary = {
        "n_total": len(rows),
        "n_secondary_deferred_via_checkpoint": len(sec["deferred_via_checkpoint"]),
        "by_egroup": dict(sorted(eg.items())),
        "by_class": {c: sum(1 for it in rows if it["class"] == c)
                     for c in ("recorded", "recorded_via_checkpoint", "no_creation_hash")},
        "n_source_conflicts": sum(1 for b in blocking if b["code"].startswith("source_conflict")),
        "grid_checks": grid_checks,
        "egroup_counts_match_expected": eg == exp["egroup_counts"],
        "n_total_match_expected": len(rows) == exp["n_total"],
        "n_no_creation_hash_match_expected": sum(1 for it in rows if it["class"] == "no_creation_hash")
        == exp["n_no_creation_hash"],
    }
    if not (summary["egroup_counts_match_expected"] and summary["n_total_match_expected"]
            and summary["n_no_creation_hash_match_expected"]):
        blocking.append({"code": "expected_count_mismatch"})
    return {
        "_doc": "블록 BD (docs/119 A-3) 독립 기대목록 — 기록물 + 동결 설계 격자 + writer 소스(file:line)만으로 작성. "
                "live 디렉터리 열거 0 · 봉인 바이트 판독 0(no_sealed_io 가드). E-B partial 의 기대 sha 는 Phase B 에서 "
                "확증 checkpoint.jsonl 투영(§2-3)으로 확정한다(expected_sha256 = via_checkpoint).",
        "block": BLOCK, "instruction": INSTRUCTION, "built_at_kst": now_kst(),
        "inputs": dict(sorted(inputs.items())),
        "writer_rules": {"confirm_models": list(models), "confirm_models_at": models_at,
                         "ckpt_fields": list(ckpt_fields or []), "ckpt_fields_at": ckpt_at,
                         "projection_keys": ck_keys, "allowed_top_confirm_at": allowed_c_at,
                         "allowed_top_stability_at": allowed_s_at, "confirm_partial_fmt": G["confirm_partial_fmt"],
                         "confirm_partial_fmt_at": part_fmt_at, "confirm_oof_fmt": G["confirm_oof_fmt"],
                         "confirm_oof_fmt_at": oof_fmt_at, "stab_partial_fmt": G["stab_partial_fmt"],
                         "stab_partial_fmt_at": stab_fmt_at, "confirm_seeds": seeds, "stab_seeds": stab_seeds,
                         "n_folds": G["n_folds"], "rep_seed": {str(k): v for k, v in sorted(rep_seed.items())}},
        "y4_paths": sorted(y4), "y4_history": y4_history,
        "secondary": sec, "summary": summary, "blocking": blocking,
        "items": rows,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Phase B — 투영 · 대조 · 열람 대장 · 운영 사건 · R-d · 대장 3벌 · 서명 · 범위 밖 사본 · 문면 정정
# ═══════════════════════════════════════════════════════════════════════════
def project_checkpoint(path, keep, all_fields):
    """§2-3 — 줄마다 object_pairs_hook 로 키 이름만 기록하고 화이트리스트 밖 값은 버린다."""
    names, rows = [], []

    def hook(pairs):
        names.append(tuple(k for k, _v in pairs))
        return {k: v for k, v in pairs if k in keep}

    for ln in read_bytes(path).decode("utf-8").split("\n"):
        if ln.strip():
            rows.append(json.loads(ln, object_pairs_hook=hook))
    fmt_ok = len(names) == len(rows) and all(len(n) == len(all_fields) and set(n) == set(all_fields) for n in names)
    return rows, fmt_ok


def do_projection(root, man, hashes, blocking):
    """E-B partial 기대 sha 확정. checkpoint 파일 sha 가 기록원과 먼저 일치해야 한다."""
    items = {it["path"]: it for it in man["items"]}
    wr = man["writer_rules"]
    keep, allf = wr["projection_keys"], wr["ckpt_fields"]
    by_ck = {}
    for it in man["items"]:
        if it["class"] == "recorded_via_checkpoint":
            by_ck.setdefault(it["rule"]["checkpoint"], set()).add(it["path"])
    out = {}
    for ck, parts in sorted(by_ck.items()):
        info = {"n_expected_partials": len(parts)}
        exp = items[ck]["expected_sha256"]
        live_sha = hashes.get(ck)
        info["checkpoint_sha_matches_recorder"] = live_sha is not None and live_sha == exp
        if not info["checkpoint_sha_matches_recorder"]:
            blocking.append({"code": "checkpoint_sha_mismatch", "path": ck})
            out[ck] = info
            continue
        rows, fmt_ok = project_checkpoint(os.path.join(root, ck), keep, allf)
        info["n_rows"] = len(rows)
        info["format_ok"] = fmt_ok
        if not fmt_ok:
            blocking.append({"code": "checkpoint_format", "path": ck})
            out[ck] = info
            continue
        tree = ck.rsplit("/_sealed/", 1)[0]
        m = re.search(r"rep(\d+)_seed(\d+)$", tree)
        got, conflict, bad_rep = {}, 0, 0
        for r in rows:
            if m and int(r["rep"]) != int(m.group(1)):
                bad_rep += 1
            p = "%s/_sealed/_partial/%s" % (tree, wr["confirm_partial_fmt"] % (r["model"], int(r["fold"]),
                                                                               int(r["train_seed"])))
            if p in got and got[p] != r["artifact_sha256"]:
                conflict += 1
            got[p] = r["artifact_sha256"]
        info.update({"n_distinct_units": len(got), "n_duplicate_rows": len(rows) - len(got),
                     "n_conflicting_duplicates": conflict, "n_rep_field_mismatch": bad_rep,
                     "names_eq_grid": set(got) == parts})
        if conflict:
            blocking.append({"code": "checkpoint_conflict", "path": ck})
        if bad_rep:
            blocking.append({"code": "checkpoint_format", "path": ck, "what": "rep"})
        if set(got) != parts:
            blocking.append({"code": "grid_mismatch", "path": ck, "n_missing": len(parts - set(got)),
                             "n_extra": len(set(got) - parts)})
        for p in parts & set(got):
            items[p]["expected_sha256"] = got[p]
        out[ck] = info
    return out


def compare(man, live, hashes, y4_ctx, blocking, nonblocking):
    """B-1 4 — 기대 ↔ live 양방향 대조 (누락 · 초과 · 바이트 · sha · Y4)."""
    exp_items = {it["path"]: it for it in man["items"]}
    live_art = {p: v for p, v in live.items() if not v["access"]}
    by = {}

    def row(eg):
        return by.setdefault(eg, {"expected": 0, "live": 0, "matched": 0, "missing": 0, "unexpected": 0,
                                  "sha_mismatch": 0, "size_mismatch": 0, "source_conflict": 0, "no_creation_hash": 0})
    status = {}
    for p, it in sorted(exp_items.items()):
        r = row(it["egroup"])
        r["expected"] += 1
        if p not in live_art:
            r["missing"] += 1
            blocking.append({"code": "missing", "path": p})
            status[p] = "missing"
            continue
        r["live"] += 1
        lv = live_art[p]
        st = "ok"
        if it["expected_bytes"] is not None and lv["bytes"] != it["expected_bytes"]:
            r["size_mismatch"] += 1
            blocking.append({"code": "size_mismatch", "path": p})
            st = "size_mismatch"
        if it["class"] == "no_creation_hash":
            r["no_creation_hash"] += 1
            ok, why = y4_check(p, it, lv, y4_ctx)
            if ok:
                nonblocking.append({"code": "no_creation_hash", "path": p, "first_baseline_sha16": hashes[p][:16]})
                st = "no_creation_hash" if st == "ok" else st
            else:
                blocking.append({"code": "y4_condition_failed", "path": p, "why": why})
                st = "y4_condition_failed"
        else:
            es = it["expected_sha256"]
            if not (es and HEX64.match(es)):
                blocking.append({"code": "expected_sha_unresolved", "path": p})
                st = "expected_sha_unresolved"
            elif hashes.get(p) != es:
                r["sha_mismatch"] += 1
                blocking.append({"code": "sha_mismatch", "path": p})
                st = "sha_mismatch"
        if st == "ok" or st == "no_creation_hash":
            r["matched"] += 1
        status[p] = st
    for p in sorted(set(live_art) - set(exp_items)):
        eg = "unexpected"
        row(eg)["unexpected"] += 1
        blocking.append({"code": "unexpected", "path": p})
        status[p] = "unexpected"
    for b in man.get("blocking", []):
        if b["code"].startswith("source_conflict"):
            for p in [b.get("path")] + list(b.get("candidates", [])):
                if p in exp_items:
                    row(exp_items[p]["egroup"])["source_conflict"] += 1
                    break
    return {"by_egroup": dict(sorted(by.items())), "n_expected": len(exp_items), "n_live": len(live_art)}, status


def y4_check(p, it, lv, ctx):
    rl = it["rule"]
    if not rl.get("existence_evidence_at"):
        return False, "no_existence_evidence"
    bound = parse_kst(rl["mtime_bound_kst"])
    t = datetime.datetime.fromtimestamp(lv["mtime_ns"] // 1000000000, KST).replace(tzinfo=None)
    if bound is None or t > bound:
        return False, "mtime_after_block_completion"
    g = rl["history_group"]
    h = ctx["history"].get(g) or {}
    if not h.get("at") or ctx["live_fps"].get(g + "__no_access") != h.get("fingerprint"):
        return False, "stat_history_inconsistent"
    return True, ""


def parse_access_line(ln):
    return json.loads(ln)


# ── 대응 규칙 (b) — 바이트로 고정된 문서화 수동 게이트 줄 (docs/119b Z1 · 등록 블록 리포트 문단) ──────────
MB_PATH = re.compile(r"`([^`\s]+/_sealed/access\.log)`")
MB_LINES = re.compile(r"(\d+)\s*줄\s*→\s*\**\s*(\d+)\s*줄")
MB_BYTES = re.compile(r"([\d,]+)\s*B\s*→\s*([\d,]+)\s*B")
MB_QUOTE = re.compile(r"`(\{[^`]*\})`")


def manual_gate_candidates(root, b):
    """등록 블록 리포트(sha 고정)를 빈 줄로 문단 분할 → 문단마다 백틱 access.log 경로 · 「N줄 → N+1줄」 ·
    「A B → C B」 · 백틱 한 줄 JSON 인용이 **각 정확히 1개**인 문단만 후보(조건 ①·②). 파싱 실패·모호 = 후보 0."""
    text = read_text_public(os.path.join(root, b["report"]))
    if sha_bytes(text.encode("utf-8")) != b["report_sha256"]:
        return {"report_sha_ok": False, "candidates": []}
    paras, cur = [], []
    for i, ln in enumerate(text.split("\n"), 1):
        if ln.strip():
            cur.append((i, ln))
        elif cur:
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    out = []
    for pl in paras:
        pt = "\n".join(ln for _i, ln in pl)
        paths, lt, bt, qs = MB_PATH.findall(pt), MB_LINES.findall(pt), MB_BYTES.findall(pt), MB_QUOTE.findall(pt)
        if not (len(paths) == len(lt) == len(bt) == len(qs) == 1):
            continue
        n0, n1 = int(lt[0][0]), int(lt[0][1])
        a0, a1 = int(bt[0][0].replace(",", "")), int(bt[0][1].replace(",", ""))
        try:
            q = json.loads(qs[0])
        except ValueError:
            continue
        tree = os.path.dirname(os.path.dirname(paths[0]))
        if n1 != n0 + 1 or a1 <= a0 or not isinstance(q, dict) or not q or tree not in b["trees"]:
            continue
        out.append({"tree": tree, "line_no": n1, "offset": a0, "length": a1 - a0, "quote": q,
                    "report_line": pl[0][0]})
    return {"report_sha_ok": True, "candidates": out}


def _jeq(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def manual_match(c, tree, line_no, off, length, e, ts, window):
    """조건 ③ 순번 == N+1 · ④ 시작 오프셋 == A · ⑤ 길이(개행 포함) == C − A · ⑥ 인용 ⊆ 줄(값 동일) · ⑦ ts 시간창."""
    lo, hi = parse_kst(window[0]), parse_kst(window[1])
    return (c["tree"] == tree and line_no == c["line_no"] and off == c["offset"] and length == c["length"]
            and all(k in e and _jeq(e[k], v) for k, v in c["quote"].items())
            and ts is not None and lo <= ts <= hi)


def audit_access(root, live, spec, blocking):
    """B6 — access.log 전 줄 파싱 · AO 기준선 이후 줄을 대응: (a) 블록 [착수, 완료] 시간창 + 트리 + writer purpose ·
    (b) `manual_lines_from_report` 등록 블록의 리포트 문단이 바이트로 고정한 수동 게이트 줄(docs/119b Z1)."""
    exp_lines = spec["expected"]["access_lines"]
    base = spec["access_baseline"]
    blocks = spec["blocks"]
    purposes = {}
    for b in blocks:
        cs = set()
        for w in b["writers"]:
            cs |= str_constants(root, w)
        purposes[b["id"]] = cs
    manual = {b["id"]: manual_gate_candidates(root, b) for b in blocks if b.get("manual_lines_from_report")}
    req = set(spec["access_required_keys"])
    per_file, n_unattr, n_human, n_fmt, n_open = {}, 0, 0, 0, 0
    manual_lines = []
    for p in sorted(x for x, v in live.items() if v["access"]):
        tree = os.path.dirname(os.path.dirname(p))
        raw = read_bytes(os.path.join(root, p))
        n_nl = raw.count(b"\n")
        text = raw.decode("utf-8")
        n_open += text.count("OPEN sealed")
        recs, pos = [], 0                                           # (시작 바이트 오프셋, 길이(개행 포함), 줄)
        for seg in raw.split(b"\n"):
            ln = seg.decode("utf-8")
            if ln.strip():                                          # AO opened_check 와 같은 행 규칙
                recs.append((pos, len(seg) + (1 if pos + len(seg) < len(raw) else 0), ln))
            pos += len(seg) + 1
        lines = [r[2] for r in recs]
        nb = base.get(p, 0)
        info = {"n_lines": n_nl, "expected_lines": exp_lines.get(tree), "ao_baseline": nb,
                "after_baseline": max(0, len(lines) - nb), "by_block": {}, "by_rule": {}, "n_human_exposure_true": 0,
                "n_type_not_machine_read": 0, "n_unattributed": 0, "n_format_error": 0, "first_ts": None,
                "last_ts": None}
        if exp_lines.get(tree) != n_nl:
            blocking.append({"code": "access_lines_changed", "tree": tree, "expected": exp_lines.get(tree),
                             "live": n_nl})
        if len(lines) < nb:
            blocking.append({"code": "access_lines_below_baseline", "tree": tree})
        for i, ln in enumerate(lines):
            post = i >= nb
            try:
                e = parse_access_line(ln)
                if not isinstance(e, dict) or (post and not (req <= set(e) and e.get("human_exposure") in (True, False))):
                    raise ValueError
            except ValueError:
                info["n_format_error"] += 1
                n_fmt += 1
                blocking.append({"code": "access_format", "tree": tree, "line": i + 1})
                continue
            ts = parse_kst(str(e.get("ts_kst") or e.get("ts") or ""))
            if ts is not None:
                s_ = ts.strftime("%Y-%m-%d %H:%M:%S")
                info["first_ts"] = info["first_ts"] or s_
                info["last_ts"] = s_
            if e.get("human_exposure") is True:
                info["n_human_exposure_true"] += 1
                n_human += 1
                blocking.append({"code": "human_exposure", "tree": tree, "line": i + 1})
            if e.get("type") != "machine_read":
                info["n_type_not_machine_read"] += 1
                blocking.append({"code": "access_type", "tree": tree, "line": i + 1})
            if not post:
                info["by_block"]["AO_baseline"] = info["by_block"].get("AO_baseline", 0) + 1
                continue
            hit, rule = None, None
            for b in blocks:
                if b.get("manual_lines_from_report"):               # (a) 에는 수동 등록 블록을 쓰지 않는다(Z2)
                    continue
                lo, hi = parse_kst(b["window"][0]), parse_kst(b["window"][1])
                if (tree in b["trees"] and ts is not None and lo <= ts <= hi
                        and e.get("purpose") in purposes[b["id"]] and e.get("actor") in purposes[b["id"]]):
                    hit, rule = b["id"], "a_writer"
                    break
            if hit is None:
                off, length = recs[i][0], recs[i][1]
                for b in blocks:
                    if not b.get("manual_lines_from_report") or tree not in b["trees"]:
                        continue
                    c = next((c for c in manual[b["id"]]["candidates"]
                              if manual_match(c, tree, i + 1, off, length, e, ts, b["window"])), None)
                    if c is not None:
                        hit, rule = b["id"], "b_manual_documented"
                        manual_lines.append({"tree": tree, "line": i + 1, "block": b["id"], "rule": rule,
                                             "report": b["report"], "report_line": c["report_line"],
                                             "offset": off, "length": length, "quote_keys": sorted(c["quote"])})
                        break
            if hit is None:
                info["n_unattributed"] += 1
                n_unattr += 1
                blocking.append({"code": "access_unattributed", "tree": tree, "line": i + 1})
            else:
                info["by_block"][hit] = info["by_block"].get(hit, 0) + 1
                info["by_rule"][rule] = info["by_rule"].get(rule, 0) + 1
        per_file[p] = info
    if n_open:
        blocking.append({"code": "open_sealed_substring", "n": n_open})
    missing_files = sorted(set(exp_lines) - {os.path.dirname(os.path.dirname(p)) for p in per_file})
    for t in missing_files:
        blocking.append({"code": "access_log_missing", "tree": t})
    return {"per_file": per_file, "n_files": len(per_file), "n_lines": sum(v["n_lines"] for v in per_file.values()),
            "n_unattributed": n_unattr, "n_human_exposure_true": n_human, "n_format_error": n_fmt,
            "n_open_sealed_substring": n_open,
            "line_rule": "기준선(AO) 줄 = JSON 객체 · type machine_read · human_exposure is True 금지(AO 규칙 — 옛 줄은 ts·"
                         "actor·path 키가 없을 수 있다) · 기준선 이후 줄 = 필수 키 전부 + human_exposure 불리언",
            "attribution_rules": {
                "a_writer": "블록 [착수, 완료] 시간창 + 트리 + writer 소스 문자열 상수(purpose·actor)",
                "b_manual_documented": "docs/119b Z1 — 등록 블록 리포트(sha 고정) 한 문단의 백틱 access.log 경로 · "
                                       "「N줄 → N+1줄」 · 「A B → C B」 · 인용 JSON 각 1개 + 줄 순번 == N+1 · 시작 오프셋 == A · "
                                       "길이(개행 포함) == C − A · 인용 ⊆ 줄 · ts_kst ∈ 블록 시간창"},
            "manual_rule": {k: {"report_sha_ok": v["report_sha_ok"], "n_candidates": len(v["candidates"])}
                            for k, v in manual.items()},
            "manual_lines": manual_lines, "n_manual_attributed": len(manual_lines),
            "blocks": [dict({k: b[k] for k in ("id", "docs", "window", "window_source", "trees", "writers")},
                            **({"report": b["report"], "report_sha256": b["report_sha256"],
                                "manual_lines_from_report": True} if b.get("manual_lines_from_report") else {}))
                       for b in blocks],
            "baseline_source": spec["access_baseline_source"]}


# ── B7 운영 사건 (값 비판독 · 개수·불리언·시각·줄 번호·sha16 만) ──────────────────
def _doc33_items(text):
    lines = text.split("\n")
    starts = {}
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^(\d+)\. \*\*", ln)
        if m:
            starts[int(m.group(1))] = i
    order = sorted(starts.items(), key=lambda x: x[1])
    out = {}
    for j, (n, s) in enumerate(order):
        e = order[j + 1][1] - 1 if j + 1 < len(order) else len(lines)
        out[n] = (s, e)
    return out, lines


def _record_ts(lines, s, e):
    hits = []
    for ln in lines[s - 1:e]:
        hits += re.findall(r"본 항목 기록 \**(20\d\d-\d\d-\d\d \d\d:\d\d:\d\d) KST", ln)
    return hits[-1] if hits else None


def ops_checks(root, ops, hashes, status):
    J = lambda rel: os.path.join(root, rel)                         # noqa: E731
    res = {}
    # (a) AY SIGTERM·재개
    h = ops["holm8"]
    hb = read_jsonl_public(J(h["heartbeat"]))
    runlog = read_text_public(J(h["runlog"])).split("\n")
    man = read_json_public(J(h["manifest"]))
    cks = [e for e in hb if e.get("event") == "checkpoint"]
    seq, gaps, dups = [], 0, 0
    prev = {}
    resumes = [e for e in hb if e.get("event") == "checkpoint_resume"]
    for e in hb:
        if e.get("event") == "checkpoint_resume":
            prev[e.get("phase")] = int(e.get("b_done") or 0)
        if e.get("event") != "checkpoint":
            continue
        ph, b = e.get("phase"), int(e.get("b_done") or 0)
        seq.append(b)
        if ph in prev:
            if b == prev[ph]:
                dups += 1
            elif b != prev[ph] + h["ckpt_every"]:
                gaps += 1
        elif b != h["ckpt_every"]:
            gaps += 1
        prev[ph] = b
    shas = [e.get("ckpt_sha256") for e in cks]
    last = shas[-1] if shas else None
    cur = hashes.get(h["tree"] + "/" + h["ckpt_name"])
    launches = sorted({int(x) for ln in runlog for x in re.findall(r"\tR2\t.*· launch (\d+)$", ln)})
    resume_lines = [i + 1 for i, ln in enumerate(runlog) if re.search(r"\tR4b\tresume ·", ln)]
    rng_at = literal_line(root, h["harness"], h["rng_check_literal"])
    step_at = text_line(root, h["harness"], h["resume_step_text"])
    res["a_holm8_resume"] = {
        "n_heartbeat_events": len(hb), "n_checkpoint_events": len(cks), "n_counter_gaps": gaps,
        "n_counter_duplicates": dups, "n_resume_events": len(resumes),
        "n_ckpt_sha_distinct": len(set(shas)), "n_ckpt_sha_consecutive_repeat": sum(
            1 for a, b in zip(shas, shas[1:]) if a == b),
        "last_heartbeat_ckpt_sha16": (last or "")[:16],
        "sealed_checkpoint_current_sha16": (cur or "")[:16],
        "last_heartbeat_ckpt_eq_sealed_current": bool(last and cur and (cur == last or cur.startswith(last))),
        "runlog_launches": launches, "manifest_n_launches": man.get("n_launches"),
        "manifest_n_resumes": man.get("n_resumes"),
        "launches_match_manifest": len(launches) == man.get("n_launches"),
        "resumes_match_manifest": len(resume_lines) == man.get("n_resumes") == len(resumes),
        "runlog_resume_lines": resume_lines,
        "rng_replay_check_at": rng_at, "resume_step_at": step_at,
        "rng_replay_record_present": bool(resume_lines) and bool(rng_at and step_at)
        and int(rng_at.rsplit(":", 1)[1]) < int(step_at.rsplit(":", 1)[1]),
        "rng_replay_note": "재개 줄(R4b resume)은 하네스가 난수 state 재생 대조(InvalidRun 분기)를 통과한 뒤에만 기록한다 "
                           "— 대조 값 자체는 기록되지 않으며 본 감사는 문자열 존재와 소스 순서만 본다.",
    }
    # (b) 감시 래퍼 중복 기동
    w = ops["holm8_watchdog"]
    wsha = sha_file(J(w["events"]))
    ev = read_jsonl_public(J(w["events"]))
    starts = [e for e in ev if e.get("event") == "watchdog_start"]
    lch = [e for e in ev if e.get("event") == "launch"]
    kids = [e for e in ev if e.get("event") == "child_started"]
    run_ids = sorted({e.get("run_id") for e in hb if e.get("run_id")})
    res["b_holm8_watchdog"] = {
        "events_sha256": wsha, "events_sha_matches_expected": wsha == w["sha256"],
        "n_events": len(ev), "n_watchdog_start": len(starts),
        "watchdog_start_launch_index": [e.get("launch_index") for e in starts],
        "n_launch_events": len(lch), "launch_index_unique": len({e.get("launch_index") for e in lch}) == len(lch),
        "n_child_started": len(kids), "child_pid_unique": len({e.get("pid") for e in kids}) == len(kids),
        "child_launch_index_unique": len({e.get("launch_index") for e in kids}) == len(kids),
        "heartbeat_run_ids": run_ids, "manifest_run_id": man.get("run_id"),
        "single_writer": len(run_ids) == 1 and run_ids[0] == man.get("run_id") and len(kids) == man.get("n_launches"),
    }
    # (c) AY Phase A 편차 12건 — 발생(리포트) ↔ 기록(docs/33)
    c = ops["ay_deviations"]
    rep = read_text_public(J(c["report"])).split("\n")
    s5 = next(i for i, ln in enumerate(rep) if ln.startswith("## 5."))
    e5 = next(i for i in range(s5 + 1, len(rep)) if rep[i].startswith("## "))
    ents = []
    for i in range(s5, e5):
        m = re.match(r"^(\d+)\. ", rep[i])
        if m:
            nd = ("편차 아님" in rep[i]) or ("충돌" in rep[i] and "없음" in rep[i])
            ents.append({"no": int(m.group(1)), "line": i + 1, "is_deviation": not nd})
    occurred = next((ln.split("수행:", 1)[1].strip() for ln in rep[:10] if "수행:" in ln), None)
    items33, l33 = _doc33_items(read_text_public(J(c["doc33"])))
    found = [n for n, (s, _e) in items33.items() if c["header_marker"] in l33[s - 1]]
    fi = found[-1] if found else None
    res["c_ay_phaseA_deviations"] = {
        "report": c["report"], "occurred_report_line": occurred, "entries": ents,
        "n_deviation": sum(1 for x in ents if x["is_deviation"]),
        "recorded_item": fi, "recorded_item_header_line": items33[fi][0] if fi else None,
        "recorded_ts_kst": _record_ts(l33, *items33[fi]) if fi else None,
        "spec_item": c["spec_item"], "spec_item_matches_found": fi == c["spec_item"],
    }
    # (d) 115b 감시 이벤트 의미 구분
    d = ops["d12"]
    dsha = sha_file(J(d["watchdog"]))
    dev = read_jsonl_public(J(d["watchdog"]))
    dhb = read_jsonl_public(J(d["heartbeat"]))
    tree_files = {p: s for p, s in hashes.items() if p.startswith(d["tree"] + "/_sealed/")}

    def which(hx):
        return sorted(p.rsplit("/", 1)[-1] for p, s in tree_files.items() if s.startswith(hx))

    recs = []
    for e in dev:
        if e.get("event") == "completed" and e.get("ckpt_sha256"):
            recs.append(("watchdog", "completed", e.get("variant"), e["ckpt_sha256"]))
    for e in dhb:
        if e.get("event") == "variant_done" and e.get("ckpt_sha256"):
            recs.append(("heartbeat", "variant_done", e.get("variant"), e["ckpt_sha256"]))
    out = []
    for src, evn, var, hx in recs:
        mt = which(hx[:16])
        r = {"source": src, "event": evn, "variant": var, "sha16": hx[:16], "matches_current_sealed": mt}
        if not mt:
            idx = [i for i, e in enumerate(dhb) if (e.get("ckpt_sha256") or "")[:16] == hx[:16]
                   and e.get("event") == "checkpoint"]
            later = [i for i, e in enumerate(dhb) if e.get("event") == "variant_done" and e.get("variant") == var
                     and idx and i > idx[-1]]
            r.update({"heartbeat_checkpoint_event_index": idx,
                      "heartbeat_checkpoint_phase": [dhb[i].get("phase") for i in idx],
                      "later_variant_done_index": later,
                      "superseded_by_later_write": bool(idx and later),
                      "watchdog_source_rule_at": text_line(root, d["watchdog_src"], d["watchdog_rule_text"])})
        out.append(r)
    res["d_d12_watchdog_semantics"] = {"events_sha256": dsha, "events_sha_matches_expected": dsha == d["sha256"],
                                       "records": out}
    # (e) 블록 BA `wc -l`
    e_ = ops["wc_l"]
    s, en = items33[e_["item"]]
    wl = [i for i in range(s, en + 1) if "wc -l" in l33[i - 1]]
    res["e_ba_wc_l"] = {"doc33_item": e_["item"], "doc33_lines": wl, "targets": e_["targets"],
                        "targets_status": {t: status.get(t) for t in e_["targets"]},
                        "targets_unchanged": all(status.get(t) == "ok" for t in e_["targets"]),
                        "correction_text": e_["correction_text"]}
    # (f) BA 구현 결정 I1~I6 — 근거 줄 인용(file:line)만
    f_ = ops["ba_impl"]
    s, en = items33[f_["item"]]
    r116 = read_text_public(J(f_["report"])).split("\n")
    res["f_ba_impl_decisions"] = {
        k: {"doc33_lines": [i for i in range(s, en + 1) if re.search(r"(?<![A-Za-z0-9])%s(?![0-9])" % k, l33[i - 1])][:8],
            "report_lines": [i + 1 for i, ln in enumerate(r116)
                             if re.search(r"(?<![A-Za-z0-9])%s(?![0-9])" % k, ln)][:8]}
        for k in f_["ids"]}
    res["f_ba_impl_decisions"]["_note"] = "판단은 cowork 검토 대상 — 러너는 근거 줄 위치만 인용(문면 미전재)."
    return res


# ── B8 R-d ─────────────────────────────────────────────────────────────────
RD_A = ("R1", "캘리브레이션", "구현식", "1종오류")
RD_B = ("경계", "일치", "승계")


def _has(s, kw):
    if kw == "R1":
        return re.search(r"(?<![A-Za-z0-9])R1(?![0-9])", s) is not None
    return kw in s


def _sentences(text):
    out = []
    for ln in text.split("\n"):
        for s in re.split(r"(?<=[.!?。])\s+", ln):
            if s.strip():
                out.append(s.strip())
    return out


def rd_classify(s):
    a, b = any(_has(s, k) for k in RD_A), any(_has(s, k) for k in RD_B)
    if not (a and b):
        return "a_only" if a else ("b_only" if b else None)
    expands = (re.search(r"Holm\s*보정\s*후", s) is not None and re.search(r"동일|같|일치|승계", s) is not None
               and re.search(r"금지|않|아니|아님|없|한정", s) is None)
    return "compliant" if ("보정 전" in s and not expands) else "violation"


def rd_check(root, rd):
    texts = []
    P = read_json_public(os.path.join(root, rd["plan"]))

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i))
        elif isinstance(o, str):
            texts.append((rd["plan"] + ":" + path, o))
    walk(P[rd["plan_key"]], rd["plan_key"])
    for rel in rd["docs"]:
        for i, ln in enumerate(read_text_public(os.path.join(root, rel)).split("\n"), 1):
            texts.append(("%s:%d" % (rel, i), ln))
    targets, a_only, b_only_n = [], [], 0
    for loc, t in texts:
        for s in _sentences(t):
            c = rd_classify(s)
            if c in ("compliant", "violation"):
                targets.append({"loc": loc, "class": c, "excerpt": s[:120]})
            elif c == "a_only":
                a_only.append({"loc": loc, "excerpt": s[:120]})
            elif c == "b_only":
                b_only_n += 1
    side = read_json_public(os.path.join(root, rd["sidecar"]))
    verb = _dig(side, rd["sidecar_key"])
    plan_strings = [t for loc, t in texts if loc.startswith(rd["plan"] + ":")]
    return {"n_target_sentences": len(targets), "n_violation": sum(1 for x in targets if x["class"] == "violation"),
            "targets": targets, "not_applicable_a_only": a_only, "n_not_applicable_b_only": b_only_n,
            "verbatim_r_d_in_plan_reporting_text": any(verb in s for s in plan_strings),
            "verbatim_r_d_in_reporting_plan": verb in read_text_public(os.path.join(root, rd["reporting_plan"])),
            "checklist_item": _dig(side, rd["checklist_key"]),
            "rule": "대상 = (R1|캘리브레이션|구현식|1종오류) ∧ (경계|일치|승계) 동시 등장 문장 · 적합 = 「보정 전」 한정어 있고 "
                    "Holm 보정 후 판정과 동일/승계라고(부정어 없이) 서술하지 않음 · 한쪽 키워드만 = 비해당(판정 cowork)"}


# ── B9 대장 3벌 대응표 · 서명 일치 ─────────────────────────────────────────────
def _ts_all(s):
    return [x[:16] for x in re.findall(r"20\d\d-\d\d-\d\d \d\d:\d\d(?::\d\d)?", str(s))]


def ledgers_table(root, lg):
    J = lambda rel: os.path.join(root, rel)                         # noqa: E731
    t45 = read_text_public(J(lg["doc45"])).split("\n")
    s = next(i for i, ln in enumerate(t45) if ln.startswith(lg["section_start"]))
    e = next(i for i in range(s + 1, len(t45)) if t45[i].startswith(lg["section_end"]))
    rows45 = []
    for i in range(s, e):
        ln = t45[i]
        if ln.startswith("|") and not re.match(r"^\|\s*-", ln) and not ln.startswith("| 시각"):
            cols = [c.strip() for c in ln.strip("|").split("|")]
            c2 = cols[2] if len(cols) > 2 else ""
            blk = re.search(r"블록 ([A-Z]{1,2})(?![A-Za-z])", c2)
            rep = re.search(r"반복(\d)", c2)
            rows45.append({"line": i + 1, "ts": _ts_all(cols[0]), "block": blk.group(1) if blk else None,
                           "repeat": None if blk else ("consensus" if "consensus" in c2 else (rep.group(1) if rep
                                                                                                else None))})
    F = read_json_public(J(lg["fll"]))
    fll = []
    for i, x in enumerate(F):
        blk = re.match(r"^([A-Z]{1,2}) ", str(x.get("block") or ""))
        fll.append({"index": i, "ts": _ts_all(x.get("ts_kst")) + _ts_all(x.get("ts_completed_kst")),
                    "block": blk.group(1) if blk else None,
                    "repeat": str(x.get("repeat")) if x.get("repeat") is not None else None})
    L = read_json_public(J(lg["ledger"]))
    flr = L[lg["flr_key"]]
    frows = [{"index": i, "ts": _ts_all(r.get("ts_kst")) + _ts_all(r.get("ts_completed_kst")),
              "repeat": str(r.get("repeat"))} for i, r in enumerate(flr.get("rows", []))]

    def multi(r):
        return r is not None and bool(re.search(r"[+,]", str(r)))

    def match(a, pool):
        """키 우선순위: 블록 문자 일치 → (블록 없는 초기 행) 반복 번호 일치(consensus ↔ 복수 반복) → 시각 일치."""
        m = []
        for b in pool:
            if a.get("block"):
                ok = a["block"] == b.get("block")
            elif a.get("repeat") == "consensus":
                ok = multi(b.get("repeat")) and not b.get("block")
            elif a.get("repeat"):
                ok = str(b.get("repeat")) == a["repeat"] and not b.get("block")
            else:
                ok = bool(set(a["ts"]) & set(b["ts"]))
            if ok:
                m.append(b.get("index", b.get("line")))
        return m
    table = []
    for r in rows45:
        mf, ml = match(r, fll), match(r, frows)
        table.append({"doc45_line": r["line"], "ts": r["ts"], "block": r["block"], "repeat": r["repeat"],
                      "fll_index": mf, "ledger_flr_index": ml,
                      "no_match_reason": None if (mf or ml) else "시각·블록·반복 키 어느 것도 다른 대장과 대응 안 됨"})
    fll_unmatched = [x["index"] for x in fll if not any(x["index"] in t["fll_index"] for t in table)]
    return {"doc45_rows": len(rows45), "fll_rows": len(fll), "ledger_flr_keys": len(flr),
            "ledger_flr_rows": len(frows), "table": table, "fll_without_doc45_row": fll_unmatched,
            "rows_added": 0,
            "note": "원기록 보존 + 출처 표시 대조표 — 새 행 추가 0. 부호 열은 전재하지 않는다(시각·블록·반복 키만)."}


def sign_check(root, sg):
    F = read_json_public(os.path.join(root, sg["fll"]))
    S = read_json_public(os.path.join(root, sg["sdm"]))
    known = [i for i, x in enumerate(F) if x.get("delta_sign") is not None]
    srcs = []
    for r in S.get("rows", []):
        m = re.search(r"first_look_log\.json\[(\d+)\]", str(r.get("sign_source", "")))
        srcs.append(int(m.group(1)) if m else None)
    return {"sdm_sha256": sha_file(os.path.join(root, sg["sdm"])),
            "sdm_sha_matches_expected": sha_file(os.path.join(root, sg["sdm"])) == sg["sdm_sha256"],
            "n_fll_entries": len(F), "n_fll_sign_known": len(known), "sdm_n_rows_field": S.get("n_rows"),
            "sdm_len_rows": len(S.get("rows", [])),
            "three_values_agree": len(known) == S.get("n_rows") == len(S.get("rows", [])),
            "sdm_row_sources_eq_fll_sign_known": sorted(x for x in srcs if x is not None) == known,
            "sign_known_ts_kst": [F[i].get("ts_kst") for i in known],
            "n_new_sign_known_since_ao": sum(1 for i in known if i >= sg["ao_fll_entries"]),
            "rule": "AO sign_disclosure_consistency 와 같은 규칙 — 부호 값 출력 0 · 개수·시각만"}


# ── B10 범위 밖 사본 ─────────────────────────────────────────────────────────
def _is_original(rel):
    return re.match(r"^experiments/runs/[^/]+/_sealed(/|$)", rel) is not None


def oog_copies(root, live, hashes, og, blocking):
    sizes = {}
    for p, v in live.items():
        if not v["access"] and v["bytes"] > 0:
            sizes.setdefault(v["bytes"], []).append(p)
    by_sha = {}
    for p, s in hashes.items():
        by_sha.setdefault(s, []).append(p)
    n_scanned = n_hashed = 0
    copies, named_dirs, named_files = [], [], []
    for dp, dn, fn in os.walk(root):
        rd = os.path.relpath(dp, root)
        if rd.split(os.sep)[0] == ".git" or _is_original(rd):
            dn[:] = []
            continue
        if rd != "." and "sealed" in os.path.basename(rd).lower():
            named_dirs.append(rd)
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                continue
            n_scanned += 1
            in_named = any(rel.startswith(d + "/") for d in named_dirs)
            if in_named:
                named_files.append(rel)
            sz = os.path.getsize(p)
            if sz in sizes:
                n_hashed += 1
                s = sha_file(p)
                for orig in by_sha.get(s, []):
                    if live[orig]["bytes"] == sz:
                        copies.append({"copy_path": rel, "original_path": orig, "sha16": s[:16]})
    acc = {}
    for rel in named_files:
        if rel.endswith("/access.log"):
            n_h = n_t = 0
            for ln in read_bytes(os.path.join(root, rel)).decode("utf-8").split("\n"):
                if ln.strip():
                    e = parse_access_line(ln)
                    n_h += e.get("human_exposure") is not False
                    n_t += e.get("type") != "machine_read"
            acc[rel] = {"n_human_exposure_true": n_h, "n_type_not_machine_read": n_t}
    exp = og["expected"]
    copy_files = sorted({c["copy_path"] for c in copies})
    cond = {
        "a_all_expected_copies_byte_identical": set(exp["copy_files"]) <= set(copy_files),
        "b_access_log_machine_only": all(v["n_human_exposure_true"] == 0 and v["n_type_not_machine_read"] == 0
                                         for v in acc.values()),
        "c_no_other_files": sorted(named_files) == sorted(exp["files_in_sealed_named_dirs"])
        and sorted(named_dirs) == sorted(exp["sealed_named_dirs"]),
        "d_copies_covered_by_ao": set(copy_files) <= set(exp["copy_files"]),
    }
    for k, v in cond.items():
        if not v:
            blocking.append({"code": "oog_rule_" + k[0]})
    return {"rule": og["rule"], "n_files_scanned": n_scanned, "n_files_hashed": n_hashed, "copies": copies,
            "copy_files": copy_files, "sealed_named_dirs": sorted(named_dirs),
            "files_in_sealed_named_dirs": sorted(named_files), "access_logs": acc, "conditions": cond,
            "verdict": "non_blocking_recorded" if all(cond.values()) else "blocking"}


# ── B11 문면 정정 대상 · B-1 11 관찰 ─────────────────────────────────────────
def doc_corrections(root, dc, n_sha_problems):
    items33, lines = _doc33_items(read_text_public(os.path.join(root, dc["doc33"])))
    out = []
    for n, (s, e) in sorted(items33.items()):
        for i in range(s, e + 1):
            ln = lines[i - 1]
            ph = [p for p in dc["phrases"] if p in ln]
            bs = [b for b in dc["basis"] if b in ln]
            if ph and bs:
                out.append({"item": n, "line": i, "phrases": ph, "basis": bs})
    return {"targets": out, "n_targets": len(out), "supported_by_sha_audit": n_sha_problems == 0,
            "correction_text": dc["correction_text"]}


def obs_post_counts(root, rel):
    P = read_json_public(os.path.join(root, rel))
    e = P["outputs"]["expected_post_counts"]
    return {"at_118_stat": e["at_118_stat"], "note": "이름과 달리 「118 시점 값으로 계산한 개봉 후 예상치」(118 시점 실측 "
            "n_access_log 25 · n_sealed_files_total 826 · 그 뒤 트리 5개에 access.log 신규 생성분 반영). 동결물이라 수정 0 · "
            "해석 주석만."}


# ── 9키 · 결속 검사 · 누설 스캔 ──────────────────────────────────────────────
def check_schema(obj, top_keys, report_path):
    fails = []
    if not isinstance(obj, dict) or sorted(obj) != sorted(top_keys):
        fails.append("top_level_keys")
        return fails
    if obj.get("audit_version") != "v3":
        fails.append("audit_version")
    if obj.get("verdict") not in ("PASS", "FAIL"):
        fails.append("verdict")
    if obj.get("report_path") != report_path:
        fails.append("report_path")
    if sorted(obj.get("sealed_counts") or {}) != sorted(COUNT_KEYS):
        fails.append("sealed_counts")
    if not all(isinstance(v, str) and HEX64.match(v) for v in (obj.get("sealed_sha256") or {}).values()):
        fails.append("sealed_sha256")
    if not all(isinstance(v, str) and HEX64.match(v) for v in (obj.get("frozen_118_sha256") or {}).values()):
        fails.append("frozen_118_sha256")
    return fails


def binding_check(root, audit, groups, top_keys, report_path):
    """B-2 4 — unblinding_run.py G-gate 의 감사 파일 규칙을 독립 구현(키 집합 · verdict · report_path · stat 재계산)."""
    f = []
    if set(audit) != set(top_keys) or audit.get("verdict") != "PASS" or audit.get("audit_version") != "v3":
        f.append("audit_verdict_or_schema")
    if audit.get("report_path") != report_path:
        f.append("audit_report_path")
    counts, fps, acc = stat_summary_v3(root, groups)
    if counts != audit.get("sealed_counts"):
        f.append("sealed_counts_changed")
    for g, s in (audit.get("stat_fingerprints") or {}).items():
        if fps.get(g) != s:
            f.append("stat_fingerprint_changed:" + g)
    if acc != audit.get("access_log_lines"):
        f.append("access_log_lines_changed")
    return f


LEAK_NUM = re.compile(r"(?<![0-9A-Za-z])\d+\.\d{4,}")
FORBID_SUB = ("delta", "p_value", "pvalue", "lambda", "t_obs", "n_epochs", "wall_second", "auc", "macro_ap")
FORBID_EXACT = {"ap", "ci", "p"}


def leak_scan(texts, objs, planted=()):
    hits = []
    for name, t in texts:
        for m in LEAK_NUM.finditer(t):
            hits.append({"where": name, "kind": "decimal4", "at": m.start()})
        for pl in planted:
            if pl in t:
                hits.append({"where": name, "kind": "planted"})

    def keys(o, name):
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                if "/" in kl:            # 경로 키(봉인 파일명 예: lambda_selected.json)는 값 이름이 아니다
                    keys(v, name)
                    continue
                if kl in FORBID_EXACT or any(s in kl for s in FORBID_SUB):
                    hits.append({"where": name, "kind": "forbidden_key", "key": str(k)})
                keys(v, name)
        elif isinstance(o, list):
            for v in o:
                keys(v, name)
    for name, o in objs:
        keys(o, name)
    return hits


# ═══════════════════════════════════════════════════════════════════════════
# core (fixture·실저장소 공용 순수 경로) — 쓰기 0, 결과 객체 반환
# ═══════════════════════════════════════════════════════════════════════════
def run_core(root, spec, man):
    blocking, nonblocking, log = [], [], []
    L = lambda msg: log.append("%s\t%s" % (now_kst(), msg))        # noqa: E731
    exp = spec["expected"]
    groups = spec["groups"]
    L("start")
    dirs, live, glob_equal = scan_live(root)
    counts0, fps0, acc0 = stat_summary_v3(root, groups)
    start = {"counts_eq": counts0 == exp["counts"], "fingerprints_eq": fps0 == exp["fingerprints"],
             "access_lines_eq": acc0 == exp["access_lines"], "sealed_dirs_glob_equal": glob_equal}
    if not all(start.values()):
        blocking.append({"code": "f2_changed_at_start", "detail": {k: v for k, v in start.items() if not v}})
    L("live scan · dirs %d · files %d · glob_equal %s" % (len(dirs), len(live), glob_equal))
    arts = sorted(p for p, v in live.items() if not v["access"])
    ckpts = sorted({it["rule"]["checkpoint"] for it in man["items"] if it["class"] == "recorded_via_checkpoint"})
    hashes = {}
    for p in ckpts:
        if p in live:
            hashes[p] = sha_file(os.path.join(root, p))
    man = json.loads(json.dumps(man))
    proj = do_projection(root, man, hashes, blocking)
    L("projection · checkpoints %d" % len(proj))
    itm = {it["path"]: it for it in man["items"]}
    dfr = man.get("secondary", {}).get("deferred_via_checkpoint", [])
    n_dfr_ok = 0
    for d in dfr:
        if any(itm[t]["expected_sha256"] == d["sha256"] for t in d["targets"]):
            n_dfr_ok += 1
        else:
            blocking.append({"code": "source_conflict", "origin": "secondary_deferred", "source": d["source"],
                             "key_path": d["key_path"], "candidates": d["targets"]})
    proj["_secondary_deferred"] = {"n": len(dfr), "n_consistent": n_dfr_ok}
    for p in arts:
        if p not in hashes:
            hashes[p] = sha_file(os.path.join(root, p))
    L("hashed · %d" % len(hashes))
    y4_ctx = {"history": man.get("y4_history", {}), "live_fps": fps0}
    cmp_, status = compare(man, live, hashes, y4_ctx, blocking, nonblocking)
    L("compare · expected %d · live %d" % (cmp_["n_expected"], cmp_["n_live"]))
    for b in man.get("blocking", []):
        blocking.append(dict(b, origin="expected_manifest"))
    acc = audit_access(root, live, spec, blocking)
    L("access audit · files %d · unattributed %d" % (acc["n_files"], acc["n_unattributed"]))
    det = {"projection": proj, "comparison": cmp_, "access_audit": acc}
    if spec.get("ops"):
        det["ops"] = ops_checks(root, spec["ops"], hashes, status)
    if spec.get("rd"):
        det["rd"] = rd_check(root, spec["rd"])
        for t in det["rd"]["targets"]:
            if t["class"] == "violation":
                blocking.append({"code": "rd_violation", "loc": t["loc"]})
        if not (det["rd"]["verbatim_r_d_in_plan_reporting_text"] and det["rd"]["verbatim_r_d_in_reporting_plan"]):
            nonblocking.append({"code": "rd_verbatim_absent",
                                "plan": det["rd"]["verbatim_r_d_in_plan_reporting_text"],
                                "reporting_plan": det["rd"]["verbatim_r_d_in_reporting_plan"]})
    if spec.get("ledgers"):
        det["ledgers"] = ledgers_table(root, spec["ledgers"])
    if spec.get("sign"):
        det["sign"] = sign_check(root, spec["sign"])
    if spec.get("oog"):
        det["oog"] = oog_copies(root, live, hashes, spec["oog"], blocking)
    n_sha_problems = sum(1 for b in blocking if b["code"] in ("sha_mismatch", "size_mismatch", "missing"))
    if spec.get("doc_corrections"):
        det["doc_corrections"] = doc_corrections(root, spec["doc_corrections"], n_sha_problems)
    if spec.get("obs_plan"):
        det["obs_expected_post_counts"] = obs_post_counts(root, spec["obs_plan"])
    frozen = {}
    fm = read_json_public(os.path.join(root, spec["frozen_manifest"]))
    for rel, v in sorted(fm["frozen_7"].items()):
        frozen[rel] = sha_file(os.path.join(root, rel))
        if frozen[rel] != v["sha256"]:
            blocking.append({"code": "f4_changed", "path": rel})
    counts1, fps1, acc1 = stat_summary_v3(root, groups)
    end = {"counts_eq_start": counts1 == counts0, "fingerprints_eq_start": fps1 == fps0, "access_eq_start": acc1 == acc0}
    if not all(end.values()):
        blocking.append({"code": "f2_changed_during_run"})
    verdict = "PASS" if not blocking else "FAIL"
    audit = {
        "audit_version": "v3", "verdict": verdict, "audited_at_kst": now_kst(),
        "sealed_sha256": {p: hashes[p] for p in arts},
        "sealed_counts": counts0, "stat_fingerprints": fps0, "access_log_lines": acc0,
        "frozen_118_sha256": frozen, "report_path": spec["report_path"],
    }
    sch = check_schema(audit, spec["top_keys"], spec["report_path"])
    if sch:
        blocking.append({"code": "schema", "fails": sch})
    bind = binding_check(root, dict(audit, verdict="PASS"), groups, spec["top_keys"], spec["report_path"])
    if bind:
        blocking.append({"code": "binding_check", "fails": bind})
    y4_rows = [{"path": p, "bytes": live[p]["bytes"], "mtime_kst": ns_to_kst(live[p]["mtime_ns"]),
                "mtime_ns": live[p]["mtime_ns"], "sha16": hashes[p][:16],
                "existence_evidence_at": next(it for it in man["items"] if it["path"] == p)["rule"]
                ["existence_evidence_at"]}
               for p in man.get("y4_paths", []) if p in live]
    details = {"block": BLOCK, "instruction": INSTRUCTION, "gates_start": start, "gates_end": end,
               "live_scan": {"n_sealed_dirs": len(dirs), "n_files": len(live), "n_artifacts": len(arts),
                             "sealed_dirs_glob_equal": glob_equal},
               "y4": y4_rows, "status_counts": _count(status.values()), **det,
               "frozen_118_sha256": frozen, "binding_check_fails": bind, "schema_fails": sch}
    L("leak scan")
    hits = leak_scan([("audit", dumps(audit)), ("details", dumps(details)), ("log", "\n".join(log))],
                     [("audit", audit), ("details", details)], spec.get("planted", ()))
    if hits:
        blocking.append({"code": "output_leak", "n_hits": len(hits)})
    verdict = "PASS" if not blocking else "FAIL"
    audit["verdict"] = verdict
    details.update({"verdict": verdict, "blocking": blocking, "n_blocking": len(blocking),
                    "nonblocking": nonblocking, "leak_hits": hits})
    L("verdict %s · blocking %d" % (verdict, len(blocking)))
    return audit, details, log


def _count(vals):
    out = {}
    for v in vals:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


# ═══════════════════════════════════════════════════════════════════════════
# 실저장소 spec
# ═══════════════════════════════════════════════════════════════════════════
def real_spec(root=ROOT):
    plan = read_json_public(os.path.join(root, PLAN_REL))
    groups = plan["stat_groups"]
    R = RUNS_REL
    conf3 = ["%s/v3_gin_confirm_rep%d_seed%d" % (R, r, s) for r, s in ((1, 201), (2, 202), (3, 203))]
    cons, gcons, lev = R + "/v3_consensus_rep123", R + "/v3_gin_confirm_consensus_rep123", R + "/v3_rqint_leverage_d11"
    stab = R + "/v3_gin_stability"
    ao = read_json_public(os.path.join(root, AO_REL))
    oo = ao["out_of_glob_sealed_copies"]
    S = SRC_REL
    return {
        "groups": groups, "top_keys": TOP_KEYS, "report_path": REPORT_REL, "expected": REAL_EXPECTED,
        "frozen_manifest": FREEZE_MANIFEST_REL,
        "egroup_of": {"existing": "E-A", "confirm_gin": "E-B", "stability": "E-C", "gin_consensus": "E-D",
                      "leverage": "E-E", "holm8": "E-E", "d12": "E-E", "s6": "E-E", "sens": "E-F"},
        "recorders": {
            "ao": {"path": AO_REL, "sha256": "a7fba492765e799398fc60dbcf9ed91728e14b9ca324b0bfba4fb4fe8cb07294",
                   "key": "hashes.sha256_all_sealed_artifacts"},
            "confirm": {"path": R + "/v3_gin_start_authorization/manifest_t4_post_confirmatory.json",
                        "sha256": "a59ab54afd51508543a3ca952a5147ffc0c8687f997aacf42362ab699683ea59",
                        "tree_fmt": R + "/v3_gin_confirm_rep{r}_seed{s}"},
            "stability": {"path": stab + "/manifest_s2_post_stability.json",
                          "sha256": "223209a99c694da0ddb03b4e5da021adae6c7eaaec75a89ffe553d0ffcf036cd", "tree": stab},
            "public": [
                {"path": gcons + "/manifest_public.json", "tree": gcons, "mode": "tree"},
                {"path": lev + "/manifest_public.json", "tree": lev, "mode": "tree"},
                {"path": R + "/v3_rqint_holm8/manifest_public.json", "tree": R + "/v3_rqint_holm8", "mode": "tree"},
                {"path": R + "/v3_rqint_d12/manifest_public.json", "tree": R + "/v3_rqint_d12", "mode": "tree"},
                {"path": R + "/v3_stability_ss15/manifest_public.json", "tree": R + "/v3_stability_ss15",
                 "mode": "tree"},
                {"path": R + "/v3_confirm_sens/manifest_public.json", "tree": R + "/v3_confirm_sens", "mode": "repo",
                 "sha256": "9a1b9230fdc3b66a072a6b2de13875199b6cd6f3a26037bb612c8db25a284752"},
            ],
        },
        "grid": {
            "writer_confirm": S + "/confirmatory_gin_train.py", "writer_stab": S + "/confirmatory_gin_stability.py",
            "confirm_partial_fmt": "%s_fold%d_seed%d.npz", "confirm_oof_fmt": "oof_%s_seed%d.npz",
            "stab_partial_fmt": "%s_rep%d_fold%d_seed%d.npz",
            "gin_seed_freeze": CFG_REL + "/gin_seed_freeze.json", "ladder": CFG_REL + "/ladder_freeze.json",
            "plan_confirm": R + "/v3_gin_start_authorization/plan_confirmatory_315.json",
            "plan_stab": stab + "/plan_stability_42.json", "n_folds": 5,
            "projection_keys": ["rep", "fold", "model", "train_seed", "artifact_sha256"],
            "y4_names": ["env_fingerprint.json", "train_stdout.log"],
        },
        "y4_history": {"confirm_gin": S + "/stability_ss15_run.py", "stability": S + "/stability_ss15_run.py"},
        "secondary": {"runs_dir": R, "patterns": ["*_public.json", "config.json", "_run_state.json",
                                                  "_consensus_state.json"],
                      "files": ["experiments/provenance/first_look_log.json", "experiments/provenance/ledger.json",
                                "experiments/provenance/sealing_completeness_audit.json"]},
        "access_required_keys": ["ts_kst", "type", "purpose", "human_exposure", "path", "actor"],
        "access_baseline": ao["opened_check"]["entries_per_file"],
        "access_baseline_source": AO_REL + ":opened_check.entries_per_file",
        "blocks": [
            {"id": "AT", "docs": "docs/110", "trees": conf3, "writers": [S + "/confirmatory_gin_train.py"],
             "window": ["2026-09-21 16:31:08", "2026-09-22 11:05:59"],
             "window_source": "착수 = docs/33 항목 62 ① (sessions.jsonl 세션 1) · 완료 = docs/110 report2 수행 11:05"},
            {"id": "AU", "docs": "docs/111", "trees": [stab],
             "writers": [S + "/confirmatory_gin_stability.py", S + "/confirmatory_gin_train.py"],
             "window": ["2026-09-22 23:48:56", "2026-09-23 11:34:59"],
             "window_source": "착수 = docs/33 항목 64 ① · 완료 = docs/111 report2 수행 11:34"},
            {"id": "AV", "docs": "docs/112", "trees": [stab], "writers": [],
             "report": "docs/112_rqint_downstream_spec_report.md",
             "report_sha256": "73ad76c57fa867f79e4fed87278f4b2e0336c923020aab6b0cc7956ccf8d34fd",
             "manual_lines_from_report": True, "window": ["2026-09-23 00:00:00", "2026-09-23 23:59:59"],
             "window_source": "일 단위 — docs/33 항목 65 · docs/112 수행 줄이 날짜(2026-09-23)만 기재 · (b) 조건 ⑦ 전용 "
                              "(docs/119b Z2)"},
            {"id": "AW", "docs": "docs/113", "trees": conf3 + [gcons], "writers": [S + "/confirmatory_gin_consensus.py"],
             "window": ["2026-09-27 23:27:19", "2026-09-27 23:30:39"],
             "window_source": "하네스 동결 ~ 완료 = docs/33 항목 66 ③"},
            {"id": "AX", "docs": "docs/114", "trees": [cons, gcons, lev], "writers": [S + "/rqint_leverage_d11.py"],
             "window": ["2026-09-28 09:22:13", "2026-09-28 09:56:23"],
             "window_source": "하네스 동결 ~ 본 항목 기록 = docs/33 항목 68 ③"},
            {"id": "AY", "docs": "docs/115", "trees": [cons, gcons, lev, R + "/v3_rqint_holm8"],
             "writers": [S + "/rqint_holm8_run.py"], "window": ["2026-09-28 12:02:00", "2026-10-01 22:12:18"],
             "window_source": "하네스 동결 12:02 ~ 본 항목 기록 = docs/33 항목 70 ③"},
            {"id": "AZ", "docs": "docs/115b", "trees": [cons, gcons, lev, R + "/v3_rqint_d12"],
             "writers": [S + "/rqint_d12_run.py"], "window": ["2026-10-02 01:21:00", "2026-10-04 10:24:38"],
             "window_source": "하네스 동결 01:21 ~ 본 항목 기록 = docs/33 항목 73 ③"},
            {"id": "BA", "docs": "docs/116", "trees": conf3 + [stab, R + "/v3_stability_ss15"],
             "writers": [S + "/stability_ss15_run.py"], "window": ["2026-10-04 11:15:53", "2026-10-04 11:35:44"],
             "window_source": "하네스 동결 = docs/33 항목 74 ③ ~ 항목 75 기록 ③"},
            {"id": "BB", "docs": "docs/117", "trees": [R + "/v3_confirm_rep1_seed201"],
             "writers": [S + "/confirmatory_oof_sens.py"], "window": ["2026-10-04 13:26:48", "2026-10-04 14:44:11"],
             "window_source": "항목 76 기록 ~ 항목 77 기록 = docs/33 항목 76·77 ③"},
        ],
        "ops": {
            "holm8": {"tree": R + "/v3_rqint_holm8", "heartbeat": R + "/v3_rqint_holm8/heartbeat.jsonl",
                      "runlog": R + "/v3_rqint_holm8/run.log", "manifest": R + "/v3_rqint_holm8/manifest_public.json",
                      "ckpt_name": "_sealed/checkpoint.npz", "ckpt_every": 1000, "harness": S + "/rqint_holm8_run.py",
                      "rng_check_literal": "난수 state", "resume_step_text": "\"resume · phase %s"},
            "holm8_watchdog": {"events": R + "/v3_holm8_watchdog/watchdog_events.jsonl",
                               "sha256": "2b7a47948372776ebe0f42ae14ea3b889551d0b6abeda988f43c500c933d7238"},
            "ay_deviations": {"report": "docs/115_rqint_holm8_mainrun_report.md", "doc33": DOC33_REL,
                              "header_marker": "블록 AY Phase A 편차", "spec_item": 71},
            "d12": {"tree": R + "/v3_rqint_d12", "watchdog": R + "/v3_d12_watchdog/watchdog_events.jsonl",
                    "sha256": "de704ae86742d23eaf5a976936b01ac24de44ac733bb2e1d34d494b786b07164",
                    "heartbeat": R + "/v3_rqint_d12/heartbeat.jsonl", "watchdog_src": S + "/rqint_d12_watchdog.py",
                    "watchdog_rule_text": "last = {k: o.get(k) for k in (\"variant\", \"b_done\", \"k_done\", \"phase\", "
                                          "\"ckpt_sha256\")}"},
            "wc_l": {"item": 74, "targets": ["%s/_sealed/checkpoint.jsonl" % t for t in conf3 + [stab]],
                     "correction_text": "봉인 파일 판독 발생 · 구조 정보(줄 수) 사람 노출"},
            "ba_impl": {"item": 74, "report": "docs/116_stability_ss15_report.md",
                        "ids": ["I1", "I2", "I3", "I4", "I5", "I6"]},
        },
        "rd": {"plan": PLAN_REL, "plan_key": "reporting_text",
               "docs": ["docs/118_unblinding_reporting_plan.md", "docs/118b_external_validation_plan.md"],
               "reporting_plan": "docs/118_unblinding_reporting_plan.md",
               "sidecar": CFG_REL + "/rqint_downstream_spec_v1_amendment3.json",
               "sidecar_key": "reviewer_20260929.r_d", "checklist_key": "opening_prep_audit_checklist_additions"},
        "ledgers": {"doc45": "docs/45_research_integrity_ledger.md", "section_start": "## 5.", "section_end": "## 6.",
                    "fll": "experiments/provenance/first_look_log.json", "ledger": "experiments/provenance/ledger.json",
                    "flr_key": "first_look_register"},
        "sign": {"fll": "experiments/provenance/first_look_log.json",
                 "sdm": "experiments/provenance/sign_disclosure_matrix.json",
                 "sdm_sha256": "147d5d5f62edf84a10f31f7395237f2790e350711fd9f76dada24f067a11ff51",
                 "ao_fll_entries": ao["sign_disclosure_consistency"]["n_first_look_entries"]},
        "oog": {"rule": oo["rule"], "expected": {"copy_files": oo["copy_files"],
                                                  "sealed_named_dirs": oo["sealed_named_dirs"],
                                                  "files_in_sealed_named_dirs": [x["path"] for x in
                                                                                 oo["files_in_sealed_named_dirs"]]}},
        "doc_corrections": {"doc33": DOC33_REL, "phrases": ["0바이트 불변", "바이트 불변", "내용 불변"],
                            "basis": ["stat 지문", "지문", "access 제외"],
                            "correction_text": "stat 지문은 경로·크기 불변만 증명한다. 내용 불변은 본 감사(항목 80)의 sha "
                                               "대조로 사후 확인했다"},
        "obs_plan": PLAN_REL,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 실저장소 게이트 (F1 · F2 · F4 · 락 · pycache) — run 전용
# ═══════════════════════════════════════════════════════════════════════════
def _git(root, *args):
    p = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True, check=True)
    return p.stdout


def count_pycache(root):
    n = 0
    for dp, dn, _fn in os.walk(root):
        if ".git" in os.path.relpath(dp, root).split(os.sep):
            dn[:] = []
            continue
        n += sum(1 for d in dn if d == "__pycache__")
    return n


def real_gates(root, spec):
    E = spec["expected"]
    g = {}
    g["git_head"] = _git(root, "rev-parse", "--short", "HEAD").strip() == E["git"]["head"]
    g["git_commits"] = int(_git(root, "rev-list", "--count", "HEAD").strip()) == E["git"]["n_commits"]
    g["git_modified"] = len([x for x in _git(root, "ls-files", "-m").split("\n") if x]) == E["git"]["n_modified"]
    g["no_index_lock"] = not os.path.exists(os.path.join(root, ".git", "index.lock"))
    counts, fps, acc = stat_summary_v3(root, spec["groups"])
    g["f2_counts"] = counts == E["counts"]
    g["f2_fingerprints"] = fps == E["fingerprints"]
    g["f2_access_lines"] = acc == E["access_lines"]
    _d, live, _ge = scan_live(root)
    g["f2_sealed_bytes"] = sum(v["bytes"] for v in live.values()) == E["sealed_bytes_total"]
    fm = os.path.join(root, FREEZE_MANIFEST_REL)
    g["f4_freeze_manifest"] = sha_file(fm) == E["freeze_manifest_sha256"]
    F7 = read_json_public(fm)["frozen_7"]
    g["f4_frozen_7"] = all(sha_file(os.path.join(root, r)) == v["sha256"] for r, v in F7.items())
    g["f4_other"] = all(sha_file(os.path.join(root, r)) == s for r, s in E["f4_other"].items())
    lk = os.path.join(root, RUNS_REL)
    g["no_compute_lock"] = not (os.path.exists(os.path.join(lk, ".compute_lock"))
                                or os.path.exists(os.path.join(lk, ".compute_lock.json")))
    g["stale_lock_lines"] = read_bytes(os.path.join(lk, ".compute_lock.stale.jsonl")).count(b"\n") == E[
        "stale_lock_lines"]
    g["pycache_dirs"] = count_pycache(root) == E["pycache_dirs"]
    out = [d for d in os.listdir(lk) if d.startswith("v3_unblinding") or d.startswith("v3_unblind_")]
    g["output_dirs"] = sorted(out) == ["v3_unblind_freeze"]
    plan = read_json_public(os.path.join(root, PLAN_REL))
    fl = plan["flags"]
    g["flags"] = all(read_json_public(os.path.join(root, r))["gin_start_still_blocked"] is True
                     for r in fl["gin_start_still_blocked_true"]) and all(
        read_json_public(os.path.join(root, r))["unblinding_performed"] is False for r in fl["unblinding_performed_false"])
    return g


def doc33_markers(root):
    found = {k: [] for k in MARKER_RE}
    for ln in read_text_public(os.path.join(root, DOC33_REL)).split("\n"):
        for k, rx in MARKER_RE.items():
            m = rx.match(ln)
            if m:
                found[k].append(m.group(1))
    return found


# ═══════════════════════════════════════════════════════════════════════════
# 합성 결함 selftest (U1~U17) — tempfile 가짜 저장소 · 실저장소 쓰기 0
# ═══════════════════════════════════════════════════════════════════════════
FX_PLANT = "0.73519284"


def _fx_build(tmp):
    """봉인 트리 6개(access.log 포함) · 기록원 JSON · checkpoint · writer 소스 · 설계 격자."""
    _STATE["fixture_root"] = os.path.abspath(tmp)
    R = "experiments/runs"

    def W(rel, data):
        _safe_write(os.path.join(tmp, rel), data)

    def B(n, seed):
        return hashlib.sha256(seed.encode()).digest() * n

    def S(rel):
        return sha_file(os.path.join(tmp, rel))
    W("src/fx_conf_writer.py",
      'MODELS = ["M0", "M1"]\n'
      'CKPT_FIELDS = ["rep", "fold", "model", "train_seed", "completed_at_kst", "artifact_sha256", "n_epochs",\n'
      '               "wall_seconds"]\n\n\n'
      'def partial_name(model, fold, seed):\n    return "%s_fold%d_seed%d.npz" % (model, fold, seed)\n\n\n'
      'OOF = "oof_%s_seed%d.npz"\n'
      'allowed_top = {"checkpoint.jsonl", "env_fingerprint.json", "access.log", "train_stdout.log"}\n'
      'PURPOSES = ["create", "assemble", "vscode-claude"]\n')
    W("src/fx_stab_writer.py",
      'def _partial_name(model, rep, fold, seed):\n    return "%s_rep%d_fold%d_seed%d.npz" % (model, rep, fold, seed)\n\n\n'
      'allowed_top = {"checkpoint.jsonl", "env_fingerprint.json", "access.log", "train_stdout.log"}\n'
      'PURPOSES = ["create", "vscode-claude"]\n')
    W("src/fx_pub_writer.py", 'PURPOSES = ["pub build", "vscode-claude"]\n')
    tA, tB, gc, gs, pub, sens = (R + "/fx_tA", R + "/fx_tB", R + "/fx_gc_rep1_seed201", R + "/fx_gs", R + "/fx_pub",
                                 R + "/fx_sens")
    W(tA + "/_sealed/a.npz", B(3, "a"))
    W(tA + "/_sealed/b.json", '{"macro_ap": %s, "delta": -0.0123456}\n' % FX_PLANT)
    W(tA + "/_sealed/lambda_selected.json", '{"lambda": 1}\n')
    W(tB + "/_sealed/x.npz", B(2, "x"))
    ck_rows = []
    for m in ("M0", "M1"):
        for f in (0, 1):
            rel = "%s/_sealed/_partial/%s_fold%d_seed42.npz" % (gc, m, f)
            W(rel, B(2, rel))
            ck_rows.append({"rep": 1, "fold": f, "model": m, "train_seed": 42, "completed_at_kst": "x",
                            "artifact_sha256": S(rel), "n_epochs": 77, "wall_seconds": 12.3456789})
    W(gc + "/_sealed/checkpoint.jsonl", "".join(json.dumps(r) + "\n" for r in ck_rows))
    for m in ("M0", "M1"):
        W("%s/_sealed/oof_%s_seed42.npz" % (gc, m), B(2, m + "oof"))
    W(gc + "/_sealed/env_fingerprint.json", '{"python": "3"}\n')
    W(gc + "/_sealed/train_stdout.log", "### x\nloss 0.123456789\n")
    for m in ("M0", "M1"):
        W("%s/_sealed/_partial/%s_rep1_fold0_seed3.npz" % (gs, m), B(2, m + "stab"))
    W(gs + "/_sealed/checkpoint.jsonl", '{"rep": 1}\n')
    W(gs + "/_sealed/env_fingerprint.json", '{"python": "3"}\n')
    W(gs + "/_sealed/train_stdout.log", "### y\n")
    W(pub + "/_sealed/r.json", '{"lambda": 0.5}\n')
    W(sens + "/_sealed/q.npz", B(1, "q"))
    ts = now_kst()

    def acc(purpose, he=False):
        return json.dumps({"ts_kst": ts, "type": "machine_read", "purpose": purpose, "human_exposure": he,
                           "path": "_sealed/", "actor": "vscode-claude"}, ensure_ascii=False) + "\n"
    W(tA + "/_sealed/access.log", json.dumps({"ts": ts, "type": "machine_read", "step": "legacy"}) + "\n" + acc("create"))
    W(gc + "/_sealed/access.log", acc("create") + acc("assemble"))
    W(gs + "/_sealed/access.log", acc("create"))
    W(pub + "/_sealed/access.log", acc("pub build"))
    # 기록원
    W("experiments/provenance/fx_ao.json", dumps({
        "hashes": {"sha256_all_sealed_artifacts": {tA + "/_sealed/a.npz": S(tA + "/_sealed/a.npz"),
                                                   tA + "/_sealed/b.json": S(tA + "/_sealed/b.json"),
                                                   tA + "/_sealed/lambda_selected.json":
                                                       S(tA + "/_sealed/lambda_selected.json"),
                                                   tB + "/_sealed/x.npz": S(tB + "/_sealed/x.npz")}},
        "opened_check": {"entries_per_file": {tA + "/_sealed/access.log": 1}}}))
    W(R + "/fx_auth/t4.json", dumps({
        "ts_kst": "2099-01-01 00:00:00 KST",
        "oof_sha256": {"rep1_seed201/oof_%s_seed42.npz" % m: S("%s/_sealed/oof_%s_seed42.npz" % (gc, m))
                       for m in ("M0", "M1")},
        "checkpoint_sha256": {"rep1_seed201": S(gc + "/_sealed/checkpoint.jsonl")}}))
    W(gs + "/s2.json", dumps({
        "ts_kst": "2099-01-01 00:00:00 KST",
        "partial_sha256": {"%s_rep1_fold0_seed3.npz" % m: S("%s/_sealed/_partial/%s_rep1_fold0_seed3.npz" % (gs, m))
                           for m in ("M0", "M1")},
        "checkpoint_sha256": S(gs + "/_sealed/checkpoint.jsonl")}))
    W(pub + "/manifest_public.json", dumps({"sealed_files": [
        {"name": "_sealed/r.json", "bytes": os.path.getsize(os.path.join(tmp, pub, "_sealed/r.json")),
         "sha256": S(pub + "/_sealed/r.json")}]}))
    W(sens + "/manifest_public.json", dumps({"sealed_files": [
        {"name": sens + "/_sealed/q.npz", "bytes": os.path.getsize(os.path.join(tmp, sens, "_sealed/q.npz")),
         "sha256": S(sens + "/_sealed/q.npz")}]}))
    gp0 = gc + "/_sealed/_partial/M0_fold0_seed42.npz"
    W("experiments/provenance/fx_fll.json", dumps([{"sealed_path": tA + "/_sealed",
                                                     "sealed_sha256": {"a.npz": S(tA + "/_sealed/a.npz")}},
                                                    {"inputs_machine_read": {"partials": {gp0: S(gp0)}}}]))
    W("cfg/gsf.json", dumps({"confirmatory_seed_prefix": [42], "model_scope_stability": ["M0", "M1"],
                             "training_seeds_ordered": [42, 3], "representative_units": [[201, 0]]}))
    W("cfg/ladder.json", dumps({"models_frozen": {"M0": [], "M1": []}}))
    W(R + "/fx_auth/plan_c.json", dumps({"rep_seed_map": {"1": 201}, "units": [
        {"rep": 1, "fold": f, "model": m, "train_seed": 42} for f in (0, 1) for m in ("M0", "M1")]}))
    W(gs + "/plan_s.json", dumps({"rep_seed_map": {"1": 201}, "units": [
        {"rep": 1, "fold": 0, "model": m, "train_seed": 3} for m in ("M0", "M1")]}))
    fz = {}
    for i in range(7):
        rel = "frozen/f%d.txt" % i
        W(rel, "frozen %d\n" % i)
        fz[rel] = {"sha256": S(rel), "bytes": os.path.getsize(os.path.join(tmp, rel))}
    W("frozen/freeze_manifest.json", dumps({"frozen_7": fz}))
    groups = {"confirm_gin": [gc], "stability": [gs], "pub": [pub], "sens": [sens], "__rest__": []}
    counts, fps, accl = stat_summary_v3(tmp, groups)
    W("src/fx_hist.py", 'H = ["%s", "%s"]\n' % (fps["confirm_gin__no_access"], fps["stability__no_access"]))
    W("docs/plan_rd.md", "R1 캘리브레이션 감사의 경계 일치는 보정 전 α=0.05 조건으로 한정한다.\n")
    spec = {
        "groups": groups, "top_keys": TOP_KEYS, "report_path": REPORT_REL, "frozen_manifest": "frozen/freeze_manifest.json",
        "egroup_of": {"existing": "E-A", "confirm_gin": "E-B", "stability": "E-C", "pub": "E-E", "sens": "E-F"},
        "expected": {"counts": counts, "fingerprints": fps, "access_lines": accl,
                     "egroup_counts": {"E-A": 4, "E-B": 9, "E-C": 5, "E-E": 1, "E-F": 1}, "n_total": 20,
                     "n_no_creation_hash": 4},
        "recorders": {"ao": {"path": "experiments/provenance/fx_ao.json", "key": "hashes.sha256_all_sealed_artifacts"},
                      "confirm": {"path": R + "/fx_auth/t4.json", "tree_fmt": R + "/fx_gc_rep{r}_seed{s}"},
                      "stability": {"path": gs + "/s2.json", "tree": gs},
                      "public": [{"path": pub + "/manifest_public.json", "tree": pub, "mode": "tree"},
                                 {"path": sens + "/manifest_public.json", "tree": sens, "mode": "repo"}]},
        "grid": {"writer_confirm": "src/fx_conf_writer.py", "writer_stab": "src/fx_stab_writer.py",
                 "confirm_partial_fmt": "%s_fold%d_seed%d.npz", "confirm_oof_fmt": "oof_%s_seed%d.npz",
                 "stab_partial_fmt": "%s_rep%d_fold%d_seed%d.npz", "gin_seed_freeze": "cfg/gsf.json",
                 "ladder": "cfg/ladder.json", "plan_confirm": R + "/fx_auth/plan_c.json", "plan_stab": gs + "/plan_s.json",
                 "n_folds": 2, "projection_keys": ["rep", "fold", "model", "train_seed", "artifact_sha256"],
                 "y4_names": ["env_fingerprint.json", "train_stdout.log"]},
        "y4_history": {"confirm_gin": "src/fx_hist.py", "stability": "src/fx_hist.py"},
        "secondary": {"runs_dir": R, "patterns": ["*_public.json"], "files": ["experiments/provenance/fx_fll.json"]},
        "access_required_keys": ["ts_kst", "type", "purpose", "human_exposure", "path", "actor"],
        "access_baseline": {tA + "/_sealed/access.log": 1}, "access_baseline_source": "fx_ao",
        "blocks": [
            {"id": "FX1", "docs": "fx", "trees": [tA, gc, gs], "writers": ["src/fx_conf_writer.py", "src/fx_stab_writer.py"],
             "window": ["2026-01-01 00:00:00", "2099-12-31 23:59:59"], "window_source": "fixture"},
            {"id": "FX2", "docs": "fx", "trees": [pub], "writers": ["src/fx_pub_writer.py"],
             "window": ["2026-01-01 00:00:00", "2099-12-31 23:59:59"], "window_source": "fixture"}],
        "rd": {"plan": "cfg/gsf.json", "plan_key": "model_scope_stability", "docs": ["docs/plan_rd.md"],
               "reporting_plan": "docs/plan_rd.md", "sidecar": "cfg/side.json", "sidecar_key": "r.r_d",
               "checklist_key": "c"},
        "oog": {"rule": "fixture", "expected": {"copy_files": [], "sealed_named_dirs": [],
                                                "files_in_sealed_named_dirs": []}},
        "planted": (FX_PLANT, "12.3456789", "0.0123456"),
    }
    W("cfg/side.json", dumps({"r": {"r_d": "보정 전 경계 한정"}, "c": ["점검"]}))
    return spec


def _fx_run(tmp, spec):
    man = build_expected(tmp, spec)
    return man, run_core(tmp, spec, man)


def _codes(det):
    return {b["code"] for b in det["blocking"]}


def _oracle_stat(tmp, groups):
    code = ("import sys, json; sys.path.insert(0, %r); import unblinding_run as u; "
            "c, f, a = u.stat_summary(%r, json.loads(%r)); print(json.dumps([c, f, a]))") % (HERE, tmp, json.dumps(groups))
    p = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout.strip().split("\n")[-1])


ALLOWED_IMPORTS = {"sys", "argparse", "ast", "builtins", "contextlib", "datetime", "fnmatch", "hashlib", "json", "os",
                   "re", "shutil", "subprocess", "tempfile"}
JSON_LOAD_FUNCS = {"read_json_public", "read_jsonl_public", "project_checkpoint", "parse_access_line", "_oracle_stat",
                   "_build_expected", "run_core", "_selftest_u17", "stage_selftest",   # stage_selftest = 가짜 저장소 fixture 만
                   "manual_gate_candidates", "rerun_compare", "_selftest_u18"}   # r2 — 공개 리포트 인용 JSON · 1회차 공개 산출물 사본


def hygiene_ast(src):
    tree = ast.parse(src)
    bad = []
    parent_fn = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            for n in ast.walk(fn):
                parent_fn.setdefault(id(n), fn.name)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    bad.append("import:" + a.name)
        elif isinstance(n, ast.ImportFrom):
            bad.append("importfrom:" + str(n.module))
        elif isinstance(n, ast.Attribute):
            if isinstance(n.value, ast.Name) and n.value.id == "os" and n.attr in ("environ", "getenv", "environb"):
                bad.append("os.environ")
            if n.attr == "load" and isinstance(n.value, ast.Name) and n.value.id in ("np", "numpy", "pickle"):
                bad.append("np.load")
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == "open":
                mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
                mv = mode.value if isinstance(mode, ast.Constant) else ("?" if mode is not None else "r")
                if any(c in str(mv) for c in "wax+?") and parent_fn.get(id(n)) != "_safe_write":
                    bad.append("open_write_outside_safe_write")
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "json" \
                    and f.attr in ("load", "loads") and parent_fn.get(id(n)) not in JSON_LOAD_FUNCS:
                bad.append("json_load_outside_allowed:" + str(parent_fn.get(id(n))))
    return bad


def _selftest_u17(tmp, spec):
    a1 = _fx_run(tmp, spec)[1][0]
    a2 = _fx_run(tmp, spec)[1][0]
    s1 = dumps({k: v for k, v in a1.items() if k != "audited_at_kst"})
    s2 = dumps({k: v for k, v in a2.items() if k != "audited_at_kst"})
    return json.loads(s1) == json.loads(s2) and s1 == s2


def _selftest_u18(tmp, spec):
    """U18 — 대응 규칙 (b). fixture 안정성 트리 access.log 에 수동 게이트 줄 1개를 붙이고 등록 리포트 문단을 변형해 7하위 사례."""
    gs = "experiments/runs/fx_gs"
    alog = gs + "/_sealed/access.log"
    a0 = os.path.getsize(os.path.join(tmp, alog))
    ts = now_kst()
    day = ts[:10]
    line = {"ts_kst": ts, "type": "machine_read", "purpose": "hash-compare", "human_exposure": False,
            "path": "_sealed/checkpoint.jsonl", "actor": "vscode-claude", "step": "fx P5 해시 대조", "note": "추가 키"}
    lb = (json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8")
    _safe_write(os.path.join(tmp, alog), read_bytes(os.path.join(tmp, alog)) + lb)
    c0 = a0 + len(lb)
    spec["expected"]["counts"], spec["expected"]["fingerprints"], spec["expected"]["access_lines"] = \
        stat_summary_v3(tmp, spec["groups"])
    quote = {k: v for k, v in line.items() if k not in ("ts_kst", "note")}
    rep_rel, other_rel = "docs/fx_av_report.md", "docs/fx_other_report.md"

    def para(n0=1, a=a0, c=c0, q=quote, with_quote=True):
        body = "`%s` — %d줄 → **%d줄** (%s B → %s B)\n" % (alog, n0, n0 + 1, format(a, ","), format(c, ","))
        if with_quote:
            body += "`%s`\n" % json.dumps(q, ensure_ascii=False)
        return "### 3-4. 조회 대장 (1줄)\n\n" + body + "\n---\n"

    def go(report_text, other_text=None, window=(day + " 00:00:00", day + " 23:59:59")):
        _safe_write(os.path.join(tmp, rep_rel), report_text)
        if other_text is not None:
            _safe_write(os.path.join(tmp, other_rel), other_text)
        sp = json.loads(dumps(spec))
        sp["planted"] = tuple(spec.get("planted", ()))
        sp["blocks"].append({"id": "FXAV", "docs": "fx", "trees": [gs], "writers": [], "report": rep_rel,
                             "report_sha256": sha_file(os.path.join(tmp, rep_rel)), "manual_lines_from_report": True,
                             "window": list(window), "window_source": "fixture"})
        _m, (a, d, _l) = _fx_run(tmp, sp)
        acc = d["access_audit"]
        pf = acc["per_file"][alog]
        return {"verdict": a["verdict"], "unattributed": "access_unattributed" in _codes(d),
                "by_rule": pf["by_rule"], "n_manual": acc["n_manual_attributed"],
                "manual_line": [x["line"] for x in acc["manual_lines"]]}
    hq = dict(quote, human_exposure=True)
    res = {
        "a": go(para()),
        "b": go(para(n0=2)),
        "c": go(para(with_quote=False)),
        "d": go("### 3-4. 조회 대장\n\n(문단 없음)\n", other_text=para()),
        "e": go(para(q=hq)),
        "f_offset": go(para(a=a0 + 1, c=c0 + 1)),
        "f_length": go(para(c=c0 + 3)),
        "g": go(para(), window=("2025-01-01 00:00:00", "2025-01-01 23:59:59")),
    }
    ok = {"a": res["a"]["verdict"] == "PASS" and not res["a"]["unattributed"] and res["a"]["n_manual"] == 1
          and res["a"]["by_rule"] == {"a_writer": 1, "b_manual_documented": 1} and res["a"]["manual_line"] == [2]}
    for k in ("b", "c", "d", "e", "f_offset", "f_length", "g"):
        ok[k] = res[k]["unattributed"] and res[k]["verdict"] == "FAIL" and res[k]["n_manual"] == 0
    return res, ok


def stage_selftest(out_dir):
    plan_groups = read_json_public(os.path.join(ROOT, PLAN_REL))["stat_groups"]
    before = (stat_summary_v3(ROOT, plan_groups), count_pycache(ROOT))
    cases = []

    def case(cid, title, expect, got, ok):
        cases.append({"id": cid, "title": title, "expect": expect, "got": got, "pass": bool(ok)})

    def fresh():
        d = tempfile.mkdtemp(prefix="preaudit_v3_fx_")
        return d, _fx_build(d)

    def mutate(tmp, rel, data):
        _safe_write(os.path.join(tmp, rel), data)

    tmps = []
    try:
        # U1 정상
        t, sp = fresh()
        tmps.append(t)
        man, (aud, det, log) = _fx_run(t, sp)
        case("U1", "정상 fixture", "PASS · 9키 정확 · 기록원 불일치 0",
             {"verdict": aud["verdict"], "keys": sorted(aud) == sorted(TOP_KEYS), "blocking": sorted(_codes(det)),
              "n_items": man["summary"]["n_total"]},
             aud["verdict"] == "PASS" and sorted(aud) == sorted(TOP_KEYS) and not check_schema(aud, TOP_KEYS, REPORT_REL)
             and man["summary"]["n_source_conflicts"] == 0)
        u1 = (aud, det, log)
        # U2 누락
        t, sp = fresh()
        tmps.append(t)
        os.remove(os.path.join(t, "experiments/runs/fx_tB/_sealed/x.npz"))
        _m, (a, d, _l) = _fx_run(t, sp)
        case("U2", "기대 파일 1개 삭제", "차단 missing", sorted(_codes(d)), "missing" in _codes(d) and a["verdict"] == "FAIL")
        # U3 초과
        t, sp = fresh()
        tmps.append(t)
        mutate(t, "experiments/runs/fx_tB/_sealed/extra.npz", b"zz")
        _m, (a, d, _l) = _fx_run(t, sp)
        case("U3", "기대 밖 파일 1개 추가", "차단 unexpected", sorted(_codes(d)), "unexpected" in _codes(d))
        # U4 바이트 변조(크기 같음)
        t, sp = fresh()
        tmps.append(t)
        p = os.path.join(t, "experiments/runs/fx_tA/_sealed/a.npz")
        b = bytearray(read_bytes(p))
        b[5] ^= 0xFF
        mutate(t, "experiments/runs/fx_tA/_sealed/a.npz", bytes(b))
        _m, (a, d, _l) = _fx_run(t, sp)
        case("U4", "바이트 1개 변조(크기 같음)", "차단 sha_mismatch", sorted(_codes(d)),
             "sha_mismatch" in _codes(d) and "size_mismatch" not in _codes(d))
        # U5 크기 변조
        t, sp = fresh()
        tmps.append(t)
        mutate(t, "experiments/runs/fx_pub/_sealed/r.json", '{"lambda": 0.55}\n')
        _m, (a, d, _l) = _fx_run(t, sp)
        case("U5", "크기 변조", "차단 size_mismatch", sorted(_codes(d)), "size_mismatch" in _codes(d))
        # U6 기록원 충돌
        t, sp = fresh()
        tmps.append(t)
        mutate(t, "experiments/provenance/fx_fll.json", dumps([{"sealed_path": "experiments/runs/fx_tA/_sealed",
                                                                 "sealed_sha256": {"a.npz": "0" * 64}}]))
        m6, (a, d, _l) = _fx_run(t, sp)
        case("U6", "기록원 2곳이 같은 파일에 다른 sha", "차단 source_conflict", sorted(_codes(d)),
             "source_conflict" in _codes(d) and m6["summary"]["n_source_conflicts"] >= 1)
        # U7 격자 불일치
        t, sp = fresh()
        tmps.append(t)
        T4 = read_json_public(os.path.join(t, "experiments/runs/fx_auth/t4.json"))
        T4["oof_sha256"]["rep1_seed201/oof_M9_seed42.npz"] = "1" * 64
        mutate(t, "experiments/runs/fx_auth/t4.json", dumps(T4))
        m7, (a, d, _l) = _fx_run(t, sp)
        case("U7", "기록원 이름 집합 ≠ 설계 격자", "차단 grid_mismatch", sorted(_codes(d)), "grid_mismatch" in _codes(d))
        # U8 checkpoint 키 위반 · sha 불일치
        t, sp = fresh()
        tmps.append(t)
        ckp = "experiments/runs/fx_gc_rep1_seed201/_sealed/checkpoint.jsonl"
        rows = [json.loads(x) for x in read_bytes(os.path.join(t, ckp)).decode().split("\n") if x.strip()]
        rows[0]["extra_key"] = 1
        mutate(t, ckp, "".join(json.dumps(r) + "\n" for r in rows))
        T4 = read_json_public(os.path.join(t, "experiments/runs/fx_auth/t4.json"))
        T4["checkpoint_sha256"]["rep1_seed201"] = sha_file(os.path.join(t, ckp))
        mutate(t, "experiments/runs/fx_auth/t4.json", dumps(T4))
        _m, (a, d1, _l) = _fx_run(t, sp)
        t2, sp2 = fresh()
        tmps.append(t2)
        T4 = read_json_public(os.path.join(t2, "experiments/runs/fx_auth/t4.json"))
        T4["checkpoint_sha256"]["rep1_seed201"] = "2" * 64
        mutate(t2, "experiments/runs/fx_auth/t4.json", dumps(T4))
        _m, (a, d2, _l) = _fx_run(t2, sp2)
        case("U8", "checkpoint 키 집합 위반 · checkpoint sha 기록원 불일치", "차단 checkpoint_format · checkpoint_sha_mismatch",
             [sorted(_codes(d1)), sorted(_codes(d2))],
             "checkpoint_format" in _codes(d1) and "checkpoint_sha_mismatch" in _codes(d2))
        # U9 access.log 대응 없음 · 감소 · human_exposure
        res9 = []
        for kind in ("unattributed", "decrease", "human"):
            t, sp = fresh()
            tmps.append(t)
            ap = os.path.join(t, "experiments/runs/fx_gc_rep1_seed201/_sealed/access.log")
            lines = read_bytes(ap).decode().split("\n")[:-1]
            if kind == "unattributed":
                e = json.loads(lines[0])
                e["purpose"] = "unknown purpose"
                lines.append(json.dumps(e))
                sp["expected"]["access_lines"]["experiments/runs/fx_gc_rep1_seed201"] += 1
            elif kind == "decrease":
                lines = lines[:1]
            else:
                e = json.loads(lines[0])
                e["human_exposure"] = True
                lines[0] = json.dumps(e)
            mutate(t, "experiments/runs/fx_gc_rep1_seed201/_sealed/access.log", "\n".join(lines) + "\n")
            _m, (a, d, _l) = _fx_run(t, sp)
            res9.append(sorted(_codes(d)))
        case("U9", "access.log 대응 없음 · 줄 수 감소 · human_exposure", "차단 각각", res9,
             "access_unattributed" in res9[0] and "access_lines_changed" in res9[1] and "human_exposure" in res9[2])
        # U10 Y4 비차단
        a, d, _l = u1
        y4n = [x for x in d["nonblocking"] if x["code"] == "no_creation_hash"]
        case("U10", "Y4 대상 파일만 기록 없음", "비차단 no_creation_hash · verdict PASS",
             {"n_no_creation_hash": len(y4n), "verdict": a["verdict"]}, len(y4n) == 4 and a["verdict"] == "PASS")
        # U11 오라클
        t = tmps[0]
        mine = list(stat_summary_v3(t, sp["groups"]))
        orc = _oracle_stat(t, sp["groups"])
        case("U11", "stat 지문·계수·access 개행 = unblinding_run.stat_summary(오라클)", "일치",
             {"oracle_ok": orc is not None, "n_fp_keys": len(mine[1]), "equal": orc == json.loads(json.dumps(mine))},
             orc is not None and orc == json.loads(json.dumps(mine)) and len(mine[1]) == 2 * len(sp["groups"]))
        # U12 스키마
        a = u1[0]
        f1 = check_schema(dict(a, extra=1), TOP_KEYS, REPORT_REL)
        f2 = check_schema({k: v for k, v in a.items() if k != "verdict"}, TOP_KEYS, REPORT_REL)
        f3 = check_schema(dict(a, report_path="docs/x.md"), TOP_KEYS, REPORT_REL)
        case("U12", "9키 외 키 · 키 누락 · report_path 다름", "스키마 검사 실패", [f1, f2, f3], bool(f1 and f2 and f3))
        # U13 누설 스캔
        a, d, lg = u1
        hits = leak_scan([("audit", dumps(a)), ("details", dumps(d)), ("log", "\n".join(lg))],
                         [("audit", a), ("details", d)], (FX_PLANT, "12.3456789", "0.0123456"))
        neg = leak_scan([("t", "x 0.12345 y")], [("o", {"wall_seconds": 1})])
        case("U13", "출력 누설 스캔(소수 4자리+ · 금지 키 · fixture 심은 값)", "0 (양성 대조 적발)",
             {"n_hits": len(hits), "positive_control_hits": len(neg)}, not hits and len(neg) == 2)
        # U14 위생 + 실저장소 불변
        bad = hygiene_ast(read_text_public(SELF))
        guard = False
        try:
            with no_sealed_io():
                os.listdir(os.path.join(tmps[0], "experiments/runs/fx_tA/_sealed"))
        except GuardViolation:
            guard = True
        case("U14", "AST 위생 · build-expected 봉인 I/O 가드 · 실저장소 불변(사후 확인)", "0 · 가드 작동 · 불변",
             {"ast_violations": bad, "guard_trips": guard}, not bad and guard)
        # U15 R-d
        cl = [rd_classify("R1 캘리브레이션 감사의 경계 일치는 Holm 보정 후 판정과 동일하다."),
              rd_classify("보정 전 α=0.05 에서의 R1 경계 일치는 Holm 보정 후 판정에도 그대로 승계된다."),
              rd_classify("R1 캘리브레이션 감사의 경계 일치는 보정 전 α=0.05 조건으로 한정한다."),
              rd_classify("§8 Power simulation 은 docs/94 R1 을 따른다."),
              rd_classify("prevalence 경계 PT 는 제외한다.")]
        case("U15", "R-d 검사기 — 확대 문장 적발 · 한정 문장 통과 · 비해당 분류", "작동", cl,
             cl == ["violation", "violation", "compliant", "a_only", "b_only"])
        # U16 범위 밖 사본
        t, sp = fresh()
        tmps.append(t)
        src = read_bytes(os.path.join(t, "experiments/runs/fx_tA/_sealed/a.npz"))
        mutate(t, "backup/x_sealed/a_copy.npz", src)
        alt = bytearray(src)
        alt[0] ^= 1
        mutate(t, "other/same_size.npz", bytes(alt))
        mutate(t, "backup/x_sealed/access.log", json.dumps({"type": "machine_read", "human_exposure": False}) + "\n")
        sp["oog"]["expected"] = {"copy_files": ["backup/x_sealed/a_copy.npz"], "sealed_named_dirs": ["backup/x_sealed"],
                                 "files_in_sealed_named_dirs": ["backup/x_sealed/a_copy.npz", "backup/x_sealed/access.log"]}
        _m, (a, d, _l) = _fx_run(t, sp)
        ok_a = (d["oog"]["copy_files"] == ["backup/x_sealed/a_copy.npz"] and "other/same_size.npz" not in d["oog"]["copy_files"]
                and d["oog"]["verdict"] == "non_blocking_recorded" and a["verdict"] == "PASS")
        mutate(t, "backup/x_sealed/access.log", json.dumps({"type": "machine_read", "human_exposure": True}) + "\n")
        _m, (a2, d2, _l) = _fx_run(t, sp)
        case("U16", "범위 밖 사본 — 동일 사본 기록 · 같은 크기 다른 바이트 비사본 · 사본 디렉터리 human_exposure 차단", "작동",
             {"recorded": ok_a, "blocking_after_human": sorted(_codes(d2))}, ok_a and "oog_rule_b" in _codes(d2))
        # U17 결정성
        t, sp = fresh()
        tmps.append(t)
        same = _selftest_u17(t, sp)
        case("U17", "재실행 결정성(audited_at_kst 제외 바이트 동일)", "동일", same, same)
        # U18 대응 규칙 (b) — 바이트로 고정된 문서화 수동 게이트 줄 (docs/119b Z1 · A-3)
        t, sp = fresh()
        tmps.append(t)
        r18, ok18 = _selftest_u18(t, sp)
        case("U18", "대응 규칙 (b) — a 전 조건 일치 대응 · b 순번 · c 인용 없음 · d 미등록 문서 · e 인용 값 · "
                    "f 오프셋/길이 · g 시간창 → 차단",
             "a = b_manual_documented · b~g = access_unattributed", {"cases": r18, "sub_pass": ok18},
             all(ok18.values()) and len(ok18) == 8)
    finally:
        _STATE["fixture_root"] = None
        for t in tmps:
            shutil.rmtree(t, ignore_errors=True)
    after = (stat_summary_v3(ROOT, plan_groups), count_pycache(ROOT))
    inv = before == after
    for c in cases:
        if c["id"] == "U14":
            c["got"]["real_repo_invariant"] = inv
            c["pass"] = c["pass"] and inv
    res = {"block": BLOCK, "instruction": INSTRUCTION, "ts_kst": now_kst(), "script_sha256": sha_file(SELF),
           "n_cases": len(cases), "n_pass": sum(c["pass"] for c in cases),
           "all_pass": all(c["pass"] for c in cases) and len(cases) == 18, "cases": cases}
    hits = leak_scan([("selftest", dumps(res))], [], (FX_PLANT, "12.3456789", "0.0123456"))
    res["leak_hits"] = len(hits)
    res["all_pass"] = res["all_pass"] and not hits
    _safe_write(os.path.join(out_dir, SELFTEST_R2_NAME), dumps(res))
    print("selftest %d/%d · all_pass %s" % (res["n_pass"], res["n_cases"], res["all_pass"]))
    for c in cases:
        print("  %s %s" % (c["id"], "PASS" if c["pass"] else "FAIL"))
    return 0 if res["all_pass"] else 1


def stage_build_expected(out_dir):
    spec = real_spec(ROOT)
    out = os.path.join(out_dir, EXPECTED_NAME)
    if os.path.exists(out):
        print("expected manifest 이미 존재 — 재생성 거부")
        return 3
    man = build_expected(ROOT, spec)
    _safe_write(out, dumps(man))
    s = man["summary"]
    print("expected %d · by_egroup %s · by_class %s · conflicts %d · blocking %d" % (
        s["n_total"], s["by_egroup"], s["by_class"], s["n_source_conflicts"], len(man["blocking"])))
    print("sha256 %s" % sha_file(out))
    return 0 if not man["blocking"] else 2


# ── Z5 — 1회차(run1_FAIL) 대비 섹션 대조 (docs/119b §0-2 Z5 · 선언 변화는 Phase A 에 고정) ──────────────
Z5_AUDIT_EXCLUDE = ("verdict", "audited_at_kst")
Z5_DETAILS_EXCLUDE = ("access_audit", "blocking", "n_blocking", "verdict", "script_sha256", "selftest_sha256",
                      "audit_json_sha256",                                  # ↑ 지시서 Z5 제외 (nonblocking 은 access 관련만 제외)
                      "block", "instruction", "rerun_vs_run1")              # ↑ 러너 선언 — 라벨 메타 · 본 섹션
Z5_DECLARED = {
    "D1 ops.c_ay_phaseA_deviations": "spec_item 73 → 71 · spec_item_matches_found false → true (Z3 정정의 직접 결과) · 나머지 동일",
    "D2 doc_corrections": "targets 중 항목 ≤ 79 = 1회차 targets 와 동일 · 항목 ≥ 80(1회차 이후 기록) 추가분은 목록만 · "
                          "n_targets 제외 · correction_text·supported_by_sha_audit 동일",
    "D3 ledgers": "table[].doc45_line 이 모든 행에서 같은 상수 k ≥ 0 만큼 이동(docs/45 §2·§3 append) · 나머지 동일",
    "D4 oog": "n_files_scanned · n_files_hashed 제외(저장소 전역 파일 수 — 봉인 무관) · 나머지 동일",
}


def rerun_compare(aud, det, a1, d1):
    """같은 입력이면 같아야 하는 섹션을 1회차와 대조. 반환 = 섹션별 동일 불리언 + 선언 변화 판정(값 출력 0)."""
    ka = sorted((set(aud) | set(a1)) - set(Z5_AUDIT_EXCLUDE))
    audit_keys = {k: k in aud and k in a1 and dumps(aud[k]) == dumps(a1[k]) for k in ka}
    secs, post80, k_shift = {}, [], None
    for k in sorted((set(det) | set(d1)) - set(Z5_DETAILS_EXCLUDE) - {"nonblocking"}):
        if k not in det or k not in d1:
            secs[k] = False
            continue
        x, y = json.loads(dumps(det[k])), json.loads(dumps(d1[k]))
        if k == "ops":
            cx, cy = x.get("c_ay_phaseA_deviations", {}), y.get("c_ay_phaseA_deviations", {})
            ok = (cx.pop("spec_item", None) == 71 and cy.pop("spec_item", None) == 73
                  and cx.pop("spec_item_matches_found", None) is True and cy.pop("spec_item_matches_found", None) is False)
            secs[k] = ok and dumps(x) == dumps(y)
        elif k == "doc_corrections":
            tx, ty = x.pop("targets", []), y.pop("targets", [])
            x.pop("n_targets", None)
            y.pop("n_targets", None)
            post80 = [{"item": t["item"], "line": t["line"]} for t in tx if t["item"] >= 80]
            secs[k] = (dumps([t for t in tx if t["item"] <= 79]) == dumps(ty) and all(t["item"] <= 79 for t in ty)
                       and dumps(x) == dumps(y))
        elif k == "ledgers":
            rx, ry = x.get("table", []), y.get("table", [])
            sh = {(a.pop("doc45_line", None) or 0) - (b.pop("doc45_line", None) or 0) for a, b in zip(rx, ry)}
            k_shift = sorted(sh)
            secs[k] = len(rx) == len(ry) and len(sh) <= 1 and all(s >= 0 for s in sh) and dumps(x) == dumps(y)
        elif k == "oog":
            for z in (x, y):
                z.pop("n_files_scanned", None)
                z.pop("n_files_hashed", None)
            secs[k] = dumps(x) == dumps(y)
        else:
            secs[k] = dumps(x) == dumps(y)
    nb = lambda d: [v for v in d.get("nonblocking", []) if "access" not in str(v.get("code", ""))]   # noqa: E731
    secs["nonblocking(access 관련 제외)"] = dumps(nb(det)) == dumps(nb(d1))
    return {"audit_keys_identical": audit_keys, "audit_7keys_identical": len(ka) == 7 and all(audit_keys.values()),
            "details_sections_identical": secs, "details_all_identical": all(secs.values()),
            "details_excluded": list(Z5_DETAILS_EXCLUDE) + ["nonblocking(access 관련만)"], "declared_changes": Z5_DECLARED,
            "doc_corrections_post_run1_targets": post80, "ledgers_doc45_line_shift": k_shift,
            "all_identical": len(ka) == 7 and all(audit_keys.values()) and all(secs.values())}


def stage_run(out_dir, root=ROOT, spec=None, gate_fn=None):
    """root·spec·gate_fn 인자는 개발 중 가짜 저장소 점검용 — CLI 는 실저장소 기본값만 쓴다."""
    spec = spec or real_spec(root)
    gate_fn = gate_fn or real_gates
    st_p, ex_p = os.path.join(out_dir, SELFTEST_R2_NAME), os.path.join(out_dir, EXPECTED_NAME)
    r1 = os.path.join(out_dir, RUN1_DIR)
    log = []
    try:
        if (os.path.exists(os.path.join(root, AUDIT_REL)) or os.path.exists(os.path.join(out_dir, DETAILS_NAME))
                or os.path.exists(os.path.join(out_dir, RUNLOG_NAME)) or os.path.exists(os.path.join(root, REPORT_REL))):
            raise PreconditionFail("audit_outputs_exist")
        if sorted(os.listdir(out_dir)) != sorted([SELFTEST_NAME, SELFTEST_R2_NAME, EXPECTED_NAME, RUN1_DIR]):
            raise PreconditionFail("out_dir_state")
        if sorted(os.listdir(r1)) != sorted(RUN1_ARCHIVE) or any(
                sha_file(os.path.join(r1, n)) != s for n, s in RUN1_ARCHIVE.items()):
            raise PreconditionFail("run1_archive")
        st = read_json_public(st_p)
        me = sha_file(SELF)
        mk = doc33_markers(root)
        cur = {"expected_manifest_v3": sha_file(ex_p), "audit_script_r2": me, "selftest_r2": sha_file(st_p)}
        for k, v in cur.items():
            if not mk[k] or set(mk[k]) != {v} or (k != "expected_manifest_v3" and len(mk[k]) != 1):
                raise PreconditionFail("doc33_marker:" + k)
        if not (st.get("all_pass") is True and st.get("script_sha256") == me):
            raise PreconditionFail("selftest_binding")
        g0 = gate_fn(root, spec)
        log.append("%s\tgates_start\t%s" % (now_kst(), " ".join("%s=%s" % kv for kv in sorted(g0.items()))))
        if not all(g0.values()):
            raise PreconditionFail("gates_start:" + ",".join(k for k, v in g0.items() if not v))
        man = read_json_public(ex_p)
        aud, det, clog = run_core(root, spec, man)
        log += clog
        g1 = gate_fn(root, spec)
        log.append("%s\tgates_end\t%s" % (now_kst(), " ".join("%s=%s" % kv for kv in sorted(g1.items()))))
        det["real_gates_start"], det["real_gates_end"] = g0, g1
        if not all(g1.values()):
            det["blocking"].append({"code": "gates_end_changed", "fails": [k for k, v in g1.items() if not v]})
            aud["verdict"] = det["verdict"] = "FAIL"
            det["n_blocking"] = len(det["blocking"])
        det.update({"script_sha256": me, "expected_manifest_sha256": cur["expected_manifest_v3"],
                    "selftest_sha256": cur["selftest_r2"]})
        z5 = rerun_compare(aud, det, read_json_public(os.path.join(r1, "pre_unblinding_audit_v3.json")),
                           read_json_public(os.path.join(r1, DETAILS_NAME)))
        z5.update({"run1_dir": os.path.relpath(r1, root), "run1_archive_sha256": RUN1_ARCHIVE})
        det["rerun_vs_run1"] = z5
        log.append("%s\trerun_vs_run1\taudit_7keys %s · details %s" % (
            now_kst(), z5["audit_7keys_identical"], z5["details_all_identical"]))
        if not z5["all_identical"]:
            det["blocking"].append({"code": "rerun_vs_run1_mismatch",
                                    "sections": sorted([k for k, v in z5["audit_keys_identical"].items() if not v]
                                                       + [k for k, v in z5["details_sections_identical"].items() if not v])})
        if leak_scan([("rerun_vs_run1", dumps(z5))], [("rerun_vs_run1", z5)], spec.get("planted", ())):
            det["blocking"].append({"code": "output_leak", "where": "rerun_vs_run1"})
        if det["blocking"]:
            aud["verdict"] = det["verdict"] = "FAIL"
            det["n_blocking"] = len(det["blocking"])
        ab = dumps(aud)
        _safe_write(os.path.join(root, AUDIT_REL), ab)
        det["audit_json_sha256"] = sha_bytes(ab.encode("utf-8"))
        _safe_write(os.path.join(out_dir, DETAILS_NAME), dumps(det))
        log.append("%s\twritten\taudit %s · details" % (now_kst(), det["audit_json_sha256"]))
        _safe_write(os.path.join(out_dir, RUNLOG_NAME), "\n".join(log) + "\n")
        print("verdict %s · blocking %d · audit sha %s" % (aud["verdict"], det["n_blocking"], det["audit_json_sha256"]))
        return 0 if aud["verdict"] == "PASS" else 2
    except PreconditionFail as e:
        print("전제 불충족: %s" % e)
        return 3
    except Exception as e:                                          # noqa: BLE001 — Y10 중도 실패: 9키 JSON 미작성
        log.append("%s\tcrash\t%s" % (now_kst(), type(e).__name__))
        try:
            _safe_write(os.path.join(out_dir, RUNLOG_NAME), "\n".join(log) + "\n")
        except Exception:                                           # noqa: BLE001
            pass
        print("중도 실패: %s (9키 JSON 미작성)" % type(e).__name__)
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["selftest", "build-expected", "run"])
    ap.add_argument("--out", default=os.path.join(ROOT, OUT_REL))
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if a.stage == "selftest":
        return stage_selftest(out)
    if a.stage == "build-expected":
        return stage_build_expected(out)
    return stage_run(out)


if __name__ == "__main__":
    sys.exit(main())
