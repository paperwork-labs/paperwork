---
title: Cloudflare — decommission zones on former personal account
last_reviewed: 2026-04-28
owner: infra-ops
status: active
domain: infra
doc_kind: runbook
summary: "After NS soak (~24h), delete the five migrated zones from the founder's former personal Cloudflare account using scripts/cloudflare_decommission_zones.py."
tags: [cloudflare, dns, migration, security]
---

# Cloudflare zone decommission (old personal account)

## When to run

1. **At least ~24 hours after** nameserver / registrar cutover to the work account
   (soak ended **~2026-04-29 21:00 UTC** for the 2026-04-28 migration).
2. Confirm production is healthy on the **work** account (HTTP checks, Clerk, email
   DNS) and global resolvers show the **new** delegation (see
   `docs/runbooks/CLOUDFLARE_OWNERSHIP.md`).

Do **not** run early: if public NS still matches the old zone's Cloudflare
`name_servers`, the script **refuses** to delete (precondition failure).

## Old-account API token

1. Log into the **former** personal Cloudflare account (migrated-from; see
   `CLOUDFLARE_OWNERSHIP.md`).
2. **My Profile → API Tokens → Create Token** (custom).
3. Permissions: **Zone → Zone → Read** (to list zones via the API) and
   **Zone → Zone → Delete** (required for `DELETE /zones/{id}`). Optionally add
   **Zone → Zone → Edit** if you use the same token for other maintenance.
4. Copy the token value once. **Do not** store it in the Studio vault or GitHub
   secrets — export it only in your shell for the one-shot run:

```bash
export CLOUDFLARE_OLD_API_TOKEN='...paste...'
```

## Commands (dry-run, then apply)

From the repo root:

```bash
# 1) Dry-run — prints dig preconditions + "would delete" (no API deletes)
python3 scripts/cloudflare_decommission_zones.py

# 2) If and only if every zone shows PRECONDITIONS: PASS:
python3 scripts/cloudflare_decommission_zones.py --apply
```

Success ends with a green line: **all 5 zones decommissioned**. A red summary
means at least one zone failed preconditions or a DELETE call failed — **stop
and investigate** (do not bypass checks).

## If a precondition fails

Typical causes: resolver still seeing old NS, partial propagation, or a typo at
the registrar. **Do not** force-delete zones from the dashboard without
understanding DNS state.

1. Re-check delegation: `dig NS <apex> @1.1.1.1`, `@8.8.8.8`, `@9.9.9.9`.
2. Compare to the **work** account zone nameservers in Cloudflare.
3. When all three resolvers agree on the **new** pair and HTTP/Clerk checks are
   green, re-run the dry-run.

## Rollback / recovery

Deleting a zone in Cloudflare is **destructive** for that account's copy of the
zone, but Cloudflare may retain a **~30-day** recovery window for emergency
restore (see current Cloudflare support documentation). Registrar NS must still
point at live nameservers on the **work** account — deleting the old duplicate
zone does **not** change delegation once migration is complete.

## Related

* `scripts/cloudflare_decommission_zones.py` — implementation.
* `scripts/cloudflare_issue_readonly_tokens.py` — per-zone read tokens on the
  **work** account (separate concern; run manually after merge, not in CI).
* `docs/runbooks/CLOUDFLARE_OWNERSHIP.md` — canonical zone IDs and account IDs.
