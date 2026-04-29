from pathlib import Path

__version__ = "0.1.0"


def find_monorepo_root(start: Path | None = None) -> Path | None:
    """Return the nearest Paperwork monorepo root, if the current tree has one."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".cursor" / "rules").is_dir() and (candidate / "apis" / "brain").is_dir():
            return candidate
    return None
