"""
Phase 010 – Statistics Engine
==============================
Computes descriptive statistics over a collection of
:class:`~core.experiment_runner.ExperimentResult` objects.

Responsibilities:
    - Aggregate ``AnalysisResult.metrics`` across repeated trials.
    - Compute mean, variance, standard deviation, and confidence intervals
      for every numeric metric.
    - Summarise perturbation metadata from ``ErrorResult``.
    - Detect and store **vector-valued** metrics for downstream scientific
      comparison (Phase 017 extension).
    - Return plain Python dicts so downstream (Export Manager) needs no
      statistical knowledge.

Constraints:
    - Consumes only ``ExperimentResult`` objects. Never reruns experiments.
    - Never modifies any result object.
    - Existing scalar pathway is completely unchanged.
"""

from __future__ import annotations

import copy
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.experiment_runner import ExperimentResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)

def _variance(values: Sequence[float], mean: float) -> float:
    return sum((v - mean) ** 2 for v in values) / len(values)

def _std(variance: float) -> float:
    return math.sqrt(variance)

def _confidence_interval(
    mean: float, std: float, n: int, z: float = 1.96
) -> tuple[float, float]:
    """Return a (lower, upper) 95 % CI using the Normal approximation."""
    if n <= 1:
        return (mean, mean)
    margin = z * std / math.sqrt(n)
    return (mean - margin, mean + margin)


# ---------------------------------------------------------------------------
# Vector data type detection
# ---------------------------------------------------------------------------

# Supported vector types.
_VECTOR_TYPES = (list, tuple)

try:
    import numpy as np
    _VECTOR_TYPES = (list, tuple, np.ndarray)
except ImportError:
    pass


def _is_vector_value(val: Any) -> bool:
    """Return ``True`` if *val* is a vector type we can compare.

    Supported: ``list[int|float]``, ``tuple``, ``numpy.ndarray``.
    """
    return isinstance(val, _VECTOR_TYPES)


def _ensure_flat_float_list(val: Any) -> List[float]:
    """Convert a vector value to a flat ``list[float]``.

    Handles ``list``, ``tuple``, and ``numpy.ndarray``.
    NaN / Inf entries are preserved (callers may filter as needed).
    """
    if isinstance(val, (list, tuple)):
        return [float(v) for v in val]
    try:
        import numpy as np
        if isinstance(val, np.ndarray):
            return val.flatten().astype(float).tolist()
    except ImportError:
        pass
    return []


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class MetricStats:
    """Descriptive statistics for a single numeric metric across trials.

    Attributes:
        metric_name: Name of the metric (e.g. ``"mean_degree"``).
        n:           Number of observations.
        mean:        Arithmetic mean.
        variance:    Population variance.
        std:         Standard deviation.
        min:         Minimum value.
        max:         Maximum value.
        ci_lower:    Lower bound of 95 % confidence interval.
        ci_upper:    Upper bound of 95 % confidence interval.
        raw:         Original observed values.
    """
    metric_name: str
    n: int = 0
    mean: float = 0.0
    variance: float = 0.0
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    raw: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "n":           self.n,
            "mean":        self.mean,
            "variance":    self.variance,
            "std":         self.std,
            "min":         self.min,
            "max":         self.max,
            "ci_lower":    self.ci_lower,
            "ci_upper":    self.ci_upper,
        }


@dataclass
class AnalysisStats:
    """Aggregated statistics for one analysis across all trials.

    Attributes:
        analysis_name:   Name of the analysis.
        n_trials:        Number of trials that succeeded.
        n_failed:        Number of trials that failed.
        metric_stats:    Dict mapping metric name → :class:`MetricStats`.
        mean_runtime:    Mean wall-clock runtime across successful trials.
        total_warnings:  Total warning count across all trials.
    """
    analysis_name: str
    n_trials: int = 0
    n_failed: int = 0
    metric_stats: Dict[str, MetricStats] = field(default_factory=dict)
    mean_runtime: float = 0.0
    total_warnings: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_name":  self.analysis_name,
            "n_trials":       self.n_trials,
            "n_failed":       self.n_failed,
            "mean_runtime":   self.mean_runtime,
            "total_warnings": self.total_warnings,
            "metric_stats":   {k: v.to_dict() for k, v in self.metric_stats.items()},
        }


@dataclass
class ExperimentStatistics:
    """Top-level statistics for a batch of experiment results.

    Attributes:
        n_experiments:        Total number of experiments processed.
        n_succeeded:          Number that completed with SUCCESS status.
        n_partial:            Number with PARTIAL status.
        n_failed:             Number that FAILED.
        mean_runtime:         Mean total runtime across all experiments.
        analysis_stats:       Per-analysis aggregated statistics.
        perturbation_summary: Aggregated perturbation metadata.
        vector_data:
            Raw vector values keyed by
            ``{analysis_name: {metric_key: [vector_per_trial, ...]}}``.
            Only populated for metrics whose values are lists/tuples/ndarrays.
            Used by :meth:`StatisticsEngine.compute_vector_comparisons`.
    """
    n_experiments: int = 0
    n_succeeded: int = 0
    n_partial: int = 0
    n_failed: int = 0
    mean_runtime: float = 0.0
    analysis_stats: Dict[str, AnalysisStats] = field(default_factory=dict)
    perturbation_summary: Dict[str, Any] = field(default_factory=dict)
    vector_data: Dict[str, Dict[str, List[Any]]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_experiments":       self.n_experiments,
            "n_succeeded":         self.n_succeeded,
            "n_partial":           self.n_partial,
            "n_failed":            self.n_failed,
            "mean_runtime":        self.mean_runtime,
            "analysis_stats":      {k: v.to_dict() for k, v in self.analysis_stats.items()},
            "perturbation_summary": self.perturbation_summary,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class StatisticsEngine:
    """Computes descriptive statistics over experiment results.

    Accepts one or more :class:`~core.experiment_runner.ExperimentResult`
    objects and aggregates their analysis metrics.

    Example::

        engine = StatisticsEngine()
        stats  = engine.aggregate([result_1, result_2, result_3])
        print(stats.to_dict())
    """

    def aggregate(
        self,
        results: List[ExperimentResult],
    ) -> ExperimentStatistics:
        """Aggregate *results* into an :class:`ExperimentStatistics` object.

        Args:
            results: One or more completed experiment results.

        Returns:
            An :class:`ExperimentStatistics` with per-analysis metric stats
            and a perturbation summary.
        """
        if not results:
            logger.warning("[StatisticsEngine] aggregate() called with empty list.")
            return ExperimentStatistics()

        stats = ExperimentStatistics(n_experiments=len(results))

        # ── Top-level status counts ──────────────────────────────────────
        from core.experiment_runner import ExperimentStatus
        for r in results:
            if r.status == ExperimentStatus.SUCCESS:
                stats.n_succeeded += 1
            elif r.status == ExperimentStatus.PARTIAL:
                stats.n_partial += 1
            else:
                stats.n_failed += 1

        runtimes = [r.runtime_seconds for r in results]
        stats.mean_runtime = _mean(runtimes)

        # ── Per-analysis metric aggregation ──────────────────────────────
        # Collect values: {analysis_name: {metric_name: [values]}}
        collector: Dict[str, Dict[str, List[float]]] = {}
        runtimes_by_analysis: Dict[str, List[float]] = {}
        warnings_by_analysis: Dict[str, int] = {}
        failed_by_analysis: Dict[str, int] = {}
        # Vector data collector: {analysis_name: {metric_key: [vector_per_trial]}}
        vector_collector: Dict[str, Dict[str, List[Any]]] = {}

        for exp_result in results:
            for a_res in exp_result.analysis_results:
                name = a_res.analysis_name
                if name not in collector:
                    collector[name] = {}
                    runtimes_by_analysis[name] = []
                    warnings_by_analysis[name] = 0
                    failed_by_analysis[name] = 0
                    vector_collector[name] = {}

                from modules.graph_analyses.analysis_result import AnalysisStatus
                if a_res.status == AnalysisStatus.FAILED:
                    failed_by_analysis[name] += 1
                    continue

                runtimes_by_analysis[name].append(a_res.runtime_seconds)
                warnings_by_analysis[name] += len(a_res.warnings)

                for metric_key, metric_val in a_res.metrics.items():
                    # ── Scalar pathway (unchanged) ────────────────
                    if isinstance(metric_val, (int, float)):
                        if metric_key not in collector[name]:
                            collector[name][metric_key] = []
                        collector[name][metric_key].append(float(metric_val))
                    # ── Vector pathway (new) ──────────────────────
                    elif _is_vector_value(metric_val):
                        if metric_key not in vector_collector[name]:
                            vector_collector[name][metric_key] = []
                        vector_collector[name][metric_key].append(
                            copy.deepcopy(metric_val)
                        )
                    # ── Skip other types (strings, dicts, etc.) ───
                    else:
                        continue

        # Store collected vector data for downstream comparison.
        stats.vector_data = vector_collector

        # Convert raw collections into MetricStats / AnalysisStats.
        for a_name, metrics_map in collector.items():
            a_stats = AnalysisStats(
                analysis_name=a_name,
                n_trials=len(runtimes_by_analysis.get(a_name, [])),
                n_failed=failed_by_analysis.get(a_name, 0),
                mean_runtime=_mean(runtimes_by_analysis[a_name])
                    if runtimes_by_analysis[a_name] else 0.0,
                total_warnings=warnings_by_analysis.get(a_name, 0),
            )

            for m_name, values in metrics_map.items():
                if not values:
                    continue
                m = _mean(values)
                v = _variance(values, m)
                s = _std(v)
                lo, hi = _confidence_interval(m, s, len(values))
                a_stats.metric_stats[m_name] = MetricStats(
                    metric_name=m_name,
                    n=len(values),
                    mean=m,
                    variance=v,
                    std=s,
                    min=min(values),
                    max=max(values),
                    ci_lower=lo,
                    ci_upper=hi,
                    raw=values,
                )

            stats.analysis_stats[a_name] = a_stats

        # ── Perturbation summary ─────────────────────────────────────────
        stats.perturbation_summary = self._summarise_perturbations(results)

        logger.info(
            "[StatisticsEngine] Aggregated %d experiments: "
            "success=%d partial=%d failed=%d "
            "vector_metrics=%d",
            stats.n_experiments,
            stats.n_succeeded,
            stats.n_partial,
            stats.n_failed,
            sum(len(v) for v in vector_collector.values()),
        )
        return stats

    # ------------------------------------------------------------------ #
    # Vector comparison                                                    #
    # ------------------------------------------------------------------ #

    def compute_vector_comparisons(
        self,
        baseline_stats: ExperimentStatistics,
        perturbed_stats: ExperimentStatistics,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, MetricStats]]:
        """Compare vector-valued metrics between baseline and perturbed trials.

        For each analysis and metric that has registered comparison strategies
        in :class:`~modules.statistical_evaluation.vector_comparison.VectorComparisonRegistry`,
        this method computes derived scalar metrics by comparing each
        perturbed trial's vector against the **average baseline vector**.

        Each derived scalar (e.g. ``pagerank_spearman``) then gets its own
        :class:`MetricStats` with mean / std / CI across perturbed trials,
        making them directly usable by the existing statistical evaluation
        machinery.

        Args:
            baseline_stats:
                :class:`ExperimentStatistics` for the baseline (0% error)
                trials.  Must contain ``vector_data``.
            perturbed_stats:
                :class:`ExperimentStatistics` for the perturbed trials.
                Must contain ``vector_data``.
            config:
                Optional configuration dict (e.g. ``{"top_k_overlap": 100}``).
                The engine-level config is merged with per-analysis config
                from ``config.get("statistics", {})``.

        Returns:
            A dict ``{analysis_name: {derived_metric_name: MetricStats}}``
            of derived scalar statistics.
        """
        from modules.statistical_evaluation.vector_comparison import (
            VectorComparisonRegistry,
        )

        cfg = copy.deepcopy(config or {})
        stats_cfg = cfg.get("statistics", {})
        top_k = int(stats_cfg.get("top_k_overlap", 100))
        comparison_cfg = {"top_k_overlap": top_k}

        result: Dict[str, Dict[str, MetricStats]] = {}

        # Determine the set of analyses that have vectors in both groups.
        all_analyses = set(baseline_stats.vector_data.keys()) & set(
            perturbed_stats.vector_data.keys()
        )

        for a_name in sorted(all_analyses):
            b_analysis_vecs = baseline_stats.vector_data[a_name]
            p_analysis_vecs = perturbed_stats.vector_data[a_name]

            # Determine which metric keys have strategies AND data in both.
            common_metrics = (
                set(b_analysis_vecs.keys())
                & set(p_analysis_vecs.keys())
            )

            for metric_key in sorted(common_metrics):
                strategy = VectorComparisonRegistry.get(a_name, metric_key)
                if strategy is None:
                    continue  # no comparison strategy registered

                b_raw_list = b_analysis_vecs[metric_key]
                p_raw_list = p_analysis_vecs[metric_key]

                if not b_raw_list or not p_raw_list:
                    logger.warning(
                        "[StatisticsEngine] Empty vector data for %s / %s. Skipping.",
                        a_name, metric_key,
                    )
                    continue

                # Convert all vectors to flat float lists.
                b_vectors = [_ensure_flat_float_list(v) for v in b_raw_list]
                p_vectors = [_ensure_flat_float_list(v) for v in p_raw_list]

                # Average baseline vectors across trials to get one
                # representative baseline.
                avg_baseline = self._average_vectors(b_vectors)

                if avg_baseline is None:
                    continue

                # For each perturbed trial, compare against the average
                # baseline vector, collecting derived scalars.
                # Organise: {derived_key: [value_per_trial]}
                derived_values: Dict[str, List[float]] = {}

                for p_vec in p_vectors:
                    try:
                        comparison = strategy(avg_baseline, p_vec, comparison_cfg)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "[StatisticsEngine] Vector comparison failed "
                            "for %s / %s: %s. Skipping trial.",
                            a_name, metric_key, exc,
                        )
                        continue

                    for d_key, d_val in comparison.items():
                        if not math.isfinite(d_val):
                            continue
                        derived_values.setdefault(d_key, []).append(d_val)

                if not derived_values:
                    continue

                # Build MetricStats for each derived scalar.
                if a_name not in result:
                    result[a_name] = {}

                for d_key, values in sorted(derived_values.items()):
                    # Prefix the derived key with the original metric name
                    # for disambiguation (e.g. "in_degrees" → "in_degrees_ks").
                    full_key = f"{metric_key}_{d_key}"
                    m = _mean(values)
                    v = _variance(values, m)
                    s = _std(v)
                    lo, hi = _confidence_interval(m, s, len(values))
                    result[a_name][full_key] = MetricStats(
                        metric_name=full_key,
                        n=len(values),
                        mean=m,
                        variance=v,
                        std=s,
                        min=min(values),
                        max=max(values),
                        ci_lower=lo,
                        ci_upper=hi,
                        raw=values,
                    )

        total_derived = sum(
            len(derived)
            for a_derived in result.values()
            for derived in [a_derived]
        )
        if total_derived:
            logger.info(
                "[StatisticsEngine] Computed %d derived vector comparison metrics "
                "across %d analyses.",
                total_derived, len(result),
            )

        return result

    @staticmethod
    def _average_vectors(vectors: List[List[float]]) -> Optional[List[float]]:
        """Element-wise average of a list of equal-length vectors.

        Returns ``None`` if *vectors* is empty or lengths are inconsistent.
        NaN / Inf values are excluded element-wise.
        """
        if not vectors:
            return None

        ref_len = len(vectors[0])
        for v in vectors[1:]:
            if len(v) != ref_len:
                logger.warning(
                    "[StatisticsEngine] Inconsistent vector lengths: "
                    "%d vs %d. Cannot average.",
                    ref_len, len(v),
                )
                return None

        n = len(vectors)
        if n == 1:
            return vectors[0]

        averaged: List[float] = []
        for i in range(ref_len):
            finite_vals = [v[i] for v in vectors if math.isfinite(v[i])]
            if not finite_vals:
                averaged.append(0.0)
            else:
                averaged.append(sum(finite_vals) / len(finite_vals))

        return averaged

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _summarise_perturbations(
        self, results: List[ExperimentResult]
    ) -> Dict[str, Any]:
        """Aggregate numeric fields from all ``ErrorResult.perturbation_metadata``."""
        pm_collector: Dict[str, List[float]] = {}
        model_names: List[str] = []

        for exp_result in results:
            er = exp_result.error_result
            if er is None:
                continue
            model_names.append(er.model_name)
            for k, v in er.perturbation_metadata.items():
                if isinstance(v, (int, float)):
                    pm_collector.setdefault(k, []).append(float(v))

        if not pm_collector:
            return {}

        summary: Dict[str, Any] = {
            "model_names": list(set(model_names)),
        }
        for k, vals in pm_collector.items():
            m = _mean(vals)
            summary[k] = {
                "mean": m,
                "std":  _std(_variance(vals, m)),
                "min":  min(vals),
                "max":  max(vals),
                "n":    len(vals),
            }
        return summary
