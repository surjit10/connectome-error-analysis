"""
Phase 004 – Data Loader
========================
Loads FlyWire connectome datasets from gzip-compressed CSV files into memory
and returns a standardised :class:`FlyWireDataset` container.

Backend: Polars (replaces pandas).  Polars is used throughout for its
columnar memory layout, zero-copy slicing, and lazy evaluation support.

Design constraints:
    - Dataset path resolution is delegated to the
      :class:`~core.dataset_registry.DatasetRegistry`.
    - Biological ID columns (root_id, pre_root_id, post_root_id) are
      preserved exactly as loaded — never downcast or remapped.
    - No scientific calculations.
    - No graph construction.
    - Schema validation is performed after loading; errors are reported
      rather than silently ignored.

Public API::

    from core.data_loader import load_dataset, load_dataset_from_info

    dataset = load_dataset("FAFB", "/data/raw")        # convenience wrapper
    dataset = load_dataset_from_info(registry_info)    # registry-aware path
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import polars as pl

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataset container
# ---------------------------------------------------------------------------

@dataclass
class FlyWireDataset:
    """Standardised representation of one loaded FlyWire connectome dataset.

    Attributes:
        name:        Canonical dataset name (e.g. ``"FAFB"``).
        neurons:     Polars DataFrame with one row per neuron.
        connections: Polars DataFrame with one row per directed synapse.
    """

    name: str
    neurons: pl.DataFrame
    connections: pl.DataFrame


# ---------------------------------------------------------------------------
# Column-name normalisation maps
# (Kept here because they describe the canonical schema used throughout the
#  framework — they are not biological parameters; they are structural
#  transformations of the CSV headers.)
# ---------------------------------------------------------------------------

PRINCETON_MAPPING: dict = {
    "Root ID":                   "root_id",
    "Top in/out region":         "top_region",
    "Community labels":          "community_labels",
    "Predicted NT type":         "predicted_nt_type",
    "Predicted NT confidence":   "predicted_nt_confidence",
    "Verified NT type":          "verified_nt_type",
    "Verified Neuropeptide":     "verified_neuropeptide",
    "Body Part":                 "body_part",
    "Function":                  "function",
    "Flow":                      "flow",
    "Super Class":               "super_class",
    "Class":                     "class_",
    "Sub Class":                 "sub_class",
    "Hemilineage":               "hemilineage",
    "Nerve":                     "nerve",
    "Soma side":                 "soma_side",
    "Primary Cell Type":         "primary_cell_type",
    "Alternative Cell Type(s)":  "alternative_cell_types",
    "Cable length (nm)":         "cable_length_nm",
    "Surface area (nm^2)":       "surface_area_nm2",
    "Volume (nm^3)":             "volume_nm3",
}

FAFB_MAPPING: dict = {
    "group":                     "top_region",
    "nt_type":                   "predicted_nt_type",
    "nt_type_score":             "predicted_nt_confidence",
    "side":                      "soma_side",
    "primary_type":              "primary_cell_type",
    "additional_type(s)":        "alternative_cell_types",
}


# ---------------------------------------------------------------------------
# Data-loading errors
# ---------------------------------------------------------------------------

class DataLoaderError(Exception):
    """Raised when a dataset cannot be loaded or fails schema validation."""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_csv(filepath: Path) -> pl.DataFrame:
    """Load a (possibly gzip-compressed) CSV file into a Polars DataFrame.

    Polars reads gzip natively.  Column types are inferred by the engine.
    Biological ID columns are left at their inferred type (Int64) and are
    never downcast.
    """
    if not filepath.exists():
        raise DataLoaderError(f"File not found: {filepath}")
    try:
        return pl.read_csv(filepath, infer_schema_length=10_000)
    except Exception as exc:
        raise DataLoaderError(
            f"Failed to read '{filepath}': {exc}"
        ) from exc


def _load_fafb_neurons(dataset_dir: Path) -> pl.DataFrame:
    """Load and join the FAFB-specific neuron and classification files."""
    neurons = _load_csv(dataset_dir / "neurons.csv.gz")
    classification = _load_csv(dataset_dir / "classification.csv.gz")
    cell_types = _load_csv(dataset_dir / "consolidated_cell_types.csv.gz")

    df = neurons.join(classification, on="root_id", how="left")
    df = df.join(cell_types, on="root_id", how="left")
    return df


def _normalize_columns(df: pl.DataFrame, is_fafb: bool) -> pl.DataFrame:
    """Rename columns to the canonical schema using Polars rename.

    Only renames columns that actually exist in *df*; ignores the rest.
    """
    mapping = FAFB_MAPPING if is_fafb else PRINCETON_MAPPING
    existing_renames = {k: v for k, v in mapping.items() if k in df.columns}
    if existing_renames:
        df = df.rename(existing_renames)
    return df


def _validate_columns(
    df: pl.DataFrame,
    required: List[str],
    table_label: str,
    dataset_name: str,
) -> None:
    """Raise :class:`DataLoaderError` if any *required* columns are absent.

    Args:
        df:           The DataFrame to validate.
        required:     List of column names that must be present.
        table_label:  Human-readable label (``"neurons"`` or ``"connections"``).
        dataset_name: Used in the error message.
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataLoaderError(
            f"Dataset '{dataset_name}' {table_label} table is missing "
            f"required columns: {missing}. "
            f"Available columns: {df.columns}"
        )


# ---------------------------------------------------------------------------
# Public entry-points
# ---------------------------------------------------------------------------

def load_dataset_from_info(info: "DatasetInfo") -> FlyWireDataset:  # type: ignore[name-defined]  # noqa: F821
    """Load a dataset using a pre-resolved :class:`~core.dataset_registry.DatasetInfo`.

    This is the preferred entry-point when the Experiment Runner already holds
    a :class:`~core.dataset_registry.DatasetRegistry` instance.

    Args:
        info: A :class:`~core.dataset_registry.DatasetInfo` with
              ``dataset_dir`` already resolved.

    Returns:
        A :class:`FlyWireDataset` backed by Polars DataFrames.

    Raises:
        DataLoaderError: If the dataset directory or files are missing, or
                         if schema validation fails.
    """
    if info.dataset_dir is None:
        raise DataLoaderError(
            f"DatasetInfo for '{info.name}' has no resolved dataset_dir. "
            "Provide a dataset_root when constructing the DatasetRegistry."
        )

    dataset_dir: Path = info.dataset_dir
    name: str = info.name

    logger.info(
        "[DataLoader] Loading dataset '%s' from '%s'.", name, dataset_dir
    )

    # ── Load neurons ─────────────────────────────────────────────────────
    if info.is_fafb:
        neurons_df = _load_fafb_neurons(dataset_dir)
    else:
        neurons_file = dataset_dir / info.files.get("neurons", "neurons.csv.gz")
        neurons_df = _load_csv(neurons_file)

    neurons_df = _normalize_columns(neurons_df, is_fafb=info.is_fafb)

    # ── Load connections ──────────────────────────────────────────────────
    connections_file = dataset_dir / info.files.get(
        "connections", "connections_princeton.csv.gz"
    )
    connections_df = _load_csv(connections_file)

    # ── Schema validation ─────────────────────────────────────────────────
    if info.required_neuron_columns:
        _validate_columns(
            neurons_df, info.required_neuron_columns, "neurons", name
        )
    if info.required_connection_columns:
        _validate_columns(
            connections_df, info.required_connection_columns, "connections", name
        )

    logger.info(
        "[DataLoader] Loaded '%s': %d neurons, %d connections.",
        name, len(neurons_df), len(connections_df),
    )

    return FlyWireDataset(
        name=name,
        neurons=neurons_df,
        connections=connections_df,
    )


def load_dataset(
    dataset_name: str,
    dataset_root: Union[str, Path],
    *,
    configs_root: Union[str, Path] = "configs/",
) -> FlyWireDataset:
    """Convenience wrapper: build a registry on-the-fly and load *dataset_name*.

    This entry-point is used by the Experiment Runner when no pre-built
    registry is available.

    Args:
        dataset_name: Case-insensitive dataset name (e.g. ``"FAFB"``).
        dataset_root: Root directory containing per-dataset folders.
        configs_root: Path to the ``configs/`` directory used for registry
                      initialisation.  Defaults to ``"configs/"``.

    Returns:
        A :class:`FlyWireDataset` backed by Polars DataFrames.

    Raises:
        DataLoaderError: On any loading or validation failure.
    """
    from core.dataset_registry import DatasetRegistry, DatasetRegistryError

    try:
        registry = DatasetRegistry(
            configs_root=configs_root,
            dataset_root=dataset_root,
        )
        info = registry.lookup(dataset_name)
    except DatasetRegistryError as exc:
        # Fall back to legacy path resolution when the registry has no config
        # for this dataset (e.g. a dataset added without a YAML yet).
        logger.warning(
            "[DataLoader] Registry lookup failed for '%s': %s. "
            "Falling back to legacy path resolution.",
            dataset_name, exc,
        )
        info = _legacy_resolve(dataset_name, dataset_root)

    return load_dataset_from_info(info)


# ---------------------------------------------------------------------------
# Legacy path-resolution fallback
# ---------------------------------------------------------------------------

def _legacy_resolve(
    dataset_name: str,
    dataset_root: Union[str, Path],
) -> "DatasetInfo":  # type: ignore[name-defined]  # noqa: F821
    """Replicate the original ``_locate_dataset_folder`` logic as a fallback.

    Used when the registry has no YAML for the requested dataset.
    Returns a minimal :class:`~core.dataset_registry.DatasetInfo`.
    """
    from core.dataset_registry import DatasetInfo, DatasetRegistryError

    root = Path(dataset_root)
    name_upper = dataset_name.upper()

    dataset_dir: Optional[Path] = None
    for folder in root.iterdir():
        if folder.is_dir() and folder.name.upper().startswith(f"{name_upper}_"):
            dataset_dir = folder
            break

    if dataset_dir is None:
        raise DataLoaderError(
            f"Dataset folder for '{dataset_name}' not found in '{root}'."
        )

    is_fafb = name_upper == "FAFB"
    return DatasetInfo(
        name=name_upper,
        dataset_dir=dataset_dir,
        is_fafb=is_fafb,
        files={
            "neurons": "neurons.csv.gz",
            "connections": "connections_princeton.csv.gz",
            "classification": "classification.csv.gz",
            "cell_types": "consolidated_cell_types.csv.gz",
        },
        required_neuron_columns=["root_id"],
        required_connection_columns=["pre_root_id", "post_root_id"],
    )
