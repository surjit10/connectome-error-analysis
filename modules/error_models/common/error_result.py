"""
Phase 008 – Error Model Framework / Error Result
=================================================
Defines :class:`ErrorResult`, the single stable return type of every concrete
error model that subclasses
:class:`~modules.error_models.base_error_model.BaseErrorModel`.

Design changes vs original:
    - ``perturbed_graph`` field is **removed**.
      Error models no longer produce graph copies.
    - Added ``edge_mask``: a boolean list parallel to the baseline graph's
      edge sequence.  True = edge is active; False = edge is suppressed.
    - Added ``weight_updates``: a dict mapping edge index → new weight value
      for edges whose syn_count (or weight) should be scaled.
    - These two objects together fully describe a perturbation without
      ever copying the baseline graph.
    - The Experiment Runner is responsible for building the temporary
      analysis subgraph from the baseline + mask + weight_updates.

All other fields remain identical to the original contract.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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

    The Experiment Runner receives this object and uses ``edge_mask`` and
    ``weight_updates`` to construct a temporary analysis subgraph.
    It must not inspect internal perturbation details beyond these fields.

    Attributes:
        model_name:
            The canonical name of the error model.
        status:
            One of ``SUCCESS``, ``FAILED``, or ``SKIPPED``.
        dataset_name:
            Name of the source dataset.
        runtime_seconds:
            Wall-clock execution time in seconds.
        config_snapshot:
            Shallow copy of the configuration dict passed to the model.
        edge_mask:
            Boolean list, length == graph.ecount() of the baseline graph.
            ``True`` means the edge remains active.
            ``False`` means the edge is suppressed (treated as missing).
            ``None`` when ``status != SUCCESS``.
        weight_updates:
            Dict mapping igraph edge index → updated weight value.
            Only edges whose weight differs from the baseline are listed.
            Empty dict if no weight changes were made.
        perturbation_metadata:
            Free-form dict describing what was changed
            (e.g. ``{"edges_removed": 42, "removal_rate": 0.05}``).
        warnings:
            Non-fatal warning messages produced during execution.
        errors:
            Error messages (populated when ``status == FAILED``).
        extra:
            Reserved for future extensions.
    """

    model_name: str
    status: ErrorModelStatus = ErrorModelStatus.SUCCESS
    dataset_name: str = ""
    runtime_seconds: float = 0.0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    edge_mask: Optional[List[bool]] = None
    weight_updates: Dict[int, float] = field(default_factory=dict)
    added_edges: List[tuple] = field(default_factory=list)
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
    def has_perturbation(self) -> bool:
        """``True`` when a valid edge_mask is available."""
        return self.edge_mask is not None or len(self.added_edges) > 0

    # ------------------------------------------------------------------ #
    # Serialisation helpers                                                #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain ``dict`` (omits the mask itself; stores summary)."""
        active = (
            sum(self.edge_mask) if self.edge_mask is not None else None
        )
        suppressed = (
            len(self.edge_mask) - active
            if (self.edge_mask is not None and active is not None)
            else None
        )
        return {
            "model_name":             self.model_name,
            "status":                 self.status.value,
            "dataset_name":           self.dataset_name,
            "runtime_seconds":        self.runtime_seconds,
            "config_snapshot":        self.config_snapshot,
            "active_edges":           active,
            "suppressed_edges":       suppressed,
            "weight_update_count":    len(self.weight_updates),
            "added_edge_count":       len(self.added_edges),
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
            f"has_perturbation={self.has_perturbation})"
        )

    def __repr__(self) -> str:
        return self.summary()
