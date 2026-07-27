"""
Phase 007 – Analysis Framework / Base Analysis
===============================================
Defines :class:`BaseAnalysis`, the abstract base class that every concrete
graph analysis must subclass.

Design constraints:
    - Enforces the Phase 007 execution contract:
        PreparedGraph → Input Validation → Analysis Execution → AnalysisResult
    - Never implements graph algorithms — those belong to concrete subclasses.
    - Never modifies the graph.
    - Accepts only :class:`~modules.preprocessing.prepared_graph.PreparedGraph`
      (never raw DataFrames, CSVs, or bare ``nx.DiGraph`` objects).
    - Returns only :class:`~modules.graph_analyses.analysis_result.AnalysisResult`.
    - Provides timing, logging, and error-handling scaffolding so concrete
      analyses can focus purely on their algorithm.

Concrete analysis authoring guide::

    from modules.graph_analyses.base_analysis import BaseAnalysis
    from modules.graph_analyses.analysis_result import AnalysisResult

    class DegreeAnalysis(BaseAnalysis):
        NAME = "degree"

        def _run(self, prepared, config, result):
            # compute degree metrics …
            result.metrics["mean_out_degree"] = …

    # Register it:
    from modules.graph_analyses.analysis_registry import registry
    registry.register(DegreeAnalysis)
"""

from __future__ import annotations

import abc
import copy
import logging
import time
from typing import Any, Dict, Optional

from modules.preprocessing.common.prepared_graph import PreparedGraph
from .analysis_result import AnalysisResult, AnalysisStatus
from .exceptions import AnalysisExecutionError, InvalidInputError

logger = logging.getLogger(__name__)


class BaseAnalysis(abc.ABC):
    """Abstract base for every graph analysis in the FlyWire framework.

    Subclass and implement :meth:`_run`.  The framework handles input
    validation, timing, logging, and error wrapping automatically via
    :meth:`execute`.

    Class attributes:
        NAME (str):
            The canonical identifier used for registration and reporting.
            Every subclass **must** set this to a non-empty string.

    Example::

        class DegreeAnalysis(BaseAnalysis):
            NAME = "degree"

            def _run(self, prepared, config, result):
                # prepared.graph is an igraph.Graph (directed).
                in_degs  = prepared.graph.indegree()
                out_degs = prepared.graph.outdegree()
                n = prepared.graph.vcount()
                result.metrics["mean_in_degree"]  = sum(in_degs)  / n if n else 0.0
                result.metrics["mean_out_degree"] = sum(out_degs) / n if n else 0.0
    """

    # Subclasses MUST override this with a unique, non-empty string.
    NAME: str = ""

    # ------------------------------------------------------------------ #
    # Public API (called by Experiment Runner)                             #
    # ------------------------------------------------------------------ #

    def execute(
        self,
        prepared: PreparedGraph,
        config: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """Run the analysis and return a standardised :class:`AnalysisResult`.

        This is the **only** method the Experiment Runner should call.

        The method:
        1. Validates the input against the framework contract.
        2. Initialises a :class:`AnalysisResult` with metadata.
        3. Times the call to :meth:`_run`.
        4. Catches and records any exception without propagating it
           (the runner inspects ``result.status`` instead).

        Args:
            prepared:
                A :class:`~modules.preprocessing.prepared_graph.PreparedGraph`
                produced by Phase 006.  **Must not be a raw graph.**
            config:
                Optional ``dict`` of analysis-specific configuration.  Passed
                through unchanged to :meth:`_run`.  A snapshot is stored in
                the result.

        Returns:
            An :class:`AnalysisResult` whose ``status`` is ``SUCCESS`` or
            ``FAILED``.

        Raises:
            InvalidInputError:
                If *prepared* is not a valid :class:`PreparedGraph`.
        """
        self._validate_input(prepared)

        result = AnalysisResult(
            analysis_name=self.NAME,
            dataset_name=prepared.dataset_name,
            config_snapshot=copy.copy(config or {}),
        )

        logger.info(
            "[Analysis/%s] Starting on dataset '%s'.",
            self.NAME, prepared.dataset_name,
        )

        t_start = time.perf_counter()

        try:
            self._run(prepared, config or {}, result)
            result.status = AnalysisStatus.SUCCESS
        except InvalidInputError:
            raise  # propagate input contract violations immediately
        except Exception as exc:  # noqa: BLE001
            result.status = AnalysisStatus.FAILED
            result.errors.append(str(exc))
            logger.exception(
                "[Analysis/%s] Execution failed on dataset '%s': %s",
                self.NAME, prepared.dataset_name, exc,
            )

        result.runtime_seconds = time.perf_counter() - t_start

        logger.info(
            "[Analysis/%s] Finished. status=%s runtime=%.3fs metrics=%d",
            self.NAME,
            result.status.value,
            result.runtime_seconds,
            len(result.metrics),
        )

        return result

    # ------------------------------------------------------------------ #
    # Abstract method (implemented by concrete analyses)                   #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def _run(
        self,
        prepared: PreparedGraph,
        config: Dict[str, Any],
        result: AnalysisResult,
    ) -> None:
        """Implement the analysis algorithm here.

        Populate ``result.metrics`` with the analysis output.
        Append to ``result.warnings`` for non-fatal issues.
        Do **not** catch exceptions — the framework handles that in
        :meth:`execute`.
        Do **not** set ``result.status`` — the framework sets it.

        Args:
            prepared: The preprocessed graph (read-only).
            config:   Configuration dict (may be empty).
            result:   Pre-initialised result object to populate.
        """
        raise NotImplementedError  # pragma: no cover

    # ------------------------------------------------------------------ #
    # Framework-level validation                                           #
    # ------------------------------------------------------------------ #

    def _validate_input(self, prepared: Any) -> None:
        """Enforce the input contract for this analysis.

        Args:
            prepared: The value passed to :meth:`execute`.

        Raises:
            InvalidInputError: On any contract violation.
        """
        if not isinstance(prepared, PreparedGraph):
            raise InvalidInputError(
                f"[Analysis/{self.NAME}] Expected a PreparedGraph, "
                f"got {type(prepared).__name__}. "
                "Do not bypass Phase 006 preprocessing."
            )

        if not prepared.is_valid:
            # A PreparedGraph with validation errors is still accepted but
            # a warning is emitted.  Concrete analyses can inspect
            # prepared.validation_report for more detail.
            logger.warning(
                "[Analysis/%s] PreparedGraph for '%s' has validation errors. "
                "Proceeding with caution.",
                self.NAME, prepared.dataset_name,
            )

    # ------------------------------------------------------------------ #
    # Identity helpers                                                     #
    # ------------------------------------------------------------------ #

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Verify that every subclass declares a non-empty NAME."""
        super().__init_subclass__(**kwargs)
        # Skip check for intermediate abstract classes that leave NAME empty.
        if not getattr(cls, "__abstractmethods__", None) and not cls.NAME:
            raise TypeError(
                f"Concrete analysis class {cls.__name__!r} must define a "
                "non-empty class attribute NAME."
            )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.NAME!r})"
