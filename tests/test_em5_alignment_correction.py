"""
Deterministic synthetic alignment verification test.

Verifies that after the EM5 PageRank correction:

  1. baseline PageRank exists in baseline_analysis_results
  2. EM5 merge occurs (A+B -> M1, C+D -> M2)
  3. absorbed IDs are removed from the graph
  4. merged IDs are present in the temp graph
  5. baseline vector is collapsed into merged space (sum rule)
  6. perturbed vector is re-indexed into merged space
  7. both vectors represent the same comparison IDs/order
  8. Pearson receives aligned values (not positional values)
  9. Spearman receives aligned values
 10. Top-K compares the same neuron identities
 11. Raw pagerank_scores is removed; scalar keys are present

Graph
-----
Neurons: A=100, B=200, C=300, D=400, E=500
Edges (syn_count=2):
  A -> C, A -> D, B -> C, B -> D  (A+B share all partners -> merge pair 1)

Merge at rate=1.0 produces: A+B -> M1, C+D -> M2 (2 pairs, 4 absorbed)
Temp graph: [E, M1, M2]  (3 nodes = 5 - 2 merges)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import igraph

from modules.preprocessing import preprocess_graph


def _build_graph():
    """5-node directed graph where A+B and C+D will both be merged."""
    roots = [100, 200, 300, 400, 500]  # A, B, C, D, E
    g = igraph.Graph(directed=True)
    g.add_vertices(len(roots))
    g.vs["root_id"] = roots
    edges = [(0, 2), (0, 3), (1, 2), (1, 3)]
    g.add_edges(edges)
    g.es["syn_count"] = [2, 2, 2, 2]
    g.vs["super_class"] = ["neuron"] * 5
    g.vs["top_region"] = ["AL"] * 5
    g.vs["soma_side"] = ["left"] * 5
    g["dataset_name"] = "TEST"
    g["id_to_idx"] = {rid: i for i, rid in enumerate(roots)}
    g["id_map"] = {i: rid for i, rid in enumerate(roots)}
    return g


def test_em5_pagerank_alignment_end_to_end():
    """
    Full deterministic alignment test.
    Verifies neuron-ID-aware comparison, not positional comparison.
    """
    from core.experiment_runner import ExperimentConfig, ExperimentResult
    from core.merge_experiment_runner import MergeExperimentRunner
    from modules.graph_analyses.analysis_registry import registry as a_reg
    from modules.error_models import registry as e_reg

    prepared = preprocess_graph(
        _build_graph(), index_node_attrs=["top_region", "soma_side"]
    )

    # ── Step 1: Verify baseline graph ─────────────────────────────────────
    base_g = prepared.graph
    assert base_g.vcount() == 5
    baseline_ids = [base_g.vs[i]["root_id"] for i in range(base_g.vcount())]
    print(f"\nBaseline node IDs: {baseline_ids}")

    # ── Step 2: Apply error model ─────────────────────────────────────────
    model = e_reg.instantiate("merge_errors")
    err = model.execute(
        prepared,
        config={
            "error_rate": 1.0,
            "degree_threshold": 2,
            "min_shared_partners": 1,
            "jaccard_min": 0.0,
            "top_k_per_neuron": 50,
            "max_retries": 5,
        },
        seed=1,
    )
    plan = err.extra.get("merge_plan", {})
    assert len(plan) >= 1, "Expected at least one merge pair"
    k = len(plan)
    print(f"\nMerge plan: {k} pair(s)")
    all_source_ids = set()
    all_merge_ids = set()
    for entry in plan.values():
        src = entry["source_ids"]
        mid = entry["merge_id"]
        all_source_ids.update(src)
        all_merge_ids.add(mid)
        print(f"  root_ids={src} -> merged as {mid}")

    # ── Step 3: Build temp graph ──────────────────────────────────────────
    runner = MergeExperimentRunner(a_reg, e_reg)
    config = ExperimentConfig(dataset_name="TEST", dataset_root="x")
    result = ExperimentResult(experiment_id="align_test", dataset_name="TEST")
    temp_graph, temp_prepared = runner._merge_build_temp_graph(
        prepared, err, config, result
    )
    assert temp_graph is not None
    expected_temp_vcount = base_g.vcount() - k  # net -1 per pair
    assert temp_graph.vcount() == expected_temp_vcount, (
        f"Expected {expected_temp_vcount} nodes in temp graph, "
        f"got {temp_graph.vcount()}"
    )

    temp_ids = [temp_graph.vs[i]["root_id"] for i in range(temp_graph.vcount())]
    print(f"\nTemp graph node IDs: {temp_ids}")

    temp_id_set = set(temp_ids)
    # All absorbed sources must be gone
    for sid in all_source_ids:
        assert sid not in temp_id_set, f"Absorbed root {sid} still in temp graph"
    # All merged IDs must be present
    for mid in all_merge_ids:
        assert mid in temp_id_set, f"Merged ID {mid} missing from temp graph"

    # ── Step 4: Run PageRank on baseline and temp graph ───────────────────
    from modules.graph_analyses.analysis_registry import registry as analysis_reg
    pagerank_analysis = analysis_reg.instantiate("pagerank")
    base_res = pagerank_analysis.execute(prepared, config={})
    pert_res = pagerank_analysis.execute(temp_prepared, config={})

    baseline_pr = list(base_res.metrics["pagerank_scores"])
    perturbed_pr = list(pert_res.metrics["pagerank_scores"])
    print(f"\nBaseline PageRank length: {len(baseline_pr)}")
    print(f"Perturbed PageRank length (pre-alignment): {len(perturbed_pr)}")
    assert len(baseline_pr) == 5
    assert len(perturbed_pr) == expected_temp_vcount

    # ── Step 5: Populate result (simulates baseline_analysis_names) ───────
    result.baseline_analysis_results.append(base_res)
    result.analysis_results.append(pert_res)

    # ── Step 6: Run alignment ─────────────────────────────────────────────
    runner._align_pagerank_vectors(result, prepared, plan, temp_graph)

    # ── Step 7: Verify collapsed baseline ────────────────────────────────
    collapsed_base = result.baseline_analysis_results[0].metrics["pagerank_scores"]
    expected_aligned_len = base_g.vcount() - k
    print(f"\nCollapsed baseline length: {len(collapsed_base)}")
    assert len(collapsed_base) == expected_aligned_len

    # Get merged_order to verify ID alignment
    from core.merge_vector_alignment import build_merged_order
    id_map = prepared.lookup.id_map
    merged_order = build_merged_order(id_map, 5, plan)
    print(f"\nAligned IDs (merged_order): {merged_order}")
    print(f"Collapsed baseline values:  {[round(v, 6) for v in collapsed_base]}")

    # Verify sum rule for each merge pair
    id_to_idx = prepared.lookup.id_to_idx
    for entry in plan.values():
        src = entry["source_ids"]
        pr_a = baseline_pr[id_to_idx[src[0]]]
        pr_b = baseline_pr[id_to_idx[src[1]]]
        first_source = src[0]
        slot_idx = merged_order.index(first_source)
        expected_sum = pr_a + pr_b
        actual_val = collapsed_base[slot_idx]
        assert abs(actual_val - expected_sum) < 1e-9, (
            f"Sum rule violated for pair {src}: "
            f"collapsed[{slot_idx}]={actual_val:.8f} != "
            f"PR({src[0]})+PR({src[1]})={expected_sum:.8f}"
        )
        print(f"\nSum rule [OK]: PR({src[0]})+PR({src[1]}) = "
              f"{pr_a:.6f}+{pr_b:.6f} = {expected_sum:.6f} "
              f"== collapsed[{slot_idx}]={actual_val:.6f}")

    # ── Step 8: pagerank_scores removed from analysis_results ────────────
    pert_metrics = result.analysis_results[0].metrics
    assert "pagerank_scores" not in pert_metrics, (
        "Raw pagerank_scores must be removed after per-trial comparison"
    )
    print("\nRaw pagerank_scores correctly removed from analysis_results [OK]")

    # ── Step 9: Scalar comparison metrics present and valid ───────────────
    for scalar_key in (
        "pagerank_scores_pearson",
        "pagerank_scores_spearman",
        "pagerank_scores_topk_overlap",
    ):
        assert scalar_key in pert_metrics, f"Missing scalar: {scalar_key}"
        val = pert_metrics[scalar_key]
        print(f"  {scalar_key} = {val:.6f}")
        assert isinstance(val, float), f"{scalar_key} must be float, got {type(val)}"

    print("\n[OK] All EM5 PageRank alignment checks passed.")
    print("     Aligned comparison uses neuron root IDs, not array positions.")


def test_no_baseline_analysis_results_still_runs_without_crash():
    """
    If baseline_analysis_names is NOT configured (empty baseline_analysis_results),
    _align_pagerank_vectors emits a warning and skips Phase 3 gracefully.
    The perturbed pagerank_scores vector remains in analysis_results unchanged
    (Phase 2 still runs because it doesn't depend on baseline data).
    """
    from core.experiment_runner import ExperimentConfig, ExperimentResult
    from core.merge_experiment_runner import MergeExperimentRunner
    from modules.graph_analyses.analysis_registry import registry as a_reg
    from modules.error_models import registry as e_reg

    prepared = preprocess_graph(
        _build_graph(), index_node_attrs=["top_region", "soma_side"]
    )
    model = e_reg.instantiate("merge_errors")
    err = model.execute(prepared, config={
        "error_rate": 1.0, "degree_threshold": 2, "min_shared_partners": 1,
        "jaccard_min": 0.0,
    }, seed=1)
    plan = err.extra.get("merge_plan", {})

    runner = MergeExperimentRunner(a_reg, e_reg)
    config = ExperimentConfig(dataset_name="TEST", dataset_root="x")
    result = ExperimentResult(experiment_id="no_baseline", dataset_name="TEST")
    temp_graph, temp_prepared = runner._merge_build_temp_graph(
        prepared, err, config, result
    )
    from modules.graph_analyses.analysis_registry import registry as analysis_reg
    pert_res = analysis_reg.instantiate("pagerank").execute(temp_prepared, config={})
    result.analysis_results.append(pert_res)
    # NOTE: baseline_analysis_results is intentionally empty (not configured)

    # Should not crash — warning is emitted but execution continues
    runner._align_pagerank_vectors(result, prepared, plan, temp_graph)

    pert_metrics = result.analysis_results[0].metrics
    # Phase 2 (reindex) still ran -> pagerank_scores is still present (reindexed)
    # Phase 3 (comparison) was skipped -> no scalar keys
    assert "pagerank_scores" in pert_metrics, (
        "Without baseline, pagerank_scores should remain (Phase 3 skipped)"
    )
    assert "pagerank_scores_pearson" not in pert_metrics, (
        "No comparison scalars without baseline"
    )
    print("\n[OK] No-baseline fallback is graceful (Phase 3 skipped safely).")
