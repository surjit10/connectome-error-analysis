"""
Phase TBD – False Synapses / Weight Assignment
=================================================
Provides functions for assigning biologically plausible synaptic weights to
false-positive (false-synapse) edges.

The weight is sampled from the empirical distribution of **weak** edges in the
baseline graph (syn_count ≤ 5).  This is a modelling assumption consistent
with the observation that the majority of observed connections (∼71.5 % in
the BANC dataset) have five or fewer synapses, making weak connections a
reasonable prior for false-positive reconstruction errors.

References:
    - The ≤ 5 threshold is adopted as a modelling assumption, stated in the
      methodology section of any paper using this framework.
   - It is **not** a biologically verified property of false-positive errors.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from modules.preprocessing.common.prepared_graph import PreparedGraph
from modules.preprocessing.false_synapses.config import WEIGHT_THRESHOLD

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_empirical_weights: Optional[np.ndarray] = None


def get_empirical_weight_distribution(
    prepared: PreparedGraph,
    *,
    max_syn_count: int = WEIGHT_THRESHOLD,
) -> np.ndarray:
    """Return the empirical distribution of ``syn_count`` values for edges
    whose weight ≤ *max_syn_count*.

    The result is computed once and cached in memory so that repeated calls
    (across trials) are effectively free.

    Returns:
        A 1-D ``numpy.ndarray`` of ``int`` values (observed synapse counts).
    """
    global _empirical_weights
    if _empirical_weights is not None:
        return _empirical_weights

    # Extract syn_count from the baseline graph's edge attributes.
    graph = prepared.graph
    if "syn_count" in graph.edge_attributes():
        weights = graph.es["syn_count"]
    elif "weight" in graph.edge_attributes():
        weights = graph.es["weight"]
    else:
        logger.warning(
            "[WeightAssignment] No syn_count or weight edge attribute found; "
            "falling back to uniform weight of 1."
        )
        _empirical_weights = np.array([1], dtype=np.int64)
        return _empirical_weights

    arr = np.array(weights, dtype=np.int64)
    weak = arr[arr <= max_syn_count]

    if len(weak) == 0:
        logger.warning(
            "[WeightAssignment] No edges with syn_count ≤ %d; "
            "using full distribution.", max_syn_count,
        )
        weak = arr

    _empirical_weights = weak
    logger.info(
        "[WeightAssignment] Cached %s weak-edge weights (syn_count ≤ %d).",
        f"{len(_empirical_weights):,}", max_syn_count,
    )
    return _empirical_weights


def sample_false_weight(
    rng: np.random.Generator,
    weight_distribution: np.ndarray,
) -> int:
    """Sample a single synaptic weight from the empirical distribution.

    Args:
        rng:                NumPy random generator (seeded by the framework).
        weight_distribution: Array of observed synapse counts.

    Returns:
        A random ``int`` weight from the distribution (sampled with replacement).
    """
    return int(rng.choice(weight_distribution))
