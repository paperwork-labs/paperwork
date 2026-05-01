export type BrokerageId =
  | "schwab"
  | "fidelity"
  | "ibkr"
  | "tastytrade"
  | (string & {});

export type OAuthCredentials = {
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  scopes?: string[];
};

export type OAuthTokens = {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  scope: string[];
  raw: Record<string, unknown>;
};

export type AccountSummary = {
  accountId: string;
  accountType: string;
  custodianAccountNumber?: string;
  totalEquity?: { value: number; currency: string };
  cashBalance?: { value: number; currency: string };
};

export type Position = {
  symbol: string;
  quantity: number;
  averageCost?: number;
  marketValue?: { value: number; currency: string };
};

export type Transaction = {
  id: string;
  date: Date;
  type:
    | "buy"
    | "sell"
    | "dividend"
    | "deposit"
    | "withdrawal"
    | "fee"
    | "other";
  symbol?: string;
  quantity?: number;
  amount: { value: number; currency: string };
  description?: string;
};
