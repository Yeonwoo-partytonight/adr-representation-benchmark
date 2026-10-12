"""package_hashes.py — R3 본 실행 패키지 파일 해시 목록 (블록 AP · docs/104).

실행한 패키지 파일이 배포본과 같은지 확인하기 위한 목록을 만듭니다.
파일을 읽어 해시만 계산하며, 네트워크 접속·파일 수정·삭제는 하지 않습니다.
결과 = 이 파일과 같은 폴더의 package_hashes.json

사용
----
    python package_hashes.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# 배포 파일 20개 — 경로 표기는 운영체제와 무관하게 '/' 로 고정한다(결과 키에 os.sep 이 섞이지 않게).
PACKAGE_FILES = [
    "README_R3_MAIN.md",
    "canonical.py",
    "collect_env.py",
    "package_hashes.py",
    "requirements_r3.txt",
    "v3_Multimodal/src/run_rqint_audit.py",
    "v3_Multimodal/src/sap/__init__.py",
    "v3_Multimodal/src/sap/bootstrap.py",
    "v3_Multimodal/src/sap/consensus.py",
    "v3_Multimodal/src/sap/decision.py",
    "v3_Multimodal/src/sap/freeze.py",
    "v3_Multimodal/src/sap/metrics.py",
    "v3_Multimodal/src/sap/null_generator.py",
    "v3_Multimodal/src/sap/redaction.py",
    "v3_Multimodal/src/sap/rqint.py",
    "v3_Multimodal/src/sap/rqint_audit.py",
    "v3_Multimodal/src/sap/rqint_synthetic.py",
    "v3_Multimodal/src/sap/signflip.py",
    "v3_Multimodal/src/sap/synthetic.py",
    "v3_Multimodal/src/sap/unseen_target.py",
]


def main():
    files = {}
    for rel in PACKAGE_FILES:
        path = os.path.join(ROOT, *rel.split("/"))
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            files[rel] = None
            continue
        files[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    n_missing = sum(1 for v in files.values() if v is None)
    result = {"n_files_listed": len(PACKAGE_FILES), "n_missing": n_missing, "files": files}
    with open(os.path.join(ROOT, "package_hashes.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"files={len(PACKAGE_FILES)} missing={n_missing} written=package_hashes.json")
    return 0 if n_missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
