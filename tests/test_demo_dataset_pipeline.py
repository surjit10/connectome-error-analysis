import pytest
import shutil
import os
from pathlib import Path

from core.experiment_runner import ExperimentRunner, ExperimentConfig
from modules.error_models.common.error_registry import registry as error_registry
from modules.graph_analyses.analysis_registry import registry as analysis_registry
from modules.statistical_evaluation import StatisticalEvaluator
from core.export_manager import ExportManager

def test_complete_demo_pipeline(tmp_path):
    """
    Validates the complete execution pipeline (Phase 001-018) locally using the TEST_v1 dataset.
    This guarantees every framework component remains stable across experiments.
    """
    ds_name = "TEST"
    err_model = "missed_synapses"
    err_rate = 0.10
    seed = 42
    
    output_base = tmp_path / "results"
    trial_base = output_base / ds_name / err_model / "10_percent" / "trial_001"
    baseline_trial = output_base / ds_name / err_model / "0_percent" / "trial_001"
    
    biology_config = {
        "weights": {
            "synapse_weight": 1.0,
            "source_degree_weight": 1.0,
            "target_degree_weight": 1.0
        }
    }
    
    baseline_config = ExperimentConfig(
        dataset_name=ds_name,
        dataset_root="0-demodata",
        error_model_name=err_model,
        error_model_config={"error_rate": 0.0, "biology": biology_config},
        analysis_names=["basic_structure", "degree_distribution"],
        preprocessing_config={"features": {"degree": True, "synapse_counts": True}},
        seed=seed,
        output_root=str(baseline_trial),
        create_zip=False,
        extra={"metadata": {"experiment_name": "Test Validation"}}
    )

    perturbed_config = ExperimentConfig(
        dataset_name=ds_name,
        dataset_root="0-demodata",
        error_model_name=err_model,
        error_model_config={"error_rate": err_rate, "biology": biology_config},
        analysis_names=["basic_structure", "degree_distribution"],
        preprocessing_config={"features": {"degree": True, "synapse_counts": True}},
        seed=seed,
        output_root=str(trial_base),
        create_zip=True,
        extra={"metadata": {"experiment_name": "Test Validation"}}
    )
    
    # Run Phase 001-016
    runner = ExperimentRunner(analysis_registry, error_registry)
    
    res_base = runner.run(baseline_config)
    assert res_base.succeeded, f"Baseline failed: {res_base.errors}"
    
    res_pert = runner.run(perturbed_config)
    assert res_pert.succeeded, f"Perturbed failed: {res_pert.errors}"
    
    # Run Phase 017
    evaluator = StatisticalEvaluator()
    eval_result = evaluator.evaluate([res_base], [res_pert])
    assert eval_result is not None
    assert eval_result.dataset_name == "TEST"
    
    aggregated = {0.10: eval_result}
    
    # Run Phase 018
    ExportManager().export_presentation(
        results_by_rate=aggregated,
        output_root=output_base,
        metadata={"experiment_name": "Test Validation"}
    )
    
    # Assertions for ExportManager
    assert any(trial_base.glob("*/metadata.json"))
    assert any(trial_base.glob("*/summary.csv"))
    
    # Assertions for Phase 018 Presentation Layer
    pres_dir = output_base / "presentation"
    assert (pres_dir / "dashboard_data.json").exists()
    assert (pres_dir / "global_statistics.csv").exists()
    assert (pres_dir / "plots" / "effect_size_vs_error_rate.png").exists()
    
    # Assertion for Final ZIP Archive
    assert (output_base.parent / "Test_Validation_complete.zip").exists()
