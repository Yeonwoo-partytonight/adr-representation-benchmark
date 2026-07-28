# Paper ID: su2022multilabel   <!-- 원고 [5] -->

## 서지정보 (Bibliographic)
- Title: A multi-label learning model for predicting drug-induced pathology in multi-organ based on toxicogenomics data
- Authors: R. Su, H. Yang, L. Wei, S. Chen, Q. Zou
- Year: 2022
- Journal/Venue: PLoS Computational Biology, vol. 18, no. 9, art. no. e1010402
- DOI: 10.1371/journal.pcbi.1010402
- PMID: 36070305
- 운영기관/신뢰도: Tianjin University / Shandong University / UESTC. PLoS Comput Biol = SCI급. PubMed 색인.

## 연구설계 (Study design)
- Research question: 독성유전체(toxicogenomics) 데이터로 간·신장의 약물유발 병리소견을 다중라벨로 예측할 수 있는가?
- Model: Att-RethinkNet (메모리 구조 + attention, 라벨 연관정보 활용)
- 특징: 화합물 종류·용량·투여시간 고려, 다중 병리소견 동시 예측

## 주요 결과 (Main findings)
- Finding 1: 기존 state-of-the-art 대비 경쟁력 있는 성능으로 간독성·신독성 예측.
- Finding 2: 이전 모델이 병리소견을 개별 예측한 것과 달리 동시 예측(라벨 연관 활용).

## 근거 위치 (Evidence locations)
- Abstract: "it predicts multiple pathological findings at the same time, instead of predicting each pathology separately as the previous model did"

## 한계 (Limitations)
- 입력이 toxicogenomics 데이터(분자 구조-only 아님) → 본 연구와 입력 modality가 다름. 간·신장 2개 장기 한정.

## 본 연구 관련성 (Relevance to our paper)
- Introduction: 약물 안전성 예측이 다중라벨 학습으로 다루어져 왔다는 서술의 보조 출처([4]와 함께). 라벨 간 연관 활용 흐름 제시.

## 신뢰도 판정 (Reliability judgment)
- Peer reviewed: Yes
- Full text checked: No (초록·PubMed 메타데이터 확인)
- Risk of bias: 낮음

## 검색 메타 (재현성)
- 검색일: 2026-07-14
- 검색 DB / 쿼리: PubMed / "multi-label adverse drug reaction prediction chemical structure machine learning"
