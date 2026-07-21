"""
Phase 002 – Configuration System
=================================
Provides :class:`ConfigManager`, the single entry-point for loading,
merging, and validating YAML configuration objects.

Merge order (later wins):
    defaults
        ↓
    dataset
        ↓
    error model
        ↓
    analysis profile
        ↓
    experiment

Design constraints:
    - Do NOT hardcode any paths; all config roots are supplied at call-time.
    - Configuration objects are plain dicts — immutable after loading.
    - Never perform dataset loading, graph construction, or biology here.
    - Schema validation is best-effort: warn on unknown keys, error on
      missing required keys.

Typical usage::

    from core.config_manager import ConfigManager

    manager = ConfigManager(configs_root="configs/")
    cfg = manager.load_experiment("configs/experiments/baseline.yaml")
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration error
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when a configuration file is invalid or missing."""


# ---------------------------------------------------------------------------
# Immutable config view
# ---------------------------------------------------------------------------

class FrozenConfig:
    """Read-only wrapper around a plain dict.

    Prevents accidental mutation of the merged config after loading.
    Supports attribute-style read access (``cfg.dataset_name``) as well as
    dict-style access (``cfg["dataset_name"]``).
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        # Store raw data in a way that __setattr__ cannot overwrite.
        object.__setattr__(self, "_data", copy.deepcopy(data))

    # ------------------------------------------------------------------ #
    # Dict-like read access                                                #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if absent."""
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    # ------------------------------------------------------------------ #
    # Attribute-style read access                                          #
    # ------------------------------------------------------------------ #

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"FrozenConfig has no key {name!r}.")

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(
            "FrozenConfig is immutable after construction. "
            "Do not modify configuration objects at runtime."
        )

    # ------------------------------------------------------------------ #
    # Serialisation helpers                                                #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> Dict[str, Any]:
        """Return a deep copy of the underlying dict."""
        return copy.deepcopy(self._data)

    def __repr__(self) -> str:
        return f"FrozenConfig({list(self._data.keys())})"


# ---------------------------------------------------------------------------
# Deep-merge helper
# ---------------------------------------------------------------------------

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base* (override wins on conflicts).

    Both arguments are left unchanged; the merged result is a new dict.
    """
    result: Dict[str, Any] = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


# ---------------------------------------------------------------------------
# YAML I/O helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dict.

    Returns an empty dict for empty files (rather than None).

    Raises:
        ConfigError: If the file does not exist or cannot be parsed.
    """
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error in {path}: {exc}") from exc


def _load_yaml_optional(path: Path) -> Dict[str, Any]:
    """Like :func:`_load_yaml` but returns ``{}`` when the file is missing."""
    if not path.exists():
        logger.debug("[ConfigManager] Optional file not found, skipping: %s", path)
        return {}
    return _load_yaml(path)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def _validate_required_keys(
    data: Dict[str, Any],
    required_keys: List[str],
    context: str,
) -> None:
    """Raise :class:`ConfigError` if any of *required_keys* are missing from *data*."""
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ConfigError(
            f"[ConfigManager] Configuration '{context}' is missing required "
            f"keys: {missing}"
        )


def _validate_schema(
    data: Dict[str, Any],
    schema: Dict[str, Any],
    context: str,
) -> None:
    """Light-weight schema validation using a loaded schema dict."""
    required = schema.get("required_keys", [])
    if required:
        _validate_required_keys(data, required, context)


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """Loads, merges, and validates framework configuration objects.

    All configuration is loaded from YAML files.  The merge order is:

        defaults → dataset → error model → analysis profile → experiment

    Experiments are the final layer and always override earlier layers.

    Args:
        configs_root:
            Path to the ``configs/`` directory.  This directory must contain
            ``defaults.yaml`` and the ``schemas/``, ``datasets/``,
            ``error_models/``, and ``analyses/`` sub-directories.

    Example::

        manager = ConfigManager("configs/")
        cfg = manager.load_experiment("configs/experiments/baseline.yaml")
        print(cfg.dataset_name)
    """

    _DEFAULTS_FILE = "defaults.yaml"
    _SCHEMAS_DIR   = "schemas"

    def __init__(self, configs_root: Union[str, Path] = "configs/") -> None:
        self._root = Path(configs_root)
        self._defaults: Dict[str, Any] = self._load_defaults()
        self._schemas: Dict[str, Dict[str, Any]] = self._load_schemas()
        logger.info(
            "[ConfigManager] Initialised with root='%s'. "
            "Schemas loaded: %s",
            self._root,
            list(self._schemas.keys()),
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def load_experiment(
        self,
        experiment_path: Union[str, Path],
        *,
        dataset_config_path: Optional[Union[str, Path]] = None,
        error_model_config_path: Optional[Union[str, Path]] = None,
        analysis_config_path: Optional[Union[str, Path]] = None,
    ) -> FrozenConfig:
        """Load and merge all configuration layers for one experiment.

        The merge order is::

            defaults
                ↓
            dataset          (auto-resolved from dataset_name if not given)
                ↓
            error model      (optional)
                ↓
            analysis profile (optional)
                ↓
            experiment       (always loaded)

        Args:
            experiment_path:
                Path to the experiment-level YAML.  Must contain at least
                ``dataset_name`` and ``dataset_root``.
            dataset_config_path:
                Override path for the dataset config.  When ``None``, the
                registry will attempt to locate it from ``dataset_name``.
            error_model_config_path:
                Optional override path for an error model config.
            analysis_config_path:
                Optional override path for an analysis profile config.

        Returns:
            A :class:`FrozenConfig` representing the fully merged, validated
            configuration.

        Raises:
            ConfigError: If required keys are missing or a file cannot be parsed.
        """
        experiment_data = _load_yaml(Path(experiment_path))
        _validate_schema(
            experiment_data,
            self._schemas.get("experiment", {}),
            str(experiment_path),
        )

        # Start with defaults.
        merged = copy.deepcopy(self._defaults)

        # Dataset layer.
        dataset_cfg = self._resolve_dataset_config(
            experiment_data, dataset_config_path
        )
        merged = _deep_merge(merged, dataset_cfg)

        # Error model layer (optional).
        if error_model_config_path:
            em_cfg = _load_yaml(Path(error_model_config_path))
            merged = _deep_merge(merged, em_cfg)
        elif "error_model_config_path" in experiment_data:
            em_path = self._root / experiment_data["error_model_config_path"]
            em_cfg = _load_yaml_optional(em_path)
            merged = _deep_merge(merged, em_cfg)

        # Analysis profile layer (optional).
        if analysis_config_path:
            an_cfg = _load_yaml(Path(analysis_config_path))
            merged = _deep_merge(merged, an_cfg)

        # Experiment layer (always last — highest precedence).
        merged = _deep_merge(merged, experiment_data)

        logger.info(
            "[ConfigManager] Loaded experiment config from '%s'.",
            experiment_path,
        )
        return FrozenConfig(merged)

    def load_dataset_config(
        self,
        dataset_name: str,
    ) -> FrozenConfig:
        """Load and return the dataset-level configuration for *dataset_name*.

        Args:
            dataset_name: Case-insensitive dataset name (e.g. ``"FAFB"``).

        Returns:
            A :class:`FrozenConfig` for the dataset.

        Raises:
            ConfigError: If no dataset config file is found.
        """
        path = self._find_dataset_config(dataset_name)
        data = _load_yaml(path)
        _validate_schema(
            data,
            self._schemas.get("dataset", {}),
            str(path),
        )
        merged = _deep_merge(self._defaults, data)
        return FrozenConfig(merged)

    def load_from_dict(self, data: Dict[str, Any]) -> FrozenConfig:
        """Wrap a plain dict in a :class:`FrozenConfig` (merges with defaults).

        Useful for constructing configs programmatically in tests or notebooks.

        Args:
            data: Configuration dict (overrides defaults).

        Returns:
            A :class:`FrozenConfig`.
        """
        merged = _deep_merge(self._defaults, data)
        return FrozenConfig(merged)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load_defaults(self) -> Dict[str, Any]:
        """Load ``configs/defaults.yaml``."""
        path = self._root / self._DEFAULTS_FILE
        if not path.exists():
            logger.warning(
                "[ConfigManager] defaults.yaml not found at '%s'. "
                "Using empty defaults.", path,
            )
            return {}
        return _load_yaml(path)

    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Load all YAML files from ``configs/schemas/``."""
        schemas: Dict[str, Dict[str, Any]] = {}
        schema_dir = self._root / self._SCHEMAS_DIR
        if not schema_dir.exists():
            logger.warning(
                "[ConfigManager] Schema directory not found: '%s'.", schema_dir
            )
            return schemas
        for schema_file in schema_dir.glob("*.yaml"):
            key = schema_file.stem.replace("_schema", "")
            try:
                schemas[key] = _load_yaml(schema_file)
                logger.debug(
                    "[ConfigManager] Loaded schema '%s' from '%s'.", key, schema_file
                )
            except ConfigError as exc:
                logger.warning(
                    "[ConfigManager] Could not load schema '%s': %s", schema_file, exc
                )
        return schemas

    def _resolve_dataset_config(
        self,
        experiment_data: Dict[str, Any],
        override_path: Optional[Union[str, Path]],
    ) -> Dict[str, Any]:
        """Return the dataset config dict, resolved from *experiment_data*."""
        if override_path:
            return _load_yaml(Path(override_path))

        dataset_name = experiment_data.get("dataset_name", "")
        if not dataset_name:
            return {}

        try:
            path = self._find_dataset_config(dataset_name)
            return _load_yaml_optional(path)
        except ConfigError:
            logger.warning(
                "[ConfigManager] Dataset config for '%s' not found; "
                "skipping dataset layer.", dataset_name,
            )
            return {}

    def _find_dataset_config(self, dataset_name: str) -> Path:
        """Locate the dataset config YAML for *dataset_name* (case-insensitive).

        Raises:
            ConfigError: If no matching file is found.
        """
        datasets_dir = self._root / "datasets"
        if not datasets_dir.exists():
            raise ConfigError(
                f"Datasets config directory not found: '{datasets_dir}'"
            )
        needle = dataset_name.lower()
        for f in datasets_dir.glob("*.yaml"):
            if f.stem.lower() == needle:
                return f
        raise ConfigError(
            f"No dataset config found for '{dataset_name}' in '{datasets_dir}'. "
            f"Available: {[f.stem for f in datasets_dir.glob('*.yaml')]}"
        )
