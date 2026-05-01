import type { BrokerageAdapter } from "../adapter.js";

/** Stub only — IBKR Client Portal / OAuth endpoints vary by program; replace when implementing. */
export const ibkrAdapter: BrokerageAdapter = {
  id: "ibkr",
  buildAuthorizeUrl: (creds, opts) => {
    const url = new URL("https://api.ibkr.com/v1/oauth2/authorize");
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", creds.clientId);
    url.searchParams.set("redirect_uri", creds.redirectUri);
    url.searchParams.set("scope", (creds.scopes ?? ["read"]).join(" "));
    if (opts?.state) url.searchParams.set("state", opts.state);
    return url.toString();
  },
  exchangeCode: async () => {
    throw new Error("Not implemented: IBKR OAuth exchange");
  },
  refreshTokens: async () => {
    throw new Error("Not implemented: IBKR OAuth refresh");
  },
  listAccounts: async () => {
    throw new Error("Not implemented: IBKR adapter is a stub");
  },
  listPositions: async () => {
    throw new Error("Not implemented");
  },
  listTransactions: async () => {
    throw new Error("Not implemented");
  },
};
