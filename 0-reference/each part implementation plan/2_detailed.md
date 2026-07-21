Below is a much more implementation-oriented `README_PER_PHASE.md`. Unlike the reference README, this one tells you **exactly what has to be implemented, where it belongs in the repository, what information is still required, what should not be implemented yet, and why** according to your architecture.

---

# README_PER_PHASE.md

# FlyWire Research Framework – Phase-wise Implementation Guide

## Purpose

This document serves as the implementation roadmap for the FlyWire Error Analysis Framework.

For every development phase, it explains:

* what should be implemented
* where it belongs
* why it exists
* what dependencies must already exist
* what information is still required
* what should **NOT** be implemented yet

The objective is to build a reusable research framework first and only then implement biological research modules.

---

# Overall Architecture Philosophy

The repository follows a layered architecture.

```
Configuration Layer
        │
        ▼
Core Framework
        │
        ▼
Reusable Scientific Modules
        │
        ▼
Experiment Runner
        │
        ▼
Results & Export
```

The framework must remain independent of any single experiment.

Future research should primarily involve **adding modules**, not modifying the framework.

---

# Phase Dependency Overview

| Phase               | Prompt  | Status                | Main Dependency      |
| ------------------- | ------- | --------------------- | -------------------- |
| Repository Scaffold | 001     | Ready                 | None                 |
| Configuration       | 002     | Ready                 | Repository           |
| Dataset Registry    | 003     | Ready                 | Configuration        |
| Data Loading        | 004     | Wait for CSV Schema   | Registry             |
| Graph Construction  | 005     | Wait for Graph Design | Loader               |
| Preprocessing       | 006     | Wait for Graph API    | Graph Builder        |
| Analysis Framework  | 007     | Ready after Graph API | Graph Builder        |
| Error Framework     | 008     | Ready after Graph API | Graph Builder        |
| Experiment Runner   | 009     | Partial               | Framework Interfaces |
| Export              | 010     | Partial               | Runner               |
| Research Modules    | 011-025 | Wait                  | Complete Framework   |

---

# PHASE 1 – Framework Foundation

Goal

Build reusable software infrastructure.

No biological logic belongs here.

---

# 001 Repository Scaffold

## Purpose

Create the repository structure.


### Input

Repository Architecture

### Responsibilities

Create the root repository structure
Initialize package directories
Set up placeholder files
Define dependency files

### Output

Repository Structure

### Consumed By

Phase 002

### Consistency Rules

Do not implement logic.
Only establish folder structure.

---

## Implement In

```
.github/
configs/
core/
modules/
docs/
results/
research_data/
tests/
```

---

## Implement

* repository tree
* package structure
* placeholder modules
* README files
* .gitignore
* requirements.txt

---

## Do NOT Implement

* CSV loading
* graph objects
* preprocessing
* biology
* experiments

---

## Future Dependencies

Everything depends on this phase.

---

## Required Information

Only repository architecture.

---

# 002 Configuration System

## Purpose

Implement reusable configuration management.


### Input

Configuration Files

### Responsibilities

Load YAML configurations
Merge default and specific configurations
Validate configurations against schemas

### Output

Configuration Objects

### Consumed By

Phase 003, 009

### Consistency Rules

Do not hardcode paths.
Always return validated configuration objects.
Never modify configuration objects at runtime.

---

## Implement In

```
core/config_manager.py

configs/

configs/defaults.yaml
configs/datasets/
configs/error_models/
configs/analyses/
configs/experiments/
configs/schemas/
```

---

## Implement

Configuration loader

Configuration merging

```
defaults

↓

dataset

↓

error model

↓

analysis profile

↓

experiment
```

YAML validation

Configuration objects

Default handling

Schema validation

---

## Do NOT Implement

Dataset loading

Graph creation

Experiment execution

Biological parameters

---

## Required Information

Architecture only.

---

# 003 Dataset Registry

## Purpose

Provide a centralized registry for all supported FlyWire datasets.


### Input

Dataset Registry configuration

### Responsibilities

Register available datasets
Resolve folder paths
Provide lookup API

### Output

Dataset Location

### Consumed By

Phase 004

### Consistency Rules

Do not parse CSV files.
Only return validated paths and metadata.

---

## Implement In

```
core/dataset_registry.py

configs/datasets/
```

---

## Implement

Dataset registration

Dataset metadata

Version information

Folder resolution

Path validation

Dataset lookup API

---

## Registry Should Return

```
Dataset Name

↓

Version

↓

Location

↓

Metadata
```

---

## Do NOT Implement

CSV parsing

Graph creation

Caching

Preprocessing

---

## Required Information

Dataset names

Folder organization

---

# PHASE 2 – Data Layer

Cannot be fully implemented until CSV schema is finalized.

---

# 004 Data Loader

## Purpose

Load FlyWire datasets into memory.


### Input

Dataset name
Dataset root path
Dataset Registry information
Raw CSV files

### Responsibilities

Load datasets into memory
Stream large files
Validate table structure

### Output

FlyWireDataset
├── neurons DataFrame
└── connections DataFrame

### Consumed By

Graph Builder

### Consistency Rules

Always return the same FlyWireDataset object.
Never return raw dictionaries.
Never modify biological values.
Only normalize schema.

---

## Implement In

```
core/data_loader.py
```

---

## Implement

Dataset loading pipeline

Compressed CSV reader

Streaming support

Memory-efficient loading

Validation

Error handling

Dataset object creation

---

## Needs Before Implementation

Final CSV schema

Specifically

* neuron table
* edge table
* column names
* data types
* missing value rules

---

## Loader Should Produce

```
Raw Tables

↓

Validated Tables

↓

Dataset Object
```

---

## Should NOT

Build graphs

Modify data

Remove rows

Apply preprocessing

Run experiments

---

# 005 Graph Builder

## Purpose

Convert dataset tables into a reusable graph representation.


### Input

FlyWireDataset
├── neurons DataFrame
└── connections DataFrame

### Responsibilities

Create graph nodes
Create graph edges
Attach attributes
Return reusable graph
Do not compute graph metrics.

### Output

Graph API Object

(Current implementation: NetworkX DiGraph)
Nodes
Edges
Node attributes
Edge attributes

### Consumed By

Preprocessing
Analysis Framework
Error Framework

### Consistency Rules

Always produce the same graph type.
Do not compute graph statistics.
Do not modify biological metadata.
Only construct the graph.

---

## Implement In

```
core/graph_builder.py
```

---

## Implement

Graph construction

Node creation

Edge creation

Attributes

Metadata

Graph API

---

## Required Before Coding

CSV schema

Graph library

(NetworkX / igraph)

Node representation

Edge representation

Graph metadata design

---

## Graph API Must Define

```
Nodes

Edges

Attributes

Graph Metadata

Lookup Methods
```

---

## Important

This becomes the central contract.

Changing it later affects nearly every component.

---

# 006 Preprocessing

## Purpose

Prepare graphs before analysis.

Runs once per dataset.


### Input

Directed weighted graph
Node attributes
Edge attributes

### Responsibilities

• Validate graph structure
• Generate validation report
• Generate reusable graph metadata
• Build reusable lookup/index structures
• Prepare the graph for downstream components

### Output

Prepared Graph

A validated Graph API Object enriched with reusable metadata.

The graph topology and biological information remain unchanged.

### Consumed By

Experiment Runner

### Consistency Rules

Do not perturb graph.
Do not apply biological changes.
Maintain consistent node IDs.

---

## Implement In

```
modules/preprocessing/
```

---

## Implement

Structural validation

Validation report generation

Metadata generation

Reusable lookup/index generation

Graph preparation for downstream components

---

## Required Before Coding

Graph API

Cleaning strategy

Validation rules

Caching strategy

---

## Output

```
Graph API Object

↓

Validation

↓

Metadata Generation

↓

Prepared Graph
```

---

## Never Do

Perturbations

Statistics

Analysis

Experiment logic

---

# PHASE 3 – Framework Interfaces

Framework becomes reusable here.

---

# 007 Analysis Framework

## Purpose

Provide reusable interfaces for graph analyses.


### Input

Architecture requirements
Graph API contract
Analysis interface contract
Result interface contract

### Responsibilities

Provide reusable analysis interfaces
Register available analyses

### Output

Analysis Interface

### Consumed By

Experiment Runner

### Consistency Rules

Expose interfaces only.
Do not implement algorithms.
Maintain a stable analysis API.

---

## Implement In

```
modules/graph_analyses/

base_analysis.py
analysis_registry.py
```

---

## Implement

Abstract analysis interface

Registration mechanism

Execution interface

Shared outputs

Result object

---

## Do NOT Implement

Degree

PageRank

Communities

Matching

Biological metrics

Only interfaces.

---

## Future Modules

Structural

Centrality

Community

Biological

Matching

Conserved Circuits

---

# 008 Error Model Framework

## Purpose

Provide reusable perturbation interfaces.


### Input

Architecture requirements
Graph API contract
Perturbation interface contract
Configuration contract

### Responsibilities

Define BaseErrorModel
Define Registration mechanism
Define Configuration interface
Define Common execution contract

### Output

Error Interface

### Consumed By

Experiment Runner

### Consistency Rules

Expose interfaces only.
Do not implement specific error logic like missed synapses.
Maintain a stable error model API.

---

## Implement In

```
modules/error_models/

base_error_model.py
error_registry.py
```

---

## Implement

Abstract perturbation interface

Registration

Random seed support

Configuration handling

Validation

---

## Do NOT Implement

Missed synapses

Merge

Split

False positives

Weight noise

Localized errors

Only framework.

---

# PHASE 4 – Experiment Execution

---

# 009 Experiment Runner

## Purpose

Coordinate the complete execution pipeline.


### Input

Framework Components
Prepared Graph
Analysis Interface
Error Interface
Configuration Objects

### Responsibilities

Coordinate execution pipeline
Run baseline analyses
Execute experiment loops

### Output

Experiment Results

### Consumed By

Phase 010

### Consistency Rules

Never implement biology.
Never know specific metric logic.
Only orchestrate the pipeline and pass data.

---

## Implement In

```
core/experiment_runner.py
```

---

## Responsibilities

Load Configuration

↓

Load Dataset

↓

Build Graph

↓

Preprocess Graph

↓

Run Baseline Analyses

↓

Execute Experiment Loop

↓

Generate Experiment Results

---

## Runner Should Never Know

Biology

Perturbation implementation

Graph algorithms

Specific metrics

---

## Required Before Coding

Analysis interface

Error interface

Graph API

Configuration objects

---

# 010 Export & Statistics

## Purpose

Aggregate and export experiment results.


### Input

Experiment Results

Configuration Snapshot

Runtime Metadata

### Responsibilities

Compute confidence intervals
Calculate mean and variance
Format results into standard exports

### Output

Export Package

### Consumed By

Researcher

### Consistency Rules

Never modify experiment results.
Only format and package.

---

## Implement In

```
core/statistics_engine.py

core/export_manager.py

core/metadata_manager.py
```

---

## Implement

Statistics

Confidence intervals

Mean

Variance

CSV export

Metadata

Experiment package

README generation

ZIP creation

---

## Output Package

```
README.md

summary.csv

trial_results.csv

metadata.json

config_snapshot.yaml

runtime_report.txt

plots/

logs/
```

---

## Never Access

Raw datasets

Graph objects

Perturbation logic

---

# PHASE 5 – Research Modules

Framework is complete.

Scientific implementation begins.

---

# 011–020 Missed Synapses

Implement In

```
modules/error_models/false_negatives/

modules/graph_analyses/

configs/error_models/

configs/experiments/
```

---

## Requires

Scientific methodology

Probability model

Randomization strategy

Evaluation protocol

Statistical methodology

Metric definitions

Validation protocol

---

## Framework Components Reused

Configuration

Dataset Loader

Graph Builder

Preprocessing

Experiment Runner

Statistics

Export

---

## New Code

Only perturbation logic

Only analysis implementations

No framework modification

---

# PHASE 6 – Future Error Models

Implement

```
False Positives

Merge Errors

Split Errors

Weight Noise

Localized Errors
```

---

## Rule

Only add new modules.

Never modify

```
core/

experiment_runner

graph API

configuration

statistics

export
```

---

# Information Required Before Each Phase

| Information                  | Needed By | Reason                                        |
| ---------------------------- | --------- | --------------------------------------------- |
| Repository Architecture      | 001       | Create project structure                      |
| Configuration Design         | 002       | Build configuration system                    |
| Dataset List                 | 003       | Register available datasets                   |
| CSV Schema                   | 004       | Correctly parse FlyWire files                 |
| Graph API Design             | 005       | Define the framework's central graph contract |
| Preprocessing Strategy       | 006       | Standardize graph preparation                 |
| Analysis Interface Design    | 007       | Build reusable analysis framework             |
| Error Model Interface Design | 008       | Build reusable perturbation framework         |
| Experiment Lifecycle         | 009       | Orchestrate execution pipeline                |
| Statistics Methodology       | 010       | Aggregate experiment results                  |
| Biological Methodology       | 011+      | Implement scientific error models             |
| Metric Definitions           | 013+      | Implement graph analyses                      |

---

# Development Rules

## Framework Rules

* Framework code must never contain biological logic.
* Keep `core/` generic and reusable.
* Keep `modules/` responsible only for scientific implementations.
* Configuration must drive behavior; avoid hardcoded values.
* The Graph API is the central contract and should remain stable.

## Research Rules

* Every new error model should extend the framework rather than modify it.
* Every new graph analysis should implement the shared analysis interface.
* One Kaggle run should execute exactly one Dataset + one Error Model + one Analysis Profile.
* Raw datasets remain immutable; perturbations always operate on graph copies.
* Export only summarized results to `results/`; keep large artifacts in `research_data/`.

---

# Complete Implementation Roadmap

```text
001 Repository Scaffold
        │
        ▼
002 Configuration System
        │
        ▼
003 Dataset Registry
        │
        ▼
      (Need CSV Schema)
        │
        ▼
004 Data Loader
        │
        ▼
      (Need Graph Design)
        │
        ▼
005 Graph Builder
        │
        ▼
006 Preprocessing
        │
        ▼
007 Analysis Framework
        │
        ▼
008 Error Model Framework
        │
        ▼
009 Experiment Runner
        │
        ▼
010 Statistics & Export
        │
        ▼
Reusable Research Framework Complete
        │
        ▼
011–020 Missed Synapses Research Module
        │
        ▼
Framework Validation
        │
        ▼
021–025 Additional Error Models
        │
        ▼
Reusable Connectomics Research Platform
```

This version is intended as an implementation guide rather than just a conceptual reference. It maps each phase directly to your repository structure, makes explicit **what code belongs in which directory**, identifies the architectural dependencies that block implementation, and enforces the separation between reusable framework code (`core/`, `configs/`) and scientific research modules (`modules/`).

---

## Phase Input / Output Contracts

| Phase | Input | Output | Next Consumer |
|---|---|---|---|
| 001 | Repository Architecture | Repository Structure | 002 |
| 002 | Configuration Files | Configuration Objects | 003,009 |
| 003 | Dataset Registry | Dataset Location | 004 |
| 004 | CSV Files | FlyWireDataset | 005 |
| 005 | FlyWireDataset | Graph API Object | 006,007,008 |
| 006 | Graph API Object | Prepared Graph | 009 |
| 007 | Graph API Contract | Analysis Interface | 009 |
| 008 | Graph API Contract | Error Interface | 009 |
| 009 | Framework Components | Experiment Results | 010 |
| 010 | Experiment Results | Export Package | Researcher |

---

## Overall Data Flow

```text
Raw CSV Files
        │
        ▼
Data Loader
        │
        ▼
FlyWireDataset
        │
        ▼
Graph Builder
        │
        ▼
Graph API Object
        │
        ▼
Preprocessing
        │
        ▼
Prepared Graph
        │
        ▼
Experiment Runner
      ┌──────────────┬──────────────┐
      ▼              ▼
Error Model     Graph Analysis
      │              │
      └──────► Experiment Results ◄──────┘
                     │
                     ▼
            Statistics Engine
                     │
                     ▼
             Export Manager
                     │
                     ▼
            Experiment Package
```
