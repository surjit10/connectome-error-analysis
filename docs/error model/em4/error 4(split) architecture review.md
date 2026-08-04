# EM4 Integration & Architecture Compatibility Review

> **Reviewer stance:** EM1–EM3 are frozen, production-quality code. This review treats them as an immutable contract. Any recommendation to modify an existing file is treated as a last resort and must be individually justified.

---

## Part 1 — Architecture Mapping

| Module | File | Responsibility | EM4 Reuse? | Modify? | New? |
|--------|------|----------------|-----------|---------|------|
| `BaseErrorModel` | `modules/error_models/common/base_error_model.py` | Abstract base: validation, RNG init, timing, exception wrapping, `_perturb` dispatch | **Yes — inherit directly** | ❌ No | — |
| `ErrorResult` | `modules/error_models/common/error_result.py` | Return contract: `edge_mask`, `added_edges`, `weight_updates`, `perturbation_metadata` | **Yes — populate directly** | ❌ No | — |
| `ErrorRegistry` | `modules/error_models/common/error_registry.py` | Catalogue of models, keyed by NAME | **Yes — `registry.register()`** | ❌ No | — |
| `common/utils.py` | `modules/error_models/common/utils.py` | Config helpers: `require_config_key`, `validate_config_keys`, `add_warning` | **Yes — import directly** | ❌ No | — |
| `ExperimentRunner` | `core/experiment_runner.py` | Pipeline orchestration, temp graph construction | **Yes — zero changes required** | ❌ No | — |
| `_build_temp_graph` | inside `experiment_runner.py` | Applies `edge_mask`, `added_edges`, `weight_updates` to baseline | **Yes — already supports topology changes** | ❌ No | — |
| `PreparedGraph` | `modules/preprocessing/common/prepared_graph.py` | Immutable baseline graph container | **Yes — read-only access only** | ❌ No | — |
| `AnalysisRegistry` | `modules/graph_analyses/analysis_registry.py` | Catalogue of analyses | **Yes — unchanged** | ❌ No | — |
| `StatisticsEngine` | `core/statistics_engine.py` | Aggregation of `ExperimentResult` | **Yes — unchanged** | ❌ No | — |
| `ExportManager` | `core/export_manager.py` | CSV/JSON/HTML export | **Yes — unchanged** | ❌ No | — |
| `CheckpointManager` | `core/checkpoint_manager.py` | Trial checkpointing | **Yes — unchanged** | ❌ No | — |
| `BiologicalAssumptions` | `modules/error_models/common/biology.py` | Declarative biology config | ❌ Not needed (split model has its own candidate logic) | ❌ No | — |
| `ProbabilityCalibrator` | `modules/error_models/common/calibration.py` | EM1-specific synapse probability calibration | ❌ Not needed | ❌ No | — |
| `VulnerabilityModel` | `modules/preprocessing/missed_synapses/vulnerability.py` | EM1-specific edge vulnerability scoring | ❌ Not needed | ❌ No | — |
| **`split_errors/`** | `modules/error_models/split_errors/` | New EM4 perturbation model | — | — | **✅ New** |
| **`split_errors.yaml`** | `configs/error_models/split_errors.yaml` | EM4 configuration | — | — | **✅ New** |
| **`error-4-split-errors.ipynb`** | `notebooks/error-4-split-errors.ipynb` | EM4 experiment notebook | — | — | **✅ New** |

---

## Part 2 — Dependency Analysis

```
EM4 SplitErrors
    │
    ├── DIRECT DEPENDENCIES (must import)
    │   ├── modules.error_models.common.base_error_model.BaseErrorModel
    │   ├── modules.error_models.common.error_result.ErrorResult
    │   ├── modules.error_models.common.error_registry.registry
    │   ├── modules.error_models.common.utils  (optional, for config helpers)
    │   └── modules.preprocessing.common.prepared_graph.PreparedGraph (type hint)
    │
    ├── INDIRECT DEPENDENCIES (framework handles automatically)
    │   ├── core.experiment_runner.ExperimentRunner  (calls model.execute())
    │   ├── modules.graph_analyses.*                  (run after perturbation)
    │   └── core.statistics_engine / export_manager  (consume ExperimentResult)
    │
    └── NO DEPENDENCY (intentionally isolated)
        ├── modules.error_models.missed_synapses.*
        ├── modules.error_models.false_synapses.*
        ├── modules.error_models.synapse_count.*
        ├── modules.error_models.common.biology
        ├── modules.error_models.common.calibration
        └── modules.preprocessing.missed_synapses.*
```

---

## Part 3 — Existing Infrastructure Reuse

| Component | File | Class/Function | How EM4 Reuses It |
|-----------|------|---------------|-------------------|
| RNG seeding | `base_error_model.py` | `BaseErrorModel.execute()` | Framework calls `rng = np.random.default_rng(seed)` automatically; `_perturb(rng=rng)` receives it |
| Input validation | `base_error_model.py` | `_validate_input()` | Automatically checks `PreparedGraph` contract before `_perturb` is called |
| Timing + logging | `base_error_model.py` | `execute()` | Runtime, start/finish logs, exception wrapping all handled for free |
| Status tracking | `error_result.py` | `ErrorResult.status` | Framework sets `SUCCESS`/`FAILED` — EM4 only populates fields |
| Model registration | `error_registry.py` | `registry.register()` | One-liner at module bottom, identical to EM1–EM3 |
| Config key validation | `common/utils.py` | `require_config_key`, `validate_config_keys` | EM4 calls these to parse `minimum_degree`, `min_fragment_size`, etc. |
| Warning emission | `common/utils.py` | `add_warning()` | Used when a neuron is skipped (degree too low, fragment too small) |
| Temp graph building | `experiment_runner.py` | `_build_temp_graph()` | Already handles `edge_mask` + `added_edges` together. EM4 uses the combined path. |
| Graph analyses | `analysis_registry.py` | All registered analyses | Run unchanged on the temp graph produced by EM4 |
| Export pipeline | `export_manager.py`, `statistics_engine.py` | Full pipeline | Consumes `ExperimentResult` — no EM4 awareness needed |

---

## Part 4 — Existing Graph Utilities

| Utility | Available? | Location | EM4 Usage |
|---------|-----------|----------|-----------|
| Neighbor extraction | ✅ igraph native | `graph.neighbors(v)` | Extract ego network |
| Degree calculation | ✅ igraph native | `graph.degree()` / `graph.degree(v)` | Candidate selection filter |
| Edge iteration | ✅ igraph native | `graph.es` | Edge count validation |
| Node lookup | ✅ `PreparedGraph` | `prepared.lookup.id_to_idx` | Map root IDs to igraph indices |
| Graph copying | ✅ igraph native | `graph.copy()` | **Not needed** — EM4 produces mask/added_edges, never copies baseline |
| Subgraph creation | ✅ igraph native | `graph.subgraph(vertices)` | Create ego-network subgraph |
| Connected components | ✅ igraph native | `sub.connected_components()` | Core partition algorithm |
| Community detection | ✅ igraph native | `sub.community_multilevel()` | Louvain fallback |
| Node insertion | ✅ igraph native | `graph.add_vertices()` | **Not needed** — ExperimentRunner handles this via `added_edges` |
| Node deletion | ✅ igraph native | `graph.delete_vertices()` | **Not needed** — communicated via `edge_mask` |

**Finding:** No new graph utility functions are required. All necessary operations are already available in igraph or the existing framework.

---

## Part 5 — Existing Validation

The `BaseErrorModel.execute()` already validates:
- `edge_mask` length matches `graph.ecount()` (line 138–144 of `base_error_model.py`)
- `prepared` is a valid `PreparedGraph` instance

**New validation required inside EM4 `_perturb` only:**
- Fragment size check: `min(len(setA), len(setB)) >= min_fragment_size`
- Minimum degree check: `degree(v) >= minimum_degree`
- Edge count conservation: `len(setA) + len(setB) == degree(v)` (zero-loss assertion)

These validations are internal to `model.py` and do not require changes to shared modules.

---

## Part 6 — Existing Configuration

All EM4 parameters belong in a new `configs/error_models/split_errors.yaml`. The pattern is identical to `synapse_count.yaml`:

```yaml
# configs/error_models/split_errors.yaml
error_model: split_errors

error_rate: 0.05         # Fraction of eligible neurons to split
minimum_degree: 10       # Minimum degree for a neuron to be eligible
min_fragment_size: 3     # Minimum number of partners in the smaller fragment
max_retry: 3             # Number of re-roll attempts before skipping a neuron
community_algorithm: louvain   # Algorithm for 1-component fallback
random_seed: null        # Optional seed override (framework seed takes priority)
```

These keys are passed via `ExperimentConfig.error_model_config` — the same dict-based interface used by all existing models. **No changes to any configuration loading module are required.**

---

## Part 7 — Existing Experiment Runner

**EM4 is registered identically to EM1–EM3.**

The `ExperimentRunner` is fully generic:
1. It calls `self._error_registry.instantiate(name)` with any registered name.
2. It calls `model.execute(prepared, config=..., seed=...)`.
3. It reads `error_result.edge_mask` and `error_result.added_edges` to build the temp graph.

**Critical finding:** `_build_temp_graph()` already handles the combined `has_mask and has_added` path (lines 742–755). EM4 will use `edge_mask` (to remove the original node's edges) and `added_edges` (to rewire to the two fragment nodes). **This path is already implemented and tested.**

> **Verdict: ExperimentRunner requires zero modifications.**

---

## Part 8 — Existing Statistics Pipeline

The statistics pipeline consumes `ExperimentResult`, which is agnostic to the error model used. Once the temp graph is built, the analysis results are structurally identical regardless of whether the perturbation was EM1, EM2, EM3, or EM4.

- `StatisticsEngine`: No changes needed.
- `ExportManager` (CSV/JSON/HTML): No changes needed.
- `MetadataManager`: No changes needed.
- All graph analyses (PageRank, Betweenness, etc.): Run unchanged on the temp graph.

> **Verdict: The entire statistics and export pipeline requires zero modifications.**

---

## Part 9 — Existing BaseErrorModel

`BaseErrorModel` already provides everything EM4 needs:

| Hook | Status |
|------|--------|
| `rng` (seeded, non-global) | ✅ Provided as argument to `_perturb` |
| `config` dict | ✅ Provided as argument to `_perturb` |
| `result` pre-initialised | ✅ Provided as argument to `_perturb` |
| Input validation | ✅ `_validate_input` runs before `_perturb` |
| Exception handling | ✅ Any uncaught exception in `_perturb` is caught by `execute()` |
| Timing | ✅ `runtime_seconds` set automatically |
| Logging | ✅ Start/finish logged automatically |
| NAME enforcement | ✅ `__init_subclass__` enforces non-empty NAME |

> **Verdict: BaseErrorModel requires zero modifications. EM4 inherits it unchanged.**

---

## Part 10 — New Code Required

```
modules/error_models/split_errors/
    __init__.py          [NEW] — imports model, triggers auto-registration
    model.py             [NEW] — SplitErrors(BaseErrorModel): core _perturb logic
```

`model.py` is the only substantial new file. It is self-contained and does not require a separate `helper.py` or `validator.py` — all helpers are small enough to live inside `model.py` as private functions, consistent with EM3 (`synapse_count/model.py`, 163 lines, zero helpers).

**No shared utilities need to be modified or created.** All graph operations use igraph directly. Validation logic is internal to EM4.

---

## Part 11 — Existing Tests

**Tests that already cover EM4 indirectly:**
- `test_error_registry.py` — confirms `registry.register()` works for any `BaseErrorModel` subclass
- `test_experiment_runner.py` — confirms the runner pipeline works with any registered model
- `test_full_pipeline.py` — confirms end-to-end execution produces valid `ExperimentResult`

**New tests required (inside `tests/test_split_errors.py`):**

| Test | Purpose |
|------|---------|
| `test_split_correctness` | Verify edge count before == edge count after (A + B = original degree) |
| `test_rewiring_no_loss` | Verify no edges are silently dropped or duplicated |
| `test_minimum_degree_rejection` | Neurons with degree < 10 must be skipped |
| `test_min_fragment_rejection` | Splits producing fragment < 3 partners must retry/skip |
| `test_determinism` | Same seed → identical split selection |
| `test_graph_integrity` | After 1000 splits, graph remains valid (no orphans, no self-loops) |
| `test_louvain_fallback` | 1-component ego graphs correctly fall back to community detection |
| `test_clique_rejection` | Clique + 1 community → model safely skips neuron |
| `test_star_topology` | Star graph → correct component-based split |
| `test_synthetic_small` | Small synthetic graph (5 nodes) with known expected output |

---

## Part 12 — Notebook Compatibility

Existing notebooks are standalone and reference their own error model by name string. Creating `notebooks/error-4-split-errors.ipynb` requires no changes to any existing notebook.

The new notebook follows the identical cell structure of `error-3-synapse-count.ipynb`:
1. Imports and configuration
2. Dataset loading
3. ExperimentRunner setup
4. Multi-trial loop
5. Statistical evaluation
6. Summary table and plots

---

## Part 13 — Regression Risk Analysis

| Proposed Action | Risk | Justification |
|----------------|------|--------------|
| Create `split_errors/model.py` | **None** | New file; no existing code paths touched |
| Create `split_errors/__init__.py` | **None** | New file |
| Add `from . import split_errors` to `modules/error_models/__init__.py` | **Low** | Additive import only; Python executes registration side-effect at import time. Identical to lines 63–65 already present for EM1–EM3 |
| Create `configs/error_models/split_errors.yaml` | **None** | New file; config loading is on-demand |
| Create `notebooks/error-4-split-errors.ipynb` | **None** | New file |
| Create `tests/test_split_errors.py` | **None** | New file |

> **One file requires a single-line addition:** `modules/error_models/__init__.py` needs `from . import split_errors` appended. This is additive, not a modification of existing logic.

---

## Part 14 — Backward Compatibility

**EM4 cannot affect EM1–EM3 output because:**

1. The `ErrorRegistry` is a name-keyed dict. Adding `split_errors` does not alter the lookup path for `missed_synapses`, `false_synapses`, or `synapse_count_measurement`.
2. `BaseErrorModel.execute()` is a pure dispatch to `_perturb()`. Each model's `_perturb` is isolated.
3. The `ExperimentRunner` instantiates models by name. Running EM1 is independent of whether EM4 is registered.
4. The `PreparedGraph` is read-only. EM4 never writes to `prepared.graph`.
5. The `np.random.default_rng(seed)` is locally scoped inside each `execute()` call. EM4's RNG cannot leak into EM1–EM3 trials.

> **Conclusion: EM1–EM3 will produce bit-identical outputs after EM4 is integrated.**

---

## Part 15 — Final Implementation Plan

| Step | File | Action | Risk |
|------|------|--------|------|
| 1 | `modules/error_models/split_errors/__init__.py` | Create: import `SplitErrors`, trigger auto-registration | None |
| 2 | `modules/error_models/split_errors/model.py` | Create: implement `SplitErrors(BaseErrorModel)._perturb()` | None |
| 3 | `modules/error_models/__init__.py` | Add `from . import split_errors` (1 line, additive only) | Low |
| 4 | `configs/error_models/split_errors.yaml` | Create: EM4 config with all validated parameters | None |
| 5 | `tests/test_split_errors.py` | Create: 10 targeted unit tests covering all edge cases | None |
| 6 | `notebooks/error-4-split-errors.ipynb` | Create: experiment notebook following EM3 structure | None |

---

## Part 16 — Refactoring Review

| Considered Modification | Decision | Justification |
|------------------------|----------|---------------|
| Extract ego-graph logic to `common/graph_utils.py` | **Rejected** | Only EM4 uses this logic; no other model needs it. Adding to shared utils violates the "contamination" principle. |
| Add `node_additions` field to `ErrorResult` | **Rejected** | The existing `added_edges` field already carries the rewired edges. The virtual "fragment nodes" are implicit in the edge additions — no explicit node management is needed in the result contract. |
| Add `split_errors` to `BiologicalAssumptions` | **Rejected** | `BiologicalAssumptions` is EM1-specific (synapse-level vulnerability). EM4 has different biology. Adding EM4 config there would contaminate an unrelated module. |
| Modify `_build_temp_graph` to handle node deletion | **Rejected** | Not needed. The split is communicated as: edge_mask=False for original node's edges + added_edges for fragments. The runner's existing combined-path already handles this correctly. |

---

## Part 17 — Final File Tree

```
modules/
    error_models/
        __init__.py                    [MODIFY — 1 line added]
        common/                        [EXISTING — untouched]
            base_error_model.py
            error_registry.py
            error_result.py
            utils.py
            biology.py
            calibration.py
            exceptions.py
        missed_synapses/               [EXISTING — untouched]
            __init__.py
            model.py
        false_synapses/                [EXISTING — untouched]
            __init__.py
            model.py
            weight_assignment.py
        synapse_count/                 [EXISTING — untouched]
            __init__.py
            model.py
        split_errors/                  [NEW]
            __init__.py
            model.py

configs/
    error_models/
        split_errors.yaml              [NEW]
        synapse_count.yaml             [EXISTING — untouched]
        false_synapses.yaml            [EXISTING — untouched]

tests/
    test_split_errors.py               [NEW]

notebooks/
    error-4-split-errors.ipynb         [NEW]
```

---

## Part 18 — Final Decision Summary

### Safe To Reuse

| Class / Function | File |
|------------------|------|
| `BaseErrorModel` | `modules/error_models/common/base_error_model.py` |
| `ErrorResult` | `modules/error_models/common/error_result.py` |
| `ErrorRegistry` + `registry` singleton | `modules/error_models/common/error_registry.py` |
| `require_config_key`, `validate_config_keys`, `add_warning` | `modules/error_models/common/utils.py` |
| `ExperimentRunner._build_temp_graph()` | `core/experiment_runner.py` |
| `PreparedGraph.graph`, `PreparedGraph.lookup` | `modules/preprocessing/common/prepared_graph.py` |
| `AnalysisRegistry` | `modules/graph_analyses/analysis_registry.py` |
| `StatisticsEngine`, `ExportManager`, `MetadataManager` | `core/` |

---

### Must Remain Untouched

| File | Reason |
|------|--------|
| `core/experiment_runner.py` | The `_build_temp_graph` method already handles all EM4 perturbation types. Any change risks breaking the temp graph construction for EM1–EM3. |
| `modules/error_models/common/base_error_model.py` | The abstract contract is already sufficient. Any change propagates to all four models simultaneously. |
| `modules/error_models/common/error_result.py` | The `added_edges` field already covers EM4's topology changes. No new fields needed. |
| `modules/error_models/missed_synapses/` | Production-frozen. |
| `modules/error_models/false_synapses/` | Production-frozen. |
| `modules/error_models/synapse_count/` | Production-frozen. |
| `modules/error_models/common/biology.py` | EM1-specific; EM4 has no dependency on vulnerability scoring. |
| `modules/error_models/common/calibration.py` | EM1-specific; EM4 does not calibrate probabilities. |

---

### New Code Only

| File | Class / Function |
|------|-----------------|
| `modules/error_models/split_errors/model.py` | `SplitErrors(BaseErrorModel)` |
| `modules/error_models/split_errors/model.py` | `_select_candidates(graph, n, min_degree, rng)` |
| `modules/error_models/split_errors/model.py` | `_partition_ego(subgraph, rng, min_fragment_size)` |
| `modules/error_models/split_errors/model.py` | `_greedy_balance(groups)` |
| `modules/error_models/split_errors/__init__.py` | (registration trigger) |
| `configs/error_models/split_errors.yaml` | (configuration) |
| `tests/test_split_errors.py` | 10 unit tests |
| `notebooks/error-4-split-errors.ipynb` | Experiment notebook |

---

## Final Recommendation

### ✅ Option A

> **EM4 can be implemented entirely as a standalone module. The single required change — appending one import line to `modules/error_models/__init__.py` — is purely additive. No existing architecture changes are required. Proceed with implementation.**

The framework was designed with this extensibility in mind. The `BaseErrorModel`/`ErrorResult`/`ErrorRegistry` triad, combined with `_build_temp_graph`'s already-implemented combined mask-plus-added-edges path, makes EM4 a pure plug-in. Writing EM4 is now exclusively a software engineering task with zero methodological or architectural uncertainty remaining.
