# GraphDTA SOTA 베이스라인 — v2 ADR 멀티라벨(구조-only) 동등조건 비교

> 교수님 지정 SOTA(GraphDTA, Nguyen 2021) 약물 그래프 브랜치 2종(GIN/GAT-GCN)을 v2와 동일 데이터·split·라벨·평가 PT(301)·프로토콜·5시드[1, 2, 3, 4, 42]로 비교. 입력 피처=v2 graph_features 재사용, 학습레시피=A_wd 동일(focal γ2+sqrt pw+wd 1e-4) → **차이는 아키텍처뿐**. device=mps.
> valid 기준 선택(seed42, test 미사용) = **graphdta_gin**. (선택 로그: valid_selection.csv)

## valid 선택 로그 (seed 42, valid macro PR-AUC)

| GraphDTA 변형 | arch | valid macro PR-AUC |
|---|---|---|
| graphdta_gin ★ | gin | 0.1617 |
| graphdta_gatgcn | gatgcn | 0.1066 |

## 비교표 (test, 5시드 mean ± std)

| 모델 | macro PR-AUC | micro PR-AUC |
|---|---|---|
| **GraphDTA-graphdta_gin** | 0.140 ± 0.013 | 0.163 ± 0.011 |
| 튜닝 RF | 0.182 ± 0.001 | 0.294 ± 0.002 |
| 튜닝 GNN (A_wd) | 0.166 ± 0.025 | 0.223 ± 0.016 |
| 디폴트 RF | 0.191 ± 0.002 | 0.322 ± 0.002 |

## 대응검정 + 효과크기

**시드 단위(5시드):**
- vs 튜닝 GNN(A_wd) — macro Δ-0.027 95%CI[-0.045,-0.009] (0포함=False, t p=0.015, dz=-1.83); micro Δ-0.059 (0포함=False, t p=0.001).
- vs 튜닝 RF — macro Δ-0.042 95%CI[-0.058,-0.027] (0포함=False, t p=0.002, dz=-3.40); micro Δ-0.130 (0포함=False, t p=0.000).

**PT 단위(seed 42, 301PT):**
- vs A_wd: GraphDTA 0.141 vs 0.151 (Δ-0.011, GraphDTA 우위 147/301), Wilcoxon p=0.4676, rank-biserial r=-0.049, dz=-0.083.
- vs 튜닝RF: GraphDTA 0.141 vs 0.181 (Δ-0.041, GraphDTA 우위 122/301), Wilcoxon p=0.0000, rank-biserial r=-0.273, dz=-0.224.

## 판정 (방향 무관 정직 보고)
- (i) **GraphDTA도 v2 GIN(A_wd)을 능가하지 못함**(macro Δ-0.027).
- (ii) **GraphDTA도 튜닝 RF(지문)를 능가하지 못함**(macro Δ-0.042). → 최신 SOTA 아키텍처조차 이 규모·분할에서 지문 RF를 못 넘음 = 음성결과·데이터지배 논지 강화.

> 과장 금지: macro(구별 가능 여부)와 micro·안정성을 구분해 해석. GraphDTA PT별은 seed42 기준, A_wd/튜닝RF PT별 산출물 재사용(robustness/round1b·fairtune; MPS 비결정성으로 미세차 가능).

## v3 약물 축 재사용 인터페이스
- `drug_branch.GraphDTAClassifier(protein_encoder=None)` = 본 약물-only 베이스라인.
- v3: `ProteinEncoderStub`를 ProtBERT/1D-CNN 인코더로 교체해 `protein_encoder=`에 주입하면 약물 embed ⊕ 단백질 embed → head로 멀티모달이 활성화된다(현재 배선만, 비활성).
