"""
Phase 007 – Analysis Framework
===============================
Public surface of the graph-analyses package.

Downstream components (Experiment Runner, Statistics Engine, research modules)
should import from here, not from the sub-modules directly.

Typical Experiment Runner usage::

    from modules.graph_analyses import registry, AnalysisResult, AnalysisStatus

    analysis = registry.instantiate("degree")
    result   = analysis.execute(prepared_graph)

    if result.status == AnalysisStatus.SUCCESS:
        stats_engine.record(result)

Typical concrete-analysis authoring::

    from modules.graph_analyses import BaseAnalysis, registry

    class MyAnalysis(BaseAnalysis):
        NAME = "my_analysis"

        def _run(self, prepared, config, result):
            result.metrics["answer"] = 42

    registry.register(MyAnalysis)
"""

from .exceptions import (
    AnalysisFrameworkError,
    AnalysisExecutionError,
    InvalidInputError,
    RegistryError,
)
from .analysis_result import AnalysisResult, AnalysisStatus
from .base_analysis import BaseAnalysis
from .analysis_registry import AnalysisRegistry, registry

__all__ = [
    # Core contract
    "BaseAnalysis",
    "AnalysisResult",
    "AnalysisStatus",
    # Registry
    "AnalysisRegistry",
    "registry",
    # Exceptions
    "AnalysisFrameworkError",
    "AnalysisExecutionError",
    "InvalidInputError",
    "RegistryError",
]

# Auto-register all known analyses
from . import structural
from . import network_statistics
from . import centrality
from . import biological
