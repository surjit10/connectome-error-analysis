# EM4 (Split Errors) — Final Integration Verification Report (Updated Architecture)

> **Reviewer stance:** EM1–EM3 are production-frozen. Every finding here is backed by direct
> code evidence. Every modification to an existing file is individually justified with file,
> line, reason, and regression risk.
>
> **Updated Architecture Goal:** Implement EM4 as a completely isolated extension without modifying
> any execution path used by EM1–EM3. EM4 will use a dedicated `SplitExperimentRunner` rather than
> modifying the shared `ExperimentRunner`.

---

## Part 1 — Architecture Mapping

| Module | File | Responsibility | Reuse | Modify | New |
|--------|------|----------------|-------|--------|-----|
| `BaseErrorModel` | `modules/error_models/common/base_error_model.py` | Abstract base: validation, RNG, timing, exception wrapping, `_perturb` dispatch | ✅ Inherit directly | ❌ | — |
| `ErrorResult` | `modules/error_models/common/error_result.py` | Return contract: `edge_mask`, `added_edges`, `weight_updates`, metadata | ✅ Populate directly | ❌ | — |
| `ErrorRegistry` | `modules/error_models/common/error_registry.py` | Name-keyed catalogue of models | ✅ `registry.register()` | ❌ | — |
| `common/utils.py` | `modules/error_models/common/utils.py` | `require_config_key`, `validate_config_keys`, `add_warning` | ✅ Import directly | ❌ | — |
| `ExperimentRunner` | `core/experiment_runner.py` | Production runner for EM1–EM3 only | ❌ No | ❌ | — |
| **`SplitExperimentRunner`**| `core/split_experiment_runner.py` | Dedicated execution pipeline for topology-changing error models requiring temporary vertex creation. | — | — | ✅ New |
| `PreparedGraph` | `modules/preprocessing/common/prepared_graph.py` | Immutable baseline graph container | ✅ Read-only access | ❌ | — |
| `GraphLookup` | `modules/preprocessing/common/lookup.py` | `id_to_idx` mapping for root ID → igraph vertex index | ✅ Used for `added_edges` root ID resolution | ❌ | — |
| `AnalysisRegistry` | `modules/graph_analyses/analysis_registry.py` | Catalogue of graph analyses | ✅ Unchanged | ❌ | — |
| `StatisticsEngine` | `core/statistics_engine.py` | Aggregates `ExperimentResult` lists | ✅ Unchanged | ❌ | — |
| `ExportManager` | `core/export_manager.py` | CSV/JSON/HTML export | ✅ Unchanged | ❌ | — |
| `CheckpointManager` | `core/checkpoint_manager.py` | Trial checkpointing | ✅ Unchanged | ❌ | — |
| **`split_errors/`** | `modules/error_models/split_errors/` | EM4 perturbation model | — | — | ✅ New |
| **`split_errors.yaml`** | `configs/error_models/split_errors.yaml` | EM4 configuration | — | — | ✅ New |
| **`error-4-split-errors.ipynb`** | `notebooks/error-4-split-errors.ipynb` | EM4 experiment notebook | — | — | ✅ New |
| **`test_split_errors.py`** | `tests/test_split_errors.py` | EM4 unit and integration tests | — | — | ✅ New |

---

## Part 2 — Dependency Analysis

**EM4 Dependency Chain:**

```
SplitErrors
        │
        ▼
SplitExperimentRunner
        │
        ▼
_split_build_temp_graph()
        │
        ▼
Existing Analysis Pipeline
        │
        ▼
Statistics Engine
        │
        ▼
Export Manager
```

---

## Part 3 — Experiment Runner

**`ExperimentRunner` remains untouched.**

EM4 introduces `core/split_experiment_runner.py` which mirrors the execution flow of `ExperimentRunner` but implements an independent temporary graph construction stage capable of supporting temporary fragment vertices.

**Why this eliminates regression risk:**
By duplicating the runner logic for EM4, we guarantee that the execution path for EM1, EM2, and EM3 remains identical to their production state. The `ExperimentRunner` does not need to learn about temporary vertex creation or handle `ErrorResult` extensions. Any complexities introduced by EM4's node splitting are strictly confined to `SplitExperimentRunner`.

---

## Part 4 — Temporary Graph Construction

**EM4 utilizes `_split_build_temp_graph()`**

This function is:
- **Private to `SplitExperimentRunner`**
- **Responsible only for EM4** (or future topology-altering models)
- **Allowed to create temporary fragment vertices** to accurately represent the anatomical split
- **Allowed to extend temporary lookup tables** (like `id_to_idx`) to resolve edges involving these new vertices
- **Guaranteed to never modify `PreparedGraph`**, strictly adhering to the immutability of the baseline

*State explicitly:* The original `_build_temp_graph()` in `core/experiment_runner.py` remains completely untouched and continues serving EM1–EM3 without any added complexity.

---

## Part 5 — ErrorResult Compatibility

The current `ErrorResult` contract remains entirely sufficient.

If `SplitExperimentRunner` requires additional metadata (such as the number of virtual nodes to create, or synthetic IDs for fragment vertices), it should store this information inside the existing `perturbation_metadata` dictionary or `extra` dictionary.

*Recommendation:* Avoid changing shared framework contracts like the `ErrorResult` API unless absolutely necessary. We will pass split-specific graphing instructions to `SplitExperimentRunner` via `perturbation_metadata`.

---

## Part 6 — File Tree

```
core/
    experiment_runner.py          (Existing, untouched)
    split_experiment_runner.py    (New)
        └── _split_build_temp_graph()
```

---

## Part 7 — Required File Changes

**Required Modifications to Existing Files:**

1. **`modules/error_models/__init__.py`** (Line 65)
   - Add `from . import split_errors` to trigger auto-registration.
   - *This is the ONLY existing file that should remain modified.*

Everything else should be implemented as new files whenever possible. The prior recommendation to modify `experiment_runner.py` is withdrawn.

---

## Part 8 — Regression Analysis

EM1–EM3 now execute through `ExperimentRunner`, while EM4 executes through `SplitExperimentRunner`.

Therefore:
- Execution paths are physically separated.
- Temporary graph construction is isolated.
- Topology-changing logic cannot affect EM1–EM3.

This provides **significantly stronger regression guarantees** than attempting to generalize `_build_temp_graph()` to support both standard edge masks and temporary node creation. The production code path for EM1–EM3 remains bit-for-bit identical.

---

## Part 9 — Notebook Integration

Instead of relying on the standard `ExperimentRunner`, the EM4 notebook becomes:

```
error-4-split-errors.ipynb
        │
        ▼
SplitExperimentRunner
        │
        ▼
SplitErrors (Model)
        │
        ▼
_split_build_temp_graph()
        │
        ▼
Existing analyses
        │
        ▼
Statistics
        │
        ▼
Export
```

All existing notebooks remain unchanged.

---

## Part 10 — Final Directory Structure

**Expected additions:**

```
core/
    split_experiment_runner.py

modules/
    error_models/
        split_errors/
            __init__.py
            model.py

configs/
    error_models/
        split_errors.yaml

tests/
    test_split_errors.py

notebooks/
    error-4-split-errors.ipynb
```

**Keep Unchanged (Architecture Only):**
Do not modify the EM4 scientific methodology, biological assumptions, graph partitioning algorithm, ego-network decomposition, candidate selection, Louvain fallback, validation rules, or computational complexity. This task concerns architecture only.
