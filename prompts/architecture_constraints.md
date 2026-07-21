# Architectural Constraints

Every implementation prompt must obey these strict rules. Violating these rules corrupts the framework.

1. **Notebook Boundaries**: Notebooks must never perform graph operations. They only configure and orchestrate.
2. **Experiment Runner**: The `ExperimentRunner` orchestrates the workflow. Do not add biological logic here.
3. **Preprocessing Isolation**: Preprocessing computes features only. It does not alter the underlying topological graph structure or remove edges.
4. **Error Models Isolation**: Error models perform perturbations only. They must return an `ErrorResult` (edge mask), and never modify the baseline `PreparedGraph`.
5. **Statistics Isolation**: The `StatisticsEngine` performs aggregation only. Do not put graph metrics here.
6. **Analysis Isolation**: Graph analyses must compute metrics on the provided graph but must never modify the graph.
7. **No Duplication**: No module should duplicate another module's responsibility. Reuse existing registries and engines.
8. **Immutability**: Runtime configurations and baseline graphs must remain immutable.
