"""
presentation/dataset_exporter.py
==================================
Orchestrates all exports for one (error_model, dataset) pair.

Responsibilities:
    - Instantiate SingleRateExporter for each error rate.
    - Instantiate TrendExporter for trend analysis.
    - Render dataset summary.html.

Design constraints:
    - No statistical computation.
    - No figure generation (delegates to specialized exporters).
    - Consumes pre-computed analysis objects.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from modules.reporting.trend_analysis import TrendAnalysisResult
from modules.reporting.sensitivity_analysis import SensitivityResult
from presentation.base_exporter import BaseExporter
from presentation.single_rate_exporter import SingleRateExporter
from presentation.trend_exporter import TrendExporter
from presentation.preservation_config import (
    calculate_preservation,
    get_biological_status,
    get_integrity_verdict,
    is_preservation_metric,
    higher_is_better,
    KEY_INTEGRITY_METRICS,
)

logger = logging.getLogger(__name__)

_ERROR_RATE_LABEL_MAP = {
    0.0:  "0",
    0.01: "1",
    0.05: "5",
    0.10: "10",
    0.20: "20",
}


def _rate_label(rate: float) -> str:
    """Convert float rate to folder-safe label (e.g., '10' for 10%, '0_25' for 0.25%)."""
    if rate in _ERROR_RATE_LABEL_MAP:
        return _ERROR_RATE_LABEL_MAP[rate]
    return f"{rate*100:g}".replace(".", "_")


class DatasetExporter(BaseExporter):
    """Orchestrate all exports for one dataset within one error model.

    Args:
        output_dir:          Root for this dataset (e.g. ``results/missed_synapses/BANC/``).
        results_by_rate:     All statistical results keyed by error rate.
        trend:               Pre-computed TrendAnalysisResult.
        sensitivity:         Pre-computed SensitivityResult.
        error_model_slug:    Slug (e.g. ``"missed_synapses"``).
        error_model_display: Human-readable name.
        dataset_name:        Dataset name (e.g. ``"BANC"``).
        results_root:        ``results/`` root for relative path computation.
    """

    def __init__(
        self,
        output_dir:          Path,
        results_by_rate:     Dict[float, StatisticalEvaluationResult],
        trend:               TrendAnalysisResult,
        sensitivity:         SensitivityResult,
        error_model_slug:    str,
        error_model_display: str,
        dataset_name:        str,
        results_root:        Path,
    ) -> None:
        super().__init__(output_dir)
        self._results    = results_by_rate
        self._trend      = trend
        self._sensitivity = sensitivity
        self._em_slug    = error_model_slug
        self._em_display = error_model_display
        self._dataset    = dataset_name
        self._root       = results_root

    def export(self) -> None:
        """Run the full dataset export pipeline."""
        self._ensure_dirs(self.output_dir)
        sorted_rates = sorted(self._results.keys())

        # Phase A — per error rate
        for rate in sorted_rates:
            label     = _rate_label(rate)
            rate_dir  = self.output_dir / f"error_{label}"
            exporter  = SingleRateExporter(
                output_dir          = rate_dir,
                result              = self._results[rate],
                error_model_slug    = self._em_slug,
                error_model_display = self._em_display,
                dataset_name        = self._dataset,
                results_root        = self._root,
                sorted_rates        = sorted_rates,
            )
            exporter.export()

        # Phase B — trend analysis
        trend_dir = self.output_dir / "trend_analysis"
        TrendExporter(
            output_dir          = trend_dir,
            trend               = self._trend,
            sensitivity         = self._sensitivity,
            results_by_rate     = self._results,
            error_model_slug    = self._em_slug,
            error_model_display = self._em_display,
            dataset_name        = self._dataset,
            results_root        = self._root,
        ).export()

        # Phase C — dataset summary.html
        self._render_summary(sorted_rates)

    # ------------------------------------------------------------------ #
    # HTML                                                                 #
    # ------------------------------------------------------------------ #

    def _compute_rates_info(self, sorted_rates: List[float]) -> List[Dict]:
        """Build per-rate info with preservation data for the summary page."""
        rates_info = []
        for rate in sorted_rates:
            res    = self._results[rate]
            label  = _rate_label(rate)
            rate_metrics = self._trend.metrics_by_rate.get(rate, {})
            n_disrupted = 0
            for key, ev in rate_metrics.items():
                if not is_preservation_metric(key):
                    continue
                pres = calculate_preservation(
                    ev.baseline_mean, ev.mean,
                    higher_is_better=higher_is_better(key),
                )
                if pres < 95.0:
                    n_disrupted += 1
            rates_info.append({
                "label":       label,
                "n_trials":    res.n_trials,
                "n_disrupted": n_disrupted,
            })
        return rates_info

    def _compute_integrity(self) -> float:
        """Compute overall network integrity from the first non-baseline rate."""
        sorted_rates = sorted(self._results.keys())
        # Use the first perturbed rate (skip baseline)
        for rate in sorted_rates:
            if rate > 0.0:
                res = self._results[rate]
                preservations = []
                for a_name, m_dict in res.metrics.items():
                    for m_name, ev in m_dict.items():
                        key = f"{a_name}.{m_name}"
                        if key in KEY_INTEGRITY_METRICS:
                            pres = calculate_preservation(
                                ev.baseline_mean, ev.mean,
                                higher_is_better=higher_is_better(key),
                            )
                            preservations.append(pres)
                if preservations:
                    return round(sum(preservations) / len(preservations), 2)
        return 100.0

    def _render_summary(self, sorted_rates: List[float]) -> None:
        n_metrics    = len(self._sensitivity.summaries)
        total_trials = sum(r.n_trials for r in self._results.values())
        rates_info   = self._compute_rates_info(sorted_rates)

        # Overall integrity score
        integrity_score = self._compute_integrity()
        integrity_emoji, integrity_verdict, integrity_css = get_integrity_verdict(integrity_score)

        # Find worst preserved metric from first perturbed rate
        worst_preservation = 100.0
        worst_metric = "—"
        for rate in sorted_rates:
            if rate > 0.0:
                for key, ev in self._trend.metrics_by_rate.get(rate, {}).items():
                    if not is_preservation_metric(key):
                        continue
                    pres = calculate_preservation(
                        ev.baseline_mean, ev.mean,
                        higher_is_better=higher_is_better(key),
                    )
                    if pres < worst_preservation:
                        worst_preservation = pres
                        worst_metric = key

        # Preservation ranking preview (preservation metrics only)
        from collections import defaultdict
        metric_worst = defaultdict(lambda: 100.0)
        for rate in sorted_rates:
            for key, ev in self._trend.metrics_by_rate.get(rate, {}).items():
                if not is_preservation_metric(key):
                    continue
                pres = calculate_preservation(
                    ev.baseline_mean, ev.mean,
                    higher_is_better=higher_is_better(key),
                )
                if pres < metric_worst[key]:
                    metric_worst[key] = pres

        # Sort by worst preservation (ascending)
        sorted_metrics = sorted(metric_worst.items(), key=lambda x: x[1])
        sensitivity_rows = []
        for rank, (key, min_pres) in enumerate(sorted_metrics[:10], start=1):
            _, bio_label, bio_css = get_biological_status(min_pres)
            sensitivity_rows.append({
                "rank":            rank,
                "metric_key":      key,
                "min_preservation": f"{min_pres:.2f}%",
                "biological_status": bio_label,
                "bio_css":         bio_css,
            })

        root_path = self._rel_root(self.output_dir, self._root)

        self._render_template(
            "dataset_summary.html",
            {
                "dataset_name":        self._dataset,
                "error_model_slug":    self._em_slug,
                "error_model_display": self._em_display,
                "n_rates":             len(sorted_rates),
                "total_trials":        total_trials,
                "n_metrics":           n_metrics,
                "integrity_score":     f"{integrity_score:.2f}%",
                "integrity_emoji":     integrity_emoji,
                "integrity_verdict":   integrity_verdict,
                "integrity_css":       integrity_css,
                "worst_preservation":  f"{worst_preservation:.2f}%",
                "worst_metric":        worst_metric,
                "rates":               rates_info,
                "sensitivity_rows":    sensitivity_rows,
                "root_path":           root_path,
            },
            self.output_dir / "summary.html",
        )
