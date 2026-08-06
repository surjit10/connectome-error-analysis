# Q&A Cheat Sheet — Professional Answers to Likely Questions

**Style:** concise, scientific, concrete. Each answer gives the logic and, where relevant, the number. For deeper technical detail, refer to the code or `correction.md`.

---

## 1. Why study the impact of reconstruction errors on connectome analysis?

Because connectome reconstruction is inherently imperfect — errors arise during imaging, segmentation, and proofreading. Any analysis performed on a reconstructed connectome inherits those errors. Understanding **how and how much errors distort graph metrics** tells researchers which conclusions are trustworthy and which error types to prioritize correcting. This is a reliability question at the heart of the field.

---

## 2. What distinguishes "missed" from "false" synapses?

Two independent error classes:

- **Missed synapses (false negatives):** genuine connections that the reconstruction fails to detect. We model per-synapse survival as an independent binomial trial with probability (1 − rate); edge weight becomes the surviving count, and an edge is removed only if its weight reaches zero.
- **False synapses (false positives):** connections that do not exist biologically but appear in the reconstruction. We add k = rate × edge_count artificial edges, each weighted from the empirical distribution of weak edges (≤5 synapses).

They are complementary failure modes with different graph signatures, which is why we test them separately.

---

## 3. Why is synapse loss exactly proportional to the error rate?

By construction, not by coincidence. The missed-synapse model applies an independent binomial survival trial to every synapse with success probability (1 − rate). In expectation, and closely in practice (within 0.01%), the fraction of removed synapses equals the rate. This was a deliberate design choice: the model behaves as an unbiased random process, so any downstream distortion is attributable to the error itself, not to model artifacts.

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
