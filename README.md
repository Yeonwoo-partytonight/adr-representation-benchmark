# adr-representation-benchmark

희소 다중라벨 ADR(부작용) 예측에서 **Morgan 지문 RandomForest와 분자 그래프 GNN**을 단일 스캐폴드 분할 조건에서 비교한 벤치마크. KCI 투고 논문의 재현용 코드·설정·데이터 분할을 공개한다.

> *의약품 표지 기반 희소 다중라벨 ADR 예측에서 Morgan 지문 RandomForest와 결합 속성 미사용 GIN 기반 모델의 비교: 단일 스캐폴드 분할 연구.* 한국정보전자통신기술학회논문지 (게재 예정).

## 개요

승인 저분자 의약품의 ADR을 **구조 정보만으로** 예측하는 문제를 구성하고, 데이터·라벨·스캐폴드 분할·평가 지표를 고정한 채 분자 표현(지문 대 그래프)을 비교한다. 라벨은 OnSIDES v3.1.1, 구조는 PubChem에서 취득하여 **1,092개 분자 × 370개 부작용 PT(라벨 밀도 0.0489)**의 희소 다중라벨 문제를 만든다.

핵심 결과: Morgan 지문 RandomForest가 macro PR-AUC 0.191(무작위 기준선의 약 3.6배)에 도달했으나, 분자 그래프 GNN은 5개 시드 모두에서 이를 넘지 못했다(macro 0.166). 이 결과는 RandomForest에 동등 탐색 예산을 주거나 GraphDTA 파생 인코더를 적응해도 유지되었다. **본 데이터 규모와 단일 스캐폴드 분할 조건**에서 얻은 부정적 벤치마크 결과이며, GNN 일반의 실패로 확장하지 않는다.

## 데이터 출처

| 데이터 | 출처 | 용도 |
|---|---|---|
| OnSIDES v3.1.1 | Tatonetti Lab (Columbia/Cedars-Sinai) | ADR 라벨 (y) |
| PubChem | NCBI/NLM | 분자 구조 SMILES (X), CID 공통 키 |

공개 데이터만 사용하였다. 원자료는 각 출처에서 취득하며, 본 리포에는 전처리 산출물과 분할 파일을 포함한다.

## 재현

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

- 전처리 산출물: `data/processed/master_X.parquet`, `data/processed/master_Y.parquet`
- 스캐폴드 분할(고정): `data/processed/scaffold_split.json` (train/valid/test = 873/109/110, Bemis–Murcko 골격 기반)
- 실험 설정: `v1_RF/src/config.yaml`, `v2_GNN/src/config.yaml`
- 시드: `{1, 2, 3, 4, 42}` (기본 42)
- 평가 지표: **PR-AUC(macro/micro) 핵심**, 보조로 ROC-AUC·F1

평가 집합은 양성이 없는 PT를 제외해 370개 중 301개 PT를 macro에 포함하며, 이 집합을 전 모델에 동일 적용한다.

## 실험 환경

Apple M5 Pro (64GB) · PyTorch MPS · Python 3.14.4. 정확한 패키지 버전은 `requirements-lock.txt`(캡처 시점 기준) 참조.
주요 버전: PyTorch 2.12.1, PyTorch Geometric 2.8.0, RDKit 2026.3.3, scikit-learn 1.9.0, XGBoost 3.3.0.

> MPS는 부동소수점 누적의 비결정성으로 동일 시드에서도 절대 수치에 미세 변동이 있어, 다중 시드로 완화하고 결론을 방향 일관성·분산과 함께 보고한다.

## 저장소 구조

```
pipeline/        데이터 파이프라인 (STEP1~7, 공통 모듈)
v1_RF/src/       RandomForest / XGBoost + Morgan 지문 베이스라인
v2_GNN/src/      분자 그래프 GNN (torch-geometric)
scripts/         데이터 취득·검증 스크립트
data/processed/  전처리 산출물 + scaffold_split.json
```

## 라이선스 / 면책

연구 목적 코드. 의료적 판단에 직접 사용 금지. 약물 안전성 정보는 각국 규제기관(FDA/EMA/MHRA/PMDA) 및 의료진을 참고할 것.
