"""v3 SAP (Statistical Analysis Plan) 동결 모듈 — docs/41 (A6~A11 + redaction).

⛔ 무결성 최상위(절대 위반 금지)
  1. 이 패키지의 어떤 모듈도 확증용 split(seed 201~205 × 3반복)·confirmatory OOF·
     master_X/master_Y·scaffold_split.json 을 **생성/조회/import 하지 않는다.**
  2. 모든 함수는 **결정적·데이터-무관 순수 함수**다(입력 = 요약통계 또는 synthetic 생성기,
     출력 = 판정 라벨 / 통계량). 확증 값은 일절 포함하지 않는다.
  3. 등록된 설계·가설·집계·성공기준(docs/30 §5~§9)은 불변. 이 패키지는 등록된 분석의
     **구현 자유도만 제거**한다(정의 동결). 프로토콜은 고치지 않고 구현만 고친다.

모듈
  metrics.py       macro AP(사전등록 §7, ladder_confirmatory.macro_ap 정의와 동일) — 공유 헬퍼
  redaction.py     first-look redaction: emit_sign + sealed-path write API
  consensus.py     A8 — consensus OOF(§6 방법A)
  bootstrap.py     A7 — paired scaffold-cluster bootstrap (undefined-AP·BCa)
  signflip.py      A6 — scaffold-group sign-flip randomization (+ calibration audit)
  decision.py      A11 — RQ2/RQ3/RQ4 성공판정 · Holm · BH-FDR · SESOI/TOST 3분판정
  null_generator.py A9 — 자연 임베딩 재배치 null(§5) global·family-constrained
  unseen_target.py A10 — fold-local unseen-target 층화(§9) + sequence-novelty 층
  synthetic.py     검증용 가짜 데이터 생성기(확증 데이터와 무관)
  freeze.py        synthetic dry-run 검증 → 코드 미접근 스캔 → sha256 manifest 동결
"""
