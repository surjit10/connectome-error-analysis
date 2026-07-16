# Phase 004 Prerequisite — Dataset Analysis Complete

## Output Location

```
/home/surjit/Desktop/flywire/v1/docs/dataset_analysis/
```

11 files created · 1,850 lines · all based on direct file inspection

---

## What Was Done

Every `.csv.gz` in `research_data/raw/` was opened, measured, and analyzed:
- Row counts (via Python csv reader)
- Column names and types (from headers + sample rows)
- Null rates per column per dataset
- Duplicate detection
- Negative value checks
- Memory estimation
- Neuropil value sampling
- NT type value sampling

---

## The 5 Most Critical Findings

### 1. Two Neuron Schemas, Not One

| Schema | Datasets | Columns | Header Style |
|--------|---------|---------|--------------|
| Princeton | BANC, MANC, MAOL, MCNS | 21 | Mixed-case with spaces |
| FAFB | FAFB | 10 | lowercase_underscore |

The loader **must** detect schema variant before normalizing.

### 2. FAFB Requires 3-File Join

FAFB splits data across `neurons.csv.gz`, `classification.csv.gz`, `consolidated_cell_types.csv.gz`.  
All three must be LEFT JOINed on `root_id` to get a complete neuron table.

### 3. ID Format is Incompatible Across Datasets

- BANC/FAFB: 18-digit `uint64` FlyWire root IDs (e.g., `720575940381905254`)
- MANC/MAOL/MCNS: Small integer body IDs (e.g., `10000`)

Never join IDs across datasets. Always load as `int64`.

### 4. `nt_type` in Connections — FAFB Only

The column exists in all datasets but is 100% empty in BANC, MANC, MAOL, MCNS.  
Only FAFB connections have NT type populated (`ACH`, `GABA`, `GLUT`, `DA`, `SER`, `OCT`).

### 5. MCNS Data Is Severely Sparse

| Column | Null Rate in MCNS |
|--------|------------------|
| Flow | 100% |
| Hemilineage | 100% |
| Nerve | 99.4% |
| neuropil in connections | 100% UNASGD |
| Cable/Surface/Volume | 100% |

MCNS v0.9 is a pre-release dataset with minimal annotation.

---

## Scale of Data

| Metric | Value |
|--------|-------|
| Total connections rows | ~28.5 million |
| Largest single file | FAFB connections (5.3M rows, 66MB compressed) |
| Total compressed size | 189 MB |
| Estimated RAM (all datasets) | ~1.9 GB |
| Recommended approach | One dataset per Kaggle run (already the framework architecture) |

---

## Documents Generated

| File | Key Content |
|------|-------------|
| [README.md](README.md) | Executive summary |
| [01_dataset_inventory.md](01_dataset_inventory.md) | All files, sizes, row counts |
| [02_file_analysis.md](02_file_analysis.md) | Mandatory / Optional / Unused classification |
| [03_csv_schema.md](03_csv_schema.md) | Full column schema + null rates per dataset |
| [04_common_schema.md](04_common_schema.md) | Cross-dataset column presence matrix |
| [05_dataset_differences.md](05_dataset_differences.md) | Every schema divergence + handling strategy |
| [06_relationships.md](06_relationships.md) | PKs, FKs, join paths, FAFB join sequence |
| [07_loader_requirements.md](07_loader_requirements.md) | 13 functional requirements + memory estimates |
| [08_standard_dataset_object.md](08_standard_dataset_object.md) | FlyWireDataset dataclass + API signature |
| [09_risks.md](09_risks.md) | 13 risks with severity + mitigation |
| [10_phase4_recommendations.md](10_phase4_recommendations.md) | 7-step implementation order + test checklist |
