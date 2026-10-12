# [블록 AB] RQ-int 외부 통계검토 회신 접수 기록 — 수행 리포트

- 지시서: `docs/86_rqint_reviewer_response_record_prompt_for_vscode.md` (초판 2026-08-12 14:38 + `## AB-5` append)
- 수행: Claude Code (VS Code) · 2026-08-14 13:53 KST
- 결과: **완료** (자동 종료검증 27항목 전건 PASS · 미이행 0)

---

## 1. 게이트/선행조건

| 항목 | 기대 | 실측 | 판정 |
|---|---|---|---|
| 회신 원본 `docs/RQint_Reviewer_Response_<EXTERNAL-REVIEWER>_20260810.docx` | 실재 · sha256 실측 기록 | `0c29ddf201eb6751a47f420d0c405fdafd0a6baf0ae7705059b0a85fa296aa99` · 63,649 B | PASS |
| 회신 원본 판별자 | `"reverts to the paired scaffold-cluster BCa interval"` 존재 | 존재(§10 문단 말미) · `Approved with revisions` **2회** | PASS |
| 서명 요청본 `docs/RQint_Reviewer_Record_Signature_20260812.docx` | 실재 · sha256 실측 | `bfb01bfeae87ee3bb642bae33fad6697a2d5c48829b9cfaf69c054d255ea08c3` | PASS |
| 대응표 `docs/84` · 발송 초안 `docs/85` | 실재 | 실재 | PASS |
| A6 모듈 `sap/signflip.py` | 무수정 대조 | `3de1223585ae0f97…` 착수=종료 동일(**0바이트**) | PASS |
| SAP `manifest.json` | sha16 `756d485feb4715e9` · `sap_version` 1.1 | `756d485feb4715e9` · `1.1` · 착수=종료 동일 | PASS |
| `ladder_freeze.json` | sha16 `b885585aefbabb32` | `b885585aefbabb32` 불변 | PASS |
| `gin_seed_freeze.json` | `representative_units` `[[201,4],[202,1],[203,0]]` · `confirmatory_seed_prefix` `[42,1,2]` | 전건 일치(+ `training_seeds_ordered` `[42,1,2,3,4]`) | PASS |
| 개봉 상태 | `unblinding_performed` **false** | `false` (착수=종료) | PASS |
| sealed guard | 275종(access.log 제외) / 291종(포함) | **275 / 291** · stat-only 스냅샷 sha256 착수=종료 동일 | PASS |
| `docs/33` 마지막 항목 | **42**(다음 43) | **44**(다음 **45**) | ★ **불일치 → 중단 조건대로 중단하지 않고 실측값 45로 진행 + cowork FACTS 결함 보고** |
| 1회성 조건 | `rqint_procedure_decisions_v0.json` 부재 | 부재 | PASS |

**중단 조건 4건 전부 미발동** — `signflip.py` 절댓값 존재 · manifest sha16 일치 · sealed guard 종수 불변 ·
회신 원본 6개 값 전건 추출 성공.

---

## 2. 실행한 명령

```bash
# 착수 게이트 (해시·동결값·봉인 stat 스냅샷·docs/33 번호 실측)
shasum -a 256 <대상 14파일>
python3 -c "…manifest sap_version / gin_seed_freeze / status 판독…"
python3 -c "…experiments/runs/*/_sealed/**/* stat-only 스냅샷…"   # 275 / 291

# 회신 원본 축자 판독 (zipfile → word/document.xml, cowork 요약 미사용)
python3 -c "…판별자·표지 표 6값·부록 B 4값 추출…"

# §9-1 A6 코드 실물 재확인 (AST · 0바이트 수정)
python3 -c "…ast.walk → count 대입문 · np.abs/abs · _EPS · 부등호…"

# D18 재현 (동결 파일에 적힌 명령을 그대로 실행)
python3 -c "import hashlib;print([int(hashlib.sha256(str(s).encode('ascii')).hexdigest(),16)%5 for s in (201,202,203)])"

# 본 기입
python3 v3_Multimodal/src/record_block_AB.py

# 종료 스윕
find . -type f -mmin -25 -not -path './.git/*' -not -path '*/__pycache__/*'
python3 -c "…difflib 로 추가행만 격리 후 부호어·봉인키 스캔…"
git status --porcelain ; git rev-parse --short HEAD ; git rev-list --count HEAD
```

---

## 3. 산출물

- `v3_Multimodal/config/rqint_procedure_decisions_v0.json` — **신규**, 절차 결정 기록(**동결 아님**).
  21,502 B · sha256 `951b302a2d474361…`
- `experiments/provenance/ledger.json` — `external_reviews` **3→6** · `correspondence` **11→17(+6)** ·
  `timeline` **42→43** · `authoritative_sources` **19→21** · 최상위 키 11 불변.
  223,266 B → 248,214 B · sha256 `5c399365b59cc3ab…`
- `experiments/provenance/sign_disclosure_matrix.json` — `decisions_after` **2분할**(원 문자열 바이트 보존,
  경로 16객체에 신규 키 2종). 29,748 B → 230,332 B · sha256 `147d5d5f62edf84a…`
- `docs/33_prereg_deviation_log.md` — **항목 45** append(추가행 125 · 삭제 0).
  245,893 B → 257,853 B · sha256 `7e8b43445afd34da…`
- `docs/45_research_integrity_ledger.md` — §2 타임라인 +1행 · §5 문서 이력 +1(추가행 3 · 삭제 0).
  99,972 B → 104,499 B · sha256 `c2772aaa6fefab19…`
- `docs/85_advisor_mail_signature_request_20260812.md` — §후속 메일 실제 발송 기록 append(추가행 59 · 삭제 0).
  13,332 B → 16,633 B · sha256 `66e0bf2dba9dc4fc…`
- `docs/88_chatgpt_review5_triage.md` — §7 재정정 블록인용 1건(추가행 2 · 삭제 0 · **Y3 행 바이트 무수정**).
  21,824 B → 23,008 B · sha256 `8b982e3bd354c11b…`
- `v3_Multimodal/src/record_block_AB.py` — 기록 스크립트(재실행 가능 · 게이트·종료검증 내장)

---

## 4. 관측 (출처 경로 병기)

**회신 표지 표 6값 — 러너 축자 추출**(`docs/RQint_Reviewer_Response_<EXTERNAL-REVIEWER>_20260810.docx`
`word/document.xml`, cowork 요약 미사용)

| 필드 | 값 |
|---|---|
| Reviewer | `<EXTERNAL-REVIEWER>, Ph.D.` |
| Degree / statistical specialty | `Ph.D., Department of Information and Communications Engineering, KAIST — resampling-based inference, multiple testing, evaluation metrics for predictive models` |
| Affiliation | `Gyeongnam Intelligence Innovation Center (GIIC)` |
| Date of review | **`2026-08-10`** |
| Access to sealed confirmatory results | `None. §11.2의 results-blind 조건 하에 검토하였으며 …` |
| Overall determination | `Approved with revisions (조건부 승인)` |

- **날짜 불일치 1건** — 표지 `2026-08-10` / **부록 B `2026-08-06`**. 두 리터럴을 `date_discrepancy` 로
  **모두 보존**하고 표지 채택 근거를 병기했다(`ledger.external_reviews[5].date_discrepancy`).
- **부록 B 미기입 2칸** — `Affiliation` **공란**, `서명/일자` 미기입 → `signature_status =
  pending_as_of_2026-08-12` (`v3_Multimodal/config/rqint_procedure_decisions_v0.json`).

**§9-1 A6 코드 실물 재확인**(`v3_Multimodal/src/sap/signflip.py`:76 · AST 판독 · **0바이트 수정**)

- 축자 = `count = int(np.sum(np.abs(perm) >= abs(delta_obs) - _EPS))` — `np.abs(perm)` 와
  `abs(delta_obs)` **둘 다 존재**(AST 호출 목록 `['int','sum','abs','abs']`), 비교연산자 `GtE`.
- `_EPS` **실측 = `1e-12`**(`signflip.py`:40). 임계에서 **빼는** 방향이라 조건이 더 쉽게 참 →
  **카운트 증가 → `p = (1+count)/(B+1)` 증가 = 보수적**.
- 국문 정본 `docs/55b_rqint_external_statreview_package_v2.md`:195 = `양측 p = (1 + #{|Δ*| ≥ |Δ_obs|}) / (B + 1)`
  → 절댓값 존재.
- 판정 = `code_defect: false` · `document_only: true` · `scope: english_recipient_copy_only` ·
  **이미 산출된 ②③⑤⑥⑦ p-값 영향 0**.

**실측 재확인 3건**

| ID | 실측 | 출처 |
|---|---|---|
| D10 | scaffold group **732**(확증 3반복 전건 일치) | `experiments/runs/v3_confirm_rep{1,2,3}_seed20{1,2,3}/split_manifest.json` |
| D18 | 재현 명령 stdout **`[4, 1, 0]`** | `v3_Multimodal/config/gin_seed_freeze.json` `representative_unit_rule.reproduce` |
| D20 | `"RF primary confirmatory (RF-Morgan+seq)"` **14곳**(횟수만 기록, 수정 0) | `experiments/sap/manifest.json` |

**★ R5 는 실측 결과 `partial`**(회신·cowork 는 "§8 초안 이미 충족"으로 적었음) —
`docs/55b` §8(457~479행) 개정문 문면에 **기지 부호 4건은 있으나**
(`the only confirmatory information known to the investigators was the sign of Δ(M2b−M1b) for four artifacts`)
**공개일자 2026-07-27 은 §8 안에 없고**(문서 §2 `docs/55b`:137 에만 있음) **노출 인원 수는 문서 어디에도 없다**.
→ SAP 1.2 개정문에 두 요소를 추가해야 R5 완결(`rqint_procedure_decisions_v0.json` `conditions.R5.runner_measurement`).

**확정 1건 · 사전 명시 2건 · 미확정 5건**

- 확정 = 예비 학습시드 **`[3, 4]`**(기동결 `training_seeds_ordered` 미사용 접미부 기계 취득, 신규 추첨 0) +
  `stability_analysis_is_independent_replication: false`.
- 사전 명시(재문의 0 · `escalated_to_reviewer: false`) = **Y1** 계수 단위 = 실패한 원 확증시드 수 ·
  **Y2** R1 실패 폴백은 판정하지 않고 Holm 슬롯 `p = 1.0`. 둘 다 **GIN 학습 0회 · R1 감사 0회 시점 기록**.
  + `on_r1_failure_reconsult_reviewer: true`(§6-2 R1 "본 승인은 무효" 문면 근거).
- `still_unspecified` **5건** = `[0]` Y1 · `[1]` Y2 · `[2]` **B 값·정의** · `[3]` **C0~C3 복제 수** ·
  `[4]` **R3 제2자**. `[2]`·`[3]` 은 `blocking` 필드로 **R1 감사 착수를 막는다**고 명시.

**`decisions_after` 2분할**(`experiments/provenance/sign_disclosure_matrix.json`)

- 한정어 없는 맨 `"none"` 위치 **실측** = `rows[0].disclosure_routes[1]`(`public_repository_pushed`,
  반복1) **1건뿐**(전 경로 객체 스캔).
- 열거는 cowork 목록을 베끼지 않고 **기계 수집** — `ledger.json:timeline`(파싱 가능 38 entry) +
  `docs/33` 「기입 시각」 스탬프 보유 항목(13/45). 절단점은 **경로별 노출 시각**(local_commit 경로는
  `git log -1 --format=%cI 10687f4` = `2026-07-28T16:10:26+09:00` 실측).
- `advisor` 경로는 노출 시각이 `unknown_as_of_2026-08-06` → **절단점 없음 = 미판정**(추측 절단 0).
  반복1 `public_repository_pushed` 는 미공개 → 해당 없음.
- **판정 불변** — "부호를 근거로 한 설계·성공기준 변경 0" 유지. 부호 노출 이후
  `emit_sign_called = true` 인 timeline 결정 **0건**(기계 확인).

**서신·상신**(`ledger.correspondence` +6 · 네트워크 0)

- 2026-08-12 스레드 `<GMAIL-MSGID>` **5건** + R3 상신 **신규 스레드** `<GMAIL-MSGID>` 1건.
- 확정 3건 = ① 정정 통지는 서명 요청 문서에 합침 ② 국문 본문 그대로 제출 가능 ③ 회수 경로 = 교수님 전달 → 서명 → 회신.
- `forwarded_at` = **`unknown_as_of_2026-08-12`**(「전달 드리고」는 예정 표현 · 완료 통보 없음 — 추측 기입 0).
- `open_question.r3_second_party` = **2레코드**(이력 `not_yet_escalated` / 현행 `escalated_awaiting_advisor_reply`),
  현행에 **`supersedes` 포인터** 존재 · `resolved: false` · `advisor_reply: none_as_of_2026-08-12`.
- 발송본 본문 축자 기입은 지시서 코드블록과 **문자 단위 완전 일치**(406자, 추정·의역 0).

**`external_reviews` 3 → 6** — round 4(`docs/50`, **누락 보충**) + round 5(`docs/88`) + <EXTERNAL-REVIEWER> 박사.
기존 3항목 **객체 단위 무수정**(type 소급 부여 0). 5차는 **접수·분류 사실만** 기록(버킷 A 채택 확정은 SAP 1.2 블록).
충돌 2건 = **X1** BCa 유효 replicate 임계 게이트 **신설 안 함** · **X2** R1 실패 폴백 = 후보 C 회귀(ChatGPT 대안 기각).

---

## 5. 지시서 대비 편차·판단

1. **실행 순서 — 큐 맨 위(95)가 아니라 86 을 먼저 수행했다.** 근거 = `docs/95` §머리말 ★★
   *"실행 순서 = `docs/86`(블록 AB) → 본 블록(AH). … 반대로 하면 중복 기입이 된다"* 및 `docs/_next.md`
   2026-08-14 배너 *"권장 실행 순서 = `/실행 86` → 95 → 91 → 94 재개"*. 두 문서 모두 86 선행을 명시했고,
   순서를 지키지 않으면 `external_reviews` 중복 기입이 발생한다.
2. **cowork FACTS 결함 2건**(`docs/33` 항목45 §(9)·`ledger` `run_facts.cowork_facts_defects` 기입)
   - ① `docs/86` §1 은 `docs/33` 마지막 항목을 **42**(다음 43)로 적었으나 실측 마지막은 **44**
     (블록 AC 항목43 · 블록 AD 항목44). 중단 조건 규정대로 **중단하지 않고 실측값 45** 로 진행했다.
   - ② 종료검증 **#6 은 `external_reviews` 3→6**, **#11d 는 3→5** 로 서로 다르다. cowork 자기고지대로
     정본은 **6** 이며 #11d 의 5 는 AB-2-6 구간 부분합이다. **6 을 기준으로 검증**했다.
3. **R5 판정을 `already_satisfied` → `partial` 로 바꿨다.** 지시서 AB-2-2 는 R5 를 `already_satisfied` 로
   지정하면서 동시에 *"러너가 §8 문면을 실측 확인"* 하라고 했다. 실측 결과 §8 개정문에 공개일자와
   노출 인원이 없어 `partial` 이 정확하다. 지시서 지정값을 그대로 쓰면 **충족되지 않은 조건을 충족으로
   기록**하게 되므로 실측을 채택했고, 근거·측정값을 `conditions.R5.runner_measurement` 에 전부 남겼다
   (CLAUDE.md §10-2 「Methods 는 코드가 실제 수행하는 것만」·「음성 결과도 정직하게」 우선).
4. **`still_unspecified` 항목 수 5건의 구성.** 지시서 AB-2-4 의 미확정 표는 **3행**이지만 종료검증
   #11·#24 와 큐 요약은 **5건**을 요구한다. 두 요구를 동시에 만족하는 유일한 구성인
   `[Y1, Y2, B, C0~C3, R3]` 로 배열했다 — 이 순서라야 #11b 의 *"`still_unspecified[2]`·`[3]` 에
   `blocking` 필드"* 와 AB-2-4 의 *"1·2번(B·C0~C3)은 blocking 명시"* 가 **동시에** 성립한다.
   Y1·Y2 는 「회신서가 값을 지정하지 않은 항목」이라는 배열 의미에 부합하며, 각 항목의 `status` 가
   `resolved_by_our_pre_specified_reading_2026-08-12` 로 우리 종결 사실을 명시한다
   (`still_unspecified_semantics` 필드에 배열 의미를 문면화).
5. **R3 제2자에 대한 교수님 승인(2026-08-12 18:34:47 · 메시지 `<GMAIL-MSGID>`)은 본 블록에 기입하지
   않았다.** 지시서 AB-5 는 `approved: false` · `advisor_reply: none_as_of_2026-08-12` ·
   `resolved: false` · 레코드 **2건**을 종료검증(#23·#24·#28)으로 못박았고, 그 승인 기입은
   `docs/91`(블록 AG) ① 이 자기 범위로 지정하고 있다. 중복 기입을 피하려고 지시서를 그대로 따랐다
   — 기입된 값은 전부 `as_of_2026-08-12` 시점 한정 표기라 사실과 어긋나지 않는다.
6. **`docs/88` 은 파일 말미가 아니라 §7 본문 끝(수평선 앞)에 삽입했다.** 지시서가 *"§7 아래에 … append"*
   라고 지정했기 때문이다. 삽입행 2줄을 제거하면 착수 sha256 이 **정확히 복원**됨을 기계 증명했고,
   Y3 행은 바이트 무수정이다. (`docs/85` 는 지시서대로 **파일 말미 append** — 접두사 바이트 완전 보존.)
7. **`sign_disclosure_matrix.json` 이 29.7 KB → 230.3 KB 로 커졌다.** 지시서가 *"각 경로 객체에"*
   `decisions_after_enumerated`(항목마다 일시·근거 문서)를 넣으라고 지정해 16개 경로 객체에 열거 목록이
   중복 저장된 결과다. 경로마다 절단점이 달라 목록도 달라지므로 공유 참조로 축약하지 않고 지시서를
   문면대로 따랐다.
8. **예상 밖 파일 변경 1건(러너 무관)** — `docs/92_<SECOND-PARTY>_mail_r3_20260812.md` 의 mtime 이
   **2026-08-14 13:37:41**(본 스크립트 실행 13:53:25 이전)로 갱신돼 있다. 본 블록의 스크립트·명령은
   `docs/92` 를 참조하지 않는다(`grep` 0건). 러너 외 편집으로 보이며 사실만 기록한다.

**충돌 없음** — 지시서 ↔ `CLAUDE.md` 충돌은 3번(R5 판정)이 유일하며, 지시서 자신이 실측을 지시했으므로
실질 충돌이 아니다.

---

## 6. 종료검증 결과 (28항 = 초판 21 + AB-5 7)

자동 검증 **27항 전건 PASS**(스크립트 내장). 나머지 3항은 별도 명령으로 확인:

| # | 결과 |
|---|---|
| 18 전수 스윕 | PASS — 최근 25분 내 수정 = 기입 대상 7 + 기록 스크립트 1. **예상 밖 1건**(`docs/92`, 러너 무관 — §5-8) |
| 19 추가분 스캔 | PASS — 4개 문서 추가행(125/3/59/2)·`ledger` 추가분·`signmat` 신규 키·결정 JSON 전부 **부호어 0 · 봉인 수치 키 0 · 삭제행 0** |
| 20 미실행 확인 | PASS — `emit_sign` 0 · `decision.py` 호출 0 · 모델 학습·추론 0 · 네트워크(Gmail 재조회) 0 · `git commit`/`push` 0(HEAD `566f487` · 커밋 수 **21** 불변) |
| 27 발송본 축자 | PASS — 지시서 코드블록 ↔ `docs/85` append 본문 **문자 단위 완전 일치**(406자) |

**미이행 목록**: 없음. (범위 밖으로 남긴 것 = RQ-int 구현 확정 · R1 캘리브레이션 감사 · SAP 1.2 재동결 ·
`manifest` `model_family` 정정·erratum · `B` 확정 · GIN 학습 · 개봉 · 레버리지 진단 λ·ρ · 검토자 재발송
— 전부 지시서 「이 블록에서 하지 않는 것」에 명시된 항목이다.)

---

## 7. 다음 액션 제안

1. **`/실행 95`(블록 AH)** — 본 블록이 `external_reviews` 를 6으로 만들고 `external_reviewer_identity`
   를 신원·소속·검토일까지 supersede 해소했으므로, AH 는 설계대로 **서명 사실만** 얹으면 된다
   (AH-4 배너의 「AB 가 이미 돌았다면 live 실측 후 멱등 처리」 분기가 그대로 적용된다).
2. **`docs/91`(블록 AG)** 에서 R3 제2자 교수님 승인(2026-08-12 18:34:47 · `<GMAIL-MSGID>`)을 기입할 때
   `rqint_procedure_decisions_v0.json` `still_unspecified[4]` 와 `ledger` `open_question.r3_second_party`
   **두 곳**을 supersede 대상으로 잡아야 한다(현재 값 = `escalated_awaiting_advisor_reply` · `resolved: false`).
3. **cowork 확인 요망 2건** — ① **R5 = `partial`**(§8 개정문에 공개일자·노출 인원 추가 필요)을 SAP 1.2 동결
   블록 지시서에 반영할 것 ② `ledger.timeline` 에 **블록 AC·AD entry 가 없다**(`docs/33` 항목43·44 와
   `docs/45` 문서 이력에는 존재). 본 블록은 append-only 규약상 손대지 않았다.
