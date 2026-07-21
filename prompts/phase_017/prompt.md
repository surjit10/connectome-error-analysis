# Implementation Prompt: Phase 017 — Statistical Evaluation

## 1. Why is this phase needed?
**Scientific Motivation:**
To answer the research question robustly, we must aggregate the graph metrics across multiple independent trials to compute confidence intervals and statistical significance.

**How it answers the research question:**
This phase is an unskippable link in the scientific workflow. It cannot be merged with other phases because maintaining strict architectural isolation ensures that different biological assumptions or models can be swapped without invalidating the entire simulation pipeline.

## 2. What are the inputs?
- **Required Inputs:** A list of `ExperimentResult` objects containing `AnalysisResults` from all trials.
- **Data Structure:** Immutably passed objects or configuration dicts.
- **Validation Rules:** Must adhere to strict type checking and bounding.

## 3. What algorithm is applied?
**Detailed Computational Steps:**
The research methodology does not define this implementation detail. Implement only the minimum infrastructure required without introducing new scientific assumptions. Configure the notebook or script to consume `ExperimentStatistics` output, grouping by dataset and error rate.

**Scientific Assumptions:** Deterministic behaviour is guaranteed if the same random seed is provided.

## 4. What are the outputs?
- **Returned Objects:** Aggregated statistical tables and export files.
- **Consumer Phase:** Passed seamlessly to the next phase by the ExperimentRunner.

## 5. Scientific Justification
**Validity:** This step accurately isolates a specific mathematical operation required to translate raw connectome data into biologically plausible error simulation.
**Assumptions:** Relies on the assumption that the provided inputs represent true biological states.
**Extensibility:** By encapsulating this logic, future experiments can replace this algorithm without modifying unrelated phases.

## 6. File-Level Implementation Specification
**Exact File Locations:**
- `experiments_missed_synapses.ipynb` - Purpose: Final statistical rendering.

## 7. Algorithm-to-Code Mapping
| Evaluate statistics | `experiments_missed_synapses.ipynb` | N/A | Cell 10 | Pandas DataFrame |

## 8. What This Phase Must Implement
**Must implement:**
* statistical rendering
* confidence interval display

## 9. What This Phase Must NOT Implement
**Must NOT implement:**
* graph perturbation
* raw metric computation
* baseline framework modifications

## 10. Integration Requirements
- **Integration Workflow:** Previous: Phase 016. Wraps up the workflow.
- **Shared Utilities:** Use core framework logging and validation tools.

## 11. Configuration Requirements
- **Configurations:** Notebook configuration.
- **Validation Rules:** Must not accept invalid ranges.

## 12. Logging Requirements
- **Logging:** Print summary tables.
- **Level:** Ensure warnings and errors are appropriately captured via the standard python `logging` module.

## 13. Validation Requirements
- **Validation Checks:** Ensure statistical outputs match expected schemas without NaN confidence intervals.
- **Quality-Control Rules:** 
  - Node count unchanged.
  - No new nodes created.
  - No new edges introduced.
  - Edge weights remain non-negative integers.

## 14. Deliverables
**The coding AI must produce:**
* Statistical summary tables
* Final exported results
- Full validation report
- Log files output
