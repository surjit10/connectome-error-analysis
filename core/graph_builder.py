"""
Phase 005 – Graph Builder
=========================
Converts a FlyWireDataset (produced by Phase 004) into an igraph.Graph
while preserving all biological information exactly as loaded.

Backend: python-igraph (replaces NetworkX).  igraph stores adjacency in
contiguous C arrays, giving dramatically lower RAM usage and faster traversal
than NetworkX's dict-of-dicts representation.

Biological ID contract:
    igraph assigns internal integer vertex indices (0..N-1).
    The original FlyWire root_id values are stored as the vertex attribute
    "root_id" and NEVER modified, downcast, or remapped.
    A mapping dict  igraph_index → root_id  is attached to graph["id_map"]
    and  root_id → igraph_index  to graph["id_to_idx"]  so that every
    downstream component can convert between the two spaces without ambiguity.

This module is the central graph contract of the framework.
Every downstream component (Preprocessing, Analysis, Error Framework,
Experiment Runner) consumes the graph produced here.
"""

import igraph
import polars as pl

from core.data_loader import FlyWireDataset


class GraphBuilderError(Exception):
    """Raised when the dataset cannot be converted to a graph."""


class GraphBuilder:
    """Converts a FlyWireDataset into an igraph.Graph (directed).

    Responsibilities:
        - Validate that required tables and identifier columns are present.
        - Create one vertex per neuron with all available attributes.
        - Create one directed edge per connection with all available attributes.
        - Store biological ID ↔ igraph-index mappings in graph attributes.
        - Attach dataset-level metadata in graph attributes.

    This class does NOT compute metrics, preprocess data, apply
    perturbations, or perform any biological analysis.

    Example::
        >>> builder = GraphBuilder()
        >>> graph = builder.build(dataset)
    """

    # Column that uniquely identifies each neuron.
    _NODE_ID_COL: str = "root_id"

    # Columns that define a directed edge.
    _EDGE_SRC_COL: str = "pre_root_id"
    _EDGE_DST_COL: str = "post_root_id"

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def build(self, dataset: FlyWireDataset) -> igraph.Graph:
        """Build and return a directed igraph.Graph from *dataset*.

        Args:
            dataset: A :class:`~core.data_loader.FlyWireDataset` backed by
                Polars DataFrames.  Both ``neurons`` and ``connections`` tables
                must be present and non-empty.

        Returns:
            A directed :class:`igraph.Graph` whose vertices represent neurons
            and whose edges represent directed synaptic connections.
            All neuron columns are stored as vertex attributes.
            All connection columns (except endpoint identifiers) are stored
            as edge attributes.
            Graph-level metadata is stored as graph attributes.

        Raises:
            GraphBuilderError: If the dataset is structurally invalid.
        """
        self._validate_dataset(dataset)

        graph = igraph.Graph(directed=True)
        id_to_idx = self._add_vertices(graph, dataset.neurons)
        self._add_edges(graph, dataset.connections, id_to_idx)
        self._attach_metadata(graph, dataset, id_to_idx)

        return graph

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _validate_dataset(self, dataset: FlyWireDataset) -> None:
        """Raise GraphBuilderError if *dataset* is not usable."""
        if not isinstance(dataset, FlyWireDataset):
            raise GraphBuilderError(
                f"Expected FlyWireDataset, got {type(dataset).__name__}."
            )
        if dataset.neurons is None or dataset.neurons.is_empty():
            raise GraphBuilderError(
                f"Dataset '{dataset.name}': neurons table is missing or empty."
            )
        if dataset.connections is None or dataset.connections.is_empty():
            raise GraphBuilderError(
                f"Dataset '{dataset.name}': connections table is missing or empty."
            )
        if self._NODE_ID_COL not in dataset.neurons.columns:
            raise GraphBuilderError(
                f"Dataset '{dataset.name}': neurons table missing required "
                f"column '{self._NODE_ID_COL}'."
            )
        for col in (self._EDGE_SRC_COL, self._EDGE_DST_COL):
            if col not in dataset.connections.columns:
                raise GraphBuilderError(
                    f"Dataset '{dataset.name}': connections table missing "
                    f"required column '{col}'."
                )

    def _add_vertices(
        self, graph: igraph.Graph, neurons: pl.DataFrame
    ) -> dict:
        """Insert every neuron as a vertex with its attributes.

        The ``root_id`` column value becomes vertex attribute "root_id".
        Every remaining column is attached as a vertex attribute under the
        same name.  igraph integer vertex indices are assigned sequentially
        (0, 1, 2, …) — the mapping back to biological IDs is preserved via
        the returned dict and graph attributes.

        Args:
            graph:   The igraph.Graph to populate.
            neurons: Normalised neuron Polars DataFrame from the dataset.

        Returns:
            id_to_idx: dict mapping root_id → igraph vertex index (int).
        """
        n = len(neurons)
        graph.add_vertices(n)

        attr_cols = [c for c in neurons.columns if c != self._NODE_ID_COL]

        # root_id column — must exist (validated above).
        root_ids = neurons[self._NODE_ID_COL].to_list()
        graph.vs["root_id"] = root_ids

        # All other neuron columns as vertex attributes.
        for col in attr_cols:
            graph.vs[col] = neurons[col].to_list()

        # Build bidirectional ID mappings.
        id_to_idx: dict = {rid: idx for idx, rid in enumerate(root_ids)}
        return id_to_idx

    def _add_edges(
        self,
        graph: igraph.Graph,
        connections: pl.DataFrame,
        id_to_idx: dict,
    ) -> None:
        """Insert every connection as a directed edge with its attributes.

        Edge direction: pre_root_id → post_root_id (matching the dataset).
        Every remaining column (e.g. neuropil, syn_count, nt_type) is stored
        as an edge attribute.

        Edges whose endpoints are not present in id_to_idx (i.e., the neuron
        was not in the neurons table) are skipped with a count stored in
        graph["skipped_edges"].

        Args:
            graph:       The igraph.Graph to populate.
            connections: Normalised connections Polars DataFrame.
            id_to_idx:   Mapping root_id → igraph vertex index.
        """
        attr_cols = [
            c for c in connections.columns
            if c not in (self._EDGE_SRC_COL, self._EDGE_DST_COL)
        ]

        src_col = connections[self._EDGE_SRC_COL].to_list()
        dst_col = connections[self._EDGE_DST_COL].to_list()

        edge_list = []
        attr_data: dict = {col: [] for col in attr_cols}
        skipped = 0

        attr_columns_data = {col: connections[col].to_list() for col in attr_cols}

        for i, (src_id, dst_id) in enumerate(zip(src_col, dst_col)):
            src_idx = id_to_idx.get(src_id)
            dst_idx = id_to_idx.get(dst_id)
            if src_idx is None or dst_idx is None:
                skipped += 1
                continue
            edge_list.append((src_idx, dst_idx))
            for col in attr_cols:
                attr_data[col].append(attr_columns_data[col][i])

        graph.add_edges(edge_list)

        # Attach edge attributes.
        for col in attr_cols:
            graph.es[col] = attr_data[col]

        if skipped:
            graph["skipped_edges"] = skipped

    def _attach_metadata(
        self,
        graph: igraph.Graph,
        dataset: FlyWireDataset,
        id_to_idx: dict,
    ) -> None:
        """Store dataset-level metadata and ID mappings in graph attributes.

        Args:
            graph:     The graph to annotate.
            dataset:   Source dataset whose metadata to preserve.
            id_to_idx: root_id → igraph vertex index mapping.
        """
        graph["dataset_name"] = dataset.name
        graph["node_count"] = graph.vcount()
        graph["edge_count"] = graph.ecount()
        # Bidirectional ID mapping for downstream components.
        graph["id_to_idx"] = id_to_idx
        graph["id_map"] = {idx: rid for rid, idx in id_to_idx.items()}
