from __future__ import annotations

import typer
from rich.console import Console

from pwl import find_monorepo_root
from pwl.app_inventory import write_registry


def registry_build() -> None:
    """Build Brain's monorepo app registry manifest."""
    console = Console()
    root = find_monorepo_root()
    if root is None:
        console.print("[red]Could not find a Paperwork monorepo root.[/red]")
        raise typer.Exit(1)

    try:
        path = write_registry(root)
    except (OSError, ValueError) as exc:
        console.print(f"[red]registry-build failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]wrote[/green] {path.relative_to(root)}")
