# FlyWire Connectomics Prompt Engineering Framework

## Purpose
This directory serves as the central orchestration hub for all future AI-assisted implementation workflows in the FlyWire Research Framework. It houses execution prompts, dependency graphs, architectural rules, and progress trackers.

## How Prompts are Generated
Prompts are not written ad-hoc. They are generated based strictly on the templates provided in the `templates/` directory and must pass verification checks before execution. Every prompt is isolated to a single scientific responsibility or framework layer.

## Dependency-First Implementation Philosophy
No implementation prompt may be generated or executed until all of its upstream dependencies have been completed, merged, and verified. Dependencies are explicitly documented in `dependency_graph.md`.

## Verification-First Workflow
Before any implementation code is written, the implementing AI agent must perform a repository inspection. It must verify that the requested APIs exist, check the method signatures, and ensure the architectural state matches the prompt's assumptions. If verification fails, implementation halts.

## Implementation Lifecycle
1. **Verify Previous Phase**: Ensure prerequisite phases are fully merged.
2. **Verify Dependencies**: Check inputs and interfaces.
3. **Verify Repository**: Read actual source code to confirm API contracts.
4. **Generate Prompt**: Use `implementation_prompt_template.md`.
5. **Implement**: Execute the prompt (coding).
6. **Run Tests**: Verify regression and unit tests.
7. **Update Tracker**: Mark the phase as Complete in `implementation_tracker.md`.
8. **Generate Next Prompt**: Proceed to the next phase.
