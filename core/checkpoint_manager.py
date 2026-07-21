"""
Phase 012 — Checkpoint Manager
==============================
Handles saving and loading of experiment state, biological features, and vulnerability tables.
"""
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class CheckpointManager:
    """Manages serialization of intermediate pipeline artifacts."""
    
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[CheckpointManager] Initialized at {self.output_dir}")
        
    def save_checkpoint(self, name: str, data: Dict[str, Any]) -> None:
        """Saves a generic checkpoint containing metadata and tables."""
        file_path = self.output_dir / f"{name}.pkl"
        try:
            with open(file_path, "wb") as f:
                pickle.dump(data, f)
            logger.info(f"[CheckpointManager] Saved checkpoint '{name}' to {file_path}")
        except Exception as e:
            logger.error(f"[CheckpointManager] Failed to save checkpoint '{name}': {e}")
            raise
            
    def load_checkpoint(self, name: str) -> Optional[Dict[str, Any]]:
        """Loads a generic checkpoint."""
        file_path = self.output_dir / f"{name}.pkl"
        if not file_path.exists():
            logger.warning(f"[CheckpointManager] Checkpoint '{name}' not found.")
            return None
        try:
            with open(file_path, "rb") as f:
                logger.info(f"[CheckpointManager] Loaded checkpoint '{name}' from {file_path}")
                return pickle.load(f)
        except Exception as e:
            logger.error(f"[CheckpointManager] Failed to load checkpoint '{name}': {e}")
            return None

    def save_phase_012_checkpoint(
        self, 
        experiment_name: str, 
        metadata: Any,
        biological_assumptions: Any,
        edge_feature_table: Any,
        validation_results: Any
    ) -> None:
        """
        Specialized method to save Phase 012 artifacts.
        Avoids storing duplicate graph data (the raw igraph object).
        """
        checkpoint_data = {
            "experiment_metadata": experiment_name,
            "dataset_metadata": metadata,
            "biological_assumptions": biological_assumptions,
            "edge_feature_table": edge_feature_table,
            "validation_results": validation_results
        }
        self.save_checkpoint(f"{experiment_name}_phase_012", checkpoint_data)

    def save_phase_013_checkpoint(
        self,
        experiment_name: str,
        metadata: Any,
        vulnerability_model_parameters: Any,
        edge_vulnerability_table: Any,
        validation_results: Any
    ) -> None:
        """
        Specialized method to save Phase 013 artifacts.
        """
        checkpoint_data = {
            "experiment_metadata": experiment_name,
            "dataset_metadata": metadata,
            "vulnerability_model_parameters": vulnerability_model_parameters,
            "edge_vulnerability_table": edge_vulnerability_table,
            "validation_results": validation_results
        }
        self.save_checkpoint(f"{experiment_name}_phase_013", checkpoint_data)

    def save_phase_014_checkpoint(
        self,
        experiment_name: str,
        metadata: Any,
        target_error_rate: float,
        edge_probability_table: Any,
        validation_results: Any
    ) -> None:
        """
        Specialized method to save Phase 014 artifacts.
        """
        checkpoint_data = {
            "experiment_metadata": experiment_name,
            "dataset_metadata": metadata,
            "target_error_rate": target_error_rate,
            "edge_probability_table": edge_probability_table,
            "validation_results": validation_results
        }
        self.save_checkpoint(f"{experiment_name}_phase_014", checkpoint_data)

    def save_phase_015_checkpoint(
        self,
        experiment_name: str,
        metadata: Any,
        simulation_statistics: Any,
        perturbed_graph_info: Any,
        validation_results: Any
    ) -> None:
        """
        Specialized method to save Phase 015 artifacts.
        """
        checkpoint_data = {
            "experiment_metadata": experiment_name,
            "dataset_metadata": metadata,
            "simulation_statistics": simulation_statistics,
            "perturbed_graph_info": perturbed_graph_info,
            "validation_results": validation_results
        }
        self.save_checkpoint(f"{experiment_name}_phase_015", checkpoint_data)

    def save_phase_016_checkpoint(
        self,
        experiment_name: str,
        metadata: Any,
        analysis_results: Any,
        validation_results: Any
    ) -> None:
        """
        Specialized method to save Phase 016 artifacts.
        """
        checkpoint_data = {
            "experiment_metadata": experiment_name,
            "dataset_metadata": metadata,
            "analysis_results": analysis_results,
            "validation_results": validation_results
        }
        self.save_checkpoint(f"{experiment_name}_phase_016", checkpoint_data)

    def save_phase_017_checkpoint(
        self,
        experiment_name: str,
        evaluation_result: Any,
        validation_results: Any
    ) -> None:
        """
        Specialized method to save Phase 017 artifacts.
        """
        checkpoint_data = {
            "experiment_metadata": experiment_name,
            "evaluation_result": evaluation_result,
            "validation_results": validation_results
        }
        self.save_checkpoint(f"{experiment_name}_phase_017", checkpoint_data)
