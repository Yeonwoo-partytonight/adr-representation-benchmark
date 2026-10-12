# [블록 K] 층 회계 정합 검증 + assertion 고정 + §13-6 커버리지 감사 — 수행 리포트

- 지시서: `docs/54_v3_strata_accounting_prompt_for_vscode.md`
- 수행: Claude Code (VS Code) · 2026-08-04 09:29 KST
- 결과: **완료**

> ⚠️ **본 리포트에는 층별 macro AP · Δ · CI · sign-flip p · 부호가 한 값도 없다.** 전량 `_sealed/`.
> 개봉(`open_sealed`) **0건** · 성공판정 함수 호출 **0건** · 다중성 보정 **0건** · 새 추정 **0건**.
> 기재된 수치는 **표본수 회계**와 **설계 진단치**(층 경계까지의 거리 등)뿐이다.

> ✅ **K-0 재현 결과: cowork 실측표와 러너 실측이 전건 일치**했다. 정본 교체 불필요.

---

## 1. 게이트/선행조건

| 항목 | 기대 | 실측 | 판정 |
|---|---|---|---|
| `_sealed/stratification_result.json` sha256 | `cd2969c73ed6bae7…` | `cd2969c73ed6bae720df5ffacae8dbba7d6ce8c6e7e6f10b95fa0f91937196ef` | PASS |
| 배타 락 | 획득·정상 해제 | `ComputeLock(role="recorder")` 획득 pid=75343 → 해제 | PASS |
| G-IDLE 게이트 A | load1 < 2.0 | **1차 진입 거부** load1=2.55 → 유휴 대기 후 재진입 **load1=1.49** | PASS |
| sealed guard (착수) | 스냅샷 | **157종**(`experiments/runs/**/_sealed/` 하위 트리 전 파일, `access.log` 제외) | — |
| sealed guard (종료) | 착수와 완전 일치 | 157종 sha256 **전건 일치**(`sealed_guard_unchanged=true`) | PASS |
| `open_sealed` 이력 | 0건 | 0건 (본 블록 `_sealed/` 값 미열람 — sha256 지문 대조만) | PASS |
| 기존 공개 파일 불변 | 바이트 불변 | `strata_assignment.csv` `8247f431…` · `strata_summary.json` `d9333f5e…` · `stratification_public.json` `459ec7e1…` (미수정) | PASS |
| **K-2-1** 행수 | 3,276 | 3,276 (1,092 약물 × 3반복, `(cid, rep)` 중복 0) | PASS |
| **K-2-1** 고유 약물 | 1,092 | 1,092 | PASS |
| **K-2-1** 반복 집합 | {1, 2, 3} 전수 | {1, 2, 3}, 반복별 1,092행 | PASS |
| **K-2-2** `stable_*` 컬럼 | 재계산과 일치 | 3축 전건 일치(불일치 0) | PASS |
| **K-2-3** 축별 `Σ stable + unstable` | 847 | 847 / 847 / 847 | PASS |
| **K-2-3** `847 + no-target 245` | 1,092 | 1,092 | PASS |
| **K-2-3** 축 간 추정 모수 | 동일 | 동일 + **추정 대상 약물 집합도 집합 단위 동일** | PASS |
| **K-2-4** `stratification_public.json` units 합 | 축별 847 | 847 / 847 / 847, `unstable_stratum_counts` 일치 | PASS |
| **독립 재현** | 층 배정 전 컬럼 일치 | 3,276행 × 8컬럼 **불일치 0** | PASS |
| **K-4** 방어 assert | 결과 계열 키 부재 | `macro_ap`·`delta`·`sign`·`ci_*`·`p_*`·`boot_*` 검출 **0** (공개 3파일) | PASS |
| 분류 불가 사례 | 0 | **0건** | PASS |

**게이트 A 경위(정직 고지)** — 최초 진입에서 `load1=2.55` 로 하드 게이트에 걸려 거부됐다. **임계를 바꾸거나
우회하지 않고**, 시스템이 유휴가 될 때까지 진입만 미루는 대기 런처(`load1 < 1.5` 연속 40초 → 러너 진입)를
사용했다. 게이트 판정 자체는 러너 안에서 그대로 수행됐고 `load1 = 1.49 < 2.0` 으로 PASS 했다.
본 블록은 wall-clock 이 결론에 들어가지 않으므로(계산 wall ≈ 1초) 이 대기는 산출물에 영향이 없다.

---

## 2. 실행한 명령

```bash
# 유휴 대기 런처(게이트 A 우회 없음) → 유휴 도달 시 러너 자동 진입
#   load1 < 1.5 가 연속 4회(40초) 관측되면 exec, 게이트 판정은 러너 내부에서 수행
scratchpad/wait_and_run_blockK.sh
#   └─ .venv/bin/python3 v3_Multimodal/src/strata_accounting_check.py

# 사전 검증(프로젝트 파일 미기록) — 산출 경로를 scratchpad 로 바꾼 드라이런 1회
```

수행 스테이지(단일 프로세스): 독립 재현 → K-2 회계 assert → `stratification_public.json` 대조 →
K-3 사유 분류 → K-4 공개 요약 → K-5 커버리지 감사 → sealed guard 재대조.

---

## 3. 산출물

**신규 4파일** (기존 파일 덮어쓰기 0):

- `experiments/runs/v3_stratification/strata_accounting_public.json` — K-4 공개 회계 요약 (4,270 B · sha256 `3f099d9b047ddd1c…`)
- `experiments/runs/v3_stratification/unstable_cases.csv` — K-3 사유 분류 전건 (855행 · 111,516 B · sha256 `65fdb542479cc8df…`)
- `experiments/runs/v3_stratification/accounting_check.json` — K-2 assert·재현 상세 (7,956 B · sha256 `ff8448b7fef2aa43…`)
- `experiments/runs/v3_stratification/coverage_audit.json` — K-5 커버리지 감사 (9,027 B · sha256 `d481163d1debc984…`)

**신규·수정 코드**:

- `v3_Multimodal/src/strata_accounting_check.py` — **신규**(판독 전용 러너)
- `v3_Multimodal/src/stratification_run.py` — `assert_strata_accounting(df)` **추가** + `stage_strata`·`stage_verify` 에서 호출. **본 블록에서 실행하지 않았다**(지시서 K-2-5 규정).

**문서**: `docs/47_v3_stratification_report.md` 정정 배너 · `docs/33` 항목24 · `docs/45` §2 타임라인 1행 ·
`experiments/provenance/ledger.json` timeline 27 → 28.

---

## 4. 관측 (출처 경로 병기)

### 4-1. 회계 재현 — 세 축 모두 847 로 닫힌다

(출처: `experiments/runs/v3_stratification/strata_accounting_public.json`)

| 축 | stable 층별 표본수 | `unstable_stratum` | 추정 모수 | no-target(제외) | 전체 |
|---|---|---|---|---|---|
| `drug_class` | all-seen 552 · mixed 206 · all-unseen 18 | **71** | **847** | 245 | 1,092 |
| `seq_stratum` | seen 820 · unseen_ge90 2 · unseen_70_90 15 | **10** | **847** | 245 | 1,092 |
| `struct_bin` | q1 144 · q2 174 · q3 150 · q4 175 | **204** | **847** | 245 | 1,092 |

`docs/54` K-0 의 cowork 실측표와 **전건 일치**한다. 즉 `docs/51` 메일의 "820+2+15=837" 은
**데이터·계산 오류가 아니라 `unstable_stratum` 10명을 적지 않은 보고 누락**이다.

독립 재현 범위: 층 배정 3,276행을 동결 입력(`master_X/Y.parquet` · `06_targets_human.csv` ·
확증 split `fold_membership.csv` 3반복 · `identity_pairs.tsv` · `_max_tanimoto.npy` ·
`struct_bounds.json`)과 동결 연산자(`sap/unseen_target.classify_drug`·`drug_sequence_stratum`, **무수정**)로
처음부터 재계산해 `fold`·`drug_class`·`seq_stratum`·`n_targets`·`n_unseen_targets`·`n_seqid_observed`·
`struct_bin`·`max_tanimoto` **8컬럼 전건 일치**(불일치 0)를 확인했다.
(출처: `accounting_check.json` → `independent_reproduction`)

### 4-2. 축 간 교차표 (표본수만) — "18 vs 17" 의 정체

(출처: `strata_accounting_public.json` → `cross_tab_drug_class_x_seq_stratum`. 라벨 = 3반복 일치 시 해당 층, 불일치 시 `unstable_stratum`)

| `drug_class` \ `seq_stratum` | seen | unseen_ge90 | unseen_70_90 | unstable | 계 |
|---|---|---|---|---|---|
| all-seen | 552 | · | · | · | 552 |
| mixed | 206 | · | · | · | 206 |
| **all-unseen** | · | **2** | **15** | **1** | **18** |
| unstable | 62 | · | · | 9 | 71 |
| 계 | 820 | 2 | 15 | 10 | **847** |

- `drug_class` stable `all-unseen` **18명 중 17명**(15+2)이 서열축에서도 stable, **정확히 1명**이 서열축 `unstable`.
- 역방향으로 서열축 unseen 층 17명은 **전원** `all-unseen` — **교차 오염 0**.
- 두 숫자는 **서로 다른 축의 서로 다른 stable 필터** 결과이며 모순이 아니다.

### 4-3. 경계·불일치 사례 분류 (K-3)

(출처: `unstable_cases.csv` 855행 = 285 약물-축 × 3반복 · 집계는 `strata_accounting_public.json`)

| 축 | unstable 약물 | 경계 인접 | 집합 변동 | 관측 결손 | 분류 불가 |
|---|---|---|---|---|---|
| `drug_class` | 71 | 0 | **71** | 0 | **0** |
| `seq_stratum` | 10 | **1** | 9 | 0 | **0** |
| `struct_bin` | 204 | **204** | 0 | 0 | **0** |

- **`struct_bin` 204건 전부 경계 인접** — 반복 간 max Morgan Tanimoto 가 분위 경계
  (0.2500 / 0.3284 / 0.4658)를 넘나든다. 경계까지의 최소 거리 = 최소 0.000 · 중앙값 0.022 · 최대 0.132
  (경계 자체가 경험 분위값이라 정확히 경계 위에 놓이는 값이 존재한다).
- **`drug_class` 71건 전부 집합 변동** — "T_d 는 반복 불변이므로 원인은 fold-train 표적 집합뿐"이라고
  **가정하지 않고**, 해당 71명 전부에서 `n_unseen_targets` 가 반복 간 실제로 달라짐을 확인해 분류했다.
- **관측 결손**(all-unseen 且 `n_seqid_observed == 0`)은 반복 1·2·3 **전부 0건**으로 재확인됐다
  (`strata_summary.json` 의 기존 보고와 일치).
- **분류 불가 0건** — 개별 보고 대상 없음.

### 4-4. ★ `all-unseen` ∩ 서열축 `unstable` 1건 상세 (설계 진단 · 결과 아님)

(출처: `unstable_cases.csv` 해당 3행 · `strata_accounting_public.json` → `boundary_cases.special_case_cids`)

| cid | rep | fold | `seq_stratum` | `drug_class` | drug-level max identity(%) | 넘나든 경계 | 경계까지 거리 |
|---|---|---|---|---|---|---|---|
| 16139605 | 1 | 4 | `unseen_70_90` | all-unseen | **87.5** | 90 | **2.5 %p** |
| 16139605 | 2 | 3 | `unseen_ge90` | all-unseen | **100.0** | 90 | 2.5 %p |
| 16139605 | 3 | 3 | `unseen_ge90` | all-unseen | **100.0** | 90 | 2.5 %p |

표적 1개(`n_targets=1`, `n_unseen_targets=1`, `n_seqid_observed=1`)인 약물이며, fold 배정이 바뀌면서
train 표적 집합이 달라져 최근접 identity 가 87.5 % ↔ 100.0 % 로 이동해 **90 % 경계**를 넘나든다.

> ⚠️ **부수 관측(한계로만 명시, 연산자 무수정)**: 반복 2·3 의 identity 가 **100.0 %** 인데도 `unseen` 으로
> 분류된다. H-0-2 canonicalization 이 **isoform suffix 절단만** 적용하고 `secondary_to_primary` ·
> `seq_representative` 병합을 **비활성**했기 때문에, 동일 서열의 다른 accession 은 exact-seen 으로
> 병합되지 않는다. 이는 동결된 설계 선택이며 본 블록에서 바꾸지 않는다.

### 4-5. 축별 위상 라벨 (교수님 2026-08-03 결정 · 라벨만 부착, 해석·판정 없음)

(출처: `strata_accounting_public.json` → `axes[].role`, 근거 = `docs/53` §1)

| 축 | `role` | 근거 |
|---|---|---|
| `struct_bin` | `confirmatory` | 사전등록된 연속 표적 유사도 축 = 확증 유지 |
| `seq_stratum` | `confirmatory` | 동상 |
| `drug_class` | `data_characteristic` | 세 집단의 **분포 자체는 데이터 특성으로 보고**, **재분할 결과 분석은 exploratory** |

`drug_class` 는 사전등록 §11 의 **연속축 목록에 포함되지 않는다**(§9 범주 정의)는 사실도 감사표에 명기했다.

---

## 5. ★ §13-6 커버리지 감사 (K-5 — 계산 없음 · 명세만)

사전등록 `docs/29` **§11** 문면:

> 연속 유사도 층화(primary): max Morgan Tanimoto / 표적 max sequence identity /
> **unseen-target proportion(unweighted · evidence-weighted · mechanism-target indicator ·
> dominant-target-cold)**. 각 축에서 성능 · **Δ(M2b−M1b) 및 Δ(M2b−P-ID)** 층화.

(출처: `experiments/runs/v3_stratification/coverage_audit.json` — 9항목 중 **수행 4 · 미수행 5**)

| # | 등록 항목 | 수행 | 입력 가용 | 정의 동결 | 선행 조건 | 위상 |
|---|---|---|---|---|---|---|
| A1 | max Morgan Tanimoto | ✅ 블록 H (`struct_q1~q4`) | 가용 | 동결(`struct_bounds.json`) | — | confirmatory |
| A2 | 표적 max sequence identity | ✅ 블록 H (`seen`/`≥90`/`70–90`/`40–70`/`<40`) | 가용 | 동결(`SEQID_BOUNDARIES`) | — | confirmatory |
| A3 | unseen-target proportion — **unweighted** | ❌ | **가용** (`n_unseen_targets`/`n_targets`) | **미동결** — 층 경계·연속축 처리 방식이 SAP·등록 어디에도 없음 | 경계 동결 amendment | confirmatory |
| A4 | unseen-target proportion — **evidence-weighted** | ❌ | 부분 (`07_agg_topk.csv` weight·pChEMBL, **top-k ≤5 한정**; `08_m1b_covariates.csv` 약물수준 evidence) | **미동결** — 'evidence' 정의·가중 함수·경계 | 가중 정의 + 경계 동결 amendment | confirmatory |
| A5 | unseen-target proportion — **mechanism-target indicator** | ❌ | **재생성 필요** — `03_targets.csv` `source` 가 전건 `chembl` 단일값(표적 수준 mechanism 구분 없음), `08_m1b_covariates.csv` 는 약물 수준 `mechanism_target_n` 만. 캐시 `_cache/` 에 ChEMBL `mechanism` 응답 **1,009 파일** 존재 → **네트워크 없이 재파싱 가능** | **미동결** — 판정 기준 | 플래그 재생성 + 기준 동결 amendment | confirmatory |
| A6 | unseen-target proportion — **dominant-target-cold** | ❌ | 부분 (`07_agg_topk.csv` `rank`·pChEMBL; top-k 밖 순위 부재) | **미동결** — dominant 정의·cold 임계 | 정의·임계 동결 amendment | confirmatory |
| C1 | 각 축에서 Δ(M2b−M1b) 층화 | ✅ 블록 H (수행 축 한정, 13층 전건, 산출 `_sealed/`) | 가용 | 동결(SAP `756d485feb4715e9`) | — | confirmatory |
| C2 | 각 축에서 **Δ(M2b−P-ID)** 층화 | ❌ | **가용** — `v3_confirm_rest_consensus_rep123/_sealed/consensus_P-ID.npz`(블록 I, 2026-08-04) + `v3_consensus_rep123/_sealed/consensus_M2b.npz` | 동결(대비는 `HOLM_FAMILY` ②) | **없음 — 해소됨** | confirmatory |
| X1 | (§11 목록 밖) `drug_class` 3분류 | ✅ 블록 H | 가용 | 동결(`classify_drug`, 등록 §9) | — | data_characteristic |

**★ C2 정정 반영**: `Δ(M2b−P-ID)` 는 블록 I 완료로 P-ID consensus OOF 가 확보되어 **선행 조건이 해소된
상태**다. "블록 I 이후 가능"이 아니라 **지금 계산 가능하며, 다만 본 블록(K) 범위 밖**이다 → 후속 블록 후보.

> ⚠️ **미동결 정의는 본 블록에서 정하지 않았다.** A3 경계 · A4 가중 정의 · A5 판정 기준 · A6 임계는
> 기록만 하고 확정하지 않았다. Δ 부호 4건이 **이미 공개된 뒤**이므로 확정은 **post-interim amendment**
> 로만 가능하다.

---

## 6. 지시서 대비 편차·판단

1. **sealed guard 범위를 지시서보다 넓게 잡았다** — 블록 H 는 4개 디렉터리 12종, 블록 I 는 30종을 대조했으나,
   본 블록은 `experiments/runs/**/_sealed/` **하위 트리 전 파일 157종**(`access.log` 제외)을 대조했다.
   더 보수적인 방향이므로 지시서 취지(`착수·종료 시 sealed guard 파일수·해시 대조`)에 부합한다.
   (기록: `docs/33` 항목24 ⑧)
2. **게이트 A 1차 거부 → 유휴 대기 후 재진입** — 임계 변경·우회 없음. 지시서 "중단 조건"에 게이트 A 는
   없으나, 가장 보수적인 선택으로 **우회하지 않고 대기**를 택했다(블록 H·I 선례와 동일). 계산 wall ≈ 1초라
   대기가 산출물에 영향을 주지 않는다.
3. **K-3 `drug_class` 사유를 가정하지 않고 검증했다** — "집합 변동"을 정의상 자명한 것으로 처리하지 않고,
   71건 전부에서 `n_unseen_targets` 의 반복 간 변동을 실제로 확인한 뒤 분류했다.
4. **K-3 의 `s_drug`(drug-level max identity) 는 파일에 없어 재계산했다** — `strata_assignment.csv` 는
   `seq_stratum` 라벨만 담고 층 결정에 쓰인 identity 값을 담지 않는다. 경계까지의 거리를 산출하려면
   필수여서 동결 연산자 경로 그대로 재계산했다(모델·통계 계산 아님, 산출물은 신규 파일에만 기록).
5. **`stratification_run.py` 를 수정했으나 실행하지 않았다** — 지시서 K-2-5 규정 그대로. 따라서 기존
   `strata_assignment.csv`·`strata_summary.json`·`stratification_public.json` 은 **바이트 불변**이다.
   (정직 고지: 추가한 `assert_strata_accounting(df)` 만 **순수 함수 단독 호출**로 문법·동작을 확인했다
   — `--stage` 실행 0, 파일 기록 0, `main()`·`ComputeLock` 경로 미진입.)
6. **CLAUDE.md 와의 충돌 없음.** git commit·push 는 지시서 금지 규정대로 **수행하지 않았다**
   (`docs/` 는 `.gitignore` 대상이라 문서 편집은 애초에 추적되지 않는다).

---

## 7. 다음 액션 제안

1. **`Δ(M2b−P-ID)` 층화 블록**을 후속 지시서로 — 선행 조건이 해소돼 있고 SAP 대비 정의도 동결돼 있어,
   블록 H 와 동일한 층 정의·seed(6001/6002)·B=10000 으로 **추가 동결 없이** 착수 가능하다(산출은 봉인).
2. **unseen-target proportion 축(A3~A6) amendment 초안** — A3(unweighted)만이라도 층 경계를 동결하면
   §11 커버리지의 절반이 즉시 회복된다. Δ 부호 공개 이후이므로 **post-interim amendment** 표기가 필수다.
3. A5 는 착수 전 **표적 수준 mechanism 플래그 재생성**(캐시 재파싱, 네트워크 0)이 선행돼야 한다.

`Cowork에 전달: docs/54_v3_strata_accounting_report.md 확인 요청`
