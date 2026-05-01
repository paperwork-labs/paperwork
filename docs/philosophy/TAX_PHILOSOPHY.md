---
owner: cpa
last_reviewed: 2026-04-23
doc_kind: philosophy
domain: tax
status: active
---

# Tax Philosophy

Immutable rules for what FileFree, the CPA persona, the EA persona, and any tax-related Brain output will and will not do. Edits require founder + `cpa` persona + `tax-domain` persona ack.

Companion: `docs/PRD.md` (FileFree section) is the current architecture proxy until `docs/architecture/TAX_ARCHITECTURE.md` is split out.

## 1. We are NOT your CPA, EA, or attorney

Every tax-domain Brain response — chat, draft return, reminder, summary — MUST surface this disclaimer:

> "Paperwork Labs is a software platform. Information provided here is general guidance based on publicly available IRS and state rules. It is not personal tax, legal, or financial advice. For your specific situation, consult a licensed CPA or EA. We will refer you to one on request."

The disclaimer is rendered by the platform (banner + footer in returns, banner above chat); it is not the persona's job to remember to type it. Removing the disclaimer is a P0.

## 2. What FileFree will NOT auto-do

FileFree will NEVER:

- File a return without explicit user click-to-sign on Form 8879 (or state equivalent)
- Submit an extension without explicit user confirmation
- Move money to/from the IRS or state revenue (no auto-debit, no auto-withdrawal of estimated tax)
- Sign Form 2848 (Power of Attorney) on behalf of a user
- Represent a user in an IRS audit, correspondence, or notice response — that's an EA / attorney job; we surface the notice and connect to a human

What we WILL do:

- Pre-fill returns from broker / W-2 / 1099 imports
- Catch obvious errors (math, missing forms, wrong AGI threshold)
- Draft response letters for IRS notices — always reviewed by a human EA before send
- Schedule reminders for estimated tax deadlines
- Maintain a verifiable transcript of every decision a user made (audit trail)

## 3. PII handling beyond Data Philosophy

Tax PII (SSN, ITIN, EIN, AGI, dependents, brokerage account numbers) inherits all rules from `DATA_PHILOSOPHY.md` plus:

1. **Display masking**: SSN shows as `***-**-1234` everywhere except the explicit "Edit SSN" form. The form requires re-auth (password or biometric).
2. **No SSN in logs, ever**, even masked. The `redact_credentials` log filter has explicit SSN regex.
3. **No SSN in LLM prompts**, even masked. The PII scrubber substitutes `<SSN_USER_<id>>` and the substitution table is server-only, never sent to a vendor.
4. **Retention**: tax PII is kept 7 years past return year (IRS requirement). After that, hard delete with audit log entry.
5. **State sharing**: federal-only data NEVER auto-flows to state filings unless the user opts in per state. We do not assume reciprocity.

## 4. EFIN / e-file rules

When we are the e-file transmitter (post-EFIN approval):

- Every transmission goes through a `tax-domain` persona pre-flight check (math, schema, prior-year mismatch)
- Acknowledgment from IRS MeF goes into `bronze.efile_ack` with raw payload + parsed status
- A rejected return surfaces a Slack alert to `#filefree-ops` AND a user notification within 5 minutes
- We retain transmitter logs for the IRS-required period (currently 7 years per Pub 1345)
- Any change to the transmitter pipeline requires the `cpa` persona's review (not just engineering)

## 5. What we will NOT claim

- We will **not** advertise that FileFree "guarantees the maximum refund" or any phrasing implying we beat human CPAs. We support, we don't replace.
- We will **not** advertise tax savings figures we can't substantiate from real user cohorts (and even then, with disclaimers)
- We will **not** market to users in jurisdictions we are not licensed/registered to operate in
- We will **not** auto-claim credits/deductions a user didn't explicitly answer questions for. No "we noticed you might qualify for X — applied!" without an opt-in click.

## 6. Escalation triggers

These auto-page the founder + `cpa` persona owner via Slack DM:

| Trigger                                                                             | Why                               |
|-------------------------------------------------------------------------------------|-----------------------------------|
| IRS notice received for any user                                                    | response window is short          |
| Return rejected by IRS MeF for the same reason ≥ 3 times in 24h                     | systemic issue                    |
| User reports a math error post-filing                                               | refile or amendment may be needed |
| Any FileFree tier-1 service down for > 5 min during filing season (Jan 15 – Apr 30) | revenue + user trust event        |
| Any single user's PII unmasked in a UI, log, or API response                        | P0                                |

## 7. What we will NOT do

- We will **not** auto-amend a filed return without explicit user authorization for THAT amendment
- We will **not** charge a user for software AND a CPA referral fee from the same return without disclosing both
- We will **not** ship features that nudge users toward more aggressive deductions for our SEO benefit
- We will **not** ship an "AI tax coach" that gives binding advice — the disclaimer in §1 is non-negotiable

## Lineage & amendments

Authored 2026-04-23 as part of Docs Streamline 2026 Q2. Append-only. Architecture companion (`TAX_ARCHITECTURE.md`) deferred to follow-up; current architecture lives in `docs/PRD.md` FileFree section and `docs/EFIN_FILING_INSTRUCTIONS.md`.

### Amendments

_None yet._
