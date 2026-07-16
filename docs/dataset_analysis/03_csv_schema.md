# 03 — CSV Schema

> All schemas are derived from direct file inspection.  
> Column names, types, and nullability are measured from actual data.  
> "Nullable" means empty string observed in that column.

---

## 3.1 Schema Group Classification

There are **three distinct CSV schemas** across all datasets:

| Schema Group | Files | Datasets |
|-------------|-------|---------|
| **Connections Schema** | connections_princeton.csv.gz | ALL (identical) |
| **Princeton Neurons Schema** | neurons.csv.gz | BANC, MANC, MAOL, MCNS |
| **FAFB Neurons Schema** | neurons.csv.gz | FAFB only |
| **FAFB Classification Schema** | classification.csv.gz | FAFB only |
| **FAFB Cell Types Schema** | consolidated_cell_types.csv.gz | FAFB only |

---

## 3.2 Connections Schema (Universal — All 5 Datasets)

**File**: `connections_princeton.csv.gz`  
**Applies to**: BANC, FAFB, MANC, MAOL, MCNS  
**Columns**: 5

| # | Column | Raw Name | Type | Nullable | Unique | Description | Biological Meaning | Value Range / Examples |
|---|--------|---------|------|----------|--------|-------------|-------------------|----------------------|
| 0 | pre_root_id | `pre_root_id` | int64 / str | No | No (FK) | Presynaptic neuron identifier | The neuron releasing neurotransmitter | BANC/FAFB: 18-digit int64 (e.g., `720575941076956631`); MANC/MAOL/MCNS: small int (e.g., `10000`) |
| 1 | post_root_id | `post_root_id` | int64 / str | No | No (FK) | Postsynaptic neuron identifier | The neuron receiving neurotransmitter | Same format as pre_root_id |
| 2 | neuropil | `neuropil` | str | No | No | Brain region where connection occurs | Anatomical location of the synapse | Abbreviated brain region code: `ME_R`, `AL_L`, `CV`, `LO_R`, `UNASGD` |
| 3 | syn_count | `syn_count` | int32 | No | No | Number of synapses in this connection | Connection strength / weight | Positive integer; observed range: 1–several thousand; no negatives confirmed |
| 4 | nt_type | `nt_type` | str | Yes | No | Neurotransmitter type for this connection | Chemical identity of the synapse | FAFB: `ACH`, `DA`, `GABA`, `GLUT`, `OCT`, `SER`; ALL OTHERS: 100% empty string |

### Notes on Connections Schema

- **Composite natural key**: `(pre_root_id, post_root_id, neuropil)` — uniquely identifies one connection in one region.
- The same `(pre, post)` pair may appear multiple times with different `neuropil` values (multi-region projections). This is biologically correct.
- `syn_count` is the primary **edge weight** for graph construction.
- `nt_type` in connections is only reliable in FAFB. In other datasets, use the neuron-level NT prediction from `neurons.csv.gz`.

### Neuropil Values by Dataset

| Dataset | Sample Neuropil Values | Notes |
|---------|----------------------|-------|
| BANC | `ABDNM_L`, `AL_L`, `AL_R`, `AME_L`, `AME_R`, `AMMC_L`... | Full brain + VNC; bilateral |
| FAFB | `LA_L`, `ME_L`, `UNASGD` | Only 3 distinct in first 50K rows; likely more |
| MANC | `CV`, `LTct`, `LegNp_T1_L`, `ADMN_L`... | VNC-specific neuropils |
| MAOL | `LO_R`, `LOP_R`, `ME_R`, `AME_R`, `NotPrimary` | Optic lobe; right hemisphere |
| MCNS | `UNASGD` | All sampled rows unassigned; may be dataset-wide |

---

## 3.3 Princeton Neurons Schema (BANC, MANC, MAOL, MCNS)

**File**: `neurons.csv.gz`  
**Applies to**: BANC_v888, MANC_v1.2.1, MAOL_v1.1, MCNS_v0.9  
**Columns**: 21  
**Header style**: Mixed-case with spaces and special characters

| # | Column | Raw Name | Type | Nullable | Description | Biological Meaning |
|---|--------|---------|------|----------|-------------|-------------------|
| 0 | root_id | `Root ID` | int64 / str | No (PK) | Unique neuron identifier | The neuron's proofreading root ID |
| 1 | top_region | `Top in/out region` | str | No | Primary anatomical region of input/output | Where the neuron primarily receives or sends synapses |
| 2 | community_labels | `Community labels` | str | Yes | Semi-structured key-value metadata string | Encodes instance name, synonyms, cross-refs, tracing status, etc. |
| 3 | predicted_nt_type | `Predicted NT type` | str | Yes | ML-predicted neurotransmitter type | Computational prediction of chemical identity |
| 4 | predicted_nt_confidence | `Predicted NT confidence` | float | Yes | Confidence score for NT prediction | Model certainty; range 0.0–1.0 |
| 5 | verified_nt_type | `Verified NT type` | str | Yes | Experimentally verified NT type | Ground truth from biological experiments |
| 6 | verified_neuropeptide | `Verified Neuropeptide` | str | Yes | Verified neuropeptide identity | Peptide neuromodulator if applicable |
| 7 | body_part | `Body Part` | str | Yes | Body segment the neuron belongs to | Anatomical body region (head, thorax, abdomen) |
| 8 | function | `Function` | str | Yes | Functional category | Known biological role |
| 9 | flow | `Flow` | str | Yes | Signal flow direction | `afferent`, `intrinsic`, `efferent` — information flow direction in circuit |
| 10 | super_class | `Super Class` | str | Yes | Highest-level neuron class | Broad biological category (sensory, motor, interneuron, etc.) |
| 11 | class | `Class` | str | Yes | Mid-level class | More specific classification within super class |
| 12 | sub_class | `Sub Class` | str | Yes | Detailed sub-classification | Fine-grained morphological/functional type |
| 13 | hemilineage | `Hemilineage` | str | Yes | Developmental lineage | Stem cell origin; key for developmental biology analyses |
| 14 | nerve | `Nerve` | str | Yes | Nerve bundle | Which nerve the neuron's axon travels through |
| 15 | soma_side | `Soma side` | str | No† | Hemisphere of soma | `left`, `right`, or bilateral; body location |
| 16 | primary_cell_type | `Primary Cell Type` | str | Yes | Primary cell type label | Standard FlyWire neuron type name (e.g., `DNp01`, `T4b`) |
| 17 | alternative_cell_types | `Alternative Cell Type(s)` | str | Yes | Additional cell type labels | Comma-separated alternative identities |
| 18 | cable_length_nm | `Cable length (nm)` | float | Yes† | Total cable length in nm | Morphological size metric |
| 19 | surface_area_nm2 | `Surface area (nm^2)` | float | Yes† | Surface area in nm² | Morphological size metric |
| 20 | volume_nm3 | `Volume (nm^3)` | float | Yes† | Volume in nm³ | Morphological size metric |

†`soma_side` is Never null in BANC/MAOL but 0.3% null in MANC, 3.6% null in MCNS.  
†Morphology columns (18–20) are 100% null in BANC, MAOL, MCNS. Only MANC has `Volume` populated.

### Nullability Per Column Per Dataset (Princeton Schema)

| Column | BANC (158K) | MANC (23K) | MAOL (52K) | MCNS (167K) |
|--------|------------|-----------|-----------|------------|
| Root ID | 0% | 0% | 0% | 0% |
| Top in/out region | 0% | 0% | 0% | 0% |
| Community labels | 14.6% | 0% | 0% | 0.0% |
| Predicted NT type | 5.5% | 1.0% | 15.5% | 9.8% |
| Predicted NT confidence | 5.5% | 1.0% | 15.5% | 9.8% |
| Verified NT type | 58.7% | 100% | 100% | 100% |
| Verified Neuropeptide | 95.6% | 100% | 100% | 100% |
| Body Part | 87.6% | 100% | 100% | 100% |
| Function | 84.8% | 100% | 100% | 100% |
| Flow | 7.2% | 0% | 1.1% | 100% |
| Super Class | 7.3% | 0% | 1.1% | 0% |
| Class | 43.5% | 7.1% | 11.6% | 84.1% |
| Sub Class | 75.8% | 0.4% | 12.1% | 86.8% |
| Hemilineage | 68.1% | 40.2% | 93.7% | 100% |
| Nerve | 89.7% | 55.5% | ~100% | 99.4% |
| Soma side | 0% | 0.3% | 0% | 3.6% |
| Primary Cell Type | 25.1% | 0.5% | 1.9% | 1.3% |
| Alternative Cell Type(s) | 25.1% | 0.5% | 1.9% | 1.3% |
| Cable length (nm) | 100% | 100% | 100% | 100% |
| Surface area (nm^2) | 100% | 100% | 100% | 100% |
| Volume (nm^3) | 100% | 0% | 100% | 100% |

### `Community labels` Field Format

This field encodes free-text metadata using inconsistent delimiters across datasets:

**MANC example**:
```
description::Giant fiber,group::10000,instance::DNlt002_CvC_R,rootLocation::[24481, 36044, 67070],rootSide::RHS,synonyms::GF, Giant Fiber,transmission::electrical,vfbId::VFB_jrcv07ps
```

**MAOL example**:
```
celltypePredictedNt::gaba,celltypePredictedNtConfidence::0.77603704,consensusNt::gaba,instance::CT1_L,ntReference::Takemura et al 2017,statusLabel::Roughly traced
```

**MCNS example**:
```
hemibrainType: Giant Fiber,instance: DNp01(GF),mancBodyid: 10000,statusLabel: Roughly traced,synonyms: Kennedy and Broadie 2018: GF
```

**Key observations**:
- MANC uses `::` as key-value separator, `,` as pair separator
- MAOL uses `::` as key-value separator, `,` as pair separator
- MCNS uses `: ` (colon+space) as key-value separator, `,` as pair separator
- Field presence varies (MANC has `vfbId`, MAOL has `ntReference`, MCNS has `hemibrainType`)
- **Loader should store this field raw**; a dedicated `parse_community_labels()` utility is recommended for downstream use

---

## 3.4 FAFB Neurons Schema

**File**: `neurons.csv.gz`  
**Applies to**: FAFB_v783 only  
**Columns**: 10  
**Header style**: All lowercase, underscore-separated

| # | Column | Raw Name | Type | Nullable | Description | Biological Meaning |
|---|--------|---------|------|----------|-------------|-------------------|
| 0 | root_id | `root_id` | int64 | No (PK) | Unique neuron identifier (18-digit) | FlyWire proofreading root ID |
| 1 | group | `group` | str | No | Anatomical group/region | Neuropil region the neuron primarily belongs to (e.g., `LO.LOP`, `ME`) |
| 2 | nt_type | `nt_type` | str | Yes | Predicted NT type | Neurotransmitter identity (14.1% empty) |
| 3 | nt_type_score | `nt_type_score` | float | No | Confidence for top NT | Range 0.0–1.0; 0% null |
| 4 | da_avg | `da_avg` | float | No | Dopamine probability | ML probability of dopaminergic identity |
| 5 | ser_avg | `ser_avg` | float | No | Serotonin probability | ML probability of serotonergic identity |
| 6 | gaba_avg | `gaba_avg` | float | No | GABA probability | ML probability of GABAergic identity |
| 7 | glut_avg | `glut_avg` | float | No | Glutamate probability | ML probability of glutamatergic identity |
| 8 | ach_avg | `ach_avg` | float | No | Acetylcholine probability | ML probability of cholinergic identity |
| 9 | oct_avg | `oct_avg` | float | No | Octopamine probability | ML probability of octopaminergic identity |

**Important**: FAFB `neurons.csv.gz` contains **only NT scores** — no flow, super_class, class, hemilineage, soma_side, or cell type information. That data lives in `classification.csv.gz` and `consolidated_cell_types.csv.gz`.

---

## 3.5 FAFB Classification Schema

**File**: `classification.csv.gz`  
**Applies to**: FAFB_v783 only  
**Columns**: 8  
**Rows**: 139,255 (matches FAFB neurons exactly)

| # | Column | Raw Name | Type | Nullable | Description | Biological Meaning |
|---|--------|---------|------|----------|-------------|-------------------|
| 0 | root_id | `root_id` | int64 | No (PK) | Neuron identifier | Joins to neurons.csv.gz and connections |
| 1 | flow | `flow` | str | No | Signal flow | `intrinsic`, `afferent`, `efferent` |
| 2 | super_class | `super_class` | str | No | Top-level class | Broad neuron category |
| 3 | class | `class` | str | Yes | Mid-level class | 22.7% null |
| 4 | sub_class | `sub_class` | str | Yes | Detailed sub-class | 28.0% null |
| 5 | hemilineage | `hemilineage` | str | Yes | Developmental lineage | 73.0% null |
| 6 | side | `side` | str | Yes | Hemisphere | 0.02% null; `left`, `right` |
| 7 | nerve | `nerve` | str | Yes | Nerve bundle | 93.1% null |

---

## 3.6 FAFB Consolidated Cell Types Schema

**File**: `consolidated_cell_types.csv.gz`  
**Applies to**: FAFB_v783 only  
**Columns**: 3  
**Rows**: 138,327 (928 fewer than total neurons — those neurons are unclassified)

| # | Column | Raw Name | Type | Nullable | Description | Biological Meaning |
|---|--------|---------|------|----------|-------------|-------------------|
| 0 | root_id | `root_id` | int64 | No (PK) | Neuron identifier | Joins to neurons; 928 neurons absent = unclassified |
| 1 | primary_type | `primary_type` | str | No | Primary cell type | Standard FlyWire type name (e.g., `T4b`) |
| 2 | additional_types | `additional_type(s)` | str | Yes | Additional types | Comma-separated alternative identities; 89.9% empty |
