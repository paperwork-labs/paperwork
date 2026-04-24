"""Defaults for OAuth package tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_oauth_callback_allowlist() -> Iterator[None]:
    """``/oauth/*/initiate`` validates ``callback_url`` against live ``settings``.

    CI may omit ``OAUTH_ALLOWED_CALLBACK_URLS``; collection order can import the
    app before per-module ``os.environ.setdefault`` runs. Mutate the loaded
    settings object once per session so route tests stay deterministic.
    """

    from app.config import settings

    raw = getattr(settings, "OAUTH_ALLOWED_CALLBACK_URLS", None) or ""
    if not raw.strip():
        settings.OAUTH_ALLOWED_CALLBACK_URLS = "https://app.example/cb"
    yield
