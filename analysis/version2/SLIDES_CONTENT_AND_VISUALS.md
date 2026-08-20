# 3.5-Minute Slide Deck: Content & Visual Blueprint

**Topic**: How Reconstruction Errors Affect the FlyWire Connectome  
**Author**: Surjit Mandal  
**Target Duration**: Strictly 3.5 Minutes (210 Seconds)  
**Aspect Ratio**: 16:9 Widescreen  
**Layout Scheme**: Professional Executive Light Mode (Nature/Science publication style), 2-Column Responsive Card Grid  
**Location**: `/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2/SLIDES_CONTENT_AND_VISUALS.md`

---

## SLIDE 1: Research Overview & Benchmark Design
`Timing: 0:00 - 0:25 (25s) | Category: RESEARCH OVERVIEW & BENCHMARK DESIGN`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ RESEARCH OVERVIEW & BENCHMARK DESIGN                                                   [0:00 / 3:30]   │
│ How Reconstruction Errors Affect the FlyWire Connectome                                                │
│ Measuring how wiring diagram errors change network structure across 5 fruit fly connectomes            │
├───────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ Surjit Mandal                                     │ THE FIVE ERROR TYPES TESTED                        │
│                                                   │                                                    │
│ WHY THIS MATTERS                                  │ 1. Missed Synapses (EM1):                          │
│ Automated AI tools make mistakes when mapping     │    The detector fails to spot a real connection.   │
│ brain wiring diagrams from EM images. This study  │ 2. False Synapses (EM2):                           │
│ tests how much these errors change network        │    The detector adds a fake connection.            │
│ connections, brain regions, and neuron rankings.  │ 3. Synapse Count Jitter (EM3):                     │
│                                                   │    Small counting errors in synapse numbers.       │
│ DATASETS TESTED                                   │ 4. Split Neurons (EM4):                            │
│ • 5 Drosophila Connectomes: BANC, FAFB, MANC,     │    A neuron gets broken into fragments.            │
│   MCNS, MAOL (24k to 167k neurons)                │ 5. Merged Neurons (EM5):                           │
│ • 1,030 simulation runs across 10 error levels    │    Two distinct neurons are joined into one node.  │
│                                                   │                                                    │
│ KEY PAPERS & REFERENCES                           │ MAIN GOAL                                          │
│ • Dorkenwald et al. Nature 2024 (FlyWire)         │ Provide clear sensitivity benchmarks showing how   │
│ • Buhmann et al. Nature Methods 2021 (Synapse)    │ each error type affects brain graph measurements.  │
│ • Januszewski 2018 | Takemura 2023 | Scheffer 2020│                                                    │
└───────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

- **Speaker Timing**: `0:00 - 0:25` (25 seconds)

---

## SLIDE 2: Global Error Comparison
`Timing: 0:25 - 1:00 (35s) | Category: GLOBAL ERROR COMPARISON`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GLOBAL ERROR COMPARISON                                                                [0:25 / 3:30]   │
│ How Each Error Type Changes the Graph                                                                  │
│ Comparing network changes across all 5 connectomes                                                     │
├───────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ OVERALL ERROR IMPACT                              │ EMBEDDED CLEAN FIGURE (clean_fig_global_fingerprints)│
│ Each error type produces a distinct pattern of    │                                                    │
│ change across the connectome.                     │ ┌────────────────────────────────────────────────┐ │
│                                                   │ │   [ HIGH-CONTRAST HORIZONTAL BAR CHART ]       │ │
│ RESULTS AT HIGHEST TESTED ERROR LEVEL (20%)       │ │                                                │ │
│ • Missed Synapses (n=5):  -4.9% Edges | -30.3% Var│ │ Shows distinct signature for each error model: │ │
│ • False Synapses  (n=3): +19.4% Edges | -13.8% Var│ │ • Count Noise: +0.03% Synapses (flat)          │ │
│ • Synapse Noise   (n=5):   0.0% Edges |  +5.5% Var│ │ • Merges: -10.9% Edges, +46.9% Weight Variance │ │
│ • Split Neurons   (n=5):   0.0% Edges |   0.0% Var│ └────────────────────────────────────────────────┘ │
│ • Merge Neurons   (n=4): -10.9% Edges | +46.9% Var│                                                    │
│                                                   │ MAIN TAKEAWAY                                      │
│ NOTE ON ERROR SCALING                             │ Synapse count noise and neuron splits do not change│
│ At typical residual error levels (2–5%), reported │ the total connections. Merged neurons caused the   │
│ average metrics change by less than 1% (n=3..5).  │ largest damage (-10.9% edges, +46.9% variance).    │
└───────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

- **Speaker Timing**: `0:25 - 1:00` (35 seconds)
- **Embedded Figure**: [`figures/clean_fig_global_fingerprints.png`](figures/clean_fig_global_fingerprints.png)

---

## SLIDE 3: Finding 1 — Missed Synapse Analysis
`Timing: 1:00 - 1:40 (40s) | Category: MISSED SYNAPSE ANALYSIS`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ MISSED SYNAPSE ANALYSIS                                                                [1:00 / 3:30]   │
│ Why Missed Synapses Do Not Proportionally Eliminate Connections                                        │
│ Connections with multiple synapses provide built-in protection against loss                            │
├───────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ SYNAPSE LOSS VS CONNECTION LOSS                   │ EMBEDDED CLEAN FIGURE (clean_fig_binomial_buffering) │
│ Evaluating whether losing 20% of synapses removes │                                                    │
│ 20% of graph connections.                         │ ┌────────────────────────────────────────────────┐ │
│                                                   │ │   [ ~4x BUFFERING ZONE SENSITIVITY PLOT ]      │ │
│ MAIN RESULTS                                      │ │                                                │ │
│ • Total Synapses: drop by ~20.0%                  │ │ • Red Curve : Total Synapses (-20.0% linear)   │ │
│ • Connection Count: drops by only -4.87% (~4x)    │ │ • Cyan Curve: Edge Count Loss (-4.87% buffered)│ │
│ • Largest Connected Core (SCC): shrinks by -0.04% │ │ • Green Zone: ~4x Buffering Zone               │ │
│                                                   │ └────────────────────────────────────────────────┘ │
│ WHY THIS HAPPENS                                  │                                                    │
│ Many connections have multiple synapses. An edge  │ MAIN TAKEAWAY                                      │
│ is only lost if every single synapse on it is     │ Connections with more synapses are strongly        │
│ missed (P = p^w).                                 │ protected from disappearing.                       │
└───────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

- **Speaker Timing**: `1:00 - 1:40` (40 seconds)
- **Embedded Figure**: [`figures/clean_fig_binomial_buffering.png`](figures/clean_fig_binomial_buffering.png)

---

## SLIDE 4: Finding 2 — Split vs Merge Comparison
`Timing: 1:40 - 2:20 (40s) | Category: SPLIT VS MERGE COMPARISON`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SPLIT VS MERGE COMPARISON                                                              [1:40 / 2:20]   │
│ Merging Neurons Produces Larger Changes in Edge Count and Weight Variance                              │
│ Neuron merges reduce edge count and strongly increase connection-weight variance                       │
├───────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ SPLITS VS MERGES                                  │ EMBEDDED CLEAN FIGURE (clean_fig_split_vs_merge)     │
│ Comparing what happens when neurons are split into│                                                    │
│ pieces vs when separate neurons are merged.       │ ┌────────────────────────────────────────────────┐ │
│                                                   │ │   [ SPLIT VS MERGE DIRECT COMPARISON BARS ]    │ │
│ HEAD-TO-HEAD AT HIGHEST TESTED ERROR LEVEL (20%)  │ │                                                │ │
│ Metric             | Split (n=5)  | Merge (n=4)   │ │ • Green Bars: Splits (100% edge preservation)  │ │
│ -------------------|--------------|-------------- │ │ • Coral Bars: Merges (-10.9% edges, +46.9% var)│ │
│ Edge Count Change  |     0.0%     |    -10.9%     │ └────────────────────────────────────────────────┘ │
│ Total Synapse Chg  |     0.0%     |     -0.1%     │                                                    │
│ Mean Degree        |    -14.9%    |     -2.6%     │ KEY TAKEAWAY                                       │
│ Largest SCC        |    +17.6%    |     -9.0%     │ Splitting redistributes existing connections across│
│ Weight Variance    |     0.0%     |    +46.9%     │ fragments while preserving total edge and synapse  │
│                                                   │ counts. Merging combines neurons, reducing edge    │
│                                                   │ count by 10.9% and increasing weight var by 46.9%. │
└───────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

- **Speaker Timing**: `1:40 - 2:20` (40 seconds)
- **Embedded Figure**: [`figures/clean_fig_split_vs_merge.png`](figures/clean_fig_split_vs_merge.png)

---

## SLIDE 5: Finding 3 — Centrality & Connectome Comparison
`Timing: 2:20 - 3:00 (40s) | Category: CENTRALITY & CONNECTOME COMPARISON`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CENTRALITY & CONNECTOME COMPARISON                                                     [2:20 / 3:30]   │
│ PageRank Remains Stable; Higher Connection Strength Is Associated With Lower Edge Loss                 │
│ PageRank similarity to baseline remains high (r >= 0.977); edge loss varies with median weight         │
├───────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ 1. PAGERANK SIMILARITY REMAINS HIGH               │ EMBEDDED CLEAN FIGURE (clean_fig_pagerank_median)    │
│ • PageRank remains highly correlated with baseline│                                                    │
│   across tested error models (r ≈ 0.977–1.000).   │ ┌────────────────────────────────────────────────┐ │
│ • Node importance rankings resist perturbation.   │ │ [ LEFT: PageRank Correlation (r >= 0.977) ]    │ │
│                                                   │ │ [ RIGHT: Scatter: Edge Change vs Median W ]    │ │
│ 2. HIGHER CONNECTION STRENGTH -> LOWER EDGE LOSS  │ │ • MCNS (med 9.0) -> -0.007% edge count change  │ │
│ • MCNS (med 9.0): -0.007%  | FAFB (med 6.0): -2.5%│ │ • MANC (med 2.0) -> -9.73% edge count change   │ │
│ • BANC (med 4.0): -3.19%   | MAOL (med 2.0): -8.9%│ └────────────────────────────────────────────────┘ │
│ • MANC (med 2.0): -9.73%                          │                                                    │
│                                                   │ MAIN TAKEAWAY                                      │
│ Note: Observations reflect cross-connectome       │ PageRank similarity to baseline remains high while │
│ associations across the 5 tested datasets.        │ edge loss varies with median connection weight.    │
└───────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

- **Speaker Timing**: `2:20 - 3:00` (40 seconds)
- **Embedded Figure**: [`figures/clean_fig_pagerank_and_median_law.png`](figures/clean_fig_pagerank_and_median_law.png)

---

## SLIDE 6: Secondary Effects of Reconstruction Errors
`Timing: 3:00 - 3:30 (30s) | Category: SECONDARY ERROR FINGERPRINTS`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SECONDARY ERROR FINGERPRINTS                                                           [3:00 / 3:30]   │
│ Secondary Effects of Reconstruction Errors                                                             │
│ Different reconstruction errors leave different fingerprints beyond the quantity directly perturbed. │
├───────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ 1. MISSED SYNAPSES   [Direct: -20% synapses]      │ 4. SPLIT ERRORS      [Direct: Nodes split]         │
│ SECONDARY EFFECT: Connections & global routing are│ SECONDARY EFFECT: Connections preserved, but partner│
│ much more preserved than synapse loss suggests.   │ redistribution dilutes degree & alters components. │
│ Evidence: -20.0% syn | -4.9% edges | r = 0.999    │ Evidence: 0.0% edge loss | -14.9% deg | +17.6% SCC │
├───────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ 2. FALSE SYNAPSES    [Direct: Candidate edges]    │ 5. MERGE ERRORS      [Direct: Nodes combined]      │
│ SECONDARY EFFECT: Weak additions expand edge count│ SECONDARY EFFECT: Collapses distinct edges into    │
│ far more than synapse mass while increasing recip.│ heavier connections, shrinking component size.     │
│ Evidence: +19.4% edges | +7.6% syn | -13.8% var   │ Evidence: -0.1% syn | -10.9% edges | +46.9% var    │
├───────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ 3. SYNAPSE-COUNT NOISE [Direct: Weights perturbed]│ KEY QUALITY-CONTROL TAKEAWAY                       │
│ SECONDARY EFFECT: Topology-based QC completely    │ Each error leaves a distinct secondary fingerprint │
│ misses this error; weight statistics shift.       │ (loss, weak dilution, distortion, dilution, merge).│
│ Evidence: 0.0% edge/node change | +5.5% weight var│ Joint multi-level assessment is required.          │
└───────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

- **Speaker Timing**: `3:00 - 3:30` (30 seconds)

---

## SLIDE 7: Appendix — Complete 5-Connectome Breakdown Table
`Timing: Q&A / Reference | Category: APPENDIX & FULL DATASET COMPARISON`

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ APPENDIX & FULL DATASET COMPARISON                                                     [Q&A / Backup]  │
│ Individual Connectome Breakdown Table                                                                  │
│ Comparing exact Δ Edge Count and metrics across BANC, FAFB, MANC, MCNS, and MAOL (at 20% Peak Error)   │
├───────────────────────────────────────────────────┬────────────────────────────────────────────────────┤
│ 1. MISSED SYNAPSES (EM1) BREAKDOWN                │ 3. FALSE SYNAPSES (EM2) BREAKDOWN                  │
│ • BANC (med 4.0): -3.19% edges | r = 0.998        │ • BANC: +20.00% edges | +10.02% syn | -15.03% var  │
│ • FAFB (med 6.0): -2.50% edges | r = 1.000        │ • FAFB: +20.00% edges |  +6.58% syn | -13.90% var  │
│ • MANC (med 2.0): -9.73% edges | r = 0.998        │ • MCNS: +18.18% edges |  +6.32% syn | -12.61% var  │
│ • MCNS (med 9.0): -0.007% edges| r = 1.000        │ • MEAN (n=3): +19.39% edges | +7.64% syn           │
│ • MAOL (med 2.0): -8.92% edges | r = 0.999        │                                                    │
│ • MEAN (n=5)    : -4.87% edges | r = 0.999        │ 4. SPLIT NEURONS (EM4) ACROSS ALL 5 DATASETS       │
│                                                   │ • 0.0% edge loss (100% preserved in all 5 datasets)│
│ 2. MERGED NEURONS (EM5) BREAKDOWN                 │ • Mean degree drops by -12.8% to -16.0% (-14.9%)   │
│ • BANC: -12.18% edges | +59.87% var | -8.30% SCC  │ • Largest SCC shifts by +14.9% to +19.2% (+17.6%)  │
│ • FAFB: -16.09% edges | +64.98% var | -9.33% SCC  │                                                    │
│ • MANC:  -8.27% edges | +24.46% var | -9.98% SCC  │ 5. BASELINE DATASET SIZES                          │
│ • MCNS:  -7.12% edges | +38.20% var | -8.24% SCC  │ • BANC: 158k nodes | FAFB: 139k nodes              │
│ • MEAN (n=4)    : -10.91% edges | +46.88% var     │ • MANC: 24k nodes  | MCNS: 167k | MAOL: 52k        │
└───────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```
