"""
Phase TBD – Synapse Count Measurement Error Model
====================================================
Simulates measurement uncertainty in synaptic weight estimation.

Auto-registers :class:`SynapseCountMeasurementError` on import via the
registration call at the bottom of ``model.py``.
"""

from .model import SynapseCountMeasurementError

__all__ = [
    "SynapseCountMeasurementError",
]
