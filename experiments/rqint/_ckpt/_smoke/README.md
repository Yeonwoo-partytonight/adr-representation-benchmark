# 하네스 end-to-end 스모크 증거 (블록 AE · 본런 아님)

2026-08-12 22:5x KST, **배터리 전원**에서 `--allow-battery` 로 실행한 하네스 검증 산출물.
C0:prop 의 r=0..3 (rep_seed 20260813~20260816) 4복제를 계산해 다음을 실증했다.

- 체크포인트 append / 재개 시 중복 0 (재개 시 20260813·20260814 건너뛰고 20260815·20260816 진행)
- 여집합 항등식 감사 1,000 draw · 실패 0 · max_abs_dev 0.0 · `complement_identity_used` true
- tie 율 0.0
- RAM 라이브 게이트 동작 (peak 0.76 GiB ≪ 임계 30.72 GiB)
- `--stage summary` · `rqint_calibration_verify.py` 독립 재계산 불일치 0
- rep_seed 20260815 의 `t_star_sha256` = `896e8292b078747c…` 가
  `calibration_determinism_C0_prop.json` 의 3번째 복제와 **바이트 동일**

★ **본런 체크포인트에서 분리 보관한다.** 이유 = AE-6 전원 규정상 본런은 AC 전원에서만 수행하며,
본런 산출은 AC 세션만으로 구성한다. 값 자체는 시드의 순수 함수라 전원과 무관하게 동일하지만,
복제별 `task_seconds` 가 배터리 구간 측정치이므로 본런 산출에 섞지 않는다.
본런은 이 4복제를 **처음부터 다시** 계산하며 바이트 동일해야 한다.
