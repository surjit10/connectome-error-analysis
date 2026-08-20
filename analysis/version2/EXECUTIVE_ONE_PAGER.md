# Executive One-Pager: How Reconstruction Errors Affect the FlyWire Connectome

**Topic**: How Reconstruction Errors Affect the FlyWire Connectome  
**Author**: Surjit Mandal | **Target Format**: 1-Page Evaluation Handout  
**Location**: `/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2/EXECUTIVE_ONE_PAGER.md`

---

## 1. Core Research Question
> **When automated AI tools map brain wiring diagrams from electron microscope images, how much do different errors change network connections, and which error types cause the most damage?**

We tested this across **5 Drosophila connectomes** (BANC, FAFB, MANC, MCNS, MAOL), **5 distinct error models**, and **10 error levels** ($0\% \to 20\%$) over **1,030 simulation runs**.

---

## 2. Key Papers & References
Our error models represent reconstruction challenges documented in connectomics literature (*Dorkenwald et al., Nature 2024*; *Buhmann et al., Nature Methods 2021*; *Januszewski et al., Nature Methods 2018*; *Takemura et al., Nature 2023*; *Scheffer et al., eLife 2020*):
- **Missed Synapses (EM1)**: Automated detector fails to spot a real connection.
- **False Synapses (EM2)**: Automated detector adds a fake connection where none exists.
- **Synapse Count Noise (EM3)**: Small counting errors in synapse numbers.
- **Split Neurons (EM4)**: A single neuron gets broken into fragments.
- **Merged Neurons (EM5)**: Two distinct neurons get accidentally joined together.

---

## 3. Results at Highest Tested Error Level (20%)

*Cross-dataset averages relative to baseline (0% error):*

| Error Model | Δ Edge Count (%) | Δ Total Synapses (%) | Δ Weight Variance (%) | Δ Mean Degree (%) | Largest Connected Core (SCC) (%) | PageRank Pearson $r$ |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Missed Synapses (EM1) (n=5)** | $-4.87\%$ | **$-20.00\%$** | **$-30.25\%$** | $-4.87\%$ | $-0.04\%$ | **0.999** |
| **False Synapses (EM2) (n=3)** | **$+19.39\%$** | $+7.64\%$ | $-13.85\%$ | **$+19.39\%$** | $+0.63\%$ | **0.994** |
| **Synapse Count Noise (EM3) (n=5)** | $0.00\%$ | $+0.03\%$ | $+5.45\%$ | $0.00\%$ | $0.00\%$ | **0.999** |
| **Split Neurons (EM4) (n=5)** | $0.00\%$ | $0.00\%$ | $0.00\%$ | **$-14.87\%$** | **$+17.63\%$** | **0.995** |
| **Merged Neurons (EM5) (n=4)** | **$-10.91\%$** | $-0.10\%$ | **$+46.88\%$** | $-2.60\%$ | **$-8.96\%$** | **0.989** |

---

## 4. Key Findings & Conclusions

1. **Missed Synapses Do Not Proportionally Eliminate Connections**:  
   Losing 20% of synapses reduces connections by only $-4.87\%$ because connections with multiple synapses are naturally protected ($P(\text{loss}) = p^w$).
2. **Merging Neurons Causes Much More Damage Than Splitting**:  
   Neuron merges combine two separate neurons into one, deleting $-10.9\%$ of edges, shrinking the largest connected component by $-9.0\%$, and boosting weight variance by $+46.9\%$.
3. **Neuron Importance Rankings Stay Stable**:  
   PageRank rankings remain highly stable across all tested error models ($r \approx 0.977\text{--}1.000$).
4. **Stronger Connections Protect Against Edge Loss**:  
   MANC (median weight 2.0) loses $-9.73\%$ of edges, while MCNS (median weight 9.0) loses only $-0.007\%$, showing that networks with stronger connections resist edge loss better.
5. **Practical Conclusion**:  
   Proofreaders should prioritize finding and fixing merge errors and missed synapses to protect brain network structure.
