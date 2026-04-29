import json
from pathlib import Path

from typer.testing import CliRunner

from pwl.cli import app

runner = CliRunner()


def _make_monorepo(root: Path) -> None:
    (root / ".cursor" / "rules").mkdir(parents=True)
    (root / "apis" / "brain").mkdir(parents=True)
    (root / "apps" / "studio" / "src" / "data").mkdir(parents=True)
    (root / "render.yaml").write_text("services:\n")
    (root / "apps" / "studio" / "src" / "data" / "workstreams.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated": "2026-04-28T00:00:00Z",
                "workstreams": [
                    {
                        "id": "WS-58-pwl-cli",
                        "title": "pwl CLI",
                        "track": "Z",
                        "priority": 0,
                        "status": "completed",
                        "percent_done": 100,
                        "owner": "brain",
                        "brief_tag": "track:pwl-cli",
                        "blockers": [],
                        "last_pr": 388,
                        "last_activity": "2026-04-28T00:00:00Z",
                        "last_dispatched_at": None,
                        "notes": "CLI shell landed.",
                        "estimated_pr_count": 1,
                        "github_actions_workflow": None,
                        "related_plan": "level_4_autonomy_+_platform",
                    }
                ],
            }
        )
        + "\n"
    )


def _load_workstreams(root: Path) -> list[dict[str, object]]:
    path = root / "apps" / "studio" / "src" / "data" / "workstreams.json"
    data = json.loads(path.read_text())
    return data["workstreams"]


def _assert_workstream_schema(root: Path) -> None:
    workstreams = _load_workstreams(root)
    priorities = [item["priority"] for item in workstreams]
    assert len(priorities) == len(set(priorities))
    for item in workstreams:
        assert str(item["id"]).startswith("WS-")
        assert len(str(item["title"])) <= 100
        assert item["status"] in {"pending", "in_progress", "blocked", "completed", "cancelled"}
        assert isinstance(item["blockers"], list)
        if item["status"] == "completed":
            assert item["percent_done"] == 100


def test_new_app_renders_template_tree(tmp_path, monkeypatch) -> None:
    _make_monorepo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-app", "foo"])

    assert result.exit_code == 0
    expected_files = [
        "pyproject.toml",
        "README.md",
        "Dockerfile",
        ".gitignore",
        ".python-version",
        "src/foo/__init__.py",
        "src/foo/main.py",
        "src/foo/config.py",
        "tests/test_healthz.py",
        "alembic.ini",
        "alembic/env.py",
        "alembic/versions/.gitkeep",
    ]
    for relative_path in expected_files:
        assert (tmp_path / "apis" / "foo" / relative_path).exists()
    assert (
        'SERVICE_NAME = "foo"'
        in (tmp_path / "apis" / "foo" / "src" / "foo" / "main.py").read_text()
    )


def test_new_app_requires_name() -> None:
    result = runner.invoke(app, ["new-app"])

    assert result.exit_code == 2


def test_new_app_validates_name(tmp_path, monkeypatch) -> None:
    _make_monorepo(tmp_path)
    monkeypatch.chdir(tmp_path)

    for name in ["Foo", "ab", "1foo", "foo_bar", "a" * 42]:
        result = runner.invoke(app, ["new-app", name])

        assert result.exit_code == 2


def test_new_app_refuses_overwrite_existing(tmp_path, monkeypatch) -> None:
    _make_monorepo(tmp_path)
    (tmp_path / "apis" / "foo").mkdir()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-app", "foo"])

    assert result.exit_code == 1
    assert "already exists" in result.stdout


def test_new_app_substitutes_variables(tmp_path, monkeypatch) -> None:
    _make_monorepo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-app", "my-api"])

    assert result.exit_code == 0
    package_root = tmp_path / "apis" / "my-api" / "src" / "my_api"
    assert package_root.exists()
    assert "my_api.main:app" in (tmp_path / "apis" / "my-api" / "Dockerfile").read_text()
    assert "MyApi API" in (package_root / "main.py").read_text()
    assert 'paperwork_service_up{service="my-api"} 1' in (package_root / "main.py").read_text()


def test_new_app_appends_render_service(tmp_path, monkeypatch) -> None:
    _make_monorepo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-app", "foo"])

    assert result.exit_code == 0
    render_yaml = (tmp_path / "render.yaml").read_text()
    assert render_yaml.count("type: web") == 1
    assert "name: foo" in render_yaml
    assert "cd apis/foo && pip install ." in render_yaml
    assert "gunicorn foo.main:app" in render_yaml


def test_new_app_appends_workstream_entry(tmp_path, monkeypatch) -> None:
    _make_monorepo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-app", "foo"])

    assert result.exit_code == 0
    workstreams = _load_workstreams(tmp_path)
    assert len(workstreams) == 2
    assert workstreams[-1]["id"] == "WS-59-foo-onboarding"
    assert workstreams[-1]["status"] == "pending"
    assert workstreams[-1]["priority"] == 1
    _assert_workstream_schema(tmp_path)


def test_new_app_dry_run_does_not_write(tmp_path, monkeypatch) -> None:
    _make_monorepo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["new-app", "foo", "--dry-run"])

    assert result.exit_code == 0
    assert "DRY RUN" in result.stdout
    assert not (tmp_path / "apis" / "foo").exists()
