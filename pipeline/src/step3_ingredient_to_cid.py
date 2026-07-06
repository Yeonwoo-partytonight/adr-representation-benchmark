#!/usr/bin/env python3
"""STEP3 — ingredient(RxCUI) → PubChem CID 매핑.  ★ Mac에서 실행(네트워크 필요).

매핑 경로(03 명세 D1, RxCUI→CID 우선 + 폴백):
  (a) PubChem name→CID    : rxnorm_name 으로 PUG-REST 조회 (1순위, 커버리지 높음)
  (b) PubChem xref/RxCUI  : 숫자 RxCUI에 대해 xref 조회 (2순위 폴백)
실패분은 버리되 unmapped_ingredients.csv 로 보존.

입력 : data/processed/labels_ingredient_meddra.parquet (STEP2)
출력 : data/processed/ingredient_to_cid.parquet  (ingredient_id, cid, mapping_source, mapping_status)
        data/processed/unmapped_ingredients.csv
캐시 : data/processed/_cache_cid.json (중복/재실행 방지)
"""
import pandas as pd, requests, time, json, os, sys
SEED=42
OUT="data/processed"
CACHE=f"{OUT}/_cache_cid.json"
PUG="https://pubchem.ncbi.nlm.nih.gov/rest/pug"
HEADERS={"User-Agent":"NaturalBiologics-ADR-pipeline/1.0 (academic)"}
SLEEP=0.22          # ≤5 req/s 준수
MAXRETRY=3

def get_json(url):
    for i in range(MAXRETRY):
        try:
            r=requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code==200:
                return r.json()
            if r.status_code==404:
                return None
            # 429/5xx → 지수 백오프
            time.sleep(SLEEP*(2**i)+0.5)
        except requests.RequestException:
            time.sleep(SLEEP*(2**i)+0.5)
    return None

def name_to_cid(name):
    import urllib.parse as up
    u=f"{PUG}/compound/name/{up.quote(name)}/cids/JSON"
    j=get_json(u)
    if j and j.get("IdentifierList",{}).get("CID"):
        return min(j["IdentifierList"]["CID"])   # 최소 CID(보통 parent)
    return None

def rxcui_to_cid(rxcui):
    u=f"{PUG}/compound/xref/RegistryID/{rxcui}/cids/JSON"
    j=get_json(u)
    if j and j.get("IdentifierList",{}).get("CID"):
        return min(j["IdentifierList"]["CID"])
    return None

def main():
    lab=pd.read_parquet(f"{OUT}/labels_ingredient_meddra.parquet")
    ings=(lab[['ingredient_id','ingredient_name']].drop_duplicates()
            .reset_index(drop=True))
    print(f"[입력] 매핑 대상 ingredient: {len(ings):,}")
    cache=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    rows=[]
    for k,(iid,name) in enumerate(zip(ings['ingredient_id'],ings['ingredient_name']),1):
        if iid in cache:
            rows.append(cache[iid]); continue
        cid=None; src=None
        if isinstance(name,str) and name.strip():
            cid=name_to_cid(name); src="pubchem_name" if cid else None
            time.sleep(SLEEP)
        if cid is None and str(iid).isdigit():     # RxCUI 폴백
            cid=rxcui_to_cid(iid); src="pubchem_xref_rxcui" if cid else None
            time.sleep(SLEEP)
        rec={"ingredient_id":iid,"ingredient_name":name,
             "cid":int(cid) if cid else None,
             "mapping_source":src or "",
             "mapping_status":"ok" if cid else "fail"}
        cache[iid]=rec; rows.append(rec)
        if k%50==0:
            json.dump(cache,open(CACHE,"w"))
            ok=sum(1 for r in rows if r['mapping_status']=='ok')
            print(f"  {k}/{len(ings)} 처리 (성공 {ok})")
    json.dump(cache,open(CACHE,"w"))

    df=pd.DataFrame(rows)
    ok=df[df.mapping_status=='ok'].copy()
    fail=df[df.mapping_status=='fail'].copy()
    cov=len(ok)/len(df)
    print(f"\n[결과] 매핑 성공 {len(ok):,} / 실패 {len(fail):,}  (커버리지 {cov:.1%})")
    df[['ingredient_id','cid','mapping_source','mapping_status']].to_parquet(
        f"{OUT}/ingredient_to_cid.parquet", index=False)
    fail[['ingredient_id','ingredient_name']].to_csv(
        f"{OUT}/unmapped_ingredients.csv", index=False)
    print(f"[저장] ingredient_to_cid.parquet / unmapped_ingredients.csv")
    if cov < 0.50:
        print("⚠️  커버리지 50% 미만 — 03 명세상 멈추고 보고 대상(UniChem 등 대안 검토 필요).")
        sys.exit(2)

if __name__=="__main__":
    main()
