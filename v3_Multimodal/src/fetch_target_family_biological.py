#!/usr/bin/env python3
"""fetch_target_family_biological.py — (A) P-FAM **생물학적 family** 소싱 (교수님 승인 2026-07-24).

근거·설계(임의 변경 금지):
  docs/30_preregistration_OSF_clean.md §4(P-FAM = target **family/domain** multi-hot;
    "UniProt family·Pfam/InterPro·ChEMBL class")·§9(family 정의 다중; UniRef50 primary + Pfam/InterPro/ChEMBL class = sensitivity),
  docs/33(이탈 로그)·docs/34(부분 동결).
  교수님 승인(2026-07-24): P-FAM family를 **생물학적 family로 재소싱**(자체 mmseqs 50% 클러스터는
    near-identity라 표적 79.3%가 싱글톤 → coarse-family 통제 미달). 자체클러스터(09)는 §9 sensitivity로 보존.

방법(결정적, §3-A 승인 범위 네트워크만 — 기존 target_chembl_id/uniprot의 class·Pfam/InterPro만):
  primary = **ChEMBL protein classification**:
    - 기존 human single-protein 표적(06_targets_human.csv)의 component_id로
      `/target_component?component_id__in=..&only=component_id,protein_classifications` 배치 수집(leaf protein_class_id).
    - `/protein_classification?limit=1000` 전체 트리(class_level·pref_name·parent_id) 1회 수집 → parent 체인.
    - **coarse 레벨을 코드에 사전고정**(TARGET_LEVEL): leaf에서 부모체인을 올라가 class_level==TARGET_LEVEL 조상을
      family로. leaf가 그보다 얕으면 leaf를 사용. (예: L2 = Kinase / GPCR / Ion channel 수준)
  fallback = **UniProt Pfam/InterPro**(네트워크 0 — 기존 캐시된 target JSON의 target_component_xrefs 재사용):
    - ChEMBL class 결측 표적은 Pfam(PFxxxxx) → 없으면 InterPro(IPRxxxxxx) xref로 family 보충.
    - 그래도 결측이면 자기 uniprot을 단독 family(SINGLETON)로 두되 **missing_flag=1 + 커버리지 기록**(날조 금지).

granularity 게이트(**사후조정 아님·라벨/성능 무참조** — 오직 coverage·싱글톤%):
  - TARGET_LEVEL(=PRIMARY_LEVEL)에서 family/target·싱글톤% 산출. 현 자체클러스터 79.3%(715/902) 대비 실질 coarse 검증.
  - 여전히 near-identity(family 싱글톤% ≥ SINGLETON_GATE)면 **한 단계 coarse(더 낮은 class level)**로 조정 후 재기록.
  - 커버리지(=biological family 부여 비율) 목표 ≥~85%. 이 선택은 어떤 라벨/성능도 보지 않는다.

무결성:
  - 라벨·분자셋·구조·split·mean-pool·Morgan 무접근. **새 표적/분자 추가·재매핑·재다운로드 없음.**
  - 네트워크 = §3-A(기존 표적의 protein_classification / target_component class, 전체 class 트리)만.
    Pfam/InterPro는 캐시된 target JSON xref 재사용(네트워크 0). DrugBank·mock 없음. 확증 split(seed 201~205) 무생성·무조회.
  - 결정적: 정렬·배치 순서 고정, 모든 ChEMBL 요청 JSON 캐시(coverage_mapping._cache/). 09(자체클러스터) 덮어쓰기 없음(추가만).

산출:
  data/processed/target_mapping/10_target_family_biological.csv
    (uniprot, target_chembl_id, family_id, family_name, family_source[chembl_class/pfam/interpro/singleton], level, missing_flag)
  data/processed/target_mapping/_target_family_biological_stats.json  (레벨결정·커버리지·싱글톤% 대비)
  + _cache/ 신규 요청 JSON(target_component·protein_classification)

실행: .venv/bin/python3 v3_Multimodal/src/fetch_target_family_biological.py
"""
from __future__ import annotations
import os
import sys
import csv
import json
import hashlib
import urllib.parse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coverage_mapping as cm  # noqa: E402  (cache-first HTTP + CSV 유틸 재사용)

OUT = cm.OUTDIR
CACHE = cm.CACHEDIR
CHEMBL = cm.CHEMBL
F_HUMAN = os.path.join(OUT, "06_targets_human.csv")
F_10 = os.path.join(OUT, "10_target_family_biological.csv")
F_STATS = os.path.join(OUT, "_target_family_biological_stats.json")

COMP_BATCH = 40          # target_component?component_id__in 배치
# ── 동결 granularity 규칙 (사전고정, 라벨/성능 무참조) ──
PRIMARY_LEVEL = 2        # ChEMBL protein class 목표 레벨(L2 = Kinase/GPCR/Ion channel 수준)
FALLBACK_LEVEL = 1       # 싱글톤% 게이트 초과 시 한 단계 coarse(L1 = Enzyme/Membrane receptor/…)
SINGLETON_GATE = 0.60    # family 싱글톤% ≥ 이 값이면 FALLBACK_LEVEL로 조정(자체클러스터 79.3% 대비)
SELFCLUST_SINGLETON_FRAC = 715 / 902  # 자체 mmseqs 50% 클러스터 기준(_family_cluster_stats.json)


def cpath(url):
    return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest()[:20] + ".json")


def qin(ids):
    return urllib.parse.quote(",".join(str(i) for i in ids), safe="")


# ═══════════════════════════════════════════════════════════════════════════
# 1) 표적 컴포넌트·xref (캐시된 target JSON 재사용 — 네트워크 0)
# ═══════════════════════════════════════════════════════════════════════════
def load_targets():
    """06 human 표적 → uni→tid, uni→component_id, uni→Pfam/InterPro xref(캐시 target JSON에서)."""
    rows = list(csv.DictReader(open(F_HUMAN)))
    uni2tid = {}
    for r in rows:
        if r["uniprot"] and r["target_chembl_id"]:
            uni2tid.setdefault(r["uniprot"], r["target_chembl_id"])
    unis = sorted(uni2tid)
    uni2comp, uni2pfam, uni2interpro, missing_target_json = {}, {}, {}, []
    for u in unis:
        tid = uni2tid[u]
        p = cpath(f"{CHEMBL}/target/{tid}?format=json")
        if not os.path.exists(p):
            missing_target_json.append(u)
            continue
        d = json.load(open(p))
        for c in d.get("target_components", []):
            if c.get("accession") != u:
                continue
            if c.get("component_id"):
                uni2comp[u] = c["component_id"]
            pf, ipr = [], []
            for x in (c.get("target_component_xrefs") or []):
                if x.get("xref_src_db") == "Pfam" and x.get("xref_id"):
                    pf.append((x["xref_id"], x.get("xref_name") or ""))
                elif x.get("xref_src_db") == "InterPro" and x.get("xref_id"):
                    ipr.append((x["xref_id"], x.get("xref_name") or ""))
            if pf:
                uni2pfam[u] = sorted(pf)[0]        # 결정적 선택(정렬 첫번째)
            if ipr:
                uni2interpro[u] = sorted(ipr)[0]
    return uni2tid, unis, uni2comp, uni2pfam, uni2interpro, missing_target_json


# ═══════════════════════════════════════════════════════════════════════════
# 2) ChEMBL protein classification (§3-A 네트워크): component → leaf class, 전체 트리
# ═══════════════════════════════════════════════════════════════════════════
def fetch_component_classes(comp_ids):
    """target_component?component_id__in 배치 → {component_id: [protein_class_id, ...]}."""
    out = defaultdict(list)
    ids = sorted(set(comp_ids))
    for i in range(0, len(ids), COMP_BATCH):
        batch = ids[i:i + COMP_BATCH]
        url = (f"{CHEMBL}/target_component?component_id__in={qin(batch)}"
               f"&only=component_id,protein_classifications&format=json&limit=1000")
        data = cm.http_get_json(url)
        if data:
            for c in data.get("target_components", []):
                cid = c.get("component_id")
                for pc in (c.get("protein_classifications") or []):
                    pid = pc.get("protein_classification_id")
                    if pid is not None:
                        out[cid].append(pid)
        print(f"    component_class batch {i//COMP_BATCH+1}/{-(-len(ids)//COMP_BATCH)}", flush=True)
    return out


def fetch_class_tree():
    """전체 protein_classification 트리 → {pid: {level, name, parent}}."""
    recs = cm._paged(
        f"{CHEMBL}/protein_classification?format=json", key="protein_classifications", cap_pages=20)
    tree = {}
    for r in recs:
        pid = r["protein_class_id"]
        tree[pid] = {"level": r.get("class_level"), "name": r.get("pref_name") or "",
                     "parent": r.get("parent_id")}
    return tree


def ancestor_at_level(leaf_pid, tree, level):
    """leaf에서 parent 체인을 올라가 class_level==level 조상 반환. leaf가 더 얕으면 leaf 반환."""
    node = leaf_pid
    seen = set()
    chosen = leaf_pid          # 기본 = leaf(체인에 목표 레벨 없을 때)
    while node in tree and node not in seen:
        seen.add(node)
        lv = tree[node]["level"]
        if lv == level:
            return node
        if lv is not None and lv < level:
            # 이미 목표보다 얕음 → 더 못 내려감. 지금까지 본 가장 깊은(=시작 leaf) 사용.
            break
        node = tree[node]["parent"]
    return chosen


# ═══════════════════════════════════════════════════════════════════════════
# 3) family 배정 + granularity 계산
# ═══════════════════════════════════════════════════════════════════════════
def assign_families(unis, uni2comp, comp_classes, tree, uni2pfam, uni2interpro, level):
    """각 표적 uniprot → [(family_id, family_name, source, class_level, missing_flag)] (multi-hot OR).

    우선순위: ChEMBL class(레벨 조상) → Pfam → InterPro → singleton(자기 uniprot)."""
    assign = {}
    for u in unis:
        comp = uni2comp.get(u)
        leaves = comp_classes.get(comp, []) if comp is not None else []
        fams = []
        seen = set()
        for leaf in sorted(set(leaves)):
            if leaf not in tree:
                continue
            anc = ancestor_at_level(leaf, tree, level)
            fid = f"CHEMBL_CLASS:{anc}"
            if fid in seen:
                continue
            seen.add(fid)
            fams.append((fid, tree[anc]["name"], "chembl_class", tree[anc]["level"], 0))
        if fams:
            assign[u] = fams
            continue
        # fallback (네트워크 0 — 캐시 xref)
        if u in uni2pfam:
            pf, nm = uni2pfam[u]
            assign[u] = [(f"PFAM:{pf}", nm, "pfam", "", 0)]
        elif u in uni2interpro:
            ipr, nm = uni2interpro[u]
            assign[u] = [(f"INTERPRO:{ipr}", nm, "interpro", "", 0)]
        else:
            assign[u] = [(f"SINGLETON:{u}", "", "singleton", "", 1)]
    return assign


def granularity(assign):
    """family/target·싱글톤family%·coverage(biological 부여 비율) 산출."""
    fam_targets = defaultdict(set)
    src_targets = defaultdict(int)     # per-target 대표 source(첫 family source)
    for u, fams in assign.items():
        for (fid, nm, src, lv, mf) in fams:
            fam_targets[fid].add(u)
        # per-target source = 그 표적의 (동일)source (fallback은 단일, chembl_class는 전부 동일 소스)
        src_targets[fams[0][2]] += 1
    n_targets = len(assign)
    n_families = len(fam_targets)
    singleton_families = sum(1 for s in fam_targets.values() if len(s) == 1)
    covered = n_targets - src_targets.get("singleton", 0)
    return {
        "n_targets": n_targets,
        "n_families": n_families,
        "family_per_target": round(n_families / n_targets, 4) if n_targets else 0.0,
        "singleton_families": singleton_families,
        "singleton_family_frac": round(singleton_families / n_families, 4) if n_families else 0.0,
        "coverage_biological": round(covered / n_targets, 4) if n_targets else 0.0,
        "source_breakdown": dict(sorted(src_targets.items())),
        "top_family_sizes": sorted((len(s) for s in fam_targets.values()), reverse=True)[:12],
    }


# ═══════════════════════════════════════════════════════════════════════════
def main():
    print("[fetch_fam_bio] (A) P-FAM 생물학적 family — ChEMBL protein class(primary) + Pfam/InterPro(fallback)")
    print("[무결성] 네트워크 = §3-A(기존 표적 protein_classification/target_component class + 전체 class 트리)만. "
          "Pfam/InterPro=캐시 xref 재사용(네트워크 0). 라벨/구조/split/mean-pool/Morgan 무접근. 확증 split 무조회.")

    uni2tid, unis, uni2comp, uni2pfam, uni2interpro, missing_json = load_targets()
    print(f"[data] human single-protein 표적 uniprot {len(unis)} | component_id 확보 {len(uni2comp)} | "
          f"target JSON 결측 {len(missing_json)}")
    print(f"[fallback 후보] Pfam xref {len(uni2pfam)} · InterPro xref {len(uni2interpro)} (캐시)")

    print("[1/2] ChEMBL protein_classification 트리 (전체)")
    tree = fetch_class_tree()
    print(f"    class 트리 {len(tree)} 노드")
    print("[2/2] target_component protein_classifications (배치)")
    comp_classes = fetch_component_classes([uni2comp[u] for u in unis if u in uni2comp])
    n_with_class = sum(1 for u in unis if comp_classes.get(uni2comp.get(u)))
    print(f"    ChEMBL class 보유 표적 {n_with_class}/{len(unis)}")

    # ── granularity 게이트 (라벨/성능 무참조) ──
    assign_primary = assign_families(unis, uni2comp, comp_classes, tree, uni2pfam, uni2interpro, PRIMARY_LEVEL)
    g_primary = granularity(assign_primary)
    assign_fallback = assign_families(unis, uni2comp, comp_classes, tree, uni2pfam, uni2interpro, FALLBACK_LEVEL)
    g_fallback = granularity(assign_fallback)
    print(f"[granularity] L{PRIMARY_LEVEL}: families {g_primary['n_families']} "
          f"싱글톤% {g_primary['singleton_family_frac']:.3f} coverage {g_primary['coverage_biological']:.3f}")
    print(f"[granularity] L{FALLBACK_LEVEL}: families {g_fallback['n_families']} "
          f"싱글톤% {g_fallback['singleton_family_frac']:.3f} coverage {g_fallback['coverage_biological']:.3f}")
    print(f"[baseline]   자체클러스터 mmseqs 50%: 싱글톤% {SELFCLUST_SINGLETON_FRAC:.3f} (715/902)")

    # 사전 규칙: PRIMARY_LEVEL 싱글톤% ≥ GATE 면 FALLBACK_LEVEL 채택
    if g_primary["singleton_family_frac"] >= SINGLETON_GATE:
        chosen_level, assign, g = FALLBACK_LEVEL, assign_fallback, g_fallback
        gate_decision = (f"L{PRIMARY_LEVEL} 싱글톤% {g_primary['singleton_family_frac']:.3f} ≥ 게이트 {SINGLETON_GATE} "
                         f"→ 한 단계 coarse L{FALLBACK_LEVEL} 채택")
    else:
        chosen_level, assign, g = PRIMARY_LEVEL, assign_primary, g_primary
        gate_decision = (f"L{PRIMARY_LEVEL} 싱글톤% {g_primary['singleton_family_frac']:.3f} < 게이트 {SINGLETON_GATE} "
                         f"→ L{PRIMARY_LEVEL} 유지")
    print(f"[게이트 결정] {gate_decision} | 채택 level=L{chosen_level}")

    # ── 10 CSV 저장 (uniprot 정렬, target 다중 family 롱포맷) ──
    header = ["uniprot", "target_chembl_id", "family_id", "family_name",
              "family_source", "level", "missing_flag"]
    rows = []
    for u in unis:
        tid = uni2tid[u]
        for (fid, nm, src, lv, mf) in assign[u]:
            rows.append([u, tid, fid, nm, src, lv, mf])
    rows.sort(key=lambda x: (x[0], x[2]))
    cm.write_csv(F_10, header, rows)

    # ── 통계·매니페스트 ──
    stats = {
        "_doc": "P-FAM 생물학적 family 소싱 — 사전등록 §4/§9. 자체클러스터(09) 대체 primary, 09는 §9 sensitivity 보존.",
        "network_scope": "§3-A only: ChEMBL protein_classification(전체 트리) + target_component "
                         "(기존 component_id의 protein_classifications). Pfam/InterPro=캐시 target JSON xref(네트워크 0).",
        "chembl_source_endpoints": {
            "component_class": f"{CHEMBL}/target_component?component_id__in=..&only=component_id,protein_classifications",
            "class_tree": f"{CHEMBL}/protein_classification?format=json (class_level·pref_name·parent_id 전체 트리)",
            "pfam_interpro_fallback": "캐시된 /target/{tid} JSON의 target_component_xrefs (Pfam/InterPro; 네트워크 0)",
        },
        "granularity_rule": {"primary_level": PRIMARY_LEVEL, "fallback_level": FALLBACK_LEVEL,
                             "singleton_gate": SINGLETON_GATE,
                             "note": "라벨·성능 무참조. 오직 coverage·싱글톤%로 레벨 선택."},
        "gate_decision": gate_decision,
        "chosen_level": chosen_level,
        "n_targets": len(unis),
        "n_with_chembl_class": n_with_class,
        "granularity_primary_L%d" % PRIMARY_LEVEL: g_primary,
        "granularity_fallback_L%d" % FALLBACK_LEVEL: g_fallback,
        "granularity_chosen": g,
        "selfcluster_baseline": {
            "source": "_family_cluster_stats.json (mmseqs2 easy-cluster --min-seq-id 0.5)",
            "n_families": 902, "n_singletons": 715,
            "singleton_family_frac": round(SELFCLUST_SINGLETON_FRAC, 4),
            "family_per_target": round(902 / 1191, 4),
        },
        "coarser_than_selfcluster": {
            "singleton_frac_drop": round(SELFCLUST_SINGLETON_FRAC - g["singleton_family_frac"], 4),
            "family_per_target_drop": round(round(902 / 1191, 4) - g["family_per_target"], 4),
            "is_substantially_coarser": bool(
                g["singleton_family_frac"] < SELFCLUST_SINGLETON_FRAC and g["family_per_target"] < 902 / 1191),
        },
        "integrity": {
            "network_calls": "§3-A ChEMBL class only (deterministic cache)",
            "pfam_interpro_network": 0,
            "new_targets_or_molecules": 0, "remapping": False, "redownload": False,
            "labels_molset_structure_split_accessed": False,
            "selfcluster_09_overwritten": False,
            "fabricated_families": 0,
            "note": "결측=SINGLETON fallback + missing_flag=1(날조 0). 09(자체클러스터) 불변·보존.",
        },
    }
    json.dump(stats, open(F_STATS, "w"), indent=2, ensure_ascii=False)
    print(f"  ✅ {os.path.relpath(F_STATS, cm.ROOT)}")
    print(f"[완료] level=L{chosen_level} | families {g['n_families']} "
          f"싱글톤% {g['singleton_family_frac']:.3f} (자체클러스터 {SELFCLUST_SINGLETON_FRAC:.3f} 대비) "
          f"coverage {g['coverage_biological']:.3f} | source {g['source_breakdown']}")


if __name__ == "__main__":
    main()
