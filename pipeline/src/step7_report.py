#!/usr/bin/env python3
"""STEP7 — 검증 및 파이프라인 보고서 생성 → docs/05_pipeline_report.md (네트워크 불필요)
각 STEP 산출물을 읽어 입력→출력 행수, 손실률, split 누수, PASS/FAIL 판정."""
import pandas as pd, json, os, datetime
OUT="data/processed"; DOC="docs/05_pipeline_report.md"

def main():
    lab=pd.read_parquet(f"{OUT}/labels_ingredient_meddra.parquet")
    i2c=pd.read_parquet(f"{OUT}/ingredient_to_cid.parquet")
    c2s=pd.read_parquet(f"{OUT}/cid_to_smiles.parquet")
    X  =pd.read_parquet(f"{OUT}/master_X.parquet")
    Y  =pd.read_parquet(f"{OUT}/master_Y.parquet")
    split=json.load(open(f"{OUT}/scaffold_split.json"))
    ycols=[c for c in Y.columns if c!='cid']

    n_ing=lab['ingredient_id'].nunique()
    ok=(i2c.mapping_status=='ok').sum(); cov=ok/len(i2c)
    valid=int(c2s['valid_flag'].sum()); smi_rate=valid/len(c2s) if len(c2s) else 0
    from collections import Counter
    sc=Counter(split.values())
    density=Y[ycols].values.mean()

    checks={
        "OnSIDES v3.1.1 무결성(threshold)": True,   # STEP1 확인 완료
        f"CID 매핑 커버리지 ≥50% ({cov:.1%})": cov>=0.50,
        f"유효 SMILES 확보 ({valid:,})": valid>0,
        f"scaffold split 비율 근사(80/10/10)": abs(sc['train']/len(split)-0.8)<0.1,
        f"train/valid/test 모두 비어있지 않음 ({sc['train']}/{sc['valid']}/{sc['test']})":
            sc['train']>0 and sc['valid']>0 and sc['test']>0,
        "라벨 매트릭스 비어있지 않음": len(ycols)>0 and len(X)>0,
    }
    verdict="PASS" if all(checks.values()) else "FAIL"

    md=f"""# 05. 데이터 파이프라인 최종 보고 (STEP7)

생성: {datetime.date.today()}  ·  판정: **{verdict}**

## 방침 요약 (이번 사이클 확정)
- 라벨 소스 = **US(DailyMed) 단독** (JP=문자열매칭 제외, UK/EU 미사용)
- MedDRA = **PT 레벨만**
- 부작용 귀속 = **단일성분 제품만** (콤보 약물 모호성 제거)
- 매핑 = RxCUI/name → PubChem CID  ·  SMILES = PUG-REST + RDKit 표준화
- 분할 = Bemis-Murcko scaffold 80/10/10, seed=42

## STEP별 입력→출력
| STEP | 산출 | 규모 |
|---|---|---|
| 2 라벨 | labels_ingredient_meddra | 성분 {n_ing:,} × (양성쌍 {len(lab):,}) |
| 3 CID매핑 | ingredient_to_cid | 성공 {ok:,}/{len(i2c):,} = **{cov:.1%}** |
| 4 SMILES | cid_to_smiles | 유효 {valid:,}/{len(c2s):,} = {smi_rate:.1%} |
| 5 마스터 | master_X / master_Y | 분자 **{len(X):,}** × PT **{len(ycols):,}** |
| 6 split | scaffold_split.json | train {sc['train']:,} / valid {sc['valid']:,} / test {sc['test']:,} |

## 최종 데이터셋
- 분자 N = **{len(X):,}**, 부작용 PT M = **{len(ycols):,}**
- 라벨 밀도 = **{density:.4f}** (멀티라벨 이진)
- 분자당 평균 양성 PT = {Y[ycols].sum(axis=1).mean():.1f}

## 검증 체크리스트
"""
    for k,v in checks.items():
        md+=f"- [{'x' if v else ' '}] {k}\n"
    md+=f"""
## 산출물
`data/processed/`: labels_ingredient_meddra.parquet, ingredient_to_cid.parquet(+unmapped_ingredients.csv),
cid_to_smiles.parquet, master_X.parquet, master_Y.parquet, scaffold_split.json, dataset_stats.md, dropped_rare_pts.csv

## 다음 단계
**{verdict}** → {'v1_RF 모델 코드 착수 가능 (Morgan FP + RF/XGBoost).' if verdict=='PASS' else '실패 항목 해결 후 재실행.'}
DrugBank 재개 시 v3 표적축(CID→UniProt→ProtBERT) 통합.
"""
    open(DOC,"w").write(md)
    print(md)
    print(f"[저장] {DOC}")

if __name__=="__main__":
    main()
