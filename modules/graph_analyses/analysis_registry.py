"""
Phase 007 – Analysis Framework / Analysis Registry
===================================================
Provides :class:`AnalysisRegistry`, a central catalogue of all known
:class:`~modules.graph_analyses.base_analysis.BaseAnalysis` subclasses.

Design constraints:
    - Generic: the registry knows nothing about specific algorithms.
    - Thread-safe for read access (Python's GIL protects dict operations).
    - Analyses are registered by their ``BaseAnalysis.NAME`` string.
    - Duplicate registrations raise :class:`~modules.graph_analyses.exceptions.RegistryError`
      unless ``overwrite=True`` is passed.
    - The module-level ``registry`` singleton is the canonical instance used
      by the Experiment Runner.

Usage example::

    # In a concrete analysis module:
    from modules.graph_analyses.analysis_registry import registry
    from modules.graph_analyses.base_analysis import BaseAnalysis

    class DegreeAnalysis(BaseAnalysis):
        NAME = "degree"
        def _run(self, prepared, config, result):
            ...

    registry.register(DegreeAnalysis)

    # In the Experiment Runner:
    from modules.graph_analyses.analysis_registry import registry

    analysis = registry.instantiate("degree")
    result = analysis.execute(prepared_graph)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from .base_analysis import BaseAnalysis
from .exceptions import RegistryError

logger = logging.getLogger(__name__)


class AnalysisRegistry:
    """Central catalogue of available graph analyses.

    Each analysis is stored by its :attr:`~modules.graph_analyses.base_analysis.BaseAnalysis.NAME`.

    Attributes:
        _analyses: Internal mapping of ``name → BaseAnalysis subclass``.

    Example::

        registry = AnalysisRegistry()
        registry.register(DegreeAnalysis)
        registry.register(PageRankAnalysis)

        analysis = registry.instantiate("degree")
        result = analysis.execute(prepared)
    """

    def __init__(self) -> None:
        self._analyses: Dict[str, Type[BaseAnalysis]] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register(
        self,
        analysis_cls: Type[BaseAnalysis],
        *,
        overwrite: bool = False,
    ) -> None:
        """Add *analysis_cls* to the registry.

        Args:
            analysis_cls:
                A concrete subclass of :class:`~modules.graph_analyses.base_analysis.BaseAnalysis`.
                Its ``NAME`` attribute is used as the registry key.
            overwrite:
                If ``True``, silently replace any previously registered class
                with the same ``NAME``.  Defaults to ``False``.

        Raises:
            RegistryError:
                If *analysis_cls* is not a valid subclass, has an empty
                ``NAME``, or a class with the same ``NAME`` is already
                registered and ``overwrite`` is ``False``.
        """
        self._validate_cls(analysis_cls)

        name = analysis_cls.NAME

        if name in self._analyses and not overwrite:
            raise RegistryError(
                f"An analysis named {name!r} is already registered "
                f"({self._analyses[name].__name__}). "
                "Pass overwrite=True to replace it."
            )

        self._analyses[name] = analysis_cls
        logger.info(
            "[AnalysisRegistry] Registered analysis %r → %s.",
            name, analysis_cls.__name__,
        )

    def unregister(self, name: str) -> None:
        """Remove the analysis registered under *name*.

        Args:
            name: The ``NAME`` of the analysis to remove.

        Raises:
            RegistryError: If no analysis with *name* is registered.
        """
        if name not in self._analyses:
            raise RegistryError(
                f"Cannot unregister {name!r}: no analysis with that name is registered."
            )
        removed = self._analyses.pop(name)
        logger.info(
            "[AnalysisRegistry] Unregistered analysis %r (%s).",
            name, removed.__name__,
        )

    # ------------------------------------------------------------------ #
    # Retrieval                                                            #
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> Type[BaseAnalysis]:
        """Return the analysis **class** registered under *name*.

        Args:
            name: The ``NAME`` of the desired analysis.

        Returns:
            The :class:`~modules.graph_analyses.base_analysis.BaseAnalysis`
            subclass.

        Raises:
            RegistryError: If no analysis with *name* is registered.
        """
        if name not in self._analyses:
            raise RegistryError(
                f"No analysis named {name!r} is registered. "
                f"Available: {self.list_names()}"
            )
        return self._analyses[name]

    def instantiate(
        self,
        name: str,
        *args: object,
        **kwargs: object,
    ) -> BaseAnalysis:
        """Instantiate and return the analysis registered under *name*.

        All positional and keyword arguments are forwarded to the class
        constructor.  Most concrete analyses take no constructor arguments,
        but this forwards them for flexibility.

        Args:
            name:     The ``NAME`` of the desired analysis.
            *args:    Forwarded to the analysis constructor.
            **kwargs: Forwarded to the analysis constructor.

        Returns:
            An instance of the requested analysis.

        Raises:
            RegistryError: If no analysis with *name* is registered.
        """
        cls = self.get(name)
        return cls(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Introspection                                                        #
    # ------------------------------------------------------------------ #

    def list_names(self) -> List[str]:
        """Return a sorted list of all registered analysis names."""
        return sorted(self._analyses.keys())

    def list_classes(self) -> List[Type[BaseAnalysis]]:
        """Return a sorted-by-name list of all registered analysis classes."""
        return [self._analyses[n] for n in self.list_names()]

    def is_registered(self, name: str) -> bool:
        """Return ``True`` if an analysis with *name* is registered."""
        return name in self._analyses

    def __len__(self) -> int:
        return len(self._analyses)

    def __repr__(self) -> str:
        return (
            f"AnalysisRegistry(analyses={self.list_names()})"
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_cls(analysis_cls: object) -> None:
        """Raise :class:`RegistryError` if *analysis_cls* is not usable."""
        if not isinstance(analysis_cls, type):
            raise RegistryError(
                f"Expected a class, got {type(analysis_cls).__name__!r}."
            )
        if not issubclass(analysis_cls, BaseAnalysis):
            raise RegistryError(
                f"{analysis_cls.__name__!r} must subclass BaseAnalysis."
            )
        if not analysis_cls.NAME:
            raise RegistryError(
                f"{analysis_cls.__name__!r} has an empty NAME attribute."
            )


# ---------------------------------------------------------------------------
# Module-level singleton — import and use this everywhere.
# ---------------------------------------------------------------------------

#: The canonical registry instance.  Import this in concrete analysis modules
#: to register analyses, and in the Experiment Runner to retrieve them.
registry: AnalysisRegistry = AnalysisRegistry()
