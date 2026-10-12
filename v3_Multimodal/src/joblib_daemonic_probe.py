#!/usr/bin/env python3
"""joblib_daemonic_probe.py — joblib(loky) daemonic 강등 사실 확인 (블록 E-4 증거).

배경
----
블록 D 의 D-3·D-4 는 `multiprocessing.Pool` 워커 안에서
`MultiOutputClassifier(n_jobs=18)` 을 호출했다. Pool 워커는 **daemonic** 이므로
joblib 의 loky 백엔드는

    UserWarning: Loky-backed parallel loops cannot be called in a multiprocessing,
                 setting n_jobs=1

과 함께 프로세스 팬아웃을 **무음으로 `n_jobs=1` 로 강등**한다. 즉 D-3·D-4 의 모든
워커는 **배정 코어 수와 무관하게 내부 직렬**로 실행됐다.

본 스크립트는 그 사실을 **introspection 만으로** 확인한다.
  · 모델 학습 0 · permutation 0 · 실제 데이터 미접근 · 네트워크 0.
  · `joblib.delayed(len)([1,2,3])` 이라는 자명한 작업만 돌린다.

실행: .venv/bin/python3 v3_Multimodal/src/joblib_daemonic_probe.py
산출: experiments/runs/v3_null_probe2_compute/_evidence/joblib_daemonic_probe.json
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import platform
import sys
import warnings
from datetime import datetime, timedelta, timezone

import joblib
import sklearn

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
KST = timezone(timedelta(hours=9))
OUT = os.path.join(ROOT, "experiments", "runs", "v3_null_probe2_compute",
                   "_evidence", "joblib_daemonic_probe.json")

N_JOBS_REQUESTED = 18


def _measure():
    """현재 프로세스에서 joblib 병렬도를 관측 (학습 없음)."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        par = joblib.Parallel(n_jobs=N_JOBS_REQUESTED)
        result = par(joblib.delayed(len)([1, 2, 3]) for _ in range(3))
        eff = joblib.effective_n_jobs(N_JOBS_REQUESTED)
        msgs = [str(x.message) for x in w]
    proc = mp.current_process()
    return {
        "process_name": proc.name,
        "daemonic": bool(proc.daemon),
        "n_jobs_requested": N_JOBS_REQUESTED,
        "effective_n_jobs": eff,
        "warnings": msgs,
        "trivial_result": result,
    }


def _worker(_):
    return _measure()


def main():
    parent = _measure()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=2) as pool:
        child = pool.map(_worker, [0])[0]

    downgraded = (child["effective_n_jobs"] == 1
                  and parent["effective_n_jobs"] == N_JOBS_REQUESTED
                  and child["daemonic"] and not parent["daemonic"])

    rec = {
        "_scope": ("joblib daemonic 강등 사실 확인 — introspection 전용. "
                   "모델학습 0 · permutation 0 · 실제 데이터 미접근 · 네트워크 0."),
        "NOT_AN_ANALYSIS_RESULT": True,
        "enters_null_distribution": False,
        "ts_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "versions": {
            "joblib": joblib.__version__,
            "sklearn": sklearn.__version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "parent_non_daemonic": parent,
        "pool_worker_daemonic": child,
        "daemonic_downgrade_confirmed": downgraded,
        "interpretation": (
            "multiprocessing.Pool 워커는 daemonic 이므로 loky 백엔드가 n_jobs=1 로 강등된다. "
            "따라서 블록 D 의 D-3·D-4 워커 내부 MultiOutputClassifier 는 요청값(18)과 무관하게 "
            "**직렬(n_jobs=1)** 로 실행됐다. 이는 실행 형태(시간)에만 관여하며 예측 배열의 "
            "비트 동일성에는 영향이 없다(D-2·D-3 G1·D-4 의 0-diff 증명이 그대로 유효)."),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)

    print(f"joblib {joblib.__version__} · sklearn {sklearn.__version__}")
    print(f"  parent  daemonic={parent['daemonic']} effective_n_jobs={parent['effective_n_jobs']} "
          f"warnings={len(parent['warnings'])}")
    print(f"  worker  daemonic={child['daemonic']} effective_n_jobs={child['effective_n_jobs']} "
          f"warnings={child['warnings']}")
    print(f"  daemonic_downgrade_confirmed = {downgraded}")
    print(f"  → {os.path.relpath(OUT, ROOT)}")
    return 0 if downgraded else 1


if __name__ == "__main__":
    sys.exit(main())
