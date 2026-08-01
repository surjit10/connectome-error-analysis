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
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from modules.reporting.trend_analysis import TrendAnalysisResult
from modules.reporting.sensitivity_analysis import SensitivityResult
from presentation.base_exporter import BaseExporter
from presentation.trend_plotter import TrendPlotter
from presentation.preservation_config import (
    calculate_preservation,
    get_biological_status,
    is_preservation_metric,
    higher_is_better,
    KEY_INTEGRITY_METRICS,
)

logger = logging.getLogger(__name__)


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
    # Preservation helpers                                                 #
    # ------------------------------------------------------------------ #

    def _preservation_for_rate(self, rate: float, key: str) -> float:
        """Compute preservation for one metric at one error rate."""
        if not is_preservation_metric(key):
            return 100.0
        ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
        if ev is None:
            return 100.0
        return calculate_preservation(
            ev.baseline_mean, ev.mean,
            higher_is_better=higher_is_better(key),
        )

    # ------------------------------------------------------------------ #
    # CSVs                                                                 #
    # ------------------------------------------------------------------ #

    def _write_combined_results(self) -> None:
        """Write combined_results.csv — all metrics × all rates."""
        rows = []
        for rate in self._trend.rates:
            for key, ev in self._trend.metrics_by_rate.get(rate, {}).items():
                a_name, _, m_name = key.partition(".")
                preservation = self._preservation_for_rate(rate, key)
                _, bio_label, _ = get_biological_status(preservation)
                rows.append({
                    "rate":           rate,
                    "rate_pct":       f"{rate*100:g}%",
                    "analysis":       a_name,
                    "metric":         m_name,
                    "baseline_mean":  ev.baseline_mean,
                    "mean":           ev.mean,
                    "std":            ev.std,
                    "ci_lower":       ev.ci_lower,
                    "ci_upper":       ev.ci_upper,
                    "preservation_pct": round(preservation, 4),
                    "biological_status": bio_label,
                })
        self._write_csv(
            rows,
            ["rate", "rate_pct", "analysis", "metric", "baseline_mean",
             "mean", "std", "ci_lower", "ci_upper", "preservation_pct",
             "biological_status"],
            self.output_dir / "combined_results.csv",
        )

    def _write_combined_statistics(self) -> None:
        """Write combined_statistics.csv — preservation ranking."""
        # Rank metrics by worst (minimum) preservation across all rates
        rows = []
        ranking = self._compute_preservation_ranking()
        for rank, (key, min_preservation) in enumerate(ranking, start=1):
            _, bio_label, _ = get_biological_status(min_preservation)
            rows.append({
                "rank":              rank,
                "metric":            key,
                "min_preservation":  round(min_preservation, 4),
                "biological_status": bio_label,
            })
        self._write_csv(
            rows,
            ["rank", "metric", "min_preservation", "biological_status"],
            self.output_dir / "combined_statistics.csv",
        )

    # ------------------------------------------------------------------ #
    # HTML                                                                 #
    # ------------------------------------------------------------------ #

    def _compute_preservation_ranking(self) -> List[Tuple[str, float]]:
        """Rank preservation metrics by minimum preservation (worst first).

        Only includes metrics classified as 'preservation' type.
        """
        all_keys = set()
        for m_dict in self._trend.metrics_by_rate.values():
            all_keys.update(m_dict.keys())

        ranking: List[Tuple[str, float]] = []
        for key in sorted(all_keys):
            if not is_preservation_metric(key):
                continue
            preservations = []
            for rate in self._trend.rates:
                ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                if ev is not None:
                    pres = calculate_preservation(
                        ev.baseline_mean, ev.mean,
                        higher_is_better=higher_is_better(key),
                    )
                    preservations.append(pres)
            if preservations:
                ranking.append((key, min(preservations)))
        ranking.sort(key=lambda x: x[1])
        return ranking

    def _render_trend_report(self, plot_groups: Dict[str, List[str]]) -> None:
        rates     = self._trend.rates
        rate_pcts = [f"{r*100:g}" for r in rates]

        ranking = self._compute_preservation_ranking()
        all_preservations = [p for _, p in ranking]
        min_preservation = f"{min(all_preservations):.4f}%" if all_preservations else "100.0000%"
        avg_preservation = f"{sum(all_preservations)/len(all_preservations):.4f}%" if all_preservations else "100.0000%"
        worst_metric = ranking[0][0] if ranking else "—"

        # Preservation table rows (metric × rate)
        all_keys = [k for k, _ in ranking]
        preservation_table_rows = []
        for key in all_keys:
            cells = []
            for rate in rates:
                pres = self._preservation_for_rate(rate, key)
                _, bio_label, _ = get_biological_status(pres)
                cells.append({"value": f"{pres:.4f}%", "label": bio_label})
            preservation_table_rows.append({"metric": key, "cells": cells})

        # Preservation ranking table rows
        sensitivity_rows = []
        for rank, (key, min_pres) in enumerate(ranking, start=1):
            _, bio_label, bio_css = get_biological_status(min_pres)
            sensitivity_rows.append({
                "rank":            rank,
                "metric_key":      key,
                "min_preservation": f"{min_pres:.4f}%",
                "biological_status": bio_label,
                "bio_css":         bio_css,
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
                "rates":               [f"{r*100:g}" for r in rates],
                "n_metrics":           len(all_keys),
                "min_preservation":    min_preservation,
                "avg_preservation":    avg_preservation,
                "worst_metric":        worst_metric,
                "sensitivity_rows":    sensitivity_rows,
                "preservation_table_rows": preservation_table_rows,
                "heatmap_plots":       _to_plot_list(plot_groups.get("heatmaps", [])),
                "global_summary_plots": _to_plot_list(plot_groups.get("global_summaries", [])),
                "ranking_plots":       _to_plot_list(plot_groups.get("rankings", [])),
                "metric_trend_plots":  _to_plot_list(plot_groups.get("metric_trends", []), "trend "),
                "root_path":           root_path,
            },
            self.output_dir / "trend_report.html",
        )
