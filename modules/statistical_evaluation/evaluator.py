"""
Phase 017 — Statistical Evaluation
===================================
Aggregates the results produced by multiple independent simulation trials
and quantifies how biologically plausible EM reconstruction errors affect graph analyses.
"""
import math
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.experiment_runner import ExperimentResult
from core.statistics_engine import StatisticsEngine

logger = logging.getLogger(__name__)

def cohens_d(mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int) -> float:
    """Computes Cohen's d effect size between two groups (perturbed vs baseline)."""
    if n1 + n2 <= 2:
        return 0.0
    pooled_var = ((n1 - 1) * (std1 ** 2) + (n2 - 1) * (std2 ** 2)) / (n1 + n2 - 2)
    if pooled_var == 0:
        return 0.0
    return (mean1 - mean2) / math.sqrt(pooled_var)

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
        
        eval_metrics = {}
        for a_name, p_astat in perturbed_stats.analysis_stats.items():
            eval_metrics[a_name] = {}
            b_astat = baseline_stats.analysis_stats.get(a_name)
            
            for m_name, p_mstat in p_astat.metric_stats.items():
                if b_astat and m_name in b_astat.metric_stats:
                    b_mstat = b_astat.metric_stats[m_name]
                    d = cohens_d(
                        p_mstat.mean, p_mstat.std, p_mstat.n,
                        b_mstat.mean, b_mstat.std, b_mstat.n
                    )
                    b_mean = b_mstat.mean
                    b_std = b_mstat.std
                else:
                    d = 0.0
                    b_mean = float('nan')
                    b_std = float('nan')
                    
                eval_metrics[a_name][m_name] = MetricEvaluation(
                    metric_name=m_name,
                    baseline_mean=b_mean,
                    baseline_std=b_std,
                    mean=p_mstat.mean,
                    std=p_mstat.std,
                    ci_lower=p_mstat.ci_lower,
                    ci_upper=p_mstat.ci_upper,
                    effect_size=d
                )
                
        # Validation
        for a_name, m_dict in eval_metrics.items():
            for m_name, ev in m_dict.items():
                if math.isnan(ev.baseline_mean):
                    raise ValueError(f"Baseline missing for metric {a_name}.{m_name}")
                if not math.isfinite(ev.effect_size):
                    raise ValueError(f"Non-finite effect size for metric {a_name}.{m_name}")
                    
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
