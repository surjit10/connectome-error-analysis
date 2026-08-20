"""
Compare Existing Runner
=======================
Lightweight comparison runner that matches existing Real replicate observations
against Null replicate observations without loading or perturbing the connectome graph.
Computes Welch's independent t-test, Cohen's d, and Benjamini-Hochberg FDR correction.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import HypothesisExperimentConfig
from ..analysis.secondary_effects import SecondaryEffectRecord
from ..comparison.metric_comparison import (
    MetricComparisonResult,
    MetricComparator,
)
from ..comparison.hypothesis_tests import (
    HypothesisTestResult,
    HypothesisTestEngine,
)
from ..export.hypothesis_exporter import HypothesisExporter
from ..loaders.existing_real_results_loader import ExistingRealResultsLoader

logger = logging.getLogger(__name__)


class CompareExistingRunner:
    """Orchestrates statistical comparison between pre-existing Real and Null experiment observations."""

    def __init__(self) -> None:
        self._comparator = MetricComparator()
        self._test_engine = HypothesisTestEngine()
        self._loader = ExistingRealResultsLoader()

    def run(
        self,
        config: HypothesisExperimentConfig,
        real_records: Optional[List[SecondaryEffectRecord]] = None,
        null_records: Optional[List[SecondaryEffectRecord]] = None,
    ) -> Any:
        """Execute lightweight statistical comparison across existing Real and Null observations.

        Args:
            config: HypothesisExperimentConfig instance.
            real_records: Optional pre-loaded list of Real SecondaryEffectRecord objects.
                If None, loaded from config.real_results_path.
            null_records: Optional pre-loaded list of Null SecondaryEffectRecord objects.
                If None, loaded from config.null_results_path.

        Returns:
            HypothesisRunnerResult with comparison results, FDR adjustments, and export paths.
        """
        # Import dynamically to avoid circular import
        from .hypothesis_experiment_runner import HypothesisRunnerResult

        t_start = time.perf_counter()
        logger.info(
            f"[CompareExistingRunner] Starting comparison for dataset '{config.dataset_name}'."
        )

        runner_result = HypothesisRunnerResult(
            dataset_name=config.dataset_name,
            null_model_name=config.null_model_name,
        )

        try:
            # 1. Load Real records if not provided
            if real_records is None:
                if not config.real_results_path:
                    raise ValueError(
                        "[CompareExistingRunner] No real_records provided and config.real_results_path is not set."
                    )
                real_records = self._loader.load(
                    source_path=config.real_results_path,
                    dataset_name=config.dataset_name,
                    error_models=config.error_model_names,
                    error_rates=config.error_rates,
                )

            # 2. Load Null records if not provided
            if null_records is None:
                if not config.null_results_path:
                    raise ValueError(
                        "[CompareExistingRunner] No null_records provided and config.null_results_path is not set."
                    )
                null_records = self._loader.load(
                    source_path=config.null_results_path,
                    dataset_name=config.dataset_name,
                    error_models=config.error_model_names,
                    error_rates=config.error_rates,
                )

            logger.info(
                f"[CompareExistingRunner] Comparing {len(real_records)} Real records against "
                f"{len(null_records)} Null records."
            )

            all_records = real_records + null_records
            runner_result.secondary_records = all_records

            # 3. Group and index records
            real_grouped: Dict[Tuple[str, float, str, str], List[float]] = {}
            metric_cats: Dict[Tuple[str, str], str] = {}
            for r in real_records:
                key = (r.error_model, r.error_rate, r.analysis_name, r.metric_name)
                real_grouped.setdefault(key, []).append(r.relative_change)
                metric_cats[(r.error_model, r.metric_name)] = r.category

            null_grouped: Dict[Tuple[str, float, str, str], List[float]] = {}
            for r in null_records:
                key = (r.error_model, r.error_rate, r.analysis_name, r.metric_name)
                null_grouped.setdefault(key, []).append(r.relative_change)

            # 4. Compare matching groups using independent Welch's t-test
            comparisons: List[MetricComparisonResult] = []
            all_keys = sorted(real_grouped.keys() | null_grouped.keys())

            for em_name, rate, a_name, m_name in all_keys:
                r_list = real_grouped.get((em_name, rate, a_name, m_name), [])
                n_list = null_grouped.get((em_name, rate, a_name, m_name), [])
                cat = metric_cats.get((em_name, m_name), "secondary_emergent")

                comp = self._comparator.compare(
                    dataset=config.dataset_name,
                    error_model=em_name,
                    error_rate=rate,
                    analysis_name=a_name,
                    metric_name=m_name,
                    category=cat,
                    real_effects=r_list,
                    null_effects=n_list,
                    paired=False,  # Always independent
                )
                comparisons.append(comp)

            runner_result.comparison_results = comparisons

            # 5. Multiple testing FDR adjustment
            self._test_engine.alpha = config.significance_level
            test_results = self._test_engine.evaluate_suite(comparisons)
            runner_result.test_results = test_results

            # 6. Export comparison tables and markdown summary
            exporter = HypothesisExporter(output_root=config.output_root)
            exported = exporter.export(
                dataset=config.dataset_name,
                null_model_name=config.null_model_name,
                secondary_records=all_records,
                test_results=test_results,
                extra_metadata={
                    "error_models": config.error_model_names,
                    "error_rates": config.error_rates,
                    "execution_mode": "compare_existing",
                },
            )
            runner_result.exported_paths = exported

        except Exception as exc:
            logger.exception(f"[CompareExistingRunner] Comparison failure: {exc}")
            runner_result.status = "FAILED"
            runner_result.errors.append(str(exc))

        runner_result.runtime_seconds = time.perf_counter() - t_start
        logger.info(
            f"[CompareExistingRunner] Completed in {runner_result.runtime_seconds:.4f}s "
            f"(Status: {runner_result.status})."
        )
        return runner_result
