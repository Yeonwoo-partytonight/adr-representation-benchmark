# adr-representation-benchmark

희소 다중라벨 ADR(부작용) 예측에서 **Morgan 지문 RandomForest와 분자 그래프 GNN**을 단일 스캐폴드 분할 조건에서 비교한 벤치마크. KCI 투고 논문의 재현용 코드·설정·데이터 분할을 공개한다.

> *의약품 표지 기반 희소 다중라벨 ADR 예측에서 Morgan 지문 RandomForest와 결합 속성 미사용 GIN 기반 모델의 비교: 단일 스캐폴드 분할 연구.* 한국정보전자통신기술학회논문지 (게재 예정).

## 개요

승인 저분자 의약품의 ADR을 **구조 정보만으로** 예측하는 문제를 구성하고, 데이터·라벨·스캐폴드 분할·평가 지표를 고정한 채 분자 표현(지문 대 그래프)을 비교한다. 라벨은 OnSIDES v3.1.1, 구조는 PubChem에서 취득하여 **1,092개 분자 × 370개 부작용 PT(라벨 밀도 0.0489)**의 희소 다중라벨 문제를 만든다.

핵심 결과: Morgan 지문 RandomForest가 macro PR-AUC 0.191(무작위 기준선의 약 3.6배)에 도달했으나, 분자 그래프 GNN은 5개 시드 모두에서 이를 넘지 못했다(macro 0.166). 이 결과는 RandomForest에 동등 탐색 예산을 주거나 GraphDTA 파생 인코더를 적응해도 유지되었다. **본 데이터 규모와 단일 스캐폴드 분할 조건**에서 얻은 부정적 벤치마크 결과이며, GNN 일반의 실패로 확장하지 않는다.

## 데이터 출처

| 데이터 | 출처 | 용도 |
|---|---|---|
| OnSIDES v3.1.1 | Tatonetti Lab (Columbia/Cedars-Sinai) | ADR 라벨 (y) |
| PubChem | NCBI/NLM | 분자 구조 SMILES (X), CID 공통 키 |

공개 데이터만 사용하였다. 원자료는 각 출처에서 취득하며, 본 리포에는 전처리 산출물과 분할 파일을 포함한다.

## 재현

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

- 전처리 산출물: `data/processed/master_X.parquet`, `data/processed/master_Y.parquet`
- 스캐폴드 분할(고정): `data/processed/scaffold_split.json` (train/valid/test = 873/109/110, Bemis–Murcko 골격 기반)
- 실험 설정: `v1_RF/src/config.yaml`, `v2_GNN/src/config.yaml`
- 시드: `{1, 2, 3, 4, 42}` (기본 42)
- 평가 지표: **PR-AUC(macro/micro) 핵심**, 보조로 ROC-AUC·F1

평가 집합은 양성이 없는 PT를 제외해 370개 중 301개 PT를 macro에 포함하며, 이 집합을 전 모델에 동일 적용한다.

## 실험 환경

Apple M5 Pro (64GB) · PyTorch MPS · Python 3.14.4. 정확한 패키지 버전은 `requirements-lock.txt`(캡처 시점 기준) 참조.
주요 버전: PyTorch 2.12.1, PyTorch Geometric 2.8.0, RDKit 2026.3.3, scikit-learn 1.9.0, XGBoost 3.3.0.

> MPS는 부동소수점 누적의 비결정성으로 동일 시드에서도 절대 수치에 미세 변동이 있어, 다중 시드로 완화하고 결론을 방향 일관성·분산과 함께 보고한다.

## 저장소 구조

```
pipeline/        데이터 파이프라인 (STEP1~7, 공통 모듈)
v1_RF/src/       RandomForest / XGBoost + Morgan 지문 베이스라인
v2_GNN/src/      분자 그래프 GNN (torch-geometric)
scripts/         데이터 취득·검증 스크립트
data/processed/  전처리 산출물 + scaffold_split.json
```

## 라이선스 / 면책

연구 목적 코드. 의료적 판단에 직접 사용 금지. 약물 안전성 정보는 각국 규제기관(FDA/EMA/MHRA/PMDA) 및 의료진을 참고할 것.

---

## v3 (PLOS ONE submission): preregistered controlled representation study

### Overview

The v3 cycle asks a narrower question than the KCI study above: **does a mean-pooled protein
language model (ProtBERT) target embedding carry information about drug-label adverse drug
reaction (ADR) annotation beyond target identity alone?** The design is a preregistered model
ladder with identity and family controls, repeated scaffold splits, confirmatory out-of-fold
(OOF) prediction, a sign-flip null, and a frozen statistical analysis plan (SAP) that was
registered before any confirmatory result was read.

- Manuscript: *Testing mean-pooled protein language model target embeddings beyond target
  identity in drug-label adverse drug reaction annotation: a preregistered controlled
  representation study.*
- Preregistration (OSF): <https://osf.io/5w2uv>
- Archived release DOI (Zenodo): `[to be added after release]`

Numeric results are **not** reproduced in this README. The manuscript is the authoritative
record of every reported value.

### Repository layout (v3)

```
v3_Multimodal/src/          model ladder, controls, late fusion, SAP operators, recording harness
v3_Multimodal/config/       frozen specifications (ladder, seeds, training contract, SAP status)
v3_Multimodal/results/      pilot ladder and drug-graph-encoder baseline metrics
experiments/runs/<run>/      per-run logs, environment fingerprints, public summaries
  .../oof_public/            OOF / consensus predictions released from the sealed trees
  .../sealed_access_log/     the sealed-tree access ledger for that run
experiments/sap/            frozen SAP manifest and hash registry
experiments/rqint/          RQ-int calibration and second-party replication packages
experiments/provenance/     integrity ledger, sign-disclosure matrix, unblinding records
data/processed/             derived labels, structures, target mapping, ProtBERT embeddings, splits
docs/                       research records (Korean; whitelisted file by file)
```

### Reproduction order

1. **Environment** — `pip install -r requirements.txt` (Apple Silicon / PyTorch MPS; see the
   KCI section above for the captured package versions).
2. **Derived data** — target mapping under `data/processed/target_mapping/`
   (`01_inchikey.csv` → `02_chembl.csv` → `03_targets.csv` → `04_sequences.csv` →
   `05_affinity.csv`) and the ProtBERT embeddings aggregated into
   `data/processed/drug_target_emb_meanpool*.npy`.
3. **Repeated scaffold splits** — `data/processed/splits/` holds the frozen fold assignments;
   do not recompute them.
4. **Ladder and control training** — `v3_Multimodal/src/train_ladder.py` and
   `ladder_confirmatory.py`, driven by `v3_Multimodal/config/ladder_freeze.json`.
5. **Confirmatory OOF** — `confirmatory_oof_rep1.py` and the per-arm runners; outputs are the
   `oof_public/` arrays in this repository.
6. **SAP statistics** — `v3_Multimodal/src/sap/` (bootstrap, sign-flip, BCa, decision rules),
   bound to `experiments/sap/manifest.json`.
7. **Tables and figures** — the manuscript's supplementary index lists which record file backs
   each reported quantity.

### Data sources (v3) and how to re-obtain them

| Source | Operator | Role in v3 |
|---|---|---|
| OnSIDES v3.1.1 | Tatonetti Lab (Columbia University Irving Medical Center / Cedars-Sinai) | ADR labels (y) |
| PubChem | NCBI / U.S. National Library of Medicine | compound structures, CID join key |
| ChEMBL | EMBL-EBI | compound–target associations, assay confidence, mechanism annotations |
| UniProtKB | UniProt Consortium | target protein sequences for the ProtBERT embeddings |

`data/raw/` is **not** included in this repository (size and redistribution terms). Download
OnSIDES v3.1.1 from its GitHub releases and re-run the pipeline steps above; compound, target
and sequence records are re-queried from PubChem, ChEMBL and UniProtKB by the scripts in
`v3_Multimodal/src/`. Licensing of the released data and outputs is described in
`LICENSE-DATA.md`.

### What predictions are released

- **Released in full** — every confirmatory out-of-fold prediction that backs a reported
  result: per-replicate and consensus OOF arrays for all ladder, control, tuned-RF, late-fusion
  and sensitivity arms (RF arms, and GIN arms across all three training seeds), plus the
  RQ-int decision input `t_star.npy`. These sit in `experiments/runs/<run>/oof_public/`.
- **Summaries only** — sign-flip null realisations, model checkpoints, partial per-fold
  intermediates and unblinding staging artefacts are not released as raw arrays. The
  corresponding aggregate files (for example
  `experiments/runs/v3_null_MAIN/aggregate_public.json` and
  `experiments/runs/v3_unblinding/results/results_full.json`) are released instead. The reason
  is size and the fact that these intermediates are fully summarised by the released
  aggregates; nothing reported in the manuscript depends on the raw realisations.
- **Not released** — the journal supplementary tables (submitted as S1–S3 Tables), the internal
  working-instruction documents, the pilot-ladder prediction arrays, and the second-party
  transfer archives whose plain-text trees are already released.

The sealed originals themselves stay sealed: `experiments/runs/<run>/oof_public/` holds
**byte-identical copies**, and
`experiments/runs/v3_release_sealed_map.csv` maps every sealed path to its public path with
both SHA-256 digests. Twenty-nine summary files were already published during unblinding under
`experiments/runs/v3_unblinding/results/sealed_publish/` and were not copied again; the mapping
table points at those existing paths.

### Masking notice

The transparency records are released as **masked copies**. Personal identifiers of
non-authors were replaced; author names were not. Replacement tokens:

| Original | Replacement token |
|---|---|
| e-mail address | `<EMAIL>` |
| local part of an e-mail address written on its own, without the domain | `<EMAIL-USER>` |
| external statistical reviewer (non-author) | `<EXTERNAL-REVIEWER>` |
| second-party replication operator (non-author) | `<SECOND-PARTY>` |
| absolute path prefix of the repository checkout | `<REPO_ROOT>/` |
| other absolute paths under the user home directory | `<HOME>/` |
| operating-system account name, where it survives outside a path | `<USER>` |
| Gmail message / thread identifier | `<GMAIL-MSGID>` |

`masking_map.csv` lists every masked file with the pattern applied, the number of
replacements, and the SHA-256 digest **before and after** masking.

> **Logs from the earlier (KCI) stage of this project.** Six run logs
> (`experiments/results/run.log`, `v1_RF/results/run.log`, `v2_GNN/results/run.log`,
> `v2_GNN/results_improve/{diagnose,round1a,round1b}_run.log`) contained the absolute paths of
> the author's working copy. They are masked in this release and are flagged
> `kci_era_already_public=Y` in `masking_map.csv`. The unmasked text remains in earlier commits
> and under the tag `kci-2026-v1.0`; a published commit cannot be withdrawn, so this release
> limits further exposure rather than undoing it.

> **Important.** For the files whose `registry_bound` column is `Y` in `masking_map.csv`, the
> original SHA-256 digest is recorded in the project's hash registries
> (`experiments/sap/manifest.json`, `experiments/provenance/ledger.json`, `docs/33`, `docs/45`).
> Those registry entries refer to the **unmasked originals**, so hashing the published copy will
> not reproduce the registered digest. `masking_map.csv` carries both digests so the binding can
> be checked mechanically.

### Korean-language records

The research records are kept in Korean and are released unchanged except for masking:

| File | Contents |
|---|---|
| `docs/30_preregistration_OSF_clean.md` | the v3 preregistration as registered (the registration of record is on OSF, linked above) |
| `docs/33_prereg_deviation_log.md` | numbered log of every deviation from the preregistration |
| `docs/45_research_integrity_ledger.md` | integrity invariants, chronology, frozen-artefact hash ledger, first-look register |
| `experiments/provenance/ledger.json` | machine-readable chronology, frozen artefacts, external reviews, correspondence |
| `experiments/provenance/sign_disclosure_matrix.json` | which parties could have seen an effect sign, and when |
| `docs/118_unblinding_reporting_plan.md`, `docs/120_unblinding_run_report.md` | unblinding plan and the executed run |
| `docs/05`, `docs/19`, `docs/20`, `docs/31`, `docs/54`, `docs/86`, `docs/105`, `docs/121c`, `docs/126` | pipeline, coverage, target-audit, stratification, reviewer-response and supplement-index records |

**Snapshot point.** The released records are the state as of deviation-log item **96** and
`ledger.json` timeline entry **93**. The entries that record the preparation of this release
itself (item 97, timeline entry 94) are *not* included in the published snapshot, to keep the
snapshot well-defined.

### Sealing and unblinding, in brief

Confirmatory predictions and metrics were written into per-run `_sealed/` trees that no
analysis step was allowed to read without recording the read. Every machine read is one JSON
line in that tree's `access.log`, stating the time, purpose, step, and whether a human saw any
value (`human_exposure`). The statistical analysis plan was frozen, hashed and registered
before any sealed value was inspected. Unblinding happened once, on 2026-10-08, under a
recorded approval; `experiments/provenance/unblinding_approval.json` and
`unblinding_event.json` hold that record.

The published `experiments/runs/<run>/sealed_access_log/access.log` is the ledger of that run,
including the read performed to produce this release. Eight sealed trees never carried a ledger
of their own; for those, the ledger published here contains only this release's read record and
is marked `"ledger_origin": "public_only_no_sealed_ledger"`.

### Citation

See `CITATION.cff`. Cite the manuscript and, where the archived snapshot matters, the Zenodo
DOI for tag `v3-plosone-v1.0` (`[to be added after release]`).

### Licensing (v3)

- Code: MIT (`LICENSE`).
- Data, predictions, results and records: CC BY-SA 4.0 (`LICENSE-DATA.md`), which also lists
  the upstream source terms.

Correspondence: see the corresponding author listed in the manuscript.
