# A3 — RF max_features 감사 (설정 변경 금지 · 문서화)

- 동결 RF 하이퍼: `{'n_estimators': 300, 'max_depth': None, 'n_jobs': -1, 'class_weight': 'balanced_subsample'}` — **max_features 미지정 → sklearn 기본값 = `sqrt`**.
- 즉 각 트리 노드 split마다 후보 = `max(1, int(sqrt(D)))` 개 feature를 무작위 표집(D=전체 feature 차원).

## 모델별 max_features 해석 (seed-42 dev side_dim 기준)

| 모델 | 전체 D | max_features(sqrt) | m/D (임의 feature가 후보일 확률≈) |
|---|---|---|---|
| M1b | 2060 | 45 | 0.0218 |
| M2b | 2124 | 46 | 0.0217 |
| P-ID | 3159 | 56 | 0.0177 |
| P-FAM | 2102 | 45 | 0.0214 |
| C-CAP | 2124 | 46 | 0.0217 |
| M0 | 2048 | 45 | 0.0220 |
| M1 | 2050 | 45 | 0.0220 |
| M2 | 2114 | 45 | 0.0213 |

## primary contrast M1b → M2b (B_seq 64차원 추가) 영향

- M1b: D=2060, max_features=45, 임의 feature 후보확률 ≈ 0.0218
- M2b: D=2124, max_features=46, 임의 feature 후보확률 ≈ 0.0217
- **Morgan/covariate feature가 특정 split의 후보로 뽑힐 확률**은 M1b 0.0218 → M2b 0.0217 로 소폭 변한다(D 증가 → 1/√D 감소). 절대 변화폭 0.00019.
- 후보 개수 자체는 45 → 46 (√D 증가).

## 해석(문서화 — 설정 불변)

- 따라서 **M2b − M1b** 는 '서열 블록(B_seq) 정보' + 'RF feature-subsampling regime의 미세 변화(√D·1/√D)'의 합이다.
- 이는 순수 정보량 인과식별이 아니라 **전체 RF pipeline 증분**임을 명시한다(docs/37 §4 Bucket B 정합).
- **max_features 설정은 pilot 레시피 그대로 유지**(재튜닝 0). 본 감사는 문서화 목적이며 어떤 값도 변경하지 않는다.

