"""
modules/reporting/comparison_analysis.py
=========================================
Scaffold for future cross-dataset and cross-error-model comparison analysis.

Currently returns an empty :class:`ComparisonResult`.  When multiple datasets
or error models are available, this module will be extended to produce
comparative metrics without any changes to the rest of the architecture.

Design constraints:
    - No plotting. No HTML. No file I/O.
    - All outputs are plain Python dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ComparisonResult:
    """Placeholder for future cross-dataset / cross-error-model comparison.

    Attributes:
        datasets_compared:    List of dataset names included.
        error_models_compared: List of error model names included.
        notes:                Human-readable notes on what was compared.
    """
    datasets_compared:     List[str]        = field(default_factory=list)
    error_models_compared: List[str]        = field(default_factory=list)
    notes:                 List[str]        = field(default_factory=list)
    data:                  Dict            = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Return ``True`` if no comparison data has been populated."""
        return not self.data
