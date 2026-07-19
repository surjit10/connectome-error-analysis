"""
Phase 007 – Analysis Framework / Shared Utilities
==================================================
Lightweight utilities shared across analysis sub-modules.

Only genuinely cross-cutting helpers live here.  Algorithm-specific or
biology-specific code must never be placed here.

Currently provides:
    - :func:`require_metric` — assert a metric key exists in a config dict.
    - :func:`validate_config_keys` — warn on unrecognised config keys.
    - :func:`add_warning` — uniform helper to append a warning to an
      :class:`~modules.graph_analyses.analysis_result.AnalysisResult`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable

from .analysis_result import AnalysisResult
from .exceptions import InvalidInputError

logger = logging.getLogger(__name__)


def require_metric(
    config: Dict[str, Any],
    key: str,
    analysis_name: str,
) -> Any:
    """Return ``config[key]``, raising :class:`InvalidInputError` if absent.

    Args:
        config:        Configuration dict passed to an analysis.
        key:           Required configuration key.
        analysis_name: Name of the calling analysis (for error messages).

    Returns:
        The value stored at ``config[key]``.

    Raises:
        InvalidInputError: If *key* is not present in *config*.
    """
    if key not in config:
        raise InvalidInputError(
            f"[Analysis/{analysis_name}] Required configuration key "
            f"{key!r} is missing."
        )
    return config[key]


def validate_config_keys(
    config: Dict[str, Any],
    known_keys: Iterable[str],
    analysis_name: str,
    result: AnalysisResult,
) -> None:
    """Emit a warning for any config key not listed in *known_keys*.

    This is non-fatal: unexpected keys are logged and appended to
    ``result.warnings``, but execution continues.

    Args:
        config:        Configuration dict passed to an analysis.
        known_keys:    Iterable of recognised key names.
        analysis_name: Name of the calling analysis (for messages).
        result:        Result object to append warnings to.
    """
    known = set(known_keys)
    unknown = sorted(set(config.keys()) - known)
    if unknown:
        msg = (
            f"[Analysis/{analysis_name}] Unrecognised configuration "
            f"key(s): {unknown}. They will be ignored."
        )
        logger.warning(msg)
        result.warnings.append(msg)


def add_warning(result: AnalysisResult, message: str) -> None:
    """Append *message* to ``result.warnings`` and log it at WARNING level.

    Provides a single consistent way for analyses to record non-fatal issues.

    Args:
        result:  The :class:`~modules.graph_analyses.analysis_result.AnalysisResult`
                 to annotate.
        message: Human-readable warning text.
    """
    logger.warning("[Analysis/%s] %s", result.analysis_name, message)
    result.warnings.append(message)
