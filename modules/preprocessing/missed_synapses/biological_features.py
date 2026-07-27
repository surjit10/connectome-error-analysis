"""
Phase 012 — Biological Feature Extraction
==========================================
Extracts the precise edge-level biological features required for downstream
vulnerability scoring without mutating the original graph.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
import polars as pl
from typing import Any

from modules.preprocessing.common.prepared_graph import PreparedGraph

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class EdgeFeatureTable:
    """
    Immutable edge feature representation.
    """
    features: pl.DataFrame
    
    def __post_init__(self) -> None:
        required_cols = [
            "pre_root", "post_root", "syn_count",
            "source_degree", "target_degree",
            "reciprocal", "source_pagerank", "target_pagerank"
        ]
        missing = [c for c in required_cols if c not in self.features.columns]
        if missing:
            raise ValueError(f"Missing required columns in EdgeFeatureTable: {missing}")
        if sum(self.features.null_count().row(0)) > 0:
            raise ValueError("EdgeFeatureTable contains missing (NaN/null) values.")
        logger.info(f"[BiologicalFeatures] EdgeFeatureTable validated successfully with {len(self.features)} edges.")

def extract_biological_features(prepared: PreparedGraph) -> EdgeFeatureTable:
    """
    Extracts biological features for every edge in the connectome.
    Consumes pre-computed node baseline features from Phase 006 to avoid recomputation.
    """
    logger.info("[BiologicalFeatures] Starting edge feature extraction.")
    graph = prepared.graph
    
    if graph.ecount() == 0:
        logger.warning("[BiologicalFeatures] Graph has 0 edges.")
        return EdgeFeatureTable(features=pl.DataFrame({
            "pre_root": [], "post_root": [], "syn_count": [],
            "source_degree": [], "target_degree": [],
            "reciprocal": [], "source_pagerank": [], "target_pagerank": []
        }))

    sources = []
    targets = []
    syn_counts = []
    reciprocals = []
    
    # Construct base edge attributes
    has_weight = "weight" in graph.edge_attributes()
    edge_weights = graph.es["weight"] if has_weight else [1] * graph.ecount()
    
    for e_idx, e in enumerate(graph.es):
        s, t = e.source, e.target
        sources.append(s)
        targets.append(t)
        syn_counts.append(edge_weights[e_idx])
        reciprocals.append(1 if graph.are_adjacent(t, s) else 0)
        
    df = pl.DataFrame({
        "pre_root": sources,
        "post_root": targets,
        "syn_count": syn_counts,
        "reciprocal": reciprocals
    })
    
    # Fetch pre-computed node features
    vcount = graph.vcount()
    total_degree = prepared.baseline_features.get("total_degree", [0] * vcount)
    pagerank = prepared.baseline_features.get("pagerank", [0.0] * vcount)
    
    node_df = pl.DataFrame({
        "node_id": range(vcount),
        "degree": total_degree,
        "pagerank": pagerank
    })
    
    # Map source features
    df = df.join(node_df, left_on="pre_root", right_on="node_id", how="left").rename({
        "degree": "source_degree",
        "pagerank": "source_pagerank"
    })
    
    # Map target features
    df = df.join(node_df, left_on="post_root", right_on="node_id", how="left").rename({
        "degree": "target_degree",
        "pagerank": "target_pagerank"
    })
    
    logger.info(f"[BiologicalFeatures] Extracted features for {len(df)} edges. Extraction completed.")
    return EdgeFeatureTable(features=df)
