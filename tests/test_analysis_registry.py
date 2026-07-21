import pytest
from modules.graph_analyses.analysis_registry import AnalysisRegistry
from modules.graph_analyses.exceptions import RegistryError
from tests.dummy_modules.dummy_analysis import DummyAnalysis
from modules.preprocessing import preprocess_graph
import igraph

def test_analysis_registry():
    registry = AnalysisRegistry()
    
    registry.register(DummyAnalysis)
    assert DummyAnalysis.NAME in registry.list_names()
    
    analysis = registry.instantiate(DummyAnalysis.NAME)
    assert isinstance(analysis, DummyAnalysis)
    
    with pytest.raises(RegistryError):
        registry.register(DummyAnalysis) # duplicate
        
def test_analysis_execution():
    analysis = DummyAnalysis()
    
    g = igraph.Graph(directed=True)
    g.add_vertices(2)
    g.add_edges([(0,1)])
    g["dataset_name"] = "test"
    prepared = preprocess_graph(g)
    
    result = analysis.execute(prepared)
    assert result.status.value == "SUCCESS"
    assert result.metrics["nodes"] == 2
    assert result.metrics["edges"] == 1

