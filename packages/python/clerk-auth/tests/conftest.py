"""Shared fixtures for Clerk auth tests."""

from __future__ import annotations

from typing import Any

import pytest

from tests.support import generate_rsa_pem, public_jwk_from_pem


@pytest.fixture()
def rsa_private_pem() -> bytes:
    return generate_rsa_pem()


@pytest.fixture()
def rsa_public_jwk(rsa_private_pem: bytes) -> dict[str, Any]:
    return public_jwk_from_pem(rsa_private_pem)
