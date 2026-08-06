# Presentation Script — Impact of Reconstruction Errors on Connectome Graph Analysis

**Deck:** `main.pdf` (13 slides) · **Target:** ~6 minutes · **Format:** professional talk track, ~150 words/min

---

## Slide 1 — Title (~15 s)

> Good morning, everyone. Today I'll present an experimental study on how **reconstruction errors in connectome data** propagate into downstream graph analysis.
>
> Specifically, we quantify the impact of two common error types — **missed synapses** and **false synapses** — on the structural and functional properties of a real biological connectome.

---

## Slide 2 — Problem Overview (~30 s)

> The motivation is straightforward. Connectome reconstruction is an imperfect pipeline: errors arise during imaging and automated proofreading, and every error changes the graph we analyze.
>
> The core question: **to what extent do these errors distort the conclusions drawn from connectome graph analysis?**
>
> Our approach: take a real, neuron-resolved connectome — the BANC dataset, with 158,262 neurons and 3,990,039 connections — apply controlled errors at known rates, run a comprehensive battery of graph analyses, and compare every output against the error-free baseline.

---

## Slide 3 — Two Error Models (~40 s)

> We model the two fundamental error classes separately, because they have different biological origins and different graph signatures.
>
> **Missed synapses — false negatives.** Each synapse on a connection survives independently with probability (1 − rate), modelled as a **binomial process**. The edge weight becomes the number of surviving synapses, and an edge is removed only if all of its synapses are lost. This mirrors proofreading errors that under-count connectivity.
>
> **False synapses — false positives.** We add k artificial connections, where k = rate × baseline edge count. Each added edge receives a **low weight sampled from the empirical distribution of weak edges** (≤5 synapses), reflecting that spurious reconstructions are typically weak.

---

## Slide 4 — Experimental Setup (~30 s)

> The design is designed for statistical robustness. We use the **BANC** connectome, a *Drosophila melanogaster* brain and nerve cord, and test **ten error rates** ranging from 0.25% to 20%, with **five seeded trials per rate** to ensure reproducibility.
>
> The pipeline is fixed across all runs: load dataset → build graph → preprocess → apply error model → analyze → compute statistics → export.
>
> Each trial takes approximately 3 minutes, roughly **5 hours total** for the full sweep of 100 runs.

---

## Slide 5 — Evaluation Metrics (~25 s)

> To capture the impact comprehensively, we compute **49 graph metrics**, grouped into five biological families: **topology** (edges, density, degree distributions), **connectivity** (weak/strong components), **synaptic properties** (weight statistics), **network organization** (reciprocity, assortativity, PageRank), and **similarity** (KS and Wasserstein distances, correlation measures).
>
> Every metric is evaluated against baseline with 95% confidence intervals across the five trials.

---

## Slide 6 — Missed Synapses Results (~40 s)

> Under missed synapses, the primary effect is a **predictable, linear erosion of the synaptic layer**. Synapse loss is exactly proportional to the rate — 20% error removes 20.0% of synapses — confirming the model behaves as intended.
>
> Critically, the structural layer is largely preserved: edge count drops only 3.2%, the giant strongly-connected component retains **99.95% of its vertices**, reciprocity shifts by only 0.6%, and PageRank correlation remains at 0.997.
>
> The interpretation: missed synapses degrade **fine-grained synaptic statistics while leaving the global wiring architecture effectively intact**.

---

## Slide 7 — False Synapses Results (~40 s)

> False synapses produce the opposite pattern: the graph is **inflated rather than eroded**. At 20% error, edge count increases by exactly 20% and total synapse count by 10%.
>
> The added edges are weak — a mean weight of approximately 3 synapses versus the baseline mean of 5.9 — so they dilute the weight distribution rather than creating dominant hubs.
>
> The structural distortion, however, is substantial: the **degree distribution is distorted approximately 15× more** than under missed synapses at the same rate, and hub-ranking fidelity erodes — top-k overlap falls to 0.89, versus 0.97 for missed.

---

## Slide 8 — Comparison (~35 s)

> At identical nominal rates, the two models are clearly distinguishable in their signatures.
>
> **Missed synapses contract the graph**: −20.0% synapses, −3.2% edges, reciprocity essentially flat.
>
> **False synapses expand it**: +20.0% edges, +10.0% synapses, reciprocity up 7.1%, and even the giant component grows by 0.4% as added edges bridge previously separate components.
>
> At equal error magnitude, **false synapses are the more disruptive model** — every structural effect is larger in magnitude.

---

## Slide 9 — Category-wise Preservation (~35 s)

> To make the comparison scientifically interpretable, we summarize preservation per biological category rather than as a single aggregate.
>
> **Structural topology** is preserved at 97.9% under missed synapses but only 88.9% under false — adding edges disturbs the wiring plan more than removing synapses does.
>
> **Synaptic properties** are the most sensitive category: 83.1% preserved under missed synapses, driven by weight variance (69%) and median weight (75%).
>
> **Connectivity** and **network organization** remain above 95% under both models. In short: global architecture is robust; the synaptic layer degrades first.

---

## Slide 10 — How Preservation Is Calculated (~25 s)

> One methodological note for transparency. Each metric is converted to a preservation score using the **symmetric ratio**: min(baseline, perturbed) ÷ max(baseline, perturbed) × 100. This treats deviations in either direction — loss *or* gain — as damage.
>
> Category preservation is then the **unweighted arithmetic mean** of its member metrics. No weighting or adjustment is applied; every value shown is reproducible from the raw metric-level data.

---

## Slide 11 — Reliability of the Results (~25 s)

> The results are statistically stable. We ran **five seeded trials per rate**, producing 490 aggregated rows per model.
>
> Inter-trial spread is minimal: the standard deviation is approximately **0.01% of the mean** for the primary metrics, and false-synapse injection is **deterministic** — zero variance across trials.
>
> All primary trends are **monotone** across the ten rates with no dips, and the impact-status classifications are consistent across trials.

---

## Slide 12 — Conclusions (~35 s)

> Four conclusions follow directly from the data.
>
> **First**, reconstruction errors produce direct, measurable effects — synapse loss and edge gain are exactly proportional to the rate, and these are the most sensitive quantities we measured.
>
> **Second**, global topology is highly robust — the giant component and node count remain above 99%, and PageRank correlation stays ≥0.98 even at 20% error.
>
> **Third**, false synapses are the more disruptive error type — they distort degree distributions 14–27× more and erode hub-ranking fidelity.
>
> **Fourth**, the two error types leave **separable signatures**: missed synapses deflate synaptic statistics, while false synapses inflate the graph with weak edges.

---

## Slide 13 — Summary (~25 s)

> In summary: reconstruction errors degrade **synaptic statistics first**, while the coarse wiring architecture remains stable.
>
> The practical implication for connectome analysis: **false-positive errors warrant greater caution** — at equal rates they distort the graph more than missed synapses, so downstream analyses should account for error type when assessing reliability.
>
> Thank you — I'm happy to take questions.

---

## Delivery Notes

- **Pace:** one slide per 30 seconds on average; pause briefly on slides 6–9 (the results).
- **Numbers to state with confidence:** −20.0% vs +20.0% (proportionality), 99.95% SCC retention, 15× KS distortion at 20%, and the category values on slide 9.
- **Shorten to 5 min:** compress slides 4–5 and 10–11 to a single line each (setup + methodology).
- **If pressed on the CSVs:** the exported `combined_results.csv` files carry older weight/assortativity values; the slides use the framework's current formula (see `correction.md`). Re-running the export regenerates matching CSVs.
