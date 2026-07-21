"""
Phase 006 – Preprocessing / PreparedGraph
==========================================
Wraps an igraph.Graph together with the products of preprocessing
(validation report, metadata, lookup index) into a single, stable object
that the Experiment Runner receives.

Design constraints:
    - Lightweight wrapper — the original graph is stored by reference, not
      copied.
    - Provides a read-only interface; the underlying graph must not be
      mutated once wrapped.
    - All fields populated by the preprocessing pipeline are available as
      first-class attributes so downstream phases do not need to import
      sub-modules of the preprocessing package.
    - No experiment logic, perturbation logic, or statistics belong here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import igraph

from .metadata import GraphMetadata
from .lookup import GraphLookup
from .validator import ValidationReport

logger = logging.getLogger(__name__)


@dataclass
class PreparedGraph:
    """The central output of Phase 006 Preprocessing.

    Wraps an :class:`igraph.Graph` with its associated preprocessing
    artifacts.  All downstream phases (Experiment Runner, Analysis Framework,
    Error Model Framework) receive this object and should use it instead of
    the raw graph wherever possible.

    Attributes:
        graph:
            The original :class:`igraph.Graph` produced by the Phase 005
            Graph Builder.  **Do not mutate this object.**  Error models must
            work on the edge-mask / weight-array abstraction, never on copies
            of this graph.
        validation_report:
            :class:`~modules.preprocessing.validator.ValidationReport`
            produced by :class:`~modules.preprocessing.validator.GraphValidator`.
        metadata:
            :class:`~modules.preprocessing.metadata.GraphMetadata` describing
            the graph's structural properties.
        lookup:
            :class:`~modules.preprocessing.lookup.GraphLookup` providing O(1)
            lookup structures.
        dataset_name:
            Convenience accessor — mirrors ``graph["dataset_name"]``.
        is_valid:
            ``True`` when the validation report contains no ERROR-level
            findings.

    Example::

        from modules.preprocessing import preprocess_graph

        prepared = preprocess_graph(graph)

        # Use metadata.
        print(prepared.metadata.node_count)

        # Use lookup for fast edge access.
        weight = prepared.lookup.get_edge_weight(src_id, dst_id)

        # Pass the original graph to an analysis.
        analysis.run(prepared.graph)
    """

    graph: igraph.Graph
    validation_report: ValidationReport
    metadata: GraphMetadata
    lookup: GraphLookup
    dataset_name: str = ""
    is_valid: bool = True

    def __post_init__(self) -> None:
        # Synchronise convenience fields from the report/graph after init.
        if not self.dataset_name:
            self.dataset_name = (
                self.metadata.dataset_name
                or self.graph["dataset_name"]
            )
        self.is_valid = self.validation_report.passed

        logger.info(
            "[Preprocessing/PreparedGraph] Created PreparedGraph for '%s' | "
            "valid=%s nodes=%d edges=%d",
            self.dataset_name,
            self.is_valid,
            self.metadata.node_count,
            self.metadata.edge_count,
        )

    # ------------------------------------------------------------------ #
    # Convenience helpers used by downstream phases                        #
    # ------------------------------------------------------------------ #

    def node_count(self) -> int:
        """Return the number of nodes (delegates to metadata, O(1))."""
        return self.metadata.node_count

    def edge_count(self) -> int:
        """Return the number of edges (delegates to metadata, O(1))."""
        return self.metadata.edge_count

    def summary(self) -> str:
        """Return a compact human-readable one-liner summary."""
        return (
            f"PreparedGraph(dataset={self.dataset_name!r}, "
            f"nodes={self.metadata.node_count}, "
            f"edges={self.metadata.edge_count}, "
            f"valid={self.is_valid})"
        )

    def __repr__(self) -> str:
        return self.summary()
