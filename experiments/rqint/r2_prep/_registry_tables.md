
### ① SAP 11모듈

| 경로 | sha256[:16] | bytes | 이미 등재된 곳 | 비고 |
|---|---|---|---|---|
| `v3_Multimodal/src/sap/__init__.py` | `8dc63e28ffcf93dc` | 1,635 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/metrics.py` | `a7d3fe4fe9e87983` | 4,256 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/redaction.py` | `4d4bf221141fbc79` | 3,647 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/consensus.py` | `9bddb53da5752c46` | 3,124 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/bootstrap.py` | `05437c516e606a05` | 14,214 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/signflip.py` | `3de1223585ae0f97` | 6,772 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/decision.py` | `f688b20d816acabe` | 16,353 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/null_generator.py` | `90886abce256a130` | 11,119 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/unseen_target.py` | `96c0c87911e8c93d` | 5,610 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/synthetic.py` | `ddf715e6fba7503e` | 8,444 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |
| `v3_Multimodal/src/sap/freeze.py` | `94e6369fa952be7f` | 42,927 | manifest.modules · ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 등재 |

### ② RQ-int 3모듈

| 경로 | sha256[:16] | bytes | 이미 등재된 곳 | 비고 |
|---|---|---|---|---|
| `v3_Multimodal/src/sap/rqint.py` | `eb842bc98140e9c5` | 12,970 | docs/45 §3 | 블록 AC 산출 · SAP 미등재 |
| `v3_Multimodal/src/sap/rqint_audit.py` | `ddffe6d128de4d18` | 19,573 | docs/45 §3 | 블록 AC 산출 · SAP 미등재 |
| `v3_Multimodal/src/sap/rqint_synthetic.py` | `27ef0011ee041920` | 5,572 | docs/45 §3 | 블록 AC 산출 · SAP 미등재 |

### ③ config 동결파일

| 경로 | sha256[:16] | bytes | 이미 등재된 곳 | 비고 |
|---|---|---|---|---|
| `v3_Multimodal/config/a5_boundary_amendment.json` | `860f5a4529dfb57b` | 5,667 | **미등재** |  |
| `v3_Multimodal/config/a5_mechanism_freeze.json` | `3419b2f793d74051` | 5,340 | docs/45 §3 |  |
| `v3_Multimodal/config/a5_stratum_label_supersede.json` | `ac187375d2a7c16e` | 5,176 | **미등재** |  |
| `v3_Multimodal/config/b_100k_prespec.json` | `e7406c23b8d61b0c` | 7,916 | docs/45 §3 |  |
| `v3_Multimodal/config/b_dryrun_prespec.json` | `9a2545eb0d897f30` | 9,191 | docs/45 §3 |  |
| `v3_Multimodal/config/gin_inner_valid_freeze.json` | `038599c3e1576022` | 6,913 | docs/45 §3 |  |
| `v3_Multimodal/config/gin_inner_valid_freeze.status.json` | `bd329fefe613971f` | 677 | docs/45 §3 |  |
| `v3_Multimodal/config/gin_seed_freeze.json` | `10828447c6d33118` | 4,637 | docs/45 §3 |  |
| `v3_Multimodal/config/holm7_latefusion_freeze.json` | `d89f8c52412b656e` | 7,424 | docs/45 §3 |  |
| `v3_Multimodal/config/ladder_freeze.json` | `b885585aefbabb32` | 16,896 | ledger.frozen_artifacts · docs/45 §3 |  |
| `v3_Multimodal/config/post_interim_freeze_v1_0.json` | `502db732bd5e45cb` | 10,844 | docs/45 §3 |  |
| `v3_Multimodal/config/post_interim_freeze_v1_0.status.json` | `dbb00d540d7436e5` | 4,628 | **미등재** |  |
| `v3_Multimodal/config/r3_second_party_freeze.json` | `0624d3ddb852c4e9` | 12,192 | docs/45 §3 |  |
| `v3_Multimodal/config/reviewer_identity_resolved.json` | `981abdfa296805f4` | 7,224 | **미등재** |  |
| `v3_Multimodal/config/rf_tuned_freeze.json` | `c1ef6406fbb48b7f` | 3,970 | docs/45 §3 |  |
| `v3_Multimodal/config/rqint_procedure_decisions_v0.json` | `951b302a2d474361` | 21,502 | docs/45 §3 |  |

### ④ B·시드집합·대표폴드·실패처리 소재

| 경로 | sha256[:16] | bytes | 이미 등재된 곳 | 비고 |
|---|---|---|---|---|
| `v3_Multimodal/src/sap/rqint.py` | `eb842bc98140e9c5` | 12,970 | docs/45 §3 | `B_DEFINITION_STATUS` L63-64 = `still_unspecified` (B 의 유일한 소재) |
| `v3_Multimodal/config/gin_seed_freeze.json` | `10828447c6d33118` | 4,637 | docs/45 §3 | 대표 outer unit 3 · training_seeds_ordered 5 · confirmatory_seed_prefix 3 · 예비/안정성 시드 |
| `v3_Multimodal/config/rqint_procedure_decisions_v0.json` | `951b302a2d474361` | 21,502 | docs/45 §3 | D17 실패처리 규칙 축자(L169) · `status` = decisions_recorded_not_frozen |
| `v3_Multimodal/config/b_100k_prespec.json` | `e7406c23b8d61b0c` | 7,916 | docs/45 §3 | (가) 해석 실주행 사전명시 — B 판정식 2분기 |
| `v3_Multimodal/config/b_dryrun_prespec.json` | `9a2545eb0d897f30` | 9,191 | docs/45 §3 | (나) 해석 드라이런 사전명시 · 외삽 정책 |
| `experiments/rqint/calibration_design.json` | `42e2f8f9f3f24ec1` | 18,693 | docs/45 §3 | C0~C3 복제수 primary 2,000 / sensitivity 1,000 · A12 · F_ACC |

### ⑤ 사전등록·개정문·원장 문서

| 경로 | sha256[:16] | bytes | 이미 등재된 곳 | 비고 |
|---|---|---|---|---|
| `docs/30_preregistration_OSF_clean.md` | `cdbaa7e69e654a36` | 18,434 | ledger.frozen_artifacts · docs/45 §3 | OSF 사전등록 정본 (immutable) |
| `docs/55b_rqint_external_statreview_package_v2.md` | `21f71e0fbfa3c4d1` | 45,610 | **미등재** | 외부검토 패키지 v2 — §8 개정문 원본 |
| `docs/84_rqint_reviewer_response_triage.md` | `2ff314e0bcac009b` | 14,588 | **미등재** | D1~D22 · R1~R6 정본 |
| `docs/33_prereg_deviation_log.md` | `99017397ba2b365d` | 308,047 | **미등재** | 이탈기록 (append-only — 원장 등재값 `9399034b66e45aec` 은 동결시점 스냅샷이라 live 와 다른 것이 정상) |
| `docs/45_research_integrity_ledger.md` | `871a290b35b698b8` | 126,782 | **미등재** | 무결성 원장 (append-only — 고정 해시 동결 대상 아님) |
| `experiments/sap/manifest.json` | `756d485feb4715e9` | 40,130 | ledger.frozen_artifacts · docs/45 §3 | SAP 1.1 매니페스트 |
| `experiments/provenance/ledger.json` | `720c5c02cf52fe76` | 292,870 | **미등재** | 기계검증 원장 (append-only) |
| `experiments/provenance/sign_disclosure_matrix.json` | `147d5d5f62edf84a` | 230,332 | **미등재** | 부호 인지 기록표(R5 근거) |
| `v3_Multimodal/config/reviewer_identity_resolved.json` | `981abdfa296805f4` | 7,224 | **미등재** | amendment 빈칸 4개 값 |