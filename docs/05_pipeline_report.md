# 05. 데이터 파이프라인 최종 보고 (STEP7)

생성: 2026-06-24  ·  판정: **PASS**

## 방침 요약 (이번 사이클 확정)
- 라벨 소스 = **US(DailyMed) 단독** (JP=문자열매칭 제외, UK/EU 미사용)
- MedDRA = **PT 레벨만**
- 부작용 귀속 = **단일성분 제품만** (콤보 약물 모호성 제거)
- 매핑 = RxCUI/name → PubChem CID  ·  SMILES = PUG-REST + RDKit 표준화
- 분할 = Bemis-Murcko scaffold 80/10/10, seed=42

## STEP별 입력→출력
| STEP | 산출 | 규모 |
|---|---|---|
| 2 라벨 | labels_ingredient_meddra | 성분 1,115 × (양성쌍 23,111) |
| 3 CID매핑 | ingredient_to_cid | 성공 1,115/1,115 = **100.0%** |
| 4 SMILES | cid_to_smiles | 유효 1,111/1,111 = 100.0% |
| 5 마스터 | master_X / master_Y | 분자 **1,092** × PT **370** |
| 6 split | scaffold_split.json | train 873 / valid 109 / test 110 |

## 최종 데이터셋
- 분자 N = **1,092**, 부작용 PT M = **370**
- 라벨 밀도 = **0.0489** (멀티라벨 이진)
- 분자당 평균 양성 PT = 18.1

## 검증 체크리스트
- [x] OnSIDES v3.1.1 무결성(threshold)
- [x] CID 매핑 커버리지 ≥50% (100.0%)
- [x] 유효 SMILES 확보 (1,111)
- [x] scaffold split 비율 근사(80/10/10)
- [x] train/valid/test 모두 비어있지 않음 (873/109/110)
- [x] 라벨 매트릭스 비어있지 않음

## 산출물
`data/processed/`: labels_ingredient_meddra.parquet, ingredient_to_cid.parquet(+unmapped_ingredients.csv),
cid_to_smiles.parquet, master_X.parquet, master_Y.parquet, scaffold_split.json, dataset_stats.md, dropped_rare_pts.csv

## 다음 단계
**PASS** → v1_RF 모델 코드 착수 가능 (Morgan FP + RF/XGBoost).
DrugBank 재개 시 v3 표적축(CID→UniProt→ProtBERT) 통합.
