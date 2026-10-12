# 33. 사전등록 이탈 기록 (append-only) — v3 확증 사다리

> **형식(사전등록 §16 준수)**: `YYYY-MM-DD HH:MM | 변경 | 사유 | 이 시점에 확증용 새 split test/OOF를 조회했는가(Y/N)`
>
> 이 로그는 OSF 동결 사전등록서(`docs/30_preregistration_OSF_clean.md`, OSF https://osf.io/5w2uv, 2026-07-23 동결)의
> **무결성 이탈·형식 변경을 append-only로 관리**한다. **`docs/30`(OSF mirror)은 절대 수정하지 않는다.**
> `docs/29`(내부 master) §20 change-history에는 동일 1줄을 mirror 허용(§E).
>
> 원칙: 결과(확증 split test/OOF)를 본 뒤의 **가설·주모델·성공기준 변경은 하지 않는다.** 아래 항목은
> 모두 등록된 설계의 **데이터 확보/형식**에 한정되며, 확증 split은 미생성·미조회 상태를 유지한다.

---

## 이탈 기록

- **2026-07-24 12:18 KST | M1b 공변량(confidence·action·mechanism·승인연도) 및 P-FAM family(자체 서열 50% 클러스터) 데이터 소스 확정·수집 | 등록된 §4 M1b/§9 P-FAM 설계의 데이터 확보(설계·가설 불변, 라벨/분자셋/split/구조 불변) | N (확증 split 미조회·미생성)**

### 세부 (근거 추적)

1. **M1b 공변량 소스**(사전등록 §4 M1b 리스트 그대로 — 설계 불변):
   - 교수님 승인(2026-07-24 안건1=A): "1회 캐시 확장 후 M1b 정식 구현".
   - `docs/31` A-2·A-3 gap(mechanism MoA 플래그·confidence·연도 미수집), `docs/32` §4-1 보류 사유를 해소.
   - 네트워크는 **§4-A 승인 범위로만** = **기존 매핑된 943개 chembl_id**에 대한 ChEMBL
     `/mechanism`(action_type·mechanism_of_action·target), `/assay`(confidence_score 0–9),
     `/molecule`(first_approval) 1회 배치 수집. pchembl-strength는 `05b`(네트워크 불요).
   - **새 표적·분자 추가 없음·재매핑 없음.** 라벨/분자셋/구조/split/mean-pool/Morgan 무접근.
   - 결측(승인연도·confidence)은 **날조 없이** missing 지시자 + 0 대치, 커버리지 리포트
     (`08_m1b_covariates.csv`, `_m1b_covariate_stats.json`).
   - 산출·구현: `v3_Multimodal/src/fetch_m1b_covariates.py` → `B_m1b` 블록(`ladder_confirmatory.py`).

2. **P-FAM family 소스**(사전등록 §9 family 정의 — 자체 서열 50% 클러스터):
   - 교수님 승인(2026-07-24 안건2=A): "자체 서열 mmseqs2 클러스터 family".
   - `docs/32` §4-2 보류(family 라벨 미확보) 해소: human single-protein 표적 서열(1,191, **_cache/ 재사용,
     네트워크 0**)을 **mmseqs2 easy-cluster** 결정적 파라미터(`--min-seq-id 0.5 -c 0.8 --cov-mode 0 --threads 1`)로
     클러스터링 → coarse family(902 클러스터).
   - **한계 명시**: 본 표적셋 자체 50% 클러스터라 canonical UniRef50과 다름(사전등록 §9 sensitivity 계열).
     family 라벨은 label-free·split-free 외부주석 성격; `B_fam` vocab만 fold-train fit(OOV 드롭).
   - 산출·구현: `v3_Multimodal/src/cluster_target_families.py` → `09_target_family_clusters.csv`
     → `B_fam` 블록(`ladder_confirmatory.py`).

3. **불변 확인**: 사전등록 §4 M1b/§9 P-FAM **정의·가설·집계·성공기준 변경 없음**. 라벨(master_Y)·분자셋(master_X)·
   scaffold split·구조(Morgan)·서열 mean-pool 불변. **확증용 split(seed 201~205 × 3) 미생성·미조회·미예측**.
   보류였던 5모델(M1b·M2b·P-ID·P-FAM·C-CAP)은 기존 동결 블록 + B_m1b/B_fam **결합만**으로 조립
   (새 RF 하네스·재튜닝 없음; pilot n_estimators=300 등 그대로).

> 완결 매니페스트: `docs/34_v3_ladder_freeze_complete.md`. 동결 스펙: `v3_Multimodal/config/ladder_freeze.json`.

---

- **2026-07-24 | P-FAM family를 자체 50% 클러스터에서 생물학적 family(ChEMBL protein class 우선, Pfam/InterPro fallback)로 재정의; mmseqs 50%는 §9 sensitivity로 보존 | 자체클러스터 79% 싱글톤으로 coarse-family 통제 미달(§4 P-FAM 문구는 생물학 family 명시), 설계·가설·라벨·split 불변 | N (확증 split 미조회·미생성)**

### 세부 (근거 추적)

4. **P-FAM family 재정의**(사전등록 §4 "target **family/domain** multi-hot (UniProt family·Pfam/InterPro·ChEMBL class)" / §9 "family 정의 다중"):
   - 교수님 승인(2026-07-24): 자체 mmseqs 50% 클러스터는 near-identity(표적 **715/902 = 79.3%가 싱글톤**, `_family_cluster_stats.json`)라
     RQ3b(coarse family 통제)가 P-ID와 사실상 동일해져 무력 → **생물학적 family로 재소싱**.
   - **소스(§3-A 승인 범위 네트워크만 — 기존 target_chembl_id/uniprot)**: primary = **ChEMBL protein classification**
     (`/target_component?...&only=component_id,protein_classifications` 배치 + `/protein_classification` 전체 트리; leaf→부모체인→**L2 조상**).
     fallback = 캐시된 target JSON의 **Pfam/InterPro xref**(네트워크 0). 결측은 SINGLETON + missing_flag(날조 0).
   - **결과(라벨·성능 무참조 granularity 게이트)**: L2 = **42 family, 싱글톤% 19.1%, family/target 0.035, 커버리지 100%**
     (전 표적 ChEMBL class 보유) — 자체클러스터 79.3% 대비 **실질 coarse화**. 게이트: L2 싱글톤% 0.191 < 0.60 → **L2 유지**.
   - **보존**: 자체클러스터(`09_target_family_clusters.csv`)는 삭제하지 않고 **`B_fam_selfclust`(§9 sensitivity)**로 보존
     (sensitivity 모델 `P-FAM_selfclust` seed-42 dev macro AP = **0.2309 = 기존 P-FAM 정확 재현** → 블록 보존 확인).
   - **불변**: **M0·M1·M2·M1b·M2b·P-ID·C-CAP 블록/모델/smoke 값 바이트 불변**(byte-invariance assert 통과, RF 재계산 없음).
     사전등록 §4 M1b·primary contrast(M2b−M1b)·M2b−P-ID·C-CAP·성공기준·집계·P-FAM 개념 **변경 없음**(coarse family 데이터 확보만).
     라벨(master_Y)·분자셋(master_X)·scaffold split·구조(Morgan)·mean-pool 불변. **확증용 split(seed 201~205 × 3) 미생성·미조회·미예측.**
   - 산출·구현: `v3_Multimodal/src/fetch_target_family_biological.py` → `10_target_family_biological.csv`
     → `B_fam`(생물학) 블록(`ladder_confirmatory.py`). 갱신 리포트 = `docs/35_v3_pfam_refresh.md`. **`docs/30`(OSF mirror) 무수정.**

---

- **2026-07-24 16:33 KST | 사전등록 §4 M1b 공변량 목록에 pchembl-strength mean/max(+ pchembl_missing 지시자) 정식 포함 명문화(amendment). 동결 구현과 등록 열거의 불일치를 확증 OOF 조회 전에 투명 해소. | 동결 `B_m1b`(`ladder_freeze.json`, 2026-07-24)가 §4 열거({evidence count, mechanism/binding ratio, mean/max confidence, 승인연도})에 없는 pChEMBL을 이미 포함 → 사용자 승인(유지+amendment)으로 M1b 공변량 집합을 등록 열거 + pChEMBL로 확정. 결과-의존 아님(OOF 미조회). | N (확증 split 미조회·미생성)**

### 세부 (근거 추적)

5. **M1b 공변량 amendment (pChEMBL 명문화)**:
   - **발견**: `docs/37`(ChatGPT 리뷰 필터링) §1 교차검증 — `docs/30` §4 · `docs/29` §4 M1b 열거에는 pChEMBL이 없으나, 동결 `config/ladder_freeze.json` `B_m1b`(13차원)는 `pchembl_mean`·`pchembl_max` + 지시자 `pchembl_missing`을 포함. 위 12:18 항목은 "§4 그대로"로 기재했으나 §4 열거와 실제 불일치였음.
   - **결정(사용자 승인 2026-07-24)**: pChEMBL을 M1b에서 **제거하지 않고 유지**하며, M1b 공변량 집합을 **{ChEMBL evidence count, mechanism/binding ratio, mean/max confidence, 승인/최초라벨 연도, pChEMBL-strength mean/max}** + 결측 지시자로 **amendment 명문화**. pChEMBL은 §4 "study-intensity/evidence 공변량" 취지의 연구량·근거강도 대리변수로 간주.
   - **무결성 근거**: 본 amendment는 **확증용 split(seed 201~205×3) OOF를 한 번도 조회하지 않은 시점**에 기록된다(N). 결과-의존적 사후 변경이 아니라, **동결 시점(2026-07-24)부터 존재하던 구현을 확증 조회 전에 투명 공개**하는 것이다. `B_m1b`·의존 5모델(M1b·M2b·P-ID·P-FAM·C-CAP)은 **재계산·재동결 불요(바이트 불변)**.
   - **방어력 보강(정직 공개)**: 등록 열거를 사후 **확장**하는 방향이므로, (i) 확증 조회 전 기록임을 명시하고, (ii) **pChEMBL 제외 M1b(`B_m1b_nopchembl`)를 sensitivity로 병기**하여 primary 결론이 pChEMBL 포함/제외에 견고한지 보고한다(sensitivity 추가는 허용, primary·성공기준 불변). 구현 준비 = `docs/38` 하드닝.
   - **OSF 처리**: `docs/30`(OSF 동결본)은 수정하지 않는다. 본 amendment는 OSF의 transparent addendum/deviation 및 논문의 preregistration-deviation 표에 공개한다. `docs/29` §20 mirror 1줄 추가.
   - 구현: `ladder_freeze.json` `B_m1b` **변경 없음**(문서화 amendment). 근거 문서 = 본 항목 + `docs/37` §1 + `docs/29` §20.

---

- **2026-07-24 19:45 KST | ★위 16:33 "유지" 결정을 대체 — primary M1b를 **사전등록 §4 열거 일치판(pChEMBL 제외, 10차원)**으로 정정하고, pChEMBL 포함(13차원)판은 **사전지정 sensitivity로 강등**. | ChatGPT 2차 리뷰(§4 닫힌 열거면 제외판이 preregistration-concordant primary)와 교수님 상의용 요약(`docs/39` 첨부 PDF) 검토 후 사용자 승인(안 B). 확증 결과-의존 아님(OOF 미조회). | N (확증 split 미조회·미생성)**

### 세부 (근거 추적)

6. **M1b primary 재지정 (pChEMBL 제외 = 등록 §4 일치)**:
   - **판단**: `docs/30`·`docs/29` §4의 M1b 공변량은 **닫힌 열거**이고 pChEMBL은 미열거. pChEMBL은 연구량이 아니라 potency·assay-selection 정보(ChatGPT #7)라 "연구량 통제 후 서열 증분"이라는 분해를 흐림. → **primary를 등록 열거와 정확히 일치하는 판으로 정정**하는 것이 더 엄격·방어적(등록 준수 복원 = 금지된 변경 아님).
   - **primary `B_m1b`(정정) = 10차원**: 연속 7(log1p evidence/mech_n/bind_n, mech/bind ratio, confidence mean/max, first_approval_year) + 지시자 3(confidence/year/chembl_unmapped). = 기존 13차원에서 pchembl_mean/max/missing 3개 제거. 소스 `08_m1b_covariates.csv` 불변(컬럼 선택만 변경, 재수집 없음).
   - **재동결(OOF 조회 전, 안전)**: M1b·M2b·P-ID·P-FAM·C-CAP를 10차원 B_m1b로 재조립·재동결(RF pilot 레시피 그대로, 재튜닝 0). `M0·M1·M2`·타 블록은 byte-invariant. 구현 = `docs/38`(개정).
   - **sensitivity 보존**: pChEMBL 포함(13차원)판 = `B_m1b_pchembl` + `M1b_pchembl`·`M2b_pchembl`로 동결. primary(제외) 결론의 pChEMBL 포함/제외 robustness 보고용.
   - **primary 지정 확정**: 판정은 **제외판(primary) 하나로만**. 유리한 쪽 cherry-pick 금지(ChatGPT #5). SAP(`docs/41`) decision 함수의 primary 대상 = 제외판.
   - **무결성**: 확증 split·OOF 미조회(N). 라벨·분자셋·구조·mean-pool·split 불변. `docs/30`(OSF) 무수정 — 본 정정은 OSF transparent deviation + 논문 preregistration-deviation 표에 공개. `docs/29` §20 mirror 1줄 추가.
   - 근거 문서 = 본 항목 + `docs/40` §3 + `docs/39` 첨부(pChEMBL 결정요약 PDF).

---

- **2026-07-25 15:31 KST | SAP 동결(A6~A11 + first-look redaction) — 모든 분석 연산자를 코드로 확정·synthetic 검증·hash 동결(`experiments/sap/manifest.json`). 확증 split·OOF 미생성·미조회(N), 네트워크 0. | `docs/41` 실행(vscode) → cowork 독립 교차검증 PASS**

### 세부 (근거 추적)

7. **SAP 동결 + CI 방법 사전고정(BCa)**:
   - **동결 내용**: consensus(A8 방법A)·bootstrap(A7 paired scaffold-cluster)·sign-flip(A6, 검정통계량=macro AP Δ 자체)·null 생성기(A9 target↔embedding 재배치)·unseen-target(A10 fold-local)·decision(A11 RQ2/3/4·Holm·BH-FDR·SESOI/TOST)·redaction(first-look emit_sign)을 `v3_Multimodal/src/sap/`에 결정적 순수 함수로 구현. 모듈별 sha256 = `experiments/sap/manifest.json`. cowork 재검증: live sha == manifest sha(10모듈 전부), config_binding sha16=b885585aefbabb32(dim=10 primary·13 sensitivity), all_validation_pass=True, AST 스캔 forbidden import/data-load/경로리터럴 0, 확증 split·OOF 미존재.
   - **CI 방법 사전고정 = BCa(primary), percentile = 동시산출 sensitivity**: `docs/30` §8은 "95% CI(**BCa 또는 percentile 사전고정**)"으로 CI 방법을 **사전등록이 명시적으로 위임한 사전고정 항목**으로 남겨둠. 이를 **확증 최초 조회 이전**(SAP 동결 시점)에 BCa로 확정 = 등록 이행이지 설계 변경 아님. 근거: macro AP처럼 치우친 통계량에 편향·가속 보정 BCa가 더 정확, `docs/41`이 jackknife(scaffold delete-one) 세부까지 규정한 것과 정합. jackknife 단위=scaffold delete-one(약물 단위 혼용 금지).
   - **무결성**: 입력=synthetic 뿐, 확증 데이터 미접근(AST 하드 증명). 확증 split(seed 201~205×3)·OOF 미생성·미조회(N). `docs/30`(OSF) 무수정. 근거 문서 = 본 항목 + `docs/41` + `experiments/sap/manifest.json`.

---

- **2026-07-25 18:20 KST | SAP 재-동결 amendment(docs/43 A1~A6) — 이미 동결된 SAP 연산자의 미명세 구현 자유도를 확증 조회 전 확정·재-hash. A1(BCa 불능→`ci_primary`=not_estimable, percentile 성공판정 투입 금지)·A2(Holm family 7 고정·결측 p→1.0·MULTIPLICITY_MANIFEST hash)·A3(PT별 BH-FDR eligibility=결과-독립: 양성≥10 AND 양성-포함 scaffold cluster≥3)·A4(NULL_B=1000 정확값 동결·MC SE·full permutation·common RF seed 42)·A5(bootstrap undefined-PT 진단·고정교집합 sensitivity)·A6(ESTIMAND=drug-weighted macro AP·sign-flip prediction-swap caveat·metrics edge assert·B_seq PCA 모집단). 변경 모듈 7종(metrics/bootstrap/signflip/decision/null_generator/synthetic/freeze) sha256 재-hash, sap_version 1.0→1.1, `experiments/sap/manifest.json` 재기록. synthetic 재검증 8/8 PASS(A1~A6 신규 + 기존 audit) + AST 미접근 True. 설계·가설·집계·성공기준·`ladder_freeze.json`(sha16 b885585aefbabb32) 불변. | 등록 분석의 구현 자유도만 제거(설계 변경 아님), 확증 조회 전=무결성 영향 없음. 근거=`docs/42`·`docs/43`·`experiments/sap/manifest.json` | N (확증 split·OOF 미조회·미생성)**

---

- **2026-07-27 10:55 KST | 확증 OOF 반복1(seed 201) M1b·M2b 최초 조회 | §13 실행순서 3 | 새 split test/OOF 조회 = Y**

---

- **2026-07-27 11:10 KST | 반복↔seed 대응 사전확정(반복 r = seed 200+r → 201/202/203, 204·205 미사용 예비) | §6 미명세 항목의 결과-독립 확정 | 등록 설계·가설·집계·성공기준 무변경(문구 명확화) | 확증 결과 조회 = N (기록 시점 delta_sign=null, 작성자 blind)**

---

- **2026-07-27 21:16 KST | null 교환 단위 family partition tie-break 확정 — 복수 family 소속 표적은 `family_id` 문자열 **사전순 최소값** 1개를 교환 family로 배정(결정적·결과 무참조) | 동결 `build_family_permutation`은 partition(분할)을 요구하나 소스 CSV(`10_target_family_biological.csv`)는 표적당 다중 family를 허용(1,191 중 14). 규칙 부재를 확증 null 본런 전에 결과-무참조로 해소 | 확증 조회 = N (본 항목에서 새 split test/OOF 미조회 — 반복1 부호는 2026-07-27 10:55 기조회, `sealed_human_read=false`: `_sealed/access.log` `open_sealed` **0건**)**

### 세부 (근거 추적)

8. **family partition tie-break (§13-4 재배치 null 전용)**:
   - **primary 규칙**: 복수 family 소속 표적은 `family_id` 문자열 **사전순 최소값** 1개를 그 표적의 교환 family로 배정한다. 결정적(정렬만 사용)·결과 무참조(라벨·AP·Δ 미참조).
   - **적용 위치**: **동결 모듈 바깥 상류 전처리**. `v3_Multimodal/src/sap/null_generator.py`는 **바이트 무수정**(sha16 `90886abce256a130` 불변) — 본 규칙은 `build_family_permutation`에 넘길 `targets_by_family` 를 만드는 입력 구성 단계에만 관여한다.
   - **`B_fam`(P-FAM) multi-hot 정의는 불변** — 본 규칙은 null 교환 단위 partition **전용**이며 모델 블록에 영향 없다.
   - **파생량(동결)**: 고정(|family|≤2) target **13** = 싱글톤 family 9 + size-2 family 2개(4 표적), 고정 family **11**, 교환가능 family **31**, 교환가능 target **1,178**(98.9%), family **42**, 표적 **1,191**, tie-break 적용 **14**.
   - **ALT(사전지정 민감도)**: 이중소속 14개 표적을 permutation에서 **제외**하는 규칙(항목 12 참조).
   - **산출**: `data/processed/target_mapping/11_null_family_partition.csv`(sha256 `a95e26f9a527e945…`) · `11b_null_family_partition_ALT.csv`(sha256 `aee6c742c52ce77c…`). 구현 = `v3_Multimodal/src/null_partition_freeze.py`.
   - **정직 고지**: 본 규칙은 **2026-07-27 13:31 타이밍 프로브에서 이미 적용된 뒤** 본 항목으로 문서화되었다. 프로브는 `probe_only=true`·`enters_null_distribution=false`·`empirical_p` 미호출이므로 null 분포·p에 미투입이다.

---

- **2026-07-27 21:16 KST | 사전등록 §13 실행순서 4↔5 스왑 — `3 → 5(반복2·3) → 4(재배치 null)` 로 실행 | **연산 인프라 로지스틱스 전용**: null 본런이 단일 머신을 수일간 점유하기 전에 반복2·3 OOF를 먼저 확보(랩 서버·유료 클라우드 불가, Mac 단독 확정). 분석 정의·가설·집계·성공기준·검정통계량 정의는 **불변** | 확증 조회 = N (본 항목 기록 시점 새 OOF 미생성; `sealed_human_read=false`, `open_sealed` 0건)**

### 세부 (근거 추적)

9. **§13 실행순서 4↔5 스왑**:
   - **변경되는 것**: 두 단계의 **실행 시각 순서**뿐.
   - **변경되지 않는 것(명문화)**: RQ1~RQ7 가설, primary contrast(M2b−M1b), estimand(drug-weighted macro AP), consensus 정의(방법A), NULL_B=1000, `NULL_RF_COMMON_SEED=42`, `p_emp` 공식, Holm/BH 다중성 매니페스트, SESOI/TOST, 성공기준, 검정통계량 정의 — **전부 불변**.
   - **부수효과 명시**: 스왑으로 null 비교 시점에 반복 3개가 모두 존재하게 되지만, null `T_obs` 기준은 **스왑 여부와 무관하게 등록 실행순서가 정한 값**으로 확정한다(항목 11).
   - 논문 preregistration-deviation 표에 그대로 공개한다.

---

- **2026-07-27 21:16 KST | §13-4 재배치 null 검정통계량·검정방향 **판독 확정**(등록 문면 확정, 설계 변경 아님) — `T` = 관측 **M2b macro AP**, 방향 = **단측 상단꼬리(one-sided upper)** | 등록 §3 RQ4 행·§8("관측 M2b가 재배치 null 대비 `p_emp<0.05`")·§5 `p_emp=(1+#{T_b ≥ T_obs})/(B+1)`·SAP `decision.py` 다중성 매니페스트 ④("재배치 null만 upper-tail(one-sided), 나머지는 two-sided")의 문면을 구현 이전에 일의적으로 고정 | 확증 조회 = N (`sealed_human_read=false`, `open_sealed` 0건)**

### 세부 (근거 추적)

10. **null 검정통계량 `T` 와 검정방향**:
   - **`T` 정의** = **관측 M2b macro AP**(consensus OOF 위, eligible PT). `T_b` = permutation b 의 M2b macro AP.
   - **Δ 기준과의 동치 증명**: 재배치는 `B_seq`만 교란하고 M1b는 permutation 불변이므로 `AP_M1b`는 상수다. 따라서
     `Δ_b = AP_M2b(b) − AP_M1b(const)` 이고 `Δ_obs = AP_M2b(obs) − AP_M1b(const)` 이므로
     `#{Δ_b ≥ Δ_obs} = #{T_b ≥ T_obs}` → **`p_emp` 값이 동일**하다. 구현은 M2b AP 기준으로 한다(상수항 감산 불필요).
   - **방향** = **단측 상단꼬리**. 근거 = 등록 §5 `p_emp=(1+#{T_b ≥ T_obs})/(B+1)`(부등호가 상단꼬리를 이미 규정) + SAP `decision.py` MULTIPLICITY_MANIFEST ④.
   - **해석 주의(문장 그대로 보존)**: 반복1 Δ 부호가 negative여도 RQ4는 **M2b 자체를 null 분포와 비교**하므로 독립적으로 유의할 수 있다. "Δ 음성 ⇒ RQ4 자동 실패"로 서술하지 않는다.

---

- **2026-07-27 21:16 KST | §13-4 null `T_obs` 기준 = **반복1(seed 201) 단일반복** — 확정(사용자 승인 2026-07-27) | 등록 §13 실행순서에서 4(null)가 5(나머지 2반복)보다 앞서므로 등록이 상정한 null 비교 시점에 존재하는 반복은 1개. SAP `consensus.build_consensus` 가 "반복이 1개뿐이면 그 자체를 반환"으로 단일반복 경로를 명시 | 확증 조회 = N (기준 확정에 sealed 수치 미사용 — `open_sealed` 0건, `sealed_human_read=false`)**

### 세부 (근거 추적)

11. **null `T_obs` 기준**:
   - **확정**: `T_obs` = 반복1(seed 201) OOF 위에서 산출한 M2b macro AP.
   - **타당성 요건(필수)**: `T_obs`와 모든 `T_b`는 **동일 절차**(rep1 split·동일 5-fold·동일 fold 배정·RF `random_state=42`)로 산출한다. 프로브 identity control이 이 동일성을 이미 증명했다(§13-3 sealed `oof_M2b.npz`와 바이트 동일, 불일치 원소 0/404,040).
   - **문면 충돌 정직 기재**: 등록 §8은 "consensus OOF 위에서 추론"이라 표현하므로 **충돌이 존재한다.** 본 결정은 **§13 실행순서 정합 우선**이며, 아래를 사전 명시한다.
     (i) 4↔5 스왑 사유는 **인프라 로지스틱스**이지 통계적 선택이 아니다(항목 9).
     (ii) 본 기준은 **스왑 여부와 무관하게** 등록 실행순서가 정한 값이다(스왑이 없었다면 애초에 반복이 1개뿐이었다).
     (iii) consensus 기준 null 은 **사후 민감도로만** 가능하다(비용 ≈3배 — consensus는 3반복 OOF 각각을 permutation마다 재계산해야 함).
   - **공개**: 논문 preregistration-deviation 표에 위 (i)~(iii)을 그대로 공개한다.

---

- **2026-07-27 21:16 KST | 파티션 ALT 민감도 사양 **동결** — paired(동일 seed 재사용) · `B_family_ALT=100` · `B_global_ALT=10`(global은 규칙 불변 → **음성대조**) · `enters_p_emp=false` | tie-break 규칙(항목 8)에 결론이 의존하지 않음을 사전지정 민감도로 보이기 위함. 사양을 본런 이전에 고정해 결과-의존적 민감도 설계를 차단 | 확증 조회 = N (`sealed_human_read=false`, `open_sealed` 0건)**

### 세부 (근거 추적)

12. **파티션 ALT 민감도 사양**:
   - **ALT 규칙** = 이중소속 14개 표적을 permutation에서 **제외**(`11b_null_family_partition_ALT.csv`, sha256 `aee6c742c52ce77c…`). 제외 후 family 크기 재계산 → 교환가능 target **1,162**.
   - **paired**: primary와 **동일 seed**를 재사용해 몬테카를로 잡음을 상쇄한다.
   - **B**: `B_family_ALT=100`, `B_global_ALT=10`. global은 tie-break 규칙과 무관(교환 단위 = 전체 unique target)하므로 ALT에서도 규칙이 불변 → **음성대조**(차이가 나오면 하네스 버그 신호).
   - **`enters_p_emp=false`**: ALT의 `T_b`는 primary null 분포에 **편입 금지**. primary `p_emp`는 모드별 1,000개 전량으로만 계산한다.
   - **discordant 처리(사전 확정)**: primary와 ALT의 결론(유의/비유의)이 갈리면 **양 규칙 모두 full-B(1,000)로 재실행**한 뒤 **보수적(큰) `p_emp`** 를 채택한다. 유리한 쪽 선택 금지.

---

- **2026-07-27 21:16 KST | permutation 산출물 저장 정책 동결 — full OOF npz 저장 **금지**, `_sealed/`에 `{mode, seed, oof_sha256, macro_AP, delta, wall_s, cpu_s, peak_rss}` **스칼라만** 기록(감사 예외 = 각 모드 최초 3개 OOF) | 전량 저장 시 1.11GB(프로브 실측 npz 554KB × 2,000)로 불필요하며, 스칼라 + 배열 sha256 만으로 재현·감사가 가능. 저장 정책은 통계량 정의와 무관 | 확증 조회 = N (`sealed_human_read=false`, `open_sealed` 0건)**

### 세부 (근거 추적)

13. **permutation 산출물 저장 정책**:
   - **저장(sealed)**: permutation당 `{mode, seed, oof_sha256, macro_AP, delta, wall_s, cpu_s, peak_rss}`. `oof_sha256` = OOF 배열의 sha256(값 미보존 상태에서 재현 검증용 지문).
   - **감사 예외**: **각 모드 최초 3개** permutation의 OOF npz는 `_sealed/`에 보관(총 6개) — 제3자 재현 감사용.
   - **공개 파일에는 시간·메모리·개수·해시만**. `macro_AP`·`delta`는 sealed(부호-only redaction 규칙 적용 대상).

---

- **2026-07-27 21:16 KST | §13-4 병렬화 정책 동결(Mac 단독 인프라 확정 반영) — `ladder_freeze.json` **바이트 불변**(`n_jobs=-1` 포함 어떤 값도 파일 수정 금지). 허용 = ① permutation 단위 **프로세스 병렬**(b별 독립·결정적 seed 분할), ② RF/MultiOutput 병렬 인자의 **런타임 override**. ②는 통계적 비-파라미터이나 **identity control 0-diff 증명이 붙은 구성만** 본런 채택 | 랩 서버·유료 클라우드 불가로 Mac 단독 확정, 프로브 실측 15.6일(단일 프로세스 순차)을 실행 가능 범위로 줄여야 함. 병렬 인자는 예측값에 영향을 주지 않아야 하며(RF `random_state=42` 고정·PT별 독립), 그 무영향을 **측정으로 증명한 구성만** 사용 | 확증 조회 = N (`sealed_human_read=false`, `open_sealed` 0건)**

### 세부 (근거 추적)

14. **병렬화 정책**:
   - **불변**: `v3_Multimodal/config/ladder_freeze.json`(sha16 `b885585aefbabb32`)은 파일 수정 금지. 동결 레시피의 하이퍼파라미터(`n_estimators=300`, `max_depth=None`, `class_weight="balanced_subsample"`, `random_state=42`)는 전부 불변.
   - **허용 ①** permutation 단위 프로세스 병렬: permutation은 seed만으로 완전 결정되고(프로브 assert: 같은 seed → 같은 mapping) b 간 상태 공유가 0이므로 프로세스 분할이 결과를 바꾸지 않는다.
   - **허용 ②** `RandomForestClassifier(n_jobs=…)` / `MultiOutputClassifier(n_jobs=…)` 의 **런타임 override**(메모리상 dict 변경만, 파일 쓰기 없음). 이는 **통계적 비-파라미터**(연산 스케줄링만 바꿈)이다.
   - **채택 조건(하드)**: ②의 각 구성은 **identity control 0-diff 증명**(예측 배열 sha256이 기준 구성과 비트 동일)이 붙은 것만 본런에 채택한다. 증명 없는 구성은 **영구 제외**.
   - **블록 D는 측정 전용**: 본런 구성 채택은 별도 지시로만 확정한다.
   - **정정 예고**: 프로브 기록의 "374시간"은 `n_jobs=-1` 18코어 **wall-clock** 이며 CPU-시간이 아니다(블록 D-1에서 실측 재산정 후 정정 이력 형식으로 기재).

---

- **2026-07-27 21:27 KST | 확증 OOF **반복2(seed 202)·반복3(seed 203)** M1b·M2b 조회 + **consensus(반복1·2·3, SAP A8 방법A)** 산출 | §13 실행순서 5 (4↔5 스왑 후 — 항목9) | 새 split test/OOF 조회 = **Y** (본 줄은 조회 **직전** 기록, 작성자 blind)**

> ⚠️ **기재 이력(정직 고지)**: 본 항목의 최초 기입(2026-07-27 21:27 KST)은 셸 heredoc 인용 오류로 백틱 안 코드 식별자가 탈락한 **결손 텍스트**였다. 같은 시각대(21:2x)에 **의미 동일·내용 완전한 본문으로 재기입**했으며, 결손본은 정보를 담고 있지 않아 보존하지 않는다. 이 재기입은 **OOF 조회 이전**에 이루어졌고 기록 내용(seed·게이트·redaction 규칙)은 변경되지 않았다.

### 세부 (근거 추적)

15. **§13-5 반복2·3 + consensus**:
   - **기록 시점**: 본 항목은 OOF를 읽기 **직전**(게이트 B)에 기록되었다. 기록 시점의 반복2·3 부호는 `null` 이며 작성자는 blind 상태다. 완료 후 부호는 `docs/45` §5 대장 · `experiments/provenance/ledger.json` · `first_look_log.json` 에 별도 append 한다.
   - **seed**: 반복2 = **202**, 반복3 = **203**(`docs/33` 2026-07-27 11:10 사전확정 = 반복 r → seed 200+r). **204·205 미사용**. 결과 기반 seed 교체·추가·재추첨 영구 금지 — 러너가 그 외 seed 를 시도하면 즉시 중단하도록 하드코딩되어 있다(`SEED_MAP`·`FORBIDDEN_SEEDS` 게이트, exit 7).
   - **코드경로 동일성 증명**: 반복2·3 러너(`confirmatory_oof_rep23.py`)는 반복1(`confirmatory_oof_rep1.py`)의 **동일 함수 객체**(`build_scaffold_groups` · `assign_folds` · `split_diagnostics` · `gate0_verify`)를 import 해 사용하며, 인자화된 것은 **seed·repeat·경로**뿐이다. 검증 = 본 경로를 `seed=201` 로 돌린 재현본 `folds.json` 이 반복1 원본과 **sha256 동일**(`3c1a5d68bfcc6ddf…`, fold 크기 [218, 218, 219, 218, 219]). 반복1 원본 파일은 **읽기만** 했고 재생성·덮어쓰기 하지 않았다.
   - **compute 조건 연속성**: 반복1과 **동일 조건**으로 실행한다 — BLAS 스레드 환경변수 **미설정** 그대로, RF/MultiOutput 병렬 인자 무변경(`n_jobs=-1` / `None`). 병렬화 실험(블록 D)은 본 블록 **이후**로 분리해 반복1~3 sealed 산출물의 compute 환경 연속성을 보존한다.
   - **게이트A(하드)**: 약물 **1,092 전수** · scaffold group **732 전수** · 모든 scaffold group이 정확히 1 fold(**fold 교차 0**) · 전 약물 정확히 1 fold · rare-PT 모든 train fold에 PT별 양성 ≥1 · `B_seq` PCA fit 모집단 = outer-fold train ∩ 매핑 · 전 fold `leak_rows=0` · 전 fold RF `random_state=42`. 하나라도 실패하면 **OOF 미조회 상태로 중단**(seed 재추첨 금지 = seed shopping 차단).
   - **redaction**: 공개 = 각 실행의 `metrics_public.json` = `{"sign": ...}` **단 하나**. 원시 macro AP · Δ 크기 · PT별 · fold별 · 반복별 AP · 확률예측은 전부 `_sealed/`. `repeat_macro_aps` 는 호출하되 출력값은 **전부 sealed**(로그·콘솔 미기록).
   - **반복1 불변**: `v3_confirm_rep1_seed201/_sealed/` 3종 sha256(`8722a4e1c52d2eae…` / `b2a61ba846eead5f…` / `350fa12fac84ef4c…`)을 블록 시작 · 각 반복 종료 · 블록 종료에 확인한다. consensus 입력으로 반복1 sealed OOF 2종을 로드하되 **machine_read**(`human_exposure=false`)로 `access.log` 에 기록하고 값은 출력하지 않는다(`open_sealed` **0건** 유지).
   - **미실행**: bootstrap CI · sign-flip · p-value · SESOI/TOST · 성공판정 · §13-4 재배치 null 본런 · sealed 값 사람 열람 · 네트워크 · `data/raw/` 변경 · git commit.

---

- **2026-07-27 22:19 KST | 블록 C compute 조건 정직 고지 + 블록 D 측정 규약 보정 3건 — 재계산 0·모델학습 0·네트워크 0·sealed 미개봉·p 미계산. ① 블록 C(§13-5 반복2·3+consensus)는 **배터리 전원·저전력 모드(powermode=1)** 에서 실행되어 **wall-clock 비교 불가**(산출물 **바이트 동일성에는 영향 없음**), 해당 wall-clock 은 블록 D·§13-4 추정에 **투입 금지**. ② 블록 D-3 **처리량 정의 = w / wall_max**(워커 중 마지막 완료 기준), 평균 기반 계산 금지 + 코어 배정 규칙·P/E 비대칭 한계 명시. ③ 블록 D-4 **열감쇠·지속부하 baseline = 단독(w=1) 1 permutation 완주 값만**, 병렬 워커0(identity) wall 은 0-diff 검증 전용 | 측정 조건이 다른 시간값을 섞으면 §13-4 총시간 추정이 무효가 된다. 처리량을 평균으로 잡으면 P/E 코어 비대칭에서 생기는 워커 간 불균등이 낙관적으로 상쇄되고, 오버서브스크립션 상태의 wall 을 baseline 으로 쓰면 열감쇠가 과대추정된다. 세 보정 모두 **시간 측정 규약**에만 관여하며 통계 정의·가설·집계·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`) 불변 | 확증 조회 = N (본 항목에서 새 split test/OOF 미조회 — 부호는 2026-07-27 22:14 기조회, `sealed_human_read=false`: `open_sealed` **0건**)**

### 세부 (근거 추적)

16. **블록 C compute 조건 고지 + 블록 D 측정 규약 보정**:
   - **블록 C 전원 실측**: 실행 구간 `2026-07-27 21:26:46` ~ `2026-07-27 22:14:58`. 전원 소스 = **배터리**, powermode = **1**(저전력 모드 ON). 근거 = ① `pmset -g log` 상 구간 시작 직전 상태 `Battery`(직전 이벤트 `2026-07-27 20:45:23`)이며 구간 내 전원 전환 이벤트 **0건** → 전환 없음, ② 실시간 샘플 4건 전부 배터리·powermode=1, ③ 배터리 잔량 단조 방전 [87, 86, 86, 85](AC 연결 시 나타나지 않는 패턴). 산출 = `experiments/runs/v3_confirm_rep23/power_state_block_C.json`.
   - **wall-clock 사용 제한**: 블록 C 기록의 반복별 wall(반복2 1365.4s · 반복3 1371.3s)은 **배터리·저전력 구간 측정치**라 AC·정상 클럭 조건과 **비교 불가**하다. 블록 D 벤치마크·§13-4 총시간 추정에 **투입 금지**하며, 블록 D 스크립트는 블록 C 시간값을 일절 읽지 않는다(`compute_public.json` → `excluded_inputs.block_C_wallclock`).
   - **바이트 동일성 무영향(정직 고지)**: 전원·클럭 상태는 산출물의 **바이트 동일성에 영향을 주지 않는다**. RF `random_state=42` 고정·PT별 독립·연산 순서 불변이므로 부동소수 결과가 전원 상태에 의존하지 않으며, 따라서 반복2·3·consensus 의 `_sealed` sha256 및 **Δ 부호 판정은 유효**하다. 제한되는 것은 **시간 비교**뿐이다.
   - **D-3 처리량 정의(보정)**: **처리량 = w / wall_max**, `wall_max` = 워커 중 **마지막 완료** wall. 평균·중앙값 기반 처리량 계산 **금지**(min·median 은 워커 간 불균등 진단용 **기술통계**로만 보고). 워커 수마다 워커별 wall `min / median / max / (max−min)/median` 을 보고한다. setup 상각 처리량도 `w / max(per_worker_recurring_s)` 로 max 기준을 쓴다.
   - **코어 배정 규칙(명시)**: **워커당 배정 코어 = logical // w**(logical=18, 최소 1). **RF 우선 배정**(`rf_n_jobs` = min(요청, 배정코어); `-1` 이면 배정코어 전량) → **잔여 슬롯을 MOC** 에(`moc_n_jobs` = max(1, 배정코어 // `rf_n_jobs`); 원 구성이 `None` 이면 `None` 유지). BLAS 스레드 상한도 동일 값으로 설정(부모 설정 → spawn 상속).
   - **한계(P/E 비대칭)**: Apple Silicon 은 P코어 6·E코어 12 로 비대칭이고 코어 배정은 macOS 스케줄러가 QoS 기준으로 수행한다. 위 규칙은 워커당 **스레드 수 상한**만 균등 분배할 뿐 물리 코어를 고정(affinity pinning)하지 못한다(macOS 는 사용자 수준 CPU affinity API 미제공). 따라서 워커별 실제 P/E 혼합 비율이 불균등할 수 있고 이는 워커 간 wall 편차로 관측된다 — 처리량을 `wall_max` 로 정의한 것은 이 불균등을 낙관적으로 상쇄하지 않기 위함이다.
   - **D-4 baseline 규칙(보정)**: 열감쇠·지속부하 baseline 은 **단독(w=1) 1 permutation 완주 값만** 사용한다(D-4a). 병렬 배치(D-4b)의 **워커0(identity) wall 은 오버서브스크립션 상태 측정치**이므로 baseline 금지 — **0-diff 검증 용도로만** 쓴다. 열감쇠율 = 단독 런의 첫 fold → 마지막 fold 변화율, 지속부하 하한(600s) 충족 여부도 단독 런 기준으로 판정한다.
   - **D-4 전원 로깅(보정)**: 지속부하 구간(D-4a·D-4b 각각)의 **전원 상태(AC/배터리)·powermode 값·시각**을 60s 주기로 샘플해 로그·`compute_public.json` 에 기록한다. 구간 중 AC 이탈 또는 powermode≠0 이 관측되면 해당 구간 wall-clock 을 **비교 불가**로 표시하고 투영표를 잠정 처리한다.
   - **실행 순서(확정)**: 블록 C 완료 → **AC 연결 + `pmset -g | grep powermode` == 0 확인** → 블록 D 시작 → **블록 D 완료 후 정지**. §13-4 본런은 **별도 지시**로만 착수한다(주말 예정).
   - **불변**: 통계 정의·가설·집계·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 동결 모듈 sha256 전부 불변. 본 보정은 **시간 측정 규약**에만 관여한다.

- **2026-07-28 18:28 KST | §13-4 **병렬 실행 구성 확정**(블록 D 측정 전용) — 구성 **D**(`MultiOutputClassifier(n_jobs=18)` / `RandomForestClassifier(n_jobs=1)`) × **프로세스 워커 18**. 예측 배열 **0-diff 증명 3종**(D-2 구성 간 sha256 일치 · D-3 G1 워커수 불변 · D-4 전량 identity 재확인) 첨부. 워커 수 스윕은 **`n_estimators=60` 타이밍 프록시**로 측정했음을 정직 고지 | 프로브1 실측 15.6일(단일 프로세스 순차)은 §13-4 본런에 비현실적. `ladder_freeze.json`(sha16 `b885585aefbabb32`)은 **바이트 무수정**이며 병렬 인자만 메모리상 복사본에서 override — 이는 통계적 비-파라미터이나 **무영향을 측정으로 증명한 구성만** 채택한다는 항목14 규칙을 그대로 이행 | 확증 조회 = N (`sealed_human_read=false`, `open_sealed` 0건, `empirical_p` 미호출, p 미계산, `T_obs` 비교 없음)**

### 세부 (근거 추적)

16. **§13-4 병렬 실행 구성 확정 (블록 D — 측정 전용)**:
   - **하드웨어 실측**: P코어 6 · E코어 12 · logical 18 · RAM 64GiB(예산 38.4GiB). 전원 = AC 연결 · 저전력 모드 해제(`powermode=0`) · `caffeinate -dimsu` 하에서 측정.
   - **D-1 실효 병렬도 정정**: 구성 A(현행 `n_jobs=-1`)의 fold 단가 = wall 96.9s / **진짜 CPU-시간 198.6s** → 실효 병렬도 **2.05**(logical 18 대비 11% · P코어 6 대비 34%). **정정**: 프로브1 기록의 "374시간"은 18스레드 **wall-clock**이며 CPU-시간이 아니다. 재산정 총 CPU-시간 = **552h**, 총 wall = **269h(11.2일)**.
   - **D-2 병렬축 스윕(각 구성 1 fold · 300 trees · identity permutation)**: A(MOC=None / RF=-1(18)) wall 97s/CPU 199s/비트동일=True · B(MOC=None / RF=6) wall 98s/CPU 194s/비트동일=True · C(MOC=6 / RF=1) wall 30s/CPU 161s/비트동일=True · D(MOC=18 / RF=1) wall 16s/CPU 211s/비트동일=True · E(MOC=6 / RF=3) wall 37s/CPU 268s/비트동일=True. **비트동일 게이트** = 예측 배열 sha256 기준값 `b36a00b22b3abcd0`(구성 A, §13-3 sealed 와 이미 0-diff) 대비 전 구성 일치 = **True**, 제외 구성 = 없음. 최속 = **D**(구성 A 대비 6.01× 가속).
   - **D-3 워커 수 스윕 — 타이밍 프록시 사용(정직 고지)**: 워커 {1,3,6,9,12,18} 스윕은 **`n_estimators=60` 프록시**로 측정했다(동결값 300 아님). 프록시 산출은 `_proxy/` 에 격리되고 `NOT_AN_ANALYSIS_RESULT` 플래그를 달았으며 **OOF 미저장 · 어떤 분석·판정·null 분포에도 미투입**이다. 워커당 스레드 환경변수(`OMP_NUM_THREADS` 등 5종)는 배정 코어 수로 명시 고정, multiprocessing 은 `spawn`. **G1 동시성 불변성** = 같은 seed 예측 sha256 이 워커 수와 무관하게 동일 = **True**. RAM 게이트(합계 peak RSS ≤ 38.4GiB) 탈락 워커 수 = 없음. 선정 **W_BEST = 18**.
   - **D-4 전량 재확인(300 trees)**: (구성 D, 워커 18)로 permutation 1회 완주(5 fold). 프록시 예측 대비 **오차 -10.2%**(허용 ±30% · 통과 = True) → 프록시는 상대 비교 용도로 타당. **0-diff 재확인**: 전량 identity permutation 의 fold 0 예측 sha256 `b36a00b22b3abcd0` = D-2 구성 A 기준값과 **비트 동일 True**. **지속부하 열 감쇠**: 540s 연속 부하(하한 600s 충족 = False)에서 첫 fold→마지막 fold 감쇠율 중앙값 **-1.8%** — 총 wall 추정에 반영했다.
   - **D-5 판정**: 권장 = 구성 **D** × 워커 **18**, 2,000 permutation 예상 총 wall(열감쇠 반영) **1.79일** → 7일 초과 = **False** → **Mac 단독 실행 가능**.
   - **미실행**: `empirical_p` 호출 · p 계산 · `T_obs` 비교 · null 분포 · bootstrap · sign-flip · SESOI/TOST · 성공판정 · `ladder_freeze.json` 수정 · §13-4 본런 · sealed 값 사람 열람 · 네트워크 · `data/raw/` 변경 · git commit.

---

- **2026-07-28 19:57 KST | 블록 D **사후 정정 6건** + §13-4 본런 **인프라 하드닝**(블록 E — 정정·구현 전용) — 계산 0·모델학습 0·permutation 0·네트워크 0·sealed 미개봉. ① `docs/33` 항목번호 **중복(16 이 2건)** 을 레코더 하드코딩 버그로 확인, append-only 원칙에 따라 **원문은 수정하지 않고** 후자를 **`항목16-B`** 로 별칭 지정. ② **joblib daemonic 강등** — `multiprocessing.Pool` 워커가 daemonic 이라 loky 가 `MultiOutputClassifier` 를 무음으로 `n_jobs=1` 강등했고, 따라서 D-3·D-4 는 **배정 코어와 무관하게 내부 직렬**로 실행됐다(실제 채택 구성 = **18 프로세스 × 내부 직렬**). ③ 권장값 1.79일은 **ALT 민감도 110회 미포함** → 전체 2110회 = **1.89일**. ④ 지시된 배타 락·G-IDLE 이 **블록 D 실행 시점에는 미구현**이었음을 정직 고지(본 블록에서 구현). ⑤ 열감쇠 근거 한계(지속부하 540s < 하한 600s)는 재측정 없이 **본런 실시간 감시**로 대체. ⑥ 통계 정의·가설·집계·성공기준·`ladder_freeze.json`·SAP 모듈 sha256 **전부 불변** | 정정 대상은 **실행 기술·측정 규약·인프라**뿐이며 **결론값은 불변**이다(7일 초과 = **False** 유지). 권장값은 본런과 동일 형태를 전량 실측한 값이라 강등의 영향을 받지 않는다 | 확증 조회 = N (새 split test/OOF 미생성·미조회, `open_sealed` **0건**, `empirical_p` 미호출, p 미계산, `T_obs` 비교 없음)**

### 세부 (근거 추적)

17. **블록 D 사후 정정 + 본런 인프라 하드닝 (블록 E — 정정·구현 전용)**:
   - **①-1 항목번호 중복 확인**: `docs/33` 에 `16.` 세부 항목이 **2건** 존재한다 — (ㄱ) 2026-07-27 21:16·22:19 계열 "블록 C compute 조건 고지 + 블록 D 측정 규약 보정", (ㄴ) 2026-07-28 "§13-4 병렬 실행 구성 확정". 원인 = `null_probe2_record.py` 가 항목번호를 **`"16."` 으로 하드코딩**한 것(문서를 판독하지 않음).
   - **①-2 조치**: **append-only 원칙에 따라 원문 2건은 어느 쪽도 수정하지 않는다.** 대신 후자(ㄴ)를 **`항목16-B`** 로 별칭 지정하고, `docs/45` §2·`ledger.json` 의 **상호참조 문자열만** `항목16-B` 로 갱신한다 — 참조 문자열 갱신은 **원문 사실의 변경이 아니다**(가리키는 대상과 내용은 동일). 레코더는 `doc_numbering.next_item_number()` 로 `^\d+\. \*\*` **최대 번호 + 1** 을 계산하도록 수정했고, **중복 번호 검출 assert** 를 추가했다(본 항목 번호 17 은 그 로직으로 산출).
   - **②-1 joblib daemonic 강등 — 사실**: `multiprocessing.Pool` 워커는 **daemonic** 이므로 joblib(loky)이 `UserWarning: Loky-backed parallel loops cannot be called in a multiprocessing, setting n_jobs=1` 와 함께 `MultiOutputClassifier` 의 프로세스 팬아웃을 **무음으로 `n_jobs=1` 로 강등**했다. 따라서 D-3·D-4 의 **모든 워커는 배정 코어 수와 무관하게 내부 직렬**로 실행됐다.
   - **②-2 독립 확인**: `joblib_daemonic_probe.py`(introspection 전용 — 모델학습 0·데이터 미접근)로 재현했다. 부모(비-daemonic) `effective_n_jobs`=18 · 경고 0건 vs Pool 워커(daemonic) `effective_n_jobs`=1 · 동일 경고 발생 (joblib 1.5.3 · scikit-learn 1.9.0). 산출 = `experiments/runs/v3_null_probe2_compute/_evidence/joblib_daemonic_probe.json`.
   - **②-3 타이밍 증거**: 동일 구성 D 인데 **D-2 네이티브 16.1s/fold** vs **D-4a 워커 내부 107.8s/fold** — **6.7×** 차이. 강등이 없었다면 나올 수 없는 격차다.
   - **②-4 실제 채택 구성(정정 후 정본)**: **`18 프로세스 × (RF n_jobs=1, MOC 실효 n_jobs=1)`**. 스레드 환경변수 5종(`OMP_NUM_THREADS` 등)=1 은 **BLAS 레벨에서 실제 적용**됐다.
   - **②-5 미실행으로 정정되는 기술**: `compute_public.json` 의 `scaling_rule`·`core_assignment_rule`("내부 병렬도를 배정 코어에 맞춰 축소", "RF 우선 배정 → 잔여 슬롯 MOC") 및 `docs/33` 항목16-B 의 "코어 배정 규칙(명시)" 문단이 기술한 **MOC 프로세스 팬아웃은 한 번도 일어나지 않았다.**
   - **②-6 결론값 무영향(정직 고지)**: 권장값 **1.79일은 본런과 동일 형태(18워커 × 내부 직렬)를 전량 실측**한 값이므로 유효하다(`measured_full=true`). 독립 교차검증 — 네이티브 구성 D 순차 16.1s/fold × 5 fold × 2000 perm = **1.87일** 로 같은 자릿수다. **성능을 남겨둔 것도 아니다.**
   - **②-7 D-5 표 해석 한계**: D×1~D×12 행은 "네이티브 구성 D" 가 아니라 **"직렬화된 구성 D"** 의 값이다 — **D×1=13.99일 > A×1=11.21일** 역전이 그 흔적이다. 또한 D×1 은 **프록시 앵커 보정(1.114) 경로** 값이며, 단독 전량 실측(542s/perm)으로 계산하면 **12.5일** 이다 → **표 안에 측정 출처가 다른 행이 혼재**한다. **권장행 D×18 은 전량 실측이라 영향 없음.**
   - **③ 총 permutation 수 정정**: 1.79일은 **2,000회(global 1000 + family 1000) 기준**이며 **사전지정 ALT 민감도 110회(`B_family_ALT`=100 + `B_global_ALT`=10)를 포함하지 않는다.** 전체 **2110회 → 45.3h ≈ 1.89일**. 정지 임계 7일 대비 **7일 초과 = False** → **판정 불변**.
   - **④ 락·G-IDLE 미구현 상태로 블록 D 가 실행된 사실(정직 고지)**: 지시된 **배타 락·G-IDLE 은 블록 D 실행 시점에 구현되어 있지 않았고**, 러너가 이를 **값 날조 없이 "보고 불가"로 명시**했다. 같은 날 **15:58~16:10 다른 세션의 git commit·reset 이력**이 존재하나 블록 D 는 **17:34 시작**으로 겹치지 않는다. E-3 감사 결과(아래 ⑥)를 근거로 첨부한다. 본 블록(E-1)에서 `compute_lock.py` 로 구현 완료했으며 **§13-4 본런에는 하드 게이트로 적용**한다 — 락 = `O_EXCL` 생성·pid 생존검사·stale 원문보존 인수·재판독 후 자기 pid 일 때만 해제, G-IDLE = A(진입 load<2.0 하드)·B(스테이지 직전·직후 경쟁 프로세스 0건 하드)·C(스테이지 사이 정착 대기, ≥4.0 이면 중단).
   - **⑤ 열감쇠 근거 한계와 처리 방침**: 지속부하 **540s < 하한 600s**(`sustained_ok`=False)로 감쇠율 **-1.8%**(적용 계수 1.000)의 근거가 얇다. **재측정하지 않고**, 본런에서 **배치별 처리량을 체크포인트에 로깅해 실시간으로 감쇠를 감시**하는 방식으로 대체한다(여유 1.89일 vs 정지 조건 7일).
   - **⑥ E-3 git 이력 무결성 감사(읽기 전용)**: 2026-07-28 15:58~16:10 구간 커밋(`878b3ba`·`025e2ea`·`b5cd8e0`·reset→`878b3ba`·`bdb65c8`·`10687f4`)이 건드린 **보호 대상 파일 = 0건**. `docs/30`·`docs/33`·`docs/45`·`**/_sealed/**`·`experiments/provenance/**` 는 **git 미추적**이라 커밋·reset 이 접근 자체를 못 한다. `ladder_freeze.json`·`src/sap/**`·`experiments/sap/manifest.json` 은 15:47~15:51 에 **최초 추가(A)된 뒤 한 번도 수정되지 않았고**(각 파일 커밋 이력 1건), HEAD blob 과 live 파일이 **바이트 동일**이다. reset 구간도 내용 중립(재생성 커밋의 blob 해시 동일). **PASS.**
   - **⑦ 불변 확인**: 통계 정의·가설·집계·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 11모듈 sha256 **전부 불변**. sealed 12종 sha256 불변 = **True**. 본 정정은 **실행 기술·측정 규약·인프라**에만 관여한다. 확증 조회 = **N**(새 split test/OOF **미생성·미조회**, `open_sealed` **0건**).
   - **미실행**: `empirical_p` 호출 · p 계산 · `T_obs` 비교 · null 분포 · bootstrap · sign-flip · SESOI/TOST · 성공판정 · `ladder_freeze.json` 수정 · SAP 모듈 수정 · `docs/30` 수정 · §13-4 본런 · sealed 덮어쓰기·사람 열람 · 네트워크 · `data/raw/` 변경 · git commit·push.

---

- **2026-07-28 23:17 KST | §13-4 본런 **착수 전 사전정정 3건**(블록 F-0 — 정정·기록 전용) — 계산 0·모델학습 0·permutation 0·네트워크 0·sealed 미개봉. ① **daemonic 강등 적용 범위 정정** — 권장 구성(w=18)에는 강등이 **적용된 적이 없다**(코어 배정 18//18=1 → MOC **요청 1**·실효 1). 강등이 작용한 지점은 **D-4a 단독**(요청 18→실효 1)과 **D-3 의 w∈{1,3,6,9}** 뿐이며 w∈{12,18}은 **요청 자체가 1**. ② **RAM 추정치 정정** — `D5_recommendation.sum_peak_rss_gib`(10.59 GiB)는 **D-3 프록시(n_estimators=60)** w=18 행과 **바이트 일치**하며, **300트리 × 18워커 합계 peak RSS 는 미측정**이다. 단독 300트리 실측 1.790 GiB × 18 = **≈32.2 GiB(예산 38.4 의 84%)**, 여유 16% → **라이브 RAM 게이트(G4) 필수**. ③ **§13-4 공개 범위 사전확정(redaction)** — 공개 = **완주 개수·해시·시간·메모리·게이트 PASS/FAIL 뿐**, `p_emp`·MC SE·유의 여부·null 분포·`T_obs`·`T_b` 는 전부 `_sealed/` 이며 개봉은 **성공판정 단계에서 Holm/BH 다중성과 함께 일괄** | ①은 블록 E 정정의 **범위를 좁히는** 재정정으로 **결론값 불변**(1.79일은 w=18·MOC 실효 1 형태의 전량 실측). ②는 예산 대비 여유가 16%뿐이라 추정만으로 본런에 진입할 수 없다는 판단. ③은 RQ4 유의 여부를 §13-4 단계에서 단독 공개하면 **조각 개봉**이 되기 때문 | 통계 정의·가설·집계·성공기준·`NULL_B=1000`·`p_emp` 공식·`ladder_freeze.json`·SAP 모듈 sha256 **전부 불변** | 확증 조회 = N (새 split test/OOF 미생성·미조회, `open_sealed` **0건**, `empirical_p` 미호출, p 미계산, `T_obs` 비교 없음)**

### 세부 (근거 추적)

18. **§13-4 본런 착수 전 사전정정 3건 (블록 F-0 — 정정·기록 전용)**:
   - **①-1 사실 판독**: `compute_public.json` 판독 결과 — `D4_full_verification.scaled_cfg` = `{rf_n_jobs: 1, moc_n_jobs: 1, cores_assigned: 1}`, `D4_baseline_rule.solo_baseline.scaled_cfg` = `{rf_n_jobs: 1, moc_n_jobs: 18, cores_assigned: 18}`, D-3 워커별 **MOC 요청값** = w=1→18 · 3→6 · 6→3 · 9→2 · 12→1 · 18→1.
   - **①-2 정정 내용**: **권장 구성(w=18)에는 daemonic 강등이 적용된 적이 없다.** 코어 배정 규칙(`logical // w` = `18//18` = **1**)에 의해 MOC=**1 이 요청**되었고 실효도 1이므로, 강등이 개입할 여지 자체가 없었다. 강등이 **실제로 작용한** 지점은 ① **D-4a 단독 baseline**(요청 18 → 실효 1)과 ② **D-3 의 w∈{1,3,6,9}**(요청 18/6/3/2) 행뿐이다. **w∈{12,18} 은 요청 자체가 1** 이라 강등과 무관하다.
   - **①-3 기입**: `run_manifest_draft.json` 의 `parallel_policy` · `parallel_detail.confirmed_config.label` · `moc_n_jobs_requested` 를 **`MOC 요청=1 · 실효=1 · daemonic 강등 무관 / RF=1`** 로 정정하고, `joblib_daemonic_downgrade` 를 **`{"confirmed_config": false, "d4a_solo": true, "d3_rows_w_1_3_6_9": true}`** 로 세분화했다. `compute_public.json` 은 기존 항목 무수정 · `corrections` 에 **append only**.
   - **①-4 결론 불변**: 1.79일은 **(w=18, MOC 실효 1) 형태의 전량 실측**이므로 그대로 유효하다. D-4a 단독의 **108s/fold** 가 네이티브 **16.1s/fold** 와 **6.7×** 차이 난 이유가 바로 이 강등이며, 이는 **단독 baseline 에만** 해당한다 — 권장 구성의 시간값과 무관하다. 0-diff 증명 3종 해시도 불변.
   - **②-1 RAM 사실 판독**: `D5_recommendation.sum_peak_rss_gib` = **10.592743 GiB** 는 `D3_worker_sweep` 의 **w=18 행**(`sum_peak_rss_bytes` = 11,373,871,104)과 **바이트 일치**(assert PASS)이며, 그 행은 `timing_proxy=true` · `n_estimators=60` 이다(동결값 300). 따라서 **300트리 × 18워커 합계 peak RSS 는 한 번도 측정되지 않았다.**
   - **②-2 정정 추정치**: 단독 300트리 **실측** `peak_rss_gib` = **1.790** → 18워커 합계 **추정 ≈ 32.2 GiB**(예산 38.4 GiB 의 **84%**), 여유 **16%**. 이는 **측정이 아니라 선형 추정**임을 명시한다(`estimate_not_measurement=true`).
   - **②-3 조치**: 여유가 16% 뿐이므로 **라이브 RAM 게이트(G4)를 본런 하드 게이트로 신설**한다 — 첫 풀 라운드(18 task) 동안 **10초 주기로 전 워커 RSS 합계 샘플**, 합계가 예산 **38.4 GiB** 를 초과하면 **워커 수를 즉시 하향(18→12→9)** 하고 사실·시각·관측값을 기록한 뒤 재개한다. 워커 수는 **G1 동시성 불변성으로 통계적 중립이 증명된 축**이므로 변경이 허용되나, **변경 이력을 반드시 기록**한다. `D5_recommendation` 은 **무수정**(정정은 `corrections` append 로만).
   - **③ 공개 범위 사전확정(redaction)**: 본런 완료 시 **공개 = 완주 permutation 개수 · 해시 · 시간 · 메모리 · 게이트 PASS/FAIL · 워커 수 변경 이력 · `power_excursion` 수 · 세션 분할 이력**뿐이다. **`p_emp` · MC SE · 유의 여부 · null 분포 · `T_obs` · `T_b` · macro AP · Δ 는 전부 `_sealed/`** 에 두고, 개봉은 **성공판정 단계에서 Holm/BH 다중성과 함께 일괄** 수행한다. 사유 = §13-4 단계에서 RQ4 유의 여부를 단독 공개하면 **조각 개봉**이 되어 다중성 보정 이전에 결과를 부분 학습하게 되기 때문이다. 이 결정은 **본런 착수 전**에 기록되었다(`decided_before_run=true`).
   - **④ 불변 확인**: 통계 정의·가설·집계·성공기준·`NULL_B=1000`·`p_emp` 공식·seed 규칙·ALT 사양·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 11모듈 sha256 **전부 불변**. 본 정정은 **실행 기술·측정 규약·공개 규약**에만 관여한다. 확증 조회 = **N**(새 split test/OOF **미생성·미조회**, `open_sealed` **0건**).
   - **미실행**: `empirical_p` 호출 · p 계산 · `T_obs` 비교 · null 분포 · permutation 실행 · bootstrap · sign-flip · SESOI/TOST · 성공판정 · `ladder_freeze.json` 수정 · SAP 모듈 수정 · `docs/30` 수정 · sealed 덮어쓰기·사람 열람 · 네트워크 · `data/raw/` 변경 · git commit·push.

---

- **2026-08-01 01:16 KST | §13-4 재배치 null **본런 완주**(2,110/2,110) + **집계 실행**(사전등록 절차 그대로 · 편차 0) — 본런은 6세션 분할(2026-07-28 23:38:10 KST ~ 2026-07-31 21:18:17 KST)로 수행됐고 세션별 완주 415/94/576/801/216/8, 전 세션 워커 **18 × (RF `n_jobs=1`, MOC `n_jobs=1`)** · AC 전원 · `powermode` 0 · `graceful_stop=true` · `power_excursion` 0. 모드별 완주 = global 1000 · family 1000 · family_ALT 100 · global_ALT 10, `_sealed/checkpoint.jsonl` 2110행. 게이트 전항 PASS(G0 · G3 identity 0/404040 · G1+G2 sha 동일 · seed 격리 교집합 0 · sealed guard 12종 불변 · **G4 미발동**). **분할 실행은 seed 결정성 때문에 산출물에 무영향이며 실행 로그 사항으로만 기록한다.** 집계는 본 항목 기입 **직후** `--stage aggregate` 를 **1회** 실행하며, 이는 `empirical_p` 의 **최초 기계 호출**이다(사람 열람 아님) | 본런 완주 사실과 집계 착수 시점을 **결과를 보기 전에**(pre-look) 남겨 사후 선택의 여지를 없애기 위함. 집계 공개 범위는 항목18 ③에서 **이미 사전확정**되어 있으며 본 항목에서 **변경하지 않는다** | 통계 정의·가설·집계 규칙·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 모듈 sha256(manifest `756d485feb4715e9`)·`null_generator.py`(`90886abce256a130`)·`NULL_B=1000`·`NULL_RF_COMMON_SEED=42`·`p_emp` 공식·파티션 CSV 2종 **전부 불변** | 확증 조회 = N (새 split test/OOF 미생성·미조회, `open_sealed` **0건**, 사람 열람 0 — 집계의 `empirical_p` 호출은 **기계 호출**이며 산출은 전량 `_sealed/`)**

### 세부 (근거 추적)

19. **§13-4 재배치 null 본런 완주(2,110/2,110) + 집계 실행 (블록 F-2 — 실행·기록 전용)**:
   - **① 본런 완주 사실**: `progress_public.json` 판독 — `completed` = **2110/2110**, `stop_reason` = `"done"`, 모드별 `completed_by_mode` = `expected_by_mode` = **global 1000 · family 1000 · family_ALT 100 · global_ALT 10**. `_sealed/checkpoint.jsonl` **2110행**(행 수만 판독 — 내용 미열람).
   - **② 세션 분할 이력**: 세션1 2026-07-28 23:38:10 KST→2026-07-29 08:19:59 KST 완주 415 · 세션2 2026-07-29 17:38:05 KST→2026-07-29 19:33:39 KST 완주 94 · 세션3 2026-07-29 20:32:19 KST→2026-07-30 08:17:07 KST 완주 576 · 세션4 2026-07-30 17:22:45 KST→2026-07-31 08:15:25 KST 완주 801 · 세션5 2026-07-31 16:32:10 KST→2026-07-31 20:38:57 KST 완주 216 · 세션6 2026-07-31 21:05:43 KST→2026-07-31 21:18:17 KST 완주 8. 전 세션 `graceful_stop=true`, 워커 수 **18 고정**(변경 이력 0건), 실행 형태 **RF `n_jobs=1` · MOC `n_jobs=1`**(블록 F-0 ①의 정정된 정본 구성), 전원 상태 **AC 6/6 · `powermode_live`=0 6/6**, `power_excursion` **0**. **분할 실행은 permutation seed 가 결정적이므로 산출물(예측·해시)에 영향을 주지 않는다** — 실행 로그 사항으로만 기록하며, 통계량·집계 규칙과는 무관하다.
   - **③ 재개 세션의 게이트 축약(사전지정)**: 세션 2~6은 **환경 지문 완전 일치**(`env_fingerprint_match=true`, `diff_keys` 0건)를 확인한 뒤 **G3 identity·G1/G2 재실행을 생략**했다. 이는 블록 F 설계에 따른 **사전지정 축약**이며, 값은 **첫 세션(2026-07-28 23:46:31 KST) 결과를 인용**했다 — G3 identity `n_elements_differing` = **0/404040**, `array_bitwise_match` = **True**, sealed sha256 expected == live, G1+G2 solo(1워커) vs pool(18워커) OOF sha256 **동일**. seed 격리 = 예약·프로브 seed 와의 교집합 **0**(2110 task · 고유 seed 2000).
   - **④-1 관측 RAM(정직 고지 — F-0 ② 추정과의 대조)**: 워커 합계 peak RSS 의 **세션별 최대** = **30.94 / 30.28 / 29.85 / 32.51 / 31.36 / 17.52 GiB**(세션 1~6 순) → **전체 최대 = 32.51 GiB**(예산 **38.4 GiB** 의 **84.7%**, 여유 15.3%). **세션 5 의 최대(31.36)를 전체 최대로 오독하지 않도록 명시한다.**
   - **④-2 추정 대비 방향**: F-0 ②의 선형 프록시 추정은 **32.22 GiB**(예산의 83.9%)였다. 관측 최대는 그보다 **+0.29 GiB(+0.9%) 높다** — 즉 추정은 근소하게 **낙관적**이었으며, **"추정보다 낮았다"는 서술은 사실이 아니다.** 그럼에도 관측치는 예산 **38.4 GiB 이내**이므로 **결론(예산 내 실행)에는 변화가 없다.**
   - **④-3 G4 판정**: 라이브 RAM 게이트 G4 의 임계는 **예산(38.4 GiB)** 이며 관측 최대가 이를 넘지 않아 **미발동**(`ram_gate_G4.exceeded` = **false**, 샘플 75회, 워커 수 하향 **0회**). ④-2 의 방향(추정 < 관측)을 고려하면 **F-0 ②의 "미측정이므로 추정만으로 진입할 수 없다 → 라이브 게이트 필수" 라는 정직 고지는 유효했다.**
   - **⑤ 공개 범위 — 항목18 ③에서 이미 사전확정, 본 항목에서 변경 없음**: 집계 산출 중 `p_emp` · MC SE · 유의 여부 · null 분포 · `T_obs` · `T_b` · macro AP · Δ 는 **전부 `_sealed/null_result.json`** 에 두고, 개봉은 **성공판정 단계에서 Holm/BH 다중성과 함께 일괄** 수행한다. **§13-4 단독 개봉 = 조각 개봉이므로 금지.** 공개 파일(`aggregate_public.json`)에는 **개수·해시·시간·메모리·PASS/FAIL 만** 기록한다.
   - **⑥ `empirical_p` 최초 호출 전환점(명시)**: 항목 1~18 은 전부 "`empirical_p` **미호출**" 상태에서 작성됐다. **본 항목 이후 실행되는 집계가 그 전환점**이다 — 드라이버는 하드 assert(모드별 `unique==expected` · 중복 0 · 누락 0 · 범위밖 0 · `B == NULL_B == 1000` · checkpoint 마지막 줄 완전성 · sealed guard ≥ 12종) **전항 PASS 시에만** `empirical_p` 를 호출하며, 하나라도 FAIL 이면 **호출조차 하지 않고 중단**한다(부분집계 물리 차단). 호출은 **기계 호출**이고 반환값은 즉시 `_sealed/` 로 봉인되므로 **`sealed_human_read=false` · `open_sealed` 0건 유지**다. 확증 조회 = **N**.
   - **⑦ 불변 확인**: 통계 정의·가설·집계 규칙·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 11모듈 + `manifest.json`(sha16 `756d485feb4715e9`)·`null_generator.py`(sha16 `90886abce256a130`)·`NULL_B` = **1000**·`NULL_RF_COMMON_SEED` = **42**·`p_emp` 공식·파티션 CSV 2종 sha256 **전부 불변**. sealed guard **12종** 불변 = **True**. `docs/30`(OSF mirror) 무수정.
   - **미실행(본 항목 시점)**: p 해석 · `T_obs` 비교 결과 열람 · null 분포 열람 · 성공판정 · 개봉 · Holm/BH · bootstrap CI · sign-flip · SESOI/TOST · `ladder_freeze.json` 수정 · SAP 모듈 수정 · `docs/30` 수정 · sealed 덮어쓰기·사람 열람 · 네트워크 · `data/raw/` 변경 · git commit·push.

---

- **2026-08-01 16:55 KST | §13-6 연속 유사도 층화 **판독확정 5건**(블록 H-0 — 기록 전용·pre-look) — 층화 계산 0 · bootstrap 0 · sign-flip 0 · 성공판정 0 · 개봉 0 · 네트워크 0. 등록 문면이 **구현 이전 단계에서 일의적이지 않은 지점** 5건을 **결과를 보기 전에** 고정한다: ① consensus 기준 층 배정 = **반복별 배정 후 3반복 일치 약물만 primary**, 불일치는 `unstable_stratum` 으로 **분리 집계**(제외 아님) ② `canonicalize_accession` 의 `secondary_to_primary`·`seq_representative` 공급 파일이 프로젝트에 없어 **둘 다 `None`(병합 없음)** 으로 고정하고 isoform suffix 절단만 적용 ③ `eligible_pt=None`(370 PT 전열) — 층 내부 재선정 금지 ④ 층화 전용 seed = bootstrap **6001** · sign-flip **6002** · `B=10000`, 예약·확증·null 본런·프로브 seed 와 **교집합 0** 실측 ⑤ 구조축 = fold-train 약물집합 대비 **max Morgan Tanimoto**(동결 지문 r=2·2048bit 그대로), 층 경계는 사전등록에 수치가 없으므로 **반복1 기준 25/50/75 분위**로 확정 = **0.2500 / 0.3284 / 0.4658**(3반복 공통 적용, 결과를 본 뒤 조정 금지) | 5건 모두 **설계·가설·성공기준 변경이 아니라** 구현 자유도 제거이며, 계산 착수 **전에** 고정해야 사후 선택의 여지가 없어지기 때문 | 통계 정의·가설·집계 규칙·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 11모듈 + `manifest.json`(sha16 `756d485feb4715e9`)·`SEQID_BOUNDARIES`·`SEQID_STRATA`·`MIN_SUPPORT`·`INFERENCE_MODE`·`IDENTITY_METHOD` **전부 불변** | 확증 조회 = N (본 항목 시점 — consensus OOF 미판독, `open_sealed` **0건**, bootstrap·sign-flip 미실행)**

### 세부 (근거 추적)

20. **§13-6 연속 유사도 층화 판독확정 5건 (블록 H-0 — 기록 전용·pre-look)**:
   - **① consensus 기준 층 배정**: consensus 는 3반복 평균이지만 fold-local `T_train,f` 는 **반복마다 다르다**(반복별 split seed 201·202·203). 따라서 층을 **반복별로 배정한 뒤, 3반복에서 층이 일치하는 약물만 primary 층화 대상**으로 한다. 불일치 약물은 **제외하지 않고** `unstable_stratum` 으로 **분리 집계·별도 보고**한다. 사유 = consensus 예측 위에서 하나의 층 라벨을 붙이려면 반복 간 라벨 안정성이 전제인데, 불안정 약물을 임의로 한 층에 배정하면 그 층의 정의가 흐려지고, 반대로 버리면 표본이 결과-무관하지 않게 줄어든다. 개수는 `strata_summary.json` 의 `unstable` 로 공개한다.
   - **② canonicalization 공급 dict 부재(정직 고지)**: `sap/unseen_target.py` 의 `canonicalize_accession` 은 `secondary_to_primary`(secondary→primary accession) 와 `seq_representative`(동일 서열 대표 병합) 를 **호출자가 공급**하도록 되어 있으나, 프로젝트에 그 매핑 파일이 **없다**. `09_target_family_clusters.csv` 의 `cluster_rep` 는 **50% identity 클러스터의 대표**이므로 "동일 서열 대표"와 의미가 달라 **대입하지 않는다**(파일 존재 = true, 그러나 미사용). → 두 인자 모두 **`None`(병합 없음)** 으로 고정하고 **isoform suffix 절단만** 적용한다. **방향성 고지**: 병합하지 않으면 동일 서열의 다른 accession 이 `seen` 대신 `unseen` 으로 잡혀 **전이 성능을 과대평가하지 않는 보수적 방향**이며(그 표적은 identity 축에서 `unseen_ge90` 으로 흡수된다), 이 사실을 논문 한계로 명시한다.
   - **③ `eligible_pt`**: 확증 런과 **동일하게** `eligible_pt=None`(= `master_Y` 370 PT 전열). **층 내부에서 PT 를 재선정하지 않는다** — 표본이 작은 층에서 PT 를 다시 고르면 층마다 estimand 가 달라진다. 층 표본에서 test-positive 가 0 인 PT 의 처리는 `sap/metrics.py` `macro_ap` 의 **동결된 undefined-AP 규칙**(macro 평균에서 제외 + 제외율 기록)에 그대로 위임한다.
   - **④ 층화 전용 seed(교집합 실측)**: bootstrap `seed=6001` · sign-flip `seed=6002` · `B=10000`(SAP 동결 기본값 준수). 착수 전 대조한 금지 집합 = 예약 seed(201~205·42) · §13-4 null 본런 seed(global 1000~1999 · family 11000~11999) · 프로브 seed(9000001~9000002 · 9000101~9000118) · SAP dry-run seed — 총 **2033개**와 대조해 **교집합 0** 을 실제로 확인했다.
   - **⑤ 구조축 정의와 경계값**: 약물 d 의 구조 유사도 = **fold-train 약물집합에 대한 max Morgan Tanimoto**. 지문은 `ladder_freeze.json` `morgan`(radius **2**, n_bits **2048**) **동결 정의 그대로**이며 파라미터 변경·재정의는 없다(`master_X.parquet` 은 SMILES 만 보관하므로 동결 파라미터로 결정적 생성 — 파싱 실패 0건). 사전등록에 구조축 경계 **수치가 없으므로** `SEQID_BOUNDARIES` 처럼 인용할 값이 없다 → **분위수 고정**으로 확정한다: 반복1 기준 max Tanimoto 의 **25/50/75 분위 = 0.2500 / 0.3284 / 0.4658**, 이를 **3반복에 공통 적용**한다. 반복별 max Tanimoto 요약(중앙값) = 반복1 0.3284 · 반복2 0.3282 · 반복3 0.3256. **결과를 본 뒤 경계를 조정하지 않는다.** 경계 산출은 **구조 정보만** 사용하며 라벨·예측·확증 OOF 를 일절 참조하지 않는다(산출 `experiments/runs/v3_stratification/struct_bounds.json`).
   - **⑥ 착수 전 게이트 실측(H-1)**: `ladder_freeze.json` sha16 **b885585aefbabb32** · SAP `manifest.json` sha16 **756d485feb4715e9**(v1.1) · SAP 모듈 **11/11** sha 일치 · sealed guard **12종** 존재 · consensus 3파일 sha256 = `metrics_full.json` `6a861640a0594053` · `consensus_M1b.npz` `f77a69528ebdb88c` · `consensus_M2b.npz` `8594592e2afae583` · 입력 전건 존재(반복1·2·3 `fold_membership.csv` 각 1092행 · `targets_human.fasta` **1191** 서열) · `open_sealed` **0건**.
   - **⑦ identity 인프라 사전 고지**: `IDENTITY_METHOD` 가 요구하는 pairwise identity 산출물이 프로젝트에 **존재하지 않는다**(`_mmseqs/` 에는 easy-**cluster** 결과만 있고 easy-**search** 결과는 없다). 도구 `mmseqs2` 는 **이미 설치되어 있어**(존재 = true) 지시서가 예외로 허용한 `brew install` 을 **실행하지 않았다 → 본 블록의 네트워크 사용은 0건**이다. 동결된 `IDENTITY_METHOD`(mmseqs2 easy-search, 양방향 best identity)를 **다른 도구로 대체하지 않는다**. 미정렬 쌍은 identity **0 으로 대체하지 않고** `missing` 으로 유지하며, `seqid_max` 는 **관측된 값만으로** max 를 취하고 관측 0건 약물 수를 별도 집계한다.
   - **⑧ 공개/봉인 범위(사전확정·변경 금지)**: **공개** = identity 산출물·파라미터·커버리지 · 층 배정표 · 층별 표본수/클러스터수 · formal·descriptive 라벨 · `B`·seed · 소요시간·메모리 · 해시 · 게이트 PASS/FAIL · `unstable_stratum` 개수. **봉인** = 층별 macro AP · Δ · CI(BCa/percentile) · sign-flip p · null 요약 · 부트스트랩 분포. 다중성 보정(Holm/BH)·성공판정은 **본 단계에서 하지 않는다** — 성공판정 단계에서 일괄한다.
   - **미실행(본 항목 시점)**: 층화 bootstrap · sign-flip · 층별 macro AP · Δ · CI · p · 다중성 보정 · 성공판정(`rq2_decision`·`rq3_decision`·`rq4_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · 개봉(`open_sealed`) · `ladder_freeze.json` 수정 · SAP 모듈 수정 · `docs/30` 수정 · 확증 split·fold·seed 재추첨 · `data/raw/` 변경 · 네트워크 · git commit·push.

---

- **2026-08-02 20:43 KST | §13-6 연속 유사도 층화 **실행 완료**(블록 H — identity 인프라 → 층 배정 → 층별 추정) — 산출 **전량 `_sealed/`**, 개봉 0 · 성공판정 0 · 다중성 보정 0. ① **identity 인프라 신설**: `IDENTITY_METHOD` 가 요구하는 pairwise identity 산출물이 프로젝트에 없어(기존 `_mmseqs/` = easy-**cluster** 결과뿐) `mmseqs2 18-8cc5c` easy-**search** all-vs-all 을 신규 실행했다 — 정렬쌍 **201,289/708,645**(28.40%), 자기적중 1191 제외, 양방향 best identity 로 대칭화, 미정렬 쌍은 **0 채움 없이 `missing` 유지**. ② **층 배정**: 반복1·2·3 각각 fold-local `T_train,f` 로 4분류·서열 6층·구조 4분위를 배정(총 **3,276행** = 1,092 × 3반복), 3반복 일치 약물만 primary·불일치는 `unstable_stratum` 분리(drug_class 71 · seq_stratum 10 · struct_bin 204). `no-target` **245** 약물은 `INFERENCE_MODE` 상 excluded 로 층화 추정에서 제외. ③ **계측 후 실행**: `B=100` 파일럿(최대 표본 층)으로 전 층 × `B=10000` 총 wall 을 **0.193일**로 추정 → 7일 임계 미만 확인 후 본계산, 실측 **8.03h**. 파일럿 산출은 전량 폐기(봉인 저장 0). ④ **층 13개** 산출(formal 9 · descriptive 4), BCa 불능 층은 percentile 대체 없이 `not_estimable` 그대로 봉인(**1건**). 게이트 전항 PASS(H-1 G0 · sealed guard 12종 불변 · H-4 약물 1092/scaffold 732/fold 교차 0/consensus shape [1092, 370] NaN 0 · seed 교집합 0) | 층화는 등록 §13-6 의 사전지정 분석이며, 본 블록은 **추정만** 수행하고 유의·성공·동등 판정을 일절 하지 않는다. 층별 수치를 단독 공개하면 다중성 보정 이전의 **조각 개봉**이 되기 때문 | 통계 정의·가설·집계 규칙·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 11모듈 + `manifest.json`(sha16 `756d485feb4715e9`)·`SEQID_BOUNDARIES`·`SEQID_STRATA`·`MIN_SUPPORT`·`INFERENCE_MODE`·`IDENTITY_METHOD` **전부 불변**, `docs/30` 무수정 | 확증 조회 = **Y(값 미열람)** — 층화 추정은 확증 consensus OOF 를 **기계 판독**해 새 추정을 만들었으므로 조회 대장에 Y 로 기록하되, `open_sealed` **0건** · 공개 노출 **0** 이다**

### 세부 (근거 추적)

21. **§13-6 연속 유사도 층화 실행 (블록 H — 실행·기록 전용)**:
   - **① identity 인프라(H-2) — 사실과 신설**: `sap/unseen_target.py` `IDENTITY_METHOD` 는 "mmseqs2 easy-search (bidirectional best identity)" 를 요구하나, 프로젝트의 `_mmseqs/` 에는 **easy-cluster 산출물만** 있었고 pairwise identity 산출물은 **존재하지 않았다**. 본 블록에서 `mmseqs2 18-8cc5c`(바이너리 sha256 `4fbce02c758bc330`)로 `targets_human.fasta`(1191 서열, sha256 `854eda439629f7e7`) self-search 를 실행했다. **도구는 이미 설치되어 있어 지시서가 예외 허용한 `brew install` 을 실행하지 않았고, 본 블록의 네트워크 사용은 0건**이다. 산출 = `identity_pairs.tsv`(sha256 `7a47e4951207fdf2`, 201,289행) + `identity_manifest.json`. 이 산출물은 **설계 자산이며 결과가 아니므로 공개 경로**에 둔다.
   - **②-1 대칭화·결측 처리**: `unseen_target.IDENTITY_METHOD` 문면 그대로 **양방향 best identity**(A→B, B→A 중 큰 값)로 대칭화하고 자기 자신은 제외했다(자기적중 1191건 = 전 서열). 커버리지 = **201,289/708,645(28.40%)**. 미정렬 쌍은 identity **0 으로 대체하지 않고 `missing` 으로 유지**했고, `seqid_max` 는 **관측된 값만으로** max 를 취했다. 관측 0건 약물 수(반복별) = **0 / 0 / 0** — 즉 all-unseen 약물 전원이 train 표적과의 identity 를 최소 1건 이상 관측했다.
   - **②-2 층 배정(H-3)**: `T_d` = `06_targets_human.csv` 의 cid→uniprot 집합에 `canonicalize_set(..., None, None)`(항목20 ②) 적용. `T_train,f` = 반복 r·fold f 의 **train 쪽 약물 표적 합집합**(모듈이 하지 않는 조립을 호출자가 수행). 약물 층 = `classify_drug`, 서열 층 = `drug_sequence_stratum`, 구조 층 = 항목20 ⑤ 분위 경계(0.2500/0.3284/0.4658). 산출 `experiments/runs/v3_stratification/strata_assignment.csv` **3,276행** — **배정은 결과가 아니므로 공개**.
   - **②-3 층별 표본(공개 범위 내)**: drug_class/all-seen n=552·clu=398·formal·CI estimable · drug_class/all-unseen n=18·clu=16·descriptive·CI estimable · drug_class/mixed n=206·clu=167·formal·CI estimable · drug_class/unstable_stratum n=71·clu=65·formal·CI estimable · seq_stratum/seen n=820·clu=571·formal·CI estimable · seq_stratum/unseen_ge90 n=2·clu=2·descriptive·CI not_estimable · seq_stratum/unseen_70_90 n=15·clu=13·descriptive·CI estimable · seq_stratum/unstable_stratum n=10·clu=9·descriptive·CI estimable · struct_bin/struct_q1 n=144·clu=107·formal·CI estimable · struct_bin/struct_q2 n=174·clu=137·formal·CI estimable · struct_bin/struct_q3 n=150·clu=117·formal·CI estimable · struct_bin/struct_q4 n=175·clu=130·formal·CI estimable · struct_bin/unstable_stratum n=204·clu=161·formal·CI estimable. `MIN_SUPPORT`(min_drugs=20 · min_positive_pt_support=5) 대조로 **formal 9 · descriptive 4** 라벨을 붙였다. **라벨링만 했고 해석하지 않는다.**
   - **②-4 `unstable_stratum`(항목20 ① 규정 적용)**: 3반복에서 층이 갈린 약물 = drug_class **71** · seq_stratum **10** · struct_bin **204**. 제외하지 않고 축별 **분리 집계 층**으로 함께 추정했다. 구조축의 불안정 비율이 가장 큰데, fold-train 약물집합이 반복마다 달라 max Tanimoto 가 분위 경계를 넘나들기 때문이다(사실 기술 — 해석 아님).
   - **③ 계측 후 실행(H-5-0)**: `B=100` 파일럿을 최대 표본 층(`seq_stratum/seen`, n_drugs=820 · clusters=571)에서 실측해 per-replicate 단가를 얻고, 전 층 × `B=10000` 총 wall 을 **4.62h(0.193일)** 로 추정했다 — 정지 임계 7.0일 대비 **초과 = false**. **파일럿 산출은 전량 폐기**(`pilot_artifacts_discarded=true`, 봉인 저장 0). 본계산 실측 wall = **8.03h**.
   - **④ 본계산(H-5-1)**: 층별 `metrics.macro_ap(y_s, P_s, eligible_pt=None)` → Δ, `bootstrap.paired_scaffold_bootstrap(..., B=10000, seed=6001, unit="scaffold_cluster")`, `signflip.scaffold_signflip(..., B=10000, seed=6002)`. primary CI = **BCa**, **BCa 실패 시 percentile 대체 금지** — `not_estimable` 그대로 봉인(**1/13층**). 산출은 전량 `_sealed/stratification_result.json`(sha256 `cd2969c73ed6bae7`). 공개 파일 `stratification_public.json` 은 층별 `n_drugs`·`n_clusters`·`n_eff_clusters`·formal/descriptive 라벨·`B`·seed·소요시간·해시·게이트 PASS/FAIL **뿐**이며, **층별 macro AP·Δ·CI·sign-flip p 는 한 값도 없다**(방어 assert 통과).
   - **⑤ 다중성·성공판정 미수행(사전확정 그대로)**: Holm/BH 는 **성공판정 단계에서 일괄** 적용한다. 본 단계는 **raw 산출만** 봉인했고 `sap/decision.py` 의 `rq2_decision`·`rq3_decision`·`rq4_decision`·`holm`·`bh_fdr`·`tost_equivalence` 를 **한 번도 호출하지 않았다**(`decision_functions_called` = `[]`, `multiplicity_applied` = false). 유의·성공·동등 여부를 판단하거나 서술하지 않는다.
   - **⑥ 게이트(H-1·H-4) 실측**: H-1 — `ladder_freeze.json` sha16 **b885585aefbabb32** · SAP `manifest.json` **756d485feb4715e9** · 11모듈 sha 일치 · sealed guard **12종** · 입력 전건 존재 · `open_sealed` 0. H-4 — 약물 **1092** 전수 · scaffold group **732** 전수 · fold 교차 **0** · 반복별 층 배정 합계 각 **1092** · `no-target` **245** 약물의 추정집합 포함 **0건** · consensus shape **[1092, 370]** = `y` shape **[1092, 370]** · NaN **0** · seed 교집합 **0**. 종료 시 sealed guard **12종 불변 = true**.
   - **⑦ 확증 조회 = Y(값 미열람) — 판정 근거**: 층화 계산은 확증 consensus OOF(`consensus_M1b.npz`·`consensus_M2b.npz`)를 **기계 판독**해 **새 추정을 생성**했다. 따라서 조회 대장에는 **Y** 로 기록한다. 다만 (i) `open_sealed`(사람 열람) **0건**, (ii) `access.log` 전건이 `machine_read`·`human_exposure=false`(누적 **28건**), (iii) 층별 AP·Δ·CI·p 의 **공개 노출 0**, (iv) 부호(`emit_sign`)조차 층별로는 공개하지 않았다 — 즉 **Y 는 "값을 보았다"가 아니라 "확증 산출물을 계산에 투입했다"** 는 뜻이다.
   - **⑧ 시간·전원 정직 고지(결론값 무영향 · 시간 비교만 제한)**: (i) **파일럿 추정이 과소했다** — H-5-0 의 스케일 모형은 층 비용을 `n_drugs` 에 선형으로 가정했으나, 실제 지배변수는 **층 표본 내 양성이 1건 이상인 PT 수**(`macro_ap` 의 동결된 undefined-AP 규칙상 양성 0 PT 는 건너뛴다)였다. 그 결과 추정 **4.62h** 대비 실측 **8.03h** 로 **1.74배** 더 걸렸다. **7일 정지 게이트 판정은 뒤집히지 않는다**(재추정치도 0.334일 ≪ 7일). (ii) **전원 상태가 런 중간에 바뀌었다** — 층 1·2 구간은 **배터리·`powermode=1`(저전력)**, 층 3~13 은 **AC·`powermode=0`** 이다(전원 샘플러 2026-08-01 18:57:27 KST 개시, 샘플 75건 중 AC 75 · `powermode=0` 75). 따라서 **층별 `wall_s` 는 서로 비교할 수 없다** — 층 간 비용 비교·후속 시간 추정에 투입 금지(`docs/45` 블록 C 추기와 동일 취급). (iii) **시스템 슬립으로 계산이 중단됐다** — 착수 2026-08-01 17:08:24 KST → 완료 2026-08-02 02:30:48 KST 로 로그 경과는 **9.37h** 인데 기록 `total_wall_s` 는 **8.03h** 이며, 차이 **80.8분**이 시스템 중단분이다(전원 샘플 결손 구간 **4건**이 증거). 원인 = AC 연결 상태에서도 발생한 macOS `Idle Sleep`·`Maintenance Sleep` 과 덮개 닫기(`Clamshell Sleep`). **기록 `wall_s` 는 `time.perf_counter()`(macOS `mach_absolute_time`) 누계라 슬립 구간을 세지 않으므로 순수 계산시간**이며, 중단은 벽시계 완료시각만 늘렸다. 2026-08-01 21:02 부터 `caffeinate -i -s -w <pid>` 로 유휴 슬립을 차단했다(`compute_lock.py` 는 경쟁 프로세스 판정에서 `caffeinate` 를 명시적으로 제외하므로 게이트에 영향 없음). (iv) **세 항목 모두 봉인 산출물·통계량에는 영향이 없다** — seed 고정(6001/6002)·단일 프로세스·연산 순서 불변이므로 Δ·CI·p 와 산출물 바이트는 전원·클럭·중단과 무관하다. 제한되는 것은 **시간 비교뿐**이다.
   - **⑨ 한계(정직 고지)**: (i) 항목20 ② 의 canonicalization 미병합 — 동일 서열의 다른 accession 이 `seen` 대신 `unseen` 으로 잡힐 수 있고(전이 성능을 과대평가하지 않는 보수적 방향, 해당 표적은 identity 축에서 `unseen_ge90` 으로 흡수) 이를 논문 한계로 명시한다. (ii) 서열축 상위 층(`unseen_40_70`·`unseen_lt40`)은 표본이 비어 있거나 극소여서 `MIN_SUPPORT` 미달 → **descriptive** 이며, 전이 주장의 핵심 층에서 formal inference 가 불가능하다. (iii) 구조축 경계는 사전등록에 수치가 없어 분위수로 고정한 것이므로 문헌 근거가 아니라 **본 데이터 분포 기반**이다(항목20 ⑤ 에 사전 기록). (iv) 층별 추정은 다중성 보정 전 raw 이며, 해석은 성공판정 단계 이후에만 가능하다.
   - **미실행**: 개봉(`open_sealed`) · 성공판정 함수 호출 · Holm/BH 다중성 보정 · TOST · 유의/성공/동등 서술 · 층별 수치의 공개 기입 · `ladder_freeze.json` 수정 · SAP 모듈 수정 · `docs/30` 수정 · `SEQID_BOUNDARIES`/`SEQID_STRATA`/`MIN_SUPPORT`/`INFERENCE_MODE`/`IDENTITY_METHOD` 변경 · 확증 split·fold·seed 재추첨 · `data/raw/` 변경 · 네트워크 · git commit·push.

---

- **2026-08-03 14:43 KST | 확증 RF 사다리 **잔여 6모델 OOF**(M0·M1·M2·P-ID·P-FAM·C-CAP) 착수 전 **판독확정 5건 사전기입**(블록 I-0) — 본 항목은 **계산 0 · 확증 OOF 미조회 · 개봉 0 · 성공판정 0 · 다중성 보정 0** 인 **pre-look** 기록이다. 배경: `sap/decision.py` 의 `HOLM_FAMILY`(크기 7 **고정**)는 ② `M2b−P-ID` ③ `M2b−P-FAM` ⑤ `M2b−M0` ⑥ `M2b−RF_tuned` ⑦ `RFseq−RF` ⑧ `RQ-int` 를 포함하는데, 현재 확증 OOF 는 `M1b`·`M2b` **2모델뿐**이라 ②③⑤⑥ 을 **계산할 수 없다**. 개봉(성공판정)은 family **전원이 갖춰진 뒤 일괄**이므로 잔여 모델 산출이 개봉의 임계경로다. 따라서 §13-7(GIN)·§13-8(late-fusion)보다 **앞당겨** 수행하되, 가설·모델정의·대비·다중성 규칙·α·성공기준은 **한 글자도 바꾸지 않는다** | 지시서 = `docs/48_v3_rf_remaining_oof_prompt_for_vscode.md` | 동결 확인 = `ladder_freeze.json` sha16 `b885585aefbabb32` · SAP `manifest.json` sha16 `756d485feb4715e9`(v1.1) · 11모듈 sha 일치 | **독립성 진술: 본 확정 시점까지 `_sealed/` 의 어떤 값도 사람이 열람하지 않았다(`open_sealed` 0건)**

### 세부 (근거 추적)

22. **확증 RF 사다리 잔여 6모델 OOF — 판독확정(pre-look, 블록 I-0) 및 §16 실행순서 이탈 amendment**:
   - **① 대상 모델 = 6개(재정의 금지)**: `ladder_confirmatory.FROZEN_MODELS` 8개(`M0 M1 M2 M1b M2b P-ID P-FAM C-CAP`) 중 확증 OOF 미산출인 **`M0` · `M1` · `M2` · `P-ID` · `P-FAM` · `C-CAP`**. 피처 블록 구성은 동결본(`MODEL_BLOCKS`) 그대로 사용하고 **재정의·재튜닝하지 않는다**. 이미 산출된 **`M1b` · `M2b` 는 재계산하지 않고 기존 sealed 산출물을 그대로 재사용**한다(재계산은 반복1~3 의 sealed 바이트를 흔들어 §13-3·13-5 기록과의 대응을 파괴하기 때문). split 역시 `data/processed/splits/confirmatory/rep{1,2,3}_seed{201,202,203}/folds.json` 을 **그대로 읽어 쓴다** — 새 split 생성·재추첨 금지.
   - **② `RF_tuned`(Holm ⑥)는 이 블록에서 계산하지 않는다**: `RF_tuned` 는 동결 사다리 8모델에 포함되지 않는 **별도 baseline**(v1 `results_fairtune` 계열)이다. 본 블록에서는 **소싱 가능성만 조사해 보고**하고(어떤 구성이 baseline 인지 · 확증 fold 에 적용 가능한지 · 추가 동결이 필요한지), **계산은 다음 지시서로 넘긴다**. 조사 결과는 수행 리포트 §6 에 기록한다.
   - **③ 공개 범위 = Δ 의 부호도 비공개**: §13-3·§13-5 에서 `M2b−M1b` 의 **부호**를 공개한 것은 사전등록된 **primary interim look** 이었다. ②③⑤⑥ 의 부호는 **등록에 없는 추가 노출**이므로, 본 블록의 공개는 **완주 개수 · 해시 · 시간 · 메모리 · 게이트 PASS/FAIL 뿐**이고 **Δ·AP·CI·p·부호 전부 봉인**한다. 공개 파일 `rest_public.json` 에는 `macro_ap`·`delta`·`sign`·`ci_*`·`p_*` 키가 **부재**함을 방어 assert 로 강제한다.
   - **④ consensus 산출 범위**: 6모델 각각에 대해 SAP `consensus.build_consensus`(**방법A** — 약물-PT 별 raw probability 3반복 **산술평균**)를 `M1b`·`M2b` 와 **동일하게** 적용하되, 기존 `experiments/runs/v3_consensus_rep123/` 는 **불변**으로 두고 **별도 디렉터리**에 저장한다. **반복 순서·가중치 변경 금지.**
   - **⑤ §16 실행순서 이탈 amendment (ChatGPT 4차 리뷰 A9 반영 — `docs/50` §8)** — 본 블록은 사전등록 §16 실행순서보다 앞당겨 수행된다. 이 amendment 는 "원 사전등록의 단순 구현"이 아니라 **부호 공개 이후의 post-interim amendment** 로 표기한다(리뷰 원칙: 날짜가 찍힌 amendment 로 구분). 결의문 원문:

     > Operational order deviation from §16: confirmatory RF OOF artifacts required for hypotheses ②, ③, ⑤, and ⑥ will be generated before the later registered blocks. The sole purpose is to complete all members of the fixed Holm family before any inferential output is unsealed. No hypothesis, model specification, contrast, multiplicity rule, alpha level, or success criterion is changed. All intermediate artifacts remain sealed and machine-readable only. Unsealing will occur once, after completion and integrity verification of the full family and documented supervisor approval.

     - **시각(KST)**: 2026-08-03 14:43:19 KST — **본계산 착수 전**.
     - **독립성 진술**: 본 확정은 `_sealed/` 의 **어떤 값에도 접근하지 않은 상태**에서 작성됐다. 지금까지 사람에게 노출된 확증 산출은 §13-3·§13-5 의 `M2b−M1b` **부호뿐**이며, 그 부호는 본 amendment 가 정하는 **어떤 항목(대상 모델·공개 범위·consensus 방법·실행 순서)에도 입력되지 않았다**. `sap/redaction.py` 의 `open_sealed`(사람 열람) 호출은 프로젝트 전 구간 **0건**이고, 지금까지의 `_sealed/` 접근은 전건 `machine_read`·`human_exposure=false` 다.
     - **code commit 부재 사유**: 본 프로젝트는 실행 시점의 코드 상태를 **git commit 이 아니라 동결 해시**(`ladder_freeze.json` sha16 `b885585aefbabb32` · SAP `manifest.json` sha16 `756d485feb4715e9` + 11모듈 개별 sha256)로 고정한다. 지시서(`docs/48` §0 "절대 금지")가 **git commit·push 를 명시적으로 금지**하므로 본 블록은 commit 을 남기지 않으며, 시점 증명은 위 해시 + 본 append-only 기록 + `experiments/provenance/{first_look_log,ledger}.json` 이 대신한다. (공개 리포지토리 위생 점검은 별건 블록 J 에서 다루며, 그 블록은 현재 보류 상태다.)
   - **미실행(본 항목 시점)**: 확증 OOF 조회 · 모델 학습 · 개봉(`open_sealed`) · 성공판정 함수 호출(`rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · bootstrap/sign-flip/p · Δ·AP·CI·p·**부호**의 기입 · 기존 sealed 산출물 수정 · split·fold·seed 재추첨 · `ladder_freeze.json`·SAP 모듈·`docs/30` 수정 · GIN·late-fusion·interaction·외부검증 착수 · `data/raw/` 변경 · 네트워크 · git commit·push.

---

- **2026-08-04 01:18 KST | 확증 RF 사다리 **잔여 6모델**(`M0` · `M1` · `M2` · `P-ID` · `P-FAM` · `C-CAP`) OOF **실행 완료**(블록 I) — 3반복(seed 201·202·203) × 5 fold × 6모델 = **90개 (반복,모델,fold) 전건 완주** + 6모델 consensus. 산출 **전량 `_sealed/`**, **개봉 0 · 성공판정 0 · 다중성 보정 0 · Δ 미산출 · 부호 미산출(`emit_sign` 호출 0)**. 목적 = `sap/decision.py` `HOLM_FAMILY`(크기 7 **고정**)의 ② `M2b−P-ID` ③ `M2b−P-FAM` ⑤ `M2b−M0` 를 계산 가능하게 만드는 **산출물 확보**이며, 개봉은 family 전원이 갖춰진 뒤 **일괄** 수행한다. ① **기존 산출 재사용**: `M1b`·`M2b` 는 재계산하지 않고 §13-3·§13-5 sealed 를 그대로 두었으며, split 은 `rep{1,2,3}_seed{201,202,203}/folds.json` 을 **그대로 읽었다**(새 split 생성·재추첨 0). ② **코드경로 동일성 증명**: 신규 러너 `confirmatory_oof_rest.py` 로 `M2b` 반복1 fold0(218행 × 370 PT, dim 2124, dtype `float64`)을 재계산해 기존 sealed `oof_M2b.npz` 의 해당 슬라이스와 **원시 바이트 동일**함을 확인했다(`byte_identical` = true). 기존 파일은 **읽기만** 했다(`machine_read`). ③ **정합 검증 전항 PASS**: 약물 **1092** 전수 · scaffold group **732** 전수 · scaffold-fold 교차 **0**(3반복) · rare-PT(모든 outer train fold 에 PT별 양성 ≥1) 위반 **0** · 반복별 OOF shape **(1092, 370)** · NaN **0** · 모델별 `leak_rows` **0**. ④ **계측 후 실행**: 최고차원 모델 `P-ID`(dim 3173) 1 fold 를 실측해 총 wall 을 **0.070일**로 추정 → 정지 임계 7.0일 미만 확인 후 본계산 진입, 실측 계산 wall **2.34시간**(세션 1개). ⑤ **공개 범위 축소 준수**(항목22 ③): 공개 파일 `rest_public.json` 에는 완주 개수·해시·시간·메모리·게이트 PASS/FAIL **뿐**이며 `macro_ap`·`delta`·`sign`·`ci_*`·`p_*` 키가 **부재**함을 방어 assert 로 확인했다. 게이트 전항 PASS(G0 · G-IDLE A/B · sealed guard **30종 불변**) | **통계 정의·가설·대비·다중성 규칙·α·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 11모듈 + `manifest.json`(sha16 `756d485feb4715e9`) 전부 불변**, `docs/30` 무수정 | 확증 조회 = **Y(값 미열람)** — 잔여 6모델 OOF 를 **새로 생성**했으므로 대장에 Y 로 기록하되, `open_sealed` **0건** · Δ·AP·CI·p·**부호**의 공개 노출 **0** 이다**

### 세부 (근거 추적)

23. **확증 RF 사다리 잔여 6모델 OOF 실행 (블록 I — 실행·기록 전용, Holm family ②③⑤⑥ 산출물 확보)**:
   - **① 왜 이 블록이 §13-7·13-8 보다 먼저인가**: `HOLM_FAMILY` 는 **크기 7 고정**이고 Holm 보정은 family 전원의 p 가 있어야 성립한다. 확증 OOF 에 `M1b`·`M2b` 밖에 없으면 ②③⑤⑥ 의 p 를 만들 수 없고, `HOLM_UNDEFINED_FILL=1.0` 으로 채우면 **검정력을 스스로 버리는** 셈이 된다. 따라서 잔여 모델 산출이 **개봉의 임계경로**이며, 이 순서 변경은 항목22 ⑤ 의 날짜 찍힌 **post-interim amendment** 로 사전 기입한 뒤 착수했다(가설·모델정의·대비·다중성 규칙·α·성공기준 **불변**).
   - **② 대상·재사용 경계**: 계산 대상 = `M0` · `M1` · `M2` · `P-ID` · `P-FAM` · `C-CAP` (동결 `FROZEN_MODELS` 8개 중 미산출 6개). `B_m1b` 기준 분기 3모델(`P-ID`·`P-FAM`·`C-CAP`)은 primary `B_m1b`(10차원, pChEMBL 제외 — 항목6 재지정본)을 그대로 쓴다. 모델별 조립 차원(반복1 fold0 train fit 기준) = M0 2048 · M1 2050 · M2 2114 · P-ID 3173 · P-FAM 2102 · C-CAP 2124. `M1b`·`M2b` 는 **재계산 금지** 규정대로 손대지 않았고, 종료 시 기존 sealed **30종**의 sha256 이 시작과 **완전 일치**함을 확인했다(`access.log` 은 `machine_read` append 로 변하므로 guard 대상에서 제외).
   - **③ 하네스 재사용과 동일성**: 기존 `confirmatory_oof_rep1.py`·`confirmatory_oof_rep23.py` 는 **한 줄도 수정하지 않고** `gate0_verify`·`sha256_file` 및 `ladder_confirmatory` 의 블록 클래스·`rf_fit_predict`·`MODEL_BLOCKS` 를 **import 재사용**했다(신규 파일 `confirmatory_oof_rest.py` 는 모델 루프만 6개로 교체). RF `random_state=42` 전 fold 공통 · `eligible_pt=None` · undefined-AP 는 `sap/metrics.macro_ap` 동결 규칙에 위임 · BLAS 스레드 환경변수 **미설정** 유지 · RF 병렬 인자 무변경 — 즉 반복1·2·3 과 **동일 compute 조건**이다.
   - **③-1 바이트 동일성 증명의 범위(정직 고지)**: 기존 sealed `oof_M2b.npz` 는 **5 fold 전체** OOF 를 담으므로 1 fold 재계산과 **파일 단위** 비교는 원리적으로 불가능하다. 따라서 fold0 의 test 행 슬라이스를 dtype·shape·`tobytes()` **3중 일치**로 비교했다. 이 비교가 덮는 것 = fold 로더 · 블록 인스턴스화 · fold-train 전용 fit · 행렬 조립 순서 · `rf_fit_predict` · dtype 승격 경로 **전부**이며, 덮지 않는 것 = 나머지 4 fold 의 재현(비용 대비 실익 없음 — 동일 코드경로가 fold 인덱스만 바꿔 도는 구조).
   - **④ 누수 방지**: 모델별로 필요한 블록만 **fold-train 에서만** fit 하고(`B0`→`B1`→`B_seq`→`C_ccap`→`B_pid`→`B_m1b`→`B_fam` 표준 순서, `C_ccap` 은 `B_seq` 이후), 매 fold 마다 `leakage_assert` 로 `leak_rows=0` 을 확인했다. `B_seq` PCA 는 기존 규약대로 **outer-fold train ∩ 매핑 약물**에서만 fit 했고 그 모집단이 정확히 일치함을 `np.array_equal` 로 강제했다. `B_pid`·`B_fam` 의 vocab 은 fold-train 약물의 표적/family 만으로 구성하고 test OOV 는 드롭했다(동결 정의).
   - **⑤ consensus(항목22 ④ 그대로)**: 6모델 각각 SAP `consensus.build_consensus`(**방법A** — 약물-PT 별 raw probability 3반복 **산술평균**, 반복 순서 1→2→3 고정·가중치 없음)를 적용해 **별도 디렉터리** `experiments/runs/v3_confirm_rest_consensus_rep123/_sealed/` 에 저장했다. 기존 `v3_consensus_rep123/` 는 **불변**이다.
   - **⑥ Δ·부호를 만들지 않았다**: 봉인 `metrics_full.json` 에는 모델별 macro AP 와 fold별 macro AP 만 담고 **Δ 를 계산하지 않았으며 `sap/redaction.emit_sign` 을 한 번도 호출하지 않았다**. §13-3·§13-5 의 부호 공개는 등록된 primary interim look 이었지만 ②③⑤⑥ 의 부호는 **등록에 없는 추가 노출**이므로, 만들지 않는 것이 가장 보수적이다. Δ·CI·p 는 개봉 단계에서 consensus 위 bootstrap/sign-flip 으로 **일괄** 산출한다.
   - **⑦ 체크포인트·세션 분할**: `(반복, 모델, fold)` 단위로 `_sealed/checkpoint.jsonl` 에 완주를 기록하고 재개 시 skip 했다(중복 키 검출 assert 내장). 세션 간에는 환경 지문(`env_fingerprint.json`: python·numpy·scipy·sklearn·joblib·pandas 버전 + `ladder_freeze`/SAP manifest sha256 + split 파일 sha256 + machine/os) 일치를 확인하고 `gate_c_settle` 을 거쳤다. 총 세션 **1개**, fold 단위 계산시간은 최소 93초 ~ 최대 97초였다.
   - **⑧ `RF_tuned`(Holm ⑥)는 계산하지 않았다 — 소싱 조사 결과**: `RF_tuned` 는 동결 사다리 8모델에 **포함되지 않는** 별도 baseline 으로, 사전등록 §"추가 baseline(필수)" 의 "Morgan RF·tuned RF" 에 해당한다. 구성 자체는 `v1_RF/results_fairtune/best_config.yaml`(sha16 `f411602e9a46a34c`)에 **완전 명세**돼 있고 **valid 로만 선택**(test 미사용, 탐색예산 16, `sample_seed=42`)됐으므로 확증 OOF 에 대해 **결과-독립**이다. 그러나 그대로는 확증 fold 에 적용할 수 없다 — (i) **지문이 다르다**: 튜닝 구성은 Morgan **r=3**/2048bit 인데 동결 블록 `B0` 는 **r=2**/2048bit 다 → 신규 블록(예 `B0_r3`) **동결이 필요**하다. (ii) **RF 하이퍼가 다르다**: `n_estimators=1000·max_depth=40·max_features=sqrt·min_samples_leaf=2·class_weight=balanced` vs 동결 `RF_KW`(`300·None·class_weight=balanced_subsample`). (iii) **평가 맥락이 다르다**: v1 선택은 seed-42 **개발** split(873/109/110)·**301 PT** 기준이고 확증은 5-fold scaffold CV·**370 PT** 다. → **결론: `RF_tuned` 는 "새 블록 + 새 하이퍼셋"의 추가 동결(amendment)을 선행해야 계산 가능하며, 본 블록의 "모델 재정의 금지" 제약 안에서는 착수할 수 없다.** 계산은 다음 지시서로 넘기고, 그 지시서는 (a) `B0_r3` 블록 동결, (b) `RF_tuned` 하이퍼셋 동결, (c) 두 항목이 **결과-독립**임을 명시하는 amendment 를 선행해야 한다. 개봉 시점까지 ⑥ 의 p 가 없으면 `HOLM_UNDEFINED_FILL=1.0` 이 적용되며(드롭 금지 규정), 이는 검정력에 **보수적** 방향이다.
   - **⑨ 시간 고지(결론값 무영향)**: 기록 `wall_s` 는 `time.perf_counter()` 누계라 macOS 시스템 슬립 구간을 세지 않는 **순수 계산시간**이다. 러너는 `caffeinate -i -s` 아래에서 실행했고, G-IDLE 게이트 A(1분 load < 2.0)를 **우회하지 않기 위해** 시스템이 유휴가 될 때까지 진입을 미루는 대기 런처를 사용했다(게이트 판정 자체는 러너 안에서 그대로 수행). 계측·추정 시간은 **결과-독립 계측치**이며 통계량·봉인 산출물 바이트와 무관하다(seed 고정·연산 순서 불변).
   - **⑩ 한계(정직 고지)**: (i) Holm family 7 중 본 블록이 채운 것은 ②③⑤ 의 **산출물**뿐이고, ⑥(`RF_tuned`)·⑦(`RFseq−RF`)·⑧(`RQ-int`)은 여전히 미산출이다 — ⑧ 은 미동결 3건이 선결돼야 한다. (ii) ④(재배치 null)는 §13-4 에서 이미 완주했다. (iii) 본 블록은 **추정도 판정도 하지 않았다** — 산출물만 만들었다. 어떤 모델이 어떤 모델보다 낫다는 진술은 개봉·다중성 보정 이후에만 가능하다.
   - **미실행**: 개봉(`open_sealed`) · 성공판정 함수 호출(`rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · bootstrap/sign-flip/p · Δ 산출 · 부호 산출(`emit_sign`) · `RF_tuned` 계산 · GIN(§13-7) · late-fusion(§13-8) · interaction · 외부/temporal 검증 · 기존 sealed 수정 · split·fold·seed 재추첨 · `ladder_freeze.json` 수정 · SAP 모듈 수정 · `docs/30` 수정 · `data/raw/` 변경 · 네트워크 · git commit·push.

---

- **2026-08-04 09:29 KST | 층 회계 정합 **독립 재현** + 회계 assertion **코드 고정** + §13-6 **커버리지 감사**(블록 K) — 교수님 2026-08-03 회신(`docs/53` §4·§5) 이행. **모델학습 0 · permutation 0 · bootstrap 0 · sign-flip 0 · 네트워크 0 · 개봉 0 · 성공판정 0 · 다중성 보정 0 · Δ·AP·CI·p 재산출 0**. 판독 전용이며 기존 공개 파일·`_sealed/` 는 **바이트 불변**(신규 4파일만 추가). 결과: ① 교수님이 지적하신 "820+2+15=837 ≠ 847"·"unseen 합계 17인데 본문 18" 은 **데이터·계산 오류가 아니라 보고 누락**(`unstable_stratum` 미기재)임을 러너가 **독립 재현으로 확인**했다 — 세 축 모두 `Σ stable(no-target 제외) + unstable = 847`, `847 + no-target 245 = 1,092` 로 닫힌다. ② "18 vs 17" 은 **경계 사례 정확히 1건**이다. ③ 회계 항등식을 `stratification_run.py` 의 하드 assert 로 **코드 고정**해 향후 재실행 시 자동 강제되게 했다. ④ 사전등록 §11 연속축 6종 중 **2종 수행 · 4종 미수행**(unseen-target proportion 4변형 전부)이며, `Δ(M2b−P-ID)` 층화는 블록 I 완료로 **선행 조건이 해소**됐다(지금 계산 가능, 본 블록 범위 밖) | 지시서 = `docs/54_v3_strata_accounting_prompt_for_vscode.md` · 리포트 = `docs/54_v3_strata_accounting_report.md` | 동결 확인 = `ladder_freeze.json`·SAP 11모듈·`manifest.json` **무수정**(본 블록은 읽지도 않는 회계 판독), `docs/30` 무수정 | **확증 조회 = N**(새 추정 없음 · `_sealed/` 값 미열람 · `open_sealed` 0건 · 봉인 파일은 sha256 지문 대조만)

### 세부 (근거 추적)

24. **층 회계 정합 검증 + assertion 고정 + §13-6 커버리지 감사 (블록 K — 판독·기록 전용)**:
   - **① 독립 재현(cowork 값 무신뢰 원칙)**: `docs/54` K-0 의 cowork 실측표를 그대로 믿지 않고, 신규 판독 전용 스크립트 `v3_Multimodal/src/strata_accounting_check.py` 가 **동결 입력·동결 연산자로 층 배정을 처음부터 재계산**했다(입력 = `master_X/Y.parquet` · `06_targets_human.csv` · 확증 split `fold_membership.csv` 3반복 · `identity_pairs.tsv` · `_max_tanimoto.npy` · `struct_bounds.json`; 연산자 = `sap/unseen_target.classify_drug`·`drug_sequence_stratum` **무수정**). 재계산 3,276행이 기존 `strata_assignment.csv` 와 `fold`·`drug_class`·`seq_stratum`·`n_targets`·`n_unseen_targets`·`n_seqid_observed`·`struct_bin`·`max_tanimoto` **전 컬럼 불일치 0** 으로 일치했다. **cowork 표와 실측이 전건 일치**하여 정본 교체는 불필요했다.
   - **② 하드 회계 assert(핵심)** — 축마다 `Σ stable(no-target 제외) + unstable_stratum == 847` **AND** `847 + no-target 245 == 1,092` **AND** 세 축의 추정 모수가 동일. 실측: `drug_class` 552+206+18+**71**=847 · `seq_stratum` 820+2+15+**10**=847 · `struct_bin` 144+174+150+175+**204**=847. 추가로 (i) 파일에 저장된 `stable_*` 컬럼이 재계산 결과와 일치, (ii) 세 축의 **추정 대상 약물 집합이 집합 단위로 동일**(개수 일치보다 강한 조건), (iii) `stratification_public.json` 의 `units[].n_drugs` 축별 합이 847 — 전항 PASS.
   - **③ assertion 코드 고정**: 동일 assert 블록을 `stratification_run.py` 에 `assert_strata_accounting(df)` 로 **추가**하고 `stage_strata`(배정 직후)·`stage_verify`(H-4 검증)에서 호출하게 했다. **본 블록에서 `stratification_run.py` 를 실행하지 않았다** — 기존 산출물 재생성 금지 규정 때문이며, 따라서 `strata_assignment.csv`·`strata_summary.json`·`stratification_public.json` 은 바이트 불변이다.
   - **④ 경계·불일치 사례 전건 분류**(`unstable_cases.csv`, 855행 = 285 약물-축 × 3반복): `struct_bin` 204건 **전부 경계 인접**(반복 간 max Tanimoto 가 분위 경계 0.2500/0.3284/0.4658 을 넘나듦) · `drug_class` 71건 **전부 집합 변동**(fold-train 표적 집합 변동 — 가정하지 않고 `n_unseen_targets` 가 반복 간 실제로 달라짐을 확인) · `seq_stratum` 10건 = 집합 변동 9 + 경계 인접 1. **관측 결손**(all-unseen 且 `n_seqid_observed==0`)은 반복 1·2·3 **전부 0건**으로 재확인됐고, **분류 불가 0건**이다.
   - **⑤ "18 vs 17" 경계 사례 1건의 정체**: `cid 16139605`(표적 1개). 반복1 = `unseen_70_90`(drug-level max identity **87.5%**), 반복2·3 = `unseen_ge90`(**100.0%**) — 즉 **90% 경계까지 거리 2.5%p** 로 반복 간 층이 바뀐다. `drug_class` 는 3반복 모두 `all-unseen` 으로 stable 이므로, `drug_class` stable `all-unseen` 18명 중 **17명만** 서열축에서도 stable(`unseen_70_90` 15 + `unseen_ge90` 2)이고 이 1명이 서열축 `unstable` 이다. 역방향 교차표에서도 서열축 unseen 층 17명은 **전원** `all-unseen` 이다(교차 오염 0). **두 숫자는 서로 다른 축의 서로 다른 stable 필터 결과이며 모순이 아니다.** ⚠️ 부수 관측(설계 진단, 결과 아님): 반복2·3 의 identity 가 **100.0%** 인데도 `unseen` 으로 분류되는 것은 H-0-2 canonicalization 이 isoform suffix 절단만 적용하고 `secondary_to_primary`·`seq_representative` 병합을 **비활성**했기 때문이다(동일 서열의 다른 accession 은 exact-seen 으로 병합되지 않는다). 동결 연산자를 바꾸지 않으며 **한계로만 명시**한다.
   - **⑥ §13-6 커버리지 감사(계산 없음 · 명세만)** — 사전등록 §11 연속축 대비: **수행 2종**(max Morgan Tanimoto · 표적 max sequence identity) · **미수행 4종**(unseen-target proportion 의 unweighted · evidence-weighted · mechanism-target indicator · dominant-target-cold). 대비축은 `Δ(M2b−M1b)` 수행(수행 축 한정) · `Δ(M2b−P-ID)` 미수행. 미수행 항목의 상태: `unweighted` 는 **입력 가용**(`strata_assignment.csv` 의 `n_unseen_targets`/`n_targets`)이나 **층 경계가 SAP·등록 어디에도 미동결**; `evidence-weighted`·`dominant-target-cold` 는 입력 부분가용(`07_agg_topk.csv` weight·rank·pChEMBL, top-k≤5 한정) + **정의 미동결**; `mechanism-target indicator` 는 현 산출물에 **표적 수준 mechanism 플래그 부재**(`03_targets.csv` 의 `source` 가 전건 `chembl` 단일값, `08_m1b_covariates.csv` 는 약물 수준 `mechanism_target_n` 만) → 캐시(`_cache/` 내 ChEMBL `mechanism` 응답 1,009 파일) 재파싱으로 **네트워크 없이 재생성 가능**하나 판정 기준은 미동결. **미동결 정의는 본 블록에서 정하지 않았다** — Δ 부호 4건이 이미 공개된 뒤이므로 확정은 **post-interim amendment** 로만 가능하다. ★ `Δ(M2b−P-ID)` 는 블록 I 완료로 `consensus_P-ID.npz` 가 확보돼 **선행 조건이 해소**됐다 — "블록 I 이후 가능"이 아니라 **지금 계산 가능하며 다만 본 블록 범위 밖**이고, 후속 블록 후보로 제안한다.
   - **⑦ 축별 위상 라벨(교수님 2026-08-03 결정 반영, 라벨만 부착·해석 없음)**: `struct_bin`·`seq_stratum` = `confirmatory`(연속 표적 유사도 축 = 확증 유지) · `drug_class` = `data_characteristic`(세 집단의 **분포 자체는 데이터 특성으로 보고**, **재분할 결과 분석은 exploratory**). `drug_class` 는 등록 §11 의 연속축 목록에 **포함되지 않는다**(§9 범주 정의)는 사실도 감사표에 명기했다.
   - **⑧ 무결성 게이트**: 배타 락(`role="recorder"`) 획득·정상 해제 · **G-IDLE 게이트 A 를 우회하지 않았다**(최초 진입 시 `load1=2.55` 로 거부 → 임계 변경 없이 유휴 대기 런처로 `load1<1.5` 연속 40초 도달까지 진입만 미룬 뒤 재진입, 러너 자체 게이트 A 는 `load1=1.49 < 2.0` 으로 PASS) · **sealed guard 157종**(`experiments/runs/**/_sealed/` 하위 트리 전 파일, `access.log` 제외) sha256 이 시작·종료 **완전 일치** · `_sealed/stratification_result.json` sha256 `cd2969c73ed6bae7…` 불변. 공개 산출물 3종에 `macro_ap`·`delta`·`sign`·`ci_*`·`p_*`·`boot_*` 키가 **부재**함을 방어 assert 로 강제했다(검출 0).
   - **미실행**: 개봉(`open_sealed`) · 성공판정 함수 호출(`rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · 다중성 보정 · bootstrap/sign-flip/permutation · 층별 Δ·AP·CI·p 재산출 · 부호 산출·공개 · 미실행 축(unseen-target proportion 등) **계산 착수** · 미동결 정의 확정 · 기존 sealed·공개 산출물 수정 · `stratification_run.py` **실행** · `ladder_freeze.json`·SAP 모듈·`sap/manifest.json`·`docs/30` 수정 · split·fold·seed 재추첨 · `data/raw/` 변경 · 네트워크 · git commit·push.

---

- **2026-08-04 21:22 KST | §13-6 커버리지 C2 — **`Δ(M2b−P-ID)` 층화** 착수 전 **판독확정 3건 사전기입**(블록 L-0) — 본 항목은 **계산 0 · `_sealed/` 값 미열람(지문 대조만) · 개봉 0 · 성공판정 0 · 다중성 보정 0** 인 **pre-look** 기록이다. 배경: 블록 H(§13-6)는 등록 §11 이 요구하는 두 대비 중 `Δ(M2b−M1b)` 층화만 수행했고 **`Δ(M2b−P-ID)` 층화는 미수행**이었다(`docs/54` 커버리지 감사 C2). 블록 I(2026-08-04 01:20)로 `consensus_P-ID.npz` 가 확보돼 **선행 조건이 해소**됐고, 대비 자체는 이미 `sap/decision.py` `HOLM_FAMILY` ②(`M2b-P-ID`)로 **동결**돼 있어 **추가 amendment 가 필요 없다**. 본 블록은 **모델학습 0 · 새 OOF 생성 0**(기존 consensus 재사용)이며 층 배정·구조축 경계·identity 산출물도 **전부 기존 산출 그대로** 쓴다 | 지시서 = `docs/57_v3_pid_stratification_prompt_for_vscode.md` | 동결 확인 = `ladder_freeze.json` sha16 `b885585aefbabb32` · SAP `manifest.json` sha16 `756d485feb4715e9`(v1.1) · 11모듈 sha 일치 | **독립성 진술: 본 확정 시점까지 `_sealed/` 의 어떤 값도 사람이 열람하지 않았다(`open_sealed` 0건)**

### 세부 (근거 추적)

25. **§13-6 커버리지 C2 — `Δ(M2b−P-ID)` 층화 판독확정(pre-look, 블록 L-0)**:
   - **① 대비 정의(부호 규약 고정)**: `Δ_PID = macro AP(M2b) − macro AP(P-ID)`. 피감수 = `M2b`, 감수 = `P-ID` 로 두어 `sap/decision.py` `HOLM_FAMILY` ②(`M2b-P-ID`, `MULTIPLICITY_MANIFEST` contrast `"M2b − P-ID"`) 및 블록 H 의 `Δ(M2b−M1b)` 와 **동일 방향**으로 고정한다. 구현상으로는 동결 연산자 `sap/bootstrap.paired_scaffold_bootstrap` · `sap/signflip.scaffold_signflip` 의 **첫 인자 = 기준 arm · 둘째 인자 = 비교 arm** 슬롯에 각각 `P-ID` · `M2b` 를 배치한다(두 함수 모두 `Δ = macroAP(둘째) − macroAP(첫째)` 로 정의돼 있다). 이 방향이 규약과 일치하는지는 **합성 데이터로 1회 검증**한 뒤 본계산에 들어가며, 확증 값으로는 검증하지 않는다.
   - **② 재표집 seed = 블록 H 와 동일 재사용(새 seed 를 뽑지 않는다)**: bootstrap `seed=6001` · sign-flip `seed=6002` · `B=10000` · `unit="scaffold_cluster"` · primary CI = `BCa`(불능 시 percentile 대체 금지 → `not_estimable` 그대로 봉인). **사유**: 층·B·재표집 인덱스를 `M1b` 대비와 **동일 조건**으로 두어야 두 대비의 차이가 **재표집 난수 차이에서 생기지 않는다**. 새 seed 를 뽑으면 사후 선택(여러 seed 중 고르기)의 여지가 생기므로, 그 여지를 원천 제거한다.
   - **③ 공개 범위 = 블록 H 와 동일하되 **부호도 비공개****: 공개는 층별 표본수·클러스터수·`n_eff_clusters`·formal/descriptive 라벨·축 위상 라벨·`B`·seed·소요시간·해시·게이트 PASS/FAIL **뿐**이다. `M2b−P-ID` 는 Holm family ② 이므로 **부호 노출도 조각 개봉**에 해당한다 — §13-3·§13-5 에서 공개한 `M2b−M1b` 의 부호는 사전등록된 **primary interim look** 이었지만 ② 의 부호는 **등록에 없는 추가 노출**이다. 따라서 Δ·AP·CI·p·**부호** 전부 봉인하고, 공개 파일에 `macro_ap`·`delta`·`sign`·`ci_*`·`p_*`·`boot_*`·`null_*` 키가 **부재**함을 방어 assert 로 강제한다. 이는 블록 I(항목22 ③)와 동일한 축소 규정이다.
   - **④ 재계산 금지 경계(본 블록이 만들지 않는 것)**: consensus OOF(`M2b`·`P-ID`·`M1b`) · 층 배정(`strata_assignment.csv`) · 구조축 경계(`struct_bounds.json`) · identity(`identity_pairs.tsv`) 는 **전부 기존 산출을 그대로 읽는다**. 기존 `_sealed/` 는 **일체 덮어쓰지 않으며**(블록 H 의 `stratification_result.json` 포함) 신규 산출은 **신규 디렉터리** `experiments/runs/v3_stratification_pid/_sealed/` 에만 쓴다. 층 정의·필터도 블록 H 와 **완전 동일**(`no-target` 245 제외 · 3반복 일치=stable · 불일치=`unstable_stratum` · `eligible_pt=None` 370 PT 전열 · undefined-AP 는 `sap/metrics.macro_ap` 동결 규칙에 위임 · 층 수 **13**)이며, 블록 H 러너 `stratification_run.py` 는 **수정하지 않고 import 재사용**한다.
   - **⑤ 범위 밖(착수 금지)**: A3~A6 unseen-target proportion 4변형(정의 미동결 — 별도 amendment 대상) · `RF_tuned`(⑥, `B0_r3` 동결 amendment 선행) · late-fusion(⑦) · GIN·RQ-int(⑧, 외부 통계 검토 대기) · 성공판정(개봉).
   - **미실행(본 항목 시점)**: `_sealed/` 값 열람(`open_sealed`) · 성공판정 함수 호출(`rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · 다중성 보정 · bootstrap/sign-flip/p · Δ·AP·CI·p·**부호**의 산출과 기입 · 모델 학습 · 새 OOF 생성 · 기존 sealed·공개 산출물 수정 · `stratification_run.py` 수정 · split·fold·seed 재추첨 · `ladder_freeze.json`·SAP 모듈·`sap/manifest.json`·`docs/30` 수정 · `data/raw/` 변경 · 네트워크 · git commit·push.

---

- **2026-08-05 08:36 KST | §13-6 커버리지 C2 — **`Δ(M2b−P-ID)` 층화 실행 완료**(블록 L). 층 **13개** 전건 산출(formal 9 · descriptive 4), 산출 **전량 `_sealed/stratification_pid_result.json`**(sha256 `d38151f60b141ea2`). **모델학습 0 · 새 OOF 생성 0**(기존 consensus 재사용) · **개봉 0 · 성공판정 0 · 다중성 보정 0 · Δ·AP·CI·p·부호 공개 0**. 근거 = `docs/54` 커버리지 감사 C2(등록 §11 이 요구하는 두 대비 중 `Δ(M2b−P-ID)` 미수행) + 블록 I 로 `consensus_P-ID.npz` 확보 → **선행 조건 해소·정의 동결·추가 amendment 불요** | 지시서 = `docs/57_v3_pid_stratification_prompt_for_vscode.md` · 리포트 = `docs/57_v3_pid_stratification_report.md` | 동결 확인 = `ladder_freeze.json` sha16 `b885585aefbabb32` · SAP `manifest.json` sha16 `756d485feb4715e9` · 11모듈 sha 일치 · sealed guard **157종** 시작=종료 완전 일치 · `stratification_run.py`·`sap/` 11모듈·`docs/30` **무수정** | **확증 조회 = Y(값 미열람)** — consensus OOF 를 기계 판독해 새 추정을 생성했으므로 대장에 Y 로 기록하되 `open_sealed` **0건** · `access.log` 전건 `machine_read`/`human_exposure=false` · 공개 노출 **0**(부호 포함)

### 세부 (근거 추적)

26. **§13-6 커버리지 C2 — `Δ(M2b−P-ID)` 층화 실행 (블록 L — 실행·기록 전용, Holm family ② 산출물 확보)**:
   - **① 무엇을 했나**: 블록 H 가 `Δ(M2b−M1b)` 에 대해서만 수행한 §13-6 연속 유사도 층화를, **동일한 층·동일한 B·동일한 seed** 로 `Δ(M2b−P-ID)`(Holm family ②)에 대해 반복했다. 층 배정(`strata_assignment.csv`)·구조축 경계(`struct_bounds.json`)·identity(`identity_pairs.tsv`)·consensus OOF 는 **한 건도 재계산하지 않고** 기존 산출을 그대로 읽었다(`recomputed_nothing` 4항목). 신규 산출은 **신규 디렉터리** `experiments/runs/v3_stratification_pid/` 에만 썼고 기존 `_sealed/` 는 **일체 손대지 않았다**.
   - **② 대비 방향 검증(합성 데이터)**: 동결 연산자 `paired_scaffold_bootstrap`·`scaffold_signflip` 은 둘 다 `Δ = macroAP(둘째 인자) − macroAP(첫째 인자)` 로 정의된다. 첫째 = `P-ID`(기준 arm) · 둘째 = `M2b`(비교 arm) 로 배치해 `Δ_PID = macro AP(M2b) − macro AP(P-ID)` 를 만들었고, 이 방향이 규약과 일치하는지를 **합성 데이터만으로** 확인했다(확증 consensus 미사용): 비교 arm 이 우수하면 Δ>0 · 기준 arm 이 우수하면 Δ<0 · arm 교환 시 반대칭 · bootstrap/sign-flip 의 `delta_obs` 가 점추정과 일치. 나아가 **같은 합성 입력에서 블록 H 의 `run_unit` 과 Δ 가 완전히 일치**함을 확인해 arm 슬롯 매핑이 블록 H 와 동일함을 증명했다(`identical_to_block_H_run_unit_slot_mapping` = true).
   - **③ 행 정렬 동일성(두 consensus 가 서로 다른 런에서 생성됨)**: `consensus_M2b.npz`(블록 C, sha256 `8594592e2afae583`)와 `consensus_P-ID.npz`(블록 I, sha256 `9598da3498b1d3ce`)는 **서로 다른 런**의 산출이므로 행이 어긋나면 조용히 잘못된 대비가 나온다. 세 겹으로 확인했다 — (i) 두 npz 에 저장된 `cid` 배열이 **원소 단위로 동일**하고 `master_X.parquet` 정렬과도 동일, (ii) 두 러너가 **같은 동결 함수** `ladder_confirmatory.load_frozen()` 을 import 해 호출한다는 것을 **런타임 함수 객체 동일성**으로 확인(텍스트가 같은 별개 구현이 아니다) — 그 함수가 `master_X`/`master_Y` 정렬 일치를 assert 하고 `cid_order` 를 master_X 의 cid 열로 정의한다, (iii) 입력 `master_X.parquet` 의 sha256 이 블록 I 기록과 동일. 추가로 블록 I 는 자체 검증에서 기존 블록 C sealed npz 의 `cid` 배열이 master_X 정렬과 같음을 이미 assert 해 두었다.
   - **④ 동일 반복·동일 fold 기반**: 두 consensus 모두 반복 {1,2,3} = seed {201,202,203} · 5-fold · **동일 `folds.json`** 에서 산출됐음을 실측 sha256 로 확인했다(블록 I `rest_public.json` 기록값 3건 일치 · 블록 C `block_C_summary.json` 의 rep1 folds sha 일치 · 반복별 `config.json` 의 `split.seed`/`n_fold`/`dir` 일치 · fold 크기 3반복 동일).
   - **⑤ 층 정의는 블록 H 와 완전 동일**: `stratification_run.py` 를 **수정하지 않고 import 재사용**해 `load_common`·`estimation_units`·`assert_strata_accounting`·`build_strata_summary` 를 그대로 호출했다. `no-target` 245 제외 · 3반복 일치=stable · 불일치=`unstable_stratum`(drug_class 71 · seq_stratum 10 · struct_bin 204) · `eligible_pt=None`(370 PT 전열, 층 내부 재선정 금지) · undefined-AP 는 `sap/metrics.macro_ap` 동결 규칙에 위임 · 층 수 **13**. 층별 표본수는 블록 H `stratification_public.json` 및 블록 K `strata_accounting_public.json` 과 **전건 일치**함을 하드 assert 로 확인했다(축별 합 847).
   - **⑥ 재표집 seed 재사용(L-0-2 그대로)**: bootstrap `seed=6001` · sign-flip `seed=6002` · `B=10000` · `unit="scaffold_cluster"` · primary CI = `BCa`. **새 seed 를 뽑지 않았다** — 층·B·재표집 인덱스를 `M1b` 대비와 동일 조건으로 두어 두 대비의 차이가 재표집 난수에서 생기지 않게 하고, 사후 seed 선택의 여지를 원천 제거하기 위함이다. BCa 불능 층은 percentile 로 대체하지 않고 `not_estimable` 그대로 봉인했다(**1건**).
   - **⑦ 계측 후 실행**: 층마다 Δ 1회 비용을 **직접 실측**한 뒤 최대 표본 층 `B=100` 파일럿으로 비례상수를 보정해 총 wall 을 **7.64h**로 추정, 정지 임계 7.0일 미만 확인 후 본계산에 들어갔다. 실측 계산 wall **7.35h**(추정 대비 0.96배). 블록 H 는 층 비용을 `n_drugs` 선형으로 **가정**해 1.74배 과소추정했는데, 본 블록은 지배변수(층 내 양성≥1 PT 수)를 가정하지 않고 층마다 실측하는 방식으로 바꿨다. 파일럿 통계 산출은 **전량 폐기**(봉인 저장 0)하고 시간만 기록했다.
   - **⑧ 공개 범위 축소(L-0-3) — 부호도 비공개**: `M2b−P-ID` 는 Holm family ② 이므로 **부호 노출도 조각 개봉**이다. 공개 파일 `stratification_pid_public.json` 에는 층별 표본수·클러스터수·`n_eff_clusters`·formal/descriptive 라벨·축 위상 라벨·`B`·seed·소요시간·해시·게이트 PASS/FAIL 뿐이고, `macro_ap`·`delta`·`sign`·`ci_*`·`p_*`·`boot_*`·`null_*` 계열 키가 **부재**함을 방어 assert 로 강제했다(공개 **4파일** 전건 검출 **0**, `redaction_scan_public.json`). 키 검사에 더해 **부호 라벨 값**(`emit_sign` 출력)이 공개 파일에 없음을 **값 검사**로도 확인했다. §13-3·§13-5 에서 공개한 `M2b−M1b` 부호는 사전등록된 primary interim look 이었지만 ② 의 부호는 등록에 없는 추가 노출이므로 만들지 않는다.
   - **⑧-1 자체 검사코드 결함 2건(발견·수정 — 봉인 산출물 무관)**: 본계산 완주 **직후** 실행한 교차검사가 두 번 실패했다. 둘 다 **내가 새로 쓴 검사코드**의 문제이고 동결 정의·통계량·봉인 바이트와 무관하다. (i) `signcheck_public.json` 의 **검사 이름** 2개가 금지어에 걸렸다 — 값이 아니라 불리언 플래그 이름이었으나 L-5 는 해당 **키의 부재**를 요구하므로 assert 를 완화하지 않고 이름을 바꿔 재생성했다. (ii) `pilot_timing.json` 의 `signflip_B100`(= sign-flip **소요시간**)이 걸렸다 — 원인은 내가 `sign` 을 **통짜 접두사**로 쓴 것이다. 지시서 L-5 목록은 `macro_ap`·`delta`·`sign` 이 **정확한 키 이름**이고 별표가 붙은 `ci_*`·`p_*`·`boot_*`·`null_*` 만 접두사이므로 규칙을 그 문면대로 되돌리고, 값을 담는 파생 키를 막기 위해 `delta_`·`macro_ap`·`sign_` 접두사를 추가했으며, **부호 유출은 값 검사로 직접** 막도록 바꿨다(부호에 대해서는 이전보다 정확해졌다). 두 수정 사이에 **통계 재계산 0건 · 봉인 산출물 수정 0건**이며 봉인 sha256 은 본계산 종료 시점 값 그대로다.
   - **⑨ 게이트**: 배타 락(`role="runner"`) 획득·정상 해제 · **G-IDLE 게이트 A 를 우회하지 않았다**(임계 변경 0 — 시스템이 유휴가 될 때까지 러너 **진입만 미루는** 대기 런처를 쓰고 게이트 판정은 러너 안에서 그대로 수행) · 게이트 B 는 스테이지 및 층 단위 전후로 호출해 경쟁 계산 프로세스 0건 확인 · G0(`ladder_freeze` `b885585aefbabb32` · SAP manifest `756d485feb4715e9` · 11모듈 일치) · **sealed guard 157종**(`experiments/runs/**/_sealed/` 전 트리, `access.log` 제외) sha256 시작=종료 **완전 일치** · `open_sealed` **0건**.
   - **⑩ 한계(정직 고지)**: (i) 본 블록은 **추정만** 했고 판정은 하지 않았다 — 층별 산출은 다중성 보정 전 raw 이며 해석은 개봉·Holm/BH 이후에만 가능하다. (ii) 층 정의의 한계는 블록 H·K 와 동일하게 승계된다(canonicalization 미병합 · 서열축 상위 층 표본 부족 → descriptive · 구조축 경계는 문헌이 아니라 본 데이터 분위). (iii) 등록 §11 의 **unseen-target proportion 4변형은 여전히 미수행**이며 정의가 미동결이라 본 블록 범위 밖이다. (iv) 두 대비(`M2b−M1b`·`M2b−P-ID`)는 **동일 재표집 난수**를 공유하므로 서로 독립이 아니다 — 이는 의도된 설계(난수 차이 제거)이며 두 대비를 결합해 해석할 때 고려해야 한다.
   - **미실행**: 개봉(`open_sealed`) · 성공판정 함수 호출(`rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · 다중성 보정 · Δ·AP·CI·p·**부호**의 공개 기입 · `emit_sign` 호출 · 모델 학습 · 새 OOF 생성 · consensus·층 배정·구조축 경계·identity 재계산 · 기존 `_sealed/`·공개 산출물 수정 · `stratification_run.py` 수정 · A3~A6 unseen-target proportion 착수 · `RF_tuned`(⑥)·late-fusion(⑦)·GIN/RQ-int(⑧) · split·fold·seed 재추첨 · `ladder_freeze.json`·SAP 모듈·`sap/manifest.json`·`docs/30` 수정 · `data/raw/` 변경 · 네트워크 · git commit·push.

---

- **2026-08-05 09:45 KST | 공개 저장소의 **Δ 부호 노출 사실**을 이탈 로그에 명시적으로 편입 + 기록 전용 스크립트 계열의 공개 제외 규칙 추가(블록 J′) — 본 항목은 **계산 0 · 조회 0 · `_sealed/` 접근 0 · 성공판정 0 · 다중성 보정 0** 인 **기록 전용** 항목이다. 배경: 블록 J(`docs/52`) 점검에서 공개 원격 `adr-representation-benchmark` 의 브랜치 `chore/archive-kci-separation` 이 이미 `bdb65c8` 까지 푸시되어 있었고, 그 안에 §13-3·§13-5 의 Δ 부호가 파일로 들어 있음이 확인됐다. 이 노출은 **사고가 아니라 사전등록된 부호-only interim look 정책의 산출**이므로 회수·히스토리 재작성을 하지 않고 **사실로 고정 기록**한다 | 사용자 결정(2026-08-04) D1~D4 이행 | 지시서 = `docs/56_git_hygiene_resume_prompt_for_vscode.md` · 리포트 = `docs/56_git_hygiene_resume_report.md` | **확증 조회 = N** (`open_sealed` 0건 · `_sealed/` 읽기·쓰기 0 · `decision.py` 호출 0 · 새 추정 0 · 부호 **신규** 공개 0)

### 세부 (근거 추적)

27. **공개 저장소 Δ 부호 노출 사실의 명시적 기록 + 기록 전용 스크립트 공개 제외 (블록 J′ — 저장소 위생, 기록 전용)**:
   - **① 사실(경로·커밋으로만 지시 — 부호 값은 본 항목에 쓰지 않는다)**: `experiments/runs/v3_confirm_rep23/block_C_summary.json` 의 Δ 부호 **3건**이 커밋 `878b3ba`(2026-07-28 15:58 KST)로 **공개 원격에 푸시된 상태**다. 또한 `experiments/runs/v3_confirm_rep{1,2,3}_seed20{1,2,3}/metrics_public.json` 및 `experiments/runs/v3_consensus_rep123/metrics_public.json` 의 부호 **4건**이 커밋 `10687f4`(2026-07-28 16:10 KST)에 있으며 이 커밋은 **로컬 전용(미푸시)** 이다. 값 자체는 이미 `docs/45` §5 대장에 기록돼 있으므로 여기서는 **경로·커밋 해시로만** 가리킨다.
   - **② 성격 = 등록된 interim look 의 산출(사고 아님)**: 두 커밋에 담긴 부호는 전부 `Δ(M2b−M1b)` = Holm family ①(primary) 의 부호이며, §13-3(반복1)·§13-5(반복2·3·consensus)에서 **"공개는 Δ 부호 1개"** 로 사전 규정된 부호-only redaction 정책에 따라 산출된 것이다. 해당 4회 조회는 이미 `docs/45` §5 확증 조회 대장에 **4행으로 기록**돼 있다(2026-07-27 10:55·22:14 ×3). 즉 새로 발생한 노출이 아니라, **기존에 기록된 조회의 파일 상 흔적**이다.
   - **③ 방침 = 회수·히스토리 재작성 하지 않는다**: 이미 공개된 이상 재작성의 회수 효과는 제한적이고, 재작성 자체가 확증 산출물의 감사 추적을 훼손한다. 대신 논문 preregistration-deviation 표에 **"Δ(M2b−M1b) 부호는 등록된 interim look 으로 공개되었으며 공개 저장소 타임스탬프로 확인 가능"** 으로 기재한다. 검증 가능성은 오히려 이 공개 이력으로 **강화**된다(부호가 개봉 이전에 고정돼 있었음을 제3자가 시각으로 확인할 수 있다).
   - **④ 적용 범위의 경계 — §13-4 이후 산출물의 부호는 계속 비공개**: 재배치 null(블록 F, §13-4) · §13-6 층화(블록 H·L) · 확증 잔여 6모델 OOF(블록 I) 의 Δ·AP·CI·p **및 부호**는 **등록에 없는 추가 노출**이므로 전량 봉인 원칙이 그대로 유지된다(항목22 ③ · 항목26 ⑧). 본 항목은 그 원칙을 **완화하지 않으며**, 이미 발생한 family ① 부호 노출에만 한정된 사후 기록이다.
   - **⑤ 부수 조치(사용자 결정 D2)**: `record_block_*.py` · `record_cd_corrections.py` 계열은 `docs/33`·`docs/45` 원문을 문자열로 내장하므로 `docs/` 와 동일 범주로 보아 `.gitignore` 규칙을 **추가**하고, 이미 추적 중이던 2종은 `git rm --cached` 로 **추적만 해제**했다(작업트리 파일 보존, sha256 불변). ⚠️ **한계**: 이 조치는 **이미 푸시된 과거 공개분을 회수하지 못한다** — 앞으로의 갱신만 막는다. 해당 스크립트에 개인정보·봉인 수치·부호는 **0건**임이 블록 J 에서 확인됐다.
   - **⑥ author 메타데이터(D3·D4)**: 과거 커밋의 실명·hostname 메타데이터는 **재작성하지 않는다**(D4). 앞으로 만드는 커밋만 공개용 identity(`Yeonwoo Bae` / GitHub noreply 주소)로 정리했고, 저장소 **local** 설정으로만 적용했다(global 무변경).
   - **미실행**: `_sealed/` 열람(`open_sealed`) · 성공판정 함수 호출(`rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · 다중성 보정 · Δ·AP·CI·p 산출 · **부호 신규 산출·신규 공개**(`emit_sign` 0회) · 모델 학습 · 새 OOF 생성 · 기존 `_sealed/`·공개 산출물 수정 · 히스토리 재작성(`filter-repo`·`rebase`·`reset --hard`·`--force`) · **`git push`** · `.gitignore` 완화 · `ladder_freeze.json`·SAP 모듈·`sap/manifest.json`·`docs/30` 수정 · `data/raw/` 변경 · 네트워크(원격 **조회**만: `push --dry-run`·`ls-remote`).

---

- **2026-08-05 10:25 KST | 문서가 "공개"라고 명시한 설계 자산 **5종**이 `.gitignore` 화이트리스트에 막혀 저장소에 없던 상태를 해소 — `.gitignore` 에 **부정(`!`) 예외 추가만** 하고 로컬 커밋 2건 수행(블록 N). 본 항목은 **계산 0 · 모델학습 0 · 새 OOF 0 · `_sealed/` 접근 0 · 조회 0 · 성공판정 0 · 다중성 보정 0 · `emit_sign` 0 · `git push` 0** 인 **저장소 위생·기록 전용** 항목이다 | 사용자 승인(2026-08-05) — 블록 J′ `docs/56` §6-1 상신에 대한 결정 | 지시서 = `docs/59_public_assets_gitignore_prompt_for_vscode.md` · 리포트 = `docs/59_public_assets_gitignore_report.md` | **확증 조회 = N**

### 세부 (근거 추적)

28. **공개 약속 설계 자산의 추적 개시 (블록 N — 저장소 위생, 기록 전용)**:
   - **① 사실(불일치의 정체)**: `docs/47_v3_stratification_report.md` §3 "**공개**" 목록에 경로가 명시된 자산 중 **5종**이 `.gitignore` 화이트리스트(`data/processed/*` 26행 · `*.csv` 27행 · `*.tsv` 28행)에 걸려 **저장소에 들어가 있지 않았다** — `data/processed/target_mapping/_mmseqs/identity_pairs.tsv` · `identity_pairs.tsv.sha256` · `identity_manifest.json` · `experiments/runs/v3_stratification/strata_assignment.csv` · `power_samples.tsv`. 즉 **문서의 공개 약속과 저장소 상태가 어긋나 있었다.** 아직 푸시 전이라 실제 공개 불일치는 발생하지 않았고, 푸시·투고 이전에 해소했다. 이 불일치는 블록 J′(`docs/56` §5-1)가 `.gitignore` 완화 금지 조항 때문에 보수적으로 미커밋하고 결정사항으로 올린 건이다.
   - **② 근거 = 사용자 승인(2026-08-05)이며 설계·통계는 불변**: 부정 예외 추가는 **정책 완화**이므로 러너 재량이 아니라 사용자 승인에 근거한다. 바뀐 것은 **저장소 추적 범위뿐**이며 가설·contrast·Holm family·성공기준·`ladder_freeze.json`(`b885585aefbabb32`)·SAP `manifest.json`(`756d485feb4715e9`)·SAP 11모듈은 **전부 불변**이다. 층 정의·층 배정·추정치 어느 것도 재계산하지 않았고, 커밋 대상 파일의 **바이트를 한 글자도 고치지 않았다**(`experiments/runs/**`·`data/processed/**` 내용 수정 금지 조항 준수 — redaction 포함).
   - **③ 커밋 대상은 문서에서 도출했다(러너 임의 선정 아님)**: `docs/30`·`docs/45`·`docs/47`·`docs/48`·`docs/54`·`docs/57`(지시서/리포트 10파일)에서 경로 토큰을 전수 추출해 **55경로**를 얻고, 각각을 (문서의 공개 약속) × (저장소 상태)로 판정했다 — `tracked` **32** · `ignored_not_promised` **18** · `promised_but_ignored` **5** · `promised_but_missing` **0**. `promised_but_ignored` 5종이 착수 전 실측치와 **정확히 일치**했다. `_easy_search_raw.tsv`(11.7 MB 중간 산출물)는 어떤 문서도 공개로 기술하지 않음을 재확인해 **제외**했다(`docs/47` 등장 1회는 mmseqs 명령 재현용 코드블록 안).
   - **④ 규칙만으로 정확히 약속분만 열었다(`git add -f` 0회)**: `data/processed/*` 는 `target_mapping` **디렉터리 자체**를 제외하므로 git 이 그 안으로 내려가지 않아 파일 단위 `!` 만으로는 효과가 없다. 디렉터리를 부정한 뒤 `data/processed/target_mapping/**` 로 내용을 **전부 재-제외**하고, `_mmseqs/` 만 다시 부정한 뒤 `_mmseqs/*` 로 재-제외하고, 약속된 3파일만 정확히 부정했다. 역검증 — 작업트리 전체에서 **새로 열린 파일 = 정확히 5개**(초과 0 · 누락 0), `target_mapping` 하위 **12,236파일 중 12,233 무시**(캐시 9,334항목·ProtBERT 임베딩·`.fasta` 3종·`_easy_search_raw.tsv`·`tmp*` 전부 무시 유지). `.gitignore` 는 **추가 14줄뿐**이고 기존 80줄은 **바이트 단위 접두사 동일**(수정·삭제 0).
   - **⑤ 유출 스캔(블록 J′ 기준)**: 5파일 전건 — PII **0**(학번·성명·지도교수명·핸들·이메일 정규식·hostname) · 봉인 수치 키 **0**(`p_emp`·`T_obs`·`T_b`·`macro_ap`·`ci_bca`·`ci_percentile`·`p_two_sided`·`delta`) · **부호 값 0**(키 이름이 아니라 `"positive"`/`"negative"`/`"zero"` **값**으로 판정) · 10 MB 초과 **0**. `identity_pairs.tsv`(4.43 MB, sha256 `7a47e495…`)·`strata_assignment.csv`(sha256 `8247f431…`)는 `docs/47` 기록 해시와 **일치** → 리포트가 기술한 바로 그 바이트다. `identity_pairs.tsv` 4.43 MB 는 **영구적 저장소 증가**(압축 후 약 1.24 MB)임을 명시한다.
   - **⑥ `<HOME>` 절대경로 4건(수정하지 않음)**: `identity_manifest.json` 의 `command` 필드에 재현용 mmseqs 명령 전문이 그대로 들어 있어 입력 fasta 2회·raw 출력 1회·tmp 디렉터리 1회로 **총 4건** 나타난다(mmseqs 바이너리 경로는 `/opt/homebrew/...` 로 해당 없음). 블록 J′ §4-4 가 정리한 범주와 동일하고 원격 `bdb65c8` 에 이미 같은 계열 문자열이 공개돼 있으며, `data/processed/**` 내용 수정이 금지돼 redaction 이 불가능하다. **결정사항으로 유지 상신**(러너 로그의 경로 정책).
   - **⑦ 커밋 2건 · 푸시 0**: `7c86e6b`(`.gitignore` 단독, 1파일 +14/−0) · `566f487`(자산 5파일 추가, raw 4,681,143 B). 각 커밋 직후 `git show --name-status` 로 금지경로(`_sealed/`·`experiments/provenance/`·`docs/**`·`paper/`·`archive/`·`backup/`·`.claude/`·`data/raw/`·`*.hwp*`·`AGENTS.md`·`CLAUDE.md`·`record_block_*`) 혼입 **0/0** 확인. author 는 블록 J′ 가 설정한 저장소 **local** identity 그대로이며 **global 은 여전히 unset**. **`git push` 0회 — 원격 `chore/archive-kci-separation` tip 은 `bdb65c8` 그대로다.** 따라서 본 조치로 **새로 공개된 것은 아직 없다**(공개 여부는 별도 푸시 결정 사항, `docs/56` §6-4).
   - **⑧ 회색지대 2건은 커밋하지 않았다(§6 상신)**: (i) `experiments/runs/v3_stratification/unstable_cases.csv` — `docs/47` §3 공개 목록에 없고 `docs/54` 는 "신규 4파일"로만 기술해 **공개 라벨이 없다**. (ii) `data/processed/splits/confirmatory/rep{1,2,3}_seed{201,202,203}/folds.json`·`fold_membership.csv` — `docs/30` §분할 규격이 "분할 알고리즘·모든 split 파일 공개"라고 **총론으로** 약속하나 경로 단위 공개 목록에는 없다. 판정이 갈리므로 지시서 N-1 규정대로 **손대지 않고 결정사항으로 올린다**.
   - **미실행**: `_sealed/` 접근·열람(`open_sealed`) · 성공판정 함수 호출(`rq*_decision`·`holm`·`bh_fdr`·`tost_equivalence`) · 다중성 보정 · Δ·AP·CI·p 산출 · 부호 산출·공개(`emit_sign` 0회) · 모델 학습 · 새 OOF 생성 · 재계산 일체 · 커밋 대상 파일 내용 수정(redaction 포함) · `.gitignore` 기존 줄 수정·삭제 · `git add -A`·`git add -f` · **`git push`** · 히스토리 재작성 · global git config 변경 · `ladder_freeze.json`·SAP 모듈·`sap/manifest.json`·`docs/30` 수정 · `data/raw/` 변경 · 네트워크.

---

- **2026-08-05 16:51 KST | GIN training seed·대표 outer unit ID 사전 확정(등록문 미지정 자유도 값 지정) | 등록 §6·§13이 값을 지정하지 않은 항목을 GIN 착수 전·확증 결과 미조회 상태에서 결과-독립 규칙으로 확정 | N (확증 split OOF 미조회)**

### 세부 (근거 추적)

29. **GIN training seed·대표 outer unit ID 사전 확정 (블록 Q — 기입 전용)**:

> **(1) 범위와 시점**
> 본 보완은 확증 결과가 봉인되어 있고 GIN 학습이 시작되지 않은 2026-08-05에, 기존 등록문에서 값이 지정되지 않았던
> 대표 outer unit 및 training seed ID만을 확정하기 위해 작성한다. Outer unit은 반드시
> `(split_seed, zero-based fold_index)` 쌍으로 식별한다. 각 split seed `s ∈ {201, 202, 203}`에 대하여
> 줄바꿈 없는 ASCII 십진 문자열 `s`의 SHA-256 digest를 unsigned 256-bit 정수로 해석하고 그 값을 5로 나눈
> 나머지를 fold index로 정하였다. 이에 따라 안정성 분석의 세 unit은 `(201, f4)`, `(202, f1)`, `(203, f0)`으로
> 고정한다. 이 규칙은 fold별 약물 수, scaffold-group 수, 라벨별 성능 및 모델 결과를 입력으로 사용하지 않는다.
> 규칙은 fold 구성표를 확인한 후 확정되었으나, 어떤 GIN 학습·예측·성능 결과도 확인하기 전에 고정되었다.
> 이 해시 규칙 외의 대안(다른 해시 함수·문자열 인코딩·모듈러)은 계산·비교한 사실이 없다.

> **(2) Seed**
> GIN training seed의 사전 순서 목록은 선행 v2 관행을 계승하여 `(42, 1, 2, 3, 4)`로 고정한다. 이 목록은 본 확정
> 이전부터 `v2_GNN/src/robustness.py`와 `v3_Multimodal/src/train_ladder.py`에 존재하던 순서다. 확증 GIN에는 이
> 목록의 앞 3개인 `(42, 1, 2)`를 모든 15 outer unit에 적용하고, 기존 등록대로 seed별 완전 OOF 예측에서 각각
> macro AP 및 Δ를 산출한 뒤 세 Δ를 평균한다(metric-then-average). 기술적 안정성 분석에는 위 세 대표 unit에서
> 전체 5개 seed `(42, 1, 2, 3, 4)`를 적용한다. `train_seed=42`는 GIN 학습 난수의 ID이며 RF의 `random_state=42`
> 또는 개발용 `split_seed=42`와는 별개의 매개변수이다.

> **(3) 안정성 분석의 대상·지표·분해**
> 3×5 안정성 분석은 등록 §13의 "동일 세트" 문면대로 GIN 7모델(M0, M1, M1b, M2b, P-ID, P-FAM, C-CAP) 전부에
> 적용하며, 등록된 분해 보고의 primary는 Δ(M2b − M1b) 한 쌍으로 하고 나머지 모델의 cell 값은 보조표로 제시한다.
> 각 outer unit과 training seed 조합에서 대비 대상 두 모델을 동일 seed로 짝지어 실행하고, 해당 held-out fold에서
> `Δ_ij = macroAP_ij(M2b) − macroAP_ij(M1b)`를 계산한다. 이 fold 단위 평가는 확증 estimand(전체 1,092 약물의
> complete OOF)와 평가 단위가 다르며, 확증 추론을 대체하지 않는다. macro AP는 **기존 동결 규정(사전등록 §7)을
> 그대로 따른다** — 적격 PT 집합은 전체 평가셋에서 고정된 370개이며, 해당 cell 표본 내 양성이 0인 PT는 AP가
> 미정의이므로 **macro 평균에서 제외**한다(가변 분모). AP를 0으로 대치하는 방식은 채택하지 않으며, cell별로 실제
> 평균에 사용된 PT 수와 제외된 PT 수를 함께 보고한다. 15개 Δ는 outer-unit 제곱합, training-seed 제곱합 및 잔차
> 제곱합으로 기술적으로 분해하고, 각 제곱합의 전체 제곱합 대비 비율과 outer-unit별 seed 평균·표준편차·범위,
> 그리고 15개 cell 값 전부를 보고한다. 잔차는 unit×seed 상호작용과 분리되지 않은 backend 비결정성을 포함한다.
> 이 분석에서는 모집단 분산성분, ICC, 유의성검정 또는 확증적 신뢰구간을 해석하지 않는다.

> **(4) 실행 규약**
> 확증 GIN 15 unit × 3 seed를 전량 완주·봉인한 뒤에 대표 3 unit의 4·5번째 seed를 추가한다. 각 실행 전에 Python,
> NumPy, PyTorch CPU/MPS, DataLoader generator·worker 및 모델 초기화에 동일한 training seed를 명시적으로
> 재설정하며, seed는 가중치 초기화, dropout, minibatch 순서 및 사용되는 모든 stochastic sampler를 제어한다.
> 소프트웨어 버전, 하드웨어, MPS 설정, deterministic-algorithm 설정 및 실행 순서를 고정·기록한다. 사전 정의된
> hard technical failure만 동일 seed와 동일 설정으로 1회 재시도하며, seed 교체나 결과 기반 재학습은 허용하지
> 않고 모든 실패와 재시도를 기록한다. 안정성 분석의 결과는 주 결과, 가설 판정, 모델·하이퍼파라미터·seed 선택
> 또는 집계방식 변경에 사용하지 않으며, 산출물은 확증 산출 경로와 분리된 디렉터리에 기록한다. **본 항목은
> outer-train 내부 validation 설계(분할 단위·비율, monitor, patience, min/max epoch, best checkpoint tie-break)를
> 확정하지 않는다. 해당 항목과 RQ-int 미결 U1~U7, SAP 1.2 재동결은 여전히 미해결이며 GIN 착수는 계속 차단된다.**

### English resolution

> Before any GIN training or access to sealed performance results, we fixed the diagnostic outer units as
> `(split_seed, zero-based fold_index) = (201,4), (202,1), and (203,0)`, obtained by mapping the SHA-256 integer of
> each split seed's newline-free decimal string modulo five; the rule uses no fold size, scaffold-group count, or
> model output as input, and no alternative hash rule was evaluated. The pre-existing ordered training-seed list
> `(42,1,2,3,4)` — already present in the v2 and v3 training code before this decision — will be used for the 3×5
> technical diagnostic across all seven GIN ladder models, with its fixed prefix `(42,1,2)` used for the confirmatory
> full-OOF GIN analysis under metric-then-average aggregation. Fold-level macro AP follows the frozen §7 rule
> unchanged: over the fixed eligible set of 370 preferred terms, PTs with no in-sample positives are excluded from
> the macro mean rather than assigned an average precision of zero. The diagnostic is descriptive only, is reported
> as a two-way sum-of-squares decomposition without variance components, ICC, or significance tests, and cannot
> affect model selection or hypothesis adjudication.

> 근거 = `docs/64_gin_seed_fold_triage.md` §5 · 지시서 = `docs/65_gin_seed_fold_freeze_prompt_for_vscode.md` · 신규 동결 파일 = `v3_Multimodal/config/gin_seed_freeze.json`(sha256 `10828447c6d33118`, `ladder_freeze.json` sha16 `b885585aefbabb32` **무수정** · SAP `manifest.json` sha16 `756d485feb4715e9` · 11모듈 sha 일치). **미실행**: GIN 학습·추론 · 통계 계산 · 새 추정 · Δ·부호 산출(`emit_sign` 0) · `_sealed/` 접근(`open_sealed` 0) · 성공판정·다중성 보정 · 네트워크 · git commit.

---

- **2026-08-05 19:04 KST | GIN inner-validation 설계 사전 확정(등록문 미지정 자유도 값 지정) | 등록 §5·§6이 값을 지정하지 않은 inner-valid 단위·비율·무작위원·블록 fit 모집단을 GIN 착수 전·확증 결과 미조회 상태에서 결과-독립 규칙으로 확정 | N (확증 split OOF 미조회)**

### 세부 (근거 추적)

30. **GIN inner-validation 설계 사전 확정 (블록 R — 기입 전용)**:

> **(1) 범위 — 새로 정하지 않은 것**
> 본 보완은 `gin_seed_freeze.json`의 미규정 목록 중 inner-validation 설계 항목만을 해소한다. 착수 전 점검에서
> 미규정으로 분류됐던 항목 가운데 max epoch(200), patience(30), monitor 지표, best checkpoint 갱신 조건과
> 그로부터 자동으로 따라오는 tie-break은 실제로는 이미 동결돼 있었다 —
> `v3_Multimodal/src/train_ladder.py`의 A_wd 레시피 상수와 학습 루프가 그 값을 정하고 있고, 갱신 조건이
> 엄격 부등호이므로 동점 시에는 이른 epoch이 선택된다. monitor는 표본 내 양성이 1개 이상인 PT만 평균하는
> valid macro AP이며, 적격 PT 집합이 370 전열이므로 동결 §7의 macro AP 규칙과 정의가 일치한다. min epoch
> 하한은 존재하지 않으며, 하한을 새로 도입하면 A_wd 레시피 변경에 해당하므로 도입하지 않는다. 따라서 본
> 항목이 새로 확정하는 것은 아래 (2)~(3)에 한정된다.

> **(2) inner-valid 구성**
> inner-valid는 outer-train 안에서만 떼며 outer test fold는 어떤 방식으로도 사용하지 않는다. 분할 단위는
> Bemis–Murcko scaffold group이고, 파싱 불가·무고리 분자에 부여되는 빈 문자열 scaffold는 등록된 outer split과
> 동일하게 하나의 정당한 그룹으로 센다. 비율은 outer-train의 1/9로 고정한다. 이는 새로 만든 수치가 아니라
> 개발 split 873/109/110의 비-test 풀 대비 valid 비율(109/982 = 0.11100)을 계승한 값으로, 1/9 = 0.11111과
> 소수 셋째 자리까지 일치한다. 무작위원은 `inner_seed = 1000 × split_seed + fold_index`로 정하며 training
> seed와 무관하다. 분할 절차는 새 알고리즘을 만들지 않고 등록 §6의 outer split 알고리즘을 두 개의 불균등
> bucket으로 일반화해 그대로 재사용한다 — 그룹을 (−크기, 첫 cid 문자열)로 사전 정렬하고
> `random.Random(inner_seed)`로 셔플한 뒤, 누적합이 목표를 넘지 않는 첫 bucket에 배정하고 모두 초과하면
> 마지막 bucket에 배정한다. 하나의 outer unit `(split_seed, fold_index)`마다 inner split은 하나이며, GIN 7모델과
> 5개 training seed 전부가 그것을 공유한다. 따라서 같은 cell의 M1b와 M2b는 동일한 학습·검증 조건을 공유하고,
> training seed 축은 순수한 학습 무작위성만을 나타낸다. 착수 전 검증에서 15 outer unit 전부 inner-valid 97
> 약물, 두 bucket 간 scaffold group 교차 0, inner-train에서 양성이 0인 적격 PT 0개(등록 §6 rare-PT 제약 충족)를
> 확인했다. 후보 비율 10%·15%·20%도 같은 제약을 모두 통과했으므로 제약이 아니라 위 계승 논증으로 1/9을
> 택했음을 밝힌다. 이 검사는 라벨과 분할 구성만 사용했고 어떤 GIN 학습·예측·성능 결과도 확인하기 전에
> 수행되었다.

> **(3) 피처 블록 적합 모집단과 RF 비대칭**
> StandardScaler, PCA-64, vocabulary 등 fold별 피처 블록은 inner-valid 행을 포함한 **outer-train 전체**에서
> 적합한다. 이는 등록 §5가 "split별 scaler·PCA·집계통계·모델선택은 해당 fold의 train/valid에서만 적합"으로
> 규정한 범위이며, 확증 RF 하네스가 outer-train 전체에서 블록을 적합하는 것과 동일한 처리다. 그 결과 같은
> 사다리 단계의 입력 표현은 두 model family 사이에서 동일하게 유지되고, outer test 누수는 없다. 다만 RF는
> 결정적이어서 inner-valid가 불요한 반면 GIN은 동결된 A_wd 레시피가 early stopping을 요구하므로, 실제 gradient
> 갱신이 보는 약물 수는 RF가 873~874, GIN이 776~777로 11.1% 다르다. 이 비대칭은 수용하고 명시하며,
> inner-valid로 epoch을 고른 뒤 outer-train 전체로 재학습해 동등화하는 방식은 채택하지 않는다. 재학습안은 GIN
> 학습량을 약 두 배로 늘리고, 다른 표본 크기에서 선택한 epoch이 그대로 전이된다는 새 가정을 요구하며,
> 재학습 구간에는 early stopping 안전장치가 없기 때문이다.

> **(4) 한계와 잔여 미결**
> RQ-int는 Δ_RF와 Δ_GIN의 차이를 묻는데 두 family의 학습 표본 수가 11.1% 다르다. 표본이 적어 GIN이 서열
> 정보를 활용할 여지가 눌린다면 Δ_GIN이 축소될 수 있고 이는 family 차이로 오독될 수 있다. 이 비대칭은
> 설계상 불가피하며 결과를 보기 전에 확정·공개했다. 또한 outer unit `(202, f2)`의 inner-valid는 97 약물이
> scaffold group 15개에만 걸쳐 있고 그중 77 약물이 빈 문자열 pseudo-group에서 오므로, 이 unit의 early stopping
> monitor는 사실상 15개 클러스터에 근거한다. 이는 등록 split이 그 pseudo-group을 하나의 그룹으로 세는 규약을
> 내부에도 동일 적용한 직접적 귀결이므로 규칙을 바꾸지 않고 한계로 명시한다. 거대 그룹을 검증 bucket에서
> 배제하는 규칙은 관측 후 조정에 해당해 채택하지 않는다. **본 항목은 RQ-int 미결 U1~U7과 SAP 1.2 재동결을
> 해소하지 않으며 GIN 착수는 계속 차단된다.**

### English resolution

> Before any GIN training or access to sealed performance results, we fixed the inner-validation design that the
> registration left unvalued. Within each outer training fold the validation set is drawn at the Bemis-Murcko
> scaffold-group level and holds one ninth of the outer-training rows, a proportion inherited from the development
> split (109/982 = 0.11100 against 1/9 = 0.11111) rather than newly chosen; it is drawn by reusing the registered
> outer-split algorithm with two unequal buckets under the seed 1000 x split_seed + fold_index, so the split is
> independent of the training seed and is shared by all seven GIN ladder models and all five training seeds. Fold
> feature blocks are fitted on the entire outer-training fold, inner-validation rows included, exactly as the
> confirmatory RF harness does, so the input representation is identical across families and no outer-test
> information is used. Because RF is deterministic while the frozen recipe requires early stopping for GIN, the two
> families train on sample sizes differing by 11.1%; we accept and disclose this asymmetry rather than equalizing it
> by refitting, and we report it as a limitation of the RQ-int comparison. Maximum epochs, patience, the monitored
> metric, the checkpoint rule and its earliest-epoch tie-break were already frozen in the recipe and are restated,
> not chosen, here.

> 근거 = `docs/66_gin_inner_validation_design.md` §2·§3 · 지시서 = `docs/67_gin_inner_valid_freeze_prompt_for_vscode.md` · 신규 동결 파일 = `v3_Multimodal/config/gin_inner_valid_freeze.json`(sha256 `038599c3e1576022`) · 재현 검증 = `experiments/runs/v3_gin_inner_valid_freeze/inner_split_check.json`(15 outer unit 전건 `docs/66` §4 일치, 입력 = `fold_membership.csv`+`master_Y.parquet` 뿐) · 선행 동결 `ladder_freeze.json` sha16 `b885585aefbabb32` **무수정** · `gin_seed_freeze.json` sha16 `10828447c6d33118` **무수정** · SAP `manifest.json` sha16 `756d485feb4715e9` · 11모듈 sha 일치. **러너 정정 2건(지시서 §3 JSON 대비)** — ① `inner_split.algorithm` 의 사전정렬 키 `str(first cid)` → `str(first row index)`(동결 master 테이블 cid 오름차순 위치, outer-train 재색인 없음): `assign_folds` 의 `groups` 가 scaffold→**행 인덱스** 리스트라 `groups[g][0]` 은 cid 가 아니며, cid 로 구현하면 셔플 초기순서가 달라져 docs/66 §4 표를 재현하지 못한다. 교정 해석은 동결 outer split 을 3반복 전건 0행 불일치로 재현해 검증했다. ② `already_frozen_not_newly_chosen.source` 의 `train_ladder.py:61-63` → `61-67`(레시피 상수 줄 실측 61~67; `236-248` 은 실측 일치). 둘 다 **설계값 변경이 아니라 재현 불가·불일치 문구의 교정**이며, 국문·영문 문안은 지시서 지정대로 무수정 삽입했다. 국문 (2) 문단의 '(−크기, 첫 cid 문자열)' 표현에도 같은 정정이 적용된다. **미실행**: GIN 학습·추론 · 모델 코드 실행 · 새 추정 · Δ·부호 산출(`emit_sign` 0) · `_sealed/` 접근(`open_sealed` 0) · 성공판정·다중성 보정 · 네트워크 · git commit.

---

- **2026-08-06 09:33 KST | post-interim 확정 v1.0 — Holm ⑥·⑦ 조작적 정의, λ 절차, 연속축 A3·A4·A6 정의, early stopping 세부, 명칭 정정, 저장소 방침 | 등록문이 대비만 정하고 그 아래를 규정하지 않은 항목을 해당 계산 착수 전·확증 결과 미조회 상태에서 등록 문면·기존 동결물로부터 도출해 확정 | N (확증 split OOF 미조회)**

### 세부 (근거 추적)

31. **post-interim 확정 v1.0 (블록 S — 기입 전용)**:

> **(1) 성격과 시점**
> 본 확정은 확증 결과가 봉인돼 있고 Holm ⑥·⑦ 계산과 연속축 A3·A4·A6 층화를 아직 착수하지 않은
> 2026-08-05에, 사전등록서가 대비만 정하고 그 아래 수준을 규정하지 않은 항목들을 한 건으로 묶어
> 확정한 것이다. 각 항목은 임의 선택이 아니라 등록 문면 또는 이미 동결된 산출물로부터 도출했으며,
> 도출 규칙과 기각한 대안을 함께 기록한다. Δ의 부호 4건이 이미 알려진 뒤의 결정이므로 이 전체를
> 날짜가 찍힌 post-interim amendment로 표기한다. 지도교수께는 `docs/70`으로 통보하고 이의 제기
> 기회를 열어 두었으며, 이의가 있는 항목은 되돌린다.

> **(2) Holm ⑥ — `M2b − RF_tuned`의 baseline**
> baseline은 Morgan 지문 반경 3, 2048비트 단독이며 표적 유래 블록을 포함하지 않고, 하이퍼파라미터는
> 확증 split이 생성되기 이전에 공정튜닝 절차가 이미 선택해 둔 구성을 축자 그대로 쓴다. 재튜닝은 하지
> 않는다. 도출 근거는 등록 §4가 "Morgan RF·tuned RF"를 쌍으로 열거하고 ⑤가 이미 디폴트 Morgan RF를
> 쓰므로 ⑥은 그 튜닝 대응물이어야 한다는 것이며, 사다리 동결 파일이 공정튜닝 RF를 사다리에서
> 사용하지 않는다고 명시해 두어 그것이 처음부터 별도 baseline으로 취급돼 있었다는 사실이 이를
> 뒷받침한다. 기존 반경 2 블록에 튜닝 하이퍼파라미터만 얹는 대안은 그런 구성이 존재한 적이 없고
> 지금 새로 조립하는 것이 되어 연구자 자유도가 오히려 커지므로 기각한다. 착수 전에 지문 생성기
> 버전, chirality 설정, count 대 bit 표현, 비트 수, 반경을 함께 동결한다. 이 비교는 반경만 또는
> 하이퍼파라미터만의 효과를 분리하는 ablation이 아니라 개발단계에서 선택된 강한 구조전용 baseline
> 전체와의 benchmark 비교이며, 그렇게 명시해 보고한다.

> **(3) Holm ⑦ — 기준 RF, `p_seq`, 그리고 λ**
> 기준 RF는 `p_RF = M0`으로 한다. 등록 §14 표가 "RF+seq > RF는 서열이 fingerprint와 비중복 정보를
> 제공함을 뜻한다"고 적어 문면이 일의적이며, M0의 확증 산출물이 이미 있어 추가 학습이 없다.
> `p_seq`는 표적 서열 블록 단독을 primary로 하고 표적 수·매핑 여부를 더한 구성을 sensitivity로
> 병기하며, sensitivity 결과는 ⑦의 성공판정이나 primary 대체에 사용하지 않는다. 표적이 매핑되지
> 않은 245개 약물이 0 벡터가 되는데 이 0은 결측의 명시적 지시자가 아니라는 점을 한계로 기록한다.
> `p_seq`의 학습기는 동결된 확증 RF 하네스를 동일한 하이퍼파라미터 그대로 서열 블록에만 적용한다.
> ⑦이 등록상 RF 상보성 가설이고 기준선도 RF이므로 학습기를 고정하고 피처만 바꾸는 것이 대비가
> 주장하는 바와 정확히 일치하며, 이렇게 하면 새 학습기도 새 하이퍼파라미터도 도입하지 않는다.
> ridge, MLP 등 대안은 모두 부호가 알려진 뒤에 새 하이퍼파라미터를 고르게 만들므로 기각한다.
> λ는 GIN inner-validation과 동일한 1/9 scaffold group 분할과 동일한 무작위원을 공유해 선택하고,
> 선택 지표는 검증셋 macro AP이며 동결된 미정의-AP 제외 규칙을 그대로 적용한다. 격자는 0.00부터
> 1.00까지 0.05 간격이고, λ는 outer unit별로 하나씩 고르며, 동점이면 0.5에 가까운 λ를, 그래도
> 동점이면 작은 λ를 택한다. λ를 고른 뒤 두 base learner를 outer training 전체로 재적합한다.
> 재적합하지 않으면 `p_RF`가 대비 상대인 M0보다 적은 표본으로 학습한 모델이 되어 대비가 서열의
> 비중복 정보가 아니라 학습표본 크기 차이를 섞기 때문이며, 재적합된 `p_RF`의 예측이 해당 fold의
> 기존 봉인 M0 OOF와 바이트 단위로 동일함을 assert로 강제한다. λ=0.5 고정판은 항상 병기하며 선택
> λ와 교체하지 않는다. 내부 다중 CV는 λ 추정이 더 안정적이나 새 분할 규칙과 새 피처 적합 모집단을
> 추가하게 되어 기각한다.

> **(4) 등록 §11 세 번째 연속축 중 A3·A4·A6**
> 보고 형식은 이미 수행·봉인된 앞 두 연속축과 동일하게 사전 고정 구간 층화로 한다. 세 번째 축만
> 다른 형식을 쓰면 축 사이 비교가 불가능해지므로 선례를 계승한다. A3은 미관찰 표적 수를 전체 표적
> 수로 나눈 비율이며 구간은 0, 0 초과 0.5 미만, 0.5 이상 1 미만, 1이다. A4는 pChEMBL 점수 가중
> 비율로 부르며 결합친화도로 가중하되 pChEMBL이 결측인 pair는 분자와 분모 양쪽에서 제외하고
> 약물별 결측 pair 수를 함께 기록하며, 모든 pair가 결측인 약물은 별도 층으로 둔다. A6은 결합친화도
> 중앙값이 최대인 주표적이 미관찰이면 1로 하고 동점은 UniProt 접근번호 사전순 최소로 깬다. 표적이
> 하나도 매핑되지 않은 245개 약물은 분모가 0이므로 사전 정의된 제외 집합으로 두고 0 구간과 합치지
> 않으며 그 수를 함께 보고한다. 커버리지의 분모를 명시하면 pair 기준으로는 12,613 중 12,514이고
> 약물 기준으로는 매핑된 847개 중 16개가 pChEMBL을 전혀 갖지 않는다. 재표집 seed, 반복 수, 단위,
> 신뢰구간 방법은 앞선 층화 블록의 것을 그대로 재사용하며 새 seed를 추첨하지 않는다. 각 축에서
> 등록대로 두 대비를 모두 산출한다. A5는 작용기전 표적의 약물 귀속을 복원할 수 없어 1회 재조회가
> 필요하므로 본 항목에서 확정하지 않으며, 승인되지 않으면 임의 대리지표로 대체하지 않고 추정
> 불가로 남긴다.

> **(5) 부수 확정과 잔여**
> GIN early stopping의 최소 개선폭은 0이다. 체크포인트 갱신이 엄격 부등호이므로 어떤 크기의 개선도
> 반영되고 동점은 갱신하지 않아 이른 epoch이 선택된다. 검증 지표가 미정의인 epoch은 개선 없음으로
> 처리하고, 모든 epoch에서 미정의이면 hard technical failure로 기록해 동일 seed·동일 설정으로 1회
> 재시도하며 조용히 건너뛰지 않는다. 실측상 15개 내부 검증셋 모두 양성을 가진 PT가 293개에서
> 323개 사이여서 이 상황은 발생하지 않는다. 명칭 세 건을 정정한다 — "대표 fold"는 "사전 지정된
> 진단 unit"으로, Holm ⑥은 ablation이 아니라 benchmark 비교로, A4의 가중은 "친화도 질량"이 아니라
> "pChEMBL 점수 가중 비율"로 부른다. 공개 저장소는 성능 산출물의 추가 push를 중지하고, 이미 공개된
> 것은 삭제하거나 이력을 고쳐 쓰지 않으며 공개 시점과 범위만 기록하고, 공개는 새 부호를 동반하지
> 않는 범위에서만 한다. 개봉 전에 봉인 완전성 점검과 부호 인지 기록표를 갖추기로 하고 그 규격을
> 여기에 명시하되 구현은 후속 블록으로 미룬다. **본 항목은 A5 재조회 승인, 개봉 승인자 지정,
> RQ-int 미결 U1~U7, SAP 1.2 재동결을 해소하지 않으며, GIN 학습과 Holm ⑥·⑦ 계산은 계속 차단된다.**

### English resolution

> Before starting the Holm 6 and Holm 7 computations, before the third continuous stratification axis, and
> without access to any sealed performance value, we froze the operational definitions that the registration
> had left below the level of the contrast. Holm 6 uses the structure-only Morgan radius-3 baseline whose
> hyperparameters were already selected by the pre-confirmatory fair-tuning procedure, taken verbatim, and is
> reported as a benchmark comparison rather than an ablation. Holm 7 uses M0 as the fingerprint baseline and a
> sequence-only feature set carried by the frozen confirmatory RF harness with unchanged hyperparameters, so
> that no new learner and no new hyperparameter enter after the signs became known; lambda is selected on the
> same one-ninth scaffold-group inner split already frozen for GIN, and both base learners are refitted on the
> full outer-training fold afterwards so that the fingerprint arm is byte-identical to the existing M0 out-of-fold
> predictions. The third continuous axis is reported as pre-fixed bins, matching the two axes already sealed,
> with drugs having no mapped target held out as a named excluded set rather than merged into the zero bin.
> Each definition is recorded with the rule that produced it and the alternative that was rejected.

> 근거 = `docs/69_advisor_consult_triage_20260805.md` · `docs/70_advisor_reply_draft_20260805.md` §1 · 지시서 = `docs/71_post_interim_freeze_v1_prompt_for_vscode.md` · 신규 파일 = `v3_Multimodal/config/post_interim_freeze_v1_0.json`(sha256 `502db732bd5e45cb`) · `v3_Multimodal/config/gin_inner_valid_freeze.status.json`(sha256 `bd329fefe613971f`) · 선행 동결 `ladder_freeze.json` sha16 `b885585aefbabb32` **무수정** · `gin_seed_freeze.json` sha16 `10828447c6d33118` **무수정** · `gin_inner_valid_freeze.json` sha16 `038599c3e1576022` **무수정** · SAP `manifest.json` sha16 `756d485feb4715e9` · 11모듈 sha 일치 · `HOLM_FAMILY` 7 라벨 실측(`sap/decision.py:44`, ⑥ `M2b-RF_tuned` · ⑦ `RFseq-RF` 포함). **러너 부기 3건** — ① 기입 시각은 실측값 그대로 쓴다: 확정 **도출**일은 `docs/69`·`docs/70` 의 **2026-08-05**(국문 (1) 문단 표기)이고 **기입**일은 **2026-08-06** 이다. 지시서 §4 헤더 템플릿의 날짜 자리에는 실제 기입 시각을 넣었으며 소급 기입은 하지 않았다. 국문·영문 문안은 지시서 지정대로 **바이트 그대로** 삽입했다(임의 수정 0). ② `gin_inner_valid_freeze.json` 의 지위는 대상 파일을 수정하지 않고 **사이드카** `gin_inner_valid_freeze.status.json` 으로 남겼다 — `status=frozen`(지시서 §3 지정) 이되 `delegated_by_advisor=false` 와 통보 위치를 함께 적어 **위임 범위 밖이었다는 사실을 숨기지 않는다**(`docs/69` §4 의 `provisional_pending_ratification` 안과는 지시서 §3 이 명시적으로 다르게 지정했다). ③ Holm ⑥ baseline 의 하이퍼파라미터는 `v1_RF/results_fairtune/best_config.yaml` 을 **판독만** 하여 축자 전재했고 지문 반경·비트 수가 `docs/70` §1-2 서술과 일치함을 게이트에서 확인했다. 같은 파일에 함께 저장된 **선택 지표값은 성능 수치이므로 동결 JSON·본 항목·리포트 어디에도 옮기지 않았다.** **미실행**: 모델 학습·추론(RF·GIN 무관) · 통계 계산 · 새 추정 · Δ·부호 산출(`emit_sign` 0) · `_sealed/` 접근(`open_sealed` 0) · 성공판정·다중성 보정 · A5 재조회 · Holm ⑥·⑦ 계산 · 연속축 A3·A4·A6 층화 · 네트워크 · git commit·push.

---

32. **판독확정(pre-look, 블록 O-0) — Holm ⑥ `M2b − RF_tuned` 착수 전 기입**:

> **(1) 성격 — 신규 확정이 아니라 실행수준 동결 1건**
> ⑥ 의 조작적 정의는 블록 S 가 이미 확정해 항목31 국문 (2) 와
> `v3_Multimodal/config/post_interim_freeze_v1_0.json` 의 `holm6_rf_tuned` 에 기입했고,
> 지도교수께 `docs/70` §1-2 로 통보해 이의 제기 기회를 열어 두었으며 2026-08-06 회신에서
> 이의가 제기되지 않았다(`docs/77`). 따라서 지시서 개정판 v2 는 같은 확정을 새 항목으로 다시
> 넣는 것을 폐지했다 — 대장에 중복 확정 기록을 만들지 않기 위해서다. 본 항목이 새로 확정하는
> 것은 확정본이 "착수 전에 함께 동결하라"고 남겨 둔 **지문 생성기 명세 다섯 항목뿐**이며,
> 그 값은 러너가 정한 것이 아니라 동결 `B0`(반경 2)를 만든 코드경로에서 그대로 읽어 온 것이다.
> 이 기입의 방어력은 **`B0_r3` 행렬을 한 번도 생성하기 전에, 확증 결과를 조회하지 않은 상태에서**
> 값을 고정했다는 사실에 있다.

> **(2) 지문 생성기 명세 실측 동결**
> `ladder_confirmatory.py` 의 `MorganBlock` 을 구문트리로 판독해 생성기 호출의 인자 집합이
> 반경과 비트 수 둘뿐임을 확인했고, 위치인자가 없어 다른 인자가 숨어 들어갈 여지가 없음을
> assert 로 고정했다. 그러므로 반경 3 구성은 동결 `B0` 와 **반경 하나만** 다르다. 실측값은
> RDKit 버전 2026.03.3, chirality 포함 여부 false
> (생성기 호출이 이 인자를 명시하지 않으므로 시그니처 기본값이 실사용값이다), 표현은 count 가
> 아닌 bit 벡터(지문 추출 호출이 count 계열이 아님을 판독), 비트 수 2048,
> 반경은 동결 `B0` 가 2 이고 본 블록이 3 이다. 구현은
> `MorganBlock` 을 **상속**해 동일 코드경로를 그대로 실행하되 반경 상수만 일시 치환하고 원복하는
> 방식이며, `ladder_confirmatory.py` 는 한 바이트도 수정하지 않는다.

> **(3) 판독확정 5건 — 확정본과 대조만(새 판단 0)**
> 비교 arm 의 피처는 반경 3 Morgan 지문 단독이고 표적 유래 블록을 넣지 않는다. 하이퍼파라미터는
> 공정튜닝 결과 파일에서 축자 인용하며 그 파일의 sha16 은 `f411602e9a46a34c` 로
> `docs/48` 기록값과 일치한다(선택 지표값은 성능 수치이므로 어디에도 전재하지 않는다). 결과-독립성은
> 그 선택이 확증 split 생성 이전, 개발 split 의 검증셋만으로 이뤄졌고 test 를 쓰지 않았다는 사실로
> 성립한다. 공개 범위는 형상·개수·차원·해시·소요시간·게이트 판정뿐이며 층별·모델별 지표와 대비량과
> 그 부호는 전량 비공개다. 실행순서 이탈은 항목22 의 A9 연장선이며, 목적은 개봉 전에 Holm family
> 전원을 채우는 것이고 가설·모델정의·대비·다중성 규칙·유의수준·성공기준은 불변이다.

> **(4) 문면 충돌 1건과 그 해석**
> 사다리 동결 파일의 RF 하이퍼파라미터 항목에는 공정튜닝 RF 를 쓰지 않는다는 주석이 달려 있다.
> 이는 **동결 사다리 8모델의 RF 하네스**에 튜닝 하이퍼를 주입하지 않는다는 뜻이며 같은 항목의
> 재튜닝 여부 필드가 거짓인 것과 짝을 이룬다. 등록 §4 가 별도 baseline 으로 열거한 ⑥ 자체를
> 금지하는 문면이 아니다. 그러므로 사다리 동결 파일은 한 바이트도 고치지 않고 **별도 동결 파일**을
> 신설한다.

> **(5) 착수 게이트 실측**
> 확정 내용·확정 기입·교수님 통보·교수님 무이의·차단 해제 다섯 경로를 실측해 전건 일치를 확인했고,
> 특히 차단 플래그가 거짓임을 확인했다. 선행 동결 4종과 SAP 매니페스트 및 11개
> 모듈 해시가 기대값과 일치하고, 다중성 family 는 소스 구문트리 판독으로 7 라벨이며 ⑥ 라벨이
> 포함돼 있다(import·실행 아님). 봉인 산출물 159종의 경로·해시 스냅샷을 착수 시점에 떴다.

> 근거 = `docs/60_v3_rf_tuned_prompt_for_vscode.md`(개정판 v2) · 확정본 = `docs/33` 항목31 국문 (2) · `v3_Multimodal/config/post_interim_freeze_v1_0.json`(sha256 `502db732bd5e45cb`) · 신규 동결 = `v3_Multimodal/config/rf_tuned_freeze.json`(sha256 `c1ef6406fbb48b7f`) · `ladder_freeze.json` sha16 `b885585aefbabb32` **무수정** · SAP `manifest.json` sha16 `756d485feb4715e9`(v1.1) · `HOLM_FAMILY` 7 라벨(`sap/decision.py:44`). **미실행**: RF 학습·추론 · 지문 행렬 생성 · Δ·지표·CI·p 산출 · `emit_sign` · `decision.py` 호출 · 개봉 · `_sealed/` 쓰기 · split·fold·seed 재추첨 · 네트워크 · git commit·push. 기입 시각 2026-08-06 14:21:48 KST.

---

33. **실행 기록(블록 O) — Holm ⑥ `M2b − RF_tuned` comparator arm 확증 OOF**:

> **(1) 무엇을 실행했고 무엇을 실행하지 않았나**
> 반복 셋(seed 201·202·203) × fold 다섯 = 15 model-fold 를 전건 완주해
> `RF_tuned` 의 확증 OOF 를 만들고 반복 셋의 예측을 동결 규칙대로 평균해 consensus 를 만들었다.
> 산출은 전량 봉인했고 신규 디렉터리에만 기록했다. **대비는 만들지 않았다** — `M2b` 와의 Δ, 그
> 크기, 신뢰구간, p 값, 그리고 부호 어느 것도 산출하지 않았다. ⑥ 은 다중성 family 의 구성원이므로
> 부호 하나의 노출도 조각 개봉이기 때문이다. 성공판정 함수와 다중성 보정 함수는 호출하지 않았고,
> family 라벨은 소스 구문트리 판독으로만 확인했다(import·실행 아님).

> **(2) 코드경로 동일성 — 새 러너가 기존 하네스와 같은 것을 계산하는가**
> 신규 러너로 동결 모델 `M0` 의 반복1 fold0 을 다시 계산해, 블록 I 가 봉인해 둔 같은 위치의 예측과
> dtype·형상·원시 바이트가 모두 일치함을 확인했다. 이것이 데이터 로딩·fold 배정·행 정렬·RF 하네스가
> 블록 I 와 동일하다는 증거다. 재계산본은 어디에도 저장하지 않고 폐기했으며 기존 봉인은 기계 판독만
> 했다. 불일치였다면 본계산에 착수하지 않고 중단하도록 걸어 두었다.

> **(3) `B0_r3` 정합**
> 형상은 약물 수 × 비트 수이고 dtype 은 동결 `B0` 와 같으며, SMILES 로부터 분자 객체를 만들지 못한
> 건수도 `B0` 와 같다. 행 순서는 동결 master 의 정렬 그대로다. 반경 인자가 실제로 적용됐는지는
> **두 행렬이 같으면 중단**하도록 assert 로 강제했고, 실측 결과 약물 1058행에서 서로 다른
> 행렬이었다. 비트 밀도 차이는 공개 요약 파일에 기록했다(지문 자체의 성질이며 결과 계열이 아니다).
> 결정적 지문이라 적합 모집단이 공집합임도 확인해 누수 assert 를 통과했다.

> **(4) 계측**
> 지시서는 `docs/48` 의 외삽값을 신뢰하지 말고 실측하라고 지정했다. 동결 RF 는 나무 수가 적고 본
> 모델은 나무 수가 많으며 잎 최소 표본 수도 다르기 때문이다. 실측한 1 model-fold 단가는 약
> 5분이었고, 이로부터 추정한 총 소요는 약 1.2시간, 실제 계산 시간 합은 약
> 0.9시간으로 정지 임계인 이레에 크게 미달했다. 본 블록은 arm 하나이고 피처 차원이
> 고정이라 model-fold 단가가 균일하므로 차원비 스케일 없이 단가 곱하기 개수로 추정했고, 실측
> 단가 분포도 200초에서 288초 사이로 균일했다.

> **(5) 전력 상태 — 소요시간은 비교 불가, 산출 바이트는 무영향**
> 본계산 도중 배터리가 임계 잔량까지 방전되어 시스템이 강제 절전에 들어갔다가 외부 전원 연결로
> 복귀했다. 전력 관리 로그에 경고 등급이 둘에서 셋으로 올라간 기록이 남아 있고, 절전 억제 도구의
> 보증은 정상 생성돼 있었으나 임계 잔량의 강제 절전은 그 보증으로 막지 못한다. 러너의 시간 측정은
> 단조 시계를 쓰고 이 시계는 절전 구간을 세지 않으므로 **fold 단가는 오염되지 않았다** — 열다섯
> 개가 모두 같은 범위이고, 절전 구간을 걸친 model-fold 는 **1개**(rep1 fold3, 공백 약
> 89분)뿐이며 그 fold 자신의 측정치도 다른 fold 와 같은 범위다. 오염된 것은 **블록 전체의
> 경과 시간**이며, 이 블록의 경과 시간을 다른 블록의 비용 추정에 투입해서는 안 된다. 같은 성격의
> 선례가 이미 대장에 있다(반복2·3 블록의 배터리 실행 기록). **산출물 바이트에는 영향이 없다** —
> 난수 시드가 고정돼 있고 연산 순서가 불변이며, 프로세스 절전·재개는 메모리 상태를 그대로
> 보존하기 때문이다. 이 무영향을 논증에 맡기지 않고 측정으로 닫기 위해, 절전 경계를 걸친 그
> model-fold 하나를 같은 코드경로로 재계산해 저장본과 바이트가 같은지 별도로 확인한다(자진 추가
> 검증 · 지시서 미요구 · 재계산본은 저장하지 않고 폐기).

> **(6) 불변 확인**
> 사다리 동결 파일과 GIN 관련 동결 셋, post-interim 확정 파일, SAP 매니페스트의 해시가 기대값과
> 전건 일치했고, 원본 러너 넷과 등록 문서 둘도 손대지 않았다. 봉인 산출물 전수 스냅샷은 착수 시점의
> 160종이 전건 불변이고, 새로 늘어난 파일은 전부 본 블록 디렉터리 안에서만 발생했다. 확증
> 조회는 **Y(값 미열람)** 로 판정한다 — 봉인 파일을 만들었고 기존 봉인을 기계 판독했으나, 사람이
> 값을 연 적은 없고(`open_sealed` 호출 없음) 접근 기록은 전건 기계 판독으로 남았으며 공개 노출은
> 형상·개수·해시·시간뿐이다.

> **(7) 한계 — 결과와 함께 보고할 것**
> 튜닝 탐색이 지문 표현까지 포함했기 때문에 비교 arm 은 primary arm 과 하이퍼파라미터와 지문 반경
> 양쪽에서 다르다. 따라서 ⑥ 은 차이의 단일 원인을 분리하지 못하며 강한 구조전용 baseline 전체와의
> 비교로만 해석해야 한다. 튜닝이 이뤄진 맥락(개발 split·더 적은 PT 집합)도 확증 설정과 달랐다.
> 두 사실 모두 결과 보고 시 병기한다.

> 지시서 = `docs/60_v3_rf_tuned_prompt_for_vscode.md`(개정판 v2) · pre-look = `docs/33` 항목32 · 확정본 = `docs/33` 항목31 국문 (2) · 동결 = `v3_Multimodal/config/rf_tuned_freeze.json`(sha256 `c1ef6406fbb48b7f`) · 공개 요약 = `experiments/runs/v3_confirm_rftuned/rftuned_public.json` · 봉인 = OOF 6종 + consensus 2종 · 무수정 대조 = `ladder_freeze.json` sha16 `b885585aefbabb32` · SAP `manifest.json` sha16 `756d485feb4715e9` · `post_interim_freeze_v1_0.json` sha16 `502db732bd5e45cb`. **미실행**: 개봉 · 성공판정 · 다중성 보정 · Δ·지표·CI·p 산출 · 부호 산출(`emit_sign`) · 재튜닝·재탐색 · split·fold·seed 재추첨 · 기존 봉인 덮어쓰기 · 동결 8모델 재계산 · ⑦ late-fusion · ⑧ RQ-int · A3·A4·A6 층화 · A5 재조회 · GIN 착수 · 네트워크 · git commit·push. 기입 시각 2026-08-06 18:43:59 KST.

---

34. **⑦ 기준 RF 선택에서 기각한 대안 — 보충 기록 (블록 P-0-1 — 착수 전 기입, 항목31 **보충**)**:

> **⑦ 기준 RF 선택에서 기각한 대안 — 보충 기록**
>
> 본 항목은 항목31 (3) 문단의 보충이며 항목31 을 대체하지 않는다. 항목31 은 Holm ⑦ 의 기준 RF 를
> `M0`(분자 지문 단독 RF)로 확정한 근거만 적었고, 함께 검토했다가 **기각한 대안**을 적지 않았다.
> 기각한 대안은 **`M1b` 를 기준 RF 로 쓰는 안**이며, 기각 사유는 두 가지다. 첫째, `M1b` 를 쓰면
> Holm ① 의 primary 대비 축(`M2b − M1b`)과 겹쳐 같은 축을 두 번 세게 된다. 둘째, 등록 §14 표가
> *"RF+seq > RF ⇒ 서열이 **fingerprint** 와 비중복 정보 제공"* 이라고 적어 기준 RF 를 지문 RF 로
> 읽도록 문면이 일의적인데, `M1b` 는 표적 유래 공변량을 포함하므로 그 문면에서 멀어진다.
> 이 기각 판단은 확정 시점(2026-08-05)에 이미 내려져 있었고 근거는 `docs/70` §1-3 에 있으나,
> 블록 S 의 기입 지시서(`docs/71`)에 해당 필드가 누락되어 동결 JSON 과 항목31 양쪽에 옮겨지지
> 못했다. 본 보충은 **Holm ⑦ 계산 착수 전에** 기록되며, 확정 내용을 바꾸지 않고 이미 확정돼 있던
> 기각 사유를 문서에 되돌려 놓는 것뿐이다.

> 지시서 = `docs/61_v3_late_fusion_prompt_for_vscode.md`(개정판 v2.1, sha256 `149252088bc12b71`) §P-0-1 · 상신 = `docs/71_..._report.md` §4-3·§5-⑤(블록 S 결손 1건) · 확정 근거 = `docs/70_advisor_reply_draft_20260805.md` §1-3 `[기각]` · JSON 대응물 = `v3_Multimodal/config/holm7_latefusion_freeze.json` `rejected_alternatives[0]` · 무수정 대조 = `post_interim_freeze_v1_0.json` sha16 `502db732bd5e45cb` · `ladder_freeze.json` sha16 `b885585aefbabb32` · `rf_tuned_freeze.json` sha16 `c1ef6406fbb48b7f` · SAP `manifest.json` sha16 `756d485feb4715e9` · `HOLM_FAMILY` 7 라벨(`sap/decision.py:44`, ⑦ `RFseq-RF` 포함). **본 항목은 항목31 을 supersede 하지 않는다** — append 로 보충하며 확정 내용을 바꾸지 않는다. **미실행**: 모델 학습·추론 · λ 선택 · Δ·지표·CI·p 산출 · 부호 산출(`emit_sign` 0) · `_sealed/` 쓰기·개봉(`open_sealed` 0) · 성공판정·다중성 보정 · split·fold·seed 재추첨 · 네트워크 · git commit·push. 기입 시각 2026-08-06 20:28:05 KST.

---

35. **실행 기록(블록 P) — Holm ⑦ `RFseq − RF` late-fusion arm 확증 OOF**:

> **(1) 무엇을 실행했고 무엇을 실행하지 않았나**
> 반복 셋(seed 201·202·203) × fold 다섯 = **15 outer unit** 을 전건 완주해
> 서열 단독 arm, 볼록결합 앙상블 arm, 고정 가중 앙상블 arm, 그리고 감도 구성 두 arm 의 확증 OOF 를
> 만들고 반복 셋의 예측을 동결 규칙대로 평균해 consensus 를 만들었다. 산출은 전량 봉인했고 신규
> 디렉터리에만 기록했다. **대비는 만들지 않았다** — 앙상블과 기준 RF 의 차이, 그 크기, 신뢰구간,
> p 값, 부호 어느 것도 산출하지 않았다. ⑦ 은 다중성 family 의 구성원이므로 부호 하나의 노출도
> 조각 개봉이기 때문이다. 성공판정 함수와 다중성 보정 함수는 호출하지 않았고, family 라벨은 소스
> 구문트리 판독으로만 확인했다(import·실행 아님).

> **(2) 확정본과 실행수준 동결**
> 설계는 이미 확정돼 있었다 — 기준 RF 는 분자 지문 단독 모델, 서열 arm 은 표적 서열 블록 단독을
> primary 로 하고 표적 수·매핑 여부를 더한 구성을 감도로 병기, 학습기는 동결 확증 RF 하네스를
> 하이퍼파라미터 그대로 서열 블록에만 적용. 본 블록이 새로 정한 것은 없고, 확정본이 실행 수준으로
> 남겨 둔 사항(재적합 assert 방식·부분 산출물 위치·봉인 파일 이름)만 별도 동결 파일에 적었다.
> 확정 파일 자체는 **한 바이트도 고치지 않았다**. 착수 전에 확정본 세 곳(동결 JSON·본 대장 항목31
> 국문 (3)·지도교수 통보문 §1-3~§1-5)이 서로 어긋나지 않음을 문면 대조로 확인했다.

> **(3) 내부 분할 — 새 추첨 0**
> 볼록결합 가중을 고르는 검증셋은 GIN 내부 검증을 위해 이미 동결해 둔 같은 분할을 그대로 공유했고,
> 새로 추첨하지 않고 동결 규칙으로 **재현**했다. 사전정렬 키가 첫 **행 인덱스**이지 cid 가 아니라는
> 점(대장 항목30 이 정정한 사항)을 그대로 따랐다. 열다섯 unit 전건에서 검증셋 크기, 학습셋 크기,
> 검증셋 scaffold 그룹 수, 검증셋에서 정의 가능한 PT 수가 동결 검증표와 **정확히 일치**했고, 두
> bucket 사이 scaffold 그룹 교차는 0, 행 합은 outer-train 과 같았다. 가중 선택에 쓰인 행과 해당
> fold 의 test 행의 교집합이 0 임도 전건 확인했다.

> **(4) 재적합 바이트 동일성 — 매 unit**
> 가중을 고른 뒤 두 base learner 를 outer training 전체로 재적합했다. 재적합하지 않으면 기준 RF 가
> 대비 상대보다 적은 표본으로 학습한 모델이 되어 대비가 서열의 비중복 정보가 아니라 학습표본 크기
> 차이를 섞기 때문이다. 재적합된 기준 RF 예측이 해당 fold 의 기존 봉인 산출물과 dtype·형상·원시
> 바이트 세 겹으로 동일함을 **15 unit 전건**
> 확인했다(결정적 RF·동일 학습행·동일 하이퍼이므로 동일해야 정상이다). 불일치는 하네스 경로가
> 어긋났다는 뜻이므로 즉시 중단하고 산출을 폐기하도록 걸어 두었으며, 실제로는 전건 일치했다.

> **(5) 가중 절차와 봉인**
> 가중은 격자 위에서 내부 검증셋 macro AP 로 골랐고 격자는 영에서 일까지 스물한 점이며 부동소수
> 누적 오차를 피하려고 정수 인덱스로 생성해 중복·결손이 없음을 확인했다. 동점이면 가운데에 가까운
> 값을, 그래도 동점이면 작은 값을 택하도록 미리 정해져 있었다. **선택된 가중값 자체는 봉인**했다 —
> 결과에 의존해 고른 양이므로 값 하나의 공개도 조각 개봉이다. 공개 요약에는 격자의 정의만 적었다.
> 가중을 반으로 고정한 판도 함께 만들어 병기했고 선택된 가중과 교체하지 않았다. 등록이 함께 보고
> 하라고 한 보조 지표(상관·순위 불일치·정오 비중복·개선 fold 비율)는 봉인 파일 안에서만 계산해
> 담고 공개 요약에는 존재 여부만 적었다.

> **(6) 계측**
> 지시서는 비용 지배변수가 RF 적합 횟수임을 명시하고 확정본의 재적합 요구를 반영하지 않은 이전
> 추정치를 신뢰하지 말라고 지정했다. 실측한 단가로부터 추정한 총 소요는 약 2.3시간이었고
> 실제 계산 시간 합은 약 2.4시간으로 정지 임계인 이레에 크게 미달했다. unit 당 RF 적합은
> 여섯 번(내부 단계 셋 + 재적합 단계 셋)이고 전체 90회이며, unit 단가 분포는 551초에서
> 619초 사이였다.

> **(7) 한계 — 결과와 함께 보고할 것**
> 표적이 매핑되지 않은 약물들의 서열 블록은 정확히 영 벡터가 되는데 이 영은 결측의 명시적 표시가
> 아니다(모델은 그것을 '표적이 없다'가 아니라 '모든 성분이 영인 표적'으로 읽는다). 따라서 상보성
> 추정치는 사실상 표적이 매핑된 약물들이 이끈다. 감도 구성은 ⑦ 의 성공판정에 쓰지 않고 primary 를
> 대체하지도 않으며 별도 파일로 봉인했다.

> **(8) 불변 확인**
> 사다리 동결 파일, GIN 관련 동결 셋, post-interim 확정 파일, 블록 O 가 신설한 동결 파일, SAP
> 매니페스트의 해시가 기대값과 전건 일치했고, 원본 러너들과 등록·통보 문서도 손대지 않았다. 봉인
> 산출물 전수 스냅샷은 착수 시점의 185종이 전건 불변이고 새로 늘어난 파일은 전부 본 블록
> 디렉터리 안에서만 발생했다. 확증 조회는 **Y(값 미열람)** 로 판정한다 — 봉인 파일을 만들었고 기존
> 봉인을 기계 판독했으나 사람이 값을 연 적은 없고 접근 기록은 전건 기계 판독으로 남았다.

> 지시서 = `docs/61_v3_late_fusion_prompt_for_vscode.md`(개정판 v2.1) · 착수 전 보충 = `docs/33` 항목34 · 확정본 = `docs/33` 항목31 국문 (3) · `docs/70` §1-3·§1-4·§1-5 · 신규 동결 = `v3_Multimodal/config/holm7_latefusion_freeze.json`(sha256 `d89f8c52412b656e`) · 공개 요약 = `experiments/runs/v3_latefusion/latefusion_public.json` · 봉인 = 반복별 21종 + consensus 6종 · 내부 분할 재현 대조 = `experiments/runs/v3_gin_inner_valid_freeze/inner_split_check.json` 전건 일치 · 무수정 대조 = `ladder_freeze.json` sha16 `b885585aefbabb32` · `gin_inner_valid_freeze.json` sha16 `038599c3e1576022` · `post_interim_freeze_v1_0.json` sha16 `502db732bd5e45cb` · `rf_tuned_freeze.json` sha16 `c1ef6406fbb48b7f` · SAP `manifest.json` sha16 `756d485feb4715e9` · `HOLM_FAMILY` 7 라벨(`sap/decision.py`, ⑦ `RFseq-RF` 포함). **미실행**: 개봉 · 성공판정 · 다중성 보정 · Δ·지표·CI·p 산출 · 부호 산출(`emit_sign`) · **λ 값 공개** · split·fold·seed 재추첨 · **내부 valid 재추첨** · 기존 봉인 덮어쓰기 · 동결 8모델·`RF_tuned` 재계산 · ⑧ RQ-int · A3·A4·A6 층화 · A5 재조회 · GIN 착수 · 네트워크 · git commit·push. 기입 시각 2026-08-06 23:34:48 KST.

---

36. **개봉 전 점검 — 봉인 완전성 점검 + 부호 인지 기록표 (블록 X — 점검·기입 전용)**:

> **(1) 무엇을 했고 무엇을 하지 않았나**
> post-interim 확정본이 "개봉 전에 봉인 완전성 점검과 부호 인지 기록표를 갖추기로 하고 그 규격을
> 여기에 명시하되 구현은 후속 블록으로 미룬다"고 남긴 두 절차를 **구현**했다. 계산·학습·추론·개봉·
> 새 부호 산출은 **한 건도 없다**. 봉인 파일에 한 조작은 경로·크기·수정시각·바이트 해싱뿐이고,
> 배열을 적재하거나 지표 파일을 역직렬화하지 않았다. 완주 격자 확인에 쓰인 체크포인트만 키
> 화이트리스트로 투영해 읽었고 지표·차이값은 메모리에도 담지 않았다.

> **(2) 기대 목록을 먼저 만들고 그 다음에 대조했다(비순환)**
> 가장 흔한 실패는 살아 있는 디렉터리를 훑어 그것을 기대 목록이라 부르는 것이다. 그러면 존재하는
> 모든 것이 기대된 것이 되어 점검이 항등식이 된다. 그래서 기대 목록을 **동결 러너의 상수(모델
> 목록·반복·fold·파일명 규칙)·동결 config·각 블록 리포트의 봉인 표·실행 시점 기록물**에서 먼저
> 구성하고, 산출군마다 그 구성 근거를 파일에 남긴 뒤 살아 있는 목록과 **양방향**으로 맞췄다.
> 기대 273종 대 실측 273종에서 **결손 0종 ·
> 예상 밖 0종**이다.

> **(3) 완주 격자는 개수가 아니라 집합으로 판정했다**
> 개수만 같고 조합이 어긋나는 경우를 잡기 위해 체크포인트에서 (반복, fold) 및 (반복, 모델, fold)
> 조합을 집합으로 뽑아 기대 격자와 **집합 동일성**으로 비교했다. 사다리 잔여·⑥·⑦·재배치 null
> 네 산출군 전건에서 집합이 같았다.

> **(4) 해시 대조와 미개봉 확인**
> 봉인 산출물 273종의 해시를 전부 계산하고, 기록물에 남아 있는
> 기대값과 대조 가능한 것을 전부 맞췄다 — **312건 대조에 불일치
> 0건**이다. 대조 근거는 실행 시점 조회 기록, 각 블록의 실행·합의 상태 파일,
> 층화·null 공개 요약의 봉인 결과 해시, 그리고 과거 블록이 남긴 봉인 감시 스냅샷이다.
> 접근 기록은 15개 파일 **91건**이며 전건이
> 기계 판독이고 **사람 노출은 0건**이다.

> **(5) 장애·재시작 기록**
> 사다리 잔여·⑥·⑦ 세 계산 블록은 모두 **단일 세션 완주**이고 환경 지문이 일치한다. 다세션이었던
> 것은 재배치 null 본런 하나이며 이는 장애가 아니라 설계상 허용된 중단·재개다(완주 2,110/2,110).
> 그 체크포인트의 시각 역행 여섯 건은 전부 **같은 세션 안의 1초** 역행으로, 열여덟 워커가 완료를
> 배치로 수집해 기록하는 데서 오는 순서 어긋남이며 중복 조합은 0이고 조합 집합은 기대 격자와 같다.
> 확정본이 명시적으로 요구한 실패·재시작 항목으로 **블록 O 의 강제 절전 89분 공백**을 등재했다 —
> 산출 바이트에는 영향이 없고(절전 경계 fold 재계산이 바이트 동일) 오염된 것은 경과시간뿐이다.
> 블록 C 의 배터리·저전력 실행과 락 자가시험의 합성 인수 기록도 함께 등재했다.

> **(6) 부호 인지 기록표 — 이미 알려진 부호만**
> 새로 알아내지 않았다. 조회 기록에서 부호가 확정된 항목을 기계로 식별하니 **4건**
> 이고 전부 주분석 대비다. 행 하나는 대비 하나에 대응시키고, 누가·언제·어떤 경로로 알았는지는
> 행 안의 인지 경로 목록으로 표현했다 — 같은 대비를 경로마다 쪼개면 대비 수가 부풀려지기 때문이다.
> 경로는 네 종류다: 러너 최초 조회, **공개 저장소를 통한 불특정 다수**, 미푸시 로컬 커밋,
> 그리고 지도교수. 공개 저장소 경로는 문자열 존재가 아니라 **스칼라 값**으로 판정했고
> (3건), 푸시 여부는 네트워크가 아니라 로컬 원격추적 참조와
> 그 이력으로 확인했다. 미푸시 커밋의 네 건은 원격 참조의 조상이 아니어서 불특정 다수에게
> 열려 있지 않다. 지도교수 경로는 조회 **이후** 서신에서 부호 전달이 확인되지 않아
> **unknown_as_of_2026-08-06** 로 남기고 미해결 질문에 올렸다 — 추측 기입은
> 하지 않는다. 어느 행에서도 부호 이후에 설계나 성공기준이 바뀐 사실은 없다.

> **(7) 상신 두 건의 독립 재현**
> cowork 가 상신한 정합 불일치 두 건을 베끼지 않고 직접 재현했다. 첫째, 구조화 대장의 조회 등록부
> 행이 하나뿐인데 조회 기록의 부호 확정 항목은 넷이다 — 사실이었다. 설계 의도를 확인하니 최초
> 조회 지시서가 구조화 대장도 **같이 갱신**하라고 정했고 문서판 대장은 이미 넉 줄이므로, 구조화
> 대장만 뒤처진 것이다. 이후 블록들이 이 객체의 **불변**을 자기 검증 항목으로 걸어 둔 탓에 갱신
> 기회가 없었다. 따라서 기존 한 줄은 그대로 두고 **세 줄을 append** 했으며 낡은 상태 문면은
> 지우지 않고 정정 문면을 **덧붙였다**. 둘째, 같은 객체가 접근 기록을 "부재"라고 적고 있으나 실제로는
> 파일 15개 91건이 존재한다 — **"열람 0"이라는
> 판정 자체는 여전히 참**이고 "파일이 부재"라는 서술만 틀렸다. 둘을 섞지 않고 후자만 정정했다.

> **(8) 불변 확인**
> 동결 아홉 종의 해시가 기대값과 전건 일치하고 다중성 family 라벨은 소스 구문트리 판독으로 일곱
> 개다. 봉인 전수는 착수·종료가 **산출물 273종 / 전체 288종**으로
> 완전히 같고, 본 블록이 봉인에 더한 파일은 **0**이다. 개봉 여부는 여전히 거짓이며 **본 점검
> 통과는 개봉 허가가 아니다** — 개봉은 다중성 family 전원 확보와 별도 승인이 있어야 한다.

> 지시서 = `docs/78_pre_unblinding_audit_prompt_for_vscode.md` · 규격 정본 = `v3_Multimodal/config/post_interim_freeze_v1_0.json` `pre_unblinding_procedures_specified`(sha16 `502db732bd5e45cb`) · 본 대장 항목31 국문 (5) · 산출 = `experiments/provenance/sealing_completeness_audit.json`(sha256 `b189f77f30dce9b5`) · `experiments/provenance/sign_disclosure_matrix.json`(sha256 `d20415256c087825`) · `docs/79_sign_disclosure_matrix.md`(sha256 `99d3292aa0f0dabd`) · 공개 요약 = `experiments/runs/v3_pre_unblinding_audit/audit_public.json` · 무수정 대조 = `ladder_freeze.json` sha16 `b885585aefbabb32` · `gin_seed_freeze.json` sha16 `10828447c6d33118` · `gin_inner_valid_freeze.json` sha16 `038599c3e1576022` · `rf_tuned_freeze.json` sha16 `c1ef6406fbb48b7f` · `holm7_latefusion_freeze.json` sha16 `d89f8c52412b656e` · SAP `manifest.json` sha16 `756d485feb4715e9`(v1.1 · 11모듈 일치) · `HOLM_FAMILY` 7 라벨(`sap/decision.py:44`, 구문트리 판독). **미실행**: 개봉(`unblinding_performed` false 유지) · `open_sealed` · 성공판정 · 다중성 보정 · Δ·지표·CI·p 산출 · 부호 산출(`emit_sign`) · `decision.py` 호출 · 새 부호 인지 · 봉인 파일 역직렬화 · `_sealed/` 쓰기·수정·삭제 · split·fold·seed 재추첨 · A5 재조회 · GIN 착수 · ⑧ RQ-int · 네트워크 · git commit·push. 기입 시각 2026-08-07 09:57:45 KST.

---

37. **A5(작용기전 표적 지시자) 정의 동결 — 재조회 착수 **전** 기입 (블록 Y 전반부)**:

> **(1) 무엇을 지금 기입하고 무엇을 아직 하지 않았나**
> ChEMBL `/mechanism` 1회 재조회에 착수하기 **전에** A5 축의 정의와 구간을 파일로 고정한다.
> 조회는 이 항목을 쓴 **뒤에** 시작한다. 지금 시점에 수행한 네트워크 요청은 **0건**이고,
> 조회 캐시 디렉터리는 **아직 존재하지 않는다**(러너가 만든다). A5 층화 계산·Δ·CI·p·라벨 결합은
> 이 블록의 범위가 아니다 — 승인 조건이 "라벨과 결합하기 **전에** 캐시를 봉인" 이므로
> **봉인 지점이 블록의 끝**이고 층화는 후속 블록이다.

> **(2) 왜 조회보다 먼저 쓰는가**
> 커버리지를 먼저 보고 나서 구간을 정하면 "결측이 많아서 경계를 옮겼다"는 의심을 구조적으로
> 배제할 수 없다. 그래서 순서를 뒤집어, **정의를 고정한 시각**(`frozen_at_kst`
> 2026-08-07 10:36:00 KST)이 최초 네트워크 호출 시각보다 이르다는 것을 러너가 기동 시 assert 하도록
> 걸어 두었다. 정의·구간은 러너가 새로 만들지 않았고 `docs/63` §2 표의 A5 행(줄 41, sha256
> `2c009368f2848220`)을 **축자로** 옮겼다 — 정의 = 「약물의
> mechanism 표적 중 unseen 이 하나라도 있으면 1, 전부 seen 이면 0, mechanism 표적이 없으면
> no_mechanism」, 구간 = `{0}` · `{1}` · `no_mechanism`.

> **(3) 승인의 범위를 부풀리지 않는다 — 두 항목을 분리 기재했다**
> 교수님이 명시적으로 승인한 것은 **1회 재조회**뿐이다(`docs/77` §3 주석 1 — 질문 「▶ 위 조건으로
> 1회 재조회를 승인해 주시겠습니까? (승인 / 불승인·A5 미수행)」 에 대한 답 축자 **「승인」**).
> A5 의 **정의·구간**에 대해서는 명시적 승인 문구가 없으므로 A3·A4·A6 과 같은 경로,
> 즉 **내선 확정(`no_objection_raised`)** 으로 적었다. 동결 파일의 `advisor_status` 는 이 둘을
> `explicitly_approved` 와 `definition_status` 로 **분리**해 담는다. 승인 조건 4항은 원문 그대로
> 옮겼다 — ① 기존 943개 ID 한정·1회만 ② 조회일·출처·원응답·해시·ID 매핑 실패율 기록
> ③ 라벨과 결합하기 전 캐시 봉인 ④ A5 는 **"현재 snapshot 기반 post-interim 보조분석"** 으로 표기.
> 넷째 조건은 `analysis_label` 에 축자로 넣었다.

> **(4) 재표집 규약은 새로 정하지 않는다**
> 재표집 seed·B·재표본 단위·CI 방법은 블록 H/L 에서 이미 고정된 것을 **그대로 재사용**하며
> 새 seed 추첨은 **0**이다(확정본 `axes_a3_a4_a6.resampling` 인용). 비매핑 245 약물은 `{0}` 에
> 병합하지 않는 **사전 정의 제외 집합**이고, 3반복에서 층이 엇갈리는 약물은 제외가 아니라
> `unstable_stratum` 으로 분리 집계한다(H-0-1). 보고 형식도 앞선 두 유사도 축과 동일한
> 사전고정 구간 형식을 따른다 — 축마다 형식이 다르면 축 간 비교가 불가능해지기 때문이다.

> 산출 = `v3_Multimodal/config/a5_mechanism_freeze.json`(sha256 `3419b2f793d74051`) · 지시서 = `docs/80_a5_mechanism_requery_prompt_for_vscode.md` · 승인 기록 = `docs/77` §3 주석 1 · 정의 정본 = `docs/63` §2 A5 행(줄 41) · 선행 = `post_interim_freeze_v1_0.json`(sha16 `502db732bd5e45cb`) `axes_a3_a4_a6.A5_status` 「NOT frozen here - requires a one-off re-query…」 · 읽기 전용 입력 3종 sha16 = `02_chembl.csv` `48b3c13cfe12c68a` · `06_targets_human.csv` `2784c1bd0fb8df3b` · `08_m1b_covariates.csv` `c302399f32c71083`. **이 시점 미실행**: 네트워크 요청(0건 · 캐시 디렉터리 미생성) · 라벨 결합 · `master_Y`·PT·OOF 접근 · A5 층화·Δ·CI·p · `emit_sign` · `decision.py` 호출 · 개봉(`unblinding_performed` false 유지) · `_sealed/` 쓰기(273/288 불변) · GIN 착수 · ⑧ RQ-int · git commit·push. 기입 시각 2026-08-07 10:37:00 KST.

---

38. **A5 작용기전 표적 1회 재조회 — 조회·해석·캐시 봉인 완료 (블록 Y 후반부)**:

> **(1) 무엇을 했고 어디서 멈췄나**
> 항목37에서 정의를 고정한 뒤 ChEMBL `/mechanism` 을 **943 화합물 한정·1회** 조회했다.
> 승인 조건이 "라벨과 결합하기 **전에** 캐시를 봉인" 이므로 **봉인이 이 블록의 끝**이다 —
> A5 층화·Δ·CI·p 는 한 건도 계산하지 않았고 `master_Y`·PT·OOF·성능 산출물은 **열지 않았다**.
> 산출은 `(cid, chembl_id, target_chembl_id, uniprot, action_type, mechanism_of_action, …)` 표와
> 그 원응답·해시·실패율 기록뿐이다.

> **(2) 배치를 쓰지 않은 이유 — 이 블록이 존재하는 이유이기도 하다**
> 과거 수집(`fetch_m1b_covariates.py:82`)은 `molecule_chembl_id__in=` **배치**로 조회했고,
> `only=` 에 `molecule_chembl_id` 를 넣었는데도 응답에서 그 필드가 대부분 빠져 **약물 귀속이
> 소실**됐다(`docs/63` §3). 그래서 이번에는 `?molecule_chembl_id=<ID>` 로 **분자당 1요청**을 보내
> 귀속을 **응답 본문이 아니라 요청 자체**로 보장했다. 응답에 `molecule_chembl_id` 가 있는 경우
> 요청 ID 와 일치하는지 매 건 assert 했고 **불일치 0건**이다. 비용은 늘지만 귀속 보장이 우선이다.

> **(3) 조회 결과와 실패율**
> 요청 943건 중 성공 **943건** · 실패 **0건**(실패율 0.0000).
> 실제 네트워크 호출은 1087건이며, 성공한 ID 를 다시 부른 일은 없다
> — 재개 시 캐시에서 읽고 네트워크를 치지 않도록 체크포인트를 두었다. 요청 URL 은 전건 로그로
> 남겼고 관측된 호스트는 `www.ebi.ac.uk` 하나뿐이다.

> **(4) target → UniProt 해석과 그 scope 해석 1건**
> A5 의 unseen 판정 기준은 UniProt accession 인데 mechanism 응답은 `target_chembl_id` 를 준다.
> 먼저 기존 로컬 파일(`06_targets_human.csv`)로 해석하고, 그래도 남는 target 만 `/target/{id}` 로
> 조회했다. mechanism 이 지목한 target 전체 **333종** 중 로컬 해석 **189종** · 추가 조회 해석
> **124종** · 끝내 미해석 **20종**(대리지표 대체 0 — 미해석은 미해석으로 남긴다).
> ★ **여기에 해석이 하나 들어간다**: 승인 문면의 "기존 943개 ID 한정" 은 **화합물** 기준인데
> `/target/` 조회 대상은 그 943 화합물의 응답이 **스스로 지목한** target 이므로 새 화합물 도입이
> 아니라고 읽었다. 이는 우리의 해석이므로 사유·조회 건수(144건)·
> 엔드포인트를 manifest `scope_interpretation` 에 명시하고 리포트에도 적었다.
> 한 target 이 여러 UniProt 을 갖는 경우(86종)는 임의로 하나 고르지 않고 **전건 보존**했다.

> **(5) 봉인의 뜻 — `_sealed/` 로 옮기는 것이 아니다**
> A5 캐시는 **라벨과 무관한 메타데이터**라 `_sealed/` 에 넣지 않았다. 넣었다면 봉인 회계
> 273/288 이 깨지고 개봉 대상으로 오분류됐을 것이다. 여기서 봉인은 **조회 시점 상태를 해시로
> 고정해 이후 변경을 불가능하게 만드는 것**이고, 캐시 파일 2174종의
> 해시를 전건 기록한 뒤 manifest 를 쓴 **직후 다시 해시해 일치**를 확인했다. 응답은 절삭·정규화
> 없이 **바이트 원문 그대로** 보관했다(`raw/` 1087건). 기존 캐시
> `_cache/` 는 읽지도 쓰지도 않았고 신규 디렉터리에만 기록했다.

> **(6) 과거 수집과의 정합 — 판정이 아니라 사실**
> `08_m1b_covariates.csv` 의 `mechanism_target_n` 과 약물별 mechanism 표적 수를 대조하니
> **일치 943건 · 불일치 0건**이다. snapshot 시점이 다르므로 불일치는
> 예상 범위이고, 그래서 A5 를 **"현재 snapshot 기반 post-interim 보조분석"** 으로 표기한다
> (승인 조건 ④ 축자). 불일치는 전건 열거해 manifest 에 남겼다. A5 세 구간 중
> **`no_mechanism` 에 해당할 약물은 393종**이다 — 이는 **층 배정이 아니라 가용성 수치**이며
> `{0}`/`{1}` 배정은 unseen 판정이 필요하고 그것은 후속 블록이다.

> **(7) 승인 범위를 부풀리지 않았다**
> 교수님이 명시적으로 승인한 것은 **재조회 행위**뿐이고(`docs/77` §3 주석 1 축자 「승인」),
> A5 의 정의·구간은 A3·A4·A6 과 같은 **내선 확정(`no_objection_raised`)** 으로 적었다.
> 이 구분은 동결 파일 `advisor_status` 와 manifest `approval.scope` 양쪽에 그대로 들어 있다.

> 지시서 = `docs/80_a5_mechanism_requery_prompt_for_vscode.md` · 승인 = `docs/77` §3 주석 1 (2026-08-06 12:05:26 KST 축자 「승인」) · 정의 정본 = `docs/63` §2 A5 행(줄 41) · 산출 = `v3_Multimodal/config/a5_mechanism_freeze.json`(sha256 `3419b2f793d74051`) · `data/processed/target_mapping/a5_mechanism_targets.csv`(sha256 `62fb85d013a15d15`) · `experiments/provenance/a5_requery_manifest.json`(sha256 `66023c1d4403bbb2`) · 공개 요약 = `experiments/runs/v3_a5_requery/a5_requery_public.json` · 캐시 = `data/processed/target_mapping/_a5_mechanism_cache/`(`cache_tree_sha256` `349e42d5f11771e7`) · 무수정 대조 = `ladder_freeze.json` sha16 `b885585aefbabb32` · `gin_seed_freeze.json` sha16 `10828447c6d33118` · `gin_inner_valid_freeze.json` sha16 `038599c3e1576022` · `post_interim_freeze_v1_0.json` sha16 `502db732bd5e45cb`(**0바이트 수정**) · `rf_tuned_freeze.json` sha16 `c1ef6406fbb48b7f` · `holm7_latefusion_freeze.json` sha16 `d89f8c52412b656e` · SAP `manifest.json` sha16 `756d485feb4715e9`(v1.1 · 11모듈) · 기존 캐시 `_cache/` 무수정. **미실행**: 라벨 결합(`label_join_performed` false · `master_Y`·PT·OOF 접근 0) · A5 층화·Δ·CI·p·부호 · `emit_sign` · `decision.py` 호출 · 개봉(`unblinding_performed` false 유지) · `_sealed/` 쓰기(273/288 착수=종료) · 친화도 수치 기록 · 943 밖 화합물 조회 · 2회차 조회 · GIN 착수(`gin_start_still_blocked` true 유지) · ⑧ RQ-int · git commit·push. 기입 시각 2026-08-07 11:13:28 KST.

---

39. **A5 경계 명료화 — 세 번째 축(A3·A4·A5·A6) 층화 착수 **전** 기입 (블록 Z 전반부)**:

> **(1) 무엇을 지금 정하고 무엇을 아직 하지 않았나**
> 등록 §11 세 번째 축(unseen-target proportion) 4변형의 층화에 착수하기 **전에**, A5 의 경계
> 가운데 동결 문면이 판정하지 못하는 경우를 확정해 파일로 고정한다
> (`v3_Multimodal/config/a5_boundary_amendment.json`, sha256 `860f5a4529dfb57b`, 기입 시각
> `2026-08-07 12:05:16 KST`). 이 시점에 산출한 Δ·AP·CI·p·부호는 **0건**이고 봉인 디렉터리는
> **아직 존재하지 않는다**(러너가 만든다).

> **(2) 왜 계산보다 먼저 쓰는가**
> 층별 표본수를 먼저 보고 나서 경계를 정하면 "표본이 적어서 층을 합쳤다"는 의심을 구조적으로
> 배제할 수 없다. 그래서 순서를 뒤집어, **경계를 고정한 시각**이 `_sealed/checkpoint.jsonl` 의
> **최소 ts**(= 최초 Δ 산출 시각)보다 이르다는 것을 종료검증이 기계 확인하도록 걸어 두었다.

> **(3) 무엇이 문제였나 — 동결 문면이 세 경우를 구분하지 못한다**
> A5 동결 문면은 「mechanism **표적**이 없으면 `no_mechanism`」 인데, 블록 Y 가 캐시를 만들면서
> 실제 데이터에는 ① 레코드 자체가 없는 경우 ② 레코드는 있으나 `target_chembl_id` 가 비어 있는
> 경우 ③ `target_chembl_id` 는 있으나 UniProt 이 전부 미해석인 경우가 **따로** 존재한다는 것이
> 드러났다(`docs/80` §4-4). 문면은 이 셋을 구분하지 못한다.

> **(4) 사용자 결정(2026-08-07) — 네 구분**
> **A. 레코드 없음 → `no_mechanism`**(문면 그대로). **B. 레코드는 있으나 표적 없음 →
> `no_mechanism`** — 문면이 「**표적**이 없으면」 이라고 적었으므로 기준은 레코드 유무가 아니라
> **표적 유무**다. **C. 표적은 있으나 UniProt 전부 미해석 → 신규 층 `not_estimable`** — 표적이
> **있으므로** `no_mechanism` 이 아니고, unseen 판정이 UniProt accession 대조로 이뤄지는데 대조할
> accession 이 없으므로 `{0}`/`{1}` 도 아니다. **D. UniProt 1개 이상 해석 → `{0}`/`{1}`
> 배정**(문면 그대로). 최종 구간 = `{0}` · `{1}` · `no_mechanism` · `not_estimable`.

> **(5) 이것은 정의 변경이 아니라 경계 명료화다**
> `a5_mechanism_freeze.json`(sha256 `3419b2f793d74051`)의 `definition`·`bins` 는 **1바이트도 수정하지
> 않는다**(`supersedes_nothing: true`). 본 항목은 그 문면이 **이미 채택한 기준**(표적 유무)을
> 판정 불가 경우에 적용한 결과를 적을 뿐이다. 신규 층 `not_estimable` 도 새 효과 구간이 아니라
> **estimability 부재 표기**다 — 교수님 2026-08-03 결정(「빈 층 = 효과 부재가 아니라 estimability
> 부재」)과 같은 취지이며, 대리지표로 대체하지 않는다(미해석은 미해석으로 남긴다).

> **(6) 승인 범위를 부풀리지 않는다**
> 본 경계 명료화는 A3·A4·A6 과 같은 **내선 확정(`no_objection_raised`)** 이고 **명시적 승인이
> 아니다**. 교수님이 명시적으로 승인한 것은 **1회 재조회 행위**뿐이다(`docs/77` §3 주석 1).
> 승인 조건 ④의 표기 **"현재 snapshot 기반 post-interim 보조분석"** 은 **A5 에만** 붙이고
> A3·A4·A6 에는 붙이지 않는다 — 그 조건은 재조회를 거친 A5 에 대한 것이기 때문이다.

> 산출 = `v3_Multimodal/config/a5_boundary_amendment.json`(sha256 `860f5a4529dfb57b`) · 지시서 = `docs/81_axes_a3a4a5a6_stratification_prompt_for_vscode.md` Z-2 · 선행 = `v3_Multimodal/config/a5_mechanism_freeze.json`(sha256 `3419b2f793d74051`, **0바이트 수정**) · `post_interim_freeze_v1_0.json` `axes_a3_a4_a6`(sha16 `502db732bd5e45cb`) · 계기 = `docs/80` §4-4. **이 시점 미실행**: Δ·AP·CI·p·부호 산출(0건 · 봉인 디렉터리 미생성) · 층 배정 · `emit_sign` · `decision.py` 호출 · Holm/BH · 개봉(`unblinding_performed` false 유지) · 모델 재학습·재추론 · A5 재조회(`a5_requery_executed` true 불변 · 네트워크 0) · 새 seed·B·CI 방법 추첨 · GIN 착수(`gin_start_still_blocked` true 유지) · ⑧ RQ-int · git commit·push. 기입 시각 2026-08-07 12:06:05 KST.

---

40. **등록 §11 세 번째 축 — A3·A4·A5·A6 unseen-target proportion 층화 실행 (블록 Z — 실행·기록 전용, 블록 Z 후반부 — 착수 전 기입은 항목39)**:

> **(1) 무엇을 했나 — §13-6 커버리지의 마지막 결손**
> 블록 H(구조·서열 2축)·블록 L(`Δ(M2b−P-ID)`) 이후 남아 있던 등록 §11 **세 번째 축 4변형**
> (A3·A4·A5·A6)을 수행했다. 정의는 이미 동결돼 있었다 — A3·A4·A6 은
> `post_interim_freeze_v1_0.json` `axes_a3_a4_a6`(sha16 `502db732bd5e45cb`), A5 는 블록 Y 의
> `a5_mechanism_freeze.json`(sha16 `3419b2f793d74051`) + 착수 전 경계 명료화
> `a5_boundary_amendment.json`(sha16 `860f5a4529dfb57b`, 항목39). 층 **20개** ×
> 대비 **2종**(`Δ(M2b−M1b)`=Holm ① · `Δ(M2b−P-ID)`=Holm ②) = **40 unit-run 전건 완주**,
> 산출은 **전량 `_sealed/axes_result.json`**(sha256 `5c1aa8e24cd5ca9c`). **모델 재학습·재추론 0 ·
> 새 OOF 0 · 네트워크 0 · 개봉 0 · 성공판정 0 · 다중성 보정 0 · Δ·AP·CI·p·부호 공개 0.**

> **(2) 착수 전 동결이 계산보다 먼저임을 시각으로 증명**
> A5 경계 명료화 기입 **2026-08-07 12:05:16 KST** < 최초 Δ 산출 **2026-08-07 19:14:27 KST**
> (`a5_boundary_amendment.json` `amended_at_kst` vs `_sealed/checkpoint.jsonl` 최소 `ts_kst`).
> 층별 표본수를 보고 구간을 조정하는 경로를 구조적으로 차단했다 — 동결 구간을 그대로 썼고
> 경계 조정은 **0건**이다(`axes_summary.json` `boundary_adjustment`).

> **(3) 비순환 판정 2건 — 러너가 임의로 고르지 않았다**
> ① `pchembl_median` 정본 파일: 동결 문면은 파일을 지목하지 않으므로(*"as produced by the
> existing frozen pipeline"*) **동결 커버리지 상수를 재현하는 쪽**으로 판정했다. 후보 2개를 모두
> 채워 보고 `05b_affinity_values.csv`(sha16 `9abf3972100f168d`)가
> **12514/
> 12613 pair · drug
> 16/847** 을
> 재현해 정본으로 확정했고, `07_agg_topk.csv` 는
> 3436 로 재현하지 못했다(단일 후보만 재현 →
> 판정 유일). ② A5 표적도 블록 H 와 **같은 함수·같은 인자**
> `sap_unseen.canonicalize_set(t, None, None)`(isoform 절단만)을 통과시킨 뒤 `T_train_f` 와
> 비교했다 — 생략하면 집합 원소가 어긋나 unseen 이 과대계상된다. 고유 UniProt
> **758 → 758**.

> **(4) A5 모집단 943 ≠ 추정 모수 847 — 분해를 독립 재현했다**
> 두 집합의 관계를 실측했다: 943 ∩ 847 = **847** ·
> 847 중 A5 모집단 밖 **0** · 943 중 847 밖
> **96**(비매핑 245 사전 제외 집합의 일부). 847 **내부** 분해는
> A **326** / B **21** / C **24** / D **476** (합 847)
> 이고 943 기준으로는 A 393 / B 27 / C 29 / D 494 다.
> cowork 참고값을 베끼지 않고 러너가 원자료에서 재계산했으며 일치했다. C 집단
> (**표적은 있으나 UniProt 전부 미해석**)이 `{0}`·`{1}`·`no_mechanism` 에 유입되지 않았음을
> 하드 assert 로 확인했고, `not_estimable` 층 == C 집합임을 양방향으로 확인했다.

> **(5) 회계 하드 게이트 — 축마다 통과**
> 축별 `Σ stable + unstable` = A3 847 · A4 847 ·
> A5 847 · A6 847 = **847** ·
> `847 + 245 =
> 1092` · **네 축의 추정 대상 약물 집합 동일**
> (true).
> 층별 표본수 — A3: `{0}` 552 · `(0,0.5)` 184 · `[0.5,1)` 14 · `{1}` 18 · `unstable_stratum` 79 / A4: `{0}` 557 · `(0,0.5)` 172 · `[0.5,1)` 12 · `{1}` 12 · `no_evidence` 16 · `unstable_stratum` 78 / A5: `{0}` 264 · `{1}` 181 · `no_mechanism` 347 · `not_estimable` 24 · `unstable_stratum` 31 /
> A6: `{0}` 741 · `{1}` 48 · `no_evidence` 16 · `unstable_stratum` 42. 3반복 배정이 일치하면 `stable`, 불일치는 축별 `unstable_stratum`
> 으로 **제외가 아니라 분리 집계**했다(블록 H-0-1 계승).

> **(6) 상수는 전건 import 재사용 — 새 추첨 0**
> `SEED_BOOTSTRAP` 6001 · `SEED_SIGNFLIP` 6002 ·
> `B_MAIN` 10000 · `BOOT_UNIT` `scaffold_cluster` · `ELIGIBLE_PT` None(370 PT 전열) ·
> `EXPECT_DENOM` 847 · `WALL_ABORT_DAYS` 7 을 `stratification_run.py` 에서 **import 재사용**했고,
> 그 사실을 **AST 로 기계 확인**했다(대상 14종 ·
> 리터럴 재정의 0 ·
> 새 seed 추첨 0).
> 블록 H·L 러너(`stratification_run.py`·`pid_stratification_run.py`)는 **한 줄도 수정하지 않았다**.

> **(7) 계측은 층별 직접 실측 — 선형 가정 코드 부재**
> 블록 H 가 층 비용을 약물수 선형으로 **가정**해 1.74배 과소추정했고 블록 L 이 직접 실측으로
> 맞췄으므로(`docs/57` §4) 본 블록도 **층 × 대비마다 Δ 1회를 직접 실측**한 뒤 최대 표본 층
> (`A6/{0}`, n=741)
> 에서 `B=100` 파일럿으로 비례상수만 보정했다(`linear_assumption_used`
> false). 추정 총 wall **22.29h** — 정지 임계
> 7.0일 미만 확인 후 진입 → 실측 **21.49h**(추정 대비
> 0.96배). 파일럿 통계 산출은 **전량 폐기**(봉인 저장 0)하고 시간만 남겼다.

> **(8) 본계산과 공개 범위 — Δ 의 부호조차 공개하지 않는다**
> 층마다 두 대비 각각 `B=10000` 재표집 · 단위 `scaffold_cluster` · primary CI
> `BCa`. 공개 파일 `axes_public.json` 에는 축·층 이름·표본수·클러스터수·
> formal(28)/descriptive(12) 라벨·회계·판정 근거·B·seed·시간·해시·게이트뿐이고,
> `macro_ap`·`delta`·`sign`·`ci_*`·`p_*`·`boot_*`·`null_*` 계열 키가 **부재**함을 방어 assert 로
> 강제했다. 키 이름뿐 아니라 **값**으로도 판정한다 — 허용 실수는 층 경계 정의값·계측 시간·
> 계측 보정상수·load1·RSS 뿐이고 그 밖의 float 는 차단된다. 공개
> **4파일** 전건 검출 **0**
> (`redaction_scan_public.json`).

> **(9) 자체 검사코드 결함 1건(발견·수정 — 봉인 산출물 무관)**
> 본계산 완주 직후 공개요약이 40건 **전건**을 `not_estimable` 로 표기했다. 원인은 통계가
> 아니라 **내가 쓴 공개요약 코드**다 — estimability 판정 필드는 `ci_primary.status`
> (∈ `estimable`/`not_estimable`, SAP A1 상 **BCa 성공 시에만** `estimable`)인데 내가
> `ci_bca.status` 로 걸렀고, 그 필드의 성공 토큰은 `estimable` 이 아니라 **`bca`**
> 여서(`sap/bootstrap.py` `_bca_ci` 반환 규약) 전건이 거짓 분류됐다. 정본 필드로 교정하고
> 규약을 `estimability_rule` 로 공개 파일에 명시했다. 실측은 `ci_primary`
> **40/40 estimable** → **BCa 불능 층 0건 · percentile 자동대체
> 0건**. 교정은 **체크포인트 40건 전건 SKIP** 으로
> 수행해 **통계 재계산 0**, 봉인 파일은 **재작성 0 · 판독 0**
> (`sealed_result_rewritten_this_run` false ·
> sha256 `5c1aa8e24cd5ca9c` 본계산 종료 시점 값 그대로).

> **(10) 한계(정직 고지)**
> (i) 본 블록은 **추정만** 했고 판정하지 않았다 — 층별 산출은 다중성 보정 전 raw 이며 해석은
> 개봉·Holm/BH 이후에만 가능하다. (ii) A5 는 승인 조건 ④에 따라 **"현재 snapshot 기반
> post-interim 보조분석"** 표기를 유지하며 이 표기는 **A5 에만** 붙고 A3·A4·A6 에는 붙지 않는다.
> (iii) A5 경계 명료화는 **내선 확정이지 명시적 승인이 아니다** — 교수님이 명시적으로 승인한
> 것은 1회 재조회 행위뿐이다(`docs/77` §3 주석 1). (iv) `not_estimable` 24
> 명은 **estimability 부재이지 효과 부재가 아니며** 대리지표로 대체하지 않았다. (v) 두 대비는
> **동일 재표집 난수**를 공유하므로 서로 독립이 아니다(블록 H·L 과 동일한 의도된 설계).

> 지시서 = `docs/81_axes_a3a4a5a6_stratification_prompt_for_vscode.md` · 리포트 =
`docs/81_axes_a3a4a5a6_stratification_report.md` · 착수 전 기입 = `docs/33` 항목39 ·
동결 = `a5_mechanism_freeze.json`(sha16 `3419b2f793d74051`, **0바이트 수정**) ·
`a5_boundary_amendment.json`(sha16 `860f5a4529dfb57b`) · `post_interim_freeze_v1_0.json`(sha16
`502db732bd5e45cb`) · 공개 요약 = `experiments/runs/v3_stratification_axes/axes_public.json` ·
봉인 = `_sealed/axes_result.json`(sha256 `5c1aa8e24cd5ca9c`) + `_sealed/checkpoint.jsonl` 40행 ·
입력 기계 판독 = `consensus_M1b` `f77a69528ebdb88c` · `consensus_M2b` `8594592e2afae583` ·
`consensus_P-ID` `9598da3498b1d3ce` · 무수정 대조 = `ladder_freeze.json` sha16 `b885585aefbabb32` · SAP
`manifest.json` sha16 `756d485feb4715e9` · sealed guard **273종 불변**. **미실행**: 개봉
(`unblinding_performed` false 유지 · `open_sealed` 0건) · 성공판정
(`decision.py` 호출 0건) · 다중성 보정
false · 부호 산출(`emit_sign`
false) · Δ·AP·CI·p·부호의 공개 기입 · 모델 재학습·재추론
(0) · 새 OOF(0) · 층 경계·정의 변경 · 새 seed·B·CI
방법·재표집 단위 추첨 · A5 재조회(`a5_requery_executed` true 불변 · 네트워크
0) · GIN 착수(`gin_start_still_blocked` true 유지) · ⑧ RQ-int ·
`stratification_run.py`·`pid_stratification_run.py` 수정 · `data/raw/` 변경 · git commit·push.
기입 시각 2026-08-08 16:45:40 KST.

---

41. **`docs/55b` 국문 정본의 `M1`/`M1b` 서술 정정 — 2026-08-05 약속 이행 (블록 AA-A — 문면 정정 전용)**:

> **(1) 왜 고쳤나 — 미이행 약속의 해소**
> 2026-08-05 15:02:56 KST 발신 메시지(`<GMAIL-MSGID>`) §③ 에서 영문본의 `M1b` 서술을
> "molecular structure + 10차원" → "M1 + 10차원" 으로 고치면서 **국문 정본 `docs/55b` 도 함께
> 수정하겠다고 약속**했으나 이행되지 않았다(`ledger.json` `timeline[32].run_facts.open_commitment`,
> `status` = `not_fulfilled_as_of_2026-08-06`). 결함은 둘이었다 — ① `docs/55b`:48 이 `M1` 을
> **정의 없이 나열**했고 ② 같은 줄이 `M1b` 를 "구조 + 비서열 표적 공변량 10차원" 으로 적어
> **`B1`(2차원)이 누락**돼 nested 사다리(`M1` ⊂ `M1b` ⊂ `M2b`)가 깨져 보였다.

> **(2) 정정 3요소 — 값은 동결 파일에서 실측했다**
> 러너는 cowork 문장을 베끼지 않고 `v3_Multimodal/config/ladder_freeze.json` 을 직접 읽어
> `models_frozen` 과 `blocks_frozen` 에서 다음을 확인한 뒤 문면을 썼다 —
> `M1` = `[B0, B1]`, `B0` = Morgan ECFP r=2 · 2048-bit, `B1` = **2차원**
> (① `log1p(매핑 human 표적 수)`, 해당 fold 의 train 에서만 적합한 `StandardScaler`
> ② 매핑 mask 0/1) → **`M1` 차원 = 2048 + 2 = 2050**; `M1b` = `[B0, B1, B_m1b]` = **`M1` + 10차원**;
> `M2b` = `[B0, B1, B_m1b, B_seq]` = `M1b` + 64차원.
> 세 번째 요소 = **coverage 제외 사유** — OSF 동결본 `docs/30` §4 는 `M1` 을
> "M0 + log(표적수) + missing/coverage" 로 적었으나 구현은 mask 만 쓰는 2차원이다.
> 매핑된 약물에서 coverage 평균이 **상수 1.000** 이라(`docs/31_v3_target_audit_meanpool_report.md`:141)
> mask 와 완전히 중복되기 때문이며, 이 사유는 `ladder_freeze.json`
> `blocks_frozen.B1_count_mask.def` 에 이미 동결돼 있었다. 등록문↔구현 불일치로 오해되지 않도록
> 정정문에 함께 적었다. 절 번호는 규약대로 **OSF `docs/30` 기준**으로 인용했다.

> **(3) 무엇을 지웠고 무엇을 남겼나 — 최소 치환 + 원 문면 보존**
> 착수본(sha256 `83f896ea55a885ab`, 43,764 B)에서 **모델 사다리 불릿(48~50행) 한 곳만** 치환했다.
> 치환 구간 앞 접두사(1~47행, sha256 `635120a2c1368961`)·중간 통과 구간(착수본 51~52행,
> sha256 `6d303562646b1c19`)·뒤 접미사(착수본 53행~끝, sha256 `6b6c20edbc225330`)가
> 착수본과 **바이트 동일**함을 기계 확인했고, 이 셋에 원 불릿 3행을 다시 끼워 재조립한 결과가
> 착수본 sha256 과 **완전 일치**함으로써 치환 구간 밖 변경 0 을 증명했다.
> **원 문면은 흔적 없이 덮이지 않았다** — 같은 절 하단 각주 1줄에 원 문구
> "구조 + 비서열 표적 공변량 10차원" 을 **축자 인용**해 보존했다. 종료본 sha256
> `21f71e0fbfa3c4d1` · 45,610 B. 착수본은 `docs/55b_..._v2.md.pre_fix.bak` 로 보존했다.

> **(4) ★ 정정판 ≠ 발송본 — 검토자는 옛 판본을 갖고 있다**
> `docs/55b` 는 **2026-08-05 15:02:56 KST 에 PDF 로 이미 발송**됐고(메시지 `<GMAIL-MSGID>`,
> 제목 「통계 검토 문서 수정하여 송부드립니다.」; 15:19 에 Word 포맷 재전송), 외부 검토자께는
> 교수님이 전달하셨다. 지금 고친 정본은 **그 발송본과 다르다** — 검토자가 보유한 판본에는
> 위 정정이 반영돼 있지 않다. 이 사실을 정정 각주 안에도 명시했다.
> **본 블록에서 재발송·후속 메일은 하지 않았다**(발송 여부는 사용자 판단 → `open_questions`).
> 참고로 같은 성격의 미해소 2건이 더 있다 — ① 발송 PDF 의 `§11-4 기입란` 누락
> ② 영문본 §④ "대표 fold·seed 가 어느 문서에도 없다" 가 블록 Q(2026-08-05 16:51)로 stale 이 된 건.
> **둘 다 본 블록 범위 밖**이며 후속 메일 1통으로 함께 처리하는 선택지가 있다는 사실만 남긴다.

> **(5) `.docx` 재생성과 구조 검증**
> `pandoc` 부재로 기존 관례대로 `v3_Multimodal/src/md_to_docx_min.py` 로 재생성했다
> (기존 docx 는 `.pre_fix.bak` 로 백업, sha256 `b573b00ffeb7eee4`). 재생성본 sha256
> `74510e0f0bd9b5ba` · 33,299 B. 구조 검증 = 표 **12개 전건 `w:tbl`**,
> `Heading1/2/3` = 1/12/19 로 착수본과 **동일**(절 번호 `## 0.`~`## 11.` = 최고 절 번호 11).
> md↔docx 텍스트는 마크다운 강조문자를 제거한 정규화 비교에서 **완전 일치**
> (착수본 19,457자 = 19,457자 / 정정판 20,289자 = 20,289자). docx 텍스트 차분은 공통 접두
> 2,078자 + 공통 접미 17,154자로 **변경이 정정 구간에만 국한**됨을 확인했다.

> **(6) 한계(정직 고지)**
> (i) 본 정정은 **문면만** 고쳤다 — 동결값·모델·수치는 한 글자도 바뀌지 않았고 재계산도 없다.
> (ii) 정본과 발송본의 괴리는 **해소되지 않았다**(재발송 미수행). (iii) `open_commitment` 의
> 기존 `status` 문자열은 supersede 규약에 따라 **덮어쓰지 않고** 신규 timeline entry 에
> 해소 사실을 적었으므로, 대장을 읽을 때는 두 entry 를 함께 보아야 한다.

> 지시서 = `docs/82_docs55b_m1b_fix_and_a5_relabel_prompt_for_vscode.md` §AA-A ·
리포트 = `docs/82_docs55b_m1b_fix_and_a5_relabel_report.md` ·
약속 원문 = `ledger.json` `timeline[32].run_facts.open_commitment`(**객체 단위 무수정**) ·
정본 근거 = `v3_Multimodal/config/ladder_freeze.json`(sha16 `b885585aefbabb32`, **0바이트 수정**) ·
등록 문면 = `docs/30_preregistration_OSF_clean.md` §4 · coverage 실측 =
`docs/31_v3_target_audit_meanpool_report.md`:141 · 정정 대상 = `docs/55b_..._v2.md`
(`83f896ea55a885ab` → `21f71e0fbfa3c4d1`) + `.docx`(`b573b00ffeb7eee4` → `74510e0f0bd9b5ba`) ·
v1 무수정 대조 = `docs/55_..._package.md` sha16 `1f6081d824bb2c95` · `.docx` sha16 `222eb130cdddfc64` ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**. **미실행**: 재발송·후속 메일 ·
`docs/55`(v1) 수정 · 계산·재계산 · 모델 학습·추론 · Δ·AP·CI·p·부호 산출 · `emit_sign` ·
`decision.py` 호출 · 개봉(`unblinding_performed` false 유지) · `open_sealed` · 봉인 판독·쓰기 ·
`open_commitment` 덮어쓰기 · 네트워크 · `data/raw/` 변경 · git commit·push.
기입 시각 2026-08-09 15:47:29 KST.

---

42. **A5 층 `not_estimable` 개명 — `mechanism_target_unresolved` (블록 AA-B — 라벨 정정 전용, 산출물 무수정)**:

> **(1) 왜 고쳤나 — 예약어와의 명칭 충돌**
> 이 프로젝트에서 `not_estimable` 은 **SAP A1 의 예약어**로 「BCa 실패 → `ci_primary` 추정 불가」를
> 뜻한다(`experiments/sap/manifest.json` A1 · `sap/bootstrap.py:201-209`; 선례 = 블록 L
> `seq_stratum::unseen_ge90`). 그런데 A5 의 이 층은 실측상 `estimable: true` ·
> `inference_mode: formal` 로 **정상 추정됐고**(24명·16 scaffold cluster), 같은 공개 파일
> `axes_public.json` 안에 SAP 뜻의 `not_estimable_units: []` · `n_not_estimable_units: 0` 이
> **공존**한다. 한 문서에서 같은 낱말이 두 가지를 가리키므로 심사자가 반드시 걸린다.

> **(2) ★ 원인 귀속 — 러너가 아니라 cowork 다**
> 이 이름을 지은 주체는 **cowork** 다. `docs/81` 지시서 Z-2 가 A5 의 C 집단 층 이름을
> `not_estimable` 로 규정했고, **블록 Z 러너는 지시서대로 정확히 수행했다**. 러너 과실이 아니며
> 본 항목은 지시서 결함의 사후 정정이다.

> **(3) 새 이름과 그 근거**
> `not_estimable` → **`mechanism_target_unresolved`**. 이 층의 실제 성격은 "추정 불가"가 아니라
> "mechanism 표적을 UniProt 으로 해석하지 못함"이다
> (`a5_boundary_amendment.json` `cases.C` = `target_chembl_id` 는 있으나 UniProt 전부 미해석).
> `no_mechanism`(347명, 표적이 **없음**)과는 **다른 뜻**임이 이름에서 드러나야 한다 —
> 이쪽은 표적이 **있는데** 해석이 안 된 경우다. SAP 의 `not_estimable` 뜻은 **그대로**이며
> `sap/` 하위 파일은 한 글자도 바뀌지 않았다(`sap_not_estimable_definition_unchanged: true`).

> **(4) 무엇을 했고 무엇을 하지 않았나 — 순수 라벨 문제**
> **한 것** = 매핑 파일 1개 신설(`v3_Multimodal/config/a5_stratum_label_supersede.json`,
> sha256 `ac187375d2a7c16e`) + 본 대장 기입 + `ledger` 기입. 앞으로의 모든 보고·논문은 새 이름을 쓴다.
> **하지 않은 것** = `_sealed/axes_result.json` 수정(**절대**) · `axes_public.json` 수정 ·
> `axes_assignment.csv` 수정 · 재계산 · 층 멤버십 변경. **층 구성원은 한 명도 바뀌지 않았다** —
> 그래서 산출물을 다시 만들 필요가 없고, 다시 만들면 오히려 `ts_kst` 때문에 해시만 흔들린다
> (블록 Z 편차 2 교훈). 세 산출물은 착수=종료 sha256 동일함을 기계 확인했다 —
> `_sealed/axes_result.json` `5c1aa8e24cd5ca9c` · `axes_public.json` `a539c83d51a9bb92` ·
> `axes_assignment.csv` `2bae421f9e5fa863`. 봉인 파일은 **해시만 대조**했고 판독하지 않았다.

> **(5) 구성원 실측(공개 CSV 만 판독)**
> `axes_assignment.csv` 에서 `stable_A5=True` 이고 3반복 배정이 모두 `not_estimable` 인 cid =
> **24명**으로 `axes_public.json` 의 `n_drugs` 24 와 일치했다. 정렬 cid 목록의
> sha256 = `17148aa9166d415c` 이며 목록 전건을 매핑 파일에 기록했다. 이 판독은 확증 조회가 아니다
> (Δ·AP·CI·p·부호 미판독) → `docs/45` §5 확증 조회 대장 **+0행**.

> **(6) 한계(정직 고지)**
> (i) 이미 생성된 산출물·기록물(`axes_public.json`·`axes_assignment.csv`·`_sealed/`·
> `a5_boundary_amendment.json`·`docs/33` 항목39·40·`docs/81` 리포트)은 **옛 이름을 그대로 담고
> 있다** — append-only 원칙상 소급 재작성하지 않았으므로, 읽는 이는 매핑 파일을 함께 보아야 한다.
> (ii) 새 이름은 **cowork 확정 사항**이며 `advisor_status` 는 **내선 확정 · 명시적 승인 아님**이다.

> 지시서 = `docs/82_docs55b_m1b_fix_and_a5_relabel_prompt_for_vscode.md` §AA-B ·
리포트 = `docs/82_docs55b_m1b_fix_and_a5_relabel_report.md` · 원인 = `docs/81` 지시서 Z-2(cowork) ·
신규 매핑 = `v3_Multimodal/config/a5_stratum_label_supersede.json`(sha256 `ac187375d2a7c16e`) ·
무수정 대조 = `_sealed/axes_result.json` `5c1aa8e24cd5ca9c` · `axes_public.json` `a539c83d51a9bb92` ·
`axes_assignment.csv` `2bae421f9e5fa863` · `a5_boundary_amendment.json` sha16 `860f5a4529dfb57b` ·
`a5_mechanism_freeze.json` sha16 `3419b2f793d74051` · `ladder_freeze.json` sha16 `b885585aefbabb32` ·
SAP `manifest.json` sha16 `756d485feb4715e9` · sealed guard **275/291 불변**. **미실행**: 재계산 ·
층 멤버십 변경 · 산출물 3종 수정 · SAP 정의 변경 · 개봉(`unblinding_performed` false 유지) ·
`open_sealed`(봉인 판독 0 · 해시 대조만) · 성공판정 · 다중성 보정 · Δ·AP·CI·p·부호 산출 ·
`emit_sign` · 네트워크 · git commit·push. 기입 시각 2026-08-09 15:47:29 KST.

---

43. **RQ-int 검정 구현 및 R6 검증 (블록 AC — 합성 전용, 동결 아님)**:

> **(1) 무엇을 만들었나 — 신규 파일만, 동결 모듈 0바이트**
> 등록 §8 Holm family ⑧ `RQ-int` 슬롯의 검정 절차를 **`docs/55b` §5 후보 B**(공유 동전
> scaffold-blocked arm-swap)로 구현했다. 신규 파일 4개 = `v3_Multimodal/src/sap/rqint.py`
> (sha256 `eb842bc98140e9c5`) · `sap/rqint_synthetic.py`(`27ef0011ee041920`) ·
> `sap/rqint_audit.py`(`ddffe6d128de4d18`) · `run_rqint_audit.py`(`ab831c2726a36e8a`).
> **SAP manifest 등재 11모듈은 전원 sha256 착수=종료 동일**(0바이트)이고 `manifest.json`
> sha16 `756d485feb4715e9` · `sap_version` **1.1** 불변, `freeze.py` `MODULE_FILES`(11개)와
> `__init__.py` 모듈 목록에 신규 파일을 **등재하지 않았다**(SAP 1.2 동결 블록의 일).

> **(2) 설계 — 무엇을 계승했고 무엇을 새로 정했나**
> 지표 `metrics.macro_ap` 와 repeat 축 집계 `consensus.build_consensus` 는 **동결 정의를 그대로
> import 재사용**했다(estimand 분기 방지). 양측 p 공식과 tolerance 는 `signflip.py` 를
> **import 하지 않고 축자 계승**했다 — `count = sum(|T*| >= |T_obs| - _EPS)`,
> `p = (1 + count) / (참조분포 크기 + 1)`, `_EPS = 1e-12`(카운트를 늘리는 **보수적** 방향).
> 집계 형식은 `docs/84` D3 = repeat 축 **prediction-then-metric**(양 family 공통) ·
> seed 축 **metric-then-average**(GIN 전용). 동전 벡터 `z` 는 D4 대로 **3 seed × 3 repeat 전체에
> 공동 적용**하고, consensus **8행렬(RF 2 + GIN 3seed×2)은 순열 루프 밖 1회** 산출한다(D5,
> `assert len(mats) == 8`).

> **(3) ★ 강한 null / 약한 null 불일치 — 모듈 docstring 에 명문화**
> 후보 B 가 **부과**하는 귀무는 `H0^B`(각 family 내부에서 arm 라벨이 군 단위로 교환 가능
> = Δ_RF = 0 **이고** Δ_GIN = 0, **강한 null**)이고, **검정 대상** 가설은
> `H0^int: Δ_RF = Δ_GIN`(공통값 ≠ 0 허용, **약한 null**)이다. `H0^B ⊊ H0^int` 로 **둘은
> 일치하지 않는다.** 따라서 이 검정을 **"약한 null 에 대한 정확검정"으로 표기하는 것을 금지**하고,
> 약한 null 하 1종오류 통제는 **R1 캘리브레이션 감사(C0~C3)로 실증되기 전까지 주장하지 않는다**
> (`rqint.NAME_CAVEAT` · A6 `signflip.NAME_CAVEAT` 와 같은 규격). 모델 재학습은 포함하지 않는
> 고정 OOF 의 conditional randomization 이다.

> **(4) R6 9항 — 전항 PASS (합성 fixture 산출, `experiments/rqint/audit_r6.json` sha256 `921e16ea8191bc9b`)**
> R6-1 가환성(임의 z 100개 × 8행렬 = 800쌍, `np.array_equal` 전건 성립, max abs diff **0.0**) ·
> R6-2 zero-effect → p **정확히 1.0**(T=0, 모든 T*=0) ·
> R6-3 대칭 할당 균등성(R=200, mean(p) **0.4950**, KS **0.0514** < 0.16 — `audit_uniform` 과
> **동일 허용오차** mean_tol 0.10 · ks_tol 0.16, 재측정 불요) ·
> R6-4 여집합 반대칭(**1,000 draw 명시적 재계산 전건 PASS**, max dev **0.0**, 폴백 미발동) ·
> R6-5 전체 교환 보존(z ≡ 1 → T* = −T, dev **0.0**) ·
> R6-6 군 순서 불변(순서보존 재라벨 + 행 치환에서 p·T **정확 동일**) ·
> R6-7 재실행 결정성(참조분포 **바이트 동일**) ·
> R6-8 완전열거 정답표(G=8 → 2^8=256 전수 exact p **0.046875** vs 몬테카를로 p **0.047619**,
> 차 **0.00074** ≤ 3×MC SE **0.01003**) ·
> R6-9 독립 구현 대조(8행렬 사전산출·여집합 항등식·벡터화를 **쓰지 않는** 이중 루프 참조 구현과
> T* 수열 max abs diff **0.0**; 참조 구현은 `rqint.py` 를 import 하지 않고 동전열만 같은 seed 로
> 각자 생성). ★ 이 수치는 **전부 합성 fixture 산출물**이며 `G`(20 또는 8)는 **감사용 임의값**으로
> 확증 분할의 scaffold group 수와 무관하다.

> **(5) ★ `B` 정의는 미확정으로 남긴다 — 본 블록에서 정하지 않았다**
> 여집합 쌍(`z̄ = 1 − z`)은 `T*(z̄) = −T*(z)` 가 **항등적으로** 성립해(R6-4 로 실증) 참조분포를
> 정확히 대칭으로 만들고 **평가 비용을 절반**으로 줄인다. 그래서 코드는 `n_coin_vectors`(뽑은
> 동전 수)와 `n_permutation_values`(참조분포 크기 = 전자 × 2)를 **둘 다 기록**하며, **어느 쪽을
> 등록 문면의 `B` 로 부를지는 `still_unspecified`** 다(SAP 1.2 에서 확정 필요).
> **★ 추가 관측(설계상 중요)**: 양측 p 는 `|T*|` 를 쓰므로 `|T*(z̄)| = |T*(z)|` 이고, 여집합 값은
> 양측 p 에 **추가 정보를 주지 않는다** — 몬테카를로 오차는 **독립 동전 draw 수**가 지배한다.
> 여집합 쌍의 효용은 **참조분포의 정확한 대칭성**이지 p 의 정밀도 향상이 아니다.

> **(6) 약한-null 예비 진단 — 판정 아님(게이트로 쓰지 않았다)**
> `Δ_RF ≈ Δ_GIN ≠ 0` 합성 fixture(R=200)에서 mean(p) **0.4585** · frac(p ≤ 0.05) **0.0950** ·
> frac(p ≤ 0.05/7) **0.0150** · frac(p ≤ 0.05/4) **0.0350**(실현 평균 Δ_RF 0.3251 · Δ_GIN 0.3313 ·
> |Δ 격차| 0.0535). 명목 대비 대략 **2~3배**로, 검토자가 지적한 **우려 1(강한/약한 null 불일치)·
> 우려 2(공유 동전의 분산 축소 → anti-conservative)** 와 방향이 일치한다. **그러나 이 수치로
> 합격·불합격을 판정하지 않았다** — 정식 판정은 **R1 의 C1~C3**(α=0.05 뿐 아니라 0.05/7·0.05/4
> 에서도 봄, A10)이며 본 진단은 **R1 설계에 넣을 예상 규모를 잡기 위한 것**이다.

> **(7) 단가 계측 — 실측만, 외삽 0**
> `per_permutation_seconds` = **0.015306 s**(macro-AP 8회 포함한 T* 1회 평가의 벽시계 실측 평균,
> 합성 fixture N=100 · K=10 · G=20 · 200 draw). 확증 규모로의 **외삽은 하지 않았다**(계측 블록의 일).
> 감사 전체 벽시계 **1,041.08 s**. 환경 = Python 3.14.4 · numpy 2.5.0 · scikit-learn 1.9.0 ·
> macOS-26.5.2-arm64.

> **(8) 고정 시드집합 조건부성(D6) — 유의성과 무관하게 항상 기록**
> 반환 dict 는 `inference_conditional_on = "pre-specified GIN training seed set"` 과
> **시드별 대비 서술통계**(`delta_gin_per_seed` 리스트 + mean·sd)를 **항상** 담는다(D6-ii).

> **(9) ★ 본 기입은 어떤 착수 허가도 아니다**
> **차단 상태 전부 유지** — `unblinding_performed` **false** · `gin_start_still_blocked` **true** ·
> SAP 1.2 재동결 **미실행**(`sap_version` 1.1 유지) · `B` 확정 **미실행** · R1 캘리브레이션 감사
> C0~C4 **미실행** · C0~C3 복제 수 **미확정** · `manifest.json` `model_family` erratum **미처리** ·
> 레버리지 진단 λ·ρ **미실행**. 본 블록은 **구현 + 합성 감사**일 뿐이며, 확증 데이터로의 적용은
> R1 통과와 SAP 1.2 동결 이후다.

> **(10) 항목번호 산출과 충돌 가능성(정직 고지)**
> 항목번호 **43** 은 `doc_numbering.next_item_number` 로 **실측 산출**했고(하드코딩 0),
> 중복 assert 는 선재 `{16: 2}` 만 허용목록으로 통과했다. **블록 AB(`docs/86`)가 아직
> 실행되지 않았으므로** AB 가 나중에 자기 번호를 다시 실측하면 본 항목과의 선후가 바뀔 수 있다 —
> AB 러너는 실행 시점에 번호를 **재실측**해야 한다.

> 지시서 = `docs/89_rqint_implementation_r6_prompt_for_vscode.md` ·
리포트 = `docs/89_rqint_implementation_r6_report.md` · 설계 정본 = `docs/55b` §5 후보 B ·
`docs/84` §1 D3·D4·D5·D16 / §2 R6 · 산출 = `experiments/rqint/audit_r6.json`(sha16 `921e16ea8191bc9b`) ·
`experiments/rqint/run.log`(sha16 `43f395828040f2b5`) · SAP `manifest.json` sha16 `756d485feb4715e9`
**불변** · 동결 11모듈 sha256 **전원 착수=종료 동일** · sealed guard **275종(access.log 제외) /
291종(포함) 불변**. **미실행**: 확증 데이터 로드(`master_X`/`master_Y`/`scaffold_split.json`/확증 OOF) ·
`_sealed/` 읽기·쓰기(stat-only 스냅샷 착수=종료 동일) · 개봉(`unblinding_performed` false 유지) ·
`open_sealed` · `emit_sign` · `decision.py` 호출 · 성공판정 · 다중성 보정 · 모델 학습·추론 ·
GIN 착수 · SAP 재동결 · `MODULE_FILES`·`__init__.py` 갱신 · R1 감사 C0~C4 · 네트워크 ·
`data/raw/` 변경 · git commit·push. 기입 시각 2026-08-12 16:13:13 KST.

---

44. **RQ-int 계측 및 C0~C4 예산 확정 (블록 AD — 계측 전용, 판정 0)**:

> **(1) 무엇을 했나 — 시간과 규모만 쟀다**
> `docs/84` §5 실행순서 **④(계측 → C0~C4 복제·순열 수 확정)**. 신규 파일 2개(**`sap/` 밖**) =
> `v3_Multimodal/src/rqint_timing.py`(sha16 `fdb0dcd4822b2f88`) ·
> `rqint_reduced_fixture.py`(`e5a46bc38cdb8879`). 산출 4종 =
> `experiments/rqint/timing.json`(`85c222e8f50ec290`) · `profile_match.json`(`17098c5286be4a54`) ·
> `weak_null_scaled.json`(`f5946db74fdd1554`) · `budget.json`(`51867bfd1fc6a3f6`).
> **1종오류·검정력 판정 0 · `B` 확정 0 · SAP 1.2 동결 0 · 축소 fixture 규칙 동결 0 ·
> GIN 착수 0 · 개봉 0 · 네트워크 0 · 동결물 0바이트.**

> **(2) 입력 — 라벨·군만 실제, 예측행렬은 100% 합성**
> `docs/84` §2 R1 설계가 명시 허용한 대로 **실제 라벨행렬(`master_Y`)과 실제 스캐폴드
> 군집구조(`master_X` → `scaffold_of`)** 만 로드했고(여는 데이터 경로는 이 **2개뿐**, AST 스캔
> 전건 확인), **예측행렬은 전부 `sap.synthetic._scores_from_labels` 합성**이다
> (`predictions_are_synthetic: true` · `confirmatory_predictions_loaded: false`).
> 군 산출은 확증 러너의 `scaffold_of` 를 **import 재사용**(F-SCAF, 재구현 0).
> 형상 assert = **N 1,092 · K 370 · G 732 · `n_eligible` 370 · `n_eval` 370 · undefined-AP 0**.

> **(3) AD-1-1 전규모 군 프로파일 — D13 과 일치**
> Kish `G_eff` = **85.347**(D13 85.3, 차 0.047) · 상위 2군 행 점유율 **14.194%**(D13 14.2%) ·
> `G_eff/G` = **0.11659**(D13 0.117). 군 크기 min/median/max = **1 / 1 / 78**, 싱글톤 **627개
> (85.7%)**, no-scaffold 버킷 **77행**, 벤젠군(`c1ccccc1`) **78행**. **D13 은 전건 재현되었다.**

> **(4) AD-2 단가 — 단독(w=1) 실측, 외삽 0**
> AC 전원 · `powermode 0`(저전력 해제) · BLAS 5종 명시 고정. `T*` 1회 평가(= consensus 8행렬
> 위 macro-AP 8회) 벽시계 = 전규모(1,092×370×732) **0.71665 s** · 축소(400×60) **0.099663 s** ·
> 참조(블록 AC 조건 N=100·K=10·G=20 재현) **0.015707 s**. 참조값은 F-PPS **0.015306 s** 대비
> **1.026배** — 환경 일치 확인. 스레드 감도는 무시 가능(전규모 1스레드 0.71665 vs 전량 0.70713,
> 축소 0.099663 vs 0.098288) = 본 워크로드는 **BLAS 병목이 아니다**.
> **열감쇠**: 전규모 단독 지속부하 **614.6 s**(≥600 s 충족, 21 구간) 에서 처리율 변화
> **+0.20%**(끝이 오히려 빠름) → 단독 열감쇠 **0**.

> **(5) AD-3 병렬 — `W_BEST = 18`, 결정성 전건 성립**
> 워커 {1,3,6,9,12,18} × 두 규모. 처리량은 **`w / wall_max`**(F-THR) 정의로 계산했고 평균 기반
> 계산은 **0건**. 워커 wall 불균등 `(max−min)/median` ≤ **1.5%**(전 구성). 축소 규모
> evals/s = 9.94 → 88.39(w=18), 전규모 1.23 → 7.88(w=18). **실효 병렬 배수**(같은 오버헤드를
> 가진 w=1 대비) = 축소 **8.90×** · 전규모 **6.40×**(logical 18 대비 효율 49% / 36% —
> P코어 6 + E코어 12 구성상 예상 범위). **RAM 게이트**: 10초 주기 전 워커 RSS 합계 최대
> **4.75 GiB(축소) / 7.28 GiB(전규모)** ≪ 임계 30.72 GiB(예산 38.4 × 80%) → **탈락 워커 수 0**.
> **★ 결정성(G1 상당)**: 같은 seed 에서 `T*` 수열 sha256 이 **워커 수와 무관하게 바이트 동일**
> (두 규모 × 6 구성 전건 PASS). 워커당 스레드 상한 = `logical // w` 를 **spawn 이전에 환경변수로
> 고정**하고 실효 스레드 수를 런타임 실측 기록했다.

> **(6) AD-4 축소 fixture 규칙 확정 — 그리고 ★ `G_eff/G ≈ 0.117` 은 N=400 에서 도달 불가**
> 규칙 **R-ROW** = 실제 군 크기 분포의 **최대잉여법 비례축소**(잉여 내림차순 → 군 크기 내림차순
> → 군 키 오름차순의 결정적 배분), 규칙 **R-PT** = 선정 400행 안의 **라벨 유병률만**으로 6 등분위
> 층화 후 층당 10개 seed(20260812) 고정 추출 — 성능·예측·부호 **일절 미참조**, 최저층에
> 유병률 **1** 인 극희귀 PT 포함(적격 369 중 60 선정, 유병률 min 1 / median 8.5 / max 222).
> **★ 설계 결함 보고(cowork FACTS)**: `docs/84` §2 R1 이 "축소규모에서 `G_eff/G ≈ 0.117` 재현
> 필수"라 했으나, `G_eff/G = (Σm)²/(G·Σm²)` 이고 **상위 2군이 Σm² 를 지배**하므로, 상위 2군
> 행 점유율을 실제값(14.2%)에 맞춘 채 N=400 에서 얻을 수 있는 **최소값은 0.13255**(전수 탐색:
> 상위 29·28 + 크기 28 블록 5개 + 싱글톤 203 → G=210)이며 **0.117 은 도달 불가능**하다.
> → 본 블록은 **형상 충실(비례축소)을 primary 로 확정**한다: `G_eff/G` 만 비율최적 변형(0.1326)이
> 낫고, **나머지 4개 프로파일 지표는 비례축소가 전규모에 더 가깝다** — 상위2군 점유율
> 0.1425(전규모 0.1419) · `max n²/Σn²` **0.408**(전규모 0.435 / 비율최적 0.146) · 크기 왜도
> **11.74**(전규모 17.44 / 비율최적 5.20) · 단일군 교환 레버리지 상위5 점유 **0.493**
> (전규모 0.363 / 비율최적 0.636). 두 변형은 **라벨행렬·행 집합이 동일**하고 군 라벨만 다르다.
> **bridge smoke**(전규모 R=10 × 순열 300, 기술통계만): 실현 Δ_RF 0.0120 / 0.0322 로 목표를
> 재현했고 p 분포 형상이 축소와 질적으로 어긋나지 않았다(**판정 아님**, R=10 이라 해상도 없음).

> **(7) AD-5 약한-null 재측정 — ★ 계측이지 판정이 아니다**
> 축소 fixture(N=400·K=60)에서 공통효과 목표 Δ ∈ {0.01, 0.03}, **R=200 · 내부 순열 300**
> (참조분포 600) × 두 군 변형 = 4셀. 강도(logit)→Δ 보정은 원점통과 선형적합(probe 4점 × 40복제)
> 으로 잡았고 **실현 평균 Δ_RF 0.01347 / 0.03631 · Δ_GIN 0.01188 / 0.03453 · 평균 |Δ 격차|
> 0.02509 / 0.02518**. 결과 `frac(p ≤ 0.05)` = **0.050 / 0.060 / 0.045 / 0.050**
> (MC SE 0.015~0.017) — **명목 0.05 대비 0.9~1.2배**로 사실상 명목 수준이다.
> **★ 이는 블록 AC 예비 진단(Δ≈0.33 에서 1.9배)이 C1~C3 의 예측치가 아님을 실증한다** —
> 공유 동전 arm-swap 의 anti-conservativeness 는 **공통효과 크기에 의존**하며, AC 값은
> 상한에 가깝다. 다만 **꼬리에서는 다르다**: 0.05/7(=0.00714) 지점에서 비례축소 변형이
> **0.025 / 0.015**(명목 대비 3.5 / 2.1배, 기대 카운트 1.43 · SE 0.00595)로 나왔고 비율최적
> 변형은 **0.000 / 0.005**(0 / 0.7배)였다. R=200 은 이 지점의 해상도가 낮다.
> **★ 이 수치로 어떤 합격·불합격도 판정하지 않았고, R1 합격기준(기각률 ≤ α + 2·SE)을 적용하지
> 않았으며, 후보 B 를 채택·기각하지 않았다.** 정식 판정은 **R1 의 C1~C3** 다.
> JSON·리포트 양쪽에 `status: "계측 · 판정 아님"` · `NOT_AN_ANALYSIS_RESULT: true` 를 기입했다.

> **(8) AD-6 비용 모델과 C0~C4 확정값 — 근거는 단가뿐**
> 비용 모델 = `총 평가 횟수 = Σ(복제 × 내부 순열)`, `총 벽시계 = 총 평가 횟수 / 처리량(W_BEST)
> × (1 + 열감쇠율)`. **비용 축은 `n_coin_vectors`**(F-COIN) — 여집합 항등식 `T*(z̄) = −T*(z)`
> 때문에 **참조분포 크기는 평가 횟수의 2배**이며 여집합은 평가 0회로 도출된다(각주 명시).
> 확정: **C0~C3 = 복제 2,000 × 내부 순열 2,000**(F-C03 범위 1,000~2,000 의 **상한** — 단가상
> 7일 예산에 여유가 있어 범위 내 최대 정밀도를 택함) · **C4 = 복제 400 × 내부 순열 1,000 ×
> τ 3격자**(F-C4 범위 200~400 의 상한, 사전지정 τ=0.02). 예상 벽시계 = C0~C3 각 **15.55 h** ·
> C4 **46.61 h** · **총 108.79 h = 4.53 일** → **`exceeds_7d = false`**.
> **기각률·검정력·p 분포를 근거로 쓰지 않았다**(중단 조건 준수). 열감쇠율은 단독 0 과 병렬
> 4셀 드리프트(0.052/0.067/0.077/0.249) 중 **최댓값 0.249** 를 **보수적으로** 적용했다
> (중앙값이면 총 벽시계 0.858배). 모든 외삽에 `estimate_not_measurement: true` + 실측 앵커 병기.
> **A12 적응적 중지 규칙**(C4: 최대 400 / 200 시점 Wilson 95% 구간이 0.50·0.80 경계를 가로지르지
> 않으면 중단 / 가로지르면 400 / 400 에서도 가로지르면 낮은 지위)을 **사전 기술**했다(적용 0).

> **(9) `B` — 미확정 유지**
> 전규모 드라이런 예상 벽시계 = `n_coin_vectors` **100,000 → 3.88 h** · **50,000 → 1.94 h**
> 로 둘 다 F-BREC 의 24 h 기준 이내다. **그러나 본 블록은 `B` 를 확정하지 않는다** —
> 값도, `n_coin_vectors` vs `n_permutation_values` 정의도 **`still_unspecified`** 이며
> SAP 1.2 동결 블록의 일이다(판정만 예고).

> **(10) ★ 본 기입은 어떤 착수 허가도 아니다**
> **차단 상태 전부 유지** — `unblinding_performed` **false** · `gin_start_still_blocked` **true** ·
> `sap_version` **1.1** 불변 · manifest sha16 `756d485feb4715e9` 불변 · 등재 11모듈 sha256
> 착수=종료 동일(0바이트) · 블록 AC 산출 4파일 sha256 동일 · `freeze.py` `MODULE_FILES`·
> `__init__.py` 무변경 · `_sealed/` stat 스냅샷 착수=종료 동일(**275종 / 291종**) ·
> **R1 캘리브레이션 감사 C0~C4 미실행** · SAP 1.2 재동결 미실행 · 축소 fixture 규칙 **동결 미실행** ·
> `manifest.json` `model_family` erratum 미처리 · 레버리지 진단 λ·ρ 미실행(D11 은 GIN 선행 필요).

> **(11) 항목번호 산출**
> 항목번호 **44** 은 `doc_numbering.next_item_number` 로 **실측 산출**(하드코딩 0), 중복 assert 는
> 선재 `{16: 2}` 만 허용목록으로 통과. **블록 AB(`docs/86`)는 여전히 미실행**이므로 AB 러너는
> 실행 시점에 자기 번호를 **재실측**해야 한다(현재 `docs/33` 최대 번호 = 44).

> 지시서 = `docs/90_rqint_timing_calibration_budget_prompt_for_vscode.md` ·
리포트 = `docs/90_rqint_timing_calibration_budget_report.md` · 설계 정본 = `docs/84` §1 D13·D15·D19 /
§2 R1 · 선행 = `docs/89` 리포트(블록 AC) · 산출 = `experiments/rqint/{timing,profile_match,
weak_null_scaled,budget}.json` · SAP `manifest.json` sha16 `756d485feb4715e9` **불변** ·
동결 11모듈 + 블록 AC 산출 4파일 sha256 **전원 착수=종료 동일** · sealed guard **275종
(access.log 제외) / 291종(포함) 불변**. **미실행**: 확증 예측·OOF 로드 · `_sealed/` 읽기·쓰기
(stat-only 스냅샷 착수=종료 동일) · 개봉 · `open_sealed` · `emit_sign` · `decision.py` 호출 ·
성공판정 · 다중성 보정 · 1종오류·검정력 판정 · `B` 확정 · GIN 학습·착수 · SAP 1.2 재동결 ·
`MODULE_FILES`·`__init__.py` 갱신 · R1 감사 C0~C4 · 네트워크 · `data/raw/` 변경 · git commit·push.
기입 시각 2026-08-12 20:59:49 KST.

---

45. **RQ-int 외부 통계검토 회신 접수 및 절차 결정 기록 (블록 AB — 기입 전용)**:

> **(1) 무엇을 접수했나 — 판정과 조건**
> <EXTERNAL-REVIEWER> Ph.D.(Department of Information and Communications Engineering, KAIST /
> Gyeongnam Intelligence Innovation Center)의 **2026-08-10** 자 외부 통계검토 회신을 원장에 등재했다.
> 판정 = **Approved with revisions**(조건부 승인), 조건 = **R1~R6 전부 봉인해제 이전 완료**.
> 러너는 cowork 요약을 베끼지 않고 회신 원본(`docs/RQint_Reviewer_Response_<EXTERNAL-REVIEWER>_20260810.docx`,
> sha256 `0c29ddf201eb6751`)의
> `word/document.xml` 을 직접 판독해 표지 표 6개 값을 **축자 추출**했고, 착수 시 판별자 문자열
> `"reverts to the paired scaffold-cluster BCa interval"` 존재를 재확인했다(부재 시 중단 조건 발동 예정이었다).
> **날짜 불일치 1건** — 표지 `Date of review` = **2026-08-10**, **부록 B** = **2026-08-06**.
> 우리는 표지 기준 08-10 을 채택해 서명 요청본에 기입하고 "08-06 이 맞으면 수정 요청" 문면을 함께
> 넣었으며, **두 리터럴을 모두 보존**한다(임의 삭제 0). 부록 B 는 `Affiliation` **공란** ·
> 서명/일자 **미기입** → `signature_status = pending_as_of_2026-08-12`.

> **(2) 승인 조건 R1~R6 과 차단 관계**
> R1 = 캘리브레이션 감사 C0~C4 완료(**실패 시 승인 무효 → 후보 C 회귀**) · R2 = GIN 학습 착수 이전
> SAP v1.2 동결 + 해시 · R3 = **제2자 독립 재실행** · R4 = Holm 이중보고를 SAP 문언에 포함 ·
> R5 = 기지 부호 4건·공개일자·노출 인원을 개정문에 명시 · R6 = A6 감사 2종을 RQ-int 코드경로에 재실행.
> **★ R5 는 `partial` 이다(러너 실측).** 회신·cowork 는 "§8 초안 이미 충족" 이라 적었으나, `docs/55b` §8
> 개정문 문면에 **기지 부호 4건은 있으나 공개일자 2026-07-27 은 없고**(§2 본문 `docs/55b`:137 에만 있음)
> **노출 인원 수는 문서 어디에도 없다**. SAP 1.2 개정문에 두 요소를 추가해야 R5 가 완결된다.

> **(3) 회신 §9-1 요구 — A6 코드 실물 재확인(러너 독립 실측)**
> 회신은 "A6 은 이미 동결되어 시험 ②③⑤⑥⑦ 에 사용된 모듈이므로 **코드 실물을 확인하라**"고 했다.
> `v3_Multimodal/src/sap/signflip.py`:76 을 **AST 로 판독**한 결과
> `count = int(np.sum(np.abs(perm) >= abs(delta_obs) - _EPS))` — `np.abs(perm)` 와 `abs(delta_obs)` 가 **둘 다 존재**한다.
> `_EPS` 실측값 = **1e-12** 이고, 임계에서 이를 **빼는** 방향이라 조건이 더 쉽게 참이 되어
> **카운트 증가 → p 증가 → 보수적**이다(부등호 `GtE` 까지 코드에서 직접 확인).
> 국문 정본 `docs/55b`:195 도 `양측 p = `(1 + #{|Δ*| ≥ |Δ_obs|}) / (B + 1)`.` 로 절댓값이 있다.
> → **`code_defect: false` · `document_only: true` · `scope: english_recipient_copy_only`**,
> 이미 산출된 ②③⑤⑥⑦ 의 p-값은 **영향 없음**. `signflip.py` 는 **0바이트 수정**(확인만).

> **(4) 채택 결정 D1~D22 와 실측 재확인 3건**
> `v3_Multimodal/config/rqint_procedure_decisions_v0.json`(sha256 `951b302a2d474361`)에 D1~D22
> **22건** · R1~R6 **6건**을 기록했다. **이 파일은 SAP 1.2 가 아니다** —
> `status: decisions_recorded_not_frozen` · `is_sap_freeze: false` · `sap_version_at_record: "1.1"`.
> cowork 표를 그대로 믿지 않고 3건을 실측했다 — **D10** 교환 단위 scaffold group 수는 확증 3반복
> `split_manifest.json` 전건 **732** 로 동결값과 일치(`already_satisfied`) · **D18** 대표폴드 재현 명령을
> 실제로 실행해 **`[4, 1, 0]`** 재현(`already_satisfied`) · **D20** `manifest.json` 의
> `"RF primary confirmatory (RF-Morgan+seq)"` 출현 **14곳**(횟수만 기록, **수정 0** — erratum 은 SAP 1.2 동결 블록).

> **(5) 확정 1건 · 사전 명시 2건 · 미확정 5건**
> **확정** = 예비 학습시드 **`[3, 4]`**(순서 포함). `gin_seed_freeze.json`
> `training_seeds_ordered = [42,1,2,3,4]` 의 **미사용 접미부를 기계적으로 취한 것**이며 신규 추첨·신규
> 선택 **0** 이고, 이 리스트는 GIN 학습 **0회** 시점(2026-08-05 16:51)에 이미 순서까지 동결돼 있었다.
> `stability_seeds` 와 3·4 가 겹치는 것은 데이터 재사용이나 검정 중복이 아니라 동일 난수 초기화값
> 사용일 뿐이므로 수용하되, **`stability_analysis_is_independent_replication: false`** 를 함께 적었다.
> **사전 명시 2건**(재문의 없이 우리가 회신 문면의 공백을 메움, `resolution_mode:
> pre_specified_reading_of_reviewer_condition` · `escalated_to_reviewer: false`) —
> **Y1** "2개 이상 교체" 의 계수 단위 = **실패한 원 확증시드의 수**(해석 ②를 취하면 예비목록 두 번째
> 항목 `4` 가 구조적으로 도달 불가가 되어 회신 §9-3 자신의 "순서까지 동결" 지시와 모순되므로 ①이 유일
> 정합 독법) · **Y2** R1 실패 시 폴백은 **판정하지 않는다**(후보 C 회귀 + 크기 추정치 탐색적 보고 +
> Holm 슬롯 `p = 1.0`, 가족 크기 7 유지 — 회신 §4-3 에서 연역되며 **우리가 임계값을 새로 만들지 않는다**).
> 두 건 모두 **GIN 학습 0회 · R1 감사 0회 시점에 기록**하므로 관측에 조건부인 사후 선택이 아니다.
> **★ R1 이 실제 실패하면 폴백 적용 전 검토자 재자문 의무**(`on_r1_failure_reconsult_reviewer: true`) —
> 회신 §6-2 R1 이 실패 시 "본 승인은 무효" 라고 명시했기 때문이다.
> **미확정 5건**(추측 기입 0) = Y1·Y2(우리 사전 명시로 종결) · **B 의 값과 정의**(권고 100,000, 드라이런
> 24h 초과 시 50,000 — 동전벡터 수인지 총 배치 수인지도 미확정) · **C0~C3 복제 수**(계측 이후 확정,
> 결과 보고 정하는 것 금지) · **R3 제2자 수행 주체**. **B 와 C0~C3 두 건은 R1 감사 착수를 막는다**
> (`blocking` 필드 명시).

> **(6) 우리가 놓쳤던 사항 — §5-1 Holm 이중보고**
> 회신 §5-1 은 RQ-int 를 구현하면 **나머지 6개 가설의 Holm 조정 p 가 약하게 작아진다**고 지적하고
> 이는 중립적 변경이 아니므로 **(A) 구현 p / (B) p=1.0 폴백 두 판을 모두 보고**하라고 요구했다(= D14 = R4).
> 이는 **우리 요청 문서가 다루지 않은 사항**이며 SAP 1.2 문언과 원고 양쪽에 반영해야 한다.

> **(7) `sign_disclosure_matrix.json` `decisions_after` 2분할 — 판정 불변**
> 현 값은 `"none — 부호를 근거로 한 설계·성공기준 변경 0."` 로 한정어가 붙어 있으나,
> **한정어 없는 맨 `"none"` 1건**이 `rows[0].disclosure_routes[1]`(`public_repository_pushed`)에
> 있음을 러너가 전 경로 객체 스캔으로 실측했다. 부호 노출(2026-07-27) **이후에 실제로 발생한 결정**이
> 존재하므로(RQ-int 절차 신설·외부 통계검토 의뢰·검정력 사다리·2026-08-05 시드·대표폴드 동결 등)
> 필드를 `none` 으로만 읽으면 반례가 생긴다. → **원 문자열은 바이트 그대로 보존**하고 경로 객체마다
> `decisions_after_enumerated`(노출 시각을 절단점으로 한 결정 목록)와 `evidence_of_influence`
> 두 키만 **superseding append** 했다. 열거는 cowork 목록을 베끼지 않고 `ledger.json` timeline 과
> `docs/33` 기입 시각 스탬프에서 **기계 수집**했다. `advisor` 경로는 노출 시각이
> `unknown_as_of_2026-08-06` 이라 절단점이 없어 **미판정**으로 두었고, 반복1 의 공개저장소 경로는
> **미공개**라 해당 없음이다. **판정("부호를 근거로 한 설계·성공기준 변경 0")은 바뀌지 않았다** —
> 바뀐 것은 그 판정을 뒷받침하는 **서술의 정확성**뿐이다.

> **(8) 서신·상신 기록**
> `correspondence` 에 **6건 append**(2026-08-12 스레드 `<GMAIL-MSGID>` 5건 + R3 상신 신규 스레드
> `<GMAIL-MSGID>` 1건). 확정 3건 = ① 정정 통지는 **서명 요청 문서에 합침**(별도 재발송 아님)
> ② 서명 요청본 **국문 본문 그대로 제출 가능** ③ 회수 경로 = 교수님 전달 → 서명 → 회신.
> **`forwarded_at`(검토자 전달 시각)은 `unknown_as_of_2026-08-12`** — "전달 드리고" 는 예정 표현이고
> 완료 통보가 없다(추측 기입 0). **R3 제2자 상신은 2026-08-12 14:48:48 KST 에 실제 발송**됐다
> (메시지 `<GMAIL-MSGID>`). 초판 지시서가 `not_yet_escalated` 로 적은 것은 11:05 발송본 기준으로는
> 정확했고 그 사실도 **이력 레코드로 보존**했다 — `open_question.r3_second_party` 는 **이력·현행
> 2레코드**이며 현행에 `supersedes` 포인터를 넣었다(블록 W 결손 재발 방지). 초안↔발송본 차이 **6건은
> 전부 문면**이고 실질 변경 0 이라 `escalation_substantively_complete: true` 이나, **수행 주체 확정은
> 미완**이므로 `still_unspecified` 에서 빼지 않았다(`escalated: true` · `resolved: false`).
> `external_reviews` 는 **3 → 6**(round 4 `docs/50` **누락 보충** + round 5 `docs/88` + <EXTERNAL-REVIEWER> 박사)이며
> 기존 3항목은 **객체 단위 무수정**(type 소급 부여 금지). 5차 회신은 **접수·분류 사실만** 기록하고
> 버킷 A 채택 확정은 SAP 1.2 동결 블록으로 미뤘다. 충돌 2건 = **X1** BCa 유효 replicate 임계 게이트
> **신설 안 함**(A7 은 이미 동결·사용된 모듈이라 판정규칙 신설은 부호 인지 후 변경) · **X2** R1 실패
> 폴백은 <EXTERNAL-REVIEWER> §10 대로 **후보 C 회귀**(ChatGPT 대안 기각, 판정규칙은 Y2 사전 명시로 충당).

> **(9) cowork FACTS 결함 2건(정직 고지)**
> ① `docs/86` §1 은 `docs/33` 마지막 항목을 **42**(다음 43)로 적었으나 실측 마지막은 **44**
> 이다(블록 AC 항목43 · 블록 AD 항목44 가 그 뒤에 추가됨). 중단 조건 규정대로 중단하지 않고 실측값
> **45** 으로 진행했다. ② 종료검증 **#6 은 `external_reviews` 3→6**, **#11d 는 3→5** 로 서로
> 다르다. cowork 자기고지대로 정본은 **6** 이며 #11d 의 5 는 AB-2-6 구간 부분합이다.

> **(10) 한계 — 본 기입은 어떤 착수 허가도 아니다**
> **GIN 학습·착수 차단 유지**(`gin_start_still_blocked: true`) · **개봉 0**(`unblinding_performed`
> false) · **RQ-int 구현 확정 0** · **SAP 1.2 재동결 0** · **`B` 확정 0** · **`model_family` 정정 0**.
> 서명본 회수는 본 블록 이후 사안이며(블록 AH · `docs/95`), R1 감사 실행도 별도 블록이다.

> 지시서 = `docs/86_rqint_reviewer_response_record_prompt_for_vscode.md`(초판 + AB-5) ·
리포트 = `docs/86_rqint_reviewer_response_record_report.md` · 회신 원본 =
`docs/RQint_Reviewer_Response_<EXTERNAL-REVIEWER>_20260810.docx`(sha256
`0c29ddf201eb6751`) · 대응표 = `docs/84` ·
신규 = `v3_Multimodal/config/rqint_procedure_decisions_v0.json`(sha256 `951b302a2d474361`, **동결 아님**) ·
무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1**) ·
`signflip.py` sha16 `3de1223585ae0f97`(**0바이트**) ·
`ladder_freeze.json` sha16 `b885585aefbabb32` ·
`gin_seed_freeze.json` sha16 `10828447c6d33118` ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**. **미실행**: 계산·재계산 ·
모델 학습·추론 · Δ/AP/CI/p/부호 산출 · `emit_sign` · `decision.py` 호출 · 개봉 · `open_sealed` ·
봉인 판독·쓰기 · RQ-int 구현(검정 함수·순열 루프·합성 데이터 생성기) · SAP 1.2 재동결 · `B` 확정 ·
`model_family` 정정 · GIN 학습·착수 · Gmail 재조회(네트워크) · `data/raw/` 변경 · git commit·push.
기입 시각 2026-08-14 13:53:25 KST.

---

46. **검토자 서명본 접수 · 신원 확정 해소 · amendment 빈칸 값 확정 (블록 AH — 기입 전용)**:

   - **① 무엇을 접수했나**: **2026-08-13 15:31:31 KST** 교수님 경유로 **<EXTERNAL-REVIEWER> 박사 서명본**을 수령했다(Gmail 메시지 `<GMAIL-MSGID>` · 스레드 `<GMAIL-MSGID>` · 본문 축자 「연우씨. 연구원 서명 받은 파일 송부 드립니다.」). 파일 = `docs/RQint_Reviewer_Record_Signature_20260812_SIGNED.pdf`(sha256 `161dd9d2290df32b…` · 146,939 B). 우리 회신 = `<GMAIL-MSGID>`(2026-08-14 12:58:46 KST). 서명 요청 발송은 `<GMAIL-MSGID>`(2026-08-12 11:48:38 KST · 첨부 **`.docx`**).
   - **② 서명 실측(러너 독립 재확인)**: 2쪽 「서명 / Signature」 란에 PDF 이미지 XObject **206×97 · DeviceRGB + SMask(= RGBA)** 가 존재하고, **발송본(`.docx`)의 내장 이미지는 0장**·**발송 전 PDF 의 이미지도 0장**이다. **서명 일자 축자 = 2026-08-12.** 발송본 ↔ 서명본 본문은 공백 제거 정규화 후 **접미 1,111자 일치**(미해독 문자 115자는 대조 제외) → §3 참고 3건·§4 향후절차 **무수정 = 검토자 이의 0건**.
   - **③ 신원 해소의 귀속(멱등)**: `external_reviewer_identity: unknown_as_of_2026-08-06` 의 해소는 **블록 AB(2026-08-14 13:53)가 이미 수행**했다(`ledger.timeline[42].run_facts.external_reviewer_identity_resolved` — 신원·소속·검토일·판정). 본 블록은 지시서 §머리말의 멱등 규약대로 그 위에 **서명 사실만** 얹었다 — **`external_reviews` 항목 추가 0**(live 실측 6건 유지 · <EXTERNAL-REVIEWER> entry 는 인덱스 5 에 이미 존재) · **기존 객체 수정 0**. AB 가 남긴 `signature_status = pending_as_of_2026-08-12` 를 신규 timeline entry 가 **superseding append** 로 해소하며, 원 문자열 `unknown_as_of_2026-08-06` 두 곳(`timeline[32]`·`[35]`)은 **바이트 보존**한다.
   - **④ amendment 빈칸 값 확정 — 문면 동결 아님**: `[DATE]` = **2026-08-10** · `[NAME]` = **<EXTERNAL-REVIEWER>** · `[DEGREE]` = **Ph.D.** · `[AFFILIATION]` = **Gyeongnam Intelligence Innovation Center (GIIC)**. ★ `[DATE]` 는 **승인일(Date of review)** 이며 **서명일 2026-08-12 가 아니다** — 회신 원본이 표지 **08-10** / 부록 B **08-06** 으로 달라 우리가 표지 기준 08-10 으로 통일하고 *"08-06이 맞다면 아래 표를 수정해 주십시오"* 라고 명시했는데 **서명본에서 수정되지 않았다**. 두 리터럴을 모두 보존한다. 신규 파일 = `v3_Multimodal/config/reviewer_identity_resolved.json`(`freeze_status` = `values_confirmed_not_frozen` · `frozen_by` = `pending_R2_SAP_1_2` · **SAP 등재 모듈 아님** · `manifest.json` 0바이트 수정).
   - **⑤ 문면 차이 3건 귀속**: SIGNED 와 발송 전 PDF 사이 텍스트 차이 3건(**영문 부제 삭제** · **"저희가 기입"→"기입"** · **"일자만"→"일자를"**)은 **연구자 본인이 발송 전에 편집**한 것이고 `.docx` 가 이미 편집 후 상태다. 러너가 `word/document.xml` 로 독립 재확인했다(영문 부제 **부재** · **"일자를 채워" 존재**). 따라서 발송본과 서명본의 본문은 동일하고 **정정 대상 기록은 없다**. 발송 전 PDF 는 편집 전 산출물로 보존한다.
   - **⑥ 조회 규약 확립(신규)**: `search_threads` 의 메시지 목록은 **전수가 아닐 수 있다** — 같은 스레드 `<GMAIL-MSGID>` 를 search 는 **5건**, `get_thread` 는 **7건** 반환한다(러너 재실측 **7건** 확인). 앞으로 Gmail 실측은 **스레드 ID 확보 후 `get_thread` 로 재확인한 값만** 원장에 기입한다.
   - **⑦ 블록 AC·AD timeline entry 보충 2건**: `docs/33` 항목43·44 와 `docs/45` 문서 이력에는 있으나 `ledger.timeline` 에 전용 entry 가 없던 것을(블록 AB 러너 상신 ②) 본 블록에서 append 했다. 출처는 `docs/89`·`docs/90` 리포트 **실측만**이고, **소급 날짜 기입 0** — 각 entry 에 `recorded_at`(본 블록 기입 시각)과 `event_at`(리포트 실측 시각)을 **분리 기재**했다(블록 S 선례). 기존 43 entry 는 **객체 단위 무수정**. 결과 `timeline` **43 → 46**(AC·AD 2건 + 본 블록 1건).
   - **⑧ 러너 편차 4건(정직 고지)**: **AH-DEV-1** `docs/86` 배너를 AH-4 의 「맨 위」가 아니라 **파일 말미**에 append 했다 — §7-8 의 「초판 바이트 접두사 동일」과 동시 성립이 불가능하고, 기계 검증 가능한 접두사 보존을 택했다(블록 V `docs/72` 말미 배너 선례 · AB 는 이미 수행돼 가시성 목적 소멸). **AH-DEV-2** `timeline` 최종 길이는 AH-5(+1)와 §7-10b(43→45) 를 모두 만족하는 **46** 이다(§7-10b 의 45 는 본 블록 자신의 entry 를 세지 않은 부분합). **AH-DEV-3** §1-1 ★ 조회 규약이 요구한 FACTS 1-1 재확인을 위해 Gmail `get_thread` 를 **1회(읽기 전용)** 호출했다 — 첨부 **재다운로드 0** · 발신 0 · 변경 0 · 그 외 네트워크 0. **AH-DEV-4** 서명 이미지 **7,156 B** 는 PNG 재인코딩 산물이라 인코더 의존적이어서 **독립 재현 불가**로 남긴다(러너 재인코딩 5,514 B / 5,305 B) — 화소 규격 **206×97 · RGBA** 만 PASS 로 판정했다.
   - **⑨ 한계 — 본 기입은 어떤 착수 허가도 아니다**: **SAP 1.2 재동결 0** · **amendment 문면 동결 0** · **개봉 0**(`unblinding_performed` false) · **GIN 착수 차단 유지**(`gin_start_still_blocked` true) · **R1 캘리브레이션 감사 0** · **R3 이행 0** · **`B` 확정 0**.

> 지시서 = `docs/95_reviewer_signature_receipt_prompt_for_vscode.md` · 리포트 = `docs/95_reviewer_signature_receipt_report.md` · 서명본 = `docs/RQint_Reviewer_Record_Signature_20260812_SIGNED.pdf`(sha256 `161dd9d2290df32b`) · 발송본 = `docs/RQint_Reviewer_Record_Signature_20260812.docx`(sha256 `bfb01bfeae87ee3b`) · 발송 전 PDF = `…20260812.pdf`(sha256 `8316c56230b3ccd0`, 미발송 보존) · 회신 원본 = `docs/RQint_Reviewer_Response_<EXTERNAL-REVIEWER>_20260810.docx`(sha256 `0c29ddf201eb6751`) · 신규 = `v3_Multimodal/config/reviewer_identity_resolved.json`(**동결 아님** — `freeze_status` `values_confirmed_not_frozen`) · 무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · 블록 AC 산출 4파일 **0바이트** · sealed guard **275종(access.log 제외) / 291종(포함) 불변**. **미실행**: 계산·재계산 · 모델 학습·추론 · Δ/AP/CI/p/부호 산출 · `emit_sign` · `decision.py` 호출 · 개봉 · `open_sealed` · 봉인 판독·쓰기 · SAP 1.2 재동결 · amendment 문면 동결 · `external_reviews` 항목 추가 · `B` 확정 · R1 감사 · R3 이행 · GIN 학습·착수 · 첨부 재다운로드 · `data/raw/` 변경 · git commit·push. 기입 시각 2026-08-14 14:51:14 KST.

---

47. **R3 제2자 확정 · 합격기준 사전명시 (블록 AG — 트리거 사건 이전 기입)**:

   - **① 제2자 = <SECOND-PARTY> 확정**: **2026-08-12 18:34:47 KST** 교수님 승인(Gmail 메시지 `<GMAIL-MSGID>` · 스레드 `<GMAIL-MSGID>` · 본문 축자 「네 <SECOND-PARTY>씨에게 부탁해서 처리하시죠.」). 상신 = `<GMAIL-MSGID>`(2026-08-12 14:48:48 KST), 우리 수신확인 = `<GMAIL-MSGID>`(2026-08-12 19:19:31 KST). 실제 요청 발송 = `<GMAIL-MSGID>`(2026-08-14 14:26:28 KST · **신규 스레드** `<GMAIL-MSGID>` · 첨부 없음 · 발송 실측 대장 `docs/96`). 제2자 회신은 **미수령**(2026-08-14 15:12 KST `get_thread` 실측 — 스레드 메시지 1건 = 우리 발신분뿐).
   - **② ★ 승인의 범위**: 교수님이 승인한 것은 **수행 주체가 <SECOND-PARTY>이라는 것뿐**이다. **합격 기준 · 게이트 G-ENV · `numeric_core` 제외 목록 · 패키지 구성 · 일정은 승인 대상이 아니며 우리 내선 결정**이다. 이 구분을 흐리지 않는다.
   - **③ ★ 철회 여지 문장의 삭제(`docs/96` §2 #6)**: 초안(`docs/92`)에 있던 「혹시 일정이 부담되시거나 더 적절한 분이 계시면 편하게 말씀해 주십시오.」가 **발송본에서 빠졌다**(초안↔발송본 차이 7건 중 **유일한 실질 삭제**, 나머지 6건은 문체). 즉 제2자는 **<SECOND-PARTY>으로 사실상 확정 요청된 상태**이고, 교체가 필요해지면 **교수님 재상신** 경로만 남는다 — 우리 임의 교체는 불가하다.
   - **④ 합격기준 2단 — 트리거 사건 이전 동결**: 트리거 사건 = **제2자 산출물 회수**이며 동결 시각(**2026-08-14 15:12:46 KST**) 기준 **미발생**이다. **1차** = 정규화 비교객체 `numeric_core` 의 sha256 **바이트 동일** → R3 충족. **2차** = 1차 불일치 시에만 발동하며 게이트 **G-ENV**(`python_version`·`numpy`·`sklearn`·`machine`·BLAS 구현 중 **1개 이상 상이**로 환경 상이 입증)를 **먼저** 통과해야 한다. 게이트 통과 시 판정 불리언(R6-1~R6-9 각 pass·`r6_all_pass`·`synthetic_only`·`confirmatory_data_accessed`·`unblinding_performed`·`gin_start_still_blocked`)·이산량(형상 N·K·G·시드·`n_coin_vectors`·`n_permutation_values`·count·완전열거 2^8 개수)·문자열(`sap_version`·모듈 sha256·`B_definition_status`)은 **완전일치**, 연속량(macro AP·Δ_RF·Δ_GIN·`T_obs`·`T*` 수열·`p_exact`·`p_mc`·`mean(p)`·KS)은 **상대오차 ≤ 1e-9**. ★ **환경이 전부 동일한데 산출이 다르면 2차 판정 금지** → 즉시 중단·원인 규명 후 재자문(동일 환경 불일치 = 코드 비결정성이며 허용오차로 덮을 사안이 아니다). **2차도 실패 시 R3 미충족 확정** + 교수님·<EXTERNAL-REVIEWER> 박사(GIIC)께 보고, **임의 3차 기준 금지**.
   - **⑤ 1e-9 의 근거**: `macro_ap` 는 `average_precision_score` 의 산술평균이고 순열 통계량은 그 차의 차이다. float64 누산 순서 차이(BLAS 구현·SIMD 폭)의 오차는 항목당 상대 1e-15 규모이며 K·G 규모 누산을 거쳐도 1e-12 를 넘기 어렵다 → **1e-9 는 3자리 느슨한 상한**으로 "플랫폼 차이는 통과, 실질 계산 차이는 포착"에 부합한다. p-값은 동일 시드 → 동일 동전 벡터라 **결정적**이므로 별도 MC 허용오차를 두지 않는다(두면 실질 차이를 덮는다).
   - **⑥ 비교객체 `numeric_core` 사전 고정**: 제외 **규칙 6항 / 구체 JSON pointer 8개** — `/run_at_kst` · `/wall_clock_seconds` · `/timing/per_permutation_seconds` · `/timing/per_reference_value_seconds` · `/versions` · `/_doc` · `/block` · `/instruction`(+ 확장 슬롯 1항은 **비워 둠** = 지금 고정된 제외는 규칙 1~5 뿐). 포함은 `/r6` 전체 · `/r6_all_pass` · `/code_scan` · `/import_topology` · `/text_checks` · `/d6_conditionality_keys` · 4개 불리언 · `/sap_version_unchanged` · `/timing` 의 형상·개수 필드. 정규화 직렬화 = `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")` **축자 고정**이며 이후 변경은 amendment 대상이다.
   - **⑦ 신규 파일**: `v3_Multimodal/config/r3_second_party_freeze.json`(sha256 `0624d3ddb852c4e9` · `resolution_mode` = `pre_specified_before_trigger_event` · **SAP 등재 모듈 아님** · `manifest.json`·`freeze.py` `MODULE_FILES`·`sap/__init__.py` **0바이트**).
   - **⑧ 한계 — 본 기입은 어떤 판정도 아니다**: **R3 판정 0** · **R3 이행 0** · **SAP 1.2 재동결 0**(`sap_version` 1.1 · manifest sha16 `756d485feb4715e9` 불변) · **`B` 확정 0** · **개봉 0**(`unblinding_performed` false) · **GIN 착수 차단 유지**(`gin_start_still_blocked` true).

---

48. **R3 프로브 패키지 산출 · 해시 · 미이행 목록 (블록 AG — 종료 후 기입)**:

   - **① 패키지**: `experiments/rqint/r3_package/` **19파일** · zip `experiments/rqint/r3_package.zip` sha256 `fcbcaeea6c6158de` (72,281 B · 결정적 zip = 고정 타임스탬프·고정 순서). 구성 = `README_R3.md` · `requirements_probe.txt` · `run_rqint_probe.py`(신규) · `canonical.py`(신규) · `collect_env.py`(신규) · `sap/` **14파일 복사본**(동결 11모듈 + rqint 3모듈). 복사원 원본 14파일 sha256 **착수=종료 동일**(0바이트 수정), 복사본도 원본과 **바이트 동일**.
   - **② 프로브 규격·실측**: 규모 **N=60 · K=8 · G=12 · `n_coin_vectors`=64**(지시서 지정 그대로 — 예산 초과가 없어 **축소 불필요**). 우리 Mac 벽시계 **7.8초**(재실행 7.62초, 예산 60초). 입력 **100% 합성** — `sap.rqint_synthetic` 의 **기존 fixture 생성기 재사용**(재구현 0). 시드는 `run_rqint_audit.py` 리터럴을 그대로 취했다(**새 추첨 0**) — fixture zero=11 · exchangeable=12 · timing=99, 검사 시드 **R6-n → n**(원 스크립트 자체 관례 계승). R6 **부분집합 6항**(R6-1·R6-2·R6-5·R6-6·R6-7·R6-9) **전항 PASS**. 제외 3항 = **R6-3**(균등성 R=200 → 예산 초과) · **R6-4**(합격기준 `draws_checked >= 1000` 이 **규모 의존** — 기준 완화 금지이므로 미실행) · **R6-8**(2^G=4,096 전수열거 → 예산 초과) → **R3 본 드라이런에서 전항 실행**한다.
   - **③ `numeric_core` 결정성 실측**: 동일 기계 2회 실행에서 `numeric_core_sha256` **동일**(`3745438643aa1c53…` · canonical bytes 12,774 · 적용된 제외 pointer 8개). 이것은 비교 스킴이 우리 쪽에서 안정적임을 보인 것일 뿐 **R3 판정이 아니다.**
   - **④ ★ 기대 해시 미동봉**: 패키지 내 기대 해시 파일 **0건**. 우리 프로브 산출물(`probe_result_local.json`·`probe_numeric_core_local.sha256`·`probe_run_local.log`)과 우리 환경 명세(`env_local.json`)는 **패키지 밖** `experiments/rqint/r3_package_meta/` 에 둔다 — 제2자가 우리 값을 보고 맞출 이유를 만들지 않기 위함이다.
   - **⑤ PII redaction**: `collect_env.py` 는 hostname 을 **원문 저장하지 않고** sha256 앞 12자리(`host_id`)만 쓰며 파일명도 `env_<host_id>.json` 이다. 절대경로형 문자열(`/Users/`·`/home/`·`/root/`·`C:\\Users`·`/var/folders/`)은 `<path-redacted>` 로 치환한다(`docs/56` 규칙). 우리 기준 명세 = `host_id` `89be108a4c00` · Python **3.14.4** · numpy **2.5.0** · sklearn **1.9.0** · scipy **1.18.0** · `macOS-26.5.2-arm64-arm-64bit-Mach-O` · cpu 18.
   - **⑥ 확증 데이터 미접근 증명(3층)**: **S1**(동결 `freeze.py code_scan` 동일 규칙 — 금지 import · data-load call · `open()` 경로 리터럴) = **0건**(19파일 중 .py 17파일 스캔). **S2**(비-docstring 문자열 상수 어휘) = **50 hit / 7파일** 이며 전건 분류 완료 = ㉠ 스캐너 자신의 금지어 목록(`freeze.py` 22 + `run_rqint_probe.py` 17 = 39) ㉡ 라벨 문자열(`decision.py` 7 = "RF primary confirmatory (RF-Morgan+seq)") ㉢ 주석성 note(`metrics.py`·`unseen_target.py`·`consensus.py` 각 1) ㉣ **sealed 쓰기 API 의 경로 조립 1건**(`redaction.py`:51 `os.path.join(run_dir, "_sealed")` — 호출자가 `run_dir` 을 넘겨야 하고 프로브는 이 모듈을 **import 하지 않는다**). **S3 런타임 증명** — 프로브가 실제로 로드한 `sap` 하위 모듈은 `consensus`·`metrics`·`rqint`·`rqint_audit`·`rqint_synthetic`·`signflip`·`synthetic` **7종뿐**이며 `redaction`·`freeze`·`bootstrap`·`decision`·`null_generator`·`unseen_target` 는 **미로드**다(`probe_result_local.json` `sap_modules_imported_at_runtime`).
   - **⑦ 원장**: `ledger.json` `timeline` **46 → 47**(본 블록 entry 1건) · `correspondence` **19 → 22**(+3) · `authoritative_sources` **22 → 24**(`docs/91`·`docs/96` 등재) · **`first_look_register` 6 불변** · 최상위 키 **11 불변** · `timeline[:46]`·`correspondence[:19]` 직렬화 **완전 일치**(기존 객체 무수정).
   - **⑧ 편차 자진신고 2건**: **AG-DEV-1** 지시서 AG-6 은 `correspondence` **19→23(+4)** 를 지시했으나 실측 결과 4항목 중 **질의(`<GMAIL-MSGID>`)는 이미 `correspondence[16]` 에 존재**했다(블록 AB 기입분). 같은 Gmail 메시지의 중복 entry 를 만드는 것은 원장 무결성 훼손이므로 **+3 만 append** 하고 최종 **22** 로 두었다. 대신 승인 entry 에 `supersedes` 포인터를 달아 기존 항목의 `advisor_reply: none_as_of_2026-08-12` 를 **superseding append** 로 해소했다(원 객체 바이트 보존). 블록 AH 의 `AH-DEV-2`(부분합↔최종값 혼동)와 **같은 계열의 FACTS 오차**이며 정정 방향은 반대다(과다계상). **AG-DEV-2** 종료검증 §7-8 의 「`data/`·`_sealed/`·`master_`·`oof_` 참조 문자열 스캔 0건」은 **동결 11모듈을 원본 그대로 동봉하는 한 달성 불가**다(위 ⑥ 참조) — 동결물 0바이트 수정 원칙이 상위이므로 모듈을 손대지 않고, 대신 **S1 = 0건**(운용 기준)에 S2 전건 분류 + S3 런타임 미로드 증명을 덧붙였다.
   - **⑨ ★ 미이행 목록(본 블록이 하지 않은 것)**: **R3 판정 0** · **R3 이행 0**(프로브는 플랫폼 적합성 확인 전용이며 판정에 쓰지 않는다) · **R1 캘리브레이션 감사 0**(블록 AF 는 `C0:prop` 1,440/2,000 에서 중단 상태 유지) · **전규모 드라이런 0** · **R2(SAP 1.2 재동결) 0** · **`manifest.json`·`freeze.py`·`sap/__init__.py` 무수정** · **`B` 확정 0** · **개봉 0**(`unblinding_performed` false) · **`emit_sign` 0** · **`open_sealed` 0** · **`decision.py` 호출 0** · **GIN 학습·착수 0**(`gin_start_still_blocked` true) · **확증 데이터 로드 0** · **`data/raw/` 변경 0** · **제2자 회신 회수 0**(미수령) · **패키지 발송 0**(발송 시점은 R2 완료 이후) · **git commit·push 0**.

> 지시서 = `docs/91_r3_second_party_prep_prompt_for_vscode.md` · 리포트 = `docs/91_r3_second_party_prep_report.md` ·
신규 = `v3_Multimodal/config/r3_second_party_freeze.json`(sha256 `0624d3ddb852c4e9` · **동결 파일이나 SAP 등재 아님**) ·
`experiments/rqint/r3_package.zip`(sha256 `fcbcaeea6c6158de`) · 발송 대장 = `docs/96_<SECOND-PARTY>_mail_r3_SEND_20260814.md` ·
무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) ·
블록 AC 산출 4파일 **0바이트**(`eb842bc98140e9c5`·`27ef0011ee041920`·`ddffe6d128de4d18`·`ab831c2726a36e8a`) ·
`ladder_freeze.json` `b885585aefbabb32` · `gin_seed_freeze.json` `10828447c6d33118` ·
`post_interim_freeze_v1_0.json` `502db732bd5e45cb` ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 착수=종료 `diff` 무출력) ·
HEAD `566f487` 불변 · 커밋 수 **21** 불변. **미실행**: 위 ⑨ 전항. 기입 시각 2026-08-14 15:12:46 KST.

---
49. **R1 캘리브레이션 감사 C0~C4 (블록 AE·AF — 본런, 합성 예측 전용)**:

   - **① 동결일 / 기입일 분리(소급 기입 0)**: 설계 **동결일 = 2026-08-12 22:25:21 KST**(`experiments/rqint/calibration_design.json` · sha256 `42e2f8f9f3f24ec1…` · 사이드카 `calibration_design.sha256.json` 와 3자 일치 · 착수=종료 불변). **기입일 = 2026-08-18 12:03 KST**(본 항목). 동결 시각 < 첫 시뮬레이션 시각(**2026-08-12 22:46:44 KST**, `calibration_sessions.jsonl` `design_frozen` ↔ 첫 `session_start`)을 로그로 증명한다. **동결 이후 설계 변경 0** — 복제 수·순열 수·τ 격자·주입법·판정 지점·합격기준 전부 불변이며 본런 중 재보정 0.
   - **② 중간 보류·중단 세션이 있었다는 사실**: 본런은 한 번에 이어지지 않았다. **보류 2건** = ⓐ 2026-08-12 AC 전원 미연결로 `docs/93` 을 보류(게이트 18/18 PASS·동결 완료 상태로 정지), ⓑ 2026-08-14 22:0x KST `/재개` 호출 시 배터리 13%·방전·`powermode 1` 이 실측돼 **착수 게이트 1에서 거부**(`--allow-battery` 미사용 — 스모크 전용이므로 본런 우회 0). **`/중단` 4건** = 2026-08-13 08:07:37(C0:prop 1,440) · 2026-08-13 17:35:57(C0:prop 1,512 — **45W 어댑터가 18워커 부하를 감당하지 못해 AC 연결 상태에서 방전**) · 2026-08-13 23:30:35(C1:prop 215) · 2026-08-14 08:43:27(C1:prop 1,569). **유실 복제 0** — 재개는 전부 동일 `rep_seed` 로 이어져 중단 여부가 결과를 바꾸지 않았고, 스모크 시드 `20260813~16` 의 본런 재계산값은 계산필드 **전건 바이트 동일**(차이는 `pid`·`start_rel`·`end_rel`·`task_seconds`·`per_permutation_seconds`·`threads_limit` 운영 메타뿐)이다. 최종 완주는 2026-08-14 22:24:56 ~ **2026-08-18 11:55:10 KST** 구간의 무중단 11셀 순차 실행이다.
   - **③ AE-0 `G_eff/G ≈ 0.117` 도달불가 처리 4항(검토자 조건이므로 임의 대체 0)**: 전규모 목표 **0.116594** 는 N=400 에서 **수학적으로 도달 불가**이고 도달 가능 최소는 **0.13255**(격차 +0.01596, 블록 AD 전수 탐색 · cowork 독립 재탐색 동일 최적). 처리 = ⓐ **primary = 비례축소**(`F-PROF-P` · G=313 · `G_eff` 77.595 · `G_eff/G` 0.24791) — AD-4 프로파일 대조 6지표 중 **5개**가 전규모에 더 가깝다는 근거, ⓑ **sensitivity = 비율최적**(`F-PROF-R` · G=210 · `G_eff` 27.836 · `G_eff/G` 0.13255 · `Σm²` 5,748), ⓒ **합격 판정을 두 변형 모두에 적용**(완화 아님·강화), ⓓ 검토자 통지 문안은 서명본 회수 편 동봉 사안으로 **본 블록 범위 밖**(작성 0).
   - **④ 효과 주입 5요소(A11) — 동결대로 이행**: ⓐ **방식** = 합성 점수행렬의 **logit 척도 상수 가산**(블록 AD `synth_common_effect` 계승), ⓑ **귀속** = C1·C2 는 양 family M2b arm 에 공통 δ(`E[T]=0`) / C3 는 GIN 두 arm 동일 하향(`Δ_GIN` 불변 assert 통과, 실측 `mean_delta_rf` 0.000065 · `mean_delta_gin` −0.000061 로 `E[T]=0` 구조 확인) / C4 는 RF M2b arm 에만 τ(부호 + 고정), ⓒ **동질 주입**(전 PT·전 scaffold 군 동일 상수 — 이질 주입 사후 도입 0), ⓓ **tie 처리** = jitter 0·난수 tie-break 0이며 실측 tie 율 **전 11셀 0.00**, ⓔ **슬롯 매핑** = `sap/rqint.py` 인터페이스 그대로 + 합성 자가시험 통과(`mean_T` 0.101802 vs 기대 0.10, `sign_ok` true). 규모별 보정계수 **분리** 유지 — 축소 slope 0.503095(AD-5 0.500237 대비 비 1.00571) / 전규모 slope 0.574723(AD-4-4 0.591611 대비 비 0.97145).
   - **⑤ ★ AF-0 #3 — 주입 기전이 "열별 상수 가산"인 근거(문면 은폐 0)**: 동결 문면은 가산 대상을 "**양성 라벨 원소**"라 적었으나 실제 구현은 `logit = strength·(y − colmean(y)) + N(0,1)` 이므로, 강도를 `base → base + d` 로 올릴 때 PT `j` 의 **양성 원소에 `+d·(1 − prev_j)`**, **음성 원소에 `−d·prev_j`** 가 각각 **열별 상수**로 가산된다. 즉 문자 그대로의 "양성에만 가산"이 아니라 **양성−음성 순분리가 정확히 `d`** 이며 이 값이 **전 PT·전 군에서 동일**하다. 따라서 A11 이 요구한 **동질 주입은 실질적으로 성립**하고, 귀무 구조(`E[T]=0`)와 검정력 해석도 그대로 유지된다. cowork 판정 3건(예산 140.03 h 수용 · 항목45 기입의 본 블록 이월 · 본 기전 수용)을 수용해 여기 명문화한다.
   - **⑥ 1종오류 — 3지점 기각률 + Wilson 95% CI(공식 판정은 α 지점 하나뿐)**:

     | 셀 | 역할 | R | α=0.05 기각률 | Wilson 95% CI | `α+2·SE` 상한 | α/7=0.0071429 | α/4=0.0125 | 판정 |
     |---|---|---|---|---|---|---|---|---|
     | C0:prop | primary | 2,000 | **0.0525** | [0.0436, 0.0632] | 0.059974 | 0.0085 | 0.0125 | pass |
     | C0:ratio | sensitivity | 1,000 | **0.0610** | [0.0478, 0.0776] | 0.065137 | 0.0070 | 0.0170 | pass |
     | C1:prop | primary | 2,000 | **0.0430** | [0.0350, 0.0528] | 0.059072 | 0.0105 | 0.0160 | pass |
     | C1:ratio | sensitivity | 1,000 | **0.0540** | [0.0416, 0.0698] | 0.064295 | 0.0070 | 0.0120 | pass |
     | C2:prop | primary | 2,000 | **0.0485** | [0.0399, 0.0588] | 0.059607 | 0.0075 | 0.0130 | pass |
     | C2:ratio | sensitivity | 1,000 | **0.0360** | [0.0261, 0.0494] | 0.061782 | 0.0030 | 0.0100 | pass |
     | C3:prop | primary | 2,000 | **0.0485** | [0.0399, 0.0588] | 0.059607 | 0.0035 | 0.0100 | pass |
     | C3:ratio | sensitivity | 1,000 | **0.0420** | [0.0312, 0.0563] | 0.062686 | 0.0050 | 0.0100 | pass |

     `SE = √(r̂(1−r̂)/R_sim)` 는 **관측 `r̂` 로 매번 계산**했다(상수 하드코딩 0). **보조 2지점에 임계 신설 0** — `auxiliary_points_exceeding` = `{}` 로 상신 사항 **0건**이다.
   - **⑦ C0 p 균등성(KS)**: `C0:prop` 통계량 **0.030086** · p **0.052447**, `C0:ratio` 통계량 **0.028560** · p **0.381263** — 둘 다 기준 `p > 0.05` 충족. 다만 **`C0:prop` 의 p 는 0.0524 로 기준 바로 위**임을 정직하게 기록한다(사후 완화·재실행 0).
   - **⑧ C4 검정력 곡선 3τ · A12**: τ=0.01 **0.2500** [0.2101, 0.2947] · τ=0.02 **0.7350** [0.6897, 0.7759] · τ=0.03 **0.9725** [0.9514, 0.9846](각 R=400 · 내부 순열 1,000). A12 중간판정(200복제) = τ0.01 0.260 [0.2041, 0.3249] `crosses_boundary` **false** · τ0.02 0.770 [0.7069, 0.8229] **true** · τ0.03 0.975 [0.9428, 0.9893] **false**.
   - **⑨ ★ 절차 이탈 자진신고 — A12 적응적 중지 미이행(AF-DEV-1)**: 동결 규칙은 "200복제 Wilson 95% CI 가 0.50·0.80 을 **가로지르지 않으면 해당 τ 중단**" 이고, 실측상 **τ=0.01·τ=0.03 은 `stop_at_interim` = true** 였다. 그러나 `rqint_calibration.py` 는 **A12 를 `--stage summary` 에서만 계산**하고 `--stage run` 에 중지 로직이 없어(코드 실측: A12 참조가 상수 정의·design 기입·summary 3곳뿐) **세 τ 전부 400 복제를 전수 수행**했다. 성격·영향 = ⓐ **설계 완화가 아니라 초과 수행**(예산 절감 규칙을 못 쓴 것이며 복제·τ·판정지점·합격기준은 불변), ⓑ **R1 합격 판정에 무영향** — C4 는 1종오류 시나리오가 아니어서 `F-ACC` 미적용이고 `r1_passed` 는 C0~C3 8셀로만 산출된다, ⓒ 복제는 사전 결정된 `rep_seed` 로 생성되므로 400 전수는 같은 모수의 **더 정밀한 추정**이며 적응적 중지 편향이 새로 들어오지 않는다, ⓓ **중간(200)·최종(400) 값을 둘 다 보존**해 어느 쪽으로도 재판정이 가능하다. **자체 구제 0** — 데이터 절단·재실행·규칙 개정 없이 사실만 기록한다. 예산 영향은 C4 실측 28.26 h(= 9.45+9.41+9.40)로, A12 가 이행됐다면 τ0.01·τ0.03 이 각각 절반 수준이었을 것이다.
   - **⑩ τ=0.02 의 D19 사다리 지위**: 사전지정 τ=0.02 의 검정력은 **0.735**(95% CI [0.690, 0.776])로 **0.50 이상**이다. 따라서 "τ=0.02 검정력 <0.50 이면 D19 사다리 **최하단 지위**를 그대로 채택" 이라는 사전동결 조항은 **발동하지 않는다**. 동시에 **0.80 에는 못 미치므로** 관례적 검정력 기준을 충족한다고 주장하지 않는다 — τ 격자 확대·복제 증가·SESOI 조정·판정규칙 변경은 전부 **미수행(금지 조항 준수)**.
   - **⑪ `r1_passed` = `true`**: C0~C3 의 **primary·sensitivity 두 변형 모두** α 지점 기각률 ≤ `α+2·SE` 이며 C0 KS 도 두 변형 모두 통과. `official_decision_point` = `alpha` · `fallback_applied` **false** · `reruns_after_fail` **0** · `seed_changes_after_fail` **0**. 독립 검증(A21 — 본런·`sap` 미import 별도 스크립트가 복제별 p 원값만 읽어 재계산) = `any_mismatch_vs_main_run` **false** · `design_unchanged_since_freeze` **true** · `all_ast_clean` **true**.
   - **⑫ 운용 실측**: 총 복제 **13,200**(prop 4×2,000 + ratio 4×1,000 + C4 3×400) · 총 벽시계 **107.11 h**(완주 세션 88.51 h + 중단 세션 18.60 h) = 동결 예산 **140.03 h 의 76.5%**(예산 재산출 0). 처리량 = 축소 셀 **145.7~170.4 rep/h** · 전규모 C4 **42.3~42.5 rep/h**(정의 `w / wall_max`, 평균 기반 0) · `W_BEST` 18 · threads/worker 1. **RAM peak 4.89~4.91 GiB(축소) / 7.31 GiB(전규모)** 로 게이트 임계 30.72 GiB 대비 여유, **`ram_gate` 브리치 0건 · `stopped_reason` 전 13 세션 `None`**. 전원 = 최종 완주 구간 전건 **AC(96W 어댑터 · `powermode 0` · `caffeinate -dimsu`)**, 배터리·저전력 구간 측정치는 예산·처리량 표에 **투입 0**. 여집합 항등식 감사 = **시나리오·변형당 정확히 1회**(11셀 × 1,000 draw · 실패 **0** · `max_abs_dev` **0.0**).
   - **⑬ 무결성 — 착수=종료 불변**: SAP 등재 **11모듈 0바이트** · `manifest.json` sha16 **`756d485feb4715e9`** · `sap_version` **1.1** · 블록 AC 산출 4파일 + 블록 AD 2파일 **0바이트** · `ladder_freeze.json` `b885585aefbabb32` · `gin_seed_freeze.json` `10828447c6d33118` · `sap/` 내 신규·수정 파일 **0건** · `_sealed/` guard **275종(access.log 제외) / 291종(포함)** 및 stat-only 스냅샷 sha256 **착수=종료 완전 동일** · HEAD `566f487` 불변. 본 블록이 만든 파일은 `_ckpt/calibration_*.jsonl` 11종 · `calibration_summary.json` · `calibration_verify.json` · `calibration_facts.json` · `calibration_sessions.jsonl` 뿐이다.
   - **⑭ ★ 본 기입은 어떤 착수 허가도 아니다**: **개봉 0**(`unblinding_performed` false) · **확증 예측·OOF 로드 0**(`confirmatory_predictions_loaded` false · `confirmatory_data_accessed` false · `sealed_accessed` false · 예측 **100% 합성**) · **SAP 1.2 재동결 0** · **`B` 확정 0**(`B_definition_status` = `still_unspecified`) · **GIN 학습·착수 0**(`gin_start_still_blocked` true) · **`emit_sign` 0** · **`decision.py` 호출 0**(`HOLM_FAMILY` 상수 판독 1건뿐) · **네트워크 0** · **`data/raw/` 변경 0** · **git commit·push 0**. R1 은 충족됐으나 R2(SAP 1.2 재동결)·R3(제2자 독립 재실행)·`B` 확정·개봉·GIN 착수는 **전부 차단 유지**다.

> 지시서 = `docs/94_r1_mainrun_with_ops_commands_prompt_for_vscode.md`(선행 `docs/93_r1_calibration_audit_prompt_for_vscode.md` — 보류 후 94 로 이어받음) · 리포트 = `docs/94_r1_mainrun_with_ops_commands_report.md`(중간) · `docs/94_r1_mainrun_with_ops_commands_report2.md`(완주) ·
동결 = `experiments/rqint/calibration_design.json`(sha256 `42e2f8f9f3f24ec1` · 동결 2026-08-12 22:25:21 KST) ·
산출 = `experiments/rqint/calibration_summary.json` · `calibration_verify.json` · `calibration_facts.json` · `calibration_sessions.jsonl` · `_ckpt/calibration_*.jsonl` **11종 13,200행**(파싱 실패 0 · `rep_seed` 중복 0 · 시드 범위 20260813~24461212 가 동결 `seed_regime` 과 일치 · 확증 시드 공간과 **교집합 0**) ·
운영 커맨드 = `.claude/commands/재개.md`(sha16 `010bd1138a1828d7` · 5,919 B) · `중단.md`(**v2 신판** sha16 `73c908dce1e7b254` · 8,620 B) — 둘 다 `docs/claude_commands/` 원본과 **바이트 동일**, 기존 `실행.md`(4,178 B) · `작업기록.md`(4,980 B) **0바이트 수정** ·
무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · 블록 AC 산출 4파일 + AD 2파일 **0바이트** ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 sha256 착수=종료 동일). **미실행**: 위 ⑭ 전항. 기입 시각 2026-08-18 12:03 KST.

---

50. **전규모 합성 드라이런 벽시계 계측 → `B` 후보 산출 (블록 AI — 계측 전용 · `B` 동결 0)**:

   - **① 배경 — 이 블록이 R2 보다 앞이다**: `docs/84` §5 실행순서는 **⑥ = 전규모 드라이런 벽시계 → `B` 확정**, **⑦ = SAP 1.2 재동결(R2)** 이고, R2 의 동결 대상 목록에는 축자로 "구현 코드·난수시드·**B**·시드집합·대표폴드·실패처리 규칙을 GIN 학습 착수 이전에 v1.2 로 동결"이 들어 있다. 그런데 `sap/rqint.py` 의 `B_DEFINITION_STATUS` 는 여전히 **`still_unspecified`** 다. ⑥ 을 건너뛰면 **R2 가 빈칸을 동결**하므로 본 블록을 먼저 수행했다. ★ **본 블록은 `B` 를 동결하지 않는다** — 계측·후보값 산출까지이고 문면 동결은 R2 의 일이며 `sap/rqint.py` 는 **0바이트 수정**이다.
   - **② 두 해석과 비용 2배 차이**: `pair_complement=True` 라 **참조분포 크기 = 2 × `n_coin_vectors`** 이므로 `B` 의 두 해석은 정확히 2배 차이난다 — **(가) `B` = `n_coin_vectors`** → 동전 100,000 / 참조분포 200,000, **(나) `B` = 참조분포 크기** → 동전 50,000 / 참조분포 100,000. `rqint_test` 는 **직렬 루프**(`for b in range(n_coin_vectors)`, 병렬 파라미터 없음)라 워커 수로 나눠지지 않는다.
   - **③ 수렴 논증은 측정 전에 사전명시했다**: 사전명시 파일 **`v3_Multimodal/config/b_dryrun_prespec.json`**(sha256 `9a2545eb0d897f30…` · 동결 **2026-08-22T00:56:14+09:00** · **SAP 등재 아님**)에 (가) 41.8 h > 24 h → D15 로 50,000 하향 / (나) 하향 불필요 = 동전 50,000 → **두 해석이 같은 구성(동전 50,000)으로 수렴**한다는 논증과, **외삽 허용 밴드 [18 h, 30 h]**(24 h 의 [0.75, 1.25]) 밖에서만 외삽 판정을 허용한다는 규칙을 **어떤 측정도 보기 전에** 고정했다. 동결 시각 **< 첫 측정 시각 2026-08-22T01:42:52+09:00** 이 파일시스템 birth time 으로 증명된다. ★ 같은 파일에 **전건 붕괴 시의 처리(`contingency_if_premise_fails`)도 측정 전에** 함께 규정했다 — 사후에 유리한 해석을 고르지 못하게 하기 위함이다.
   - **④ 단가 계측(단독 실행 · 동시 워커 0 · AC 전원 · 효과주입 0 · 전규모 fixture N 1,092 · K 370 · G 732)**: 계단 3점 = n=200 wall **135.79 s** û_wall 0.678943 · n=500 wall **347.29 s** û_wall 0.694588 · n=1000 wall **700.91 s** û_wall 0.700911. **선형성 상대 산포 0.0316** (기준 ≤ 0.10) → **통과**. `û` = 3점 중앙값 **0.694588 s/동전**(주루프 기준 `per_permutation_seconds` 중앙값 0.693028 s). `F-C4UNIT` 1.506339 s(18워커 경합 하 **상한**) 대비 **0.461배**, 블록 AD `F_UNIT_FULL` 0.716650 s 대비 **0.969배** — 단독 실행이 경합 하 측정치보다 빠르다는 예상과 부합한다.
   - **⑤ ★ 수렴 논증의 전건이 외삽으로 성립하지 않았다(사전명시된 처리 그대로 이행)**: 실측 `û` 로 계산한 (가) 100,000 동전의 추정 벽시계는 **19.49 h** 로 사전명시 밴드 **[18, 30] h 안**이다 → **외삽 판정 금지**(밴드 안이면 실주행으로만 판정한다는 사전 규칙). 즉 `docs/97` §2-1 이 참고로 든 41.8 h(단가 1.506 상한 기준)는 **단독 실행 실측에서 재현되지 않았고**, "(가) > 24 h" 라는 전건은 **미확정**이다. 사전명시 `contingency_if_premise_fails` 에 따라 ⓐ 전건 붕괴 사실을 그대로 기록하고, ⓑ 결정적 드라이런(동전 50,000)은 **예정대로 수행**했으며, ⓒ (가) 의 24 h 판정은 **본 블록에서 확정하지 않고 상신 사항으로 남긴다**(100,000 동전 실주행은 본 블록 예산 밖 — **자체 구제 0 · 구성 변경 0**). 참고로 블록 AD 가 적은 "드라이런 100,000 **3.88 h** / 50,000 1.94 h" 추정은 `F_THRU_FULL`(18워커 처리량)을 쓴 값이라 **직렬 함수인 `rqint_test` 에는 적용되지 않는다**(F-SERIAL) — 본 계측이 이를 대체한다.
   - **⑥ 결정적 드라이런 실측(동전 50,000 · `pair_complement=True` · `threads_limit` 1 · 단독 · AC 전원 · 24 h 하드 캡)**: 총 벽시계 **9.885 h**(35585.1 s) · 캡 도달 **아니오** · 실현 참조분포 **100,000**(= 2 × 50,000, 기대와 일치) · 여집합 항등식 감사 **1000 draw · 실패 0 · max_abs_dev 0.0** · `complement_identity_used` **true** · RAM peak **0.46 GiB**(게이트 30.72 GiB, 브리치 0건). → **D15 판정: 동전 50,000 구성은 24 h 이내(9.88 h)**.
   - **⑦ 추정 p 와 몬테카를로 SE 병기(D15 후단 이행)**: `T_obs` **0.00318021** · `p` **0.672623** · **`SE_MC = sqrt( p·(1−p) / n_permutation_values )` = 0.00148392**(축자 식 그대로) · `count_abs_ge_obs` 67,262 · p 공식 = `p = (1.0 + count) / (n_permutation_values + 1.0), count = sum(abs(perm) >= abs(T_obs) - _EPS)   # F-PFORM 축자 계승`. ★ **이 `p` 는 100% 합성 예측 위의 값이라 확증 결과가 아니다** — 귀무 구성(효과 주입 0)에서 나온 타이밍용 산출이며 어떤 가설 판정에도 쓰지 않는다.
   - **⑧ R2 에 넘길 `B` 후보값(동결·확정 아님)**: **(나) 해석(= `B` 는 참조분포 크기 `n_permutation_values`)** 를 택하면 `B` = 100,000 = **동전 50,000**, 실측 **9.88 h < 24 h** 로 D15 의 하향 조건이 발동하지 않는다 → **후보값 `B` = 100,000(참조분포 기준)**. **(가) 해석(= `B` 는 동전 수)** 를 택하면 동전 100,000 이 필요하고, 본 실측에서 파생한 2배 외삽은 **≈ 19.58 h**(= 2·T_obs(50,000) − 1,000·û)로 **24 h 이내로 보이나 밴드 안이라 외삽 판정이 금지**돼 있다 → **미확정 · 상신**. 검토자 §9-2 의 함의 단가 1.08 s/동전은 (가) ≈ 30 h 를 함의해 **검토자가 `B` 를 동전 수로 상정했음**을 시사하지만, 실측 단가가 그보다 낮으므로 **해석 확정은 R2 의 일**이다.
   - **⑨ AI-0 — cowork 판정 3건 수용 기록**: ⓐ **AF-DEV-1(A12 적응적 중지 미이행)은 검토자에게 상신하지 않는다** — 사용자 결정 2026-08-18. 근거 = R1 판정 무영향(C4 는 `F-ACC` 미적용이고 `r1_passed` 는 C0~C3 8셀에서 산출) + 설계 **완화가 아니라 초과 수행**. ★ "왜 통보하지 않았는가"가 나중에 재점이 되지 않도록 **결정 사실과 근거를 여기 남긴다**. ⓑ **항목48 ⑨ 의 AF 진도 기술("`C0:prop` 1,440/2,000 중단 상태 유지")은 stale 이며 정본은 항목49 ②** — 중단 4건 = 1,440 · 1,512 · 215 · 1,569 이고 최종 완주는 2026-08-18 11:55:10 이다. **항목48 문면은 무수정**(append-only)이고 본 줄이 supersede 포인터다. ⓒ **`docs/94` report2 §7 정정 2건** — §7-2 "R1 충족으로 **R2(SAP 1.2 재동결)** 가 다음 관문이다"는 **틀렸다**(⑥ 이 R2 보다 앞, 위 ①), §7-3 "큐 잔여 = `docs/86` · `docs/95` · `docs/91`"은 셋 다 2026-08-14 완료라 **stale** 이다(원장 미오염 — 제안문에 그침). **두 건 모두 리포트 문면은 무수정**이고 정정 기록은 여기와 `docs/97_b_definition_dryrun_report.md` §5 에 남긴다.
   - **⑩ 무결성 — 착수=종료 불변**: SAP 등재 **11모듈 0바이트** · `manifest.json` sha16 **`756d485feb4715e9`** · `sap_version` **1.1** · 블록 AC 4파일 + AD 2파일 **0바이트** · ★ **`sap/rqint.py` sha256 `eb842bc98140e9c5…` 착수=종료 동일**(`B_DEFINITION_STATUS` 리터럴 무수정) · `_sealed/` guard **275종(access.log 제외) / 291종(포함)** 및 stat-only 스냅샷 sha256 **완전 동일** · HEAD `566f487` · 커밋 21 불변. 본 블록이 만든 파일 = `v3_Multimodal/config/b_dryrun_prespec.json` · `v3_Multimodal/src/b_dryrun.py` · `experiments/rqint/b_dryrun/` 산출 뿐이다.
   - **⑪ 시드 — 신규 추첨 0**: `SEED_RULE_TEXT` 의 probe 파생 규약(`BASE_SEED + k·1,000,000`)을 그대로 이어 계단 = 850260813·850260814·850260815, 결정적 드라이런 = **860260813**(동전 RNG = +900,000,000). **확증 시드 공간(8개)** 및 **블록 AF `rep_seed` 13,200개**와 **교집합 0**(동전 시드도 교집합 0) 을 assert 로 확인했다.
   - **⑫ ★ 본 기입은 어떤 착수 허가도 아니다**: **`B` 문면 동결 0**(`B_definition_status` = `still_unspecified` 유지) · **SAP 1.2 재동결 0** · **개봉 0**(`unblinding_performed` false · `open_sealed` 0 · `emit_sign` 0 · `decision.py` 호출 0) · **확증 예측·OOF 로드 0**(`confirmatory_predictions_loaded` false · 예측 **100% 합성** · 효과 주입 0) · **GIN 학습·착수 0**(`gin_start_still_blocked` true) · **네트워크 0** · **`data/raw/` 변경 0** · **git commit·push 0**. R2·R3·`B` 확정·개봉·GIN 착수는 **전부 차단 유지**다.

> 지시서 = `docs/97_b_definition_dryrun_prompt_for_vscode.md` · 리포트 = `docs/97_b_definition_dryrun_report.md` ·
사전명시(동결, SAP 등재 아님) = `v3_Multimodal/config/b_dryrun_prespec.json`(sha256 `9a2545eb0d897f30` · 동결 2026-08-22T00:56:14+09:00) ·
산출 = `experiments/rqint/b_dryrun/stair.json` · `decisive.json` · `facts.json` · `verify.json` · `integrity.json` · `decisive_heartbeat.jsonl` ·
러너 = `v3_Multimodal/src/b_dryrun.py`(신규 · **`sap/` 밖** · AST 스캔상 데이터 경로 `master_X.parquet`·`master_Y.parquet` 2개뿐) ·
무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · 블록 AC 4파일 + AD 2파일 **0바이트** · `sap/rqint.py` **0바이트** ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 sha256 착수=종료 동일). **미실행**: 위 ⑫ 전항. 기입 시각 2026-08-22 11:56:58 KST.

---

51. **(가) 해석 실주행 — 동전 100,000 · 24 h 하드 캡 → `B` 24h 판정 완결 (블록 AJ — 계측·판정 전용 · `B` 정의 채택 0)**:

   - **① 왜 이것이 「설계 변경」이 아닌가 — 동결된 정책이 지정한 이행이다**: 연쇄는 4단계다. ⓐ **정책 문면(측정 전 동결)** — 블록 AI 의 `b_dryrun_prespec.json`(sha256 `9a2545eb0d897f30…` · 동결 **2026-08-22T00:56:14+09:00**) 의 `extrapolation_policy.rule_inside_band` 축자 = **"밴드 안이면 외삽 금지 → 실주행 + 24h 하드 캡으로 판정한다."** ⓑ **밴드 안 판정(실측)** — 동전 100,000 의 추정 벽시계 `T̂` 는 **19.49 h**(계단 외삽) · **19.58 h**(50,000 실측의 2배 외삽)로 **둘 다 사전명시 밴드 [18, 30] h 안**이었다. ⓒ **상신** — 같은 파일의 `contingency_if_premise_fails.action③`(측정 전 동결)이 "100,000 동전 실주행은 본 블록 예산 밖이므로 **자체 판단으로 구성을 바꾸지 않는다** → **상신 사항으로 보고**"라 규정했고 블록 AI 는 그대로 이행했다(`docs/97` report §4-5·§6-1). ⓓ **승인** — 사용자가 **2026-08-22** 그 상신을 승인했다. ★ 따라서 본 블록은 **결과를 보고 구성을 키운 사후 설계 변경이 아니라**, 측정 전에 동결된 정책이 "밴드 안이면 실주행하라"고 **미리 지정한 경로**를 밟은 것이다.
   - **② 델타 사전명시 동결(실주행 전)**: **`v3_Multimodal/config/b_100k_prespec.json`**(sha256 `e7406c23b8d61b0c…` · 동결 **2026-08-22T22:12:40+09:00** · **SAP 등재 아님** · 이후 무수정). `supersedes_nothing` = true — **블록 AI 의 prespec 을 대체하지 않고**(AI 산출물 4종 **0바이트**) `action③` 이 넘긴 **단 하나의 항목**만 규정한다. `run_config` = 동전 **100,000** · `pair_complement` true · 참조분포 **200,000** · 감사 draw 1,000 · `threads_limit` **1** · 캡 **86,400 s**. ★ **판정식 2분기를 측정 전에 고정**했다 — 완주 & ≤24 h → (가) 하향 미충족 / 캡 도달 → 24 h 초과 확정 → 50,000 하향. **3분기 신설·캡 연장·재실행 금지.** 동결 시각 **2026-08-22T22:12:40+09:00 < 실주행 시작 2026-08-23T11:36:18+09:00**.
   - **③ 시드 신규 추첨 0 — 결정성 검증을 공짜로 얻는 설계**: `rep_seed` **860260813**(= 블록 AI 결정적 드라이런)을 **그대로 재사용**했다(동전 시드 1760260813). 동전 생성기가 단일 `default_rng` 스트림이고 루프가 직렬(`for b in range(n_coin_vectors)`)이므로 100,000 run 의 앞 50,000 동전은 50,000 run 의 **prefix** 다 → **b=50,000 시점 러닝 카운트가 블록 AI 실측 67,262 와 정확히 일치해야 한다**. 착수 전 소규모 자가시험(n_coin 100 vs 200)으로 이 전제(prefix 동일 · 여집합 감사 비교란 · 관측량 불변)를 **바이트 수준에서 확인**했다(`prefix_smoke.json`).
   - **④ ★ 결정성 검증 2건 — 전건 통과**: ⓐ **b=50,000 러닝 카운트 = 67,262**(참조분포 100,000 기준) — 기대 **67,262** 와 **정확히 일치**(`p` 재현값 0.6726232738 = 블록 AI `p` 와 동일). 종료검증에서는 산출 배열 `t_star.npy` 로 **러너와 독립 재계산**해 같은 값을 얻었다. ⓑ **관측통계량 바이트 동일** — `T_obs` **0.0031802114140302242** · `delta_rf` **0.00038510137913283504** · `delta_gin` **-0.002795110034897389** 이 `F-AIOBS` 와 `repr` 수준에서 동일하다. 같은 `rep_seed` 인데 관측량이 달랐다면 fixture 재현성이 깨진 것이므로 즉시 중단 조건이었다 — **불일치 0**.
   - **⑤ 실주행 실측(동전 100,000 · `threads_limit` 1 · 단독 실행 · AC 96 W · 24 h 하드 캡)**: 총 벽시계 **19.4887 h**(70159.4 s) · 캡 도달 **아니오** · AC 이탈 **아니오** · 실현 참조분포 **200,000**(= 2 × 100,000) · 여집합 항등식 감사 **1000 draw · 실패 0 · max_abs_dev 0.0** · `complement_identity_used` **true** · `per_permutation_seconds` **0.694628** · RAM peak **0.46 GiB**(게이트 30.72 GiB · 브리치 0건). 참고 — 블록 AI 실측 단가 0.697678 s/동전 대비 본런 0.694628 s/동전.
   - **⑥ ★ D15 판정 — 사전 고정한 2분기 중 실현된 가지**: **완주 · 벽시계 19.489 h ≤ 24 h** → (가) 는 **하향 조건 미충족** → `B` = 동전 100,000(참조분포 200,000) 후보 성립. 이로써 **(가) 해석의 24 h 판정이 실측으로 완결**됐고, 블록 AI 가 상신으로 남긴 미해결 항목은 **해소**됐다.
   - **⑦ 최종 판정표(양 해석)**: **(가) `B` = 동전 수** → 동전 100,000 / 참조분포 200,000 / 벽시계 **19.489 h**(본 블록 실측) / 24 h **이내**. **(나) `B` = 참조분포 크기** → 동전 50,000 / 참조분포 100,000 / 벽시계 **9.8848 h**(블록 AI 실측) / 24 h **이내**. **두 해석 모두 실측으로 24 h 판정이 확정**됐다.
   - **⑧ 양 해석 `SE_MC` 대비(R2 의 정의 선택 근거)**: 식 축자 = **`SE_MC = sqrt( p·(1−p) / n_permutation_values )`**. (가) `p` **0.670512** · **`SE_MC` 0.00105101**(참조분포 200,000) / (나) `p` **0.672623** · **`SE_MC` 0.00148392**(참조분포 100,000). **참조분포가 2배면 SE 는 1/√2 = 0.70711 배** — 실측 비 **0.70827**. 즉 (가) 는 **정밀도 √2 배 · 비용 2배**다. ★ **이 `p`·`SE_MC` 는 100% 합성 예측 위의 값이라 확증 결과가 아니며** 어떤 가설 판정에도 쓰지 않는다.
   - **⑨ ★ 정의 채택 선언 0 — 본 블록은 실측을 갖춰 주는 데까지다**: `sap/rqint.py` 의 `B_DEFINITION_STATUS` 는 **`still_unspecified` 그대로**이고 파일은 **0바이트 수정**이다. **(가)/(나) 중 무엇을 `B` 로 삼을지는 R2(SAP 1.2 재동결) 소관**이며 본 블록은 어느 쪽도 채택·동결·권고하지 않는다. 참고로 검토자 §9-2 의 함의 단가 1.08 s/동전은 (가) ≈ 30 h 를 함의해 **검토자가 `B` 를 동전 수로 상정했음**을 시사하지만, 실측 단가가 그보다 낮다는 사실까지가 본 블록의 기여다.
   - **⑩ 무결성 — 착수=종료 불변**: SAP 등재 **11모듈 0바이트** · `manifest.json` sha16 **`756d485feb4715e9`** · `sap_version` **1.1** · 블록 AC 4파일 + AD 2파일 **0바이트** · ★ **`sap/rqint.py` sha16 `eb842bc98140e9c5` 착수=종료 동일** · ★ **블록 AI 산출물 4종**(`b_dryrun_prespec.json`·`stair.json`·`decisive.json`·`b_dryrun.py`) **0바이트** · `_sealed/` guard **275종(access.log 제외) / 291종(포함)** 및 stat-only 스냅샷 sha256 **완전 동일**(블록 AI 착수 스냅샷 `741feb8e52a3cf00…` 과도 동일) · HEAD `566f487` · 커밋 21 불변. 본 블록이 만든 파일 = `v3_Multimodal/config/b_100k_prespec.json` · `v3_Multimodal/src/b_100k_run.py` · `experiments/rqint/b_100k/` 산출 뿐이다.
   - **⑪ ★ 본 기입은 어떤 착수 허가도 아니다**: **`B` 정의 채택·문면 동결 0** · **SAP 1.2 재동결 0** · **개봉 0**(`unblinding_performed` false · `_sealed/` 읽기·쓰기 0 · `open_sealed` 0 · `emit_sign` 0 · `decision.py` 호출 0) · **확증 예측·OOF 로드 0**(`confirmatory_predictions_loaded` false · 예측 **100% 합성** · 효과 주입 **0**) · **GIN 학습·착수 0**(`gin_start_still_blocked` true) · **네트워크 0** · **`data/raw/` 변경 0** · **git commit·push 0**. R2·R3·`B` 확정·개봉·GIN 착수는 **전부 차단 유지**다.

> 지시서 = `docs/98_b_definition_100k_run_prompt_for_vscode.md` · 리포트 = `docs/98_b_definition_100k_run_report.md` ·
델타 사전명시(동결, SAP 등재 아님) = `v3_Multimodal/config/b_100k_prespec.json`(sha256 `e7406c23b8d61b0c` · 동결 2026-08-22T22:12:40+09:00 · `supersedes_nothing` true) ·
산출 = `experiments/rqint/b_100k/run.json` · `se_comparison.json` · `prefix_smoke.json` · `facts.json` · `verify.json` · `integrity.json` · `run_heartbeat.jsonl` · `t_star.npy` ·
러너 = `v3_Multimodal/src/b_100k_run.py`(신규 · **`sap/` 밖** · `b_dryrun.py` 는 **읽기 전용 import**) ·
무수정 대조 = 블록 AI 산출물 4종 **0바이트** · SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · 블록 AC 4파일 + AD 2파일 **0바이트** · `sap/rqint.py` **0바이트** ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 sha256 착수=종료 동일). **미실행**: 위 ⑪ 전항. 기입 시각 2026-08-24 07:10:03 KST.

---

52. **R2 준비 — SAP 1.2 재동결 「설계 확정」 (블록 AK — 무동결 · 계산 0 · 채택 0)**:

   - **① 왜 「준비 블록」을 따로 두었나 — R2 실행 직전에 문면 충돌 2건이 실측됐다**: **충돌 A** = `sap_version` 은 `v3_Multimodal/src/sap/freeze.py` **L581 하드코딩 리터럴**이고 CLI·환경변수·설정파일 경로가 **0개**인데(`F-VERLIT`), 그 `freeze.py` 자신이 `MODULE_FILES` **11개 중 하나**다(`F-MODFILES`, L47). 따라서 1.1 → 1.2 는 **필연적으로 11모듈 중 1개의 sha256 을 바꾼다** → `docs/55b` §8 L470 축자 **"all pre-existing module hashes remain unchanged"** 와 충돌한다. **충돌 B** = D20 의 `model_family` 문자열 원천은 매니페스트가 아니라 **`v3_Multimodal/src/sap/decision.py` 7행**(L61·65·69·73·77·81·85)이고 `manifest.json` **14곳**(`frozen_parameters`/`validation` × `multiplicity_manifest[0..6]`)은 그 파생물이다 → 「11모듈 불변」(decision.py 못 고침)과 「manifest 재현성」(고쳐야 함)이 **동시 성립 불가**하다. D20 이 요구하는 **「전후 sha16」이 manifest 인지 모듈인지도 문면상 미결**이다. 동결은 되돌릴 수 없고 매니페스트 해시를 수십 블록이 참조 중이므로 **측정·선택지 정리를 먼저 하고 동결은 `docs/100` 으로 분리**했다.

   - **② 「비실질 메타데이터」 주장의 코드 근거 — AST 판정 = 표기 전용**: `MULTIPLICITY_MANIFEST` 는 `decision.py` 에서 **L59 Store 1건뿐**이고 읽는 코드가 없다. `freeze.py` 의 L372·L650 은 **둘 다 dict 값 위치의 Load** = 직렬화 기록 전용이다. 첨자·순회·컴프리헨션 **0건**. `model_family` 키를 **읽는** 코드는 저장소 전역(`.venv`·`archive` 제외) **0곳**이다. Holm 계산은 `HOLM_FAMILY`(라벨 7개)만 쓰며(`holm()` L190~210: `labels = list(HOLM_FAMILY)` · `assert m == len(HOLM_FAMILY) == 7`), **순서 무관**(`np.argsort(p)`)이고 family_size 도 `HOLM_FAMILY` 길이로 고정된다. → **D20 의 「비실질」 주장은 코드로 뒷받침된다** — `model_family` 를 어떻게 고쳐도 수치 결과는 바뀌지 않는다. 다만 `decision.py` 를 고치면 **핵심 분석 모듈 해시가 바뀐다**는 사실은 그대로 남는다(= 충돌 B).

   - **③ 가상 해시 산출(파일 수정 0 · 메모리 내 치환)**: `freeze.py` 현재 sha256 `94e6369fa952be7f…`(42,927 B) → **A-1a**(L581 리터럴 1문자만) `8bef5f70d168c50d…`(42,927 B) · **A-1b**(리터럴+주석) `37442f6db2717746…`(42,959 B). 나머지 **10모듈은 변경 없음**. 11모듈 live sha256 은 `manifest.modules` 등재값과 **전건 일치**했다. ★ **실제로 고치지 않았다** — 전 파일 **0바이트**다.

   - **④ ★ 지시서 미상정 실측 3건(R2 의 필수 후속 작업을 늘린다)**: ⓐ **매니페스트는 애초에 바이트 재현물이 아니다** — `frozen_at_kst` 가 `datetime.now(KST)`(`freeze.py` L582)이고 `versions` 가 설치 패키지 버전(L674)이다. 즉 `manifest.reproduce` 는 **의미 수준 재현**이며, 이 사실은 A-3·B-2 에 대한 「재현성 붕괴」 반론의 강도를 낮춘다(붕괴가 아니라 **이미 성립하지 않던 것의 명시화**). ⓑ **매니페스트 sha16 `756d485feb4715e9` 하드코딩이 30파일 · 48곳**이다. 그중 **R2 이후에도 실행될 live src 3개** — `pre_unblinding_audit.py`(L64 기대해시·L121 게이트) · `rqint_package_gates.py`(L35) · `rqint_calibration.py`(L138·892·1328) — 는 기대값을 갱신하지 않으면 **R2 직후 자동 실패**한다. ★ `pre_unblinding_audit.py` 는 **개봉 전 필수 감사**다. `sap_version == "1.1"` 을 `assert` 로 거는 곳도 6개다(`confirmatory_oof_rep1.py:160` 외 `record_block_*` 5개). ⓒ **`experiments/rqint/r3_package/sap/` 에 SAP 11모듈의 바이트 동일 사본**이 있다(전건 `identical_to_live` true) → `freeze.py`·`decision.py` 를 고치면 즉시 발산하므로 R3 축자 「동결 해시로부터 동일 산출 확인」 충족에 패키지 재생성이 필요하다.

   - **⑤ 선택지 정리 — 채택 0(사용자/검토자 몫)**: 충돌 A **3안**(A-1 L581 한 줄 / A-2 외부 주입 / A-3 manifest 후처리)과 충돌 B **3안**(B-1 `decision.py` 7행 수정+스키마 분리 / B-2 무수정·manifest 필드 추가 / B-3 이번 회차 보류)을 **비용·무결성·재현성** 3축 비교표로 냈고, 안별 §8 개정문 문안까지 **영문+국문 3종씩** 작성했다. B 3안에 대해서는 **D20 4요구**(전후 문자열·전후 sha16·라인 diff·11모듈 불변 명시)의 ○/× 표와 **「어느 sha16 을 가리키는가」**(B-1 = `decision.py`+manifest / B-2 = manifest 만 / B-3 = 없음)를 명시했다. ★ **러너는 어느 안도 채택하지 않았다.**

   - **⑥ §8 개정문 확정 문안 초안 — `docs/99_amendment_section8_draft.md`(신규)**: 빈칸 4개를 **2026-08-10 / <EXTERNAL-REVIEWER> / Ph.D. / Gyeongnam Intelligence Innovation Center (GIIC)** 로 채웠다(출처 = `v3_Multimodal/config/reviewer_identity_resolved.json:blanks_resolved`, 블록 AH, 서명본 `…_SIGNED.pdf` sha256 `161dd9d2290df32b…` 축자). ★ **승인일 2026-08-10 ≠ 서명일 2026-08-12** 이며 부록 B `2026-08-06` 과 표지 `2026-08-10` 이 갈렸을 때 **표지 기준으로 통일**했고 서명본에서 정정되지 않았다는 확정 근거(`both_literals_preserved`)를 **주석으로 병기**했다. 해시 관련 문장은 **`{A안}`·`{B안}` 플레이스홀더**로 두었다. **`docs/55b` 는 0바이트** — 본문 삽입은 `docs/100` 의 일이다.

   - **⑦ ★ R5 두 요소 추가 + 실측 불일치 1건 정직 기록**: R5 는 현재 **`partial` 인 유일한 승인조건**이다(`rqint_procedure_decisions_v0.json:conditions.R5.status`). 실측(`F-R5GAP`) = 부호 4건은 §8 에 있으나 **공개일자 2026-07-27 은 §8 안에 없고** §2 본문 L137 **1곳뿐**이며 **노출 인원은 문서 전체에 없다**. 초안에 두 요소를 넣었다 — **공개일자 2026-07-27**(`first_look_register.rows` 4행 `ts_kst` 전건과 일치) · **노출 인원** = 「방향을 아는 사람은 **실명 2명**(연구자·지도교수), **외부 검토자는 부호 4건이 존재하고 서로 동일하다는 사실만** 고지받았고 방향은 모른다(`docs/55b` §2 축자), **4건 중 3건**(반복2·반복3·consensus)은 **2026-07-28 부터 공개 저장소에서 열람 가능**」. 공개 근거 = `experiments/provenance/sign_disclosure_matrix.json:public_exposure_verification` — 스칼라 부호 리터럴 **3개**(`/repeats/2/sign`·`/repeats/3/sign`·`/consensus/sign`) · `in_pushed_commit` **true** · 원격 tip `bdb65c8` · 커밋 `878b3ba`(2026-07-28 15:58:58 KST) · push reflog 2026-07-28 16:10:52 +0900. 반복1 은 **푸시된 커밋에 없다**. ★ **불일치** — 「실명 2명」 중 **지도교수 항목은 저장소 실측이 `unknown_as_of_2026-08-06`** 이다(`sign_disclosure_matrix.json:advisor_route.determination` · `sign_lexeme_hits_in_correspondence` **빈 배열** · `open_questions[0]` 축자 「지도교수에게 Δ(M2b−M1b) 부호가 전달된 사실이 서신 기록에서 확인되지 않는다」). 지시서가 이 문안을 **사용자 확정**으로 지정했으므로 초안 본문은 지시서대로 쓰되, 초안 §6 과 리포트 §5 에 불일치와 **두 선택지**(① 근거 보강 후 「2명」 유지 / ② 「연구자 1명 확정, 지도교수 전달 여부 서신 기록상 미확인」 으로 조정)를 정리했다. **러너는 채택하지 않았다.**

   - **⑧ `still_unspecified` 3건 종결안 초안 — `v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json`(신규 · `.DRAFT` 접미사 필수)**: `status` = `draft_not_frozen` · `is_sap_freeze` **false** · `supersedes` **null**(v0 를 대체하지 않고 superseding 관계만 기술) · **v0 는 0바이트**. ⓐ **`B` = 동전 벡터 수 = 100,000**(참조분포 200,000) — 사용자 확정 **2026-08-24**. 근거 = `F-BMEAS` **19.4887 h ≤ 24 h** → D15 하향 **미발동** · 검토자 §9-2 함의 단가 1.08 s/동전이 「동전 수 상정」 시사 · 판정식 2분기가 실주행 **이전**에 동결(`b_100k_prespec.json` 2026-08-22T22:12:40 < 실주행 2026-08-23T11:36:18). ⓑ **C0~C3 복제수 primary 2,000 / sensitivity 1,000** — ★ **결과를 보고 정한 것이 아니다**: `calibration_design.json`(sha256 `42e2f8f9f3f24ec1…`) 동결 **2026-08-12 22:25:21 KST** 가 첫 시뮬레이션 세션 시작 **2026-08-12 22:46:44 KST** 보다 **21분 23초 앞선다**(`calibration_sessions.jsonl` 실측). 검토자 권고 1,000~2,000 범위 안. ⓒ **`r3_second_party` = <SECOND-PARTY> 확정** — 교수님 승인 축자 「네 <SECOND-PARTY>씨에게 부탁해서 처리하시죠.」(`ledger.correspondence[19]`, 메시지 `<GMAIL-MSGID>`, 2026-08-12 18:34:47 KST) + `r3_second_party_freeze.json`(`0624d3ddb852c4e9`).

   - **⑨ ★ 누락 발견 — 블록 AG 가 `r3_second_party` 를 종결하지 않았다**: 2026-08-24 실측으로 `rqint_procedure_decisions_v0.json:still_unspecified[4]` 는 여전히 `status` = **`escalated_awaiting_advisor_reply`** · `confirmed_second_party` = **null** 이다. 항목의 `note` 축자(「상신은 완료됐으나 수행 주체 확정은 미완이므로 still_unspecified 에서 빼지 않는다」)는 **승인 서신 접수(2026-08-12 18:34:47) 이전 기준**이라 stale 이다. 승인은 그날 저녁 도착했고 블록 AG(2026-08-14)가 접수·기록했으나 v0 의 해당 항목에는 반영되지 않았다. **본 블록은 v0 를 고치지 않고 누락 사실만 기록**했다(DRAFT 의 `★_omission_found_by_this_block`). 부수 확인 — 메모 등에 있던 `ledger.open_question.r3_second_party` 는 **존재하지 않는 키**다(ledger 최상위 **11키**에 `open_question` 없음, 실측) → 조치 불요. v0 의 stale 3건(`conditions.R1.status`=`pending` vs 실측 `r1_passed`=true · `R6`=`pending` vs 블록 AC 수행 · `R5`=`partial`)도 **고치지 않고 기록만** 했다.

   - **⑩ 해시 원장 스펙 + R2 이행 대조표 — `docs/99_r2_hash_registry_spec.md`(신규)**: 범주 ①SAP 11모듈 ②RQ-int 3모듈(`sap/rqint*.py`) ③config 동결파일 16종 ④`B`·시드집합·대표폴드·실패처리 규칙의 소재 파일 ⑤사전등록·개정문·원장 문서 — 총 **45행**에 현재 sha256 을 실측 병기하고 **「이미 어디에 등재됐는가 / 아직 원장에 없는가」**를 마지막 열에 표기했다. **미등재 11건** = 실질 신규 등재 **6건** + append-only **4건**(고정 해시 동결 불가 → 「동결 시점 스냅샷」 지위) + 표기 정정 1건. ★ 그중 **`reviewer_identity_resolved.json`(§8 빈칸 값 원천)** 과 **`sign_disclosure_matrix.json`(R5 노출 인원 근거)** 이 미등재인 것이 가장 중요하다. 이행 대조표는 **R2·R4·R5·D19·D20·D21·D22 + KS 신설** 8행을 「요구 축자 / 현재 상태 / 이행 위치 / 남은 일」 4열로 채웠다 — **R4** = SAP 1.2 §RQ-int 다중성 소절 2문장 + `manifest.frozen_parameters.decision_A11.multiplicity` 문자열, 총 **3곳** 지정(★ `holm()` **코드 수정 불필요** — A/B 두 판은 같은 함수를 입력만 달리 호출해 얻는다; 고치면 11모듈 해시가 또 바뀐다). **D19** = C4 실측 검정력 τ0.01 **0.250** / τ0.02 **0.735** / τ0.03 **0.9725**(각 R=400, α=0.05 기각률) → τ=0.02 는 3단 사다리 **중간단(0.50~0.80)** = 「검정력·유보문장 병기」, 최하단 조항 **미발동**, 0.80 미달이므로 관례적 충족 주장 금지. **D21** = **확인 완료**(`gin_seed_freeze.json` `10828447c6d33118`: 대표 unit **3** = (201,4)·(202,1)·(203,0) · `training_seeds_ordered` **5** · `confirmatory_seed_prefix` **3** · `stability_seeds` **5**) ★ RQ-int 는 「3 seed × 3 repeat」(D4·D5)이므로 SAP 1.2 는 **어느 5/3 인지 명시**해야 한다. **D22** = `sap/rqint.py` `TEST_STATISTIC` 에 "additive surrogate 대체 금지(A6 계승)" 가 **이미 있음** → 「`e_g` 선형화 = 보조 진단 전용」 1문장 추가. **★ KS 신설 항목** = `C0:prop` KS p **0.052447**(여유 **+0.002447**)이 기준 0.05 **바로 위**라는 사실을 R2 문면에 **정직 기재**하도록 항목을 신설하고 병기 문안까지 작성했다. **AF-DEV-1 미상신 결정**(사용자 2026-08-18)은 **항목50 참조만**(중복 기입 0).

   - **⑪ 무결성 — 착수=종료 불변**: **`sap_version` 1.1** · `manifest.json` sha16 **`756d485feb4715e9`**(sha256 착수=종료 동일) · SAP 등재 **11모듈 0바이트** · `freeze.py` **미실행 · 0바이트** · `decision.py` **0바이트** · **config 동결파일 16종 전건 0바이트**(`ladder_freeze`·`gin_seed_freeze`·`gin_inner_valid_freeze`(+`.status`)·`post_interim_freeze_v1_0`(+`.status`)·`rf_tuned_freeze`·`holm7_latefusion_freeze`·`a5_boundary_amendment`·`a5_mechanism_freeze`·`a5_stratum_label_supersede`·`r3_second_party_freeze`·`reviewer_identity_resolved`·`rqint_procedure_decisions_v0`·`b_dryrun_prespec`·`b_100k_prespec`) · **`docs/55b` 0바이트** · 블록 AC 4파일 + AD 2파일 + AI 4종 + AJ 산출물 **0바이트** · `sap/rqint.py` sha16 **`eb842bc98140e9c5`** 불변(`B_DEFINITION_STATUS` = `still_unspecified` 그대로) · `_sealed/` guard **275종(access.log 제외) / 291종(포함)** 및 stat-only 스냅샷 착수=종료 동일 · HEAD **`566f487`** · 커밋 **21** 불변. 본 블록이 만든 파일 = `docs/99_r2_freeze_prep_report.md` · `docs/99_amendment_section8_draft.md` · `docs/99_r2_hash_registry_spec.md` · `v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json` · `experiments/rqint/r2_prep/` 산출뿐이다.

   - **⑫ ★ 본 기입은 어떤 착수 허가도 아니다**: **동결 0**(`sap_version` 1.2 승격 **0** · 매니페스트 재생성 **0** · 원장 신규 등재 **0**) · **채택 0**(충돌 A·B 안 채택 0 · `B` 정의 동결 0 · `still_unspecified` 3건 동결 0 — `.DRAFT` 초안뿐) · **개봉 0**(`unblinding_performed` false · `_sealed/` 읽기·쓰기 0 · `open_sealed` 0 · `emit_sign` 0 · `decision.py` 호출·import 0) · **계산 0**(모델 학습·추론·순열·새 추정 0 · 확증 예측·OOF 로드 0) · **GIN 착수 0**(`gin_start_still_blocked` true) · **네트워크 0** · **`data/raw/` 변경 0** · **git commit·push 0**. R2·R3·`B` 확정·개봉·GIN 착수는 **전부 차단 유지**다.

> 지시서 = `docs/99_r2_freeze_prep_prompt_for_vscode.md` · 리포트 = `docs/99_r2_freeze_prep_report.md` ·
신규 산출 = `docs/99_amendment_section8_draft.md`(sha256 `29b2d8f401afa0dc…`) · `docs/99_r2_hash_registry_spec.md`(`d10ffe4431fd2f60…`) · `v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json`(`88287032cf6fbc58…`) · `experiments/rqint/r2_prep/{facts,impact,registry,verify}.json` ·
무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · `docs/55b` **0바이트** · config 동결파일 **16종 0바이트** · `sap/rqint.py` **0바이트** · 블록 AC 4파일 + AD 2파일 + AI 4종 + AJ 산출물 **0바이트** ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 sha256 착수=종료 동일). **미실행**: 위 ⑫ 전항. 기입 시각 2026-08-24 11:57:50 KST.

---
53. **★ R2 완주 — SAP **1.1 → 1.2** 재동결 (블록 AN — `docs/102` 2차 델타 · 정본 `docs/100` · 1차 델타 `docs/101`)**:

   - **① 이 항목이 기록하는 것 — 수십 블록이 검증해 온 불변식을 «의도적으로·통제 하에» 깼다**: `manifest sha16` **`756d485feb4715e9`** 와 `sap_version` **1.1** 은 지금까지 모든 블록의 게이트 상수였다. 본 블록이 그것을 **`d08dcedf2a22e1c8…` · `1.2`** 로 바꾼다. 사유 = 외부 통계검토 승인조건 **R2**(「RQ-int 구현 코드·난수시드·`B`·시드집합·대표폴드·실패처리 규칙을 GIN 학습 착수 이전에 v1.2 로 동결하고 해시 기록」). **선행 시도 2회는 전부 롤백**했다 — 블록 AL(`docs/100`)은 AL-4 에서 신규 2필드의 «값» 미확정으로, 블록 AM(`docs/101`)은 AL-5 에서 `pre_unblinding_audit.py` 「1회 실행 → 통과」 조항이 **구조적으로 충족 불가**여서. 본 블록은 `docs/102` 【대체 4】로 그 조항을 정정받아 **AL-1~AL-8 완주**했다.

   - **② 사용자 결정 3건과 각각의 근거**: **A-1a** = `freeze.py` **L581 리터럴 1곳만** `"1.1"`→`"1.2"`(주석·다른 행 무수정). 근거 = `sap_version` 은 L581 하드코딩이 유일 소재이고 CLI·env 경로 0개인데 `freeze.py` 자신이 11모듈 중 하나라, 버전 증가는 **필연적으로 1개 모듈 해시를 바꾼다**. **B-2** = `decision.py` **무수정**(핵심 분석 모듈 해시 보존) + manifest 에 `primary_model_family`/`families_compared` **추가**, 기존 `model_family` **14곳 보존**. 근거 = `model_family` 를 **읽는** 코드가 저장소 전역 0곳이고 Holm 계산은 `HOLM_FAMILY` 만 쓴다(비실질 메타데이터). **R5 = 「1명」** = 부호 **방향**을 아는 사람 = 연구자 1명. 근거 = 서신 **22행 전수 스캔에서 부호 방향 어휘 0건** · `sign_disclosure_matrix.advisor_route` = `unknown_as_of_2026-08-06` · 연구자 확인 「전달한 적 없음」. 지도교수는 **부호 4건의 존재·상호 동일성만** 고지받았다.

   - **③ ★ 사전 예측 해시 적중 — 치환 범위가 의도를 넘지 않았음의 증명**: `docs/100` AL-2 가 사전 제시한 값 **`8bef5f70d168c50d…`(42,927 B)** 와 실측이 **완전 일치**했다. 차이 바이트 오프셋 **[32653] 단 1개** · 크기 **불변** · `difflib` hunk **`@@ -581 +581 @@` 1행**. (블록 AL·AM 도 같은 값을 냈다 — **3회 독립 재현**.) ★ 주석 내 `1.1` 은 따옴표가 없어 치환 대상이 아니다 = 「주석 무수정」 충족.

   - **④ `freeze.py` 실행 — 검증 8종 전건 PASS · `n_changed` = 1**: metrics · consensus · bootstrap(primary_ci=BCa · scaffold Δ_obs 0.2956 · A1 `not_estimable`=`bca_failed_z0_degenerate`) · signflip(zero-effect p=1.0000 · uniform mean_p 0.533 KS 0.100) · null_generator(NULL_B 1000 · MC_SE 0.2449) · decision(A11 진리표 전건 True) · unseen_target · redaction **전건 PASS**, `all_validation_pass` **true**. AST 스캔 **확증 데이터 미접근 = True**(금지 import 0 · data-load call 0 · open 데이터리터럴 0). ★ **modules 11 중 `freeze.py` 1개만 변경 · 나머지 10개는 SAP 1.1 등재값과 전건 동일**(프로그램 대조 `identical 10 / changed 1`). config sha16 `b885585aefbabb32`. 재생성 매니페스트 = **`26071a10944bfc3b…`(40,136 B)** — `frozen_at_kst`=`datetime.now(KST)` 라 **바이트 재현물이 아니며** AL 의 `50abc0e9…`·AM 의 `5b61d1d3…` 과 다른 것이 정상이다.

   - **⑤ B-2 erratum — 확정값·도출규칙·멱등**: `primary_model_family` = 문자열 **`"RF"` 7슬롯 공통**(연구 수준 사실) · `families_compared` = 슬롯 **②~⑦ `["RF"]`** · 슬롯 **⑧ `["RF","GIN"]`**(RQ-int 는 `T = Δ_RF − Δ_GIN` 이라 두 family 가 걸린다 — `sap/rqint.py` `TEST_STATISTIC` 축자). ★ **D20 이 지적한 결함이 정확히 이것** — 한 문자열이 «연구 수준 primary» 와 «슬롯 수준 비교대상» 을 뭉뚱그려 ⑧ 까지 `"RF primary confirmatory (RF-Morgan+seq)"` 로 적혀 있었다. 도출 규칙을 erratum `derivation_rule` 에 **기계 판독 가능**하게 기록했다. 값 검증 **6조건 전건 PASS**(스크립트 미import 독립 재검산): 두 필드 14/14 · primary 14/14 `"RF"` · 리스트 14/14 · `["RF","GIN"]` = 블록당 정확히 1개(id `⑧`) · 나머지 `["RF"]` 12 · **기존 `model_family` 14곳 문자열·개수 불변**. 스크립트 `v3_Multimodal/src/sap_manifest_erratum.py`(`9cd4bb6f2b8f253d…` · `sap/` **밖** = SAP 모듈 아님)는 **멱등** — `--check`→적용→재적용 **3회 모두 매니페스트 sha256 동일**. 매니페스트 **패치 전 `26071a10944bfc3b…`(40,136 B) → 패치 후 `d08dcedf2a22e1c8…`(55,303 B)**. 사이드카 `experiments/sap/sap_manifest_erratum_d20.json`(`91e764404feaa8fa…`) = 자기참조 회피용 「패치 후 sha」 기록 위치. erratum 6요소 전건 존재. ★ **스크립트는 블록 AM 이 작성·검증·멱등확인한 것을 원위치 복귀시켜 재사용**했다(`9cd4bb6f2b8f253d…` 바이트 동일).

   - **⑥ ★ AL-5 검증 조항 정정 — cowork 지시서 결함의 자인(같은 계열 3번째)**: `docs/100` AL-5 는 「갱신 후 `pre_unblinding_audit.py` 를 실제로 1회 실행해 통과를 확인할 것」이라 했으나, 그 스크립트는 `main()` **첫 문장이 1회성 가드**(L948)이고 산출물 2종이 이미 존재해(`sealing_completeness_audit.json` 2026-08-07 09:52 · `sign_disclosure_matrix.json` 2026-08-14 13:53) **`rc=2` 즉시 종료** — 산출물 삭제가 금지이므로 **어떤 방법으로도 충족될 수 없었다**. (AJ-2-b 「동결 모듈 0바이트 ↔ 루프 계측 삽입」 · AL 「`decision.py` 호출 0 ↔ `freeze.py` 실행」에 이은 **3번째**.) → `docs/102` 【대체 4】가 **검증만** `gate_g0()`·`gate_holm()` **직접 호출**로 대체했고(**`main()` 호출 0** · 1회성 산출물 삭제·이동·가드 무력화 0), 본 블록이 그대로 이행했다. 착수 시 AST 재확인 = module-level 부작용은 **`sys.path.insert(0, HERE)` 1건뿐**(파일시스템·데이터 영향 0 — cowork 의 「부작용 0」 서술을 이 1건으로 정밀화한다) · `if __name__` 가드 **L1210** · `gate_g0` 경로 리터럴 = `manifest.json` **뿐**, `_sealed` 미접근 · `open_sealed`/`emit_sign` **0** · `gate_holm` 은 `decision.py` **`ast.parse`+`literal_eval` 판독만**(import·실행 아님). **합격기준 6항 전건 PASS** — `sap_version` **1.2** · `n_modules` **11** · `n_module_mismatch` **0** · manifest 기대 `d08dcedf2a22e1c8` = live **일치** · G0 나머지 **8종 전건 일치** · `gate_holm` pass **true** · `n_labels` **7**.

   - **⑦ ★ 이탈기록 — divergence 2건은 «손대지 않고 기록만»** (사용자 확정 2026-08-25 · `docs/102` 【대체 5】):
     **divergence-A** — `pre_unblinding_audit.py` L66 `SEALED_BASELINE_ARTIFACTS` **273** / L67 `SEALED_BASELINE_TOTAL` **288** vs live **275 / 291**. **미갱신.** 사유 = 이 상수는 stale 하드코딩이 아니라 **블록 X 감사가 실제로 커버한 범위의 사실 기록**이다(`sealing_completeness_audit.json` 실측 `n_sealed_files` **273** · `n_total` **288** · `n_missing` **0** · `n_unexpected` **0** · `blocking_findings` **0**). **감사 재실행 없이 숫자만 275/291 로 갱신하면 커버리지에 대한 거짓 기록**이 된다(`CLAUDE.md` §10-1 위반). 블록 AM 러너가 고치지 않은 판단이 옳았다.
     **divergence-B** — L61 `G0_EXPECT["…/post_interim_freeze_v1_0.status.json"]` = **`a12fee2cdfd71350`** vs live **`dbb00d540d7436e5`**. **미갱신.** 사유 = R2 mandate(`docs/99` §3 = manifest sha16 · `sap_version`) 밖 · **자체 구제 금지** · divergence 증거 보존. **R2 무관·선재**임의 근거 = 해당 파일 mtime **2026-08-07 11:13** · `docs/82_docs55b_m1b_fix_and_a5_relabel_report.md`:**26** 이 같은 파일을 `dbb00d540d7436e5` 로 대조해 **G0 10/10 PASS** 로 기록(2026-08-07) · `docs/99` §1③·§2#3 도 실측 `dbb00d540d7436e5` 를 **신규 등재 대상**으로 등록. ★ **반사실 대조를 실행으로 제시**했다 — R2 «착수 이전» 기대값(롤백 스냅샷의 `G0_EXPECT`)으로 R2 «착수 이전» 상태(`_rollback/manifest.json` + 구 `freeze.py`)를 판정해도 **동일하게 이 1건만 불일치**한다(스크래치패드 재구성 트리에서 실행 · live 트리 무변경). → **§6 롤백 미발동** · 「선재 divergence」로 분류.
     **★ 개봉 전제 결손(후속 블록 사안으로 상신)** — 블록 X 개봉 전 감사(2026-08-07 09:52) **이후에 봉인이 추가**됐다: `experiments/runs/v3_stratification_axes/_sealed/{checkpoint.jsonl,axes_result.json}`(2026-08-08 15:49) + access.log **3건**(2026-08-08 16:22, `v3_confirm_rest_consensus_rep123`·`v3_stratification_axes`·`v3_consensus_rep123`). 즉 **live 275/291 중 감사가 해싱·대조한 것은 273 뿐**이며, **봉인 산출물 2건이 개봉 전 감사에 커버되지 않았다.** → **개봉 전에 감사 재수행이 필요하다.** ★ **본 블록에서 감사 재수행 0**(범위 밖) — 사실만 상신한다.

   - **⑧ live src 3파일 기대값 갱신 — 7행**: `pre_unblinding_audit.py` **L64·L121**(`224a5c8b81cf0b58…`) · `rqint_package_gates.py` **L35**(`7d0823b8060a6ab9…`) · `rqint_calibration.py` **L138·L717·L892·L1328**(`1adf999f6a2ea19e…`). 세 파일 **크기 불변**. 변경 내용은 `756d485feb4715e9`→`d08dcedf2a22e1c8` 와 `"1.1"`→`"1.2"` **두 종류뿐**. ★ **`docs/99` §3 목록 안만 갱신**했다(`docs/102` §4-30 축자 「`docs/99` §3 대상 2곳만 변경」). 목록 밖 **표시 문자열 2행은 미변경** — `pre_unblinding_audit.py`:959 로그 문면 「SAP 1.1 11모듈 일치」 · `rqint_package_gates.py`:5 docstring 「SAP manifest 756d485feb4715e9」. 둘 다 **게이트가 아니라 표시 문자열**이고, 959 는 `main()` 안이라 1회성 가드로 **출력되지 않는다**. 블록 AM 은 이 2행을 함께 갱신했으나(그쪽 §5-2) 본 블록은 `docs/102` §4-30 을 우선했다 — **stale 표시 문자열 2행이 남아 있다는 사실을 여기 기록**하고 후속 정정 사안으로 남긴다. `rqint_calibration.py`:83 `BASE_STRENGTH = 1.1`(합성 예측 기저 강도, 실수)은 **손대지 않았다.** ※ 이미 완주한 블록의 러너(`confirmatory_oof_*`·`null_main_run`·`stratification_run`·`strata_accounting_check`·`rqint_timing`·`record_block_*` 14종·완료 블록 스크립트 7종)는 **재실행하지 않으므로 갱신 대상이 아니다**(`docs/99` §3 분류 2·3·4) — **무처리**.

   - **⑨ R3 프로브 패키지 재동기화**: `freeze.py` 가 바뀌어 `r3_package/sap/freeze.py` 사본이 발산 → **14파일 재대조 후 발산 1건만 갱신**, 종료 시 **14/14 live 재일치**. zip 을 **블록 AG 와 동일한 결정적 방식**으로 재생성했다(`ZipInfo(date_time=(2026,8,14,0,0,0))` · 경로 정렬 · `external_attr` `0o644<<16` · `create_system` 3). ★ **방식을 먼저 검증**했다 — 동기화 전 현재 디렉터리로 재생성하니 기존 zip `fcbcaeea6c6158de…`(72,281 B)가 **바이트 동일 재현**됐다(compresslevel 무관). 새 zip = **`a94b04f53ba5e392…`(72,280 B · 19파일)**, 2회차 생성 **바이트 동일**(결정성 확인). **기대 해시 파일 동봉 0건.** `docs/33` **항목48 의 구 sha256 `fcbcaeea6c6158de` 에 대한 superseding append 가 본 줄이다**(항목48 문면 **무수정**). ★ **메일 2 미발송이라 외부에 배포된 구 패키지는 없다.**

   - **⑩ 동결 산출 3종**: **(1)** `v3_Multimodal/config/rqint_procedure_decisions_v1.json`(`16776f21df6ae29b…` · 22,062 B) — `.DRAFT` 를 뗀 동결본. `still_unspecified` **3건 종결** = `B` **동전 벡터 수 100,000**(참조분포 200,000 · 실측 19.4887 h ≤ 24 h 로 D15 하향조항 미발동) · C0~C3 복제수 **primary 2,000 / sensitivity 1,000**(★ 사후 선택 아님 — 설계 동결 2026-08-12 **22:25:21** 이 첫 시뮬 세션 시작 **22:46:44** 보다 **21분 23초 앞선다**) · R3 제2자 **<SECOND-PARTY> 학생**(지도교수 승인 2026-08-12 18:34:47 KST · `<GMAIL-MSGID>`). **v0 는 0바이트**(`951b302a2d474361…` 불변) · `supersedes` 로만 연결. 조건 R1·R2·R4·R5·R6 = **satisfied**, **R3 = pending**(제2자 독립 재실행 자체는 미이행). 구 DRAFT 는 `experiments/rqint/r2_freeze_3/rqint_procedure_decisions_v1.DRAFT_superseded.json` 로 이관 보존. **(2)** `docs/100_sap_1_2_amendment.md`(`5f773f98e93ae067…` · 16,637 B) — §8 개정문 **확정본**(영문+국문 대역). 빈칸 **0** = **2026-08-10** / **<EXTERNAL-REVIEWER>** / **Ph.D.** / **GIIC**, ★ **승인일 2026-08-10 ≠ 서명일 2026-08-12** 주석 병기. 해시 문장 = **A-1 문안 + B-2 문안**(플레이스홀더 제거). R5 4요소·**R4**(Holm 이중보고 A/B — ★ `holm()` **코드 수정 0**, 입력만 달리 호출)·**D19**(τ0.01 **0.250**/τ0.02 **0.735**/τ0.03 **0.9725** → τ=0.02 = **중간단**, 최하단 조항 **미발동**, 0.80 미달이므로 관례적 충족 주장 **금지**)·**D21**(대표 unit 3 = **(201,4)·(202,1)·(203,0)** · `training_seeds_ordered` **5** · RQ-int 는 3 seed × 3 repeat)·**D22**(`e_g` 선형화 부호뒤집기 = **보조 진단 전용**)·★ **KS 정직 기재**(`C0:prop` KS p **0.052446940943157605** = 기준 0.05 **바로 위**, 여유 **+0.002447**; `C0:ratio` 는 0.38126) 전건 수록. ★ **부호의 «방향» 값은 문서 어디에도 적지 않았다**(블라인딩 유지). **AF-DEV-1 미상신 결정**은 **항목50 참조만**(중복 기입 0). **(3)** `experiments/sap/sap_1_2_hash_registry.json`(`855616a27ff1f8fa…` · 17,578 B) — `docs/99` 범주 ①~⑤ **51항목** + **실질 신규 등재 6건**. ★ `reviewer_identity_resolved.json`(§8 빈칸 원천)·`sign_disclosure_matrix.json`(R5 근거) **전건 포함**(프로그램 assert). append-only **4건**은 **「동결 시점 스냅샷」 지위**로 별도 표기(고정 해시 동결 불가 — 이후 append 로 값이 바뀌는 것이 정상이며 불일치를 무결성 위반으로 판정하지 않는다. ★ 본 항목 기입으로 `docs/33`·`docs/45`·`docs/55b`·`ledger.json` 4건의 live 해시는 원장 스냅샷값과 **즉시 달라진다** — 설계된 동작이다).

   - **⑪ 바뀐 것 / 바뀌지 않은 것**: **바뀜** = `freeze.py` **1행**(`8bef5f70d168c50d…`) · `manifest.json`(**`d08dcedf2a22e1c8…`** · 재생성+erratum) · `sap_version` **1.1→1.2** · live src **3파일 7행** · `r3_package.zip`(**`a94b04f53ba5e392…`**) · `r3_package/sap/freeze.py` 사본. **안 바뀜** = **`decision.py` 포함 SAP 분석 모듈 10개 0바이트**(`decision.py` `f688b20d816acabe` 불변) · 봉인 **291/275**(stat-only 착수=종료 `diff` **차이 0**) · 확증 산출물 전부 · **Holm family 7** · α · 성공기준 · primary estimand · 기존 `model_family` **14곳** · `pre_unblinding_audit.py` **L61·L66·L67** · 1회성 산출물 2종(mtime 2026-08-07 09:52 · 2026-08-14 13:53) · `rqint_procedure_decisions_v0.json` · **HEAD `566f487` · 커밋 21**.

   - **⑫ 미실행(본 블록이 하지 않은 것)**: **개봉 0**(`unblinding_performed` **false** · `_sealed/` 읽기·쓰기 0 · stat-only 291종 착수=종료 동일 · `open_sealed` 0 · `emit_sign` 0) · **GIN 착수 0**(`gin_start_still_blocked` **true**) · **확증 데이터 로드 0** · **모델 학습·추론 0** · **순열 계산 0** · **성공판정·다중성 보정 0** · 확증 산출물·봉인 데이터에 대한 **`decision.py` 호출 0**(`freeze.py` 검증 경로의 **합성 fixture A11 진리표는 허용** — `docs/101` §2 대체 문면, AST 미접근 True) · **`main()` 호출 0** · **1회성 산출물 삭제·이동·재생성 0** · **가드 무력화 0** · **봉인 감사 재수행 0** · **R3 제2자 실행 0**(패키지 재생성까지만) · **메일 발송 0** · **네트워크 0** · **`data/raw/` 변경 0** · **`git commit`/`push` 0**. 기입 시각 2026-08-25 15:31:53 KST.

> 지시서 = `docs/102_r2_al5_verification_delta_prompt_for_vscode.md`(2차 델타) · `docs/101_...resume_prompt_for_vscode.md`(1차 델타) · `docs/100_r2_sap12_freeze_prompt_for_vscode.md`(정본) · 리포트 = `docs/102_r2_al5_verification_delta_report.md` ·
신규 동결 = `experiments/sap/manifest.json`(`d08dcedf2a22e1c8…` · `sap_version` **1.2**) · `v3_Multimodal/config/rqint_procedure_decisions_v1.json`(`16776f21df6ae29b…`) · `docs/100_sap_1_2_amendment.md`(`5f773f98e93ae067…`) · `experiments/sap/sap_1_2_hash_registry.json`(`855616a27ff1f8fa…`) · `experiments/sap/sap_manifest_erratum_d20.json`(`91e764404feaa8fa…`) · `v3_Multimodal/src/sap_manifest_erratum.py`(`9cd4bb6f2b8f253d…`) · `experiments/rqint/r3_package.zip`(`a94b04f53ba5e392…`) ·
무수정 대조 = SAP 분석 모듈 **10종 0바이트**(`decision.py` `f688b20d816acabe` 포함) · `rqint_procedure_decisions_v0.json` `951b302a2d474361` · `pre_unblinding_audit.py` **L61·L66·L67** · 봉인 **275/291** stat-only 착수=종료 동일 · 블록 AL 증거 12파일 + 블록 AM 증거 22파일 = **34파일 0바이트**(`shasum -c` OK) · HEAD `566f487`·**21**. **미실행**: 위 ⑫ 전항.

---

54. **★ 개봉 전 감사 재수행 — 봉인 완전성 점검 v2 (블록 AO — `docs/103` · live 275/291 전체 대조 · 개봉 0)**:

   - **① 이 항목이 기록하는 것 — 항목53 ⑦ 「개봉 전제 결손」의 해소**: 블록 X 개봉 전 감사(`experiments/provenance/sealing_completeness_audit.json` · `b189f77f30dce9b5…` · 2026-08-07 09:52:20 KST)는 봉인 **273/288** 만 해싱·대조했고, 그 뒤 블록 Z 가 봉인 산출물 **2건**(`experiments/runs/v3_stratification_axes/_sealed/{axes_result.json, checkpoint.jsonl}` · 2026-08-08 15:49:09 KST)과 access.log entry **30건**을 더 남겼다. 본 블록은 **지금 있는 봉인 275/291 전체**를 대상으로 같은 점검을 다시 수행해 개봉의 선행요건을 채운다. 같은 ⑦ 의 divergence-A·B 처리도 함께 기록한다(③). 신설 = `v3_Multimodal/src/pre_unblinding_audit_v2.py`(`13cf681aab2a5e94…` · 65,156 B · 1,243행). 산출 = `experiments/provenance/sealing_completeness_audit_v2.json`(`a7fba492765e7993…` · 118,751 B) · 공개요약 `experiments/runs/v3_pre_unblinding_audit_v2/audit_public.json`(`a985570cde580f4b…` · 2,949 B).

   - **② 판정 — PASS**: `verdict` **PASS** · `blocking_findings` **0건**. 기대 목록 **275**(v1 `build_expected()` G1~G12 **273** + 신설 **G13** 2) · live 산출물 **275** → **missing 0 · unexpected 0**. 블록 X 대비 `added` **2**(위 두 봉인 경로) · `removed` **0**. 해시 대조 = 산출물 **275종 전건 해싱** · 기록 보유 **275/275**(`files_without_recorded_hash` **0**) · 대조 **862쌍**(v1 `recorded_hashes()` 313 + R-a 273 + R-b 273 + R-c 1 + R-d 2) · **불일치 0** · `recorded_but_absent_in_live` **0** · `changed_since_block_X` **0**(= 블록 X 가 해싱한 273 종이 지금도 바이트 동일). 열람 = access.log **16파일 / 121 entry** · `type` **machine_read 단일** · `human_exposure` true **0** · `"OPEN sealed"` 부분문자열 **0** · 귀속 불가 신규 entry **0**. model×fold×seed 교차대조 **5군 전건 `set_equal` true**(v1 4군 + G13 — G13 은 `key` 집합 40 일치 · 중복 0 · 시각 역행 0). G0 v2 **13행**(동결 12파일 + SAP 판정) 착수·종료 모두 일치 · SAP `1.2` 11모듈 불일치 0 · G-HOLM `n_labels` **7** · 봉인 스냅샷(경로·크기·mtime·sha256) **착수=종료 동일**.

   - **③ v1 무수정 원칙과 그 근거 — divergence-A·B 는 v1 에서 계속 미갱신**: v1 `pre_unblinding_audit.py`(sha256 `224a5c8b81cf0b58…`)의 `SEALED_BASELINE_*` **273/288** 과 `G0_EXPECT` status 해시 **`a12fee2cdfd71350`** 는 stale 하드코딩이 아니라 **블록 X 가 실제로 대조한 범위를 적은 역사 기록**이고(항목53 ⑦), v1 의 sha256 자체가 R2 가 새로 정한 불변식이다(항목53 ⑧). 또 v1 `main()` 첫 문장(L947)이 1회성 가드라 산출물 2종이 있는 한 `rc=2` 로 즉시 종료되고 산출물 삭제·이동은 금지다(블록 AM 선례). → **v1 을 고치지도 재실행하지도 않고**, v1 을 **읽기 전용 모듈로 import** 해 순수 함수만 재사용하는 v2 를 신설했다(`V1.main`·`gate_g0`·`hash_crosscheck`·`build_sign_matrix`·`verify_public_exposure` 호출 **0** · `V1.<이름> = …` 모듈 전역 재할당 **0** · `numpy`·`pandas`·`sap`·`axes_stratification_run` import **0** — AST 로 확인). 실행은 **`--dry-run` → `--write` 2단계**로, 1회성 가드는 `--write` 분기 첫 문장에만 뒀다(파싱 결함을 쓰기 전에 잡고, 「실행 후 통과」 요구가 재실행 금지와 충돌하는 계열 결함 — AJ-2-b·AL·AL-5 — 을 작성 단계에서 막는 장치). 종료 시 v1 스크립트와 v1 산출물 4종(`sealing_completeness_audit.json` `b189f77f30dce9b5` · `sign_disclosure_matrix.json` `147d5d5f62edf84a` · `v3_pre_unblinding_audit/audit_public.json` `3d07cc6bacba719c` · `record_public.json` `f67ee01ce6c2c10b`) **전건 바이트 보존 확인**. → **v1 에서는 divergence-A·B 를 계속 미갱신으로 두고**, v2 가 현행값(**275/291** · status `dbb00d540d7436e5`)으로 대조를 끝냈으므로 **개봉 전제로서는 해소**된다. status 해시 전이의 경위도 산출물 `gates.status_sidecar_transition` 에 기록했다(블록 Y 의 superseding append · `from` false → `to` true · `ts_kst` 2026-08-07 11:13:28 KST · `basis.block` "Y" · `docs/82_docs55b_m1b_fix_and_a5_relabel_report.md`:26 이 같은 값으로 G0 PASS 기록).

   - **④ ★ 감사 범위 밖의 봉인 사본 발견 — 처분 = 보존 + 문서화**: 저장소 전체(`.git` 제외 · `_sealed/` 원본 제외 · 심볼릭 링크 미추적)를 크기로 거르고 sha256 으로 확인한 결과, 봉인 산출물의 **바이트 사본이 `backup/v3_sealed_backup_20260727/rep1_seed201_sealed/` 에 3파일**(`metrics_full.json` `8722a4e1c52d2eae` · `oof_M1b.npz` `b2a61ba846eead5f` · `oof_M2b.npz` `350fa12fac84ef4c`) **/ 동일 쌍 4개** 있었다(4번째 쌍 = `oof_M2b.npz` ↔ `v3_null_probe/_sealed/oof_M2b_identity.npz` — identity 대조 설계상 정상). 스캔 **131,562 파일 · 해시 계산 245 파일**. `sealed` 이름 디렉터리는 **2개**이고 그 안의 파일은 **정확히 7개**(위 3 + 사본 `access.log` `9a182b691f371325` + 기록물 구본 `provenance/{first_look_log.json,ledger.json}` **해싱만·파싱 0** + `SHA256SUMS.txt` `5f74ae7a72607697`). 사본 디렉터리 `access.log` = entry **6** · 전부 `machine_read` · `human_exposure` true **0** · `"OPEN sealed"` **0** · 마지막 2026-07-27 21:16:18 KST. 백업 자체 무결성 `SHA256SUMS.txt` 대조 **6/6 OK**. **`docs/33`·`docs/45`·`docs/78` 어디에도 기록이 없었다 = 블록 X 는 이 사본을 보지 않았다.** 사전 명시한 판정 규칙 ⓐ~ⓓ 전건 충족 → `verdict` **`non_blocking_recorded`**. **처분 = 보존 + 문서화(사용자 확정 2026-09-10)** — 삭제·이동·권한 변경 **0**, 착수=종료 sha·크기·mtime 동일. 근거 = 원본과 바이트 동일하고 열람 흔적은 기계 판독뿐이며, 2026-07-27 시점 해시를 담은 독립 사본이라 **원본 무변경의 보조 증거**가 된다. 문제는 사본 존재가 기록되지 않았던 점이므로 본 감사 산출물과 이 항목 기재로 해소한다. ★ **주의 — 앞으로 이 사본을 사람이 열면 원본을 여는 것과 똑같이 개봉이다.** `_sealed/` 밖이라 access.log 가 자동으로 남지 않으므로 더 위험하다.

   - **⑤ access.log +30 의 귀속과 ★ 항목53 ⑦ 「access.log 3건」 정정**: 블록 X(15파일/91 entry) 이후 늘어난 **30 entry** 는 `v3_confirm_rest_consensus_rep123` +5 · `v3_consensus_rep123` +10 · `v3_stratification_axes` 신규 15 로, **30건 전부** `type`=machine_read · `human_exposure`=false · `actor`=vscode-claude · `step`=「등록 §11 세 번째 축 — A3·A4·A5·A6 층화(블록 Z)」 **단일 조합**이고 ts 범위는 2026-08-07 12:29:55 ~ 2026-08-08 16:22:52 KST 다 → **전량 블록 Z 에 귀속**, `unattributed` **0**. 기존 15파일은 앞부분 행이 하나도 줄지 않았다. 블록 Z 실행 사건 **2건을 `known_failure_and_restart_events` 에 등재**(합계 3 → **5**): **(1)** 선행 세션(2026-08-07 12:05~12:29 KST 에 Z-2 + `--stage verify` 까지)에서 Δ 산출 0 인 상태로 같은 블록이 **재개** — 2회차 실행 아님(`docs/81` §5 편차 1 · `gates_public.json` `ts_kst` 2026-08-07 16:56:39 KST · 체크포인트 40행 · key 중복 0). **(2)** 공개요약 코드 결함 교정 재진입(2026-08-08 16:22:50→16:22:53 KST · stage=estimate · rc=0)이 **40/40 SKIP** 으로 통계 재계산 0 · 봉인 재작성 0(`sealed_result_rewritten_this_run` false · `axes_result.json` sha16 `5c1aa8e24cd5ca9c` 가 `docs/81` §3 기록과 동일) — 이 재진입이 2026-08-08 16:22:52 KST entry 를 남겼다. `launcher.log` 에서 `stage=estimate` 세션 **2개**를 독립 추출해 대조했다. ★ **항목53 ⑦ 문면 정정** — 거기 적힌 「access.log **3건**(2026-08-08 16:22)」의 **3 은 파일 수**이고, entry 로는 그 시각 **6건**이며 블록 X 이후 전체 증가분은 **30건**이다. 항목53 문면은 append-only 원칙상 **고치지 않고** 이 항목에서 바로잡는다.

   - **⑥ 미실행(본 블록이 하지 않은 것)**: **개봉 0**(`unblinding_performed` **false** 유지 · `gin_start_still_blocked` **true** 유지) · **새 부호 산출 0**(Δ·macro AP·CI·p 계산 0 · `emit_sign` 0 · `open_sealed` 0 · `sap/decision.py` import·호출 0 — `V1.gate_holm()` 의 AST 판독은 import·실행이 아니다) · **봉인 값 판독 0**(`.npz`/`.npy` 역직렬화 0 · 봉인 `*_result.json`·`metrics_full.json`·`lambda_selected.json` `json.load` 0) · **`_sealed/` 쓰기 0**(추가 파일 0) · **모델 학습·추론 0** · **Holm ⑧ RQ-int 0** · **GIN 착수 0** · **R3 제2자 실행 0** · **v1 스크립트·v1 산출물 수정 0** · 항목53 ⑧ 의 **stale 표시 문자열 2행 정정 0**(사용자 결정 대기 — 범위 밖) · **`sign_disclosure_matrix.json` 재생성·수정 0** · **`first_look_log.json` append 0**(조회가 아니므로 pre-look 항목도 만들지 않는다) · **status sidecar 수정 0** · **`backup/` 사본 처분 0** · **네트워크 0** · **`data/raw/` 변경 0** · **`git commit`/`push`/`add` 0**(HEAD `566f487` · 커밋 **21** · `git ls-files -m` **4건** 착수=종료 동일). 기입 시각 2026-09-10 21:15 KST. ★ **절차 이탈 자진신고 1건** — 최종 상태 점검에서 `git status --porcelain` 을 **1회** 실행했다(지시서 절대금지 5 는 `status` 를 인덱스 접촉 명령으로 금지하고 `rev-parse`·`rev-list --count`·`ls-files -m` 만 허용). **commit·add·stash·push 0** · HEAD `566f487` · 커밋 **21** · `git ls-files -m` **4건** 착수=종료 동일 · 작업트리·봉인·산출물 무변경 · 본 블록 신규 산출물은 전부 `.gitignore` 대상. 자체 구제 0, 리포트 `docs/103_pre_unblinding_reaudit_report.md` §5 에도 동일 기재.

   - **⑦ 봉인 접촉 기록(전건 값 판독 0)**: **ⓐ** cowork 사전 실측(2026-09-10) — 봉인 산출물 275종 **바이트 해싱** · 백업 사본 해싱 · `v3_stratification_axes/_sealed/checkpoint.jsonl` **키 허용목록 투영 판독 1회**(`key`·`ts_kst` 만, 값 출력 0). **ⓑ** cowork 교차검증 에이전트(같은 날) — 해싱과 access.log 파싱만, checkpoint 파싱 0. **ⓒ** 본 블록 v2 실행(`--dry-run` 1회 + `--write` 1회) — 봉인 275종 해싱(착수·종료 각 1회) + `checkpoint.jsonl` **5파일 키 허용목록 투영**(`V1.read_ckpt` · 허용목록 밖 `sealed`·`public`·`macro_AP`·`delta` 등은 메모리에도 적재하지 않음) + access.log 전체 파싱(메타데이터). ★ ⓐ~ⓒ 전부 **access.log 미기록** — v1 `read_ckpt` 선례와 같다(해싱·키 투영은 `open_sealed` 경로가 아니라 기록 훅이 없다). 이 사실 자체를 여기 남긴다.

> 지시서 = `docs/103_pre_unblinding_reaudit_prompt_for_vscode.md` · 리포트 = `docs/103_pre_unblinding_reaudit_report.md` ·
신규 산출 = `v3_Multimodal/src/pre_unblinding_audit_v2.py`(`13cf681aab2a5e94…`) · `experiments/provenance/sealing_completeness_audit_v2.json`(`a7fba492765e7993…`) · `experiments/runs/v3_pre_unblinding_audit_v2/audit_public.json`(`a985570cde580f4b…`) ·
무수정 대조 = `pre_unblinding_audit.py` `224a5c8b81cf0b58…` · v1 산출물 4종 · 봉인 **275/291** 착수=종료 동일 · `backup/` 7파일 · `first_look_log.json` `4f6d8bd9c286ebc6`(13 entry) · status sidecar `dbb00d540d7436e5` · HEAD `566f487`·**21**. **미실행**: 위 ⑥ 전항.

---

55. **★ R3 본 드라이런 사전 동결 — 패키지 · 로컬 기준값 · 판정기 (블록 AP — `docs/104` · 트리거(메일 3 발송) 이전 · 판정 0)**:

   - **① 프로브(메일 2) 경과 — ★ 판정 아님**: 스레드 `<GMAIL-MSGID>` 를 `get_thread` 로 재실측(2026-09-14 00:2x KST)해 **6건 전수** 확인했다. **M1** outbound `<GMAIL-MSGID>` 2026-09-10 16:03:50 KST(07:03:50Z · 첨부 0 · **신규 스레드** — 2026-08-14 발송분 `<GMAIL-MSGID>`/스레드 `<GMAIL-MSGID>` 가 무회신이라 문면을 재사용한 리마인드) · **M2** inbound `<GMAIL-MSGID>` 20:36:40 KST(환경명세 회신 = Python **3.14.2** MSC v.1944 AMD64 / Windows-10-10.0.19045-SP0 / AMD64 / Intel64 Family 6 Model 158 Stepping 12 / numpy **2.4.0** / **sklearn not installed** / scipy 1.16.3 + 「후속 요청은 이 스레드 답장으로」 요청) · **M3** outbound `<GMAIL-MSGID>` 21:29:42 KST(**메일 2 = 프로브 패키지 발송** · 첨부 `r3_package.zip` application/zip 1건 · sizeEstimate 118,836 · venv 4줄 + `-X utf8` + 회수 3파일 + 기대값 미동봉 명시) · **M4** inbound `<GMAIL-MSGID>` 23:16:36 KST(회수 3첨부) · **M5** outbound `<GMAIL-MSGID>` 2026-09-11 00:49:09 KST(수령 감사 · 「이번에 만드신 환경에서 그대로」) · **M6** inbound `<GMAIL-MSGID>` 00:52:11 KST(Gmail 이모지 반응 ❤️). 프로브 결과(`experiments/rqint/r3_package_meta/probe_compare_second_party.json`) = 제2자 실행환경 **Python 3.12.9 · numpy 2.5.0 · sklearn 1.9.0 · scipy-openblas 0.3.33.112.0 · Windows-10-10.0.19045-SP0**(메일 1 회신의 3.14.2/np2.4.0 과 다름 — venv 를 `python`(=3.12.9)으로 만든 것으로 보임), **R6 6항 전항 PASS**, 제2자 `numeric_core` `8b5fb0bf28c4…`(12,794 B) ≠ 로컬 `3745438643aa…`(12,774 B). **원인은 `code_scan` 파일 라벨의 경로구분자 20곳뿐**(`per_file` 키 14 + `s2_string_literal_hits[].file` 6 · +20 B · 비제외 필드 그 외 차이 0)이고 `\`→`/` 정규화 시 로컬과 **완전 일치** → 수치는 Windows/OpenBLAS ↔ macOS/Accelerate 에서 비트 동일. ★ **이 결함은 프로브 러너(`run_rqint_probe.py:134` `os.path.join("sap", f)`) 한정이며 본 드라이버에는 없다** — `v3_Multimodal/src/run_rqint_audit.py` **L36–37** 은 `NEW_FILES = ["sap/rqint.py", "sap/rqint_synthetic.py", "sap/rqint_audit.py", "run_rqint_audit.py"]` 리터럴이다(러너 실측). ★ 프로브는 **R3 판정에 쓰지 않는다**(`v3_Multimodal/config/r3_second_party_freeze.json` `probe_package._doc` 축자: 「R3 판정 0 — 프로브는 플랫폼 적합성 확인 전용」). ★ **프로브 미실행 R6 = R6-3 · R6-4 · R6-8 의 3건**(프로브 `r6` 키 6 vs 본 감사 9 — 러너 실측). 지시서 `docs/104` ⑩ 은 이를 「R6-4·R6-8」 2건으로 적었으나 실측은 3건이므로 **R6-3 을 포함해 기록**한다. 곧 이 3항은 Windows 동일성이 아직 확인되지 않았다.

   - **② 패키지 — 20파일 · 저장소 레이아웃 · 결정적 zip**: 배포본 `experiments/rqint/r3_main_package.zip` sha256 **`4b474b3d7f098c67fa3bae1c1d8a9dadb0bce3ad7f978ae911ad450307999948`** · **73,746 B** · 엔트리 **20**(디렉터리 엔트리 0). 매니페스트 `experiments/rqint/r3_main_package_meta/package_manifest.json` sha256 **`5cc58d1fc9356414b83050d33e237f1035c01b30425794644555f062868fe895`**(5,470 B · `expected_values_included` false · `externally_distributed` false). 구성 = 동결 드라이버 `run_rqint_audit.py`(`ab831c2726a36e8a…`) + SAP 11모듈 + rqint 3모듈 + `canonical.py`·`collect_env.py`(프로브 패키지에서 바이트 그대로) + cowork 작성 입력 3종(`README_R3_MAIN.md`·`package_hashes.py`·`requirements_r3.txt`). **저장소 레이아웃(`v3_Multimodal/src/…`)을 그대로 쓴 이유** = R3 축자가 「**동결 해시로부터** 동일 산출」이라 새 러너를 만들지 않고 동결 드라이버를 바이트 그대로 동봉해야 하는데, 그 드라이버가 `ROOT = HERE/../..`(L20) 아래 `experiments/rqint/`(L35·L339)에 쓰므로 같은 레이아웃이어야 산출이 패키지 폴더 안에 떨어진다. ★ **저장소 원본 드라이버는 직접 실행하지 않았다**(L339 가 블록 AC 산출물을 덮어쓴다) — 로컬 기준 실행은 zip 을 **저장소 밖 임시 디렉터리**에 푼 사본으로만 했다. 검사 = 스테이징 20파일 sha256 **20/20** 일치(복사 원본 착수=종료 동일) · 부산물 0 · 경로 목록이 `package_hashes.py` 의 `PACKAGE_FILES`(AST 리터럴 판독 · import·실행 0)와 **순서까지 동일** · `package_hashes.py` AST 제약 PASS(import = `__future__`·`hashlib`·`json`·`os`·`sys` 뿐 · `open()` 은 `"rb"` 1곳 + `"w"` 1곳 · 네트워크 모듈 0) · 패키지 안 `data/`·`_sealed`·`experiments/` 경로 0. **기대값 미동봉** — 20파일 바이트 전체에서 `fd488eb4`·`3745438643aa`·`8b5fb0bf28c4`·`921e16ea8191`·`a94b04f53ba5`·`4b474b3d7f09` **6종 전건 0건**. ★ **zip 결정성 3플랫폼 재현** — cowork 가 클라우드 Linux x86_64(Python 3.11.15/zlib 1.3 · 3.14.0rc2/zlib 1.3.1)에서 같은 recipe 로 만든 예측값과 본 실행(macOS arm64 · Python 3.14.4 · **zlib 1.2.12**)의 산출이 **sha256·바이트 수 모두 동일**했다. recipe = 이름 정렬 · `date_time` (2026,9,11,0,0,0) 고정 · `external_attr` `0o644<<16` · `create_system` 3 · `ZIP_DEFLATED` · 디렉터리 엔트리 0.

   - **③ 로컬 기준값 — 블록 AC 와 일치(L2 PASS)**: `numeric_core` sha256 **`fd488eb429a71990d47ebf321efeb1f34083bbeb4813730a76777262b1ba878b`** · canonical bytes **7,493** — (a) 패키지 `canonical.py` 가 쓴 `audit_numeric_core.sha256` 파일값과 (b) 스테이징 `canonical.py` 를 경로로 로드해 재계산한 값이 **둘 다** 블록 AC `experiments/rqint/audit_r6.json`(`921e16ea8191…`)의 값과 같다. 실행 = `.venv/bin/python3`(3.14.4 · numpy 2.5.0 · sklearn 1.9.0 · BLAS/LAPACK **accelerate**) · c1~c4 `returncode` 전건 0 · c2 벽시계 **1,031.05 s**(드라이버 자기기록 `wall_clock_seconds` 1,030.18) · 전체 2026-09-14 00:28:29 → 00:45:41 KST · 시도 **1회**(끊김 0 · `.compute_lock.stale.jsonl` 착수=종료 689 B). 산출물 검사 L1(`r6_all_pass` true · `r6` 9키 전부 `pass` true · `synthetic_only` true · `confirmatory_data_accessed` false · `unblinding_performed` false · `gin_start_still_blocked` true) · L3(`n_missing` 0 · 20/20 = manifest) · L4(스테이징·zip·AC `audit_r6.json`·`run.log` 착수=종료 sha256 동일) · L5(봉인 275/16/291/25 착수=종료) · L6(임시 디렉터리 신규 파일 **정확히 5개** · 원래 20파일 불변 · `__pycache__` 0) 전건 성립. 리프 실측도 블록 AC 와 같다 — audit 전체 str 93 / float 49 / bool 39 / int 21 / null 1, `numeric_core` str 85 / float 46 / bool 39 / int 21 / null 1(리스트 20), 0.0 인 float **9개**. ★ **부수 관측(판정 무관)** — 본 실행의 `versions.platform` 은 `macOS-26.6.2-arm64-arm-64bit-Mach-O` 로 블록 AC 의 `macOS-26.5.2-…` 와 다르다(OS 마이너 갱신). `/versions` 는 제외 pointer 이고 G-ENV 5필드에도 platform 이 없으므로 `numeric_core` 와 L7 판정에 영향이 없으며, 실제로 해시가 일치했다.

   - **④ 판정기 운용화 선언 — `r3_judge.py`(`df26e946d17cd0b5…` · 25,828 B)**: freeze 2차의 항목 목록(「각종 count」「모듈 sha256」 등)은 `audit_r6.json` 필드로 기계 대응이 되지 않고 **「모듈 sha256」은 `audit_r6.json` 에 아예 없다.** 그래서 (a) `numeric_core` **전 리프를 타입 규칙**으로 판정하고(bool·int·str·null 완전 일치 / float 상대오차 `|a−b| / max(|a|,|b|,1e-12) ≤ 1e-9` / 키 집합·리스트 길이 완전 일치) (b) 패키지에 `package_hashes.py` 를 넣어 **모듈 sha256 을 회수**해 `package_manifest.json` 과 대조하며(누락·불일치·여분 0이어야 통과) (c) 「sap_version」은 `/sap_version_unchanged` 완전 일치로, (d) **G-ENV 는 양쪽 값이 모두 알려진 필드만 「상이」로 센다**(누락·None 으로 2차에 진입하지 않는다). 여기에 (e) **입력 결속 검사**를 앞에 둔다(⑪). ★ **freeze 목록 항목에 대해 느슨해지는 방향은 0이다** — 목록의 `T_obs` 등은 값이 0.0 이어도 freeze 연속량 공식이 그대로 적용되며(자기검사 T15 가 1e-17 교란을 `R3_not_satisfied` 로 잡는다), 목록 **밖** 리프는 오히려 추가로 판정한다. 따라서 **amendment 가 아니다.** 1차 기준(바이트 동일)·제외 pointer 8개·허용오차 1e-9·공식·G-ENV 필드 5개는 **그대로**이고, 판정기는 기동 시 `r3_second_party_freeze.json` 해시(`0624d3dd…`)·허용오차 상수·제외 pointer 목록·G-ENV 필드 수를 정본과 대조해 어긋나면 스스로 중단한다.

   - **⑤ ★ 리터럴 고지(판정 무관)**: 드라이버 **L305** `"sap_version_unchanged": "1.1"` 과 `sap/rqint.py` **L63** `B_DEFINITION_STATUS = "still_unspecified — …"` 는 **블록 AC 시점에 박힌 리터럴**이며, SAP 1.2 현재 상태(`experiments/sap/manifest.json` `sap_version` **1.2** · `B` 정의 종결)를 뜻하지 않는다. 동결 코드 0바이트 원칙상 고치지 않으며, R3 는 **양쪽 산출의 동일성**을 비교하므로 두 값이 같기만 하면 된다(본 로컬 산출도 같은 두 리터럴을 담고 있다 — `audit_r6_local_main.json` 실측).

   - **⑥ 자기검사·자기대조·동결 해시**: `r3_judge.py --selftest` **16/16 PASS**(`judge_selftest.json` `aace4c227aee7bbb…` · 5,356 B). 케이스별 실측 = T1 `R3_satisfied_stage1` · T2 `R3_satisfied_stage2`(리프 실패 0) · T3 `R3_not_satisfied`[`continuous`] · T4 `R3_not_satisfied`[`boolean`] · T5 `stage2_forbidden_same_environment` · T6 `R3_not_satisfied`(리프 실패 0 · `package_hashes_pass` **false**) · T7 `R3_not_satisfied`[`keys`] · T8 `R3_not_satisfied`[`discrete`] · T9 `R3_satisfied_stage1` · T14 `R3_satisfied_stage2` · T15 `R3_not_satisfied`[`continuous`] · T10~T13 `input_invalid` · T16 `valid`. **자기대조 1회**(기준 파일 작성 직후 · `--write` 없음) = **exit 2 · `[input_invalid]` · 문제 정확히 2건**(「제2자 audit 파일이 우리 기준 audit 와 바이트 동일(사본)」·「제2자 host_id 가 우리 host_id 와 같음」) — 이 호출은 판정기가 기준 파일의 **판정기 sha256 · audit sha256 · env sha256 · manifest sha256 네 대조를 모두 통과한 뒤에만** 입력 검증에 도달하므로 「정확히 2건」 출력이 기준 파일 ↔ 판정기 연결 무결성의 확인이다(**판정 아님**). 기준 파일 `experiments/rqint/r3_main_package_meta/r3_main_reference.json` sha256 **`74337a3288a2479407ec8ecdbd3c5a2831edf6cf26e11028a1bf6046ea23d48c`**(2,690 B · `trigger_event_status` 「not_yet — 메일 3 미발송」 · `not_shared_with_second_party` true). `r3_verdict.json` **부재 유지**.

   - **⑦ 메일 1 문면과 실제의 차이(기록만)**: M1 본문의 「제 장비 기준 **20분**」·「회신해 주실 것은 … **JSON 파일 2개**뿐」은 프로브 기준 문면을 재사용한 것이고, 본 드라이런 실제는 **로컬 벽시계 1,031 s(≈17.2분)** · 회수물 **4개**(`env_*.json` · `experiments/rqint/audit_r6.json` · `audit_numeric_core.sha256` · `package_hashes.json` — `README_R3_MAIN.md` 기준)다. 본 패키지 README 는 이미 17분·4개로 적혀 있다. M5 본문의 「결과도 잘 맞게 나왔습니다」는 비공식 표현이며 **프로브 raw 해시는 불일치**였다(원인·정규화 후 일치 = ①).

   - **⑧ 미실행(본 블록이 하지 않은 것)**: **메일 3 발송·초안 작성 0**(cowork·사용자 소관) · **제2자 본 실행 0** · **R3 판정 0**(`r3_judge.py` 실제 판정 모드는 위 자기대조 1회뿐이고 `--write` 0 · `r3_verdict.json` 부재) · **R3 충족 기록 0** · **개봉 0**(`post_interim_freeze_v1_0.status.json` `unblinding_performed` false · `gin_start_still_blocked` true 유지) · **GIN 착수 0** · **`emit_sign` 0** · **`B` 확정 0** · **SAP 재동결 0** · **`decision.py` 호출 0** · **봉인 접근 0**(경로 나열 계수만 · 읽기·복사·해싱 0) · **`data/processed/`·`backup/` 접근 0** · **`pip install` 0** · **네트워크 = Gmail `get_thread` 읽기 전용 2회**(스레드 `<GMAIL-MSGID>` 6건 · `<GMAIL-MSGID>` 1건 · 첨부 다운로드 0 · 발신 0) **외 0** · **git commit·push·add·stash·status 0**(HEAD `566f487` · 커밋 **21** · `git ls-files -m` **4건** 착수=종료 동일) · `docs/33` 항목53 ⑧ stale 표시문자열 2행 정정 0 · `AGENTS.md` 갱신 0.

   - **⑨ 대상 교체 선언 2건(동결 파일은 무수정 — 이 항목이 superseding 기록)**: **(i)** `r3_second_party_freeze.json` `acceptance_criteria.stage_2_pre_specified_tolerance.gate_G_ENV.our_env_reference` 는 `experiments/rqint/r3_package_meta/env_local.json`(프로브 시점)이나, **본 드라이런의 우리 쪽 G-ENV 기준은 `experiments/rqint/r3_main_package_meta/env_local_main.json`** 이다. L7 실측 = 두 파일의 G-ENV 5필드(`python_version` 3.14.4 · `numpy` 2.5.0 · `sklearn` 1.9.0 · `machine` arm64 · BLAS/LAPACK `["accelerate","accelerate"]`)가 **전건 동일** → 교체는 **실질 동일**이며 판정 결과를 바꾸지 않는다. **(ii)** `rqint_procedure_decisions_v1.json` `conditions.R3.package` 와 `experiments/sap/sap_1_2_hash_registry.json` 은 프로브 zip `a94b04f53ba5e392…` 만 「R3 패키지」로 등재하고 있으나, **본 드라이런 패키지는 `r3_main_package.zip`(`4b474b3d7f098c67…`)** 이고 프로브 zip 은 **「플랫폼 적합성 프로브」 지위로 남는다**(두 동결 파일은 0바이트 수정).

   - **⑩ 잔차 리프 7개 · 0.0 취약성 고지**: `RESIDUAL_POINTERS` = 같은 양을 두 경로로 계산한 **차이**라 freeze 「연속량」 목록 밖이고 로컬값이 전부 0.0 이다. 0.0 ↔ 1.1e-16 같은 부동소수 잡음이 목록 밖 필드에서 「R3 미충족 확정」(되돌릴 수 없음)을 만드는 것을 막기 위해 **상대오차로 비교하지 않고 타입·존재만 확인**하며, 대신 각 잔차는 다른 판정 리프에 묶여 있다. 결속표(러너가 `v3_Multimodal/src/sap/rqint_audit.py` 에서 각 R6 의 `pass` 산식을 실측):

     | 잔차 pointer | 소속 | 그 R6 의 `pass` 산식(실측) | 결속 방식 |
     |---|---|---|---|
     | `/r6/R6-1/max_abs_diff` | R6-1 가환성 | L157 `ok = all_equal or max_diff < 1e-15` | 잔차가 산식에 **직접** 들어감 → 소속 `pass`(불리언·완전 일치)가 판정 |
     | `/r6/R6-4/max_abs_dev` | R6-4 여집합 반대칭 | L204 `ok = ca["draws_checked"] >= 1000 and ca["failures"] == 0` | 소속 `pass` + `failures`·`draws_checked`(int·완전 일치) |
     | `/r6/R6-5/abs_dev` | R6-5 전체 교환 | L225 `pass = bool(dev == 0.0)` | 잔차 = `dev` 자체 → `pass` 가 `dev == 0.0` 을 **완전** 판정 |
     | `/r6/R6-6/abs_dT` | R6-6 군 순서 불변 | L253 `ok = (p_relabeled == p_base) and d_t < 1e-12` | 잔차가 산식에 직접 + `p_base`·`p_relabeled` 연속량 비교 |
     | `/r6/R6-8/abs_dT_vs_naive` | R6-8 완전열거 | L293 `ok = abs(p_MC − p_exact) ≤ 3·SE + 1e-12` — ★ **`abs_dT_vs_naive` 와 무관** | **간접** — `/r6/R6-8/T_obs`(전수열거)·`/r6/R6-8/T_obs_impl`(MC)이 각각 freeze 연속량 공식으로 비교됨 |
     | `/r6/R6-9/max_abs_diff_t_star_sequence` | R6-9 독립 구현 대조 | L311 `ok = d_seq < 1e-12 and d_obs < 1e-12` | 잔차가 산식에 직접 |
     | `/r6/R6-9/abs_diff_T_obs` | R6-9 | 같은 산식 | 잔차가 산식에 직접 + `T_obs_impl`·`T_obs_naive` 연속량 비교 |

     ★ **목록 항목은 0.0 이어도 freeze 공식 그대로다** — `numeric_core` 의 0.0 float 9개 중 잔차 7개를 뺀 **`/r6/R6-2/T_obs` · `/r6/R6-2/max_abs_t_star`** 는 freeze 「연속량」 목록(`T_obs`·`T*` 수열) 항목이므로 1e-17 차이만으로도 미충족이 날 수 있다. 이것을 **알고 동결**했다(자기검사 T15 가 바로 그 경우를 확인한다). ★ **R6-3 · R6-4 · R6-8 은 프로브에서 미실행이라 Windows 동일성이 아직 확인되지 않았다**(①).

   - **⑪ 입력 결속 규칙 — `input_invalid` 는 판정이 아니라 재회수 사유다**: 실제 판정 모드는 비교 전에 4종을 검사한다. **ⓐ** env 가 `collect_env.py` 산출물인가(`collected_by` 접두 + `python_version`·`numpy`·`sklearn`·`machine`·`platform`·`host_id` 문자열 존재 + `numpy_build_config` BLAS/LAPACK 이름 존재) **ⓑ** 제2자 audit 의 `versions.{python,numpy,sklearn,platform}` 이 제2자 env 와 일치하는가 **ⓒ** 제2자 audit 이 우리 기준 audit 의 **바이트 사본이 아닌가** **ⓓ** 제2자 `host_id` 가 우리와 **다른가**. 하나라도 불성립이면 **exit 2 · `input_invalid`** 로 끝나고 `R3_satisfied`/`R3_not_satisfied` 어느 쪽도 선언하지 않는다 — 잘못 회수된 파일이 「미충족 확정」(되돌릴 수 없음)을 만드는 것을 막기 위함이다. 자기검사 T10~T13 이 네 규칙을, T16 이 정상 입력 대조군을 확인한다.

   - **⑫ F18 원상복구 — cowork 부산물 pyc 1건 제거**: `experiments/rqint/r3_package/__pycache__/canonical.cpython-310.pyc`(sha256 `abcc719712eff7be5a5dea297eb99110196503301fcda3c2d1e4b1f1a6b70c0f` · 4,641 B · mtime 2026-09-10 15:48:22 UTC = 2026-09-11 00:48:22 KST)는 cowork 가 기기 VM(Python 3.10)에서 `import canonical` 로 블록 AC 기준 `numeric_core` 를 실측할 때 생긴 것이다. 해시·크기·mtime 을 F18 과 대조해 일치를 확인한 뒤 **2026-09-14 00:21:59 KST 에 파일과 빈 `__pycache__/` 디렉터리를 제거**했다 → `experiments/rqint/r3_package/` 는 동결 당시 **19파일**로 복귀했고, 19파일 전건이 `r3_package_meta/package_manifest.json` 등재값과 일치하며 `r3_package.zip`(`a94b04f53ba5e392…`)은 불변이다. 본 블록은 그 뒤 어떤 경로에도 새 `__pycache__` 를 만들지 않았다(스테이징·메타·입력·`r3_package`·`v3_Multimodal/src/` 착수 대비 신규 0 — 모든 파이썬 호출에 `PYTHONDONTWRITEBYTECODE=1` + `-B`, 신설 두 스크립트는 `import sys` 직후 `sys.dont_write_bytecode = True`).

> 지시서 = `docs/104_r3_main_package_prompt_for_vscode.md` · 리포트 = `docs/104_r3_main_package_report.md` ·
신규 산출 = `experiments/rqint/r3_main_package.zip`(`4b474b3d7f098c67…` · 73,746 B · 20파일) · `experiments/rqint/r3_main_package/`(스테이징 20파일) · `experiments/rqint/r3_main_package_meta/`(**9종** — `package_manifest.json` `5cc58d1fc9356414…` · `env_local_main.json` `fa2bd54d5ae40ed2…` · `audit_r6_local_main.json` `c53e15c26fdc3dc0…` · `numeric_core_local_main.json` `bf31b967aadf76d0…` · `package_hashes_local_main.json` `021c8e5ffde7456e…` · `run_local_main.log` `fac7ffb79ca3d18f…` · `local_run_record.json` `5601b7ce07955832…` · `judge_selftest.json` `aace4c227aee7bbb…` · `r3_main_reference.json` `74337a3288a24794…`) · `v3_Multimodal/src/build_r3_main_package.py` · `v3_Multimodal/src/r3_judge.py`(`df26e946d17cd0b5…`) ·
무수정 대조 = SAP 11모듈 · rqint 3모듈 · `run_rqint_audit.py` `ab831c2726a36e8a…` · `experiments/rqint/audit_r6.json` `921e16ea8191bc9b…` · `run.log` `43f395828040f2b5…` · `r3_package/` 19파일 · `r3_package.zip` `a94b04f53ba5e392…` · `r3_package_meta/**` 10파일 · `r3_second_party_freeze.json` `0624d3ddb852c4e9…` · `experiments/sap/manifest.json` `d08dcedf2a22e1c8…` · 입력 4파일 · 봉인 **275/16/291/25** 착수=종료 · status sidecar `dbb00d540d7436e5` · HEAD `566f487`·**21**. **미실행**: 위 ⑧ 전항.

---

56. **★ R3 판정 — 동결 판정기 1회 실행 · 「R3 충족(1차)」 확정 (블록 AQ — `docs/105` · 계산 0 · 개봉 0)**:

   - **① 트리거·회수 경위 — 메일 3(M7) → 회수(M8)**: 스레드 `<GMAIL-MSGID>` 를 `get_thread` 로 재실측(2026-09-14 23:46 KST)해 **8건 전수** 확인했다. **M7** outbound `<GMAIL-MSGID>` **2026-09-14 01:27:38 KST**(2026-09-13T16:27:38Z · 첨부 `r3_main_package.zip` application/zip **1건** · sizeEstimate **130,708** · 본문 = 「본 실행」 4줄 명령 + 회수 4파일 + 「제 컴퓨터에서 약 17분」 안내) = **트리거**. **M8** inbound `<GMAIL-MSGID>` **2026-09-14 15:10:45 KST**(2026-09-14T06:10:45Z · 첨부 **4** = `env_e2c3a7fa6723.json` · `audit_r6.json` · `audit_numeric_core.sha256` · `package_hashes.json` · 본문 축자 「본 실행 진행 후 생성된 파일 첨부해서 보내드립니다. 확인 부탁 드립니다.」). ★ **회수 경로 = 메일 첨부 → 사용자 다운로드 → Cowork 업로드 → cowork 커밋**이며, **첨부 원본 바이트와 커밋본의 대조는 미실시**다(`attachment_byte_verification` = not_performed). 다운로드 과정에서 env 파일명이 `env_e2c3a7fa6723 1.json` 로 개명돼 저장소에는 `env_second_party_main_e2c3a7fa6723.json` 로 들어왔다(내용 무변경 — ②의 바이트 동일성 관측이 이를 보강한다). 회수물 5파일(cowork 기입 receipt 포함)은 `experiments/rqint/r3_second_party_return/` 에 있고 착수=종료 sha256 동일이다 — `audit_r6_second_party.json` **`e06464919c4e0358d48b42c6b7b85cd04c079c94bb9851f67ed72a87f5cd7413`**(10,382 B) · `env_second_party_main_e2c3a7fa6723.json` **`7a404edba225af64be7c4f3dbcf9014b2aaf39bd04c3fe8023e0df8a31065106`**(3,100 B) · `audit_numeric_core_second_party.sha256` **`2e5461a65bc9d789487b9f957fe0833857c5bdbde93ef2699ee82d8137c0031d`**(778 B) · `package_hashes_second_party.json` **`7560b6cdde1d10f8d91edf4dc84fe47ec093b9d5f2d21b9a9a4a1e91a176da86`**(3,168 B) · `r3_second_party_return_receipt.json` **`e2b20d97153845b27651ae2811b633fce8601cca5dae69efdab9ee5398a11153`**(3,247 B).

   - **② 제2자 실행 실측**: `run_at_kst` **2026-09-14T14:34:37+09:00** · `wall_clock_seconds` **4,223.9 s**(70.4분 — 우리 로컬 1,030.18 s 의 약 4.1배로, M7 본문의 「1시간~1시간 30분」 예상 범위 안이다) · 환경 4필드 `versions` = Python **3.12.9** / numpy **2.5.0** / sklearn **1.9.0** / **Windows-10-10.0.19045-SP0** · `r6_all_pass` **true** · `r6_3_remeasure` **null** · 본인 산출 `numeric_core` **`fd488eb4…`** · canonical bytes **7,493** · `package_hashes` `n_files_listed` **20** · `n_missing` **0**. ★ **env 파일은 프로브 회수본 `experiments/rqint/r3_package_meta/env_second_party_e2c3a7fa6723.json` 와 바이트 동일**(양쪽 sha256 `7a404edba225af64…`) — 같은 기계·같은 가상환경(r3env)에서 같은 `collect_env.py` 를 돌렸으므로 산출이 동일한 것이며 **이상이 아니다**(M5 본문 「이번에 만드신 환경에서 그대로」 지시대로 실행된 정황 근거이기도 하다). ★ 프로브에서 미실행이던 **R6-3 · R6-4 · R6-8** 3항(항목55 ①)은 본 드라이런에서 Windows 환경에서도 수행됐고 `r6_all_pass` true 에 포함된다.

   - **③ ★ 판정 결과 축자 — 동결 판정기 `r3_judge.py` 1회**: 산출 `experiments/rqint/r3_main_package_meta/r3_verdict.json` sha256 **`5469a076b6659e4db5e0b049c66e945f2cce7cc6da4c66ac543f70e24b6a29a9`** · **2,730 B** · `run_at_kst` **2026-09-14 23:46:55 KST** · `judge_sha256` **`df26e946d17cd0b5ea20c741008bbdfbe19ee8b2b7d92b0de7664943ea4bcd12`** · `freeze.freeze_sha256` **`0624d3ddb852c4e9a2f7f070024814653264eb49c2652dd3e7a947ac38ff27d0`** · `rel_tol` **1e-09** · 제외 pointer **8** · G-ENV 필드 **5**.
     **`verdict` = `R3_satisfied_stage1`** — 곧 **1차 기준(numeric_core 바이트 동일)으로 충족**이다. `stage1` = `ours` **`fd488eb429a71990d47ebf321efeb1f34083bbeb4813730a76777262b1ba878b`** · `second_party` **`fd488eb429a71990d47ebf321efeb1f34083bbeb4813730a76777262b1ba878b`** · `second_party_canonical_bytes` **7,493** · `byte_identical` **true**(양쪽 해시·바이트 수 모두 동일). `package_hashes` = `n_expected` **20** · `n_mismatch_or_missing` **0** · `mismatch_or_missing` **[]** · `unexpected` **[]** · `pass` **true**. `stage2` = **`"not_run — 1차 통과(freeze stage_1_byte_identity.on_pass)"`** — freeze `stage_1_byte_identity.on_pass` 대로 **2차(허용오차 판정)는 실행하지 않았다**. 판정기 호출은 **정확히 2회**(① 출력만 → ② 같은 인자 `--write` 1회)이고 **두 호출의 `verdict` 가 동일**함을 기록 전에 확인했으며, `--write` 는 1회뿐이다(`_write_once` 가 재기입을 차단). exit code 0.

   - **④ G-ENV 5필드 대조표(`r3_verdict.json:g_env`) — `n_differ` 3 · `pass` true**:

     | 필드 | 우리(`env_local_main.json`) | 제2자(`env_second_party_main_e2c3a7fa6723.json`) | `differs` |
     |---|---|---|---|
     | `python_version` | 3.14.4 | 3.12.9 | **true** |
     | `numpy` | 2.5.0 | 2.5.0 | false |
     | `sklearn` | 1.9.0 | 1.9.0 | false |
     | `machine` | arm64 | AMD64 | **true** |
     | `numpy_build_config`(BLAS/LAPACK 구현) | `["accelerate","accelerate"]` | `["scipy-openblas","scipy-openblas"]` | **true** |

     `n_differ` **3** ≥ 1 이므로 「다른 환경」 요건이 성립하고 `g_env.pass` **true** 다(`info_host_id` = 우리 `89be108a4c00` ↔ 제2자 `e2c3a7fa6723`, 참고정보). 곧 **Python 마이너·CPU 아키텍처·BLAS/LAPACK 구현이 다른 기계에서 `numeric_core` 가 바이트 단위로 재현**됐다. numpy·sklearn 버전이 같은 것은 `requirements_r3.txt` 로 고정한 결과이며, R3 의 취지는 「같은 코드·같은 입력 · **다른 환경**」이므로 요건에 어긋나지 않는다.

   - **⑤ 러너 독립 검증 5항(AQ-3 · 판정기와 별도 · **판정 대체 아님**)**: **(1)** `canonical.py` 를 **import 하지 않고** 제외 pointer 8개(RFC6901 자체 구현)와 직렬화 규약 `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",",":")).encode("utf-8")` 만으로 제2자 audit 에서 재계산 → **`fd488eb429a71990d47ebf321efeb1f34083bbeb4813730a76777262b1ba878b` / 7,493 B** 로 기준과 일치(적용 pointer 8/8 전건 실제 삭제됨). **(2)** 제2자 `package_hashes_second_party.json` 20항목 ↔ `package_manifest.json` 등재값(접두 `r3_main_package/` 제거) **20/20 일치** · 불일치 0 · 누락 0 · 여분 0 · bytes 불일치 0. **(3)** 입력 결속 4규칙 수동 확인 — 제2자 audit sha `e06464919c4e0358…` **≠** 기준 audit sha `c53e15c26fdc3dc0…` · `versions` 4필드 = env 4필드(python/numpy/sklearn/platform 전건 동일) · `host_id` 상이(`e2c3a7fa6723` ≠ 우리 `89be108a4c00`) · `collected_by` = 축자 「collect_env.py (블록 AG · docs/91 AG-5)」(양쪽 동일 문자열). **(4)** 리프 대조(정보 기록) — `r3_judge.compare_tree()` 를 모듈 함수로 호출해 기준 core ↔ 제2자 core 를 비교한 결과 **리프 불일치 0건**(`n_leaf_failures` 0 · 1차 통과와 정합) · 두 core 직렬화 바이트도 7,493 = 7,493 동일. **(5)** G-ENV 5필드 대조표 = ④. ★ 다섯 항이 모두 판정기 출력과 **어긋나지 않았다**.

   - **⑥ R3 조건 상태 전이 — 동결 파일은 무수정이고 이 항목과 ledger 가 superseding 기록이다**: `v3_Multimodal/config/rqint_procedure_decisions_v1.json`(`16776f21df6ae29b…` · 22,062 B)의 `conditions.R3.status` 는 **`"pending"`** 이고 `remaining` 은 「제2자 독립 재실행 자체는 미이행. R3 본 드라이런은 후속 블록.」이다. 동결 파일이라 **0바이트 수정**하며, **실제 상태 = 충족(`satisfied`)** 임의 근거는 **판정 근거** `r3_verdict.json`(`5469a076b6659e4d…` · `verdict` `R3_satisfied_stage1`) · **판정 시각** 2026-09-14 23:46:55 KST · **판정기 sha256** `df26e946d17cd0b5ea20c741008bbdfbe19ee8b2b7d92b0de7664943ea4bcd12` 다. 아울러 같은 파일 `conditions.R3.package` 와 `experiments/sap/sap_1_2_hash_registry.json`(`855616a27ff1f8fa…` · 17,578 B · L370–374)이 「R3 패키지」로 등재한 **프로브 zip `a94b04f53ba5e392…`** 는, 실제 판정에 쓰인 **본 드라이런 패키지 `r3_main_package.zip`(`4b474b3d7f098c67fa3bae1c1d8a9dadb0bce3ad7f978ae911ad450307999948` · 73,746 B · 20파일)** 로 **superseding 기록**된다(프로브 zip 은 「플랫폼 적합성 프로브」 지위로 남고, 두 동결 파일은 0바이트 수정 — 항목55 ⑨(ii) 의 연장).

   - **⑦ 잔여 개봉 요건 2건 — R3 충족으로도 개봉은 열리지 않는다**: `docs/103` AO-10 S13 대로 **(i) Holm ⑧ RQ-int 미확보**(R3 → GIN 착수 → λ·ρ 진단이 선행해야 한다) · **(ii) 개봉 별도 승인·시점 미정**. 「봉인 완전성 점검」은 블록 AO(`docs/103`)로 충족됐고, 본 블록으로 **R3 가 충족**됐으나 위 2건이 남아 있으므로 개봉 요건은 **미완결**이다(`v3_Multimodal/config/post_interim_freeze_v1_0.status.json` `dbb00d540d7436e5` · `unblinding_performed` **false** · `gin_start_still_blocked` **true** 유지).

   - **⑧ 미실행(본 블록이 하지 않은 것)**: **개봉 0** · **GIN 착수 0** · **새 부호 산출 0**(계산·학습·추론 0 · `experiments/runs/.compute_lock.json` 부재 확인만) · **판정기 재실행 금지**(2회 호출 외 0 · `--selftest` 재실행 0 · `r3_verdict.json` 재기입 0 — freeze `on_fail` 축자 「임의 3차 기준을 만들지 않는다. 허용오차를 늘리지 않는다. 비교객체를 바꾸지 않는다.」에 따라 **기준·허용오차·제외 목록·판정기 코드 수정 0**) · **`emit_sign` 0** · **`decision.py` 호출 0** · **봉인 접근 0**(경로 나열 계수만 — 25/275/16/291 착수=종료 · 읽기·복사·해싱 0) · **`data/` 접근 0** · **메일 발송·초안 작성 0**(교수님·외부검토자 <EXTERNAL-REVIEWER> Ph.D. 보고는 cowork·사용자 소관) · **`pip` 0** · **네트워크 = Gmail `get_thread` 읽기 전용 1회**(스레드 `<GMAIL-MSGID>` 8건 · 첨부 다운로드 0 · 발신 0) 외 0 · **git commit·push·add·stash·status 0**(HEAD `566f487` · 커밋 **21** · `git ls-files -m` **4건** 착수=종료 동일) · `rqint_procedure_decisions_v1.json`·`sap_1_2_hash_registry.json` 파일 수정 0 · `docs/33` 항목53 ⑧ stale 표시문자열 2행 정정 0 · `AGENTS.md` 갱신 0 · 새 `__pycache__` 0(모든 호출에 `PYTHONDONTWRITEBYTECODE=1` + `-B`).

   - **⑨ 판정 권위 선언**: **정본은 동결 판정기 `r3_judge.py`(`df26e946…` · 트리거 이전 동결) 의 출력 `r3_verdict.json` 이다.** cowork 의 사전 대조(2026-09-14 23:37~23:45 KST · 제2자 `numeric_core` `fd488eb4…`/7,493 B 일치 · `package_hashes` 20/20)와 본 항목 ⑤ 의 러너 독립 검증 5항은 **검증**이며 **판정을 대체하지 않는다**. 세 경로가 같은 값을 내놓은 것은 판정의 재현성 근거로만 기록한다.

> 지시서 = `docs/105_r3_verdict_prompt_for_vscode.md` · 리포트 = `docs/105_r3_verdict_report.md` ·
신규 산출 = `experiments/rqint/r3_main_package_meta/r3_verdict.json`(`5469a076b6659e4d…` · 2,730 B · `verdict` `R3_satisfied_stage1`) — `r3_main_package_meta/` **9종 → 10종** ·
무수정 대조 착수=종료 sha256 동일 = `r3_judge.py` `df26e946d17cd0b5…` · `r3_main_reference.json` `74337a3288a24794…` · `package_manifest.json` `5cc58d1fc9356414…` · `audit_r6_local_main.json` `c53e15c26fdc3dc0…` · `env_local_main.json` `fa2bd54d5ae40ed2…` · `package_hashes_local_main.json` `021c8e5ffde7456e…` · `judge_selftest.json` `aace4c227aee7bbb…` · `r3_main_package.zip` `4b474b3d7f098c67…` · `r3_main_package/` 스테이징 20파일 · `r3_second_party_return/` 회수 5파일 · `r3_second_party_freeze.json` `0624d3ddb852c4e9…` · SAP 11모듈 · rqint 3모듈 · `run_rqint_audit.py` `ab831c2726a36e8a…` · `experiments/rqint/audit_r6.json` `921e16ea8191bc9b…` · `run.log` `43f395828040f2b5…` · 봉인 **275/16/291/25** · status sidecar `dbb00d540d7436e5` · HEAD `566f487`·**21**. **미실행**: 위 ⑧ 전항.

---

57. **★ GIN 착수 설계 동결 + 예산 산출 — 확증 GIN 학습 0회 (블록 AR — `docs/106` · 개봉 0 · 착수 0)**:

   - **① 무엇을 동결했는가 — 규격 7항 (a)~(g)**: 신규 동결 2파일 = `v3_Multimodal/config/gin_confirm_harness_freeze.json` sha256 **`1af993fde7330e1d48e6d10fee157c1310f42dacc5c1d65a4834b9020e5b7072`** · **21,968 B** + sidecar `…status.json` sha256 **`5df9a7c4bfa64749f2b37f5b1984cfcca85d8f609e6c8c444097ff78e24c819a`** · **1,439 B**(선행 `gin_inner_valid_freeze.status.json` 과 **동일 9필드**: `target`·`target_sha256`·`status`·`delegated_by_advisor`·`basis`·`reversibility`·`advisor_notified_in`·`item_requiring_advisor_confirmation`·`as_of_kst`). **(a) 실행 디렉터리** = `experiments/runs/v3_gin_confirm_rep{r}_seed{s}/`(r∈1,2,3 ↔ s∈201,202,203) · `v3_gin_confirm_consensus_rep123/` · `v3_gin_stability/` — 근거는 기존 실행 디렉터리 **33개**의 경로 관례 + `gin_seed_freeze.firewall` 축자 「Stability outputs are written to a **directory separate from** the confirmatory run outputs」. 통계적 선택이 아니라 경로 관례다. **(b) 공개/봉인 경계** = ⑤ 참조. **(c) `_sealed/` 레이아웃** = `oof_{model}_seed{t}.npz`(P 1092×370 float32 + y int8 + `pt_index` + `cid_order`; model 7 × t∈{42,1,2} → 확증 **21개/반복**) · `metrics_full.json`(셀별 macro AP·Δ·`n_eval`·`n_excluded_undefined`·`best_ep`·`best_v`) · `access.log`(`type`=machine_read · `human_exposure`=false) · `checkpoint.jsonl` · `env_fingerprint.json` — ★ **경로 문자열·키 스키마로만 검증**했고 본 블록은 `_sealed` 디렉터리를 **0개 만들었다**(S11 은 `schema_fixture/` 에서 평평한 이름으로 수행). **(d) 재개 단위** = **`(rep, fold, model, train_seed)` 4-튜플** · append-only · key 중복 금지 assert · 한 줄 = 완료 사실 + 산출 sha256 + epoch 수 + 소요 초. 근거는 기존 `_sealed/checkpoint.jsonl` **선례 6건**(`v3_confirm_rest`·`v3_confirm_rftuned`·`v3_latefusion`·`v3_null_MAIN`·`v3_stratification_axes`·`v3_stratification_pid`) + `docs/93`(블록 AE) 세션 분할 운용 **뿐**이며 — ★ **AR-5 예산 결과를 근거로 달지 않았다**(AR-2 가 AR-5 보다 먼저 수행되므로 순환이 된다). **(e) 실패처리** = `gin_seed_freeze.failure_policy` **축자 전문 그대로**(「Only pre-defined hard technical failures (crash, OOM, NaN loss) may be retried, exactly once, with the SAME seed and SAME configuration…」) · 재구현·완화·확장 **0**. **(f) 집계 경로** = repeat 축 **prediction-then-metric** · seed 축 **metric-then-average** · consensus **8행렬** · 「행렬을 먼저 평균하면 D3 위반」 · `build_consensus`·`macro_ap` **재구현 금지, import 호출**. **(g) 미실행 선언 9필드** = `gin_start_still_blocked` true · **`is_authorization` false** · `confirmatory_training_runs_performed` 0 · `sealed_read` 0 · `sealed_dirs_created` 0 · `emit_sign_calls` 0 · `open_sealed_calls` 0 · `unblinding_performed` false · `rqint_test_calls` 0. ★ **규격 파일의 모든 필드가 `derived_from` 축자 인용을 동반**하며 근거를 못 대는 필드는 적지 않았다.

   - **② 하네스 코드 — 자체 차단(exit 11) 설계**: `v3_Multimodal/src/confirmatory_gin_rep.py` sha256 **`1e6642bf9ecac5a272fdb49c441668d2f6f3ec97e87528831aad75a9c40d995a`** · **42,450 B** · **840행**. stage 3종 = `--stage selftest`(**기본값**) / `--stage plan` / `--stage train`. **차단 구현 축자**: `main()` 이 `train` 분기에 들어가면 **동결 로드보다 먼저** `enforce_gin_block()` 을 호출하고, 그 함수는 `rqint_procedure_decisions_v1.json`·`gin_seed_freeze.json`·`gin_inner_valid_freeze.json` **3파일을 읽어** `gin_start_still_blocked` 를 확인한 뒤 **하나라도 true 면** `"GIN 착수 차단 중: <파일명> gin_start_still_blocked=true. 해제는 별도 블록·별도 승인."` 을 출력하고 **`sys.exit(11)`** 한다. ★ **우회 경로 0 확인** — `--force` 인자 없음 · 환경변수 분기 없음 · 기본값 우회 없음 · 주석 처리로 끌 수 있는 경로 없음(argparse `choices` 3종 외 인자는 `--out` 뿐이고 `plan` 전용이다). 가드는 `selftest`/`plan` 에는 적용하지 않는다(학습을 하지 않으므로). 별도로 동결 3종 sha256 상수 대조가 있고 불일치 시 **exit 2**. **하드코딩 0** — 시드·대표 unit·epoch·patience·inner-valid 비율·모델 목록을 전부 동결 파일에서 로드한다(`valid_fraction` 은 문면 `"1/9 of the outer-train rows"` 를 파싱해 분모 9를 얻는다). A_wd 상수는 `train_ladder` 에서 **import** 하고 규격 파일·`gin_inner_valid_freeze` 값과 **교차 대조 assert**(S5). **재구현 0** — `sap.metrics.macro_ap` · `sap.consensus.build_consensus` · `sap.rqint.build_eight_consensus`/`observed_statistic` · `ladder_confirmatory` 블록 클래스·`MODEL_BLOCKS`·`PCA_K` · `v2_GNN/src/train` 6종 · `drug_branch.GINDrugEncoder` · `graph_features.{ATOM_FDIM, smiles_to_data}` · **`confirmatory_oof_rep1.assign_folds`** 를 전부 import 한다. **inner split** 은 동결문 축자(「pre-sort groups by (-group_size, **str(first row index)**)… the outer-train subset is **NOT re-indexed**… **bucket 0 = inner-valid**, bucket 1 = inner-train」)대로 `assign_folds` 를 **2버킷으로 일반화**(`assign_buckets(groups, n, seed, cuts)`)했고, ★ **등간 cuts(`[(i+1)n/k]`)로 호출하면 import 한 동결 `assign_folds` 와 `fold_of_group`·`order`·`counts` 전건 동일함을 assert** 해 «재구현이 아님» 을 기계로 증명한다(S4). `inner_seed = 1000*split_seed + zero_based_fold_index` · 분할 단위 = Bemis-Murcko scaffold group(빈 문자열 scaffold = 정당한 1개 군) · 동결문 assert 3종 중 2종(그룹 서로소 · `inner_train + inner_valid == outer_train`)은 함수 내부에서, 3번째(inner-train 양성 0 적격 PT 0건)는 라벨로 검사한다. **금지 가드(코드 수준)** — `open_sealed`·`emit_sign`·`sap.decision`·`requests`/`urllib`/`http` **미import** · `_sealed/` 경로 읽기 호출 0 · `_sealed` 디렉터리 생성 0 · `rqint_test` 미호출 · 최상단 `sys.dont_write_bytecode = True`.

   - **③ 자체검사 12건 — `n_pass` 12 · `n_skip` 0 · `all_pass` true (정의 `n_pass + n_skip == n_cases`)**: 산출 `experiments/runs/v3_gin_harness_selftest/selftest.json` sha256 **`37b0af4d2ef74ad410c76603a143c7089161c6f35a75d68271a8a8cf94c78e09`** · **11,246 B**. **SKIP 0건이므로 SKIP 사유 없음** — `.venv`(python 3.14.4) 에 torch 2.12.1 · torch_geometric 2.8.0 · rdkit 2026.03.3 · sklearn 1.9.0 · numpy 2.5.0 · pandas 3.0.3 가 전부 있고 `torch.backends.mps.is_available()` true 라 AR-0-4 의 AST 대체 경로(S5)·SKIP 경로(S9)는 **발동하지 않았다**. 결과: **S1** 동결 3종 sha256 3/3 · **S2** 대표 unit 규칙 재산출 `[4,1,0]` = 동결값 · **S3** inner split **15/15 unit 전건 일치**(`inner_valid` 전부 **97** · `n_inner_train`·`n_valid_scaffold_groups`·`n_valid_defined_pt`·`n_inner_train_zero_positive_pt`·`largest_valid_group_size`·`largest_valid_group_is_empty_scaffold`·`n_outer_train_scaffold_groups` 전건 `inner_split_check.json` 과 동일) · **S4** outer split 3반복 전건 `mismatched_rows` **0** · `fold_sizes` `[218,218,219,218,219]` · groups **732**(+ 일반화 등가성 assert 3/3) · **S5** A_wd 상수 12개 = 코드 = 규격 = 동결 · **S6** early-stop 진리표 6케이스(strict `>` · patience **30** 정확히 소진 시 ep 31 정지 · patience 29 에서는 미정지 · tie = **최초** epoch · `min_epoch` **부재**) · **S7** macro AP 가변 분모(`n_eval` 3 · `n_excluded_undefined` 2 · `n_eligible` 5 · `excl_frac` 0.4 · `defined_mask` · **AP=0 대입 없음**) · **S8** consensus 행렬 **정확히 8개** · seed 키 정렬 · metric-then-average 경로 확인 · **`rqint_test` 호출 0 · 순열 계산 0** · **S9** 아래 자진기재 · **S10** `--stage train` → **exit 11** · 표준출력에 차단 사유 · `v3_gin_confirm_*` 디렉터리 생성 **0** · **S11** 규격 왕복(`schema_fixture/SEALED_LAYOUT.json` 에 상대경로 **90개** 기입 + 키 스키마 검사 · **`_sealed` 디렉터리 생성 0**) · **S12** 위생(`__pycache__` **4,541** 착수=종료 · 봉인 **25/291/275/16** 불변).
     ★ **S9 합성 smoke 자진기재**: 「지시서가 공급한 **고정 SMILES 12개** + `numpy.random.default_rng(20260914)` 라벨 12×8 Bernoulli(0.3) 로 **2 epoch 합성 학습 1회**를 수행했다(device `mps` · 0.193 s · 0.096 s/epoch · 파싱 실패 0 · 예측 shape 12×8 확인). `data.build_graphs` **미사용**(`graph_features.smiles_to_data` 사용 — `build_graphs` 는 `master_X`/`master_Y`/`scaffold_split` 에 하드와이어라 합성 fixture 에 쓸 수 없다) · 확증 라벨·분할·봉인 접근 **0** · 수치 폐기(예측·손실·지표 미기록) · 산출은 selftest 디렉터리에만. 시드 20260914 는 합성 fixture 전용이며 확증 시드 집합(201~203 · 42/1/2/3/4)과 **교집합 0** 이다. `gin_seed_freeze.preconditions.gin_training_runs_before_freeze = 0` 의 대상인 **확증 GIN 학습은 0회**이며, 이 smoke 는 그것과 구분된다.」

   - **④ 예산 — 규칙을 산출 «전» 에 고정했고 폴백을 쓰지 않았다**: 산출 `experiments/runs/v3_gin_budget/gin_budget_estimate.json` sha256 **`f42e839d154611f2050124fdf2902cbec5a02988860de185622236113b139605`** · **11,151 B** + `README.md` sha256 **`6fd60d4a59c48b49341bd3cd41f92f5c620d1789b20995e44c68205b31c51796`** · **1,224 B**. **대응 규칙** = 파일 mtime 정렬 순서가 로그 등장 순서와 일치함을 **실측 확인**(50/50)한 뒤, 파일 *i−1* → *i* 의 mtime 차를 run *i* 의 지속시간으로 본다(i = 1…49). **run 0 제외** = run 0 은 `M0_seed42`(epoch **195**)이고 인접차가 정의되지 않아 **지속시간을 관측할 수 없으므로** 단가 산식의 분자(지속시간 합)와 분모(epoch 합) **양쪽에서 제외**했다 — 단, 개발 epoch 분포(3지점)에는 50건 전부를 포함한다. **이상치 규칙** = `n_durations` **49** 에 Tukey 상단 울타리 `Q3 + 1.5·IQR`(numpy 기본 linear 분위수): `Q1` **86.900 s** · `Q3` **360.655 s** · `IQR` **273.754 s** · **울타리 771.286 s**. **제외 3건 전건** = run 15 `M3_seed42` **812.909 s / 73 ep** · run 42 `A_top1_seed2` **1,125.371 s / 48 ep** · run 44 `A_top1_seed4` **3,661.775 s / 84 ep**(= 61.03분 유휴 구간). 잔존 **46 run**(지속시간 합 **9,890.713 s** / epoch 합 **3,460**). **단가 `u` = 2.858588 s/epoch** · **폴백 사용 0**. **`k_rows` = 777 / 873 = 0.8900**(가정: per-epoch 비용이 행 수에 선형 — `assumptions` 에 가정임을 명시). **규모** = `run_counts` 315 / 42 / **357** · `oof_matrices` **63** / primary **18** · shape 1092×370. **epoch 3지점** = 하한 median **65** · 중앙 mean **77.2** · 상한 **200**. **derating 3지점** = 1.0 / 1.3 / 2.0. **3×3 표 2종** — 선행비용 **미포함**(h): 65ep 16.40 / 21.32 / 32.80 · 77.2ep 19.48 / 25.32 / 38.96 · 200ep 50.46 / 65.60 / 100.92 ; 선행비용 **포함**(h): 65ep **19.66** / 24.58 / 36.06 · 77.2ep 22.74 / 28.58 / 42.22 · 200ep 53.72 / 68.86 / **104.18**. **선행비용 산출법 = ②** — ①(「fold 당 7모델 합」)은 `v3_confirm_rest/run.log` 의 모델 집합이 **6개**(`M0`·`M1`·`M2`·`P-ID`·`P-FAM`·`C-CAP`)로 GIN 7모델 집합(`M0`·`M1`·`M1b`·`M2b`·`P-ID`·`P-FAM`·`C-CAP`)과 **다르므로**(M1b·M2b 없음 · M2 여분) 구성할 수 없었다. 따라서 본계산 `wall` **90건**의 모델별 중위값(C-CAP 93.10 · M0 94.10 · M1 93.20 · M2 93.20 · P-FAM 93.10 · P-ID 94.30 s)의 중위값 **93.20 s × 7 = 652.40 s/unit**, × **18 unit**(확증 15 + 안정성 대표 3 — 안정성은 firewall 상 별도 디렉터리라 블록 fit 재수행으로 보수 계상) = **3.262 h**. ★ 이 값에는 **RF 학습 시간이 섞여 있어** GIN 의 「블록 fit + 그래프 빌드」만을 분리할 수 없으므로 **과대추정(보수적)** 방향임을 `assumptions` 에 적었다. `v3_confirm_rep1_seed201` 의 4분 29초는 `B_pid`·`B_fam`·`C_ccap` fit 이 그 구간에 없으므로 **「상한」이라고 부르지 않고** 참고값으로만 병기했다. 블록 AE 의 열감쇠 **0.2489** 는 다른 작업부하(캘리브레이션 감사) 실측치라 **미적용**하고 `derating_0_2489_not_applied_and_why` 에 근거와 함께 별항 병기했으며, **S9 smoke 초/epoch 는 단가에 투입하지 않았다**(`s9_smoke_not_used_in_unit_cost: true`). **세션 계획** = AC 전원 필수(블록 AE 선례 · 배터리 측정치 예산 투입 금지 · 착수 전 `pmset -g ps`/`-g adapter` 실측) · 체크포인트 단위 = (d) 의 4-튜플 · 재개 = 미등재 단위부터 · `compute_lock` 취득 + `LOAD_HARD_MAX 2.0` 게이트 + 열 안정화 · `caffeinate` 하 백그라운드 + 로그 tail · 세션당 권장 상한 8 h. ★ **등록 §13 예산절 초과(189 → 357)와 그 해소 근거를 축자로** — `registered_budget_clause_exceeded` 에 「등록 §13 예산절보다 많은 계산을 쓴다(189 → 357). 근거 = 등록 §6 + docs/50 §결정. 완화가 아니라 **증가** 방향」을 기입했고, 러너가 `docs/30` **§6 L105** 축자 「RF는 결정적, GIN은 **outer fold당 3 training seed 평균**」과 `docs/50` **L36** 축자 「**결정**: 확증 GIN estimand = 모든 outer fold에서 사전지정 **3 training seed 평균**(§7)」을 **직접 확인**했다(G10).

   - **⑤ 공개/봉인 경계 결정과 `emit_sign` 0 이 «강화 방향» 인 근거**: **공개 허용** = 개수 · 분할 진단 · 환경 명세 · 타이밍 · 게이트 통과 여부 · `n_eval`/`n_excluded_undefined` · epoch 수 · 재시도 로그 **끝**. **봉인** = 모든 예측 확률 · 모든 macro AP · 모든 Δ · **Δ 의 부호** · valid monitor 값 · `best_v`. 근거 **3중** — **(1)** `docs/36` §4-R 축자 「노출 금지(사람·리포트·채팅): 원시 macro AP 값, Δ의 크기, PT별 AP/Δ, fold별 수치, 확률 예측 분포」 + F17 실측 `run.log` 축자 「RF random_state=42 (**수치 미기록 — redaction**)」·「[지표] macro AP 산출 완료 — **원시값·Δ크기 미출력(sealed, 3개 파일 sha 기록)**」 **(2)** `sap/rqint.py` `TEST_STATISTIC` 축자 「**T = Δ_RF − Δ_GIN**, Δ_F = macroAP(y, P_F^{M2b}) − macroAP(y, P_F^{M1b}); 양측.」 → **Δ_GIN 은 검정통계량 T 의 항**이므로 그 부호를 공개하면 **새 공개 사건**이 되고, 승인조건 **R5** 가 확정한 문면(`disclosure_date` **2026-07-27** · `n_persons_knowing_direction` **1** · 「4건 중 3건(반복2·반복3·consensus)이 … 공개 저장소 커밋으로 열람 가능 · **반복1 미공개**」)을 바꾼다 **(3)** `gin_seed_freeze.firewall` 축자 「Stability results **must not change** the primary results, hypothesis adjudication, model/hyperparameter/seed selection, or the aggregation method」. → 이 규칙은 기존 RF 확증 관례(`metrics_public.json` 24 B 에 부호 1개)보다 **공개를 줄이는** 방향이므로 **완화가 아니라 강화**이고 amendment 에 해당하지 않는다. 이 판단을 규격 파일 `spec.b_public_sealed_boundary.not_an_amendment_because` 에 축자로 적었다. ★ **`metrics_public.json` 값 미판독** — 본 블록은 그 파일의 **바이트 수(24)와 키 이름(`['sign']`)만** 확인했고 **값은 읽지 않았다**(§1-2 · F17). 부호 자체는 `ledger.first_look_register` 와 `docs/45` §5 에 이미 등재돼 있어 파일을 새로 읽어 얻을 정보가 없으며, R5 가 반복1 을 「공개 저장소 미노출」로 등재하고 있으므로 판독 자체를 하지 않았다.

   - **⑥ 승인조건 6건 실질 충족 + 동결문 `still_unspecified` 2건도 해소 — 그럼에도 차단 유지**: `rqint_procedure_decisions_v1.json`(`16776f21df6ae29b…` · 22,062 B)의 `conditions_summary` = `{"satisfied": ["R1","R2","R4","R5","R6"], "pending": ["R3"]}` 이고, **R3 는 동결 파일상 `pending` 이지만 실제로는 충족**이다(`experiments/rqint/r3_main_package_meta/r3_verdict.json` `5469a076b6659e4d…` · `verdict` **`R3_satisfied_stage1`** · 2026-09-14 23:46:55 KST · 항목 **56 ⑥**). → **승인조건 6건 실질 전건 충족.** 아울러 `gin_seed_freeze.still_unspecified` / `gin_inner_valid_freeze.still_unspecified` 에 남아 있는 2건도 이미 해소돼 있다 — **「SAP 1.2 re-freeze」** 는 블록 AN(`docs/102`)이 완주했고(live `experiments/sap/manifest.json` `sap_version` **1.2** · sha16 **`d08dcedf2a22e1c8`**), **「U1-U7 (RQ-int) pending external statistical review」** 는 위 승인조건 6건으로 종결됐다. 따라서 `gin_inner_valid_freeze.status.json` 의 `reversibility` 축자 「GIN cannot start until the **SAP 1.2 re-freeze approval**, so this decision remains reversible until then」의 조건도 충족이다. ★ **그런데도 동결 파일 3종은 0바이트 수정**했고, 위 사실은 본 항목과 `ledger.json` 의 **superseding 기록**으로만 남긴다. 신규 sidecar 의 `reversibility` 는 선행 문면을 **대체하지 않고 기초로 삼아 조건을 추가**했다. **그럼에도 남은 차단 요소 4건** = ① **교수님 회신**(⑦ 에서 도착 확인 — 사실로서는 충족됐으나 플래그 해제는 별건) ② **Holm ⑧ RQ-int**(GIN 산출 → λ·ρ 진단 선행) ③ **개봉 승인·시점**(별건 · `unblinding_performed` **false** 유지) ④ **`gin_start_still_blocked` 해제**(별도 블록 · 별도 승인). **본 블록은 해제 근거를 만들지 않았고**, 플래그 3곳은 착수=종료 **전부 true** 다.

   - **⑦ AR-6 개봉 전 감사 영향 판정 = 영향 없음 (grep 확인만 · 실행 0)**: `pre_unblinding_audit.py`(`SEALED_BASELINE_ARTIFACTS` **273** / `SEALED_BASELINE_TOTAL` **288** — stale) · `pre_unblinding_audit_v2.py`(`SEALED_BASELINE_ARTIFACTS_V2` **275** / `_ACCESS_LOGS_V2` **16** / `_TOTAL_V2` **291** / `_DIRS_V2` **25** — 현행) · `rqint_package_gates.py`(L107-108 대상 = **`v3_Multimodal/src/sap` 뿐**)을 grep 으로 확인했다. 신규 3종(`gin_confirm_harness_freeze.json` · `…status.json` · `confirmatory_gin_rep.py`)은 **`_sealed/` 밖 · `src/sap/` 밖**이고, 봉인 계수 **25/291/275/16** 은 착수=종료 불변이며, v2 의 「unexpected」 게이트는 `live_art = {k for k in snap_start if not k.endswith("/access.log")}` = **봉인 산출물만** 대상이다. `G0_EXPECT`(v1 9항) · `G0_EXPECT_V2`(v2 12항) 는 **명시 파일 목록**이라 디렉터리를 훑지 않으므로 신규 파일이 들어오지 않는다. 세 스크립트에서 신규 파일명 언급 **0건**. → **기대값 갱신 요구 없음.** ★ `pre_unblinding_audit*.py` **실행 0**(1회성 가드).

   - **⑧ ★ cowork 측 자진신고 1건 (본 블록 러너 아님)**: 본 지시서 교차검증 과정에서 cowork 의 검증 에이전트가 `experiments/runs/v3_confirm_rep1_seed201/metrics_public.json` 을 `cat` 으로 **1회 판독**했다(`wc -c` 로 충분했다). 해당 파일은 **봉인 밖 공개 파일**이고 그 내용(반복1 Δ 부호)은 `ledger.first_look_register` · `docs/45` §5 · 같은 폴더 `run.log` 에 **이미 등재**돼 있어 **새 정보 취득은 없다**. 다만 R5 가 반복1 을 「공개 저장소 미노출」로 등재하고 있으므로 사실만 기록한다. **`_sealed/` 접근 0 · `open_sealed` 0 · `emit_sign` 0 · 계산 0.** ★ **본 블록 러너는 §1-2 · F17 에 따라 이 파일의 «값» 을 읽지 않았다** — 바이트 수(24)와 키 이름(`['sign']`)만 확인했다.

   - **⑨ 미실행(본 블록이 하지 않은 것)**: **확증 GIN 학습 0**(`master_X`/`master_Y` 의 특징·라벨로 GIN 을 학습·예측한 행위 0 — S3 의 inner split 재현은 `fold_membership.csv` + `master_Y.parquet` 의 **분할·라벨 계수**만 쓰는 블록 R 과 동일 입력이며 학습·예측이 아니다) · **개봉 0**(`unblinding_performed` **false** 유지) · **`_sealed/` 읽기·쓰기·복사·해싱 0** · **`_sealed` 디렉터리 생성 0** · `open_sealed` **0** · `emit_sign` **0** · `sap/decision.py` import·호출 **0** · `rqint_test` 호출 **0** · **순열 계산 0** · `metrics_public.json` **값 판독 0** · **동결 파일 수정 0**(`gin_seed_freeze.json` `10828447c6d33118…` · `gin_inner_valid_freeze.json` `038599c3e1576022…` · `…status.json` `bd329fefe613971f…` · `ladder_freeze.json` · `rqint_procedure_decisions_v1.json` `16776f21df6ae29b…` · `experiments/sap/sap_1_2_hash_registry.json` · SAP 14모듈 · `sap/rqint*.py` 3종 · `ladder_confirmatory.py` `13a17129db6a6679` · `train_ladder.py` `1d0a5357aafe57bd` · `confirmatory_oof_*.py` · `v2_GNN/src/*` · `experiments/rqint/` 기존 산출물 · `docs/30`·`docs/50`·`docs/64`·`docs/66` 착수=종료 동일) · **플래그 해제 0**(3곳 전부 true) · **하이퍼파라미터 재탐색 0** · 새 통계 기준·성공기준·Holm 항목 신설 **0** · `B` 재정의 **0** · **`pre_unblinding_audit*` 실행 0** · **`pip` 0** · **네트워크 = Gmail 읽기 전용 `get_thread` 2회**(스레드 `<GMAIL-MSGID>`·`<GMAIL-MSGID>` · `METADATA_ONLY` 형식 · **본문·첨부 판독 0** · 다운로드 0) **외 0** · **발신·초안 작성·수정·라벨 변경 0** · **git commit·push·add·stash·status 0**(HEAD **`566f487`** · 커밋 **21** · `git ls-files -m` **4건** 착수=종료 동일) · **봉인 25/291/275/16 착수=종료** · **`__pycache__` 4,541 착수=종료**(모든 파이썬 호출에 `PYTHONDONTWRITEBYTECODE=1` + `-B`, 신설 스크립트 최상단 `sys.dont_write_bytecode = True`) · `data/raw/` 접근 **0** · `data/processed/` 쓰기 **0**(읽기만) · `AGENTS.md` 갱신 **0**.

> 지시서 = `docs/106_gin_harness_design_freeze_prompt_for_vscode.md` · 리포트 = `docs/106_gin_harness_design_freeze_report.md` ·
신규 산출 **6종** = `v3_Multimodal/config/gin_confirm_harness_freeze.json`(`1af993fde7330e1d…` · 21,968 B) · `…status.json`(`5df9a7c4bfa64749…` · 1,439 B) · `v3_Multimodal/src/confirmatory_gin_rep.py`(`1e6642bf9ecac5a2…` · 42,450 B · 840행) · `experiments/runs/v3_gin_harness_selftest/selftest.json`(`37b0af4d2ef74ad4…` · 11,246 B · 12/12 PASS) · `experiments/runs/v3_gin_budget/gin_budget_estimate.json`(`f42e839d154611f2…` · 11,151 B · `not_an_authorization` true) · `experiments/runs/v3_gin_budget/README.md`(`6fd60d4a59c48b49…` · 1,224 B) ·
기록 = 본 항목 57 · `docs/45` §2 1행 + §3 3행 · `ledger.json`(`timeline` 54 → **55** · `frozen_artifacts` dict 19 → **22키** · `correspondence` 30 → **33** · `authoritative_sources` 31 → **32** · `indent=2`+말미 개행 유지) ·
무수정 대조 착수=종료 sha256 동일 = 위 ⑨ 전항 · 봉인 **275/16/291/25** · HEAD `566f487`·**21**. **미실행**: 위 ⑨ 전항.

---

58. **기록 정정 — `selftest.json` 바이트 수 오기 정정 (분석·실행·동결 결과 변경 없음) (블록 AS — `docs/109` · 확증 학습 0회 · 개봉 0)**:

   - **① 원래 기록**: 블록 AR 이 `experiments/runs/v3_gin_harness_selftest/selftest.json` 의 크기를 **11,246 B** 로 적었다. 구값이 적힌 곳은 정확히 **3곳** — `docs/33` **L2049**(항목 57 ③ 본문) · `docs/33` **L2065**(항목 57 말미 「신규 산출 6종」 줄) · `experiments/provenance/ledger.json` 의 **`timeline[54].event`**.

   - **② 정정/명확화 내용**: 같은 파일의 **실측값은 11,399 B** 다(sha256 **`37b0af4d2ef74ad410c76603a143c7089161c6f35a75d68271a8a8cf94c78e09`** — sha256 은 구기록과 동일하다). 즉 바뀐 것은 **바이트 수 표기 하나뿐**이고 파일 자체는 한 바이트도 달라지지 않았다. 블록 AS 착수 게이트 G5 가 이 파일의 sha256·바이트를 live 실측으로 대조하면서 드러났다.

   - **③ 발견 시각**: **2026-09-16**(블록 AS 착수 게이트 G5). 정정 기입은 본 항목이며 블록 AS 종료 시점이다. 지시서 `docs/109` F5 가 이미 **11,399** 로 교정된 값을 싣고 있었고, F14 의 트리아지 정본 `docs/108` 이 이를 확정했다.

   - **④ 분석·실행·결과 영향**: **없다.** 파일 내용·selftest 판정 모두 불변이다 — `n_cases` **12** · `n_pass` **12** · `n_skip` **0** · `all_pass` **true**. 동결 대상은 sha256 이지 바이트 수 표기가 아니므로 v1 하네스 `FREEZE_SHA256` 상수·`preconditions` 해시·블록 AR 의 어떤 판정도 영향을 받지 않는다. 재계산·재학습 **0**.

   - **⑤ 원본 바이트·기존 항목 무수정**: **구값이 적힌 3곳의 원문을 고치지 않았다.** 본 항목은 **append-only 정정**이며 항목 57 과 `ledger.timeline[54]` 은 블록 AR 종료 바이트 그대로다. 블록 AS 의 종료검증 stale 값 스캔은 이 **3곳을 기지 예외로 명시 제외**하고, 그 밖에 구값이 남아 있는 곳은 본 항목 ① 의 정정 인용 1건뿐임을 확인했다.

   - **⑥ 관련 신규 파일과 해시**: 본 정정과 직접 관련된 신규 산출은 `experiments/runs/v3_gin_start_authorization/manifest_t1_pre_v2.json`(**`d471756459d6eb37…`** · 8,843 B — v1 산출물 6종의 착수 시점 sha256·바이트를 실측 기입) 과 `…/manifest_t2_pre_exec.json`(**`e5230d159515b726…`** · 15,191 B — 종료 시점 재해싱 결과) 이다. 두 파일 모두 `selftest.json` 을 **11,399 B** 로 기록한다.

   - **⑦ 귀책**: cowork — 기록 결함이며 러너 행위가 아니다(`gin_start_supersede.json` 의 `defect_attribution` 축자와 동일).

---

59. **정보 접근 범위 명확화 — 공개 범위 축소 및 봉인 자료 비열람 절차 강화 (블록 AS — `docs/109` · 확증 GIN 학습 0회 · 플래그 해제 0 · 개봉 0)**:

   - **① 원래 기록**: 블록 AR(항목 57 ⑥)이 「승인조건 6건 실질 전건 충족 · `still_unspecified` 2건도 해소 — **그럼에도 차단 유지**」로 끝냈고, 차단 플래그 3곳(`rqint_procedure_decisions_v1.json` · `gin_seed_freeze.json` · `gin_inner_valid_freeze.json`)의 `gin_start_still_blocked` 를 **전부 true** 로 둔 채 「해제는 별도 블록·별도 승인」이라고 적었다. 비열람 증거는 봉인 계수 대조(25/291/275/16)와 `access.log` 자기기록에 의존했다.

   - **② 정정/명확화 내용**: 교수님 **명시 승인**(2026-09-15 12:42:00 KST · 메시지 `<GMAIL-MSGID>` · 축자 「착수는 바로 진행합시다. 본 메일은 <EXTERNAL-REVIEWER> 박사에게 전달하겠습니다. 진홍 드림.」)이 도착했으나 **플래그를 false 로 바꿀 수 없다**. 따라서 본 블록은 **플래그를 해제하지 않고**, v1 을 0바이트 보존한 채 **append-only supersession** 으로 신규 실행계약을 만들었다(= 「legacy block was valid, then superseded」). 아울러 비열람 주장의 **기술적 한계를 문면으로 못박고**(⑧) 공개 범위를 축소했다.

   - **③ 발견 시각**: 교착 확인 = `docs/107`(6차 트리아지) · 해법 확정 = `docs/108`(7차 트리아지) · 사용자 확정 = **2026-09-16**(`docs/108` §7) · 수행 = 블록 AS(**2026-09-16**).

   - **④ 분석·실행·결과 영향**: **확증 결과 수치에 영향 0** — 확증 GIN 학습·추론 **0회**, 재계산 0, 개봉 0, 순열 0. 영향은 «실행계약과 기록» 에 한정되며 아래 ①~⑨ 로 적는다.

     - **①(교착의 사실관계)**: 플래그를 든 3파일 중 **②③ 이 v1 하네스 `confirmatory_gin_rep.py` 의 `FREEZE_SHA256`(L75)에 해시 상수로 박혀 있어** 값을 바꾸면 하네스가 `load_frozen()` 에서 스스로 **exit 2**(`EXIT_FREEZE_MISMATCH`)로 멈춘다. 게다가 3파일 전부 「동결 파일 0바이트 수정」 규율 대상이다. 승인은 있는데 플래그를 내릴 수 없는 교착이다.

     - **②(v1 무수정 보존 원칙)**: ①②③ 의 `gin_start_still_blocked` 는 **착수=종료 3/3 `true`** 이고 sha256 도 착수=종료 동일이다(`16776f21df6ae29b…` · `10828447c6d33118…` · `038599c3e1576022…`). 같은 플래그가 true 로 적힌 나머지 **6개 config**(`gin_confirm_harness_freeze` · `holm7_latefusion_freeze` · `post_interim_freeze_v1_0`(+`.status`) · `r3_second_party_freeze` · `rqint_procedure_decisions_v0`)도 **전부 무수정**이다 — 그 6개는 게이트가 아니라 비실행 선언 필드다. v1 산출물 6종 + `gin_inner_valid_freeze.status.json` 도 **0바이트**다.

     - **③(신규 8종 해시)**: `config/gin_start_supersede.json` **`c061d033ae35bea3…`**(6,359 B) · `config/gin_confirm_harness_freeze_v2.json` **`ec43025a61378e18…`**(26,558 B) · `config/gin_confirm_harness_freeze_v2.status.json` **`73c0a69c571fb075…`**(2,056 B · 선행과 **동일 9필드**) · `src/confirmatory_gin_rep_v2.py` **`644abf4f272c51e6…`**(28,331 B · 575행) · `experiments/runs/v3_gin_start_authorization/selftest_v2.json` **`adcc143c29ac44d7…`**(12,476 B · **10/10 PASS** · `all_pass` true) · `…/manifest_t1_pre_v2.json` **`d471756459d6eb37…`**(8,843 B) · `…/manifest_t2_pre_exec.json` **`e5230d159515b726…`**(15,191 B) · `experiments/runs/v3_gin_budget/gin_budget_estimate_v2.json` **`8325c6d00bfb6f10…`**(13,865 B).

     - **④(v2 게이트 6조건 · exit 12)**: `require_supersession(cfg_dir=None, supersede_path=None)` 이 **0** v1 산출물 2종 sha256 → **1** ①②③ sha256 → **2** ①②③ 플래그 **전부 true**(false 면 **거부**) → **3** 승인 이벤트 존재·sha256·`is_authorization` true → **4** 승인 이벤트의 `blocking_artifacts_verified` 3건이 1·2 실측과 일치 → **5** `unblinding_performed` false **그리고** 봉인 계수 25/291/275/16(stat-only) 을 검사하고, 하나라도 불충족이면 **exit 12**(v1 의 11 과 구분)로 거부한다. ★ **v1 `enforce_gin_block()`(exit 11)은 train·verify 경로에서 호출하지 않는다** — ①②③ 이 앞으로도 true 이므로 그 함수를 부르면 영구 차단이 된다. 두 인자는 **`--stage selftest` 의 음성 검사 전용**이고 `train`·`verify` 분기는 **인자 0개**로 호출하며 CLI 옵션·환경변수 주입 경로는 **만들지 않았다**. ★★ 이것은 가드 «완화»도 «축소»도 아니며 v1 과 **논리적으로 비교 불가**다 — v1 은 「플래그 **false** ⇒ 실행」, v2 는 「플래그 **true** + 6조건 ⇒ 실행」이므로 두 허용집합은 **서로소**다. 안전성 근거의 정확한 형태는 다음 한 문장이다: **v1 의 단일 플래그 조건을, 해시 고정 + 외부 승인 이벤트 + 봉인 계수 + 비개봉을 함께 요구하는 조건으로 «교체»했고, 교체된 조건이 요구하는 증거가 더 많다.** 음성 검사 **T5·T6·T7 은 전부 거부**(exit 12)로 끝났고, 원본 ①②③ 과 승인 이벤트는 **이동·개명·삭제·수정 0**(합성 cfg 디렉터리 사본으로만 수행).

     - **⑤(v1↔v2 과학명세 기계 diff)**: `spec`(6키) · `output_scale`(10키) · `harness` 의 `inner_split`·`feature_block_fit_population`·`rng_scope`·`recipe_constants_A_wd`·`early_stopping`·`reuse_import_not_reimplement`·`code_level_prohibition_guards` — **지정 9키 전건 바이트 동일**(`json.dumps(…, sort_keys=True, ensure_ascii=False)` 비교 · `n_identical` **9/9**). `harness.stages`·`harness.default_stage` 는 v2 가 stage 를 4종으로 늘리므로 **diff 대상에서 제외**했다. → v2 는 **운영 supersession 이지 실질 amendment 가 아니다**. 시드(42·1·2) · 7모델 · 3반복 · 5 fold · epoch 상한 200 · **357 run** 전부 불변이며, `build_plan` 재실행이 **315/42/357 · OOF 63/primary 18 · [1092, 370]** 을 그대로 낸다(T8).

     - **⑥(승인 서신 3건)**: 스레드 `<GMAIL-MSGID>` 의 (i) outbound 2026-09-15 12:39:31 `<GMAIL-MSGID>` · (ii) **inbound 2026-09-15 12:42:00 `<GMAIL-MSGID>`**(착수 승인) · (iii) outbound 2026-09-15 12:44:19 `<GMAIL-MSGID>` 를 `ledger.correspondence` **33 → 36** 으로 등재했다. ★ **본 블록의 VS Code 세션에는 Gmail 도구가 연결돼 있지 않아 Gmail 호출을 0회 했다** — 세 건의 `message_id`·`thread_id`·시각·방향은 `docs/109` F11 **공급값**이며 본 블록에서 재측정하지 않았고, 각 엔트리의 `measurement` 필드에 그 사실을 적었다(블록 AS 편차 1 · 리포트 §5·§6).

     - **⑦(예산 v2)**: `gin_budget_estimate_v2.json` 은 v1 을 **0바이트 보존**하고 **수치·계산식 변경 0**(`numeric_baseline_changed` **false** · `v1_bytes_unchanged` **true**)인 채 **라벨과 해석만** 바꾼다. F12 표를 원자료(`results/ladder/*_seed*.csv` 50파일 mtime + `v3_ladder/run.log` early-stop 50건)에서 **재도출해 마지막 자리까지 대조**했다 — 울타리 **771.286 s** · 잔존 **46 run** · 지속시간 합 **9,890.713 s** · epoch 합 **3,460** · 단가 **2.858588 s/epoch** · 블록별 10행·레짐 4행 전건 일치. ★ **`104.18 h` 는 상한이 아니다 — M0-M2 기준 max·2.0 = 141.90 h**(`upper_bound_claim_withdrawn`). 계획 범위는 **15.62~38.05 h**(mean·1.3 · `planning_range_mean_1_3`)로 적고 자원 예약은 보수측 **38 h**(`resource_reservation_hours`)로 잡는다 — 단일 대표값을 «중앙값» 으로 제시하지 않는다. RF wall 유래 선행비용 3.262 h 는 **`proxy_of_unknown_direction`** 으로 재라벨했다(v1 의 「과대추정·보수적」 방향 단언 철회). derating 3지점은 「신뢰구간·예측구간·확률 분위수가 아닌 **운영 배수**」다. `M2` 와 `A_chunk` 는 둘 다 side_dim=64 · concat 인데 **7.4557배** 차이가 나고, 실행 순서와 속도의 정렬은 기계 상태 효과와 **양립하는 관찰·추론이며 원인 확정이 아니다**.

     - **⑧(A-plus 비열람 증거 + 한계 문구)**: 4시점 manifest 중 **1·2시점만** 본 블록에서 만들고 **지도교수 서명·OSF 업데이트 등록은 실행 «후» 첨부**로 미뤘다(`deferred_to_post_execution` 2건 · `signature_status` `deferred_to_post_execution`) — 첫 run 을 지연시키지 않기 위해서이고, 12:42 승인 직후 추가 서명을 요청하면 이미 한 승인을 되묻는 것으로 읽히기 때문이다(사용자 확정 2026-09-16). 두 manifest 에 다음 두 문구를 **축자로** 넣었다: (a) 「`_sealed/`의 `access.log` 는 운영 코드가 자체 생성한 응용계층 로그로서, 기록 대상 경로를 통한 접근이 관찰되지 않았음을 보조적으로 보여 준다. 다만 OS 수준의 독립 감사로그가 아니므로 관리자 접근, 우회 경로 또는 로그 외 접근의 부재를 독립적으로 증명하지는 않는다.」 (b) **논문 경계 문구** 「연구팀은 실행 전후 manifest 의 해시 일치, 봉인 루트의 불변 확인, 응용계층 접근로그 및 실행 전 승인 기록을 통해 결과 비열람 절차를 문서화하였다. 그러나 봉인이 암호학적 키 통제나 OS 수준 독립 감사로 강제된 것은 아니므로, 이 자료는 절차 준수에 대한 감사추적을 제공하지만 절대적 비열람을 기술적으로 증명하지는 않는다.」

     - **⑨(비실행 선언)**: **확증 GIN 학습·추론 0회**(`--stage train` 은 `require_supersession()` 통과 후 **스텁**으로 정지 — 학습 코드 0) · **플래그 해제 0**(3/3 true 착수=종료) · `_sealed/` **읽기·쓰기·복사·해싱 0** · `_sealed` 디렉터리 생성 **0**(봉인 **25/291/275/16** 착수=종료 · stat-only 스냅샷만) · `open_sealed` **0** · `emit_sign` **0** · `sap/decision.py` import·호출 **0** · `rqint_test` 호출 **0** · **순열 계산 0** · `unblinding_performed` **false** · `experiments/runs/v3_confirm_rep1_seed201/metrics_public.json` **값 판독 0** · **동결 파일 수정 0**(SAP 11모듈 + `sap/rqint*.py` 3 + `ladder_confirmatory.py` + `train_ladder.py` + `ladder_freeze.json` + `sap_1_2_hash_registry.json` + ①②③ + `gin_inner_valid_freeze.status.json` = **22 경로** 착수=종료 sha256 동일) · **git 쓰기 0**(`commit`·`push`·`add`·`stash`·`status` 0 · HEAD **`566f487`** · 커밋 **21** · `git ls-files -m` **4건** 착수=종료 동일) · **`.git/index.lock` 제거·이동 0**(0 B · 2026-08-06 19:59 KST 선재 락 — `docs/104` L86 선례대로 진행) · **`pip` 0** · **네트워크 0**(Gmail 도구 미연결 — 읽기 전용 호출도 0회) · **`__pycache__` 4,541 착수=종료**(archive 포함 규약 · 제외 시 4,540) · `data/raw/` 접근 **0** · `data/processed/` 쓰기 **0**.

   - **⑤ 원본 바이트·기존 항목 무수정**: 항목 57 이하 기존 문면은 **한 글자도 고치지 않았다.** 본 항목은 append 다. `ledger.json` 의 기존 `frozen_artifacts` **22 엔트리**·`correspondence` **33 엔트리**·`timeline` **55 엔트리**도 무수정이며 신규 키·행만 추가했다.

   - **⑥ 관련 신규 파일과 해시**: 위 ④-③ 의 **신규 8종** 전건 + 기록 3곳(`docs/33` 항목 58·59 · `docs/45` §2 +1행 / §3 +4행 · `experiments/provenance/ledger.json` `timeline` **56** · `frozen_artifacts` **26** · `correspondence` **36** · `authoritative_sources` **33**).

> 지시서 = `docs/109_gin_start_supersession_prompt_for_vscode.md` · 리포트 = `docs/109_gin_start_supersession_report.md` ·
신규 산출 **8종** = 위 ④-③ · 기록 = 본 항목 58·59 · `docs/45` §2 1행 + §3 4행 · `ledger.json`(`timeline` 55 → **56** · `frozen_artifacts` 22 → **26키** · `correspondence` 33 → **36** · `authoritative_sources` 32 → **33** · `indent=2`+말미 개행 유지) ·
무수정 대조 착수=종료 sha256 동일 = ①②③ · v1 산출물 6종 · `gin_inner_valid_freeze.status.json` · 동결 22경로 · 봉인 **25/291/275/16** · HEAD `566f487`·**21**. **미실행**: 위 ④-⑨ 전항.

60. **기록 정정 — 블록 AS 서신 3건 `measurement` 재측정·원래 축자 복원 (블록 AS 편차 1 해소 · cowork · 분석·실행·동결 결과 변경 없음)**:

   - **① 원래 기록**: `docs/109` F11 은 `ledger.correspondence[33..35]` 의 `measurement` 를 「Gmail `get_thread`(METADATA_ONLY) — id·thread_id·시각·방향만 실측. 제목은 본 블록에서 재측정하지 않았다(스레드 선례 계승).」로 축자 고정했으나, 블록 AS 러너 세션에 Gmail 도구가 없어 3건에 「본 블록 Gmail 호출 0회 — VS Code 세션에 Gmail 도구가 연결돼 있지 않다. id·thread_id·시각·방향은 docs/109 F11 공급값이며 본 블록에서 재측정하지 않았다. 제목도 본 블록에서 재측정하지 않았다(스레드 선례 계승 — correspondence[31]·[32]).」를 기입했다(항목 59 ④-⑥ · 리포트 §5 편차 1). 러너의 선택은 §10-1 에 부합했다.

   - **② 정정 내용**: 사용자 결정(**2026-09-21** 「편차 1 (나)」)에 따라 cowork 가 Gmail 읽기 전용 `get_thread(threadId <GMAIL-MSGID>, METADATA_ONLY)` **1회**로 재측정했다. 실측 = `<GMAIL-MSGID>` 2026-09-15T03:39:31Z(= **12:39:31 KST**) · SENT · outbound / `<GMAIL-MSGID>` 03:42:00Z(= **12:42:00 KST**) · IMPORTANT,INBOX · inbound / `<GMAIL-MSGID>` 03:44:19Z(= **12:44:19 KST**) · SENT · outbound — 상대방 전건 `<EMAIL>` · thread_id 전건 `<GMAIL-MSGID>` → **F11 공급값과 전건 일치(불일치 0)**. 따라서 `measurement` **1필드만** F11 원래 축자로 교체했다. 제목·본문·스니펫은 METADATA_ONLY 로 반환되지 않아 **판독 0**.

   - **③ 발견 시각**: 편차 발생 = 블록 AS(2026-09-16) · 사용자 결정·재측정·교체 = **2026-09-21 15:09:59 KST**.

   - **④ 분석·실행·결과 영향**: **없음.** 확증 계산 0 · 학습 0 · 개봉 0 · `_sealed/` 접근 0 · `gin_start_still_blocked` 변경 0 · git 0. `gin_start_supersede.json` 의 `network_calls` 0 · `network_calls_note` 는 블록 AS 당시의 사실이므로 **0바이트 유지**. 교체 전 문면은 `ledger.timeline[56].superseded_text_preserved` 에 축자 보존.

   - **⑤ 원본 바이트·기존 항목 무수정**: 항목 59 이하 문면 무수정(append). `ledger.json` = `correspondence[33..35]` 의 `measurement` 외 필드·`correspondence[0..32]`·`timeline[0..55]`·`frozen_artifacts` 26키·`authoritative_sources` 33 **기계 assert 로 무수정 확인**, `indent=2`+말미 개행 유지.

   - **⑥ 관련 파일과 해시**: `experiments/provenance/ledger.json` `39bcd915df6fb462`(389,863 B) → 교체 후 값은 `docs/45` §2 해당 행 · `timeline` 56 → **57** · `correspondence` **36 유지**.

61. **★ 확증 GIN 학습 착수 전 동결 — 재개 게이트 보충 · side 입력 도출 확정 (블록 AT — `docs/110` · 학습 0회 시점 기록)**:

   - **① 원래 기록**: (ⅰ) 실행계약 v2(`gin_confirm_harness_freeze_v2.json` `ec43025a61378e18…`)의 **6조건 게이트 조건 5** 는 `unblinding_performed is False` **그리고** 봉인 계수 `{25, 291, 275, 16}`(`confirmatory_gin_rep_v2.py` L87 `SEALED_COUNTS_EXPECTED` · `sealed_counts()` L134 는 저장소 전체에서 경로에 `_sealed` 가 든 모든 파일을 센다) 일치를 함께 요구한다. 즉 **첫 세션이 GIN 결과를 `_sealed/` 에 쓰는 순간 계수가 바뀌어 이후 모든 재개가 exit 12 로 막힌다.** 예산(계획 범위 **15.62~38.05 h** · 예약 38 h · 세션 상한 권장 8 h)상 세션 분할은 필수이므로, v2 문면 그대로는 완주가 불가능하다. (ⅱ) v1·v2 어느 동결 파일도 **GIN(LadderNet) side 입력의 블록 구성**을 명시하지 않았다 — `MODEL_BLOCKS` 는 RF 용 블록 목록이고, GIN 은 구조를 그래프 브랜치가 맡으므로 `B0`(Morgan) 의 처리와 융합 방식이 미규정 상태였다. (ⅲ) 등록 `docs/30` **§4 L78** 은 「**neural family는 mean + DeepSets 병행(보조). 통제군 side 차원 64 통일.**」 이라고 적고 있으나 **그 이행 방식**(어느 블록에 무엇을 적용해 64로 맞추는지, 64 미만 블록은 어떻게 하는지, RF family 에도 적용되는지)은 어디에도 규정돼 있지 않았다.

   - **② 보충·확정 내용** (사용자 결정 **2026-09-21** D1~D5 · 재논의 금지):
     - **D1 재개 게이트** = v2 **무수정** + 재개검사 추가. 첫 착수는 v2 `require_supersession()` 을 **그대로** 통과한다. 재개 때도 v2 게이트를 **그대로 자식 프로세스로(인자 0개)** 호출하되, 실패가 **「조건 5 단 하나」**(`5:not_unblinded_and_sealed_counts`)일 때만 대체검사 **5′**(a~g)를 적용한다. **논리 근거**: 조건 3 이 승인 이벤트 `gin_start_supersede.json` 의 sha256 을 `PINNED_SHA256` 으로 고정하므로 이벤트 안의 `unblinding_performed`(false)는 바뀔 수 없다 → **조건 0~4 가 통과하고 조건 5 만 실패하면 실패 원인은 봉인 계수뿐**이다. 5′ = **a** GIN 소유 3개 반복 디렉터리를 제외한 stat-only 계수 == 25/291/275/16 · **b** 전체 `_sealed` = 25 + (생성된 GIN 반복 디렉터리, ≤3) · **c** 반복별 `_partial/*.npz` 집합 == 그 반복 `checkpoint.jsonl` 키 집합(키 중복 0 · 8필드 · 개행 종료 · **마지막 줄 잘림은 자동 복구하지 않고 exit 14·상신**) · **d** `oof_*.npz` ⊆ 5 fold 전부 체크포인트된 (model, seed) 그룹 · **e** 그 밖의 봉인 파일 ⊆ {`checkpoint.jsonl`,`env_fingerprint.json`,`access.log`,`train_stdout.log`} ∪ `_orphans/*`(전부 `failures.jsonl` 등재) · `.tmp` 0 · **f** `manifest_t3_launch.json` 의 `harness_sha256`·`contract_sha256` == 현재 파일 sha · **g** `v3_gin_stability*`·`v3_gin_confirm_consensus*` 0 · `unblinding_performed` false. 그 밖의 rc·실패 목록 → **exit 14, 학습 0**. **v2 파일은 0바이트 수정**이고 규칙은 학습 전에 동결 파일(`gin_train_contract.json`)에 고정했다. ★ 이는 v2 게이트의 **완화가 아니다** — v2 게이트를 그대로 통과시키고 그 위에 **조건을 더 얹는다**(5′ a~g 는 v2 조건 5 가 검사하지 않던 파일 단위 정합까지 요구한다).
     - **D2 범위** = **확증 315회만**(7모델 × train seed 3 × 반복 3 × outer fold 5) → 반복별 OOF 21 × 3 = **63 봉인**. **안정성 42 · consensus · macro AP/Δ/부호 산출 · RQ-int 는 전부 다음 블록**이다(동결 실행순서 「Complete and seal the confirmatory GIN run (15 units x 3 seeds) FIRST; only afterwards add seeds 3 and 4…」).
     - **D3 side 입력 도출** = 각 모델의 RF 블록 목록에서 **`B0`(Morgan)만 뺀 것**, `concat` 융합, `M0` = side 없음(`side_dim` 0), 블록 스케일링은 RF 와 같은 fit 결과 그대로(**추가 스케일링 0**). **근거 축자 3건**(러너가 실재 확인): (ㄱ) `docs/30` **L71** 「`| M0 | 구조만 (RF=Morgan r=2 2048bit / GIN=graph embedding) | — |`」 → GIN 에서 구조 블록은 그래프 임베딩이 대체한다. (ㄴ) `gin_inner_valid_freeze.json` `feature_block_fit_population.rationale` 「Using the same population keeps the input representation identical across families for the same rung.」 (ㄷ) `train_ladder.py` `LADDER`(L288~)의 확증 관련 사다리 `fusion` = **`"concat"`**(`"gated"` 는 범위 밖 M4 뿐). 모순 문면 탐색(`docs/30`·`docs/50`·`docs/64`~`67`·`gin_*freeze*.json` 전수 grep `Morgan`·`gated`·`StandardScaler`·`side`·`64`) 결과 **L78 외 적중 0**.
     - **D4 L78 이행** = **P-ID 만 φ(PCA-64), P-FAM 원차원.** `B_pid` multi-hot(확증 fold 별 **1,090~1,139** 차원 — 러너 재측정)에 등록된 φ(= train-fit z-score → PCA-64, `B_seq` 와 같은 방식)를 적용한다. **φ 정의** = `B_pid.fit(otr)` → `M = B_pid.transform(arange(N))` → fit 행 = `otr` 중 `M` 행합 > 0 인 행(= outer-train ∩ 매핑) → `StandardScaler().fit(M[fit])` → `PCA(n_components=64, svd_solver="full", random_state=42).fit(Xs[fit])` → 전 행 변환 → **행합 0 인 행은 정확히 0 으로 재설정**(assert). fit 행 ⊆ `otr`(leak 0) · fit 행 수 ≥ 64 assert. 구현은 **새 하네스 안의 얇은 래퍼**이고 `ladder_confirmatory` 는 **0바이트 수정**이다. **P-FAM 은 `B_fam` 이 확증 fold 별 40~42 차원 < 64**(러너 재측정) 라 PCA 로 64 를 만들 수 없다 → **원차원 유지**하고 「통제군 side 차원 64 통일이 P-FAM 에 대해 **물리적으로 불가능**」을 **한계로 명시**한다. `C_ccap` 은 이미 64차원이다.
     - **D5 L78 적용 범위** = **neural family 전용으로 해석·기록.** 「side」는 GIN(LadderNet) 입력을 가리키는 neural 전용 용어이고, **같은 문단에서 RF family 집계는 따로 규정**돼 있다(「RF family(primary) 집계 = 표적 mean-pool → z-score → PCA-64 고정 피처.」). 따라서 「통제군 side 차원 64 통일」은 RF family 에는 해당하지 않는다 → **RF 확증 P-ID 가 `B_pid` 원차원인 것은 이 해석 아래에서 편차가 아니다.** RF 확증 산출물은 본 블록에서 **건드리지 않는다**. DeepSets 는 등록 §4 「보조자료(본문 아님)」라 본 블록 **범위 밖**이다.

   - **③ 발견 시각**: v2 조건 5 의 구조적 교착 = **cowork 2026-09-21**(지시서 `docs/110` F6) · L78 충돌 = **cowork 교차검증 독립 에이전트 1회, 2026-09-21**(`docs/110` §8 결함 1 [치명]) · 사용자 확정 D1~D5 = **2026-09-21**.

   - **④ 분석·실행·결과 영향**: **과학 명세 변경 0.** 본 항목은 **확증 GIN 학습 0회 시점**에 기록됐다(착수 타임스탬프보다 **이전**). 바뀐 것은 **운영 규약**(재개 게이트·세션·쓰기·실패 처리)과 **미규정이던 side 입력의 확정**뿐이다. 하이퍼파라미터·seed·순서·모델범위·분할·inner split·블록 정의 변경 **0** · `gin_start_still_blocked` **3/3 true 유지** · `unblinding_performed` **false** · 개봉 **0** · 지표 산출 **0**(macro AP·Δ·부호·CI·p·consensus·`rqint_test`·순열·`emit_sign`·`open_sealed`·`sap.decision` 전부 0) · 기존 25개 봉인 트리 **291/275/16 불변** · git 쓰기 0. ★ **공개/봉인 경계는 v2 규격보다 «강화»** — F10 의 공개 허용 항목 중 **`n_epochs`(epoch 수)를 공개하지 않는다**. 이유: `n_epochs = min(best_ep + PATIENCE, EPOCHS)` 등식(러너가 `train_ladder.py` L226~250 판독으로 확인)이 성립하므로 `n_epochs < 200` 이면 `best_ep = n_epochs − 30` 이 그대로 역산되고, `best_ep` 는 v2 규격이 **봉인 파일 내용**으로 둔 값이다. `n_epochs` 는 봉인 `checkpoint.jsonl` 에만 두고 공개 타이밍은 `wall_seconds` 뿐이다. 추가 봉인 3종(`_partial/*.npz` · `train_stdout.log` · `_orphans/`)도 **전부 봉인 쪽 = 공개 축소 방향**이다. `train_stdout.log` 는 `train_ladder.log()` 가 `print` 라서(`train_ladder.py` L81) `train_variant` 가 `validMacro … best …` 를 stdout 으로 내보내는 것을 **가로채 봉인**하기 위한 것이다(stderr 도 함께 가로챈다).

   - **⑤ 원본 바이트·기존 항목 무수정**: 항목 60 이하 문면 **무수정**(append-only). `docs/33` 삽입 전 바이트 **426,394**(`a6576a782b93cb84`) 접두 보존. F4 권한 체인 **13종** · F5 재사용 모듈 **12종** 착수 전후 sha256 동일(기계 대조). `confirmatory_gin_rep_v2.py`·`confirmatory_gin_rep.py`·`ladder_confirmatory.py`·`train_ladder.py` **0바이트 수정**.

   - **⑥ 관련 파일과 해시**: 신규 **4종** — `v3_Multimodal/config/gin_train_contract.json` **`e50f972674e782f5…`**(26,915 B · 실행계약 «운영 보충» · `is_authorization` **false** · `authorization_is_made_by` = `gin_start_supersede.json` · `supplements` = `gin_confirm_harness_freeze_v2.json` · `science_spec_changed` **false** · 하네스 sha 미포함(순환 방지 · 블록 AS 선례)) / `v3_Multimodal/src/confirmatory_gin_train.py` **`714f98983cceff85…`**(81,844 B) / `experiments/runs/v3_gin_start_authorization/selftest_train.json` **`f715add2e49afd23…`**(15,347 B · **U1~U12 + U3b·U10b 14/14 PASS · n_skip 0** · 확증 라벨 학습 **0회** · 합성 스모크 1회) / `experiments/runs/v3_gin_start_authorization/plan_confirmatory_315.json` **`121d6db4d1e2a4be…`**(29,138 B · 315 단위).

   - **⑦ 안정성·지표·consensus 는 범위 밖**: 안정성 **42회**(대표 unit `(201,f4)`·`(202,f1)`·`(203,f0)` × seed 값 3·4 × 7모델) · GIN consensus + macro AP·Δ 산출(봉인) · `metrics_full.json` · Holm ⑧ RQ-int · 개봉 승인·시점 — **전부 다음 블록 이후**다. 본 블록의 하네스는 315 단위 + 63 npz 완료 시 `confirmatory_complete` 를 기록하고 **안정성 단위로 넘어가지 않는다**(`--stage run` 에 안정성 스케줄 0 — 자체검사 U2 로 기계 확인).

   - **⑧ cowork 자진신고 2건**(`docs/110` F16 축자): (1) 「**2026-09-21 cowork 가 `experiments/runs/v3_confirm_rest/_sealed/checkpoint.jsonl` 앞 600 B 를 판독**했다(선례 레이아웃 확인 중 `head -c 600`). 노출 필드 = `repeat`·`model`·`fold`·`n_train`·`n_test`·`dim`·`wall_s`·`peak_rss_gib`·`sha256_partial`·`ts_kst`·`session_seq` — **성능 값·예측값·Δ·부호 0**. 이후 cowork 는 `_sealed/` 를 stat 만 했다. 해당 `access.log` 는 **수정하지 않는다**(기록은 `docs/33`·ledger 로만).」 (2) 「같은 날 cowork 의 `git status` 1회가 `.git/index.lock`(0 B)을 남겼고 삭제 권한을 받아 **즉시 제거**했다(연구 산출 영향 0).」 — 러너 착수 시 `.git/index.lock` **부재** 실측 확인.

62. **★ 확증 GIN 학습 315회 완주·봉인 — 세션 1 비정상 종료 1건 · 데이터 손실 0 (블록 AT — `docs/110` §4 · 지표 산출 0 · 개봉 0)**:

   - **① 원래 기록**: 항목 61 이 블록 AT **착수 전**(확증 GIN 학습 0회 시점)에 재개 게이트 5′·side 입력 도출·공개/봉인 경계를 동결했고, 본런은 그 계약 아래 **2026-09-21 16:31:08 KST** 에 착수됐다(`sessions.jsonl` 세션 1 `mode: first_launch` · 게이트 rc **0** + `GATE_PASS` · AC true · Wattage **94** · load1 **1.9**). 항목 61 ⑥ 시점에는 완주 계수(F15 예측 **28 / 681+n / 19 / 662+n**)와 실패·고아 전건이 미확정이었다.

   - **② 완주 결과** (전건 실측 · 러너 독립검증 V1~V5 · `manifest_t4_post_confirmatory.json` **`a59ab54afd515085…`** 8,660 B):
     - **확증 315/315 단위 · OOF 63/63 봉인 완료.** 반복별 = `checkpoint.jsonl` **105줄** · `_partial/*.npz` **105** · `oof_*.npz` **21** (rep1_seed201 · rep2_seed202 · rep3_seed203 전부 동일). 체크포인트 키 **315 전건 유일**(중복 0) · 8필드 고정 · 개행 종료 · **파일 기록 순서가 `plan_confirmatory_315.json` 순서와 완전 일치**(rep 별 부분수열도 일치) → 비정상 종료에도 **재실행·중복·순서 교란 0**.
     - **실패 0 · 재시도 0 · 고아 0 · `.tmp` 잔존 0.** `failures.jsonl` 은 **3반복 전부 생성되지 않았다**(= 등재할 실패가 없었다는 뜻이며 파일 부재 자체가 실패 0 의 증거다). 동결 `failure_policy` 의 재시도 경로는 **한 번도 발동하지 않았다**.
     - **총 계산 wall = 44,229.991 s = 12.29 h**(공개 `run.log` 315줄 합 = `manifest_t4.total_wall_seconds` **바이트 일치**). 착수→완주 경과 **14 h 43 m 03 s**(= 계산 12.29 h + 중단 공백 2 h 24 m 36 s + 게이트·조립 등). 예산 v2 계획 범위 **[15.62, 38.05] h** 의 **하한보다 빠르다**(예약 38 h 중 실사용 ≈ 14.7 h).
     - **봉인 계수 = F15 예측과 완전 일치** — 착수 **25 / 291 / 275 / 16** → 완주 **28 / 681 / 662 / 19**(고아 n = **0** 이므로 예측식 `681+n`·`662+n` 의 n 이 0). **기존 25개 봉인 트리는 291 / 275 / 16 불변**(GIN 3개 반복 디렉터리를 제외한 stat-only 재계수로 기계 확인). ★ **다음 블록 게이트 상수 = `{n_sealed_dirs: 28, n_sealed_files_total: 681, n_sealed_artifacts: 662, n_access_log: 19}`** 를 새 봉인 기준선으로 쓴다.
     - OOF 63종 전건 구조 검증(러너 독립 · 봉인 **값 판독 0**) = 키 4종 `{P, y, pt_index, cid_order}` · `P` **(1092, 370) float32** · `y` **int8** · `pt_index` == `arange(370)` · `cid_order` **(1092,)** · **`y` 가 `master_Y` 와 63/63 전건 동일** · **`cid_order` 가 `master_X.cid` 와 63/63 전건 동일**. `_partial` **315/315** 의 sha256 이 체크포인트 `artifact_sha256` 와 **전건 일치**, OOF **63/63** sha256 이 `manifest_t4.oof_sha256` 와 **전건 일치**.

   - **③ 발견 시각 · 세션 1 비정상 종료(신규 편차)**: **2026-09-22 00:07:54 KST**, 착수 7 h 36 m 46 s 경과 지점에서 **세션 1 프로세스(python PID 73859)가 아무 기록도 남기지 않고 종료**했다. 실측 증거 = (ⅰ) `caffeinate` PID 73861 의 `ClientDied`(3 assertion 동시) 가 **00:07:54**(`pmset -g log`) — `caffeinate` 는 자식이 끝나면 함께 죽으므로 **python 종료 시각 = 00:07:54** · (ⅱ) 마지막 `_partial` 커밋 mtime **00:07** · (ⅲ) `sessions.jsonl` 에 세션 1 의 `session_end` **없음** · (ⅳ) 공개 `nohup_run.out` 에 traceback·예외·`stopped_reason` **없음** · (ⅴ) `~/Library/Logs/DiagnosticReports/` 에 python 크래시·jetsam 리포트 **0건** · (ⅵ) 그 뒤 **00:16:07 에 `'Idle Sleep'`**(AC 전원 · 배터리 100%)이 걸렸다 = **그 시점에 sleep 을 막는 `caffeinate` assertion 이 이미 없었다**는 독립 확증. **원인은 확정하지 못했다** — 시스템 로그 보존 기간이 해당 구간에 미치지 않아(`log show` 질의 결과 0건) 외부 SIGKILL·프로세스 그룹 정리·커널 수준 종료를 구분할 근거가 없다. **하네스 내부 실패 경로가 아니라는 것만은 확실하다**(내부 실패·시그널 경로는 전부 `failures.jsonl` 또는 `stopped_reason` 을 남기며 둘 다 0건이다). ★ 지시서 `docs/110` AT-9·§7 이 「`caffeinate` 는 덮개 닫힘 절전을 막지 못할 수 있음」을 **착수 전에 이미 한계로 명시**한 항목과 같은 계열의 운영 리스크다. **재개**는 사용자가 AT-9 재개 명령을 그대로 실행해 이뤄졌다 — **02:27:50**(게이트 A `load1=2.18 ≥ 2.0` 거부) · **02:30:36**(`load1=2.01 ≥ 2.0` 거부) · **02:32:26 통과**(`load1=1.37`) → 세션 2 python PID **89684**(`caffeinate` 89685 · `run.pid` 89532). 즉 **부하 게이트가 설계대로 2회 거부하고 3회차에 통과**했다.
     - 세션 2 는 v2 게이트를 **그대로 자식 프로세스로 호출**해 **rc 12 · 실패 목록 정확히 `["5:not_unblinded_and_sealed_counts"]`** 를 받고, 항목 61 D1 의 **대체검사 5′(a~g) 전건 통과**로 재개했다(`sessions.jsonl` 세션 1 `mode: resume` 행 = `legacy_counts` 25/291/275/16 · `n_stray_sealed_dirs` 25 · `n_gin_dirs` 2 · `n_orphans_moved` **0**). **D1 의 재개 게이트가 실제 사고에서 설계대로 작동한 첫 사례**다.
     - 재개 시 `compute_lock` 이 죽은 보유자를 **stale 로 인수**했다(`[LOCK] 획득 pid=89684 … (stale 인수: lock_holder_dead(pid=73859))`). 이 인수 사실은 **기존 `compute_lock.py`(F5 재사용 모듈 · 0바이트 수정)가 추적 파일 `experiments/runs/.compute_lock.stale.jsonl` 에 1줄 append** 하는 설계이므로, `git ls-files -m` 가 **F1 기대 4건 → 5건**이 됐다(추가분 = 그 1줄뿐 · 내용 = ts·인수 pid·사유·원 락 파일 원문). **git 인덱스 접촉·`git status`·`add`·`commit`·`push`·`stash` 는 0회**이고 HEAD `566f487`·커밋 **21**·`.git/index.lock` **부재**는 불변이다. 이는 **연구 산출이 아니라 락 감사 기록의 정상 증가**이며 §6 롤백 대상이 아니다(착수 이후 롤백 없음 규정).

   - **④ 분석·실행·결과 영향**: **과학적 영향 0 · 데이터 손실 0.** 비정상 종료 시점에 진행 중이던 단위는 `.tmp`→`os.replace`→체크포인트 append 라는 **원자적 커밋 규약** 때문에 (ⅰ) 커밋 전이었으면 흔적 없이 폐기되고 재개 때 **처음부터 다시 계산**되며 (ⅱ) 커밋 후였으면 체크포인트 키로 **건너뛴다**. 고아 판정 대상(`.tmp` 또는 체크포인트 없는 `.npz`) 이 **0건**이었으므로 종료 시점은 **단위 경계**였다. 따라서 **부분 학습된 산출물이 봉인에 섞여 들어갈 경로가 없었고**, 체크포인트 순서 == plan 순서라는 독립 검증이 이를 다시 확인한다. ★ **지표 산출 0** — macro AP · Δ · 부호 · CI · p · consensus · `rqint_test` · 순열 · `emit_sign` · `open_sealed` · `sap.decision` **전부 0회**. outer-test 예측으로 계산한 지표 **0**(예측값 접촉 = `np.isfinite` 기술검사 + 조립 행배치·sha 대조 **두 가지뿐**). **안정성 42 단위 실행 0** · **consensus 디렉터리 0** · **`metrics_full.json` 생성 0**(저장소 내 16종은 전부 RF 계열 기존 산출물 `v3_confirm_*`·`v3_consensus_*`·`v3_latefusion_*`·`v3_confirm_rftuned_*` 이고 mtime 2026-07-27~2026-08-06 · GIN 디렉터리 내 **0건** · 본 블록 접촉 0). `gin_start_still_blocked` **3/3 true 유지** · `unblinding_performed` **false** · 개봉 **0**. **공개 스캔 위반 0** — 지시서 §4-2 V4 지정 8종(존재 13파일 · `failures.jsonl` 3건은 실패 0 으로 부재) 전수에서 금지 키(`macro_ap`·`delta`·`sign`·`best_v`·`best_ep`·`n_epochs`·`valid`·`ap`) **0** · 단어경계 정규식 적중 **0** · `run.log` 는 **8열 고정 · 줄당 소수 리터럴 정확히 1개**(`wall_seconds` 뿐 → `n_epochs` 비공개 유지 기계 확인).

   - **⑤ 원본 바이트·기존 항목 무수정**: 항목 61 이하 문면 **무수정**(append-only). `docs/33` 삽입 전 바이트 **437,433**(`ca049a8e464ce603`) 접두 보존. **F4 권한 체인 13종 · F5 재사용 모듈 12종 · 항목 61 의 신규 4종(계약·하네스·selftest·plan) · `manifest_t3_launch.json` 전부 착수=완주 sha256 동일**(러너 기계 대조 **33/33**). `__pycache__` **4,541** 불변. 기존 25개 봉인 트리 쓰기 **0**(`access.log` 포함).

   - **⑥ 관련 파일과 해시**: 신규 **1종** — `experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json` **`a59ab54afd515085…`**(8,660 B · 공개 · `n_units` 315 · `n_oof` 63 · `n_sessions` **2** · `total_wall_seconds` 44,230 · `stability_units_executed` **0** · `consensus_built` **false** · `metrics_computed` **false** · `unblinding_performed` **false** · `n_epochs` 관련 값 **0**). 반복별 `checkpoint.jsonl` sha256 = rep1 **`f078df96e4957de3…`** · rep2 **`1b50c30573db67d7…`** · rep3 **`049ba9dff26de761…`**. 봉인 산출 = `oof_*.npz` **63** + `_partial/*.npz` **315** + 반복별 `checkpoint.jsonl`·`env_fingerprint.json`·`access.log`·`train_stdout.log`.

   - **⑦ 여전히 막혀 있는 것**: **안정성 42회**(대표 unit `(201,f4)`·`(202,f1)`·`(203,f0)` × seed 값 3·4 × 7모델) · **GIN consensus + macro AP·Δ 산출(봉인)** · `metrics_full.json` · **Holm ⑧ RQ-int**(λ·ρ 진단 선행) · **개봉 승인·시점**(별건) · 지도교수 서명·OSF 업데이트(실행 «후» 첨부) — **전부 다음 블록 이후**다. 본 블록 하네스는 315 단위 + 63 npz 완료 시 `confirmatory_complete` 를 기록하고 **안정성 단위로 넘어가지 않았다**(`sessions.jsonl` 마지막 행 = `{"event": "confirmatory_complete", "n_units": 315, "n_oof": 63, "n_sessions": 1}` · 안정성 디렉터리 **0**).

63. **★ GIN 안정성 학습 착수 전 동결 — 안정성 계약·하네스(AT 하네스 import 재사용) (블록 AU — `docs/111` · 학습 0회 시점 기록)**:

   - **① 원래 기록**: (ⅰ) `gin_seed_freeze.json`(`10828447c6d33118…`)의 안정성 설계 축자 — `execution_order` 「Complete and seal the confirmatory GIN run (15 units x 3 seeds) FIRST; only afterwards add seeds 3 and 4 (the 4th and 5th entries of the ordered list) on the three representative units.」 · `delta_definition` 「Delta_ij = macroAP_ij(M2b) - macroAP_ij(M1b), computed on the held-out fold of outer unit i under training seed j.」 · `delta_unit_caveat` 「This fold-level evaluation unit differs from the confirmatory estimand, which is the complete-OOF metric over all 1,092 drugs.」 · `firewall` 「Stability results must not change the primary results, hypothesis adjudication, model/hyperparameter/seed selection, or the aggregation method. Stability outputs are written to a directory separate from the confirmatory run outputs.」 · 대표 unit `representative_units` `[[201,4],[202,1],[203,0]]`(SHA-256 mod 5 규칙 · 재현식 결과 `[4,1,0]` 러너 실측) · 추가 seed = `training_seeds_ordered[3:5]` = `[3, 4]`(확증 `[42,1,2]` 와 교집합 **0**). (ⅱ) 산출 경로는 v2 규격 `gin_confirm_harness_freeze_v2.json` `spec.a_run_directories.stability` = `experiments/runs/v3_gin_stability/` 로 이미 동결돼 있다. (ⅲ) ★ **동결 레이아웃 문면 차이** — v1 `gin_confirm_harness_freeze.json`(`1af993fde7330e1d…`)과 v2(`ec43025a61378e18…`)의 `spec.c_sealed_layout.files."oof_{model}_seed{t}.npz"` 는 `"train_seed_domain_confirmatory": [42, 1, 2]` 와 함께 **`"train_seed_domain_stability_additional": [3, 4]`** 를 적어 두었고, 같은 절 `validated_by` 축자는 「**경로 문자열·키 스키마만 (schema_fixture). 본 블록은 _sealed 디렉터리를 0개 만든다.**」다. `docs/106` L423 표도 「`oof_{model}_seed{t}.npz` … model ∈ 7, t ∈ {42,1,2}(+안정성 값 3,4) → 확증 **21개**/반복」로 같은 표기를 쓴다. (ⅳ) 블록 AT 하네스 `confirmatory_gin_train.py`(`714f98983cceff85…`)는 안정성 42회를 돌릴 수 없다 — `make_plan()` 이 **315 를 assert**(L561) · `repeat_dir()` 가 `v3_gin_confirm_rep{r}_seed{s}` 로 **하드와이어**(L123~125) · CLI 가 `--stage`/`--out` 뿐 · 재개 게이트 5′(g)가 **`v3_gin_stability*` 디렉터리 존재 시 거부**(L454~457). 그리고 그 파일 수정은 금지다. (ⅴ) 봉인 계수가 항목 62 완주로 **28/681/662/19** 가 되어 v2 `require_supersession()` 조건 5(`SEALED_COUNTS_EXPECTED` 25/291/275/16)는 **영구 불충족**이다 — 러너 실측: v2 게이트 자식 프로세스 호출 결과 **rc 12 · 실패 접두 줄 1개 · 파싱 목록 정확히 `["5:not_unblinded_and_sealed_counts"]`**.

   - **② 보충·확정 내용** (사용자 결정 **2026-09-22** E1~E4 · 재논의 금지):
     - **E1 하네스** = **신규 계약 + 신규 하네스, AT 하네스 import 재사용.** 신규 `v3_Multimodal/config/gin_stability_contract.json` + 신규 `v3_Multimodal/src/confirmatory_gin_stability.py`. 과학 경로(그래프·side 조립·φ(B_pid)·원자적 쓰기·봉인 기록기·v2 게이트 호출)는 동결 `confirmatory_gin_train.py` 를 **모듈 import**(`import confirmatory_gin_train as at`)해 그 함수를 **그대로 호출**한다 — **재구현 0**. import 규약 = 「**sha 확인 → import → `os.path.samefile(at.__file__, <그 경로>)` assert**」(불일치 = exit 14 · 학습 0). 허용목록 **29 이름**(`build_graphs`·`build_side`·`atomic_npz`·`sealed_access`·`sealed_stdout_append`·`sealed_ckpt_append`·`sealed_ckpt_read`·`unit_key`·`call_v2_gate`·`parse_gate_failures`·`count_sealed`·`count_pycache`·`pub_line`·`pub_jsonl`·`pub_json`·`read_power`·`wait_load_ok`·`env_info`·`Stopper`·`now_kst`·`sha256_file` + 상수 8종) · 금지목록(확증 디렉터리 하드와이어·AT 산출물 기록·315 assert·5′(g) 거부 계열) 참조 **0**. ※ `at.__file__` 은 위 samefile assert 가 요구하는 **import 동일성 확인**이며 재사용 «함수» 가 아니므로 계약 `reuse.allowlist` 와 층위를 분리해 센다(자체검사 S3 가 기계 구분). **AT 계약·하네스 포함 동결물 전부 0바이트.**
     - **E2 장시간 본런 생존성** = **이번 블록은 감시 래퍼 없음 · 결정 보류.** 약 1.7 h 단일 세션. 비정상 종료 시 **사람이 같은 착수 명령을 다시 실행** → 재개 게이트가 판정한다. **착수·재개는 macOS 터미널**에서 한다(항목 62 교훈 — 러너 래퍼 셸 수명에 본런을 묶지 않는다). 감시 래퍼/짧은 세션 결정은 장시간 블록(예: Holm ⑧ 순열) 때 다시 한다.
     - **E3 `/중단`·`/재개` 일반화** = **안 함**(AE 전용). 중단 = `kill -TERM $(cat experiments/runs/v3_gin_stability/python.pid)` · 재개 = 착수 명령 재실행.
     - **E4 동결 레이아웃 문면 차이** = **fold 단위 partial 만 봉인 + 차이 기록.** ①(ⅲ) 의 `train_seed_domain_stability_additional: [3, 4]` 는 **문자 그대로는 충족 불가능**하다 — 안정성 설계는 대표 outer unit 당 5 fold 중 **1 fold** 만 학습하므로(42 = 3 unit × 7 model × 2 seed) 1,092행 전체를 덮는 완전 OOF 행렬을 조립할 4 fold 가 존재하지 않는다. **해석** = `gin_seed_freeze.delta_definition`(fold 수준 추정량)이 우선하며, 그 규격 절의 `validated_by` 축자가 스스로 「경로 문자열·키 스키마만」 검증됐음을 밝히고 있으므로 seed 영역 표기는 **스키마 예시이지 산출 의무가 아니다**. **채택** = `_sealed/_partial/{model}_rep{r}_fold{k}_seed{t}.npz` **42개만** 봉인하고 `oof_*.npz`·`metrics_full.json`·consensus 는 만들지 않는다. **partial 형식은 확증과 동일**(`P_test` float32 `(n_te, 370)` · `best_ep` int32 · `best_v` float64 · 행 순서 = `np.where(fold_membership.fold == k)[0]` 오름차순) — 다음 블록이 15셀(3 unit × seed 42·1·2·3·4)을 계산할 때 seed 42·1·2 는 확증 `_partial`, seed 3·4 는 이 블록 `_partial` 을 같은 판독 경로로 읽기 때문이다. **과학 명세 영향 0**(`science_spec_changed` false). 계약 `frozen_layout_reconciliation` 에 규격 두 파일의 축자·`docs/106` 축자·충족 불가 사유·해석·채택을 전문 기록했다.
     - **재개 게이트 5″(a~h)** — v2 **무수정**. 순서 = v2 게이트(자식 프로세스·인자 0개) → 고아 처리 → 5″. **공통 선행** = rc **12** 그리고 파싱 목록 == `["5:not_unblinded_and_sealed_counts"]`(★ 블록 AT 와 달리 **첫 착수도 rc 12** 를 기대한다 — 봉인 계수가 이미 28/681 이므로). rc 0 = 「봉인 계수 불변 = 설명 불가」 거부. **논리 근거**는 항목 61 D1 과 같다(조건 3 이 승인 이벤트 sha256 을 고정 → 조건 0~4 통과 + 조건 5 단독 실패 ⇒ 원인은 봉인 계수뿐). 조건 = **a** 확증 3트리 + `v3_gin_stability/` 제외 stat-only 계수 **25/291/275/16** · **b** 확증 3트리만의 계수 **3/390/387/3** 그리고 **stat 지문 `5440aefcded112bcd425f61968f9974898f26efe2beab69155f7a5a47cf3333b`**(390줄 · 이름·크기만 · 파일 열지 않음) · **c** 전체 `_sealed` 디렉터리 == 28 + (안정성 봉인 존재 ? 1 : 0) · **d** 안정성 `_partial/*.npz` 이름 집합 == `checkpoint.jsonl` 키 집합 · 모든 키 ∈ 계획 42 · 잘린 마지막 줄 = **자동 복구 없이 거부** · **e** 봉인 최상위 ⊆ {`checkpoint.jsonl`,`env_fingerprint.json`,`access.log`,`train_stdout.log`} · 하위 ⊆ {`_partial`,`_orphans`} · `oof_*` **0** · 고아 전부 `failures.jsonl` 등재 · `.tmp` 0 · **f** 안정성 봉인 또는 `manifest_s1_launch.json` 이 있으면 그 `harness_sha256`·`contract_sha256` == 현재 파일 sha · **g** `v3_gin_confirm_consensus*` 0 · `unblinding_performed` false · AT `manifest_t4` sha == `a59ab54afd515085…` · **h** F4 13종·F5 12종·F6 7종 sha 불변. **mode** = 봉인 없음+manifest 없음 `first_launch` / 봉인 없음+manifest 있음 `launch_retry`(manifest 재기록 0) / 봉인 있음+manifest 있음 `resume` / 봉인 있음+manifest 없음 **거부**. 거부 = exit 14 · 학습 0.
     - **OOF 조립 없음 · 지표 산출 0** — 안정성 추정량이 **fold 수준**이라 조립 대상이 아니다. macro AP·Δ·부호·SS 분해·CI·p·consensus·`rqint_test`·순열·`emit_sign`·`open_sealed`·`sap.decision` **전부 0**. 유일한 지표 계산 = `train_variant` 내부 inner-valid monitor(봉인).
     - **firewall 쓰기 가드** — 하네스가 여는 모든 쓰기 경로(`open(…,"w"/"a")`·`atomic_npz`·`pub_*`·`sealed_*`·`shutil.move` 목적지·`os.makedirs`)가 `_assert_stab_path()` 를 거쳐 `experiments/runs/v3_gin_stability/` 밖이면 `AssertionError`. 예외 = `compute_lock` 내부 쓰기(모듈 소관)와 `--stage selftest` 한정 `tempfile.mkdtemp()` 루트(허용 집합은 selftest 진입 시에만 채워지며 `run`·`plan`·`status`·`finalize` 진입 시 비어 있음을 assert). **봉인 기록기 호출 조건** — `at.sealed_access`·`at.sealed_stdout_append`·`at.sealed_ckpt_append` 는 첫 줄에서 `os.makedirs(sdir, exist_ok=True)` 를 하므로(영구 교착 위험: 「봉인 있음 + manifest 없음 = 거부」) `os.path.isdir(<stab>/_sealed)` 가 참일 때만 부른다. 봉인 디렉터리 생성은 **manifest_s1 기록 직후 단 한 곳**뿐이다.
     - **착수 = 사용자 macOS 터미널**(E2). 러너는 본런을 띄우지 않는다. `caffeinate -dimsu nohup` · `run.pid` = caffeinate PID · `python.pid` = 하네스가 락 획득 직후 기록 · 착수 전 **load1 < 1.4 대기 루프**(하네스 자체 게이트 A 통과선은 2.0) · AC **96 W** 필수(Wattage ≥ 90).

   - **③ 발견·결정 시각**: 동결 레이아웃 문면 차이(E4) = **cowork 교차검증 독립 에이전트, 2026-09-22**(`docs/111` §8 결함 1 [치명]) · AT 하네스 재사용 경계·봉인 기록기 조기 생성 교착·launch_retry sha 미대조 등 결함 16건 = **cowork 2026-09-22** · 사용자 확정 E1~E4 = **2026-09-22**.

   - **④ 분석·실행·결과 영향**: **과학 명세 변경 0.** 본 항목은 **GIN 안정성 학습 0회 시점**에 기록됐다(`manifest_s1_launch.json` **부재** = 착수 이전임의 기계 증거). 확증 경로와 **바뀌는 것은 train_seed 값뿐**(42·1·2 → 3·4)이며 같은 `fold_membership.csv`·`folds.json` 교차확인, 같은 `inner_split(scaf, otr, 1000*split_seed + fold, 9)`(inner-valid **97**), 같은 `rest.fit_fold`, 같은 `at.build_side`(D3·D4 · φ(B_pid)), 같은 `tl.train_variant(data, device, side_dim, "concat", seed)` 를 쓴다. 하이퍼파라미터·seed 목록·순서·모델범위·대표 unit 변경 **0** · seed 대체 **0** · 결과 기반 재학습 **0** · `gin_start_still_blocked` **3/3 true 유지** · `unblinding_performed` **false** · 개봉 **0** · 지표 산출 **0** · 확증 3트리·기존 25트리 쓰기 **0**(`access.log` 포함 · stat 만). side_dim 교차확인표(확증 공개 `run.log` 실측 21행: `(201,f4)` P-FAM **53** · `(202,f1)` **54** · `(203,f0)` **52** · 그 밖 M0 0·M1 2·M1b 12·M2b/P-ID/C-CAP 76)를 계약에 동결하고 본런 중 매 전환에서 assert 한다.

   - **⑤ 원본 바이트·기존 항목 무수정**: 항목 62 이하 문면 **무수정**(append-only). `docs/33` 삽입 전 바이트 **447,491**(`41d80e5664ebc986`) 접두 보존. **F4 권한 체인 13종 · F5 재사용 모듈 12종 · F6 블록 AT 산출 7종 = 32/32 착수 전 sha256 동일**(러너 기계 대조). `confirmatory_gin_train.py`·`gin_train_contract.json`·`confirmatory_gin_rep_v2.py`·`confirmatory_gin_rep.py`·`train_ladder.py`·`ladder_confirmatory.py` **0바이트 수정**. `__pycache__` **4,541** 불변 · 전체 봉인 **28/681/662/19** 불변 · 확증 stat 지문 **`5440aefc…`** 불변.

   - **⑥ 관련 파일과 해시**: 신규 **4종** — `v3_Multimodal/config/gin_stability_contract.json` **`e092c18ff7afd4f2…`**(37,474 B · 실행계약 «운영 보충» · `is_authorization` **false** · `authorization_is_made_by` = `gin_start_supersede.json` · `supplements` = [`gin_confirm_harness_freeze_v2.json`, `gin_train_contract.json`] · `science_spec_changed` **false** · 하네스 sha 미포함(순환 방지 · 블록 AS·AT 선례)) / `v3_Multimodal/src/confirmatory_gin_stability.py` **`c68a4a242a734408…`**(88,296 B · stage 5종 · CLI `--stage`/`--out` 뿐) / `experiments/runs/v3_gin_stability/selftest_stability.json` **`c2c8d9bde7232ebf…`**(16,305 B · **S1~S13 + S10b 14/14 PASS · n_skip 0** · 재개 게이트 진리표 **①~⑰ 18/18** · 확증 라벨 학습 **0회** · 합성 스모크 1회) / `experiments/runs/v3_gin_stability/plan_stability_42.json` **`492f03600ae7c5ac…`**(4,397 B · **42 단위** · `plan_sha256` `620eb83d25412ff8…` · `oof_assembled` false).

   - **⑦ 범위 밖**: **GIN consensus + macro AP·Δ 봉인 산출** · `metrics_full.json` · 안정성 15셀 **SS 분해**(서술 전용 — REML·ICC·검정 금지) · **Holm ⑧ RQ-int**(λ·ρ 진단 선행) · **개봉 승인·시점**(별건) · 지도교수 서명·OSF 업데이트(실행 «후» 첨부) — **전부 다음 블록 이후**다. 본 블록 하네스는 42 단위 완료 시 `stability_complete` 를 기록하고 **조립·지표로 넘어가지 않는다**(자체검사 S2 가 확증 단위 스케줄 **0** 을, S12 가 금지 이름 **0** 을 기계 확인).

   - **⑧ AT 하네스 5′(g)의 영구 거부는 무해하다**: `selftest_stability.json`·`plan_stability_42.json` 이 먼저 생기면서 `experiments/runs/v3_gin_stability/`(봉인 **없음**) 디렉터리가 만들어졌다. 그 결과 AT 하네스의 재개 게이트 5′(g)(「`v3_gin_stability*` 존재 시 거부」)는 **이후 영구 거부**가 된다. 이는 무해하다 — 블록 AT 는 **315/315 · OOF 63/63 으로 이미 완주·봉인**됐고(항목 62 · `sessions.jsonl` 마지막 행 `confirmatory_complete`), 본 블록은 **AT 하네스의 어떤 stage 도 실행하지 않는다**(`import` 해서 허용목록 함수만 호출 · 자체검사 S3 가 금지목록 참조 0 을 기계 확인). AT 산출물 7종은 착수 전 sha256 **전건 동일**이다.

64. **★ GIN 안정성 학습 42회 완주·봉인 — 단일 세션 무사고 · 실패·재시도·고아 0 (블록 AU — `docs/111` §4 · 지표 산출 0 · OOF 조립 0 · 개봉 0)**:

   - **① 원래 기록**: 항목 63 이 블록 AU **착수 전**(안정성 학습 0회 시점)에 사용자 결정 E1~E4 · 재개 게이트 5″(a~h) · firewall 쓰기 가드 · 동결 레이아웃 문면 차이(E4)를 동결했고, 본런은 그 계약 아래 **2026-09-22 23:48:56 KST** 에 사용자 macOS 터미널에서 착수됐다(`sessions.jsonl` 세션 1 `mode: first_launch` · v2 게이트 **rc 12** + 파싱 목록 정확히 `["5:not_unblinded_and_sealed_counts"]` · AC true · Wattage **94** · load1 **0.7**). 항목 63 ⑥ 시점에는 완주 계수(F14 예측 **29 / 727+n / 707+n / 20**)와 실패·고아 전건이 미확정이었다.

   - **② 완주 결과** (전건 실측 · 러너 독립검증 V1~V6 · `manifest_s2_post_stability.json` **`223209a99c694da0…`** 6,018 B):
     - **안정성 42/42 단위 봉인 완료 · OOF 조립 0**(설계대로 — `delta_definition` 이 fold 수준이라 조립 대상이 아니다. E4). `_sealed/_partial/*.npz` **42** · `checkpoint.jsonl` **42줄** · 키 **42 전건 유일**(중복 0) · 8필드 고정 · 개행 종료 · **기록 순서가 `plan_stability_42.json` 순서와 완전 일치**.
     - **실패 0 · 재시도 0 · 고아 0 · `.tmp` 잔존 0.** `failures.jsonl` 은 **생성되지 않았다**(= 등재할 실패가 없었다는 뜻이며 파일 부재 자체가 실패 0 의 증거다 — 항목 62 와 같은 규약). 동결 `failure_policy` 의 재시도 경로는 **한 번도 발동하지 않았다**.
     - **세션 1개 · 비정상 종료 0.** 착수 **2026-09-22 23:48:56 KST** → 완주 **2026-09-23 01:45:35 KST**, 경과 **1 h 56 m 39 s**(6,999 s). 총 계산 wall = **6,993.7 s = 1.94 h**(공개 `run.log` 42줄 합 = `manifest_s2.total_wall_seconds` 일치) → **비계산 구간은 5.3 s**(게이트·그래프 구성·락). 블록 AT 의 세션 1 비정상 종료(항목 62 ③)와 같은 사건은 **재발하지 않았다**.
     - **예산 대비**: F11 예측 **6,097 s ≈ 1.69 h**(확증 대표 3 unit 63단위 평균 145.17 s × 42) 대비 실측 **6,993.7 s = 1.94 h** 로 **+14.7%**. 예약 **4 h** 안이고 세션 상한 8 h 에 미치지 않는다. 초과분은 모델별 편차(단일 최장 단위 **406.633 s**(P-FAM) · 모델별 합 최대 M1b **1,486.8 s** · 최소 P-ID **293.1 s**)에 따른 것이며 **재시도·실패에 의한 것이 아니다**(재시도 0).
     - **봉인 계수 = F14 예측과 완전 일치** — 착수 **28 / 681 / 662 / 19** → 완주 **29 / 727 / 707 / 20**(고아 n = **0** 이므로 예측식 `727+n`·`707+n` 의 n 이 0). 안정성 봉인 = `_partial` **42** + `checkpoint.jsonl` + `env_fingerprint.json` + `train_stdout.log` + `access.log` = **46 파일**. **기존 25트리 25 / 291 / 275 / 16 불변** · **확증 3트리 3 / 390 / 387 / 3 불변 · stat 지문 `5440aefcded112bcd425f61968f9974898f26efe2beab69155f7a5a47cf3333b` 불변**(390줄 · 이름·크기만 · 파일을 열지 않음). ★ **다음 블록 게이트 상수 = `{n_sealed_dirs: 29, n_sealed_files_total: 727, n_sealed_artifacts: 707, n_access_log: 20}`** 를 새 봉인 기준선으로 쓴다.
     - `_partial` **42/42** 의 sha256 이 체크포인트 `artifact_sha256` 및 `manifest_s2.partial_sha256` 와 **전건 일치** · npz 키 **42/42** `{P_test, best_ep, best_v}` · `P_test` **float32 (n_te, 370)** · 행 수가 `fold_membership.csv` 의 `|te|`(rep1_f4 **219** · rep2_f1 **218** · rep3_f0 **218**)와 **42/42 일치**. 공개 `run.log` 의 `side_dim` 열은 F10 교차확인표와 **42/42 일치**(P-FAM = rep1 **53** · rep2 **54** · rep3 **52**). 분할 진단(공개 · 개수뿐) = inner-valid **97 · 3/3** · inner-train 양성 0 PT **0 · 3/3**.

   - **③ 신규 편차 0**: 본 블록에서 새로 발생한 이탈은 **없다**. 단일 세션 완주라 재개 게이트·실패 정책·세션 경계 중 **어느 것도 발동하지 않았다**(`mode: first_launch` 1회뿐 · `launch_retry`·`resume` 0). 항목 63 ② 에 동결한 5″(a~h)는 **첫 착수 판정 1회에만 쓰였고**(v2 게이트 rc 12 · 조건 5 단독 실패 · a~h 전건 통과 · `precondition_mismatch` **빈 목록**), 그 판정 결과는 `sessions.jsonl` 세션 1 `gate` 필드에 그대로 기록돼 있다. 항목 63 ⑧ 이 예고한 **AT 하네스 5′(g) 영구 거부**는 예고대로 성립하며 무해하다(AT 완주·봉인됨 · 본 블록은 AT stage 실행 **0** · `import` 후 허용목록 함수만 호출).

   - **④ 분석·실행·결과 영향**: **과학적 영향 0 · 데이터 손실 0 · 확증 결과 영향 0.** 안정성 산출은 `gin_seed_freeze.firewall` 축자(「Stability outputs are written to a directory separate from the confirmatory run outputs.」)대로 **확증 디렉터리 밖**(`experiments/runs/v3_gin_stability/`)에만 쓰였고, 하네스의 `_assert_stab_path` 쓰기 가드가 모든 쓰기 경로를 그 루트로 제한했다(selftest 임시 루트 허용 집합은 `run`·`finalize` 경로에서 비어 있음 — S11). **확증 3트리·기존 25트리 쓰기 0**(`access.log` 포함)이 계수·stat 지문 불변로 확인된다. ★ **지표 산출 0** — macro AP · Δ · 부호 · SS 분해 · CI · p · consensus · `rqint_test` · 순열 · `emit_sign` · `open_sealed` · `sap.decision` **전부 0회**(하네스 AST 재검 · 공개 로그 전수 스캔). **OOF 조립 0** · 안정성 `oof_*.npz` **0** · `metrics_full.json` **0** · consensus 디렉터리 **0** · 확증 단위 실행 **0**. 예측값 접촉 = `np.isfinite` 기술검사 + shape assert + finalize 의 키·shape·dtype·sha 대조 **세 가지뿐**이다(`docs/111` §2-6). 러너의 봉인 접근은 stat·이름·sha256·shape/dtype 로 한정되고 **사람 판독 0**이다.

   - **⑤ 원본 바이트·기존 항목 무수정**: 항목 63 이하 문면 **무수정**(append-only). `docs/33` 삽입 전 바이트 **461,986**(`c0d018829e673fa6`) 접두 보존. **F4 권한 체인 13종 · F5 재사용 모듈 12종 · F6 블록 AT 산출 7종 = 32/32 착수=완주 sha256 동일**(러너 기계 대조) · 항목 63 신규 4종(계약 **`e092c18ff7afd4f2`** · 하네스 **`c68a4a242a734408`** · selftest **`c2c8d9bde7232ebf`** · plan **`492f03600ae7c5ac`**) **전건 불변**이고 `manifest_s1_launch.json` 이 기록한 `harness_sha256`·`contract_sha256` 와도 일치한다(**착수 후 하네스·계약 교체 0** — V6). 플래그 ①②③ **3/3 true** · `unblinding_performed` **false**. `__pycache__` **4,541** 불변 · HEAD **`566f487`** · 커밋 **21** · `git ls-files -m` **5건** 착수=완주 동일(단일 세션이라 락 stale 인수 **0건** → `.compute_lock.stale.jsonl` append 없음 — 항목 62 ③ 의 증가와 다르다) · `.git/index.lock` 부재 · `git status`·`add`·`commit`·`push`·`stash` **0회** · 네트워크 **0**.

   - **⑥ 관련 파일과 해시**: 신규 **1종** — `experiments/runs/v3_gin_stability/manifest_s2_post_stability.json` **`223209a99c694da0…`**(6,018 B · 공개 · `n_units` **42** · `n_sessions` **1** · `n_failures_logged` **0** · `n_retries` **0** · `n_orphans` **0** · `total_wall_seconds` **6,993.7** · `confirmatory_units_executed` **0** · `oof_assembled` **false** · `consensus_built` **false** · `metrics_computed` **false** · `unblinding_performed` **false** · `n_epochs`·`best_*` 관련 값 **0**). 안정성 `checkpoint.jsonl` sha256 = **`1c1618e790ce33ef…`**. 봉인 산출 = `_partial/*.npz` **42** + `checkpoint.jsonl`·`env_fingerprint.json`·`access.log`·`train_stdout.log`(= 46). 공개 산출 = `run.log`(42줄 8열) · `split_diagnostics_public.json` · `env_public.json` · `sessions.jsonl`(3행) · `manifest_s1_launch.json` · `manifest_s2_post_stability.json` · `nohup_run.out` · `plan_stability_42.json` · `selftest_stability.json` · `run.pid`·`python.pid` (`failures.jsonl` 은 실패 0 이라 **부재**).

   - **⑦ 여전히 막혀 있는 것**: **GIN consensus + macro AP·Δ 봉인 산출** · `metrics_full.json` · **안정성 15셀 SS 분해**(서술 전용 — REML·ICC·검정 금지 · seed 42·1·2 는 확증 `_partial`, seed 3·4 는 본 블록 `_partial` 사용) · **Holm ⑧ RQ-int**(λ·ρ 진단 선행) · **개봉 승인·시점**(별건 · `unblinding_performed` **false** 유지) · 지도교수 서명·OSF 업데이트(실행 «후» 첨부) · 장시간 본런 생존성 대책(E2 로 보류 — 감시 래퍼 vs 짧은 세션) — **전부 다음 블록 이후**다. 본 블록 하네스는 42 단위 완료 시 `stability_complete` 를 기록하고 **조립·지표로 넘어가지 않았다**(`sessions.jsonl` 마지막 행 = `{"event": "stability_complete", "n_units": 42, "n_sessions": 1, "oof_assembled": false}`).

65. **★ RQ-int 후속 계산 명세 사전지정·동결 — D11 λ·ρ · D12 민감도 · Holm ⑧ 본런 규칙 (블록 AV — `docs/112` · 확증 계산 0회 시점 기록)**:

   - **① 원래 기록**: `docs/84` 대응표는 검토자 §3 Q2 의 **D11**(레버리지 진단 λ_k·ρ)·**D12**(민감도 2종)를 「SAP 1.2 + 결과」에 반영하는 것으로 적었다. 그러나 **실측 결과 그 «실행» 명세는 저장소 어디에도 반영돼 있지 않았다.** 전수 검색(P7 — `v3_Multimodal/config/*.json` · `experiments/sap/**` · `experiments/rqint/**` · `v3_Multimodal/src/sap/*.py` · `docs/100_sap_1_2_amendment.md` · `rqint_procedure_decisions_v{0,1}.json`, **255 파일**, 검색어 `레버리지`·`λ`·`lambda`·`ρ`·`rho`·`leverage`·`민감도`·`sensitivity`·`벤젠`·`benzene`·`싱글톤`·`singleton`·`e_g`) 적중 **112 파일**의 분류는 다음과 같다.
     - **① 상위 «결정 문면»(면제)** — `rqint_procedure_decisions_v0.json`(`status: decisions_recorded_not_frozen`) `decisions` 의 **D11**(「레버리지 진단 λ_k (k=1,2,10)·ρ 사전규정. 게이트 아님, 보고·주석용」 · `our_status: new_blocked_on_gin`)·**D12**(「민감도 분석 2종 — (i) no-scaffold 버킷 싱글톤 분해 (ii) 벤젠군 사전규정 결정적 2분할(정규화 SMILES 사전순). 폴드 배정 불변」), `docs/100_sap_1_2_amendment.md` §7 의 **D22**(`e_g` 선형화 부호뒤집기 = 보조 진단 전용).
     - **② 문서 목록·계획 언급(면제)** — `gin_confirm_harness_freeze_v2.json` L466 「Holm ⑧ RQ-int (GIN 산출 → λ·ρ 진단 선행 필요)」, `experiments/rqint/_parts/profile.json` 「벤젠군 = 'c1ccccc1'. D12 민감도 2종의 대상이다(본 블록에서 실행 0)」, `experiments/rqint/_parts/fixture.json` 의 합성 캘리브레이션 leverage(파일 자체가 「**NOT D11 λ_k/ρ**」로 명시), `calibration_design.json` 「레버리지 상위5 점유」(프로파일 대조 6지표 중 하나 · D11 아님).
     - 그 밖 적중은 **다른 뜻의 동형 문자열**이다 — 파이썬 `lambda` 키워드, RF 정규화 하이퍼파라미터 `lambda_selected.json`, late-fusion 가중 `lambda`(`holm7_latefusion_freeze.json` `p_ens = lambda·p_RF + (1−lambda)·p_seq`), `paired_scaffold_bootstrap` 의 `unit` sensitivity, `ladder_freeze.json` 의 pChEMBL sensitivity 트랙.
     - **③ 입력 경로·출력 스키마·수식·호출규약을 갖춘 «실행 가능한» 명세 = 0건.** 따라서 보류 사유 없음.

   - **② 보충·확정**: 본 블록은 그 **하위 실행 명세**를 사전지정했다(상위 결정의 재지정이 아니다). 사용자 결정 **G1~G6** = (G1) 112 = 명세 동결 전용(계산 0) · 113 = 지표 산출 — 감사 경계를 시간으로 분리 · (G2) 동결 범위 = 후속 전체(S1~S8) · (G3) `λ_k` 의 `T_k` = **`|e_g|` 상위 k 단일 정본**(아래 ③ 정정 경위) · (G4) 112 에 구현 + 합성 자체검사 포함 · (G5) 안정성 15셀 SS = Holm ⑧ 봉인 이후 독립 블록(116) · (G6) 113 조회 대장 = 조회행 추가 + Δ·부호 미산출 표기.
     동결 명세 **S1~S8** = S1 metrics 계약(113) · S2 D11 λ·ρ(114) · S3 D12 민감도 2종(115) · S4 Holm ⑧ 본런 규칙(115) · S5 D9 Δ·BCa(115) · S6 안정성 15셀 SS(116) · S7 공개/봉인 경계와 조회 대장 규약 · S8 사전지정 무결성.
     **축자 / 도출 / 해석을 분리 표기**했다 — 검토자 회신 docx 를 `word/document.xml` 의 `m:oMath` 구조 그대로 파싱해 9개 식(`d_{F,g}`·`e_g`·`T(z)`·`λ_k`·`ρ`·`G_eff`·양측 `p`·`SE(p̂)`·Holm `p̃_(k)`)을 복원하고 **부록 A「Word 삽입용 수식」의 선형식·LaTeX 평문과 전건 대조**했다(`unresolved` **0**). 도출(`e_g := (T_obs − T(z^{(g)}))/2`)은 축자(`e_g = d_{RF,g} − d_{GIN,g}`)와 합성에서 전 군 최대 절대차 **1.73e-18** 로 일치했다. 해석 항목(§4)은 4-1 `T_k` 정본 · 4-2 `n_eval`·`n_excluded_undefined` 봉인 축소 · 4-3 §9.1 `Δ` ↔ 부록 A7 `T` 표기 별칭 · 4-4 봉인 `checkpoint.jsonl` 기계 판독 1회 한정 · 4-5 `p_two_sided` 는 검증용 복제(정본 = `sap.rqint.rqint_test`) · 4-6 `B=100,000` 은 v1 `closures` 승계 · 4-7 S5 의 `B`·`seed` 는 공개 산출물 실측(`B=10000`·`seed_bootstrap=6001`)으로 모두 **별도 절에 명시**했다.

   - **③ 발견·결정 시각 및 G3 정정 경위**: 명세 결손 발견 = cowork **2026-09-23** · 사용자 확정 **2026-09-23**(G1~G6) · 외부 방법론 자문 **2026-09-23**(「후속 계산 명세 전체를 지표 산출 이전에 동결하라」). ★ **G3 정정**: cowork 가 처음 「`λ_k` 의 `T_k` 에 부호 포함 여부의 해석 여지가 있다」고 본 것은 **오류였다.** 회신 docx 의 해당 문단은 OMML `m:d`(`m:begChr m:val="|"`)로 **절댓값 기호를 싣고 있고**, 부록 A11·A12 가 절댓값을 명시하며, 무엇보다 §3(a) 본문(문단 89)이 「**`T_k` 는 `|e_g|` 가 큰 상위 `k` 개 군의 집합입니다**」라고 **평문으로** 못박는다. 단순 태그 strip 이 그 기호를 버린 것이 오해의 원인이었다(교차검증 실측). 따라서 `λ_k^signed` 는 **만들지 않는다** — 검토자가 요구한 적 없는 양을 동결물에 넣지 않는다. 무해한 병기가 아님은 합성에서 확인된다(T4): 부호 혼재 fixture `e = [−9, 5, 4, 1, 0.5]` 에서 절댓값 기준 `λ_1` = **0.6572** vs 부호 기준 대안 = **0.2028**.

   - **④ 영향**: SAP 1.2 **문면·`manifest.json`·11모듈 전부 0바이트 불변**(본 블록은 SAP 개정이 아니다 — 명세 JSON 이 `is_sap_freeze: false`·`modifies_sap_manifest: false`·`is_authorization: false` 를 스스로 선언한다). **확증 계산 0 · 확증 지표 0 · consensus 조립 0 · 개봉 0 · 모델 학습 0 · 네트워크 0 · git 쓰기 0.** 산출된 모든 수치는 **합성 fixture** 위의 값이며 산출물마다 `provenance: "synthetic_fixture"` 를 달았다.

   - **⑤ 원본 무수정**: F4 권한 체인 **13/13** · F5 재사용 모듈 **12/12** · F6 블록 AT 산출 **7/7** · F7 블록 AU 산출 **7/7**(합 **39/39**) · F8 SAP `manifest.json`(`d08dcedf2a22e1c8` · 55,303 B · `sap_version` 1.2) + 등록 11모듈 + **manifest 미등재 3종**(`sap/rqint.py` `eb842bc98140e9c5` · `sap/rqint_audit.py` `ddffe6d128de4d18` · `sap/rqint_synthetic.py` `27ef0011ee041920`) + `rqint_procedure_decisions_v{0,1}.json` **전건 sha 불변**. 차단 플래그 ①②③ `gin_start_still_blocked` **3/3 true** 유지.

   - **⑥ 관련 파일 해시**: 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json` **`fb1de5da61b30165…`** 30,762 B · 모듈 `v3_Multimodal/src/rqint_downstream.py` **`3e92a4ded1ea60b7…`** 42,331 B · 사전지정 문서 `docs/112_rqint_downstream_prespecification.md` **`cbb24b94873a00f5…`** 24,958 B · 축자 추출 `experiments/runs/v3_rqint_downstream_spec/reviewer_verbatim_extract.json` **`0f0bd65338692f36…`** 77,920 B · 추출기(일회성 · 동결 대상 아님) `…/extract_omml.py` **`a9f5844b320c07cf…`** 19,578 B · 자체검사 `…/selftest_downstream.json` **`73b398a579744f10…`** 7,694 B(T1~T12 **전건 PASS · skip 0**). 검토자 원문 `RQint_Reviewer_Response_<EXTERNAL-REVIEWER>_20260810.docx` **`0c29ddf201eb6751…`** 63,649 B(`m:oMath` **135**) 불변.

   - **⑦ 범위 밖**: 본 항목은 **명세 동결만** 기록한다. GIN consensus 조립·macro AP·Δ 산출(113) · D11 λ·ρ 실행(114) · Holm ⑧ 본런 + D9 BCa + D12(115) · 안정성 15셀 SS(116) · 개봉 승인·시점(별건) · 지도교수 서명·OSF 업데이트는 **각 블록에서 별도 기록**한다. ★ **장시간 본런 생존성 대책(E2)** 은 여전히 미해결이며 **블록 115 착수 «전»** 결정이 필요하다.

   - **⑧ 사전지정 무결성 증거**: 봉인 계수 **29 / 727 / 707 / 20**(착수=종료 불변) · **확증 3트리 stat 지문 `5440aefcded112bcd425f61968f9974898f26efe2beab69155f7a5a47cf3333b` 불변**(390줄) · `v3_gin_confirm_consensus*` 디렉터리 **0개** · `experiments/runs/.compute_lock.json` 부재 · `unblinding_performed` **false** · **확증 봉인 값의 사람 판독 0**. 조회 대장은 `docs/112` §2-1 예외에 따라 `…/v3_gin_stability/_sealed/access.log` 에 **machine_read 1줄만** 증가했다(`purpose: hash-compare` · `human_exposure: false` · `step: "블록 AV P5 해시 대조"` — `checkpoint.jsonl` 1종의 sha256 대조용). 그 1줄로 안정성 1트리 지문은 `dd546d64bffc2652…` → **`b4b493d265824709a242a12d37334659bf78a75bd51a46f8b0174f058d6e6cec`** 로 바뀌었고(46줄), 이 값을 **다음 블록의 게이트 상수**로 넘긴다. 본 블록이 실제로 판독한 것은 **검토자 docx 문면 · 코드·동결 JSON 문면 · `master_X.parquet` 의 SMILES(라벨 `master_Y` 미접근) · 기존 공개 산출물의 호출 파라미터 · 봉인 파일의 stat** 뿐이다.

66. **GIN consensus 조립 + 셀별 macro AP·Δ 봉인 산출 — 확증 GIN 최초 지표 (블록 AW — `docs/113` · 개봉 0 · 부호 미산출)**:

   - **① 원래 기록**: 블록 AV(`docs/112`)가 동결한 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da61b30165…` · 30,762 B)의 **`S1_metrics_contract`** 가 본 블록의 실행 대상을 사전지정했다 — repeat 축 = prediction-then-metric(3 rep OOF → `sap.consensus.build_consensus` → macro AP) · seed 축 = metric-then-average(시드별 Δ 먼저, 평균은 나중 · GIN 전용) · 셀 **cell_1 21 · cell_2 3 · cell_3 1 · cell_4 63**(추가 금지) · 대비 방향 **M2b − M1b** 고정 · `sap.metrics.macro_ap(y, P, eligible_pt=np.arange(370))` 명시 호출 · 양성 0 PT 제외(가변 분모 · AP=0 대입 금지) · 무효 규칙 값 무관 5종. 본 블록은 S1 을 **새로 정하지 않고 그대로 구현**했다.

   - **② 보충·해석**: (H1) `metrics_full.json` 에 학습 메타 `best_ep`·`best_v`(315 단위)를 **`training_meta_not_cells`** 키로 포함했다. 주 근거 = S7 `boundary` 축자 「metrics_full.json (AP·Δ·best_ep·best_v) 전부 봉인」(봉인 경계 문장). 보조 근거 = v2 `spec.c_sealed_layout.files["metrics_full.json"].content` 이나, 그 표는 **반복 디렉터리 `_sealed`** 구성표이고 블록 AT 는 반복별 metrics_full 을 만들지 않았다 — **S1 이 이를 consensus 디렉터리 metrics_full 하나로 통합했고 본 블록은 S1 을 따랐다**(위치 정합). 학습 메타는 S1 «셀»이 아니다(`cells_frozen_here_no_additions_later` 는 지표 셀 4종 88개에 관한 조항). 이 판독 과정에서 **partial sha ↔ checkpoint `artifact_sha256`** 대조를 함께 수행했고, 그 결과 **S1 에 없는 무효 사유 2종**(partial sha·키 집합 불일치 · 학습 메타 ≠ 315)을 두었다 — 둘 다 봉인 저장소 무결성 결함이므로 셀 전체 무효가 보수적이다(S1 무효 규칙의 **확장**으로 명시). (H2) S1 `access_ledger_rule`·S7 `block_113_row` 의 「Δ·부호 «미산출»」은 문면 그대로 읽으면 S1 자신의 셀(cell_2 Δ_GIN,s · cell_3 Δ_GIN)과 **모순**이다. 본 블록은 이를 **「Δ 의 부호를 따로 산출하지 않는다(`emit_sign` 0 · 부호 키 0 · 부호 비교 연산 0)」** 로 해석했고 Δ **값**은 `metrics_full.json` 에만 봉인했다. **이것은 amendment 가 아니라 명세 내부 모순의 해소(해석)** 이며 블록 H 선례(「층별 Δ 부호 미공개 · 전량 봉인」)와 같은 형식이다.

   - **③ 시각**: 하네스 신설 → 합성 selftest K1~K12 **전건 PASS · skip 0** → 하네스·selftest 동결 **2026-09-27 23:27:19 KST** → `--stage run` 착수 **2026-09-27 23:30:28 KST**(G-IDLE A load1 1.63 < 2.0 · 락 획득) → 완료 **2026-09-27 23:30:39 KST** · `wall_seconds` **10.72** · **run 1회**(재실행 0).

   - **④ 영향**: 봉인 **29/727/707/20 → 30/750/729/21**(신규 트리 `v3_gin_confirm_consensus_rep123/_sealed/` 1개 · 파일 23 = consensus 21 + `metrics_full.json` + `access.log` 1줄) · 확증 3트리 `access.log` rep 당 **+1줄**(24/24/23 → **25/25/24** · 그 외 387파일 바이트 불변) → 확증 3트리 stat 지문 `5440aefc…` → **`6ed86c86830b664916c80c13fc2b0f355528c963df5b66e9053184316e51a8b9`** · 안정성 `b4b493d2…`·기존 25트리 `8cf3d207…` **불변** · SAP 1.2·명세 3종 **0바이트** · 개봉 **0** · `unblinding_performed` **false** · 플래그 ①②③ **3/3 true**.

   - **⑤ 원본 무수정**: F4 권한 체인 13 + F5 재사용 12 = 25/25 · AT 7 · AU 6 · AV 3 · SAP manifest `d08dcedf2a22e1c8` + `consensus.py`·`metrics.py`·`rqint.py` sha 불변. 입력 **OOF 63 · checkpoint 3 · partial 315 = 381건 sha 전건 일치**(기대 sha 정본 = 공개 `manifest_t4_post_confirmatory.json` `a59ab54afd515085…`) · `master_X` `788c8a64d19e8c3c` · `master_Y` `bd23584342de6482`. RF consensus(`v3_consensus_rep123`) **열기·해싱 0**(access.log 19줄 불변).

   - **⑥ 관련 해시**: 하네스 `v3_Multimodal/src/confirmatory_gin_consensus.py` **`32c3444452fd3a2548e308e2d04cc808075192ccef6d4519bf73bb144bf86b01`**(64,684 B) · selftest `experiments/runs/v3_gin_consensus_harness_selftest/selftest_consensus.json` **`ff20824ba31f61ed10066b9a3e8f26c82d3815f08f14b52968d28a82f567c544`**(5,431 B) · 공개 `experiments/runs/v3_gin_confirm_consensus_rep123/manifest_public.json` **`768f7267bf8c033ccb3830838e7501d18605fb19d2630061723bafebd7a259dd`**(5,350 B) · 봉인 22파일 sha16 = `consensus_C-CAP_seed42.npz` `b6e931b142e3704a` · `consensus_C-CAP_seed1.npz` `73100d2080ccc1fa` · `consensus_C-CAP_seed2.npz` `63bc25437e236e9c` · `consensus_M0_seed42.npz` `3662479007463e3e` · `consensus_M0_seed1.npz` `3c1c49375d8f6836` · `consensus_M0_seed2.npz` `313b25538a90475d` · `consensus_M1_seed42.npz` `9b8d68db0b4c990a` · `consensus_M1_seed1.npz` `889989d30520be63` · `consensus_M1_seed2.npz` `12152f778b86729e` · `consensus_M1b_seed42.npz` `9b5f16ac16c1d857` · `consensus_M1b_seed1.npz` `1bdf935198258739` · `consensus_M1b_seed2.npz` `32a5f1bc701e2f10` · `consensus_M2b_seed42.npz` `b36ff282b410295b` · `consensus_M2b_seed1.npz` `9ae11e2d072da87b` · `consensus_M2b_seed2.npz` `03a0db458b4d4f48` · `consensus_P-FAM_seed42.npz` `d2a1a11fce7dcaed` · `consensus_P-FAM_seed1.npz` `2c560e89f818e93d` · `consensus_P-FAM_seed2.npz` `c879426226ecc567` · `consensus_P-ID_seed42.npz` `08b8d61a11dbd16c` · `consensus_P-ID_seed1.npz` `fcb0e291648a134d` · `consensus_P-ID_seed2.npz` `702979be5068ba3b` · `metrics_full.json` `f08ba2307146160f` · 신규 consensus 트리 stat 지문 `66cf4290bf33c9880dfe0e91f440923081cd2a2a6fd3af76346b69e3905f56bf`(23줄).

   - **⑦ 범위 밖**: D11 λ·ρ(114) · Holm ⑧ 본런 + D9 BCa + D12(115) · 안정성 15셀 SS(116) · 개봉 승인·시점(별건) · 지도교수 서명·OSF 업데이트 · 장시간 본런 생존성 대책(E2 — 115 전 결정). `ledger.first_look_register` 는 **무수정**(블록 H~Z 선례 — 구조화 대장 4행 유지, 조회행은 `first_look_log.json`·`docs/45` §5 에). ★ 긴장 1줄: ledger `status_corrected_20260807` 은 「구조화 대장이 뒤처진 것은 설계 의도가 아니다」라고 기록했다 — 동기화는 개봉 준비 블록에서 일괄한다.

   - **⑧ 사전지정 무결성**: 명세 `fb1de5da…` 동결 시각(블록 AV · 파일 mtime 2026-09-23 12:16:41 KST) < 본 산출 2026-09-27 23:30:39 KST — 셀 정의·집계·무효 규칙이 산출 **이전에** 고정돼 있었다. 결과 의존 분기 **0**(재실행 0 · 셀 선택·제외 0 · 무효 규칙 발동 0). 러너는 봉인 «값»을 본 적이 없다 — 기계 판독 경로는 하네스 `run` stage 내부뿐이고, stdout·`run.log`·`manifest_public.json` 에는 개수·시각·sha 만 있다(AP·Δ·`n_eval`·`n_excluded_undefined`·`best_ep`·`best_v` 0).

67. **ChatGPT 8차 리뷰 반영 — RQ-int 주 p 식 amendment(U2) · 동결 자체검사 T12 적용 범위 정정 · H1 보충 · 115 생존성 결정(U1) (블록 AX — `docs/114` · 확증 계산 0회 시점 기록)**:

   - **① 원래 기록**: 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da…`) `S4_holm8_main_run` 에 p 식 문면이 **두 개** 병존한다 — 구현식 `p_formula_implementation_verbatim` 축자 「p = (1.0 + count) / (n_permutation_values + 1.0), count = sum(abs(perm) >= abs(T_obs) - _EPS)」 · 검토자식 `p_formula_reviewer_verbatim` 축자 「p=(1+∑_(b=1)^B I(|T_b |≥|T_"obs" |))/(B+1)」. `B` = 동전 벡터 수 100,000(`rqint_procedure_decisions_v1.json` closure `b_monte_carlo_sample_size_and_definition` 축자 「B = 동전 벡터 수 (n_coin_vectors)」 · 「pair_complement = true 이므로 참조분포 = 2 × 동전 수.」 · 사용자 확정 2026-08-24). D14 이중보고 축자 「판1: 구현 p」 · 「판2: 해당 슬롯 p=1.0 폴백판」. 동결 자체검사 `rqint_downstream.py` `selftest_T12_hygiene` 은 봉인 계수 **29/727/707/20** 과 확증 3트리 지문 **`5440aefc…`** 를 assert 한다. 항목 66 ② 의 H1 서술 = 「S1 에 없는 무효 사유 2종 … 셀 전체 무효가 보수적이다(S1 무효 규칙의 **확장**으로 명시)」.

   - **② 보충·확정**: **(U2)** Holm ⑧ 의 주 p(Holm 입력) = **`(1 + c)/(B + 1)`**, c = `#{b ∈ [0, B) : |perm[b]| ≥ |T_obs| − eps}` — `sap.rqint.rqint_test(..., return_perm=True)` 반환 `perm` 의 **앞쪽 B 개**(동전 벡터 값 · 여집합 제외, 정본) · 항등식 경로(`complement_identity_used` true)에서는 `count == 2c` 를 assert · 폴백 경로에서도 정본 정의를 쓰고 count/2 를 쓰지 않는다 · eps = `sap.rqint._EPS`(구현 규약 · 검토자 축자 식에는 eps 가 없음을 명기) · 구현식 p 는 **봉인 병기**(보조) · 몬테카를로 SE `√(p̂(1−p̂)/B)`, B=100,000 **불변**. 근거: 쌍 |T| 동일 → count = 2c → 구현식 = (1+2c)/(2B+1) 은 검토자식보다 (B−c)/((2B+1)(B+1)) ≥ 0 만큼 작다(상한 약 5.0×10⁻⁶ · 반보수) · 유효 무작위화 p 는 (1+c)/(B+1) · 보정 전 α=0.05 기각 경계는 B=2,000·100,000 모두 동일 → R1 PASS·D19 검정력 0.735 승계. closure evidence 「SE 대비」의 「참조분포 2배 → SE 는 1/√2 배. (가)는 정밀도 √2 배」는 **대체된 해석**(B 값·정의 결정은 불변). **(U2-a)** D14 이중보고의 「판1」은 amendment 후 **주 p(검토자형)** 를 가리킨다 · 판2 불변. 사이드카 = `v3_Multimodal/config/rqint_downstream_spec_v1_amendment1.json`(동결 2026-09-28T09:12:46+09:00). **(T12 적용 범위 정정)** T12 의 계수·지문 assert 는 **블록 AV 시점 스냅샷에만 적용되는 검증 계약**이다 — 블록 AW 봉인 추가(30/750/729/21 · 지문 `6ed86c86…`)로 **구조적으로 불통과**하며, 모듈 순수함수(`leverage_profile` 등)의 동작은 계수와 무관하다. 스냅샷은 재현 불가(봉인 상태 비가역)이므로 현재 상태 위생은 각 블록 하네스가 새 상수로 수행한다. **추론법 변경 아님**. 이후 `rqint_downstream.py` 는 함수 import 만 하고 `--stage selftest`·`main()`·`run_selftest()` 는 호출하지 않는다. **(H1 보충)** 항목 66 ② 의 H1 은 「보수적이므로 변경 아님」이 아니라 **「산출물 유효성 조건의 추가 — 절차 변경 · 보수 방향 · 값·부호 미열람 상태에서 2026-09-23 결정」** 으로 읽는다(항목 66 무수정 · 본 항목이 보충). **(U1)** 115 생존성 = **감시·자동 재개**(세부 규칙은 115 지시서). **(구현 무결성 검사 보충)** 블록 AX 하네스 R5 무효 사유 중 S2 `invalidation_rules`(입력 sha · 행 순서 · 비유한 값) 밖의 4종 — **도출↔축자 불일치 · 113 교차 비트 불일치 · G ≠ 732 · 행렬 수 ≠ 8** — 은 값과 방향에 무관한 **구현 일관성 검사**이며 S2 의 변경이 아니라 보충으로 **확증 판독 전에** 사전 기록한다.

   - **③ 시각**: ChatGPT 8차 회신 수령 → 트리아지 `docs/113c` → 사용자 결정 U1~U3·U2-a **2026-09-28 00:3x KST**(`docs/113c` §6 · `docs/114` §0) → 사이드카 동결 **2026-09-28T09:12:46+09:00** → 본 항목 기록 **2026-09-28 09:13:52 KST**. 이 시점 블록 AX 의 확증 입력 판독 **0회**.

   - **④ 영향**: SAP 1.2(`experiments/sap/manifest.json` `d08dcedf2a22e1c8`)·명세 JSON(`fb1de5da…`)·`sap/rqint.py`(`eb842bc98140e9c5`) **0바이트** · Holm ⑧ 의 주 p 식(과 D14 판1 지시 대상)만 대체 · 결과 미열람 — 봉인 계수 **30/750/729/21** · 지문 착수값 확증 `6ed86c86…` · 안정성 `b4b493d2…` · 기존 25트리 `8cf3d207…` · GIN consensus `66cf4290…` · Holm ⑧ p **미계산** · `unblinding_performed` **false**.

   - **⑤ 원본 무수정**: 명세 JSON · `sap/rqint.py` · `rqint_procedure_decisions_v1.json`(`16776f21df6ae29b`) · 항목 66 · `rqint_downstream.py`(`3e92a4de…`) 전부 무수정. amendment 는 **신규 사이드카 파일**로만.

   - **⑥ 관련 해시 (S8 amendment 의무 형식)**: `hash_before` = 명세 **`fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf`** · `hash_after` = {명세 **`fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf`**(0바이트 불변) + 사이드카 `v3_Multimodal/config/rqint_downstream_spec_v1_amendment1.json` **`63c29d6b6a9e22951f2e2891b54f4251d5e4f679fc1d3b3f110cfdf510aab05c`**(5,299 B)} · 8차 리뷰 문서 `docs/113b_chatgpt_review8_briefing.md` `8ec15269948b3225b2444612f47c3efd8fb0b411418d9828c1143f2f7c09aeca` · `docs/113c_chatgpt_review8_triage.md` `cd1506da7974feb5d7dd60b61c514f54af5612b413852d058aacca68be28a906` · `docs/113d_rqint_contract_table_blank.md` `09c96bf58b24e90cda31fbb186db5e13af56ab61d219632fd6e3ee906681608f`.

   - **⑦ 범위 밖**: 115 운영 규칙 상세(감시·자동 재개 규칙 · 사람 계약표 `docs/113d` 대조 — U3) · 개봉 준비 감사 · 외부 검토자에게 U2 사후 통지 · 개봉 승인(별건).

   - **⑧ 사전지정 무결성**: 본 항목과 사이드카는 **블록 AX `run` 의 R2 판독 기록(확증 입력 판독 직전 access.log 기입)보다 먼저** 기록됐다 — 사이드카 2026-09-28T09:12:46+09:00 · 본 항목 2026-09-28 09:13:52 KST < R2 시각(항목 68 ⑧ 에서 대조). U2 는 Holm ⑧ 의 어떤 확증 수치(T_obs·perm·p)도 계산되지 않은 상태에서 결정됐다.

68. **D11 레버리지 진단 λ·ρ 봉인 산출 (블록 AX — `docs/114` · 게이트 아님 · p 미계산 · 부호 미산출)**:

   - **① 원래 기록**: 블록 AV 동결 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da…`) **`S2_d11_leverage`** 가 본 블록(114)의 실행 대상을 사전지정했다 — `e_g` 축자 「d_(F,g)=1/2 [Δ_F (0)-Δ_F (1_g )],  e_g=d_("RF",g)-d_("GIN",g)」 · 도출식 `e_g = (T_obs − T(z^{(g)}))/2`(동치) · `λ_k`(k ∈ {1, 2, 10}, T_k = |e_g| 상위 k 군) · `ρ`(분자 절댓값) · 입력 consensus **8행렬** + master_Y + scaffold 군 **732** · 봉인 `leverage_diagnostics.json` · 공개 = 완료 불리언·개수·해시·`wall_seconds` · 「게이트 아님, 보고·주석용」 · 무효 = 무결성 사유만. 본 블록은 S2 를 **새로 정하지 않고 그대로 구현**했다(계산 = `rqint_downstream.leverage_profile`·`leverage_profile_verbatim`·`lambda_k`·`rho` import 호출 · 재구현 0 · 모듈 selftest·main 호출 0).

   - **② 보충·해석**: (a) 항목 67 ② 에 사전 기록한 **구현 무결성 검사 보충 4종**(도출↔축자 불일치 · 113 교차 비트 불일치 · G ≠ 732 · 행렬 수 ≠ 8)을 S2 무효 3종과 함께 R5 에 두었다 — 발동 **0**. (b) λ 단조 assert `0 ≤ λ_1 ≤ λ_2 ≤ λ_10 ≤ 1` 은 부동소수 합산 순서 차에 의한 1ulp 급 위반으로 무효가 나지 않도록 **허용오차 1e-12** 로 구현했다(값·방향 무관 · 판정 결과 true). (c) 공개 경계는 S7(「완료 여부 불리언만」)보다 구체적인 **S2 `public_allowed`**(불리언·개수·해시·`wall_seconds`)를 따랐다 · 공개 키 금지어 검사에서 `n_` 접두 개수 키(`n_lambda_k` 등)는 값 정보가 없는 중립 메타데이터로 면제했다. (d) RF consensus 원 dtype 은 가정 없이 로드 후 기록만 하고 float64 로 변환해 사용했다(봉인 JSON `rf_consensus_dtype_original`). (e) `y = master_Y[PT 370열].values.astype(int)` — 블록 AW 하네스와 축자 동일.

   - **③ 시각**: 사이드카 동결 2026-09-28T09:12:46+09:00 → 항목 67 기록 2026-09-28 09:13:52 KST → 하네스 신설 → 합성 selftest L1~L12 **전건 PASS · skip 0**(첫 시도) → 하네스·selftest 동결 **2026-09-28 09:22:13 KST** → load1 < 1.7 × 3회(10초 간격) 대기 → `--stage run` R0 **2026-09-28 09:27:52 KST** · **R2 판독 기록 2026-09-28 09:27:53 KST** · R6 봉인 2026-09-28 09:55:57 KST · 완료 **2026-09-28 09:55:57 KST** · `wall_seconds` **1685.389** · **run 1회**(재실행 0).

   - **④ 영향**: 봉인 **30/750/729/21 → 31/752/730/22**(신규 트리 `v3_rqint_leverage_d11/_sealed/` 1개 · 파일 2 = `leverage_diagnostics.json` + `access.log` 1줄) · RF consensus `v3_consensus_rep123/_sealed/access.log` **19 → 20줄** · GIN consensus `v3_gin_confirm_consensus_rep123/_sealed/access.log` **1 → 2줄**(그 외 파일 바이트 불변) → 기존 25트리 지문 `8cf3d207…` → **`6fe853b31a987660593171acb660c4c5a97b5b6b952d96f39ff05e9e781fd9b8`** · GIN consensus 트리 지문 `66cf4290…` → **`dac246845ed2fbc6b29518c816a39c029478ff14b1550b9de6475d56f9df9ebf`** · 확증 GIN 3트리 `6ed86c86…`·안정성 `b4b493d2…` **불변(무접촉)** · SAP 1.2·명세 JSON·사이드카 **0바이트** · p **미계산** · 부호 **미산출** · 개봉 **0** · `unblinding_performed` **false** · 플래그 ①②③ **3/3 true**.

   - **⑤ 원본 무수정**: F4 25 · AT 7 · AU 6 · AV 3 · AW 4 · SAP manifest `d08dcedf2a22e1c8` + `consensus.py`·`metrics.py`·`rqint.py`·`decision.py`·`redaction.py` · `confirmatory_oof_rep1.py`·`ladder_confirmatory.py`·`compute_lock.py` sha 불변. 입력 **8행렬 + metrics_full sha 전건 일치**(정본 = GIN consensus `manifest_public.json` `768f7267…` · RF = `first_look_log.json` 인덱스 6) · cid 순서 · 유한성 · 도출↔축자 · 113 교차 비트 일치 **전부 true**.

   - **⑥ 관련 해시**: 하네스 `v3_Multimodal/src/rqint_leverage_d11.py` **`4f2537ec228c03a9cf9f42545edbd63c6f73783e931bdbdc0780238b3e36e557`**(61,177 B) · selftest `experiments/runs/v3_rqint_leverage_harness_selftest/selftest_leverage.json` **`6baae1e0116feb86044661f4c7a7c71778b1f6a03c0fb6f3a4df7e7eed9d50fb`**(6,197 B) · 공개 `experiments/runs/v3_rqint_leverage_d11/manifest_public.json` **`d799e7e89a599704b699b76cbac1237f3c7297aaade07c748db69179ea5ab965`**(1,664 B) · 봉인 `experiments/runs/v3_rqint_leverage_d11/_sealed/leverage_diagnostics.json` **`0832ef65aa59c16973f5776c9dbcd917cb9e0b4b76202a64e271f357fb5206ac`**(165,593 B) · 사이드카 `v3_Multimodal/config/rqint_downstream_spec_v1_amendment1.json` `63c29d6b6a9e22951f2e2891b54f4251d5e4f679fc1d3b3f110cfdf510aab05c` · 신규 트리 stat 지문 `b19c3e9c369a8f6bb236d324b440024e07adeb67bb718bd30bd52f72fcc3fd4f`(2줄).

   - **⑦ 범위 밖**: Holm ⑧ 본런(U2 주 p 적용) + D9 BCa + D12(115 — 사람 계약표 `docs/113d` 대조 후 등록 · U3) · 안정성 15셀 SS(116) · 개봉 준비 감사 · 개봉 승인(별건) · 외부 검토자 U2 사후 통지. λ·ρ 는 어떤 판정·집계·모델선택에도 쓰지 않는다(S2 `no_result_dependent_branching`).

   - **⑧ 사전지정 무결성**: **사이드카 2026-09-28T09:12:46+09:00 · 항목 67 2026-09-28 09:13:52 KST < 본 블록 R2 판독 기록 2026-09-28 09:27:53 KST < 본 항목 기록 2026-09-28 09:56:23 KST** — p 식 amendment(U2)와 구현 무결성 검사 보충이 어떤 확증 입력 판독보다도 먼저 기록됐다. 명세 S2 동결(블록 AV) < 산출. 결과 의존 분기 **0**(재실행 0 · 무효 발동 0). 러너는 봉인 «값»을 본 적이 없다 — 기계 판독 경로는 하네스 `run` stage 내부뿐이고, stdout·`run.log`·`manifest_public.json` 에는 개수·시각·sha·불리언만 있다(e_g·λ·ρ·T_obs·Δ 0).

69. **Holm ⑧ 본런 착수 전 결정 — 확증 동전 시드 공백 보충(V1) · Δ_GIN BCa 복합 정의(V2) · 115/115b 분할(V3) · U3 이행 방식 · 계약표 대조 반영 (블록 AY — `docs/115` · 확증 계산 0회 시점 기록)**:

   - **① 원래 기록**: 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da…`) `S4_holm8_main_run.rng` 축자 = `generator` 「np.random.default_rng(seed)」 · `seed_fixed_in_run_config` **true** · `repeat_index_determinism` 「반복 인덱스는 결정적이어야 한다(재개 시 동일 순서 재현)」. `docs/100_sap_1_2_amendment.md` L73 축자 「The test statistic, exchangeability unit, resampling scheme, B, random seeds, and the GIN seed set and aggregation order were fixed without reference to GIN outputs, sealed confirmatory quantities, or fold-level metrics.」 — 그러나 **확증 RQ-int 동전 시드의 «값»은 어느 동결 파일에도 없다**(cowork 실측: `sap_1_2_hash_registry.json` category_4 7항목 · `rqint_procedure_decisions_v1.json` closures 3건 · 명세 S4 — 값 0건. 존재하는 값은 합성 드라이런용 `b_100k_prespec.json` `coin_seed` 1760260813 · `b_dryrun_prespec.json` 뿐). 명세 S5 `operator` = `sap.bootstrap.paired_scaffold_bootstrap` 은 **행렬 1쌍**(`consensus_M1b`, `consensus_M2b`)만 받는 함수라 Δ_GIN(시드 3개 Δ 의 평균)의 구간을 직접 내지 못한다. 명세 S3 `executed_in_block` **115** · `permutation_scale.B` **100,000**(주 분석과 동일).

   - **② 보충·확정**: **(V1)** 확증 동전 시드 = `coin_seed = int(sha256(label.encode("ascii")).hexdigest(), 16) mod 2**32`, label = `"DTI_ADR_Prediction v3 RQ-int Holm8 confirmatory coin seed"`(57자 · ASCII) · **1회만 계산**(대체 문자열·인코딩·법 변형 평가 0) → **2967772708** · 감사 시드(`rqint_test` 규약 seed + 1_000_003) **2968772711** — 러너 재계산이 cowork 사전값과 일치 · 충돌 검사(분할 42·201·202·203 · 학습 42·1·2·3·4 · bootstrap 6001 · null 1000~1002·11000~11002·9000001~ · 드라이런 860260813·1760260813 · 캘리브레이션 동전 ≈ 9.2e8 · 드라이런 동전 ≈ 1.74e9~1.76e9 · 각 +1,000,003) 교집합 **0** · 115b(D12)도 같은 coin_seed. **(V2)** Δ_GIN BCa = **복합 부트스트랩** — RF 는 동결 함수를 S5 `call_convention`(`scaffold_cluster` · 0.05 · B 10,000 · seed 6001 · `eligible_pt=np.arange(370)`) 그대로 호출 · GIN 은 같은 난수 규약(`default_rng(6001)` · 매 b `rng.choice(np.arange(G), size=G, replace=True, p=None)`)의 같은 cluster 표본을 3 시드에 공통 적용 → `sap.bootstrap._delta_on_rows` 로 시드별 Δ_s → `np.mean([Δ_1, Δ_2, Δ_3])`(s 순서 1·2·3) · jackknife = scaffold delete-one 에서 같은 평균 · 구간 = `sap.bootstrap._bca_ci` · 실패 시 `not_estimable`(percentile 대체 금지) · RF·GIN 은 같은 seed 6001 → 같은 군 표본 열을 공유 · GIN percentile 은 민감도로 봉인 · 판정 미사용·항상 병기 · **S = 1 에서 동결 함수와 비트 일치**를 합성 selftest(Q9)로 증명. **(V3)** 115 = S4 + S5 · 115b = S3(D12) — B = 100,000 고정 · 총 ≈ 63 h · 주분석 검증 후 민감도. **(V4 · 해석)** Holm 조정은 7슬롯 p 가 모두 있어야 하므로 개봉·판정 블록에서 한다 — 본 블록은 ⑧ 슬롯 주 p·보조 p 와 D14 판2 폴백 조건 기록까지. **(U3 이행 방식)** ⑧ 계약표는 사람이 아니라 **타 계열 모델(OpenAI ChatGPT)이 1차 출처 4종**(`docs/30` · `docs/55b` · `docs/100` · 검토자 회신 docx)**만으로 작성**했고, 사용자가 발주·전달했다(**사람 작성 아님**) · cowork 대조 `docs/113e` = 등록 차단 불일치 **0**. **(`docs/113e` 반영 2건)** (i) **B 수치의 기록 연쇄** 축자 = 「`docs/30` §8 10,000 = ②~⑦ sign-flip 용 → `docs/55b` §5 RQ-int 제안 10,000 → 검토자 §9.2 권고 100,000(24 h 초과 시 50,000) → 블록 AJ 합성 실주행 19.4887 h ≤ 24 h(하향 미발동) → `rqint_procedure_decisions_v1.json` closure `b_monte_carlo_sample_size_and_definition` 100,000(사용자 2026-08-24 · R2 동결). SAP 1.2 개정문(`docs/100`)에는 수치가 없다(수치 정본 = closure).」 (ii) **AP=0 대입 금지 규칙의 출처** = `gin_seed_freeze.json` `macro_ap_rule` · `docs/64` §3-1(1차 출처 4종에는 없음 — `docs/113e` #8). 사이드카 = `v3_Multimodal/config/rqint_downstream_spec_v1_amendment2.json`(동결 2026-09-28T11:21:41+09:00).

   - **③ 시각**: 사용자 결정 V1~V3 **2026-09-28**(`docs/115` §0) → `docs/113e` 작성 2026-09-28 10:5x KST → 사이드카 2호 동결 **2026-09-28T11:21:41+09:00** → 본 항목 기록 **2026-09-28 11:22:31 KST**. 이 시점 블록 AY 의 확증 입력 판독 **0회** · 하네스 미작성.

   - **④ 영향**: 명세 JSON(`fb1de5da…`) · 사이드카 1호(`63c29d6b…`) · `sap/*.py`(`rqint.py` `eb842bc98140e9c5` · `bootstrap.py` `05437c516e606a05`) · SAP 1.2 manifest(`d08dcedf2a22e1c8`) **0바이트** · 동전 시드 «값»과 GIN 복합 BCa «정의»만 보충 · 결과 미열람 — 봉인 계수 **31/752/730/22** · 지문 착수값 기존 25트리 `6fe853b3…` · 확증 `6ed86c86…` · 안정성 `b4b493d2…` · GIN consensus `dac24684…` · leverage `b19c3e9c…` · ⑧ p **미계산** · BCa **미계산** · `unblinding_performed` **false**.

   - **⑤ 원본 무수정**: 명세 JSON · 사이드카 1호 · `sap/rqint.py` · `sap/bootstrap.py` · `rqint_procedure_decisions_v1.json`(`16776f21df6ae29b`) · 항목 67·68 · `docs/113e` 전부 무수정. 결정은 **신규 사이드카 2호 파일**로만.

   - **⑥ 관련 해시 (S8 amendment 의무 형식)**: `hash_before` = {명세 **`fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf`** + 사이드카 1호 **`63c29d6b6a9e22951f2e2891b54f4251d5e4f679fc1d3b3f110cfdf510aab05c`**} · `hash_after` = {명세(0바이트 불변) + 사이드카 1호(0바이트 불변) + 사이드카 2호 `v3_Multimodal/config/rqint_downstream_spec_v1_amendment2.json` **`c8e1e2569e7f62fe14a49bdd5581baf3d2d9da9fb411e15099cd85a01bf1a3d8`**(8,051 B)} · `docs/113e_contract_table_reconciliation.md` `3aa1ab58fd9b22150486576ee307284d230468baf1c5365ca0b3a611885faf2d`(10,715 B) · 참조 `v3_Multimodal/config/b_100k_prespec.json` `e7406c23b8d61b0c4d04638395f4c7803e1e0dc32501baa8dae5047c4d169625`(7,916 B).

   - **⑦ 범위 밖**: 115b D12 민감도 2종(S3) · 116 안정성 15셀 SS · Holm 7슬롯 조정·판정(개봉 블록 — 명세 S4 `adjudication`·`holm_family`) · D17 「실패 시 슬롯 p = 1.0」 적용(개봉·판정 블록) · 개봉 준비 감사(8차 A-3) · 개봉 승인 · 외부 검토자 U2·V1·V2 사후 통지.

   - **⑧ 사전지정 무결성**: 본 항목과 사이드카 2호는 **블록 AY 본런의 첫 R2 판독 기록(확증 입력 판독 직전 access.log 기입)보다 먼저** 기록됐다 — 사이드카 2026-09-28T11:21:41+09:00 · 본 항목 2026-09-28 11:22:31 KST < 본런 첫 R2 시각(항목 70 ⑧ 에서 대조). V1·V2·V3 은 Holm ⑧ 의 어떤 확증 수치(T_obs 재계산·동전 T*·p·BCa)도 계산되지 않은 상태에서 결정됐다.

70. **★ Holm ⑧ RQ-int 본런(B = 100,000) + D9 BCa 봉인 완주 — launch 2회 · 체크포인트 재개 1회 · 폴백 0 · 데이터 손실 0 (블록 AY — `docs/115` Phase B · Holm 조정·판정 0 · 부호 미산출 · 개봉 0)**:

   - **① 원래 기록**: 블록 AV 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da…`) **S4_holm8_main_run · S5_d9_delta_bca** + 사이드카 1호(`63c29d6b…` — 주 p `(1 + c)/(B + 1)` · 보조 p `(1 + count)/(2B + 1)` 봉인 병기) + 사이드카 2호(`c8e1e256…` — V1 동전 시드 **2967772708** · 감사 시드 2968772711 · V2 GIN 복합 BCa · V3 115/115b 분할)가 본런을 사전지정했다 — 동전 벡터 B **100,000** · 참조분포 200,000(`pair_complement`) · 감사 draw 1,000 · 양측 · D4 동전 공유 · D5 consensus 8행렬 루프 밖 1회 · 체크포인트 1,000 동전 · 재개가 난수열을 바꾸지 않음 · 무효 = 값 무관 무결성 사유만 · D9 = RF 동결 함수 `sap.bootstrap.paired_scaffold_bootstrap`(scaffold_cluster · 0.05 · B 10,000 · seed 6001) + GIN 복합(V2). **B 수치의 기록 연쇄(`docs/113e` #11 축자)** = 「`docs/30` §8 10,000 = ②~⑦ sign-flip 용 → `docs/55b` §5 RQ-int 제안 10,000 → 검토자 §9.2 권고 100,000(24 h 초과 시 50,000) → 블록 AJ 합성 실주행 19.4887 h ≤ 24 h(하향 미발동) → `rqint_procedure_decisions_v1.json` closure `b_monte_carlo_sample_size_and_definition` 100,000(사용자 2026-08-24 · R2 동결). SAP 1.2 개정문(`docs/100`)에는 수치가 없다(수치 정본 = closure).」

   - **② 실행·판단**: 하네스 `rqint_holm8_run.py`(`e1c4cf95…`)·감시 래퍼 `rqint_holm8_watchdog.py`(`fc84f5bd…`)는 Phase A 동결본 그대로 실행됐다(**수정 0** · 공개 manifest 의 `harness_sha256`·`watchdog_sha256`·`selftest_sha256` == 동결값). 사용자가 macOS 터미널에서 감시 래퍼를 띄웠다(AY-8). **launch 이력(R2 도달 = launch)**: (1) launch 1 = R0′ first **2026-09-28 20:30:53 KST** · R2 20:30:54 · R4a T_obs 비트 일치 · 동전 0 → **90,000**(체크포인트 90회 · 마지막 2026-09-29 14:41:30 KST · 경과 65,436.1 s) → **2026-09-29 14:42:01 KST 감시 래퍼가 SIGTERM 을 수신해 자식에 전달**(수신 경위는 이벤트 로그에 기록 없음 · 하네스 정상 종료 · 락 해제 기록 존재 · `hard_stop` 0). (2) launch 2 = reentry **2026-09-30 22:40:13 KST**(`_tmp` 정리 0) · R2 22:40:14 · R4a T_obs 비트 일치 · 체크포인트 **90,000 에서 재개**(내부 무결성 + `rng.random(G)` × 90,000 소진 후 난수 state 일치 — `checkpoint_integrity_ok` true) → 100,000 (2026-10-01 00:40:41 KST) → R4c 집계(봉인) → R4d BCa RF 00:40:41~01:12:29 · GIN 복합 01:12:29~02:50:33 → R6 봉인 02:50:33 → R7 공개 02:50:35 · 감시 래퍼 `completed`(exit 0) 02:51:08. 마지막 체크포인트 이후 진행분(≤ 31 s)은 폐기되고 같은 난수열로 재계산됐다(결정적). **폴백 0**(`phase` 전 구간 `coins` · `k_done` 0 — 감사 실패 시에만 발동하는 값 무관 분기). **전원**: 체크포인트 100/100 AC · `n_power_lost` 0 · 2026-09-30 13:08:18 KST 기동분은 배터리여서 `power_wait` 20,835.1 s(재시작 미산입 · R2 미도달 → 입력 access.log 불변). **운영 사건(값 무관 · 기록)**: (a) 감시 래퍼 **동시 기동 2회**(2026-09-28 20:26:14/20:26:28 · 2026-09-30 13:08:18/21:47:29) — 두 경우 모두 자식 기동 전 SIGTERM 으로 함께 정지했고 **자식 중복 기동 0**(watchdog `launch` 2 == heartbeat `r2_started` 2 == `r2_complete` 2 == manifest `n_launches` 2) · `ComputeLock` 이 2차 방어. (b) `stall_suspect` 1회(2026-10-01 01:11:05 KST · RF BCa 구간 — 동결 함수에 진행 훅이 없어 약 32분 heartbeat 공백 · Phase A 리포트 §5-11 예고대로 · 기록만). (c) `compute_lock` stale 인수 **0**(`.compute_lock.stale.jsonl` 3줄 불변). **(V4 · 해석 승계)** Holm 조정은 7슬롯 p 가 모두 있어야 하므로 개봉·판정 블록에서 한다 — 본 블록은 ⑧ 슬롯 주 p·보조 p 와 D14 판2 폴백 조건 기록까지(봉인). D17(「실패 시 슬롯 p = 1.0」)은 개봉·판정 블록이 적용하며 본 블록은 조건 문장만 봉인 JSON 에 기록했다. 재실행·재시드·B 축소·동전 폐기 **0**.

   - **③ 시각**: 사이드카 2호 2026-09-28T11:21:41+09:00 → 항목 69 2026-09-28 11:22:31 KST → 하네스·감시 래퍼·selftest 동결 2026-09-28 12:02 KST → 첫 R2 **2026-09-28 20:30:54 KST** → launch 2 R2 2026-09-30 22:40:14 KST → 봉인 완료 **2026-10-01 02:50:35 KST** → 본 항목 기록 2026-10-01 22:12:18 KST. 계산 경과 = launch 1 65,436.1 s + launch 2 15,021.7 s(`wall_seconds_last_launch`) = **80,457.8 s ≈ 22.35 h**(F8 예측 ≈ 21.6 h 대비 +3.5% · 동전 ≈ 0.727 s/개 · AJ 0.6946 s/개 대비 +4.7%).

   - **④ 영향**: 봉인 **31/752/730/22 → 32/757/734/23**(신규 트리 `experiments/runs/v3_rqint_holm8/_sealed/` 1개 · 5파일 = `access.log`(2줄 = 1 + 재개 1) · `checkpoint.npz` · `t_star.npy` · `holm8_result.json` · `d9_bca_result.json`) · 입력 access.log = RF consensus **20 → 22줄** · GIN consensus **2 → 4줄** · leverage **1 → 3줄**(= 착수 + launch 2 · 그 외 파일 바이트 불변 — access.log 제외 stat 지문 기존 25트리 `7b617e1c…` · GIN consensus `d061293d…` · leverage `ed9b8605…` 불변 · 기존 25트리 RF 외 access.log 15개 지문 `440226aa…` 불변) → 지문 갱신: 기존 25트리 `6fe853b3…` → **`a61e45589227e062b632be2801cf0605845054445b63905ea27d393c008cad9d`** · GIN consensus `dac24684…` → **`c2715eecaf18f995e07177a211df2db2c6010bd5962eab42e0783e76b6cbf10f`** · leverage `b19c3e9c…` → **`717c7162e774cd0a80c699bb5cc1db8edacb2f3a1067c39555fee4c231e9cfe9`** · 신규 트리 **`4177f61de8f3fd60a59d537b0683634a21e3dbe0e508c60da5dc4ee1ebcafc5e`** · 확증 GIN 3트리 `6ed86c86…`·안정성 `b4b493d2…` **불변(무접촉)** · 확증 access.log 25/25/24 불변. 명세·사이드카 1·2호·SAP 1.2·`sap/*.py` **0바이트** · Holm 조정 **0** · 판정 **0** · 부호 **미산출** · 개봉 **0** · `unblinding_performed` **false** ×3 · 플래그 ①②③ **3/3 true**.

   - **⑤ 원본 무수정**: 명세 · 사이드카 1·2호 · 하네스·감시 래퍼·selftest · `sap/rqint.py` `eb842bc98140e9c5` · `sap/bootstrap.py` `05437c516e606a05` · SAP manifest `d08dcedf2a22e1c8`(11모듈 등재값 11/11) · `rqint_procedure_decisions_v1.json` `16776f21df6ae29b` · `compute_lock.py` `b03a0b0012948b34` · `confirmatory_oof_rep1.py` `afb894c09fdaad6f` · AX 산출 4종 · 입력 8행렬(RF 2 · GIN 6) · `master_X`/`master_Y` sha 전부 불변. 러너 독립 검증(하네스 import 0 · stat·sha·개행 수만) **56/56 PASS**.

   - **⑥ 관련 해시**: 봉인 `checkpoint.npz` **`b298c01bc18c0473f7b4010989ecc0190659668444fc7a44bb926a1d86f7fc6d`**(808,056 B · 최종본) · `t_star.npy` **`7882a95c6648686a97a18df0283fb861fe733cca2cf77fedcd5b49b85ed3f0d4`**(800,128 B) · `holm8_result.json` **`4cf3b79b66e5a76dd3b5baae2495678e7ad00a40611f003a2579d78e3e807913`**(3,337 B) · `d9_bca_result.json` **`5eeacc66945eb8e344f8ef2fdb2fd95869d13e359161e197a246482354170abd`**(4,283 B) · 신규 `access.log` `d94dfdc355dc8500a987878c4f6d96589ea37f660b5bfde646473fd3c30d9ff6` · 공개 `experiments/runs/v3_rqint_holm8/manifest_public.json` **`e87e9d4e597c0af4e755094a2291977e10ef9a255ca26421f50dbbfc2e4b0c2a`**(2,576 B) · `run.log` `823b2b53239d25419ec94c2212297a0d018f05c67a07e6298436bcffbfa09ce5` · `heartbeat.jsonl` `b03bfdfc8c4a5132c198a64d9c8d6e7b21e8c795fe53b3bb20754d9faec3c848` · `experiments/runs/v3_holm8_watchdog/watchdog_events.jsonl` `2b7a47948372776ebe0f42ae14ea3b889551d0b6abeda988f43c500c933d7238` · 하네스 `e1c4cf956c0ddb606ddf0d4440b3b85eecab4d2cc98d66468e07d0fa2b597288` · 감시 래퍼 `fc84f5bd12e7448e5fa0285d99d7478b79934a3c882516c6518ffe0a70e848e2` · selftest `b0e019c73639c90910d74ef5d1527505744199974a8ebc0ef915d86c4aeb787a` · 사이드카 2호 `c8e1e2569e7f62fe14a49bdd5581baf3d2d9da9fb411e15099cd85a01bf1a3d8` · run_id `AY-2026-09-28T20:30:53+09:00`.

   - **⑦ 범위 밖**: 115b D12 민감도 2종(S3 · 같은 coin_seed) · 116 안정성 15셀 SS · Holm 7슬롯 조정·판정(개봉 블록 — 명세 S4 `adjudication`·`holm_family`) · D17 적용 · 개봉 준비 감사(8차 A-3) · 개봉 승인 · 외부 검토자 사후 통지. `ledger.first_look_register` **무수정**(선례 — 조회행은 `first_look_log.json`·`docs/45` §5).

   - **⑧ 사전지정 무결성**: **사이드카 2호 2026-09-28T11:21:41+09:00 · 항목 69 2026-09-28 11:22:31 KST · 하네스 동결 12:02 KST < 본런 첫 R2 2026-09-28 20:30:54 KST** — 동전 시드·GIN 복합 BCa 정의·분할이 어떤 확증 입력 판독보다도 먼저 기록됐다. 결과 의존 분기 **0** — 재개 1회는 외부 SIGTERM(값 무관)이고, 폴백 미발동·재시드·B 축소·동전 폐기 0. 러너는 봉인 «값»을 본 적이 없다 — 기계 판독 경로는 하네스 `run` stage 내부뿐이고, stdout·`run.log`·`heartbeat.jsonl`·`manifest_public.json`·`watchdog_events.jsonl` 에는 개수·시각·경과·전원·load·sha·불리언만 있다(p·T*·T_obs·Δ·CI 0 — 독립 검증 V6 누설 스캔 0).

71. **외부 검토자 2026-09-29 의견 수신(U2 해석 동의 · 반영 요구 5건 · 봉인해제 승인 아님) · 사후 통지 서신 3건 · 블록 AY Phase A 편차 12건·운영 주의 1건 보충 (블록 AZ — `docs/115b` · 기록만 · 계산 0)**:

   - **① 원래 기록**: 사후 통지 발송 = 2026-09-29 02:52:20 KST · 메시지 `<GMAIL-MSGID>` · 스레드 `<GMAIL-MSGID>` — 국문 정본 `docs/113f_reviewer_notice_u2_v1_v2_20260928.md` `c9efaeeacc1740ce71e844070490cc68dce878575c109f63d4b5c98c10ad076d`(11,728 B) · 발송 기록 `docs/113g_reviewer_notice_sent_record.md` `3fb6927e5a4c045b6aca77038069a423e47c226f2fad25d4513ed59d84e44831`(9,805 B). 블록 AY 항목 **69·70** 에는 Phase A 편차(`docs/115_rqint_holm8_mainrun_report.md` §5 항목 1~12)가 **열거되지 않았다**(러너 실측: 항목 69~70 본문에서 「편차」 0회 · 「EXIT_CRASH」·「refused_start」·「selftest 재실행」·「VECLIB」·「13/14」 각 0회 · `stall_suspect` 는 항목 70 에 운영 관측으로 1회 언급될 뿐 Phase A 편차로서의 열거는 아님). `ledger.json` correspondence 에도 위 서신이 미등재였다(`docs/113g` §4 — 블록 AY Phase B 게이트가 ledger sha 를 고정했기 때문).

   - **② 보충**: **(a) 검토자 의견 축자**(`docs/113g` §5-1 인용부 전문 · 강조 `*` 제거본 그대로 · 사람 요약으로 대체하지 않음):

     > 전달해 주신 U2·V1·V2 절차 결정 통지서를 검토했습니다. 확증 결과를 열람하기 전에 명세의 불일치와 누락 사항을 확인하고, 결정 내용과 시점을 별도로 기록하여 공유해 주셔서 감사합니다.
     > 아래 의견은 통지서에 기재된 결과 미열람 상태와 사전 기록 사실을 전제로 한 절차적 검토 의견입니다.
     >
     > 1. 주 p 식 확정(U2) 문의한 핵심 사항부터 답변드리면, B를 본래 추출한 동전 벡터 100,000개의 수로 정의하고, 해당 B개에 대해서만 초과 횟수 c를 계산하여 주 p를 p = (1+c)/(B+1)로 산출하는 해석에 동의합니다. 여집합으로 추가 생성한 통계량을 별도의 독립 추출 횟수처럼 B에 더하지 않고, 기존 구현식의 값은 보조 기록으로 보존하는 방식으로 정리해 주세요. 이는 기존 승인에서 요구한 가환성 및 무작위화 규약이 유지된다는 전제입니다. 또한 eps = 10^-12는 원 수학식에 포함된 항이 아니라 수치 비교를 위한 구현 규약임을 구분하여 명시하고, 결과에 따라 변경하지 않아야 합니다. count = 2c를 이용한 두 식의 관계 설명도 해당 항등식이 확인된 경로에 한정해 주세요.
     > 한 가지 구분할 점은, 통지서에서 설명한 보정 전 α = 0.05에서의 기각 경계 일치를 Holm 보정 후의 모든 판정까지 동일하다는 의미로 확대해서는 안 된다는 것입니다. 기존 감사 결과의 승계 범위는 확인된 조건으로 한정하고, Holm ⑧ 및 D14의 「판1」에는 이번에 확정한 주 p를 일관되게 적용해 주세요. 「판2」의 기존 폴백 규약은 그대로 유지하면 됩니다.
     >
     > 기록 및 이후 진행에 관하여
     > 이번 회신은 본런을 다시 수행하거나 봉인된 확증 수치를 열람하라는 요청은 아닙니다. 위 사항은 결과를 개봉하지 않은 상태에서 절차 문서와 점검 기록에 반영해 주시면 됩니다.
     > 또한 이 회신은 위 보충사항에 대한 의견이며, R1–R6 전체 이행 여부를 다시 검증했다는 의미나 봉인해제 승인에 해당하지는 않습니다. 봉인 상태를 유지하면서 예정된 개봉 준비 감사를 진행하고, 최종 개봉 여부와 시점은 기존 절차에 따라 양진홍 교수님의 승인을 받아 진행해 주세요.
     > 절차상의 누락과 해석 차이를 결과 열람 전에 정리해 주신 점에 감사드립니다. 남은 단계도 같은 원칙으로 마무리해 주시기 바랍니다.
     > 감사합니다.
     > <EXTERNAL-REVIEWER> 드림

     **(b) 반영 요구 대조표**(`docs/115b` §0 · `docs/113g` §5-3): R-a B = 원 동전 100,000 · c 는 그 B 개에서만 · 여집합 불가산 · 구현식 보조 보존 → 기존 사이드카 1호 `c_definition` (본 항목에 검토자 동의 출처로 인용) · **R-b** eps 는 구현 규약임을 구분 명시 · 결과에 따라 변경 금지 → 사이드카 1호 `eps_note` 는 앞 절반만 있음 → **사이드카 3호 `reviewer_20260929.r_b` 에 축자 보충**(항목 72) · R-c count = 2c 설명은 항등식 확인 경로에 한정 → 사이드카 1호 `c_definition` 인용 · D12 에도 동일 적용 · **R-d** 보정 전 α = 0.05 기각 경계 일치를 Holm 보정 후 판정으로 확대 금지 · 기존 감사 승계 범위 한정 → **문면 없음** → **사이드카 3호 `reviewer_20260929.r_d` + 개봉 준비 감사 점검 항목 추가 의무 기록**(항목 72) · R-e Holm ⑧ · D14 판1 = 주 p · 판2 폴백 유지 → 사이드카 1호 `d14_panel1_refers_to` 인용. **(c) 서신 3건**(스레드 `<GMAIL-MSGID>` · get_thread 3건 · cowork Gmail 실측 — 러너 네트워크 0): #1 2026-09-29 02:52:20 KST 발신(<EMAIL-USER> → <EMAIL-USER>) `<GMAIL-MSGID>` 「[DTI-ADR v3] RQ-int 봉인해제 이전 절차 결정 3건 사후 통지 — <EXTERNAL-REVIEWER> 박사님 전달 부탁드립니다!」 · 첨부 `RQint_Reviewer_Notice_U2V1V2_20260928.docx`(로컬 최종본 46,057 B `939630345b51b8402cb9ca2a48776cb964d8f7227b5fd490fc3098dcfae22b06` · mtime 발송 4분 전 · **발송본 바이트 동일성 미검증 — 첨부 다운로드 도구 없음**) / #2 2026-09-29 12:27:18 KST 수신(<EMAIL-USER> → <EMAIL-USER>) `<GMAIL-MSGID>` 「Re: …」 — 교수님이 검토자 의견을 본문 인용으로 전달(교수님 → 검토자 전달 시각 메일에 미명시) / #3 2026-09-29 12:34:00 KST 발신(<EMAIL-USER> → <EMAIL-USER>) `<GMAIL-MSGID>` 「Re: …」 — 반영 약속 답신. → `ledger.json` correspondence **36 → 39**(본 항목 직후 · `recorded_in_block` "AZ"). **(d) 블록 AY Phase A 편차 12건 + 운영 주의 1건**(정본 = `docs/115_rqint_holm8_mainrun_report.md` `2a143fc125c3c8b562f8a3a6f549fc424c6c5045035c2296e3f5856fae052953` §5 · 각 1줄 + 출처 줄 번호):
     - 편차 1: first 모드 「락 부재」 구현 — 살아 있는 보유자 = 종료 9 · dead-pid = `ComputeLock` stale 인수 (`docs/115_rqint_holm8_mainrun_report.md` L197-200)
     - 편차 2: reentry 신규 트리 지문 대체 규칙 — 이름 집합 ⊆ 5종 · access.log 존재 · 계수 상하한 (`docs/115_rqint_holm8_mainrun_report.md` L201)
     - 편차 3: Q10 「출력 미생성」 해석 — 결과 봉인 파일·체크포인트 미생성(`_sealed` 에는 access.log 만) (`docs/115_rqint_holm8_mainrun_report.md` L202-204)
     - 편차 4: **종료 코드 1(EXIT_CRASH) 신설** — R2 이후 비-무효 예외 → 1(감시 래퍼 재기동·산입) · 게이트·무효·무결성 = 13 (`docs/115_rqint_holm8_mainrun_report.md` L205-207)
     - 편차 5: Q2 AST 예외 2건 — 감사 수 1,000(= `CKPT_EVERY`) 리터럴 제외 · 주 p 식 문자열은 결속 assert 전용 (`docs/115_rqint_holm8_mainrun_report.md` L208-210)
     - 편차 6: 감시 래퍼 수동 재기동 거부(`refused_start`) — `hard_stop`·`restart_limit` 이후 재기동 시 (`docs/115_rqint_holm8_mainrun_report.md` L211)
     - 편차 7: D9 관측값 비트 일치를 봉인 JSON 불리언으로만 기록(무효 사유 신설 0) (`docs/115_rqint_holm8_mainrun_report.md` L212-214)
     - 편차 8: 봉인 JSON 비유한 값 → `null` + `status` 보존(`allow_nan=False` 유지) (`docs/115_rqint_holm8_mainrun_report.md` L215)
     - 편차 9: **selftest 재실행 1회** — fixture cid 리터럴 100000 → 90000 · 1차 13/14 → 2차 14/14 · 계산 경로 변경 0 (`docs/115_rqint_holm8_mainrun_report.md` L216-218)
     - 편차 10: 스레드 변수 이름 `VECLIB_MAXIMUM_THREADS`(블록 AJ 선례) (`docs/115_rqint_holm8_mainrun_report.md` L219)
     - 편차 11: `stall_suspect` 예고 — RF BCa 약 31분 heartbeat 공백 · 기록만 (`docs/115_rqint_holm8_mainrun_report.md` L220)
     - 편차 12: µs 크래시 창 — first 모드 `mkdir(out)` 과 heartbeat 첫 줄 사이 사망 시 reentry 13 정지 (`docs/115_rqint_holm8_mainrun_report.md` L221)
     - 13 (**편차 아님 · 원문상 「운영 주의」**): 착수 시 load1 7.78 — `com.apple.Virtualization.VirtualMachine` 가동 시 감시 래퍼 load 게이트가 본런 기동을 막는다 (`docs/115_rqint_holm8_mainrun_report.md` L222-225)

     **(e) 누락 원인**: cowork 지시서 `docs/115` B-2 가 항목 70 내용에 Phase A 편차를 열거하도록 지시하지 않았다(지시서 결함) · `runner_at_fault` **false**. 재발 방지 = `docs/115b` B-2 가 항목 73 에 Phase A 리포트 §5 편차 전부 열거를 명시.

   - **③ 시각**: 사후 통지 발송 2026-09-29 02:52:20 KST → 검토자 의견 수신(교수님 인용 전달) **2026-09-29 12:27:18 KST** → 반영 약속 답신 **2026-09-29 12:34:00 KST** → cowork 기록 `docs/113g` §5(2026-09-29 13:1x KST) → 블록 AY Phase B 완료(2026-10-01 22:16 KST) → 본 항목 기록 **2026-10-02 00:38:56 KST**.

   - **④ 영향**: 계산 경로·동결물 **0** — 명세(`fb1de5da…`) · 사이드카 1·2호(`63c29d6b…` · `c8e1e256…`) · `rqint_downstream.py`(`3e92a4de…`) · `sap/*.py` · SAP 1.2 manifest(`d08dcedf2a22e1c8`) 0바이트. 검토자 회신은 재실행·수치 열람 요구 0(축자 「본런을 다시 수행하거나 봉인된 확증 수치를 열람하라는 요청은 아닙니다」). 값 미열람 — 봉인 계수 **32/757/734/23** · 지문 6종 착수값 일치(기존 25트리 `a61e4558…` · 확증 GIN `6ed86c86…` · 안정성 `b4b493d2…` · GIN consensus `c2715eec…` · leverage `717c7162…` · Holm ⑧ `4177f61d…`) · `unblinding_performed` **false** · 플래그 3/3 true.

   - **⑤ 원본 무수정**: 항목 69·70 · `docs/113f`·`docs/113g` · `docs/115_rqint_holm8_mainrun_report.md` · 기존 correspondence 36항목(객체 단위) · `correspondence_subject_authority` 전부 무수정. 보충은 **신규 항목·신규 correspondence 3행**으로만.

   - **⑥ 관련 해시**: `hash_before` = {`docs/33` 516,138 B `8bfb01b1deb724cb0ee10e8427a8c374fe33d95738c658707c675d6a66ec8c46` · `ledger.json` 443,588 B `2f10a6995a9186fddaaaeac451eb81cbf0da005d0bd2925f1eaf8d829e9b8b6d`} · `hash_after` = {`ledger.json` 446,756 B `40e0fb0991efb8a8a1dd73369bf3014c624267572549298b8c7caf49505ef726`(correspondence +3 · 역복원 = 끝 3개 제거 → 443,588 B `2f10a6995a9186fd…` 일치)} · `docs/33` 의 본 항목 기록 후 sha 는 항목 72 ⑥ `hash_before` 에 기록 · 참조 `docs/113g_reviewer_notice_sent_record.md` `3fb6927e5a4c045b6aca77038069a423e47c226f2fad25d4513ed59d84e44831` · `docs/113f_reviewer_notice_u2_v1_v2_20260928.md` `c9efaeeacc1740ce71e844070490cc68dce878575c109f63d4b5c98c10ad076d` · `docs/115_rqint_holm8_mainrun_report.md` `2a143fc125c3c8b562f8a3a6f549fc424c6c5045035c2296e3f5856fae052953`(22,453 B).

   - **⑦ 범위 밖**: 검토자 R-b·R-d 의 «문면» 보충(항목 72 · 사이드카 3호 `rqint_downstream_spec_v1_amendment3.json`) · 개봉 준비 감사(별 블록 — R-d 점검 포함) · D12 계산(블록 AZ 본런) · 116 · Holm 조정·판정·개봉 · 개봉 승인(양진홍 교수님).

   - **⑧ 사전지정 무결성**: 이 항목은 **D12 확증 판독 이전**(블록 AZ 의 어떤 R2 판독 기록보다 먼저 · `experiments/runs/v3_rqint_d12*` 0)에 기록됐다. 검토자 의견은 결과 미열람 상태에서 수신됐고 계산 경로를 바꾸지 않는다.

72. **D12 민감도 2종 착수 전 결정 — 군 라벨 = 동결 구현 모듈 함수(W1′ · 정정 경위 포함) · p 식 = 주 분석과 동일(W2) · 한 트리 연속 실행(W3) · 검토자 R-b·R-d 문면 보충 (블록 AZ — `docs/115b` · D12 계산 0회 시점 기록)**:

   - **① 원래 기록**: 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da…`) **S3_d12_sensitivity** 축자 — `reviewer_verbatim` 「주 분석은 frozen 정의를 유지하되, 민감도 분석으로 (i) no-scaffold 버킷의 싱글톤 분해, (ii) 벤젠군의 사전규정된 결정적 2분할(예: 정규화 SMILES 사전순)을 병기하십시오. 폴드 배정은 변경하지 않으므로 누출 방지 성질은 그대로 유지됩니다.」 · (i) `target` 「scaffold 문자열이 **빈 문자열**인 버킷(비고리형 + 파싱 실패)」 · `rule` 「그 버킷의 각 약물을 독립 군으로 분해한다」 · `G_prime` 808 · (ii) `target_scaffold` `c1ccccc1` · `sort_key` 「정규화 SMILES(master_X.smiles_canonical) 사전순, 동률 시 cid 오름차순」 · `rule` 「정렬 후 앞 절반 / 뒤 절반. 홀수면 앞쪽이 1 많다.」 · `G_second` 733 · `permutation_scale` B 100,000 · 참조 200,000 · `pair_complement` true · `reporting` 「주 분석 p 와 **병기**한다. 주 분석을 대체하지 않는다.」 · `asserts` 「폴드 배정 불변」 · 「군 재구성 전후 행 집합 동일」 · 「라벨 행렬 불변」 · `no_result_dependent_branching` 「민감도 결과로 주 검정·판정·집계·모델선택을 바꾸지 않는다.」 · `executed_in_block` 115(분할 전 값 — 사이드카 2호 `block_split["115b"] == ["S3"]`). 명세 `implementation_module` = `v3_Multimodal/src/rqint_downstream.py`(`3e92a4ded1ea60b777c460b1b120232ae3051fe3a80e2e7c4f12d943c92ea680` · 42,331 B · 블록 AV 2026-09-23 동결) — `split_no_scaffold` L194-208(라벨 L203 `f"{empty_label}__singleton_{i}"`) · `split_benzene` L211-235(라벨 L228 `f"{target}__A"` · L230 `f"{target}__B"` · 정렬 L224 `(smiles[i], i)`). 사이드카 2호(`c8e1e256…`) `coin_seed.applies_to` = ["115 S4", "115b S3 (i)(ii)"] · `applies_to_note` 「115b(D12) 도 같은 coin_seed 를 쓴다(공통 난수 · 군 수가 달라 동전 벡터 길이는 다르다).」 명세 S3 에는 p 식 필드가 없다.

   - **② 보충·확정**: **(W1′ 군 라벨)** `rqint_downstream.split_no_scaffold` · `split_benzene` 를 import 해 **호출만**(재구현 0 · 새 라벨 규칙 0) — 경위 축자: 「cowork 가 처음에 「새 군의 라벨 문자열이 미정」이라는 전제로 질문했고 사용자가 cowork 추천안(공백 접두 라벨)을 골랐다. 그 직후 cowork 가 명세 `implementation_module` = `v3_Multimodal/src/rqint_downstream.py`(블록 AV · 2026-09-23 동결)에 이미 라벨이 정의돼 있음(`f"{empty_label}__singleton_{i}"` · `f"{target}__A"`/`f"{target}__B"`)을 발견해 정정 질문했고, 사용자가 **동결 함수 사용**으로 확정했다. 두 질문 모두 확증 판독 0 · D12 계산 0 시점이다. 결과적으로 새 자유도는 0 이다(9/23 사전지정을 그대로 집행).」 → 라벨 (i) `"__singleton_{행 인덱스}"` · (ii) `"c1ccccc1__A"`/`"c1ccccc1__B"` · G = 732 → (i) **808** · (ii) **733** · cid sha 규칙 = `sha256(json.dumps([int(cid) for cid in L]).encode()).hexdigest()` (파이썬 기본 구분자 `", "`) → (i) `bd99dfa392442ccf888cf5842c1e074fea52d9487efa000c270060955284765f` · (ii) 앞 `63d8049de17a9dbd83e299d8e114fdba95026308410e4ab714cd3aaf779b9444` · 뒤 `9879e90d7abb4309c1f8405d15ab0910e4c4726e932f20e21bd0ea67f86fa883` — **러너 Mac 재실측 일치**(RDKit 2026.03.3 · 77 · 78 · 39/39 · 벤젠군 SMILES 동률 0 · cowork 실측 환경 Linux · RDKit 2026.03.6). **(W2 p 식)** 주 p = `(1 + c)/(B + 1)` · 보조 p = `(1 + count)/(2B + 1)` 봉인 병기 · SE 동일 — 근거 축자: 「명세 S3 에는 p 식 필드가 없고 `reporting` = 「주 분석 p 와 **병기**」다. 검토자 2026-09-29 의견이 「Holm ⑧ 및 D14 판1 에 확정 주 p 를 **일관되게** 적용」을 요구했으므로 같은 식을 쓴다. 사이드카 3호에 **해석**으로 기록한다(동결물 수정 0).」 · 집계·폴백 분기 = `docs/115` R4c 축자 · identity 시 `count == 2c` assert(R-c 한정) · **D14·D17 미적용**(민감도 · 판정 미사용) · 주 분석 p 와 병기 · 주 분석 대체 금지. **(W3 실행)** `experiments/runs/v3_rqint_d12/` 하나에서 (i) → (ii) 순서 · 감시·자동 재개 · Phase B 1회 — 축자: 「변형마다 **새 `np.random.default_rng(COIN_SEED)`** 로 시작한다(공통 난수 · 사이드카 2호 `applies_to_note` 「군 수가 달라 동전 벡터 길이는 다르다」). 감사 rng 도 변형마다 새 `default_rng(COIN_SEED + 1_000_003)`. 즉 변형 v 의 결과는 **`sap.rqint.rqint_test(P_RF, P_GIN, y, scaffold_group=groups_v, eligible_pt=np.arange(370), n_coin_vectors=100000, seed=COIN_SEED, pair_complement=True, complement_audit_draws=1000, return_perm=True)` 와 비트 일치**해야 한다(합성 Q3 로 증명 · 실데이터는 체크포인트 재개 가능한 청크 실행).」 · 순서 (i) → (ii) · 변형마다 새 `default_rng(2967772708)` · 감사 rng 새 `default_rng(2968772711)` · 변형별 B 100,000 · 감사 1,000 · 집계는 두 변형 done 후 1회. **(검토자 R-b 축자 보충)** 「eps = sap.rqint._EPS(1e-12) 는 원 수학식의 항이 아니라 수치 비교용 구현 규약이다. 결과에 따라 변경하지 않는다(검토자 2026-09-29 · 사이드카 1호 eps_note 보충).」 **(R-c 범위)** 「count = 2c 관계 서술은 complement_identity_used == true 경로에 한정한다.」 **(R-d 축자 보충)** 「보정 전 α = 0.05 에서의 기각 경계 일치(R1 캘리브레이션 감사·구현식 대 주 p 비교)를 Holm 보정 후 판정까지 동일하다는 의미로 확대하지 않는다. 기존 감사 결과의 승계 범위는 확인된 조건(보정 전 α = 0.05 경계)으로 한정한다.」 + 개봉 준비 감사 점검 항목 추가 의무: 「개봉·판정 블록 문면이 보정 전 경계 일치를 보정 후 판정으로 확대 서술하지 않는지 점검 (검토자 R-d · 2026-09-29)」 **(R-e)** 「Holm ⑧ · D14 판1 = 주 p · 판2 폴백 유지(사이드카 1호 d14_panel1_refers_to 재확인)」 · 검토자 회신 = 봉인해제 승인 아님 · R1–R6 재검증 아님. **(폴드 배정 불변의 갈음 · 해석)** 「명세 asserts 「폴드 배정 불변」은 본 계산에 폴드가 입력되지 않으므로(OOF 행렬은 봉인·고정) 「행 수·행 순서·cid 배열·y 바이트 불변 + 변경 행 = 대상 버킷 행뿐」으로 갈음해 검증한다 — 해석」 사이드카 = `v3_Multimodal/config/rqint_downstream_spec_v1_amendment3.json`(동결 2026-10-02T00:40:15+09:00).

   - **③ 시각**: 사용자 결정 W1′·W2·W3 **2026-10-02**(`docs/115b` §0 · 두 질문 모두 확증 판독 0 · D12 계산 0 시점) → 항목 71 기록 2026-10-02 00:38:56 KST → 사이드카 3호 동결 **2026-10-02T00:40:15+09:00** → 본 항목 기록 **2026-10-02 00:41:10 KST**. 이 시점 블록 AZ 의 확증 입력 판독 **0회** · 하네스 미작성 · `experiments/runs/v3_rqint_d12*` **0**.

   - **④ 영향**: 명세 JSON(`fb1de5da…`) · 사이드카 1·2호(`63c29d6b…` · `c8e1e256…`) · `rqint_downstream.py`(`3e92a4de…`) · `sap/rqint.py`(`eb842bc98140e9c5`) · SAP 1.2 manifest(`d08dcedf2a22e1c8`) **0바이트** · 라벨 규칙·p 식·실행 순서는 9/23 사전지정과 기존 결정을 그대로 집행(새 자유도 0) · 결과 미열람 — 봉인 계수 **32/757/734/23** · 지문 6종 착수값 일치 · D12 p **미계산** · `unblinding_performed` **false**.

   - **⑤ 원본 무수정**: 명세 JSON · 사이드카 1·2호 · `rqint_downstream.py` · `sap/*.py` · `rqint_procedure_decisions_v1.json`(`16776f21df6ae29b`) · 항목 69·70·71 전부 무수정. 결정은 **신규 사이드카 3호 파일**로만.

   - **⑥ 관련 해시 (S8 amendment 의무 형식)**: `hash_before` = {명세 **`fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf`** + 사이드카 1호 **`63c29d6b6a9e22951f2e2891b54f4251d5e4f679fc1d3b3f110cfdf510aab05c`** + 사이드카 2호 **`c8e1e2569e7f62fe14a49bdd5581baf3d2d9da9fb411e15099cd85a01bf1a3d8`**} · `hash_after` = {명세·사이드카 1·2호(0바이트 불변) + 사이드카 3호 `v3_Multimodal/config/rqint_downstream_spec_v1_amendment3.json` **`ed054b4a374d8cce69163ff3c3913c3188ad1f436253068ba65dd682198b3fd2`**(9,799 B)} · 구현 모듈 `3e92a4ded1ea60b777c460b1b120232ae3051fe3a80e2e7c4f12d943c92ea680` · `docs/33` 항목 71 기록 후(본 항목 직전) 527,988 B `3cdc3e361e4c55327b915acd144d869e17878488e4ba85c2b238b937b4f4dc88`.

   - **⑦ 범위 밖**: 116 안정성 15셀 SS · 개봉 준비 감사(8차 A-3 + 검토자 R-d 점검) · Holm 7슬롯 조정·판정·개봉(명세 S4 `adjudication`·`holm_family` · D17) · 개봉 승인(양진홍 교수님).

   - **⑧ 사전지정 무결성**: **이 항목과 사이드카 3호의 시각 < 블록 AZ 본런 첫 R2 시각**(Phase B 항목 73 에서 대조). W1′·W2·W3 은 D12 의 어떤 확증 수치(동전 T*·p)도 계산되지 않은 상태에서 결정됐다.

73. **★ D12 민감도 2종 RQ-int 본런((i) G′ = 808 · (ii) G″ = 733 · 변형당 B = 100,000 · 같은 coin_seed) 봉인 완주 — launch 1회 · 재개 0 · 폴백 0 · 데이터 손실 0 (블록 AZ — `docs/115b` Phase B · 주 분석 대체 0 · Holm 조정·판정 0 · 부호 미산출 · 개봉 0)**:

   - **① 원래 기록**: 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da…`) **S3_d12_sensitivity**(`implementation_module` = `v3_Multimodal/src/rqint_downstream.py` `3e92a4de…`) + 사이드카 1호(`63c29d6b…` — 주 p `(1 + c)/(B + 1)` · 보조 p `(1 + count)/(2B + 1)` 봉인 병기) + 사이드카 2호(`c8e1e256…` — coin_seed **2967772708** · `applies_to` ["115 S4", "115b S3 (i)(ii)"] · `block_split["115b"]` == ["S3"]) + 사이드카 3호(`ed054b4a…` — W1′ 군 라벨 = 동결 함수 `split_no_scaffold`·`split_benzene` 호출만 · W2 p 식 = 주 분석과 동일 · W3 한 트리 연속 실행 · 변형마다 새 `default_rng(coin_seed)` · 감사 `default_rng(coin_seed + 1_000_003)` = 2968772711 · D14·D17 미적용 · 「주 분석 p 와 병기 · 주 분석 대체 금지」)가 본런을 사전지정했다 — 변형 순서 i → ii · 동전 벡터 B **100,000**(변형마다) · 참조분포 200,000(`pair_complement`) · 감사 draw 1,000 · 양측 · D4 동전 공유 · D5 consensus 8행렬 루프 밖 1회(변형 공통) · 체크포인트 1,000 동전 · 재개가 난수열을 바꾸지 않음 · 무효 = 값 무관 무결성 사유만. 기록 = 항목 72(D12 계산 0회 시점).

   - **② 실행·판단**: 하네스 `rqint_d12_run.py`(`9f12e430…`)·감시 래퍼 `rqint_d12_watchdog.py`(`f2f6c70a…`)는 Phase A 동결본 그대로 실행됐다(**수정 0** · 공개 manifest 의 `harness_sha256`·`watchdog_sha256`·`selftest_sha256`·`amendment3_sha256` == 동결값). 사용자가 macOS 터미널에서 감시 래퍼를 띄웠다(AZ-10). 감시 래퍼 `watchdog_start` **2026-10-02 12:08:34 KST** → 기동 게이트(load1 < 1.7 × 3회) 대기 1,080.5 s → `launch` 1 · 자식 기동 **12:26:35 KST**. **launch 이력(R2 도달 = launch)**: launch 1 = R0′ first(트리 생성 12:26:38) · R1 군 구성(기본 732 · i 808 · ii 733 — `d12_groups_match_spec` · `rows_cids_labels_unchanged` true) · **R2 2026-10-02 12:26:38 KST** · R3 입력 8행렬 + leverage 검증 · R4a T_obs 비트 일치(블록 AX 기록) · **변형 i** 동전 0 → 100,000(12:26:39 ~ **2026-10-03 08:41:40 KST** · 경과 72,901.5 s ≈ 0.729 s/동전) → `variant_done` i → **변형 ii** 동전 0 → 100,000(08:41:40 ~ **2026-10-04 04:52:28 KST** · 72,648.9 s ≈ 0.726 s/동전) → `variant_done` ii → R4c 집계(done 체크포인트 2개 재로드 · `checkpoint load (aggregate)` 2회 · 봉인) 04:52:29 → R6 봉인 → R7 공개 **04:52:31 KST** → 감시 래퍼 `completed`(exit 0) 04:52:59. **재개 0 · 폴백 0**(두 변형 전 구간 `phase` coins · `k_done` 0 — 감사 실패 시에만 발동하는 값 무관 분기). **전원**: 체크포인트 200/200 AC · `n_power_lost` 0. **운영 사건**: 단일 인스턴스 가드 `refused_duplicate` **0** · `refused_start`·`hard_stop`·`restart_limit`·`stall_suspect` **0** · `compute_lock` stale 인수 **0**(`.compute_lock.stale.jsonl` 3줄 불변). 재실행·재시드·B 축소·동전 폐기 **0**. D12 결과는 **민감도**이며 주 분석(항목 70 ⑧ 주 p)을 대체하지 않고 주 검정·판정·집계·모델선택을 바꾸지 않는다(명세 S3 `no_result_dependent_branching`).
     **Phase A 편차 전부 열거(`docs/115b_rqint_d12_sensitivity_report.md` §5 · 블록 AY 누락 재발 방지 — 항목 71 ② (e))**:
     (1) selftest 실행 3회(하네스 동결 전 · 계산 경로 변경 0 — 1차 Q12 subprocess 트랩 예외 → `_sp_run_untrapped` 수정 · 2차 13/14 Q8 `d14_d17_applied` 키 제거 · 3차 14/14 · 동결 sha = 3차 이후) (L156-159) ·
     (2) 체크포인트 로드 기록 순서 = 판독 → access.log·`checkpoint_load` 기록 → 무결성 검증(변조 파일도 기록 후 13 정지) · purpose = 판독 phase 기준 (L160) ·
     (3) heartbeat `checkpoint_resume` 이벤트 유지(`checkpoint_load` 계수와 분리 · manifest `n_resumes` · V4 산식은 `checkpoint_load` 만) (L161) ·
     (4) done 체크포인트 검증 규칙 추가(보수 방향 — b_done == B · 폴백 키 유무와 감사 실패 수 정합 · done·집계 로드에서도 난수 state 재생 대조) (L162) ·
     (5) Q6 실데이터 검사(공개 전처리 산출물 `master_X` 로 명세 G′/G″ 일치 확인 · 확증 입력 판독 0) (L163) ·
     (6) 감시 래퍼 `main(watchdog_dir, heartbeat_path, spawn)` 선택 인자(Q12 이중 기동 시험용 · 본런은 인자 없이 호출) (L164) ·
     (7) 「폴드 배정 불변」의 갈음 = 행 수·행 순서·cid·`y` 바이트 불변 + 변경 행 = 대상 버킷 행(사이드카 3호 `fold_assignment_note`) (L165) ·
     (8) Q2 AST 예외 = 블록 AY 와 동일(감사 수 1,000 = `CKPT_EVERY` 리터럴 제외 · 주 p 식 문자열은 `check_terms` 결속 assert 전용) (L166) ·
     (9) 사이드카 3호 권한 `chmod a-w` 후 선례(644)로 즉시 복원 · 바이트 무변(sha 동일) (L167) ·
     (10) 항목 72 줄 번호 초안(L209·L236)을 실측(L194-208 · L211-235)으로 기록 전 수정 (L168) ·
     (11) 운영 참고(편차 아님) — 착수 load1 4.25 → 종료 1.03 · 데스크톱 앱 VM 이 기동 지연 가능 (L169) ·
     (12) `CLAUDE.md` 충돌 없음(편차 아님 · 확인 기록) (L170).
     **Phase B 편차**: 독립 검증 스크립트 V7 누설 스캔의 허용 문맥 창(24자)이 `wall_seconds_last_launch` 앞 글자를 잘라 1차 60/61 → 창 40자로 고친 재실행 61/61(검증 스크립트 결함 · 공개 파일·봉인 무관 · 값 노출 0).

   - **③ 시각**: 사용자 결정 W1′·W2·W3 2026-10-02 → 항목 71 2026-10-02 00:38:56 KST → 사이드카 3호 동결 **2026-10-02T00:40:15+09:00** → 항목 72 **2026-10-02 00:41:10 KST** → 하네스·감시 래퍼·selftest 동결 01:21 KST → 감시 래퍼 기동 12:08:34 → 첫 R2 **2026-10-02 12:26:38 KST** → 변형 i 완료 2026-10-03 08:41:40 KST → 변형 ii 완료 2026-10-04 04:52:28 KST → 봉인 완료 **2026-10-04 04:52:31 KST** → 본 항목 기록 2026-10-04 10:24:38 KST. 계산 경과(`wall_seconds_last_launch`) = **145,553.3 s ≈ 40.43 h**(F8 예측 ≈ 40.4 h 대비 +0.1% · 동전 평균 ≈ 0.728 s/개 · 블록 AY 0.727 s/개와 동등).

   - **④ 영향**: 봉인 **32/757/734/23 → 33/763/739/24**(신규 트리 `experiments/runs/v3_rqint_d12/_sealed/` 1개 · 6파일 = `access.log`(3줄 = R0′ 1 + `checkpoint_load` 2) · `checkpoint_i.npz` · `checkpoint_ii.npz` · `t_star_i.npy` · `t_star_ii.npy` · `d12_result.json`) · 입력 access.log = RF consensus **22 → 23줄** · GIN consensus **4 → 5줄** · leverage **3 → 4줄**(= 착수 + launch 1 · 그 외 파일 바이트 불변 — access.log 제외 stat 지문 기존 25트리 `7b617e1c…` · GIN consensus `d061293d…` · leverage `ed9b8605…` 불변 · 기존 25트리 RF 외 access.log 15개 지문 `440226aa…` 불변) · **Holm ⑧ 트리 무접촉**(access.log 2줄 불변 · 지문 `4177f61d…` 불변) → 지문 갱신: 기존 25트리 `a61e4558…` → **`7c585d25a78988fe01358cb33f5edb6935827d9b6bf815bfd0899103b166c0fa`** · GIN consensus `c2715eec…` → **`2d52c9ac03961a6a7610ff7cfee6758fd957c6584867e47e44cb7f62548d11df`** · leverage `717c7162…` → **`f0829db7e97b7fa37722265f311388c2d592b2458b2dbf514fe4748c0dc5a836`** · 신규 트리 **`33a9e057a7786722cb5a7dc640dd63700855eeb7977be8d883f722290bcfd93d`** · 확증 GIN 3트리 `6ed86c86…`·안정성 `b4b493d2…`·Holm ⑧ `4177f61d…` **불변**. 명세·사이드카 1·2·3호·`rqint_downstream.py`·SAP 1.2·`sap/*.py` **0바이트** · Holm 조정 **0** · 판정 **0** · 부호 **미산출** · 개봉 **0** · `unblinding_performed` **false** ×3 · 플래그 ①②③ **3/3 true**.

   - **⑤ 원본 무수정**: 명세 · 사이드카 1·2·3호 · `rqint_downstream.py` · 하네스·감시 래퍼·selftest · 블록 AY 하네스·감시 래퍼·selftest·manifest_public · AX `rqint_leverage_d11.py` · `sap/rqint.py` `eb842bc98140e9c5` · `sap/bootstrap.py` `05437c516e606a05` · SAP manifest `d08dcedf2a22e1c8`(11모듈 등재값 11/11) · `rqint_procedure_decisions_v1.json` `16776f21df6ae29b` · `compute_lock.py` `b03a0b0012948b34` · `confirmatory_oof_rep1.py` `afb894c09fdaad6f` · 입력 8행렬(RF 2 · GIN 6) · leverage `0832ef65…` · `master_X`/`master_Y` · ledger `frozen_artifacts` 경로 보유 37건 전부 불변 · 항목 70·71·72 무수정. 러너 독립 검증(하네스 import 0 · stat·sha·개행 수만) **61/61 PASS**.

   - **⑥ 관련 해시**: `hash_before` = `docs/33` 537,378 B `08918dabc58c61915927619c418fc71676794dbf295740356117843b57c31ffe`(마지막 72) · 봉인 `checkpoint_i.npz` **`135e6960bf9f4dcaffaa4564f4b8108bbdf451847e02b7a0e0fc8579e4a069c1`**(808,306 B) · `checkpoint_ii.npz` **`38c5665b7bf0b5442a13f9aff0422d75f388746e6ae424b3e86ff56db4e302e4`**(808,310 B) · `t_star_i.npy` **`e2257561f635a754cb650fd0c30a703d4b2080593226f1189487f4a720156ffe`**(800,128 B) · `t_star_ii.npy` **`77970055f5f7d3faa1d1e28ab9dc9e21b95184e6b3d5aa46ca9b51aacd651212`**(800,128 B) · `d12_result.json` **`9c8754aac63207954cf4a2122aeb3d22f0d7f8b546487744fe600fd55316f22f`**(4,926 B) · 신규 `access.log` `8c15578b38210a102b9836679881c762ab109a49f1b41599e36609772abf37fb` · 공개 `experiments/runs/v3_rqint_d12/manifest_public.json` **`f49db33795e6d25391b58e26b3e43438da842887c52e6cb756c02a0fdc476ccc`**(3,234 B) · `run.log` `92cfeedc6dbde0497dcdd4923d95f12b13b4f1f3665c89cef9b654770025a8e0` · `heartbeat.jsonl` `84bba20092ad5dddc54b1639c0e0a78bc3edfafbe671346b103c50ac2ba5bd8b` · `experiments/runs/v3_d12_watchdog/watchdog_events.jsonl` `de704ae86742d23eaf5a976936b01ac24de44ac733bb2e1d34d494b786b07164` · `child_stdout.log` `70b225b1c1957e837ee95f29ea2296a7154bea35c504fcdb0faaf818da593cc1` · 하네스 `9f12e4307316e30a7373ad7d2460da945c245e11f34c806864e923133d09bbe7` · 감시 래퍼 `f2f6c70a5a674ef341f0bf7cf049fd59466908dd1a051231125cb0bf1ab2f47b` · selftest `2deeee468d2f42716b1c29446446e44b6d97b2681387eed1d3d8a4f17efe33c7` · 사이드카 3호 `ed054b4a374d8cce69163ff3c3913c3188ad1f436253068ba65dd682198b3fd2` · run_id `AZ-2026-10-02T12:26:38+09:00`.

   - **⑦ 범위 밖**: 116 안정성 15셀 SS · 개봉 준비 감사(8차 A-3 · 독립 기대목록 양방향 · 로그판 14행↔구조화 4행 대조표 · 검토자 R-d 점검 — 사이드카 3호 `opening_prep_audit_checklist_additions`) · Holm 7슬롯 조정·판정(개봉 블록 — 명세 S4 `adjudication`·`holm_family` · D17) · D12 p 의 공개·주 p 병기 서술(개봉 이후) · 개봉 승인(양진홍 교수님). `ledger.first_look_register` **무수정**(선례 — 조회행은 `first_look_log.json`·`docs/45` §5).

   - **⑧ 사전지정 무결성**: **사이드카 3호 2026-10-02T00:40:15+09:00 · 항목 72 2026-10-02 00:41:10 KST · 하네스 동결 01:21 KST < 본런 첫 R2 2026-10-02 12:26:38 KST**(`heartbeat.jsonl` `r2_started` launch 1) — 군 라벨·p 식·실행 순서가 D12 의 어떤 확증 입력 판독보다도 먼저 기록됐다(항목 72 ⑧ 대조 완료). 결과 의존 분기 **0** — 진행 표시는 변형 이름·동전 개수·시간뿐이고, 집계는 두 변형 루프가 모두 끝난 뒤 done 체크포인트에서 1회 · 폴백 미발동 · 재시드·B 축소·동전 폐기 0. 러너는 봉인 «값»을 본 적이 없다 — 기계 판독 경로는 하네스 `run` stage 내부뿐이고, stdout·`run.log`·`heartbeat.jsonl`·`manifest_public.json`·`watchdog_events.jsonl`·`child_stdout.log` 에는 개수·시각·경과·전원·load·sha·불리언만 있다(p·T*·T_obs·count·c·CI 0 — 독립 검증 V7 누설 스캔 0).

74. **★ 안정성 15셀 SS(S6) 착수 전 구현 결정 — I1~I6 · 하네스 동결 (블록 BA — `docs/116` · S6 계산 0 시점)**:

   - **① 원래 기록**: 명세 `v3_Multimodal/config/rqint_downstream_spec_v1.json`(`fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf` · 30,762 B · 블록 AV 2026-09-23 동결) **S6_stability_15cell_ss** 축자 전문(JSON 그대로 · 하네스가 이 JSON 을 읽어서 쓴다): `{"executed_in_block": 116, "execution_timing": "Holm ⑧ 봉인 **이후**", "why_after": "firewall 을 시간 순서로 입증한다. 명세는 블록 AV 에서 미리 동결하되, 실행은 주 검정이 봉인된 뒤다.", "firewall_verbatim": "Stability results must not change the primary results, hypothesis adjudication, model/hyperparameter/seed selection, or the aggregation method. Stability outputs are written to a directory separate from the confirmatory run outputs.", "cells": {"representative_units": [[201, "f4"], [202, "f1"], [203, "f0"]], "seeds": 5, "n_cells": 15}, "inputs": {"confirmatory_partial": "experiments/runs/v3_gin_confirm_rep{r}_seed{s}/_sealed/_partial/{model}_fold{k}_seed{t}.npz", "confirmatory_t_domain": [42, 1, 2], "stability_partial": "experiments/runs/v3_gin_stability/_sealed/_partial/{model}_rep{r}_fold{k}_seed{t}.npz", "stability_t_domain": [3, 4], "note": "두 스키마가 다르다(안정성만 rep 접두가 파일명에 있다). 둘 다 명세에 박는다."}, "fold_level_delta": "Δ_ij = macroAP_ij(M2b) − macroAP_ij(M1b)", "analysis": "서술적 two-way SS 분해", "reported": ["SS_unit/SST", "SS_seed/SST", "SS_res/SST", "unit별 seed 평균/SD/범위", "15셀 값", "셀별 n_eval", "셀별 n_excluded_undefined"], "sst_zero_rule": "SST = 0 이면 비율을 정의하지 않고 not_defined 로 기록한다(0 나눗셈 금지).", "forbidden": ["REML", "ICC", "분산성분 추정", "유의성 검정", "확증 CI"], "descriptive_only": true, "no_result_dependent_branching": "SS 결과로 주 검정·판정·집계·모델선택을 바꾸지 않는다."}` · 구현 모듈 `v3_Multimodal/src/rqint_downstream.py`(`3e92a4ded1ea60b777c460b1b120232ae3051fe3a80e2e7c4f12d943c92ea680`) `two_way_ss` · `v3_Multimodal/config/gin_seed_freeze.json`(`10828447…`) `delta_definition`·`delta_unit_caveat`·`training_seeds_ordered`.

   - **② 구현 결정 I1~I6 (축자 — `docs/116` §0 표 · cowork 구현 결정 · 사용자 결정 아님 · 확증 판독 0 · S6 계산 0 시점)**: 아래 6행은 지시서 표 행을 러너가 파일에서 직접 읽어 바이트 그대로 옮긴 것이다(손 전사 0).

     | # | 구현 사항 | 근거 |
     |---|---|---|
     | **I1** 출력 경로 | `experiments/runs/v3_stability_ss15/`(`_sealed/` + 공개 파일). selftest 출력 = `experiments/runs/v3_ss15_harness_selftest/selftest_ss15.json` | S6 firewall 축자 「Stability outputs are written to a directory separate from the confirmatory run outputs」 · ★ 접두어 `v3_gin_stability` 회피 — 동결 AT 하네스 `confirmatory_gin_train.py` L456 이 `nm.startswith("v3_gin_stability")` 로 디렉터리를 판정한다(AT 는 재실행하지 않지만 판정 집합을 오염시키지 않는다) · selftest 디렉터리는 접두어 `v3_stability_ss15` 를 쓰지 않는다(R0 부재 판정 glob 과 겹치지 않게 · 블록 AW 교차검증 치명 1 선례) |
     | **I2** 공개/봉인 경계 | **S6 산출 전부 봉인**(15셀 Δ · SS_unit/SST · SS_seed/SST · SS_res/SST · SST 와 각 SS · unit별 seed 평균/SD/범위 · 총평균 · 셀별 n_eval·n_excluded_undefined). 공개 = 완료 불리언 · 개수 · 환경 · `wall_seconds` · 사전 정의 게이트 불리언 · 봉인 파일 이름/바이트/sha256 | S7 `boundary` 에 S6 행이 없다 → 가장 가까운 등급(「λ·ρ·e_g 프로파일 · D12 결과 → 봉인 · 공개는 완료 여부 불리언만」)을 적용. 15셀 값은 fold 수준 Δ 라 부호를 직접 싣는다. `n_eval`·`n_excluded_undefined` 는 S7 `n_eval_and_n_excluded_undefined_narrowed_to_sealed` 그대로 봉인. **공개를 줄이는 방향 = 강화 · amendment 아님**(S7 자신의 `not_an_amendment_because` 논리) |
     | **I3** 입력 무결성 사슬 | 확증 partial 18개: 파일 sha == 해당 rep `checkpoint.jsonl` 행의 `artifact_sha256`, 그 `checkpoint.jsonl` 바이트 sha == `manifest_t4.checkpoint_sha256[rep]`. 안정성 partial 12개: 파일 sha == 안정성 `checkpoint.jsonl` 행의 `artifact_sha256` **그리고** == `manifest_s2.partial_sha256[name]`, 그 `checkpoint.jsonl` 바이트 sha == `manifest_s2.checkpoint_sha256`. fold 행 = `folds.json`(1차) + `fold_membership.csv` `fold` 열(교차) · 두 파일 sha == `v3_confirm_rest/rest_public.json` `inputs_sha256.splits` | S1 `inputs.folds` 「하네스가 기록한 것을 그대로 쓴다 · 재생성 금지」 · AU 계약 `partial_format_reason` 「행 순서 = `np.where(fold_membership.fold == k)[0]` 오름차순」 · AT/AU 하네스의 `folds.json` ↔ `fold_membership.csv` 교차 assert 선례 |
     | **I4** 무효 사유(값 무관) | S1 5종(입력 sha 불일치 · 행 순서/cid 불일치 · 비유한 값 · 입력 결손 · 셀 수 불일치)을 준용하고 S6 구조 사유 3종을 더한다: partial 키 집합 ≠ {`P_test`,`best_ep`,`best_v`} · `P_test.shape` ≠ (n_te, 370) · 같은 셀의 M1b·M2b `n_eval` 불일치(같은 y 이므로 구조적으로 같아야 한다). → **전체 무효·상신 · 출력 디렉터리 미생성.** 불리한 셀만 재생성·제외 **금지** | S1 `invalidation_rules_value_independent`·`invalidation_consequence` · S6 에는 무효 조항이 없으므로 보수 방향으로 준용 |
     | **I5** SST = 0 표기 · provenance | `two_way_ss` 는 SST = 0 이면 `frac_*` 를 `None` 으로 돌려준다 → 봉인 JSON 에서는 S6 `sst_zero_rule` 축자대로 **문자열 `"not_defined"`** 로 기록하고 `sst_zero: true` 를 함께 둔다. 모듈 반환의 `provenance: "synthetic_fixture"` 는 봉인 JSON 에서 **`"confirmatory_sealed"` 로 덮어쓰고** 원래 값을 `module_provenance_constant` 로 병기한다 | S6 `sst_zero_rule` 「SST = 0 이면 비율을 정의하지 않고 not_defined 로 기록한다」 · 모듈 `PROVENANCE` 는 합성 전용 상수(모듈 docstring) |
     | **I6** 행렬 방향 | `delta_cells` (3, 5) — 행 = unit 순서 `[(rep1, fold4), (rep2, fold1), (rep3, fold0)]`(= S6 `representative_units` `[[201,"f4"],[202,"f1"],[203,"f0"]]` 순서) · 열 = 학습 시드 **값** `[42, 1, 2, 3, 4]`(= `gin_seed_freeze.training_seeds_ordered`). SD 는 모듈 그대로 `ddof=1` | S6 `cells` · `inputs.confirmatory_t_domain` [42,1,2] · `stability_t_domain` [3,4] · S1 `notation_freeze`(파일명·키의 `seed{t}` 의 t = 학습 시드 **값**) |

   - **③ 시각**: Holm ⑧ 봉인 2026-10-01 02:50:35 KST → D12 봉인 2026-10-04 04:52:31 KST → 지시서 `docs/116` 등록(2026-10-04) → 착수 게이트 P1~P11 **94/94 PASS**(2026-10-04 11:06 KST) → selftest 1회차 2026-10-04 11:14:23 KST 착수 **12/13**(K2 `no_path_pattern_literals` — K2 검사 함수 자신의 탐지용 부분문자열 리터럴 3개를 스스로 적발한 자기참조 오탐 · 탐지 문자열을 명세 JSON 에서 읽도록 수정) → selftest 2회차 2026-10-04 11:14:46 KST 착수 **13/13 PASS**(결과 `ts_kst` 2026-10-04 11:15:28.570 KST) → **하네스·selftest 동결** 2026-10-04 11:15:53 KST → 본 항목 기록 **2026-10-04 11:16:47 KST**. 두 회차 모두 확증 입력 판독 0(합성 fixture 만 · 확증 판독 전이므로 수정 허용 — 지시서 BA-4 1). **cowork 측 편차 1건 축자 기록**: 「2026-10-04 지시서 교차검증 중 독립 에이전트가 확증 rep 3개·안정성 `checkpoint.jsonl` 4개에 `wc -l`(줄 수 세기)을 1회 실행했다. 허용 범위(stat · access.log 개행 수) 밖의 봉인 파일 바이트 판독이며 access.log 기입은 없다. 출력은 줄 수뿐이고 필드·값은 열람하지 않았다(사람에게 노출된 것은 숫자 105/105/105/42 뿐 — 동결 계약·공개 manifest 의 단위 수와 같다). 파일 바이트·지문은 변하지 않았다(본 블록 P2 확인).」

   - **④ 영향**: 아직 없음 — 봉인 계수 **33/763/739/24** 불변 · stat 지문 7그룹·access 제외 지문 5종 착수값 일치(게이트 P2) · `experiments/runs/v3_stability_ss15*` **0** · S6 셀 값 **미존재** · `unblinding_performed` false · 플래그 ①②③ 3/3 true. selftest 디렉터리 `experiments/runs/v3_ss15_harness_selftest/`(봉인 밖 · 합성 전용) 신설.

   - **⑤ 관련 해시**: 하네스 `v3_Multimodal/src/stability_ss15_run.py` **`1e39d07117327b1cf026be31c002f01dfc7c236ccfdb6c20be3b4880388e51d1`**(87,795 B) · selftest `experiments/runs/v3_ss15_harness_selftest/selftest_ss15.json` **`17aabe39cae04268a0a93cf0b929dcc3b5f95252a6113bc1c68a2f19e6bffec2`**(6,495 B · K1~K13 13/13 · skip 0 · `provenance` `synthetic_fixture`) · 명세 `fb1de5da61b30165af2b8f9debb6112611f0af48b6849ed4e1ad5dd52e84b3bf` · 구현 모듈 `3e92a4ded1ea60b777c460b1b120232ae3051fe3a80e2e7c4f12d943c92ea680` · `docs/33` 본 항목 직전 549,408 B `4f48b6d976c37428`. 이후 하네스 수정 = 블록 무효(지시서 BA-4 2).

   - **⑥ 시간 순서**: Holm ⑧ 봉인 2026-10-01 02:50:35 KST < D12 봉인 2026-10-04 04:52:31 KST < 본 항목 기록 2026-10-04 11:16:47 KST < (예정) `--stage run` R2. 명세 S6 `execution_timing` 「Holm ⑧ 봉인 **이후**」 충족.

   - **⑦ 범위 밖**: 개봉(`open_sealed`) · Holm 7슬롯 조정·판정 · S6 결과의 해석 · 개봉 준비 감사(8차 A-3 + 검토자 R-d — 사이드카 3호 `opening_prep_audit_checklist_additions`) · 개봉 승인(양진홍 교수님).

   - **⑧ 사전지정 무결성**: S6 는 2026-09-23(블록 AV) 동결이며, I1~I6 과 하네스는 **S6 셀 값이 존재하지 않는 시점**(확증·안정성 partial 판독 0)에 확정됐다. 무효 규칙은 값과 무관한 I4 뿐이고 결과 의존 분기 0 — 산출값을 보고 재실행·셀 선택·집계 변경·시드 교체를 하지 않는다(명세 `global_no_result_dependent_branching` · S6 `no_result_dependent_branching`).

75. **★ 안정성 15셀 fold 수준 Δ + 서술적 two-way SS 분해 봉인 산출 (블록 BA — `docs/116` · S6 실행 · 서술 전용 · 판정 0 · 부호 미산출 · 개봉 0)**:

   - **① 원래 기록**: 명세 `rqint_downstream_spec_v1.json`(`fb1de5da…`) **S6_stability_15cell_ss**(블록 AV 2026-09-23 동결 · 축자 전문 = 항목 74 ①) + 항목 74(I1~I6 · 하네스 동결 · 2026-10-04 11:16:47 KST).

   - **② 실행·판단**: 착수 게이트 P1~P11 94/94 PASS → selftest 2회(1회차 12/13 — K2 자기참조 오탐 · 2회차 13/13 · 둘 다 확증 판독 전) → 하네스 동결 → 항목 74 → `--stage run` **1회**(재실행 0 · exit 0 · 2026-10-04 11:16:56 KST 기동 · G-IDLE A load1 1.44 · `ComputeLock` 획득·해제). 하네스 `run` 내부 기계 판독 = 확증 partial 18 + 안정성 partial 12 = **30** · `checkpoint.jsonl` **4**(확증 rep 3 + 안정성 1) · `master_X`/`master_Y` · split 6 · manifest 3종(공개). I3 sha 사슬 전건 일치 · cid/fold 행(219/218/218) 일치 · 유한성 · 구조 검사 통과 → **R5 무효 미발동**. `sap.metrics.macro_ap`(eligible `np.arange(370)` 명시) 30회 → 15셀 Δ(M2b − M1b) → `rqint_downstream.two_way_ss` 1회. 산출은 전부 `_sealed/ss15_result.json` 에만 봉인 · 공개 = 개수·불리언·sha·시각뿐 · `wall_seconds` 2.998. 러너 독립 검증 V1~V9 **59/59 PASS**(하네스 import 0 · stat·sha·access.log 개행 수 · 공개 파일만). **BA 편차**: (a) selftest 1회차 K2 실패(자기참조 오탐 — 검사 함수가 탐지용 부분문자열 리터럴 3개를 스스로 적발 · 탐지 문자열을 명세 JSON 에서 읽도록 수정 · 확증 판독 전 · 지시서 BA-4 1 허용 범위) · (b) 하네스 동결 전 실제 저장소에서 `gate` 를 읽기 전용으로 1회 사전 점검(`docs/33` 항목 74 검사만 우회 · 쓰기 0 · 봉인 내용 판독 0 · 봉인 stat·access.log 개행 수·공개 파일만) — 동결 후 R0 실패로 블록이 보류되는 것을 막기 위한 보수적 확인 · (c) 기록용 입력 partial 30 sha256 은 러너가 파일 바이트 해시로 재계산(내용 판독 0 · 안정성 12개는 `manifest_s2.partial_sha256` 와 일치 확인) · (d) `run.log` 에 지시서 열거(R0·R2·R3·R4·R6·R7) 외 R1·R5 행도 남김(개수·불리언 문구뿐 · 강화 방향) · (e) 기록 스크립트·게이트·검증 스크립트는 scratchpad 에 두었다(저장소 미추가).

   - **③ 시각**: 항목 74 2026-10-04 11:16:47 KST → R2 2026-10-04 11:16:58.161 KST(`run.log` seq 3) → R6 2026-10-04 11:17:00.198 KST(seq 7) → R7 2026-10-04 11:17:00.650 KST(seq 8) → 본 항목 기록 2026-10-04 11:35:44 KST.

   - **④ 영향**: 봉인 33/763/739/24 → **34/765/740/25** · 확증 access.log 25/25/24 → **26/26/25** · 안정성 4 → **5** · 신규 `v3_stability_ss15/_sealed/access.log` 1줄 · stat 지문 확증 → `54db739fd07cae92b7665267f28720d52645ff19784777d4b4b3752148ac6776` · 안정성 → `01578eda438edce87ce30dfabb89d242b55ddf3cd0e3ebefa06e29f3f222d7ec` · 신규 `v3_stability_ss15` → `19a79b7f57c3febd5493d650c500c2fabeb5e4ed89b725aa6ec58c7eb5c70735` · access 제외 지문 확증 `1992ab00…`·안정성 `65f08361…` **불변**(= access.log 외 바이트 불변) · 기존 25트리 `7c585d25…`·GIN consensus `2d52c9ac…`·leverage `f0829db7…`·Holm ⑧ `4177f61d…`·D12 `33a9e057…` **불변** · RF consensus 23 · GIN consensus 5 · leverage 4 · Holm ⑧ 2 · D12 3 access.log 불변.

   - **⑤ 원본 무수정**: F4(명세·사이드카 1~3호·`rqint_downstream.py`·`gin_seed_freeze.json`·`gin_stability_contract.json`·`compute_lock.py`·`sap/__init__.py`·선행 하네스 5종) · F5(SAP 1.2 manifest·`sap/{metrics,consensus,decision,rqint,bootstrap}.py`) · 입력(manifest 3종·`master_X/Y`·split 6) sha 전건 일치(V7).

   - **⑥ 관련 해시**: 하네스 `1e39d07117327b1cf026be31c002f01dfc7c236ccfdb6c20be3b4880388e51d1` · selftest `17aabe39cae04268a0a93cf0b929dcc3b5f95252a6113bc1c68a2f19e6bffec2` · `manifest_public.json` `dba5e314b953c83e6fb30d6069d7401cde1d88155f181171d9b3d49f4f85d1aa`(1,715 B) · `_sealed/ss15_result.json` `105af61769107e694b1fb7eb96584771c6c14b160f8baddf0268edd042358fdd`(11,634 B) · 신규 access.log `2dba9827d3b11ca5bb2447eb740f748b13e2c4089f599b73c04e0f45f7362f12` · `run.log` `75a9d832956509376cd92199caf490f58a632afda5e8750beb4185fb4cdb5ccc` · run_id `BA-2026-10-04T11:17:00+09:00` · 입력 partial 30 집합 sha(정렬 JSON) `4eee281392873dc0c0c4667dda3cd29202140fb51fab428b662c2b051cb20da1`.

   - **⑦ 범위 밖**: 개봉(`open_sealed`) · Holm 7슬롯 조정·판정 · **S6 결과의 해석** · 개봉 준비 감사(8차 A-3 + 검토자 R-d) · 개봉 승인(양진홍 교수님). firewall 축자: 「Stability results must not change the primary results, hypothesis adjudication, model/hyperparameter/seed selection, or the aggregation method. Stability outputs are written to a directory separate from the confirmatory run outputs.」

   - **⑧ 사전지정 무결성**: S6 동결 2026-09-23 < 항목 74 2026-10-04 11:16:47 KST < R2 2026-10-04 11:16:58.161 KST — 구현 결정과 하네스가 계산보다 먼저 기록됐다. 결과 의존 분기 0(재실행·셀 선택·집계 변경·시드 교체 0) · REML·ICC·분산성분·검정·CI 0 · `emit_sign` 0 · 러너는 봉인 «값»을 본 적 없다(기계 판독 경로 = 하네스 `run` 내부뿐 · stdout·`run.log`·`manifest_public.json` 에는 개수·시각·sha·불리언만).

76. **★ 사전지정 민감도 3종(M1b_pchembl·M2b_pchembl·P-FAM_selfclust) RF OOF 학습 착수 전 결정 — G7 · J1~J6 · 하네스 동결 (블록 BB — `docs/117` · 학습 0 · 지표 0 시점)**:

   - **① 원래 기록**: `v3_Multimodal/config/ladder_freeze.json`(`b885585aefbabb32f432b2e60141f6b12ac8bdf971066a9434021762e6ef0868` · 16,896 B · 동결 2026-07-24) 축자 — `sensitivity_models` = `{"M1b_pchembl": ["B0", "B1", "B_m1b_pchembl"], "M2b_pchembl": ["B0", "B1", "B_m1b_pchembl", "B_seq"], "P-FAM_selfclust": ["B0", "B1", "B_m1b", "B_fam_selfclust"]}` · `sensitivity_blocks` = `{"B_m1b_pchembl": "pChEMBL 포함(13차원) M1b 공변량 — primary B_m1b(10차원, §4 일치)의 pChEMBL 포함/제외 robustness. sensitivity 모델 M1b_pchembl=[B0,B1,B_m1b_pchembl], M2b_pchembl=[B0,B1,B_m1b_pchembl,B_seq].", "B_fam_selfclust": "자체 mmseqs 50% 클러스터(09) — P-FAM primary에서 대체 후 §9 sensitivity 보존. sensitivity 모델 P-FAM_selfclust=[B0,B1,B_m1b,B_fam_selfclust]."}`. 사전등록 §4(모델 사다리)·§9(sensitivity — family 정의 다중 · pChEMBL 포함/제외) 의 사전지정 민감도. 확증 OOF 는 지금까지 어떤 `_sealed/` 에도 없었다(`docs/116c` §8 조사).

   - **② 결정 축자 + 구현 결정**: **G7**(사용자 · 2026-10-04 13:1x KST · `docs/116c` §8 축자) 「**G7 = 개봉 전 학습 블록 추가.** pChEMBL 13차원판(M1b_pchembl·M2b_pchembl)·P-FAM_selfclust OOF 를 개봉 전에 동결 하네스로 생성·봉인 → 개봉 시 민감도로 함께 산출.」 · **J1**(지표 미계산) 「블록 I 는 반복별·consensus `metrics_full.json`(macro AP)을 함께 봉인했지만, 본 블록은 **OOF·consensus 행렬만** 봉인한다. AP 는 개봉 블록이 동결 절차로 일괄 계산한다(봉인 값의 종류를 늘리지 않는 쪽 · 강화 방향)」 · **J2** 「모델 정의 정본 = `ladder_freeze.json` `sensitivity_models` — 하네스는 그 JSON 을 sha 검증 후 읽어서 블록 목록을 만든다. `ladder_confirmatory.MODEL_BLOCKS` 의 `M1b_pchembl`·`M2b_pchembl` 항목과 일치 assert(`P-FAM_selfclust` 는 `MODEL_BLOCKS` 에 없음 — JSON 만 정본)」 · **J3** 「오케스트레이션만 하네스에 둔다 — 블록 fit 순서·누수 assert·RF 호출 흐름은 블록 I `fit_fold`/`predict_fold` 와 같은 논리를 블록 목록 인자로 일반화. 과학 경로(블록 클래스 · `rf_fit_predict` · `RF_KW` · `SEED` · `PCA_K` · `load_frozen`)는 import 그대로」 · **J4** 「출력 = `experiments/runs/v3_confirm_sens/_sealed/`(partial·checkpoint·env·equivalence) · `v3_confirm_sens_rep{r}_seed{s}/_sealed/oof_{model}.npz` · `v3_confirm_sens_consensus_rep123/_sealed/consensus_{model}.npz` · selftest = `experiments/runs/v3_sensoof_harness_selftest/selftest_sensoof.json`」 · **J5** 「consensus = 같은 run 의 반복 OOF 3개를 메모리에서 `sap.consensus.build_consensus([rep1, rep2, rep3])`(1→2→3 고정)」 · **J6** 「새 코드 경로 검증 = 라벨 무관 2중 — (a) seed-42 개발 split train 에서 블록만 fit 해 `B_m1b_pchembl` 13 · `B_fam_selfclust` 835 · 조립 차원 M1b_pchembl 2063 · M2b_pchembl 2127 · P-FAM_selfclust 2895 정확 일치(`data/processed/_ladder_smoke_stats.json` `724685376479ae49…`) (b) 확증 rep1 fold 0 primary P-FAM 을 하네스 오케스트레이션과 `confirmatory_oof_rest.fit_fold`/`predict_fold` 로 각각 계산해 `P.tobytes()` 동일(메모리 내) (c) hstack 순서 = `sensitivity_models[model]` 리스트 순서」. 모델 3종 × 반복 3(분할 시드 201/202/203) × fold 5 = **45 fit** · RF `random_state=42` · 바이트 동일성 증명 = M2b rep1 fold0 vs `v3_confirm_rep1_seed201/_sealed/oof_M2b.npz`(기대 sha `350fa12fac84ef4ca1355d256665c333d9cd8ca34de257e7321aefa36d8a3260` · 감사 기준선 `sealing_completeness_audit.json` `b189f77f30dce9b5` 경로 키 조회). **9차 리뷰 U6 대조**: 정의 동결(2026-07-24)은 RF 부호 최초 인지(2026-07-27 반복1)보다 앞서지만 **학습은 그 이후**이며, 결정자는 부호 인지자와 같은 연구자다 — 본 블록은 새 자유도 0(동결 정의 집행: 새 모델·하이퍼·블록·시드 0)이고 결과 무관(지표·Δ·부호 미계산 · 결과 의존 분기 0)이다.

   - **③ 시각**: selftest 1회차(S1~S11 11/11 PASS · skip 0 · 2026-10-04 13:24:39 → 13:25:54 KST · 실패 회차 0 · 확증 판독 0) → 하네스·selftest 동결 → 실저장소 gate S0 읽기 전용 사전 점검(docs/33 항목 검사만 우회 · 쓰기 0 · PASS) → 본 항목 기록 2026-10-04 13:26:48 KST. verify·run 은 본 항목 이후.

   - **④ 영향(아직 없음)**: 봉인 34/765/740/25 불변 · `v3_confirm_sens*` 0개 · 신규 비봉인 1트리(`v3_sensoof_harness_selftest/selftest_sensoof.json`) · 학습 0 · 확증 봉인 판독 0.

   - **⑤ 관련 해시**: 하네스 `v3_Multimodal/src/confirmatory_oof_sens.py` `967f3749cb0796e7202de6723e1694d96c4605dc2e5374972f739c6f812e76d9`(88,861 B) · selftest `experiments/runs/v3_sensoof_harness_selftest/selftest_sensoof.json` `96ab3332fd5bbf91ad833aaaf4f76f70c786d9ea63903b699f2533c8ec53fe70`(6,821 B).

   - **⑥ 참조**: 개봉 산출 범위 공백 G1~G10 의 결정(`docs/116c` §8)은 블록 118(개봉 절차 동결)에서 집행한다.

   - **⑦ 범위 밖**: AP·Δ·부호·p·CI 계산 · 개봉(`open_sealed`) · Holm 조정·판정 · 개봉 절차 동결(118) · 개봉 준비 감사(119) · 개봉 승인(양진홍 교수님).

   - **⑧ 사전지정 무결성**: 정의(2026-07-24 동결) → G7(2026-10-04 13:1x) → J1~J6(`docs/117`) → 하네스·selftest 동결 → 본 항목 → (이후) verify 판독 → 첫 fit. 모델·블록 목록은 JSON 에서 읽고(selftest S2 AST — core 범위 리터럴 재기술 0) RF 레시피·시드는 import 그대로라 구현 자유도가 결과를 볼 수 있는 시점 전에 모두 닫혔다.

77. **★ 사전지정 민감도 3종 RF OOF 학습·봉인 완주 (블록 BB — `docs/117` · 지표 0 · 개봉 0)**:

   - **① 원래 기록**: `ladder_freeze.json` `sensitivity_models`(2026-07-24 동결 · 축자 전문 = 항목 76 ①) + 항목 76(G7 · J1~J6 · 하네스 동결 · 2026-10-04 13:26:48 KST).

   - **② 실행·판단**: 착수 게이트 P1~P10 전건 PASS(F1~F8 재측정 일치) → selftest 1회(S1~S11 11/11 · skip 0) → 하네스 동결 → 항목 76 → `--stage verify` **1회**(exit 0 · 2026-10-04 13:26:55.086 KST 기동 · G-IDLE A PASS · `ComputeLock` 획득·해제): I-3 정합(약물 1,092 · scaffold 그룹 732 · fold 교차 0 · rare-PT 0) · **J6(a)** seed-42 개발 split train 873 에서 `B_m1b_pchembl` 13 · `B_fam_selfclust` 835 · 조립 차원 2063/2127/2895 정확 일치 · **J6(b)** primary P-FAM rep1 fold0 하네스 vs 블록 I `fit_fold`/`predict_fold` `P.tobytes()` 동일 · **F6** rep1 `access.log` +1줄(machine_read · 2026-10-04 13:31:32.732 KST) 후 `oof_M2b.npz` 판독(바이트 sha = 감사 기준선 `350fa12f…` 일치) → M2b rep1 fold0 218행 × 370 **dtype·shape·tobytes 3중 일치(byte_identical true)** → `_equivalence/` 2파일 봉인. → `--stage run` **1회 완주**(세션 1 · 재개 0 · exit 0 · 45 fit · OOF 9 · consensus 3 · `wall_seconds` 4180.803). **BB 편차**: (a) 첫 `run` 기동(2026-10-04 13:31:43 KST)은 G-IDLE 게이트 A 가 load1 ≥ 2.0(verify 의 RF 병렬 fit 잔여 감쇠)로 **진입 거부**(exit 10 · gate·락·쓰기 이전 · 디스크 변화 0) → load1 < 1.8 대기 후 재기동(2026-10-04 13:33:40.308 KST 세션 1 시작) — 하네스·입력 무수정이라 BB-5 「기술 결함 재시도」 범위 · 세션 수에 미산입(체크포인트 0 상태). (b) 하네스 동결 후 실저장소에서 `gate(S0)` 를 읽기 전용으로 1회 사전 점검(docs/33 항목 검사만 우회 · 쓰기 0 · 봉인 내용 판독 0) — 블록 BA 편차 (b) 와 같은 보수적 확인. (c) verify 의 run.log 는 성공 후 일괄 기록(실패 시 stdout 만 — 상태 S1 판별 단순화) · run.log 를 verify·run 이 같은 파일에 append(S1 최상위 허용 항목 = `_sealed`·`run.log`). (d) `checkpoint.jsonl` 의 `blocks_fit` 필드를 [블록, 차원] 쌍으로 기록(블록 I 는 블록 이름만 — 공개 `block_dims` 의 `B_fam_selfclust` fold별 차원을 재개 시에도 체크포인트에서 복원하기 위함 · 필드 집합은 지시서 열거 13개 그대로). (e) 기록·게이트·검증 스크립트는 scratchpad(저장소 미추가). (f) 하네스 소스가 `confirmatory_oof_rest` 를 모듈째 import(`cor`)해 J6(b) 에서 `make_blocks`·`fit_fold`·`predict_fold` 를 호출 — 지시서 J6(b) 가 그 비교를 명시하므로 그 3함수는 verify 전용(run·core 미사용 · selftest S3 AST 로 core 의 RF 호출 경로 = `predict_h` 단독 확인). (g) import 사슬(`confirmatory_oof_rest` → `confirmatory_oof_rep1` → `sap.metrics`·`sap.redaction`)이 지표 모듈을 메모리에 적재하지만 **하네스 소스의 호출 0**(selftest S10 AST — 지시서 §2-1 판정 기준).

   - **③ 시각**: 항목 76 2026-10-04 13:26:48 KST < verify 판독 2026-10-04 13:31:32.732 KST < 첫 fit 2026-10-04 13:35:13.761 KST < 완료 2026-10-04 14:43:20.684 KST → 본 항목 기록 2026-10-04 14:44:11 KST.

   - **④ 영향**: 봉인 34/765/740/25 → **39/826/801/25**(신규 5트리: `v3_confirm_sens/_sealed` 49 = partial 45 + checkpoint + env + `_equivalence/` 2 · rep 트리 3 × OOF 3 = 9 · consensus 3 · 신규 access.log 0) · `v3_confirm_rep1_seed201/_sealed/access.log` 개행 **17 → 18** · 그 밖 access.log 24개 개행 불변 · 기존 25트리 access 제외 지문 `7b617e1c…` 불변(= access.log 외 경로·크기 불변) · 기존 25트리 새 stat 지문 `d984c66b898dcbeebf305a16ded5b7036f277d2c77f3eec35995f7f1153dea84` · 신규 sens 그룹 지문 `6e9a581d7181d5283e599d41661d9588bbd4ab6988f3b87af0a8026bb714e083` · 확증 GIN `54db739f…`·안정성 `01578eda…`·GIN consensus `2d52c9ac…`·leverage `f0829db7…`·Holm ⑧ `4177f61d…`·D12 `33a9e057…`·S6 `19a79b7f…` **경로·크기 불변**.

   - **⑤ 원본 무수정**: F4(`ladder_freeze.json`·`_ladder_smoke_stats.json`·`ladder_confirmatory.py`·`confirmatory_oof_rest.py`·`confirmatory_oof_rep1.py`·`compute_lock.py`·`sap/{consensus,__init__}.py`·SAP manifest·08·09 CSV·선행 하네스 5종) sha 전건 일치 · `inputs_sha16` 10/10 · split 6 == `rest_public`(V6).

   - **⑥ 관련 해시**: 하네스 `967f3749cb0796e7202de6723e1694d96c4605dc2e5374972f739c6f812e76d9` · selftest `96ab3332fd5bbf91ad833aaaf4f76f70c786d9ea63903b699f2533c8ec53fe70` · `manifest_public.json` `9a1b9230fdc3b66a072a6b2de13875199b6cd6f3a26037bb612c8db25a284752`(21,571 B) · `run.log` `c672ffb185c583f08d2997d25ce77bf86cbf0cddeef41d2845ddb20de16ed50c` · `_equivalence/equivalence.json` `2700bcadc3d5d3e4b49f2d62070f6293c3a97ffdf4070ed6170a67ecfd5b69b0` · `_equivalence/repro_M2b_rep1_fold0.npy` `3151e927e96853a83891b2f5944a348b176a53a2c22da80f6f065be5611cf4b7` · 봉인 61파일 (이름, sha) 정렬 JSON sha `4ea93061d5e6170769b98526bcecd7a34bd8bf2cbdfbadaa1e4a1d9d569b8686`(목록 = `manifest_public.json` `sealed_files`).

   - **⑦ 범위 밖**: AP·Δ·부호·p·CI 계산(J1 — 개봉 블록이 동결 절차로 일괄) · 개봉(`open_sealed`) · Holm 조정·판정 · 개봉 절차 동결(118) · 개봉 준비 감사(119) · 개봉 승인(양진홍 교수님).

   - **⑧ 사전지정 무결성**: 정의 동결 2026-07-24 < 항목 76 2026-10-04 13:26:48 KST < verify 판독 < 첫 fit — 구현 결정·하네스가 학습보다 먼저 기록됐다. 결과 의존 분기 0(지표를 계산하지 않으므로 재학습·제외·순서 변경의 근거가 될 값 자체가 없음 · 재개 0) · 새 모델·하이퍼·블록·시드 0 · `emit_sign`·`open_sealed`·지표 함수 호출 0 · 러너는 봉인 «값»을 본 적 없다(기계 판독 경로 = 하네스 verify·run 내부뿐 · stdout·`run.log`·`manifest_public.json` 에는 개수·시각·차원·wall·sha·불리언만 · 독립 검증은 stat·sha·개행 수만).

78. **★ 개봉 절차 동결 — G1~G11 · X1~X3 집행 · 계획 JSON·개봉 스크립트·독립 검산기·보고 계획 (블록 BC — `docs/118` · 봉인 판독 0 · 개봉 0)**:

   - **① 원래 기록**: 등록 docs/30 §8(다중비교 ① 무보정 · ②~⑧ Holm · 성공 기준 RQ2·RQ3·RQ4 · 최소 성립 조건 「RF family에서 RQ2 + (RQ3 또는 C-CAP) + RQ4 + scaffold·약물 수준 CI」) · SAP 1.2(`experiments/sap/manifest.json` `d08dcedf2a22e1c8493c842507422de1f6c705ce54ce995e038e09f604706e10` · `sap/decision.py` `f688b20d816acabe17c2906cfa846c1f794ba45a416248c08aa7e41676e82a92`) · 명세 `rqint_downstream_spec_v1.json` `fb1de5da…` + 사이드카 1·2·3호 · 기존 개봉 규약 축자 「개봉은 Holm ②~⑧ 전원이 갖춰진 뒤 **1회·일괄**, 교수님 승인 이후에만 · 부분 개봉 없음」(`docs/70`:27) · 개봉 기록 = 승인자·승인 시각·대상 목록(`docs/70`:178-179) · 승인자 = 양진홍 교수님(`docs/77`).

   - **② 결정 축자 (전부 봉인 값 미열람 상태에서 결정)**: X1~X3·G1~G11 = 2026-10-04 12:4x~13:2x KST(`docs/116c` §7·§8) · H1~H4 = 2026-10-04 13:4x KST(118 교차검증 후). 축자(`docs/118` §0-1·§0-1b 표 행 그대로 · 계획 JSON `decisions.rows_verbatim` 에 동일 전재):
     - | **X1** | 절차 동결(118) → 전수 감사(119) → 승인 → 개봉(120). 승인은 **118 동결 해시 + 119 감사 리포트 해시**에 결속 |
     - | **X2** | ⑧ 귀무 문면·보고 계획을 개봉 승인 요청에 **비차단 첨부**(외부 검토자 의견은 받되 개봉을 막지 않음) |
     - | **X3** | **독립 소형 검산기만**: SAP 코드·개봉 스크립트를 import 하지 않고 동결 문면만으로 짠 검산이 개봉 산출과 일치해야 공개 |
     - | **G1** | ①②③⑤⑥⑦ 및 secondary 전 대비 공통: **bootstrap seed 6001 · sign-flip seed 6002 · B 10,000** · eligible = `np.arange(370)` 명시. ① CI 는 재계산해 봉인 `d9_bca_result.json["rf"]` 와 **비트 일치 assert** · ① Δ 는 `holm8_result.json["delta_rf"]` 와 비트 일치 assert |
     - | **G2** | ④ 슬롯 p = **max(p_emp_global, p_emp_family)**. 두 원 p 와 RQ4 판정 병기 |
     - | **G3~G10** | cowork 기본안 일괄(§0-3 표) — 같은 절차·「비판정·secondary」 라벨·결과와 무관하게 전부 보고 |
     - | **G7** | 민감도 OOF 3종은 블록 BB 가 봉인 → 개봉 시 secondary 로 산출 |
     - | **G11** | **판정 p = Holm 조정 p**: `rq3_decision` 의 p = ②·③ Holm 조정 p · `rq4_decision` 두 입력 = ④ 슬롯 Holm 조정 p(같은 값) · RQ-int = ⑧ Holm 조정 p < α(D7) · ① RQ2 = 원 p(무보정). 원 p 항상 병기 |
     - | **H1** RQ8 외부·시간 검증 | 사전등록 §12·§13-9 「외부/temporal 1종(본문 최소 1종)」 은 **수행·이탈 기록 모두 없었다**(교차검증 실측). → **계획만 개봉 전 동결**: cowork 가 `docs/118b_external_validation_plan.md`(데이터 소스·분할·모델·지표·판정)를 작성·사용자 확인 후 **119 착수 전** 동결하고, 실행은 개봉 이후 별도 블록. 본 블록은 계획 JSON `prereg_coverage` 에 「RQ8 = plan_frozen_pre_opening(docs/118b · sha256 `4f06d39e9aa827bd63a2ac28e6dbedbedec2430bbde10aaadd567c81c726f60e`) · execution_post_opening」으로 등재만 한다(RQ8 의 R8-1~R8-3 = 라벨 출처 이식성 · EU∪UK 주 · 부호 일치만 — 2026-10-04 사용자 결정) · `docs/118b` 는 **동결물 목록(승인 결속 `approved_hashes`)에 추가**한다 |
     - | **H2** C-CAP 판정 | 등록 §8 「최소 성립 조건 = RQ2 + (RQ3 또는 C-CAP) + RQ4」 의 C-CAP(M2b − C-CAP) = **RQ3 와 같은 규칙 · 원 p**(Holm family 밖 · 무보정): `sap.decision._contrast_pass(ci_primary, p_raw)`(CI 하한 > 0 ∧ p < α · not_estimable → 실패). **최소 성립 = RQ2 ∧ (RQ3 ∨ C-CAP) ∧ RQ4** 를 판정 출력에 포함 |
     - | **H3** 판정 Holm 판 | **RQ3·RQ4·RQ-int 판정 = 판1(⑧ = 주 p)의 조정 p**(사이드카 1호 `d14_panel1_refers_to` 정합). 판2(⑧ = 1.0)는 전 표 보고 + 슬롯별 결론 차이 플래그만 |
     - | **H4** 그 밖 미수행 등록 항목 | **일괄 이탈 기록 + 계산 가능한 것만 포함.** 개봉 전 `docs/33`(항목 78)에 항목별 미수행 사유 기록: §5 B(degree-preserving 재학습 null)·C(residue-shuffle) · §4 추가 baseline 중 LR(Morgan+multi-hot)·ridge·MLP(Morgan+평균 ProtBERT) · §8 PT bootstrap(endpoint-generalization) · §9 hard cold split·dual-shift · §11 XAI · §12 PU. **봉인물로 산출 가능해 개봉 산출에 포함**: label prevalence baseline(PT prevalence 상수 예측의 macro AP — 라벨만으로 결정) · target-only sequence baseline(`consensus_seq`·`consensus_seq_sens` macro AP) · RQ7 부속 지표(⑦ rep별 `metrics_full.json` 봉인값 공개) · ④ null 분포 그림(`v3_null_MAIN/_sealed/checkpoint.jsonl` 의 primary `macro_AP` 열 + T_obs 수직선) · GIN ②③⑤ 방향(GIN cell_1 점추정 · 기술) |
     - 9차 리뷰 반영(`docs/116b`·`116c` B 버킷): ⑧ 귀무 문면(U1) · 추론 대상 축자 + 해설(U5) · 부호 인지·결정 대조표(U6) · S6 금지 표현 · 보고 우선순위·공개 의무(#2) · 합성 Holm 7슬롯 검증(#3) → 계획 JSON `reporting_text` · selftest U3.
     - G11 근거: 등록 §8 「②~⑧ Holm 보정」 · D7(RQ-int = Holm 조정 p < α). 판정 p = 판1 조정 p(H3 · 사이드카 1호 `d14_panel1_refers_to` 정합) · ① RQ2 = 원 p.
     - **H4 미수행 등록 항목별 이탈 기록** (13건 · 개봉 전 기록 · 결과 무관):
     - §4 neural family mean + DeepSets 병행(보조) — 등록 위치 docs/30 §4 · 미수행 사유: DeepSets 집계 미구현 — GIN 은 mean-pool 집계판만 학습 · **개봉 전 기록**
     - §4 M1b 적응증·ATC 통제 sensitivity — 등록 위치 docs/30 §4 · 미수행 사유: 적응증·ATC 공변량 미수집·미학습 · **개봉 전 기록**
     - §4 C-CAP train–val gap 보고 — 등록 위치 docs/30 §4 · 미수행 사유: 확증 RF 하네스 산출물에 train/valid 지표 기록 없음(rest metrics_full 키 = OOF macro AP 계열만 · confirmatory_oof_rest.py:651-661) · **개봉 전 기록**
     - §4 baseline Morgan + target multi-hot (LR) — 등록 위치 docs/30 §4 · 미수행 사유: LR 모델 미학습(H4) · **개봉 전 기록**
     - §4 baseline Morgan + 평균 ProtBERT (ridge · MLP) — 등록 위치 docs/30 §4 · 미수행 사유: ridge·MLP 모델 미학습(H4) · **개봉 전 기록**
     - §4 보조자료(C-RAND · M3 · M4 · neural DeepSets · ESM-2 · affinity top-k sweep · PU-loss · calibration 세부 · leave-one-target-out · 1,000회 test-time permutation · 단계화 null · 적응증·ATC) — 등록 위치 docs/30 §4 · 미수행 사유: 보조자료(본문 아님) 실험 미수행 — H4 일괄 이탈 기록 · **개봉 전 기록**
     - §5 B retrained degree-preserving null — 등록 위치 docs/30 §5 · 미수행 사유: 재학습 null 미수행(H4) · **개봉 전 기록**
     - §5 C residue-shuffle — 등록 위치 docs/30 §5 · 미수행 사유: residue-shuffle 임베딩 미산출(H4) · **개봉 전 기록**
     - §8 PT bootstrap (endpoint-generalization sensitivity) — 등록 위치 docs/30 §8 · 미수행 사유: PT 재표본 bootstrap 미구현(H4) · **개봉 전 기록**
     - §9 하드 cold split (stress test) — 등록 위치 docs/30 §9 · 미수행 사유: family-disjoint split 미생성(H4) · **개봉 전 기록**
     - §9 dual-shift exploratory stress test — 등록 위치 docs/30 §9 · 미수행 사유: dual-shift split 미생성(H4) · **개봉 전 기록**
     - §11 XAI(tier-2) — 등록 위치 docs/30 §11 · 미수행 사유: attribution 분석 미수행(H4) · **개봉 전 기록**
     - §12 PU(보조) — 등록 위치 docs/30 §12 · 미수행 사유: PU-loss·FAERS 검증 미수행(H4) · **개봉 전 기록**
     - 산출 불가(데이터 구조 · 이탈 아님 · 개봉 산출에 `not_computable` 로 보고):
     - §7 N=5 macro AP — not_computable: master_Y 는 양성 ≥ 10 PT 370 열만 보유(데이터 구조)
     - §7 양성 1~2개 초희소 PT exploratory stratum — not_computable: master_Y 는 양성 ≥ 10 PT 370 열만 보유(데이터 구조)
     - **RQ8(H1)**: 등록 §12·§13-9 「외부/temporal 1종(본문 최소 1종)」은 수행·이탈 기록 모두 없었다 → 계획만 개봉 전 동결(`docs/118b_external_validation_plan.md` sha256 `4f06d39e9aa827bd63a2ac28e6dbedbedec2430bbde10aaadd567c81c726f60e` · 12,000 B · R8-1~R8-3 = 라벨 출처 이식성 · EU∪UK 주 · 부호 일치만) · 실행은 개봉 이후 별도 블록 · 계획 JSON `prereg_coverage` = `plan_frozen_pre_opening` · 승인 결속 `approved_hashes` 에 포함.

   - **③ 시각**: 착수 게이트 P1~P8 PASS(2026-10-04 23:1x KST) → 공식 selftest 2026-10-04 23:38:52 ~ 23:41:26 KST → 동결 매니페스트 2026-10-04 23:41:43 KST → 본 항목 기록 2026-10-04 23:43:01 KST. 모두 120 개봉 실행·승인 이전.

   - **④ 영향**: 봉인 **39/826/801/25 불변** · stat 지문 9그룹(기존 25트리 `d984c66b…` · 확증 GIN `54db739f…` · 안정성 `01578eda…` · GIN consensus `2d52c9ac…` · leverage `f0829db7…` · Holm ⑧ `4177f61d…` · D12 `33a9e057…` · S6 `19a79b7f…` · sens `6e9a581d…`) 착수 = 종료 동일 · access.log 25개 개행 불변 · `v3_unblinding*` 0 · `__pycache__` 4,541 불변 · `--stage run` 실행 0 · 동결물(SAP·명세·사이드카·decision.py 등) 0바이트 수정.

   - **⑤ 동결 해시 7종**: `v3_Multimodal/config/unblinding_plan_v1.json` `d5aa594b630992fd10739573409a2008227db72a843f310b001b9ca24ce59764`(항목 38개 · 입력 48파일 · 판독 트리 26개 · prereg_coverage 67항목 누락 0) · `v3_Multimodal/src/unblinding_run.py` `84f773596a01cf3fdc93334ca2f01af977d24e939a911be42f464b3f95cc3737`(PLAN_SHA256 상수 = 계획 sha) · `v3_Multimodal/src/unblinding_watchdog.py` `334eced17a6db4925c8f9011acc5e28cb326f7081aedb0e0102b8414cdd6fd3e` · `v3_Multimodal/src/unblinding_independent_check.py` `10075502901efbcc370edad527169dd8da5928a2abfd6bb799fc4d4a5700939e` · `docs/118_unblinding_reporting_plan.md` `e3b342e75cfee99a062d67b6cdfe16d3c614dad9b5b4c7333ab89ccee8203abb` · `experiments/runs/v3_unblind_freeze/selftest_unblinding_run.json` `7a477fd1cfdd13740e1987a3450464861a8a2ba50d25b862dd6c59262eb0842a`(U1~U16 + 정상 완주 17/17 · skip 0) · `experiments/runs/v3_unblind_freeze/selftest_independent_check.json` `17da44e69df3c053a1139b2d676303816e2876b17af80d3acbf050d722efa58f`(K1~K11 11/11) · 동결 매니페스트 `experiments/runs/v3_unblind_freeze/freeze_manifest.json` `4ed6a5e4a9df67347d7dc1441b25c4e15441838981237741bb5a66b8f8665a9c`.

   - **⑥ 승인 결속**: 개봉 승인은 위 동결 해시와 `docs/119_pre_unblinding_audit_v3_report.md`·`experiments/provenance/pre_unblinding_audit_v3.json`(119 산출 · 스키마는 계획 JSON `expected_hash_source` 에 고정)에 결속된다. 승인 기록 `experiments/provenance/unblinding_approval.json` 은 블록 120 러너가 사용자가 제공한 승인 증거(Gmail)로 작성하며, `approved_hashes` 7경로 전부가 현재 파일 sha 와 같아야 `--stage run` 이 진행한다(G-gate). 감시 래퍼·selftest 2종은 run stage 의 selftest 결속 검사(script·plan·watchdog·checker sha)로 결속.

   - **⑦ 범위 밖**: 개봉 준비 전수 감사(119 — 전 봉인 파일 내용 해시 vs 생성 기록 · access.log 내용 · 대장 대응표) · 개봉 승인 요청(X2 비차단 첨부 = `docs/118_unblinding_reporting_plan.md`) · 개봉 실행(120) · RQ8 실행.

   - **⑧ 사전지정 무결성**: 모든 결정(X1~X3 · G1~G11 · H1~H4)과 계산 절차·판정 입력·보고 문면·실패/재개 규칙이 개봉 전에 기록·동결됐다. 다만 **RF 부호 4건 인지 상태**(2026-07-27 연구자 1인 · 정본 `experiments/provenance/sign_disclosure_matrix.json`)에서 이뤄진 결정이라는 사실을 병기한다 — 「완전 맹검」 주장 금지(보고 계획 `sign_awareness_table`). 러너는 봉인 파일을 하나도 열지 않았다(키 경로는 writer 코드 file:line 에서 확정 · 봉인 트리는 stat·이름·크기와 access.log 개행 수만 · 합성 selftest 는 tempfile 저장소에서만 실행).

79. **★ 개봉 전 전수 감사 v3 착수 전 동결 — Y1~Y10 · 독립 기대목록 801 · 감사 스크립트 · 합성 결함 U1~U17 (블록 BD — `docs/119` · 봉인 판독 0)**:

   - **① 원래 기록**: 8차 리뷰 A-3(`docs/113c` 줄 58 — ① 독립 기대목록 동결 ② 값 비판독 인터페이스 + 합성 결함 사례 + 코드 해시 + 독립 검토를 **먼저** 고정 ③ 1회 실행 · 양방향 대조 · 대장 원기록 보존 + 출처 표시 대조표) · 9차 리뷰 §3 운영 사건 표(`docs/116c` 줄 66~76 · 6행) · 사이드카 3호 `rqint_downstream_spec_v1_amendment3.json` `opening_prep_audit_checklist_additions`(R-d · 2026-09-29) · 9차 U2(stat 지문 = 경로·크기만) · 계획 JSON `unblinding_plan_v1.json` `expected_hash_source`(9키 · `report_path` = `docs/119_pre_unblinding_audit_v3_report.md`) · 선행 감사기 `pre_unblinding_audit.py` `224a5c8b…`·`pre_unblinding_audit_v2.py` `13cf681a…`(참조만 · import 0).

   - **② 변경 내용(Y1~Y10 · `docs/119` §0 축자 요약)**: Y1 두 단계(Phase A 동결 → cowork 독립 검토 → Phase B 1회) · Y2 봉인 sha = 1 MiB 청크 바이트 해싱 · access.log 기록 0 · Y3 `sealed_sha256` = access.log 를 뺀 봉인 산출물 801개(계획 JSON 「전 봉인 파일」 문구에 대한 **해석** — access.log 는 120 이 줄을 더하는 대장이므로 `access_log_lines` 개행 수로 고정) · Y4 생성 시점 sha 기록이 없는 8파일 = `no_creation_hash` 비차단(이번 감사 sha 를 첫 기준값으로) · Y5 기록원 여럿이면 전부 일치(불일치 = 차단) · Y6 기대목록은 기록물 + 동결 설계 격자로만(live 열거는 대조 단계에서만) · Y7 9키 JSON + 상세 파일 분리 · Y8 차단 사유가 있으면 verdict FAIL · 동결물 수정은 별도 블록 · Y9 문면 정정은 항목 80 append · Y10 중도 실패 시 9키 JSON 미작성. **구현 결정(러너 · 지시서 공백 보충)**: (a) build-expected 단계는 `no_sealed_io` 가드(봉인 경로 open·listdir·scandir 즉시 실패)로 실행 · (b) 보조 기록원(Y5) 범위 = `first_look_log.json` · `ledger.json` · `sealing_completeness_audit.json`(AO v1 기록원) · `experiments/runs/*/` 의 `*_public.json`·`config.json`·`_run_state.json`·`_consensus_state.json` 70개 — 64자 sha 값 1,917건 중 기대 파일로 해석 1,283 · 일치 1,265 · **불일치 0** · 미해석 634(그중 기대 sha 와 값 일치 15) · **via_checkpoint 대상 18건(FLL 블록 BA 항목의 확증 GIN partial sha)은 Phase B 투영 뒤 대조로 지연** · (c) 열람 대장(B6) 대응 = 블록 8개(AT·AU·AW·AX·AY·AZ·BA·BB)의 [착수, 완료] 시간창(docs/33 항목 62·64·66·68·70·73·74~77 ③ 및 docs/110·111 report2 시각) × 트리 × writer 소스 문자열 상수(purpose·actor) · AO 기준선 줄은 AO 규칙(JSON 객체 · type machine_read · `human_exposure is True` 금지)으로만, 기준선 이후 줄은 필수 키 6종 전부 요구 · `"OPEN sealed"` 부분문자열 > 0 = 차단 · (d) Y4 조건 = 존재 근거(`confirmatory_gin_train.py:378` · `confirmatory_gin_stability.py:467` `allowed_top`) · mtime ≤ manifest_t4/manifest_s2 `ts_kst` · 그룹 `__no_access` 지문이 블록 완료 이후 기록(`stability_ss15_run.py:125`·`:126`)과 live 에서 같음 · (e) B7(a) 「난수 state 재생 대조 기록의 존재」 = run.log `R4b resume` 줄 존재 + 하네스 소스 순서(`rqint_holm8_run.py:819` 난수 state 대조 분기 < `:832` resume 기록) · (f) 누설 스캔의 금지 키 검사는 경로 키(예: 봉인 파일명 `lambda_selected.json` 3개)를 제외.

   - **③ 사유**: A-3 ①·② 를 Phase B 실행 **전에** 고정해 기대목록·판정 규칙이 실측 결과에 맞춰 바뀔 여지를 없앤다(비순환). 구현 결정 (a)~(f)는 지시서가 형식만 정한 부분을 기록원·writer 소스 file:line 근거로 구체화한 것이다.

   - **④ 결정 주체·시각**: cowork 기본안(Y1~Y10 · 사용자 위임 「G3~G10 기본안 일괄」) · 구현 결정 (a)~(f) = 러너(지시서 공백 보충 · `docs/119_pre_unblinding_audit_v3_phaseA_report.md` §5 공개) · 동결 2026-10-05 01:21:07 KST · 본 항목 기록 2026-10-05 01:22:51 KST.

   - **⑤ 영향**: 개봉 전 · 판정 무관. 봉인 판독 0(봉인 바이트 해싱·투영은 Phase B 로 미룸) · access.log 기록 0 · 계산 0 · 네트워크 0 · git 쓰기 0. 독립 기대목록 = **801**(E-A 275 · E-B 387 · E-C 45 · E-D 22 · E-E 11 · E-F 61) · 분류 recorded 478 · recorded_via_checkpoint 315 · no_creation_hash 8 · 격자 대조 = 확증 315 단위·oof 63 이름·안정성 42 이름 전부 일치 · 기록원 불일치 0. 합성 결함 selftest **17/17**(U1~U17 · 오라클 U11 = `unblinding_run.stat_summary` 서브프로세스 대조 일치). 봉인 39/826/801/25 · 18키 · access 개행 25파일 223 착수 = 종료.

   - **⑥ 해시**: `v3_Multimodal/src/pre_unblinding_audit_v3.py` f750f457e254fce0f285339b5f0f8dc16a65140b668c18572e8ed7f74fad121e(125,497 B) · `experiments/runs/v3_preaudit_v3/selftest_audit_v3.json` 0206118188c544258d8513a29752da8d3cd65fb2a7ecaf29f33c5317a54052b8(5,144 B) · `experiments/runs/v3_preaudit_v3/expected_manifest_v3.json` cf513074e756572fc3f7283f291c5e3a6644701ba94caf02c7f58d817480e43c(712,170 B). `--stage run` 이 줄 전체 정규식으로 읽는 고정 마커:

     expected_manifest_v3 sha256: cf513074e756572fc3f7283f291c5e3a6644701ba94caf02c7f58d817480e43c
     audit_script sha256: f750f457e254fce0f285339b5f0f8dc16a65140b668c18572e8ed7f74fad121e
     selftest sha256: 0206118188c544258d8513a29752da8d3cd65fb2a7ecaf29f33c5317a54052b8

80. **★ 개봉 전 전수 감사 v3 실행 결과 (블록 BD — verdict · 801 대조 · 열람 대장 · 운영 사건 · R-d · 문면 정정)**:

   - **① 결과 요약**: `--stage run` 1회(2026-10-05 01:36:39 ~ 01:36:45 KST · 착수·종료 실저장소 게이트 16/16 PASS · 오라클 `unblinding_run.stat_summary` 착수 = 종료) → **verdict = FAIL · 차단 1/1** = `access_unattributed`(`experiments/runs/v3_gin_stability/_sealed/access.log` 4번째 줄). **내용 대조는 전건 통과**: 기대 801 ↔ live 801 · 일치 801 · 누락 0 · 초과 0 · 크기 불일치 0 · sha 불일치 0 · 기록원 불일치 0(보조 지연 대조 18/18 일치) · checkpoint 3파일 sha = manifest_t4 · 형식 위반 0 · 투영 315 단위 = 격자. 열람 대장 25파일 223줄 · human_exposure true 0 · 형식 오류 0 · `OPEN sealed` 0 · 미대응 **1**. 스키마·결속 재검(120 G-gate 규칙 독립 구현) 실패 0 · 누설 스캔 적중 0. **차단 원인(공개 기록 근거)**: 그 줄은 블록 **AV**(`docs/112_rqint_downstream_spec_report.md` §3-4 · 2026-09-23 · P5 해시 대조 · actor `vscode-claude` · purpose `hash-compare` · 안정성 access.log 3→4줄)가 남긴 것으로, 항목 79 ② (c) 에 동결된 대응 규칙의 블록 목록 8개(AT·AU·AW·AX·AY·AZ·BA·BB)에 AV 가 없고, 그 줄의 actor·purpose 가 writer 소스 문자열 상수가 아니라(러너 수동 게이트) 규칙상 대응될 수 없었다. 기록물상 출처는 존재하나, 동결 규칙으로는 미대응이므로 Y8 에 따라 verdict FAIL 을 그대로 둔다 — 동결물(감사 스크립트 · 기대목록) 수정·재실행은 **본 블록에서 하지 않는다**(Y8·Y10 — cowork 판단 후 별도 블록 · 같은 경로 덮어쓰기 시 ledger supersede). 비차단: Y4 `no_creation_hash` 8파일(첫 기준값 sha16 — 확증 rep1 `a756ca42371bdb8f`·`ca588703c42d5ceb` · rep2 `ce8096df00c05794`·`de09926449cf0635` · rep3 `b202a3ba126a15c2`·`e050d55884c11f36` · 안정성 `d0e83a3172c01306`·`7c78ec05cefb82b4` · 각 env_fingerprint.json·train_stdout.log 순) · `rd_verbatim_absent`(cowork Phase A 판정 (b) 비차단 확정).

   - **② 문면 정정 3건(Y9 · 기존 항목·리포트 본문 수정 0)**:
     - (i) **stat 지문 근거 「바이트/내용 불변」 표현** — 「stat 지문은 경로·크기 불변만 증명한다. 내용 불변은 본 감사(항목 80)의 sha 대조로 사후 확인했다」. 대상 6줄 = 항목 23(L404) · 66(L2265) · 68(L2301) · 70(L2337) · 73(L2435) · 75(L2480). 본 감사 801/801 sha 일치로 사후 뒷받침됨(`supported_by_sha_audit` true).
     - (ii) **블록 BA `wc -l`**(항목 74 · L2460) — 「봉인 파일 판독 발생 · 구조 정보(줄 수) 사람 노출」. 대상 4파일(확증 GIN 3트리·안정성 `_sealed/checkpoint.jsonl`) 현재 sha = 기대(판독이 변경을 낳지 않았음).
     - (iii) **115b 감시 이벤트 의미** — 감시 래퍼 `completed.ckpt_sha256`(`1e55328b77b8dc9e`) = heartbeat 206번째 `checkpoint` 이벤트(변형 ii · coins 단계 · 완료 직전 체크포인트)를 `rqint_d12_watchdog.py:159` 규칙으로 옮겨 적은 값이며, 207번째 `variant_done` 이 그 뒤 덮어쓴 상태를 기록했으므로 **현재 어느 봉인 파일과도 같지 않다**(과거 상태). heartbeat `variant_done` 해시 2건은 각각 현재 `checkpoint_i.npz`·`checkpoint_ii.npz` sha 와 같다.
     - (추가 · cowork Phase A 판정 (a)) 지시서 `docs/119` §4 B-1 6(c)의 「`docs/33` 항목 73」은 오기이며 AY Phase A 편차 12건의 기록은 **항목 71**(L2347 · 2026-10-02 00:38:56 KST)이다.
     - (관찰 · 비차단) 계획 JSON `outputs.expected_post_counts.at_118_stat` 30/831 은 이름과 달리 「118 시점 값으로 계산한 개봉 후 예상치」다(118 시점 실측 25/826). 동결물이라 수정 0.

   - **③ 운영 사건 6행**: (a) AY SIGTERM·재개 — heartbeat 125 이벤트 · checkpoint 100 · 카운터 누락 0 · 중복 0 · run.log launch [1,2] = manifest `n_launches` 2 · 재개 1 = `n_resumes` 1 · 체크포인트 sha 100개 상이(연속 반복 0) · 마지막 heartbeat 체크포인트 sha = 봉인 `checkpoint.npz` 현재 sha · 난수 state 재생 대조 기록 존재(`R4b resume` 줄 + 소스 순서 `rqint_holm8_run.py:819` < `:832`). (b) 감시 래퍼 중복 기동 — 이벤트 21 · `watchdog_start` 6(launch_index 0·0·0·1·1·1) · launch 2 · child pid 2 유일 · run_id 1 = manifest · 봉인 출력 작성 주체 1. (c) AY Phase A 편차 12건 — 발생 = `docs/115` Phase A 2026-09-28 11:19~12:05 KST · 기록 = 항목 71 2026-10-02 00:38:56 KST. (d) 115b — ② (iii). (e) BA `wc -l` — ② (ii). (f) BA 구현 결정 I1~I6 — 근거 줄: I1 L2445·2449·2453·2470 · I2 L2454 · I3 L2455 · I4 L2456·2470 · I5 L2457(+ `docs/116` 리포트 L78) · I6 L2445·2449·2458·2470 — 판단 cowork 검토 대상.

   - **④ 대장 3벌 대응표**: `docs/45` §5 16행 ↔ `first_look_log.json` 19행 ↔ `ledger.json` `first_look_register.rows` 4행(dict 6키) — 16행 전부 FLL 대응 · FLL 미대응 0 · 반복 1·2·3·consensus 4행 = FLR rows 4 · 새 행 추가 0. 서명 일치: FLL 부호 인지 4 = `sign_disclosure_matrix.json` `n_rows` 4 = rows 4 · AO 이후 신규 0 · 세 값 일치.

   - **⑤ R-d 판정**: 검사 대상 문장(두 키워드군 동시) **0** · 위반 0/0 · 비해당 a_only 3 · b_only 14 · 사이드카 3호 `reviewer_20260929.r_d` 축자 문장 실림 = 계획 JSON 아니오 · 보고 계획 아니오(요지 문장만 — 비차단 확정). 범위 밖 사본 = AO 규칙 ⓐ~ⓓ 전부 충족 · `non_blocking_recorded`(사본 3파일 · 사본 디렉터리 2 · 그 안 7파일 = AO 와 동일).

   - **⑥ 결정 주체·시각**: 실행·기록 = vscode-claude(runner · 지시서 `docs/119` Phase B · cowork Phase A 검증 PASS 2026-10-05) · 실행 2026-10-05 01:36:39~01:36:45 KST · 본 항목 기록 2026-10-05 01:39:44 KST. 영향: 개봉 전 · 판정 무관 · 봉인 역직렬화 0(투영 3파일 키 화이트리스트 제외) · access.log 기록 0 · 값 출력 0 · 네트워크 0 · git 쓰기 0. **120 G-gate 는 verdict PASS 를 요구하므로 현 9키 JSON(FAIL)으로는 개봉 불가.**

   - **⑦ 산출 해시**: `experiments/provenance/pre_unblinding_audit_v3.json` 65c5bfb2ca141a515d91e3ec51ecfe090bdd349941409515ff4c688810a0e1b8(124,817 B · 9키 · verdict FAIL) · `experiments/runs/v3_preaudit_v3/audit_details_v3.json` d033df07dc6f6b28db40f45ccc0df0a1ba2de1e8cca01868e2a8a0a49ff6a1b6(44,842 B) · `experiments/runs/v3_preaudit_v3/run.log` cd941fe610066b0765dfd882eb93d67f8f5b526e0608ef5a72e0b6902d2b59ca(1,217 B) · 리포트 `docs/119_pre_unblinding_audit_v3_report.md` 는 자기 sha 미기재.

81. **★ 개봉 전 전수 감사 v3 재실행 준비 — 열람 대장 대응 규칙 보정(Z1~Z6) · 1회차 보관 (블록 BE — `docs/119b` · 봉인 판독 0)**:

   - **① 원래 기록**: `docs/119` §3-B6 대응 규칙(대응 키 = 블록 [착수, 완료] 시간창 + 트리 + writer 소스 문자열 상수 · 블록 목록 8개 AT·AU·AW·AX·AY·AZ·BA·BB) · 항목 79 ② 구현 결정 (c) · 1회차 결과 = 항목 80(verdict FAIL · 차단 1 = `experiments/runs/v3_gin_stability/_sealed/access.log` 4번째 줄 `access_unattributed`). 그 줄의 출처 = 블록 AV 공개 리포트 `docs/112_rqint_downstream_spec_report.md`(22,143 B · `73ad76c5…`) §3-4 L148~149(2026-09-23 기록). 경위: 지시서 r1(14,125 B)은 Z1 ① 을 「인용 JSON == 줄 전체(키·값 전부)」로 정했으나, 러너가 A-0 직후 공개 바이트 기록으로 그 인용이 **요약 인용**임을 보이고 보류했다(`docs/119b_pre_unblinding_reaudit_hold_report.md` 8,689 B · `f67579f0…` §4-1 — 전이 362 B 대 인용 직렬화 177 B · 1회차 형식 검사상 그 줄은 필수 6키(`ts_kst` 포함)를 가짐). 지시서 r2(16,482 B · `a2915338…`)가 그 보류를 반영해 Z1 을 바이트 고정 규칙으로 교체했다.

   - **② 변경 내용(Z1~Z6 · 스크립트 diff 요약 — 전문은 `docs/119b_pre_unblinding_reaudit_phaseA_report.md` 부록)**: **Z1** 대응 규칙 (b) 추가 — 등록 블록 리포트(sha 고정) 한 문단에 백틱 access.log 경로 · 「N줄 → N+1줄」 · 「A B → C B」 · 백틱 한 줄 JSON 인용이 각 정확히 1개일 때만 후보 · 대응 조건 = 줄 순번 == N+1 ∧ 시작 바이트 오프셋 == A ∧ 길이(개행 포함) == C − A ∧ 인용 ⊆ 줄(키·값 동일 · 줄의 추가 키 허용) ∧ `ts_kst` ∈ 블록 시간창 · 대응 결과에 `rule` = `a_writer` | `b_manual_documented` 기록(함수 `manual_gate_candidates` · `manual_match` · `audit_access`). 기존 규칙 (a) 불변 · 수동 등록 블록은 (a) 에서 건너뜀. **Z2** 블록 목록에 AV 추가(`docs/112` · 리포트 sha `73ad76c5…` · 트리 `v3_gin_stability` · 시간창 2026-09-23 00:00:00~23:59:59 KST 일 단위 · `writers` [] · `manual_lines_from_report` true). **Z3** `ops.ay_deviations.spec_item` 73 → **71**. **Z4** 1회차 산출 보관(⑥). **Z5** 1회차 대비 섹션 대조 — 9키 JSON 은 `verdict`·`audited_at_kst` 를 뺀 7키 바이트 동일 · 상세는 지시서 제외 섹션 + 러너 선언(라벨 메타 `block`·`instruction`)을 뺀 나머지 동일 · 선언 변화 D1~D4(D1 Z3 의 직접 결과 spec_item 73→71·일치 불리언 · D2 문면 정정 대상 중 1회차 이후 기록된 항목 ≥ 80 줄 · D3 docs/45 §2·§3 append 로 §5 줄 번호가 모든 행에서 같은 상수만큼 이동 · D4 저장소 전역 파일 수 카운터 2개)만 허용 · 그 밖 차이 = 차단 `rerun_vs_run1_mismatch`(함수 `rerun_compare` · `stage_run`). run 전제 = 출력 디렉터리 정확히 {1회차 selftest · selftest r2 · expected_manifest · run1_FAIL/} · run1_FAIL 5파일 sha 고정 · 9키 JSON·상세·run.log·리포트 부재 · 마커 `audit_script_r2`·`selftest_r2`(각 1개) · `expected_manifest_v3`(항목 79·81 전부 같은 값). selftest 출력 = `selftest_audit_v3r2.json` · **U18**(하위 a 대응 · b 순번 · c 인용 없음 · d 미등록 문서 · e 인용 값 · f 오프셋 · f 길이 · g 시간창 → 차단) 추가 · 상단 docstring·`BLOCK`·`INSTRUCTION` 표기. 그 밖의 함수·상수·출력 형식 변경 0 · 스펙·기대목록·기대 상수 변경 0.

   - **③ 사유**: cowork 지시서 설계 결함 — `docs/119` §3-B6 은 writer 소스 문자열 상수만 대응 근거로 인정했고, 러너가 수동 게이트로 남긴 줄(블록 AV)과 그 블록이 블록 목록에 없었다. **이 보정은 1회차 FAIL 결과를 본 뒤에 이뤄졌다**(Z6). 보정 근거(블록 AV 리포트)는 2026-09-23 작성 공개 기록이며, 이번 보정은 그 1줄 외에 대응 범위를 넓히지 않는다 — 조건 ④·⑤ 가 그 줄을 파일 안에서 바이트로 유일하게 고정하고 (b) 등록 블록은 AV 1개뿐이다. r1 이 요약 인용을 축자 인용으로 오인해 보류됐다는 사실(`docs/112` 인용은 요약 인용 — 바이트 근거)도 함께 공개한다. Z5 선언 변화 D1~D4 는 지시서 Z5 가 열거하지 않은 「입력 불변인데 필연적으로 달라지는 필드」를 Phase B 실행 **전에** 고정한 러너 구현 결정이다(cowork 검토 대상).

   - **④ 결정 주체·시각**: cowork 기본안(Z1~Z6 · `docs/119b` r2 · Y10 「재감사 = 별도 블록 · 같은 경로 덮어쓰기 + ledger supersede」 집행) · Z5 선언 변화 D1~D4·`BLOCK`/`INSTRUCTION` 표기·run 전제 세부 = 러너(지시서 공백 보충 · Phase A 리포트 §5 공개) · 보관 2026-10-05 21:55 KST · 동결 2026-10-05 22:00:37 KST · 본 항목 기록 2026-10-05 22:02:06 KST.

   - **⑤ 영향**: 대응 범위 = 블록 AV 1줄(`v3_gin_stability` access.log 순번 4 · 공개 리포트 문단 L148 파싱 결과 = 오프셋 975 · 길이 362 · 인용 키 6). 그 밖의 판정 규칙·기대목록 801·기대 상수·출력 형식 불변. 개봉 전 · 판정 무관 · 봉인 판독 0(Phase A 에서 access.log 는 selftest 의 stat 개행 수 세기만) · access.log 기록 0 · 계산 0 · 네트워크 0 · git 쓰기 0. 봉인 39/826/801/25 · 18키 · access 개행 25파일 223 불변. 합성 결함 selftest **18/18**(U1~U17 유지 + U18 하위 8/8).

   - **⑥ 해시**: 보정 스크립트 `v3_Multimodal/src/pre_unblinding_audit_v3.py` a5e19ba3f2ade25c7a893ed602343e70de1ad2242a6b04cb76c953b01bb9bcbd(142,438 B · supersedes 1회차 f750f457e254fce0f285339b5f0f8dc16a65140b668c18572e8ed7f74fad121e) · `experiments/runs/v3_preaudit_v3/selftest_audit_v3r2.json` d423a2b505d420a8842d276e2aebd810a845dc555f9bbdf38c27cb4c06b4ed8d(7,571 B · supersedes 1회차 selftest 0206118188c544258d8513a29752da8d3cd65fb2a7ecaf29f33c5317a54052b8 — 보존) · 기대목록 불변. 보관 6파일(sha 이동·복사 전후 동일 assert): 이동 `experiments/provenance/pre_unblinding_audit_v3.json` → `experiments/runs/v3_preaudit_v3/run1_FAIL/pre_unblinding_audit_v3.json` 65c5bfb2ca141a515d91e3ec51ecfe090bdd349941409515ff4c688810a0e1b8(124,817 B) · 이동 `experiments/runs/v3_preaudit_v3/audit_details_v3.json` → `experiments/runs/v3_preaudit_v3/run1_FAIL/audit_details_v3.json` d033df07dc6f6b28db40f45ccc0df0a1ba2de1e8cca01868e2a8a0a49ff6a1b6(44,842 B) · 이동 `experiments/runs/v3_preaudit_v3/run.log` → `experiments/runs/v3_preaudit_v3/run1_FAIL/run.log` cd941fe610066b0765dfd882eb93d67f8f5b526e0608ef5a72e0b6902d2b59ca(1,217 B) · 복사 `v3_Multimodal/src/pre_unblinding_audit_v3.py (1회차 f750f457…)` → `experiments/runs/v3_preaudit_v3/run1_FAIL/pre_unblinding_audit_v3_run1.py` f750f457e254fce0f285339b5f0f8dc16a65140b668c18572e8ed7f74fad121e(125,497 B) · 복사 `experiments/runs/v3_preaudit_v3/selftest_audit_v3.json` → `experiments/runs/v3_preaudit_v3/run1_FAIL/selftest_audit_v3_run1.json` 0206118188c544258d8513a29752da8d3cd65fb2a7ecaf29f33c5317a54052b8(5,144 B) · 이름 변경 `docs/119_pre_unblinding_audit_v3_report.md` → `docs/119_pre_unblinding_audit_v3_report_run1_FAIL.md` 59e213387d77cbb145dc4787ec7da4e7c45777c6cc87dc5d06a21ddb769006ba(19,030 B). `--stage run` 이 줄 전체 정규식으로 읽는 고정 마커:

     audit_script_r2 sha256: a5e19ba3f2ade25c7a893ed602343e70de1ad2242a6b04cb76c953b01bb9bcbd
     selftest_r2 sha256: d423a2b505d420a8842d276e2aebd810a845dc555f9bbdf38c27cb4c06b4ed8d
     expected_manifest_v3 sha256: cf513074e756572fc3f7283f291c5e3a6644701ba94caf02c7f58d817480e43c

82. **★ 개봉 전 전수 감사 v3 재실행 결과 (블록 BE — verdict · Z5 대조)**:

   - **① 결과**: `--stage run` 1회(2026-10-06 17:21:46 ~ 17:21:50 KST · `audited_at_kst` 2026-10-06 17:21:49.694 KST · 착수·종료 실저장소 게이트 16/16 True · 오라클 `unblinding_run.stat_summary` 출력 착수 = 종료 바이트 동일) → **verdict = PASS · 차단 0**. 기대 801 ↔ live 801 · 일치 801 · 누락 0 · 초과 0 · 크기 불일치 0 · sha 불일치 0 · 기록원 불일치 0 · checkpoint 3파일 투영 = 격자 · 열람 대장 25파일 223줄 · human_exposure true 0 · 형식 오류 0 · `OPEN sealed` 0 · **미대응 0** · 스키마·결속 재검 실패 0 · 누설 스캔 적중 0. 비차단 = Y4 `no_creation_hash` 8파일(첫 기준값 sha16 = 항목 80 ① 과 동일) · `rd_verbatim_absent`(항목 80 ⑤ 와 동일).

   - **② 1회차 대비(Z5 · 상세 `rerun_vs_run1`)**: 9키 JSON 7키(`access_log_lines`·`audit_version`·`frozen_118_sha256`·`report_path`·`sealed_counts`·`sealed_sha256`·`stat_fingerprints`) 1회차와 정렬 직렬화 **바이트 동일 7/7** · 상세 22섹션 **동일 22/22**(제외 = 지시서 Z5 목록 + 라벨 메타 `block`·`instruction` · `nonblocking` 은 access 관련만 제외) · 선언 변화 D1~D4 범위 안: D1 `spec_item` 71 · 일치 true · D2 1회차 이후 추가 대상 = 항목 80 L2599 1건 · D3 `doc45_line` 이동 k = 6 균일 · D4 파일 수 카운터만 상이. 입력 불변 하에 결과 불변이 확인됐다.

   - **③ 대응 규칙 (b) 적용 줄 목록**: 1줄 — 트리 `experiments/runs/v3_gin_stability` · 순번 4 · 시작 오프셋 975 · 길이 362 · 블록 AV · 근거 `docs/112_rqint_downstream_spec_report.md` L148(리포트 sha 일치 · 후보 1) · 인용 키 6(`actor`·`human_exposure`·`path`·`purpose`·`step`·`type`). 그 트리 5줄 = (a) 4(AU 3 · BA 1) + (b) 1(AV). 그 밖 24파일은 전부 (a) 또는 AO 기준선으로 대응(1회차와 같은 배분).

   - **④ 문면 정정**: 항목 80 ② (i)~(iii)(및 그 추가·관찰 2건)이 정본이다 — 본 항목은 새 정정을 두지 않는다(D2 의 항목 80 L2599 는 정정 문구 자체가 대상 키워드를 가진 것으로 새 정정 대상 아님).

   - **⑤ 해시·supersede**: `experiments/provenance/pre_unblinding_audit_v3.json` 6638e0e448db049d621d02dcba9cd3dd37eb436b71bd2e2690cf614b732558fe(124,817 B · 9키 · verdict PASS · supersedes 1회차 65c5bfb2ca141a515d91e3ec51ecfe090bdd349941409515ff4c688810a0e1b8 — 보관 `experiments/runs/v3_preaudit_v3/run1_FAIL/pre_unblinding_audit_v3.json`) · `experiments/runs/v3_preaudit_v3/audit_details_v3.json` 3ab7ab135ec19be50e6d4255984f5df57b75bd2c9ab46251bb9ae1c1d33f811d(50,350 B · supersedes d033df07dc6f6b28db40f45ccc0df0a1ba2de1e8cca01868e2a8a0a49ff6a1b6 — 보관 `experiments/runs/v3_preaudit_v3/run1_FAIL/audit_details_v3.json`) · `experiments/runs/v3_preaudit_v3/run.log` a1c0c19ed54ae604eba4eae0608c5aa7421286166658a8dafc2dcbb93c7188ad(1,292 B). 스크립트 r2 a5e19ba3f2ade25c7a893ed602343e70de1ad2242a6b04cb76c953b01bb9bcbd · selftest r2 d423a2b505d420a8842d276e2aebd810a845dc555f9bbdf38c27cb4c06b4ed8d · 기대목록 cf513074e756572fc3f7283f291c5e3a6644701ba94caf02c7f58d817480e43c(항목 81 마커와 동일). 리포트 `docs/119_pre_unblinding_audit_v3_report.md` 는 자기 sha 미기재. 실행·기록 = vscode-claude(runner · 지시서 `docs/119b` Phase B · cowork BE-A 검증 2026-10-06) · 본 항목 기록 2026-10-06 17:24:01 KST. 봉인 역직렬화 0(투영 3파일 키 화이트리스트 제외) · access.log 기록 0 · 값 출력 0 · 네트워크 0 · git 쓰기 0. 다음 = 지도교수 승인 → 120.

83. **★ 확증 결과 개봉 승인 접수·승인 기록 작성 (블록 BF — `docs/120` Phase A · 봉인 판독 0)**:

   - **① 승인 요청**: 2026-10-06 20:39:34 KST · <EMAIL> → 양진홍 교수님 <<EMAIL>> · 제목 「[DTI-ADR v3] 확증 결과 개봉(봉인 해제) 승인 요청드립니다」 · message_id `<GMAIL-MSGID>` · thread_id `<GMAIL-MSGID>` · 첨부 `DTI-ADR_v3_개봉결과_보고계획_20261006.docx`(`docs/118_unblinding_reporting_plan.md` 열람용 변환본 — 결속 대상은 `.md` 해시) · 본문 결속 7해시: v3_Multimodal/config/unblinding_plan_v1.json `d5aa594b630992fd10739573409a2008227db72a843f310b001b9ca24ce59764` · v3_Multimodal/src/unblinding_run.py `84f773596a01cf3fdc93334ca2f01af977d24e939a911be42f464b3f95cc3737` · v3_Multimodal/src/unblinding_independent_check.py `10075502901efbcc370edad527169dd8da5928a2abfd6bb799fc4d4a5700939e` · docs/118_unblinding_reporting_plan.md `e3b342e75cfee99a062d67b6cdfe16d3c614dad9b5b4c7333ab89ccee8203abb` · docs/118b_external_validation_plan.md `4f06d39e9aa827bd63a2ac28e6dbedbedec2430bbde10aaadd567c81c726f60e` · docs/119_pre_unblinding_audit_v3_report.md `0396a4e8c6177113cfc9db4ce027a57f679ac21c72385f3cb981020ca2406af5` · experiments/provenance/pre_unblinding_audit_v3.json `6638e0e448db049d621d02dcba9cd3dd37eb436b71bd2e2690cf614b732558fe`.

   - **② 승인 회신(축자 · 서명 블록 제외)**: 2026-10-06 20:55:11 KST · message_id `<GMAIL-MSGID>` · thread_id `<GMAIL-MSGID>` — 「네. 연우씨. / 메일 내용 확인하였고, "개봉 승인" 합니다. / <EXTERNAL-REVIEWER> 박사에게도 전달하겠습니다. / 양진홍 드림.」

   - **③ 승인 기록·G-gate**: `experiments/provenance/unblinding_approval.json` 5ff4c45a84285000dfadec308446e679a0ea725347b3065866094ea8dbd6292b(1,376 B · 키 6 = 계획 `approval_binding.required_fields` · `approved_hashes` 는 지시서 §0 표에서 옮겨 적은 뒤 디스크 sha 7/7 일치 assert · `recorded_at_kst` 2026-10-07 02:45:12.485 KST). `unblinding_run.gate(ROOT, {plan, launch_lines})` 건조 확인 = `[]`(launch_lines `{}` · `core`·`main`·`--stage run` 호출 0 · compute lock 획득 0) · `--stage status` = `{"output_exists": false}`. 감시 디렉터리 `experiments/runs/v3_unblind_watchdog/` 빈 디렉터리 생성.

   - **④ 영향**: 동결물 7종·계획 JSON·감사 산출물·래퍼 0바이트 수정 · 봉인 39/826/801/25 · 18키 · access 223 착수 = 종료 · access.log 기록 0 · 확증 값 미열람 · `unblinding_event.json` 부재 · `v3_unblinding*` 0.

   - **⑤ <EXTERNAL-REVIEWER> 박사 전달**: 교수님이 회신에서 전달 의사를 표명 · 실제 전달은 미확인(외부 검토자 회신은 개봉을 막지 않는다 — X2).

   - **⑥ 증거 경로 편차**: 지시서 증거 = cowork Gmail get_thread(2026-10-07). 러너도 Phase A 중 Gmail get_thread(PLAIN_TEXT · 읽기 전용) 1회로 두 메시지를 직접 재확인했다(발신자·시각 11:39:34Z/11:55:11Z · 본문 축자 · 7해시 전건 일치). 지시서 A-5 「네트워크 0」 대비 편차 — 승인 기록 작성이 1차 증거 미확인 상태로 차단돼 확인 목적에 한정. 쓰기·발송 0.

   - **⑦ 다음**: 사용자 터미널에서 감시 래퍼 본런(≈20~22 h · AC ≥ 90 W) → 완료 후 `/실행 120` = Phase B. 기록 = vscode-claude(runner · 지시서 `docs/120` Phase A) · 본 항목 기록 2026-10-07 02:47:13 KST.

84. **★ 확증 결과 개봉 실행 완료 (블록 BF — `docs/120` Phase B)**:

   - **① 실행 이력**: 감시 래퍼(`v3_Multimodal/src/unblinding_watchdog.py`) 사용자 터미널 기동 2026-10-07 13:11:46 KST(`watchdog_start`) → `power_wait` 1회(60.1 s · 「배터리 또는 어댑터 < 90W」) → `power_ok` 13:12:46 → launch 1 · 자식 pid 19688 13:15:26 KST → 러너 R1 13:15:31.481 KST(`launches.jsonl` launch 1) → 항목 38/38 `item_done` → R5 06:22:04.377 · R6 07:05:49.863 · R7 07:05:50.355 KST → 래퍼 `completed` exit_code 0 2026-10-08 07:06:37 KST. launch 1 · 재시작 0 · 재개 0 · rc 12/13 0 · `_staging/failure.json` 부재 · 폴백 0. wall(launch→completed) ≈ 17 h 51 m. 래퍼 이벤트 41줄(start 1 · power_wait 1 · power_ok 1 · launch 1 · child_started 1 · progress 19 · stall_suspect 17 · completed 1) — `stall_suspect` 17건은 「heartbeat 30분 이상 미갱신(기록만)」으로, 항목 단위 heartbeat 간격(≈1 h/항목)에 따른 기록이며 재시작·개입 0. 자식 stdout = `[G-IDLE A] PASS … load1=1.56 < 2.0` · LOCK 획득·해제 pid 19688 · `{"stage": "run", "published": true}` (`experiments/runs/v3_unblind_watchdog/child_stdout.log`).

   - **② 공개 이벤트**: `experiments/provenance/unblinding_event.json` 10287d9dc4750f8567fe80d89cb0d13daf866e742f5320b916fceaceebd31344(6,044 B · type `unblinding_publish` · ts 2026-10-08 07:05:50.351 KST · `approval_ref` = 승인 기록 sha 5ff4c45a84285000… 일치) · `experiments/runs/v3_unblinding/results/manifest_public.json` 2205e5b570d204606f659c22c93ae0ad749b77bc5222a82de803b53b424caa6d(5,840 B · 파일 39 · published_at 2026-10-08 07:05:50.350 KST · plan_sha256 = ①). 공개 39파일 sha 전건 일치 · `results_layout` 전 항목 존재 · results/ 여분 파일 0.

   - **③ 독립 검산·G1**: `results_full.json` `independent_check` = `{"all_match": true}`(X3). G1 = 공개 `results_full.json` C1 `delta_obs` == 공개 `holm8_result.json` `delta_rf`(정확 일치) · C1 `bootstrap` 5키(delta_obs·ci_bca·ci_percentile·ci_primary·boot_summary) == 공개 `d9_bca_result.json[rf]` 5/5 정확 일치(공개 파일 간 비교 · 재계산 0).

   - **④ 봉인 계수 전후**: 39/826/801/25 · access 223 → **39/831/801/30** · access **275**(계획 `expected_post_counts` 일치). 판독 트리 26개 각 +2(= launch 1 + 공개 1) · 신규 access.log 5 = 계획 `trees_without_access_log_at_118` · 판독 범위 밖 트리 증가 0 · 봉인 산출물 801 내용 sha = 감사 JSON `sealed_sha256` 801/801 일치(개봉이 봉인 원본을 바꾸지 않음). 승인 결속 7해시 · 동결물 31파일 · 승인 기록 sha 본런 전후 불변 · 플래그 6파일 무수정.

   - **⑤ 판정 요약(`results_full.json` `decisions` 축자 · 6키)**: `{"RQ2": {"alpha": 0.05, "ci_estimable": true, "ci_low": -0.01631979733530217, "cond1_ci_lower_gt0": false, "cond2_signflip_p_lt_alpha": false, "cond3_sesoi": false, "delta_obs": -0.006324167855457974, "rq": "RQ2 (M2b>M1b, primary)", "rule": "성공 ⟺ (1)&(2)&(3) 모두(IU). 방향성은 (1) CI 하한>0가 보장(D1).", "sesoi": 0.01, "signflip_p": 0.23347665233476653, "success": false}, "RQ3": {"M2b_vs_PFAM": {"ci_estimable": true, "ci_low": -0.017724908775914715, "cond1_ci_lower_gt0": false, "cond2_p_lt_alpha": false, "p": 0.286971302869713, "pass": false}, "M2b_vs_PID": {"ci_estimable": true, "ci_low": -0.026589781855748833, "cond1_ci_lower_gt0": false, "cond2_p_lt_alpha": true, "p": 0.0006999300069993001, "pass": false}, "p_raw": {"M2b-P-FAM": 0.057394260573942604, "M2b-P-ID": 9.999000099990002e-05}, "rq": "RQ3 (M2b>P-ID 및 M2b>P-FAM)", "rule": "성공 ⟺ 두 대비 각각 (1) CI 하한>0 & (2) p<α. co-primary 통제(max 금지).", "success": false}, "RQ4": {"family_constrained": {"p_emp": 0.9881011898810119, "pass": false}, "global": {"p_emp": 0.9881011898810119, "pass": false}, "p_raw": {"p_emp_family": 0.965034965034965, "p_emp_global": 0.21478521478521478, "p_slot": 0.965034965034965}, "rq": "RQ4 (M2b > 재배치 null)", "rule": "성공 ⟺ global·family-constrained 재배치 null 둘 다 p_emp<α.", "success": false}, "RQ_int": {"adjusted_p": 0.0013199868001319986, "alpha": 0.05, "p_raw": 0.00021999780002199978, "rule": "판1 Holm 조정 p < α (D7 · H3)", "success": true}, "C_CAP": {"ci_estimable": true, "ci_low": 0.016013085435127514, "cond1_ci_lower_gt0": true, "cond2_p_lt_alpha": true, "p": 9.999000099990002e-05, "pass": true}, "minimum_establishment": {"rule": "RQ2 ∧ (RQ3 ∨ C-CAP) ∧ RQ4 (H2 · 등록 §8)", "success": false}}`

   - **⑥ 편차·운영 사건**: (a) 착수 시 `power_wait` 60.1 s(래퍼 전원 게이트 정상 동작 · 기동 거부 후 자동 재확인). (b) `stall_suspect` 17건(기록만 · 개입 0). (c) heartbeat `item_start` S-pch(2026-10-08 01:38:16) load1 2.49 기록 — 진입 게이트가 아닌 heartbeat 기록값 · 실패·중단 0. (d) `first_look_log.json` +1행 미기입 — 기존 19행의 키 집합이 9종으로 갈려 따를 형식이 하나로 정해지지 않음(지시서 B-1-4 단서) → `docs/120_unblinding_run_report.md` §5 상신. (e) `decisions` 축자 출처 = 공개 `results_full.json` `decisions`(staging `decisions.json` 미열람). (f) 공개 후 `_staging/` 잔존(내용 미열람 · 삭제 0). 그 밖 편차 0.

   - **⑦ 다음**: 플래그 6파일(`unblinding_performed` false ×3 · `gin_start_still_blocked` true ×3) 갱신 여부 = 별도 결정(cowork 상신) · RQ8 외부 검증 실행(`docs/118b`) = 개봉 이후 별도 블록. 기록 = vscode-claude(runner · 지시서 `docs/120` Phase B) · 본 항목 기록 2026-10-08 10:17:21 KST.

85. **★ 개봉 후 상태 기록 — 플래그 6파일 원본 보존 + post_unblinding_status_v1 신설 · FLL (나) 확정 · 결과 보고 서신 (블록 BG — `docs/121`)**:

   - **① 결정(사용자 2026-10-08 · 축자)**: **Y1** 원본 6파일은 1바이트도 수정하지 않는다. 개봉 후 현재 상태는 새 파일 `v3_Multimodal/config/post_unblinding_status_v1.json` 한 곳에 기록하고, 6파일의 해당 필드를 «개봉 시점까지의 동결 값»으로 해석하도록 supersede 관계를 명시한다. 선례 = `v3_Multimodal/config/gin_start_supersede.json`(블록 AS · 플래그 0바이트 보존 + append-only supersession). **Y2** `gin_start_still_blocked: true` 3건은 true 유지 · 의미만 기록한다 — 「구(v1) 실행계약 경로의 착수 차단 플래그. GIN 은 `gin_start_supersede.json`(교수님 승인 2026-09-15 12:42 KST · 메시지 `<GMAIL-MSGID>`)에 따른 v2 계약으로 실행·완료됐다. v2 계약은 이 값이 true 인 것을 요구 조건으로 읽는다」. **Y3** `unblinding_performed: false` 3건은 «개봉 전 동결 시점의 값»으로 해석하고, 현재 사실 = `unblinding_performed: true`(근거 = `unblinding_event.json` sha)를 새 파일에 기록한다. **Y4** 블록 BF 편차 1(FLL +1행) = (나) 미기입 확정. 사람 노출 기록은 `unblinding_event.json` · 판독 26트리 access.log 공개 줄 · `docs/33` 항목 84 · `docs/45` §2 로 충분하다. **Y5** 결과 보고 메일(2026-10-08 10:53:02 KST)을 ledger `correspondence` 에 +1.

   - **② 상태 파일**: `v3_Multimodal/config/post_unblinding_status_v1.json` 6,837 B · 428a4f248b2de3774f52d8aec0ea2602b3d622a1b042e067a2c5d1cbcc712ea5 · 작성 2026-10-08 11:36:39 KST · 키 15(지시서 순서 그대로 · 추가 키 0) · `unblinding_performed` true(근거 `unblinding_event.json` 10287d9dc4750f85… · ts 2026-10-08 07:05:50.351 KST · `manifest_public.json` 2205e5b570d20460… · 승인 기록 5ff4c45a84285000…) · `gin_status.authority` = `gin_start_supersede.json` c061d033ae35bea3… · `superseded_flag_fields` 8원소(①·④ 각 2필드 + ②③⑤⑥ 각 1필드) · `is_authorization` false · `fll_decision` (나) 미기입. 값은 디스크 6파일 JSON 을 읽어 필드 전 출현이 기대 값과 일치함을 assert 후 기입. 자기 sha 미기입(이후 0바이트 불변).

   - **③ 6파일 불변 실측(착수·작성 직전·종료 3회 바이트·sha256 일치)**: ① `v3_Multimodal/config/rqint_procedure_decisions_v1.json` 22,062 B `16776f21df6ae29b…`(gin_start_still_blocked true · unblinding_performed false) · ② `v3_Multimodal/config/gin_seed_freeze.json` 4,637 B `10828447c6d33118…`(gin_start_still_blocked true) · ③ `v3_Multimodal/config/gin_inner_valid_freeze.json` 6,913 B `038599c3e1576022…`(gin_start_still_blocked true) · ④ `v3_Multimodal/config/post_interim_freeze_v1_0.status.json` 4,628 B `dbb00d540d7436e5…`(unblinding_performed false · gin_start_still_blocked true) · ⑤ `v3_Multimodal/config/gin_train_contract.json` 26,915 B `e50f972674e782f5…`(unblinding_performed false) · ⑥ `experiments/runs/v3_gin_start_authorization/manifest_t4_post_confirmatory.json` 8,660 B `a59ab54afd515085…`(unblinding_performed false). `gin_start_supersede.json` 6,359 B · 개봉 산출 3종 · 승인 결속 7해시(`docs/120` §0 표) 전건 착수=종료.

   - **④ 결과 보고 메일**: 2026-10-08 10:53:02 KST · <EMAIL> → 양진홍 교수님 <<EMAIL>> · 제목 「Re: [DTI-ADR v3] 확증 결과 개봉(봉인 해제) 승인 요청드립니다」 · message_id `<GMAIL-MSGID>` · thread_id `<GMAIL-MSGID>` · 첨부 `DTI-ADR_v3_개봉결과표_20261008.docx`(저장소 사본 `docs/DTI-ADR_v3_개봉결과표_20261008.docx` 13,310 B fca7c08ff9ec3e58… · 공개 `results/table_main.csv` 에서 cowork 생성 열람용 요약 · 값 반올림 표기) · 요지 = 개봉 실행·무결성 · 확증 판정 요약(RQ2·RQ3·RQ4 불성립 · C-CAP 통과 · RQ-int 성립 · 최소 성립 불성립) · 해석상 주의 3건 · 다음 계획 · <EXTERNAL-REVIEWER> 박사 공유 요청. 측정 = cowork Gmail get_thread 2026-10-08(러너 재측정 아님 · 네트워크 0).

   - **⑤ 영향**: 동결물 0바이트(6파일 · `gin_start_supersede.json` · 개봉 산출물) · 봉인 39/831/801/30 · access 275 착수=종료 불변(stat·이름·크기·개행 수만) · 봉인 판독 0 · `_staging/` 열람 0 · 계산 0 · 기존 코드 수정 0 · `first_look_log.json` 무수정(Y4) · git 쓰기 0 · 네트워크 0.

   - **⑥ 편차**: 없음. 기록 = vscode-claude(runner · 지시서 `docs/121`) · 본 항목 기록 2026-10-08 11:37:23 KST.

86. **개봉 결과 보고 초안 작성 · RF_tuned 약물 겹침 실측 (블록 BH — `docs/122` · 새 추론 계산 0)**:

   - **① 근거**: 개봉 결과 보고 규칙 정본 = `docs/121c_chatgpt_review10_triage.md` §1 표(41c99c9b162093af… · 사용자 Z1 일괄 승인 2026-10-08). Z2 순서(본 블록 → RQ8 → 원고 감사) · Z3 원고 감사 = 지도교수 최종 + ChatGPT 보조(→ 주장 대조표 사전 작성) · Z4 RF_tuned v1 분할 ↔ v3 확증 fold 약물 겹침 실측을 본 블록에 포함. 값 출처 = `experiments/runs/v3_unblinding/results/` 공개 파일(`results_full.json` 372cce5d1be9f377… · `table_main.csv` · `sealed_publish/*` 29 · `fig_*.json`)만.

   - **② 산출(신규 6파일 · 기존 파일 수정 0)**: `docs/122_results_filled.md` 78,416 B `165b7db3d65fc694…` · `docs/122_results_filled_fullprecision.csv` 322,464 B `e138d4f9460164cb…` · `docs/122_results_section_draft_en.md` 15,714 B `55bc125ca1de770a…` · `docs/122_claim_audit_table.md` 65,862 B `9b8ef53bae33fa81…` · `experiments/runs/v3_post_unblinding/rftuned_overlap.json` 5,176 B `b63c2b70359cb48e…` · `v3_Multimodal/src/post_unblinding_rftuned_overlap.py` 5,647 B `05ec6b8c211c5191…`. `docs/118_unblinding_reporting_plan.md` 원본 무수정(e3b342e75cfee99a… · 기입본은 머리·§3 이하 바이트 보존 assert).

   - **③ 겹침 실측(메타데이터만 · 학습·예측·라벨 판독 0 · `_sealed/` 접근 0)**: v1 분할(`data/processed/scaffold_split.json` 88369dba24449770…) = train 873 · valid 109 · test 110 (cid 1,092). v3 확증 folds.json 키 구조 = {cid(str): outer_fold(int 0..4)} · rep1 3c1a5d68bfcc6ddf… · rep2 786feeca045f6036… · rep3 9db08cf96298b47e…. 각 rep 에서 1,092 약물 전부가 test 로 정확히 1회 · 그중 v1 train+valid 982(train 873 · valid 109) · v1 test 110. fold별: rep1_seed201: f0 218(train 172 · valid 19 · test 27) / f1 218(train 168 · valid 26 · test 24) / f2 219(train 184 · valid 15 · test 20) / f3 218(train 185 · valid 18 · test 15) / f4 219(train 164 · valid 31 · test 24); rep2_seed202: f0 218(train 199 · valid 9 · test 10) / f1 218(train 172 · valid 23 · test 23) / f2 219(train 178 · valid 22 · test 19) / f3 218(train 159 · valid 32 · test 27) / f4 219(train 165 · valid 23 · test 31); rep3_seed203: f0 218(train 163 · valid 28 · test 27) / f1 218(train 172 · valid 20 · test 26) / f2 219(train 174 · valid 22 · test 23) / f3 218(train 172 · valid 26 · test 20) / f4 219(train 192 · valid 13 · test 14). fairtune 선택 = selected_by valid_macro_pr · search_budget 16 · best_config.yaml f411602e9a46a34c…(성능 값 미전재). 해석 고정문(121c §2-4) = 「RF_tuned 하이퍼파라미터는 v1 valid 분할 성능으로 선택됐고, 그 과정의 학습·선택에 쓰인 약물(train+valid)이 v3 확증 test fold 에 포함된다. 영향 방향은 RF_tuned 기준선에 유리 → ⑥ Δ(M2b − RF_tuned)를 보수적으로 만든다. ⑥ 판정(기각 0)에는 영향 없음.」.

   - **④ 자기 점검(독립 재파싱 · 초안↔대조표↔원천)**: 결과 절 문장 62 == 대조표 행 62 · 숫자 285 전부 출처 연결(미연결 0) · 반올림 불일치 0 · 금지 문형 grep 0 · 필수 한정어 누락 0 · 기입본 csv 1951셀 원천 재해석 불일치 0 · 기입본 머리·§3 이하 바이트 보존 true · §2 빈 칸 0 → PASS.

   - **⑤ 영향**: p·CI·Holm·판정 재계산 0 · 새 대비·부분집합·하위 꼬리 p 0 · 동결물·결과 파일·`post_unblinding_status_v1.json`·`docs/118` 0바이트 · 봉인 39/831/801/30 · access 275 착수=종료 불변(stat·이름·크기·개행 수만) · 봉인 판독 0 · `_staging/` 열람 0 · `first_look_log.json` 무수정 · git 쓰기 0 · `git status` 0 · 네트워크 0.

   - **⑥ 편차(리포트 `docs/122_results_draft_report.md` §5)**: (a) 121c #4 문면 「21.5%(global)」 는 p_emp(215/1,001)에 해당 — 재배치 중 관찰값 이상 비율은 214/1,000 = 21.4% 이므로 결과 절은 개수(965/1,000 · 214/1,000)와 비율 21.4%·p_emp 0.215 를 함께 적음 · 「exceeded by」 대신 정의(≥)대로 「equalled or exceeded by」. (b) `docs/118` §2-1 「판정」 칸·§2-6·§2-7 은 빈칸이 아니어서 원문을 지우지 않고 「→ 결과」 를 덧붙이거나 표 아래 「기입」 소절로 추가. (c) C4·C8 Δ 칸 = 미산출(사유) + T_obs 병기. (d) S-unit-sw 유효 재표본 수 = 별도 키 없음(미기록) · percentile 구간은 「추론 미사용」 표기로 공개. (e) SP-REP·SP-LATEFUSION 의 fold별 macro AP 는 공개 사본 참조로 두고 표 전재 안 함. 기록 = vscode-claude(runner · 지시서 `docs/122`) · 본 항목 기록 2026-10-08 15:21:09 KST.

87. **결과 절 초안 문장 4개 정정 (블록 BH′ — `docs/122b`)**:

   - **① 정정 4건(문장 ID 유지 · 문면은 지시서 `docs/122b` §2 축자)**:
     - **S06** 전: 「The signs of four RF contrasts were seen by one investigator on 2026-07-27, before unblinding; decisions taken after that date are listed against this disclosure in experiments/provenance/sign_disclosure_matrix.json, and blinding is not claimed for those decisions.」<br>후: 「Before unblinding, one investigator saw only the signs of the RF primary contrast Δ(M2b − M1b) in the three split repeats and in the consensus (four signs, all negative; 2026-07-27); decisions taken after that date are listed against this disclosure in experiments/provenance/sign_disclosure_matrix.json, and blinding is not claimed for those decisions.」
     - **S19** 전: 「This overlap favours the RF_tuned baseline and therefore makes Δ(M2b − RF_tuned) conservative; it does not affect the ⑥ decision (not rejected).」<br>후: 「This overlap would be expected to favour the RF_tuned baseline, which would make Δ(M2b − RF_tuned) conservative; its magnitude was not quantified, and it does not affect the ⑥ decision (not rejected).」
     - **S49** 전: 「In the M2b − M1b stratification (13 strata), the CI lower bound exceeded 0 in two structural bins (struct_q1: Δ = 0.0379, [0.0123, 0.0526]; struct_q2: Δ = 0.0293, [0.0065, 0.0501]), and the CI upper bound was below 0 in struct_q4 (Δ = −0.0191, [−0.0384, −0.0093]) and in the sequence stratum labelled unstable_stratum (Δ = −0.0736, [−0.1294, −0.0225]).」<br>후: 「In the M2b − M1b stratification (13 strata; raw estimates without multiplicity adjustment), the CI lower bound exceeded 0 in 2 strata and the CI upper bound was below 0 in 2 strata; all strata are reported in Supplementary Table [S-STRAT].」
     - **S62** 전: 「⑥: all v1 training and validation drugs used to tune RF_tuned also appear in the confirmatory test folds; the direction of this overlap favours RF_tuned (see [S18] and [S19]).」<br>후: 「⑥: all v1 training and validation drugs used to tune RF_tuned also appear in the confirmatory test folds; this overlap would be expected to favour RF_tuned (see [S18] and [S19]).」
     - 사유: S06 = 사실 오기(인지 대상은 «RF 대비 4개»가 아니라 같은 대비 Δ(M2b − M1b)의 반복 1·2·3 + consensus 부호 4건 — `experiments/provenance/sign_disclosure_matrix.json` rows 4행 · sign 전부 negative · runner_first_look 2026-07-27 → «all negative» 확인되어 유지) · S19·S62 = 겹침 영향 방향을 사실처럼 단정 → 추정으로 완화 · S49 = 다중성 보정 없는 13층 중 CI 이탈 층만 이름·수치 나열(선택적 강조) → 개수(2·2·13)만 본문 · 층 전수는 보충표(`docs/122_results_filled.md` §2-6 SP-STRAT 기입본).

   - **② cowork 오기 1건**: `docs/121c` #4 문면 「21.5%(global)」 → 21.4%(214/1,000 · p_emp 0.215 = 215/1,001). 블록 BH 러너 지적(항목 86 ⑥(a)) · cowork 확인 후 `docs/121c` §2-1 에 정정 줄 추가(cowork 수행 · 6f7cb683c93cab00…). 결과 절 [S14] 는 이미 21.4% 로 기재되어 수정 0.

   - **③ 산출 2종 전후**: `docs/122_results_section_draft_en.md` 15,714 B `55bc125ca1de770a…` → 15,735 B `f39c7d03d72cb44a…` · `docs/122_claim_audit_table.md` 65,862 B `9b8ef53bae33fa81…` → 65,090 B `a5b16276663702d3…`. 그 밖 초안 58문장·대조표 58행 바이트 불변(줄 단위 assert).

   - **④ 자기 점검 재실행(`bh_check.py` 사본 + 금지 정규식 2개 추가 `therefore makes .* conservative` · `signs of four rf contrasts` — 정정 전 초안에서 각 1건 적중 확인)**: 문장 62 == 행 62 · 숫자 275(S49 15 → 5) 전부 출처 연결(미연결 0) · 반올림 불일치 0 · 금지 문형 0 · 필수 한정어 누락 0 · csv 1951셀 불일치 0 · 기입본 바이트 보존 true · §2 빈 칸 0 → PASS. 대조표 자기 점검 표에 「122b 재실행」 열 추가.

   - **⑤ 영향**: 새 계산 0(S49 개수는 공개 사본 층 계수) · 다른 문장 수정 0 · 새 문장 0 · 결과 파일·봉인·동결물·`docs/122_results_filled.md`·`_fullprecision.csv` 0바이트 · 봉인 39/831/801/30 · access 275 착수=종료 불변 · git 쓰기 0 · `git status` 0 · 네트워크 0. 기록 = vscode-claude(runner · 지시서 `docs/122b`) · 본 항목 기록 2026-10-08 15:28:33 KST.

88. **결과 절 초안 문장 2개 추가 정정 (블록 BH″ — `docs/122c`)**:

   - **① 정정 2건(문장 ID 유지 · 문면은 지시서 `docs/122c` §2 축자)**:
     - **S06** 전: 「Before unblinding, one investigator saw only the signs of the RF primary contrast Δ(M2b − M1b) in the three split repeats and in the consensus (four signs, all negative; 2026-07-27); decisions taken after that date are listed against this disclosure in experiments/provenance/sign_disclosure_matrix.json, and blinding is not claimed for those decisions.」<br>후: 「Before unblinding, one investigator saw the signs of the RF primary contrast Δ(M2b − M1b) in the three split repeats and in the consensus (four signs, all negative; 2026-07-27); three of these signs (repeats 2 and 3 and the consensus), without effect sizes or p-values, were also present in a commit pushed to the public project repository on 2026-07-28. Decisions taken after 2026-07-27 are listed against these disclosures in experiments/provenance/sign_disclosure_matrix.json, and blinding is not claimed for those decisions.」
     - **S49** 전: 「In the M2b − M1b stratification (13 strata; raw estimates without multiplicity adjustment), the CI lower bound exceeded 0 in 2 strata and the CI upper bound was below 0 in 2 strata; all strata are reported in Supplementary Table [S-STRAT].」<br>후: 「In the M2b − M1b stratification (13 strata; raw estimates without multiplicity adjustment), a BCa interval was estimable in 12 strata (the remaining stratum contained 2 drugs); among these 12, the CI lower bound exceeded 0 in 2 strata and the CI upper bound was below 0 in 2 strata; all strata are reported in Supplementary Table [S-STRAT].」
     - 진위 assert 5건(원천 직접 · 전부 참): (i) `experiments/provenance/sign_disclosure_matrix.json` rows[0](반복1) `public_repository_pushed` route = `미공개` (ii) rows[1..3] 같은 route `when` = 2026-07-28 16:10:52 +0900 · `public_exposure_verification` n_scalar_sign_literals 3 · scalar_sign_key_paths [/repeats/2/sign, /repeats/3/sign, /consensus/sign] · in_pushed_commit true (iii) `experiments/runs/v3_confirm_rep23/block_C_summary.json` `_scope` 에 「AP·Δ 크기·p 없음」 (iv) 층화 결과 공개 사본에서 `ci_primary.status == not_estimable` 층 = `seq_stratum::unseen_ge90` 1개 · n_drugs 2 (v) 나머지 12층 중 CI 하한>0 = 2 · 상한<0 = 2.

   - **② 귀속 = cowork 지시서(`docs/122b`) 문면 결함(러너 수행 결함 아님)**: S06 은 블록 BH 원문부터 공개 저장소 push 경로(`bdb65c8` · 부호 3개 · 크기·p 없음)를 빠뜨려 노출 범위를 실제보다 작게 적었다 — 122b 정정 문면도 같은 누락을 이어받음. S49 는 13층 모두 CI 가 있는 것처럼 읽혔다.

   - **③ S49 not_estimable 사유**: `seq_stratum::unseen_ge90` = 약물 2 · 클러스터 2 → 클러스터 복원추출 재표본 Δ 가 소수 이산값뿐이고 관측값이 그 최솟값이라 bias-correction z0 가 퇴화(`ci_bca.status = bca_failed_z0_degenerate` → `ci_primary.status = not_estimable`). 시드 무관 구조적 불능 · 동결 SAP A1 은 percentile 대체 금지(`ci_percentile` 은 sensitivity 전용) → **재계산·percentile 승격 0**. S51(M2b − P-ID)의 「had no estimable CI」 와 같은 방식으로 맞춤(S51 수정 0).

   - **④ 산출 2종 전후**: `docs/122_results_section_draft_en.md` 15,735 B `f39c7d03d72cb44a…` → 16,011 B `6f7f2b92d6424088…` · `docs/122_claim_audit_table.md` 65,090 B `a5b16276663702d3…` → 68,187 B `a641c8be387e6766…`. 그 밖 초안 60문장·대조표 60행 바이트 불변(줄 단위 assert).

   - **⑤ 자기 점검 재실행(`bhp_check.py` 사본 + 금지 정규식 1개 추가 `saw only the signs` — 정정 전 초안에서 1건(S06) 적중 확인 + S49 CI 불능 층 재확인 추가)**: 문장 62 == 행 62 · 숫자 282(S06 1 → 5 · S49 5 → 8) 전부 출처 연결(미연결 0) · 반올림 불일치 0 · 금지 문형 0 · 필수 한정어 누락 0 · csv 1951셀 불일치 0 · 기입본 바이트 보존 true · §2 빈 칸 0 · 초안 문면 == 대조표 문면 62/62 → PASS. 대조표 자기 점검 표에 「122c 재실행」 열 추가.

   - **⑥ 영향**: 새 계산 0(S49 개수는 공개 사본 층 필드 계수) · 다른 문장 수정 0(S50·S51 포함) · 새 문장 0 · 결과 파일·봉인·동결물·`docs/122_results_filled.md`·`_fullprecision.csv` 0바이트 · 봉인 39/831/801/30 · access 275 착수=종료 불변 · git 쓰기 0 · `git status` 0 · 네트워크 0. 기록 = vscode-claude(runner · 지시서 `docs/122c`) · 본 항목 기록 2026-10-08 15:41:48 KST.

89. **RQ8 외부 라벨 행렬 구성(블록 BI E1 — `docs/123`) · 예측 판독 전**:

   - **① 규칙별 개수(118b §2 규칙 1~10 · `v3_Multimodal/src/rq8_external_validation.py --stage e1` · step2·step5 와 같은 식, 출처 필터만 교체)**:
     - **EU∪UK(주)**: 라벨 문서 3,895 · 부작용 행 158,847 → PMB 외 0 → PMB 158,847 → PT 126,473 → 단일성분 귀속 115,571 · (ingredient, PT) 양성 30,035 · ingredient 1,097 · 대표 CID 678 → 규칙 7(master_X) 672 [118b §2-4 정의(규칙 1·4·6·7) 681] · 370 PT 양성 쌍 14,144 · 평가 약물(규칙 9) 669 (370 PT 양성 0 제외 3) · 적격 PT 주(≥10·음성≥1) 273 / 민감도(≥1·음성≥1) 364
     - **EU**: 라벨 문서 1,021 · 부작용 행 76,869 → PMB 외 0 → PMB 76,869 → PT 61,297 → 단일성분 귀속 52,862 · (ingredient, PT) 양성 18,390 · ingredient 590 · 대표 CID 324 → 규칙 7(master_X) 322 [118b §2-4 정의(규칙 1·4·6·7) 327] · 370 PT 양성 쌍 7,234 · 평가 약물(규칙 9) 318 (370 PT 양성 0 제외 4) · 적격 PT 주(≥10·음성≥1) 205 / 민감도(≥1·음성≥1) 350
     - **UK**: 라벨 문서 2,874 · 부작용 행 81,978 → PMB 외 0 → PMB 81,978 → PT 65,176 → 단일성분 귀속 62,709 · (ingredient, PT) 양성 14,716 · ingredient 652 · 대표 CID 476 → 규칙 7(master_X) 472 [118b §2-4 정의(규칙 1·4·6·7) 478] · 370 PT 양성 쌍 8,854 · 평가 약물(규칙 9) 471 (370 PT 양성 0 제외 1) · 적격 PT 주(≥10·음성≥1) 208 / 민감도(≥1·음성≥1) 355

   - **② PMB 외 행 수**: EU∪UK 0 · EU 0 · UK 0 (118b §2 규칙 2 실측과 같음 · 버린 행 0).

   - **③ 평가 약물·적격 PT 수**: EU∪UK 669 · 273(주) / 364(민감도) — EU 318 · 205 / 350 — UK 471 · 208 / 355. R8-main 의 not_estimable 기준(적격 PT < 20 또는 평가 약물 < 100)에 걸리지 않음. 평가 약물 cid 목록·적격 PT 목록 = `e1_manifest.json` `sources.*.eval_drug_cids` · `eligible_pt_ge10` · `eligible_pt_ge1`.

   - **④ 커버리지 assert 정의(편차 판단 기록)**: 지시서 `docs/123` §3 문면 「규칙 7 이후 약물 수 = EU 327 · UK 478 · EU∪UK 681(118b §2-4 실측)」 ↔ 정본 118b §2-4 「규칙 1·4·6·7 까지 적용한 `master_X` 약물 수」. 규칙 1~7 전부(2 PMB · 3 PT 포함) 적용 수는 EU 322 · UK 472 · EU∪UK 672 로 기대값과 다르고, 118b §2-4 정의(라벨 문서 → 단일성분 → CID → master_X, 부작용 행 무관)로는 **327 · 478 · 681 정확 일치**(라벨 문서 1,021 · 2,874 · 부작용 행 76,869 · 81,978 도 118b 와 일치). 118b 우선(`docs/123` §0)에 따라 assert 를 118b §2-4 정의로 적용했고, 첫 실행은 규칙 1~7 정의로 assert 해 E1 산출 쓰기 전에 중단(디렉터리 미생성)한 뒤 재실행했다. 라벨 행렬·평가 약물·적격 PT 는 규칙 1~11 전부 적용본이며 assert 정의와 무관하게 동일하다. 차이 9·5·6 약물 = 해당 출처 단일성분 라벨 문서는 있으나 PMB·PT 부작용 행이 없는 약물.

   - **⑤ E1 산출 sha**: `labels_euuk.npz` 2444613658b0ee2a79a944a8c3c48b08a006287e9e85de3b4c8fde540baa2ce2 (y 53c5585d86b62d1b… · cid 8e9ec4511f9c8480… · pt ac53ff0b67eb4871…) · `labels_eu.npz` 646d21e456793c7b3260a087eb24ebf30696458925cf5c97a2ef4d36ae4ddcea (y 9739cf57649d35f5… · cid 6f6a69c6005a7c35… · pt ac53ff0b67eb4871…) · `labels_uk.npz` 013b909458c395d2f5b0505eee83b8b88ac70f534f4784df46621276a7fa0fe4 (y ecc3f7d97fa9b492… · cid d6bdb2c4d192c144… · pt ac53ff0b67eb4871…) · `e1_manifest.json` 6fb735fb3a58f51c303375d8b49f04a7ceee42ac4ffe3cca4002f7e587641dbd(63,838 B) · 러너 `rq8_external_validation.py` 7abd16207c49df6b40926c7d4ac58a688be28171b6380d19f19f22255e6f6134. 입력 12파일 sha = 118b §1-1·§1-2 표와 12/12 일치(`e1_manifest.json` `input_sha256`).

   - **⑥ `_sealed` open 0 증빙**: E1 프로세스에 `sys.addaudithook('open')` 가드(`_sealed` 경로 open 시 PermissionError + 계수) → `sealed_open_attempts` 0. 봉인 stat 지문(파일 내용 open 없이 경로·크기·mtime) E1 전 = 후 `1bf1605a9e0303ec…` · 39/831/801/30. 예측 8파일 판독 0 · access.log 기록 0(E2 에서 275 → 277 예정). 기록 = vscode-claude(runner · 지시서 `docs/123`) · E1 2026-10-08 16:06:12.233 KST ~ 2026-10-08 16:06:14.739 KST · 본 항목 기록 2026-10-08 16:07:07 KST.

90. **RQ8 외부 검증 결과(블록 BI E2 — `docs/123`)**:

   - **① 6행 표(118b §3 · `experiments/runs/v3_rq8_external/results_rq8.json`)**:
     - **R8-main**(EU∪UK · RF · pos≥10 & neg≥1): 평가 약물 669 · 적격 PT 273 · AP(M1b) 0.145786 · AP(M2b) 0.142693 · Δ -0.003093 · CI(BCa) [-0.012242, 0.002849] estimable · undefined-AP 0/0
     - **R8-eu**(EU · RF · pos≥10 & neg≥1): 평가 약물 318 · 적격 PT 205 · AP(M1b) 0.178962 · AP(M2b) 0.179863 · Δ 0.000901 · CI(BCa) [-0.013842, 0.010360] estimable · undefined-AP 0/0
     - **R8-uk**(UK · RF · pos≥10 & neg≥1): 평가 약물 471 · 적격 PT 208 · AP(M1b) 0.155646 · AP(M2b) 0.150790 · Δ -0.004856 · CI(BCa) [-0.014844, 0.002911] estimable · undefined-AP 0/0
     - **R8-pt1**(EU∪UK · RF · pos≥1 & neg≥1): 평가 약물 669 · 적격 PT 364 · AP(M1b) 0.127952 · AP(M2b) 0.120679 · Δ -0.007273 · CI(BCa) [-0.016856, -0.001032] estimable · undefined-AP 0/0
     - **R8-gin**(EU∪UK · GIN · ≥10): 평가 약물 669 · 적격 PT 273 · Δ_GIN(시드 평균) 0.007039 (seed42 0.005398 · seed1 0.009297 · seed2 0.006420) · CI 미산출
     - **R8-int**(US(master_Y) · RF · pos≥10 & neg≥1): 평가 약물 669 · 적격 PT 296 · AP(M1b) 0.172128 · AP(M2b) 0.167191 · Δ -0.004936 · CI(BCa) [-0.017644, 0.003974] estimable · undefined-AP 0/0
     - 라벨 일치(R8-main 평가 약물 × 370 PT): 양쪽 양성 5,381 · 외부에만 8,763 · 내부에만 9,361 · Jaccard 0.2289.

   - **② R8-main 판정(118b §4)**: **방향 재현** — 기준 부호 = 내부 ① Δ(M2b − M1b) consensus 점추정 −0.006324167855457974(negative · `results_full.json` C1) · Δ_ext 부호 negative · 적격 PT 273 ≥ 20 · 평가 약물 669 ≥ 100. CI 0 포함 여부 미사용 · 다른 행으로 대체 0 · p 미계산 · tier-3 · 비판정.

   - **③ 독립 검산(`rq8_independent_check.py` · 별도 프로세스 · import = __future__, argparse, hashlib, json, numpy, os, pandas, sklearn, sys · 금지 import 0(AST))**: 라벨 y·cid·pt 바이트 동일 True/True/True · R8-main |ΔAP(M1b)| 0 · |ΔAP(M2b)| 0 · |ΔΔ| 0 (≤ 1e-12) · 판정 범주 일치 True → all_match True.

   - **④ 판독 기록·봉인**: E2 시작 2026-10-08 16:07:56.183 KST 에 `v3_consensus_rep123/_sealed/access.log` · `v3_gin_confirm_consensus_rep123/_sealed/access.log` 각 1줄 append(기존 줄 불변 · 말미 개행) → access 275 → 277. 예측 8파일 sha = `pre_unblinding_audit_v3.json` `sealed_sha256` 8/8 일치(판독 전 · 종료 시 재확인). 봉인 데이터 801 파일 sha 종료 시 감사 기대값 대조 불일치 0/801. 봉인 39/831/801/30.

   - **⑤ R8-gin CI 미산출 해석**: 118b §1-3 「집계는 118 계획 JSON 의 GIN ① 대응 항목과 같은 규칙」 → `unblinding_plan_v1.json` `S-GIN`(CI 없이 방향만 보고 · `confirmatory_gin_consensus.py` cell_3 = 시드별 Δ_t 의 평균, metric-then-average). 118b §3 「같은 절차로 산출하는 행」 문면은 CI 산출을 6행 공통으로 읽힐 여지가 있으나, GIN 은 학습시드 3개 consensus 를 시드 평균하는 집계라 RF 용 paired bootstrap 을 그대로 적용하면 새 절차 신설이 된다 — 이 처리(CI 미산출 · 시드별 Δ_t 3개 병기)는 cowork 해석(`docs/123` §4-3)이며 여기 그대로 기록한다.

   - **⑥ 118b §4 「공개 사실(맹검 한계)」 축자**:

     - **공개 사실(맹검 한계)**: 내부 ① 부호는 2026-07-27 최초 조회 이후 연구자가 알고 있다(`experiments/provenance/sign_disclosure_matrix.json`). 본 계획의 설계 선택(R8-1~R8-3 · 적격 기준 · not_estimable 기준)은 그 이후에 정해졌으나 **외부 라벨 쪽 PT 별 분포와 모든 예측값을 보지 않은 상태**에서 정했다. 이 사실을 보고서에 축자 기재한다.

   - **⑦ 118b §6 고정 문장 축자**:

     - 「RQ8(tier-3)은 사전등록 §12 의 두 선택지 중 DailyMed→EMA/EMC 라벨 출처 이식성으로 수행하였다. 이후 OnSIDES 데이터 release 가 없어 temporal 선택지는 수행할 수 없었다. 평가는 내부 1,092 약물 중 EU 또는 UK 단일성분 라벨이 있는 약물에서, 내부 consensus OOF 예측을 고정한 채 정답만 외부 라벨로 바꾸어 수행하였으며, 새 분자 일반화나 독립 표본 재현을 뜻하지 않는다.」

   - **⑧ 산출 sha**: `results_rq8.json` 3d18a95db167ed2305e5627ee77d4519547019c6eca0d1a263ae09a08d1a69c5 · `results_rq8_table.md` 836d81f9926c60f3784c44a53ba156468d068f155bc160cbe92d8997f88451ea · `independent_check.json` 4ecf4acc30d7683f96ea0db6dc47666ffc8b967af15b1f9730c4b9d5add7148b · 러너 `rq8_external_validation.py` 7abd16207c49df6b40926c7d4ac58a688be28171b6380d19f19f22255e6f6134 · 검산기 `rq8_independent_check.py` 008a4604ec4b031c666aaa60b1159ce5c96d66f0a281a1e5e4240cc2a2cbedd0. bootstrap 2026-10-08 16:07:58.473 KST ~ 2026-10-08 16:53:12.429 KST. 새 학습 0 · 봉인 데이터 쓰기 0 · git 쓰기 0 · 네트워크 0. 기록 = vscode-claude(runner · 지시서 `docs/123`) · 본 항목 기록 2026-10-08 16:53:29 KST.

91. **결과 절 초안에 RQ8 반영(블록 BJ — `docs/124` · 수행 = 블록 BJ′ `docs/124b` 델타)**:

   - **① 추가 문장 S63~S72(문면 = `docs/124` §2-1 축자 · S72 만 `docs/124b` 대체 1 축자)** — 새 절 `## 3.5 External label-source transportability (RQ8, tier-3)` 을 S58 뒤·표 1 앞에, S72 를 표 주석 S62 뒤에 삽입:
     - **S63** 「RQ8 (tier-3; not part of the minimum establishment condition, without multiplicity adjustment and without p-values) was carried out as DailyMed → EMA/EMC label-source transportability; the temporal option was not available because no OnSIDES data release later than v3.1.1 existed.」
     - **S64** 「The consensus OOF predictions were kept fixed and only the reference labels were replaced by EU and UK single-ingredient label documents for drugs already in the internal set; this is neither an assessment on new molecules nor an independent-sample replication, and absolute AP values are not compared with the internal analysis.」
     - **S65** 「The RQ8 design choices were frozen on 2026-10-04, after the sign of the internal primary contrast ① was known (see [S06]) but before any per-PT distribution of the external labels or any prediction was examined.」
     - **S66** 「With EU ∪ UK labels (669 drugs; 273 PTs with at least 10 positives), Δ(M2b − M1b) was −0.0031 (95% BCa CI [−0.0122, 0.0028]); its sign matched the negative sign of the internal contrast ①, so the pre-specified RQ8 category is "direction reproduced".」
     - **S67** 「The RQ8 rule uses the sign of Δ only; the CI in [S66] includes 0 and was not used for the category.」
     - **S68** 「In descriptive rows, Δ was 0.0009 ([−0.0138, 0.0104]) with EU labels only (318 drugs; 205 PTs), −0.0049 ([−0.0148, 0.0029]) with UK labels only (471 drugs; 208 PTs), and −0.0073 ([−0.0169, −0.0010]) with EU ∪ UK labels when PTs with at least 1 positive were eligible (364 PTs).」
     - **S69** 「For GIN, the mean over training seeds 42, 1 and 2 of Δ(M2b − M1b) with EU ∪ UK labels was 0.0070 (per seed 0.0054, 0.0093 and 0.0064); no CI was computed, following the pre-specified descriptive GIN rule.」
     - **S70** 「On the same 669 drugs with the internal (DailyMed) labels, Δ was −0.0049 ([−0.0176, 0.0040]; 296 PTs).」
     - **S71** 「Over these 669 drugs and 370 PTs, 5,381 drug–PT positives were shared by the external and internal labels, 8,763 were external-only and 9,361 internal-only (Jaccard 0.2289).」
     - **S72** 「In Table 3, only R8-main carries the pre-specified RQ8 category; the other rows are descriptive, and the eligible-PT rule (at least 10 positives and at least 1 negative among the evaluated drugs; at least 1 positive and at least 1 negative for R8-pt1) was applied separately to each row's labels.」

   - **② 표 3(`docs/124` §2-2 축자 · 표 2 블록 뒤·`## Table notes` 앞)**:

     ## Table 3. RQ8 external label-source transportability (tier-3; Δ = M2b − M1b on fixed consensus OOF predictions)

     | ID | Reference labels | Model | Drugs | Eligible PTs | Δ | 95% BCa CI | Role |
     |---|---|---|---|---|---|---|---|
     | R8-main | EU ∪ UK | RF | 669 | 273 | −0.0031 | [−0.0122, 0.0028] | RQ8 category: direction reproduced |
     | R8-eu | EU | RF | 318 | 205 | 0.0009 | [−0.0138, 0.0104] | Descriptive |
     | R8-uk | UK | RF | 471 | 208 | −0.0049 | [−0.0148, 0.0029] | Descriptive |
     | R8-pt1 | EU ∪ UK (PTs ≥ 1 positive) | RF | 669 | 364 | −0.0073 | [−0.0169, −0.0010] | Sensitivity, descriptive |
     | R8-gin | EU ∪ UK | GIN (mean of 3 seeds) | 669 | 273 | 0.0070 | — | Descriptive (no CI) |
     | R8-int | DailyMed (internal) | RF | 669 | 296 | −0.0049 | [−0.0176, 0.0040] | Baseline on the same drugs |

     No p-values were computed. Per-arm AP values are in Supplementary Table [S-RQ8]. Source: `experiments/runs/v3_rq8_external/results_rq8.json` (`rows`, `verdict_R8_main`, `label_concordance`).

   - **③ 산출 3종 전후**: `docs/122_results_section_draft_en.md` `6f7f2b92d6424088…` → 19,447 B `044b8e4f30acf006…` · `docs/122_claim_audit_table.md` `a641c8be387e6766…` → 82,242 B `e032a4e5affe02e8…` · `docs/124_table3_fullprecision.csv`(신규) 3,064 B `1469176daf3696b0…`. 기존 S01~S62 · 표 1·2 · 머리말 바이트 불변(줄 단위 부분수열 assert) · 대조표 S01~S62 행 바이트 불변(62/62) · `docs/122_results_filled.md`·`_fullprecision.csv` 0바이트.

   - **④ 자기 점검(`bhc_check.py` 사본 확장 = `bj_check.py`)**: 문장 72 == 행 72 · 숫자 330(+48) 전부 출처 연결(미연결 0) · 반올림 불일치 0 · 금지 문형 0 · 필수 한정어 누락 0 · 기존 csv 1951셀 불일치 0 · 표 3 csv 28셀 → `results_rq8.json` 재해석 불일치 0 · 초안 문면 == 대조표 문면 72/72 · 기존 S01~S62 바이트 불변 62/62 · 금지 정규식 3개 추가(`validat` · `generaliz` · `transportab(le|ility) (was|is) (shown|demonstrated|established)`) 새 10문장 0건 · 합성 문자열 3/3 적중 → PASS. 숫자 토큰 규칙(124b 추가 1): 행 ID(`R8-main`·`R8-eu`·`R8-uk`·`R8-pt1`·`R8-gin`·`R8-int`)와 절 번호(`3.5`)는 식별자로 숫자 토큰에서 제외 · 그 밖 숫자(표 번호 `Table 3` 의 `3` 포함)는 전부 출처 연결. 124b 대체 1 assert: R8 6행 `eligible_rule` 재판독 = R8-pt1 `pos≥1 & neg≥1` · 나머지 5행 `pos≥10 & neg≥1` → S72 문면 일치.

   - **⑤ 블록 BI 편차 (a)(커버리지 assert 정의) cowork 수용**: 빠진 약물은 PMB·PT 행이 없어 규칙 9 에서 어차피 제외 → 결과 불변 · cowork 독립 재계산 일치(`docs/124` §0).

   - **⑥ `docs/124` 중단 2회**: `docs/124` 는 2회 호출(2026-10-09 11:48 · 13:50 KST) 모두 쓰기 0 으로 중단 — S72 적격 규칙 서술이 R8-pt1 에서 거짓(cowork 지시서 문면 결함). 본 블록(`docs/124b`)에서 S72 만 정정해 수행. 1차 리포트 `docs/124_results_rq8_insert_report.md` sha256 `770d0a791f801e0f12b34313605d74f95466ec463cd46fc9e108a8207489f10a` · 2차 리포트 `docs/124_results_rq8_insert_report2.md` sha256 `114ca0dcd7bd7c8b0c8bdb698527e0de8b76d2ebc79fe6cf0129720dab47641b` · `docs/124` 지시서 sha256 `d49650e97c5af951fbc01875206551480a3a7b8c04f4e426770c1360894932a0`(미수정).

   - **⑦ 영향**: 새 계산 0(공개 산출 `results_rq8.json` 판독만 · 재부트스트랩·p 0) · 기존 문장 수정 0 · AP 절대값 문장 0 · 봉인 판독 0 · 봉인 39/831/801/30 · access 277 착수=종료 불변 · git 쓰기 0 · 네트워크 0. 기록 = vscode-claude(runner · 지시서 `docs/124`+`docs/124b`) · 본 항목 기록 2026-10-09 13:57:58 KST.

92. **결과 절 감사(Z3 보조) 반영(블록 BK — `docs/125c`)**:

   - **① 정정 15건(문면 = `docs/125c` §2 축자 · 근거 = `docs/125b` §1 판정 #1~#13 · 회신 원문 `docs/125a`)**:
     - **S01** 전 「All inferential results below are conditional on the fixed consensus out-of-fold (OOF) predictions: retraining variability enters only through 3 split repeats for RF (training random_state 42 fixed) and 3 split repeats × 3 training seeds for GIN, and no generalization to new samples is claimed.」<br>→ 후 「Unless otherwise indicated, inference is conditional on the fixed consensus OOF predictions, which combine 3 split repeats for RF (training random_state 42 fixed) and 3 split repeats × 3 training seeds for GIN; the resampling procedures do not retrain the models or estimate uncertainty from new training samples, and no generalization to new samples is claimed. RQ4 instead uses the fixed rep1 OOF predictions.」
     - **S04** 전 「Within each bootstrap replicate, PTs with zero test positives were excluded from that replicate's macro AP, while the eligible PT set itself remained fixed at 370 PTs.」<br>→ 후 「In the internal analyses, the eligible PT set was fixed at 370 PTs; PTs with no positives in a bootstrap replicate were excluded from that replicate's macro AP. In RQ8, eligibility was fixed separately for each row before resampling.」
     - **S09** 전 「Under the frozen three-category classification (Positive/Equivalent/Inconclusive, with no inferiority category), the pre-registered decision was Inconclusive: the 95% BCa interval [−0.0163, 0.0005] excluded gains ≥ 0.01 but included losses larger than −0.01.」<br>→ 후 「Under the frozen three-category classification (Positive/Equivalent/Inconclusive, with no inferiority category), the label was Inconclusive: the 95% BCa interval [−0.0163, 0.0005] had an upper bound below 0.01 and included negative differences below −0.01. These interval features do not constitute a separate non-superiority or inferiority decision.」
     - **S19** 전 「This overlap would be expected to favour the RF_tuned baseline, which would make Δ(M2b − RF_tuned) conservative; its magnitude was not quantified, and it does not affect the ⑥ decision (not rejected).」<br>→ 후 「The overlap may favour RF_tuned, but its effect on the contrast and on inference was not quantified; under the frozen analysis, ⑥ was not rejected.」
     - **S31** 전 「For M1 − M0, Δ = 0.0030 (95% BCa CI [0.0011, 0.0050]; sign-flip p = 0.0001 with c = 0; Equivalent).」<br>→ 후 「Except for the per-PT BH-FDR analysis, the remaining secondary and sensitivity results in this section are reported without multiplicity adjustment and are not used for confirmatory decisions. For M1 − M0, Δ = 0.0030 (95% BCa CI [0.0011, 0.0050]; unadjusted sign-flip p = 0.0001 with c = 0; frozen label: Equivalent).」
     - **S39** 전 「With size-weighted resampling, the BCa interval was not estimable (recorded status bca_failed_z0_degenerate; B = 10,000); the number of valid replicates is not recorded as a separate key, and no percentile substitute was used for inference.」<br>→ 후 「With size-weighted resampling, the BCa interval was not estimable because the bias-correction proportion reached a boundary (status bca_failed_z0_degenerate; B = 10,000); the number of valid replicates was not recorded separately, and no percentile substitute was used for inference.」
     - **S40** 전 「The percentile interval recorded for sensitivity reporting only was [0.0054, 0.0102].」<br>→ 후 「In this size-weighted sensitivity analysis, the observed Δ remained −0.0063, while the percentile interval was [0.0054, 0.0102]; the BCa interval was not estimable, and the percentile interval was reported descriptively without entering any success decision.」
     - **S55** 전 「Of these 5 seeds, 3 coincide with the confirmatory GIN seeds; the numbers of evaluable PTs per unit were 355, 349 and 361; drug overlap between units is not reported in the published results.」<br>→ 후 「Of these 5 seeds, 3 coincide with the confirmatory GIN seeds; the numbers of evaluable PTs per unit were 355, 349 and 361; the three units (219, 218 and 218 test drugs) shared 40, 47 and 40 drugs pairwise (rep1 fold4 with rep2 fold1, rep1 fold4 with rep3 fold0, and rep2 fold1 with rep3 fold0), so these selected cells should not be treated as independent replications.」
     - **S59** 전 「Decisions use the frozen three-category classification (Positive: CI lower bound > 0 and |Δ| ≥ 0.01; Equivalent: CI within [−0.01, 0.01]; otherwise Inconclusive), which has no inferiority category.」<br>→ 후 「The frozen three-category labels are assigned separately from the RQ-specific success decisions: Positive requires a CI lower bound > 0 and ∣Δ∣ ≥ 0.01; Equivalent requires the CI to lie within [−0.01, 0.01]; otherwise the label is Inconclusive. This classification has no inferiority category.」
     - **S61** 전 「p = 0.0001 denotes c = 0, the minimum attainable value 1/10,001 with B = 10,000; ⑧ uses B = 100,000 and ④ uses B = 1,000 per null, with Monte Carlo SE 0.0058 (family) and 0.0130 (global).」<br>→ 후 「For the tests with B = 10,000, p reported as 0.0001 here denotes c = 0 and the minimum attainable value 1/10,001; this interpretation does not apply to rounded p-values from procedures with different B. RQ-int (⑧) uses B = 100,000, and RQ4 (④) uses B = 1,000 per null, with Monte Carlo SE 0.0058 (family) and 0.0130 (global).」
     - **S62** 전 「⑥: all v1 training and validation drugs used to tune RF_tuned also appear in the confirmatory test folds; this overlap would be expected to favour RF_tuned (see [S18] and [S19]).」<br>→ 후 「⑥: all v1 training and validation drugs used during RF_tuned hyperparameter selection also appear in the confirmatory test folds; this creates potential selection optimism, whose effect was not quantified (see [S18] and [S19]).」
     - **S65** 전 「The RQ8 design choices were frozen on 2026-10-04, after the sign of the internal primary contrast ① was known (see [S06]) but before any per-PT distribution of the external labels or any prediction was examined.」<br>→ 후 「The RQ8 design choices were frozen on 2026-10-04, after the sign of the internal primary contrast ① was known (see [S06]) but before the external-label PT distributions or the prediction values were examined for this evaluation.」
     - **S68** 전 「In descriptive rows, Δ was 0.0009 ([−0.0138, 0.0104]) with EU labels only (318 drugs; 205 PTs), −0.0049 ([−0.0148, 0.0029]) with UK labels only (471 drugs; 208 PTs), and −0.0073 ([−0.0169, −0.0010]) with EU ∪ UK labels when PTs with at least 1 positive were eligible (364 PTs).」<br>→ 후 「In descriptive rows, Δ was 0.0009 ([−0.0138, 0.0104]) with EU labels only (318 drugs; 205 PTs), opposite in sign to R8-main; it was −0.0049 ([−0.0148, 0.0029]) with UK labels only (471 drugs; 208 PTs), and −0.0073 ([−0.0169, −0.0010]) with EU ∪ UK labels when PTs with at least 1 positive were eligible (364 PTs). These rows do not determine the RQ8 category.」
     - **S69** 전 「For GIN, the mean over training seeds 42, 1 and 2 of Δ(M2b − M1b) with EU ∪ UK labels was 0.0070 (per seed 0.0054, 0.0093 and 0.0064); no CI was computed, following the pre-specified descriptive GIN rule.」<br>→ 후 「For GIN, the mean over training seeds 42, 1 and 2 of Δ(M2b − M1b) with EU ∪ UK labels was 0.0070 (per seed 0.0054, 0.0093 and 0.0064), opposite in sign to the RF R8-main estimate; no CI was computed under the pre-specified descriptive GIN rule, and this result is not a test of a GIN-specific gain.」
     - **S70** 전 「On the same 669 drugs with the internal (DailyMed) labels, Δ was −0.0049 ([−0.0176, 0.0040]; 296 PTs).」<br>→ 후 「On the same 669 drugs with the internal (DailyMed) labels, Δ was −0.0049 ([−0.0176, 0.0040]; 296 PTs); the drugs were held fixed, while the eligible PT set remained label-source dependent.」

   - **② 추가 3건(`docs/125c` §3 축자 · S73·S74 = S64 뒤 · S75 = S65 뒤 · 판정 #18~#20)**:
     - **S73** 「Drug–PT pairs absent from the source labels were coded as negative under the observed-label definition, and differences in documentation practices between EU and UK labels were not controlled.」
     - **S74** 「Evaluation was restricted to drugs in the internal set with at least one external positive label within the fixed internal PT panel; drugs with no such positive label were excluded.」
     - **S75** 「The RQ8 plan was frozen before the full internal results were released; external PT-level label processing and external-label scoring followed that release, and detailed access and execution times are given in the transparency record.」

   - **③ 표 각주 변경(표 셀 값 불변 · 판정 #14~#17)**: 표 1 제목 → 「Confirmatory and decision contrasts and test statistics」 · 표 1 헤더 1칸 「Sign-flip p (raw)」 → 「Raw p (procedure-specific)」(C4 재배치 상측 · C8 공유-교환 혼재 해소) · † 주석 「p = 0.0001 = 1/10,001 (c = 0).」 → 「p reported as 0.0001 is the rounded value of 1/10,001 (c = 0, B = 10,000).」(줄 나머지 바이트 불변) · 표 1 아래 새 주석 2문단(대비·p 절차 구분 / RQ 성공 판정 vs 3분 라벨) · 표 2 주석 1줄(기각 열 의미 · D14 마지막 열 범위) · 표 3 주석 1줄(R8-main 만 판정 · 기타 기술 · 다중성 무보정 · 같은 약물 = 독립 재현 아님 · GIN Δ = 시드별 차이 평균).

   - **④ S55 메타데이터 계수(예측 판독 0 · 봉인 판독 0)**: 대표 unit = `ss15_result.json#/cells` 키 → `rep1|fold4` · `rep2|fold1` · `rep3|fold0` · test 집합 크기 219 · 218 · 218 · 쌍별 교집합 rep1|fold4 ∩ rep2|fold1 = 40 · rep1|fold4 ∩ rep3|fold0 = 47 · rep2|fold1 ∩ rep3|fold0 = 40 · 3중 교집합 9 → cowork 사전 계수(219/218/218 · 40/47/40 · 9)와 **정확히 일치**. 기존 S55 의 PT 수 355·349·361 은 같은 unit 순서(대조표 출처 `cells/rep1|fold4|seed42` · `rep2|fold1|seed42` · `rep3|fold0|seed42` `n_eval`) 확인. 입력 sha: `experiments/runs/v3_unblinding/results/sealed_publish/experiments__runs__v3_stability_ss15___sealed__ss15_result.json` `105af61769107e69…` · `data/processed/splits/confirmatory/rep1_seed201/folds.json` `3c1a5d68bfcc6ddf…` · `data/processed/splits/confirmatory/rep2_seed202/folds.json` `786feeca045f6036…` · `data/processed/splits/confirmatory/rep3_seed203/folds.json` `9db08cf96298b47e…`. 산출 `docs/125c_s6_unit_overlap.json` = 대조표 S55 출처로 연결. 동결 보고 의무(`reporting_text.md` s6_text 「unit 간 약물 중복 수」) 이행.

   - **⑤ 121c #6 「유효 재표본 수 기록」 미충족**: size-weighted 재표본(`results_full.json#/items/S-unit-sw/bootstrap`)에 `n_valid` 키가 없음(조회 시 null · `bca_diagnostics` 에도 부재 — 트리아지 문면 「`n_valid` null」 과 실질 동일) · 개봉 후 재실행은 새 계산이라 금지 → **복구 불가**. S39 는 「the number of valid replicates was not recorded separately」 로 미기록 사실을 서술(보고 요구 미충족을 본 항목에 기록).

   - **⑥ 트리아지 C 2건 이관**: (#22) 미수행 사전등록 항목 연결 문장 → 방법 절/보충 이탈표(정본 = 본 문서 항목 78) · (#23) `[S-STRAT]`·`[S-RQ8]` 자리표시자 · F-NULL·F-D13 그림 참조 번호 → 원고 통합 단계에서 확정. 본 블록 미수행.

   - **⑦ 산출 sha · 자기 점검**: `docs/122_results_section_draft_en.md` `044b8e4f30acf006…` → 22,985 B `3814919652d5da01…` · `docs/122_claim_audit_table.md` `e032a4e5affe02e8…` → 91,211 B `54ed83be16a53696…` · `docs/125c_s6_unit_overlap.json`(신규) 1,649 B `ded447632906215d…`. 자기 점검(`bk_check.py` = `bj_check.py` 사본 확장): 문장 75 == 행 75 · 숫자 337(+7: S40 +1 · S55 +6) 전부 출처 연결(미연결 0) · 반올림 불일치 0 · 금지 문형 0(RQ8 정규식 3개 S63~S75 적용 0 · S01 「no generalization」 은 적용 범위 밖 유지) · 필수 한정어 누락 0 · csv 2종(기존 1951셀 · 표 3 28셀) 불일치 0 · 초안 == 대조표 문면 75/75 · 정정·추가 대상 외 57문장·행 바이트 불변 57/57 · 재생성·추가 행 18/18 · S55 재계수 일치 → **PASS**. 대조표 자기 점검 표에 «125c 재실행» 열 추가. S59 의 `∣Δ∣` = U+2223(지시서 축자 · 기존 초안 S59 는 ASCII `|` 였음 — 리포트 §5 기재).

   - **영향**: 새 추론 계산 0(부트스트랩·p 재실행 0) · 메타데이터 계수 1건(④)만 · 예측 판독 0 · 봉인 판독 0 · csv 2종 0바이트 · 결과 수치 변경 0 · 봉인 39/831/801/30 · access 277 착수=종료 불변 · git 쓰기 0 · 네트워크 0. 기록 = vscode-claude(runner · 지시서 `docs/125c`) · 본 항목 기록 2026-10-09 15:41:15 KST.

93. **결과 절 통합 준비(블록 BL — `docs/126`)**:

   - **① 사용자 결정(2026-10-09 15:5x KST · `docs/126` §0 축자)**: 결정 L1 — F-NULL = 본문 **Figure 1**(RQ4 · [S14]) · F-D13 = 본문 **Figure 2**(RQ-int · [S24]). 등록 §5 A 「관측값과 null 분포 전체 그림」 의무. / 결정 L2 — 결과 절에 포인터 1문장 **[S76]** 추가(§3.3 끝 = [S46] 바로 뒤) + 보충표 S1 신설. / 보충표 번호 = 결과 절 **첫 언급 순서**: S1 = 미수행 등록 항목([S76]) · S2 = M2b − M1b 층화([S49]) · S3 = RQ8 arm별 AP(표 3 주석). 본문 표 1~3 번호 불변.

   - **② 정정 3건(문면 = `docs/126` §3-1 축자 · 근거 = `docs/125b` §1 #23)**:
     - **S14** 전 「RQ4 was not met: the observed rep1 (seed 201) M2b macro AP, T_obs = 0.1244, was equalled or exceeded by 965 of 1,000 family-constrained reallocations (96.5%; p_emp = 0.965) and by 214 of 1,000 global reallocations (21.4%; p_emp = 0.215), giving a slot p of 0.965 and a Holm-adjusted p of 0.988 in Panel I and 1.000 in Panel II.」<br>→ 후 「RQ4 was not met: the observed rep1 (seed 201) M2b macro AP, T_obs = 0.1244, was equalled or exceeded by 965 of 1,000 family-constrained reallocations (96.5%; p_emp = 0.965) and by 214 of 1,000 global reallocations (21.4%; p_emp = 0.215), giving a slot p of 0.965 and a Holm-adjusted p of 0.988 in Panel I and 1.000 in Panel II (Figure 1).」
     - **S24** 전 「The observed statistic was T_obs = Δ_RF − Δ_GIN = −0.0145, with Δ_RF = −0.0063 and Δ_GIN = 0.0082 (M2b − M1b within each family).」<br>→ 후 「The observed statistic was T_obs = Δ_RF − Δ_GIN = −0.0145, with Δ_RF = −0.0063 and Δ_GIN = 0.0082 (M2b − M1b within each family; Figure 2).」
     - **S49** 전 「In the M2b − M1b stratification (13 strata; raw estimates without multiplicity adjustment), a BCa interval was estimable in 12 strata (the remaining stratum contained 2 drugs); among these 12, the CI lower bound exceeded 0 in 2 strata and the CI upper bound was below 0 in 2 strata; all strata are reported in Supplementary Table [S-STRAT].」<br>→ 후 「In the M2b − M1b stratification (13 strata; raw estimates without multiplicity adjustment), a BCa interval was estimable in 12 strata (the remaining stratum contained 2 drugs); among these 12, the CI lower bound exceeded 0 in 2 strata and the CI upper bound was below 0 in 2 strata; all strata are reported in Supplementary Table S2.」
     - **표 3 주석**: 「Per-arm AP values are in Supplementary Table [S-RQ8].」 → 「Per-arm AP values are in Supplementary Table S3.」(그 줄 나머지 바이트 불변)

   - **③ 추가**: **S76**(S46 바로 뒤 · §3.3 끝) 「Registered analyses that were not performed or were not computable are listed in Supplementary Table S1, with the reasons recorded before unblinding.」 · 파일 끝(S72 뒤) `## Figure legends` 블록 — Figure 1(F-NULL · 50 bins · 1,000 family + 1,000 global · T_obs = 0.1244 · 상측 단측) · Figure 2(F-D13 · 200 bins · 0 대칭 · 100,000 · T_obs = −0.0145). 범례 숫자는 `[Sxx]` 밖 → 출처 = §2 메타데이터 assert 경로(`fig_null_realloc.json#/panels/family|global/{n,counts,observed}` · `fig_d13_rqint_reference.json#/panels/t_star/{n,counts,edges,observed}` · `results_full.json#/items/C4/T_obs` · `#/items/C8/t_obs` — 리포트 §4). 초안 `[S-` 자리표시자 0.

   - **④ 보충표 S1 신설 · 번호 규칙**: `docs/126_supp_table_S1_registered_items.md` = `unblinding_plan_v1.json#/prereg_coverage/map`(67키 · `item` 50 · `deviation_not_performed` 13 · `not_computable` 2 · `plan_frozen_pre_opening` 2) 비-`item` **17키**와 지시서 §3-2 «map 키» 열 **문자열·순서 완전 일치 assert** · 각 행 영문 항목·상태·사유·보고 위치 = 지시서 축자(map 키 열은 미출력) · 미수행 사유 정본 = 본 문서 항목 78(개봉 전 기록). 보충표 번호 = 결과 절 첫 언급 순(S1 = [S76] · S2 = [S49] · S3 = 표 3 주석) · 본문 표 1~3 번호 불변 · 색인 `docs/126_supplement_index.md`(Figure 1·2 · Table S1~S3 ↔ 출처 경로·sha). S2·S3 표 조판은 원고 통합 단계(본 블록 미수행).

   - **⑤ 항목 92 보충 — 표 1 수정 전 제목 원문**: 항목 92 ③ 은 바뀐 뒤 제목만 적고 수정 전 원문을 빠뜨렸음. 블록 BK 러너 작업 사본(`044b8e4f…` 초안 · sha256 전체 일치 확인)이 남아 있어 그 줄을 축자 기록 → 「## Table 1. Confirmatory and decision contrasts (consensus OOF macro AP; Δ = treatment − baseline)」(101 B · cowork 역복원 크기 산정 101 B 와 일치).

   - **⑥ 산출 sha · 자기 점검**: `docs/122_results_section_draft_en.md` `3814919652d5da01…` → 23,684 B `00bbf75b61150061…` · `docs/122_claim_audit_table.md` `54ed83be16a53696…` → 94,947 B `6ad3452e48334783…` · `docs/126_supp_table_S1_registered_items.md`(신규) 3,153 B `ab02b8f673bb2723…` · `docs/126_supplement_index.md`(신규) 2,027 B `432ad7d77110613f…`. 자기 점검(`bl_check.py` = `bk_check.py` 사본 확장): 문장 76 == 행 76 · 숫자 337(불변 · `Figure 1`·`Figure 2` 의 숫자는 식별자로 `IDENT` 가림 · `Supplementary Table S1~S3` 은 영문자 뒤라 토큰 아님) 전부 출처 연결(미연결 0) · 반올림 불일치 0 · 금지 문형 0(그림 범례 포함) · 필수 한정어 누락 0(S76 「recorded before unblinding」) · csv 2종(기존 1951셀 · 표 3 28셀) 불일치 0 · 초안 == 대조표 문면 76/76 · 대상 외 72문장·행 바이트 불변 72/72 · 재생성·추가 행 4/4 · 비문장 줄 순서 보존 부분수열 true · 보충표 S1 map 키 true · 그림 메타데이터 assert 4/4 → **PASS**. 대조표 자기 점검 표에 «126 재실행» 열 추가.

   - **영향**: 새 추론 계산 0 · 메타데이터 assert(키·개수·히스토그램 counts 합)만 · 예측 판독 0 · 봉인 판독 0 · 그림 재생성 0 · csv 2종 0바이트 · 결과 수치 변경 0 · 봉인 39/831/801/30 · access 277 착수=종료 불변 · git 쓰기 0 · 네트워크 0. 기록 = vscode-claude(runner · 지시서 `docs/126`) · 본 항목 기록 2026-10-09 17:00:57 KST.

94. **보충표 S2·S3 조판 · 원고 조립 폴더 반입(블록 BM — `docs/127`)**:

   - **① 산출 파일·sha**: `paper/v3/supplementary/Table_S2.md` 2,446 B `13b832a135cd463f…` · `paper/v3/supplementary/Table_S3.md` 1,428 B `f30a495a07501b38…` · `paper/v3/figures/Figure_1.png` 47,199 B `8c9f39ce9e415c73…` · `paper/v3/figures/Figure_2.png` 26,345 B `efd89fb53bf8cf98…` · `paper/v3/supplementary/Table_S1.md` 3,153 B `ab02b8f673bb2723…` · `docs/127_supp_tables_fullprecision.csv` 23,098 B `a1d9ee0c631ada48…` · 색인 `docs/126_supplement_index.md` 말미 append(`432ad7d77110613f…` → 2,352 B `2e86aaab45f13fc4…` · 기존 바이트 접두 불변). 표 제목·헤더·범례·행 라벨 = 지시서 §3 축자(지시서 파일에서 직접 추출) · `paper/v3/` = 로컬 전용(커밋 금지 목록).

   - **② §2 assert**: 층화 json `#/strata` 13키 · 축별 `n_drugs` 합 **847 / 847 / 847** · 13층 전부 `bootstrap/unit` = `scaffold_cluster` · `bootstrap/B` = `signflip/B` = 10000 · `docs/122_results_filled_fullprecision.csv` `2-6 SP-STRAT` 50셀(Δ 13 · CI 하한·상한 각 12 · p 13 — `seq_stratum::unseen_ge90` CI 는 csv 부재 · json `ci_primary/status` = `not_estimable`) **비트 동일**(repr 일치 + source_key 일치) · 반올림 13행 × 5칸 = §3-1 «기대값» 문자 단위 일치(`f`-format == Decimal ROUND_HALF_UP 이중 확인) · `struct_bounds.json` 경계 3자리 = 0.250 · 0.328 · 0.466 · `bin_rule` 일치 · `unseen_target.py` `SEQID_BOUNDARIES`(90 · 70 · 40) · `classify_drug` · `drug_sequence_stratum`(seen 우선 · all-unseen 은 표적별 최대 identity 의 최댓값) 문면 대조 일치(실행 0) · `results_rq8.json#/rows` 6키 · R8-gin `per_seed` 3키 · 6행 `delta` == `docs/124_table3_fullprecision.csv` Δ 셀 비트 동일 · S3 9행 AP·Δ 기대값 문자 단위 일치.

   - **③ 범례 사실 근거**: 847 = 축별 `n_drugs` 합(②) · 245 = 1,092 − 847(`docs/54` K-2-3) · fold-local 배정·3반복 불일치 → unstable = `docs/47` H-3 · 40–<70%·<40% stable 0 = `docs/47` 리포트 표(L127) · 반복1 사분위 = `struct_bounds.json`(`reference_repeat` 1) · B·unit·p 종류 = 층화 json(`bootstrap/B` · `unit` · `signflip/p_two_sided` · `exchange_unit` Bemis–Murcko scaffold group) · seen/unseen 규칙 = `unseen_target.py` · 다중성 미적용 = 층화 json `multiplicity` · S3 「Δ for R8-gin is the mean of the seed-specific differences」 = `#/rows/R8-gin/aggregation` + 3시드 Δ 평균 == `#/rows/R8-gin/delta`(|차| < 1e−15, 기존 값 산술 대조) · S3 Reference labels·Model = 초안 표 3 같은 행 문면.

   - **④ 복사 3건**: `fig_null_realloc.png` → `paper/v3/figures/Figure_1.png` · `fig_d13_rqint_reference.png` → `figures/Figure_2.png` · `docs/126_supp_table_S1_registered_items.md` → `supplementary/Table_S1.md` — 바이트 복사 · 원본 sha 동일 3/3(재생성·편집 0).

   - **⑤ 셀 추적**: `docs/127_supp_tables_fullprecision.csv` 121행(S2 78 = 13층 × 6값 · S3 43 = RF 5행 × 5 + 시드 3행 × 5 + mean 1행 × 3) · 전체 정밀도 · JSON 포인터 출처 · `unseen_ge90` CI 2칸 = `not_estimable`(출처 `ci_primary/status`) · 시드·mean 행 Drugs·PTs 출처 = `#/rows/R8-gin`.

   - **영향**: 새 추론 계산 0 · 공개 산출물 값 재포맷만 · `_sealed/` 판독 0 · 예측 판독 0 · 그림 재생성 0 · 결과 절 초안·대조표 0바이트 · csv 2종 0바이트 · 봉인 39/831/801/30 · access 277 착수=종료 불변 · git 쓰기 0 · 네트워크 0. 기록 = vscode-claude(runner · 지시서 `docs/127`) · 본 항목 기록 2026-10-09 19:22:11 KST.

95. **PLOS ONE 원고 초안 v0(블록 BN — `docs/129`)**:

   - **① 산출 파일·sha**: `paper/v3/manuscript/manuscript_plosone_v0.md` 67,184 B `f1b348a1989b759b…` · `paper/v3/manuscript/methods_trace.csv` 18,283 B `42265fd08dc8e407…` · `paper/v3/manuscript/reference_verification.csv` 6,610 B `856ad9409bb52f16…` · `paper/v3/manuscript/reference_fetch_log.jsonl` 16,446 B `c6e7838313190b1d…` · `paper/v3/manuscript/cover_letter_v0.md` 3,597 B `3fc8d469801616eb…` · `paper/v3/manuscript/open_items.md` 4,794 B `630dcacb128ad2a5…` · 색인 `docs/126_supplement_index.md` 말미 append(`2e86aaab45f13fc4…` → 2,603 B `3ee9364b7f04be67…` · 기존 바이트 접두 불변). `paper/v3/` = 로컬 전용(gitignore L11).

   - **② BN-2 assert PASS**: 결과 절 `docs/122_results_section_draft_en.md`(`00bbf75b61150061…`) 축자 이식 — 역치환·원위치 복원 시 `[Sxx]` 문장 집합 문자 단위 동일 · S01~S76 각 1회 · 표 3개 셀 행 바이트 동일 · 표 비-ID 각주·범례 동일. 치환 건수 = {"section number removed": 5, "Figure 1 → Fig 1": 4, "legend moved": 2, "table moved": 3, "Figure 2 → Fig 2": 4, "Supplementary Table S1 → S1 Table": 1, "Supplementary Table S2 → S2 Table": 1, "Supplementary Table S3 → S3 Table": 1, "table-note sentences moved": 5, "draft header blockquote removed": 1}. 표 1·2 = 3.1 소절(Holm family) 말미 · 표 3 = RQ8 소절 말미(결과 절에 표 인용 문장이 없어 «내용 소절 말미» 배치 — open_items 18).

   - **③ 참고문헌**: 후보 37 + 러너 추가 1(R38 = R11 DOI 의 DataCite 2018 arXiv 레코드) — verified 32 · excluded 1(R11 연도 불일치: 후보 ICLR 2019 vs DataCite 2018 · 인용 0) · no_doi_manual 5(R18·R32·R37·R35·R36 — 기계 검증 불가 · 누락 서지 요소 TBD). 원고 인용 37건 = verified 32 + no_doi_manual 5 · excluded 인용 0. 결과/주장 인용 13건 초록 대조 = 전부 Y.

   - **④ 네트워크**: GET 84건 · 호스트 {'api.crossref.org': 29, 'eutils.ncbi.nlm.nih.gov': 52, 'api.datacite.org': 3} · HTTP 200 84/84 · 로그 줄 수 = 요청 수 · 화이트리스트 외 호스트 0 · User-Agent 에 연구자 메일 없음.

   - **영향**: 새 추론 계산 0 · `_sealed/` 판독 0 · 예측 판독 0 · 결과 절·대조표·보충표·그림·설정·코드 0바이트(F1~F12 sha 착수 = 종료) · 봉인 39/831/801/30 · access 277 착수=종료 불변 · git 쓰기 0. 기록 = vscode-claude(runner · 지시서 `docs/129`) · 본 항목 기록 2026-10-11 22:07:54 KST.

   - **정정(항목 95 ② 치환 건수 · 2026-10-11 22:09:47 KST)**: ② 의 `Figure 1 → Fig 1: 4` · `Figure 2 → Fig 2: 4` 는 빌드 스크립트가 assert 단계에서 치환 함수를 다시 호출해 계수기가 2배로 늘어난 값이다. 실제 치환 = **Figure 1 → Fig 1 2건**(S14 · 범례) · **Figure 2 → Fig 2 2건**(S24 · 범례) — F1 본문 `Figure 1`·`Figure 2` 각 2회 · 원고 결과 절 `Fig 1`·`Fig 2` 각 2회 · `Figure` 잔존 0 으로 재계수 확인. 원고 바이트·assert 판정(PASS)은 영향 없음(계수기 표시값만 오류). 기록 = vscode-claude(runner · `docs/129`).

96. **v3 공개 릴리스 Phase A 감사(블록 BO — `docs/130`)**:

   - **① 산출 파일·sha**: `docs/130_v3_release_manifest.csv` 433,488 B `1de5b38f3af14ce3…`(헤더 1 + 데이터 1,841행 · 12열) · `docs/130_v3_release_scan.md` 21,125 B `e092c14b4cf17052…`. 둘 다 `.gitignore:8:docs/` 로 로컬 전용.

   - **② 클래스별 건수·크기**: `include=Y` 975행 326.39 MB(봉인 228행 238.32 MB = stat 기준 · 비봉인 747행 88.07 MB) · `include=REVIEW` 21행 2.72 MB · `include=N` 845행. 클래스 — C 189(5.44 MB) · F 50(0.54) · P 152 Y + 11 REVIEW(234.89) · R 401 Y + 3 REVIEW(26.08) · T 59 Y + 7 REVIEW(2.66) · D 76(56.42) · L 48(0.36) · X 845. R1 적용 = 확증 반복별·consensus OOF 152개 전부 `Y`(24 run · 근거 `unblinding_plan_v1.json#/read_scope/trees`) · null 실현값 16개(`v3_null_MAIN` 12 · `v3_null_probe` 4)와 체크포인트·`_partial`·`_staging`·`_ckpt` 중간 산출은 `X`(「R1: 요약만」). 100 MB 초과 0 · 50 MB 초과 0 · 최대 단일 파일 9.01 MB.

   - **③ BO-2 원고 근거 대조**: `paper/v3/manuscript/methods_trace.csv`(288행 · `42265fd08dc8e407…`)의 경로형 출처 **39/39 전건 manifest 행 존재**(누락 0). 비-경로 토큰 69개는 `results_sid` 46 · `ref` 20 · `git_object` 3(`kci-2026-v1.0:` 태그 객체 — 이미 공개). `include≠Y` = **REVIEW 5건**(`CLAUDE.md` · `docs/129_*_prompt_for_vscode.md` · `paper/v3/supplementary/Table_S1~S3.md`) — 비공개(`X`)로 남은 인용 출처 0. S06 이 지목한 `experiments/provenance/sign_disclosure_matrix.json` 은 R2 에 따라 `T`/`Y`.

   - **④ 스캔(원문 0건 · 별칭만)**: `include ∈ {Y,REVIEW}` 996행 중 봉인 229·집계 2·이진 46 제외 → 텍스트 **719파일 전수** 스캔(읽기 실패 0). 패턴 16종 중 적중 = `author_name` 28파일/139건(저자 3인 · 마스킹 대상 아님) · `name_NAME-1` 23/170(외부 통계 검토자) · `abspath_users` 19/42 · `email` 13/122(단일 웹메일 도메인) · `name_NAME-2` 7/30(제2자) · `gmail_msgid` 2/2. 토큰·키 5종(`ghp_`·`github_pat_`·`sk-`·`AKIA`·PEM) · 국제전화 접두 · 호스트명 2종 = **전건 0**. 전화번호 패턴 6파일 37건은 경계가드 적용 후 shape 판정으로 **전건 오탐**(sha256 16진 내부 숫자열 · `elapsed_s` 부동소수 · UUID 경로) → 실제 전화번호 0건. 비봉인 `.npz` 14개 배열 이름에 사람 이름 0건. 마스킹 필요 파일 **44개** 중 현재 sha256 이 해시 레지스트리에 등재된 것 **16개**(전체 13 · 앞16자 3) → 마스킹 사본의 sha 는 원본과 달라지므로 README 고지 대상. 파일명 자체에 실명이 든 파일이 `docs/` 3건·루트 1건 존재(경로 미기재) → `docs/` 디렉터리 일괄 개방 금지.

   - **⑤ 영향**: **쓰기 = 본 산출 2파일 + 기록 3종뿐.** 파일 복사·이동·삭제 0 · 마스킹 적용 0(계획만) · `.gitignore` 수정 0(부정예외는 초안 90줄 = `docs/130_v3_release_scan.md` §8) · git 쓰기 0(`add`·`commit`·`stash`·`switch`·`worktree`·`tag`·`push`·`fetch`·`status` 전건 미실행 · 읽기는 `rev-parse`·`rev-list`·`ls-files`·`ls-tree`·`check-ignore` 만) · HEAD `566f487` · 커밋 수 21 · `ls-files -m` 5 · `origin/main` `5570685…` 착수=종료 불변 · `.git/index.lock` 부재 · **`_sealed/` 내용 판독 0**(`os.stat` 만 · 봉인 39/831/801/30 · access 277 · stat 지문 `58a3eec970dfbd6a…` 착수=종료 동일) · 네트워크 0 · 새 계산 0 · 개봉 0. 기록 = vscode-claude(runner · 지시서 `docs/130`) · 본 항목 기록 2026-10-12 01:05:40 KST.
