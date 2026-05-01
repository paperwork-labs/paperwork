---
last_reviewed: 2026-05-01
---

# Cloudflare token inventory (WS-57 batch A)

Scoped-token posture follows WS-47 (`apis/brain/app/services/cloudflare_token_resolver.py`). This table documents **direct** use of `CLOUDFLARE_API_TOKEN` / env reads outside the resolver.

| Location | Token source | Operation class | Notes |
|----------|----------------|-----------------|-------|
| `apis/brain/app/services/cloudflare_token_resolver.py` | `settings.CLOUDFLARE_API_TOKEN` | Write resolver fallback | Intended: single fallback path with warning when per-zone `CLOUDFLARE_TOKEN_<SLUG>` is unset. |
| `apis/brain/app/services/cloudflare_client.py` → `bearer_for_cloudflare_dns_read` | `settings.CLOUDFLARE_API_TOKEN` | Read fallback | Used only when no per-zone `CLOUDFLARE_READONLY_TOKEN_*` is set for that apex. Read-only DNS GET paths. |
| `apis/brain/app/services/cloudflare_client.py` → `bearer_for_cloudflare_dns_write` / `cloudflare_auth_headers(write=True)` | Resolver (`resolve_write_token` / `write_auth_headers`) | Write | Does **not** read `CLOUDFLARE_API_TOKEN` directly for mutations; delegates to resolver. |
| `apis/brain/app/services/clerk_dns_watch.py` | `os.environ` `CLOUDFLARE_API_TOKEN` / `CF_TOKEN` | Read / validation only | Checks presence before shelling out to `scripts/reconcile_clerk_dns.py --check-only` (DNS comparison; no Brain-initiated DNS writes). |
| `scripts/reconcile_clerk_dns.py`, `scripts/dns_set_spf_dmarc.py`, `scripts/cloudflare_issue_readonly_tokens.py`, cutover shell scripts | Env / vault `CLOUDFLARE_API_TOKEN` | Mixed (CLI) | Operators’ scripts; not Brain runtime write paths. Issue-readonly script uses account-wide token only where needed to mint narrower tokens. |

**Audit result (batch A):** No Brain write paths use `settings.CLOUDFLARE_API_TOKEN` directly outside `cloudflare_token_resolver` and the documented read fallbacks above.
