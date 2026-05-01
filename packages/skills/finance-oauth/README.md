# `@paperwork/skills-finance-oauth`

Thin, provider-agnostic scaffolding for **OAuth 2.0 / PKCE** and a **`BrokerageAdapter`** interface aimed at brokerages and financial data providers (Schwab, Fidelity, Interactive Brokers, Tastytrade, and similar). Apps own routing, persistence, and vaulting; this package supplies URL builders, PKCE helpers, and typed contracts so **Axiomfolio** (and other clients) can link accounts consistently.

## Install

Workspace dependency:

```json
{
  "dependencies": {
    "@paperwork/skills-finance-oauth": "workspace:*"
  }
}
```

## PKCE helpers

Use [`RFC 7636`](https://datatracker.ietf.org/doc/html/rfc7636) helpers before redirecting the user to an authorize URL:

- `generateCodeVerifier(length?)` — random base64url string (43–128 chars).
- `generateCodeChallenge(verifier)` — SHA-256 S256 challenge (base64url).
- `buildPkceUrl(authUrl, params)` — merge query params (e.g. `code_challenge`, `code_challenge_method`) into the provider authorize URL.

The caller typically stores the verifier server-side (session) and passes `code_verifier` when exchanging the authorization code.

## `BrokerageAdapter`

Implementors expose:

| Method | Purpose |
|--------|---------|
| `buildAuthorizeUrl(creds, opts?)` | Authorization redirect URL (`state`, optional PKCE flags). |
| `exchangeCode(creds, code, opts?)` | Trade auth code (+ optional `codeVerifier`) for tokens. |
| `refreshTokens(creds, refreshToken)` | Rotate access token. |
| `listAccounts(tokens)` | Connected accounts summary. |
| `listPositions(tokens, accountId)` | Holdings for one account. |
| `listTransactions(tokens, accountId, opts?)` | Cash ledger / activity with optional `since` / `limit`. |

`OAuthCredentials` carries `clientId`, `clientSecret`, `redirectUri`, and optional `scopes`. **Never ship secrets to the browser** — keep adapter calls on the server.

## Bundled stubs

`brokerageAdapterRegistry` maps **`schwab`**, **`fidelity`**, **`ibkr`**, and **`tastytrade`** to stub adapters:

- **`buildAuthorizeUrl`** builds a plausible authorize URL (parameters only; no secrets).
- **All other methods throw** with clear `Not implemented` messages — no synthetic positions, balances, or transactions.

Authorize endpoints for non-Schwab stubs are **placeholders** until provider-specific docs are wired; replace per vendor OAuth documentation.

## Adding a real adapter

1. Create `src/adapters/<provider>.ts` implementing `BrokerageAdapter`.
2. Export from `src/index.ts` and register in `brokerageAdapterRegistry` if shared.
3. Store refresh tokens encrypted at rest using your vault pattern (see skills extraction roadmap).

## Scripts

- `pnpm build` — `tsup` ESM + types.
- `pnpm test` — Vitest.
