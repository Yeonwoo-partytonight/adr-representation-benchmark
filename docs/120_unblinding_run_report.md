# [블록 BF] 확증 결과 개봉 실행 — Phase B(공개 무결성 확인 · 기록) — 수행 리포트

- 지시서: `docs/120_unblinding_run_prompt_for_vscode.md`
- 수행: Claude Code (VS Code) · 2026-10-08 오전 ~ 10:19 KST 종료 (기록 3종 10:17:21 KST)
- 결과: **완료(Phase B)** — B-0 게이트 27/27 PASS · 기록 3종 append(docs/33 항목 84 · docs/45 §2 +1 · §3 +2 · ledger timeline 81 · frozen_artifacts 77) · FLL 무수정(§5 편차 1) · 재계산 0 · `_staging/` 내용 열람 0 · git 쓰기 0 · 네트워크 0

## 1. 게이트/선행조건 (§무결성 — B-0 실측표)
| 항목 | 기대 | 실측 | 판정 |
|---|---|---|---|
| 분기 | Phase A 리포트 있음 · 래퍼 마지막 이벤트 = 자식 rc 0 완료 · `manifest_public.json` 있음 | `completed` exit_code 0 (2026-10-08 07:06:37 KST · hb_event `r7_done`) · 존재 | Phase B |
| F1 git | 566f487 · 21 · ls-files -m 5 · index.lock 부재 | 566f487 · 21 · 5 · 부재 | PASS |
| 래퍼 종료 | 완료(자식 rc 0) | `completed` exit_code 0 | PASS |
| 재시작 수 | ≤ 5 | launch 1 · 재시작 0 | PASS |
| rc 12/13 이력 | 0 | 0(exit_code 이력 = [0]) | PASS |
| `_staging/failure.json` | 부재 | 부재(존재 여부만 확인) | PASS |
| `manifest_public.json` 전 파일 sha | 전건 일치 | 39/39 일치 · results/ 여분 파일 0(40 = 39 + manifest) | PASS |
| `results_layout` | 전 항목 존재 | 11 파일 + `sealed_publish/` 29 존재 | PASS |
| `unblinding_event.json` | 존재 · `approval_ref` == 승인 기록 sha | 존재 · `5ff4c45a…` == 승인 기록 sha · `manifest_public_sha256` == 디스크 · `files` == manifest | PASS |
| 승인 기록 sha | 본런 전후 불변 `5ff4c45a84285000…` | 동일 | PASS |
| 승인 결속 7해시 | 불변 · 디스크 일치 | 7/7 | PASS |
| 동결물 F4 31파일 | 불변 | 31/31(Phase A 대조목록 재사용) · `PLAN_SHA256` == ① | PASS |
| 독립 검산 | `all_match` true | `results_full.json` `independent_check` = `{"all_match": true}` | PASS |
| G1 비트 일치 | 통과 | C1 `delta_obs` == holm8 `delta_rf` · C1 bootstrap 5키 == d9 `rf` 5/5(공개 파일 간 정확 일치) | PASS |
| 봉인 계수 | 39 / 831 / 801 / 30 | 39 / 831 / 801 / 30 | PASS |
| 신규 access.log | 5 = 계획 `trees_without_access_log_at_118` | 5 · 집합 일치 | PASS |
| 판독 트리 access 증가 | 각 launch 수(1) + 공개 1 = +2 | 26/26 트리 +2 · 합 223 → 275 | PASS |
| 판독 범위 밖 트리 증가 | 0 | 0 | PASS |
| `launches.jsonl` | launch 수 대조 | launch 1 · published 1 · 트리 목록 = 계획 26 | PASS |
| 봉인 801 내용 sha | = 감사 JSON `sealed_sha256` | 801/801 · live 이름 집합 = 키 집합 | PASS |
| 플래그 6파일 | 무수정 | true×3 · false×3 그대로 | PASS |
| compute lock | 부재 | 부재 | PASS |
| B-3 종료 | B-0 재실행 · 역복원 · 7해시 불변 | 27/27 PASS · 기록 3종 역복원 assert PASS · FLL sha 불변 | PASS |

## 2. 실행한 명령
```bash
# 분기 판정 (이름·존재만)
tail -5 experiments/runs/v3_unblind_watchdog/watchdog_events.jsonl ; ls experiments/runs/v3_unblinding/results
# B-0 게이트 (scratchpad/b0_gate.py · unblinding_run import → stat_summary·sealed_stat 만 · 쓰기 0)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scratchpad/b0_gate.py
# B-1 기록 (scratchpad/b1_records.py · append-only · 역복원 assert 후 temp + os.replace)
python3 -B scratchpad/b1_records.py
# B-3 종료검증 = b0_gate.py 재실행
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scratchpad/b0_gate.py
```
`--stage run` 직접 실행 0 · 래퍼 기동 0 · `open_sealed` 0 · 재계산 0.

## 3. 산출물
- `docs/33_prereg_deviation_log.md` — 항목 84 추가 · 623,244 B · `dd068b50da254c2a04f4f701f059bf09dd57ace6047a3e46b78011b5760b6e11` (앞 617,535 B = Phase A 종료본 `8f6f534b…` 보존)
- `docs/45_research_integrity_ledger.md` — §2 +1 · §3 +2 · 219,115 B · `359898ebee94686599b43500695af3b1f400d3c77f097bbdb7485afccb6f59c8`
- `experiments/provenance/ledger.json` — timeline 81 · frozen_artifacts 77(`unblinding_event` · `unblinding_results_manifest`) · correspondence 41(불변) · 498,694 B · `1b7cc89bbf7ad0bbb0f815219e67a006832ba930f4b9b5bc7436002326057362`
- `experiments/provenance/first_look_log.json` — **무수정** · 55,628 B · `838db38d…`(§5 편차 1)
- 이 리포트.
- (러너 산출 아님 · 본런 산출 참조) `experiments/provenance/unblinding_event.json` · 6,044 B · sha256 `10287d9dc4750f8567fe80d89cb0d13daf866e742f5320b916fceaceebd31344` · `experiments/runs/v3_unblinding/results/manifest_public.json` · 5,840 B · sha256 `2205e5b570d204606f659c22c93ae0ad749b77bc5222a82de803b53b424caa6d`

## 4. 관측 (출처 경로 병기)

### 4-1. 실행 이력 (`experiments/runs/v3_unblind_watchdog/watchdog_events.jsonl` · `experiments/runs/v3_unblinding/launches.jsonl` · `heartbeat.jsonl`)
- 래퍼 기동 2026-10-07 13:11:46 KST → `power_wait` 60.1 s → `power_ok` 13:12:46 → launch 1 / 자식 pid 19688 13:15:26 → R1 13:15:31.481 → 항목 38/38 → R5 2026-10-08 06:22:04.377 · R6 07:05:49.863 · R7 07:05:50.355 → `completed` rc 0 07:06:37 KST. wall(launch→completed) ≈ 17 h 51 m.
- 래퍼 이벤트 41줄 = start 1 · power_wait 1 · power_ok 1 · launch 1 · child_started 1 · progress 19 · stall_suspect 17 · completed 1. heartbeat 88줄 = item_start 38 · item_done 38 · pt_checkpoint 7 · r1/r2/r5/r6/r7 각 1.
- 자식 stdout: `[G-IDLE A] PASS [unblinding run entry] load1=1.56 < 2.0` · LOCK 획득·해제 pid 19688 · `{"stage": "run", "published": true}` (`experiments/runs/v3_unblind_watchdog/child_stdout.log`).

### 4-2. §결과 — `results/table_main.md` 전문 축자
출처 `experiments/runs/v3_unblinding/results/table_main.md` · 4,282 B · sha256 `70db5e27831c0ca820e44d6c7b5a8589a0b8eac93c292db650b667c36625799c`

````markdown
| id | slot | label | status | delta_obs | ci_low | ci_high | ci_status | p_raw | p_adj_panel1 | p_adj_panel2 | decision | tost | base | treat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | ① | M2b − M1b (RF · primary) | confirmatory | -0.006324167855457974 | -0.01631979733530217 | 0.0005022188133184531 | estimable | 0.23347665233476653 |  |  | RQ2 = rq2_decision(원 p · 무보정) | Inconclusive | M1b | M2b |
| C2 | ② | M2b − P-ID | confirmatory | -0.01859785531900579 | -0.026589781855748833 | -0.012083831188583609 | estimable | 9.999000099990002e-05 | 0.0006999300069993001 | 0.0006999300069993001 | RQ3(판1 Holm 조정 p · H3) | Inconclusive | P-ID | M2b |
| C3 | ③ | M2b − P-FAM | confirmatory | -0.008372529740464735 | -0.017724908775914715 | -0.0018306019568997038 | estimable | 0.057394260573942604 | 0.286971302869713 | 0.34436556344365565 | RQ3(판1 Holm 조정 p · H3) | Inconclusive | P-FAM | M2b |
| C4 | ④ | M2b vs 자연 임베딩 재배치 null | confirmatory |  |  |  |  | 0.965034965034965 | 0.9881011898810119 | 1.0 | RQ4 = rq4_decision(판1 조정 p, 판1 조정 p) · 원 p_emp 2개 별도 칸 |  |  |  |
| C5 | ⑤ | M2b − M0 | confirmatory | 0.005483205168877542 | -0.0046739007689148475 | 0.012896151203300987 | estimable | 0.32936706329367066 | 0.9881011898810119 | 1.0 | Holm 표 | Inconclusive | M0 | M2b |
| C6 | ⑥ | M2b − RF_tuned | confirmatory | 0.009210235944827366 | -0.0007722179906984651 | 0.016007018771262684 | estimable | 0.35766423357664234 | 0.9881011898810119 | 1.0 | Holm 표 | Inconclusive | RF_tuned | M2b |
| C7 | ⑦ | RF+seq − RF (ens − M0) | confirmatory | -0.0010989134151744018 | -0.0024749418684072893 | 0.0009684456419485055 | estimable | 0.23607639236076391 | 0.9443055694430557 | 1.0 | Holm 표 | Equivalent | M0(p_RF) | ens |
| C8 | ⑧ | RQ-int (Δ_RF vs Δ_GIN) | confirmatory |  |  |  |  | 0.00021999780002199978 | 0.0013199868001319986 | 1.0 | RQ-int = 판1 Holm 조정 p < α (D7 · H3) · 판2(⑧ = 1.0) 병기(D14) |  |  |  |
| C-CAP | RQ3d | M2b − C-CAP | secondary_decision | 0.023767005819215925 | 0.016013085435127514 | 0.028495763794111874 | estimable | 9.999000099990002e-05 |  |  | H2: _contrast_pass(ci_primary, 원 p) → 최소 성립 조건 (Holm family 밖 · 무보정) | Positive | C-CAP | M2b |
| S-RQ1 | RQ1 | M1 − M0 | secondary | 0.0029941851112579854 | 0.0010590294628741938 | 0.0050296383073101135 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Equivalent | M0 | M1 |
| S-RQ1b | RQ1b | M1b − M1 | secondary | 0.00881318791307753 | 0.006068651695134552 | 0.011504953578289026 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Inconclusive | M1 | M1b |
| S-M2 | M2 | M2 − M1 | secondary | -0.0021303003340538418 | -0.012407213284871972 | 0.004805869236717105 | estimable | 0.718028197180282 |  |  | 비판정 | Inconclusive | M1 | M2 |
| S-7h | ⑦h | ens_half − M0 (λ = 0.5) | secondary | -0.03532509549041027 | -0.042938254051190276 | -0.02218127826197649 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Inconclusive | M0(p_RF) | ens_half |
| S-7s | ⑦s | ens_sens − M0 | secondary | -0.0009985848730177382 | -0.0022822584706261887 | 0.000901750895516047 | estimable | 0.22497750224977503 |  |  | 비판정 | Equivalent | M0(p_RF) | ens_sens |
| S-pch | ①pch | M2b_pchembl − M1b_pchembl | sensitivity | -0.006757920983905041 | -0.016416919429555792 | -0.00028551247023092915 | estimable | 0.1628837116288371 |  |  | 비판정 · ① pChEMBL 민감도 | Inconclusive | M1b_pchembl | M2b_pchembl |
| S-fsc | ③fsc | M2b − P-FAM_selfclust | sensitivity | -0.016945839426196596 | -0.02542971049139943 | -0.010161419450953068 | estimable | 9.999000099990002e-05 |  |  | 비판정 · ③ family 정의 민감도 | Inconclusive | P-FAM_selfclust | M2b |
| S-unit-drug | ①unit | M2b − M1b bootstrap 단위 = drug | sensitivity | -0.006324167855457974 | -0.01335283873253267 | 7.259081595379845e-05 | estimable |  |  |  | 비판정 · ci_primary 그대로(percentile 아님) |  | M1b | M2b |
| S-unit-sw | ①unit | M2b − M1b bootstrap 단위 = size_weighted | sensitivity | -0.006324167855457974 |  |  | not_estimable |  |  |  | 비판정 · ci_primary 그대로(percentile 아님) |  | M1b | M2b |
````

### 4-3. §결과 — `results/reporting_text.md` 전문 축자
출처 `experiments/runs/v3_unblinding/results/reporting_text.md` · 8,349 B · sha256 `99a4728e8bfd5b5ddb321d5b273d29a631e646d4520a8f9dd319c6a6cc41e0bc`

````markdown
# 개봉 결과 보고 문면 (계획 `v3_Multimodal/config/unblinding_plan_v1.json` · sha256 d5aa594b630992fd10739573409a2008227db72a843f310b001b9ca24ce59764)

## estimand_verbatim

conditional OOF evaluation — 고정된 consensus OOF 예측 위에서의 macro AP Δ. 모델 재학습 미포함(예측을 고정한 조건부 평가). A6: cluster 복원추출→멤버 약물행 복제→pooled AP = drug-weighted macro AP.

## estimand_commentary_U5

재학습 변동은 RF 에서 분할 반복 3(학습 random_state 42 고정), GIN 에서 분할 반복 3 × 학습시드 3 범위에서만 반영 · 새 표본 일반화 주장 아님

## null_hypothesis_rqint_verbatim

강한 null(각 family 내부 arm 라벨이 군 단위 교환 가능)을 부과하는 공유 동전 군 단위 교환 검정 · 검정 대상은 약한 null(Δ_RF = Δ_GIN) · 약한 null 하 1종오류는 R1 사전지정 시뮬레이션 조건(보정 전 α=0.05)에서만 실증 · 「약한 null 정확검정」 표기 금지. 참조분포 = 동전 100,000 + 짝 여집합(독립 추출 200,000 아님).

## t_obs_basis_rq4

④ T_obs = rep1(seed 201) OOF 기준(consensus 아님) — 동결 사실.

## d13_methods

Kish G_eff 85.3 · 상위 2군 14.2% 지배(docs/84:55)를 방법부에 명시한다.

## d14_rule

Both adjusted-p tables are reported in full (docs/100:145). 판1(⑧ = 주 p) · 판2(⑧ = 1.0). 두 판에서 다른 6슬롯 결론이 달라지면 본문에 명시한다(d14_conclusion_differs).

## d19_verbatim

The τ = 0.02 power level (0.735 at unadjusted α = 0.05, middle rung of the pre-specified ladder) was below the 0.80 target; power for the Holm-adjusted decision is lower, so a non-significant RQ-int has limited ability to exclude interactions of that size.

## rqint_nonsignificant_verbatim

A non-significant RQ-int is reported as inconclusive and must not be interpreted as evidence of equal sequence effects across model families.

## r_d

보정 전 α=0.05 경계 일치를 Holm 보정 후 판정으로 확대 서술 금지 · 기존 감사 승계 범위 = 확인된 조건으로 한정.

## s6_text

선택된 15셀의 기술적 제곱합 분해. 금지 표현 = 「분할 분산」·「시드가 X% 설명」·「재현성 입증」·「seed 효과 유의」. 병기 = 확증 seed 중복(5 중 3) · unit 간 약물 중복 수 · unit별 유효 PT 수.

## sign_awareness_table

RF 부호 4건 인지(2026-07-27 연구자 1인 · 정본 experiments/provenance/sign_disclosure_matrix.json) ↔ 이후 결정 목록(결정자·시점·방향 — U2·W1′~W3·I1~I6·J1~J6·G1~G11·H1~H4) — 「완전 맹검」 주장 금지.

## reporting_priority_and_disclosure

① 주 판정은 주 p·조정 p 로만 결정 ② D12·BCa·S6·민감도와의 불일치는 공개 의무 ③ 부가분석으로 주 판정 대체 금지 ④ 결과 설명용 원인·새 수치 기준(「안정적」 등)은 미리 정하지 않음 ⑤ 산출 목록의 모든 항목을 결과와 무관하게 공개.

## allowed_claims_s14_verbatim

| 확보 결과 | 허용 주장 |
|---|---|
| M2b > M1b | 서열 표현이 (개수·연구량 통제 후) 증분 정보 제공 |
| M2b > C-CAP | 개선이 단순 파라미터/용량 증가 아님 |
| M2b > P-ID | 서열 내용이 이산 정체성 이상 기여 |
| M2b > P-FAM | 서열이 coarse family 이상 기여 |
| True > 재배치 null | 정확한 drug–target 대응이 예측에 기여 |
| 유사도 낮은 층 M2b > P-ID | 서열 표현이 미관찰 표적에 전이 |
| RF+seq > RF | 서열이 fingerprint와 비중복 정보 제공 |
| 외부서 방향 재현 | label-source·시간 transportability 지지 |
| M2b ≈ RF | 관측 성능 유사; 우월·비열등 주장 불가 |
| M2b < RF 이나 M2b > M1b | 서열 증분 가치 있으나 최종 utility는 RF 미만 |
| M2b ≈ P-ID | 이득이 서열보다 정체성 기인 가능 |
| 재배치 null ≈ M2b | drug–target 대응 기반 해석 불가 |
| seen 성공·unseen 실패 | continuous representation 이점, 기전 정보 미입증 |

## 결과 표

| id | slot | label | status | delta_obs | ci_low | ci_high | ci_status | p_raw | p_adj_panel1 | p_adj_panel2 | decision | tost | base | treat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | ① | M2b − M1b (RF · primary) | confirmatory | -0.006324167855457974 | -0.01631979733530217 | 0.0005022188133184531 | estimable | 0.23347665233476653 |  |  | RQ2 = rq2_decision(원 p · 무보정) | Inconclusive | M1b | M2b |
| C2 | ② | M2b − P-ID | confirmatory | -0.01859785531900579 | -0.026589781855748833 | -0.012083831188583609 | estimable | 9.999000099990002e-05 | 0.0006999300069993001 | 0.0006999300069993001 | RQ3(판1 Holm 조정 p · H3) | Inconclusive | P-ID | M2b |
| C3 | ③ | M2b − P-FAM | confirmatory | -0.008372529740464735 | -0.017724908775914715 | -0.0018306019568997038 | estimable | 0.057394260573942604 | 0.286971302869713 | 0.34436556344365565 | RQ3(판1 Holm 조정 p · H3) | Inconclusive | P-FAM | M2b |
| C4 | ④ | M2b vs 자연 임베딩 재배치 null | confirmatory |  |  |  |  | 0.965034965034965 | 0.9881011898810119 | 1.0 | RQ4 = rq4_decision(판1 조정 p, 판1 조정 p) · 원 p_emp 2개 별도 칸 |  |  |  |
| C5 | ⑤ | M2b − M0 | confirmatory | 0.005483205168877542 | -0.0046739007689148475 | 0.012896151203300987 | estimable | 0.32936706329367066 | 0.9881011898810119 | 1.0 | Holm 표 | Inconclusive | M0 | M2b |
| C6 | ⑥ | M2b − RF_tuned | confirmatory | 0.009210235944827366 | -0.0007722179906984651 | 0.016007018771262684 | estimable | 0.35766423357664234 | 0.9881011898810119 | 1.0 | Holm 표 | Inconclusive | RF_tuned | M2b |
| C7 | ⑦ | RF+seq − RF (ens − M0) | confirmatory | -0.0010989134151744018 | -0.0024749418684072893 | 0.0009684456419485055 | estimable | 0.23607639236076391 | 0.9443055694430557 | 1.0 | Holm 표 | Equivalent | M0(p_RF) | ens |
| C8 | ⑧ | RQ-int (Δ_RF vs Δ_GIN) | confirmatory |  |  |  |  | 0.00021999780002199978 | 0.0013199868001319986 | 1.0 | RQ-int = 판1 Holm 조정 p < α (D7 · H3) · 판2(⑧ = 1.0) 병기(D14) |  |  |  |
| C-CAP | RQ3d | M2b − C-CAP | secondary_decision | 0.023767005819215925 | 0.016013085435127514 | 0.028495763794111874 | estimable | 9.999000099990002e-05 |  |  | H2: _contrast_pass(ci_primary, 원 p) → 최소 성립 조건 (Holm family 밖 · 무보정) | Positive | C-CAP | M2b |
| S-RQ1 | RQ1 | M1 − M0 | secondary | 0.0029941851112579854 | 0.0010590294628741938 | 0.0050296383073101135 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Equivalent | M0 | M1 |
| S-RQ1b | RQ1b | M1b − M1 | secondary | 0.00881318791307753 | 0.006068651695134552 | 0.011504953578289026 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Inconclusive | M1 | M1b |
| S-M2 | M2 | M2 − M1 | secondary | -0.0021303003340538418 | -0.012407213284871972 | 0.004805869236717105 | estimable | 0.718028197180282 |  |  | 비판정 | Inconclusive | M1 | M2 |
| S-7h | ⑦h | ens_half − M0 (λ = 0.5) | secondary | -0.03532509549041027 | -0.042938254051190276 | -0.02218127826197649 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Inconclusive | M0(p_RF) | ens_half |
| S-7s | ⑦s | ens_sens − M0 | secondary | -0.0009985848730177382 | -0.0022822584706261887 | 0.000901750895516047 | estimable | 0.22497750224977503 |  |  | 비판정 | Equivalent | M0(p_RF) | ens_sens |
| S-pch | ①pch | M2b_pchembl − M1b_pchembl | sensitivity | -0.006757920983905041 | -0.016416919429555792 | -0.00028551247023092915 | estimable | 0.1628837116288371 |  |  | 비판정 · ① pChEMBL 민감도 | Inconclusive | M1b_pchembl | M2b_pchembl |
| S-fsc | ③fsc | M2b − P-FAM_selfclust | sensitivity | -0.016945839426196596 | -0.02542971049139943 | -0.010161419450953068 | estimable | 9.999000099990002e-05 |  |  | 비판정 · ③ family 정의 민감도 | Inconclusive | P-FAM_selfclust | M2b |
| S-unit-drug | ①unit | M2b − M1b bootstrap 단위 = drug | sensitivity | -0.006324167855457974 | -0.01335283873253267 | 7.259081595379845e-05 | estimable |  |  |  | 비판정 · ci_primary 그대로(percentile 아님) |  | M1b | M2b |
| S-unit-sw | ①unit | M2b − M1b bootstrap 단위 = size_weighted | sensitivity | -0.006324167855457974 |  |  | not_estimable |  |  |  | 비판정 · ci_primary 그대로(percentile 아님) |  | M1b | M2b |
````

### 4-4. 그 밖 공개 파일 (경로·sha만)
- `experiments/runs/v3_unblinding/results/table_pt_bh.md` · 34,203 B · sha256 `ac5b18ca937b175b8fb402a7c72b41dbaa9c04edfd5c8d65b0d523ce22719ade` · 표 데이터 행 370(머리 2줄 별도) · 열 `pt | col | delta_obs | p_raw | q_bh | reject`
- `experiments/runs/v3_unblinding/results/table_pt_bh.csv` · 28,983 B · sha256 `53e276d6ad7452d8370c51e735652a4fefcc2dfdfc5b5a5d2c8498276cdac4f8` · 데이터 행 370
- 그림 F-D13: `experiments/runs/v3_unblinding/results/fig_d13_rqint_reference.png` · 26,345 B · sha256 `efd89fb53bf8cf98cd7a71abe1dc1768cdc2a3df94357f4954f42920ebe9665a` · 데이터 `experiments/runs/v3_unblinding/results/fig_d13_rqint_reference.json` · 8,882 B · sha256 `d5c045c6e40e810b48f21883c8c70ccd259110a135bb9686646ec7c6cea290ec`
- 그림 F-NULL: `experiments/runs/v3_unblinding/results/fig_null_realloc.png` · 47,199 B · sha256 `8c9f39ce9e415c73d33b2311eee21ef3ddb0f4d9470dcfa1280593556e1f17e7` · 데이터 `experiments/runs/v3_unblinding/results/fig_null_realloc.json` · 4,464 B · sha256 `246b066700e00d98931fa87ef7539f2700a2b5ee230073b9fb6d6a27ecd071cd`
- `experiments/runs/v3_unblinding/results/results_full.json` · 4,653,286 B · sha256 `372cce5d1be9f3772996284fc651fe0ff23310a61d79cb0a1bf6716c5b5a1414` · `sealed_publish/` 29파일(sha = `manifest_public.json`)

### 4-5. §판정 — `results_full.json` `decisions` 축자 (출처 `experiments/runs/v3_unblinding/results/results_full.json` · 4,653,286 B · sha256 `372cce5d1be9f3772996284fc651fe0ff23310a61d79cb0a1bf6716c5b5a1414`)

```json
{
 "C_CAP": {
  "ci_estimable": true,
  "ci_low": 0.016013085435127514,
  "cond1_ci_lower_gt0": true,
  "cond2_p_lt_alpha": true,
  "p": 9.999000099990002e-05,
  "pass": true
 },
 "RQ2": {
  "alpha": 0.05,
  "ci_estimable": true,
  "ci_low": -0.01631979733530217,
  "cond1_ci_lower_gt0": false,
  "cond2_signflip_p_lt_alpha": false,
  "cond3_sesoi": false,
  "delta_obs": -0.006324167855457974,
  "rq": "RQ2 (M2b>M1b, primary)",
  "rule": "성공 ⟺ (1)&(2)&(3) 모두(IU). 방향성은 (1) CI 하한>0가 보장(D1).",
  "sesoi": 0.01,
  "signflip_p": 0.23347665233476653,
  "success": false
 },
 "RQ3": {
  "M2b_vs_PFAM": {
   "ci_estimable": true,
   "ci_low": -0.017724908775914715,
   "cond1_ci_lower_gt0": false,
   "cond2_p_lt_alpha": false,
   "p": 0.286971302869713,
   "pass": false
  },
  "M2b_vs_PID": {
   "ci_estimable": true,
   "ci_low": -0.026589781855748833,
   "cond1_ci_lower_gt0": false,
   "cond2_p_lt_alpha": true,
   "p": 0.0006999300069993001,
   "pass": false
  },
  "p_raw": {
   "M2b-P-FAM": 0.057394260573942604,
   "M2b-P-ID": 9.999000099990002e-05
  },
  "rq": "RQ3 (M2b>P-ID 및 M2b>P-FAM)",
  "rule": "성공 ⟺ 두 대비 각각 (1) CI 하한>0 & (2) p<α. co-primary 통제(max 금지).",
  "success": false
 },
 "RQ4": {
  "family_constrained": {
   "p_emp": 0.9881011898810119,
   "pass": false
  },
  "global": {
   "p_emp": 0.9881011898810119,
   "pass": false
  },
  "p_raw": {
   "p_emp_family": 0.965034965034965,
   "p_emp_global": 0.21478521478521478,
   "p_slot": 0.965034965034965
  },
  "rq": "RQ4 (M2b > 재배치 null)",
  "rule": "성공 ⟺ global·family-constrained 재배치 null 둘 다 p_emp<α.",
  "success": false
 },
 "RQ_int": {
  "adjusted_p": 0.0013199868001319986,
  "alpha": 0.05,
  "p_raw": 0.00021999780002199978,
  "rule": "판1 Holm 조정 p < α (D7 · H3)",
  "success": true
 },
 "d14_any_difference": false,
 "d14_conclusion_differs": {
  "M2b-M0": false,
  "M2b-P-FAM": false,
  "M2b-P-ID": false,
  "M2b-RF_tuned": false,
  "M2b-realloc_null": false,
  "RFseq-RF": false
 },
 "gin_direction_agrees": false,
 "gin_directional_vs_rf": {
  "GIN M2b − M0": true,
  "GIN M2b − P-FAM": false,
  "GIN M2b − P-ID": true
 },
 "holm": {
  "panel1": {
   "adjusted_p": {
    "M2b-M0": 0.9881011898810119,
    "M2b-P-FAM": 0.286971302869713,
    "M2b-P-ID": 0.0006999300069993001,
    "M2b-RF_tuned": 0.9881011898810119,
    "M2b-realloc_null": 0.9881011898810119,
    "RFseq-RF": 0.9443055694430557,
    "RQ-int": 0.0013199868001319986
   },
   "alpha": 0.05,
   "family_size": 7,
   "family_size_fixed": 7,
   "method": "Holm step-down",
   "note": "②~⑧ 동시 Holm(family=7 고정). ① M2b−M1b(primary)는 무보정(이 family 제외). 결측/undefined p → 1.0(드롭 금지).",
   "raw_p": {
    "M2b-M0": 0.32936706329367066,
    "M2b-P-FAM": 0.057394260573942604,
    "M2b-P-ID": 9.999000099990002e-05,
    "M2b-RF_tuned": 0.35766423357664234,
    "M2b-realloc_null": 0.965034965034965,
    "RFseq-RF": 0.23607639236076391,
    "RQ-int": 0.00021999780002199978
   },
   "reject": {
    "M2b-M0": false,
    "M2b-P-FAM": false,
    "M2b-P-ID": true,
    "M2b-RF_tuned": false,
    "M2b-realloc_null": false,
    "RFseq-RF": false,
    "RQ-int": true
   },
   "undefined_fill_value": 1.0,
   "undefined_filled": {
    "M2b-M0": false,
    "M2b-P-FAM": false,
    "M2b-P-ID": false,
    "M2b-RF_tuned": false,
    "M2b-realloc_null": false,
    "RFseq-RF": false,
    "RQ-int": false
   }
  },
  "panel2": {
   "adjusted_p": {
    "M2b-M0": 1.0,
    "M2b-P-FAM": 0.34436556344365565,
    "M2b-P-ID": 0.0006999300069993001,
    "M2b-RF_tuned": 1.0,
    "M2b-realloc_null": 1.0,
    "RFseq-RF": 1.0,
    "RQ-int": 1.0
   },
   "alpha": 0.05,
   "family_size": 7,
   "family_size_fixed": 7,
   "method": "Holm step-down",
   "note": "②~⑧ 동시 Holm(family=7 고정). ① M2b−M1b(primary)는 무보정(이 family 제외). 결측/undefined p → 1.0(드롭 금지).",
   "raw_p": {
    "M2b-M0": 0.32936706329367066,
    "M2b-P-FAM": 0.057394260573942604,
    "M2b-P-ID": 9.999000099990002e-05,
    "M2b-RF_tuned": 0.35766423357664234,
    "M2b-realloc_null": 0.965034965034965,
    "RFseq-RF": 0.23607639236076391,
    "RQ-int": 1.0
   },
   "reject": {
    "M2b-M0": false,
    "M2b-P-FAM": false,
    "M2b-P-ID": true,
    "M2b-RF_tuned": false,
    "M2b-realloc_null": false,
    "RFseq-RF": false,
    "RQ-int": false
   },
   "undefined_fill_value": 1.0,
   "undefined_filled": {
    "M2b-M0": false,
    "M2b-P-FAM": false,
    "M2b-P-ID": false,
    "M2b-RF_tuned": false,
    "M2b-realloc_null": false,
    "RFseq-RF": false,
    "RQ-int": false
   }
  }
 },
 "minimum_establishment": {
  "rule": "RQ2 ∧ (RQ3 ∨ C-CAP) ∧ RQ4 (H2 · 등록 §8)",
  "success": false
 },
 "tost": {
  "C-CAP": "Positive",
  "C1": "Inconclusive",
  "C2": "Inconclusive",
  "C3": "Inconclusive",
  "C5": "Inconclusive",
  "C6": "Inconclusive",
  "C7": "Equivalent",
  "S-7h": "Inconclusive",
  "S-7s": "Equivalent",
  "S-M2": "Inconclusive",
  "S-RQ1": "Equivalent",
  "S-RQ1b": "Inconclusive",
  "S-fsc": "Inconclusive",
  "S-pch": "Inconclusive"
 }
}
```

### 4-6. 보고 계획 칸 매핑 (`docs/118_unblinding_reporting_plan.md` · sha256 `e3b342e7…` · 해석 없음)
| `decisions` 키 | 보고 계획 칸 |
|---|---|
| `RQ2` | §2-3 판정 요약 「RQ2」 행 · §2-1 C1 행 「판정」 열 |
| `RQ3` (`M2b_vs_PID` · `M2b_vs_PFAM` · `p_raw`) | §2-3 「RQ3」 행 · §2-1 C2·C3 행 |
| `RQ4` (`global` · `family_constrained` · `p_raw`) | §2-3 「RQ4」 행 · §2-1 C4 행(원 p 칸 = `p_emp_global`·`p_emp_family`·슬롯 p) |
| `RQ_int` | §2-3 「RQ_int」 행 · §2-1 C8 행 |
| `C_CAP` | §2-3 「C_CAP」 행 · §2-1 C-CAP 행 |
| `minimum_establishment` | §2-3 「최소 성립」 행 |
| `gin_direction_agrees` · `gin_directional_vs_rf` | §2-3 「GIN 방향 일치(G9 · 기술)」 행 · §2-4 S-GIN |
| `holm.panel1` · `holm.panel2` | §2-2 Holm 판1 · 판2 표 |
| `d14_conclusion_differs` · `d14_any_difference` | §2-2 「결론 차이(D14)」 열 · §4 D14 차이 서술 규칙 |
| `tost` | §2-1·§2-4 「TOST」 열 |

적용되는 보고 계획 문면(축자 · §3·§4): 「A non-significant RQ-int is reported as inconclusive …」는 `RQ_int.success` 값에 따라 적용 여부가 정해지며, 「판정은 판1 조정 p 로만 한다(H3). 판2 는 판정을 바꾸지 않는다.」 · 「부가분석으로 주 판정을 대체하지 않는다.」 · 「관측·벤치마크 결과에서 인과를 주장하지 않는다.」 · 등록 §14 허용 주장표(4-3 `allowed_claims_s14_verbatim` 축자)는 결과 문장 작성 시 그대로 적용한다. 칸별 결과 기입·문장화는 본 리포트 범위 밖(별도 블록).

### 4-7. 봉인 계수 전후 (`unblinding_run.stat_summary` 실측 · 감사 JSON `experiments/provenance/pre_unblinding_audit_v3.json`)
- 전: 39/826/801/25 · access 223(25파일) → 후: 39/831/801/30 · access 275(30파일). 판독 26트리 각 +2 · 범위 밖 0. 봉인 산출물 801 sha 불변.

## 5. 지시서 대비 편차·판단
- **편차 1 — FLL +1행 미기입(B-1-4 단서 적용)**: `first_look_log.json` 19행의 키 집합이 9종으로 갈린다(공통 키 7개 = `ts_kst`·`viewer`·`step`·`status`·`confirmatory`·`delta_sign`·`note` · 최근 행은 `block`·`sealed_sha256`·`runner_asserts_passed` 등이 행마다 다름). 지시서 「키 집합이 행마다 달라 따를 형식이 하나로 정해지지 않으면 쓰지 말고 리포트 §5 에 사유를 남긴다」에 따라 쓰지 않았다(sha `838db38d…` 불변). **cowork 결정 요청**: (가) 공통 7키 + `block`·`approval_ref`·`results_path`·`ts_completed_kst` 형식으로 1행 추가하는 후속 지시 / (나) 미기입 유지(사람 노출 기록은 `unblinding_event.json` · access.log · docs/33 항목 84 · docs/45 §2 로 충분). 공개 시각 `2026-10-08 07:05:50.351 KST` · 경로 `experiments/runs/v3_unblinding/results/` · approval_ref `5ff4c45a…` · 「일괄 공개(R7)」 값은 위 기록들에 이미 있다.
- 판단 2 — `decisions` 축자 출처: 지시서는 `decisions.json`(staging)을 가리키지만 `_staging/` 열람 금지와 충돌할 여지가 있어, 공개된 `results_full.json` 의 `decisions` 키를 축자 출처로 썼다(R7 공개본 · manifest sha 검증 대상). staging `decisions.json` 은 열지 않았다.
- 판단 3 — 독립 검산·G1 근거: `independent_check.json` 은 staging 에만 있어, 공개 `results_full.json` `independent_check` = `{"all_match": true}` 로 판정했다. G1 은 계획 `g1_bit_equality` 의 키로 공개 `results_full` C1 과 공개 `sealed_publish/…holm8_result.json`·`…d9_bca_result.json` 을 정확 비교했다(재계산 아님). 러너가 G1 불일치 시 `g1_*` 코드로 중단하는데 중단·failure.json 이 없다는 점도 병행 근거.
- 판단 4 — `_staging/` 이름 목록 1회: 분기 확인 중 `ls experiments/runs/v3_unblinding/_staging` 로 **파일명만** 1회 출력됐다(decisions.json · design.json · design_groups.npy · independent_check.json · items). 내용 열람 0 · 공개 후 시점. 지시서 「진단은 파일명만」 범위로 판단해 기록한다. 공개 후 `_staging/` 잔존(삭제 0).
- 판단 5 — 운영 사건(실패 아님): 착수 `power_wait` 60.1 s · `stall_suspect` 17건(래퍼 「기록만」 · heartbeat 항목 단위 ≈1 h 간격) · heartbeat `item_start` S-pch load1 2.49(진입 게이트 아님 · 중단 0). 전부 docs/33 항목 84 ⑥ 에 기록.
- 판단 6 — B-3 「`git status` 0」은 Phase A 와 같이 「호출 0」으로 해석(F1 금지 조항과 정합).
- CLAUDE.md 충돌: 없음.

## 6. 다음 액션 제안
- **플래그 6파일 갱신 여부 상신**: `unblinding_performed` false ×3(`post_interim_freeze_v1_0.status.json` · `gin_train_contract.json` · `v3_gin_start_authorization/manifest_t4_post_confirmatory.json`) · `gin_start_still_blocked` true ×3 — 동결 설정 파일이라 본 블록은 무수정. 갱신 시 별도 지시서(사유·전후 해시).
- §5 편차 1(FLL) 결정 · RQ8 외부 검증 실행(`docs/118b`) 블록 · 보고 계획 칸 기입·원고 결과 문장화 블록(§14 허용 주장표 준수 · evidence-checker 감사).
