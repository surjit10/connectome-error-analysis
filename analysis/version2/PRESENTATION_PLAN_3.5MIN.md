# Master 3.5-Minute Presentation Architecture & Execution Plan

**Topic**: How Reconstruction Errors Affect the FlyWire Connectome  
**Author**: Surjit Mandal  
**Target Duration**: Strictly 3 Minutes 30 Seconds (210 Seconds)  
**Total Slides**: 6 Slides (Clean, Uncluttered, High-Impact)  
**Pacing**: ~125 words per minute (~440 words total)  
**Location**: `/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2/PRESENTATION_PLAN_3.5MIN.md`

---

## 1. Core Structure (6-Slide Blueprint)

```
┌───────────┬─────────────────────────────────────────────────┬──────────┬────────────┐
│ TIMESTAMP │ SLIDE TITLE                                     │ DURATION │ WORD COUNT │
├───────────┼─────────────────────────────────────────────────┼──────────┼────────────┤
│ 0:00-0:25 │ 1. Research Overview & Benchmark Design         │  25 sec  │  ~55 words │
│ 0:25-1:00 │ 2. Global Error Comparison                      │  35 sec  │  ~75 words │
│ 1:00-1:40 │ 3. Finding 1: Missed Synapse Analysis           │  40 sec  │  ~85 words │
│ 1:40-2:20 │ 4. Finding 2: Split vs Merge Comparison         │  40 sec  │  ~85 words │
│ 2:20-3:00 │ 5. Finding 3: Centrality & Connectome Comparison│  40 sec  │  ~80 words │
│ 3:00-3:30 │ 6. Proofreading Priorities & Summary            │  30 sec  │  ~60 words │
├───────────┴─────────────────────────────────────────────────┼──────────┼────────────┤
│ TOTAL PRESENTATION TIME                                     │ 3:30 min │ ~440 words │
└─────────────────────────────────────────────────────────────┴──────────┴────────────┘
```

---

## 2. Slide Details & Narrative Flow

### Slide 1: Research Overview & Benchmark Design (`0:00 - 0:25`)
- **Hook**: When automated machine-learning models reconstruct brain wiring diagrams from EM images, errors are introduced.
- **Presenter**: **Surjit Mandal**, Computational Neuroscience & Connectomics.
- **Question**: How much do these errors alter graph-level properties, and which error types have the largest structural impact?
- **Scope**: 5 Drosophila Connectomes (BANC, FAFB, MANC, MCNS, MAOL), 5 Error Models (0% to 20%), 1,030 independently seeded simulation runs.

### Slide 2: Global Error Comparison (`0:25 - 1:00`)
- **Question**: Which error types alter overall graph structure, and which have limited topological impact?
- **Result**: Synapse count jitter and cell splits preserve the number of edges in tested simulations. Merged neurons produced the largest structural changes (-10.9% edges, +46.9% weight variance).
- **Takeaway**: Connectome graph structure is highly stable under scalar counting noise, but acutely sensitive to node merging.
- **Embedded Figure**: `figures/clean_fig_global_fingerprints.png`

### Slide 3: Finding 1 — Missed Synapse Analysis (`1:00 - 1:40`)
- **Question**: If automated detection misses 20% of synapses, does the graph lose 20% of its connections?
- **Result**: Total synapses drop linearly (-20.0%), but edge count drops only -4.87% (4x buffering effect).
- **Takeaway**: In the modeled connectomes, many edges contain multiple synapses ($P = p^w$). Higher-weight connections are less likely to disappear under independent synapse loss.
- **Embedded Figure**: `figures/clean_fig_binomial_buffering.png`

### Slide 4: Finding 2 — Split vs Merge Comparison (`1:40 - 2:20`)
- **Question**: How do graph metrics respond to over-segmentation (splits) versus under-segmentation (merges)?
- **Result**: Splits conserve 100% of edges; Merges combine two neurons into a single node, deleting -10.9% of edges and increasing weight variance by +46.9%.
- **Takeaway**: Merging substantially alters connectivity and weight distributions far more than splitting.
- **Embedded Figure**: `figures/clean_fig_split_vs_merge.png`

### Slide 5: Finding 3 — Centrality & Connectome Comparison (`2:20 - 3:00`)
- **Question**: Are neuron importance rankings reliable, and why do connectomes respond differently?
- **Result**: Global PageRank rankings remain highly correlated with baseline ($r \ge 0.98$ to $0.999$). Connectomes with higher median connection strength (MCNS, median 9.0) showed greater resistance to edge loss (0.007%) than sparser circuits (MANC, median 2.0, -9.7% edge loss).
- **Takeaway**: Node centrality rankings show high stability; higher connection strength increases resistance to edge loss.
- **Embedded Figure**: `figures/clean_fig_pagerank_and_median_law.png`

### Slide 6: Proofreading Priorities & Summary (`3:00 - 3:30`)
- **Primary Conclusion**: These results suggest prioritizing evaluation of merge and missed-synapse errors when preserving graph topology is the objective.
- **Sensitivity Indicator**: Weight variance showed high sensitivity across error models (-30.3% to +46.9%), reflecting changes in weight distributions before binary edge counts change.
