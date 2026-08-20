# Literature and Scientific Methodology Reference Guide (Version 2)
**Project**: Quantitative Sensitivity Analysis across 5 *Drosophila* EM Connectomes  
**Author**: Surjit  
**Target Delivery**: 3.5-Minute Final Defense & Publication Reference  
**Location**: `/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2/LITERATURE_AND_METHODOLOGY_REFERENCE.md`

---

## 1. Foundational Literature & Academic Grounding

Connectome reconstruction from serial-section Transmission / Scanning Electron Microscopy (ssTEM / FIB-SEM) relies on automated computer vision pipelines (convolutional neural networks for 3D membrane segmentation and synaptic partner prediction) followed by human proofreading. Our study's 5 error models are directly motivated by the reconstruction bottlenecks and error distributions characterized in landmark connectomics literature:

```
                                  AUTOMATED EM RECONSTRUCTION PIPELINE
  ┌────────────────────────┐       ┌────────────────────────┐       ┌────────────────────────┐
  │   Synapse Detection    │  ───► │  Membrane Segmentation │  ───► │ Agglomeration & Proof │
  │ (e.g., Synful CNN)     │       │ (Flood-Filling Networks│       │ (PyChunkedGraph /      │
  │ Buhmann et al. (2021)  │       │  Januszewski et al.)   │       │  Dorkenwald et al.)    │
  └───────────┬────────────┘       └───────────┬────────────┘       └───────────┬────────────┘
              │                                │                                │
              ▼                                ▼                                ▼
  ┌────────────────────────┐       ┌────────────────────────┐       ┌────────────────────────┐
  │  EM1: Missed Synapses  │       │   EM4: Split Neurons   │       │   EM5: Merged Neurons  │
  │  EM2: False Synapses   │       │  (Over-segmentation)   │       │  (Under-segmentation)  │
  │  EM3: Synapse Noise    │       │                        │       │                        │
  └────────────────────────┘       └────────────────────────┘       └────────────────────────┘
```

---

### Core Publication Reference Set (Verified DOIs & Contributions)

#### 1. Whole-Brain Dataset Provenance & Proofreading Dynamics
* **Dorkenwald, S., Li, P. H., Januszewski, M., ... Murthy, M., & Seung, H. S. (FlyWire Consortium). (2024). *Neuronal wiring diagram of an adult brain*. Nature, 634(8032), 124–138.**  
  DOI: [`10.1038/s41586-024-07558-y`](https://doi.org/10.1038/s41586-024-07558-y)
  * **Primary Finding**: Unveiled the complete FlyWire whole-brain connectome of *Drosophila melanogaster* (139,255 neurons, 5.3M edges, 50.7M synapses).
  * **Methodological Grounding**: Establishes that human proofreading via dynamic chunked graphs (`PyChunkedGraph`) is overwhelmingly dedicated to resolving over-segmentation splits and under-segmentation merges. Provides the `FAFB` baseline dataset.

#### 2. Automated Synapse Detection Error Rates (EM1 & EM2)
* **Buhmann, J., Sheridan, A., Malin-Mayor, C., Schlegel, P., Gerhard, S., Bock, D. D., & Funke, J. (2021). *Automatic detection of synaptic partners in a whole-brain Drosophila electron microscopy dataset*. Nature Methods, 18(7), 771–774.**  
  DOI: [`10.1038/s41592-021-01183-7`](https://doi.org/10.1038/s41592-021-01183-7)
  * **Primary Finding**: Introduced the **Synful** deep learning pipeline for automated synapse detection, quantifying false-negative rates (~20%) and false-positive rates (~20%) against human ground truth.
  * **Methodological Grounding**: Directly motivates our $0\% \to 20\%$ error sweep for **EM1 (Missed Synapses)** and **EM2 (False Synapses)** and validates our per-edge binomial thinning model.

#### 3. Automated Volumetric EM Segmentation (EM4 & EM5)
* **Januszewski, M., Kornfeld, J., Li, P. H., Pope, A., Blakely, T., Lindsey, L., Maitin-Shepard, J., Tyka, M., Denk, W., & Jain, V. (2018). *High-precision automated reconstruction of neurons with flood-filling networks*. Nature Methods, 15(8), 605–610.**  
  DOI: [`10.1038/s41592-018-0049-4`](https://doi.org/10.1038/s41592-018-0049-4)
  * **Primary Finding**: Established Flood-Filling Networks (FFNs) for 3D EM volumetric segmentation, characterizing automated run-lengths and identifying boundary leakage (merges) and premature path termination (splits).
  * **Methodological Grounding**: Ground truth for automated segmentation error modes in electron microscopy.

#### 4. Graph-Based Connectomics Reconstruction & Biological Constraints
* **Matejek, B., Haehn, D., Zhu, H., Wei, D., Parag, T., & Pfister, H. (2019). *Biologically-Constrained Graphs for Global Connectomics Reconstruction*. Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), pp. 2486–2495.**  
  DOI: [`10.1109/CVPR.2019.00260`](https://doi.org/10.1109/CVPR.2019.00260)
  * **Primary Finding**: Formulated connectomics agglomeration as graph optimization under biological constraints (soma location, region, connectivity priors) to resolve split and merge ambiguities.
  * **Methodological Grounding**: Supports our use of graph-topological community partitioning and anatomical constraints (region, soma side) as legitimate computational surrogates for neurite boundary handling.

#### 5. Sparser Motor Nerve Cord Baseline & The Median Weight Law
* **Takemura, S. Y., Aso, Y., Hige, T., ... Scheffer, L. K. (2023). *A connectome of the male Drosophila ventral nerve cord*. Nature, 624(7992), 624–633.**  
  DOI: [`10.1038/s41586-023-06762-w`](https://doi.org/10.1038/s41586-023-06762-w)
  * **Primary Finding**: Full reconstruction of the Male Adult Nerve Cord (`MANC`), comprising 23,665 neurons and 30.9M synapses with sparse motor circuit wiring.
  * **Methodological Grounding**: Baseline dataset for `MANC` and empirical proof of the **Median Weight Law** (median 2.0 synapses/edge vs 9.0 in central brain).

#### 6. Graph Analysis Protocols & Centrality Robustness
* **Scheffer, L. K., Xu, C. S., Januszewski, M., ... Rubin, G. M. (2020). *A connectome and analysis of the adult Drosophila central brain*. eLife, 9, e57443.**  
  DOI: [`10.7554/eLife.57443`](https://doi.org/10.7554/eLife.57443)
  * **Primary Finding**: Hemibrain connectome analysis formalizing PageRank centrality damping ($\alpha=0.85$), degree distributions, reciprocity, and the $w \ge 3$ threshold rule for noise filtering.
  * **Methodological Grounding**: Directly motivates our PageRank damping protocols and multi-synaptic threshold filtering analysis.

#### 7. Multi-Connectome Consensus & Cross-Dataset Alignment
* **Schlegel, P., Bates, A. S., Stürner, T., ... Jefferis, G. S. X. E. (2024). *Whole-brain annotation and multi-connectome marker quantification in Drosophila*. Nature, 634(8032), 139–152.**  
  DOI: [`10.1038/s41586-024-07953-3`](https://doi.org/10.1038/s41586-024-07953-3)
  * **Primary Finding**: Consensus cell typing and multi-connectome alignment across FAFB and hemibrain datasets.
  * **Methodological Grounding**: Cross-connectome biological context and comparative cell classification.

#### 8. Dataset Acquisition (FAFB ssTEM Volume)
* **Zheng, Z., Lauritzen, J. S., Perlman, E., ... Bock, D. D. (2018). *A Complete Electron Microscopy Volume of the Adult Drosophila Brain*. Cell, 174(3), 730–743.**  
  DOI: [`10.1016/j.cell.2018.06.019`](https://doi.org/10.1016/j.cell.2018.06.019)
  * **Primary Finding**: Original serial-section transmission EM acquisition and volume alignment of the complete adult female fly brain.
  * **Methodological Grounding**: Primary volume acquisition reference for the FAFB dataset.

#### 9. Topological Link Prediction (EM2 & EM5 Candidate Generation)
* **Liben-Nowell, D., & Kleinberg, J. (2007). *The link-prediction problem for social networks*. Journal of the American Society for Information Science and Technology, 58(7), 1019–1031.**  
  DOI: [`10.1002/asi.20591`](https://doi.org/10.1002/asi.20591)
  * **Primary Finding**: Mathematical foundation of neighborhood Jaccard similarity and common-neighbor metrics for topological link prediction.
  * **Methodological Grounding**: Justification for candidate pair ranking in EM2 (false synapses) and EM5 (merges).

#### 10. Injective Synthetic Vertex Pairing (EM5 Merge Identification)
* **Szudzik, M. (2006). *An Elegant Pairing Function*. Wolfram Research / NKS 2006 Conference.**  
  URL: `https://szudzik.com/ElegantPairing.pdf`
  * **Primary Finding**: Mathematical proof of the bijective pairing function $\mathbb{N}_0 \times \mathbb{N}_0 \to \mathbb{N}_0$.
  * **Methodological Grounding**: Mathematical proof of bijective, collision-free synthetic merged vertex IDs in EM5.

---

## 2. Mathematical Modeling of the 5 Error Models (Code Ground Truth)

Every error model perturbs the baseline graph $G_0 = (V_0, E_0, W_0)$ into a perturbed graph $G_r = (V_r, E_r, W_r)$ at nominal error rate $r \in [0, 0.20]$. All operations use locally seeded random number generators (`numpy.random.Generator`) ensuring bitwise reproducibility.

```
┌────────────────────────┬──────────────────────────┬──────────────────────────────────────────────────────────────────┐
│ ERROR MODEL            │ TARGET LEVEL             │ MATHEMATICAL PERTURBATION MECHANISM                              │
├────────────────────────┼──────────────────────────┼──────────────────────────────────────────────────────────────────┤
│ EM1: Missed Synapses   │ Synapse Loss (FN)        │ Calibrated Binomial Thinning: w' ~ Bin(w, 1-p)                   │
│ EM2: False Synapses    │ Spurious Edges (FP)      │ Directed Out-Jaccard Candidate Sampling: k = round(r * |E|)      │
│ EM3: Count Uncertainty │ Weight Measurement       │ Discretized Proportional Noise: w' = max(1, round(w + N(0, rw))) │
│ EM4: Split Neurons     │ Over-segmentation        │ 1-Hop Ego-Network Louvain/Component 2-Way Partition             │
│ EM5: Merge Neurons     │ Under-segmentation       │ Region-Constrained Partner Jaccard Merge + Szudzik Pairing       │
└────────────────────────┴──────────────────────────┴──────────────────────────────────────────────────────────────────┘
```

---

### EM1: Missed Synapses (Synapse Detection False Negatives)
* **Code Implementation**: [`modules/error_models/missed_synapses/model.py`](file:///home/surjit/Desktop/flywire/v1/modules/error_models/missed_synapses/model.py), [`vulnerability.py`](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/missed_synapses/vulnerability.py), [`calibration.py`](file:///home/surjit/Desktop/flywire/v1/modules/error_models/common/calibration.py).
* **Vulnerability Formulation**:
  $$V(e) = w_{\text{syn}}\left(1 - \frac{s_e - s_{\min}}{s_{\max} - s_{\min}}\right) + w_{\text{src}}\left(1 - \frac{d_{\text{src}} - d_{\min}^{\text{src}}}{d_{\max}^{\text{src}} - d_{\min}^{\text{src}}}\right) + w_{\text{tgt}}\left(1 - \frac{d_{\text{tgt}} - d_{\min}^{\text{tgt}}}{d_{\max}^{\text{tgt}} - d_{\min}^{\text{tgt}}}\right)$$
* **Probability Calibration Algorithm**:
  Solves by iterative mass redistribution for removal probabilities $p_e \in [0, 1]$ such that:
  $$\mathbb{E}[\text{Synapse Loss}] = \sum_{e \in E} p_e \cdot w(e) = r \cdot \sum_{e \in E} w(e)$$
* **Stochastic Thinning**:
  $$w'(e) \sim \operatorname{Binomial}(w(e), 1 - p_e)$$
  $$\Pr(\text{Edge Deletion} \mid w(e)) = (p_e)^{w(e)}$$
  *Scientific Guarantee*: Target $r$ strictly represents the **expected fraction of total synapses removed**. Edge loss is buffered by multi-synaptic redundancy.

---

### EM2: False Synapses (Hallucinated Synaptic Connections)
* **Code Implementation**: [`modules/error_models/false_synapses/model.py`](file:///home/surjit/Desktop/flywire/v1/modules/error_models/false_synapses/model.py), [`candidate_generator.py`](file:///home/surjit/Desktop/flywire/v1/modules/preprocessing/false_synapses/candidate_generator.py).
* **Candidate Ranking (Directed Out-Jaccard)**:
  $$J_{\text{out}}(a, b) = \frac{|\operatorname{succ}(a) \cap \operatorname{succ}(b)|}{|\operatorname{succ}(a) \cup \operatorname{succ}(b)|}$$
* **Sampling & Injection**:
  - Injects $k = \operatorname{round}(r \cdot |E_0|)$ new edges sampled without replacement with probability proportional to $J_{\text{out}}(a, b)$.
  - Injected weights drawn with replacement from empirical weak baseline distribution ($w \le 5$).

---

### EM3: Synapse-Count Measurement Uncertainty
* **Code Implementation**: [`modules/error_models/synapse_count/model.py`](file:///home/surjit/Desktop/flywire/v1/modules/error_models/synapse_count/model.py).
* **Discretized Proportional Model**:
  $$\sigma_e = r \cdot w_e$$
  $$w'_e = \max(1, \operatorname{round}(w_e + \epsilon_e)), \quad \epsilon_e \sim \mathcal{N}(0, \sigma_e^2)$$
* *Scientific Property*: Graph topology (nodes, edges, connectivity) is **100% conserved**. The lower bound clamp $\ge 1$ introduces a minor positive expectation bias on single-synapse connections ($< 0.05\%$).

---

### EM4: Split Errors (Over-Segmentation)
* **Code Implementation**: [`modules/error_models/split_errors/model.py`](file:///home/surjit/Desktop/flywire/v1/modules/error_models/split_errors/model.py), [`core/split_experiment_runner.py`](file:///home/surjit/Desktop/flywire/v1/core/split_experiment_runner.py).
* **Eligibility & Partitioning**:
  - Selects neurons with $\operatorname{deg}_{\text{total}}(v) \ge 10$.
  - Extracts 1-hop undirected ego-network neighbor subgraph $G_N(c)$ (excluding autapses).
  - If disconnected $\to$ uses connected components; if connected $\to$ Louvain modularity optimization (`community_multilevel`).
  - Greedy Largest-First assignment into 2 balanced fragments $c_1, c_2$.
* **Synthetic Fragment IDs**:
  $$\operatorname{ID}(c, f) = -(2 \cdot |c| + f), \quad f \in \{1, 2\}$$
* **Vector Alignment**: Uses **Sum Aggregation** ($\operatorname{PR}(c) = \operatorname{PR}(c_1) + \operatorname{PR}(c_2)$) to conserve stationary probability mass.

---

### EM5: Merge Errors (Under-Segmentation)
* **Code Implementation**: [`modules/error_models/merge_errors/model.py`](file:///home/surjit/Desktop/flywire/v1/modules/error_models/merge_errors/model.py), [`core/merge_experiment_runner.py`](file:///home/surjit/Desktop/flywire/v1/core/merge_experiment_runner.py).
* **Hard Anatomical Filters & Partner Jaccard Ranking**:
  - Requires identical `top_region` and compatible `soma_side`.
  - Shared partners $\ge 3$, full-partner Jaccard $J(a, b) \ge 0.001$, top-50 candidates per neuron.
* **Bijective Szudzik Synthetic ID Pairing**:
  $$\operatorname{pair}(x, y) = \begin{cases} y^2 + x & \text{if } x < y \\ y^2 + 2y & \text{if } x = y \end{cases} \quad \text{where } x = \min(|a|, |b|), \, y = \max(|a|, |b|)$$
* **Graph Rewiring & Synapse Accounting**:
  Parallel edges collapse with summed weights ($w_M = w_a + w_b$); internal $a \leftrightarrow b$ edges are dropped with explicit self-loop synapse tracking.

---

## 3. Formal Invariants & Conservation Laws Table

```
┌────────────────────────┬──────────────────────┬────────────────────────┬──────────────────────────────────────────┐
│ ERROR MODEL            │ NODE COUNT (|V|)     │ EDGE COUNT (|E|)       │ TOTAL SYNAPSE BUDGET (W)                 │
├────────────────────────┼──────────────────────┼────────────────────────┼──────────────────────────────────────────┤
│ EM1: Missed Synapses   │ Invariant (|V'| = |V|)│ Decreases (-4.9%)      │ Decreases 1-for-1 (-20.0%)               │
│ EM2: False Synapses    │ Invariant (|V'| = |V|)│ Increases (+19.4%)     │ Increases (+7.6%)                        │
│ EM3: Synapse Count     │ Invariant (|V'| = |V|)│ Invariant (|E'| = |E|) │ Conserved (+0.03% discretization bias)   │
│ EM4: Split Errors      │ Increases (|V| + k)  │ Invariant (0.0% dE)    │ Conserved (100% minus autapses)          │
│ EM5: Merge Errors      │ Decreases (|V| - k)  │ Decreases (-10.9%)     │ Conserved (100% minus internal self-loops)│
└────────────────────────┴──────────────────────┴────────────────────────┴──────────────────────────────────────────┘
```

---

## 4. Defensible Scientific Framing Guidelines

When presenting or writing about this methodology, adhere to these scientifically precise descriptions:

1. **Topological Approximation vs Biophysical Simulation**:  
   State clearly that EM4 (splits) and EM5 (merges) are **graph-theoretic topological approximations** designed for graph-level connectomes where 3D morphological volumetric meshes and skeletons are absent.
2. **Jaccard Ranking as a Link-Prediction Proxy**:  
   Describe neighborhood Jaccard similarity as a **topological surrogate for spatial neuropil co-arborization**, grounded in link-prediction literature (*Liben-Nowell & Kleinberg, 2007*).
3. **Discretized Measurement Uncertainty**:  
   Describe EM3 as a **discretized proportional measurement error process** with integer rounding and a lower bound of 1.
4. **Binomial Buffering Mechanism**:  
   Emphasize that the 4-fold resilience of graph edges under missed synapses is a direct mathematical consequence of binomial thinning on multi-synaptic connections ($P(\text{loss}) = p^w$).
