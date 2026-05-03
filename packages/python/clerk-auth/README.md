# clerk-auth

Shared FastAPI-ready Clerk bearer JWT verifier with JWKS fetching, TTL caching,
and fail-open degradation snapshots for JWKS outages.

Canonical workspace layout: monorepo `packages/python/clerk-auth/`. Older
consumers installing `packages/auth-clerk/src/python/paperwork_auth` via Docker
continue to operate unchanged until backend adoption waves migrate them.

## Public API

- `JWKSClient(clerk_issuer, cache_ttl_s=3600)` — retrieves signing keys via
  `{issuer}/.well-known/jwks.json`.
  - `get_signing_key(kid)` — returns cached key material merged from the JWKS
    payload; warns and returns last-known snapshots if Clerk itself is unreachable
    (`degradation_snapshot()` exposes counters modeled after MCP quota degrade
    metrics).
  - Raises `ClerkUnreachableError` when no snapshot exists for `kid`.

- `ClerkTokenValidator(issuer, audience, jwks_client=None)` /
  `validate(token) -> ClerkClaims` — verifies signature, expiry, issuer, and
  audience (required). Throws `InvalidTokenError` **with one stable message**
  (`INVALID_TOKEN_MESSAGE`) for every rejection so clients cannot tell which gate
    failed.

- `ClerkClaims` — pydantic frozen model exposing `user_id` (`sub`), optional org
  + email helpers, authoritative `issued_at` / `expires_at` datetimes, and a
  `raw` claim bag for JWT templates/custom fields.

- `require_clerk_user(validator)` / `optional_clerk_user(validator)` — FastAPI
  helpers that strictly require `Authorization: Bearer …` (**no Clerk cookie support**).
  Successful responses unwrap `ClerkClaims`; malformed/missing Bearer strings and
    invalid JWTs emit HTTP 401 with the same opaque detail string used by `InvalidTokenError`.

## Improvements over `paperwork_auth`

| Area | Historical `paperwork_auth` | `clerk-auth` |
| --- | --- | --- |
| Distribution | Pip sidecar tucked under `@paperwork-labs/auth-clerk` | First-class uv workspace member |
| Bearer surface | Bearer + `__session` cookie shortcut | Bearer-only injection for clearer API semantics |
| Claims modeling | Frozen dataclass + `Mapping` dumps | pydantic frozen `ClerkClaims` (+ `raw` escape hatch) |
| JWKS resilience | TTL cache + naive urllib fallback path | TTL cache merged with JWKS degrade snapshots exposed via telemetry |
| Error hygiene | Caller-facing strings surfaced `HTTPException` details | Dedicated `InvalidTokenError`/`ClerkUnreachableError` split internally, HTTP deps emit uniform detail |

## Deprecation roadmap

Docker-backed installs will keep `paperwork_auth` until Waves **K10-K13**
retire Dockerfile copies/requirements rewrites across backends.

## Developing

```bash
cd packages/python/clerk-auth
uv sync --extra test
uv run ruff check src tests
uv run mypy src
uv run pytest
```
