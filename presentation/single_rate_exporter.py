"""
presentation/single_rate_exporter.py
======================================
Exports everything for **one error-rate experiment** into:

    error_{x}/
        report.html
        summary.csv
        data/
            metrics.json
            metadata.json
        plots/
            distributions/
            structure/

Design constraints:
    - No statistical computation.
    - No figure generation (delegates to SingleRatePlotter).
    - Only file I/O, CSV/JSON writing, and HTML rendering.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modules.statistical_evaluation.evaluator import (
    MetricEvaluation,
    StatisticalEvaluationResult,
)
from modules.reporting.sensitivity_analysis import SensitivityResult
from presentation.base_exporter import BaseExporter
from presentation.single_rate_plotter import SingleRatePlotter

logger = logging.getLogger(__name__)


def _effect_label(d: float) -> str:
    a = abs(d)
    if a < 0.2:
        return "Negligible"
    if a < 0.5:
        return "Small"
    if a < 0.8:
        return "Medium"
    return "Large"


def _pct_change(mean: float, baseline: float) -> Tuple[str, str]:
    """Return (formatted_pct_string, sign_char)."""
    if baseline == 0 or not math.isfinite(baseline) or not math.isfinite(mean):
        return "—", "="
    delta = (mean - baseline) / abs(baseline) * 100
    sign  = "+" if delta >= 0 else ""
    return f"{sign}{delta:.2f}%", ("+" if delta >= 0 else "-")


class SingleRateExporter(BaseExporter):
    """Export results for one error-rate experiment.

    Args:
        output_dir:        The ``error_x/`` directory for this experiment.
        result:            Statistical result for this rate.
        error_model_slug:  Slug of the error model (e.g. ``"missed_synapses"``).
        error_model_display: Human-readable name.
        dataset_name:      Dataset name (e.g. ``"BANC"``).
        results_root:      ``results/`` root used to compute relative paths.
        sorted_rates:      All error rates in order (for prev/next navigation).
    """

    def __init__(
        self,
        output_dir:          Path,
        result:              StatisticalEvaluationResult,
        error_model_slug:    str,
        error_model_display: str,
        dataset_name:        str,
        results_root:        Path,
        sorted_rates:        List[float],
    ) -> None:
        super().__init__(output_dir)
        self._result      = result
        self._em_slug     = error_model_slug
        self._em_display  = error_model_display
        self._dataset     = dataset_name
        self._root        = results_root
        self._all_rates   = sorted_rates

    def export(self) -> None:
        """Run the full single-rate export pipeline."""
        rate    = self._result.error_level
        rate_pct = f"{rate*100:.0f}"
        logger.info("[SingleRateExporter] Exporting error_%s%%", rate_pct)

        self._ensure_dirs(
            self.output_dir,
            self.output_dir / "data",
            self.output_dir / "plots" / "distributions",
            self.output_dir / "plots" / "structure",
        )

        # 1. CSV — summary.csv
        self._write_summary_csv(rate_pct)

        # 2. JSON — data/metrics.json, data/metadata.json
        self._write_metrics_json()
        self._write_metadata_json(rate_pct)

        # 3. Plots
        plotter = SingleRatePlotter(
            metrics    = self._result.metrics,
            output_dir = self.output_dir / "plots",
            error_rate = rate,
        )
        dist_files, struct_files = plotter.generate_all()

        # 4. HTML report
        self._render_report(rate_pct, dist_files, struct_files)

    # ------------------------------------------------------------------ #
    # CSV                                                                  #
    # ------------------------------------------------------------------ #

    def _write_summary_csv(self, rate_pct: str) -> None:
        rows = []
        for a_name, m_dict in self._result.metrics.items():
            for m_name, ev in m_dict.items():
                rows.append({
                    "rate": rate_pct,
                    "analysis": a_name,
                    "metric": m_name,
                    "baseline_mean": ev.baseline_mean,
                    "mean": ev.mean,
                    "std": ev.std,
                    "ci_lower": ev.ci_lower,
                    "ci_upper": ev.ci_upper,
                    "effect_size": ev.effect_size,
                })
        self._write_csv(
            rows,
            ["rate", "analysis", "metric", "baseline_mean", "mean",
             "std", "ci_lower", "ci_upper", "effect_size"],
            self.output_dir / "summary.csv",
        )

    # ------------------------------------------------------------------ #
    # JSON                                                                 #
    # ------------------------------------------------------------------ #

    def _write_metrics_json(self) -> None:
        data = {}
        for a_name, m_dict in self._result.metrics.items():
            data[a_name] = {}
            for m_name, ev in m_dict.items():
                data[a_name][m_name] = {
                    "baseline_mean":  ev.baseline_mean,
                    "mean":           ev.mean,
                    "std":            ev.std,
                    "ci_lower":       ev.ci_lower,
                    "ci_upper":       ev.ci_upper,
                    "effect_size":    ev.effect_size,
                    "effect_label":   _effect_label(ev.effect_size),
                }
        self._write_json(data, self.output_dir / "data" / "metrics.json")

    def _write_metadata_json(self, rate_pct: str) -> None:
        meta = {
            "dataset_name":    self._dataset,
            "error_model":     self._em_slug,
            "error_rate_pct":  rate_pct,
            "n_trials":        self._result.n_trials,
            "runtime_seconds": self._result.runtime_seconds,
        }
        self._write_json(meta, self.output_dir / "data" / "metadata.json")

    # ------------------------------------------------------------------ #
    # HTML                                                                 #
    # ------------------------------------------------------------------ #

    def _render_report(
        self,
        rate_pct:     str,
        dist_files:   List[str],
        struct_files: List[str],
    ) -> None:
        metrics = self._result.metrics
        rate    = self._result.error_level

        # Build metrics table rows
        metric_rows = []
        for a_name, m_dict in metrics.items():
            for m_name, ev in m_dict.items():
                delta_pct, delta_sign = _pct_change(ev.mean, ev.baseline_mean)
                metric_rows.append({
                    "analysis":    a_name,
                    "metric":      m_name,
                    "baseline_mean": f"{ev.baseline_mean:.6g}",
                    "mean":          f"{ev.mean:.6g}",
                    "std":           f"{ev.std:.6g}",
                    "ci_lower":      f"{ev.ci_lower:.6g}",
                    "ci_upper":      f"{ev.ci_upper:.6g}",
                    "effect_size":   f"{ev.effect_size:.4f}",
                    "effect_label":  _effect_label(ev.effect_size),
                    "delta_pct":     delta_pct,
                    "delta_sign":    delta_sign,
                })

        all_effects = [abs(ev.effect_size) for m_d in metrics.values() for ev in m_d.values()]
        n_sensitive = sum(1 for e in all_effects if e >= 0.8)
        max_d       = f"{max(all_effects):.4f}" if all_effects else "0.0000"
        top_key     = metric_rows[
            all_effects.index(max(all_effects))
        ]["metric"] if all_effects else "—"
        avg_d = f"{sum(all_effects)/len(all_effects):.4f}" if all_effects else "0.0000"

        # Prev / next navigation
        idx       = self._all_rates.index(rate) if rate in self._all_rates else -1
        prev_url  = None
        next_url  = None
        if idx > 0:
            prev_rate = self._all_rates[idx - 1]
            prev_url  = f"../error_{prev_rate*100:.0f}/report.html"
        if idx < len(self._all_rates) - 1:
            next_rate = self._all_rates[idx + 1]
            next_url  = f"../error_{next_rate*100:.0f}/report.html"

        root_path = self._rel_root(self.output_dir, self._root)

        self._render_template(
            "single_rate_report.html",
            {
                "dataset_name":      self._dataset,
                "error_model_slug":  self._em_slug,
                "error_model_display": self._em_display,
                "error_rate_pct":    rate_pct,
                "n_trials":          self._result.n_trials,
                "n_metrics":         len(metric_rows),
                "n_sensitive":       n_sensitive,
                "max_effect_size":   max_d,
                "avg_effect_size":   avg_d,
                "top_metric":        top_key,
                "metric_rows":       metric_rows,
                "dist_plots":        [{"filename": f, "label": f.replace(".png","").replace("distribution_","")} for f in dist_files],
                "struct_plots":      [{"filename": f, "label": f.replace(".png","")} for f in struct_files],
                "prev_rate_url":     prev_url,
                "next_rate_url":     next_url,
                "root_path":         root_path,
            },
            self.output_dir / "report.html",
        )
