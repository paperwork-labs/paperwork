# @paperwork/skills-gmail-inbound

Foundation package for **Bills auto-ingestion**: Google OAuth for Gmail, pull-based message listing, MIME parsing with `mailparser`, and lightweight invoice heuristics (PDF + keywords, amounts, due dates).

## Install (workspace)

```json
{
  "dependencies": {
    "@paperwork/skills-gmail-inbound": "workspace:*"
  }
}
```

## OAuth setup (Google Cloud Console)

1. Create or reuse a Google Cloud project and enable the **Gmail API**.
2. Create an **OAuth 2.0 Client ID** and set the **Authorized redirect URI** to match `GmailInboundConfig.redirectUri`.
3. Scopes:
   - Default (read/list): `https://www.googleapis.com/auth/gmail.readonly`
   - **`markProcessed` also needs** `https://www.googleapis.com/auth/gmail.modify`

Never commit client secrets or real tokens.

## Usage

```ts
import { GmailInboundClient } from "@paperwork/skills-gmail-inbound";

const client = new GmailInboundClient({
  clientId: process.env.GMAIL_OAUTH_CLIENT_ID!,
  clientSecret: process.env.GMAIL_OAUTH_CLIENT_SECRET!,
  redirectUri: process.env.GMAIL_OAUTH_REDIRECT_URI!,
  scopes: [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
  ],
  knownVendorDomains: ["stripe.com"],
});

const url = client.buildAuthorizeUrl("state");
const tokens = await client.exchangeCode(code);
const messages = await client.list(tokens, { maxResults: 10 });
```

## Tests

```bash
pnpm -C packages/skills/gmail-inbound test
```

Fixture-based parser tests only; no Gmail API calls.
