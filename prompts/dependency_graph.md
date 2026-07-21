# Dependency Graph (Phases 011-017)

The implementation order must strictly follow this directed acyclic graph.

`Feature Extraction` (Phase 006) 
       ↓ 
**Phase 011: Vulnerability Model** 
*(Depends on: Feature Extraction. Consumes: PreparedGraph. Produces: Vulnerability Scores)*
       ↓ 
**Phase 012: Probability Calibration** 
*(Depends on: Vulnerability Model. Consumes: Vulnerability Scores. Produces: Probabilities)*
       ↓ 
**Phase 013: Missed Synapse Error Model** 
*(Depends on: Calibration. Consumes: Probabilities. Produces: ErrorResult)*
       ↓ 
**Phase 014: Scientific Analysis Plugins** 
*(Depends on: Error Model. Consumes: Perturbed Graph. Produces: AnalysisResult)*
       ↓ 
**Phase 015: Automated Test Coverage** 
*(Depends on: Phases 011-014. Consumes: Implemented Modules. Produces: Test Reports)*
       ↓ 
**Phase 016: Scientific Documentation** 
*(Depends on: Phase 014. Consumes: Final Implementations. Produces: Documentation)*
       ↓ 
**Phase 017: Notebook Integration** 
*(Depends on: Phase 013, 014. Consumes: Registries. Produces: Final `.ipynb` Launcher)*
