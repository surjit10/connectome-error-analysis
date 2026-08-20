# 3.5-Minute Presentation: Anticipated Q&A Defense Cheat Sheet

**Topic**: How Reconstruction Errors Affect the FlyWire Connectome  
**Author**: Surjit Mandal  
**Format**: Rapid 15-Second Crisp Answers for Presentation Evaluators  
**Location**: `/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2/DEFENSE_AND_QA_CHEAT_SHEET.md`

---

### Q1: Why do missed synapses delete 20% of synapses but only 4.9% of graph edges?
> **15-Second Answer**:  
> "An edge only disappears if *every single synapse* on that connection is deleted. Under our binomial model $w' \sim \text{Bin}(w, 1-p)$, the probability of edge deletion is $p^w$. For a 1-synapse edge, deletion probability is $20\%$. But for a 5-synapse edge, deletion probability drops exponentially to $(0.20)^5 = 0.032\%$. Because Drosophila connectomes rely heavily on multi-synaptic connections, the edge skeleton is mathematically buffered against false negative detection."

---

### Q2: Why are merge errors so much more destructive than split errors?
> **15-Second Answer**:  
> "Split errors merely dilute existing connections across daughter fragments, preserving 100% of edges and total synapses. Merge errors, on the other hand, fuse distinct functional entities, obliterating internal edges ($-10.9\%$), shrinking graph components ($-9.0\%$), and pooling synaptic weights into massive artificial super-hubs (+46.9% weight variance surge). They fundamentally destroy circuit modularity."

---

### Q3: Is your proofreading priority experimentally proven, or is it a recommendation?
> **15-Second Answer**:  
> "What is **experimentally proven** by our 1,030 simulation runs is the **Damage Hierarchy**: Merged Neurons (-10.9% edges, +47% weight variance) and Missed Synapses (-20% synapses) drive almost all structural network distortion, while Splits (0.0% edge loss) and Count Noise (0.0% topological change) are structurally benign. Therefore, focusing manual proofreading effort on Merges and Missed Synapses is a **direct mathematical consequence of our sensitivity data**, while Splits can be merged algorithmically post-hoc."

---

### Q4: Why do you test up to 20% error rate instead of only realistic residual noise?
> **15-Second Answer**:  
> "In heavily proofread datasets (FlyWire v783), residual noise is under 2% to 5%, where our data proves graph changes are negligible (under 1% shift, PageRank $r > 0.999$). We test up to 20% as an **experimental stress test** to model raw, unproofread machine-learning outputs (*Buhmann et al., Nature Methods 2021*), establishing worst-case bounds for future automated pipelines."

---

### Q5: Why do you recommend Weight Variance as a real-time warning sign?
> **15-Second Answer**:  
> "Weight variance captures the second moment of the synaptic weight distribution and moves 3 to 5 times faster than binary topology across all error models. When neurons merge, weights pool together causing an immediate $+46.9\%$ spike; when synapses are missed, weights compress causing a $-30.3\%$ collapse. It detects distribution distortion long before binary graph topology shows measurable degradation."

---

### Q6: Why is MCNS almost immune to missed synapses (-0.007%) while MANC loses -9.7%?
> **15-Second Answer**:  
> "This is governed by the **Median Connection Weight Rule**. MANC is a motor nerve cord connectome with a median of only 2.0 synapses per edge, so single-synapse connections frequently get wiped out ($20\%$ loss). MCNS is a central brain connectome with a median of 9.0 synapses per edge, where the probability of losing all 9 synapses is $(0.2)^9 \approx 5 \times 10^{-7}$. Resilience scales exponentially with baseline connection thickness."

---

### Q7: If PageRank vector correlation is r >= 0.98 under merges, why do you warn about hub fragility?
> **15-Second Answer**:  
> "While global Pearson vector correlation across 150,000 neurons remains high ($r \ge 0.98$), individual rank orders in the top-100 hub tier suffer local displacement. Under merge errors, top-100 hub overlap drops to 86% on BANC, meaning 14 of the top 100 hubs are displaced by artificial multi-neuron mergers. Global routing remains intact, but specific hub identifications require targeted proofreading."

---

### Q8: How do your error models align with empirical FlyWire literature?
> **15-Second Answer**:  
> "Our models are directly grounded in published FlyWire literature (*Dorkenwald et al., Nature 2024* and *Buhmann et al., Nature Methods 2021*). Buhmann's Synful precision/recall curves defined our 0–20% synapse perturbation range, while PyChunkedGraph proofreading logs confirmed that over-segmentation splits and under-segmentation merges are the primary human corrections performed during whole-brain reconstruction."
