# 20. v3 표적 축 파이프라인 + ProtBERT 임베딩 리포트 (마일스톤 2)

> 생성: `v3_Multimodal/src/target_pipeline.py` (SEED=42, 캐시-우선 재파싱, 네트워크 재수집 없음).
> 선행: `docs/19_v3_coverage_report.md`(게이트 통과). 범위=피처 텐서+임베딩 캐시까지. 모델 학습은 다음 마일스톤.
> 설계 확정: human-only 주 분석 + 전체 organism ablation(`_all`), affinity 가중 top-k(k=5), M1 표적개수 통제군.

## 1. 핵심 수치 (완료 보고용)

- **① pChEMBL 복구**: activity 캐시 재파싱으로 (chembl×uniprot) **15449 pair** 수치 복구(median 집계). 네트워크 재수집 0.
- **② ProtBERT 절단 비율**: 임베딩 1920개 중 **940개 절단(49.0%)** (서열>510잔기, 앞쪽 510잔기만 사용).
- **③ affinity 결측 보충 비율**(human 주): top-k 미달로 mechanism-only 표적을 균등가중 보충한 약물 **37/847 (4.4%)**, 그중 affinity 전무(전부 결측) 약물 **16개**.

## 2. 표적 세트 (STEP1)

- **human(주)**: 분자 847 (커버 77.6%), 유니크 표적 1191, 표적/약물 중앙값 7·95p 51·max 331.
- **all(ablation)**: 분자 868 (커버 79.5%), 유니크 표적 1948, 표적/약물 중앙값 10·95p 63·max 340.

> 참고: 사전추정 human 860 대비 **실측 human 분자 수는 아래 표대로**(정직 보고). 게이트(≥70%)는 유지.

## 3. 교란 통제 (M1 근거) — study bias

| 통계 | 대상 | 값 |
|---|---|---|
| Spearman(n_targets_human, n_ADR) | 전체 1092 | rho=0.191, p=1.78e-10 |
| Spearman(n_targets_human, n_ADR) | 매핑 서브셋(847) | rho=0.136, p=6.84e-05 |
| Spearman(n_targets_all, n_ADR) | 전체 1092 | rho=0.185, p=7.19e-10 |
| Mann-Whitney U (ADR수: 매핑 vs 비매핑) | 847 vs 245 | U=125794, p=3.94e-07 |

- 매핑 약물 ADR 수 중앙값 **14** vs 비매핑 **9**.
- cowork 사전값 rho≈0.193 **재현 여부: 재현(±0.02 이내)**.
- 해석: 표적 수와 ADR 수의 양의 상관은 '많이 연구된 약물=라벨 ADR 많음'이라는 study bias 가능성. → M1(표적 개수-only)을 필수 통제군으로 두고, M2(서열)≈M1이면 ProtBERT 서열이 study bias 이상을 기여하지 못한 것으로 판정.

## 4. split별 표적 커버리지·n_targets (편향 재확인)

| split | 분자수 | 매핑 | 커버% | n_targets 중앙값(매핑) |
|---|---|---|---|---|
| train | 873 | 671 | 76.9% | 7 |
| valid | 109 | 86 | 78.9% | 10 |
| test | 110 | 90 | 81.8% | 6 |

## 5. 산출물

```
data/processed/target_mapping/
  05b_affinity_values.csv  (chembl_id, uniprot, pchembl_median, n_records, value_types, organism)
  06_targets_human.csv / 06b_targets_all.csv  (cid, chembl_id, target_chembl_id, uniprot, organism)
  07_agg_topk.csv / 07b_agg_topk_all.csv  (cid, uniprot, rank, pchembl_median, weight, affinity_imputed)
  protbert_emb/<uniprot>.npy  (1024, float32, 잔기 평균 pooling)
  protbert_index.csv  (uniprot, seq_len, truncated, emb_path)
data/processed/
  drug_target_emb.npy   (1092,1024) float32  — top-k 가중평균, 비매핑=zero  [human 주]
  drug_target_mask.npy  (1092,) int8         — 표적보유=1
  drug_n_targets.npy    (1092,) int32        — M1 통제군(human)
  drug_target_emb_all.npy / _mask_all / drug_n_targets_all.npy  — 전체 organism ablation
```

재실행: `python v3_Multimodal/src/target_pipeline.py --step all` (SEED=42, 캐시 결정적).

## 6. 한계 (정직 보고)

- **ProtBERT 절단**: 49.0% 서열이 510잔기 초과로 절단됨(중앙값 490·95p 1435·max 7096 aa). 긴 단백질의 C-말단 정보 손실 → 논문 한계. 512-청크 mean-pool은 ablation 후보(미구현).
- **affinity 집계**: 동일 compound×target 다중 assay는 median(pchembl) 채택. mechanism 유래 표적은 affinity 결측 → top-k 미달 시 균등 가중 보충(비율은 §1③).
- **BindingDB 미반영**(coverage 단계 REST 404) → 표적/affinity는 ChEMBL 단독 하한.
- **study bias**(§3): 표적 정보의 이득이 생물학이 아닌 연구 인기도 아티팩트일 수 있음 → M1 통제 필수.
- 구조·라벨·split 불변, 재학습/재다운로드 없음.
