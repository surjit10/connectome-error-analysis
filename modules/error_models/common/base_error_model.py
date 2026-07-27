"""
Phase 008 – Error Model Framework / Base Error Model
=====================================================
Defines :class:`BaseErrorModel`, the abstract base class that every concrete
perturbation model must subclass.

Architecture changes vs original:
    - ``graph.copy()`` is **completely removed**.
      The baseline graph is never copied.
    - Error models receive the baseline :class:`PreparedGraph` in read-only
      mode and produce an :class:`ErrorResult` containing:
          ``edge_mask``      — boolean list (True = active, False = suppressed)
          ``weight_updates`` — dict {edge_index: new_weight}
    - The Experiment Runner uses these two arrays to build a temporary
      :class:`igraph.Graph` subgraph for the duration of one analysis pass,
      then destroys it.
    - Randomness is provided via ``numpy.random.default_rng(seed)`` — a
      locally-scoped RNG object, never the global random state.
    - The RNG is passed into ``_perturb()`` as an argument so concrete models
      never need to call ``numpy.random.seed()`` or ``random.seed()``.

Concrete error model authoring guide::

    from modules.error_models.base_error_model import BaseErrorModel
    from modules.error_models.error_result import ErrorResult

    class MissedSynapses(BaseErrorModel):
        NAME = "missed_synapses"

        def _perturb(self, prepared, config, result, rng):
            # Use rng to sample which edges to suppress.
            n_edges = prepared.graph.ecount()
            rate = config.get("removal_rate", 0.05)
            mask = rng.random(n_edges) >= rate   # True = keep
            result.edge_mask = mask.tolist()
            result.perturbation_metadata["edges_removed"] = int((~mask).sum())

    from modules.error_models.error_registry import registry
    registry.register(MissedSynapses)
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from modules.preprocessing.common.prepared_graph import PreparedGraph
from .error_result import ErrorResult, ErrorModelStatus
from .exceptions import InvalidInputError

logger = logging.getLogger(__name__)


class BaseErrorModel(abc.ABC):
    """Abstract base for every perturbation model in the FlyWire framework.

    Subclass and implement :meth:`_perturb`.  The framework handles
    input validation, timing, RNG initialisation, logging, and exception
    wrapping automatically via :meth:`execute`.

    Class attributes:
        NAME (str):
            Canonical identifier used for registration and reporting.
            Every concrete subclass **must** set this to a non-empty string.
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
        2. Initialise a local numpy RNG from *seed*.
        3. Call :meth:`_perturb` — concrete model populates ``result.edge_mask``
           and ``result.weight_updates``.
        4. Validate that the mask length matches graph edge count.
        5. Catch any exception, record it, mark as ``FAILED``.

        The baseline graph is **never copied or mutated**.

        Args:
            prepared:
                A :class:`~modules.preprocessing.prepared_graph.PreparedGraph`
                from Phase 006.  Must not be a raw graph.
            config:
                Optional ``dict`` of model-specific configuration.
            seed:
                Optional integer random seed for reproducibility.

        Returns:
            An :class:`ErrorResult` whose ``status`` is ``SUCCESS`` or
            ``FAILED``.

        Raises:
            InvalidInputError:
                If *prepared* is not a valid :class:`PreparedGraph`.
        """
        self._validate_input(prepared)

        cfg = config or {}
        result = ErrorResult(
            model_name=self.NAME,
            dataset_name=prepared.dataset_name,
            config_snapshot=dict(cfg),
        )

        # Initialise a local, non-global RNG.
        rng = np.random.default_rng(seed)

        logger.info(
            "[ErrorModel/%s] Starting on dataset '%s' (seed=%s).",
            self.NAME, prepared.dataset_name, seed,
        )

        t_start = time.perf_counter()

        try:
            self._perturb(prepared, cfg, result, rng)
            # Validate mask length if provided.
            if result.edge_mask is not None:
                expected_len = prepared.graph.ecount()
                actual_len = len(result.edge_mask)
                if actual_len != expected_len:
                    raise ValueError(
                        f"edge_mask length {actual_len} does not match "
                        f"graph edge count {expected_len}."
                    )
            result.status = ErrorModelStatus.SUCCESS
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

        return result

    # ------------------------------------------------------------------ #
    # Abstract method (implemented by concrete models)                     #
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def _perturb(
        self,
        prepared: PreparedGraph,
        config: Dict[str, Any],
        result: ErrorResult,
        rng: np.random.Generator,
    ) -> None:
        """Implement the perturbation algorithm here.

        Populate ``result.edge_mask`` with a boolean list parallel to
        ``prepared.graph.es`` (True = active, False = suppressed).

        Populate ``result.weight_updates`` with a dict mapping igraph edge
        index → new weight for edges whose weight should change.

        Populate ``result.perturbation_metadata`` with a description of what
        was changed.

        Do **NOT**:
        - copy or mutate ``prepared.graph`` (it is the immutable baseline).
        - set ``result.status`` (the framework sets it after this returns).
        - call ``random.seed()`` or ``numpy.random.seed()`` — use *rng* only.
        - catch exceptions (the framework handles them in :meth:`execute`).

        Args:
            prepared: The preprocessed baseline graph (read-only).
            config:   Configuration dict (may be empty).
            result:   Pre-initialised result object to populate.
            rng:      numpy random Generator seeded by the framework.
        """
        raise NotImplementedError  # pragma: no cover

    # ------------------------------------------------------------------ #
    # Framework-level helpers                                              #
    # ------------------------------------------------------------------ #

    def _validate_input(self, prepared: Any) -> None:
        """Enforce the input contract.

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
