"""
Hypothesis Testing Loaders
==========================
Data loaders for importing external or historical experiment results into
canonical replicate-level SecondaryEffectRecord representations.
"""

from .existing_real_results_loader import ExistingRealResultsLoader

__all__ = ["ExistingRealResultsLoader"]
