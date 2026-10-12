#!/usr/bin/env python3
"""verify_block_O_suspend_fold.py — 블록 O 자진 추가 검증(지시서 미요구).

배경
----
블록 O 본계산 중 **임계 배터리 강제 슬립**이 발생했다(pmset 실측: 2026-08-06 15:39:42
`BatteryHealth Warning level: 3 cap: 2` 직후 시스템 정지, AC 연결로 복귀). 15 model-fold 중
**rep1 fold3 하나만** 서스펜드 경계를 걸친다(fold2 완주 15:42:10 → fold3 완주 17:16:10,
그러나 fold3 자신의 `perf_counter` wall 은 287.9s 로 다른 fold 와 같은 범위).

프로세스 서스펜드·재개는 메모리 상태를 그대로 보존하므로 계산을 오염시킬 수 없다. 그러나 그것은
**논증**이지 측정이 아니다. 본 스크립트는 그 fold 하나를 같은 코드경로로 재계산해 저장된 부분
산출과 **바이트 동일**함을 확인해 논증을 측정으로 바꾼다.

⛔ 개봉 0 · `emit_sign` 0 · Δ·지표·CI·p 산출 0 · `decision.py` 0 · 기존 산출물 **쓰기 0**
   (부분 산출은 **읽기만**) · 재튜닝 0 · split 재추첨 0 · 네트워크 0 · git 0.
   재계산본은 **저장하지 않고 폐기**한다(블록 O O-3-1 과 같은 규약).

실행: .venv/bin/python3 v3_Multimodal/src/verify_block_O_suspend_fold.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from compute_lock import ComputeLock, gate_a_load, gate_b_exclusive      # noqa: E402
from confirmatory_oof_rftuned import (                                   # noqa: E402
    MODEL, MorganBlockR3, load_freeze, tuned_rf_kw, predict_fold_tuned,
    partial_path, sealed_guard_snapshot, assert_guard_unchanged, BASE_DIR,
)
from confirmatory_oof_rest import fold_of_row_for                        # noqa: E402
from ladder_confirmatory import load_frozen                              # noqa: E402

REP, FOLD = 1, 3           # 서스펜드 경계를 걸친 유일한 model-fold


def main():
    gates = {"A": gate_a_load("블록 O 자진검증 진입"),
             "B": gate_b_exclusive("블록 O 자진검증")}
    guard0 = sealed_guard_snapshot()

    fz = load_freeze()
    rf_kw = tuned_rf_kw(fz)
    d = load_frozen()
    Y = d["Ym"]
    b3 = MorganBlockR3(d["X"]["smiles_canonical"].tolist(), d["cid_order"])

    fr = fold_of_row_for(REP, d["cid_order"])
    te = np.where(fr == FOLD)[0]
    tr = np.where(fr != FOLD)[0]

    t0 = time.perf_counter()
    b3.fit(tr)
    assert int(b3._fit_rows_mask.sum()) == 0, "B0_r3 fit 모집단이 공집합이 아니다"
    P, dim = predict_fold_tuned(b3, tr, te, Y, rf_kw)
    wall = time.perf_counter() - t0

    stored_path = partial_path(REP, FOLD)
    stored = np.load(stored_path)
    same = (P.dtype == stored.dtype and P.shape == stored.shape
            and P.tobytes() == stored.tobytes())

    out = {
        "purpose": ("블록 O 자진 추가 검증 — 임계 배터리 강제 슬립 구간을 걸친 유일한 "
                    "model-fold(rep1 fold3)의 결정성을 재계산으로 확인"),
        "model": MODEL, "repeat": REP, "fold": FOLD,
        "n_train": int(len(tr)), "n_test": int(len(te)), "dim": int(dim),
        "dtype_recomputed": str(P.dtype), "dtype_stored": str(stored.dtype),
        "shape_recomputed": list(P.shape), "shape_stored": list(stored.shape),
        "byte_identical": bool(same),
        "recompute_wall_s": wall,
        "stored_partial": os.path.relpath(stored_path, ROOT),
        "gates": gates,
        "note": ("재계산본은 저장하지 않고 폐기했다. 저장된 부분 산출은 읽기만 했고 "
                 "어떤 봉인 산출물도 수정하지 않았다. Δ·지표·CI·p·부호 산출 0."),
    }
    guard1 = sealed_guard_snapshot()
    out["sealed_guard_check"] = assert_guard_unchanged(guard0, guard1, "자진검증")
    assert out["sealed_guard_check"]["n_added_own"] == 0, "자진검증이 파일을 새로 만들었다"

    p = os.path.join(BASE_DIR, "suspend_fold_recheck_public.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"[자진검증] rep{REP} {MODEL} fold{FOLD} 재계산 — "
          f"바이트 동일 = {same} | wall {wall:.1f}s (수치 미기록)")
    print(f"[자진검증] sealed guard 불변 {out['sealed_guard_check']} · 산출 파일 신규 0")
    print(f"[자진검증] 기록 = {os.path.relpath(p, ROOT)}")
    assert same, "❌ 서스펜드 구간 fold 재계산이 저장본과 다르다 — 즉시 보고"


if __name__ == "__main__":
    with ComputeLock(script="verify_block_O_suspend_fold.py", role="runner"):
        main()
