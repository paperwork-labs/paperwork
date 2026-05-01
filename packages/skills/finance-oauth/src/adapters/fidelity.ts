import type { BrokerageAdapter } from "../adapter.js";

/** Stub only — authorize URL host/path may change when Fidelity OAuth is wired. */
export const fidelityAdapter: BrokerageAdapter = {
  id: "fidelity",
  buildAuthorizeUrl: (creds, opts) => {
    const url = new URL("https://oauth.fidelity.com/fs/oauth2/auth");
    url.searchParams.set("response_type", "code");
    url.searchParams.set("client_id", creds.clientId);
    url.searchParams.set("redirect_uri", creds.redirectUri);
    url.searchParams.set("scope", (creds.scopes ?? ["read"]).join(" "));
    if (opts?.state) url.searchParams.set("state", opts.state);
    return url.toString();
  },
  exchangeCode: async () => {
    throw new Error("Not implemented: Fidelity OAuth exchange");
  },
  refreshTokens: async () => {
    throw new Error("Not implemented: Fidelity OAuth refresh");
  },
  listAccounts: async () => {
    throw new Error("Not implemented: Fidelity adapter is a stub");
  },
  listPositions: async () => {
    throw new Error("Not implemented");
  },
  listTransactions: async () => {
    throw new Error("Not implemented");
  },
};
