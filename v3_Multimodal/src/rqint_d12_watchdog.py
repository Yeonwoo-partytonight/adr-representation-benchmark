"""rqint_d12_watchdog.py — 블록 AZ (docs/115b AZ-7): D12 민감도 본런 감시 래퍼(감시·자동 재개).

블록 AY 감시 래퍼(`rqint_holm8_watchdog.py`)를 복제했다. 대상 = `rqint_d12_run.py --stage run`.
래퍼 자체는 봉인 판독 0 · 계산 0. 읽는 것은 공개 heartbeat(`experiments/runs/v3_rqint_d12/heartbeat.jsonl`)의
개수·sha 필드와 자신의 이벤트 로그뿐이다.

종료 코드 처리 (docs/115 AY-5 축자 · docs/115b AZ-7 동일)
  0      완료 → 종료
  10/15  부하·전원 → 대기 후 재기동 (재시작 상한 미산입 · R2 이전 종료라 access.log 불변)
  9      락 바쁨 → 60 s 대기 후 재시도 · 연속 30회면 정지·보류
  13     무결성/무효 → 즉시 정지 · 재기동 금지
  그 밖  비정상 종료·신호·OOM → 재기동 · 산입. MAX_RESTARTS = 10 초과 시 정지·보존·보류
재기동 간 backoff ≥ 60 s. 래퍼를 수동으로 다시 띄우면 재시작 카운터를 이벤트 로그에서 복원한다.

단일 인스턴스 가드 (docs/115b AZ-7 신설)
  `restore()`·`refused_start` 판단·`watchdog_start` 이벤트보다 먼저 `watchdog.lock` 에 flock(LOCK_EX | LOCK_NB).
  실패하면 `refused_duplicate` 1줄 기록 후 종료 코드 3 (자식 기동 0 · 다른 인스턴스에 신호 0).
  락은 프로세스 수명 동안 유지한다(파일 삭제 0 — 커널이 종료 시 해제).
  한계: 래퍼가 SIGKILL 로 죽으면 flock 은 풀리지만 자식 하네스는 계속 돌 수 있다. 이때 새 래퍼가 띄운 자식은
  하네스의 `ComputeLock`(종료 9)이 막는다 — 이중 계산 0.

이벤트 로그 = 공개 `experiments/runs/v3_d12_watchdog/watchdog_events.jsonl`
(시각·사건·종료 코드·직전 heartbeat 의 variant·b_done·체크포인트 sha — 값 0).
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
HARNESS = os.path.join(_HERE, "rqint_d12_run.py")
WATCHDOG_DIR_REL = "experiments/runs/v3_d12_watchdog"
EVENTS_REL = WATCHDOG_DIR_REL + "/watchdog_events.jsonl"
CHILD_LOG_REL = WATCHDOG_DIR_REL + "/child_stdout.log"
LOCK_NAME = "watchdog.lock"
HEARTBEAT_REL = "experiments/runs/v3_rqint_d12/heartbeat.jsonl"

EXIT_OK = 0
EXIT_DUPLICATE = 3
EXIT_LOCK_BUSY = 9
EXIT_LOAD = 10
EXIT_HARD = 13
EXIT_POWER = 15
MAX_RESTARTS = 10
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
EVENT_KEYS = ("ts_kst", "event", "exit_code", "variant", "b_done", "k_done", "phase", "ckpt_sha256", "restarts",
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


class Watchdog:
    """의존성(자식 실행·전원·부하·시계·sleep)을 주입받는다 — selftest Q12 가 모의 객체로 검증."""

    def __init__(self, events_path, heartbeat_path, spawn=None, power=power_status, load1=load1_now,
                 clock=time.monotonic, sleep=time.sleep, child_log_path=None):
        self.events_path = events_path
        self.heartbeat_path = heartbeat_path
        self.spawn = spawn if spawn is not None else self._spawn_default
        self.power = power
        self.load1 = load1
        self.clock = clock
        self.sleep = sleep
        self.child_log_path = child_log_path
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

    def last_heartbeat(self):
        """공개 heartbeat 의 마지막 체크포인트 줄에서 variant·b_done·k_done·phase·ckpt sha 만."""
        if not os.path.exists(self.heartbeat_path):
            return {}
        last = {}
        with open(self.heartbeat_path, encoding="utf-8") as f:
            for ln in f:
                try:
                    o = json.loads(ln)
                except ValueError:
                    continue
                if o.get("event") == "checkpoint":
                    last = {k: o.get(k) for k in ("variant", "b_done", "k_done", "phase", "ckpt_sha256")}
        return last

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
                self.event("power_wait")
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
            while True:
                rc = self.child.poll()
                if rc is not None:
                    break
                self.sleep(CHILD_POLL_S)
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
            info = {k: hb.get(k) for k in ("variant", "b_done", "k_done", "phase", "ckpt_sha256")
                    if hb.get(k) is not None}
            if rc == EXIT_OK:
                self.event("completed", exit_code=rc, **info)
                return EXIT_OK
            if rc == EXIT_HARD:
                self.event("hard_stop", exit_code=rc, note="무결성/무효 — 재기동 금지 · 보존·보류·상신", **info)
                return EXIT_HARD
            if rc == EXIT_LOCK_BUSY:
                self.busy_consec += 1
                self.event("lock_busy", exit_code=rc, busy_consec=self.busy_consec, **info)
                if self.busy_consec >= BUSY_MAX_CONSEC:
                    self.event("busy_limit", exit_code=rc, busy_consec=self.busy_consec,
                               note="연속 30회 — PID 재사용으로 stale 판정 실패 의심 · 정지·보류")
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
                           note="재시작 상한 초과 — 정지·보존·보류 (동전 폐기·B 축소 금지)")
                return EXIT_HARD
            self.sleep(BACKOFF_S)


def main(watchdog_dir=None, heartbeat_path=None, spawn=None):
    """인자는 selftest Q12 전용(임시 디렉터리·모의 자식). 본런은 인자 없이 호출한다."""
    wdir = watchdog_dir or os.path.join(ROOT, WATCHDOG_DIR_REL)
    if not os.path.isdir(wdir):
        raise SystemExit("감시 래퍼 디렉터리 부재: " + wdir)
    wd = Watchdog(os.path.join(wdir, os.path.basename(EVENTS_REL)), heartbeat_path or os.path.join(ROOT, HEARTBEAT_REL),
                  spawn=spawn, child_log_path=os.path.join(wdir, os.path.basename(CHILD_LOG_REL)))
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
