# Paper ID: yang2019chemprop   <!-- 원고 [9] -->

## 서지정보 (Bibliographic)
- Title: Analyzing Learned Molecular Representations for Property Prediction
- Authors: K. Yang, K. Swanson, W. Jin, C. Coley, P. Eiden, H. Gao, A. Guzman-Perez, T. Hopper, B. Kelley, M. Mathea, A. Palmer, V. Settels, T. Jaakkola, K. Jensen, R. Barzilay
- Year: 2019
- Journal/Venue: Journal of Chemical Information and Modeling, vol. 59, no. 8, pp. 3370-3388
- DOI: 10.1021/acs.jcim.9b00237
- PMID: 31361484
- 운영기관/신뢰도: MIT CSAIL 외 (BASF·Amgen·Novartis 공동). JCIM = ACS, SCI급. PubMed 색인.

## 연구설계 (Study design)
- Research question: 계산된 분자 지문/기술자 기반 신경망 vs 그래프 합성곱 신경망 중 무엇이 새로운 화학 공간으로 일반화할 때 우수한가?
- Dataset: 공개 19개 + 산업 독점 16개 데이터셋
- Model: 제안 graph convolutional model(D-MPNN) vs 고정 기술자 기반 모델·기존 그래프 아키텍처

## 주요 결과 (Main findings)
- Finding 1: 최근 문헌은 두 방법 중 어느 쪽이 새로운 화학 공간 일반화에서 우수한지 명확히 결론내지 못했다("recent literature has yet to clearly determine which of these two methods is superior when generalizing to new chemical space").
- Finding 2: 제안 모델은 고정 분자 기술자 기반 모델 및 기존 그래프 아키텍처를 일관되게 대등하거나 능가.

## 근거 위치 (Evidence locations)
- Abstract (PubMed 초록 확인): 위 인용 문구.

## 한계 (Limitations)
- 회귀/분류 물성 예측 태스크 중심. 희소 다중라벨 ADR은 대상 아님. 저자들도 실험 재현성 수준에는 미달이라 명시.

## 본 연구 관련성 (Relevance to our paper)
- Introduction: "그래프 표현이 항상 지문을 능가하지는 않으며, 어느 쪽이 우수한지 확정적이지 않다"는 서술의 근거([7,8]과 함께 인용).
- Discussion(4.2): 그래프 우위 보고가 상이한 조건에서 얻어졌다는 맥락 근거.

## 신뢰도 판정 (Reliability judgment)
- Peer reviewed: Yes
- Full text checked: No (초록·PubMed 메타데이터 확인)
- Risk of bias: 낮음. 단, 저자들이 자체 제안 모델을 평가한 점 유의.

## 검색 메타 (재현성)
- 검색일: 2026-07-14
- 검색 DB / 쿼리: PubMed / lookup_article_by_citation(J Chem Inf Model, 2019, vol 59, p.3370, Yang)
