# v2_GNN 개선 Round 1a — (다) 손실/불균형 단독

> GIN(정규화 현행 고정: dropout 0.2, weight_decay 0, 3층). 손실/불균형만 5변형 비교.
> 데이터·split·test·301규칙 v1 동일(공정비교 불변). seed=42, device=mps. **valid macro PR-AUC 로만 선택**.
> valid 기준 선택 = **focal_g2_sqrt**.

## 성능 (test) — valid 선택 ★, v1 병기

| 모델 | valid macroPR | test macroPR | **test microPR** | macroROC | hamming |
|---|---|---|---|---|---|
| 1a-raw (대조군=기존 null 재현) | 0.171 | 0.150 | **0.079** | 0.595 | 0.728 |
| 1a-sqrt | 0.154 | 0.100 | 0.267 | 0.564 | 0.958 |
| 1a-clip10 | 0.161 | 0.151 | 0.163 | 0.611 | 0.900 |
| 1a-focal_g2 | 0.159 | 0.128 | 0.291 | 0.592 | 0.959 |
| **1a-focal_g2_sqrt ★** | **0.178** | **0.171** | 0.199 | 0.611 | 0.940 |
| v1-RandomForest | — | 0.188 | 0.320 | 0.617 | 0.959 |
| v1-XGBoost | — | 0.158 | 0.251 | 0.579 | 0.949 |

## 핵심 — micro 붕괴는 캘리브레이션 문제였음 (가설 입증)

진단의 핵심 가설(라벨별 `pos_weight=neg/pos` 과팽창 → micro 캘리브레이션 붕괴)이 **단독으로 확증**됨:

- **raw pos_weight: micro PR-AUC 0.079** (기존 null의 micro 0.106 수준 재현 — 과팽창으로 전역 랭킹 붕괴).
- pos_weight를 **완화/대체하면 micro가 극적으로 회복**: sqrt 0.267, clip10 0.163, focal_g2 **0.291**(RF 0.320에 근접), focal_g2_sqrt 0.199.
- 즉 micro 참패는 GNN 표현력 한계가 아니라 **손실 가중 설정의 미스캘리브레이션**이었다. 정규화·구조는 전혀 안 바꿨는데도 micro만 ~3.7배(0.079→0.291) 회복.

> 트레이드오프: micro를 가장 잘 살리는 focal_g2/sqrt는 macro(희귀 PT 가중)를 일부 희생. **focal_g2_sqrt가 valid macro·test macro 모두 최고**이면서 micro도 raw 대비 2.5배 회복 → 균형점. (선택은 valid 기준이며 결과적으로 test에서도 최선이라 cherry-picking 아님.)

## RQ2 판정 (best=focal_g2_sqrt vs v1 RF)

- mean PR-AUC 0.171 vs 0.188 (Δ−0.017, 142/301 PT 우위).
- **Wilcoxon p=0.086** (paired t p 유사), α=0.05 → **비유의**, 방향 gnn≤rf.
- 1라운드(다) 단독으로는 macro에서 RF를 **아직 못 넘음**(gap −0.021→−0.017로 소폭 축소). macro 격차의 주원인은 과적합 → **(라) 1b의 몫**.

## 빈도 3분위별 best GNN vs v1 RF

| 구간 | PT수 | 양성수 | GNN | RF | 차이 |
|---|---|---|---|---|---|
| 저빈도 | 102 | 10–18 | 0.144 | 0.132 | **+0.013** |
| 중빈도 | 99 | 19–45 | 0.136 | 0.160 | −0.025 |
| 고빈도 | 100 | 46–671 | 0.232 | 0.274 | −0.042 |

- 기존(raw) 대비 **저빈도 우위가 +0.002→+0.013로 확대**, 고빈도 열세는 −0.043→−0.042로 거의 불변.
- 고빈도 열세가 남는 건 과적합 영향 → 1b(정규화/구조)에서 추가 개선 기대.

## 종합

- (다) 단독 성과: **micro 캘리브레이션 붕괴 해소(가설 입증)** + macro 소폭 개선(0.167→0.171). 단 RF 대비 macro는 여전히 비유의 열세.
- 다음: 1a 최적 손실(**focal γ=2 + sqrt pos_weight**) 위에 **(라) 정규화/구조 보강**(weight_decay 1e-4, dropout 0.4, JK/residual)으로 과적합(gap 0.53) 직격 → macro 회복 시도.

> MPS(Apple Silicon) 비결정성으로 run 간 소수점 미세 변동 가능. 공정성: v1 RF는 디폴트(미튜닝) — 최종 판정 시 RF 동등예산 튜닝 필요(한계로 기록).
