# Implementation Prompt: Phase 011 — Biological Assumptions

## 1. Why is this phase needed?
**Scientific Motivation:** 
Reconstruction errors in connectomics are not uniformly distributed random noise. They correlate strongly with local biological features, such as the number of synapses forming a connection and the arborization complexity (node degrees) of the participating neurons. 
**Research Motivation:** 
To rigorously answer how robust graph analyses are to plausible false-negative errors, the framework must first formally define the biological constraints and assumptions that dictate which synapses are likely to be missed. 
**Biological Motivation:** 
Sparse connections with fewer synapses are naturally more vulnerable to being completely severed if a single synapse is missed during EM reconstruction.
**Why this phase exists & cannot be merged:** 
This phase exists to isolate the pure biological theory from the mathematical perturbation logic. It cannot be merged with the vulnerability model (Phase 013) because the framework demands a configuration-driven architecture where biological assumptions are loaded as immutable, declarative metadata rather than hardcoded mathematical steps.
**Contribution to Research Objective:** 
It establishes the configuration foundations required to generate biologically plausible perturbations, rather than falling back to naive random edge deletion.

## 2. What are the inputs?
- **Required Inputs:** Biological weight configurations (e.g., source degree weight, target degree weight, synapse count weight) supplied via the framework configuration YAMLs.
- **Source of Input:** User-defined `ExperimentConfig` YAML files parsed by `ConfigManager`.
- **Previous Dependency:** Phase 010 (Framework Orchestration / Configuration System).
- **Expected Schema:** A YAML dictionary mapping biological feature names to their respective impact weights (float values).
- **Expected Types:** `float` for weights.
- **Validation Requirements:** Weights must be numeric.

*Important Note: Phase 011 does not require graph processing.*

## 3. What algorithm is applied?
**Methodology:**
1. Define scientific assumptions H1–H5 in code as structural constraints or documentation constraints.
2. Validate that the provided biological assumptions (weights and configurations) are internally consistent (e.g., within expected ranges, no missing mandatory keys).
3. Store the biological assumptions as immutable experiment metadata using a dataclass (e.g., `FrozenConfig` or a specific `BiologicalAssumptions` dataclass).
4. Register these assumptions so they are accessible to downstream phases without allowing modification.
5. Expose the biological assumptions through the existing `ConfigManager` configuration layers.
6. Enforce immutability to prevent later phases from modifying the assumptions during runtime.

**Strict Constraints:**
- No graph processing occurs.
- No biological feature extraction occurs.
- No vulnerability computation occurs.
- No probability calibration occurs.
- No perturbation occurs.
- No graph analysis occurs.
- No statistical analysis occurs.

## 4. What are the outputs?
- Immutable biological assumptions dataclass.
- Validated metadata representing the biological configuration.
- Experiment configuration object containing the parsed biological schema.
- Validation reports indicating whether the biological assumptions were successfully loaded and verified.

## Scientific Assumptions
The following assumptions must be preserved and reflected in the architectural constraints established in this phase:

**H1:** False-negative errors occur at the synapse level. Edges are never directly removed.
**H2:** Weak connections become vulnerable naturally through synapse loss. Never manually delete weak edges.
**H3:** Sparse neurons are more susceptible. This is only a biological hypothesis; do not compute vulnerability in this phase.
**H4:** Reconstruction errors are stochastic. Randomness will be used later; do not perform random sampling in this phase.
**H5:** The simulator must never create neurons, delete neurons, merge neurons, split neurons, or invent edges. Only synapse counts may decrease in later phases.

## File-Level Implementation Specification

**`configs/schemas/biological_schema.yaml`**
- **Status:** This component does not currently exist in the repository. Create a new implementation in the most appropriate location consistent with the existing architecture.
- **Purpose:** Validate biological assumptions configuration.
- **Reason it exists:** The `ConfigManager` dynamically loads schemas from `configs/schemas/`.
- **Configuration objects:** YAML schema defining required biological keys.

**`modules/error_models/biology.py`** (or equivalent new module)
- **Status:** This component does not currently exist in the repository. Create a new implementation in the most appropriate location consistent with the existing architecture.
- **Purpose:** Represent the biological assumptions in code.
- **Reason it exists:** To store immutable biological assumptions separate from perturbation logic.
- **Classes/Dataclasses:** `BiologicalAssumptions` (immutable dataclass).
- **Methods:** `__init__`, `validate()`.
- **Validation objects:** Internal logic to verify weights.
- **Logging:** Log successful loading of assumptions.

**`tests/test_biology.py`**
- **Status:** This component does not currently exist in the repository. Create a new implementation in the most appropriate location consistent with the existing architecture.
- **Purpose:** Test validation of biological assumptions.
- **Tests:** `test_valid_assumptions`, `test_invalid_assumptions`.

## Algorithm-to-Code Mapping

| Scientific Requirement | Verified File | Verified Class | Verified Function | Output |
| --- | --- | --- | --- | --- |
| Define H1-H5 constraints | `biology.py` (New implementation required) | `BiologicalAssumptions` | N/A | Documented constraints |
| Validate assumptions are internally consistent | `biology.py` (New implementation required) | `BiologicalAssumptions` | `validate()` | Validation success/failure |
| Store assumptions as immutable metadata | `biology.py` (New implementation required) | `BiologicalAssumptions` | `__init__()` | Immutable dataclass |
| Register & expose through framework config | `biological_schema.yaml` (New implementation required) | N/A | N/A | YAML schema |

## What Must Be Implemented
* biological assumptions dataclasses
* assumption validation logic
* immutable biological metadata structures
* assumption registration / schema definitions
* experiment metadata integration (updating configuration)
* configuration validation logic for biology

## What Must NOT Be Implemented
* graph loading
* feature extraction
* degree computation
* PageRank
* vulnerability model
* probability calibration
* random sampling
* synapse removal
* edge removal
* graph perturbation
* graph analysis
* statistical evaluation

## Integration Requirements
- **Previous Dependencies:** Framework Configuration (`ConfigManager`), `FrozenConfig`.
- **Next Dependency:** Phase 012 (Biological Feature Extraction).
- **Experiment Runner Integration:** The `ExperimentRunner` must be able to load these biological assumptions via the config.
- **Configuration Integration:** Integrates into `configs/schemas/` to be automatically loaded by `ConfigManager._load_schemas()`.
- **Validation Integration:** Integrates with the existing lightweight schema validation in `ConfigManager`.
- **Logging Integration:** Standard Python `logging` to capture configuration load success/failure.

## Logging Requirements
Only log the following:
- biological assumptions loaded
- validation success
- validation failure
- configuration summary

## Validation Requirements
Validate only:
- assumptions exist in the configuration
- assumptions are internally consistent (e.g., correct data types, within range)
- assumptions become immutable upon instantiation
- configuration is valid against the newly created schema
*(Do not validate graph properties. No graph exists yet.)*

## Deliverables
The coding AI must produce or initialize structures capable of holding:
* Experiment configuration
* Dataset metadata
* Random seed
* Target error rate
* Achieved error rate
* Number of synapses removed
* Number of edges removed
* Structural graph metrics
* Network statistics
* Downstream biological analysis results
* Runtime statistics
* Validation report
* Checkpoint files
* Log files
*(Note: As this is Phase 011, many of these downstream deliverables will remain empty/unpopulated until later phases, but the AI must produce the Experiment configuration schema and validation report for the biological assumptions).*
