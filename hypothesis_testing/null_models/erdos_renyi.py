"""
Directed Erdős–Rényi Null Model
===============================
Implements a homogeneous random directed G(N, M) graph generator matching
the total vertex count N and total edge count M of the baseline connectome,
with empirical edge-weight sampling.

Properties:
    - Preserves: Total vertex count N, Total directed edge count M.
    - Randomizes: Degree distribution (becomes Poisson), Clustering, Reciprocity,
      Modularity, and Flow structure.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, Optional

import igraph
import numpy as np

from .base import BaseNullModel

logger = logging.getLogger(__name__)


class DirectedErdosRenyiNullModel(BaseNullModel):
    """Generates a homogeneous directed G(N, M) random graph."""

    NAME = "erdos_renyi"

    def generate(
        self,
        real_graph: igraph.Graph,
        config: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ) -> igraph.Graph:
        """Generate a directed G(N, M) graph matching real_graph size."""
        n = real_graph.vcount()
        m = real_graph.ecount()

        if seed is not None:
            igraph.set_random_number_generator(random.Random(seed))
            np_rng = np.random.default_rng(seed)
        else:
            np_rng = np.random.default_rng()

        logger.info(
            f"[DirectedErdosRenyiNullModel] Generating directed G(N={n:,}, M={m:,})."
        )
        null_g = igraph.Graph.Erdos_Renyi(n=n, m=m, directed=True, loops=False)

        # Copy vertex attributes from real_graph
        for attr in real_graph.vertex_attributes():
            null_g.vs[attr] = real_graph.vs[attr]

        if "root_id" not in null_g.vertex_attributes():
            null_g.vs["root_id"] = list(range(1, n + 1))

        # Sample edge weights from empirical distribution
        if "syn_count" in real_graph.edge_attributes():
            empirical_weights = np.array(real_graph.es["syn_count"])
            sampled_weights = np_rng.choice(empirical_weights, size=m, replace=True)
            null_g.es["syn_count"] = sampled_weights.tolist()
        elif "weight" in real_graph.edge_attributes():
            empirical_weights = np.array(real_graph.es["weight"])
            sampled_weights = np_rng.choice(empirical_weights, size=m, replace=True)
            null_g.es["weight"] = sampled_weights.tolist()
        else:
            null_g.es["syn_count"] = [1] * m

        # Attach metadata
        base_name = (
            real_graph["dataset_name"]
            if "dataset_name" in real_graph.attributes()
            else "CONNECTOME"
        )
        null_g["dataset_name"] = f"{base_name}_NULL_ERDOS_RENYI"
        null_g["null_model"] = self.NAME
        null_g["null_seed"] = seed

        root_ids = null_g.vs["root_id"]
        null_g["id_to_idx"] = {rid: idx for idx, rid in enumerate(root_ids)}
        null_g["id_map"] = {idx: rid for idx, rid in enumerate(root_ids)}

        self._validate_null_graph(null_g, real_graph)
        return null_g
