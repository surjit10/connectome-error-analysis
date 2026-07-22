"""
Local Demo Runner
=================
End-to-end smoke test for the Connectome Error Analysis framework using the
small synthetic **TEST** dataset in ``0-demodata/``.

Pipeline executed
-----------------
1. **Baseline** (0 % error)  — run the full analysis pipeline with no perturbation.
2. **Perturbed** (10 % error) — re-run after applying the *missed_synapses* error model.
3. **Statistical evaluation**  — compare baseline vs. perturbed metric distributions.
4. **Export** — serialise results to ``results/TEST/missed_synapses/``.

Usage::

    python run_demo.py

Output will be written to the ``results/`` directory (ignored by git).
"""

from pathlib import Path
from core.experiment_runner import ExperimentRunner, ExperimentConfig
from modules.error_models.error_registry import registry as error_registry
from modules.graph_analyses.analysis_registry import registry as analysis_registry
from modules.statistical_evaluation import StatisticalEvaluator
from core.export_manager import ExportManager
import warnings

warnings.filterwarnings("ignore")


def run_demo():
    ds_name = "TEST"
    err_model = "missed_synapses"
    
    # 0% Error (Baseline)
    baseline_config = ExperimentConfig(
        dataset_name=ds_name,
        dataset_root="0-demodata",
        error_model_name=err_model,
        error_model_config={
            "error_rate": 0.0, 
            "biology": {"weights": {"synapse_weight": 1.0, "source_degree_weight": 1.0, "target_degree_weight": 1.0}}
        },
        analysis_names=["basic_structure", "degree_distribution", "pagerank", "centrality", "connected_components", "reciprocity"],
        preprocessing_config={"features": {"degree": True, "synapse_counts": True}},
        seed=42,
        output_root=str(Path("results") / ds_name / err_model / "0_percent" / "trial_001"),
        create_zip=False,
        extra={"metadata": {"experiment_name": "Demo Baseline"}}
    )

    # 10% Error (Perturbed)
    perturbed_config = ExperimentConfig(
        dataset_name=ds_name,
        dataset_root="0-demodata",
        error_model_name=err_model,
        error_model_config={
            "error_rate": 0.10, 
            "biology": {"weights": {"synapse_weight": 1.0, "source_degree_weight": 1.0, "target_degree_weight": 1.0}}
        },
        analysis_names=["basic_structure", "degree_distribution", "pagerank", "centrality", "connected_components", "reciprocity"],
        preprocessing_config={"features": {"degree": True, "synapse_counts": True}},
        seed=42,
        output_root=str(Path("results") / ds_name / err_model / "10_percent" / "trial_001"),
        create_zip=True,
        extra={"metadata": {"experiment_name": "Demo Perturbed"}}
    )
    
    runner = ExperimentRunner(analysis_registry, error_registry)
    
    print("Running Baseline (0% error)...")
    res_base = runner.run(baseline_config)
    
    print("Running Perturbation (10% error)...")
    res_pert = runner.run(perturbed_config)
    
    print("Running Statistical Evaluation...")
    evaluator = StatisticalEvaluator()
    eval_result = evaluator.evaluate([res_base], [res_pert])
    
    print("Exporting Presentation Layer...")
    ExportManager().export_presentation(
        results_by_rate={0.10: eval_result},
        output_root=Path("results/TEST/missed_synapses"),
        metadata={"experiment_name": "Demo Experiment"}
    )
    print("Done! Check the 'results/' directory.")

if __name__ == "__main__":
    run_demo()
