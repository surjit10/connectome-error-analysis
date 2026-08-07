"""
Error Model 5 (EM5) – Merge Errors (Under-Segmentation)
=========================================================
Public surface of the merge-errors package.  Importing this module triggers
auto-registration of :class:`MergeErrorsModel` in the global error-model
registry (``name = "merge_errors"``).
"""

from .model import MergeErrorsModel

__all__ = ["MergeErrorsModel"]
