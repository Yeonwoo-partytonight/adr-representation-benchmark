#!/usr/bin/env python3
"""GraphDTA(Nguyen et al., Bioinformatics 2021) 약물 그래프 브랜치 — v2 SOTA 베이스라인 + v3 약물 축.

교수님 지정 SOTA(GraphDTA)의 *약물 그래프 인코더*를 우리 PyG 파이프라인에 정합 구현한다.
원 구현(github thinng/GraphDTA) 2종 아키텍처를 재현:
  - GINConvNet  : 5×GINConv(dim=32) + BatchNorm → global_add_pool → FC(embed)  [Davis 최적]
  - GAT_GCN     : GATConv(heads=10) → GCNConv → cat(max,mean)pool → FC1500 → FC(embed)  [KIBA 최적]

[범위] 원본은 약물그래프+단백질서열 dual-input(친화도 회귀)이나, 본 작업은 단백질 축을
DrugBank 중단으로 제외(v3 유보)하고 **약물 그래프 브랜치 + 멀티라벨 분류 head**(370 PT,
회귀→이진분류로 head만 교체)만 사용한다. 단백질 축은 ProteinEncoder 인터페이스로 stub 배선만.

[통제] 입력 그래프 피처는 v2 graph_features.py(동일 atom/bond feature)를 그대로 사용 →
v2 GIN과의 차이가 '아키텍처'로만 한정된다.

입력: PyG Data(x, edge_index, batch[, protein]). 출력: 370 logits(sigmoid는 손실에서).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import (GINConv, GATConv, GCNConv,
                                global_add_pool, global_mean_pool, global_max_pool)


class GINDrugEncoder(nn.Module):
    """GraphDTA GINConvNet 약물 브랜치(원본 dim=32, 5층). → embed_dim 약물 임베딩."""
    def __init__(self, in_dim, dim=32, n_layers=5, embed_dim=128, dropout=0.2):
        super().__init__()
        self.dropout = dropout
        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()
        d = in_dim
        for _ in range(n_layers):
            mlp = nn.Sequential(nn.Linear(d, dim), nn.ReLU(), nn.Linear(dim, dim))
            self.convs.append(GINConv(mlp))
            self.bns.append(nn.BatchNorm1d(dim))
            d = dim
        self.fc = nn.Linear(dim, embed_dim)
        self.embed_dim = embed_dim

    def forward(self, x, edge_index, batch):
        for conv, bn in zip(self.convs, self.bns):
            x = F.relu(conv(x, edge_index))     # 원본: relu(conv) 후 bn
            x = bn(x)
        x = global_add_pool(x, batch)           # GINConvNet = add pool
        x = F.relu(self.fc(x))
        x = F.dropout(x, p=self.dropout, training=self.training)
        return x                                # [batch, embed_dim]


class GATGCNDrugEncoder(nn.Module):
    """GraphDTA GAT_GCN 약물 브랜치(원본 heads=10, fc 1500). → embed_dim 약물 임베딩."""
    def __init__(self, in_dim, heads=10, embed_dim=128, dropout=0.2):
        super().__init__()
        self.dropout = dropout
        self.conv1 = GATConv(in_dim, in_dim, heads=heads)     # out = in_dim*heads
        self.conv2 = GCNConv(in_dim * heads, in_dim * heads)
        self.fc_g1 = nn.Linear(in_dim * heads * 2, 1500)      # cat(max,mean) → *2
        self.fc_g2 = nn.Linear(1500, embed_dim)
        self.embed_dim = embed_dim

    def forward(self, x, edge_index, batch):
        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        x = torch.cat([global_max_pool(x, batch), global_mean_pool(x, batch)], dim=1)
        x = F.relu(self.fc_g1(x))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.fc_g2(x)
        x = F.dropout(x, p=self.dropout, training=self.training)
        return x                                # [batch, embed_dim]


class ProteinEncoderStub(nn.Module):
    """v3 단백질 축 인터페이스(현재 비활성 — DrugBank 중단으로 stub).

    v3 재개 시: GraphDTA 원본의 1D-CNN(서열) 또는 ProtBERT 임베딩으로 교체하고,
    forward(data)가 [batch, embed_dim] 단백질 임베딩을 반환하도록 구현한다.
    data.protein(또는 data.target_seq) 필드를 입력으로 받는다.
    """
    def __init__(self, embed_dim=128):
        super().__init__()
        self.embed_dim = embed_dim

    def forward(self, data):
        raise NotImplementedError(
            "단백질 축은 v3에서 활성화 예정(DrugBank 표적 서열 통합 후). "
            "현재 약물-only 베이스라인에서는 protein_encoder=None 으로 사용한다.")


class GraphDTAClassifier(nn.Module):
    """GraphDTA 약물 브랜치 + (옵션)단백질 축 + 멀티라벨 분류 head.

    protein_encoder=None → 약물-only(본 v2 SOTA 베이스라인, 구조-only ADR 멀티라벨).
    protein_encoder 지정 → v3 멀티모달(약물 embed ⊕ 단백질 embed → head). 인터페이스만 배선.
    """
    def __init__(self, in_dim, n_out, arch="gin", embed_dim=128, dropout=0.2,
                 protein_encoder=None):
        super().__init__()
        if arch == "gin":
            self.drug = GINDrugEncoder(in_dim, embed_dim=embed_dim, dropout=dropout)
        elif arch == "gatgcn":
            self.drug = GATGCNDrugEncoder(in_dim, embed_dim=embed_dim, dropout=dropout)
        else:
            raise ValueError(f"알 수 없는 arch: {arch} (gin|gatgcn)")
        self.protein = protein_encoder
        head_in = embed_dim + (protein_encoder.embed_dim if protein_encoder is not None else 0)
        # global pooling → MLP head → 370 logits (v2 head 스타일과 동일 통제)
        self.head = nn.Sequential(
            nn.Linear(head_in, embed_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(embed_dim, n_out),
        )

    def forward(self, data):
        d = self.drug(data.x, data.edge_index, data.batch)
        if self.protein is not None:                 # v3 경로(현재 비활성)
            p = self.protein(data)
            d = torch.cat([d, p], dim=1)
        return self.head(d)                           # [batch, n_out] logits


def build_graphdta(arch, in_dim, n_out, dropout=0.2, protein_encoder=None):
    return GraphDTAClassifier(in_dim, n_out, arch=arch, dropout=dropout,
                              protein_encoder=protein_encoder)
