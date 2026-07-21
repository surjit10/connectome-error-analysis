"""
Phase 006 – Preprocessing / Structural Validator
=================================================
Inspects an :class:`igraph.Graph` produced by the Graph Builder and
produces a :class:`ValidationReport` describing any structural problems.

Design constraints (from Phase 006 spec):
    - NEVER modifies the graph.
    - NEVER removes biological information.
    - Reports problems; does not fix them.
    - Returns the same :class:`ValidationReport` structure regardless of
      graph size so that downstream components can rely on a stable contract.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import igraph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Severity enum
# ---------------------------------------------------------------------------

class ValidationSeverity(enum.Enum):
    """Severity level of a single validation finding."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Individual finding
# ---------------------------------------------------------------------------

@dataclass
class ValidationFinding:
    """A single finding from structural validation.

    Attributes:
        severity:    How critical this finding is.
        code:        Short machine-readable identifier (e.g. ``"SELF_LOOP"``).
        message:     Human-readable description.
        detail:      Optional extra context (e.g. the offending node ID).
    """
    severity: ValidationSeverity
    code: str
    message: str
    detail: Optional[Any] = None


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

@dataclass
class ValidationReport:
    """Reusable container summarising the structural health of a graph.

    Produced by :class:`GraphValidator` and attached to the
    :class:`~modules.preprocessing.prepared_graph.PreparedGraph`.

    Attributes:
        dataset_name:       Name of the source dataset (from ``graph["dataset_name"]``).
        node_count:         Number of vertices in the graph.
        edge_count:         Number of edges in the graph.
        is_directed:        Whether the graph is directed.
        isolated_node_ids:  Set of root_id values with neither in- nor out-edges.
        self_loop_edges:    List of ``(src_root_id, dst_root_id)`` self-loops.
        duplicate_edges:    List of ``(src_root_id, dst_root_id)`` duplicates.
        invalid_edge_refs:  Always empty for igraph (igraph guarantees valid refs).
        missing_node_attrs: Dict mapping root_id → list of missing expected attrs.
        missing_edge_attrs: Dict mapping ``(src_id, dst_id)`` → list of missing attrs.
        findings:           Full ordered list of :class:`ValidationFinding`.
        passed:             ``True`` when no ERROR-level findings exist.
    """
    dataset_name: str = ""
    node_count: int = 0
    edge_count: int = 0
    is_directed: bool = True
    isolated_node_ids: Set[Any] = field(default_factory=set)
    self_loop_edges: List[tuple] = field(default_factory=list)
    duplicate_edges: List[tuple] = field(default_factory=list)
    invalid_edge_refs: List[tuple] = field(default_factory=list)
    missing_node_attrs: Dict[Any, List[str]] = field(default_factory=dict)
    missing_edge_attrs: Dict[tuple, List[str]] = field(default_factory=dict)
    findings: List[ValidationFinding] = field(default_factory=list)
    passed: bool = True

    # ------------------------------------------------------------------ #
    # Convenience helpers                                                  #
    # ------------------------------------------------------------------ #

    def errors(self) -> List[ValidationFinding]:
        """Return only ERROR-level findings."""
        return [f for f in self.findings if f.severity == ValidationSeverity.ERROR]

    def warnings(self) -> List[ValidationFinding]:
        """Return only WARNING-level findings."""
        return [f for f in self.findings if f.severity == ValidationSeverity.WARNING]

    def summary_lines(self) -> List[str]:
        """Return a compact human-readable summary as a list of strings."""
        lines = [
            f"Dataset       : {self.dataset_name}",
            f"Nodes         : {self.node_count}",
            f"Edges         : {self.edge_count}",
            f"Directed      : {self.is_directed}",
            f"Isolated nodes: {len(self.isolated_node_ids)}",
            f"Self-loops    : {len(self.self_loop_edges)}",
            f"Invalid refs  : {len(self.invalid_edge_refs)}",
            f"Errors        : {len(self.errors())}",
            f"Warnings      : {len(self.warnings())}",
            f"Passed        : {self.passed}",
        ]
        return lines


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class GraphValidator:
    """Structural validator for FlyWire igraph.Graph objects.

    Validates a graph produced by the Phase 005 Graph Builder and returns a
    :class:`ValidationReport`. The graph is **never mutated**.

    Args:
        expected_node_attrs:  Optional list of vertex attribute names that every
                              vertex is expected to carry.
        expected_edge_attrs:  Optional list of edge attribute names that every
                              edge is expected to carry.

    Example::

        validator = GraphValidator(
            expected_node_attrs=["super_class", "soma_side"],
            expected_edge_attrs=["syn_count"],
        )
        report = validator.validate(graph)
        if not report.passed:
            for finding in report.errors():
                print(finding.message)
    """

    def __init__(
        self,
        expected_node_attrs: Optional[List[str]] = None,
        expected_edge_attrs: Optional[List[str]] = None,
    ) -> None:
        self._expected_node_attrs: List[str] = expected_node_attrs or []
        self._expected_edge_attrs: List[str] = expected_edge_attrs or []

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def validate(self, graph: igraph.Graph) -> ValidationReport:
        """Run all structural checks and return a :class:`ValidationReport`.

        Args:
            graph: An :class:`igraph.Graph` from the Graph Builder.

        Returns:
            A fully populated :class:`ValidationReport`.
        """
        report = ValidationReport()

        # Populate summary fields before checks.
        report.dataset_name = graph["dataset_name"] if "dataset_name" in graph.attributes() else "<unknown>"
        report.node_count = graph.vcount()
        report.edge_count = graph.ecount()
        report.is_directed = graph.is_directed()

        self._check_graph_exists(graph, report)
        self._check_is_directed(graph, report)
        self._check_null_root_ids(graph, report)
        self._check_isolated_nodes(graph, report)
        self._check_self_loops(graph, report)
        self._check_duplicate_edges(graph, report)
        self._check_node_attributes(graph, report)
        self._check_edge_attributes(graph, report)

        # Determine overall pass/fail.
        report.passed = len(report.errors()) == 0

        self._log_summary(report)
        return report

    # ------------------------------------------------------------------ #
    # Individual checks                                                    #
    # ------------------------------------------------------------------ #

    def _check_graph_exists(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Verify the graph object is not None and is a recognised type."""
        if graph is None:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="NULL_GRAPH",
                message="Graph object is None.",
            ))
            return

        if not isinstance(graph, igraph.Graph):
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="WRONG_GRAPH_TYPE",
                message=(
                    f"Expected igraph.Graph, "
                    f"got {type(graph).__name__}."
                ),
            ))

    def _check_is_directed(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Confirm the graph is directed (FlyWire synapses are directed)."""
        if not graph.is_directed():
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="UNDIRECTED_GRAPH",
                message=(
                    "Graph is undirected. FlyWire connectome graphs must be "
                    "directed (pre_root_id → post_root_id)."
                ),
            ))

    def _check_null_root_ids(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Check for vertices whose root_id attribute is None."""
        if "root_id" not in graph.vertex_attributes():
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="MISSING_ROOT_ID_ATTR",
                message="Vertex attribute 'root_id' is not present on the graph.",
            ))
            return

        null_indices = [
            v.index for v in graph.vs if v["root_id"] is None
        ]
        if null_indices:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="NULL_NODE_ID",
                message=f"Graph contains {len(null_indices)} vertex/vertices with None root_id.",
                detail=null_indices[:10],
            ))

    def _check_isolated_nodes(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Identify vertices with no in-edges AND no out-edges."""
        # igraph: degree == 0 for both in and out means isolated.
        isolated_indices = graph.vs.select(_degree_eq=0).indices
        if isolated_indices:
            if "root_id" in graph.vertex_attributes():
                isolated_ids = {graph.vs[i]["root_id"] for i in isolated_indices}
            else:
                isolated_ids = set(isolated_indices)
            report.isolated_node_ids = isolated_ids
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="ISOLATED_NODES",
                message=(
                    f"{len(isolated_ids)} isolated vertex/vertices found "
                    f"(no in- or out-edges)."
                ),
                detail=list(isolated_ids)[:10],
            ))

    def _check_self_loops(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Detect edges from a vertex to itself."""
        loop_edges = graph.es.select(_source_eq=None)  # placeholder; use is_loop
        # igraph provides is_loop() on EdgeSeq
        loop_indices = [e.index for e in graph.es if graph.is_loop(e.index)]

        if loop_indices:
            if "root_id" in graph.vertex_attributes():
                loops = [
                    (
                        graph.vs[graph.es[i].source]["root_id"],
                        graph.vs[graph.es[i].target]["root_id"],
                    )
                    for i in loop_indices
                ]
            else:
                loops = [
                    (graph.es[i].source, graph.es[i].target)
                    for i in loop_indices
                ]
            report.self_loop_edges = loops
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="SELF_LOOPS",
                message=f"{len(loops)} self-loop edge(s) detected.",
                detail=loops[:10],
            ))

    def _check_duplicate_edges(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Detect duplicate (src, dst) pairs."""
        if graph.has_multiple():
            # Collect multi-edges using igraph.
            seen: Dict[tuple, int] = {}
            duplicates = []
            for e in graph.es:
                key = (e.source, e.target)
                seen[key] = seen.get(key, 0) + 1
            duplicates = [k for k, cnt in seen.items() if cnt > 1]
            if "root_id" in graph.vertex_attributes():
                duplicates = [
                    (graph.vs[s]["root_id"], graph.vs[t]["root_id"])
                    for s, t in duplicates
                ]
            report.duplicate_edges = duplicates
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="DUPLICATE_EDGES",
                message=f"{len(duplicates)} duplicate edge(s) detected.",
                detail=duplicates[:10],
            ))

    def _check_node_attributes(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Report vertices missing any of the expected attribute keys."""
        if not self._expected_node_attrs:
            return

        available_vertex_attrs = set(graph.vertex_attributes())
        missing: Dict[Any, List[str]] = {}
        has_root_id = "root_id" in available_vertex_attrs

        for v in graph.vs:
            absent = [
                attr for attr in self._expected_node_attrs
                if attr not in available_vertex_attrs or v[attr] is None
            ]
            if absent:
                node_key = v["root_id"] if has_root_id else v.index
                missing[node_key] = absent

        report.missing_node_attrs = missing

        if missing:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="MISSING_NODE_ATTRS",
                message=(
                    f"{len(missing)} vertex/vertices missing one or more expected "
                    f"attributes: {self._expected_node_attrs}."
                ),
                detail=dict(list(missing.items())[:5]),
            ))

    def _check_edge_attributes(
        self, graph: igraph.Graph, report: ValidationReport
    ) -> None:
        """Report edges missing any of the expected attribute keys."""
        if not self._expected_edge_attrs:
            return

        available_edge_attrs = set(graph.edge_attributes())
        missing: Dict[tuple, List[str]] = {}
        has_root_id = "root_id" in graph.vertex_attributes()

        for e in graph.es:
            absent = [
                attr for attr in self._expected_edge_attrs
                if attr not in available_edge_attrs or e[attr] is None
            ]
            if absent:
                if has_root_id:
                    key = (
                        graph.vs[e.source]["root_id"],
                        graph.vs[e.target]["root_id"],
                    )
                else:
                    key = (e.source, e.target)
                missing[key] = absent

        report.missing_edge_attrs = missing

        if missing:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="MISSING_EDGE_ATTRS",
                message=(
                    f"{len(missing)} edge(s) missing one or more expected "
                    f"attributes: {self._expected_edge_attrs}."
                ),
                detail=dict(list(missing.items())[:5]),
            ))

    # ------------------------------------------------------------------ #
    # Logging                                                              #
    # ------------------------------------------------------------------ #

    def _log_summary(self, report: ValidationReport) -> None:
        log_fn = logger.info if report.passed else logger.warning
        log_fn(
            "[Preprocessing/Validator] %s | nodes=%d edges=%d "
            "errors=%d warnings=%d passed=%s",
            report.dataset_name,
            report.node_count,
            report.edge_count,
            len(report.errors()),
            len(report.warnings()),
            report.passed,
        )
