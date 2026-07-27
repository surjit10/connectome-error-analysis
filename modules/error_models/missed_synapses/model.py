"""
Phase 015 — Missed Synapse Simulation
======================================
Core biological simulation engine for Experiment 1.
Consumes calibrated probabilities and stochastically removes individual synapses.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np

from ..common.base_error_model import BaseErrorModel
from ..common.error_result import ErrorResult
from modules.preprocessing.common.prepared_graph import PreparedGraph

logger = logging.getLogger(__name__)


class MissedSynapsesModel(BaseErrorModel):
    """
    Simulates missed synapse errors by applying calibrated biological removal probabilities
    to individual synapses in an independent binomial trial.
    """
    
    NAME = "missed_synapses"

    def _perturb(
        self,
        prepared: PreparedGraph,
        config: Dict[str, Any],
        result: ErrorResult,
        rng: np.random.Generator,
    ) -> None:
        logger.info("[MissedSynapses] Starting stochastic synapse simulation.")
        
        if not hasattr(prepared, "calibrated_probabilities"):
            raise ValueError(
                "[MissedSynapses] Missing 'calibrated_probabilities' in PreparedGraph. "
                "Phase 014 must run before Phase 015."
            )
            
        prob_table = prepared.calibrated_probabilities.probabilities
        
        syn_count = prob_table["syn_count"].to_numpy().astype(np.int64)
        removal_prob = prob_table["calibrated_removal_probability"].to_numpy().astype(np.float64)
        
        if len(syn_count) != prepared.graph.ecount():
            raise ValueError(
                f"[MissedSynapses] Probability table length ({len(syn_count)}) "
                f"does not match graph edge count ({prepared.graph.ecount()})."
            )
            
        # For each edge, n=syn_count independent synapses, each with survival probability p=(1.0 - removal_prob)
        survival_prob = np.clip(1.0 - removal_prob, 0.0, 1.0)
        
        # Binomial sampling: n trials, probability of success p
        surviving_synapses = rng.binomial(n=syn_count, p=survival_prob)
        
        # Edge mask: True if > 0 synapses survive
        edge_mask = surviving_synapses > 0
        
        # Weight updates: for edges that survive but lost synapses
        weight_updates = {}
        # Find indices where survival > 0 AND survival < original
        changed_mask = (surviving_synapses > 0) & (surviving_synapses < syn_count)
        changed_indices = np.nonzero(changed_mask)[0]
        
        for idx in changed_indices:
            weight_updates[int(idx)] = int(surviving_synapses[idx])
            
        # Quality Control & Stats
        total_original = syn_count.sum()
        total_surviving = surviving_synapses.sum()
        removed_synapses = total_original - total_surviving
        removed_edges = int((~edge_mask).sum())
        
        achieved_error_rate = 0.0 if total_original == 0 else removed_synapses / total_original
        
        target_error_rate = float(config.get("error_rate", 0.0))
        tolerance = float(config.get("tolerance", 0.005)) # ±0.5 percentage points
        
        if total_original > 0 and abs(achieved_error_rate - target_error_rate) > tolerance:
            raise RuntimeError(
                f"[MissedSynapses] Quality Control failed! Achieved error rate "
                f"{achieved_error_rate:.4f} outside tolerance ({tolerance}) of target {target_error_rate}."
            )
            
        # Check validation rules
        if total_surviving > total_original:
            raise RuntimeError("[MissedSynapses] Surviving synapses exceeded original synapse count.")
        if (surviving_synapses < 0).any():
            raise RuntimeError("[MissedSynapses] Generated negative surviving synapse counts.")
            
        # Output artifacts
        result.edge_mask = edge_mask.tolist()
        result.weight_updates = weight_updates
        result.perturbation_metadata = {
            "total_original_synapses": int(total_original),
            "total_surviving_synapses": int(total_surviving),
            "removed_synapses": int(removed_synapses),
            "removed_edges": removed_edges,
            "target_error_rate": float(target_error_rate),
            "achieved_error_rate": float(achieved_error_rate)
        }
        
        logger.info(
            f"[MissedSynapses] Simulation complete. "
            f"Removed {removed_synapses} synapses ({achieved_error_rate:.2%}). "
            f"Removed {removed_edges} edges."
        )

# Register the model
from ..common.error_registry import registry
registry.register(MissedSynapsesModel, overwrite=True)
