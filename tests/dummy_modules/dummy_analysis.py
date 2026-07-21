from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_result import AnalysisResult, AnalysisStatus
from modules.preprocessing import PreparedGraph

class DummyAnalysis(BaseAnalysis):
    NAME = "dummy_analysis"
    
    def _run(self, prepared: PreparedGraph, config: dict, result: AnalysisResult) -> None:
        """Returns simple graph metrics."""
        result.metrics = {
            "nodes": prepared.node_count(),
            "edges": prepared.edge_count()
        }
        result.status = AnalysisStatus.SUCCESS
