import json

from typer.testing import CliRunner

from pwl import find_monorepo_root
from pwl.app_inventory import REGISTRY_RELATIVE_PATH
from pwl.cli import app

runner = CliRunner()


def _registry_path() -> str:
    root = find_monorepo_root()
    assert root is not None
    return str(root / REGISTRY_RELATIVE_PATH)


def test_registry_build_writes_parseable_json() -> None:
    result = runner.invoke(app, ["registry-build"])

    assert result.exit_code == 0
    with open(_registry_path(), encoding="utf-8") as fp:
        data = json.load(fp)
    assert data["schema"] == "app_registry/v1"
    assert data["generated_by"] == "pwl registry-build"
    assert isinstance(data["apps"], list)


def test_registry_schema_has_required_app_keys() -> None:
    result = runner.invoke(app, ["registry-build"])

    assert result.exit_code == 0
    with open(_registry_path(), encoding="utf-8") as fp:
        data = json.load(fp)
    first = data["apps"][0]
    for key in (
        "name",
        "path",
        "type",
        "framework",
        "language",
        "conformance",
        "size_signals",
        "last_modified",
        "depends_on_services",
    ):
        assert key in first


def test_registry_includes_core_apps_when_present() -> None:
    result = runner.invoke(app, ["registry-build"])

    assert result.exit_code == 0
    with open(_registry_path(), encoding="utf-8") as fp:
        data = json.load(fp)
    names = {app["name"] for app in data["apps"]}
    assert {"brain", "axiomfolio", "studio"}.issubset(names)
