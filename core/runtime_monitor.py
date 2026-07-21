"""
Phase 009 – Runtime Monitor
============================
Records wall-clock time and peak RAM usage during an experiment pipeline run.

Responsibilities:
    - Sample current process RSS (resident set size) memory at checkpoints.
    - Track peak RAM seen during the monitored region.
    - Record wall-clock start/stop times.
    - Return a plain-dict summary that the Experiment Runner stores in
      ``ExperimentResult.peak_ram_mb`` and metadata.

Design constraints:
    - Uses only the standard library (``resource`` on POSIX, ``psutil``
      fallback if available, otherwise graceful degradation).
    - Never modifies any experiment object.
    - Never runs experiments or loads data.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _sample_ram_mb() -> float:
    """Return current process RSS in megabytes.

    Tries psutil first (more accurate cross-platform), then falls back to
    the ``resource`` module (POSIX-only), then returns 0.0 if neither
    is available.
    """
    try:
        import psutil
        import os
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except ImportError:
        pass

    try:
        import resource
        # getrusage returns peak RSS in kilobytes on Linux.
        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return kb / 1024.0
    except Exception:  # noqa: BLE001
        pass

    return 0.0


@dataclass
class RuntimeSnapshot:
    """A point-in-time snapshot of runtime metrics.

    Attributes:
        label:      Human-readable label for this checkpoint.
        elapsed_s:  Seconds elapsed since the monitor was started.
        ram_mb:     RAM usage in MB at this checkpoint.
    """
    label: str
    elapsed_s: float
    ram_mb: float


@dataclass
class RuntimeReport:
    """Summary of runtime metrics for one monitored region.

    Attributes:
        started_at:    Wall-clock start time (Unix epoch seconds).
        finished_at:   Wall-clock finish time.
        total_s:       Total elapsed seconds.
        peak_ram_mb:   Maximum RAM observed across all checkpoints.
        snapshots:     Ordered list of :class:`RuntimeSnapshot` objects.
    """
    started_at: float = 0.0
    finished_at: float = 0.0
    total_s: float = 0.0
    peak_ram_mb: float = 0.0
    snapshots: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain serialisable dict."""
        return {
            "started_at":  self.started_at,
            "finished_at": self.finished_at,
            "total_s":     self.total_s,
            "peak_ram_mb": self.peak_ram_mb,
            "snapshots": [
                {
                    "label":     s.label,
                    "elapsed_s": s.elapsed_s,
                    "ram_mb":    s.ram_mb,
                }
                for s in self.snapshots
            ],
        }


class RuntimeMonitor:
    """Lightweight runtime and memory monitor.

    Usage::

        monitor = RuntimeMonitor()
        monitor.start()
        monitor.checkpoint("after_load")
        monitor.checkpoint("after_build")
        report = monitor.stop()
        print(report.peak_ram_mb)
    """

    def __init__(self) -> None:
        self._t0: float = 0.0
        self._started: bool = False
        self._snapshots: list = []

    def start(self) -> None:
        """Begin monitoring."""
        self._t0 = time.perf_counter()
        self._started = True
        self._snapshots = []
        logger.debug("[RuntimeMonitor] Monitoring started.")

    def checkpoint(self, label: str) -> RuntimeSnapshot:
        """Record a labelled checkpoint.

        Args:
            label: Human-readable description of this checkpoint.

        Returns:
            The recorded :class:`RuntimeSnapshot`.
        """
        elapsed = time.perf_counter() - self._t0 if self._started else 0.0
        ram = _sample_ram_mb()
        snap = RuntimeSnapshot(label=label, elapsed_s=elapsed, ram_mb=ram)
        self._snapshots.append(snap)
        logger.debug(
            "[RuntimeMonitor] Checkpoint '%s': elapsed=%.2fs ram=%.1fMB",
            label, elapsed, ram,
        )
        return snap

    def stop(self) -> RuntimeReport:
        """Stop monitoring and return a :class:`RuntimeReport`.

        Returns:
            A :class:`RuntimeReport` with peak RAM, total time, and all
            checkpoints.
        """
        t_end = time.perf_counter()
        total = t_end - self._t0 if self._started else 0.0
        peak = max((s.ram_mb for s in self._snapshots), default=0.0)

        report = RuntimeReport(
            started_at=self._t0,
            finished_at=t_end,
            total_s=total,
            peak_ram_mb=peak,
            snapshots=list(self._snapshots),
        )

        self._started = False
        logger.debug(
            "[RuntimeMonitor] Stopped. total=%.2fs peak_ram=%.1fMB",
            total, peak,
        )
        return report
