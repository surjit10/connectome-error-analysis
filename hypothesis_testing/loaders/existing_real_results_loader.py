"""
Existing Real Results Loader
============================
Loads replicate-level Real connectome observations from either:
1. Canonical hypothesis-testing replicate CSV / Parquet exports
   (e.g., secondary_effect_summary.csv, replicate_level_effects.parquet).
2. Historical experiment result directory trees (e.g., results/banc/ or
   flywire_results_organized/BANC/) by discovering per-trial summary.csv and
   metadata.json files across error rates and seeds, matching own-seed 0% baselines.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from ..analysis.secondary_effects import (
    SecondaryEffectRecord,
    classify_metric,
)

logger = logging.getLogger(__name__)


class ExistingRealResultsLoader:
    """Loads and converts existing Real experiment results into canonical SecondaryEffectRecord objects."""

    def __init__(self, near_zero_threshold: float = 1e-4) -> None:
        self.near_zero_threshold = near_zero_threshold

    def load(
        self,
        source_path: Union[str, Path],
        dataset_name: Optional[str] = None,
        error_models: Optional[List[str]] = None,
        error_rates: Optional[List[float]] = None,
    ) -> List[SecondaryEffectRecord]:
        """Load replicate-level records from a canonical file or results directory.

        Args:
            source_path: File path (CSV/Parquet) or Directory path to historical results.
            dataset_name: Optional dataset filter/override.
            error_models: Optional list of error models to include.
            error_rates: Optional list of error rates to include.

        Returns:
            List of validated SecondaryEffectRecord objects.

        Raises:
            FileNotFoundError: If source_path does not exist.
            ValueError: If source data contains only aggregated means or is incompatible.
        """
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"[ExistingRealResultsLoader] Path not found: {path}")

        if path.is_file():
            return self._load_from_file(path, dataset_name, error_models, error_rates)
        elif path.is_dir():
            return self._load_from_directory(path, dataset_name, error_models, error_rates)
        else:
            raise ValueError(f"[ExistingRealResultsLoader] Unsupported path type: {path}")

    def _load_from_file(
        self,
        file_path: Path,
        dataset_name: Optional[str] = None,
        error_models: Optional[List[str]] = None,
        error_rates: Optional[List[float]] = None,
    ) -> List[SecondaryEffectRecord]:
        """Load from a canonical CSV or Parquet file."""
        logger.info(f"[ExistingRealResultsLoader] Loading records from file: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix == ".parquet":
            df = pd.read_parquet(file_path)
        elif suffix == ".csv":
            df = pd.read_csv(file_path, keep_default_na=False)
        else:
            raise ValueError(
                f"[ExistingRealResultsLoader] Unsupported file extension '{suffix}'. Expected .csv or .parquet."
            )

        # Ensure condition column values are strings ('real' or 'null')
        if "condition" in df.columns:
            df["condition"] = df["condition"].astype(str).str.lower()
            df["condition"] = df["condition"].replace({"": "null", "nan": "null", "none": "null"})


        # Validate that the file contains replicate-level data rather than only aggregated means
        required_cols = {"condition", "error_model", "error_rate", "metric_name", "relative_change"}
        missing = required_cols - set(df.columns)
        if missing:
            # Check if this is an aggregated summary without replicate observations
            if "baseline_mean" in df.columns or "mean_preservation" in df.columns:
                raise ValueError(
                    f"[ExistingRealResultsLoader] File '{file_path}' contains only pre-aggregated summary statistics "
                    f"without replicate-level trial observations (missing columns: {sorted(missing)}). "
                    "Valid statistical inference (Welch's t-test) requires raw replicate observations."
                )
            raise ValueError(
                f"[ExistingRealResultsLoader] Missing required replicate-level columns: {sorted(missing)}"
            )

        records: List[SecondaryEffectRecord] = []
        for _, row in df.iterrows():
            cond = str(row.get("condition", "real")).lower()
            d_name = str(row.get("dataset", dataset_name or "DATASET"))
            em = str(row["error_model"])
            rate = float(row["error_rate"])

            if dataset_name and d_name.lower() != dataset_name.lower():
                continue
            if error_models and em not in error_models:
                continue
            if error_rates and not any(math.isclose(rate, r, abs_tol=1e-5) for r in error_rates):
                continue

            metric = str(row["metric_name"])
            a_name = str(row.get("analysis_name", "analysis"))
            category = str(row.get("category", classify_metric(em, metric).value))
            b_val = float(row.get("baseline_value", 0.0))
            p_val = float(row.get("perturbed_value", 0.0))
            abs_delta = float(row.get("absolute_delta", p_val - b_val))
            rel_change = float(row.get("relative_change", 0.0))
            is_near_zero = bool(row.get("is_near_zero_baseline", abs(b_val) < self.near_zero_threshold))
            seed = int(row.get("trial_seed", row.get("seed", 1)))
            null_rep_id = row.get("null_graph_replicate_id")
            if pd.isna(null_rep_id):
                null_rep_id = None
            else:
                null_rep_id = int(null_rep_id)

            comp_ratio = row.get("perturbation_completion_ratio")
            if pd.isna(comp_ratio):
                comp_ratio = None
            else:
                comp_ratio = float(comp_ratio)

            records.append(SecondaryEffectRecord(
                condition=cond,
                dataset=d_name,
                error_model=em,
                error_rate=rate,
                trial_seed=seed,
                analysis_name=a_name,
                metric_name=metric,
                category=category,
                baseline_value=b_val,
                perturbed_value=p_val,
                absolute_delta=abs_delta,
                relative_change=rel_change,
                is_near_zero_baseline=is_near_zero,
                null_graph_replicate_id=null_rep_id,
                perturbation_completion_ratio=comp_ratio,
            ))

        logger.info(f"[ExistingRealResultsLoader] Loaded {len(records)} replicate records from file.")
        return records

    def _load_from_directory(
        self,
        dir_path: Path,
        dataset_name: Optional[str] = None,
        error_models: Optional[List[str]] = None,
        error_rates: Optional[List[float]] = None,
    ) -> List[SecondaryEffectRecord]:
        """Traverse a historical experiment result directory and extract replicate-level records."""
        logger.info(f"[ExistingRealResultsLoader] Scanning historical result directory: {dir_path}")

        # Check for direct canonical summary file first
        canonical_csv = dir_path / "secondary_effect_summary.csv"
        if canonical_csv.exists():
            return self._load_from_file(canonical_csv, dataset_name, error_models, error_rates)

        canonical_parquet = dir_path / "replicate_level_effects.parquet"
        if canonical_parquet.exists():
            return self._load_from_file(canonical_parquet, dataset_name, error_models, error_rates)

        # Discover trial directories with metadata.json and summary.csv
        # Pattern: <error_model>/<rate_str>/trial_<seed>/<exp_id>/
        trial_dirs: List[Path] = []
        for p in dir_path.glob("*/*/*/BANC_*"):
            if p.is_dir() and (p / "metadata.json").exists() and (p / "summary.csv").exists():
                trial_dirs.append(p)
        # Also check general non-BANC naming patterns
        if not trial_dirs:
            for p in dir_path.glob("*/*/*/*"):
                if p.is_dir() and (p / "metadata.json").exists() and (p / "summary.csv").exists():
                    trial_dirs.append(p)

        if not trial_dirs:
            raise ValueError(
                f"[ExistingRealResultsLoader] No valid trial directories found in '{dir_path}'. "
                "Expected directories containing metadata.json and summary.csv."
            )

        # Group trial data by (error_model, rate, seed)
        # 1. Parse all trials
        trials_data: List[Dict[str, Any]] = []
        for td in trial_dirs:
            try:
                with open(td / "metadata.json", "r", encoding="utf-8") as f:
                    meta = json.load(f)
                summ_df = pd.read_csv(td / "summary.csv")

                em = meta.get("error_model_name") or meta.get("config_snapshot", {}).get("error_model_name")
                rate = float(
                    meta.get("error_model_config", {}).get("error_rate",
                    meta.get("config_snapshot", {}).get("error_model_config", {}).get("error_rate", 0.0))
                )
                seed = int(meta.get("seed", meta.get("config_snapshot", {}).get("seed", 1)))
                d_name = meta.get("dataset_name", dataset_name or "DATASET")

                # Extract metric map: {analysis: {metric: float_value}}
                metric_map: Dict[str, Dict[str, float]] = {}
                for _, row in summ_df.iterrows():
                    a_name = str(row["analysis"])
                    m_name = str(row["metric"])
                    # Use 'mean' as single trial value
                    val = float(row["mean"])
                    metric_map.setdefault(a_name, {})[m_name] = val

                achieved_rate = meta.get("perturbation_metadata", {}).get("achieved_error_rate")

                trials_data.append({
                    "dataset": d_name,
                    "error_model": em,
                    "error_rate": rate,
                    "seed": seed,
                    "metrics": metric_map,
                    "achieved_rate": achieved_rate,
                })
            except Exception as exc:
                logger.warning(f"[ExistingRealResultsLoader] Failed to read trial dir '{td}': {exc}")

        # 2. Extract baseline metrics per (error_model, seed) at rate=0.0
        baselines: Dict[Tuple[str, int], Dict[str, Dict[str, float]]] = {}
        for t in trials_data:
            if math.isclose(t["error_rate"], 0.0, abs_tol=1e-5):
                key = (t["error_model"], t["seed"])
                baselines[key] = t["metrics"]

        # Fallback baseline across all seeds if own-seed baseline missing
        global_baselines: Dict[str, Dict[str, Dict[str, float]]] = {}
        for (em, seed), m_dict in baselines.items():
            if em not in global_baselines:
                global_baselines[em] = m_dict

        # 3. Build SecondaryEffectRecord objects
        records: List[SecondaryEffectRecord] = []
        for t in trials_data:
            em = t["error_model"]
            rate = t["error_rate"]
            seed = t["seed"]
            d_name = t["dataset"]

            if dataset_name and d_name.lower() != dataset_name.lower():
                continue
            if error_models and em not in error_models:
                continue
            if error_rates and not any(math.isclose(rate, r, abs_tol=1e-5) for r in error_rates):
                continue

            base_m = baselines.get((em, seed), global_baselines.get(em, {}))

            comp_ratio = None
            if t["achieved_rate"] is not None and rate > 1e-10:
                comp_ratio = float(min(1.0, t["achieved_rate"] / rate))
            elif rate <= 1e-10:
                comp_ratio = 1.0

            for a_name, m_dict in t["metrics"].items():
                for m_name, p_val in m_dict.items():
                    if not math.isfinite(p_val):
                        continue

                    b_val = base_m.get(a_name, {}).get(m_name, 0.0)
                    abs_delta = p_val - b_val
                    is_near_zero = abs(b_val) < self.near_zero_threshold
                    rel_change = abs_delta if is_near_zero else (abs_delta / b_val)
                    category = classify_metric(em, m_name).value

                    records.append(SecondaryEffectRecord(
                        condition="real",
                        dataset=d_name,
                        error_model=em,
                        error_rate=rate,
                        trial_seed=seed,
                        analysis_name=a_name,
                        metric_name=m_name,
                        category=category,
                        baseline_value=b_val,
                        perturbed_value=p_val,
                        absolute_delta=abs_delta,
                        relative_change=rel_change,
                        is_near_zero_baseline=is_near_zero,
                        null_graph_replicate_id=None,
                        perturbation_completion_ratio=comp_ratio,
                    ))

        logger.info(
            f"[ExistingRealResultsLoader] Reconstructed {len(records)} replicate records "
            f"from historical trial directories in '{dir_path}'."
        )
        return records
