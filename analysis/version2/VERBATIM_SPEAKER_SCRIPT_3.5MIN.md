# 3.5-Minute Verbatim Speaker Script: Presentation

**Topic**: How Reconstruction Errors Affect the FlyWire Connectome  
**Author**: Surjit Mandal  
**Target Duration**: Strictly 3.5 Minutes (210 Seconds)  
**Word Count**: ~420 words (~120 words per minute)  
**Location**: `/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2/VERBATIM_SPEAKER_SCRIPT_3.5MIN.md`

---

## 🎙️ Verbatim Script with Slide Transitions & Physical Pointing Cues

---

### Slide 1: Research Overview & Benchmark Design
`[0:00 - 0:25] | Duration: 25 Seconds | Target Word Count: ~55 words`

* **Visual Pointing Cue**: 👉 *State your name, Surjit Mandal, point to 'Why This Matters' on the left, and gesture across the five tested error models on the right.*
* **Verbatim Spoken Words**:
  > "Good morning. I am Surjit Mandal. In modern neuroscience, automated AI tools map brain wiring diagrams with millions of connections. But these tools make errors.
  > 
  > Our core question is: **When these errors enter a connectome, how much do network connections and brain properties change, and which error types cause the most damage?**
  > 
  > We tested five fruit fly connectomes across five error types over 1,030 simulation runs."

---

### Slide 2: Global Error Comparison
`[0:25 - 1:00] | Duration: 35 Seconds | Target Word Count: ~75 words`

* **Visual Pointing Cue**: 👉 *Point to the Global Fingerprints bar chart, contrasting the 0.0% row for Count Noise and Splits against the -10.9% edge loss and +46.9% Weight Variance surge for Merges.*
* **Verbatim Spoken Words**:
  > "Here is our summary across all five datasets at the highest tested error rate of 20%.
  > 
  > Notice that **Synapse Count Noise** and **Split Neurons** do not delete any graph connections. In contrast, **Merged Neurons** caused the largest structural changes, removing 11% of edges and inflating connection weight variance by 47%.
  > 
  > The key takeaway: network structure is very stable against simple counting noise, but highly sensitive when neurons are accidentally merged."

---

### Slide 3: Finding 1 — Missed Synapse Analysis
`[1:00 - 1:40] | Duration: 40 Seconds | Target Word Count: ~80 words`

* **Visual Pointing Cue**: 👉 *Point to the green shaded 4x Buffering Zone between total synapses and actual edge loss, highlighting the formula $P(\text{loss}) = p^w$.*
* **Verbatim Spoken Words**:
  > "Our first major finding explains why missed synapses do not delete connections at a one-to-one rate.
  > 
  > When our simulation removes 20% of all synapses, actual connection count drops by only **4.87%**—about 4 times smaller than the synapse loss.
  > 
  > Why? In real brains, many connections share multiple synapses. A connection is only lost if every single synapse on it is missed. Stronger connections with multiple synapses are naturally protected from disappearing."

---

### Slide 4: Finding 2 — Split vs Merge Comparison
`[1:40 - 2:20] | Duration: 40 Seconds | Target Word Count: ~80 words`

* **Visual Pointing Cue**: 👉 *Point to the head-to-head comparison chart, contrasting the green Split bars (0.0% edge loss) against the coral Merge bars (-10.9% edge loss and +46.9% weight variance).*
* **Verbatim Spoken Words**:
  > "Next: How does splitting a neuron compare to merging neurons?
  > 
  > Our simulations show that **Split errors** divide a neuron across pieces but preserve 100% of graph connections and total synapses. In contrast, **Merge errors** combine two distinct neurons into one, deleting 11% of connections and boosting weight variance by 47%.
  > 
  > Merging neurons causes far more structural distortion than splitting."

---

### Slide 5: Finding 3 — Centrality & Connectome Comparison
`[2:20 - 3:00] | Duration: 40 Seconds | Target Word Count: ~75 words`

* **Visual Pointing Cue**: 👉 *Point to the PageRank correlation on the left, then point to the MANC vs MCNS comparison on the right.*
* **Verbatim Spoken Words**:
  > "Third: How do neuron importance rankings and connection strengths behave?
  > 
  > First, PageRank rankings remain highly stable across tested error models, with Pearson **r between 0.977 and 1.000**.
  > 
  > Second, datasets with stronger connections lose far fewer edges: MANC, with a median weight of 2, loses 9.7% of edges, while MCNS, with a median weight of 9, loses only 0.007% (-0.007%)."

---

### Slide 6: Actionable Rules & Summary
`[3:00 - 3:30] | Duration: 30 Seconds | Target Word Count: ~55 words`

* **Visual Pointing Cue**: 👉 *Point to the Error Impact Summary table on the left, then conclude with the summary on the right.*
* **Verbatim Spoken Words**:
  > "To summarize our findings:
  > 
  > Different reconstruction errors produce very different network impacts. Merges cause the largest structural damage, while missed synapses show substantial synapse loss but buffered edge loss.
  > 
  > When reviewing and cleaning connectomes, proofreaders should prioritize finding and fixing merge errors and missed synapses.
  > 
  > I am Surjit Mandal. Thank you for your time and attention!"
