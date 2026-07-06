#!/usr/bin/env bash
# download_data.sh — 공개 데이터 다운로드 (Mac에서 실행; 샌드박스는 release-assets 호스트가 막혀 불가)
# 실행: cd ~/Desktop/Papers/NaturalBiologics_ADR_Prediction && bash scripts/download_data.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"
mkdir -p "$RAW"; cd "$RAW"

# ============ OnSIDES v3.1.1 (필수, 메인 부작용 데이터) ============
ONS_VER="v3.1.1"
ONS_URL="https://github.com/tatonetti-lab/onsides/releases/download/${ONS_VER}/onsides-${ONS_VER}.zip"
echo "▶ OnSIDES ${ONS_VER} 다운로드"
curl -L -o "onsides-${ONS_VER}.zip" "$ONS_URL"
unzip -o "onsides-${ONS_VER}.zip" -d "onsides-${ONS_VER}"
echo "  압축 해제 완료 → $RAW/onsides-${ONS_VER}/"

# --- 버전·threshold 검증 (v3.1.0 결함 회피 확인) ---
echo "▶ OnSIDES 무결성 검증"
python3 - "$RAW/onsides-${ONS_VER}" <<'PY'
import sys, glob, os
import pandas as pd
base = sys.argv[1]
# product_adverse_effect 테이블 찾기
cands = glob.glob(os.path.join(base, "**", "*adverse_effect*.csv"), recursive=True)
if not cands:
    print("  [WARN] product_adverse_effect CSV를 못 찾음. zip 레이아웃 확인 필요:")
    for p in glob.glob(os.path.join(base, "**", "*.csv"), recursive=True)[:20]:
        print("   -", os.path.relpath(p, base))
    sys.exit(0)
f = cands[0]
# 메모리 안전: 컬럼만 먼저
head = pd.read_csv(f, nrows=5)
print("  파일:", os.path.relpath(f, base))
print("  컬럼:", list(head.columns))
n = sum(1 for _ in open(f, "rb")) - 1
print(f"  행 수: {n:,}")
if "pred1" in head.columns:
    # threshold(pred1 > 3.258) 적용 여부: 전부 통과해야 정상(v3.1.1)
    mn = pd.read_csv(f, usecols=["pred1"])["pred1"].min()
    print(f"  pred1 최소값: {mn:.4f}  → {'OK(threshold 적용됨)' if mn > 3.258 else '⚠ 저신뢰 섞임(v3.1.0 결함 의심!)'}")
# 기대치: 약 6,928,666 행
print("  기대(v3.1.1): adverse effects≈6,928,666 / products=41,119 / ingredients=1,866")
PY

# ============ SIDER 4.1 (⏸ 이번 사이클 미사용 — 비교 트랙 자리만) ============
# 03 명세 §0: 단일 라벨 = OnSIDES. SIDER는 라벨로 안 씀. 받고 싶으면 DOWNLOAD_SIDER=1 로.
if [ "${DOWNLOAD_SIDER:-0}" = "1" ]; then
  echo "▶ (옵션) SIDER 4.1 다운로드 — 비교 트랙용"
  mkdir -p "$RAW/sider4.1"; cd "$RAW/sider4.1"
  SIDER_BASE="http://sideeffects.embl.de/media/download"
  for f in meddra_all_se.tsv.gz drug_names.tsv drug_atc.tsv; do
    echo "  - $f"; curl -fL -O "${SIDER_BASE}/${f}" || echo "    [WARN] $f 실패 → 미러 dhimmel/SIDER4"
  done
else
  echo "▶ SIDER: 이번 사이클 미사용(03 명세). 받으려면 DOWNLOAD_SIDER=1 bash scripts/download_data.sh"
fi

echo
echo "▶ 다음(03 명세 STEP1): OnSIDES 실측 스키마 추출"
echo "    python scripts/inspect_onsides_schema.py   # → docs/04_onsides_schema_actual.md"
echo "    (생성된 04 문서를 에이전트에게 회신 → STEP2~7 파이프라인 착수)"
echo
echo "✅ 다운로드 단계 종료."
echo "   - 단일 라벨(y): OnSIDES v3.1.1."
echo "   - 구조(X): PubChem (성분→CID→SMILES, STEP3~4에서 수집)."
echo "   - DrugBank: 재개 시 표적 단백질 서열·DDI 통합(v3). 매일 자동 확인 중."
