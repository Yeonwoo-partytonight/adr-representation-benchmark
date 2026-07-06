#!/usr/bin/env python3
"""STEP C — GNN 모델 (v2_GNN).

명세 docs/09_v2_gnn_spec.md §3 STEP C.
- 공통 골격: [GNN×n_layers] → global pooling(mean|add) → MLP head → 370 logits.
- 3종 비교: GCN / GIN / GAT (동일 깊이·hidden 통제). 주 후보 GIN.
- 출력층: 370 PT 멀티라벨. logits 반환(손실에서 sigmoid 처리).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import (GCNConv, GINConv, GATConv,
                                global_mean_pool, global_add_pool, JumpingKnowledge)


def _make_conv(conv_type, in_dim, out_dim, heads):
    if conv_type == "gcn":
        return GCNConv(in_dim, out_dim)
    if conv_type == "gin":
        mlp = nn.Sequential(nn.Linear(in_dim, out_dim), nn.ReLU(), nn.Linear(out_dim, out_dim))
        return GINConv(mlp)
    if conv_type == "gat":
        assert out_dim % heads == 0, f"hidden({out_dim}) % heads({heads}) != 0"
        return GATConv(in_dim, out_dim // heads, heads=heads, concat=True)
    raise ValueError(f"알 수 없는 conv: {conv_type}")


class GNN(nn.Module):
    """공통 골격 + 옵션(jk, residual). 1a 는 jk=None/residual=False(현행 유지),
    1b 에서 jk='cat'/residual=True 로 over-smoothing 완화."""
    def __init__(self, in_dim, n_out, conv_type="gin", hidden=128, n_layers=3,
                 dropout=0.2, pool="mean", gat_heads=4, jk=None, residual=False):
        super().__init__()
        self.conv_type = conv_type
        self.dropout = dropout
        self.residual = residual
        self.jk_mode = jk
        self.pool_fn = global_mean_pool if pool == "mean" else global_add_pool
        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()
        d = in_dim
        for _ in range(n_layers):
            self.convs.append(_make_conv(conv_type, d, hidden, gat_heads))
            self.bns.append(nn.BatchNorm1d(hidden))
            d = hidden
        if jk == "cat":
            self.jk = JumpingKnowledge("cat")
            head_in = hidden * n_layers
        else:
            self.jk = None
            head_in = hidden
        self.head = nn.Sequential(
            nn.Linear(head_in, hidden), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden, n_out),
        )

    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch
        xs = []
        for conv, bn in zip(self.convs, self.bns):
            h = conv(x, edge_index)
            h = bn(h)
            h = F.relu(h)
            h = F.dropout(h, p=self.dropout, training=self.training)
            if self.residual and h.shape == x.shape:
                h = h + x                       # residual (차원 일치 층에서만)
            x = h
            xs.append(x)
        x = self.jk(xs) if self.jk is not None else x
        g = self.pool_fn(x, batch)
        return self.head(g)            # [batch, n_out] logits


def build_model(cfg, in_dim, n_out, conv_type=None, pool=None, overrides=None):
    """overrides: dict 로 dropout/n_layers/jk/residual 등 덮어쓰기(개선 사이클용)."""
    m = dict(cfg["model"])
    o = overrides or {}
    return GNN(
        in_dim=in_dim, n_out=n_out,
        conv_type=conv_type or m["convs"][0],
        hidden=m["hidden"], n_layers=o.get("n_layers", m["n_layers"]),
        dropout=o.get("dropout", m["dropout"]), pool=pool or m["pool"],
        gat_heads=m["gat_heads"], jk=o.get("jk"), residual=o.get("residual", False),
    )
