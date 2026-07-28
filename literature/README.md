# literature/ — 문헌·근거 추적

Claude가 **기억이 아니라 파일에서** 인용·근거를 가져오게 만드는 폴더.

```
literature/
├── pdf/              # 원문 PDF (git 커밋 금지 — 용량·저작권)
├── notes/            # 논문별 Evidence Note (_TEMPLATE.md 복사해서 <citekey>.md)
├── search_results/   # 검색 결과 원본 CSV (query·date·db 헤더 포함)
├── screening.csv     # 제목·초록 1차 선별표 (include/exclude + 사유)
└── evidence_table.csv# ★ 원고 주장 ↔ 출처 매핑 (claim_id 기준)
```

## 원칙
- **검색 결과 제목 ≠ 실제 주장.** 초록 최소 확인, 핵심 주장은 전문 확인 후에만 evidence_table에 "확인" 표기.
- 원고 문장의 claim_id ↔ evidence_table 행이 1:1로 연결돼야 한다.
- 인용키(source_key)는 `references.bib`의 안정적 citekey와 동일하게.

## 흐름
literature-reviewer가 채우고 → manuscript-reviewer가 evidence_table을 근거로 인용 → evidence-checker가 대조 감사.
