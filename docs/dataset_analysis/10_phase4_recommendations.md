# 10 — Phase 004 Implementation Recommendations

> Concrete, ordered recommendations for implementing `core/data_loader.py`.  
> Based entirely on findings from Documents 01–09.

---

## 10.1 Graph Construction Information (Phase 005 Preview)

Although graph construction belongs to Phase 005, the following information was identified during dataset analysis:

| Graph Element | Source | Notes |
|--------------|--------|-------|
| **Nodes** | `neurons.csv.gz` | Each `root_id` is one node |
| **Edges** | `connections_princeton.csv.gz` | Each row is one directed edge |
| **Edge weight** | `syn_count` | Primary weight for all graphs |
| **Node: NT type** | `predicted_nt_type` (neurons) | Used for biological grouping |
| **Node: NT confidence** | `predicted_nt_confidence` (neurons) | Filters unreliable predictions |
| **Node: cell type** | `primary_cell_type` (neurons) | Identity for neuron matching |
| **Node: flow** | `flow` (neurons) | Afferent/efferent/intrinsic |
| **Node: super_class** | `super_class` (neurons) | High-level graph partition |
| **Node: soma_side** | `soma_side` (neurons) | Left/right hemisphere |
| **Edge: neuropil** | `neuropil` (connections) | Region-specific subgraphs |
| **Edge: NT type** | `nt_type` (connections) | Only reliable in FAFB |
| **FAFB: NT proba** | `da_avg`, `gaba_avg`, etc. | Per-neuron NT distribution |
| **Multi-edge** | `(pre, post, neuropil)` | Same pair may have multiple edges |
| **Aggregated weight** | `sum(syn_count)` by `(pre, post)` | For simple directed graphs |

---

## 10.2 Implementation Order

Implement `core/data_loader.py` in this exact order:

### Step 1: Foundation — Path Validation & Discovery

```
load_dataset(path, config)
    → validate path exists
    → discover files in directory
    → detect schema variant (21-col Princeton vs 10-col FAFB)
    → build file manifest (mandatory present? optional present?)
    → raise DatasetNotFoundError if mandatory files missing
```

**Why first**: All subsequent steps depend on knowing which files exist and which schema is in use.

---

### Step 2: Connections Loader (Simpler Schema)

Implement the connections loader first because:
- Schema is identical across all 5 datasets (lowest complexity)
- Establishes the ID dtype handling pattern
- Confirms chunked loading works before tackling neurons

```
_load_connections(path, chunk_size)
    → pd.read_csv(path, compression='gzip', dtype={'pre_root_id': 'int64', ...})
    → validate syn_count > 0
    → return DataFrame with canonical column names
```

---

### Step 3: Princeton Neurons Loader

```
_load_princeton_neurons(path)
    → pd.read_csv(path, compression='gzip', dtype={'Root ID': 'int64'})
    → apply explicit column rename mapping (not algorithmic normalization)
    → cast dtypes for float columns
    → set root_id as index
    → return DataFrame with canonical column names
```

---

### Step 4: FAFB Neurons Loader (Multi-File)

```
_load_fafb_neurons(neurons_path, classification_path, cell_types_path)
    → load neurons.csv.gz (10 columns)
    → rename columns to canonical names
    → if classification_path exists: load + left join on root_id
    → if cell_types_path exists: load + left join on root_id
    → add NaN columns for Princeton-only fields (community_labels, etc.)
    → set root_id as index
    → return combined DataFrame
```

---

### Step 5: Column Uniformity Pass

After loading neurons (either variant), add NaN-filled columns for all standard columns not present in the current dataset. This ensures downstream code never encounters a `KeyError` regardless of dataset.

```
_ensure_standard_columns(df, schema_variant)
    → for each column in STANDARD_NEURON_COLUMNS:
        if column not in df: df[column] = None
    → return df
```

---

### Step 6: Validation

```
_validate(neurons, connections) → ValidationReport
    → check duplicate root_ids in neurons
    → check duplicate (pre, post, neuropil) in connections
    → check syn_count >= 1
    → check mandatory columns present
    → compute null_rates for all key columns
    → optionally: check referential integrity
    → return ValidationReport
```

---

### Step 7: Assemble FlyWireDataset Object

```
return FlyWireDataset(
    dataset_name=...,
    version=...,
    neurons=neurons_df,
    connections=connections_df,
    metadata=DatasetMetadata(...),
    validation=validation_report,
    extras=DatasetExtras(...) if fafb else None,
    load_time_seconds=elapsed
)
```

---

## 10.3 Validation Strategy

| Check | When | Behavior |
|-------|------|---------|
| Path exists | Before loading | Raise `DatasetNotFoundError` |
| Mandatory files present | Before loading | Raise `DatasetLoadError` |
| Schema variant detection | After reading header | Set internal flag; no error |
| Column rename success | After renaming | Raise `SchemaError` if expected columns missing |
| syn_count >= 1 | After loading connections | Log WARNING; report count |
| Duplicate neuron IDs | After loading neurons | Log WARNING; report count |
| Duplicate connection triplets | After loading connections | Log WARNING; report count |
| Mandatory standard columns present | After normalization pass | Raise `SchemaError` |
| Referential integrity | Optional (disabled by default) | Log WARNING; report count |

**Rule**: The loader should never silently correct data. It should either raise (critical) or warn (non-critical) and continue.

---

## 10.4 Error Handling

Define these custom exceptions in `core/data_loader.py`:

```python
class DatasetNotFoundError(Exception):
    """Raised when the dataset directory does not exist."""

class DatasetLoadError(Exception):
    """Raised when mandatory files are missing or unreadable."""

class SchemaError(Exception):
    """Raised when expected columns are absent after normalization."""
```

All other unexpected errors (e.g., corrupt gzip, malformed CSV) should propagate naturally without being caught and hidden.

---

## 10.5 Logging Strategy

Use Python's standard `logging` module. Do not use `print()`.

```python
import logging
logger = logging.getLogger(__name__)

# Use these levels:
logger.debug(...)    # File paths, column lists, row counts (verbose)
logger.info(...)     # "Loading BANC_v888 connections (3.9M rows)..."
logger.warning(...)  # Missing optional files, empty nt_type, null rates
logger.error(...)    # Failures (before raising exceptions)
```

---

## 10.6 Reusable Design Decisions

| Decision | Rationale |
|---------|-----------|
| Explicit column mapping dict | Algorithmic normalization fails on `(nm)`, `^`, `/` |
| LEFT JOIN for FAFB files | Preserves all 139,255 neurons; 928 unclassified become NaN |
| NaN-fill missing standard columns | Eliminates KeyError in downstream analyses regardless of dataset |
| `int64` for all IDs | Handles 18-digit BANC/FAFB IDs; safe for small MANC/MAOL/MCNS IDs |
| Store `community_labels` raw | Cross-dataset parsing requires dataset-specific logic |
| `connections_nt_type_populated` flag | Prevents silent empty results in NT-based analyses |
| `DatasetConfig` injection | No metadata.json exists; config is the only metadata source |
| Chunk loading for connections | FAFB (5.3M rows) may hit Kaggle memory limits |
| Separate validation dataclass | Clean separation; validation results can be logged/exported |

---

## 10.7 Recommended pandas Configuration

```python
pd.read_csv(
    path,
    compression='gzip',
    dtype={
        'root_id': 'int64',        # or 'Root ID' before rename
        'pre_root_id': 'int64',
        'post_root_id': 'int64',
        'syn_count': 'int32',
    },
    na_values=['', 'NA', 'NaN', 'None'],   # Treat empty strings as NaN
    keep_default_na=True,
    encoding='utf-8',
)
```

---

## 10.8 Caching Recommendation (Phase 004 Optional)

After loading and normalizing, the loader can optionally cache the result as parquet:

```
research_data/cache/{dataset_name}_{version}/
    neurons.parquet
    connections.parquet
```

Parquet preserves dtypes, supports nullable int64, and is ~3× faster to load than gzip CSV. This significantly accelerates repeated Kaggle runs.

**Not required for Phase 004**. Implement after the core loader is working.

---

## 10.9 Testing Checklist for Phase 004

Before marking Phase 004 complete, verify:

- [ ] All 5 datasets load without error
- [ ] BANC/FAFB IDs are stored as int64 (verify max value > 2^31)
- [ ] FAFB neuron table has all 139,255 rows after join
- [ ] FAFB neuron table contains `flow`, `super_class` from classification.csv
- [ ] All standard columns present in all 5 loaded datasets (no KeyError)
- [ ] `community_labels` column is raw string (not parsed)
- [ ] ValidationReport shows 0 duplicates for all datasets
- [ ] ValidationReport shows 0 negative syn_count for all datasets
- [ ] Logging emits INFO for each major step
- [ ] `load_time_seconds` is captured for all 5 datasets
- [ ] MCNS loads without error despite 100% UNASGD neuropil
- [ ] DatasetNotFoundError is raised with clear message if path doesn't exist
