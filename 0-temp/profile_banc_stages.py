"""Throwaway profiling script — analysis only, not part of the framework.

Times each stage of the EM1 pipeline on the real BANC graph to localize
the stall reported after the banner is printed.
"""
import time
import warnings
warnings.filterwarnings("ignore")

def t(label):
    print(f"  -- {label}: done", flush=True)

# ── Stage 1: dataset load ────────────────────────────────────────────────
t0 = time.perf_counter()
from core.data_loader import load_dataset
ds = load_dataset("BANC", "research_data/raw", configs_root="configs/")
print(f"[1] load_dataset        : {time.perf_counter()-t0:7.2f}s  ({len(ds.connections)} rows)", flush=True)

# ── Stage 2: graph build ─────────────────────────────────────────────────
t0 = time.perf_counter()
from core.graph_builder import GraphBuilder
g = GraphBuilder().build(ds)
print(f"[2] graph_build         : {time.perf_counter()-t0:7.2f}s  ({g.vcount()} nodes, {g.ecount()} edges)", flush=True)
del ds

# ── Stage 3: baseline preprocess (notebook feature config) ───────────────
t0 = time.perf_counter()
from modules.preprocessing import preprocess_graph
pp_cfg = {"features": {"degree": True, "synapse_counts": True}}
prepared = preprocess_graph(g, feature_config=pp_cfg["features"])
print(f"[3] preprocess (all)    : {time.perf_counter()-t0:7.2f}s", flush=True)

# ── Stage 3b: extract_biological_features alone ──────────────────────────
t0 = time.perf_counter()
from modules.preprocessing.missed_synapses.biological_features import extract_biological_features
ef = extract_biological_features(prepared)
print(f"[3b] bio_features        : {time.perf_counter()-t0:7.2f}s  ({len(ef.features)} rows)", flush=True)
del ef

# ── Stage 4: subgraph_edges full copy (0% mask = all edges active) ───────
t0 = time.perf_counter()
mask = [True] * g.ecount()
active = [i for i, m in enumerate(mask) if m]
sub = g.subgraph_edges(active, delete_vertices=False)
print(f"[4] subgraph_edges copy : {time.perf_counter()-t0:7.2f}s  ({sub.ecount()} edges)", flush=True)

# ── Stage 5: preprocess on temp graph (features all False) ───────────────
t0 = time.perf_counter()
off = {"indegree": False, "outdegree": False, "total_degree": False,
       "pagerank": False, "reciprocal_ratio": False, "hub_neighbor_count": False,
       "two_hop_size": False}
tmp_prep = preprocess_graph(sub, feature_config=off)
print(f"[5] preprocess (off)    : {time.perf_counter()-t0:7.2f}s", flush=True)
del sub, tmp_prep, prepared

# ── Stage 6: pagerank analysis (weighted, syn_count) ─────────────────────
t0 = time.perf_counter()
w = g.pagerank(weights="syn_count", damping=0.85)
print(f"[6] weighted pagerank   : {time.perf_counter()-t0:7.2f}s", flush=True)
del w

# ── Stage 7: connected components (weak + strong) ────────────────────────
t0 = time.perf_counter()
c = g.components(mode="weak")
print(f"[7] WCC                 : {time.perf_counter()-t0:7.2f}s", flush=True)
del c
t0 = time.perf_counter()
c = g.components(mode="strong")
print(f"[7b] SCC                 : {time.perf_counter()-t0:7.2f}s", flush=True)
del c

# ── Stage 8: assortativity + reciprocity ─────────────────────────────────
t0 = time.perf_counter()
a = g.assortativity_degree(directed=True)
print(f"[8] assortativity       : {time.perf_counter()-t0:7.2f}s", flush=True)
t0 = time.perf_counter()
r = g.reciprocity()
print(f"[8b] reciprocity         : {time.perf_counter()-t0:7.2f}s", flush=True)

print("PROFILE COMPLETE", flush=True)
