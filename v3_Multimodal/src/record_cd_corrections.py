#!/usr/bin/env python3
"""record_cd_corrections.py — 보정 3건 기록: `docs/33` 항목16 + `docs/45` §5 추기 + ledger append.

보정 대상 (사용자 지시, 2026-07-27):
  1) 블록 C 보고 보정 — 반복2·3 실행 시점 전원 상태·powermode 기록 + "wall-clock 비교 불가
     (배터리·저전력 모드), 바이트 동일성에는 영향 없음" 명시 + 블록 D·§13-4 추정 투입 금지.
  2) D-3 보정 — 처리량 = w / wall_max(마지막 완료 기준), 평균 기반 금지. 워커별 wall
     min/median/max/(max−min)/median 보고. 코어 배정 규칙 명시 + P/E 비대칭 한계.
  3) D-4 보정 — 열감쇠·지속부하 baseline = 단독 1 permutation 완주 값만. 워커0(identity) wall
     은 0-diff 검증 전용. 지속부하 구간 전원 상태·powermode·시각 로깅.

재계산 0 · 모델학습 0 · 네트워크 0 · sealed 미개봉 · p 미계산. 기록 전용.
"""
from __future__ import annotations

import os
import json
import collections
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KST = timezone(timedelta(hours=9))
DOCS33 = os.path.join(ROOT, "docs", "33_prereg_deviation_log.md")
DOCS45 = os.path.join(ROOT, "docs", "45_research_integrity_ledger.md")
LED = os.path.join(ROOT, "experiments", "provenance", "ledger.json")
PWR = os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep23", "power_state_block_C.json")
CSUM = os.path.join(ROOT, "experiments", "runs", "v3_confirm_rep23", "block_C_summary.json")

MARK33 = "16. **블록 C compute 조건 고지 + 블록 D 측정 규약 보정**"
MARK45 = "블록 C compute 조건(전원)"


def main():
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    pwr = json.load(open(PWR))
    csum = json.load(open(CSUM))
    hist = pwr["source_history"]

    src_start = hist["source_at_window_start"]
    n_ev = hist["n_events_in_window"]
    batt = pwr["battery_percent_trend"]
    pm = "·".join(pwr["powermode_values_seen"])
    walls = {r: round(v["wall_clock_sec"], 1) for r, v in csum["repeats"].items()}

    # ── docs/33 항목16 ───────────────────────────────────────────────────────
    d33 = open(DOCS33).read()
    assert MARK33 not in d33, "docs/33 항목16 이미 기록됨"
    entry = f"""
---

- **{now} | 블록 C compute 조건 정직 고지 + 블록 D 측정 규약 보정 3건 — 재계산 0·모델학습 0·네트워크 0·sealed 미개봉·p 미계산. ① 블록 C(§13-5 반복2·3+consensus)는 **배터리 전원·저전력 모드(powermode={pm})** 에서 실행되어 **wall-clock 비교 불가**(산출물 **바이트 동일성에는 영향 없음**), 해당 wall-clock 은 블록 D·§13-4 추정에 **투입 금지**. ② 블록 D-3 **처리량 정의 = w / wall_max**(워커 중 마지막 완료 기준), 평균 기반 계산 금지 + 코어 배정 규칙·P/E 비대칭 한계 명시. ③ 블록 D-4 **열감쇠·지속부하 baseline = 단독(w=1) 1 permutation 완주 값만**, 병렬 워커0(identity) wall 은 0-diff 검증 전용 | 측정 조건이 다른 시간값을 섞으면 §13-4 총시간 추정이 무효가 된다. 처리량을 평균으로 잡으면 P/E 코어 비대칭에서 생기는 워커 간 불균등이 낙관적으로 상쇄되고, 오버서브스크립션 상태의 wall 을 baseline 으로 쓰면 열감쇠가 과대추정된다. 세 보정 모두 **시간 측정 규약**에만 관여하며 통계 정의·가설·집계·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`) 불변 | 확증 조회 = N (본 항목에서 새 split test/OOF 미조회 — 부호는 2026-07-27 22:14 기조회, `sealed_human_read=false`: `open_sealed` **0건**)**

### 세부 (근거 추적)

{MARK33}:
   - **블록 C 전원 실측**: 실행 구간 `{pwr['window_start_kst']}` ~ `{pwr['window_end_kst']}`. 전원 소스 = **배터리**, powermode = **{pm}**(저전력 모드 ON). 근거 = ① `pmset -g log` 상 구간 시작 직전 상태 `{src_start}`(직전 이벤트 `{hist['source_at_window_start_evidence_ts']}`)이며 구간 내 전원 전환 이벤트 **{n_ev}건** → 전환 없음, ② 실시간 샘플 {pwr['n_samples']}건 전부 배터리·powermode={pm}, ③ 배터리 잔량 단조 방전 {batt}(AC 연결 시 나타나지 않는 패턴). 산출 = `experiments/runs/v3_confirm_rep23/power_state_block_C.json`.
   - **wall-clock 사용 제한**: 블록 C 기록의 반복별 wall(반복2 {walls.get('2')}s · 반복3 {walls.get('3')}s)은 **배터리·저전력 구간 측정치**라 AC·정상 클럭 조건과 **비교 불가**하다. 블록 D 벤치마크·§13-4 총시간 추정에 **투입 금지**하며, 블록 D 스크립트는 블록 C 시간값을 일절 읽지 않는다(`compute_public.json` → `excluded_inputs.block_C_wallclock`).
   - **바이트 동일성 무영향(정직 고지)**: 전원·클럭 상태는 산출물의 **바이트 동일성에 영향을 주지 않는다**. RF `random_state=42` 고정·PT별 독립·연산 순서 불변이므로 부동소수 결과가 전원 상태에 의존하지 않으며, 따라서 반복2·3·consensus 의 `_sealed` sha256 및 **Δ 부호 판정은 유효**하다. 제한되는 것은 **시간 비교**뿐이다.
   - **D-3 처리량 정의(보정)**: **처리량 = w / wall_max**, `wall_max` = 워커 중 **마지막 완료** wall. 평균·중앙값 기반 처리량 계산 **금지**(min·median 은 워커 간 불균등 진단용 **기술통계**로만 보고). 워커 수마다 워커별 wall `min / median / max / (max−min)/median` 을 보고한다. setup 상각 처리량도 `w / max(per_worker_recurring_s)` 로 max 기준을 쓴다.
   - **코어 배정 규칙(명시)**: **워커당 배정 코어 = logical // w**(logical=18, 최소 1). **RF 우선 배정**(`rf_n_jobs` = min(요청, 배정코어); `-1` 이면 배정코어 전량) → **잔여 슬롯을 MOC** 에(`moc_n_jobs` = max(1, 배정코어 // `rf_n_jobs`); 원 구성이 `None` 이면 `None` 유지). BLAS 스레드 상한도 동일 값으로 설정(부모 설정 → spawn 상속).
   - **한계(P/E 비대칭)**: Apple Silicon 은 P코어 6·E코어 12 로 비대칭이고 코어 배정은 macOS 스케줄러가 QoS 기준으로 수행한다. 위 규칙은 워커당 **스레드 수 상한**만 균등 분배할 뿐 물리 코어를 고정(affinity pinning)하지 못한다(macOS 는 사용자 수준 CPU affinity API 미제공). 따라서 워커별 실제 P/E 혼합 비율이 불균등할 수 있고 이는 워커 간 wall 편차로 관측된다 — 처리량을 `wall_max` 로 정의한 것은 이 불균등을 낙관적으로 상쇄하지 않기 위함이다.
   - **D-4 baseline 규칙(보정)**: 열감쇠·지속부하 baseline 은 **단독(w=1) 1 permutation 완주 값만** 사용한다(D-4a). 병렬 배치(D-4b)의 **워커0(identity) wall 은 오버서브스크립션 상태 측정치**이므로 baseline 금지 — **0-diff 검증 용도로만** 쓴다. 열감쇠율 = 단독 런의 첫 fold → 마지막 fold 변화율, 지속부하 하한(600s) 충족 여부도 단독 런 기준으로 판정한다.
   - **D-4 전원 로깅(보정)**: 지속부하 구간(D-4a·D-4b 각각)의 **전원 상태(AC/배터리)·powermode 값·시각**을 60s 주기로 샘플해 로그·`compute_public.json` 에 기록한다. 구간 중 AC 이탈 또는 powermode≠0 이 관측되면 해당 구간 wall-clock 을 **비교 불가**로 표시하고 투영표를 잠정 처리한다.
   - **실행 순서(확정)**: 블록 C 완료 → **AC 연결 + `pmset -g | grep powermode` == 0 확인** → 블록 D 시작 → **블록 D 완료 후 정지**. §13-4 본런은 **별도 지시**로만 착수한다(주말 예정).
   - **불변**: 통계 정의·가설·집계·성공기준·`ladder_freeze.json`(sha16 `b885585aefbabb32`)·SAP 동결 모듈 sha256 전부 불변. 본 보정은 **시간 측정 규약**에만 관여한다.
"""
    open(DOCS33, "w").write(d33.rstrip("\n") + "\n" + entry)
    print("[1/3] docs/33 항목16 추가")

    # ── docs/45 §5 추기 ──────────────────────────────────────────────────────
    d45 = open(DOCS45).read()
    assert MARK45 not in d45, "docs/45 추기 이미 기록됨"
    anchor = "> ⚠️ **추기(2026-07-27 22:14 KST)**: 그 뒤 `access.log`는"
    i = d45.index(anchor)
    end = d45.index("\n", i)
    note = (
        f"\n> ⚠️ **추기({now}) — {MARK45}**: 블록 C(반복2·3+consensus)는 전 구간 **배터리 전원·"
        f"저전력 모드(powermode={pm})** 에서 실행되었다(근거: `power_state_block_C.json` — 구간 내 "
        f"전원 전환 이벤트 {n_ev}건·실시간 샘플 {pwr['n_samples']}건 전부 배터리·배터리 잔량 단조 방전 "
        f"{batt}). 따라서 이 블록의 **wall-clock 은 비교 불가**이며 블록 D·§13-4 총시간 추정에 "
        f"**투입하지 않는다**. 전원·클럭 상태는 **바이트 동일성에는 영향이 없으므로**(RF "
        f"`random_state=42` 고정·연산 순서 불변) 위 표의 sealed sha256 과 Δ 부호 판정은 유효하다 — "
        f"제한되는 것은 시간 비교뿐이다."
    )
    d45 = d45[:end + 1] + note + "\n" + d45[end + 1:]
    open(DOCS45, "w").write(d45)
    print("[2/3] docs/45 §5 추기 추가")

    # ── ledger append ────────────────────────────────────────────────────────
    led = json.load(open(LED), object_pairs_hook=collections.OrderedDict)
    led["timeline"].append(collections.OrderedDict([
        ("ts", now[:10]), ("ts_kst", now),
        ("actor", "vscode-claude"),
        ("step", "블록 C compute 조건 고지 + 블록 D 측정 규약 보정 3건"),
        ("event", (
            "① 블록 C(§13-5 반복2·3+consensus) 실행 구간 전원 상태 실측·기록 — 전 구간 배터리·"
            f"powermode={pm}(저전력 ON) → wall-clock 비교 불가, 블록 D·§13-4 추정 투입 금지. "
            "바이트 동일성에는 영향 없음(sealed sha256·부호 판정 유효). "
            "② 블록 D-3 처리량 정의를 w/wall_max(마지막 워커 완료 기준)로 확정, 평균 기반 계산 금지, "
            "워커별 wall min/median/max/(max−min)/median 보고 의무화, 코어 배정 규칙"
            "(워커당=logical//w · RF 우선→잔여 MOC)과 P/E 비대칭 한계 명시. "
            "③ 블록 D-4 열감쇠·지속부하 baseline 을 단독(w=1) 1 permutation 완주 값으로 한정, "
            "병렬 워커0(identity) wall 은 0-diff 검증 전용, 지속부하 구간 전원·powermode·시각 60s 주기 로깅. "
            "재계산 0·모델학습 0·네트워크 0·sealed 미개봉.")),
        ("artifacts", [
            "experiments/runs/v3_confirm_rep23/power_state_block_C.json",
            "experiments/runs/v3_confirm_rep23/power_samples.jsonl",
            "v3_Multimodal/src/power_state_probe.py",
            "v3_Multimodal/src/null_compute_probe2.py (D-3·D-4 보정 반영)",
            "docs/33 항목16", "docs/45 §5 추기",
        ]),
        ("confirmatory", "N (새 split test/OOF 미조회 — 부호는 2026-07-27 22:14 기조회, open_sealed 0건)"),
        ("result_summary", (
            f"블록 C 전원 = 배터리·powermode {pm} 전 구간(전환 이벤트 {n_ev}건, 샘플 "
            f"{pwr['n_samples']}건, 잔량 {batt}). wall_clock_comparable=false. "
            "블록 D 측정 규약 3건 보정 코드 반영 완료(미실행 — AC·powermode=0 확인 후 착수).")),
        ("integrity_note", (
            "통계 정의·가설·집계·성공기준 불변 · ladder_freeze.json sha16 b885585aefbabb32 불변 · "
            "SAP 동결 모듈 sha256 불변 · 본 보정은 시간 측정 규약에만 관여 · "
            "empirical_p 미호출 · p 미계산 · bootstrap/sign-flip/SESOI/성공판정 미실행 · "
            "§13-4 본런 미착수(별도 지시) · data/raw 불변 · docs/30 무수정 · git commit 없음.")),
    ]))
    json.dump(led, open(LED, "w"), indent=1, ensure_ascii=False)
    print(f"[3/3] ledger.json timeline append (총 {len(led['timeline'])}건)")


if __name__ == "__main__":
    main()
