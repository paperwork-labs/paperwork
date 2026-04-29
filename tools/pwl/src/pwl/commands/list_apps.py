import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pwl import find_monorepo_root


def _language_for(path: Path) -> str:
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        return "python"
    if (path / "package.json").exists() or (path / "tsconfig.json").exists():
        return "typescript"
    return "unknown"


def _last_commit_date(root: Path, path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path.relative_to(root))],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, ValueError):
        return "unknown"

    return result.stdout.strip() or "unknown"


def _freshness_badge(commit_date: str) -> str:
    if commit_date == "unknown":
        return "unknown"

    try:
        committed = date.fromisoformat(commit_date)
    except ValueError:
        return "unknown"

    age_days = (datetime.now(UTC).date() - committed).days
    if age_days <= 30:
        return f"fresh ({commit_date})"
    if age_days <= 180:
        return f"warm ({commit_date})"
    return f"stale ({commit_date})"


def _iter_entries(root: Path) -> list[tuple[str, str, Path]]:
    entries: list[tuple[str, str, Path]] = []
    for parent_name, app_type in (("apis", "api"), ("apps", "web"), ("packages", "package")):
        parent = root / parent_name
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            if child.is_dir() and not child.name.startswith("_"):
                entries.append((child.name, app_type, child))
    return entries


def list_apps() -> None:
    """List Paperwork apps, APIs, and packages with freshness metadata."""
    root = find_monorepo_root()
    if root is None:
        Console().print("[red]Not inside a Paperwork monorepo.[/red]")
        raise typer.Exit(1)

    table = Table(title="Paperwork apps")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Language")
    table.add_column("Freshness")

    for name, app_type, path in _iter_entries(root):
        commit_date = _last_commit_date(root, path)
        table.add_row(name, app_type, _language_for(path), _freshness_badge(commit_date))

    Console().print(table)
