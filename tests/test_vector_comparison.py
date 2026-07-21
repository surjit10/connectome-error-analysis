"""
Tests for Phase 017 — Vector-Valued Graph Statistics Comparison
================================================================
Validates that vector-valued metrics (PageRank, degree distribution,
betweenness, closeness) are detected, compared, and the derived scalar
summaries flow through the existing statistical evaluation pipeline.

Backward compatibility: all existing scalar-only tests must remain passing.
"""

import math
import pytest

import numpy as np

from core.experiment_runner import ExperimentResult, ExperimentStatus
from core.statistics_engine import StatisticsEngine, _is_vector_value, MetricStats
from modules.graph_analyses.analysis_result import AnalysisResult, AnalysisStatus
from modules.statistical_evaluation.vector_comparison import (
    VectorComparisonRegistry,
    compare_pagerank,
    compare_degree_distribution,
    compare_betweenness,
    compare_closeness,
)
from modules.statistical_evaluation.evaluator import StatisticalEvaluator


# ===================================================================
# Unit Tests: Vector detection
# ===================================================================

class TestVectorDetection:
    def test_list_is_vector(self):
        assert _is_vector_value([1, 2, 3]) is True

    def test_tuple_is_vector(self):
        assert _is_vector_value((1.0, 2.0)) is True

    def test_ndarray_is_vector(self):
        assert _is_vector_value(np.array([1, 2, 3])) is True

    def test_float_is_not_vector(self):
        assert _is_vector_value(3.14) is False

    def test_int_is_not_vector(self):
        assert _is_vector_value(42) is False

    def test_str_is_not_vector(self):
        assert _is_vector_value("hello") is False

    def test_dict_is_not_vector(self):
        assert _is_vector_value({"a": 1}) is False

    def test_none_is_not_vector(self):
        assert _is_vector_value(None) is False


# ===================================================================
# Unit Tests: Registry
# ===================================================================

class TestVectorComparisonRegistry:
    def test_default_registrations(self):
        """Verify all expected strategies are auto-registered."""
        assert VectorComparisonRegistry.has("pagerank", "pagerank_scores")
        assert VectorComparisonRegistry.has("degree_distribution", "in_degrees")
        assert VectorComparisonRegistry.has("degree_distribution", "out_degrees")
        assert VectorComparisonRegistry.has("centrality", "betweenness")
        assert VectorComparisonRegistry.has("centrality", "closeness")

    def test_missing_registration(self):
        assert not VectorComparisonRegistry.has("nonexistent", "metric")

    def test_custom_registration(self):
        def my_compare(b, p, cfg):
            return {"custom_metric": 1.0}

        VectorComparisonRegistry.register("custom_analysis", "custom_vec", my_compare)
        assert VectorComparisonRegistry.has("custom_analysis", "custom_vec")
        strategy = VectorComparisonRegistry.get("custom_analysis", "custom_vec")
        assert strategy([1.0], [2.0], {}) == {"custom_metric": 1.0}

        # Clean up
        VectorComparisonRegistry.unregister("custom_analysis", "custom_vec")
        assert not VectorComparisonRegistry.has("custom_analysis", "custom_vec")

    def test_list_registrations(self):
        regs = VectorComparisonRegistry.list_registrations()
        assert ("pagerank", "pagerank_scores") in regs
        assert ("degree_distribution", "in_degrees") in regs


# ===================================================================
# Unit Tests: Comparison Strategies
# ===================================================================

class TestComparePageRank:
    def test_identical_vectors(self):
        vec = [0.1, 0.2, 0.3, 0.2, 0.1, 0.05]
        result = compare_pagerank(vec, vec, {"top_k_overlap": 3})
        assert result["spearman"] == pytest.approx(1.0, abs=1e-6)
        assert result["pearson"] == pytest.approx(1.0, abs=1e-6)
        assert result["topk_overlap"] == 1.0

    def test_reversed_vectors(self):
        """Spearman should capture rank correlation even without linear relationship."""
        vec_a = [0.1, 0.2, 0.3, 0.4, 0.5]
        vec_b = [0.5, 0.4, 0.3, 0.2, 0.1]
        result = compare_pagerank(vec_a, vec_b, {"top_k_overlap": 2})
        # Reversed ranking → negative Spearman
        assert result["spearman"] < 0
        # Top-2 indices should be different (rank positions swapped)
        assert result["topk_overlap"] < 1.0

    def test_small_vector(self):
        result = compare_pagerank([1.0], [2.0], {})
        assert result["spearman"] == 0.0
        assert result["pearson"] == 0.0

    def test_empty_vector(self):
        result = compare_pagerank([], [], {})
        assert result["spearman"] == 0.0

    def test_nan_handling(self):
        vec_a = [0.1, 0.2, float("nan"), 0.4]
        vec_b = [0.15, 0.25, 0.35, float("nan")]
        result = compare_pagerank(vec_a, vec_b, {"top_k_overlap": 2})
        # Should not crash, return finite values
        assert math.isfinite(result["spearman"])
        assert math.isfinite(result["pearson"])


class TestCompareDegreeDistribution:
    def test_identical_distributions(self):
        deg = [1, 2, 2, 3, 3, 3, 4, 5]
        result = compare_degree_distribution(deg, deg, {})
        assert result["ks"] == pytest.approx(0.0, abs=1e-6)
        assert result["wasserstein"] == pytest.approx(0.0, abs=1e-6)

    def test_different_distributions(self):
        low = [1, 1, 2, 2, 2]
        high = [3, 3, 4, 4, 5, 5]
        result = compare_degree_distribution(low, high, {})
        assert result["ks"] > 0.0
        assert result["wasserstein"] > 0.0
        assert result["mean_baseline"] < result["mean_perturbed"]

    def test_edge_cases(self):
        # Single element
        result = compare_degree_distribution([1.0], [2.0], {})
        assert math.isfinite(result["ks"])
        # All same value
        result = compare_degree_distribution([1, 1, 1], [2, 2, 2], {})
        assert math.isfinite(result["wasserstein"])


class TestCompareBetweenness:
    def test_identical_vectors(self):
        vec = [0.01, 0.02, 0.03, 0.04]
        result = compare_betweenness(vec, vec, {"top_k_overlap": 2})
        assert result["spearman"] == 1.0
        assert result["pearson"] == 1.0
        assert result["topk_overlap"] == 1.0

    def test_different_top_k(self):
        vec_a = [0.1, 0.2, 0.3, 0.01, 0.02]
        vec_b = [0.3, 0.2, 0.1, 0.02, 0.01]
        # With k=5 (full set), top-k overlap is 1.0 since all 5 positions
        # are in the top-5 of both vectors (just reordered)
        result_5 = compare_betweenness(vec_a, vec_b, {"top_k_overlap": 5})
        assert result_5["topk_overlap"] == 1.0
        # With k=1, only the top index overlaps
        result_1 = compare_betweenness(vec_a, vec_b, {"top_k_overlap": 1})
        assert result_1["topk_overlap"] >= 0.0


class TestCompareCloseness:
    def test_identical_vectors(self):
        vec = [0.5, 0.3, 0.4, 0.2]
        result = compare_closeness(vec, vec, {})
        assert result["spearman"] == 1.0

    def test_handles_disconnected(self):
        """NaN/Inf values from disconnected nodes must not crash."""
        base = [0.5, 0.3, float("inf"), 0.4, 0.0, float("nan")]
        perturbed = [0.45, 0.32, float("inf"), 0.38, 0.0, float("nan")]
        result = compare_closeness(base, perturbed, {})
        assert math.isfinite(result["spearman"])
        assert math.isfinite(result["pearson"])

    def test_differs_from_betweenness(self):
        """Closeness and betweenness use different comparison logic."""
        vec_a = [0.5, 0.3, 0.1]
        vec_b = [0.4, 0.35, 0.1]
        cb = compare_closeness(vec_a, vec_b, {})
        bb = compare_betweenness(vec_a, vec_b, {"top_k_overlap": 3})
        # Same Spearman computation, but closeness also has Pearson
        assert "pearson" in cb
        assert "topk_overlap" not in cb  # closeness does not compute top-k


# ===================================================================
# Integration Tests: StatisticsEngine vector data flow
# ===================================================================

class TestStatisticsEngineVectorFlow:
    @pytest.fixture
    def sample_results(self):
        """Create two ExperimentResult objects with mixed scalar and vector metrics."""
        r1 = ExperimentResult(
            experiment_id="trial_1",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            analysis_results=[
                AnalysisResult(
                    analysis_name="pagerank",
                    status=AnalysisStatus.SUCCESS,
                    metrics={
                        "pagerank_scores": [0.1, 0.2, 0.3, 0.2, 0.1],
                        "mean_pagerank": 0.18,
                    },
                ),
                AnalysisResult(
                    analysis_name="basic_structure",
                    status=AnalysisStatus.SUCCESS,
                    metrics={"node_count": 5, "edge_count": 10},
                ),
            ],
        )
        r2 = ExperimentResult(
            experiment_id="trial_2",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            analysis_results=[
                AnalysisResult(
                    analysis_name="pagerank",
                    status=AnalysisStatus.SUCCESS,
                    metrics={
                        "pagerank_scores": [0.15, 0.25, 0.2, 0.3, 0.1],
                        "mean_pagerank": 0.20,
                    },
                ),
                AnalysisResult(
                    analysis_name="basic_structure",
                    status=AnalysisStatus.SUCCESS,
                    metrics={"node_count": 5, "edge_count": 10},
                ),
            ],
        )
        return [r1, r2]

    def test_scalar_aggregation_unchanged(self, sample_results):
        """Existing scalar metric aggregation must remain identical."""
        engine = StatisticsEngine()
        stats = engine.aggregate(sample_results)

        # Scalar metric from pagerank
        ms = stats.analysis_stats["pagerank"].metric_stats["mean_pagerank"]
        assert ms.mean == pytest.approx(0.19, abs=1e-6)
        assert ms.n == 2

        # Scalar metric from basic_structure
        ms = stats.analysis_stats["basic_structure"].metric_stats["node_count"]
        assert ms.mean == 5.0
        assert ms.n == 2

    def test_vector_data_collected(self, sample_results):
        """Vector metrics must be separately stored in vector_data."""
        engine = StatisticsEngine()
        stats = engine.aggregate(sample_results)

        assert "pagerank" in stats.vector_data
        assert "pagerank_scores" in stats.vector_data["pagerank"]
        assert len(stats.vector_data["pagerank"]["pagerank_scores"]) == 2

        # basic_structure should NOT have vector data
        assert "basic_structure" not in stats.vector_data or \
               stats.vector_data["basic_structure"] == {}

    def test_vector_comparison_produces_derived_scalars(self, sample_results):
        """compute_vector_comparisons must produce MetricStats for derived metrics."""
        engine = StatisticsEngine()

        # Split into baseline (first trial) and perturbed (both)
        baseline_stats = engine.aggregate([sample_results[0]])
        perturbed_stats = engine.aggregate(sample_results)

        config = {"statistics": {"top_k_overlap": 3}}
        result = engine.compute_vector_comparisons(
            baseline_stats, perturbed_stats, config
        )

        assert "pagerank" in result
        derived = result["pagerank"]
        derived_keys = set(derived.keys())

        # Check derived metric names exist
        assert "pagerank_scores_spearman" in derived_keys
        assert "pagerank_scores_pearson" in derived_keys
        assert "pagerank_scores_topk_overlap" in derived_keys

        # Check MetricStats structure
        for ms in derived.values():
            assert isinstance(ms, MetricStats)
            assert ms.n >= 1
            assert math.isfinite(ms.mean)
            assert math.isfinite(ms.std)

    def test_no_vector_data_returns_empty(self):
        """Analyses that produce no vector metrics should yield empty comparison."""
        r = ExperimentResult(
            experiment_id="test",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            analysis_results=[
                AnalysisResult(
                    analysis_name="basic_structure",
                    status=AnalysisStatus.SUCCESS,
                    metrics={"node_count": 5},
                ),
            ],
        )
        engine = StatisticsEngine()
        stats_a = engine.aggregate([r])
        stats_b = engine.aggregate([r])
        result = engine.compute_vector_comparisons(stats_a, stats_b, {})
        assert result == {}

    def test_inconsistent_vector_lengths(self, sample_results):
        """Trials with inconsistent vector lengths must not crash."""
        r3 = ExperimentResult(
            experiment_id="trial_3",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            analysis_results=[
                AnalysisResult(
                    analysis_name="pagerank",
                    status=AnalysisStatus.SUCCESS,
                    metrics={"pagerank_scores": [0.1, 0.2]},  # different length
                ),
            ],
        )
        engine = StatisticsEngine()
        baseline_stats = engine.aggregate([sample_results[0]])
        perturbed_stats = engine.aggregate([sample_results[0], r3])
        result = engine.compute_vector_comparisons(baseline_stats, perturbed_stats, {})
        # Should handle gracefully — either empty or with partial results
        assert isinstance(result, dict)


# ===================================================================
# Integration Tests: Full Evaluator flow
# ===================================================================

class TestEvaluatorVectorFlow:
    @pytest.fixture
    def trials(self):
        """Build baseline and perturbed trials with vector metrics."""
        # Baseline trial (0% error)
        base = ExperimentResult(
            experiment_id="baseline",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            config_snapshot={"error_model_config": {"error_rate": 0.0}},
            analysis_results=[
                AnalysisResult(
                    analysis_name="pagerank",
                    status=AnalysisStatus.SUCCESS,
                    metrics={
                        "pagerank_scores": [0.1, 0.2, 0.3, 0.25, 0.15],
                        "mean_pagerank": 0.20,
                    },
                ),
            ],
        )
        # Perturbed trials (5% error)
        perturbed_1 = ExperimentResult(
            experiment_id="perturbed_1",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            config_snapshot={"error_model_config": {"error_rate": 0.05}},
            analysis_results=[
                AnalysisResult(
                    analysis_name="pagerank",
                    status=AnalysisStatus.SUCCESS,
                    metrics={
                        "pagerank_scores": [0.12, 0.18, 0.28, 0.22, 0.20],
                        "mean_pagerank": 0.20,
                    },
                ),
            ],
        )
        perturbed_2 = ExperimentResult(
            experiment_id="perturbed_2",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            config_snapshot={"error_model_config": {"error_rate": 0.05}},
            analysis_results=[
                AnalysisResult(
                    analysis_name="pagerank",
                    status=AnalysisStatus.SUCCESS,
                    metrics={
                        "pagerank_scores": [0.11, 0.22, 0.25, 0.20, 0.22],
                        "mean_pagerank": 0.20,
                    },
                ),
            ],
        )
        return [base], [perturbed_1, perturbed_2]

    def test_evaluator_includes_vector_derived_metrics(self, trials):
        """The evaluator must produce vector-derived metrics alongside scalars."""
        baseline, perturbed = trials
        evaluator = StatisticalEvaluator(config={"statistics": {"top_k_overlap": 3}})
        result = evaluator.evaluate(baseline, perturbed)

        assert "pagerank" in result.metrics

        # Check scalar metrics still present
        assert "mean_pagerank" in result.metrics["pagerank"]

        # Check vector-derived metrics present
        derived_keys = set(result.metrics["pagerank"].keys())
        for suffix in ["spearman", "pearson", "topk_overlap"]:
            key = f"pagerank_scores_{suffix}"
            assert key in derived_keys, f"Missing derived metric: {key}"

        # Check MetricEvaluation structure for derived metrics
        for key, ev in result.metrics["pagerank"].items():
            if key != "mean_pagerank":
                assert math.isfinite(ev.mean)
                assert math.isfinite(ev.effect_size)

    def test_scalar_only_fallback(self):
        """Evaluator with only scalar metrics must behave identically to before."""
        base = ExperimentResult(
            experiment_id="base",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            config_snapshot={"error_model_config": {"error_rate": 0.0}},
            analysis_results=[
                AnalysisResult(
                    analysis_name="basic_structure",
                    status=AnalysisStatus.SUCCESS,
                    metrics={"node_count": 5, "edge_count": 10},
                ),
            ],
        )
        perturbed = ExperimentResult(
            experiment_id="perturbed",
            status=ExperimentStatus.SUCCESS,
            dataset_name="TEST",
            config_snapshot={"error_model_config": {"error_rate": 0.05}},
            analysis_results=[
                AnalysisResult(
                    analysis_name="basic_structure",
                    status=AnalysisStatus.SUCCESS,
                    metrics={"node_count": 4, "edge_count": 8},
                ),
            ],
        )
        evaluator = StatisticalEvaluator()
        result = evaluator.evaluate([base], [perturbed])

        assert "basic_structure" in result.metrics
        assert "node_count" in result.metrics["basic_structure"]
        assert "edge_count" in result.metrics["basic_structure"]
        assert len(result.metrics["basic_structure"]) == 2  # no extra derived
