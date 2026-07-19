"""
Phase 007 – Analysis Framework / Exceptions
============================================
All custom exceptions raised by the analysis framework.

Kept in a dedicated module so that every other sub-module can import from
here without introducing circular dependencies.
"""

from __future__ import annotations


class AnalysisFrameworkError(Exception):
    """Base class for all analysis-framework exceptions."""


class InvalidInputError(AnalysisFrameworkError):
    """Raised when an analysis receives an input that does not satisfy the
    framework's input contract (e.g. a raw graph instead of a PreparedGraph,
    or a PreparedGraph that failed validation).
    """


class AnalysisExecutionError(AnalysisFrameworkError):
    """Raised when an analysis raises an unexpected error during execution.

    The original exception is always chained via ``raise ... from original``.
    """


class RegistryError(AnalysisFrameworkError):
    """Raised for any problem with the :class:`~modules.graph_analyses.
    analysis_registry.AnalysisRegistry` (duplicate registration, unknown
    analysis name, etc.).
    """
