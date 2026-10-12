# 19. v3 멀티모달(DrugBank-free) 표적 매핑 Coverage 리포트

> 생성: `v3_Multimodal/src/coverage_mapping.py` (SEED=42, 요청 JSON 캐시 `data/processed/target_mapping/_cache/`).
> 근거 설계: `docs/18_sci_v3_paper_plan.md` §4.3, 지시 `docs/11_advisor_consult_submission.md` §3, 프롬프트 `docs/18b`.
> **범위**: 커버리지 측정만. 모델 학습·ProtBERT 임베딩 계산은 포함하지 않음(다음 마일스톤).
> 데이터 소스: **ChEMBL (EMBL-EBI) REST**, **UniProt (EMBL-EBI) REST**. DrugBank 미사용. BindingDB=아래 §비고 참조.

## 1. Coverage 표

| 단계 | 대상 | 성공 | 커버리지 % |
|---|---|---|---|
| C0 전체 | 1092 | 1092 | 100% |
| C1 InChIKey(로컬 RDKit) | 1092 | 1092 | 100.0% |
| C2 ChEMBL compound | 1092 | 943 | 86.4% |
| C3 ≥1 UniProt target ★ | 1092 | 880 | 80.6% |
| C4 서열 확보 | 1092 | 877 | 80.3% |
| C5 affinity 보유 | 1092 | 859 | 78.7% |

- 각 단계는 **분자(cid) 단위** 커버리지(분모 = 확정 분자셋 1,092).
- C2는 full InChIKey **정확 매칭**(ChEMBL `standard_inchi_key`) 기준 — stereo/염 형태 차이로 인한 미매칭은 보수적 하한.
- C3는 mechanism(MoA) + pChEMBL 보유 activity에서 얻은 표적 중 **SINGLE PROTEIN → UniProt accession** 이 잡힌 분자 수.

## 2. 분포·기여

- **약물당 UniProt 표적 수**(표적≥1 분자 880개 대상): 중앙값 **12**, 95퍼센타일 **70**, 범위 1~355.
- **유니크 UniProt 표적 수**: 전체 **2596** (그중 서열 확보 **2561**).
- **Human(Homo sapiens) 표적 유니크 수**: **1474**.
- **서열 길이 분포**(확보 2561): 중앙값 **490 aa**, 95퍼센타일 **1435 aa**, 범위 20~7096.
- **source별 기여**: ChEMBL = 전 표적(주소스). BindingDB = 미반영(아래 §비고).
- 표적 organism 상위:
  - Homo sapiens: 15781 (drug×target rows)
  - Rattus norvegicus: 2362 (drug×target rows)
  - Bacteria: 657 (drug×target rows)
  - Mus musculus: 514 (drug×target rows)
  - Bos taurus: 196 (drug×target rows)
  - Mycobacterium tuberculosis: 109 (drug×target rows)

## 3. 게이트 판정 (docs/18 §4.3)

- **C3 = 880/1092 = 80.6%** → **≥70% (80.6%) → 계획대로 M0~M4 전면 진행.**

C3 커버리지가 70% 이상이므로 표적 축을 전체 분자셋에 적용해 M0~M4 사다리와 ablation을 계획대로 진행한다. 비매핑 분자는 소수이므로 M0-only 보조 처리 또는 결측 표적 임베딩(마스킹)으로 흡수한다.

## 4. 산출물 · 재현 방법

```
data/processed/target_mapping/
  01_inchikey.csv    (cid, smiles, inchikey, ok)
  02_chembl.csv      (cid, inchikey, chembl_id, matched)
  03_targets.csv     (cid, inchikey, chembl_id, target_chembl_id, uniprot, organism, target_type, source, n_targets_per_drug)
  04_sequences.csv   (uniprot, seq_len, has_seq)
  05_affinity.csv    (inchikey, uniprot, has_affinity, value_type)
  _cache/            (요청 JSON/FASTA 캐시 — 재현·오프라인 재실행)
```

재실행:
```bash
python v3_Multimodal/src/coverage_mapping.py --step all
```
모든 HTTP 응답은 `_cache/`에 저장되어 동일 입력에 대해 결정적으로 재현된다(seed=42, 확률적 연산 없음).

## 5. 비고 · 한계 (정직 보고)

- **BindingDB 미반영**: 실행 시점(2026-07-14) BindingDB REST 엔드포인트(`axis2/services/BDBService/*`, `/rest/*`)가 404를 반환해 자동 수집 불가. 따라서 C3는 **ChEMBL 단독 하한**이며, BindingDB 보강 시 커버리지가 상승할 여지가 있다(향후 수동 병합 과제).
- **정확 InChIKey 매칭 한계**: stereo/염/호변이체 차이로 ChEMBL 미매칭이 발생할 수 있어 C2는 보수적. connectivity-layer(첫 14자) 매칭으로 완화 가능하나 본 측정은 정직한 정확매칭 기준을 채택.
- **표적 근거 기준**: activity는 `pchembl_value` 보유(표준화 효력값)만 채택 → 저신뢰 표적 배제. mechanism(MoA)은 큐레이션이라 무조건 포함.
- 이 리포트는 **구조·라벨·split 불변**(재다운로드/재학습 없음) 원칙을 지켰다.
