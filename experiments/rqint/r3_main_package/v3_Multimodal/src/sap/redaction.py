"""redaction.py — first-look redaction (docs/41 §7, docs/40 §1, docs/36 §4-R).

목적: 확증 반복1의 **실질 블라인딩**. 사람·리포트·채팅에 노출되는 것은 Δ의 **부호 1개**뿐이며,
원시 macro AP·Δ 크기·per-PT·per-fold·확률 예측은 **sealed 경로**에만 저장하고 최초 접근
시각·조회자를 로깅한다. 공개 경로는 sign 필드만 담는다.

⚠️ 무결성: 본 모듈은 확증 데이터를 로드하지 않는다. `emit_sign`은 순수 함수이며, sealed I/O는
   경로·로그 규칙만 제공한다(값은 호출자가 넘긴 것). freeze.py가 synthetic으로 규칙을 검증한다.

⚠️ SESOI(=0.01)와 zero-tol(=1e-6)의 구분: `emit_sign`의 zero 임계는 순수 **부호 판정용**의 수치
   안정 임계이며, 성공판정의 SESOI(|Δ|≥0.01, decision.py)와 별개다(혼용 금지).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta

__all__ = ["ZERO_TOL", "emit_sign", "SealedStore"]

KST = timezone(timedelta(hours=9))

# zero 판정 임계(사전고정) — docs/36 §4 예시(|Δ|<1e-6). 결과 조회 전에 고정된 상수.
ZERO_TOL = 1e-6


def emit_sign(delta, zero_tol=ZERO_TOL):
    """Δ → 공개 가능한 부호 라벨. 공개 출력은 반드시 이 함수만 통과한다.

    반환: "positive" | "zero" | "negative". |delta| < zero_tol 이면 "zero".
    NaN은 "zero"로 처리하지 않고 ValueError(값 오류를 부호로 숨기지 않음)."""
    d = float(delta)
    if d != d:  # NaN
        raise ValueError("emit_sign: delta is NaN (부호 판정 불가 — 값 오류를 은폐하지 않음)")
    if abs(d) < float(zero_tol):
        return "zero"
    return "positive" if d > 0 else "negative"


class SealedStore:
    """sealed 경로 저장 + 공개 경로 분리 + 최초 접근 로깅.

    - `write_sealed(name, obj)`: 원시 수치(macro AP·Δ크기·per-PT·per-fold·확률)를 `_sealed/`에 저장.
    - `write_public(name, delta)`: 공개 경로에 **{"sign": ...}** 만 저장(emit_sign 통과).
    - `open_sealed(name, accessor)`: sealed 최초 접근 = 시각·조회자를 access log에 append 후 반환.
      성공판정 단계(3반복+null 완료) 전에는 호출하지 않는 것이 규칙(코드가 강제하진 않되 로깅으로 감사).
    """

    def __init__(self, run_dir):
        self.run_dir = run_dir
        self.sealed_dir = os.path.join(run_dir, "_sealed")
        self.access_log = os.path.join(self.sealed_dir, "access.log")

    def _ensure(self):
        os.makedirs(self.sealed_dir, exist_ok=True)

    def _now(self):
        return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

    def write_sealed(self, name, obj):
        self._ensure()
        p = os.path.join(self.sealed_dir, name)
        with open(p, "w") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        return p

    def write_public(self, name, delta):
        os.makedirs(self.run_dir, exist_ok=True)
        p = os.path.join(self.run_dir, name)
        with open(p, "w") as f:
            json.dump({"sign": emit_sign(delta)}, f, indent=2, ensure_ascii=False)
        return p

    def open_sealed(self, name, accessor):
        """sealed 파일을 연다 = 무결성 이벤트. 시각·조회자를 append-only 로깅."""
        self._ensure()
        line = f"{self._now()} | OPEN sealed/{name} | accessor={accessor}"
        with open(self.access_log, "a") as f:
            f.write(line + "\n")
        p = os.path.join(self.sealed_dir, name)
        with open(p) as f:
            return json.load(f)
