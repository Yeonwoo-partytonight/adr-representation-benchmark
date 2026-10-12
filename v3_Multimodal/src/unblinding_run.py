"""unblinding_run.py — 블록 BC (docs/118) 개봉 스크립트 · 120 개봉 실행 전용 (본 블록은 selftest 만).

동결 계획 `v3_Multimodal/config/unblinding_plan_v1.json` 이 개봉이 계산·공개할 **모든 것**의 정본이다.
이 스크립트는 항목·인자·경로·시드·B 를 재기술하지 않는다(selftest U1 AST). 계획 dict 를 인자로 받는
`core(root, plan, expected, out_root, fault=None, hooks=None)` 가 R1~R7 을 수행한다.

  --stage selftest (기본) : 합성 저장소(tempfile)에 B 를 줄인 합성 계획을 넘겨 core 를 태운다. 실저장소 판독 0.
  --stage run             : 승인 G-gate(`gate(root, expected)`) 통과 시에만 core 실행. 디스크 계획 sha == PLAN_SHA256.
  --stage status          : 진행 상태(항목 id·오류 코드·파일명·개수)만 출력. 값 0.
  --out                   : selftest 결과 경로(selftest 전용).
환경변수 판독 0(스레드 변수 «설정»만 — numpy import 전 · 블록 AY 선례).

⛔ 무결성 (docs/118 §2 · BC-2)
  · 판정 함수·검정·부트스트랩은 `sap.*` 를 import 해 그대로 호출한다(재구현 0). 결과 의존 분기 0.
  · 진행 표시·heartbeat·예외 메시지·status 출력 = 항목 id·시각·개수·오류 코드뿐(값 0).
  · 무결성 실패(입력 결손·sha 불일치·키 충돌·확증 비유한·완전성·G1 비트 불일치·독립 검산 불일치) → 즉시 중단 ·
    `_staging/failure.json`(코드·항목 id·파일명) · 재개 금지 · 공개 0. 실패·중단 상태 staging 의 사람 열람 금지.
  · 재개(값 무관 중단: 전원·SIGTERM·크래시·감시 래퍼 재시작) = 같은 명령 재실행 · 완료 항목 건너뜀(결정적).
  · `sap.redaction.open_sealed` 미호출 — 파일별 사람 열람 경로가 아니라 R7 의 일괄 공개다(계획 JSON 명시).
종료 코드 = 0 완료 · 1 비정상(재개 대상) · 9 락 바쁨 · 10 부하 · 12 G-gate 거부 · 13 무결성 실패 · 15 전원.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import os

for _tv in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
            "NUMEXPR_NUM_THREADS"):
    os.environ[_tv] = "1"                    # 블록 AY 선례 · numpy import 전 «설정»(판독 0)

import argparse
import ast
import builtins
import copy
import csv
import datetime
import glob
import hashlib
import io
import json
import re
import shutil
import signal
import subprocess
import tempfile

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── 동결 결속 상수 (계획 JSON 은 이 스크립트의 해시를 갖지 않는다 — 순환 방지) ──────────
PLAN_REL = "v3_Multimodal/config/unblinding_plan_v1.json"
PLAN_SHA256 = "d5aa594b630992fd10739573409a2008227db72a843f310b001b9ca24ce59764"
PRE_IMPORT_SHA = {
    "v3_Multimodal/src/sap/__init__.py": "8dc63e28ffcf93dcdfde7facd0cf1d51b6e6c15ac4de2304de61c12ccb7a5306",
    "v3_Multimodal/src/sap/metrics.py": "a7d3fe4fe9e87983b35b086b0c464bde1e710e013f98813a2f28a2b48c8b2004",
    "v3_Multimodal/src/sap/signflip.py": "3de1223585ae0f978438bacfdd8e439c7f0ce95b776d615d098a5881e6ce06d2",
    "v3_Multimodal/src/sap/bootstrap.py": "05437c516e606a053e02acefb23c2597365472201b6c70ff2814278d6597a31e",
    "v3_Multimodal/src/sap/decision.py": "f688b20d816acabe17c2906cfa846c1f794ba45a416248c08aa7e41676e82a92",
    "v3_Multimodal/src/sap/consensus.py": "9bddb53da5752c460ad2ac8f594a6ed09dd2e08c332a28fcd8bed0812ab58c91",
    "v3_Multimodal/src/confirmatory_oof_rep1.py": "afb894c09fdaad6f1c75df789c5e2ede1dbbc2151a8c30b8eda6044cd6f336b6",
    "v3_Multimodal/src/ladder_confirmatory.py": "13a17129db6a6679bd6dbdc28a12c0f31e2e8d6b0811130450add602daf5137c",
}

EXIT_OK, EXIT_CRASH, EXIT_LOCK_BUSY, EXIT_LOAD, EXIT_GATE, EXIT_INTEGRITY, EXIT_POWER = 0, 1, 9, 10, 12, 13, 15
KST = datetime.timezone(datetime.timedelta(hours=9))


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    with open(p, "rb") as f:
        return sha256_bytes(f.read())


def _verify_pre_import(root):
    for rel, s in PRE_IMPORT_SHA.items():
        if sha256_file(os.path.join(root, rel)) != s:
            raise SystemExit("import 전 sha 불일치: " + rel)


_verify_pre_import(ROOT)
import sap.bootstrap as sb                              # noqa: E402
import sap.decision as sd                               # noqa: E402
import sap.metrics as sm                                # noqa: E402
import sap.signflip as ss                               # noqa: E402
from confirmatory_oof_rep1 import scaffold_of           # noqa: E402  (블록 AY 하네스와 같은 군 구성)

# 계획의 함수 이름 → 동결 함수 (계획이 고르는 대상 · 여기서 인자를 정하지 않는다)
FUNCS = {
    "sap.signflip.scaffold_signflip": ss.scaffold_signflip,
    "sap.bootstrap.paired_scaffold_bootstrap": sb.paired_scaffold_bootstrap,
    "sap.decision.tost_equivalence": sd.tost_equivalence,
    "sap.decision.rq2_decision": sd.rq2_decision,
    "sap.decision.rq3_decision": sd.rq3_decision,
    "sap.decision.rq4_decision": sd.rq4_decision,
    "sap.decision._contrast_pass": sd._contrast_pass,
    "sap.decision.holm": sd.holm,
    "sap.decision.bh_fdr": sd.bh_fdr,
    "sap.decision.pt_eligibility": sd.pt_eligibility,
    "sap.metrics.macro_ap": sm.macro_ap,
}


# ═══════════════════════════════════════════════════════════════════════════
# 예외 · 보조
# ═══════════════════════════════════════════════════════════════════════════
class IntegrityFailure(Exception):
    """무결성 실패 — 재개 금지. code·item·file 만 싣는다(값 0)."""

    def __init__(self, code, item="", file=""):
        super().__init__("%s|%s|%s" % (code, item, file))
        self.code, self.item, self.file = code, item, file


class GateRefused(Exception):
    pass


class PowerLoss(Exception):
    pass


class _Fault(Exception):
    """selftest 전용 — 값 무관 중단(SIGTERM·크래시) 모의."""


def now_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " KST"


def _json_safe(o):
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _json_safe(o.tolist())
    return o


def _json_bytes(obj):
    return (json.dumps(_json_safe(obj), indent=2, ensure_ascii=False, allow_nan=False, sort_keys=True)
            + "\n").encode("utf-8")


def _get(obj, path):
    for k in path:
        obj = obj[k]
    return obj


class Writer:
    """런타임 쓰기 가드 — 허용 경로 밖 쓰기는 IntegrityFailure."""

    def __init__(self, allowed_roots, allowed_files):
        self.roots = [os.path.abspath(r) + os.sep for r in allowed_roots]
        self.files = {os.path.abspath(f) for f in allowed_files}

    def check(self, p):
        a = os.path.abspath(p)
        if a in self.files or any(a.startswith(r) for r in self.roots):
            return a
        raise IntegrityFailure("write_guard", file=os.path.basename(p))

    def atomic(self, dest, data):
        dest = self.check(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".partial"
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dest)

    def append_line(self, path, obj):
        path = self.check(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    raise IntegrityFailure("access_log_no_trailing_newline", file=os.path.basename(path))
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


# ═══════════════════════════════════════════════════════════════════════════
# 봉인 stat (G-gate · 감사 대조) — 이름·크기만
# ═══════════════════════════════════════════════════════════════════════════
def sealed_stat(root):
    lines, dirs = [], 0
    for dp, dn, fn in os.walk(root):
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
    return sha256_bytes(("\n".join(s) + "\n").encode("utf-8"))


def stat_summary(root, groups):
    """계획 `stat_groups`(그룹 → 접두 목록 · `__rest__` = 나머지) 규칙으로 지문·계수·access 개행."""
    dirs, lines = sealed_stat(root)
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
            with open(os.path.join(root, r), "rb") as f:
                acc[os.path.dirname(os.path.dirname(r))] = f.read().count(b"\n")
    n_acc = sum(1 for x in lines if x[2])
    counts = {"n_sealed_dirs": dirs, "n_sealed_files_total": len(lines), "n_sealed_artifacts": len(lines) - n_acc,
              "n_access_log": n_acc}
    return counts, fps, acc


# ═══════════════════════════════════════════════════════════════════════════
# G-gate (run 전용 · 순수 함수) — 실패 사유 리스트 반환(쓰기 0)
# ═══════════════════════════════════════════════════════════════════════════
def gate(root, expected):
    """expected = {"plan": dict, "launch_lines": {tree: int}} — 계획에서 경로를 읽는다."""
    plan = expected["plan"]
    ab = plan["approval_binding"]
    fails = []
    ap = os.path.join(root, ab["record_path"])
    if not os.path.exists(ap):
        return ["approval_missing"]
    try:
        A = json.loads(open(ap, "rb").read().decode("utf-8"))
    except Exception:            # noqa: BLE001
        return ["approval_unreadable"]
    if set(A) != set(ab["required_fields"]):
        fails.append("approval_fields")
    if A.get("approver") != ab["approver"]:
        fails.append("approval_approver")
    ev = A.get("evidence") or {}
    if set(ev) != set(ab["evidence_fields"]) or not all(isinstance(ev.get(k), str) and ev.get(k) for k in ev):
        fails.append("approval_evidence")
    ah = A.get("approved_hashes") or {}
    if set(ah) != set(ab["approved_hashes_paths"]):
        fails.append("approval_hash_set")
    else:
        for rel, s in ah.items():
            p = os.path.join(root, rel)
            if not os.path.exists(p) or sha256_file(p) != s:
                fails.append("approval_hash_mismatch:" + os.path.basename(rel))
    src = plan["expected_hash_source"]
    aud_p = os.path.join(root, src["audit_path"])
    if not os.path.exists(aud_p):
        fails.append("audit_missing")
        return fails
    AU = json.loads(open(aud_p, "rb").read().decode("utf-8"))
    if set(AU) != set(src["top_level_keys"]) or AU.get("verdict") != "PASS" or AU.get("audit_version") != "v3":
        fails.append("audit_verdict_or_schema")
        return fails
    if AU.get("report_path") != src["report_path"]:
        fails.append("audit_report_path")
    counts, fps, acc = stat_summary(root, plan["stat_groups"])
    ll = expected.get("launch_lines") or {}
    resume = any(ll.values())
    n_new = sum(1 for t in ll if ll[t] and t not in AU["access_log_lines"])
    exp_counts = dict(AU["sealed_counts"])
    exp_counts["n_sealed_files_total"] += n_new
    exp_counts["n_access_log"] += n_new
    if counts != exp_counts:
        fails.append("sealed_counts_changed")
    for g, s in AU["stat_fingerprints"].items():
        if (not resume or g.endswith("__no_access")) and fps.get(g) != s:
            fails.append("stat_fingerprint_changed:" + g)
    exp_acc = dict(AU["access_log_lines"])
    for t, n in ll.items():
        exp_acc[t] = exp_acc.get(t, 0) + n
    if acc != exp_acc:
        fails.append("access_log_lines_changed")
    fl = plan["flags"]
    for rel in fl["gin_start_still_blocked_true"]:
        if json.loads(open(os.path.join(root, rel), "rb").read())["gin_start_still_blocked"] is not True:
            fails.append("flag_blocked:" + os.path.basename(rel))
    for rel in fl["unblinding_performed_false"]:
        if json.loads(open(os.path.join(root, rel), "rb").read())["unblinding_performed"] is not False:
            fails.append("flag_unblinding:" + os.path.basename(rel))
    out = plan["outputs"]
    found = sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, out["presence_glob"])))
    if found and found != [out["root"]]:
        fails.append("unexpected_output_dirs")
    o = os.path.join(root, out["root"])
    if os.path.exists(o):
        if os.path.exists(os.path.join(o, out["failure_file"])):
            fails.append("prior_integrity_failure")
        if os.path.exists(os.path.join(o, out["results_dir"])):
            fails.append("results_already_published")
        if not os.path.exists(os.path.join(o, out["launches_file"])):
            fails.append("output_exists_not_resume_state")
    elif resume:
        fails.append("launch_lines_without_output")
    lk = os.path.join(root, plan["long_run"]["compute_lock_path"])
    if os.path.exists(lk):
        try:
            pid = int(json.loads(open(lk, "rb").read()).get("pid"))
            os.kill(pid, 0)
            fails.append("compute_lock_held")
        except (ProcessLookupError, ValueError, TypeError):
            pass
        except PermissionError:
            fails.append("compute_lock_held")
    return fails


def launch_lines(root, plan):
    """이전 launch 가 R1 에서 append 한 access.log 줄 수(트리별) — launches 기록에서 복원."""
    out = plan["outputs"]
    lp = os.path.join(root, out["root"], out["launches_file"])
    ll = {}
    if os.path.exists(lp):
        for ln in open(lp, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                for t in e.get("r1_trees", []):
                    ll[t] = ll.get(t, 0) + 1
                for t in e.get("r7_trees", []):
                    ll[t] = ll.get(t, 0) + 1
    return ll


# ═══════════════════════════════════════════════════════════════════════════
# core — R1~R7
# ═══════════════════════════════════════════════════════════════════════════
class Ctx:
    def __init__(self, root, plan, expected, out_root, fault, hooks):
        self.root, self.plan, self.expected, self.out_root = root, plan, expected, out_root
        self.fault = set(fault or ())
        self.hooks = hooks or {}
        O = plan["outputs"]
        self.staging = os.path.join(out_root, O["staging_dir"])
        self.items_dir = os.path.join(self.staging, O["items_subdir"])
        self.hb_path = os.path.join(out_root, O["heartbeat_file"])
        trees = [os.path.join(root, t, "_sealed", "access.log") for t in plan["read_scope"]["trees"]]
        self.w = Writer([out_root], trees + [os.path.join(root, plan["outputs"]["event_path"])])
        self.power = self.hooks.get("power", lambda: True)
        self.load1 = self.hooks.get("load1", lambda: 0.0)
        self.calls = self.hooks.get("call_log")            # selftest U6 — 호출 기록

    def heartbeat(self, event, item=""):
        self.w.append_line(self.hb_path, {"ts_kst": now_kst(), "event": event, "item": item,
                                          "power_ok": bool(self.power()), "load1": round(float(self.load1()), 2)})

    def call(self, name, *a, **kw):
        if self.calls is not None:
            self.calls.append({"func": name, "kwargs": {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                                                        for k, v in kw.items()
                                                        if k not in ("y", "scaffold_group")},
                               "arg_ids": [id(x) for x in a[:2]]})
        return FUNCS[name](*a, **kw)

    def fail(self, code, item="", file=""):
        e = IntegrityFailure(code, item, file)
        self.w.atomic(os.path.join(self.staging, self.plan["outputs"]["failure_file"]),
                      _json_bytes({"code": code, "item": item, "file": file, "ts_kst": now_kst()}))
        raise e


def _fault_hit(ctx, tag):
    if tag in ctx.fault:
        raise _Fault(tag)


def _load_inputs(ctx):
    """R2 — 계획 입력 전부 sha 대조 후 같은 바이트에서 로드."""
    P, root = ctx.plan, ctx.root
    exp = ctx.expected["sealed_sha256"]
    lab = P["labels"]
    bx = open(os.path.join(root, lab["master_x"]["path"]), "rb").read()
    by = open(os.path.join(root, lab["master_y"]["path"]), "rb").read()
    if sha256_bytes(bx) != ctx.expected["labels_sha256"]["master_x"]:
        ctx.fail("sha_mismatch", file=os.path.basename(lab["master_x"]["path"]))
    if sha256_bytes(by) != ctx.expected["labels_sha256"]["master_y"]:
        ctx.fail("sha_mismatch", file=os.path.basename(lab["master_y"]["path"]))
    X, Y = pd.read_parquet(io.BytesIO(bx)), pd.read_parquet(io.BytesIO(by))
    if list(X["cid"]) != list(Y["cid"]) or list(X["cid"]) != sorted(X["cid"]):
        ctx.fail("label_order")
    ycols = [c for c in Y.columns if c != "cid"]
    y = Y[ycols].values.astype(int)
    D = P["design"]
    if y.shape != (D["n_rows"], D["n_pt"]):
        ctx.fail("label_shape")
    scaf = [scaffold_of(s) for s in X[lab["smiles_column"]].tolist()]
    uniq = sorted(set(scaf))
    gidx = {g: i for i, g in enumerate(uniq)}
    gi = np.array([gidx[s] for s in scaf], dtype=int)
    if len(uniq) != D["n_groups"]:
        ctx.fail("n_groups")
    blobs = {}
    for rel in P["read_scope"]["files"]:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            ctx.fail("input_missing", file=rel)
        b = open(p, "rb").read()
        if rel not in exp or sha256_bytes(b) != exp[rel]:
            ctx.fail("sha_mismatch", file=rel)
        blobs[rel] = b
    cid = X["cid"].astype(np.int64).values
    return {"y": y, "ycols": ycols, "gi": gi, "cid": cid, "blobs": blobs}


def _matrix(ctx, data, rel, item_id):
    key = ("M", rel)
    if key in data:
        return data[key]
    NZ = ctx.plan["npz_schema"]
    with np.load(io.BytesIO(data["blobs"][rel]), allow_pickle=False) as z:
        if set(z.files) != set(NZ["keys"]):
            ctx.fail("npz_keys", item_id, rel)
        C, cid = z[NZ["matrix_key"]], z[NZ["cid_key"]]
    if C.shape != data["y"].shape or not np.array_equal(np.asarray(cid, dtype=np.int64), data["cid"]):
        ctx.fail("matrix_shape_or_order", item_id, rel)
    if not np.isfinite(C).all():
        ctx.fail("matrix_nonfinite", item_id, rel)
    data[key] = C.astype(np.float64)
    return data[key]


def _jload(data, rel):
    key = ("J", rel)
    if key not in data:
        data[key] = json.loads(data["blobs"][rel].decode("utf-8"))
    return data[key]


def _eligible(ctx):
    return np.arange(ctx.plan["design"]["n_pt"])


def _item_paths(ctx, iid):
    return (os.path.join(ctx.items_dir, iid + ".json"), os.path.join(ctx.items_dir, iid + ".perm.npy"),
            os.path.join(ctx.items_dir, iid + ".boot.npy"))


def _save_npy(ctx, path, arr):
    buf = io.BytesIO()
    np.save(buf, np.asarray(arr, dtype=np.float64), allow_pickle=False)
    ctx.w.atomic(path, buf.getvalue())


def _part(ctx, iid, part):
    return os.path.join(ctx.items_dir, "_parts", "%s__%s.json" % (iid, part))


def _signflip_part(ctx, data, item, cB, cT):
    sp = _part(ctx, item["id"], "signflip")
    if os.path.exists(sp):
        return json.loads(open(sp, "rb").read())
    a = item["signflip"]
    r = ctx.call(a["function"], cB, cT, data["y"], data["gi"], eligible_pt=_eligible(ctx), B=a["B"], seed=a["seed"],
                 return_perm=True)
    _save_npy(ctx, _item_paths(ctx, item["id"])[1], r.pop("perm"))
    ctx.w.atomic(sp, _json_bytes(r))
    return json.loads(open(sp, "rb").read())


def _bootstrap_part(ctx, data, item, cB, cT, spec, tag):
    sp = _part(ctx, item["id"], tag)
    if os.path.exists(sp):
        return json.loads(open(sp, "rb").read())
    r = ctx.call(spec["function"], cB, cT, data["y"], data["gi"], eligible_pt=_eligible(ctx), B=spec["B"],
                 seed=spec["seed"], unit=spec["unit"], alpha=spec["alpha"], return_boot=True)
    boot_path = _item_paths(ctx, item["id"])[2] if tag == "bootstrap" else os.path.join(
        ctx.items_dir, "%s.%s.npy" % (item["id"], tag))
    _save_npy(ctx, boot_path, r.pop("boot"))
    ctx.w.atomic(sp, _json_bytes(r))
    return json.loads(open(sp, "rb").read())


def _finite_or_fail(ctx, item, vals):
    if item["status"] == "confirmatory" and not all(v is not None and np.isfinite(v) for v in vals):
        ctx.fail("confirmatory_nonfinite", item["id"])


def h_contrast(ctx, data, item):
    cB = _matrix(ctx, data, item["base"]["path"], item["id"])
    cT = _matrix(ctx, data, item["treat"]["path"], item["id"])
    sf = _signflip_part(ctx, data, item, cB, cT)
    _fault_hit(ctx, "sigterm_mid:" + item["id"])
    bs = _bootstrap_part(ctx, data, item, cB, cT, item["bootstrap"], "bootstrap")
    if sf["delta_obs"] != bs["delta_obs"]:
        ctx.fail("delta_mismatch_signflip_bootstrap", item["id"])
    cp = bs["ci_primary"]
    lo = cp["low"] if cp["low"] is not None else float("nan")
    hi = cp["high"] if cp["high"] is not None else float("nan")
    tost = ctx.call(item["tost"]["function"], lo, hi, bs["delta_obs"], ci_status=cp["status"])
    _finite_or_fail(ctx, item, [sf["delta_obs"], sf["p_two_sided"]])
    return {"delta_obs": sf["delta_obs"], "p_raw": sf["p_two_sided"], "signflip": sf, "bootstrap": bs, "tost": tost}


def h_ci_only(ctx, data, item):
    cB = _matrix(ctx, data, item["base"]["path"], item["id"])
    cT = _matrix(ctx, data, item["treat"]["path"], item["id"])
    bs = _bootstrap_part(ctx, data, item, cB, cT, item["bootstrap"], "bootstrap")
    return {"delta_obs": bs["delta_obs"], "bootstrap": bs}


def h_sealed_p_null(ctx, data, item):
    J = _jload(data, item["source"])
    k = item["keys"]
    pg, pf = float(_get(J, k["p_global"])), float(_get(J, k["p_family"]))
    _finite_or_fail(ctx, item, [pg, pf])
    slot = max(pg, pf)                                    # G2
    return {"p_emp_global": pg, "p_emp_family": pf, "p_slot": slot, "slot_rule": item["slot_rule"],
            "T_obs": _get(J, k["T_obs"]), "T_obs_basis": item["T_obs_basis"]}


def h_sealed_p_holm8(ctx, data, item):
    J = _jload(data, item["source"])
    k = item["keys"]
    out = {name: _get(J, path) for name, path in k.items()}
    _finite_or_fail(ctx, item, [float(out["p_primary"])])
    out["p_slot"] = float(out["p_primary"])
    return out


def h_pt_tests(ctx, data, item):
    cB = _matrix(ctx, data, item["base"]["path"], item["id"])
    cT = _matrix(ctx, data, item["treat"]["path"], item["id"])
    el = ctx.call(item["eligibility"]["function"], data["y"], data["gi"])
    cols = list(el["eligible_pt"])
    ck = _part(ctx, item["id"], "pt_checkpoint")
    done = json.loads(open(ck, "rb").read())["per_pt"] if os.path.exists(ck) else {}
    a = item["signflip"]
    every = item["checkpoint_every_pt"]
    n_new = 0
    for j in cols:
        lab = data["ycols"][j]
        if lab in done:
            continue
        r = ctx.call(a["function"], cB, cT, data["y"], data["gi"], eligible_pt=np.array([j]), B=a["B"],
                     seed=a["seed"])
        done[lab] = {"col": int(j), "delta_obs": r["delta_obs"], "p_two_sided": r["p_two_sided"]}
        n_new += 1
        if n_new % every == 0:
            ctx.w.atomic(ck, _json_bytes({"per_pt": done}))
            ctx.heartbeat("pt_checkpoint", item["id"])
            _fault_hit(ctx, "sigterm_pt:" + item["id"])
    ctx.w.atomic(ck, _json_bytes({"per_pt": done}))
    bh = ctx.call(item["bh"]["function"], {lab: done[lab]["p_two_sided"] for lab in sorted(done)}, q=item["bh"]["q"])
    return {"n_eligible": el["n_eligible"], "eligibility_rule": el["rule"], "per_pt": done, "bh": bh}


def h_baseline_ap(ctx, data, item):
    out = {}
    el = _eligible(ctx)
    for name, rel in item["matrices"].items():
        out[name] = ctx.call(item["metric"], data["y"], _matrix(ctx, data, rel, item["id"]), el)
        out[name].pop("defined_mask", None)
    if item.get("prevalence_baseline"):
        prev = data["y"].mean(axis=0)
        P = np.tile(prev, (data["y"].shape[0], 1))
        r = ctx.call(item["metric"], data["y"], P, el)
        r.pop("defined_mask", None)
        out["label_prevalence_baseline"] = r
    return out


def h_gin(ctx, data, item):
    G = _jload(data, item["gin_metrics"])
    H = _jload(data, item["holm8"])
    D9 = _jload(data, item["d9"])
    k = item["keys"]
    c3 = _get(G, k["cell_3_delta_gin"])
    if c3 != _get(H, k["holm8_delta_gin"]):
        ctx.fail("g1_cell3_vs_holm8_delta_gin", item["id"])
    out = {"cell_2_delta_gin_per_seed": _get(G, k["cell_2_delta_gin_per_seed"]), "cell_3_delta_gin": c3,
           "d9_gin_composite": _get(D9, k["d9_gin_composite"])}
    c1 = _get(G, k["cell_1"])
    fmt, seeds = item["cell_1_key_format"], item["seeds"]
    dirs = {}
    for name, gc in item["gin_contrasts"].items():
        per = [_get(c1, [fmt.format(model=gc["treat"], t=t)] + k["cell_1_value_path"])
               - _get(c1, [fmt.format(model=gc["base"], t=t)] + k["cell_1_value_path"]) for t in seeds]
        dirs[name] = {"per_seed": per, "seed_mean": float(np.mean(per)), "rf_item": gc["rf_item"]}
    out["gin_directional_contrasts"] = dirs
    return out


def _sub_metrics(y, P, spec):
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
    K = y.shape[1]
    pos = y.sum(0)
    prev = y.mean(0)
    ap = np.array([average_precision_score(y[:, j], P[:, j]) if pos[j] > 0 else np.nan for j in range(K)])
    out = {}
    for n in spec["n_threshold_subsets"]:
        m = pos >= n
        out["macro_ap_N%d" % n] = float(np.nanmean(ap[m])) if m.any() else None
        out["n_pt_N%d" % n] = int(m.sum())
    for name, why in spec["not_computable"].items():
        out[name] = {"status": "not_computable", "reason": why}
    q = np.quantile(prev, spec["prevalence_bin_quantiles"])
    bins = np.digitize(prev, q, right=True)              # 경계 PT 는 하위 bin
    out["prevalence_bin_macro_ap"] = {"bin%d" % b: float(np.nanmean(ap[bins == b])) for b in range(len(q) + 1)}
    out["prevalence_bin_n_pt"] = {"bin%d" % b: int((bins == b).sum()) for b in range(len(q) + 1)}
    w = pos.astype(float)
    out["label_weighted_macro_ap"] = float(np.nansum(ap * w) / w[~np.isnan(ap)].sum())
    out["micro_ap"] = float(average_precision_score(y.ravel(), P.ravel()))
    out["prevalence_normalized_lift"] = float(np.nanmean(ap / prev))
    k = spec["budget_k"]
    top = np.argsort(-P, axis=0, kind="stable")[:k]
    hits = np.array([y[top[:, j], j].sum() for j in range(K)], dtype=float)
    out["precision_at_k"] = float(np.mean(hits / k))
    out["recall_at_k"] = float(np.mean(hits[pos > 0] / pos[pos > 0]))
    out["budget_k"] = int(k)
    out["brier_macro"] = float(np.mean([brier_score_loss(y[:, j], P[:, j]) for j in range(K)]))
    ok = [(j) for j in range(K) if 0 < pos[j] < y.shape[0]]
    out["roc_auc_macro"] = float(np.mean([roc_auc_score(y[:, j], P[:, j]) for j in ok]))
    out["roc_auc_n_pt"] = len(ok)
    return out


def h_sub_metrics(ctx, data, item):
    cB = _matrix(ctx, data, item["base"]["path"], item["id"])
    cT = _matrix(ctx, data, item["treat"]["path"], item["id"])
    mb, mt = _sub_metrics(data["y"], cB, item["spec"]), _sub_metrics(data["y"], cT, item["spec"])
    dl = {}
    for k, v in mt.items():
        if isinstance(v, float) and isinstance(mb.get(k), float):
            dl[k] = v - mb[k]
        elif isinstance(v, dict) and all(isinstance(x, float) for x in v.values()) and isinstance(mb.get(k), dict):
            dl[k] = {kk: v[kk] - mb[k][kk] for kk in v}
    return {"base": mb, "treat": mt, "delta_treat_minus_base": dl, "descriptive_only": True}


def h_sealed_publish(ctx, data, item):
    out = {"files": {}}
    for rel, paths in item["extract"].items():
        J = _jload(data, rel) if rel.endswith(".json") else None
        out["files"][rel] = {"sha256": sha256_bytes(data["blobs"][rel]),
                             "extracted": {"/".join(map(str, p)): _get(J, p) for p in paths} if J is not None else {}}
    return out


def _hist(vals, bins, lo, hi):
    c, e = np.histogram(np.asarray(vals, dtype=float), bins=bins, range=(lo, hi))
    return c.tolist(), e.tolist()


def h_figure(ctx, data, item):
    spec = item["figure"]
    if spec["type"] == "d13_tstar":
        T = np.load(io.BytesIO(data["blobs"][spec["t_star"]]), allow_pickle=False)
        H = _jload(data, spec["holm8"])
        m = float(np.max(np.abs(T)))
        c, e = _hist(T, spec["bins"], -m, m)
        panels = {"t_star": {"counts": c, "edges": e, "observed": _get(H, spec["observed_key"]), "n": int(T.size)}}
    else:
        rows = [json.loads(ln) for ln in data["blobs"][spec["checkpoint"]].decode("utf-8").splitlines() if ln.strip()]
        J = _jload(data, spec["null_result"])
        panels = {}
        for kind, val in spec["kind_values"].items():
            v = [r[spec["value_field"]] for r in rows if r.get(spec["filter_field"]) is True
                 and r.get(spec["kind_field"]) == val]
            if not v:
                ctx.fail("figure_no_rows", item["id"], spec["checkpoint"])
            c, e = _hist(v, spec["bins"], float(min(v)), float(max(v)))
            panels[kind] = {"counts": c, "edges": e, "observed": _get(J, spec["observed_key"]), "n": len(v)}
    return {"figure": spec["type"], "panels": panels, "dpi": spec["dpi"]}


def h_reporting(ctx, data, item):
    RT = ctx.plan["reporting_text"]
    return {"inserted_keys": [k for k in item["text_keys"] if k in RT], "references": item["references"]}


HANDLERS = {"reporting": h_reporting, "contrast": h_contrast, "ci_only": h_ci_only, "sealed_p_null": h_sealed_p_null,
            "sealed_p_holm8": h_sealed_p_holm8, "pt_tests": h_pt_tests, "baseline_ap": h_baseline_ap,
            "gin": h_gin, "sub_metrics": h_sub_metrics, "sealed_publish": h_sealed_publish, "figure": h_figure}


def _item_result(ctx, iid):
    return json.loads(open(_item_paths(ctx, iid)[0], "rb").read())


def r4_decisions(ctx):
    P = ctx.plan
    res = {i["id"]: _item_result(ctx, i["id"]) for i in P["items"]}
    HP = P["holm"]
    panels = {}
    for pname, pspec in HP["panels"].items():
        pv = {}
        for lab, src in pspec["slots"].items():
            pv[lab] = src["fixed_value"] if "fixed_value" in src else float(_get(res[src["item"]], src["field"]))
        panels[pname] = ctx.call(HP["function"], pv, alpha=HP["alpha"])
        if any(panels[pname]["undefined_filled"].values()):
            ctx.fail("holm_undefined_fill_triggered", pname)
    p1, p2 = panels[HP["adjudication_panel"]], panels[HP["comparison_panel"]]
    d14 = {lab: p1["reject"][lab] != p2["reject"][lab] for lab in p1["reject"] if lab != HP["d14_excluded_label"]}
    adj = p1["adjusted_p"]
    DE = P["decisions"]
    out = {"holm": panels, "d14_conclusion_differs": d14, "d14_any_difference": any(d14.values())}
    r2 = DE["RQ2"]
    c = res[r2["item"]]
    out["RQ2"] = ctx.call(r2["function"], c["bootstrap"]["ci_primary"], c["p_raw"], c["delta_obs"])
    r3 = DE["RQ3"]
    a, b = res[r3["items"][0]], res[r3["items"][1]]
    out["RQ3"] = ctx.call(r3["function"], a["bootstrap"]["ci_primary"], adj[r3["holm_labels"][0]],
                          b["bootstrap"]["ci_primary"], adj[r3["holm_labels"][1]])
    out["RQ3"]["p_raw"] = {r3["holm_labels"][0]: a["p_raw"], r3["holm_labels"][1]: b["p_raw"]}
    r4 = DE["RQ4"]
    pa = adj[r4["holm_label"]]
    out["RQ4"] = ctx.call(r4["function"], pa, pa)
    n = res[r4["item"]]
    out["RQ4"]["p_raw"] = {"p_emp_global": n["p_emp_global"], "p_emp_family": n["p_emp_family"], "p_slot": n["p_slot"]}
    ri = DE["RQ_int"]
    out["RQ_int"] = {"adjusted_p": adj[ri["holm_label"]], "alpha": HP["alpha"],
                     "success": bool(adj[ri["holm_label"]] < HP["alpha"]), "rule": ri["rule"],
                     "p_raw": res[ri["item"]]["p_slot"]}
    cc = DE["C_CAP"]
    k = res[cc["item"]]
    out["C_CAP"] = ctx.call(cc["function"], k["bootstrap"]["ci_primary"], k["p_raw"])
    out["minimum_establishment"] = {
        "success": bool(out["RQ2"]["success"] and (out["RQ3"]["success"] or out["C_CAP"]["pass"])
                        and out["RQ4"]["success"]),
        "rule": DE["minimum_establishment_rule"]}
    out["tost"] = {i["id"]: res[i["id"]]["tost"]["label"] for i in P["items"] if "tost" in res[i["id"]]}
    out["gin_direction_agrees"] = None
    g = [i for i in P["items"] if i["kind"] == "gin"]
    if g:
        gr = res[g[0]["id"]]
        out["gin_direction_agrees"] = bool(np.sign(gr["cell_3_delta_gin"]) == np.sign(res[r2["item"]]["delta_obs"]))
        out["gin_directional_vs_rf"] = {nm: bool(np.sign(v["seed_mean"]) == np.sign(res[v["rf_item"]]["delta_obs"]))
                                        for nm, v in gr["gin_directional_contrasts"].items()}
    return res, out


def r5_completeness(ctx, res, dec):
    P = ctx.plan
    ids = [i["id"] for i in P["items"]]
    if len(set(ids)) != len(ids) or set(res) != set(ids):
        ctx.fail("completeness_items")
    for i in P["items"]:
        r = res[i["id"]]
        if i["status"] == "confirmatory" and i["kind"] == "contrast":
            if not all(np.isfinite(v) for v in (r["delta_obs"], r["p_raw"])):
                ctx.fail("confirmatory_nonfinite", i["id"])
    G1 = P["g1_bit_equality"]
    c1 = res[G1["item"]]
    H = json.loads(ctx_blob(ctx, G1["holm8"]))
    if c1["delta_obs"] != _get(H, G1["holm8_delta_key"]):
        ctx.fail("g1_delta_rf", G1["item"])
    D9 = json.loads(ctx_blob(ctx, G1["d9"]))
    ref = _get(D9, G1["d9_rf_key"])
    for key in G1["bootstrap_keys"]:
        if _json_safe(c1["bootstrap"][key]) != ref[key]:
            ctx.fail("g1_d9_" + key, G1["item"])
    if set(dec["holm"][P["holm"]["adjudication_panel"]]["raw_p"]) != set(sd.HOLM_FAMILY):
        ctx.fail("holm_family_labels")


def ctx_blob(ctx, rel):
    return ctx._data["blobs"][rel].decode("utf-8")


def r6_independent(ctx):
    P = ctx.plan
    chk = os.path.join(ctx.root, P["independent_check"]["script_path"])
    plan_path = ctx.hooks.get("plan_path", os.path.join(ctx.root, PLAN_REL))
    cmd = [sys.executable, "-B", chk, "--stage", "check", "--root", ctx.root, "--plan", plan_path,
           "--staging", ctx.staging]
    r = subprocess.run(cmd, capture_output=True, text=True)
    op = os.path.join(ctx.staging, P["independent_check"]["output_file"])
    if r.returncode != 0 or not os.path.exists(op):
        ctx.fail("independent_check_error")
    o = json.loads(open(op, "rb").read())
    if o.get("all_match") is not True:
        ctx.fail("independent_check_mismatch", ",".join(o.get("mismatch_items", [])))
    return o


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _tables(P, res, dec):
    t = {}
    adj1 = dec["holm"][P["holm"]["adjudication_panel"]]["adjusted_p"]
    adj2 = dec["holm"][P["holm"]["comparison_panel"]]["adjusted_p"]
    head = ["id", "slot", "label", "status", "delta_obs", "ci_low", "ci_high", "ci_status", "p_raw", "p_adj_panel1",
            "p_adj_panel2", "decision", "tost", "base", "treat"]
    rows = []
    for i in P["items"]:
        r = res[i["id"]]
        if i["kind"] not in ("contrast", "ci_only", "sealed_p_null", "sealed_p_holm8"):
            continue
        cp = (r.get("bootstrap") or {}).get("ci_primary") or {}
        hl = i.get("holm_label")
        rows.append([i["id"], i.get("slot", ""), i["label"], i["status"], r.get("delta_obs", ""), cp.get("low"),
                     cp.get("high"), cp.get("status", ""), r.get("p_raw", r.get("p_slot")),
                     adj1.get(hl) if hl else None, adj2.get(hl) if hl else None, i.get("decision_ref", ""),
                     (r.get("tost") or {}).get("label", ""), (i.get("base") or {}).get("arm", ""),
                     (i.get("treat") or {}).get("arm", "")])
    t["main"] = (head, rows)
    pt = [i for i in P["items"] if i["kind"] == "pt_tests"]
    if pt:
        r = res[pt[0]["id"]]
        t["pt_bh"] = (["pt", "col", "delta_obs", "p_raw", "q_bh", "reject"],
                      [[k, v["col"], v["delta_obs"], v["p_two_sided"], r["bh"]["adjusted_p"][k], r["bh"]["reject"][k]]
                       for k, v in sorted(r["per_pt"].items())])
    return t


def _render_md(head, rows):
    s = "| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n"
    for r in rows:
        s += "| " + " | ".join(_fmt(v) for v in r) + " |\n"
    return s


def _png(spec_item, fig, path_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(fig["panels"])
    f, axs = plt.subplots(1, n, figsize=(6 * n, 4), dpi=fig["dpi"])
    axs = np.atleast_1d(axs)
    for ax, (name, p) in zip(axs, sorted(fig["panels"].items())):
        e = np.asarray(p["edges"])
        ax.stairs(p["counts"], e, fill=True, alpha=0.6)
        ax.axvline(float(p["observed"]), color="k", linestyle="--", linewidth=1.2)
        ax.set_title(name)
        ax.set_xlabel(spec_item["figure"]["x_label"])
        ax.set_ylabel("count")
    f.tight_layout()
    buf = io.BytesIO()
    f.savefig(buf, format="png", dpi=fig["dpi"], metadata={"Software": None})
    plt.close(f)
    return buf.getvalue()


def r7_publish(ctx, res, dec, chk):
    P = ctx.plan
    O = P["outputs"]
    build = os.path.join(ctx.staging, "_results_build")
    if os.path.exists(build):
        shutil.rmtree(ctx.w.check(build))
    files = {}

    def put(name, data):
        ctx.w.atomic(os.path.join(build, name), data)
        files[name] = sha256_bytes(data)

    full = {"plan_sha256": ctx.expected["plan_sha256"], "items": res, "decisions": dec,
            "independent_check": {"all_match": chk["all_match"]}, "estimand": P["reporting_text"]["estimand_verbatim"]}
    put("results_full.json", _json_bytes(full))
    for name, (head, rows) in _tables(P, res, dec).items():
        put("table_%s.md" % name, _render_md(head, rows).encode("utf-8"))
        sio = io.StringIO()
        wr = csv.writer(sio, lineterminator="\n")
        wr.writerow(head)
        for r in rows:
            wr.writerow([_fmt(v) for v in r])
        put("table_%s.csv" % name, sio.getvalue().encode("utf-8"))
    for i in P["items"]:
        if i["kind"] == "figure":
            put(i["figure"]["output_stem"] + ".json", _json_bytes(res[i["id"]]))
            put(i["figure"]["output_stem"] + ".png", _png(i, res[i["id"]], None))
        if i["kind"] == "sealed_publish":
            for rel in i["extract"]:
                put("sealed_publish/" + rel.replace("/", "__"), ctx._data["blobs"][rel])
    RT = P["reporting_text"]
    txt = "# 개봉 결과 보고 문면 (계획 `%s` · sha256 %s)\n\n" % (PLAN_REL, ctx.expected["plan_sha256"])
    for k in RT["insertion_order"]:
        txt += "## %s\n\n%s\n\n" % (k, RT[k] if isinstance(RT[k], str) else json.dumps(RT[k], ensure_ascii=False,
                                                                                       indent=1))
    txt += "## 결과 표\n\n" + _render_md(*_tables(P, res, dec)["main"])
    put("reporting_text.md", txt.encode("utf-8"))
    mp = {"plan_sha256": ctx.expected["plan_sha256"], "published_at_kst": now_kst(),
          "files": {k: files[k] for k in sorted(files)}}
    ctx.w.atomic(os.path.join(build, "manifest_public.json"), _json_bytes(mp))
    _fault_hit(ctx, "crash_before_publish_move")
    dest = os.path.join(ctx.out_root, O["results_dir"])
    os.replace(ctx.w.check(build), ctx.w.check(dest))
    msha = sha256_file(os.path.join(dest, "manifest_public.json"))
    ev = {"ts_kst": now_kst(), "type": "unblinding_publish", "approval_ref": ctx.expected["approval_sha256"],
          "plan_sha256": ctx.expected["plan_sha256"], "manifest_public_sha256": msha, "files": mp["files"]}
    ctx.w.atomic(os.path.join(ctx.root, O["event_path"]), _json_bytes(ev))
    for t in P["read_scope"]["trees"]:
        ctx.w.append_line(os.path.join(ctx.root, t, "_sealed", "access.log"),
                          {"ts_kst": now_kst(), "type": "unblinding_publish", "purpose": "unblinding",
                           "approval_ref": ctx.expected["approval_sha256"], "human_exposure": True,
                           "event_ref": O["event_path"], "actor": "vscode-claude"})
    ctx.w.append_line(os.path.join(ctx.out_root, O["launches_file"]),
                      {"ts_kst": now_kst(), "event": "published", "r7_trees": list(P["read_scope"]["trees"])})
    return msha


def core(root, plan, expected, out_root, fault=None, hooks=None):
    """R1~R7. plan = 계획 dict(run = 동결본 · selftest = B 축소 합성본). expected = 기대 sha·승인 ref."""
    ctx = Ctx(root, plan, expected, out_root, fault, hooks)
    O = plan["outputs"]
    if os.path.exists(os.path.join(ctx.staging, O["failure_file"])):
        raise IntegrityFailure("prior_failure")
    if os.path.exists(os.path.join(out_root, O["results_dir"])):
        return {"already_published": True}
    os.makedirs(ctx.w.check(ctx.items_dir), exist_ok=True)
    launches = [json.loads(ln) for ln in open(os.path.join(out_root, O["launches_file"]), encoding="utf-8")
                if ln.strip()] if os.path.exists(os.path.join(out_root, O["launches_file"])) else []
    n_launch = 1 + sum(1 for e in launches if e.get("event") == "launch")
    if n_launch > 1 + plan["long_run"]["max_restarts"]:
        raise GateRefused("restart_limit")
    # R1 판독 기록 (launch 마다 1줄 · machine_read · human_exposure false)
    trees = list(plan["read_scope"]["trees"])
    for t in trees:
        ctx.w.append_line(os.path.join(root, t, "_sealed", "access.log"),
                          {"ts_kst": now_kst(), "type": "machine_read", "purpose": "unblinding",
                           "approval_ref": expected["approval_sha256"], "human_exposure": False,
                           "step": "블록 120 R1 · launch %d" % n_launch, "actor": "vscode-claude",
                           "note": "개봉 스크립트·독립 검산기 판독 범위 합집합. 값 공개 0(R7 이전)."})
    ctx.w.append_line(os.path.join(out_root, O["launches_file"]),
                      {"ts_kst": now_kst(), "event": "launch", "launch": n_launch, "r1_trees": trees})
    ctx.heartbeat("r1_done")
    _fault_hit(ctx, "crash_after_r1")
    # R2 입력
    data = _load_inputs(ctx)
    ctx._data = data
    dz = {"n_rows": int(data["y"].shape[0]), "n_pt": int(data["y"].shape[1]),
          "n_groups": int(len(np.unique(data["gi"]))), "ycols_sha256": sha256_bytes("\n".join(data["ycols"]).encode())}
    ctx.w.atomic(os.path.join(ctx.staging, O["design_file"]), _json_bytes(dz))
    _save_npy_int(ctx, os.path.join(ctx.staging, O["design_groups_file"]), data["gi"])
    ctx.heartbeat("r2_done")
    # R3 항목
    for item in plan["items"]:
        jp = _item_paths(ctx, item["id"])[0]
        if os.path.exists(jp):
            continue
        if not ctx.power():
            ctx.heartbeat("power_lost", item["id"])
            raise PowerLoss()
        ctx.heartbeat("item_start", item["id"])
        try:
            r = HANDLERS[item["kind"]](ctx, data, item)
        except (KeyError, TypeError, IndexError):
            ctx.fail("key_missing", item["id"])
        r["id"], r["kind"], r["status"] = item["id"], item["kind"], item["status"]
        ctx.w.atomic(jp, _json_bytes(r))
        ctx.heartbeat("item_done", item["id"])
        _fault_hit(ctx, "crash_after_item:" + item["id"])
    # R4 판정 · R5 완전성
    res, dec = r4_decisions(ctx)
    ctx.w.atomic(os.path.join(ctx.staging, O["decisions_file"]), _json_bytes(dec))
    r5_completeness(ctx, res, dec)
    ctx.heartbeat("r5_done")
    # R6 독립 검산 · R7 공개
    chk = r6_independent(ctx)
    ctx.heartbeat("r6_done")
    msha = r7_publish(ctx, res, dec, chk)
    ctx.heartbeat("r7_done")
    return {"published": True, "manifest_public_sha256": msha, "n_items": len(res), "launch": n_launch}


def _save_npy_int(ctx, path, arr):
    buf = io.BytesIO()
    np.save(buf, np.asarray(arr, dtype=np.int64), allow_pickle=False)
    ctx.w.atomic(path, buf.getvalue())


# ═══════════════════════════════════════════════════════════════════════════
# stage run / status
# ═══════════════════════════════════════════════════════════════════════════
def power_status(min_w):
    try:
        ps = subprocess.run(["pmset", "-g", "ps"], capture_output=True, text=True, timeout=30).stdout
        ad = subprocess.run(["pmset", "-g", "adapter"], capture_output=True, text=True, timeout=30).stdout
    except Exception:            # noqa: BLE001
        return False
    m = re.search(r"Wattage\s*=\s*(\d+)", ad)
    return bool("AC Power" in ps and m is not None and int(m.group(1)) >= min_w)


def load_plan(root):
    b = open(os.path.join(root, PLAN_REL), "rb").read()
    if sha256_bytes(b) != PLAN_SHA256:
        raise GateRefused("plan_sha_mismatch")
    return json.loads(b.decode("utf-8"))


def stage_run():
    plan = load_plan(ROOT)
    LR = plan["long_run"]
    st = json.loads(open(os.path.join(ROOT, plan["freeze"]["selftest_run_path"]), "rb").read())
    me = sha256_file(os.path.abspath(__file__))
    if not (st.get("all_pass") is True and st.get("script_sha256") == me and st.get("plan_sha256") == PLAN_SHA256
            and st.get("watchdog_sha256") == sha256_file(os.path.join(ROOT, LR["watchdog_path"]))
            and st.get("checker_sha256") == sha256_file(os.path.join(ROOT, plan["independent_check"]["script_path"]))):
        raise GateRefused("selftest_binding")
    O = plan["outputs"]
    if os.path.exists(os.path.join(ROOT, O["root"], O["results_dir"])):
        print(json.dumps({"stage": "run", "already_published": True}), flush=True)
        return EXIT_OK
    ll = launch_lines(ROOT, plan)
    fails = gate(ROOT, {"plan": plan, "launch_lines": ll})
    if fails:
        raise GateRefused(" · ".join(fails))
    if not power_status(LR["adapter_min_w"]):
        return EXIT_POWER
    import compute_lock as cl                        # 실행 인프라(동결 대상 아님) — run 전용
    cl.gate_a_load("unblinding run entry")
    AU = json.loads(open(os.path.join(ROOT, plan["expected_hash_source"]["audit_path"]), "rb").read())
    ap = os.path.join(ROOT, plan["approval_binding"]["record_path"])
    expected = {"sealed_sha256": AU["sealed_sha256"], "labels_sha256": {k: v["sha256"] for k, v in
                                                                        plan["labels"].items() if isinstance(v, dict)},
                "approval_sha256": sha256_file(ap), "plan_sha256": PLAN_SHA256}

    def _term(signum, _f):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _term)
    with cl.ComputeLock(script="unblinding_run.py", role="runner"):
        r = core(ROOT, plan, expected, os.path.join(ROOT, plan["outputs"]["root"]),
                 hooks={"power": lambda: power_status(LR["adapter_min_w"]), "load1": lambda: os.getloadavg()[0]})
    print(json.dumps({"stage": "run", "published": bool(r.get("published") or r.get("already_published"))}),
          flush=True)
    return EXIT_OK


def stage_status(root=ROOT, plan=None):
    plan = plan or json.loads(open(os.path.join(root, PLAN_REL), "rb").read())
    O = plan["outputs"]
    o = os.path.join(root, O["root"])
    st = {"output_exists": os.path.exists(o)}
    if st["output_exists"]:
        idir = os.path.join(o, O["staging_dir"], O["items_subdir"])
        done = sorted(f[:-5] for f in os.listdir(idir) if f.endswith(".json")) if os.path.isdir(idir) else []
        st["items_done"] = done
        st["n_items_done"] = len(done)
        st["n_items_plan"] = len(plan["items"])
        fp = os.path.join(o, O["staging_dir"], O["failure_file"])
        if os.path.exists(fp):
            F = json.loads(open(fp, "rb").read())
            st["failure"] = {"code": F["code"], "item": F["item"], "file": F["file"]}
        st["results_published"] = os.path.exists(os.path.join(o, O["results_dir"]))
        lp = os.path.join(o, O["launches_file"])
        st["n_launch"] = sum(1 for ln in open(lp, encoding="utf-8") if '"event": "launch"' in ln) if os.path.exists(
            lp) else 0
    return st


# ═══════════════════════════════════════════════════════════════════════════
# selftest — 합성 저장소 · 축소 계획 · U1~U16
# ═══════════════════════════════════════════════════════════════════════════
_RINGS = ["c1ccccc1", "c1ccncc1", "C1CCCCC1", "c1ccc2ccccc2c1", "c1ccoc1", "C1CCNCC1", "c1ccsc1", "C1CCOC1",
          "c1cncnc1", "C1CCCC1", "c1ccc2[nH]ccc2c1", "O=C1CCCCN1"]
_CHAINS = ["C", "CC", "CCC", "O", "N", "CO", "CN", "OC", "C(C)C", "CCO"]


def _fx_smiles():
    smi = [ch + r for r in _RINGS for ch in _CHAINS]
    smi += ["CCCC", "CCCCO", "CCN(C)C", "CC(=O)O", "OCCO", "CCCCCC"]
    return smi


def selftest_plan(plan, n_rows, n_pt, n_groups, B):
    """동결 계획과 같은 스키마 · B 와 설계 크기만 바꾼 합성 계획(항목·인자 구조 동일)."""
    p = copy.deepcopy(plan)
    p["design"].update({"n_rows": n_rows, "n_pt": n_pt, "n_groups": n_groups})
    for it in p["items"]:
        for k in ("signflip", "bootstrap"):
            if k in it:
                it[k]["B"] = B
        if it["kind"] == "pt_tests":
            it["checkpoint_every_pt"] = 2
        if it["kind"] == "sub_metrics":
            it["spec"]["n_threshold_subsets"] = [3]
            it["spec"]["budget_k"] = 5
    p["_selftest_reduced"] = True
    return p


def _nested_set(d, path, v):
    for k in path[:-1]:
        if not isinstance(d.get(k), dict):
            d[k] = {}
        d = d[k]
    d[path[-1]] = v


def build_fixture(base, plan_real, B=60, seed=20261004):
    """합성 저장소 — 실저장소와 같은 상대 경로. 반환 (root, synthetic_plan, expected, plan_path)."""
    rng = np.random.default_rng(seed)
    root = os.path.join(base, "repo")
    smi = _fx_smiles()
    n = len(smi)
    groups = [scaffold_of(s) for s in smi]
    G = len(set(groups))
    K = 6
    cid = np.arange(1000, 1000 + n, dtype=np.int64)
    y = np.zeros((n, K), dtype=np.int8)
    gu = sorted(set(groups))
    gid = np.array([gu.index(g) for g in groups])
    for j in range(K):
        p = 0.12 + 0.05 * j
        y[:, j] = (rng.random(n) < p).astype(np.int8)
        y[np.where(gid == (j % G))[0][:2], j] = 1
    plan = selftest_plan(plan_real, n, K, G, B)

    def wb(rel, data):
        pth = os.path.join(root, rel)
        os.makedirs(os.path.dirname(pth), exist_ok=True)
        with open(pth, "wb") as f:
            f.write(data)

    lab = plan["labels"]
    bx = io.BytesIO()
    pd.DataFrame({"cid": cid, lab["smiles_column"]: smi}).to_parquet(bx)
    by = io.BytesIO()
    Yd = pd.DataFrame(y, columns=["%08d" % (10000000 + j) for j in range(K)])
    Yd.insert(0, "cid", cid)
    Yd.to_parquet(by)
    wb(lab["master_x"]["path"], bx.getvalue())
    wb(lab["master_y"]["path"], by.getvalue())
    NZ = plan["npz_schema"]
    mats = {}
    base_sig = rng.normal(size=(n, K))
    for rel in plan["read_scope"]["files"]:
        if rel.endswith(".npz"):
            noise = rng.normal(scale=0.8, size=(n, K))
            M = 1 / (1 + np.exp(-(base_sig + 1.2 * y + noise)))
            mats[rel] = M
            buf = io.BytesIO()
            np.savez(buf, **{NZ["matrix_key"]: M, NZ["cid_key"]: cid})
            wb(rel, buf.getvalue())
    yi = y.astype(int)
    gi = np.array([gu.index(g) for g in groups], dtype=int)
    G1 = plan["g1_bit_equality"]
    c1 = [i for i in plan["items"] if i["id"] == G1["item"]][0]
    MB, MT = mats[c1["base"]["path"]], mats[c1["treat"]["path"]]
    el = np.arange(K)
    d_rf = sm.macro_ap(yi, MT, el)["macro_ap"] - sm.macro_ap(yi, MB, el)["macro_ap"]
    bspec = c1["bootstrap"]
    rf = sb.paired_scaffold_bootstrap(MB, MT, yi, gi, eligible_pt=el, B=bspec["B"], seed=bspec["seed"],
                                      unit=bspec["unit"], alpha=bspec["alpha"])
    jsons = {}
    for it in plan["items"]:
        if it["kind"] == "sealed_publish":
            for rel, paths in it["extract"].items():
                if rel.endswith(".json"):
                    d = jsons.setdefault(rel, {})
                    for pth in paths:
                        _nested_set(d, pth, float(rng.random()))
    gk = [i for i in plan["items"] if i["kind"] == "gin"][0]
    hk = [i for i in plan["items"] if i["kind"] == "sealed_p_holm8"][0]
    nk = [i for i in plan["items"] if i["kind"] == "sealed_p_null"][0]
    d_gin = float(rng.normal(scale=0.01))
    H = jsons.setdefault(hk["source"], {})
    for name, pth in hk["keys"].items():
        _nested_set(H, pth, float(rng.random() * 0.02))
    Bh = 1000
    c = 7
    _nested_set(H, hk["keys"]["B"], Bh)
    _nested_set(H, hk["keys"]["c_abs_ge_obs_first_B"], c)
    _nested_set(H, hk["keys"]["p_primary"], (1.0 + c) / (Bh + 1.0))
    _nested_set(H, G1["holm8_delta_key"], d_rf)
    _nested_set(H, gk["keys"]["holm8_delta_gin"], d_gin)
    D9 = jsons.setdefault(G1["d9"], {})
    _nested_set(D9, G1["d9_rf_key"], _json_safe(rf))
    _nested_set(D9, gk["keys"]["d9_gin_composite"] + ["ci_primary"], {"low": -0.01, "high": 0.02})
    GM = jsons.setdefault(gk["gin_metrics"], {})
    _nested_set(GM, gk["keys"]["cell_3_delta_gin"], d_gin)
    _nested_set(GM, gk["keys"]["cell_2_delta_gin_per_seed"], {str(t): d_gin for t in gk["seeds"]})
    models = sorted({gc[x] for gc in gk["gin_contrasts"].values() for x in ("base", "treat")})
    for m in models:
        for t in gk["seeds"]:
            _nested_set(GM, gk["keys"]["cell_1"] + [gk["cell_1_key_format"].format(model=m, t=t)]
                        + gk["keys"]["cell_1_value_path"], float(0.15 + 0.01 * rng.random()))
    NR = jsons.setdefault(nk["source"], {})
    _nested_set(NR, nk["keys"]["p_global"], 0.0297)
    _nested_set(NR, nk["keys"]["p_family"], 0.0396)
    _nested_set(NR, nk["keys"]["T_obs"], 0.18)
    for rel, d in jsons.items():
        wb(rel, (json.dumps(d, indent=2) + "\n").encode("utf-8"))
    for it in plan["items"]:
        if it["kind"] != "figure":
            continue
        fs = it["figure"]
        if fs["type"] == "d13_tstar":
            buf = io.BytesIO()
            np.save(buf, rng.normal(scale=0.01, size=2000), allow_pickle=False)
            wb(fs["t_star"], buf.getvalue())
        else:
            rows = []
            for kind, val in fs["kind_values"].items():
                for r_ in range(120):
                    rows.append({fs["kind_field"]: val, fs["filter_field"]: r_ < 100, fs["value_field"]:
                                 float(0.15 + 0.01 * rng.normal())})
            wb(fs["checkpoint"], "".join(json.dumps(r_) + "\n" for r_ in rows).encode("utf-8"))
    for rel in plan["read_scope"]["files"]:
        if not os.path.exists(os.path.join(root, rel)):
            wb(rel, b"{}\n")
    # 봉인 트리 access.log (read_scope 중 일부 트리는 부재 — 실저장소처럼)
    for t in plan["read_scope"]["trees"]:
        if t not in plan["read_scope"]["trees_without_access_log_at_118"]:
            wb(t + "/_sealed/access.log", (json.dumps({"type": "machine_read", "actor": "fixture"}) + "\n").encode())
    fl = plan["flags"]
    for rel in fl["gin_start_still_blocked_true"]:
        wb(rel, json.dumps({"gin_start_still_blocked": True}).encode())
    for rel in fl["unblinding_performed_false"]:
        wb(rel, json.dumps({"unblinding_performed": False}).encode())
    plan_path = os.path.join(root, PLAN_REL)
    wb(PLAN_REL, (json.dumps(plan, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    for rel in plan["approval_binding"]["approved_hashes_paths"]:
        src = os.path.join(ROOT, rel)
        if rel in (PLAN_REL, plan["expected_hash_source"]["audit_path"]):
            continue
        if rel.endswith(".py") and os.path.exists(src):
            wb(rel, open(src, "rb").read())
        else:
            wb(rel, ("# fixture " + rel + "\n").encode())
    exp_sha = {rel: sha256_file(os.path.join(root, rel)) for rel in plan["read_scope"]["files"]}
    counts, fps, acc = stat_summary(root, plan["stat_groups"])
    AU = {"audit_version": "v3", "verdict": "PASS", "audited_at_kst": now_kst(), "sealed_sha256": exp_sha,
          "sealed_counts": counts, "stat_fingerprints": fps, "access_log_lines": acc,
          "frozen_118_sha256": {}, "report_path": plan["expected_hash_source"]["report_path"]}
    wb(plan["expected_hash_source"]["audit_path"], _json_bytes(AU))
    ab = plan["approval_binding"]
    A = {"approver": ab["approver"], "approved_at_kst": now_kst(),
         "evidence": {k: "fixture-" + k for k in ab["evidence_fields"]},
         "approved_hashes": {rel: sha256_file(os.path.join(root, rel)) for rel in ab["approved_hashes_paths"]},
         "recorded_by": "selftest", "recorded_at_kst": now_kst()}
    wb(ab["record_path"], _json_bytes(A))
    expected = {"sealed_sha256": exp_sha,
                "labels_sha256": {"master_x": sha256_file(os.path.join(root, lab["master_x"]["path"])),
                                  "master_y": sha256_file(os.path.join(root, lab["master_y"]["path"]))},
                "approval_sha256": sha256_file(os.path.join(root, ab["record_path"])),
                "plan_sha256": sha256_file(plan_path)}
    return root, plan, expected, plan_path


def _copy_fixture(src_base, dst_base):
    shutil.copytree(os.path.join(src_base, "repo"), os.path.join(dst_base, "repo"))
    return os.path.join(dst_base, "repo")


def _run_core(root, plan, expected, plan_path, fault=None, call_log=None, power=None):
    hooks = {"plan_path": plan_path}
    if call_log is not None:
        hooks["call_log"] = call_log
    if power is not None:
        hooks["power"] = power
    return core(root, plan, expected, os.path.join(root, plan["outputs"]["root"]), fault=fault, hooks=hooks)


def _tree_bytes(d):
    out = {}
    for dp, _dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, d)] = open(p, "rb").read()
    return out


def _value_free(obj):
    """status·heartbeat 산출에 소수 값(4자리+)이 없는지."""
    s = json.dumps(obj, ensure_ascii=False)
    s = re.sub(r'"ts_kst": "[^"]*"', "", s)
    s = re.sub(r'"load1": [0-9.]+', "", s)
    return re.search(r"\d\.\d{4,}", s) is None


def selftest(out_path):
    res = {"stage": "selftest", "script_sha256": sha256_file(os.path.abspath(__file__)), "started_kst": now_kst()}
    plan_real = json.loads(open(os.path.join(ROOT, PLAN_REL), "rb").read())
    res["plan_sha256"] = sha256_file(os.path.join(ROOT, PLAN_REL))
    res["plan_sha_matches_constant"] = res["plan_sha256"] == PLAN_SHA256
    LR = plan_real["long_run"]
    res["watchdog_sha256"] = sha256_file(os.path.join(ROOT, LR["watchdog_path"]))
    res["checker_sha256"] = sha256_file(os.path.join(ROOT, plan_real["independent_check"]["script_path"]))
    real_before = stat_summary(ROOT, plan_real["stat_groups"])
    checks = {}

    def rec(name, ok, note=""):
        checks[name] = {"pass": bool(ok), "note": note}

    base = tempfile.mkdtemp(prefix="unblind_selftest_")
    try:
        fx_base = os.path.join(base, "fx0")
        os.makedirs(fx_base)
        root0, plan, expected, plan_path = build_fixture(fx_base, plan_real)

        def fresh(tag):
            b = os.path.join(base, tag)
            os.makedirs(b)
            return _copy_fixture(fx_base, b)

        def fplan(r):
            return os.path.join(r, PLAN_REL)

        # ── U1 상수·해시·계획 결속(재기술 0) ──
        src = open(os.path.abspath(__file__), encoding="utf-8").read()
        tree = ast.parse(src)
        consts = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)]
        strs = {c for c in consts if isinstance(c, str)}
        nums = {c for c in consts if isinstance(c, (int, float)) and not isinstance(c, bool)}
        ids = {i["id"] for i in plan_real["items"]}
        paths = set(plan_real["read_scope"]["files"]) | set(plan_real["read_scope"]["trees"])
        args = set()
        for i in plan_real["items"]:
            for k in ("signflip", "bootstrap"):
                if k in i:
                    args |= {i[k]["B"], i[k]["seed"]}
        D = plan_real["design"]
        args |= {D["n_rows"], D["n_pt"], D["n_groups"]}
        hit_ids = sorted(ids & strs)
        hit_paths = sorted(p for p in paths if any(p in s for s in strs))
        hit_nums = sorted(args & nums)
        rec("U1", res["plan_sha_matches_constant"] and not hit_ids and not hit_paths and not hit_nums
            and len(ids) == len(plan_real["items"]),
            "item ids %d · path literals %d · arg literals %d" % (len(hit_ids), len(hit_paths), len(hit_nums)))

        # ── U2 G-gate 거부 (쓰기 0) ──
        u2 = {}
        r = fresh("u2ok")
        u2["ok_passes"] = gate(r, {"plan": plan, "launch_lines": {}}) == []
        r = fresh("u2a")
        os.remove(os.path.join(r, plan["approval_binding"]["record_path"]))
        u2["no_approval"] = "approval_missing" in gate(r, {"plan": plan, "launch_lines": {}})
        r = fresh("u2b")
        with open(fplan(r), "ab") as f:
            f.write(b" ")
        u2["hash_mismatch"] = any(x.startswith("approval_hash_mismatch") for x in gate(r, {"plan": plan,
                                                                                         "launch_lines": {}}))
        r = fresh("u2c")
        ap_ = os.path.join(r, plan["expected_hash_source"]["audit_path"])
        A = json.loads(open(ap_, "rb").read())
        A["verdict"] = "FAIL"
        open(ap_, "wb").write(_json_bytes(A))
        u2["audit_fail"] = "audit_verdict_or_schema" in gate(r, {"plan": plan, "launch_lines": {}})
        r = fresh("u2d")
        fp_ = os.path.join(r, plan["flags"]["unblinding_performed_false"][0])
        open(fp_, "wb").write(json.dumps({"unblinding_performed": True}).encode())
        u2["flag"] = any(x.startswith("flag_unblinding") for x in gate(r, {"plan": plan, "launch_lines": {}}))
        r = fresh("u2e")
        os.makedirs(os.path.join(r, plan["outputs"]["root"]))
        u2["output_exists"] = "output_exists_not_resume_state" in gate(r, {"plan": plan, "launch_lines": {}})
        r = fresh("u2f")
        os.makedirs(os.path.join(r, plan["outputs"]["root"] + "_x"))
        u2["stray_glob"] = "unexpected_output_dirs" in gate(r, {"plan": plan, "launch_lines": {}})
        r = fresh("u2g")
        sealed_any = [p for p in plan["read_scope"]["files"] if p.endswith(".npz")][0]
        with open(os.path.join(r, sealed_any), "ab") as f:
            f.write(b"\0")
        u2["stat_changed"] = any(x.startswith("stat_fingerprint_changed") or x == "sealed_counts_changed"
                                 for x in gate(r, {"plan": plan, "launch_lines": {}}))
        before = _tree_bytes(r)
        gate(r, {"plan": plan, "launch_lines": {}})
        u2["gate_writes_zero"] = _tree_bytes(r) == before
        rec("U2", all(u2.values()), json.dumps(u2))

        # ── 정상 완주 (U3~U7·U10~U12 의 기준) ──
        rA = fresh("runA")
        calls = []
        sA = _run_core(rA, plan, dict(expected, plan_sha256=sha256_file(fplan(rA))), fplan(rA), call_log=calls)
        outA = os.path.join(rA, plan["outputs"]["root"])
        resA = json.loads(open(os.path.join(outA, plan["outputs"]["results_dir"], "results_full.json"), "rb").read())
        decA = resA["decisions"]
        rec("RUN_A", sA.get("published") is True, "n_items %s" % sA.get("n_items"))

        # ── U3 합성 Holm 7슬롯 ──
        L = list(sd.HOLM_FAMILY)

        def hand_holm(pv):
            m = 7
            order = sorted(range(m), key=lambda i: (pv[i], i))
            adj = [0.0] * m
            run = 0.0
            for rank, i in enumerate(order):
                run = max(run, (m - rank) * pv[i])
                adj[i] = min(1.0, run)
            return adj

        cases = {"ties": [0.01, 0.01, 0.2, 0.03, 0.5, 0.01, 0.04],
                 "boundary": [0.05 / 7 - 1e-6, 0.05 / 6 + 1e-6, 0.9, 0.9, 0.9, 0.9, 0.9],
                 "all_reject": [1e-4] * 7, "none_reject": [0.6] * 7,
                 "monotone": [0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.2]}
        u3 = {}
        for nm, pv in cases.items():
            h = sd.holm(dict(zip(L, pv)))
            hand = hand_holm(pv)
            u3[nm] = all(abs(h["adjusted_p"][L[i]] - hand[i]) < 1e-15 for i in range(7)) and all(
                h["reject"][L[i]] == (hand[i] < 0.05) for i in range(7))
        hm = sd.holm({k: v for k, v in zip(L[:6], [0.01] * 6)})
        u3["missing_fill"] = hm["undefined_filled"][L[6]] is True and hm["raw_p"][L[6]] == 1.0
        u3["boundary_split"] = sd.holm(dict(zip(L, cases["boundary"])))["reject"][L[0]] is True and \
            sd.holm(dict(zip(L, cases["boundary"])))["reject"][L[1]] is False
        indep = _independent_holm_via_checker(cases)
        u3["checker_agrees"] = indep
        rec("U3", all(u3.values()), json.dumps(u3))

        # ── U4 D14 ──
        H1, H2 = decA["holm"][plan["holm"]["adjudication_panel"]], decA["holm"][plan["holm"]["comparison_panel"]]
        lab8 = plan["holm"]["d14_excluded_label"]
        u4 = {"panel2_rqint_is_1": H2["raw_p"][lab8] == 1.0,
              "panel1_rqint_is_primary": H1["raw_p"][lab8] == resA["items"][
                  plan["holm"]["panels"][plan["holm"]["adjudication_panel"]]["slots"][lab8]["item"]]["p_slot"],
              "others_equal_raw": all(H1["raw_p"][k] == H2["raw_p"][k] for k in L if k != lab8)}
        pv1 = dict(zip(L, [0.0075, 0.3, 0.3, 0.3, 0.3, 0.3, 0.001]))
        pv2 = dict(pv1, **{lab8: 1.0})
        a1, a2 = sd.holm(pv1), sd.holm(pv2)
        flag = {k: a1["reject"][k] != a2["reject"][k] for k in L if k != lab8}
        u4["fixture_flag_true"] = any(flag.values())
        rec("U4", all(u4.values()), json.dumps(u4))

        # ── U5 G2·G11 ──
        nk = [i for i in plan["items"] if i["kind"] == "sealed_p_null"][0]
        u5 = {"g2_max": resA["items"][nk["id"]]["p_slot"] == max(resA["items"][nk["id"]]["p_emp_global"],
                                                                 resA["items"][nk["id"]]["p_emp_family"])}
        adj = H1["adjusted_p"]
        u5["rq4_uses_adjusted"] = decA["RQ4"]["global"]["p_emp"] == adj[plan["decisions"]["RQ4"]["holm_label"]] \
            and decA["RQ4"]["family_constrained"]["p_emp"] == adj[plan["decisions"]["RQ4"]["holm_label"]]
        r3s = plan["decisions"]["RQ3"]
        u5["rq3_uses_adjusted"] = decA["RQ3"]["M2b_vs_PID"]["p"] == adj[r3s["holm_labels"][0]] and \
            decA["RQ3"]["M2b_vs_PFAM"]["p"] == adj[r3s["holm_labels"][1]]
        c1id = plan["decisions"]["RQ2"]["item"]
        u5["rq2_uses_raw"] = decA["RQ2"]["signflip_p"] == resA["items"][c1id]["p_raw"]
        ci_ok = {"low": 0.01, "high": 0.05, "status": "estimable"}
        raw_ok = sd.rq3_decision(ci_ok, 0.02, ci_ok, 0.02)["success"]
        adj_f = sd.holm(dict(zip(L, [0.02, 0.02, 0.5, 0.5, 0.5, 0.5, 0.5])))["adjusted_p"]
        adj_res = sd.rq3_decision(ci_ok, adj_f[L[0]], ci_ok, adj_f[L[1]])["success"]
        u5["fixture_raw_success_adjusted_fail"] = raw_ok is True and adj_res is False
        u5["rq4_fixture"] = sd.rq4_decision(0.03, 0.03)["success"] is True and sd.rq4_decision(
            adj_f[L[0]], adj_f[L[0]])["success"] is False
        rec("U5", all(u5.values()), json.dumps(u5))

        # ── U6 호출 인자 ──
        u6 = {}
        sf_calls = [c for c in calls if c["func"] == "sap.signflip.scaffold_signflip"]
        bs_calls = [c for c in calls if c["func"] == "sap.bootstrap.paired_scaffold_bootstrap"]
        cons = [i for i in plan["items"] if i["kind"] == "contrast"]
        u6["n_signflip_calls"] = len([c for c in sf_calls if c["kwargs"].get("return_perm")]) == len(cons)
        u6["signflip_args"] = all(c["kwargs"]["seed"] == cons[0]["signflip"]["seed"] and c["kwargs"]["B"] ==
                                  cons[0]["signflip"]["B"] and c["kwargs"]["eligible_pt"] == list(range(plan[
                                      "design"]["n_pt"])) for c in sf_calls if c["kwargs"].get("return_perm"))
        u6["bootstrap_args"] = all(c["kwargs"]["seed"] == cons[0]["bootstrap"]["seed"] and c["kwargs"]["B"] ==
                                   cons[0]["bootstrap"]["B"] and c["kwargs"]["alpha"] == cons[0]["bootstrap"]["alpha"]
                                   and c["kwargs"]["return_boot"] is True for c in bs_calls)
        units = sorted({c["kwargs"]["unit"] for c in bs_calls})
        u6["bootstrap_units"] = units == sorted({i["bootstrap"]["unit"] for i in plan["items"] if "bootstrap" in i})
        # Δ 방향 = 처치 − 기준 (합성 행렬에서 직접)
        Xf = pd.read_parquet(os.path.join(rA, plan["labels"]["master_y"]["path"]))
        yv = Xf[[c for c in Xf.columns if c != "cid"]].values.astype(int)
        ok_dir = True
        for it in cons:
            def _m(rel):
                with np.load(os.path.join(rA, rel)) as z:
                    return z[plan["npz_schema"]["matrix_key"]]
            el = np.arange(plan["design"]["n_pt"])
            d = sm.macro_ap(yv, _m(it["treat"]["path"]), el)["macro_ap"] - sm.macro_ap(yv, _m(it["base"]["path"]),
                                                                                      el)["macro_ap"]
            ok_dir &= d == resA["items"][it["id"]]["delta_obs"]
        u6["delta_direction_treat_minus_base"] = bool(ok_dir)
        rec("U6", all(u6.values()), json.dumps(u6))

        # ── U7 G1 비트 일치 assert ──
        r = fresh("u7")
        G1 = plan["g1_bit_equality"]
        hp = os.path.join(r, G1["holm8"])
        H = json.loads(open(hp, "rb").read())
        _nested_set(H, G1["holm8_delta_key"], _get(H, G1["holm8_delta_key"]) + 1e-15)
        open(hp, "wb").write((json.dumps(H, indent=2) + "\n").encode())
        e7 = dict(expected, sealed_sha256=dict(expected["sealed_sha256"], **{G1["holm8"]: sha256_file(hp)}),
                  plan_sha256=sha256_file(fplan(r)))
        u7 = {}
        try:
            _run_core(r, plan, e7, fplan(r))
            u7["stopped"] = False
        except IntegrityFailure as e:
            u7["stopped"] = e.code == "g1_delta_rf"
        u7["no_results"] = not os.path.exists(os.path.join(r, plan["outputs"]["root"], plan["outputs"]["results_dir"]))
        r = fresh("u7b")
        dp = os.path.join(r, G1["d9"])
        D9 = json.loads(open(dp, "rb").read())
        rfk = _get(D9, G1["d9_rf_key"])
        rfk["ci_percentile"]["low"] = rfk["ci_percentile"]["low"] + 1e-12
        open(dp, "wb").write((json.dumps(D9, indent=2) + "\n").encode())
        e7b = dict(expected, sealed_sha256=dict(expected["sealed_sha256"], **{G1["d9"]: sha256_file(dp)}),
                   plan_sha256=sha256_file(fplan(r)))
        try:
            _run_core(r, plan, e7b, fplan(r))
            u7["d9_stopped"] = False
        except IntegrityFailure as e:
            u7["d9_stopped"] = e.code.startswith("g1_d9_")
        rec("U7", all(u7.values()), json.dumps(u7))

        # ── U8 실패 규칙 ──
        u8 = {}

        def expect_fail(tag, mutate, code_prefix, exp_over=None):
            r_ = fresh("u8_" + tag)
            ex = dict(expected, plan_sha256=sha256_file(fplan(r_)))
            if exp_over:
                ex = exp_over(r_, ex)
            mutate(r_)
            try:
                _run_core(r_, plan, ex, fplan(r_))
                return False
            except IntegrityFailure as e:
                o = os.path.join(r_, plan["outputs"]["root"])
                return (e.code.startswith(code_prefix) and not os.path.exists(os.path.join(o, plan["outputs"][
                    "results_dir"])) and os.path.exists(os.path.join(o, plan["outputs"]["staging_dir"],
                                                                     plan["outputs"]["failure_file"])))

        some_npz = [i for i in plan["items"] if i["kind"] == "contrast"][1]["base"]["path"]
        u8["input_missing"] = expect_fail("miss", lambda r_: os.remove(os.path.join(r_, some_npz)), "input_missing")
        u8["sha_mismatch"] = expect_fail("sha", lambda r_: open(os.path.join(r_, some_npz), "ab").write(b"\0"),
                                         "sha_mismatch")

        def nan_mut(r_):
            with np.load(os.path.join(r_, some_npz)) as z:
                M, cc = z[plan["npz_schema"]["matrix_key"]].copy(), z[plan["npz_schema"]["cid_key"]]
            M[0, 0] = np.nan
            buf = io.BytesIO()
            np.savez(buf, **{plan["npz_schema"]["matrix_key"]: M, plan["npz_schema"]["cid_key"]: cc})
            open(os.path.join(r_, some_npz), "wb").write(buf.getvalue())

        def nan_exp(r_, ex):
            nan_mut(r_)
            return dict(ex, sealed_sha256=dict(ex["sealed_sha256"], **{some_npz: sha256_file(os.path.join(r_,
                                                                                                        some_npz))}))
        u8["nan"] = expect_fail("nan", lambda r_: None, "matrix_nonfinite", exp_over=nan_exp)

        r_ = fresh("u8_compl")
        ex_ = dict(expected, plan_sha256=sha256_file(fplan(r_)))
        bad_plan = copy.deepcopy(plan)
        bad_plan["items"].append(copy.deepcopy(bad_plan["items"][0]))      # id 중복 → 완전성 실패
        try:
            _run_core(r_, bad_plan, ex_, fplan(r_))
            u8["completeness"] = False
        except IntegrityFailure as e:
            u8["completeness"] = e.code == "completeness_items"
        r_ = fresh("u8_chk")
        ex_ = dict(expected, plan_sha256=sha256_file(fplan(r_)))
        try:
            _core_with_tamper(r_, plan, ex_, {"plan_path": fplan(r_)})
            u8["independent_mismatch"] = False
        except IntegrityFailure as e:
            u8["independent_mismatch"] = e.code == "independent_check_mismatch"
        u8["independent_mismatch_no_results"] = not os.path.exists(os.path.join(
            r_, plan["outputs"]["root"], plan["outputs"]["results_dir"]))
        rec("U8", all(u8.values()), json.dumps(u8))

        # ── U9 재개 (항목 중간 중단 → 재실행 · 무중단과 바이트 동일) ──
        r = fresh("u9")
        ex9 = dict(expected, plan_sha256=sha256_file(fplan(r)))
        cons_ids = [i["id"] for i in plan["items"] if i["kind"] == "contrast"]
        n_int = 0
        for tag in ("crash_after_item:" + cons_ids[0], "sigterm_mid:" + cons_ids[2], "crash_after_r1"):
            try:
                _run_core(r, plan, ex9, fplan(r), fault={tag})
            except _Fault:
                n_int += 1
        _run_core(r, plan, ex9, fplan(r))
        out9 = os.path.join(r, plan["outputs"]["root"])
        u9 = {"interrupts": n_int == 3}
        same = True
        for it in plan["items"]:
            for p in _item_paths_static(plan, outA, it["id"]) + []:
                q = p.replace(outA, out9)
                if os.path.exists(p) != os.path.exists(q) or (os.path.exists(p) and open(p, "rb").read() != open(
                        q, "rb").read()):
                    same = False
        u9["items_byte_identical"] = same
        ra = json.loads(open(os.path.join(outA, plan["outputs"]["results_dir"], "results_full.json"), "rb").read())
        rb = json.loads(open(os.path.join(out9, plan["outputs"]["results_dir"], "results_full.json"), "rb").read())
        u9["results_full_equal"] = ra == rb
        rec("U9", all(u9.values()), json.dumps(u9))

        # ── U10 독립 검산기 ──
        chk_path = os.path.join(ROOT, plan_real["independent_check"]["script_path"])
        u10 = {}
        ctree = ast.parse(open(chk_path, encoding="utf-8").read())
        banned = tuple(plan_real["independent_check"]["banned_import_prefixes"])
        allowed = set(plan_real["independent_check"]["allowed_imports"])
        mods = set()
        for n_ in ast.walk(ctree):
            if isinstance(n_, ast.Import):
                mods |= {a.name for a in n_.names}
            elif isinstance(n_, ast.ImportFrom):
                mods.add(n_.module or "")
        u10["import_ban"] = not any(m.startswith(banned) for m in mods) and all(m.split(".")[0] in allowed
                                                                                for m in mods)
        stA = os.path.join(outA, plan["outputs"]["staging_dir"])
        u10["normal_all_match"] = json.loads(open(os.path.join(stA, plan["independent_check"]["output_file"]),
                                                  "rb").read())["all_match"] is True
        for tag in ("p", "holm", "label"):
            r_ = fresh("u10_" + tag)
            ex_ = dict(expected, plan_sha256=sha256_file(fplan(r_)))
            try:
                _core_with_tamper(r_, plan, ex_, {"plan_path": fplan(r_)}, what=tag)
                u10["detect_" + tag] = False
            except IntegrityFailure as e:
                u10["detect_" + tag] = e.code == "independent_check_mismatch"
        rec("U10", all(u10.values()), json.dumps(u10))

        # ── U11 BH·TOST·S-PT·부지표·D13 형식 ──
        u11 = {}
        pt = [i for i in plan["items"] if i["kind"] == "pt_tests"][0]
        rp = resA["items"][pt["id"]]
        u11["pt_bh_keys"] = set(rp["bh"]["adjusted_p"]) == set(rp["per_pt"]) and rp["n_eligible"] == len(rp["per_pt"])
        u11["tost_labels"] = all(v in ("Positive", "Equivalent", "Inconclusive", "Not-estimable")
                                 for v in decA["tost"].values()) and len(decA["tost"]) == len(cons)
        smi_ = [i for i in plan["items"] if i["kind"] == "sub_metrics"][0]
        sb_ = resA["items"][smi_["id"]]["base"]
        u11["sub_not_computable"] = all(sb_[k]["status"] == "not_computable" for k in smi_["spec"]["not_computable"])
        u11["sub_keys"] = all(k in sb_ for k in ("micro_ap", "label_weighted_macro_ap", "prevalence_normalized_lift",
                                                 "precision_at_k", "recall_at_k", "brier_macro", "roc_auc_macro",
                                                 "prevalence_bin_macro_ap"))
        fd = [i for i in plan["items"] if i["kind"] == "figure" and i["figure"]["type"] == "d13_tstar"][0]
        pd13 = resA["items"][fd["id"]]["panels"]["t_star"]
        u11["d13_bins_symmetric"] = len(pd13["counts"]) == fd["figure"]["bins"] and abs(
            pd13["edges"][0] + pd13["edges"][-1]) < 1e-15
        u11["pngs"] = all(os.path.exists(os.path.join(outA, plan["outputs"]["results_dir"], i["figure"]["output_stem"]
                                                      + ".png")) for i in plan["items"] if i["kind"] == "figure")
        rec("U11", all(u11.values()), json.dumps(u11))

        # ── U12 공개 산출 ──
        u12 = {}
        r = fresh("u12")
        ex12 = dict(expected, plan_sha256=sha256_file(fplan(r)))
        try:
            _run_core(r, plan, ex12, fplan(r), fault={"crash_before_publish_move"})
        except _Fault:
            pass
        u12["no_results_while_staging"] = not os.path.exists(os.path.join(r, plan["outputs"]["root"],
                                                                          plan["outputs"]["results_dir"]))
        resd = os.path.join(outA, plan["outputs"]["results_dir"])
        mp = json.loads(open(os.path.join(resd, "manifest_public.json"), "rb").read())
        u12["manifest_sha"] = all(sha256_file(os.path.join(resd, k)) == v for k, v in mp["files"].items())
        txt = open(os.path.join(resd, "reporting_text.md"), encoding="utf-8").read()
        u12["verbatim_texts"] = all(plan["reporting_text"][k] in txt for k in plan["reporting_text"]["insertion_order"]
                                    if isinstance(plan["reporting_text"][k], str))
        ev = json.loads(open(os.path.join(rA, plan["outputs"]["event_path"]), "rb").read())
        u12["event_recorded"] = ev["type"] == "unblinding_publish" and ev["manifest_public_sha256"] == sha256_file(
            os.path.join(resd, "manifest_public.json"))
        acc_ok = True
        for t in plan["read_scope"]["trees"]:
            lines = open(os.path.join(rA, t, "_sealed", "access.log"), encoding="utf-8").read().splitlines()
            types = [json.loads(x)["type"] for x in lines]
            acc_ok &= types[-1] == "unblinding_publish" and types.count("machine_read") >= 1
            acc_ok &= json.loads(lines[-1])["human_exposure"] is True
        u12["access_log_r1_r7"] = acc_ok
        rec("U12", all(u12.values()), json.dumps(u12))

        # ── U14 장시간 장치 ──
        rec("U14", *_selftest_watchdog(base, plan, plan_real))

        # ── U15 재개 vs 무결성 실패 · status 값 0 ──
        u15 = {}
        r = fresh("u15a")
        ex15 = dict(expected, plan_sha256=sha256_file(fplan(r)))
        try:
            _run_core(r, plan, ex15, fplan(r), fault={"sigterm_pt:" + pt["id"]})
        except _Fault:
            pass
        ck = os.path.join(r, plan["outputs"]["root"], plan["outputs"]["staging_dir"], plan["outputs"]["items_subdir"],
                          "_parts", "%s__pt_checkpoint.json" % pt["id"])
        u15["pt_checkpoint_saved"] = os.path.exists(ck)
        _run_core(r, plan, ex15, fplan(r))
        u15["sigterm_resumed"] = os.path.exists(os.path.join(r, plan["outputs"]["root"],
                                                             plan["outputs"]["results_dir"]))
        rq = json.loads(open(os.path.join(r, plan["outputs"]["root"], plan["outputs"]["results_dir"],
                                          "results_full.json"), "rb").read())
        u15["pt_resume_equal"] = rq["items"][pt["id"]] == resA["items"][pt["id"]]
        r = fresh("u15b")
        ex15b = dict(expected, plan_sha256=sha256_file(fplan(r)))
        try:
            _run_core(r, plan, ex15b, fplan(r), fault={"crash_after_item:" + cons_ids[0]})
        except _Fault:
            pass
        open(os.path.join(r, some_npz), "ab").write(b"\0")
        try:
            _run_core(r, plan, ex15b, fplan(r))
            u15["sha_tamper_stops"] = False
        except IntegrityFailure as e:
            u15["sha_tamper_stops"] = e.code == "sha_mismatch"
        try:
            _run_core(r, plan, ex15b, fplan(r))
            u15["resume_refused_after_failure"] = False
        except IntegrityFailure as e:
            u15["resume_refused_after_failure"] = e.code == "prior_failure"
        stt = stage_status(r, plan)
        u15["status_value_free"] = _value_free(stt) and stt.get("failure", {}).get("code") == "sha_mismatch"
        hb = [json.loads(x) for x in open(os.path.join(outA, plan["outputs"]["heartbeat_file"]), encoding="utf-8")]
        u15["heartbeat_value_free"] = all(set(h) == {"ts_kst", "event", "item", "power_ok", "load1"} for h in hb) and \
            _value_free(hb)
        rec("U15", all(u15.values()), json.dumps(u15))

        # ── U16 prereg_coverage ──
        rec("U16", *_selftest_coverage(plan_real))

        # ── U13 위생 ──
        u13 = {}
        net = {"socket", "urllib", "http", "requests", "ftplib", "smtplib", "ssl"}
        mods = set()
        for n_ in ast.walk(tree):
            if isinstance(n_, ast.Import):
                mods |= {a.name.split(".")[0] for a in n_.names}
            elif isinstance(n_, ast.ImportFrom):
                mods.add((n_.module or "").split(".")[0])
        u13["no_network_import"] = not (mods & net)
        env_attr = [n_ for n_ in ast.walk(tree) if isinstance(n_, ast.Attribute) and n_.attr == "environ"]
        env_store = [n_ for n_ in ast.walk(tree) if isinstance(n_, ast.Subscript) and isinstance(n_.value, ast.Attribute)
                     and n_.value.attr == "environ" and isinstance(n_.ctx, ast.Store)]
        u13["no_environ_read"] = len(env_attr) == len(env_store) and not [
            n_ for n_ in ast.walk(tree) if isinstance(n_, ast.Attribute) and n_.attr == "getenv"]
        u13["no_open_sealed"] = "open_sealed" not in [n_.attr for n_ in ast.walk(tree) if isinstance(n_, ast.Attribute)]
        r = fresh("u13")
        wrote_outside = []
        real_open = builtins.open

        def guard_open(file, mode="r", *a, **kw):
            if any(m in mode for m in "wax+") and not os.path.abspath(str(file)).startswith(base):
                wrote_outside.append(str(file))
            return real_open(file, mode, *a, **kw)

        builtins.open = guard_open
        try:
            _run_core(r, plan, dict(expected, plan_sha256=sha256_file(fplan(r))), fplan(r))
        finally:
            builtins.open = real_open
        u13["writes_inside_temp_only"] = not wrote_outside
        try:
            Writer([os.path.join(r, "x")], []).check(os.path.join(r, "y", "z"))
            u13["write_guard_blocks"] = False
        except IntegrityFailure:
            u13["write_guard_blocks"] = True
        real_after = stat_summary(ROOT, plan_real["stat_groups"])
        u13["real_sealed_unchanged"] = real_after == real_before
        u13["real_no_unblinding_dir"] = not glob.glob(os.path.join(ROOT, plan_real["outputs"]["presence_glob"]))
        rec("U13", all(u13.values()), json.dumps(u13))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    order = ["U1", "U2", "RUN_A", "U3", "U4", "U5", "U6", "U7", "U8", "U9", "U10", "U11", "U12", "U13", "U14", "U15",
             "U16"]
    res["checks"] = {k: checks[k] for k in order if k in checks}
    res["n_checks"] = len(res["checks"])
    res["n_pass"] = sum(1 for v in res["checks"].values() if v["pass"])
    res["skipped"] = [k for k in order if k not in checks]
    res["all_pass"] = res["n_pass"] == res["n_checks"] == len(order)
    res["finished_kst"] = now_kst()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(_json_bytes(res))
    print(json.dumps({"stage": "selftest", "all_pass": res["all_pass"], "n_pass": res["n_pass"],
                      "n_checks": res["n_checks"], "failed": [k for k, v in res["checks"].items() if not v["pass"]]},
                     ensure_ascii=False), flush=True)
    return EXIT_OK if res["all_pass"] else EXIT_CRASH


def _item_paths_static(plan, out_root, iid):
    d = os.path.join(out_root, plan["outputs"]["staging_dir"], plan["outputs"]["items_subdir"])
    return [os.path.join(d, iid + ".json"), os.path.join(d, iid + ".perm.npy"), os.path.join(d, iid + ".boot.npy")]


def _core_with_tamper(root, plan, expected, hooks, what="p"):
    """독립 검산 직전에 staging 을 변조(합성 저장소 전용) — R6 이 불일치를 잡아 중단하는지."""
    orig = r6_independent

    def tampered(ctx):
        P = ctx.plan
        if what == "p":
            it = [i for i in P["items"] if i["kind"] == "contrast"][0]
            p = _item_paths(ctx, it["id"])[0]
            R = json.loads(open(p, "rb").read())
            R["p_raw"] = R["p_raw"] + 1e-9
            ctx.w.atomic(p, _json_bytes(R))
        else:
            dp = os.path.join(ctx.staging, P["outputs"]["decisions_file"])
            D = json.loads(open(dp, "rb").read())
            if what == "holm":
                lab = sd.HOLM_FAMILY[0]
                D["holm"][P["holm"]["adjudication_panel"]]["adjusted_p"][lab] += 1e-9
            else:
                D["RQ2"]["success"] = not D["RQ2"]["success"]
            ctx.w.atomic(dp, _json_bytes(D))
        return orig(ctx)

    globals()["r6_independent"] = tampered
    try:
        return core(root, plan, expected, os.path.join(root, plan["outputs"]["root"]), hooks=hooks)
    finally:
        globals()["r6_independent"] = orig


def _independent_holm_via_checker(cases):
    """검산기 자체 Holm 을 별도 프로세스로 호출해 sap.decision.holm 과 정확 일치하는지."""
    chk = os.path.join(_HERE, "unblinding_independent_check.py")
    L = list(sd.HOLM_FAMILY)
    payload = json.dumps({"labels": L, "cases": cases})
    r = subprocess.run([sys.executable, "-B", chk, "--stage", "holm_probe"], input=payload, capture_output=True,
                       text=True)
    if r.returncode != 0:
        return False
    got = json.loads(r.stdout)
    for nm, pv in cases.items():
        h = sd.holm(dict(zip(L, pv)))
        if got[nm]["adjusted_p"] != [h["adjusted_p"][k] for k in L] or got[nm]["reject"] != [h["reject"][k]
                                                                                             for k in L]:
            return False
    return True


def _selftest_watchdog(base, plan, plan_real):
    import importlib.util
    LR = plan_real["long_run"]
    wpath = os.path.join(ROOT, LR["watchdog_path"])
    spec = importlib.util.spec_from_file_location("unblinding_watchdog_t", wpath)
    W = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(W)
    d = os.path.join(base, "wd")
    os.makedirs(d)
    u = {"max_restarts": W.MAX_RESTARTS == LR["max_restarts"]}
    lk = os.path.join(d, W.LOCK_NAME)
    fd1 = W.acquire_instance_lock(lk)
    fd2 = W.acquire_instance_lock(lk)
    u["single_instance"] = fd1 is not None and fd2 is None
    spawned = []
    u["dup_exit"] = W.main(watchdog_dir=d, heartbeat_path=os.path.join(d, "hb.jsonl"),
                           spawn=lambda: spawned.append(1) or 0) == W.EXIT_DUPLICATE and not spawned
    os.close(fd1)
    seq = iter([1, 1, 1, 1, 1, 1, 1, 1])
    clock = [0.0]

    def sleep(s):
        clock[0] += s

    ev = os.path.join(d, "ev_restart.jsonl")
    w = W.Watchdog(ev, os.path.join(d, "hb.jsonl"), spawn=lambda: next(seq), power=lambda: True, load1=lambda: 0.1,
                   clock=lambda: clock[0], sleep=sleep)
    rc = w.run()
    E = [json.loads(x) for x in open(ev, encoding="utf-8")]
    u["restart_limit"] = rc == W.EXIT_HARD and sum(1 for e in E if e["event"] == "restart_counted") == \
        LR["max_restarts"] + 1 and E[-1]["event"] == "restart_limit"
    pw = iter([False, False, True])
    ev2 = os.path.join(d, "ev_power.jsonl")
    w2 = W.Watchdog(ev2, os.path.join(d, "hb.jsonl"), spawn=lambda: 0, power=lambda: next(pw), load1=lambda: 0.1,
                    clock=lambda: clock[0], sleep=sleep)
    rc2 = w2.run()
    E2 = [json.loads(x)["event"] for x in open(ev2, encoding="utf-8")]
    u["battery_refuses_launch_until_ac"] = rc2 == 0 and E2.index("power_wait") < E2.index("launch")
    ev3 = os.path.join(d, "ev_hard.jsonl")
    w3 = W.Watchdog(ev3, os.path.join(d, "hb.jsonl"), spawn=lambda: W.EXIT_HARD, power=lambda: True,
                    load1=lambda: 0.1, clock=lambda: clock[0], sleep=sleep)
    u["integrity_no_restart"] = w3.run() == W.EXIT_HARD and [json.loads(x)["event"] for x in open(
        ev3, encoding="utf-8")].count("launch") == 1
    hbp = os.path.join(d, "hb2.jsonl")
    with open(hbp, "w") as f:
        f.write(json.dumps({"ts_kst": "t", "event": "item_done", "item": "X", "power_ok": True, "load1": 0.5}) + "\n")
    u["heartbeat_info_value_free"] = set(W.Watchdog(ev3, hbp).last_heartbeat()) <= {"event", "item"}
    vals = [json.loads(x) for f_ in (ev, ev2, ev3) for x in open(f_, encoding="utf-8")]
    u["events_value_free"] = all(set(e) <= set(W.EVENT_KEYS) for e in vals) and _value_free(vals)
    ok = all(u.values())
    return ok, json.dumps(u)


def _selftest_coverage(plan_real):
    cov = plan_real["prereg_coverage"]
    allowed = set(plan_real["prereg_coverage_rules"]["allowed_prefixes"])
    ids = {i["id"] for i in plan_real["items"]}
    reg = plan_real["prereg_coverage_rules"]["registered_items"]

    def check(c):
        miss = [k for k in reg if k not in c["map"]]
        bad = []
        for k, v in c["map"].items():
            pre = v["status"]
            if pre not in allowed:
                bad.append(k)
            if pre == "item" and not set(v["item_ids"]) <= ids:
                bad.append(k)
        return not miss and not bad

    ok_real = check(cov)
    c2 = copy.deepcopy(cov)
    c2["map"].pop(reg[0])
    ok_detect = not check(c2)
    return ok_real and ok_detect, json.dumps({"real_complete": ok_real, "removed_one_detected": ok_detect,
                                              "n_registered": len(reg)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["selftest", "run", "status"], default="selftest")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.stage == "selftest":
        plan = json.loads(open(os.path.join(ROOT, PLAN_REL), "rb").read())
        return selftest(os.path.join(ROOT, a.out) if a.out else os.path.join(ROOT, plan["freeze"]["selftest_run_path"]))
    if a.stage == "status":
        print(json.dumps(stage_status(), ensure_ascii=False, indent=2), flush=True)
        return EXIT_OK
    if a.out:
        raise SystemExit("--out 은 selftest 전용")
    try:
        return stage_run()
    except GateRefused as e:
        print(json.dumps({"stage": "run", "refused": str(e)}, ensure_ascii=False), flush=True)
        return EXIT_GATE
    except IntegrityFailure as e:
        print(json.dumps({"stage": "run", "integrity_failure": e.code, "item": e.item, "file": e.file},
                         ensure_ascii=False), flush=True)
        return EXIT_INTEGRITY
    except PowerLoss:
        return EXIT_POWER
    except SystemExit:
        raise
    except Exception as e:           # noqa: BLE001 — 값 누설 방지: 형식만
        print(json.dumps({"stage": "run", "crash": type(e).__name__}), flush=True)
        return EXIT_CRASH


if __name__ == "__main__":
    raise SystemExit(main())
