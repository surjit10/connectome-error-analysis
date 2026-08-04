"""
Error Model 4 (EM4) – Split Errors (Segmentation Fragmentation)
================================================================
Public surface of the split-errors package.  Importing this module triggers
auto-registration of :class:`SplitErrorsModel` in the global error-model
registry (``name = "split_errors"``).
"""

from .model import SplitErrorsModel

__all__ = ["SplitErrorsModel"]
