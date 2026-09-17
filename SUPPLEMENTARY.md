# 보충자료 (Supplementary Material)

**논문** 의약품 표지 기반 희소 다중라벨 ADR 예측에서 Morgan 지문 RandomForest와 결합 속성 미사용 GIN 기반 모델의 비교: 단일 스캐폴드 분할 연구
(*Morgan-Fingerprint Random Forest versus Bond-Attribute-Agnostic GIN-Based Models for Sparse Multi-Label Prediction of Drug-Label ADR Annotations: A Single-Scaffold-Split Study*)
— 한국정보전자통신기술학회논문지(KIIECT), 2026 게재 예정. 권·호·쪽·DOI는 게재 후 갱신한다.

이 파일은 위 논문의 보충자료(보충자료 표 S1)를 대신한다. 내용은 저장소 태그 `kci-2026-v1.0` 기준이다.

## 근거 파일

표 S1의 값은 아래 파일에서 확인할 수 있다. 각 표 아래 `근거:` 줄에 파일과 행 번호를 적었다(태그 `kci-2026-v1.0` 기준).

- (a) 지문 기반 모델: `v1_RF/src/config.yaml`, `v1_RF/src/train.py`, `v1_RF/src/fairtune.py`, `v1_RF/results_fairtune/best_config.yaml`
- (b)·(c) GNN: `v2_GNN/src/config.yaml`, `v2_GNN/src/graph_features.py`, `v2_GNN/src/models.py`, `v2_GNN/src/train.py`, `v2_GNN/src/train_improve.py`, `v2_GNN/results*/`
- (d) 표현–학습기 분리 구성: `v1_RF/src/repr_*.py`, `v1_RF/results_repr/best_config_{mlp,descrf}.yaml`, `v1_RF/results_repr/descriptor_preprocess.json`

---

## 보충자료 표 S1. 재현용 하이퍼파라미터 — 지문 기반 모델과 GNN 최종 구성

**Supplementary Table S1.** Reproducibility hyperparameters — fingerprint-based models and final GNN configuration

아래 값은 공개 저장소의 `config.yaml`과 모델 코드에서 확인한 실제 설정이다. 각 순차 탐색 라운드 내부의 조기 종료와 후보 선택은 validation macro AP를 기준으로 수행하였다. 다만 후보별 고정 evaluation 분할 성능이 각 라운드에서 산출된 뒤 후속 라운드가 진행되었으므로, 해당 분할은 전체 개발 과정에서 미열람된 확증용 test로 간주하지 않는다.

### (a) Fingerprint-based models

| Component | Value |
|---|---|
| Default RF `n_estimators` / `max_depth` | 300 / None |
| Default RF `class_weight` | balanced_subsample (applied per label-wise binary estimator) |
| Default RF `random_state` / `n_jobs` | 42 / −1 |
| Default RF multi-output implementation | `MultiOutputClassifier(RandomForestClassifier(...))` — 370 independent RFs, one per PT |
| XGBoost `n_estimators` / `max_depth` / `learning_rate` | 300 / 6 / 0.1 |
| XGBoost `subsample` / `colsample_bytree` | 0.8 / 0.8 |
| XGBoost `objective` / others | binary:logistic (default) · eval_metric = logloss · tree_method = hist · random_state = 42 · n_jobs = −1 |
| XGBoost early stopping / multi-output | Not used / label-wise loop of `XGBClassifier` (one-vs-rest per PT; labels without training positives are assigned probability 0) |
| XGBoost class imbalance | Label-wise `scale_pos_weight` = negatives / positives |
| Tuned RF search space | `n_estimators`{300,600,1000}, `max_depth`{None,20,40}, `max_features`{sqrt,log2,0.1}, `min_samples_leaf`{1,2,5}, `class_weight`{balanced,balanced_subsample,None}, Morgan{(r2,2048),(r2,4096),(r3,2048)} |
| Selected tuned RF | n_estimators = 1000, max_depth = 40, max_features = sqrt, min_samples_leaf = 2, class_weight = balanced, Morgan (r3, 2048); validation macro AP 0.206 |

근거:
- Default RF: `v1_RF/src/config.yaml:3`(seed 42), `:15-19`. 적합은 `v1_RF/src/train.py:47-52`(`MultiOutputClassifier(RandomForestClassifier(random_state=seed, …))`).
- XGBoost 하이퍼파라미터: `v1_RF/src/config.yaml:20-26`. 적합은 `v1_RF/src/train.py:55-78`(`eval_metric="logloss"`, `tree_method="hist"`, `random_state=seed`).
- 실행 경로는 `v1_RF/run_v1.sh:18` → `v1_RF/src/train.py`이다. XGBoost는 이 경로에서 라벨별 루프(OvR)로 PT마다 `XGBClassifier`를 적합하고, 라벨마다 `scale_pos_weight = neg/pos`를 넣는다(`train.py:56-73`). 학습 양성이 없는 라벨은 적합하지 않고 확률 0으로 둔다(`train.py:67-68`). 실행 기록은 `v1_RF/results/run.log:7-8`(「라벨별 scale_pos_weight 적용」)이다.
- Tuned RF 탐색 공간: `v1_RF/src/fairtune.py:47-54`. 예산 16개·샘플링 시드 42는 `:42-43`에 있다.
- 선택값: `v1_RF/results_fairtune/best_config.yaml:2-12` (`valid_macro_pr: 0.2059…`).

### (b) Final GNN model A_wd

| Component | Value |
|---|---|
| Atom (node) features (ATOM_FDIM = 41) | Element symbol one-hot [C,N,O,S,F,Cl,Br,I,P,B,Si,Se,H]+other (14), degree [0–5]+other (7), formal charge [−2..2]+other (6), total H count [0–4]+other (6), hybridization [SP,SP2,SP3,SP3D,SP3D2]+other (6), IsAromatic (1), IsInRing (1) |
| Bond (edge) features (BOND_FDIM = 7) | Bond type one-hot [SINGLE,DOUBLE,TRIPLE,AROMATIC]+other (5), IsConjugated (1), IsInRing (1). Note: edge_attr is computed and stored but not consumed by the GCN/GIN/GAT convolutions, so it does not affect the A_wd results |
| Self-loops | No explicit self-loops added at graph construction (bidirectional bond edges only); PyG convolution defaults apply (GCN and GAT add them internally, GIN does not) |
| GIN layer structure | 3 layers; each layer = GINConv(MLP: Linear(in,128) → ReLU → Linear(128,128)) → BatchNorm1d(128) → ReLU → Dropout(0.2); hidden size 128 |
| Readout / global pooling | global_mean_pool |
| Output layer / activation | Linear(128,128) → ReLU → Dropout → Linear(128,370); raw logits (no output activation; sigmoid is applied at the loss and prediction steps) |
| Optimizer / lr / batch | Adam / 0.001 / 32 |
| Max epochs / early-stopping patience | 200 / 30 (monitored on validation macro AP) |
| Dropout / weight decay | 0.2 / 1e-4 |
| Focal loss | γ = 2; L = mean((1−p_t)^γ · BCE_logits(logits, target, pos_weight)) |
| pos_weight | Label-wise pos_weight = sqrt(negatives / positives); 1.0 for labels with no positives |
| Final model selection epoch | Epoch maximizing validation macro AP (representative seed-42 instance, best_ep = 114; Note 1) |
| Training seeds | {1, 2, 3, 4, 42} |

근거:
- 원자·결합 특성: `v2_GNN/src/graph_features.py:21-30`(목록), `:42-49`(`atom_features`, 14+7+6+6+6+2 = 41), `:52-55`(`bond_features`, 5+2 = 7), `:58-59`(`ATOM_FDIM`·`BOND_FDIM`).
- 그래프 구성(양방향 결합 엣지, 명시적 self-loop 없음): `graph_features.py:69-80`. `edge_attr`는 `models.py:58-61`의 합성곱에 전달되지 않는다.
- GIN 구조: `v2_GNN/src/models.py:19-21`(GIN MLP), `:42-45`(층·BatchNorm), `:60-67`(conv → BN → ReLU → Dropout). hidden·층 수·dropout은 `v2_GNN/src/config.yaml:15-17`.
- 풀링: `models.py:38`, `:70` · `config.yaml:18`. 출력층: `models.py:52-55`, `:71`.
- 최적화기·lr·batch: `v2_GNN/src/train_improve.py:61-62` · `config.yaml:23-24`.
- epochs 200 / patience 30: `v2_GNN/src/train_improve.py:165`(Round 1b). `config.yaml:22`·`:29`의 150 / 20은 구조 비교와 Round 1a(`train_improve.py:162`)의 설정이다.
- weight decay 1e-4: `train_improve.py:108`(`A_wd`).
- Focal loss: `v2_GNN/src/train.py:62-74`. pos_weight는 `train.py:52-59`(neg/pos, 양성 0 라벨은 1.0)와 `train_improve.py:34-35`(sqrt).
- best_ep = 114: `v2_GNN/results_improve/paper_tables/awd_seed42_meta.json:6`. 학습 시드: `v2_GNN/src/robustness.py:43`.

### (c) Sequential search process (within-stage selection by validation macro AP; fixed evaluation split not treated as untouched)

| Round | Configurations evaluated and validation macro AP |
|---|---|
| Architecture comparison | GCN 0.164, GIN 0.174 (selected), GAT 0.168 |
| Round 1a (loss / imbalance, 5 configurations) | raw 0.171, sqrt 0.154, clip10 0.161, focal_g2 0.159, **focal_g2_sqrt 0.178** (selected) |
| Round 1b (regularization / architecture, 4 configurations) | **A_wd 0.186** (selected), B_wd_drop 0.152, C_wd_drop_jk 0.154, D_wd_drop_res 0.169 |

표 S1(c)에 열거된 평가 항목은 구조 비교 3개, Round 1a 5개, Round 1b 4개로 총 12개이다. 단계 간 기준 구성의 재평가가 포함될 수 있으므로 이를 12개의 상호 독립적 고유 후보 또는 RandomForest의 16개 후보와 동일한 탐색예산으로 해석하지 않는다. 최종 A_wd는 해당 순차 탐색에서 validation macro AP 최댓값 0.186과 train–validation 격차를 참고해 선택하였다. 표 S1(c)의 validation 값은 단계별 대표 실행값이며 표 3의 5회 evaluation 평균과 동일한 집계 수준이 아니다. 고정 evaluation 분할은 후보별 결과가 순차 개발 중 산출되었으므로 전체 개발 과정에서 미열람된 확증용 test로 간주하지 않는다.

근거:
- 구조 비교: `v2_GNN/results/_train_meta_v2.json:14-20`.
- Round 1a: `v2_GNN/results_improve/round1a/_round_meta.json:2-9`. 구성 정의는 `v2_GNN/src/train_improve.py:97-103`.
- Round 1b: `v2_GNN/results_improve/round1b/_round_meta.json:2-7`. 구성 정의는 `train_improve.py:106-112`.

### (d) Representation–learner separation configurations

| Component | Value |
|---|---|
| **Morgan FP + MLP** search space | `hidden_dims`{(512),(1024),(512,256),(1024,512),(2048,512)}, `dropout`{0.2,0.4,0.5}, `lr`{1e-3,5e-4,1e-4}, `batch_size`{32,64,128} |
| Selected MLP | hidden_dims = (2048,512), dropout = 0.5, lr = 1e-3, batch_size = 64; validation macro AP 0.200 |
| MLP training procedure (identical to A_wd) | Focal loss γ = 2 · label-wise pos_weight = √(neg/pos) · Adam · weight decay 1e-4 · epochs 200 · patience 30 · early stopping on validation macro AP |
| MLP representation | Morgan r = 2 / 2,048 bits (fixed to the same setting as the default RF) |
| **RDKit descriptor + RF** representation | `rdkit.Chem.Descriptors.descList`, 217 computed → 213 used |
| Descriptor preprocessing (train statistics only) | inf → NaN, then imputed with the training median · 4 zero-variance columns dropped using training variance (`SMR_VSA8`, `SlogP_VSA9`, `fr_diazo`, `fr_thiocyan`) · standardization fitted on train, applied to valid/test |
| Descriptor numerical stabilization | Sign-preserving log1p compression `sign(x)·log1p(\|x\|)` applied to the single `Ipc` column (Note 2). Being monotonically increasing, it leaves the RF split criterion (order comparison) unchanged |
| descriptor + RF search space | Same as the tuned RF but without the Morgan axis: `n_estimators`{300,600,1000}, `max_depth`{None,20,40}, `max_features`{sqrt,log2,0.1}, `min_samples_leaf`{1,2,5}, `class_weight`{balanced,balanced_subsample,None} |
| Selected descriptor + RF | n_estimators = 600, max_depth = 20, max_features = 0.1, min_samples_leaf = 2, class_weight = balanced_subsample; validation macro AP 0.197 |

근거:
- MLP 탐색 공간: `v1_RF/src/repr_mlp.py:85-90`. 예산 16개·샘플링 시드 42는 `:76-77`에 있다.
- MLP 선택값: `v1_RF/results_repr/best_config_mlp.yaml:3-9`, `:19` (`valid_macro_ap: 0.1996…`).
- MLP 학습 절차: `repr_mlp.py:79-82`(epochs·patience·weight decay·γ), `:122-132`(sqrt pos_weight), `:165-168`. 기록은 `best_config_mlp.yaml:10-18`.
- MLP 표현: `repr_mlp.py:83` (`FP_RADIUS, FP_BITS = 2, 2048`).
- RDKit 기술자: `v1_RF/src/repr_desc_rf.py:85-86` · `v1_RF/results_repr/descriptor_preprocess.json:7`, `:15` (217 → 213).
- 전처리: `repr_desc_rf.py:117`(train 중앙값), `:126-130`(train 분산 0 열 제거), `:160-165`(train 기준 표준화) · `descriptor_preprocess.json:8-14`, `:20`.
- 수치 안정화: `repr_desc_rf.py:141-157` · `descriptor_preprocess.json:16-19` (`Ipc`).
- descriptor + RF 탐색 공간: `repr_desc_rf.py:53-59`. 예산·시드는 `:48-49`.
- 선택값: `v1_RF/results_repr/best_config_descrf.yaml:3-8`, `:18` (`valid_macro_ap: 0.1966…`).
- (d)의 두 구성은 모두 탐색 예산 16개, 샘플링 시드 42로 탐색했고, validation macro AP만으로 선택하였다(위 근거 행).

**Note 1)** The Apple M5 Pro MPS backend was not fully deterministic across repeated executions with the same nominal seed 42. Accordingly, the dispersion across the five nominal-seed runs includes both seed-related optimization variation and backend nondeterminism. Table S1 reports a stored representative seed-42 training instance with `best_ep = 114`. Figure 3 and the conditional bootstrap in Section 3.4 use a separate fixed seed-42 prediction pair with micro AP values of 0.320 for the default RandomForest and 0.215 for A_wd, whereas the five-run aggregation in Table 3 includes a different seed-42 A_wd run. These artifacts are therefore reported as distinct runs and are not treated as interchangeable or numerically identical.

**Note 2)** `Ipc` (information content of the characteristic polynomial coefficients) grows super-exponentially with molecular size and reaches about 1.2 × 10<sup>169</sup> in this dataset (the next largest, `BertzCT`, is about 1.7 × 10<sup>4</sup>), exceeding the floating-point range and making standardization and training impossible. Dropping the column would violate the "full descriptor set" condition of the representation, so the column was compressed with an order-preserving monotonic transform instead.

근거: Note 1의 `best_ep = 114`는 `awd_seed42_meta.json:6`에 있다. Figure 3용 seed-42 짝(micro AP 0.3197 / 0.2152)은 `v2_GNN/results_improve/paper_tables/tables_8_9.md:3`에 있다. Note 2의 크기(약 1.2e169, 다음으로 큰 값 약 1.7e4)는 `repr_desc_rf.py:141-146`에 있다.

---

## 표 3 재현 절차

본문 표 3(여섯 모델 구성, 5개 시드 mean ± std)은 아래 입력에서 다시 계산할 수 있다. 재학습은 필요 없다.

**입력**
- 기존 4개 구성의 시드별 값(11개 파일):
  - `v2_GNN/results_improve/robustness/robustness_per_seed.csv` — 디폴트 RF와 A_wd
  - `v1_RF/results_fairtune/seed_{1,2,3,4,42}.csv` — 튜닝 RF
  - `v3_Multimodal/results/graphdta_baseline/seed_{1,2,3,4,42}.csv` — GraphDTA-GIN
- 신규 2개 구성의 시드별 값(10개 파일):
  - `v1_RF/results_repr/seed_{1,2,3,4,42}_mlp.csv`
  - `v1_RF/results_repr/seed_{1,2,3,4,42}_descrf.csv`

**실행**
```bash
python v1_RF/src/repr_tables.py
```

**출력** (`v1_RF/results_repr/`)
- `aggregate_test.csv` — 모델 × 시드별 macro·micro AP
- `table3_extended.csv` — 표 3 (mean ± std, `ddof=1`)
- `pairwise_contrasts.csv` — 쌍별 비교 3쌍 (차이·방향만 기록, 유의성 주장 없음)

위 입력으로 실행하면 세 출력 파일이 저장소에 있는 파일과 바이트 단위로 같게 생성된다.

신규 2개 구성의 시드별 값을 처음부터 다시 만드는 스크립트는 `v1_RF/src/repr_mlp.py`와 `v1_RF/src/repr_desc_rf.py`이고, 실행 로그는 `v1_RF/results_repr/run_mlp.log`, `run_descrf.log`, `run.log`에 있다.

## 실행 환경

- Apple M5 Pro (64GB) · PyTorch MPS · **Python 3.14.4**
- 패키지 버전: `requirements-lock.txt` (프로젝트 `.venv`에서 `pip freeze --all`로 캡처)
- **주의:** lock 파일은 캡처 시점(2026-09-17)의 환경이다. 실험 실행 시점(v1_RF 2026-06-24, v2_GNN 2026-06-25, repr arms 2026-08-30~31)의 환경과 같다고 보장하지 않는다.
- MPS 백엔드는 같은 시드에서도 실행마다 결과가 조금씩 달라질 수 있다(Note 1).
- 실행 로그 두 곳(`v1_RF/results_repr/run.log:100`, `run_descrf.log:3`)의 로컬 절대경로 접두사는 공개 전에 지웠다. 그 밖의 바이트는 바꾸지 않았다.
