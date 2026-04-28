# paperwork-auth

Python sidecar for the `@paperwork-labs/auth-clerk` package. Verifies
Clerk-issued JWTs against the Frontend API JWKS and exposes a FastAPI
dependency for protected routes.

## Install (editable, from the monorepo root)

```bash
pip install -e packages/auth-clerk/src/python
```

Add to `apis/<service>/requirements.txt`:

```
-e ./packages/auth-clerk/src/python
```

## Usage

```python
from fastapi import Depends, FastAPI
from paperwork_auth import require_clerk_user, ClerkUser

app = FastAPI()

@app.get("/me")
async def me(user: ClerkUser = Depends(require_clerk_user())) -> dict:
    return {"user_id": user.user_id, "org_id": user.org_id}
```

The default config reads `CLERK_JWT_ISSUER` (required, e.g.
`https://clerk.filefree.ai`) and `CLERK_JWT_AUDIENCE` (optional) from the
environment. Override by passing a `ClerkJwtConfig` instance to
`require_clerk_user(config=...)`.

## Token sources

The dependency accepts either:

- `Authorization: Bearer <token>` header
- `__session` cookie (Clerk's default for browser sessions)

All verification failures are surfaced as `HTTPException(401)`. Underlying
jose error messages are not leaked to the client; check service logs (the
module emits `WARNING` records via `logging.getLogger("paperwork_auth.jwks")`).
