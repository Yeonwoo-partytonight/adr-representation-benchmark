# STEP 1 — Multi-seed robustness (v2 음성결과 방어)

> A_wd(focal γ2 + sqrt pos_weight + weight_decay 1e-4) vs v1 RF, seed [1, 2, 3, 4, 42] (5/5회). 데이터·split·test·301규칙·프로토콜 v1 동일. 튜닝·변형 없음(seed만 변경).

## 집계 (test, mean ± std)

| 모델 | macro PR-AUC | micro PR-AUC |
|---|---|---|
| GNN A_wd | 0.166 ± 0.025 | 0.223 ± 0.016 |
| v1 RF | 0.191 ± 0.002 | 0.322 ± 0.002 |
| 차이(GNN−RF) macro | -0.025 ± 0.024 | |

## seed별 Wilcoxon (PT별 PR-AUC, GNN vs RF)

| seed | GNN macro | RF macro | Δmacro | Wilcoxon p | 방향 |
|---|---|---|---|---|---|
| 1 | 0.130 | 0.191 | -0.061 | 0.0000 | gnn<rf |
| 2 | 0.188 | 0.194 | -0.006 | 0.4218 | gnn<rf |
| 3 | 0.187 | 0.190 | -0.004 | 0.8652 | gnn<rf |
| 4 | 0.174 | 0.192 | -0.017 | 0.0456 | gnn<rf |
| 42 | 0.152 | 0.188 | -0.036 | 0.0008 | gnn<rf |

- **방향 일관성**: 5/5 seed 에서 GNN < RF.
- **유의성 일관성**: 3/5 seed 에서 Wilcoxon p<0.05.
- 결론: GNN ≤ RF 가 seed 전반에 걸쳐 안정적 → v2 음성결과는 단일 seed 우연 아님.

> MPS 비결정성으로 미세 변동 가능. 공정성: v1 RF는 디폴트(미튜닝) — 튜닝 GNN이 디폴트 RF에도 못 미침이 null을 강화.
