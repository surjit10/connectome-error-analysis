"""
Phase 006 – Preprocessing / Pipeline Entry-Point
=================================================
Provides :func:`preprocess_graph`, the single public function that
orchestrates all preprocessing steps in the correct order.

Usage::

    import networkx as nx
    from modules.preprocessing import preprocess_graph

    graph: nx.DiGraph = graph_builder.build(dataset)
    prepared = preprocess_graph(graph)

    # Downstream:
    experiment_runner.run(prepared)

Pipeline order (must match Phase 006 spec):

    Graph API Object
         │
         ▼
    Structural Validation   ← validator.py
         │
         ▼
    Validation Report       ← validator.ValidationReport
         │
         ▼
    Metadata Generation     ← metadata.py
         │
         ▼
    Lookup / Index Gen.     ← lookup.py
         │
         ▼
    PreparedGraph           ← prepared_graph.py

Design constraints:
    - Never modifies the graph.
    - Never applies error models.
    - Never computes graph statistics.
    - Never exports results.
    - Only orchestrates the preprocessing sub-steps.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import networkx as nx

from .validator import GraphValidator, ValidationReport
from .metadata import build_metadata, GraphMetadata
from .lookup import build_lookup, GraphLookup
from .prepared_graph import PreparedGraph

logger = logging.getLogger(__name__)


def preprocess_graph(
    graph: nx.DiGraph,
    *,
    expected_node_attrs: Optional[List[str]] = None,
    expected_edge_attrs: Optional[List[str]] = None,
    index_node_attrs: Optional[List[str]] = None,
    raise_on_error: bool = False,
) -> PreparedGraph:
    """Run the full Phase 006 preprocessing pipeline on *graph*.

    Executes the following steps in order:

    1. **Structural Validation** — checks topology, self-loops, isolated
       nodes, missing attributes, and invalid references.
    2. **Metadata Generation** — derives a lightweight structural description.
    3. **Lookup Index Building** — constructs O(1) accessor structures.
    4. **PreparedGraph Assembly** — packages all outputs into the contract
       object consumed by downstream phases.

    The original *graph* object is never mutated.

    Args:
        graph:
            A :class:`networkx.DiGraph` produced by the Phase 005 Graph
            Builder.
        expected_node_attrs:
            Optional list of node attribute names that each node is expected
            to carry.  Nodes lacking any of these will appear as warnings in
            the :class:`~modules.preprocessing.validator.ValidationReport`.
            Defaults to ``None`` (no attribute expectations).
        expected_edge_attrs:
            Optional list of edge attribute names that each edge is expected
            to carry.  Defaults to ``None``.
        index_node_attrs:
            Optional list of node attribute names for which to build an
            inverted attribute index inside
            :class:`~modules.preprocessing.lookup.GraphLookup`.
            Defaults to the standard FlyWire biological columns
            (``super_class``, ``class_``, ``soma_side``, etc.).
        raise_on_error:
            If ``True``, raise a :class:`PreprocessingError` when the
            validation report contains ERROR-level findings.  Default is
            ``False`` (the caller inspects ``prepared.is_valid`` instead).

    Returns:
        A :class:`~modules.preprocessing.prepared_graph.PreparedGraph`
        wrapping the graph and all preprocessing artefacts.

    Raises:
        PreprocessingError:
            Only when *raise_on_error* is ``True`` and validation fails.

    Example::

        prepared = preprocess_graph(
            graph,
            expected_edge_attrs=["syn_count"],
            raise_on_error=True,
        )
    """
    logger.info(
        "[Preprocessing/Pipeline] Starting preprocessing for '%s'.",
        graph.graph.get("dataset_name", "<unknown>"),
    )

    # ------------------------------------------------------------------ #
    # Step 1: Structural Validation                                        #
    # ------------------------------------------------------------------ #

    validator = GraphValidator(
        expected_node_attrs=expected_node_attrs,
        expected_edge_attrs=expected_edge_attrs,
    )
    report: ValidationReport = validator.validate(graph)

    if not report.passed:
        logger.warning(
            "[Preprocessing/Pipeline] Validation found %d error(s) for '%s'. "
            "Proceeding with is_valid=False.",
            len(report.errors()),
            report.dataset_name,
        )
        if raise_on_error:
            error_msgs = "; ".join(
                f.message for f in report.errors()
            )
            raise PreprocessingError(
                f"Graph validation failed for '{report.dataset_name}': "
                f"{error_msgs}"
            )

    # ------------------------------------------------------------------ #
    # Step 2: Metadata Generation                                          #
    # ------------------------------------------------------------------ #

    metadata: GraphMetadata = build_metadata(graph)

    # ------------------------------------------------------------------ #
    # Step 3: Lookup / Index Generation                                    #
    # ------------------------------------------------------------------ #

    lookup: GraphLookup = build_lookup(
        graph,
        index_node_attrs=index_node_attrs,
    )

    # ------------------------------------------------------------------ #
    # Step 4: Assemble PreparedGraph                                       #
    # ------------------------------------------------------------------ #

    prepared = PreparedGraph(
        graph=graph,
        validation_report=report,
        metadata=metadata,
        lookup=lookup,
    )

    logger.info(
        "[Preprocessing/Pipeline] Preprocessing complete. %s",
        prepared.summary(),
    )

    return prepared


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class PreprocessingError(Exception):
    """Raised by :func:`preprocess_graph` when validation fails and
    *raise_on_error* is ``True``."""
