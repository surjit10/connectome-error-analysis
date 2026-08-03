"""
presentation/model_summary.py
==============================
Presentation-only summary builders shared by the dataset summary page and the
error-model comparison page.

Every value here is derived from **already-computed** statistical results
(``TrendAnalysisResult`` / ``SensitivityResult`` / ``StatisticalEvaluationResult``)
or from the exported ``combined_results.csv`` — no new statistics are computed.

Design constraints:
    - No statistical computation beyond re-arranging existing values.
    - No plotting, no file I/O.
    - Pure functions returning plain dicts for the Jinja2 templates.
    - The consumer (DatasetExporter) uses this module so the numbers it shows
      are identical to the underlying trend analysis.

The report is **purely descriptive**: it reports measured values (baseline /
perturbed / Δ% / preservation % / std / 95% CI) and lets reviewers draw their
own conclusions.  No verdicts, status labels, or interpretation sentences are
generated here.
"""
from __future__ import annotations

from typing import Dict, List

from modules.reporting.trend_analysis import TrendAnalysisResult
from presentation.preservation_config import (
    METRIC_DISPLAY_NAMES,
    SIMILARITY_METRICS,
    calculate_preservation,
    higher_is_better,
    is_preservation_metric,
)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _display(key: str, fallback: str) -> str:
    """Display name for a metric key (falls back to the metric suffix)."""
    return METRIC_DISPLAY_NAMES.get(key, fallback)


def _preservation(ev, key: str) -> float:
    """Preservation % for one MetricEvaluation, honouring direction."""
    return calculate_preservation(
        ev.baseline_mean, ev.mean,
        higher_is_better=higher_is_better(key),
    )


def _fmt(value: float) -> str:
    if value is None or value != value:  # None or NaN
        return "—"
    return f"{value:.4f}"


# --------------------------------------------------------------------------- #
# Per-metric preservation (min across rates)
# --------------------------------------------------------------------------- #

def metric_min_preservations(
    trend: TrendAnalysisResult,
    only_preservation: bool = True,
) -> Dict[str, float]:
    """Return ``{metric_key: min_preservation_across_rates}``.

    Only metrics classified as preservation metrics are included when
    ``only_preservation`` is ``True`` (the default).
    """
    out: Dict[str, float] = {}
    for rate, m_dict in trend.metrics_by_rate.items():
        for key, ev in m_dict.items():
            if only_preservation and not is_preservation_metric(key):
                continue
            pres = _preservation(ev, key)
            if key not in out or pres < out[key]:
                out[key] = pres
    return out


# --------------------------------------------------------------------------- #
# Network similarity section (derived scalar summaries only)
# --------------------------------------------------------------------------- #

def build_network_similarity(
    trend: TrendAnalysisResult,
) -> List[Dict]:
    """Build the Network Similarity Analysis table.

    Displays only the **derived scalar** summaries of vector comparisons
    (Pearson / Spearman / Top-K overlap / KS / Wasserstein).  Raw per-node
    vectors are never exposed.

    Returns ``[{metric_key, display, rate_cells: [{rate_pct, value}]}]``.
    """
    rows: List[Dict] = []
    for key, display in SIMILARITY_METRICS.items():
        rate_cells = []
        for rate in trend.rates:
            ev = trend.metrics_by_rate.get(rate, {}).get(key)
            if ev is None:
                continue
            rate_cells.append({"rate_pct": f"{rate*100:g}", "value": _fmt(ev.mean)})
        if rate_cells:
            rows.append({
                "metric_key": key,
                "display":    display,
                "rate_cells": rate_cells,
            })
    return rows


# --------------------------------------------------------------------------- #
# Statistical reliability section
# --------------------------------------------------------------------------- #

def build_reliability(
    trend: TrendAnalysisResult,
) -> List[Dict]:
    """Build the Statistical Reliability table.

    For each preservation metric reports the mean std and mean 95% CI width
    across all error rates (across-trial variability).

    Returns ``[{metric_key, display, avg_std, avg_ci_width, n_rates}]``.
    """
    rows: List[Dict] = []
    for key in sorted(metric_min_preservations(trend).keys()):
        stds, widths = [], []
        for rate in trend.rates:
            ev = trend.metrics_by_rate.get(rate, {}).get(key)
            if ev is None:
                continue
            stds.append(ev.std)
            if ev.ci_lower is not None and ev.ci_upper is not None:
                widths.append(ev.ci_upper - ev.ci_lower)
        if not stds:
            continue
        rows.append({
            "metric_key":   key,
            "display":      _display(key, key.split(".")[-1]),
            "avg_std":      f"{sum(stds)/len(stds):.4f}",
            "avg_std_num":  sum(stds)/len(stds),
            "avg_ci_width": f"{sum(widths)/len(widths):.4f}" if widths else "—",
            "avg_ci_width_num": sum(widths)/len(widths) if widths else None,
            "n_rates":      len(stds),
        })
    return rows
