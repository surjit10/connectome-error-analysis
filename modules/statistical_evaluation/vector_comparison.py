"""
Phase 017 — Vector-Valued Graph Statistics Comparison
======================================================
Provides a registration-based strategy pattern for comparing vector-valued
graph analysis metrics (PageRank, degree distribution, betweenness,
closeness, etc.) across baseline and perturbed trials.

Each comparison strategy receives two vectors (baseline, perturbed) together
with optional configuration and returns a dict of derived scalar metrics
(e.g. ``{"spearman": 0.85, "topk_overlap": 0.72}``).

Design constraints:
    - Strategies are registered by ``(analysis_name, metric_key)`` so the
      StatisticsEngine can dispatch without hard-coding analysis names.
    - New analyses can register their own strategies without modifying the
      engine or evaluator.
    - All comparison functions are pure — no side effects, no I/O.
    - NaN / Inf / empty inputs are handled gracefully (logged warnings,
      fallback values instead of crashes).
"""

from __future__ import annotations

import abc
import logging
import math
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

#: A comparison function receives (baseline_vector, perturbed_vector, config)
#: and returns a dict of derived scalar metric name → value.
ComparisonFunc = Callable[
    [List[float], List[float], Dict[str, Any]],
    Dict[str, float],
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class VectorComparisonRegistry:
    """Maps ``(analysis_name, metric_key)`` to a comparison function.

    Usage::

        VectorComparisonRegistry.register("pagerank", "pagerank_scores",
                                           compare_pagerank)

        strategy = VectorComparisonRegistry.get("pagerank", "pagerank_scores")
        if strategy is not None:
            result = strategy(baseline_vec, perturbed_vec, config)

    Thread-safe for read access under the GIL.
    """

    _registry: Dict[Tuple[str, str], ComparisonFunc] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def register(
        cls,
        analysis_name: str,
        metric_key: str,
        func: ComparisonFunc,
        *,
        overwrite: bool = False,
    ) -> None:
        """Register *func* as the comparison strategy for *analysis_name* /
        *metric_key*.

        Args:
            analysis_name:
                The ``BaseAnalysis.NAME`` (e.g. ``"pagerank"``).
            metric_key:
                The key inside ``AnalysisResult.metrics`` that holds the
                vector (e.g. ``"pagerank_scores"``).
            func:
                Callable ``(baseline_vec, perturbed_vec, config) → dict``.
            overwrite:
                Silently replace an existing registration when ``True``.
        """
        key = (analysis_name, metric_key)
        if key in cls._registry and not overwrite:
            logger.warning(
                "[VectorComparisonRegistry] Strategy already registered for "
                "%s / %s. Pass overwrite=True to replace.",
                analysis_name, metric_key,
            )
            return
        cls._registry[key] = func
        logger.debug(
            "[VectorComparisonRegistry] Registered strategy for %s / %s.",
            analysis_name, metric_key,
        )

    @classmethod
    def unregister(cls, analysis_name: str, metric_key: str) -> None:
        """Remove the strategy for *(analysis_name, metric_key)*."""
        key = (analysis_name, metric_key)
        cls._registry.pop(key, None)

    # ------------------------------------------------------------------ #
    # Lookup                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def get(
        cls,
        analysis_name: str,
        metric_key: str,
    ) -> Optional[ComparisonFunc]:
        """Return the registered comparison function, or ``None``."""
        return cls._registry.get((analysis_name, metric_key))

    @classmethod
    def has(cls, analysis_name: str, metric_key: str) -> bool:
        """Return ``True`` if a strategy is registered."""
        return (analysis_name, metric_key) in cls._registry

    @classmethod
    def list_registrations(cls) -> List[Tuple[str, str]]:
        """Return sorted list of all registered ``(analysis_name, metric_key)``."""
        return sorted(cls._registry.keys())

    @classmethod
    def get_strategies_for_analysis(
        cls,
        analysis_name: str,
    ) -> Dict[str, ComparisonFunc]:
        """Return a dict of ``metric_key → ComparisonFunc`` for *analysis_name*."""
        return {
            mk: func
            for (an, mk), func in cls._registry.items()
            if an == analysis_name
        }


# ===================================================================
# Scientific Comparison Implementations
# ===================================================================

# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------


def _robust_spearman(
    x: List[float],
    y: List[float],
) -> float:
    """Compute Spearman rank correlation with NaN/constant guards.

    Returns a value in ``[-1, 1]`` or 0.0 if the computation fails.
    """
    if len(x) < 3 or len(y) < 3:
        return 0.0
    # Remove NaN / Inf
    mask = [
        math.isfinite(xi) and math.isfinite(yi)
        for xi, yi in zip(x, y)
    ]
    xf = [xi for m, xi in zip(mask, x) if m]
    yf = [yi for m, yi in zip(mask, y) if m]
    if len(xf) < 3:
        return 0.0
    try:
        from scipy.stats import spearmanr
        r, _ = spearmanr(xf, yf)
        return r if math.isfinite(r) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def _robust_pearson(
    x: List[float],
    y: List[float],
) -> float:
    """Compute Pearson correlation with NaN/constant guards."""
    if len(x) < 3 or len(y) < 3:
        return 0.0
    mask = [
        math.isfinite(xi) and math.isfinite(yi)
        for xi, yi in zip(x, y)
    ]
    xf = [xi for m, xi in zip(mask, x) if m]
    yf = [yi for m, yi in zip(mask, y) if m]
    if len(xf) < 3:
        return 0.0
    # Check for constant input
    if max(xf) - min(xf) < 1e-12 or max(yf) - min(yf) < 1e-12:
        return 0.0
    try:
        from scipy.stats import pearsonr
        r, _ = pearsonr(xf, yf)
        return r if math.isfinite(r) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def _top_k_overlap(
    x: List[float],
    y: List[float],
    k: int = 100,
) -> float:
    """Compute Jaccard-like overlap of top-k indices between two vectors.

    Returns fraction ``[0, 1]``.
    """
    if not x or not y:
        return 0.0
    k = min(k, len(x), len(y))
    if k == 0:
        return 0.0
    top_x = set(np.argsort(x)[-k:].tolist())
    top_y = set(np.argsort(y)[-k:].tolist())
    intersection = top_x & top_y
    return len(intersection) / k


def _robust_ks(
    x: List[float],
    y: List[float],
) -> float:
    """Two-sample Kolmogorov–Smirnov statistic, or 0.0 on failure."""
    xf = [v for v in x if math.isfinite(v)]
    yf = [v for v in y if math.isfinite(v)]
    if len(xf) < 2 or len(yf) < 2:
        return 0.0
    try:
        from scipy.stats import ks_2samp
        stat, _ = ks_2samp(xf, yf)
        return stat if math.isfinite(stat) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def _robust_wasserstein(
    x: List[float],
    y: List[float],
) -> float:
    """1D Wasserstein distance, or 0.0 on failure."""
    xf = [v for v in x if math.isfinite(v)]
    yf = [v for v in y if math.isfinite(v)]
    if len(xf) < 1 or len(yf) < 1:
        return 0.0
    try:
        from scipy.stats import wasserstein_distance
        d = wasserstein_distance(xf, yf)
        return d if math.isfinite(d) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def _mean_std(values: List[float]) -> Tuple[float, float]:
    """Robust mean and std (0 for empty/single)."""
    if not values:
        return 0.0, 0.0
    arr = np.array([v for v in values if math.isfinite(v)])
    if len(arr) < 1:
        return 0.0, 0.0
    return float(np.mean(arr)), float(np.std(arr, ddof=0))


# ===================================================================
# Concrete comparison strategies
# ===================================================================


def compare_degree_distribution(
    baseline: List[float],
    perturbed: List[float],
    config: Dict[str, Any],
) -> Dict[str, float]:
    """Compare two degree vectors (in-degree or out-degree).

    Returns derived scalar metrics:
        - ``mean_baseline``, ``mean_perturbed``
        - ``var_baseline``, ``var_perturbed``
        - ``ks`` — Kolmogorov–Smirnov statistic
        - ``wasserstein`` — 1D Wasserstein distance
    """
    b_mean, b_std = _mean_std(baseline)
    p_mean, p_std = _mean_std(perturbed)

    return {
        "mean_baseline": b_mean,
        "mean_perturbed": p_mean,
        "var_baseline": b_std * b_std,
        "var_perturbed": p_std * p_std,
        "ks": _robust_ks(baseline, perturbed),
        "wasserstein": _robust_wasserstein(baseline, perturbed),
    }


def compare_pagerank(
    baseline: List[float],
    perturbed: List[float],
    config: Dict[str, Any],
) -> Dict[str, float]:
    """Compare two PageRank score vectors.

    Returns:
        - ``spearman`` — Spearman rank correlation
        - ``pearson`` — Pearson correlation
        - ``topk_overlap`` — Top-K index overlap (K from config)
    """
    top_k = int(config.get("top_k_overlap", 100))

    return {
        "spearman": _robust_spearman(baseline, perturbed),
        "pearson": _robust_pearson(baseline, perturbed),
        "topk_overlap": _top_k_overlap(baseline, perturbed, k=top_k),
    }


def compare_betweenness(
    baseline: List[float],
    perturbed: List[float],
    config: Dict[str, Any],
) -> Dict[str, float]:
    """Compare two betweenness centrality vectors.

    Returns:
        - ``spearman`` — Spearman rank correlation
        - ``pearson`` — Pearson correlation
        - ``topk_overlap`` — Top-K index overlap (K from config)
    """
    top_k = int(config.get("top_k_overlap", 100))

    return {
        "spearman": _robust_spearman(baseline, perturbed),
        "pearson": _robust_pearson(baseline, perturbed),
        "topk_overlap": _top_k_overlap(baseline, perturbed, k=top_k),
    }


def compare_closeness(
    baseline: List[float],
    perturbed: List[float],
    config: Dict[str, Any],
) -> Dict[str, float]:
    """Compare two closeness centrality vectors.

    Handles disconnected graphs safely (uses only vertices with finite
    closeness).

    Returns:
        - ``spearman`` — Spearman rank correlation
        - ``pearson`` — Pearson correlation
    """
    # Filter out NaN/Inf from disconnected nodes for closeness
    b_filtered = [v for v in baseline if math.isfinite(v)]
    p_filtered = [v for v in perturbed if math.isfinite(v)]

    # If filtered lengths differ, fall back to rank-based comparison
    # on the full vectors after replacing NaN/Inf with sentinel values.
    if len(b_filtered) < 3 or len(p_filtered) < 3:
        # Use rank of finite values only — align by index
        aligned_b = [v if math.isfinite(v) else -1.0 for v in baseline]
        aligned_p = [v if math.isfinite(v) else -1.0 for v in perturbed]
        return {
            "spearman": _robust_spearman(aligned_b, aligned_p),
            "pearson": 0.0,  # Pearson unreliable with sentinels
        }

    return {
        "spearman": _robust_spearman(b_filtered, p_filtered),
        "pearson": _robust_pearson(b_filtered, p_filtered),
    }


# ===================================================================
# Auto-registration
# ===================================================================


def _register_default_strategies() -> None:
    """Register all built-in comparison strategies.

    Called automatically at module import time.
    """
    # Degree distribution — two vector metrics
    VectorComparisonRegistry.register(
        "degree_distribution", "in_degrees",
        compare_degree_distribution,
        overwrite=True,
    )
    VectorComparisonRegistry.register(
        "degree_distribution", "out_degrees",
        compare_degree_distribution,
        overwrite=True,
    )

    # PageRank
    VectorComparisonRegistry.register(
        "pagerank", "pagerank_scores",
        compare_pagerank,
        overwrite=True,
    )

    # Centrality (betweenness)
    VectorComparisonRegistry.register(
        "centrality", "betweenness",
        compare_betweenness,
        overwrite=True,
    )

    # Centrality (closeness)
    VectorComparisonRegistry.register(
        "centrality", "closeness",
        compare_closeness,
        overwrite=True,
    )

    logger.info(
        "[VectorComparisonRegistry] Registered %d default strategies.",
        len(VectorComparisonRegistry.list_registrations()),
    )


# Execute auto-registration on import.
_register_default_strategies()
