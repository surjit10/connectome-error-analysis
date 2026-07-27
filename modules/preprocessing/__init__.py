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

from .common.validator import GraphValidator, ValidationReport, ValidationSeverity
from .common.metadata import GraphMetadata
from .common.lookup import GraphLookup
from .common.prepared_graph import PreparedGraph
from .common.pipeline import preprocess_graph, PreprocessingError
from .false_synapses.candidate_generator import CandidateGenerator

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
    # False-synapse candidate generation
    "CandidateGenerator",
]
