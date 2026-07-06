#!/usr/bin/env python3
"""STEP B — 데이터 로드 + scaffold split 적용 (v1_RF).

명세 docs/08_v1_rf_spec.md §2 STEP B.
- data/processed 의 기성 산출물(master_X/Y, scaffold_split.json)만 사용.
- scaffold_split.json 을 **그대로 로드**해 train/valid/test 를 가른다. 재계산·무작위 분할 금지.
- master_X 와 master_Y 는 cid 기준 동일 순서로 정렬되어 있음을 assert 로 검증.
"""
import os
import json
import yaml
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def load_config(path=None):
    path = path or os.path.join(HERE, "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def _abspath(p):
    """config 의 상대경로(프로젝트 루트 기준)를 절대경로로."""
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def load_dataset(cfg, log=print):
    """master_X / master_Y / scaffold_split 로드 후 split mask 반환.

    Returns
    -------
    X : DataFrame  (cid, smiles_canonical)
    Y : ndarray (N, n_pt) int  멀티라벨 정답
    ycols : list[str]  PT 컬럼명
    masks : dict[str, ndarray(bool)]  {"train","valid","test"} 행 마스크
    """
    X = pd.read_parquet(_abspath(cfg["data"]["master_x"]))
    Y = pd.read_parquet(_abspath(cfg["data"]["master_y"]))

    # 정렬·정합성 검증 (재계산하지 않고 그대로 사용하므로 입력 무결성만 확인)
    assert list(X["cid"]) == list(Y["cid"]), "X/Y cid 정렬 불일치 — 파이프라인 산출물 확인 필요"
    ycols = [c for c in Y.columns if c != "cid"]

    with open(_abspath(cfg["data"]["split"])) as f:
        split = json.load(f)

    sp = X["cid"].astype(str).map(split)
    n_missing = int(sp.isna().sum())
    if n_missing:
        raise ValueError(f"scaffold_split 에 없는 cid {n_missing}개 — split 그대로 로드 원칙 위반 가능")

    masks = {grp: (sp == grp).values for grp in ("train", "valid", "test")}
    Ym = Y[ycols].values.astype(int)

    log(f"[data] 분자 {len(X)} × PT {len(ycols)} | split "
        f"train {masks['train'].sum()} / valid {masks['valid'].sum()} / test {masks['test'].sum()}")
    return X, Ym, ycols, masks


if __name__ == "__main__":
    cfg = load_config()
    X, Y, ycols, masks = load_dataset(cfg)
    print("OK", X.shape, Y.shape, len(ycols))
