# Clerk production custom domain — DNS runbook (Paperwork Labs)

Production Command Center (`www.paperworklabs.com`) uses Clerk with a **custom Frontend API host** (often `clerk.paperworklabs.com`) and **Account Portal** host (often `accounts.paperworklabs.com`). If those hostnames have **no DNS records**, the browser cannot load the sign-in page and interactive SSO appears “broken” even when application code and keys are correct.

**Registrar / DNS:** `paperworklabs.com` is served from **Vercel** (apex may resolve to Vercel anycast). Add the records below in **Vercel → Project/Domains → DNS** (or the registrar if DNS is delegated elsewhere), consistent with how other `*.paperworklabs.com` records are managed.

**Source of truth for targets:** **Clerk Dashboard → Configure → Domains → Production**. Clerk shows the exact CNAME targets for your instance. The table below lists the **usual** Clerk production pattern; always confirm the dashboard values before saving.

## Required DNS records

| Hostname | Type | Typical target (confirm in Clerk) |
| -------- | ---- | ----------------------------------- |
| `clerk.paperworklabs.com` | CNAME | `frontend-api.clerk.services` |
| `accounts.paperworklabs.com` | CNAME | `accounts.clerk.services` |

Clerk may display instance-specific hostnames (e.g. `clerk.<instance>.lcl.dev` or regional variants). **Use exactly what the dashboard shows**, not a guess from this doc.

## Optional records (email / deliverability)

If you use Clerk for **transactional email** or branded **DKIM**, the dashboard will list additional CNAMEs. Typical patterns:

| Hostname | Type | Typical pattern (confirm in Clerk) |
| -------- | ---- | ---------------------------------- |
| `clk._domainkey.paperworklabs.com` | CNAME | `dkim1.<INSTANCE_ID>.clerk.services` |
| `clk2._domainkey.paperworklabs.com` | CNAME | `dkim2.<INSTANCE_ID>.clerk.services` |
| `clkmail.paperworklabs.com` | CNAME | `mail.<INSTANCE_ID>.clerk.services` |

Replace `<INSTANCE_ID>` with the value from **Clerk Dashboard → Domains → Production** (not hard-coded in this repo).

## Verification

After records propagate:

```bash
dig accounts.paperworklabs.com CNAME +short
dig clerk.paperworklabs.com CNAME +short
curl -I https://accounts.paperworklabs.com/sign-in
```

Expect CNAME chains to resolve and `curl` to return HTTP **200** or **3xx** from the identity host (not NXDOMAIN / connection refused).

## Operational escape hatch (Studio)

While DNS is missing or propagating, Studio can be configured with **`CLERK_DOMAIN_DEGRADED=1`** so `/admin` does not redirect to the Account Portal and **only Basic Auth** can grant access. See `docs/infra/CLERK_STUDIO.md` and `apps/studio/src/middleware.ts`. Remove the flag once DNS and sign-in are healthy.

## Related

- `docs/infra/CLERK_STUDIO.md` — Studio Clerk + Basic Auth runbook
- `docs/infra/CLERK_FILEFREE.md` — FileFree Clerk runbook
