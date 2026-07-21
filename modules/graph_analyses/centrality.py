"""
Tier 2 — Centrality Statistics
"""
from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_registry import registry

class CentralityAnalysis(BaseAnalysis):
    NAME = "centrality"
    def _run(self, prepared, config, result):
        g = prepared.graph
        weights = "weight" if "weight" in g.edge_attributes() else None
        
        try:
            result.metrics["betweenness"] = g.betweenness(weights=weights)
        except Exception as e:
            result.warnings.append(f"Betweenness failed: {e}")
            
        try:
            result.metrics["closeness"] = g.closeness(weights=weights)
        except Exception as e:
            result.warnings.append(f"Closeness failed: {e}")

registry.register(CentralityAnalysis, overwrite=True)
