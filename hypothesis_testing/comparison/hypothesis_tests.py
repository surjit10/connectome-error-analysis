"""
Hypothesis Testing Engine & Interpretation Generator
====================================================
Evaluates scientific hypotheses (H0 vs H1), applies multiple-testing FDR corrections,
and produces plain-English narrative interpretations of connectome structural effects.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .metric_comparison import MetricComparisonResult

logger = logging.getLogger(__name__)


def benjamini_hochberg_fdr(p_values: List[Optional[float]], alpha: float = 0.05) -> Tuple[List[Optional[float]], List[bool]]:
    """Applies Benjamini-Hochberg FDR correction to a list of p-values."""
    n = len(p_values)
    if n == 0:
        return [], []

    # Extract valid p-values with their original indices
    valid = [(i, p) for i, p in enumerate(p_values) if p is not None and math.isfinite(p)]
    if not valid:
        return [None] * n, [False] * n

    valid_sorted = sorted(valid, key=lambda x: x[1])
    m = len(valid_sorted)

    adj_p_map: Dict[int, float] = {}
    sig_map: Dict[int, bool] = {}

    # Step-up procedure
    # p_adj_i = min(p_i * m / rank, next_p_adj)
    cum_min = 1.0
    for rank_idx in range(m - 1, -1, -1):
        orig_idx, p_val = valid_sorted[rank_idx]
        rank = rank_idx + 1
        adj_p = min(1.0, p_val * m / rank)
        cum_min = min(cum_min, adj_p)
        adj_p_map[orig_idx] = cum_min
        sig_map[orig_idx] = cum_min < alpha

    adjusted: List[Optional[float]] = []
    significant: List[bool] = []
    for i in range(n):
        if i in adj_p_map:
            adjusted.append(adj_p_map[i])
            significant.append(sig_map[i])
        else:
            adjusted.append(None)
            significant.append(False)

    return adjusted, significant


@dataclass
class HypothesisTestResult:
    """Final hypothesis-testing outcome with adjusted significance and human interpretation."""
    comparison: MetricComparisonResult
    adjusted_p_value: Optional[float]
    is_significant: bool
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        d = self.comparison.to_dict()
        d["adjusted_p_value"] = self.adjusted_p_value
        d["is_significant"] = self.is_significant
        d["interpretation"] = self.interpretation
        return d


class HypothesisTestEngine:
    """Evaluates hypothesis test results across comparison suites."""

    def __init__(self, alpha: float = 0.05) -> None:
        self.alpha = alpha

    def evaluate_suite(
        self, comparisons: List[MetricComparisonResult]
    ) -> List[HypothesisTestResult]:
        """Apply FDR correction and generate narrative interpretations."""
        if not comparisons:
            return []

        # Only secondary emergent metrics with valid p-values participate in
        # FDR correction.  Exclude:
        #   - primary_imposed / control_invariant (mechanically determined)
        #   - zero_variance_indeterminate (both groups identical, no test)
        #   - p_value is None (insufficient data or n<3)
        secondary_indices = [
            i for i, c in enumerate(comparisons)
            if c.category == "secondary_emergent"
            and c.p_value is not None
            and c.test_name != "zero_variance_indeterminate"
        ]
        secondary_p_vals = [comparisons[i].p_value for i in secondary_indices]

        adj_p_sub, sig_sub = benjamini_hochberg_fdr(secondary_p_vals, alpha=self.alpha)

        adj_map: Dict[int, Optional[float]] = {
            sec_idx: adj_p_sub[k] for k, sec_idx in enumerate(secondary_indices)
        }
        sig_map: Dict[int, bool] = {
            sec_idx: sig_sub[k] for k, sec_idx in enumerate(secondary_indices)
        }

        results: List[HypothesisTestResult] = []
        for i, comp in enumerate(comparisons):
            adj_p = adj_map.get(i)
            is_sig = sig_map.get(i, False)
            interp = self._generate_interpretation(comp, adj_p, is_sig)

            results.append(HypothesisTestResult(
                comparison=comp,
                adjusted_p_value=adj_p,
                is_significant=is_sig,
                interpretation=interp,
            ))

        return results

    def _generate_interpretation(
        self, comp: MetricComparisonResult, adj_p: Optional[float], is_sig: bool
    ) -> str:
        """Generate a scientifically precise plain-English narrative."""
        metric_label = comp.metric_name.replace("metric_", "").replace("_", " ")
        rate_pct = f"{comp.error_rate * 100:.1f}%"
        diff_pct = f"{comp.effect_difference * 100:+.2f}%"

        # 1. Primary/Guaranteed Manipulations
        if comp.category == "primary_imposed":
            return (
                f"Primary imposed manipulation: {metric_label} change is algebraically "
                f"or mechanically predetermined by the error model operation."
            )
        if comp.category == "control_invariant":
            return (
                f"Control invariant: {metric_label} remains topologically fixed by design "
                f"under {comp.error_model}."
            )

        # 2. Zero-variance deterministic tests
        if comp.test_name == "zero_variance_indeterminate":
            return (
                f"At {rate_pct} error rate, {metric_label} changed by {diff_pct} in both Real and Null. "
                f"Both groups produced identical values (zero variance); the response is purely "
                f"mechanical and does not depend on biological connectome organization."
            )
        if comp.test_name == "zero_variance_deterministic":
            direction = "greater" if comp.effect_difference > 0 else "less"
            return (
                f"At {rate_pct} error rate, {metric_label} changed by {comp.real_mean_effect:+.2%} in Real "
                f"vs {comp.null_mean_effect:+.2%} in Null (difference = {diff_pct}). "
                f"Both groups have zero variance, so the difference is deterministic."
            )

        # 3. Single-trial point comparison
        if comp.real_n == 1 and comp.null_n == 1:
            direction = "amplified" if comp.effect_difference > 0 else "buffered"
            return (
                f"At {rate_pct} error rate, Real effect was {comp.real_mean_effect:+.2%} vs "
                f"Null effect {comp.null_mean_effect:+.2%} (difference = {diff_pct}). "
                f"Single trial evaluated (deterministic point difference; run >= 3 seeds for significance testing)."
            )

        # 4. Replicated significance outcomes
        if is_sig:
            direction = "greater" if comp.effect_difference > 0 else "less"
            return (
                f"At {rate_pct} error rate, the secondary change in {metric_label} was significantly "
                f"{direction} in Real ({comp.real_mean_effect:+.2%}) than Null ({comp.null_mean_effect:+.2%}) "
                f"(difference = {diff_pct}, d = {comp.effect_size:.2f}, p_adj = {adj_p:.4f}). "
                f"Suggests connectome biological organization significantly shapes this secondary effect."
            )
        else:
            if adj_p is not None:
                return (
                    f"At {rate_pct} error rate, the secondary change in {metric_label} (Real: {comp.real_mean_effect:+.2%}, "
                    f"Null: {comp.null_mean_effect:+.2%}) did not differ significantly (p_adj = {adj_p:.4f}, d = {comp.effect_size:.2f}). "
                    f"The observed response is consistent with expected random network behavior."
                )
            else:
                return (
                    f"At {rate_pct} error rate, {metric_label} showed a difference of {diff_pct}, "
                    f"but statistical significance could not be determined due to low sample size (n < 3)."
                )
