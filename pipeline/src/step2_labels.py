#!/usr/bin/env python3
"""STEP2 — 라벨(y) 테이블 구성. OnSIDES v3.1.1 → (ingredient_id, meddra_pt, confidence).
방침(확정): 라벨=US(DailyMed, 전부 PMB) / MedDRA=PT행만 / 부작용 귀속=단일성분 제품만(콤보 제외).
출력: data/processed/labels_ingredient_meddra.parquet
"""
import pandas as pd, os
SEED=42
BASE="data/raw/onsides-v3.1.1/csv"; OUT="data/processed"
os.makedirs(OUT, exist_ok=True)
log=[]
def L(m): print(m); log.append(m)

pl =pd.read_csv(f"{BASE}/product_label.csv", dtype=str)[['label_id','source']]
p2r=pd.read_csv(f"{BASE}/product_to_rxnorm.csv", dtype=str)
i2p=pd.read_csv(f"{BASE}/vocab_rxnorm_ingredient_to_product.csv", dtype=str)
vm =pd.read_csv(f"{BASE}/vocab_meddra_adverse_effect.csv", dtype=str)
vi =pd.read_csv(f"{BASE}/vocab_rxnorm_ingredient.csv", dtype=str)
pae=pd.read_csv(f"{BASE}/product_adverse_effect.csv",
    usecols=['product_label_id','effect_meddra_id','match_method','pred1'],
    dtype={'product_label_id':str,'effect_meddra_id':str,'match_method':str})

L(f"[입력] product_adverse_effect 행: {len(pae):,}")

# 1) PT 집합
pt_ids=set(vm[vm['meddra_term_type']=='PT']['meddra_id'])
pt_name=vm.set_index('meddra_id')['meddra_name']
L(f"[PT] vocab PT 수: {len(pt_ids):,}")

# 2) 단일성분 제품
ning=i2p.groupby('product_id')['ingredient_id'].nunique()
single_prod=set(ning[ning==1].index)
L(f"[콤보필터] 단일성분 product: {len(single_prod):,} / 전체 {len(ning):,}")

# 3) US 라벨
us_labels=set(pl[pl['source']=='US']['label_id'])
L(f"[소스] US 라벨: {len(us_labels):,}")

# 4) 라벨 게이트: US & PT & PMB
m=pae[pae['product_label_id'].isin(us_labels)]
L(f"  US 필터 후 부작용행: {len(m):,}")
m=m[m['match_method']=='PMB']
L(f"  PMB 필터 후: {len(m):,}")
m=m[m['effect_meddra_id'].isin(pt_ids)]
L(f"  PT 필터 후: {len(m):,}")

# 5) label -> 단일성분 product -> ingredient
lab2prod=p2r[p2r['rxnorm_product_id'].isin(single_prod)]
prod2ing=i2p[i2p['product_id'].isin(single_prod)]
bridge=lab2prod.merge(prod2ing, left_on='rxnorm_product_id', right_on='product_id')[['label_id','ingredient_id']].drop_duplicates()
L(f"[브리지] (label,ingredient) 쌍: {len(bridge):,}")

df=m.merge(bridge, left_on='product_label_id', right_on='label_id')
L(f"  성분 귀속 후 부작용행: {len(df):,}")

# 6) (ingredient, PT) 집계 — confidence=max pred1
lab=(df.groupby(['ingredient_id','effect_meddra_id'])['pred1'].max()
       .reset_index().rename(columns={'effect_meddra_id':'meddra_pt','pred1':'confidence'}))
lab['meddra_pt_name']=lab['meddra_pt'].map(pt_name)
lab['ingredient_name']=lab['ingredient_id'].map(vi.set_index('rxnorm_id')['rxnorm_name'])

L(f"\n[산출] (ingredient,PT) 양성쌍: {len(lab):,}")
L(f"  distinct ingredient: {lab['ingredient_id'].nunique():,}")
L(f"  distinct PT: {lab['meddra_pt'].nunique():,}")
L(f"  성분당 평균 PT 수: {len(lab)/lab['ingredient_id'].nunique():.1f}")

lab.to_parquet(f"{OUT}/labels_ingredient_meddra.parquet", index=False)
L(f"[저장] {OUT}/labels_ingredient_meddra.parquet")
open(f"{OUT}/_step2_log.txt","w").write("\n".join(log))
