# Paper ID: liang2022sse   <!-- 원고 [4] -->

## 서지정보 (Bibliographic)
- Title: A novel machine learning model based on sparse structure learning with adaptive graph regularization for predicting drug side effects
- Authors: X. Liang, J. Li, Y. Fu, L. Qu, Y. Tan, P. Zhang
- Year: 2022
- Journal/Venue: Journal of Biomedical Informatics, vol. 132, art. no. 104131
- DOI: 10.1016/j.jbi.2022.104131
- PMID: 35840061
- 운영기관/신뢰도: Central South University (Xiangya Hospital, NHC Key Lab). JBI = Elsevier, SCI급. PubMed 색인.

## 연구설계 (Study design)
- Research question: 약물 부작용 예측을 다중라벨 학습으로 풀되 부작용 간 관계를 모델링할 수 있는가?
- Method: sparse structure learning으로 부작용 간 관계 모델링 + adaptive graph regularization으로 약물 데이터의 지역 구조 탐색·다중 특징 융합
- 입력: 약물의 화학구조 + 생물학적 경로(pathway) 특징
- 평가: 교차검증

## 주요 결과 (Main findings)
- Finding 1: 제안 방법이 기존 state-of-the-art 대비 예측 성능을 유의하게 개선.
- Finding 2: 모델이 약물 이웃관계·부작용 관계·부작용 관련 약물 특징을 학습(해석가능).

## 근거 위치 (Evidence locations)
- Abstract: "treats side effect prediction as a multi-label learning problem and uses sparse structure learning to model the relationships between side effects"

## 한계 (Limitations)
- 교차검증 기반(스캐폴드 분할 아님) → 본 연구의 엄격한 분할과 조건이 다름. 화학구조 외 생물학적 특징 필요.

## 본 연구 관련성 (Relevance to our paper)
- Introduction: 부작용 예측이 "다중라벨 학습으로 다루어지며 화학구조·생물학적 특징을 활용한 모델이 제안되어 왔다"는 서술의 출처([5]와 함께).

## 신뢰도 판정 (Reliability judgment)
- Peer reviewed: Yes
- Full text checked: No (초록·PubMed 메타데이터 확인)
- Risk of bias: 낮음

## 검색 메타 (재현성)
- 검색일: 2026-07-14
- 검색 DB / 쿼리: PubMed / "multi-label adverse drug reaction prediction chemical structure machine learning"
