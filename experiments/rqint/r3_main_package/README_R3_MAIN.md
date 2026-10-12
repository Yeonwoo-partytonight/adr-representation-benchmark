# R3 본 실행 — 실행 안내

지난번 점검(`r3_package`)에 이어 부탁드리는 **본 실행 1건**입니다.
이번 결과가 논문 통계 검토 조건(제2자 독립 재실행)의 대조에 쓰입니다.

---

## 소요 시간

제 Mac 기준 약 **17분**이었습니다. 지난번 점검 속도로 보면 선배님 PC 에서는
**1시간~1시간 30분** 정도 걸릴 수 있습니다.
실행 중에는 터미널 창을 닫지 말아 주시고, PC 가 절전 모드로 들어가지 않게 해 주세요.

## 준비

압축을 풀면 `r3_main_package` 폴더가 생깁니다. 터미널(명령 프롬프트 또는 PowerShell)에서
그 폴더로 이동해 주세요.

파이썬은 **지난번 점검 때 만든 가상환경(`r3env`)을 그대로** 씁니다.
아래 명령의 `<r3env>` 자리에 그 폴더 경로를 **꺾쇠 괄호 없이** 넣어 주세요
(예: 지난번 `r3_package` 폴더 안에 만드셨다면 `C:\...\r3_package\r3env\Scripts\python.exe collect_env.py`).

## 실행 — Windows (4줄, 한 줄씩)

```
<r3env>\Scripts\python.exe collect_env.py
<r3env>\Scripts\python.exe -X utf8 v3_Multimodal\src\run_rqint_audit.py
<r3env>\Scripts\python.exe canonical.py experiments\rqint\audit_r6.json audit_numeric_core.sha256
<r3env>\Scripts\python.exe package_hashes.py
```

- 두 번째 줄이 오래 걸리는 본 계산입니다. 마지막에 `[완료] ...s` 가 나오면 끝난 것입니다.
- 두 번째 줄의 `-X utf8` 은 빼지 말아 주세요. 출력에 특수문자가 있어서 Windows 에서는
  이 옵션이 없으면 실행 환경에 따라 첫 줄에서 멈출 수 있습니다.
- 지난번 가상환경을 지우셨다면 이 폴더에서 먼저 아래 2줄을 실행하고, 위 명령의 `<r3env>` 를
  `.\r3env` 로 바꿔 주세요.

```
python -m venv r3env
.\r3env\Scripts\python.exe -m pip install -r requirements_r3.txt
```

## 실행 — macOS / Linux

```
<r3env>/bin/python collect_env.py
<r3env>/bin/python -X utf8 v3_Multimodal/src/run_rqint_audit.py
<r3env>/bin/python canonical.py experiments/rqint/audit_r6.json audit_numeric_core.sha256
<r3env>/bin/python package_hashes.py
```

## 보내주실 것 (4개)

1. `env_` 로 시작하는 `.json` 파일 (폴더 맨 위에 생깁니다)
2. `experiments/rqint/audit_r6.json`
3. `audit_numeric_core.sha256`
4. `package_hashes.json`

`experiments/rqint/run.log` 에는 컴퓨터 사용자 폴더 경로가 찍히므로 보내지 않으셔도 됩니다.

---

## 이게 뭔가요

- 입력은 전부 난수로 만든 **합성 데이터**입니다. 실제 연구 데이터는 이 패키지에
  한 바이트도 들어 있지 않습니다.
- 스크립트는 네트워크에 접속하지 않고, 기존 파일을 지우거나 고치지 않습니다.
  이 폴더 안에 결과 파일만 새로 만듭니다.
- **정답값은 일부러 넣지 않았습니다.** 보내주신 결과를 저희가 받아서 대조합니다.
  (기대값을 먼저 알려드리면 "독립 확인"의 의미가 없어집니다.)
- 폴더 안의 코드 파일은 수정하지 말아 주세요. `package_hashes.json` 은 실행한 파일이
  배포본과 같은지 확인하는 용도입니다.

## 파일 구성

| 경로 | 설명 |
|---|---|
| `v3_Multimodal/src/run_rqint_audit.py` | 본 계산 스크립트 (동결본 그대로) |
| `v3_Multimodal/src/sap/` | 동결된 계산 모듈 14개 |
| `collect_env.py` | 환경 명세 수집 (컴퓨터 이름은 해시 앞 12자리만 기록) |
| `canonical.py` | 결과 JSON → 비교용 해시 |
| `package_hashes.py` | 패키지 파일 해시 목록 |
| `requirements_r3.txt` | 권장 버전 (가상환경을 새로 만들 때만 사용) |

문제가 생기면 오류 메시지를 그대로 보내주시면 됩니다. 감사합니다!
