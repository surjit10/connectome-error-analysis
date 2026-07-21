from modules.error_models.base_error_model import BaseErrorModel
from modules.error_models.error_result import ErrorResult, ErrorModelStatus
from modules.preprocessing import PreparedGraph

class DummyErrorModel(BaseErrorModel):
    NAME = "dummy_error"
    
    def _perturb(self, prepared: PreparedGraph, config: dict, result: ErrorResult, rng) -> None:
        """Simple dummy model that does no perturbation."""
        # Baseline execution implies returning an empty mask or no updates
        result.edge_mask = [True] * prepared.edge_count()
        result.weight_updates = {}
        result.status = ErrorModelStatus.SUCCESS
        result.metrics = {"dummy_metric": 42}
