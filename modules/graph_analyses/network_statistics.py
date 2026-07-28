"""
Tier 2 — Network Statistics
"""
import math

from modules.graph_analyses.base_analysis import BaseAnalysis
from modules.graph_analyses.analysis_registry import registry


def _degree_summary_stats(degrees):
    """Compute summary statistics for a list of degree values.

    Returns a dict with mean, median, variance, stdev, max, min.
    Handles empty lists gracefully by returning zeros.
    """
    n = len(degrees)
    if n == 0:
        return {
            "mean": 0.0,
            "median": 0.0,
            "variance": 0.0,
            "std": 0.0,
            "max": 0,
            "min": 0,
        }
    mean = sum(degrees) / n
    if n == 1:
        return {
            "mean": float(mean),
            "median": float(degrees[0]),
            "variance": 0.0,
            "std": 0.0,
            "max": int(degrees[0]),
            "min": int(degrees[0]),
        }
    variance = sum((d - mean) ** 2 for d in degrees) / n
    std = math.sqrt(variance)
    sorted_deg = sorted(degrees)
    if n % 2 == 1:
        median = float(sorted_deg[n // 2])
    else:
        median = (sorted_deg[n // 2 - 1] + sorted_deg[n // 2]) / 2.0
    return {
        "mean": float(mean),
        "median": median,
        "variance": variance,
        "std": std,
        "max": int(max(degrees)),
        "min": int(min(degrees)),
    }


class DegreeDistributionAnalysis(BaseAnalysis):
    NAME = "degree_distribution"
    def _run(self, prepared, config, result):
        g = prepared.graph
        in_degrees = g.indegree()
        out_degrees = g.outdegree()
        total_degrees = [i + o for i, o in zip(in_degrees, out_degrees)]

        # Raw degree vectors for downstream vector comparison.
        result.metrics["in_degrees"] = in_degrees
        result.metrics["out_degrees"] = out_degrees

        # Summary statistics — computed from the already-fetched vectors.
        in_stats = _degree_summary_stats(in_degrees)
        out_stats = _degree_summary_stats(out_degrees)
        total_stats = _degree_summary_stats(total_degrees)

        for prefix, stats in [("in", in_stats), ("out", out_stats), ("total", total_stats)]:
            result.metrics[f"{prefix}_degree_mean"] = stats["mean"]
            result.metrics[f"{prefix}_degree_median"] = stats["median"]
            result.metrics[f"{prefix}_degree_variance"] = stats["variance"]
            result.metrics[f"{prefix}_degree_std"] = stats["std"]
            result.metrics[f"{prefix}_degree_max"] = stats["max"]
            result.metrics[f"{prefix}_degree_min"] = stats["min"]


class PageRankAnalysis(BaseAnalysis):
    NAME = "pagerank"
    def _run(self, prepared, config, result):
        g = prepared.graph
        # Priority: syn_count (biological name) → weight (igraph convention).
        weights = (
            "syn_count" if "syn_count" in g.edge_attributes()
            else "weight" if "weight" in g.edge_attributes()
            else None
        )
        damping = config.get("damping", 0.85)
        result.metrics["pagerank_scores"] = g.pagerank(weights=weights, damping=damping)


registry.register(DegreeDistributionAnalysis, overwrite=True)
registry.register(PageRankAnalysis, overwrite=True)
