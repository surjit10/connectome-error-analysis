"""
Comparison Package
==================
Statistical comparison engines, hypothesis testing, and narrative reporting.
"""

from .metric_comparison import (
    MetricComparisonResult,
    MetricComparator,
    cohens_d,
)
from .hypothesis_tests import (
    HypothesisTestResult,
    HypothesisTestEngine,
    benjamini_hochberg_fdr,
)

__all__ = [
    "MetricComparisonResult",
    "MetricComparator",
    "HypothesisTestResult",
    "HypothesisTestEngine",
    "cohens_d",
    "benjamini_hochberg_fdr",
]
