# v2_GNN 개선 — STEP 0 진단

> GIN(기존 best 설정: hidden 128×3층, BCE+라벨별 pos_weight, lr 1e-3, weight_decay 0)을
> **early stopping 없이 250 epoch** 재학습하며 epoch별 train/valid macro·micro PR-AUC를 기록.
> 데이터·split·test·301규칙 고정(공정비교 불변). seed=42, device=mps.
> 산출: learning_curve.png / learning_curve.csv / freq_tertile.csv.

## 1. 학습곡선 요약

| 지표 | train(최종 250ep) | valid(최종) | valid 최고 | v1 RF |
|---|---|---|---|---|
| macro PR-AUC | **0.692** | 0.167 | **0.172 @ ep222** | 0.188 |
| micro PR-AUC | **0.508** | 0.128 | — | 0.320 |

- **train↔valid gap = +0.525**(macro). train은 0.69까지 치솟지만 valid는 0.17 부근에서 **정체**.
- **epoch을 늘려도 valid는 개선되지 않음**: 기존 1사이클 early-stop best는 ep111(valid 0.174), 250ep로 늘려도 best는 ep222에서 **0.172로 거의 동일**. 즉 추가 학습분은 전부 train 과적합으로 흡수됨.

## 2. 과적합/과소적합 판정

**강한 과적합(overfitting) 우세.** train macro 0.69 ≫ valid 0.17(gap 0.53). 모델은 train을 충분히 적합(표현력 부족=과소적합 아님)하지만 일반화에 실패. 핵심 원인은 **정규화 부재**(현재 weight_decay=0, dropout 0.2뿐)와 3층 message passing의 over-smoothing 가능성. **단순 epoch 상향((가) 단독)은 효과 없음**이 250ep 실험으로 확인됨.

## 3. PT 양성빈도 3분위별 GIN(기존) vs v1 RF (test PR-AUC 평균)

| 구간 | PT수 | 전체 양성수 범위 | GIN 평균 PR | RF 평균 PR | 차이(GIN−RF) |
|---|---|---|---|---|---|
| 저빈도 | 102 | 10–18 | 0.134 | 0.132 | **+0.002** |
| 중빈도 | 99 | 19–45 | 0.137 | 0.160 | −0.023 |
| 고빈도 | 100 | 46–671 | 0.231 | 0.274 | **−0.043** |

- **저빈도에서는 GIN이 RF와 대등(+0.002)**, 중·고빈도로 갈수록 RF에 크게 뒤짐(−0.023, −0.043).
- **micro PR-AUC 참패(0.106 vs 0.320)**의 정체: micro는 고빈도 PT가 풀을 지배하는데, 바로 그 고빈도 구간에서 GIN이 가장 무너짐. 라벨별 `pos_weight=neg/pos`(고빈도일수록 작지만 여전히 큼)가 확률을 과대 팽창시켜 PT 간 전역 랭킹(=micro)을 망가뜨리는 **캘리브레이션 문제**로 해석됨.

## 4. 결론 — "천장이 아니라 미최적화"

- 표현력 부족(과소적합)은 아님 → GNN 자체 천장 신호 아님.
- **과적합 + 고빈도 PT 캘리브레이션 붕괴**가 핵심 → 정조준 가능한 미최적화.
- 따라서 적용 레버: **(라) 정규화/구조 보강**(과적합 직격)과 **(다) 손실/불균형 재점검**(micro·고빈도 직격)을 1순위로, (가)는 LR 스케줄·patience 상향만 보조로. (나) edge feature는 과적합 상황이라 용량 추가 신중 → 후순위.
