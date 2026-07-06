# pipeline/ — 루트 공통 데이터 파이프라인 (v1·v2·v3 공유)

03 명세(`docs/03_data_pipeline_spec.md`) §0.2에 따라, **데이터 파이프라인은 여기 한 곳**에서
STEP1~7을 수행해 `data/processed/`에 산출물을 만든다. 각 단계 모델(`v1_RF/`, `v2_GNN/`,
`v3_Multimodal/`)은 이 산출물(`master_X/Y.parquet`, `scaffold_split.json`)을 **그대로 로드**할
뿐, 라벨·분자셋·split을 재계산하지 않는다. (ablation 표 성립 조건)

## STEP → (예정) 모듈
| STEP | 산출물 | 모듈(예정, `pipeline/src/`) |
|---|---|---|
| 1 | `docs/04_onsides_schema_actual.md` | `scripts/inspect_onsides_schema.py` (완료) |
| 2 | `labels_ingredient_meddra.parquet` | `build_labels.py` |
| 3 | `ingredient_to_cid.parquet`(+unmapped) | `map_ingredient_to_cid.py` (D1 핵심) |
| 4 | `cid_to_smiles.parquet` | `fetch_smiles.py` (PUG-REST; `scripts/fetch_pubchem_smiles.py` 코어 재사용) |
| 5 | `master_X.parquet`, `master_Y.parquet`, `dataset_stats.md` | `build_master.py` |
| 6 | `scaffold_split.json` | `scaffold_split.py` (Bemis-Murcko) |
| 7 | `docs/05_pipeline_report.md` | `report.py` |

## 착수 조건
STEP2~7 코드는 **STEP1 실측 스키마(04) 확보 후** 작성한다. 특히 성분 테이블의 외부 ID
컬럼(RxCUI/UNII/CID)이 STEP3(D1) 매핑 경로를 결정하므로, 그걸 본 뒤 구현한다.

- 전역 SEED=42 고정, 버전 핀, 처리 로그 필수.
- mock 데이터 금지 — 실패 시 멈추고 보고.
