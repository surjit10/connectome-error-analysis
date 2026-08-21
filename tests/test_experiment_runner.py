import pytest
from core.experiment_runner import ExperimentRunner, ExperimentConfig, ExperimentStatus
from modules.graph_analyses.analysis_registry import AnalysisRegistry
from modules.error_models.common.error_registry import ErrorRegistry
from tests.dummy_modules.dummy_error_model import DummyErrorModel
from tests.dummy_modules.dummy_analysis import DummyAnalysis

def test_experiment_runner(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    
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
        analysis_names=[DummyAnalysis.NAME]
    )
    
    result = runner.run(config)
    
    assert result.succeeded
    assert result.dataset_name == "TEST"
    assert result.error_result is not None
    assert result.error_result.model_name == DummyErrorModel.NAME
    assert len(result.analysis_results) == 1
    assert result.analysis_results[0].analysis_name == DummyAnalysis.NAME
    assert result.analysis_results[0].metrics["nodes"] == 3
    assert result.analysis_results[0].metrics["edges"] == 3


def test_experiment_runner_raises_on_error_model_failure(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    
    a_reg = AnalysisRegistry()
    a_reg.register(DummyAnalysis)
    
    class FailingErrorModel(DummyErrorModel):
        NAME = "failing_model"
        def _perturb(self, prepared, config, result, rng):
            raise ValueError("Deliberate failure in error model")
            
    e_reg = ErrorRegistry()
    e_reg.register(FailingErrorModel)
    
    runner = ExperimentRunner(a_reg, e_reg)
    
    config = ExperimentConfig(
        dataset_name=name,
        dataset_root=str(dataset_root),
        configs_root=str(temp_configs),
        error_model_name=FailingErrorModel.NAME,
        analysis_names=[DummyAnalysis.NAME]
    )
    
    result = runner.run(config)
    assert not result.succeeded
    assert result.status == ExperimentStatus.FAILED
    assert any("Execution aborted to prevent generating invalid baseline-fallback" in err for err in result.errors)
    assert len(result.analysis_results) == 0

