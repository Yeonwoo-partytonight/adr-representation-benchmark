# 24. v3 확증 단계 사전등록 (Preregistration)

> **작성 시각**: 2026-07-16
> **작성 근거**: `docs/23_v3_confirmatory_prereg_prompt.md` (확증 단계 단일 기준)
> **선행(탐색)**: `docs/22_v3_ladder_report.md`
>
> ## ★ 이 문서의 지위
> 이 문서는 **새 split의 test 데이터를 단 한 번도 조회하지 않은 시점에 작성·커밋**된다.
> 커밋 이후 **수정하지 않는다.** 불가피한 변경은 본문을 고치지 않고 **§9 변경 이력에 append-only로**
> (변경 시각·사유·결과 조회 여부를 명시하여) 기록한다. 결과를 본 뒤의 가설·주모델·성공기준
> 변경은 금지한다(`CLAUDE.md` §10-2).

---

## 1. 배경 — 왜 확증 단계가 필요한가

`docs/22`의 v3 사다리(M0~M4)와 ablation 6종은 **단일 scaffold split의 동일한 test 110분자**를
반복 조회하며 산출됐다. M0~M4(5) + ablation(6) + cowork 진단까지 누적되어 **해당 test의 독립성은
소진**됐다. 따라서:

- **`docs/22`의 모든 결과를 exploratory(탐색적)로 재분류**한다.
- 본 문서가 정의하는 **새 repeated scaffold split 10개 위에서의 분석만 confirmatory(확증적)**이다.
- exploratory 결과는 가설 생성의 근거로만 쓰고, 확증 판정의 근거로 쓰지 않는다.

확증 설계의 근거가 된 cowork 추가 진단(전부 실측, `docs/23` 참조):

| 진단 | 실측 | 확증 설계에 미친 영향 |
|---|---|---|
| RF(Morgan)+ProtBERT | 0.228 vs Morgan-only 0.189 (Δ+0.038) | 표적 축 이득이 "약한 GNN의 복구"가 아님 → **backbone 2종(RF·GIN) 모두에서 검증** |
| RF+표적 multi-hot 정체 | 0.196 (Δ+0.006) | 구조가 있으면 표적 '정체'는 거의 무기여 → **S2(랜덤 코드) 통제군 필수** |
| RF+organism 전체 | 0.229 (Δ+0.001) | GNN의 A_allorg +0.034가 RF에서 재현 안 됨 → **A_allorg 주모델 승격 금지, ablation으로만** |
| test PT support | 301 PT 중 161개(53.5%)가 양성 1~2개 | macro AP 절대값 해석 취약 → **support 층화 보고 필수** |
| 교란 | Spearman(표적수, ADR수) rho=0.191, p=1.8e-10 | study bias 존재 → **S1 통제군 필수** |

---

## 2. 가설 (사전 고정)

- **H1 (주 가설)**: 표적 단백질 서열(ProtBERT)을 추가하면 구조-only 대비 test macro PR-AUC가
  향상된다. → **`S4 > S0`, 양 backbone(RF·GIN) 모두에서.**
- **H2**: 그 향상은 표적 '정체(identity)'만으로 설명되지 않는다. → **`S4 > S2`.**
- **H3 (방향 미지정, 양측검정)**: PLM 표현이 단순 서열 통계보다 낫다. → **`S4 vs S3`.**

H1·H2는 방향 지정 가설이나 검정은 **양측 Wilcoxon**으로 수행하고(보수적), 방향은 Δ 부호로 판정한다.

---

## 3. 지표 (사전 고정)

- **주 지표**: test **macro PR-AUC** — 평가 대상 = **test에서 양성 ≥1인 PT**
  (기존 v1/v2/v3 exploratory와 비교 가능하도록 프로토콜 유지).
- **부지표(필수 병기)**:
  - support 층화 macro PR-AUC: 양성 **≥2 / ≥5 / ≥10** 층
  - micro PR-AUC (370 PT ravel)
  - macro ROC-AUC
- 주 판정은 **주 지표에만** 근거한다. 부지표는 결론의 강건성 점검·정직 보고용이며,
  주 지표가 미달일 때 부지표로 성공을 주장하지 않는다.

---

## 4. 주 모델 (사전 고정 — 변경 금지)

**S4 = 구조 + ProtBERT PCA-64**, 구성:

| 항목 | 고정값 |
|---|---|
| organism | **human-only** |
| 다중표적 집계 | **affinity 가중 top-k, k=5** |
| 서열 절단 | **앞 510잔기** |
| side feature 차원 | **PCA-64** |
| 융합 | concat |

> **A_allorg(전체 organism)는 주 모델이 아니다.** exploratory에서 GIN 기준 Δ+0.034였으나 RF에서
> Δ+0.001로 재현되지 않았다(단일 split·아키텍처 노이즈 의심). organism은 **ablation으로만** 본다.
> 확증 결과가 어떻게 나오든 A_allorg를 주 모델로 승격하지 않는다.

---

## 5. 사다리 설계 (사전 고정)

**backbone 2종**: (A) **RF-Morgan** (r=2, 2048 bit), (B) **GIN** (GraphDTA 약물 브랜치, A_wd 레시피).
두 backbone이 **동일한 사다리**를 돈다. 변수는 side feature뿐.

| 단계 | side feature | 통제 대상 |
|---|---|---|
| **S0** | 없음(구조만) | 하한선 |
| **S1** | mask + n_targets | 매핑 여부·연구량(study bias) |
| **S2** | 랜덤 per-target 코드 → 동일 집계 → PCA-64 | 표적 **정체** |
| **S3** | 단순 서열 피처 → 동일 집계 → PCA-64 | 서열 **조성·길이**(PLM 없이) |
| **S4** | ProtBERT → 동일 집계 → PCA-64 | **PLM 표현력** |

- **차원 통일**: S2/S3/S4의 side 차원은 모두 **64**로 고정한다. 표현력 비교가 차원 비교로
  오염되지 않게 하기 위함.
- **S2 랜덤 코드**: per-UniProt 랜덤 벡터. **코드 생성 seed 10개**를 사용해 평균±std로 보고한다
  (단일 난수로 결론 내지 않음). 코드 차원 sweep 32/64/128/256은 **split 3개 한정** 별도 보고.
- **S3 단순 서열 피처**: 아미노산 조성(20d) + 서열 길이(1d) + dipeptide 조성(400d) +
  물리화학 요약(net charge, hydrophobicity(GRAVY), aromaticity, MW 등). **ProtBERT와 동일한**
  affinity 가중 top-k(k=5) 집계 → z-score → PCA-64 파이프라인을 통과시킨다.

---

## 6. Split 프로토콜 (사전 고정)

- **repeated scaffold split 10개**, Bemis–Murcko scaffold 기준 **스캐폴드 단위** train/valid/test 배정.
- 비율 **873/109/110** (80/10/10) 유지, ±소폭 허용(스캐폴드 그룹 단위라 정확 일치 불가).
- split 생성 seed = **{101, …, 110}** → `data/processed/splits/scaffold_split_{01..10}.json`.
- **기존 `data/processed/scaffold_split.json`은 변경하지 않는다.** exploratory 결과 대응용으로 보존하며,
  **확증 분석에는 포함하지 않는다.**
- **생성 방식 명시(중요)**: 기존 `pipeline/src/step6_scaffold_split.py`는 큰 스캐폴드 그룹 우선의
  **결정적(deterministic)** 배정이라 seed를 바꿔도 분할이 거의 변하지 않는다. 따라서 repeated split은
  **스캐폴드 그룹을 seed로 무작위 셔플한 뒤 목표 비율까지 순차 배정**하는 방식으로 생성한다.
  스캐폴드 단위 배정(=누수 차단)이라는 성질은 동일하게 유지한다. 이는 결과를 보기 전에 고정된 결정이다.
- **누수 assert 필수**: 동일 스캐폴드가 두 split에 걸치면 실패 처리.
- split마다 **scaler·PCA·집계 통계·모델 선택(early stopping/하이퍼)을 전부 해당 split의
  train/valid에서만 재적합**한다. unmapped 약물은 fit에서 제외 후 transform → mask로 재-0
  (`docs/22`와 동일 논리, assert로 검증).
- 각 split의 **스캐폴드 수·test 분자 수·PT support 분포**를 기록한다.

---

## 7. 통계 분석 계획 (사전 고정)

**분석 단위 = split** (n=10).

- **페어드 비교**: split별 Δ를 계산 → **Wilcoxon signed-rank(양측), n=10**.
  대상: `S4−S0`, `S4−S2`, `S4−S3`, `S4−S1`, `S1−S0`.
  (탐색 단계 n=5는 Wilcoxon p 하한이 0.062라 α=0.05 도달이 원천 불가했음 → n=10으로 해소.)
- **split-level 95% CI** + 효과크기(**rank-biserial** 또는 **Cohen's dz**) 병기.
  이 CI를 일반화 불확실성의 주된 표현으로 삼는다.
- **분산 분해**: 대표 3 split × 5 seed로 **split 간 분산 vs seed 간 분산**을 비교 보고.
- **support 층화**: 주 지표 외 양성 ≥2/≥5/≥10 층에서 동일 검정을 반복. **결론이 층에 따라
  바뀌면 정직하게 보고**한다.
- **PT 수준 분해**: PT별 ΔAP 분포·향상 PT 비율·상위 기여 PT를 보고(소수 PT가 전체를 끌었는지 확인).

### ★ 성공 기준 (사전 고정 — 사후 완화 금지)

**H1 성공** ⟺ 10 split 페어드 비교에서 `S4 − S0`가
1. **Wilcoxon 양측 p < 0.05**, **그리고**
2. **split-level 95% CI가 0을 포함하지 않음**,
3. **양 backbone(RF·GIN) 모두에서** 1·2를 만족.

**H2 성공** ⟺ `S4 − S2`에 대해 위와 **동일 기준** 적용.

**H3**: 방향 미지정. `S4 vs S3` 양측 Wilcoxon p<0.05 & CI 0 불포함이면 유의차 있음으로 보고하고
방향은 Δ 부호로 기술한다. 미달이면 "PLM이 단순 서열 통계 대비 유의한 우위 없음"으로 보고한다.

**미달 시 → 음성으로 보고한다.** 사후에 기준을 바꾸거나, 부지표·특정 층·특정 backbone만 골라
성공을 주장하지 않는다.

### 다중비교에 대한 사전 입장
주 판정은 H1(주 지표·양 backbone)에 한정한다. H2·H3는 부차 가설로, 다중비교 보정을 별도로
적용하지 않되 **탐색적 성격을 리포트에 명시**한다. S1−S0, S4−S1 등 나머지 비교는 기술통계로만 보고한다.

---

## 8. 실행 예산 · 하이퍼파라미터 (사전 고정)

| backbone | 예산 |
|---|---|
| RF-Morgan | 10 split × 5 단계 × **3 seed** |
| GIN | 10 split × 5 단계 × **1 seed** + **대표 3 split × 5 seed**(분산 분해용) |

- **하이퍼파라미터 재탐색 금지.** `docs/22` 설정 그대로 고정:
  - GIN = A_wd 레시피 (focal γ=2 + sqrt pos_weight + weight_decay 1e-4, Adam lr 1e-3,
    batch 32, epochs 200, patience 30, embed_dim 128, dropout 0.2, arch=GIN)
  - PCA_K = 64, top-k = 5
  - RF = v1 디폴트 구성 (Morgan r=2, 2048 bit)
- **모델 선택은 split별 valid만.** test로 선택하지 않는다.

### 계획된 Ablation·Sensitivity (10 split, RF backbone 우선)
1. **safety-panel 표적 제거**(지식 누수 대응): hERG(Q12809), CYP3A4(P08684), CYP2D6(P10635),
   CYP2C9(P11712), CYP2C19(P33261), CYP1A2(P05177), P-gp/ABCB1(P08183) 제거 후 S4 재실행.
   **핵심 = 제거해도 S4>S0가 유지되는가.**
2. **mapped-only 분석**: test를 mapped/unmapped로 나눠 각각 보고.
3. **organism**: human-only(주) vs 전체 — RF·GIN 양쪽 재현 여부.
4. **절단**: 앞510 vs 청크 mean-pool.
5. **집계**: top-k가중 vs 평균 vs top-1.
6. affinity 통계(구 M3), gated 융합(구 M4)은 S4 위 **부가**로만.

### 데이터 재사용 (재계산 금지)
`data/processed/target_mapping/*`, `protbert_emb/*.npy`, `master_X.parquet`, `master_Y.parquet`.
라벨·분자셋 변경 금지. mock 데이터·DrugBank 금지.

---

## 9. 변경 이력 (append-only)

> 형식: `YYYY-MM-DD HH:MM | 변경 내용 | 사유 | 이 시점에 새 split test 결과를 조회했는가(Y/N)`

- 2026-07-16 | 최초 작성·커밋 | 확증 단계 착수 | **N (새 split 미생성, test 미조회)**
