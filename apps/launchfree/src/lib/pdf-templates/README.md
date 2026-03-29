# PDF templates — LLC formation documents

## Overview

This directory contains [React PDF](https://react-pdf.org/) (`@react-pdf/renderer`) components that render **state-specific LLC formation documents**, primarily **Articles of Organization** (or the state’s equivalent, such as a **Certificate of Formation**). LaunchFree uses them to generate downloadable PDFs that align with each Secretary of State’s (or Division of Corporations’) expectations for structure and required disclosures.

These templates are **not** a substitute for legal advice. They implement our best-effort mapping of public filing requirements; filers remain responsible for accuracy and for any state-specific steps beyond the PDF (e.g., publication, registered agent designation, online-only workflows).

---

## State coverage

Fees below are the **amounts used in product and filing-engine validation** and must stay aligned with `packages/data/src/portals/fees.ts` and `packages/filing-engine` portal configs. **Re-verify on the official source before changing numbers.**

| State | Official form / document name | Filing fee (USD) | Fee source | Statute reference (verify current) | Last verified |
| ----- | ------------------------------ | ---------------- | ---------- | ----------------------------------- | ------------- |
| **CA** | Form **LLC-1** — Articles of Organization | **$70** standard; **$350** 24-hour expedited | [CA SOS business entity forms](https://www.sos.ca.gov/business-programs/business-entities/forms) | Cal. Corp. Code § 17702.01 et seq. | 2026-03-28 |
| **TX** | Form **205** — Certificate of Formation (LLC) | **$300** | [TX SOS corporate forms](https://www.sos.state.tx.us/corp/forms_702.shtml) | Tex. Bus. Orgs. Code § 3.005 | 2026-03-28 |
| **FL** | Articles of Organization — LLC | **$125** ($100 filing + $25 registered agent designation, when applicable) | [FL Sunbiz forms & fees](https://dos.fl.gov/sunbiz/forms/fees/) | Fla. Stat. § 605.0201 | 2026-03-28 |
| **DE** | Certificate of Formation — LLC | **$90** | [DE Division of Corporations fees](https://corp.delaware.gov/fee.shtml) | Del. LLC Act § 18-201 | 2026-03-28 |
| **WY** | Articles of Organization | **$100** (typical online filing; confirm channel) | [WY SOS business fees (PDF)](https://sos.wyo.gov/Business/docs/BusinessFees.pdf) | Wyo. Stat. § 17-29-201 | 2026-03-28 |
| **NY** | Articles of Organization | **$200** | [NY DOS fee schedules](https://dos.ny.gov/fee-schedules) | NY LLC Law § 203 | 2026-03-28 |
| **NV** | Articles of Organization | **$425** typical total at formation (**$75** articles + **$150** initial list + **$200** state business license — confirm current breakdown) | [NV SOS forms & fees](https://www.nvsos.gov/businesses/commercial-recordings/forms-fees) | NRS Chapter 86 | 2026-03-28 |
| **IL** | Form **LLC-5.5** — Articles of Organization | **$150** | [IL SOS LLC instructions](https://www.ilsos.gov/departments/business_services/organization/llc_instructions.html) | 805 ILCS 180/5-5 | 2026-03-28 |
| **GA** | Articles of Organization | **$100** | [GA SOS Corporations Division](https://sos.ga.gov/corporations-division) | O.C.G.A. § 14-11-203 | 2026-03-28 |
| **WA** | Certificate of Formation | **$180** | [WA SOS fee schedule](https://apps.sos.wa.gov/corps/feescheduleexpeditedservice.aspx) | RCW 25.15.071 | 2026-03-28 |

---

## Data quality requirements

1. **Fees** — Every dollar amount in templates, UI copy, and `STATE_FILING_FEES` must match the **official state SOS (or Division of Corporations) fee schedule** at the time of the change. If a state bundles multiple charges (e.g., NV), document the breakdown in code comments and keep totals consistent with product billing expectations.
2. **Statutes and rules** — Law citations (statute sections, act names) must be **current** for the filing year. When legislatures renumber or amend sections, update both this README’s table and inline template comments.
3. **Form names and terminology** — Use the **exact official names** (e.g., “Certificate of Formation” vs. “Articles of Organization,” form numbers like LLC-1, 205, LLC-5.5). Do not substitute colloquial labels in user-visible PDF titles or fee lines.
4. **Change control** — Any update to fees, statutes, form names, or required fields requires a **pull request with review**. Prefer linking the verifying official URL in the PR description.

---

## Official sources (primary fee / forms pages)

Use these pages as the starting point for manual verification:

| State | URL |
| ----- | --- |
| **CA** | https://www.sos.ca.gov/business-programs/business-entities/forms |
| **TX** | https://www.sos.state.tx.us/corp/forms_702.shtml |
| **FL** | https://dos.fl.gov/sunbiz/forms/fees/ |
| **DE** | https://corp.delaware.gov/fee.shtml |
| **WY** | https://sos.wyo.gov/Business/docs/BusinessFees.pdf |
| **NY** | https://dos.ny.gov/fee-schedules |
| **NV** | https://www.nvsos.gov/businesses/commercial-recordings/forms-fees |
| **IL** | https://www.ilsos.gov/departments/business_services/organization/llc_instructions.html |
| **GA** | https://sos.ga.gov/corporations-division |
| **WA** | https://apps.sos.wa.gov/corps/feescheduleexpeditedservice.aspx |

---

## Adding a new state

1. **Research** — From the official SOS site, capture form name/number, standard filing fee, expedited options, statute references, and any fields that must appear on the filing (registered agent, principal office, management structure, etc.).
2. **Data layer** — Add the state to `packages/data/src/portals/fees.ts` (`STATE_FILING_FEES` and `STATE_NAMES`) and extend the filing-engine portal JSON under `packages/data/src/portals/` if the state is supported for automation.
3. **Template file** — Add `{state}-articles.tsx` (or `{state}-certificate.tsx` if that matches official terminology), following existing patterns: `StyleSheet`, props interface, and `Document`/`Page` layout consistent with other states.
4. **Exports & generation** — Wire the component into whatever module generates PDFs (e.g., `generate-pdf.tsx` or API routes) and export types from `index.ts` if this package should re-export the template.
5. **Validation** — Update `packages/filing-engine/src/__tests__/portal-configs.test.ts` (`OFFICIAL_FEES`, `OFFICIAL_PORTAL_URLS`, `SUPPORTED_STATES`) so automated checks stay in sync.
6. **Documentation** — Add a row to the **State coverage** table above with fee, source URL, statute, and **last verified** date.
7. **PR** — Open a PR; include links to the official pages used for verification.

---

## Testing

There are **no Vitest tests inside `apps/launchfree`** targeting these PDF components today. Use the following to validate related configuration and catch fee drift:

**Filing engine (fee and portal URL accuracy)**

From the repository root:

```bash
pnpm --filter @paperwork-labs/filing-engine test
```

Focused scripts (from the same package):

```bash
pnpm --filter @paperwork-labs/filing-engine test:fees
pnpm --filter @paperwork-labs/filing-engine validate
```

**LaunchFree TypeScript (templates compile)**

```bash
pnpm --filter @paperwork-labs/launchfree type-check
```

**Monorepo-wide**

```bash
pnpm test
```

After changing any template, manually generate a sample PDF in dev and confirm layout, required labels, and fee text against the current official form or instructions.
