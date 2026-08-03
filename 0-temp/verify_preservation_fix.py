"""Verify the symmetric preservation fix against real stored results.

Recomputes preservation with the OLD formula (min(ratio,1)*100) and the NEW
symmetric formula for every (rate, metric) row in the stored EM1/EM2/EM3
presentation summary CSVs, then prints a compact before/after diff.

Also empirically checks whether igraph's subgraph_edges() renumbers edge
indices (relevant to the weight_updates remapping concern).
"""
import csv
import sys
from pathlib import Path

import igraph

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from presentation.preservation_config import (
    calculate_preservation,
    higher_is_better,
    is_preservation_metric,
)

ROOTS = {
    "EM1": Path("/home/surjit/Desktop/flywire/v1/dataset/error-1/results/BANC/missed_synapses/missedsynapses/BANC"),
    "EM2": Path("/home/surjit/Desktop/flywire/v1/dataset/error-2/results/BANC/false_synapses/falsesynapses/BANC"),
    "EM3": Path("/home/surjit/Desktop/flywire/v1/dataset/error-3/results/BANC/synapse_count_measurement"),
}

# Find the actual presentation root per model (error_*/summary.csv folders)
def find_summary_files(root: Path):
    if not root.exists():
        return []
    return sorted(root.glob("error_*/summary.csv"))


def old_preservation(baseline, perturbed, hib):
    if baseline == 0:
        return 100.0 if perturbed == 0 else 0.0
    ratio = perturbed / baseline if hib else baseline / perturbed
    return min(ratio, 1.0) * 100.0


def load_rows(path: Path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                b = float(r["baseline_mean"])
                m = float(r["mean"])
            except (KeyError, ValueError):
                continue
            rows.append((r["analysis"], r["metric"], b, m))
    return rows


def main():
    print("=" * 100)
    print("PART A — Preservation recomputation (old clamp vs new symmetric)")
    print("=" * 100)
    for model, root in ROOTS.items():
        files = find_summary_files(root)
        if not files:
            print(f"\n[{model}] no error_*/summary.csv found under {root}")
            continue
        print(f"\n--- {model} ---")
        changed = 0
        for sf in files:
            rate_label = sf.parent.name
            for a, m, b, p in load_rows(sf):
                key = f"{a}.{m}"
                if not is_preservation_metric(key):
                    continue
                hib = higher_is_better(key)
                old = old_preservation(b, p, hib)
                new = calculate_preservation(b, p, higher_is_better=hib)
                if abs(old - new) > 1e-9:
                    changed += 1
                    print(f"  {rate_label:>10} {key:<45} base={b:>14,.2f} pert={p:>14,.2f}  "
                          f"old={old:7.4f}%  new={new:7.4f}%")
        print(f"  [{model}] rows whose preservation changed: {changed}")

    print()
    print("=" * 100)
    print("PART B — igraph subgraph_edges() edge-index renumbering check")
    print("=" * 100)
    g = igraph.Graph(n=5)
    g.add_edges([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])
    g.es["syn_count"] = [10, 20, 30, 40, 50]
    mask = [True, False, True, True, False]  # keep baseline edges 0, 2, 3
    active = [i for i, a in enumerate(mask) if a]
    sg = g.subgraph_edges(active, delete_vertices=False)
    print(f"  baseline edge syn_count:      {g.es['syn_count']}")
    print(f"  mask (True=keep):             {mask}")
    print(f"  active baseline indices:      {active}")
    print(f"  subgraph edge syn_count:      {sg.es['syn_count']}")
    print(f"  subgraph edge indices map to: {list(range(sg.ecount()))} -> baseline {active}")
    # Simulate weight_updates keyed by BASELINE index (what EM1/EM3 produce)
    # and applied naively by baseline index (what _build_temp_graph does for EM3).
    weight_updates = {0: 99, 2: 88}
    for edge_idx, new_weight in weight_updates.items():
        if edge_idx < sg.ecount():
            sg.es[edge_idx]["syn_count"] = new_weight
    print(f"  after naive baseline-indexed weight update: {sg.es['syn_count']}")
    print(f"  NOTE: baseline edge 0 -> subgraph idx 0 (OK), baseline edge 2 -> subgraph idx 2,")
    print(f"        but baseline edge 3 (kept) sits at subgraph idx 2, so idx-2 update hits the")
    print(f"        WRONG edge whenever edges were removed before it.")


if __name__ == "__main__":
    main()
