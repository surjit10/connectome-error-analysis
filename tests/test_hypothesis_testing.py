"""
Integration and Unit Tests for Hypothesis Testing Subsystem
============================================================
Validates null-model generators, secondary effects extraction, statistical
comparison engine, and end-to-end hypothesis testing execution.
"""

import math
import pytest
import igraph
import pandas as pd
from pathlib import Path

from hypothesis_testing.config import HypothesisExperimentConfig, Condition
from hypothesis_testing.null_models.degree_preserving_rewriter import DirectedDegreeWeightPreservingNullModel
from hypothesis_testing.null_models.erdos_renyi import DirectedErdosRenyiNullModel
from hypothesis_testing.null_models.null_registry import registry as null_registry
from hypothesis_testing.analysis.secondary_effects import (
    SecondaryEffectsExtractor,
    classify_metric,
    MetricCategory,
)
from hypothesis_testing.comparison.metric_comparison import MetricComparator, cohens_d
from hypothesis_testing.comparison.hypothesis_tests import (
    HypothesisTestEngine,
    benjamini_hochberg_fdr,
)
from hypothesis_testing.runners.hypothesis_experiment_runner import HypothesisExperimentRunner


def _create_sample_graph() -> igraph.Graph:
    """Helper to build a small directed test graph with metadata."""
    g = igraph.Graph(directed=True)
    g.add_vertices(6)
    g.vs["root_id"] = [101, 102, 103, 104, 105, 106]
    g.vs["top_region"] = ["AL", "AL", "MB", "MB", "LH", "LH"]
    g.vs["soma_side"] = ["R", "R", "L", "L", "R", "L"]

    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (1, 3), (2, 4)]
    g.add_edges(edges)
    g.es["syn_count"] = [5, 10, 2, 8, 4, 12, 6, 7]
    g["dataset_name"] = "SAMPLE_TEST"
    g["id_to_idx"] = {rid: idx for idx, rid in enumerate(g.vs["root_id"])}
    g["id_map"] = {idx: rid for idx, rid in enumerate(g.vs["root_id"])}
    return g


def test_degree_preserving_null_model():
    """Verify directed degree-preserving null model retains degree sequence and weights."""
    g = _create_sample_graph()
    orig_in = g.indegree()
    orig_out = g.outdegree()
    orig_weights = sorted(g.es["syn_count"])

    model = DirectedDegreeWeightPreservingNullModel()
    null_g = model.generate(g, seed=42)

    assert null_g.vcount() == g.vcount()
    assert null_g.ecount() == g.ecount()
    assert null_g.indegree() == orig_in
    assert null_g.outdegree() == orig_out
    assert sorted(null_g.es["syn_count"]) == orig_weights
    assert null_g.vs["root_id"] == g.vs["root_id"]
    assert null_g.vs["top_region"] == g.vs["top_region"]


def test_erdos_renyi_null_model():
    """Verify Erdős–Rényi null model matches size and retains vertex attributes."""
    g = _create_sample_graph()
    model = DirectedErdosRenyiNullModel()
    null_g = model.generate(g, seed=42)

    assert null_g.vcount() == g.vcount()
    assert null_g.ecount() == g.ecount()
    assert null_g.vs["root_id"] == g.vs["root_id"]
    assert "syn_count" in null_g.edge_attributes()


def test_null_registry():
    """Verify null models are correctly catalogued in registry."""
    names = null_registry.list_names()
    assert "degree_preserving" in names
    assert "erdos_renyi" in names

    inst = null_registry.instantiate("degree_preserving")
    assert isinstance(inst, DirectedDegreeWeightPreservingNullModel)


def test_metric_classification():
    """Verify metric categorization rulebook."""
    assert classify_metric("missed_synapses", "metric_total_synapses") == MetricCategory.PRIMARY_IMPOSED
    assert classify_metric("missed_synapses", "metric_edge_count") == MetricCategory.SECONDARY_EMERGENT
    assert classify_metric("split_errors", "metric_node_count") == MetricCategory.PRIMARY_IMPOSED
    assert classify_metric("split_errors", "metric_wcc_max_size") == MetricCategory.SECONDARY_EMERGENT
    assert classify_metric("merge_errors", "metric_node_count") == MetricCategory.PRIMARY_IMPOSED
    assert classify_metric("merge_errors", "metric_edge_count") == MetricCategory.SECONDARY_EMERGENT


def test_fdr_correction():
    """Verify Benjamini-Hochberg FDR correction."""
    p_vals = [0.001, 0.01, 0.04, 0.20, 0.80]
    adj_p, sig = benjamini_hochberg_fdr(p_vals, alpha=0.05)

    assert len(adj_p) == 5
    assert adj_p[0] <= adj_p[1] <= adj_p[2]
    assert sig[0] is True
    assert sig[4] is False


def test_cohens_d():
    """Verify Cohen's d calculation."""
    d = cohens_d(10.0, 2.0, 10, 5.0, 2.0, 10)
    assert math.isclose(d, 2.5, rel_tol=1e-3)

    # Identical groups
    d_zero = cohens_d(5.0, 1.0, 10, 5.0, 1.0, 10)
    assert d_zero == 0.0


def test_end_to_end_hypothesis_pipeline(temp_configs, temp_dataset, tmp_path):
    """End-to-end validation of hypothesis testing runner on synthetic test dataset."""
    dataset_root, name = temp_dataset
    out_dir = tmp_path / "results" / "hypothesis_testing"

    runner = HypothesisExperimentRunner()

    config = HypothesisExperimentConfig(
        dataset_name=name,
        dataset_root=str(dataset_root),
        configs_root=str(temp_configs),
        run_real=True,
        run_null=True,
        null_model_name="degree_preserving",
        error_model_names=["synapse_count_measurement"],
        error_rates=[0.00, 0.05],
        random_seeds=[1, 2],
        analysis_names=["basic_structure"],
        output_root=str(out_dir),
    )

    result = runner.run(config)

    # 1. Check pipeline success
    assert result.status == "SUCCESS"
    assert len(result.errors) == 0

    # 2. Check secondary effect records
    assert len(result.secondary_records) > 0
    conditions = {r.condition for r in result.secondary_records}
    assert "real" in conditions
    assert "null" in conditions

    # 3. Check comparisons and test results
    assert len(result.comparison_results) > 0
    assert len(result.test_results) > 0

    # 4. Check exported files
    exp_paths = result.exported_paths
    assert "secondary_effect_summary" in exp_paths
    assert "hypothesis_test_results" in exp_paths
    assert "summary_markdown" in exp_paths

    assert exp_paths["secondary_effect_summary"].exists()
    assert exp_paths["hypothesis_test_results"].exists()
    assert exp_paths["summary_markdown"].exists()


def test_null_only_mode_execution_and_zero_real_runs(temp_configs, temp_dataset, tmp_path, monkeypatch):
    """Verify NULL_ONLY mode runs 0 Real experiments and exports replicate-level null observations."""
    dataset_root, name = temp_dataset
    out_dir = tmp_path / "results" / "hypothesis_testing_null_only"

    runner = HypothesisExperimentRunner()

    real_run_count = 0
    orig_run_condition = runner._run_condition

    def spied_run_condition(condition, *args, **kwargs):
        nonlocal real_run_count
        if condition == "real":
            real_run_count += 1
        return orig_run_condition(condition, *args, **kwargs)

    monkeypatch.setattr(runner, "_run_condition", spied_run_condition)

    config = HypothesisExperimentConfig(
        dataset_name=name,
        dataset_root=str(dataset_root),
        configs_root=str(temp_configs),
        execution_mode="null_only",
        null_model_name="degree_preserving",
        error_model_names=["synapse_count_measurement"],
        error_rates=[0.00, 0.05],
        random_seeds=[1, 2],
        analysis_names=["basic_structure"],
        output_root=str(out_dir),
    )

    result = runner.run(config)

    # 1. Assert Real condition was never executed
    assert real_run_count == 0, f"Expected 0 Real condition executions, got {real_run_count}"
    assert result.status == "SUCCESS"

    # 2. Assert Null records are present
    assert len(result.secondary_records) > 0
    assert all(r.condition == "null" for r in result.secondary_records)

    # 3. Assert replicate observations exported in null_observations/
    null_csv = out_dir / name / "null_observations" / "replicate_level_effects.csv"
    assert null_csv.exists(), f"Expected {null_csv} to exist"
    df = pd.read_csv(null_csv)
    assert len(df) == len(result.secondary_records)
    assert "trial_seed" in df.columns
    assert "null_graph_replicate_id" in df.columns
    assert "relative_change" in df.columns


def test_existing_real_results_loader_rejects_mean_only(tmp_path):
    """Verify loader rejects mean-only aggregated summaries and reports insufficient replicate data."""
    import pandas as pd
    from hypothesis_testing.loaders.existing_real_results_loader import ExistingRealResultsLoader

    mean_only_csv = tmp_path / "aggregated_means.csv"
    pd.DataFrame({
        "rate": [5.0],
        "metric": ["edge_count"],
        "baseline_mean": [3990039.0],
        "mean_preservation": [99.33],
    }).to_csv(mean_only_csv, index=False)

    loader = ExistingRealResultsLoader()
    with pytest.raises(ValueError, match="contains only pre-aggregated summary statistics"):
        loader.load(mean_only_csv)


def test_compare_existing_runner_execution(tmp_path):
    """Verify CompareExistingRunner matches replicate observations and runs independent Welch t-test & FDR."""
    import pandas as pd
    from hypothesis_testing.config import HypothesisExperimentConfig
    from hypothesis_testing.runners.compare_existing_runner import CompareExistingRunner

    out_dir = tmp_path / "results" / "compare_existing"

    # Create synthetic Real and Null replicate files
    real_csv = tmp_path / "real_effects.csv"
    pd.DataFrame([
        {
            "condition": "real", "dataset": "TEST", "error_model": "missed_synapses",
            "error_rate": 0.05, "trial_seed": 1, "analysis_name": "basic_structure",
            "metric_name": "reciprocity", "category": "secondary_emergent",
            "baseline_value": 0.18, "perturbed_value": 0.15462, "absolute_delta": -0.02538,
            "relative_change": -0.141, "is_near_zero_baseline": False,
        },
        {
            "condition": "real", "dataset": "TEST", "error_model": "missed_synapses",
            "error_rate": 0.05, "trial_seed": 2, "analysis_name": "basic_structure",
            "metric_name": "reciprocity", "category": "secondary_emergent",
            "baseline_value": 0.18, "perturbed_value": 0.15426, "absolute_delta": -0.02574,
            "relative_change": -0.143, "is_near_zero_baseline": False,
        },
        {
            "condition": "real", "dataset": "TEST", "error_model": "missed_synapses",
            "error_rate": 0.05, "trial_seed": 3, "analysis_name": "basic_structure",
            "metric_name": "reciprocity", "category": "secondary_emergent",
            "baseline_value": 0.18, "perturbed_value": 0.15444, "absolute_delta": -0.02556,
            "relative_change": -0.142, "is_near_zero_baseline": False,
        },
    ]).to_csv(real_csv, index=False)

    null_csv = tmp_path / "null_effects.csv"
    pd.DataFrame([
        {
            "condition": "null", "dataset": "TEST", "error_model": "missed_synapses",
            "error_rate": 0.05, "trial_seed": 1, "null_graph_replicate_id": 0,
            "analysis_name": "basic_structure", "metric_name": "reciprocity",
            "category": "secondary_emergent", "baseline_value": 0.02, "perturbed_value": 0.01966,
            "absolute_delta": -0.00034, "relative_change": -0.017, "is_near_zero_baseline": False,
        },
        {
            "condition": "null", "dataset": "TEST", "error_model": "missed_synapses",
            "error_rate": 0.05, "trial_seed": 2, "null_graph_replicate_id": 1,
            "analysis_name": "basic_structure", "metric_name": "reciprocity",
            "category": "secondary_emergent", "baseline_value": 0.02, "perturbed_value": 0.01962,
            "absolute_delta": -0.00038, "relative_change": -0.019, "is_near_zero_baseline": False,
        },
        {
            "condition": "null", "dataset": "TEST", "error_model": "missed_synapses",
            "error_rate": 0.05, "trial_seed": 3, "null_graph_replicate_id": 2,
            "analysis_name": "basic_structure", "metric_name": "reciprocity",
            "category": "secondary_emergent", "baseline_value": 0.02, "perturbed_value": 0.01964,
            "absolute_delta": -0.00036, "relative_change": -0.018, "is_near_zero_baseline": False,
        },
    ]).to_csv(null_csv, index=False)

    config = HypothesisExperimentConfig(
        dataset_name="TEST",
        dataset_root=str(tmp_path),
        execution_mode="compare_existing",
        real_results_path=str(real_csv),
        null_results_path=str(null_csv),
        output_root=str(out_dir),
    )

    runner = CompareExistingRunner()
    result = runner.run(config)

    assert result.status == "SUCCESS"
    assert len(result.comparison_results) == 1
    comp = result.comparison_results[0]
    assert comp.real_n == 3
    assert comp.null_n == 3
    assert comp.is_paired is False
    assert comp.test_name == "welch_t_test"
    assert math.isclose(comp.effect_difference, -0.124, abs_tol=1e-3)
    assert comp.p_value is not None and comp.p_value < 0.05

    assert len(result.test_results) == 1
    assert result.test_results[0].is_significant is True
    assert result.test_results[0].adjusted_p_value is not None


def test_own_condition_baselines_isolated(tmp_path):
    """Verify that multiple null graphs normalize strictly against their own 0% baseline."""
    extractor = SecondaryEffectsExtractor()

    # Null Graph 1: baseline = 100.0, perturbed = 80.0 -> -20%
    base_1 = {1: {"struct": {"metric_x": 100.0}}}
    pert_1 = {0.05: {1: {"struct": {"metric_x": 80.0}}}}
    recs_1 = extractor.extract_effects("null", "TEST", "EM1", base_1, pert_1, null_graph_replicate_id=0)

    # Null Graph 2: baseline = 200.0, perturbed = 160.0 -> -20%
    base_2 = {1: {"struct": {"metric_x": 200.0}}}
    pert_2 = {0.05: {1: {"struct": {"metric_x": 160.0}}}}
    recs_2 = extractor.extract_effects("null", "TEST", "EM1", base_2, pert_2, null_graph_replicate_id=1)

    assert math.isclose(recs_1[0].relative_change, -0.20, rel_tol=1e-3)
    assert math.isclose(recs_2[0].relative_change, -0.20, rel_tol=1e-3)
    assert recs_1[0].baseline_value == 100.0
    assert recs_2[0].baseline_value == 200.0


def test_existing_real_results_loader_on_historical_banc_results():

    """Verify ExistingRealResultsLoader correctly parses historical results/banc trial folders."""
    from hypothesis_testing.loaders.existing_real_results_loader import ExistingRealResultsLoader

    banc_path = Path("results/banc")
    if not banc_path.exists():
        pytest.skip("results/banc directory not present in environment")

    loader = ExistingRealResultsLoader()
    records = loader.load(
        source_path=banc_path,
        dataset_name="BANC",
        error_models=["missed_synapses", "split_errors"],
        error_rates=[0.05],
    )

    assert len(records) > 0
    seeds = {r.trial_seed for r in records}
    assert len(seeds) >= 3, f"Expected at least 3 seeds, got {seeds}"
    for r in records:
        assert r.condition == "real"
        assert r.dataset == "BANC"
        assert r.baseline_value is not None
        assert math.isfinite(r.relative_change)

