#!/usr/bin/env python3
"""pre_unblinding_audit_v2.py — [블록 AO] 개봉 전 감사 재수행 (지시서 `docs/103`).

블록 X(`docs/78`)의 봉인 완전성 점검은 **273/288** 만 대조한 상태로 끝났고, 그 뒤
블록 Z 가 봉인 산출물 2건과 access.log entry 30건을 더 남겼다(`docs/33` 항목53 ⑦
「개봉 전제 결손」). 이 스크립트는 **지금 있는 봉인 275/291 전체**를 대상으로 같은
점검을 다시 수행한다.

v1 무수정 원칙
--------------
`pre_unblinding_audit.py`(v1) 는 **바이트 하나 고치지 않는다.** v1 의 상수
(`SEALED_BASELINE_*` 273/288 · `G0_EXPECT` 의 status 해시)는 stale 하드코딩이 아니라
**블록 X 가 실제로 대조한 범위를 적은 역사 기록**이고, v1 의 sha256
`224a5c8b81cf0b58…` 은 R2 가 정한 불변식이다. 따라서 v1 은 **읽기 전용 모듈로 import**
해서 순수 함수만 재사용하고, 새 상수·새 산출 경로·자체 1회성 가드는 이 파일 안에만 둔다.

호출하지 않는 v1 함수: `main` · `gate_g0` · `hash_crosscheck` · `build_sign_matrix` ·
`verify_public_exposure`. 모듈 전역 재할당(`V1.<name> = …`)도 하지 않는다.

성격 고지
--------
**계산 0 · 학습 0 · 추론 0 · 개봉 0 · 새 부호 산출 0 · `_sealed/` 쓰기 0.**
봉인 파일에 하는 조작은 **경로·크기·mtime·sha256(바이트 해싱)** 뿐이다.
예외 두 가지만 명시 허용된다 — ⓐ `checkpoint.jsonl` 은 `V1.read_ckpt()`(키 허용목록
투영)로만 파싱한다 ⓑ `access.log` 는 메타데이터라 전체 파싱을 허용한다.

실행 (2단계 · 순서 고정)
------------------------
    PYTHONDONTWRITEBYTECODE=1 python3 -B v3_Multimodal/src/pre_unblinding_audit_v2.py --dry-run
    PYTHONDONTWRITEBYTECODE=1 python3 -B v3_Multimodal/src/pre_unblinding_audit_v2.py --write

`--dry-run` 은 모든 게이트·대조·예측값 검사를 수행하되 **파일 쓰기 0** 이고 1회성 가드를
적용하지 않는다. `--write` 만 1회성 가드를 걸고 산출물을 쓴다.
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import pre_unblinding_audit as V1                                    # noqa: E402
from compute_lock import ComputeLock, gate_b_exclusive               # noqa: E402

BLOCK = "AO — 개봉 전 감사 재수행(봉인 완전성 점검 v2)"
INSTRUCTION = "docs/103_pre_unblinding_reaudit_prompt_for_vscode.md"

PROV = os.path.join(ROOT, "experiments", "provenance")
RUNS = os.path.join(ROOT, "experiments", "runs")
CFG = os.path.join(ROOT, "v3_Multimodal", "config")

AUDIT_V2_JSON = os.path.join(PROV, "sealing_completeness_audit_v2.json")
OUT_RUN_V2 = os.path.join(RUNS, "v3_pre_unblinding_audit_v2")
PUBLIC_V2_JSON = os.path.join(OUT_RUN_V2, "audit_public.json")

SPEC_FILE = os.path.join(CFG, "post_interim_freeze_v1_0.json")
SPEC_KEY = "pre_unblinding_procedures_specified"
SPEC_SUBKEY = "sealing_completeness_audit"
STATUS_FILE = os.path.join(CFG, "post_interim_freeze_v1_0.status.json")

# v1 산출물 — 바이트 보존 대상 (착수=종료 확인용, 읽기 전용)
V1_SCRIPT = "v3_Multimodal/src/pre_unblinding_audit.py"
V1_SCRIPT_SHA = "224a5c8b81cf0b58ebb79560f566470b4792af030f0865a3d0910855dbfdf996"
V1_AUDIT = "experiments/provenance/sealing_completeness_audit.json"
V1_OUTPUTS = [
    V1_AUDIT,
    "experiments/provenance/sign_disclosure_matrix.json",
    "experiments/runs/v3_pre_unblinding_audit/audit_public.json",
    "experiments/runs/v3_pre_unblinding_audit/record_public.json",
]

# ── G0 v2 — 동결 12파일 (지시서 AO-1-2). v1 의 G0_EXPECT 는 읽지도 고치지도 않는다 ──
G0_EXPECT_V2 = {
    "v3_Multimodal/config/ladder_freeze.json": "b885585aefbabb32",
    "v3_Multimodal/config/gin_seed_freeze.json": "10828447c6d33118",
    "v3_Multimodal/config/gin_inner_valid_freeze.json": "038599c3e1576022",
    "v3_Multimodal/config/gin_inner_valid_freeze.status.json": "bd329fefe613971f",
    "v3_Multimodal/config/post_interim_freeze_v1_0.json": "502db732bd5e45cb",
    # ★ v1 은 a12fee2cdfd71350 — 블록 Y 의 superseding append 로 전이(항목53 ⑦ divergence-B)
    "v3_Multimodal/config/post_interim_freeze_v1_0.status.json": "dbb00d540d7436e5",
    "v3_Multimodal/config/rf_tuned_freeze.json": "c1ef6406fbb48b7f",
    "v3_Multimodal/config/holm7_latefusion_freeze.json": "d89f8c52412b656e",
    "experiments/sap/manifest.json": "d08dcedf2a22e1c8",
    "v3_Multimodal/config/a5_mechanism_freeze.json": "3419b2f793d74051",
    "v3_Multimodal/config/rqint_procedure_decisions_v1.json": "16776f21df6ae29b",
    "experiments/sap/sap_1_2_hash_registry.json": "855616a27ff1f8fa",
}

# cowork 2026-09-10 실측 · 가드 전용 — 기대목록 아님 (기대목록은 AO-3 에서 기록물로 구성)
SEALED_BASELINE_ARTIFACTS_V2 = 275
SEALED_BASELINE_ACCESS_LOGS_V2 = 16
SEALED_BASELINE_TOTAL_V2 = 291
SEALED_BASELINE_DIRS_V2 = 25

BLOCK_X_TS = "2026-08-07 09:52:20 KST"
BLOCK_Z_STEP = "등록 §11 세 번째 축 — A3·A4·A5·A6 층화(블록 Z)"

AXES_RUN = "experiments/runs/v3_stratification_axes"
AXES_SEALED_RESULT = f"{AXES_RUN}/_sealed/axes_result.json"
AXES_SEALED_CKPT = f"{AXES_RUN}/_sealed/checkpoint.jsonl"
DOCS81 = "docs/81_axes_a3a4a5a6_stratification_report.md"
AXES_RUNNER = "v3_Multimodal/src/axes_stratification_run.py"

CKPT_FILES = [
    "experiments/runs/v3_confirm_rest/_sealed/checkpoint.jsonl",
    "experiments/runs/v3_confirm_rftuned/_sealed/checkpoint.jsonl",
    "experiments/runs/v3_latefusion/_sealed/checkpoint.jsonl",
    "experiments/runs/v3_null_MAIN/_sealed/checkpoint.jsonl",
    AXES_SEALED_CKPT,
]

HEX64 = re.compile(r"^[0-9a-f]{64}$")


class Abort(Exception):
    """중단 — 즉시 종료 구간에서 던진다."""


class Findings:
    """blocking 수집기.

    착수 게이트 구간(AO-2 순서 ①~③)과 `--dry-run` 전 구간은 **즉시 중단**,
    `--write` 의 순서 ④~⑤ 는 **모아서** ⑥ 에서 FAIL 판정한다.
    """

    def __init__(self, write: bool):
        self.write = write
        self.items: list[str] = []
        self.immediate = True

    def add(self, msg: str) -> None:
        self.items.append(msg)
        if self.immediate or not self.write:
            raise Abort(msg)


def s16(relpath: str) -> str:
    return V1.sha256_file(os.path.join(ROOT, relpath))[:16]


def sha(relpath: str) -> str:
    return V1.sha256_file(os.path.join(ROOT, relpath))


def parse_kst(ts: str) -> datetime:
    """"YYYY-MM-DD HH:MM[:SS] KST" 두 형식을 모두 받는다."""
    t = ts.replace("KST", "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    raise ValueError(f"알 수 없는 ts 형식: {ts!r}")


def sealed_dir_of(relpath: str) -> str:
    parts = relpath.split("/")
    return "/".join(parts[: parts.index("_sealed") + 1])


# ═══════════════════════════════════════════════════════════════════════════
# AO-1. 게이트
# ═══════════════════════════════════════════════════════════════════════════
def gate_g0_v2():
    """동결 12파일 + SAP 판정 = 13행. v1 `gate_g0` 의 SAP 로직을 그대로 옮겨 왔다."""
    rows, bad = {}, []
    for p, exp in G0_EXPECT_V2.items():
        got = s16(p)
        rows[p] = {"expected_sha16": exp, "observed_sha16": got, "match": got == exp}
        if got != exp:
            bad.append(p)
    man = V1.load_json(os.path.join(ROOT, "experiments", "sap", "manifest.json"))
    mods, mbad = man["modules"], []
    for name, meta in mods.items():
        exp = meta if isinstance(meta, str) else (meta.get("sha256") or meta.get("sha"))
        got = V1.sha256_file(os.path.join(ROOT, "v3_Multimodal", "src", "sap", name))
        if not (got == exp or got.startswith(exp)):
            mbad.append(name)
    sap_ok = (man.get("sap_version") == "1.2" and len(mods) == 11 and not mbad)
    rows["_sap"] = {"sap_version": man.get("sap_version"), "n_modules": len(mods),
                    "n_module_mismatch": len(mbad), "mismatched_modules": mbad,
                    "match": bool(sap_ok)}
    return {"pass": bool(not bad and sap_ok), "n_rows": len(rows),
            "mismatched": bad + mbad, "detail": rows}


def status_sidecar_transition():
    st = V1.load_json(STATUS_FILE)
    hist = st.get("a5_requery_executed_history")
    ok = (isinstance(hist, list) and len(hist) >= 1
          and hist[0].get("from") is False and hist[0].get("to") is True
          and hist[0].get("ts_kst") == "2026-08-07 11:13:28 KST"
          and (hist[0].get("basis") or {}).get("block") == "Y")
    h0 = hist[0] if isinstance(hist, list) and hist else {}
    return {
        "pass": bool(ok),
        "observed_sha16": s16("v3_Multimodal/config/post_interim_freeze_v1_0.status.json"),
        "history_is_list": isinstance(hist, list),
        "history_len": len(hist) if isinstance(hist, list) else None,
        "from": h0.get("from"), "to": h0.get("to"), "ts_kst": h0.get("ts_kst"),
        "basis_block": (h0.get("basis") or {}).get("block"),
        "method": h0.get("method"),
        "recorded_g0_pass_in": "docs/82_docs55b_m1b_fix_and_a5_relabel_report.md:26 "
                               "(G0 동결 10종 표에 post_interim_freeze_v1_0.status "
                               "`dbb00d540d7436e5` 로 PASS 기록)",
        "note": "v1 G0_EXPECT 의 a12fee2cdfd71350 → 현행 dbb00d540d7436e5 전이 = "
                "블록 Y 의 superseding append(항목53 ⑦ divergence-B).",
    }


def sealed_baseline(snap):
    n_logs = sum(1 for k in snap if k.endswith("/access.log"))
    n_art = len(snap) - n_logs
    n_dirs = len([p for p in glob.glob(os.path.join(RUNS, "**", "_sealed"), recursive=True)
                  if os.path.isdir(p)])
    obs = {"n_artifacts": n_art, "n_access_logs": n_logs,
           "n_total": len(snap), "n_sealed_directories": n_dirs}
    exp = {"n_artifacts": SEALED_BASELINE_ARTIFACTS_V2,
           "n_access_logs": SEALED_BASELINE_ACCESS_LOGS_V2,
           "n_total": SEALED_BASELINE_TOTAL_V2,
           "n_sealed_directories": SEALED_BASELINE_DIRS_V2}
    return {"pass": obs == exp, "expected": exp, "observed": obs}


# ═══════════════════════════════════════════════════════════════════════════
# AO-3. 기대 목록 — v1 G1~G12 + G13 (비순환: 기록물에서 먼저 구성)
# ═══════════════════════════════════════════════════════════════════════════
def _axes_paths_from_ast():
    """`axes_stratification_run.py` 를 **ast.parse 로 리터럴만** 읽는다(import 0)."""
    src = open(os.path.join(ROOT, AXES_RUNNER), encoding="utf-8").read()
    tree = ast.parse(src)
    env = {"ROOT": ROOT}
    lineno = {}
    literals = []

    def resolve(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name) and node.id in env:
            return env[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "join"):
            parts = [resolve(a) for a in node.args]
            if any(p is None for p in parts):
                return None
            return os.path.join(*parts)
        return None

    contrasts = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name == "CONTRASTS":
                try:
                    contrasts = sorted({c["id"] for c in ast.literal_eval(node.value)})
                    lineno["CONTRASTS"] = node.lineno
                except Exception:
                    contrasts = None
                continue
            val = resolve(node.value)
            if isinstance(val, str):
                env[name] = val
                lineno[name] = node.lineno
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "axes_result.json":
            literals.append(node.lineno)
    sealed_dir = env.get("SEALED_DIR")
    ckpt = env.get("F_CKPT")
    return {
        "sealed_dir": os.path.relpath(sealed_dir, ROOT) if sealed_dir else None,
        "checkpoint": os.path.relpath(ckpt, ROOT) if ckpt else None,
        "axes_result": (os.path.relpath(os.path.join(sealed_dir, "axes_result.json"), ROOT)
                        if sealed_dir else None),
        "axes_result_literal_linenos": sorted(literals),
        "contrasts": contrasts,
        "linenos": lineno,
        "method": "ast.parse — import·실행 0",
    }


def _axes_paths_from_docs81():
    """docs/81 §3 의 봉인 경로 2행과 **바로 다음 행**의 sha16·크기를 뽑는다."""
    lines = open(os.path.join(ROOT, DOCS81), encoding="utf-8").read().split("\n")
    out = {}
    pat_sha = re.compile(r"`([0-9a-f]{16})…?`")
    pat_size = re.compile(r"([\d,]+)\s*B")
    for i, ln in enumerate(lines):
        for target in (AXES_SEALED_RESULT, AXES_SEALED_CKPT):
            if f"`{target}`" in ln and "SEALED" in ln:
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                m_sha, m_size = pat_sha.search(nxt), pat_size.search(nxt)
                out[target] = {
                    "path_lineno": i + 1,
                    "hash_lineno": i + 2,
                    "sha16": m_sha.group(1) if m_sha else None,
                    "size": int(m_size.group(1).replace(",", "")) if m_size else None,
                }
    return out


def build_expected_v2():
    groups = V1.build_expected()

    ast_facts = _axes_paths_from_ast()
    docs81 = _axes_paths_from_docs81()
    fl = V1.load_json(os.path.join(PROV, "first_look_log.json"))
    fl_paths = [e.get("sealed_path") for e in fl if e.get("sealed_path")]
    pub = V1.load_json(os.path.join(ROOT, AXES_RUN, "axes_public.json"))

    agreement = {
        "axes_result.json": {
            "docs81": AXES_SEALED_RESULT in docs81,
            "runner_ast": ast_facts["axes_result"] == AXES_SEALED_RESULT,
            "first_look_log": AXES_SEALED_RESULT in fl_paths,
            "axes_public": pub.get("sealed_result_path") == AXES_SEALED_RESULT,
        },
        "checkpoint.jsonl": {
            "docs81": AXES_SEALED_CKPT in docs81,
            "runner_ast": ast_facts["checkpoint"] == AXES_SEALED_CKPT,
        },
        "runner_ast_detail": ast_facts,
        "docs81_detail": docs81,
    }
    agreement["all_agree"] = bool(
        all(agreement["axes_result.json"].values())
        and all(agreement["checkpoint.jsonl"].values()))

    groups.append({
        "group": "stratification_axes_a3_a6",
        "expected_from": [
            f"{DOCS81} L{docs81.get(AXES_SEALED_RESULT, {}).get('path_lineno')}·"
            f"L{docs81.get(AXES_SEALED_CKPT, {}).get('path_lineno')} — 봉인 경로 2종",
            f"{AXES_RUNNER}:SEALED_DIR(L{ast_facts['linenos'].get('SEALED_DIR')})·"
            f"F_CKPT(L{ast_facts['linenos'].get('F_CKPT')}) + 리터럴 'axes_result.json' "
            f"(L{'·L'.join(str(x) for x in ast_facts['axes_result_literal_linenos'])}) "
            f"— AST 판독, import 0",
            "experiments/provenance/first_look_log.json[12].sealed_path",
            f"{AXES_RUN}/axes_public.json:sealed_result_path",
        ],
        "expected_grid": {
            "n_units": pub.get("n_units"),
            "contrasts": ast_facts["contrasts"],
            "n_unit_runs": pub.get("n_unit_runs"),
            "checkpoint_rows": len(pub.get("units") or []),
        },
        "expected_paths": [AXES_SEALED_RESULT, AXES_SEALED_CKPT],
        "n_expected": 2,
        "source_agreement": agreement,
    })
    return groups


# ═══════════════════════════════════════════════════════════════════════════
# AO-4. model × fold × seed 교차 대조 — 집합 판정
# ═══════════════════════════════════════════════════════════════════════════
def model_fold_seed_crosscheck_v2():
    out = V1.model_fold_seed_crosscheck()

    pub = V1.load_json(os.path.join(ROOT, AXES_RUN, "axes_public.json"))
    exp_keys = [f"{u['axis']}::{u['stratum']}::{u['contrast']}" for u in pub["units"]]
    ast_contrasts = set(_axes_paths_from_ast()["contrasts"] or [])
    pairs = {}
    for u in pub["units"]:
        pairs.setdefault((u["axis"], u["stratum"]), set()).add(u["contrast"])

    rows = V1.read_ckpt(AXES_SEALED_CKPT)
    obs_keys = [r.get("key") for r in rows]

    aux = {
        "contrast_set_matches_runner_ast":
            bool({u["contrast"] for u in pub["units"]} == ast_contrasts),
        "n_axis_stratum_pairs_is_20": len(pairs) == 20,
        "every_pair_has_both_contrasts": bool(all(v == ast_contrasts for v in pairs.values())),
    }
    out.append({
        "group": "stratification_axes_a3_a6",
        "source": f"{AXES_SEALED_CKPT} (키 화이트리스트 투영: key·ts_kst — "
                  f"sealed·public 은 적재하지 않음)",
        "criterion": "set equality on axis::stratum::contrast (개수 대조 아님)",
        "expected_grid": {"n_keys": len(set(exp_keys)),
                          "contrasts": sorted(ast_contrasts),
                          "n_axis_stratum_pairs": 20, "n_unit_runs": pub.get("n_unit_runs")},
        "observed_grid": {"n_keys": len(set(obs_keys)),
                          "contrasts": sorted({k.split("::")[-1] for k in obs_keys if k}),
                          "n_axis_stratum_pairs": len(pairs)},
        "set_equal": bool(set(obs_keys) == set(exp_keys) and all(aux.values())),
        "n_rows": len(rows),
        "n_duplicate_keys": len(obs_keys) - len(set(obs_keys)),
        "auxiliary_conditions": aux,
    })
    return out


# ═══════════════════════════════════════════════════════════════════════════
# AO-5. 해시 — 기록된 값과 대조 (기록원 R-a ~ R-d 추가)
# ═══════════════════════════════════════════════════════════════════════════
def recorded_hashes_v2():
    """(path → [(value, source, mode)]) — mode ∈ {sha256, sha16_prefix+size}."""
    rec: dict[str, list[tuple]] = {}
    for path, pairs in V1.recorded_hashes().items():
        rec[path] = [(s, src, "sha256") for s, src in pairs]

    def add(path, value, source, mode="sha256"):
        rec.setdefault(path, []).append((value, source, mode))

    # R-a ─ 블록 X 스냅샷
    xa = V1.load_json(os.path.join(ROOT, V1_AUDIT))
    ra = xa["hashes"]["sha256_all_sealed_artifacts"]
    for p, sh in ra.items():
        add(p, sh, f"{V1_AUDIT}:hashes.sha256_all_sealed_artifacts (블록 X, {BLOCK_X_TS})")

    # R-b ─ 블록 Z 착수 sealed guard
    gp = V1.load_json(os.path.join(ROOT, AXES_RUN, "gates_public.json"))
    for p, sh in gp["sealed_guard_start"].items():
        if isinstance(sh, str) and HEX64.match(sh):
            add(p, sh, f"{AXES_RUN}/gates_public.json:sealed_guard_start "
                       f"(블록 Z, {gp.get('ts_kst')})")

    # R-c ─ axes_public 의 봉인 결과 해시
    pub = V1.load_json(os.path.join(ROOT, AXES_RUN, "axes_public.json"))
    if isinstance(pub.get("sealed_result_sha256"), str) and HEX64.match(pub["sealed_result_sha256"]):
        add(AXES_SEALED_RESULT, pub["sealed_result_sha256"],
            f"{AXES_RUN}/axes_public.json:sealed_result_sha256")

    # R-d ─ docs/81 의 16-hex 접두 + 크기
    d81 = _axes_paths_from_docs81()
    n_rd = 0
    for target, meta in d81.items():
        if meta.get("sha16") and meta.get("size"):
            add(target, {"sha16": meta["sha16"], "size": meta["size"]},
                f"{DOCS81} L{meta['hash_lineno']}", "sha16_prefix+size")
            n_rd += 1
    if n_rd != 2:
        raise Abort(f"R-d 파싱 실패 — 정확히 2쌍이어야 하는데 {n_rd}쌍")
    return rec, ra


def hash_crosscheck_v2(snap, rec, block_x_table):
    """v1 `hash_crosscheck` 와 같은 비교 로직(경로 기준 기록 sha ↔ live sha)."""
    arts = {k: v for k, v in snap.items() if not k.endswith("/access.log")}
    compared, mismatch, uncovered = 0, [], []
    per_file: dict[str, list[str]] = {}
    for path, entries in rec.items():
        if path not in snap:
            uncovered.append({"path": path, "reason": "기록에는 있으나 live 스냅샷에 없음"})
            continue
        live = snap[path]
        for value, src, mode in entries:
            compared += 1
            if mode == "sha256":
                ok = (value == live["sha256"])
                detail = {"recorded_sha256": value, "live_sha256": live["sha256"]}
            else:
                ok = (live["sha256"].startswith(value["sha16"])
                      and live["size"] == value["size"])
                detail = {"recorded_sha16": value["sha16"], "recorded_size": value["size"],
                          "live_sha16": live["sha256"][:16], "live_size": live["size"]}
            if not ok:
                mismatch.append({"path": path, "source": src, "mode": mode, **detail})
            per_file.setdefault(path, []).append(src)

    changed = sorted(p for p, sh in block_x_table.items()
                     if p in arts and arts[p]["sha256"] != sh)
    without = sorted(p for p in arts if p not in per_file)
    return {
        "sha256_all_sealed_artifacts": {k: v["sha256"] for k, v in sorted(arts.items())},
        "n_sealed_artifacts_hashed": len(arts),
        "recorded_sources": sorted({s for v in rec.values() for _, s, _ in v}),
        "recorded_source_ids": {
            "R-a": f"{V1_AUDIT}:hashes.sha256_all_sealed_artifacts",
            "R-b": f"{AXES_RUN}/gates_public.json:sealed_guard_start",
            "R-c": f"{AXES_RUN}/axes_public.json:sealed_result_sha256",
            "R-d": f"{DOCS81} L82·L84 (sha16 접두 + 크기)",
        },
        "n_files_with_recorded_hash": len(per_file),
        "files_without_recorded_hash": without,
        "n_compared": compared,
        "n_mismatch": len(mismatch),
        "mismatches": mismatch,
        "recorded_but_absent_in_live": uncovered,
        "changed_since_block_X": changed,
        "double_counted_note": "R-a 와 R-b 는 같은 값의 표(273행)를 서로 다른 주체·시각이 "
                               "쓴 독립 기록이라 둘 다 대조한다 → 862 쌍 가운데 546 쌍은 "
                               "이중 대조다.",
    }


# ═══════════════════════════════════════════════════════════════════════════
# AO-6. 열람 점검 — access.log
# ═══════════════════════════════════════════════════════════════════════════
def opened_check_v2(snap):
    oc = V1.opened_check(snap)

    xa = V1.load_json(os.path.join(ROOT, V1_AUDIT))
    base = xa["opened_check"]["entries_per_file"]

    per_file, new_rows, shrunk = {}, [], []
    n_open_sealed = 0
    for lp in sorted(oc["entries_per_file"]):
        rows = []
        with open(os.path.join(ROOT, lp), encoding="utf-8") as f:
            text = f.read()
        n_open_sealed += text.count("OPEN sealed")
        for line in text.split("\n"):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        n0 = base.get(lp, 0)
        per_file[lp] = {"n0": n0, "n_now": len(rows), "n_new": len(rows) - n0}
        if len(rows) < n0:
            shrunk.append(lp)
        for o in rows[n0:]:
            new_rows.append((lp, o))

    grouped, ts_all, unattributed = {}, [], []
    for lp, o in new_rows:
        key = f"{o.get('type')} | {o.get('actor')} | {o.get('step')} | " \
              f"human_exposure={o.get('human_exposure')}"
        grouped[key] = grouped.get(key, 0) + 1
        t = o.get("ts_kst") or o.get("ts")
        if t:
            ts_all.append(t)
        if o.get("step") != BLOCK_Z_STEP:
            unattributed.append({"file": lp, "step": o.get("step"),
                                 "ts_kst": t, "actor": o.get("actor"),
                                 "type": o.get("type")})

    oc["n_open_sealed_substring"] = n_open_sealed
    oc["delta_since_block_X"] = {
        "baseline_source": f"{V1_AUDIT}:opened_check.entries_per_file "
                           f"({len(base)}파일 · {sum(base.values())} entries)",
        "per_file": per_file,
        "n_new_entries": len(new_rows),
        "grouped": grouped,
        "ts_min": min(ts_all) if ts_all else None,
        "ts_max": max(ts_all) if ts_all else None,
        "unattributed": unattributed,
        "files_shrunk": shrunk,
    }
    return oc


# ═══════════════════════════════════════════════════════════════════════════
# AO-7. 실패·재시작 기록
# ═══════════════════════════════════════════════════════════════════════════
def _launcher_estimate_sessions():
    p = os.path.join(ROOT, AXES_RUN, "launcher.log")
    enter = re.compile(r"^(\S+ \S+) \| .*러너 진입 stage=(\S+)")
    leave = re.compile(r"^(\S+ \S+) \| 러너 종료 rc=(\S+) \(stage=(\S+)\)")
    sessions, pending = [], None
    for line in open(p, encoding="utf-8"):
        m = enter.match(line.strip())
        if m:
            pending = {"stage": m.group(2), "start_ts_kst": m.group(1) + " KST"}
            continue
        m = leave.match(line.strip())
        if m and pending and pending["stage"] == m.group(3):
            pending.update({"stop_ts_kst": m.group(1) + " KST", "rc": m.group(2)})
            sessions.append(pending)
            pending = None
    return [s for s in sessions if s["stage"] == "estimate"], len(sessions)


def failure_and_restart_log_v2():
    frl = V1.failure_and_restart_log()

    rows = V1.read_ckpt(AXES_SEALED_CKPT)
    keys = [r.get("key") for r in rows]
    ts = [r["ts_kst"] for r in rows if "ts_kst" in r]
    est, n_all = _launcher_estimate_sessions()
    frl["per_run_sessions"].append({
        "run": "v3_stratification_axes",
        "checkpoint": AXES_SEALED_CKPT,
        "n_rows": len(rows),
        "duplicate_key_field": "key (★ v1 의 (mode, seed)/(repeat, model, fold) 로직을 "
                               "쓰면 (None, None)×40 이 되어 중복 39 로 오판한다)",
        "n_unique_keys": len(set(keys)),
        "n_duplicate_keys": len(keys) - len(set(keys)),
        "n_timestamp_regressions": sum(1 for a, b in zip(ts, ts[1:]) if b < a),
        "ts_min": min(ts) if ts else None, "ts_max": max(ts) if ts else None,
        "launcher_estimate_sessions": est,
        "n_estimate_sessions": len(est),
        "n_launcher_sessions_all_stages": n_all,
        "source_launcher_log": f"{AXES_RUN}/launcher.log",
    })

    frl["known_failure_and_restart_events"].extend([
        {
            "event": "블록 Z 선행 세션 → 재개 (2회차 실행 아님)",
            "when_kst": "2026-08-07 12:05~12:29 KST 선행 세션 → 같은 블록이 체크포인트 "
                        "설계에 따라 재개 (재개 세션 게이트 기록 2026-08-07 16:56:39 KST)",
            "evidence": f"{DOCS81} §5 편차 1 · {AXES_RUN}/gates_public.json:ts_kst",
            "affected_unit": "블록 Z 전 구간",
            "verdict": "산출 결손·중복 아님 — 선행 세션은 Z-2(경계 amendment + docs/33 "
                       "항목39)와 --stage verify 까지만 수행했고 checkpoint.jsonl · "
                       "axes_result.json · axes_public.json 은 전부 부재였다. 재개 세션이 "
                       "게이트 전항을 다시 실측하고 --stage verify 를 재실행했다. "
                       "체크포인트 40행 · key 중복 0.",
            "caffeinate_note": None,
        },
        {
            "event": "블록 Z 공개요약 코드 결함 교정 재진입 (통계 재계산 0)",
            "when_kst": "2026-08-08 16:22:50 → 16:22:53 KST (stage=estimate, rc=0)",
            "evidence": f"{DOCS81} §5 편차 2 · {AXES_RUN}/launcher.log · "
                        f"{AXES_RUN}/axes_public.json:sealed_result_rewritten_this_run",
            "affected_unit": "axes_public.json 의 estimability 판정 필드 (봉인 산출물 무관)",
            "verdict": "체크포인트 40건 전건 SKIP 으로 교정 → 통계 재계산 0 · 봉인 재작성 0 "
                       "(sealed_result_rewritten_this_run false · axes_result.json sha16 "
                       "5c1aa8e24cd5ca9c 가 docs/81 §3 기록과 동일) · 봉인 판독 0. "
                       "이 재진입이 2026-08-08 16:22:52 KST access.log entry 6건 / 3파일을 남겼다.",
            "caffeinate_note": None,
        },
    ])
    frl["n_known_events"] = len(frl["known_failure_and_restart_events"])
    return frl


# ═══════════════════════════════════════════════════════════════════════════
# AO-8. 감사 범위 밖의 봉인 사본
# ═══════════════════════════════════════════════════════════════════════════
DISPOSITION = ("보존 + 문서화 — 사용자 확정 2026-09-10. 근거: 원본과 바이트 동일·열람 "
               "흔적은 기계 판독뿐이며, 2026-07-27 시점 해시를 담은 독립 사본이라 원본 "
               "무변경의 보조 증거가 된다. 문제는 사본 존재가 기록되지 않았던 점이므로 "
               "본 감사 산출물과 docs/33 항목54 기재로 해소한다.")

AO8_RULE = ("ⓐ 모든 사본이 live 봉인 원본과 바이트 동일 ⓑ 사본 디렉터리 access.log 에 "
            "human_exposure true 0 · type 이 machine_read 만 ⓒ sealed 이름 디렉터리 안에 "
            "기대 7파일 말고 다른 파일 0 ⓓ 사본 파일 3개가 전부 AO-5 에서 이미 대조된 "
            "원본에 대응 — 모두 만족하면 non_blocking_recorded, 하나라도 어기면 blocking.")


def _is_original(rel_path: str) -> bool:
    return rel_path.startswith("experiments/runs/") and "_sealed" in rel_path.split("/")


def out_of_glob_sealed_copies(snap, hashed_paths):
    arts = {k: v for k, v in snap.items() if not k.endswith("/access.log")}
    by_size: dict[int, list[str]] = {}
    by_sha: dict[str, list[str]] = {}
    for k, v in arts.items():
        by_size.setdefault(v["size"], []).append(k)
        by_sha.setdefault(v["sha256"], []).append(k)

    n_scanned = n_hashed = 0
    copies = []
    sealed_dirs = set()
    for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=False):
        dirnames[:] = [d for d in dirnames if not (dirpath == ROOT and d == ".git")]
        rd = os.path.relpath(dirpath, ROOT)
        if rd != "." and not _is_original(rd) and "sealed" in os.path.basename(rd).lower():
            sealed_dirs.add(rd)
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            rp = os.path.relpath(full, ROOT)
            if _is_original(rp):
                continue
            n_scanned += 1
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size not in by_size:
                continue
            n_hashed += 1
            digest = V1.sha256_file(full)
            for orig in by_sha.get(digest, []):
                copies.append({"copy_path": rp, "original_path": orig,
                               "sha16": digest[:16], "size": size,
                               "byte_identical": True})

    files_in_dirs = []
    for d in sorted(sealed_dirs):
        for dirpath, _dn, fns in os.walk(os.path.join(ROOT, d)):
            for fn in sorted(fns):
                full = os.path.join(dirpath, fn)
                rp = os.path.relpath(full, ROOT)
                if any(r["path"] == rp for r in files_in_dirs):
                    continue
                st = os.stat(full)
                digest = V1.sha256_file(full)
                if any(c["copy_path"] == rp for c in copies):
                    cls = "봉인 사본"
                elif fn == "access.log":
                    cls = "사본 디렉터리 열람 기록"
                elif fn == "SHA256SUMS.txt":
                    cls = "백업 체크섬"
                else:
                    cls = "기록물 구본(봉인 아님 · 해싱만, 파싱 0)"
                files_in_dirs.append({"path": rp, "size": st.st_size,
                                      "mtime": round(st.st_mtime, 6),
                                      "sha256": digest, "sha16": digest[:16],
                                      "class": cls})

    # 사본 디렉터리 access.log
    log_check = {"present": False}
    for r in files_in_dirs:
        if r["path"].endswith("/access.log"):
            text = open(os.path.join(ROOT, r["path"]), encoding="utf-8").read()
            rows = [json.loads(x) for x in text.split("\n") if x.strip()]
            log_check = {
                "present": True, "path": r["path"], "n_entries": len(rows),
                "types": sorted({o.get("type") for o in rows}),
                "n_human_exposure_true": sum(1 for o in rows if o.get("human_exposure") is True),
                "n_open_sealed_substring": text.count("OPEN sealed"),
                "last_ts_kst": max((o.get("ts_kst") or o.get("ts")) for o in rows) if rows else None,
            }

    # SHA256SUMS.txt
    sums_check = {"present": False}
    for r in files_in_dirs:
        if r["path"].endswith("/SHA256SUMS.txt"):
            base = os.path.dirname(os.path.join(ROOT, r["path"]))
            ok = bad = 0
            for line in open(os.path.join(ROOT, r["path"]), encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                exp, name = line.split(None, 1)
                got = V1.sha256_file(os.path.join(base, name.strip()))
                if got == exp:
                    ok += 1
                else:
                    bad += 1
            sums_check = {"present": True, "path": r["path"], "n_ok": ok, "n_bad": bad,
                          "verdict": "OK" if bad == 0 else "FAIL"}

    copy_files = sorted({c["copy_path"] for c in copies})
    conds = {
        "a_all_byte_identical": all(c["byte_identical"] for c in copies),
        "b_access_log_machine_only": bool(
            log_check.get("present") and log_check.get("n_human_exposure_true") == 0
            and log_check.get("types") == ["machine_read"]
            and log_check.get("n_open_sealed_substring") == 0),
        "c_no_other_files": len(files_in_dirs) == 7,
        "d_copies_covered_by_ao5": all(c["original_path"] in hashed_paths for c in copies),
    }
    return {
        "scan_scope": "저장소 루트 전체(.git 제외 · experiments/runs/**/_sealed/** 원본 제외 · "
                      "심볼릭 링크 미추적) 중 live 봉인 산출물과 크기가 같은 파일만 sha256 계산",
        "n_files_scanned": n_scanned,
        "n_files_hashed": n_hashed,
        "n_copy_files": len(copy_files),
        "n_copy_pairs": len(copies),
        "copies": sorted(copies, key=lambda c: (c["copy_path"], c["original_path"])),
        "copy_files": copy_files,
        "sealed_named_dirs": sorted(sealed_dirs),
        "files_in_sealed_named_dirs": sorted(files_in_dirs, key=lambda r: r["path"]),
        "n_files_in_sealed_named_dirs": len(files_in_dirs),
        "backup_access_log_check": log_check,
        "backup_sha256sums_check": sums_check,
        "rule": AO8_RULE,
        "rule_conditions": conds,
        "verdict": "non_blocking_recorded" if all(conds.values()) else "blocking",
        "disposition": DISPOSITION,
        "note": "원본끼리의 바이트 동일(identity 대조 설계)은 사본으로 세지 않는다 — "
                "copy_path 가 _sealed 원본 밖일 때만 사본이다.",
    }


# ═══════════════════════════════════════════════════════════════════════════
# AO-9. 부호 인지 기록표 정합 (재생성 0 · 값 0)
# ═══════════════════════════════════════════════════════════════════════════
def sign_disclosure_consistency():
    fl = V1.load_json(os.path.join(PROV, "first_look_log.json"))
    mx = V1.load_json(os.path.join(PROV, "sign_disclosure_matrix.json"))
    n_known = sum(1 for e in fl if e.get("delta_sign") is not None)
    x_dt = parse_kst(BLOCK_X_TS)
    later = [i for i, e in enumerate(fl) if e.get("ts_kst") and parse_kst(e["ts_kst"]) > x_dt]
    new_known = [i for i in later if fl[i].get("delta_sign") is not None]
    return {
        "n_first_look_entries": len(fl),
        "n_sign_known": n_known,
        "matrix_n_rows_field": mx.get("n_rows"),
        "matrix_len_rows": len(mx.get("rows") or []),
        "three_values_agree": bool(n_known == mx.get("n_rows") == len(mx.get("rows") or [])),
        "n_entries_after_block_X": len(later),
        "entry_indices_after_block_X": later,
        "new_sign_known_contrasts_since_block_X": len(new_known),
        "artifacts_sha256": {
            "sign_disclosure_matrix.json": sha("experiments/provenance/sign_disclosure_matrix.json"),
            "docs/79_sign_disclosure_matrix.md": sha("docs/79_sign_disclosure_matrix.md"),
            "first_look_log.json": sha("experiments/provenance/first_look_log.json"),
        },
        "regenerated": False,
        "note": "이 블록은 기록표를 다시 만들지도 고치지도 않는다 — 개수와 sha 만 적는다.",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════════════════
def _snapshot_witness(snap):
    """착수/종료 대조용 증거 묶음."""
    return {
        "sealed": {k: (v["size"], v["mtime"], v["sha256"]) for k, v in sorted(snap.items())},
        "v1_script": sha(V1_SCRIPT),
        "v1_outputs": {p: sha(p) for p in V1_OUTPUTS},
        "sign_artifacts": {
            "sign_disclosure_matrix.json": sha("experiments/provenance/sign_disclosure_matrix.json"),
            "docs/79_sign_disclosure_matrix.md": sha("docs/79_sign_disclosure_matrix.md"),
            "first_look_log.json": sha("experiments/provenance/first_look_log.json"),
        },
    }


def _backup_witness(oog):
    return {r["path"]: (r["size"], r["mtime"], r["sha256"])
            for r in oog["files_in_sealed_named_dirs"]}


def run(write: bool) -> int:
    fnd = Findings(write)
    mode = "--write" if write else "--dry-run"
    V1.logln(f"[모드] {mode} · 블록 {BLOCK}")

    with ComputeLock(script="pre_unblinding_audit_v2.py", role="runner"):
        gb_entry = gate_b_exclusive("pre_unblinding_audit_v2:entry")
        try:
            # ── ③ AO-1 게이트 1~5 ────────────────────────────────────────
            g0 = gate_g0_v2()
            if not g0["pass"]:
                fnd.add(f"G0 v2 불일치: {g0['mismatched']}")
            trans = status_sidecar_transition()
            if not trans["pass"]:
                fnd.add("status sidecar 전이 기록 불일치")
            holm = V1.gate_holm()
            if not holm.get("pass"):
                fnd.add(f"G-HOLM 불일치: {holm.get('n_labels')}")
            status = V1.load_json(STATUS_FILE)
            unb = {"unblinding_performed": status.get("unblinding_performed"),
                   "gin_start_still_blocked": status.get("gin_start_still_blocked")}
            if unb["unblinding_performed"] is not False or unb["gin_start_still_blocked"] is not True:
                fnd.add(f"개봉 상태 이상: {unb}")
            V1.logln(f"[G0 v2] {g0['n_rows']}행 PASS · SAP "
                     f"{g0['detail']['_sap']['sap_version']} "
                     f"{g0['detail']['_sap']['n_modules']}모듈 불일치 "
                     f"{g0['detail']['_sap']['n_module_mismatch']} | "
                     f"[G-HOLM] {holm['n_labels']} 라벨 (decision.py:{holm['lineno']})")

            snap_start = V1.sealed_snapshot()
            base = sealed_baseline(snap_start)
            if not base["pass"]:
                fnd.add(f"봉인 기준선 불일치 — {base['observed']} (기대 {base['expected']})")
            V1.logln(f"[sealed guard] 착수 — 산출물 {base['observed']['n_artifacts']} · "
                     f"access.log {base['observed']['n_access_logs']} · "
                     f"합 {base['observed']['n_total']} · "
                     f"디렉터리 {base['observed']['n_sealed_directories']}")
            witness_start = _snapshot_witness(snap_start)
            if witness_start["v1_script"] != V1_SCRIPT_SHA:
                fnd.add("v1 스크립트 sha256 불일치")

            # ── ④ AO-3 ~ AO-9 ────────────────────────────────────────────
            fnd.immediate = False

            groups = build_expected_v2()
            expected_all = []
            for g in groups:
                expected_all += g["expected_paths"]
            n_dup = len(expected_all) - len(set(expected_all))
            if n_dup:
                fnd.add(f"기대 목록 중복 경로 {n_dup}건")
            g13 = groups[-1]
            if not g13["source_agreement"]["all_agree"]:
                fnd.add("G13 기록원 간 경로 불일치")
            if g13["expected_grid"] != {"n_units": 20, "contrasts": ["C1", "C2"],
                                        "n_unit_runs": 40, "checkpoint_rows": 40}:
                fnd.add(f"G13 expected_grid 불일치: {g13['expected_grid']}")

            live_art = {k for k in snap_start if not k.endswith("/access.log")}
            missing = sorted(set(expected_all) - live_art)
            unexpected = sorted(live_art - set(expected_all))
            xa_table = V1.load_json(os.path.join(ROOT, V1_AUDIT))["hashes"]["sha256_all_sealed_artifacts"]
            added = sorted(live_art - set(xa_table))
            removed = sorted(set(xa_table) - live_art)
            V1.logln(f"[대조] 기대 {len(expected_all)} · live 산출물 {len(live_art)} → "
                     f"missing {len(missing)} · unexpected {len(unexpected)} | "
                     f"ΔX added {len(added)} · removed {len(removed)}")
            if missing:
                fnd.add(f"missing {len(missing)}건 — 산출 결손(개봉 부적격)")
            if unexpected:
                fnd.add(f"unexpected {len(unexpected)}건 — 기대 목록 미포괄")
            if sorted(added) != sorted([AXES_SEALED_RESULT, AXES_SEALED_CKPT]):
                fnd.add(f"delta_vs_block_X.added 예측 불일치: {added}")
            if removed:
                fnd.add(f"delta_vs_block_X.removed {len(removed)}건")

            mfs = model_fold_seed_crosscheck_v2()
            if not all(x["set_equal"] for x in mfs):
                fnd.add("model×fold×seed 집합 불일치: "
                        + ", ".join(x["group"] for x in mfs if not x["set_equal"]))
            V1.logln(f"[교차대조] {len(mfs)}군 set_equal "
                     f"{sum(1 for x in mfs if x['set_equal'])}/{len(mfs)}")

            rec, xa_table2 = recorded_hashes_v2()
            hashes = hash_crosscheck_v2(snap_start, rec, xa_table2)
            V1.logln(f"[해시] 산출물 {hashes['n_sealed_artifacts_hashed']} · "
                     f"기록보유 {hashes['n_files_with_recorded_hash']} · "
                     f"대조 {hashes['n_compared']} · 불일치 {hashes['n_mismatch']}")
            for key, exp_val in [("n_sealed_artifacts_hashed", 275),
                                 ("n_files_with_recorded_hash", 275),
                                 ("n_compared", 862), ("n_mismatch", 0)]:
                if hashes[key] != exp_val:
                    fnd.add(f"AO-5 예측값 불일치 — {key}={hashes[key]} (기대 {exp_val})")
            for key in ("files_without_recorded_hash", "recorded_but_absent_in_live",
                        "changed_since_block_X"):
                if hashes[key]:
                    fnd.add(f"AO-5 예측값 불일치 — {key} {len(hashes[key])}건")

            opened = opened_check_v2(snap_start)
            d = opened["delta_since_block_X"]
            V1.logln(f"[열람] 파일 {opened['n_access_log_files']} · entry "
                     f"{opened['n_access_log_entries']} · human {opened['n_human_exposure_true']} · "
                     f"신규 {d['n_new_entries']} · OPEN sealed {opened['n_open_sealed_substring']}")
            if opened["n_human_exposure_true"]:
                fnd.add(f"human_exposure=true {opened['n_human_exposure_true']}건 — 개봉 발생")
            if opened["n_open_sealed_substring"]:
                fnd.add(f"'OPEN sealed' {opened['n_open_sealed_substring']}건")
            if d["unattributed"]:
                fnd.add(f"귀속 불가 신규 entry {len(d['unattributed'])}건")
            if d["files_shrunk"]:
                fnd.add(f"access.log 행 감소 {len(d['files_shrunk'])}파일")
            if d["n_new_entries"] != 30 or len(d["grouped"]) != 1:
                fnd.add(f"신규 entry 예측 불일치: {d['n_new_entries']}건 / "
                        f"{len(d['grouped'])}조합")

            frl = failure_and_restart_log_v2()
            oog = out_of_glob_sealed_copies(snap_start, set(live_art))
            V1.logln(f"[범위 밖 사본] 스캔 {oog['n_files_scanned']} · 해시 "
                     f"{oog['n_files_hashed']} · 사본 {oog['n_copy_files']}파일/"
                     f"{oog['n_copy_pairs']}쌍 · 판정 {oog['verdict']}")
            if oog["verdict"] != "non_blocking_recorded":
                fnd.add(f"AO-8 판정 규칙 위반: {oog['rule_conditions']}")
            if oog["backup_sha256sums_check"].get("verdict") != "OK":
                fnd.add("백업 SHA256SUMS 대조 실패")
            witness_backup_start = _backup_witness(oog)

            sign = sign_disclosure_consistency()
            if not sign["three_values_agree"]:
                fnd.add("부호 인지 기록표 개수 불일치")
            if sign["new_sign_known_contrasts_since_block_X"]:
                fnd.add("블록 X 이후 새로 알려진 부호 있음")
            for k, v in sign["artifacts_sha256"].items():
                if v != witness_start["sign_artifacts"][k]:
                    fnd.add(f"부호 관련 산출물 sha 변화: {k}")

            # ── ⑤ 종료 측 재확인 ─────────────────────────────────────────
            snap_end = V1.sealed_snapshot()
            witness_end = _snapshot_witness(snap_end)
            sealed_same = witness_start["sealed"] == witness_end["sealed"]
            v1_script_same = witness_start["v1_script"] == witness_end["v1_script"]
            v1_out_same = witness_start["v1_outputs"] == witness_end["v1_outputs"]
            sign_same = witness_start["sign_artifacts"] == witness_end["sign_artifacts"]
            g0_end = gate_g0_v2()
            oog_end = out_of_glob_sealed_copies(snap_end, {k for k in snap_end
                                                           if not k.endswith("/access.log")})
            backup_same = witness_backup_start == _backup_witness(oog_end)
            base_end = sealed_baseline(snap_end)
            if not sealed_same:
                fnd.add("봉인 스냅샷 착수≠종료")
            if not v1_script_same:
                fnd.add("v1 스크립트 sha 착수≠종료")
            if not v1_out_same:
                fnd.add("v1 산출물 4종 sha 착수≠종료")
            if not sign_same:
                fnd.add("부호 관련 3종 sha 착수≠종료")
            if not backup_same:
                fnd.add("백업 7파일 착수≠종료")
            if not g0_end["pass"]:
                fnd.add("G0 v2 종료 측 불일치")
            gb_exit = gate_b_exclusive("pre_unblinding_audit_v2:exit")
            V1.logln(f"[sealed guard] 종료 — 산출물 {base_end['observed']['n_artifacts']} · "
                     f"access.log {base_end['observed']['n_access_logs']} · "
                     f"합 {base_end['observed']['n_total']} · 착수동일 {sealed_same}")
        except Abort as e:
            V1.logln(f"[중단] {e}")
            if not write:
                V1.logln("[중단] --dry-run — 파일 쓰기 0")
            return 3

        # ── ⑥ 판정 ───────────────────────────────────────────────────────
        blocking = list(fnd.items)
        spec_txt = V1.load_json(SPEC_FILE)[SPEC_KEY][SPEC_SUBKEY]
        audit = {
            "_warning": "점검 전용 — 지표·부호·λ·Δ·CI·p 값 일체 없음"
                        "(경로·개수·크기·mtime·해시·조합·세션 메타만).",
            "ts_kst": V1.now_kst(),
            "block": BLOCK,
            "instruction": INSTRUCTION,
            "spec_source": {
                "path": V1.rel(SPEC_FILE),
                "sha256": V1.sha256_file(SPEC_FILE),
                "key_path": f"{SPEC_KEY}.{SPEC_SUBKEY}",
                "verbatim": spec_txt,
            },
            "supersedes": {
                "v1_audit_path": V1_AUDIT,
                "v1_audit_sha256": witness_end["v1_outputs"][V1_AUDIT],
                "v1_coverage": {"artifacts": 273, "total": 288},
                "v1_script_path": V1_SCRIPT,
                "v1_script_sha256": witness_end["v1_script"],
                "v1_outputs_byte_preserved": bool(v1_script_same and v1_out_same),
                "v1_outputs": witness_end["v1_outputs"],
                "reason": "블록 X 감사(2026-08-07 09:52:20 KST) 이후 블록 Z 가 봉인 산출물 "
                          "2건과 access.log entry 30건을 남겨 live 275/291 가운데 273 개만 "
                          "대조된 상태였다(개봉 전제 결손). v1 은 1회성 가드로 재실행이 막혀 "
                          "있고 v1 상수는 블록 X 가 대조한 범위를 적은 역사 기록이므로 "
                          "고치지 않고, v1 을 읽기 전용으로 import 하는 v2 를 신설해 현행 "
                          "전체를 다시 대조했다.",
                "divergences_addressed": [
                    "항목53 ⑦ divergence-A SEALED_BASELINE",
                    "항목53 ⑦ divergence-B G0_EXPECT status",
                    "항목53 ⑦ 개봉 전제 결손",
                ],
            },
            "gates": {
                "G0_v2": g0,
                "G0_v2_at_exit": {"pass": g0_end["pass"], "mismatched": g0_end["mismatched"]},
                "G_HOLM": holm,
                "G_IDLE_B": {"entry": gb_entry, "exit": gb_exit,
                             "note": "계산 0 이므로 G-IDLE A 는 면제 · B 는 유지"},
                "sealed_baseline": base,
                "sealed_baseline_at_exit": base_end,
                "status_sidecar_transition": trans,
                "unblinding_state_at_start": unb,
            },
            "expected_manifest": groups,
            "expected_manifest_note": "G1~G12 는 v1 build_expected() 를 그대로 재사용하고 "
                                      "G13 만 v2 가 기록물 4곳에서 새로 구성했다. 어느 군도 "
                                      "live 디렉터리 열거로 만들지 않았다(비순환).",
            "live_inventory": {
                "n_sealed_files": base["observed"]["n_artifacts"],
                "n_access_logs": base["observed"]["n_access_logs"],
                "n_total": base["observed"]["n_total"],
                "n_sealed_directories": base["observed"]["n_sealed_directories"],
                "by_directory": {},
            },
            "crosscheck": {
                "scope": "access.log 제외 산출물 275종 (sealed guard 기준선 규약과 동일)",
                "n_expected": len(expected_all),
                "n_live": len(live_art),
                "missing": missing, "n_missing": len(missing),
                "unexpected": unexpected, "n_unexpected": len(unexpected),
                "delta_vs_block_X": {"added": added, "removed": removed,
                                     "baseline": f"{V1_AUDIT} (블록 X, {BLOCK_X_TS})"},
                "verdict": "PASS" if not missing and not unexpected else "FAIL",
            },
            "model_fold_seed_crosscheck": mfs,
            "hashes": hashes,
            "opened_check": opened,
            "failure_and_restart_log": frl,
            "out_of_glob_sealed_copies": oog,
            "sign_disclosure_consistency": sign,
            "unblinding_state": {
                "unblinding_performed": False,
                "unblinding_approver": "양진홍 교수님",
                "timing": "still_undecided — 별도 승인 필요",
                "remaining_requirements": [
                    "봉인 완전성 점검 — 이 블록의 판정으로 충족(275/291 전체 대조)",
                    "부호 인지 기록표 — 작성됨(블록 X, 이후 블록 AB·AH 가 append)",
                    "Holm ⑧ RQ-int — 미확보(R3 → GIN → λ·ρ 진단이 선행)",
                    "개봉 별도 승인·시점 — 미정",
                ],
                "note": "이 점검을 통과해도 개봉 허가가 아니다.",
            },
            "verdict": "PASS" if not blocking else "FAIL",
            "blocking_findings": blocking,
        }
        by_dir = {}
        for k in snap_end:
            sd = sealed_dir_of(k)
            e = by_dir.setdefault(sd, {"n_files": 0, "n_access_log": 0})
            if k.endswith("/access.log"):
                e["n_access_log"] += 1
            else:
                e["n_files"] += 1
        audit["live_inventory"]["by_directory"] = dict(sorted(by_dir.items()))

        scan_audit = V1.defensive_scan(audit)
        public = {
            "_scope": "공개 — 판정·개수·해시 대조 건수만. 지표·부호 값·λ·Δ·CI·p 는 없다.",
            "ts_kst": audit["ts_kst"],
            "block": BLOCK,
            "instruction": INSTRUCTION,
            "gates": {
                "G0_v2_pass": g0["pass"],
                "G0_v2_n_rows": g0["n_rows"],
                "G0_v2_pass_at_exit": g0_end["pass"],
                "G_HOLM_n_labels": holm["n_labels"],
                "G_IDLE_B_competitors": 0,
                "status_sidecar_transition_pass": trans["pass"],
                "sealed_artifacts_start": base["observed"]["n_artifacts"],
                "sealed_total_start": base["observed"]["n_total"],
                "sealed_directories": base["observed"]["n_sealed_directories"],
                "sealed_snapshot_start_equals_exit": sealed_same,
            },
            "sealing_completeness": {
                "n_expected": len(expected_all),
                "n_live_artifacts": len(live_art),
                "n_missing": len(missing),
                "n_unexpected": len(unexpected),
                "n_added_since_block_X": len(added),
                "n_removed_since_block_X": len(removed),
                "n_hashed": hashes["n_sealed_artifacts_hashed"],
                "n_files_with_recorded_hash": hashes["n_files_with_recorded_hash"],
                "n_hash_compared": hashes["n_compared"],
                "n_hash_mismatch": hashes["n_mismatch"],
                "n_changed_since_block_X": len(hashes["changed_since_block_X"]),
                "n_crosscheck_groups": len(mfs),
                "model_fold_seed_all_set_equal": all(x["set_equal"] for x in mfs),
                "n_access_log_files": opened["n_access_log_files"],
                "n_access_log_entries": opened["n_access_log_entries"],
                "n_access_log_entries_new_since_block_X": opened["delta_since_block_X"]["n_new_entries"],
                "n_unattributed_new_entries": len(opened["delta_since_block_X"]["unattributed"]),
                "n_human_exposure_true": opened["n_human_exposure_true"],
                "n_open_sealed_substring": opened["n_open_sealed_substring"],
                "access_log_types": sorted(opened["type_distribution"]),
                "n_known_failure_restart_events": frl["n_known_events"],
                "verdict": audit["verdict"],
            },
            "out_of_scope_sealed_copies": {
                "n_copy_files": oog["n_copy_files"],
                "n_copy_pairs": oog["n_copy_pairs"],
                "n_sealed_named_dirs": len(oog["sealed_named_dirs"]),
                "n_files_in_sealed_named_dirs": oog["n_files_in_sealed_named_dirs"],
                "copy_access_log_entries": oog["backup_access_log_check"]["n_entries"],
                "copy_access_log_human_exposure_true":
                    oog["backup_access_log_check"]["n_human_exposure_true"],
                "checksum_manifest_verified": oog["backup_sha256sums_check"]["n_ok"],
                "checksum_manifest_failed": oog["backup_sha256sums_check"]["n_bad"],
                "verdict": oog["verdict"],
                "disposition": "보존 + 문서화 (사용자 확정 2026-09-10) — 경로는 감사 산출물과 "
                               "docs/33 항목54 에만 적는다.",
            },
            "sign_disclosure_consistency": {
                "n_first_look_entries": sign["n_first_look_entries"],
                "n_sign_known": sign["n_sign_known"],
                "matrix_n_rows": sign["matrix_len_rows"],
                "new_sign_known_contrasts_since_block_X":
                    sign["new_sign_known_contrasts_since_block_X"],
                "regenerated": False,
            },
            "ckpt_projection_files": len(CKPT_FILES),
            "not_performed": {
                "unblinding_performed": False,
                "open_sealed_calls": 0,
                "emit_sign_calls": 0,
                "decision_py_calls": 0,
                "sealed_value_reads": 0,
                "model_training": 0,
                "network": 0,
                "git_commit": 0,
                "git_push": 0,
                "files_added_to_sealed": 0,
                "backup_disposition": 0,
            },
            "not_performed_note": "sealed_value_reads = 봉인 산출물을 역직렬화해 지표·배열 "
                                  "값을 적재한 횟수. checkpoint.jsonl 의 키 허용목록 투영은 "
                                  "여기 세지 않고 ckpt_projection_files 로 따로 적는다.",
            "artifacts": {},
            "defensive_scan": {
                "n_forbidden_keys": 0,
                "n_value_scan_hits": 0,
                "method": "★ 키 이름이 아니라 값으로 판정 (V1.defensive_scan).",
            },
        }
        scan_public = V1.defensive_scan(public)
        public["defensive_scan"]["n_forbidden_keys"] = scan_public["n_forbidden_keys"]
        public["defensive_scan"]["n_value_scan_hits"] = scan_public["n_value_scan_hits"]
        if scan_public["n_forbidden_keys"] or scan_public["n_value_scan_hits"]:
            blocking.append(f"공개요약 방어 스캔 위반 — 키 {scan_public['n_forbidden_keys']} · "
                            f"값 {scan_public['n_value_scan_hits']}")
            audit["blocking_findings"] = blocking
            audit["verdict"] = "FAIL"
        audit["defensive_scan_self"] = {
            "n_forbidden_keys": scan_audit["n_forbidden_keys"],
            "forbidden_keys": scan_audit["forbidden_keys"],
            "n_value_scan_hits": scan_audit["n_value_scan_hits"],
            "value_scan_kinds": sorted({h["kind"] for h in scan_audit["value_scan_hits"]}),
        }

        V1.logln(f"[판정] {audit['verdict']} · blocking {len(audit['blocking_findings'])}건")
        if not write:
            V1.logln("[--dry-run] 파일 쓰기 0 — 예측값 전건 일치. --write 로 진행 가능.")
            return 0 if audit["verdict"] == "PASS" else 3

        # ── ⑦ 감사 v2 JSON (FAIL 이어도 증거로 쓴다) ─────────────────────
        audit_sha = V1.dump_json(AUDIT_V2_JSON, audit)
        V1.logln(f"[산출] {V1.rel(AUDIT_V2_JSON)} sha16={audit_sha[:16]}")
        if audit["verdict"] != "PASS":
            V1.logln("[중단] FAIL — 공개요약을 쓰지 않는다.")
            return 3

        # ── ⑧ PASS 일 때만 공개요약 ──────────────────────────────────────
        public["artifacts"] = {
            "sealing_completeness_audit_v2.json": audit_sha,
        }
        scan_public2 = V1.defensive_scan(public)
        if scan_public2["n_forbidden_keys"] or scan_public2["n_value_scan_hits"]:
            V1.logln(f"[중단] 공개요약 방어 스캔 2차 위반 — 키 "
                     f"{scan_public2['n_forbidden_keys']} · 값 "
                     f"{scan_public2['n_value_scan_hits']} → 공개요약 미작성 "
                     f"(감사 v2 JSON 은 다시 쓰지 않는다)")
            return 3
        public["defensive_scan"]["n_forbidden_keys"] = scan_public2["n_forbidden_keys"]
        public["defensive_scan"]["n_value_scan_hits"] = scan_public2["n_value_scan_hits"]
        public_sha = V1.dump_json(PUBLIC_V2_JSON, public)
        V1.logln(f"[산출] {V1.rel(PUBLIC_V2_JSON)} sha16={public_sha[:16]}")
        return 0


def parse_args(argv):
    ap = argparse.ArgumentParser(description="블록 AO — 봉인 완전성 점검 v2 (275/291 전체 대조)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="게이트·대조·예측값 검사만 — 파일 쓰기 0 · 1회성 가드 미적용")
    g.add_argument("--write", action="store_true",
                   help="같은 코드 경로 + 1회성 가드 + 산출물 기록")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.write:
        if os.path.exists(AUDIT_V2_JSON) or os.path.exists(PUBLIC_V2_JSON):
            print(f"[중단] v2 산출물이 이미 존재한다 — 1회성 블록. "
                  f"{V1.rel(AUDIT_V2_JSON)} / {V1.rel(PUBLIC_V2_JSON)}", file=sys.stderr)
            sys.exit(2)
    sys.exit(run(write=bool(args.write)))


if __name__ == "__main__":
    main()
