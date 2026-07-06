#!/usr/bin/env bash
# v2_GNN 한 줄 실행 진입점: graph→train(3종+ablation)→evaluate→stats
# 명세 docs/09_v2_gnn_spec.md §3 STEP H. 로그는 results/run.log 로.
set -euo pipefail
export PYTORCH_ENABLE_MPS_FALLBACK=1     # 일부 scatter/sparse op MPS 미지원 대비

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="python3"

SRC="v2_GNN/src"
LOG="v2_GNN/results/run.log"
mkdir -p v2_GNN/results

echo "=== v2_GNN run $(date -u +%Y-%m-%dT%H:%M:%SZ) | python=$($PY -V 2>&1) | MPS_FALLBACK=$PYTORCH_ENABLE_MPS_FALLBACK ===" | tee "$LOG"
"$PY" "$SRC/train.py"    2>&1 | tee -a "$LOG"   # STEP A~D: graph+학습 → _preds_v2.npz
"$PY" "$SRC/evaluate.py" 2>&1 | tee -a "$LOG"   # STEP E: metrics/그림/summary
"$PY" "$SRC/stats.py"    2>&1 | tee -a "$LOG"   # STEP F: Wilcoxon (RQ2)
echo "=== done $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
