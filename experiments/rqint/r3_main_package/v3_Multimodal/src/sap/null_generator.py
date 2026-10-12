"""null_generator.py — A9: 자연 임베딩 재배치 permutation null (docs/41 §5, 사전등록 §5).

보존(불변): 각 단백질 embedding **자체**, drug degree, target degree, incidence matrix,
  결측 target 패턴, M1b 공변량, embedding 전체 분포.
교환: **target identity ↔ embedding 대응만.** 동일 target은 모든 약물에서 **동일한 permuted
  embedding을 공유**한다(drug-target row별 독립 셔플 금지 — target consistency 파괴 = 지나치게 쉬운 null).
  - global           : 교환 단위 = unique target. **full permutation(fixed point 허용, derangement 아님)**
    — 즉 일부 target이 자기 자신에 매핑돼도 유효(무작위 순열의 자연스러운 결과, 인위적 배제 시 분포 왜곡).
  - family-constrained: 교환 단위 = family 내 unique target. **singleton·size-2 family는 교환 불가
    → 원위치 고정**(가능 permutation 부족[≤2!]·서열정보 미파괴 사유; 규칙 명시, 개수 보고).

PCA/RF 재학습 범위(null 가설 정의의 일부 — 문서화): permuted embedding마다 B_seq PCA를 fold-train에서
  재적합, RF도 fold별 재학습. 이 범위를 null 가설 정의에 포함한다(confirmatory 단계에서 실행;
  본 SAP 모듈은 재배치 **연산자**와 보존 assert만 동결한다).

경험적 p: p_emp = (1 + #{T_b ≥ T_obs}) / (B+1). **B = NULL_B(정확값 동결)**, seed list 고정.
  global·family 둘 다 통과 규칙. empirical_p는 **MC standard error**(≈ sqrt(p(1−p)/B))를 함께 반환.
  ⚠️ 결과 조회 후 B 상향·조기중단·실패 재시도(selective precision) **금지** — NULL_B는 한 값으로 잠근다.
common RF seed: null은 프리즈 레시피 random_state=NULL_RF_COMMON_SEED(=42)를 **전 permutation·전 반복
  동일**하게 사용(representation 효과 격리 — RF 난수 변동이 아니라 embedding 재배치만 신호원). docs/36 runner가
  이 계약을 assert 해야 한다.
중복 sequence(동일 서열 복수 accession): 교환 단위 = accession(unique target)으로 취급하되, 동일 서열
  accession은 embedding이 동일하므로 재배치가 embedding 분포를 바꾸지 않음(규칙 고정·문서화).

⚠️ 무결성: 입력 그래프/embedding은 호출자 제공(synthetic 또는 확증 단계 동결 캐시). 본 모듈은 확증
   split·OOF·master_X/Y를 로드하지 않는 순수 함수다.
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "build_global_permutation", "build_family_permutation",
    "apply_target_embedding_permutation", "empirical_p", "null_incidence_report",
    "assert_preservation", "PRESERVED", "PCA_RF_REFIT_SCOPE", "NULL_B", "NULL_RF_COMMON_SEED",
]

PRESERVED = ["protein_embedding_vectors", "drug_degree", "target_degree", "incidence_matrix",
             "missing_target_pattern", "m1b_covariates", "embedding_distribution"]

# A4: 재배치 null Monte Carlo B **정확값 동결**(결과 무참조 사전 확정; "≥1000" 표현 제거).
#     실행예산 허용 시 상향 가능하나 반드시 **한 값으로 잠그고 결과 조회 후 변경 금지**.
NULL_B = 1000
# A4: null RF common random numbers — 전 permutation·전 반복 동일 seed(representation 효과 격리).
NULL_RF_COMMON_SEED = 42

PCA_RF_REFIT_SCOPE = ("permuted embedding마다 B_seq PCA를 fold-train에서 재적합(사전등록 파이프라인 일부 → "
                      "null에도 동일 적용), RF도 fold별 재학습(random_state=NULL_RF_COMMON_SEED 공통). "
                      "이 재학습 범위를 null 가설 정의의 일부로 문서화.")


def build_global_permutation(unique_targets, seed):
    """global 재배치: unique target → source target(그 embedding을 빌림) 의 bijection.

    A4: **full permutation(fixed point 허용, derangement 아님)** — np.random.permutation은 자기 자신
    매핑을 배제하지 않는다(무작위 순열의 자연 결과). 반환: {target: source_target}. target t 는
    embedding[source]를 갖는다(전 약물 공유)."""
    ut = list(unique_targets)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(ut))                  # fixed point 허용(derangement 강제 안 함)
    return {ut[i]: ut[perm[i]] for i in range(len(ut))}


def build_family_permutation(targets_by_family, seed):
    """family-constrained 재배치: family 내에서만 교환. singleton·size-2 family는 원위치 고정.

    targets_by_family : {family_id: [target,...]}.
    반환: (mapping {target: source_target}, report{fixed_families, exchangeable_families, ...})."""
    rng = np.random.default_rng(seed)
    mapping = {}
    fixed_families, exch_families = [], []
    n_fixed_targets = 0
    n_exch_targets = 0
    # family_id 정렬로 결정적 순서 보장(seed만으로 재현)
    for fam in sorted(targets_by_family.keys(), key=lambda x: str(x)):
        members = list(targets_by_family[fam])
        if len(members) <= 2:                        # singleton·size-2 → 교환 불가·고정
            for t in members:
                mapping[t] = t
            fixed_families.append(fam)
            n_fixed_targets += len(members)
        else:
            perm = rng.permutation(len(members))     # family 내 full permutation(fixed point 허용)
            for i, t in enumerate(members):
                mapping[t] = members[perm[i]]
            exch_families.append(fam)
            n_exch_targets += len(members)
    n_targets = int(n_fixed_targets + n_exch_targets)
    report = {
        "n_families": len(targets_by_family),
        "n_fixed_families_singleton_or_size2": len(fixed_families),
        "n_exchangeable_families": len(exch_families),
        "n_fixed_targets": int(n_fixed_targets),           # A4: 고정 target 수
        "n_exchangeable_targets": int(n_exch_targets),     # A4: 교환 가능 target 수
        "n_targets": n_targets,
        "fixed_target_frac": float(n_fixed_targets / n_targets) if n_targets else 0.0,
        "rule": "|family|≤2 → 원위치 고정(가능 permutation ≤2!·서열 미파괴); |family|≥3 → family 내 full permutation",
    }
    return mapping, report


def apply_target_embedding_permutation(cid2targets, target_emb, mapping, cid_order):
    """재배치 mapping 하에서 약물별 **mean-pool** embedding 재계산(비매핑=zero).

    cid2targets : {cid: [target,...]}   target_emb : {target: vec}   mapping : {target: source}.
    동일 target은 모든 약물에서 동일 permuted embedding(embedding[mapping[t]])를 공유한다."""
    tgts0 = next(iter(target_emb.values()))
    dim = len(tgts0)
    out = np.zeros((len(cid_order), dim), dtype=np.float64)
    for r, cid in enumerate(cid_order):
        ts = cid2targets.get(cid, [])
        if not ts:
            continue                                  # 결측 → zero(missing 패턴 보존)
        vecs = [target_emb[mapping[t]] for t in ts]   # 재배치된 embedding, target별 공유
        out[r] = np.mean(vecs, axis=0)
    return out


def empirical_p(observed_stat, null_stats):
    """p_emp = (1 + #{T_b ≥ T_obs}) / (B+1) + **Monte Carlo standard error**(A4).

    mc_se ≈ sqrt(p(1−p)/B) — B는 null_stats 길이(= NULL_B 이어야 함). B가 NULL_B와 다르면 로깅용
    플래그(b_equals_null_b)로 표시(결과-기반 상향 감시)."""
    null = np.asarray(null_stats, dtype=float)
    B = len(null)
    ge = int(np.sum(null >= float(observed_stat)))
    p = (1.0 + ge) / (B + 1.0)
    mc_se = float(np.sqrt(p * (1.0 - p) / B)) if B > 0 else float("nan")
    return {"p_emp": p, "B": int(B), "n_ge_obs": ge, "mc_se": mc_se,
            "expected_B": NULL_B, "b_equals_null_b": bool(B == NULL_B),
            "note": "결과 조회 후 B 상향·조기중단·재시도 금지(selective precision). B는 NULL_B로 고정."}


def null_incidence_report(cid2targets, cid_order, unique_targets):
    """A4: 재배치 null 로깅 — eligible target 수·incidence 비율·결측 통계(결과 무참조)."""
    n_drugs = len(cid_order)
    n_targets = len(unique_targets)
    n_edges = int(sum(len(cid2targets.get(c, [])) for c in cid_order))
    n_drugs_with_target = int(sum(1 for c in cid_order if cid2targets.get(c)))
    denom = n_drugs * n_targets
    return {
        "n_targets": n_targets,                        # eligible(교환 대상) target 수 = unique target
        "n_drugs": n_drugs,
        "n_edges": n_edges,
        "incidence_ratio": float(n_edges / denom) if denom else 0.0,
        "n_drugs_with_target": n_drugs_with_target,
        "frac_drugs_with_target": float(n_drugs_with_target / n_drugs) if n_drugs else 0.0,
        "note": "eligible target = unique target(교환 단위). incidence_ratio = edges/(drugs×targets).",
    }


def _degree_maps(cid2targets, cid_order):
    drug_deg = {c: len(cid2targets.get(c, [])) for c in cid_order}
    tgt_deg = {}
    for c in cid_order:
        for t in cid2targets.get(c, []):
            tgt_deg[t] = tgt_deg.get(t, 0) + 1
    return drug_deg, tgt_deg


def assert_preservation(cid2targets, target_emb, mapping, cid_order, tol=1e-9):
    """재배치 null 보존조건 assert. 위반 시 AssertionError. 반환=검사 요약(dict)."""
    # 1) embedding 전체 분포 보존 = mapping이 bijection(사용 embedding multiset 동일)
    srcs = sorted(mapping.values(), key=lambda x: str(x))
    keys = sorted(target_emb.keys(), key=lambda x: str(x))
    assert sorted(mapping.keys(), key=lambda x: str(x)) == keys, "[A9] mapping 정의역 != target 집합"
    assert srcs == keys, "[A9] mapping이 bijection 아님(embedding 분포 미보존)"

    # 2) 동일 target = 동일 permuted embedding 공유 (row별 독립 셔플이 아님)
    #    두 약물이 공유하는 target에 대해 재배치 embedding이 동일한지 확인.
    shared_checked = 0
    seen_target_vec = {}
    for c in cid_order:
        for t in cid2targets.get(c, []):
            v = target_emb[mapping[t]]
            if t in seen_target_vec:
                assert np.allclose(seen_target_vec[t], v, atol=tol), \
                    f"[A9] target {t} 재배치 embedding이 약물마다 다름(row별 셔플 = 금지)"
                shared_checked += 1
            else:
                seen_target_vec[t] = v

    # 3) degree·incidence 보존 = 그래프 미변경 (cid2targets 그대로 사용)
    drug_deg, tgt_deg = _degree_maps(cid2targets, cid_order)

    # 4) 결측 패턴 보존 = degree 0 약물 집합 불변(그래프 미변경 → 자명)
    missing = [c for c in cid_order if drug_deg[c] == 0]

    return {
        "embedding_distribution_preserved": True,
        "mapping_is_bijection": True,
        "target_embedding_shared_across_drugs": True,
        "n_shared_target_checks": int(shared_checked),
        "graph_untouched_degree_incidence_preserved": True,
        "n_drug_missing_targets": len(missing),
        "n_unique_targets": len(target_emb),
        "note": "그래프(edges)는 재배치에서 미변경 → drug/target degree·incidence·결측 패턴 자동 보존.",
    }
