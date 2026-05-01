import type {
  AccountSummary,
  BrokerageId,
  OAuthCredentials,
  OAuthTokens,
  Position,
  Transaction,
} from "./types.js";

export interface BrokerageAdapter {
  readonly id: BrokerageId;

  buildAuthorizeUrl(
    creds: OAuthCredentials,
    opts?: { state?: string; pkce?: boolean },
  ): string;

  exchangeCode(
    creds: OAuthCredentials,
    code: string,
    opts?: { codeVerifier?: string },
  ): Promise<OAuthTokens>;

  refreshTokens(
    creds: OAuthCredentials,
    refreshToken: string,
  ): Promise<OAuthTokens>;

  listAccounts(tokens: OAuthTokens): Promise<AccountSummary[]>;

  listPositions(
    tokens: OAuthTokens,
    accountId: string,
  ): Promise<Position[]>;

  listTransactions(
    tokens: OAuthTokens,
    accountId: string,
    opts?: { since?: Date; limit?: number },
  ): Promise<Transaction[]>;
}
