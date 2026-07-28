"""
Tier 1 — Structural Graph Properties
"""
from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_registry import registry

import math

from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_registry import registry


def _weight_summary_stats(weights):
    """Compute summary statistics for a list of edge weights.

    Returns a dict with mean, median, variance, stdev, max, min.
    Handles empty lists gracefully by returning zeros.
    """
    n = len(weights)
    if n == 0:
        return {
            "mean": 0.0,
            "median": 0.0,
            "variance": 0.0,
            "std": 0.0,
            "max": 0.0,
            "min": 0.0,
        }
    mean = sum(weights) / n
    if n == 1:
        return {
            "mean": float(mean),
            "median": float(weights[0]),
            "variance": 0.0,
            "std": 0.0,
            "max": float(weights[0]),
            "min": float(weights[0]),
        }
    variance = sum((w - mean) ** 2 for w in weights) / n
    std = math.sqrt(variance)
    sorted_w = sorted(weights)
    if n % 2 == 1:
        median = float(sorted_w[n // 2])
    else:
        median = (sorted_w[n // 2 - 1] + sorted_w[n // 2]) / 2.0
    return {
        "mean": float(mean),
        "median": median,
        "variance": variance,
        "std": std,
        "max": float(max(weights)),
        "min": float(min(weights)),
    }


class BasicStructureAnalysis(BaseAnalysis):
    NAME = "basic_structure"
    def _run(self, prepared, config, result):
        g = prepared.graph
        result.metrics["node_count"] = g.vcount()
        result.metrics["edge_count"] = g.ecount()

        # Edge weight statistics
        # Priority: syn_count (biological name) → weight (igraph convention).
        if "syn_count" in g.edge_attributes():
            weights = list(g.es["syn_count"])
        elif "weight" in g.edge_attributes():
            weights = list(g.es["weight"])
        else:
            weights = None

        if weights is not None:
            result.metrics["total_synapses"] = sum(weights)
            w_stats = _weight_summary_stats(weights)
            result.metrics["weight_mean"] = w_stats["mean"]
            result.metrics["weight_median"] = w_stats["median"]
            result.metrics["weight_variance"] = w_stats["variance"]
            result.metrics["weight_std"] = w_stats["std"]
            result.metrics["weight_max"] = w_stats["max"]
            result.metrics["weight_min"] = w_stats["min"]
        else:
            result.metrics["total_synapses"] = g.ecount()
            # No weights available — set edge weight stats to zero
            for key in ["weight_mean", "weight_median", "weight_variance",
                        "weight_std", "weight_max", "weight_min"]:
                result.metrics[key] = 0.0
            result.warnings.append(
                "Graph has no 'syn_count' or 'weight' edge attribute; "
                "edge weight statistics set to zero."
            )

        result.metrics["density"] = g.density()


class ConnectedComponentsAnalysis(BaseAnalysis):
    NAME = "connected_components"
    def _run(self, prepared, config, result):
        g = prepared.graph

        # Weakly connected components
        wcc = g.components(mode="weak")
        wcc_sizes = wcc.sizes()
        result.metrics["wcc_count"] = len(wcc)
        result.metrics["wcc_max_size"] = max(wcc_sizes) if wcc_sizes else 0
        result.metrics["wcc_size_distribution"] = sorted(wcc_sizes, reverse=True)

        # Strongly connected components
        scc = g.components(mode="strong")
        scc_sizes = scc.sizes()
        result.metrics["scc_count"] = len(scc)
        result.metrics["scc_max_size"] = max(scc_sizes) if scc_sizes else 0
        result.metrics["scc_size_distribution"] = sorted(scc_sizes, reverse=True)


class ReciprocityAnalysis(BaseAnalysis):
    NAME = "reciprocity"
    def _run(self, prepared, config, result):
        result.metrics["reciprocity"] = prepared.graph.reciprocity()


registry.register(BasicStructureAnalysis, overwrite=True)
registry.register(ConnectedComponentsAnalysis, overwrite=True)
registry.register(ReciprocityAnalysis, overwrite=True)
