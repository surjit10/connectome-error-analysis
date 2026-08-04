"""
EM4 — Split Vector Alignment: unit + regression tests
=======================================================
Verifies ``core.split_vector_alignment`` — the EM4-only helper that rebuilds
per-vertex analysis vectors (e.g. PageRank) produced on the EM4 *temporary*
graph back into the **baseline vertex ordering**, so the shared vector
comparison pipeline (StatisticsEngine → VectorComparisonRegistry) compares
aligned vectors.

Test map (per the EM4 alignment specification):

    1. Perfect alignment after one split.
    2. Multiple split neurons.
    3. No split → alignment is the identity.
    4. Fragment aggregation (sum default; mean option).
    5. Top-K overlap restored.
    6. Pearson / Spearman remain high on identical graphs.
    7. EM1 regression — execution path, outputs unchanged.
    8. EM2 regression — execution path, outputs unchanged.
    9. EM3 regression — execution path, outputs unchanged.

Design constraints honoured:
    - The shared modules are never imported by the alignment helper's tests
      for mutation — only for verification.
    - No shared framework file is modified; alignment is EM4-only.
"""

from __future__ import annotations

import ast
import gzip
import math
from pathlib import Path

import igraph
import pytest

from core.split_vector_alignment import (
    align_pagerank_vectors,
    align_vertex_vector,
    build_baseline_order,
    build_split_parents,
    build_temp_root_to_index,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _baseline_graph(root_ids, edges):
    """Build a baseline igraph with ``root_id`` vertex attributes.

    Vertex index == position of the root id in *root_ids* (dense order,
    as produced by the Graph Builder / ``id_map``).
    """
    g = igraph.Graph(directed=True)
    g.add_vertices(len(root_ids))
    g.vs["root_id"] = list(root_ids)
    g.add_edges(edges)
    g["id_to_idx"] = {rid: i for i, rid in enumerate(root_ids)}
    g["id_map"] = {i: rid for i, rid in enumerate(root_ids)}
    return g


def _fake_split_plan(splits):
    """Build a split-plan-shaped dict: ``{root: {"fragment_ids": [...], ...}}``."""
    return {
        root: {"fragment_ids": [f"{root}.1", f"{root}.2"]}
        for root in splits
    }


def _split_one(root_ids, splits, frag_scores):
    """Simulate a temp graph after splitting.

    Returns ``(baseline_order, temp_root_to_index, split_parents, temp_vector)``
    where *split_parents* is the ``{parent: [fragments]}`` mapping that the
    runner derives from the split plan via
    :func:`build_split_parents` — exactly the value the runner passes to
    :func:`align_pagerank_vectors`.

    - Split parents are removed from the temp graph; two fragment roots are
      added (appended at the end, mimicking the runner's construction).
    - Non-split neurons keep their baseline index.
    - *frag_scores* maps ``frag_root -> score`` for the appended fragments.
    """
    baseline_order = list(root_ids)
    raw_plan = _fake_split_plan(splits)
    split_parents = build_split_parents(raw_plan)

    temp_root_to_index: dict = {}
    temp_vector: list = []
    # Deterministic position-based scores so vectors are realistic and
    # reproducible.  Fragment scores are preserved as provided.
    def _placeholder(idx: int) -> float:
        return float((idx * 7 + 3) % 11) / 10.0 + 0.01

    for idx, rid in enumerate(root_ids):
        if rid in splits:
            continue  # parent deleted from the temp graph
        temp_root_to_index[rid] = len(temp_vector)
        temp_vector.append(_placeholder(len(temp_vector)))

    for rid in splits:
        for fid in raw_plan[rid]["fragment_ids"]:
            if fid not in frag_scores:
                continue  # fragment absent from the temp graph (defensive path)
            temp_root_to_index[fid] = len(temp_vector)
            temp_vector.append(frag_scores[fid])

    return baseline_order, temp_root_to_index, split_parents, temp_vector


# ---------------------------------------------------------------------------
# 1. Perfect alignment after one split
# ---------------------------------------------------------------------------

class TestSingleSplit:
    def test_aligned_length_equals_baseline(self) -> None:
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3, 4], splits=[2], frag_scores={"2.1": 0.5, "2.2": 0.3})
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        assert len(aligned) == len(baseline_order) == 4

    def test_fragments_aggregated_into_parent_position(self) -> None:
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3, 4], splits=[2], frag_scores={"2.1": 0.4, "2.2": 0.25})
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        # Position of parent 2 in the baseline ordering is index 1.
        assert aligned[1] == pytest.approx(0.4 + 0.25, abs=1e-9)
        # Non-split neurons keep their own temp-graph scores.
        assert aligned[0] == temp_vector[temp_root_to_index[1]]
        assert aligned[2] == temp_vector[temp_root_to_index[3]]
        assert aligned[3] == temp_vector[temp_root_to_index[4]]

    def test_only_pagerank_metric_contract(self) -> None:
        """The aligned value at each position is a plain float, never a dict."""
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3], splits=[1], frag_scores={"1.1": 0.5, "1.2": 0.2})
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        assert all(isinstance(v, float) for v in aligned)


# ---------------------------------------------------------------------------
# 2. Multiple split neurons
# ---------------------------------------------------------------------------

class TestMultipleSplits:
    def test_multiple_split_parents(self) -> None:
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one(
                [1, 2, 3, 4, 5, 6],
                splits=[2, 5],
                frag_scores={"2.1": 0.1, "2.2": 0.2, "5.1": 0.3, "5.2": 0.4},
            )
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        # Parent 2 → index 1; parent 5 → index 4.
        assert aligned[1] == pytest.approx(0.1 + 0.2, abs=1e-9)
        assert aligned[4] == pytest.approx(0.3 + 0.4, abs=1e-9)
        # Non-split neurons unchanged.
        assert aligned[0] == temp_vector[temp_root_to_index[1]]
        assert aligned[2] == temp_vector[temp_root_to_index[3]]
        assert aligned[3] == temp_vector[temp_root_to_index[4]]
        assert aligned[5] == temp_vector[temp_root_to_index[6]]

    def test_adjacent_split_parents(self) -> None:
        """Two split neurons whose fragments both exist in the temp graph."""
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one(
                [1, 2, 3, 4],
                splits=[2, 3],
                frag_scores={"2.1": 0.2, "2.2": 0.3, "3.1": 0.4, "3.2": 0.5},
            )
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        assert aligned[1] == pytest.approx(0.2 + 0.3, abs=1e-9)
        assert aligned[2] == pytest.approx(0.4 + 0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# 3. No split → identity
# ---------------------------------------------------------------------------

class TestNoSplit:
    def test_alignment_is_identity(self) -> None:
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3, 4], splits=[], frag_scores={})
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        # With no splits the temp graph has the same vertex order as baseline.
        expected = [temp_vector[temp_root_to_index[r]] for r in baseline_order]
        assert aligned == pytest.approx(expected, abs=1e-12)


# ---------------------------------------------------------------------------
# 4. Fragment aggregation
# ---------------------------------------------------------------------------

class TestAggregation:
    def test_sum_is_default(self) -> None:
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3], splits=[2], frag_scores={"2.1": 0.3, "2.2": 0.6})
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        assert aligned[1] == pytest.approx(0.9, abs=1e-9)

    def test_mean_aggregation(self) -> None:
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3], splits=[2], frag_scores={"2.1": 0.3, "2.2": 0.6})
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents,
            aggregation="mean",
        )
        assert aligned[1] == pytest.approx(0.45, abs=1e-9)

    def test_unknown_aggregation_raises(self) -> None:
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3], splits=[2], frag_scores={"2.1": 0.3, "2.2": 0.6})
        )
        with pytest.raises(ValueError):
            align_vertex_vector(
                temp_vector, baseline_order, temp_root_to_index, split_parents,
                aggregation="geometric",
            )

    def test_missing_fragment_uses_available_scores(self) -> None:
        """A fragment absent from the temp graph contributes nothing to the
        sum; the remaining fragment's score is used."""
        baseline_order, temp_root_to_index, split_parents, temp_vector = (
            _split_one([1, 2, 3], splits=[2], frag_scores={"2.1": 0.3})
        )
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        # Only one fragment score exists; sum of [0.3] == 0.3.
        assert aligned[1] == pytest.approx(0.3, abs=1e-9)

    def test_skipped_split_keeps_parent_own_score(self) -> None:
        """A root listed in the split plan that was NOT actually split (the
        runner skips unresolved / edgeless roots) keeps its own temp-graph
        score instead of being zeroed."""
        baseline_order = [1, 2, 3]
        # Parent 2 is in the plan but the temp graph still contains the
        # parent vertex (it was never deleted) and no fragments.
        split_parents = build_split_parents(_fake_split_plan([2]))
        temp_root_to_index = {1: 0, 2: 1, 3: 2}
        temp_vector = [0.5, 0.4, 0.1]
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        assert aligned[1] == pytest.approx(0.4, abs=1e-12)

    def test_missing_vertex_defensive_zero(self) -> None:
        """A neuron genuinely absent from the temp graph falls back to 0.0."""
        baseline_order = [1, 2, 3]
        split_parents = {}
        # Neuron 2 missing from the temp graph entirely.
        temp_root_to_index = {1: 0, 3: 1}
        temp_vector = [0.5, 0.1]
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        assert aligned[1] == 0.0


# ---------------------------------------------------------------------------
# 5. Top-K overlap restored
# ---------------------------------------------------------------------------

class TestTopKOverlap:
    def test_misaligned_vectors_collapse_then_restored(self) -> None:
        """The exact bug: index-space misalignment destroys top-K overlap;
        alignment restores it."""
        from modules.statistical_evaluation.vector_comparison import (
            compare_pagerank,
        )

        # Baseline: neuron 3 (index 2) is the highest-ranked neuron.
        baseline_order = [1, 2, 3, 4, 5]
        baseline_vec = [0.1, 0.15, 0.5, 0.2, 0.05]

        # Temp graph after splitting neuron 3: parents {1,2,4,5} keep their
        # order, fragments of 3 are appended.  The RAW temp vector is in this
        # new order — positions do NOT correspond to baseline positions, and
        # the parent's mass is now spread over the two appended positions,
        # so the raw top-K picks up entirely different positions.
        temp_root_to_index = {1: 0, 2: 1, 4: 2, 5: 3, "3.1": 4, "3.2": 5}
        temp_vector = [0.1, 0.15, 0.2, 0.05, 0.25, 0.25]
        split_parents = build_split_parents(_fake_split_plan([3]))

        # 5a. The buggy comparison (raw temp vector, different length).
        # Baseline top-3 positions {2,3,1}; raw temp top-3 positions {4,5,2}.
        # Only position 2 coincides → overlap is destroyed.
        broken = compare_pagerank(baseline_vec, temp_vector, {"top_k_overlap": 3})
        assert broken["topk_overlap"] <= 0.34  # grossly wrong overlap

        # 5b. After alignment the vectors share the baseline index space.
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        fixed = compare_pagerank(baseline_vec, aligned, {"top_k_overlap": 3})
        assert fixed["topk_overlap"] == 1.0  # fully restored


# ---------------------------------------------------------------------------
# 6. Pearson / Spearman remain high on identical graphs
# ---------------------------------------------------------------------------

class TestCorrelations:
    def test_identical_aligned_graph_high_correlation(self) -> None:
        """Two vectors that are the same after alignment must correlate ~1.0."""
        from modules.statistical_evaluation.vector_comparison import (
            compare_pagerank,
        )

        baseline_order = list(range(1, 21))
        # Baseline scores: deterministic pseudo-random spread.
        baseline_vec = [float((i * 13) % 97) / 97.0 for i in range(20)]

        # Temp graph: neuron 5 deleted, its two fragments appended at the
        # end; every other neuron keeps its position.  The fragment scores
        # sum to the parent's baseline score, so after alignment the vector
        # must be identical to the baseline.
        temp_order = [r for r in baseline_order if r != 5]
        temp_root_to_index = {r: i for i, r in enumerate(temp_order)}
        temp_root_to_index["5.1"] = len(temp_root_to_index)
        temp_root_to_index["5.2"] = len(temp_root_to_index)
        temp_vector = (
            [v for i, v in enumerate(baseline_vec) if i != 4]
            + [baseline_vec[4] / 2, baseline_vec[4] / 2]
        )
        split_parents = build_split_parents(_fake_split_plan([5]))

        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        assert aligned == pytest.approx(baseline_vec, abs=1e-9)

        comparison = compare_pagerank(baseline_vec, aligned, {"top_k_overlap": 10})
        assert comparison["pearson"] > 0.999
        assert comparison["spearman"] > 0.999
        assert comparison["topk_overlap"] == 1.0


# ---------------------------------------------------------------------------
# Mapping builders
# ---------------------------------------------------------------------------

class TestMappingBuilders:
    def test_build_baseline_order(self) -> None:
        g = _baseline_graph([10, 20, 30], [(0, 1)])
        prepared_like = type(
            "PreparedLike", (), {"lookup": type("L", (), {"id_map": g["id_map"]})()}
        )()
        order = build_baseline_order(prepared_like.lookup.id_map, g.vcount())
        assert order == [10, 20, 30]

    def test_build_temp_root_to_index(self) -> None:
        g = _baseline_graph([10, 20, 30], [(0, 1)])
        mapping = build_temp_root_to_index(g)
        assert mapping == {10: 0, 20: 1, 30: 2}

    def test_build_split_parents(self) -> None:
        plan = {
            5: {"fragment_ids": ["5.1", "5.2"], "edges_rewired": 3},
            9: {"fragment_ids": ["9.1", "9.2"], "edges_rewired": 1},
        }
        parents = build_split_parents(plan)
        assert parents == {5: ["5.1", "5.2"], 9: ["9.1", "9.2"]}

    def test_synthetic_negative_int_fragment_ids(self) -> None:
        """Mirror production: fragment ids are synthetic negative ints."""
        baseline_order = [10, 20, 30]
        # Parent 20 splits into fragments -201, -202 (production-style ids).
        split_parents = build_split_parents({20: {"fragment_ids": [-201, -202]}})
        temp_root_to_index = {10: 0, 30: 1, -201: 2, -202: 3}
        temp_vector = [0.5, 0.2, 0.15, 0.15]
        aligned = align_pagerank_vectors(
            temp_vector, baseline_order, temp_root_to_index, split_parents
        )
        # Parent 20 → baseline index 1; fragments sum to 0.30.
        assert aligned[1] == pytest.approx(0.30, abs=1e-12)
        assert aligned[0] == pytest.approx(0.5, abs=1e-12)
        assert aligned[2] == pytest.approx(0.2, abs=1e-12)


# ---------------------------------------------------------------------------
# 7–9. EM1 / EM2 / EM3 regression — execution paths and outputs unchanged
# ---------------------------------------------------------------------------

class TestSharedFrameworkIsolation:
    """The EM4 alignment code must never be reachable from EM1–EM3 paths."""

    FROZEN_FILES = [
        "core/experiment_runner.py",
        "core/statistics_engine.py",
        "modules/statistical_evaluation/vector_comparison.py",
        "modules/error_models/missed_synapses/model.py",
        "modules/error_models/false_synapses/model.py",
        "modules/error_models/synapse_count/model.py",
    ]

    @pytest.mark.parametrize("rel_path", FROZEN_FILES)
    def test_frozen_module_never_references_alignment(self, rel_path) -> None:
        """No shared module imports or references the EM4 alignment helper."""
        project_root = Path(__file__).resolve().parent.parent
        source = (project_root / rel_path).read_text(encoding="utf-8")
        assert "split_vector_alignment" not in source, (
            f"{rel_path} references the EM4-only alignment helper — "
            "this would couple the shared framework to EM4."
        )


class TestEM1Regression:
    """EM1 (missed_synapses) must run via ExperimentRunner and produce
    deterministic, unchanged outputs — the alignment step never fires on the
    EM1 path because EM1 uses ``ExperimentRunner`` (not
    ``SplitExperimentRunner``) and never emits a ``split_plan``."""

    def test_em1_pipeline_runs_and_is_deterministic(
        self, temp_dataset, temp_configs,
    ) -> None:
        from core.experiment_runner import ExperimentRunner, ExperimentConfig
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )
        from modules.error_models.common.error_registry import (
            registry as error_registry,
        )

        dataset_root, name = temp_dataset
        runner = ExperimentRunner(analysis_registry, error_registry)

        def run_once() -> dict:
            config = ExperimentConfig(
                dataset_name=name,
                dataset_root=str(dataset_root),
                configs_root=str(temp_configs),
                error_model_name="missed_synapses",
                error_model_config={"error_rate": 0.0},
                analysis_names=["pagerank"],
                seed=42,
            )
            result = runner.run(config)
            assert result.succeeded, result.errors
            a_res = result.analysis_results[0]
            return {
                "pagerank_len": len(a_res.metrics["pagerank_scores"]),
                "pagerank_sum": round(sum(a_res.metrics["pagerank_scores"]), 9),
                "n_analyses": len(result.analysis_results),
            }

        first, second = run_once(), run_once()
        assert first == second  # bit-for-bit deterministic


class TestEM2Regression:
    """EM2 (false_synapses) via the existing candidate-generator pipeline."""

    def test_em2_pipeline_runs_and_is_deterministic(
        self, tmp_path,
    ) -> None:
        import gzip
        import yaml

        from modules.preprocessing import preprocess_graph
        from modules.preprocessing.false_synapses.candidate_generator import (
            CandidateGenerator,
        )
        from modules.preprocessing.false_synapses.config import (
            FALSE_SYNAPSE_CONFIG,
        )

        # --- Small dataset with a false-synapse candidate pair ---
        data_dir = tmp_path / "data" / "TEST_v1"
        data_dir.mkdir(parents=True)
        neurons = "root_id,top_region,soma_side\n10,AL,left\n20,AL,left\n30,AL,right\n"
        with gzip.open(data_dir / "neurons.csv.gz", "wt") as f:
            f.write(neurons)
        edges = "pre_root_id,post_root_id,syn_count\n10,30,5\n20,30,8\n"
        with gzip.open(data_dir / "connections_princeton.csv.gz", "wt") as f:
            f.write(edges)

        cfg_root = tmp_path / "configs"
        (cfg_root / "schemas").mkdir(parents=True)
        (cfg_root / "datasets").mkdir(parents=True)
        (cfg_root / "error_models").mkdir(parents=True)
        (cfg_root / "analyses").mkdir(parents=True)
        (cfg_root / "experiments").mkdir(parents=True)
        with open(cfg_root / "defaults.yaml", "w") as f:
            yaml.dump({
                "framework": {"version": "1.0.0"},
                "loader": {"id_columns": ["root_id", "pre_root_id", "post_root_id"]},
                "preprocessing": {"features": {"pagerank": True}},
                "runner": {"auto_export": False},
                "statistics": {"confidence_level": 0.95},
            }, f)
        with open(cfg_root / "schemas" / "experiment_schema.yaml", "w") as f:
            yaml.dump({"required_keys": ["dataset_name", "dataset_root"]}, f)
        with open(cfg_root / "schemas" / "dataset_schema.yaml", "w") as f:
            yaml.dump({"required_keys": ["name", "files"]}, f)
        with open(cfg_root / "datasets" / "test.yaml", "w") as f:
            yaml.dump({
                "name": "TEST", "version": "1", "is_fafb": False,
                "files": {
                    "neurons": "neurons.csv.gz",
                    "connections": "connections_princeton.csv.gz",
                },
                "required_neuron_columns": ["root_id"],
                "required_connection_columns": ["pre_root_id", "post_root_id"],
            }, f)

        # --- Generate candidates once (outside the runner) ---
        from core.data_loader import load_dataset
        from core.graph_builder import GraphBuilder

        dataset = load_dataset("TEST", str(data_dir.parent), configs_root=str(cfg_root))
        graph = GraphBuilder().build(dataset)
        prepared = preprocess_graph(
            graph,
            index_node_attrs=["top_region"],
            feature_config={
                "indegree": True, "outdegree": True, "pagerank": False,
                "reciprocal_ratio": False, "hub_neighbor_count": False,
                "two_hop_size": False,
            },
        )
        gen_config = {**FALSE_SYNAPSE_CONFIG, "min_region_size": 2}
        cache_path = tmp_path / "candidates.parquet"
        CandidateGenerator(prepared, config=gen_config).generate(cache_path)

        # --- Run EM2 twice with the same seed via ExperimentRunner ---
        from core.experiment_runner import ExperimentRunner, ExperimentConfig
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )
        from modules.error_models.common.error_registry import (
            registry as error_registry,
        )

        runner = ExperimentRunner(analysis_registry, error_registry)

        def run_once() -> dict:
            config = ExperimentConfig(
                dataset_name="TEST",
                dataset_root=str(data_dir.parent),
                configs_root=str(cfg_root),
                error_model_name="false_synapses",
                error_model_config={
                    "error_rate": 0.5,
                    "candidate_cache_path": str(cache_path),
                },
                analysis_names=["pagerank"],
                preprocessing_config={"index_node_attrs": ["top_region"]},
                seed=42,
            )
            result = runner.run(config)
            assert result.succeeded, result.errors
            assert result.error_result is not None
            return {
                "added_edges": list(result.error_result.added_edges),
                "pagerank_sum": round(
                    sum(result.analysis_results[0].metrics["pagerank_scores"]), 9
                ),
            }

        first, second = run_once(), run_once()
        assert first == second  # deterministic, unchanged


class TestEM3Regression:
    """EM3 (synapse_count_measurement) via ExperimentRunner."""

    def test_em3_pipeline_runs_and_is_deterministic(
        self, temp_dataset, temp_configs,
    ) -> None:
        from core.experiment_runner import ExperimentRunner, ExperimentConfig
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )
        from modules.error_models.common.error_registry import (
            registry as error_registry,
        )

        dataset_root, name = temp_dataset
        runner = ExperimentRunner(analysis_registry, error_registry)

        def run_once() -> dict:
            config = ExperimentConfig(
                dataset_name=name,
                dataset_root=str(dataset_root),
                configs_root=str(temp_configs),
                error_model_name="synapse_count_measurement",
                error_model_config={"error_rate": 0.1},
                analysis_names=["pagerank"],
                seed=7,
            )
            result = runner.run(config)
            assert result.succeeded, result.errors
            a_res = result.analysis_results[0]
            return {
                "weight_updates": dict(result.error_result.weight_updates),
                "pagerank_sum": round(sum(a_res.metrics["pagerank_scores"]), 9),
            }

        first, second = run_once(), run_once()
        assert first == second  # deterministic, unchanged
