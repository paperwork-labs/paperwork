import type { BrokerageAdapter } from "./adapter.js";
import { fidelityAdapter } from "./adapters/fidelity.js";
import { ibkrAdapter } from "./adapters/ibkr.js";
import { schwabAdapter } from "./adapters/schwab.js";
import { tastytradeAdapter } from "./adapters/tastytrade.js";

export type {
  AccountSummary,
  BrokerageId,
  OAuthCredentials,
  OAuthTokens,
  Position,
  Transaction,
} from "./types.js";

export type { BrokerageAdapter } from "./adapter.js";

export {
  buildPkceUrl,
  generateCodeChallenge,
  generateCodeVerifier,
} from "./oauth.js";

export { fidelityAdapter, ibkrAdapter, schwabAdapter, tastytradeAdapter };

/** Lookup table for bundled stub adapters (extend at app layer as providers land). */
export const brokerageAdapterRegistry: Record<string, BrokerageAdapter> = {
  schwab: schwabAdapter,
  fidelity: fidelityAdapter,
  ibkr: ibkrAdapter,
  tastytrade: tastytradeAdapter,
};
