#!/usr/bin/env bash
# run_pipeline.sh — 데이터 파이프라인 STEP2~7 일괄 실행 (★ Mac에서 실행, STEP3·4는 PubChem 네트워크 필요)
# 사용: cd adr-representation-benchmark && bash pipeline/run_pipeline.sh
#  - venv 활성화 후 실행 권장(RDKit/requests/pyarrow 필요)
#  - 중간 실패해도 캐시(_cache_*.json)로 재실행 시 이어서 진행
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."          # 프로젝트 루트
export SEED=42
P=pipeline/src

echo "▶ STEP2  라벨 테이블 (로컬)";      python3 $P/step2_labels.py
echo "▶ STEP3  ingredient→CID (네트워크)"; python3 $P/step3_ingredient_to_cid.py
echo "▶ STEP4  CID→SMILES (네트워크)";    python3 $P/step4_cid_to_smiles.py
echo "▶ STEP5  마스터 조립 (로컬)";       python3 $P/step5_assemble_master.py
echo "▶ STEP6  scaffold split (로컬)";    python3 $P/step6_scaffold_split.py
echo "▶ STEP7  보고서 → docs/05 (로컬)";  python3 $P/step7_report.py
echo "✅ 파이프라인 완료. docs/05_pipeline_report.md 의 PASS/FAIL 확인 후 v1_RF 착수."
