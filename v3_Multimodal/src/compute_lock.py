#!/usr/bin/env python3
"""compute_lock.py — 배타 실행 락 + G-IDLE 유휴 게이트 (블록 E-1).

목적
----
§13-4 본런은 **wall-clock 측정이 결론에 직결**되므로, 다른 세션·다른 스크립트가
동시에 CPU를 쓰면 측정치가 오염된다. 본 모듈은 두 가지를 강제한다.

  1) **배타 락** — `experiments/runs/.compute_lock.json` 을 `O_EXCL` 로 생성.
     보유자 생존 시 **exit 9** (아무 작업도 하지 않음). 죽은 보유자는 원문을
     `.compute_lock.stale.jsonl` 에 **append 보존**한 뒤 1회 인수.
  2) **G-IDLE** — 프로젝트 계산 프로세스·시스템 부하가 없는지 3종(A/B/C)으로 확인.
     하드 게이트 위반 시 **exit 10**.

성격 고지
--------
본 모듈은 **동결 아티팩트가 아니다**. SAP 11모듈·`ladder_freeze.json` 을 읽지도
수정하지도 않으며, 통계량·가설·집계·성공기준과 무관한 **실행 인프라**다.
어떤 수치도 산출하지 않는다(측정·판정·p 계산 없음).

사용
----
    from compute_lock import ComputeLock, gate_a_load, gate_b_exclusive, gate_c_settle

    def main():
        with ComputeLock(script="null_main.py", role="runner"):
            gate_a_load()                       # 최초 진입 1회 (하드)
            gate_b_exclusive("stage_d3:before")  # 스테이지 직전 (하드)
            ...
            gate_b_exclusive("stage_d3:after")   # 스테이지 직후 (하드)
            caveat = gate_c_settle()             # 스테이지 사이 (soft)

**부모만 획득한다.** `main()` 안에서만 `ComputeLock` 을 쓰고, spawn 자식 워커는
본 모듈의 락 로직에 접근하지 않는다(자식이 락을 만지면 부모 해제 시 경합).
"""
from __future__ import annotations

import errno
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KST = timezone(timedelta(hours=9))

LOCK_PATH = os.path.join(ROOT, "experiments", "runs", ".compute_lock.json")
STALE_PATH = os.path.join(ROOT, "experiments", "runs", ".compute_lock.stale.jsonl")

EXIT_LOCK_BUSY = 9      # 다른 계산 세션이 락 보유 중
EXIT_NOT_IDLE = 10      # G-IDLE 위반 (부하 또는 경쟁 프로세스)

# G-IDLE 임계값 (실행 전 고정 — 결과 무참조)
LOAD_HARD_MAX = 2.0     # 게이트 A / C 통과선
LOAD_ABORT = 4.0        # 게이트 C 즉시 중단선
SETTLE_INTERVAL_S = 15
SETTLE_MAX_S = 180

# recorder 역할 재시도 (문서 기입 스크립트는 짧으므로 대기 후 진입 허용)
RECORDER_RETRY_INTERVAL_S = 5
RECORDER_RETRY_MAX_S = 60

# 게이트 B 가 경쟁으로 간주하는 프로젝트 계산 스크립트
COMPUTE_SCRIPT_RE = re.compile(
    r"confirmatory_oof_rep1|confirmatory_oof_rep23|null_compute_probe2|null_timing_probe|"
    r"ladder_confirmatory|null_probe2_record|null_main"
)

# **실제 python 인터프리터**인지 판정 (argv[0] basename 기준).
#   · `/bin/zsh -c "... .venv/bin/python3 ..."` 처럼 명령줄이 python 을 *언급만* 하는
#     래퍼 셸(= 자기 자신을 띄운 부모)을 경쟁 프로세스로 오탐하지 않기 위함.
#   · macOS/Homebrew venv 는 ps 에 프레임워크 실체 경로
#     `.../Python.app/Contents/MacOS/Python` (basename **대문자 `Python`**)로 보이므로
#     **반드시 대소문자 무시**로 매칭한다(이 누락이 게이트 B 전면 무력화를 일으켰다).
PYTHON_EXE_RE = re.compile(r"^python(\d+(\.\d+)*)?$", re.IGNORECASE)


def now_kst_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


# ── 프로세스 조사 ────────────────────────────────────────────────────────────
def _ps_snapshot():
    """`ps -Ao pid,ppid,command` 판독 → [(pid, ppid, command), ...]."""
    try:
        out = subprocess.run(["ps", "-Ao", "pid,ppid,command"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception as e:                                  # ps 실패 = 판정 불가
        raise RuntimeError(f"ps 판독 실패 — G-IDLE 판정 불가: {e}")
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            rows.append((int(parts[0]), int(parts[1]), parts[2]))
        except ValueError:
            continue
    return rows


def _descendants(rows, root_pid):
    """root_pid 의 후손 pid 집합(ppid 트리 BFS)."""
    children = {}
    for pid, ppid, _ in rows:
        children.setdefault(ppid, []).append(pid)
    seen, stack = set(), list(children.get(root_pid, []))
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(children.get(p, []))
    return seen


def _is_python_process(cmd: str) -> bool:
    """argv[0] 의 basename 이 python 인터프리터인가 (셸 래퍼 오탐 방지)."""
    argv0 = cmd.split(None, 1)[0] if cmd.strip() else ""
    return bool(PYTHON_EXE_RE.match(os.path.basename(argv0)))


def competing_processes():
    """자신·후손·caffeinate·ps 를 제외한 '프로젝트 계산 python 프로세스' 목록."""
    rows = _ps_snapshot()
    me = os.getpid()
    mine = _descendants(rows, me) | {me}
    out = []
    for pid, ppid, cmd in rows:
        if pid in mine:
            continue
        if "caffeinate" in cmd:
            continue
        if re.search(r"(^|/)ps( |$)", cmd) or cmd.strip().startswith("ps "):
            continue
        if not _is_python_process(cmd):             # 셸 래퍼·에디터 등 제외
            continue
        if ROOT in cmd or COMPUTE_SCRIPT_RE.search(cmd):
            out.append({"pid": pid, "ppid": ppid, "command": cmd[:200]})
    return out


# ── G-IDLE ──────────────────────────────────────────────────────────────────
def _die(code, msg):
    print(f"\n[G-IDLE/LOCK] {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def gate_a_load(label="entry"):
    """게이트 A (하드) — 최초 측정 진입 시 1분 load average < 2.0."""
    load1 = os.getloadavg()[0]
    if not (load1 < LOAD_HARD_MAX):
        _die(EXIT_NOT_IDLE,
             f"게이트 A 실패 [{label}] — load1={load1:.2f} ≥ {LOAD_HARD_MAX} "
             f"({now_kst_str()}). 측정 진입 중단.")
    print(f"[G-IDLE A] PASS [{label}] load1={load1:.2f} < {LOAD_HARD_MAX}", flush=True)
    return {"gate": "A", "label": label, "load1": load1, "pass": True}


def gate_b_exclusive(label):
    """게이트 B (하드) — 경쟁 계산 프로세스 0건. 모든 스테이지 직전·직후 호출."""
    procs = competing_processes()
    if procs:
        detail = " | ".join(f"pid={p['pid']} {p['command'][:120]}" for p in procs[:5])
        _die(EXIT_NOT_IDLE,
             f"게이트 B 실패 [{label}] — 경쟁 계산 프로세스 {len(procs)}건 ({now_kst_str()}): {detail}")
    print(f"[G-IDLE B] PASS [{label}] 경쟁 프로세스 0건", flush=True)
    return {"gate": "B", "label": label, "competitors": 0, "pass": True}


def gate_c_settle(label="between-stages"):
    """게이트 C (soft) — 병렬 스테이지 직후 잔여 load 감쇠를 기다린다.

    병렬 스테이지 직후의 load 는 **자기 자식의 잔여 감쇠분**이라 하드 게이트로
    잡으면 오탐이다. 따라서 정착 대기 후 판정한다.
      · < 2.0        → 통과
      · ≥ 4.0        → exit 10 (외부 부하로 간주)
      · 2.0 ~ 4.0    → settle_caveat=true 기록 후 통과
    """
    t0 = time.perf_counter()
    samples = []
    while True:
        load1 = os.getloadavg()[0]
        samples.append(round(load1, 2))
        if load1 < LOAD_HARD_MAX:
            print(f"[G-IDLE C] PASS [{label}] load1={load1:.2f} "
                  f"({time.perf_counter() - t0:.0f}s 대기)", flush=True)
            return {"gate": "C", "label": label, "load1": load1,
                    "waited_s": round(time.perf_counter() - t0, 1),
                    "samples": samples, "settle_caveat": False, "pass": True}
        if load1 >= LOAD_ABORT:
            _die(EXIT_NOT_IDLE,
                 f"게이트 C 실패 [{label}] — load1={load1:.2f} ≥ {LOAD_ABORT} "
                 f"({now_kst_str()}). 외부 부하로 간주, 중단.")
        if time.perf_counter() - t0 >= SETTLE_MAX_S:
            print(f"[G-IDLE C] PASS(caveat) [{label}] load1={load1:.2f} "
                  f"— {SETTLE_MAX_S}s 내 <{LOAD_HARD_MAX} 미도달, settle_caveat=true", flush=True)
            return {"gate": "C", "label": label, "load1": load1,
                    "waited_s": round(time.perf_counter() - t0, 1),
                    "samples": samples, "settle_caveat": True, "pass": True}
        time.sleep(SETTLE_INTERVAL_S)


# ── 배타 락 ─────────────────────────────────────────────────────────────────
def _pid_alive(pid):
    """os.kill(pid, 0) 로 생존 검사. ESRCH=사망 · EPERM=생존(타 사용자)."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        if e.errno == errno.ESRCH:
            return False
        if e.errno == errno.EPERM:
            return True
        raise


def _payload(script, role):
    return {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "ts_kst": now_kst_str(),
        "host": socket.gethostname(),
        "script": script,
        "role": role,
        "python": sys.executable,
        "argv": sys.argv,
    }


def _write_lock_excl(script, role):
    """O_EXCL 생성 + fsync. 성공 True / 이미 존재 False."""
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    try:
        os.write(fd, json.dumps(_payload(script, role), ensure_ascii=False, indent=2).encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def _archive_stale(raw_text, reason):
    """죽은/파손 락의 **원문을 보존**한 채 stale 로그에 append."""
    rec = {
        "ts_kst": now_kst_str(),
        "taken_over_by_pid": os.getpid(),
        "reason": reason,
        "original_raw": raw_text,          # 원문 전문 보존 (파싱 실패해도 문자열 그대로)
    }
    with open(STALE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _inspect_existing():
    """기존 락 판독 → (raw_text, parsed_or_None, reason_if_stale)."""
    try:
        with open(LOCK_PATH, encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        return None, None, None
    try:
        obj = json.loads(raw)
    except Exception as e:
        return raw, None, f"lock_json_corrupt: {e}"
    pid = obj.get("pid")
    if not isinstance(pid, int):
        return raw, obj, "lock_pid_missing"
    if _pid_alive(pid):
        return raw, obj, None                      # 생존 = stale 아님
    return raw, obj, f"lock_holder_dead(pid={pid})"


class ComputeLock:
    """배타 실행 락. 컨텍스트 매니저 또는 acquire()/release() 로 사용.

    보유자 생존 시 exit 9. `role="recorder"` 는 최대 60초(5초 간격) 재시도.
    해제는 **재판독해 pid 가 자신일 때만** 수행한다.
    """

    def __init__(self, script, role="runner"):
        self.script = script
        self.role = role
        self.acquired = False
        self.takeover = None
        self._prev_handlers = {}

    # 시그널 → SystemExit 로 변환해 finally(해제)를 보장
    def _install_signals(self):
        def handler(signum, frame):
            raise SystemExit(128 + signum)
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._prev_handlers[sig] = signal.signal(sig, handler)
            except (ValueError, OSError):
                pass                                # 비-메인 스레드 등

    def _restore_signals(self):
        for sig, prev in self._prev_handlers.items():
            try:
                signal.signal(sig, prev)
            except (ValueError, OSError):
                pass
        self._prev_handlers.clear()

    def _try_once(self):
        """1회 시도 → "ok" | "busy" | "stale-retry-failed"."""
        if _write_lock_excl(self.script, self.role):
            return "ok"
        raw, obj, reason = _inspect_existing()
        if raw is None:                             # 그사이 해제됨 → 재시도
            return "ok" if _write_lock_excl(self.script, self.role) else "busy"
        if reason is None:                          # 보유자 생존
            self._busy_holder = obj
            return "busy"
        # 죽었거나 파손 → 원문 보존 후 인수, O_EXCL 재시도 1회
        _archive_stale(raw, reason)
        try:
            os.remove(LOCK_PATH)
        except FileNotFoundError:
            pass
        if _write_lock_excl(self.script, self.role):
            self.takeover = reason
            return "ok"
        return "stale-retry-failed"

    def acquire(self):
        self._busy_holder = None
        deadline = (time.perf_counter() + RECORDER_RETRY_MAX_S
                    if self.role == "recorder" else None)
        while True:
            res = self._try_once()
            if res == "ok":
                break
            if deadline is not None and time.perf_counter() < deadline:
                h = self._busy_holder or {}
                print(f"[LOCK] 보유 중(pid={h.get('pid')} {h.get('script')}) — "
                      f"{RECORDER_RETRY_INTERVAL_S}s 후 재시도", flush=True)
                time.sleep(RECORDER_RETRY_INTERVAL_S)
                continue
            h = self._busy_holder or {}
            _die(EXIT_LOCK_BUSY,
                 f"락 획득 실패({res}) — 보유자 pid={h.get('pid')} "
                 f"script={h.get('script')} ts={h.get('ts_kst')} role={h.get('role')}. "
                 f"아무 작업도 수행하지 않고 중단({now_kst_str()}).")
        self.acquired = True
        self._install_signals()
        msg = f"[LOCK] 획득 pid={os.getpid()} script={self.script} role={self.role}"
        if self.takeover:
            msg += f" (stale 인수: {self.takeover})"
        print(msg, flush=True)
        return self

    def release(self):
        if not self.acquired:
            return
        self.acquired = False
        self._restore_signals()
        try:
            with open(LOCK_PATH, encoding="utf-8") as f:
                obj = json.loads(f.read())
        except FileNotFoundError:
            print("[LOCK] 경고 lock_file_missing — 해제 시점에 락 파일 없음", flush=True)
            return
        except Exception as e:
            print(f"[LOCK] 경고 lock_owner_changed — 판독 실패({e}), 삭제하지 않음", flush=True)
            return
        if obj.get("pid") != os.getpid():
            print(f"[LOCK] 경고 lock_owner_changed — 보유자 pid={obj.get('pid')} "
                  f"!= 자신 {os.getpid()}. 삭제하지 않음.", flush=True)
            return
        os.remove(LOCK_PATH)
        print(f"[LOCK] 해제 pid={os.getpid()}", flush=True)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


if __name__ == "__main__":                          # 자가시험 (계산·측정 없음)
    with ComputeLock(script="compute_lock.py --selftest", role="runner"):
        print("[selftest] 락 보유 중 —", LOCK_PATH)
        print("[selftest] competing =", len(competing_processes()))
        print("[selftest] load1 =", round(os.getloadavg()[0], 2))
