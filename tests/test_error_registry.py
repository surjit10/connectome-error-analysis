import pytest
from modules.error_models.common.error_registry import ErrorRegistry
from tests.dummy_modules.dummy_error_model import DummyErrorModel
from modules.preprocessing import preprocess_graph
import igraph

def test_error_registry():
    registry = ErrorRegistry()
    
    registry.register(DummyErrorModel)
    assert DummyErrorModel.NAME in registry.list_names()
    
    model = registry.instantiate(DummyErrorModel.NAME)
    assert isinstance(model, DummyErrorModel)
    
def test_error_execution():
    model = DummyErrorModel()
    
    g = igraph.Graph(directed=True)
    g.add_vertices(2)
    g.add_edges([(0,1)])
    g["dataset_name"] = "test"
    prepared = preprocess_graph(g)
    
    result = model.execute(prepared)
    assert result.status.value == "SUCCESS"
    assert result.edge_mask == [True]
    assert result.weight_updates == {}

