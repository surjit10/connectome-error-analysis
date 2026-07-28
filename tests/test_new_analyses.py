"""
Tests for the newly implemented graph analyses:

1. Degree Summary Statistics
2. Component Size Distribution
3. Assortativity
4. Edge Weight Statistics
"""

import math
import pytest
import igraph

from modules.graph_analyses.network_statistics import DegreeDistributionAnalysis
from modules.graph_analyses.structural import BasicStructureAnalysis, ConnectedComponentsAnalysis
from modules.graph_analyses.assortativity import AssortativityAnalysis
from modules.preprocessing import preprocess_graph


# =========================================================================
# Helper: build a small PreparedGraph from a synthetic igraph.Graph
# =========================================================================

def _make_prepared(g, dataset_name="test"):
    g["dataset_name"] = dataset_name
    return preprocess_graph(g)


# =========================================================================
# Degree Summary Statistics
# =========================================================================

class TestDegreeSummaryStats:
    def test_small_graph(self):
        """Verify summary stats on a simple 4-node directed graph."""
        g = igraph.Graph(directed=True)
        g.add_vertices(4)
        g.add_edges([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
        prepared = _make_prepared(g)

        analysis = DegreeDistributionAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"

        # in-degrees: node0=1, node1=1, node2=2, node3=1  → mean=1.25
        assert result.metrics["in_degree_mean"] == pytest.approx(1.25)
        # out-degrees: node0=2, node1=1, node2=1, node3=1  → mean=1.25
        assert result.metrics["out_degree_mean"] == pytest.approx(1.25)
        # total degrees: node0=3, node1=2, node2=3, node3=2  → mean=2.5
        assert result.metrics["total_degree_mean"] == pytest.approx(2.5)

        # Check min/max
        assert result.metrics["in_degree_max"] == 2
        assert result.metrics["in_degree_min"] == 1
        assert result.metrics["out_degree_max"] == 2
        assert result.metrics["out_degree_min"] == 1
        assert result.metrics["total_degree_max"] == 3
        assert result.metrics["total_degree_min"] == 2

        # Check variance ≥ 0
        assert result.metrics["in_degree_variance"] >= 0
        assert result.metrics["out_degree_variance"] >= 0
        assert result.metrics["total_degree_variance"] >= 0

    def test_empty_graph(self):
        """An empty graph (no vertices) — all stats should be zero."""
        g = igraph.Graph(directed=True)
        prepared = _make_prepared(g)

        analysis = DegreeDistributionAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        for key in ["mean", "median", "variance", "std", "max", "min"]:
            assert result.metrics[f"in_degree_{key}"] == 0
            assert result.metrics[f"out_degree_{key}"] == 0
            assert result.metrics[f"total_degree_{key}"] == 0

    def test_single_node(self):
        """A single node with no edges."""
        g = igraph.Graph(directed=True)
        g.add_vertices(1)
        prepared = _make_prepared(g)

        analysis = DegreeDistributionAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["in_degree_mean"] == 0.0
        assert result.metrics["in_degree_median"] == 0.0
        assert result.metrics["in_degree_max"] == 0
        assert result.metrics["in_degree_min"] == 0
        assert result.metrics["out_degree_mean"] == 0.0

    def test_directed_graph_with_self_loop(self):
        """Directed graph with a self-loop.

        In igraph, a self-loop counts 1 toward both indegree and outdegree
        of the looped vertex (not 2).  With edges [(0,0), (0,1)]:
          indegrees: node0=1, node1=1  → mean=1.0
        """
        g = igraph.Graph(directed=True)
        g.add_vertices(2)
        g.add_edges([(0, 0), (0, 1)])
        prepared = _make_prepared(g)

        analysis = DegreeDistributionAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["in_degree_mean"] == pytest.approx(1.0)


# =========================================================================
# Component Size Distribution
# =========================================================================

class TestComponentSizeDistribution:
    def test_single_component(self):
        """A single strongly connected component."""
        g = igraph.Graph(directed=True)
        g.add_vertices(3)
        g.add_edges([(0, 1), (1, 2), (2, 0)])
        prepared = _make_prepared(g)

        analysis = ConnectedComponentsAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["wcc_count"] == 1
        assert result.metrics["wcc_max_size"] == 3
        assert result.metrics["wcc_size_distribution"] == [3]

        assert result.metrics["scc_count"] == 1
        assert result.metrics["scc_max_size"] == 3
        assert result.metrics["scc_size_distribution"] == [3]

    def test_multiple_components(self):
        """Two disconnected components."""
        g = igraph.Graph(directed=True)
        g.add_vertices(5)
        g.add_edges([(0, 1), (1, 2), (3, 4)])
        prepared = _make_prepared(g)

        analysis = ConnectedComponentsAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["wcc_count"] == 2
        assert result.metrics["wcc_max_size"] == 3
        # Distribution sorted descending
        assert result.metrics["wcc_size_distribution"] == [3, 2]

        # SCCs (each edge is in its own SCC for directed)
        assert result.metrics["scc_size_distribution"] is not None

    def test_empty_graph(self):
        """No vertices — should handle gracefully."""
        g = igraph.Graph(directed=True)
        prepared = _make_prepared(g)

        analysis = ConnectedComponentsAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["wcc_count"] == 0
        assert result.metrics["wcc_max_size"] == 0
        assert result.metrics["wcc_size_distribution"] == []

        assert result.metrics["scc_count"] == 0
        assert result.metrics["scc_max_size"] == 0
        assert result.metrics["scc_size_distribution"] == []

    def test_single_node_isolated(self):
        """Single isolated node — one WCC of size 1."""
        g = igraph.Graph(directed=True)
        g.add_vertices(1)
        prepared = _make_prepared(g)

        analysis = ConnectedComponentsAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["wcc_count"] == 1
        assert result.metrics["wcc_max_size"] == 1
        assert result.metrics["wcc_size_distribution"] == [1]


# =========================================================================
# Assortativity
# =========================================================================

class TestAssortativity:
    def test_assortativity_executes(self):
        """Assortativity returns a float metric on a graph with varied
        source out-degrees and target in-degrees.

        Uses a chain with extra edges to create degree variation on both
        sides of the edge endpoints.
        """
        g = igraph.Graph(directed=True)
        g.add_vertices(10)
        # Chain: 0→1→2→3→4→5→6→7→8→9
        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5),
                 (5, 6), (6, 7), (7, 8), (8, 9)]
        # Extra edges from node 0 (gives it outdeg=3)
        edges += [(0, 2), (0, 3)]
        # Back edges (gives some nodes indeg > 1)
        edges += [(7, 5), (8, 6)]
        g.add_edges(edges)
        prepared = _make_prepared(g)

        analysis = AssortativityAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert "degree_assortativity" in result.metrics
        val = result.metrics["degree_assortativity"]
        assert not math.isnan(val), (
            f"assortativity_degree returned NaN on graph with "
            f"out-degrees={g.outdegree()} in-degrees={g.indegree()}"
        )
        assert -1.0 <= val <= 1.0
        assert isinstance(val, float)

    def test_assortativity_disassortative(self):
        """A directed graph where a hub feeds many leaves should be
        disassortative (negative assortativity).

        Graph: 0→1, 0→2, 0→3, 0→4, 5→0, 6→0, 7→0
        Node 0: outdeg=4, indeg=3 (hub)
        Leaves 1-4: indeg=1, outdeg=0
        Nodes 5-7: outdeg=1, indeg=0
        """
        g = igraph.Graph(directed=True)
        g.add_vertices(8)
        g.add_edges([
            (0, 1), (0, 2), (0, 3), (0, 4),  # hub → leaves
            (5, 0), (6, 0), (7, 0),           # feeders → hub
        ])
        prepared = _make_prepared(g)

        analysis = AssortativityAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        val = result.metrics["degree_assortativity"]
        assert not math.isnan(val), (
            f"assortativity_degree returned NaN on disassortative graph: "
            f"out-degrees={g.outdegree()} in-degrees={g.indegree()}"
        )
        # Hub connecting to leaves should give negative assortativity
        assert val < 0, f"Expected negative assortativity, got {val}"

    def test_empty_graph(self):
        """Empty graph should still succeed."""
        g = igraph.Graph(directed=True)
        prepared = _make_prepared(g)

        analysis = AssortativityAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        # Edge case: igraph returns NaN or 0 for empty graphs
        assert "degree_assortativity" in result.metrics


# =========================================================================
# Edge Weight Statistics
# =========================================================================

class TestEdgeWeightStats:
    def test_weighted_graph(self):
        """Verify weight stats for a simple weighted graph."""
        g = igraph.Graph(directed=True)
        g.add_vertices(3)
        g.add_edges([(0, 1), (1, 2), (0, 2)])
        g.es["weight"] = [5.0, 10.0, 2.0]
        prepared = _make_prepared(g)

        analysis = BasicStructureAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["total_synapses"] == pytest.approx(17.0)
        assert result.metrics["weight_mean"] == pytest.approx(17.0 / 3)
        assert result.metrics["weight_median"] == pytest.approx(5.0)
        assert result.metrics["weight_max"] == pytest.approx(10.0)
        assert result.metrics["weight_min"] == pytest.approx(2.0)
        assert result.metrics["weight_variance"] >= 0
        assert result.metrics["weight_std"] >= 0

    def test_unweighted_graph(self):
        """Graph without a 'weight' attribute — falls back gracefully."""
        g = igraph.Graph(directed=True)
        g.add_vertices(3)
        g.add_edges([(0, 1), (1, 2)])
        prepared = _make_prepared(g)

        analysis = BasicStructureAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        # Without weight attribute, total_synapses = edge_count
        assert result.metrics["total_synapses"] == 2
        # Edge weight stats should be zero (and a warning emitted)
        assert result.metrics["weight_mean"] == 0.0
        assert result.metrics["weight_median"] == 0.0
        assert result.metrics["weight_max"] == 0.0
        assert result.metrics["weight_min"] == 0.0
        assert len(result.warnings) > 0
        assert any("weight" in w for w in result.warnings)

    def test_empty_graph(self):
        """Empty graph (no edges)."""
        g = igraph.Graph(directed=True)
        g.add_vertices(2)
        prepared = _make_prepared(g)

        analysis = BasicStructureAnalysis()
        result = analysis.execute(prepared)

        assert result.status.value == "SUCCESS"
        assert result.metrics["edge_count"] == 0
        assert result.metrics["total_synapses"] == 0
        assert result.metrics["weight_mean"] == 0.0
        assert result.metrics["weight_median"] == 0.0
        assert result.metrics["weight_max"] == 0.0
        assert result.metrics["weight_min"] == 0.0
