# v2_GNN 결과 요약 (RQ2)

> 분자 그래프 GNN(GCN/GIN/GAT) 멀티라벨 부작용 예측. v1과 동일 master_X/Y + scaffold_split.json + 동일 평가 프로토콜(test 110분자 / 평가 PT 301). device=mps, seed=42, loss=bce, hidden=128×3층.
> **모델 선택은 valid macro PR-AUC 로만** 수행(테스트로 선택하지 않음 — leakage/cherry-picking 방지). valid 기준 최적 = **GIN**.

## 성능 (test) — ★PR-AUC 핵심, v1 병기

| 모델 | valid macroPR | test macro PR-AUC | test micro PR-AUC | macro ROC-AUC | macro F1@0.5 | hamming |
|---|---|---|---|---|---|---|
| GNN-GCN | 0.164 | 0.153 | 0.087 | 0.615 | 0.116 | 0.792 |
| GNN-GIN ★ | 0.174 | 0.167 | 0.106 | 0.617 | 0.126 | 0.791 |
| GNN-GAT | 0.168 | 0.188 | 0.110 | 0.636 | 0.130 | 0.794 |
| GNN-GIN_addpool | 0.148 | 0.137 | 0.067 | 0.602 | 0.100 | 0.675 |
| v1-RandomForest | — | 0.188 | 0.320 | 0.617 | 0.025 | 0.959 |
| v1-XGBoost | — | 0.158 | 0.251 | 0.579 | 0.094 | 0.949 |

## 관찰
- valid-최적 GNN(GIN) test macro PR-AUC 0.167 vs v1 RF 0.188 → 차이 -0.021 (-11.2%). 통계적 유의성은 stats.py(Wilcoxon, RQ2 판정) 참조.
- GNN 3종 valid: GCN 0.164, GIN 0.174, GAT 0.168.
- Ablation: GNN(v2) vs Fingerprint+RF(v1) [위 표], GCN/GIN/GAT 3종 비교, pooling(mean vs add) 변형 포함.

## 재현성 / 한계
- 전역 SEED=42(torch/numpy/random) 고정, 설정 config.yaml 분리.
- **MPS(Apple Silicon) 비결정성으로 run 간 소수점 미세 변동이 있을 수 있음**(GPU 비결정적 누적). 결론(모델 순위·유의성)은 안정적이나 절대 수치는 ±소폭 변동 가능.
- 데이터 규모 작음(train ~870분자) → 분산 큼. RQ2 판정은 PT 단위 Wilcoxon 검정으로.

## 산출물
- metrics_overall.csv (GNN 3종+ablation, v1 RF/XGB 병기)
- metrics_per_pt.csv (valid-최적 GNN PT별)
- pr_curves.png (최적 GNN vs v1 RF micro PR)
- significance_v1_vs_v2.csv (stats.py — RQ2)
