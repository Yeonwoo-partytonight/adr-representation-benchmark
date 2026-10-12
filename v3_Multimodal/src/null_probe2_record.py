#!/usr/bin/env python3
"""null_probe2_record.py — 블록 D-6 문서 기입 (docs/33 · docs/45 · ledger.json).

규칙(블록 D 전용):
  · 파이썬 파일 쓰기만 사용. **heredoc 금지**.
  · 기입 후 **재판독 라운드트립 assert** — 백틱 수 · 기대 부분문자열 전수 확인.
  · 수치는 전부 `compute_public.json` 에서 읽어 삽입(손입력 0).
  · AP·Δ·p 수치 없음(측정치·해시·PASS/FAIL만).

블록 E-2 수정:
  · `docs/33` 세부 항목번호 **"16." 하드코딩 제거** → `doc_numbering.next_item_number()`
    로 문서를 실제 판독해 `^\\d+\\. \\*\\*` 최대 번호 + 1 을 계산한다.
  · `docs/45`·`ledger.json` 의 상호참조 문자열도 **같은 계산값**을 쓴다.
  · 기입 후 **중복 번호 검출 assert** 를 수행한다.
  · `compute_lock` 배타 락(`role="recorder"`)을 적용한다.

실행: .venv/bin/python3 v3_Multimodal/src/null_probe2_record.py
"""
from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KST = timezone(timedelta(hours=9))

sys.path.insert(0, HERE)
from compute_lock import ComputeLock                                   # noqa: E402
from doc_numbering import (assert_no_duplicate_item_numbers,           # noqa: E402
                           assert_number_written_once, crossref_label,
                           next_item_number)

PUB = os.path.join(ROOT, "experiments", "runs", "v3_null_probe2_compute", "compute_public.json")
DOC33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
DOC45 = os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")
LEDGER = os.path.join(ROOT, "experiments", "provenance", "ledger.json")


def now_kst():
    return datetime.now(KST)


def roundtrip_assert(path, expect_substrings, expect_backticks_added, before_text):
    """재판독 라운드트립 — 파일을 다시 읽어 기대 부분문자열 전수 + 백틱 증가분을 확인."""
    with open(path, encoding="utf-8") as f:
        after = f.read()
    missing = [s for s in expect_substrings if s not in after]
    assert not missing, f"[roundtrip FAIL] {os.path.relpath(path, ROOT)} 누락: {missing[:3]}"
    added = after.count("`") - before_text.count("`")
    assert added == expect_backticks_added, \
        (f"[roundtrip FAIL] {os.path.relpath(path, ROOT)} 백틱 증가 {added} != {expect_backticks_added} "
         f"(인용 파손 가능)")
    assert after.startswith(before_text), \
        f"[roundtrip FAIL] {os.path.relpath(path, ROOT)} 기존 내용 변경됨 (append-only 위반)"
    return {"file": os.path.relpath(path, ROOT), "backticks_added": added,
            "substrings_checked": len(expect_substrings), "pass": True}


def main():
    pub = json.load(open(PUB, encoding="utf-8"))
    ts = now_kst()
    ts_date = ts.strftime("%Y-%m-%d")
    ts_kst = ts.strftime("%Y-%m-%d %H:%M KST")

    d1 = pub["D1_true_cpu_time"]
    d2 = pub["D2_config_sweep"]
    gate = pub["D2_bitwise_gate"]
    d3 = pub["D3_worker_sweep"]
    g1 = pub["D3_G1_concurrency_invariance"]
    d4 = pub["D4_full_verification"]
    rec = pub["D5_recommendation"]
    hw = pub["hardware"]

    cfg_best = d3["cfg_best"]
    w_best = d3["w_best"]
    best_row = [c for c in d2 if c["name"] == cfg_best][0]
    speedup = d2[0]["wall_s"] / best_row["wall_s"]
    decay_pct = d4["thermal"]["median_decay_frac"] * 100
    proxy_err_pct = d4["proxy_check"]["error_frac"] * 100
    over7 = rec["over_7_days"]
    days = rec["expected_total_wall_days_thermal"]
    verdict_kr = "**Mac 단독 부적합**" if over7 else "**Mac 단독 실행 가능**"

    cfg_tbl = " · ".join(
        f"{c['name']}({c['label']}) wall {c['wall_s']:.0f}s/CPU {c['cpu_s']:.0f}s"
        f"/비트동일={c['bitwise_identical_to_A']}" for c in d2)
    excl = gate["excluded_configs"] or "없음"

    # ── docs/33 ────────────────────────────────────────────────────────────
    with open(DOC33, encoding="utf-8") as f:
        b33 = f.read()

    # E-2: 항목번호를 문서에서 실제 판독해 계산(하드코딩 금지).
    #      docs/45·ledger 의 상호참조 문자열도 동일 계산값을 쓴다.
    item_no = next_item_number(b33)
    xref = crossref_label(b33, item_no)
    item_head = f"{item_no}. **§13-4 병렬 실행 구성 확정 (블록 D — 측정 전용)**"
    print(f"[번호계산] docs/33 다음 항목번호 = {item_no} · 상호참조 = {xref}")

    days_txt = f"{days:.2f}일" if days is not None else "산출 불가"
    e33 = f"""
- **{ts_kst} | §13-4 **병렬 실행 구성 확정**(블록 D 측정 전용) — 구성 **{cfg_best}**(`MultiOutputClassifier(n_jobs={best_row['moc_n_jobs']})` / `RandomForestClassifier(n_jobs={best_row['rf_n_jobs']})`) × **프로세스 워커 {w_best}**. 예측 배열 **0-diff 증명 3종**(D-2 구성 간 sha256 일치 · D-3 G1 워커수 불변 · D-4 전량 identity 재확인) 첨부. 워커 수 스윕은 **`n_estimators=60` 타이밍 프록시**로 측정했음을 정직 고지 | 프로브1 실측 15.6일(단일 프로세스 순차)은 §13-4 본런에 비현실적. `ladder_freeze.json`(sha16 `{pub['ladder_freeze_sha16']}`)은 **바이트 무수정**이며 병렬 인자만 메모리상 복사본에서 override — 이는 통계적 비-파라미터이나 **무영향을 측정으로 증명한 구성만** 채택한다는 항목14 규칙을 그대로 이행 | 확증 조회 = N (`sealed_human_read=false`, `open_sealed` 0건, `empirical_p` 미호출, p 미계산, `T_obs` 비교 없음)**

### 세부 (근거 추적)

{item_head}:
   - **하드웨어 실측**: P코어 {hw['performance_cores']} · E코어 {hw['efficiency_cores']} · logical {hw['logical']} · RAM {hw['ram_bytes'] / 2**30:.0f}GiB(예산 {hw['ram_budget_gib']:.1f}GiB). 전원 = AC 연결 · 저전력 모드 해제(`powermode=0`) · `caffeinate -dimsu` 하에서 측정.
   - **D-1 실효 병렬도 정정**: 구성 A(현행 `n_jobs=-1`)의 fold 단가 = wall {d1['wall_s']:.1f}s / **진짜 CPU-시간 {d1['cpu_s']:.1f}s** → 실효 병렬도 **{d1['effective_parallelism_cpu_over_wall']:.2f}**(logical {hw['logical']} 대비 {d1['efficiency_vs_logical_18'] * 100:.0f}% · P코어 {hw['performance_cores']} 대비 {d1['efficiency_vs_p_cores_6'] * 100:.0f}%). **정정**: 프로브1 기록의 "374시간"은 18스레드 **wall-clock**이며 CPU-시간이 아니다. 재산정 총 CPU-시간 = **{d1['total_cpu_hours_A']:.0f}h**, 총 wall = **{d1['total_wall_hours_A']:.0f}h({d1['total_wall_days_A']:.1f}일)**.
   - **D-2 병렬축 스윕(각 구성 1 fold · 300 trees · identity permutation)**: {cfg_tbl}. **비트동일 게이트** = 예측 배열 sha256 기준값 `{gate['reference_sha256'][:16]}`(구성 A, §13-3 sealed 와 이미 0-diff) 대비 전 구성 일치 = **{gate['all_identical']}**, 제외 구성 = {excl}. 최속 = **{cfg_best}**(구성 A 대비 {speedup:.2f}× 가속).
   - **D-3 워커 수 스윕 — 타이밍 프록시 사용(정직 고지)**: 워커 {{1,3,6,9,12,18}} 스윕은 **`n_estimators={d3['n_estimators_proxy']}` 프록시**로 측정했다(동결값 {d3['frozen_n_estimators']} 아님). 프록시 산출은 `_proxy/` 에 격리되고 `NOT_AN_ANALYSIS_RESULT` 플래그를 달았으며 **OOF 미저장 · 어떤 분석·판정·null 분포에도 미투입**이다. 워커당 스레드 환경변수(`OMP_NUM_THREADS` 등 5종)는 배정 코어 수로 명시 고정, multiprocessing 은 `spawn`. **G1 동시성 불변성** = 같은 seed 예측 sha256 이 워커 수와 무관하게 동일 = **{g1['pass']}**. RAM 게이트(합계 peak RSS ≤ {hw['ram_budget_gib']:.1f}GiB) 탈락 워커 수 = {pub['D3_ram_gate']['excluded_workers'] or '없음'}. 선정 **W_BEST = {w_best}**.
   - **D-4 전량 재확인(300 trees)**: (구성 {cfg_best}, 워커 {w_best})로 permutation 1회 완주(5 fold). 프록시 예측 대비 **오차 {proxy_err_pct:+.1f}%**(허용 ±{d4['proxy_check']['tolerance'] * 100:.0f}% · 통과 = {d4['proxy_check']['proxy_accepted']}) → 프록시는 상대 비교 용도로 타당. **0-diff 재확인**: 전량 identity permutation 의 fold 0 예측 sha256 `{d4['identity_fold0_sha256'][:16]}` = D-2 구성 A 기준값과 **비트 동일 {d4['zero_diff_vs_d2_configA']}**. **지속부하 열 감쇠**: {d4['thermal']['sustained_load_s']:.0f}s 연속 부하(하한 {d4['thermal']['sustained_min_s']:.0f}s 충족 = {d4['thermal']['sustained_ok']})에서 첫 fold→마지막 fold 감쇠율 중앙값 **{decay_pct:+.1f}%** — 총 wall 추정에 반영했다.
   - **D-5 판정**: 권장 = 구성 **{cfg_best}** × 워커 **{w_best}**, 2,000 permutation 예상 총 wall(열감쇠 반영) **{days_txt}** → 7일 초과 = **{over7}** → {verdict_kr}.
   - **미실행**: `empirical_p` 호출 · p 계산 · `T_obs` 비교 · null 분포 · bootstrap · sign-flip · SESOI/TOST · 성공판정 · `ladder_freeze.json` 수정 · §13-4 본런 · sealed 값 사람 열람 · 네트워크 · `data/raw/` 변경 · git commit.

---
"""
    with open(DOC33, "a", encoding="utf-8") as f:
        f.write(e33)
    r33 = roundtrip_assert(
        DOC33,
        [item_head,
         "`ladder_freeze.json`", "`NOT_AN_ANALYSIS_RESULT`", "`OMP_NUM_THREADS`",
         f"`n_estimators={d3['n_estimators_proxy']}` 프록시",
         gate["reference_sha256"][:16], d4["identity_fold0_sha256"][:16],
         "확증 조회 = N", "타이밍 프록시 사용(정직 고지)"],
        e33.count("`"), b33)
    print(f"[docs/33] roundtrip PASS — {r33}")

    # E-2: 중복 번호 검출 assert — 방금 쓴 번호가 정확히 1회여야 하고,
    #      문서 전체에도 (기존 허용 중복 외) 중복이 없어야 한다.
    with open(DOC33, encoding="utf-8") as f:
        a33 = f.read()
    print(f"[번호중복] {assert_number_written_once(b33, a33, item_no)}")
    print(f"[번호중복] {assert_no_duplicate_item_numbers(DOC33)}")

    # ── docs/45 §2 타임라인 ─────────────────────────────────────────────────
    with open(DOC45, encoding="utf-8") as f:
        b45 = f.read()
    row = (f"| {ts_kst} | §13-4 **블록 D(측정 전용)** 병렬 구성 확정 — 구성 **{cfg_best}**"
           f"(MOC n_jobs={best_row['moc_n_jobs']} / RF n_jobs={best_row['rf_n_jobs']}) × 워커 **{w_best}**. "
           f"실효 병렬도 **{d1['effective_parallelism_cpu_over_wall']:.2f}**"
           f"(logical {hw['logical']} 대비 {d1['efficiency_vs_logical_18'] * 100:.0f}%) — "
           f"프로브1 '374시간'은 wall-clock이며 CPU-시간 아님을 실측 정정(총 CPU {d1['total_cpu_hours_A']:.0f}h). "
           f"비트동일 게이트 전 구성 통과={gate['all_identical']}(제외 {excl}) · G1 워커수 불변={g1['pass']} · "
           f"전량 identity 0-diff={d4['zero_diff_vs_d2_configA']} · 열 감쇠 {decay_pct:+.1f}%. "
           f"워커 스윕은 `n_estimators={d3['n_estimators_proxy']}` **타이밍 프록시**(분석 미투입, `_proxy/` 격리, "
           f"오차 {proxy_err_pct:+.1f}%). 2,000 perm 예상 총 wall **{days_txt}** → 7일 초과={over7} → {verdict_kr}. "
           f"`ladder_freeze.json` sha16 `{pub['ladder_freeze_sha16']}` 불변 · 블록 C sealed "
           f"{pub['sealed_guard']['files']}종 sha256 불변={pub['sealed_guard']['unchanged']} "
           f"| vscode-claude | N (`empirical_p` 미호출·p 미계산·`T_obs` 비교 없음·`open_sealed` 0건) "
           f"| `experiments/runs/v3_null_probe2_compute/compute_public.json`, docs/33 {xref}, "
           f"ledger.json timeline |\n")
    anchor = "\n## 3. 동결 아티팩트 해시 원장"
    assert anchor in b45, "docs/45 §3 앵커 없음"
    n45 = b45.replace(anchor, row + anchor, 1)
    with open(DOC45, "w", encoding="utf-8") as f:
        f.write(n45)
    with open(DOC45, encoding="utf-8") as f:
        a45 = f.read()
    assert a45.count("`") == b45.count("`") + row.count("`"), "docs/45 백틱 수 불일치"
    for s in [f"구성 **{cfg_best}**", "타이밍 프록시", pub["ladder_freeze_sha16"],
              "`empirical_p` 미호출"]:
        assert s in a45, f"docs/45 누락: {s}"
    assert len(a45) == len(b45) + len(row), "docs/45 길이 불일치(기존 내용 변경 의심)"
    print(f"[docs/45] roundtrip PASS — 백틱 +{row.count('`')} · 1행 삽입")

    # ── ledger.json timeline append ────────────────────────────────────────
    led = json.load(open(LEDGER, encoding="utf-8"))
    n_before = len(led["timeline"])
    led["timeline"].append({
        "ts": ts_date, "ts_kst": ts_kst, "actor": "vscode-claude",
        "step": "§13-4 블록 D (병렬 구성 실측·확정 — 측정 전용)",
        "event": (
            f"Mac wall-clock 최적화 실측. (1) 실효 병렬도 {d1['effective_parallelism_cpu_over_wall']:.2f} "
            f"(cpu/wall; logical {hw['logical']} 대비 {d1['efficiency_vs_logical_18'] * 100:.0f}%, "
            f"P코어 {hw['performance_cores']} 대비 {d1['efficiency_vs_p_cores_6'] * 100:.0f}%) — "
            f"프로브1 '374시간'은 wall-clock이며 CPU-시간이 아님을 실측 정정(재산정 총 CPU "
            f"{d1['total_cpu_hours_A']:.0f}h / 총 wall {d1['total_wall_days_A']:.1f}일). "
            f"(2) 병렬축 5구성 스윕 — 비트동일 게이트 전 구성 통과={gate['all_identical']}, 제외={excl}, "
            f"최속=구성 {cfg_best}({speedup:.2f}× 가속). (3) 워커 스윕 {{1,3,6,9,12,18}}은 "
            f"n_estimators={d3['n_estimators_proxy']} **타이밍 프록시**로 측정(OOF 미저장·분석 미투입·"
            f"_proxy/ 격리·NOT_AN_ANALYSIS_RESULT) — G1 동시성 불변성={g1['pass']}, W_BEST={w_best}. "
            f"(4) 전량 300 trees 재확인 — 프록시 오차 {proxy_err_pct:+.1f}%, identity 0-diff="
            f"{d4['zero_diff_vs_d2_configA']}, 지속부하 {d4['thermal']['sustained_load_s']:.0f}s 열 감쇠 "
            f"{decay_pct:+.1f}%(총 wall 추정에 반영). (5) 권장 = 구성 {cfg_best} × 워커 {w_best}, "
            f"2,000 permutation 예상 총 wall {days_txt} → 7일 초과={over7} → "
            f"{verdict_kr.replace('**', '')}."),
        "artifacts": [
            "experiments/runs/v3_null_probe2_compute/compute_public.json",
            "experiments/runs/v3_null_probe2_compute/config.json",
            "experiments/runs/v3_null_probe2_compute/run.log",
            "experiments/runs/v3_null_probe2_compute/_proxy/worker_sweep_proxy.json (NOT_AN_ANALYSIS_RESULT)",
            "experiments/runs/v3_null_probe2_compute/_sealed/fold_pred_reference.npy",
            f"docs/33_prereg_deviation_log.md ({xref})",
            "docs/45_research_integrity_ledger.md §2",
        ],
        "zero_diff_proof_sha256": {
            "D2_reference_configA_fold0": gate["reference_sha256"],
            "D4_full_identity_fold0": d4["identity_fold0_sha256"],
            "D3_G1_invariant": g1["pass"],
        },
        "integrity": {
            "confirmatory_oof_accessed": False, "sealed_human_read": False,
            "empirical_p_called": False, "p_computed": False, "T_obs_compared": False,
            "ladder_freeze_modified": False,
            "ladder_freeze_sha16": pub["ladder_freeze_sha16"],
            "blockC_sealed_unchanged": pub["sealed_guard"]["unchanged"],
            "blockC_sealed_files": pub["sealed_guard"]["files"],
            "network_calls": 0, "raw_data_modified": False, "git_commit": False,
        },
        "timing_proxy_disclosure": {
            "used": True, "stage": "D-3 워커 수 스윕",
            "n_estimators_proxy": d3["n_estimators_proxy"],
            "frozen_n_estimators": d3["frozen_n_estimators"],
            "oof_saved": False, "enters_analysis": False,
            "reverified_full_in": "D-4", "error_vs_full_pct": proxy_err_pct,
        },
    })
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=2, ensure_ascii=False)
    rt = json.load(open(LEDGER, encoding="utf-8"))
    assert len(rt["timeline"]) == n_before + 1, "ledger timeline 길이 불일치"
    last = rt["timeline"][-1]
    assert last["ts"] == ts_date and last["ts_kst"] == ts_kst, "ts/ts_kst 병기 실패"
    assert last["integrity"]["empirical_p_called"] is False
    assert last["timing_proxy_disclosure"]["enters_analysis"] is False
    assert "타이밍 프록시" in last["event"]
    print(f"[ledger.json] roundtrip PASS — timeline {n_before} → {len(rt['timeline'])}")

    print("\n=== D-6 기록 완료 ===")
    print(f"  docs/33 {xref} · docs/45 §2 1행 · ledger.json timeline#{len(rt['timeline'])}")
    print(f"  권장 = 구성 {cfg_best} × 워커 {w_best} · 예상 {days_txt} · 7일 초과 = {over7}")


if __name__ == "__main__":
    with ComputeLock(script="null_probe2_record.py", role="recorder"):
        sys.exit(main())
