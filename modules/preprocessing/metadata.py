"""
Phase 006 – Preprocessing / Graph Metadata
==========================================
Generates a lightweight, reusable description of a graph's structural
properties. Metadata is computed once during preprocessing and carried
forward in the :class:`~modules.preprocessing.prepared_graph.PreparedGraph`.

Design constraints:
    - Describes only the graph topology and dataset identity.
    - Never includes experiment-specific information.
    - Never modifies the graph.
    - All fields are plain Python types so the object is easily serialisable.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import networkx as nx

logger = logging.getLogger(__name__)

# Increment this when the metadata schema changes so that consumers can
# detect stale cached metadata.
_PREPROCESSING_VERSION: str = "1.0.0"


@dataclass
class GraphMetadata:
    """Reusable, read-only description of a graph's structure.

    Produced by :func:`build_metadata` and attached to
    :class:`~modules.preprocessing.prepared_graph.PreparedGraph`.

    Attributes:
        dataset_name:            Source dataset identifier (from ``graph.graph``).
        node_count:              Number of nodes.
        edge_count:              Number of directed edges.
        density:                 Graph density in [0, 1].
        is_directed:             Always ``True`` for FlyWire graphs.
        is_weighted:             ``True`` when at least one edge carries a
                                 ``syn_count`` (or ``weight``) attribute.
        available_node_attrs:    Sorted list of attribute keys present on at
                                 least one node.
        available_edge_attrs:    Sorted list of attribute keys present on at
                                 least one edge.
        preprocessing_timestamp: ISO-8601 UTC timestamp of when this metadata
                                 was generated.
        preprocessing_version:   Schema version string (``_PREPROCESSING_VERSION``).
        extra:                   Reserved for future extensions; always empty
                                 by default.
    """

    dataset_name: str = ""
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    is_directed: bool = True
    is_weighted: bool = False
    available_node_attrs: List[str] = field(default_factory=list)
    available_edge_attrs: List[str] = field(default_factory=list)
    preprocessing_timestamp: str = ""
    preprocessing_version: str = _PREPROCESSING_VERSION
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain ``dict`` representation (useful for JSON export)."""
        return {
            "dataset_name": self.dataset_name,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "density": self.density,
            "is_directed": self.is_directed,
            "is_weighted": self.is_weighted,
            "available_node_attrs": self.available_node_attrs,
            "available_edge_attrs": self.available_edge_attrs,
            "preprocessing_timestamp": self.preprocessing_timestamp,
            "preprocessing_version": self.preprocessing_version,
            "extra": self.extra,
        }


def build_metadata(graph: nx.DiGraph) -> GraphMetadata:
    """Compute and return :class:`GraphMetadata` for *graph*.

    Traverses the graph once to collect all available attribute keys without
    modifying any data.

    Args:
        graph: A :class:`networkx.DiGraph` from the Phase 005 Graph Builder.

    Returns:
        A fully populated :class:`GraphMetadata` instance.
    """
    dataset_name: str = graph.graph.get("dataset_name", "<unknown>")
    node_count: int = graph.number_of_nodes()
    edge_count: int = graph.number_of_edges()

    # Compute density (networkx handles divide-by-zero gracefully).
    density: float = nx.density(graph)

    # Collect unique attribute keys across all nodes (skip empty graphs).
    node_attr_keys: set = set()
    for _, attrs in graph.nodes(data=True):
        node_attr_keys.update(attrs.keys())

    # Collect unique attribute keys across all edges.
    edge_attr_keys: set = set()
    is_weighted: bool = False
    _weight_indicators = {"syn_count", "weight"}

    for _, _, attrs in graph.edges(data=True):
        edge_attr_keys.update(attrs.keys())
        if not is_weighted and bool(attrs.keys() & _weight_indicators):
            is_weighted = True

    metadata = GraphMetadata(
        dataset_name=dataset_name,
        node_count=node_count,
        edge_count=edge_count,
        density=round(density, 10),
        is_directed=graph.is_directed(),
        is_weighted=is_weighted,
        available_node_attrs=sorted(node_attr_keys),
        available_edge_attrs=sorted(edge_attr_keys),
        preprocessing_timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        preprocessing_version=_PREPROCESSING_VERSION,
    )

    logger.info(
        "[Preprocessing/Metadata] %s | nodes=%d edges=%d density=%.6e "
        "weighted=%s node_attrs=%d edge_attrs=%d",
        metadata.dataset_name,
        metadata.node_count,
        metadata.edge_count,
        metadata.density,
        metadata.is_weighted,
        len(metadata.available_node_attrs),
        len(metadata.available_edge_attrs),
    )

    return metadata
