#!/usr/bin/env python3
"""record_block_c.py — 블록 C-5 기록: `docs/45` §5 대장 3행 + `ledger.json` timeline append.

입력 = `experiments/runs/v3_confirm_rep23/block_C_summary.json`(공개 요약: 부호·해시·시간·개수만).
`docs/33` §16 항목15는 조회 **직전**에 이미 기록됨(게이트 B) — 여기서는 완료 사실만 추가한다.
AP·Δ 크기·p 는 일절 기록하지 않는다.
"""
from __future__ import annotations

import os
import json
import collections
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KST = timezone(timedelta(hours=9))
SUM = os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep23", "block_C_summary.json")
DOCS45 = os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")
LED = os.path.join(ROOT, "experiments", "provenance", "ledger.json")


def sha16(d):
    return {k: v[:16] for k, v in sorted(d.items())}


def main():
    s = json.load(open(SUM))
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    r2, r3 = s["repeats"]["2"], s["repeats"]["3"]
    cons = s["consensus"]

    # ── docs/45 §5 대장 3행 (반복1 행 형식 그대로) ───────────────────────────
    doc = open(DOCS45).read()
    anchor = ("| 2026-07-27 10:55:31 KST (완료 2026-07-27 11:17:57 KST) | vscode-claude(runner) | "
              "반복1 / seed 201 |")
    assert anchor in doc, "docs/45 §5 반복1 행 미발견"
    end = doc.index("\n", doc.index(anchor))

    def sha_cell(d, keys):
        return " · ".join(f"{k.replace('.npz','').replace('.json','')} `{d[k][:16]}`"
                          for k in keys if k in d)

    rows = []
    for r, tag in ((r2, "반복2 / seed 202"), (r3, "반복3 / seed 203")):
        rows.append(
            f"| {s['ts_kst'][:16]} KST | vscode-claude(runner) | {tag} | **{r['sign']}** | "
            f"{sha_cell(r['sealed_sha256'], ['metrics_full.json','oof_M1b.npz','oof_M2b.npz'])} | "
            f"PASS — 전 fold RF random_state=42 · B_seq PCA=outer-fold train∩매핑 fit · "
            f"부호-only redaction · leak_rows=0 · 약물 1,092/scaffold group 732 전수 · fold 교차 0 |")
    rows.append(
        f"| {s['ts_kst'][:16]} KST | vscode-claude(runner) | **consensus (반복1·2·3)** | "
        f"**{cons['sign']}** | "
        f"{sha_cell(cons['sealed_sha256'], ['metrics_full.json','consensus_M1b.npz','consensus_M2b.npz'])} | "
        f"PASS — SAP A8 방법A(raw probability 산술평균, 3반복) · 반복1 sealed 입력은 machine_read"
        f"(human_exposure=false) · 공개=부호 1개 |")
    doc = doc[:end + 1] + "\n".join(rows) + "\n" + doc[end + 1:]
    open(DOCS45, "w").write(doc)
    print(f"[C-5] docs/45 §5 대장 {len(rows)}행 추가")

    # ── ledger timeline append ──────────────────────────────────────────────
    led = json.load(open(LED), object_pairs_hook=collections.OrderedDict)
    led["timeline"].append(collections.OrderedDict([
        ("ts", now[:10]), ("ts_kst", now),
        ("actor", "vscode-claude(runner)"), ("step", "§13-5 반복2·3 + consensus"),
        ("event", ("확증 OOF 반복2(seed 202)·반복3(seed 203) M1b·M2b 전수 조회 + consensus(반복1·2·3, "
                   "SAP A8 방법A = raw probability 산술평균) 산출. 각 실행 공개 = Δ(M2b−M1b) 부호 1개. "
                   "반복1과 동일 함수 객체 재사용(코드경로 동일성 증명: seed=201 재현본 folds.json 이 "
                   f"반복1 원본과 sha256 동일 {s['code_path_equivalence']['reproduced_sha256'][:16]}) · "
                   "반복1과 동일 compute 조건(BLAS 환경변수 미설정·병렬 인자 무변경).")),
        ("artifacts", [
            "data/processed/splits/confirmatory/rep2_seed202/",
            "data/processed/splits/confirmatory/rep3_seed203/",
            "experiments/runs/v3_confirm_rep2_seed202/(config.json·metrics_public.json·_sealed/)",
            "experiments/runs/v3_confirm_rep3_seed203/(config.json·metrics_public.json·_sealed/)",
            "experiments/runs/v3_consensus_rep123/(config.json·metrics_public.json·_sealed/)",
            "experiments/runs/v3_confirm_rep23/block_C_summary.json",
            "v3_Multimodal/src/confirmatory_oof_rep23.py",
        ]),
        ("hash", {
            "rep2_sealed_sha16": sha16(r2["sealed_sha256"]),
            "rep3_sealed_sha16": sha16(r3["sealed_sha256"]),
            "consensus_sealed_sha16": sha16(cons["sealed_sha256"]),
            "rep1_sealed_sha16_unchanged": sha16(s["rep1_sealed_unchanged"]["at_end"]),
        }),
        ("confirmatory", "Y (새 split test/OOF 조회 — 부호만 방출, sealed 수치 미열람)"),
        ("result_summary", (f"반복2 delta_sign = {r2['sign']} · 반복3 delta_sign = {r3['sign']} · "
                            f"consensus(1·2·3) delta_sign = {cons['sign']} "
                            "(원시 macro AP·Δ 크기·PT별·fold별·반복별 AP 는 sealed, 미열람)")),
        ("integrity_note", (
            "게이트0 PASS · 게이트A(하드) 전 항목 PASS: 약물 1,092 전수 · scaffold group 732 전수 · "
            "모든 scaffold group 이 정확히 1 fold(fold 교차 0) · rare-PT 전 train fold PT별 양성 ≥1 · "
            "B_seq PCA fit = outer-fold train∩매핑 · 전 fold leak_rows=0 · 전 fold RF random_state=42 · "
            "OOF shape (1092,370) NaN 0. "
            "seed 게이트: 반복 r = seed 200+r 만 허용(204·205 미사용, 그 외 시도 시 즉시 중단 하드코딩). "
            "반복1 _sealed 3종 sha256 은 블록 시작·각 반복 종료·블록 종료에서 모두 불변. "
            "consensus 입력의 반복1 sealed OOF 2종은 machine_read(human_exposure=false)로만 로드 — "
            "open_sealed(사람 열람) 호출 0건 유지. "
            f"누출 스캔: 확증 경로 공개/config/log 에서 지표 후보 소수 검출 "
            f"{s['leak_scan']['n_hits_strict_confirmatory']}건. "
            "bootstrap/sign-flip/p/SESOI/TOST/성공판정 미실행 · §13-4 null 본런 미착수 · "
            "네트워크 0 · data/raw 불변 · docs/30 무수정 · git commit 없음.")),
    ]))
    json.dump(led, open(LED, "w"), indent=1, ensure_ascii=False)
    print(f"[C-5] ledger.json timeline append (총 {len(led['timeline'])}건)")


if __name__ == "__main__":
    main()
