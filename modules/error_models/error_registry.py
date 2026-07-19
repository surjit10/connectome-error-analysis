"""
Phase 008 – Error Model Framework / Error Registry
===================================================
Provides :class:`ErrorRegistry`, the central catalogue of all known
:class:`~modules.error_models.base_error_model.BaseErrorModel` subclasses,
and the module-level ``registry`` singleton.

Design constraints:
    - Generic: the registry knows nothing about specific perturbations.
    - Mirrors :class:`~modules.graph_analyses.analysis_registry.AnalysisRegistry`
      (Phase 007) for consistency.
    - Models are keyed by their ``BaseErrorModel.NAME`` string.
    - Duplicate registrations raise :class:`~modules.error_models.exceptions.ErrorRegistryError`
      unless ``overwrite=True`` is passed.

Usage::

    # Register a model (done once, usually at module import time):
    from modules.error_models.error_registry import registry

    class MissedSynapses(BaseErrorModel):
        NAME = "missed_synapses"
        ...

    registry.register(MissedSynapses)

    # Instantiate and run (Experiment Runner):
    model  = registry.instantiate("missed_synapses")
    result = model.execute(prepared_graph, config={"removal_rate": 0.05})
"""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from .base_error_model import BaseErrorModel
from .exceptions import ErrorRegistryError

logger = logging.getLogger(__name__)


class ErrorRegistry:
    """Central catalogue of available error models.

    Each model is stored by its
    :attr:`~modules.error_models.base_error_model.BaseErrorModel.NAME`.

    Example::

        reg = ErrorRegistry()
        reg.register(MissedSynapses)
        model = reg.instantiate("missed_synapses")
        result = model.execute(prepared)
    """

    def __init__(self) -> None:
        self._models: Dict[str, Type[BaseErrorModel]] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register(
        self,
        model_cls: Type[BaseErrorModel],
        *,
        overwrite: bool = False,
    ) -> None:
        """Add *model_cls* to the registry.

        Args:
            model_cls:
                A concrete subclass of
                :class:`~modules.error_models.base_error_model.BaseErrorModel`.
            overwrite:
                If ``True``, silently replace a previously registered class
                with the same ``NAME``.  Defaults to ``False``.

        Raises:
            ErrorRegistryError:
                If *model_cls* is invalid, has an empty ``NAME``, or a model
                with the same ``NAME`` is already registered and ``overwrite``
                is ``False``.
        """
        self._validate_cls(model_cls)
        name = model_cls.NAME

        if name in self._models and not overwrite:
            raise ErrorRegistryError(
                f"An error model named {name!r} is already registered "
                f"({self._models[name].__name__}). "
                "Pass overwrite=True to replace it."
            )

        self._models[name] = model_cls
        logger.info(
            "[ErrorRegistry] Registered model %r → %s.",
            name, model_cls.__name__,
        )

    def unregister(self, name: str) -> None:
        """Remove the model registered under *name*.

        Args:
            name: The ``NAME`` of the model to remove.

        Raises:
            ErrorRegistryError: If no model with *name* is registered.
        """
        if name not in self._models:
            raise ErrorRegistryError(
                f"Cannot unregister {name!r}: no model with that name is registered."
            )
        removed = self._models.pop(name)
        logger.info(
            "[ErrorRegistry] Unregistered model %r (%s).",
            name, removed.__name__,
        )

    # ------------------------------------------------------------------ #
    # Retrieval                                                            #
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> Type[BaseErrorModel]:
        """Return the model **class** registered under *name*.

        Raises:
            ErrorRegistryError: If no model with *name* is registered.
        """
        if name not in self._models:
            raise ErrorRegistryError(
                f"No error model named {name!r} is registered. "
                f"Available: {self.list_names()}"
            )
        return self._models[name]

    def instantiate(
        self,
        name: str,
        *args: object,
        **kwargs: object,
    ) -> BaseErrorModel:
        """Instantiate and return the model registered under *name*.

        Args:
            name:     The ``NAME`` of the desired model.
            *args:    Forwarded to the model constructor.
            **kwargs: Forwarded to the model constructor.

        Returns:
            An instance of the requested error model.

        Raises:
            ErrorRegistryError: If no model with *name* is registered.
        """
        cls = self.get(name)
        return cls(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Introspection                                                        #
    # ------------------------------------------------------------------ #

    def list_names(self) -> List[str]:
        """Return a sorted list of all registered model names."""
        return sorted(self._models.keys())

    def list_classes(self) -> List[Type[BaseErrorModel]]:
        """Return a sorted-by-name list of all registered model classes."""
        return [self._models[n] for n in self.list_names()]

    def is_registered(self, name: str) -> bool:
        """Return ``True`` if a model with *name* is registered."""
        return name in self._models

    def __len__(self) -> int:
        return len(self._models)

    def __repr__(self) -> str:
        return f"ErrorRegistry(models={self.list_names()})"

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_cls(model_cls: object) -> None:
        """Raise :class:`ErrorRegistryError` if *model_cls* is not usable."""
        if not isinstance(model_cls, type):
            raise ErrorRegistryError(
                f"Expected a class, got {type(model_cls).__name__!r}."
            )
        if not issubclass(model_cls, BaseErrorModel):
            raise ErrorRegistryError(
                f"{model_cls.__name__!r} must subclass BaseErrorModel."
            )
        if not model_cls.NAME:
            raise ErrorRegistryError(
                f"{model_cls.__name__!r} has an empty NAME attribute."
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: The canonical registry instance.  Import this everywhere — in concrete
#: model modules to register models, and in the Experiment Runner to retrieve
#: them.
registry: ErrorRegistry = ErrorRegistry()
