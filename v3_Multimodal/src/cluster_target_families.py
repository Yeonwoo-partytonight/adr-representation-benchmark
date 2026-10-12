#!/usr/bin/env python3
"""cluster_target_families.py — (C) P-FAM family 소스: 자체 서열 mmseqs2 클러스터링 (교수님 승인 안건2=A).

근거·설계(임의 변경 금지):
  docs/30_preregistration_OSF_clean.md §4(P-FAM=coarse family multi-hot)·§9(family 정의; UniRef50 취지=50% identity),
  docs/32 §4-2(B_fam 보류 사유: family 라벨 미확보, 무-네트워크 후보=mmseqs2 자체 클러스터),
  교수님 승인(2026-07-24 안건2=A): 자체 서열 mmseqs2 클러스터 family.

방법(결정적):
  - 입력: 06_targets_human.csv 상 human single-protein 표적 UniProt(1,191)의 서열(FASTA).
    서열은 **_cache/ 재사용(네트워크 0)** — UniProt 재다운로드 없음. uniprot 정렬 순서 고정.
  - mmseqs2 easy-cluster **고정 파라미터**: --min-seq-id 0.5 -c 0.8 --cov-mode 0 --threads 1.
    (사전등록 §9 UniRef50 취지 = 50% identity coarse family)
  - cluster representative = coarse family id. member→rep 매핑을 09_target_family_clusters.csv에 저장.

⚠️ 한계(리포트·매니페스트 기록): 이는 UniProt/UniRef50 전체 대비가 아니라 **본 표적셋 자체 50% 클러스터**라
  canonical UniRef50과 다르다(사전등록 §9 sensitivity 계열). family 라벨은 label-free·split-free 외부 주석
  성격(클러스터 id가 라벨/split에 의존하지 않음). B_fam 블록의 vocab만 fold-train에서 fit(OOV 드롭).

무결성:
  - 라벨·분자셋·구조·split·mean-pool·Morgan 무접근. 새 표적/분자/재매핑 없음. UniProt FASTA 재다운로드 없음.
  - 결정적: uniprot 정렬 입력, mmseqs --threads 1 고정 파라미터, cluster_id = rep 정렬 순번.

산출:
  data/processed/target_mapping/09_target_family_clusters.csv  (uniprot, cluster_rep, cluster_id)
  data/processed/target_mapping/_family_cluster_stats.json     (mmseqs 버전/파라미터·클러스터 수·분포)
  data/processed/target_mapping/_mmseqs/                        (FASTA·mmseqs 산출; gitignore)

실행: PATH=/opt/homebrew/bin:$PATH .venv/bin/python3 v3_Multimodal/src/cluster_target_families.py
"""
from __future__ import annotations
import os
import csv
import json
import hashlib
import subprocess
import shutil
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TM = os.path.join(ROOT, "data", "processed", "target_mapping")
CACHE = os.path.join(TM, "_cache")
WORK = os.path.join(TM, "_mmseqs")
UNIPROT = "https://rest.uniprot.org/uniprotkb"

F_HUMAN = os.path.join(TM, "06_targets_human.csv")
F_OUT = os.path.join(TM, "09_target_family_clusters.csv")
F_STATS = os.path.join(TM, "_family_cluster_stats.json")

# ── 동결 mmseqs 파라미터 (사전등록 §9 UniRef50 취지 = 50% identity) ──
MIN_SEQ_ID = "0.5"
COV = "0.8"
COV_MODE = "0"
THREADS = "1"


def cache_fasta(acc):
    """UniProt FASTA를 _cache/에서만 읽는다(네트워크 0). 미존재=None."""
    url = f"{UNIPROT}/{acc}.fasta"
    h = hashlib.sha1(url.encode()).hexdigest()[:20]
    p = os.path.join(CACHE, h + ".json.txt")
    if not os.path.exists(p):
        return None
    txt = open(p).read()
    return "".join(l.strip() for l in txt.splitlines() if not l.startswith(">"))


def mmseqs_bin():
    b = shutil.which("mmseqs") or "/opt/homebrew/bin/mmseqs"
    if not os.path.exists(b) and not shutil.which("mmseqs"):
        raise RuntimeError("mmseqs 미설치 — `brew install mmseqs2` 필요")
    return b


def main():
    print("[cluster_fam] (C) P-FAM 자체 서열 mmseqs2 클러스터 — human single-protein 표적")
    print("[무결성] 서열=_cache/ 재사용(네트워크 0). 라벨/구조/split/mean-pool/Morgan 무접근. 확증 split 무조회.")
    os.makedirs(WORK, exist_ok=True)

    # ── 1) human single-protein 표적 uniprot(정렬) + 서열(캐시) ──
    unis = sorted({r["uniprot"] for r in csv.DictReader(open(F_HUMAN)) if r["uniprot"]})
    seqs, missing = [], []
    for u in unis:
        s = cache_fasta(u)
        if s:
            seqs.append((u, s))
        else:
            missing.append(u)
    print(f"  표적 uniprot {len(unis)} | 서열보유 {len(seqs)} | 서열미보유 {len(missing)}")

    fasta = os.path.join(WORK, "targets_human.fasta")
    with open(fasta, "w") as f:
        for u, s in seqs:      # 정렬 순서 = 결정적 입력
            f.write(f">{u}\n{s}\n")

    # ── 2) mmseqs easy-cluster (결정적 파라미터) ──
    mm = mmseqs_bin()
    ver = subprocess.run([mm, "version"], capture_output=True, text=True).stdout.strip()
    prefix = os.path.join(WORK, "clu")
    tmp = os.path.join(WORK, "tmp")
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    cmd = [mm, "easy-cluster", fasta, prefix, tmp,
           "--min-seq-id", MIN_SEQ_ID, "-c", COV, "--cov-mode", COV_MODE, "--threads", THREADS]
    print("  run:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-2000:])
        raise RuntimeError(f"mmseqs easy-cluster 실패 (rc={r.returncode})")

    # ── 3) cluster TSV 파싱 (rep \t member) → member→rep ──
    tsv = prefix + "_cluster.tsv"
    member2rep = {}
    rep_members = defaultdict(list)
    with open(tsv) as f:
        for line in f:
            rep, mem = line.rstrip("\n").split("\t")
            member2rep[mem] = rep
            rep_members[rep].append(mem)
    reps_sorted = sorted(rep_members)                     # 결정적 cluster_id
    rep2id = {rep: i for i, rep in enumerate(reps_sorted)}
    print(f"  클러스터 수 {len(reps_sorted)} (표적 {len(member2rep)})")

    # ── 4) 저장 (uniprot 정렬) ──
    rows = []
    for u, _ in seqs:
        rep = member2rep.get(u, u)   # (모든 member는 tsv에 존재; 방어적)
        rows.append([u, rep, rep2id[rep]])
    rows.sort(key=lambda x: x[0])
    os.makedirs(os.path.dirname(F_OUT), exist_ok=True)
    with open(F_OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["uniprot", "cluster_rep", "cluster_id"])
        w.writerows(rows)
    print(f"  ✅ {os.path.relpath(F_OUT, ROOT)} ({len(rows)} rows)")

    # ── 5) 통계·매니페스트 ──
    sizes = sorted((len(v) for v in rep_members.values()), reverse=True)
    singletons = sum(1 for s in sizes if s == 1)
    stats = {
        "mmseqs_version": ver,
        "params": {"min_seq_id": MIN_SEQ_ID, "cov": COV, "cov_mode": COV_MODE, "threads": THREADS,
                   "cmd": "easy-cluster"},
        "n_target_uniprot": len(unis),
        "n_seq_available": len(seqs),
        "n_seq_missing": len(missing),
        "n_clusters": len(reps_sorted),
        "n_singletons": singletons,
        "cluster_size_top10": sizes[:10],
        "cluster_size_median": sizes[len(sizes) // 2] if sizes else 0,
        "caveat": ("본 표적셋 자체 50% 클러스터(UniProt/UniRef50 전체 대비 아님) — canonical UniRef50과 다름"
                   "(사전등록 §9 sensitivity 계열). family 라벨은 label-free·split-free 외부 주석 성격; "
                   "B_fam vocab만 fold-train fit(OOV 드롭)."),
        "integrity": {"network_calls": 0, "fasta_source": "_cache/ (재사용)",
                      "labels_molset_structure_split_accessed": False},
    }
    json.dump(stats, open(F_STATS, "w"), indent=2, ensure_ascii=False)
    print(f"  ✅ {os.path.relpath(F_STATS, ROOT)}")
    print(f"[완료] 클러스터 {len(reps_sorted)}개, singleton {singletons}, "
          f"최대 {sizes[0] if sizes else 0} · 중앙값 {stats['cluster_size_median']}")


if __name__ == "__main__":
    main()
