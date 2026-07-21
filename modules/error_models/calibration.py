"""
Phase 014 — Probability Calibration
===================================
Converts relative biological vulnerability scores into strict execution probabilities.
Ensures that Expected Synapse Loss ≈ Target Experimental Error Rate.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
import numpy as np
import polars as pl
from typing import Any

from modules.error_models.vulnerability import EdgeVulnerabilityTable

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class CalibratedProbabilityTable:
    """Immutable calibrated probability representation."""
    probabilities: pl.DataFrame
    
    def __post_init__(self) -> None:
        if "calibrated_removal_probability" not in self.probabilities.columns:
            raise ValueError("CalibratedProbabilityTable missing 'calibrated_removal_probability'.")
        col = self.probabilities["calibrated_removal_probability"]
        if col.null_count() > 0:
            raise ValueError("calibrated_removal_probability contains missing values.")
        if not col.is_finite().all():
            raise ValueError("calibrated_removal_probability contains non-finite values.")
        if col.min() < 0.0 or col.max() > 1.0:
            raise ValueError(f"calibrated_removal_probability out of bounds [0.0, 1.0]. Min: {col.min()}, Max: {col.max()}")
        logger.info(f"[Calibration] Validated CalibratedProbabilityTable for {len(self.probabilities)} edges.")

class ProbabilityCalibrator:
    """
    Calibrates vulnerability scores so that the expected number of removed
    synapses matches the target error rate precisely.
    """
    
    def __init__(self, target_error_rate: float, max_iterations: int = 50, tolerance: float = 1e-6):
        self.target_error_rate = float(target_error_rate)
        self.max_iterations = int(max_iterations)
        self.tolerance = float(tolerance)
        
    def calibrate(self, vulnerability_table: EdgeVulnerabilityTable) -> CalibratedProbabilityTable:
        """
        Executes the iterative calibration scaling algorithm.
        """
        logger.info("[Calibration] Starting probability calibration.")
        df = vulnerability_table.scores
        
        # Determine total synapses and target drops
        total_synapses = df["syn_count"].sum()
        target_synapse_drops = total_synapses * self.target_error_rate
        logger.info(f"[Calibration] Target error rate: {self.target_error_rate:.4f}. Target synapse drops: {target_synapse_drops:.2f} / {total_synapses}")
        
        if target_synapse_drops == 0:
            logger.info("[Calibration] Target error rate is 0. Setting all probabilities to 0.0.")
            df_calibrated = df.with_columns(calibrated_removal_probability=pl.lit(0.0))
            return CalibratedProbabilityTable(probabilities=df_calibrated)
            
        raw = df["raw_vulnerability_score"].to_numpy().astype(np.float64)
        syn = df["syn_count"].to_numpy().astype(np.float64)
        
        current_weighted_sum = (raw * syn).sum()
        
        if current_weighted_sum <= 0:
            logger.warning("[Calibration] Sum of raw vulnerability is 0. Applying uniform probability across all synapses.")
            # If all vulnerability scores are 0, everyone gets uniform probability scaled by their synapses.
            # p_e = target_synapse_drops / total_synapses
            p = np.full(len(raw), self.target_error_rate, dtype=np.float64)
            df_calibrated = df.with_columns(calibrated_removal_probability=pl.Series(p))
            return CalibratedProbabilityTable(probabilities=df_calibrated)
            
        # Iterative mass redistribution
        alpha = target_synapse_drops / current_weighted_sum
        p = raw * alpha
        
        for iteration in range(self.max_iterations):
            capped = p > 1.0
            if not capped.any():
                expected_drops = (p * syn).sum()
                logger.info(f"[Calibration] Converged without capping. Expected drops: {expected_drops:.2f}")
                break
                
            p[capped] = 1.0
            expected_drops = (p * syn).sum()
            diff = target_synapse_drops - expected_drops
            
            if abs(diff) < self.tolerance:
                logger.info(f"[Calibration] Converged after {iteration+1} iterations. Expected drops: {expected_drops:.2f}")
                break
                
            # Redistribute lost mass to uncapped edges
            uncapped = ~capped
            uncapped_weighted_sum = (raw[uncapped] * syn[uncapped]).sum()
            
            if uncapped_weighted_sum <= 0:
                logger.warning("[Calibration] Cannot redistribute mass; all non-zero vulnerability edges are capped.")
                break
                
            capped_drops = (p[capped] * syn[capped]).sum()
            required_from_uncapped = target_synapse_drops - capped_drops
            
            new_alpha = required_from_uncapped / uncapped_weighted_sum
            p[uncapped] = raw[uncapped] * new_alpha
        else:
            expected_drops = (p * syn).sum()
            logger.warning(f"[Calibration] Reached maximum iterations ({self.max_iterations}). Final expected drops: {expected_drops:.2f}")
            
        # Ensure strict bounding [0.0, 1.0] due to floating point inaccuracies
        p = np.clip(p, 0.0, 1.0)
            
        df_calibrated = df.with_columns(
            calibrated_removal_probability = pl.Series("calibrated_removal_probability", p)
        )
        
        logger.info("[Calibration] Calibration scaling completed.")
        return CalibratedProbabilityTable(probabilities=df_calibrated)
