#!/bin/zsh
# 블록 CN — AC 전원 연결을 기다려 봉인 bootstrap 런을 detached 로 띄운다.
# 사용자 결정(2026-11-09): "어댑터 연결 후 자동 진행".
set -u
ROOT=<REPO_ROOT>
LOG=$ROOT/experiments/runs/v3_exploratory/_ckpt/run.log
mkdir -p "$(dirname "$LOG")"

until pmset -g ps | grep -q "AC Power"; do sleep 10; done
echo "AC CONNECTED $(date '+%Y-%m-%d %H:%M:%S')"
pmset -g ps | head -2

# caffeinate 로 유휴 절전만 억제(임계배터리 강제절전은 막지 못함 — AC 이므로 해당 없음)
cd "$ROOT"
# macOS 에는 setsid 가 없다 → nohup + disown 으로 셸에서 떼어낸다.
nohup caffeinate -dimsu "$ROOT/.venv/bin/python" -I \
  experiments/runs/v3_exploratory/_src/sealed.py --workers 12 \
  > "$LOG" 2>&1 < /dev/null &
PID=$!
disown $PID 2>/dev/null || true
echo "LAUNCHED pid=$PID log=$LOG"
