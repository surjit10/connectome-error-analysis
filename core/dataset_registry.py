"""
Phase 003 – Dataset Registry
==============================
Provides :class:`DatasetRegistry`, the central catalogue of all known
FlyWire dataset configurations.

Responsibilities:
    - Register dataset metadata from ``configs/datasets/`` YAML files.
    - Resolve the concrete filesystem path to a dataset folder.
    - Provide a clean lookup API so the Data Loader never contains
      path-resolution logic.

Design constraints:
    - Never parses CSV files.
    - Never builds graphs.
    - Returns only validated paths and metadata.
    - No caching — path resolution is always performed fresh on request.

Typical usage::

    from core.dataset_registry import DatasetRegistry

    registry = DatasetRegistry(configs_root="configs/", dataset_root="/data/raw")
    info = registry.lookup("FAFB")
    # info.dataset_dir is a resolved Path to the dataset folder
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry error
# ---------------------------------------------------------------------------

class DatasetRegistryError(Exception):
    """Raised when a dataset cannot be registered or resolved."""


# ---------------------------------------------------------------------------
# Dataset Info container
# ---------------------------------------------------------------------------

@dataclass
class DatasetInfo:
    """All information the Data Loader needs about one registered dataset.

    Attributes:
        name:             Canonical dataset name (e.g. ``"FAFB"``).
        version:          Version string from config.
        dataset_dir:      Resolved :class:`pathlib.Path` to the dataset folder.
        is_fafb:          Whether special FAFB multi-file loading is required.
        files:            Mapping of logical file role to filename within
                          *dataset_dir* (e.g. ``{"neurons": "neurons.csv.gz"}``).
        required_neuron_columns:     Column names that must exist after loading.
        required_connection_columns: Column names that must exist after loading.
        extra:            Any additional keys from the config YAML.
    """

    name: str
    version: str = ""
    dataset_dir: Optional[Path] = None
    is_fafb: bool = False
    files: Dict[str, str] = field(default_factory=dict)
    required_neuron_columns: List[str] = field(default_factory=list)
    required_connection_columns: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def neuron_file(self) -> Optional[Path]:
        """Return the resolved path to the neurons file (or ``None``)."""
        fname = self.files.get("neurons")
        if fname and self.dataset_dir:
            return self.dataset_dir / fname
        return None

    def connections_file(self) -> Optional[Path]:
        """Return the resolved path to the connections file (or ``None``)."""
        fname = self.files.get("connections")
        if fname and self.dataset_dir:
            return self.dataset_dir / fname
        return None

    def classification_file(self) -> Optional[Path]:
        """Return the resolved path to the FAFB classification file."""
        fname = self.files.get("classification")
        if fname and self.dataset_dir:
            return self.dataset_dir / fname
        return None

    def cell_types_file(self) -> Optional[Path]:
        """Return the resolved path to the FAFB consolidated_cell_types file."""
        fname = self.files.get("cell_types")
        if fname and self.dataset_dir:
            return self.dataset_dir / fname
        return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class DatasetRegistry:
    """Central catalogue of FlyWire dataset configurations.

    On construction the registry scans ``configs/datasets/`` and loads all
    dataset YAML files it finds.  It then resolves each dataset's folder
    inside *dataset_root*.

    Args:
        configs_root:
            Path to the ``configs/`` directory.
        dataset_root:
            Root directory under which per-dataset folders live.
            Pass ``None`` to defer resolution (useful for metadata-only
            lookups where filesystem access is not needed).

    Example::

        registry = DatasetRegistry("configs/", "/data/raw")
        info = registry.lookup("FAFB")
        loader.load(info)
    """

    def __init__(
        self,
        configs_root: Union[str, Path] = "configs/",
        dataset_root: Optional[Union[str, Path]] = None,
    ) -> None:
        self._configs_root = Path(configs_root)
        self._dataset_root = Path(dataset_root) if dataset_root else None
        self._registry: Dict[str, DatasetInfo] = {}
        self._load_all_datasets()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def lookup(self, name: str) -> DatasetInfo:
        """Return the :class:`DatasetInfo` for *name*.

        Args:
            name: Case-insensitive dataset name (e.g. ``"FAFB"``).

        Returns:
            A :class:`DatasetInfo` with ``dataset_dir`` resolved when
            *dataset_root* was supplied.

        Raises:
            DatasetRegistryError: If *name* is not registered.
        """
        key = name.upper()
        if key not in self._registry:
            raise DatasetRegistryError(
                f"Dataset '{name}' is not registered. "
                f"Available datasets: {self.list_names()}"
            )
        return self._registry[key]

    def is_registered(self, name: str) -> bool:
        """Return ``True`` if a dataset named *name* is registered."""
        return name.upper() in self._registry

    def list_names(self) -> List[str]:
        """Return a sorted list of all registered dataset names."""
        return sorted(self._registry.keys())

    def resolve_dataset_dir(
        self, name: str, dataset_root: Union[str, Path]
    ) -> Path:
        """Locate the dataset's subfolder within *dataset_root*.

        The subfolder is identified by matching the dataset name prefix
        against the names of directories inside *dataset_root*.

        Args:
            name:         Dataset name.
            dataset_root: Root directory that contains dataset folders.

        Returns:
            Resolved :class:`pathlib.Path` to the dataset folder.

        Raises:
            DatasetRegistryError: If no matching folder is found.
        """
        root = Path(dataset_root)
        needle = name.upper()
        for folder in root.iterdir():
            if folder.is_dir() and folder.name.upper().startswith(f"{needle}_"):
                return folder
        # Fallback: exact name match.
        candidate = root / needle
        if candidate.is_dir():
            return candidate
        raise DatasetRegistryError(
            f"No dataset directory found for '{name}' in '{root}'. "
            f"Expected a directory starting with '{needle}_'."
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load_all_datasets(self) -> None:
        """Scan ``configs/datasets/`` and register every YAML found."""
        datasets_dir = self._configs_root / "datasets"
        if not datasets_dir.exists():
            logger.warning(
                "[DatasetRegistry] Dataset config directory not found: '%s'.",
                datasets_dir,
            )
            return

        for yaml_path in sorted(datasets_dir.glob("*.yaml")):
            try:
                self._load_dataset_yaml(yaml_path)
            except DatasetRegistryError as exc:
                logger.warning(
                    "[DatasetRegistry] Skipping '%s': %s", yaml_path, exc
                )

    def _load_dataset_yaml(self, yaml_path: Path) -> None:
        """Parse one dataset YAML and add it to the registry."""
        try:
            with yaml_path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise DatasetRegistryError(
                f"YAML parse error in '{yaml_path}': {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise DatasetRegistryError(
                f"Dataset config '{yaml_path}' is empty or not a mapping."
            )

        name = data.get("name")
        if not name:
            raise DatasetRegistryError(
                f"Dataset config '{yaml_path}' is missing required key 'name'."
            )

        canonical_name = str(name).upper()

        # Resolve dataset directory if we have a root.
        dataset_dir: Optional[Path] = None
        if self._dataset_root is not None:
            try:
                dataset_dir = self.resolve_dataset_dir(
                    canonical_name, self._dataset_root
                )
            except DatasetRegistryError:
                # Directory may not exist yet (e.g. in CI or testing).
                logger.debug(
                    "[DatasetRegistry] Dataset directory for '%s' not found "
                    "under '%s'; dataset_dir will be None.",
                    canonical_name, self._dataset_root,
                )

        known_keys = {
            "name", "version", "description", "is_fafb", "files",
            "required_neuron_columns", "required_connection_columns",
        }
        extra = {k: v for k, v in data.items() if k not in known_keys}

        info = DatasetInfo(
            name=canonical_name,
            version=str(data.get("version", "")),
            dataset_dir=dataset_dir,
            is_fafb=bool(data.get("is_fafb", False)),
            files=dict(data.get("files", {})),
            required_neuron_columns=list(
                data.get("required_neuron_columns", [])
            ),
            required_connection_columns=list(
                data.get("required_connection_columns", [])
            ),
            extra=extra,
        )

        self._registry[canonical_name] = info
        logger.info(
            "[DatasetRegistry] Registered dataset '%s' v%s (dir=%s).",
            canonical_name, info.version, dataset_dir,
        )

    def __len__(self) -> int:
        return len(self._registry)

    def __repr__(self) -> str:
        return f"DatasetRegistry(datasets={self.list_names()})"
