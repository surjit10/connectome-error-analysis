import pandas as pd
import numpy as np
import os
import time
import json
import psutil

start_time = time.time()
mem_start = psutil.Process().memory_info().rss / (1024 * 1024)

# Load data
print("Loading data...")
df = pd.read_csv('research_data/raw/BANC_v888/connections_princeton.csv.gz')
neurons = pd.read_csv('research_data/raw/BANC_v888/neurons.csv.gz')

print(f"Data loaded in {time.time() - start_time:.2f} seconds")

# Part 1, 2, 3, 4: Neuron-level statistics
# We need to treat pre and post independently, then aggregate
# Outgoing edges (neuron is pre)
out_stats = df.groupby('pre_root_id').agg(
    out_edges=('post_root_id', 'count'),
    out_partners=('post_root_id', 'nunique'),
    out_synapses=('syn_count', 'sum'),
    out_neuropils=('neuropil', 'nunique')
).reset_index().rename(columns={'pre_root_id': 'root_id'})

# Incoming edges (neuron is post)
in_stats = df.groupby('post_root_id').agg(
    in_edges=('pre_root_id', 'count'),
    in_partners=('pre_root_id', 'nunique'),
    in_synapses=('syn_count', 'sum'),
    in_neuropils=('neuropil', 'nunique')
).reset_index().rename(columns={'post_root_id': 'root_id'})

# Merge
print("Merging in/out stats...")
n_stats = pd.merge(out_stats, in_stats, on='root_id', how='outer').fillna(0)

n_stats['total_edges'] = n_stats['out_edges'] + n_stats['in_edges']
n_stats['total_synapses'] = n_stats['out_synapses'] + n_stats['in_synapses']

# Total distinct neuropils per neuron
# Stack all pre and post neuropils
all_neuropils = pd.concat([
    df[['pre_root_id', 'neuropil']].rename(columns={'pre_root_id': 'root_id'}),
    df[['post_root_id', 'neuropil']].rename(columns={'post_root_id': 'root_id'})
])

neuropil_counts = all_neuropils.groupby('root_id')['neuropil'].nunique().reset_index(name='total_neuropils')
n_stats = pd.merge(n_stats, neuropil_counts, on='root_id', how='left').fillna(0)

# Total distinct partners per neuron
all_partners = pd.concat([
    df[['pre_root_id', 'post_root_id']].rename(columns={'pre_root_id': 'root_id', 'post_root_id': 'partner'}),
    df[['post_root_id', 'pre_root_id']].rename(columns={'post_root_id': 'root_id', 'pre_root_id': 'partner'})
])
partner_counts = all_partners.groupby('root_id')['partner'].nunique().reset_index(name='total_partners')
n_stats = pd.merge(n_stats, partner_counts, on='root_id', how='left').fillna(0)

# Neuropil Dominance (Fraction of synapses in the largest neuropil)
syn_per_neuropil = all_neuropils.copy()
# We need weights to calculate dominance. 
# Re-create edge stack with syn_count
edges_stack = pd.concat([
    df[['pre_root_id', 'neuropil', 'syn_count']].rename(columns={'pre_root_id': 'root_id'}),
    df[['post_root_id', 'neuropil', 'syn_count']].rename(columns={'post_root_id': 'root_id'})
])
max_syn_per_neuropil = edges_stack.groupby(['root_id', 'neuropil'])['syn_count'].sum().reset_index()
max_syn = max_syn_per_neuropil.groupby('root_id')['syn_count'].max().reset_index(name='max_neuropil_synapses')
n_stats = pd.merge(n_stats, max_syn, on='root_id', how='left').fillna(0)
n_stats['neuropil_dominance'] = np.where(n_stats['total_synapses'] > 0, n_stats['max_neuropil_synapses'] / n_stats['total_synapses'], 0)

# Partners per neuropil
partners_stack = pd.concat([
    df[['pre_root_id', 'neuropil', 'post_root_id']].rename(columns={'pre_root_id': 'root_id', 'post_root_id': 'partner'}),
    df[['post_root_id', 'neuropil', 'pre_root_id']].rename(columns={'post_root_id': 'root_id', 'pre_root_id': 'partner'})
])
partners_per_neuropil = partners_stack.groupby(['root_id', 'neuropil'])['partner'].nunique().reset_index()
mean_partners_per_neuropil = partners_per_neuropil.groupby('root_id')['partner'].mean().reset_index(name='mean_partners_per_neuropil')
n_stats = pd.merge(n_stats, mean_partners_per_neuropil, on='root_id', how='left').fillna(0)

# Part 5: Feature Correlations
corr_cols = ['total_synapses', 'total_partners', 'total_neuropils', 'in_edges', 'out_edges']
corr_matrix = n_stats[corr_cols].corr()

# Extract community labels
community_sample = neurons.head(10).to_dict(orient='records')
community_columns = list(neurons.columns)

# Write results to json
results = {
    "total_neurons": len(n_stats),
    "p1_neuropils": {
        "pct_1_neuropil": float(np.mean(n_stats['total_neuropils'] == 1) * 100),
        "pct_multi_neuropil": float(np.mean(n_stats['total_neuropils'] > 1) * 100),
        "mean": float(n_stats['total_neuropils'].mean()),
        "median": float(n_stats['total_neuropils'].median()),
        "max": float(n_stats['total_neuropils'].max()),
        "p95": float(np.percentile(n_stats['total_neuropils'], 95)),
    },
    "p2_balance": {
        "mean_dominance": float(n_stats['neuropil_dominance'].mean()),
        "median_dominance": float(n_stats['neuropil_dominance'].median()),
        "pct_highly_dominant_90": float(np.mean(n_stats['neuropil_dominance'] > 0.90) * 100)
    },
    "p3_partners": {
        "mean_partners_total": float(n_stats['total_partners'].mean()),
        "mean_partners_per_neuropil_overall": float(partners_per_neuropil['partner'].mean()),
        "median_partners_per_neuropil_overall": float(partners_per_neuropil['partner'].median()),
        "max_partners_per_neuropil_overall": float(partners_per_neuropil['partner'].max())
    },
    "p4_in_out": {
        "mean_in_neuropils": float(n_stats['in_neuropils'].mean()),
        "mean_out_neuropils": float(n_stats['out_neuropils'].mean()),
        "polarized_pct": float(np.mean((n_stats['in_neuropils'] == 0) | (n_stats['out_neuropils'] == 0)) * 100)
    },
    "p5_correlation": corr_matrix.to_dict(),
    "p6_small": {
        "partners_lt_2": float(np.mean(n_stats['total_partners'] < 2) * 100),
        "partners_lt_5": float(np.mean(n_stats['total_partners'] < 5) * 100),
        "partners_lt_10": float(np.mean(n_stats['total_partners'] < 10) * 100),
        "neuropils_eq_1": float(np.mean(n_stats['total_neuropils'] == 1) * 100)
    },
    "p7_coherence": {
        # Rough measure: Are partners grouped into neuropils?
        # A partner can be in multiple neuropils, but generally, if avg partners/neuropil is high, there is coherence.
        "partner_neuropil_ratio": float(np.mean(n_stats['total_partners'] / n_stats['total_neuropils'].clip(lower=1)))
    },
    "p8_sampling": {
        "top_5pct_neurons": int(0.05 * len(n_stats)),
        "top_10pct_neurons": int(0.10 * len(n_stats)),
    },
    "p9_cost": {
        "runtime_seconds": float(time.time() - start_time),
        "memory_mb": float(psutil.Process().memory_info().rss / (1024 * 1024) - mem_start)
    },
    "community_cols": community_columns,
    "community_sample": community_sample
}

os.makedirs('analysis', exist_ok=True)
with open('analysis/em4_stats.json', 'w') as f:
    json.dump(results, f, indent=2)

print("Done. Wrote to analysis/em4_stats.json")
