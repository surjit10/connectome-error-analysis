"""
Integration test for the False Synapse Error Model pipeline.

Tests the full flow: CandidateGenerator -> cache -> FalseSynapseModel ->
ExperimentRunner, using a carefully constructed 3-neuron graph.

Graph:
  Neurons: 10, 20, 30 (all in "AL" region)
  Edges:   10 -> 30 (weight 5)
           20 -> 30 (weight 8)

  Inverted index for target 30: predecessors = {10, 20}
  Candidate pair: (10, 20) shares target 30, not an existing edge!
  Candidate pair: (20, 10) also shares target 30, not an existing edge!
"""

import igraph
import pytest

from modules.preprocessing import preprocess_graph
from modules.preprocessing.false_synapses.candidate_generator import (
    CandidateGenerator,
)
from modules.preprocessing.false_synapses.config import FALSE_SYNAPSE_CONFIG
from modules.error_models.false_synapses.model import FalseSynapseModel
from modules.error_models.common.error_result import ErrorResult

# Test config overrides to work with a 3-neuron test graph.
_TEST_CONFIG = {**FALSE_SYNAPSE_CONFIG, "min_region_size": 2}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def candidate_graph() -> igraph.Graph:
    """3-neuron graph with one non-edge candidate pair (10,20) sharing target 30."""
    g = igraph.Graph(directed=True)
    g.add_vertices(3)
    g.vs["root_id"] = [10, 20, 30]
    g.vs["top_region"] = ["AL", "AL", "AL"]
    g.vs["soma_side"] = ["left", "left", "right"]
    g.add_edges([(0, 2), (1, 2)])  # 10 -> 30, 20 -> 30
    g.es["syn_count"] = [5, 8]
    g["dataset_name"] = "TEST"
    g["id_to_idx"] = {10: 0, 20: 1, 30: 2}
    g["id_map"] = {0: 10, 1: 20, 2: 30}
    return g


@pytest.fixture
def candidate_prepared(candidate_graph: igraph.Graph):
    """Preprocess the candidate graph, indexing by top_region and soma_side."""
    return preprocess_graph(
        candidate_graph,
        index_node_attrs=["top_region", "soma_side"],
        feature_config={
            "indegree": True,
            "outdegree": True,
            "pagerank": False,
            "reciprocal_ratio": False,
            "hub_neighbor_count": False,
            "two_hop_size": False,
        },
    )


# ---------------------------------------------------------------------------
# Candidate generation tests
# ---------------------------------------------------------------------------

class TestCandidateGeneration:
    def test_generate_candidates_excludes_existing_edges(
        self, candidate_prepared, tmp_path,
    ) -> None:
        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        import polars as pl
        candidates = pl.read_parquet(str(cache_path))

        existing = {(10, 30), (20, 30)}
        candidate_pairs = set(
            zip(candidates["pre_root_id"], candidates["post_root_id"])
        )
        overlap = existing & candidate_pairs
        assert len(overlap) == 0, f"Candidates include existing edges: {overlap}"

    def test_generate_candidates_includes_shared_neighbor_pairs(
        self, candidate_prepared, tmp_path,
    ) -> None:
        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        import polars as pl
        candidates = pl.read_parquet(str(cache_path))

        candidate_pairs = set(
            zip(candidates["pre_root_id"], candidates["post_root_id"])
        )
        # (10,20) and (20,10) share target 30 and are not existing edges.
        assert (10, 20) in candidate_pairs or (20, 10) in candidate_pairs, (
            f"Expected (10,20) or (20,10) in candidates, got: {candidate_pairs}"
        )

    def test_generate_candidates_respects_region(
        self, candidate_prepared, tmp_path,
    ) -> None:
        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        import polars as pl
        candidates = pl.read_parquet(str(cache_path))
        if len(candidates) > 0:
            assert all(r == "AL" for r in candidates["region"])

    def test_generate_candidates_has_schema(
        self, candidate_prepared, tmp_path,
    ) -> None:
        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        import polars as pl
        candidates = pl.read_parquet(str(cache_path))
        expected_cols = {
            "pre_root_id", "post_root_id",
            "jaccard_out", "jaccard_in", "region",
        }
        assert expected_cols.issubset(set(candidates.columns))


# ---------------------------------------------------------------------------
# Perturbation model tests
# ---------------------------------------------------------------------------

class TestFalseSynapseModel:
    def test_model_registered(self) -> None:
        from modules.error_models.common.error_registry import (
            registry as error_registry,
        )
        assert error_registry.is_registered("false_synapses")

    def test_execute_returns_error_result(
        self, candidate_prepared, tmp_path,
    ) -> None:
        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        model = FalseSynapseModel()
        result = model.execute(
            candidate_prepared,
            config={
                "error_rate": 0.5,  # k = round(0.5 * 2) = 1
                "candidate_cache_path": str(cache_path),
            },
            seed=42,
        )

        assert isinstance(result, ErrorResult)
        assert result.succeeded
        assert isinstance(result.added_edges, list)
        # k = round(0.5 * 2) = 1 added edge expected.
        assert len(result.added_edges) == 1
        assert len(result.added_edges[0]) == 3  # (pre, post, weight)

    def test_execute_zero_rate_adds_no_edges(
        self, candidate_prepared, tmp_path,
    ) -> None:
        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        model = FalseSynapseModel()
        result = model.execute(
            candidate_prepared,
            config={
                "error_rate": 0.0,
                "candidate_cache_path": str(cache_path),
            },
        )
        assert len(result.added_edges) == 0

    def test_added_edges_have_valid_root_ids(
        self, candidate_prepared, tmp_path,
    ) -> None:
        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        model = FalseSynapseModel()
        result = model.execute(
            candidate_prepared,
            config={
                "error_rate": 1.0,
                "candidate_cache_path": str(cache_path),
            },
            seed=42,
        )

        valid_ids = {10, 20, 30}
        for pre, post, weight in result.added_edges:
            assert pre in valid_ids, f"Invalid pre_root_id: {pre}"
            assert post in valid_ids, f"Invalid post_root_id: {post}"
            assert isinstance(weight, int) and weight > 0

    def test_baseline_graph_not_modified(
        self, candidate_prepared, tmp_path,
    ) -> None:
        original_edge_count = candidate_prepared.graph.ecount()

        generator = CandidateGenerator(candidate_prepared, config=_TEST_CONFIG)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        model = FalseSynapseModel()
        model.execute(
            candidate_prepared,
            config={
                "error_rate": 0.5,
                "candidate_cache_path": str(cache_path),
            },
            seed=42,
        )

        assert candidate_prepared.graph.ecount() == original_edge_count


# ---------------------------------------------------------------------------
# Full pipeline integration
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_experiment_runner_with_false_synapses(
        self, tmp_path,
    ) -> None:
        """Run a full experiment with the false-synapse model via ExperimentRunner.

        Creates a complete dataset on disk with the right topology for
        false-synapse candidate generation (neurons 10,20 in AL sharing
        target 30), then runs the full ExperimentRunner pipeline against it.
        """
        import gzip
        import yaml

        # --- Create dataset on disk ---
        data_dir = tmp_path / "data" / "TEST_v1"
        data_dir.mkdir(parents=True)

        neurons_csv = "root_id,top_region,soma_side\n10,AL,left\n20,AL,left\n30,AL,right\n"
        with gzip.open(data_dir / "neurons.csv.gz", "wt") as f:
            f.write(neurons_csv)

        edges_csv = "pre_root_id,post_root_id,syn_count\n10,30,5\n20,30,8\n"
        with gzip.open(data_dir / "connections_princeton.csv.gz", "wt") as f:
            f.write(edges_csv)

        # --- Create configs on disk ---
        cfg_root = tmp_path / "configs"
        (cfg_root / "schemas").mkdir(parents=True)
        (cfg_root / "datasets").mkdir(parents=True)
        (cfg_root / "error_models").mkdir(parents=True)
        (cfg_root / "analyses").mkdir(parents=True)
        (cfg_root / "experiments").mkdir(parents=True)

        defaults = {
            "framework": {"version": "1.0.0"},
            "loader": {"id_columns": ["root_id", "pre_root_id", "post_root_id"]},
            "preprocessing": {"features": {"indegree": True, "outdegree": True, "pagerank": True}},
            "runner": {"auto_export": False},
            "statistics": {"confidence_level": 0.95},
        }
        with open(cfg_root / "defaults.yaml", "w") as f:
            yaml.dump(defaults, f)

        exp_schema = {"required_keys": ["dataset_name", "dataset_root"]}
        with open(cfg_root / "schemas" / "experiment_schema.yaml", "w") as f:
            yaml.dump(exp_schema, f)

        dataset_schema = {"required_keys": ["name", "files"]}
        with open(cfg_root / "schemas" / "dataset_schema.yaml", "w") as f:
            yaml.dump(dataset_schema, f)

        dataset_cfg = {
            "name": "TEST",
            "version": "1",
            "is_fafb": False,
            "files": {
                "neurons": "neurons.csv.gz",
                "connections": "connections_princeton.csv.gz",
            },
            "required_neuron_columns": ["root_id"],
            "required_connection_columns": ["pre_root_id", "post_root_id"],
        }
        with open(cfg_root / "datasets" / "test.yaml", "w") as f:
            yaml.dump(dataset_cfg, f)

        # --- Generate candidates first (outside ExperimentRunner) ---
        from core.data_loader import load_dataset
        from core.graph_builder import GraphBuilder

        dataset = load_dataset("TEST", str(data_dir.parent), configs_root=str(cfg_root))
        graph = GraphBuilder().build(dataset)
        prepared = preprocess_graph(
            graph,
            index_node_attrs=["top_region"],
            feature_config={
                "indegree": True,
                "outdegree": True,
                "pagerank": False,
                "reciprocal_ratio": False,
                "hub_neighbor_count": False,
                "two_hop_size": False,
            },
        )

        gen_config = {**FALSE_SYNAPSE_CONFIG, "min_region_size": 2}
        generator = CandidateGenerator(prepared, config=gen_config)
        cache_path = tmp_path / "candidates.parquet"
        generator.generate(cache_path)

        # --- Run ExperimentRunner ---
        from core.experiment_runner import ExperimentRunner, ExperimentConfig
        from modules.graph_analyses.analysis_registry import (
            registry as analysis_registry,
        )
        from modules.error_models.common.error_registry import (
            registry as error_registry,
        )

        runner = ExperimentRunner(
            analysis_registry=analysis_registry,
            error_registry=error_registry,
        )

        config = ExperimentConfig(
            dataset_name="TEST",
            dataset_root=str(data_dir.parent),
            configs_root=str(cfg_root),
            error_model_name="false_synapses",
            error_model_config={
                "error_rate": 0.5,
                "candidate_cache_path": str(cache_path),
            },
            analysis_names=[],
            preprocessing_config={
                "index_node_attrs": ["top_region"],
            },
            seed=42,
        )

        result = runner.run(config)
        assert result.succeeded, (
            f"Experiment failed with errors: {result.errors}"
        )
        assert result.error_result is not None
        assert len(result.error_result.added_edges) > 0
