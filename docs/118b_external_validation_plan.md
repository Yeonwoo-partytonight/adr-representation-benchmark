# docs/118b — RQ8 외부(라벨 출처 이식성) 검증 계획 — 개봉 전 동결본

- 작성: cowork · 2026-10-04 (KST)
- 근거 결정: **H1**(계획만 개봉 전 동결 · 실행은 개봉 후 별도 블록) — `docs/116c` H1~H4 · 본 문서의 설계 선택 **R8-1~R8-3**은 2026-10-04 사용자 결정
- 지위: **tier-3 · 비판정(최소 성립 조건 RQ2 ∧ (RQ3 ∨ C-CAP) ∧ RQ4 에 들어가지 않음) · 다중성 보정 없음 · 결과와 무관하게 전부 보고**
- 결속: 118 계획 JSON `prereg_coverage.RQ8` = `plan_frozen_pre_opening` + 본 문서 sha256 · 119 감사가 본 문서 sha 를 재측정 · 개봉 승인(`unblinding_approval.json`)의 `approved_hashes` 에 포함

---

## 0. 등록 문면과 이번 선택

사전등록 `docs/30_preregistration_OSF_clean.md` §12(줄 162) 축자:
> 외부/시간 검증(tier-3, 본문 최소 1종): DailyMed→EMA/EMC transportability 또는 temporal(이후 OnSIDES release 신규약물, 모델 완전 동결) 중 택1. SIDER는 절대 AP 비교 금지·방향 재현만.

§3 표(줄 57): `RQ8 | 외부·시간 방향 재현? | ΔAP 방향 유지 | tier-3`.

| # | 결정 (2026-10-04 사용자) | 근거 |
|---|---|---|
| **R8-1** | **DailyMed → EMA/EMC 라벨 출처 이식성**을 택한다. temporal 은 택하지 않는다 | OnSIDES 최신 **데이터** release 가 여전히 v3.1.1 이다(v3.2.x 는 코드만 바뀐 release — GitHub release 노트 「This release does not include a data update. The most recent data release is v3.1.1.」). 이후 release 의 신규약물이 존재하지 않으므로 temporal 은 현재 수행할 수 없다 |
| **R8-2** | 외부 정답 = **EU(EMA) ∪ UK(EMC) 합집합이 주**, EU 단독 · UK 단독은 부(보조) | 커버리지(§2-4)와 출처별 이질성을 함께 보고 |
| **R8-3** | 판정 = **부호 일치만**. CI 는 서술적으로 병기하고 p 는 계산하지 않는다 | 등록 문면 「ΔAP 방향 유지」 · tier-3 |

**이 검증이 말하는 것 / 말하지 않는 것 (보고 문면에 축자 전재)**
- 말하는 것: 「US(DailyMed) 라벨로 학습·평가한 Δ(M2b − M1b)의 **방향**이, 같은 약물의 정답을 독립 규제기관 라벨 문서(EMA·EMC)로 바꿔도 유지되는가」 — **라벨 출처(label-source) 이식성**.
- 말하지 않는 것: **새 분자에 대한 일반화가 아니다**(평가 약물은 내부 1,092 의 부분집합이고, 예측은 내부 consensus OOF 그대로다). 시간 이식성이 아니다. 같은 약물의 US·EU·UK 라벨은 서로 상관되어 있으므로 **독립 표본 재현이 아니다**. 절대 AP 를 내부와 비교하지 않는다(등록 「절대 AP 비교 금지」 취지 준용).

---

## 1. 입력 (전부 개봉 전 존재 · 본 문서 동결 시점 sha 고정)

### 1-1. 외부 라벨 원자료 (OnSIDES v3.1.1 · `data/raw/onsides-v3.1.1/csv/`)
| 파일 | 바이트 | sha256 |
|---|---|---|
| `product_label.csv` | 7,808,857 | `77586d3895dd826744912f604c8eca9eef44181d66171c5650b9dc28ba93e329` |
| `product_adverse_effect.csv` | 399,718,339 | `167354272565e7df8eccdfa9592aa4d863999382a01ea438902154663713039b` |
| `product_to_rxnorm.csv` | 839,921 | `0fdd5237a136f1086dcde3ddac56e77847b3e80e7bfafdb540c2e1bd0cc40fc7` |
| `vocab_rxnorm_ingredient_to_product.csv` | 118,648 | `3b07b2f34ba665be6f14cbce3f7c54c25daa8946868470ca868e1d55f9447632` |
| `vocab_meddra_adverse_effect.csv` | 210,126 | `fddc123742cfd3beb215ea0dbfe0bb4edb977792b6c87c949eb66587c90b2661` |
| `vocab_rxnorm_ingredient.csv` | 63,820 | `84e37e2b6b96cd96de556b9bcf4359a7eb322ba8ef3a627fe9666890524e5f7a` |

### 1-2. 내부 매핑·축 (재사용 · 무수정)
| 파일 | 바이트 | sha256 | 용도 |
|---|---|---|---|
| `data/processed/ingredient_to_cid.parquet` | 18,129 | `693dc17c6ae11fc81e568451b7c3ab57a6722e2540b84c8fc27b205e42d8a3fb` | ingredient → CID (`mapping_status == 'ok'`) |
| `data/processed/cid_to_smiles.parquet` | 42,683 | `bc410f2e7f50c5ec5ba2790bc0bcec36f0acfdbe336cf09c2ff9a9643e781c6e` | `valid_flag` · 대표 CID 병합 |
| `data/processed/master_X.parquet` | — | `788c8a64d19e8c3cc030476e7b2eb7f207246e3af6e73304d97f2fc9aa2ae6e6` | 평가 약물 모집단(1,092) |
| `data/processed/master_Y.parquet` | — | `bd23584342de6482e50f218bd409740acc2a00eeac86ee95bd89952bc3d18018` | PT 축 370 · 내부 라벨(서술 비교용) |
| `pipeline/src/step2_labels.py` | — | `533cda042b5827523877af58968c24609972d91c658f40cbb4085a96c110787e` | 라벨 게이트 규칙 정본 |
| `pipeline/src/step5_assemble_master.py` | — | `b245f31b2c7499f79ef9ef37e99a59dc583662915edfce343afa52cfabc4fff4` | CID 병합·OR 결합 규칙 정본 |

### 1-3. 예측 (봉인 · 개봉(120) 이후에만 판독)
- 주: RF consensus `experiments/runs/v3_consensus_rep123/_sealed/consensus_M1b.npz` · `consensus_M2b.npz` — 내부 ① 과 **같은 파일**.
- 부(서술): GIN consensus `experiments/runs/v3_gin_confirm_consensus_rep123/_sealed/consensus_{M1b,M2b}_seed{1,2,42}.npz` — 집계(학습시드 평균 등)는 118 계획 JSON 의 GIN ① 대응 항목과 **같은 규칙**.
- 기대 sha 정본 = 119 감사 `experiments/provenance/pre_unblinding_audit_v3.json` `sealed_sha256`.

---

## 2. 외부 라벨 행렬 구성 — 내부 파이프라인 규칙을 출처만 바꿔 그대로 적용

1. **출처 필터**: `product_label.source ∈ S`, S = {EU, UK}(주) · {EU} · {UK}(부). (내부는 S = {US}.)
2. **매칭 방법**: `match_method == 'PMB'`. 확인 사실: v3.1.1 의 EU·UK 부작용 행은 **전부 PMB**(EU 76,869 · UK 81,978 행 — 2026-10-04 cowork 실측). 실행 시 PMB 외 값이 있으면 그 행은 버리고 개수를 보고한다.
3. **MedDRA**: `meddra_term_type == 'PT'` 만.
4. **단일성분 제품만**: `vocab_rxnorm_ingredient_to_product` 에서 성분 수 1 인 product · label → product → ingredient 브리지(step2 와 같은 식).
5. **(ingredient, PT) 양성** = 위 게이트를 통과한 행이 1개 이상(confidence 임계 없음 — 내부와 동일).
6. **ingredient → CID → 대표 CID**: `mapping_status == 'ok'` · `valid_flag` · 같은 canonical SMILES 는 최소 CID 로 병합 · 약물×PT **OR 결합**(step5 와 동일).
7. **약물 축**: 대표 CID 가 `master_X.cid` 에 있는 약물만(예측이 있는 약물). 내부에 없는 EU/UK 전용 약물은 쓰지 않는다.
8. **PT 축**: 내부 370 PT(`master_Y` 열 순서) 고정. 그 밖의 PT 는 버린다.
9. **평가 약물**: 7 의 약물 중 370 PT 에서 외부 양성이 **1개 이상**인 약물(내부 step5 의 전부-음성 제거와 같은 규칙). 라벨은 있으나 370 PT 양성이 0 인 약물은 개수만 보고하고 제외.
10. **PT 적격(주)**: 평가 약물 중 외부 양성 **≥ 10**(내부 `MIN_POS = 10` 준용) 이고 음성 ≥ 1 인 PT. **민감도**: 양성 ≥ 1 · 음성 ≥ 1.
11. **해석 주의(보고 의무)**: 외부 라벨에 없는 (약물, PT) 는 음성으로 둔다 — 내부와 같은 observed-label 정의(PU 성격). EU/UK 라벨 문서의 서술 관행 차이는 통제하지 않는다.

### 2-4. 커버리지 (2026-10-04 cowork 실측 · 라벨만 · 예측 판독 0)
규칙 1·4·6·7 까지 적용한 `master_X` 약물 수: **EU 327 · UK 478 · EU∪UK 681**(라벨 문서 수 EU 1,021 · UK 2,874). 규칙 9·10 이후 수는 실행 블록에서 처음 산출한다(사전에 PT 별 양성 수를 보지 않았다).

---

## 3. 지표와 Δ

- 지표: macro AP = 적격 PT 별 average precision 의 단순 평균 — 내부 ① 과 **같은 함수**(`sap.metrics.macro_ap`, sha 는 118 F4) 를 평가 약물×적격 PT 부분행렬에 적용.
- **Δ_ext = AP_ext(M2b) − AP_ext(M1b)** (내부 ① 과 같은 방향 · 같은 consensus 예측).
- CI(서술): `sap.bootstrap.paired_scaffold_bootstrap`, `unit="scaffold_cluster"` · seed **6001** · B **10,000**(G1 과 동일) · 평가 약물 부분집합 입력 · 함수 반환의 주 CI 그대로. **p 는 계산하지 않는다**(sign-flip 미수행).
- 같은 절차로 산출하는 행(결과와 무관하게 전부 보고):

| id | 정답 | 모델 | PT 적격 | 지위 |
|---|---|---|---|---|
| **R8-main** | EU∪UK | RF consensus | ≥10 | **판정(tier-3)** |
| R8-eu | EU | RF | ≥10 | 부 · 서술 |
| R8-uk | UK | RF | ≥10 | 부 · 서술 |
| R8-pt1 | EU∪UK | RF | ≥1 | 민감도 · 서술 |
| R8-gin | EU∪UK | GIN consensus | ≥10 | 부 · 서술 |
| R8-int | US(내부 `master_Y`) | RF | 평가 약물 부분집합 · ≥10 | 기준선 · 서술 — 같은 약물 부분집합에서 내부 라벨로 잰 Δ(부분집합 효과와 출처 효과를 구분) |

- 서술 병기: 평가 약물 수 · 적격 PT 수 · 외부/내부 라벨 일치(양성 쌍 Jaccard · 외부에만 있는 양성 쌍 수 · 내부에만 있는 양성 쌍 수).

---

## 4. 판정 (R8-main 1개만)

- 기준 부호 = 개봉(120) 산출의 **내부 ① Δ(M2b − M1b) consensus 점추정 부호**.
- 판정:
  - `sign(Δ_ext) == sign(Δ_①)` 이고 둘 다 0 이 아님 → **「방향 재현」**
  - 그 밖(부호 반대 · 어느 한쪽 정확히 0) → **「방향 비재현」**
  - 적격 PT < **20** 또는 평가 약물 < **100** → **「not_estimable」**(판정 없음 · 사유 보고)
- CI 가 0 을 포함하는지는 **판정에 쓰지 않는다**(서술).
- **공개 사실(맹검 한계)**: 내부 ① 부호는 2026-07-27 최초 조회 이후 연구자가 알고 있다(`experiments/provenance/sign_disclosure_matrix.json`). 본 계획의 설계 선택(R8-1~R8-3 · 적격 기준 · not_estimable 기준)은 그 이후에 정해졌으나 **외부 라벨 쪽 PT 별 분포와 모든 예측값을 보지 않은 상태**에서 정했다. 이 사실을 보고서에 축자 기재한다.

---

## 5. 실행 순서·무결성 (실행 블록 = 개봉(120) 이후 별도 블록)

1. **전제**: 120 완료 · 120 리포트 cowork 검증 PASS · 본 문서 sha == 118 계획 JSON `prereg_coverage.RQ8.sha256` == 승인 기록 `approved_hashes` 값.
2. **E1 라벨 단계(예측 판독 0)**: §1-1·1-2 입력 sha 전수 대조 → §2 규칙으로 외부 라벨 행렬 3종(EU∪UK · EU · UK) + 평가 약물 목록 + 적격 PT 목록을 만들고 sha 를 `docs/33` 새 항목에 **먼저** 기록.
3. **E2 채점 단계**: E1 기록 이후에만 §1-3 예측을 판독 → §3 표 6행 산출 → §4 판정.
4. **독립 검산**: X3 와 같은 방식 — SAP import 없는 소형 구현으로 R8-main 의 Δ_ext 를 재계산해 일치 확인.
5. **금지**: 개봉 후 출처 조합·적격 기준·not_estimable 기준·모델·집계 변경 · 결과에 따른 행 추가/삭제 · R8-main 외 행으로 판정 대체. 변경이 불가피하면 `docs/33` 정정 절차로 원 계획 결과와 **함께** 보고.
6. **기록**: `docs/33` · `docs/45` · `ledger.json` · `first_look_log.json` append-only(기존 블록 관례).

---

## 6. 보고 문면 (결과와 무관한 고정 문장)

- 「RQ8(tier-3)은 사전등록 §12 의 두 선택지 중 DailyMed→EMA/EMC 라벨 출처 이식성으로 수행하였다. 이후 OnSIDES 데이터 release 가 없어 temporal 선택지는 수행할 수 없었다. 평가는 내부 1,092 약물 중 EU 또는 UK 단일성분 라벨이 있는 약물에서, 내부 consensus OOF 예측을 고정한 채 정답만 외부 라벨로 바꾸어 수행하였으며, 새 분자 일반화나 독립 표본 재현을 뜻하지 않는다.」
- 결과 문장은 §4 세 범주 중 하나를 그대로 쓰고, 「입증」·「일반화 확인」·「외부 검증 통과」 표현은 쓰지 않는다.
- 사전등록 이탈 기록: 「§13-9 외부/시간 검증 계획이 개봉 전 구체화되지 않았던 사실 → 2026-10-04 본 문서로 개봉 전 동결(H1)」 을 `docs/33` 에 기재(118 블록 일괄 이탈 기록 H4 와 함께).

---

출처: OnSIDES releases — https://github.com/tatonetti-lab/onsides/releases (v3.2.x 데이터 미갱신 · 최신 데이터 release v3.1.1)
