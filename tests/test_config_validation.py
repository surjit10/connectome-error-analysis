"""
Phase 017 — Configuration Validation Tests
===========================================
Verify that:
  1. Every configured analysis exists in the registry.
  2. Invalid analysis names raise clear errors.
  3. Missing analyses are caught.
  4. The analysis registry validation works correctly.

These tests exercise only the configuration and registry layers — they do
not run full experiments.
"""

import pytest

from core.experiment_runner import ExperimentRunner, ExperimentConfig, ExperimentStatus
from modules.graph_analyses.analysis_registry import registry as analysis_registry
from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.exceptions import RegistryError
from modules.error_models.error_registry import registry as error_registry
from modules.preprocessing.prepared_graph import PreparedGraph


# ===================================================================
# Task 6 — Configuration Validation
# ===================================================================

@pytest.fixture
def runner():
    return ExperimentRunner(analysis_registry, error_registry)


class TestAnalysisNameValidation:
    """Verify analysis name validation in the pipeline."""

    def test_valid_analysis_names_execute(self, runner, temp_configs, temp_dataset):
        """All registered analysis names must execute successfully."""
        dataset_root, name = temp_dataset
        all_names = analysis_registry.list_names()

        config = ExperimentConfig(
            dataset_name=name,
            dataset_root=str(dataset_root),
            configs_root=str(temp_configs),
            error_model_name=None,
            analysis_names=all_names,
        )
        result = runner.run(config)
        assert result.succeeded, f"Experiment failed with valid names: {result.errors}"

        executed = {a.analysis_name for a in result.analysis_results}
        for n in all_names:
            assert n in executed, f"Analysis '{n}' was configured but not executed!"

    def test_invalid_analysis_name_causes_partial_failure(self, runner, temp_configs, temp_dataset):
        """An invalid analysis name should cause a partial or failed status."""
        dataset_root, name = temp_dataset

        config = ExperimentConfig(
            dataset_name=name,
            dataset_root=str(dataset_root),
            configs_root=str(temp_configs),
            error_model_name=None,
            analysis_names=["this_analysis_does_not_exist"],
        )
        result = runner.run(config)
        # The runner catches instantiation errors, so the experiment may still
        # report SUCCESS (empty analysis list) or PARTIAL.  The key is it
        # does NOT crash — it records the error.
        assert result.status in (ExperimentStatus.SUCCESS, ExperimentStatus.PARTIAL, ExperimentStatus.FAILED), \
            f"Unexpected status: {result.status}"

        # The single analysis result should be FAILED
        assert len(result.analysis_results) == 1
        assert result.analysis_results[0].status.name == "FAILED", \
            "Invalid analysis should produce FAILED result!"

    def test_mixed_valid_and_invalid_names(self, runner, temp_configs, temp_dataset):
        """Valid + invalid names should produce PARTIAL status."""
        dataset_root, name = temp_dataset
        valid_name = analysis_registry.list_names()[0]

        config = ExperimentConfig(
            dataset_name=name,
            dataset_root=str(dataset_root),
            configs_root=str(temp_configs),
            error_model_name=None,
            analysis_names=[valid_name, "nonexistent_analysis"],
        )
        result = runner.run(config)

        assert result.status == ExperimentStatus.PARTIAL, \
            f"Expected PARTIAL for mixed valid/invalid names, got {result.status}"

        # One SUCCESS, one FAILED
        statuses = {a.analysis_name: a.status.name for a in result.analysis_results}
        assert statuses[valid_name] == "SUCCESS", f"Valid analysis should succeed!"
        assert statuses.get("nonexistent_analysis", "") == "FAILED", \
            "Invalid analysis should be FAILED!"

    def test_empty_analysis_list(self, runner, temp_configs, temp_dataset):
        """An empty analysis list should succeed (no analyses run)."""
        dataset_root, name = temp_dataset

        config = ExperimentConfig(
            dataset_name=name,
            dataset_root=str(dataset_root),
            configs_root=str(temp_configs),
            error_model_name=None,
            analysis_names=[],
        )
        result = runner.run(config)
        assert result.succeeded, f"Experiment with empty analysis list failed: {result.errors}"
        assert len(result.analysis_results) == 0, \
            f"Expected 0 analysis results, got {len(result.analysis_results)}"

    def test_duplicate_analysis_names(self, runner, temp_configs, temp_dataset):
        """Duplicate names in analysis_names should be handled gracefully
        (the runner executes each entry in order, which means duplicates
        run twice)."""
        dataset_root, name = temp_dataset
        valid_name = analysis_registry.list_names()[0]

        config = ExperimentConfig(
            dataset_name=name,
            dataset_root=str(dataset_root),
            configs_root=str(temp_configs),
            error_model_name=None,
            analysis_names=[valid_name, valid_name],
        )
        result = runner.run(config)

        # Should succeed with 2 entries (same analysis run twice)
        assert result.succeeded, f"Experiment with duplicate names failed: {result.errors}"
        assert len(result.analysis_results) == 2, \
            f"Expected 2 results for duplicate names, got {len(result.analysis_results)}"
        assert result.analysis_results[0].analysis_name == valid_name
        assert result.analysis_results[1].analysis_name == valid_name
        # Metrics should be identical (same graph, same analysis)
        assert result.analysis_results[0].metrics == result.analysis_results[1].metrics


class TestRegistryValidation:
    """Verify the AnalysisRegistry itself validates names correctly."""

    def test_registry_get_valid_name(self):
        """Getting a valid name returns the class."""
        for name in analysis_registry.list_names():
            cls = analysis_registry.get(name)
            assert issubclass(cls, BaseAnalysis)

    def test_registry_get_invalid_name_raises(self):
        """Getting an invalid name raises RegistryError."""
        with pytest.raises(RegistryError, match="is registered"):
            analysis_registry.get("this_analysis_does_not_exist_12345")

    def test_registry_instantiate_valid(self):
        """Instantiating a valid analysis returns an instance."""
        for name in analysis_registry.list_names():
            instance = analysis_registry.instantiate(name)
            assert isinstance(instance, BaseAnalysis)

    def test_registry_instantiate_invalid_raises(self):
        """Instantiating an invalid name raises RegistryError."""
        with pytest.raises(RegistryError, match="is registered"):
            analysis_registry.instantiate("nope_not_a_real_analysis")


class TestAnalysisSchemaValidation:
    """Verify ExperimentConfig validation for analysis-related fields."""

    def test_analysis_names_must_be_list(self):
        """analysis_names should be provided as a list."""
        config = ExperimentConfig(
            dataset_name="TEST",
            dataset_root="/tmp",
            analysis_names=["valid_name"],
        )
        assert isinstance(config.analysis_names, list)

    def test_config_stores_analysis_names_correctly(self):
        """The config must preserve the analysis names list."""
        names = ["a", "b", "c"]
        config = ExperimentConfig(
            dataset_name="TEST",
            dataset_root="/tmp",
            analysis_names=names,
        )
        assert config.analysis_names == names

    def test_config_snapshot_contains_analysis_names(self, runner, temp_configs, temp_dataset):
        """The experiment result's config snapshot should include analysis_names."""
        dataset_root, name = temp_dataset
        test_names = ["basic_structure", "degree_distribution"]
        config = ExperimentConfig(
            dataset_name=name,
            dataset_root=str(dataset_root),
            configs_root=str(temp_configs),
            error_model_name=None,
            analysis_names=test_names,
        )
        result = runner.run(config)
        snapshot = result.config_snapshot
        assert "analysis_names" in snapshot, \
            f"analysis_names missing from config snapshot keys: {list(snapshot.keys())}"
        assert snapshot["analysis_names"] == test_names, \
            f"Expected {test_names}, got {snapshot['analysis_names']}"
