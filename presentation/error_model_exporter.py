"""
presentation/error_model_exporter.py
=======================================
Orchestrates all exports for one complete error model
(one entry in ``results/{error_model}/``).

Responsibilities:
    - Invoke DatasetExporter for each dataset.
    - Scaffold cross_dataset_analysis/ directory.
    - Render overview.html.

Design constraints:
    - No statistical computation.
    - No figure generation.
    - Pure orchestration and HTML rendering.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from modules.reporting.trend_analysis import TrendAnalysisResult
from modules.reporting.sensitivity_analysis import SensitivityResult
from presentation.base_exporter import BaseExporter
from presentation.dataset_exporter import DatasetExporter, _rate_label

logger = logging.getLogger(__name__)


class ErrorModelExporter(BaseExporter):
    """Export one complete error model.

    Args:
        output_dir:          Root for the error model (e.g. ``results/missed_synapses/``).
        error_model_slug:    URL-safe slug.
        error_model_display: Human-readable name.
        description:         Short description of the error model.
        results_root:        ``results/`` root.
    """

    def __init__(
        self,
        output_dir:          Path,
        error_model_slug:    str,
        error_model_display: str,
        description:         str,
        results_root:        Path,
    ) -> None:
        super().__init__(output_dir)
        self._em_slug    = error_model_slug
        self._em_display = error_model_display
        self._description = description
        self._root       = results_root

        # Registered datasets (populated via add_dataset)
        self._datasets: List[Dict] = []

    def add_dataset(
        self,
        dataset_name:    str,
        results_by_rate: Dict[float, StatisticalEvaluationResult],
        trend:           TrendAnalysisResult,
        sensitivity:     SensitivityResult,
    ) -> None:
        """Register a dataset to be exported.

        Call this once per dataset before calling :meth:`export`.
        """
        self._datasets.append({
            "name":           dataset_name,
            "results":        results_by_rate,
            "trend":          trend,
            "sensitivity":    sensitivity,
        })

    def export(self) -> None:
        """Run the complete error model export pipeline."""
        self._ensure_dirs(
            self.output_dir,
            self.output_dir / "cross_dataset_analysis",
        )

        ds_info_for_overview = []

        for ds in self._datasets:
            dataset_name    = ds["name"]
            results_by_rate = ds["results"]
            trend           = ds["trend"]
            sensitivity     = ds["sensitivity"]

            dataset_dir = self.output_dir / dataset_name
            DatasetExporter(
                output_dir          = dataset_dir,
                results_by_rate     = results_by_rate,
                trend               = trend,
                sensitivity         = sensitivity,
                error_model_slug    = self._em_slug,
                error_model_display = self._em_display,
                dataset_name        = dataset_name,
                results_root        = self._root,
            ).export()

            sorted_rates = sorted(results_by_rate.keys())
            ds_info_for_overview.append({
                "name":    dataset_name,
                "n_rates": len(sorted_rates),
                "n_trials": sum(r.n_trials for r in results_by_rate.values()),
                "rates":   [
                    {
                        "label":   _rate_label(r),
                        "n_trials": results_by_rate[r].n_trials,
                    }
                    for r in sorted_rates
                ],
            })

        self._render_overview(ds_info_for_overview)

    # ------------------------------------------------------------------ #
    # HTML                                                                 #
    # ------------------------------------------------------------------ #

    def _render_overview(self, ds_info: List[Dict]) -> None:
        total_rates  = sum(d["n_rates"]  for d in ds_info)
        total_trials = sum(d["n_trials"] for d in ds_info)
        root_path    = self._rel_root(self.output_dir, self._root)

        self._render_template(
            "error_model_overview.html",
            {
                "error_model_slug":    self._em_slug,
                "error_model_display": self._em_display,
                "description":         self._description,
                "datasets":            ds_info,
                "total_rates":         total_rates,
                "total_trials":        total_trials,
                "root_path":           root_path,
            },
            self.output_dir / "overview.html",
        )
