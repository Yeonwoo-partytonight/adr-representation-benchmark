"""unseen_target.py — A10: fold-local unseen-target 정의 + sequence-novelty 층 (docs/41 §6, 사전등록 §9).

각 outer fold f: T_train,f = 해당 fold train 약물의 매핑 UniProt canonical accession 집합. 약물 d의 T_d.
  - all-seen  : T_d ⊆ T_train,f
  - all-unseen: T_d ∩ T_train,f = ∅ 且 T_d ≠ ∅
  - mixed     : 그 외(≥1 seen & ≥1 unseen)
  - no-target : T_d = ∅  — **별도 층**(all-unseen에 넣지 말 것)

canonicalization(고정): isoform suffix(-N) 제거 → base accession; secondary→primary 매핑; obsolete 제외;
  reviewed(Swiss-Prot) 우선; 동일 서열 복수 accession은 대표 accession으로 병합(제공 매핑 기반).

sequence novelty 층(exact-unseen과 분리): unseen target t에 s(t)=max_{u∈T_train,f} seqid(t,u).
  drug-level aggregation = **보수적**: 모든 target이 exact-unseen 且 drug 요약 s_drug = max_t s(t) 로 bin.
  (drug가 seen target을 하나라도 가지면 s_drug=100(exact) → 'seen'.)
  층 경계(결과 무참조·문헌 근거 사전 고정): seen / ≥90 / 70–90 / 40–70 / <40.
  identity 도구·DB·alignment·버전 고정(IDENTITY_METHOD). 최소 표본·positive support, formal vs descriptive 지정.

⚠️ 무결성: 입력 T_d·T_train,f·seqid는 호출자 제공(확증 fold는 확증 단계에서만 채움). 순수 함수.
"""
from __future__ import annotations

__all__ = [
    "classify_drug", "canonicalize_accession", "canonicalize_set",
    "drug_sequence_stratum", "SEQID_BOUNDARIES", "SEQID_STRATA", "IDENTITY_METHOD",
    "MIN_SUPPORT", "INFERENCE_MODE",
]

# 층 경계(%) — 결과 무참조로 사전 고정(문헌 표준 remote-homology 구간).
SEQID_BOUNDARIES = {"high": 90.0, "mid": 70.0, "low": 40.0}
SEQID_STRATA = ["seen", "unseen_ge90", "unseen_70_90", "unseen_40_70", "unseen_lt40", "no-target"]

# identity 도구·DB·alignment·버전(사전 고정, 결과 무참조). 실제 값은 확증 단계 산출물에도 동일 기록.
IDENTITY_METHOD = {
    "tool": "mmseqs2 easy-search (bidirectional best identity)",
    "sequence_db": "UniProtKB canonical (본 표적셋 accession의 canonical sequence)",
    "identity_def": "alignment percent identity(%), 양방향 max",
    "version_pinned_in_manifest": True,
    "note": "정확 도구/버전은 confirmatory 산출과 manifest에 동일 기록. 경계는 결과 무참조 사전 고정.",
}

# 최소 표본·positive support(사전 고정) + 층별 formal inference vs descriptive.
MIN_SUPPORT = {"min_drugs": 20, "min_positive_pt_support": 5}
INFERENCE_MODE = {
    "seen": "formal (primary seen-target 주장)",
    "unseen_ge90": "descriptive (근접 상동 — 전이 주장 약함)",
    "unseen_70_90": "descriptive-to-formal (표본 충분 시 formal)",
    "unseen_40_70": "formal (전이 주장 핵심 층, 표본 충분 시)",
    "unseen_lt40": "descriptive (remote homology; 표본 희소 예상 → hypothesis-generating)",
    "no-target": "excluded (별도 층, 전이 분석 제외)",
    "rule": "표본<MIN_SUPPORT 층은 formal inference 대신 point estimate+wide CI(descriptive)로만 보고.",
}


def canonicalize_accession(acc, secondary_to_primary=None, seq_representative=None):
    """단일 accession → canonical primary accession(고정 규칙).

    1) isoform suffix 제거: 'P12345-2' → 'P12345'.
    2) secondary→primary 매핑(제공 시).
    3) 동일 서열 대표 accession 병합(seq_representative 제공 시).
    (obsolete·unreviewed 제외는 상위 매핑 단계에서 수행 — 여기선 표기 정규화만.)"""
    a = str(acc).strip()
    if "-" in a:
        a = a.split("-")[0]                       # isoform suffix 제거
    if secondary_to_primary:
        a = secondary_to_primary.get(a, a)        # secondary→primary
    if seq_representative:
        a = seq_representative.get(a, a)          # 동일서열 대표로 병합
    return a


def canonicalize_set(accs, secondary_to_primary=None, seq_representative=None):
    """accession 집합 → canonical accession 집합(중복 병합)."""
    return {canonicalize_accession(a, secondary_to_primary, seq_representative) for a in accs}


def classify_drug(T_d, T_train_f):
    """fold-local 4분류. T_d·T_train_f = canonical accession 집합."""
    T_d = set(T_d)
    T_train_f = set(T_train_f)
    if len(T_d) == 0:
        return "no-target"
    if T_d <= T_train_f:
        return "all-seen"
    if len(T_d & T_train_f) == 0:
        return "all-unseen"
    return "mixed"


def _bin_identity(s):
    """s(%) → novelty stratum 라벨(unseen 전제)."""
    b = SEQID_BOUNDARIES
    if s >= b["high"]:
        return "unseen_ge90"
    if s >= b["mid"]:
        return "unseen_70_90"
    if s >= b["low"]:
        return "unseen_40_70"
    return "unseen_lt40"


def drug_sequence_stratum(T_d, T_train_f, seqid_max):
    """보수적 drug-level novelty 층.

    seqid_max : {target: max identity(%) to T_train_f}  (unseen target에 대해서만 필요).
    - T_d 비면 'no-target'.
    - seen target을 하나라도 가지면 s_drug=100 → 'seen'.
    - all-unseen이면 s_drug = max_t s(t) 로 bin(보수적: 가장 train에 가까운 target이 층을 결정)."""
    T_d = set(T_d)
    T_train_f = set(T_train_f)
    if len(T_d) == 0:
        return "no-target"
    if len(T_d & T_train_f) > 0:                   # seen target 존재(exact) → seen
        return "seen"
    # all-unseen: 각 target의 train 최대 identity 중 최댓값(가장 가까운 것)으로 보수적 bin
    s_drug = max(float(seqid_max.get(t, 0.0)) for t in T_d)
    return _bin_identity(s_drug)
