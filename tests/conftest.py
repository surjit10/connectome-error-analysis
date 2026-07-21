import pytest
import os
import gzip
from pathlib import Path
import yaml

@pytest.fixture
def temp_dataset(tmp_path):
    """Creates a small synthetic dataset in a temp directory."""
    dataset_root = tmp_path / "data"
    dataset_dir = dataset_root / "TEST_v1"
    dataset_dir.mkdir(parents=True)
    
    # Create nodes.csv.gz
    nodes_csv = "root_id,super_class,top_region\n1,neuron,AL\n2,neuron,MB\n3,neuron,AL\n"
    with gzip.open(dataset_dir / "neurons.csv.gz", "wt") as f:
        f.write(nodes_csv)
        
    # Create edges.csv.gz
    edges_csv = "pre_root_id,post_root_id,syn_count\n1,2,5\n2,3,10\n1,3,2\n"
    with gzip.open(dataset_dir / "connections_princeton.csv.gz", "wt") as f:
        f.write(edges_csv)
        
    return dataset_root, "TEST"

@pytest.fixture
def temp_configs(tmp_path):
    """Creates a temporary configs structure."""
    configs_root = tmp_path / "configs"
    
    (configs_root / "schemas").mkdir(parents=True)
    (configs_root / "datasets").mkdir(parents=True)
    (configs_root / "error_models").mkdir(parents=True)
    (configs_root / "analyses").mkdir(parents=True)
    (configs_root / "experiments").mkdir(parents=True)
    
    # Defaults
    defaults = {
        "framework": {"version": "1.0.0"},
        "loader": {"id_columns": ["root_id", "pre_root_id", "post_root_id"]},
        "preprocessing": {"features": {"indegree": True, "outdegree": True, "pagerank": True}},
        "runner": {"auto_export": False},
        "statistics": {"confidence_level": 0.95}
    }
    with open(configs_root / "defaults.yaml", "w") as f:
        yaml.dump(defaults, f)
        
    # Schemas
    exp_schema = {"required_keys": ["dataset_name", "dataset_root"]}
    with open(configs_root / "schemas" / "experiment_schema.yaml", "w") as f:
        yaml.dump(exp_schema, f)
        
    dataset_schema = {"required_keys": ["name", "files"]}
    with open(configs_root / "schemas" / "dataset_schema.yaml", "w") as f:
        yaml.dump(dataset_schema, f)
        
    # Dataset config
    dataset_cfg = {
        "name": "TEST",
        "version": "1",
        "is_fafb": False,
        "files": {"neurons": "neurons.csv.gz", "connections": "connections_princeton.csv.gz"},
        "required_neuron_columns": ["root_id"],
        "required_connection_columns": ["pre_root_id", "post_root_id"]
    }
    with open(configs_root / "datasets" / "test.yaml", "w") as f:
        yaml.dump(dataset_cfg, f)
        
    return configs_root
