"""Tests for ``app.utils.paths`` — canonical path resolution.

This module is the single source of truth for resolving Brain paths in both
the repo (``<repo>/apis/brain/...``) and container (``/app/...``) layouts.
The Wave 0 incident was a ``parents[4]`` IndexError in
``probe_failure_dispatcher`` because the file was at a different depth in the
container than in the repo. These tests pin the contract so the same class of
bug can't regress.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.utils import paths as paths_mod


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_ROOT", raising=False)
    monkeypatch.delenv("BRAIN_DATA_DIR", raising=False)
    monkeypatch.delenv("REPO_ROOT", raising=False)


def test_brain_root_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "fake-brain"
    target.mkdir()
    monkeypatch.setenv("BRAIN_ROOT", str(target))
    assert paths_mod.brain_root() == target


def test_brain_data_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "data-override"
    target.mkdir()
    monkeypatch.setenv("BRAIN_DATA_DIR", str(target))
    assert paths_mod.brain_data_dir() == target


def test_repo_root_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "monorepo"
    target.mkdir()
    monkeypatch.setenv("REPO_ROOT", str(target))
    assert paths_mod.repo_root() == target


def test_brain_data_dir_derives_from_brain_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When only ``BRAIN_ROOT`` is set, ``brain_data_dir`` returns ``<root>/data``."""
    target = tmp_path / "brain-pkg"
    target.mkdir()
    monkeypatch.setenv("BRAIN_ROOT", str(target))
    assert paths_mod.brain_data_dir() == target / "data"


def test_brain_root_repo_layout_finds_brain_dir() -> None:
    """In the repo layout, walking up from ``app/utils/paths.py`` lands on ``apis/brain/``.

    This is the canonical fallback when no env override is present and we're
    not in the container.
    """
    root = paths_mod.brain_root()
    assert root.name in {"brain", "app"}, f"unexpected brain_root: {root}"
    if root.name == "brain":
        assert (root / "alembic").is_dir()
        assert (root / "app").is_dir()


def test_repo_root_repo_layout_finds_monorepo() -> None:
    """In the repo layout, ``repo_root`` walks up to the monorepo root."""
    root = paths_mod.repo_root()
    if root != Path("/app"):
        assert (root / "apis" / "brain").is_dir()
        assert (root / "apps").is_dir()


def test_is_container_returns_false_outside_container() -> None:
    """When ``/app/alembic`` and ``/app/app`` don't both exist, we're not in a container."""
    sentinel_alembic = Path("/app/alembic").is_dir()
    sentinel_app = Path("/app/app").is_dir()
    if not (sentinel_alembic and sentinel_app):
        assert paths_mod._is_container() is False


def test_brain_scripts_dir_repo_layout() -> None:
    """In repo, brain scripts live at ``<repo>/scripts``, not under ``apis/brain/``."""
    if paths_mod._is_container():
        pytest.skip("container layout has its own scripts dir at /app/scripts")
    scripts = paths_mod.brain_scripts_dir()
    assert scripts.name == "scripts"
    assert (scripts.parent / "apis" / "brain").is_dir()
