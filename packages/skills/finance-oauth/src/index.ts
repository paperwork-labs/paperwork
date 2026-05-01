export enum FinancialInstitution {
  SCHWAB = "SCHWAB",
  TASTYTRADE = "TASTYTRADE",
  IBKR = "IBKR",
  PLAID = "PLAID",
}

export type OAuthConfig = {
  institution: FinancialInstitution;
  clientId: string;
  redirectUri: string;
  scopes: string[];
};

export class FinanceOAuthClient {
  getAuthUrl(_config: OAuthConfig): string {
    throw new Error("FinanceOAuthClient.getAuthUrl: not implemented");
  }

  exchangeCode(_code: string): Promise<unknown> {
    throw new Error("FinanceOAuthClient.exchangeCode: not implemented");
  }

  refreshToken(_token: string): Promise<unknown> {
    throw new Error("FinanceOAuthClient.refreshToken: not implemented");
  }

  revokeAccess(_token: string): Promise<void> {
    throw new Error("FinanceOAuthClient.revokeAccess: not implemented");
  }
}
