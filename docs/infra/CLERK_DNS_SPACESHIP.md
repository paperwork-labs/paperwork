---
owner: infra-ops
last_reviewed: 2026-04-28
doc_kind: runbook
domain: infra
status: active
summary: "Clerk CNAMEs for paperworklabs.com: same five rows as historically pasted in Spaceship; as of 2026-04-28 create them in the Cloudflare work-account zone (registrar remains Spaceship for delegation only)."
tags: [clerk, dns, spaceship, infra, founder]
---

# Clerk production DNS for `paperworklabs.com`

> **2026-04-28:** Authoritative DNS for `paperworklabs.com` is the **Paperwork Labs work Cloudflare** zone (NS `janet` + `noel`; see `docs/runbooks/cloudflare-ownership.md`). **Spaceship** remains the **registrar** only. Enter the CNAME rows below in **Cloudflare → DNS → Records** (same **name** / **target** semantics as the legacy Spaceship column labels). For the primary `accounts` host step-by-step, see `docs/infra/CLERK_ACCOUNTS_DNS_TONIGHT.md`.

**Purpose:** Add the **five CNAME records** below so Clerk can verify domain ownership, serve the **Frontend API** on `clerk.paperworklabs.com`, **auto-host the Account Portal** on `accounts.paperworklabs.com`, and configure **Clerk email** (mail subdomain + DKIM).

Clerk’s primary application domain is **`paperworklabs.com`**. The Account Portal is **Clerk-hosted** at `https://accounts.paperworklabs.com` after these records propagate — you do **not** deploy a separate `apps/accounts/` app for that host. Broader **satellite** topology (other brands) remains in [`CLERK_SATELLITE_TOPOLOGY.md`](CLERK_SATELLITE_TOPOLOGY.md).

**Dashboard reference (optional):** A founder capture of the Clerk **Domains** panel with these five rows: `assets/Screenshot_2026-04-27_at_12.55.47_AM-8418cfe1-ab14-4a77-87d2-565114f7213e.png` (add to the repo if you want it linked from Studio).

## Paste table (5 CNAMEs)

In **Cloudflare**, use **Type** `CNAME`, **Name** = left column (apex-relative), **Target** = Value column, **Proxy** off (DNS only) unless Clerk’s current dashboard explicitly requires orange-cloud.

| Type | Name (Cloudflare) / Host (legacy Spaceship) | Value (CNAME target) | TTL |
|------|---------------------------------------------|----------------------|-----|
| CNAME | `clerk` | `frontend-api.clerk.services` | 300 (or default) |
| CNAME | `accounts` | `accounts.clerk.services` | 300 (or default) |
| CNAME | `clkmail` | `mail.uqxloe4nmf2s.clerk.services` | 300 (or default) |
| CNAME | `clk._domainkey` | `dkim1.uqxloe4nmf2s.clerk.services` | 300 (or default) |
| CNAME | `clk2._domainkey` | `dkim2.uqxloe4nmf2s.clerk.services` | 300 (or default) |

**Full FQDNs (for your mental model — the Name column is apex-relative):**

- `clerk.paperworklabs.com`
- `accounts.paperworklabs.com`
- `clkmail.paperworklabs.com`
- `clk._domainkey.paperworklabs.com`
- `clk2._domainkey.paperworklabs.com`

## Record-entry gotchas (Cloudflare; legacy Spaceship column names below)

- **Name / Host = subdomain prefix only** — e.g. `clerk`, not `clerk.paperworklabs.com`. Same for `accounts`, `clkmail`, and the two DKIM names.
- **Underscored DKIM names** like `clk._domainkey` and `clk2._domainkey` are valid in Cloudflare; create them exactly as in the table.
- **No trailing dot** on CNAME target values (use `frontend-api.clerk.services`, not `frontend-api.clerk.services.`).
- If you had an old **`accounts`** CNAME from earlier experiments, **delete it first**, then add the Clerk `accounts` → `accounts.clerk.services` record (only **one** CNAME per name).
- **Apex** `paperworklabs.com` — leave as-is; these records are **subdomains only**.

## Verification (Clerk + DNS)

1. After saving all **five** records, wait **~5 minutes** for DNS to start answering consistently.
2. In **Clerk Dashboard** → **Configure** → **Developers** → **Domains** → **Verify configuration** (or the per-domain verify control Clerk shows for your instance).
3. All **five** should move from **Unverified** to **Verified** (Frontend API, Account portal, email/DKIM rows as shown in the Dashboard).
4. **DKIM (records 4 & 5)** can take **15–30 minutes** longer in some paths; re-check verification after a short wait if email/DKIM lines lag the others.

## One-liner: `dig` all five

```bash
for h in clerk accounts clkmail clk._domainkey clk2._domainkey; do
  echo "=== $h.paperworklabs.com ==="
  dig CNAME $h.paperworklabs.com +short
done
```

Expect each line to show the corresponding Clerk `*.clerk.services` target (no duplicate zones or doubled suffixes).

## Troubleshooting

- **“Clerk still says Unverified”** — In some DNS UIs, mis-entered hosts create nonsense like `*.paperworklabs.com.paperworklabs.com`. Check the saved record names in **Cloudflare** (or Spaceship if you are reading a legacy capture), then run the `dig` one-liner above. Each `+short` should be a single `*.clerk.services` name.
- **Email / DKIM error in Clerk** — Wait up to **30 minutes** for DKIM propagation, then use **Verify configuration** again in the Dashboard.
- **“Multiple records” / conflicts** — Only **one CNAME** is allowed per hostname. Remove duplicate or stale CNAMEs on the same name (e.g. two `accounts` rows).

## See also

- [`CLERK_SATELLITE_TOPOLOGY.md`](CLERK_SATELLITE_TOPOLOGY.md) — portfolio satellite domains (other sites) after production DNS is green.
