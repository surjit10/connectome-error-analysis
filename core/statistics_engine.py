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
    - Return plain Python dicts so downstream (Export Manager) needs no
      statistical knowledge.

Constraints:
    - Consumes only ``ExperimentResult`` objects. Never reruns experiments.
    - Uses only the Python standard library (no scipy/numpy dependency).
    - Never modifies any result object.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

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
    """
    n_experiments: int = 0
    n_succeeded: int = 0
    n_partial: int = 0
    n_failed: int = 0
    mean_runtime: float = 0.0
    analysis_stats: Dict[str, AnalysisStats] = field(default_factory=dict)
    perturbation_summary: Dict[str, Any] = field(default_factory=dict)

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

        for exp_result in results:
            for a_res in exp_result.analysis_results:
                name = a_res.analysis_name
                if name not in collector:
                    collector[name] = {}
                    runtimes_by_analysis[name] = []
                    warnings_by_analysis[name] = 0
                    failed_by_analysis[name] = 0

                from modules.graph_analyses.analysis_result import AnalysisStatus
                if a_res.status == AnalysisStatus.FAILED:
                    failed_by_analysis[name] += 1
                    continue

                runtimes_by_analysis[name].append(a_res.runtime_seconds)
                warnings_by_analysis[name] += len(a_res.warnings)

                for metric_key, metric_val in a_res.metrics.items():
                    if not isinstance(metric_val, (int, float)):
                        continue   # only numeric metrics are aggregated
                    if metric_key not in collector[name]:
                        collector[name][metric_key] = []
                    collector[name][metric_key].append(float(metric_val))

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
            "success=%d partial=%d failed=%d",
            stats.n_experiments,
            stats.n_succeeded,
            stats.n_partial,
            stats.n_failed,
        )
        return stats

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
