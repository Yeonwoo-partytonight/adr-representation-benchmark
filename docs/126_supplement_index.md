# 126 보충 자료 색인 — 그림·보충표 번호 ↔ 출처 (블록 BL)

> 결과 절 초안 `docs/122_results_section_draft_en.md` 의 그림·보충표 번호와 출처 산출물 대응. 번호 규칙 = 결과 절 **첫 언급 순서**(결정 L1·L2 · `docs/126` §0). 본문 표 1~3 = 초안 내 표(번호 불변). 숫자 `1`·`2`·`S1`~`S3` 은 식별자.

| 번호 | 내부 ID | 출처 산출물 | 첫 언급 |
|---|---|---|---|
| Figure 1 | F-NULL (RQ4 재배치 null 분포 · 패널 family·global) | `experiments/runs/v3_unblinding/results/fig_null_realloc.png` (sha256 `8c9f39ce9e415c73…`) · `experiments/runs/v3_unblinding/results/fig_null_realloc.json` (sha256 `246b066700e00d98…`) | [S14] |
| Figure 2 | F-D13 (RQ-int 공유-교환 참조 분포 · 패널 t_star) | `experiments/runs/v3_unblinding/results/fig_d13_rqint_reference.png` (sha256 `efd89fb53bf8cf98…`) · `experiments/runs/v3_unblinding/results/fig_d13_rqint_reference.json` (sha256 `d5c045c6e40e810b…`) | [S24] |
| Table S1 | 미수행·산출불가 등록 항목 (17행) | `docs/126_supp_table_S1_registered_items.md` ← `v3_Multimodal/config/unblinding_plan_v1.json#/prereg_coverage/map` (sha256 `d5aa594b630992fd…`) · `docs/33` 항목 78 | [S76] |
| Table S2 | M2b − M1b 층화 (13층 전부) | `experiments/runs/v3_unblinding/results/results_full.json#/items/SP-STRAT` + `experiments/runs/v3_unblinding/results/sealed_publish/experiments__runs__v3_stratification___sealed__stratification_result.json` (sha256 `cd2969c73ed6bae7…`) | [S49] |
| Table S3 | RQ8 arm별 AP | `experiments/runs/v3_rq8_external/results_rq8.json#/rows` (sha256 `3d18a95db167ed23…`) + `experiments/runs/v3_rq8_external/results_rq8_table.md` (sha256 `836d81f9926c60f3…`) | 표 3 주석 |

- 그림 범례 = 초안 `## Figure legends`(Figure 1·2). 그림 파일은 개봉 시 산출본 그대로(본 블록 재생성 0).
- **S2·S3 표 조판은 원고 통합 단계(본 블록 미수행).** 본 블록은 번호·출처 연결만 확정한다.

## 블록 BM(`docs/127`) 갱신
- 조립 폴더 `paper/v3/`: `figures/Figure_1.png` · `figures/Figure_2.png` · `supplementary/Table_S1.md` · `supplementary/Table_S2.md` · `supplementary/Table_S3.md`. 셀 추적 = `docs/127_supp_tables_fullprecision.csv`. 위 «S2·S3 표 조판 미수행» 은 본 블록으로 해소.

## 블록 BN(`docs/129`) 갱신
- 원고 초안 `paper/v3/manuscript/manuscript_plosone_v0.md` 에서 보충표 표기를 PLOS 형식(`S1 Table`~`S3 Table`)·그림 표기를 `Fig 1`·`Fig 2` 로 치환해 사용. 출처 대응은 위 표 그대로.
