import pytest
from core.data_loader import load_dataset, load_dataset_from_info, FlyWireDataset, DataLoaderError
from core.dataset_registry import DatasetRegistry
import polars as pl

def test_data_loader(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    
    # Load using convenience method
    dataset = load_dataset(name, dataset_root, configs_root=temp_configs)
    
    assert isinstance(dataset, FlyWireDataset)
    assert isinstance(dataset.neurons, pl.DataFrame)
    assert isinstance(dataset.connections, pl.DataFrame)
    
    assert len(dataset.neurons) == 3
    assert len(dataset.connections) == 3
    
    # Check columns
    assert "root_id" in dataset.neurons.columns
    assert "pre_root_id" in dataset.connections.columns
    assert "post_root_id" in dataset.connections.columns

def test_data_loader_missing_columns(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    reg = DatasetRegistry(temp_configs, dataset_root)
    info = reg.lookup(name)
    
    # Manually corrupt schema requirements to force error
    info.required_neuron_columns = ["missing_column"]
    
    with pytest.raises(DataLoaderError, match="missing required columns"):
        load_dataset_from_info(info)
