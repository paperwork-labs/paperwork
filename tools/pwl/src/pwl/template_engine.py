from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from string import Template


def _to_snake(name: str) -> str:
    return name.replace("-", "_")


def _to_pascal(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("-"))


def compute_context(name: str, author: str | None = None) -> dict[str, str]:
    """Compute template variables for a Paperwork app scaffold."""
    return {
        "name": name,
        "name_snake": _to_snake(name),
        "name_pascal": _to_pascal(name),
        "author": author or "Paperwork Labs",
        "year": str(datetime.now(UTC).year),
    }


def _render_relative_path(path: Path, context: dict[str, str]) -> Path:
    rendered_parts: list[str] = []
    for part in path.parts:
        output_part = part.removesuffix(".tmpl")
        rendered_parts.append(Template(output_part).substitute(context))
    return Path(*rendered_parts)


def render_template_tree(src: Path, dst: Path, context: dict[str, str]) -> None:
    """Render a template tree into dst using string.Template substitution."""
    if not src.is_dir():
        raise FileNotFoundError(f"Template directory not found: {src}")
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {dst}")

    for source_path in sorted(src.rglob("*")):
        relative_path = source_path.relative_to(src)
        target_path = dst / _render_relative_path(relative_path, context)

        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix == ".tmpl":
            rendered = Template(source_path.read_text()).substitute(context)
            target_path.write_text(rendered)
        else:
            shutil.copyfile(source_path, target_path)
