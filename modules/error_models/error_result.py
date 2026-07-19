"""
Phase 008 – Error Model Framework / Error Result
=================================================
Defines :class:`ErrorResult`, the single stable return type of every concrete
error model that subclasses
:class:`~modules.error_models.base_error_model.BaseErrorModel`.

Design constraints:
    - Generic: must hold the output of any future perturbation model
      (missed synapses, false positives, merge errors, split errors, etc.).
    - Contains no experiment-specific fields.
    - All fields are plain Python types (except the perturbed graph) so the
      object can be logged and summarised without domain knowledge.
    - The perturbed graph is a new ``nx.DiGraph`` produced by the concrete
      model — the original ``PreparedGraph`` is never modified.
    - Mirrors the structure of ``AnalysisResult`` (Phase 007) for consistency.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import networkx as nx


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class ErrorModelStatus(enum.Enum):
    """Execution status of a completed (or failed) error model run."""
    SUCCESS = "SUCCESS"
    FAILED  = "FAILED"
    SKIPPED = "SKIPPED"   # e.g. model was inapplicable to this graph


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ErrorResult:
    """Standardised result produced by every concrete error model.

    The Experiment Runner receives this object and passes the perturbed graph
    to an Analysis.  It must not inspect internal perturbation details.

    Attributes:
        model_name:
            The canonical name of the error model (matches the key used in
            :class:`~modules.error_models.error_registry.ErrorRegistry`).
        status:
            One of ``SUCCESS``, ``FAILED``, or ``SKIPPED``.
        dataset_name:
            Name of the source dataset (copied from
            ``PreparedGraph.dataset_name``).
        runtime_seconds:
            Wall-clock execution time in seconds.
        config_snapshot:
            Shallow copy of the configuration dict passed to the model.
        perturbed_graph:
            A *new* :class:`networkx.DiGraph` that is a perturbed copy of the
            original graph.  ``None`` when ``status != SUCCESS``.
        perturbation_metadata:
            Free-form dict describing what was changed (e.g.
            ``{"edges_removed": 42, "removal_rate": 0.05}``).
            Populated by concrete models; empty by default.
        warnings:
            List of non-fatal warning messages produced during execution.
        errors:
            List of error messages (populated when ``status == FAILED``).
        extra:
            Reserved for future extensions.
    """

    model_name: str
    status: ErrorModelStatus = ErrorModelStatus.SUCCESS
    dataset_name: str = ""
    runtime_seconds: float = 0.0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    perturbed_graph: Optional[nx.DiGraph] = None
    perturbation_metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Convenience properties                                               #
    # ------------------------------------------------------------------ #

    @property
    def succeeded(self) -> bool:
        """``True`` iff ``status == SUCCESS``."""
        return self.status == ErrorModelStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """``True`` iff ``status == FAILED``."""
        return self.status == ErrorModelStatus.FAILED

    @property
    def has_perturbed_graph(self) -> bool:
        """``True`` when a perturbed graph is available."""
        return self.perturbed_graph is not None

    # ------------------------------------------------------------------ #
    # Serialisation helpers                                                #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain ``dict`` (omits the graph object itself)."""
        return {
            "model_name":             self.model_name,
            "status":                 self.status.value,
            "dataset_name":           self.dataset_name,
            "runtime_seconds":        self.runtime_seconds,
            "config_snapshot":        self.config_snapshot,
            "has_perturbed_graph":    self.has_perturbed_graph,
            "perturbation_metadata":  self.perturbation_metadata,
            "warnings":               self.warnings,
            "errors":                 self.errors,
            "extra":                  self.extra,
        }

    def summary(self) -> str:
        """Return a compact one-liner for logging."""
        return (
            f"ErrorResult(model={self.model_name!r}, "
            f"status={self.status.value}, "
            f"dataset={self.dataset_name!r}, "
            f"runtime={self.runtime_seconds:.3f}s, "
            f"perturbed_graph={'yes' if self.has_perturbed_graph else 'no'})"
        )

    def __repr__(self) -> str:
        return self.summary()
