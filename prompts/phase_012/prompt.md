# Implementation Prompt: Phase 012 — Biological Feature Extraction

## 1. Why is this phase needed?
**Scientific Motivation:** 
To accurately simulate missed synapses, we must first understand the structural and biological context of every connection in the connectome. Each edge (connection) exists within a broader network topology.
**Biological Motivation:** 
A connection's vulnerability to being missed during EM reconstruction depends on both its intrinsic strength (synapse count) and the complexity of the participating neurons (source and target degrees, PageRank). By extracting these features, we build a complete profile of every connection.
**Why biological characterization must occur before perturbation:** 
The baseline biological reality must be captured immutably. If feature extraction were mixed with perturbation, we would risk contaminating our vulnerability metrics with perturbed data.
**Why features must remain immutable & why later phases depend on them:** 
The features represent the ground truth of the biological network. Future phases (e.g., Phase 013 Vulnerability Model) mathematically transform these features into error probabilities. If the baseline features change, the downstream models lose their deterministic anchors.
**Why this phase cannot be merged with Phase 013:** 
Separating feature extraction from vulnerability modelling ensures that we can swap out the vulnerability algorithm in the future without having to rewrite the costly graph traversal and feature combination logic.

## 2. What are the inputs?
- **Original Connectome & Graph Representation:** The `PreparedGraph` object containing the immutable `igraph.Graph` topology and the pre-computed node-level `baseline_features` (e.g., PageRank, degree).
- **Metadata from Phase 011:** Validated biological assumptions and schema configuration from the Phase 011 config layers.
- **Experiment Configuration:** The global `ExperimentConfig` ensuring deterministic execution.

*Note: All inputs originate from the framework's existing preprocessing pipeline (Phase 006) and configuration manager (Phase 011).*

## 3. What algorithm is applied?
**Methodology:**
For every edge in the `PreparedGraph`:
1. **Read presynaptic neuron:** Extract the `source` vertex ID.
2. **Read postsynaptic neuron:** Extract the `target` vertex ID.
3. **Read synapse count:** Extract the edge's `weight` (which represents biological synapse count).
4. **Compute source degree:** Retrieve the out-degree (or total degree) of the source vertex from `PreparedGraph.baseline_features`.
5. **Compute target degree:** Retrieve the in-degree (or total degree) of the target vertex from `PreparedGraph.baseline_features`.
6. **Determine reciprocal connectivity:** Check if a reverse edge exists from the target back to the source.
7. **Compute source PageRank:** Retrieve the PageRank of the source vertex from `PreparedGraph.baseline_features`.
8. **Compute target PageRank:** Retrieve the PageRank of the target vertex from `PreparedGraph.baseline_features`.
9. **Construct a biological feature vector:** Assemble these specific values into a row.
10. **Store the feature vector:** Append it to a centralized feature table (e.g., a Polars DataFrame or parallel arrays).
11. **Preserve the original graph unchanged:** Ensure no properties are mutated.

**Strict Constraints:**
- Feature extraction occurs exactly once.
- Features become immutable.
- Features are reused by every later phase.
- No normalization occurs.
- No vulnerability computation occurs.
- No probability computation occurs.
- No graph modification occurs.
- No simulation occurs.
- No statistics are computed.

**Required Feature Schema:**
The implementation must produce a feature table containing exactly:
| Feature | Description |
| --- | --- |
| `pre_root` | Presynaptic neuron |
| `post_root` | Postsynaptic neuron |
| `syn_count` | Biological synapse count |
| `source_degree` | Outgoing connectivity |
| `target_degree` | Incoming connectivity |
| `reciprocal` | Bidirectional connection |
| `source_pagerank` | Source importance |
| `target_pagerank` | Target importance |

*(Do not add extra biological features unless they already exist in the repository. Do not remove required features.)*

## 4. What are the outputs?
- Immutable feature table (e.g., Polars DataFrame or struct array) mapping edge indices to their biological features.
- Validated feature metadata (e.g., column schemas, data types).
- Checkpoint contents (the serialized feature table, if checkpointing is enabled for this run).
- Runtime metadata (extraction time, memory footprint).
- **Consumer phase:** The resulting feature table is passed directly to Phase 013 (Vulnerability Model).

## Scientific Justification
**Why characterization must precede perturbation:** Perturbation permanently destroys biological information. We must map the intact state to calculate accurate error likelihoods.
**Independent of the vulnerability model:** Different scientific hypotheses will require different mathematical combinations of these features (linear vs. non-linear models). By extracting the features into a raw, un-transformed table, we remain agnostic to the vulnerability formula.
**Unchanged throughout experiment:** The ground truth biological state does not fluctuate across Monte Carlo trials. Recomputing it per trial would be biologically invalid and computationally wasteful.
**Reproducibility:** A distinct feature table allows other researchers to verify our feature metrics independently of our chosen error model.

## File-Level Implementation Specification

**`modules/error_models/biological_features.py`**
- **Status:** This component does not currently exist in the repository. Create a new implementation in the most appropriate location while remaining consistent with the existing architecture.
- **Purpose:** Extracts and structures the raw biological features for every edge.
- **Responsibility:** Traverse the `PreparedGraph`, combine edge attributes with node-level `baseline_features`, and build the immutable feature table.
- **Classes:** `BiologicalFeatureExtractor`.
- **Methods:** `extract_features(prepared_graph: PreparedGraph) -> DataFrame/Dict`.

**`tests/test_biological_features.py`**
- **Status:** This component does not currently exist in the repository. Create a new implementation.
- **Purpose:** Test edge-level biological feature extraction.
- **Responsibility:** Ensure the table size exactly matches the edge count and validates all required schema columns.

## Algorithm-to-Code Mapping

| Scientific Step | Verified File | Verified Class | Verified Function | Output |
| --- | --- | --- | --- | --- |
| Read pre/post neuron | `biological_features.py` (New) | `BiologicalFeatureExtractor` | `extract_features()` | `pre_root`, `post_root` |
| Read synapse count | `biological_features.py` (New) | `BiologicalFeatureExtractor` | `extract_features()` | `syn_count` |
| Map source/target degrees | `biological_features.py` (New) | `BiologicalFeatureExtractor` | `extract_features()` | `source_degree`, `target_degree` |
| Map reciprocal/PageRank | `biological_features.py` (New) | `BiologicalFeatureExtractor` | `extract_features()` | `reciprocal`, `source_pagerank`, `target_pagerank` |
| Construct feature table | `biological_features.py` (New) | `BiologicalFeatureExtractor` | `extract_features()` | Immutable feature table |

## What Must Be Implemented
* biological feature extraction
* feature validation against the required schema
* feature table generation
* feature metadata
* feature checkpoint logic (if supported by runner)
* feature serialization
* logging
* validation

## What Must NOT Be Implemented
* vulnerability scoring
* feature normalization
* weighted linear model
* probability calibration
* random sampling
* synapse removal
* edge deletion
* graph perturbation
* graph analysis
* statistical evaluation

## Integration Requirements
- **Dependency on Phase 011:** Utilizes configuration loaded during Phase 011 (though relies heavily on `PreparedGraph` from Phase 006).
- **Experiment Runner:** The `ExperimentRunner` must invoke `BiologicalFeatureExtractor` prior to invoking the `ErrorRegistry` models.
- **Configuration Integration:** Feature extraction must respect global deterministic settings (e.g. dataset selection).
- **Output Interface:** The immutable feature table must be exposed in a format easily consumed by Phase 013 (e.g., passed as an argument to the vulnerability model).
- **Logging Integration:** Must use standard python `logging`.

## Configuration Requirements
- **Dataset selection:** Graph source is derived from `ExperimentConfig`.
- **Validation rules:** Config schemas should not be modified, but runtime validation must assert the presence of all required columns.

## Logging Requirements
The implementation must log:
- graph loaded
- number of nodes
- number of edges
- feature extraction started
- feature extraction completed
- execution time
- feature validation success
- checkpoint saved (if applicable)
*(Do not log perturbation information).*

## Validation Requirements
Require validation of:
- graph successfully loaded
- required edge attributes exist (`weight` representing synapses)
- required node identifiers exist
- every edge has a complete feature vector
- feature table size equals exactly the edge count
- no missing values (NaNs) in the table
- original graph remains unchanged
- feature schema matches specification exactly

## Deliverables
The implementation must produce:
* immutable feature table
* feature metadata
* checkpoint
* validation report
* execution log
* runtime statistics
* feature schema documentation
