"""
presentation/presentation_export.py
=====================================
Thin backward-compatible façade over the new modular exporter architecture.

This class preserves the original ``PresentationExporter`` interface so that
any existing call sites continue to work without modification.  Internally it
delegates to the new :class:`~presentation.dataset_exporter.DatasetExporter`
and :class:`~presentation.root_index_exporter.RootIndexExporter`.

For new code, prefer instantiating the specialized exporters directly.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from modules.reporting.trend_analysis import TrendAnalysis
from modules.reporting.sensitivity_analysis import SensitivityAnalysis
from presentation.dataset_exporter import DatasetExporter
from presentation.root_index_exporter import RootIndexExporter

logger = logging.getLogger(__name__)


class PresentationExporter:
    """Backward-compatible façade over the new reporting pipeline.

    Original interface preserved::

        exporter = PresentationExporter(output_root, experiment_name, metadata)
        exporter.export(results_by_rate)

    Args:
        output_root:     Root output directory (legacy: ``results/BANC/...``).
        experiment_name: Experiment identifier string.
        metadata:        Free-form metadata dict.
    """

    def __init__(
        self,
        output_root:     Path,
        experiment_name: str,
        metadata:        Dict[str, Any],
    ) -> None:
        self.output_root     = Path(output_root)
        self.experiment_name = experiment_name
        self.metadata        = metadata or {}

    def export(self, results_by_rate: Dict[float, StatisticalEvaluationResult]) -> None:
        """Run the full export pipeline.

        Derives error-model and dataset names from *results_by_rate* and
        *metadata*, then delegates to :class:`DatasetExporter`.
        """
        if not results_by_rate:
            logger.warning("[PresentationExporter] No results to export.")
            return

        # Infer dataset name
        first_result = next(iter(results_by_rate.values()))
        dataset_name = first_result.dataset_name or self.metadata.get("dataset_name", "Unknown")

        # Infer error model slug from experiment_name (e.g. "MissedSynapses_BANC" → "missed_synapses")
        em_raw = self.metadata.get("error_model", "")
        if not em_raw:
            em_raw = self.experiment_name.lower().replace(
                f"_{dataset_name.lower()}", ""
            ).replace(" ", "_")
        error_model_slug    = em_raw.lower().replace(" ", "_")
        error_model_display = error_model_slug.replace("_", " ").title()

        # Target directory: results/{error_model_slug}/{dataset_name}/
        results_root = self.output_root
        dataset_dir  = results_root / error_model_slug / dataset_name

        # Run analysis
        trend = TrendAnalysis(
            results_by_rate  = results_by_rate,
            dataset_name     = dataset_name,
            error_model_name = error_model_slug,
        ).compute()

        sensitivity = SensitivityAnalysis(trend).compute()

        # Delegate to DatasetExporter
        DatasetExporter(
            output_dir          = dataset_dir,
            results_by_rate     = results_by_rate,
            trend               = trend,
            sensitivity         = sensitivity,
            error_model_slug    = error_model_slug,
            error_model_display = error_model_display,
            dataset_name        = dataset_name,
            results_root        = results_root,
        ).export()

        # Root index
        RootIndexExporter(results_root).export()

        logger.info(
            "[PresentationExporter] Export complete → %s",
            dataset_dir,
        )
