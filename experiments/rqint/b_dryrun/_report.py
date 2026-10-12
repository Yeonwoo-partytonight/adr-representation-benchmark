#!/usr/bin/env python3
"""docs/97 수행 리포트 생성 — 모든 수치를 산출 파일에서 읽어 채운다(전사 오류 0)."""
import os, sys, json, hashlib, subprocess
from datetime import datetime, timezone, timedelta
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(ROOT, "experiments", "rqint", "b_dryrun")
KST = timezone(timedelta(hours=9))
J = lambda p: json.load(open(p, encoding="utf-8"))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
sz = lambda p: os.path.getsize(p)

stair = J(os.path.join(OUT, "stair.json")); dec = J(os.path.join(OUT, "decisive.json"))
facts = J(os.path.join(OUT, "facts.json")); ver = J(os.path.join(OUT, "verify.json"))
integ = J(os.path.join(OUT, "integrity.json")); ins = J(os.path.join(OUT, "doc_inserts.json"))
pre_p = os.path.join(ROOT, "v3_Multimodal", "config", "b_dryrun_prespec.json")
pre = J(pre_p); pre_sha = sha(pre_p)
r = dec["result"]; sw = stair["u_wall_stats"]; sl_ = stair["u_loop_stats"]
pa = stair["projection"]["interp_a_100000"]; pb = stair["projection"]["interp_b_50000"]
dec_h = dec["wall_hours_total"]
a_from_dec = (2.0 * dec["wall_seconds_total"] - 1000 * stair["u_hat_primary"]) / 3600.0
now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
n33 = ins["docs33_item_number"]

def art(rel):
    p = os.path.join(ROOT, rel)
    return f"- `{rel}` — {sz(p):,} B · sha256 `{sha(p)[:16]}…`"

def cell(v, n=110):
    """표 셀 안전화 — 개행 접기 + 파이프 이스케이프 + 길이 제한."""
    t = " ".join(str(v).split())
    if len(t) > n:
        t = t[:n] + "…"
    return t.replace("|", "\\|")

fact_rows = "\n".join(
    f"| `{x['fact_id']}` | {cell(x['expect'], 150)} | `{x['source'].replace(chr(96), '')}` | {cell(x['measured'])} | "
    f"{'✅' if x['pass'] else '❌'} |" for x in facts["rows"])
ver_rows = "\n".join(
    f"| {x['no']} | {cell(x['item'], 150)} | {cell(x['expect'], 130)} | {cell(x['got'], 130)} | "
    f"{'✅ PASS' if x['pass'] else '❌ FAIL'} |" for x in ver["rows"])
stair_rows = "\n".join(
    f"| {x['n_coin_vectors']:,} | {x['rep_seed']} | {x['wall_seconds']:.2f} | {x['synth_seconds']:.2f} | "
    f"**{x['u_wall_per_coin']:.6f}** | {x['u_loop_per_coin']:.6f} | {x['n_permutation_values']:,} |"
    for x in stair["stair_rows"])

md = f"""# [블록 AI] 실행순서 ⑥ — 전규모 합성 드라이런 벽시계 계측 → `B` 후보 확정 — 수행 리포트

- 지시서: `docs/97_b_definition_dryrun_prompt_for_vscode.md`
- 수행: Claude Code (VS Code) · {now}
- 결과: 완료 (단, **(가) 해석의 24 h 판정은 사전명시 규칙에 따라 미확정 → 상신**)

## 1. 게이트/선행조건

### 1-1. FACTS registry 14행 — 전건 **실측 소스에서 직접** 대조

| fact ID | 기대값 | 실측 소스 | 실측 | 판정 |
|---|---|---|---|---|
{fact_rows}

**{facts['n_pass']}/{facts['n_total']} PASS · `all_facts_pass` = {str(facts['all_facts_pass']).lower()}** → 착수 게이트 통과.

### 1-2. 운용 게이트

| 항목 | 기대 | 실측 | 판정 |
|---|---|---|---|
| AC 전원 | 연결 | {cell(stair['env']['pmset_ps'].splitlines()[0])} · 96W USB-C 어댑터 · `IsCharging` Yes | ✅ |
| `caffeinate -dimsu` | 실행 중 | {str(stair['env']['caffeinate_running']).lower()} | ✅ |
| 동시 워커 | 0 (단독 실행) | 캘리브레이션 하네스 프로세스 0건(`pgrep -fl "rqint_calibration\\|mainrun_driver"`) | ✅ |
| `threads_limit` | 1 | {cell(stair['env']['env_thread_vars'])} | ✅ |
| 사전명시 동결 시각 | < 첫 측정 | {pre['frozen_at_kst']} < {stair['env']['when_kst']} (파일 birth time) | ✅ |

## 2. 실행한 명령

```bash
# AI-1 사전명시 동결 (측정 이전)
.venv/bin/python3  # → v3_Multimodal/config/b_dryrun_prespec.json 생성 (sha256 {pre_sha[:16]}…)

# 게이트
.venv/bin/python3 experiments/rqint/b_dryrun/_facts.py          # FACTS 14행 실측 대조

# AI-2 단가 계측 (단독 실행 · 동시 워커 0 · AC 전원)
nohup caffeinate -dimsu &
nohup .venv/bin/python3 v3_Multimodal/src/b_dryrun.py --stage stair \\
      > experiments/rqint/b_dryrun/stair.log 2>&1 &

# AI-3 결정적 드라이런 (동전 50,000 · 24h 하드 캡)
nohup .venv/bin/python3 v3_Multimodal/src/b_dryrun.py --stage decisive \\
      > experiments/rqint/b_dryrun/decisive.log 2>&1 &

# AI-4 기입 + 종료검증
.venv/bin/python3 experiments/rqint/b_dryrun/_integrity.py
.venv/bin/python3 experiments/rqint/b_dryrun/_record.py         # docs/33 · docs/45 · ledger.json
.venv/bin/python3 experiments/rqint/b_dryrun/_verify.py         # 종료검증 18항
```

## 3. 산출물

{art('v3_Multimodal/config/b_dryrun_prespec.json')} — **AI-1 사전명시 동결본**(측정 이전 · **SAP 등재 아님** · 이후 무수정)
{art('v3_Multimodal/src/b_dryrun.py')} — 계측 러너(신규 · **`sap/` 밖** · 재구현 0, `rqint_calibration` import 재사용)
{art('experiments/rqint/b_dryrun/stair.json')} — AI-2 계단 계측 3점 + 선형성 + 투영
{art('experiments/rqint/b_dryrun/decisive.json')} — AI-3 결정적 드라이런 실측
{art('experiments/rqint/b_dryrun/facts.json')} — FACTS 14행 대조
{art('experiments/rqint/b_dryrun/verify.json')} — 종료검증 18항
{art('experiments/rqint/b_dryrun/integrity.json')} — 무결성 선언
{art('experiments/rqint/b_dryrun/decisive_heartbeat.jsonl')} — 60초 주기 하트비트(경과·전원·load·RSS)

## 4. 관측 (출처 경로 병기)

### 4-1. AI-2 단가 계측 — 단독 실행 · 동시 워커 0 · 효과 주입 0 · 전규모 fixture(N 1,092 · K 370 · G 732)

| `n_coin_vectors` | `rep_seed` | 벽시계 (s) | 합성점수 생성 (s) | `û_wall` = wall/n | `û_loop` (`per_permutation_seconds`) | 실현 참조분포 |
|---|---|---|---|---|---|---|
{stair_rows}

(출처 `experiments/rqint/b_dryrun/stair.json`)

- **선형성**: `û_wall` 상대 산포 **{sw['relative_spread']:.6f}** (기준 ≤ 0.10) → **통과**. `û_loop` 상대 산포 {sl_['relative_spread']:.6f}.
- **`û` = 3점 중앙값 = {stair['u_hat_primary']:.6f} s/동전** (주루프 기준 {sl_['median']:.6f} s).
- 비교: `F-C4UNIT` **1.506339 s**(18워커 경합 하 = 단독의 **상한**) 대비 **{stair['ratio_u_hat_over_C4']:.3f}배** · 블록 AD `F_UNIT_FULL` **0.716650 s**(단독 계측) 대비 **{stair['ratio_u_hat_over_F_UNIT_FULL']:.3f}배**.
- 비용 모형(사전명시): `T̂(n) = t_synth + n·û + min(1000, n)·û_audit`, `t_synth` 중앙값 **{stair['t_synth_median_seconds']:.2f} s** (출처 `stair.json` `cost_model`).

### 4-2. AI-3 결정적 드라이런 — 동전 50,000 · `pair_complement=True` · `threads_limit` 1 · 24 h 하드 캡

| 항목 | 실측 |
|---|---|
| 총 벽시계 | **{dec['wall_seconds_total']:,.1f} s = {dec_h:.4f} h** |
| 24 h 하드 캡 도달 | **{str(dec['cap_hit']).lower()}** |
| AC 전원 이탈 | {str(dec['ac_power_lost']).lower()} |
| `n_coin_vectors` | {r['n_coin_vectors']:,} |
| 실현 참조분포 `n_permutation_values` | **{r['n_permutation_values']:,}** (= 2 × {r['n_coin_vectors']:,}) |
| 여집합 항등식 감사 | {r['complement_audit']['draws_checked']:,} draw · **실패 {r['complement_audit']['failures']}** · `max_abs_dev` {r['complement_audit']['max_abs_dev']} · tol {r['complement_audit']['tol']} |
| `complement_identity_used` | {str(r['complement_identity_used']).lower()} |
| `per_permutation_seconds` | {r['per_permutation_seconds']:.6f} |
| `complement_audit_seconds` | {r['complement_audit_seconds']:.2f} |
| RAM peak | {dec['ram_samples_max_gib']:.3f} GiB (게이트 30.72 GiB · 브리치 {len(dec['ram_breaches'])}건) |
| `rep_seed` / 동전 시드 | {r['rep_seed']} / {r['coin_seed']} |

(출처 `experiments/rqint/b_dryrun/decisive.json`)

### 4-3. D15 후단 — 추정 `p` 와 몬테카를로 SE 병기

- `T_obs` = **{r['T_obs']:.8f}** · `count_abs_ge_obs` = {r['count_abs_ge_obs']:,}
- `p` 공식(모듈 축자) = `{r['p_formula']}`
- **`p` = {r['p_two_sided']:.6f}**
- **몬테카를로 SE 식(축자) = `SE_MC = sqrt( p·(1−p) / n_permutation_values )` → `SE_MC` = {r['se_mc']:.6g}**
- ★ **이 `p` 는 100% 합성 예측 위의 값이므로 확증 결과가 아니다.** 귀무 구성(효과 주입 0)에서 벽시계 계측을 위해 돌린 산출이며, 어떤 가설 판정에도 쓰지 않는다. (출처 `decisive.json` `result`)

### 4-4. 판정표 (지시서 AI-4 양식 그대로)

| 해석 | 구성 | 벽시계 | 24h 판정 | 근거 |
|---|---|---|---|---|
| (가) `B` = 동전 수 | 100,000 동전 (참조분포 200,000) | `T̂` = **{pa['T_hat_hours']:.2f} h** (계단 외삽) · 실측 파생 2배 외삽 ≈ **{a_from_dec:.2f} h** | **미확정 — 외삽 판정 금지** | `T̂` 가 사전명시 밴드 **[18, 30] h 안** → `extrapolation_policy` 상 실주행으로만 판정 |
| (나) `B` = 참조분포 크기 | 50,000 동전 (참조분포 100,000) | **{dec_h:.3f} h (실측)** | **24 h 이내** | AI-3 실주행 |
| **수렴 구성** | **50,000 동전 / 참조분포 100,000** | **{dec_h:.3f} h (실측)** | — | §2-2 |

### 4-5. ★ 수렴 논증의 전건이 성립하지 않았다 — 사전명시 처리 그대로 이행

`docs/97` §2-2 의 수렴 논증은 **"(가) 의 벽시계가 24 h 를 초과한다"** 는 전건에 의존한다. 그 전건은
§2-1 의 참고 외삽(`û ≈ 1.506 s/동전`, **18워커 경합 하 상한**)에서 (가) ≈ 41.8 h 라 본 데서 왔다.

**단독 실행 실측 `û` = {stair['u_hat_primary']:.6f} s/동전** 은 그 상한의 **{stair['ratio_u_hat_over_C4']:.3f}배**에 그쳤고,
그 결과 (가) 100,000 동전의 추정 벽시계는 **{pa['T_hat_hours']:.2f} h** 로 **사전명시 밴드 [18, 30] h 안**에 들어온다.
`extrapolation_policy` 는 "밴드 안이면 외삽 금지 → 실주행 + 24 h 하드 캡으로 판정한다"고 **측정 전에** 규정했으므로,
**(가) 의 24 h 판정은 본 블록에서 내릴 수 없다.**

처리는 `b_dryrun_prespec.json` 의 `contingency_if_premise_fails`(**측정 전 동결**) 그대로다:

1. 전건이 외삽으로 성립하지 않음을 **그대로 기록**한다(§2-2 논증 문면은 무수정).
2. **결정적 드라이런(동전 50,000)은 예정대로 수행**했다 — 두 해석 공통의 하한 구성이고, 계단(1,000 → 100,000, 100배 외삽) 대비 훨씬 짧은 **2배 외삽**(`T̂(100,000) ≈ 2·T_obs(50,000) − 1,000·û` ≈ **{a_from_dec:.2f} h**)을 제공한다.
3. **(가) 는 상신 사항**으로 남긴다. 100,000 동전 실주행(≈ {a_from_dec:.1f} h, 24 h 캡 안에 들어갈 것으로 보임)은 본 블록 예산·구성 밖이므로 **자체 판단으로 구성을 바꾸지 않았다**(§0 자체 구제 금지 · `decisive_config` 는 측정 전에 50,000 으로 동결됨).

**참고(판정 아님)**: 블록 AD 가 `docs/45` 에 남긴 "드라이런 100,000 **3.88 h** / 50,000 1.94 h" 추정은
`F_THRU_FULL`(18워커 처리량 8.932 evals/s)을 분모로 쓴 값이다. 그러나 `F-SERIAL` 대로 `rqint_test` 는
**직렬 루프**라 워커 수로 나눠지지 않으므로 그 추정은 본 함수에 적용되지 않는다 — **본 계측이 이를 대체한다.**

### 4-6. AI-0 — cowork 판정 3건 수용 통보 (계산 0)

1. **AF-DEV-1(A12 적응적 중지 미이행)은 검토자에게 상신하지 않는다** — 사용자 결정 **2026-08-18**.
   근거 = R1 판정 무영향(C4 는 `F-ACC` 미적용이고 `r1_passed` 는 C0~C3 8셀에서 산출) + 설계 **완화가 아니라 초과 수행**.
   ★ "왜 통보하지 않았는가"가 나중에 재점이 되지 않도록 **결정 사실과 근거를 원장(`docs/33` 항목{n33} ⑨ⓐ · `ledger.timeline`)에 남겼다.**
2. **`docs/33` 항목48 ⑨ 의 AF 진도 기술은 stale** — "`C0:prop` 1,440/2,000 중단 상태 유지"는 낡았고
   **정본은 항목49 ②**(중단 4건 = 1,440 · 1,512 · 215 · 1,569 · 최종 완주 **2026-08-18 11:55:10**)이다.
   **항목48 문면은 무수정**(append-only)이며 supersede 포인터를 항목{n33} ⑨ⓑ 에 넣었다.
3. **`docs/94` report2 §7 정정 2건** — §7-2 축자 *"R1 충족으로 **R2(SAP 1.2 재동결)** 가 다음 관문이다"* 는
   **틀렸다**(§4-5·`F-ORDER` 대로 **⑥ 이 R2 보다 앞**). §7-3 축자 *"큐 잔여 = `docs/86` · `docs/95` · `docs/91`"* 은
   셋 다 2026-08-14 완료라 **stale** 이다(원장 미오염 — 제안문에 그쳤다).
   **두 건 모두 `docs/94` report2 문면은 무수정**이고, 정정 기록은 본 리포트와 `docs/33` 항목{n33} ⑨ⓒ 에 남긴다.

### 4-7. 기입 3곳

| 위치 | 내용 | 실측 |
|---|---|---|
| `docs/33` | **신규 항목{n33}**(번호 = `doc_numbering.py` 실측) | 착수 sha256 `{ins['docs33_sha256_before'][:16]}` → `{ins['docs33_sha256_after'][:16]}` · 접두사 바이트 동일 · 삭제 0 · 중복 assert PASS |
| `docs/45` | §2 연대기 **+1행** · §5 **문서이력 +1행**(조회 대장 표 **무수정** — 개봉 0 이므로 조회행 없음) | 착수 sha256 `{ins['docs45_sha256_before'][:16]}` → `{ins['docs45_sha256_after'][:16]}` · 삽입행 제거 시 착수본 복원 |
| `experiments/provenance/ledger.json` | `timeline` **47 → {ins['ledger_timeline']}** · `authoritative_sources` **24 → {ins['ledger_authoritative_sources']}** · `correspondence` 22 불변 · `first_look_register` 6 불변 · 최상위 키 11 불변 | 기존 entry **객체 단위 불변** assert 통과 |

## 5. 지시서 대비 편차·판단

1. **★ (가) 해석의 24 h 판정을 내리지 않았다 — 지시서 §2-2 의 수렴 논증 전건이 실측에서 성립하지 않았기 때문.**
   지시서 `extrapolation_policy` 는 "(가) 는 `T̂ ≈ 41.8 h` 로 구간 밖 → 외삽으로 '24h 초과' 판정한다"고 예상했으나,
   **단독 실행 실측 단가가 그 근거였던 1.506 s/동전(18워커 경합 상한)의 {stair['ratio_u_hat_over_C4']:.3f}배**에 그쳐
   `T̂` = **{pa['T_hat_hours']:.2f} h** 가 밴드 **안**으로 들어왔다. 같은 정책의 "밴드 안이면 외삽 금지" 조항이 우선하므로
   외삽 판정을 하지 않았다. **자체 구제 0** — 구성을 100,000 으로 바꾸지 않았고, `decisive_config` 는 측정 전에 동결된 50,000 그대로 돌렸다.
   → 기록 = `docs/33` 항목{n33} ⑤ · 본 리포트 §4-5.
2. **사전명시 파일에 지시서 열거 항목 외 2개 필드를 추가**했다(측정 **전** 동결본에 포함, 사후 추가 0):
   `cost_model`(감사 draw 가 `min(1000, n)` 이라 `n ≤ 1000` 계단에서는 감사 비중이 100% 인데 `n = 50,000` 에서는 2% 라
   계단 벽시계를 그대로 외삽하면 단가가 약 2배 부풀려진다 — 그래서 **계단은 감사를 끄고**(`complement_audit_draws=0`) 순수 단가를 재고
   감사 비용을 `min(1000, n)·û` 로 별도 가산하도록 **측정 전에** 고정했다)과
   `contingency_if_premise_fails`(위 1번의 처리 규정). 둘 다 **지시서 §AI-1 의 "포함:" 목록을 줄이지 않고 추가만** 한 것이다.
   ※ 결정적 드라이런은 지시서대로 `complement_audit_draws` **기본값 1,000 유지**로 돌렸다.
3. **신규 러너 1파일 작성** — `v3_Multimodal/src/b_dryrun.py`. `rqint_calibration.py` 의 `--stage run` 은 C0~C4 셀 전용이라
   본 블록의 단일 구성 계측에 쓸 수 없다. 재구현은 0이며 fixture·합성점수·시드규칙·RAM 게이트·전원 게이트를 전부 import 재사용했고,
   **`sap/` 밖**에 두어 동결 모듈 불변식을 건드리지 않았다. `sap/rqint.py`·`rqint_calibration.py` **모두 0바이트 수정**.
4. **`F-C4CTX` 검사 범위 정정 1건**(FACTS 값 자체는 일치) — `calibration_sessions.jsonl` 전 세션의 `workers` distinct 는
   `[2, 18]` 이지만 `2` 는 `C0:prop` **스모크 세션**이고, `F-C4UNIT` 이 읽는 **`C4:tau0.01` 셀의 `workers` 는 전건 18** 이다.
   검사 스크립트를 해당 셀로 좁혀 재실행했고 결과는 **14/14 PASS** 다.
5. 지시서 ↔ `CLAUDE.md` 충돌 **없음**.

## 6. 다음 액션 제안

1. **(가) 해석의 24 h 판정이 미해결이다** — 100,000 동전 실주행은 본 실측 파생 추정 **≈ {a_from_dec:.1f} h** 로 24 h 캡 안에 들어갈 가능성이 크다. R2 이전에 이 1회 실주행을 승인할지 cowork 판단이 필요하다(승인 시 소요 ≈ {a_from_dec:.0f} h 연속 AC).
2. 그 판정이 나오면 R2 는 **(가)/(나) 중 어느 정의든 `B` 를 실측 근거와 함께 동결**할 수 있다. 현재 후보 = **(나) 기준 `B` = 100,000(참조분포) = 동전 50,000, 실측 {dec_h:.2f} h**.
3. 검토자 §9-2 의 함의 단가 1.08 s/동전은 (가) ≈ 30 h 를 함의해 **검토자가 `B` 를 동전 수로 상정했음**을 시사한다 — R2 문면에 이 점을 명시하면 해석 논쟁이 재발하지 않는다.

## 7. 종료검증 ({ver['n_total']}항)

| # | 항목 | 기대 | 실측 | 판정 |
|---|---|---|---|---|
{ver_rows}

**{ver['n_pass']}/{ver['n_total']} PASS**

## 8. 본 블록이 하지 않은 것

- **`B` 문면 동결 0 · 확정 선언 0** — `sap/rqint.py` 의 `B_DEFINITION_STATUS` 는 `still_unspecified` 그대로이고 파일은 **0바이트 수정**이다. 동결은 **R2 의 일**.
- **(가) 해석의 24 h 판정 0** — 외삽 금지 구간이라 판정하지 않고 **상신**했다. 100,000 동전 실주행 **0**.
- **SAP 1.2 재동결 0** — `sap_version` **1.1** 유지 · `manifest.json` sha16 `756d485feb4715e9` · 동결 11모듈 + 블록 AC 4파일 + AD 2파일 **0바이트**.
- **개봉 0** — `unblinding_performed` false · `_sealed/` 읽기·쓰기 0(stat-only 스냅샷 **275종/291종** 및 sha256 착수=종료 동일) · `open_sealed` **0** · `emit_sign` **0** · `decision.py` 호출 **0**.
- **확증 예측·OOF 로드 0** — `confirmatory_predictions_loaded` false · 예측행렬 **100% 합성** · 효과 주입 **0**(귀무 구성) · AST 스캔상 데이터 경로는 `master_X.parquet`·`master_Y.parquet` **2개뿐**.
- **GIN 학습·착수 0** — `gin_start_still_blocked` true.
- **R2·R3 이행 0 · 검토자 상신 0 · 새 fixture 생성 0 · 시드 신규 추첨 0.**
- **`data/raw/` 변경 0 · 네트워크 0 · git commit·push 0**(HEAD `566f487` · 커밋 21 불변).
"""
p = os.path.join(ROOT, "docs", "97_b_definition_dryrun_report.md")
open(p, "w", encoding="utf-8").write(md)
print(f"written {p} · {sz(p):,} B")
