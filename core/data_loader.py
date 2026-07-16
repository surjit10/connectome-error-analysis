import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import Union

@dataclass
class FlyWireDataset:
    """Standardized representation of one loaded FlyWire connectome dataset."""
    name: str
    neurons: pd.DataFrame
    connections: pd.DataFrame

PRINCETON_MAPPING = {
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
    "Volume (nm^3)": "volume_nm3"
}

FAFB_MAPPING = {
    "group": "top_region",
    "nt_type": "predicted_nt_type",
    "nt_type_score": "predicted_nt_confidence",
    "side": "soma_side",
    "primary_type": "primary_cell_type",
    "additional_type(s)": "alternative_cell_types"
}

def _locate_dataset_folder(dataset_name: str, dataset_root: Path) -> Path:
    """Find the specific dataset directory matching the dataset name."""
    for folder in dataset_root.iterdir():
        if folder.is_dir() and folder.name.startswith(f"{dataset_name}_"):
            return folder
    raise FileNotFoundError(f"Dataset folder for {dataset_name} not found in {dataset_root}")

def _load_csv(filepath: Path) -> pd.DataFrame:
    """Load a gzip-compressed CSV file into a pandas DataFrame."""
    return pd.read_csv(filepath, compression="gzip")

def _load_fafb_neurons(dataset_dir: Path) -> pd.DataFrame:
    """Load and join the FAFB-specific neuron and classification files."""
    neurons = _load_csv(dataset_dir / "neurons.csv.gz")
    classification = _load_csv(dataset_dir / "classification.csv.gz")
    cell_types = _load_csv(dataset_dir / "consolidated_cell_types.csv.gz")

    df = neurons.merge(classification, on="root_id", how="left")
    df = df.merge(cell_types, on="root_id", how="left")
    return df

def _normalize_columns(df: pd.DataFrame, is_fafb: bool) -> pd.DataFrame:
    """Rename columns to the canonical schema format."""
    mapping = FAFB_MAPPING if is_fafb else PRINCETON_MAPPING
    return df.rename(columns=mapping)

def load_dataset(dataset_name: str, dataset_root: Union[str, Path]) -> FlyWireDataset:
    """
    Load a FlyWire dataset into memory and return a standardized dataset object.
    
    Args:
        dataset_name: Name of the dataset (e.g., 'MANC', 'FAFB')
        dataset_root: Root directory containing dataset folders
        
    Returns:
        FlyWireDataset: A standardized dataset object
    """
    root_path = Path(dataset_root)
    dataset_dir = _locate_dataset_folder(dataset_name, root_path)
    
    is_fafb = dataset_name.upper() == "FAFB"
    
    # Load Neurons
    if is_fafb:
        neurons_df = _load_fafb_neurons(dataset_dir)
    else:
        neurons_df = _load_csv(dataset_dir / "neurons.csv.gz")
        
    neurons_df = _normalize_columns(neurons_df, is_fafb)
    
    # Load Connections
    connections_df = _load_csv(dataset_dir / "connections_princeton.csv.gz")
    
    return FlyWireDataset(
        name=dataset_name.upper(),
        neurons=neurons_df,
        connections=connections_df
    )
