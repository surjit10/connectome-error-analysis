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

logger = logging.getLogger(__name__)

_ERROR_RATE_LABEL_MAP = {
    0.0:  "0",
    0.01: "1",
    0.05: "5",
    0.10: "10",
    0.20: "20",
}


def _rate_label(rate: float) -> str:
    """Convert float rate to folder-safe label (``'10'`` for 10%)."""
    if rate in _ERROR_RATE_LABEL_MAP:
        return _ERROR_RATE_LABEL_MAP[rate]
    return f"{rate*100:.0f}"


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

    def _render_summary(self, sorted_rates: List[float]) -> None:
        all_effects = [s.max_effect_size for s in self._sensitivity.summaries]
        n_sensitive = sum(1 for s in self._sensitivity.summaries if s.is_sensitive)
        max_d       = f"{max(all_effects):.4f}" if all_effects else "0.0000"
        top_metric  = self._sensitivity.summaries[0].metric_key if self._sensitivity.summaries else "—"
        n_metrics   = len(self._sensitivity.summaries)
        total_trials = sum(r.n_trials for r in self._results.values())

        # Per-rate summary for link list
        rates_info = []
        for rate in sorted_rates:
            res    = self._results[rate]
            label  = _rate_label(rate)
            # How many metrics are sensitive at THIS rate specifically?
            rate_metrics = self._trend.metrics_by_rate.get(rate, {})
            n_sens_at_rate = sum(
                1 for ev in rate_metrics.values() if abs(ev.effect_size) >= 0.8
            )
            rates_info.append({
                "label":      label,
                "n_trials":   res.n_trials,
                "n_sensitive": n_sens_at_rate,
            })

        sensitivity_rows = [
            {
                "rank":            s.rank,
                "metric_key":      s.metric_key,
                "max_effect_size": s.max_effect_size,
                "effect_label":    s.effect_label,
                "threshold_rate":  s.threshold_rate,
                "is_sensitive":    s.is_sensitive,
            }
            for s in self._sensitivity.summaries[:10]  # top 10 preview
        ]

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
                "n_sensitive":         n_sensitive,
                "max_effect_size":     max_d,
                "top_metric":          top_metric,
                "rates":               rates_info,
                "sensitivity_rows":    sensitivity_rows,
                "root_path":           root_path,
            },
            self.output_dir / "summary.html",
        )
