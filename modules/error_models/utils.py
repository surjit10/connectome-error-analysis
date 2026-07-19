"""
Phase 008 – Error Model Framework / Shared Utilities
=====================================================
Lightweight utilities shared across error-model sub-modules.

Only genuinely cross-cutting helpers live here.  Biological logic,
specific perturbation strategies, and graph algorithms must never be
placed here.

Mirrors the utility pattern from Phase 007 (``modules/graph_analyses/utils.py``)
but operates on :class:`~modules.error_models.error_result.ErrorResult`
rather than ``AnalysisResult`` to maintain a clean separation of concerns.

Currently provides:
    - :func:`require_config_key` — assert a required key is in a config dict.
    - :func:`validate_config_keys` — warn on unrecognised config keys.
    - :func:`add_warning` — consistent helper to append a warning.
    - :func:`init_numpy_seed` — optional helper for models using NumPy RNG.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from .error_result import ErrorResult
from .exceptions import InvalidInputError

logger = logging.getLogger(__name__)


def require_config_key(
    config: Dict[str, Any],
    key: str,
    model_name: str,
) -> Any:
    """Return ``config[key]``, raising :class:`InvalidInputError` if absent.

    Args:
        config:     Configuration dict passed to an error model.
        key:        Required configuration key.
        model_name: Name of the calling model (for error messages).

    Returns:
        The value stored at ``config[key]``.

    Raises:
        InvalidInputError: If *key* is not present in *config*.
    """
    if key not in config:
        raise InvalidInputError(
            f"[ErrorModel/{model_name}] Required configuration key "
            f"{key!r} is missing."
        )
    return config[key]


def validate_config_keys(
    config: Dict[str, Any],
    known_keys: Iterable[str],
    model_name: str,
    result: ErrorResult,
) -> None:
    """Emit a warning for any config key not in *known_keys*.

    Non-fatal: unknown keys are logged and added to ``result.warnings``
    but execution continues.

    Args:
        config:     Configuration dict passed to an error model.
        known_keys: Iterable of recognised key names.
        model_name: Name of the calling model (for messages).
        result:     Result object to append warnings to.
    """
    known = set(known_keys)
    unknown = sorted(set(config.keys()) - known)
    if unknown:
        msg = (
            f"[ErrorModel/{model_name}] Unrecognised configuration "
            f"key(s): {unknown}. They will be ignored."
        )
        logger.warning(msg)
        result.warnings.append(msg)


def add_warning(result: ErrorResult, message: str) -> None:
    """Append *message* to ``result.warnings`` and log at WARNING level.

    Args:
        result:  The :class:`~modules.error_models.error_result.ErrorResult`
                 to annotate.
        message: Human-readable warning text.
    """
    logger.warning("[ErrorModel/%s] %s", result.model_name, message)
    result.warnings.append(message)


def init_numpy_seed(seed: Optional[int]) -> None:
    """Initialise NumPy's global random state with *seed*.

    Only call this if your error model uses ``numpy.random`` functions.
    Models using only the stdlib ``random`` module are handled automatically
    by :meth:`~modules.error_models.base_error_model.BaseErrorModel._init_seed`.

    Args:
        seed: Integer seed, or ``None`` to skip initialisation.
    """
    if seed is None:
        return
    try:
        import numpy as np  # optional dependency
        np.random.seed(seed)
        logger.debug("[ErrorModel/utils] NumPy random seed set to %d.", seed)
    except ImportError:
        logger.debug("[ErrorModel/utils] NumPy not available; seed not applied.")
