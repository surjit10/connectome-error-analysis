"""
presentation/base_exporter.py
==============================
Shared base class for all presentation exporters.

Provides common utilities for directory creation, JSON/CSV writing, and
Jinja2 HTML template rendering.

Design constraints:
    - No statistical computation.
    - No figure generation.
    - Only file I/O and HTML rendering.
    - All subclasses must pass pre-computed data objects — never raw
      ExperimentResult or analysis objects.
"""
from __future__ import annotations

import csv
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Path to the templates directory (sibling to this file)
_TEMPLATES_DIR = Path(__file__).parent / "templates"


class BaseExporter:
    """Abstract base exporter with shared I/O utilities.

    Args:
        output_dir: The target directory for this exporter's output.
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    # ------------------------------------------------------------------ #
    # Directory helpers                                                    #
    # ------------------------------------------------------------------ #

    def _ensure_dirs(self, *dirs: Path) -> None:
        """Create one or more directories (including parents) if absent."""
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # JSON / CSV                                                           #
    # ------------------------------------------------------------------ #

    def _write_json(self, data: Any, path: Path) -> None:
        """Serialise *data* as pretty-printed JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug("[%s] Wrote %s", self.__class__.__name__, path)

    def _write_csv(
        self,
        rows: List[Dict[str, Any]],
        fieldnames: Sequence[str],
        path: Path,
    ) -> None:
        """Write *rows* to a CSV file with the given *fieldnames* header."""
        if not rows:
            logger.debug("[%s] Skipping empty CSV: %s", self.__class__.__name__, path)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        logger.debug("[%s] Wrote %s (%d rows)", self.__class__.__name__, path, len(rows))

    # ------------------------------------------------------------------ #
    # HTML rendering                                                       #
    # ------------------------------------------------------------------ #

    def _render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        output_path: Path,
    ) -> None:
        """Render a Jinja2 template to *output_path*.

        Args:
            template_name: Filename of the template (e.g. ``"trend_report.html"``).
            context:       Template variables.
            output_path:   Destination file path.
        """
        context.setdefault(
            "generated_at",
            datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        )
        template = self._jinja_env.get_template(template_name)
        html = template.render(**context)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.debug("[%s] Rendered %s → %s", self.__class__.__name__, template_name, output_path)

    # ------------------------------------------------------------------ #
    # Path helpers                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rel_root(from_dir: Path, results_root: Path) -> str:
        """Return a relative ``../../../`` path from *from_dir* to *results_root*."""
        try:
            rel = from_dir.relative_to(results_root)
            depth = len(rel.parts)
            return "../" * depth if depth > 0 else ""
        except ValueError:
            return ""
