# Data and output licensing (v3 release files)

Data, predictions, results and records added by the **v3 release** of this repository are
licensed under the **Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0)** licence. The authoritative licence text is at
<https://creativecommons.org/licenses/by-sa/4.0/legalcode>; a human-readable summary is at
<https://creativecommons.org/licenses/by-sa/4.0/>.

Source code in this repository is licensed separately under the MIT licence (see `LICENSE`).

## Scope

This file covers the files added or modified by the v3 release commit, that is: derived data
under `data/processed/`, out-of-fold predictions under `experiments/runs/*/oof_public/`,
sealed-access ledgers under `experiments/runs/*/sealed_access_log/`, result and summary files
under `experiments/` and `v3_Multimodal/results/`, frozen configuration under
`v3_Multimodal/config/`, transparency records under `experiments/provenance/` and `docs/`, and
the mapping tables `experiments/runs/v3_release_sealed_map.csv` and `masking_map.csv`.

Files that were already present in the repository before the v3 release (the KCI 2026
submission assets under `v1_RF/`, `v2_GNN/`, `pipeline/`, `scripts/` and the pre-existing parts
of `data/processed/`) are **not** re-licensed by this file. Their terms are unchanged.

## Third-party sources

Derived data in this repository is computed from the following public sources. Their own terms
govern the upstream records; users who redistribute material derived from them should cite and
comply with each source.

| Source | Licence as published by the provider | Used for |
|---|---|---|
| OnSIDES v3.1.1 (Tatonetti Lab, Columbia University Irving Medical Center / Cedars-Sinai) | CC BY 4.0 (stated as "data … CC BY 4.0" in the OnSIDES repository README) | adverse-drug-reaction labels (y); cite Tanaka et al., *Med* 2025;6(7):100642, doi:10.1016/j.medj.2025.100642 |
| PubChem (NCBI / U.S. National Library of Medicine) | U.S. government work; see PubChem's own usage policies | compound structures (canonical SMILES), CID as the join key |
| ChEMBL (EMBL-EBI) | CC BY-SA 3.0 Unported (stated in the ChEMBL FAQ as "licensed under a Creative Commons Attribution-Share Alike 3.0 Unported License") | compound–target associations, assay confidence, mechanism annotations |
| UniProtKB (UniProt Consortium) | CC BY 4.0 | target protein sequences, input to the ProtBERT embeddings |

Because ChEMBL-derived material is ShareAlike, the v3 release applies **CC BY-SA 4.0** to the
whole set of v3 data and outputs rather than mixing per-file terms. CC BY-SA 3.0 Unported
material may be relicensed under CC BY-SA 4.0 under the ShareAlike compatibility provisions of
those licences.

Raw upstream archives are **not** redistributed here: `data/raw/` is excluded from the
repository. See the v3 section of `README.md` for how to re-obtain each source.

## Attribution

When reusing the v3 data or outputs, cite the manuscript and this repository (see
`CITATION.cff`), and retain this notice together with the per-source attributions above.
