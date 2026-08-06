import time
import igraph
import numpy as np

# Mocking the pipeline
print("Creating mock graph...")
baseline = igraph.Graph.Erdos_Renyi(n=130000, m=4000000)

mask = np.ones(4000000, dtype=bool)
# mask[0] = False  # Miss 1 edge

print("Starting _build_temp_graph equivalent")
t0 = time.perf_counter()

active_edge_indices = [
    i for i, active in enumerate(mask) if active
]
t1 = time.perf_counter()
print(f"active_edge_indices: {t1-t0:.3f}s")

temp_graph = baseline.subgraph_edges(
    active_edge_indices, delete_vertices=False
)
t2 = time.perf_counter()
print(f"subgraph_edges: {t2-t1:.3f}s")

baseline_to_subgraph = {
    b_idx: s_idx
    for s_idx, b_idx in enumerate(active_edge_indices)
}
t3 = time.perf_counter()
print(f"baseline_to_subgraph dict: {t3-t2:.3f}s")

for attr in baseline.attributes():
    temp_graph[attr] = baseline[attr]
temp_graph["edge_count"] = temp_graph.ecount()
temp_graph["node_count"] = temp_graph.vcount()

t4 = time.perf_counter()
print(f"Total time: {t4-t0:.3f}s")

