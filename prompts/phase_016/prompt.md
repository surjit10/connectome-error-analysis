# Implementation Prompt: Phase 016 — Graph Analysis

## 1. Why is this phase needed?
**Scientific Motivation:**
After the perturbed subgraph is constructed by the ExperimentRunner, we must analyze its topological properties to measure the degradation caused by the missed synapses.

**How it answers the research question:**
This phase is an unskippable link in the scientific workflow. It cannot be merged with other phases because maintaining strict architectural isolation ensures that different biological assumptions or models can be swapped without invalidating the entire simulation pipeline.

## 2. What are the inputs?
- **Required Inputs:** The temporary perturbed `PreparedGraph`.
- **Data Structure:** Immutably passed objects or configuration dicts.
- **Validation Rules:** Must adhere to strict type checking and bounding.

## 3. What algorithm is applied?
**Detailed Computational Steps:**
The research methodology does not define this implementation detail. Implement only the minimum infrastructure required without introducing new scientific assumptions. Implement standard metric computations via `BaseAnalysis` plugins.

**Scientific Assumptions:** Deterministic behaviour is guaranteed if the same random seed is provided.

## 4. What are the outputs?
- **Returned Objects:** `AnalysisResult` objects containing numeric metrics.
- **Consumer Phase:** Passed seamlessly to the next phase by the ExperimentRunner.

## 5. Scientific Justification
**Validity:** This step accurately isolates a specific mathematical operation required to translate raw connectome data into biologically plausible error simulation.
**Assumptions:** Relies on the assumption that the provided inputs represent true biological states.
**Extensibility:** By encapsulating this logic, future experiments can replace this algorithm without modifying unrelated phases.

## 6. File-Level Implementation Specification
**Exact File Locations:**
- `modules/graph_analyses/structural.py` - Purpose: Basic structural analysis plugin.

## 7. Algorithm-to-Code Mapping
| Compute metrics | `structural.py` | `StructuralAnalysis` | `_run()` | `AnalysisResult` |

## 8. What This Phase Must Implement
**Must implement:**
* graph metric computation
* return `AnalysisResult`

## 9. What This Phase Must NOT Implement
**Must NOT implement:**
* graph perturbation
* edge deletion
* statistical aggregation across trials

## 10. Integration Requirements
- **Integration Workflow:** Previous: Phase 015. Next: Phase 017. Registered in `analysis_registry`.
- **Shared Utilities:** Use core framework logging and validation tools.

## 11. Configuration Requirements
- **Configurations:** Any analysis-specific configs from `ExperimentConfig`.
- **Validation Rules:** Must not accept invalid ranges.

## 12. Logging Requirements
- **Logging:** Log analysis execution time and completion status.
- **Level:** Ensure warnings and errors are appropriately captured via the standard python `logging` module.

## 13. Validation Requirements
- **Validation Checks:** Ensure metrics contain only numeric scalar values.
- **Quality-Control Rules:** 
  - Node count unchanged.
  - No new nodes created.
  - No new edges introduced.
  - Edge weights remain non-negative integers.

## 14. Deliverables
**The coding AI must produce:**
* Analysis plugin implementations
* `AnalysisResult` objects
- Full validation report
- Log files output
