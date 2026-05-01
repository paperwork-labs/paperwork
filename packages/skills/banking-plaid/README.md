# @paperwork/skills-banking-plaid

Plaid Link (OAuth-style connection flow), account listing, and `/transactions/sync` for Paperwork skills. Apps own Link UI, routing, token storage, and persistence; this package provides a typed `BankingPlaidClient` and normalized account/transaction shapes.

## API

- **`BankingPlaidClient`** — constructed with `PlaidConfig` (`clientId`, `secret`, `env`: `sandbox` | `development` | `production`).
  - `createLinkToken(req)` — starts Link; defaults products to `transactions` + `balance`, country to `US`, language to `en`.
  - `exchangePublicToken(publicToken)` — exchanges the Link `public_token` for an access token and `item_id`.
  - `listAccounts(accessToken)` — depository/credit/etc. accounts with parsed balances.
  - `syncTransactions(accessToken, cursor?)` — incremental sync: `added`, `modified`, `removed` transaction ids, `nextCursor`, `hasMore`.

## Conventions

- Transaction **amounts** follow Plaid: positive = debit (outflow), negative = credit (inflow).
- **Development** Plaid tier uses base path `https://development.plaid.com` (SDK only ships sandbox + production constants).

## Future consumers

Cash-balance dashboards (Brain / Money MVP), bill auto-pay and reconciliation pipelines that need normalized bank feeds without embedding Plaid types in app code.
