#!/usr/bin/env python3
"""[블록 AJ] 기입 3곳 — docs/33 신규 항목(번호 실측) · docs/45 §2·§5 · ledger.json.
append-only · 기존 문면 삭제 0 · 소급 수정 0. 멱등하지 않으므로 **1회만** 실행한다."""
import os, sys, json, hashlib
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "v3_Multimodal", "src"))
import doc_numbering as dn
OUT = os.path.join(ROOT, "experiments", "rqint", "b_100k")
KST = timezone(timedelta(hours=9))
J = lambda p: json.load(open(p, encoding="utf-8"))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

run = J(os.path.join(OUT, "run.json"))
se = J(os.path.join(OUT, "se_comparison.json"))
dec = J(os.path.join(ROOT, "experiments", "rqint", "b_dryrun", "decisive.json"))
r, rb = run["result"], dec["result"]
ck = r["checkpoint_b50000"]
pre_p = os.path.join(ROOT, "v3_Multimodal", "config", "b_100k_prespec.json")
pre, pre_sha = J(pre_p), sha(pre_p)
ai_p = os.path.join(ROOT, "v3_Multimodal", "config", "b_dryrun_prespec.json")
now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

P33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
P45 = os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")
PLED = os.path.join(ROOT, "experiments", "provenance", "ledger.json")
b33, b45 = sha(P33), sha(P45)

n = dn.next_item_number(P33)
H = run["wall_hours_total"]
A, B = se["interpretation_a"], se["interpretation_b"]
capped = run["cap_hit"]
verdict_line = ("**캡 도달(미완주)** → (가) 는 **24 h 초과 확정** → D15 에 따라 **동전 50,000 으로 하향**"
                if capped else
                f"**완주 · 벽시계 {H:.3f} h ≤ 24 h** → (가) 는 **하향 조건 미충족** → "
                f"`B` = 동전 100,000(참조분포 200,000) 후보 성립")

item = f"""{n}. **(가) 해석 실주행 — 동전 100,000 · 24 h 하드 캡 → `B` 24h 판정 완결 (블록 AJ — 계측·판정 전용 · `B` 정의 채택 0)**:

   - **① 왜 이것이 「설계 변경」이 아닌가 — 동결된 정책이 지정한 이행이다**: 연쇄는 4단계다. ⓐ **정책 문면(측정 전 동결)** — 블록 AI 의 `b_dryrun_prespec.json`(sha256 `9a2545eb0d897f30…` · 동결 **{J(ai_p)['frozen_at_kst']}**) 의 `extrapolation_policy.rule_inside_band` 축자 = **"밴드 안이면 외삽 금지 → 실주행 + 24h 하드 캡으로 판정한다."** ⓑ **밴드 안 판정(실측)** — 동전 100,000 의 추정 벽시계 `T̂` 는 **19.49 h**(계단 외삽) · **19.58 h**(50,000 실측의 2배 외삽)로 **둘 다 사전명시 밴드 [18, 30] h 안**이었다. ⓒ **상신** — 같은 파일의 `contingency_if_premise_fails.action③`(측정 전 동결)이 "100,000 동전 실주행은 본 블록 예산 밖이므로 **자체 판단으로 구성을 바꾸지 않는다** → **상신 사항으로 보고**"라 규정했고 블록 AI 는 그대로 이행했다(`docs/97` report §4-5·§6-1). ⓓ **승인** — 사용자가 **2026-08-22** 그 상신을 승인했다. ★ 따라서 본 블록은 **결과를 보고 구성을 키운 사후 설계 변경이 아니라**, 측정 전에 동결된 정책이 "밴드 안이면 실주행하라"고 **미리 지정한 경로**를 밟은 것이다.
   - **② 델타 사전명시 동결(실주행 전)**: **`v3_Multimodal/config/b_100k_prespec.json`**(sha256 `{pre_sha[:16]}…` · 동결 **{pre['frozen_at_kst']}** · **SAP 등재 아님** · 이후 무수정). `supersedes_nothing` = true — **블록 AI 의 prespec 을 대체하지 않고**(AI 산출물 4종 **0바이트**) `action③` 이 넘긴 **단 하나의 항목**만 규정한다. `run_config` = 동전 **100,000** · `pair_complement` true · 참조분포 **200,000** · 감사 draw 1,000 · `threads_limit` **1** · 캡 **86,400 s**. ★ **판정식 2분기를 측정 전에 고정**했다 — 완주 & ≤24 h → (가) 하향 미충족 / 캡 도달 → 24 h 초과 확정 → 50,000 하향. **3분기 신설·캡 연장·재실행 금지.** 동결 시각 **{pre['frozen_at_kst']} < 실주행 시작 {run['started_kst']}**.
   - **③ 시드 신규 추첨 0 — 결정성 검증을 공짜로 얻는 설계**: `rep_seed` **860260813**(= 블록 AI 결정적 드라이런)을 **그대로 재사용**했다(동전 시드 1760260813). 동전 생성기가 단일 `default_rng` 스트림이고 루프가 직렬(`for b in range(n_coin_vectors)`)이므로 100,000 run 의 앞 50,000 동전은 50,000 run 의 **prefix** 다 → **b=50,000 시점 러닝 카운트가 블록 AI 실측 67,262 와 정확히 일치해야 한다**. 착수 전 소규모 자가시험(n_coin 100 vs 200)으로 이 전제(prefix 동일 · 여집합 감사 비교란 · 관측량 불변)를 **바이트 수준에서 확인**했다(`prefix_smoke.json`).
   - **④ ★ 결정성 검증 2건 — 전건 통과**: ⓐ **b=50,000 러닝 카운트 = {ck['count_abs_ge_obs']:,}**(참조분포 100,000 기준) — 기대 **67,262** 와 **정확히 일치**(`p` 재현값 {ck['p_two_sided']:.10f} = 블록 AI `p` 와 동일). 종료검증에서는 산출 배열 `t_star.npy` 로 **러너와 독립 재계산**해 같은 값을 얻었다. ⓑ **관측통계량 바이트 동일** — `T_obs` **{r['T_obs']!r}** · `delta_rf` **{r['delta_rf']!r}** · `delta_gin` **{r['delta_gin']!r}** 이 `F-AIOBS` 와 `repr` 수준에서 동일하다. 같은 `rep_seed` 인데 관측량이 달랐다면 fixture 재현성이 깨진 것이므로 즉시 중단 조건이었다 — **불일치 0**.
   - **⑤ 실주행 실측(동전 100,000 · `threads_limit` 1 · 단독 실행 · AC 96 W · 24 h 하드 캡)**: 총 벽시계 **{H:.4f} h**({run['wall_seconds_total']:.1f} s) · 캡 도달 **{'예' if capped else '아니오'}** · AC 이탈 **{'예' if run['ac_power_lost'] else '아니오'}** · 실현 참조분포 **{r['n_permutation_values']:,}**(= 2 × {r['n_coin_vectors']:,}) · 여집합 항등식 감사 **{r['complement_audit']['draws_checked']} draw · 실패 {r['complement_audit']['failures']} · max_abs_dev {r['complement_audit']['max_abs_dev']}** · `complement_identity_used` **{str(r['complement_identity_used']).lower()}** · `per_permutation_seconds` **{r['per_permutation_seconds']:.6f}** · RAM peak **{run['ram_samples_max_gib']:.2f} GiB**(게이트 30.72 GiB · 브리치 {len(run['ram_breaches'])}건). 참고 — 블록 AI 실측 단가 0.697678 s/동전 대비 본런 {r['per_permutation_seconds']:.6f} s/동전.
   - **⑥ ★ D15 판정 — 사전 고정한 2분기 중 실현된 가지**: {verdict_line}. 이로써 **(가) 해석의 24 h 판정이 실측으로 완결**됐고, 블록 AI 가 상신으로 남긴 미해결 항목은 **해소**됐다.
   - **⑦ 최종 판정표(양 해석)**: **(가) `B` = 동전 수** → 동전 100,000 / 참조분포 200,000 / 벽시계 **{H:.3f} h**(본 블록 실측) / 24 h **{'초과' if capped or H > 24 else '이내'}**. **(나) `B` = 참조분포 크기** → 동전 50,000 / 참조분포 100,000 / 벽시계 **9.8848 h**(블록 AI 실측) / 24 h **이내**. **두 해석 모두 실측으로 24 h 판정이 확정**됐다.
   - **⑧ 양 해석 `SE_MC` 대비(R2 의 정의 선택 근거)**: 식 축자 = **`SE_MC = sqrt( p·(1−p) / n_permutation_values )`**. (가) `p` **{A['p_two_sided']:.6f}** · **`SE_MC` {A['se_mc']:.6g}**(참조분포 {A['n_permutation_values']:,}) / (나) `p` **{B['p_two_sided']:.6f}** · **`SE_MC` {B['se_mc']:.6g}**(참조분포 {B['n_permutation_values']:,}). **참조분포가 2배면 SE 는 1/√2 = {se['one_over_sqrt2']:.5f} 배** — 실측 비 **{se['se_ratio_a_over_b']:.5f}**. 즉 (가) 는 **정밀도 √2 배 · 비용 2배**다. ★ **이 `p`·`SE_MC` 는 100% 합성 예측 위의 값이라 확증 결과가 아니며** 어떤 가설 판정에도 쓰지 않는다.
   - **⑨ ★ 정의 채택 선언 0 — 본 블록은 실측을 갖춰 주는 데까지다**: `sap/rqint.py` 의 `B_DEFINITION_STATUS` 는 **`still_unspecified` 그대로**이고 파일은 **0바이트 수정**이다. **(가)/(나) 중 무엇을 `B` 로 삼을지는 R2(SAP 1.2 재동결) 소관**이며 본 블록은 어느 쪽도 채택·동결·권고하지 않는다. 참고로 검토자 §9-2 의 함의 단가 1.08 s/동전은 (가) ≈ 30 h 를 함의해 **검토자가 `B` 를 동전 수로 상정했음**을 시사하지만, 실측 단가가 그보다 낮다는 사실까지가 본 블록의 기여다.
   - **⑩ 무결성 — 착수=종료 불변**: SAP 등재 **11모듈 0바이트** · `manifest.json` sha16 **`756d485feb4715e9`** · `sap_version` **1.1** · 블록 AC 4파일 + AD 2파일 **0바이트** · ★ **`sap/rqint.py` sha16 `eb842bc98140e9c5` 착수=종료 동일** · ★ **블록 AI 산출물 4종**(`b_dryrun_prespec.json`·`stair.json`·`decisive.json`·`b_dryrun.py`) **0바이트** · `_sealed/` guard **275종(access.log 제외) / 291종(포함)** 및 stat-only 스냅샷 sha256 **완전 동일**(블록 AI 착수 스냅샷 `741feb8e52a3cf00…` 과도 동일) · HEAD `566f487` · 커밋 21 불변. 본 블록이 만든 파일 = `v3_Multimodal/config/b_100k_prespec.json` · `v3_Multimodal/src/b_100k_run.py` · `experiments/rqint/b_100k/` 산출 뿐이다.
   - **⑪ ★ 본 기입은 어떤 착수 허가도 아니다**: **`B` 정의 채택·문면 동결 0** · **SAP 1.2 재동결 0** · **개봉 0**(`unblinding_performed` false · `_sealed/` 읽기·쓰기 0 · `open_sealed` 0 · `emit_sign` 0 · `decision.py` 호출 0) · **확증 예측·OOF 로드 0**(`confirmatory_predictions_loaded` false · 예측 **100% 합성** · 효과 주입 **0**) · **GIN 학습·착수 0**(`gin_start_still_blocked` true) · **네트워크 0** · **`data/raw/` 변경 0** · **git commit·push 0**. R2·R3·`B` 확정·개봉·GIN 착수는 **전부 차단 유지**다.

> 지시서 = `docs/98_b_definition_100k_run_prompt_for_vscode.md` · 리포트 = `docs/98_b_definition_100k_run_report.md` ·
델타 사전명시(동결, SAP 등재 아님) = `v3_Multimodal/config/b_100k_prespec.json`(sha256 `{pre_sha[:16]}` · 동결 {pre['frozen_at_kst']} · `supersedes_nothing` true) ·
산출 = `experiments/rqint/b_100k/run.json` · `se_comparison.json` · `prefix_smoke.json` · `facts.json` · `verify.json` · `integrity.json` · `run_heartbeat.jsonl` · `t_star.npy` ·
러너 = `v3_Multimodal/src/b_100k_run.py`(신규 · **`sap/` 밖** · `b_dryrun.py` 는 **읽기 전용 import**) ·
무수정 대조 = 블록 AI 산출물 4종 **0바이트** · SAP `manifest.json` sha16 `756d485feb4715e9`(`sap_version` **1.1** · 11모듈 **0바이트**) · 블록 AC 4파일 + AD 2파일 **0바이트** · `sap/rqint.py` **0바이트** ·
sealed guard **275종(access.log 제외) / 291종(포함) 불변**(stat-only 스냅샷 sha256 착수=종료 동일). **미실행**: 위 ⑪ 전항. 기입 시각 {now}.

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
row45 = (f"| 2026-08-23 {run['started_kst'][11:19]} KST | **블록 AJ(계측·판정 전용 · `B` 정의 채택 0 · 확증 계산 0)** "
         f"**(가) 해석 실주행 — 동전 100,000 · 24 h 하드 캡 → `B` 24h 판정 완결** — ★ **설계 변경이 아니다**: "
         f"블록 AI 의 **측정 전 동결본** `b_dryrun_prespec.json` 의 `extrapolation_policy.rule_inside_band` 축자 "
         f"「밴드 안이면 외삽 금지 → 실주행 + 24h 하드 캡으로 판정한다」가 이미 이 실주행을 규정했고, 실측 `T̂` **19.49 h/19.58 h** 가 "
         f"밴드 **[18,30] h 안**이라 `contingency_if_premise_fails.action③` 이 **상신**으로 돌렸으며 **사용자가 2026-08-22 승인**했다 "
         f"(정책 문면 → 밴드 안 판정 → 상신 → 승인의 4단계). 델타 사전명시 **`b_100k_prespec.json`**(sha256 `{pre_sha[:16]}` · 동결 {pre['frozen_at_kst']} · "
         f"**SAP 등재 아님** · `supersedes_nothing` true · **AI prespec 무수정·대체 0**)에 `run_config`(동전 100,000/참조분포 200,000/캡 86,400 s/`threads_limit` 1)와 "
         f"**판정식 2분기를 측정 전에 고정**(완주 ≤24 h → 하향 미충족 / 캡 도달 → 24 h 초과 확정 → 50,000 하향 · **3분기·캡 연장·재실행 금지**)했다. "
         f"**시드 신규 추첨 0** — `rep_seed` **860260813 재사용**이라 **b=50,000 러닝 카운트가 67,262 와 정확히 일치**해야 하는 강한 결정성 검증이 공짜로 따라온다. "
         f"★ **결정성 검증 2건 전건 통과** — b=50,000 러닝 카운트 **{ck['count_abs_ge_obs']:,}**(= 67,262, 산출 배열로 **독립 재계산** 확인) · "
         f"`T_obs`/`delta_rf`/`delta_gin` **바이트 동일**. **실주행 실측** 총 벽시계 **{H:.4f} h** · 캡 도달 **{'예' if capped else '아니오'}** · "
         f"실현 참조분포 **{r['n_permutation_values']:,}**(= 2 × {r['n_coin_vectors']:,}) · 여집합 항등식 감사 {r['complement_audit']['draws_checked']} draw **실패 {r['complement_audit']['failures']}** · "
         f"RAM peak {run['ram_samples_max_gib']:.2f} GiB(브리치 {len(run['ram_breaches'])}). "
         f"**D15 판정** = {verdict_line.replace('**','')}. **양 해석 `SE_MC` 병기** — 식 축자 `SE_MC = sqrt(p(1−p)/n_permutation_values)`, "
         f"(가) {A['se_mc']:.6g}(참조분포 {A['n_permutation_values']:,}) vs (나) {B['se_mc']:.6g}(참조분포 {B['n_permutation_values']:,}), 비 **{se['se_ratio_a_over_b']:.5f} ≈ 1/√2** "
         f"→ (가) 는 정밀도 √2 배·비용 2배(★ 합성 예측 위의 값 = **확증 결과 아님**). "
         f"★ **정의 채택 선언 0** — (가)/(나) 중 무엇을 `B` 로 삼을지는 **R2 소관**이고 본 블록은 양쪽 실측을 갖춰 주는 데까지다. "
         f"**`B` 동결 0 · SAP 1.2 재동결 0(`sap_version` 1.1 · manifest sha16 `756d485feb4715e9` 불변 · `sap/rqint.py` **0바이트**) · "
         f"블록 AI 산출물 4종 **0바이트** · 개봉 0 · GIN 착수 0 · `emit_sign` 0 · 네트워크 0 · git commit·push 0** "
         f"| vscode-claude | **N** (예측 **100% 합성** · `confirmatory_predictions_loaded` false · `sealed_accessed` false · `open_sealed` 0건 — 조회가 아니므로 §5 확증 조회 대장에 행을 추가하지 않는다) "
         f"| `docs/98_b_definition_100k_run_prompt_for_vscode.md`(지시서), `docs/98_b_definition_100k_run_report.md`(리포트), `docs/33` 항목{n}, "
         f"`v3_Multimodal/config/b_100k_prespec.json`(sha256 `{pre_sha[:16]}`), `experiments/rqint/b_100k/run.json`, `experiments/rqint/b_100k/se_comparison.json` |")

hist45 = (f"> 📄 **문서 이력(2026-08-23) — 블록 AJ((가) 해석 실주행: 동전 100,000 → `B` 24h 판정 완결)**: 본 대장에 **신규 조회행 없음**"
          f"(조회 대장 표 자체 무수정 — **개봉 0** 이므로 조회행이 생길 수 없다). 계측 입력은 **실제 라벨행렬·실제 scaffold 군집구조뿐**"
          f"(`docs/84` §2 가 result-independent 설계량으로 명시 허용한 범위)이고 **예측행렬은 100% 합성 · 효과 주입 0**이다 — "
          f"`open_sealed` 0건 · `_sealed/` 읽기·쓰기 0(stat-only 스냅샷 **275종/291종** 및 sha256 착수=종료 동일) · `decision.py` 호출 0 · `emit_sign` 0 · "
          f"부호 신규 공개 0 · 새 추정 0 · **`B` 정의 채택 0**(R2 소관). 산출 = `experiments/rqint/b_100k/{{run,se_comparison,prefix_smoke,facts,verify,integrity}}.json`, "
          f"델타 사전명시 = `v3_Multimodal/config/b_100k_prespec.json`(sha256 `{pre_sha[:16]}`), 리포트 = `docs/98_b_definition_100k_run_report.md`.")

t45 = open(P45, encoding="utf-8").read()
lines = t45.split("\n")
i2 = max(i for i, l in enumerate(lines) if l.startswith("| 2026-08-22 02:03:15 KST |"))
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
    "ts": "2026-08-23",
    "ts_kst": now,
    "recorded_at": now,
    "event_at": f"{run['started_kst']} (실주행 착수) / {run['ended_kst']} (완료) / {now} (기입)",
    "actor": "vscode-claude (지시서 docs/98 · FACTS 14행 러너 실측 · 파일 해시 실측)",
    "step": ("블록 AJ — (가) 해석 실주행(동전 100,000 · 24h 하드 캡) → `B` 24h 판정 완결(계측·판정 전용). "
             "★ `B` 정의 채택·동결 0(채택은 R2 의 일) · SAP 1.2 재동결 0 · 개봉 0 · GIN 착수 0 · commit/push 0"),
    "event": (
        f"① 착수 근거 4단계(설계 변경 아님) — ⓐ 정책 문면: 블록 AI 의 측정 전 동결본 b_dryrun_prespec.json(sha256 9a2545eb0d897f30…) 의 "
        f"extrapolation_policy.rule_inside_band 축자 「밴드 안이면 외삽 금지 → 실주행 + 24h 하드 캡으로 판정한다」. "
        f"ⓑ 밴드 안 판정(실측): 동전 100,000 추정 벽시계 T̂ = 19.49 h(계단 외삽)·19.58 h(50,000 실측 2배 외삽) 둘 다 사전명시 밴드 [18,30] h 안. "
        f"ⓒ 상신: contingency_if_premise_fails.action③ 이 「100,000 동전 실주행은 본 블록 예산 밖 → 자체 판단으로 구성을 바꾸지 않는다 → 상신 사항으로 보고」라 규정했고 블록 AI 가 이행. "
        f"ⓓ 승인: 사용자 2026-08-22 승인. → 본 블록은 동결된 정책이 지정한 이행이지 결과를 보고 구성을 키운 사후 설계 변경이 아니다. "
        f"② 델타 사전명시 동결 — v3_Multimodal/config/b_100k_prespec.json(sha256 {pre_sha}, 동결 {pre['frozen_at_kst']}, SAP 등재 아님, supersedes_nothing true). "
        f"AI prespec 무수정·대체 0. run_config = 동전 100,000 / pair_complement true / 참조분포 200,000 / 감사 draw 1,000 / threads_limit 1 / 캡 86,400 s. "
        f"판정식 2분기를 측정 전에 고정(완주 ≤24h → (가) 하향 미충족 / 캡 도달 → 24h 초과 확정 → 50,000 하향), 3분기·캡 연장·재실행 금지. "
        f"동결 시각 {pre['frozen_at_kst']} < 실주행 시작 {run['started_kst']}. "
        f"③ 시드 신규 추첨 0 — rep_seed 860260813(동전 시드 1760260813) 재사용. 단일 default_rng 스트림 + 직렬 루프이므로 100,000 run 의 앞 50,000 동전은 50,000 run 의 prefix 다. "
        f"착수 전 소규모 자가시험(n_coin 100 vs 200)으로 prefix 동일·여집합 감사 비교란·관측량 불변을 바이트 수준 확인(prefix_smoke.json). "
        f"④ 결정성 검증 2건 전건 통과 — ⓐ b=50,000 러닝 카운트 {ck['count_abs_ge_obs']} (기대 67262, 정확히 일치; 재현 p {ck['p_two_sided']:.10f}), "
        f"종료검증에서 산출 배열 t_star.npy 로 러너 미import 독립 재계산해 동일값 확인. "
        f"ⓑ 관측통계량 바이트 동일 — T_obs {r['T_obs']!r}, delta_rf {r['delta_rf']!r}, delta_gin {r['delta_gin']!r} (F-AIOBS 와 repr 동일). 불일치 0. "
        f"⑤ 실주행 실측 — 동전 100,000, threads_limit 1, 단독 실행, AC 96W, 24h 하드 캡: 총 벽시계 {H:.4f} h ({run['wall_seconds_total']:.1f} s), "
        f"캡 도달 {str(capped).lower()}, AC 이탈 {str(run['ac_power_lost']).lower()}, 실현 참조분포 {r['n_permutation_values']} (= 2 × {r['n_coin_vectors']}), "
        f"여집합 항등식 감사 {r['complement_audit']['draws_checked']} draw 실패 {r['complement_audit']['failures']} "
        f"(max_abs_dev {r['complement_audit']['max_abs_dev']}, tol {r['complement_audit']['tol']}), "
        f"complement_identity_used {str(r['complement_identity_used']).lower()}, per_permutation_seconds {r['per_permutation_seconds']:.6f}, "
        f"RAM peak {run['ram_samples_max_gib']:.3f} GiB (게이트 30.72 GiB, 브리치 {len(run['ram_breaches'])}). "
        f"⑥ D15 판정 — 사전 고정 2분기 중 실현된 가지: {run['d15_branch']} (d15_verdict = {run['d15_verdict']}). "
        f"블록 AI 가 상신으로 남긴 (가) 해석의 24h 미판정 항목이 이로써 해소됐다. "
        f"⑦ 최종 판정표 — (가) B=동전 수: 동전 100,000/참조분포 200,000, 벽시계 {H:.3f} h(본 블록 실측); "
        f"(나) B=참조분포 크기: 동전 50,000/참조분포 100,000, 벽시계 9.8848 h(블록 AI 실측). 두 해석 모두 실측으로 24h 판정 확정. "
        f"⑧ 양 해석 SE_MC 병기 — 식 축자 SE_MC = sqrt( p·(1−p) / n_permutation_values ). "
        f"(가) p {A['p_two_sided']:.6f}, SE_MC {A['se_mc']:.6g}, 참조분포 {A['n_permutation_values']}; "
        f"(나) p {B['p_two_sided']:.6f}, SE_MC {B['se_mc']:.6g}, 참조분포 {B['n_permutation_values']}. "
        f"비 {se['se_ratio_a_over_b']:.5f} ≈ 1/√2 = {se['one_over_sqrt2']:.5f} → (가) 는 정밀도 √2 배·비용 2배. "
        f"★ 이 p·SE_MC 는 100% 합성 예측 위의 값이라 확증 결과가 아니며 어떤 가설 판정에도 쓰지 않는다. "
        f"⑨ 정의 채택 선언 0 — sap/rqint.py 의 B_DEFINITION_STATUS 는 still_unspecified 그대로이고 파일은 0바이트 수정이다. "
        f"(가)/(나) 중 무엇을 B 로 삼을지는 R2(SAP 1.2 재동결) 소관이며 본 블록은 어느 쪽도 채택·동결·권고하지 않는다. "
        f"검토자 §9-2 함의 단가 1.08 s/동전은 검토자가 B 를 동전 수로 상정했음을 시사하나 해석 확정은 R2 의 일이다. "
        f"⑩ 무결성 착수=종료 불변 — SAP 11모듈 0바이트, manifest sha16 756d485feb4715e9, sap_version 1.1, 블록 AC 4파일 + AD 2파일 0바이트, "
        f"sap/rqint.py sha16 eb842bc98140e9c5 동일(B_DEFINITION_STATUS 무수정), 블록 AI 산출물 4종 0바이트, "
        f"_sealed/ guard 275/291 및 stat-only 스냅샷 sha256 완전 동일(블록 AI 착수 스냅샷 741feb8e52a3cf00… 과도 동일), HEAD 566f487 · 커밋 21 불변. "
        f"⑪ 본 entry 는 어떤 착수 허가도 아니다 — B 정의 채택·동결 0, SAP 1.2 재동결 0, 개봉 0(unblinding_performed false · open_sealed 0 · emit_sign 0 · decision.py 호출 0), "
        f"확증 예측·OOF 로드 0(confirmatory_predictions_loaded false), GIN 착수 0(gin_start_still_blocked true), 네트워크 0, data/raw/ 변경 0, git commit·push 0."),
    "artifacts": {
        "prompt": "docs/98_b_definition_100k_run_prompt_for_vscode.md",
        "report": "docs/98_b_definition_100k_run_report.md",
        "prespec": f"v3_Multimodal/config/b_100k_prespec.json (sha256 {pre_sha})",
        "runner": "v3_Multimodal/src/b_100k_run.py",
        "outputs": ["experiments/rqint/b_100k/run.json",
                    "experiments/rqint/b_100k/se_comparison.json",
                    "experiments/rqint/b_100k/prefix_smoke.json",
                    "experiments/rqint/b_100k/facts.json",
                    "experiments/rqint/b_100k/verify.json",
                    "experiments/rqint/b_100k/integrity.json",
                    "experiments/rqint/b_100k/run_heartbeat.jsonl",
                    "experiments/rqint/b_100k/t_star.npy"],
        "deviation_log": f"docs/33 항목{n}",
    },
    "first_look": "N",
}
led["timeline"].append(entry)
led["authoritative_sources"].append(
    "docs/98 ((가) 해석 실주행: 동전 100,000 · 24h 하드 캡 → `B` 24h 판정 완결 지시서 — 블록 AJ 근거 · "
    "블록 AI `contingency_if_premise_fails.action③` 상신의 사용자 승인 이행)")
assert json.dumps(led["timeline"][:-1], ensure_ascii=False, sort_keys=True) == old_tl
assert led["authoritative_sources"][:-1] == old_au
assert len(led) == n_keys0 == 11
assert len(led["timeline"]) == n_tl0 + 1 == 49
assert len(led["authoritative_sources"]) == n_au0 + 1 == 26
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
print(f"docs/33 항목{n} 기입 · docs/45 §2+1행 §5+1행 · "
      f"ledger timeline {len(led['timeline'])} auth {len(led['authoritative_sources'])}")
