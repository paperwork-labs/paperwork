"""Validate Alembic migration chain integrity.

These tests run without a database (no_db marker) and catch chain
corruption before it ever reaches production.
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

pytestmark = pytest.mark.no_db


def _get_script_dir() -> ScriptDirectory:
    cfg = Config("app/alembic.ini")
    cfg.set_main_option("script_location", "app/alembic")
    return ScriptDirectory.from_config(cfg)


def test_single_head():
    """Migration chain must have exactly one head."""
    heads = _get_script_dir().get_heads()
    assert len(heads) == 1, f"Expected 1 head, got {len(heads)}: {heads}"


def test_no_orphan_revisions():
    """Every revision except base must have a valid down_revision."""
    script = _get_script_dir()
    for rev in script.walk_revisions():
        if rev.down_revision is not None:
            parent = script.get_revision(rev.down_revision)
            assert parent is not None, f"Orphan: {rev.revision} points to missing {rev.down_revision}"


def test_chain_is_linear():
    """No merge points -- chain must be linear (no multi-parent revisions)."""
    script = _get_script_dir()
    for rev in script.walk_revisions():
        dr = rev.down_revision
        assert not isinstance(dr, tuple), f"Branched migration: {rev.revision} has multiple parents {dr}"
