"""
Null Model Registry
===================
Catalogue of available null-model generators in the hypothesis-testing subsystem.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from .base import BaseNullModel
from .degree_preserving_rewriter import DirectedDegreeWeightPreservingNullModel
from .erdos_renyi import DirectedErdosRenyiNullModel

logger = logging.getLogger(__name__)


class NullModelRegistry:
    """Central registry of connectome null-model generators."""

    def __init__(self) -> None:
        self._models: Dict[str, Type[BaseNullModel]] = {}

    def register(
        self, model_cls: Type[BaseNullModel], *, overwrite: bool = False
    ) -> None:
        """Register a BaseNullModel subclass."""
        name = model_cls.NAME
        if not name:
            raise ValueError(f"{model_cls.__name__} has an empty NAME.")
        if name in self._models and not overwrite:
            raise ValueError(f"Null model '{name}' is already registered.")
        self._models[name] = model_cls
        logger.debug(f"[NullModelRegistry] Registered '{name}' -> {model_cls.__name__}.")

    def get(self, name: str) -> Type[BaseNullModel]:
        """Retrieve null model class by name."""
        if name not in self._models:
            raise KeyError(
                f"Unknown null model '{name}'. Available: {self.list_names()}"
            )
        return self._models[name]

    def instantiate(self, name: str, *args, **kwargs) -> BaseNullModel:
        """Instantiate null model by name."""
        cls = self.get(name)
        return cls(*args, **kwargs)

    def list_names(self) -> List[str]:
        """Return sorted list of registered null model names."""
        return sorted(self._models.keys())


# Canonical singleton
registry: NullModelRegistry = NullModelRegistry()
registry.register(DirectedDegreeWeightPreservingNullModel, overwrite=True)
registry.register(DirectedErdosRenyiNullModel, overwrite=True)
