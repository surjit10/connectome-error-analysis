"""
Tier 2 — Network Statistics
"""
from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_registry import registry

class DegreeDistributionAnalysis(BaseAnalysis):
    NAME = "degree_distribution"
    def _run(self, prepared, config, result):
        g = prepared.graph
        result.metrics["in_degrees"] = g.indegree()
        result.metrics["out_degrees"] = g.outdegree()

class PageRankAnalysis(BaseAnalysis):
    NAME = "pagerank"
    def _run(self, prepared, config, result):
        g = prepared.graph
        weights = "weight" if "weight" in g.edge_attributes() else None
        damping = config.get("damping", 0.85)
        result.metrics["pagerank_scores"] = g.pagerank(weights=weights, damping=damping)

registry.register(DegreeDistributionAnalysis, overwrite=True)
registry.register(PageRankAnalysis, overwrite=True)
