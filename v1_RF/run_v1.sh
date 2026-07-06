#!/usr/bin/env bash
# v1_RF 한 줄 실행 진입점: features → train → evaluate
# 명세 docs/08_v1_rf_spec.md §2 STEP E. 로그는 results/run.log 로.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="python3"

SRC="v1_RF/src"
LOG="v1_RF/results/run.log"
mkdir -p v1_RF/results

echo "=== v1_RF run $(date -u +%Y-%m-%dT%H:%M:%SZ) | python=$($PY -V 2>&1) ===" | tee "$LOG"
# train: featurize(STEP A) + split(STEP B) + 학습(STEP C) → results/_preds.npz
"$PY" "$SRC/train.py"     2>&1 | tee -a "$LOG"
# evaluate: STEP D → metrics_overall.csv / metrics_per_pt.csv / pr_curves.png / summary.md
"$PY" "$SRC/evaluate.py" 2>&1 | tee -a "$LOG"
echo "=== done $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
