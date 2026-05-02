---
last_reviewed: 2026-05-02
doc_kind: runbook
---

# Email deliverability (SPF + DMARC)

> **Category**: setup
> **Owner**: @infra-ops
> **Last verified**: 2026-05-02
> **Status**: active

**TL;DR:** What SPF and DMARC do for `paperworklabs.com`, how to apply records from this repo, and how to tighten DMARC after a soak. Read before changing mail-related DNS.

## Why this exists

**SPF (Sender Policy Framework)** is a DNS TXT record at the domain apex that lists which mail systems are allowed to send email *as* your domain. Receiving servers use it to detect spoofing.

**DMARC (Domain-based Message Authentication, Reporting & Conformance)** is a DNS TXT record at `_dmarc.<domain>` that tells receivers what to do when SPF or DKIM checks do not align with the visible `From:` domain, and where to send aggregate / forensic reports.

Without SPF and DMARC, legitimate mail from `founder@paperworklabs.com`, product notifications, and Clerk transactional messages is easier to mark as spam or spoof.

## Current policy (paperworklabs.com)

| Mechanism | Purpose |
|-----------|---------|
| Google Workspace | Human mail (`smtp.google.com` / MX). SPF includes Postmark’s documented include: `include:_spf.google.com`. |
| Clerk (transactional) | Clerk sends via **Postmark**; Postmark’s SPF include is `include:spf.mtasv.net` (see [Postmark SPF setup](https://postmarkapp.com/support/article/how-do-i-set-up-spf-for-postmark)). |

The apex SPF string we maintain is:

`v=spf1 include:_spf.google.com include:spf.mtasv.net -all`

`-all` means “anything not covered by the includes fails SPF” — strict, appropriate for a low-volume corporate domain.

DMARC starts at **`p=quarantine`** so misaligned mail is softened rather than dropped while we collect reports. After a soak period with clean reports, tighten to **`p=reject`** (see workstream **WS-38-tighten-dmarc-p-reject** and the section below).

### Applying DNS from this repo

```bash
# Requires CLOUDFLARE_API_TOKEN or scripts/vault-get.sh CLOUDFLARE_API_TOKEN
python3 scripts/dns_set_spf_dmarc.py
python3 scripts/dns_set_spf_dmarc.py --check-only
```

## Adding another sender later

SPF allows a limited number of DNS lookups. Each `include:` counts toward that budget.

Examples (do **not** add until you actually send from that vendor):

| Provider | Typical SPF fragment |
|----------|----------------------|
| SendGrid | `include:sendgrid.net` |
| Mailgun | `include:mailgun.org` |
| Amazon SES | `include:amazonses.com` |

Edit `scripts/dns_set_spf_dmarc.py` (`SPF_CONTENT`), re-run the script, then verify with `dig` (see script docstring / PR notes).

## Reading DMARC reports

DMARC `rua` / `ruf` addresses receive XML (and sometimes zipped) reports from participating receivers.

- **Postmark** offers a free DMARC digest tool: [postmarkapp.com/dmarc](https://postmarkapp.com/dmarc) — useful as an aggregator once you point `rua` at an address they give you, or use their importer.
- Until then, monitor the mailbox `dmarc@paperworklabs.com` (or adjust `rua` / `ruf` in the script if you use a dedicated ingest address).

## Tightening `p=quarantine` → `p=reject`

1. Run with **`p=quarantine`** for at least **30 days** while monitoring reports.
2. Confirm legitimate sources (Google, Clerk/Postmark, any marketing tool) pass SPF/DKIM alignment.
3. Update `DMARC_CONTENT` in `scripts/dns_set_spf_dmarc.py` to `p=reject`, re-run the script, verify with `dig`.

Misconfiguration with `p=reject` can cause valid mail to bounce — only tighten after evidence.

## Other production domains

**axiomfolio.com**, **filefree.ai**, **launchfree.ai**, and **distill.tax** are out of scope for this runbook’s automation; they will need the same treatment once each domain sends outbound mail from known providers. Use separate workstreams / PRs per zone.
