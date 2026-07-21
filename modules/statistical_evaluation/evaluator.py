"""
Phase 017 — Statistical Evaluation
===================================
Aggregates the results produced by multiple independent simulation trials
and quantifies how biologically plausible EM reconstruction errors affect graph analyses.

Extended in Phase 017 to also evaluate **vector-valued graph analyses**
(PageRank, degree distribution, betweenness, closeness) via registered
comparison strategies, producing derived scalar metrics that flow through
the existing statistical machinery unchanged.
"""
import math
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.experiment_runner import ExperimentResult
from core.statistics_engine import StatisticsEngine, MetricStats

logger = logging.getLogger(__name__)

def cohens_d(mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int) -> float:
    """Computes Cohen's d effect size between two groups (perturbed vs baseline)."""
    if n1 + n2 <= 2:
        return 0.0
    pooled_var = ((n1 - 1) * (std1 ** 2) + (n2 - 1) * (std2 ** 2)) / (n1 + n2 - 2)
    if pooled_var == 0:
        return 0.0
    return (mean1 - mean2) / math.sqrt(pooled_var)

def _safe_cohens_d(
    p_mean: float, p_std: float, p_n: int,
    b_mean: float, b_std: float, b_n: int,
) -> float:
    """Compute Cohen's d, returning 0.0 on any non-finite result."""
    if not (math.isfinite(p_mean) and math.isfinite(b_mean)):
        return 0.0
    d = cohens_d(p_mean, p_std, p_n, b_mean, b_std, b_n)
    return d if math.isfinite(d) else 0.0


@dataclass
class MetricEvaluation:
    metric_name: str
    baseline_mean: float
    baseline_std: float
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    effect_size: float
    
@dataclass
class StatisticalEvaluationResult:
    dataset_name: str
    error_level: float
    n_trials: int
    runtime_seconds: float
    metrics: Dict[str, Dict[str, MetricEvaluation]] = field(default_factory=dict)
    
class StatisticalEvaluator:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
    def evaluate(
        self, 
        baseline_trials: List[ExperimentResult], 
        perturbed_trials: List[ExperimentResult]
    ) -> StatisticalEvaluationResult:
        if not baseline_trials:
            raise ValueError("Baseline trials (0% error) must be provided.")
        if not perturbed_trials:
            raise ValueError("Perturbed trials must be provided.")
            
        logger.info(
            f"[StatisticalEvaluator] Evaluating {len(perturbed_trials)} perturbed "
            f"trials against {len(baseline_trials)} baseline trials."
        )
            
        engine = StatisticsEngine()
        baseline_stats = engine.aggregate(baseline_trials)
        perturbed_stats = engine.aggregate(perturbed_trials)
        
        # ── 1. Scalar metric evaluation (unchanged) ────────────────────
        eval_metrics = self._evaluate_scalar_metrics(
            baseline_stats, perturbed_stats,
        )

        # ── 2. Vector comparison metrics (new) ──────────────────────────
        vector_comparisons = engine.compute_vector_comparisons(
            baseline_stats,
            perturbed_stats,
            config=self.config,
        )
        self._merge_vector_into_evaluation(
            eval_metrics, vector_comparisons,
            baseline_stats, perturbed_stats,
        )

        # ── 3. Validation ───────────────────────────────────────────────
        for a_name, m_dict in eval_metrics.items():
            for m_name, ev in m_dict.items():
                if not math.isfinite(ev.effect_size):
                    # Non-finite effect sizes are logged but no longer fatal
                    # (vector-derived metrics may have n=1, giving 0/0).
                    logger.warning(
                        "[StatisticalEvaluator] Non-finite effect size for "
                        "%s.%s; setting to 0.0.",
                        a_name, m_name,
                    )
                    ev.effect_size = 0.0
                    
        # Extract metadata
        dataset_name = perturbed_trials[0].dataset_name
        error_level = 0.0
        for r in perturbed_trials:
            if r.error_result and hasattr(r.error_result, "perturbation_metadata"):
                error_level = float(r.error_result.perturbation_metadata.get("target_error_rate", 0.0))
                break
            elif r.config_snapshot and "error_model_config" in r.config_snapshot:
                error_level = float(r.config_snapshot["error_model_config"].get("error_rate", 0.0))
                break
                
        return StatisticalEvaluationResult(
            dataset_name=dataset_name,
            error_level=error_level,
            n_trials=len(perturbed_trials),
            runtime_seconds=perturbed_stats.mean_runtime,
            metrics=eval_metrics
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _evaluate_scalar_metrics(
        self,
        baseline_stats: Any,
        perturbed_stats: Any,
    ) -> Dict[str, Dict[str, MetricEvaluation]]:
        """Evaluate scalar metrics (existing pathway, unchanged logic)."""
        eval_metrics: Dict[str, Dict[str, MetricEvaluation]] = {}
        for a_name, p_astat in perturbed_stats.analysis_stats.items():
            eval_metrics[a_name] = {}
            b_astat = baseline_stats.analysis_stats.get(a_name)

            for m_name, p_mstat in p_astat.metric_stats.items():
                if b_astat and m_name in b_astat.metric_stats:
                    b_mstat = b_astat.metric_stats[m_name]
                    d = _safe_cohens_d(
                        p_mstat.mean, p_mstat.std, p_mstat.n,
                        b_mstat.mean, b_mstat.std, b_mstat.n,
                    )
                    b_mean = b_mstat.mean
                    b_std = b_mstat.std
                else:
                    d = 0.0
                    b_mean = float('nan') if not math.isfinite(p_mstat.mean) else 0.0
                    b_std = 0.0

                eval_metrics[a_name][m_name] = MetricEvaluation(
                    metric_name=m_name,
                    baseline_mean=b_mean,
                    baseline_std=b_std,
                    mean=p_mstat.mean,
                    std=p_mstat.std,
                    ci_lower=p_mstat.ci_lower,
                    ci_upper=p_mstat.ci_upper,
                    effect_size=d,
                )
        return eval_metrics

    def _merge_vector_into_evaluation(
        self,
        eval_metrics: Dict[str, Dict[str, MetricEvaluation]],
        vector_comparisons: Dict[str, Dict[str, MetricStats]],
        baseline_stats: Any,
        perturbed_stats: Any,
    ) -> None:
        """
        Merge derived vector comparison metrics into *eval_metrics*.

        Each derived scalar (e.g. ``pagerank_scores_spearman``) gets a
        :class:`MetricEvaluation` with Cohen's d computed against the null
        hypothesis (0 = no correlation / no distribution shift).

        Note: vector-derived metric keys (e.g. ``pagerank_scores_pearson``)
        are distinct from the original scalar metric keys, so there is no
        risk of collision with the existing scalar evaluation pathway.
        """
        for a_name, derived_dict in vector_comparisons.items():
            if a_name not in eval_metrics:
                eval_metrics[a_name] = {}

            for d_key, d_mstat in derived_dict.items():
                # Vector-derived metrics compare against the null hypothesis
                # (0 = no effect).  For example, a Spearman of 0 means no
                # rank correlation — Cohen's d measures how far the observed
                # correlation is from 0.
                d = _safe_cohens_d(
                    d_mstat.mean, d_mstat.std, d_mstat.n,
                    0.0, 0.0, 1,
                )

                eval_metrics[a_name][d_key] = MetricEvaluation(
                    metric_name=d_key,
                    baseline_mean=0.0,
                    baseline_std=0.0,
                    mean=d_mstat.mean,
                    std=d_mstat.std,
                    ci_lower=d_mstat.ci_lower,
                    ci_upper=d_mstat.ci_upper,
                    effect_size=d,
                )

        logger.debug(
            "[StatisticalEvaluator] Merged %d vector-derived metrics "
            "into evaluation.",
            sum(len(v) for v in vector_comparisons.values()),
        )
