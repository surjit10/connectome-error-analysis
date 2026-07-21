# Prompt Generation Rules

Implementation prompts generated for AI agents must strictly follow this structure:

1. **Scientific Motivation**: Why is this step biologically or mathematically necessary?
2. **Implementation Objective**: What exactly needs to be built?
3. **Repository Inspection**: Explicit instructions to use CLI or read tools to inspect the codebase BEFORE coding.
4. **Files Allowed to Modify**: A strict whitelist of target files.
5. **Files Forbidden to Modify**: Core framework files that must remain untouched.
6. **Existing APIs to Inspect**: Exact interfaces the agent must read (e.g., `BaseErrorModel._perturb()`).
7. **Implementation Requirements**: Technical and architectural constraints.
8. **Algorithm**: Detailed steps for the logic (if applicable).
9. **Validation Checklist**: Unit test requirements.
10. **Regression Checklist**: Ensuring previous components still function.
11. **Deliverables**: What the AI must output upon completion.

**Rule:** No implementation prompt may skip any of these sections.
