# 01 — Dataset Inventory

> **Source**: Direct inspection of `research_data/raw/` via `ls -lh`, `zcat | wc -l`, and Python csv analysis.  
> All row counts, sizes, and column counts are measured, not estimated.

---

## 1.1 Directory Structure

```
research_data/raw/
├── BANC_v888/
│   ├── neurons.csv.gz                (2.8 MB compressed)
│   └── connections_princeton.csv.gz  (28 MB compressed)
│
├── FAFB_v783/
│   ├── neurons.csv.gz                (1.7 MB compressed)
│   ├── connections_princeton.csv.gz  (66 MB compressed)
│   ├── classification.csv.gz         (913 KB compressed)
│   └── consolidated_cell_types.csv.gz(881 KB compressed)
│
├── MANC_v1.2.1/
│   ├── neurons.csv.gz                (996 KB compressed)
│   └── connections_princeton.csv.gz  (26 MB compressed)
│
├── MAOL_v1.1/
│   ├── neurons.csv.gz                (1.2 MB compressed)
│   └── connections_princeton.csv.gz  (29 MB compressed)
│
└── MCNS_v0.9/
    ├── neurons.csv.gz                (2.1 MB compressed)
    └── connections_princeton.csv.gz  (30 MB compressed)
```

---

## 1.2 File Inventory Table

| Dataset | Version | File | Compressed | Rows | Columns | Format |
|---------|---------|------|-----------|------|---------|--------|
| BANC | v888 | neurons.csv.gz | 2.8 MB | 158,262 | 21 | gzip CSV |
| BANC | v888 | connections_princeton.csv.gz | 28 MB | 3,990,039 | 5 | gzip CSV |
| FAFB | v783 | neurons.csv.gz | 1.7 MB | 139,255 | 10 | gzip CSV |
| FAFB | v783 | connections_princeton.csv.gz | 66 MB | 5,342,446 | 5 | gzip CSV |
| FAFB | v783 | classification.csv.gz | 913 KB | 139,255 | 8 | gzip CSV |
| FAFB | v783 | consolidated_cell_types.csv.gz | 881 KB | 138,327 | 3 | gzip CSV |
| MANC | v1.2.1 | neurons.csv.gz | 996 KB | 23,665 | 21 | gzip CSV |
| MANC | v1.2.1 | connections_princeton.csv.gz | 26 MB | 6,239,883 | 5 | gzip CSV |
| MAOL | v1.1 | neurons.csv.gz | 1.2 MB | 52,445 | 21 | gzip CSV |
| MAOL | v1.1 | connections_princeton.csv.gz | 29 MB | 6,736,968 | 5 | gzip CSV |
| MCNS | v0.9 | neurons.csv.gz | 2.1 MB | 166,694 | 21 | gzip CSV |
| MCNS | v0.9 | connections_princeton.csv.gz | 30 MB | 6,239,112 | 5 | gzip CSV |

---

## 1.3 Dataset Totals

| Dataset | Total Compressed | Total Neurons | Total Connections | Total Files |
|---------|-----------------|--------------|------------------|-------------|
| BANC_v888 | 31 MB | 158,262 | 3,990,039 | 2 |
| FAFB_v783 | 69 MB | 139,255 | 5,342,446 | 4 |
| MANC_v1.2.1 | 27 MB | 23,665 | 6,239,883 | 2 |
| MAOL_v1.1 | 30 MB | 52,445 | 6,736,968 | 2 |
| MCNS_v0.9 | 32 MB | 166,694 | 6,239,112 | 2 |
| **TOTAL** | **189 MB** | **540,321** | **28,548,448** | **12** |

---

## 1.4 Compression Details

All files use **gzip compression** (`.csv.gz`).  
Standard Python `gzip.open(..., 'rt')` is sufficient to read them.  
No special decompression tools are required.

**Estimated uncompressed sizes** (gzip typically 4–8× compression for CSV):

| Dataset | Compressed | Estimated Uncompressed |
|---------|-----------|----------------------|
| BANC_v888 | 31 MB | ~150–250 MB |
| FAFB_v783 | 69 MB | ~350–550 MB |
| MANC_v1.2.1 | 27 MB | ~130–210 MB |
| MAOL_v1.1 | 30 MB | ~150–240 MB |
| MCNS_v0.9 | 32 MB | ~160–256 MB |

---

## 1.5 Dataset Naming Convention

Pattern: `{DATASET_NAME}_v{VERSION}/`

| Component | Example | Notes |
|-----------|---------|-------|
| Dataset name | `BANC`, `FAFB`, `MANC`, `MAOL`, `MCNS` | Uppercase acronym |
| Separator | `_v` | Literal underscore + lowercase v |
| Version | `888`, `783`, `1.2.1`, `1.1`, `0.9` | Integer or semver |

> The loader must parse this naming convention to extract `dataset_name` and `version` automatically.

---

## 1.6 Biological Context of Each Dataset

| Dataset | Full Name | Organism | Brain Region | Notes |
|---------|-----------|----------|--------------|-------|
| BANC | Brain And Nerve Cord | *Drosophila melanogaster* | Full CNS (brain + VNC) | Largest neuron count among abdominal datasets |
| FAFB | Full Adult Female Brain | *Drosophila melanogaster* | Entire adult female brain | Most complete; has extra annotation files |
| MANC | Male Adult Nerve Cord | *Drosophila melanogaster* | Ventral Nerve Cord | Smallest neuron count; largest connection count |
| MAOL | Male Adult Optic Lobe | *Drosophila melanogaster* | Optic lobe | Visual system; right-hemisphere focused |
| MCNS | Male Central Nervous System | *Drosophila melanogaster* | Full CNS | Largest neuron count overall |

---

## 1.7 Version Maturity

| Dataset | Version | Implication |
|---------|---------|-------------|
| BANC | v888 | High version number → mature, many proofreading iterations |
| FAFB | v783 | High version number → mature |
| MANC | v1.2.1 | Semantic versioning → explicitly versioned release |
| MAOL | v1.1 | Semantic versioning → early stable release |
| MCNS | v0.9 | Pre-1.0 → possibly not finalized; treat with caution |

> **Uncertainty**: The exact release semantics for version numbers are not documented in the dataset files. The MCNS v0.9 pre-release status is inferred from the version number alone.
