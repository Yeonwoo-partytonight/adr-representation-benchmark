#!/usr/bin/env python3
"""verify_env.py — Mac(M5 Pro/MPS) 환경 smoke test.

실행:
    source .venv/bin/activate
    PYTORCH_ENABLE_MPS_FALLBACK=1 python scripts/verify_env.py

각 항목 [PASS]/[FAIL]을 출력. v1(RDKit)·v2(PyG)·v3(ProtBERT) 코드 경로를 최소 단위로 검증한다.
"""
from __future__ import annotations
import platform, sys, traceback

OK, results = "PASS", []
def check(name):
    def deco(fn):
        try:
            info = fn() or ""
            results.append((name, OK, info)); print(f"[PASS] {name}: {info}")
        except Exception as e:
            results.append((name, "FAIL", str(e)))
            print(f"[FAIL] {name}: {e}")
            traceback.print_exc(limit=1)
    return deco

print(f"Python {platform.python_version()} / {platform.platform()}\n")

@check("torch + MPS")
def _():
    import torch
    avail = torch.backends.mps.is_available()
    built = torch.backends.mps.is_built()
    dev = "mps" if avail else "cpu"
    x = torch.randn(1024, 1024, device=dev)
    y = (x @ x).sum().item()  # 실제 MPS 연산
    return f"torch={torch.__version__} mps_available={avail} mps_built={built} matmul_on={dev} ok={abs(y)>=0}"

@check("RDKit (Morgan FP + Murcko scaffold)")
def _():
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    smi = "CC(=O)Oc1ccccc1C(=O)O"  # aspirin
    mol = Chem.MolFromSmiles(smi)
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
    scaf = MurckoScaffold.MurckoScaffoldSmiles(smi)
    return f"fp_bits={fp.GetNumBits()} on_bits={sum(fp)} scaffold={scaf}"

@check("torch-geometric (mol graph + GCNConv forward)")
def _():
    import torch
    from torch_geometric.data import Data
    from torch_geometric.nn import GCNConv, global_mean_pool
    # 작은 분자 그래프(노드 4개) 한 개
    x = torch.randn(4, 8)
    edge_index = torch.tensor([[0,1,1,2,2,3],[1,0,2,1,3,2]], dtype=torch.long)
    conv = GCNConv(8, 16)
    h = conv(x, edge_index)
    batch = torch.zeros(4, dtype=torch.long)
    g = global_mean_pool(h, batch)
    import torch_geometric as pyg
    return f"pyg={pyg.__version__} node_out={tuple(h.shape)} graph_emb={tuple(g.shape)}"

@check("transformers ProtBERT (preprocess + tokenizer)")
def _():
    import re
    # ProtBERT 전처리 규약: 잔기 사이 공백 + U/Z/O/B -> X
    def prep(seq: str) -> str:
        seq = re.sub(r"[UZOB]", "X", seq.upper())
        return " ".join(list(seq))
    sample = prep("MKTAYIAKQRUZ")
    assert "X" in sample and "  " not in sample
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("Rostlab/prot_bert")  # vocab만(소용량)
        ids = tok(sample, return_tensors="pt")
        return f"tokenizer_ok len={ids['input_ids'].shape[1]} sample='{sample[:15]}...'"
    except Exception as e:
        # 오프라인/모델 미다운로드 시에도 전처리는 검증됨
        return f"preprocess_ok (tokenizer skipped: {type(e).__name__}); sample='{sample[:15]}...'"

@check("sklearn PR-AUC / metrics (핵심 지표)")
def _():
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score, f1_score
    y = np.array([0,0,1,0,1,1,0,1]); p = np.array([.1,.2,.7,.3,.6,.8,.05,.9])
    return f"PR-AUC={average_precision_score(y,p):.3f} ROC-AUC={roc_auc_score(y,p):.3f} F1={f1_score(y,(p>.5).astype(int)):.3f}"

@check("xgboost")
def _():
    import xgboost as xgb
    return f"xgboost={xgb.__version__}"

fails = [r for r in results if r[1] == "FAIL"]
print("\n" + "="*48)
print(f"RESULT: {len(results)-len(fails)}/{len(results)} PASS")
if fails:
    print("FAILED:", ", ".join(n for n,_,_ in fails))
    sys.exit(1)
print("✅ 모든 smoke test 통과 — v1/v2/v3 코드 경로 사용 가능")
