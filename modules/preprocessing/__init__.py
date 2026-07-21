"""
Phase 006 – Preprocessing
=========================
Public surface of the preprocessing package.

Downstream components (Experiment Runner, Analysis Framework, Error Model
Framework) should import from this package, not from the sub-modules directly.

This package operates exclusively on :class:`igraph.Graph` objects.
NetworkX is not used.

Typical usage::

    from modules.preprocessing import preprocess_graph, PreparedGraph

    prepared = preprocess_graph(graph)
    # Access pre-computed baseline features:
    indegrees = prepared.baseline_features.get("indegree", [])
"""

from .validator import GraphValidator, ValidationReport, ValidationSeverity
from .metadata import GraphMetadata
from .lookup import GraphLookup
from .prepared_graph import PreparedGraph
from .pipeline import preprocess_graph, PreprocessingError

__all__ = [
    # Pipeline entry-point
    "preprocess_graph",
    "PreprocessingError",
    # Data containers
    "PreparedGraph",
    "GraphMetadata",
    "GraphLookup",
    # Validation
    "GraphValidator",
    "ValidationReport",
    "ValidationSeverity",
]

