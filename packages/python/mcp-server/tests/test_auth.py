"""Unit tests for :mod:`mcp_server.auth`.

The token helpers are pure-Python and trivially testable. The
:class:`MCPAuthBuilder` is exercised against an in-memory SQLite
schema with a tiny ``User`` and ``MCPToken`` model that mirrors the
shape AxiomFolio's real schema gives us.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from mcp_server.auth import (
    DEFAULT_TOKEN_RANDOM_BYTES,
    MCPAuthBuilder,
    MCPAuthContext,
    _split_credential,
    generate_token,
    hash_token,
    split_credential,
)

# ----------------------------------------------------------------------
# Token helpers (pure)
# ----------------------------------------------------------------------


class TestTokenHelpers:
    def test_hash_token_deterministic(self):
        assert hash_token("abc") == hash_token("abc")
        assert hash_token("abc") != hash_token("abd")

    def test_hash_token_hex_64(self):
        h = hash_token("anything")
        assert len(h) == 64
        int(h, 16)  # round-trips as hex

    def test_generate_token_uses_prefix(self):
        plaintext, h = generate_token("mcp_test_")
        assert plaintext.startswith("mcp_test_")
        assert hash_token(plaintext) == h

    def test_generate_token_random_bytes_param(self):
        p, _ = generate_token("p_", random_bytes=8)
        # 8 random bytes -> ~12 chars urlsafe base64 (rounded)
        assert len(p) >= len("p_") + 8

    def test_generate_token_default_entropy(self):
        p, _ = generate_token("x_")
        # 32 bytes -> ~43 chars + prefix.
        assert len(p) >= len("x_") + DEFAULT_TOKEN_RANDOM_BYTES

    def test_generate_token_uniqueness(self):
        seen = {generate_token("p_")[0] for _ in range(64)}
        assert len(seen) == 64

    def test_split_credential_happy(self):
        ok = split_credential(
            "mcp_test_" + "x" * 32, prefix="mcp_test_", min_random_length=16
        )
        assert ok is not None

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            "",
            "not_an_mcp_token",
            "mcp_test_short",  # below min length
        ],
    )
    def test_split_credential_rejects(self, raw):
        assert split_credential(raw, prefix="mcp_test_") is None

    def test_underscore_alias_is_split_credential(self):
        assert _split_credential is split_credential


# ----------------------------------------------------------------------
# In-memory schema for builder tests
# ----------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class _User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class _MCPToken(Base):
    __tablename__ = "mcp_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    pii_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    user = relationship("_User", lazy="joined")

    def is_active(self, now: datetime | None = None) -> bool:
        if self.revoked_at is not None:
            return False
        ts = now or datetime.now(UTC)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return ts < exp


@pytest.fixture
def db_factory():
    # StaticPool + check_same_thread=False forces every connection to
    # share the same underlying in-memory SQLite DB. Without this, the
    # FastAPI TestClient's worker thread opens a fresh connection
    # (= fresh in-memory DB without any tables).
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(engine, expire_on_commit=False)
    return Session_


@pytest.fixture
def db_session(db_factory):
    s = db_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def alice(db_session):
    u = _User(name="alice")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _mint(
    db: Session,
    user: _User,
    *,
    expires_in: timedelta = timedelta(days=30),
    revoked: bool = False,
) -> str:
    plaintext, h = generate_token("mcp_test_")
    row = _MCPToken(
        user_id=user.id,
        token_hash=h,
        expires_at=datetime.now(UTC) + expires_in,
        revoked_at=datetime.now(UTC) if revoked else None,
    )
    db.add(row)
    db.commit()
    return plaintext


# ----------------------------------------------------------------------
# Builder.authenticate (unit-level)
# ----------------------------------------------------------------------


def _builder(db_factory, **overrides):
    defaults = dict(
        token_prefix="mcp_test_",
        token_model_class=_MCPToken,
        get_db=lambda: db_factory(),
        tier_resolver=lambda db, user: "FREE",
        scopes_for_tier_fn=lambda tier: ["mcp.read"],
        daily_limit_fn=lambda tier: 100,
    )
    defaults.update(overrides)
    return MCPAuthBuilder(**defaults)


class TestAuthenticate:
    def test_happy_path(self, db_factory, db_session, alice):
        token = _mint(db_session, alice)
        b = _builder(db_factory)
        user, row = b.authenticate(token, db_session)
        assert user.id == alice.id
        assert row.token_hash == hash_token(token)

    def test_bad_prefix_is_401(self, db_factory, db_session, alice):
        b = _builder(db_factory)
        with pytest.raises(HTTPException) as exc:
            b.authenticate("wrong_prefix_xxxxxxxxxxxxxxxxxxxx", db_session)
        assert exc.value.status_code == 401

    def test_unknown_hash_is_401(self, db_factory, db_session):
        b = _builder(db_factory)
        with pytest.raises(HTTPException) as exc:
            b.authenticate(
                "mcp_test_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", db_session
            )
        assert exc.value.status_code == 401

    def test_revoked_token_is_401(self, db_factory, db_session, alice):
        token = _mint(db_session, alice, revoked=True)
        b = _builder(db_factory)
        with pytest.raises(HTTPException) as exc:
            b.authenticate(token, db_session)
        assert exc.value.status_code == 401

    def test_expired_token_is_401(self, db_factory, db_session, alice):
        token = _mint(
            db_session, alice, expires_in=timedelta(seconds=-60)
        )
        b = _builder(db_factory)
        with pytest.raises(HTTPException) as exc:
            b.authenticate(token, db_session)
        assert exc.value.status_code == 401

    def test_inactive_user_is_401(self, db_factory, db_session, alice):
        alice.is_active = False
        db_session.commit()
        token = _mint(db_session, alice)
        b = _builder(db_factory)
        with pytest.raises(HTTPException) as exc:
            b.authenticate(token, db_session)
        assert exc.value.status_code == 401

    def test_empty_string_is_401(self, db_factory, db_session):
        b = _builder(db_factory)
        with pytest.raises(HTTPException) as exc:
            b.authenticate("", db_session)
        assert exc.value.status_code == 401


# ----------------------------------------------------------------------
# Builder.build_dependency (FastAPI integration)
# ----------------------------------------------------------------------


class TestBuildDependency:
    def test_returns_mcp_auth_context_with_scopes(
        self, db_factory, db_session, alice
    ):
        token = _mint(db_session, alice)
        b = _builder(
            db_factory,
            scopes_for_tier_fn=lambda tier: ["mcp.read", "mcp.write"],
            daily_limit_fn=lambda tier: 1000,
        )

        # Override get_db to reuse our test session
        b._get_db = lambda: db_session  # type: ignore[method-assign]
        dep = b.build_dependency()

        app = FastAPI()

        @app.post("/whoami")
        def whoami(auth: MCPAuthContext = Depends(dep)):
            return {
                "user_id": auth.user.id,
                "tier": auth.tier,
                "allowed_scopes": sorted(auth.allowed_scopes),
                "daily_limit": auth.daily_limit,
            }

        client = TestClient(app)
        r = client.post(
            "/whoami", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user_id"] == alice.id
        assert body["tier"] == "FREE"
        assert body["allowed_scopes"] == ["mcp.read", "mcp.write"]
        assert body["daily_limit"] == 1000

    def test_consent_filter_applied(self, db_factory, db_session, alice):
        token = _mint(db_session, alice)
        # Drop the special scope unless pii_consent_at is set on the token.
        def consent_filter(tok, scopes: set[str]) -> set[str]:
            if tok.pii_consent_at is None:
                scopes.discard("mcp.read_tax_engine")
            return scopes

        b = _builder(
            db_factory,
            scopes_for_tier_fn=lambda tier: [
                "mcp.read",
                "mcp.read_tax_engine",
            ],
            consent_scope_filter=consent_filter,
        )
        b._get_db = lambda: db_session  # type: ignore[method-assign]

        dep = b.build_dependency()

        app = FastAPI()

        @app.post("/scopes")
        def scopes(auth: MCPAuthContext = Depends(dep)):
            return sorted(auth.allowed_scopes)

        client = TestClient(app)
        r = client.post(
            "/scopes", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        assert r.json() == ["mcp.read"]

    def test_missing_header_returns_401(self, db_factory, db_session):
        b = _builder(db_factory)
        b._get_db = lambda: db_session  # type: ignore[method-assign]
        dep = b.build_dependency()

        app = FastAPI()

        @app.post("/p")
        def p(auth: MCPAuthContext = Depends(dep)):
            return {"ok": True}

        client = TestClient(app)
        r = client.post("/p")
        assert r.status_code == 401

    def test_last_used_at_updated_on_success(
        self, db_factory, db_session, alice
    ):
        token = _mint(db_session, alice)
        # SQLite drops tz info on round-trip, so the comparison is
        # made naive on both sides.
        before = datetime.utcnow() - timedelta(seconds=1)
        b = _builder(db_factory)
        b._get_db = lambda: db_session  # type: ignore[method-assign]
        dep = b.build_dependency()

        app = FastAPI()

        @app.post("/p")
        def p(auth: MCPAuthContext = Depends(dep)):
            return {"ok": True}

        client = TestClient(app)
        r = client.post(
            "/p", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        row = db_session.query(_MCPToken).first()
        assert row is not None
        assert row.last_used_at is not None
        seen = row.last_used_at
        if seen.tzinfo is not None:
            seen = seen.replace(tzinfo=None)
        assert seen > before


class TestMCPAuthContext:
    def test_dataclass_is_frozen(self):
        ctx = MCPAuthContext(
            user=None,
            token=None,
            tier="FREE",
            allowed_scopes=frozenset({"mcp.read"}),
            daily_limit=100,
        )
        with pytest.raises(Exception):
            ctx.user = object()  # type: ignore[misc]

    def test_fields_carry_arbitrary_types(self):
        sentinel = object()
        ctx = MCPAuthContext(
            user=sentinel,
            token=None,
            tier=("FREE", "extra"),
            allowed_scopes=frozenset(),
            daily_limit=None,
        )
        assert ctx.user is sentinel
        assert ctx.tier == ("FREE", "extra")
        assert ctx.daily_limit is None
