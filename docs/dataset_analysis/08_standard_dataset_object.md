# 08 — Standard Dataset Object

> This document defines the **standardized internal representation** that `core/data_loader.py` should produce for every dataset.  
> Every dataset — regardless of its raw schema — should be converted to this standard form before being used by any other framework component.

---

## 8.1 Design Principles

1. **Schema-normalized**: All raw column names are mapped to canonical names.
2. **Metadata-attached**: Dataset-level metadata is always present (from config, not from CSV).
3. **Self-describing**: The object carries its own validation status.
4. **Extensible**: FAFB-specific fields are stored in an optional `extras` section, not discarded.
5. **Immutable data**: Raw DataFrames are not mutated; the object holds the loaded data.

---

## 8.2 Top-Level Dataset Object

```python
@dataclass
class FlyWireDataset:
    """
    Standardized representation of one loaded FlyWire connectome dataset.
    Returned by core/data_loader.py for every dataset.
    """
    # Identity
    dataset_name: str           # e.g., "BANC", "FAFB"
    version: str                # e.g., "v888", "v783"
    dataset_path: Path          # Absolute path to the dataset directory

    # Core tables (always populated)
    neurons: pd.DataFrame       # See Section 8.3
    connections: pd.DataFrame   # See Section 8.4

    # Metadata
    metadata: DatasetMetadata   # See Section 8.5

    # Validation
    validation: ValidationReport  # See Section 8.6

    # FAFB-specific extras (None for non-FAFB datasets)
    extras: Optional[DatasetExtras]  # See Section 8.7

    # Load timing
    load_time_seconds: float    # Wall-clock time to load this dataset
```

---

## 8.3 Neurons Table (Standard Columns)

The `neurons` DataFrame must have the following canonical columns after loading.  
Columns not available in a particular dataset are set to `None` (NaN-filled column still present).

```
neurons DataFrame:

Required columns (always present, never NaN-filled except where noted):
─────────────────────────────────────────────────────────────────────
Column Name               dtype       Nullable  Source
─────────────────────────────────────────────────────────────────────
root_id                   int64       No        PK — unique neuron ID
predicted_nt_type         str         Yes       NT prediction
predicted_nt_confidence   float64     Yes       NT confidence score
top_region                str         No        Primary anatomical region
soma_side                 str         Yes       left/right/bilateral

Classification columns (present but may be NaN):
─────────────────────────────────────────────────────────────────────
flow                      str         Yes       afferent/intrinsic/efferent
super_class               str         Yes       Broad neuron category
class_                    str         Yes       Mid-level class
sub_class                 str         Yes       Detailed sub-class
hemilineage               str         Yes       Developmental lineage
nerve                     str         Yes       Nerve bundle

Cell type columns:
─────────────────────────────────────────────────────────────────────
primary_cell_type         str         Yes       Standard cell type name
alternative_cell_types    str         Yes       Additional type labels (raw)

Princeton-only columns (NaN for FAFB):
─────────────────────────────────────────────────────────────────────
community_labels          str         Yes       Raw key-value metadata string
verified_nt_type          str         Yes       Experimental NT verification
verified_neuropeptide     str         Yes       Verified neuropeptide
body_part                 str         Yes       Body segment
function                  str         Yes       Functional category
cable_length_nm           float64     Yes       Morphology (100% NaN most datasets)
surface_area_nm2          float64     Yes       Morphology (100% NaN most datasets)
volume_nm3                float64     Yes       Morphology (mostly NaN)

FAFB-only columns (NaN for Princeton datasets):
─────────────────────────────────────────────────────────────────────
da_avg                    float64     Yes       Dopamine probability
ser_avg                   float64     Yes       Serotonin probability
gaba_avg                  float64     Yes       GABA probability
glut_avg                  float64     Yes       Glutamate probability
ach_avg                   float64     Yes       Acetylcholine probability
oct_avg                   float64     Yes       Octopamine probability
```

**Index**: Set `root_id` as the DataFrame index for O(1) neuron lookup.

---

## 8.4 Connections Table (Standard Columns)

```
connections DataFrame:

Column Name     dtype     Nullable  Source
─────────────────────────────────────────────────────────────────────
pre_root_id     int64     No        FK → neurons.root_id
post_root_id    int64     No        FK → neurons.root_id
neuropil        str       No        Brain region code
syn_count       int32     No        Edge weight (synapse count)
nt_type         str       Yes       NT type (only FAFB populated)
```

**Index**: Default RangeIndex (0-based). No composite index is set by default.  
**Note on multi-edges**: The same `(pre, post)` pair may appear multiple times with different neuropil values. This is intentional and correct.

---

## 8.5 Dataset Metadata Object

```python
@dataclass
class DatasetMetadata:
    """
    Dataset-level metadata. Derived from configs/datasets/*.yaml,
    not from the raw CSV files (which contain no metadata.json).
    """
    dataset_name: str           # "BANC"
    version: str                # "v888"
    organism: str               # "Drosophila melanogaster"
    brain_region: str           # "Full CNS (brain + VNC)"
    schema_variant: str         # "princeton" or "fafb"
    neuron_count: int           # Measured at load time
    connection_count: int       # Measured at load time
    has_classification_file: bool  # FAFB only
    has_cell_types_file: bool      # FAFB only
    connections_nt_type_populated: bool  # True only for FAFB
    id_format: str              # "uint64_flyire" (BANC/FAFB) or "int_body_id" (MANC/MAOL/MCNS)
    load_timestamp: str         # ISO 8601
```

---

## 8.6 Validation Report Object

```python
@dataclass
class ValidationReport:
    """
    Records all data quality checks performed at load time.
    """
    passed: bool                    # True if no errors found

    # Counts
    duplicate_neuron_ids: int       # Should be 0
    duplicate_connection_triplets: int  # Should be 0
    negative_syn_count_rows: int    # Should be 0
    missing_mandatory_columns: list[str]  # Should be empty

    # Referential integrity (optional — expensive check)
    pre_ids_missing_from_neurons: int   # Connection pre IDs not in neurons
    post_ids_missing_from_neurons: int  # Connection post IDs not in neurons
    referential_check_performed: bool   # False if check was skipped

    # Null rates for key columns (informational)
    null_rates: dict[str, float]    # {column_name: null_fraction}

    # Warnings
    warnings: list[str]             # Non-fatal issues
    errors: list[str]               # Fatal issues
```

---

## 8.7 Dataset Extras Object (FAFB Only)

```python
@dataclass
class DatasetExtras:
    """
    FAFB-specific extra data not normalized into the standard schema.
    Stored as-is for downstream use.
    """
    # NT probability breakdown per neuron (from FAFB neurons.csv)
    # These are already merged into neurons DataFrame; stored here as
    # a convenience reference for NT-focused analyses
    nt_probability_columns: list[str]  # ["da_avg", "ser_avg", "gaba_avg", "glut_avg", "ach_avg", "oct_avg"]
```

For non-FAFB datasets, `extras` is `None`.

---

## 8.8 Column Presence Contract

The `FlyWireDataset.neurons` DataFrame always contains all standard columns, regardless of dataset. Missing columns are represented by NaN-filled columns of the correct dtype. This guarantees that downstream analyses can reference `dataset.neurons["flow"]` without KeyError regardless of which dataset is loaded.

| Contract | Enforcement |
|----------|-------------|
| All canonical columns present | Loader must create NaN columns for missing fields |
| `root_id` is unique | Validated in ValidationReport |
| `syn_count` ≥ 1 | Validated in ValidationReport |
| `pre_root_id` in neurons | Optional check; reported in ValidationReport |
| Column dtypes match spec | Loader casts types explicitly after normalization |

---

## 8.9 Loader Return Type

```python
# Public API of core/data_loader.py

def load_dataset(
    dataset_path: Union[str, Path],
    config: DatasetConfig,
    chunk_size: Optional[int] = None,
    validate: bool = True,
    check_referential_integrity: bool = False,
) -> FlyWireDataset:
    """
    Load a FlyWire connectome dataset from research_data/raw/{DATASET_VERSION}/.

    Parameters
    ----------
    dataset_path : Path to the dataset directory (e.g., .../BANC_v888/)
    config       : DatasetConfig from configs/datasets/*.yaml
    chunk_size   : If set, connections are loaded in chunks (recommended for FAFB)
    validate     : If True, run syn_count validation and duplicate checks
    check_referential_integrity : If True, verify all connection IDs exist in neurons
                                  (expensive — disabled by default)

    Returns
    -------
    FlyWireDataset with all standard tables, metadata, and validation report.

    Raises
    ------
    DatasetLoadError : If mandatory files are missing or schema validation fails
    """
```
