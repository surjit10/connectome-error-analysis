"""
Metric Comparison Engine
========================
Performs rigorous statistical comparisons between Real connectome secondary effects
and matched Null connectome secondary effects across experimental replicates.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from scipy.stats import ttest_ind as _ttest_ind
    from scipy.stats import ttest_rel as _ttest_rel
    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCIPY_AVAILABLE = False
    _ttest_ind = _ttest_rel = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def cohens_d(
    mean1: float, std1: float, n1: int,
    mean2: float, std2: float, n2: int,
) -> float:
    """Compute Cohen's d effect size between two independent groups."""
    if n1 + n2 <= 2:
        return 0.0
    pooled_var = ((n1 - 1) * (std1 ** 2) + (n2 - 1) * (std2 ** 2)) / (n1 + n2 - 2)
    if pooled_var <= 1e-15 or not math.isfinite(pooled_var):
        return 0.0
    d = (mean1 - mean2) / math.sqrt(pooled_var)
    return float(d) if math.isfinite(d) else 0.0


@dataclass
class MetricComparisonResult:
    """Statistical comparison outcome for one metric at a specific error rate."""
    dataset: str
    error_model: str
    error_rate: float
    analysis_name: str
    metric_name: str
    category: str
    real_mean_effect: float
    real_std_effect: float
    real_n: int
    null_mean_effect: float
    null_std_effect: float
    null_n: int
    effect_difference: float      # real_mean - null_mean
    effect_size: float            # Cohen's d
    p_value: Optional[float]      # Parametric/non-parametric p-value
    test_name: str                # e.g. "welch_t_test", "paired_t_test", "n=1_deterministic"
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    is_paired: bool = False
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "error_model": self.error_model,
            "error_rate": self.error_rate,
            "analysis_name": self.analysis_name,
            "metric_name": self.metric_name,
            "category": self.category,
            "real_mean_effect": self.real_mean_effect,
            "real_std_effect": self.real_std_effect,
            "real_n": self.real_n,
            "null_mean_effect": self.null_mean_effect,
            "null_std_effect": self.null_std_effect,
            "null_n": self.null_n,
            "effect_difference": self.effect_difference,
            "effect_size": self.effect_size,
            "p_value": self.p_value,
            "test_name": self.test_name,
            "warning": self.warning,
        }


class MetricComparator:
    """Compares real vs null relative effect distributions."""

    def compare(
        self,
        dataset: str,
        error_model: str,
        error_rate: float,
        analysis_name: str,
        metric_name: str,
        category: str,
        real_effects: List[float],
        null_effects: List[float],
        paired: bool = False,
    ) -> MetricComparisonResult:
        """Compare real and null secondary effect samples.

        Args:
            dataset: Dataset name.
            error_model: Error model name.
            error_rate: Error rate float.
            analysis_name: Analysis name.
            metric_name: Metric name.
            category: "secondary_emergent", "primary_imposed", etc.
            real_effects: List of relative changes for Real condition.
            null_effects: List of relative changes for Null condition.
            paired: Whether samples correspond to matched seeds.
        """
        r_arr = np.array([x for x in real_effects if math.isfinite(x)], dtype=np.float64)
        n_arr = np.array([y for y in null_effects if math.isfinite(y)], dtype=np.float64)

        n_real = len(r_arr)
        n_null = len(n_arr)

        if n_real == 0 or n_null == 0:
            return MetricComparisonResult(
                dataset=dataset,
                error_model=error_model,
                error_rate=error_rate,
                analysis_name=analysis_name,
                metric_name=metric_name,
                category=category,
                real_mean_effect=0.0,
                real_std_effect=0.0,
                real_n=n_real,
                null_mean_effect=0.0,
                null_std_effect=0.0,
                null_n=n_null,
                effect_difference=0.0,
                effect_size=0.0,
                p_value=None,
                test_name="insufficient_data",
                warning="No valid finite observations in one or both groups.",
            )

        r_mean = float(np.mean(r_arr))
        r_std = float(np.std(r_arr, ddof=1)) if n_real > 1 else 0.0
        n_mean = float(np.mean(n_arr))
        n_std = float(np.std(n_arr, ddof=1)) if n_null > 1 else 0.0

        diff = r_mean - n_mean
        d = cohens_d(r_mean, r_std, n_real, n_mean, n_std, n_null)

        # ── Statistical Testing ──────────────────────────────────────
        p_val: Optional[float] = None
        test_name = "descriptive"
        warn = None

        if n_real == 1 and n_null == 1:
            test_name = "n=1_point_comparison"
            p_val = None
            warn = "Single trial evaluated (deterministic effect difference; significance testing requires >= 3 replicates)."
        elif n_real < 3 or n_null < 3:
            test_name = "small_sample_welch_t"
            try:
                if not _SCIPY_AVAILABLE:
                    raise ImportError("scipy not available")
                stat, p = _ttest_ind(r_arr, n_arr, equal_var=False)
                p_val = float(p) if math.isfinite(p) else None
            except Exception as exc:
                p_val = None
                warn = f"Small sample t-test failed: {exc}"
            warn = (warn or "") + " Warning: Low statistical power (sample size < 3)."
        else:
            if paired and n_real == n_null:
                test_name = "paired_t_test"
                try:
                    if not _SCIPY_AVAILABLE:
                        raise ImportError("scipy not available")
                    stat, p = _ttest_rel(r_arr, n_arr)
                    p_val = float(p) if math.isfinite(p) else None
                except Exception:
                    test_name = "welch_t_test"
                    stat, p = _ttest_ind(r_arr, n_arr, equal_var=False)
                    p_val = float(p) if math.isfinite(p) else None
            else:
                test_name = "welch_t_test"
                try:
                    if not _SCIPY_AVAILABLE:
                        raise ImportError("scipy not available")
                    stat, p = _ttest_ind(r_arr, n_arr, equal_var=False)
                    p_val = float(p) if math.isfinite(p) else None
                except Exception as exc:
                    p_val = None
                    warn = f"Welch t-test failed: {exc}"

        return MetricComparisonResult(
            dataset=dataset,
            error_model=error_model,
            error_rate=error_rate,
            analysis_name=analysis_name,
            metric_name=metric_name,
            category=category,
            real_mean_effect=r_mean,
            real_std_effect=r_std,
            real_n=n_real,
            null_mean_effect=n_mean,
            null_std_effect=n_std,
            null_n=n_null,
            effect_difference=diff,
            effect_size=d,
            p_value=p_val,
            test_name=test_name,
            is_paired=paired and n_real == n_null,
            warning=warn,
        )
