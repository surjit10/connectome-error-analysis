"""
modules/reporting/trend_analysis.py
=====================================
Computes trend-level analysis across all error rates for one
(error_model, dataset) pair.

Consumes a ``Dict[float, StatisticalEvaluationResult]`` and returns a
:class:`TrendAnalysisResult` dataclass.

Design constraints:
    - No plotting.
    - No HTML.
    - No file I/O.
    - All outputs are plain Python dataclasses or stdlib types.
    - Statistical algorithms may only use numpy/scipy — no matplotlib.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from modules.statistical_evaluation.evaluator import (
    MetricEvaluation,
    StatisticalEvaluationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TrendAnalysisResult:
    """Aggregated trend data across all error rates.

    Attributes:
        rates:
            Sorted list of error rates analysed.
        metrics_by_rate:
            ``{rate: {full_metric_key: MetricEvaluation}}`` where
            ``full_metric_key`` is ``"analysis.metric"``.
        sensitivity_ranking:
            Ordered list of ``(full_metric_key, max_abs_effect_size)`` tuples
            sorted descending — most sensitive metric first.
        thresholds:
            ``{full_metric_key: first_rate_with_large_effect}`` where
            "large effect" means ``|Cohen's d| >= 0.8``.  ``None`` if the
            metric never crosses the threshold.
        metric_correlations:
            Pearson correlation matrix of metric means across error rates.
            ``{metric_a: {metric_b: r}}``
        dataset_name:
            Name of the dataset this trend covers.
        error_model_name:
            Name of the error model this trend covers.
    """
    rates:                List[float]                              = field(default_factory=list)
    metrics_by_rate:      Dict[float, Dict[str, MetricEvaluation]] = field(default_factory=dict)
    sensitivity_ranking:  List[Tuple[str, float]]                  = field(default_factory=list)
    thresholds:           Dict[str, Optional[float]]               = field(default_factory=dict)
    metric_correlations:  Dict[str, Dict[str, float]]              = field(default_factory=dict)
    dataset_name:         str                                      = ""
    error_model_name:     str                                      = ""


# ---------------------------------------------------------------------------
# Analysis class
# ---------------------------------------------------------------------------

class TrendAnalysis:
    """Compute :class:`TrendAnalysisResult` from per-rate evaluation results.

    Example::

        trend = TrendAnalysis(
            results_by_rate,
            dataset_name="BANC",
            error_model_name="missed_synapses",
        ).compute()

    Args:
        results_by_rate:   ``{rate: StatisticalEvaluationResult}``
        dataset_name:      Human-readable dataset identifier.
        error_model_name:  Human-readable error model identifier.
        large_effect_threshold:
            Cohen's d threshold for threshold detection.  Default ``0.8``.
    """

    def __init__(
        self,
        results_by_rate:   Dict[float, StatisticalEvaluationResult],
        dataset_name:      str = "",
        error_model_name:  str = "",
        large_effect_threshold: float = 0.8,
    ) -> None:
        self._results   = results_by_rate
        self._rates     = sorted(results_by_rate.keys())
        self._dataset   = dataset_name
        self._error_model = error_model_name
        self._threshold = large_effect_threshold

    def compute(self) -> TrendAnalysisResult:
        """Run all trend computations and return the result."""
        if not self._results:
            logger.warning("[TrendAnalysis] No results provided — returning empty result.")
            return TrendAnalysisResult(
                dataset_name=self._dataset,
                error_model_name=self._error_model,
            )

        metrics_by_rate = self._flatten_metrics()
        all_metric_keys = self._all_keys(metrics_by_rate)

        sensitivity  = self._compute_sensitivity(metrics_by_rate, all_metric_keys)
        thresholds   = self._compute_thresholds(metrics_by_rate, all_metric_keys)
        correlations = self._compute_correlations(metrics_by_rate, all_metric_keys)

        logger.info(
            "[TrendAnalysis] Completed for %s/%s — %d metrics across %d rates.",
            self._dataset, self._error_model, len(all_metric_keys), len(self._rates),
        )

        return TrendAnalysisResult(
            rates               = self._rates,
            metrics_by_rate     = metrics_by_rate,
            sensitivity_ranking = sensitivity,
            thresholds          = thresholds,
            metric_correlations = correlations,
            dataset_name        = self._dataset,
            error_model_name    = self._error_model,
        )

    # ------------------------------------------------------------------ #
    # Internal computations                                                #
    # ------------------------------------------------------------------ #

    def _flatten_metrics(self) -> Dict[float, Dict[str, MetricEvaluation]]:
        """Flatten nested dicts into ``{rate: {"analysis.metric": eval}}``."""
        flat: Dict[float, Dict[str, MetricEvaluation]] = {}
        for rate, res in self._results.items():
            flat[rate] = {}
            for a_name, m_dict in res.metrics.items():
                for m_name, ev in m_dict.items():
                    flat[rate][f"{a_name}.{m_name}"] = ev
        return flat

    @staticmethod
    def _all_keys(metrics_by_rate: Dict[float, Dict[str, MetricEvaluation]]) -> List[str]:
        """Collect the union of all metric keys across all rates."""
        keys: set = set()
        for m_dict in metrics_by_rate.values():
            keys.update(m_dict.keys())
        return sorted(keys)

    def _compute_sensitivity(
        self,
        metrics_by_rate: Dict[float, Dict[str, MetricEvaluation]],
        all_keys: List[str],
    ) -> List[Tuple[str, float]]:
        """Rank metrics by maximum absolute Cohen's d across all rates."""
        ranking: List[Tuple[str, float]] = []
        for key in all_keys:
            effect_sizes = [
                abs(metrics_by_rate[r][key].effect_size)
                for r in self._rates
                if key in metrics_by_rate.get(r, {})
            ]
            max_d = max(effect_sizes) if effect_sizes else 0.0
            ranking.append((key, max_d))
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking

    def _compute_thresholds(
        self,
        metrics_by_rate: Dict[float, Dict[str, MetricEvaluation]],
        all_keys: List[str],
    ) -> Dict[str, Optional[float]]:
        """Find the first error rate at which |Cohen's d| >= threshold."""
        thresholds: Dict[str, Optional[float]] = {}
        for key in all_keys:
            first = None
            for rate in self._rates:
                ev = metrics_by_rate.get(rate, {}).get(key)
                if ev is not None and abs(ev.effect_size) >= self._threshold:
                    first = rate
                    break
            thresholds[key] = first
        return thresholds

    def _compute_correlations(
        self,
        metrics_by_rate: Dict[float, Dict[str, MetricEvaluation]],
        all_keys: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """Compute Pearson correlation of metric means across error rates.

        Only considers metrics that have at least 2 non-NaN data points.
        """
        if len(self._rates) < 2:
            return {}

        # Build matrix: rows=rates, cols=metrics
        matrix: Dict[str, List[float]] = {k: [] for k in all_keys}
        for rate in self._rates:
            for key in all_keys:
                ev = metrics_by_rate.get(rate, {}).get(key)
                val = ev.mean if (ev is not None and math.isfinite(ev.mean)) else float("nan")
                matrix[key].append(val)

        # Filter to keys with enough finite values
        valid_keys = [
            k for k in all_keys
            if sum(1 for v in matrix[k] if math.isfinite(v)) >= 2
        ]

        corr: Dict[str, Dict[str, float]] = {}
        for k1 in valid_keys:
            corr[k1] = {}
            v1 = np.array(matrix[k1], dtype=float)
            for k2 in valid_keys:
                v2 = np.array(matrix[k2], dtype=float)
                # Use only indices where both are finite
                mask = np.isfinite(v1) & np.isfinite(v2)
                if mask.sum() < 2:
                    corr[k1][k2] = float("nan")
                else:
                    try:
                        r = float(np.corrcoef(v1[mask], v2[mask])[0, 1])
                        corr[k1][k2] = r if math.isfinite(r) else 0.0
                    except Exception:  # noqa: BLE001
                        corr[k1][k2] = 0.0

        return corr
