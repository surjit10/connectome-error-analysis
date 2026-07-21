# Verification Rules

Every implementation prompt requires an upfront verification step.

The implementing agent **must first verify**:
1. Existing interfaces (e.g., read abstract base classes).
2. Existing concrete classes (e.g., how the registry is populated).
3. Method signatures (e.g., verify `def _run(...)` arguments).
4. Return objects (e.g., `ErrorResult` properties).
5. Configuration schemas (e.g., YAML layouts).
6. Required dependencies (e.g., verify upstream phase is actually committed).

**CRITICAL:** The AI must NEVER assume APIs exist. 
If verification fails or a method signature is different than expected, **implementation must stop immediately** and the discrepancy must be reported.
