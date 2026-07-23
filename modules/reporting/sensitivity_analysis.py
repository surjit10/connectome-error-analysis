"""
modules/reporting/sensitivity_analysis.py
==========================================
Ranks metrics by their sensitivity to error-rate perturbations.

Consumes a :class:`~modules.reporting.trend_analysis.TrendAnalysisResult`
and produces a :class:`SensitivityResult` with enriched per-metric summaries.

Design constraints:
    - No plotting. No HTML. No file I/O.
    - All outputs are plain Python dataclasses.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from modules.reporting.trend_analysis import TrendAnalysisResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Effect-size magnitude labels (Cohen's conventions)
# ---------------------------------------------------------------------------

def _effect_label(d: float) -> str:
    """Return a human-readable label for an effect size magnitude."""
    a = abs(d)
    if a < 0.2:
        return "Negligible"
    if a < 0.5:
        return "Small"
    if a < 0.8:
        return "Medium"
    return "Large"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class MetricSensitivitySummary:
    """Sensitivity summary for a single metric.

    Attributes:
        metric_key:      Full key (``"analysis.metric"``).
        max_effect_size: Maximum |Cohen's d| across all error rates.
        effect_label:    Human label (Negligible / Small / Medium / Large).
        threshold_rate:  First error rate where |d| >= 0.8, or ``None``.
        is_sensitive:    ``True`` iff ``max_effect_size >= 0.8``.
        rank:            1-based rank (1 = most sensitive).
    """
    metric_key:      str
    max_effect_size: float
    effect_label:    str
    threshold_rate:  Optional[float]
    is_sensitive:    bool
    rank:            int


@dataclass
class SensitivityResult:
    """Complete sensitivity analysis output.

    Attributes:
        summaries:        All metrics sorted by descending effect size.
        sensitive_metrics: Subset where max |d| >= 0.8.
        dataset_name:     Dataset name.
        error_model_name: Error model name.
    """
    summaries:         List[MetricSensitivitySummary] = field(default_factory=list)
    sensitive_metrics: List[MetricSensitivitySummary] = field(default_factory=list)
    dataset_name:      str = ""
    error_model_name:  str = ""


# ---------------------------------------------------------------------------
# Analysis class
# ---------------------------------------------------------------------------

class SensitivityAnalysis:
    """Produce :class:`SensitivityResult` from a :class:`TrendAnalysisResult`.

    Example::

        sensitivity = SensitivityAnalysis(trend_result).compute()

    Args:
        trend: A completed :class:`TrendAnalysisResult`.
        large_effect_threshold: Cohen's d cutoff for "sensitive".  Default 0.8.
    """

    def __init__(
        self,
        trend: TrendAnalysisResult,
        large_effect_threshold: float = 0.8,
    ) -> None:
        self._trend     = trend
        self._threshold = large_effect_threshold

    def compute(self) -> SensitivityResult:
        """Run sensitivity analysis and return the result."""
        summaries: List[MetricSensitivitySummary] = []

        for rank, (key, max_d) in enumerate(self._trend.sensitivity_ranking, start=1):
            threshold_rate = self._trend.thresholds.get(key)
            summaries.append(MetricSensitivitySummary(
                metric_key      = key,
                max_effect_size = max_d,
                effect_label    = _effect_label(max_d),
                threshold_rate  = threshold_rate,
                is_sensitive    = max_d >= self._threshold,
                rank            = rank,
            ))

        sensitive = [s for s in summaries if s.is_sensitive]

        logger.info(
            "[SensitivityAnalysis] %d/%d metrics are sensitive (|d|>=%.1f).",
            len(sensitive), len(summaries), self._threshold,
        )

        return SensitivityResult(
            summaries         = summaries,
            sensitive_metrics = sensitive,
            dataset_name      = self._trend.dataset_name,
            error_model_name  = self._trend.error_model_name,
        )
