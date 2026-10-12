# 31. v3 표적 mapping 정밀 audit + mean-pool 집계 재계산 리포트

> 생성: `v3_Multimodal/src/target_audit_meanpool.py` (SEED=42, 결정적, **네트워크 호출 0**).
> 근거·설계: `docs/30_preregistration_OSF_clean.md`(§2 mapping audit, §4 집계, §5, §13 실행순서 1번),
> 선행 `docs/20_v3_target_pipeline_report.md`·`docs/19_v3_coverage_report.md`.
> **범위**: 사전등록서 §13 실행순서 **1번(데이터 준비 전용)**. 모델 학습·성능 조회·확증 split(seed 201~205)
> 접근을 일절 하지 않았다. 기존 동결 산출물의 재계산이며 재다운로드·재임베딩·mock·DrugBank가 없다.
> 모든 수치는 `data/processed/target_mapping/audit/*.csv` 및 재계산 `.npy`에 연결된다(traceability).

---

## 0. 요약 (완료 보고)

- **(A) mapping audit 표 7종 생성** — `data/processed/target_mapping/audit/audit_*.csv`. 계산 불가 항목(A-2 source, A-3 confidence·action)은 **날조 없이 gap으로 명시**.
- **(B) mean-pool 임베딩 재계산** — human primary 4종 + all-organism sensitivity 4종(`_meanpool[_all]` 접미), shape `(1092,1024)`/`(1092,)`, master_X cid 정렬 일치 assert 통과.
- **핵심 발견 1**: 기존 `drug_target_emb_mean.npy`(2026-07-11 "출처 불명" 산출)는 **본 human mean-pool과 사실상 동일**(cos=1.0000, max|Δ|=1.43e-06 = float32 누적순서 반올림). → 그 파일의 정체가 human single-protein mean-pool로 **확인**됨.
- **핵심 발견 2**: mean-pool은 기존 top-k affinity 가중(`drug_target_emb.npy`)과 **정의상·수치상 다름**(행별 cos 중앙값 0.995, **최소 0.857**, cos≥0.999 비율 31.8%, max|Δ|=1.76).
- **z-score·PCA·모델학습·확증 split 조회 없음**(사전등록서 §4: raw mean까지만). 구조·라벨·split 불변.

---

## (A) 표적 mapping 정밀 audit

### A-1. 표적 유형 분해  → `audit_target_types.csv`

`03_targets.csv`의 `target_type`별 drug×target 행 수 / 유니크 UniProt / 약물 수(도출 가능).

| category | target_type | 행(drug×target) | 유니크 UniProt | 약물 수 |
|---|---|---|---|---|
| 03_raw | SINGLE PROTEIN | 15,584 | 1,948 | 868 |
| 03_raw | PROTEIN FAMILY | 2,174 | 468 | 258 |
| 03_raw | PROTEIN COMPLEX GROUP | 1,271 | 224 | 80 |
| 03_raw | PROTEIN COMPLEX | 915 | 274 | 133 |
| 03_raw | PROTEIN NUCLEIC-ACID COMPLEX | 663 | 168 | 12 |
| 03_raw | PROTEIN-PROTEIN INTERACTION | 250 | 36 | 111 |
| 03_raw | CHIMERIC PROTEIN | 86 | 22 | 19 |
| 03_raw | (빈값) | 63 | 0 | 63 |
| 03_raw | SELECTIVITY GROUP | 32 | 12 | 12 |
| 03_raw | NUCLEIC-ACID | 30 | 2 | 30 |
| **primary_06_human** (SINGLE PROTEIN ∩ human) | SINGLE PROTEIN | **12,613** | **1,191** | **847** |
| all_06b (SINGLE PROTEIN, 전체 organism) | SINGLE PROTEIN | 15,584 | 1,948 | 868 |

- primary(human single-protein)는 전체 SINGLE PROTEIN(868약물·1,948표적) 중 human만 → 847약물·1,191표적.
- (빈값) 63행 = compound 매칭되었으나 단백질 표적 accession이 전무한 약물(placeholder). SINGLE PROTEIN이 아닌 유형(FAMILY/COMPLEX/…)은 primary·sensitivity 모두에서 제외.

### A-2. binding 근거 vs mechanism-only  → `audit_binding_vs_mechanism.csv`

"binding 근거"=`(chembl_id,uniprot)`가 `05b_affinity_values.csv`에 존재. "affinity 결측"=매핑 human 표적 중 05b 부재. "affinity_imputed=1"=`07_agg_topk`에서 top-k 보충된 mechanism-only 표적.

| axis | scope | drug×target pair | 약물 수 |
|---|---|---|---|
| binding_evidence (05b affinity 존재) | human_primary | 12,514 | 831 |
| affinity_missing (매핑 human 표적 중 05b 부재) | human_primary | 99 | 73 |
| affinity_imputed=1 (07 top-k 보충 표적) | human_primary | 54 | 37 |

- 831약물이 ≥1 binding 근거 표적 보유, 16약물은 근거 전무(831+16=847, A-5와 정합). affinity_imputed는 top-k=5 자리 채우기에서 보충된 부분집합(37약물).

> ⚠️ **gap 명시 (사전등록서 §2 요구의 미충족 부분)**: `03_targets.csv`의 `source`가 **전부 `chembl` 단일값**(유니크 source = `['chembl']`)이라, ChEMBL **mechanism(MoA) endpoint 유래 표적**과 **activity(binding) 유래 표적**을 산출물만으로 명시 구분할 수 없다. 본 표는 **affinity 존재를 mechanism/binding의 proxy**로 사용하며, 이는 **ChEMBL MoA 큐레이션과 동일하지 않다**(mechanism-only 표적이 실제로는 MoA 근거를 가질 수 있음). 명시 구분은 mechanism endpoint 재수집(재다운로드) 시에만 가능 → 후속 캐시 확장 과제.

### A-3. confidence / action coverage  → `audit_value_types.csv` (대체 보조 집계)

> ⚠️ **gap 명시**: target **confidence score**, **action_type**(agonist/antagonist/inhibitor)은 mechanism/action endpoint를 수집하지 않아 **현재 캐시에 없음** → **재다운로드 없이 도출 불가**(후속 캐시 확장 과제). 대체로 `05b`의 `value_types`(assay 유형) 분포를 보조 집계한다.

`05b_affinity_values.csv` (chembl×uniprot) pair의 assay 유형 분포:

| value_type | (chembl,uniprot) pair 수 |
|---|---|
| IC50 | 5,227 |
| AC50 | 4,700 |
| Ki | 3,724 |
| Kd | 3,056 |
| Potency | 2,609 |
| EC50 | 696 |
| ED50 | 15 |

(단일 assay-type 기준 분해; 원본 value_types 조합 분포 상위 15종은 CSV의 `value_types_combo` 그룹 참조.)

### A-4. 약물당 표적 수 분포  → `audit_targets_per_drug.csv`

primary(06_human) 기준(분모 = 전체 1,092), all(06b) 병기.

| scope | 매핑약물 | 중앙값 | IQR(Q1,Q3) | 범위 | 표적 0 | 1 | 2–5 | 6+ |
|---|---|---|---|---|---|---|---|---|
| human_primary | 847 | **7** | (3, 16) | 1–331 | **245** | 92 | 249 | 506 |
| all_organism | 868 | 10 | (4, 21) | 1–340 | 224 | 68 | 218 | 582 |

- 구간 합 = 245+92+249+506 = 1,092 ✓. 중앙값 7(human)·10(all)은 `docs/20` §2와 정합.

### A-5. mapping 실패·제외  → `audit_mapping_failures.csv`

`docs/19` C2~C5, `docs/20`과 교차확인·재현.

| failure_reason | scope | n |
|---|---|---|
| ChEMBL compound 미매칭 | all(1092) | 149 |
| matched이나 SINGLE PROTEIN-UniProt 표적 0 | all_organism(matched 943) | 75 |
| matched이나 human SINGLE PROTEIN 표적 0 | human(matched 943) | 96 |
| human 매핑이나 서열 전무 | human_primary(847) | 0 |
| human 매핑이나 ProtBERT 임베딩 전무 | human_primary(847) | 0 |
| human 매핑이나 affinity 근거 전무 | human_primary(847) | 16 |

excluded target type(SINGLE PROTEIN 아님) drug×target 행: PROTEIN FAMILY 2,174 / PROTEIN COMPLEX GROUP 1,271 / PROTEIN COMPLEX 915 / PROTEIN NUCLEIC-ACID COMPLEX 663 / PROTEIN-PROTEIN INTERACTION 250 / CHIMERIC PROTEIN 86 / SELECTIVITY GROUP 32 / NUCLEIC-ACID 30 (CSV 참조).

**교차확인(재현)**: matched = 1092−149 = **943** = `docs/19` C2(86.4%) ✓. `docs/19` C3=**880**은 **임의 target_type의 UniProt 보유** 약물 수이고, primary/sensitivity가 쓰는 **SINGLE PROTEIN 한정 = 868**(더 엄격)이다(재계산 확인). C4(서열 확보, any-type)=**877** 재현 ✓. human affinity 전무 **16약물** = `docs/20` §1③ 재현 ✓.

### A-6. train/test 표적 overlap (seed-42 **개발** split, 서술적 감사)  → `audit_train_test_overlap.csv`

> ⚠️ 이 overlap은 **개발용 seed-42 split 위 서술적 감사**이며 **확증 split이 아니다**(사전등록서 §6). 성능·예측을 조회하지 않았다.

- **UniProt 표적집합 Jaccard(train vs test union)**: human=**0.447**, all=**0.340**.
- human: train 유니크 표적 1,099 / test 551 / test∩train 510 / **test-only 41**.
- all: train 1,773 / test 687 / test∩train 624 / test-only 63.
- **test 표적별 train 표적과의 max sequence identity**(biopython `PairwiseAligner`, BLOSUM62, local, gap open −11·extend −1, `identities/min(len)`; FASTA=`_cache/` 재사용, **네트워크 0**):
  - test∩train 510표적은 정의상 identity=1.0(동일 서열 train 존재).
  - test-only 41표적(총 **45,018 alignment**): max identity **중앙값 0.362**, **최대 0.929**, **≥0.90 = 2표적**, **<0.40 = 22표적**.
  - 예: P07437(TUBB)↔Q13509(TUBB3) 0.926(β-tubulin isotype). test-only의 과반이 <0.40 → test에 **서열 신규성이 실재**(전이(RQ6) 층화의 근거로만 사용, 성능 조회 아님).

### A-7. 수동 audit 표본 (worksheet only)  → `audit_manual_sample.csv`

- 전체 1,092에서 **seed=42 무작위 8%** 추출 = `ceil(0.08×1092)` = **88개**(np.random.RandomState(42), replace=False, 인덱스 정렬).
- 컬럼: `cid, onsides_ingredient_id, smiles_canonical, inchikey, chembl_id, mapped_human_targets_uniprot, n_human_targets` + **빈 양식** `salt_mismatch, prodrug_mismatch, stereoisomer_mismatch, wrong_target, note`(0/1).
- **에이전트는 직접 판정하지 않았다** — worksheet + 빈 양식만 제공(사람이 채움).
- ⚠️ **약물명 gap**: 큐레이션된 약물명 문자열이 동결 산출물에 없어, `onsides_ingredient_id`(OnSIDES ingredient 식별자, RxNorm 수준)를 대체 식별자로 제공한다(auditor가 RxCUI로 조회).

---

## (B) mean-pool 집계 재계산

**정의(primary, 사전등록서 §4)**: 각 약물의 **`06_targets_human.csv` 상 매핑 human single-protein 표적 전체**에 대해 per-target ProtBERT(1024-d)를 **단순(비가중) 산술평균**. top-k 자르기·affinity 가중 **없음**. 임베딩 없는 표적은 평균에서 제외하되 개수 기록. 부동소수 결정성 = 표적 uniprot 정렬 후 f64 누적 → f32 저장.

### 산출물 (master_X cid 정렬, 재계산)

| 파일 | shape | dtype | 비고 |
|---|---|---|---|
| `drug_target_emb_meanpool.npy` | (1092, 1024) | float32 | human primary. 비매핑/임베딩전무=0 |
| `drug_target_mask_meanpool.npy` | (1092,) | int8 | 매핑 human 표적≥1 **且** 임베딩≥1 → 1 (**847**) |
| `drug_target_coverage_meanpool.npy` | (1092,) | float32 | (임베딩 확보)/(매핑 human 표적), 분모0=0 |
| `drug_n_targets_meanpool.npy` | (1092,) | int32 | 평균에 실제 사용된 표적 수 (중앙값 7·max 331) |
| `drug_target_emb_meanpool_all.npy` 외 3종(`_all`) | 동일 | 동일 | sensitivity(전체 organism); mask **866** |

- human: mask=1 **847/1092**, 매핑 표적有·임베딩전무 **0**, 매핑약물 coverage 평균 **1.000**(모든 매핑 human 표적이 임베딩 보유).
- all: mask=1 **866/1092**(06b 868 중 **2약물**은 매핑 표적 전부 임베딩 전무 → mask=0·coverage=0), coverage 평균 0.993.
- **z-score·PCA-64 미실행**(split별 train-fit이라 이 단계 범위 밖). `fit_scaler_pca(train_idx)`는 **호출되지 않는 주석 스텁**으로만 존재(사전등록서 §4).

### diff (정의 차이 입증)

| 비교 | 대상 | 비교 행 | 행별 cos (평균/중앙/최소) | cos≥0.999 비율 | max\|Δ\| |
|---|---|---|---|---|---|
| mean-pool vs **top-k 가중** | `drug_target_emb.npy` | 847 | 0.990 / 0.995 / **0.857** | 31.8% | **1.761** |
| mean-pool vs 기존 mean | `drug_target_emb_mean.npy` | 847 | 1.0000 / 1.0000 / 1.0000 | 100% | **1.43e-06** |

- **top-k 가중과 정의상 다름 입증**: 다수 약물에서 유의한 벡터 차이(cos 최소 0.857, max|Δ| 1.76). top-k=5·affinity 가중은 표적을 5개로 자르고 pchembl로 가중하지만, mean-pool은 전 표적 균등 → 표적 많은 약물(최대 331)에서 크게 벌어짐.
- **기존 `drug_target_emb_mean.npy` = 본 mean-pool**(max|Δ|=1.43e-06, float32 누적순서 반올림 수준). "출처 불명"이던 파일의 정체가 human mean-pool로 **확인**됨(단, 기존 파일은 덮어쓰지 않고 신규 `_meanpool` 접미로만 저장 — 사전등록서 §제약).

---

## 계산 불가 gap 목록 (날조 없이 명시)

| 항목 | 사유 | 해소 조건 |
|---|---|---|
| A-2 mechanism(MoA) vs binding 명시 구분 | `03_targets.csv` source 전부 `chembl` 단일값; MoA/activity 출처 플래그 미보존 | ChEMBL mechanism endpoint 재수집(재다운로드) |
| A-3 target confidence score | confidence endpoint 미수집(캐시에 없음) | 재다운로드 후 캐시 확장 |
| A-3 action_type(agonist/antagonist/inhibitor) | mechanism/action endpoint 미수집 | 재다운로드 후 캐시 확장 |
| A-7 큐레이션 약물명 문자열 | 동결 산출물에 약물명 없음(ingredient_id만) | RxNorm/외부 사전 조회(수동) |

이들은 본 단계 제약(**재다운로드·네트워크 0**) 때문이며, affinity 존재를 proxy로 쓴 것 외에 임의 대체·추정을 하지 않았다.

---

## 재현 커맨드

```bash
# 의존성: biopython(PairwiseAligner) — requirements.txt 반영
.venv/bin/python3 v3_Multimodal/src/target_audit_meanpool.py
# 결정적: SEED=42, 표적 정렬 후 f64 누적→f32, biopython 결정적, FASTA=_cache/ 재사용(네트워크 0).
# 산출: data/processed/target_mapping/audit/audit_*.csv (7종) + _audit_meanpool_stats.json,
#       data/processed/drug_target_*_meanpool[_all].npy (human 4 + all 4).
```

- 실행 환경: Python 3.14.4(.venv), numpy 2.5.0, pandas 3.0.3, scipy 1.18.0, **biopython 1.87**. SEED=42.
- 소요: A-6 alignment 45,018회 포함 약 3분30초(단일 코어, 결정적).

## 무결성 선언

- **구조·라벨·split 불변**. 재다운로드·재임베딩·재학습·mock·DrugBank **없음**. 네트워크 호출 **0**(FASTA는 `_cache/` 재사용).
- **z-score·PCA·모델 학습·확증 split(seed 201~205)의 test/OOF 조회를 수행하지 않았다**(사전등록서 §4/§5/§13; 코드에 확증 split 로더·모델 없음).
- 기존 npy(`drug_target_emb_mean.npy` 등) **덮어쓰기 없음** — 신규 `_meanpool` 접미로만 저장.
- `data/` 산출물(audit CSV·npy)은 `.gitignore` 대상 → **git 미추적 유지**(커밋 대상 아님). 추적 산출물은 본 리포트 `docs/31...md`뿐.
