# Method — Scientific Approach

This folder documents the **scientific method** used to design, implement, and
evaluate the connectome error models in this framework. It is the
submission-facing companion to the internal notes in `docs/error model/`.

## Documents

| Document | Purpose |
|----------|---------|
| [`scientific_methodology.md`](scientific_methodology.md) | The framework-level scientific approach: research question, design principles, statistical evaluation, experimental protocol — with Mermaid diagrams. |
| [`em1_missed_synapses.md`](em1_missed_synapses.md) | EM1 — missed-synapse (false-negative) detection: vulnerability scoring, probability calibration, binomial simulation. |
| [`em2_false_synapses.md`](em2_false_synapses.md) | EM2 — false-positive synapse detection: candidate generation, Jaccard ranking, weighted sampling, empirical weight assignment. |
| [`em3_synapse_count.md`](em3_synapse_count.md) | EM3 — synapse-count measurement noise: proportional Gaussian weight perturbation, topology preserved. |
| [`em4_split_errors.md`](em4_split_errors.md) | EM4 — segmentation over-fragmentation: ego-graph splitting, community partition, greedy balanced fragments. |
| [`em5_merge_errors.md`](em5_merge_errors.md) | EM5 — segmentation under-fusion: anatomical constraints, Jaccard candidate ranking, Szudzik IDs, edge collapse. |

Every per-model document derives its mathematics directly from the
implementation — formulas, thresholds, and validation checks are quoted from
the code, not invented.

## Relation to other documentation

| Location | Content |
|----------|---------|
| `docs/method/` (this folder) | Scientific design approach, presentation-ready, diagram-driven |
| `docs/error model/` | Per-model method plans and implementation roadmaps (internal detail) |
| `docs/architecture/` | System architecture of the framework |
| `docs/dataset_analysis/` | Dataset inventory, schemas, and risk analysis |
