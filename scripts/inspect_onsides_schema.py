#!/usr/bin/env python3
"""inspect_onsides_schema.py — 03 명세 STEP1: OnSIDES v3.1.1 실측 스키마 출력.

Mac에서 `download_data.sh`로 OnSIDES를 받은 뒤 실행한다:
    python scripts/inspect_onsides_schema.py

하는 일:
  - data/raw/ 아래 OnSIDES 압축 해제 폴더에서 CSV 테이블들을 찾아
  - 각 테이블의 **실제 컬럼명·행수·예시값**을 출력하고
  - 성분(ingredient) 테이블이 어떤 외부 ID(RxCUI/UNII/CID/...)를 들고 있는지 탐지하고
  - product_adverse_effect의 confidence(`pred1`) threshold 적용 여부를 재확인하여
  - 결과를 docs/04_onsides_schema_actual.md 로 저장한다.

⚠️ 실제 데이터만 사용(mock 금지). 파일을 못 찾으면 멈추고 상황을 출력한다.
"""
from __future__ import annotations
import glob, os, sys, io

SEED = 42  # 재현성(이 스크립트는 무작위성 없음. 규약상 기록)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "docs", "04_onsides_schema_actual.md")

ID_HINTS = ["rxcui", "rxnorm", "unii", "cid", "pubchem", "inchikey", "inchi", "smiles", "cas"]


def find_csvs() -> list[str]:
    pats = [
        os.path.join(RAW, "**", "*.csv"),
        os.path.join(RAW, "**", "csv", "*.csv"),
    ]
    files: set[str] = set()
    for p in pats:
        files.update(glob.glob(p, recursive=True))
    return sorted(files)


def fast_rowcount(path: str) -> int:
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
    return max(0, n - 1)  # minus header


def main():
    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas 필요: source .venv/bin/activate 후 실행")

    csvs = find_csvs()
    buf = io.StringIO()
    w = buf.write
    w("# 04. OnSIDES v3.1.1 실측 스키마 (STEP1)\n\n")
    w(f"> 자동 생성: `scripts/inspect_onsides_schema.py` · 데이터 경로: `data/raw/`\n\n")

    if not csvs:
        w("⚠️ **CSV를 못 찾음.** `bash scripts/download_data.sh`로 OnSIDES를 먼저 받으세요.\n")
        w(f"검색 경로: `{RAW}/**/*.csv`\n")
        print(buf.getvalue())
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        open(OUT, "w").write(buf.getvalue())
        sys.exit("CSV 없음 — 다운로드 후 재실행")

    w(f"발견한 테이블 **{len(csvs)}개**:\n\n")

    ingredient_findings = []
    threshold_findings = []

    for path in csvs:
        rel = os.path.relpath(path, RAW)
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            head = pd.read_csv(path, nrows=5)
        except Exception as e:
            w(f"## `{name}`\n- 경로: `{rel}`\n- ⚠️ 읽기 실패: {e}\n\n")
            continue
        cols = list(head.columns)
        nrows = fast_rowcount(path)
        w(f"## `{name}`\n")
        w(f"- 경로: `{rel}`\n- 행수: **{nrows:,}**\n- 컬럼({len(cols)}): `{cols}`\n")
        # dtype 요약
        w(f"- dtypes: `{dict(head.dtypes.astype(str))}`\n")
        # 예시 1행
        if len(head):
            w(f"- 예시 행: `{head.iloc[0].to_dict()}`\n")

        # 외부 ID 힌트 탐지
        hit = [c for c in cols if any(h in c.lower() for h in ID_HINTS)]
        if hit:
            w(f"- 🔎 외부 ID 후보 컬럼: **{hit}**\n")
            if "ingredient" in name.lower():
                ingredient_findings.append((name, hit, cols))

        # threshold 확인 (pred1)
        pred_cols = [c for c in cols if c.lower() in ("pred1", "pred_1", "prediction1")]
        if pred_cols:
            pc = pred_cols[0]
            try:
                col = pd.read_csv(path, usecols=[pc])[pc]
                mn, mx = float(col.min()), float(col.max())
                ok = mn > 3.258
                w(f"- 🔬 `{pc}` 범위: [{mn:.4f}, {mx:.4f}] → "
                  f"{'OK(threshold 적용됨)' if ok else '⚠ 저신뢰 섞임(v3.1.0 결함 의심!)'}\n")
                threshold_findings.append((name, mn, ok))
            except Exception as e:
                w(f"- `{pc}` 통계 실패: {e}\n")
        w("\n")

    # 요약 — STEP3(D1) 결정용
    w("---\n\n## STEP3(D1) 매핑 경로 판단 근거\n\n")
    if ingredient_findings:
        for name, hit, cols in ingredient_findings:
            w(f"- 성분 테이블 `{name}` 의 ID 컬럼: **{hit}**\n")
        w("\n→ 위 ID로 PubChem CID 매핑 경로 결정: "
          "RxCUI 있으면 RxNorm/UniChem→CID, UNII 있으면 UNII→CID, 직접 CID면 그대로.\n")
    else:
        w("- ⚠️ 성분 테이블에서 외부 ID 후보를 못 찾음. 전체 컬럼 목록을 보고 수동 판단 필요.\n")
    if threshold_findings:
        w("\n### threshold 재확인\n")
        for name, mn, ok in threshold_findings:
            w(f"- `{name}`: pred1 min={mn:.4f} → {'적용됨' if ok else '미적용 의심'}\n")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(buf.getvalue())
    print(buf.getvalue())
    print(f"\n✅ 저장: {os.path.relpath(OUT, ROOT)}  — 이 내용을 에이전트에게 회신하세요.")


if __name__ == "__main__":
    main()
