#!/usr/bin/env python3
"""STEP4 — CID → Canonical SMILES 수집 + RDKit 검증/표준화.  ★ Mac에서 실행(네트워크 필요).

- PUG-REST property 조회. ⚠️ PubChem 2025 명칭 변경 대응:
  'CanonicalSMILES'(구) → 'SMILES'/'ConnectivitySMILES'(신) 폴백 처리.
- RDKit: 파싱/sanitize 검증 → 실패 제거, 염·용매 제거(largest fragment), canonical 중복 병합.
- rate limit ≤5req/s, 지수 백오프, 로컬 캐시.

입력 : data/processed/ingredient_to_cid.parquet (STEP3)
출력 : data/processed/cid_to_smiles.parquet (cid, smiles_canonical, valid_flag)
캐시 : data/processed/_cache_smiles.json
"""
import pandas as pd, requests, time, json, os
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

OUT="data/processed"; CACHE=f"{OUT}/_cache_smiles.json"
PUG="https://pubchem.ncbi.nlm.nih.gov/rest/pug"
HEADERS={"User-Agent":"NaturalBiologics-ADR-pipeline/1.0 (academic)"}
SLEEP=0.22; MAXRETRY=3
PROPS=["SMILES","CanonicalSMILES","ConnectivitySMILES","IsomericSMILES"]  # 폴백 순서

def get_json(url):
    for i in range(MAXRETRY):
        try:
            r=requests.get(url,headers=HEADERS,timeout=30)
            if r.status_code==200: return r.json()
            if r.status_code==404: return None
            time.sleep(SLEEP*(2**i)+0.5)
        except requests.RequestException:
            time.sleep(SLEEP*(2**i)+0.5)
    return None

def fetch_smiles(cid):
    for p in PROPS:
        j=get_json(f"{PUG}/compound/cid/{cid}/property/{p}/JSON")
        if j:
            props=j.get("PropertyTable",{}).get("Properties",[{}])[0]
            for key in (p,"SMILES","CanonicalSMILES","ConnectivitySMILES"):
                if props.get(key): return props[key]
        time.sleep(SLEEP)
    return None

_lfc=rdMolStandardize.LargestFragmentChooser()
def standardize(smi):
    """RDKit 검증 + largest fragment(염/용매 제거) + canonical."""
    m=Chem.MolFromSmiles(smi)
    if m is None: return None
    try:
        m=_lfc.choose(m)
        Chem.SanitizeMol(m)
        return Chem.MolToSmiles(m)   # canonical
    except Exception:
        return None

def main():
    i2c=pd.read_parquet(f"{OUT}/ingredient_to_cid.parquet")
    cids=sorted({int(c) for c in i2c['cid'].dropna().unique()})
    print(f"[입력] 조회 대상 CID: {len(cids):,}")
    cache=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    rows=[]
    for k,cid in enumerate(cids,1):
        key=str(cid)
        if key in cache: rows.append(cache[key]); continue
        raw=fetch_smiles(cid)
        can=standardize(raw) if raw else None
        rec={"cid":cid,"smiles_raw":raw,"smiles_canonical":can,
             "valid_flag":bool(can)}
        cache[key]=rec; rows.append(rec)
        if k%50==0:
            json.dump(cache,open(CACHE,"w"))
            ok=sum(1 for r in rows if r['valid_flag'])
            print(f"  {k}/{len(cids)} (유효 {ok})")
    json.dump(cache,open(CACHE,"w"))

    df=pd.DataFrame(rows)
    valid=df[df.valid_flag]
    ndup=valid['smiles_canonical'].duplicated().sum()
    print(f"\n[결과] 유효 SMILES {len(valid):,} / 무효 {len(df)-len(valid):,}")
    print(f"  중복 canonical(서로 다른 CID가 동일 분자): {ndup:,}")
    df[['cid','smiles_canonical','valid_flag']].to_parquet(
        f"{OUT}/cid_to_smiles.parquet", index=False)
    print("[저장] cid_to_smiles.parquet")

if __name__=="__main__":
    main()
