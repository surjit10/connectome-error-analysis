"""
Analysis Package
================
Secondary effects extraction and metric classification for hypothesis testing.
"""

from .secondary_effects import (
    MetricCategory,
    SecondaryEffectRecord,
    SecondaryEffectsExtractor,
    classify_metric,
)

__all__ = [
    "MetricCategory",
    "SecondaryEffectRecord",
    "SecondaryEffectsExtractor",
    "classify_metric",
]
