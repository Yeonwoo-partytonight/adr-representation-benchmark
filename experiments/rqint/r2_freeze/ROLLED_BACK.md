# 블록 AL (R2 · SAP 1.2 재동결) — **롤백됨 · 미동결**

- 지시서 `docs/100_r2_sap12_freeze_prompt_for_vscode.md` · 리포트 `docs/100_r2_sap12_freeze_report.md`
- 수행 2026-08-25 · 결과 **중단(보류)**

## 이 디렉터리는 동결 산출물이 아니다

**live 저장소는 SAP 1.1 상태 그대로다.** AL-4 게이트 실패로 §6 롤백을 수행했다.

| 파일 | 지위 |
|---|---|
| `_rollback/` | AL-1 착수 스냅샷(원본 6종) — 복원 소스 |
| `_rollback_sha256.txt` | 위 6종 sha256 |
| `_sealed_stat_start.txt` | 봉인 291종 stat-only 스냅샷(착수) — 종료 시 diff 0 |
| `freeze_py_diff.txt` | AL-2 의 1행 diff 증거 |
| `_attempt_rolled_back/` | ★ **롤백된 시도 산출물**(참조 전용) — live 아님 |

`_attempt_rolled_back/manifest_sap12_ROLLED_BACK.json`(sha16 `50abc0e9e5b45517`) 과
`freeze_sap12_ROLLED_BACK.py`(sha16 `8bef5f70d168c50d`) 는 **어떤 게이트도 이 경로를 읽지 않는다**
(전 게이트는 `experiments/sap/manifest.json` 정확경로만 참조 — 실측 확인).

## 현재 live 불변식 (복원 확인필)

- `experiments/sap/manifest.json` = `756d485feb4715e9` · `sap_version` **1.1** · modules 11
- `v3_Multimodal/src/sap/freeze.py` = `94e6369fa952be7f` · 42,927 B
- SAP 11모듈 전건 등재값 일치 · `experiments/rqint/r3_package.zip` = `fcbcaeea6c6158de`
- 봉인 291/275 착수=종료 · HEAD `566f487` · 커밋 21
