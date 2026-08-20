"""
Base Null Model Interface
=========================
Defines the abstract interface and validation contract for all null-model
generators in the hypothesis-testing subsystem.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, Optional

import igraph

logger = logging.getLogger(__name__)


class BaseNullModel(abc.ABC):
    """Abstract base class for all connectome null-model generators.

    Responsibilities:
        - Take a real `igraph.Graph` produced by `GraphBuilder` as baseline input.
        - Generate a randomized counterpart matching designated baseline properties.
        - Ensure all required vertex/edge/graph attributes remain valid for downstream
          preprocessing and error-model simulation.
        - Never mutate the input `real_graph`.
    """

    NAME: str = ""

    @abc.abstractmethod
    def generate(
        self,
        real_graph: igraph.Graph,
        config: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ) -> igraph.Graph:
        """Generate and return a randomized null `igraph.Graph`.

        Args:
            real_graph:
                The unperturbed baseline directed `igraph.Graph`.
            config:
                Optional dictionary of algorithm-specific parameters.
            seed:
                Optional integer random seed for reproducibility.

        Returns:
            A new directed `igraph.Graph` representing the null model.
        """
        pass

    def _validate_null_graph(
        self, null_graph: igraph.Graph, real_graph: igraph.Graph
    ) -> None:
        """Verify that the generated null graph satisfies the framework contract."""
        if not isinstance(null_graph, igraph.Graph):
            raise TypeError(
                f"[{self.NAME}] Expected igraph.Graph, got {type(null_graph).__name__}."
            )
        if not null_graph.is_directed():
            raise ValueError(f"[{self.NAME}] Generated null graph must be directed.")

        if null_graph.vcount() != real_graph.vcount():
            logger.warning(
                f"[{self.NAME}] Null vertex count ({null_graph.vcount()}) differs "
                f"from real vertex count ({real_graph.vcount()})."
            )

        # Validate vertex root_id attribute
        if "root_id" not in null_graph.vertex_attributes():
            raise ValueError(f"[{self.NAME}] Null graph missing required vertex attribute 'root_id'.")

        # Validate edge weight/syn_count attribute
        has_syn = "syn_count" in null_graph.edge_attributes()
        has_weight = "weight" in null_graph.edge_attributes()
        if null_graph.ecount() > 0 and not (has_syn or has_weight):
            raise ValueError(
                f"[{self.NAME}] Null graph edges missing 'syn_count' or 'weight' attribute."
            )

        logger.debug(
            f"[{self.NAME}] Null graph validation passed: "
            f"V={null_graph.vcount()}, E={null_graph.ecount()}."
        )
