"""
Phase 008 – Error Model Framework / Exceptions
===============================================
All custom exceptions raised by the error-model framework.

Kept in a dedicated module to avoid circular dependencies between
sub-modules and to mirror the pattern established by Phase 007.
"""

from __future__ import annotations


class ErrorModelFrameworkError(Exception):
    """Base class for all error-model-framework exceptions."""


class InvalidInputError(ErrorModelFrameworkError):
    """Raised when an error model receives an input that does not satisfy the
    framework's input contract (e.g. a raw graph instead of a PreparedGraph).
    """


class ErrorModelExecutionError(ErrorModelFrameworkError):
    """Raised when an error model raises an unexpected exception during
    execution.  The original exception is always chained.
    """


class ErrorRegistryError(ErrorModelFrameworkError):
    """Raised for any problem with the
    :class:`~modules.error_models.error_registry.ErrorRegistry`
    (duplicate registration, unknown model name, etc.).
    """
