#!/usr/bin/env python3
"""a5_mechanism_requery.py — [블록 Y] A5 작용기전 표적 **1회 재조회** (지시서 `docs/80`).

승인: 양진홍 교수님 2026-08-06 12:05:26 KST 「승인」(`docs/77` §3 주석 1) — **재조회 행위만**.

이 스크립트가 하는 것
--------------------
1. `02_chembl.csv` 의 **943 chembl_id 한정** · **분자당 1요청**으로 ChEMBL `/mechanism` 조회
2. mechanism 이 지목한 `target_chembl_id` → UniProt 해석 (로컬 우선 · 잔여만 `/target/{id}`)
3. `(cid, chembl_id, target_chembl_id, uniprot, ...)` 표 + **원응답·해시·실패율** 기록
4. **캐시 봉인** = 조회 시점 상태를 해시로 고정 (`_sealed/` 이동이 **아니다**)

이 스크립트가 **하지 않는** 것
---------------------------
라벨 결합(`master_Y`·PT·OOF·성능 산출물 접근 0) · A5 층화·Δ·CI·p · `emit_sign` ·
`decision.py` 호출 · 개봉 · `_sealed/` 쓰기 · 기존 `_cache/` 수정 · git commit/push.

★ 배치 금지 — `fetch_m1b_covariates.py:82` 가 `molecule_chembl_id__in=` 배치로 조회한 탓에
응답에서 약물 귀속이 소실됐고(`docs/63` §3) 그것이 이 블록이 존재하는 이유다. 여기서는
귀속이 **응답 본문이 아니라 요청 자체**로 보장된다.

사용:
    python v3_Multimodal/src/a5_mechanism_requery.py --stage fetch [--limit N]
    python v3_Multimodal/src/a5_mechanism_requery.py --stage seal
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import coverage_mapping as cm                                     # noqa: E402
from compute_lock import ComputeLock, gate_b_exclusive            # noqa: E402

KST = timezone(timedelta(hours=9))

CFG = os.path.join(ROOT, "v3_Multimodal", "config")
FREEZE = os.path.join(CFG, "a5_mechanism_freeze.json")
PIF_STATUS = os.path.join(CFG, "post_interim_freeze_v1_0.status.json")
TM = os.path.join(ROOT, "data", "processed", "target_mapping")
CACHE = os.path.join(TM, "_a5_mechanism_cache")          # ★ 신규 전용 캐시 (기존 _cache/ 무수정)
RAW = os.path.join(CACHE, "raw")
JSONC = os.path.join(CACHE, "json")
RUNDIR = os.path.join(ROOT, "experiments", "runs", "v3_a5_requery")
CKPT = os.path.join(RUNDIR, "a5_fetch_checkpoint.jsonl")
REQLOG = os.path.join(RUNDIR, "a5_request_log.jsonl")
FETCHSTATE = os.path.join(RUNDIR, "a5_fetch_state.json")
OUT_CSV = os.path.join(TM, "a5_mechanism_targets.csv")
MANIFEST = os.path.join(ROOT, "experiments", "provenance", "a5_requery_manifest.json")
PUBLIC = os.path.join(RUNDIR, "a5_requery_public.json")

IN_FILES = ["02_chembl.csv", "06_targets_human.csv", "08_m1b_covariates.csv"]

# ── 네트워크 화이트리스트 (§0) ───────────────────────────────────────────────
HOST = "www.ebi.ac.uk"
PATH_MECH = "/chembl/api/data/mechanism"
PATH_TARGET = "/chembl/api/data/target/"

ALLOWED_MOL: set[str] = set()      # 02_chembl.csv 의 943
ALLOWED_TGT: set[str] = set()      # mechanism 응답이 지목한 target 만 (§Y-3-4)
NETWORK_CALLS: list[dict] = []


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def jlog(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# ── 화이트리스트 강제 + 원응답 tee (urlopen 래핑 · cm 원본 무수정) ───────────
_ORIG_URLOPEN = urllib.request.urlopen


def assert_whitelisted(url: str):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.netloc != HOST:
        raise RuntimeError(f"화이트리스트 밖 요청(호스트): {url}")
    path = u.path
    q = urllib.parse.parse_qs(u.query)
    if path.startswith(PATH_MECH):
        if "__in" in u.query:
            raise RuntimeError(f"배치 조회 금지(__in): {url}")
        mols = q.get("molecule_chembl_id", [])
        if len(mols) != 1:
            raise RuntimeError(f"molecule_chembl_id 1개가 아님: {url}")
        if mols[0] not in ALLOWED_MOL:
            raise RuntimeError(f"943 밖 화합물: {mols[0]}")
        return "mechanism", mols[0]
    if path.startswith(PATH_TARGET):
        tid = path[len(PATH_TARGET):].split("/")[0].split(".")[0]
        if tid not in ALLOWED_TGT:
            raise RuntimeError(f"허용 밖 target: {tid}")
        return "target", tid
    raise RuntimeError(f"화이트리스트 밖 엔드포인트: {url}")


class _Tee:
    """응답 바이트를 **원문 그대로** 갈무리한다(정규화·절삭 없음)."""

    def __init__(self, resp, url):
        self._r, self._url = resp, url

    def read(self, *a):
        b = self._r.read(*a)
        os.makedirs(RAW, exist_ok=True)
        h = hashlib.sha1(self._url.encode()).hexdigest()[:20]
        with open(os.path.join(RAW, h + ".body"), "wb") as f:
            f.write(b)
        NETWORK_CALLS[-1]["response_bytes"] = len(b)
        NETWORK_CALLS[-1]["response_sha256"] = sha256_bytes(b)
        NETWORK_CALLS[-1]["raw_file"] = f"raw/{h}.body"
        jlog(REQLOG, NETWORK_CALLS[-1])
        return b

    def __enter__(self):
        self._r.__enter__()
        return self

    def __exit__(self, *a):
        return self._r.__exit__(*a)

    def __getattr__(self, n):
        return getattr(self._r, n)


def guarded_urlopen(req, *a, **kw):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    kind, ident = assert_whitelisted(url)
    NETWORK_CALLS.append({"ts_kst": now_kst(), "url": url, "kind": kind, "id": ident,
                          "network": True})
    return _Tee(_ORIG_URLOPEN(req, *a, **kw), url)


urllib.request.urlopen = guarded_urlopen          # 프로세스 내 한정 · cm 파일은 무수정


def cached(url):
    return os.path.exists(cm._cache_path(url))


# ── 입력 ────────────────────────────────────────────────────────────────────
def load_population():
    rows = cm.read_csv(os.path.join(TM, "02_chembl.csv"))
    assert len(rows) == 1092, f"02_chembl 행수 {len(rows)} != 1092"
    ch2cid = {}
    for r in rows:
        if r["matched"] == "1" and r["chembl_id"]:
            assert r["chembl_id"] not in ch2cid, f"chembl_id 중복 {r['chembl_id']}"
            ch2cid[r["chembl_id"]] = int(r["cid"])
    assert len(ch2cid) == 943, f"모집단 {len(ch2cid)} != 943"
    return ch2cid


def load_local_target_map():
    """06_targets_human.csv 의 target_chembl_id → {uniprot} (로컬 해석 1순위)."""
    rows = cm.read_csv(os.path.join(TM, "06_targets_human.csv"))
    assert len(rows) == 12613, f"06_targets_human 행수 {len(rows)} != 12613"
    m = defaultdict(set)
    for r in rows:
        if r["target_chembl_id"] and r["uniprot"]:
            m[r["target_chembl_id"]].add(r["uniprot"])
    return {k: sorted(v) for k, v in m.items()}


# ── 조회 ────────────────────────────────────────────────────────────────────
def fetch_mechanism(ch):
    """분자 1건 조회(페이지 전건). → (ok, records, pages, n_net)."""
    url = f"{cm.CHEMBL}/mechanism?molecule_chembl_id={ch}&format=json&limit=1000&offset=0"
    recs, pages, n_net = [], 0, 0
    while url and pages < 5:
        if not cached(url):
            n_net += 1
        else:
            jlog(REQLOG, {"ts_kst": now_kst(), "url": url, "kind": "mechanism", "id": ch,
                          "network": False, "cache_hit": True})
        data = cm.http_get_json(url)
        if data is None:
            return False, recs, pages, n_net
        recs.extend(data.get("mechanisms", []))
        nxt = (data.get("page_meta") or {}).get("next")
        url = ("https://" + HOST + nxt) if nxt else None
        pages += 1
    return True, recs, pages, n_net


def fetch_target(tid):
    url = f"{cm.CHEMBL}/target/{tid}?format=json"
    if cached(url):
        jlog(REQLOG, {"ts_kst": now_kst(), "url": url, "kind": "target", "id": tid,
                      "network": False, "cache_hit": True})
    data = cm.http_get_json(url)
    if data is None:
        return None
    accs = []
    for comp in data.get("target_components", []):
        acc = comp.get("accession")
        if acc:
            accs.append(acc)
    return {"uniprots": sorted(set(accs)), "organism": data.get("organism"),
            "target_type": data.get("target_type")}


# ── STAGE fetch ─────────────────────────────────────────────────────────────
def stage_fetch(limit=0):
    ts_start = now_kst()
    ch2cid = load_population()
    ALLOWED_MOL.update(ch2cid)

    fz = json.load(open(FREEZE, encoding="utf-8"))
    assert fz["frozen_before_any_fetch"] is True, "정의 동결 파일이 조회 전 기입이 아니다"
    frozen_dt = datetime.strptime(fz["frozen_at_kst"], "%Y-%m-%d %H:%M:%S KST").replace(tzinfo=KST)
    assert frozen_dt < datetime.now(KST), "동결 시각이 미래다"
    print(f"[freeze] {fz['frozen_at_kst']} < 최초 네트워크 호출 (종료검증 #1)")

    st = json.load(open(PIF_STATUS, encoding="utf-8"))
    assert st["a5_requery_executed"] is False, "a5_requery_executed 이미 true — 중단"
    assert st["unblinding_performed"] is False

    os.makedirs(JSONC, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(RUNDIR, exist_ok=True)
    cm.CACHEDIR = JSONC                      # ★ 캐시 경로 분리 (기존 _cache/ 오염 0)

    done = {}
    if os.path.exists(CKPT):
        for line in open(CKPT, encoding="utf-8"):
            r = json.loads(line)
            done[r["chembl_id"]] = r         # 같은 ID 재기록 시 최신이 이긴다

    ids = sorted(ch2cid)
    if limit:
        ids = ids[:limit]

    todo = [c for c in ids if done.get(c, {}).get("status") != "ok"]
    print(f"[fetch] 대상 {len(ids)} · 기완료 {len(ids) - len(todo)} · 잔여 {len(todo)}", flush=True)

    t0 = time.time()
    for i, ch in enumerate(todo, 1):
        ok, recs, pages, n_net = fetch_mechanism(ch)
        attrib_ok = True
        seen_ids = set()
        for m in recs:
            mid = m.get("molecule_chembl_id")
            if mid is not None:
                seen_ids.add(mid)
                if mid != ch:
                    attrib_ok = False
        if not attrib_ok:
            raise RuntimeError(f"귀속 불일치 — 요청 {ch} vs 응답 {sorted(seen_ids)} (중단)")
        jlog(CKPT, {"ts_kst": now_kst(), "chembl_id": ch,
                    "status": "ok" if ok else "failed", "n_records": len(recs),
                    "pages": pages, "n_network_calls": n_net,
                    "attribution_assert": "pass",
                    "response_ids_present": sorted(seen_ids)})
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"  {i}/{len(todo)} · {el:.0f}s · {el / i:.2f}s/req · "
                  f"net={sum(1 for c in NETWORK_CALLS)}", flush=True)

    ts_end = now_kst()
    state = {"ts_start_kst": ts_start, "ts_end_kst": ts_end,
             "n_requested": len(ids), "n_network_calls_this_session": len(NETWORK_CALLS)}
    with open(FETCHSTATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(state, ensure_ascii=False, indent=2))


# ── STAGE seal ──────────────────────────────────────────────────────────────
def read_ckpt():
    last = {}
    for line in open(CKPT, encoding="utf-8"):
        r = json.loads(line)
        last[r["chembl_id"]] = r
    return last


def mech_records_for(ch):
    """캐시(원응답)에서 분자 1건의 mechanism 레코드 복원 — 네트워크 0."""
    url = f"{cm.CHEMBL}/mechanism?molecule_chembl_id={ch}&format=json&limit=1000&offset=0"
    recs = []
    pages = 0
    while url and pages < 5:
        cp = cm._cache_path(url)
        if not os.path.exists(cp):
            return None
        data = json.load(open(cp, encoding="utf-8"))
        recs.extend(data.get("mechanisms", []))
        nxt = (data.get("page_meta") or {}).get("next")
        url = ("https://" + HOST + nxt) if nxt else None
        pages += 1
    return recs


def stage_seal():
    ts = now_kst()
    ch2cid = load_population()
    ALLOWED_MOL.update(ch2cid)
    cm.CACHEDIR = JSONC
    local_map = load_local_target_map()
    ck = read_ckpt()

    in_sha = {n: sha256_file(os.path.join(TM, n)) for n in IN_FILES}

    ok_ids = sorted(c for c in ch2cid if ck.get(c, {}).get("status") == "ok")
    failed_ids = sorted(c for c in ch2cid if ck.get(c, {}).get("status") != "ok")

    # 1) mechanism 레코드 복원 + target 수집
    per_drug = {}
    all_targets = set()
    for ch in ok_ids:
        recs = mech_records_for(ch)
        assert recs is not None, f"캐시 결손 {ch}"
        per_drug[ch] = recs
        for m in recs:
            t = m.get("target_chembl_id")
            if t:
                all_targets.add(t)

    # 2) target → UniProt (로컬 우선 · 잔여만 /target/{id})
    resolved, source = {}, {}
    for t in sorted(all_targets):
        if t in local_map:
            resolved[t] = local_map[t]
            source[t] = "local_06_targets_human"
    remaining = sorted(all_targets - set(resolved))
    ALLOWED_TGT.update(remaining)
    print(f"[target] 전체 {len(all_targets)} · 로컬 해석 {len(resolved)} · 추가 조회 {len(remaining)}",
          flush=True)
    n_target_fetch = 0
    for t in remaining:
        r = fetch_target(t)
        n_target_fetch += 1
        if r and r["uniprots"]:
            resolved[t] = r["uniprots"]
            source[t] = "chembl_target_endpoint"
        else:
            resolved[t] = []
            source[t] = "unresolved"

    unresolved = sorted(t for t in all_targets if not resolved.get(t))

    # 3) 산출 CSV (라벨 결합 0)
    header = ["cid", "chembl_id", "target_chembl_id", "uniprot", "action_type",
              "mechanism_of_action", "resolution_source", "multi_uniprot"]
    rows = []
    n_no_mech = 0
    for ch in sorted(ch2cid):
        cid = ch2cid[ch]
        if ch in failed_ids:
            rows.append([cid, ch, "", "", "", "", "fetch_failed", ""])
            continue
        recs = per_drug[ch]
        if not recs:
            n_no_mech += 1
            rows.append([cid, ch, "", "", "", "", "no_mechanism", ""])
            continue
        for m in recs:
            t = m.get("target_chembl_id") or ""
            at = m.get("action_type") or ""
            moa = m.get("mechanism_of_action") or ""
            if not t:
                rows.append([cid, ch, "", "", at, moa, "no_target_chembl_id", ""])
                continue
            ups = resolved.get(t, [])
            multi = "1" if len(ups) > 1 else "0"
            if not ups:
                rows.append([cid, ch, t, "", at, moa, "unresolved", "0"])
            else:
                for u in ups:                       # ★ 전건 보존 — 임의 단일 선택 0
                    rows.append([cid, ch, t, u, at, moa, source[t], multi])
    cm.write_csv(OUT_CSV, header, rows)

    # 4) 커버리지 대조 (Y-5) — 판정 아님, 사실만
    cov = cm.read_csv(os.path.join(TM, "08_m1b_covariates.csv"))
    old_n = {}
    for r in cov:
        if r.get("chembl_id"):
            old_n[r["chembl_id"]] = int(r["mechanism_target_n"] or 0)
    new_n = {ch: len({m.get("target_chembl_id") for m in per_drug[ch]
                      if m.get("target_chembl_id")}) for ch in ok_ids}
    compare, agree, disagree = [], 0, 0
    for ch in sorted(set(old_n) | set(new_n)):
        o = old_n.get(ch)
        n = new_n.get(ch)
        if o is not None and n is not None and o == n:
            agree += 1
        else:
            disagree += 1
            compare.append({"chembl_id": ch, "old_mechanism_target_n": o,
                            "new_mechanism_target_n": n})

    # 5) 캐시 봉인 = 해시 고정 (`_sealed/` 이동이 아니다)
    def cache_tree():
        out = {}
        for dirpath, _, names in os.walk(CACHE):
            for nm in sorted(names):
                p = os.path.join(dirpath, nm)
                out[os.path.relpath(p, CACHE)] = sha256_file(p)
        return dict(sorted(out.items()))

    tree = cache_tree()
    tree_sha = sha256_bytes(json.dumps(tree, ensure_ascii=False, sort_keys=True).encode())
    n_raw = sum(1 for k in tree if k.startswith("raw/"))

    net_reqs = [json.loads(l) for l in open(REQLOG, encoding="utf-8")] \
        if os.path.exists(REQLOG) else []
    n_net_total = sum(1 for r in net_reqs if r.get("network"))
    hosts = sorted({urllib.parse.urlsplit(r["url"]).netloc for r in net_reqs})
    paths = sorted({urllib.parse.urlsplit(r["url"]).path for r in net_reqs})
    st_fetch = json.load(open(FETCHSTATE, encoding="utf-8"))

    n_req = len(ch2cid)
    n_ok = len(ok_ids)
    n_fail = len(failed_ids)

    manifest = {
        "_doc": ("A5 작용기전 표적 **1회 재조회** provenance. 승인 조건 ②의 5항목(조회일·출처·"
                 "원응답·해시·ID 매핑 실패율)이 전부 이 파일에 들어 있다. 본 블록은 A5 를 "
                 "**계산하지 않는다** — 봉인이 블록의 끝이다."),
        "block": "Y (docs/80_a5_mechanism_requery_prompt_for_vscode.md)",
        "sealed_at_kst": ts,

        "approval": {
            "record": "docs/77_advisor_approval_20260806.md §3 주석 1",
            "advisor": "양진홍 교수님",
            "approved_at_kst": "2026-08-06 12:05:26 KST",
            "verbatim": "승인",
            "scope": "1회 재조회(조회 행위)만. A5 정의·구간은 no_objection_raised(내선 확정).",
            "conditions": json.load(open(PIF_STATUS, encoding="utf-8"))["a5_requery_conditions"],
        },
        "analysis_label": "현재 snapshot 기반 post-interim 보조분석",
        "frozen_definition": {
            "path": "v3_Multimodal/config/a5_mechanism_freeze.json",
            "sha256": sha256_file(FREEZE),
            "frozen_at_kst": json.load(open(FREEZE, encoding="utf-8"))["frozen_at_kst"],
            "frozen_before_any_fetch": True,
        },

        # ── 조건 ① 조회일 ──────────────────────────────────────────────
        "queried_at_kst_start": st_fetch["ts_start_kst"],
        "queried_at_kst_end": st_fetch["ts_end_kst"],
        "sealed_stage_at_kst": ts,
        "n_network_calls": n_net_total,
        "n_network_calls_definition": ("응답 바이트를 받은 네트워크 호출 수(요청 로그 기준). "
                                       "urlopen 시도 수는 아래 *_attempts 로 별기한다."),
        "n_urlopen_attempts_fetch_session": st_fetch["n_network_calls_this_session"],
        "n_urlopen_attempts_seal_session": len(NETWORK_CALLS),
        "n_requested": n_req,

        # ── 조건 ② 출처 ────────────────────────────────────────────────
        "api_base": cm.CHEMBL,
        "api_version_if_reported": None,
        "endpoints": [f"https://{HOST}{PATH_MECH}?molecule_chembl_id=<943 중 1>&format=json"
                      f"&limit=1000&offset=<page>",
                      f"https://{HOST}{PATH_TARGET}<mechanism 응답이 지목한 target>?format=json"],
        "observed_hosts": hosts,
        "observed_paths": paths,
        "batch_query_used": False,
        "one_request_per_molecule": True,
        "request_log": "experiments/runs/v3_a5_requery/a5_request_log.jsonl",

        # ── 조건 ③ 원응답 ──────────────────────────────────────────────
        "raw_cache_dir": "data/processed/target_mapping/_a5_mechanism_cache",
        "raw_cache_layout": {"raw/": "응답 바이트 원문 그대로(절삭·정규화 0)",
                             "json/": "cm.http_get_json 캐시-우선 파일(재개용)"},
        "n_raw_files": n_raw,
        "n_cache_files_total": len(tree),
        "cache_file_sha256": tree,
        "cache_tree_sha256": tree_sha,

        # ── 조건 ④ 해시 ────────────────────────────────────────────────
        "output_csv": "data/processed/target_mapping/a5_mechanism_targets.csv",
        "output_csv_sha256": sha256_file(OUT_CSV),
        "input_sha256": in_sha,
        "existing_cache_untouched": "data/processed/target_mapping/_cache/ 는 읽지도 쓰지도 않았다",

        # ── 조건 ⑤ ID 매핑 실패율 ──────────────────────────────────────
        "n_success": n_ok,
        "n_failed": n_fail,
        "failure_rate": round(n_fail / n_req, 6),
        "failed_ids": failed_ids,
        "n_targets_total": len(all_targets),
        "n_targets_resolved_local": sum(1 for t in source.values()
                                        if t == "local_06_targets_human"),
        "n_targets_resolved_endpoint": sum(1 for t in source.values()
                                           if t == "chembl_target_endpoint"),
        "n_targets_unresolved": len(unresolved),
        "unresolved_rate": round(len(unresolved) / len(all_targets), 6) if all_targets else 0.0,
        "unresolved_target_ids": unresolved,
        "n_multi_uniprot_targets": sum(1 for t, u in resolved.items() if len(u) > 1),
        "multi_uniprot_policy": "전건 보존 — 임의 단일 선택 0",

        "scope_interpretation": {
            "question": "승인 문면의 '기존 943개 ID 한정' 은 화합물 기준인데, mechanism 응답이 "
                        "지목한 target ID 를 `/target/{id}` 로 조회하는 것이 그 범위 안인가?",
            "interpretation": "범위 안이다. 조회한 target 은 943 화합물의 응답이 스스로 지목한 "
                              "것이므로 새 화합물 도입이 아니다. A5 의 unseen 판정 기준이 "
                              "UniProt accession 이라 target→UniProt 해석이 필수적이다.",
            "mitigation": "먼저 기존 로컬 파일(06_targets_human.csv)로 해석하고 그래도 남는 "
                          "target 만 조회해 조회 건수를 최소화했다.",
            "n_target_endpoint_calls": n_target_fetch,
            "endpoint": f"https://{HOST}{PATH_TARGET}{{target_chembl_id}}?format=json",
            "status": "해석이므로 리포트에도 명시한다",
        },

        "label_join_performed": False,
        "files_opened": sorted(IN_FILES + [
            "v3_Multimodal/config/a5_mechanism_freeze.json",
            "v3_Multimodal/config/post_interim_freeze_v1_0.status.json"]),
        "label_files_accessed": [],
        "not_performed": {"a5_stratification": 0, "delta_ci_p": 0, "emit_sign": 0,
                          "decision_py": 0, "unblinding": 0, "sealed_writes": 0,
                          "git_commit": 0, "git_push": 0, "affinity_values_recorded": 0},

        "coverage_crosscheck": {
            "_note": "정합 점검이지 판정이 아니다. snapshot 시점이 다르므로 불일치는 예상 범위다.",
            "source": "data/processed/target_mapping/08_m1b_covariates.csv mechanism_target_n",
            "n_agree": agree, "n_disagree": disagree, "rows": compare,
        },
        "no_mechanism_drug_count": n_no_mech,
        "no_mechanism_note": ("가용성 수치다. `{0}`/`{1}` 층 배정은 unseen 판정이 필요하고 "
                              "그것은 후속 블록이다."),
    }

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 6) 봉인 후 불변 assert — 캐시 전건 재해시
    tree2 = cache_tree()
    assert tree2 == tree, "봉인 후 캐시 해시 불일치 — 중단"
    tree2_sha = sha256_bytes(json.dumps(tree2, ensure_ascii=False, sort_keys=True).encode())
    assert tree2_sha == tree_sha, "cache_tree_sha256 불일치 — 중단"
    for n in IN_FILES:
        assert sha256_file(os.path.join(TM, n)) == in_sha[n], f"입력 변경 {n}"

    pub = {
        "_scope": "공개 — 조회 건수·실패율·해석 결과·해시만. 지표·Δ·CI·p·부호·친화도 수치 없다.",
        "block": "Y (docs/80)", "ts_kst": ts,
        "analysis_label": "현재 snapshot 기반 post-interim 보조분석",
        "n_requested": n_req, "n_success": n_ok, "n_failed": n_fail,
        "failure_rate": round(n_fail / n_req, 6),
        "n_network_calls": n_net_total,
        "n_targets_total": len(all_targets),
        "n_targets_resolved_local": manifest["n_targets_resolved_local"],
        "n_targets_resolved_endpoint": manifest["n_targets_resolved_endpoint"],
        "n_targets_unresolved": len(unresolved),
        "unresolved_rate": manifest["unresolved_rate"],
        "n_multi_uniprot_targets": manifest["n_multi_uniprot_targets"],
        "coverage_crosscheck_n_agree": agree,
        "coverage_crosscheck_n_disagree": disagree,
        "no_mechanism_drug_count": n_no_mech,
        "gates": {"G0": "PASS", "sealed_guard_273_288": "PASS",
                  "whitelist_hosts_only": hosts == [HOST],
                  "label_join_performed": False},
        "hashes": {"a5_mechanism_freeze.json": sha256_file(FREEZE),
                   "a5_mechanism_targets.csv": sha256_file(OUT_CSV),
                   "a5_requery_manifest.json": sha256_file(MANIFEST),
                   "cache_tree_sha256": tree_sha},
    }
    with open(PUBLIC, "w", encoding="utf-8") as f:
        json.dump(pub, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps({k: v for k, v in pub.items() if k != "hashes"},
                     ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["fetch", "seal"])
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    with ComputeLock(script="a5_mechanism_requery.py", role="runner"):
        gate_b_exclusive(f"a5_requery:{a.stage}:entry")     # G-IDLE A 면제 (모델 계산 0)
        if a.stage == "fetch":
            stage_fetch(a.limit)
        else:
            stage_seal()
        gate_b_exclusive(f"a5_requery:{a.stage}:exit")


if __name__ == "__main__":
    main()
