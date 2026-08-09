"""
EM4 – Split Errors (Segmentation Fragmentation): unit and integration tests.

Covers, per the EM4 specification:
    - deterministic behaviour (same seed -> identical split plan)
    - graph integrity (edge count / synapse count preserved)
    - edge preservation (no edge loss, no duplication)
    - fragment validation (min partners per fragment)
    - retry logic (rejection -> sample another neuron)
    - Louvain fallback (connected ego graph -> community detection)
    - connected components (naturally fragmented ego graph)
    - graph validity (no self-loops, no duplicate edges, valid node IDs)
    - reproducibility (full pipeline, same seed -> same metrics)
    - compatibility with the existing framework (registry, statistics,
      metadata, export)

The baseline graph is asserted immutable in every test that touches it.
"""

import gzip

import igraph
import pytest

from modules.preprocessing import preprocess_graph


# ---------------------------------------------------------------------------
# Synthetic graph builders
# ---------------------------------------------------------------------------

def _finalise(graph: igraph.Graph, root_ids) -> igraph.Graph:
    """Attach the id maps + dataset name and give every edge a weight."""
    n = len(root_ids)
    if "syn_count" not in graph.edge_attributes():
        graph.es["syn_count"] = [1] * graph.ecount()
    if "super_class" not in graph.vertex_attributes():
        graph.vs["super_class"] = ["neuron"] * n
    graph["dataset_name"] = "TEST"
    graph["id_to_idx"] = {rid: i for i, rid in enumerate(root_ids)}
    graph["id_map"] = {i: rid for rid, i in graph["id_to_idx"].items()}
    return graph


def build_two_cluster_hub(n_per_cluster: int = 6) -> igraph.Graph:
    """Hub root 1000 with 2*n_per_cluster partners in two DISJOINT cliques.

    The (centre-removed) ego graph has exactly 2 connected components, so the
    split is deterministic (no Louvain fallback required).
    """
    n = 1 + 2 * n_per_cluster
    g = igraph.Graph(directed=True)
    g.add_vertices(n)
    root_ids = [1000] + list(range(1, n))
    g.vs["root_id"] = root_ids
    edges = []
    for p in range(1, n):
        edges.append((0, p))
    for a in range(1, 1 + n_per_cluster):
        for b in range(1, 1 + n_per_cluster):
            if a < b:
                edges.append((a, b))
    for a in range(1 + n_per_cluster, n):
        for b in range(1 + n_per_cluster, n):
            if a < b:
                edges.append((a, b))
    g.add_edges(edges)
    return _finalise(g, root_ids)


def build_autapse_hub_graph(n_per_cluster: int = 6) -> igraph.Graph:
    """``build_two_cluster_hub`` plus a self-loop (autapse) on the hub.

    Root 1000 has 2*n_per_cluster partners in two DISJOINT cliques AND an
    autapse edge 1000 -> 1000.  Regression graph for the MANC autapse crash:
    the centre must not count itself as a partner, and the autapse must be
    dropped and counted (``self_loops_dropped``) instead of crashing the
    exhaustive-partition validation.
    """
    n = 1 + 2 * n_per_cluster
    g = igraph.Graph(directed=True)
    g.add_vertices(n)
    root_ids = [1000] + list(range(1, n))
    g.vs["root_id"] = root_ids
    edges = [(0, 0)]  # autapse on the hub
    for p in range(1, n):
        edges.append((0, p))
    for a in range(1, 1 + n_per_cluster):
        for b in range(1, 1 + n_per_cluster):
            if a < b:
                edges.append((a, b))
    for a in range(1 + n_per_cluster, n):
        for b in range(1 + n_per_cluster, n):
            if a < b:
                edges.append((a, b))
    g.add_edges(edges)
    return _finalise(g, root_ids)


def build_butterfly_hub(k: int = 5) -> igraph.Graph:
    """Hub root 1000 with 2k partners: two cliques of k joined by a bridge.

    The (centre-removed) ego graph is CONNECTED -> Louvain fallback path.
    """
    n = 1 + 2 * k
    g = igraph.Graph(directed=True)
    g.add_vertices(n)
    root_ids = [1000] + list(range(1, n))
    g.vs["root_id"] = root_ids
    edges = []
    for p in range(1, n):
        edges.append((0, p))
    for a in range(1, 1 + k):
        for b in range(1, 1 + k):
            if a < b:
                edges.append((a, b))
    for a in range(1 + k, n):
        for b in range(1 + k, n):
            if a < b:
                edges.append((a, b))
    edges.append((k, k + 1))  # the single bridge edge
    g.add_edges(edges)
    return _finalise(g, root_ids)


def build_retry_graph() -> igraph.Graph:
    """Two eligible neurons: root 1000 (K10 clique -> always rejected) and
    root 2000 (two disjoint cliques -> always splits)."""
    n = 22
    g = igraph.Graph(directed=True)
    root_ids = [1000] + list(range(1, 11)) + [2000] + list(range(11, 21))
    g.add_vertices(n)
    g.vs["root_id"] = root_ids
    edges = []
    # Bad centre: vertex 0 (root 1000) + K10 clique on vertices 1..10.
    for p in range(1, 11):
        edges.append((0, p))
    for a in range(1, 11):
        for b in range(1, 11):
            if a < b:
                edges.append((a, b))
    # Good centre: vertex 11 (root 2000) + two cliques of 5.
    for p in range(12, 22):
        edges.append((11, p))
    for a in range(12, 17):
        for b in range(12, 17):
            if a < b:
                edges.append((a, b))
    for a in range(17, 22):
        for b in range(17, 22):
            if a < b:
                edges.append((a, b))
    g.add_edges(edges)
    return _finalise(g, root_ids)


def build_mutual_split_graph() -> igraph.Graph:
    """Two ADJACENT split neurons: A (root 1000) <-> B (root 2000).

    Vertex layout (root ids):
        v0     = A   (1000)
        v1..6  = A's clique X  (roots 1001..1006)
        v7..12 = A's clique Y  (roots 1007..1012)
        v13    = B   (2000)
        v14..19 = B's clique X' (roots 2001..2006)
        v20..25 = B's clique Y' (roots 2007..2012)

    A's ego has 3 components (clique X, clique Y, B) -> splits 7/6;
    B's ego likewise.  Both are eligible (degree 14).  The A—B edges must
    be chained to the correct fragment pair (regression test for the
    mutual-split rewiring path).
    """
    g = igraph.Graph(directed=True)
    root_ids = (
        [1000]
        + [1000 + i for i in range(1, 13)]   # v1..v12  -> 1001..1012
        + [2000]
        + [2000 + i for i in range(1, 13)]   # v14..v25 -> 2001..2012
    )
    assert len(root_ids) == 26
    g.add_vertices(26)
    g.vs["root_id"] = root_ids
    edges = []
    # A (v0) -> all partners v1..v12.
    for p in range(1, 13):
        edges.append((0, p))
    # Clique X (v1..v6) and clique Y (v7..v12).
    for a in range(1, 7):
        for b in range(1, 7):
            if a < b:
                edges.append((a, b))
    for a in range(7, 13):
        for b in range(7, 13):
            if a < b:
                edges.append((a, b))
    # A <-> B.
    edges.append((0, 13))
    edges.append((13, 0))
    # B (v13) -> all partners v14..v25.
    for p in range(14, 26):
        edges.append((13, p))
    # Clique X' (v14..v19) and clique Y' (v20..v25).
    for a in range(14, 20):
        for b in range(14, 20):
            if a < b:
                edges.append((a, b))
    for a in range(20, 26):
        for b in range(20, 26):
            if a < b:
                edges.append((a, b))
    g.add_edges(edges)
    return _finalise(g, root_ids)


def build_ineligible_graph() -> igraph.Graph:
    """Hub root 1000 with degree 8 (< threshold 10) -> not eligible."""
    g = igraph.Graph(directed=True)
    root_ids = [1000] + list(range(1, 9))
    g.add_vertices(9)
    g.vs["root_id"] = root_ids
    edges = [(0, p) for p in range(1, 9)]
    g.add_edges(edges)  # star: centre + 8 leaves
    return _finalise(g, root_ids)


@pytest.fixture
def hub_prepared():
    return preprocess_graph(build_two_cluster_hub(), index_node_attrs=[])


@pytest.fixture
def butterfly_prepared():
    return preprocess_graph(build_butterfly_hub(), index_node_attrs=[])


# ---------------------------------------------------------------------------
# Unit tests — model behaviour
# ---------------------------------------------------------------------------

class TestSplitModel:
    def test_model_registered(self) -> None:
        from modules.error_models.common.error_registry import (
            registry as error_registry,
        )
        assert error_registry.is_registered("split_errors")

    def test_determinism_same_seed(self, hub_prepared) -> None:
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        cfg = {"error_rate": 1.0, "degree_threshold": 10,
               "min_fragment_partners": 3}
        r1 = model.execute(hub_prepared, config=cfg, seed=42)
        r2 = model.execute(hub_prepared, config=cfg, seed=42)
        assert r1.succeeded and r2.succeeded
        assert r1.extra["split_plan"] == r2.extra["split_plan"]

    def test_connected_components_split(self, hub_prepared) -> None:
        """Two disjoint cliques -> 2 CCs -> deterministic 6/6 split."""
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            hub_prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )
        assert result.succeeded
        plan = result.extra["split_plan"]
        assert set(plan.keys()) == {1000}
        split = plan[1000]
        assert split["fallback_used"] is False
        assert split["community_count"] == 2
        sizes = [len(p) for p in split["fragment_partners"].values()]
        assert sorted(sizes) == [6, 6]
        assert split["edges_rewired"] == 12

    def test_autapse_centre_splits_without_crashing(self) -> None:
        """MANC regression: a centre with a self-loop must not raise
        'Partner partition is not exhaustive' (the centre is never its own
        partner); the autapse is dropped and counted, not rewired."""
        prepared = preprocess_graph(
            build_autapse_hub_graph(), index_node_attrs=[]
        )
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )
        assert result.succeeded
        plan = result.extra["split_plan"]
        assert set(plan.keys()) == {1000}
        split = plan[1000]
        # Exactly the 12 real partners — never the centre itself.
        fragments = list(split["fragment_partners"].values())
        union = set(fragments[0]) | set(fragments[1])
        assert union == set(range(1, 13))
        assert 1000 not in union
        assert len(fragments[0]) + len(fragments[1]) == 12
        # Autapse bookkeeping: dropped once, not rewired.
        assert split["self_loops_dropped"] == 1
        assert split["edges_rewired"] == 12
        assert result.perturbation_metadata["self_loops_dropped"] == 1
        assert result.perturbation_metadata["edges_rewired"] == 12

    def test_self_loop_only_neuron_rejected_not_crashed(self) -> None:
        """A neuron whose only edge is its own autapse is rejected (empty
        split plan -> baseline analyses), never crashes."""
        g = igraph.Graph(directed=True)
        g.add_vertices(1)
        g.vs["root_id"] = [5000]
        g.add_edges([(0, 0)])
        _finalise(g, [5000])
        prepared = preprocess_graph(g, index_node_attrs=[])
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            prepared,
            config={"error_rate": 1.0, "degree_threshold": 1,
                    "min_fragment_partners": 3},
            seed=42,
        )
        assert result.succeeded
        assert result.extra["split_plan"] == {}

    def test_partner_partition_complete_and_disjoint(self, hub_prepared) -> None:
        """Every partner is assigned to exactly one fragment (no loss/dup)."""
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            hub_prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )
        split = result.extra["split_plan"][1000]
        fragments = list(split["fragment_partners"].values())
        union = set(fragments[0]) | set(fragments[1])
        assert union == set(range(1, 13))          # all 12 partners covered
        assert len(fragments[0]) + len(fragments[1]) == 12  # no duplicates

    def test_louvain_fallback(self, butterfly_prepared) -> None:
        """Connected ego graph -> Louvain fallback -> 2 fragments."""
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            butterfly_prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )
        assert result.succeeded
        plan = result.extra["split_plan"]
        assert 1000 in plan
        split = plan[1000]
        assert split["fallback_used"] is True
        assert split["community_count"] >= 2
        sizes = [len(p) for p in split["fragment_partners"].values()]
        assert min(sizes) >= 3
        assert sum(sizes) == 10

    def test_degree_below_threshold_not_eligible(self) -> None:
        from modules.error_models import registry

        prepared = preprocess_graph(
            build_ineligible_graph(), index_node_attrs=[]
        )
        model = registry.instantiate("split_errors")
        result = model.execute(
            prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )
        assert result.succeeded
        assert result.perturbation_metadata["eligible_neurons"] == 0
        assert result.perturbation_metadata["neurons_split"] == 0
        assert result.extra.get("split_plan") == {}

    def test_rejection_and_retry(self) -> None:
        """Clique ego (1 Louvain community) is rejected; the other neuron
        still splits.  The model reports the rejection."""
        from modules.error_models import registry

        prepared = preprocess_graph(build_retry_graph(), index_node_attrs=[])
        model = registry.instantiate("split_errors")
        result = model.execute(
            prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3, "max_retries": 20},
            seed=42,
        )
        assert result.succeeded
        plan = result.extra["split_plan"]
        assert 1000 not in plan                # clique rejected
        assert 2000 in plan                    # good neuron split
        assert result.perturbation_metadata["neurons_rejected"] >= 1

    def test_zero_error_rate_splits_nothing(self, hub_prepared) -> None:
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            hub_prepared,
            config={"error_rate": 0.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )
        assert result.succeeded
        assert result.perturbation_metadata["neurons_split"] == 0

    def test_baseline_graph_never_modified(self, hub_prepared) -> None:
        from modules.error_models import registry

        vcount, ecount = (
            hub_prepared.graph.vcount(), hub_prepared.graph.ecount()
        )
        model = registry.instantiate("split_errors")
        model.execute(
            hub_prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )
        assert hub_prepared.graph.vcount() == vcount
        assert hub_prepared.graph.ecount() == ecount

    def test_no_module_level_graph_cache_retains_graphs(self) -> None:
        """EM4 must not retain baseline graphs between trials.

        Regression test for the notebook OOM root cause: a module-level
        ``_candidate_cache`` keyed by ``id(graph)`` kept a strong reference
        to every trial's freshly-built baseline graph, so a 45-trial
        notebook run pinned ~45 full connectome copies in RAM.  After the
        fix there is no such cache and old graphs must be garbage-collectable
        once a trial finishes.
        """
        import gc
        import weakref

        from modules.error_models import registry as error_registry
        import modules.error_models.split_errors.model as split_model

        assert not hasattr(split_model, "_candidate_cache")

        model = error_registry.instantiate("split_errors")
        cfg = {"error_rate": 0.5, "degree_threshold": 10,
               "min_fragment_partners": 3, "max_retries": 20}

        refs = []
        for t in range(3):
            prepared = preprocess_graph(
                build_two_cluster_hub(), index_node_attrs=[]
            )
            refs.append(weakref.ref(prepared.graph))
            model.execute(prepared, config=cfg, seed=t)
            del prepared

        gc.collect()
        assert all(r() is None for r in refs), (
            "EM4 must not retain strong references to trial graphs"
        )

    def test_unknown_config_key_warns(self, hub_prepared) -> None:
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            hub_prepared,
            config={"error_rate": 1.0, "bogus_key": 1},
            seed=42,
        )
        assert any("bogus_key" in w for w in result.warnings)

    def test_invalid_error_rate_rejected(self, hub_prepared) -> None:
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        result = model.execute(
            hub_prepared,
            config={"error_rate": 1.5, "degree_threshold": 10},
            seed=42,
        )
        assert result.failed


# ---------------------------------------------------------------------------
# Temporary graph construction tests (SplitExperimentRunner._split_build_temp_graph)
# ---------------------------------------------------------------------------

class TestTempGraphConstruction:
    def _build_runner_result(self, prepared):
        """Produce an ErrorResult carrying a split_plan via the real model."""
        from modules.error_models import registry

        model = registry.instantiate("split_errors")
        return model.execute(
            prepared,
            config={"error_rate": 1.0, "degree_threshold": 10,
                    "min_fragment_partners": 3},
            seed=42,
        )

    def _temp_graph(self, prepared, error_result):
        from core.experiment_runner import ExperimentConfig, ExperimentResult
        from core.split_experiment_runner import SplitExperimentRunner
        from modules.graph_analyses.analysis_registry import (
            registry as a_reg,
        )
        from modules.error_models.common.error_registry import (
            registry as e_reg,
        )

        runner = SplitExperimentRunner(a_reg, e_reg)
        config = ExperimentConfig(dataset_name="TEST", dataset_root="x")
        result = ExperimentResult(experiment_id="t", dataset_name="TEST")
        temp_graph, temp_prepared = runner._split_build_temp_graph(
            prepared, error_result, config, result
        )
        return temp_graph, temp_prepared

    def test_edge_and_synapse_count_preserved(self, hub_prepared) -> None:
        baseline = hub_prepared.graph
        err = self._build_runner_result(hub_prepared)
        temp, temp_prepared = self._temp_graph(hub_prepared, err)
        assert temp is not None
        assert temp.ecount() == baseline.ecount()
        assert sum(temp.es["syn_count"]) == sum(baseline.es["syn_count"])

    def test_node_count_grows_by_one_per_split(self, hub_prepared) -> None:
        baseline = hub_prepared.graph
        err = self._build_runner_result(hub_prepared)
        temp, _ = self._temp_graph(hub_prepared, err)
        n_splits = len(err.extra["split_plan"])
        assert temp.vcount() == baseline.vcount() + n_splits

    def test_no_self_loops_no_duplicates(self, hub_prepared) -> None:
        err = self._build_runner_result(hub_prepared)
        temp, _ = self._temp_graph(hub_prepared, err)
        loops = [e.index for e in temp.es if temp.is_loop(e.index)]
        assert loops == []
        assert temp.has_multiple() is False

    def test_all_edges_valid_and_weighted(self, hub_prepared) -> None:
        err = self._build_runner_result(hub_prepared)
        temp, _ = self._temp_graph(hub_prepared, err)
        for e in temp.es:
            assert 0 <= e.source < temp.vcount()
            assert 0 <= e.target < temp.vcount()
            assert e["syn_count"] >= 1

    def test_fragment_vertices_present_in_temp_lookup(self, hub_prepared) -> None:
        err = self._build_runner_result(hub_prepared)
        plan = err.extra["split_plan"][1000]
        temp, temp_prepared = self._temp_graph(hub_prepared, err)
        temp_id_to_idx = temp["id_to_idx"]
        for fid in plan["fragment_ids"]:
            assert fid in temp_id_to_idx
            assert fid in temp_prepared.lookup.node_set
        # Original split neuron is gone from the temp graph.
        assert 1000 not in temp_id_to_idx

    def test_fragment_edges_rewired_by_partner(self, hub_prepared) -> None:
        """Edges incident to the original neuron now touch the fragment of
        their partner, with weights preserved."""
        err = self._build_runner_result(hub_prepared)
        plan = err.extra["split_plan"][1000]
        frag_ids = set(plan["fragment_ids"])
        temp, _ = self._temp_graph(hub_prepared, err)

        partner_to_frag = {}
        for fid, partners in plan["fragment_partners"].items():
            for p in partners:
                partner_to_frag[p] = fid

        # Every edge touching a fragment vertex must point at a partner that
        # belongs to that fragment, and the weight must match the baseline.
        baseline = hub_prepared.graph
        baseline_weight = {
            (baseline.vs[e.source]["root_id"],
             baseline.vs[e.target]["root_id"]): e["syn_count"]
            for e in baseline.es
        }
        seen = set()
        for e in temp.es:
            src, tgt = temp.vs[e.source]["root_id"], temp.vs[e.target]["root_id"]
            if src in frag_ids or tgt in frag_ids:
                fid = src if src in frag_ids else tgt
                partner = tgt if src in frag_ids else src
                assert partner_to_frag[partner] == fid, (
                    f"edge ({src},{tgt}) rewired to wrong fragment"
                )
                # weight preserved
                if src in frag_ids:
                    key = (1000, partner)
                else:
                    key = (partner, 1000)
                assert e["syn_count"] == baseline_weight[key]
                seen.add((src, tgt))
        # 12 incident edges, none duplicated
        assert len(seen) == 12

    def test_baseline_unchanged_after_temp_build(self, hub_prepared) -> None:
        baseline = hub_prepared.graph
        vcount, ecount = baseline.vcount(), baseline.ecount()
        err = self._build_runner_result(hub_prepared)
        self._temp_graph(hub_prepared, err)
        assert baseline.vcount() == vcount
        assert baseline.ecount() == ecount

    def test_autapse_dropped_in_temp_graph(self) -> None:
        """The autapse of a split centre is dropped (not rewired): the temp
        graph has no self-loops, edge/synapse counts drop by exactly the
        autapse, and all 12 partner edges are rewired to the fragments."""
        prepared = preprocess_graph(
            build_autapse_hub_graph(), index_node_attrs=[]
        )
        baseline = prepared.graph
        err = self._build_runner_result(prepared)
        plan = err.extra["split_plan"]
        assert set(plan.keys()) == {1000}
        assert plan[1000]["self_loops_dropped"] == 1

        from core.experiment_runner import ExperimentConfig, ExperimentResult
        from core.split_experiment_runner import SplitExperimentRunner
        from modules.graph_analyses.analysis_registry import (
            registry as a_reg,
        )
        from modules.error_models.common.error_registry import (
            registry as e_reg,
        )

        runner = SplitExperimentRunner(a_reg, e_reg)
        config = ExperimentConfig(dataset_name="TEST", dataset_root="x")
        result = ExperimentResult(experiment_id="t", dataset_name="TEST")
        temp, temp_prepared = runner._split_build_temp_graph(
            prepared, err, config, result
        )
        assert temp is not None
        # The autapse is dropped: exactly one fewer edge and synapse.
        assert temp.ecount() == baseline.ecount() - 1
        assert sum(temp.es["syn_count"]) == sum(baseline.es["syn_count"]) - 1
        # No self-loops, no duplicates anywhere in the temp graph.
        loops = [e.index for e in temp.es if temp.is_loop(e.index)]
        assert loops == []
        assert temp.has_multiple() is False
        # Original centre replaced by two fragments; 12 partner edges remain.
        temp_roots = set(temp.vs["root_id"])
        assert 1000 not in temp_roots
        frag_ids = set(plan[1000]["fragment_ids"])
        assert frag_ids <= temp_roots
        partner_edges = [
            e for e in temp.es
            if temp.vs[e.source]["root_id"] in frag_ids
            or temp.vs[e.target]["root_id"] in frag_ids
        ]
        assert len(partner_edges) == 12
        # Ground-truth autapse count recorded, no bookkeeping mismatch.
        assert err.perturbation_metadata["self_loops_dropped"] == 1
        assert not any(
            "Self-loop bookkeeping mismatch" in w for w in result.warnings
        )

    def test_mutual_split_rewiring(self) -> None:
        """Two adjacent split neurons: the A—B edges are chained to the
        correct fragment pair and the temp graph stays fully valid."""
        prepared = preprocess_graph(
            build_mutual_split_graph(), index_node_attrs=[]
        )
        baseline = prepared.graph
        err = self._build_runner_result(prepared)
        plan = err.extra["split_plan"]
        assert set(plan.keys()) == {1000, 2000}  # both split

        temp, _ = self._temp_graph(prepared, err)
        assert temp is not None

        # Graph integrity: edges, synapses, node count.
        assert temp.ecount() == baseline.ecount()
        assert sum(temp.es["syn_count"]) == sum(baseline.es["syn_count"])
        assert temp.vcount() == baseline.vcount() + 2

        # Graph validity: no self-loops, no duplicates, no orphans.
        loops = [e.index for e in temp.es if temp.is_loop(e.index)]
        assert loops == []
        assert temp.has_multiple() is False
        degrees = temp.degree()
        assert all(d >= 1 for d in degrees)

        # Original neurons replaced by their fragments.
        temp_roots = set(temp.vs["root_id"])
        assert 1000 not in temp_roots and 2000 not in temp_roots
        frags = set()
        for p in plan.values():
            frags.update(p["fragment_ids"])
        assert frags <= temp_roots and len(frags) == 4

        # The A—B edges must connect the fragment of A that holds B to the
        # fragment of B that holds A, in both directions.
        a_frag_for_b = next(
            fid for fid, parts in plan[1000]["fragment_partners"].items()
            if 2000 in parts
        )
        b_frag_for_a = next(
            fid for fid, parts in plan[2000]["fragment_partners"].items()
            if 1000 in parts
        )
        cross = [
            (temp.vs[e.source]["root_id"], temp.vs[e.target]["root_id"])
            for e in temp.es
            if {temp.vs[e.source]["root_id"],
                temp.vs[e.target]["root_id"]} == {a_frag_for_b, b_frag_for_a}
        ]
        assert sorted(cross) == sorted([
            (a_frag_for_b, b_frag_for_a),
            (b_frag_for_a, a_frag_for_b),
        ]), cross

    def test_empty_plan_returns_none(self, hub_prepared) -> None:
        from core.experiment_runner import ExperimentConfig, ExperimentResult
        from core.split_experiment_runner import SplitExperimentRunner
        from modules.graph_analyses.analysis_registry import (
            registry as a_reg,
        )
        from modules.error_models.common.error_registry import (
            registry as e_reg,
        )
        from modules.error_models.common.error_result import ErrorResult

        runner = SplitExperimentRunner(a_reg, e_reg)
        err = ErrorResult(model_name="split_errors")
        config = ExperimentConfig(dataset_name="TEST", dataset_root="x")
        result = ExperimentResult(experiment_id="t", dataset_name="TEST")
        temp_graph, temp_prepared = runner._split_build_temp_graph(
            hub_prepared, err, config, result
        )
        assert temp_graph is None and temp_prepared is None


# ---------------------------------------------------------------------------
# Full pipeline integration tests (dataset on disk -> SplitExperimentRunner)
# ---------------------------------------------------------------------------

@pytest.fixture
def split_dataset(tmp_path):
    """Create TEST_v1 dataset + configs on disk with a split-prone hub."""
    data_dir = tmp_path / "data" / "TEST_v1"
    data_dir.mkdir(parents=True)

    root_ids = [1000] + list(range(1, 13))
    neurons = "root_id,super_class,top_region\n" + "\n".join(
        f"{rid},neuron,AL" for rid in root_ids
    ) + "\n"
    with gzip.open(data_dir / "neurons.csv.gz", "wt") as f:
        f.write(neurons)

    edges = []
    for p in range(1, 7):
        edges.append((1000, p, 2))
    for p in range(7, 13):
        edges.append((1000, p, 3))
    for a in range(1, 7):
        for b in range(1, 7):
            if a < b:
                edges.append((a, b, 1))
    for a in range(7, 13):
        for b in range(7, 13):
            if a < b:
                edges.append((a, b, 1))
    conn = "pre_root_id,post_root_id,syn_count\n" + "\n".join(
        f"{s},{t},{w}" for s, t, w in edges
    ) + "\n"
    with gzip.open(data_dir / "connections_princeton.csv.gz", "wt") as f:
        f.write(conn)

    cfg_root = tmp_path / "configs"
    (cfg_root / "schemas").mkdir(parents=True)
    (cfg_root / "datasets").mkdir(parents=True)
    (cfg_root / "error_models").mkdir(parents=True)
    (cfg_root / "analyses").mkdir(parents=True)
    (cfg_root / "experiments").mkdir(parents=True)

    import yaml

    yaml.dump({"framework": {"version": "1.0.0"}},
              open(cfg_root / "defaults.yaml", "w"))
    yaml.dump({"required_keys": ["dataset_name", "dataset_root"]},
              open(cfg_root / "schemas" / "experiment_schema.yaml", "w"))
    yaml.dump({"required_keys": ["name", "files"]},
              open(cfg_root / "schemas" / "dataset_schema.yaml", "w"))
    yaml.dump({
        "name": "TEST", "version": "1", "is_fafb": False,
        "files": {"neurons": "neurons.csv.gz",
                  "connections": "connections_princeton.csv.gz"},
        "required_neuron_columns": ["root_id"],
        "required_connection_columns": ["pre_root_id", "post_root_id"],
    }, open(cfg_root / "datasets" / "test.yaml", "w"))

    return str(data_dir.parent), str(cfg_root)


def _runner_config(dataset_root, configs_root, seed=42, **overrides):
    from core.experiment_runner import ExperimentConfig

    error_model_config = {
        "error_rate": 1.0,
        "degree_threshold": 10,
        "min_fragment_partners": 3,
    }
    if "error_rate" in overrides:
        error_model_config["error_rate"] = overrides.pop("error_rate")

    return ExperimentConfig(
        dataset_name="TEST",
        dataset_root=dataset_root,
        configs_root=configs_root,
        error_model_name="split_errors",
        error_model_config=error_model_config,
        analysis_names=["basic_structure", "degree_distribution"],
        baseline_analysis_names=["basic_structure"],
        seed=seed,
        **overrides,
    )


class TestFullPipeline:
    def test_runner_produces_successful_experiment_result(
        self, split_dataset,
    ) -> None:
        from core.split_experiment_runner import SplitExperimentRunner
        from modules.error_models import registry as error_registry
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )

        dataset_root, configs_root = split_dataset
        runner = SplitExperimentRunner(analysis_registry, error_registry)
        result = runner.run(_runner_config(dataset_root, configs_root))
        assert result.succeeded, result.errors
        assert result.error_result is not None
        assert result.error_result.model_name == "split_errors"
        assert result.error_result.succeeded
        assert result.error_result.perturbation_metadata["neurons_split"] == 1
        # Transient split plan is destroyed after the trial.
        assert "split_plan" not in (result.error_result.extra or {})

    def test_full_pipeline_preserves_edge_and_synapse_counts(
        self, split_dataset,
    ) -> None:
        from core.split_experiment_runner import SplitExperimentRunner
        from modules.error_models import registry as error_registry
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )

        dataset_root, configs_root = split_dataset
        runner = SplitExperimentRunner(analysis_registry, error_registry)
        result = runner.run(_runner_config(dataset_root, configs_root))
        base = result.baseline_analysis_results[0].metrics
        pert = result.analysis_results[0].metrics
        assert pert["edge_count"] == base["edge_count"]
        assert pert["total_synapses"] == base["total_synapses"]
        assert pert["node_count"] == base["node_count"] + 1

    def test_reproducibility_full_pipeline(self, split_dataset) -> None:
        from core.split_experiment_runner import SplitExperimentRunner
        from modules.error_models import registry as error_registry
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )

        dataset_root, configs_root = split_dataset
        runner = SplitExperimentRunner(analysis_registry, error_registry)
        r1 = runner.run(_runner_config(dataset_root, configs_root, seed=7))
        r2 = runner.run(_runner_config(dataset_root, configs_root, seed=7))
        m1 = r1.analysis_results[0].metrics
        m2 = r2.analysis_results[0].metrics
        assert m1 == m2
        assert (
            r1.error_result.perturbation_metadata
            == r2.error_result.perturbation_metadata
        )

    def test_statistics_engine_and_export_compatibility(
        self, split_dataset, tmp_path,
    ) -> None:
        """StatisticsEngine + MetadataManager + ExportManager consume the
        EM4 ExperimentResult unchanged."""
        from core.split_experiment_runner import SplitExperimentRunner
        from core.statistics_engine import StatisticsEngine
        from core.metadata_manager import MetadataManager
        from core.export_manager import ExportManager
        from modules.error_models import registry as error_registry
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )
        from pathlib import Path

        dataset_root, configs_root = split_dataset
        runner = SplitExperimentRunner(analysis_registry, error_registry)
        result = runner.run(_runner_config(dataset_root, configs_root))

        stats = StatisticsEngine().aggregate([result])
        assert "basic_structure" in stats.analysis_stats
        metadata = MetadataManager().collect(result)
        assert metadata.error_model_name == "split_errors"

        out_root = tmp_path / "results"
        package = ExportManager().export(
            result=result,
            metadata=metadata,
            stats=stats,
            output_root=out_root,
            create_zip=False,
        )
        assert (package.output_dir / "summary.csv").exists()
        assert (package.output_dir / "metadata.json").exists()

    def test_error_rate_zero_uses_baseline(self, split_dataset) -> None:
        from core.split_experiment_runner import SplitExperimentRunner
        from modules.error_models import registry as error_registry
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )

        dataset_root, configs_root = split_dataset
        runner = SplitExperimentRunner(analysis_registry, error_registry)
        result = runner.run(_runner_config(
            dataset_root, configs_root, error_rate=0.0,
        ))
        assert result.succeeded
        assert result.error_result.perturbation_metadata["neurons_split"] == 0
        pert = result.analysis_results[0].metrics
        assert pert["node_count"] == 13  # no split -> baseline graph
