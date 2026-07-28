"""
Phase 008 – Error Model Framework
===================================
Public surface of the error-models package.

Downstream components (Experiment Runner, research modules) should import
from here, not from the sub-modules directly.

Typical Experiment Runner usage::

    from modules.error_models import registry, ErrorResult, ErrorModelStatus

    model  = registry.instantiate("missed_synapses")
    result = model.execute(prepared_graph, config={"removal_rate": 0.05})

    if result.status == ErrorModelStatus.SUCCESS:
        # result.edge_mask is a bool list — True = active edge.
        # The runner builds the temp subgraph from this mask.
        pass

Typical concrete model authoring::

    from modules.error_models import BaseErrorModel, registry

    class MissedSynapses(BaseErrorModel):
        NAME = "missed_synapses"

        def _perturb(self, prepared, config, result, rng):
            n = prepared.graph.ecount()
            rate = config.get("removal_rate", 0.05)
            mask = rng.random(n) >= rate
            result.edge_mask = mask.tolist()

    registry.register(MissedSynapses)
"""

from .common.exceptions import (
    ErrorModelFrameworkError,
    ErrorModelExecutionError,
    InvalidInputError,
    ErrorRegistryError,
)
from .common.error_result import ErrorResult, ErrorModelStatus
from .common.base_error_model import BaseErrorModel
from .common.error_registry import ErrorRegistry, registry

__all__ = [
    # Core contract
    "BaseErrorModel",
    "ErrorResult",
    "ErrorModelStatus",
    # Registry
    "ErrorRegistry",
    "registry",
    # Exceptions
    "ErrorModelFrameworkError",
    "ErrorModelExecutionError",
    "InvalidInputError",
    "ErrorRegistryError",
]

# Auto-register standard models
from . import missed_synapses
from . import false_synapses
from . import synapse_count
