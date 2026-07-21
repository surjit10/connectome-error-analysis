# Experiment 1 Implementation Plan: Missed Synapses

This document breaks down Experiment 1 into small, modular implementation phases.

## Phase 011: Vulnerability Model Interface
* **Objective**: Define the core interface and logic for computing synaptic vulnerability.
* **Scientific Motivation**: Probabilities of missed synapses are not uniform; they depend on local graph topology.
* **Scope**: Create vulnerability base classes and degree-based implementations.
* **Expected Inputs**: PreparedGraph, biological configuration weights.
* **Expected Outputs**: Vulnerability score dictionary (edge index -> float).
* **Modules Affected**: `modules/error_models/`
* **Implementation Order**: 1

## Phase 012: Probability Calibration
* **Objective**: Map raw vulnerability scores to exact removal probabilities.
* **Scientific Motivation**: The framework requires an exact global error rate (e.g., 5%).
* **Scope**: Implement scaling algorithms to calibrate scores against a target error rate.
* **Expected Inputs**: Vulnerability scores, target error rate.
* **Expected Outputs**: Calibrated probabilities (edge index -> float).
* **Modules Affected**: `modules/error_models/`
* **Implementation Order**: 2

## Phase 013: Missed Synapses Error Model Core
* **Objective**: Implement the actual error model class registered in the framework.
* **Scientific Motivation**: Orchestrates vulnerability, calibration, and random sampling to generate the perturbed edge mask.
* **Scope**: Implement `MissedSynapses` extending `BaseErrorModel`.
* **Expected Inputs**: PreparedGraph, error config.
* **Expected Outputs**: `ErrorResult` containing the `edge_mask`.
* **Modules Affected**: `modules/error_models/missed_synapses.py`
* **Implementation Order**: 3

## Phase 014: Scientific Analyses Plugins
* **Objective**: Implement specific structural and biological analyses for the experiment.
* **Scientific Motivation**: We need to measure the topological impact (e.g. PageRank degradation) caused by the error model.
* **Scope**: Implement concrete analyses extending `BaseAnalysis`.
* **Expected Inputs**: PreparedGraph (perturbed).
* **Expected Outputs**: `AnalysisResult` containing numeric metrics.
* **Modules Affected**: `modules/graph_analyses/`
* **Implementation Order**: 4

## Phase 015: Automated Test Coverage
* **Objective**: Validate the scientific modules.
* **Scope**: Unit tests for vulnerability, calibration, and analyses.
* **Modules Affected**: `tests/`
* **Implementation Order**: 5

## Phase 016: Scientific Documentation
* **Objective**: Update the methodology documentation.
* **Scope**: Document the final algorithms used in the vulnerability model and analyses.
* **Modules Affected**: `docs/`
* **Implementation Order**: 6

## Phase 017: Notebook Integration
* **Objective**: Finalize the user-facing Kaggle notebook.
* **Scope**: Ensure the notebook registers the new plugins and exposes the new config parameters.
* **Modules Affected**: `experiments_missed_synapses.ipynb`
* **Implementation Order**: 7
