# Post hoc exploratory analyses (not preregistered)

This directory was added in release `v3-plosone-v1.1`. It holds the scripts and outputs of the
analyses that were run **after** the confirmatory results were unblinded on 2026-10-08. None of
these analyses was preregistered, none produces a p-value, and none enters any confirmatory
decision. They back **Table 4** and **S5 Table** of the manuscript. Everything released in
`v3-plosone-v1.0` is unchanged in this release; this directory and
`experiments/audits/A4_bseq_truncation_audit.csv` were added, and the README, `CITATION.cff`,
`LICENSE` and `masking_map.csv` were updated.

No model was trained or retrained. Every difference is computed on the fixed consensus
out-of-fold (OOF) predictions released under `experiments/runs/<run>/oof_public/`, with the
scaffold-cluster bootstrap of the frozen SAP (`v3_Multimodal/src/sap/bootstrap.py`;
B = 10,000, seed 6001, 95% BCa intervals).

## Where each reported number comes from

| Manuscript item | File(s) in this directory | Keys |
|---|---|---|
| Table 4 (component decomposition) | `_ckpt/X1_*.json`, `_ckpt/S0-2_C1.json` | `delta_obs`, `ci_bca.low`, `ci_bca.high` |
| S5 Table A (restricted populations) | `_ckpt/X12_mapped847_*.json`, `_ckpt/X7_excl_acyclic_*.json` | `delta_obs`, `ci_bca`, `n_clusters`, `_n_rows_evaluated` |
| S5 Table B (target-count tertiles) | `X9a/x9a_target_count_descriptive.json`, `_ckpt/X9a_T{1,2,3}_*.json` | tertile bounds and sizes; `delta_obs`, `ci_bca` |
| S5 Table C (absolute macro AP by arm) | `X3/x3_absolute_macro_ap.json` | RF consensus, GIN per seed and seed mean |
| S5 Table D (reassignment null realizations) | `_ckpt/X4_realizations.json` | `null_mean`, `null_sd`, `null_min`, `null_max`, `n_below_obs` |
| S5 Table E (target representation) | `X9a/…descriptive.json`, `X10a/x10a_truncation.json`, `X10b/x10b_anisotropy.json` | counts, truncation fractions, cosine and PCA summaries |
| S5 Table F (size-weighted diagnostic) | `X5/x5_weighted_point_estimate.json`, `_ckpt/X5_sizeweighted.json`, `_ckpt/S0-2_C1.json` | `weighted_delta`, `n_eff_clusters_kish`, percentile interval |

`_src/build_s5_table.py` regenerates S5 Table from these files without recomputing anything:
`python3 experiments/runs/v3_exploratory/_src/build_s5_table.py . S5_Table.md`.
Table 4 was assembled from the `X1` files listed above; no separate script was used.

The remaining files are audits that informed the text but are not tabulated: `A5` (reconstruction of the
ChEMBL release and UniProt query dates), `A6` (whether the released tree contains the drug–target mapping table),
`X1/x1_ccap_noise_unmapped_code_check.json`, `X4/x4_*` (public tail counts and storage check),
`X5/x5_code_reading.json`, `X7` (scaffold-group sizes) and `X10a/x10a_ion_channel_targets.csv`.

## How the outputs were produced

1. `_src/nosealed.py` — steps that read only public files (X1 point estimates, X3, X4 public
   aggregates, X5 code reading, X7, X9a, X10a, X10b, A5, A6). It also writes the two index
   arrays in `X9a/` and `_manifest/nosealed_manifest.json`.
2. `_src/launch_on_ac.sh` started `_src/sealed.py` (macOS; waits for mains power). `sealed.py`
   runs the bootstrap contracts whose outputs are in `_ckpt/`, the size-weighted point estimate
   in `X5/`, `_ckpt/run.log` and `_manifest/sealed_guard.json`.

Two internal record-keeping scripts that wrote to the project's Korean research records are not
released; they did not produce any of the files above.

**Paths in `sealed.py`.** The script reads the consensus predictions from the sealed trees
(`experiments/runs/<run>/_sealed/consensus_<arm>.npz`) and records each read. Those seven
files are **byte-identical** to the released copies in `experiments/runs/<run>/oof_public/`
(SHA-256 digests listed in `experiments/runs/v3_release_sealed_map.csv`), so the bootstrap
contracts can be re-run by pointing those paths at `oof_public/`.

**Not re-runnable from released data.**
- S5 Table D: the per-realization null values come from the sealed null checkpoint, which is
  summarised but not released as raw values (see the main README, "What predictions are
  released"). `X4/x4_public_tail_counts.json` gives the tail fractions from the released
  aggregate.
- `A5` needs a local cache of ChEMBL API responses, which is not redistributed.
- `A6` also listed archives stored outside the repository on the author's machine.

## Environment

Python 3.14.4 with the packages in `requirements.txt`. `sealed.py` uses `multiprocessing`
(fork) and calls the macOS `pmset` utility; `launch_on_ac.sh` also uses `caffeinate`.

## Masking

Four files are released as masked copies, using the tokens of the main README's masking notice
plus two new ones: `<OUTSIDE-REPO>` (an archive path outside the repository) and
`<DEVICE-SERIAL>` (a power-adapter serial number printed by `pmset`). `masking_map.csv` lists
each file with both SHA-256 digests. The digest of
`A6/a6_mapping_table_in_release.json` recorded in `_manifest/nosealed_manifest.json` refers to
the unmasked original.
