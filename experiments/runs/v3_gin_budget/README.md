# v3_gin_budget — 확증 GIN 예산 추정 (블록 AR · `docs/106`)

이 폴더는 확증 GIN 실행에 **얼마나 걸릴지**를 기존 실측치만으로 추정한 산출물이다.
`gin_budget_estimate.json` 한 파일이 본체이고, 산출 규칙은 그 안의
`duration_epoch_mapping_rule` · `outlier_rule` · `unit_cost_rule` 에 **산출 전에 고정**돼 있다.

**이 폴더가 아닌 것**
- **GIN 착수 허가가 아니다** (`not_an_authorization: true`). 착수는 여전히 막혀 있다 —
  ① 교수님 회신 ② Holm ⑧ RQ-int ③ 개봉 승인·시점 ④ `gin_start_still_blocked` 해제(별도 블록·별도 승인).
- **실험 결과가 아니다.** 확증 GIN 학습·추론은 **0회** 수행했다
  (`confirmatory_training_runs_performed: 0`). 봉인(`_sealed/`) 접근 0 · 개봉 0.
- **성능 수치가 아니다.** 여기에는 macro AP·Δ·부호가 **없다**. 시간·개수·epoch 뿐이다.

입력은 전부 기존 산출물이다 — 개발 ladder 런(`experiments/runs/v3_ladder/run.log` + 50개 `*_seed*.csv`
의 mtime)과 RF 확증 `v3_confirm_rest/run.log` 의 `wall` 90건. 새로 돌린 계산은 단가에 넣지 않았다
(`s9_smoke_not_used_in_unit_cost: true`).
