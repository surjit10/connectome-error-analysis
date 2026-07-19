"""
Phase 010 – Export Manager
============================
Packages a completed experiment into a reproducible research artifact on disk.

Responsibilities:
    - Create a dated output directory.
    - Write ``metadata.json``          — full experiment metadata.
    - Write ``config_snapshot.yaml``   — YAML-formatted configuration.
    - Write ``summary.csv``            — per-analysis aggregated statistics.
    - Write ``trial_results.csv``      — per-trial analysis metrics.
    - Write ``runtime_report.txt``     — human-readable pipeline summary.
    - Write ``README.md``              — experiment overview.
    - Create ``logs/`` and ``plots/``  — placeholder directories for future use.
    - Optionally produce a ``.zip``    — reproducibility archive.

Constraints:
    - Consumes only ``ExperimentResult``, ``ExperimentMetadata``, and
      ``ExperimentStatistics``.  Never reruns anything.
    - Never modifies any result or metadata object.
    - Uses only stdlib (``csv``, ``json``, ``zipfile``, ``pathlib``).
    - YAML export uses ``pyyaml`` (already in requirements.txt).
"""

from __future__ import annotations

import csv
import datetime
import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from core.experiment_runner import ExperimentResult
from core.metadata_manager import ExperimentMetadata
from core.statistics_engine import ExperimentStatistics

logger = logging.getLogger(__name__)

_FRAMEWORK_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Export Package descriptor
# ---------------------------------------------------------------------------

class ExportPackage:
    """Describes a completed export package.

    Attributes:
        output_dir:  The directory where all files were written.
        files:       List of :class:`pathlib.Path` objects for every written file.
        zip_path:    Path to the ZIP archive (or ``None`` if not created).
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir: Path = output_dir
        self.files: List[Path] = []
        self.zip_path: Optional[Path] = None

    def record(self, path: Path) -> None:
        """Register a newly written file."""
        self.files.append(path)

    def summary(self) -> str:
        zip_info = f", zip={self.zip_path}" if self.zip_path else ""
        return (
            f"ExportPackage(dir={self.output_dir}, "
            f"files={len(self.files)}{zip_info})"
        )

    def __repr__(self) -> str:
        return self.summary()


# ---------------------------------------------------------------------------
# Export Manager
# ---------------------------------------------------------------------------

class ExportManager:
    """Serialises experiment outputs into a reproducible research package.

    Example::

        from core.export_manager   import ExportManager
        from core.metadata_manager import MetadataManager
        from core.statistics_engine import StatisticsEngine

        stats    = StatisticsEngine().aggregate([result])
        metadata = MetadataManager().collect(result)
        package  = ExportManager().export(
            result   = result,
            metadata = metadata,
            stats    = stats,
            output_root = Path("results/"),
        )
        print(package.summary())
    """

    def export(
        self,
        result: ExperimentResult,
        metadata: ExperimentMetadata,
        stats: ExperimentStatistics,
        output_root: Path,
        *,
        create_zip: bool = True,
    ) -> ExportPackage:
        """Write all export files and return an :class:`ExportPackage`.

        Args:
            result:      The completed experiment result.
            metadata:    Collected by :class:`~core.metadata_manager.MetadataManager`.
            stats:       Aggregated by :class:`~core.statistics_engine.StatisticsEngine`.
            output_root: Root directory under which a timestamped sub-directory
                         is created.
            create_zip:  If ``True``, bundle the package into a ``.zip`` file.

        Returns:
            An :class:`ExportPackage` describing what was written.
        """
        # ── Create output directory ──────────────────────────────────────
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path(output_root) / f"{result.experiment_id}_{ts}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "logs").mkdir(exist_ok=True)
        (out_dir / "plots").mkdir(exist_ok=True)

        pkg = ExportPackage(output_dir=out_dir)

        logger.info(
            "[ExportManager] Writing package to '%s'.", out_dir,
        )

        # ── Individual file exports ──────────────────────────────────────
        self._write_metadata_json(out_dir, metadata, pkg)
        self._write_config_yaml(out_dir, metadata, pkg)
        self._write_summary_csv(out_dir, stats, pkg)
        self._write_trial_results_csv(out_dir, result, pkg)
        self._write_runtime_report(out_dir, result, metadata, stats, pkg)
        self._write_readme(out_dir, result, metadata, stats, pkg)

        # ── Optional ZIP ─────────────────────────────────────────────────
        if create_zip:
            zip_path = out_dir.parent / f"{out_dir.name}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in pkg.files:
                    zf.write(file_path, arcname=file_path.relative_to(out_dir.parent))
                # Include empty placeholder dirs.
                for placeholder in [out_dir / "logs", out_dir / "plots"]:
                    zf.mkdir(str(placeholder.relative_to(out_dir.parent)))
            pkg.zip_path = zip_path
            logger.info("[ExportManager] ZIP archive written: '%s'.", zip_path)

        logger.info("[ExportManager] Export complete. %s", pkg.summary())
        return pkg

    # ------------------------------------------------------------------ #
    # Individual writers                                                   #
    # ------------------------------------------------------------------ #

    def _write_metadata_json(
        self,
        out_dir: Path,
        metadata: ExperimentMetadata,
        pkg: ExportPackage,
    ) -> None:
        path = out_dir / "metadata.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2, default=str)
        pkg.record(path)
        logger.debug("[ExportManager] Wrote %s", path.name)

    def _write_config_yaml(
        self,
        out_dir: Path,
        metadata: ExperimentMetadata,
        pkg: ExportPackage,
    ) -> None:
        path = out_dir / "config_snapshot.yaml"
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(
                metadata.config_snapshot,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=True,
            )
        pkg.record(path)
        logger.debug("[ExportManager] Wrote %s", path.name)

    def _write_summary_csv(
        self,
        out_dir: Path,
        stats: ExperimentStatistics,
        pkg: ExportPackage,
    ) -> None:
        """Write one row per (analysis, metric) with aggregated statistics."""
        path = out_dir / "summary.csv"
        rows = []
        for a_name, a_stats in stats.analysis_stats.items():
            for m_name, m_stats in a_stats.metric_stats.items():
                rows.append({
                    "analysis":   a_name,
                    "metric":     m_name,
                    "n":          m_stats.n,
                    "mean":       m_stats.mean,
                    "std":        m_stats.std,
                    "variance":   m_stats.variance,
                    "min":        m_stats.min,
                    "max":        m_stats.max,
                    "ci_lower":   m_stats.ci_lower,
                    "ci_upper":   m_stats.ci_upper,
                })

        fieldnames = [
            "analysis", "metric", "n",
            "mean", "std", "variance", "min", "max", "ci_lower", "ci_upper",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        pkg.record(path)
        logger.debug("[ExportManager] Wrote %s (%d rows)", path.name, len(rows))

    def _write_trial_results_csv(
        self,
        out_dir: Path,
        result: ExperimentResult,
        pkg: ExportPackage,
    ) -> None:
        """Write one row per analysis result with all metrics flattened."""
        path = out_dir / "trial_results.csv"
        rows: List[Dict[str, Any]] = []

        for a_res in result.analysis_results:
            base = {
                "experiment_id":   result.experiment_id,
                "analysis_name":   a_res.analysis_name,
                "status":          a_res.status.value,
                "runtime_seconds": a_res.runtime_seconds,
                "warnings":        "; ".join(a_res.warnings),
                "errors":          "; ".join(a_res.errors),
            }
            # Flatten each metric into its own column.
            for k, v in a_res.metrics.items():
                base[f"metric_{k}"] = v
            rows.append(base)

        # Collect all column names across all rows.
        all_keys: List[str] = []
        seen: set = set()
        fixed = [
            "experiment_id", "analysis_name", "status",
            "runtime_seconds", "warnings", "errors",
        ]
        for key in fixed:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)
        for row in rows:
            for key in row:
                if key not in seen:
                    all_keys.append(key)
                    seen.add(key)

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        pkg.record(path)
        logger.debug("[ExportManager] Wrote %s (%d rows)", path.name, len(rows))

    def _write_runtime_report(
        self,
        out_dir: Path,
        result: ExperimentResult,
        metadata: ExperimentMetadata,
        stats: ExperimentStatistics,
        pkg: ExportPackage,
    ) -> None:
        lines = [
            "=" * 60,
            "FlyWire Connectome Error Analysis — Runtime Report",
            "=" * 60,
            f"Experiment ID    : {result.experiment_id}",
            f"Dataset          : {result.dataset_name}",
            f"Status           : {result.status.value}",
            f"Started          : {result.started_at}",
            f"Finished         : {result.finished_at}",
            f"Total runtime    : {result.runtime_seconds:.3f}s",
            f"Framework version: {_FRAMEWORK_VERSION}",
            "",
            "Error Model",
            "-" * 30,
        ]
        if result.error_result:
            er = result.error_result
            lines += [
                f"  Model  : {er.model_name}",
                f"  Status : {er.status.value}",
                f"  Runtime: {er.runtime_seconds:.3f}s",
                f"  Perturbation metadata: {er.perturbation_metadata}",
            ]
        else:
            lines.append("  None (baseline experiment)")

        lines += ["", "Analyses", "-" * 30]
        for a_res in result.analysis_results:
            lines.append(
                f"  {a_res.analysis_name}: status={a_res.status.value} "
                f"runtime={a_res.runtime_seconds:.3f}s "
                f"metrics={list(a_res.metrics.keys())}"
            )

        lines += ["", "Aggregated Statistics", "-" * 30]
        lines.append(f"  Experiments: {stats.n_experiments}")
        lines.append(f"  Succeeded : {stats.n_succeeded}")
        lines.append(f"  Partial   : {stats.n_partial}")
        lines.append(f"  Failed    : {stats.n_failed}")

        if result.warnings:
            lines += ["", "Warnings", "-" * 30]
            for w in result.warnings:
                lines.append(f"  [WARN] {w}")

        if result.errors:
            lines += ["", "Errors", "-" * 30]
            for e in result.errors:
                lines.append(f"  [ERROR] {e}")

        lines.append("=" * 60)

        path = out_dir / "runtime_report.txt"
        path.write_text("\n".join(lines), encoding="utf-8")
        pkg.record(path)
        logger.debug("[ExportManager] Wrote %s", path.name)

    def _write_readme(
        self,
        out_dir: Path,
        result: ExperimentResult,
        metadata: ExperimentMetadata,
        stats: ExperimentStatistics,
        pkg: ExportPackage,
    ) -> None:
        em_line = (
            f"`{result.error_result.model_name}`"
            if result.error_result else "None (baseline)"
        )
        analysis_list = (
            "\n".join(f"- `{n}`" for n in metadata.analysis_names)
            or "- None"
        )
        lines = [
            f"# Experiment: {result.experiment_id}",
            "",
            "## Overview",
            "",
            f"| Field             | Value |",
            f"|---|---|",
            f"| Dataset           | `{result.dataset_name}` |",
            f"| Status            | `{result.status.value}` |",
            f"| Error Model       | {em_line} |",
            f"| Total Runtime     | {result.runtime_seconds:.3f}s |",
            f"| Started           | {result.started_at} |",
            f"| Finished          | {result.finished_at} |",
            f"| Framework Version | `{_FRAMEWORK_VERSION}` |",
            "",
            "## Analyses Run",
            "",
            analysis_list,
            "",
            "## Package Contents",
            "",
            "| File | Description |",
            "|---|---|",
            "| `metadata.json`        | Full experiment metadata |",
            "| `config_snapshot.yaml` | Configuration used for this run |",
            "| `summary.csv`          | Aggregated per-metric statistics |",
            "| `trial_results.csv`    | Per-trial analysis metrics |",
            "| `runtime_report.txt`   | Human-readable pipeline summary |",
            "| `logs/`                | Log files (populated at runtime) |",
            "| `plots/`               | Visualisations (generated by research modules) |",
            "",
            "## Reproducibility",
            "",
            "To reproduce this experiment, restore the configuration from "
            "`config_snapshot.yaml` and re-run with the same framework version "
            f"(`{_FRAMEWORK_VERSION}`) and seed (`{metadata.seed}`).",
            "",
        ]
        path = out_dir / "README.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        pkg.record(path)
        logger.debug("[ExportManager] Wrote %s", path.name)
