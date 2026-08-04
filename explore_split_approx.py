import pandas as pd
import numpy as np
import igraph as ig
import json
import random
import time

print("Loading data...")
df = pd.read_csv('research_data/raw/BANC_v888/connections_princeton.csv.gz')

print("Building graph...")
# Create a directed graph for accurate representation, but we'll convert to undirected for community/component analysis
edges = list(zip(df['pre_root_id'].astype(str), df['post_root_id'].astype(str)))
weights = df['syn_count'].tolist()

# Using igraph
g = ig.Graph.TupleList(edges, directed=False, weights=True)
g.simplify(combine_edges="sum") # Undirected multigraph to simple graph

print(f"Graph has {g.vcount()} nodes and {g.ecount()} edges.")

# Select a sample of neurons with degree between 20 and 200
degrees = np.array(g.degree())
valid_vids = np.where((degrees >= 20) & (degrees <= 200))[0]
np.random.seed(42)
sample_vids = np.random.choice(valid_vids, size=500, replace=False)

stats = {
    'num_components': [],
    'largest_comp_ratio': [],
    'clustering_coeff': [],
    'num_communities': [],
    'largest_community_ratio': [],
    'bridge_edges': []
}

print("Analyzing ego graphs...")
start_time = time.time()
for vid in sample_vids:
    # Get neighbors
    neighbors = g.neighbors(vid)
    # Subgraph of neighbors (excluding the ego node itself)
    sub_g = g.subgraph(neighbors)
    
    # 1. Connected components
    components = sub_g.connected_components()
    stats['num_components'].append(len(components))
    
    if len(components) > 0:
        sizes = components.sizes()
        stats['largest_comp_ratio'].append(max(sizes) / sum(sizes))
    
    # 2. Clustering coefficient (density of ego graph)
    stats['clustering_coeff'].append(sub_g.transitivity_undirected(mode="zero"))
    
    # 3. Community detection (Louvain)
    if sub_g.vcount() > 1 and sub_g.ecount() > 0:
        # Get weight attribute if exists, else None
        wt = 'weight' if 'weight' in sub_g.edge_attributes() else None
        try:
            communities = sub_g.community_multilevel(weights=wt)
            stats['num_communities'].append(len(communities))
            sizes = communities.sizes()
            stats['largest_community_ratio'].append(max(sizes) / sum(sizes))
        except Exception:
            stats['num_communities'].append(1)
            stats['largest_community_ratio'].append(1.0)
    else:
        stats['num_communities'].append(sub_g.vcount())
        stats['largest_community_ratio'].append(1.0)
        
    # 4. Bridge detection in the neighbor graph
    bridges = sub_g.bridges()
    stats['bridge_edges'].append(len(bridges))

print(f"Analysis completed in {time.time() - start_time:.2f}s")

# Aggregate results
results = {
    'components': {
        'mean': np.mean(stats['num_components']),
        'median': np.median(stats['num_components']),
        'pct_multiple': np.mean(np.array(stats['num_components']) > 1) * 100,
        'mean_largest_ratio': np.mean(stats['largest_comp_ratio'])
    },
    'clustering': {
        'mean': np.mean(stats['clustering_coeff']),
        'median': np.median(stats['clustering_coeff'])
    },
    'communities': {
        'mean': np.mean(stats['num_communities']),
        'median': np.median(stats['num_communities']),
        'pct_multiple': np.mean(np.array(stats['num_communities']) > 1) * 100,
        'mean_largest_ratio': np.mean(stats['largest_community_ratio'])
    },
    'bridges': {
        'mean_per_ego': np.mean(stats['bridge_edges']),
        'pct_has_bridges': np.mean(np.array(stats['bridge_edges']) > 0) * 100
    }
}

print(json.dumps(results, indent=2))
with open('analysis/split_approx_results.json', 'w') as f:
    json.dump(results, f, indent=2)

