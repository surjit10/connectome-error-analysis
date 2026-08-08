"""
EM5 — Self-loop bookkeeping mismatch reproduction (root-cause proof).

The runner's QC reports:
    "Self-loop bookkeeping mismatch: runner dropped X, plan recorded Y."

This script proves WHY: the plan (`MergeErrorsModel._merge_stats`) counts
self-loops via SET-based membership (`b in succ_a`), so it counts each
DIRECTION at most once even when the baseline graph contains PARALLEL edges
(multiple physical rows for the same directed pair).  The runner
(`MergeExperimentRunner._merge_build_temp_graph`) iterates every physical
edge via `temp.incident()`, so it counts each parallel edge individually.

BANC-v888 contains 668,562 directed pairs with multiplicity > 1
(max multiplicity 22, ~953K duplicate rows), so every merged pair whose
members are connected by parallel edges inflates the runner's count by
(multiplicity - 1) per direction relative to the plan.

Usage:
    .venv/bin/python 0-temp/repro_em5_selfloop.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import igraph

from core.experiment_runner import ExperimentConfig, ExperimentResult
from core.merge_experiment_runner import MergeExperimentRunner
from modules.error_models import registry as error_registry
from modules.error_models.merge_errors.model import MergeErrorsModel
from modules.graph_analyses.analysis_registry import registry as analysis_registry
from modules.preprocessing import preprocess_graph


def _finalise(graph, root_ids):
    graph.vs["top_region"] = ["AL"] * len(root_ids)
    graph.vs["soma_side"] = ["left"] * len(root_ids)
    graph["dataset_name"] = "REPRO"
    graph["id_to_idx"] = {rid: i for i, rid in enumerate(root_ids)}
    graph["id_map"] = {i: rid for rid, i in graph["id_to_idx"].items()}
    return graph


def _cfg(error_rate=1.0, **overrides):
    cfg = {
        "error_rate": error_rate,
        "degree_threshold": 2,
        "min_shared_partners": 3,
        "jaccard_min": 0.001,
        "top_k_per_neuron": 50,
        "max_retries": 20,
        "region_constraint": True,
        "soma_side_constraint": True,
    }
    cfg.update(overrides)
    return cfg


def synthetic_parallel_case():
    """Pair (1000, 2000) connected by THREE parallel 1000->2000 edges
    (weights 5, 3, 2) plus one 2000->1000 edge (weight 4), plus shared
    partners X1..X3 so the pair is a valid candidate."""
    roots = [1000, 2000] + list(range(1, 4))
    g = igraph.Graph(directed=True)
    g.add_vertices(len(roots))
    g.vs["root_id"] = roots
    edges = []
    weights = {}
    for x in range(2, 5):
        edges.append((0, x)); weights[(0, x)] = 1   # 1000 -> X1..X3
        edges.append((1, x)); weights[(1, x)] = 1   # 2000 -> X1..X3
    edges += [(0, 1), (0, 1), (0, 1)]; weights[(0, 1)] = 5  # 3x parallel A->B
    edges.append((1, 0)); weights[(1, 0)] = 4       # B->A
    g.add_edges(edges)
    g.es["syn_count"] = [weights[e] for e in edges]
    return _finalise(g, roots)


def true_runner_selfloop_count(prepared, plan):
    """Exact count of physical edges the runner will drop as self-loops:
    every baseline edge whose BOTH endpoints belong to the same merged pair."""
    graph = prepared.graph
    id_to_idx = prepared.lookup.id_to_idx
    total = 0
    syn = 0
    for entry in plan.values():
        a, b = entry["source_ids"]
        ia, ib = id_to_idx[a], id_to_idx[b]
        for e in graph.es.select(_source_in=[ia, ib], _target_in=[ia, ib]):
            total += 1
            syn += int(e["syn_count"])
    return total, syn


def run_case(name, prepared, error_rate=1.0):
    print(f"\n=== {name} ===")
    base = prepared.graph
    model = MergeErrorsModel()
    err = model.execute(prepared, config=_cfg(error_rate), seed=1)
    plan = (err.extra or {}).get("merge_plan") or {}
    plan_loops = sum(p.get("self_loops_dropped", 0) for p in plan.values())
    plan_syn = sum(p.get("internal_synapses_dropped", 0) for p in plan.values())
    true_loops, true_syn = true_runner_selfloop_count(prepared, plan)

    runner = MergeExperimentRunner(analysis_registry, error_registry)
    cfg2 = ExperimentConfig(dataset_name="REPRO", dataset_root="x")
    res2 = ExperimentResult(experiment_id="repro", dataset_name="REPRO")
    # The mismatch is emitted via logger.warning, so capture it on the logger
    # (it is NOT appended to result.warnings).
    import logging
    log_records = []
    handler = logging.Handler()
    handler.emit = lambda record: log_records.append(record.getMessage())
    runner_logger = logging.getLogger("core.merge_experiment_runner")
    runner_logger.addHandler(handler)
    try:
        temp_g, temp_p = runner._merge_build_temp_graph(prepared, err, cfg2, res2)
    finally:
        runner_logger.removeHandler(handler)
    qc_warn = any("Self-loop bookkeeping mismatch" in m for m in log_records)

    print(f"  pairs merged          : {len(plan)}")
    print(f"  plan self_loops       : {plan_loops}")
    print(f"  TRUE (physical) loops : {true_loops}   <- what the runner drops")
    print(f"  plan internal_syn     : {plan_syn}")
    print(f"  TRUE internal_syn     : {true_syn}")
    print(f"  QC mismatch warning   : {qc_warn}")
    if temp_g is not None:
        print(f"  temp nodes/edges      : {temp_g.vcount()} / {temp_g.ecount()}  "
              f"(baseline {base.vcount()} / {base.ecount()})")
        loops = [e.index for e in temp_g.es if temp_g.is_loop(e.index)]
        print(f"  temp self-loops       : {len(loops)}   multi-edges: {temp_g.has_multiple()}")
        print(f"  temp synapse sum      : {sum(temp_g.es['syn_count'])}   "
              f"baseline synapse sum: {sum(base.es['syn_count'])}")
        print(f"  node invariant (base-k): "
              f"{base.vcount() - len(plan)} == {temp_g.vcount()}: "
              f"{base.vcount() - len(plan) == temp_g.vcount()}")


def banc_subgraph_case(n_neurons=4000):
    import polars as pl
    print(f"\n=== BANC subgraph ({n_neurons} neurons) ===")
    conn = pl.read_csv(
        "research_data/raw/BANC_v888/connections_princeton.csv.gz",
        infer_schema_length=10000,
    )
    deg = (
        pl.concat([
            conn.select(pre_root_id=pl.col("pre_root_id")),
            conn.select(pre_root_id=pl.col("post_root_id")),
        ])
        .group_by("pre_root_id")
        .len()
    )
    core = deg.sort("len", descending=True).head(n_neurons)["pre_root_id"].to_list()
    core_set = set(core)
    sub = conn.filter(
        pl.col("pre_root_id").is_in(core_set) & pl.col("post_root_id").is_in(core_set)
    )
    print(f"  sampled neurons: {len(core)}, edges: {sub.height}")

    g = igraph.Graph(directed=True)
    roots = sorted(core_set)
    idx = {r: i for i, r in enumerate(roots)}
    g.add_vertices(len(roots))
    g.vs["root_id"] = roots
    g.add_edges([(idx[s], idx[d]) for s, d in zip(sub["pre_root_id"], sub["post_root_id"])])
    g.es["syn_count"] = sub["syn_count"].to_list()
    _finalise(g, roots)
    prepared = preprocess_graph(g, index_node_attrs=["top_region", "soma_side"])

    d = sub.group_by(["pre_root_id", "post_root_id"]).agg(pl.len().alias("cnt"))
    print(f"  distinct pairs: {d.height}, parallel pairs: {d.filter(pl.col('cnt') > 1).height}")
    run_case("BANC-subgraph (rate=0.10)", prepared, error_rate=0.10)


if __name__ == "__main__":
    g1 = synthetic_parallel_case()
    p1 = preprocess_graph(g1, index_node_attrs=["top_region", "soma_side"])
    run_case("synthetic parallel A->B x3 + B->A", p1, error_rate=1.0)
    banc_subgraph_case()
