"""
Tier 2 — Assortativity (Degree Assortativity)
==============================================
Measures the tendency of nodes to connect to similar nodes in terms of
their degree (directed implementation uses ``igraph.Graph.assortativity_degree``).

Biological relevance:
    Assortativity in connectomes reflects whether high-degree hub neurons
    preferentially connect to other hubs (assortative mixing) or to
    low-degree neurons (disassortative mixing).  Perturbations that disrupt
    hub connectivity (e.g. missed synapses on high-degree neurons) are
    expected to shift assortativity values.
"""

from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_registry import registry


class AssortativityAnalysis(BaseAnalysis):
    """Compute degree assortativity of the directed graph.

    Uses ``igraph.Graph.assortativity_degree()`` which computes the Pearson
    correlation of degrees at either end of each directed edge.

    Metric:
        ``degree_assortativity``:
            Pearson correlation of degrees (directed).  Ranges from -1
            (disassortative) to +1 (assortative).  A value of 0 indicates
            no correlation.
    """

    NAME = "assortativity"

    def _run(self, prepared, config, result):
        g = prepared.graph
        result.metrics["degree_assortativity"] = g.assortativity_degree(directed=True)


registry.register(AssortativityAnalysis, overwrite=True)
