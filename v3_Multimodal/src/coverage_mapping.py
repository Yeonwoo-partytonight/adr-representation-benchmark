#!/usr/bin/env python3
"""coverage_mapping.py — v3 멀티모달(DrugBank-free) 표적 매핑 커버리지 측정.

목적(이 작업 범위): 확정 분자셋(1,092)에 대해
  PubChem SMILES → InChIKey → ChEMBL compound → target(UniProt) → 서열/친화도
매핑 **커버리지만** 측정한다. 모델 학습·ProtBERT 임베딩 계산은 범위가 아니다.

원칙(AGENTS.md/CLAUDE.md 가드레일):
  - 분자셋·라벨·split 불변. 기존 SMILES 재사용, PubChem 재다운로드 금지.
  - DrugBank 미사용. 공개 리소스만(ChEMBL EBI, UniProt EBI). BindingDB는 보조(가용 시).
  - 매핑 실패는 실패로 정직 보고. mock 금지.
  - 재현성: SEED 고정, 모든 요청 JSON 캐시(`_cache/`), 재시도/레이트리밋 준수, 중간 CSV 저장.

데이터 소스(공신력):
  - ChEMBL (EMBL-EBI) REST API — https://www.ebi.ac.uk/chembl/api/data/
  - UniProt (EMBL-EBI/SIB/PIR) REST — https://rest.uniprot.org/

사용:
    python v3_Multimodal/src/coverage_mapping.py --step all
    python v3_Multimodal/src/coverage_mapping.py --step all --limit 20   # 스모크 테스트
    python v3_Multimodal/src/coverage_mapping.py --step 1,2,3,4,5,6      # 개별 단계
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from collections import defaultdict

# ---------------------------------------------------------------------------
# 경로/상수
# ---------------------------------------------------------------------------
SEED = 42  # 결정적 처리(정렬/순서)용. 본 스크립트에 확률적 연산은 없음.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_PROC = os.path.join(ROOT, "data", "processed")
MASTER_X = os.path.join(DATA_PROC, "master_X.parquet")
OUTDIR = os.path.join(DATA_PROC, "target_mapping")
CACHEDIR = os.path.join(OUTDIR, "_cache")

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
UNIPROT = "https://rest.uniprot.org/uniprotkb"
UA = {"User-Agent": "DTI-ADR-v3-coverage/1.0 (academic; reproducibility run)"}

RATE_SLEEP = 0.2      # 요청 간 최소 간격(초). EBI 권장 부하 이하.
MAX_RETRY = 4         # 재시도 횟수
CHUNK_KEYS = 40       # STEP2 InChIKey 배치 크기


# ---------------------------------------------------------------------------
# HTTP: 캐시 + 재시도 + 레이트리밋
# ---------------------------------------------------------------------------
def _cache_path(url: str) -> str:
    h = hashlib.sha1(url.encode()).hexdigest()[:20]
    return os.path.join(CACHEDIR, h + ".json")


def http_get_json(url: str, timeout: int = 45):
    """GET → JSON dict. 파일 캐시 우선. 실패 시 지수 백오프 재시도.
    반환: (data|None). 네트워크/HTTP 오류로 최종 실패 시 None(정직 실패)."""
    cp = _cache_path(url)
    if os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            data = json.loads(raw)
            os.makedirs(CACHEDIR, exist_ok=True)
            with open(cp, "w") as f:
                json.dump(data, f)
            time.sleep(RATE_SLEEP)
            return data
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                # 자원 없음 = 확정 실패(재시도 무의미). 빈 결과로 캐시하지 않음.
                return None
            # 429/5xx 등은 백오프 후 재시도
            time.sleep(RATE_SLEEP * (2 ** attempt) + 0.5)
        except Exception as e:  # timeout, URLError 등
            last_err = f"{type(e).__name__}"
            time.sleep(RATE_SLEEP * (2 ** attempt) + 0.5)
    print(f"  [warn] GET 실패({last_err}): {url[:110]}", file=sys.stderr)
    return None


def http_get_text(url: str, timeout: int = 45):
    """GET → text(캐시). FASTA 등. 실패 시 None."""
    cp = _cache_path(url) + ".txt"
    if os.path.exists(cp):
        with open(cp) as f:
            return f.read()
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = r.read().decode("utf-8", "replace")
            os.makedirs(CACHEDIR, exist_ok=True)
            with open(cp, "w") as f:
                f.write(txt)
            time.sleep(RATE_SLEEP)
            return txt
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                return None
            time.sleep(RATE_SLEEP * (2 ** attempt) + 0.5)
        except Exception as e:
            last_err = f"{type(e).__name__}"
            time.sleep(RATE_SLEEP * (2 ** attempt) + 0.5)
    print(f"  [warn] GET(text) 실패({last_err}): {url[:110]}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# CSV 유틸
# ---------------------------------------------------------------------------
def write_csv(path: str, header: list[str], rows: list[list]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  ✅ {os.path.relpath(path, ROOT)}  ({len(rows)} rows)")


def read_csv(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# STEP 1 — SMILES → InChIKey (로컬 RDKit)
# ---------------------------------------------------------------------------
def step1(limit: int = 0):
    from rdkit import Chem
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    import pandas as pd

    df = pd.read_parquet(MASTER_X).sort_values("cid").reset_index(drop=True)
    if limit:
        df = df.head(limit)
    rows, ok_n = [], 0
    for _, r in df.iterrows():
        cid, smi = int(r["cid"]), str(r["smiles_canonical"])
        ik, ok = "", 0
        m = Chem.MolFromSmiles(smi)
        if m is not None:
            try:
                ik = Chem.MolToInchiKey(m)
                ok = 1 if ik else 0
            except Exception:
                ik, ok = "", 0
        ok_n += ok
        rows.append([cid, smi, ik, ok])
    write_csv(os.path.join(OUTDIR, "01_inchikey.csv"),
              ["cid", "smiles", "inchikey", "ok"], rows)
    print(f"  STEP1: InChIKey 성공 {ok_n}/{len(rows)}")
    return rows


# ---------------------------------------------------------------------------
# STEP 2 — InChIKey → ChEMBL compound (배치)
# ---------------------------------------------------------------------------
def step2():
    rows_in = read_csv(os.path.join(OUTDIR, "01_inchikey.csv"))
    keyed = [(r["cid"], r["inchikey"]) for r in rows_in if r["ok"] == "1" and r["inchikey"]]
    # inchikey→chembl_id (full InChIKey exact match, ChEMBL standard_inchi_key)
    ik2chembl: dict[str, str] = {}
    uniq_keys = sorted({ik for _, ik in keyed})
    for i in range(0, len(uniq_keys), CHUNK_KEYS):
        batch = uniq_keys[i:i + CHUNK_KEYS]
        q = urllib.parse.quote(",".join(batch), safe="")
        url = (f"{CHEMBL}/molecule?molecule_structures__standard_inchi_key__in={q}"
               f"&only=molecule_chembl_id,molecule_structures&format=json&limit=1000")
        data = http_get_json(url)
        if not data:
            continue
        for m in data.get("molecules", []):
            struct = m.get("molecule_structures") or {}
            ik = struct.get("standard_inchi_key")
            if ik and ik not in ik2chembl:
                ik2chembl[ik] = m["molecule_chembl_id"]
        print(f"    STEP2 batch {i//CHUNK_KEYS+1}/{-(-len(uniq_keys)//CHUNK_KEYS)}  누적매칭 {len(ik2chembl)}")

    rows, matched = [], 0
    for cid, ik in keyed:
        ch = ik2chembl.get(ik, "")
        m = 1 if ch else 0
        matched += m
        rows.append([cid, ik, ch, m])
    write_csv(os.path.join(OUTDIR, "02_chembl.csv"),
              ["cid", "inchikey", "chembl_id", "matched"], rows)
    print(f"  STEP2: ChEMBL 매칭 {matched}/{len(rows)}")
    return rows


# ---------------------------------------------------------------------------
# STEP 3 — compound → target(UniProt)  ★핵심 게이트
# ---------------------------------------------------------------------------
def _paged(url_base: str, key: str, cap_pages: int = 20):
    """ChEMBL 페이지네이션 순회. 결과 레코드 리스트 반환."""
    out = []
    url = url_base + "&limit=1000&offset=0"
    pages = 0
    while url and pages < cap_pages:
        data = http_get_json(url)
        if not data:
            break
        out.extend(data.get(key, []))
        meta = data.get("page_meta", {})
        nxt = meta.get("next")
        url = ("https://www.ebi.ac.uk" + nxt) if nxt else None
        pages += 1
    return out


def _resolve_target_uniprot(target_chembl_id: str):
    """ChEMBL target → [(uniprot, organism)] (SINGLE PROTEIN 성분의 accession).
    비단백질 표적(cell-line, tissue, unchecked 등)은 accession 없음 → 빈 리스트."""
    url = f"{CHEMBL}/target/{target_chembl_id}?format=json"
    data = http_get_json(url)
    if not data:
        return []
    organism = data.get("organism")
    ttype = data.get("target_type", "")
    accs = []
    for comp in data.get("target_components", []):
        acc = comp.get("accession")
        if acc:
            accs.append((acc, organism, ttype))
    return accs


def step3():
    rows_in = read_csv(os.path.join(OUTDIR, "02_chembl.csv"))
    matched = [(r["cid"], r["inchikey"], r["chembl_id"]) for r in rows_in if r["matched"] == "1"]

    # 1) 각 compound → target_chembl_id 집합 (mechanism=MoA + activity=bioactivity(pchembl))
    #    activity는 pchembl_value 보유(표준화 효력)만 사용 → 근거 있는 표적만.
    drug_targets: dict[str, set] = defaultdict(set)      # chembl_id -> {target_chembl_id}
    drug_affinity: dict[str, dict] = defaultdict(dict)    # chembl_id -> {target_chembl_id: set(value_type)}
    uniq_targets: set = set()

    for n, (cid, ik, ch) in enumerate(matched, 1):
        # mechanism (curated mechanism-of-action targets)
        mech = http_get_json(
            f"{CHEMBL}/mechanism?molecule_chembl_id={ch}&only=target_chembl_id&format=json&limit=1000")
        if mech:
            for m in mech.get("mechanisms", []):
                t = m.get("target_chembl_id")
                if t:
                    drug_targets[ch].add(t)
                    uniq_targets.add(t)
        # activity with pchembl (potency evidence)
        acts = _paged(
            f"{CHEMBL}/activity?molecule_chembl_id={ch}&pchembl_value__isnull=false"
            f"&only=target_chembl_id,pchembl_value,standard_type&format=json",
            key="activities")
        for a in acts:
            t = a.get("target_chembl_id")
            if not t:
                continue
            drug_targets[ch].add(t)
            uniq_targets.add(t)
            vt = a.get("standard_type") or "pchembl"
            drug_affinity[ch].setdefault(t, set()).add(vt)
        if n % 25 == 0 or n == len(matched):
            print(f"    STEP3 compound {n}/{len(matched)}  누적 uniq target {len(uniq_targets)}")

    # 2) target_chembl_id → UniProt(단백질 성분) 해석 (dedupe → 요청 절감)
    target2uni: dict[str, list] = {}
    for j, t in enumerate(sorted(uniq_targets), 1):
        target2uni[t] = _resolve_target_uniprot(t)
        if j % 50 == 0 or j == len(uniq_targets):
            print(f"    STEP3 target 해석 {j}/{len(uniq_targets)}")

    # 3) 03_targets.csv (drug×uniprot 롱포맷) + 약물당 uniprot 수
    rows = []
    drug_uni: dict[str, set] = defaultdict(set)  # chembl_id -> {uniprot}
    for cid, ik, ch in matched:
        for t in sorted(drug_targets.get(ch, ())):
            for (acc, org, ttype) in target2uni.get(t, []):
                drug_uni[ch].add(acc)
    for cid, ik, ch in matched:
        n_tg = len(drug_uni.get(ch, ()))
        emitted = False
        for t in sorted(drug_targets.get(ch, ())):
            for (acc, org, ttype) in target2uni.get(t, []):
                rows.append([cid, ik, ch, t, acc, org or "", ttype or "",
                             "chembl", n_tg])
                emitted = True
        if not emitted:
            # 표적은 있으나 UniProt(단백질) accession 없음, 또는 표적 자체 없음 → 기록(0)
            rows.append([cid, ik, ch, "", "", "", "", "chembl", 0])

    write_csv(os.path.join(OUTDIR, "03_targets.csv"),
              ["cid", "inchikey", "chembl_id", "target_chembl_id", "uniprot",
               "organism", "target_type", "source", "n_targets_per_drug"], rows)

    drugs_with_uni = sum(1 for ch in drug_uni if drug_uni[ch])
    print(f"  STEP3: ≥1 UniProt 표적 확보 compound {drugs_with_uni}/{len(matched)}, "
          f"uniq UniProt {len({a for s in drug_uni.values() for a in s})}")

    # affinity 중간 산출(STEP5에서 사용) — drug×target value_type 저장
    aff_rows = []
    for ch, tmap in drug_affinity.items():
        for t, vts in tmap.items():
            for (acc, org, ttype) in target2uni.get(t, []):
                aff_rows.append([ch, t, acc, ";".join(sorted(vts))])
    write_csv(os.path.join(OUTDIR, "_affinity_raw.csv"),
              ["chembl_id", "target_chembl_id", "uniprot", "value_types"], aff_rows)
    return rows


# ---------------------------------------------------------------------------
# STEP 4 — UniProt → 서열
# ---------------------------------------------------------------------------
def step4():
    rows_in = read_csv(os.path.join(OUTDIR, "03_targets.csv"))
    unis = sorted({r["uniprot"] for r in rows_in if r["uniprot"]})
    rows = []
    got = 0
    for j, acc in enumerate(unis, 1):
        txt = http_get_text(f"{UNIPROT}/{acc}.fasta")
        seq_len, has = 0, 0
        if txt:
            seq = "".join(l.strip() for l in txt.splitlines() if not l.startswith(">"))
            seq_len = len(seq)
            has = 1 if seq_len > 0 else 0
        got += has
        rows.append([acc, seq_len, has])
        if j % 50 == 0 or j == len(unis):
            print(f"    STEP4 서열 {j}/{len(unis)}  확보 {got}")
    write_csv(os.path.join(OUTDIR, "04_sequences.csv"),
              ["uniprot", "seq_len", "has_seq"], rows)
    print(f"  STEP4: 서열 확보 {got}/{len(unis)} UniProt")
    return rows


# ---------------------------------------------------------------------------
# STEP 5 — 친화도 보유 여부 (M3용, 측정만)
# ---------------------------------------------------------------------------
def step5():
    # STEP3에서 저장한 _affinity_raw(inchikey 조인) 사용
    aff = read_csv(os.path.join(OUTDIR, "_affinity_raw.csv"))
    ch2ik = {r["chembl_id"]: r["inchikey"] for r in read_csv(os.path.join(OUTDIR, "02_chembl.csv")) if r["matched"] == "1"}
    rows = []
    seen = set()
    for r in aff:
        ik = ch2ik.get(r["chembl_id"], "")
        acc = r["uniprot"]
        if not acc:
            continue
        key = (ik, acc)
        if key in seen:
            continue
        seen.add(key)
        rows.append([ik, acc, 1, r["value_types"]])
    write_csv(os.path.join(OUTDIR, "05_affinity.csv"),
              ["inchikey", "uniprot", "has_affinity", "value_type"], rows)
    print(f"  STEP5: affinity 보유 (inchikey,uniprot) pair {len(rows)}")
    return rows


# ---------------------------------------------------------------------------
# STEP 6 — Coverage 표 + 게이트 판정 → docs/19
# ---------------------------------------------------------------------------
def _pct(a, b):
    return f"{100.0*a/b:.1f}%" if b else "—"


def _quantiles(vals: list[int]):
    if not vals:
        return (0, 0, 0, 0)
    s = sorted(vals)
    n = len(s)
    def q(p):
        idx = min(n - 1, int(round(p * (n - 1))))
        return s[idx]
    return (s[0], q(0.5), q(0.95), s[-1])


def step6():
    ROOTN = 1092
    r1 = read_csv(os.path.join(OUTDIR, "01_inchikey.csv"))
    r2 = read_csv(os.path.join(OUTDIR, "02_chembl.csv"))
    r3 = read_csv(os.path.join(OUTDIR, "03_targets.csv"))
    r4 = read_csv(os.path.join(OUTDIR, "04_sequences.csv"))
    r5 = read_csv(os.path.join(OUTDIR, "05_affinity.csv"))

    c0 = ROOTN
    c1 = sum(1 for r in r1 if r["ok"] == "1")
    c2 = sum(1 for r in r2 if r["matched"] == "1")

    # C3: 분자(cid) 단위로 ≥1 UniProt 표적
    seqset = {r["uniprot"] for r in r4 if r["has_seq"] == "1"}
    cid_unis = defaultdict(set)
    cid_unis_withseq = defaultdict(set)
    for r in r3:
        if r["uniprot"]:
            cid_unis[r["cid"]].add(r["uniprot"])
            if r["uniprot"] in seqset:
                cid_unis_withseq[r["cid"]].add(r["uniprot"])
    c3 = sum(1 for cid in cid_unis if cid_unis[cid])
    c4 = sum(1 for cid in cid_unis_withseq if cid_unis_withseq[cid])

    # C5: affinity 보유 분자(cid). 05는 inchikey 기준 → cid로 환산
    ik2cid = defaultdict(set)
    for r in r2:
        if r["matched"] == "1":
            ik2cid[r["inchikey"]].add(r["cid"])
    cids_aff = set()
    for r in r5:
        for cid in ik2cid.get(r["inchikey"], ()):
            cids_aff.add(cid)
    c5 = len(cids_aff)

    # 분포/기여
    per_drug = [len(v) for v in cid_unis.values() if v]
    tmin, tmed, t95, tmax = _quantiles(per_drug)
    uniq_uni = {r["uniprot"] for r in r3 if r["uniprot"]}
    uniq_uni_seq = seqset
    seqlens = [int(r["seq_len"]) for r in r4 if r["has_seq"] == "1"]
    smin, smed, s95, smax = _quantiles(seqlens)
    organisms = defaultdict(int)
    for r in r3:
        if r["uniprot"]:
            organisms[r["organism"] or "(unknown)"] += 1
    human_targets = {r["uniprot"] for r in r3 if r["uniprot"] and (r["organism"] == "Homo sapiens")}

    gate_pct = 100.0 * c3 / c0
    if gate_pct >= 70:
        gate = f"**≥70% ({gate_pct:.1f}%) → 계획대로 M0~M4 전면 진행.**"
        rec = ("C3 커버리지가 70% 이상이므로 표적 축을 전체 분자셋에 적용해 M0~M4 사다리와 "
               "ablation을 계획대로 진행한다. 비매핑 분자는 소수이므로 M0-only 보조 처리 또는 "
               "결측 표적 임베딩(마스킹)으로 흡수한다.")
    elif gate_pct >= 40:
        gate = f"**40~70% ({gate_pct:.1f}%) → 멀티모달은 매핑 성공 서브셋으로 한정.**"
        rec = ("C3 커버리지가 40~70% 구간이므로 멀티모달(M2~M4)은 표적 매핑에 성공한 서브셋에서만 "
               "학습·평가하고, 비매핑 분자는 M0-only로 둔다. 서브셋 편향(표적이 잘 연구된 약물로 "
               "치우침)을 한계로 명시하고, 서브셋 vs 전체의 라벨 분포·prevalence 차이를 함께 보고한다.")
    else:
        gate = f"**<40% ({gate_pct:.1f}%) → 멈추고 보고(표적 축 재검토).**"
        rec = ("C3 커버리지가 40% 미만이므로 표적 축을 그대로 쓰면 멀티모달 서브셋이 지나치게 작아 "
               "스토리가 성립하지 않는다. 표적 매핑 기준 완화(예: pchembl 미보유 activity·homolog·"
               "connectivity-layer InChIKey 매칭) 또는 다른 novelty(표현 앙상블·캘리브레이션)로의 "
               "선회를 검토하고 보고 후 결정한다.")

    doc = os.path.join(ROOT, "docs", "19_v3_coverage_report.md")
    src_rel = "v3_Multimodal/src/coverage_mapping.py"
    lines = []
    A = lines.append
    A("# 19. v3 멀티모달(DrugBank-free) 표적 매핑 Coverage 리포트\n")
    A("> 생성: `v3_Multimodal/src/coverage_mapping.py` (SEED=42, 요청 JSON 캐시 `data/processed/target_mapping/_cache/`).")
    A("> 근거 설계: `docs/18_sci_v3_paper_plan.md` §4.3, 지시 `docs/11_advisor_consult_submission.md` §3, 프롬프트 `docs/18b`.")
    A("> **범위**: 커버리지 측정만. 모델 학습·ProtBERT 임베딩 계산은 포함하지 않음(다음 마일스톤).")
    A("> 데이터 소스: **ChEMBL (EMBL-EBI) REST**, **UniProt (EMBL-EBI) REST**. DrugBank 미사용. BindingDB=아래 §비고 참조.\n")

    A("## 1. Coverage 표\n")
    A("| 단계 | 대상 | 성공 | 커버리지 % |")
    A("|---|---|---|---|")
    A(f"| C0 전체 | {c0} | {c0} | 100% |")
    A(f"| C1 InChIKey(로컬 RDKit) | {c0} | {c1} | {_pct(c1, c0)} |")
    A(f"| C2 ChEMBL compound | {c0} | {c2} | {_pct(c2, c0)} |")
    A(f"| C3 ≥1 UniProt target ★ | {c0} | {c3} | {_pct(c3, c0)} |")
    A(f"| C4 서열 확보 | {c0} | {c4} | {_pct(c4, c0)} |")
    A(f"| C5 affinity 보유 | {c0} | {c5} | {_pct(c5, c0)} |")
    A("\n- 각 단계는 **분자(cid) 단위** 커버리지(분모 = 확정 분자셋 1,092).")
    A("- C2는 full InChIKey **정확 매칭**(ChEMBL `standard_inchi_key`) 기준 — stereo/염 형태 차이로 인한 미매칭은 보수적 하한.")
    A("- C3는 mechanism(MoA) + pChEMBL 보유 activity에서 얻은 표적 중 **SINGLE PROTEIN → UniProt accession** 이 잡힌 분자 수.\n")

    A("## 2. 분포·기여\n")
    A(f"- **약물당 UniProt 표적 수**(표적≥1 분자 {len(per_drug)}개 대상): "
      f"중앙값 **{tmed}**, 95퍼센타일 **{t95}**, 범위 {tmin}~{tmax}.")
    A(f"- **유니크 UniProt 표적 수**: 전체 **{len(uniq_uni)}** (그중 서열 확보 **{len(uniq_uni_seq)}**).")
    A(f"- **Human(Homo sapiens) 표적 유니크 수**: **{len(human_targets)}**.")
    A(f"- **서열 길이 분포**(확보 {len(seqlens)}): 중앙값 **{smed} aa**, 95퍼센타일 **{s95} aa**, 범위 {smin}~{smax}.")
    A("- **source별 기여**: ChEMBL = 전 표적(주소스). BindingDB = 미반영(아래 §비고).")
    A("- 표적 organism 상위:")
    for org, cnt in sorted(organisms.items(), key=lambda x: -x[1])[:6]:
        A(f"  - {org}: {cnt} (drug×target rows)")
    A("")

    A("## 3. 게이트 판정 (docs/18 §4.3)\n")
    A(f"- **C3 = {c3}/{c0} = {gate_pct:.1f}%** → {gate}\n")
    A(f"{rec}\n")

    A("## 4. 산출물 · 재현 방법\n")
    A("```\ndata/processed/target_mapping/")
    A("  01_inchikey.csv    (cid, smiles, inchikey, ok)")
    A("  02_chembl.csv      (cid, inchikey, chembl_id, matched)")
    A("  03_targets.csv     (cid, inchikey, chembl_id, target_chembl_id, uniprot, organism, target_type, source, n_targets_per_drug)")
    A("  04_sequences.csv   (uniprot, seq_len, has_seq)")
    A("  05_affinity.csv    (inchikey, uniprot, has_affinity, value_type)")
    A("  _cache/            (요청 JSON/FASTA 캐시 — 재현·오프라인 재실행)\n```")
    A(f"\n재실행:\n```bash\npython {src_rel} --step all\n```")
    A("모든 HTTP 응답은 `_cache/`에 저장되어 동일 입력에 대해 결정적으로 재현된다(seed=42, 확률적 연산 없음).\n")

    A("## 5. 비고 · 한계 (정직 보고)\n")
    A("- **BindingDB 미반영**: 실행 시점(2026-07-14) BindingDB REST 엔드포인트(`axis2/services/BDBService/*`, `/rest/*`)가 404를 반환해 자동 수집 불가. "
      "따라서 C3는 **ChEMBL 단독 하한**이며, BindingDB 보강 시 커버리지가 상승할 여지가 있다(향후 수동 병합 과제).")
    A("- **정확 InChIKey 매칭 한계**: stereo/염/호변이체 차이로 ChEMBL 미매칭이 발생할 수 있어 C2는 보수적. connectivity-layer(첫 14자) 매칭으로 완화 가능하나 본 측정은 정직한 정확매칭 기준을 채택.")
    A("- **표적 근거 기준**: activity는 `pchembl_value` 보유(표준화 효력값)만 채택 → 저신뢰 표적 배제. mechanism(MoA)은 큐레이션이라 무조건 포함.")
    A("- 이 리포트는 **구조·라벨·split 불변**(재다운로드/재학습 없음) 원칙을 지켰다.")

    os.makedirs(os.path.dirname(doc), exist_ok=True)
    with open(doc, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ✅ {os.path.relpath(doc, ROOT)}")
    print(f"  ★ C3 게이트 = {c3}/{c0} = {gate_pct:.1f}%")
    return gate_pct


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="all",
                    help="'all' 또는 '1,2,3,4,5,6' 쉼표구분")
    ap.add_argument("--limit", type=int, default=0, help="STEP1 분자 수 제한(스모크)")
    args = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    steps = ["1", "2", "3", "4", "5", "6"] if args.step == "all" else args.step.split(",")
    fns = {"1": lambda: step1(args.limit), "2": step2, "3": step3,
           "4": step4, "5": step5, "6": step6}
    for s in steps:
        print(f"▶ STEP {s}")
        fns[s.strip()]()


if __name__ == "__main__":
    main()
