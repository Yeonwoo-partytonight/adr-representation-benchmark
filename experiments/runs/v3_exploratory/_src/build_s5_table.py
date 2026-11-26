#!/usr/bin/env python3
"""Build Supplementary Table S5 (non-registered exploratory analyses) from the block-CN outputs.

Read-only: every number is read from the JSON files under experiments/runs/v3_exploratory/
and formatted here; nothing is recomputed. Usage: build_s5_table.py <repo_root> <out.md>
"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

root, out = Path(sys.argv[1]), Path(sys.argv[2])
X = root / "experiments/runs/v3_exploratory"
J = lambda p: json.load(open(X / p, encoding="utf-8"))
MINUS = "−"


def f(x, dp=4):
    q = Decimal(repr(x)).quantize(Decimal(1).scaleb(-dp), ROUND_HALF_UP)
    if q == 0 and x != 0:
        return f(x, dp + 1)
    s = f"{q:.{dp}f}" if q != 0 else f"{0:.{dp}f}"
    return s.replace("-", MINUS)


def pct(n, d):
    return f(100 * n / d, 1) + "%"


def ci(c):
    assert c["status"] == "estimable", c
    return f"[{f(c['low'])}, {f(c['high'])}]"


def contrast_row(label, pop, ck):
    d = J(f"_ckpt/{ck}.json")
    return f"| {label} | {pop} | {d['_n_rows_evaluated']:,} | {d['n_clusters']:,} | {f(d['delta_obs'])} | {ci(d['ci_primary'])} |"


L = ["# Supplementary Table S5. Non-registered exploratory analyses", ""]
L += ["All analyses in this table were added after unblinding and were not registered. Differences use the fixed consensus OOF predictions of the random forest and the scaffold-cluster bootstrap (B = 10,000; seed 6001) with 95% BCa intervals; no p-values were computed and no result enters any decision. The component decomposition is given in Table 4 of the main text.", ""]

L += ["## A. Restricted evaluation populations", ""]
L += ["| Contrast | Population | Drugs | Scaffold groups | Δ macro AP | 95% BCa CI |", "|---|---|---|---|---|---|"]
L.append(contrast_row("M2b − M1b", "Drugs with at least one mapped target", "X12_mapped847_M2b_minus_M1b"))
L.append(contrast_row("M2b − P-ID", "Drugs with at least one mapped target", "X12_mapped847_M2b_minus_P-ID"))
L.append(contrast_row("M2b − M1b", "Drugs with a ring scaffold", "X7_excl_acyclic_M2b_minus_M1b"))
L.append(contrast_row("M2b − P-ID", "Drugs with a ring scaffold", "X7_excl_acyclic_M2b_minus_P-ID"))
L.append("")

t = J("X9a/x9a_target_count_descriptive.json")
L += ["## B. Contrasts by tertile of the number of mapped targets", ""]
L += ["| Tertile | Mapped targets per drug | Drugs | Scaffold groups | M2b − M1b | 95% BCa CI | M2b − P-ID | 95% BCa CI |", "|---|---|---|---|---|---|---|---|"]
for k in ("T1", "T2", "T3"):
    a, b = J(f"_ckpt/X9a_{k}_M2b_minus_M1b.json"), J(f"_ckpt/X9a_{k}_M2b_minus_P-ID.json")
    tt = t["tertiles"][k]
    assert a["_n_rows_evaluated"] == b["_n_rows_evaluated"] == tt["n_drugs"]
    L.append(f"| {k} | {int(tt['n_targets_min'])}–{int(tt['n_targets_max'])} | {tt['n_drugs']:,} | {a['n_clusters']:,} | {f(a['delta_obs'])} | {ci(a['ci_primary'])} | {f(b['delta_obs'])} | {ci(b['ci_primary'])} |")
L += ["", "Tertile boundaries were computed over the 847 drugs with at least one mapped target. Within a tertile, PTs without a positive drug in a bootstrap replicate are excluded from that replicate's mean, so tertile values are estimates for a different population from the full-set contrast.", ""]

x3 = J("X3/x3_absolute_macro_ap.json")
L += ["## C. Absolute macro AP by arm", ""]
L += ["| Arm | RF (consensus) | GIN (mean of 3 seeds) | GIN seed 42 | GIN seed 1 | GIN seed 2 |", "|---|---|---|---|---|---|"]
for arm in ("M0", "M1", "M1b", "M2", "M2b", "P-ID", "P-FAM", "C-CAP"):
    g = x3["gin"][arm]
    if g["n_seeds"] == 0:
        assert arm in x3["gin_arms_absent"]
        gs = ["not trained"] * 4
    else:
        ps = g["per_seed_repeat_consensus"]
        gs = [f(g["seed_mean"])] + [f(ps[s]) for s in ("seed42", "seed1", "seed2")]
    L.append(f"| {arm} | {f(x3['rf_consensus_absolute_macro_ap'][arm])} | " + " | ".join(gs) + " |")
L += ["", f"Label-prevalence baseline: {f(x3['label_prevalence_baseline_macro_ap'])}. GIN values are computed per training seed on the repeat-consensus predictions and then averaged; M2 was not part of the GIN ladder.", ""]

r = J("_ckpt/X4_realizations.json")["modes"]
L += ["## D. Reassignment null realizations (M2b macro AP, split repeat 1)", ""]
L += ["| Null | Realizations | Mean | Median | SD | Minimum | Maximum | Observed | Below observed |", "|---|---|---|---|---|---|---|---|---|"]
for k, lab in (("family", "Family-constrained"), ("global", "Global")):
    m = r[k]
    L.append(f"| {lab} | {m['n_realizations']:,} | {f(m['null_mean'])} | {f(m['null_median'])} | {f(m['null_sd'])} | {f(m['null_min'])} | {f(m['null_max'])} | {f(m['T_obs'])} | {m['n_below_obs']:,} ({pct(m['n_below_obs'], m['n_realizations'])}) |")
L.append("")

tr = J("X10a/x10a_truncation.json"); an = J("X10b/x10b_anisotropy.json")["results"]["confirmatory_input_meanpool"]
L += ["## E. Target representation", ""]
L += ["| Quantity | Value |", "|---|---|"]
L.append(f"| Drugs with at least one mapped target | {t['n_mapped']:,} of {t['n_rows_total']:,} |")
L.append(f"| Mapped targets per drug, median (IQR; range) | {int(t['median'])} ({f(t['iqr'][0], 1)}–{f(t['iqr'][1], 1)}; {int(t['min'])}–{int(t['max'])}) |")
L.append(f"| Main-analysis targets longer than 510 residues | {tr['n_seq_len_gt_510']:,} of {tr['n_main_analysis_targets']:,} ({pct(tr['n_seq_len_gt_510'], tr['n_main_analysis_targets'])}) |")
a = tr["all_embedded_truncation"]
L.append(f"| All embedded targets longer than 510 residues | {a['n_truncated']:,} of {a['n']:,} ({pct(a['n_truncated'], a['n'])}) |")
L.append(f"| Drug vectors, mean pairwise cosine similarity (median) | {f(an['pairwise_cosine_mean'], 3)} ({f(an['pairwise_cosine_median'], 3)}) |")
L.append(f"| Drug vectors, variance explained by the first principal component | {pct(an['pc1_explained_variance_ratio'], 1)} |")
L.append(f"| Drug vectors, variance retained by 64 principal components | {pct(an['pca64_cumulative_explained_variance'], 1)} |")
L.append(f"| Drug vectors, principal components needed for 90% of the variance | {an['n_dims_for_90pct_variance']} |")
L += ["", "Drug vectors are the 1,024-dimensional mean-pooled ProtBERT target embeddings of the mapped drugs before the within-fold reduction to 64 principal components.", ""]

w = J("X5/x5_weighted_point_estimate.json")
lo, hi = w["size_weighted_percentile_ci_recorded"]
assert w["weighted_delta_inside_recorded_percentile_ci"] is True
L += ["## F. Size-weighted bootstrap diagnostic (primary contrast M2b − M1b)", ""]
L += ["| Quantity | Value |", "|---|---|"]
L.append(f"| Unweighted Δ (primary analysis) | {f(w['unweighted_delta_obs_recorded'])} |")
L.append(f"| Size-weighted point estimate | {f(w['weighted_delta'])} |")
L.append(f"| Size-weighted bootstrap percentile interval | [{f(lo)}, {f(hi)}] |")
L.append(f"| Kish effective number of scaffold groups | {f(w['n_eff_clusters_kish'], 1)} of {w['n_clusters']:,} |")
L += ["", "The size-weighted bootstrap weights each drug in proportion to the size of its scaffold cluster and therefore targets a different population from the primary analysis; its weighted point estimate lies inside its percentile interval, and its BCa interval was not estimable."]

b = ("\n".join(L) + "\n").encode("utf-8")
out.write_bytes(b)
import hashlib
print(len(b), hashlib.sha256(b).hexdigest(), b.count(b"\n"))
