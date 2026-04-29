import subprocess
from importlib import metadata
from pathlib import Path

from rich.console import Console

from pwl import __version__, find_monorepo_root


def _installed_version() -> str:
    try:
        return metadata.version("pwl")
    except metadata.PackageNotFoundError:
        return __version__


def _git_short_sha(root: Path | None) -> str:
    if root is None:
        return "unknown"

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"

    return result.stdout.strip() or "unknown"


def version() -> None:
    """Print the pwl version and current git short SHA."""
    root = find_monorepo_root()
    Console().print(f"pwl {_installed_version()} ({_git_short_sha(root)})")
