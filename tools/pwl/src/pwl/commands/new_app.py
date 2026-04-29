from enum import StrEnum
from typing import Annotated

import typer
from rich.console import Console


class AppType(StrEnum):
    api = "api"
    web = "web"
    package = "package"


class Language(StrEnum):
    python = "python"
    typescript = "typescript"


def _target_path(name: str, app_type: AppType) -> str:
    if app_type is AppType.web:
        return f"apps/{name}/"
    if app_type is AppType.package:
        return f"packages/{name}/"
    return f"apis/{name}/"


def new_app(
    name: Annotated[str, typer.Argument(help="New app slug, e.g. mortgage-intake.")],
    app_type: Annotated[
        AppType,
        typer.Option("--type", help="Kind of Paperwork app to scaffold."),
    ] = AppType.api,
    language: Annotated[
        Language,
        typer.Option("--language", help="Primary language for the scaffold."),
    ] = Language.python,
) -> None:
    """Stub the L4 handoff flow for creating a new Paperwork app."""
    target = _target_path(name, app_type)
    Console().print(f"Would create {target} from template app_skeleton/{app_type.value}")
    Console().print(f"Would configure primary language: {language.value}")
    Console().print("Would add render.yaml service")
    Console().print("Would add Vercel project link")
    Console().print(
        f"Would add to apps/studio/src/data/workstreams.json as WS-XX-{name}-onboarding"
    )
    Console().print("Would open PR")
    Console().print("(stub) full implementation in WS-59")
