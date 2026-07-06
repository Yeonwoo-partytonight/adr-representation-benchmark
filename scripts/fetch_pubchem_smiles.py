#!/usr/bin/env python3
"""fetch_pubchem_smiles.py — PubChem CID -> SMILES 배치 취득 (PUG-REST).

⚠️ 상태(2026-06-23): 03 명세 확정으로 **단일 라벨 = OnSIDES**가 됨. 따라서 CID는
   SIDER STITCH가 아니라 **OnSIDES 성분→CID 매핑(STEP3)** 에서 와야 한다. 아래 `--sider`
   입력 경로/stitch_to_cid()는 **이번 사이클 미사용**(비교 트랙용으로 남겨둠). 단,
   `fetch_smiles()`(CID→SMILES 코어, rate-limit·폴백)는 STEP4에서 그대로 재사용한다.
   STEP4 정식 모듈은 STEP1 스키마 확보 후 `pipeline/src/fetch_smiles.py`로 작성 예정.

배경(과거): SIDER는 약물을 STITCH ID(=PubChem CID 인코딩)로 식별 → CID->SMILES로 featurize.

입력: SIDER `meddra_all_se.tsv`(또는 CID 목록). STITCH ID 예: 'CID100000085'
  - STITCH flat 규약: 'CID1' + 9자리 zero-pad = flat compound. 실제 PubChem CID = int(자리수 제거).
  - 보수적으로: 숫자만 추출 후 앞자리 1(flat 표식) 처리. 아래 stitch_to_cid() 참고.
출력: data/processed/cid_smiles.csv  (cid, smiles, source_property)

⚠️ 미검증 주의: 에이전트 샌드박스에서 PubChem(pubchem.ncbi.nlm.nih.gov)이 차단되어
   실호출 검증을 못 했다. Mac에서 첫 실행 시 소량(--limit 5)으로 동작 확인 후 전체 실행 권장.
⚠️ PubChem 2025 변경: SMILES property 명칭이 'CanonicalSMILES'/'IsomericSMILES'에서
   'SMILES'/'ConnectivitySMILES' 등으로 바뀌었을 수 있어, 아래는 여러 후보를 순차 시도한다.

사용:
    python scripts/fetch_pubchem_smiles.py --sider data/raw/sider4.1/meddra_all_se.tsv --limit 5
    python scripts/fetch_pubchem_smiles.py --sider data/raw/sider4.1/meddra_all_se.tsv   # 전체
"""
from __future__ import annotations
import argparse, csv, os, sys, time, json, urllib.request, urllib.error

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
# 시도할 property 후보(2025 명칭 변경 대비). 앞에서부터 성공하는 것 사용.
SMILES_PROPS = ["IsomericSMILES", "CanonicalSMILES", "SMILES", "ConnectivitySMILES"]


def stitch_to_cid(stitch_id: str) -> int | None:
    """SIDER STITCH ID -> PubChem CID.
    STITCH는 'CID1xxxxxxxxx'(flat) / 'CID0xxxxxxxxx'(stereo) 형태. 숫자부에서 선행 식별자 제거.
    가장 안전한 변환: 'CID' 제거 -> 정수 -> 1e9를 뺀(또는 modulo) 실제 CID.
    실무 규약: int(digits) - 100000000 (flat) ... 버전마다 달라 둘 다 시도 가능하게 raw도 반환.
    """
    s = stitch_id.strip().upper().replace("CID", "")
    if not s.isdigit():
        return None
    n = int(s)
    # STITCH flat: 1,000,000,000 + cid  /  stereo: 0 + cid. 모듈로로 실제 CID 추출.
    cid = n % 1_000_000_000
    return cid or None


def fetch_smiles(cids: list[int], chunk: int = 100, sleep: float = 0.25) -> dict[int, tuple[str, str]]:
    """CID 리스트 -> {cid: (smiles, used_property)}. property 후보를 순차 시도."""
    out: dict[int, tuple[str, str]] = {}
    for prop in SMILES_PROPS:
        remaining = [c for c in cids if c not in out]
        if not remaining:
            break
        for i in range(0, len(remaining), chunk):
            batch = remaining[i:i + chunk]
            ids = ",".join(map(str, batch))
            url = f"{PUG}/compound/cid/{ids}/property/{prop}/JSON"
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    data = json.load(r)
                for row in data.get("PropertyTable", {}).get("Properties", []):
                    smi = row.get(prop)
                    if smi:
                        out[int(row["CID"])] = (smi, prop)
            except urllib.error.HTTPError as e:
                if e.code == 400:   # property 이름이 잘못됨 -> 다음 후보로
                    print(f"  [info] property '{prop}' 미지원(400) → 다음 후보 시도", file=sys.stderr)
                    break
                print(f"  [warn] HTTP {e.code} on batch {i}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"  [warn] {type(e).__name__} on batch {i}: {e}", file=sys.stderr)
            time.sleep(sleep)  # PubChem 권장: 초당 5요청 이하
    return out


def read_cids_from_sider(path: str) -> list[int]:
    """meddra_all_se.tsv에서 STITCH ID 컬럼을 읽어 고유 CID 리스트 반환.
    SIDER tsv는 헤더 없음; 1열=STITCH flat, 2열=STITCH stereo 가 일반적."""
    cids: set[int] = set()
    with open(path, newline="") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row:
                continue
            cid = stitch_to_cid(row[0])
            if cid:
                cids.add(cid)
    return sorted(cids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sider", help="SIDER meddra_all_se.tsv 경로")
    ap.add_argument("--cids", help="쉼표구분 CID 직접 지정(테스트용)")
    ap.add_argument("--limit", type=int, default=0, help="처음 N개만(스모크 테스트)")
    ap.add_argument("--out", default="data/processed/cid_smiles.csv")
    args = ap.parse_args()

    if args.cids:
        cids = [int(x) for x in args.cids.split(",")]
    elif args.sider:
        cids = read_cids_from_sider(args.sider)
    else:
        ap.error("--sider 또는 --cids 중 하나 필요")

    if args.limit:
        cids = cids[:args.limit]
    print(f"▶ 대상 CID {len(cids)}개")

    result = fetch_smiles(cids)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cid", "smiles", "source_property"])
        for cid in cids:
            smi, prop = result.get(cid, ("", ""))
            w.writerow([cid, smi, prop])
    got = sum(1 for c in cids if c in result)
    print(f"✅ {got}/{len(cids)} SMILES 취득 → {args.out}")
    if got < len(cids):
        print(f"  ⚠ {len(cids)-got}개 미취득(폐기약물/CID 변환 이슈). 로그 확인.")


if __name__ == "__main__":
    main()
