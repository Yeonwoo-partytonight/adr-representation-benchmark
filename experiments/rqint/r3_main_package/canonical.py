"""canonical.py — R3 비교객체 `numeric_core` 정규화 직렬화 (블록 AG · docs/91 AG-3).

목적
----
두 환경에서 나온 결과 JSON 을 **같은 방식으로** 바이트열로 만들어 sha256 을 비교한다.
환경·시각에 의존하는 필드는 **사전 고정된 제외 목록**에 따라 제거한다.
제외 목록은 트리거 사건(제2자 산출물 회수) **이전**에 고정되었으며, 이후 변경은
amendment 대상이다(`v3_Multimodal/config/r3_second_party_freeze.json`).

⛔ 무결성: 본 모듈은 계산을 하지 않는다. 파일 입출력과 문자열 정규화뿐이다.
   확증 데이터·봉인 산출물을 읽지 않는다.

사용
----
    python3 canonical.py probe_result.json                  # sha256 출력
    python3 canonical.py probe_result.json probe_numeric_core.sha256   # 파일로도 기록
"""
from __future__ import annotations

import hashlib
import json
import sys

__all__ = ["EXCLUDE_RULES", "EXCLUDE_POINTERS", "strip_excluded",
           "canonical_bytes", "numeric_core_sha256"]

# ═══════════════════════════════════════════════════════════════════════════
# 제외 규칙 — **6항**(구체 JSON pointer 는 8개). docs/91 AG-3 축자.
# ═══════════════════════════════════════════════════════════════════════════
EXCLUDE_RULES = [
    {"rule": 1, "pointers": ["/run_at_kst"],
     "reason": "실행 시각 — 환경·시점 의존"},
    {"rule": 2, "pointers": ["/wall_clock_seconds"],
     "reason": "벽시계 총 소요 — 하드웨어·부하 의존"},
    {"rule": 3, "pointers": ["/timing/per_permutation_seconds",
                             "/timing/per_reference_value_seconds"],
     "reason": "단가 2필드 — 하드웨어·부하 의존. timing 의 형상·개수 필드는 **남긴다**"},
    {"rule": 4, "pointers": ["/versions"],
     "reason": "패키지·플랫폼 버전 — 별도 대조표(G-ENV)로 비교하며 해시 대상이 아니다"},
    {"rule": 5, "pointers": ["/_doc", "/block", "/instruction"],
     "reason": "서술 문자열 — 지시서 문면 변화에 취약"},
    {"rule": 6, "pointers": [],
     "reason": ("확장 슬롯(현재 비어 있음) — 제외 목록을 늘리려면 amendment 가 필요하다. "
                "이 항목은 '지금 고정된 제외는 규칙 1~5 뿐'임을 명시하기 위한 자리다.")},
]

EXCLUDE_POINTERS = [p for r in EXCLUDE_RULES for p in r["pointers"]]


def _pop_pointer(obj, pointer):
    """JSON pointer(`/a/b`) 위치를 제거한다. 없으면 아무 것도 하지 않는다."""
    parts = [p for p in pointer.split("/") if p != ""]
    cur = obj
    for key in parts[:-1]:
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    if isinstance(cur, dict) and parts[-1] in cur:
        del cur[parts[-1]]
        return True
    return False


def strip_excluded(obj):
    """제외 목록을 적용한 **사본**을 반환한다(원본 무수정)."""
    core = json.loads(json.dumps(obj))          # deep copy (JSON 표현 그대로)
    removed = []
    for ptr in EXCLUDE_POINTERS:
        if _pop_pointer(core, ptr):
            removed.append(ptr)
    return core, removed


def canonical_bytes(obj) -> bytes:
    """★ 정규화 직렬화 — docs/91 AG-3 축자 고정. 이 한 줄이 비교의 정의다."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def numeric_core_sha256(obj):
    """(sha256hex, 제거된 pointer 목록, 바이트 길이)."""
    core, removed = strip_excluded(obj)
    b = canonical_bytes(core)
    return hashlib.sha256(b).hexdigest(), removed, len(b)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        obj = json.load(f)
    digest, removed, nbytes = numeric_core_sha256(obj)
    print(f"input                = {argv[1]}")
    print(f"excluded_applied     = {removed}")
    print(f"canonical_bytes      = {nbytes}")
    print(f"numeric_core_sha256  = {digest}")
    if len(argv) > 2:
        with open(argv[2], "w", encoding="utf-8") as f:
            json.dump({"numeric_core_sha256": digest,
                       "canonical_bytes": nbytes,
                       "excluded_pointers_applied": removed,
                       "exclude_pointers_declared": EXCLUDE_POINTERS,
                       "serialization": ('json.dumps(obj, sort_keys=True, ensure_ascii=False, '
                                         'separators=(",", ":")).encode("utf-8")'),
                       "source_file": argv[1]}, f, ensure_ascii=False, indent=2)
        print(f"written              = {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
