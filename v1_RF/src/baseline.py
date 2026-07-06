#!/usr/bin/env python3
"""v1_RF — 멀티라벨 부작용 예측 베이스라인 (Morgan FP + RandomForest / XGBoost).

CLAUDE.md 4단계 1단계 / 논문의 비교 대상(baseline).
- 입력: data/processed 의 master_X/Y + scaffold_split.json (v1·v2·v3 공유, 재계산 금지)
- 특징: Morgan(ECFP4) fingerprint
- 평가: ★PR-AUC(핵심) + ROC-AUC + F1 + Accuracy. prevalence(무작위) 대비 비교.
- 재현성: 전역 seed=42, config.yaml 분리.
실행: python v1_RF/src/baseline.py   (프로젝트 루트에서)
출력: v1_RF/results/{metrics_summary.json, per_pt_metrics.csv}
"""
import json, os, yaml, numpy as np, pandas as pd
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, f1_score, accuracy_score
try:
    import xgboost as xgb
    HAS_XGB=True
except Exception as e:
    HAS_XGB=False
    print(f"[경고] XGBoost 미사용(라이브러리 로드 실패): {type(e).__name__}. "
          f"RandomForest만 실행. Mac이면 `brew install libomp` 후 재실행하면 XGBoost 포함됨.")

HERE=os.path.dirname(__file__)
CFG=yaml.safe_load(open(os.path.join(HERE,"config.yaml")))
SEED=CFG["seed"]; np.random.seed(SEED)
RESULTS=os.path.join(HERE,"..","results"); os.makedirs(RESULTS, exist_ok=True)

def load_data():
    X=pd.read_parquet(CFG["data"]["master_x"])
    Y=pd.read_parquet(CFG["data"]["master_y"])
    assert list(X["cid"])==list(Y["cid"]), "X/Y cid 정렬 불일치"
    split=json.load(open(CFG["data"]["split"]))
    sp=X["cid"].astype(str).map(split)
    ycols=[c for c in Y.columns if c!="cid"]
    return X, Y, ycols, sp

def featurize(smiles):
    fp=CFG["fingerprint"]
    gen=rdFingerprintGenerator.GetMorganGenerator(radius=fp["radius"], fpSize=fp["n_bits"])
    M=np.zeros((len(smiles), fp["n_bits"]), dtype=np.uint8)
    for i,smi in enumerate(smiles):
        m=Chem.MolFromSmiles(smi)
        if m is not None:
            M[i]=np.frombuffer(gen.GetFingerprint(m).ToBitString().encode(),'u1')-ord('0')
    return M

def build_models():
    models={"RandomForest":
            MultiOutputClassifier(RandomForestClassifier(random_state=SEED, **CFG["models"]["random_forest"]))}
    if HAS_XGB:
        models["XGBoost"]=MultiOutputClassifier(xgb.XGBClassifier(
            random_state=SEED, eval_metric="logloss", tree_method="hist",
            **CFG["models"]["xgboost"]))
    return models

def proba_matrix(model, Xte, n_labels):
    """MultiOutputClassifier → (n, n_labels) 양성확률. 단일클래스 학습 라벨은 0 처리."""
    P=np.zeros((Xte.shape[0], n_labels))
    for j,est in enumerate(model.estimators_):
        cls=list(est.classes_)
        if 1 in cls:
            P[:,j]=est.predict_proba(Xte)[:, cls.index(1)]
    return P

def evaluate(Yte, P, ycols, thr):
    rows=[]
    for j,pt in enumerate(ycols):
        yt=Yte[:,j]; ys=P[:,j]; npos=int(yt.sum())
        row={"meddra_pt":pt, "n_pos_test":npos,
             "pr_auc":np.nan, "roc_auc":np.nan, "f1":np.nan,
             "prevalence":yt.mean()}
        if npos>0:
            row["pr_auc"]=average_precision_score(yt, ys)
            if 0<npos<len(yt):
                row["roc_auc"]=roc_auc_score(yt, ys)
            row["f1"]=f1_score(yt, (ys>=thr).astype(int), zero_division=0)
        rows.append(row)
    df=pd.DataFrame(rows)
    ev=df[df.n_pos_test>0]
    micro_ap=average_precision_score(Yte.ravel(), P.ravel())
    summary={
        "n_pt_evaluated": int(len(ev)),
        "macro_pr_auc": float(ev["pr_auc"].mean()),
        "micro_pr_auc": float(micro_ap),
        "macro_roc_auc": float(ev["roc_auc"].mean()),
        "macro_f1": float(ev["f1"].mean()),
        "mean_prevalence(random PR-AUC 기준선)": float(ev["prevalence"].mean()),
        "subset_accuracy": float(accuracy_score(Yte, (P>=thr).astype(int))),
    }
    return summary, df

def main():
    X,Y,ycols,sp=load_data()
    print(f"[데이터] 분자 {len(X)} × PT {len(ycols)} | split {sp.value_counts().to_dict()}")
    F=featurize(X["smiles_canonical"].tolist())
    Ym=Y[ycols].values.astype(int)
    tr=(sp=="train").values; te=(sp=="test").values
    Xtr,Xte=F[tr],F[te]; Ytr,Yte=Ym[tr],Ym[te]
    print(f"[특징] Morgan {F.shape[1]}bit | train {Xtr.shape} test {Xte.shape}")

    all_summary={}
    per_pt={}
    for name,model in build_models().items():
        print(f"[학습] {name} ...")
        model.fit(Xtr, Ytr)
        P=proba_matrix(model, Xte, len(ycols))
        summ,df=evaluate(Yte, P, ycols, CFG["eval"]["threshold"])
        all_summary[name]=summ
        per_pt[name]=df
        print(f"  {name}: macro PR-AUC {summ['macro_pr_auc']:.3f} | micro PR-AUC {summ['micro_pr_auc']:.3f} "
              f"| macro ROC-AUC {summ['macro_roc_auc']:.3f} | macro F1 {summ['macro_f1']:.3f}")

    json.dump(all_summary, open(f"{RESULTS}/metrics_summary.json","w"), indent=2, ensure_ascii=False)
    # per-PT는 모델별 컬럼 접두어로 합쳐 저장
    base=per_pt["RandomForest"][["meddra_pt","n_pos_test","prevalence"]].copy()
    for name,df in per_pt.items():
        base[f"{name}_pr_auc"]=df["pr_auc"].values
        base[f"{name}_roc_auc"]=df["roc_auc"].values
        base[f"{name}_f1"]=df["f1"].values
    base.sort_values("n_pos_test", ascending=False).to_csv(f"{RESULTS}/per_pt_metrics.csv", index=False)
    print(f"[저장] results/metrics_summary.json, per_pt_metrics.csv")
    print(json.dumps(all_summary, indent=2, ensure_ascii=False))

if __name__=="__main__":
    main()
