#!/usr/bin/env python3
"""null_partition_freeze.py — 블록 A(A-0·A-3·A-4): null 교환 단위 partition **동결** + 원소 수 정정.

⚠️ 재계산 0 · 네트워크 0 · 모델 학습 0 · p 계산 0 · sealed 값 사람 노출 0.

수행
  A-0  게이트0(동결 hash) + rep1 `_sealed/` 3종 sha256 불변 확인
  A-3  family partition CSV 2종 동결
         11_null_family_partition.csv      (primary — family_id 사전순 최소 tie-break)
         11b_null_family_partition_ALT.csv (ALT — 이중소속 표적 permutation 제외)
       assert: 표적 1,191 · family 42 · tie-break 14 · 고정 13 · 교환가능 1,178
               (= `experiments/runs/v3_null_probe/_precheck.json` family_report 와 완전 일치)
  A-4  `oof_M2b.npz` **shape만** machine_read(값 미로드 — zip 내 .npy 헤더만 판독) → 404,040 확인

산출: `experiments/runs/v3_null_partition_freeze/partition_freeze.json` (공개 — 개수·해시만)

실행: .venv/bin/python3 v3_Multimodal/src/null_partition_freeze.py
"""
from __future__ import annotations

import os
import sys
import json
import zipfile
import hashlib
import platform
from datetime import datetime, timezone, timedelta

import numpy as np
import numpy.lib.format as npformat
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from ladder_confirmatory import load_frozen                     # noqa: E402
from confirmatory_oof_rep1 import gate0_verify, sha256_file     # noqa: E402
from null_timing_probe import (                                 # noqa: E402
    load_target_structure, FAMILY_TIEBREAK_RULE, REP1_SEALED, REP1_ACCESS_LOG,
)

KST = timezone(timedelta(hours=9))

TM = os.path.join(ROOT, "data", "processed", "target_mapping")
F_PARTITION = os.path.join(TM, "11_null_family_partition.csv")
F_PARTITION_ALT = os.path.join(TM, "11b_null_family_partition_ALT.csv")
PROBE_PRECHECK = os.path.join(ROOT, "experiments", "runs", "v3_null_probe", "_precheck.json")
RUN_DIR = os.path.join(ROOT, "experiments", "runs", "v3_null_partition_freeze")

# rep1 sealed 3종 (docs/45 §5 대장 기록값 — 블록 A 시작·종료 시 확인)
REP1_SEALED_EXPECT = {
    "metrics_full.json": "8722a4e1c52d2eae5cbbebf6b5a5ff5cb145dd591ea5648731d7c481ed15c1b8",
    "oof_M1b.npz": "b2a61ba846eead5f66bc89bc22275ea3fe35fee950930fbdc38f07ad7e4a3f1d",
    "oof_M2b.npz": "350fa12fac84ef4ca1355d256665c333d9cd8ca34de257e7321aefa36d8a3260",
}
# A-4: 병기된 식 1092 × 370 = 404,040 (최초 기재 403,040 은 오기 — 자기반증)
EXPECT_OOF_SHAPE = (1092, 370)

_LOG = []


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def logln(m):
    line = f"{now_kst()} | {m}"
    print(line, flush=True)
    _LOG.append(line)


def flush_log():
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "run.log"), "a") as f:
        f.write("\n".join(_LOG) + "\n")
    _LOG.clear()


def native(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=native)
    return path


# ═══════════════════════════════════════════════════════════════════════════
# A-0 — 게이트0 + rep1 sealed 불변
# ═══════════════════════════════════════════════════════════════════════════
def rep1_sealed_unchanged(tag):
    live = {fn: sha256_file(os.path.join(REP1_SEALED, fn)) for fn in REP1_SEALED_EXPECT}
    ok = {fn: (live[fn] == REP1_SEALED_EXPECT[fn]) for fn in REP1_SEALED_EXPECT}
    assert all(ok.values()), f"[{tag}] rep1 _sealed sha256 불일치: {[k for k, v in ok.items() if not v]}"
    logln(f"[{tag}] rep1 _sealed 3종 sha256 불변 확인 — "
          + " · ".join(f"{k}={v[:16]}" for k, v in sorted(live.items())))
    return {"all_match": True, "sha256": live}


# ═══════════════════════════════════════════════════════════════════════════
# A-3 — partition CSV 2종
# ═══════════════════════════════════════════════════════════════════════════
def build_partition_tables(ts, fam_src_counts):
    """primary partition (tie-break = family_id 문자열 사전순 최소) 테이블."""
    fam_of = {}
    for fam, members in ts["targets_by_family"].items():
        for u in members:
            fam_of[u] = fam
    fam_size = {fam: len(m) for fam, m in ts["targets_by_family"].items()}

    rows = []
    for u in ts["unique_targets"]:
        fam = fam_of[u]
        n_src = int(fam_src_counts.get(u, 0))
        rows.append({
            "target_id": u,
            "family_id_assigned": fam,
            "n_families_in_source": n_src,
            "tiebreak_applied": int(n_src > 1),
            "exchangeable": int(fam_size[fam] >= 3),
        })
    return pd.DataFrame(rows), fam_of, fam_size


def build_partition_alt(df_primary):
    """ALT(사전지정 민감도): 이중소속(n_families_in_source>1) 표적을 permutation에서 **제외**.

    제외 후 남은 표적으로 family 크기를 재계산 → |family|≥3 인 family만 교환 가능."""
    alt = df_primary.copy()
    alt["excluded"] = (alt["n_families_in_source"] > 1).astype(int)
    keep = alt[alt["excluded"] == 0]
    size_after = keep["family_id_assigned"].value_counts().to_dict()
    alt["exchangeable"] = [
        0 if ex else int(size_after.get(f, 0) >= 3)
        for ex, f in zip(alt["excluded"], alt["family_id_assigned"])
    ]
    return alt, size_after


# ═══════════════════════════════════════════════════════════════════════════
# A-4 — sealed npz shape만 판독 (zip 내 .npy 헤더만 — 값 미로드)
# ═══════════════════════════════════════════════════════════════════════════
def sealed_oof_shape_header_only(npz_path, member="oof.npy"):
    """npz(zip) 안 .npy 의 **헤더만** 읽어 shape 반환. 배열 데이터는 읽지 않는다."""
    with zipfile.ZipFile(npz_path) as zf:
        names = zf.namelist()
        assert member in names, f"{member} 부재 (members={names})"
        with zf.open(member) as f:
            version = npformat.read_magic(f)
            # numpy 2.x: 버전별 공개 헤더 판독기(비공개 _read_array_header 제거됨)
            reader = {(1, 0): npformat.read_array_header_1_0,
                      (2, 0): npformat.read_array_header_2_0}[tuple(version)]
            shape, fortran, dtype = reader(f)
    return tuple(int(x) for x in shape), str(dtype), bool(fortran), names


def log_machine_read(path_rel, purpose):
    rec = {"ts_kst": now_kst(), "type": "machine_read", "purpose": purpose,
           "human_exposure": False, "path": path_rel, "actor": "vscode-claude",
           "step": "블록 A-4 원소 수 정정",
           "note": "npz 내부 .npy **헤더만** 판독(shape·dtype). 배열 값 미로드·미출력. open_sealed 아님."}
    with open(REP1_ACCESS_LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def access_log_summary():
    recs = []
    if os.path.exists(REP1_ACCESS_LOG):
        with open(REP1_ACCESS_LOG) as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    types = {}
    for r in recs:
        types[r.get("type")] = types.get(r.get("type"), 0) + 1
    return {"n_entries": len(recs), "by_type": types,
            "n_open_sealed": int(types.get("open_sealed", 0)),
            "sealed_human_read": bool(types.get("open_sealed", 0) > 0),
            "all_human_exposure_false": all(r.get("human_exposure") is False for r in recs)}


# ═══════════════════════════════════════════════════════════════════════════
def main():
    t_start = now_kst()
    os.makedirs(RUN_DIR, exist_ok=True)
    logln("=" * 78)
    logln("[블록 A] A-0 게이트0 · A-3 partition 동결 · A-4 원소 수 정정 — 재계산 0 · 네트워크 0 · p 0")

    # ── A-0 ────────────────────────────────────────────────────────────────
    g0 = gate0_verify()
    sealed_start = rep1_sealed_unchanged("A-0 시작")

    # ── A-3 ────────────────────────────────────────────────────────────────
    d = load_frozen()
    cid_order = d["cid_order"]
    ts = load_target_structure(cid_order)

    # 소스 CSV에서 표적별 family 개수(원본 다중소속 여부) — load_target_structure 와 동일 판독
    fbio = pd.read_csv(os.path.join(TM, "10_target_family_biological.csv"))
    src = {}
    for u, fid in zip(fbio["uniprot"], fbio["family_id"]):
        if isinstance(u, str) and u:
            src.setdefault(u, set()).add(str(fid))
    fam_src_counts = {u: len(src.get(u, ())) for u in ts["unique_targets"]}

    df, fam_of, fam_size = build_partition_tables(ts, fam_src_counts)
    alt, alt_size_after = build_partition_alt(df)

    n_targets = len(df)
    n_families = df["family_id_assigned"].nunique()
    n_tiebreak = int(df["tiebreak_applied"].sum())
    n_exch = int(df["exchangeable"].sum())
    n_fixed = n_targets - n_exch
    n_fixed_families = int(sum(1 for f, s in fam_size.items() if s <= 2))
    n_singleton_families = int(sum(1 for f, s in fam_size.items() if s == 1))
    n_size2_families = int(sum(1 for f, s in fam_size.items() if s == 2))

    pre = json.load(open(PROBE_PRECHECK))
    fr = pre["family_report"]
    checks = {
        "n_targets": (n_targets, 1191, fr["n_targets"]),
        "n_families": (n_families, 42, fr["n_families"]),
        "n_tiebreak_applied": (n_tiebreak, 14, pre["target_structure"]["n_targets_multi_family_in_source"]),
        "n_fixed_targets": (n_fixed, 13, fr["n_fixed_targets"]),
        "n_exchangeable_targets": (n_exch, 1178, fr["n_exchangeable_targets"]),
        "n_fixed_families": (n_fixed_families, 11, fr["n_fixed_families_singleton_or_size2"]),
        "n_exchangeable_families": (n_families - n_fixed_families, 31, fr["n_exchangeable_families"]),
    }
    assert_report = {}
    for k, (live, spec, probe) in checks.items():
        ok = (live == spec == probe)
        assert_report[k] = {"live": live, "spec_expected": spec, "probe_precheck": probe, "match": ok}
        if not ok:
            logln(f"[A-3] ❌ assert FAIL {k}: live={live} spec={spec} probe={probe} — 중단")
            flush_log()
            sys.exit(4)
    # 파생: 고정 13 = 싱글톤 9 + size-2 family 2개(4 표적)
    assert n_singleton_families * 1 + n_size2_families * 2 == n_fixed, "고정 표적 분해 불일치"
    logln(f"[A-3] partition assert PASS — 표적 {n_targets} · family {n_families} · tie-break {n_tiebreak} · "
          f"고정 {n_fixed}(싱글톤 family {n_singleton_families} + size-2 family {n_size2_families}×2) · "
          f"교환가능 {n_exch} — 프로브 _precheck.json family_report 와 완전 일치")

    df.to_csv(F_PARTITION, index=False)
    alt.to_csv(F_PARTITION_ALT, index=False)
    sha_primary = sha256_file(F_PARTITION)
    sha_alt = sha256_file(F_PARTITION_ALT)
    alt_excluded = int(alt["excluded"].sum())
    alt_exch = int(alt["exchangeable"].sum())
    logln(f"[A-3] 저장 11_null_family_partition.csv sha256={sha_primary[:16]} · "
          f"11b_null_family_partition_ALT.csv sha256={sha_alt[:16]} "
          f"(ALT 제외 {alt_excluded} · ALT 교환가능 {alt_exch})")

    # ── A-4 ────────────────────────────────────────────────────────────────
    m2b_path = os.path.join(REP1_SEALED, "oof_M2b.npz")
    log_machine_read(os.path.relpath(m2b_path, ROOT), "shape only")
    shape, dtype, fortran, members = sealed_oof_shape_header_only(m2b_path)
    n_elem = int(np.prod(shape))
    shape_ok = (shape == EXPECT_OOF_SHAPE)
    if not shape_ok:
        logln(f"[A-4] ❌ shape {shape} != 기대 {EXPECT_OOF_SHAPE} — **정정하지 말고 중단**(지시)")
        flush_log()
        sys.exit(5)
    logln(f"[A-4] sealed oof_M2b.npz shape={shape} dtype={dtype} → 원소 수 {n_elem:,} "
          f"(헤더만 판독 · 값 미로드) — 기대 404,040 일치")

    acc = access_log_summary()
    logln(f"[A-4] rep1 _sealed/access.log — 총 {acc['n_entries']}건 · open_sealed {acc['n_open_sealed']}건 · "
          f"human_exposure 전부 false={acc['all_human_exposure_false']} → sealed_human_read={acc['sealed_human_read']}")

    sealed_end = rep1_sealed_unchanged("A-0/A-4 종료")

    out = {
        "_scope": "블록 A(A-0·A-3·A-4) — 결과-독립 계측·구조치만. AP·Δ·p 없음.",
        "ts_kst_start": t_start, "ts_kst_end": now_kst(),
        "gate0": g0,
        "rep1_sealed_unchanged": {"at_start": sealed_start, "at_end": sealed_end},
        "partition_primary": {
            "path": os.path.relpath(F_PARTITION, ROOT),
            "sha256": sha_primary,
            "tiebreak_rule": FAMILY_TIEBREAK_RULE,
            "columns": list(df.columns),
            "n_targets": n_targets, "n_families": n_families,
            "n_tiebreak_applied": n_tiebreak,
            "n_fixed_targets": n_fixed, "n_exchangeable_targets": n_exch,
            "n_fixed_families_singleton_or_size2": n_fixed_families,
            "n_singleton_families": n_singleton_families,
            "n_size2_families": n_size2_families,
            "n_exchangeable_families": n_families - n_fixed_families,
            "fixed_target_frac": float(n_fixed / n_targets),
            "exchangeable_target_frac": float(n_exch / n_targets),
        },
        "partition_alt": {
            "path": os.path.relpath(F_PARTITION_ALT, ROOT),
            "sha256": sha_alt,
            "rule": "이중소속(n_families_in_source>1) 표적을 permutation에서 제외 후 family 크기 재계산",
            "columns": list(alt.columns),
            "n_excluded": alt_excluded,
            "n_exchangeable_targets": alt_exch,
            "n_fixed_or_excluded": n_targets - alt_exch,
            "enters_p_emp": False,
            "spec": {"B_family_ALT": 100, "B_global_ALT": 10, "paired_same_seed_reuse": True,
                     "discordant_rule": "양 규칙 full-B 후 보수적(큰) p_emp 채택"},
        },
        "assert_vs_probe_precheck": assert_report,
        "sealed_shape_check": {
            "path": os.path.relpath(m2b_path, ROOT),
            "read_mode": "zip 내 .npy 헤더만(값 미로드)",
            "npz_members": members,
            "shape": list(shape), "dtype": dtype, "fortran_order": fortran,
            "n_elements": n_elem,
            "expected_n_elements": 404040,
            "match": shape_ok,
            "correction": ("최초 기재 '불일치 원소 0/403,040' 은 오기. 병기된 식 1092×370 = 404,040 이므로 "
                           "자기반증. 실측 shape (1092, 370) 재확인 → 정정값 0/404,040."),
        },
        "sealed_access_log": acc,
        "integrity": {"network_calls": 0, "models_trained": 0, "raw_data_modified": False,
                      "docs30_modified": False, "sealed_values_human_read": False,
                      "empirical_p_called": False, "bootstrap_or_signflip": False,
                      "ladder_freeze_modified": False, "sap_modules_modified": False,
                      "git_commit": False},
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "platform": platform.platform()},
    }
    dump_json(os.path.join(RUN_DIR, "partition_freeze.json"), out)
    logln("[블록 A] A-0·A-3·A-4 완료 — 문서/원장 반영은 별도 단계")
    flush_log()
    print("\n=== 블록 A (A-0·A-3·A-4) 요약 ===")
    print(f"gate0_pass={g0['gate0_pass']} · rep1 sealed 불변=True")
    print(f"partition sha256: primary={sha_primary} ALT={sha_alt}")
    print(f"assert: " + " · ".join(f"{k}={v['live']}({'OK' if v['match'] else 'FAIL'})"
                                   for k, v in assert_report.items()))
    print(f"sealed oof_M2b shape={shape} n_elements={n_elem:,} (기대 404,040 일치={shape_ok})")


if __name__ == "__main__":
    main()
