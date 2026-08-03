from pathlib import Path
from core.config_manager import ConfigManager
from core.experiment_runner import ExperimentRunner
from core.statistics_engine import StatisticsEngine
from core.export_manager import ExportManager
from modules.statistical_evaluation.evaluator import StatisticalEvaluator

cm = ConfigManager(Path("configs"))
runner = ExperimentRunner()
stats_engine = StatisticsEngine()
export_manager = ExportManager()

dataset_name = "BANC"
dataset_root = Path("dataset/error-1")

configs = cm.get_error_model_suite("missed_synapses", dataset_name, dataset_root)
configs = sorted(configs, key=lambda c: c.error_model_config.get("error_rate", 0))

print(f"Running Missed Synapses on {dataset_name} for {len(configs)} configs...")
results = []
for config in configs:
    result = runner.run(config)
    results.append(result)
    print(f"  Ran config with error rate {config.error_model_config.get('error_rate')}: status={result.status.value}")

stats = stats_engine.aggregate(results)
print(f"Aggregation complete: {stats.n_succeeded} succeeded")

output_root = Path("results_patched/BANC/missed_synapses")
pkg = export_manager.export(results[0], cm.collect_metadata(results[0]), stats, output_root)
print(f"Exported to {pkg.output_dir}")

# Evaluate and export presentation
evaluator = StatisticalEvaluator(output_root)
results_by_rate = evaluator.evaluate_all_rates(
    baseline_dir=output_root,  # Would need proper dir matching, simpler to just run the actual pipeline script if it exists
    metrics_to_evaluate=["total_synapses", "weight_mean", "weight_variance"]
)
