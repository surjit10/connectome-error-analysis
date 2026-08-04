I actually recommend not jumping directly into coding. What you need first is a methodology specification document—something that reads like the Methods section of a research paper. Every implementation decision should be traceable to this document. If later someone asks "Why did you do it this way?", the answer should already be written here.

Below is the complete scientific methodology.

# Error Model 4 (EM4): Split Errors (Segmentation Fragmentation)

## 1. Objective

**Goal**

The objective of Error Model 4 (EM4) is to simulate segmentation split errors that occur during automated electron microscopy (EM) reconstruction.

A segmentation split error occurs when a single biological neuron is reconstructed as two independent neurons because the reconstruction algorithm fails to maintain continuity along a neurite.

Unlike biological damage, this error does not remove synapses or alter neuronal physiology. It only changes the reconstructed graph representation.

Therefore, the purpose of EM4 is to approximate the graph-level consequences of reconstruction fragmentation while preserving the original biological connectivity.

### Implementation Note
This document defines the scientific methodology only. Implementation is defined in `docs/error model/em4/em4 integration report.md`. The methodology must remain implementation independent. Future implementation changes must not alter the scientific algorithm.

Do not mention implementation classes anywhere else unless absolutely necessary.

## 2. Biological Motivation

Modern connectome reconstruction follows this pipeline

EM Images

    ↓
Segmentation

    ↓
Agglomeration

    ↓
Neuron Reconstruction

    ↓
Connectivity Graph

Split errors occur during

Segmentation

or

Agglomeration

when two portions of the same neuron fail to merge.

The biological neuron remains unchanged.

Only its digital reconstruction becomes fragmented.

## 3. Scope

The model is designed specifically for

graph-level connectomes

neuron connectivity graphs

It is not intended to simulate

EM image artifacts

segmentation masks

supervoxels

neuron meshes

neuron skeletons

because these data are unavailable in BANC.

## 4. Available Information

Graph

Nodes

Neuron

Edges

Synaptic connection

Weight

syn_count

Direction

pre → post

Metadata

**Available**

degree

partner neurons

neuropil

neurotransmitter

cell class

cell type

**Unavailable**

skeleton

mesh

coordinates

branch geometry

cable length

## 5. Scientific Assumptions

Assumption 1

Split errors occur at the neuron level.

Not

individual synapses.

Assumption 2

Split errors disconnect

one coherent local portion

of a neuron.

They do not

randomly alternate synapses.

Assumption 3

Without morphology,

local graph topology

is the best available approximation

of local neuronal organization.

Assumption 4

Local graph communities

are treated as

graph-theoretic proxies

for coherent portions of neuronal connectivity.

They are not claimed

to be actual dendrites or axons.

Assumption 5

The perturbation changes

only

Neuron identity

It never changes

Synapse count

or

Edge weights

Assumption 6

The perturbation exists only during the lifetime of a simulation trial.

The original PreparedGraph and baseline connectome remain immutable throughout all experiments.

## 6. Overall Pipeline

### Scientific Pipeline

Load Graph

    ↓
Candidate Preparation

    ↓
Eligible Neuron Selection

    ↓
Sample Split Neurons

    ↓
Local Ego Graph Extraction

    ↓
Connected Component Analysis

    ↓
Community Detection (Fallback)

    ↓
Balanced Fragment Assignment

    ↓
Create Fragment Nodes

    ↓
Edge Rewiring

    ↓
Validation

### Software Execution

SplitExperimentRunner

    ↓
_split_build_temp_graph()

    ↓
Existing Graph Analyses

    ↓
Statistics

    ↓
Export

Software execution is implementation specific and is defined by the architecture document.

## 7. Candidate Preparation

Performed once.

For every neuron compute

Degree

Weighted Degree

Unique Partners

**Purpose**

Identify neurons that can produce meaningful fragments.

## 8. Eligibility

Neuron is eligible if

Degree ≥ threshold

Recommended

Degree ≥10

**Reason**

Tiny neurons cannot be meaningfully fragmented.

## 9. Error Rate

**Input**

Error Rate

**Interpretation**

Percentage of eligible neurons

selected for splitting.

**Example**

Eligible neurons

10000

Error rate

5%

    ↓
500 neurons split.

## 10. Candidate Sampling

**Input**

Eligible neuron list

**Method**

Random sampling

without replacement.

Once a neuron is selected

it cannot be selected again.

## 11. Ego Graph Construction

For every selected neuron

construct

Ego Graph

**Definition**

Target neuron

+

Immediate neighbors

+

All edges between neighbors

Only

1-hop neighborhood.

## 12. Graph Representation

For partitioning

convert

ego graph

to

Undirected

**Reason**

Community detection and connected components represent structural organization rather than signal flow.

Original graph

remains directed.

## 13. Remove Central Neuron

Delete

Target neuron

temporarily.

Only neighbors remain.

This reveals

whether the neighborhood naturally separates.

## 14. Connected Components

Compute

Connected Components

**Input**

Neighbor graph

**Output**

Component 1

Component 2

...

Component N

**Observation**

Most neurons already fragment naturally.

## 15. Community Detection

Executed

only

if

Connected Components =1

**Method**

Louvain

**Purpose**

Detect hidden local organization.

Only

local ego graph.

Never

whole connectome.

## 16. Community Assignment

**Input**

Connected Components

or

Communities

**Method**

Greedy Largest First

**Procedure**

Sort communities

largest

    ↓
smallest

Assign next community

to currently smaller fragment.

Produces

balanced

fragment sizes.

## 17. Fragment Creation

Original

Neuron A

becomes

Neuron A1

Neuron A2

Exactly

two fragments.

## 18. Edge Rewiring

Every edge is assigned exactly once.

**Rules**

Incoming edge

X → A

    ↓
X → A1

or

X → A2

Outgoing edge

A → Y

    ↓
A1 → Y

or

A2 → Y

Assignment determined entirely by

partner's community.

No edge duplication.

No edge deletion.

## 19. Validation

Every perturbation must satisfy

**Graph Integrity**

- Edge count preserved
- Synapse count preserved
- No duplicate edges
- No invalid node IDs
- No self-loops introduced

**Fragment Quality**

Minimum

Partners ≥3

Recommended.

Otherwise

Reject

and

sample another neuron.

**Graph Validity**

Every fragment

must contain

at least

one edge.

## 20. Failure Handling

Reject neuron if

Degree <10

Reject if

Smallest fragment

<3 partners

Reject if

Only one community detected

after fallback.

Sample another neuron.

## 21. Randomness

Single experiment seed

    ↓
Trial seed

    ↓
Neuron sampling

    ↓
Community detection

All randomness derived

from one reproducible seed.

## 22. Complexity

**Preprocessing**

Compute

eligible neurons.

Complexity

O(V+E)

Performed once.

**Perturbation**

For one neuron

Ego extraction

    ↓
Connected Components

    ↓
Louvain

    ↓
Greedy assignment

    ↓
Rewire

Complexity

O(d²)

where

d

=

local degree

**Overall**

Linear

in

number of perturbed neurons.

## 23. Memory

**Stores**

Only

local ego graph.

**Memory**

O(d)

No global matrices.

Compatible

with

Kaggle Free.

## 24. Software Architecture Integration

The scientific algorithm is executed through a dedicated execution pipeline, which is responsible for:
- temporary graph construction
- fragment node creation
- temporary lookup management
- graph validation

The exact implementation is defined in `em4 integration report.md`.

(Note: Implementation examples include `SplitExperimentRunner`, `_split_build_temp_graph()`, `Split Errors Model`, etc.)

## 25. Inputs

**Required**

- PreparedGraph
- Metadata
- Configuration
- Error Rate
- Random Seed
- Trial Number

PreparedGraph remains immutable.

## 26. Outputs

### Scientific Outputs

- Perturbed Graph
- Fragment Mapping
- Selected Neurons
- Communities
- Rejected Neurons
- Validation Report
- Graph Analysis Results
- CSV
- Plots
- HTML

### Implementation Outputs

- Temporary Fragment IDs
- Temporary Lookup Mapping
- Perturbation Metadata
- Validation Logs
- Retry Statistics

Implementation outputs exist only to support execution and reproducibility.

## 27. Biological Limitations

The methodology does not reconstruct the EM segmentation process itself.

Instead, it approximates the graph-level consequences of a local segmentation failure.

Community structure is treated as a graph-theoretic proxy for coherent connectivity rather than a direct representation of physical dendritic or axonal branches.

Only binary fragmentation (two fragments) is modeled; multi-fragment reconstruction errors are outside the current scope.

## 28. Scientific Strengths

Uses only information available in BANC.

Preserves synapse counts and edge weights.

Produces coherent rather than random fragments.

Local computation only; no global graph optimization.

Reuses the existing graph analysis, statistics, export, and evaluation framework while introducing an isolated execution pipeline dedicated to topology-changing perturbations.

Scales efficiently to large connectomes and remains practical on Kaggle Free.

Makes explicit, testable assumptions rather than claiming unavailable morphological information.

## 29. Final Method Summary

| Stage | Method | Input | Output | Complexity |
| --- | --- | --- | --- | --- |
| Candidate preparation | Degree filtering | Graph | Eligible neurons | O(V+E) |
| Candidate sampling | Uniform random over eligible neurons | Eligible set | Selected neurons | O(k) |
| Ego extraction | 1-hop ego graph | Selected neuron | Local graph | O(d) |
| Partition discovery | Connected Components | Ego graph | Components | O(d²) |
| Fallback | Louvain (only if one component) | Ego graph | Communities | O(d²) |
| Fragment assignment | Greedy Largest-First | Components/communities | Two balanced groups | O(c log c), where c is the number of groups |
| Fragment creation | Node duplication | Selected neuron | A₁, A₂ | O(1) |
| Edge rewiring | Community-based reassignment | Local edges | Perturbed graph | O(d) |
| Validation | Rule-based checks | Perturbed graph | Accept/Reject | O(d) |
| Downstream analysis | Execute the perturbed graph using the project's existing analysis framework. Implementation details are defined in the architecture document. | Perturbed graph | Metrics, CSV, plots | Existing implementation |

## 30. Separation of Scientific Methodology and Software Architecture

Scientific Methodology defines:
- biological assumptions
- perturbation algorithm
- validation
- scientific interpretation

Software Architecture defines:
- execution pipeline
- runners
- temporary graph construction
- configuration
- export
- framework integration

Future software refactoring must not modify the scientific methodology.
Future scientific improvements should require changes only to the EM4 perturbation model rather than the execution framework.

One recommendation before you implement

I would make one small methodological change.

Earlier reports alternated between degree-proportional sampling and uniform sampling after a minimum degree threshold. I recommend documenting and using uniform random sampling over the eligible neuron set (degree ≥ threshold).

Why?

It avoids repeatedly targeting hubs.

It makes the error rate easier to interpret.

It separates eligibility ("large enough to split") from selection ("random reconstruction failure"), which is statistically cleaner unless you have strong quantitative evidence linking split probability to degree in BANC itself.

Everything else in the methodology is now sufficiently specified that you can move into implementation without making ad hoc design decisions during coding.

