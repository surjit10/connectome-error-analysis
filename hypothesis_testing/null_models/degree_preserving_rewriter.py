"""
Degree- and Weight-Preserving Null Model
========================================
Implements a directed degree-preserving randomized null connectome generator
using Markov Chain Monte Carlo (MCMC) double-edge swaps while conserving the
exact connection weight pool and vertex metadata.

Properties
----------
Preserved:
    - In-degree sequence  (k_in  for every vertex is exactly unchanged)
    - Out-degree sequence (k_out for every vertex is exactly unchanged)
    - Total vertex count N
    - Total edge count E
    - Global connection-weight distribution P(s)  (the multiset of all edge
      weights is conserved; weights are re-assigned uniformly at random to
      rewired edges unless ``shuffle_weights`` is disabled, in which case the
      original edge-order is preserved on the rewired graph)
    - Vertex metadata (root_id, top_region, soma_side)

Randomised:
    - Edge wiring (which vertex pairs are connected)
    - Per-node weighted degree (strength) — NOT preserved.  Because weights
      are re-assigned to edges after rewiring, the strength sequence of the
      null graph differs from the real graph even though the binary degree
      sequence and the global weight distribution are identical.  This is
      intentional: the null model tests whether secondary structural effects
      require specific wiring topology BEYOND the degree sequence alone.
    - Higher-order topology: clustering, reciprocity, community structure,
      motifs, and non-local path connectivity.

Scientific note on weight-topology decoupling
---------------------------------------------
The current implementation preserves the global weight distribution P(s) by
extracting all edge weights before rewiring and re-assigning them to the
rewired edges in their original list order (``shuffle_weights=False``) or in
a uniformly random permutation (``shuffle_weights=True``).  In both cases,
the per-node strength sequence is randomised.  This is the standard and
scientifically defensible approach for degree-preserving null models in
network neuroscience (Rubinov & Sporns 2010; Maslov & Sneppen 2002).
If preservation of the per-node strength sequence is required, use a
weighted rewiring algorithm (not currently implemented here).
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, Optional

import igraph
import numpy as np

from .base import BaseNullModel

logger = logging.getLogger(__name__)


class DirectedDegreeWeightPreservingNullModel(BaseNullModel):
    """Generates a degree- and weight-matched null graph via edge rewiring."""

    NAME = "degree_preserving"

    def generate(
        self,
        real_graph: igraph.Graph,
        config: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ) -> igraph.Graph:
        """Generate a degree-preserving rewired directed graph.

        Args:
            real_graph: The immutable baseline directed igraph.Graph.
            config: Optional config dict. Recognized keys:
                - "swaps_multiplier": int (default: 10). Total swaps = multiplier * E.
                - "shuffle_weights": bool (default: False). Whether to shuffle weights
                  among rewired edges.
            seed: Optional integer random seed.

        Returns:
            A new directed igraph.Graph with rewired topology and preserved weights.
        """
        cfg = config or {}
        swaps_multiplier = int(cfg.get("swaps_multiplier", 10))
        shuffle_weights = bool(cfg.get("shuffle_weights", False))

        # 1. Clone graph to prevent mutating baseline
        null_g = real_graph.copy()

        e_count = null_g.ecount()
        if e_count == 0:
            logger.warning("[DirectedDegreeWeightPreservingNullModel] Graph has 0 edges; returning clone.")
            return null_g

        # 2. Seed RNG for reproducibility
        if seed is not None:
            igraph.set_random_number_generator(random.Random(seed))
            np_rng = np.random.default_rng(seed)
        else:
            np_rng = np.random.default_rng()

        # 3. Extract original weights before rewiring (igraph rewire clears edge attributes)
        if "syn_count" in real_graph.edge_attributes():
            weights = list(real_graph.es["syn_count"])
        elif "weight" in real_graph.edge_attributes():
            weights = list(real_graph.es["weight"])
        else:
            weights = [1] * e_count

        # 4. Perform degree-preserving double-edge swaps
        n_swaps = max(1, swaps_multiplier * e_count)
        logger.info(
            f"[DirectedDegreeWeightPreservingNullModel] Rewiring {e_count:,} edges with "
            f"{n_swaps:,} swaps (multiplier={swaps_multiplier})."
        )

        try:
            null_g.rewire(n=n_swaps)
        except Exception as exc:
            logger.warning(
                f"[DirectedDegreeWeightPreservingNullModel] igraph rewire error: {exc}."
            )

        # 5. Re-assign weight distribution onto rewired edges
        if shuffle_weights:
            np_rng.shuffle(weights)
        null_g.es["syn_count"] = weights

        # 5. Attach null metadata
        base_name = (
            real_graph["dataset_name"]
            if "dataset_name" in real_graph.attributes()
            else "CONNECTOME"
        )
        null_g["dataset_name"] = f"{base_name}_NULL_DEGREE_PRESERVED"
        null_g["null_model"] = self.NAME
        null_g["null_seed"] = seed

        # Ensure ID mappings exist
        if "id_to_idx" not in null_g.attributes() and "root_id" in null_g.vertex_attributes():
            root_ids = null_g.vs["root_id"]
            null_g["id_to_idx"] = {rid: idx for idx, rid in enumerate(root_ids)}
            null_g["id_map"] = {idx: rid for idx, rid in enumerate(root_ids)}

        self._validate_null_graph(null_g, real_graph)
        return null_g
