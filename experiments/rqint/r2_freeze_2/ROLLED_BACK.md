# ⚠️ 이 디렉터리는 **동결물이 아니다** — 블록 AM(docs/101) 롤백 증거

- 블록 = AM · 지시서 `docs/101_r2_sap12_freeze_resume_prompt_for_vscode.md`(정본 `docs/100`)
- 결과 = **중단(보류)** · `docs/100` §6 롤백 완료 · 2026-08-25
- live 상태 = SAP **1.1** · `manifest.json` `756d485feb4715e9` · `freeze.py` `94e6369fa952be7f` (착수와 동일)

## 중단 지점 = AL-5
`docs/100` AL-5 축자 = 「갱신 후 `pre_unblinding_audit.py` 를 실제로 1회 실행해 **통과**를 확인할 것.
**통과 못 하면 중단·보고.**」 → 통과하지 못했다.

**단, 미통과 원인 3건은 전부 R2 이전부터 존재했고 R2 와 무관하다**(§6 롤백으로도 해소되지 않는다):
1. 1회성 가드 — `sealing_completeness_audit.json`·`sign_disclosure_matrix.json` 이 이미 존재(블록 X, 2026-08-07) → `main()` 이 `rc=2` 로 즉시 종료.
2. `SEALED_BASELINE_ARTIFACTS`/`TOTAL` = **273 / 288**(블록 P 실측) vs live **275 / 291**.
3. `G0_EXPECT["…/post_interim_freeze_v1_0.status.json"]` = `a12fee2cdfd71350`(블록 X 스냅샷) vs live `dbb00d540d7436e5`
   — live 값은 `docs/82`(2026-08-07)가 이미 **G0 10/10 PASS** 로 기록한 현행값이다.

★ **R2 가 담당하는 부분은 통과했다** — AL-5 갱신 후 `gate_g0()` 직접 호출 결과
`sap_version` **1.2** · `n_modules` **11** · `n_module_mismatch` **0** · manifest sha16 대조 **OK**.

## 디렉터리 내용
- `_rollback/` — AL-1 착수 스냅샷 원본 6종(복원에 사용)
- `_attempt_rolled_back/` — **롤백된 시도 산출물(참조 전용, live 아님)**
- `_sealed_stat_start.txt` — 봉인 291종 stat-only 착수 스냅샷(내용 읽기 0)
- `freeze_py_diff.txt` · `live_src_3files_diff.json` — 변경행 증거
- `manifest_pre_erratum.json` · `manifest_post_erratum.json` — 재생성/패치 매니페스트 보존본
- `_appendonly_sha256_start.txt` · `_al_evidence_sha256_start.txt` — 무변경 대조 기준선

상세 = `docs/101_r2_sap12_freeze_resume_report.md`
