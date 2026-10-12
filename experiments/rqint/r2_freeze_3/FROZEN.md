# ✅ 블록 AN — R2 완주 (SAP 1.1 → 1.2 재동결) · **롤백 아님**

- 블록 = AN · 지시서 `docs/102_r2_al5_verification_delta_prompt_for_vscode.md`(2차 델타) ·
  `docs/101_...resume_prompt_for_vscode.md`(1차 델타) · `docs/100_r2_sap12_freeze_prompt_for_vscode.md`(정본)
- 결과 = **완료** · 2026-08-25 15:38:40 KST
- live 상태 = SAP **1.2** · `manifest.json` `d08dcedf2a22e1c8` ·
  `freeze.py` `8bef5f70d168c50d`

> ★ 선행 두 디렉터리와 성격이 다르다 — `r2_freeze/`(블록 AL) · `r2_freeze_2/`(블록 AM)는 **롤백 증거**이고,
> 본 디렉터리는 **채택된 동결의 증거**다. 앞의 34파일은 본 블록에서 **0바이트**로 보존됐다(`shasum -c` 34/34 OK).

## 디렉터리 내용
- `_rollback/` — AL-1 착수 스냅샷 원본 6종 (§6 롤백 미발동 · 대조용으로만 사용)
- `_rollback_sha256.txt` · `_appendonly_sha256_start.txt` · `_al_am_evidence_sha256_start.txt` — 착수 기준선
- `_sealed_stat_start.txt` / `_sealed_stat_end.txt` — 봉인 291종 stat-only(내용 읽기 0) · **diff 차이 0**
- `_oneshot_artifacts_start.txt` — 1회성 산출물 mtime 기준선(삭제·이동 금지 대상)
- `freeze_py_diff.txt` — AL-2 의 1행 unified diff
- `manifest_pre_erratum.json` / `manifest_post_erratum.json` — 재생성/패치 매니페스트 보존본
- `live_src_3files_diff.json` — AL-5 3파일 전후 sha256·변경행·범위 기록
- `al5_gate_result.json` — `gate_g0()`·`gate_holm()` 직접 호출 결과 (**`main()` 호출 0**)
- `al5_counterfactual_pre_r2.json` — ★ 반사실 대조(R2 착수 이전 기대값 × 이전 상태) 결과
- `_verify_1_20.json` / `_verify_21_33.json` — 종료검증 33항 기계 기록
- `rqint_procedure_decisions_v1.DRAFT_superseded.json` — 동결본으로 대체된 구 DRAFT 보존본

상세 = `docs/102_r2_al5_verification_delta_report.md`
