# Implementation Prompt: Phase 015 — Missed Synapse Simulation

## 1. Why is this phase needed?
**Scientific Motivation:**
This phase executes the actual perturbation by sampling from the calibrated probabilities to generate the binary edge mask.

**How it answers the research question:**
This phase is an unskippable link in the scientific workflow. It cannot be merged with other phases because maintaining strict architectural isolation ensures that different biological assumptions or models can be swapped without invalidating the entire simulation pipeline.

## 2. What are the inputs?
- **Required Inputs:** Calibrated probabilities (Phase 014), `PreparedGraph`, and Random Seed.
- **Data Structure:** Immutably passed objects or configuration dicts.
- **Validation Rules:** Must adhere to strict type checking and bounding.

## 3. What algorithm is applied?
**Detailed Computational Steps:**
1. Initialize a random number generator with the provided seed.
2. For every edge, generate a random float between 0 and 1.
3. If random_float < edge_probability, mark edge as missing (False in mask).
4. Otherwise, mark edge as preserved (True in mask).
5. Return an `ErrorResult` containing the `edge_mask`.
Do not modify the baseline graph.

**Scientific Assumptions:** Deterministic behaviour is guaranteed if the same random seed is provided.

## 4. What are the outputs?
- **Returned Objects:** `ErrorResult` object containing the `edge_mask`.
- **Consumer Phase:** Passed seamlessly to the next phase by the ExperimentRunner.

## 5. Scientific Justification
**Validity:** This step accurately isolates a specific mathematical operation required to translate raw connectome data into biologically plausible error simulation.
**Assumptions:** Relies on the assumption that the provided inputs represent true biological states.
**Extensibility:** By encapsulating this logic, future experiments can replace this algorithm without modifying unrelated phases.

## 6. File-Level Implementation Specification
**Exact File Locations:**
- `modules/error_models/missed_synapses.py` - Purpose: Execute the stochastic simulation.

## 7. Algorithm-to-Code Mapping
| Simulate synapse loss | `missed_synapses.py` | `MissedSynapses` | `_perturb()` | `ErrorResult` |

## 8. What This Phase Must Implement
**Must implement:**
* random sampling using the calibrated probabilities
* generation of the boolean `edge_mask`
* returning `ErrorResult`

## 9. What This Phase Must NOT Implement
**Must NOT implement:**
* physical graph modification
* graph analysis
* statistical evaluation

## 10. Integration Requirements
- **Integration Workflow:** Previous: Phase 014. Next: Phase 016. Registered in `error_registry`.
- **Shared Utilities:** Use core framework logging and validation tools.

## 11. Configuration Requirements
- **Configurations:** Uses `seed` for deterministic sampling.
- **Validation Rules:** Must not accept invalid ranges.

## 12. Logging Requirements
- **Logging:** Log the actual number of edges removed vs the target number.
- **Level:** Ensure warnings and errors are appropriately captured via the standard python `logging` module.

## 13. Validation Requirements
- **Validation Checks:** Validate that `edge_mask` length matches baseline edge count. Validate achieved error rate is within tolerance.
- **Quality-Control Rules:** 
  - Node count unchanged.
  - No new nodes created.
  - No new edges introduced.
  - Edge weights remain non-negative integers.

## 14. Deliverables
**The coding AI must produce:**
* `ErrorResult` object
* Perturbation metadata (achieved removal count)
- Full validation report
- Log files output
