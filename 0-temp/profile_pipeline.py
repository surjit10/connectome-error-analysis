import sys, time
import igraph
from core.experiment_runner import ExperimentRunner, ExperimentConfig

class MockPrepared:
    def __init__(self, g):
        self.graph = g

baseline = igraph.Graph.Erdos_Renyi(n=130000, m=4000000)
for v in baseline.vs:
    v["top_region"] = "LAL"
for e in baseline.es:
    e["syn_count"] = 1
    e["pre_rid"] = "a"
    e["post_rid"] = "b"

baseline["dataset_name"] = "BANC"

from modules.preprocessing.common.pipeline import preprocess_graph
t0 = time.perf_counter()
prep = preprocess_graph(baseline, feature_config={'degree': True, 'synapse_counts': True})
t1 = time.perf_counter()
print(f"preprocess_graph took {t1-t0:.3f}s")

