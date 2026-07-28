#!/usr/bin/env python3
"""W4 검증 — 최종 1,092개 분자의 분자량(MW) 통계를 재계산해 근거 파일로 저장.

원고(§3.1)의 "분자량 중앙값 348.5 Da, 95.6%가 900 Da 이하"를 재현·검증한다.
scratchpad 계산(2026-06-29)만 있고 저장 산출물이 없던 항목(evidence_table C029)을
data/processed/mw_stats.md 로 영구 기록한다.

실행(맥, 프로젝트 루트에서):
    source .venv/bin/activate   # RDKit·pandas·pyarrow 있는 환경
    python scripts/verify_mw_stats.py
"""
import sys
from pathlib import Path

import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


def load_final_cids() -> list:
    """최종 데이터셋(1,092)의 CID 인덱스를 master_X에서 얻는다."""
    mx = pd.read_parquet(PROC / "master_X.parquet")
    if mx.index.name and "cid" in str(mx.index.name).lower():
        return list(mx.index)
    for col in mx.columns:
        if str(col).lower() == "cid":
            return list(mx[col])
    return list(mx.index)  # 인덱스가 곧 CID라고 가정(이름 없을 때)


def load_smiles_map() -> dict:
    cs = pd.read_parquet(PROC / "cid_to_smiles.parquet").reset_index()
    lower = {c.lower(): c for c in cs.columns}
    cid_col = lower.get("cid") or cs.columns[0]
    # SMILES 컬럼: 이름에 'smiles'가 들어간 컬럼을 찾는다 (예: smiles_canonical)
    smi_col = next((c for c in cs.columns if "smiles" in c.lower()), None)
    if smi_col is None:
        raise ValueError(f"SMILES 컬럼을 찾지 못했습니다. 컬럼={list(cs.columns)}")
    return dict(zip(cs[cid_col], cs[smi_col]))


def main() -> int:
    cids = load_final_cids()
    smi_map = load_smiles_map()

    mws, missing = [], 0
    for cid in cids:
        smi = smi_map.get(cid)
        if not smi:
            missing += 1
            continue
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            missing += 1
            continue
        mws.append(Descriptors.MolWt(mol))

    s = pd.Series(mws)
    n = len(s)
    median = s.median()
    pct_le_900 = (s <= 900).mean() * 100
    pct_gt_900 = 100 - pct_le_900

    out = PROC / "mw_stats.md"
    out.write_text(
        "# mw_stats.md — 분자량 분포 검증 (W4 / evidence_table C029)\n\n"
        f"- 대상 분자 수: **{n}** (MW 계산 성공; SMILES 결측/실패 {missing}건 제외)\n"
        f"- 분자량 중앙값: **{median:.1f} Da**\n"
        f"- 평균: {s.mean():.1f} Da · 최소 {s.min():.1f} · 최대 {s.max():.1f}\n"
        f"- 900 Da 이하 비율: **{pct_le_900:.1f}%**\n"
        f"- 900 Da 초과(고분자량) 비율: {pct_gt_900:.1f}%\n\n"
        "> 원고 §3.1 기재값: 중앙값 348.5 Da / 95.6% ≤ 900 Da. 위 재계산과 대조할 것.\n",
        encoding="utf-8",
    )

    print(f"[OK] n={n}, median={median:.1f} Da, <=900Da={pct_le_900:.1f}% "
          f"(missing={missing}) -> {out}")
    print("원고 기재: median 348.5 Da / 95.6% <=900Da 와 일치하는지 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
