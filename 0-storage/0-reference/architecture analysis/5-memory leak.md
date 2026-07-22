# FlyWire Connectome Framework — Memory Leak Analysis Report

> **Task**: Identify the root cause of Kaggle kernel crashes after multiple experiment trials.
> **Scope**: Investigation only. No code was modified.
> **Evidence Base**: Direct source inspection of all priority files.

---

## Executive Summary

The framework is architecturally sound in its design intent — it avoids `graph.copy()`, uses edge masks instead of graph copies, and explicitly deletes the temporary perturbed graph. **However, five concrete, evidence-backed memory accumulation issues exist**, the most critical of which is that every `ExperimentResult` object — containing the full `PreparedGraph`, the full `ErrorResult` edge mask, and full per-node vectors — is permanently stored in the notebook's `results_per_rate` dict and never freed between trials.

The **root cause** of kernel death is the combination of:
1. **All `ExperimentResult` objects are retained for the entire session lifetime** (notebook Cell 8, `results_per_rate[err_rate].append(res)`).
2. Each `ExperimentResult` holds a live reference to a **full `PreparedGraph`** (containing an `igraph.Graph`, all lookup dictionaries, two full adjacency maps, per-edge attribute dicts, and a `Polars DataFrame` of biological features).
3. The `PreparedGraph` is attached to the `ExperimentResult` as `result.prepared_graph` and is **never cleared** after the pipeline finishes.
4. **Vector statistics** (full per-node PageRank, degree, betweenness, closeness arrays) are deep-copied into `ExperimentStatistics.vector_data` every time `StatisticsEngine.aggregate()` is called inside `_step_export()`.
5. The **`GraphLookup`** object duplicates the entire graph topology as Python dicts, roughly doubling the in-memory footprint of every node's adjacency list.

With 5 error rates × 5 seeds = **25 trials**, 25 copies of all the above remain live simultaneously.

---

## Memory Lifecycle Diagram

```
Trial N begins
│
├── load_dataset()          → FlyWireDataset (large Polars DataFrames)
│       del dataset          ✓ Released after graph build (line 372)
│
├── GraphBuilder.build()    → igraph.Graph (baseline)
│       ↓
├── preprocess_graph()      → PreparedGraph
│       │   .graph            igraph.Graph (baseline) — large
│       │   .lookup            GraphLookup — DUPLICATED adjacency dicts
│       │   .baseline_features list[float] per-node vectors (indegree, outdegree, pagerank, hub, 2hop)
│       │   .edge_features     EdgeFeatureTable (Polars DataFrame, all edges)
│       │   .edge_vulnerability EdgeVulnerabilityTable (Polars DataFrame, added in Step 3.6)
│       │   .calibrated_probs  CalibratedProbabilityTable (Polars DataFrame, added in Step 3.7)
│
├── result.prepared_graph = prepared   ← ⚠ PERMANENT REFERENCE SET HERE (line 379)
│
├── VulnerabilityModel.compute_scores()   → EdgeVulnerabilityTable (Polars DataFrame)
│       setattr(prepared, "edge_vulnerability", vuln_table)
│
├── ProbabilityCalibrator.calibrate()     → CalibratedProbabilityTable (Polars DataFrame)
│       setattr(prepared, "calibrated_probabilities", calibrated_table)
│
├── MissedSynapsesModel._perturb()
│       → edge_mask: List[bool], len == graph.ecount()   ← stored in ErrorResult
│       → weight_updates: Dict[int, float]               ← stored in ErrorResult
│
├── result.error_result = error_result   ← ⚠ edge_mask list is O(E) memory retained in result
│
├── _build_temp_graph()    → temp_graph (igraph subgraph) + temp_prepared (PreparedGraph)
│
├── Analyses run on temp_prepared ...
│       PageRank:         pagerank_scores list[float], N floats  → stored in AnalysisResult.metrics
│       DegreeDistrib:    in_degrees, out_degrees list[int], 2N ints → stored in AnalysisResult.metrics
│       Centrality:       betweenness, closeness list[float], 2N floats → stored in AnalysisResult.metrics
│
├── del temp_graph, del analysis_target  ✓ Released (lines 524-525)
│
├── result.analysis_results.append(a_result)  ← ⚠ All N-length vectors retained in result
│
├── _step_export()
│       StatisticsEngine().aggregate([result])
│           → copy.deepcopy(metric_val) for every vector  ← ⚠ DEEP COPY of all vectors into ExperimentStatistics
│
├── runner.run() returns result
│
└── results_per_rate[err_rate].append(res)  ← ⚠ RESULT PERMANENTLY RETAINED IN NOTEBOOK DICT
        All of the above objects now survive for the entire kernel session.
```

---

## Files Inspected

| File | Lines | Status |
|---|---|---|
| [experiment_runner.py](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py) | 865 | ✅ Fully inspected |
| [export_manager.py](file:///home/surjit/Desktop/flywire/v1/core/export_manager.py) | 423 | ✅ Fully inspected |
| [statistics_engine.py](file:///home/surjit/Desktop/flywire/v1/core/statistics_engine.py) | 578 | ✅ Fully inspected |
| [evaluator.py](file:///home/surjit/Desktop/flywire/v1/modules/statistical_evaluation/evaluator.py) | 221 | ✅ Fully inspected |
| [vector_comparison.py](file:///home/surjit/Desktop/flywire/v1/modules/statistical_evaluation/vector_comparison.py) | 434 | ✅ Fully inspected |
| [analysis_result.py](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/analysis_result.py) | 138 | ✅ Fully inspected |
| [prepared_graph.py](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/prepared_graph.py) | 158 | ✅ Fully inspected |
| [pipeline.py](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/pipeline.py) | 347 | ✅ Fully inspected |
| [lookup.py](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/lookup.py) | 294 | ✅ Fully inspected |
| [biological_features.py](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/biological_features.py) | 101 | ✅ Fully inspected |
| [error_result.py](file:///home/surjit/Desktop/flywire/v1/modules/error_models/error_result.py) | 156 | ✅ Fully inspected |
| [base_error_model.py](file:///home/surjit/Desktop/flywire/v1/modules/error_models/base_error_model.py) | 240 | ✅ Fully inspected |
| [missed_synapses.py](file:///home/surjit/Desktop/flywire/v1/modules/error_models/missed_synapses.py) | 117 | ✅ Fully inspected |
| [vulnerability.py](file:///home/surjit/Desktop/flywire/v1/modules/error_models/vulnerability.py) | 81 | ✅ Fully inspected |
| [calibration.py](file:///home/surjit/Desktop/flywire/v1/modules/error_models/calibration.py) | 121 | ✅ Fully inspected |
| [network_statistics.py](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/network_statistics.py) | 24 | ✅ Fully inspected |
| [structural.py](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/structural.py) | 35 | ✅ Fully inspected |
| [centrality.py](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/centrality.py) | 24 | ✅ Fully inspected |
| [base_analysis.py](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/base_analysis.py) | 228 | ✅ Fully inspected |
| [experiments_missed_synapses.ipynb](file:///home/surjit/Desktop/flywire/v1/experiments_missed_synapses.ipynb) | 341 | ✅ Fully inspected |

---

## Root Cause Ranking (Most Likely → Least Likely)

### 🔴 CRITICAL — Issue 1: `ExperimentResult.prepared_graph` retains the entire `PreparedGraph` forever

**Location**: [experiment_runner.py, line 379](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L379)

```python
result.prepared_graph = prepared  # line 379 — PERMANENT REFERENCE
```

**Evidence**:

The `ExperimentResult` dataclass ([experiment_runner.py, line 191](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L191)) declares:

```python
prepared_graph: Optional[PreparedGraph] = None
```

The `PreparedGraph` ([prepared_graph.py, lines 105-111](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/prepared_graph.py#L105-L111)) holds:

```python
graph: igraph.Graph          # full baseline graph — nodes + edges + all attributes
validation_report: ValidationReport
metadata: GraphMetadata
lookup: GraphLookup          # massive Python dict structures (see Issue 2)
baseline_features: dict      # per-node vectors: indegree, outdegree, pagerank, hub_count, two_hop
edge_features: EdgeFeatureTable  # Polars DataFrame of all edges × 8 columns
```

Additionally, by the time the runner is done with Step 3.6 and 3.7, the `prepared` object has two dynamically-added attributes:

```python
prepared.edge_vulnerability     # EdgeVulnerabilityTable — Polars DataFrame (all edges)
prepared.calibrated_probabilities  # CalibratedProbabilityTable — Polars DataFrame (all edges)
```

Both are set via `setattr(prepared, ...)` ([experiment_runner.py, lines 410, 449](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L410)) and therefore live inside the `prepared` object which is then assigned to `result.prepared_graph`. **None of these are cleared after the pipeline finishes.**

**Why it accumulates**: In the notebook, Cell 8 does:

```python
results_per_rate[err_rate].append(res)
```

So every `result` object — and therefore every `PreparedGraph`, including the igraph baseline, all lookup dicts, three Polars DataFrames, and five baseline feature arrays — is kept alive inside `results_per_rate` for the entire kernel session. With 25 trials, 25 full `PreparedGraph` objects exist simultaneously.

**Temporary vs. accumulative**: **Accumulative.** Objects are never freed.

**Memory impact**: For a large connectome (e.g., FAFB with ~140k neurons, ~5M edges), each `PreparedGraph` easily occupies 1–3 GB of RAM from:
- igraph.Graph (~hundreds of MB)
- GraphLookup Python dicts (duplicate adjacency → comparable to the igraph.Graph itself)
- Three Polars DataFrames × 5M edges × 8 columns each

25 trials × ~2 GB = **~50 GB total, far exceeding any Kaggle kernel limit**.

**Why it prevents GC**: Python's garbage collector cannot free any of these objects because `results_per_rate` holds a strong reference chain: `dict → list → ExperimentResult → PreparedGraph → igraph.Graph`. Reference count never reaches zero.

---

### 🔴 CRITICAL — Issue 2: `GraphLookup` duplicates the entire graph topology in Python dicts

**Location**: [lookup.py, lines 229-249](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/lookup.py#L229-L249)

```python
adjacency_out: Dict[Any, Dict[Any, Dict[str, Any]]] = {n: {} for n in node_set}
adjacency_in:  Dict[Any, Dict[Any, Dict[str, Any]]] = {n: {} for n in node_set}
edge_attrs:    Dict[tuple, Dict[str, Any]] = {}
edge_weight:   Dict[tuple, Optional[float]] = {}
```

**Evidence**: `build_lookup()` iterates over every edge and creates three nested Python dicts containing full copies of all edge attribute values (`{attr: e[attr] for attr in edge_attr_names}`). For a graph with E edges, this creates:

- `edge_attrs`: E tuples as keys, each mapping to a dict of all edge attributes — **full duplication** of all edge attribute data from igraph into Python heap objects.
- `adjacency_out` + `adjacency_in`: two additional dict-of-dicts indexed by biological root IDs, both referencing the same attribute dicts.

Additionally, `node_attrs` duplicates all vertex attributes for all N nodes. The `successors` and `predecessors` dicts store full lists of neighbour root IDs for every node.

**Memory impact**: For 5M edges with 3 attributes each, this is roughly 5M × (tuple overhead + dict overhead + 3 attribute values) ≈ **hundreds of MB of pure Python object overhead**, in addition to the igraph representation.

**Temporary vs. accumulative**: Since `GraphLookup` is part of `PreparedGraph` which is part of `ExperimentResult` which is stored in `results_per_rate`, this is **accumulative**.

---

### 🔴 HIGH — Issue 3: `ExperimentResult.analysis_results` retains full per-node vector arrays

**Location**: [experiment_runner.py, line 770](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L770)

```python
result.analysis_results.append(a_result)
```

**Evidence**: The analyses store per-node vectors directly in `AnalysisResult.metrics`:

- [network_statistics.py, lines 11-12](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/network_statistics.py#L11): `result.metrics["in_degrees"] = g.indegree()` — `list[int]`, N elements
- [network_statistics.py, lines 11-12](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/network_statistics.py#L12): `result.metrics["out_degrees"] = g.outdegree()` — `list[int]`, N elements
- [network_statistics.py, line 20](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/network_statistics.py#L20): `result.metrics["pagerank_scores"] = g.pagerank(...)` — `list[float]`, N elements
- [centrality.py, lines 14, 19](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/centrality.py#L14): `result.metrics["betweenness"]` — `list[float]`, N elements
- [centrality.py, line 19](file:///home/surjit/Desktop/flywire/v1/modules/graph_analyses/centrality.py#L19): `result.metrics["closeness"]` — `list[float]`, N elements

Per-trial storage: 5 vectors × N elements. For N=140k, this is 5 × 140k × 8 bytes ≈ **5.6 MB per trial**, × 25 trials = **~140 MB**, staying live in `results_per_rate`.

**Temporary vs. accumulative**: **Accumulative** — all retained in `results_per_rate`.

---

### 🟡 HIGH — Issue 4: `StatisticsEngine.aggregate()` deep-copies every vector metric

**Location**: [statistics_engine.py, lines 296-299](file:///home/surjit/Desktop/flywire/v1/core/statistics_engine.py#L296-L299)

```python
vector_collector[name][metric_key].append(
    copy.deepcopy(metric_val)   # ← deep copy of a list[float] of N elements
)
```

**Evidence**: During `_step_export()` ([experiment_runner.py, line 838](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L838)), `StatisticsEngine().aggregate([result])` is called for each trial. This deep-copies every vector metric into `ExperimentStatistics.vector_data`. The `ExperimentStatistics` object is a **local variable** in `_step_export()` and is discarded — so this is not a long-term accumulation inside the framework. However:

1. During the `_step_export()` call, peak RAM is doubled for all vector data.
2. **More importantly**, `StatisticsEngine.aggregate()` is called again in Cell 9 during `StatisticalEvaluator.evaluate()` ([evaluator.py, lines 81-82](file:///home/surjit/Desktop/flywire/v1/modules/statistical_evaluation/evaluator.py#L81-L82)), and here the vectors from all trials in the group are deep-copied simultaneously into `ExperimentStatistics.vector_data`. The resulting `ExperimentStatistics` objects are local to `evaluate()`, but during that call, the peak RAM is substantial.

**Temporary vs. accumulative**: Mostly **temporary** (objects are local vars), but creates very high peak RAM spikes.

**Memory impact**: For a group of 5 perturbed trials with N=140k: 5 metrics × 5 trials × 140k × 8 bytes = **28 MB in one call**, plus deep-copy overhead. Not catastrophic on its own, but combined with Issues 1–3 it pushes the kernel over the limit.

---

### 🟡 MEDIUM — Issue 5: `ErrorResult.edge_mask` retains a full `List[bool]` per trial

**Location**: [experiment_runner.py, line 480](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L480)

```python
result.error_result = error_result
```

**Evidence**: `ErrorResult.edge_mask` is `Optional[List[bool]]` with length equal to graph edge count ([error_result.py, line 89](file:///home/surjit/Desktop/flywire/v1/modules/error_models/error_result.py#L89)). The `missed_synapses.py` model stores `edge_mask.tolist()` ([missed_synapses.py, line 97](file:///home/surjit/Desktop/flywire/v1/modules/error_models/missed_synapses.py#L97)). For E=5M edges, each Python `bool` object is 28 bytes, so a list of 5M bools = **~140 MB** in Python's heap (or ~6 MB if using `array.array`/numpy, but `.tolist()` creates Python objects).

The `ErrorResult` is retained inside `ExperimentResult.error_result`, which is in `results_per_rate`. With 20 non-baseline trials × ~140 MB = **~2.8 GB** from edge masks alone.

**Temporary vs. accumulative**: **Accumulative** — never freed while `results_per_rate` is alive.

> [!NOTE]
> The actual size depends on igraph's edge count for the specific dataset. The `edge_mask.tolist()` call on line 97 of `missed_synapses.py` creates a Python list of Python `bool` objects which is significantly heavier than numpy's bool array.

---

### 🟢 LOW — Issue 6: Three Polars DataFrames attached to each `prepared` object

**Location**: [pipeline.py, line 205-206](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/pipeline.py#L205-L206), [experiment_runner.py, lines 409-410, 448-449](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L409)

Each `PreparedGraph` carries:
- `edge_features` (Phase 012 EdgeFeatureTable): Polars DataFrame, E rows × 8 columns
- `edge_vulnerability` (Phase 013, set via `setattr`): Polars DataFrame, E rows × 9 columns
- `calibrated_probabilities` (Phase 014, set via `setattr`): Polars DataFrame, E rows × 10 columns

Since all three reference the same underlying edge data and Polars uses column-store (Apache Arrow), they share memory segments for repeated columns. Still, three separate DataFrames with E rows each represents a meaningful footprint that is retained alongside the `PreparedGraph`.

**Temporary vs. accumulative**: **Accumulative** (same root cause as Issue 1).

---

## Memory Safety Checklist Results

| Criterion | Status | Notes |
|---|---|---|
| ✓ No unnecessary deep copies | ❌ FAIL | `copy.deepcopy(metric_val)` in statistics_engine.py line 298 |
| ✓ No graph copies retained | ✅ PASS | Architecture correctly avoids graph.copy(); uses edge_mask |
| ✓ No DataFrames stored permanently | ❌ FAIL | 3 Polars DataFrames per trial stored in prepared_graph retained in ExperimentResult |
| ✓ No cached graph objects | ✅ PASS | No global/static graph caches found |
| ✓ No accumulating dictionaries | ❌ FAIL | `results_per_rate` grows unboundedly; `GraphLookup` dicts per trial |
| ✓ No accumulating lists | ❌ FAIL | `results_per_rate[rate]` list grows; `analysis_results` in each ExperimentResult |
| ✓ No static/global storage | ✅ PASS | No global result/graph caches found in framework code |
| ✓ No circular references | ✅ PASS | No obvious cycles detected |
| ✓ No references preventing GC | ❌ FAIL | `results_per_rate` holds strong refs to all PreparedGraph objects |
| ✓ No duplicate vectors | ❌ FAIL | Degree/pagerank computed in both preprocessing (baseline_features) and analyses |
| ✓ No duplicated feature tables | ❌ FAIL | Three overlapping Polars DataFrames on prepared |
| ✓ No duplicated adjacency structures | ❌ FAIL | igraph internal + GraphLookup adjacency_out/in dicts |

---

## Estimated Memory Impact Per Trial

| Object | Approx. Size (per trial, large dataset) | Accumulates? |
|---|---|---|
| igraph.Graph (baseline) | ~200–800 MB | ✅ Yes (via prepared_graph) |
| GraphLookup (Python dicts) | ~100–400 MB | ✅ Yes |
| EdgeFeatureTable (Polars, 8 cols) | ~30–100 MB | ✅ Yes |
| EdgeVulnerabilityTable (Polars, 9 cols) | ~35–110 MB | ✅ Yes |
| CalibratedProbabilityTable (Polars, 10 cols) | ~38–120 MB | ✅ Yes |
| `edge_mask` List[bool] | ~50–200 MB | ✅ Yes |
| baseline_features (5 arrays × N) | ~5–20 MB | ✅ Yes |
| AnalysisResult.metrics (5 vectors × N) | ~5–20 MB | ✅ Yes |
| **Per-trial total (conservative estimate)** | **~450 MB – 1.8 GB** | ✅ Yes |
| **25 trials total** | **~11 GB – 45 GB** | ✅ Yes |

> [!CAUTION]
> Kaggle free-tier kernels have a RAM limit of approximately 13–16 GB. Even the conservative estimate of 25 trials × ~450 MB exceeds safe headroom when combined with the kernel's own Python overhead, Polars/numpy allocators, and igraph's C-level heap.

---

## Recommended Minimal Fixes

Each fix is described with its mechanism, impact, and confirmation that it does not alter framework design, biological assumptions, or public APIs.

---

### Fix 1 (Critical): Clear `result.prepared_graph` after export

**Target**: [experiment_runner.py, ~line 346-348](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L346)

After `_step_export()` completes, the `prepared_graph` field serves no further purpose in the runner's lifecycle. The field exists in `ExperimentResult` for downstream consumers, but the notebook's Cell 9 evaluator only uses `result.analysis_results` and `result.error_result.perturbation_metadata` — not the graph itself.

**Proposed addition** (inside `run()`, after `_step_export()`):

```python
# Allow the large PreparedGraph objects to be reclaimed.
result.prepared_graph = None
```

**Why this preserves the framework**: `ExperimentResult.prepared_graph` is typed `Optional[PreparedGraph]`. Setting it to `None` is valid. The field exists so that callers *can* access the graph if needed; it does not enforce permanent retention. The `to_dict()` method already omits graph objects. The export has already completed, so no information is lost.

**Risk**: Minimal. Any caller that accesses `result.prepared_graph` after `runner.run()` returns will now get `None` instead of the graph. This is the correct post-export behavior. If a caller needs the graph, it can re-preprocess; however, this is not done anywhere in the existing notebook or framework.

---

### Fix 2 (Critical): Clear `result.error_result.edge_mask` after building the temp graph

**Target**: [experiment_runner.py, ~line 525](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L522-L528)

After the temporary perturbed graph is built (Step 6) and analyses complete (Step 7), the `edge_mask` list is no longer needed. Its summary statistics are already stored in `perturbation_metadata`.

**Proposed addition** (inside `_run_pipeline()`, after `del temp_graph`):

```python
if error_result is not None and error_result.edge_mask is not None:
    error_result.edge_mask = None
```

**Why this preserves the framework**: `ErrorResult.edge_mask` is `Optional[List[bool]]`. The docstring states it is used by the runner to build the temporary subgraph. That construction is complete at this point. `perturbation_metadata` retains the scientifically relevant summary (edges removed, achieved error rate, etc.). The `to_dict()` serialisation already converts the mask to summary statistics (active/suppressed counts), not the raw list.

**Risk**: Minimal. No code in the framework or notebook reads `edge_mask` after the subgraph is built.

---

### Fix 3 (High): Replace `copy.deepcopy(metric_val)` with a shallow copy for immutable vector types

**Target**: [statistics_engine.py, line 298](file:///home/surjit/Desktop/flywire/v1/core/statistics_engine.py#L298)

```python
# Current:
vector_collector[name][metric_key].append(
    copy.deepcopy(metric_val)
)

# Proposed (for list/tuple of scalars):
vector_collector[name][metric_key].append(
    list(metric_val)   # shallow copy — scalar elements are immutable
)
```

**Why this preserves the framework**: The purpose of the copy is to prevent the collector from holding a reference into the live `AnalysisResult.metrics` dict (so the result could theoretically be modified or freed independently). Since list elements are `int` or `float` (immutable Python scalars), a shallow copy `list(metric_val)` achieves the same isolation without the overhead of `copy.deepcopy`. For numpy arrays, `val.copy()` achieves the same.

**Risk**: Minimal. The protection of `copy.deepcopy` against nested mutable structures is unnecessary here since the vectors contain only scalars.

---

### Fix 4 (High): Nullify dynamically-attached Polars DataFrames after the pipeline uses them

**Target**: [experiment_runner.py, ~line 525-528](file:///home/surjit/Desktop/flywire/v1/core/experiment_runner.py#L522-L528)

After analyses complete, the three Polars DataFrames (`edge_features`, `edge_vulnerability`, `calibrated_probabilities`) are no longer needed. They were only required for vulnerability scoring and calibration, which are pipeline steps 3.6 and 3.7.

**Proposed addition** (after `del temp_graph`, still inside `_run_pipeline()`):

```python
# Release heavy Polars DataFrames now that the pipeline is complete.
if hasattr(prepared, "calibrated_probabilities"):
    prepared.calibrated_probabilities = None
if hasattr(prepared, "edge_vulnerability"):
    prepared.edge_vulnerability = None
prepared.edge_features = None
```

**Why this preserves the framework**: These fields are set inside `_run_pipeline()` and are only consumed by the vulnerability model, calibration, and the error model — all of which have completed. The `export_manager.py` does not read these fields. The checkpoint files for phases 012–014 have already been written. `PreparedGraph.edge_features` is typed `Optional[...]` and defaults to `None`, so this is a valid state.

**Risk**: Minimal. No code reads these fields after the pipeline ends. The data has been fully consumed.

---

### Fix 5 (Notebook-level, High Impact): Clear `results_per_rate` entries after statistical evaluation

**Target**: [experiments_missed_synapses.ipynb, Cell 9](file:///home/surjit/Desktop/flywire/v1/experiments_missed_synapses.ipynb#L250)

After `evaluator.evaluate(baseline_runs, successful_runs)` returns a summary (`eval_result`), the raw `ExperimentResult` objects in `results_per_rate[err_rate]` are no longer needed. The evaluated statistics are fully in `eval_result`.

**Proposed addition** (inside Cell 9, after `eval_result = evaluator.evaluate(...)`):

```python
# Free raw trial results after statistical evaluation is complete.
results_per_rate[err_rate] = None
```

**Why this preserves the framework**: `aggregated_stats_by_rate` stores the evaluated `StatisticalEvaluationResult` objects, which contain only lightweight scalars (`MetricEvaluation` dataclasses). The raw `ExperimentResult` objects — including all `PreparedGraph` references — are no longer used after `evaluate()` returns. Cell 10 reads `aggregated_stats_by_rate`, not `results_per_rate`.

**Risk**: Minimal in the current notebook flow. If `baseline_runs` is computed before the loop and stored separately (which it is, on line 256), it may hold references. Clearing `results_per_rate[0.00]` after all other rates are evaluated is safe.

> [!IMPORTANT]
> Fix 5 can only be applied if Fixes 1 and 2 are also applied, since Fix 5 clears the outer dict but the `prepared_graph` and `edge_mask` inside each result must also be nil for GC to reclaim the full chain. All five fixes together produce the complete solution.

---

## Garbage Collection Analysis

Python's garbage collector works by reference counting (CPython). An object is freed when its reference count drops to zero. The analysis confirms:

**References do NOT disappear after `runner.run()` returns.** The call chain is:

```
results_per_rate  (Cell 8 global)
  └─ List[ExperimentResult]
        └─ ExperimentResult.prepared_graph
              └─ PreparedGraph.graph        → igraph.Graph (C heap + Python attrs)
              └─ PreparedGraph.lookup       → GraphLookup  (Python dicts, millions of objects)
              └─ PreparedGraph.edge_features → Polars DataFrame (Arrow buffers)
              └─ prepared.edge_vulnerability → Polars DataFrame
              └─ prepared.calibrated_probs  → Polars DataFrame
        └─ ExperimentResult.error_result
              └─ ErrorResult.edge_mask     → List[bool]   (millions of Python bool objects)
        └─ ExperimentResult.analysis_results
              └─ List[AnalysisResult]
                    └─ metrics["in_degrees"] → List[int]
                    └─ metrics["out_degrees"] → List[int]
                    └─ metrics["pagerank_scores"] → List[float]
                    └─ metrics["betweenness"] → List[float]
                    └─ metrics["closeness"] → List[float]
```

**Python's GC cannot reclaim any of these** while `results_per_rate` exists in the notebook's global scope. `del` or reassignment (`= None`) is required to break the reference chain.

There are **no circular references** detected. The GC's cycle collector is not the bottleneck — it is the straightforward linear retention chain from `results_per_rate` down to igraph's C-level heap.

---

## Architecture Constraints Compliance

All five recommended fixes:

| Constraint | Compliance |
|---|---|
| No architectural redesign | ✅ All fixes are 1–3 line additions or reassignments |
| Biological assumptions unchanged | ✅ No change to vulnerability, calibration, or perturbation logic |
| Registry system unchanged | ✅ No changes to AnalysisRegistry or ErrorRegistry |
| Experiment pipeline unchanged | ✅ Pipeline steps are in the same order |
| Statistical methodology unchanged | ✅ StatisticsEngine.aggregate() logic unchanged for Fix 3 (only deepcopy → list()) |
| Exported formats unchanged | ✅ All file outputs are unaffected |
| Public APIs unchanged | ✅ `runner.run()` still returns `ExperimentResult`; fields are Optional and may be None |
| Configuration structure unchanged | ✅ ExperimentConfig is not touched |
| Deterministic behaviour | ✅ No changes to RNG or seeding |
| Reproducibility | ✅ Export files remain identical |

---

## Risk Assessment Summary

| Fix | Impact | Risk | Invasiveness |
|---|---|---|---|
| Fix 1: `result.prepared_graph = None` after export | ⚡ Critical | 🟢 Very Low | 1 line |
| Fix 2: `error_result.edge_mask = None` after temp graph built | ⚡ Critical | 🟢 Very Low | 3 lines |
| Fix 3: `list()` instead of `copy.deepcopy()` for vectors | 🔵 High | 🟢 Very Low | 1 line |
| Fix 4: Nullify Polars DataFrames after pipeline | 🔵 High | 🟢 Very Low | 4 lines |
| Fix 5: Clear `results_per_rate[rate]` after eval | ⚡ Critical | 🟡 Low (notebook-only) | 1 line per rate |

---

## Open Questions

1. **Does Cell 9 baseline handling require the full `PreparedGraph`?** The `baseline_runs` list is constructed from `results_per_rate.get(0.00, [])`. If Fix 1 is applied (clearing `prepared_graph`), this only affects the `PreparedGraph` field, not `analysis_results`. `StatisticalEvaluator.evaluate()` reads `a_res.metrics` from `analysis_results`, not the graph. Confirmed safe.

2. **Does the notebook export the `prepared_graph` from any result?** Inspected `ExportManager`: it reads only `result.analysis_results`, `result.error_result`, and scalar fields. It does not touch `result.prepared_graph`. Confirmed: clearing `prepared_graph` does not break exports.

3. **Is `edge_mask` ever needed after the temp graph is built?** The framework's `_build_temp_graph()` consumes `edge_mask` to build the igraph subgraph. After that function returns (line 748), no further code reads `edge_mask`. Confirmed safe to clear.

4. **Are there other notebooks or scripts that may depend on reading these fields after `runner.run()`?** The `run_demo.py` was not inspected in detail for this report. If any script reads `result.prepared_graph` or `result.error_result.edge_mask` after `run()`, those callers would need to be updated or the nullification step moved to a different location.
