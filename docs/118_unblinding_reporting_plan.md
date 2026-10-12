# 개봉 결과 보고 계획 (블록 BC · `docs/118` BC-4)

> 지위: **개봉 전 동결 문서**(결정 X2 — 개봉 승인 요청에 비차단 첨부). 값 칸은 모두 비어 있다. 결과를 본 뒤 이 문서를 고치면 amendment(`docs/33` 신규 항목 · 사유 · 전후 해시)다.
> 정본 = `v3_Multimodal/config/unblinding_plan_v1.json` (sha256 `d5aa594b630992fd10739573409a2008227db72a843f310b001b9ca24ce59764`). 이 문서는 그 계획을 사람이 읽는 형태로 옮긴 것이며, 둘이 어긋나면 계획 JSON 이 우선한다.
> 작성 시점 상태: 봉인 39/826/801/25 · 봉인 값 열람 0 · 개봉 0.

## 1. 무엇을 계산·공개하는가

개봉은 «봉인값 공개»가 아니라 **동결 절차에 따른 마지막 계산 + 공개**다. ⑧(`holm8_result.json`)·④(`null_result.json`)만 p 가 봉인 계산돼 있고, ①②③⑤⑥⑦ 의 sign-flip p 와 ②③⑤⑥⑦ 의 BCa CI 는 개봉 단계에서 계산한다(① 의 BCa 는 D9 로 봉인 계산됨 → 재계산 후 비트 일치 assert).

- 공통 절차(G1): bootstrap seed **6001** · sign-flip seed **6002** · B **10,000** · eligible = `np.arange(370)` · scaffold 군 732.
- sign-flip = `sap.signflip.scaffold_signflip(기준, 처치, …)` → Δ = 처치 − 기준. bootstrap = `sap.bootstrap.paired_scaffold_bootstrap(같은 순서, unit="scaffold_cluster", alpha=0.05)` · CI primary = BCa(불능 시 not_estimable — percentile 대체 금지).
- TOST 3분 판정 = `sap.decision.tost_equivalence` (CI 가 있는 전 대비).
- 판정 p(G11·H3): RQ2 = 원 p(무보정) · RQ3·RQ4·RQ-int = **판1 Holm 조정 p** · C-CAP = 원 p(H2). 원 p 는 모든 슬롯에서 항상 병기.
- 최소 성립 조건(H2) = **RQ2 ∧ (RQ3 ∨ C-CAP) ∧ RQ4**.

## 2. 결과 표 (빈 양식)

### 2-1. 확증 · 판정 대비

| id | 슬롯 | 대비 (처치 − 기준) | 지위 | Δ | CI 하한 | CI 상한 | CI status | 원 p | 조정 p 판1 | 조정 p 판2 | 판정 | TOST |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | ① | M2b − M1b (RF · primary) | confirmatory |  |  |  |  |  | — | — | RQ2 = rq2_decision(원 p · 무보정) |  |
| C2 | ② | M2b − P-ID | confirmatory |  |  |  |  |  |  |  | RQ3(판1 Holm 조정 p · H3) |  |
| C3 | ③ | M2b − P-FAM | confirmatory |  |  |  |  |  |  |  | RQ3(판1 Holm 조정 p · H3) |  |
| C4 | ④ | M2b vs 자연 임베딩 재배치 null | confirmatory |  | — | — | — |  |  |  | RQ4 = rq4_decision(판1 조정 p, 판1 조정 p) · 원 p_emp 2개 별도 칸 | — |
| C5 | ⑤ | M2b − M0 | confirmatory |  |  |  |  |  |  |  | Holm 표 |  |
| C6 | ⑥ | M2b − RF_tuned | confirmatory |  |  |  |  |  |  |  | Holm 표 |  |
| C7 | ⑦ | RF+seq − RF (ens − M0) | confirmatory |  |  |  |  |  |  |  | Holm 표 |  |
| C8 | ⑧ | RQ-int (Δ_RF vs Δ_GIN) | confirmatory |  | — | — | — |  |  |  | RQ-int = 판1 Holm 조정 p < α (D7 · H3) · 판2(⑧ = 1.0) 병기(D14) | — |
| C-CAP | RQ3d | M2b − C-CAP | secondary_decision |  |  |  |  |  | — | — | H2: _contrast_pass(ci_primary, 원 p) → 최소 성립 조건 (Holm family 밖 · 무보정) |  |

- ④ 행은 원 p 칸에 `p_emp_global` · `p_emp_family` 두 값과 슬롯 p = max(G2)를 함께 적는다. RQ4 판정 입력은 판1 조정 p(두 자리에 같은 값).
- ⑧ 행은 원 p 칸에 `p_primary`(주 p · (1+c)/(B+1)) · `p_secondary` · SE 두 개를 함께 적는다(사이드카 1호).

### 2-2. Holm 판1 · 판2 (D14 — 두 표 모두 전문 보고)

| Holm 라벨 | 슬롯 입력 | 원 p | 판1 조정 p | 판1 기각 | 판2 조정 p | 판2 기각 | 결론 차이(D14) |
|---|---|---|---|---|---|---|---|
| M2b-P-ID | C2.p_raw |  |  |  |  |  |  |
| M2b-P-FAM | C3.p_raw |  |  |  |  |  |  |
| M2b-realloc_null | C4.p_slot |  |  |  |  |  |  |
| M2b-M0 | C5.p_raw |  |  |  |  |  |  |
| M2b-RF_tuned | C6.p_raw |  |  |  |  |  |  |
| RFseq-RF | C7.p_raw |  |  |  |  |  |  |
| RQ-int | C8.p_slot (판2 = 1.0) |  |  |  |  |  | — |

### 2-3. 판정 요약

| 판정 | 규칙 | 결과 |
|---|---|---|
| RQ2 | rq2_decision(C1.bootstrap.ci_primary, C1.p_raw, C1.delta_obs) |  |
| RQ3 | rq3_decision(C2.ci_primary, adj1[M2b-P-ID], C3.ci_primary, adj1[M2b-P-FAM]) |  |
| RQ4 | rq4_decision(adj1[④], adj1[④]) · 원 p_emp_global·p_emp_family 별도 병기 |  |
| RQ_int | 판1 Holm 조정 p < α (D7 · H3) |  |
| C_CAP | _contrast_pass(C-CAP.bootstrap.ci_primary, C-CAP.p_raw) |  |
| 최소 성립 | RQ2 ∧ (RQ3 ∨ C-CAP) ∧ RQ4 (H2 · 등록 §8) |  |
| GIN 방향 일치(G9 · 기술) | sign(Δ_GIN cell_3) == sign(Δ_RF ①) |  |

### 2-4. Secondary · 민감도 (비판정 · 다중성 보정 없음 · 결과와 무관하게 전부 보고)

| id | 대비 / 내용 | 지위 | Δ | CI 하한 | CI 상한 | CI status | 원 p | TOST |
|---|---|---|---|---|---|---|---|---|
| S-RQ1 | M1 − M0 | secondary |  |  |  |  |  |  |
| S-RQ1b | M1b − M1 | secondary |  |  |  |  |  |  |
| S-M2 | M2 − M1 | secondary |  |  |  |  |  |  |
| S-7h | ens_half − M0 (λ = 0.5) | secondary |  |  |  |  |  |  |
| S-7s | ens_sens − M0 | secondary |  |  |  |  |  |  |
| S-pch | M2b_pchembl − M1b_pchembl | sensitivity |  |  |  |  |  |  |
| S-fsc | M2b − P-FAM_selfclust | sensitivity |  |  |  |  |  |  |
| S-unit-drug | M2b − M1b bootstrap 단위 = drug | sensitivity |  |  |  |  | — | — |
| S-unit-sw | M2b − M1b bootstrap 단위 = size_weighted | sensitivity |  |  |  |  | — | — |
| S-PT | M2b − M1b PT별 sign-flip + BH-FDR | secondary | 별표 | — | — | — | — | — |
| S-base | target-only sequence baseline · label prevalence baseline | descriptive | 별표 | — | — | — | — | — |
| S-GIN | GIN Δ(M2b − M1b) · GIN ②③⑤ 방향(기술) | secondary | 별표 | — | — | — | — | — |
| S-sub | ① 부지표 (docs/30 §7 · 기술) | descriptive | 별표 | — | — | — | — | — |

- S-PT 별표: PT · Δ_j · p_j · q_j(BH) · 기각(q ≤ 0.05). 적격 = 양성 ≥ 10 ∧ 양성 포함 scaffold 군 ≥ 3.
- S-base 별표: target-only sequence(`consensus_seq`·`consensus_seq_sens`) macro AP · label prevalence baseline macro AP — 점추정만.
- S-GIN 별표: cell_2(시드별 Δ_GIN) · cell_3(Δ_GIN · `holm8_result.delta_gin` 과 일치 assert) · D9 GIN 복합 BCa · GIN ②③⑤ 시드 평균 점추정과 RF 대응 항목 부호 비교(기술 · CI 없음).

### 2-5. ① 부지표 (G10 · 기술 통계 · CI·p 없음 · 판정·SESOI 미사용)

| 부지표 | 정의 | M1b | M2b | Δ |
|---|---|---|---|---|
| N=20 macro AP | global 양성 ≥ 20 PT 부분집합 |  |  |  |
| N=5 macro AP | not_computable — master_Y 는 양성 ≥ 10 PT 370 열만 보유(데이터 구조) | — | — | — |
| 양성 1~2개 초희소 PT stratum | not_computable — master_Y 는 양성 ≥ 10 PT 370 열만 보유(데이터 구조) | — | — | — |
| prevalence bin macro AP (3분위) | np.quantile(prev, [1/3, 2/3]) · np.digitize(right=True) — 경계 PT 는 하위 bin |  |  |  |
| label-weighted macro AP | PT 가중치 = 양성 수 |  |  |  |
| micro AP | average_precision_score(Ym.ravel(), P.ravel()) |  |  |  |
| prevalence-normalized lift | PT별 AP / prevalence 산술평균 |  |  |  |
| precision/recall@budget | PT별 상위 k = 10 약물 · macro 평균 |  |  |  |
| calibration(보조) | PT별 Brier score macro 평균 |  |  |  |
| ROC-AUC | 양성·음성 모두 있는 PT macro 평균 |  |  |  |

### 2-6. 봉인 결과 공개 (계산 0 · sha 확인 후 그대로 + 표 추출)

| id | 내용 | 원 파일 | 추출 키 | 키 근거(writer) |
|---|---|---|---|---|
| SP-D9 | D9 Δ_RF·Δ_GIN BCa | `experiments/runs/v3_rqint_holm8/_sealed/d9_bca_result.json` | `gin_composite/ci_bca` · `gin_composite/ci_percentile` · `gin_composite/ci_primary` · `gin_composite/delta_obs` · `gin_composite/delta_obs_per_seed` · `rf/ci_bca` · `rf/ci_percentile` · `rf/ci_primary` · `rf/delta_obs` | rqint_holm8_run.py:980-990 · 526-543 |
| SP-H8 | ⑧ 봉인 결과(p_primary·p_secondary·SE·Δ) | `experiments/runs/v3_rqint_holm8/_sealed/holm8_result.json` | `B` · `d14_dual_reporting` · `delta_gin` · `delta_gin_per_seed` · `delta_rf` · `p_primary` · `p_secondary` · `se_primary` · `se_secondary` · `t_obs` | rqint_holm8_run.py:953-979 |
| SP-D11 | D11 leverage λ_k·ρ | `experiments/runs/v3_rqint_leverage_d11/_sealed/leverage_diagnostics.json` | `T_obs` · `checks` · `delta_gin` · `delta_rf` · `lambda_k` · `rho` | rqint_leverage_d11.py:479-504 |
| SP-D12 | D12 민감도 2종 (변형별 p_primary·p_secondary·SE) | `experiments/runs/v3_rqint_d12/_sealed/d12_result.json` | `t_obs` · `variants/i/B` · `variants/i/label_rule` · `variants/i/n_groups_G` · `variants/i/p_primary` · `variants/i/p_secondary` · `variants/i/se_primary` · `variants/i/se_secondary` · `variants/ii/B` · `variants/ii/label_rule` · `variants/ii/n_groups_G` · `variants/ii/p_primary` · `variants/ii/p_secondary` · `variants/ii/se_primary` · `variants/ii/se_secondary` | rqint_d12_run.py:1027-1064 |
| SP-S6 | S6 안정성 15셀 기술적 SS 분해 | `experiments/runs/v3_stability_ss15/_sealed/ss15_result.json` | `cells` · `two_way_ss` | stability_ss15_run.py:723-756 |
| SP-STRAT | 연속 유사도 층화(M2b − M1b) | `experiments/runs/v3_stratification/_sealed/stratification_result.json` | `multiplicity` · `strata` | stratification_run.py:893-928 |
| SP-STRAT-PID | 유사도 층화(M2b − P-ID · RQ6) | `experiments/runs/v3_stratification_pid/_sealed/stratification_pid_result.json` | `multiplicity` · `strata` | pid_stratification_run.py:769-786 |
| SP-AXES | 층화 축 3종(C1 M2b − M1b · C2 M2b − P-ID) | `experiments/runs/v3_stratification_axes/_sealed/axes_result.json` | `multiplicity` · `strata` | axes_stratification_run.py:1032-1053 |
| SP-NULL | 재배치 null 전 결과(primary · ALT · T_obs) | `experiments/runs/v3_null_MAIN/_sealed/null_result.json` | `ALT` · `T_obs` · `T_obs_basis` · `primary` | null_main_run.py:1356-1390 |
| SP-LAMBDA | ⑦ λ 선택(rep별) | `experiments/runs/v3_latefusion_rep1_seed201/_sealed/lambda_selected.json`<br>`experiments/runs/v3_latefusion_rep2_seed202/_sealed/lambda_selected.json`<br>`experiments/runs/v3_latefusion_rep3_seed203/_sealed/lambda_selected.json` | `grid` · `per_unit` | confirmatory_latefusion.py:869-876 |
| SP-REP | 반복별·consensus macro AP (RF 계열) | `experiments/runs/v3_confirm_rep1_seed201/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rep2_seed202/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rep3_seed203/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rest_rep1_seed201/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rest_rep2_seed202/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rest_rep3_seed203/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rftuned_rep1_seed201/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rftuned_rep2_seed202/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rftuned_rep3_seed203/_sealed/metrics_full.json`<br>`experiments/runs/v3_consensus_rep123/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/metrics_full.json`<br>`experiments/runs/v3_confirm_rftuned_consensus_rep123/_sealed/metrics_full.json` | `macro_ap` · `per_fold_macro_ap` · `per_repeat_macro_ap` | confirmatory_oof_rep1.py:568-577 · rep23.py:376-382,483-490 · rest.py:651-661,706-714 · rftuned.py:582-594,631-640 |
| SP-LATEFUSION | ⑦ 부속 지표(RQ7 · rep별 · consensus) | `experiments/runs/v3_latefusion_rep1_seed201/_sealed/metrics_full.json`<br>`experiments/runs/v3_latefusion_rep2_seed202/_sealed/metrics_full.json`<br>`experiments/runs/v3_latefusion_rep3_seed203/_sealed/metrics_full.json`<br>`experiments/runs/v3_latefusion_consensus_rep123/_sealed/metrics_full.json` | `auxiliary_registered_s12` · `macro_ap` · `per_fold_macro_ap` · `per_repeat_macro_ap` | confirmatory_latefusion.py:879-900,946-954 |
| SP-GIN-CELLS | GIN 셀 88 | `experiments/runs/v3_gin_confirm_consensus_rep123/_sealed/metrics_full.json` | `cells` | confirmatory_gin_consensus.py:448-484,511-531 |

### 2-7. 그림

- **F-D13** — D13 ⑧ 참조분포 히스토그램 · bin 200 · 범위 대칭 [−max|T*|, +max|T*|] · 관측값 수직선 · dpi 150 · 데이터 JSON + PNG (`fig_d13_rqint_reference`).
- **F-NULL** — ④ 재배치 null 분포 그림(등록 §5 A) · bin 50 · 범위 패널별 [min, max] · 관측값 수직선 · dpi 150 · 데이터 JSON + PNG (`fig_null_realloc`).

## 3. 보고 문면 (축자 고정)

### 추론 대상 (SAP manifest `bootstrap_A7.estimand` 축자)

> conditional OOF evaluation — 고정된 consensus OOF 예측 위에서의 macro AP Δ. 모델 재학습 미포함(예측을 고정한 조건부 평가). A6: cluster 복원추출→멤버 약물행 복제→pooled AP = drug-weighted macro AP.

### 추론 대상 해설 (9차 U5)

> 재학습 변동은 RF 에서 분할 반복 3(학습 random_state 42 고정), GIN 에서 분할 반복 3 × 학습시드 3 범위에서만 반영 · 새 표본 일반화 주장 아님

### ⑧ 귀무

> 강한 null(각 family 내부 arm 라벨이 군 단위 교환 가능)을 부과하는 공유 동전 군 단위 교환 검정 · 검정 대상은 약한 null(Δ_RF = Δ_GIN) · 약한 null 하 1종오류는 R1 사전지정 시뮬레이션 조건(보정 전 α=0.05)에서만 실증 · 「약한 null 정확검정」 표기 금지. 참조분포 = 동전 100,000 + 짝 여집합(독립 추출 200,000 아님).

### ④ T_obs 기준

> ④ T_obs = rep1(seed 201) OOF 기준(consensus 아님) — 동결 사실.

### D13 방법부

> Kish G_eff 85.3 · 상위 2군 14.2% 지배(docs/84:55)를 방법부에 명시한다.

### D14 두 판 보고

> Both adjusted-p tables are reported in full (docs/100:145). 판1(⑧ = 주 p) · 판2(⑧ = 1.0). 두 판에서 다른 6슬롯 결론이 달라지면 본문에 명시한다(d14_conclusion_differs).

### D19 유보문장

> The τ = 0.02 power level (0.735 at unadjusted α = 0.05, middle rung of the pre-specified ladder) was below the 0.80 target; power for the Holm-adjusted decision is lower, so a non-significant RQ-int has limited ability to exclude interactions of that size.

### RQ-int 비유의 시

> A non-significant RQ-int is reported as inconclusive and must not be interpreted as evidence of equal sequence effects across model families.

### R-d (사이드카 3호)

> 보정 전 α=0.05 경계 일치를 Holm 보정 후 판정으로 확대 서술 금지 · 기존 감사 승계 범위 = 확인된 조건으로 한정.

### S6 서술

> 선택된 15셀의 기술적 제곱합 분해. 금지 표현 = 「분할 분산」·「시드가 X% 설명」·「재현성 입증」·「seed 효과 유의」. 병기 = 확증 seed 중복(5 중 3) · unit 간 약물 중복 수 · unit별 유효 PT 수.

### 부호 인지·결정 대조표 (9차 U6)

> RF 부호 4건 인지(2026-07-27 연구자 1인 · 정본 experiments/provenance/sign_disclosure_matrix.json) ↔ 이후 결정 목록(결정자·시점·방향 — U2·W1′~W3·I1~I6·J1~J6·G1~G11·H1~H4) — 「완전 맹검」 주장 금지.

### 보고 우선순위·공개 의무 (9차 #2)

> ① 주 판정은 주 p·조정 p 로만 결정 ② D12·BCa·S6·민감도와의 불일치는 공개 의무 ③ 부가분석으로 주 판정 대체 금지 ④ 결과 설명용 원인·새 수치 기준(「안정적」 등)은 미리 정하지 않음 ⑤ 산출 목록의 모든 항목을 결과와 무관하게 공개.

### 등록 §14 결과별 허용 주장표 (축자 전재)

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

## 4. D14 차이 서술 규칙 · 공개 의무 · 금지 표현

- 판1(⑧ = 주 p)과 판2(⑧ = 1.0) 표를 **모두 전문** 싣는다. ⑧ 를 뺀 6슬롯 중 기각 결론이 두 판에서 달라지는 슬롯이 있으면 본문에 슬롯 이름과 함께 명시한다(`decisions.d14_conclusion_differs`).
- 판정은 판1 조정 p 로만 한다(H3). 판2 는 판정을 바꾸지 않는다.
- D12 · BCa(D9) · S6 · 민감도 · 층화 · null ALT · ⑦ λ 결과가 주 판정과 어긋나면 **공개 의무**다. 부가분석으로 주 판정을 대체하지 않는다.
- 결과를 설명하는 원인이나 새 수치 기준(「안정적」 등)을 미리 정하지 않는다.
- 금지 표현: 「약한 null 정확검정」 · 「완전 맹검」 · S6 의 「분할 분산」·「시드가 X% 설명」·「재현성 입증」·「seed 효과 유의」 · 보정 전 α 경계 일치를 Holm 보정 후 판정으로 확대 서술(R-d) · 비유의 RQ-int 를 family 간 동일 효과의 증거로 해석 · 부지표·특정 층·특정 family 만 골라 성공 주장(등록 §8).
- 관측·벤치마크 결과에서 인과를 주장하지 않는다.

## 5. 등록 항목 대응 (prereg_coverage 요약)

| 등록 항목 | 처리 | 항목 id / 사유 |
|---|---|---|
| §3 RQ2 M2b > M1b (primary) | item | C1 |
| §3 RQ1 M1 > M0 | item | S-RQ1 |
| §3 RQ1b M1b > M1 | item | S-RQ1b |
| §3 RQ3a M2b > P-ID | item | C2 |
| §3 RQ3b M2b > P-FAM | item | C3 |
| §3 RQ3d M2b > C-CAP | item | C-CAP |
| §3 RQ4 M2b > 자연 임베딩 재배치 null | item | C4, F-NULL, SP-NULL |
| §3 RQ5 반복 scaffold OOF ΔAP > 0 | item | C1, SP-REP — consensus 위 추론 + 반복별 macro AP 공개 |
| §3 RQ6 유사도 낮은 층 M2b > P-ID | item | SP-STRAT-PID, SP-AXES |
| §3 RQ7 RF+seq > RF | item | C7, S-7h, S-7s, SP-LATEFUSION, SP-LAMBDA |
| §3 RQ-int interaction test | item | C8, SP-H8, SP-D9, SP-D11, SP-D12, F-D13 |
| §3 RQ8 외부·시간 방향 재현 | plan_frozen_pre_opening | docs/118b_external_validation_plan.md sha256 4f06d39e9aa827bd63a2ac28e6dbedbedec2430bbde10aaadd567c81c726f60e · execution_post_opening · R8-1~R8-3 = 라벨 출처 이식성 · EU∪UK 주 · 부호 일치만 (H1) |
| §4 M2 = M1 + 서열 (secondary robustness) | item | S-M2 |
| §4 GIN family 사다리 robustness (방향·CI) | item | S-GIN, SP-GIN-CELLS, SP-D9 |
| §4 neural family mean + DeepSets 병행(보조) | deviation_not_performed | DeepSets 집계 미구현 — GIN 은 mean-pool 집계판만 학습 |
| §4 M1b 적응증·ATC 통제 sensitivity | deviation_not_performed | 적응증·ATC 공변량 미수집·미학습 |
| §4 C-CAP train–val gap 보고 | deviation_not_performed | 확증 RF 하네스 산출물에 train/valid 지표 기록 없음(rest metrics_full 키 = OOF macro AP 계열만 · confirmatory_oof_rest.py:651-661) |
| §4 baseline label prevalence · prevalence-normalized lift | item | S-base, S-sub |
| §4 baseline Morgan RF | item | C5 — M0 = Morgan RF |
| §4 baseline tuned RF | item | C6 |
| §4 baseline M0 GIN | item | S-GIN, SP-GIN-CELLS |
| §4 baseline Morgan + target multi-hot (LR) | deviation_not_performed | LR 모델 미학습(H4) |
| §4 baseline Morgan + 평균 ProtBERT (ridge · MLP) | deviation_not_performed | ridge·MLP 모델 미학습(H4) |
| §4 baseline target-only sequence model | item | S-base |
| §4 baseline RF+seq late-fusion | item | C7 |
| §4 보조자료(C-RAND · M3 · M4 · neural DeepSets · ESM-2 · affinity top-k sweep · PU-loss · calibration 세부 · leave-one-target-out · 1,000회 test-time permutation · 단계화 null · 적응증·ATC) | deviation_not_performed | 보조자료(본문 아님) 실험 미수행 — H4 일괄 이탈 기록 |
| §5 A 자연 임베딩 재배치 null (global · family-constrained · realization ≥100) | item | C4, SP-NULL |
| §5 A 관측값과 null 분포 전체 그림 | item | F-NULL |
| §5 B retrained degree-preserving null | deviation_not_performed | 재학습 null 미수행(H4) |
| §5 C residue-shuffle | deviation_not_performed | residue-shuffle 임베딩 미산출(H4) |
| §6 반복별 macro AP 3개 보고 | item | SP-REP, SP-LATEFUSION |
| §6 consensus OOF 위 통계 추론 | item | C1, C2, C3, C5, C6, C7 |
| §6 GIN outer fold당 3 training seed 평균 | item | S-GIN |
| §7 primary macro AP (global 양성 ≥10 PT · consensus OOF) | item | C1 |
| §7 전체 370 PT macro AP | item | C1 — master_Y 의 370 열 = 양성 ≥ 10 PT 전부 → primary 와 같은 집합 |
| §7 N=20 macro AP | item | S-sub |
| §7 N=5 macro AP | not_computable | master_Y 는 양성 ≥ 10 PT 370 열만 보유(데이터 구조) |
| §7 prevalence bin별 macro AP | item | S-sub |
| §7 label-weighted macro AP | item | S-sub |
| §7 micro AP | item | S-sub |
| §7 prevalence-normalized lift | item | S-sub |
| §7 precision/recall@fixed-budget | item | S-sub |
| §7 calibration(보조) | item | S-sub |
| §7 ROC-AUC | item | S-sub |
| §7 양성 1~2개 초희소 PT exploratory stratum | not_computable | master_Y 는 양성 ≥ 10 PT 370 열만 보유(데이터 구조) |
| §8 paired scaffold cluster bootstrap 95% CI · cluster 크기 분포 · effective number of clusters | item | C1 |
| §8 drug · size-weighted bootstrap sensitivity | item | S-unit-drug, S-unit-sw |
| §8 paired sign-flip randomization | item | C1 |
| §8 PT bootstrap (endpoint-generalization sensitivity) | deviation_not_performed | PT 재표본 bootstrap 미구현(H4) |
| §8 ②~⑧ Holm 보정 | item | C2, C3, C4, C5, C6, C7, C8 — decisions.holm 판1·판2 |
| §8 PT별 formal test + BH-FDR 5% | item | S-PT |
| §8 Interaction (RF vs GIN) | item | C8 |
| §8 Power simulation | item | T-REPORT — 개봉 전 완료(docs/94 R1) · D19 축자 문장으로 보고 |
| §8 SESOI 다차원(상대개선 · lift · 다수 prevalence 층 방향) | item | S-sub — 판정은 |Δ| ≥ 0.01 단일 기준(sap.decision.SESOI) · 그 밖 차원은 기술 서술만 |
| §8 음성결과 3분 판정(TOST) | item | C1, C2, C3, C5, C6, C7, C-CAP, S-RQ1, S-RQ1b, S-M2, S-7h, S-7s, S-pch, S-fsc |
| §8 최소 성립 조건 RQ2 + (RQ3 또는 C-CAP) + RQ4 | item | C1, C2, C3, C4, C-CAP — H2 · decisions.minimum_establishment |
| §9 연속 유사도 층화(primary) | item | SP-STRAT, SP-AXES, SP-STRAT-PID |
| §9 하드 cold split (stress test) | deviation_not_performed | family-disjoint split 미생성(H4) |
| §9 family 정의 다중 | item | S-fsc — primary P-FAM = ChEMBL class L2 · selfclust = sensitivity(기존 재정의 기록 docs/33) |
| §9 dual-shift exploratory stress test | deviation_not_performed | dual-shift split 미생성(H4) |
| §10 late-fusion λ inner valid 선택 · λ = 0.5 병기 | item | C7, S-7h, SP-LAMBDA |
| §10 상관 · rank disagreement · 상호 정오 · ensemble − RF Δ · 개선 fold 비율 | item | SP-LATEFUSION — auxiliary_registered_s12 · per_fold_macro_ap 봉인값 공개 (H4 RQ7 부속) |
| §11 XAI(tier-2) | deviation_not_performed | attribution 분석 미수행(H4) |
| §12 PU(보조) | deviation_not_performed | PU-loss·FAERS 검증 미수행(H4) |
| §12 외부/시간 검증(tier-3) | plan_frozen_pre_opening | = §3 RQ8 (docs/118b) |
| §13 GIN 대표 3 fold × 5 seed | item | SP-S6 |
| §14 결과별 허용 주장 규칙 | item | T-REPORT — reporting_text.allowed_claims_s14_verbatim 축자 |

- `deviation_not_performed` 항목은 개봉 전 `docs/33` 항목 78 에 미수행 사유와 함께 기록한다(H4).
- RQ8 은 `docs/118b_external_validation_plan.md`(sha256 `4f06d39e9aa827bd63a2ac28e6dbedbedec2430bbde10aaadd567c81c726f60e`)로 개봉 전 계획 동결, 실행은 개봉 이후 별도 블록(H1).

## 6. 실패·재개 규칙 (요약)

- 재개 허용(값 무관 중단): 전원 차단 · SIGTERM · 크래시 · 감시 래퍼 재시작 → 같은 명령 재실행 · 완료 항목 건너뜀(결정적) · 재시작 상한 5.
- 무결성 실패 → 즉시 중단 · 재개 금지 · 공개 0 · amendment 필요: 입력 결손 · sha 불일치 · 키 결손 · 확증 비유한 · 완전성 실패 · G1 비트 불일치 · Holm 결측 1.0 발동 · 독립 검산 불일치.
- 실패·중단 상태의 staging 을 사람이 열어 보는 것은 금지(부분 개봉 = `docs/70`:27 위반). 진단은 오류 코드 · 항목 id · 파일명만.
- 공개는 독립 검산기(SAP·개봉 스크립트 import 0)가 `all_match` true 를 낸 뒤에만 한다(X3).
