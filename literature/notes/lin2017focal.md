# Paper ID: lin2017focal   <!-- 원고 [14] -->

## 서지정보 (Bibliographic)
- Title: Focal Loss for Dense Object Detection
- Authors: T.-Y. Lin, P. Goyal, R. Girshick, K. He, P. Dollár
- Year: 2017
- Journal/Venue: Proceedings of the IEEE International Conference on Computer Vision (ICCV), pp. 2999-3007
- DOI: 10.1109/ICCV.2017.324
- PMID: 없음(컴퓨터비전 학회 논문 — PubMed 미색인)
- 운영기관/신뢰도: Facebook AI Research (FAIR). ICCV = 컴퓨터비전 top-tier 학회(공신력 있는 국제학술대회).

## 연구설계 (Study design)
- Research question: 극단적 전경-배경 클래스 불균형이 dense detector의 정확도를 제한하는 문제를 손실함수로 해결할 수 있는가?
- Method: Focal Loss — cross-entropy에 (1-p_t)^γ 변조항을 곱해 easy negative의 기여를 낮추고 hard example에 집중. γ가 down-weighting 강도를 제어(논문 기본 γ=2).

## 주요 결과 (Main findings)
- Finding 1: 클래스 불균형이 one-stage detector 정확도의 핵심 원인이며, Focal Loss가 이를 완화.
- Finding 2: RetinaNet이 기존 one-stage/two-stage 대비 SOTA 달성.

## 근거 위치 (Evidence locations)
- ICCV 2017 Open Access(openaccess.thecvf.com) 및 dblp 서지 확인.

## 한계 (Limitations)
- 원 도메인은 객체 탐지(비전). 본 연구는 이를 희소 다중라벨 화학 데이터에 차용한 것으로, 도메인 전이의 최적성은 원 논문이 보증하지 않음.

## 본 연구 관련성 (Relevance to our paper)
- Methods(2.1·2.2): GNN 불균형 보정에 쓴 "초점 손실(Focal Loss, γ=2)"의 출처. 기존에 인용 없이 사용되던 방법 → 감사에서 보강.

## 신뢰도 판정 (Reliability judgment)
- Peer reviewed: Yes (ICCV)
- Full text checked: No (학회 공식 페이지·dblp 서지 확인)
- Risk of bias: 낮음(널리 채택된 표준 손실함수)

## 검색 메타 (재현성)
- 검색일: 2026-07-14
- 검색 DB / 쿼리: WebSearch / "Focal Loss for Dense Object Detection ICCV 2017 DOI pages" → ICCV Open Access, dblp 교차확인
