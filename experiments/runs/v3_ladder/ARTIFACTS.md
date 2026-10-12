# v3_ladder — 산출 경로 (CLAUDE.md §10-3)

재현 커맨드: `python v3_Multimodal/src/train_ladder.py` (config = 이 폴더의 `config.json`, SEED {42,1,2,3,4} 고정)

| 항목 | 경로 |
|---|---|
| config·seed·패키지버전 | `experiments/runs/v3_ladder/config.json` |
| 모델×시드 metrics (50행 = 10모델 × 5시드) | `experiments/runs/v3_ladder/metrics.csv` |
| 학습 log | `experiments/runs/v3_ladder/run.log` |
| 청크 임베딩 재계산 log | `experiments/runs/v3_ladder/prep_chunk.log` |
| 사다리 요약표 | `experiments/runs/v3_ladder/comparison_table.csv` |
| 시드 대응검정 | `experiments/runs/v3_ladder/seed_paired_tests.csv` |
| 부트스트랩 CI | `experiments/runs/v3_ladder/bootstrap_ci.json` |
| Ablation 표 | `experiments/runs/v3_ladder/ablation_table.csv` |
| 리포트 | `docs/22_v3_ladder_report.md` |

원본 산출 위치(동일 파일): `v3_Multimodal/results/ladder/`, `v3_Multimodal/results/ablation/`.
PT별 상세·예측 텐서는 원본 위치에만 보관: `*_perpt_seed42.csv`, `*_pred_seed42.npz`.

입력(재계산 금지, 선행 산출 그대로 사용):
`data/processed/drug_target_emb{,_all,_chunk,_mean,_top1}.npy`, `drug_target_mask{,_all}.npy`,
`drug_n_targets{,_all}.npy`, `drug_affinity_stats.npy`, `master_X/Y.parquet`, `scaffold_split.json`(873/109/110),
`data/processed/target_mapping/protbert_emb_chunk/`(940 = truncated==1 서열만 재계산).
