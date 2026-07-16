# 02 — File Analysis

> Every file in `research_data/raw/` is classified by purpose, framework requirement status, and loader relevance.

---

## 2.1 File Classification Legend

| Status | Meaning |
|--------|---------|
| **MANDATORY** | Required by Phase 004 loader; absence should raise an error |
| **OPTIONAL** | Enriches the dataset object; absence should produce a warning, not an error |
| **UNUSED** | Not needed by the current framework scope |

---

## 2.2 File: `neurons.csv.gz` (all datasets)

**Present in**: BANC, FAFB, MANC, MAOL, MCNS  
**Status**: **MANDATORY**

### Purpose
Contains the **node table** for the connectome graph. Each row represents one neuron (or neuronal fragment). This file provides:

- The unique neuron identifier (primary key for all graph nodes)
- Neurotransmitter identity (predicted and verified)
- Morphological classification (flow, super class, class, sub class)
- Anatomical information (soma side, nerve, body part)
- Cell type assignments (primary and alternative)
- Morphological measurements (cable length, surface area, volume — where available)

### Why Mandatory
The loader cannot construct graph nodes without this file. Every connection in `connections_princeton.csv.gz` references neuron IDs defined here. Without the neuron table, there is no node registry, no attribute lookup, and no way to validate connection integrity.

### Loader Notes
- **FAFB** uses a different schema (10 columns, lowercase headers) vs all other datasets (21 columns, mixed-case headers with spaces).
- The `Community labels` column encodes semi-structured metadata as a delimited string — the loader should store it raw and document a parsing utility for downstream use.
- Morphology columns (`Cable length (nm)`, `Surface area (nm^2)`, `Volume (nm^3)`) are 100% empty in BANC, MAOL, and MCNS; only MANC has `Volume` populated; FAFB does not have these columns at all.

---

## 2.3 File: `connections_princeton.csv.gz` (all datasets)

**Present in**: BANC, FAFB, MANC, MAOL, MCNS  
**Status**: **MANDATORY**

### Purpose
Contains the **edge table** for the connectome graph. Each row represents one directed synaptic connection between two neurons in one neuropil region. Fields:

- `pre_root_id` — presynaptic neuron ID
- `post_root_id` — postsynaptic neuron ID
- `neuropil` — brain region where the synapse occurs
- `syn_count` — number of synapses in this connection
- `nt_type` — neurotransmitter type (edge-level annotation)

### Why Mandatory
This is the **primary edge source**. Without it, no graph can be constructed. It is the largest file in every dataset and the primary memory bottleneck.

### Loader Notes
- The schema is **identical across all 5 datasets** — this is the most portable file.
- `nt_type` is populated only in FAFB (values: ACH, DA, GABA, GLUT, OCT, SER). In all other datasets it is 100% empty.
- BANC and FAFB use 18-digit `uint64` neuron IDs; MANC/MAOL/MCNS use small integer body IDs (e.g., `10000`, `10001`).
- MCNS connections use `UNASGD` as the neuropil value for all sampled rows — indicating unassigned neuropil regions. This may be dataset-wide.
- Multiple rows with the same `(pre_root_id, post_root_id)` pair exist when the connection spans multiple neuropil regions. This is expected and correct; the triplet `(pre, post, neuropil)` is the natural composite key.
- **No duplicate triplets** were observed in any dataset.

---

## 2.4 File: `classification.csv.gz` (FAFB only)

**Present in**: FAFB_v783 only  
**Status**: **OPTIONAL**

### Purpose
Contains morphological classification for FAFB neurons in a structured 8-column format. In other datasets, equivalent information is embedded inside `neurons.csv.gz`. FAFB separates it into a dedicated file.

Columns: `root_id`, `flow`, `super_class`, `class`, `sub_class`, `hemilineage`, `side`, `nerve`

### Why Optional
The FAFB `neurons.csv.gz` does **not** contain these classification fields (flow, super_class, class, etc.) — FAFB's neuron file only has NT scores and group. Therefore, for FAFB specifically, `classification.csv.gz` is the **primary source of morphological classification** and should be treated as de-facto mandatory for FAFB.

For all other datasets, this file does not exist, and the classification data comes from `neurons.csv.gz` directly.

### Loader Notes
- The loader should **left-join** this file onto the FAFB neuron table on `root_id` after loading.
- The FAFB neuron table has 139,255 rows; `classification.csv.gz` also has 139,255 rows (same set of IDs).
- `hemilineage` is 73% empty; `nerve` is 93.1% empty — this is expected biological data sparsity, not corruption.

---

## 2.5 File: `consolidated_cell_types.csv.gz` (FAFB only)

**Present in**: FAFB_v783 only  
**Status**: **OPTIONAL**

### Purpose
Contains cell type assignments for FAFB neurons — the biologically interpreted neuron identity (e.g., `T4b`, `T5b`). In other datasets, this is stored as `Primary Cell Type` inside `neurons.csv.gz`.

Columns: `root_id`, `primary_type`, `additional_type(s)`

### Why Optional
Useful for biological interpretation and downstream analyses (neuron matching, conserved circuit detection). Not required to construct the graph structure. The framework can function without it but biological analyses will be degraded.

### Loader Notes
- 138,327 rows vs 139,255 neurons → **928 neurons have no cell type entry**. This is expected (unclassified neurons).
- `additional_type(s)` is 89.9% empty — most neurons have only one cell type.
- The loader should left-join this onto the FAFB neuron table on `root_id`.

---

## 2.6 Non-CSV Files

**Observation**: No `metadata.json`, `README.md`, or any non-CSV files were found in any dataset directory.

This is a significant gap: there is **no machine-readable metadata** shipping with the datasets. Dataset-level metadata (version, organism, brain region, coordinate space, proofreading date) must be provided through the framework's own configuration system (`configs/datasets/`).

---

## 2.7 Summary Table

| File | BANC | FAFB | MANC | MAOL | MCNS | Status |
|------|------|------|------|------|------|--------|
| neurons.csv.gz | ✓ | ✓ | ✓ | ✓ | ✓ | MANDATORY |
| connections_princeton.csv.gz | ✓ | ✓ | ✓ | ✓ | ✓ | MANDATORY |
| classification.csv.gz | ✗ | ✓ | ✗ | ✗ | ✗ | OPTIONAL (FAFB-specific) |
| consolidated_cell_types.csv.gz | ✗ | ✓ | ✗ | ✗ | ✗ | OPTIONAL (FAFB-specific) |
| metadata.json | ✗ | ✗ | ✗ | ✗ | ✗ | ABSENT — use config system |
