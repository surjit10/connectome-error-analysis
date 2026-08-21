"""
Hypothesis Experiment Runner
============================
Orchestrates Condition A (Real Connectome) and Condition B (Null Connectome)
perturbation experiments, extracting secondary structural effects and conducting
hypothesis testing without modifying frozen error models or existing runners.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import igraph

from core.data_loader import load_dataset, FlyWireDataset
from core.graph_builder import GraphBuilder
from core.experiment_runner import (
    ExperimentRunner,
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
)
from core.split_experiment_runner import SplitExperimentRunner
from core.merge_experiment_runner import MergeExperimentRunner
from modules.graph_analyses.analysis_registry import registry as analysis_registry
from modules.error_models.common.error_registry import registry as error_registry

from ..config import HypothesisExperimentConfig, Condition
from ..null_models.null_registry import registry as null_registry
from ..analysis.secondary_effects import (
    SecondaryEffectRecord,
    SecondaryEffectsExtractor,
)
from ..comparison.metric_comparison import (
    MetricComparisonResult,
    MetricComparator,
)
from ..comparison.hypothesis_tests import (
    HypothesisTestResult,
    HypothesisTestEngine,
)
from ..export.hypothesis_exporter import HypothesisExporter

logger = logging.getLogger(__name__)


class _DirectGraphBuilder:
    """Dependency-injection graph builder returning a pre-built or null graph."""

    def __init__(self, graph: igraph.Graph) -> None:
        self._graph = graph

    def build(self, dataset: Any) -> igraph.Graph:
        # Return a lightweight copy to prevent in-place mutation
        return self._graph.copy()


@dataclass
class HypothesisRunnerResult:
    """Complete results package returned by HypothesisExperimentRunner."""
    dataset_name: str
    null_model_name: str
    secondary_records: List[SecondaryEffectRecord] = field(default_factory=list)
    comparison_results: List[MetricComparisonResult] = field(default_factory=list)
    test_results: List[HypothesisTestResult] = field(default_factory=list)
    exported_paths: Dict[str, Path] = field(default_factory=dict)
    runtime_seconds: float = 0.0
    status: str = "SUCCESS"
    errors: List[str] = field(default_factory=list)


class HypothesisExperimentRunner:
    """Top-level orchestrator for connectome hypothesis testing."""

    def __init__(self) -> None:
        self._analysis_reg = analysis_registry
        self._error_reg = error_registry
        self._null_reg = null_registry
        self._secondary_extractor = SecondaryEffectsExtractor()
        self._comparator = MetricComparator()
        self._test_engine = HypothesisTestEngine()

    def run(self, config: HypothesisExperimentConfig) -> HypothesisRunnerResult:
        """Execute full hypothesis-testing suite across Real and/or Null conditions.

        Args:
            config: HypothesisExperimentConfig instance.

        Returns:
            HypothesisRunnerResult with full comparisons and export paths.
        """
        # 0. Delegate directly to CompareExistingRunner if in COMPARE_EXISTING mode
        from .compare_existing_runner import CompareExistingRunner
        from ..config import ExecutionMode
        if config.execution_mode == ExecutionMode.COMPARE_EXISTING:
            return CompareExistingRunner().run(config)

        t_start = time.perf_counter()
        logger.info(
            f"[HypothesisExperimentRunner] Starting hypothesis testing on dataset '{config.dataset_name}' "
            f"(Mode: {config.execution_mode.value if isinstance(config.execution_mode, ExecutionMode) else config.execution_mode}, "
            f"Null Model: {config.null_model_name})."
        )


        runner_result = HypothesisRunnerResult(
            dataset_name=config.dataset_name,
            null_model_name=config.null_model_name,
        )

        try:
            # 1. Load dataset & build real base graph
            logger.info(f"[HypothesisExperimentRunner] Loading dataset '{config.dataset_name}'...")
            dataset = load_dataset(
                dataset_name=config.dataset_name,
                dataset_root=config.dataset_root,
                configs_root=config.configs_root,
            )
            standard_builder = GraphBuilder()
            real_base_graph = standard_builder.build(dataset)
            logger.info(
                f"[HypothesisExperimentRunner] Built real graph: "
                f"V={real_base_graph.vcount():,}, E={real_base_graph.ecount():,}."
            )

            # 2. Execute Condition A (Real)
            real_secondary_records: List[SecondaryEffectRecord] = []
            if config.run_real:
                logger.info("[HypothesisExperimentRunner] Executing Condition A: Real Connectome...")
                real_secondary_records = self._run_condition(
                    condition="real",
                    graph=real_base_graph,
                    dataset=dataset,
                    config=config,
                    null_graph_replicate_id=None,
                    error_seeds=config.random_seeds,
                )

            # 3. Execute Condition B (Null) — one independently rewired graph per null_graph_seed
            null_secondary_records: List[SecondaryEffectRecord] = []
            if config.run_null:
                null_model = self._null_reg.instantiate(config.null_model_name)
                null_graph_seeds = config.effective_null_graph_seeds
                null_error_seeds = config.effective_null_error_seeds
                logger.info(
                    f"[HypothesisExperimentRunner] Generating {len(null_graph_seeds)} "
                    f"independent null graph(s) via '{config.null_model_name}'..."
                )
                for rep_idx, ng_seed in enumerate(null_graph_seeds):
                    null_graph = null_model.generate(
                        real_graph=real_base_graph,
                        config=config.null_model_config,
                        seed=ng_seed,
                    )
                    logger.info(
                        f"[HypothesisExperimentRunner] Null graph replicate {rep_idx} "
                        f"(seed={ng_seed}): V={null_graph.vcount():,}, E={null_graph.ecount():,}."
                    )
                    rep_records = self._run_condition(
                        condition="null",
                        graph=null_graph,
                        dataset=dataset,
                        config=config,
                        null_graph_replicate_id=rep_idx + 1,
                        error_seeds=null_error_seeds,
                    )
                    null_secondary_records.extend(rep_records)


            all_secondary_records = real_secondary_records + null_secondary_records
            runner_result.secondary_records = all_secondary_records

            # 5. Perform Statistical Comparison (if both conditions were run)
            if config.run_real and config.run_null:
                logger.info("[HypothesisExperimentRunner] Performing statistical comparisons...")
                comparisons = self._compare_conditions(
                    real_records=real_secondary_records,
                    null_records=null_secondary_records,
                    config=config,
                )
                runner_result.comparison_results = comparisons

                logger.info("[HypothesisExperimentRunner] Evaluating hypotheses and adjusting FDR...")
                self._test_engine.alpha = config.significance_level
                test_results = self._test_engine.evaluate_suite(comparisons)
                runner_result.test_results = test_results
            else:
                test_results = []

            # 6. Export deliverables
            exporter = HypothesisExporter(output_root=config.output_root)
            exported = exporter.export(
                dataset=config.dataset_name,
                null_model_name=config.null_model_name,
                secondary_records=all_secondary_records,
                test_results=test_results,
                extra_metadata={
                    "error_models": config.error_model_names,
                    "error_rates": config.error_rates,
                    "random_seeds": config.random_seeds,
                },
            )
            runner_result.exported_paths = exported

        except Exception as exc:
            logger.exception(f"[HypothesisExperimentRunner] Pipeline failure: {exc}")
            runner_result.status = "FAILED"
            runner_result.errors.append(str(exc))

        runner_result.runtime_seconds = time.perf_counter() - t_start
        logger.info(
            f"[HypothesisExperimentRunner] Completed in {runner_result.runtime_seconds:.2f}s "
            f"(Status: {runner_result.status})."
        )
        return runner_result

    # ------------------------------------------------------------------ #
    # Condition Execution Helper                                         #
    # ------------------------------------------------------------------ #

    def _run_condition(
        self,
        condition: str,
        graph: igraph.Graph,
        dataset: FlyWireDataset,
        config: HypothesisExperimentConfig,
        null_graph_replicate_id: Optional[int],
        error_seeds: List[int],
    ) -> List[SecondaryEffectRecord]:
        """Execute all error models and rates on a single graph condition.

        Args:
            condition: "real" or "null".
            graph: The baseline graph for this condition (real or null).
            dataset: Loaded FlyWireDataset.
            config: Full hypothesis experiment config.
            null_graph_replicate_id: Integer index of the null graph realisation,
                or None for the real condition.  Forwarded to SecondaryEffectRecord.
            error_seeds: Random seeds for the error-model RNG in this condition.
                For real: config.random_seeds.  For null: config.effective_null_error_seeds.
        """
        # Use dependency-injected graph builder
        builder = _DirectGraphBuilder(graph)
        out_root = str(Path(config.output_root) / config.dataset_name / condition)
        if null_graph_replicate_id is not None:
            out_root = f"{out_root}/rep_{null_graph_replicate_id}"

        # 1. Establish 0% baseline metrics for this condition.
        # The baseline runs with no error model applied, so the graph is unmodified
        # and the result is deterministic regardless of which seed value is passed.
        # Run once and reuse for all error_seeds — avoids O(N_seeds) redundant analysis.
        logger.info(f"[{condition.upper()}] Running baseline (0% error)...")
        base_runner = ExperimentRunner(
            analysis_registry=self._analysis_reg,
            error_registry=self._error_reg,
            graph_builder=builder,
        )
        b_cfg = ExperimentConfig(
            dataset_name=config.dataset_name,
            dataset_root=config.dataset_root,
            configs_root=config.configs_root,
            error_model_name=None,  # Baseline: no perturbation
            analysis_names=config.analysis_names,
            analysis_configs=config.analysis_configs,
            preprocessing_config=config.preprocessing_config,
            seed=error_seeds[0],
            output_root=None,  # No raw export for internal baseline
        )
        _baseline_result = self._extract_metrics_dict(base_runner.run(b_cfg))
        # Fan the single result across all seeds so extract_effects can do seed-paired lookup
        baseline_trial_metrics: Dict[int, Dict[str, Dict[str, float]]] = {
            seed: _baseline_result for seed in error_seeds
        }

        all_condition_records: List[SecondaryEffectRecord] = []

        # 2. Iterate through each error model
        for em_name in config.error_model_names:
            logger.info(f"[{condition.upper()}] Running error model '{em_name}'...")
            runner = self._select_runner(em_name, builder)

            # Pre-generate or discover false_synapses candidates if needed
            cand_path_str: Optional[str] = None
            if em_name == "false_synapses":
                from modules.preprocessing import CandidateGenerator, preprocess_graph
                from modules.error_models.false_synapses.model import clear_candidate_cache
                clear_candidate_cache()
                cache_dir = Path("research_data/cache/false_synapses")
                cache_dir.mkdir(parents=True, exist_ok=True)
                rep_tag = f"_rep{null_graph_replicate_id}" if null_graph_replicate_id is not None else ""
                cand_file = cache_dir / f"candidates_{config.dataset_name.lower()}_{condition}{rep_tag}.parquet"
                std_file = cache_dir / "candidates.parquet"

                if cand_file.exists():
                    cand_path_str = str(cand_file)
                elif condition == "real" and std_file.exists():
                    cand_path_str = str(std_file)
                else:
                    try:
                        prep_for_cand = preprocess_graph(graph, index_node_attrs=["top_region"])
                        reg_idx = prep_for_cand.lookup.node_attr_index.get("top_region", {})
                        if reg_idx:
                            logger.info(f"[{condition.upper()}] Generating candidate cache for false_synapses at {cand_file}...")
                            CandidateGenerator(prep_for_cand).generate(cand_file)
                            cand_path_str = str(cand_file)
                        elif std_file.exists():
                            cand_path_str = str(std_file)
                    except Exception as exc:
                        logger.warning(f"[{condition.upper()}] Auto candidate generation skipped: {exc}")
                        if std_file.exists():
                            cand_path_str = str(std_file)

            perturbed_trial_metrics: Dict[float, Dict[int, Dict[str, Dict[str, float]]]] = {}
            # completion_ratios: {rate: {seed: achieved/requested ratio}} for EM4/EM5
            completion_ratios: Dict[float, Dict[int, float]] = {}

            user_em_cfg = config.error_model_configs.get(em_name, {})
            for rate in config.error_rates:
                perturbed_trial_metrics[rate] = {}
                completion_ratios[rate] = {}
                for seed in error_seeds:
                    em_cfg: Dict[str, Any] = {**user_em_cfg, "error_rate": rate}
                    if cand_path_str and "candidate_cache_path" not in em_cfg:
                        em_cfg["candidate_cache_path"] = cand_path_str

                    t_cfg = ExperimentConfig(
                        dataset_name=config.dataset_name,
                        dataset_root=config.dataset_root,
                        configs_root=config.configs_root,
                        error_model_name=em_name,
                        error_model_config=em_cfg,
                        analysis_names=config.analysis_names,
                        analysis_configs=config.analysis_configs,
                        preprocessing_config=config.preprocessing_config,
                        seed=seed,
                        output_root=f"{out_root}/{em_name}/rate_{rate}_seed_{seed}",
                    )
                    t_res = runner.run(t_cfg)
                    if not t_res.succeeded:
                        err_str = "; ".join(t_res.errors) if t_res.errors else "Trial execution failed"
                        raise RuntimeError(
                            f"[{condition.upper()}] Error model '{em_name}' trial failed (rate={rate}, seed={seed}): {err_str}"
                        )
                    perturbed_trial_metrics[rate][seed] = self._extract_metrics_dict(t_res)

                    # Capture perturbation_completion_ratio from error result.
                    # EM5 (merge_errors) and EM4 (split_errors) populate
                    # perturbation_metadata["achieved_error_rate"] reflecting actual
                    # vs. requested perturbation, which may diverge on null graphs
                    # due to candidate starvation.  EM1/EM2/EM3 do not set this field.
                    ratio = self._extract_completion_ratio(t_res, rate)
                    if ratio is not None:
                        completion_ratios[rate][seed] = ratio

            # 3. Extract baseline-relative secondary effect records
            em_records = self._secondary_extractor.extract_effects(
                condition=condition,
                dataset=config.dataset_name,
                error_model=em_name,
                baseline_trial_metrics=baseline_trial_metrics,
                perturbed_trial_metrics=perturbed_trial_metrics,
                null_graph_replicate_id=null_graph_replicate_id,
                perturbation_completion_ratios=(
                    completion_ratios if any(completion_ratios.values()) else None
                ),
            )
            all_condition_records.extend(em_records)

        return all_condition_records

    # ------------------------------------------------------------------ #
    # Comparison & Extraction Helpers                                    #
    # ------------------------------------------------------------------ #

    def _select_runner(
        self, error_model_name: str, builder: _DirectGraphBuilder
    ) -> Any:
        """Instantiate the correct runner for a given error model."""
        em_norm = error_model_name.lower().replace("-", "_")
        if em_norm == "split_errors":
            return SplitExperimentRunner(
                analysis_registry=self._analysis_reg,
                error_registry=self._error_reg,
                graph_builder=builder,
            )
        elif em_norm == "merge_errors":
            return MergeExperimentRunner(
                analysis_registry=self._analysis_reg,
                error_registry=self._error_reg,
                graph_builder=builder,
            )
        else:
            return ExperimentRunner(
                analysis_registry=self._analysis_reg,
                error_registry=self._error_reg,
                graph_builder=builder,
            )

    def _extract_metrics_dict(
        self, result: ExperimentResult
    ) -> Dict[str, Dict[str, float]]:
        """Extract numeric metrics from an ExperimentResult into a nested dict."""
        metrics_by_analysis: Dict[str, Dict[str, float]] = {}
        for a_res in result.analysis_results:
            if not a_res.succeeded:
                continue
            metrics_by_analysis[a_res.analysis_name] = {}
            for k, v in a_res.metrics.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    metrics_by_analysis[a_res.analysis_name][k] = float(v)
        return metrics_by_analysis

    def _extract_completion_ratio(
        self, result: ExperimentResult, requested_rate: float
    ) -> Optional[float]:
        """Extract the perturbation completion ratio for EM4/EM5 results.

        EM5 (merge_errors) and EM4 (split_errors) populate
        ``ErrorResult.perturbation_metadata["achieved_error_rate"]``.
        This ratio can fall below the requested rate on null graphs where
        candidate pools are smaller (e.g. EM5 shared-partner starvation).

        Returns:
            achieved / requested ratio in [0.0, 1.0], or None if the error model
            does not emit perturbation_metadata (EM1, EM2, EM3).
        """
        if result.error_result is None:
            return None
        meta = getattr(result.error_result, "perturbation_metadata", None)
        if not meta:
            return None
        achieved = meta.get("achieved_error_rate")
        if achieved is None:
            return None
        if requested_rate <= 1e-10:
            return 1.0  # baseline (0% rate) is trivially 100% complete
        return float(min(1.0, achieved / requested_rate))


    def _compare_conditions(
        self,
        real_records: List[SecondaryEffectRecord],
        null_records: List[SecondaryEffectRecord],
        config: HypothesisExperimentConfig,
    ) -> List[MetricComparisonResult]:
        """Aggregate records by (error_model, rate, analysis, metric) and compare.

        Real and Null condition samples are statistically INDEPENDENT: they are
        drawn from different graph topologies (real vs. rewired null).  Paired
        t-tests are therefore never appropriate here, regardless of how many
        shared seed integers exist.  Welch's independent-samples t-test is used
        throughout.  The comparator still accepts a `paired` argument for
        completeness, but it is always passed as False from this method.
        """
        # Index Real effects: {(em, rate, analysis, metric): [rel_changes]}
        real_grouped: Dict[Tuple[str, float, str, str], List[float]] = {}
        metric_cats: Dict[Tuple[str, str], str] = {}
        for r in real_records:
            key = (r.error_model, r.error_rate, r.analysis_name, r.metric_name)
            real_grouped.setdefault(key, []).append(r.relative_change)
            metric_cats[(r.error_model, r.metric_name)] = r.category

        # Index Null effects (may come from multiple null graph replicates)
        null_grouped: Dict[Tuple[str, float, str, str], List[float]] = {}
        for r in null_records:
            key = (r.error_model, r.error_rate, r.analysis_name, r.metric_name)
            null_grouped.setdefault(key, []).append(r.relative_change)

        comparisons: List[MetricComparisonResult] = []

        all_keys = sorted(real_grouped.keys() | null_grouped.keys())
        # paired is always False: Real and Null observations are not matched pairs.
        # See docstring and Issue 2 in the audit for the scientific justification.

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
                paired=False,  # Real vs Null are never statistically paired
            )
            comparisons.append(comp)

        return comparisons
