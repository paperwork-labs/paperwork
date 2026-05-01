---
owner: cfo
last_reviewed: 2026-04-24
doc_kind: reference
domain: infra
status: active
---
# Billing Email Migration Checklist

**TL;DR:** Checklist for moving vendor billing to `billing@paperworklabs.com`. Use it when you migrate existing accounts or sign up for new services.

**Goal**: Use `billing@paperworklabs.com` for all vendor accounts (subscriptions, servers, APIs, domains). Keeps business expenses separate from personal, clean audit trail.

**Last updated**: 2026-03-17

---

## Vendors to Migrate (was on personal email)


| Vendor                | What                                                               | Action                                                                                          | Status |
| --------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------ |
| **Vercel**            | Frontend hosting (filefree, launchfree, distill, studio, trinkets) | Dashboard → Team Settings → Members — add billing@, make owner; or create new org with billing@ | [ ]    |
| **Render**            | API hosting (FileFree, LaunchFree, Studio, Portal Worker)          | Dashboard → Account → Billing — update email to billing@                                        | [ ]    |
| **Hetzner**           | Ops VPS (n8n, Postiz)                                              | Cloud Console → Project → Members — add billing@; or update billing contact                     | [ ]    |
| **Neon**              | PostgreSQL (filefree, launchfree, venture DB)                      | Dashboard → Settings → Billing — update to billing@                                             | [ ]    |
| **Upstash**           | Redis (sessions)                                                   | Dashboard → Account → change email or add billing@                                              | [ ]    |
| **GCP**               | Cloud Vision, Cloud Storage                                        | Billing → Account Management — link billing@ or update                                          | [ ]    |
| **OpenAI**            | GPT APIs                                                           | Platform → Settings → Organization — add billing@ or update                                     | [ ]    |
| **Stripe**            | Payments (when active)                                             | Dashboard → Settings → Team — add billing@ as admin                                             | [ ]    |
| **Domain registrars** | Spaceship / Cloudflare / etc.                                      | Account → update contact email to billing@                                                      | [ ]    |
| **PostHog**           | Analytics                                                          | Project Settings → change billing email                                                         | [ ]    |
| **ElevenLabs**        | Voice clone                                                        | Account → update email                                                                          | [ ]    |
| **Cursor**            | IDE (Pro plan when upgraded)                                       | Cursor Settings → Account — use billing@ for subscription                                       | [ ]    |


---

## New Signups (use billing@ from day one)


| Service                       | When                                   | Notes                            |
| ----------------------------- | -------------------------------------- | -------------------------------- |
| **Vercel Pro**                | When 5-app monorepo triggers ($20/mo)  | Sign up with billing@            |
| **Cyber liability insurance** | Before first SSN                       | Use billing@ for policy + claims |
| **Affiliate networks**        | Impact.com, CJ — Plan B revenue        | Marcus, Wealthfront, Betterment  |
| **Column Tax**                | September 2026 (e-file partner)        | Use billing@                     |
| **April Tax**                 | If evaluated as Column Tax alternative | billing@                         |
| **Audit shield partner**      | Year 2                                 | TaxAudit or similar              |


---

## Aliases (already set up)

All route to your inbox; you choose the "send as" address:

- `billing@paperworklabs.com` — vendor invoices, subscriptions
- `hello@paperworklabs.com` — general contact
- `legal@paperworklabs.com` — contracts, legal
- `api@paperworklabs.com` — API support, developer inquiries

---

## Tips

- **Don’t change the login email** if it would lock you out. Add billing@ as a billing contact / team member instead.
- **Two-step where needed**: (1) Add billing@ as member, (2) Switch billing contact, (3) Remove personal if desired.
- **One at a time**: Migrate 1–2 vendors per session to avoid mistakes.

