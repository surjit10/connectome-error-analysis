# Presentation Speaking Script — How Reconstruction Errors Affect Connectome Analysis

**Deck:** `presentation.pdf` (11 slides) · **Target:** ~5–6 minutes · **Style:** plain, easy-to-follow talk

> **How to use this file.** This script is your complete reference for presenting the deck.
> Every slide has four parts:
>
> 1. **What's on the slide** — every small detail of the slide explained (figures, captions,
>    tables, intro lines, takeaway bars), so you never wonder "what is this thing?"
> 2. **Say this** — the words to speak, in plain language. You can read this almost word-for-word.
>    If you're short on time, say only the **bold** sentences.
> 3. **Key numbers** — the one or two numbers you must not forget.
> 4. **Notes (from the deck)** — the original speaker notes embedded in the presentation file,
>    kept here for your reference.
>
> At the top there is a **Words You Need to Know** glossary: every technical word in the deck,
> explained in simple language. Read it once before the talk. At the bottom, **Likely Questions
> & Easy Answers** prepares you for the questions people usually ask.

---

# Part 0 — Words You Need to Know (Glossary)

Every technical word used in the deck, in plain English:

| Word | Simple meaning |
|------|----------------|
| **Connectome** | A complete map of the wiring of a brain — which neurons connect to which. |
| **Neuron** | A brain cell. In the graph it is a **point (node)**. |
| **Node / Vertex** | A point in a graph. In our graphs, a node = one neuron. |
| **Edge** | A line in the graph. Here, an edge = a connection between two neurons. |
| **Synapse** | The physical contact point between two neurons where signals pass. Many synapses can sit on one connection (edge). |
| **Edge weight** | The number of synapses on a connection — how **strong** the connection is. |
| **Directed graph** | A graph where connections have a direction (A→B is not the same as B→A). Brain wiring is directional: signals flow one way at a synapse. |
| **Weighted graph** | A graph where every edge carries a weight (here: its synapse count). |
| **Segmentation** | The automated process of carving the microscope image into individual neurons. |
| **Over-segmentation** | When segmentation wrongly cuts **one real neuron into several pieces** → split errors. |
| **Under-segmentation** | When segmentation wrongly joins **several real neurons into one** → merge errors. |
| **Error rate** | The fraction of error we inject (0% → 20%). At 20%, one fifth of the relevant units are wrong. |
| **Trial** | One complete run of the experiment at one error rate, with one random seed. |
| **Baseline** | The original, correct connectome, before we add any error. |
| **Perturbed graph** | The graph after we injected error. We compare it against the baseline. |
| **Metric** | A number we compute to describe the graph (e.g., edge count, degree). |
| **Topology** | The structure of connections — which neurons connect to which — ignoring weights. |
| **Degree** | How many other neurons a neuron connects to (in = incoming, out = outgoing). |
| **Mean degree** | The average degree across all neurons. |
| **Component** | A group of neurons that are connected to each other, directly or indirectly. |
| **WCC (weakly connected component)** | A group connected if we **ignore** the direction of connections. |
| **SCC (strongly connected component)** | A group connected only when we **follow** the direction of connections (you can reach every member by following the arrows). |
| **Reciprocity** | The fraction of connections that go **both ways** (A→B and B→A both exist). |
| **Assortativity** | Whether neurons tend to connect to *similar* neurons (e.g., hub to hub). Note: unreliable in our data because the baseline is near zero. |
| **PageRank** | An importance ranking: **a neuron is important if important neurons connect to it** (same idea as Google ranking web pages). |
| **Hub** | A neuron with very high importance (PageRank). The "top-100 hubs" = the 100 most important neurons. |
| **Correlation (r)** | How similar two lists are. r = 1 means identical; r = 0 means unrelated; r = −1 means opposite. |
| **Pearson r** | Correlation of the actual values (scores). |
| **Spearman** | Correlation of the *ranks* (the order), so it cares less about exact values. |
| **Top-100 overlap** | The fraction of the top-100 hubs that stay in the top 100 after error. Measures how stable the "most important" list is. |
| **Weight variance** | How **spread out** the connection strengths are. Small = similar weights; large = some very light, some very heavy. |
| **Connectivity layer** | The part of the graph made of edges, synapses and weights. |
| **Neuron-identity layer** | The part of the graph describing **which neurons exist** and how they are grouped. |
| **Fingerprint** | The unique, recognizable pattern of changes that each error type produces. |
| **Fragmentation** | The graph breaking into more, smaller pieces (split errors). |
| **Condensation** | The graph squeezing into fewer, bigger pieces (merge errors). |
| **Control model / Control result** | A test designed so that *only* the thing we intend changes — everything else should stay the same. It proves the experiment works. |
| **Robust** | Stable; barely affected by error. |
| **Benign** | Harmless; causes no real damage. |
| **Simulated error** | An error we **injected by design** at a controlled rate (not a real, measured error). |
| **Empirical measurement** | Measured from real data (as opposed to simulated). |
| **Seeded trials** | Trials run with fixed random seeds, so anyone can re-run and get exactly the same results. |

---

# Slide 1 — Title: Research Question & Progress (~25 s)

## What's on the slide

- **Top banner: "RESEARCH PROGRESS UPDATE • FLYWIRE CONNECTOME PROJECT"** — this tells the
  audience this is a *progress update*, not a finished paper. FlyWire is the project that
  reconstructs the fruit-fly brain from electron-microscope images.
- **Big title: "How Do Reconstruction Errors Affect Connectome Graph Analysis?"** — the one
  question the whole talk answers.
- **Subtitle: "As reconstruction error grows 0 → 20%, how strongly does each error type perturb
  graph structure and downstream graph analyses?"** — this is the precise scope: we push error
  from 0% up to 20% and measure the effect on (a) the graph structure and (b) the analyses people
  run on the graph.
- **Three bullets:**
  1. *"Connectomes are directed, weighted graphs: neurons are nodes, synapses are edges."* — the
     model. Nodes = neurons; edges = connections; the arrows show direction; each edge has a
     weight (synapse count).
  2. *"Segmentation is imperfect — reconstruction errors change the observed graph."* — the
     motivation. The map we analyze is not the true map; it has mistakes.
  3. *"We measure how each error type distorts downstream graph analyses."* — the goal: quantify
     the damage.
- **The five chips: BANC, FAFB, MANC, MCNS, MAOL** — the five brain datasets used (different
  fly connectomes).
- **Caption: "5 connectomes × 5 error models • rates up to 20% • seeded trials"** — the scale of
  the experiment at a glance.

## Say this

> Good morning/afternoon everyone. Today I'm sharing a progress update on our FlyWire connectome
> research project.
>
> **The question we are trying to answer is simple: when we make mistakes while reconstructing a
> brain's wiring diagram, how much does it change the results of our graph analysis?**
>
> A quick bit of background. A connectome is a map of a brain's wiring. In that map, **neurons
> are the points (nodes)** and **synapses — the connections between neurons — are the lines
> (edges)**. This map is built from electron-microscope images, and the automated process that
> builds it is not perfect — it makes mistakes. Those mistakes change the map we analyze.
>
> So we wanted to know: which kinds of mistakes hurt the most, and which ones we can safely
> ignore?

**Key numbers to say:** 5 connectomes (BANC, FAFB, MANC, MCNS, MAOL), 5 error types, error rates up to 20%.

## Notes (from the deck) — for your reference

> FlyWire connectomes are directed, weighted graphs: neurons are nodes and synapses are edges
> with weights. Automated segmentation of electron-microscopy data is imperfect, so reconstruction
> errors change the observed graph. Our question: as the error rate grows from zero to twenty
> percent, how strongly does each error type perturb graph structure and downstream graph
> analyses? We evaluate five error models — missed synapses, false synapses, synapse-count
> measurement noise, split neurons, and merged neurons — across five connectomes: BANC, FAFB,
> MANC, MCNS and MAOL. This update walks through the design, the results per error model, and what
> they mean.

---

# Slide 2 — Experimental Design (~30 s)

## What's on the slide

- **Flow diagram (4 boxes):**
  1. **Baseline Connectome** — the correct, unmodified brain map.
  2. **Simulated Reconstruction Error** — we inject one error type at a controlled rate.
  3. **Graph Analyses** — we run the same analyses on the damaged map.
  4. **Cross-Dataset Comparison** — we repeat everything on all five brains and compare.
- **Numbers row:**
  - *5 connectomes* — five brains.
  - *5 error models* — missed, false, noise, split, merge.
  - *up to 20% error* — the strongest rate tested.
  - *1,030 trials* — total runs (all combinations × multiple random seeds).
  - *6,180 analysis rows* — the results table has 6,180 rows (1,030 trials × 6 analyses each).
  - *6 analyses per trial* — six graph analyses run per trial.
  - *0 failed rows* — every single run succeeded. Nothing crashed.
- **"Reliability checks" box:** *"Baseline invariance and graph identities verified — the
  perturbed graphs change only through the applied error model, not through analysis
  artifacts."* — in plain words: we proved that the baseline graph does not change on its own
  and that the experiment pipeline is not introducing changes by accident. **Every change we see
  is caused by the error we added.**

## Say this

> Here is how we set up the experiment. **We take a real, correct brain map, deliberately add a
> controlled amount of error, run the same set of graph analyses, and compare the results to the
> original.**
>
> We do this across **five different connectomes** and **five different error types** — missed
> synapses, false synapses, measurement noise, split neurons, and merged neurons — at error rates
> going up to 20%.
>
> In total that gives us **1,030 trials and 6,180 analysis rows, with zero failures**. Every
> change we see is caused by the error we added, because we verified the original maps don't
> change on their own.

**Key numbers to say:** 1,030 trials, 6,180 analysis rows, 0 failed rows.

## Notes (from the deck) — for your reference

> The design is deliberately simple: take the baseline connectome, apply a simulated reconstruction
> error at a controlled rate, run the same graph analyses, compare across all five datasets. The
> scale: five connectomes, five error models, rates up to twenty percent, one thousand thirty
> trials, six thousand one hundred eighty analysis rows, zero failures. Baseline invariance and
> graph identities were verified, so every change we see is caused by the error model itself.

---

# Slide 3 — What Does Each Error Model Change? (~45 s)

## What's on the slide

- **Title: "What Does Each Error Model Change?"** — the slide answers one question: which
  graph property does each error model actually move?
- **Subtitle line (right under the title):** *"Mean % change at 20% error across evaluated
  datasets — each value is the mean across datasets with available runs, not a single
  connectome."* This tells the audience the exact meaning of every number on the slide:
  a **mean across datasets** at the **20% error rate**.
- **Main visual: the signed heatmap** (`signed_heatmap_20pct.png`), centered. Rows = error
  models, columns = six graph properties (**Edges, Synapses, Mean degree, WCC, SCC, Weight
  variance**).
  - **Color = direction:** orange-red = the property **decreased**; blue = it **increased**;
    near white = unchanged (~0%).
  - **Read it by row** — each row is one error model's "fingerprint".
- **"What it means" strip below the heatmap** — one line per error model: model → affected
  metrics → direction/magnitude → plain-language interpretation:
  - **Missed:** target −20% vs. mean edge −4.9% — *removing synapses does not necessarily
    eliminate the connection*
  - **False:** more edges added +19.4%, weight variance −13.8% — *weight becomes more distributed*
  - **Split:** degree −14.9%, WCC/SCC +17.7%/+17.6% — *edges spread over more identities*
  - **Merge:** edges −10.9%, WCC −8.6%, SCC −9.0%, weight var. +46.9% — *identities collapse*
  - **Count noise:** weight var. +5.5% — *control; topology flat*
- **Small gray footnote:** *"Mean across evaluated connectomes; dataset-level values vary."*
- **Takeaway bar:** *"Different errors → distinct graph fingerprints."*

## Say this

> This is the one-slide summary. **Every number here is the mean change across the datasets
> with available runs, at the same 20% error rate** — so it is the typical response, not any
> single connectome. The colors show direction: orange means a property went **down**, blue
> means it went **up**, white means no change.
>
> Reading by row:
> - **Missed synapses** — the target is 20% synapse loss, but the mean edge loss is only
>   about 5%: removing individual synapses does not necessarily eliminate the underlying
>   neuron-to-neuron connection.
> - **False synapses** — more edges are added (+19%); the weight budget spreads thinner (weight
>   variance −13.8%).
> - **Count noise** — only the weights move (+5.5%); topology stays flat — it's our control.
> - **Split errors** — degree −15%, components fragment: the same edges are spread over more
>   neuron identities.
> - **Merge errors** — edges −11%, weight variance +47%: neuron identities collapse and
>   connectivity concentrates.
>
> The main takeaway: **different errors leave distinct graph fingerprints** — which property
> moves depends on the error type. I'll walk you through each fingerprint on the next slides.

**Key numbers to say:** weight variance −30.3% (missed) vs +46.9% (merge); missed −20% synapses
→ only −4.9% edges; split fragments WCC/SCC ~+18%; noise leaves topology at ~0%.

## Notes (from the deck) — for your reference

> This is the one-slide summary: at the same twenty percent error rate, each error model moves
> a different set of graph properties, and the diverging colors show the direction — orange for
> decreases, blue for increases. Every value shown is the mean across the datasets with
> available runs, so it is the typical response, not any single connectome. Read it by row.
> Missed synapses: the target is twenty percent synapse loss, but the mean edge loss is only
> about five percent — removing individual synapses does not necessarily eliminate the
> underlying neuron-to-neuron connection. False synapses: edges up about nineteen percent on
> average, and the weight budget spreads thinner (weight variance down ~14%). Count noise: only
> weighted statistics move, topology is untouched —
> it is our control. Split errors: mean degree down fifteen percent, components fragment. Merge
> errors are the most structurally disruptive of the five in these simulations: edges down
> eleven percent, weight variance up forty-seven percent. The rest of the talk goes through
> each fingerprint with the trend graphs from the experiment.

---

# Slide 4 — Missed Synapses: the Synaptic Layer Shrinks (~35 s)

## What's on the slide

- **Intro line (italic):** *"Synapse removal: the count falls one-for-one with the rate."*
  — removing X% of synapses removes exactly X% of the synapse total (the mechanism behind the
  "target synapse loss" number below).
- **Left figure — Total synapses.** Caption: *"Target synapse loss: −20% (exact, every
  dataset)."* — the synapse count drops by exactly the error rate on all five brains, so this
  is the **intended error level**, not an average. The model behaves as designed.
- **Right figure — Edge count.** Caption: *"Mean edge loss: −4.9% (range ≈ 0 to −9.7%) —
  most connections survive."* — although 20% of synapses are gone, only ~5% of connections
  disappear **on average** across the five connectomes (the range shows the spread: MCNS ≈ 0%
  up to MANC −9.7%). Why? Because a connection only disappears when *all* of its synapses are
  removed; connections with many synapses almost always survive.
- **Takeaway bar:** *"Weighted layer erodes (weight variance −30.3%) but most connections
  survive: −20% synapses → only −4.9% edges; PageRank r = 0.999."* — the *weights* change a lot
  (weight spread −30%), but the *structure* (most neuron-to-neuron connections) and the
  importance ranking (PageRank = 0.999) barely move.

## Say this

> First error type: **missed synapses** — connections that existed but were not detected.
>
> At the 20% error rate, we remove **exactly 20% of all synapses**, on every single dataset — so
> this is the **target loss**, not an average. But here's the interesting part: **the mean edge
> loss is only about 5%** (with per-dataset values from ≈0% to −9.7%). Why? Because removing
> individual synapses does not necessarily eliminate the underlying neuron-to-neuron connection
> — a connection survives as long as at least one of its synapses remains. So most connections
> stay intact.
>
> The fingerprint of this error: **the weighted layer erodes — weight variance drops by 30% —
> but most of the graph structure and the ranking of important neurons barely move at all.**
> PageRank — our measure of "which neurons matter most" — stays at 0.999 correlation.

**Key numbers to say:** −20% synapses, but only −4.9% edges; weight variance −30.3%; PageRank r = 0.999.

## Notes (from the deck) — for your reference

> Missed synapses remove exactly twenty percent of synapses at the twenty percent error rate — the
> removal scales one-for-one, on every dataset, so this is the target loss, not an average. But
> the mean edge loss is only about five percent: individual synapses are removed, and a
> neuron-to-neuron connection survives as long as at least one of its synapses remains, so
> connections supported by many synapses rarely disappear entirely. The result is a distinctive
> fingerprint: the synaptic layer erodes — weight variance drops about thirty percent on average —
> while most neuron-to-neuron connections and the ranking of important neurons stay almost
> untouched.

---

# Slide 5 — False Synapses: Connectivity Is Inflated (~30 s)

## What's on the slide

- **Intro line:** *"Hallucinated edges inflate connectivity; the weak component stays flat, the
  core grows."* — "hallucinated" = fake edges that don't exist in reality. They make the graph
  bigger. The *weak* component (whole reachable group) barely changes because the new edges land
  inside it, but the *strong core* grows.
- **Left figure — Edge count.** Caption: *"Mean edge-count change: +19.4% at 20% —
  connectivity inflated."* — on average, the number of connections grows by ~19% at the 20%
  rate across the three connectomes with false-synapse runs (BANC, FAFB, MCNS). The graph is
  now denser than reality.
- **Right figure — Strong component.** Caption: *"SCC: +0.6% mean — new edges extend the
  core."* — the strongly connected core (where you can reach every neuron following the arrows)
  grows slightly on average.
- **Takeaway bar:** *"More edges are added (mean +19.4%) while weight variance decreases
  (−13.8%); PageRank similarity remains high (r = 0.994)."* — connections go up on average, but the
  same total synapse budget now spreads over more edges, so the weights get thinner. The ranking
  still stays stable (r = 0.994).

## Say this

> Next: **false synapses** — connections that don't exist in reality but were added by mistake.
> This is the opposite of the last case.
>
> Here the graph gets **inflated**: the mean edge-count change is about **+19%** at the 20% rate
> (averaged over the three connectomes with false-synapse runs). The new, fake connections land
> inside the big connected core, so the weak component stays flat, while the strongly connected
> core grows a little.
>
> Because the same amount of connection strength is now spread over more edges, the **weights get
> diluted** — weight variance drops by about 14%. And again, the overall ranking of neurons stays
> very stable, with PageRank at 0.994.

**Key numbers to say:** +19.4% edges; weight variance −13.8%; PageRank r = 0.994.

## Notes (from the deck) — for your reference

> False synapses — hallucinated connections — do the opposite of missed synapses: edges grow by
> about nineteen percent at the twenty percent rate, inflating connectivity. The interesting
> detail is the asymmetry between the two components: new edges land inside the already-giant weak
> component, so it stays flat, while the strongly connected core grows slightly — the directed
> structure expands. Weight variance is diluted as the same synapse budget spreads over more edges,
> and PageRank stays at point-nine-nine-four.

---

# Slide 6 — Synapse-Count Noise: the Control Result (~25 s)

## What's on the slide

- **Left figure — Edge count.** Caption: *"Mean edge-count change: 0.0% — never touches
  topology."* — the number of connections does not change at all.
- **Small note under it:** *"Degree, WCC, SCC, reciprocity are equally flat."* — every
  structural metric is unchanged. This is the "control" proof.
- **Right table — "Metric | Mean change at 20%"** (with the small gray note "Mean across
      the five connectomes" underneath):

  | Metric | Change | Meaning |
  |---|---|---|
  | Edge count | 0.0% | No change in connections. |
  | Mean degree | 0.0% | No change in how connected neurons are. |
  | WCC / SCC | 0.0% | No change in components. |
  | Reciprocity | 0.0% | No change in two-way connections. |
  | Weight variance | +5.5% | Only the *weights* move — and only slightly. |
  | PageRank r | 0.999 | Ranking basically perfect. |

- **Takeaway bar:** *"Measurement noise is benign: only weighted statistics move (weight
  variance +5.5% mean); topology is unchanged, while PageRank remains highly stable."* — this
  slide is the *control
  result*: it proves that counting noise alone does not damage the graph structure.

## Say this

> The third error type is **measurement noise** — small random errors in counting how many
> synapses each connection has. This is our **control experiment**: by design, it only touches the
> weights, and nothing else.
>
> And that's exactly what we see. **Edge count, degree, components, and reciprocity all stay at
> 0.0% change.** Only the weight variance moves — by about 5.5%, which matches the theory.
>
> The scientific point: **if our synapse counts are slightly off, we can still trust the overall
> structure of the graph.** Unweighted analysis is basically unaffected.

**Key numbers to say:** 0.0% on all topology metrics; +5.5% weight variance; PageRank r = 0.999.

## Notes (from the deck) — for your reference

> Synapse-count measurement noise is the control model — by design it adds proportional noise to
> the weights and nothing else. And that is exactly what the experiment shows: the edge count is
> perfectly flat, as are degree, components and reciprocity, while the weight variance moves by
> five and a half percent at the twenty percent rate — matching the theoretical prediction. The
> scientific point: imprecision in synapse counts is comparatively benign; unweighted graph
> analyses are unaffected by it.

---

# Slide 7 — Split Errors: Fragmentation (~35 s)

## What's on the slide

- **Intro line:** *"Over-segmentation: one neuron is cut into several pieces; the same edges
  are re-assigned exactly once."* — one real neuron is wrongly cut into several pieces, so the
  same connections now run between more "fake" neurons.
- **Schematic (left column): BEFORE/AFTER mini-diagram** — BEFORE: 5 neurons with 4 edges;
  AFTER SPLIT: 8 identities carrying the same 4 edges, so each identity has fewer connections.
  Caption underneath: *"Mechanism: same edge budget, spread thinner per neuron."*
- **Middle figure — Mean degree.** Caption: *"Mean −14.9% — edge budget preserved but
  diluted."* — no connection is lost (the "budget" is preserved), but each piece of a neuron has
  fewer partners, so the average degree falls.
- **Right figure — Strong component.** Caption: *"Mean +17.6% (WCC +17.7%) —
  fragmentation."* — the largest components *grow* in relative size because the graph breaks
  into more, smaller islands. If components shrink in absolute size, why does the number go
  *up*? Because as the graph fragments, the largest component's share of the graph changes —
  the key idea to convey: **the graph breaks apart**.
- **Takeaway bar:** *"Edges preserved (edge count ≈ 0%) but redistributed over more neuron
  identities → fewer connections per neuron → components fragment (mean degree −14.9%; WCC/SCC
  +17.7%/+17.6%); PageRank r = 0.995."* — the full mechanism chain: edge budget kept, but spread
  over more identities; degree falls; components fragment; the ranking holds.

## Say this

> Fourth: **split errors** — when the segmentation process wrongly cuts one neuron into several
> pieces. The same wiring is still there, but it now runs between more "fake" neuron identities.
>
> Split errors preserve the same edge budget but **redistribute those edges across more neuron
> identities** — that's what the BEFORE/AFTER sketch on the slide shows. The result: the mean
> degree drops by about 15% (each piece of a neuron has fewer connections than the whole neuron
> had), and the graph fragments — the largest components change by about +18% as the graph
> breaks into more, smaller islands.
>
> What stays put: the edge count and synapse count, because nothing is lost — everything is just
> spread out. PageRank stays at 0.995.

**Key numbers to say:** mean degree −14.9%; components +17.6%/+17.7%; PageRank r = 0.995.

## Notes (from the deck) — for your reference

> Split errors — over-segmentation — behave completely differently. The edge budget is preserved:
> every edge is rewired exactly once, so the edge count stays flat. But because the same edges now
> run between more neuron identities, the mean degree falls by about fifteen percent on average,
> and the connectivity fragments: the largest weak and strong components both grow by about
> eighteen percent on average as the graph breaks into more, smaller pieces. This is a structural
> fingerprint — degree and components move, while edge and synapse counts stay put, and PageRank
> holds at point-nine-nine-five.

---

# Slide 8 — Merge Errors: Most Structurally Disruptive in This Experiment (~30 s)

## What's on the slide

- **Intro line:** *"Under-segmentation: identities collapse, edges lost, connectivity
  concentrates."* — the opposite of splitting: several real neurons are wrongly joined into one.
  Connections get squeezed together.
- **Left figure — Edge count.** Caption: *"Mean −10.9% — connections collapse as identities
  merge."* — when two neurons become one, some connections disappear (they become self-loops or
  duplicates), so the edge count falls on average.
- **Right figure — Strong component.** Caption: *"Mean −9.0% (WCC −8.6%) — the graph
  condenses."* — the components shrink on average: the graph packs into fewer, bigger pieces.
- **Takeaway bar:** *"Most structurally disruptive in these simulations: mean weight variance
  +46.9%, edges −10.9%, components ~9%; PageRank r = 0.989."* — the biggest single change in
  the whole study is the +46.9% weight variance: the same total connection strength is now
  concentrated into fewer, heavier connections. PageRank drops to 0.989 — still high, but the
  lowest of the five.

## Say this

> Fifth and last error type: **merge errors** — when the segmentation wrongly joins two or more
> neurons into one. This is the mirror image of splitting.
>
> In these simulations, merge errors produced **the strongest structural disruption of the five
> error models**. When neurons collapse together, connections disappear: the mean edge loss is
> about 11%. The graph condenses — the largest components shrink by around 9% on average. And
> because the same total connection strength is now squeezed into fewer, heavier connections,
> **weight variance jumps by almost 47% on average — the single biggest change in the whole
> study.**
>
> Everything moves at once: connectivity, weights, and neuron identity. Even so, PageRank stays
> at 0.989 — the lowest of the five, but still very high. (Note: "most disruptive here" means
> in these simulations, not a claim about real biological error rates.)

**Key numbers to say:** edges −10.9%; components −9%; weight variance +46.9%; PageRank r = 0.989.

## Notes (from the deck) — for your reference

> Merge errors — under-segmentation — produced the strongest structural disruption in these
> simulations. When neuron pairs collapse into one, edges are lost — on average down eleven
> percent at the twenty percent rate — and the components shrink by around nine percent on
> average as the graph condenses. Because the synapse budget is conserved but concentrated into
> fewer, heavier connections, the mean weight variance jumps by forty-seven percent. Everything
> moves at once: connectivity, weights, and neuron identity. PageRank stays at point-nine-eight-
> nine — still highly correlated, but the lowest of the five models.

---

# Slide 9 — PageRank Robustness Across Evaluated Connectomes (~40 s)

## What's on the slide

- **Two figures** showing the extremes:
  - **Left: `pagerank_missed_synapses.png`** — the best case (missed synapses).
  - **Right: `pagerank_merge_errors.png`** — the worst case (merge errors).
- **Table header** now says **"Mean at 20%"** — these are means across the datasets with
  runs, like the rest of the deck.
- **Small gray footnote under the table:** *"Means use available datasets; some
  error-model/dataset combinations were not run or had partial trials."* — this is why the
  title says "Across Evaluated Connectomes": false-synapse runs are unavailable for MANC and
  MAOL, and FAFB/MANC merge runs have partial trial counts.
- **Table — "Mean at 20%":**

  | Measure | Missed | False | Noise | Split | Merge |
  |---|---|---|---|---|---|
  | Pearson r | 0.999 | 0.994 | 0.999 | 0.995 | 0.989 |
  | Spearman | 0.998 | 0.971 | 0.999 | 0.976 | 0.989 |
  | Top-100 | 0.980 | 0.951 | 0.976 | 0.956 | 0.924 |

  Read it like this: the first two rows are correlations of the *ranking* — all above 0.96, so
  the global order of neurons survives every error type. The third row (Top-100) is lower —
  under merge errors only 92.4% of the top-100 hubs stay in the top-100 (and 86% on the BANC
  dataset specifically) — so the *exact list* of top hubs is more fragile than the overall order.
- **Takeaway bar:** *"At 20%: Pearson r ≥ 0.977, Spearman ≥ 0.96 — PageRank similarity
  remains high, although top-100 hub identities are more sensitive."* — the headline: no matter
  the error type, global PageRank similarity stays high, but the *exact list* of top hubs is
  more sensitive.

## Say this

> Let's zoom out and look at **how robust the importance ranking is** across all five error
> types at the 20% rate.
>
> The two graphs show the best and worst cases. **Missed synapses** are the best case — PageRank
> similarity stays at or above 0.998. **Merge errors** are the worst case — but even then,
> similarity stays at or above **0.977** on every dataset.
>
> The table shows the means across the datasets with runs: Pearson is at least 0.977, Spearman
> at least 0.96. So **global PageRank similarity remains high** even when the structure changes
> a lot.
>
> One caveat: the **top-100 hub overlap** is more fragile — it drops to 0.92 under merge errors
> (and 0.86 on BANC). So the overall ranking is stable, but exactly *which* neurons are the top
> hubs is more sensitive: some top hubs are displaced.

**Key numbers to say:** Pearson ≥ 0.977, Spearman ≥ 0.96 at 20%; top-100 overlap is the fragile part.

## Notes (from the deck) — for your reference

> How robust is PageRank? The two figures show the extremes: missed synapses — the best case, with
> similarity at or above point-nine-nine-eight — and merge errors — the worst case, which still
> stays at or above point-nine-seven-seven at twenty percent error on every dataset. The table
> summarizes all five models with the means across the datasets that have runs: Pearson at least
> point-nine-seven-seven, Spearman at least point-nine-six across the board. Two refinements: the
> top-one-hundred hub overlap is more sensitive — it drops to point-eight-six under merge errors
> on BANC — so the global ranking stays similar even when some top hubs are displaced; and local
> measures like degree and component size move earlier, acting as early-warning indicators of
> structural decay.

---

# Slide 10 — What the Results Mean (~30 s)

## What's on the slide

- **Block 1: "Different error types have distinct graph fingerprints."** — the detail:
  - Missed / false synapses → change connectivity and weighted statistics.
  - Noise → changes weighted statistics only.
  - Split errors → change degree and component structure.
  - Merge errors → strongly affect connectivity, component structure, and weight distribution.
- **Block 2: "Split and merge move the graph in opposite directions."** — the mirror image:
  - **Split** preserves edges, spreads them over more neurons, fragments components.
  - **Merge** collapses neuron identities, loses edges, concentrates connectivity.
- **Block 3: "Robustness is metric-dependent."** — structure can change a lot while the global
  PageRank stays highly correlated. An error can distort the graph without destroying which
  neurons matter most.

## Say this

> Let's step back and ask: **what do all these results actually mean?**
>
> Three conclusions.
>
> **First**, each error type leaves a distinct fingerprint — missed and false synapses change
> connectivity and weights, noise changes weights only, split errors change degree and components,
> and merge errors strongly affect connectivity, component structure, and weight distribution.
>
> **Second**, split and merge are mirror images: **split spreads the graph out and fragments it,
> merge collapses it and concentrates it.**
>
> **Third**, robustness depends on the metric you look at. The structure can change a lot while
> the global PageRank ranking stays stable. An error can distort the graph without destroying
> which neurons matter most.

**Key numbers to say:** none needed — this is the "so what" slide.

## Notes (from the deck) — for your reference

> Three conclusions. First, every error type leaves a distinct fingerprint — connectivity and
> weight statistics for missed and false synapses, degree and components for split errors,
> everything for merge errors. Second, split and merge are mirror images: split preserves edges
> and fragments connectivity; merge collapses neurons and concentrates it. Third, robustness is
> metric-dependent — structural metrics can move a lot while the global PageRank ranking stays
> stable.

---

# Slide 11 — Analysis & Conclusions (~40 s)

## What's on the slide

- **Bullet 1: "Connectivity layer vs. neuron-identity layer."** — the two layers:
  - *Connectivity layer* (edges, synapses, weights) → responds to missed and false synapses.
  - *Neuron-identity layer* (which nodes exist, how they're grouped) → responds to split and
    merge errors.
  - The two layers react to completely different error types.
- **Bullet 2: "Weighted statistics are the early indicators."** — weight variance is the most
  sensitive metric (−30.3% missed — the weighted layer erodes; +46.9% merge — connectivity
  concentrates; +5.5% noise — the control, topology untouched); it moves more strongly than
  component structure for four of the five models (split is the exception).
- **Bullet 3: "Component structure is the structural indicator."** — WCC/SCC catch split
  fragmentation (WCC +17.7%, SCC +17.6%) and merge condensation (WCC −8.6%, SCC −9.0%) that edge
  counts alone miss → **SCC should stay a headline metric**.
- **Bullet 4: "PageRank is comparatively robust."** — global PageRank similarity stays high
  (Pearson r ≥ 0.977, Spearman ≥ 0.96) even when structure changes; top-100 hub overlap is the
  fragile part (some top hubs are displaced).
- **Bullet 5: "Consistent across evaluated connectomes."** — the datasets with runs behave the
  same way → benchmarking effort is best spent on **missed-synapse detection**, the error type
  with the most disproportionate impact.
- **Small limitations line (in gray, at the bottom):** *"Limitations: simulated error models,
  not empirical measurements; FAFB merge (2 trials/rate) and MANC merge (1 trial/rate) are partial
  runs; MANC and MAOL lack false-synapse runs; assortativity% is unreliable (near-zero
  baseline)."* — be honest about these if asked (see Q&A 12).

## Say this

> Finally, let's put all the pieces together.
>
> **First**, the graph has two layers: the **connectivity layer** — edges, synapses, weights —
> which responds to missed and false synapses, and the **neuron-identity layer** — which neurons
> exist — which responds to split and merge errors. Different errors attack different layers.
>
> **Second**, **weighted statistics are the early warning system** — weight variance moves more
> strongly than component structure for four of the five error types (split is the exception).
>
> **Third**, **component structure is the best structural indicator** — it catches the
> fragmentation and condensation that edge counts alone miss. That's why we keep SCC (the strongly
> connected component) as a headline metric.
>
> **Fourth**, global PageRank similarity stays high even when structure changes substantially,
> although some top hubs are displaced — the top-100 hub list is the fragile part.
>
> **Fifth**, the evaluated connectomes behave the same way — so our benchmarking effort is best
> spent on **missed-synapse detection**, the error type with the most disproportionate impact.
>
> One honest limitation: these are **simulated errors, not real measured errors** — and a few
> datasets had partial runs. But the patterns are clear and consistent.
>
> **Thank you — I'm happy to take questions.**

**Key numbers to say:** weight variance is the most sensitive metric; SCC as headline metric; all 5 connectomes agree.

## Notes (from the deck) — for your reference

> Putting the pieces together. First, there are two distinct layers in the graph: the connectivity
> layer — edges, synapses, weights — which responds to missed and false synapses, and the
> neuron-identity layer — which nodes exist — which responds to split and merge errors. Second,
> weighted statistics are the most sensitive indicator: weight variance moves more strongly than
> component structure for four of the five models (split is the exception). Third, component
> structure is the best structural indicator: it
> captures the split fragmentation and merge condensation that edge counts alone cannot see —
> which is why SCC remains a headline metric. Fourth, PageRank is comparatively robust: global
> PageRank similarity remains high even when structure changes substantially, while hub identity is
> the fragile part. Fifth, the patterns are consistent across the evaluated connectomes, which
> means benchmarking effort is best spent on missed-synapse detection — the error type with the
> most disproportionate impact. With the caveat that these are simulations, not empirical
> measurements.

---

# Likely Questions & Easy Answers

## 1. Why should we care about reconstruction errors at all?

Because the brain map is built by an automated pipeline that is not perfect. If the map has
mistakes, then every analysis we run on the map inherits those mistakes. Knowing *which* mistakes
matter tells us which conclusions we can trust and which error types we should work hardest to
fix.

## 2. What is a node, an edge, a synapse — in simple words?

- **Node (neuron):** a point in the graph — one brain cell.
- **Edge (connection):** a line between two neurons — they talk to each other.
- **Synapse:** the actual physical contact point. One connection can have many synapses, and the
  number of synapses is the **weight** — how strong the connection is.
- So the graph is: neurons as points, connections as lines, and each line has a weight telling us
  how strong it is.

## 3. What does "degree" mean?

The degree of a neuron is simply **how many other neurons it is directly connected to**. If the
average degree drops, neurons have fewer direct partners — the wiring is thinner.

## 4. What are WCC and SCC — the "components"?

A component is a group of neurons that are connected to each other (directly or indirectly).

- **WCC (weakly connected component):** connected if we ignore the direction of the connections.
- **SCC (strongly connected component):** connected only when we respect the direction — you can
  reach every neuron in the group by following the arrows.

We watch the **largest** component. Under split errors it *grows* in relative terms (the graph
fragments into more, smaller pieces); under merge errors it *shrinks* (the graph condenses).

## 5. What is PageRank, and why is it so robust?

PageRank is a way to rank which neurons are most important: **a neuron is important if other
important neurons connect to it** (same idea as Google ranking web pages). We found the overall
ranking barely changes even at 20% error, because importance is driven by the whole pattern of
connections, not by any single edge — so losing a few edges doesn't reshuffle the ranking much.

## 6. Which error type should we worry about the most?

**Merge errors** cause the biggest changes — weight variance up almost 47%. But at *equal rates*,
**missed synapses** are the best target for benchmarking effort, because they damage the synaptic
layer a lot and are common in practice. False synapses are also important because they *add*
structure rather than just removing it.

## 7. Why did you use five different connectomes?

To check that our results are not specific to one brain. All five datasets — BANC, FAFB, MANC,
MCNS, MAOL — showed the same qualitative patterns, which gives us confidence the findings are
general.

## 8. Are these results from real errors?

No — and that's an important honesty point. **We simulated** the errors at controlled rates. Real
errors may be distributed differently. The value of simulation is that we can control exactly
what error we add, isolate its effect, and compare error types fairly. Real error measurements
are a natural next step.

## 9. Why is measurement noise so harmless?

Because it only changes the *weights* (how many synapses we count) by a small random amount. It
does not add or remove connections, and it does not change which neurons exist. So anything that
ignores weights — like edge count, degree, or components — sees zero change.

## 10. What does "weight variance" tell us, and why is it so sensitive?

Weight variance measures **how spread out connection strengths are**. It is sensitive because it
reacts to every small change in weights: removing synapses lowers it, merging neurons
concentrates strength and raises it. It's like a canary in the coal mine — it moves early and
moves the most.

## 11. Why does the ranking survive but the hubs don't?

The overall ranking is an average over millions of neurons, so it barely moves. The **top-100 hub
list** is a much smaller, more precise claim — it depends on exactly which few neurons sit at the
very top. A small amount of error is enough to swap a few neurons in and out of that narrow list,
even though the global order stays almost the same.

## 12. Were there any limitations to this study?

Yes, and they're on the slides: these are **simulated** errors; FAFB and MANC merge runs had
fewer trials; MANC and MAOL have no false-synapse runs; and one metric (assortativity) was
unreliable because its baseline is near zero. None of these change the main conclusions.

## 13. What is the practical takeaway for someone analyzing connectomes?

Three things:

1. **Structure is safe** — global wiring and importance rankings are robust to moderate error.
2. **Synaptic statistics are fragile** — treat weight-based numbers with care.
3. **Know your error type** — if your dataset has merge errors, be extra careful; if it only has
   count noise, you can relax.

## 14. What do you mean by "fingerprint"?

A fingerprint is the **unique pattern of changes** each error type produces. For example, missed
synapses only hurt the weights; split errors only hurt degree and components; merge errors hurt
everything at once. If you see a particular pattern in a real dataset, you can guess which error
type caused it.

## 15. Why is SCC (the strongly connected component) your "headline" metric?

Because it is the **best structural early-warning signal**. Edge counts alone missed the damage:
under split errors, edges stay the same but the graph fragments — and only the component
structure reveals that. SCC catches both fragmentation (split) and condensation (merge), so it
tells us more than simpler counts.
