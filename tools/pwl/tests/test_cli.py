from typer.testing import CliRunner

from pwl.cli import app

runner = CliRunner()


def test_version_returns_output() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip()
    assert "pwl" in result.stdout


def test_list_apps_includes_brain() -> None:
    result = runner.invoke(app, ["list-apps"])

    assert result.exit_code == 0
    assert "brain" in result.stdout
