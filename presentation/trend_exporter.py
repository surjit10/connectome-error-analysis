"""
presentation/trend_exporter.py
================================
Exports the trend analysis for one (error_model, dataset) pair into:

    trend_analysis/
        trend_report.html
        combined_results.csv
        combined_statistics.csv
        plots/
            metric_trends/
            global_summaries/
            heatmaps/
            rankings/

Design constraints:
    - No statistical computation.
    - No figure generation (delegates to TrendPlotter).
    - Consumes pre-computed TrendAnalysisResult and SensitivityResult.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from modules.reporting.trend_analysis import TrendAnalysisResult
from modules.reporting.sensitivity_analysis import SensitivityResult
from presentation.base_exporter import BaseExporter
from presentation.trend_plotter import TrendPlotter

logger = logging.getLogger(__name__)


def _effect_label(d: float) -> str:
    a = abs(d)
    if a < 0.2:  return "Negligible"
    if a < 0.5:  return "Small"
    if a < 0.8:  return "Medium"
    return "Large"


class TrendExporter(BaseExporter):
    """Export trend analysis for one dataset.

    Args:
        output_dir:          The ``trend_analysis/`` directory.
        trend:               Pre-computed TrendAnalysisResult.
        sensitivity:         Pre-computed SensitivityResult.
        results_by_rate:     Original results dict (for CSV export).
        error_model_slug:    Slug of the error model.
        error_model_display: Human-readable name.
        dataset_name:        Dataset name.
        results_root:        ``results/`` root for relative path computation.
    """

    def __init__(
        self,
        output_dir:          Path,
        trend:               TrendAnalysisResult,
        sensitivity:         SensitivityResult,
        results_by_rate:     Dict[float, StatisticalEvaluationResult],
        error_model_slug:    str,
        error_model_display: str,
        dataset_name:        str,
        results_root:        Path,
    ) -> None:
        super().__init__(output_dir)
        self._trend      = trend
        self._sensitivity = sensitivity
        self._results    = results_by_rate
        self._em_slug    = error_model_slug
        self._em_display = error_model_display
        self._dataset    = dataset_name
        self._root       = results_root

    def export(self) -> None:
        """Run the full trend export pipeline."""
        logger.info("[TrendExporter] Exporting trend analysis for %s/%s",
                    self._em_slug, self._dataset)

        self._ensure_dirs(self.output_dir)

        # 1. CSVs
        self._write_combined_results()
        self._write_combined_statistics()

        # 2. Plots (via TrendPlotter)
        plotter = TrendPlotter(
            trend       = self._trend,
            sensitivity = self._sensitivity,
            output_dir  = self.output_dir / "plots",
        )
        plot_groups = plotter.generate_all()

        # 3. HTML
        self._render_trend_report(plot_groups)

    # ------------------------------------------------------------------ #
    # CSVs                                                                 #
    # ------------------------------------------------------------------ #

    def _write_combined_results(self) -> None:
        """Write combined_results.csv — all metrics × all rates."""
        rows = []
        for rate in self._trend.rates:
            for key, ev in self._trend.metrics_by_rate.get(rate, {}).items():
                a_name, _, m_name = key.partition(".")
                rows.append({
                    "rate":           rate,
                    "rate_pct":       f"{rate*100:.0f}%",
                    "analysis":       a_name,
                    "metric":         m_name,
                    "baseline_mean":  ev.baseline_mean,
                    "mean":           ev.mean,
                    "std":            ev.std,
                    "ci_lower":       ev.ci_lower,
                    "ci_upper":       ev.ci_upper,
                    "effect_size":    ev.effect_size,
                    "effect_label":   _effect_label(ev.effect_size),
                })
        self._write_csv(
            rows,
            ["rate", "rate_pct", "analysis", "metric", "baseline_mean",
             "mean", "std", "ci_lower", "ci_upper", "effect_size", "effect_label"],
            self.output_dir / "combined_results.csv",
        )

    def _write_combined_statistics(self) -> None:
        """Write combined_statistics.csv — sensitivity ranking with threshold info."""
        rows = []
        for s in self._sensitivity.summaries:
            rows.append({
                "rank":            s.rank,
                "metric":          s.metric_key,
                "max_effect_size": s.max_effect_size,
                "effect_label":    s.effect_label,
                "threshold_rate":  s.threshold_rate if s.threshold_rate is not None else "",
                "is_sensitive":    s.is_sensitive,
            })
        self._write_csv(
            rows,
            ["rank", "metric", "max_effect_size", "effect_label",
             "threshold_rate", "is_sensitive"],
            self.output_dir / "combined_statistics.csv",
        )

    # ------------------------------------------------------------------ #
    # HTML                                                                 #
    # ------------------------------------------------------------------ #

    def _render_trend_report(self, plot_groups: Dict[str, List[str]]) -> None:
        rates     = self._trend.rates
        rate_pcts = [f"{r*100:.0f}" for r in rates]

        all_effects = [s.max_effect_size for s in self._sensitivity.summaries]
        n_sensitive = sum(1 for s in self._sensitivity.summaries if s.is_sensitive)
        max_d       = f"{max(all_effects):.4f}" if all_effects else "0.0000"
        top_metric  = self._sensitivity.summaries[0].metric_key if self._sensitivity.summaries else "—"

        # Effect table rows (metric × rate)
        all_keys = [s.metric_key for s in self._sensitivity.summaries]
        effect_table_rows = []
        for key in all_keys:
            cells = []
            for rate in rates:
                ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                val  = f"{ev.effect_size:.3f}" if ev else "—"
                lab  = _effect_label(ev.effect_size) if ev else "Negligible"
                cells.append({"value": val, "label": lab})
            effect_table_rows.append({"metric": key, "cells": cells})

        # Sensitivity table rows
        sensitivity_rows = []
        for s in self._sensitivity.summaries:
            sensitivity_rows.append({
                "rank":            s.rank,
                "metric_key":      s.metric_key,
                "max_effect_size": s.max_effect_size,
                "effect_label":    s.effect_label,
                "threshold_rate":  s.threshold_rate,
                "is_sensitive":    s.is_sensitive,
            })

        # Plot lists
        def _to_plot_list(filenames: List[str], prefix: str = "") -> List[Dict]:
            return [{"filename": f,
                     "label": f.replace(".png", "").replace("_", " ").replace(prefix, "").strip()}
                    for f in filenames]

        root_path = self._rel_root(self.output_dir, self._root)

        self._render_template(
            "trend_report.html",
            {
                "dataset_name":        self._dataset,
                "error_model_slug":    self._em_slug,
                "error_model_display": self._em_display,
                "rates":               [f"{r*100:.0f}" for r in rates],
                "n_metrics":           len(all_keys),
                "n_sensitive":         n_sensitive,
                "max_effect_size":     max_d,
                "top_metric":          top_metric,
                "sensitivity_rows":    sensitivity_rows,
                "effect_table_rows":   effect_table_rows,
                "heatmap_plots":       _to_plot_list(plot_groups.get("heatmaps", [])),
                "global_summary_plots": _to_plot_list(plot_groups.get("global_summaries", [])),
                "ranking_plots":       _to_plot_list(plot_groups.get("rankings", [])),
                "metric_trend_plots":  _to_plot_list(plot_groups.get("metric_trends", []), "trend "),
                "root_path":           root_path,
            },
            self.output_dir / "trend_report.html",
        )
