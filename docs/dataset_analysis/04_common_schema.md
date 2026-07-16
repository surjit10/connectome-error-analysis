# 04 — Common Schema

> Cross-dataset column presence matrix based on direct file inspection.  
> ✓ = column present and named exactly  
> ✗ = column absent  
> ~ = equivalent data present but under a different name or in a different file

---

## 4.1 Connections Table — Column Presence Matrix

All 5 datasets share an **identical** connections schema. No differences exist.

| Column | BANC | FAFB | MANC | MAOL | MCNS |
|--------|------|------|------|------|------|
| `pre_root_id` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `post_root_id` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `neuropil` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `syn_count` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `nt_type` | ✓ (empty) | ✓ (populated) | ✓ (empty) | ✓ (empty) | ✓ (empty) |

**Verdict**: Connections schema is fully universal. One parser handles all datasets.

---

## 4.2 Neurons Table — Column Presence Matrix

FAFB uses a completely different schema. The other four share the same 21-column Princeton schema.

### Morphological Classification Columns

| Column | BANC | FAFB | MANC | MAOL | MCNS |
|--------|------|------|------|------|------|
| `root_id` / `Root ID` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `flow` / `Flow` | ✓ | ~ (classification.csv) | ✓ | ✓ | ✓ |
| `super_class` / `Super Class` | ✓ | ~ (classification.csv) | ✓ | ✓ | ✓ |
| `class` / `Class` | ✓ | ~ (classification.csv) | ✓ | ✓ | ✓ |
| `sub_class` / `Sub Class` | ✓ | ~ (classification.csv) | ✓ | ✓ | ✓ |
| `hemilineage` / `Hemilineage` | ✓ | ~ (classification.csv) | ✓ | ✓ | ✓ |
| `soma_side` / `Soma side` | ✓ | ~ (`side` in classification.csv) | ✓ | ✓ | ✓ |
| `nerve` / `Nerve` | ✓ | ~ (classification.csv) | ✓ | ✓ | ✓ |

### NT Information Columns

| Column | BANC | FAFB | MANC | MAOL | MCNS |
|--------|------|------|------|------|------|
| `predicted_nt_type` / `Predicted NT type` | ✓ | ✓ (`nt_type`) | ✓ | ✓ | ✓ |
| `predicted_nt_confidence` / `Predicted NT confidence` | ✓ | ✓ (`nt_type_score`) | ✓ | ✓ | ✓ |
| `verified_nt_type` / `Verified NT type` | ✓ | ✗ | ✓ | ✓ | ✓ |
| `da_avg` | ✗ | ✓ | ✗ | ✗ | ✗ |
| `ser_avg` | ✗ | ✓ | ✗ | ✗ | ✗ |
| `gaba_avg` | ✗ | ✓ | ✗ | ✗ | ✗ |
| `glut_avg` | ✗ | ✓ | ✗ | ✗ | ✗ |
| `ach_avg` | ✗ | ✓ | ✗ | ✗ | ✗ |
| `oct_avg` | ✗ | ✓ | ✗ | ✗ | ✗ |

### Annotation & Cell Type Columns

| Column | BANC | FAFB | MANC | MAOL | MCNS |
|--------|------|------|------|------|------|
| `primary_cell_type` / `Primary Cell Type` | ✓ | ~ (consolidated_cell_types.csv) | ✓ | ✓ | ✓ |
| `alternative_cell_types` / `Alternative Cell Type(s)` | ✓ | ~ (`additional_type(s)`) | ✓ | ✓ | ✓ |
| `top_region` / `Top in/out region` | ✓ | ~ (`group`) | ✓ | ✓ | ✓ |
| `community_labels` / `Community labels` | ✓ | ✗ | ✓ | ✓ | ✓ |
| `verified_neuropeptide` / `Verified Neuropeptide` | ✓ | ✗ | ✓ | ✓ | ✓ |
| `body_part` / `Body Part` | ✓ | ✗ | ✓ | ✓ | ✓ |
| `function` / `Function` | ✓ | ✗ | ✓ | ✓ | ✓ |

### Morphology Columns

| Column | BANC | FAFB | MANC | MAOL | MCNS |
|--------|------|------|------|------|------|
| `Cable length (nm)` | ✓ (empty) | ✗ | ✓ (empty) | ✓ (empty) | ✓ (empty) |
| `Surface area (nm^2)` | ✓ (empty) | ✗ | ✓ (empty) | ✓ (empty) | ✓ (empty) |
| `Volume (nm^3)` | ✓ (empty) | ✗ | ✓ (populated) | ✓ (empty) | ✓ (empty) |

---

## 4.3 Truly Universal Columns (All Datasets, All Files)

The only columns that are **semantically present in all 5 datasets** (possibly under different names):

| Semantic Field | BANC | FAFB | MANC | MAOL | MCNS |
|---------------|------|------|------|------|------|
| Neuron ID | `Root ID` | `root_id` | `Root ID` | `Root ID` | `Root ID` |
| Predicted NT type | `Predicted NT type` | `nt_type` | `Predicted NT type` | `Predicted NT type` | `Predicted NT type` |
| Predicted NT confidence | `Predicted NT confidence` | `nt_type_score` | `Predicted NT confidence` | `Predicted NT confidence` | `Predicted NT confidence` |
| Primary cell type | `Primary Cell Type` | via `consolidated_cell_types.csv` | `Primary Cell Type` | `Primary Cell Type` | `Primary Cell Type` |
| Flow | `Flow` | via `classification.csv` | `Flow` | `Flow` | `Flow` |
| Super class | `Super Class` | via `classification.csv` | `Super Class` | `Super Class` | `Super Class` |
| Soma side | `Soma side` | `side` (classification.csv) | `Soma side` | `Soma side` | `Soma side` |

---

## 4.4 FAFB-Exclusive Columns (No Equivalent in Other Datasets)

| Column | Location | Notes |
|--------|----------|-------|
| `group` | neurons.csv.gz | Closest equivalent is `Top in/out region` in Princeton schema |
| `da_avg` | neurons.csv.gz | Per-NT probability breakdown not available elsewhere |
| `ser_avg` | neurons.csv.gz | Per-NT probability breakdown |
| `gaba_avg` | neurons.csv.gz | Per-NT probability breakdown |
| `glut_avg` | neurons.csv.gz | Per-NT probability breakdown |
| `ach_avg` | neurons.csv.gz | Per-NT probability breakdown |
| `oct_avg` | neurons.csv.gz | Per-NT probability breakdown |

---

## 4.5 Princeton-Exclusive Columns (Not in FAFB)

| Column | Notes |
|--------|-------|
| `Verified NT type` | Experimental validation; 100% empty in MANC, MAOL, MCNS |
| `Verified Neuropeptide` | 95–100% empty across all Princeton datasets |
| `Body Part` | Anatomical body segment; 87–100% empty |
| `Function` | Functional category; 84–100% empty |
| `Community labels` | Semi-structured metadata string |
| `Cable length (nm)` | 100% empty in all Princeton datasets |
| `Surface area (nm^2)` | 100% empty in all Princeton datasets |
| `Volume (nm^3)` | Only populated in MANC |
