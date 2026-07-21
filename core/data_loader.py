"""
Phase 004 – Data Loader
=======================
Loads FlyWire connectome datasets from gzip-compressed CSV files into memory
and returns a standardised :class:`FlyWireDataset` container.

Backend: Polars (replaces pandas).  Polars is used throughout for its
columnar memory layout, zero-copy slicing, and lazy evaluation support.

Design constraints:
    - Preserves all column names and data types exactly as in source CSVs.
    - Preserves all FlyWire biological identifiers (root_id, pre_root_id,
      post_root_id) without downcasting or remapping.
    - No scientific calculations are performed here.
    - No graph construction logic belongs here.
"""

import polars as pl
from pathlib import Path
from dataclasses import dataclass
from typing import Union


@dataclass
class FlyWireDataset:
    """Standardised representation of one loaded FlyWire connectome dataset."""
    name: str
    neurons: pl.DataFrame
    connections: pl.DataFrame


# ---------------------------------------------------------------------------
# Column-name normalisation maps
# ---------------------------------------------------------------------------

PRINCETON_MAPPING: dict = {
    "Root ID": "root_id",
    "Top in/out region": "top_region",
    "Community labels": "community_labels",
    "Predicted NT type": "predicted_nt_type",
    "Predicted NT confidence": "predicted_nt_confidence",
    "Verified NT type": "verified_nt_type",
    "Verified Neuropeptide": "verified_neuropeptide",
    "Body Part": "body_part",
    "Function": "function",
    "Flow": "flow",
    "Super Class": "super_class",
    "Class": "class_",
    "Sub Class": "sub_class",
    "Hemilineage": "hemilineage",
    "Nerve": "nerve",
    "Soma side": "soma_side",
    "Primary Cell Type": "primary_cell_type",
    "Alternative Cell Type(s)": "alternative_cell_types",
    "Cable length (nm)": "cable_length_nm",
    "Surface area (nm^2)": "surface_area_nm2",
    "Volume (nm^3)": "volume_nm3",
}

FAFB_MAPPING: dict = {
    "group": "top_region",
    "nt_type": "predicted_nt_type",
    "nt_type_score": "predicted_nt_confidence",
    "side": "soma_side",
    "primary_type": "primary_cell_type",
    "additional_type(s)": "alternative_cell_types",
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _locate_dataset_folder(dataset_name: str, dataset_root: Path) -> Path:
    """Find the specific dataset directory matching the dataset name."""
    for folder in dataset_root.iterdir():
        if folder.is_dir() and folder.name.startswith(f"{dataset_name}_"):
            return folder
    raise FileNotFoundError(
        f"Dataset folder for {dataset_name} not found in {dataset_root}"
    )


def _load_csv(filepath: Path) -> pl.DataFrame:
    """Load a gzip-compressed CSV file into a Polars DataFrame.

    Polars reads gzip natively; column types are inferred by the engine.
    Biological IDs (root_id, pre_root_id, post_root_id) are left at their
    inferred type — typically Int64.  They are never downcast.
    """
    return pl.read_csv(filepath, infer_schema_length=10_000)


def _load_fafb_neurons(dataset_dir: Path) -> pl.DataFrame:
    """Load and join the FAFB-specific neuron and classification files."""
    neurons = _load_csv(dataset_dir / "neurons.csv.gz")
    classification = _load_csv(dataset_dir / "classification.csv.gz")
    cell_types = _load_csv(dataset_dir / "consolidated_cell_types.csv.gz")

    df = neurons.join(classification, on="root_id", how="left")
    df = df.join(cell_types, on="root_id", how="left")
    return df


def _normalize_columns(df: pl.DataFrame, is_fafb: bool) -> pl.DataFrame:
    """Rename columns to the canonical schema format using Polars rename."""
    mapping = FAFB_MAPPING if is_fafb else PRINCETON_MAPPING
    # Only rename columns that exist in the dataframe.
    existing_renames = {k: v for k, v in mapping.items() if k in df.columns}
    if existing_renames:
        df = df.rename(existing_renames)
    return df


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def load_dataset(
    dataset_name: str,
    dataset_root: Union[str, Path],
) -> FlyWireDataset:
    """Load a FlyWire dataset into memory and return a standardised dataset object.

    Args:
        dataset_name: Name of the dataset (e.g., 'MANC', 'FAFB').
        dataset_root: Root directory containing dataset folders.

    Returns:
        FlyWireDataset: A standardised dataset object backed by Polars DataFrames.
    """
    root_path = Path(dataset_root)
    dataset_dir = _locate_dataset_folder(dataset_name, root_path)

    is_fafb = dataset_name.upper() == "FAFB"

    # Load neurons
    if is_fafb:
        neurons_df = _load_fafb_neurons(dataset_dir)
    else:
        neurons_df = _load_csv(dataset_dir / "neurons.csv.gz")

    neurons_df = _normalize_columns(neurons_df, is_fafb)

    # Load connections
    connections_df = _load_csv(dataset_dir / "connections_princeton.csv.gz")

    return FlyWireDataset(
        name=dataset_name.upper(),
        neurons=neurons_df,
        connections=connections_df,
    )
