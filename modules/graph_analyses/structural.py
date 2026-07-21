"""
Tier 1 — Structural Graph Properties
"""
from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_registry import registry

class BasicStructureAnalysis(BaseAnalysis):
    NAME = "basic_structure"
    def _run(self, prepared, config, result):
        g = prepared.graph
        result.metrics["node_count"] = g.vcount()
        result.metrics["edge_count"] = g.ecount()
        result.metrics["total_synapses"] = sum(g.es["weight"]) if "weight" in g.edge_attributes() else g.ecount()
        result.metrics["density"] = g.density()

class ConnectedComponentsAnalysis(BaseAnalysis):
    NAME = "connected_components"
    def _run(self, prepared, config, result):
        g = prepared.graph
        wcc = g.components(mode="weak")
        result.metrics["wcc_count"] = len(wcc)
        result.metrics["wcc_max_size"] = max(wcc.sizes()) if len(wcc) > 0 else 0
        scc = g.components(mode="strong")
        result.metrics["scc_count"] = len(scc)
        result.metrics["scc_max_size"] = max(scc.sizes()) if len(scc) > 0 else 0

class ReciprocityAnalysis(BaseAnalysis):
    NAME = "reciprocity"
    def _run(self, prepared, config, result):
        result.metrics["reciprocity"] = prepared.graph.reciprocity()

registry.register(BasicStructureAnalysis, overwrite=True)
registry.register(ConnectedComponentsAnalysis, overwrite=True)
registry.register(ReciprocityAnalysis, overwrite=True)
