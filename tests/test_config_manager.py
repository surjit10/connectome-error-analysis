import pytest
from core.config_manager import ConfigManager, FrozenConfig, ConfigError
import yaml

def test_config_manager_loading(temp_configs):
    cm = ConfigManager(temp_configs)
    
    # Create dummy experiment config
    exp_cfg = temp_configs / "experiments" / "test_exp.yaml"
    with open(exp_cfg, "w") as f:
        yaml.dump({"dataset_name": "TEST", "dataset_root": "/tmp"}, f)
        
    cfg = cm.load_experiment(exp_cfg)
    
    # Test merge order and defaults
    assert cfg.framework["version"] == "1.0.0"
    assert cfg.dataset_name == "TEST"
    assert cfg.dataset_root == "/tmp"
    assert cfg.is_fafb is False  # from dataset config
    
def test_frozen_config_immutable():
    cfg = FrozenConfig({"key": "value"})
    assert cfg.key == "value"
    
    with pytest.raises(TypeError):
        cfg.key = "new_value"

def test_missing_required_schema(temp_configs):
    cm = ConfigManager(temp_configs)
    
    exp_cfg = temp_configs / "experiments" / "invalid.yaml"
    with open(exp_cfg, "w") as f:
        yaml.dump({"dataset_name": "TEST"}, f) # Missing dataset_root
        
    with pytest.raises(ConfigError, match="missing required keys"):
        cm.load_experiment(exp_cfg)
