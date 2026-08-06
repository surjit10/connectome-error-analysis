import time, igraph

g = igraph.Graph.Erdos_Renyi(n=130000, m=4000000, directed=True)

# Test copy
g_copy = g.copy()
t0 = time.perf_counter()
x = sum(1 for e in g_copy.es if g_copy.are_adjacent(e.target, e.source))
print(f"copy.are_adjacent: {time.perf_counter()-t0:.3f}s")

# Test subgraph_edges
g_sub = g.subgraph_edges(list(range(g.ecount())), delete_vertices=False)
t0 = time.perf_counter()
y = sum(1 for e in g_sub.es if g_sub.are_adjacent(e.target, e.source))
print(f"subgraph_edges.are_adjacent: {time.perf_counter()-t0:.3f}s")

