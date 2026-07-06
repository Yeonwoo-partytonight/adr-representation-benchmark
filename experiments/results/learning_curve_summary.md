# 데이터 스케일링(learning curve) 분석 — RF vs GNN

> 목적: "RF>GNN 이 데이터셋이 작아서 생긴 것 아니냐"는 반박 대응. train(873)을 20/40/60/80/100% 로 iterative-stratified subsample(멀티라벨 분포 보존), seed 5개 반복. valid(109)·test(110) 고정. GNN=동등예산 A_wd(GIN), RF=v1 설정. 주지표=test macro PR-AUC.

## 비율별 test macro PR-AUC (mean ± std, seed=5)

| train_fraction | n_train | RF macro PR-AUC | GNN macro PR-AUC | 격차(RF−GNN) |
|---|---|---|---|---|
| 20% | 175 | 0.131 ± 0.018 | 0.119 ± 0.012 | +0.012 |
| 40% | 350 | 0.147 ± 0.010 | 0.130 ± 0.020 | +0.017 |
| 60% | 523 | 0.171 ± 0.008 | 0.142 ± 0.016 | +0.029 |
| 80% | 698 | 0.177 ± 0.008 | 0.159 ± 0.012 | +0.018 |
| 100% | 873 | 0.191 ± 0.002 | 0.170 ± 0.017 | +0.021 |

## 곡선 기울기 (macro PR-AUC 증가율)

| 모델 | 마지막 구간(80→100%) Δ/100분자 | 전체(20→100%) Δ/100분자 |
|---|---|---|
| RF  | +0.0083 | +0.0086 |
| GNN | +0.0063 | +0.0073 |

- GNN 마지막 구간 실제 성능 변화(80%→100%): +0.0111 macro PR-AUC.

## 결론 (3~4줄)

1. **GNN 곡선이 아직 상승 중인가?** → 예, 마지막 구간에서도 상승 중 (80→100% 기울기 +0.0063/100분자). 데이터를 더 주면 개선 여지 있음 → 규모 한계 가능성.
2. **두 모델 격차가 데이터 증가에 따라 좁혀지는가?** → 아니오, 좁혀지지 않음(오히려 유지/확대) (격차 +0.012@20% → +0.021@100%).
3. 전 구간에서 RF macro PR-AUC 가 GNN 을 상회(5/5 비율). 격차가 데이터가 늘어도 유지 → RF 우위는 데이터 규모의 산물이 아니라 이 과제(희소 멀티라벨·소분자)에서의 구조적 특성일 가능성.
4. (한계) MPS 비결정성·소표본으로 절대 수치는 ±소폭 변동 가능. scaffold split 은 v1/v2 와 동일 고정본 사용.

## 재현성 / 산출물
- 전역 seed 고정(42,1,2,3,4), subsample 은 iterative stratification(직접 구현, 시드 고정).
- `results/learning_curve.csv` (model, train_fraction, n_train, seed, macro_pr_auc, macro_roc_auc)
- `results/subsample_indices.json` (fraction→seed→선택 train cid), `results/hyperparams.json`
- `figures/learning_curve.png`
