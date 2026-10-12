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
