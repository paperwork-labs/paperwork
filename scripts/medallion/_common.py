"""Shared helpers for the parametric medallion scripts.

Track D of the Infra & Automation Hardening Sprint lifted these scripts
out of apis/axiomfolio/scripts/medallion/ so they can be invoked against
any backend via --app-dir. The per-app configuration lives in
scripts/medallion/apps.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = REPO_ROOT / "scripts" / "medallion" / "apps.yaml"

LAYER_ORDER = ("bronze", "silver", "gold", "execution", "ops")

# Import rules enforced by check_imports.py (must mirror the docstring in
# apps.yaml so humans reading either source see the same truth).
ALLOW: dict[str, set[str]] = {
    "bronze":    {"ops"},
    "silver":    {"bronze", "ops"},
    "gold":      {"silver", "bronze", "ops"},
    "execution": {"gold", "silver", "bronze", "ops"},
    "ops":       {"bronze", "silver", "gold", "execution", "ops"},
}


@dataclass(frozen=True)
class PortfolioSplit:
    parent: str
    default_layer: str
    bronze_patterns: tuple[str, ...]


@dataclass(frozen=True)
class AppConfig:
    name: str
    app_dir: Path
    services_root: Path
    import_prefix: str
    dir_layers: dict[str, str]
    portfolio_split: PortfolioSplit | None

    def classify(self, path: Path) -> str | None:
        """Return medallion layer for a .py file, or None to skip."""
        rel = path.relative_to(self.services_root).as_posix()
        top = rel.split("/", 1)[0]
        if "/" not in rel:
            return "ops"
        ps = self.portfolio_split
        if ps and top == ps.parent:
            if any(rel.startswith(p) or p in rel for p in ps.bronze_patterns):
                return "bronze"
            return ps.default_layer
        return self.dir_layers.get(top)


def load_config(app_name: str) -> AppConfig:
    """Load config for a single app by name from scripts/medallion/apps.yaml."""
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")
    data: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    apps = data.get("apps") or {}
    if app_name not in apps:
        raise KeyError(
            f"App '{app_name}' not found in {CONFIG_PATH}. "
            f"Known apps: {sorted(apps)}"
        )
    entry = apps[app_name]
    app_dir = REPO_ROOT / entry["app_dir"]
    services_root = app_dir / entry["services_root"]
    split_raw = entry.get("portfolio_split")
    split = (
        PortfolioSplit(
            parent=split_raw["parent"],
            default_layer=split_raw.get("default_layer", "silver"),
            bronze_patterns=tuple(split_raw.get("bronze_patterns", [])),
        )
        if split_raw
        else None
    )
    return AppConfig(
        name=app_name,
        app_dir=app_dir,
        services_root=services_root,
        import_prefix=entry["import_prefix"],
        dir_layers=dict(entry["dir_layers"]),
        portfolio_split=split,
    )


def resolve_app_name(app_dir_arg: str) -> str:
    """Map --app-dir filesystem hint (apis/brain) → app name (brain)."""
    data: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    apps = data.get("apps") or {}
    target = app_dir_arg.rstrip("/")
    for name, entry in apps.items():
        if entry.get("app_dir", "").rstrip("/") == target:
            return name
        if name == target:
            return name
    raise KeyError(
        f"No app entry in {CONFIG_PATH} matches --app-dir={app_dir_arg!r}. "
        f"Known apps: {sorted(apps)}"
    )
