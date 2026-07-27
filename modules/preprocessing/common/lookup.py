"""
Phase 006 – Preprocessing / Graph Lookup Index
===============================================
Builds a set of O(1) lookup structures over an igraph.Graph so that
downstream components (Analysis Framework, Error Models, Experiment Runner)
can query graph topology without repeatedly traversing the graph.

All structures are built **once** during preprocessing and stored in
:class:`~modules.preprocessing.prepared_graph.PreparedGraph`.

Design constraints:
    - Read-only view of the graph. Nothing is modified.
    - No graph metrics or statistics are computed here.
    - Lightweight wrappers preferred over deep copies of large data.
    - All lookups operate on biological root_id values exactly as loaded.

Biological ID note:
    igraph uses internal integer vertex indices (0..N-1).
    The ``GraphLookup`` translates all public-facing queries to/from
    root_id values using the ``id_to_idx`` / ``id_map`` mappings stored in
    the graph by the Graph Builder.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set

import igraph

logger = logging.getLogger(__name__)


@dataclass
class GraphLookup:
    """Pre-computed lookup/index structures for a FlyWire igraph.Graph.

    Produced by :func:`build_lookup` and attached to
    :class:`~modules.preprocessing.prepared_graph.PreparedGraph`.

    All mappings use biological root_id values (not igraph vertex indices).

    Attributes:
        node_set:
            ``frozenset`` of all root_id values.  O(1) membership tests.

        id_to_idx:
            ``{root_id: igraph_vertex_index}`` — forward mapping.

        id_map:
            ``{igraph_vertex_index: root_id}`` — reverse mapping.

        node_attrs:
            ``{root_id: {attr_name: value, ...}}`` — vertex attribute dicts
            keyed by biological ID.

        successors:
            ``{root_id: [neighbour_root_id, ...]}`` — out-neighbours.

        predecessors:
            ``{root_id: [neighbour_root_id, ...]}`` — in-neighbours.

        adjacency_out:
            ``{src_root_id: {dst_root_id: {attr: val, ...}, ...}}`` —
            out-edge attribute lookup.

        adjacency_in:
            ``{dst_root_id: {src_root_id: {attr: val, ...}, ...}}`` —
            in-edge attribute lookup.

        edge_attrs:
            ``{(src_root_id, dst_root_id): {attr: val, ...}}`` —
            flat edge lookup by biological endpoint pair.

        edge_weight:
            ``{(src_root_id, dst_root_id): float | None}`` — syn_count
            (or weight) if present, else None.

        node_attr_index:
            ``{attr_name: {value: [root_id, ...]}}`` — inverted attribute
            index built for a configurable set of vertex attribute keys.
    """

    node_set: FrozenSet[Any] = field(default_factory=frozenset)
    id_to_idx: Dict[Any, int] = field(default_factory=dict)
    id_map: Dict[int, Any] = field(default_factory=dict)
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
        """Return ``True`` if *node_id* (root_id) exists in the graph."""
        return node_id in self.node_set

    def has_edge(self, src: Any, dst: Any) -> bool:
        """Return ``True`` if the directed edge ``src → dst`` exists."""
        return (src, dst) in self.edge_attrs

    def get_successors(self, node_id: Any) -> List[Any]:
        """Return the out-neighbour root_id list (empty if absent)."""
        return self.successors.get(node_id, [])

    def get_predecessors(self, node_id: Any) -> List[Any]:
        """Return the in-neighbour root_id list (empty if absent)."""
        return self.predecessors.get(node_id, [])

    def get_edge_weight(self, src: Any, dst: Any) -> Optional[float]:
        """Return the canonical weight of edge ``src → dst``, or ``None``."""
        return self.edge_weight.get((src, dst))

    def get_edge_attrs(self, src: Any, dst: Any) -> Dict[str, Any]:
        """Return the attribute dict of edge ``src → dst`` (empty if absent)."""
        return self.edge_attrs.get((src, dst), {})

    def get_nodes_by_attr(self, attr_name: str, value: Any) -> List[Any]:
        """Return all root_id values where ``attr_name == value``."""
        return self.node_attr_index.get(attr_name, {}).get(value, [])


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_lookup(
    graph: igraph.Graph,
    index_node_attrs: Optional[List[str]] = None,
) -> GraphLookup:
    """Build and return a :class:`GraphLookup` for *graph*.

    The graph is traversed in a single pass without modification.

    Args:
        graph:
            An :class:`igraph.Graph` from the Phase 005 Graph Builder.
            Must have vertex attribute "root_id" and graph attributes
            "id_to_idx" and "id_map" set by the builder.
        index_node_attrs:
            Optional list of vertex attribute names for which to build an
            inverted index.  Defaults to a standard set of FlyWire biological
            attributes.

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

    dataset_name = (
        graph["dataset_name"]
        if "dataset_name" in graph.attributes()
        else "<unknown>"
    )
    logger.info(
        "[Preprocessing/Lookup] Building lookup structures for '%s' "
        "(%d nodes, %d edges) ...",
        dataset_name,
        graph.vcount(),
        graph.ecount(),
    )

    # Retrieve the ID mappings stored by the Graph Builder.
    id_to_idx: Dict[Any, int] = graph["id_to_idx"] if "id_to_idx" in graph.attributes() else {}
    id_map: Dict[int, Any] = graph["id_map"] if "id_map" in graph.attributes() else {}

    # ------------------------------------------------------------------ #
    # Vertex attribute structures                                          #
    # ------------------------------------------------------------------ #

    has_root_id = "root_id" in graph.vertex_attributes()
    vertex_attr_names = graph.vertex_attributes()

    node_set: FrozenSet[Any] = frozenset(id_map.values()) if id_map else frozenset()

    node_attrs: Dict[Any, Dict[str, Any]] = {}
    successors: Dict[Any, List[Any]] = {}
    predecessors: Dict[Any, List[Any]] = {}

    for v in graph.vs:
        root_id = v["root_id"] if has_root_id else v.index
        # Build attribute dict for this vertex.
        v_attrs = {attr: v[attr] for attr in vertex_attr_names}
        node_attrs[root_id] = v_attrs

        # Successors (out-neighbours) — translated to root_ids.
        succ_indices = graph.successors(v.index)
        successors[root_id] = [
            id_map.get(i, i) for i in succ_indices
        ]

        # Predecessors (in-neighbours) — translated to root_ids.
        pred_indices = graph.predecessors(v.index)
        predecessors[root_id] = [
            id_map.get(i, i) for i in pred_indices
        ]

    # ------------------------------------------------------------------ #
    # Edge attribute structures                                            #
    # ------------------------------------------------------------------ #

    _weight_key_priority = ("syn_count", "weight")
    edge_attr_names = graph.edge_attributes()

    edge_attrs: Dict[tuple, Dict[str, Any]] = {}
    edge_weight: Dict[tuple, Optional[float]] = {}
    adjacency_out: Dict[Any, Dict[Any, Dict[str, Any]]] = {n: {} for n in node_set}
    adjacency_in: Dict[Any, Dict[Any, Dict[str, Any]]] = {n: {} for n in node_set}

    for e in graph.es:
        src_root = id_map.get(e.source, e.source) if has_root_id else e.source
        dst_root = id_map.get(e.target, e.target) if has_root_id else e.target

        e_attrs = {attr: e[attr] for attr in edge_attr_names}
        key = (src_root, dst_root)
        edge_attrs[key] = e_attrs

        # Resolve canonical weight.
        w: Optional[float] = None
        for wk in _weight_key_priority:
            if wk in e_attrs and e_attrs[wk] is not None:
                w = e_attrs[wk]
                break
        edge_weight[key] = w

        adjacency_out.setdefault(src_root, {})[dst_root] = e_attrs
        adjacency_in.setdefault(dst_root, {})[src_root] = e_attrs

    # ------------------------------------------------------------------ #
    # Inverted vertex attribute index                                      #
    # ------------------------------------------------------------------ #

    node_attr_index: Dict[str, Dict[Any, List[Any]]] = {
        attr: {} for attr in index_node_attrs
    }

    for root_id, attrs in node_attrs.items():
        for attr in index_node_attrs:
            val = attrs.get(attr)
            if val is None:
                continue
            bucket = node_attr_index[attr]
            if val not in bucket:
                bucket[val] = []
            bucket[val].append(root_id)

    # ------------------------------------------------------------------ #
    # Assemble and return                                                  #
    # ------------------------------------------------------------------ #

    lookup = GraphLookup(
        node_set=node_set,
        id_to_idx=id_to_idx,
        id_map=id_map,
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
