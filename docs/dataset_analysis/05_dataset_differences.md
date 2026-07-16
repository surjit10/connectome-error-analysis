# 05 — Dataset Differences

> This document catalogs every confirmed difference between datasets.  
> Each difference includes the impact on a generic loader and the recommended handling strategy.

---

## 5.1 Neuron ID Format

**This is the most critical difference for the loader.**

| Dataset | ID Format | Example | Datatype |
|---------|----------|---------|---------|
| BANC | 18-digit FlyWire root ID | `720575940381905254` | uint64 |
| FAFB | 18-digit FlyWire root ID | `720575940596125868` | uint64 |
| MANC | Small integer body ID | `10000` | int32 or int64 |
| MAOL | Small integer body ID | `10009` | int32 or int64 |
| MCNS | Small integer body ID | `10001` | int32 or int64 |

**Implications**:
- IDs cannot be used as cross-dataset references. The same integer value may refer to different neurons in different datasets.
- The loader **must not attempt to join neuron IDs across datasets**.
- BANC/FAFB IDs exceed int32 range. The loader must use `int64` (or `uint64`) for all ID columns regardless of dataset.
- Using `uint64` is safest for BANC/FAFB; MANC/MAOL/MCNS fit in `int32` but using `int64` universally avoids type mismatches.
- **Recommendation**: Store all IDs as `int64` (or string if precision is a concern with pandas).

---

## 5.2 Neurons File Column Name Case and Spaces

| Dataset | Header Style | Example |
|---------|-------------|---------|
| BANC | Mixed-case with spaces | `Root ID`, `Super Class`, `Cable length (nm)` |
| FAFB | Lowercase with underscores | `root_id`, `nt_type`, `nt_type_score` |
| MANC | Mixed-case with spaces | `Root ID`, `Super Class`, `Cable length (nm)` |
| MAOL | Mixed-case with spaces | `Root ID`, `Super Class`, `Cable length (nm)` |
| MCNS | Mixed-case with spaces | `Root ID`, `Super Class`, `Cable length (nm)` |

**Implication**: The loader cannot use the same column accessor for FAFB vs Princeton datasets.  
**Recommendation**: Apply a normalization step — lowercase + replace spaces/special chars with underscores — as the first step after loading any CSV. Then work with canonical column names.

**Normalization mapping** (Princeton → canonical):

| Raw Name | Canonical Name |
|----------|---------------|
| `Root ID` | `root_id` |
| `Top in/out region` | `top_region` |
| `Community labels` | `community_labels` |
| `Predicted NT type` | `predicted_nt_type` |
| `Predicted NT confidence` | `predicted_nt_confidence` |
| `Verified NT type` | `verified_nt_type` |
| `Verified Neuropeptide` | `verified_neuropeptide` |
| `Body Part` | `body_part` |
| `Function` | `function` |
| `Flow` | `flow` |
| `Super Class` | `super_class` |
| `Class` | `class_` (avoid Python keyword) |
| `Sub Class` | `sub_class` |
| `Hemilineage` | `hemilineage` |
| `Nerve` | `nerve` |
| `Soma side` | `soma_side` |
| `Primary Cell Type` | `primary_cell_type` |
| `Alternative Cell Type(s)` | `alternative_cell_types` |
| `Cable length (nm)` | `cable_length_nm` |
| `Surface area (nm^2)` | `surface_area_nm2` |
| `Volume (nm^3)` | `volume_nm3` |

**FAFB normalization** (`group` → `top_region`, `nt_type` → `predicted_nt_type`, etc.):

| Raw FAFB Name | Canonical Name |
|--------------|---------------|
| `root_id` | `root_id` |
| `group` | `top_region` |
| `nt_type` | `predicted_nt_type` |
| `nt_type_score` | `predicted_nt_confidence` |
| `da_avg` | `da_avg` |
| `ser_avg` | `ser_avg` |
| `gaba_avg` | `gaba_avg` |
| `glut_avg` | `glut_avg` |
| `ach_avg` | `ach_avg` |
| `oct_avg` | `oct_avg` |

---

## 5.3 Number of Files Per Dataset

| Dataset | Files | Extra Files vs Minimum |
|---------|-------|----------------------|
| BANC | 2 | — |
| FAFB | 4 | +classification.csv.gz, +consolidated_cell_types.csv.gz |
| MANC | 2 | — |
| MAOL | 2 | — |
| MCNS | 2 | — |

**Implication**: The loader must handle the FAFB case where classification and cell type data are split across separate files. FAFB's neuron table is incomplete on its own and requires joining with these extra files.  
**Recommendation**: Implement dataset-specific file manifests in `configs/datasets/*.yaml` or in the loader's internal registry.

---

## 5.4 Neuron Count vs Classification Coverage (FAFB)

| Table | Rows |
|-------|------|
| neurons.csv.gz | 139,255 |
| classification.csv.gz | 139,255 |
| consolidated_cell_types.csv.gz | 138,327 |

**Difference**: 928 neurons exist in neurons.csv but not in consolidated_cell_types.csv. These are unclassified neurons.  
**Recommendation**: Use a left join (neurons as left table) to preserve all neurons; missing cell types become NaN.

---

## 5.5 `nt_type` Column in Connections — Population Rate

| Dataset | nt_type in connections | Population |
|---------|----------------------|-----------|
| BANC | column present | 0% — always empty |
| FAFB | column present | 100% populated (ACH, GABA, GLUT, DA, OCT, SER) |
| MANC | column present | 0% — always empty |
| MAOL | column present | 0% — always empty |
| MCNS | column present | 0% — always empty |

**Implication**: Edge-level NT type is only reliable in FAFB. For other datasets, NT type must be inferred from the neuron table using the presynaptic neuron's `predicted_nt_type`.  
**Recommendation**: The loader should document this difference via a metadata flag: `connections_nt_type_populated: bool`.

---

## 5.6 Neuropil Values and Conventions

| Dataset | Neuropil Style | Examples | Notes |
|---------|--------------|---------|-------|
| BANC | Hemisphere-suffixed | `AL_L`, `AL_R`, `ME_R` | Bilateral brain + VNC |
| FAFB | Hemisphere-suffixed | `ME_L`, `LA_L` | Appears limited in sample |
| MANC | VNC-specific codes | `CV`, `LTct`, `LegNp_T1_L` | VNC neuropils; no standard FlyWire regions |
| MAOL | Optic lobe codes | `LO_R`, `LOP_R`, `ME_R` | Right hemisphere focused; uses `NotPrimary` |
| MCNS | `UNASGD` | `UNASGD` | All sampled connections unassigned; neuropil data may be absent |

**Implication**: Neuropil codes are **not standardized** across datasets. Cross-dataset neuropil comparison requires a mapping table.  
**Uncertainty**: The MCNS neuropil situation (100% UNASGD in the first 6.2M rows) may be dataset-wide. This should be verified by spot-checking deep rows.  
**Recommendation**: Neuropil is stored as a raw string. No validation is imposed on values. Downstream analyses are responsible for neuropil-level filtering.

---

## 5.7 Morphology Column Availability

| Column | BANC | MANC | MAOL | MCNS |
|--------|------|------|------|------|
| Cable length (nm) | ✓ (present, 100% empty) | ✓ (present, 100% empty) | ✓ (present, 100% empty) | ✓ (present, 100% empty) |
| Surface area (nm^2) | ✓ (present, 100% empty) | ✓ (present, 100% empty) | ✓ (present, 100% empty) | ✓ (present, 100% empty) |
| Volume (nm^3) | ✓ (present, 100% empty) | ✓ (present, **0% empty**) | ✓ (present, 100% empty) | ✓ (present, 100% empty) |

FAFB has none of these columns at all.  
Only MANC has `Volume (nm^3)` populated.  
**Recommendation**: These columns should be loaded but flagged as unreliable metadata. The loader should not raise an error if they are empty.

---

## 5.8 `Community labels` Field Format Inconsistency

Three different key-value encodings observed:

| Dataset | Delimiter | Example Key | Example Value |
|---------|---------|-------------|--------------|
| MANC | `::` (key-value), `,` (pairs) | `description` | `Giant fiber` |
| MAOL | `::` (key-value), `,` (pairs) | `celltypePredictedNt` | `gaba` |
| MCNS | `: ` (key-value), `,` (pairs) | `hemibrainType` | `Giant Fiber` |
| BANC | Unknown (14.6% empty, rest varies) | — | — |

This field cannot be parsed uniformly without a dataset-specific parser.  
**Recommendation**: Store `community_labels` as a raw string. Provide a utility function `parse_community_labels(value, dataset_name)` that applies the correct parsing logic per dataset. Do not attempt to unpack this field inside the loader itself.

---

## 5.9 Missing Metadata Files

None of the 5 datasets ship with a `metadata.json` or `README.md`. Dataset-level metadata (version, organism, coordinate space, proofreading date) must be sourced from:
1. `configs/datasets/*.yaml` — framework configuration files
2. External FlyWire documentation

**Recommendation**: The loader should accept a `DatasetConfig` object (from the config system) rather than deriving metadata from the raw files alone.

---

## 5.10 Handling Strategy Summary

| Difference | Handling Strategy |
|-----------|-----------------|
| ID format (int64 vs small int) | Use `int64` universally; never join IDs across datasets |
| Column name case/spaces | Normalize to `snake_case` immediately after CSV load |
| FAFB extra files | FAFB-specific load path that joins 3 files; controlled by dataset config |
| Empty `nt_type` in connections | Log a warning; set `connections_nt_type_populated: False` in metadata |
| MCNS `UNASGD` neuropil | Accept as valid string; no validation |
| Empty morphology columns | Load as nullable float; do not error |
| `community_labels` format variation | Store raw; defer parsing to utility function |
| No metadata.json | Derive metadata from `DatasetConfig` (configs/datasets/) |
