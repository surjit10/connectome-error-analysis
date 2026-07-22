import pytest
from core.experiment_runner import ExperimentRunner, ExperimentConfig
from modules.graph_analyses.analysis_registry import AnalysisRegistry
from modules.error_models.error_registry import ErrorRegistry
from tests.dummy_modules.dummy_error_model import DummyErrorModel
from tests.dummy_modules.dummy_analysis import DummyAnalysis
from pathlib import Path
import shutil

def test_full_pipeline(temp_configs, temp_dataset, tmp_path):
    """
    End-to-end integration test.
    Validates: Config -> Loader -> Graph -> Preprocessing -> Runner -> Stats -> Export
    """
    dataset_root, name = temp_dataset
    out_dir = tmp_path / "results"
    
    a_reg = AnalysisRegistry()
    a_reg.register(DummyAnalysis)
    
    e_reg = ErrorRegistry()
    e_reg.register(DummyErrorModel)
    
    runner = ExperimentRunner(a_reg, e_reg)
    
    config = ExperimentConfig(
        dataset_name=name,
        dataset_root=str(dataset_root),
        configs_root=str(temp_configs),
        error_model_name=DummyErrorModel.NAME,
        baseline_analysis_names=[DummyAnalysis.NAME],
        analysis_names=[DummyAnalysis.NAME],
        output_root=str(out_dir),
        create_zip=True,
        preprocessing_config={
            "features": {
                "indegree": True,
                "pagerank": True
            }
        }
    )
    
    result = runner.run(config)
    
    # 1. Pipeline success
    assert result.succeeded
    
    # 2. Graph checks (via analysis results — PreparedGraph is released
    #    after export for memory management)
    assert len(result.analysis_results) == 1
    assert result.analysis_results[0].metrics.get("nodes") == 3
    assert result.analysis_results[0].metrics.get("edges") == 3
    
    # 3. Error model checks
    assert result.error_result is not None
    assert result.error_result.model_name == DummyErrorModel.NAME
    
    # 4. Baseline analysis checks
    assert len(result.baseline_analysis_results) == 1
    
    # 5. Additional analysis checks
    assert result.analysis_results[0].succeeded
    
    # 6. Export checks
    assert out_dir.exists()
    zips = list(out_dir.glob("*.zip"))
    assert len(zips) == 1
    
    # Clean up (usually handled by pytest tmp_path, but explicitly doing it for verification)
    shutil.rmtree(out_dir)
    assert not out_dir.exists()
