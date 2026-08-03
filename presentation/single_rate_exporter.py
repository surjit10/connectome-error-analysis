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
from presentation.base_exporter import BaseExporter
from presentation.single_rate_plotter import SingleRatePlotter
from presentation.preservation_config import (
    get_metric_type,
    calculate_preservation,
    get_biological_status,
    get_integrity_verdict,
    generate_biological_assessment,
    is_preservation_metric,
    is_change_metric,
    higher_is_better,
    KEY_INTEGRITY_METRICS,
    METRIC_DISPLAY_NAMES,
    render_preservation_metric,
    render_change_metric,
    _pct_change,
    error_model_summary,
)

logger = logging.getLogger(__name__)


def _metric_label(key: str, default: str) -> str:
    """Return display name from METRIC_DISPLAY_NAMES or fall back to default."""
    return METRIC_DISPLAY_NAMES.get(key, default)


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
        from presentation.dataset_exporter import _rate_label
        rate    = self._result.error_level
        rate_pct = _rate_label(rate).replace("_", ".")
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
                key = f"{a_name}.{m_name}"
                row = {
                    "rate": rate_pct,
                    "analysis": a_name,
                    "metric": m_name,
                    "metric_type": get_metric_type(key),
                    "baseline_mean": ev.baseline_mean,
                    "mean": ev.mean,
                    "std": ev.std,
                    "ci_lower": ev.ci_lower,
                    "ci_upper": ev.ci_upper,
                    "change_pct": _pct_change(ev.mean, ev.baseline_mean)[0],
                }
                if is_preservation_metric(key):
                    pres = calculate_preservation(
                        ev.baseline_mean, ev.mean,
                        higher_is_better=higher_is_better(key),
                    )
                    row["preservation_pct"] = round(pres, 4)
                else:
                    row["preservation_pct"] = ""
                rows.append(row)
        self._write_csv(
            rows,
            ["rate", "analysis", "metric", "metric_type", "baseline_mean", "mean",
             "std", "ci_lower", "ci_upper", "preservation_pct", "change_pct"],
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
                key = f"{a_name}.{m_name}"
                entry: dict = {
                    "baseline_mean":  ev.baseline_mean,
                    "mean":           ev.mean,
                    "std":            ev.std,
                    "ci_lower":       ev.ci_lower,
                    "ci_upper":       ev.ci_upper,
                    "metric_type":    get_metric_type(key),
                }
                if is_preservation_metric(key):
                    pres = calculate_preservation(
                        ev.baseline_mean, ev.mean,
                        higher_is_better=higher_is_better(key),
                    )
                    _, bio_label, _ = get_biological_status(pres)
                    entry["preservation_pct"] = round(pres, 4)
                    entry["biological_status"] = bio_label
                else:
                    entry["preservation_pct"] = None
                    entry["biological_status"] = None
                data[a_name][m_name] = entry
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

    def _compute_metric_rows(self) -> Tuple[List[Dict], List[Dict]]:
        """Build metric table rows, separated into preservation and change lists.

        Returns:
            Tuple of ``(preservation_rows, change_rows)``.
        """
        pres_rows: List[Dict] = []
        chg_rows: List[Dict] = []
        for a_name, m_dict in self._result.metrics.items():
            for m_name, ev in m_dict.items():
                key = f"{a_name}.{m_name}"
                if is_preservation_metric(key):
                    pres_rows.append(render_preservation_metric(
                        key, a_name, m_name,
                        ev.baseline_mean, ev.mean,
                        ev.std, ev.ci_lower, ev.ci_upper,
                    ))
                elif is_change_metric(key):
                    chg_rows.append(render_change_metric(
                        key, a_name, m_name,
                        ev.baseline_mean, ev.mean,
                        ev.std, ev.ci_lower, ev.ci_upper,
                    ))
        return pres_rows, chg_rows

    def _compute_integrity(self, preservation_rows: List[Dict]) -> Tuple[float, List[Dict]]:
        """Compute overall network integrity score from key preservation metrics.

        Returns:
            Tuple of ``(integrity_score, key_metric_rows)``.
        """
        key_rows = [
            r for r in preservation_rows
            if f"{r['analysis']}.{r['metric']}" in KEY_INTEGRITY_METRICS
        ]
        if not key_rows:
            return 100.0, []
        integrity = sum(r["preservation_num"] for r in key_rows) / len(key_rows)
        return round(integrity, 4), key_rows

    def _render_report(
        self,
        rate_pct:     str,
        dist_files:   List[str],
        struct_files: List[str],
    ) -> None:
        rate    = self._result.error_level

        # Build metric rows (separated by type)
        preservation_rows, change_rows = self._compute_metric_rows()

        # Compute overall integrity (only from preservation metrics)
        integrity_score, key_metric_rows = self._compute_integrity(preservation_rows)
        integrity_emoji, integrity_verdict, integrity_css = get_integrity_verdict(integrity_score)

        # Collect per-metric preservation dict for assessment text
        preservation_dict: Dict[str, float] = {}
        for r in preservation_rows:
            key = f"{r['analysis']}.{r['metric']}"
            preservation_dict[key] = r["preservation_num"]

        assessment = generate_biological_assessment(integrity_score, preservation_dict)

        n_preservation = len(preservation_rows)
        n_change = len(change_rows)
        n_metrics = n_preservation + n_change

        from presentation.dataset_exporter import _rate_label

        # Prev / next navigation
        idx       = self._all_rates.index(rate) if rate in self._all_rates else -1
        prev_url  = None
        next_url  = None
        if idx > 0:
            prev_rate = self._all_rates[idx - 1]
            prev_url  = f"../error_{_rate_label(prev_rate)}/report.html"
        if idx < len(self._all_rates) - 1:
            next_rate = self._all_rates[idx + 1]
            next_url  = f"../error_{_rate_label(next_rate)}/report.html"

        root_path = self._rel_root(self.output_dir, self._root)

        self._render_template(
            "single_rate_report.html",
            {
                "dataset_name":        self._dataset,
                "error_model_slug":    self._em_slug,
                "error_model_display": self._em_display,
                "error_rate_pct":      rate_pct,
                "n_trials":            self._result.n_trials,
                "n_metrics":           n_metrics,
                "preservation_rows":   preservation_rows,
                "change_rows":         change_rows,
                "has_preservation":    n_preservation > 0,
                "has_change":          n_change > 0,
                # Verdict only — the aggregated score is no longer displayed.
                "integrity_emoji":     integrity_emoji,
                "integrity_verdict":   integrity_verdict,
                "integrity_css":       integrity_css,
                "biological_assessment": assessment,
                "em_summary":          error_model_summary(self._em_slug),
                "dist_plots":          [{"filename": f, "label": f.replace(".png","").replace("distribution_","")} for f in dist_files],
                "struct_plots":        [{"filename": f, "label": f.replace(".png","")} for f in struct_files],
                "prev_rate_url":       prev_url,
                "next_rate_url":       next_url,
                "root_path":           root_path,
            },
            self.output_dir / "report.html",
        )
