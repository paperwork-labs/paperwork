import type { BrokerageAdapter } from "../adapter.js";

export const schwabAdapter: BrokerageAdapter = {
  id: "schwab",
  buildAuthorizeUrl: (creds, opts) => {
    const url = new URL("https://api.schwabapi.com/v1/oauth/authorize");
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", creds.clientId);
    url.searchParams.set("redirect_uri", creds.redirectUri);
    url.searchParams.set("scope", (creds.scopes ?? ["read"]).join(" "));
    if (opts?.state) url.searchParams.set("state", opts.state);
    return url.toString();
  },
  exchangeCode: async () => {
    throw new Error("Not implemented: Schwab OAuth exchange");
  },
  refreshTokens: async () => {
    throw new Error("Not implemented");
  },
  listAccounts: async () => {
    throw new Error("Not implemented: Schwab adapter is a stub");
  },
  listPositions: async () => {
    throw new Error("Not implemented");
  },
  listTransactions: async () => {
    throw new Error("Not implemented");
  },
};
