# Preregistration — Incremental Value of Target-Sequence Representations for Sparse Drug-Label ADR Annotation Prediction under Chemical and Target Distribution Shift

**A Falsification-Oriented, Controlled Representation Study**

---

## Registration metadata

| 항목 | 내용 |
|---|---|
| Title | Do Target Protein Sequences Add Predictive Information Beyond Target Identity? A Falsification-Oriented Evaluation of Sparse Drug-Label ADR Annotation under Scaffold and Target Shift |
| Contributors | 배연우 (Yeonwoo Bae, 제1저자·투고자) · 유남현 (Namhyun Yoo, 공저자, 경남대) · 양진홍 (Jinhong Yang, 교신저자, 인제대 의료IT학과) |
| Registration platform | OSF Registration (Open-Ended / OSF Preregistration template) |
| Registration DOI | ⟨등록 후 기입: 10.17605/OSF.IO/XXXXX⟩ |
| Registration timestamp | ⟨등록 후 기입: YYYY-MM-DD HH:MM UTC⟩ |
| Embargo | 투고/게재 시점까지 비공개(embargo) 설정 |
| Attached materials | 본 사전등록서, split 생성 코드(결과·예측 미포함) |

> **★ 무결성 선언(Attestation)**: 본 사전등록은 **확증용 새 scaffold split의 test/out-of-fold 예측을 단 한 번도 조회하지 않은 시점**에 작성·등록된다. 등록 이후 본문은 수정하지 않으며, 불가피한 변경은 §16 변경이력에 append-only로(변경 시각·사유·결과 조회 여부 명시) 기록한다. 결과를 본 뒤의 가설·주모델·성공기준 변경은 하지 않는다.
>
> **선행 pilot의 지위**: 예비 실험(단일 seed-42 scaffold split, 동일 test 110분자 반복 조회)에서 얻은 모든 수치(M1 macro AP 0.153 / M2 0.194 / RF 0.191 / Δ≈+0.041 등)는 **탐색적(exploratory)** 결과로 규정하며, 모델 구조·하이퍼파라미터·효과크기 추정·검정력 시뮬레이션의 근거로만 사용하고 **일반화 유의성의 근거로 사용하지 않는다.** 본 사전등록이 정의하는 새 split 위의 분석만 확증적(confirmatory)이다.

---

## 1. 배경·목적·엔드포인트

**목적**. 승인 약물의 부작용(ADR) 예측에서, 표적 단백질의 **서열 표현(frozen protein language model)** 이 표적 개수·이산 정체성·표적 계열·연구량 대리변수를 통제한 뒤에도 **증분적 예측 정보**를 제공하는지, 그리고 그 이득이 새로운 화학 scaffold와 새로운 표적으로 **전이**되는지를 falsification-oriented control로 규명한다. 본 연구는 "새로운 멀티모달 모델"의 성능 논문이 아니라 **무엇이 실제로 성능을 만드는지 규명하는 controlled representation study**이다.

**엔드포인트 정의(엄격)**. 예측 대상은 환자 수준 발생률이나 기전이 아니라 **"해당 약물의 미국 의약품 라벨에 특정 MedDRA PT(ADR)가 기재되어 있는가"(drug-label ADR annotation retrieval)**이다. 라벨 0은 true negative가 아니라 **unlabeled**이며, OnSIDES가 라벨 NLP 추출물이라는 점에서 결측은 비무작위(NMAR)일 수 있다(한계 §15). 따라서 "mechanistic information"이 아니라 "mechanistically structured predictive information"으로 기술한다.

---

## 2. 데이터

- **Outcome dataset**: 1,092개 단일성분 승인약물 × 370개 MedDRA PT(global positive support ≥10로 사전 확정), 양성 annotation 19,748, 라벨 밀도 0.0489. OnSIDES v3.1.1(미국 DailyMed) ADR annotation + PubChem canonical 구조. 라벨·분자셋 변경 금지, mock·DrugBank 미사용.
- **표적–약물 데이터(primary source 동결)**: curated mechanism + high-confidence direct **human single-protein** target(ChEMBL 기반 파이프라인 필터), UniProtKB canonical 서열. broader ChEMBL target(complex·family·binding-only·transporter·enzyme)과 전체 organism은 sensitivity. Open Targets/DrugCentral 승격은 tier-2 유보. source version·다운로드 날짜·UniProt accession 고정.
- **Mapping audit(필수 보고)**: direct single-protein/mechanism/binding-only/transporter·enzyme 표적 수, confidence별 수, action(agonist/antagonist/inhibitor) coverage, 약물당 표적 수 분포, mapping 실패 사유, excluded type, train/test target overlap(Jaccard·max sequence identity). 전체의 임의 5~10% **수동 audit** + 오류율·수정규칙(보충자료).
- **미매핑·부분매핑 처리**: 약물별 pre-filter target count / mapped human count / sequence-available count / coverage_ratio / evidence-weighted coverage / mechanism-target 존재 기록. Primary는 전체 1,092 유지(zero vector + missing mask + coverage_ratio), 매핑 약물만 쓰는 complete-case는 sensitivity.

---

## 3. 가설

| RQ | 질문 | 사전 가설 | 지위 |
|---|---|---|---|
| **RQ2** | 연구량 통제 위에서 서열이 표적 개수 이상 유용? | **M2b > M1b** | ★ **Primary (RF model family)** |
| RQ1 | 표적 개수가 구조보다? | M1 > M0 | secondary |
| RQ1b | 연구량 공변량 자체 기여? | M1b > M1 | secondary(교란 크기 진단) |
| RQ3a | 서열이 이산 정체성 이상? | M2b > P-ID | co-primary 통제 |
| RQ3b | 서열이 coarse family 이상? | M2b > P-FAM | co-primary 통제 |
| RQ3d | 단순 용량 아님? | M2b > C-CAP | secondary |
| RQ4 | 실제 약물–표적 대응 기여? | M2b > 자연 임베딩 재배치 null | secondary |
| RQ5 | 새 scaffold에서 유지? | 반복 scaffold OOF ΔAP > 0 | secondary |
| RQ6 | 미관찰 표적/family로 전이? | 유사도 낮은 층에서 M2b > P-ID | secondary(전이 주장) |
| RQ7 | RF와 상보(late-fusion)? | RF+seq > RF | secondary |
| RQ-int | 서열 효과가 model family에 따라 다른가? | interaction test | secondary |
| RQ8 | 외부·시간 방향 재현? | ΔAP 방향 유지 | tier-3 |

**주장 2단 분리**: (i) *seen-target* — PLM 표현이 discrete identity·coarse family보다 유용한 inductive bias를 제공. (ii) *unseen-target* — 그 이득이 서열 유사성으로 미관찰 표적/family에 전이. target-cold 표본이 부족하면 (ii)는 유보하고 (i)만 주장하며, "생물학적 기전 정보 입증"으로 확대 해석하지 않는다.

---

## 4. 모델 (model family: RF-Morgan = primary confirmatory, GIN = robustness replication)

동일 사다리·통제를 두 model family에서 모두 수행하되, **성공 판정은 RF family**로 하고 GIN은 방향·CI 일치로 robustness를 보고한다(RQ-int로 family 간 차이 평가).

**정보 분해 사다리(엄격 nested)**

| 모델 | 구성 | 추가 정보 |
|---|---|---|
| M0 | 구조만 (RF=Morgan r=2 2048bit / GIN=graph embedding) | — |
| M1 | M0 + log(표적수) + missing/coverage | polypharmacology 규모 |
| M1b | M1 + study-intensity/evidence 공변량 | 연구량 교란 (**primary 기준선**) |
| **M2b** | M1b + 표적 **서열** set embedding | **서열 내용 (primary 처치)** |
| (M2) | M1 + 서열 (연구량 공변량 미포함) | secondary robustness |

- **M1b 공변량(예측시점 허용만)**: ChEMBL target evidence count, mechanism vs binding 비율, 평균/최대 confidence, 승인/최초라벨 연도. **적응증·ATC는 leakage 우려로 본문 제외 → sensitivity만.**
- **표현·집계**: `z_t = MeanPool_residue(ProtBERT(s_t))`, 앞 510잔기(절단율 49% 한계 §15). **RF family(primary) 집계 = 표적 mean-pool → z-score → PCA-64 고정 피처.** neural family는 mean + DeepSets 병행(보조). 통제군 side 차원 64 통일. split별 scaler·PCA·집계통계·모델선택은 해당 fold의 train/valid에서만 적합(누수 assert).

**사전지정 표현 통제(M1b 기준 분기 — 표적 표현만 상이)**

| 코드 | = M1b + | 검증 |
|---|---|---|
| P-ID | target **multi-hot** | 서열 vs 이산 정체성 |
| P-FAM | target **family/domain** multi-hot (UniProt family·Pfam/InterPro·ChEMBL class) | 서열 vs coarse family |
| C-CAP | capacity-matched 합성 공변량(표적표현 없음; projection·입력차원·feature norm·dropout·effective rank 매칭, train–val gap 보고) | 단순 용량 |

**추가 baseline(필수)**: label prevalence·prevalence-normalized lift, Morgan RF·tuned RF, M0 GIN, Morgan+target multi-hot(LR), Morgan+평균 ProtBERT(ridge·MLP), target-only sequence model, RF+seq late-fusion.

**보조자료(본문 아님)**: C-RAND(≥20 realization), M3(attention)·M4(action), neural DeepSets, ESM-2 robustness, affinity-weighted top-k sweep, PU-loss 다종, calibration 세부, leave-one-target-out 전수, 1,000회 test-time permutation, 단계화 null, 적응증·ATC 통제.

---

## 5. Falsification (자연 임베딩 재배치 = primary)

- **A. 자연 임베딩 target 재배치(primary)**: 각 단백질 임베딩은 그대로 유지하여(PLM 자연성 보존) drug–target **대응만** 교환. global + family-constrained 2종, realization ≥100. 관측값과 null 분포 전체를 그림으로 제시.
- **B. Retrained degree-preserving null(보조)**: drug–target bipartite graph에서 degree 보존 double-edge swap 후 재학습, ≥20회.
- **C. Residue-shuffle(보조)**: 조성 보존·순서 파괴. 단 비자연 입력(OOD)이라 성능 저하 해석에 신중.
- 경험적 p: `p_emp = (1 + #{Δ_perm ≥ Δ_obs}) / (B+1)`.

---

## 6. 분할·평가

- **반복 scaffold OOF cross-validation**: Bemis–Murcko scaffold group 단위, **5 outer fold × 3 반복**. outer test fold는 모델 선택·early stopping·threshold 결정에 사용하지 않는다. RF는 결정적, GIN은 outer fold당 3 training seed 평균.
- **OOF pooling 규칙(중요)**: (i) 반복마다 전체 1,092 약물의 OOF 예측을 완성해 **반복별 macro AP 3개**를 산출하고, (ii) 약물별 3개 OOF score를 평균한 **consensus OOF** 위에서 통계 추론한다. 3개 반복을 3,276행처럼 단순 pool하지 않는다(약물 독립성 과대평가 방지). 반복 간 변동은 별도 보고.
- **Rare-PT fold 제약**: 가능한 모든 outer training set에 PT별 최소 1개(가능하면 3개+) positive, fold 간 label density 편차 최소화, scaffold 중복 절대 불가. 분할 알고리즘·모든 split 파일 공개.
- 기존 seed-42 split은 개발용으로만 보존하며 확증 분석에서 제외. split seed = {201…205} × 3 반복, 스캐폴드 그룹 셔플 후 목표비율 순차배정.

---

## 7. 지표

- **Primary estimand**: global 양성 **≥10인 PT의 macro Average Precision**(consensus OOF), `sklearn.metrics.average_precision_score`, PT별 AP 산술평균. 논문 전반 **macro AP**로 통일("macro PR-AUC" 표현 미사용, PR curve trapezoidal AUC와 혼용 금지).
- **Sensitivity/부지표**: 전체 370 PT macro AP, N∈{5,20}, prevalence bin별 macro AP, label-weighted macro AP, micro AP, prevalence-normalized lift, precision/recall@fixed-budget, calibration(보조), ROC-AUC.
- 양성 1~2개 초희소 PT는 별도 exploratory stratum(주 판정 제외).

---

## 8. 통계 분석계획

- 분석 단위 = **scaffold group / 약물**(seed 아님). Primary contrast = **Δ(M2b − M1b)**, RF family, consensus OOF.
- **Paired scaffold cluster bootstrap** 10,000회 → 95% CI(BCa 또는 percentile 사전고정). cluster 크기 분포·effective number of clusters 보고. drug·size-weighted bootstrap은 sensitivity.
- **Paired sign-flip randomization** — scaffold group 단위 부호 교환, 10,000회, 매 permutation마다 macro AP 재계산(비선형 지표).
- **PT bootstrap(sensitivity)**: endpoint-generalization 추론. Primary는 fixed ≥10 PT(scaffold bootstrap).
- **다중비교 gatekeeping 순서**: ① M2b−M1b(primary, 무보정) ② M2b−P-ID ③ M2b−P-FAM ④ M2b−재배치null ⑤ M2b−M0 ⑥ M2b−RF ⑦ RF+seq−RF ⑧ RQ-int. **②~⑧ Holm 보정.** PT별 검정은 양성 충분 PT에만 formal test + Benjamini–Hochberg FDR 5%, 나머지는 effect size·CI·SOC 요약.
- **Interaction(secondary)**: Δ(M2b−M1b)가 RF vs GIN에서 다른지 검정. 유의하면 family별 효과 분리 보고.
- **Power simulation(구조보존)**: pilot 예측 기반 paired score perturbation, scaffold 크기·PT prevalence·label co-occurrence·M1b/M2b score 상관·CV 변동 보존, 가정 ΔAP 0.01/0.02/0.04, 각 2,000~5,000회.
- **SESOI(다차원)**: |Δ macro AP| ≥ 0.01, 및/또는 상대개선 기준, 및 prevalence-normalized lift 개선, 및 다수 prevalence 층 방향 일관.

### 성공 기준 (사전 고정 — 사후 완화 금지)

**RQ2 성공(RF family primary)** ⟺ consensus OOF `Δ(M2b − M1b)`가 (1) scaffold cluster bootstrap **95% CI 하한 > 0**, (2) scaffold-group sign-flip randomization **양측 p < 0.05**, (3) SESOI 충족.
**Robustness(GIN)**: 방향 동일 + CI 제시(성공 필수조건 아님), RQ-int로 family 차이 평가.
**RQ3 성공** ⟺ `Δ(M2b − P-ID)` **및** `Δ(M2b − P-FAM)`가 (1)·(2) 충족(각각 사전지정, max와 비교 금지).
**RQ4 성공** ⟺ 관측 M2b가 자연 임베딩 재배치 null 대비 `p_emp < 0.05`(global·family-constrained 모두).

### 음성결과 3분 판정 (TOST, 사전 등록)
- **Positive**: CI 하한 > 0 & 효과 ≥ SESOI.
- **Equivalent/negligible**: CI ⊂ [−SESOI, +SESOI].
- **Inconclusive**: CI가 0과 ±SESOI 경계를 모두 초과 → "효과 없음" 아닌 "불확실".

미달 시 음성으로 정직 보고한다. 부지표·특정 층·특정 family만 골라 성공을 주장하지 않는다.
**최소 성립 조건**: RF family에서 RQ2 + (RQ3 또는 C-CAP) + RQ4 + scaffold·약물 수준 CI. RF를 유의하게 능가하지 못해도 이 조건 + target-similarity 전이 + late-fusion 상보성이면 독립 논문 메시지로 본다.

---

## 9. 일반화(shift) 분석

- **연속 유사도 층화(primary)**: test 약물별 max Morgan Tanimoto, 표적 max sequence identity, unseen-target proportion(unweighted·evidence-weighted·mechanism-target indicator·dominant-target-cold). 각 축에서 성능·Δ(M2b−M1b)·Δ(M2b−P-ID) 층화.
- **하드 cold split(stress test, subset 한정)**: 충분한 family/약물 subset에서만 family-disjoint. train/test 크기·coverage·PT 소실 보고.
- **family 정의 다중**: UniRef50(primary) + UniRef30/Pfam·InterPro/ChEMBL class(sensitivity).
- **dual-shift(scaffold+family 동시 미관찰) = exploratory stress test only** — 표본 급감으로 성공 조건에서 제외, point estimate + 넓은 CI, hypothesis-generating 명시.

---

## 10. RF 상보성 / 11. XAI / 12. PU·외부검증

- **RF 상보성(RQ7)**: late-fusion `p_ens = λ·p_RF + (1−λ)·p_seq`, λ는 outer training 내부 valid에서만 선택, λ=0.5 병기. 상관·rank disagreement·상호 정오분석·ensemble−RF Δ·개선 fold 비율. "상보적"은 ensemble>RF 또는 오류 비중복 확인 시에만.
- **XAI(tier-2, 보조)**: 370 PT 전체 Δ분포 우선 → 사전기준 사례선정(성공·실패 모두) → target-level attribution(leave-one-target-out, embedding zero, attention vs occlusion) → molecular attribution(IG·GNNExplainer·RF SHAP). "인과 기전 증명" 표현 금지.
- **PU(보조)**: AP는 observed-label retrieval AP로 정의, PU-loss는 sensitivity, unlabeled high-score를 FAERS/문헌으로 검증, SCAR 가정 명시 주장 회피.
- **외부/시간 검증(tier-3, 본문 최소 1종)**: DailyMed→EMA/EMC transportability 또는 temporal(이후 OnSIDES release 신규약물, 모델 완전 동결) 중 택1. SIDER는 절대 AP 비교 금지·방향 재현만.

---

## 13. 실행 순서·예산

1 표적 mapping 정밀 audit + mean-pool 집계 재계산 → 2 M0·M1·M1b·M2b + P-ID·P-FAM·C-CAP 구현·동결(RF family 우선) → 3 1반복 5-fold OOF(consensus) M2b−M1b 방향 → 4 자연 임베딩 재배치 null → 5 나머지 2반복 → 6 연속 유사도 층화 → 7 GIN robustness + interaction → 8 RF late-fusion·prevalence 층화 → 9 외부/temporal 1종 → 10 통계 동결·표·그림.

**예산**: RF family(primary) 15 fold × {M0,M1,M1b,M2b,P-ID,P-FAM,C-CAP}(결정적). GIN(robustness) 동일 세트 × fold당 1 seed + 대표 3 fold × 5 seed. 하이퍼파라미터 재탐색 금지(pilot A_wd 레시피·PCA-64 그대로). 보조자료 실험은 split 3개 한정. ProtBERT 임베딩 캐시·구조·라벨 재사용, mean 집계본만 신규 산출.

---

## 14. 결과별 허용 주장 규칙 (실험 전 확정)

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

---

## 15. 한계 (정직 보고)

OnSIDES 라벨 0의 비무작위(NMAR) 결측 / seen-target에서 identity와 sequence의 본질적 얽힘(전이 주장은 unseen에서만) / ProtBERT 앞510 절단 49% / 표적 source ChEMBL 단독 하한(BindingDB REST 404 미반영) / dual-shift 표본 부족 / MPS 비결정성으로 절대수치 ±소폭 변동(결론=순위·유의성). 검정력은 RF family primary·GIN robustness 구성으로 확보한다.

---

## 16. 변경 이력 (append-only)

> 형식: `YYYY-MM-DD HH:MM | 변경 | 사유 | 이 시점에 새 split test/OOF를 조회했는가(Y/N)`

- 2026-07-22 | 사전등록서 클린본 확정(내부 doc29 v3.3 기반) | OSF 등록 준비 | **N (새 split 미생성·미조회)**
- ⟨OSF 등록 후 기입⟩ | OSF Registration 완료 | 타임스탬프 동결 | DOI: … | embargo ~투고시 | **N**

---

*본 사전등록서는 지도 회신·방법론 외부검토를 반영해 확정된 확증 설계이다. 확정 후 OSF에 embargo로 등록하며, 등록 DOI·시각을 위 metadata와 §16에 기입한다.*
