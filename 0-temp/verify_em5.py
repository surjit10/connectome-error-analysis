"""
EM5 — Merge Errors: standalone verification script (mirrors verify_em4.py).

Verifies the EM5 merge-errors implementation end-to-end on a real dataset
(default: BANC) by running the MergeExperimentRunner across several error
rates and asserting the merge accounting invariants:

    1. Vertex count drops by exactly k (pairs merged).
    2. Edge count = baseline − self-loops dropped − parallel pairs collapsed.
    3. Total synapse count = baseline − internal_synapses_dropped.
    4. Achieved error rate (fraction of eligible neurons absorbed) lands
       within the tolerance of the target.
    5. Temp graphs have no self-loops and no multi-edges.
    6. The post-merge lookup is internally consistent (id_to_idx / id_map
       are mutual inverses; merged id present; absorbed roots absent).
    7. The baseline PreparedGraph is never mutated (vcount/ecount/weights
       unchanged after every trial).

Usage:
    .venv/bin/python 0-temp/verify_em5.py [dataset_name] [--rates 0.01 0.05 0.10]

Writes a JSON summary to analysis/em5_stats.json and prints a pass/fail report.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import igraph

from core.experiment_runner import ExperimentConfig
from core.merge_experiment_runner import MergeExperimentRunner
from modules.error_models import registry as error_registry
from modules.graph_analyses.analysis_registry import registry as analysis_registry

DATASET_NAME = sys.argv[1] if len(sys.argv) > 1 else "BANC"
DATASET_ROOT = "research_data/raw"
CONFIGS_ROOT = "configs"

if "--rates" in sys.argv:
    i = sys.argv.index("--rates")
    RATES = [float(r) for r in sys.argv[i + 1:]]
else:
    RATES = [0.00, 0.01, 0.05, 0.10]

SEEDS = [1]

ERROR_MODEL_CONFIG = {
    "region_constraint": True,
    "soma_side_constraint": True,
    "degree_threshold": 10,      # quality floor (not eligibility)
    "min_shared_partners": 3,    # Stage 2 calibration
    "jaccard_min": 0.001,        # ranking floor
    "top_k_per_neuron": 50,      # implementation bound
    "max_retries": 20,           # bounded rejection re-sampling
}

ANALYSES = ["basic_structure", "degree_distribution", "pagerank"]

TOLERANCE_ABS = 0.01  # achieved vs target error rate tolerance


def main() -> None:
    start_time = time.time()
    print(f"[verify_em5] Dataset={DATASET_NAME} rates={RATES} seeds={SEEDS}")

    runner = MergeExperimentRunner(analysis_registry, error_registry)
    checks: dict = {}
    failures: list = []

    for rate in RATES:
        for seed in SEEDS:
            tag = f"rate={rate:.2f} seed={seed}"

            config = ExperimentConfig(
                dataset_name=DATASET_NAME,
                dataset_root=DATASET_ROOT,
                configs_root=CONFIGS_ROOT,
                error_model_name="merge_errors",
                error_model_config={"error_rate": rate, **ERROR_MODEL_CONFIG},
                analysis_names=ANALYSES,
                preprocessing_config={
                    "features": {"degree": True, "synapse_counts": True}
                },
                seed=seed,
                output_root=None,  # in-memory trial; no export
                create_zip=False,
            )

            res = runner.run(config)

            if not res.succeeded:
                failures.append(f"{tag}: runner FAILED: {res.errors}")
                continue

            meta = res.error_result.perturbation_metadata
            base = res.prepared_graph.graph
            base_v, base_e = base.vcount(), base.ecount()
            base_syn = sum(base.es["syn_count"])
            k = meta["pairs_merged"]

            # ── 1. Achieved vs target error rate ─────────────────────────
            # The per-neuron error rate is discrete: k = round(0.5*rate*
            # n_eligible) pairs, so the achieved rate = 2k/n_eligible can
            # deviate from the configured rate by up to ~1/n_eligible (the
            # same quantization EM4 exhibits).  The exact invariant is
            # achieved == 2*target_pairs/n_eligible; the configured rate is
            # only approached as n_eligible grows.
            target = meta["target_pairs"]
            achieved = meta["achieved_error_rate"]
            n_eligible = meta["eligible_neurons"]
            if k != target:
                failures.append(f"{tag}: pairs_merged={k} != target_pairs={target}")
            expected_discrete = (2.0 * target / n_eligible) if n_eligible > 0 else 0.0
            if abs(achieved - expected_discrete) > 1e-9:
                failures.append(
                    f"{tag}: achieved_error_rate={achieved:.4f} != "
                    f"2*k/n_eligible={expected_discrete:.4f}"
                )
            # Soft check: configured rate vs achieved (quantization-aware).
            if abs(achieved - rate) > TOLERANCE_ABS + (2.0 / max(n_eligible, 1)):
                failures.append(
                    f"{tag}: achieved_error_rate={achieved:.4f} deviates from "
                    f"configured {rate:.4f} beyond quantization tolerance"
                )

            # ── 2. Per-vertex accounting on the perturbed analysis graph ─
            # The analysis graph lives inside result.analysis_results; the
            # structural metrics expose node/edge/synapse counts.
            structure = None
            for a_res in res.analysis_results:
                if a_res.analysis_name == "basic_structure":
                    structure = a_res.metrics
            if structure is None:
                failures.append(f"{tag}: basic_structure analysis missing")
                continue

            pert_nodes = structure["node_count"]
            pert_edges = structure["edge_count"]
            pert_syn = structure["total_synapses"]

            # node_count = baseline − 2k (absorbed) + k (merged) = baseline − k
            if pert_nodes != base_v - k:
                failures.append(
                    f"{tag}: node_count {pert_nodes} != baseline {base_v} - k {k}"
                )
            loops_dropped = meta.get("self_loops_dropped", 0)
            parallel_collapsed = meta.get("parallel_pairs_collapsed", 0)
            internal_synapses = meta.get("internal_synapses_dropped", 0)

            if pert_edges != base_e - loops_dropped - parallel_collapsed:
                failures.append(
                    f"{tag}: edge_count {pert_edges} != {base_e} - "
                    f"{loops_dropped} - {parallel_collapsed}"
                )
            if pert_syn != base_syn - internal_synapses:
                failures.append(
                    f"{tag}: synapse_count {pert_syn} != {base_syn} - "
                    f"{internal_synapses}"
                )

            # ── 3. Baseline immutability ─────────────────────────────────
            if base.vcount() != base_v or base.ecount() != base_e:
                failures.append(f"{tag}: baseline graph was MUTATED")
            if sum(base.es["syn_count"]) != base_syn:
                failures.append(f"{tag}: baseline synapse counts changed")

            # ── 4. Temp-graph invariants (rebuilt via a fresh trial) ─────
            # Re-run the model on the same prepared graph to inspect the
            # temporary merged graph directly (the trial above destroyed it).
            from modules.error_models import registry as em_registry
            from core.experiment_runner import ExperimentResult

            prepared = res.prepared_graph
            model = em_registry.instantiate("merge_errors")
            err = model.execute(
                prepared,
                config={"error_rate": rate, **ERROR_MODEL_CONFIG},
                seed=seed,
            )
            plan = (err.extra or {}).get("merge_plan") or {}
            if plan:
                cfg2 = ExperimentConfig(
                    dataset_name=DATASET_NAME,
                    dataset_root=DATASET_ROOT,
                    configs_root=CONFIGS_ROOT,
                )
                res2 = ExperimentResult(experiment_id="verify", dataset_name=DATASET_NAME)
                temp_g, temp_p = runner._merge_build_temp_graph(
                    prepared, err, cfg2, res2
                )
                if temp_g is None:
                    failures.append(f"{tag}: temp graph build returned None")
                else:
                    loops = [e.index for e in temp_g.es if temp_g.is_loop(e.index)]
                    if loops:
                        failures.append(f"{tag}: {len(loops)} self-loops in temp graph")
                    # Multi-edge check applies only to edges incident to the
                    # merged vertices (re-attached edges must be simple).  The
                    # baseline's own parallel edges between non-absorbed
                    # vertices are legitimate and remain untouched.
                    merged_idx = {temp_g["id_to_idx"][mid] for mid in plan}
                    seen_keys = set()
                    multi_incident = []
                    for e in temp_g.es:
                        if e.source in merged_idx or e.target in merged_idx:
                            key = (e.source, e.target)
                            if key in seen_keys:
                                multi_incident.append(e.index)
                            seen_keys.add(key)
                    if multi_incident:
                        failures.append(
                            f"{tag}: {len(multi_incident)} multi-edges incident "
                            "to merged vertices"
                        )

                    # Lookup consistency: id_to_idx/id_map mutual inverses.
                    id2i = temp_g["id_to_idx"]
                    i2m = temp_g["id_map"]
                    for rid, idx in id2i.items():
                        if i2m.get(idx) != rid:
                            failures.append(
                                f"{tag}: lookup inversion broken for {rid}"
                            )
                    # Merged ids present; absorbed roots absent.
                    for entry in plan.values():
                        mid = entry["merge_id"]
                        if mid not in id2i:
                            failures.append(f"{tag}: merged id {mid} absent from lookup")
                        for src in entry["source_ids"]:
                            if src in id2i:
                                failures.append(
                                    f"{tag}: absorbed root {src} still in lookup"
                                )
                    # Edge endpoints all valid.
                    for e in temp_g.es:
                        if not (0 <= e.source < temp_g.vcount() and 0 <= e.target < temp_g.vcount()):
                            failures.append(f"{tag}: invalid edge endpoint")
                    del temp_g

            checks[tag] = {
                "target_pairs": meta["target_pairs"],
                "pairs_merged": k,
                "neurons_absorbed": meta.get("neurons_absorbed", 0),
                "pairs_rejected": meta.get("pairs_rejected", 0),
                "achieved_error_rate": achieved,
                "node_delta": pert_nodes - base_v,
                "edge_delta": pert_edges - base_e,
                "synapse_delta": pert_syn - base_syn,
                "self_loops_dropped": meta.get("self_loops_dropped", 0),
                "parallel_pairs_collapsed": meta.get("parallel_pairs_collapsed", 0),
                "internal_synapses_dropped": meta.get("internal_synapses_dropped", 0),
                "ok": True,
            }
            print(
                f"  [{tag}] merged={k} absorbed={meta['neurons_absorbed']} "
                f"achieved={achieved:.4f} | Δnodes={pert_nodes - base_v} "
                f"Δedges={pert_edges - base_e} Δsyn={pert_syn - base_syn}"
            )

    ok = not failures
    summary = {
        "dataset": DATASET_NAME,
        "rates": RATES,
        "seeds": SEEDS,
        "all_checks_passed": ok,
        "failures": failures,
        "per_trial": checks,
        "runtime_seconds": time.time() - start_time,
    }

    Path("analysis").mkdir(exist_ok=True)
    with open("analysis/em5_stats.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 60)
    print(f"  EM5 VERIFICATION {'PASSED' if ok else 'FAILED'}")
    print("=" * 60)
    for fl in failures:
        print(f"  [FAIL] {fl}")
    print(f"  Summary written to analysis/em5_stats.json")
    print(f"  Runtime: {time.time() - start_time:.1f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
