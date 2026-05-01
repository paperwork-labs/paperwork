# @paperwork/skills-ledger

Append-only **double-entry ledger** primitives for TypeScript: balanced multi-currency postings, time-bounded balances, and account snapshots. Designed as a zero-runtime-dependency foundation for **Expenses**, **Bills**, and **AxiomFolio P&L** (apps own persistence and ETL).

## Install (monorepo)

```json
{
  "dependencies": {
    "@paperwork/skills-ledger": "workspace:*"
  }
}
```

## Usage

```ts
import { Ledger } from "@paperwork/skills-ledger";

const ledger = new Ledger();

ledger.append({
  description: "SaaS invoice",
  reference: "inv_123",
  postings: [
    { account: "expense:saas:vercel", amount: { value: 12_00, currency: "USD" } },
    { account: "asset:cash:operating", amount: { value: -12_00, currency: "USD" } },
  ],
});

ledger.balance("expense:saas:vercel");
ledger.snapshot();
ledger.filter((e) => e.reference === "inv_123");
```

Amounts use **minor units** (e.g. US cents). **Positive posting = debit, negative = credit.**

## Append-only invariants

1. **No removal or in-place edits** — append new `LedgerEntry` rows only.
2. **Double-entry** — for every entry, posting amounts sum to **zero per currency** (each currency balances independently).
3. **Stable reads** — `append`, `entries`, and `filter` return **deep copies**.
4. **Identity** — each entry has an `id` (default ULID-like) and UTC ISO-8601 `timestamp`.

## Build

```bash
pnpm -C packages/skills/ledger build
pnpm -C packages/skills/ledger test
```
