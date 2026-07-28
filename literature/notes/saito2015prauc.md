# Paper ID: saito2015prauc   <!-- 원고 [12] -->

## 서지정보 (Bibliographic)
- Title: The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets
- Authors: T. Saito, M. Rehmsmeier
- Year: 2015
- Journal/Venue: PLoS ONE, vol. 10, no. 3, art. no. e0118432
- DOI: 10.1371/journal.pone.0118432
- PMID: 25738806
- 운영기관/신뢰도: University of Bergen (Computational Biology Unit). PLoS ONE = SCI급 peer-review. PubMed 색인.

## 연구설계 (Study design)
- Research question: 불균형 데이터에서 ROC plot이 분류기 성능 해석을 오도하는가?
- Study type: 방법론/비교 연구 (Comparative Study)
- Metrics: ROC, Precision-Recall(PRC)

## 주요 결과 (Main findings)
- Finding 1: 불균형(음성≫양성) 상황에서 ROC plot의 시각적 해석은 specificity에 대한 직관적이지만 잘못된 해석 때문에 성능 신뢰도를 오도할 수 있다.
- Finding 2: PRC plot은 양성 예측 중 참양성 비율을 평가하므로 향후 분류 성능을 더 정확히 예측한다.

## 근거 위치 (Evidence locations)
- Abstract (PubMed 초록 확인): "the visual interpretability of ROC plots in the context of imbalanced datasets can be deceptive ... PRC plots, on the other hand, can provide the viewer with an accurate prediction of future classification performance"

## 한계 (Limitations)
- 일반 이진분류 관점 논문. 다중라벨/ADR 특화 분석은 아님.

## 본 연구 관련성 (Relevance to our paper)
- Methods(2.3): "핵심 지표는 PR-AUC" 선택의 방법론적 근거.
- Discussion(4.2): RF의 ROC-AUC(0.617/0.844) ≫ PR-AUC(0.188) 격차가 "불균형에서 ROC-AUC가 후하게 보인다"는 기존 지적과 부합한다는 서술의 근거.

## 신뢰도 판정 (Reliability judgment)
- Peer reviewed: Yes
- Full text checked: No (초록·PubMed 메타데이터 확인)
- Risk of bias: 낮음(널리 인용되는 방법론 표준)

## 검색 메타 (재현성)
- 검색일: 2026-07-14
- 검색 DB / 쿼리: PubMed / "precision-recall plot more informative than ROC plot imbalanced datasets"
