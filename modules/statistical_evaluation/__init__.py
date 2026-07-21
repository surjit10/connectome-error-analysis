"""
Phase 017 — Statistical Evaluation Framework
=============================================
Provides statistical evaluation of both scalar and vector-valued graph
analysis metrics across baseline and perturbed simulation trials.

Components:
    - :class:`StatisticalEvaluator` — orchestrates evaluation.
    - :class:`StatisticalEvaluationResult` — aggregated evaluation output.
    - :class:`MetricEvaluation` — per-metric evaluation summary.
    - :class:`VectorComparisonRegistry` — strategy registry for vector comparison.
    - :func:`compare_degree_distribution` — degree distribution comparison.
    - :func:`compare_pagerank` — PageRank vector comparison.
    - :func:`compare_betweenness` — betweenness comparison.
    - :func:`compare_closeness` — closeness comparison.
"""
from .evaluator import StatisticalEvaluator, StatisticalEvaluationResult, MetricEvaluation
from .vector_comparison import (
    VectorComparisonRegistry,
    compare_degree_distribution,
    compare_pagerank,
    compare_betweenness,
    compare_closeness,
)

__all__ = [
    "StatisticalEvaluator",
    "StatisticalEvaluationResult",
    "MetricEvaluation",
    "VectorComparisonRegistry",
    "compare_degree_distribution",
    "compare_pagerank",
    "compare_betweenness",
    "compare_closeness",
]
