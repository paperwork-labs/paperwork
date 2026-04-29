from typer.testing import CliRunner

from pwl.cli import app

runner = CliRunner()


def test_doctor_returns_zero_in_monorepo() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "monorepo" in result.stdout


def test_doctor_returns_one_outside_monorepo(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Missing .cursor/rules/ and apis/brain/ markers" in result.stdout
