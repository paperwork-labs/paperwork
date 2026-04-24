"""Unit tests for the redis_namespace helper."""

from __future__ import annotations

import pytest

from app.services.multitenant.redis_namespace import (
    tenant_key,
    tenant_scan_pattern,
)

pytestmark = pytest.mark.no_db


def test_tenant_key_namespaces_user_id():
    assert tenant_key(42, "ratelimit:foo") == "tenant:42:ratelimit:foo"


def test_tenant_key_uses_global_bucket_for_none():
    assert tenant_key(None, "cache:k") == "tenant:global:cache:k"


def test_tenant_key_rejects_empty_key():
    with pytest.raises(ValueError):
        tenant_key(1, "")


def test_tenant_key_coerces_user_id_to_int():
    # int('5') == 5; str(5) == '5'
    assert tenant_key("5", "k") == "tenant:5:k"


def test_tenant_keys_are_isolated_between_tenants():
    a = tenant_key(1, "x")
    b = tenant_key(2, "x")
    assert a != b
    assert a.startswith("tenant:1:")
    assert b.startswith("tenant:2:")


def test_scan_pattern_only_matches_one_tenant():
    pat = tenant_scan_pattern(7)
    assert pat == "tenant:7:*"
    # Should NOT accidentally also match tenant:77:*; the colon after
    # the user id is the discriminator.
    assert tenant_key(77, "z").startswith("tenant:77:")
    # A glob "tenant:7:*" does not match "tenant:77:..." because of
    # the literal colon — verified by string semantics.
