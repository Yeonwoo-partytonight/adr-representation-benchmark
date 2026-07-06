#!/usr/bin/env python3
"""STEP B — 데이터 로드 + scaffold split 적용 (v2_GNN).

명세 docs/09_v2_gnn_spec.md §3 STEP B.
- data/processed 의 기성 산출물(master_X/Y, scaffold_split.json)만 사용. v1과 동일.
- scaffold_split.json 을 그대로 로드. 재계산·무작위 분할 금지.
- SMILES → PyG Data 리스트(라벨 y=370차원) 구성, split 별 분리.
"""
import os
import json
import yaml
import numpy as np
import pandas as pd

from graph_features import smiles_to_data

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def load_config(path=None):
    path = path or os.path.join(HERE, "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def _abspath(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def build_graphs(cfg, log=print):
    """master_X/Y + split → split별 PyG Data 리스트 + 메타.

    Returns dict: graphs{train,valid,test}, ycols, Y(np), masks, n_failed.
    """
    X = pd.read_parquet(_abspath(cfg["data"]["master_x"]))
    Y = pd.read_parquet(_abspath(cfg["data"]["master_y"]))
    assert list(X["cid"]) == list(Y["cid"]), "X/Y cid 정렬 불일치"
    ycols = [c for c in Y.columns if c != "cid"]
    Ym = Y[ycols].values.astype(np.float32)

    with open(_abspath(cfg["data"]["split"])) as f:
        split = json.load(f)
    sp = X["cid"].astype(str).map(split)
    if sp.isna().any():
        raise ValueError(f"scaffold_split 에 없는 cid {int(sp.isna().sum())}개 — split 로드 원칙 위반 가능")

    smiles = X["smiles_canonical"].tolist()
    graphs = {"train": [], "valid": [], "test": []}
    failed = []
    for i, smi in enumerate(smiles):
        d = smiles_to_data(smi, y=Ym[i].tolist())
        if d is None:
            failed.append(i)
            continue
        d.cid = int(X["cid"].iloc[i])
        graphs[sp.iloc[i]].append(d)

    if failed:
        log(f"[data] SMILES→graph 실패 {len(failed)}개 (인덱스 {failed[:20]})")
    log(f"[data] 분자 {len(X)} × PT {len(ycols)} | "
        f"train {len(graphs['train'])} / valid {len(graphs['valid'])} / test {len(graphs['test'])} "
        f"(실패 {len(failed)})")
    return {"graphs": graphs, "ycols": ycols, "Y": Ym, "n_failed": len(failed)}


if __name__ == "__main__":
    cfg = load_config()
    out = build_graphs(cfg)
    print("OK", {k: len(v) for k, v in out["graphs"].items()}, "PT", len(out["ycols"]))
