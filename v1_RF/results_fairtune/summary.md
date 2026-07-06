# RQ2 공정성 보정 — RF 동등예산 튜닝 재판정

> 문제: 기존은 '튜닝 GNN(A_wd) vs **디폴트** RF' 불공정 비교. 본 분석은 RF에도 동등예산(16개 구성, sample_seed=42, valid macro PR-AUC로만 선택)을 부여해 재비교.
> 데이터·split·test·301 PT·평가 프로토콜 v2와 동일. seed [1, 2, 3, 4, 42]. GNN 수치는 v2 산출물 재사용(재학습 없음).

## 1. 선택된 RF 구성 (valid 기준, test 미사용)
- config_id=6: n_estimators=1000, max_depth=40, max_features=sqrt, min_samples_leaf=2, class_weight=balanced, FP=(r3,2048b).
- valid macro PR-AUC 최고 0.2059 (16개 구성 전체는 search_log.csv).

## 2. test 성능 (5시드 mean ± std)

| 모델 | macro PR-AUC | micro PR-AUC |
|---|---|---|
| **튜닝 RF** | 0.182 ± 0.001 | 0.294 ± 0.002 |
| 튜닝 GNN (A_wd) | 0.166 ± 0.025 | 0.223 ± 0.016 |
| 디폴트 RF | 0.191 ± 0.002 | 0.322 ± 0.002 |

## 3. 주비교 — 튜닝 RF vs 튜닝 GNN(A_wd)

**시드 단위 대응검정 (5시드):**
- macro: 평균차 +0.015, 95% CI [-0.015, +0.046] (0 포함=True), paired-t p=0.2306, Cohen's dz=+0.632.
- micro: 평균차 +0.071, 95% CI [+0.050, +0.092] (0 포함=False), paired-t p=0.0007, Cohen's dz=+4.244.

**PT 단위 대응검정 (seed 42, 301 PT):** tunedRF mean 0.181 vs tunedGNN mean 0.151 (Δ+0.030, RF 우위 PT 180/301), Wilcoxon p=0.0001 (rank-biserial r=+0.265), paired-t p=0.0033 (Cohen's dz=+0.171).

## 4. 보조비교 — 튜닝 RF vs 디폴트 RF
- 시드 macro 평균차 -0.009, 95% CI [-0.012, -0.007], paired-t p=0.0003.
- PT 단위(seed42): tunedRF 0.181 vs defaultRF 0.188 (Δ-0.007), Wilcoxon p=0.2563, rank-biserial r=+0.077. → 튜닝이 RF를 실제로 움직였는지 확인(동등예산 적용 검증).

## 5. RQ2 재판정
- **핵심: 공정성 보정 후에도 GNN은 RF를 능가하지 못한다.** 점추정상 튜닝 RF macro(0.182) ≥ 튜닝 GNN(0.166)이며 micro는 튜닝 RF(0.294)가 GNN(0.223)을 견고하게 상회(시드 95% CI 0 미포함). RF에 GNN과 동등한 탐색예산을 줘도 우열 방향은 불변 → **RQ2 음성 결과는 공정성 결함이 아니다.**
- **단, macro 차이는 유의하지 않다(marginal).** 튜닝RF−GNN macro 평균차 +0.015의 95% CI가 0을 포함(paired-t p=0.231) → macro에서는 두 모델이 통계적으로 **구별되지 않음**. 'RF가 macro에서 GNN을 압도'한다고 단정 금지(micro·안정성에서만 RF 우위 확정).
- **부수 발견(중요): valid 기반 튜닝이 RF의 test macro를 오히려 낮췄다**(디폴트 0.191 → 튜닝 0.182, 보조비교 macro p=0.0003로 유의). valid macro 최고(0.206)로 선택했음에도 test가 하락 = GNN에서 본 것과 동일한 **소규모 valid/test 불안정**. 따라서 '튜닝RF의 GNN 대비 우위'가 디폴트RF 때(Δ0.025)보다 좁아진 것은 RF가 좋아져서가 아니라 튜닝이 RF를 해쳤기 때문이며, GNN이 경쟁력을 보인 것이 아니다.
- 보수적 종합: **N=1,092·엄격 scaffold split에서는 RF/GNN 간 macro 성능차가 노이즈 수준이고(어느 표현을 택하든 macro는 무의미), micro와 시드 안정성(튜닝RF std 0.001 vs GNN 0.025)에서만 RF가 확정적 우위**. → 방법론(GNN vs RF) 선택보다 데이터 규모·분할이 성능의 지배 요인.

## 6. 프레이밍 함의
- 기존 4.2/결론의 '튜닝 GNN이 디폴트 RF에도 못 미침'은 공정성 결함이 있었음 → 동등예산 비교로 교체.
- 본 결과로 manuscript 4.2·5장의 비교를 '튜닝 RF vs 튜닝 GNN'으로 갱신하고, 효과크기(rank-biserial, Cohen's dz)를 병기할 것.

> 한계: GNN PT별은 round1b A_wd(seed42) 산출물 재사용(robustness seed42 macro 0.152와 MPS 비결정성으로 미세차). isotonic 보정은 본 탐색에 미포함(선택사항, 후속). RF는 동등예산 16구성으로 GNN 12구성에 대응.
