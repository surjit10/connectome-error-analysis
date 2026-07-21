# Implementation Prompt: Phase 014 — Probability Calibration

## 1. Why is this phase needed?
**Scientific Motivation:** 
The biological vulnerability scores computed in Phase 013 represent the relative *susceptibility* of each connection to being missed. However, a vulnerability score of `50.0` does not mean a 50% chance of removal. To perform a controlled scientific experiment, we must simulate exactly a specific *Target Error Rate* (e.g., 5% total synapse loss). This phase mathematically translates abstract biological susceptibility into strict deletion probabilities.
**Biological Motivation:** 
It scales the severity of the biological assumptions to match the empirical conditions of the specific EM reconstruction being simulated.
**Why probability calibration must occur after vulnerability estimation:** 
It enforces separation of concerns. The vulnerability model describes the biology. The calibration model describes the experimental methodology (the target severity of the simulation).
**Why this phase cannot be merged with Phase 015 (Simulation):** 
Separating calibration from the stochastic simulator guarantees that the probabilities are deterministically calculated and can be validated *before* any random sampling occurs. This allows us to prove mathematically that the expected value of edge loss exactly matches the target error rate.

## 2. What are the inputs?
- **Vulnerability Score Table:** The raw score array produced by Phase 013 (`VulnerabilityModel`).
- **Target Error Rate:** A float (e.g., 0.05) loaded from the `ExperimentConfig`.
- **Total Edge Count / Total Synapse Count:** Derived from the `PreparedGraph` metadata to determine exactly how many edges/synapses represent the target error rate.

*Note: All inputs originate directly from verified interfaces implemented in prior phases.*

## 3. What algorithm is applied?
**Methodology:**
1. Determine the target number of units (edges or synapses) to remove: `target_drops = total_units * target_error_rate`.
2. Compute the sum of all raw vulnerability scores across the connectome: `sum_vulnerability`.
3. Calculate the global scaling factor: `alpha = target_drops / sum_vulnerability`.
4. For every edge, multiply its vulnerability score by `alpha` to compute the initial probability: `p = score * alpha`.
5. Cap all probabilities at `1.0` (since an edge cannot be deleted more than 100% of the time).
6. If any probabilities were capped, calculate the "lost" probability mass and iteratively redistribute it among the uncapped edges until the sum of all probabilities exactly equals `target_drops`.
7. Store the final bounded probabilities (0.0 <= p <= 1.0).

**Strict Constraints:**
- Only probabilities are produced.
- No biological features or vulnerability scores are modified.
- No graph topology is modified.
- No random sampling or actual edge deletion occurs (this is strictly a deterministic mathematical transformation).

**Mathematical Documentation Required:**
The implementation must document the iterative capping and redistribution algorithm, the convergence criteria (e.g., maximum iterations or precision tolerance), deterministic behaviour, and handling of edge cases (e.g., when the target error rate is 0.0 or mathematically impossible to satisfy).

## 4. What are the outputs?
- Calibrated probability table (array or Polars Series) mapped precisely to the original edge indices.
- Calibration metadata (scaling factor used, number of iterations to converge).
- Checkpoint contents (serialized probabilities if supported).
- Validation report ensuring the expected value of probabilities matches the target error rate.
- Runtime metadata (execution time).
- **Consumer phase:** The resulting probability array is passed directly to Phase 015 (Missed Synapse Simulation).

## Scientific Justification
**Why biological vulnerability estimation must remain independent from probability calibration:** 
Different experiments might apply the exact same biological vulnerability model but test different target error rates (e.g., comparing 1% vs 5% vs 10% errors). Calibration handles this scaling without requiring the vulnerability formula to be recomputed or redesigned.
**Why separating these concepts improves scientific interpretability:** 
It proves that the relative biological ranking of edges remains identical across error rates, isolating the impact of severity from the impact of biological susceptibility.

## File-Level Implementation Specification

**`modules/error_models/calibration.py`**
- **Status:** This component does not currently exist in the repository. Create a new implementation in the most appropriate location while remaining fully consistent with the existing project architecture.
- **Purpose:** Scale raw scores into bounded probabilities.
- **Responsibility:** Consume the Phase 013 vulnerability scores and the target error rate, outputting exactly scaled deletion probabilities.
- **Classes:** `ProbabilityCalibrator`.
- **Methods:** `calibrate(scores, target_error_rate, total_units)`.

**`tests/test_calibration.py`**
- **Status:** This component does not currently exist in the repository. Create a new implementation.
- **Purpose:** Test the probability calibration mathematics.
- **Responsibility:** Validate that the sum of output probabilities matches the target drop count exactly, that no probability exceeds 1.0, and that the redistribution algorithm converges correctly.

## Algorithm-to-Code Mapping

| Scientific Step | Verified File | Verified Class | Verified Function | Output |
| --- | --- | --- | --- | --- |
| Calculate target drops | `calibration.py` (New) | `ProbabilityCalibrator` | `calibrate()` | Target scalar |
| Calculate initial alpha | `calibration.py` (New) | `ProbabilityCalibrator` | `calibrate()` | Scaling scalar |
| Scale and cap probabilities | `calibration.py` (New) | `ProbabilityCalibrator` | `_scale_and_cap()` | Probability array |
| Redistribute excess mass | `calibration.py` (New) | `ProbabilityCalibrator` | `_redistribute()` | Final probabilities |

## What Must Be Implemented
* mathematical scaling and capping algorithms
* probability mass redistribution logic
* convergence checking for redistribution
* probability table serialization/checkpointing (if supported by runner)
* logging
* validation

## What Must NOT Be Implemented
* vulnerability modeling
* biological feature extraction
* random sampling
* synapse removal
* edge deletion
* graph perturbation
* graph analysis
* statistical evaluation

## Integration Requirements
- **Dependency on Phase 013:** Consumes the raw vulnerability scores exactly as exported by Phase 013.
- **Experiment Runner:** The `ExperimentRunner` must bridge the output of Phase 013 and the config's error rate into this Phase 014 model.
- **Configuration Integration:** Respects the global target error rate defined in the experiment config.
- **Exported Interface:** The bounded probability table must be returned cleanly to be consumed by Phase 015.

## Configuration Requirements
- Specify only the target error rate (e.g., `error_rate: 0.05`) mapped from the experiment configuration.
- Do not invent weights, constants, or configuration keys. If the methodology lacks a specific parameter, implement only the infrastructure needed to support future configuration without changing the scientific model.

## Logging Requirements
Require logging of:
- calibration initialized
- target error rate and computed target drop count
- scaling factor (`alpha`) computed
- iterations required for mass redistribution convergence
- calibration completed
- execution time
*(Do not log random sampling or actual node drops).*

## Validation Requirements
Require validation of:
- no missing vulnerability values (NaNs) in the input
- all output probabilities are strictly bounded between 0.0 and 1.0 inclusive
- the sum of all output probabilities exactly equals the calculated `target_drops` (within floating point tolerance)
- output probability count exactly matches input score count

## Deliverables
The implementation must produce:
* calibrated probability table
* calibration metadata (iterations, alpha)
* checkpoint (if enabled)
* validation report (confirming expected value math)
* execution log
* runtime statistics
* documentation describing the iterative capping and redistribution algorithm
