#!/usr/bin/env python3
"""rqint_package_gates.py — 블록 M-5: v2 패키지 산출물 게이트 검증.

검증 항목(`docs/58` M-5)
  1. 동결 자산 불변: `ladder_freeze.json` b885585aefbabb32 · SAP manifest 756d485feb4715e9 + 11모듈 sha
  2. `docs/55` v1 `.md`/`.docx` **바이트 불변**
  3. sealed guard: 착수 스냅샷 ↔ 종료 재계산 완전 일치
  4. v2 `.md`/`.docx` 전문 **봉인 계열 스캔** (키 스캔 + 값 스캔 + 부호 노출 스캔)
  5. v2 문서 수치 ↔ `facts_public.json` 교차 대조
  6. md ↔ docx 텍스트 동등성(문서 본문 누락 없음)

실행: .venv/bin/python3 v3_Multimodal/src/rqint_package_gates.py <sealed_start.json>
산출: experiments/runs/v3_rqint_package_v2/gates_public.json
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
KST = timezone(timedelta(hours=9))
RUN = os.path.join(ROOT, "experiments", "runs", "v3_rqint_package_v2")
V2_MD = os.path.join(ROOT, "docs", "55b_rqint_external_statreview_package_v2.md")
V2_DOCX = os.path.join(ROOT, "docs", "55b_rqint_external_statreview_package_v2.docx")
V1_MD = os.path.join(ROOT, "docs", "55_rqint_external_statreview_package.md")
V1_DOCX = os.path.join(ROOT, "docs", "55_rqint_external_statreview_package.docx")

EXPECT = {
    "ladder_freeze_sha16": "b885585aefbabb32",
    "sap_manifest_sha16": "756d485feb4715e9",
    "v1_md_sha16": "1f6081d824bb2c95", "v1_md_bytes": 16746,
    "v1_docx_sha16": "222eb130cdddfc64", "v1_docx_bytes": 20135,
}

# 블록 I·K 의 봉인 계열 키 목록(재사용).
SEALED_KEYS = ("macro_ap", "delta", "sign", "ci_bca", "ci_percentile", "ci_primary",
               "p_two_sided", "p_emp", "per_pt_ap", "boot_summary", "null_summary")

# 값 스캔 화이트리스트: 문서에 나타나도 되는 소수와 그 출처(전부 비-확증).
DECIMAL_WHITELIST = {
    "0.05": "ALPHA (동결 설계상수, 사전등록 §8 공개)",
    "0.01": "SESOI (동결 설계상수, 사전등록 §8 공개)",
    "0.0625": "2/2^5 — permutation 공간 해석식(결과-독립)",
    "0.0909": "3/33 — 전수열거 공식 하한(결과-독립)",
    "0.4375": "7 × 0.0625 — Holm 최대 배수(결과-독립)",
    "0.0489": "라벨 밀도(사전등록 §2 공개 설계량)",
    "0.166": "v2_GNN 탐색적 공개수치(비봉인·다른 분할)",
    "0.025": "v2_GNN 탐색적 공개수치(표준편차)",
    "0.191": "v2_GNN 탐색적 공개수치(비봉인·다른 분할)",
    "0.002": "v2_GNN 탐색적 공개수치(표준편차)",
    "0.140": "GraphDTA 탐색적 공개수치(비봉인·다른 분할)",
    "0.013": "GraphDTA 탐색적 공개수치(표준편차)",
    "0.1346": "synthetic macro AP 1회 wall 중앙값(실측)",
    "0.1342": "synthetic 타이밍 IQR 하단(실측)",
    "0.1347": "synthetic 타이밍 IQR 상단(실측)",
    "2.99": "(i)형 단일코어 wall 추정(실측 기반)",
    "7.48": "(ii)형 단일코어 wall 추정(실측 기반)",
    "0.0004": "synthetic block-swap wall 중앙값(실측)",
    "2.05": "블록 D 실효 병렬도(공개 기록)",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sealed_inventory():
    inv = {}
    for root, _dirs, fs in os.walk(os.path.join(ROOT, "experiments", "runs")):
        if "_sealed" in root.split(os.sep):
            for f in fs:
                if f == "access.log":
                    continue
                p = os.path.join(root, f)
                inv[os.path.relpath(p, ROOT)] = sha256(p)
    return inv


def docx_text(path):
    x = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    sep = re.sub(r"</w:(p|tc|tr)>", r"</w:\1>\n", x)      # 문단·셀 경계에 개행(연결 오탐 방지)
    t = re.sub(r"<[^>]+>", "", sep)
    return (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"), x)


def main():
    start_snap = sys.argv[1]
    res = {"_doc": "블록 M-5 게이트 (docs/58). 개봉 0 · 새 추정 0 · 문서 산출물 검증 전용.",
           "checked_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"), "gates": {}}
    g = res["gates"]

    # G1 동결 자산 --------------------------------------------------------
    ladder = sha256(os.path.join(ROOT, "v3_Multimodal", "config", "ladder_freeze.json"))[:16]
    man_path = os.path.join(ROOT, "experiments", "sap", "manifest.json")
    man16 = sha256(man_path)[:16]
    man = json.load(open(man_path, encoding="utf-8"))
    mod_before = man["sap_amendment"]["module_sha_before"]
    sap_dir = os.path.join(ROOT, "v3_Multimodal", "src", "sap")
    live = {f: sha256(os.path.join(sap_dir, f)) for f in sorted(os.listdir(sap_dir))
            if f.endswith(".py")}
    changed_since_v10 = sorted(k for k in mod_before if live.get(k) != mod_before[k])
    g["G1_frozen_assets"] = {
        "ladder_freeze_sha16": ladder, "ladder_ok": ladder == EXPECT["ladder_freeze_sha16"],
        "sap_manifest_sha16": man16, "sap_manifest_ok": man16 == EXPECT["sap_manifest_sha16"],
        "sap_version": man["sap_version"], "n_sap_modules_live": len(live),
        "modules_differing_from_v1_0_baseline": changed_since_v10,
        "modules_note": "manifest 의 module_sha_before 는 v1.0 기준값이므로 A1~A6 로 재-hash 된 7모듈이 "
                        "다른 것이 정상이다. 본 블록은 이 목록이 docs/45 §3 기록과 같은지만 확인한다.",
        "pass": ladder == EXPECT["ladder_freeze_sha16"] and man16 == EXPECT["sap_manifest_sha16"],
    }

    # G2 v1 바이트 불변 ---------------------------------------------------
    g["G2_v1_immutable"] = {
        "md_sha16": sha256(V1_MD)[:16], "md_bytes": os.path.getsize(V1_MD),
        "docx_sha16": sha256(V1_DOCX)[:16], "docx_bytes": os.path.getsize(V1_DOCX),
        "pass": (sha256(V1_MD)[:16] == EXPECT["v1_md_sha16"]
                 and os.path.getsize(V1_MD) == EXPECT["v1_md_bytes"]
                 and sha256(V1_DOCX)[:16] == EXPECT["v1_docx_sha16"]
                 and os.path.getsize(V1_DOCX) == EXPECT["v1_docx_bytes"]),
    }

    # G3 sealed guard -----------------------------------------------------
    start = json.load(open(start_snap, encoding="utf-8"))
    start = {os.path.relpath(os.path.abspath(k), ROOT): v for k, v in start.items()}
    end = sealed_inventory()
    g["G3_sealed_guard"] = {
        "n_start": len(start), "n_end": len(end),
        "added": sorted(set(end) - set(start)), "removed": sorted(set(start) - set(end)),
        "changed": sorted(k for k in set(start) & set(end) if start[k] != end[k]),
        "pass": start == end,
    }

    # G4 봉인 계열 스캔(md·docx 전문) --------------------------------------
    md_text = open(V2_MD, encoding="utf-8").read()
    dx_text, dx_xml = docx_text(V2_DOCX)
    scan = {}
    for label, text in (("md", md_text), ("docx", dx_text)):
        key_hits = []
        for k in SEALED_KEYS:
            for m in re.finditer(re.escape(k), text):
                tail = text[m.end():m.end() + 40]
                # 값이 붙은 형태(= 0.12 / : 0.12 / 0.12) 만 위반으로 본다.
                if re.search(r"[=:]\s*[-+]?\d", tail) or re.search(r"^\s*[-+]?\d*\.\d", tail):
                    key_hits.append({"key": k, "context": text[max(0, m.start() - 40):m.end() + 40]})
        decimals = sorted(set(re.findall(r"(?<![\w.])\d*\.\d{2,}", text)))
        unlisted = [d for d in decimals if d not in DECIMAL_WHITELIST]
        signs = []
        for w in ("negative", "zero"):
            for m in re.finditer(w, text):
                ctx = text[max(0, m.start() - 30):m.end() + 30]
                if "positive/zero/negative" not in ctx.replace(" ", ""):
                    signs.append({"word": w, "context": ctx})
        scan[label] = {"key_with_value_hits": key_hits, "decimals_found": decimals,
                       "decimals_not_whitelisted": unlisted, "sign_disclosure_hits": signs,
                       "pass": not key_hits and not unlisted and not signs}
    g["G4_redaction_scan"] = {
        **scan,
        "note": "블록 I·K 의 키 목록을 그대로 쓰되, 본 문서는 동결 함수의 시그니처·반환필드를 "
                "의도적으로 인용하므로(지시서 M-1-8) '키 이름 등장'이 아니라 '키에 값이 붙은 형태'를 "
                "위반으로 정의했다. 값 스캔·부호 스캔이 실질 방어선이다.",
        "pass": scan["md"]["pass"] and scan["docx"]["pass"],
    }

    # G5 수치 ↔ facts 교차대조 --------------------------------------------
    facts = json.load(open(os.path.join(RUN, "facts_public.json"), encoding="utf-8"))
    e, s, pm, t = (facts["eligible_pt"], facts["scaffold_structure"],
                   facts["permutation_space"], facts["macro_ap_timing"])
    checks = {
        "n_drug_1092": "1,092" in md_text and facts["dataset"]["n_drug"] == 1092,
        "n_pt_370": "370" in md_text and facts["dataset"]["n_pt_columns"] == 370,
        "positives_19748": "19,748" in md_text and facts["dataset"]["n_positive_total"] == 19748,
        "groups_732": "732" in md_text and s["n_groups"] == 732,
        "singleton_627": "627 (85.7%)" in md_text and s["size_hist"]["size_1"] == 627,
        "max_group_78": "78 약물 (전체의 7.1%)" in md_text and s["max_group_size"] == 78,
        "kish_85_3": "85.3" in md_text and s["n_eff_clusters_kish"] == 85.3,
        "top2_155_14_2pct": "155 (14.2%)" in md_text
                            and s["top2_groups"]["combined_drugs"] == 155
                            and s["top2_groups"]["combined_share"] == 0.1419,
        "elig_370_both": "**370 / 370**" in md_text
                         and e["per_repeat"]["rep1"]["n_pt_rule_A3_both"] == 370,
        "elig_cluster_excludes_0": e["per_repeat"]["rep1"]["n_pt_failing_cluster_condition_only"] == 0,
        "min_pos_clusters_6": "최소값 = **6**" in md_text
                              and e["per_repeat"]["rep1"]["min_positive_scaffold_clusters_over_pts"] == 6,
        "fold_min_p_0625": "0.0625" in md_text
                           and pm["complement_symmetry"]["min_two_sided_p_fold_unit_5"] == 0.0625,
        "intersect_cells_124": "124" in md_text
                               and pm["unit_outer_fold_intersection_3repeats"]["n_units"] == 124,
        "timing_median": "0.1346 s" in md_text and t["median_s"] == 0.1346,
        "cost_i": "**2.99 시간**" in md_text and t["cost_estimate_B10000"]["serial_hours"] == 2.99,
        "cost_ii": "**7.48 시간**" in md_text
                   and t["cost_estimate_B10000"]["serial_hours_variant_ii"] == 7.48,
    }
    g["G5_number_crosscheck"] = {"checks": checks, "pass": all(checks.values())}

    # G6 md ↔ docx 동등성 --------------------------------------------------
    def norm(x):
        return re.sub(r"\s+", "", x)
    md_body = norm(re.sub(r"[|#>*`\-]", "", md_text))
    dx_body = norm(re.sub(r"[|#>*`\-]", "", dx_text))
    missing = [ln.strip() for ln in md_text.split("\n")
               if len(ln.strip()) > 25 and not ln.strip().startswith("|")
               and norm(re.sub(r"[|#>*`\-]", "", ln))[:60] not in dx_body]
    g["G6_md_docx_equivalence"] = {
        "md_chars": len(md_body), "docx_chars": len(dx_body),
        "n_tables_docx": dx_xml.count("<w:tbl>"),
        "n_tables_md": sum(1 for ln in md_text.split("\n")
                           if re.match(r"^\|[\s:\-|]+\|$", ln.strip())),
        "missing_lines": missing[:5], "n_missing": len(missing),
        "pass": not missing,
    }

    # 무결성 자기진술 ------------------------------------------------------
    res["integrity"] = {
        "open_sealed_calls": 0, "decision_functions_called": [], "multiplicity_applied": False,
        "emit_sign_called": False, "models_trained": 0, "new_oof": 0,
        "sealed_writes": 0, "network_calls": 0, "git_commit": False,
    }
    res["all_pass"] = all(v.get("pass") for v in g.values())

    out = os.path.join(RUN, "gates_public.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    assert json.load(open(out, encoding="utf-8")) == json.loads(json.dumps(res)), "roundtrip FAIL"
    print(json.dumps({k: v.get("pass") for k, v in g.items()}, ensure_ascii=False, indent=2))
    print("ALL PASS:", res["all_pass"])
    if not res["all_pass"]:
        print(json.dumps(res, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
