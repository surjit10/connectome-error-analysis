"""
Phase 006 – Preprocessing / Structural Validator
=================================================
Inspects a :class:`networkx.DiGraph` produced by the Graph Builder and
produces a :class:`ValidationReport` describing any structural problems.

Design constraints (from Phase 006 spec):
    - NEVER modifies the graph.
    - NEVER removes biological information.
    - Reports problems; does not fix them (unless an explicit cleaning
      strategy is provided and enabled – currently reserved for future use).
    - Returns the same :class:`ValidationReport` structure regardless of
      graph size so that downstream components can rely on a stable contract.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import networkx as nx

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
        dataset_name:       Name of the source dataset (from ``graph.graph``).
        node_count:         Number of nodes in the graph.
        edge_count:         Number of edges in the graph.
        is_directed:        Whether the graph is directed.
        isolated_node_ids:  Set of node IDs with neither in- nor out-edges.
        self_loop_edges:    List of ``(src, dst)`` tuples that are self-loops.
        duplicate_edges:    List of ``(src, dst)`` pairs found more than once
                            (only meaningful in MultiDiGraph; always empty for
                            standard DiGraph which silently merges duplicates).
        invalid_edge_refs:  List of ``(src, dst)`` edges whose endpoints do
                            not appear as nodes.
        missing_node_attrs: Dict mapping node ID → list of missing expected
                            attribute names.
        missing_edge_attrs: Dict mapping ``(src, dst)`` → list of missing
                            expected attribute names.
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
    """Structural validator for FlyWire NetworkX DiGraphs.

    Validates a graph produced by the Phase 005 Graph Builder and returns a
    :class:`ValidationReport`. The graph is **never mutated**.

    Args:
        expected_node_attrs:  Optional list of node attribute names that every
                              node is expected to carry.  Nodes missing any of
                              these will be reported as warnings.
        expected_edge_attrs:  Optional list of edge attribute names that every
                              edge is expected to carry.  Missing attrs are
                              reported as warnings.

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

    def validate(self, graph: nx.DiGraph) -> ValidationReport:
        """Run all structural checks and return a :class:`ValidationReport`.

        Args:
            graph: A :class:`networkx.DiGraph` from the Graph Builder.

        Returns:
            A fully populated :class:`ValidationReport`.
        """
        report = ValidationReport()

        # Populate summary fields before checks so they are always present.
        report.dataset_name = graph.graph.get("dataset_name", "<unknown>")
        report.node_count = graph.number_of_nodes()
        report.edge_count = graph.number_of_edges()
        report.is_directed = graph.is_directed()

        self._check_graph_exists(graph, report)
        self._check_is_directed(graph, report)
        self._check_node_id_uniqueness(graph, report)
        self._check_isolated_nodes(graph, report)
        self._check_self_loops(graph, report)
        self._check_invalid_edge_refs(graph, report)
        self._check_node_attributes(graph, report)
        self._check_edge_attributes(graph, report)

        # Determine overall pass/fail.
        report.passed = len(report.errors()) == 0

        self._log_summary(report)
        return report

    # ------------------------------------------------------------------ #
    # Individual checks (each appends to report.findings)                  #
    # ------------------------------------------------------------------ #

    def _check_graph_exists(
        self, graph: nx.DiGraph, report: ValidationReport
    ) -> None:
        """Verify the graph object is not None and is a recognised type."""
        if graph is None:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="NULL_GRAPH",
                message="Graph object is None.",
            ))
            return

        if not isinstance(graph, (nx.DiGraph, nx.MultiDiGraph)):
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="WRONG_GRAPH_TYPE",
                message=(
                    f"Expected nx.DiGraph or nx.MultiDiGraph, "
                    f"got {type(graph).__name__}."
                ),
            ))

    def _check_is_directed(
        self, graph: nx.DiGraph, report: ValidationReport
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

    def _check_node_id_uniqueness(
        self, graph: nx.DiGraph, report: ValidationReport
    ) -> None:
        """Node IDs in a NetworkX graph are inherently unique by construction.

        This check verifies internal consistency (no None node IDs) rather
        than re-implementing what NetworkX already guarantees.
        """
        none_nodes = [n for n in graph.nodes if n is None]
        if none_nodes:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="NULL_NODE_ID",
                message=f"Graph contains {len(none_nodes)} node(s) with None ID.",
                detail=none_nodes[:10],  # show at most 10 examples
            ))

    def _check_isolated_nodes(
        self, graph: nx.DiGraph, report: ValidationReport
    ) -> None:
        """Identify nodes with no in-edges AND no out-edges."""
        isolated: Set[Any] = set(nx.isolates(graph))
        report.isolated_node_ids = isolated

        if isolated:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="ISOLATED_NODES",
                message=(
                    f"{len(isolated)} isolated node(s) found "
                    f"(no in- or out-edges)."
                ),
                detail=list(isolated)[:10],
            ))

    def _check_self_loops(
        self, graph: nx.DiGraph, report: ValidationReport
    ) -> None:
        """Detect edges from a node to itself."""
        loops = list(nx.selfloop_edges(graph))
        report.self_loop_edges = loops

        if loops:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="SELF_LOOPS",
                message=f"{len(loops)} self-loop edge(s) detected.",
                detail=loops[:10],
            ))

    def _check_invalid_edge_refs(
        self, graph: nx.DiGraph, report: ValidationReport
    ) -> None:
        """Detect edges whose endpoints are not present as nodes.

        In a standard NetworkX graph built via ``add_edges_from`` this cannot
        happen (NetworkX auto-creates nodes), but this check guards against
        manual manipulation of the graph after construction.
        """
        node_set: Set[Any] = set(graph.nodes)
        invalid: List[tuple] = []
        for src, dst in graph.edges():
            if src not in node_set or dst not in node_set:
                invalid.append((src, dst))
        report.invalid_edge_refs = invalid

        if invalid:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.ERROR,
                code="INVALID_EDGE_REFS",
                message=(
                    f"{len(invalid)} edge(s) reference node IDs not present "
                    f"in the node set."
                ),
                detail=invalid[:10],
            ))

    def _check_node_attributes(
        self, graph: nx.DiGraph, report: ValidationReport
    ) -> None:
        """Report nodes missing any of the expected attribute keys."""
        if not self._expected_node_attrs:
            return

        missing: Dict[Any, List[str]] = {}
        for node, attrs in graph.nodes(data=True):
            absent = [
                attr for attr in self._expected_node_attrs
                if attr not in attrs
            ]
            if absent:
                missing[node] = absent

        report.missing_node_attrs = missing

        if missing:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="MISSING_NODE_ATTRS",
                message=(
                    f"{len(missing)} node(s) are missing one or more expected "
                    f"attributes: {self._expected_node_attrs}."
                ),
                detail=dict(list(missing.items())[:5]),
            ))

    def _check_edge_attributes(
        self, graph: nx.DiGraph, report: ValidationReport
    ) -> None:
        """Report edges missing any of the expected attribute keys."""
        if not self._expected_edge_attrs:
            return

        missing: Dict[tuple, List[str]] = {}
        for src, dst, attrs in graph.edges(data=True):
            absent = [
                attr for attr in self._expected_edge_attrs
                if attr not in attrs
            ]
            if absent:
                missing[(src, dst)] = absent

        report.missing_edge_attrs = missing

        if missing:
            report.findings.append(ValidationFinding(
                severity=ValidationSeverity.WARNING,
                code="MISSING_EDGE_ATTRS",
                message=(
                    f"{len(missing)} edge(s) are missing one or more expected "
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
