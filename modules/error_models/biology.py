"""
Phase 011 — Biological Assumptions
====================================
Defines the biological hypotheses and constraints for the error simulation.
This module purely implements the declarative biological constraints.
No graph processing occurs here.
"""
from dataclasses import dataclass
import logging
from typing import Any

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class BiologicalAssumptions:
    """
    Immutable representation of biological assumptions for the experiment.
    
    H1: False-negative errors occur at the synapse level. Edges are never directly removed.
    H2: Connections with fewer synapses are inherently more vulnerable.
    H3: Sparse neurons are more susceptible to reconstruction errors.
    H4: Reconstruction errors are stochastic (implemented in Phase 015).
    H5: The simulator must never create/delete/merge/split neurons or invent edges.
    """
    synapse_weight: float
    source_degree_weight: float
    target_degree_weight: float

    def __post_init__(self) -> None:
        if not isinstance(self.synapse_weight, (int, float)):
            raise ValueError("synapse_weight must be numeric")
        if not isinstance(self.source_degree_weight, (int, float)):
            raise ValueError("source_degree_weight must be numeric")
        if not isinstance(self.target_degree_weight, (int, float)):
            raise ValueError("target_degree_weight must be numeric")
        logger.info("[Biology] BiologicalAssumptions initialized and validated.")
        
    @classmethod
    def from_config(cls, config: Any) -> "BiologicalAssumptions":
        """Load biological assumptions from an ExperimentConfig or dict."""
        try:
            weights = config.error_model_config.get("biology", {}).get("weights", {})
        except AttributeError:
            weights = config.get("biology", {}).get("weights", {}) if isinstance(config, dict) else {}
            
        return cls(
            synapse_weight=float(weights.get("synapse_weight", 1.0)),
            source_degree_weight=float(weights.get("source_degree_weight", 1.0)),
            target_degree_weight=float(weights.get("target_degree_weight", 1.0)),
        )
