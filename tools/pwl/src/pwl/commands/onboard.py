from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from pwl import find_monorepo_root
from pwl.app_inventory import build_onboard_report, render_markdown_report


def onboard(
    app_path: Annotated[Path, typer.Argument(help="Existing app path, e.g. apis/brain.")],
) -> None:
    """Inspect an existing monorepo app and report template conformance gaps."""
    console = Console()
    root = find_monorepo_root()
    if root is None:
        console.print("[red]Could not find a Paperwork monorepo root.[/red]")
        raise typer.Exit(1)

    try:
        report = build_onboard_report(root, app_path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]onboard failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(render_markdown_report(report), markup=False)
    if not report.is_conformant:
        raise typer.Exit(1)
