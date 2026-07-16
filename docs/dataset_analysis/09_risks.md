# 09 — Risks

> Every identified risk that could make Phase 004 (Data Loader) implementation difficult.  
> Each risk includes severity, probability, and a concrete mitigation.

---

## Risk Classification

| Level | Meaning |
|-------|---------|
| 🔴 HIGH | Likely to cause implementation failure or silent data corruption |
| 🟡 MEDIUM | Will cause bugs or degraded output if not handled |
| 🟢 LOW | Minor issue; good to handle but not blocking |

---

## R-01: FAFB Schema Divergence

**Severity**: 🔴 HIGH  
**Description**: FAFB neurons use a completely different 10-column schema (lowercase headers, NT probability columns, no classification data). A loader written only for the Princeton 21-column schema will silently fail or KeyError when processing FAFB.  
**Probability**: Certain — this is a confirmed structural difference.  
**Mitigation**: Implement schema detection via column count (`len(columns) == 10` = FAFB; `len(columns) == 21` = Princeton). Maintain two normalization paths.

---

## R-02: Integer ID Overflow (uint64)

**Severity**: 🔴 HIGH  
**Description**: BANC and FAFB use 18-digit neuron IDs (e.g., `720575940381905254`). If loaded as `int32`, these values overflow silently to wrong values, corrupting all edges. Some pandas configurations default to int32 on 32-bit systems.  
**Probability**: High if default dtype inference is used.  
**Mitigation**: Explicitly specify `dtype={'pre_root_id': 'int64', 'post_root_id': 'int64', 'root_id': 'int64'}` in all `pd.read_csv()` calls. Never rely on pandas dtype inference for ID columns.

---

## R-03: FAFB FAFB Multi-File Join Failure

**Severity**: 🔴 HIGH  
**Description**: If `classification.csv.gz` or `consolidated_cell_types.csv.gz` is missing from the FAFB directory, a loader that expects them will crash. More insidiously, if the join is done incorrectly (inner join instead of left join), 928 neurons with no cell type entry will be silently dropped, corrupting the neuron table count.  
**Probability**: Medium (files may not always be present; join type is easy to get wrong).  
**Mitigation**: Use LEFT JOIN always. Detect file presence before joining. Log a WARNING (not ERROR) if optional files are missing.

---

## R-04: `Community labels` Parsing Errors

**Severity**: 🟡 MEDIUM  
**Description**: The `Community labels` field uses different delimiters in different datasets (MANC: `::`, MCNS: `: `). Any downstream code that tries to parse this field without knowing the dataset may extract wrong values or crash.  
**Probability**: High if any analysis touches this column directly.  
**Mitigation**: Store raw. Document format variations. Provide `parse_community_labels(value, dataset_name)` as a separate utility. The loader itself must not parse this field.

---

## R-05: MCNS Neuropil Unassigned

**Severity**: 🟡 MEDIUM  
**Description**: All sampled MCNS connections have `neuropil = "UNASGD"`. If this is dataset-wide (6.2M rows), then neuropil-level analyses (e.g., filtering by brain region) will produce empty results for MCNS. Analyses may silently return zero rather than failing.  
**Probability**: Medium (sample is large enough to suggest it may be dataset-wide, but not confirmed).  
**Uncertainty**: Only the first 6.2M rows were sampled for neuropil — which is the entire MCNS connections table. So this is likely dataset-wide.  
**Mitigation**: Document this in the MCNS dataset config. The loader should report `neuropil_diversity` (count of distinct neuropil values) in the metadata. Analyses should check `metadata.neuropil_diversity` before performing neuropil-level filtering.

---

## R-06: Memory Exhaustion on Kaggle

**Severity**: 🟡 MEDIUM  
**Description**: Loading all 5 datasets simultaneously requires ~1.9 GB of RAM. Kaggle's standard notebook environment has ~16–32 GB, but with graph construction and analysis, total memory may exceed limits during heavy operations. The FAFB connections table alone is ~320 MB after loading.  
**Probability**: Medium (depends on what else is in memory when the loader is called).  
**Mitigation**: The loader should support `chunk_size` parameter for connections. The framework's architecture already specifies "One Kaggle Run = One Dataset" — this is the primary mitigation.

---

## R-07: Column Name Normalization Edge Cases

**Severity**: 🟡 MEDIUM  
**Description**: Column names contain special characters: `(`, `)`, `/`, `^`, spaces. A naive `str.lower().replace(' ', '_')` normalization will produce `cable_length_(nm)` instead of `cable_length_nm`. Any column accessor using the "normalized" name will KeyError.  
**Probability**: High if normalization is not carefully tested.  
**Mitigation**: Use an explicit column mapping dictionary (see Document 05, Section 5.2) rather than algorithmic normalization. Every column should be mapped by name, not by rule. The mapping must be tested with all 12 files.

---

## R-08: `class` Column as Python Keyword

**Severity**: 🟡 MEDIUM  
**Description**: `Class` normalizes to `class` — a Python reserved keyword. While pandas allows `df['class']` (bracket notation), `df.class` will cause a SyntaxError.  
**Probability**: Certain if the column is used anywhere with dot notation.  
**Mitigation**: Normalize `Class` → `class_` (with trailing underscore). This is the standard Python convention for keyword conflicts.

---

## R-09: MCNS Version Pre-Release Data Quality

**Severity**: 🟡 MEDIUM  
**Description**: MCNS is version v0.9 — pre-1.0. The dataset may have less complete annotation, higher null rates, or structural issues compared to stable releases. Confirmed: MCNS has 100% null for `Flow`, `Hemilineage`, `Nerve`, `Body Part`, `Function`, `Cable length`, `Surface area`, `Volume` in neurons, and 100% UNASGD in connections neuropil.  
**Probability**: Confirmed existing quality issues (not a risk — a certainty).  
**Mitigation**: Document MCNS quality issues in `configs/datasets/mcns.yaml`. Flag in DatasetMetadata. Do not treat null rates as errors for this dataset; treat as expected sparse annotation.

---

## R-10: Referential Integrity Gaps

**Severity**: 🟢 LOW  
**Description**: The connections table references neuron IDs as `pre_root_id` and `post_root_id`. It has not been confirmed that every ID in the connections table exists in the neurons table. If orphaned connection IDs exist, graph construction (Phase 005) will produce nodes not in the neuron table, potentially crashing attribute lookups.  
**Probability**: Low (FlyWire maintains referential integrity, but dataset versions may include fragments).  
**Mitigation**: The loader should offer an optional `check_referential_integrity=True` mode that performs a set-difference check. This should be disabled by default (too expensive for routine loading).

---

## R-11: `nt_type` in Connections — Silent Empty Field

**Severity**: 🟢 LOW  
**Description**: The `nt_type` column in connections is present in all datasets but populated only in FAFB. An analysis that assumes `nt_type` in connections is universally available will silently produce empty results for all non-FAFB datasets.  
**Probability**: Medium (easy mistake to make when writing analyses).  
**Mitigation**: The loader should set `connections_nt_type_populated: False` in metadata for all non-FAFB datasets. All analyses that use edge-level NT type should check this flag first.

---

## R-12: CSV Encoding Issues

**Severity**: 🟢 LOW  
**Description**: Some files (especially BANC with `\r\n` line endings) exhibit Windows-style carriage returns in the raw bytes. If `newline=''` is not handled correctly, rows may include trailing `\r` characters, causing silent string mismatch errors.  
**Probability**: Low if using `pandas.read_csv()` (handles this automatically); Medium if using raw `csv.reader()` without `newline=''` parameter.  
**Mitigation**: Always use `pandas.read_csv(filepath, compression='gzip')` rather than raw `gzip.open` + `csv.reader`. Pandas handles both `\n` and `\r\n` correctly.

---

## R-13: Dataset Directory Not Found

**Severity**: 🔴 HIGH  
**Description**: The entire `research_data/` directory is `.gitignore`-excluded and must be manually placed on each machine/Kaggle environment. If the loader is called before datasets are placed, it will crash with an uninformative `FileNotFoundError`.  
**Probability**: Certain for first-time runs on new machines.  
**Mitigation**: The loader should validate the dataset path at the start and raise a clear, actionable `DatasetNotFoundError(path, dataset_name)` with instructions on where to place the data.

---

## Summary Table

| Risk | Severity | Impact |
|------|---------|--------|
| R-01: FAFB schema divergence | 🔴 HIGH | Silently wrong data |
| R-02: int64 overflow | 🔴 HIGH | Silent ID corruption |
| R-03: FAFB join failure | 🔴 HIGH | Missing neuron data |
| R-13: Dataset not found | 🔴 HIGH | Crash at startup |
| R-04: Community labels parsing | 🟡 MEDIUM | Downstream errors |
| R-05: MCNS UNASGD neuropil | 🟡 MEDIUM | Silent empty results |
| R-06: Kaggle memory | 🟡 MEDIUM | OOM crash |
| R-07: Column normalization edge cases | 🟡 MEDIUM | KeyError in analyses |
| R-08: `class` keyword | 🟡 MEDIUM | SyntaxError |
| R-09: MCNS pre-release quality | 🟡 MEDIUM | Null analysis results |
| R-10: Referential integrity gaps | 🟢 LOW | Graph attribute errors |
| R-11: NT type empty in non-FAFB | 🟢 LOW | Silent empty results |
| R-12: CSV encoding carriage returns | 🟢 LOW | String mismatches |
