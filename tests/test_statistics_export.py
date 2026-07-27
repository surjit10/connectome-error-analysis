import pytest
from core.experiment_runner import ExperimentRunner, ExperimentConfig
from modules.graph_analyses.analysis_registry import AnalysisRegistry
from modules.error_models.common.error_registry import ErrorRegistry
from tests.dummy_modules.dummy_error_model import DummyErrorModel
from tests.dummy_modules.dummy_analysis import DummyAnalysis

def test_statistics_and_export(temp_configs, temp_dataset, tmp_path):
    dataset_root, name = temp_dataset
    out_dir = tmp_path / "results"
    
    a_reg = AnalysisRegistry()
    a_reg.register(DummyAnalysis)
    e_reg = ErrorRegistry()
    
    runner = ExperimentRunner(a_reg, e_reg)
    
    config = ExperimentConfig(
        dataset_name=name,
        dataset_root=str(dataset_root),
        configs_root=str(temp_configs),
        analysis_names=[DummyAnalysis.NAME],
        output_root=str(out_dir),
        create_zip=False
    )
    
    result = runner.run(config)
    assert result.succeeded
    
    # Check that output files were created by ExportManager
    exp_dir = list(out_dir.glob("TEST_*"))[0]
    
    assert (exp_dir / "metadata.json").exists()
    assert (exp_dir / "summary.csv").exists()
    assert (exp_dir / "trial_results.csv").exists()
    assert (exp_dir / "config_snapshot.yaml").exists()
