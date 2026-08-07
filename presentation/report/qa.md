# Q&A Cheat Sheet — Professional Answers to Likely Questions

**Style:** concise, scientific, concrete. Each answer gives the logic and, where relevant, the number. For deeper technical detail, refer to the code or `correction.md`.

---

## 1. Why study the impact of reconstruction errors on connectome analysis?

Because connectome reconstruction is inherently imperfect — errors arise during imaging, segmentation, and proofreading. Any analysis performed on a reconstructed connectome inherits those errors. Understanding **how and how much errors distort graph metrics** tells researchers which conclusions are trustworthy and which error types to prioritize correcting. This is a reliability question at the heart of the field.

---

## 2. What distinguishes "missed" from "false" synapses?

Two independent error classes with entirely different code paths:

**Missed synapses (false negatives) — `modules/error_models/missed_synapses/model.py`:**

1. **Preprocessing (Phases 012–014):** Each edge's `raw_vulnerability_score` is computed as a weighted linear combination of three inverted, min-max-normalised biological features: synapse count, source-neuron degree, and target-neuron degree — edges with few synapses connecting low-degree neurons score highest. The `ProbabilityCalibrator` (Phase 014) then scales these scores with an iterative mass-redistribution algorithm so that the expected synapse loss matches the target error rate exactly, producing a `calibrated_removal_probability` per edge.

2. **Perturbation (Phase 015):** For every edge, the code draws `surviving_synapses = rng.binomial(n=syn_count, p=1.0 - calibrated_removal_probability)`. An edge is **deleted** only if `surviving_synapses == 0`; otherwise its weight is updated to the surviving count. After sampling, the code verifies that the achieved removal rate is within ±0.5 percentage points of the target.

**False synapses (false positives) — `modules/error_models/false_synapses/model.py`:**

1. **Preprocessing (one-time, `CandidateGenerator`):** For each anatomical region the code builds an **inverted successor index** (postsynaptic target → list of its presynaptic neurons). Every pair (pre_a, pre_b) that share at least one common postsynaptic target and do **not** already form an edge is kept as a candidate. Each candidate is scored by `jaccard_out = |succ(pre_a) ∩ succ(pre_b)| / |succ(pre_a) ∪ succ(pre_b)|`. Pairs with `jaccard_out < 0.001` are discarded. The top-K per region (default: `50 × region_size`) are written to `candidates.parquet`.

2. **Perturbation (per trial):** The code computes `k = round(error_rate × total_edges)` — the number of false edges to inject. It takes a sampling pool of `min(len(candidates), max(k×2, 1000))` top candidates, then draws k without replacement, with sampling probability proportional to `jaccard_out`. Each selected candidate gets a weight sampled uniformly from the empirical distribution of real edges with `syn_count ≤ 5` (≈71.5% of BANC edges). The resulting `(pre_root_id, post_root_id, weight)` triples are returned in `result.added_edges` — the baseline graph is **never mutated**.

They are complementary failure modes: missed synapses reduce edge weights via binomial thinning, false synapses inject new structurally plausible edges ranked by Jaccard connectivity overlap.

---

## 3. Why is synapse loss exactly proportional to the error rate?

By construction, not by coincidence — and enforced at two levels in the code:

1. **Calibration (Phase 014, `ProbabilityCalibrator.calibrate`):** Before any trial runs, the calibrator sets a global scaling factor `alpha = target_synapse_drops / (raw_vulnerability × syn_count).sum()` and then multiplies each edge's raw vulnerability score by alpha to produce `calibrated_removal_probability`. If any edge's probability exceeds 1.0, it is clamped to 1.0 and the residual mass is redistributed to uncapped edges in a loop (up to 50 iterations, convergence tolerance 1e-6). This guarantees that `sum(calibrated_removal_probability × syn_count) ≈ target_error_rate × total_synapses` before sampling begins.

2. **Quality control (Phase 015, `MissedSynapsesModel._perturb`):** After binomial sampling, the code computes `achieved_error_rate = (total_original - total_surviving) / total_original` and raises a `RuntimeError` if the deviation from the target exceeds the configured tolerance (default ±0.5 percentage points). This is a hard rejection gate, not just a log warning.

The achieved rate lands within 0.01% of the target in practice because the calibrated probabilities are precisely constructed to make the binomial expectation hit the target, and the large sample size (millions of synapses) means variance around that expectation is negligible.

---

## 4. Why are false synapses more disruptive than missed synapses?

Because of how each error type interacts with graph structure:

- **Missed synapses remove information** — the underlying connectivity skeleton is preserved, so structural metrics (components, PageRank) barely move; only synapse-level statistics erode.
- **False synapses inject new structure** — added edges create new connections and bridges, altering degree distributions and component structure directly.

Quantitatively, at 20% error the degree-distribution distortion (KS distance) is ~15× larger for false synapses, and hub-ranking fidelity (top-k overlap) drops to 0.89 versus 0.97. Adding spurious structure perturbs a network more than removing existing structure.

---

## 5. Why is global topology robust while fine details are fragile?

Connectomes are characterized by **redundant, densely-connected wiring**. Removing a fraction of synapses rarely disconnects the giant component because multiple alternative paths exist; at 20% error the SCC retains 99.95% of vertices. Fine-grained metrics — per-edge synapse counts, weight variance — have no redundancy: any loss appears immediately. This is a scale-dependent robustness property: aggregate structure is stable, local statistics are sensitive.

---

## 6. How is preservation computed?

For each metric, we compute a symmetric preservation score:

Preservation (%) = min(baseline, perturbed) ÷ max(baseline, perturbed) × 100

The symmetric form is essential: it treats an *increase* and a *decrease* as equivalent damage, which matters for additive error models like false synapses, where metrics rise above baseline. Category values are the unweighted arithmetic mean of their member metrics. No weighting, no normalization — fully reproducible from the raw CSV values.

---

## 7. Why are synaptic properties the most sensitive category?

Synaptic statistics are exact, non-redundant counts at the edge level. Under missed synapses, 20% of synapses are removed directly, so weight-based metrics move in proportion: weight variance preserves only 69%, median weight 75%, and total synapses 80% at 20% error. Aggregate structural metrics (component sizes, node counts) are stable averages of huge populations and shift far less. Sensitivity scales with the granularity of the measurement.

---

## 8. Why five trials, and how reliable are the results?

Because the error models are stochastic, a single run could be unrepresentative. Five independent seeded trials quantify inter-trial variability. Measured spread is ~0.01% of the mean for primary metrics; false-synapse edge injection is deterministic (σ = 0 across trials). Primary trends are monotone across all ten rates with no dips. This is strong evidence the findings reflect the model dynamics, not sampling noise.

---

## 9. What are KS distance and top-k overlap?

Two standard comparison measures:

- **KS (Kolmogorov–Smirnov) distance:** quantifies the maximum divergence between two distributions — here, the degree distribution before and after error. It captures shape distortion of the network's wiring pattern.
- **Top-k overlap:** the fraction of the top-k most central vertices (by PageRank) that remain in the top-k after perturbation. It measures stability of importance rankings.

Both are commonly used in graph comparison; we use them as complementary views of structural change.

---

## 10. What role does PageRank play in the analysis?

PageRank assigns an importance score to each vertex based on recursive centrality — a neuron is important if important neurons connect to it. It provides a biologically meaningful ranking of neurons, and its stability under perturbation (correlation ≥0.98 even at 20% error) is one of our key robustness findings. Top-k overlap uses this ranking to measure hub-preservation.

---

## 11. What do reciprocity, assortativity, and SCC/WCC measure?

Standard network metrics:

- **Reciprocity:** the fraction of connections that are bidirectional (A→B and B→A both present).
- **Assortativity:** the tendency of vertices to connect to similar vertices (e.g., high-degree to high-degree).
- **SCC/WCC (strong/weakly connected components):** maximal sets of mutually reachable vertices — the effective "core" of the network.

These characterize network organization and connectivity, complementing the topological and synaptic metrics.

---

## 12. Would the conclusions generalize to other datasets or error models?

The *direction* of the findings reflects general network properties — redundancy, scale-dependent sensitivity — so it should transfer qualitatively. The *magnitudes* would differ with dataset size, density, and degree distribution; a sparser network may break down faster, a denser one may be more robust. Testing this generalization is a natural follow-up experiment, but the core insight — false structure is more disruptive than missing structure — is structural, not dataset-specific.

---

## 13. What is the practical takeaway for connectome analysis?

Prioritize removing false-positive connections in reconstruction, since they distort graph analysis more than missed synapses at equal rates. Additionally, treat synapse-level statistics as error-sensitive and aggregate structural metrics as error-tolerant. Knowing the dominant error type of a dataset allows appropriate confidence in downstream results.

---

## 14. Why the BANC dataset (Drosophila melanogaster)?

BANC is one of the few **complete, neuron-resolved connectomes** available — large enough to be biologically realistic (158k neurons, 4M connections) yet computationally tractable for 100 controlled trials (≈5 hours). Human-scale connectomes are several orders of magnitude larger and not yet amenable to this kind of controlled perturbation study.

---

## 15. How can the results be reproduced?

Everything derives from the exported result CSVs (`results/BANC/missed_synapses` and `results/BANC/false_synapses`); the figure-generation script reads them directly with no hardcoded values. One known caveat, documented in `correction.md`: the exported `combined_results.csv` files retain older weight/assortativity preservation values (frozen at 100%), while the slides use the framework's current preservation formula. Re-running the presentation export regenerates CSVs consistent with the slides.
