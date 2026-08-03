from core.config_manager import ConfigManager
from core.experiment_runner import ExperimentRunner
from core.statistics_engine import StatisticsEngine
from core.export_manager import ExportManager
import sys
from pathlib import Path

# Run Missed Synapses on a small config to verify presentation
cm = ConfigManager(Path("configs"))
runner = ExperimentRunner()
engine = StatisticsEngine()
exporter = ExportManager()

print("Running pipeline...")
# Actually, the user's task was only to "Re-run the Missed Synapses experiment and verify that...".
# Let's find the correct runner script.
