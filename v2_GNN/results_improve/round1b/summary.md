# v2_GNN 개선 Round 1b — (라) 정규화/구조 (손실 고정 focal γ2+sqrt)

> GIN, 1b 변형 비교(손실 고정=focal γ2+sqrt pos_weight). 데이터·split·test·301규칙 v1 동일. seed=42, device=mps. valid 기준 선택 = **A_wd**.

## 성능 (test) — valid 선택 모델 ★, v1 병기

| 모델 | valid macroPR | test macroPR | test microPR | macroROC | hamming |
|---|---|---|---|---|---|
| 1b-A_wd ★ | 0.186 | 0.151 | 0.210 | 0.607 | 0.940 |
| 1b-B_wd_drop | 0.152 | 0.144 | 0.267 | 0.615 | 0.954 |
| 1b-C_wd_drop_jk | 0.154 | 0.151 | 0.275 | 0.624 | 0.955 |
| 1b-D_wd_drop_res | 0.169 | 0.159 | 0.268 | 0.616 | 0.955 |
| v1-RandomForest | — | 0.188 | 0.320 | 0.617 | 0.959 |
| v1-XGBoost | — | 0.158 | 0.251 | 0.579 | 0.949 |

## RQ2 판정 (best vs v1 RF)
- mean PR-AUC 0.151 vs 0.188 (Δ-0.037, 139/301 PT 우위)
- **Wilcoxon p=0.00194** (paired t p=0.000489), α=0.05 → **유의**, 방향 gnn<=rf

## 빈도 3분위별 best GNN vs v1 RF
| 구간 | PT수 | 양성수 | GNN | RF | 차이 |
|---|---|---|---|---|---|
| 저빈도 | 102 | 10–18 | 0.132 | 0.132 | +0.000 |
| 중빈도 | 99 | 19–45 | 0.110 | 0.160 | -0.050 |
| 고빈도 | 100 | 46–671 | 0.212 | 0.274 | -0.062 |

## train↔valid gap (과적합 추적, 기존 raw GIN gap≈0.53)
| 변형 | train macroPR | valid macroPR | gap |
|---|---|---|---|
| A_wd ★ | 0.258 | 0.186 | +0.072 |
| B_wd_drop | 0.200 | 0.152 | +0.048 |
| C_wd_drop_jk | 0.208 | 0.154 | +0.054 |
| D_wd_drop_res | 0.290 | 0.169 | +0.120 |

> MPS(Apple Silicon) 비결정성으로 run 간 소수점 미세 변동 가능. 공정성: 비교 대상 v1 RF는 디폴트 설정(미튜닝) — 최종 판정 시 RF 동등예산 튜닝 필요(한계로 기록).
