import type { BrokerageAdapter } from "../adapter.js";

/** Stub only — Tastytrade OAuth base URL may differ for sandbox vs prod. */
export const tastytradeAdapter: BrokerageAdapter = {
  id: "tastytrade",
  buildAuthorizeUrl: (creds, opts) => {
    const url = new URL("https://api.tastytrade.com/oauth/authorize");
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", creds.clientId);
    url.searchParams.set("redirect_uri", creds.redirectUri);
    url.searchParams.set("scope", (creds.scopes ?? ["read"]).join(" "));
    if (opts?.state) url.searchParams.set("state", opts.state);
    return url.toString();
  },
  exchangeCode: async () => {
    throw new Error("Not implemented: Tastytrade OAuth exchange");
  },
  refreshTokens: async () => {
    throw new Error("Not implemented: Tastytrade OAuth refresh");
  },
  listAccounts: async () => {
    throw new Error("Not implemented: Tastytrade adapter is a stub");
  },
  listPositions: async () => {
    throw new Error("Not implemented");
  },
  listTransactions: async () => {
    throw new Error("Not implemented");
  },
};
