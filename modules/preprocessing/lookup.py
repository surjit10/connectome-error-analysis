"""
Phase 006 – Preprocessing / Graph Lookup Index
===============================================
Builds a set of O(1) lookup structures over a NetworkX DiGraph so that
downstream components (Analysis Framework, Error Models, Experiment Runner)
can query graph topology without repeatedly traversing the graph.

All structures are built **once** during preprocessing and stored in
:class:`~modules.preprocessing.prepared_graph.PreparedGraph`.

Design constraints:
    - Read-only view of the graph. Nothing is modified.
    - No graph metrics or statistics are computed here.
    - Lightweight wrappers are preferred over deep copies of large data.
    - All lookups operate on node IDs exactly as present in the graph.

Memory note:
    For graphs with millions of edges the successor / predecessor dicts
    and edge-weight dict can be large. They use shallow references to
    existing Python objects in the graph's adjacency structure wherever
    possible to avoid unnecessary duplication.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class GraphLookup:
    """Pre-computed lookup/index structures for a FlyWire DiGraph.

    Produced by :func:`build_lookup` and attached to
    :class:`~modules.preprocessing.prepared_graph.PreparedGraph`.

    All mappings use the graph's native node ID type (typically ``int``
    for FlyWire ``root_id`` values).

    Attributes:
        node_set:
            ``frozenset`` of all node IDs.  O(1) membership tests.

        node_attrs:
            ``{node_id: {attr_name: value, ...}}`` — direct reference to
            the graph's internal node attribute dicts (no copy).

        successors:
            ``{node_id: [neighbour_id, ...]}`` — out-neighbours (post-synaptic
            partners) for each node.

        predecessors:
            ``{node_id: [neighbour_id, ...]}`` — in-neighbours (pre-synaptic
            partners) for each node.

        adjacency_out:
            ``{src: {dst: edge_attr_dict, ...}}`` — direct reference to
            NetworkX's internal adjacency structure for out-edges.
            Use for O(1) edge-attr access.

        adjacency_in:
            ``{dst: {src: edge_attr_dict, ...}}`` — reverse adjacency for
            in-edges.

        edge_attrs:
            ``{(src, dst): edge_attr_dict}`` — flat edge lookup by endpoint
            pair.  References the same dicts stored in the graph.

        edge_weight:
            ``{(src, dst): float | int | None}`` — synapse count (``syn_count``)
            if present, else ``weight`` if present, else ``None``.  Provides a
            single canonical weight lookup regardless of the attribute name used.

        node_attr_index:
            ``{attr_name: {value: [node_id, ...], ...}}`` — inverted index
            that maps attribute values back to the list of nodes that carry
            them.  Useful for queries such as "find all neurons where
            super_class == 'interneuron'".  Built only for a configurable
            set of node attribute keys.
    """

    node_set: FrozenSet[Any] = field(default_factory=frozenset)
    node_attrs: Dict[Any, Dict[str, Any]] = field(default_factory=dict)
    successors: Dict[Any, List[Any]] = field(default_factory=dict)
    predecessors: Dict[Any, List[Any]] = field(default_factory=dict)
    adjacency_out: Dict[Any, Dict[Any, Dict[str, Any]]] = field(
        default_factory=dict
    )
    adjacency_in: Dict[Any, Dict[Any, Dict[str, Any]]] = field(
        default_factory=dict
    )
    edge_attrs: Dict[tuple, Dict[str, Any]] = field(default_factory=dict)
    edge_weight: Dict[tuple, Optional[float]] = field(default_factory=dict)
    node_attr_index: Dict[str, Dict[Any, List[Any]]] = field(
        default_factory=dict
    )

    # ------------------------------------------------------------------ #
    # Convenience query helpers                                            #
    # ------------------------------------------------------------------ #

    def has_node(self, node_id: Any) -> bool:
        """Return ``True`` if *node_id* exists in the graph."""
        return node_id in self.node_set

    def has_edge(self, src: Any, dst: Any) -> bool:
        """Return ``True`` if the directed edge ``src → dst`` exists."""
        return (src, dst) in self.edge_attrs

    def get_successors(self, node_id: Any) -> List[Any]:
        """Return the out-neighbour list for *node_id* (empty if absent)."""
        return self.successors.get(node_id, [])

    def get_predecessors(self, node_id: Any) -> List[Any]:
        """Return the in-neighbour list for *node_id* (empty if absent)."""
        return self.predecessors.get(node_id, [])

    def get_edge_weight(self, src: Any, dst: Any) -> Optional[float]:
        """Return the canonical weight of edge ``src → dst``, or ``None``."""
        return self.edge_weight.get((src, dst))

    def get_edge_attrs(self, src: Any, dst: Any) -> Dict[str, Any]:
        """Return the attribute dict of edge ``src → dst`` (empty if absent)."""
        return self.edge_attrs.get((src, dst), {})

    def get_nodes_by_attr(self, attr_name: str, value: Any) -> List[Any]:
        """Return all node IDs where ``attr_name == value``.

        Requires *attr_name* to have been included in the index (see
        :func:`build_lookup`).  Returns an empty list if the attribute was
        not indexed or the value is not present.
        """
        return self.node_attr_index.get(attr_name, {}).get(value, [])


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_lookup(
    graph: nx.DiGraph,
    index_node_attrs: Optional[List[str]] = None,
) -> GraphLookup:
    """Build and return a :class:`GraphLookup` for *graph*.

    The graph is traversed in a single pass (plus optional attribute index
    pass) without modification.

    Args:
        graph:
            A :class:`networkx.DiGraph` from the Phase 005 Graph Builder.
        index_node_attrs:
            Optional list of node attribute names for which to build an
            inverted index.  Defaults to a standard set of FlyWire biological
            attributes: ``["super_class", "class_", "soma_side",
            "predicted_nt_type", "top_region"]``.

    Returns:
        A fully populated :class:`GraphLookup`.
    """
    if index_node_attrs is None:
        index_node_attrs = [
            "super_class",
            "class_",
            "soma_side",
            "predicted_nt_type",
            "top_region",
            "flow",
            "body_part",
        ]

    logger.info(
        "[Preprocessing/Lookup] Building lookup structures for '%s' "
        "(%d nodes, %d edges) ...",
        graph.graph.get("dataset_name", "<unknown>"),
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )

    # ------------------------------------------------------------------ #
    # Node structures                                                      #
    # ------------------------------------------------------------------ #

    # node_set – frozenset for O(1) membership.
    node_set: FrozenSet[Any] = frozenset(graph.nodes())

    # node_attrs – shallow reference, no copy of individual dicts.
    node_attrs: Dict[Any, Dict[str, Any]] = dict(graph.nodes(data=True))

    # successors / predecessors – materialised into plain lists once so
    # downstream code does not have to call graph.successors() repeatedly.
    successors: Dict[Any, List[Any]] = {
        n: list(graph.successors(n)) for n in graph.nodes()
    }
    predecessors: Dict[Any, List[Any]] = {
        n: list(graph.predecessors(n)) for n in graph.nodes()
    }

    # ------------------------------------------------------------------ #
    # Adjacency structures                                                 #
    # ------------------------------------------------------------------ #

    # adjacency_out – reference to NetworkX's internal adj dict (no copy).
    adjacency_out: Dict[Any, Dict] = dict(graph.adj)

    # adjacency_in – reverse adjacency.
    adjacency_in: Dict[Any, Dict] = dict(graph.pred)

    # ------------------------------------------------------------------ #
    # Edge structures                                                      #
    # ------------------------------------------------------------------ #

    _weight_key_priority = ("syn_count", "weight")

    edge_attrs: Dict[tuple, Dict[str, Any]] = {}
    edge_weight: Dict[tuple, Optional[float]] = {}

    for src, dst, attrs in graph.edges(data=True):
        key = (src, dst)
        edge_attrs[key] = attrs  # shallow reference

        # Resolve canonical weight.
        w: Optional[float] = None
        for wk in _weight_key_priority:
            if wk in attrs:
                w = attrs[wk]
                break
        edge_weight[key] = w

    # ------------------------------------------------------------------ #
    # Inverted node attribute index                                        #
    # ------------------------------------------------------------------ #

    node_attr_index: Dict[str, Dict[Any, List[Any]]] = {
        attr: {} for attr in index_node_attrs
    }

    for node_id, attrs in graph.nodes(data=True):
        for attr in index_node_attrs:
            val = attrs.get(attr)
            if val is None:
                continue
            bucket = node_attr_index[attr]
            if val not in bucket:
                bucket[val] = []
            bucket[val].append(node_id)

    # ------------------------------------------------------------------ #
    # Assemble and return                                                  #
    # ------------------------------------------------------------------ #

    lookup = GraphLookup(
        node_set=node_set,
        node_attrs=node_attrs,
        successors=successors,
        predecessors=predecessors,
        adjacency_out=adjacency_out,
        adjacency_in=adjacency_in,
        edge_attrs=edge_attrs,
        edge_weight=edge_weight,
        node_attr_index=node_attr_index,
    )

    logger.info(
        "[Preprocessing/Lookup] Done. "
        "Indexed node attrs: %s",
        list(node_attr_index.keys()),
    )

    return lookup
