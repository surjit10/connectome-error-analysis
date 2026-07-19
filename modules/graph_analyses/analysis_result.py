"""
Phase 007 – Analysis Framework / Analysis Result
=================================================
Defines :class:`AnalysisResult`, the single, stable return type of every
concrete analysis that subclasses :class:`~modules.graph_analyses.base_analysis.BaseAnalysis`.

Design constraints:
    - Must be generic enough to hold the output of any future analysis
      (degree, PageRank, community detection, conserved circuits, etc.).
    - Must contain no experiment-specific or perturbation-specific fields.
    - All fields are plain Python types so the object is easily serialisable
      and can be consumed by the Statistics Engine and Export Manager without
      those modules knowing anything about specific analyses.
    - Immutable after construction (fields set once; call-sites should not
      mutate the object).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class AnalysisStatus(enum.Enum):
    """Execution status of a completed (or failed) analysis."""
    SUCCESS = "SUCCESS"
    FAILED  = "FAILED"
    SKIPPED = "SKIPPED"   # e.g. analysis was not applicable to this graph


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """Standardised result produced by every concrete analysis.

    The Experiment Runner, Statistics Engine, and Export Manager all consume
    this object.  They must not inspect the ``metrics`` dict structure in
    order to function — they only rely on the top-level fields.

    Attributes:
        analysis_name:
            The canonical name of the analysis that produced this result
            (matches the key used in :class:`~modules.graph_analyses.
            analysis_registry.AnalysisRegistry`).
        status:
            One of ``SUCCESS``, ``FAILED``, or ``SKIPPED``.
        dataset_name:
            Name of the dataset the analysis was run on (copied from
            ``PreparedGraph.dataset_name``).
        runtime_seconds:
            Wall-clock execution time in seconds.  Set by
            :meth:`~modules.graph_analyses.base_analysis.BaseAnalysis.execute`
            using the framework's timing utilities.
        config_snapshot:
            A shallow copy of the configuration dict passed to the analysis.
            Empty dict if no configuration was provided.
        metrics:
            The analysis-specific output.  Each concrete analysis populates
            this with whatever key/value pairs it produces.  The keys and
            value types are documented by the concrete analysis, not here.
            Example: ``{"mean_degree": 3.14, "max_degree": 512}``.
        warnings:
            List of non-fatal human-readable warning messages produced during
            execution.
        errors:
            List of error messages (only populated when ``status == FAILED``).
        extra:
            Reserved for future extensions.  Always empty by default.

    Example (Experiment Runner perspective)::

        result = analysis.execute(prepared_graph)

        if result.status == AnalysisStatus.SUCCESS:
            stats_engine.record(result)
        else:
            logger.error(result.errors)
    """

    analysis_name: str
    status: AnalysisStatus = AnalysisStatus.SUCCESS
    dataset_name: str = ""
    runtime_seconds: float = 0.0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Convenience helpers                                                  #
    # ------------------------------------------------------------------ #

    @property
    def succeeded(self) -> bool:
        """``True`` iff ``status == SUCCESS``."""
        return self.status == AnalysisStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """``True`` iff ``status == FAILED``."""
        return self.status == AnalysisStatus.FAILED

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain ``dict`` representation for serialisation."""
        return {
            "analysis_name":    self.analysis_name,
            "status":           self.status.value,
            "dataset_name":     self.dataset_name,
            "runtime_seconds":  self.runtime_seconds,
            "config_snapshot":  self.config_snapshot,
            "metrics":          self.metrics,
            "warnings":         self.warnings,
            "errors":           self.errors,
            "extra":            self.extra,
        }

    def summary(self) -> str:
        """Return a compact one-liner for logging."""
        return (
            f"AnalysisResult(name={self.analysis_name!r}, "
            f"status={self.status.value}, "
            f"dataset={self.dataset_name!r}, "
            f"runtime={self.runtime_seconds:.3f}s, "
            f"metrics={len(self.metrics)})"
        )

    def __repr__(self) -> str:
        return self.summary()
