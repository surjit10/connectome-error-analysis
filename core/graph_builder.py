"""
Phase 005 – Graph Builder
=========================
Converts a FlyWireDataset (produced by Phase 004) into a NetworkX DiGraph
while preserving all biological information exactly as loaded.

This module is the central graph contract of the framework.
Every downstream component (Preprocessing, Analysis, Error Framework,
Experiment Runner) consumes the graph produced here.
"""

import networkx as nx
import pandas as pd

from core.data_loader import FlyWireDataset


class GraphBuilderError(Exception):
    """Raised when the dataset cannot be converted to a graph."""


class GraphBuilder:
    """Converts a FlyWireDataset into a NetworkX DiGraph.

    Responsibilities:
        - Validate that required tables and identifier columns are present.
        - Create one node per neuron with all available attributes.
        - Create one directed edge per connection with all available attributes.
        - Store dataset-level metadata in ``graph.graph``.

    This class does **not** compute metrics, preprocess data, apply
    perturbations, or perform any biological analysis.

    Example:
        >>> builder = GraphBuilder()
        >>> graph = builder.build(dataset)
    """

    # Column that uniquely identifies each neuron.
    _NODE_ID_COL: str = "root_id"

    # Columns that define a directed edge (consumed as node IDs, not attributes).
    _EDGE_SRC_COL: str = "pre_root_id"
    _EDGE_DST_COL: str = "post_root_id"

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def build(self, dataset: FlyWireDataset) -> nx.DiGraph:
        """Build and return a directed graph from *dataset*.

        Args:
            dataset: A :class:`~core.data_loader.FlyWireDataset` produced by
                Phase 004.  Both ``neurons`` and ``connections`` tables must
                be present and non-empty.

        Returns:
            A :class:`networkx.DiGraph` whose nodes are neuron IDs and whose
            edges are directed synaptic connections.  All neuron columns are
            stored as node attributes; all connection columns (except the
            endpoint identifiers) are stored as edge attributes.  Dataset-
            level metadata is stored in ``graph.graph``.

        Raises:
            GraphBuilderError: If the dataset is structurally invalid.
        """
        self._validate_dataset(dataset)

        graph = self._create_graph()
        self._add_nodes(graph, dataset.neurons)
        self._add_edges(graph, dataset.connections)
        self._attach_metadata(graph, dataset)

        return graph

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _validate_dataset(self, dataset: FlyWireDataset) -> None:
        """Raise :class:`GraphBuilderError` if *dataset* is not usable.

        Args:
            dataset: The dataset to validate.

        Raises:
            GraphBuilderError: On any structural problem.
        """
        if not isinstance(dataset, FlyWireDataset):
            raise GraphBuilderError(
                f"Expected FlyWireDataset, got {type(dataset).__name__}."
            )
        if dataset.neurons is None or dataset.neurons.empty:
            raise GraphBuilderError(
                f"Dataset '{dataset.name}': neurons table is missing or empty."
            )
        if dataset.connections is None or dataset.connections.empty:
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

    def _create_graph(self) -> nx.DiGraph:
        """Return a new, empty directed graph.

        Returns:
            An empty :class:`networkx.DiGraph`.
        """
        return nx.DiGraph()

    def _add_nodes(self, graph: nx.DiGraph, neurons: pd.DataFrame) -> None:
        """Insert every neuron as a node with its attributes.

        The ``root_id`` column becomes the node ID.  Every remaining column
        is attached as a node attribute under the same name.

        Args:
            graph:   The graph to populate.
            neurons: Normalised neuron DataFrame from the dataset.
        """
        # Columns to carry as node attributes (everything except the ID).
        attr_cols = [c for c in neurons.columns if c != self._NODE_ID_COL]

        node_list = [
            (
                row.root_id,
                {col: getattr(row, col) for col in attr_cols},
            )
            for row in neurons.itertuples(index=False)
        ]

        graph.add_nodes_from(node_list)

    def _add_edges(self, graph: nx.DiGraph, connections: pd.DataFrame) -> None:
        """Insert every connection as a directed edge with its attributes.

        Edge direction follows the dataset exactly: ``pre_root_id`` →
        ``post_root_id``.  Every remaining column (e.g. ``neuropil``,
        ``syn_count``, ``nt_type``) is stored as an edge attribute.

        Args:
            graph:       The graph to populate.
            connections: Normalised connections DataFrame from the dataset.
        """
        attr_cols = [
            c for c in connections.columns
            if c not in (self._EDGE_SRC_COL, self._EDGE_DST_COL)
        ]

        edge_list = [
            (
                row.pre_root_id,
                row.post_root_id,
                {col: getattr(row, col) for col in attr_cols},
            )
            for row in connections.itertuples(index=False)
        ]

        graph.add_edges_from(edge_list)

    def _attach_metadata(
        self, graph: nx.DiGraph, dataset: FlyWireDataset
    ) -> None:
        """Store dataset-level metadata in ``graph.graph``.

        Args:
            graph:   The graph to annotate.
            dataset: Source dataset whose metadata to preserve.
        """
        graph.graph["dataset_name"] = dataset.name
        graph.graph["node_count"] = graph.number_of_nodes()
        graph.graph["edge_count"] = graph.number_of_edges()
