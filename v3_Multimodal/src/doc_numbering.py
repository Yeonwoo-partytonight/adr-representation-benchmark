#!/usr/bin/env python3
"""doc_numbering.py — `docs/33` 세부 항목번호 계산·중복검출 (블록 E-2).

배경
----
`null_probe2_record.py` 는 세부 항목 헤더 번호를 **"16." 으로 하드코딩**하고 있었다.
그 결과 `record_cd_corrections.py` 가 이미 쓴 `16.` 과 충돌해 `docs/33` 에 같은
번호가 2회 등장한다(2026-07-27 계열 / 2026-07-28 계열). 본 모듈은 문서를 **실제로
판독**해 다음 번호를 계산하고, 새로 쓰는 번호가 중복이 아님을 assert 한다.

append-only 원칙상 **이미 기록된 원문은 수정하지 않는다.** 기존 중복은 `docs/33`
항목17(블록 E)에서 후자를 `항목16-B` 로 **별칭 지정**해 해소하며, 그 사실을
`KNOWN_PREEXISTING_DUPLICATES` 로 명시 보존한다.

통계·수치와 무관한 문서 유틸리티다(동결 아티팩트 아님).
"""
from __future__ import annotations

import os
import re
from collections import Counter

ITEM_RE = re.compile(r"^(\d+)\. \*\*", re.M)

# append-only 원칙상 원문 수정이 불가능한 **기존** 중복.
#   docs/33 의 `16.` 2건 = ① 블록 C compute 조건 + 블록 D 측정 규약 보정(2026-07-27)
#                          ② §13-4 병렬 실행 구성 확정(2026-07-28) → 별칭 `항목16-B`
# 신규 기입이 만드는 중복은 절대 허용하지 않는다(assert 실패).
KNOWN_PREEXISTING_DUPLICATES = {16}

ALIAS_SUFFIX_FOR_DUP = "-B"     # 같은 번호 2회차의 상호참조 별칭 (항목16 → 항목16-B)


def item_numbers(text: str):
    """`^\\d+\\. \\*\\*` 패턴의 항목번호를 등장 순서대로 반환."""
    return [int(m.group(1)) for m in ITEM_RE.finditer(text)]


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def next_item_number(path_or_text: str) -> int:
    """문서를 실제 판독해 **최대 번호 + 1** 을 계산한다(항목 없으면 1)."""
    text = read_text(path_or_text) if os.path.exists(path_or_text) else path_or_text
    nums = item_numbers(text)
    return max(nums) + 1 if nums else 1


def duplicate_item_numbers(text: str):
    """중복 등장한 항목번호 → {번호: 등장횟수}."""
    return {n: c for n, c in Counter(item_numbers(text)).items() if c > 1}


def assert_no_duplicate_item_numbers(path: str, allow=KNOWN_PREEXISTING_DUPLICATES):
    """중복 번호 검출 assert — 같은 번호가 2회 이상 등장하면 실패.

    `allow` 에 명시된 **기존** 중복만 예외로 통과시키고 결과에 그대로 보고한다.
    """
    text = read_text(path)
    dups = duplicate_item_numbers(text)
    unexpected = {n: c for n, c in dups.items() if n not in allow}
    assert not unexpected, (
        f"[번호중복 FAIL] {path} — 중복 항목번호 {unexpected} "
        f"(허용된 기존 중복 {sorted(allow)} 외). 신규 기입이 번호를 재사용했다.")
    return {"file": os.path.basename(path), "duplicates": dups,
            "preexisting_allowed": sorted(allow), "unexpected": unexpected, "pass": True}


def assert_number_written_once(before_text: str, after_text: str, n: int):
    """방금 쓴 번호 `n` 이 **기입 전 0회 → 기입 후 정확히 1회** 인지 확인."""
    b = item_numbers(before_text).count(n)
    a = item_numbers(after_text).count(n)
    assert b == 0, f"[번호중복 FAIL] 항목 {n} 이 기입 전에 이미 {b}회 존재"
    assert a == 1, f"[번호중복 FAIL] 항목 {n} 이 기입 후 {a}회 (기대 1회)"
    return {"number": n, "before": b, "after": a, "pass": True}


def crossref_label(before_text: str, n: int) -> str:
    """상호참조 문자열 — 같은 번호가 이미 있으면 별칭(`항목16-B`)을 붙인다."""
    seen = item_numbers(before_text).count(n)
    return f"항목{n}" if seen == 0 else f"항목{n}{ALIAS_SUFFIX_FOR_DUP}"


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "docs", "33_prereg_deviation_log.md")
    p = os.path.abspath(p)
    t = read_text(p)
    print(f"{os.path.relpath(p)}")
    print(f"  항목번호      = {item_numbers(t)}")
    print(f"  중복          = {duplicate_item_numbers(t)}")
    print(f"  다음 번호     = {next_item_number(p)}")
    print(f"  중복검출 assert = {assert_no_duplicate_item_numbers(p)}")
