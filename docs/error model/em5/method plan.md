# Error Model 5 (EM5): Merge Errors (Under-Segmentation)

> **This document defines the scientific methodology only.** Implementation is
> defined in `docs/error model/em5/implementation roadmap.md`. The methodology
> must remain implementation independent — future implementation changes must
> not alter the scientific algorithm.
>
> **Revision record:** v1.3 — corrected the synthetic merge-ID generation:
> replaced the non-injective multiplication encoding with a mathematically
> injective pairing function (Szudzik elegant pairing), updated §13, and
> added the synthetic-ID uniqueness gate to Validation (§14) and the
> independence statement to Assumption 1 (§5). v1.2 — surrogate framing pass:
> reframed `top_region`, shared-partner overlap, and Jaccard as proxies /
> ranking evidence rather than biological rules; added the graph-level
> surrogate statement, the morphology-limitation acknowledgement, and the
> literature-vs-surrogate table. v1.1 (methodology-only revision) — added
> hard anatomical constraints (region, soma side) as the first candidate
> stage; corrected the Jaccard equation; redefined the error rate per
> eligible neuron; separated implementation details (pruning, complexity,
> retries, caching) into the implementation roadmap; reclassified every
> assumption. The implementation roadmap remains the architecture source of
> truth and is unchanged except for consistency notes.

## 1. Objective

The objective of Error Model 5 (EM5) is to simulate segmentation **merge
errors** that occur during automated EM reconstruction, when two *distinct*
biological neurons are reconstructed as **one** neuron.

A merge error is the exact inverse of a split error (EM4):

| | Split error (EM4) | Merge error (EM5) |
| --- | --- | --- |
| Biology | one neuron → two reconstructed neurons | two neurons → one reconstructed neuron |
| Reconstruction phase | segmentation / agglomeration fails to join two portions of the *same* cell | agglomeration fuses portions of *different* cells |
| Graph-level effect | vertex count increases, edge count preserved | vertex count decreases, edge count decreases (parallel collapse + self-loop removal) |
| Underlying biology | unchanged | unchanged |

Like EM4, the error does **not** remove synapses or alter neuronal physiology.
It only changes the reconstructed graph representation. EM5 approximates the
graph-level consequences of reconstruction over-merging while preserving the
original biological connectivity as far as the graph allows.

## 2. Biological Motivation

The reconstruction pipeline is:

```
EM Images
    ↓
Segmentation
    ↓
Agglomeration
    ↓
Neuron Reconstruction
    ↓
Connectivity Graph
```

Merge errors occur during Segmentation or Agglomeration when two portions of
**different** neurons are fused into one object. The biological neurons remain
unchanged — only the digital reconstruction merges their identities.

The actual agglomeration algorithm operates on image-derived morphology and
membrane continuity rather than graph connectivity. EM5 approximates only the
resulting graph-level consequences because those image-level signals are
unavailable.

## 3. Scope

The model is designed for graph-level connectomes (neuron connectivity graphs)
only. It does **not** simulate EM image artifacts, segmentation masks,
supervoxels, neuron meshes, or skeletons — these data are unavailable in BANC.

## 4. Available Information

Same as EM4: directed, weighted graph (nodes = neurons, edges = synaptic
connections, weight = `syn_count`, direction = pre → post), plus metadata:
degree, partner neurons, neuropil, neurotransmitter, cell class, cell type,
**anatomical region** (`top_region`), and **soma side** (`soma_side`:
left/right/bilateral). Morphology (skeleton, mesh, coordinates, branch
geometry, cable length) is unavailable.

## 5. Scientific Assumptions

Every assumption is classified below as **supported by the literature**,
**a reasonable proxy** (an explicit modelling choice, not a biological claim),
or **an implementation choice** (moved to the implementation roadmap).

1. **Merge errors occur at the neuron-pair level.** Two neurons merge into
   exactly one reconstructed neuron. [Supported — split and merge errors are
   the two canonical, well-documented reconstruction error classes in EM
   connectomics (e.g., Januszewski et al., 2018; Scheffer et al., 2020), and
   an over-merge is a pairwise object fusion.] Multi-way merges (3+ neurons
   into one) are outside the current scope, though disjoint pairs can be
   merged in the same trial. **Collision-free synthetic IDs** (a
   mathematically injective pairing function, §13) guarantee that every
   merge event remains an **independent binary merge** throughout temporary
   graph construction: distinct pairs can never share a merged-ID key, so no
   pair is silently fused with an unrelated one.
2. **A single neuron is a spatially contiguous object with one soma.** Its
   arbor is spatially continuous, and its soma lies on one side (left/right;
   some neurons are bilateral). [Supported — standard neuroanatomy, and the
   basis of the hard constraints in §7. Note the region label is coarse: a
   neuron may arbor across regions, so region *agreement* is used only as a
   plausibility filter, not as proof of adjacency.]
3. **A merge changes only neuron identity.** Every synapse remains attributed:
   edges incident to either source neuron are re-attached to the merged
   neuron. When two edges collapse to a parallel pair (both sources connect
   to the same partner), their synapse counts are **summed** — a single
   merged neuron shows one connection of combined strength. [Reasonable proxy
   — the standard attribution convention when proofreading merges two
   reconstructed objects; consistent with the framework's graph convention.]
4. **Without morphology, shared local graph topology is the best available
   proxy for "adjacent enough to be wrongly merged."** Two neurons that
   connect to the same partners are structurally overlapping and therefore
   plausible merge candidates. [Reasonable proxy — connectivity-based
   similarity is a validated determinant of neuronal identity in comparative
   connectomics (Witvliet et al., 2021; Schwartzman et al., 2025); sharing
   partners is the canonical "guilt by association" signal (Liben-Nowell &
   Kleinberg, 2007), already used by EM2 in this framework.]
5. **Shared-neighbourhood overlap (Jaccard) is a graph-theoretic proxy** for
   spatial proximity / functional similarity — not a claim about soma
   distance or cell bodies. [Reasonable proxy — Jaccard / shared-partner
   overlap of connectivity profiles is a standard identity-similarity measure
   in the field.]
6. **A reconstruction cannot contain self-connections.** Edges between the
   two source neurons (A→B, B→A) would become a self-loop on the merged
   neuron and are dropped; their synapse count is recorded as
   `internal_synapses_dropped`. [Reasonable proxy — a graph-validity
   convention: connectome graphs are loop-free, and a merged reconstruction
   does not connect to itself. This is a deterministic modelling rule, not
   random loss.]
7. **The perturbation represents a reconstruction artifact, not a biological
   change.** It exists only for the lifetime of a simulation trial; the
   baseline connectome is never altered. [The artifact framing is scientific;
   the immutability mechanism is an implementation choice — see the roadmap.]

**Graph-level surrogate model.** EM5 is a graph-level surrogate model. The
true biological process depends on voxel-level morphology, membrane
continuity, and spatial adjacency, none of which are available in the
released connectome datasets. Consequently, EM5 estimates biologically
plausible merge candidates using anatomical metadata followed by
graph-topological similarity. The objective is to reproduce the structural
consequences of reconstruction merges rather than the segmentation algorithm
itself.

## 6. Overall Pipeline

```
Load Graph
    ↓
Stage 1 — Hard Anatomical Constraints   (same anatomical region; soma-side
                                         compatibility)
    ↓
Neighbourhood Extraction                (partner sets, once)
    ↓
Stage 2 — Connectivity Evidence         (shared partners ≥ 1 — ranking-pool
                                         floor, evaluated on the extracted
                                         partner sets)
    ↓
Similarity Computation                  (Jaccard over partner sets)
    ↓
Candidate Set                           (eligible pairs)
    ↓
Sample Merge Pairs                      (weighted by similarity, without
                                         replacement, disjoint)
    ↓
Merge: A + B → M                        (edge re-attachment)
    ↓
Parallel Edge Collapse                  (sum synapse counts)
    ↓
Self-Loop Removal                       (A↔B edges dropped, counted)
    ↓
Validation                              (integrity + quality + achieved-vs-
                                         target quality control)
```

**Ordering rationale.** Hard anatomical constraints come **first** because
they encode biological impossibility: two neurons that cannot be the same
cell (different, incompatible soma sides) or that are not plausibly adjacent
(different dominant regions) must never enter the candidate set, regardless
of graph similarity. Partner sets are extracted next, and only then is the
graph-based evidence (shared partners, similarity) evaluated on them. This
mirrors the established EM2 pipeline in this framework, which already applies
a region constraint before computing connectivity similarity and declares a
soma-side constraint in its configuration.

**On probability calibration.** An alternative ordering that includes a
"probability calibration" stage was considered and deliberately **not**
adopted: EM5 selects an *exact* number of pairs, so there is no probability
to calibrate against a target. (In EM1, calibration exists because per-synapse
removal is probabilistic and must hit a synapse-loss target; EM5's merge
count is exact by construction.) The equivalent scientific control is a
**quality-control gate in Validation**: achieved merge count vs target,
reported explicitly (§14).

## 7. Stage 1 — Hard Anatomical Constraints

Applied **before** any graph-similarity computation. A pair (A, B) is
eliminated if either condition fails:

- **Region compatibility.** `top_region(A) == top_region(B)`.
  *Justification:* because voxel-level spatial coordinates and morphology
  are unavailable, `top_region` is used as a **conservative anatomical
  approximation of local spatial proximity**. This filter removes
  biologically implausible candidate pairs but does **not** imply that
  neurons in different dominant regions could never be merged. The framework
  already applies the same filter in EM2 (its candidate generator processes
  pairs within `top_region` only), so no new architecture is required.
- **Soma-side compatibility.** `soma_side(A)` and `soma_side(B)` must be
  compatible: equal, or at least one is `bilateral`.
  *Justification:* a single neuron has a single soma (Assumption 2). Two
  neurons with different, non-bilateral soma sides cannot be the same
  neuron — this is a genuine hard (necessary) constraint. The framework
  already declares this constraint for EM2 in its configuration
  (`soma_side_constraint: true`); EM5 consumes the same `soma_side` node
  attribute.

These constraints are applied **first**, but they are not equivalent in
status: **soma-side compatibility is a genuine necessary condition** (a
single neuron has one soma), while the **region filter is a conservative
proxy** for missing spatial information. Satisfying them does not make a pair
a merge candidate — Stage 2 still applies the graph-based ranking filter.

## 8. Stage 2 — Connectivity Evidence (graph-based candidate ranking)

Shared connectivity is **not a biological requirement** for merge errors.
Two adjacent neurons can have completely different connectivity, and an
over-merge does not depend on shared partners. Instead, shared-partner
overlap is the **strongest graph-derived evidence available for ranking
plausible candidate pairs** when morphology is unavailable. It is the
graph-theoretic analogue of "guilt by association" (Liben-Nowell & Kleinberg,
2007) and is already used by EM2 in this framework; pairs with zero shared
partners are simply ranked lowest (Jaccard 0) and drop out of the candidate
set.

The specific minimum *count* (e.g., ≥ 3) is a calibration choice; pairs
below it are removed from the ranking pool as a quality/interpretability
floor, **not** because they are biologically impossible merges. Calibration
values live in the implementation roadmap.

> **Note (quality floor).** The previous draft required a minimum degree for
> eligibility. Degree is not a biological determinant of merge errors and the
> requirement is a quality floor (analogous to EM4's "tiny neurons cannot be
> meaningfully fragmented"). It is therefore **not part of the scientific
> eligibility** and is specified as an implementation quality rule in the
> roadmap.

## 9. Similarity Scoring

Score each candidate pair with the **Jaccard similarity** of their partner
sets:

```
jaccard(A, B) = |N(A) ∩ N(B)| / |N(A) ∪ N(B)|
```

where `N(A)` is the set of **all** partners of neuron A (pre and post).
This is the standard Jaccard index: the size of the intersection of the two
partner sets divided by the size of their union. (A pair sharing no partners
has Jaccard 0 and is excluded by Stage 2.)

**Acceptability.** Connectivity-profile overlap is a validated, standard
measure of neuronal identity and equivalence in comparative connectomics —
neurons are matched across individuals and hemispheres by shared synaptic
partners (Witvliet et al., 2021), and connectivity similarity is used for
neuron-type assignment without morphology (Schwartzman et al., 2025). Jaccard
overlap is one of the standard instantiations of this principle (matching
index / shared-neighbour overlap).

**Interpretation.** Jaccard similarity is used **solely as a ranking
function** among anatomically compatible candidates. It is **not interpreted
as the biological probability** that two neurons would merge during
reconstruction, nor as a claim that high-Jaccard pairs are actually the same
cell. The same ranking-derived weight drives sampling (§12) — a heuristic
for choosing which plausible pairs to perturb, not an estimate of biological
merge likelihood.

A minimum score (`jaccard_min`) is applied to remove negligible-overlap
pairs; the value is a calibration choice (roadmap).

## 10. Candidate Set

The candidate set is the set of all pairs that pass Stage 1 and clear the
Stage 2 / `jaccard_min` ranking floors. Scientifically, **all** such pairs
are eligible for sampling.

Enumerating and storing every such pair is a resource problem, not a
scientific one; the implementation may bound the enumeration (e.g., keep a
top-K per neuron) to remain practical on large connectomes, provided the
bound is documented and does not change the *definition* of the candidate
set. Implementation bounds are specified in the roadmap.

## 11. Error Rate

**Input:** error rate.

**Interpretation:** the **fraction of eligible neurons that participate in a
merge** (each merge absorbs exactly two eligible neurons):

```
k = round(0.5 × error_rate × n_eligible)      # number of pairs to merge
```

where `n_eligible` is the number of neurons in the candidate set (Stage 1
survivors, unique neurons).

**Example:** 10,000 eligible neurons, error rate 5% → 500 neurons absorbed →
**250 pairs merged**.

**Why this definition.**
- *Scientific interpretation:* "at a 5 % merge error rate, 5 % of eligible
  neurons are involved in an over-merge." This is a biological statement
  about the reconstruction, directly parallel to EM4's "error rate = fraction
  of eligible neurons split."
- *Reproducibility:* the denominator (`n_eligible`) is a property of the
  graph and the scientific constraints only; it does not depend on
  implementation bounds such as top-K or `jaccard_min`.
- *Cross-dataset comparability:* because the denominator is constraint-based
  rather than implementation-based, the rate means the same thing on BANC,
  FAFB, or MANC.

**Rejected alternative.** The previous draft defined the rate as the fraction
of the *ranked candidate table* selected. That is not scientifically
interpretable: the table size depends on implementation choices (top-K,
`jaccard_min`, pruning), so the same biological error would yield different
numbers on different datasets. The connectomics literature reports merge/split
errors per object or per pair of objects with varying denominators across
papers; none defines them per implementation-internal table. The per-eligible-
neuron definition is the project's chosen, dataset-comparable convention.

## 12. Candidate Sampling

- **Method:** random sampling **without replacement**, with sampling
  probability proportional to the Jaccard ranking (higher structural overlap
  ⇒ ranked more plausible — a sampling heuristic, not a biological
  probability). Falls back to uniform sampling if all weights are zero.
- **Disjointness constraint:** a neuron may participate in **at most one**
  merge per trial. This keeps merges independent and prevents chains
  (A+B and B+C), which are outside the current scope.
- If a sampled pair fails validation, it is rejected and a replacement is
  drawn. The maximum number of replacement attempts is an implementation
  detail (roadmap).

## 13. Merge Operation

For a sampled pair (A, B):

1. **Create merged vertex M** with a synthetic, collision-free root ID
   generated by a **mathematically injective pairing function** (Szudzik
   elegant pairing applied to the sorted pair: `x = min(|A|, |B|)`,
   `y = max(|A|, |B|)`). Uniqueness holds because the pairing function is
   mathematically injective, and the sorted order makes the ID independent
   of the pair's orientation.
2. **Re-attach every incident edge** exactly once:
   - `X → A` and `X → B` become `X → M`;
   - `A → Y` and `B → Y` become `M → Y`.
3. **Collapse parallel pairs:** if both `A → X` and `B → X` exist, they
   become one edge `M → X` with weight `w(A→X) + w(B→X)`. Identical rule for
   incoming edges.
4. **Remove self-loops:** `A → B` and `B → A` become `M → M`, which is
   dropped. `syn_count` lost is recorded in the metadata.

No edge is duplicated; no edge is invented.

**Temporary identifiers (no biological meaning).** Synthetic merge IDs are
temporary implementation identifiers used only during temporary graph
construction. They have no biological meaning and are discarded after
analysis.

**Namespace invariant.** Synthetic merge IDs must always occupy a namespace
disjoint from biological neuron IDs: all biological neuron IDs are positive,
so every synthetic merge ID is strictly negative (the pairing value is
negated).

## 14. Validation

Every perturbation must satisfy:

**Graph integrity**
- Vertex count reduced by exactly the number of merged pairs.
- Total synapse count preserved **except** the recorded
  `internal_synapses_dropped` from self-loop removal (asserted exactly).
- No self-loops.
- No multi-edges **introduced by the merge** (all merge-induced parallel
  pairs are collapsed with summed synapse counts).  Pre-existing parallel
  edges between non-absorbed neurons are legitimate and remain untouched.
- No duplicate / invalid root IDs.

**Synthetic-ID uniqueness**
- Every generated synthetic merge ID is unique within the merge plan; if a
  duplicate is detected, merge-plan construction aborts and an error is
  reported (a collision would silently fuse unrelated pairs, violating the
  binary-merge assumption). Uniqueness is guaranteed by construction via the
  injective pairing function and verified as a hard gate.

**Merge quality**
- Every merged vertex has at least one edge (degree ≥ 1); otherwise the pair
  is rejected and another is sampled.
- Every surviving edge is attributed exactly once (no loss, no duplication).
- A neuron never appears in more than one merge.

**Quality control (achieved vs target)**
- The achieved number of merges is compared with the target `k`. Because the
  count is exact by construction, a shortfall can only arise from bounded
  re-sampling running out of valid replacement pairs; any shortfall is
  reported explicitly in the perturbation metadata (transparency), never
  silently absorbed. (This gate replaces the probability-calibration stage
  that EM1 requires; see §6.)

## 15. Failure Handling

Reject a pair if:
- it fails the soma-side necessary condition (Stage 1 — impossible by
  construction);
- merging would produce a vertex with zero edges.

(Pairs below the region proxy filter or the Stage 2 ranking floor never
enter the candidate set by construction, so no further rejection is needed.)

Rejected pairs are recorded in the metadata (`pairs_rejected`). A replacement
pair is sampled; the attempt bound is an implementation detail.

## 16. Randomness

Single experiment seed → trial seed → pair sampling. **All** randomness is
derived from the framework's single NumPy RNG. Unlike EM4, no external
library RNG (igraph Louvain) is involved, so reproducibility is simpler.

## 17. Outputs

**Scientific outputs:** perturbed graph, merge mapping (source neurons →
merged id), selected pairs, candidate statistics, rejected pairs, achieved-vs-
target quality-control report, validation report, graph analysis results, CSV,
plots, HTML.

**Implementation outputs:** temporary merged ID, temporary lookup mapping,
perturbation metadata, validation logs, retry statistics. Implementation
outputs exist only to support execution and reproducibility (roadmap).

## 18. Biological Limitations

- The methodology does not reconstruct the agglomeration process itself; it
  approximates graph-level consequences of over-merging.
- EM5 does not estimate the physical contact between neuronal processes
  because the datasets contain no morphology, segmentation masks, or spatial
  coordinates. The model therefore approximates agglomeration decisions using
  graph-derived surrogate features after applying anatomical constraints.
- Jaccard overlap is a graph-theoretic proxy for adjacency, not a claim about
  physical proximity.
- Region labels are coarse: a neuron may arbor across regions, so the region
  constraint is a plausibility filter, not proof of adjacency.
- Only binary merges (two neurons → one) are modelled; multi-way merges are
  outside scope.
- Self-loop removal is a modelling rule: a merged reconstruction cannot
  connect to itself, so the A↔B synapse counts are reported as dropped rather
  than re-attributed.
- No network-centrality, hub, reciprocity, or synapse-weight feature is used
  as a merge determinant: the literature does not support these as drivers of
  reconstruction over-merging (which is a morphological, adjacency-driven
  process), and no such feature is part of this methodology.

## 19. Separation of Methodology and Architecture

The methodology defines biology and the perturbation algorithm only. The
following are **implementation concerns** defined in the implementation
roadmap, not in this document: candidate enumeration bounds (top-K), memory
and complexity analysis, caching, retry counts, calibration values
(`min_shared_partners` count, `jaccard_min`, quality-floor degree threshold),
synthetic-ID encoding, temporary graph construction, runners, configuration,
and export. (The *encoding detail* of the synthetic merge ID is an
implementation concern; the collision-free, order-independent,
negative-namespace properties of the ID are scientific properties of the
merge operation, §13.) Future software refactoring must not modify this
methodology; future scientific improvements should require changes only to
the EM5 perturbation model. The surrogate candidate-selection strategy is a
methodological approximation necessitated by unavailable morphology and
should not be interpreted as the mechanism used by modern segmentation
pipelines.

## 20. Literature vs. EM5 Surrogate

| Reconstruction driver (literature-supported) | EM5 surrogate |
| --- | --- |
| Physical proximity | `top_region` filter |
| Membrane continuity | unavailable |
| Morphology | unavailable |
| Agglomeration decision | graph similarity ranking |
| Merge event | node contraction |
