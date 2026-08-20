"""
Secondary Effects Analysis Engine
=================================
Extracts baseline-relative secondary metric changes across experimental trials,
distinguishing directly imposed manipulations from emergent structural effects.
"""

from __future__ import annotations

import enum
import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MetricCategory(enum.Enum):
    """Categorization of a metric relative to an error model."""
    PRIMARY_IMPOSED = "primary_imposed"      # Mechanically predetermined by the error model
    SECONDARY_EMERGENT = "secondary_emergent"  # True emergent secondary structural response
    CONTROL_INVARIANT = "control_invariant"    # Topologically guaranteed to stay 0% change


# Rulebook mapping (error_model, metric) -> MetricCategory
_METRIC_CLASSIFICATION_RULES: Dict[Tuple[str, str], MetricCategory] = {
    # EM1: Missed Synapses
    ("missed_synapses", "metric_total_synapses"): MetricCategory.PRIMARY_IMPOSED,
    ("missed_synapses", "metric_node_count"): MetricCategory.CONTROL_INVARIANT,
    ("missed_synapses", "metric_edge_count"): MetricCategory.SECONDARY_EMERGENT,
    ("missed_synapses", "metric_weight_mean"): MetricCategory.SECONDARY_EMERGENT,
    ("missed_synapses", "metric_weight_variance"): MetricCategory.SECONDARY_EMERGENT,
    ("missed_synapses", "metric_reciprocity"): MetricCategory.SECONDARY_EMERGENT,
    ("missed_synapses", "metric_wcc_max_size"): MetricCategory.SECONDARY_EMERGENT,
    ("missed_synapses", "metric_scc_max_size"): MetricCategory.SECONDARY_EMERGENT,

    # EM2: False Synapses
    ("false_synapses", "metric_edge_count"): MetricCategory.PRIMARY_IMPOSED,
    ("false_synapses", "metric_node_count"): MetricCategory.CONTROL_INVARIANT,
    ("false_synapses", "metric_total_synapses"): MetricCategory.SECONDARY_EMERGENT,
    ("false_synapses", "metric_weight_mean"): MetricCategory.SECONDARY_EMERGENT,
    ("false_synapses", "metric_reciprocity"): MetricCategory.SECONDARY_EMERGENT,
    ("false_synapses", "metric_wcc_max_size"): MetricCategory.SECONDARY_EMERGENT,
    ("false_synapses", "metric_scc_max_size"): MetricCategory.SECONDARY_EMERGENT,

    # EM3: Synapse Count Noise
    ("synapse_count_measurement", "metric_node_count"): MetricCategory.CONTROL_INVARIANT,
    ("synapse_count_measurement", "metric_edge_count"): MetricCategory.CONTROL_INVARIANT,
    ("synapse_count_measurement", "metric_total_synapses"): MetricCategory.PRIMARY_IMPOSED,
    ("synapse_count_measurement", "metric_weight_variance"): MetricCategory.SECONDARY_EMERGENT,
    ("synapse_count_measurement", "metric_weight_std"): MetricCategory.SECONDARY_EMERGENT,
    ("synapse_count_measurement", "metric_weight_mean"): MetricCategory.SECONDARY_EMERGENT,
    # EM3 changes only weights; node/edge topology is unchanged → density is CONTROL_INVARIANT
    ("synapse_count_measurement", "density"): MetricCategory.CONTROL_INVARIANT,

    # EM4: Split Errors
    ("split_errors", "metric_node_count"): MetricCategory.PRIMARY_IMPOSED,
    ("split_errors", "metric_total_degree_mean"): MetricCategory.PRIMARY_IMPOSED,
    ("split_errors", "metric_edge_count"): MetricCategory.CONTROL_INVARIANT,
    ("split_errors", "metric_total_synapses"): MetricCategory.CONTROL_INVARIANT,
    ("split_errors", "metric_wcc_max_size"): MetricCategory.SECONDARY_EMERGENT,
    ("split_errors", "metric_scc_max_size"): MetricCategory.SECONDARY_EMERGENT,
    ("split_errors", "metric_wcc_count"): MetricCategory.SECONDARY_EMERGENT,
    ("split_errors", "metric_scc_count"): MetricCategory.SECONDARY_EMERGENT,
    ("split_errors", "metric_reciprocity"): MetricCategory.SECONDARY_EMERGENT,

    # EM5: Merge Errors
    ("merge_errors", "metric_node_count"): MetricCategory.PRIMARY_IMPOSED,
    ("merge_errors", "metric_edge_count"): MetricCategory.SECONDARY_EMERGENT,
    ("merge_errors", "metric_total_synapses"): MetricCategory.SECONDARY_EMERGENT,
    ("merge_errors", "metric_weight_mean"): MetricCategory.SECONDARY_EMERGENT,
    ("merge_errors", "metric_weight_variance"): MetricCategory.SECONDARY_EMERGENT,
    ("merge_errors", "metric_wcc_max_size"): MetricCategory.SECONDARY_EMERGENT,
    ("merge_errors", "metric_scc_max_size"): MetricCategory.SECONDARY_EMERGENT,
    ("merge_errors", "metric_reciprocity"): MetricCategory.SECONDARY_EMERGENT,
}


def classify_metric(error_model: str, metric_name: str) -> MetricCategory:
    """Return the classification for a given (error_model, metric_name)."""
    # Normalize error model aliases
    em = error_model.lower().replace("-", "_")
    if em == "synapse_count":
        em = "synapse_count_measurement"

    rule = _METRIC_CLASSIFICATION_RULES.get((em, metric_name))
    if rule is not None:
        return rule

    # Heuristic classifications for other metrics
    if "density" in metric_name or "total_degree_mean" in metric_name:
        return MetricCategory.PRIMARY_IMPOSED

    return MetricCategory.SECONDARY_EMERGENT


@dataclass
class SecondaryEffectRecord:
    """Single trial's baseline-relative secondary effect.

    Fields
    ------
    condition : "real" or "null"
    dataset   : Dataset name, e.g. "BANC"
    error_model : Error model name, e.g. "missed_synapses"
    error_rate  : Float error rate, e.g. 0.05
    trial_seed  : Random seed used for the error-model RNG in this trial.
    analysis_name : Analysis module name, e.g. "basic_structure"
    metric_name   : Metric key, e.g. "metric_edge_count"
    category      : "secondary_emergent" | "primary_imposed" | "control_invariant"
    baseline_value  : Metric value at error_rate = 0.0 (own-condition baseline)
    perturbed_value : Metric value at this error_rate
    absolute_delta  : perturbed_value - baseline_value
    relative_change : absolute_delta / baseline_value  (or absolute_delta when baseline ~ 0)
    is_near_zero_baseline : True when |baseline_value| < threshold (absolute fallback used)
    null_graph_replicate_id : For null condition: integer index (0-based) of the null graph
        topology realisation.  None for real condition.  This field distinguishes
        observations from different independently generated null graph instances.
    perturbation_completion_ratio : Fraction of requested error actually achieved
        (requested_k / target_k).  Relevant for EM5 (candidate starvation) and EM4.
        1.0 for error models with no candidate pool (EM1, EM2, EM3).
        None when no perturbation metadata is available.
    """
    condition: str
    dataset: str
    error_model: str
    error_rate: float
    trial_seed: int
    analysis_name: str
    metric_name: str
    category: str
    baseline_value: float
    perturbed_value: float
    absolute_delta: float
    relative_change: float
    is_near_zero_baseline: bool = False
    null_graph_replicate_id: Optional[int] = None
    perturbation_completion_ratio: Optional[float] = None


class SecondaryEffectsExtractor:
    """Calculates baseline-normalized secondary metric changes across trials."""

    def __init__(self, near_zero_threshold: float = 1e-4) -> None:
        self.near_zero_threshold = near_zero_threshold

    def extract_effects(
        self,
        condition: str,
        dataset: str,
        error_model: str,
        baseline_trial_metrics: Dict[int, Dict[str, Dict[str, float]]],
        perturbed_trial_metrics: Dict[float, Dict[int, Dict[str, Dict[str, float]]]],
        null_graph_replicate_id: Optional[int] = None,
        perturbation_completion_ratios: Optional[Dict[float, Dict[int, float]]] = None,
    ) -> List[SecondaryEffectRecord]:
        """Extract baseline-normalized secondary changes for all error rates and trials.

        Args:
            condition: "real" or "null".
            dataset: Dataset name (e.g. "BANC").
            error_model: Error model name (e.g. "missed_synapses").
            baseline_trial_metrics:
                Mapping {seed: {analysis_name: {metric_name: value}}} at rate=0.0.
            perturbed_trial_metrics:
                Mapping {rate: {seed: {analysis_name: {metric_name: value}}}}.
            null_graph_replicate_id:
                0-based integer index of the null graph realisation, or None for
                the real condition.  Propagated to every output record so that
                downstream analysis can distinguish independent null-graph
                observations from error-model-only variation.
            perturbation_completion_ratios:
                Optional mapping {rate: {seed: ratio}} recording what fraction of
                the requested error was actually achieved (relevant for EM5/EM4).
                When provided, the ratio is propagated to each SecondaryEffectRecord.

        Returns:
            List of SecondaryEffectRecord objects.
        """
        records: List[SecondaryEffectRecord] = []

        # Build mean baseline across seeds in a single pass.
        # baseline_trial_metrics is fanned from one run, so all seeds share the same values;
        # averaging is still correct and costs negligible extra work.
        baseline_sums: Dict[Tuple[str, str], float] = {}
        baseline_counts: Dict[Tuple[str, str], int] = {}
        for s_dict in baseline_trial_metrics.values():
            for a_name, m_dict in s_dict.items():
                for m_name, val in m_dict.items():
                    if val is not None and math.isfinite(val):
                        key = (a_name, m_name)
                        baseline_sums[key] = baseline_sums.get(key, 0.0) + val
                        baseline_counts[key] = baseline_counts.get(key, 0) + 1
        baseline_means: Dict[Tuple[str, str], float] = {
            k: baseline_sums[k] / baseline_counts[k] for k in baseline_sums
        }

        # Process each error rate
        for rate, trials_by_seed in sorted(perturbed_trial_metrics.items()):
            for seed, a_dict in trials_by_seed.items():
                completion_ratio: Optional[float] = None
                if perturbation_completion_ratios is not None:
                    completion_ratio = perturbation_completion_ratios.get(rate, {}).get(seed)

                for a_name, m_dict in a_dict.items():
                    for m_name, p_val in m_dict.items():
                        if p_val is None or not math.isfinite(p_val):
                            continue

                        # Determine baseline value (paired seed if available, else baseline mean)
                        b_val = None
                        if seed in baseline_trial_metrics:
                            b_val = baseline_trial_metrics[seed].get(a_name, {}).get(m_name)
                        if b_val is None or not math.isfinite(b_val):
                            b_val = baseline_means.get((a_name, m_name), 0.0)

                        abs_delta = p_val - b_val
                        is_near_zero = abs(b_val) < self.near_zero_threshold

                        if is_near_zero:
                            # Avoid catastrophic division by near-zero (e.g. assortativity ~ 0.0)
                            rel_change = abs_delta
                        else:
                            rel_change = abs_delta / b_val

                        cat = classify_metric(error_model, m_name).value

                        records.append(SecondaryEffectRecord(
                            condition=condition,
                            dataset=dataset,
                            error_model=error_model,
                            error_rate=float(rate),
                            trial_seed=int(seed),
                            analysis_name=a_name,
                            metric_name=m_name,
                            category=cat,
                            baseline_value=float(b_val),
                            perturbed_value=float(p_val),
                            absolute_delta=float(abs_delta),
                            relative_change=float(rel_change),
                            is_near_zero_baseline=is_near_zero,
                            null_graph_replicate_id=null_graph_replicate_id,
                            perturbation_completion_ratio=completion_ratio,
                        ))

        logger.debug(
            f"[SecondaryEffectsExtractor] Extracted {len(records)} secondary effect records "
            f"for {condition}/{dataset}/{error_model} "
            f"(null_graph_rep={null_graph_replicate_id})."
        )
        return records

