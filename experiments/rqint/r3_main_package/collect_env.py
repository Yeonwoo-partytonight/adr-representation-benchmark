"""collect_env.py — 실행 환경 명세 수집 (블록 AG · docs/91 AG-5).

목적
----
R3 2차 판정의 **게이트 G-ENV**(두 환경이 실제로 다름을 입증) 에 쓸 명세를 모은다.
1차 판정(바이트 동일)이 성립하면 이 파일은 참고자료로만 남는다.

⛔ PII 금지 (`docs/56` redaction 규칙)
  · hostname 은 **원문을 저장하지 않는다.** sha256 앞 12자리만 `host_id` 로 기록하고
    파일명도 `env_<host_id>.json` 을 쓴다(같은 기계는 같은 이름 → 구분 가능, 신원 노출 0).
  · 사용자명이 들어갈 수 있는 **절대경로는 수집하지 않는다.** `numpy.show_config` 안의
    경로형 문자열도 `<path-redacted>` 로 치환한다.
  · 로그인명·이메일·실명·학번은 수집 항목에 **없다.**

⛔ 계산 0 · 네트워크 0 · 파일 읽기 0(자기 자신 제외).

사용
----
    python3 collect_env.py                 # env_<host_id>.json 을 현재 디렉터리에 쓴다
    python3 collect_env.py out.json        # 경로 지정
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys

__all__ = ["collect", "redact_paths", "host_id"]

_PATH_PREFIXES = ("/Users/", "/home/", "/root/", "C:\\Users", "C:/Users", "/var/folders/")

_THREAD_ENVVARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                   "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")


def host_id() -> str:
    """hostname 의 sha256 앞 12자리. 원문은 저장하지 않는다."""
    try:
        h = socket.gethostname()
    except Exception:
        h = "unknown"
    return hashlib.sha256(h.encode("utf-8")).hexdigest()[:12]


def redact_paths(obj):
    """중첩 구조 안의 절대경로형 문자열을 `<path-redacted>` 로 치환한다."""
    if isinstance(obj, dict):
        return {k: redact_paths(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_paths(v) for v in obj]
    if isinstance(obj, str):
        if any(p in obj for p in _PATH_PREFIXES):
            return "<path-redacted>"
        return obj
    return obj


def _ver(mod):
    try:
        m = __import__(mod)
        return getattr(m, "__version__", "unknown")
    except Exception:
        return "not installed"


def _numpy_build():
    try:
        import numpy as np
    except Exception:
        return {"available": False}
    try:
        cfg = np.show_config(mode="dicts")
    except Exception:
        return {"available": False, "note": "show_config(mode='dicts') 미지원"}
    return {"available": True, "config": redact_paths(cfg)}


def collect():
    return {
        "_doc": ("R3 제2자 독립 재실행 — 환경 명세(블록 AG · docs/91 AG-5). "
                 "PII 금지 규칙 적용: hostname 원문·절대경로 미수집."),
        "host_id": host_id(),
        "host_id_note": "sha256(hostname)[:12] — 원문 미저장(docs/56 redaction)",
        "python_version": platform.python_version(),
        "sys_version": sys.version.replace("\n", " "),
        "sys_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "byteorder": sys.byteorder,
        "os_cpu_count": os.cpu_count(),
        "numpy": _ver("numpy"),
        "sklearn": _ver("sklearn"),
        "scipy": _ver("scipy"),
        "numpy_build_config": _numpy_build(),
        "thread_env": {k: os.environ.get(k) for k in _THREAD_ENVVARS},
        "collected_by": "collect_env.py (블록 AG · docs/91 AG-5)",
    }


def main(argv):
    env = collect()
    out = argv[1] if len(argv) > 1 else f"env_{env['host_id']}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: env[k] for k in
                      ("host_id", "python_version", "platform", "machine",
                       "numpy", "sklearn", "scipy", "os_cpu_count")},
                     ensure_ascii=False, indent=2))
    print(f"written = {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
