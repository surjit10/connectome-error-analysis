"""
presentation/comparison_exporter.py
====================================
Generates a cross-error-model comparison report for one dataset:

    results/<dataset>/comparison/index.html

Compares Missed Synapses, False Synapses and Synapse Count Measurement on:

    - Overall Biological Preservation Score
    - Most sensitive metric (lowest min preservation)
    - Most stable metric (highest min preservation)
    - Biological verdict
    - Key findings

Design constraints:
    - **No statistical computation.**  Every value is read from the already
      exported ``trend_analysis/combined_results.csv`` /
      ``combined_statistics.csv`` files produced by the TrendExporter, or
      computed from them by simple averaging of already-stored preservation
      percentages (identical to how DatasetExporter derives the overall score).
    - No plotting.
    - Pure file I/O and HTML rendering.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from presentation.base_exporter import BaseExporter
from presentation.preservation_config import error_model_summary

logger = logging.getLogger(__name__)


class ComparisonExporter(BaseExporter):
    """Generate the cross-error-model comparison page for one dataset.

    Args:
        output_dir:   The ``comparison/`` directory (e.g. ``results/BANC/comparison/``).
        dataset_name: Dataset name (e.g. ``"BANC"``).
        results_root: The dataset root that contains the error-model folders
                      (e.g. ``results/BANC/``).
        model_slugs:  Ordered list of error-model slugs to compare.
    """

    def __init__(
        self,
        output_dir: Path,
        dataset_name: str,
        results_root: Path,
        model_slugs: List[str],
    ) -> None:
        super().__init__(output_dir)
        self._dataset = dataset_name
        self._root    = results_root
        self._slugs   = model_slugs

    # ------------------------------------------------------------------ #
    # Data reading (existing outputs only)                                #
    # ------------------------------------------------------------------ #

    def _read_ranking(self, slug: str) -> List[Dict[str, Any]]:
        """Read ``combined_statistics.csv`` → sorted preservation ranking."""
        path = self._root / slug / "trend_analysis" / "combined_statistics.csv"
        if not path.exists():
            return []
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        return rows

    # ------------------------------------------------------------------ #
    # Model summary                                                        #
    # ------------------------------------------------------------------ #

    def _summarize_model(self, slug: str, display: str) -> Optional[Dict[str, Any]]:
        ranking = self._read_ranking(slug)
        if not ranking:
            return None

        em_summary = error_model_summary(slug)

        return {
            "slug":        slug,
            "display":     display,
            "description": em_summary["biological_effect"],
            "n_metrics":   len(ranking),
        }

    # ------------------------------------------------------------------ #
    # Export                                                               #
    # ------------------------------------------------------------------ #

    def export(self) -> None:
        """Run the comparison export."""
        self._ensure_dirs(self.output_dir)

        models = []
        for slug in self._slugs:
            summary = self._summarize_model(
                slug, slug.replace("_", " ").title(),
            )
            if summary is not None:
                models.append(summary)

        if not models:
            logger.info("[ComparisonExporter] No models with data — skipping comparison page.")
            return

        root_path = self._rel_root(self.output_dir, self._root)

        self._render_template(
            "comparison_report.html",
            {
                "dataset_name": self._dataset,
                "models":       models,
                "root_path":    root_path,
            },
            self.output_dir / "index.html",
        )
        logger.info("[ComparisonExporter] Rendered comparison page (%d models).", len(models))
