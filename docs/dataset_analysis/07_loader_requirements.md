# 07 — Loader Requirements

> Concrete technical requirements for `core/data_loader.py` derived from the actual dataset properties.  
> Every requirement is justified by a specific observed dataset characteristic.

---

## 7.1 Mandatory Files (Must Load)

| File | Datasets | Justification |
|------|---------|--------------|
| `neurons.csv.gz` | All | Graph node table; primary key source |
| `connections_princeton.csv.gz` | All | Graph edge table; cannot build graph without it |

If either mandatory file is missing, the loader must raise a `DatasetLoadError` with the missing file path.

---

## 7.2 Optional Files (Load If Present)

| File | Datasets | If Missing |
|------|---------|-----------|
| `classification.csv.gz` | FAFB only | Log warning; FAFB neuron table will lack morphological classification |
| `consolidated_cell_types.csv.gz` | FAFB only | Log warning; FAFB neurons will have no cell type labels |

---

## 7.3 Unused Files

None — all currently present files have biological relevance. No files should be silently ignored.

---

## 7.4 Functional Requirements

### FR-01: Gzip Transparency

**Requirement**: The loader must transparently decompress `.csv.gz` files without requiring pre-decompression.  
**Justification**: All 12 files across all datasets are gzip-compressed.  
**Implementation**: Use `gzip.open(path, 'rt', encoding='utf-8')` or `pd.read_csv(path, compression='gzip')`.

---

### FR-02: Column Normalization

**Requirement**: After loading any CSV, the loader must normalize all column names to snake_case canonical names.  
**Justification**: FAFB uses lowercase+underscore; Princeton datasets use mixed-case with spaces and special characters (`(`, `)`, `/`, `^`). Downstream code cannot use a single column accessor without normalization.  
**Normalization rules**: See Document 05, Section 5.2 for the complete mapping.  
**Special cases**: `class` → `class_` (avoid Python keyword collision).

---

### FR-03: ID Datatype Safety

**Requirement**: All neuron ID columns (`root_id`, `pre_root_id`, `post_root_id`) must be loaded as `int64`.  
**Justification**: BANC/FAFB use 18-digit IDs exceeding `int32` max (2,147,483,647). Loading as int32 silently corrupts values.  
**Alternative**: `str` type is safe but increases memory usage.

---

### FR-04: Schema Detection

**Requirement**: The loader must detect which schema variant a `neurons.csv.gz` uses (Princeton vs FAFB) before applying column normalization.  
**Justification**: Princeton = 21 columns; FAFB = 10 columns. The column count alone is a reliable discriminator.  
**Implementation**: Check `len(df.columns)` after reading the header row.

---

### FR-05: FAFB Multi-File Join

**Requirement**: When loading FAFB, the loader must automatically join `classification.csv.gz` and `consolidated_cell_types.csv.gz` onto the neuron table.  
**Justification**: FAFB's neuron table is incomplete without these files (lacks all classification data).  
**Join type**: LEFT JOIN on `root_id`. FAFB neurons without cell type entries should have NaN, not be dropped.  
**Join sequence**: neurons → LEFT JOIN classification → LEFT JOIN cell_types.

---

### FR-06: Nullable Column Handling

**Requirement**: All columns with observed null/empty rates must be loaded as nullable types (not strict non-null).  
**Justification**: Numerous columns are partially or fully empty (see Document 03 for per-dataset null rates).  
**Implementation**: Use `dtype=object` for string columns; `pd.Float64Dtype()` for float columns that may be null; `pd.Int64Dtype()` for integer columns that may have NaN.

---

### FR-07: `syn_count` Validation

**Requirement**: After loading connections, validate that all `syn_count` values are positive integers (> 0).  
**Justification**: No negative values were observed in any dataset, but this is a fundamental data integrity invariant. A negative synapse count indicates data corruption.  
**Behavior**: Log a WARNING and report count of invalid rows. Do not fail hard unless configured to do so.

---

### FR-08: Duplicate Detection

**Requirement**: After loading, optionally check for duplicate rows.  
**Justification**: No duplicates were found in this analysis, but this should be verified at load time in case datasets are updated.  
**For neurons**: duplicate `root_id`.  
**For connections**: duplicate `(pre_root_id, post_root_id, neuropil)` triplet.  
**Behavior**: Log WARNING with count. Do not silently deduplicate unless `deduplicate=True` is passed.

---

### FR-09: Dataset Metadata Injection

**Requirement**: The loader must accept a `DatasetConfig` object (from the configuration system) and attach its metadata to the returned dataset object.  
**Justification**: No `metadata.json` exists in any dataset directory. Metadata (version, organism, brain region) must come from `configs/datasets/*.yaml`.

---

### FR-10: Progress Reporting

**Requirement**: The loader must emit progress messages (via Python `logging`) at key steps: opening file, reading header, loading rows, joining files, validation complete.  
**Justification**: The largest file (FAFB connections: 5.3M rows) takes noticeable time. Silent loading degrades user experience and makes debugging difficult.

---

### FR-11: Chunk Loading Support

**Requirement**: The loader must support chunk-based loading of the connections table.  
**Justification**: FAFB connections (5.3M rows, ~320 MB in memory) may exceed Kaggle's available RAM when combined with other data structures. Streaming/chunk loading avoids OOM.  
**Implementation**: Use `pd.read_csv(..., chunksize=N)`. The recommended chunk size: 500,000 rows (configurable).  
**Note**: Chunk loading is optional for neuron tables (max 166K rows, well within memory).

---

### FR-12: Schema Validation

**Requirement**: The loader must validate that mandatory columns are present after loading and normalization.  
**Justification**: If a dataset is updated and columns are renamed upstream, the framework should fail fast with a clear error rather than a KeyError deep in an analysis.  
**Minimum required columns**:
- Neurons: `root_id`
- Connections: `pre_root_id`, `post_root_id`, `syn_count`

---

### FR-13: `community_labels` Raw Storage

**Requirement**: The `community_labels` field must be stored as a raw string and never parsed inside the loader.  
**Justification**: The format varies across datasets (MANC/MAOL use `::`, MCNS uses `: `). Unified parsing in the loader would require dataset-specific logic that violates the generic loader principle.  
**Downstream**: A utility function `parse_community_labels(value, dataset_name)` should be provided separately.

---

## 7.5 Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Minimum connections load speed | ≤ 60 seconds for FAFB (5.3M rows) on Kaggle hardware |
| Peak memory for single dataset | ≤ 500 MB (all files combined, in-memory) |
| Python version compatibility | 3.9+ |
| Required libraries | `pandas`, `gzip` (stdlib), `csv` (stdlib) |
| Optional libraries | `pyarrow` (for parquet caching), `tqdm` (for progress bars) |

---

## 7.6 Required vs Optional Capabilities

| Capability | Status | Priority |
|-----------|--------|---------|
| Gzip decompression | Required | P0 |
| Column normalization | Required | P0 |
| int64 ID loading | Required | P0 |
| Schema detection (Princeton vs FAFB) | Required | P0 |
| Mandatory file validation | Required | P0 |
| FAFB multi-file join | Required | P0 |
| Logging | Required | P1 |
| syn_count validation | Required | P1 |
| Duplicate detection | Optional | P2 |
| Chunk loading | Optional | P2 |
| Parquet caching | Optional | P3 |
| Foreign key integrity check | Optional | P3 |
