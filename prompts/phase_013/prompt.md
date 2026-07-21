# Implementation Prompt: Phase 013 — Vulnerability Model

## 1. Why is this phase needed?
**Scientific Motivation:** 
Every biological connection has an inherent susceptibility to being missed during EM reconstruction, dependent on its structural complexity and synapse strength. We must estimate this susceptibility precisely for every connection before we introduce stochastic perturbation.
**Biological Motivation:** 
Sparse connections (low synapse count, complex arborization) are naturally more vulnerable to false-negative reconstruction errors. This phase mathematically estimates that biological vulnerability.
**Why vulnerability estimation must occur before probability calibration:** 
Biological vulnerability is a relative score. It does not natively equal a removal probability. By computing vulnerability independently, we map the biological landscape without forcing it to conform to an arbitrary target error rate (which happens later in probability calibration).
**Why it must remain independent from the perturbation engine:** 
The mathematical model for vulnerability is an actively researched hypothesis (e.g., linear vs. exponential). Keeping it independent from the stochastic simulator ensures we can swap out the vulnerability formula in future experiments without modifying or validating the core simulation engine again.
**Why this phase cannot be merged with Phase 014 (Calibration):** 
Merging them conflates biology (vulnerability) with experimental methodology (target error rate). Keeping them separate improves scientific reproducibility and interpretability.

## 2. What are the inputs?
- **Immutable Feature Table:** Produced by Phase 012 (`BiologicalFeatureExtractor`), containing exact biological features for every edge.
- **Biological Assumptions:** The validated `BiologicalAssumptions` dataclass produced by Phase 011 containing the required feature weights.
- **Experiment Configuration:** The global `ExperimentConfig` ensuring deterministic behavior.

*Note: All inputs originate directly from verified interfaces implemented in Phase 011 and Phase 012.*

## 3. What algorithm is applied?
**Methodology:**
For every edge represented in the immutable feature table:
1. Read the immutable biological feature vector (e.g., `syn_count`, `source_degree`, `target_degree`).
2. Read the corresponding biological weights from Phase 011 metadata.
3. Normalize the required biological features if explicitly defined by the configuration. (If the research methodology does not specify a concrete normalization detail, implement the minimum infrastructure necessary without introducing new scientific assumptions, such as defaulting to unnormalized or linear min-max if configured).
4. Apply a weighted linear combination: multiply each feature by its configured biological weight.
5. Sum the weighted values to produce exactly one raw vulnerability score per edge.
6. Store the vulnerability score in a new parallel array or DataFrame column.
7. Preserve the original feature table completely unchanged.

**Strict Constraints:**
- Only vulnerability scores are produced.
- Graph topology remains exactly unchanged.
- Biological feature values remain completely immutable.
- Probabilities are not computed (values are raw scores, not bounded probabilities).
- No graph perturbation occurs.

**Mathematical Documentation Required:**
The implementation must document the feature normalization method, the weighted linear combination formula, score ranges, deterministic behaviour, numerical stability protections (e.g., handling zero-degree nodes), and the handling of any missing or invalid inputs within docstrings.

## 4. What are the outputs?
- Vulnerability score table (e.g., array or Polars Series) mapped precisely to the original edge indices.
- Score metadata (mean, variance, min, max).
- Checkpoint contents (serialized vulnerability scores if supported).
- Validation report ensuring scores are valid numbers.
- Runtime metadata (execution time).
- **Consumer phase:** The resulting score table is passed directly to Phase 014 (Probability Calibration).

## Scientific Justification
**Independence from probability calibration:** Biological vulnerability represents *susceptibility*, not the definitive probability of removal. A highly vulnerable edge in a high-fidelity dataset might have a lower removal probability than a robust edge in a poor-quality dataset.
**Susceptibility vs. Probability:** This distinction prevents the mathematical model from artificially altering the biological hypothesis just to meet a target experimental error rate.
**Scientific Interpretability:** Storing raw vulnerability scores allows researchers to analyze the relative distribution of risk across the connectome independently of the simulation outputs.

## File-Level Implementation Specification

**`modules/error_models/vulnerability.py`**
- **Status:** This component does not currently exist in the repository. Create a new implementation in the most appropriate location while remaining fully consistent with the existing project architecture.
- **Purpose:** Execute the weighted linear vulnerability model.
- **Responsibility:** Consume the Phase 012 feature table and Phase 011 biological weights, outputting a raw score table.
- **Classes:** `VulnerabilityModel`.
- **Methods:** `compute_scores(features, assumptions)`.

**`tests/test_vulnerability.py`**
- **Status:** This component does not currently exist in the repository. Create a new implementation.
- **Purpose:** Test the vulnerability mathematical model.
- **Responsibility:** Validate that identical features and weights always produce deterministic, correct scores, and that the original feature table is never modified.

## Algorithm-to-Code Mapping

| Scientific Step | Verified File | Verified Class | Verified Function | Output |
| --- | --- | --- | --- | --- |
| Read feature vector | `vulnerability.py` (New) | `VulnerabilityModel` | `compute_scores()` | In-memory vectors |
| Normalize features | `vulnerability.py` (New) | `VulnerabilityModel` | `_normalize()` | Normalized arrays |
| Apply weighted model | `vulnerability.py` (New) | `VulnerabilityModel` | `_apply_weights()` | Raw scores |
| Store vulnerability | `vulnerability.py` (New) | `VulnerabilityModel` | `compute_scores()` | Score table |

## What Must Be Implemented
* biological feature normalization logic (if specified by verified configuration)
* weighted linear vulnerability model
* vulnerability score computation engine
* score validation
* score serialization/checkpointing (if supported by runner)
* logging
* validation

## What Must NOT Be Implemented
* probability calibration
* random sampling
* synapse removal
* edge deletion
* graph perturbation
* graph analysis
* statistical evaluation

## Integration Requirements
- **Dependency on Phase 011:** Consumes the biological assumptions/weights metadata exactly as exported by Phase 011.
- **Dependency on Phase 012:** Consumes the immutable feature table exactly as exported by Phase 012.
- **Experiment Runner:** The `ExperimentRunner` must bridge the output of Phase 012 to this Phase 013 model.
- **Configuration Integration:** Respects global deterministic settings (e.g. dataset limits, precision).
- **Exported Interface:** The raw vulnerability score table must be returned cleanly to be consumed by Phase 014.

## Configuration Requirements
- Specify only verified configuration parameters mapped from Phase 011 (e.g., `synapse_weight`, `degree_weight`).
- Do not invent weights, constants, or configuration keys. If the methodology lacks a specific parameter, implement only the infrastructure needed to support future configuration without changing the scientific model.

## Logging Requirements
Require logging of:
- vulnerability model initialization
- feature table loaded (dimensions)
- vulnerability computation started
- vulnerability computation completed
- validation completed
- checkpoint saved (if applicable)
- execution time
*(Do not log perturbation results or node drops).*

## Validation Requirements
Require validation of:
- required biological features exist in the input table
- no missing feature values (NaNs) are present
- normalization completed successfully without division-by-zero errors
- exactly one vulnerability score generated for every edge
- score count equals feature count exactly
- original feature table remains completely unchanged (check memory address or hash if necessary)
- vulnerability scores are finite and computationally valid (no NaNs or Infs)

## Deliverables
The implementation must produce:
* vulnerability score table
* vulnerability metadata
* checkpoint (if enabled)
* validation report
* execution log
* runtime statistics
* documentation describing the implemented vulnerability model and math constraints
