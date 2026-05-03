# `mcp-server`

Shared JSON-RPC 2.0 MCP transport, bearer-token auth, and per-user
daily quota for Paperwork Labs product backends.

This package extracts the gold-standard implementation from
AxiomFolio's `app/mcp/server.py` and `app/mcp/auth.py` so every
product (AxiomFolio, FileFree, LaunchFree) can expose an MCP server
without duplicating the dispatcher, the bearer machinery, or the
quota wiring. Each product still owns:

* its **token model** (`MCPToken` SQLAlchemy class);
* its **tool catalog** and the per-tool **scope mapping**;
* its **tier** semantics (subscription enum, scopes-by-tier table,
  daily-call-limit table);
* its **PII consent** rules (e.g. AxiomFolio drops `mcp.read_tax_engine`
  unless the token was minted with explicit consent).

This package owns the security-sensitive plumbing: JSON-RPC envelope
parsing, fail-CLOSED scope gating, reserved-arg blocking, SHA-256 token
hashing, constant-time hash compare, and the Redis quota counter with
fail-OPEN degradation reporting.

## Public API

```python
from mcp_server import (
    # Dispatcher
    MCPServer,
    JSONRPC_VERSION,
    RESERVED_ARG_NAMES,
    ERR_PARSE,
    ERR_INVALID_REQUEST,
    ERR_METHOD_NOT_FOUND,
    ERR_INVALID_PARAMS,
    ERR_INTERNAL,
    # Auth
    MCPAuthBuilder,
    MCPAuthContext,
    generate_token,
    hash_token,
    split_credential,   # legacy alias: _split_credential
    # Quota
    DailyCallQuota,
    make_module_level_quota,
    # FastAPI
    mcp_bearer,
)
```

## Why a shared package (and not per-product copies)

Triplicating an auth surface is the most reliable way to introduce
silent security drift. Wave K2 of the platform plan extracts this code
**before** FileFree and LaunchFree fork their own copies in Wave I3.

## How AxiomFolio uses it (real example)

`apis/axiomfolio/app/mcp/server.py` is now ~30 lines: it imports
`MCPServer`, plugs in AxiomFolio's `TOOL_DEFINITIONS / TOOL_HANDLERS /
TOOL_REQUIRED_SCOPE`, and binds the quota to AxiomFolio's
`MarketInfra` Redis client.

`apis/axiomfolio/app/mcp/auth.py` is now ~50 lines: it constructs an
`MCPAuthBuilder` with AxiomFolio specifics — `token_prefix=
"mcp_axfolio_"`, the AxiomFolio `MCPToken` model, the entitlement-based
tier resolver, and a consent filter for `mcp.read_tax_engine`.

The full AxiomFolio integration test suite (cross-tenant isolation,
token revocation, scope gating, JSON-RPC error codes) passes
byte-identical against the extracted package — that's the contract.

## How FileFree (or any backend) wires it up

Below is the ~20-line skeleton FileFree (Wave K11) and LaunchFree
(Wave K12) will use. Replace the four product-specific symbols and
you're done.

```python
# apis/filefree/app/mcp/server.py
from mcp_server import DailyCallQuota, MCPServer
from app.mcp.tools import TOOL_DEFINITIONS, TOOL_HANDLERS, TOOL_REQUIRED_SCOPE
from app.infra.redis import get_redis_client  # FileFree's Redis accessor

_quota = DailyCallQuota(get_redis_client, key_prefix="filefree:mcp:calls")
mcp_quota_degradation_snapshot = _quota.degradation_snapshot

def build_default_server() -> MCPServer:
    return MCPServer(
        TOOL_DEFINITIONS,
        TOOL_HANDLERS,
        TOOL_REQUIRED_SCOPE,
        quota=_quota,
    )
```

```python
# apis/filefree/app/mcp/auth.py
from mcp_server import MCPAuthBuilder, generate_token as _gen, hash_token
from app.database import get_db
from app.models.mcp_token import MCPToken
from app.services.billing.tier_catalog import (
    mcp_daily_call_limit, mcp_scopes_for_tier,
)
from app.services.billing.entitlement_service import EntitlementService

_builder = MCPAuthBuilder(
    token_prefix="mcp_filefree_",
    token_model_class=MCPToken,
    get_db=get_db,
    tier_resolver=lambda db, user: EntitlementService.effective_tier(db, user),
    scopes_for_tier_fn=mcp_scopes_for_tier,
    daily_limit_fn=mcp_daily_call_limit,
)

get_mcp_context = _builder.build_dependency()
def generate_token(): return _gen("mcp_filefree_")
__all__ = ["get_mcp_context", "generate_token", "hash_token"]
```

That's the entire integration. Token CRUD endpoints and the
`/jsonrpc` route stay in the backend (they're route-shape, not
auth-mechanism).

## Fail-CLOSED scope gating

The dispatcher will refuse to expose any tool whose name is missing
from `tool_required_scope`. This makes the "ship a new tool, forget to
list its scope" failure mode safe — the tool stays invisible until you
explicitly tier-gate it. Same guarantee AxiomFolio's tests assert
([apis/axiomfolio/app/tests/mcp/test_tools.py](../../../apis/axiomfolio/app/tests/mcp/test_tools.py)).

## Fail-OPEN quota on Redis outage

`DailyCallQuota.consume()` increments a per-user-per-UTC-day counter
in Redis with a 25-hour TTL. If Redis is unreachable, the call is
**allowed** (fail-OPEN) but the failure is recorded in
`degradation_snapshot()` for `/admin/health` to pick up. Treating the
rate limiter as a hard dependency would convert a Redis hiccup into a
global MCP outage for every paying tier — that's worse than allowing a
brief overage.

## Testing

```bash
# From the monorepo root
uv sync
uv run --package mcp-server pytest packages/python/mcp-server/tests/
```

Tests cover:

* JSON-RPC envelope shape (every error code: -32600 / -32601 / -32602 /
  -32603).
* Fail-CLOSED scope gating in both `tools/list` and `tools/call`.
* Reserved-arg blocking (`user_id`, `db`, `session`).
* Handler `ValueError` -> `-32602`; any other exception -> `-32603`
  with a generic message (no internal leak).
* Token hashing, generation, and credential splitting (parametrized
  over the malformed-input matrix).
* `MCPAuthBuilder.authenticate()` against an in-memory SQLite schema:
  happy path, bad prefix, unknown hash, revoked, expired, inactive
  user.
* `MCPAuthBuilder.build_dependency()` mounted on a real FastAPI app
  (full request roundtrip including `last_used_at` write-back).
* Daily quota: under/at/over limit, per-user isolation, day rollover,
  Redis outage fail-OPEN, degradation snapshot copy semantics.

The integration story (cross-tenant isolation, real DB, real Clerk
auth) lives in each product's own test suite — see
[apis/axiomfolio/app/tests/mcp/test_tools.py](../../../apis/axiomfolio/app/tests/mcp/test_tools.py)
for the canonical reference.
