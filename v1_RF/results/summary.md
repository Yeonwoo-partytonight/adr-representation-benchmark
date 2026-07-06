# v1_RF 베이스라인 결과 요약

> 1단계(논문 비교 대상 baseline). 데이터: master_X/Y (1092 분자 × 370 PT), scaffold split 873/109/110, seed=42.
> 특징: Morgan(ECFP4, r=2/2048bit). 평가: test 110 분자. mol 변환 실패 0개.

## 성능 (test) — ★PR-AUC 핵심

| 모델 | macro PR-AUC | micro PR-AUC | macro ROC-AUC | micro ROC-AUC | macro F1@0.5 | hamming acc | subset acc |
|---|---|---|---|---|---|---|---|
| **RandomForest** | **0.188** | **0.320** | 0.617 | 0.844 | 0.025 | 0.959 | 0.000 |
| **XGBoost** | **0.158** | **0.251** | 0.579 | 0.818 | 0.094 | 0.949 | 0.000 |
| 무작위 기준선(평균 prevalence) | 0.053 | — | 0.500 | 0.500 | — | — | — |

- 평가 대상 PT = 301개 (test 양성 ≥1). test 양성 0 이라 제외된 PT = 69개(A4).
- **핵심 해석**: RandomForest macro PR-AUC 0.188 = 무작위 기준선(0.053)의 약 **3.6배**. 엄격한 scaffold split에서 구조 정보만으로 예측력 확보.
- RF vs XGBoost: macro PR-AUC 0.188 vs 0.158 → **RandomForest** 우세.

## 캐비엇 (논문에 명시)
- **F1@0.5 낮음**: 임계값 0.5는 희소 멀티라벨에 보수적. 임계값-무관 **PR-AUC를 핵심 지표**로 사용. 운영 임계값 최적화는 후속.
- **subset accuracy ~0**: 370개 라벨 동시 정확 일치 기준이라 멀티라벨에서 자연스러운 결과(hamming accuracy 병기). 보고만.
- 데이터 규모 작음(train ~870분자) → 분산 큼. 통계적 유의성 검정은 v2 비교 시 수행.

## 다음 단계에서의 의미
이 표가 **v2_GNN / v3_Multimodal 의 비교 기준선**. 동일 master_X/Y + scaffold_split.json 으로 공정 비교.

## 산출물
- `metrics_overall.csv` — 모델 × 집계 지표
- `metrics_per_pt.csv` — PT별 PR-AUC/ROC-AUC/F1(양성 많은 순)
- `pr_curves.png` — micro PR curve(모델 비교) + 대표 PT PR curve
- 코드: `v1_RF/src/{features,data,train,evaluate}.py`, 설정: `config.yaml`
