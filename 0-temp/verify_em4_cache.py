"""
EM4 memory-leak fix verification harness.

Simulates the notebook's trial loop (fresh graph per trial -> error model run)
and records, per trial:
  - perturbation_metadata and split_plan  (the scientific outputs)
  - len(_candidate_cache)                  (memory behaviour, pre-fix)
  - whether the previous trial's graph is still strongly referenced

Usage:
    python3 0-temp/verify_em4_cache.py <snapshot.json>

Run once BEFORE the fix and once AFTER; the scientific sections of the two
snapshots must be byte-identical, while the memory sections must change.
"""

import gc
import json
import sys
import weakref

import igraph

from modules.error_models import registry
from modules.preprocessing import preprocess_graph
import modules.error_models.split_errors.model as split_model


# --------------------------------------------------------------------------- #
# Synthetic multi-hub graph (reuses the test-suite topology idiom, scaled up)  #
# --------------------------------------------------------------------------- #

def _finalise(graph, root_ids):
    n = len(root_ids)
    if "syn_count" not in graph.edge_attributes():
        graph.es["syn_count"] = [1] * graph.ecount()
    if "super_class" not in graph.vertex_attributes():
        graph.vs["super_class"] = ["neuron"] * n
    graph["dataset_name"] = "TEST"
    graph["id_to_idx"] = {rid: i for i, rid in enumerate(root_ids)}
    graph["id_map"] = {i: rid for rid, i in graph["id_to_idx"].items()}
    return graph


def build_multi_hub(n_split_hubs=10, n_reject_hubs=3, n_per=8):
    """n_split_hubs two-clique hubs (always split) + n_reject_hubs clique hubs
    (always rejected, exercising the retry path)."""
    hubs = [1000 * (i + 1) for i in range(n_split_hubs + n_reject_hubs)]
    next_rid = [1]

    def alloc(k):
        ids = list(range(next_rid[0], next_rid[0] + k))
        next_rid[0] += k
        return ids

    graph = igraph.Graph(directed=True)
    all_roots = list(hubs)
    edges = []
    for hub in hubs[:n_split_hubs]:
        partners = alloc(2 * n_per)
        all_roots.extend(partners)
        for p in partners:
            edges.append((hub, p))
        for a in partners[:n_per]:
            for b in partners[:n_per]:
                if a < b:
                    edges.append((a, b))
        for a in partners[n_per:]:
            for b in partners[n_per:]:
                if a < b:
                    edges.append((a, b))
    for hub in hubs[n_split_hubs:]:
        partners = alloc(2 * n_per)
        all_roots.extend(partners)
        for p in partners:
            edges.append((hub, p))
        for i, a in enumerate(partners):
            for b in partners[i + 1:]:
                edges.append((a, b))

    graph.add_vertices(len(all_roots))
    graph.vs["root_id"] = all_roots
    idx = {rid: i for i, rid in enumerate(all_roots)}
    graph.add_edges([(idx[s], idx[t]) for s, t in edges])
    return _finalise(graph, all_roots)


# --------------------------------------------------------------------------- #
# Trial loop (mirrors notebook Cell 7)                                         #
# --------------------------------------------------------------------------- #

def run_trials(n_trials=6, seed_base=1, error_rate=0.5):
    model = registry.instantiate("split_errors")
    cfg = {
        "error_rate": error_rate,
        "degree_threshold": 10,
        "min_fragment_partners": 3,
        "max_retries": 20,
    }

    trials = []
    prev_graph_ref = None

    for t in range(n_trials):
        graph = build_multi_hub()
        prepared = preprocess_graph(graph, index_node_attrs=[])

        # Reference to the PREVIOUS trial's graph before running this trial.
        if prev_graph_ref is not None:
            gc.collect()
            prev_alive_after_next_trial = prev_graph_ref() is not None
        else:
            prev_alive_after_next_trial = None

        result = model.execute(prepared, config=cfg, seed=seed_base + t)

        cache = getattr(split_model, "_candidate_cache", None)
        cache_size = len(cache) if cache is not None else 0

        plan = result.extra.get("split_plan", {})
        trials.append({
            "trial": t,
            "seed": seed_base + t,
            "cache_size": cache_size,
            "prev_graph_alive": prev_alive_after_next_trial,
            "metadata": result.perturbation_metadata,
            "split_plan": {str(k): v for k, v in sorted(plan.items())},
        })

        prev_graph_ref = weakref.ref(prepared.graph)
        del prepared, graph, result
        gc.collect()

    final_cache = getattr(split_model, "_candidate_cache", None)
    return {
        "trials": trials,
        "final_cache_len": len(final_cache) if final_cache is not None else 0,
        "final_cache_keys": (
            list(final_cache.keys()) if final_cache is not None else []
        ),
    }


def main():
    out_path = sys.argv[1]
    snap = run_trials()
    # Scientific sections only (metadata + split_plan) for the equivalence diff.
    snap["scientific"] = [
        {"seed": tr["seed"], "metadata": tr["metadata"],
         "split_plan": tr["split_plan"]}
        for tr in snap["trials"]
    ]
    with open(out_path, "w") as f:
        json.dump(snap, f, indent=2, sort_keys=True)
    print(f"wrote {out_path}")
    print(f"final cache len        : {snap['final_cache_len']}")
    print(f"per-trial cache sizes  : {[t['cache_size'] for t in snap['trials']]}")
    print(f"prev-graph-alive flags : {[t['prev_graph_alive'] for t in snap['trials']]}")


if __name__ == "__main__":
    main()
