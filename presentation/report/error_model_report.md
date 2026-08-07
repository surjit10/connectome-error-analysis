# Error Model Implementation Report
### Reverse-Engineered from Source Code — No Assumptions Made

**Scope:** Missed Synapses and False Synapses error models in `/home/surjit/Desktop/flywire/v1`  
**Method:** Direct code reading — every claim is sourced to a specific file, function, and line.

---

## 1. Execution Flow

The complete pipeline runs through `ExperimentRunner` in `core/experiment_runner.py`. Here is the exact sequence:

```
ExperimentConfig
       │
       ▼
core/data_loader.py → load_dataset()          — loads raw connectivity data
       │
       ▼
core/graph_builder.py → GraphBuilder          — builds igraph.Graph
       │
       ▼
modules/preprocessing/ → preprocess_graph()   — builds PreparedGraph (immutable baseline)
       │
       ├── [Missed Synapses preprocessing]
       │      modules/preprocessing/missed_synapses/biological_features.py
       │              → extract_biological_features()          [Phase 012]
       │      modules/preprocessing/missed_synapses/vulnerability.py
       │              → VulnerabilityModel.compute_scores()    [Phase 013]
       │      modules/error_models/common/calibration.py
       │              → ProbabilityCalibrator.calibrate()      [Phase 014]
       │
       ├── [False Synapses preprocessing — one-time only]
       │      modules/preprocessing/false_synapses/candidate_generator.py
       │              → CandidateGenerator.generate()          [one-time]
       │              writes → research_data/cache/false_synapses/candidates.parquet
       │
       ▼
PreparedGraph (immutable — NEVER modified)
       │
       ▼
BaseErrorModel.execute()  [base_error_model.py]
       │  initialises local RNG: rng = np.random.default_rng(seed)
       │
       ├── [Missed Synapses] MissedSynapsesModel._perturb()
       │      → returns ErrorResult { edge_mask, weight_updates }
       │
       └── [False Synapses] FalseSynapseModel._perturb()
              → returns ErrorResult { added_edges }
       │
       ▼
ExperimentRunner._build_perturbed_graph()    [experiment_runner.py L664]
       │  builds TEMPORARY igraph from baseline + ErrorResult
       │  (baseline graph is NEVER mutated)
       │
       ▼
Graph analysis modules run on temp graph
       │
       ▼
temp graph deleted; results exported
```

---

## 2. Missed Synapses Logic

### 2.1 Biological Feature Extraction (Phase 012)

**File:** `modules/preprocessing/missed_synapses/biological_features.py`  
**Function:** `extract_biological_features(prepared: PreparedGraph) → EdgeFeatureTable`

For every edge in the baseline graph, the code extracts exactly **three features**:

| Feature | Source in code | Meaning |
|---|---|---|
| `syn_count` | `graph.es["syn_count"]` or `graph.es["weight"]` | Number of synapses on this edge |
| `source_degree` | `prepared.baseline_features["total_degree"]` at the source vertex | Total connections of the presynaptic neuron |
| `target_degree` | `prepared.baseline_features["total_degree"]` at the target vertex | Total connections of the postsynaptic neuron |

Two additional features are extracted (`reciprocal`, `source_pagerank`, `target_pagerank`) but **they are never used by the vulnerability model** — they are stored in the table but not consumed downstream.

```python
# biological_features.py — extract_biological_features()
if "syn_count" in graph.edge_attributes():
    edge_weights = graph.es["syn_count"]
elif "weight" in graph.edge_attributes():
    edge_weights = graph.es["weight"]
else:
    edge_weights = [1] * graph.ecount()
```

---

### 2.2 Biological Assumptions (Phase 011)

**File:** `modules/error_models/common/biology.py`  
**Class:** `BiologicalAssumptions`

Three weights are loaded from config (default: all 1.0 if not specified):

```python
# biology.py — BiologicalAssumptions.from_config()
synapse_weight         = weights.get("synapse_weight", 1.0)
source_degree_weight   = weights.get("source_degree_weight", 1.0)
target_degree_weight   = weights.get("target_degree_weight", 1.0)
```

The docstring states the hypotheses:
- H2: Connections with fewer synapses are inherently more vulnerable.
- H3: Sparse neurons are more susceptible to reconstruction errors.

These determine the weighting of the three features. **The actual weight values are entirely config-driven.** There is no hardcoded biological justification in the code for any specific weight ratio.

---

### 2.3 Vulnerability Score Computation (Phase 013)

**File:** `modules/preprocessing/missed_synapses/vulnerability.py`  
**Function:** `VulnerabilityModel.compute_scores(feature_table) → EdgeVulnerabilityTable`

**Step 1 — Inverted Min-Max Normalisation:**  
Each of the three features is normalised to [0, 1] and then **inverted**:

```python
# vulnerability.py — inverted_normalize()
norm = (col - col.min()) / (col.max() - col.min())  # 0 = smallest, 1 = largest
return 1.0 - norm                                    # inversion: 0 = largest, 1 = smallest
```

Edge case: if `col.max() == col.min()` (all values identical), the normalized value is 0.0, and the inverted value is 1.0 for every edge.

**Step 2 — Weighted Linear Combination:**

```python
# vulnerability.py — compute_scores()
raw_score = (norm_syn * w_syn) + (norm_src_deg * w_src) + (norm_tgt_deg * w_tgt)
```

At default weights (all 1.0) this simplifies to:

```
raw_vulnerability = (1 - norm_syn_count) + (1 - norm_source_degree) + (1 - norm_target_degree)
```

So: **an edge with the fewest synapses, connecting the two least-connected neurons, gets the highest raw vulnerability score (close to 3.0).**  
An edge with the most synapses between highly-connected neurons scores close to 0.0.

> **Key insight:** Vulnerability is entirely relative. It is computed from the distribution of edges within the dataset, not from any absolute biological threshold.

---

### 2.4 Probability Calibration (Phase 014)

**File:** `modules/error_models/common/calibration.py`  
**Function:** `ProbabilityCalibrator.calibrate(vulnerability_table) → CalibratedProbabilityTable`

**Why calibration is needed:**  
The raw vulnerability scores are relative (they sum to an arbitrary value). They cannot be used directly as removal probabilities because there is no guarantee they would produce the desired error rate. Calibration converts them into actual probabilities that produce the correct expected synapse loss.

**Algorithm — Iterative Mass Redistribution:**

```
target_synapse_drops = total_synapses × target_error_rate

# Initial scale factor
alpha = target_synapse_drops / sum(raw_vulnerability × syn_count)

# Initial probabilities
p[e] = raw_vulnerability[e] × alpha

# Iterative capping loop (up to 50 iterations, tolerance 1e-6):
For each iteration:
    1. Cap any p[e] > 1.0 to exactly 1.0
    2. Recompute expected drops from capped edges
    3. Compute residual mass: remaining_drops = target - capped_drops
    4. Redistribute only to uncapped edges: new_alpha = remaining_drops / sum(raw[uncapped] × syn[uncapped])
    5. p[uncapped] = raw[uncapped] × new_alpha
    6. Stop when no probabilities exceed 1.0
```

**What `calibrated_removal_probability` means:**  
For edge e with `syn_count = n`, the calibrated probability `p_e` is the probability that **each individual synapse** on that edge is removed. The expected number of synapses removed from edge e is `p_e × n`. Summing across all edges gives `target_error_rate × total_synapses`.

---

### 2.5 Binomial Sampling (Phase 015)

**File:** `modules/error_models/missed_synapses/model.py`  
**Function:** `MissedSynapsesModel._perturb(prepared, config, result, rng)`

```python
# model.py — _perturb()
survival_prob      = np.clip(1.0 - removal_prob, 0.0, 1.0)
surviving_synapses = rng.binomial(n=syn_count, p=survival_prob)
edge_mask          = surviving_synapses > 0
```

**Is every synapse sampled independently?**  
Yes. `rng.binomial(n=syn_count, p=survival_prob)` is exactly equivalent to flipping `syn_count` independent coins each with probability `survival_prob` of landing heads (surviving). The return value is the total number of survivors. NumPy implements this as a single vectorised call over all edges simultaneously.

**What happens for specific edge types:**

| Original syn_count | survival_prob (example) | Possible outcomes | Edge fate |
|---|---|---|---|
| 1 | 0.9 | 1 (prob 0.90) or 0 (prob 0.10) | 10% chance of deletion |
| 2 | 0.9 | 2 (prob 0.81), 1 (prob 0.18), 0 (prob 0.01) | 1% chance of deletion |
| 8 | 0.9 | Binomial(8,0.9), E[survive]=7.2 | ~0.000001% chance of deletion |
| 20 | 0.9 | Binomial(20,0.9), E[survive]=18 | Deletion practically impossible |

**Under what condition is an edge deleted?**  
```python
edge_mask = surviving_synapses > 0   # False = deleted
```
An edge is deleted **only if ALL of its synapses are lost** in the binomial draw. For an edge with `n` synapses and removal probability `p`, the probability of total deletion is `p^n`.

**Under what condition is an edge preserved?**  
Whenever at least 1 synapse survives (i.e., `surviving_synapses >= 1`). If `surviving < original`, the weight is updated:

```python
# model.py — _perturb()
changed_mask    = (surviving_synapses > 0) & (surviving_synapses < syn_count)
changed_indices = np.nonzero(changed_mask)[0]
for idx in changed_indices:
    weight_updates[int(idx)] = int(surviving_synapses[idx])
```

**New edge weight = exact number of surviving synapses** from the binomial draw.

**Quality control gate:**
```python
# model.py — _perturb()
achieved_error_rate = removed_synapses / total_original
if abs(achieved_error_rate - target_error_rate) > tolerance:   # default ±0.005
    raise RuntimeError(...)
```
If the achieved rate falls outside ±0.5pp of the target, the entire trial is aborted with a `RuntimeError`.

---

### 2.6 How the Experiment Runner Applies the Result

**File:** `core/experiment_runner.py`  
**Function:** `_build_perturbed_graph()` (L664)

For missed synapses:
```python
# experiment_runner.py L720-733
if has_mask and not has_added:
    active_edge_indices = [i for i, active in enumerate(mask) if active]
    temp_graph = baseline.subgraph_edges(active_edge_indices, delete_vertices=False)
    # builds translation: baseline edge idx → subgraph edge idx
    baseline_to_subgraph = {b_idx: s_idx for s_idx, b_idx in enumerate(active_edge_indices)}
```

Then weight updates are applied to the subgraph:
```python
# experiment_runner.py L778-795
for baseline_edge_idx, new_weight in weight_updates.items():
    subgraph_edge_idx = baseline_to_subgraph.get(baseline_edge_idx)
    if subgraph_edge_idx is None:
        continue   # edge was deleted by mask — skip
    temp_graph.es[subgraph_edge_idx][weight_attr] = new_weight
```

**The baseline graph is never modified.** `subgraph_edges()` creates a new igraph object. The temp graph is used only for analysis, then discarded.

---

## 3. False Synapses Logic

### 3.1 Candidate Generation (One-Time Preprocessing)

**File:** `modules/preprocessing/false_synapses/candidate_generator.py`  
**Function:** `CandidateGenerator.generate() → Path`

This runs **once** before any trials and writes to `research_data/cache/false_synapses/candidates.parquet`.

**Algorithm — Per Region:**

```
For each anatomical region (grouped by prepared.lookup.node_attr_index["top_region"]):

    1. Skip region if len(neurons) < min_region_size (default: 10)

    2. Build in-region successor map:
       reg_succ[neuron] = {successors of neuron that are also in this region}

    3. Build inverted successor index:
       inv_idx[target] = {all presynaptic neurons that connect TO this target}

    4. For each target with ≥ max(2, min_shared_neighbors=1) presynaptic partners:
         For every UNORDERED pair (pre_a, pre_b) from those partners:
           a. Skip if (pre_a, pre_b) already exists as a real edge
           b. Compute jaccard_out = |succ(pre_a) ∩ succ(pre_b)| / |succ(pre_a) ∪ succ(pre_b)|
           c. Skip if jaccard_out < jaccard_min (default: 0.001)
           d. Compute jaccard_in  = |pred(pre_a) ∩ pred(pre_b)| / |pred(pre_a) ∪ pred(pre_b)|
           e. Keep candidate (pre_a, pre_b, jaccard_out, jaccard_in)

    5. Sort by jaccard_out descending
    6. Keep top_k = 50 × len(region_neurons) candidates

7. Merge all region fragments, sort globally by jaccard_out descending
8. Write to candidates.parquet
```

> **Note:** The pair `(pre_a, pre_b)` is stored — NOT `(pre_a, target)`. The code generates pairs of **neurons that share a common postsynaptic target**, not the connections themselves.

---

### 3.2 Why Common Postsynaptic Targets?

**File:** `candidate_generator.py` docstring (L24-30)

The rationale is stated in the code docstring:

> *"Restricting candidate pairs to those sharing at least one common neighbour is a biologically motivated filter... neurons that share postsynaptic targets participate in overlapping circuits and are statistically more likely to form synapses. This is consistent with the 'guilt by association' principle in link prediction."*

In plain terms: if neuron A and neuron B both connect to neuron C, then A→B or B→A is more biologically plausible as a false-positive than a completely random connection.

---

### 3.3 Jaccard Similarity

**File:** `modules/preprocessing/false_synapses/similarity.py`  
**Functions:** `jaccard_out()`, `jaccard_in()`

```python
# similarity.py
jaccard_out(pre_a, pre_b) = |successors(pre_a) ∩ successors(pre_b)| / |successors(pre_a) ∪ successors(pre_b)|
jaccard_in (pre_a, pre_b) = |predecessors(pre_a) ∩ predecessors(pre_b)| / |predecessors(pre_a) ∪ predecessors(pre_b)|
```

- `jaccard_out` measures how much two neurons **project to the same targets** (downstream circuit overlap).
- `jaccard_in` measures how much two neurons **receive input from the same sources** (upstream circuit overlap).

Both return values in [0.0, 1.0]. They are stored separately and **never combined**.

**Why low-Jaccard candidates are removed:**  
The threshold `jaccard_min = 0.001` removes pairs with essentially zero circuit overlap. Below this threshold, a false connection between them would be biologically implausible.

---

### 3.4 Perturbation (Per Trial)

**File:** `modules/error_models/false_synapses/model.py`  
**Function:** `FalseSynapseModel._perturb(prepared, config, result, rng)`

**Step 1 — Compute k:**
```python
# model.py L126
k = round(error_rate * total_edges)
```
At `error_rate = 0.20` with 4,000,000 edges → `k = 800,000` false edges.

**Step 2 — Load candidate table from cache:**
```python
# model.py L144
candidates = _load_candidate_table(cache_path)  # reads candidates.parquet
```
Module-level cache: loaded once per process lifetime, shared across all trials.

**Step 3 — Build sampling pool:**
```python
# model.py L171-172
pool_size = min(len(candidates), max(k * 2, 1000))
pool = candidates.head(pool_size)   # top candidates already sorted by jaccard_out
```
The pool is at most `k × 2` of the **highest-scoring** candidates (already sorted). This means sampling is biased toward the most-plausible false connections.

**Step 4 — Sample k candidates WITHOUT replacement:**
```python
# model.py L182-190
sample_indices = rng.choice(
    pool_size,
    size=k,
    replace=False,
    p=weights[:pool_size] / weights[:pool_size].sum()  # normalized jaccard_out
)
```
**Sampling is NOT uniform.** The probability of selecting candidate (pre_a, pre_b) is proportional to its `jaccard_out` score. Higher overlap → higher probability of being selected as a false edge.

**Step 5 — Assign weights:**
```python
# model.py L193-203
weight_dist = get_empirical_weight_distribution(prepared)
for row in sample.iter_rows(named=True):
    weight = sample_false_weight(rng, weight_dist)    # uniform from empirical distribution
    added.append((pre_root_id, post_root_id, weight))
```

**Weight source** (`weight_assignment.py`):
```python
# weight_assignment.py L72
weak = arr[arr <= max_syn_count]    # max_syn_count = 5 (WEIGHT_THRESHOLD from config.py)
```
The weight distribution is all `syn_count` values from real edges where `syn_count ≤ 5`. This is then sampled **uniformly with replacement**:
```python
# weight_assignment.py L102
return int(rng.choice(weight_distribution))
```

The reason for the ≤5 threshold (stated in code docstring):  
> *"~71.5% of BANC edges have five or fewer synapses, making weak connections a reasonable prior for false-positive reconstruction errors."*  
> **Note: "It is NOT a biologically verified property of false-positive errors."**

**Step 6 — Store in result:**
```python
# model.py L204
result.added_edges = added    # list of (pre_root_id, post_root_id, weight)
```
**The baseline graph is NEVER touched.**

---

### 3.5 How the Experiment Runner Applies False Synapses

**File:** `core/experiment_runner.py` L735-755

```python
# experiment_runner.py L736-740 — False-synapse style
temp_graph = baseline.copy()
if added_indices_list:
    temp_graph.add_edges(added_indices_list)
```

Root IDs are first translated to igraph vertex indices using the lookup table:
```python
# experiment_runner.py L705-711
id_to_idx = prepared.lookup.id_to_idx
for pre_rid, post_rid, weight in added_edges:
    src = id_to_idx.get(pre_rid)
    dst = id_to_idx.get(post_rid)
    if src is not None and dst is not None:
        added_indices_list.append((src, dst))
```

If a root ID is not in the lookup (neuron doesn't exist in the dataset), the edge is silently skipped.

Weights for added edges are set afterward:
```python
# experiment_runner.py L800-811
base_count = temp_graph.ecount() - len(added_weights_list)
for i, w in enumerate(added_weights_list):
    edge_idx = base_count + i
    temp_graph.es[edge_idx][weight_attr] = w
```

---

## 4. Biological Interpretation

### 4.1 What Missed Synapses Simulate

During electron microscopy connectome reconstruction, a human proofreader or automated algorithm may fail to detect a synapse that genuinely exists. Reasons include:

- Low contrast in imaging at the synapse location
- Small synapse (few synaptic vesicles)
- Edge of imaging volume
- Segmentation error partially masking the synapse

**What the code simulates:**  
Each synapse is treated as an independently detectable unit. Each one has a probability of being "missed" by the reconstruction pipeline. That probability is higher for edges with fewer synapses (harder to detect a weak connection if some of its evidence is lost) and for connections between low-degree neurons (isolated neurons may be less carefully proofread).

**Example:**

```
Original reconstruction:
   Neuron A ────[8 synapses]────▶ Neuron B

                 ↓ binomial sampling, p_survive = 0.85 per synapse

Possible outcome (binomial draw = 6):
   Neuron A ────[6 synapses]────▶ Neuron B    ← edge preserved, weight reduced

Possible outcome (binomial draw = 0):  [only for weak edges]
   Neuron A                   Neuron B        ← edge deleted entirely
```

**Why edges are rarely fully deleted:**  
For an edge with n synapses and removal probability p, the probability that ALL n synapses are missed is p^n. At p=0.20 and n=8, that probability is 0.20^8 = 0.000025% — essentially impossible. Only edges with 1 or 2 synapses have a realistic chance of full deletion.

---

### 4.2 What False Synapses Simulate

During reconstruction, the segmentation algorithm may incorrectly merge parts of two different cells, or a proofreader may incorrectly annotate a contact as a synapse when it is not. This creates an edge in the reconstruction that has no biological reality.

**What the code simulates:**  
False synapses are most likely between neurons that already share circuit context — neurons projecting to similar targets. The code uses this biological prior (Jaccard overlap) to select which phantom connections to inject.

**Example:**

```
Biological reality:
   Neuron A ────▶ Neuron C
   Neuron B ────▶ Neuron C
   (A and B share postsynaptic target C)

   Neuron A   ✗   Neuron B    ← NO real connection

Reconstruction error (false synapse injected):
   Neuron A ────[3 synapses]────▶ Neuron B   ← phantom connection added
```

The weight (3 synapses) is drawn from the empirical distribution of weak edges in the real dataset (syn_count ≤ 5), because false positives are assumed to look like weak connections.

---

## 5. Why Experimental Results Behave This Way

### 5.1 Why Missed Synapses: −20% synapses but only −3.2% edges

**Root cause: binomial thinning of synapse counts vs. full-edge deletion probability**

The model removes synapses independently. At 20% error rate, every synapse has a ~20% removal probability. For an edge with n synapses, the probability that the edge is completely deleted is approximately `p^n`.

The BANC dataset has a very heavy-tailed synapse-count distribution. The majority of edges (≈71.5%) have ≤5 synapses, but those weak edges carry relatively few total synapses. The strong edges (high syn_count) carry most of the synapse mass but are almost never deleted.

| n (synapses) | P(edge deleted) at p=0.20 |
|---|---|
| 1 | 0.200 (20%) |
| 2 | 0.040 (4%) |
| 3 | 0.008 (0.8%) |
| 5 | 0.0003 (0.03%) |
| 10 | < 0.000001% |

So the −20% effect on total synapse count comes from reducing the weight of almost every edge, while edge deletion only occurs on edges with 1-2 synapses. Since the majority of edges have 3+ synapses, the edge count drops much less than the synapse count.

**Code evidence:**
```python
# model.py — the only edge deletion condition
edge_mask = surviving_synapses > 0
```
An edge survives as long as even one synapse survives. The weight may drop from 20 to 16, but the edge remains.

---

### 5.2 Why False Synapses: +20% edges but only +10% synapses

**Root cause: k is computed from edge count, but weights are drawn from the weak-edge distribution**

```python
# model.py — k computation
k = round(error_rate * total_edges)    # at 20%: 0.20 × 4M = 800,000 new edges
```

Each of these 800,000 new edges gets a weight drawn uniformly from the empirical distribution of edges with `syn_count ≤ 5`. The mean of that distribution is somewhere around 2-3 synapses.

Meanwhile, the original graph has an average edge weight higher than 5 (because the distribution is heavy-tailed — some edges have hundreds of synapses pulling the mean up).

So: adding 20% more edges (each with ~2-3 synapses) to a graph where average weight is higher results in a synapse increase well below 20%.

**Code evidence:**
```python
# weight_assignment.py
arr = graph.es["syn_count"]
weak = arr[arr <= 5]           # only uses weak-edge values
return int(rng.choice(weak))   # uniform choice from this subset
```

---

## 6. Code Verification

### ✔ Does the implementation match the intended biological model?

**Mostly yes, with caveats:**

- H1 ("errors occur at synapse level, edges never directly removed") is enforced in the model — edges are only deleted as a consequence of all synapses being lost, never directly.
- H2 ("fewer synapses = more vulnerable") is implemented via inverted normalization of `syn_count`.
- H3 ("sparse neurons more susceptible") is implemented via inverted normalization of degree features.
- H4 ("stochastic") is implemented via `rng.binomial`.
- H5 ("never invent edges") is upheld in missed synapses but is **explicitly violated** in false synapses by design — which is the point of that model.

---

### ✔ Are there logical mistakes?

**One notable issue in the vulnerability model:**

The vulnerability score is a **weighted linear combination without normalization of the final score**. At default weights (all 1.0), the score ranges roughly from 0 to 3. The calibrator divides by the weighted sum, which compensates. However, if weights are changed in config, the effective scale of contributions from each feature changes in a non-obvious way. There is no validation that the weights sum to 1.0 or that they are positive.

**One notable issue in candidate generation:**

```python
# candidate_generator.py L277-279
if (pre_b, pre_a) in edge_weight and cfg.get("redundancy_filter", True):
    # For redundant pairs, keep the direction with higher J_out.
    pass   # ← the 'pass' means NOTHING is done here
```

The comment says "keep the direction with higher J_out" but the `pass` statement does nothing. Both directions of an existing edge should be filtered, but only `(pre_a, pre_b)` is checked as a direct existing edge (line 275). The reversed direction check on line 277 does not filter the candidate — it just falls through to normal processing. This means a candidate `(pre_a, pre_b)` can be generated even when the reverse connection `(pre_b, pre_a)` already exists. Whether this is intentional is ambiguous.

---

### ✔ Are there hidden assumptions?

1. **Equal synapse survival probability per edge:** Within a single edge, all synapses get the same `calibrated_removal_probability`. The biological reality might be that some synapses on the same axon-dendrite pair are more detectable than others, but the code cannot represent this.

2. **The weight distribution for false synapses is static:** `_empirical_weights` is a module-level cache populated once. If the distribution of the baseline graph changes between preprocessing calls (unlikely but possible in testing), the cached value persists.

3. **Top-pool bias in false synapse sampling:** The sampling pool is the **top** `k×2` candidates (not a random sample of all candidates). This means false synapses are always drawn from the highest-Jaccard pairs. At low error rates, only the very highest-scoring candidate pairs are ever selected. At high error rates, the pool expands. The pool never covers the full candidate table's tail.

4. **The vulnerability score is dataset-relative:** A "highly vulnerable" edge in a dense dataset may have more synapses than a "low vulnerability" edge in a sparse dataset. The model cannot be directly compared across datasets without acknowledging this.

5. **Regions with < 10 neurons are entirely skipped** for false synapse candidate generation. Any false synapses that would plausibly connect to those regions cannot be represented.

---

### ✔ Are probabilities normalized correctly?

**Missed synapses:** Yes. The calibrator's iterative algorithm guarantees `sum(p × syn_count) ≈ target × total_synapses`. The final clip to [0.0, 1.0] is a correctness guarantee. The QC gate in `_perturb` is a second-layer check with tolerance ±0.005.

**False synapses:** Sampling probabilities are:
```python
p = weights[:pool_size] / weights[:pool_size].sum()
```
This is a proper normalization. If all `jaccard_out` values in the pool are 0 (which cannot happen given the `jaccard_min = 0.001` filter), the code falls back to `weights = None` (uniform sampling). So normalization is handled correctly.

---

### ✔ Are edge weights handled correctly?

**Missed synapses:**  
`weight_updates` maps baseline edge index → new weight. The runner translates baseline indices to subgraph indices via `baseline_to_subgraph`. If an edge was deleted (mask=False), its baseline index will not be in the subgraph translation map, and the runner silently skips the update with `continue`. This is correct.

**False synapses:**  
Added edges are appended to the temp graph. Their weights are set using:
```python
base_count = temp_graph.ecount() - len(added_weights_list)
```
This assumes the added edges are the **last N edges** in the graph. This is true because `add_edges()` appends to the end, and no subsequent edge additions occur. Correct.

---

### ✔ Are there possible biases?

1. **Vulnerability score bias toward low-degree neurons:** Because degree is inverted, neurons with degree 1 or 2 contribute much more to a high vulnerability score than neurons with hundreds of connections. This may overfit to peripheral or weakly-connected neurons.

2. **False synapse bias toward high-Jaccard pairs:** Because sampling is weighted by `jaccard_out` AND the pool is pre-filtered to the top-K by `jaccard_out`, the false edges are doubly biased toward highly-overlapping neuron pairs. The tail of the candidate distribution (plausible but lower-overlap pairs) is almost never selected, especially at low error rates.

3. **Region-partitioned candidate generation:** Candidates are only generated between neurons within the same anatomical region. Cross-region false synapses are impossible by construction. This may be biologically appropriate but is an implementation assumption that could affect results in datasets with significant cross-region connectivity.

---

## 7. Possible Limitations

| Limitation | Location in Code | Impact |
|---|---|---|
| Vulnerability weights default to 1.0 if not in config | `biology.py L47-49` | All three features contribute equally — may not be biologically justified |
| Weight threshold (≤5) is a modelling assumption, not empirically verified | `config.py L45`, `weight_assignment.py L16` | False synapse weights may not reflect actual error distribution |
| `pass` in redundancy filter does nothing | `candidate_generator.py L277-279` | May generate candidates where reverse edge exists |
| Unused features in EdgeFeatureTable | `biological_features.py` | `reciprocal`, `source_pagerank`, `target_pagerank` are extracted but never used by VulnerabilityModel |
| Module-level caches | `model.py` (`_candidate_table`), `weight_assignment.py` (`_empirical_weights`) | Shared state across trials; not thread-safe |
| No cross-region false synapses | `candidate_generator.py L243-247` | Systematically underrepresents inter-region errors |

---

## 8. Scientific Assessment

### Missed Synapses Model

**Strengths:**
- Biologically principled: models each synapse as independently detectable, which is consistent with how EM reconstruction errors actually occur.
- Calibration ensures exact expected error rates — results are reproducible and comparable across error rates.
- The QC hard-rejection gate prevents silently wrong trials.
- The baseline graph is immutable — no possibility of data corruption across trials.

**Weaknesses:**
- The vulnerability model is biologically motivated but not empirically validated on known reconstruction error data. There is no ground truth comparison for the weights.
- All synapses on an edge share the same removal probability — within-edge spatial heterogeneity cannot be modelled.
- At low error rates, the calibration may produce very small probabilities for high-syn_count edges, making them effectively immune to perturbation. This is a design choice, not a bug.

### False Synapses Model

**Strengths:**
- Biologically motivated candidate generation (circuit overlap as prior for plausible false positives).
- Jaccard-weighted sampling produces structurally coherent false edges — not random noise.
- Baseline graph is never mutated; the model is fully reversible.

**Weaknesses:**
- The `pass` in the redundancy filter (L277-279) is a documented but unimplemented feature.
- The weight distribution (≤5 syn_count) is stated as a modelling assumption, not a verified property. The code documentation explicitly says: *"It is NOT a biologically verified property of false-positive errors."*
- The double bias (pool restricted to top-K, then weighted by Jaccard) means extremely strong-overlap pairs dominate at all error rates, potentially creating unrealistic clustering of false connections.
- `k = round(error_rate × total_edges)` means k scales with the number of edges, not the number of synapses. This makes the rate interpretation different between the two models (one is defined in terms of synapses, the other in terms of edges), which is an important asymmetry when comparing their effects.

### Summary Comparison

| Property | Missed Synapses | False Synapses |
|---|---|---|
| Rate definition | Fraction of **synapses** removed | Fraction of **edges** added |
| Selection | Biologically-weighted (vulnerability) | Biologically-weighted (Jaccard) |
| Sampling | Binomial per edge | Weighted without-replacement |
| Weight outcome | Reduced by binomial draw | Sampled from weak-edge distribution |
| Edge deletion | Only if all synapses lost | N/A |
| Graph mutation | Never (subgraph view) | Never (copy + add) |
| Baseline graph | Immutable | Immutable |
| Trial-to-trial variance | Stochastic (binomial) | Stochastic (sampling) |
| Hard QC gate | Yes (RuntimeError) | No |
