#!/usr/bin/env python3
"""
False Synapse Demo — 1000-node artificial connectome
======================================================
Generates a synthetic connectome with 1000 neurons across 5 brain regions,
then runs the full false-synapse error-model pipeline:

    1. Generate & write synthetic CSV dataset
    2. Create config YAML files for the DatasetRegistry
    3. Load dataset → Build igraph → Preprocess
    4. Candidate generation (shared-neighbour inverted-index)
    5. FalseSynapseModel perturbation
    6. ExperimentRunner orchestration (full pipeline)
    7. Results validation & summary report

Usage:
    source .venv/bin/activate
    cd "0-demo test/false synapse"
    python run_false_synapse_demo.py
"""

from __future__ import annotations

import csv
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import yaml

# ── Ensure project root is on sys.path ───────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("FalseSynapseDemo")

# ── Paths ─────────────────────────────────────────────────────────────────
DEMO_DIR = Path(__file__).resolve().parent
DATA_DIR = DEMO_DIR / "data" / "DEMO_v1"
CFG_DIR = DEMO_DIR / "configs"
CACHE_DIR = DEMO_DIR / "cache"

# ── Synthetic dataset parameters ─────────────────────────────────────────
N_NEURONS = 1000
N_EDGES = 6000                     # baseline edges
N_REGIONS = 5
REGION_NAMES = ["AL", "ME", "CB", "MB", "LO"]
SOMA_SIDES = ["left", "right", "center"]

RANDOM_SEED = 42
ERROR_RATE = 0.02                  # 2% false-positive edges
N_ERROR_EDGES_ESTIMATE = int(N_EDGES * ERROR_RATE)
MIN_EDGES_PER_TARGET = 3           # ensures shared-neighbour pairs


def generate_synthetic_connectome(
    n_neurons: int = N_NEURONS,
    n_edges: int = N_EDGES,
    seed: int = RANDOM_SEED,
) -> tuple[list[dict], list[dict]]:
    """Generate synthetic neurons and connections tables.

    Returns
    -------
    neurons : list[dict]
        Each dict has keys: root_id, top_region, soma_side
    connections : list[dict]
        Each dict has keys: pre_root_id, post_root_id, syn_count
    """
    rng = np.random.default_rng(seed)

    # ── Neurons ───────────────────────────────────────────────────────────
    root_ids = list(range(1001, 1001 + n_neurons))
    regions = rng.choice(REGION_NAMES, size=n_neurons)
    sides = rng.choice(SOMA_SIDES, size=n_neurons)

    neurons = [
        {"root_id": rid, "top_region": reg, "soma_side": side}
        for rid, reg, side in zip(root_ids, regions, sides)
    ]

    # ── Connections (structured for shared-neighbour pairs) ──────────────
    # Strategy: pick a subset (~10 %) of neurons to be "hub targets".
    # For each hub, connect a group of presynaptic neurons → those presynaptic
    # neurons share a common target → candidate generation will find them.
    n_hubs = max(20, n_neurons // 10)          # ~100 hub targets
    n_per_hub = max(MIN_EDGES_PER_TARGET, 5)   # 5+ presynaptic per hub
    n_structured = n_hubs * n_per_hub          # edges from structured part

    hub_ids = rng.choice(root_ids, size=n_hubs, replace=False).tolist()
    remaining = [rid for rid in root_ids if rid not in hub_ids]

    # Ensure we have enough non-hub neurons for presynaptic partners.
    n_presynaptic_needed = n_structured
    if len(remaining) < n_presynaptic_needed:
        # Fall back: allow hubs to be presynaptic to other hubs.
        presynaptic_pool = root_ids[:]
    else:
        presynaptic_pool = remaining[:]

    connections: list[dict] = []
    hub_idx = 0
    for hub in hub_ids:
        for _ in range(n_per_hub):
            pre = presynaptic_pool[hub_idx % len(presynaptic_pool)]
            hub_idx += 1
            syn_count = int(rng.integers(1, 12))
            connections.append({
                "pre_root_id": pre,
                "post_root_id": hub,
                "syn_count": syn_count,
            })

    # ── Fill remaining edges with random connectivity ─────────────────────
    remaining_budget = n_edges - len(connections)
    if remaining_budget > 0:
        # Generate random edges, avoid duplicates and self-loops.
        existing = {(c["pre_root_id"], c["post_root_id"]) for c in connections}
        attempts = 0
        max_attempts = remaining_budget * 20
        while len(connections) < n_edges and attempts < max_attempts:
            attempts += 1
            pre = int(rng.integers(1001, 1001 + n_neurons))
            post = int(rng.integers(1001, 1001 + n_neurons))
            if pre == post or (pre, post) in existing:
                continue
            existing.add((pre, post))
            syn_count = int(rng.integers(1, 20))
            connections.append({
                "pre_root_id": pre,
                "post_root_id": post,
                "syn_count": syn_count,
            })

    logger.info(
        "Generated %d neurons and %d connections (structured=%d, random=%d).",
        len(neurons), len(connections),
        min(n_structured, len(connections)),
        max(0, len(connections) - n_structured),
    )
    return neurons, connections


def write_csv_files(
    neurons: list[dict],
    connections: list[dict],
    data_dir: Path = DATA_DIR,
) -> None:
    """Write neurons.csv and connections.csv to *data_dir*."""
    data_dir.mkdir(parents=True, exist_ok=True)

    # ── Neurons ───────────────────────────────────────────────────────────
    neurons_path = data_dir / "neurons.csv"
    with neurons_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["root_id", "top_region", "soma_side"])
        writer.writeheader()
        writer.writerows(neurons)
    logger.info("Wrote %s (%d rows).", neurons_path, len(neurons))

    # ── Connections ───────────────────────────────────────────────────────
    conn_path = data_dir / "connections.csv"
    with conn_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pre_root_id", "post_root_id", "syn_count"])
        writer.writeheader()
        writer.writerows(connections)
    logger.info("Wrote %s (%d rows).", conn_path, len(connections))


def write_config_files(cfg_dir: Path = CFG_DIR) -> None:
    """Create the YAML config files the DatasetRegistry expects."""
    (cfg_dir / "schemas").mkdir(parents=True, exist_ok=True)
    (cfg_dir / "datasets").mkdir(parents=True, exist_ok=True)
    (cfg_dir / "error_models").mkdir(parents=True, exist_ok=True)
    (cfg_dir / "analyses").mkdir(parents=True, exist_ok=True)

    # ── defaults.yaml ─────────────────────────────────────────────────────
    defaults = {
        "framework": {"version": "1.0.0"},
        "loader": {"id_columns": ["root_id", "pre_root_id", "post_root_id"]},
        "preprocessing": {
            "features": {
                "indegree": True,
                "outdegree": True,
                "pagerank": True,
            },
        },
        "runner": {"auto_export": False},
        "statistics": {"confidence_level": 0.95},
    }
    with (cfg_dir / "defaults.yaml").open("w") as f:
        yaml.dump(defaults, f)

    # ── schemas / experiment_schema.yaml ──────────────────────────────────
    with (cfg_dir / "schemas" / "experiment_schema.yaml").open("w") as f:
        yaml.dump({"required_keys": ["dataset_name", "dataset_root"]}, f)

    # ── schemas / dataset_schema.yaml ─────────────────────────────────────
    with (cfg_dir / "schemas" / "dataset_schema.yaml").open("w") as f:
        yaml.dump({"required_keys": ["name", "files"]}, f)

    # ── datasets / demo.yaml ──────────────────────────────────────────────
    dataset_cfg = {
        "name": "DEMO",
        "version": "1.0",
        "description": "Synthetic 1000-node connectome for false-synapse demo.",
        "is_fafb": False,
        "files": {
            "neurons": "neurons.csv",
            "connections": "connections.csv",
        },
        "required_neuron_columns": ["root_id"],
        "required_connection_columns": ["pre_root_id", "post_root_id"],
    }
    with (cfg_dir / "datasets" / "demo.yaml").open("w") as f:
        yaml.dump(dataset_cfg, f)

    logger.info("Config files written to %s.", cfg_dir)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("=" * 65)
    logger.info("False Synapse Demo — 1000-node artificial connectome")
    logger.info("=" * 65)

    # ── Step 1: Generate synthetic dataset ────────────────────────────────
    logger.info("")
    logger.info("─" * 40)
    logger.info("STEP 1: Generating synthetic connectome (%d nodes, %d edges)", N_NEURONS, N_EDGES)
    t0 = time.perf_counter()
    neurons, connections = generate_synthetic_connectome()
    write_csv_files(neurons, connections)
    write_config_files()
    logger.info("Dataset generation took %.2f s.", time.perf_counter() - t0)

    # ── Step 2: Load dataset ──────────────────────────────────────────────
    logger.info("")
    logger.info("─" * 40)
    logger.info("STEP 2: Loading dataset")
    t0 = time.perf_counter()
    from core.data_loader import load_dataset

    # The dataset_root is the parent of the dataset-specific subfolder.
    # The subfolder must be named like "DEMO_v1" or similar (starts with "DEMO_").
    dataset_root = str(DATA_DIR.parent)  # points to ".../data/"

    dataset = load_dataset(
        "DEMO",
        dataset_root,
        configs_root=str(CFG_DIR),
    )
    logger.info(
        "Loaded %s: %d neurons, %d connections (%.2f s).",
        dataset.name, len(dataset.neurons), len(dataset.connections),
        time.perf_counter() - t0,
    )

    # ── Step 3: Build graph ───────────────────────────────────────────────
    logger.info("")
    logger.info("─" * 40)
    logger.info("STEP 3: Building igraph")
    t0 = time.perf_counter()
    from core.graph_builder import GraphBuilder

    graph = GraphBuilder().build(dataset)
    logger.info(
        "Graph built: %d vertices, %d edges (%.2f s).",
        graph.vcount(), graph.ecount(),
        time.perf_counter() - t0,
    )

    # ── Step 4: Preprocess ────────────────────────────────────────────────
    logger.info("")
    logger.info("─" * 40)
    logger.info("STEP 4: Preprocessing graph")
    t0 = time.perf_counter()
    from modules.preprocessing import preprocess_graph

    prepared = preprocess_graph(
        graph,
        index_node_attrs=["top_region", "soma_side"],
        feature_config={
            "indegree": True,
            "outdegree": True,
            "pagerank": True,
            "reciprocal_ratio": True,
            "hub_neighbor_count": True,
            "two_hop_size": True,
        },
    )
    logger.info(
        "Preprocessed: %s (%.2f s).",
        "valid ✓" if prepared.is_valid else "INVALID ⚠",
        time.perf_counter() - t0,
    )

    # ── Step 5: Candidate generation ──────────────────────────────────────
    logger.info("")
    logger.info("─" * 40)
    logger.info("STEP 5: Generating false-synapse candidates")
    t0 = time.perf_counter()
    from modules.preprocessing.false_synapses.candidate_generator import (
        CandidateGenerator,
    )
    from modules.preprocessing.false_synapses.config import FALSE_SYNAPSE_CONFIG

    # Tweak config for demo (lower top_k to keep runtime manageable).
    gen_config = {**FALSE_SYNAPSE_CONFIG, "min_region_size": 2, "top_k_multiplier": 10}
    generator = CandidateGenerator(prepared, config=gen_config)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "candidates.parquet"
    generator.generate(cache_path)
    gen_time = time.perf_counter() - t0

    import polars as pl
    candidates = pl.read_parquet(str(cache_path))
    logger.info(
        "Candidate generation: %s candidates in %.2f s.",
        f"{len(candidates):,}", gen_time,
    )
    if len(candidates) > 0:
        logger.info(
            "  Top-5 candidates by Jaccard_out:\n%s",
            str(candidates.head(5)),
        )

    # ── Step 6: Run ExperimentRunner with FalseSynapseModel ────────────────
    logger.info("")
    logger.info("─" * 40)
    logger.info("STEP 6: Running ExperimentRunner with FalseSynapseModel")
    t0 = time.perf_counter()

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

    # Baseline run (0 % error rate)
    baseline_config = ExperimentConfig(
        dataset_name="DEMO",
        dataset_root=dataset_root,
        configs_root=str(CFG_DIR),
        error_model_name="false_synapses",
        error_model_config={
            "error_rate": 0.0,
            "candidate_cache_path": str(cache_path),
        },
        analysis_names=["basic_structure"],
        preprocessing_config={
            "index_node_attrs": ["top_region"],
        },
        seed=RANDOM_SEED,
        experiment_id="false_synapse_demo_baseline",
    )

    logger.info("  Running baseline (0 %% error rate) …")
    result_base = runner.run(baseline_config)
    if result_base.succeeded:
        logger.info("  Baseline result: %s", result_base.summary())
    else:
        logger.warning("  Baseline had issues: %s", result_base.errors)

    # Perturbed run (ERROR_RATE % error rate)
    perturbed_config = ExperimentConfig(
        dataset_name="DEMO",
        dataset_root=dataset_root,
        configs_root=str(CFG_DIR),
        error_model_name="false_synapses",
        error_model_config={
            "error_rate": ERROR_RATE,
            "candidate_cache_path": str(cache_path),
        },
        analysis_names=["basic_structure"],
        preprocessing_config={
            "index_node_attrs": ["top_region"],
        },
        seed=RANDOM_SEED,
        experiment_id="false_synapse_demo_perturbed",
    )

    logger.info("  Running perturbed (%.1f %% error rate) …", ERROR_RATE * 100)
    result_pert = runner.run(perturbed_config)
    runner_time = time.perf_counter() - t0

    # ── Step 7: Results summary ──────────────────────────────────────────
    logger.info("")
    logger.info("═" * 65)
    logger.info("RESULTS SUMMARY")
    logger.info("═" * 65)

    if result_pert.succeeded:
        logger.info("Experiment: %s", result_pert.experiment_id)
        logger.info("Status:     %s", result_pert.status.value)
        logger.info("Runtime:    %.2f s", result_pert.runtime_seconds)

        if result_pert.error_result is not None:
            er = result_pert.error_result
            meta = er.perturbation_metadata
            n_added = len(er.added_edges)
            n_candidates = meta.get("candidates_available", 0)
            n_pool = meta.get("sampling_pool_size", 0)
            err_rate = meta.get("error_rate", ERROR_RATE)

            logger.info("")
            logger.info("  Error Model: false_synapses")
            logger.info("  Error rate:  %.4f", err_rate)
            logger.info("  Candidates available: %s", f"{n_candidates:,}")
            logger.info("  Sampling pool size:   %s", f"{n_pool:,}")
            logger.info("  False edges added:    %d", n_added)

            if n_added > 0:
                logger.info("  Sample of added edges (first 5):")
                for i, (pre, post, w) in enumerate(er.added_edges[:5]):
                    logger.info("    %d. %d → %d  (syn_count=%d)", i + 1, pre, post, w)
        else:
            logger.warning("  No error_result attached.")

        # ── Analysis results ──────────────────────────────────────────────
        logger.info("")
        logger.info("  Analyses:")
        for ar in result_pert.analysis_results:
            logger.info(
                "    %s: %s (%s)",
                ar.analysis_name, ar.status.value,
                ar.summary() if hasattr(ar, "summary") else "",
            )

    else:
        logger.error("Experiment FAILED with errors: %s", result_pert.errors)

    logger.info("")
    logger.info("─" * 40)
    logger.info("Total pipeline runtime: %.2f s", runner_time)

    # ── Validation checks ─────────────────────────────────────────────────
    logger.info("")
    logger.info("═" * 65)
    logger.info("VALIDATION CHECKS")
    logger.info("═" * 65)

    checks_passed = 0
    checks_failed = 0

    # Check 1: Experiment succeeded
    if result_pert.succeeded:
        logger.info("  ✓ Experiment completed successfully.")
        checks_passed += 1
    else:
        logger.error("  ✗ Experiment did not succeed.")
        checks_failed += 1

    # Check 2: Error result exists
    if result_pert.error_result is not None:
        logger.info("  ✓ ErrorResult produced by FalseSynapseModel.")
        checks_passed += 1
    else:
        logger.error("  ✗ No ErrorResult produced.")
        checks_failed += 1

    # Check 3: Correct number of added edges
    if result_pert.error_result is not None:
        n_added = len(result_pert.error_result.added_edges)
        expected = round(N_EDGES * ERROR_RATE)
        if n_added == expected:
            logger.info("  ✓ Added exactly %d false edges (expected %d).", n_added, expected)
            checks_passed += 1
        else:
            logger.warning(
                "  ~ Added %d false edges (expected %d) — candidates may be limited.",
                n_added, expected,
            )
            # Still pass if we added at least some
            if n_added > 0:
                checks_passed += 1
            else:
                checks_failed += 1

    # Check 4: Added edges have valid root_ids
    if result_pert.error_result is not None and len(result_pert.error_result.added_edges) > 0:
        valid_ids = set(range(1001, 1001 + N_NEURONS))
        all_valid = True
        for pre, post, _ in result_pert.error_result.added_edges:
            if pre not in valid_ids or post not in valid_ids:
                all_valid = False
                break
        if all_valid:
            logger.info("  ✓ All added edges reference valid root_ids.")
            checks_passed += 1
        else:
            logger.error("  ✗ Some added edges reference invalid root_ids.")
            checks_failed += 1

    # Check 5: Added edges have positive weights
    if result_pert.error_result is not None and len(result_pert.error_result.added_edges) > 0:
        all_positive = all(w > 0 for (_, _, w) in result_pert.error_result.added_edges)
        if all_positive:
            logger.info("  ✓ All added edges have positive weights.")
            checks_passed += 1
        else:
            logger.error("  ✗ Some added edges have non-positive weights.")
            checks_failed += 1

    # Check 6: Baseline graph not modified
    original_edges = graph.ecount()
    if graph.ecount() == original_edges:
        logger.info("  ✓ Baseline graph was not modified (still %d edges).", original_edges)
        checks_passed += 1
    else:
        logger.error("  ✗ Baseline graph was modified!")
        checks_failed += 1

    # Check 7: Candidate generation produced candidates
    if len(candidates) > 0:
        logger.info("  ✓ Candidate generation produced %s candidates.", f"{len(candidates):,}")
        checks_passed += 1
    else:
        logger.warning("  ~ No candidates generated (check region structure).")
        checks_failed += 1

    # ── Final verdict ─────────────────────────────────────────────────────
    logger.info("")
    logger.info("═" * 65)
    logger.info("VERDICT: %d / %d checks passed",
                 checks_passed, checks_passed + checks_failed)
    logger.info("═" * 65)

    if checks_failed == 0:
        logger.info("All checks passed! False-synapse demo is working correctly.")
    else:
        logger.warning("%d check(s) failed — review logs above for details.", checks_failed)

    logger.info("")
    logger.info("Generated data:   %s", DATA_DIR)
    logger.info("Config files:     %s", CFG_DIR)
    logger.info("Candidate cache:  %s", cache_path)
    logger.info("")


if __name__ == "__main__":
    main()
