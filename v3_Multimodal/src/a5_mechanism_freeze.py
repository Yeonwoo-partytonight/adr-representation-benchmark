#!/usr/bin/env python3
"""a5_mechanism_freeze.py — [블록 Y] Y-2. A5 정의 동결 (**네트워크 호출 이전**).

`docs/80` Y-2 전용. 커버리지를 보기 전에 정의를 고정한다.
정의·구간은 `docs/63` §2 표의 A5 행을 **축자로** 옮긴다(러너가 새로 만들지 않는다).

**네트워크 0 · 계산 0 · 라벨 접근 0.** 이 스크립트는 조회하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from compute_lock import ComputeLock, gate_b_exclusive           # noqa: E402

KST = timezone(timedelta(hours=9))
CFG = os.path.join(ROOT, "v3_Multimodal", "config")
OUT = os.path.join(CFG, "a5_mechanism_freeze.json")
D63 = os.path.join(ROOT, "docs", "63_unseen_proportion_axes_proposal.md")
PIF = os.path.join(CFG, "post_interim_freeze_v1_0.json")
PIF_STATUS = os.path.join(CFG, "post_interim_freeze_v1_0.status.json")
D77 = os.path.join(ROOT, "docs", "77_advisor_approval_20260806.md")

A5_ROW_LINENO = 41          # docs/63 §2 표 A5 행 (실측)


def now_kst():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    ts = now_kst()
    with ComputeLock(script="a5_mechanism_freeze.py", role="recorder"):
        gate_b_exclusive("a5_mechanism_freeze:entry")

        assert not os.path.exists(OUT), f"이미 존재 — 1회성 조건 위반: {OUT}"
        st = json.load(open(PIF_STATUS, encoding="utf-8"))
        assert st["a5_requery_executed"] is False, "a5_requery_executed 이미 true"
        assert st["unblinding_performed"] is False, "unblinding_performed true"

        d63_lines = open(D63, encoding="utf-8").read().splitlines()
        a5_row = d63_lines[A5_ROW_LINENO - 1]
        assert a5_row.startswith("| **A5 mechanism-target indicator**"), a5_row[:60]

        pif = json.load(open(PIF, encoding="utf-8"))
        axes = pif["axes_a3_a4_a6"]
        assert axes["A5_status"].startswith("NOT frozen here"), axes["A5_status"][:40]

        obj = {
            "_doc": (
                "A5(mechanism-target indicator) 축의 **정의 동결**. `docs/80` [블록 Y] Y-2. "
                "ChEMBL /mechanism 1회 재조회를 **시작하기 전에** 기입한다 — 커버리지를 보고 "
                "구간을 바꾸는 것을 구조적으로 막기 위함이다. 본 파일은 정의만 동결하며 "
                "A5 층화 계산·Δ·CI·p·라벨 결합은 **여기서 하지 않는다**(후속 블록)."),
            "block": "Y (docs/80_a5_mechanism_requery_prompt_for_vscode.md)",
            "frozen_at_kst": ts,
            "frozen_before_any_fetch": True,
            "frozen_before_any_fetch_evidence": (
                "본 파일은 재조회 러너(a5_mechanism_requery.py)보다 먼저 실행되며, 러너는 "
                "기동 시 본 파일의 frozen_at_kst 가 자신의 최초 네트워크 호출 시각보다 "
                "이르다는 것을 assert 한다(종료검증 #1)."),

            "definition": ("약물의 mechanism 표적 중 unseen 이 하나라도 있으면 1, 전부 seen 이면 0, "
                           "mechanism 표적이 없으면 no_mechanism"),
            "bins": ["{0}", "{1}", "no_mechanism"],
            "mechanism_source": "ChEMBL /mechanism (EMBL-EBI)",

            "definition_verbatim_source": {
                "path": "docs/63_unseen_proportion_axes_proposal.md",
                "section": "§2 제안 정의 (각 축 = 연속량 → 사전 고정 구간) — 표 A5 행",
                "lineno": A5_ROW_LINENO,
                "sha256": sha256_file(D63),
                "row_verbatim": a5_row,
            },

            "predecessor": {
                "path": "v3_Multimodal/config/post_interim_freeze_v1_0.json",
                "sha256": sha256_file(PIF),
                "axes_a3_a4_a6.A5_status": axes["A5_status"],
            },

            "advisor_status": {
                "explicitly_approved": (
                    "1회 재조회만. `docs/77_advisor_approval_20260806.md` §3 주석 1 — "
                    "우리 질문 「▶ 위 조건으로 1회 재조회를 승인해 주시겠습니까? "
                    "(승인 / 불승인·A5 미수행)」 에 대한 교수님 답 축자 = 「승인」."),
                "explicitly_approved_scope": "재조회(조회 행위)에 한정된다.",
                "definition_status": (
                    "내선 확정 — A3·A4·A6 과 동일 경로(`no_objection_raised`), 명시적 승인 아님"),
                "why_separated": (
                    "승인 문면은 조회 행위에 대한 것이고 A5 의 정의·구간에 대한 명시적 승인 문구는 "
                    "없다. 승인 범위를 부풀려 적지 않기 위해 두 항목을 분리 기재한다 — "
                    "`docs/77` §4 표 「내선 확정 9건 = no_objection_raised(≠ explicitly_approved)」 와 "
                    "동일한 구분이다."),
                "approval_record_sha256": sha256_file(D77),
                "approval_conditions_verbatim": st["a5_requery_conditions"],
            },

            "analysis_label": "현재 snapshot 기반 post-interim 보조분석",
            "analysis_label_source": "승인 조건 ④ 축자 (post_interim_freeze_v1_0.status.json "
                                     "a5_requery_conditions[3])",

            "shared_with_a3_a4_a6": {
                "_source": "v3_Multimodal/config/post_interim_freeze_v1_0.json "
                           "axes_a3_a4_a6 (인용 — 본 파일이 새로 정하지 않는다)",
                "no_target_handling_verbatim": axes["no_target_handling"],
                "no_target_excluded_n": 245,
                "reporting_form_verbatim": axes["reporting_form"],
                "resampling_verbatim": axes["resampling"],
                "contrasts_verbatim": axes["contrasts"],
                "stable_unstable_convention": (
                    "3반복에서 층이 일치하는 약물만 primary 층화 대상이고, 불일치 약물은 제외가 "
                    "아니라 `unstable_stratum` 으로 분리 집계·별도 보고한다(H-0-1). 구현 근거 = "
                    "`v3_Multimodal/src/stratification_run.py:772-785` `estimation_units()` "
                    "(kind=\"stable\" / \"unstable_stratum\")."),
                "resampling_constants_reused_from_blocks_H_L": {
                    "_source": "v3_Multimodal/src/stratification_run.py:65-69 (동결 상수)",
                    "SEED_BOOTSTRAP": 6001,
                    "SEED_SIGNFLIP": 6002,
                    "B_MAIN": 10000,
                    "BOOT_UNIT": "scaffold_cluster",
                    "PRIMARY_CI_METHOD": "BCa (v3_Multimodal/src/sap/bootstrap.py:37 "
                                         "PRIMARY_CI_METHOD; percentile 은 sensitivity)",
                },
                "new_seed_drawn": 0,
            },

            "not_frozen_here": ["A5 층화 계산", "Δ·CI·p", "라벨 결합"],
            "not_performed_in_this_block": {
                "label_join": False, "stratification": False, "delta_ci_p": False,
                "emit_sign": False, "decision_py": False, "unblinding": False,
            },
        }

        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")

        print(json.dumps({"written": os.path.relpath(OUT, ROOT),
                          "sha256": sha256_file(OUT),
                          "frozen_at_kst": ts}, ensure_ascii=False, indent=2))
        gate_b_exclusive("a5_mechanism_freeze:exit")


if __name__ == "__main__":
    main()
