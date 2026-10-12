#!/usr/bin/env python3
"""블록 AI 기입 3곳 — docs/33 신규 항목(번호 실측) · docs/45 §2·§5 · ledger.json.
append-only · 기존 문면 삭제 0 · 소급 수정 0. 멱등하지 않으므로 1회만 실행한다."""
import os, sys, json, hashlib
from datetime import datetime, timezone, timedelta
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))
import doc_numbering as dn
OUT = os.path.join(ROOT, "experiments", "rqint", "b_dryrun")
KST = timezone(timedelta(hours=9))
J = lambda p: json.load(open(p, encoding="utf-8"))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

stair = J(os.path.join(OUT, "stair.json"))
dec = J(os.path.join(OUT, "decisive.json"))
pre_p = os.path.join(ROOT, "v3_Multimodal", "config", "b_dryrun_prespec.json")
pre_sha = sha(pre_p)
r = dec["result"]
now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

P33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
P45 = os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")
PLED = os.path.join(ROOT, "experiments", "provenance", "ledger.json")
b33, b45 = sha(P33), sha(P45)

n = dn.next_item_number(P33)
sw, sl_ = stair["u_wall_stats"], stair["u_loop_stats"]
pa, pb = stair["projection"]["interp_a_100000"], stair["projection"]["interp_b_50000"]
srows = stair["stair_rows"]
step = " · ".join(f"n={x['n_coin_vectors']} wall **{x['wall_seconds']:.2f} s** û_wall {x['u_wall_per_coin']:.6f}"
                  for x in srows)
premise_ok = pa["vs_24h"] == "exceeds" and pa["extrapolation_allowed"]
dec_h = dec["wall_hours_total"]
a_from_dec = 2.0 * dec["wall_seconds_total"] - 1000 * stair["u_hat_primary"]

item = f"""{n}. **전규모 합성 드라이런 벽시계 계측 → `B` 후보 산출 (블록 AI — 계측 전용 · `B` 동결 0)**:

   - **① 배경 — 이 블록이 R2 보다 앞이다**: `docs/84` §5 실행순서는 **⑥ = 전규모 드라이런 벽시계 → `B` 확정**, **⑦ = SAP 1.2 재동결(R2)** 이고, R2 의 동결 대상 목록에는 축자로 "구현 코드·난수시드·**B**·시드집합·대표폴드·실패처리 규칙을 GIN 학습 착수 이전에 v1.2 로 동결"이 들어 있다. 그런데 `sap/rqint.py` 의 `B_DEFINITION_STATUS` 는 여전히 **`still_unspecified`** 다. ⑥ 을 건너뛰면 **R2 가 빈칸을 동결**하므로 본 블록을 먼저 수행했다. ★ **본 블록은 `B` 를 동결하지 않는다** — 계측·후보값 산출까지이고 문면 동결은 R2 의 일이며 `sap/rqint.py` 는 **0바이트 수정**이다.
   - **② 두 해석과 비용 2배 차이**: `pair_complement=True` 라 **참조분포 크기 = 2 × `n_coin_vectors`** 이므로 `B` 의 두 해석은 정확히 2배 차이난다 — **(가) `B` = `n_coin_vectors`** → 동전 100,000 / 참조분포 200,000, **(나) `B` = 참조분포 크기** → 동전 50,000 / 참조분포 100,000. `rqint_test` 는 **직렬 루프**(`for b in range(n_coin_vectors)`, 병렬 파라미터 없음)라 워커 수로 나눠지지 않는다.
   - **③ 수렴 논증은 측정 전에 사전명시했다**: 사전명시 파일 **`v3_Multimodal/config/b_dryrun_prespec.json`**(sha256 `{pre_sha[:16]}…` · 동결 **{J(pre_p)['frozen_at_kst']}** · **SAP 등재 아님**)에 (가) 41.8 h > 24 h → D15 로 50,000 하향 / (나) 하향 불필요 = 동전 50,000 → **두 해석이 같은 구성(동전 50,000)으로 수렴**한다는 논증과, **외삽 허용 밴드 [18 h, 30 h]**(24 h 의 [0.75, 1.25]) 밖에서만 외삽 판정을 허용한다는 규칙을 **어떤 측정도 보기 전에** 고정했다. 동결 시각 **< 첫 측정 시각 {stair['env']['when_kst']}** 이 파일시스템 birth time 으로 증명된다. ★ 같은 파일에 **전건 붕괴 시의 처리(`contingency_if_premise_fails`)도 측정 전에** 함께 규정했다 — 사후에 유리한 해석을 고르지 못하게 하기 위함이다.
   - **④ 단가 계측(단독 실행 · 동시 워커 0 · AC 전원 · 효과주입 0 · 전규모 fixture N 1,092 · K 370 · G 732)**: 계단 3점 = {step}. **선형성 상대 산포 {sw['relative_spread']:.4f}** (기준 ≤ 0.10) → **통과**. `û` = 3점 중앙값 **{stair['u_hat_primary']:.6f} s/동전**(주루프 기준 `per_permutation_seconds` 중앙값 {sl_['median']:.6f} s). `F-C4UNIT` 1.506339 s(18워커 경합 하 **상한**) 대비 **{stair['ratio_u_hat_over_C4']:.3f}배**, 블록 AD `F_UNIT_FULL` 0.716650 s 대비 **{stair['ratio_u_hat_over_F_UNIT_FULL']:.3f}배** — 단독 실행이 경합 하 측정치보다 빠르다는 예상과 부합한다.
   - **⑤ ★ 수렴 논증의 전건이 외삽으로 성립하지 않았다(사전명시된 처리 그대로 이행)**: 실측 `û` 로 계산한 (가) 100,000 동전의 추정 벽시계는 **{pa['T_hat_hours']:.2f} h** 로 사전명시 밴드 **[18, 30] h 안**이다 → **외삽 판정 금지**(밴드 안이면 실주행으로만 판정한다는 사전 규칙). 즉 `docs/97` §2-1 이 참고로 든 41.8 h(단가 1.506 상한 기준)는 **단독 실행 실측에서 재현되지 않았고**, "(가) > 24 h" 라는 전건은 **미확정**이다. 사전명시 `contingency_if_premise_fails` 에 따라 ⓐ 전건 붕괴 사실을 그대로 기록하고, ⓑ 결정적 드라이런(동전 50,000)은 **예정대로 수행**했으며, ⓒ (가) 의 24 h 판정은 **본 블록에서 확정하지 않고 상신 사항으로 남긴다**(100,000 동전 실주행은 본 블록 예산 밖 — **자체 구제 0 · 구성 변경 0**). 참고로 블록 AD 가 적은 "드라이런 100,000 **3.88 h** / 50,000 1.94 h" 추정은 `F_THRU_FULL`(18워커 처리량)을 쓴 값이라 **직렬 함수인 `rqint_test` 에는 적용되지 않는다**(F-SERIAL) — 본 계측이 이를 대체한다.
   - **⑥ 결정적 드라이런 실측(동전 50,000 · `pair_complement=True` · `threads_limit` 1 · 단독 · AC 전원 · 24 h 하드 캡)**: 총 벽시계 **{dec_h:.3f} h**({dec['wall_seconds_total']:.1f} s) · 캡 도달 **{'예' if dec['cap_hit'] else '아니오'}** · 실현 참조분포 **{r['n_permutation_values']:,}**(= 2 × {r['n_coin_vectors']:,}, 기대와 일치) · 여집합 항등식 감사 **{r['complement_audit']['draws_checked']} draw · 실패 {r['complement_audit']['failures']} · max_abs_dev {r['complement_audit']['max_abs_dev']}** · `complement_identity_used` **{str(r['complement_identity_used']).lower()}** · RAM peak **{dec['ram_samples_max_gib']:.2f} GiB**(게이트 30.72 GiB, 브리치 {len(dec['ram_breaches'])}건). → **D15 판정: 동전 50,000 구성은 24 h 이내({dec_h:.2f} h)**.
   - **⑦ 추정 p 와 몬테카를로 SE 병기(D15 후단 이행)**: `T_obs` **{r['T_obs']:.8f}** · `p` **{r['p_two_sided']:.6f}** · **`SE_MC = sqrt( p·(1−p) / n_permutation_values )` = {r['se_mc']:.6g}**(축자 식 그대로) · `count_abs_ge_obs` {r['count_abs_ge_obs']:,} · p 공식 = `{r['p_formula']}`. ★ **이 `p` 는 100% 합성 예측 위의 값이라 확증 결과가 아니다** — 귀무 구성(효과 주입 0)에서 나온 타이밍용 산출이며 어떤 가설 판정에도 쓰지 않는다.
   - **⑧ R2 에 넘길 `B` 후보값(동결·확정 아님)**: **(나) 해석(= `B` 는 참조분포 크기 `n_permutation_values`)** 를 택하면 `B` = 100,000 = **동전 50,000**, 실측 **{dec_h:.2f} h < 24 h** 로 D15 의 하향 조건이 발동하지 않는다 → **후보값 `B` = 100,000(참조분포 기준)**. **(가) 해석(= `B` 는 동전 수)** 를 택하면 동전 100,000 이 필요하고, 본 실측에서 파생한 2배 외삽은 **≈ {a_from_dec/3600:.2f} h**(= 2·T_obs(50,000) − 1,000·û)로 **24 h 이내로 보이나 밴드 안이라 외삽 판정이 금지**돼 있다 → **미확정 · 상신**. 검토자 §9-2 의 함의 단가 1.08 s/동전은 (가) ≈ 30 h 를 함의해 **검토자가 `B` 를 동전 수로 상정했음**을 시사하지만, 실측 단가가 그보다 낮으므로 **해석 확정은 R2 의 일**이다.
   - **⑨ AI-0 — cowork 판정 3건 수용 기록**: ⓐ **AF-DEV-1(A12 적응적 중지 미이행)은 검토자에게 상신하지 않는다** — 사용자 결정 2026-08-18. 근거 = R1 판정 무영향(C4 는 `F-ACC` 미적용이고 `r1_passed` 는 C0~C3 8셀에서 산출) + 설계 **완화가 아니라 초과 수행**. ★ "왜 통보하지 않았는가"가 나중에 재점이 되지 않도록 **결정 사실과 근거를 여기 남긴다**. ⓑ **항목48 ⑨ 의 AF 진도 기술("`C0:prop` 1,440/2,000 중단 상태 유지")은 stale 이며 정본은 항목49 ②** — 중단 4건 = 1,440 · 1,512 · 215 · 1,569 이고 최종 완주는 2026-08-18 11:55:10 이다. **항목48 문면은 무수정**(append-only)이고 본 줄이 supersede 포인터다. ⓒ **`docs/94` report2 §7 정정 2건** — §7-2 "R1 충족으로 **R2(SAP 1.2 재동결)** 가 다음 관문이다"는 **틀렸다**(⑥ 이 R2 보다 앞, 위 ①), §7-3 "큐 잔여 = `docs/86` · `docs/95` · `docs/91`"은 셋 다 2026-08-14 완료라 **stale** 이다(원장 미오염 — 제안문에 그침). **두 건 모두 리포트 문면은 무수정**이고 정정 기록은 여기와 `docs/97_b_definition_dryrun_report.md` §5 에 남긴다.
   - **⑩ 무결성 — 착수=종료 불변**: SAP 등재 **11모듈 0바이트** · `manifest.json` sha16 **`756d485feb4715e9`** · `sap_version` **1.1** · 블록 AC 4파일 + AD 2파일 **0바이트** · ★ **`sap/rqint.py` sha256 `eb842bc98140e9c5…` 착수=종료 동일**(`B_DEFINITION_STATUS` 리터럴 무수정) · `_sealed/` guard **275종(access.log 제외) / 291종(포함)** 및 stat-only 스냅샷 sha256 **완전 동일** · HEAD `566f487` · 커밋 21 불변. 본 블록이 만든 파일 = `v3_Multimodal/config/b_dryrun_prespec.json` · `v3_Multimodal/src/b_dryrun.py` · `experiments/rqint/b_dryrun/` 산출 뿐이다.
   - **⑪ 시드 — 신규 추첨 0**: `SEED_RULE_TEXT` 의 probe 파생 규약(`BASE_SEED + k·1,000,000`)을 그대로 이어 계단 = 850260813·850260814·850260815, 결정적 드라이런 = **860260813**(동전 RNG = +900,000,000). **확증 시드 공간(8개)** 및 **블록 AF `rep_seed` 13,200개**와 **교집합 0**(동전 시드도 교집합 0) 을 assert 로 확인했다.
   - **⑫ ★ 본 기입은 어떤 착수 허가도 아니다**: **`B` 문면 동결 0**(`B_definition_status` = `still_unspecified` 유지) · **SAP 1.2 재동결 0** · **개봉 0**(`unblinding_performed` false · `open_sealed` 0 · `emit_sign` 0 · `decision.py` 호출 0) · **확증 예측·OOF 로드 0**(`confirmatory_predictions_loaded` false · 예측 **100% 합성** · 효과 주입 0) · **GIN 학습·착수 0**(`gin_start_still_blocked` true) · **네트워크 0** · **`data/raw/` 변경 0** · **git commit·push 0**. R2·R3·`B` 확정·개봉·GIN 착수는 **전부 차단 유지**다.

> 지시서 = `docs/97_b_definition_dryrun_prompt_for_vscode.md` · 리포트 = `docs/97_b_definition_dryrun_report.md` ·
사전명시(동결, SAP 등재 아님) = `v3_Multimodal/config/b_dryrun_prespec.json`(sha256 `{pre_sha[:16]}` · 동결 {J(pre_p)['frozen_at_kst']}) ·
산출 = `experiments/rqint/b_dryrun/stair.json` · `decisive.json` · `facts.json` · `verify.json` · `integrity.json` · `decisive_heartbeat.jsonl` ·
러너 = `v3_Multimodal/src/b_dryrun.py`(신규 · **`sap/` 밖** · AST 스캔상 데이터 경로 `master_X.parquet`·`master_Y.parquet` 2개뿐) ·
무수정 대조 = SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · 블록 AC 4파일 + AD 2파일 **0바이트** · `sap/rqint.py` **0바이트** ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 sha256 착수=종료 동일). **미실행**: 위 ⑫ 전항. 기입 시각 {now}.

---
"""

t33 = open(P33, encoding="utf-8").read()
assert not t33.rstrip().endswith(item.rstrip()), "중복 기입"
new33 = t33.rstrip("\n") + "\n\n" + item
open(P33, "w", encoding="utf-8").write(new33)
d = dn.assert_no_duplicate_item_numbers(P33)
assert d["pass"], d
assert dn.item_numbers(new33)[-1] == n

# ── docs/45 §2 (+1행) · §5 문서이력 (+1행) ────────────────────────────────────
row45 = (f"| 2026-08-22 {dec['env']['when_kst'][11:19]} KST | **블록 AI(계측 전용 · `B` 동결 0 · 확증 계산 0)** "
         f"**전규모 합성 드라이런 벽시계 계측 → `B` 후보 산출** — `docs/84` §5 실행순서 **⑥**(R2 보다 **앞**). "
         f"R2 동결 대상에 `B` 가 들어 있는데 `B_DEFINITION_STATUS` 가 `still_unspecified` 라 ⑥ 을 건너뛰면 R2 가 빈칸을 동결한다. "
         f"`pair_complement=True` 이므로 **(가) `B`=동전 수** → 100,000 동전 / **(나) `B`=참조분포 크기** → 50,000 동전으로 비용이 **정확히 2배** 차이난다. "
         f"수렴 논증·외삽 허용 밴드 **[18 h, 30 h]**·전건 붕괴 시 처리를 **측정 전에** `b_dryrun_prespec.json`(sha256 `{pre_sha[:16]}` · 동결 {J(pre_p)['frozen_at_kst']} · **SAP 등재 아님**)로 고정했다. "
         f"**단가 계측**(단독·동시 워커 0·AC·효과주입 0·전규모 N1,092·K370·G732) 계단 3점 {{200,500,1000}} → 선형성 상대 산포 **{sw['relative_spread']:.4f}**(≤0.10 통과) · "
         f"`û` = **{stair['u_hat_primary']:.6f} s/동전**(F-C4UNIT 1.506339 의 **{stair['ratio_u_hat_over_C4']:.3f}배** — 18워커 경합 상한 대비 단독 실행). "
         f"★ **수렴 논증의 전건이 외삽으로 성립하지 않았다** — (가) 100,000 동전 추정 **{pa['T_hat_hours']:.2f} h** 가 사전명시 밴드 안이라 **외삽 판정 금지** → (가) 는 **미확정·상신**, 자체 구제 0(구성 변경 0). "
         f"**결정적 드라이런**(동전 50,000 · 24 h 하드 캡) 총 벽시계 **{dec_h:.3f} h** · 캡 도달 **{'예' if dec['cap_hit'] else '아니오'}** · 실현 참조분포 **{r['n_permutation_values']:,}** · "
         f"여집합 항등식 감사 {r['complement_audit']['draws_checked']} draw **실패 {r['complement_audit']['failures']}** · RAM peak {dec['ram_samples_max_gib']:.2f} GiB(브리치 {len(dec['ram_breaches'])}). "
         f"**D15 후단 이행** — `p` **{r['p_two_sided']:.6f}** · **`SE_MC = sqrt(p(1−p)/n_permutation_values)` = {r['se_mc']:.6g}**(★ **합성 예측 위의 값 = 확증 결과 아님**). "
         f"**R2 에 넘길 후보** = (나) 해석이면 `B` = 100,000(참조분포) = 동전 50,000, 실측 24 h 이내로 D15 하향 미발동. "
         f"cowork 판정 3건 수용 기입(AF-DEV-1 **미상신** 결정과 근거 · 항목48 ⑨ → **항목49 ② supersede 포인터** · `docs/94` report2 **§7-2·§7-3 정정**, 두 리포트 문면 무수정). "
         f"**`B` 동결 0 · SAP 1.2 재동결 0(`sap_version` 1.1 · manifest sha16 `756d485feb4715e9` 불변 · `sap/rqint.py` **0바이트**) · 개봉 0 · GIN 착수 0 · `emit_sign` 0 · 네트워크 0 · git commit·push 0** "
         f"| vscode-claude | **N** (예측 **100% 합성** · `confirmatory_predictions_loaded` false · `sealed_accessed` false · `open_sealed` 0건 — 조회가 아니므로 §5 확증 조회 대장에 행을 추가하지 않는다) "
         f"| `docs/97_b_definition_dryrun_prompt_for_vscode.md`(지시서), `docs/97_b_definition_dryrun_report.md`(리포트), `docs/33` 항목{n}, "
         f"`v3_Multimodal/config/b_dryrun_prespec.json`(sha256 `{pre_sha[:16]}`), `experiments/rqint/b_dryrun/stair.json`, `experiments/rqint/b_dryrun/decisive.json` |")

hist45 = (f"> 📄 **문서 이력(2026-08-22) — 블록 AI(전규모 합성 드라이런 벽시계 계측 → `B` 후보 산출)**: 본 대장에 **신규 조회행 없음**"
          f"(조회 대장 표 자체 무수정 — **개봉 0** 이므로 조회행이 생길 수 없다). 계측 입력은 **실제 라벨행렬·실제 scaffold 군집구조뿐**"
          f"(`docs/84` §2 가 result-independent 설계량으로 명시 허용한 범위)이고 **예측행렬은 100% 합성 · 효과 주입 0**이다 — "
          f"`open_sealed` 0건 · `_sealed/` 읽기·쓰기 0(stat-only 스냅샷 **275종/291종** 및 sha256 착수=종료 동일) · `decision.py` 호출 0 · `emit_sign` 0 · "
          f"부호 신규 공개 0 · 새 추정 0. 산출 = `experiments/rqint/b_dryrun/{{stair,decisive,facts,verify,integrity}}.json`, "
          f"사전명시 = `v3_Multimodal/config/b_dryrun_prespec.json`(sha256 `{pre_sha[:16]}`), 리포트 = `docs/97_b_definition_dryrun_report.md`.")

t45 = open(P45, encoding="utf-8").read()
lines = t45.split("\n")
i2 = max(i for i, l in enumerate(lines) if l.startswith("| 2026-08-18 11:55:10 KST |"))
lines.insert(i2 + 1, row45)
i5 = next(i for i, l in enumerate(lines) if l.startswith("| 시각(KST) | 조회자 |"))
lines.insert(i5, hist45)
lines.insert(i5 + 1, "")
open(P45, "w", encoding="utf-8").write("\n".join(lines))

# ── ledger.json ──────────────────────────────────────────────────────────────
led = J(PLED)
n_keys0, n_tl0, n_au0 = len(led), len(led["timeline"]), len(led["authoritative_sources"])
old_tl = json.dumps(led["timeline"], ensure_ascii=False, sort_keys=True)
old_au = list(led["authoritative_sources"])
entry = {
    "ts": "2026-08-22",
    "ts_kst": now,
    "recorded_at": now,
    "event_at": f"{stair['env']['when_kst']} (단가 계측 착수) / {dec['env']['when_kst']} (결정적 드라이런 착수) / {now} (기입)",
    "actor": "vscode-claude (지시서 docs/97 · FACTS 14행 러너 실측 · 파일 해시 실측)",
    "step": ("블록 AI — 전규모 합성 드라이런 벽시계 계측 → `B` 후보 산출(계측 전용). "
             "★ `B` 동결 0(문면 확정은 R2 의 일) · SAP 1.2 재동결 0 · 개봉 0 · GIN 착수 0 · commit/push 0"),
    "event": (
        f"① 순서 정정 — `docs/84` §5 는 ⑥ = 전규모 드라이런 벽시계 → `B` 확정, ⑦ = R2(SAP 1.2 재동결)이고 R2 의 동결 대상에 축자로 `B` 가 포함된다. "
        f"`sap/rqint.py` 의 `B_DEFINITION_STATUS` 는 `still_unspecified` 이므로 ⑥ 을 건너뛰면 R2 가 빈칸을 동결한다 → 본 블록을 R2 앞에 수행했다. "
        f"`docs/94` report2 §7-2(다음 관문 = R2)는 이로써 정정되고, §7-3(큐 잔여 86·95·91)은 셋 다 2026-08-14 완료라 stale 이다. 두 리포트 문면은 무수정. "
        f"② 두 해석 — `pair_complement=True` 로 참조분포 = 2 × `n_coin_vectors` 이므로 (가) `B`=동전 수 → 100,000 동전, (나) `B`=참조분포 크기 → 50,000 동전으로 비용이 정확히 2배 차이난다. "
        f"`rqint_test` 는 직렬 루프라 워커 수로 나눠지지 않는다(F-SERIAL). "
        f"③ 사전명시 동결 — `v3_Multimodal/config/b_dryrun_prespec.json`(sha256 {pre_sha}, 동결 {J(pre_p)['frozen_at_kst']}, SAP 등재 아님)에 수렴 논증·결정적 구성(동전 50,000)·"
        f"외삽 허용 밴드 [18h,30h]·`threads_limit` 1 고정 이유·시드 파생·**전건 붕괴 시 처리**를 어떤 측정도 보기 전에 고정했다. 동결 시각 < 첫 측정 시각. "
        f"④ 단가 계측(단독 실행·동시 워커 0·AC 전원·`caffeinate -dimsu`·효과 주입 0·전규모 fixture N1,092·K370·G732·새 fixture 생성 0) — 계단 3점 n_coin {{200,500,1000}}, "
        f"선형성 상대 산포 {sw['relative_spread']:.6f} (≤0.10 통과), û = {stair['u_hat_primary']:.6f} s/동전 (주루프 {sl_['median']:.6f} s), "
        f"F-C4UNIT 1.506339 s(18워커 경합 상한)의 {stair['ratio_u_hat_over_C4']:.3f}배 · 블록 AD F_UNIT_FULL 0.716650 s 의 {stair['ratio_u_hat_over_F_UNIT_FULL']:.3f}배. "
        f"⑤ ★ 수렴 논증의 전건 붕괴 — 실측 û 로 (가) 100,000 동전 추정 벽시계는 {pa['T_hat_hours']:.3f} h 로 사전명시 밴드 [18,30] h 안이라 외삽 판정이 금지된다. "
        f"즉 '(가) > 24h' 는 미확정이다. 사전명시 처리대로 ⓐ 사실 기록 ⓑ 결정적 드라이런은 예정대로 수행 ⓒ (가) 판정은 상신(100,000 실주행은 본 블록 예산 밖 · 자체 구제 0 · 구성 변경 0). "
        f"블록 AD 의 '드라이런 100,000 = 3.88 h' 추정은 18워커 처리량(F_THRU_FULL)을 쓴 값이라 직렬 함수에는 적용되지 않으며 본 계측이 이를 대체한다. "
        f"⑥ 결정적 드라이런 실측 — 동전 50,000 · pair_complement true · threads_limit 1 · 단독 · AC · 24h 하드 캡: 총 벽시계 {dec_h:.4f} h, 캡 도달 {str(dec['cap_hit']).lower()}, "
        f"실현 참조분포 {r['n_permutation_values']} (= 2 × {r['n_coin_vectors']}), 여집합 항등식 감사 {r['complement_audit']['draws_checked']} draw 실패 {r['complement_audit']['failures']} "
        f"(max_abs_dev {r['complement_audit']['max_abs_dev']}, tol {r['complement_audit']['tol']}), complement_identity_used {str(r['complement_identity_used']).lower()}, "
        f"RAM peak {dec['ram_samples_max_gib']:.3f} GiB (게이트 30.72 GiB, 브리치 {len(dec['ram_breaches'])}). → D15 판정: 동전 50,000 구성은 24h 이내. "
        f"⑦ D15 후단 이행 — T_obs {r['T_obs']:.8f}, p {r['p_two_sided']:.6f}, SE_MC = sqrt(p(1−p)/n_permutation_values) = {r['se_mc']:.6g} (식 축자). "
        f"★ 이 p 는 100% 합성 예측 위의 값이라 확증 결과가 아니며 어떤 가설 판정에도 쓰지 않는다. "
        f"⑧ R2 에 넘길 `B` 후보 — (나) 해석이면 B = 100,000(참조분포) = 동전 50,000 이고 실측 {dec_h:.2f} h < 24 h 라 D15 하향 미발동. "
        f"(가) 해석은 동전 100,000 이 필요하며 본 실측 파생 2배 외삽 ≈ {a_from_dec/3600:.2f} h 이나 밴드 안이라 외삽 판정 금지 → 미확정·상신. "
        f"검토자 §9-2 함의 단가 1.08 s/동전은 검토자가 B 를 동전 수로 상정했음을 시사하나 해석 확정은 R2 의 일이다. **동결·확정 선언 0건.** "
        f"⑨ cowork 판정 3건 수용 — ⓐ AF-DEV-1(A12 적응적 중지 미이행)은 검토자 미상신(사용자 결정 2026-08-18, 근거 = R1 판정 무영향 + 초과 수행). "
        f"ⓑ `docs/33` 항목48 ⑨ 의 AF 진도는 stale, 정본은 항목49 ②(중단 4건 1,440·1,512·215·1,569, 최종 완주 2026-08-18 11:55:10) — 항목48 문면 무수정, supersede 포인터만 추가. "
        f"ⓒ `docs/94` report2 §7-2·§7-3 정정(문면 무수정, 기록은 `docs/33` 항목{n} 과 `docs/97` 리포트 §5). "
        f"⑩ 무결성 착수=종료 불변 — SAP 11모듈 0바이트, manifest sha16 756d485feb4715e9, sap_version 1.1, 블록 AC 4파일 + AD 2파일 0바이트, "
        f"`sap/rqint.py` sha256 착수=종료 동일(B_DEFINITION_STATUS 무수정), `_sealed/` guard 275/291 및 stat-only 스냅샷 sha256 완전 동일, HEAD 566f487 · 커밋 21 불변. "
        f"⑪ 시드 신규 추첨 0 — probe 파생 규약 계승(계단 850260813~815, 결정적 860260813), 확증 시드 공간 8개 및 블록 AF rep_seed 13,200개와 교집합 0(동전 시드 포함). "
        f"⑫ 본 entry 는 어떤 착수 허가도 아니다 — `B` 동결 0, SAP 1.2 재동결 0, 개봉 0(unblinding_performed false · open_sealed 0 · emit_sign 0 · decision.py 호출 0), "
        f"확증 예측·OOF 로드 0(confirmatory_predictions_loaded false), GIN 착수 0(gin_start_still_blocked true), 네트워크 0, data/raw/ 변경 0, git commit·push 0."),
    "artifacts": {
        "prompt": "docs/97_b_definition_dryrun_prompt_for_vscode.md",
        "report": "docs/97_b_definition_dryrun_report.md",
        "prespec": f"v3_Multimodal/config/b_dryrun_prespec.json (sha256 {pre_sha})",
        "runner": "v3_Multimodal/src/b_dryrun.py",
        "outputs": ["experiments/rqint/b_dryrun/stair.json", "experiments/rqint/b_dryrun/decisive.json",
                    "experiments/rqint/b_dryrun/facts.json", "experiments/rqint/b_dryrun/verify.json",
                    "experiments/rqint/b_dryrun/integrity.json",
                    "experiments/rqint/b_dryrun/decisive_heartbeat.jsonl"],
        "deviation_log": f"docs/33 항목{n}",
    },
    "first_look": "N",
}
led["timeline"].append(entry)
led["authoritative_sources"].append(
    "docs/97 (전규모 합성 드라이런 벽시계 계측 → `B` 후보 확정 지시서 — 블록 AI 근거 · 실행순서 ⑥, R2 선행)")
assert json.dumps(led["timeline"][:-1], ensure_ascii=False, sort_keys=True) == old_tl
assert led["authoritative_sources"][:-1] == old_au
assert len(led) == n_keys0 == 11
assert len(led["timeline"]) == n_tl0 + 1 == 48
assert len(led["authoritative_sources"]) == n_au0 + 1 == 25
assert len(led["correspondence"]) == 22 and len(led["first_look_register"]) == 6
with open(PLED, "w", encoding="utf-8") as f:
    json.dump(led, f, ensure_ascii=False, indent=2)
    f.write("\n")

json.dump({"docs33_item_number": n, "docs33_sha256_before": b33, "docs33_sha256_after": sha(P33),
           "docs45_sha256_before": b45, "docs45_sha256_after": sha(P45),
           "docs45_inserted_lines": [row45, hist45],
           "ledger_timeline": len(led["timeline"]),
           "ledger_authoritative_sources": len(led["authoritative_sources"])},
          open(os.path.join(OUT, "doc_inserts.json"), "w"), ensure_ascii=False, indent=2)
print(f"docs/33 항목{n} 기입 · docs/45 §2+1행 §5+1행 · ledger timeline {len(led['timeline'])} auth {len(led['authoritative_sources'])}")
