#!/usr/bin/env python3
"""fetch_m1b_covariates.py — (A) 1회 캐시 확장: M1b 공변량 소스 수집 (교수님 승인, 등록-중립).

근거·설계(임의 변경 금지):
  docs/30_preregistration_OSF_clean.md §4(M1b 공변량 리스트)·§13(실행순서),
  docs/31(A-2·A-3 gap: mechanism/confidence/연도 미수집), docs/32(B_m1b 보류 사유),
  교수님 승인(2026-07-24 안건1=A): "기존 매핑된 chembl_id/target에 대해서만" 아래를 1회 수집.

수집 범위(§4-A, 등록-중립 — 새 표적·분자 추가 금지·재매핑 금지·라벨/구조/split 무접근):
  1) /mechanism (molecule_chembl_id__in 배치): action_type, mechanism_of_action, target_chembl_id
     → mechanism-target 수·action 계열.
  2) assay confidence_score(0–9): pchembl activity의 assay_chembl_id(활동캐시엔 없음 → only= 확장·배치
     재수집), assay endpoint에서 confidence_score 보충 → 약물별 mean/max.
  3) molecule first_approval(승인연도): molecule_chembl_id__in 배치, 약물별.
  + pchembl-strength(05b, mean/max): 네트워크 불요(교차확인용).

⚙️ EBI 요청 최소화: 전 endpoint를 molecule_chembl_id__in / assay_chembl_id__in **배치**로 수집
   (per-drug 순회 대비 요청 ~10배 절감; EBI 기본 지연 ~3s/req 완화). 결정적 캐시(coverage_mapping._cache/).

무결성:
  - **기존 chembl_id(02_chembl matched=1, 943개)에 한정.** 새 표적/분자/재매핑 없음.
  - 라벨·분자셋·구조·split·mean-pool·Morgan 무접근. data/raw 무수정.
  - 결측(승인연도·confidence)은 **날조 금지** → missing 플래그 + 0 대치, 커버리지 리포트.
  - 결정적: 모든 요청 JSON 캐시, 정렬·집계·배치 순서 고정. 확증 split(seed 201~205) 무생성·무조회.

산출:
  data/processed/target_mapping/08_m1b_covariates.csv
  data/processed/target_mapping/_m1b_covariate_stats.json  (커버리지 리포트)
  + _cache/ 신규 요청 JSON(결정적)

실행: .venv/bin/python3 v3_Multimodal/src/fetch_m1b_covariates.py
"""
from __future__ import annotations
import os
import sys
import json
import statistics as st
import urllib.parse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coverage_mapping as cm  # noqa: E402  (cache-first HTTP + CSV 유틸 재사용)

OUT = cm.OUTDIR
F_08 = os.path.join(OUT, "08_m1b_covariates.csv")
F_STATS = os.path.join(OUT, "_m1b_covariate_stats.json")

MOL_BATCH = 50    # mechanism / molecule __in 배치
ACT_BATCH = 20    # activity __in 배치(분자당 활동 다수 → 페이지 폭주 방지)
ASSAY_BATCH = 100  # assay confidence __in 배치


def opath(name):
    return os.path.join(OUT, name)


def qin(ids):
    return urllib.parse.quote(",".join(ids), safe="")


def load_matched():
    """02_chembl matched=1 → cid(int)→chembl_id, chembl_id→[cid] (정렬)."""
    rows = cm.read_csv(opath("02_chembl.csv"))
    cid2ch, ch2cids = {}, defaultdict(list)
    for r in rows:
        if r["matched"] == "1" and r["chembl_id"]:
            cid = int(r["cid"])
            cid2ch[cid] = r["chembl_id"]
            ch2cids[r["chembl_id"]].append(cid)
    return cid2ch, ch2cids


def fetch_mechanisms(chembls):
    """mechanism (batch) → {chembl_id: (mech_target set, action set, present)}."""
    mt = {ch: set() for ch in chembls}
    ac = {ch: set() for ch in chembls}
    present = {ch: False for ch in chembls}
    ids = sorted(chembls)
    for i in range(0, len(ids), MOL_BATCH):
        batch = ids[i:i + MOL_BATCH]
        recs = cm._paged(
            f"{cm.CHEMBL}/mechanism?molecule_chembl_id__in={qin(batch)}"
            f"&only=molecule_chembl_id,target_chembl_id,action_type,mechanism_of_action&format=json",
            key="mechanisms", cap_pages=10)
        for m in recs:
            ch = m.get("molecule_chembl_id")
            if ch not in mt:
                continue
            present[ch] = True
            t = m.get("target_chembl_id")
            if t:
                mt[ch].add(t)
            a = m.get("action_type")
            if a:
                ac[ch].add(a)
        print(f"    mechanism batch {i//MOL_BATCH+1}/{-(-len(ids)//MOL_BATCH)}", flush=True)
    return mt, ac, present


def fetch_activities(chembls):
    """pchembl activity (batch, paged) → {chembl_id: (n_records, binding_target set, assay set)}, all_assays."""
    n_rec = {ch: 0 for ch in chembls}
    bt = {ch: set() for ch in chembls}
    asy = {ch: set() for ch in chembls}
    all_assays = set()
    ids = sorted(chembls)
    for i in range(0, len(ids), ACT_BATCH):
        batch = ids[i:i + ACT_BATCH]
        recs = cm._paged(
            f"{cm.CHEMBL}/activity?molecule_chembl_id__in={qin(batch)}&pchembl_value__isnull=false"
            f"&only=molecule_chembl_id,target_chembl_id,assay_chembl_id&format=json",
            key="activities", cap_pages=80)
        for a in recs:
            ch = a.get("molecule_chembl_id")
            if ch not in n_rec:
                continue
            n_rec[ch] += 1
            t = a.get("target_chembl_id")
            if t:
                bt[ch].add(t)
            asyid = a.get("assay_chembl_id")
            if asyid:
                asy[ch].add(asyid)
                all_assays.add(asyid)
        print(f"    activity batch {i//ACT_BATCH+1}/{-(-len(ids)//ACT_BATCH)}  누적 assay {len(all_assays)}", flush=True)
    return n_rec, bt, asy, all_assays


def fetch_assay_confidence(assay_ids):
    """assay_chembl_id__in 배치 → {assay_chembl_id: confidence_score(int|None)}."""
    conf = {}
    ids = sorted(assay_ids)
    for i in range(0, len(ids), ASSAY_BATCH):
        batch = ids[i:i + ASSAY_BATCH]
        url = (f"{cm.CHEMBL}/assay?assay_chembl_id__in={qin(batch)}"
               f"&only=assay_chembl_id,confidence_score&format=json&limit=1000")
        data = cm.http_get_json(url)
        if data:
            for a in data.get("assays", []):
                conf[a["assay_chembl_id"]] = a.get("confidence_score")
        if (i // ASSAY_BATCH + 1) % 20 == 0 or i + ASSAY_BATCH >= len(ids):
            print(f"    assay confidence {min(i+ASSAY_BATCH,len(ids))}/{len(ids)}", flush=True)
    return conf


def fetch_first_approval(chembls):
    """molecule_chembl_id__in 배치 → {chembl_id: first_approval(int|None)}."""
    appr = {}
    ids = sorted(chembls)
    for i in range(0, len(ids), MOL_BATCH):
        batch = ids[i:i + MOL_BATCH]
        url = (f"{cm.CHEMBL}/molecule?molecule_chembl_id__in={qin(batch)}"
               f"&only=molecule_chembl_id,first_approval&format=json&limit=1000")
        data = cm.http_get_json(url)
        if data:
            for m in data.get("molecules", []):
                appr[m["molecule_chembl_id"]] = m.get("first_approval")
    return appr


def load_pchembl_by_chembl():
    """05b → chembl_id → [pchembl_median] (네트워크 불요, 교차확인용)."""
    pch = defaultdict(list)
    for r in cm.read_csv(opath("05b_affinity_values.csv")):
        try:
            pch[r["chembl_id"]].append(float(r["pchembl_median"]))
        except (ValueError, KeyError):
            continue
    return pch


def main():
    print("[fetch_m1b] (A) 1회 캐시 확장 — 기존 chembl_id 한정 mechanism·confidence·first_approval (배치)")
    print("[무결성] 새 표적/분자 추가·재매핑 없음. 라벨/구조/split/mean-pool/Morgan 무접근. 확증 split 무조회.")
    cid2ch, ch2cids = load_matched()
    chembls = sorted(set(cid2ch.values()))
    print(f"[data] matched chembl_id {len(chembls)} (약물 cid {len(cid2ch)})", flush=True)

    pch = load_pchembl_by_chembl()

    print("[1/4] mechanism (batch)"); mech_targets, mech_actions, mech_present = fetch_mechanisms(chembls)
    print("[2/4] activities (batch, paged)"); n_records, binding_targets, drug_assays, all_assays = fetch_activities(chembls)
    print(f"[3/4] assay confidence — uniq assay {len(all_assays)}"); assay_conf = fetch_assay_confidence(all_assays)
    n_conf_nonnull = sum(1 for v in assay_conf.values() if v is not None)
    print(f"    confidence 수집 {len(assay_conf)} (non-null {n_conf_nonnull})", flush=True)
    print("[4/4] first_approval (batch)"); approval = fetch_first_approval(chembls)
    n_appr = sum(1 for v in approval.values() if v is not None)
    print(f"    승인연도 보유 {n_appr}/{len(chembls)}", flush=True)

    # ── per-drug 집계 → 08 CSV (cid 정렬, matched cid만) ──
    header = ["cid", "chembl_id", "evidence_count", "mechanism_target_n", "binding_target_n",
              "action_types", "confidence_mean", "confidence_max", "first_approval_year",
              "pchembl_mean", "pchembl_max",
              "confidence_missing", "year_missing", "pchembl_missing", "mechanism_missing"]
    rows = []
    cov = {"confidence_present": 0, "year_present": 0, "pchembl_present": 0,
           "mechanism_present": 0, "binding_present": 0}
    for cid in sorted(cid2ch):
        ch = cid2ch[cid]
        confs = [assay_conf.get(a) for a in drug_assays[ch]]
        confs = [c for c in confs if c is not None]
        conf_missing = 0 if confs else 1
        c_mean = st.mean(confs) if confs else 0.0
        c_max = float(max(confs)) if confs else 0.0
        yr = approval.get(ch)
        year_missing = 0 if (yr is not None and yr != "") else 1
        year_val = int(yr) if not year_missing else 0
        pvals = pch.get(ch, [])
        pch_missing = 0 if pvals else 1
        p_mean = st.mean(pvals) if pvals else 0.0
        p_max = float(max(pvals)) if pvals else 0.0
        mn = len(mech_targets[ch])
        acts = ";".join(sorted(mech_actions[ch]))
        mech_missing = 0 if mech_present[ch] else 1
        bn = len(binding_targets[ch])

        cov["confidence_present"] += (conf_missing == 0)
        cov["year_present"] += (year_missing == 0)
        cov["pchembl_present"] += (pch_missing == 0)
        cov["mechanism_present"] += (mech_missing == 0)
        cov["binding_present"] += (bn > 0)

        rows.append([cid, ch, n_records[ch], mn, bn, acts,
                     f"{c_mean:.4f}", f"{c_max:.1f}", year_val,
                     f"{p_mean:.4f}", f"{p_max:.4f}",
                     conf_missing, year_missing, pch_missing, mech_missing])
    rows.sort(key=lambda x: int(x[0]))
    cm.write_csv(F_08, header, rows)

    nD = len(cid2ch)
    stats = {
        "n_drugs_matched": nD,
        "coverage": {k: {"n": v, "pct": round(100.0 * v / nD, 1)} for k, v in cov.items()},
        "missing_rate": {
            "confidence": round(100.0 * (nD - cov["confidence_present"]) / nD, 1),
            "year": round(100.0 * (nD - cov["year_present"]) / nD, 1),
            "pchembl": round(100.0 * (nD - cov["pchembl_present"]) / nD, 1),
            "mechanism": round(100.0 * (nD - cov["mechanism_present"]) / nD, 1),
        },
        "assay_confidence": {"uniq_assays": len(all_assays),
                             "fetched": len(assay_conf), "non_null": n_conf_nonnull},
        "first_approval_with_year": n_appr,
        "note": ("network=§4-A only (mechanism/confidence/first_approval for existing 943 chembl_id, batched). "
                 "no new targets/molecules, no re-mapping, no label/structure/split access. "
                 "missing = flag+0 impute (no fabrication)."),
        "source_endpoints": {
            "mechanism": f"{cm.CHEMBL}/mechanism?molecule_chembl_id__in=..&only=target_chembl_id,action_type,mechanism_of_action",
            "confidence": f"{cm.CHEMBL}/assay?assay_chembl_id__in=..&only=assay_chembl_id,confidence_score",
            "first_approval": f"{cm.CHEMBL}/molecule?molecule_chembl_id__in=..&only=molecule_chembl_id,first_approval",
            "pchembl_strength": "05b_affinity_values.csv (no network)",
        },
    }
    json.dump(stats, open(F_STATS, "w"), indent=2, ensure_ascii=False)
    print(f"[stats] {os.path.relpath(F_STATS, cm.ROOT)}")
    print(f"[coverage] confidence {cov['confidence_present']}/{nD} "
          f"({100*cov['confidence_present']/nD:.1f}%), year {cov['year_present']}/{nD} "
          f"({100*cov['year_present']/nD:.1f}%), mechanism {cov['mechanism_present']}/{nD} "
          f"({100*cov['mechanism_present']/nD:.1f}%), pchembl {cov['pchembl_present']}/{nD}")
    print("[완료] 08_m1b_covariates.csv 생성 (matched cid 정렬, 날조 0=missing 플래그).")


if __name__ == "__main__":
    main()
