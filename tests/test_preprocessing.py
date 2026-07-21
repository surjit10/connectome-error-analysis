import pytest
from core.graph_builder import GraphBuilder
from core.data_loader import load_dataset
from modules.preprocessing import preprocess_graph, PreparedGraph
import igraph

def test_preprocessing_pipeline(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    dataset = load_dataset(name, dataset_root, configs_root=temp_configs)
    graph = GraphBuilder().build(dataset)
    
    prepared = preprocess_graph(graph)
    
    assert isinstance(prepared, PreparedGraph)
    assert prepared.is_valid
    
    # Check baseline features
    features = prepared.baseline_features
    assert "indegree" in features
    assert "outdegree" in features
    assert "total_degree" in features
    assert "pagerank" in features
    assert "reciprocal_ratio" in features
    assert "hub_neighbor_count" in features
    assert "two_hop_size" in features
    
    # Verify graph is not copied
    assert prepared.graph is graph
