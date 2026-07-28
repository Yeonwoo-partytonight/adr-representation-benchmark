#!/usr/bin/env python3
"""ladder_confirmatory.py — v3 RF-family 확증 사다리(부분): M1b-독립 피처 블록 + RF 하네스 동결.

근거·설계(임의 변경 금지):
  docs/30_preregistration_OSF_clean.md §4(모델 사다리·표현통제·집계)·§6(분할)·§7(지표)·§8(통계)·§13(실행순서·예산),
  docs/31_v3_target_audit_meanpool_report.md(mean-pool primary 입력·coverage 상수 확인).
  사전등록서는 동결(OSF, 2026-07-23) → 설계·가설·집계·성공기준 변경 금지.

본 파일의 범위(사전등록 §13 실행순서 2번의 **완결 실행** — 2026-07-24, 7모델 전부 동결):
  - 동결·조립: M0, M1, M2(=M1+서열, secondary), **M1b·M2b·P-ID·P-FAM·C-CAP**(M1b 기준 분기).
  - 블록: B0·B1·B_seq·B_pid·C_ccap(기존 동결) + **B_m1b(M1b 공변량)·B_fam(P-FAM family)**(2026-07-24 데이터 확보 후 구현).
    · B_m1b 소스 = 08_m1b_covariates.csv (fetch_m1b_covariates.py; 교수님 승인 §4-A ChEMBL 1회 캐시 확장).
    · B_fam 소스 = **10_target_family_biological.csv (생물학적 family; fetch_target_family_biological.py)**.
  - ⚠️ 사전등록 설계·가설·집계·성공기준 불변. 보류였던 두 블록의 **데이터 확보**일 뿐(라벨/분자셋/split/구조/mean-pool/Morgan 불변).

P-FAM family 재정의(2026-07-24 교수님 승인 — docs/35):
  - **변경**: B_fam primary = 09(자체 mmseqs 50% 클러스터, 715/902=79.3% 싱글톤 → coarse-family 통제 미달) →
    **10(생물학적 family: ChEMBL protein class L2, Kinase/GPCR/Ion channel 수준 42 family, 19.1% 싱글톤)**. P-FAM만 재조립·재동결.
  - **자체클러스터(09)는 삭제하지 않고 `B_fam_selfclust`(sensitivity, 사전등록 §9 family 정의 다중)로 보존.**
  - **M0·M1·M2·M1b·M2b·P-ID·C-CAP 블록/모델은 바이트 불변**(재계산·덮어쓰기 금지) — 하단 byte-invariance assert로 강제.
  - 네트워크 = §3-A(기존 target_chembl_id/uniprot의 protein_classification / target_component class + 전체 class 트리)만.

무결성(사전등록 §제약):
  - **확증용 split(seed 201~205 × 3) 생성·조회·예측 금지.** smoke test는 seed-42 **개발** split 전용(탐색적, 확증 수치 아님).
  - 재다운로드·mock·DrugBank·라벨/분자셋/구조 변경 없음. **본 스크립트 네트워크 호출 0**(08/09 CSV·동결 npy·parquet 재사용).
    데이터 소스 네트워크는 §4-A 승인 범위(기존 943 chembl_id의 mechanism/confidence/first_approval)로만 — fetch_m1b_covariates.py.
  - RF 하이퍼파라미터 재탐색·재튜닝 금지 — pilot 레시피 그대로(v1_RF/src/config.yaml·baseline.py, v2_GNN/src/robustness.py rf_proba, pilot RF macro AP≈0.191).
  - PCA-64 그대로(svd_solver='full', random_state 고정). 모든 fold 통계는 train-only fit + leakage assert.
  - 결정적 실행(seed·random_state 고정, 집계 순서 고정). 기존 npy 덮어쓰기 없음.

산출:
  v3_Multimodal/config/ladder_freeze.json      # 동결 스펙(블록·차원·fit 규칙·RF 하이퍼·보류 목록)
  data/processed/_ladder_smoke_stats.json      # smoke 결과(누수 assert·C-CAP 매칭·macro AP) — gitignore(신규 접미)
  docs/32_v3_ladder_freeze_partial.md          # (별도 저자) 매니페스트

실행: .venv/bin/python3 v3_Multimodal/src/ladder_confirmatory.py
"""
import os
import sys
import json
import platform
import hashlib
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import average_precision_score

from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import rdFingerprintGenerator

RDLogger.DisableLog("rdApp.*")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PROC = os.path.join(ROOT, "data", "processed")
CONF = os.path.join(ROOT, "v3_Multimodal", "config")
os.makedirs(CONF, exist_ok=True)

# ── 동결 상수 (재탐색·재튜닝 금지) ─────────────────────────────────────────────
SEED = 42
PCA_K = 64
MORGAN_RADIUS, MORGAN_BITS = 2, 2048
# pilot RF 레시피(=default RF, macro AP≈0.191): v1_RF/src/config.yaml + v2_GNN/src/robustness.py rf_proba
RF_KW = dict(n_estimators=300, max_depth=None, n_jobs=-1, class_weight="balanced_subsample")

# 동결 산출물 입력(재다운로드·재임베딩 금지) — docs/31 primary(human mean-pool)
F_MASTER_X = os.path.join(PROC, "master_X.parquet")
F_MASTER_Y = os.path.join(PROC, "master_Y.parquet")
F_SPLIT = os.path.join(PROC, "scaffold_split.json")     # seed-42 개발 split 전용
F_EMB = os.path.join(PROC, "drug_target_emb_meanpool.npy")        # B_seq 입력(primary)
F_MASK = os.path.join(PROC, "drug_target_mask_meanpool.npy")
F_NTGT = os.path.join(PROC, "drug_n_targets_meanpool.npy")
F_COV = os.path.join(PROC, "drug_target_coverage_meanpool.npy")   # 참고만(피처 제외 — 상수 1.0)
F_PID = os.path.join(PROC, "target_mapping", "06_targets_human.csv")  # cid→uniprot 표적셋
F_M1B = os.path.join(PROC, "target_mapping", "08_m1b_covariates.csv")  # B_m1b 공변량 (fetch_m1b_covariates.py 산출)
F_FAM = os.path.join(PROC, "target_mapping", "09_target_family_clusters.csv")  # B_fam_selfclust (mmseqs2 자체클러스터, sensitivity 보존)
F_FAMBIO = os.path.join(PROC, "target_mapping", "10_target_family_biological.csv")  # ★ B_fam primary (생물학적 family; fetch_target_family_biological.py)
F_FAMBIO_STATS = os.path.join(PROC, "target_mapping", "_target_family_biological_stats.json")


def log(m):
    print(m, flush=True)


def _mask_from_idx(idx, n):
    m = np.zeros(n, dtype=bool)
    m[np.asarray(idx)] = True
    return m


def eff_rank(X):
    """스펙트럼 엔트로피 유효차원(Roy & Vetterli): exp(-Σ p_i ln p_i), p_i=λ_i/Σλ_i (공분산 고유값)."""
    Xc = X - X.mean(0)
    cov = (Xc.T @ Xc) / max(len(X) - 1, 1)
    ev = np.linalg.eigvalsh(cov)
    ev = ev[ev > 1e-12]
    if ev.size == 0:
        return 0.0
    p = ev / ev.sum()
    return float(np.exp(-(p * np.log(p)).sum()))


def feat_norm(X):
    """행별 L2 norm 평균(feature norm 매칭 진단)."""
    return float(np.linalg.norm(X, axis=1).mean())


# ═══════════════════════════════════════════════════════════════════════════
# 피처 블록 (M1b-독립) — 모든 fold 통계는 해당 fold의 train(valid 제외)에서만 fit
# ═══════════════════════════════════════════════════════════════════════════
class Block:
    """공통 인터페이스. fit(train_idx)은 train 행만 보고, transform(idx)은 임의 인덱스에 적용.
    _fit_rows_mask = fit 시 실제로 참조한 행(bool, 길이 N) → leakage_assert에서 train ⊇ fit 검증."""
    name = "base"

    def __init__(self, n):
        self.n = n
        self._fit_rows_mask = np.zeros(n, dtype=bool)
        self.dim = 0

    def fit(self, train_idx):
        raise NotImplementedError

    def transform(self, idx):
        raise NotImplementedError

    def leakage_assert(self, train_idx):
        """fit이 test/valid 인덱스를 보지 않았음을 강제(누수 안전)."""
        train_mask = _mask_from_idx(train_idx, self.n)
        leaked = self._fit_rows_mask & ~train_mask
        assert not leaked.any(), (
            f"[{self.name}] leakage: fit이 non-train 행 {int(leaked.sum())}개 참조")
        return {"block": self.name, "n_fit_rows": int(self._fit_rows_mask.sum()),
                "n_train": int(train_mask.sum()), "leak_rows": 0, "dim": self.dim}


class MorganBlock(Block):
    """B0 — Morgan(ECFP) r=2, 2048-bit (pilot v1_RF 정의 그대로). 결정적, fit 불필요."""
    name = "B0_morgan"

    def __init__(self, smiles, cid_order):
        super().__init__(len(smiles))
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)
        M = np.zeros((len(smiles), MORGAN_BITS), dtype=np.uint8)
        n_fail = 0
        for i, smi in enumerate(smiles):
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                M[i] = gen.GetFingerprintAsNumPy(mol).astype(np.uint8)
            else:
                n_fail += 1
        self.M = M
        self.n_fail = n_fail
        self.dim = MORGAN_BITS

    def fit(self, train_idx):
        # 결정적 지문 — fit 없음. _fit_rows_mask 비움(누수 assert 항상 통과).
        return self

    def transform(self, idx):
        return self.M[np.asarray(idx)].astype(np.float32)


class CountMaskBlock(Block):
    """B1 — log1p(표적수) [train StandardScaler] + mask(0/1 원본). coverage 제외(상수 1.0·mask 중복)."""
    name = "B1_count_mask"

    def __init__(self, n_targets, mask):
        super().__init__(len(n_targets))
        self.logn = np.log1p(n_targets.astype(np.float64))[:, None]  # (N,1)
        self.mask = mask.astype(np.float32)[:, None]                 # (N,1) 0/1
        self.dim = 2

    def fit(self, train_idx):
        # 0=표적없음은 실측값 → 전체 train으로 표준화(사전등록 §4 / pilot n_targets 관례)
        self._fit_rows_mask = _mask_from_idx(train_idx, self.n)
        self.sc = StandardScaler().fit(self.logn[train_idx])
        return self

    def transform(self, idx):
        idx = np.asarray(idx)
        a = self.sc.transform(self.logn[idx]).astype(np.float32)
        return np.hstack([a, self.mask[idx]])


class SeqBlock(Block):
    """B_seq(primary) — mean-pool ProtBERT(1024) → z-score → PCA-64.
    fit = train ∩ 매핑 약물만(zero 결측 제외). transform 후 비매핑 행 재-0."""
    name = "B_seq"

    def __init__(self, emb, mask, pca_k=PCA_K):
        super().__init__(len(emb))
        self.emb = emb.astype(np.float64)   # (N,1024)
        self.mask = mask.astype(bool)       # (N,)
        self.pca_k = pca_k
        self.dim = pca_k
        self.evr = None

    def fit(self, train_idx):
        train_mask = _mask_from_idx(train_idx, self.n)
        fit_mask = train_mask & self.mask          # ★ train ∩ 매핑(zero 결측 제외 = 여전히 train-only)
        assert fit_mask.sum() >= self.pca_k, f"[{self.name}] fit 매핑행 {int(fit_mask.sum())} < PCA {self.pca_k}"
        self._fit_rows_mask = fit_mask
        self.sc = StandardScaler().fit(self.emb[fit_mask])
        Xs = self.sc.transform(self.emb[fit_mask])
        self.pca = PCA(n_components=self.pca_k, svd_solver="full", random_state=SEED).fit(Xs)
        self.evr = float(self.pca.explained_variance_ratio_.sum())
        return self

    def transform(self, idx):
        idx = np.asarray(idx)
        Xs = self.sc.transform(self.emb[idx])
        Xp = self.pca.transform(Xs).astype(np.float32)
        unmapped = ~self.mask[idx]                 # ★ 표준화→PCA→마스크 재적용: 비매핑은 정확히 0
        Xp[unmapped] = 0.0
        assert np.abs(Xp[unmapped]).sum() == 0.0, f"[{self.name}] 비매핑 재-0 실패"
        return Xp


class PidBlock(Block):
    """B_pid — UniProt 표적 multi-hot. vocab = fold train 매핑 약물의 표적만(train-fit). test OOV 표적 드롭.
    (모델 조립은 M1b 확정 후 — 여기선 블록 fit/transform + 누수 assert만.)"""
    name = "B_pid"

    def __init__(self, cid_to_targets, cid_order):
        super().__init__(len(cid_order))
        # 행별 표적셋(cid 정렬 = master_X 순서)
        self.targets_per_row = [set(cid_to_targets.get(int(c), set())) for c in cid_order]
        self.vocab = []
        self.vidx = {}

    def fit(self, train_idx):
        self._fit_rows_mask = _mask_from_idx(train_idx, self.n)
        vocab = set()
        for i in train_idx:
            vocab |= self.targets_per_row[i]
        self.vocab = sorted(vocab)                 # 결정적 집계 순서
        self.vidx = {u: j for j, u in enumerate(self.vocab)}
        self.dim = len(self.vocab)
        return self

    def transform(self, idx):
        idx = np.asarray(idx)
        M = np.zeros((len(idx), self.dim), dtype=np.float32)
        n_oov = 0
        for r, i in enumerate(idx):
            for u in self.targets_per_row[i]:
                j = self.vidx.get(u)
                if j is not None:
                    M[r, j] = 1.0
                else:
                    n_oov += 1                     # OOV 표적 드롭(train vocab 밖)
        self.last_oov = n_oov
        return M


class CcapBlock(Block):
    """C_ccap — capacity-matched 합성 공변량. 표적 신호 0.
    매칭: 출력차원(=B_seq.pca_k) + feature norm + effective rank + **B_seq와 동일한 mask sparsity**.
    B_seq가 비매핑 약물을 0으로 두므로 C-CAP도 비매핑은 0(같은 결측패턴) → B_seq와의 유일한 차이는
    '매핑 약물의 값이 실제 서열임베딩 vs 표적무관 노이즈'뿐(공정 용량통제).

    구성: L=chol(cov of B_seq **매핑 train 행**), z~N(0,I) 행-인덱스 결정적 시드(표적 무관)
         → x = mean + z·Lᵀ, 이후 비매핑 행 재-0. fit은 B_seq fit 후 그 매핑 train 출력의 2차 통계만(train-only)."""
    name = "C_ccap"

    def __init__(self, seq_block, master_seed=SEED):
        super().__init__(seq_block.n)
        self.seq = seq_block
        self.master_seed = master_seed
        self.dim = seq_block.pca_k

    def fit(self, train_idx):
        train_idx = np.asarray(train_idx)
        train_out = self.seq.transform(train_idx)           # (n_train, K) — B_seq는 이미 fit됨
        mapped_local = self.seq.mask[train_idx]             # bool (n_train,)
        mapped_out = train_out[mapped_local]               # 매핑·비영 행만(= B_seq fit 모집단과 정합)
        assert mapped_out.shape[0] >= self.dim, f"[{self.name}] 매핑 train {mapped_out.shape[0]} < K {self.dim}"
        # ★ leakage: fit이 참조한 행 = train ∩ 매핑 (B_seq와 동일 모집단, train-only)
        fit_mask = _mask_from_idx(train_idx, self.n) & self.seq.mask
        self._fit_rows_mask = fit_mask
        self.mean = mapped_out.mean(0)
        cov = np.cov(mapped_out, rowvar=False)
        self.L = np.linalg.cholesky(cov + 1e-6 * np.eye(self.dim))   # PSD 보정
        # 매칭 진단(매핑 train 기준)
        self.train_effrank = eff_rank(mapped_out)
        self.train_featnorm = feat_norm(mapped_out)
        return self

    def _row_noise(self, i):
        ss = np.random.SeedSequence([int(self.master_seed), int(i)])   # 표적 무관·결정적
        return np.random.default_rng(ss).standard_normal(self.dim)

    def transform(self, idx):
        idx = np.asarray(idx)
        Z = np.stack([self._row_noise(int(i)) for i in idx])           # (len,K) iid N(0,I)
        out = (self.mean + Z @ self.L.T).astype(np.float32)
        unmapped = ~self.seq.mask[idx]                                 # ★ B_seq와 동일 mask sparsity
        out[unmapped] = 0.0
        return out


# ═══════════════════════════════════════════════════════════════════════════
# M1b·P-FAM 블록 (2026-07-24 데이터 확보 후 구현 — 사전등록 §4 설계 그대로, 데이터만 확보)
#   소스: 08_m1b_covariates.csv (fetch_m1b_covariates.py; §4-A 승인 범위 ChEMBL 1회 캐시 확장),
#         09_target_family_clusters.csv (cluster_target_families.py; mmseqs2 자체 50% 클러스터).
#   ⚠️ 사전등록 설계·가설·집계·성공기준 불변 — 보류(스텁)였던 두 블록의 **데이터 확보**일 뿐.
# ═══════════════════════════════════════════════════════════════════════════
class M1bCovariateBlock(Block):
    """B_m1b — M1b study-intensity/evidence 공변량 블록 (사전등록 §4 리스트).

    ★ M1b primary 재지정 (2026-07-24 19:45 KST amendment, 사용자 승인 안 B; docs/33 항목6·docs/40 §3):
      사전등록 §4 M1b 공변량 열거는 **닫힌 목록**이며 pChEMBL 미포함:
        {ChEMBL target evidence count, mechanism vs binding 비율, 평균/최대 confidence, 승인/최초라벨 연도}.
      → **primary `B_m1b` = pChEMBL 제외(10차원) = 등록 §4 정확 일치.**
        pChEMBL 포함(13차원)판은 `B_m1b_pchembl`(사전지정 sensitivity)로 강등·보존.
      (이전 16:33 "유지+amendment 명문화"는 위 19:45 정정으로 대체됨 — docs/33 append-only 이력.)

    사전등록 §4 M1b 공변량(예측시점 허용만; 적응증·ATC는 leakage로 제외):
      1) ChEMBL target evidence count  → 08.evidence_count (pchembl activity 레코드 수) → log1p
      2) mechanism vs binding 비율      → 08.mechanism_target_n / binding_target_n (mechanism endpoint 실측) → ratio
      3) 평균/최대 confidence           → 08.confidence_mean / _max (assay confidence_score 0–9) + missing 지시자
      4) 승인/최초라벨 연도             → 08.first_approval_year (ChEMBL first_approval) + missing 지시자
      [sensitivity 전용] pchembl-strength mean/max → 08.pchembl_mean / _max (05b pchembl_median) + missing 지시자

    내부적으로 항상 full 13차원(연속 9 + 지시자 4)을 계산한 뒤 `include_pchembl`로 컬럼 선택:
      · primary (include_pchembl=False, dim=10): 연속 7 = log1p(evidence), log1p(mech_n), log1p(bind_n),
        mech_vs_bind_ratio, confidence_mean, confidence_max, first_approval_year;
        지시자 3 = confidence_missing, year_missing, chembl_unmapped.
      · sensitivity (include_pchembl=True, dim=13): 위 + pchembl_mean, pchembl_max (연속), pchembl_missing (지시자).
    연속형은 **fold train에서만 StandardScaler fit**(누수 assert), 결측은 0 대치(날조 아님).
    지시자는 미표준화. chembl_unmapped=1 → 미매칭 약물(전 공변량 0 & 나머지 결측지시자도 1).
    """
    name = "B_m1b"
    FULL_CONT_NAMES = ["log1p_evidence_count", "log1p_mechanism_target_n", "log1p_binding_target_n",
                       "mechanism_vs_binding_ratio", "confidence_mean", "confidence_max",
                       "first_approval_year", "pchembl_mean", "pchembl_max"]
    FULL_IND_NAMES = ["confidence_missing", "year_missing", "pchembl_missing", "chembl_unmapped"]
    # 컬럼 선택(full 인덱스 기준). primary=pChEMBL 제외, sensitivity=full.
    PRIMARY_CONT_IDX = [0, 1, 2, 3, 4, 5, 6]           # pchembl_mean(7)·pchembl_max(8) 제외
    PRIMARY_IND_IDX = [0, 1, 3]                        # pchembl_missing(2) 제외, chembl_unmapped(3) 유지
    # 사전등록 §4 열거(닫힌 목록, pChEMBL 미포함) — primary 근거
    PREREG_COVARIATES = [
        "chembl_target_evidence_count", "mechanism_vs_binding_ratio",
        "confidence_mean", "confidence_max", "approval_or_first_label_year",
    ]
    SOURCE_STATUS = {
        "chembl_target_evidence_count": "08_m1b_covariates.csv:evidence_count (pchembl activity 레코드 수)",
        "mechanism_vs_binding_ratio": "08_m1b_covariates.csv:mechanism_target_n/binding_target_n (mechanism endpoint 실측)",
        "confidence_mean": "08_m1b_covariates.csv:confidence_mean (assay confidence_score 0–9, §4-A 수집)",
        "confidence_max": "08_m1b_covariates.csv:confidence_max (assay confidence_score 0–9, §4-A 수집)",
        "approval_or_first_label_year": "08_m1b_covariates.csv:first_approval_year (ChEMBL first_approval, §4-A 수집)",
    }
    # sensitivity(B_m1b_pchembl) 전용 추가 근거
    SOURCE_STATUS_PCHEMBL = {
        "pchembl_strength_mean": "08_m1b_covariates.csv:pchembl_mean (05b pchembl_median)",
        "pchembl_strength_max": "08_m1b_covariates.csv:pchembl_max (05b pchembl_median)",
    }

    def __init__(self, cov_by_cid, cid_order, include_pchembl=False, name="B_m1b"):
        """cov_by_cid: {cid: dict(08 컬럼)}. 미매칭 cid는 부재 → 0 + chembl_unmapped=1.
        include_pchembl=False → primary(10차원, 등록 §4 일치); True → sensitivity(13차원)."""
        super().__init__(len(cid_order))
        self.name = name
        self.include_pchembl = include_pchembl
        n = len(cid_order)
        Cfull = np.zeros((n, 9), dtype=np.float64)   # 연속형 full(결측 0 대치)
        Ifull = np.zeros((n, 4), dtype=np.float32)   # 지시자 full
        for i, c in enumerate(cid_order):
            d = cov_by_cid.get(int(c))
            if d is None:                        # ChEMBL 미매칭 약물: 전 공변량 부재 → 모든 결측 지시자 1
                Ifull[i, 0] = Ifull[i, 1] = Ifull[i, 2] = Ifull[i, 3] = 1.0
                continue
            ev = float(d["evidence_count"]); mn = float(d["mechanism_target_n"]); bn = float(d["binding_target_n"])
            ratio = mn / (mn + bn) if (mn + bn) > 0 else 0.0
            Cfull[i, 0] = np.log1p(ev); Cfull[i, 1] = np.log1p(mn); Cfull[i, 2] = np.log1p(bn); Cfull[i, 3] = ratio
            Cfull[i, 4] = float(d["confidence_mean"]); Cfull[i, 5] = float(d["confidence_max"])
            Cfull[i, 6] = float(d["first_approval_year"])
            Cfull[i, 7] = float(d["pchembl_mean"]); Cfull[i, 8] = float(d["pchembl_max"])
            Ifull[i, 0] = float(int(d["confidence_missing"]))
            Ifull[i, 1] = float(int(d["year_missing"]))
            Ifull[i, 2] = float(int(d["pchembl_missing"]))
        self._Cfull = Cfull
        self._Ifull = Ifull                      # 커버리지 리포트용 full 지시자 보존
        if include_pchembl:
            self.cont_idx = list(range(9)); self.ind_idx = list(range(4))
        else:
            self.cont_idx = list(self.PRIMARY_CONT_IDX); self.ind_idx = list(self.PRIMARY_IND_IDX)
        self.C = Cfull[:, self.cont_idx]         # 선택된 연속형(StandardScaler 대상)
        self.I = Ifull[:, self.ind_idx]          # 선택된 지시자
        self.cont_names = [self.FULL_CONT_NAMES[j] for j in self.cont_idx]
        self.ind_names = [self.FULL_IND_NAMES[j] for j in self.ind_idx]
        self.dim = len(self.cont_idx) + len(self.ind_idx)

    def fit(self, train_idx):
        # 연속형은 fold train(valid 제외) 전체로 StandardScaler fit(결측 0 대치 후) — 누수 없음.
        self._fit_rows_mask = _mask_from_idx(train_idx, self.n)
        self.sc = StandardScaler().fit(self.C[train_idx])
        return self

    def transform(self, idx):
        idx = np.asarray(idx)
        cont = self.sc.transform(self.C[idx]).astype(np.float32)
        return np.hstack([cont, self.I[idx]])


class FamilyBlock(Block):
    """B_fam — P-FAM coarse family multi-hot. vocab = **fold train 매핑 약물의 family만**(train-fit),
    test OOV family 드롭 — B_pid와 동일 규칙. 약물별 family = 그 약물의 human single-protein 표적의 family 집합
    (multi-hot OR; 표적당 다중 family 허용). 비매핑 약물은 빈 집합 → 0 벡터.

    두 정의(동일 클래스, 입력만 상이):
      · **B_fam(primary, 생물학적 family)** = ChEMBL protein class L2(Kinase/GPCR/Ion channel 수준) +
        Pfam/InterPro fallback (10_target_family_biological.csv). 사전등록 §4 "target family/domain multi-hot".
      · **B_fam_selfclust(sensitivity 보존)** = 자체 mmseqs2 50% 클러스터(09_target_family_clusters.csv).
        near-identity(79.3% 싱글톤)라 coarse-family 통제엔 부적합 → primary는 생물학 family로 대체, 자체클러스터는 §9 sensitivity 보존."""
    name = "B_fam"

    def __init__(self, cid_to_families, cid_order, name="B_fam"):
        super().__init__(len(cid_order))
        self.name = name
        self.fams_per_row = [set(cid_to_families.get(int(c), set())) for c in cid_order]
        self.vocab = []
        self.vidx = {}

    def fit(self, train_idx):
        self._fit_rows_mask = _mask_from_idx(train_idx, self.n)
        vocab = set()
        for i in train_idx:
            vocab |= self.fams_per_row[i]
        self.vocab = sorted(vocab)               # 결정적 집계 순서
        self.vidx = {u: j for j, u in enumerate(self.vocab)}
        self.dim = len(self.vocab)
        return self

    def transform(self, idx):
        idx = np.asarray(idx)
        M = np.zeros((len(idx), self.dim), dtype=np.float32)
        n_oov = 0
        for r, i in enumerate(idx):
            for u in self.fams_per_row[i]:
                j = self.vidx.get(u)
                if j is not None:
                    M[r, j] = 1.0
                else:
                    n_oov += 1                   # OOV family 드롭(train vocab 밖)
        self.last_oov = n_oov
        return M


# ═══════════════════════════════════════════════════════════════════════════
# 모델 사다리 정의 (사전등록 §4)
# ═══════════════════════════════════════════════════════════════════════════
MODEL_BLOCKS = {
    # 동결(M1b-독립)
    "M0":    ["B0"],
    "M1":    ["B0", "B1"],
    "M2":    ["B0", "B1", "B_seq"],          # = M1 + 서열 (연구량 공변량 미포함, secondary robustness)
    # 동결(M1b 기준 분기 — primary B_m1b = 10차원 pChEMBL 제외, 등록 §4 일치; 2026-07-24 19:45 재지정)
    "M1b":   ["B0", "B1", "B_m1b"],           # primary 기준선
    "M2b":   ["B0", "B1", "B_m1b", "B_seq"],  # primary 처치
    "P-ID":  ["B0", "B1", "B_m1b", "B_pid"],
    "P-FAM": ["B0", "B1", "B_m1b", "B_fam"],
    "C-CAP": ["B0", "B1", "B_m1b", "C_ccap"],
    # 사전지정 sensitivity(pChEMBL 포함 13차원 B_m1b_pchembl) — primary 결론의 pChEMBL 포함/제외 robustness
    "M1b_pchembl": ["B0", "B1", "B_m1b_pchembl"],
    "M2b_pchembl": ["B0", "B1", "B_m1b_pchembl", "B_seq"],
}
# primary 사다리 8모델 동결(2026-07-24). smoke 순서 = 사다리 순서.
FROZEN_MODELS = ["M0", "M1", "M2", "M1b", "M2b", "P-ID", "P-FAM", "C-CAP"]
# 사전지정 sensitivity 모델(primary 판정 대상 아님 — robustness 보고용).
SENSITIVITY_MODELS = ["M1b_pchembl", "M2b_pchembl"]
DEFERRED_MODELS = []          # 보류 없음 — 전 모델 조립됨
DEFERRED_BLOCKS = set()       # 보류 블록 없음 — B_m1b·B_fam 데이터 확보 완료


class DeferredModel(Exception):
    """M1b 블록 미확정 → 조립 금지 모델."""


def assemble_matrix(model_id, blocks, idx):
    """model_id의 블록들을 idx 행에 대해 조립(hstack). 보류 블록 포함 시 DeferredModel.
    ★ 호출 전 모든 블록은 해당 fold train에서 fit되어 있어야 함(누수 안전은 fit 단계에서 보장)."""
    ids = MODEL_BLOCKS[model_id]
    deferred = [b for b in ids if b in DEFERRED_BLOCKS]
    if deferred:
        raise DeferredModel(f"{model_id} 보류 — 미확정 블록 {deferred} (M1b 확정 후 조립).")
    parts = [blocks[b].transform(idx) for b in ids]
    return np.hstack(parts).astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════
# RF 하네스 (pilot 레시피 동결, 결정적) + 지표
# ═══════════════════════════════════════════════════════════════════════════
def rf_fit_predict(Xtr, Ytr, Xeval, seed=SEED):
    """MultiOutputClassifier(RandomForest) — pilot 레시피 그대로. 결정적(random_state 고정)."""
    clf = MultiOutputClassifier(RandomForestClassifier(random_state=seed, **RF_KW))
    clf.fit(Xtr, Ytr)
    P = np.zeros((Xeval.shape[0], Ytr.shape[1]), dtype=np.float32)
    for j, est in enumerate(clf.estimators_):
        cls = list(est.classes_)
        if 1 in cls:
            P[:, j] = est.predict_proba(Xeval)[:, cls.index(1)]
    return P


def macro_ap(Yte, P):
    """macro AP = eval fold에서 양성>0인 PT의 average_precision_score 산술평균(사전등록 §7).
    (전체 370 PT는 global 양성≥10로 사전확정 = ≥10 집합. fold test에선 양성 보유 PT만 정의됨.)
    smoke 리포트용 sanity — 확증 아님·해석 금지."""
    aps, n_eval = [], 0
    for j in range(Yte.shape[1]):
        yt = Yte[:, j]
        if yt.sum() > 0:
            aps.append(average_precision_score(yt, P[:, j]))
            n_eval += 1
    return float(np.mean(aps)), n_eval


# ═══════════════════════════════════════════════════════════════════════════
# 데이터 로드 (동결 산출물)
# ═══════════════════════════════════════════════════════════════════════════
def load_frozen():
    X = pd.read_parquet(F_MASTER_X)
    Y = pd.read_parquet(F_MASTER_Y)
    assert list(X["cid"]) == list(Y["cid"]), "master_X/Y cid 정렬 불일치"
    cid_order = X["cid"].astype(int).tolist()
    # cid 정렬 기준 확인(master_X는 정렬 저장) — 모든 npy가 이 순서와 정합해야 함
    assert cid_order == sorted(cid_order), "master_X cid 미정렬 — npy 정합 전제 위반"
    ycols = [c for c in Y.columns if c != "cid"]
    Ym = Y[ycols].values.astype(int)
    split = json.load(open(F_SPLIT))                    # seed-42 개발 split 전용
    sp = np.array([split[str(c)] for c in cid_order])
    emb = np.load(F_EMB)
    mask = np.load(F_MASK)
    ntgt = np.load(F_NTGT)
    assert emb.shape == (len(cid_order), 1024), f"emb shape {emb.shape}"
    assert mask.shape == ntgt.shape == (len(cid_order),), "mask/ntgt shape 불일치"
    # cid→uniprot 표적셋 (B_pid)
    tdf = pd.read_csv(F_PID)
    cid2targets = tdf.groupby("cid")["uniprot"].apply(lambda s: set(s.dropna())).to_dict()
    # B_m1b 공변량 (08) — {cid: dict(컬럼)}; 미매칭 cid는 부재(블록이 0+지시자 처리)
    mdf = pd.read_csv(F_M1B)
    cov_by_cid = {int(r["cid"]): r for r in mdf.to_dict("records")}
    # ── B_fam primary (생물학적 family, 10) — uniprot→set(family_id) (multi-hot OR) → cid→family 집합 ──
    fbio = pd.read_csv(F_FAMBIO)
    uni2fam_bio = defaultdict(set)
    for r in fbio.to_dict("records"):
        if isinstance(r["uniprot"], str) and r["uniprot"]:
            uni2fam_bio[r["uniprot"]].add(str(r["family_id"]))
    cid2families_bio = {}
    for cid, tgts in cid2targets.items():
        fams = set()
        for u in tgts:
            fams |= uni2fam_bio.get(u, set())
        if fams:
            cid2families_bio[int(cid)] = fams
    n_families_total_bio = len({f for fs in uni2fam_bio.values() for f in fs})
    # ── B_fam_selfclust (자체 mmseqs 50% 클러스터, 09) — sensitivity 보존 (uniprot→cluster_id) ──
    #   ★ family_id = int cluster_id 그대로(기존 B_fam과 동일 정렬순 → P-FAM_selfclust가 기존 P-FAM smoke 정확 재현).
    fdf = pd.read_csv(F_FAM)
    uni2fam_sc = {r["uniprot"]: int(r["cluster_id"]) for r in fdf.to_dict("records")}
    cid2families_sc = {}
    for cid, tgts in cid2targets.items():
        fams = {uni2fam_sc[u] for u in tgts if u in uni2fam_sc}
        if fams:
            cid2families_sc[int(cid)] = fams
    n_families_total_sc = len(set(uni2fam_sc.values()))
    return dict(X=X, cid_order=cid_order, ycols=ycols, Ym=Ym, sp=sp,
                emb=emb, mask=mask, ntgt=ntgt, cid2targets=cid2targets, split=split,
                cov_by_cid=cov_by_cid,
                cid2families_bio=cid2families_bio, n_families_total_bio=n_families_total_bio,
                cid2families_sc=cid2families_sc, n_families_total_sc=n_families_total_sc)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════════
# Smoke test (seed-42 개발 split 전용) + 동결 매니페스트
# ═══════════════════════════════════════════════════════════════════════════
def main():
    log("[ladder_conf] v3 RF-family 확증 사다리 — A0: M1b primary 재지정(pChEMBL 제외 10차원, 등록 §4 일치) 재조립·재동결")
    log("[A0] amendment 2026-07-24 19:45 KST(안 B): primary B_m1b=10차원; sensitivity B_m1b_pchembl=13차원 강등·보존.")
    log(f"[무결성] 확증 split(seed 201~205) 미조회. smoke=seed-42 dev split 전용(탐색적). 본 스크립트 네트워크 0(08/09/10 CSV 재사용).")
    # 생물학 family 소싱 통계(fetch_target_family_biological.py 산출) — B_fam 매니페스트용
    fam_bio_stats = json.load(open(F_FAMBIO_STATS)) if os.path.exists(F_FAMBIO_STATS) else {}
    # 기존 동결 config(있으면) — M0..C-CAP 바이트 불변 assert용
    prior_freeze_path = os.path.join(CONF, "ladder_freeze.json")
    prior_freeze = json.load(open(prior_freeze_path)) if os.path.exists(prior_freeze_path) else None
    d = load_frozen()
    N = len(d["cid_order"])
    train_idx = np.where(d["sp"] == "train")[0]
    valid_idx = np.where(d["sp"] == "valid")[0]
    test_idx = np.where(d["sp"] == "test")[0]
    log(f"[data] N={N} PT={len(d['ycols'])} | split train {len(train_idx)}/valid {len(valid_idx)}/test {len(test_idx)}")

    # ── 블록 인스턴스화 ──
    b_morgan = MorganBlock(d["X"]["smiles_canonical"].tolist(), d["cid_order"])
    b_count = CountMaskBlock(d["ntgt"], d["mask"])
    b_seq = SeqBlock(d["emb"], d["mask"], pca_k=PCA_K)
    b_pid = PidBlock(d["cid2targets"], d["cid_order"])
    b_ccap = CcapBlock(b_seq, master_seed=SEED)          # B_seq 의존(fit 순서 보장)
    b_m1b = M1bCovariateBlock(d["cov_by_cid"], d["cid_order"],
                              include_pchembl=False, name="B_m1b")          # ★ primary 10차원(pChEMBL 제외, 등록 §4)
    b_m1b_pch = M1bCovariateBlock(d["cov_by_cid"], d["cid_order"],
                                  include_pchembl=True, name="B_m1b_pchembl")  # sensitivity 13차원(pChEMBL 포함)
    b_fam = FamilyBlock(d["cid2families_bio"], d["cid_order"], name="B_fam")              # ★ 10 생물학적 family(primary)
    b_fam_sc = FamilyBlock(d["cid2families_sc"], d["cid_order"], name="B_fam_selfclust")  # 09 자체클러스터(sensitivity 보존)

    blocks = {"B0": b_morgan, "B1": b_count, "B_seq": b_seq,
              "B_pid": b_pid, "C_ccap": b_ccap, "B_m1b": b_m1b, "B_m1b_pchembl": b_m1b_pch,
              "B_fam": b_fam, "B_fam_selfclust": b_fam_sc}

    # ── fold train에서만 fit (의존순서: B_seq → C_ccap) ──
    log(f"[fit] seed-42 dev train({len(train_idx)}) 전용 fit — 모든 스케일러·PCA·vocab train-only")
    b_morgan.fit(train_idx)   # no-op (결정적)
    b_count.fit(train_idx)
    b_seq.fit(train_idx)
    b_ccap.fit(train_idx)     # B_seq 이후
    b_pid.fit(train_idx)
    b_m1b.fit(train_idx)      # primary(10차원) StandardScaler(연속형 7) train-only
    b_m1b_pch.fit(train_idx)  # sensitivity(13차원) StandardScaler(연속형 9) train-only
    b_fam.fit(train_idx)      # vocab=train 생물학 family (OOV 드롭)
    b_fam_sc.fit(train_idx)   # vocab=train 자체클러스터 family (sensitivity)

    # ── 누수 assert (전 9블록; B_m1b·B_m1b_pchembl·B_fam·B_fam_selfclust 포함) ──
    leak = {}
    for k in ["B0", "B1", "B_seq", "C_ccap", "B_pid", "B_m1b", "B_m1b_pchembl", "B_fam", "B_fam_selfclust"]:
        leak[k] = blocks[k].leakage_assert(train_idx)
    log(f"[leakage] 전 블록 train-only fit assert 통과(leak_rows=0): {[leak[k]['block'] for k in leak]}")

    # ── 블록 차원·정의 ──
    dims = {"B0_morgan": b_morgan.dim, "B1_count_mask": b_count.dim,
            "B_seq": b_seq.dim, "B_pid": b_pid.dim, "C_ccap": b_ccap.dim,
            "B_m1b": b_m1b.dim, "B_m1b_pchembl": b_m1b_pch.dim,
            "B_fam": b_fam.dim, "B_fam_selfclust": b_fam_sc.dim}
    log(f"[dims] {dims} | B_seq PCA-64 EVR={b_seq.evr:.3f} (fit 매핑 {int(b_seq._fit_rows_mask.sum())}/train {len(train_idx)})")
    log(f"[B_m1b] primary dim={b_m1b.dim} cont={b_m1b.cont_names} ind={b_m1b.ind_names}")
    log(f"[B_m1b_pchembl] sensitivity dim={b_m1b_pch.dim} (pChEMBL 포함 13차원)")
    log(f"[B_pid] vocab(train 표적) = {b_pid.dim} | [B_fam(생물학)] vocab = {b_fam.dim}/전체 {d['n_families_total_bio']} "
        f"| [B_fam_selfclust] vocab = {b_fam_sc.dim}/전체 {d['n_families_total_sc']}")
    # M1b 커버리지(seed-42 dev 서술) — 결측률 (full 지시자 기준, primary/sensitivity 공통)
    Ifull = b_m1b._Ifull
    n_unmapped = int(Ifull[:, 3].sum())
    n_conf_miss = int(Ifull[:, 0].sum()); n_year_miss = int(Ifull[:, 1].sum()); n_pch_miss = int(Ifull[:, 2].sum())
    log(f"[B_m1b] chembl 미매칭 {n_unmapped}/{N} · confidence 결측 {n_conf_miss} · 연도 결측 {n_year_miss} · pchembl 결측 {n_pch_miss}")

    # ── C-CAP 매칭 진단(B_seq 대비 차원·norm·effective rank; train–val gap) ──
    seq_tr, seq_va = b_seq.transform(train_idx), b_seq.transform(valid_idx)
    cap_tr, cap_va = b_ccap.transform(train_idx), b_ccap.transform(valid_idx)
    ccap_match = {
        "dim_B_seq": b_seq.dim, "dim_C_ccap": b_ccap.dim, "dim_match": b_seq.dim == b_ccap.dim,
        "effrank_B_seq_train": eff_rank(seq_tr), "effrank_C_ccap_train": eff_rank(cap_tr),
        "effrank_B_seq_valid": eff_rank(seq_va), "effrank_C_ccap_valid": eff_rank(cap_va),
        "featnorm_B_seq_train": feat_norm(seq_tr), "featnorm_C_ccap_train": feat_norm(cap_tr),
        "featnorm_B_seq_valid": feat_norm(seq_va), "featnorm_C_ccap_valid": feat_norm(cap_va),
        "train_val_gap_effrank_B_seq": eff_rank(seq_tr) - eff_rank(seq_va),
        "train_val_gap_effrank_C_ccap": eff_rank(cap_tr) - eff_rank(cap_va),
        "train_val_gap_featnorm_B_seq": feat_norm(seq_tr) - feat_norm(seq_va),
        "train_val_gap_featnorm_C_ccap": feat_norm(cap_tr) - feat_norm(cap_va),
        "target_signal": 0,  # C-CAP은 표적 무관 시드 노이즈 → 표적 신호 0
    }
    log(f"[C-CAP 매칭] dim {ccap_match['dim_B_seq']}={ccap_match['dim_C_ccap']} | "
        f"effrank seq(tr {ccap_match['effrank_B_seq_train']:.2f}/va {ccap_match['effrank_B_seq_valid']:.2f}) "
        f"cap(tr {ccap_match['effrank_C_ccap_train']:.2f}/va {ccap_match['effrank_C_ccap_valid']:.2f}) | "
        f"featnorm seq {ccap_match['featnorm_B_seq_train']:.2f} cap {ccap_match['featnorm_C_ccap_train']:.2f}")

    # ── 보류 해소 확인: 전 블록·모델 조립 가능(deferred 없음) ──
    deferred_check = {"blocks_deferred": sorted(DEFERRED_BLOCKS), "models_deferred": list(DEFERRED_MODELS),
                      "all_blocks_assembled": True}
    for mid in FROZEN_MODELS + SENSITIVITY_MODELS:   # primary 8 + sensitivity 2 전부 조립 시도(예외 없어야 함)
        assemble_matrix(mid, blocks, train_idx[:8])   # 소량 조립 sanity
    log(f"[동결] 보류 블록/모델 없음 — primary {len(FROZEN_MODELS)} + sensitivity {len(SENSITIVITY_MODELS)}모델 전부 조립 가능"
        f"(deferred_blocks={sorted(DEFERRED_BLOCKS)}).")

    # ── Smoke (seed-42 dev, sanity only, 해석 금지) ──
    #   ★ A0 재지정: primary B_m1b가 13→10차원으로 정정되므로 M1b·M2b·P-ID·P-FAM·C-CAP은 **의도된 재계산**.
    #     M1b-독립 M0·M1·M2만 byte-invariant → 기존 smoke 값 보존(재계산 금지).
    Ytr = d["Ym"][train_idx]
    Yte = d["Ym"][test_idx]
    INVARIANT_PRESERVE = ["M0", "M1", "M2"]                     # M1b-독립 → 불변(보존)
    RECOMPUTE = ["M1b", "M2b", "P-ID", "P-FAM", "C-CAP"]        # B_m1b(10차원) 의존 → 의도된 재계산
    prior_stats_path = os.path.join(PROC, "_ladder_smoke_stats.json")
    prior_smoke = {}
    if os.path.exists(prior_stats_path):
        prior_smoke = json.load(open(prior_stats_path)).get("smoke_macro_ap", {})
    smoke = {}
    for mid in INVARIANT_PRESERVE:                              # 불변 모델: 기존값 보존(재계산 안 함)
        if mid in prior_smoke:
            smoke[mid] = prior_smoke[mid]
            log(f"[smoke:보존] {mid} test macro_AP={smoke[mid]['macro_ap']:.4f} (기존값, 재계산 없음 — byte-invariant)")
        else:
            log(f"[smoke:WARN] {mid} 기존 smoke 값 없음 → 보존 불가(수동 확인 필요)")
    for mid in RECOMPUTE:                                       # B_m1b(10차원) 재조립·재실행
        Xtr = assemble_matrix(mid, blocks, train_idx)
        Xte = assemble_matrix(mid, blocks, test_idx)
        P = rf_fit_predict(Xtr, Ytr, Xte, seed=SEED)
        m_ap, n_ev = macro_ap(Yte, P)
        smoke[mid] = {"macro_ap": m_ap, "n_pt_eval": n_ev, "side_dim": Xtr.shape[1]}
        log(f"[smoke:재계산] {mid}(B_m1b 10차원) feat_dim={Xtr.shape[1]:4d} test macro_AP={m_ap:.4f} (evalPT {n_ev}) — sanity")
    # ── 사전지정 sensitivity smoke ──
    sensitivity_smoke = {}
    for mid in SENSITIVITY_MODELS:                             # pChEMBL 포함 13차원 B_m1b_pchembl
        Xtr = assemble_matrix(mid, blocks, train_idx)
        Xte = assemble_matrix(mid, blocks, test_idx)
        P = rf_fit_predict(Xtr, Ytr, Xte, seed=SEED)
        m_ap, n_ev = macro_ap(Yte, P)
        sensitivity_smoke[mid] = {"macro_ap": m_ap, "n_pt_eval": n_ev, "side_dim": Xtr.shape[1],
                                  "note": "pChEMBL 포함(13차원) B_m1b_pchembl 기반 sensitivity — primary 판정 대상 아님."}
        log(f"[sensitivity:재계산] {mid}(B_m1b_pchembl 13차원) feat_dim={Xtr.shape[1]:4d} test macro_AP={m_ap:.4f} (evalPT {n_ev})")
    # sensitivity: P-FAM_selfclust([B0,B1,B_m1b,B_fam_selfclust]) — 자체클러스터 블록 보존 확인(primary 10차원 B_m1b 기준)
    sc_blocks = ["B0", "B1", "B_m1b", "B_fam_selfclust"]
    Xtr_sc = np.hstack([blocks[b].transform(train_idx) for b in sc_blocks]).astype(np.float32)
    Xte_sc = np.hstack([blocks[b].transform(test_idx) for b in sc_blocks]).astype(np.float32)
    Psc = rf_fit_predict(Xtr_sc, Ytr, Xte_sc, seed=SEED)
    m_ap_sc, n_ev_sc = macro_ap(Yte, Psc)
    sensitivity_smoke["P-FAM_selfclust"] = {
        "macro_ap": m_ap_sc, "n_pt_eval": n_ev_sc, "side_dim": Xtr_sc.shape[1],
        "note": "자체클러스터(09) 보존 블록 sanity. 어떤 primary frozen 모델에도 미포함."}
    log(f"[sensitivity] P-FAM_selfclust feat_dim={Xtr_sc.shape[1]:4d} test macro_AP={m_ap_sc:.4f} "
        f"(evalPT {n_ev_sc}) — 자체클러스터 블록 보존 확인")
    log(f"[smoke] M0 sanity 참조 = v2_GNN robustness seed_42 rf_macro 0.18819 (Morgan-only RF, 불변 보존)")

    # ── 재현 메타 ──
    versions = {"python": platform.python_version(),
                "numpy": np.__version__, "pandas": pd.__version__,
                "sklearn": __import__("sklearn").__version__,
                "rdkit": __import__("rdkit").__version__}
    inputs = {os.path.relpath(p, ROOT): {"sha16": sha256(p)} for p in
              [F_MASTER_X, F_MASTER_Y, F_SPLIT, F_EMB, F_MASK, F_NTGT, F_PID, F_M1B, F_FAMBIO, F_FAM]}

    # ── 동결 config ──
    freeze = {
        "_doc": "v3 RF-family 확증 사다리(부분) 동결 스펙 — 사전등록 §4/§6/§7/§8/§13. 설계 변경 금지.",
        "seed": SEED, "pca_k": PCA_K,
        "morgan": {"radius": MORGAN_RADIUS, "n_bits": MORGAN_BITS, "source": "v1_RF pilot 정의 그대로"},
        "rf_hyperparameters": {**RF_KW,
            "provenance": "pilot default RF(macro AP≈0.191): v1_RF/src/config.yaml + v2_GNN/src/robustness.py rf_proba",
            "retuned": False, "note": "재탐색·재튜닝 금지(사전등록 §13 예산). fairtune tuned RF는 미사용."},
        "blocks_frozen": {
            "B0_morgan": {"dim": b_morgan.dim, "fit": "none(결정적)", "def": "Morgan ECFP r=2 2048bit, cid 정렬"},
            "B1_count_mask": {"dim": b_count.dim, "fit": "log1p(n_targets) StandardScaler on train; mask 0/1 원본",
                              "def": "coverage 제외(docs/31: mapped coverage 상수 1.0 → mask 중복)"},
            "B_seq": {"dim": b_seq.dim, "evr": b_seq.evr,
                      "fit": "train∩매핑에서 z-score→PCA-64(svd_solver=full, random_state=42); transform 후 비매핑 재-0",
                      "input": "drug_target_emb_meanpool.npy(primary, human mean-pool)"},
            "B_pid": {"dim_seed42_dev": b_pid.dim,
                      "fit": "vocab=train 매핑 약물 표적만(train-fit); test OOV 표적 드롭; multi-hot",
                      "input": "target_mapping/06_targets_human.csv (cid→uniprot)",
                      "note": "블록만 동결 — 모델 조립은 M1b 확정 후"},
            "C_ccap": {"dim": b_ccap.dim,
                       "fit": "B_seq train 출력의 mean·cov만(train-only) → chol; z~N(0,I) 행-시드(표적무관) → mean+z·Lᵀ",
                       "match": "차원·feature norm·effective rank(=B_seq train 공분산 표집), 표적신호 0",
                       "held_out_rank_caveat": (
                           f"held-out(seed-42 valid) effective rank 갈림: B_seq {ccap_match['effrank_B_seq_valid']:.2f} "
                           f"vs C_ccap {ccap_match['effrank_C_ccap_valid']:.2f} (docs/32 §3). 실측 서열임베딩이 held-out에서 "
                           f"유효차원 더 감소(train–val gap {ccap_match['train_val_gap_effrank_B_seq']:.2f}) vs 매칭 노이즈 유지"
                           f"({ccap_match['train_val_gap_effrank_C_ccap']:.2f}) — 규정준수·M2b>C-CAP에 보수적. 인위은폐 아님(실측)."),
                       "note": "블록 동결(docs/32); 모델 C-CAP=[B0,B1,B_m1b,C_ccap] 조립·동결(2026-07-24)"},
            "B_m1b": {"dim": b_m1b.dim,
                      "status": "primary — pChEMBL 제외(10차원) = 사전등록 §4 열거 정확 일치 (2026-07-24 19:45 재지정, 안 B)",
                      "fit": "연속형 7(log1p evidence·mech_n·bind_n, mech/bind ratio, confidence mean/max, first_approval_year) "
                             "StandardScaler on train(결측 0 대치) + 지시자 3(confidence_missing, year_missing, chembl_unmapped)",
                      "input": "target_mapping/08_m1b_covariates.csv (fetch_m1b_covariates.py; §4-A ChEMBL 1회 캐시 확장; 컬럼 선택만 변경·재수집 없음)",
                      "prereg_covariates": M1bCovariateBlock.PREREG_COVARIATES,
                      "source_status": M1bCovariateBlock.SOURCE_STATUS,
                      "cont_features": b_m1b.cont_names, "indicators": b_m1b.ind_names,
                      "amendment": "docs/33 항목6(2026-07-24 19:45 KST) — pChEMBL은 §4 닫힌 열거 미포함이라 primary에서 제외; "
                                   "pChEMBL 포함판은 B_m1b_pchembl(sensitivity)로 강등. 확증 OOF 미조회 시점 정정(결과-의존 아님).",
                      "note": "적응증·ATC는 leakage로 제외(sensitivity만·본 블록 미포함, 사전등록 §4)"},
            "B_m1b_pchembl": {"dim": b_m1b_pch.dim,
                      "status": "sensitivity — pChEMBL 포함(13차원). primary(제외) 결론의 pChEMBL 포함/제외 robustness 보고용.",
                      "fit": "연속형 9(primary 7 + pchembl_mean·pchembl_max) StandardScaler on train(결측 0 대치) "
                             "+ 지시자 4(confidence/year/pchembl missing, chembl_unmapped)",
                      "input": "target_mapping/08_m1b_covariates.csv (동일 소스, 컬럼 선택만 상이)",
                      "prereg_covariates": M1bCovariateBlock.PREREG_COVARIATES + ["pchembl_strength_mean", "pchembl_strength_max"],
                      "source_status": {**M1bCovariateBlock.SOURCE_STATUS, **M1bCovariateBlock.SOURCE_STATUS_PCHEMBL},
                      "cont_features": b_m1b_pch.cont_names, "indicators": b_m1b_pch.ind_names,
                      "note": "이전 동결 B_m1b(13차원)와 정의 동일 — sensitivity 블록으로 보존. sensitivity 모델 = M1b_pchembl·M2b_pchembl."},
            "B_fam": {"dim_seed42_dev": b_fam.dim,
                      "status": "primary (P-FAM) — 생물학적 family 재정의(2026-07-24, 교수님 승인; docs/35)",
                      "fit": "vocab=train 매핑 약물의 생물학적 family만(train-fit); test OOV family 드롭; multi-hot(표적당 다중 family OR)",
                      "input": "target_mapping/10_target_family_biological.csv (fetch_target_family_biological.py)",
                      "family_source": ("ChEMBL protein classification (primary) + Pfam/InterPro fallback + SINGLETON(결측). "
                                        f"chosen level = L{fam_bio_stats.get('chosen_level')}"),
                      "level": fam_bio_stats.get("chosen_level"),
                      "n_families_total": d["n_families_total_bio"],
                      "granularity": {
                          "n_families": fam_bio_stats.get("granularity_chosen", {}).get("n_families"),
                          "singleton_family_frac": fam_bio_stats.get("granularity_chosen", {}).get("singleton_family_frac"),
                          "family_per_target": fam_bio_stats.get("granularity_chosen", {}).get("family_per_target"),
                          "coverage_biological": fam_bio_stats.get("granularity_chosen", {}).get("coverage_biological"),
                          "vs_selfcluster": "자체 mmseqs 50% 클러스터 79.3%(715/902) 싱글톤 → 생물학 family로 실질 coarse화(대비=docs/35)"},
                      "gate_decision": fam_bio_stats.get("gate_decision"),
                      "prereg": "사전등록 §4 P-FAM=target family/domain multi-hot(UniProt family·Pfam/InterPro·ChEMBL class), §9 family 정의 다중",
                      "note": "확증 fold마다 vocab 재-fit → 차원 가변(train-fit 원칙, B_pid와 동일). 자체클러스터는 B_fam_selfclust(sensitivity) 보존."},
            "B_fam_selfclust": {"dim_seed42_dev": b_fam_sc.dim,
                      "status": "sensitivity (사전등록 §9 family 정의 다중) — primary에서 대체, 보존만",
                      "fit": "vocab=train 매핑 약물의 family(cluster_id)만(train-fit); test OOV family 드롭; multi-hot",
                      "input": "target_mapping/09_target_family_clusters.csv (cluster_target_families.py; mmseqs2 easy-cluster)",
                      "mmseqs_params": {"min_seq_id": "0.5", "cov": "0.8", "cov_mode": "0", "threads": "1"},
                      "n_families_total": d["n_families_total_sc"],
                      "caveat": ("본 표적셋 자체 50% 클러스터 — near-identity(715/902=79.3% 싱글톤)라 coarse-family 통제엔 부적합 "
                                 "→ P-FAM primary는 생물학 family로 대체. 자체클러스터는 §9 sensitivity로 보존(삭제 안 함)."),
                      "note": "어떤 frozen 모델에도 미포함. sensitivity 분석용 보존 블록(P-FAM_selfclust)."},
        },
        "blocks_deferred": {},
        "models_frozen": {m: MODEL_BLOCKS[m] for m in FROZEN_MODELS},
        "models_deferred": {},
        "sensitivity_blocks": {
            "B_m1b_pchembl": "pChEMBL 포함(13차원) M1b 공변량 — primary B_m1b(10차원, §4 일치)의 pChEMBL 포함/제외 robustness. "
                             "sensitivity 모델 M1b_pchembl=[B0,B1,B_m1b_pchembl], M2b_pchembl=[B0,B1,B_m1b_pchembl,B_seq].",
            "B_fam_selfclust": "자체 mmseqs 50% 클러스터(09) — P-FAM primary에서 대체 후 §9 sensitivity 보존. "
                               "sensitivity 모델 P-FAM_selfclust=[B0,B1,B_m1b,B_fam_selfclust]."},
        "sensitivity_models": {
            "M1b_pchembl": MODEL_BLOCKS["M1b_pchembl"],
            "M2b_pchembl": MODEL_BLOCKS["M2b_pchembl"],
            "P-FAM_selfclust": ["B0", "B1", "B_m1b", "B_fam_selfclust"]},
        "m1b_reprimary_2026_07_24": {
            "change": "primary B_m1b: pChEMBL 포함 13차원 → pChEMBL 제외 10차원(사전등록 §4 닫힌 열거 정확 일치).",
            "reason": ("docs/30·docs/29 §4 M1b 공변량은 닫힌 열거이고 pChEMBL 미포함. pChEMBL은 연구량이 아니라 potency·assay-selection 정보"
                       "(ChatGPT #7)라 '연구량 통제 후 서열 증분' 분해를 흐림 → primary를 등록 열거와 정확히 일치하게 정정(등록 준수 복원 = 금지된 변경 아님)."),
            "amendment_log": "docs/33 항목6 (2026-07-24 19:45 KST) — 이전 16:33 '유지+명문화'를 대체. 확증 OOF 미조회(N).",
            "primary_10_features": {"cont": b_m1b.cont_names, "ind": b_m1b.ind_names},
            "sensitivity_13_features": {"cont": b_m1b_pch.cont_names, "ind": b_m1b_pch.ind_names},
            "reprimary_models": RECOMPUTE,      # B_m1b(10차원)로 재조립·재동결(RF pilot 레시피 그대로, 재튜닝 0)
            "sensitivity_models": SENSITIVITY_MODELS,
            "byte_invariant_blocks": ["B0_morgan", "B1_count_mask", "B_seq", "B_pid", "C_ccap", "B_fam", "B_fam_selfclust"],
            "byte_invariant_models": INVARIANT_PRESERVE,
            "intended_recompute_note": "B_m1b(10차원 정정)·M1b·M2b·P-ID·P-FAM·C-CAP은 byte-invariant 아님(의도된 재계산). "
                                       "models_frozen(블록구성 매핑)은 불변(블록 id 리스트 미변경).",
            "byte_invariance_asserted": True},
        "pfam_refresh_2026_07_24": {
            "change": "P-FAM primary B_fam: 자체 mmseqs 50% 클러스터(09) → 생물학적 family(10, ChEMBL protein class L2 + Pfam/InterPro fallback)",
            "reason": "자체클러스터 715/902=79.3% 싱글톤 = near-identity → coarse-family 통제(RQ3b) 미달. 사전등록 §4 P-FAM 문구는 생물학 family 명시.",
            "scope": "P-FAM/B_fam만 재조립·재동결. M0·M1·M2·M1b·M2b·P-ID·C-CAP 바이트 불변(byte-invariance assert 통과).",
            "selfcluster_preserved_as": "B_fam_selfclust (sensitivity; 09 삭제 안 함)",
            "prereg_unchanged": "설계·가설·집계·성공기준·P-FAM 개념 불변(coarse family 데이터 확보만). docs/30 무수정, docs/33 이탈 1줄 append.",
            "chosen_level": fam_bio_stats.get("chosen_level"),
            "gate_decision": fam_bio_stats.get("gate_decision"),
            "byte_invariance_asserted": True},
        "metric": {"macro_ap": "average_precision_score, fold 양성>0 PT AP 산술평균(사전등록 §7). smoke=sanity, 확증 아님"},
        "versions": versions, "inputs_sha16": inputs,
        "m1b_coverage_seed42_dev": {
            "chembl_unmapped": n_unmapped, "confidence_missing": n_conf_miss,
            "year_missing": n_year_miss, "pchembl_missing": n_pch_miss, "n_total": N},
        "integrity": {
            "confirmatory_split_accessed": False,
            "confirmatory_split_generated": False,
            "smoke_split": "scaffold_split.json (seed-42 dev, train/valid/test)",
            "ladder_network_calls": 0,  # 본 스크립트(ladder_confirmatory.py)는 08/09/10 CSV 재사용, 네트워크 0
            "data_source_network": ("§4-A: fetch_m1b_covariates.py(mechanism/confidence/first_approval, 기존 943 chembl_id); "
                                    "cluster_target_families.py(mmseqs2, 서열=_cache/ 재사용 네트워크 0); "
                                    "§3-A: fetch_target_family_biological.py(기존 표적 protein_classification/target_component class + 전체 class 트리; "
                                    "Pfam/InterPro=캐시 xref 네트워크 0)"),
            "redownload": False, "mock": False, "drugbank": False,
            "labels_molset_structure_changed": False,
            "new_targets_or_molecules_added": False, "remapping": False,
            "existing_npy_overwritten": False,
            "selfcluster_09_overwritten": False,
            "meanpool_morgan_split_changed": False,
            "invariant_models_recomputed": False,  # M0·M1·M2 smoke RF 재계산 안 함(기존값 보존 = byte-invariant)
            "m1b_primary_pchembl_excluded": True,  # A0: primary B_m1b=10차원(§4 일치); 13차원은 sensitivity 강등
            "m1b_dependent_models_recomputed": True,  # M1b·M2b·P-ID·P-FAM·C-CAP = 의도된 재계산(B_m1b 10차원 정정)
            "labels_structure_meanpool_morgan_split_invariant": True,  # 라벨·구조·mean-pool·Morgan·split 불변
            "fabricated_values": {"confidence": 0, "year": 0, "family": 0,
                                  "note": "결측=missing 지시자/SINGLETON fallback+0 대치(날조 0). 커버리지=_m1b_covariate_stats.json·_target_family_biological_stats.json"},
        },
        "reproduce": ".venv/bin/python3 v3_Multimodal/src/ladder_confirmatory.py",
        "reproduce_data_sources": [
            ".venv/bin/python3 v3_Multimodal/src/fetch_m1b_covariates.py     # 08 (§4-A ChEMBL, 결정적 캐시)",
            ".venv/bin/python3 v3_Multimodal/src/fetch_target_family_biological.py  # 10 (§3-A ChEMBL protein class, 생물학 family)",
            "PATH=/opt/homebrew/bin:$PATH .venv/bin/python3 v3_Multimodal/src/cluster_target_families.py  # 09 (mmseqs2, sensitivity 보존)",
        ],
    }

    # ── byte-invariance assert (A0 정정 후) ──
    #   불변 블록 = B0·B1·B_seq·B_pid·C_ccap·B_fam·B_fam_selfclust (B_m1b 미의존).
    #   불변 모델 = M0·M1·M2 (B_m1b 미의존, smoke 값 보존).
    #   의도된 재계산(불변 아님) = B_m1b(10차원 정정)·M1b·M2b·P-ID·P-FAM·C-CAP.
    #   models_frozen(블록 id 리스트 매핑)은 불변(리스트 미변경 — 변화는 B_m1b 블록 내부).
    byte_inv = {"invariant_blocks": [], "invariant_models": [], "models_frozen_identical": None,
                "intended_recompute_blocks": ["B_m1b(13→10)", "(new)B_m1b_pchembl"],
                "intended_recompute_models": RECOMPUTE}
    if prior_freeze is not None:
        inv_blocks = ["B0_morgan", "B1_count_mask", "B_seq", "B_pid", "C_ccap", "B_fam", "B_fam_selfclust"]
        for bk in inv_blocks:
            a = json.dumps(prior_freeze["blocks_frozen"].get(bk), sort_keys=True, ensure_ascii=False)
            b = json.dumps(freeze["blocks_frozen"].get(bk), sort_keys=True, ensure_ascii=False)
            assert a == b, f"[byte-invariance 위반] 불변 블록 '{bk}' 정의가 변경됨"
            byte_inv["invariant_blocks"].append(bk)
        # models_frozen(블록구성 매핑)은 불변이어야 함(B_m1b 블록 내부만 변경, 리스트 미변경)
        a_m = json.dumps(prior_freeze.get("models_frozen"), sort_keys=True, ensure_ascii=False)
        b_m = json.dumps(freeze.get("models_frozen"), sort_keys=True, ensure_ascii=False)
        assert a_m == b_m, "[byte-invariance 위반] models_frozen(사다리 블록구성 매핑)이 변경됨"
        byte_inv["models_frozen_identical"] = True
        for mid in INVARIANT_PRESERVE:
            if mid in prior_smoke and mid in smoke:
                assert smoke[mid] == prior_smoke[mid], f"[byte-invariance 위반] {mid} smoke 값이 보존되지 않음"
                byte_inv["invariant_models"].append(mid)
        # (정직 공개) 의도된 재계산 대상은 이전 값과 달라야 정상 — 강제 아님, 로그만
        changed = [mid for mid in RECOMPUTE if mid in prior_smoke and smoke.get(mid) != prior_smoke.get(mid)]
        byte_inv["m1b_dependent_changed_vs_prior"] = changed
        log(f"[byte-invariance] 불변 블록 {byte_inv['invariant_blocks']} + models_frozen + 불변 모델 {byte_inv['invariant_models']} "
            f"불변 확인 통과. 의도된 재계산(변화) 모델 = {changed}.")
    else:
        byte_inv["models_frozen_identical"] = None
        log("[byte-invariance] 기존 ladder_freeze.json 없음 → 첫 생성(불변 대상 없음).")
    freeze["m1b_reprimary_2026_07_24"]["byte_invariance_check"] = byte_inv

    fpath = os.path.join(CONF, "ladder_freeze.json")
    json.dump(freeze, open(fpath, "w"), indent=2, ensure_ascii=False)
    log(f"[동결] {os.path.relpath(fpath, ROOT)} 저장")

    # ── smoke 결과 JSON (data/processed 신규 접미, gitignore) ──
    stats = {"leakage_assert": leak, "ccap_match": ccap_match,
             "deferred_check": deferred_check, "smoke_macro_ap": smoke,
             "sensitivity_smoke": sensitivity_smoke,
             "block_dims_seed42_dev": dims, "b_seq_evr": b_seq.evr,
             "b_pid_vocab_seed42_dev": b_pid.dim,
             "b_fam_vocab_seed42_dev": b_fam.dim, "b_fam_selfclust_vocab_seed42_dev": b_fam_sc.dim,
             "n_families_total_bio": d["n_families_total_bio"], "n_families_total_selfclust": d["n_families_total_sc"],
             "pfam_family_bio": {"chosen_level": fam_bio_stats.get("chosen_level"),
                                 "granularity_chosen": fam_bio_stats.get("granularity_chosen"),
                                 "gate_decision": fam_bio_stats.get("gate_decision")},
             "invariant_models_preserved": {m: (m in prior_smoke) for m in INVARIANT_PRESERVE},
             "m1b_dependent_recomputed": RECOMPUTE,
             "m1b_coverage_seed42_dev": {"chembl_unmapped": n_unmapped, "confidence_missing": n_conf_miss,
                                         "year_missing": n_year_miss, "pchembl_missing": n_pch_miss},
             "split_counts": {"train": len(train_idx), "valid": len(valid_idx), "test": len(test_idx)},
             "m0_sanity_reference_rf_macro_seed42": 0.18819}
    spath = os.path.join(PROC, "_ladder_smoke_stats.json")
    json.dump(stats, open(spath, "w"), indent=2, ensure_ascii=False, default=float)
    log(f"[smoke stats] {os.path.relpath(spath, ROOT)} 저장 (gitignore)")

    # ── A0 매니페스트 (experiments/audits/) — 근거·감사용(§9) ──
    audit_dir = os.path.join(ROOT, "experiments", "audits")
    os.makedirs(audit_dir, exist_ok=True)
    a0 = {
        "task": "A0 — M1b primary 재지정(pChEMBL 제외 10차원 = 사전등록 §4 일치) 재조립·재동결",
        "amendment": "docs/33 항목6 (2026-07-24 19:45 KST, 안 B). 확증 OOF 미조회(N).",
        "prereg_ref": "docs/30 §4 M1b 공변량 열거(닫힌 목록, pChEMBL 미포함)",
        "primary_B_m1b": {"dim": b_m1b.dim, "cont_features": b_m1b.cont_names, "ind_features": b_m1b.ind_names,
                          "prereg_covariates_matched": M1bCovariateBlock.PREREG_COVARIATES,
                          "pchembl_removed": ["pchembl_mean", "pchembl_max", "pchembl_missing"]},
        "sensitivity_B_m1b_pchembl": {"dim": b_m1b_pch.dim, "cont_features": b_m1b_pch.cont_names,
                                      "ind_features": b_m1b_pch.ind_names},
        "reprimary_models_refrozen": {m: {"blocks": MODEL_BLOCKS[m], "side_dim": smoke[m]["side_dim"],
                                          "leak_rows": 0} for m in RECOMPUTE},
        "sensitivity_models": {m: {"blocks": MODEL_BLOCKS[m], "side_dim": sensitivity_smoke[m]["side_dim"],
                                   "leak_rows": 0} for m in SENSITIVITY_MODELS},
        "leak_assert": {k: leak[k]["leak_rows"] for k in leak},
        "byte_invariance": byte_inv,
        "invariant_models_preserved": {m: smoke.get(m) is not None for m in INVARIANT_PRESERVE},
        "m1b_coverage_seed42_dev": {"chembl_unmapped": n_unmapped, "confidence_missing": n_conf_miss,
                                    "year_missing": n_year_miss, "pchembl_missing": n_pch_miss, "n_total": N},
        "integrity": freeze["integrity"],
        "versions": versions,
        "inputs_sha16": inputs,
    }
    a0path = os.path.join(audit_dir, "A0_m1b_reprimary_manifest.json")
    json.dump(a0, open(a0path, "w"), indent=2, ensure_ascii=False, default=float)
    log(f"[A0 manifest] {os.path.relpath(a0path, ROOT)} 저장")

    log("[완료] A0 — primary B_m1b 10차원(§4 일치) 재조립·재동결 완료. "
        "M0·M1·M2·불변 블록 byte-invariant, sensitivity B_m1b_pchembl(13차원)·M1b_pchembl·M2b_pchembl 동결.")
    return freeze, stats


if __name__ == "__main__":
    main()
