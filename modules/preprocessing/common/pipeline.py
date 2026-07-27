"""
Phase 006 – Preprocessing / Pipeline Entry-Point
=================================================
Provides :func:`preprocess_graph`, the single public function that
orchestrates all preprocessing steps in the correct order.

This module operates exclusively on :class:`igraph.Graph` objects produced
by the Phase 005 Graph Builder.  NetworkX is not used and must not be
imported.

Usage::

    import igraph
    from modules.preprocessing import preprocess_graph

    graph: igraph.Graph = graph_builder.build(dataset)
    prepared = preprocess_graph(graph)

    # Downstream:
    experiment_runner.run(prepared)

Pipeline order (matches Phase 006 spec):

    igraph.Graph (from GraphBuilder)
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
    Baseline Feature Extr.  ← _extract_features() below
         │
         ▼
    PreparedGraph           ← prepared_graph.py

Design constraints:
    - Never modifies the graph.
    - Never applies error models.
    - Never computes graph statistics (only baseline structural features).
    - Never exports results.
    - Only orchestrates the preprocessing sub-steps.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Any, List, Optional

import igraph

from ..common.validator import GraphValidator, ValidationReport
from ..common.metadata import build_metadata, GraphMetadata
from ..common.lookup import build_lookup, GraphLookup
from ..common.prepared_graph import PreparedGraph
from ..missed_synapses.biological_features import extract_biological_features

logger = logging.getLogger(__name__)


def preprocess_graph(
    graph: igraph.Graph,
    *,
    expected_node_attrs: Optional[List[str]] = None,
    expected_edge_attrs: Optional[List[str]] = None,
    index_node_attrs: Optional[List[str]] = None,
    raise_on_error: bool = False,
    feature_config: Optional[Dict[str, Any]] = None,
) -> PreparedGraph:
    """Run the full Phase 006 preprocessing pipeline on *graph*.

    Executes the following steps in order:

    1. **Structural Validation** — checks topology, self-loops, isolated
       nodes, missing attributes, and invalid references.
    2. **Metadata Generation** — derives a lightweight structural description.
    3. **Lookup Index Building** — constructs O(1) accessor structures.
    4. **Baseline Feature Extraction** — computes indegree, outdegree,
       total_degree, PageRank, reciprocal_ratio, hub_neighbor_count, and
       two_hop_size exactly once.
    5. **PreparedGraph Assembly** — packages all outputs into the contract
       object consumed by downstream phases.

    The original *graph* object is never mutated.

    Args:
        graph:
            An :class:`igraph.Graph` produced by the Phase 005 Graph Builder.
        expected_node_attrs:
            Optional list of vertex attribute names that each vertex is
            expected to carry.  Defaults to ``None`` (no expectations).
        expected_edge_attrs:
            Optional list of edge attribute names that each edge is expected
            to carry.  Defaults to ``None``.
        index_node_attrs:
            Optional list of vertex attribute names for which to build an
            inverted attribute index inside
            :class:`~modules.preprocessing.lookup.GraphLookup`.
        raise_on_error:
            If ``True``, raise :class:`PreprocessingError` when the
            validation report contains ERROR-level findings.  Default is
            ``False`` (the caller inspects ``prepared.is_valid`` instead).
        feature_config:
            Optional dict controlling which baseline features to compute.
            Recognised keys (all default ``True``):
                ``indegree``, ``outdegree``, ``total_degree``,
                ``pagerank``, ``pagerank_damping`` (float, default 0.85),
                ``reciprocal_ratio``, ``hub_neighbor_count``, ``two_hop_size``.

    Returns:
        A :class:`~modules.preprocessing.prepared_graph.PreparedGraph`
        wrapping the graph and all preprocessing artefacts.

    Raises:
        PreprocessingError:
            Only when *raise_on_error* is ``True`` and validation fails.
        TypeError:
            If *graph* is not an :class:`igraph.Graph`.
    """
    if not isinstance(graph, igraph.Graph):
        raise TypeError(
            f"preprocess_graph() expects an igraph.Graph, "
            f"got {type(graph).__name__}. "
            "Ensure the Graph Builder produces an igraph.Graph."
        )

    dataset_name = (
        graph["dataset_name"] if "dataset_name" in graph.attributes() else "<unknown>"
    )
    logger.info(
        "[Preprocessing/Pipeline] Starting preprocessing for '%s'.",
        dataset_name,
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
            error_msgs = "; ".join(f.message for f in report.errors())
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
    # Step 4: Baseline Feature Extraction (computed once)                 #
    # ------------------------------------------------------------------ #

    fcfg = feature_config or {}
    baseline_features: Dict[str, Any] = _extract_features(graph, fcfg)

    # ------------------------------------------------------------------ #
    # Step 5: Assemble PreparedGraph                                       #
    # ------------------------------------------------------------------ #

    prepared = PreparedGraph(
        graph=graph,
        validation_report=report,
        metadata=metadata,
        lookup=lookup,
        baseline_features=baseline_features,
    )

    # ------------------------------------------------------------------ #
    # Step 6: Biological Edge Feature Extraction                           #
    # ------------------------------------------------------------------ #
    
    edge_features = extract_biological_features(prepared)
    prepared.edge_features = edge_features

    logger.info(
        "[Preprocessing/Pipeline] Preprocessing complete. %s",
        prepared.summary(),
    )

    return prepared


# ---------------------------------------------------------------------------
# Baseline feature extraction
# ---------------------------------------------------------------------------

def _extract_features(
    graph: igraph.Graph,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute reusable baseline structural features for *graph*.

    Features are computed exactly once during preprocessing and stored in
    :attr:`~modules.preprocessing.prepared_graph.PreparedGraph.baseline_features`.
    Downstream analyses use these arrays directly rather than recomputing them.

    No biological logic is performed here — only generic graph-structural
    quantities that igraph computes natively.

    Args:
        graph:  An :class:`igraph.Graph` from the Graph Builder.
        config: Feature switches from preprocessing config.

    Returns:
        A dict mapping feature name → value/list.
    """
    n = graph.vcount()
    e = graph.ecount()
    features: Dict[str, Any] = {}

    if n == 0:
        logger.warning(
            "[Preprocessing/Features] Graph has 0 vertices; "
            "skipping all feature computation."
        )
        return features

    # ── Degree sequences ────────────────────────────────────────────────

    if config.get("indegree", True):
        features["indegree"] = graph.indegree()

    if config.get("outdegree", True):
        features["outdegree"] = graph.outdegree()

    if config.get("total_degree", True):
        in_deg = features.get("indegree") or graph.indegree()
        out_deg = features.get("outdegree") or graph.outdegree()
        features["total_degree"] = [i + o for i, o in zip(in_deg, out_deg)]

    # ── PageRank ─────────────────────────────────────────────────────────

    if config.get("pagerank", True):
        damping = float(config.get("pagerank_damping", 0.85))
        try:
            features["pagerank"] = graph.pagerank(damping=damping, directed=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[Preprocessing/Features] PageRank computation failed: %s", exc
            )

    # ── Reciprocal ratio ─────────────────────────────────────────────────
    # Fraction of directed edges (u→v) that also have a reverse edge (v→u).

    if config.get("reciprocal_ratio", True):
        if e > 0:
            try:
                reciprocal_count = sum(
                    1 for e_obj in graph.es
                    if graph.are_adjacent(e_obj.target, e_obj.source)
                )
                features["reciprocal_ratio"] = reciprocal_count / e
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[Preprocessing/Features] Reciprocal ratio failed: %s", exc
                )
        else:
            features["reciprocal_ratio"] = 0.0

    # ── Hub neighbour count ──────────────────────────────────────────────
    # For each vertex v, count the distinct out-neighbours of v's out-neighbours
    # (i.e. the size of the 1-hop neighbourhood of v's successors, excluding v
    # itself).  This is a lightweight proxy for hub centrality.

    if config.get("hub_neighbor_count", True):
        try:
            hub_counts: List[int] = []
            for v_idx in range(n):
                successors = set(graph.successors(v_idx))
                hub_set: set = set()
                for s in successors:
                    hub_set.update(graph.successors(s))
                hub_set.discard(v_idx)
                hub_counts.append(len(hub_set))
            features["hub_neighbor_count"] = hub_counts
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[Preprocessing/Features] Hub neighbour count failed: %s", exc
            )

    # ── Two-hop reachable set size ───────────────────────────────────────
    # Number of distinct vertices reachable from v in at most 2 directed hops.

    if config.get("two_hop_size", True):
        try:
            two_hop: List[int] = []
            for v_idx in range(n):
                one_hop = set(graph.successors(v_idx))
                two_hop_set = set(one_hop)
                for s in one_hop:
                    two_hop_set.update(graph.successors(s))
                two_hop_set.discard(v_idx)
                two_hop.append(len(two_hop_set))
            features["two_hop_size"] = two_hop
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[Preprocessing/Features] Two-hop size failed: %s", exc
            )

    logger.info(
        "[Preprocessing/Features] Extracted features: %s",
        list(features.keys()),
    )
    return features


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class PreprocessingError(Exception):
    """Raised by :func:`preprocess_graph` when validation fails and
    *raise_on_error* is ``True``."""
