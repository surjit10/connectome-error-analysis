"""
EM5 — Merge Vector Alignment: unit + regression tests.

Verifies ``core.merge_vector_alignment`` — the EM5-only helper that
re-expresses per-vertex analysis vectors (e.g. PageRank) produced on the
baseline and on the EM5 *temporary merged* graph into one common **merged
coordinate space** of length ``vcount - k``.

Test map (per the EM5 alignment specification):
    - build_merged_order   collapses each pair into one slot, in order.
    - collapse_baseline_vector sums the two source entries (sum rule) and is
      identity for non-merged neurons.
    - reindex_temp_vector places the merged vertex's score into the slot.
    - sum aggregation conserves total mass for the merged pair.
    - alignment integration through MergeExperimentRunner (baseline AND
      perturbed vectors both aligned, equal length).
    - No shared framework file is modified; alignment is EM5-only.
"""

import igraph
import pytest

from modules.preprocessing import preprocess_graph


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def merge_plan():
    """Two merges: (1000, 2000) and (3000, 4000)."""
    return {
        -9000000000000: {
            "merge_id": -9000000000000,
            "source_ids": [1000, 2000],
        },
        -7000000000000: {
            "merge_id": -7000000000000,
            "source_ids": [3000, 4000],
        },
    }


@pytest.fixture
def baseline_maps():
    """id_map for 6 vertices 1000, 2000, 3000, 4000, 5000, 6000."""
    roots = [1000, 2000, 3000, 4000, 5000, 6000]
    id_to_idx = {rid: i for i, rid in enumerate(roots)}
    id_map = {i: rid for i, rid in enumerate(roots)}
    return id_map, id_to_idx


# ---------------------------------------------------------------------------
# build_merged_order
# ---------------------------------------------------------------------------

class TestMergedOrder:
    def test_order_and_length(self, merge_plan, baseline_maps):
        from core.merge_vector_alignment import build_merged_order

        id_map, _ = baseline_maps
        order = build_merged_order(id_map, 6, merge_plan)
        # 6 vertices - 2 merges = 4 slots; second members dropped.
        assert len(order) == 4
        assert order == [1000, 3000, 5000, 6000]

    def test_empty_plan_identity(self, baseline_maps):
        from core.merge_vector_alignment import build_merged_order

        id_map, _ = baseline_maps
        order = build_merged_order(id_map, 6, {})
        assert order == [1000, 2000, 3000, 4000, 5000, 6000]


# ---------------------------------------------------------------------------
# collapse_baseline_vector
# ---------------------------------------------------------------------------

class TestCollapseBaseline:
    def test_merged_pair_slots_are_summed(self, merge_plan, baseline_maps):
        from core.merge_vector_alignment import (
            build_merged_order,
            collapse_baseline_vector,
        )

        id_map, id_to_idx = baseline_maps
        order = build_merged_order(id_map, 6, merge_plan)
        # Positional vector: index i has value i + 1 (baseline vertex order).
        vector = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        collapsed = collapse_baseline_vector(vector, id_to_idx, merge_plan, order)
        assert collapsed == [
            1.0 + 2.0,   # slot 1000: 1000 + 2000
            3.0 + 4.0,   # slot 3000: 3000 + 4000
            5.0,         # 5000 unchanged
            6.0,         # 6000 unchanged
        ]
        # Mass conservation for the merged pair: 3.0 == 1.0 + 2.0, etc.
        assert collapsed[0] == 3.0 and collapsed[1] == 7.0

    def test_identity_for_single_slots(self, baseline_maps):
        from core.merge_vector_alignment import (
            build_merged_order,
            collapse_baseline_vector,
        )

        id_map, id_to_idx = baseline_maps
        order = build_merged_order(id_map, 6, {})
        vector = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        collapsed = collapse_baseline_vector(vector, id_to_idx, {}, order)
        assert collapsed == vector


# ---------------------------------------------------------------------------
# reindex_temp_vector
# ---------------------------------------------------------------------------

class TestReindexTemp:
    def test_merged_slot_reads_merged_vertex_score(self, merge_plan):
        from core.merge_vector_alignment import (
            build_merged_order,
            reindex_temp_vector,
        )

        roots = [1000, 2000, 3000, 4000, 5000, 6000]
        id_map = {i: rid for i, rid in enumerate(roots)}
        order = build_merged_order(id_map, 6, merge_plan)
        m1 = merge_plan[-9000000000000]["merge_id"]
        m2 = merge_plan[-7000000000000]["merge_id"]
        # Temp graph has 4 vertices: m1, m2, 5000, 6000 (in this order).
        temp_root_to_index = {m1: 0, m2: 1, 5000: 2, 6000: 3}
        vector = [0.9, 0.7, 0.5, 0.3]  # m1, m2, 5000, 6000
        reindexed = reindex_temp_vector(vector, temp_root_to_index, merge_plan, order)
        assert reindexed == [0.9, 0.7, 0.5, 0.3]

    def test_absent_root_defensive_zero(self, merge_plan):
        from core.merge_vector_alignment import (
            build_merged_order,
            reindex_temp_vector,
        )

        roots = [1000, 2000, 3000, 4000, 5000, 6000]
        id_map = {i: rid for i, rid in enumerate(roots)}
        order = build_merged_order(id_map, 6, merge_plan)
        # Neither merged vertex is present in the temp graph -> defensive 0.0
        # for both merged slots; single roots read their own scores.
        temp_root_to_index = {1000: 0, 3000: 1, 5000: 2, 6000: 3}
        vector = [1.0, 2.0, 3.0, 4.0]
        reindexed = reindex_temp_vector(vector, temp_root_to_index, merge_plan, order)
        assert reindexed == [0.0, 0.0, 3.0, 4.0]


# ---------------------------------------------------------------------------
# End-to-end alignment through the real pipeline (temp graph + runner)
# ---------------------------------------------------------------------------

class TestPipelineAlignment:
    def _build_graph(self):
        """Baseline: 1000 & 2000 share X1..X3 (a merge pair), plus singles
        5000 and 6000.  Vertex order: 1000, 2000, X1..X3, 5000, 6000."""
        roots = [1000, 2000] + list(range(1, 4)) + [5000, 6000]
        g = igraph.Graph(directed=True)
        g.add_vertices(len(roots))
        g.vs["root_id"] = roots
        edges = [(0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (1, 4)]
        g.add_edges(edges)
        g.es["syn_count"] = [1] * g.ecount()
        g.vs["super_class"] = ["neuron"] * len(roots)
        g.vs["top_region"] = ["AL"] * len(roots)
        g.vs["soma_side"] = ["left"] * len(roots)
        g["dataset_name"] = "TEST"
        g["id_to_idx"] = {rid: i for i, rid in enumerate(roots)}
        g["id_map"] = {i: rid for rid, i in g["id_to_idx"].items()}
        return g

    def test_runner_alignment_integration(self):
        from core.experiment_runner import ExperimentConfig, ExperimentResult
        from core.merge_experiment_runner import MergeExperimentRunner
        from modules.graph_analyses.analysis_registry import (
            registry as a_reg,
        )
        from modules.error_models import registry as e_reg

        prepared = preprocess_graph(
            self._build_graph(), index_node_attrs=["top_region", "soma_side"]
        )
        model = e_reg.instantiate("merge_errors")
        error_result = model.execute(
            prepared,
            config={
                "error_rate": 1.0, "degree_threshold": 2,
                "min_shared_partners": 3, "jaccard_min": 0.001,
            },
            seed=42,
        )
        assert len(error_result.extra["merge_plan"]) == 1

        runner = MergeExperimentRunner(a_reg, e_reg)
        config = ExperimentConfig(dataset_name="TEST", dataset_root="x")
        result = ExperimentResult(experiment_id="t", dataset_name="TEST")
        temp_graph, temp_prepared = runner._merge_build_temp_graph(
            prepared, error_result, config, result
        )
        assert temp_graph is not None

        # Run the pagerank analysis on both graphs, then align.
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )

        pagerank_analysis = analysis_registry.instantiate("pagerank")
        base_res = pagerank_analysis.execute(prepared, config={})
        pert_res = pagerank_analysis.execute(temp_prepared, config={})
        result.baseline_analysis_results.append(base_res)
        result.analysis_results.append(pert_res)

        runner._align_pagerank_vectors(result, prepared, error_result.extra["merge_plan"], temp_graph)

        base_vec = result.baseline_analysis_results[0].metrics["pagerank_scores"]
        pert_vec = result.analysis_results[0].metrics["pagerank_scores"]
        # 7 baseline vertices - 1 merge = 6 aligned slots.
        assert len(base_vec) == len(pert_vec) == 6
        # The merged pair's collapsed baseline mass equals the merged vertex's
        # score only approximately (renormalisation), but the vectors must be
        # equal length and finite.
        assert all(v >= 0 for v in pert_vec)


# ---------------------------------------------------------------------------
# Isolation test — the shared framework must never reference EM5 helpers
# ---------------------------------------------------------------------------

class TestIsolation:
    def test_no_shared_module_references_em5_helpers(self) -> None:
        """The EM5 alignment/runner code must never be reachable from
        EM1–EM4 paths (mirrors the EM4 isolation guarantee)."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent
        forbidden = ("merge_vector_alignment", "merge_experiment_runner")
        exempt_prefixes = (
            "core/merge_experiment_runner.py",
            "core/merge_vector_alignment.py",
            "tests/test_merge_errors.py",
            "tests/test_em5_vector_alignment.py",
            "modules/error_models/merge_errors",
            "notebooks",
            "docs",
        )

        shared_files = [
            root / "core" / "experiment_runner.py",
            root / "core" / "split_experiment_runner.py",
            root / "core" / "split_vector_alignment.py",
            root / "modules" / "statistical_evaluation",
            root / "modules" / "error_models" / "common",
            root / "modules" / "error_models" / "missed_synapses",
            root / "modules" / "error_models" / "false_synapses",
            root / "modules" / "error_models" / "synapse_count",
            root / "modules" / "error_models" / "split_errors",
        ]

        offenders = []
        for path in shared_files:
            if path.is_dir():
                files = list(path.rglob("*.py"))
            else:
                files = [path]
            for f in files:
                rel = f.relative_to(root).as_posix()
                if rel.startswith(exempt_prefixes):
                    continue
                text = f.read_text(encoding="utf-8")
                for token in forbidden:
                    if token in text:
                        offenders.append((rel, token))

        assert offenders == [], (
            "EM5-only code must not be referenced by shared/frozen modules: "
            f"{offenders}"
        )
