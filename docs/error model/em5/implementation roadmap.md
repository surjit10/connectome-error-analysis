# EM5 (Merge Errors) — Implementation Roadmap

> **Stance:** EM1–EM4 are frozen, production-quality code. This roadmap treats
> them as an immutable contract. **No existing file is modified** except one
> additive import line in `modules/error_models/__init__.py` and the
> already-empty placeholder `configs/error_models/merge_errors.yaml`.
> Everything else is new code.

---

## 0. Executive Summary

EM5 (merge errors / under-segmentation) is the **exact inverse of EM4 (split
errors)**. The established, battle-tested EM4 extension pattern applies
directly, with a dedicated runner and EM5-only vector alignment so that the
shared framework never learns about temporary merged vertices. EM5
approximates the graph-level consequences of reconstruction over-merging and
is **not** intended to reproduce voxel-level agglomeration algorithms.

The complete artifact set (all NEW files except two safe touches):

| # | Artifact | Path | Type |
|---|----------|------|------|
| 1 | Scientific methodology | `docs/error model/em5/method plan.md` | ✅ written |
| 2 | Model package | `modules/error_models/merge_errors/__init__.py`, `model.py` | NEW |
| 3 | Config | `configs/error_models/merge_errors.yaml` | fill empty placeholder |
| 4 | Dedicated runner | `core/merge_experiment_runner.py` | NEW |
| 5 | Vector alignment helper | `core/merge_vector_alignment.py` | NEW |
| 6 | Registration | `modules/error_models/__init__.py` — add `from . import merge_errors` | +1 line, additive |
| 7 | Unit + integration tests | `tests/test_merge_errors.py` | NEW |
| 8 | Vector-alignment + isolation tests | `tests/test_em5_vector_alignment.py` | NEW |
| 9 | Experiment notebook | `notebooks/error-5-merge-errors.ipynb` + `notebooks/test_notebook/error-5-test-merge-errors.ipynb` | NEW |
| 10 | Verification scripts | `0-temp/run_em5.py`, `0-temp/verify_em5.py` | NEW |
| 11 | Presentation | generated from trial CSVs by the existing error-model-agnostic exporters | generated |

---

## 1. How the Existing Framework Works (verified against the code)

### 1.1 The core contract (frozen, reused as-is)

- **`modules/error_models/common/base_error_model.py`** — abstract
  `BaseErrorModel`. The runner calls `model.execute(prepared, config, seed)`,
  which validates input, creates a **local** `np.random.default_rng(seed)`,
  times and exception-wraps the call, then dispatches to the abstract
  `_perturb(prepared, config, result, rng)`. The baseline graph is never
  copied or mutated. Concrete models never touch global RNG.
- **`modules/error_models/common/error_result.py`** — `ErrorResult` carries
  `edge_mask` (bool list), `weight_updates` (dict), `added_edges`
  (list of `(pre_root_id, post_root_id, weight)`), `perturbation_metadata`,
  `warnings`, `errors`, and `extra` (free-form dict — EM4 uses
  `extra["split_plan"]`; EM5 uses `extra["merge_plan"]`).
- **`modules/error_models/common/error_registry.py`** — name-keyed catalogue.
  Concrete models self-register at module import time via
  `registry.register(cls, overwrite=True)`. `modules/error_models/__init__.py`
  imports each model package, triggering registration.
- **`modules/error_models/common/utils.py`** — `validate_config_keys`,
  `require_config_key`, `add_warning` (import directly; do not extend).
- **`modules/preprocessing/common/prepared_graph.py`** — immutable baseline
  container; `prepared.graph` (igraph) and `prepared.lookup.id_to_idx /
  id_map` (root_id ↔ index).

### 1.2 The two execution patterns

| | EM1–EM3 | EM4 (template for EM5) |
|---|---|---|
| Runner | `core/experiment_runner.py` (`ExperimentRunner`) | `core/split_experiment_runner.py` (`SplitExperimentRunner`) — **dedicated**, composes the shared runner's step methods, never modifies them |
| Temp graph | `_build_temp_graph()`: mask → subgraph; added_edges → copy+add | `_split_build_temp_graph()`: copies baseline, **adds fragment vertices**, rewires edges, deletes parents, rebuilds lookups, wraps in a featureless `PreparedGraph` |
| Vector alignment | none (vertex set unchanged) | `core/split_vector_alignment.py` — EM4-only; re-aligns `pagerank_scores` to baseline ordering (sum aggregation) because vertex indices shift |
| Baseline analyses | `ExperimentRunner` steps | Same shared steps reused, EM1-specific vulnerability/calibration phases **omitted** |

### 1.3 What EM4 did, step by step (the template)

1. Wrote `docs/error model/em4/method plan.md` (methodology → source of truth).
2. Created `modules/error_models/split_errors/{__init__,model}.py` —
   `SplitErrorsModel(BaseErrorModel)`, `NAME = "split_errors"`, computes a
   serialisable `split_plan` into `result.extra["split_plan"]`, self-registers.
3. Created `configs/error_models/split_errors.yaml`.
4. Created `core/split_experiment_runner.py` (dedicated runner) +
   `core/split_vector_alignment.py` (EM5 will mirror both).
5. Added **one additive line** to `modules/error_models/__init__.py`:
   `from . import split_errors`.
6. Created `tests/test_split_errors.py` + `tests/test_em4_vector_alignment.py`
   (incl. an isolation test asserting no shared module imports the EM4-only
   helper).
7. Created `notebooks/error-4-split-errors.ipynb` and a quick test notebook.
8. Added `0-temp` verification scripts.

---

## 2. EM5 Design Decisions (settled here, so implementation is mechanical)

### 2.1 `merge_plan` schema — `ErrorResult.extra["merge_plan"]`

Mirrors `split_plan` (descriptive plan; the temp builder recomputes edges from
the baseline graph — the baseline is the source of truth):

```python
{
  <merge_id>: {                      # synthetic id of the merged vertex
      "source_ids": [root_a, root_b],   # the two absorbed neurons (ordered)
      "edges_reattached": int,          # incident edges moved to M
      "parallel_pairs_collapsed": int,  # pairs merged into one edge (sum)
      "self_loops_dropped": int,        # A->B / B->A edges removed
      "internal_synapses_dropped": int, # syn_count lost to self-loop removal
  },
  ...
}
```

Synthetic merge id (collision-free with real positive root ids): the
**Szudzik (elegant) pairing function** — a mathematically proven bijection
N x N -> N — applied to the sorted pair:

```python
def merge_id(a, b):
    x, y = min(abs(a), abs(b)), max(abs(a), abs(b))
    return -(y*y + x) if x < y else -(y*y + 2*y)   # always negative
```

The result is deterministic, injective (collision-free), and
order-independent after sorting (A, B) and (B, A) yield the same ID.
Uniqueness holds because the pairing function is mathematically injective.
Always negative, so it can never collide with real positive biological root
ids. A trial runs exactly one error model, so overlap with EM4's
fragment-id namespace is impossible in practice (documented, not enforced).

> **Temporary identifiers (no biological meaning).** Synthetic merge IDs
> are temporary implementation identifiers used only during temporary
> graph construction. They have no biological meaning and are discarded
> after analysis.
>
> **Namespace invariant.** Synthetic merge IDs always occupy a namespace
> disjoint from biological neuron IDs: all biological neuron IDs are
> positive, so every synthetic merge ID is strictly negative (the pairing
> value is negated).

### 2.2 `_merge_build_temp_graph()` semantics (isolated in the EM5 runner)

1. `temp = baseline.copy()` (never mutates the baseline).
2. For each pair in the plan: capture incident edges of A and B (partner
   **root ids**, direction, attrs), mark A and B for deletion.
3. Delete all absorbed vertices in one batch; add one synthetic vertex M per
   merge (copy vertex attrs from the surviving representative).
4. Rebuild the `root_id → index` map (deletion renumbers everything — never
   assume indices, mirror EM4 Phase 3).
5. Add re-attached edges grouped by `(M, partner_root, direction)`:
   - parallel pair (`A→X` and `B→X`) ⇒ **one** edge `M→X`,
     `syn_count = w(A→X) + w(B→X)`;
   - `A→B` / `B→A` ⇒ dropped (self-loop), count recorded.
6. Rebuild temp `id_to_idx` / `id_map`, copy graph-level metadata, wrap in a
   featureless `PreparedGraph` (features disabled, exactly like EM4).
7. Disjointness is guaranteed by the model, so no chain handling is needed.

### 2.3 Vector alignment — `core/merge_vector_alignment.py`

EM5 deletes vertices, so both the baseline vector and the temp vector must be
expressed in a common **merged coordinate space** (length `vcount − k`):

- `build_merged_order(id_map, vcount, merge_plan)` — baseline root order where
  each pair collapses to one slot (the first member keeps its position).
- `collapse_baseline_vector(vector, merged_order)` — sums the two entries of
  each merged pair into the slot (**sum aggregation**, mass-conserving: the
  merged neuron's score equals the sum of its sources; mirrors EM4's sum rule).
- `reindex_temp_vector(vector, temp_root_to_index, merged_order)` — places the
  merged vertex's score into the slot.

Both vectors end up identically ordered ⇒ Pearson/Spearman/top-K comparison in
the shared `vector_comparison` module stays valid. Only `pagerank_scores` is
aligned (mirror EM4's documented limitation). The shared framework modules
never see the alignment.

### 2.4 Config — `configs/error_models/merge_errors.yaml`

```yaml
error_model: merge_errors
error_rate: 0.05            # fraction of ELIGIBLE NEURONS participating in a
                          # merge; k = round(0.5 * rate * n_eligible) pairs
region_constraint: true     # Stage 1 hard constraint (same top_region) —
                            # mirrors EM2's existing key
soma_side_constraint: true  # Stage 1 hard constraint (soma-side
                            # compatibility) — mirrors EM2's existing key
degree_threshold: 10        # QUALITY FLOOR only (not scientific eligibility)
min_shared_partners: 3      # Stage 2 (graph-based ranking) calibration value
jaccard_min: 0.001          # candidate score floor (calibration)
top_k_per_neuron: 50        # candidate-enumeration bound (implementation)
max_retries: 20             # bounded rejection re-sampling (implementation)
```

The file already exists (empty placeholder from the original architecture
plan — `docs/architecture/flywire_architecture.md` and `repo_tree.txt` both
list `merge_errors/`), so filling it touches no working code. `region_constraint`
and `soma_side_constraint` reuse the exact mechanism EM2 already consumes.

### 2.5 Model internals (`_perturb`)

Stage 1 hard constraints (region + soma-side, via the lookup's `top_region` /
`soma_side` indexes) → Stage 2 Graph-Based Candidate Ranking (shared
partners ≥ `min_shared_partners`, ranked by Jaccard) → top-K bounded
candidate set (built
fresh each trial; **no module-level cache** — the EM4 memory-leak regression
proves this matters) → `k = round(0.5 × error_rate × n_eligible)` → weighted
sampling without replacement with a disjointness constraint + bounded retries
→ per-pair merge stats →
`result.extra["merge_plan"]` + `perturbation_metadata`
(`pairs_merged`, `neurons_absorbed`, `pairs_rejected`, `retries_used`,
`parallel_pairs_collapsed`, `self_loops_dropped`,
`internal_synapses_dropped`, ...). No graph mutation anywhere.

---

## 3. File-by-File Roadmap (implementation order)

| Step | File | Action | Depends on |
|------|------|--------|-----------|
| 0 | `docs/error model/em5/method plan.md` | ✅ done (this repo) | — |
| 1 | `modules/error_models/merge_errors/__init__.py` | NEW — docstring + `from .model import MergeErrorsModel` | — |
| 2 | `modules/error_models/merge_errors/model.py` | NEW — `MergeErrorsModel(BaseErrorModel)`, `NAME = "merge_errors"`, §2.5 algorithm, self-register | 0 |
| 3 | `configs/error_models/merge_errors.yaml` | fill placeholder (§2.4) | 0 |
| 4 | `modules/error_models/__init__.py` | **add** `from . import merge_errors` (1 line, additive) | 1–2 |
| 5 | `core/merge_experiment_runner.py` | NEW — `MergeExperimentRunner`, mirrors `SplitExperimentRunner`, `_merge_build_temp_graph()` (§2.2) | 1–4 |
| 6 | `core/merge_vector_alignment.py` | NEW — pure alignment helpers (§2.3); runner calls an `_align_pagerank_vectors()` stage (both baseline + temp vectors) | 5 |
| 7 | `tests/test_merge_errors.py` | NEW (§4) | 1–5 |
| 8 | `tests/test_em5_vector_alignment.py` | NEW (§4) | 6 |
| 9 | `notebooks/error-5-merge-errors.ipynb` + test notebook | NEW — mirror `error-4-split-errors.ipynb` cell structure with `MergeExperimentRunner` | 5 |
| 10 | `0-temp/run_em5.py`, `0-temp/verify_em5.py` | NEW — mirror `0-temp/run_em1.py` / root `verify_em4.py` | 5 |
| 11 | Presentation | generated by existing exporters (error-model-agnostic) from trial CSVs | 9 |

---

## 4. Test Plan

### 4.1 `tests/test_merge_errors.py` (mirrors `tests/test_split_errors.py`)

Unit (model):
- `test_model_registered` — `registry.is_registered("merge_errors")`.
- `test_determinism_same_seed` — same seed ⇒ identical `merge_plan`.
- `test_hard_constraint_region` — pairs in different `top_region` excluded
  (mirrors EM2's per-region candidate generation).
- `test_hard_constraint_soma_side` — incompatible soma sides excluded;
  equal sides and bilateral-compatible sides pass.
- `test_degree_quality_floor` — degree < quality floor ⇒ excluded
  (implementation quality rule, not scientific eligibility).
- `test_candidate_min_shared_partners` — pairs below the shared-partner floor
  excluded.
- `test_jaccard_scoring` — known synthetic pair ⇒ expected Jaccard, ranking.
- `test_disjointness` — a neuron never appears in two merges.
- `test_error_rate_pair_count` — `k = round(0.5 × error_rate × n_eligible)`
  (e.g. 10 eligible neurons @ 50 % → 2–3 pairs; 100 % → 5 pairs).
- `test_zero_error_rate_merges_nothing`.
- `test_invalid_error_rate_rejected` (`error_rate` ∉ [0,1] ⇒ FAILED).
- `test_unknown_config_key_warns`.
- `test_baseline_graph_never_modified` — vcount/ecount/weights unchanged.
- `test_no_module_level_graph_cache` — weakref GC regression (mirror EM4's).
- `test_merge_plan_schema` — per-pair stats present and consistent.
- `test_merge_id_order_independent` — `_merge_id(a, b) == _merge_id(b, a)`.
- `test_merge_id_injective` — distinct sorted pairs produce distinct IDs,
  including the counter-example `(1, 7)` vs `(2, 4)` that the old
  multiplication encoding collided on.
- `test_merge_plan_ids_unique` — every generated merge ID is unique within
  the plan (the Szudzik pairing is injective; duplicate detection aborts
  merge-plan construction and reports an error).

Temp graph (`MergeExperimentRunner._merge_build_temp_graph`):
- `test_vertex_count_reduced_by_k`.
- `test_synapse_count_preserved_minus_self_loops` — exactly
  `internal_synapses_dropped` lost.
- `test_parallel_edges_collapsed_and_summed`.
- `test_self_loops_removed`.
- `test_no_self_loops_no_multi_edges_no_duplicates`.
- `test_all_edges_valid_and_weighted`.
- `test_merged_vertex_in_temp_lookup`; absorbed roots absent.
- `test_baseline_unchanged_after_temp_build`.
- `test_empty_plan_returns_none`.

Full pipeline (dataset on disk → runner):
- `test_runner_produces_successful_experiment_result` — metadata
  `model_name == "merge_errors"`, `merge_plan` destroyed after trial.
- `test_pipeline_metrics` — `node_count` = baseline − k; edge count =
  baseline − collapses − self-loops; `total_synapses` = baseline − dropped.
- `test_reproducibility_full_pipeline`.
- `test_statistics_engine_and_export_compatibility` — StatisticsEngine /
  MetadataManager / ExportManager consume the EM5 `ExperimentResult`
  unchanged (mirror the EM4 test verbatim).
- `test_error_rate_zero_uses_baseline`.

### 4.2 `tests/test_em5_vector_alignment.py` (mirrors `tests/test_em4_vector_alignment.py`)

- `build_merged_order` correctness (order, pair collapse).
- `collapse_baseline_vector` sums paired entries; identity for non-merged.
- `reindex_temp_vector` places merged scores in the right slots.
- Sum aggregation conserves total mass; `mean` option works.
- **Isolation test:** no shared/frozen module (`core/experiment_runner.py`,
  `modules/error_models/common/*`, EM1–EM4 modules) imports or references
  `core.merge_vector_alignment` or `core.merge_experiment_runner`.

---

## 5. Phased Execution Plan with Validation Gates

**Phase 0 — Documentation (this roadmap).** Gate: user review of the method
plan before any code is written (mirrors EM4's "methodology first" rule).

**Phase 1 — Model + config + registration.** Create steps 1–4. Gate:
```bash
python -c "from modules.error_models import registry; \
m = registry.instantiate('merge_errors'); print(m)"
pytest tests/test_merge_errors.py -q -k "not temp and not pipeline"
```

**Phase 2 — Temp builder + runner.** Create step 5. Gate:
```bash
pytest tests/test_merge_errors.py -q
```

**Phase 3 — Vector alignment.** Create step 6. Gate:
```bash
pytest tests/test_em5_vector_alignment.py -q
```

**Phase 4 — Notebook quick test.** Create step 9 (test notebook first: 2 rates
× 1 seed on BANC). Gate: notebook completes end-to-end; export package
contains `summary.csv` + `metadata.json`; `pagerank` comparison metrics are
non-degenerate.

**Phase 5 — Verification scripts + presentation.** Create step 10, run
presentation export. Gate: `0-temp/verify_em5.py` reports vertex/edge/synapse
delta consistent with the plan.

**Phase 6 — Full regression.** Gate:
```bash
pytest tests/ -q          # full suite — EM1–EM4 tests must be untouched & green
```
Plus a targeted `git diff` review proving only `modules/error_models/__init__.py`
(+1 line) and the empty config file changed among existing files.

---

## 6. Regression-Risk / Zero-Touch Table

| Proposed action | Risk | Justification |
|---|---|---|
| New `merge_errors/{__init__,model}.py` | None | New files; no existing path touched |
| New `core/merge_experiment_runner.py` | None | Mirrors the EM4 precedent: a dedicated runner composes shared steps without modifying them |
| New `core/merge_vector_alignment.py` | None | EM5-only; imported only by the EM5 runner (isolation test enforces this) |
| New tests / notebooks / `0-temp` scripts | None | New files |
| Fill `configs/error_models/merge_errors.yaml` | None | File is an empty placeholder; config loading is on-demand |
| **`modules/error_models/__init__.py` +1 line** | Low | Purely additive import; identical to the existing `from . import split_errors` line; registry is name-keyed so EM1–EM4 lookups are unaffected |

**Must remain untouched:** `core/experiment_runner.py`,
`core/split_experiment_runner.py`, `core/split_vector_alignment.py`,
`modules/error_models/common/*`, all EM1–EM4 packages, preprocessing,
statistics engine, metadata manager, export manager, all existing tests and
notebooks.

**Why EM1–EM4 stay bit-identical:** (1) the registry is name-keyed; (2)
`BaseErrorModel.execute` is pure dispatch; (3) each model's `_perturb` is
isolated; (4) the baseline `PreparedGraph` is read-only; (5) RNGs are locally
scoped per `execute()` call. These are the same five guarantees EM4's
integration report documented — EM5 adds nothing new to the shared path.

---

## 7. Open Items for the User

1. **Error-rate semantics** — ✅ **resolved in the method plan v1.1**: `error_rate`
   is now the fraction of **eligible neurons** participating in a merge
   (`k = round(0.5 × rate × n_eligible)`), per §11. This is dataset-comparable
   (independent of top-K / `jaccard_min`) and mirrors EM4's per-eligible-neuron
   convention.
2. **Hard anatomical constraints** — added as Stage 1 of the methodology
   (region + soma side); implemented via the same keys EM2 already uses
   (`region_constraint`, `soma_side_constraint`) — no architecture change.
3. **Weighted vs uniform sampling** — Jaccard-weighted is recommended
   (plausibility), uniform is the documented fallback. §2.5.
4. **Self-loop synapse accounting** — dropped and reported vs re-attributed.
   §5/Assumption 6 of the method plan recommends dropped+reported.
5. **Multi-way merges** — explicitly out of scope (Assumption 1); disjoint
   pairs only.
