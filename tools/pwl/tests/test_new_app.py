from typer.testing import CliRunner

from pwl.cli import app

runner = CliRunner()


def test_new_app_stub_message() -> None:
    result = runner.invoke(app, ["new-app", "foo"])

    assert result.exit_code == 0
    assert "Would create apis/foo/ from template app_skeleton/api" in result.stdout
    assert "(stub) full implementation in WS-59" in result.stdout


def test_new_app_requires_name() -> None:
    result = runner.invoke(app, ["new-app"])

    assert result.exit_code == 2


def test_new_app_web_type_messages() -> None:
    result = runner.invoke(app, ["new-app", "foo", "--type", "web"])

    assert result.exit_code == 0
    assert "Would create apps/foo/ from template app_skeleton/web" in result.stdout
    assert "Would add Vercel project link" in result.stdout
