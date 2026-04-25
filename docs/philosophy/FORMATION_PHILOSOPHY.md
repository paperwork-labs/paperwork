---
owner: legal
last_reviewed: 2026-04-23
doc_kind: philosophy
domain: formation
status: active
---

# Formation Philosophy

Immutable rules for what LaunchFree, the legal persona, and any business-formation Brain output will and will not do. Edits require founder + `legal` persona ack.

Companion: `docs/PRD.md` (LaunchFree section) is the current architecture proxy until `docs/architecture/FORMATION_ARCHITECTURE.md` is split out.

## 1. We are NOT your lawyer

Every formation-domain Brain response — chat, draft document, filing reminder — MUST surface this disclaimer:

> "Paperwork Labs is a software platform that helps you complete forms. We are not your lawyer or registered agent. Information provided here is general guidance, not legal advice. For complex situations (multi-state operations, foreign founders, significant assets, partnerships, M&A, regulated industries), consult an attorney. We will refer you to one on request."

Disclaimer is rendered by the platform, not by the persona's prose. Removing it is a P0.

## 2. What LaunchFree will NOT auto-file

LaunchFree will NEVER:

- File a state Articles of Incorporation, Articles of Organization, or Certificate of Formation without explicit user click-to-file
- Submit IRS Form SS-4 (EIN) without user confirmation of the responsible party identity
- Move money to/from state filing fees without an explicit user payment authorization (Stripe-side confirmation, not just an in-app click)
- Sign on behalf of a user as registered agent unless the user has explicitly contracted us as their RA in a signed agreement
- File annual reports / franchise tax returns without the user's annual authorization (one-time per year, can be batched but not silent)
- Resolve a state notice (rejection, deficiency) without user awareness — we surface the notice within 24h

## 3. Multi-state caveats

Operations in any state we are not registered to do business in are forbidden:

- LaunchFree may form an LLC in any state (the user is the entity, not us)
- LaunchFree may NOT advertise services in a state where formation requires a licensed attorney without an attorney partner in that state
- LaunchFree may NOT represent itself as the user's registered agent in a state where we have not registered ourselves as a commercial RA

The persona MUST refuse and route to a referral when asked to operate in an unsupported state.

## 4. PII and document handling

Formation PII (founder SSN/ITIN, address, EIN, banking) inherits all rules from `DATA_PHILOSOPHY.md` and `TAX_PHILOSOPHY.md` plus:

1. **Operating agreements, bylaws, member resolutions** — drafts may be generated from templates; the user reviews and signs. We do NOT pre-sign with a digital signature on behalf of the user.
2. **EIN application data** is treated as tax PII — full TAX_PHILOSOPHY rules apply.
3. **Founder identity verification** is required before any state filing. We use a third-party KYC vendor (allowlisted in `docs/axiomfolio/privacy.md`); we do not store the raw ID document beyond the KYC provider's retention.
4. **Attorney work product** — drafts produced by a licensed-attorney partner are marked `attorney_drafted=true` in metadata and are not edited by automation.

## 5. What we will NOT claim

- We will **not** advertise that LaunchFree "saves you from needing a lawyer" — for simple LLC formation it can; for anything else it can't, and we should not pretend otherwise
- We will **not** market "asset protection" or "tax savings" as outcomes of LLC formation without the disclaimers from TAX_PHILOSOPHY §5
- We will **not** market in jurisdictions where commercial formation services are restricted to licensed attorneys
- We will **not** claim "rated #1" or similar superlatives without verifiable third-party ratings linked

## 6. Escalation triggers

These auto-page the founder + `legal` persona owner via Slack DM:

| Trigger | Why |
|---|---|
| State filing rejected for any user | response window varies by state |
| User-reported registered agent service failure (notice not delivered) | regulatory consequence |
| KYC failure pattern — same applicant flagged ≥ 2 times in 7 days | possible identity fraud signal |
| Any LaunchFree user receives a state notice for "doing business without registration" in a state we facilitated | systemic risk |
| Subpoena, civil investigative demand, or government inquiry to LaunchFree | engages company legal |

## 7. What we will NOT do

- We will **not** form a corporation or LLC for an applicant who fails KYC, regardless of revenue impact
- We will **not** file a "certificate of dissolution" or "withdrawal" without an explicit confirmation flow that surveys the user about debt, taxes, and existing contracts
- We will **not** ship a feature that nudges users to form additional entities they don't need ("most successful businesses have multiple LLCs!" — no)
- We will **not** ship an "AI legal advisor" that gives binding advice — the disclaimer in §1 is non-negotiable
- We will **not** integrate with a state portal we cannot maintain a certified path to. If a state changes their portal, we either update or pause that state.

## Lineage & amendments

Authored 2026-04-23 as part of Docs Streamline 2026 Q2. Append-only. Architecture companion (`FORMATION_ARCHITECTURE.md`) deferred to follow-up; current architecture lives in `docs/PRD.md` LaunchFree section.

### Amendments

_None yet._
