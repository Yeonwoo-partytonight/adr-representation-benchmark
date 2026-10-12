"""unblinding_watchdog.py — 블록 BC (docs/118 BC-2) 개봉 실행(120) 감시 래퍼(감시·자동 재개).

블록 AZ 감시 래퍼(`rqint_d12_watchdog.py`)를 따른다. 대상 = `unblinding_run.py --stage run`.
래퍼 자체는 봉인 판독 0 · 계산 0. 읽는 것은 공개 heartbeat(`experiments/runs/v3_unblinding/heartbeat.jsonl`)의
event·item 필드, 계획 JSON 의 항목 개수, 자신의 이벤트 로그뿐이다.

종료 코드 처리
  0      완료 → 종료
  10/15  부하·전원 → 대기 후 재기동 (재시작 상한 미산입)
  9      락 바쁨 → 60 s 대기 후 재시도 · 연속 30회면 정지·보류
  12/13  G-gate 거부 · 무결성 실패 → 즉시 정지 · 재기동 금지 (amendment 필요)
  그 밖  비정상 종료·신호·OOM → 재기동 · 산입. MAX_RESTARTS = 5 초과 시 정지·보존·보류
재기동 간 backoff ≥ 60 s. 래퍼를 수동으로 다시 띄우면 재시작 카운터를 이벤트 로그에서 복원한다.
AC 전원 게이트: 배터리면 자식 기동 거부(power_wait) — 하네스도 같은 게이트를 다시 건다(이중).

단일 인스턴스 가드: `restore()`·이벤트보다 먼저 `watchdog.lock` 에 flock(LOCK_EX | LOCK_NB).
실패하면 `refused_duplicate` 1줄 기록 후 종료 코드 3 (자식 기동 0 · 신호 0).

진행 예측: 자식 실행 중 heartbeat 의 `item_done` 개수 변화마다 `progress` 1줄(완료 수 · 전체 수 ·
완료 항목 평균 wall 로 잔여 초 추정). 값 0.

이벤트 로그 = 공개 `experiments/runs/v3_unblind_watchdog/watchdog_events.jsonl`
(디렉터리 접두가 `v3_unblinding` 과 다르다 — G-gate 부재 판정 glob 회피).
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import datetime
import fcntl
import json
import os
import re
import signal
import subprocess
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
HARNESS = os.path.join(_HERE, "unblinding_run.py")
PLAN_REL = "v3_Multimodal/config/unblinding_plan_v1.json"
WATCHDOG_DIR_REL = "experiments/runs/v3_unblind_watchdog"
EVENTS_REL = WATCHDOG_DIR_REL + "/watchdog_events.jsonl"
CHILD_LOG_REL = WATCHDOG_DIR_REL + "/child_stdout.log"
LOCK_NAME = "watchdog.lock"
HEARTBEAT_REL = "experiments/runs/v3_unblinding/heartbeat.jsonl"

EXIT_OK = 0
EXIT_DUPLICATE = 3
EXIT_LOCK_BUSY = 9
EXIT_LOAD = 10
EXIT_GATE = 12
EXIT_HARD = 13
EXIT_POWER = 15
MAX_RESTARTS = 5
BACKOFF_S = 60
POWER_POLL_S = 60
ADAPTER_MIN_W = 90
LOAD_MAX = 1.7
LOAD_POLL_S = 10
LOAD_CONSEC = 3
LOAD_WAIT_LONG_S = 90 * 60
BUSY_RETRY_S = 60
BUSY_MAX_CONSEC = 30
STALL_S = 30 * 60
CHILD_POLL_S = 60
EVENT_KEYS = ("ts_kst", "event", "exit_code", "item", "hb_event", "n_done", "n_total", "eta_s", "restarts",
              "busy_consec", "waited_s", "launch_index", "pid", "note")
TERMINAL_REFUSE = ("hard_stop", "restart_limit", "completed")
KST = datetime.timezone(datetime.timedelta(hours=9))


def now_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def power_status():
    """pmset 판독 — AC 이고 어댑터 Wattage ≥ 90 이면 ok."""
    try:
        ps = subprocess.run(["pmset", "-g", "ps"], capture_output=True, text=True, timeout=30).stdout
        ad = subprocess.run(["pmset", "-g", "adapter"], capture_output=True, text=True, timeout=30).stdout
    except Exception:            # noqa: BLE001 — 판독 실패 = 전원 불명 → 대기
        return False
    m = re.search(r"Wattage\s*=\s*(\d+)", ad)
    return bool("AC Power" in ps and m is not None and int(m.group(1)) >= ADAPTER_MIN_W)


def load1_now():
    return os.getloadavg()[0]


def acquire_instance_lock(lock_path):
    """flock(LOCK_EX | LOCK_NB). 성공 = fd(프로세스 수명 동안 보유) · 다른 인스턴스 보유 = None."""
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def plan_item_count():
    try:
        with open(os.path.join(ROOT, PLAN_REL), "rb") as f:
            return len(json.loads(f.read())["items"])
    except Exception:            # noqa: BLE001
        return None


class Watchdog:
    """의존성(자식 실행·전원·부하·시계·sleep)을 주입받는다 — selftest U14 가 모의 객체로 검증."""

    def __init__(self, events_path, heartbeat_path, spawn=None, power=power_status, load1=load1_now,
                 clock=time.monotonic, sleep=time.sleep, child_log_path=None, n_total=None):
        self.events_path = events_path
        self.heartbeat_path = heartbeat_path
        self.spawn = spawn if spawn is not None else self._spawn_default
        self.power = power
        self.load1 = load1
        self.clock = clock
        self.sleep = sleep
        self.child_log_path = child_log_path
        self.n_total = n_total
        self.restarts = 0
        self.busy_consec = 0
        self.launch_index = 0
        self.child = None

    # ── 이벤트 로그 (값 0 — 허용 키만) ──
    def event(self, name, **kw):
        rec = {"ts_kst": now_kst(), "event": name}
        for k, v in kw.items():
            if k not in EVENT_KEYS:
                raise KeyError("허용되지 않은 이벤트 키: " + k)
            rec[k] = v
        os.makedirs(os.path.dirname(self.events_path), exist_ok=True)
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _read_events(self):
        if not os.path.exists(self.events_path):
            return []
        with open(self.events_path, encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]

    def restore(self):
        ev = self._read_events()
        self.restarts = sum(1 for e in ev if e.get("event") == "restart_counted")
        self.launch_index = sum(1 for e in ev if e.get("event") == "launch")
        terminal = [e["event"] for e in ev if e.get("event") in TERMINAL_REFUSE]
        return terminal[-1] if terminal else None

    def _hb_rows(self):
        if not os.path.exists(self.heartbeat_path):
            return []
        rows = []
        with open(self.heartbeat_path, encoding="utf-8") as f:
            for ln in f:
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    continue
        return rows

    def last_heartbeat(self):
        """공개 heartbeat 의 마지막 줄에서 event·item 만."""
        rows = self._hb_rows()
        return {k: rows[-1].get(k) for k in ("event", "item")} if rows else {}

    def progress(self):
        """item_done 개수 · 완료 항목 평균 wall 로 잔여 초 추정(ts 차이만 사용)."""
        rows = self._hb_rows()
        done = [r for r in rows if r.get("event") == "item_done"]
        start = {r.get("item"): r.get("ts_kst") for r in rows if r.get("event") == "item_start"}
        walls = []
        for r in done:
            try:
                t0 = datetime.datetime.strptime(start[r["item"]][:23], "%Y-%m-%d %H:%M:%S.%f")
                t1 = datetime.datetime.strptime(r["ts_kst"][:23], "%Y-%m-%d %H:%M:%S.%f")
                walls.append((t1 - t0).total_seconds())
            except (KeyError, ValueError, TypeError):
                pass
        n_done = len({r.get("item") for r in done})
        eta = None
        if walls and self.n_total:
            eta = round(sum(walls) / len(walls) * max(self.n_total - n_done, 0))
        return n_done, eta

    def _heartbeat_mtime(self):
        try:
            return os.path.getmtime(self.heartbeat_path)
        except OSError:
            return None

    # ── 대기 ──
    def wait_power(self):
        t0 = self.clock()
        announced = False
        while not self.power():
            if not announced:
                self.event("power_wait", note="배터리 또는 어댑터 < 90W — 자식 기동 거부")
                announced = True
            self.sleep(POWER_POLL_S)
        if announced:
            self.event("power_ok", waited_s=round(self.clock() - t0, 1))

    def wait_load(self):
        t0 = self.clock()
        t_block = t0
        consec = 0
        while consec < LOAD_CONSEC:
            if self.load1() < LOAD_MAX:
                consec += 1
            else:
                consec = 0
            if consec >= LOAD_CONSEC:
                break
            if self.clock() - t_block > LOAD_WAIT_LONG_S:
                self.event("load_wait_long", waited_s=round(self.clock() - t0, 1))
                t_block = self.clock()
            self.sleep(LOAD_POLL_S)
        return round(self.clock() - t0, 1)

    # ── 자식 실행 ──
    def _spawn_default(self):
        cmd = [sys.executable, "-B", HARNESS, "--stage", "run"]
        log = open(self.child_log_path, "ab") if self.child_log_path else subprocess.DEVNULL
        try:
            self.child = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            self.event("child_started", pid=self.child.pid, launch_index=self.launch_index)
            t_start = self.clock()
            stalled = False
            last_done = -1
            while True:
                rc = self.child.poll()
                if rc is not None:
                    break
                self.sleep(CHILD_POLL_S)
                n_done, eta = self.progress()
                if n_done != last_done:
                    self.event("progress", n_done=n_done, n_total=self.n_total, eta_s=eta)
                    last_done = n_done
                mt = self._heartbeat_mtime()
                idle = (time.time() - mt) if mt is not None else (self.clock() - t_start)
                if idle > STALL_S and self.clock() - t_start > STALL_S:
                    if not stalled:
                        self.event("stall_suspect", pid=self.child.pid, note="heartbeat 30분 이상 미갱신(기록만)")
                        stalled = True
                else:
                    stalled = False
            return rc
        finally:
            self.child = None
            if log is not subprocess.DEVNULL:
                log.close()

    def terminate_child(self):
        if self.child is not None and self.child.poll() is None:
            self.child.send_signal(signal.SIGTERM)

    # ── 주 루프 ──
    def run(self):
        prior = self.restore()
        if prior in TERMINAL_REFUSE:
            self.event("refused_start", note="이전 종결 사건 존재: " + prior)
            return EXIT_OK if prior == "completed" else EXIT_HARD
        self.event("watchdog_start", restarts=self.restarts, launch_index=self.launch_index)
        while True:
            self.wait_power()
            waited = self.wait_load()
            self.launch_index += 1
            self.event("launch", launch_index=self.launch_index, waited_s=waited)
            rc = self.spawn()
            hb = self.last_heartbeat()
            info = {"hb_event": hb.get("event"), "item": hb.get("item")} if hb else {}
            if rc == EXIT_OK:
                self.event("completed", exit_code=rc, **info)
                return EXIT_OK
            if rc in (EXIT_HARD, EXIT_GATE):
                self.event("hard_stop", exit_code=rc, note="무결성 실패/G-gate 거부 — 재기동 금지 · 보존·보류·상신",
                           **info)
                return EXIT_HARD
            if rc == EXIT_LOCK_BUSY:
                self.busy_consec += 1
                self.event("lock_busy", exit_code=rc, busy_consec=self.busy_consec, **info)
                if self.busy_consec >= BUSY_MAX_CONSEC:
                    self.event("busy_limit", exit_code=rc, busy_consec=self.busy_consec, note="연속 30회 — 정지·보류")
                    return EXIT_LOCK_BUSY
                self.sleep(BUSY_RETRY_S)
                continue
            self.busy_consec = 0
            if rc in (EXIT_LOAD, EXIT_POWER):
                self.event("wait_load" if rc == EXIT_LOAD else "wait_power", exit_code=rc, **info)
                self.sleep(BACKOFF_S)
                continue
            self.restarts += 1
            self.event("restart_counted", exit_code=rc, restarts=self.restarts, **info)
            if self.restarts > MAX_RESTARTS:
                self.event("restart_limit", exit_code=rc, restarts=self.restarts,
                           note="재시작 상한 초과 — 정지·보존·보류")
                return EXIT_HARD
            self.sleep(BACKOFF_S)


def main(watchdog_dir=None, heartbeat_path=None, spawn=None):
    """인자는 selftest U14 전용(임시 디렉터리·모의 자식). 본런은 인자 없이 호출한다."""
    wdir = watchdog_dir or os.path.join(ROOT, WATCHDOG_DIR_REL)
    if not os.path.isdir(wdir):
        raise SystemExit("감시 래퍼 디렉터리 부재: " + wdir)
    wd = Watchdog(os.path.join(wdir, os.path.basename(EVENTS_REL)), heartbeat_path or os.path.join(ROOT, HEARTBEAT_REL),
                  spawn=spawn, child_log_path=os.path.join(wdir, os.path.basename(CHILD_LOG_REL)),
                  n_total=plan_item_count())
    lock_fd = acquire_instance_lock(os.path.join(wdir, LOCK_NAME))      # restore()·이벤트보다 먼저
    if lock_fd is None:
        wd.event("refused_duplicate", note="다른 감시 래퍼 인스턴스가 실행 중 — 자식 기동 0 · 신호 0")
        return EXIT_DUPLICATE

    def _on_term(signum, _frame):
        wd.terminate_child()
        wd.event("watchdog_signal", note="signal %d — 자식에 SIGTERM 전달" % signum)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    return wd.run()


if __name__ == "__main__":
    raise SystemExit(main())
