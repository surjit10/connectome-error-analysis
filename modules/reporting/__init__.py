"""
modules/reporting
=================
Scientific analysis modules that sit between the statistical evaluation layer
and the presentation layer.

These modules consume :class:`StatisticalEvaluationResult` objects (produced by
``modules.statistical_evaluation``) and produce structured analysis objects
(dataclasses) that the presentation exporters consume.

Design constraints:
    - No plotting. No HTML. No file I/O.
    - All outputs are plain Python dataclasses.
    - No circular imports: these modules import from statistical_evaluation only.
"""
from .data_loader import load_trial_summaries, aggregate_by_rate, ReportingDataLoader
from .trend_analysis import TrendAnalysisResult, TrendAnalysis
from .sensitivity_analysis import SensitivityResult, SensitivityAnalysis
from .comparison_analysis import ComparisonResult

__all__ = [
    "load_trial_summaries",
    "aggregate_by_rate",
    "ReportingDataLoader",
    "TrendAnalysisResult",
    "TrendAnalysis",
    "SensitivityResult",
    "SensitivityAnalysis",
    "ComparisonResult",
]
