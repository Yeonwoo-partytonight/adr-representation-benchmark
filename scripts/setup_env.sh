#!/usr/bin/env bash
# setup_env.sh — Mac(M5 Pro) 환경 구축 스크립트
# 실행: cd ~/Desktop/Papers/NaturalBiologics_ADR_Prediction && bash scripts/setup_env.sh
#
# 에이전트(리눅스 샌드박스)는 MPS·Mac venv를 검증할 수 없으므로, 이 스크립트를
# Mac에서 직접 실행해 환경을 만들고 scripts/verify_env.py로 검증한다.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
echo "▶ project: $PROJECT_ROOT"

# --- Python 인터프리터 선택: 3.14 우선, 막히면 3.12 권장 ---
PY="${PYTHON:-python3}"
echo "▶ python: $($PY --version)"
echo "  (참고: torch-geometric 컴파일 확장(pyg-lib/torch-scatter)이 3.14 휠을 아직"
echo "   제공하지 않을 수 있음. plain torch_geometric로 GNN은 동작. 막히면 PYTHON=python3.12 로 재실행)"

# --- venv ---
if [ ! -d ".venv" ]; then
  "$PY" -m venv .venv
  echo "▶ created .venv"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools

# --- 핵심 설치 ---
# torch: macOS arm64 wheel은 MPS 백엔드 포함(CUDA 아님). 기본 PyPI 휠 사용.
pip install -r requirements.txt

# torch-geometric 컴파일 확장은 선택. 기본 GNN(GCN/GAT/GIN)은 불필요.
# 필요해질 때만 아래를 torch 버전에 맞춰 별도 설치(실패해도 기본 기능엔 영향 없음):
#   pip install torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-${TORCH_VER}+cpu.html

# --- MPS CPU fallback 권장 환경변수 (셸 rc에 추가하면 영구) ---
echo
echo "▶ 권장: 다음을 ~/.zshrc 에 추가 (일부 sparse/scatter op MPS 미지원 대비)"
echo "    export PYTORCH_ENABLE_MPS_FALLBACK=1"
echo
echo "✅ 설치 완료. 다음 실행:"
echo "    source .venv/bin/activate && PYTORCH_ENABLE_MPS_FALLBACK=1 python scripts/verify_env.py"
