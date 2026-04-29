import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pwl import find_monorepo_root

PASS = "pass"
WARN = "warn"
FAIL = "fail"


def _run(command: list[str], root: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None


def _gh_status(root: Path | None) -> tuple[str, str]:
    if shutil.which("gh") is None:
        return WARN, "gh CLI is not installed"

    result = _run(["gh", "auth", "status"], root)
    if result is None or result.returncode != 0:
        return WARN, "gh CLI is installed but not authenticated"
    return PASS, "gh CLI is installed and authenticated"


def _binary_status(name: str) -> tuple[str, str]:
    if shutil.which(name) is None:
        return WARN, f"{name} is not installed"
    return PASS, f"{name} is installed"


def _env_status(root: Path) -> tuple[str, str]:
    env_files = sorted(root.glob("**/.env.example"))
    if not env_files:
        return WARN, "No .env.example files found"
    return PASS, f"Found {len(env_files)} .env.example file(s)"


def _merge_queue_status(root: Path) -> tuple[str, str]:
    path = root / "apis" / "brain" / "data" / "merge_queue.json"
    if not path.exists():
        return WARN, "Merge queue file is not present"

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return WARN, "Merge queue file is not valid JSON"

    queue = data.get("queue")
    if not isinstance(queue, list):
        return WARN, "Merge queue file has no queue list"
    if queue:
        return WARN, f"Merge queue has {len(queue)} item(s)"
    return PASS, "Merge queue is empty"


def _template_status() -> tuple[str, str]:
    main_template = resources.files("pwl.templates").joinpath(
        "app_skeleton",
        "api",
        "src",
        "${name_snake}",
        "main.py.tmpl",
    )
    try:
        content = main_template.read_text()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        return FAIL, f"API app skeleton template is missing: {exc}"

    if "FastAPI" not in content or "/healthz" not in content:
        return FAIL, "API app skeleton main.py.tmpl is not parseable"
    return PASS, "Found app_skeleton/api main.py.tmpl"


def _render(results: list[tuple[str, str, str]]) -> None:
    table = Table(title="pwl doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    colors = {PASS: "green", WARN: "yellow", FAIL: "red"}
    for name, status, detail in results:
        table.add_row(name, f"[{colors[status]}]{status}[/{colors[status]}]", detail)

    Console().print(table)


def doctor() -> None:
    """Run health checks against the current Paperwork monorepo."""
    root = find_monorepo_root()
    results: list[tuple[str, str, str]] = []

    if root is None:
        results.append(("monorepo", FAIL, "Missing .cursor/rules/ and apis/brain/ markers"))
        _render(results)
        raise typer.Exit(1)

    results.append(("monorepo", PASS, f"Paperwork monorepo at {root}"))
    results.append(("gh", *_gh_status(root)))
    results.append(("uv", *_binary_status("uv")))
    results.append(("pnpm", *_binary_status("pnpm")))
    results.append(("env files", *_env_status(root)))
    results.append(("merge queue", *_merge_queue_status(root)))
    results.append(("templates", *_template_status()))

    _render(results)
    if any(status == FAIL for _, status, _ in results):
        raise typer.Exit(1)
