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
    is_preservation_metric,
    higher_is_better,
    METRIC_CATEGORIES,
    METRIC_DISPLAY_NAMES,
    error_model_summary,
)
from presentation.model_summary import (
    build_network_similarity,
    build_reliability,
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
        """Build per-rate info (label + trial count) for the summary page."""
        rates_info = []
        for rate in sorted_rates:
            res    = self._results[rate]
            label  = _rate_label(rate)
            rates_info.append({
                "label":    label,
                "n_trials": res.n_trials,
            })
        return rates_info

    def _build_preservation_matrix(self, sorted_rates: List[float]) -> List[Dict]:
        """Full preservation response per metric across every tested error rate.

        Purely numerical — no status labels, no threshold classifications.
        Groups metrics by biological family so reviewers can observe
        monotonic / non-monotonic / recovery behaviour across perturbation
        levels directly from the table.
        """
        groups: List[Dict] = []
        for category, keys in METRIC_CATEGORIES.items():
            rows = []
            for key in keys:
                # Only preservation-type metrics belong in a preservation
                # matrix.  "change" metrics (e.g. wcc_count, scc_count) are
                # structural reorganisation indicators reported with delta%
                # in the per-rate reports, not with a preservation score.
                if not is_preservation_metric(key):
                    continue
                cells = []
                found = False
                for rate in sorted_rates:
                    ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                    # Emit a "—" placeholder for missing rates so every row
                    # aligns with the header row (same column count).
                    if ev is None:
                        cells.append({
                            "rate_pct": f"{rate*100:g}",
                            "value":    "—",
                            "value_num": None,
                        })
                        continue
                    found = True
                    pres = calculate_preservation(
                        ev.baseline_mean, ev.mean,
                        higher_is_better=higher_is_better(key),
                    )
                    cells.append({
                        "rate_pct": f"{rate*100:g}",
                        "value":    f"{pres:.4f}%",
                        "value_num": pres,
                    })
                # Skip metrics that were never measured for this model so no
                # phantom all-"—" rows appear (only placeholder gaps within
                # an otherwise measured metric are shown).
                if found:
                    rows.append({
                        "metric_key": key,
                        "display":    METRIC_DISPLAY_NAMES.get(key, key.split(".")[-1]),
                        "cells":      cells,
                    })
            if rows:
                groups.append({"category": category, "rows": rows})
        return groups

    def _build_category_matrix(self, sorted_rates: List[float]) -> List[Dict]:
        """Mean preservation per biological family across every tested error rate.

        Numerical only — no "Highly Preserved" / "Mostly Preserved" labels.
        """
        out: List[Dict] = []
        for category, keys in METRIC_CATEGORIES.items():
            cells = []
            found = False
            for rate in sorted_rates:
                vals = []
                for key in keys:
                    ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                    if ev is None:
                        continue
                    if not is_preservation_metric(key):
                        continue
                    vals.append(calculate_preservation(
                        ev.baseline_mean, ev.mean,
                        higher_is_better=higher_is_better(key),
                    ))

                if vals:
                    found = True
                    cells.append({
                        "rate_pct": f"{rate*100:g}",
                        "value":    f"{sum(vals)/len(vals):.4f}%",
                        "value_num": sum(vals)/len(vals),
                    })
                else:
                    # Align with the header row even when a family has no
                    # measured metric at this rate.
                    cells.append({
                        "rate_pct": f"{rate*100:g}",
                        "value":    "—",
                        "value_num": None,
                    })
            # Skip families with no measured metrics at any rate so no phantom
            # all-"—" rows appear (same guard as _build_preservation_matrix).
            if found:
                out.append({"category": category, "cells": cells})
        return out

    def render_summary(self) -> None:
        """Re-render just the dataset summary.html (used after comparison export)."""
        self._render_summary(sorted(self._results.keys()))

    def _render_summary(self, sorted_rates: List[float]) -> None:
        n_metrics    = len(self._sensitivity.summaries)
        total_trials = sum(r.n_trials for r in self._results.values())
        rates_info   = self._compute_rates_info(sorted_rates)

        # ── Purely numerical data-driven tables (no verdicts, no statuses) ─
        preservation_matrix = self._build_preservation_matrix(sorted_rates)
        category_matrix     = self._build_category_matrix(sorted_rates)
        network_similarity  = build_network_similarity(self._trend)
        reliability_rows    = build_reliability(self._trend)

        # Overall preservation per rate (average across preservation metrics)
        overall_by_rate = []
        for rate in sorted_rates:
            pres_list = []
            for key, ev in self._trend.metrics_by_rate.get(rate, {}).items():
                if not is_preservation_metric(key):
                    continue
                pres_list.append(calculate_preservation(
                    ev.baseline_mean, ev.mean,
                    higher_is_better=higher_is_better(key),
                ))
            if pres_list:
                overall_by_rate.append({
                    "rate_pct":  f"{rate*100:g}",
                    "value":     f"{sum(pres_list)/len(pres_list):.2f}%",
                    "value_num": sum(pres_list)/len(pres_list),
                })

        em_summary = error_model_summary(self._em_slug)

        # Only show the comparison link when the comparison page exists (it is
        # generated separately by ComparisonExporter, e.g. from the regen
        # script, so it may be absent on a single-model notebook run).
        has_comparison = (
            self.output_dir.parent / "comparison" / "index.html"
        ).exists()

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
                "rates":               rates_info,
                # Purely numerical data-driven tables
                "preservation_matrix": preservation_matrix,
                "category_matrix":     category_matrix,
                "network_similarity":  network_similarity,
                "reliability_rows":    reliability_rows,
                "overall_by_rate":     overall_by_rate,
                "em_summary":          em_summary,
                "has_comparison":      has_comparison,
                "root_path":           root_path,
            },
            self.output_dir / "summary.html",
        )
