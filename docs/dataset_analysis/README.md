# FlyWire Dataset Analysis — Phase 004 Prerequisite

**Purpose**: This folder contains the complete reverse-engineered schema documentation for all five FlyWire connectome datasets. Every document here is derived from direct inspection of the actual `.csv.gz` files in `research_data/raw/`. No assumptions were made; all figures are measured.

**Target**: Provides everything needed to implement `core/data_loader.py` (Phase 004) without reopening the raw datasets.

---

## Documents

| File | Contents |
|------|----------|
| [01_dataset_inventory.md](01_dataset_inventory.md) | Folder structure, file sizes, row counts, compression ratio |
| [02_file_analysis.md](02_file_analysis.md) | Purpose of every file, required vs optional vs unused |
| [03_csv_schema.md](03_csv_schema.md) | Full column-by-column schema for every CSV in every dataset |
| [04_common_schema.md](04_common_schema.md) | Cross-dataset column presence matrix |
| [05_dataset_differences.md](05_dataset_differences.md) | Schema divergences, renames, ID formats, extras |
| [06_relationships.md](06_relationships.md) | Primary keys, foreign keys, join paths |
| [07_loader_requirements.md](07_loader_requirements.md) | Concrete technical requirements for the loader |
| [08_standard_dataset_object.md](08_standard_dataset_object.md) | Proposed standard internal representation |
| [09_risks.md](09_risks.md) | Implementation risks and mitigations |
| [10_phase4_recommendations.md](10_phase4_recommendations.md) | Ordered recommendations for Phase 004 implementation |

---

## Analysis Scope

| Dataset | Version | Files | Total Compressed |
|---------|---------|-------|-----------------|
| BANC | v888 | 2 | 31 MB |
| FAFB | v783 | 4 | 69 MB |
| MANC | v1.2.1 | 2 | 27 MB |
| MAOL | v1.1 | 2 | 30 MB |
| MCNS | v0.9 | 2 | 32 MB |

**Total rows across all connections tables**: ~28.5 million  
**Estimated memory to load all datasets simultaneously**: ~1.9 GB

---

## Key Findings (Executive Summary)

1. **Connections schema is identical across all 5 datasets** — 5 columns, same names, same types.
2. **Neurons schema has two distinct variants**: 21-column "Princeton format" (BANC, MANC, MAOL, MCNS) vs 10-column "FAFB-specific format".
3. **FAFB is the only dataset with extra files**: `classification.csv.gz` and `consolidated_cell_types.csv.gz`.
4. **Neuron IDs differ drastically**: BANC/FAFB use 18-digit uint64 FlyWire IDs; MANC/MAOL/MCNS use small integers (body IDs).
5. **`nt_type` in connections is populated only in FAFB**; all other datasets leave it 100% empty.
6. **Morphology columns (`Cable length`, `Surface area`, `Volume`) are entirely empty in BANC, MAOL, MCNS** and present only for MANC and FAFB (partial).
7. **`Community labels` encodes structured key-value metadata as a free-text string** in all Princeton-format datasets — requires parsing.
8. **No duplicate rows** detected in any file across all datasets.
9. **No negative `syn_count` values** detected anywhere.

---

## Analysis Date

Generated: 2026-07-16  
Analyst: Antigravity AI  
Based on: Direct file inspection of `research_data/raw/`
