from typer.testing import CliRunner

from pwl.cli import app

runner = CliRunner()


def test_onboard_brain_reports_markers() -> None:
    result = runner.invoke(app, ["onboard", "apis/brain"])

    assert "| marker | required | present | gap |" in result.stdout
    assert "type: `python-api`" in result.stdout
    assert "framework: `FastAPI`" in result.stdout
    assert "pyproject.toml" in result.stdout
    assert "medallion comment" in result.stdout


def test_onboard_nonexistent_app_exits_nonzero() -> None:
    result = runner.invoke(app, ["onboard", "nonexistent/app"])

    assert result.exit_code != 0
    assert "does not exist" in result.stdout


def test_onboard_package_ui_detects_package_and_node_language() -> None:
    result = runner.invoke(app, ["onboard", "packages/ui"])

    assert "type: `package`" in result.stdout
    assert "language: `typescript`" in result.stdout
    assert "package.json" in result.stdout
