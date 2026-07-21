import pytest
from core.dataset_registry import DatasetRegistry, DatasetInfo, DatasetRegistryError

def test_dataset_registry_loading(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    reg = DatasetRegistry(temp_configs, dataset_root)
    
    assert "TEST" in reg.list_names()
    assert reg.is_registered("TEST")
    
    info = reg.lookup("TEST")
    assert isinstance(info, DatasetInfo)
    assert info.name == "TEST"
    assert info.dataset_dir is not None
    assert str(dataset_root) in str(info.dataset_dir)
    assert not info.is_fafb
    
def test_missing_dataset(temp_configs):
    reg = DatasetRegistry(temp_configs, "/tmp")
    
    with pytest.raises(DatasetRegistryError, match="not registered"):
        reg.lookup("NON_EXISTENT")
        
def test_folder_resolution(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    reg = DatasetRegistry(temp_configs, dataset_root)
    info = reg.lookup(name)
    assert info.dataset_dir.name == "TEST_v1"
