#!/usr/bin/env python3
"""STEP A — featurize (v1_RF).

명세 docs/08_v1_rf_spec.md §2 STEP A.
- RDKit Morgan Fingerprint radius=2, nBits=2048.
- 최신 RDKit 권장 API: rdFingerprintGenerator.GetMorganGenerator (deprecation 회피).
- SMILES→mol 실패 분자는 목록 기록(실제로는 valid 만 들어옴).
- 출력: X_fp (N×2048 uint8), 행 순서 = master_X cid 순.
"""
import numpy as np
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import rdFingerprintGenerator

RDLogger.DisableLog("rdApp.*")


def morgan_matrix(smiles_list, radius=2, n_bits=2048, log=print):
    """SMILES 리스트 → (N, n_bits) uint8 Morgan FP 행렬.

    Returns
    -------
    M : ndarray (N, n_bits) uint8
    failed : list[int]  mol 변환 실패 행 인덱스
    """
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    M = np.zeros((len(smiles_list), n_bits), dtype=np.uint8)
    failed = []
    for i, smi in enumerate(smiles_list):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            failed.append(i)
            continue
        # GetFingerprintAsNumPy → uint8 비트벡터(빠르고 사본 불필요)
        M[i] = gen.GetFingerprintAsNumPy(mol).astype(np.uint8)
    if failed:
        log(f"[features] SMILES→mol 실패 {len(failed)}개 (인덱스: {failed[:20]}{'...' if len(failed) > 20 else ''})")
    log(f"[features] Morgan FP r={radius} bits={n_bits} → {M.shape} (밀도 {M.mean():.4f})")
    return M, failed


if __name__ == "__main__":
    from data import load_config, load_dataset
    cfg = load_config()
    X, Y, ycols, masks = load_dataset(cfg)
    fp = cfg["fingerprint"]
    M, failed = morgan_matrix(X["smiles_canonical"].tolist(), fp["radius"], fp["n_bits"])
    print("OK", M.shape, "failed", len(failed))
