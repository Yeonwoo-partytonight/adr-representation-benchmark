#!/usr/bin/env python3
"""_record.py — 블록 AK 기입 3곳: docs/33 항목52 · docs/45 §2+§5 · ledger.json."""
import hashlib, json, os, sys
from datetime import datetime, timedelta, timezone

ROOT = "<REPO_ROOT>"
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))
import doc_numbering as dn  # noqa: E402

def sha(p):
    return hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest()

D33 = "docs/33_prereg_deviation_log.md"
D45 = "docs/45_research_integrity_ledger.md"
LED = "experiments/provenance/ledger.json"

before = {p: sha(p) for p in (D33, D45, LED)}
d33_before_bytes = os.path.getsize(os.path.join(ROOT, D33))
d45_before_bytes = os.path.getsize(os.path.join(ROOT, D45))

# ── docs/33 항목번호 실측
N = dn.next_item_number(os.path.join(ROOT, D33))
assert N == 52, f"기대 52, 실측 {N}"

ITEM = f"""{N}. **R2 준비 — SAP 1.2 재동결 「설계 확정」 (블록 AK — 무동결 · 계산 0 · 채택 0)**:

   - **① 왜 「준비 블록」을 따로 두었나 — R2 실행 직전에 문면 충돌 2건이 실측됐다**: **충돌 A** = `sap_version` 은 `v3_Multimodal/src/sap/freeze.py` **L581 하드코딩 리터럴**이고 CLI·환경변수·설정파일 경로가 **0개**인데(`F-VERLIT`), 그 `freeze.py` 자신이 `MODULE_FILES` **11개 중 하나**다(`F-MODFILES`, L47). 따라서 1.1 → 1.2 는 **필연적으로 11모듈 중 1개의 sha256 을 바꾼다** → `docs/55b` §8 L470 축자 **"all pre-existing module hashes remain unchanged"** 와 충돌한다. **충돌 B** = D20 의 `model_family` 문자열 원천은 매니페스트가 아니라 **`v3_Multimodal/src/sap/decision.py` 7행**(L61·65·69·73·77·81·85)이고 `manifest.json` **14곳**(`frozen_parameters`/`validation` × `multiplicity_manifest[0..6]`)은 그 파생물이다 → 「11모듈 불변」(decision.py 못 고침)과 「manifest 재현성」(고쳐야 함)이 **동시 성립 불가**하다. D20 이 요구하는 **「전후 sha16」이 manifest 인지 모듈인지도 문면상 미결**이다. 동결은 되돌릴 수 없고 매니페스트 해시를 수십 블록이 참조 중이므로 **측정·선택지 정리를 먼저 하고 동결은 `docs/100` 으로 분리**했다.

   - **② 「비실질 메타데이터」 주장의 코드 근거 — AST 판정 = 표기 전용**: `MULTIPLICITY_MANIFEST` 는 `decision.py` 에서 **L59 Store 1건뿐**이고 읽는 코드가 없다. `freeze.py` 의 L372·L650 은 **둘 다 dict 값 위치의 Load** = 직렬화 기록 전용이다. 첨자·순회·컴프리헨션 **0건**. `model_family` 키를 **읽는** 코드는 저장소 전역(`.venv`·`archive` 제외) **0곳**이다. Holm 계산은 `HOLM_FAMILY`(라벨 7개)만 쓰며(`holm()` L190~210: `labels = list(HOLM_FAMILY)` · `assert m == len(HOLM_FAMILY) == 7`), **순서 무관**(`np.argsort(p)`)이고 family_size 도 `HOLM_FAMILY` 길이로 고정된다. → **D20 의 「비실질」 주장은 코드로 뒷받침된다** — `model_family` 를 어떻게 고쳐도 수치 결과는 바뀌지 않는다. 다만 `decision.py` 를 고치면 **핵심 분석 모듈 해시가 바뀐다**는 사실은 그대로 남는다(= 충돌 B).

   - **③ 가상 해시 산출(파일 수정 0 · 메모리 내 치환)**: `freeze.py` 현재 sha256 `94e6369fa952be7f…`(42,927 B) → **A-1a**(L581 리터럴 1문자만) `8bef5f70d168c50d…`(42,927 B) · **A-1b**(리터럴+주석) `37442f6db2717746…`(42,959 B). 나머지 **10모듈은 변경 없음**. 11모듈 live sha256 은 `manifest.modules` 등재값과 **전건 일치**했다. ★ **실제로 고치지 않았다** — 전 파일 **0바이트**다.

   - **④ ★ 지시서 미상정 실측 3건(R2 의 필수 후속 작업을 늘린다)**: ⓐ **매니페스트는 애초에 바이트 재현물이 아니다** — `frozen_at_kst` 가 `datetime.now(KST)`(`freeze.py` L582)이고 `versions` 가 설치 패키지 버전(L674)이다. 즉 `manifest.reproduce` 는 **의미 수준 재현**이며, 이 사실은 A-3·B-2 에 대한 「재현성 붕괴」 반론의 강도를 낮춘다(붕괴가 아니라 **이미 성립하지 않던 것의 명시화**). ⓑ **매니페스트 sha16 `756d485feb4715e9` 하드코딩이 30파일 · 48곳**이다. 그중 **R2 이후에도 실행될 live src 3개** — `pre_unblinding_audit.py`(L64 기대해시·L121 게이트) · `rqint_package_gates.py`(L35) · `rqint_calibration.py`(L138·892·1328) — 는 기대값을 갱신하지 않으면 **R2 직후 자동 실패**한다. ★ `pre_unblinding_audit.py` 는 **개봉 전 필수 감사**다. `sap_version == "1.1"` 을 `assert` 로 거는 곳도 6개다(`confirmatory_oof_rep1.py:160` 외 `record_block_*` 5개). ⓒ **`experiments/rqint/r3_package/sap/` 에 SAP 11모듈의 바이트 동일 사본**이 있다(전건 `identical_to_live` true) → `freeze.py`·`decision.py` 를 고치면 즉시 발산하므로 R3 축자 「동결 해시로부터 동일 산출 확인」 충족에 패키지 재생성이 필요하다.

   - **⑤ 선택지 정리 — 채택 0(사용자/검토자 몫)**: 충돌 A **3안**(A-1 L581 한 줄 / A-2 외부 주입 / A-3 manifest 후처리)과 충돌 B **3안**(B-1 `decision.py` 7행 수정+스키마 분리 / B-2 무수정·manifest 필드 추가 / B-3 이번 회차 보류)을 **비용·무결성·재현성** 3축 비교표로 냈고, 안별 §8 개정문 문안까지 **영문+국문 3종씩** 작성했다. B 3안에 대해서는 **D20 4요구**(전후 문자열·전후 sha16·라인 diff·11모듈 불변 명시)의 ○/× 표와 **「어느 sha16 을 가리키는가」**(B-1 = `decision.py`+manifest / B-2 = manifest 만 / B-3 = 없음)를 명시했다. ★ **러너는 어느 안도 채택하지 않았다.**

   - **⑥ §8 개정문 확정 문안 초안 — `docs/99_amendment_section8_draft.md`(신규)**: 빈칸 4개를 **2026-08-10 / <EXTERNAL-REVIEWER> / Ph.D. / Gyeongnam Intelligence Innovation Center (GIIC)** 로 채웠다(출처 = `v3_Multimodal/config/reviewer_identity_resolved.json:blanks_resolved`, 블록 AH, 서명본 `…_SIGNED.pdf` sha256 `161dd9d2290df32b…` 축자). ★ **승인일 2026-08-10 ≠ 서명일 2026-08-12** 이며 부록 B `2026-08-06` 과 표지 `2026-08-10` 이 갈렸을 때 **표지 기준으로 통일**했고 서명본에서 정정되지 않았다는 확정 근거(`both_literals_preserved`)를 **주석으로 병기**했다. 해시 관련 문장은 **`{{A안}}`·`{{B안}}` 플레이스홀더**로 두었다. **`docs/55b` 는 0바이트** — 본문 삽입은 `docs/100` 의 일이다.

   - **⑦ ★ R5 두 요소 추가 + 실측 불일치 1건 정직 기록**: R5 는 현재 **`partial` 인 유일한 승인조건**이다(`rqint_procedure_decisions_v0.json:conditions.R5.status`). 실측(`F-R5GAP`) = 부호 4건은 §8 에 있으나 **공개일자 2026-07-27 은 §8 안에 없고** §2 본문 L137 **1곳뿐**이며 **노출 인원은 문서 전체에 없다**. 초안에 두 요소를 넣었다 — **공개일자 2026-07-27**(`first_look_register.rows` 4행 `ts_kst` 전건과 일치) · **노출 인원** = 「방향을 아는 사람은 **실명 2명**(연구자·지도교수), **외부 검토자는 부호 4건이 존재하고 서로 동일하다는 사실만** 고지받았고 방향은 모른다(`docs/55b` §2 축자), **4건 중 3건**(반복2·반복3·consensus)은 **2026-07-28 부터 공개 저장소에서 열람 가능**」. 공개 근거 = `experiments/provenance/sign_disclosure_matrix.json:public_exposure_verification` — 스칼라 부호 리터럴 **3개**(`/repeats/2/sign`·`/repeats/3/sign`·`/consensus/sign`) · `in_pushed_commit` **true** · 원격 tip `bdb65c8` · 커밋 `878b3ba`(2026-07-28 15:58:58 KST) · push reflog 2026-07-28 16:10:52 +0900. 반복1 은 **푸시된 커밋에 없다**. ★ **불일치** — 「실명 2명」 중 **지도교수 항목은 저장소 실측이 `unknown_as_of_2026-08-06`** 이다(`sign_disclosure_matrix.json:advisor_route.determination` · `sign_lexeme_hits_in_correspondence` **빈 배열** · `open_questions[0]` 축자 「지도교수에게 Δ(M2b−M1b) 부호가 전달된 사실이 서신 기록에서 확인되지 않는다」). 지시서가 이 문안을 **사용자 확정**으로 지정했으므로 초안 본문은 지시서대로 쓰되, 초안 §6 과 리포트 §5 에 불일치와 **두 선택지**(① 근거 보강 후 「2명」 유지 / ② 「연구자 1명 확정, 지도교수 전달 여부 서신 기록상 미확인」 으로 조정)를 정리했다. **러너는 채택하지 않았다.**

   - **⑧ `still_unspecified` 3건 종결안 초안 — `v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json`(신규 · `.DRAFT` 접미사 필수)**: `status` = `draft_not_frozen` · `is_sap_freeze` **false** · `supersedes` **null**(v0 를 대체하지 않고 superseding 관계만 기술) · **v0 는 0바이트**. ⓐ **`B` = 동전 벡터 수 = 100,000**(참조분포 200,000) — 사용자 확정 **2026-08-24**. 근거 = `F-BMEAS` **19.4887 h ≤ 24 h** → D15 하향 **미발동** · 검토자 §9-2 함의 단가 1.08 s/동전이 「동전 수 상정」 시사 · 판정식 2분기가 실주행 **이전**에 동결(`b_100k_prespec.json` 2026-08-22T22:12:40 < 실주행 2026-08-23T11:36:18). ⓑ **C0~C3 복제수 primary 2,000 / sensitivity 1,000** — ★ **결과를 보고 정한 것이 아니다**: `calibration_design.json`(sha256 `42e2f8f9f3f24ec1…`) 동결 **2026-08-12 22:25:21 KST** 가 첫 시뮬레이션 세션 시작 **2026-08-12 22:46:44 KST** 보다 **21분 23초 앞선다**(`calibration_sessions.jsonl` 실측). 검토자 권고 1,000~2,000 범위 안. ⓒ **`r3_second_party` = <SECOND-PARTY> 확정** — 교수님 승인 축자 「네 <SECOND-PARTY>씨에게 부탁해서 처리하시죠.」(`ledger.correspondence[19]`, 메시지 `<GMAIL-MSGID>`, 2026-08-12 18:34:47 KST) + `r3_second_party_freeze.json`(`0624d3ddb852c4e9`).

   - **⑨ ★ 누락 발견 — 블록 AG 가 `r3_second_party` 를 종결하지 않았다**: 2026-08-24 실측으로 `rqint_procedure_decisions_v0.json:still_unspecified[4]` 는 여전히 `status` = **`escalated_awaiting_advisor_reply`** · `confirmed_second_party` = **null** 이다. 항목의 `note` 축자(「상신은 완료됐으나 수행 주체 확정은 미완이므로 still_unspecified 에서 빼지 않는다」)는 **승인 서신 접수(2026-08-12 18:34:47) 이전 기준**이라 stale 이다. 승인은 그날 저녁 도착했고 블록 AG(2026-08-14)가 접수·기록했으나 v0 의 해당 항목에는 반영되지 않았다. **본 블록은 v0 를 고치지 않고 누락 사실만 기록**했다(DRAFT 의 `★_omission_found_by_this_block`). 부수 확인 — 메모 등에 있던 `ledger.open_question.r3_second_party` 는 **존재하지 않는 키**다(ledger 최상위 **11키**에 `open_question` 없음, 실측) → 조치 불요. v0 의 stale 3건(`conditions.R1.status`=`pending` vs 실측 `r1_passed`=true · `R6`=`pending` vs 블록 AC 수행 · `R5`=`partial`)도 **고치지 않고 기록만** 했다.

   - **⑩ 해시 원장 스펙 + R2 이행 대조표 — `docs/99_r2_hash_registry_spec.md`(신규)**: 범주 ①SAP 11모듈 ②RQ-int 3모듈(`sap/rqint*.py`) ③config 동결파일 16종 ④`B`·시드집합·대표폴드·실패처리 규칙의 소재 파일 ⑤사전등록·개정문·원장 문서 — 총 **45행**에 현재 sha256 을 실측 병기하고 **「이미 어디에 등재됐는가 / 아직 원장에 없는가」**를 마지막 열에 표기했다. **미등재 11건** = 실질 신규 등재 **6건** + append-only **4건**(고정 해시 동결 불가 → 「동결 시점 스냅샷」 지위) + 표기 정정 1건. ★ 그중 **`reviewer_identity_resolved.json`(§8 빈칸 값 원천)** 과 **`sign_disclosure_matrix.json`(R5 노출 인원 근거)** 이 미등재인 것이 가장 중요하다. 이행 대조표는 **R2·R4·R5·D19·D20·D21·D22 + KS 신설** 8행을 「요구 축자 / 현재 상태 / 이행 위치 / 남은 일」 4열로 채웠다 — **R4** = SAP 1.2 §RQ-int 다중성 소절 2문장 + `manifest.frozen_parameters.decision_A11.multiplicity` 문자열, 총 **3곳** 지정(★ `holm()` **코드 수정 불필요** — A/B 두 판은 같은 함수를 입력만 달리 호출해 얻는다; 고치면 11모듈 해시가 또 바뀐다). **D19** = C4 실측 검정력 τ0.01 **0.250** / τ0.02 **0.735** / τ0.03 **0.9725**(각 R=400, α=0.05 기각률) → τ=0.02 는 3단 사다리 **중간단(0.50~0.80)** = 「검정력·유보문장 병기」, 최하단 조항 **미발동**, 0.80 미달이므로 관례적 충족 주장 금지. **D21** = **확인 완료**(`gin_seed_freeze.json` `10828447c6d33118`: 대표 unit **3** = (201,4)·(202,1)·(203,0) · `training_seeds_ordered` **5** · `confirmatory_seed_prefix` **3** · `stability_seeds` **5**) ★ RQ-int 는 「3 seed × 3 repeat」(D4·D5)이므로 SAP 1.2 는 **어느 5/3 인지 명시**해야 한다. **D22** = `sap/rqint.py` `TEST_STATISTIC` 에 "additive surrogate 대체 금지(A6 계승)" 가 **이미 있음** → 「`e_g` 선형화 = 보조 진단 전용」 1문장 추가. **★ KS 신설 항목** = `C0:prop` KS p **0.052447**(여유 **+0.002447**)이 기준 0.05 **바로 위**라는 사실을 R2 문면에 **정직 기재**하도록 항목을 신설하고 병기 문안까지 작성했다. **AF-DEV-1 미상신 결정**(사용자 2026-08-18)은 **항목50 참조만**(중복 기입 0).

   - **⑪ 무결성 — 착수=종료 불변**: **`sap_version` 1.1** · `manifest.json` sha16 **`756d485feb4715e9`**(sha256 착수=종료 동일) · SAP 등재 **11모듈 0바이트** · `freeze.py` **미실행 · 0바이트** · `decision.py` **0바이트** · **config 동결파일 16종 전건 0바이트**(`ladder_freeze`·`gin_seed_freeze`·`gin_inner_valid_freeze`(+`.status`)·`post_interim_freeze_v1_0`(+`.status`)·`rf_tuned_freeze`·`holm7_latefusion_freeze`·`a5_boundary_amendment`·`a5_mechanism_freeze`·`a5_stratum_label_supersede`·`r3_second_party_freeze`·`reviewer_identity_resolved`·`rqint_procedure_decisions_v0`·`b_dryrun_prespec`·`b_100k_prespec`) · **`docs/55b` 0바이트** · 블록 AC 4파일 + AD 2파일 + AI 4종 + AJ 산출물 **0바이트** · `sap/rqint.py` sha16 **`eb842bc98140e9c5`** 불변(`B_DEFINITION_STATUS` = `still_unspecified` 그대로) · `_sealed/` guard **275종(access.log 제외) / 291종(포함)** 및 stat-only 스냅샷 착수=종료 동일 · HEAD **`566f487`** · 커밋 **21** 불변. 본 블록이 만든 파일 = `docs/99_r2_freeze_prep_report.md` · `docs/99_amendment_section8_draft.md` · `docs/99_r2_hash_registry_spec.md` · `v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json` · `experiments/rqint/r2_prep/` 산출뿐이다.

   - **⑫ ★ 본 기입은 어떤 착수 허가도 아니다**: **동결 0**(`sap_version` 1.2 승격 **0** · 매니페스트 재생성 **0** · 원장 신규 등재 **0**) · **채택 0**(충돌 A·B 안 채택 0 · `B` 정의 동결 0 · `still_unspecified` 3건 동결 0 — `.DRAFT` 초안뿐) · **개봉 0**(`unblinding_performed` false · `_sealed/` 읽기·쓰기 0 · `open_sealed` 0 · `emit_sign` 0 · `decision.py` 호출·import 0) · **계산 0**(모델 학습·추론·순열·새 추정 0 · 확증 예측·OOF 로드 0) · **GIN 착수 0**(`gin_start_still_blocked` true) · **네트워크 0** · **`data/raw/` 변경 0** · **git commit·push 0**. R2·R3·`B` 확정·개봉·GIN 착수는 **전부 차단 유지**다.

> 지시서 = `docs/99_r2_freeze_prep_prompt_for_vscode.md` · 리포트 = `docs/99_r2_freeze_prep_report.md` ·
신규 산출 = `docs/99_amendment_section8_draft.md`(sha256 `29b2d8f401afa0dc…`) · `docs/99_r2_hash_registry_spec.md`(`d10ffe4431fd2f60…`) · `v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json`(`88287032cf6fbc58…`) · `experiments/rqint/r2_prep/{{facts,impact,registry,verify}}.json` ·
무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · `docs/55b` **0바이트** · config 동결파일 **16종 0바이트** · `sap/rqint.py` **0바이트** · 블록 AC 4파일 + AD 2파일 + AI 4종 + AJ 산출물 **0바이트** ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 sha256 착수=종료 동일). **미실행**: 위 ⑫ 전항. 기입 시각 {NOW}.

---
"""

# ── docs/33 append (append-only · 접두사 바이트 보존)
p33 = os.path.join(ROOT, D33)
with open(p33, "r", encoding="utf-8") as f:
    t33 = f.read()
with open(p33, "w", encoding="utf-8") as f:
    f.write(t33 + "\n" + ITEM)

# ── docs/45 §2 +1행 · §5 문서이력 +1행 (조회 대장 표 무수정)
p45 = os.path.join(ROOT, D45)
lines = open(p45, encoding="utf-8").read().split("\n")
assert lines[65].startswith("| 2026-08-23 11:36:18 KST |"), lines[65][:60]
assert lines[142].startswith("> 📄 **문서 이력(2026-08-23)"), lines[142][:60]
assert lines[144].startswith("| 시각(KST) | 조회자 |"), lines[144][:60]

ROW2 = ("| 2026-08-24 12:30 KST | **블록 AK(준비 전용 · 무동결 · 계산 0 · 채택 0)** "
  "**R2(SAP 1.2 재동결) 설계 확정 — 문면 충돌 2건 실측·선택지 정리·§8 문안 초안** — `docs/84` §5 ⑦ 의 앞단이다. "
  "**충돌 A** = `sap_version` 은 `sap/freeze.py` **L581 하드코딩 리터럴**(CLI·env 경로 0)인데 `freeze.py` 자신이 "
  "`MODULE_FILES` **11개 중 하나**라, 1.1→1.2 는 필연적으로 11모듈 중 1개 해시를 바꾼다 → `docs/55b` §8 L470 축자 "
  "「all pre-existing module hashes remain unchanged」와 충돌. **충돌 B** = D20 의 `model_family` 원천은 "
  "`sap/decision.py` **7행**(L61·65·69·73·77·81·85)이고 `manifest.json` **14곳**은 파생물이라 「11모듈 불변」과 "
  "「manifest 재현성」이 동시 성립 불가하며, D20 의 「전후 sha16」이 manifest 인지 모듈인지도 **문면상 미결**이다. "
  "★ **AST 판정** — `MULTIPLICITY_MANIFEST` 는 `decision.py` L59 **Store 1건뿐**(읽는 코드 0), `freeze.py` "
  "L372·L650 은 **dict 값 Load = 직렬화 기록 전용**, `model_family` 를 **읽는** 코드는 저장소 전역 **0곳**, Holm 은 "
  "`HOLM_FAMILY`(7 라벨)만 사용·순서 무관 → **D20 의 「비실질」 주장은 코드로 뒷받침된다**. "
  "**가상 해시**(파일 수정 0 · 메모리 내 치환) `freeze.py` `94e6369fa952be7f…` → A-1a `8bef5f70d168c50d…` / "
  "A-1b `37442f6db2717746…`, 나머지 10모듈 불변. ★ **지시서 미상정 실측 3건** — ⓐ 매니페스트는 애초에 "
  "**바이트 재현물이 아니다**(`frozen_at_kst` = `datetime.now`, `versions` = 설치 패키지 버전) ⓑ 매니페스트 sha16 "
  "`756d485feb4715e9` 하드코딩 **30파일·48곳**이고 그중 **R2 이후에도 실행될 live src 3개**"
  "(`pre_unblinding_audit.py`·`rqint_package_gates.py`·`rqint_calibration.py`)는 기대값 갱신 없이는 "
  "**R2 직후 자동 실패** — `pre_unblinding_audit.py` 는 **개봉 전 필수 감사**다 ⓒ `experiments/rqint/r3_package/sap/` 에 "
  "SAP 11모듈 **바이트 동일 사본**이 있어 R3 「동결 해시로부터 동일 산출」 충족에 재생성 필요. "
  "산출 = `docs/99_amendment_section8_draft.md`(빈칸 4개 **2026-08-10 / <EXTERNAL-REVIEWER> / Ph.D. / GIIC** 확정, "
  "★ **승인일 ≠ 서명일 2026-08-12**, R5 두 요소 **공개일자 2026-07-27 · 노출 인원** 추가, 해시 문장은 "
  "`{{A안}}`·`{{B안}}` 플레이스홀더 + 안별 문안 영문·국문 3종씩) · `docs/99_r2_hash_registry_spec.md`(원장 **45행** "
  "실측 · **미등재 11건** · R2 이행 대조표 **8행**) · `rqint_procedure_decisions_v1.DRAFT.json`(종결안 3건 초안 · "
  "`draft_not_frozen` · v0 **0바이트**). ★ **누락 발견** — 블록 AG 가 종결했어야 할 `r3_second_party` 가 v0 에 "
  "미반영(`escalated_awaiting_advisor_reply` · `confirmed_second_party` null 그대로). ★ **R5 실측 불일치** — "
  "「실명 2명」 중 지도교수 항목은 `sign_disclosure_matrix.json:advisor_route` = **`unknown_as_of_2026-08-06`**"
  "(서신 부호 어휘 스캔 **빈 배열**) → 두 선택지 정리·**채택 0**. **동결 0 · 채택 0 · 개봉 0 · 계산 0 · GIN 착수 0 · "
  "`emit_sign` 0 · 네트워크 0 · git commit·push 0** | vscode-claude | **N** (봉인 stat-only · `open_sealed` 0 · "
  "확증 데이터 로드 0 — 조회가 아니므로 §5 확증 조회 대장에 행을 추가하지 않는다) | "
  "`docs/99_r2_freeze_prep_prompt_for_vscode.md`(지시서), `docs/99_r2_freeze_prep_report.md`, `docs/33` 항목52, "
  f"`experiments/rqint/r2_prep/{{facts,impact,registry,verify}}.json` |")

ROW5 = ("> 📄 **문서 이력(2026-08-24) — 블록 AK(R2 준비: SAP 1.2 재동결 설계 확정 · 무동결)**: 본 대장에 "
  "**신규 조회행 없음**(조회 대장 표 자체 무수정 — **개봉 0** 이므로 조회행이 생길 수 없다). 입력은 **기존 파일의 "
  "읽기와 stat 뿐**이고 확증 조회 **N** 이다 — 확증 예측·OOF 로드 **0** · 모델 학습·추론 **0** · 새 추정 **0** · "
  "Δ·AP·CI·p·부호 산출 **0** · `emit_sign` **0** · `open_sealed` **0** · `_sealed/` 읽기·쓰기 **0**"
  "(stat-only 스냅샷 **275종(access.log 제외) / 291종(포함)** 및 sha256 착수=종료 동일) · `decision.py` "
  "호출·import **0**(AST 판독만) · **SAP 1.2 재동결 0**(`sap_version` **1.1** · manifest sha16 "
  "`756d485feb4715e9` 불변 · 11모듈 및 config 동결파일 16종 · 블록 AC 4파일 · AD 2파일 · AI 4종 · AJ 산출물 "
  "**전건 0바이트** · `sap/` 내 신규·수정 **0건**) · **`docs/55b` 0바이트**(§8 개정문 확정본은 신규 초안 파일로만) · "
  "**`B` 정의 동결 0**(`sap/rqint.py` `B_DEFINITION_STATUS` = `still_unspecified` 그대로) · **GIN 착수 0** · "
  "**개봉 0**(`unblinding_performed` false) · 네트워크 **0** · git commit·push **0**(HEAD `566f487` 불변). "
  "본 블록은 **선택지를 정리하는 데까지**이고 충돌 A·B 어느 안도 **채택하지 않았다** — 채택은 사용자/검토자 몫이며 "
  "동결은 `docs/100`(R2 실제 동결)의 일이다. ★ **R5 실측 불일치 1건 기록** — 개정문 「실명 2명(연구자·지도교수)」 중 "
  "지도교수 항목은 `experiments/provenance/sign_disclosure_matrix.json:advisor_route.determination` = "
  "**`unknown_as_of_2026-08-06`** 이고 `sign_lexeme_hits_in_correspondence` 가 **빈 배열**이다(서신 기록에서 "
  "부호 전달 미확인). 지시서가 사용자 확정 문안으로 지정했으므로 초안 본문은 그대로 쓰되 두 선택지를 병기했다. "
  "기록 = `docs/33` 항목52, 리포트 = `docs/99_r2_freeze_prep_report.md`. "
  "**본 기록은 어떤 착수 허가도 아니다** — R2 동결 · R3 이행 · `B` 확정 · GIN 착수 · 개봉은 전부 **차단 유지**다.")

new = lines[:66] + [ROW2] + lines[66:143] + ["", ROW5] + lines[143:]
open(p45, "w", encoding="utf-8").write("\n".join(new))

# ── ledger.json
pled = os.path.join(ROOT, LED)
led = json.load(open(pled, encoding="utf-8"))
n_tl, n_auth = len(led["timeline"]), len(led["authoritative_sources"])
assert n_tl == 49 and n_auth == 26, (n_tl, n_auth)
keys_before = list(led.keys())
flr_keys_before = list(led["first_look_register"].keys())
flr_rows_before = len(led["first_look_register"]["rows"])
corr_before = len(led["correspondence"])

led["timeline"].append({
  "ts": "2026-08-24",
  "ts_kst": NOW,
  "recorded_at": NOW,
  "event_at": "2026-08-24 (블록 AK 수행·기입)",
  "actor": "vscode-claude (지시서 docs/99 · FACTS 18행 러너 실측 · 파일 해시 실측)",
  "step": ("블록 AK — R2(SAP 1.2 재동결) 준비: 문면 충돌 2건 실측 확정 · 선택지 정리 · §8 개정문 문안 초안 · "
           "still_unspecified 3건 종결안 초안 · 해시 원장 스펙 + R2 이행 대조표. "
           "★ 무동결 · 계산 0 · 채택 0(충돌 A·B 안 채택은 사용자/검토자 몫) · 개봉 0 · GIN 착수 0 · commit/push 0"),
  "event": (
    "① 충돌 A 확정 — sap_version 은 v3_Multimodal/src/sap/freeze.py L581 하드코딩 리터럴이고 CLI·환경변수·설정파일 "
    "경로가 0개인데(F-VERLIT), freeze.py 자신이 MODULE_FILES 11개 중 하나다(F-MODFILES, L47). 따라서 1.1→1.2 는 "
    "필연적으로 11모듈 중 1개 sha256 을 바꾸며 docs/55b §8 L470 축자 'all pre-existing module hashes remain "
    "unchanged' 와 충돌한다. L581 리터럴은 freeze.py 안에서 L581(매니페스트 dict 값)·L698(완료 로그 문자열 보간) "
    "2곳뿐이고 조건·비교·분기에 진입하지 않는다 → A-1 의 계산 무영향 주장은 코드로 성립. "
    "② 충돌 B 확정 — model_family 문자열 원천은 decision.py 7행(L61·65·69·73·77·81·85)이고 manifest.json 14곳"
    "(frozen_parameters/validation × multiplicity_manifest[0..6])은 파생물이다. 11모듈 불변과 manifest 재현성이 "
    "동시 성립 불가하며, D20 의 '전후 sha16' 이 manifest 인지 모듈인지 문면상 미결이다. "
    "③ AST 판정(D20 '비실질' 주장의 근거) — MULTIPLICITY_MANIFEST 는 decision.py L59 Store 1건뿐이고 읽는 코드가 "
    "없다. freeze.py L372·L650 은 둘 다 dict 값 위치의 Load = 직렬화 기록 전용이며 첨자·순회·컴프리헨션 0건이다. "
    "model_family 키를 읽는 코드는 저장소 전역(.venv·archive 제외) 0곳이다. Holm 계산은 HOLM_FAMILY(라벨 7)만 쓰고"
    "(holm() L190~210: labels = list(HOLM_FAMILY), assert m == len(HOLM_FAMILY) == 7) 순서 무관(np.argsort(p))이며 "
    "family_size 도 HOLM_FAMILY 길이 고정이다 → D20 의 '비실질 메타데이터' 주장은 코드로 뒷받침된다. "
    "④ 가상 해시(파일 수정 0 · 메모리 내 치환) — freeze.py 94e6369fa952be7f4ac41f79da6d3b63f80a1a7c2192873a4"
    "99e3ccd4a2f1cc9 (42,927 B) → A-1a(리터럴 1문자) 8bef5f70d168c50d7860d5e1d70f78b771d76405fafe2c4d256ac04d"
    "08078bc9 (42,927 B) / A-1b(리터럴+주석) 37442f6db2717746ba05c68002bac5d29df433e4d9fa4496c3f96514668b0ca2 "
    "(42,959 B). 나머지 10모듈 변경 없음. 11모듈 live sha256 은 manifest.modules 등재값과 전건 일치. "
    "⑤ 지시서 미상정 실측 3건 — (a) manifest 는 애초에 바이트 재현물이 아니다: frozen_at_kst 가 "
    "datetime.now(KST)(freeze.py L582), versions 가 설치 패키지 버전(L674) → manifest.reproduce 는 의미 수준 "
    "재현이며 이 사실이 A-3·B-2 에 대한 '재현성 붕괴' 반론의 강도를 낮춘다. (b) manifest sha16 756d485feb4715e9 "
    "하드코딩이 30파일·48곳이고 그중 R2 이후에도 실행될 live src 3개(pre_unblinding_audit.py L64·L121, "
    "rqint_package_gates.py L35, rqint_calibration.py L138·892·1328)는 기대값 갱신 없이는 R2 직후 자동 실패한다 "
    "— pre_unblinding_audit.py 는 개봉 전 필수 감사다. sap_version == '1.1' 을 assert 로 거는 곳도 6개다"
    "(confirmatory_oof_rep1.py:160 외 record_block_* 5개). (c) experiments/rqint/r3_package/sap/ 에 SAP 11모듈의 "
    "바이트 동일 사본이 있어(전건 identical_to_live true) freeze.py·decision.py 수정 시 즉시 발산한다 → R3 축자 "
    "'동결 해시로부터 동일 산출 확인' 충족에 패키지 재생성 필요. "
    "⑥ 선택지 정리(채택 0) — 충돌 A 3안(A-1 L581 한 줄 / A-2 sap_version 외부 주입 / A-3 manifest 후처리)과 "
    "충돌 B 3안(B-1 decision.py 7행 수정+스키마 분리 / B-2 무수정·manifest 필드 추가 / B-3 이번 회차 보류)을 "
    "비용·무결성·재현성 3축 비교표로 정리하고 안별 §8 문안을 영문+국문 3종씩 작성했다. B 3안에는 D20 4요구"
    "(전후 문자열·전후 sha16·라인 diff·11모듈 불변 명시) ○/× 표와 '어느 sha16 을 가리키는가'(B-1 = decision.py + "
    "manifest / B-2 = manifest 만 / B-3 = 없음)를 명시했다. 러너는 어느 안도 채택하지 않았다. "
    "⑦ §8 개정문 확정 문안 초안 — docs/99_amendment_section8_draft.md. 빈칸 4개 = 2026-08-10 / <EXTERNAL-REVIEWER> / "
    "Ph.D. / Gyeongnam Intelligence Innovation Center (GIIC), 출처 = "
    "v3_Multimodal/config/reviewer_identity_resolved.json:blanks_resolved(블록 AH, 서명본 SIGNED.pdf sha256 "
    "161dd9d2290df32befed6ca9e028799f60a4cab3a84598db22728a7d8678ea3f 축자). 승인일 2026-08-10 != 서명일 "
    "2026-08-12 이며 부록 B 2026-08-06 과 표지 2026-08-10 이 갈렸을 때 표지 기준으로 통일했고 서명본에서 "
    "정정되지 않았다는 확정 근거를 주석 병기했다. 해시 문장은 {A안}·{B안} 플레이스홀더. docs/55b 는 0바이트. "
    "⑧ R5 두 요소 추가 — R5 는 현재 partial 인 유일한 승인조건이다. 실측(F-R5GAP) = 공개일자 2026-07-27 은 §8 "
    "안에 없고 §2 본문 L137 1곳뿐이며 노출 인원은 문서 전체에 없다. 초안에 공개일자 2026-07-27 과 노출 인원 문안"
    "(방향을 아는 사람 = 실명 2명 / 외부 검토자는 부호 4건 존재·동일 사실만 고지받고 방향은 모름 / 4건 중 3건은 "
    "2026-07-28 부터 공개 저장소 열람 가능)을 영문+국문으로 넣었다. 공개 근거 = sign_disclosure_matrix.json: "
    "public_exposure_verification 스칼라 부호 리터럴 3개(/repeats/2/sign·/repeats/3/sign·/consensus/sign), "
    "in_pushed_commit true, 원격 tip bdb65c8, 커밋 878b3ba(2026-07-28 15:58:58 KST), push reflog "
    "2026-07-28 16:10:52 +0900. 반복1 은 푸시된 커밋에 없다. "
    "⑨ ★ R5 실측 불일치 1건 — '실명 2명' 중 지도교수 항목은 sign_disclosure_matrix.json:advisor_route."
    "determination = unknown_as_of_2026-08-06 이고 sign_lexeme_hits_in_correspondence 가 빈 배열이다(서신 "
    "기록에서 부호 전달 미확인, open_questions[0] 축자). 지시서가 사용자 확정 문안으로 지정했으므로 초안 본문은 "
    "그대로 쓰되 초안 §6 과 리포트 §5 에 두 선택지(근거 보강 후 '2명' 유지 / '연구자 1명 확정, 지도교수 전달 여부 "
    "미확인' 으로 조정)를 정리했다. 러너는 채택하지 않았다. "
    "⑩ still_unspecified 3건 종결안 초안 — v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json "
    "(status = draft_not_frozen, is_sap_freeze false, supersedes null, v0 는 0바이트). B = 동전 벡터 수 100,000"
    "(참조분포 200,000, 사용자 확정 2026-08-24, F-BMEAS 19.4887 h ≤ 24 h → D15 하향 미발동) / C0~C3 복제수 "
    "primary 2,000 · sensitivity 1,000 (★ 결과를 보고 정한 것이 아니다 — calibration_design.json 동결 "
    "2026-08-12 22:25:21 KST 가 첫 시뮬레이션 세션 시작 22:46:44 KST 보다 21분 23초 앞선다) / r3_second_party = "
    "<SECOND-PARTY> 확정(correspondence[19] <GMAIL-MSGID> 2026-08-12 18:34:47 KST 축자 승인 + "
    "r3_second_party_freeze.json 0624d3ddb852c4e9). "
    "⑪ ★ 누락 발견 — 블록 AG 가 종결했어야 할 r3_second_party 가 rqint_procedure_decisions_v0.json 에 "
    "반영되지 않았다(still_unspecified[4] 가 여전히 escalated_awaiting_advisor_reply · confirmed_second_party "
    "null). 항목의 note 는 승인 서신 접수 이전 기준이라 stale 이다. 본 블록은 v0 를 고치지 않고 누락 사실만 "
    "기록했다. 부수 확인 — 'ledger.open_question.r3_second_party' 는 존재하지 않는 키다(최상위 11키에 "
    "open_question 없음, 실측) → 조치 불요. v0 의 stale 3건(R1 pending vs r1_passed true / R6 pending vs 블록 AC "
    "수행 / R5 partial)도 고치지 않고 기록만 했다. "
    "⑫ 해시 원장 스펙 + R2 이행 대조표 — docs/99_r2_hash_registry_spec.md. 범주 5개 총 45행에 현재 sha256 실측 "
    "병기 + '이미 어디에 등재됐는가/아직 없는가' 마지막 열. 미등재 11건 = 실질 신규 등재 6건 + append-only 4건"
    "(고정 해시 동결 불가 → 스냅샷 지위) + 표기 정정 1건. 그중 reviewer_identity_resolved.json(§8 빈칸 값 원천)과 "
    "sign_disclosure_matrix.json(R5 노출 인원 근거)이 미등재인 것이 가장 중요하다. 이행 대조표 8행 = R2·R4·R5·"
    "D19·D20·D21·D22 + KS 신설. R4 는 SAP 1.2 §RQ-int 다중성 소절 2문장 + manifest.frozen_parameters."
    "decision_A11.multiplicity 문자열 총 3곳 지정(holm() 코드 수정 불필요 — A/B 두 판은 같은 함수를 입력만 달리 "
    "호출해 얻는다). D19 는 C4 실측 검정력 tau0.01 0.250 / tau0.02 0.735 / tau0.03 0.9725(각 R=400, alpha=0.05 "
    "기각률) → tau=0.02 는 3단 사다리 중간단(0.50~0.80) = 검정력·유보문장 병기, 최하단 조항 미발동, 0.80 미달이라 "
    "관례적 충족 주장 금지. D21 은 확인 완료(gin_seed_freeze.json 10828447c6d33118: 대표 unit 3 = (201,4)(202,1)"
    "(203,0), training_seeds_ordered 5, confirmatory_seed_prefix 3, stability_seeds 5) — RQ-int 는 3 seed × 3 "
    "repeat 이므로 SAP 1.2 는 어느 5/3 인지 명시해야 한다. D22 는 sap/rqint.py TEST_STATISTIC 에 'additive "
    "surrogate 대체 금지(A6 계승)' 가 이미 있어 e_g 선형화 = 보조 진단 전용 1문장 추가로 족하다. KS 신설 항목 = "
    "C0:prop KS p 0.052446940943157605(여유 +0.0024469)이 기준 0.05 바로 위임을 R2 문면에 정직 기재. "
    "AF-DEV-1 미상신 결정은 docs/33 항목50 참조만(중복 기입 0). "
    "⑬ 무결성 착수=종료 불변 — sap_version 1.1, manifest sha16 756d485feb4715e9, SAP 11모듈 0바이트, freeze.py "
    "미실행·0바이트, decision.py 0바이트, config 동결파일 16종 전건 0바이트, docs/55b 0바이트, 블록 AC 4파일 + "
    "AD 2파일 + AI 4종 + AJ 산출물 0바이트, sap/rqint.py sha16 eb842bc98140e9c5 불변, _sealed/ guard 275종"
    "(access.log 제외)/291종(포함) 및 stat-only 스냅샷 착수=종료 동일, HEAD 566f487, 커밋 21 불변. "
    "⑭ 미실행 — 동결 0(sap_version 승격 0 · 매니페스트 재생성 0 · 원장 신규 등재 0), 채택 0(충돌 A·B 안 0 · B 정의 "
    "동결 0 · still_unspecified 3건 동결 0), 개봉 0(unblinding_performed false · open_sealed 0 · emit_sign 0 · "
    "decision.py 호출·import 0), 계산 0(모델 학습·추론·순열·새 추정 0 · 확증 예측·OOF 로드 0), GIN 착수 0"
    "(gin_start_still_blocked true), 네트워크 0, data/raw 변경 0, git commit·push 0."
  ),
  "artifacts": [
    "docs/99_r2_freeze_prep_prompt_for_vscode.md (지시서)",
    "docs/99_r2_freeze_prep_report.md",
    "docs/99_amendment_section8_draft.md (sha256 29b2d8f401afa0dc97782c32b6875d22baf4527d1f95b2562de8c02dd337bf54)",
    "docs/99_r2_hash_registry_spec.md",
    "v3_Multimodal/config/rqint_procedure_decisions_v1.DRAFT.json",
    "experiments/rqint/r2_prep/facts.json",
    "experiments/rqint/r2_prep/impact.json",
    "experiments/rqint/r2_prep/registry.json",
    "experiments/rqint/r2_prep/verify.json",
    "docs/33 항목52",
  ],
  "first_look": ("N — 봉인 stat-only(291종 스냅샷 착수=종료 동일) · open_sealed 0 · 확증 예측·OOF 로드 0 · "
                 "새 부호 산출 0 · emit_sign 0. 조회가 아니므로 docs/45 §5 확증 조회 대장에 행을 추가하지 않는다."),
})

led["authoritative_sources"].append(
  "docs/99 (R2 준비 — SAP 1.2 재동결 설계 확정 지시서: 문면 충돌 2건 실측 · 선택지 정리 · §8 문안 초안 · "
  "still_unspecified 3건 종결안 초안 · 해시 원장 스펙 — 블록 AK 근거 · 실행순서 ⑦(R2)의 앞단 · 무동결)")

# ★ 원본 포맷(indent=2 + 말미 개행) 유지 — 접두 entry 바이트 보존
with open(pled, "w", encoding="utf-8") as f:
    f.write(json.dumps(led, ensure_ascii=False, indent=2) + "\n")

# ── 기입 후 불변 확인
led2 = json.load(open(pled, encoding="utf-8"))
assert list(led2.keys()) == keys_before, "ledger 최상위 키 변경"
assert len(led2["timeline"]) == 50, len(led2["timeline"])
assert len(led2["authoritative_sources"]) == 27
assert len(led2["correspondence"]) == corr_before == 22
assert list(led2["first_look_register"].keys()) == flr_keys_before
assert len(led2["first_look_register"]["rows"]) == flr_rows_before == 4

# docs/33 접두사 바이트 동일
raw33 = open(os.path.join(ROOT, D33), "rb").read()
assert hashlib.sha256(raw33[:d33_before_bytes]).hexdigest() == before[D33], "docs/33 접두사 변경!"
N2 = dn.next_item_number(os.path.join(ROOT, D33))
assert N2 == 53, N2

print("docs/33 item:", N, "-> next now", N2, "| prefix preserved: True")
print("docs/45 bytes:", d45_before_bytes, "->", os.path.getsize(os.path.join(ROOT, D45)))
print("ledger timeline:", n_tl, "->", len(led2["timeline"]),
      "| auth:", n_auth, "->", len(led2["authoritative_sources"]),
      "| corr:", len(led2["correspondence"]), "| keys:", len(led2))
json.dump({"before": before, "docs33_bytes_before": d33_before_bytes,
           "docs45_bytes_before": d45_before_bytes,
           "docs45_inserted_line_indices_0based": [66, 143, 144],
           "item_number": N},
          open(os.path.join(ROOT, "experiments/rqint/r2_prep/doc_inserts.json"), "w",
               encoding="utf-8"), ensure_ascii=False, indent=1)
