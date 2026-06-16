"""Strategy discovery — find and instantiate strategies by slug or family.

Works in both development (uv workspace) and installed (pip) layouts by
using importlib/pkgutil to walk the ``alphakit.strategies`` namespace
package rather than hardcoding filesystem paths.

Each strategy sub-module must contain:
  - __init__.py exporting the strategy class
  - strategy.py with the implementation
  - config.yaml with universe, parameters, and rebalance frequency
"""

from __future__ import annotations

import importlib
import importlib.resources
import pkgutil
from pathlib import Path
from typing import Any

import yaml
from alphakit.core.protocols import StrategyProtocol

FAMILIES = (
    "trend",
    "meanrev",
    "carry",
    "value",
    "volatility",
    "rates",
    "commodity",
    "options",
    "macro",
)


def _family_module(family: str) -> Any:
    """Import ``alphakit.strategies.{family}`` or return None."""
    try:
        return importlib.import_module(f"alphakit.strategies.{family}")
    except ImportError:
        return None


def _strategy_dirs() -> list[tuple[str, str, Path]]:
    """Return (family, slug, path) for every installed strategy.

    Uses pkgutil.iter_modules on each family's ``__path__`` to discover
    strategy sub-packages. This works in both workspace-dev and pip-installed
    layouts because Python sets ``__path__`` correctly in both cases.
    """
    results: list[tuple[str, str, Path]] = []
    for family in FAMILIES:
        fam_mod = _family_module(family)
        if fam_mod is None:
            continue
        for _importer, slug, ispkg in pkgutil.iter_modules(fam_mod.__path__):
            if not ispkg:
                continue
            # Verify this sub-package has a strategy.py
            slug_mod_path = f"alphakit.strategies.{family}.{slug}"
            try:
                slug_mod = importlib.import_module(slug_mod_path)
            except ImportError:
                continue
            # Get the filesystem path from the module's __path__ or __file__
            if hasattr(slug_mod, "__path__"):
                pkg_path = Path(slug_mod.__path__[0])
            elif hasattr(slug_mod, "__file__") and slug_mod.__file__:
                pkg_path = Path(slug_mod.__file__).parent
            else:
                continue
            if (pkg_path / "strategy.py").exists():
                results.append((family, slug, pkg_path))
    return results


def discover_slugs(family: str | None = None) -> list[str]:
    """Return all strategy slugs, optionally filtered by family."""
    return [slug for fam, slug, _ in _strategy_dirs() if family is None or fam == family]


def load_config(family: str, slug: str) -> dict[str, Any]:
    """Load a strategy's config.yaml as a dict.

    Locates the config file via the installed module's ``__path__`` rather
    than hardcoding a monorepo layout.
    """
    mod_path = f"alphakit.strategies.{family}.{slug}"
    try:
        mod = importlib.import_module(mod_path)
    except ImportError as exc:
        raise FileNotFoundError(f"Cannot import {mod_path} to locate config.yaml") from exc

    if hasattr(mod, "__path__"):
        config_path = Path(mod.__path__[0]) / "config.yaml"
    elif hasattr(mod, "__file__") and mod.__file__:
        config_path = Path(mod.__file__).parent / "config.yaml"
    else:
        raise FileNotFoundError(f"Cannot determine path for {mod_path}")

    if not config_path.exists():
        raise FileNotFoundError(f"No config.yaml for {family}/{slug} at {config_path}")
    with open(config_path) as f:
        return dict(yaml.safe_load(f))


def instantiate(family: str, slug: str) -> StrategyProtocol:
    """Import and instantiate a strategy by family and slug.

    Imports from ``alphakit.strategies.{family}.{slug}`` and finds the
    first exported class that satisfies StrategyProtocol.
    """
    module_path = f"alphakit.strategies.{family}.{slug}"
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        raise ImportError(f"Cannot import strategy {family}/{slug}: {exc}") from exc

    # Find the strategy class from __all__
    for name in getattr(mod, "__all__", []):
        cls = getattr(mod, name, None)
        if cls is not None and isinstance(cls, type):
            instance = cls()
            if isinstance(instance, StrategyProtocol):
                return instance
    raise RuntimeError(f"No StrategyProtocol-conforming class found in {module_path}.__all__")


def find_strategy(slug: str) -> tuple[str, str]:
    """Find the family for a given slug. Returns (family, slug)."""
    for family, s, _ in _strategy_dirs():
        if s == slug:
            return (family, s)
    raise KeyError(f"Strategy slug '{slug}' not found in any family")


def benchmark_results_path(family: str, slug: str) -> Path:
    """Return the path to a strategy's benchmark_results.json.

    Locates the file via the installed module's path, so it works in
    both workspace-dev and pip-installed layouts.
    """
    mod_path = f"alphakit.strategies.{family}.{slug}"
    try:
        mod = importlib.import_module(mod_path)
    except ImportError as exc:
        raise FileNotFoundError(
            f"Cannot import {mod_path} to locate benchmark_results.json"
        ) from exc

    if hasattr(mod, "__path__"):
        return Path(mod.__path__[0]) / "benchmark_results.json"
    if hasattr(mod, "__file__") and mod.__file__:
        return Path(mod.__file__).parent / "benchmark_results.json"
    raise FileNotFoundError(f"Cannot determine path for {mod_path}")
