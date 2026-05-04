# Provider API Token Scope Audit — Q2 2026

**Status**: PROPOSED — orchestrator/founder runs verification script post-merge  
**Date**: 2026-05-04  
**Authored by**: T3.1-pre cheap-agent (composer-1.5)  
**Feeds**: T3.1 IaC drift detector

## Why this exists

T3.1 IaC drift detector (`scripts/check_infra_drift.py`) needs read-only API access to each provider to compare deployed state vs canonical `infra/state/*.yaml`. Tokens are expected to live in Studio Vault (see [docs/SECRETS.md](../SECRETS.md)). This audit lists **required API scopes** and **how to verify** them before T3.1 implements the drift checks. No secret values belong in this document.

## Vault contract (read path)

- **Single-secret lookup**: `./scripts/vault-get.sh SECRET_NAME` (Bearer `SECRETS_API_KEY` from `.env.local`, or admin basic auth — same contract as [scripts/vault-get.sh](../../scripts/vault-get.sh)).
- **Upsert (out of scope here)**: `./scripts/vault-set.sh NAME --value ...` — see [scripts/vault-set.sh](../../scripts/vault-set.sh).

Canonical env names below match [docs/infra/STUDIO_ENV.md](../infra/STUDIO_ENV.md) and existing automation (e.g. [scripts/reconcile_clerk_dns.py](../../scripts/reconcile_clerk_dns.py), [apps/studio/src/lib/command-center.ts](../../apps/studio/src/lib/command-center.ts)).

## Required scopes per provider

### Cloudflare — vault keys `CLOUDFLARE_API_TOKEN` (primary), legacy `CF_TOKEN` / `CF_API_TOKEN` if present

**Required**: `Zone:Read` on all six zones: `paperworklabs.com`, `filefree.ai`, `launchfree.ai`, `distill.tax`, `axiomfolio.com`, and **`tools.filefree.ai`** (same Cloudflare zone as `filefree.ai` unless you intentionally split zones; the drift detector must still be able to read DNS for that hostname’s zone).

**Why**: T3.1 IaC drift detector compares live zone metadata, DNS records, and (where modeled) rulesets/WAF config against canonical `infra/state/cloudflare.yaml`.

**Verification endpoint**: `GET https://api.cloudflare.com/client/v4/user/tokens/verify` — returns token `status` and permission groups so you can confirm zone coverage (see [Cloudflare API — verify token](https://developers.cloudflare.com/fundamentals/api/reference/rest-api-endpoints/#verify-token)).

**Notes**:

- Repo scripts and runbooks standardize on **`CLOUDFLARE_API_TOKEN`**; `CF_TOKEN` is a legacy alias in some tools.
- **Implementation note**: Listing and diffing **DNS record contents** typically requires **`DNS:Read`** (or equivalent zone DNS read) in addition to `Zone:Read`. When `check_infra_drift.py` is wired for record-level diffs, confirm the token includes DNS read on each zone above.

---

### Render — vault key `RENDER_API_KEY`

**Required**: **`Service:Read`** (enumerate services, deploy metadata, service settings) + **`EnvVar:Read`** (read non-secret env var metadata for drift vs `render.yaml` / documented env matrix).

**Why**: T3.1 IaC drift detector aligns Render service definitions, regions, plans, and declared env keys with canonical `infra/state/render.yaml` (or successor state file). Studio already probes services via `GET https://api.render.com/v1/services` ([apps/studio/src/lib/infra-probes.ts](../../apps/studio/src/lib/infra-probes.ts)); env-var parity checks need env var list endpoints.

**Verification endpoint** (smoke + scope exercise):

1. `GET https://api.render.com/v1/owners?limit=1` — validates API key ([Render API — list workspaces / owners](https://api-docs.render.com/reference/list-owners)).
2. `GET https://api.render.com/v1/services?limit=1` — requires service read.
3. `GET https://api.render.com/v1/services/{serviceId}/env-vars?limit=1` — requires env var read (use `serviceId` from the previous response).

**Notes**: Render uses a single **API key** string (Bearer), not OAuth scopes named in the dashboard the same way as Cloudflare; the capability names above map to the permissions Render shows when creating a key.

---

### Clerk — vault key `CLERK_SECRET_KEY` (Backend API / “secret key”)

**Required**: Effective access equivalent to **`Instance:Read`** + **`Domain:Read`** on the production Clerk instance (Dashboard permission names). The Backend API secret key must be allowed to read instance settings and the domain list used for DNS / cutover drift.

**Why**: T3.1 IaC drift detector compares Clerk-satellite configuration (e.g. authorized domains, proxy/satellite settings relevant to DNS) against canonical `infra/state/clerk.yaml`. Today, [scripts/reconcile_clerk_dns.py](../../scripts/reconcile_clerk_dns.py) calls `GET {CLERK_API_BASE}/v1/domains` with the secret key.

**Verification endpoint** (Bearer secret key):

1. `GET https://api.clerk.com/v1/instance` — instance metadata ([Clerk Backend API](https://clerk.com/docs/reference/backend-api/tag/Instance)).
2. `GET https://api.clerk.com/v1/domains?limit=5` — domain list ([Clerk Backend API — Domains](https://clerk.com/docs/reference/backend-api/tag/Domains)).

**Notes**: Set `CLERK_API_URL` if using a non-default Clerk API host; the script defaults to `https://api.clerk.com`.

---

### Hetzner — vault key `HETZNER_API_TOKEN`

**Required**: **`Server:Read`** (list/read Cloud servers in the project).

**Why**: T3.1 IaC drift detector compares server inventory, status, and selected labels/types against canonical `infra/state/hetzner.yaml`. Studio’s infrastructure card uses `GET https://api.hetzner.cloud/v1/servers` ([apps/studio/src/lib/command-center.ts](../../apps/studio/src/lib/command-center.ts)).

**Verification endpoint**: `GET https://api.hetzner.cloud/v1/servers` ([Hetzner Cloud API — list servers](https://docs.hetzner.cloud/#servers-list-all-servers)).

**Notes**: Create a **read-only** API token in Hetzner Cloud Console (Security → API tokens) scoped at least to server read for the ops project.

---

### Neon — vault key `NEON_API_KEY`

**Required**: **`Project:Read`** + **`Branch:Read`** (list projects; list branches per project for connection / pool drift).

**Why**: T3.1 IaC drift detector compares Neon project IDs, default branches, and branch metadata against canonical `infra/state/neon.yaml`. Studio smoke-checks `GET https://console.neon.tech/api/v2/projects` ([apps/studio/src/lib/command-center.ts](../../apps/studio/src/lib/command-center.ts)); branch-level drift needs branch listing.

**Verification endpoint** (Bearer API key):

1. `GET https://console.neon.tech/api/v2/projects?limit=1` — project read ([Neon API — list projects](https://api-docs.neon.tech/reference/listprojects)).
2. `GET https://console.neon.tech/api/v2/projects/{project_id}/branches?limit=1` — branch read ([Neon API — list branches](https://api-docs.neon.tech/reference/listprojectbranches)).

**Notes**: The verification script picks `project_id` from the first project returned; multi-project accounts should repeat manually for each tracked project if needed.

---

## Verification script

See [scripts/audits/verify_provider_token_scopes.sh](../../scripts/audits/verify_provider_token_scopes.sh). Run from a machine with vault access (`.env.local` with `SECRETS_API_KEY`, or admin credentials per `vault-get.sh`):

```bash
./scripts/audits/verify_provider_token_scopes.sh
```

The script prints **PASS** or **FAIL** per provider and exits non-zero if any provider fails. Append the redacted transcript (no response bodies containing secrets) to this section after verification.

### Post-verification log (append-only)

| Run date | Operator | Result summary |
|----------|----------|----------------|
| _pending_ | _founder/orchestrator_ | _paste summary after running script_ |

## Not done in this PR

- Live API calls against providers (orchestrator/founder runs the script post-merge with vault access).
- Updating or rotating any vault entries.
- Authoring `infra/state/*.yaml` or `scripts/check_infra_drift.py` (owned by T3.1).
- Vercel, Upstash, GitHub, or other providers outside the five listed in T3.1-pre.
