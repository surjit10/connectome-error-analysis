# Error Model 3 — Synapse Count Measurement

## Purpose
This document records the scientific assumptions, implementation rationale, and expected behavior of the Synapse Count Measurement error model. It serves as documentation for future development and scientific review.

## Scientific Motivation
This error model simulates measurement uncertainty in synapse quantification.

The biological connectivity is assumed to be correct:
- neurons are correctly identified,
- connected neuron pairs remain connected,
- no false connections are introduced,
- no existing connections are removed.

Only the estimated number of synapses associated with an existing connection is considered uncertain. This models reconstruction pipelines that correctly identify connectivity while producing imperfect synapse counts.

## Biological Hypothesis
The hypothesis is:
The wiring diagram is accurate, but the measured strength of each connection contains random measurement error.

Therefore:
- topology is preserved,
- connection strength is uncertain.

## Mathematical Model
For every edge:
`true_weight = syn_count`

measurement uncertainty is simulated as:
`new_weight = max(1, round(true_weight + N(0, σ)))`

where:
`σ = (error rate) × (true_weight)`

The perturbation is independently sampled for every edge.

### Why Proportional Noise?
Noise variance increases with synapse count. Large connections naturally exhibit larger absolute uncertainty than weak connections.

**Examples:**
- True Count 3 (5% Error): `σ = 0.15` (Very small variation)
- True Count 20 (5% Error): `σ = 1` (Moderate variation)
- True Count 100 (5% Error): `σ = 5` (Larger variation)

This approximates multiplicative measurement uncertainty.

## Graph Properties
This model does not:
- create edges
- remove edges
- modify neurons
- alter graph topology

Only edge weights are modified.

## Expected Behaviour

**Metrics expected to remain essentially unchanged:**
- Node Count
- Edge Count
- Density
- Degree Distribution
- Connected Components
- Reciprocity

**Metrics expected to change:**
- Total Synapses
- Mean Synapse Count
- Weight Variance
- Weight Standard Deviation
- Weighted PageRank
- Weighted Network Statistics

## Dataset-Specific Validation (BANC)
The BANC dataset was analyzed before evaluating potential bias from the lower clamp.

**Observed distribution:**
| Property | Value |
|----------|-------|
| Total Edges | 3,037,361 |
| Minimum synapse count | 3 |
| `syn_count = 1` | 0 |
| `syn_count = 2` | 0 |
| `syn_count <= 5` | 60.90% |
| `syn_count <= 10` | 83.77% |

### Lower Clamp Assessment
The implementation enforces:
`new_weight = max(round(...), 1)`

**Potential concern:**
Edges with very small weights could become positively biased because negative perturbations cannot reduce the weight below one.

**Dataset analysis showed:**
- no edge has `syn_count = 1`
- no edge has `syn_count = 2`
- minimum observed weight is `3`

At the maximum tested error rate (20%), `σ = 0.6` for the weakest edge. Reducing a weight of three to zero would require an extremely unlikely (>4σ) Gaussian deviation.

Therefore the lower clamp is effectively a numerical safeguard rather than a significant source of experimental bias for BANC.

## Scientific Interpretation
This model evaluates the robustness of weighted graph analyses to uncertainty in synapse quantification.

It does not evaluate:
- missing synapses
- false synapses
- structural reconstruction errors

Those are addressed separately by Error Model 1 and Error Model 2.

## Limitations
Current assumptions:
- independent Gaussian perturbation
- proportional variance
- no spatial correlation
- no neuron-type-specific bias
- no imaging-specific bias
- topology remains fixed

These assumptions simplify biological measurement uncertainty and should be considered when interpreting results.

## Future Considerations
Potential future extensions include:
- log-normal measurement noise
- Poisson counting noise
- neuron-type-dependent uncertainty
- compartment-specific measurement error
- correlated regional measurement noise
- confidence-weighted perturbations

## Revision History
**Version 1**
- Initial proportional Gaussian measurement model.
- Verified weighted PageRank uses syn_count.
- Verified BANC synapse-count distribution.
- Confirmed negligible influence of the lower clamp for BANC.
