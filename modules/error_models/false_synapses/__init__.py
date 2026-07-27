"""
Phase TBD – False Synapses Error Model
=========================================
False-positive (false-synapse) error model.

Auto-registers :class:`FalseSynapseModel` on import via the registration
call at the bottom of ``model.py``.
"""

from .model import FalseSynapseModel

__all__ = [
    "FalseSynapseModel",
]
