"""
Phase 008 – Error Model Framework / Base Error Model
=====================================================
Defines :class:`BaseErrorModel`, the abstract base class that every concrete
perturbation model must subclass.

Design constraints:
    - Enforces the Phase 008 execution contract:
        PreparedGraph → Validation → Graph Copy → Perturbation → ErrorResult
    - Never implements biological perturbation logic.
    - Never modifies the original graph.
    - Accepts only :class:`~modules.preprocessing.prepared_graph.PreparedGraph`.
    - Returns only :class:`~modules.error_models.error_result.ErrorResult`.
    - Provides timing, logging, seed management, and error-handling so
      concrete models focus solely on their perturbation algorithm.

Concrete error model authoring guide::

    from modules.error_models.base_error_model import BaseErrorModel
    from modules.error_models.error_result import ErrorResult

    class MissedSynapses(BaseErrorModel):
        NAME = "missed_synapses"

        def _perturb(self, graph_copy, config, result):
            # remove some edges from graph_copy …
            result.perturbation_metadata["edges_removed"] = …

    # Register once:
    from modules.error_models.error_registry import registry
    registry.register(MissedSynapses)
"""

from __future__ import annotations

import abc
import copy
import logging
import time
from typing import Any, Dict, Optional

import networkx as nx

from modules.preprocessing.prepared_graph import PreparedGraph
from .error_result import ErrorResult, ErrorModelStatus
from .exceptions import InvalidInputError

logger = logging.getLogger(__name__)


class BaseErrorModel(abc.ABC):
    """Abstract base for every perturbation model in the FlyWire framework.

    Subclass and implement :meth:`_perturb`.  The framework handles
    input validation, graph copying, timing, seed initialisation, logging,
    and exception wrapping automatically via :meth:`execute`.

    Class attributes:
        NAME (str):
            Canonical identifier used for registration and reporting.
            Every concrete subclass **must** set this to a non-empty string.

    Example::

        class MissedSynapses(BaseErrorModel):
            NAME = "missed_synapses"

            def _perturb(self, graph_copy, config, result):
                rate = config.get("removal_rate", 0.05)
                edges = list(graph_copy.edges())
                to_remove = random.sample(edges, int(len(edges) * rate))
                graph_copy.remove_edges_from(to_remove)
                result.perturbation_metadata["edges_removed"] = len(to_remove)
    """

    NAME: str = ""

    # ------------------------------------------------------------------ #
    # Public API (called by Experiment Runner)                             #
    # ------------------------------------------------------------------ #

    def execute(
        self,
        prepared: PreparedGraph,
        config: Optional[Dict[str, Any]] = None,
        *,
        seed: Optional[int] = None,
    ) -> ErrorResult:
        """Run the perturbation and return a standardised :class:`ErrorResult`.

        This is the **only** method the Experiment Runner should call.

        Steps executed by the framework:
        1. Validate the input (must be a ``PreparedGraph``).
        2. Initialise the random seed if provided.
        3. Create a **deep copy** of the underlying graph so the original is
           never mutated.
        4. Time the call to :meth:`_perturb`.
        5. Catch any exception, record it, and mark the result as ``FAILED``
           without re-raising (the runner inspects ``result.status``).

        Args:
            prepared:
                A :class:`~modules.preprocessing.prepared_graph.PreparedGraph`
                from Phase 006.  Must not be a raw graph.
            config:
                Optional ``dict`` of model-specific configuration.  A snapshot
                is stored in the result.
            seed:
                Optional integer random seed for reproducibility.  Forwarded
                to :meth:`_init_seed`.

        Returns:
            An :class:`ErrorResult` whose ``status`` is ``SUCCESS`` or
            ``FAILED``.  On success, ``result.perturbed_graph`` is set.

        Raises:
            InvalidInputError:
                If *prepared* is not a valid :class:`PreparedGraph`.
        """
        self._validate_input(prepared)

        cfg = config or {}
        result = ErrorResult(
            model_name=self.NAME,
            dataset_name=prepared.dataset_name,
            config_snapshot=copy.copy(cfg),
        )

        if seed is not None:
            self._init_seed(seed)

        logger.info(
            "[ErrorModel/%s] Starting on dataset '%s' (seed=%s).",
            self.NAME, prepared.dataset_name, seed,
        )

        # Create an independent copy of the graph for perturbation.
        graph_copy: nx.DiGraph = prepared.graph.copy()

        t_start = time.perf_counter()

        try:
            self._perturb(graph_copy, cfg, result)
            result.status = ErrorModelStatus.SUCCESS
            result.perturbed_graph = graph_copy
        except InvalidInputError:
            raise  # propagate contract violations immediately
        except Exception as exc:  # noqa: BLE001
            result.status = ErrorModelStatus.FAILED
            result.errors.append(str(exc))
            logger.exception(
                "[ErrorModel/%s] Execution failed on dataset '%s': %s",
                self.NAME, prepared.dataset_name, exc,
            )

        result.runtime_seconds = time.perf_counter() - t_start

        logger.info(
            "[ErrorModel/%s] Finished. status=%s runtime=%.3fs",
            self.NAME, result.status.value, result.runtime_seconds,
        )

        # Safety check: original graph must be unmodified.
        assert prepared.graph is not graph_copy, (
            "BaseErrorModel.execute() must not replace prepared.graph."
        )

        return result

    # ------------------------------------------------------------------ #
    # Abstract method (implemented by concrete models)                     #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def _perturb(
        self,
        graph_copy: nx.DiGraph,
        config: Dict[str, Any],
        result: ErrorResult,
    ) -> None:
        """Implement the perturbation algorithm here.

        Modify *graph_copy* in-place to apply the biological error.
        Populate ``result.perturbation_metadata`` with a description of what
        was changed.
        Append to ``result.warnings`` for non-fatal issues.

        Do **not**:
        - touch the original graph (not passed here by design).
        - set ``result.status`` (the framework sets it after this returns).
        - set ``result.perturbed_graph`` (the framework sets it after this returns).
        - catch exceptions (the framework handles them in :meth:`execute`).

        Args:
            graph_copy: Independent deep copy of the original graph to mutate.
            config:     Configuration dict (may be empty).
            result:     Pre-initialised result object to annotate.
        """
        raise NotImplementedError  # pragma: no cover

    # ------------------------------------------------------------------ #
    # Framework-level helpers                                              #
    # ------------------------------------------------------------------ #

    def _validate_input(self, prepared: Any) -> None:
        """Enforce the input contract.

        Args:
            prepared: Value passed to :meth:`execute`.

        Raises:
            InvalidInputError: On any contract violation.
        """
        if not isinstance(prepared, PreparedGraph):
            raise InvalidInputError(
                f"[ErrorModel/{self.NAME}] Expected a PreparedGraph, "
                f"got {type(prepared).__name__}. "
                "Do not bypass Phase 006 preprocessing."
            )
        if not prepared.is_valid:
            logger.warning(
                "[ErrorModel/%s] PreparedGraph for '%s' has validation errors. "
                "Proceeding with caution.",
                self.NAME, prepared.dataset_name,
            )

    @staticmethod
    def _init_seed(seed: int) -> None:
        """Initialise the Python ``random`` module with *seed*.

        Concrete models that use ``random`` will be automatically reproducible.
        Models using ``numpy.random`` should call ``numpy.random.seed(seed)``
        in their own ``_perturb`` implementation.

        Args:
            seed: Integer random seed.
        """
        import random
        random.seed(seed)
        logger.debug("[ErrorModel] Random seed set to %d.", seed)

    # ------------------------------------------------------------------ #
    # Identity helpers                                                     #
    # ------------------------------------------------------------------ #

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Verify that every concrete subclass declares a non-empty NAME."""
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "__abstractmethods__", None) and not cls.NAME:
            raise TypeError(
                f"Concrete error model {cls.__name__!r} must define a "
                "non-empty class attribute NAME."
            )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.NAME!r})"
