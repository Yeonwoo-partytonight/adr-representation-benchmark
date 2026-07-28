# A2 — Split 진단 요약 (결과 무참조; 확증 split 미생성)

- 분자 수 N = 1092

## Scaffold group (Bemis–Murcko, step6 정의)

| 지표 | 빈 scaffold 포함 | 빈 scaffold 제외 |
|---|---|---|
| group 수 | 732 | 731 |
| size median | 1 | 1 |
| size p90/p95/p99 | 2/3/6 | 2/3/6 |
| size max | 78 (7.1%) | 78 (7.1%) |
| **N_eff** | 85.3 | 128.1 |

- 빈 scaffold('' 무고리/파싱불가) 그룹 크기 = 77

## PT positive-scaffold 분포 (370 PT)

- distinct positive-scaffold 수: median 19, min 6, max 493

- PT 중 positive-scaffold>0 비율: 100.0% · ≥3 비율: 100.0%

- 최대 단일 scaffold 양성 집중도: median 0.103, max 0.538

## undefined-PT AP 규칙 (사전 고정)

- bootstrap/OOF 평가에서 특정 draw·fold의 test-positive가 0인 PT는 그 draw·fold의 macro 평균에서 제외(average_precision_score 미정의). 제외율(draw별 제외 PT 비율)을 확증 단계에서 보고.

## 확증 fold-level 진단

- DEFERRED — 확증 split(seed 201) 미생성(무결성). fold별 PT 양성 0/1/2/≥3 분포·fold 간 label density·train/test 표적 Jaccard·rare-PT 제약 충족 여부는 docs/36 실행 시 split 생성 후 산출.

