"""
Hypothesis Testing Subsystem for Connectome Reconstruction Error Analysis
========================================================================
Provides null-model generation, baseline-relative secondary effect analysis,
and hypothesis-testing capabilities across real and randomized connectomes.
"""

from .config import HypothesisExperimentConfig, Condition, ExecutionMode
from .runners.hypothesis_experiment_runner import HypothesisExperimentRunner
from .runners.compare_existing_runner import CompareExistingRunner
from .loaders.existing_real_results_loader import ExistingRealResultsLoader

__all__ = [
    "HypothesisExperimentConfig",
    "Condition",
    "ExecutionMode",
    "HypothesisExperimentRunner",
    "CompareExistingRunner",
    "ExistingRealResultsLoader",
]

