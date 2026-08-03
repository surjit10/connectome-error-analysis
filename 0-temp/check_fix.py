from pathlib import Path
from core.config_manager import ConfigManager
import yaml

with open("configs/experiments/missed_synapses.yaml", "r") as f:
    config_data = yaml.safe_load(f)
    print(config_data.get("experiment_id", "No experiment_id"))
