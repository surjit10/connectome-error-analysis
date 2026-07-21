import pytest
from core.graph_builder import GraphBuilder
from core.data_loader import load_dataset
import igraph

def test_graph_builder(temp_configs, temp_dataset):
    dataset_root, name = temp_dataset
    dataset = load_dataset(name, dataset_root, configs_root=temp_configs)
    
    gb = GraphBuilder()
    graph = gb.build(dataset)
    
    assert isinstance(graph, igraph.Graph)
    assert graph.is_directed()
    assert graph.vcount() == 3
    assert graph.ecount() == 3
    
    # Check mappings
    assert "id_to_idx" in graph.attributes()
    assert "id_map" in graph.attributes()
    assert "dataset_name" in graph.attributes()
    
    # Check baseline weights
    assert "syn_count" in graph.edge_attributes()
    
    # Check node metadata
    assert "root_id" in graph.vertex_attributes()
    assert "super_class" in graph.vertex_attributes()
