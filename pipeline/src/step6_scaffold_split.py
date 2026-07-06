#!/usr/bin/env python3
"""STEP6 — Scaffold Split (Bemis-Murcko).  ★ 교수님 체크리스트 1순위 (네트워크 불필요)

- RDKit Bemis-Murcko scaffold 기준 그룹 분할. 같은 scaffold가 train/test에 동시 포함 금지(누수 차단).
- train/valid/test = 80/10/10, seed=42 고정.
- v1·v2·v3 가 글자 그대로 공유 → 모델 단계에서 재계산 금지, 이 파일 로드.

입력 : master_X.parquet
출력 : scaffold_split.json  {cid: "train"|"valid"|"test"}
"""
import pandas as pd, json, random
from collections import defaultdict
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

OUT="data/processed"; SEED=42
FRAC=(0.8,0.1,0.1)

def scaffold(smi):
    m=Chem.MolFromSmiles(smi)
    if m is None: return ""
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False)
    except Exception:
        return ""

def main():
    X=pd.read_parquet(f"{OUT}/master_X.parquet")
    n=len(X); print(f"[입력] 분자 {n:,}")
    groups=defaultdict(list)
    for cid,smi in zip(X['cid'],X['smiles_canonical']):
        groups[scaffold(smi)].append(cid)
    # 큰 scaffold 그룹부터 train에 채워 deterministic + 누수 차단
    gl=sorted(groups.values(), key=lambda g:(-len(g), str(g[0])))
    random.Random(SEED).shuffle(gl)            # 동률 그룹 재현가능 셔플
    gl=sorted(gl, key=lambda g:-len(g))        # 큰 scaffold 그룹 우선(DeepChem 방식)
    tr_cut=FRAC[0]*n                            # train 누적 상한
    va_cut=(FRAC[0]+FRAC[1])*n                  # train+valid 누적 상한, 나머지=test
    split={}; c={"train":0,"valid":0,"test":0}
    for g in gl:
        if c["train"]+len(g)<=tr_cut:           tgt="train"
        elif c["train"]+c["valid"]+len(g)<=va_cut: tgt="valid"
        else:                                   tgt="test"
        for cid in g: split[str(cid)]=tgt
        c[tgt]+=len(g)
    json.dump(split, open(f"{OUT}/scaffold_split.json","w"), indent=0)

    # 누수 검증
    sc_by_split=defaultdict(set)
    cid2sc={}
    for sc,g in groups.items():
        for cid in g: cid2sc[str(cid)]=sc
    for cid,sp in split.items(): sc_by_split[sp].add(cid2sc[cid])
    leak=(sc_by_split["train"]&sc_by_split["test"])|(sc_by_split["train"]&sc_by_split["valid"])|(sc_by_split["valid"]&sc_by_split["test"])
    leak.discard("")  # 빈 scaffold(파싱불가)는 평가에서 제외 고려
    print(f"[분할] train {c['train']:,} / valid {c['valid']:,} / test {c['test']:,}")
    print(f"[누수검증] 교차 scaffold 수(빈값 제외): {len(leak)}  → {'PASS' if len(leak)==0 else 'FAIL'}")
    print(f"[scaffold] 고유 scaffold 그룹: {len(groups):,}")
    print("[저장] scaffold_split.json")

if __name__=="__main__":
    main()
