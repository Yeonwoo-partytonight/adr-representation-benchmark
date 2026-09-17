#!/usr/bin/env python3
"""STEP A — SMILES → 분자 그래프(PyG Data) 변환. v2_GNN / v3 공용.

명세 docs/09_v2_gnn_spec.md §3 STEP A.
- 원자=노드(노드 특징), 결합=엣지(엣지 특징, 무방향→양방향).
- 노드: 원소 one-hot, degree, formal charge, 수소수, 혼성, 방향족/고리 여부.
- 엣지: 결합 종류(single/double/triple/aromatic), 고리 여부, conjugation.
- 컴파일 확장(torch-scatter/sparse) 불필요 — 기본 PyG 로 동작.

비고: v2 의 GCN/GIN/GAT 비교는 노드 특징 + 그래프 토폴로지로 통제한다(3종 동일 입력).
edge_attr 는 Data 에 보존하여 v3 등 후속 단계가 재사용할 수 있게 한다.
"""
import torch
from rdkit import Chem
from rdkit import RDLogger
from torch_geometric.data import Data

RDLogger.DisableLog("rdApp.*")

# 자주 등장하는 원소(소분자 약물 커버). 그 외는 'other' 버킷.
ATOM_LIST = ['C', 'N', 'O', 'S', 'F', 'Cl', 'Br', 'I', 'P', 'B', 'Si', 'Se', 'H']
HYBRID = [Chem.rdchem.HybridizationType.SP,
          Chem.rdchem.HybridizationType.SP2,
          Chem.rdchem.HybridizationType.SP3,
          Chem.rdchem.HybridizationType.SP3D,
          Chem.rdchem.HybridizationType.SP3D2]
BOND_TYPES = [Chem.rdchem.BondType.SINGLE,
              Chem.rdchem.BondType.DOUBLE,
              Chem.rdchem.BondType.TRIPLE,
              Chem.rdchem.BondType.AROMATIC]


def _onehot(x, choices):
    v = [0] * (len(choices) + 1)         # 마지막 칸 = 'other'(목록 외) 버킷
    if x in choices:
        v[choices.index(x)] = 1
    else:
        v[-1] = 1
    return v


def atom_features(a):
    f = _onehot(a.GetSymbol(), ATOM_LIST)
    f += _onehot(a.GetDegree(), [0, 1, 2, 3, 4, 5])
    f += _onehot(a.GetFormalCharge(), [-2, -1, 0, 1, 2])
    f += _onehot(a.GetTotalNumHs(), [0, 1, 2, 3, 4])
    f += _onehot(a.GetHybridization(), HYBRID)
    f += [int(a.GetIsAromatic()), int(a.IsInRing())]
    return f


def bond_features(b):
    f = _onehot(b.GetBondType(), BOND_TYPES)
    f += [int(b.GetIsConjugated()), int(b.IsInRing())]
    return f


ATOM_FDIM = len(atom_features(Chem.MolFromSmiles('C').GetAtomWithIdx(0)))
BOND_FDIM = len(bond_features(Chem.MolFromSmiles('CC').GetBondWithIdx(0)))


def smiles_to_data(smiles, y=None):
    """SMILES → PyG Data(x, edge_index, edge_attr[, y]). 실패 시 None."""
    m = Chem.MolFromSmiles(smiles)
    if m is None or m.GetNumAtoms() == 0:
        return None
    x = torch.tensor([atom_features(a) for a in m.GetAtoms()], dtype=torch.float)
    src, dst, eattr = [], [], []
    for b in m.GetBonds():
        i, j = b.GetBeginAtomIdx(), b.GetEndAtomIdx()
        bf = bond_features(b)
        src += [i, j]; dst += [j, i]            # 무방향 → 양방향 엣지
        eattr += [bf, bf]
    if not src:                                  # 원자 1개(엣지 없음)
        edge_index = torch.zeros((2, 0), dtype=torch.long)
        edge_attr = torch.zeros((0, BOND_FDIM), dtype=torch.float)
    else:
        edge_index = torch.tensor([src, dst], dtype=torch.long)
        edge_attr = torch.tensor(eattr, dtype=torch.float)
    data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
    if y is not None:
        data.y = torch.tensor(y, dtype=torch.float).view(1, -1)
    return data


if __name__ == "__main__":   # 자기검증
    d = smiles_to_data("CC(=O)Oc1ccccc1C(=O)O", y=[0, 1, 0])
    print(f"ATOM_FDIM {ATOM_FDIM} BOND_FDIM {BOND_FDIM} | nodes {tuple(d.x.shape)} "
          f"edges {tuple(d.edge_index.shape)} edge_attr {tuple(d.edge_attr.shape)} y {tuple(d.y.shape)}")
