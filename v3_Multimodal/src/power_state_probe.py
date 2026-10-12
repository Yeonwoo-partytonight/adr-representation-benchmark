#!/usr/bin/env python3
"""power_state_probe.py — 전원 상태(AC/배터리)·powermode 실측 기록기.

용도 (보정 지시 3건 중 블록 C 보고 보정 · D-4 보정):
  - 블록 C(§13-5 반복2·3 + consensus) 실행 구간의 **전원 상태·powermode·시각**을 기록한다.
  - 블록 D 지속부하 구간에서도 동일 함수로 샘플을 남긴다.

측정 전용. 네트워크 호출 없음. 결과 값(AP·Δ·p) 일절 미접근 — `_sealed/` 미개봉.

기록 두 층:
  1) **실시간 샘플**(`power_samples.jsonl`) — 호출 시점의 `pmset -g ps` / `pmset -g live`.
  2) **소급 이력**(`pmset -g log`) — AC↔배터리 전환 시각. 샘플러를 늦게 붙여도 구간 전체를
     재구성할 수 있는 근거. 커널 로그이므로 사후 조작 없이 구간 전체를 덮는다.

실행:
  python3 v3_Multimodal/src/power_state_probe.py --run-dir experiments/runs/v3_confirm_rep23 \
      --tag block_C --window-start "2026-07-27 21:26:46" [--watch-pid 12345 --interval 120]
"""
from __future__ import annotations

import os
import re
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def now_kst():
    return datetime.now(KST)


def ts_str(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S KST")


def sh(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception as e:                                          # noqa: BLE001
        return f"<unavailable: {e}>"


def sample(tag=""):
    """호출 시점의 전원 상태 1건. `null_compute_probe2.power_state()` 와 동일 정보원."""
    ps = sh(["pmset", "-g", "ps"])
    live = sh(["pmset", "-g", "live"])
    powermode = None
    for ln in live.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0] == "powermode":
            try:
                powermode = int(p[1])
            except ValueError:
                powermode = p[1]
    m = re.search(r"(\d+)%", ps)
    return {
        "ts_kst": ts_str(now_kst()),
        "tag": tag,
        "on_ac_power": "AC Power" in ps,
        "power_source": ("AC" if "AC Power" in ps else
                         ("Battery" if "Battery Power" in ps else "unknown")),
        "powermode_live": powermode,
        "low_power_mode_off": (powermode == 0),
        "battery_percent": int(m.group(1)) if m else None,
        "charging": ("; charging" in ps),
        "raw_pmset_ps": ps.strip(),
        "thermal_pressure": sh(["sh", "-c", "pmset -g therm 2>/dev/null | head -20"]).strip(),
    }


_LOG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ([+-]\d{4})\s")


def source_history(window_start=None, window_end=None):
    """`pmset -g log` 에서 AC↔배터리 **전환 시각**을 소급 추출.

    커널 전원 로그 기반이라 샘플러를 늦게 붙인 구간도 재구성된다.
    반환 = {transitions:[{ts_kst, source, line}], source_at_window_start, sources_in_window}
    """
    raw = sh(["pmset", "-g", "log"], timeout=120)
    events = []
    for ln in raw.splitlines():
        m = _LOG_TS.match(ln)
        if not m:
            continue
        low = ln.lower()
        if "using ac" in low:
            src = "AC"
        elif "using batt" in low:
            src = "Battery"
        else:
            continue
        events.append({"ts": m.group(1), "source": src, "line": ln.strip()})

    transitions, prev = [], None
    for e in events:
        if e["source"] != prev:
            transitions.append(e)
            prev = e["source"]

    at_start, at_start_ts, in_window, ev_window = None, None, [], []
    last_transition_before = None
    if window_start:
        for e in events:
            if e["ts"] <= window_start:
                at_start, at_start_ts = e["source"], e["ts"]
        for t in transitions:
            if t["ts"] <= window_start:
                last_transition_before = t
        end = window_end or "9999"
        ev_window = [e for e in events if window_start <= e["ts"] <= end]
        in_window = sorted({e["source"] for e in ev_window})
    return {
        "n_events_parsed": len(events),
        "transitions": transitions[-40:],
        "source_at_window_start": at_start,
        "source_at_window_start_evidence_ts": at_start_ts,
        "last_transition_before_window": last_transition_before,
        "n_events_in_window": len(ev_window),
        "sources_seen_in_window": in_window,
        "window_start": window_start, "window_end": window_end,
        "log_source": "pmset -g log (커널 전원 로그 — 소급 재구성)",
        "interpretation": (
            "window 내 전원 소스 이벤트 0건 = 전원 전환 없음 → window 시작 직전 상태가 구간 내내 유지"
            if window_start and not ev_window else
            "window 내 전원 소스 이벤트 존재 — transitions 참조"),
    }


def append_sample(run_dir, rec):
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "power_samples.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_samples(run_dir):
    p = os.path.join(run_dir, "power_samples.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(ln) for ln in open(p) if ln.strip()]


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def summarize(run_dir, tag, window_start, window_end=None):
    """구간 요약 + **wall-clock 사용 제한 문구**를 함께 고정한다."""
    samples = read_samples(run_dir)
    hist = source_history(window_start, window_end)
    in_tag = [s for s in samples if s.get("tag", "").startswith(tag)]
    on_batt = any(not s["on_ac_power"] for s in in_tag) or \
        ("Battery" in (hist["sources_seen_in_window"] or [])) or \
        (hist["source_at_window_start"] == "Battery")
    lpm_on = any(s["powermode_live"] not in (0, None) for s in in_tag)
    clean = (not on_batt) and (not lpm_on)

    batt = [s["battery_percent"] for s in in_tag if s["battery_percent"] is not None]
    out = {
        "_scope": f"{tag} 실행 구간 전원 상태 실측 — 측정 전용. 결과 값(AP·Δ·p) 미접근.",
        "tag": tag,
        "window_start_kst": window_start, "window_end_kst": window_end,
        "n_samples": len(in_tag),
        "live_sample_coverage": {
            "first_sample_kst": in_tag[0]["ts_kst"] if in_tag else None,
            "last_sample_kst": in_tag[-1]["ts_kst"] if in_tag else None,
            "note": ("실시간 샘플이 구간 시작보다 늦게 붙은 경우, 그 앞 구간은 "
                     "`source_history`(pmset 커널 로그 — 전환 이벤트 0건 = 전환 없음) 와 "
                     "`battery_percent_trend`(단조 방전 = AC 미연결) 로 보강한다."),
        },
        "battery_percent_trend": batt,
        "battery_monotonic_discharge": bool(len(batt) >= 2 and
                                            all(b <= a for a, b in zip(batt, batt[1:])) and
                                            batt[-1] < batt[0]),
        "samples": in_tag,
        "source_history": hist,
        "on_battery_during_window": bool(on_batt),
        "low_power_mode_on_during_window": bool(lpm_on),
        "powermode_values_seen": sorted({str(s["powermode_live"]) for s in in_tag}),
        "wall_clock_comparable": bool(clean),
        "wall_clock_usage_rule": (
            "이 구간의 wall-clock 은 **비교 불가**(배터리 전원·저전력 모드 powermode=1). "
            "블록 D 및 §13-4 총시간 추정에 **투입 금지**. "
            "전원·클럭 상태는 산출물 **바이트 동일성에는 영향 없음** — RF random_state·"
            "연산 순서·부동소수 결과가 전원 상태에 의존하지 않으므로 sealed 산출물 sha256 및 "
            "부호 판정은 유효하다."
            if not clean else
            "AC 전원·저전력 모드 해제 구간 — wall-clock 비교 가능."),
        "ts_kst": ts_str(now_kst()),
    }
    p = os.path.join(run_dir, f"power_state_{tag}.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--tag", default="block_C")
    ap.add_argument("--window-start", default=None, help='"YYYY-MM-DD HH:MM:SS"')
    ap.add_argument("--window-end", default=None)
    ap.add_argument("--watch-pid", type=int, default=None,
                    help="이 PID 가 살아있는 동안 --interval 마다 샘플, 종료 시 최종 샘플 후 요약")
    ap.add_argument("--interval", type=float, default=120.0)
    ap.add_argument("--summarize-only", action="store_true")
    args = ap.parse_args()

    run_dir = args.run_dir if os.path.isabs(args.run_dir) else os.path.join(ROOT, args.run_dir)

    if not args.summarize_only:
        rec = append_sample(run_dir, sample(f"{args.tag}:start"))
        print(f"[power] {rec['ts_kst']} · {rec['power_source']} · powermode={rec['powermode_live']} "
              f"· batt={rec['battery_percent']}%")

        if args.watch_pid:
            while pid_alive(args.watch_pid):
                time.sleep(args.interval)
                if not pid_alive(args.watch_pid):
                    break
                r = append_sample(run_dir, sample(f"{args.tag}:during"))
                print(f"[power] {r['ts_kst']} · {r['power_source']} · "
                      f"powermode={r['powermode_live']} · batt={r['battery_percent']}%")
            r = append_sample(run_dir, sample(f"{args.tag}:end"))
            print(f"[power] {r['ts_kst']} · {r['power_source']} · powermode={r['powermode_live']} "
                  f"· batt={r['battery_percent']}% (watched PID {args.watch_pid} 종료)")

    end = args.window_end or ts_str(now_kst())[:19]
    out, p = summarize(run_dir, args.tag, args.window_start, end)
    print(f"[power] 요약 저장 → {os.path.relpath(p, ROOT)}")
    print(f"[power] 배터리 구간={out['on_battery_during_window']} · "
          f"저전력모드={out['low_power_mode_on_during_window']} · "
          f"wall-clock 비교가능={out['wall_clock_comparable']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
