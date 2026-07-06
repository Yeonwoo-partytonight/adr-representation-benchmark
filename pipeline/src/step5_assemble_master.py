#!/usr/bin/env python3
"""STEP5 — 마스터 데이터셋 조립.  (네트워크 불필요, Mac/로컬 공용)

CID를 키로 X(SMILES)·y(라벨) join → multi-label 이진 매트릭스.
- 여러 ingredient가 동일 CID로 병합되면 라벨 OR 결합(어느 성분이든 양성이면 양성).
- 희귀 PT 필터: 양성 분자 < N(기본 10) 인 PT 컬럼 제외(목록 보존).

입력 : labels_ingredient_meddra.parquet, ingredient_to_cid.parquet, cid_to_smiles.parquet
출력 : master_X.parquet (cid, smiles_canonical)
        master_Y.parquet (cid × meddra_pt 이진)
        dataset_stats.md, dropped_rare_pts.csv
"""
import pandas as pd, numpy as np, os
OUT="data/processed"; MIN_POS=10   # D3 기본값

def main():
    lab=pd.read_parquet(f"{OUT}/labels_ingredient_meddra.parquet")
    i2c=pd.read_parquet(f"{OUT}/ingredient_to_cid.parquet")
    c2s=pd.read_parquet(f"{OUT}/cid_to_smiles.parquet")
    c2s=c2s[c2s.valid_flag].copy()

    # ingredient → cid → smiles
    m=lab.merge(i2c[i2c.mapping_status=='ok'][['ingredient_id','cid']], on='ingredient_id')
    m=m.merge(c2s[['cid','smiles_canonical']], on='cid')
    # 동일 canonical SMILES = 동일 분자 → 대표 CID(최소)로 병합
    rep=(c2s.dropna(subset=['smiles_canonical'])
            .sort_values('cid').groupby('smiles_canonical')['cid'].first().rename('rep_cid'))
    m=m.merge(rep, on='smiles_canonical')
    print(f"[조인] (성분,PT,분자) 행: {len(m):,} | distinct 분자(rep_cid): {m['rep_cid'].nunique():,}")

    # 분자(rep_cid) × PT 이진 (OR 결합)
    m['v']=1
    Y=(m.pivot_table(index='rep_cid', columns='meddra_pt', values='v',
                     aggfunc='max', fill_value=0).astype('int8'))
    # 희귀 PT 필터
    pos=Y.sum(axis=0)
    keep=pos[pos>=MIN_POS].index
    dropped=pos[pos<MIN_POS]
    Y=Y[keep]
    print(f"[희귀필터] PT {len(pos)} → 유지 {len(keep)} / 제외 {len(dropped)} (양성<{MIN_POS})")

    # 희귀필터로 양성이 전부 사라진 분자(전부-음성) 제거 → 모든 분자 라벨 ≥1 보장
    nz=Y.sum(axis=1)>0
    n_drop_mol=int((~nz).sum())
    Y=Y[nz]
    print(f"[전부음성 제거] 라벨 0 분자 {n_drop_mol}개 제거 → 분자 {len(Y)}")

    # X
    X=(m[['rep_cid','smiles_canonical']].drop_duplicates('rep_cid')
        .rename(columns={'rep_cid':'cid'}).reset_index(drop=True))
    Y=Y.reset_index().rename(columns={'rep_cid':'cid'})
    # X와 Y 분자 집합·행순서 완전 일치 (cid 오름차순 고정) — 모델이 행 인덱스로 붙여도 안전
    common=sorted(set(X['cid']) & set(Y['cid']))
    X=X[X['cid'].isin(common)].sort_values('cid').reset_index(drop=True)
    Y=Y[Y['cid'].isin(common)].sort_values('cid').reset_index(drop=True)
    assert list(X['cid'])==list(Y['cid']), "master_X/Y cid 정렬 불일치"

    X.to_parquet(f"{OUT}/master_X.parquet", index=False)
    Y.to_parquet(f"{OUT}/master_Y.parquet", index=False)
    pd.DataFrame({'meddra_pt':dropped.index,'n_pos':dropped.values}).to_csv(
        f"{OUT}/dropped_rare_pts.csv", index=False)

    # 통계
    ycols=[c for c in Y.columns if c!='cid']
    density=Y[ycols].values.mean()
    permol=Y[ycols].sum(axis=1)
    stats=f"""# dataset_stats.md (STEP5)

- 분자 수 (N): **{len(X):,}**
- 부작용 PT 수 (M): **{len(ycols):,}**  (희귀 PT {len(dropped)}개 제외, 기준 양성<{MIN_POS})
- 라벨 양성쌍 합계: **{int(Y[ycols].values.sum()):,}**
- 라벨 밀도(양성/전체셀): **{density:.4f}**
- 분자당 평균 양성 PT: **{permol.mean():.1f}** (중앙값 {int(permol.median())}, 최대 {int(permol.max())})
- PT당 평균 양성 분자: **{Y[ycols].sum(axis=0).mean():.1f}** (최소 {int(Y[ycols].sum(axis=0).min())}, 최대 {int(Y[ycols].sum(axis=0).max())})

> 클래스 불균형(낮은 라벨 밀도)은 모델 단계에서 Focal Loss/오버샘플링으로 보정(교수님 체크리스트).
"""
    open(f"{OUT}/dataset_stats.md","w").write(stats)
    print(stats)
    print("[저장] master_X.parquet / master_Y.parquet / dataset_stats.md / dropped_rare_pts.csv")

if __name__=="__main__":
    main()
