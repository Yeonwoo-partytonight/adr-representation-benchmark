#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SAP 1.2 매니페스트 erratum 패치 (D20 · 채택안 B-2) — **SAP 모듈 아님**.

이 파일은 `v3_Multimodal/src/sap/` **밖**에 있다. SAP 11모듈에 포함되지 않으며
`manifest.modules` 의 해시 대상이 아니다. 계산·모델·봉인 데이터에 일절 접근하지 않는다.

무엇을 하는가 (docs/100 AL-4 · docs/101 §1)
-------------------------------------------
1. `multiplicity_manifest` 의 각 슬롯에 `primary_model_family`(문자열) 와
   `families_compared`(문자열 리스트) 를 **추가**한다. 기존 `model_family` 키는
   **값·위치 모두 보존**(삭제·수정 0).
2. 최상위에 `erratum` 블록을 추가한다 — `d20` 키에 D20 요구 6요소 + 도출 규칙.

멱등(idempotent)
----------------
이미 패치된 매니페스트에 다시 적용하면 **바이트 0 변경**이다.
(사이드카는 매니페스트로부터 결정적으로 재산출되므로 역시 바이트 동일.)

사용
----
    python3 v3_Multimodal/src/sap_manifest_erratum.py [--manifest PATH] [--check]

`--check` 는 패치 여부만 판정하고 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

MANIFEST_DEFAULT = "experiments/sap/manifest.json"
SIDECAR_DEFAULT = "experiments/sap/sap_manifest_erratum_d20.json"

# ── 확정값 (docs/101 §1-1 · 사용자 확정 2026-08-25 · 러너 재논의 금지) ──────────
PRIMARY_MODEL_FAMILY = "RF"                 # 연구 수준 사실 — 7슬롯 전건 공통
FAMILIES_COMPARED_DEFAULT = ["RF"]          # 슬롯 ②~⑦
FAMILIES_COMPARED_INTERACTION = ["RF", "GIN"]   # 슬롯 ⑧ (RQ-int) 만
INTERACTION_SLOT_ID = "⑧"

MODEL_FAMILY_LEGACY = "RF primary confirmatory (RF-Morgan+seq)"
N_SLOTS_PER_BLOCK = 7
BLOCKS = (("frozen_parameters", "decision_A11"), ("validation", "decision_A11"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dump(obj) -> str:
    """freeze.py L696 과 **동일한 직렬화**: indent=2 · ensure_ascii=False · 말미 개행 없음."""
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _slots(manifest: dict):
    """(블록경로, 슬롯리스트) 를 순서대로 내준다."""
    for a, b in BLOCKS:
        yield f"{a}.{b}.multiplicity_manifest", manifest[a][b]["multiplicity_manifest"]


def is_applied(manifest: dict) -> bool:
    if "erratum" not in manifest or "d20" not in manifest.get("erratum", {}):
        return False
    for _, slots in _slots(manifest):
        for s in slots:
            if "primary_model_family" not in s or "families_compared" not in s:
                return False
    return True


def families_for(slot_id: str) -> list:
    """★ 도출 규칙 — 슬롯 ⑧(RQ-int)만 두 family, 나머지는 RF 내부 대비."""
    return list(FAMILIES_COMPARED_INTERACTION) if slot_id == INTERACTION_SLOT_ID \
        else list(FAMILIES_COMPARED_DEFAULT)


def add_fields(manifest: dict) -> dict:
    """1단계 — 슬롯 2필드 추가. 기존 `model_family` 는 손대지 않는다."""
    for _, slots in _slots(manifest):
        assert len(slots) == N_SLOTS_PER_BLOCK, f"슬롯 수 {len(slots)} ≠ {N_SLOTS_PER_BLOCK}"
        for s in slots:
            assert s["model_family"] == MODEL_FAMILY_LEGACY, "기존 model_family 문자열 불일치"
            s["primary_model_family"] = PRIMARY_MODEL_FAMILY
            s["families_compared"] = families_for(s["id"])
    return manifest


def build_erratum(before_sha: str, line_diff: str, slot_map: dict) -> dict:
    """2단계 — D20 요구 6요소 + 도출 규칙(기계 판독 가능)."""
    return {
        "_doc": ("SAP 1.2 재동결(R2) 시 적용된 매니페스트 erratum. 조용한 수정 금지 원칙에 따라 "
                 "전후 문자열·전후 sha256·라인 diff·모듈 해시 불변 사실을 기록한다. "
                 "적용 주체 = v3_Multimodal/src/sap_manifest_erratum.py (SAP 모듈 아님)."),
        "d20": {
            "id": "D20",
            "source_of_requirement": [
                "docs/84_rqint_reviewer_response_triage.md (D1~D22 정본, D20)",
                "docs/99_amendment_section8_draft.md §4 (B-2 문안)",
                "docs/100_r2_sap12_freeze_prompt_for_vscode.md §0 B · AL-4",
                "docs/101_r2_sap12_freeze_resume_prompt_for_vscode.md §1 (값 확정)",
            ],
            "adopted_option": "B-2 — decision.py 무수정 · manifest 에만 필드 추가",
            "classification": "non-substantive metadata labelling erratum (비실질 표기 정정)",
            "numerical_impact": "none",
            "numerical_impact_basis": (
                "`model_family` 를 읽는 코드가 저장소 전역 0곳이고 Holm 보정은 `HOLM_FAMILY` 만 "
                "사용한다(블록 AK 실측 = experiments/rqint/r2_prep/impact.json:conflict_B). "
                "신규 2필드도 동일하게 어떤 계산에서도 읽히지 않는다."
            ),

            # ── ① 전후 문자열 ────────────────────────────────────────────────
            "element_1_before_after_string": {
                "before": {
                    "schema": {"model_family": MODEL_FAMILY_LEGACY},
                    "n_locations": N_SLOTS_PER_BLOCK * len(BLOCKS),
                    "locations": [f"{p}[0..{N_SLOTS_PER_BLOCK - 1}].model_family"
                                  for p, _ in [(f"{a}.{b}.multiplicity_manifest", None) for a, b in BLOCKS]],
                    "defect": ("한 문자열이 «연구 수준 primary family» 와 «슬롯 수준 비교 대상» 을 "
                               "뭉뚱그려, 두 family 가 걸리는 슬롯 ⑧(RQ-int)까지 동일하게 "
                               f"'{MODEL_FAMILY_LEGACY}' 로 적혀 있었다. D20 이 지적한 결함이 정확히 이것이다."),
                },
                "after": {
                    "schema": {
                        "model_family": MODEL_FAMILY_LEGACY + "  (축자 보존 — 삭제·수정 0)",
                        "primary_model_family": PRIMARY_MODEL_FAMILY,
                        "families_compared": "슬롯별 리스트 (아래 derivation_rule 참조)",
                    },
                    "n_locations_added": N_SLOTS_PER_BLOCK * len(BLOCKS),
                    "resolution": ("두 필드로 분리하면 연구 수준 사실과 슬롯 수준 사실이 나뉘고 "
                                   "슬롯 ⑧ 의 표기 결함이 해소된다."),
                },
                "model_family_preserved": True,
            },

            # ── ② 전후 sha16 = manifest.json 의 패치 전/후 ──────────────────
            "element_2_manifest_sha256": {
                "_note": ("docs/100 §0 B 결정 — «전후 sha16» 은 `experiments/sap/manifest.json` 을 "
                          "가리킨다(모듈 해시 아님)."),
                "v1_1_baseline_before_R2": {
                    "sha256_16": "756d485feb4715e9",
                    "bytes": 40130,
                    "what": "R2 착수 시점의 SAP 1.1 매니페스트 (freeze.py 재실행 이전)",
                },
                "before_patch": {
                    "sha256": before_sha,
                    "sha256_16": before_sha[:16],
                    "what": ("freeze.py(SAP 1.2) 재생성 직후 · 본 erratum 미적용 상태. "
                             "보존본 = experiments/rqint/r2_freeze_2/manifest_pre_erratum.json"),
                },
                "after_patch": {
                    "sha256": "SELF_REFERENTIAL_SEE_SIDECAR",
                    "_why": ("패치 후 매니페스트의 sha256 을 그 매니페스트 «안에» 적으면 자기참조라 "
                             "성립하지 않는다(적는 순간 해시가 바뀐다)."),
                    "recorded_in": [
                        SIDECAR_DEFAULT,
                        "experiments/sap/sap_1_2_hash_registry.json",
                        "docs/101_r2_sap12_freeze_resume_report.md",
                        "docs/33_prereg_deviation_log.md (해당 항목)",
                    ],
                },
                "reproducibility_note": ("매니페스트는 애초에 바이트 재현물이 아니다 — "
                                         "freeze.py L582 `frozen_at_kst = datetime.now(KST)` · "
                                         "L674 `versions` = 설치 패키지 버전."),
            },

            # ── ③ 라인 diff (manifest JSON 기준) ────────────────────────────
            "element_3_line_diff": {
                "_scope": ("패치 전 매니페스트 → 슬롯 2필드 추가만 적용한 매니페스트의 unified diff. "
                           "본 erratum 블록 자체의 추가분은 자기참조가 되므로 제외했다 "
                           "(그 추가분은 최상위 키 `erratum` 하나이며 기존 키 삭제·수정 0)."),
                "format": "unified diff (n=1) of json.dumps(indent=2, ensure_ascii=False)",
                "lines_added": N_SLOTS_PER_BLOCK * len(BLOCKS) * 2,
                "lines_removed": 0,
                "diff": line_diff.splitlines(),
            },

            # ── ④ 기존 모듈 해시 불변 명시 ──────────────────────────────────
            "element_4_module_hashes": {
                "statement": ("SAP 11모듈 중 `decision.py` 를 포함한 10개는 해시 불변이다. "
                              "11번째 등재 파일 `freeze.py` 만 버전 리터럴 1행(L581 `\"1.1\"` → `\"1.2\"`) "
                              "때문에 바뀐다. 그 줄은 매니페스트에 기록될 뿐 어떤 계산에서도 읽히지 않는다."),
                "unchanged_modules": 10,
                "changed_modules": 1,
                "freeze_py": {"before_sha256_16": "94e6369fa952be7f",
                              "after_sha256_16": "8bef5f70d168c50d",
                              "bytes": 42927, "changed_lines": 1, "changed_line_no": 581},
                "decision_py": {"sha256_16": "f688b20d816acabe", "changed_lines": 0},
            },

            # ── ⑤ decision.py 원천 7행 무수정 → 매니페스트 ≠ 코드 순수 재생성물 ──
            "element_5_decision_py_unmodified": {
                "statement": ("`model_family` 문자열의 원천은 `decision.py` 7행"
                              "(L61·65·69·73·77·81·85)이며 B-2 채택에 따라 **무수정**이다. "
                              "따라서 `freeze.py` 만으로 재생성한 매니페스트는 본 erratum 1건만큼 "
                              "현재 매니페스트와 다르다."),
                "source_lines_in_decision_py": [61, 65, 69, 73, 77, 81, 85],
                "manifest_differs_from_pure_regeneration_by": "exactly 1 recorded erratum patch",
            },

            # ── ⑥ reproduce 정밀화 ─────────────────────────────────────────
            "element_6_reproduce_refinement": {
                "statement": ("`reproduce` = `python3 v3_Multimodal/src/sap/freeze.py` **+ "
                              "`python3 v3_Multimodal/src/sap_manifest_erratum.py` 1회**. "
                              "후자는 멱등이며 SAP 모듈이 아니다."),
                "steps": [
                    "python3 v3_Multimodal/src/sap/freeze.py",
                    "python3 v3_Multimodal/src/sap_manifest_erratum.py",
                ],
                "erratum_script_is_sap_module": False,
                "erratum_script_idempotent": True,
            },

            # ── ★ 도출 규칙 (기계 판독 가능 — docs/101 §1-2) ────────────────
            "derivation_rule": {
                "_doc": "다음 사람이 두 필드의 값을 재도출할 수 있도록 규칙을 명시한다. 임의 작명이 아니다.",
                "primary_model_family": {
                    "level": "study",
                    "datatype": "string",
                    "value": PRIMARY_MODEL_FAMILY,
                    "constant_across_slots": True,
                    "rule": ("본 확증연구의 primary confirmatory family 는 RF 이며 슬롯과 무관하게 "
                             "동일하다. 그래서 7슬롯 공통이다."),
                },
                "families_compared": {
                    "level": "slot",
                    "datatype": "list[string]",
                    "rule": ("각 슬롯의 기존 `contrast` 문자열에서 **결정적으로 도출**한다 — "
                             "대비에 실제로 걸리는 model family 를 모두 적는다."),
                    "rule_short": "슬롯 ⑧ 만 [\"RF\",\"GIN\"], 나머지 6슬롯은 [\"RF\"].",
                    "mapping": slot_map,
                    "exception_slot_id": INTERACTION_SLOT_ID,
                    "exception_basis": (
                        "슬롯 ⑧ = interaction (RQ-int). 검정통계량이 `T = Δ_RF − Δ_GIN` "
                        "(v3_Multimodal/src/sap/rqint.py `TEST_STATISTIC` 축자) 이므로 "
                        "RF·GIN 두 family 가 걸린다."
                    ),
                    "non_exception_basis": (
                        "②~⑦ 은 M2b−P-ID · M2b−P-FAM · M2b vs 자연 임베딩 재배치 null · M2b−M0 · "
                        "M2b−tuned-RF baseline · RF-seq−RF 로 전부 RF family 내부 대비다."
                    ),
                },
            },

            "does_not_change": [
                "가설", "대비(contrast)", "크기 7의 고정 Holm family", "유의수준 α",
                "성공기준", "primary estimand", "봉인 산출물", "SAP 10모듈 해시",
            ],
        },
    }


def apply(manifest_path: Path, sidecar_path: Path, check_only: bool = False) -> int:
    before_sha = _sha256(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if is_applied(manifest):
        print(f"[erratum] 이미 적용됨 — 매니페스트 무변경 (sha256 {before_sha[:16]})")
        if not check_only:
            _write_sidecar(manifest_path, sidecar_path)
        return 0
    if check_only:
        print("[erratum] 미적용 상태")
        return 1

    # 1단계 — 슬롯 2필드 추가 (라인 diff 산출용으로 이 단계만의 전후를 뜬다)
    text_before = _dump(manifest)
    manifest = add_fields(manifest)
    text_fields_only = _dump(manifest)
    line_diff = "\n".join(difflib.unified_diff(
        text_before.splitlines(), text_fields_only.splitlines(),
        "manifest.json (freeze.py 재생성 직후)", "manifest.json (슬롯 2필드 추가 후)",
        n=1, lineterm=""))

    # 2단계 — erratum 블록
    slot_map = {}
    for _, slots in _slots(manifest):
        for s in slots:
            slot_map[s["id"]] = list(s["families_compared"])
    manifest["erratum"] = build_erratum(before_sha, line_diff, slot_map)

    _verify(manifest)
    manifest_path.write_text(_dump(manifest), encoding="utf-8")
    after_sha = _sha256(manifest_path)
    print(f"[erratum] 적용 완료 — before {before_sha[:16]} → after {after_sha[:16]}")
    _write_sidecar(manifest_path, sidecar_path)
    return 0


def _write_sidecar(manifest_path: Path, sidecar_path: Path) -> None:
    """자기참조를 피해 «패치 후» 해시를 밖에 기록한다. 매니페스트로부터 결정적."""
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    d20 = m["erratum"]["d20"]
    sidecar = {
        "_doc": ("매니페스트 erratum(D20) 의 «패치 후» sha256. 자기참조를 피하기 위해 "
                 "매니페스트 밖에 둔다. 생성 = v3_Multimodal/src/sap_manifest_erratum.py"),
        "manifest_path": str(manifest_path),
        "manifest_sha256_v1_1_baseline_before_R2":
            d20["element_2_manifest_sha256"]["v1_1_baseline_before_R2"]["sha256_16"],
        "manifest_sha256_before_patch": d20["element_2_manifest_sha256"]["before_patch"]["sha256"],
        "manifest_sha256_after_patch": _sha256(manifest_path),
        "manifest_bytes_after_patch": manifest_path.stat().st_size,
        "sap_version": m["sap_version"],
        "erratum_script_sha256": _sha256(Path(__file__)),
    }
    sidecar_path.write_text(_dump(sidecar), encoding="utf-8")
    print(f"[erratum] 사이드카 기록 — {sidecar_path} (after {sidecar['manifest_sha256_after_patch'][:16]})")


def _verify(manifest: dict) -> None:
    """docs/101 §1-3 값 검증 6조건. 어긋나면 즉시 예외."""
    n_slots = n_rf = n_list = n_interaction = n_default = n_model_family = 0
    for path, slots in _slots(manifest):
        assert len(slots) == N_SLOTS_PER_BLOCK, f"{path}: 슬롯 수 {len(slots)}"
        n_int_block = 0
        for s in slots:
            n_slots += 1
            assert "primary_model_family" in s and "families_compared" in s, f"{path}: 필드 누락"
            if s["primary_model_family"] == PRIMARY_MODEL_FAMILY:
                n_rf += 1
            if isinstance(s["families_compared"], list):
                n_list += 1
            if s["families_compared"] == FAMILIES_COMPARED_INTERACTION:
                n_int_block += 1
                n_interaction += 1
                assert s["id"] == INTERACTION_SLOT_ID, f"{path}: ['RF','GIN'] 슬롯 id={s['id']}"
            elif s["families_compared"] == FAMILIES_COMPARED_DEFAULT:
                n_default += 1
            if s.get("model_family") == MODEL_FAMILY_LEGACY:
                n_model_family += 1
        assert n_int_block == 1, f"{path}: ['RF','GIN'] 슬롯 {n_int_block}개 (기대 1)"
    total = N_SLOTS_PER_BLOCK * len(BLOCKS)
    assert n_slots == total and n_rf == total and n_list == total, "필드 존재·값 검증 실패"
    assert n_interaction == len(BLOCKS) and n_default == total - len(BLOCKS), "슬롯 분포 실패"
    assert n_model_family == total, f"기존 model_family {n_model_family}곳 (기대 {total})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SAP 1.2 manifest erratum (D20 · B-2) — 멱등")
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT)
    ap.add_argument("--sidecar", default=SIDECAR_DEFAULT)
    ap.add_argument("--check", action="store_true", help="판정만, 쓰기 0")
    a = ap.parse_args(argv)
    return apply(Path(a.manifest), Path(a.sidecar), check_only=a.check)


if __name__ == "__main__":
    sys.exit(main())
