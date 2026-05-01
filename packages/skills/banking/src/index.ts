export type BankAccount = {
  id: string;
  institution: string;
  accountType: string;
  balance: number;
  currency: string;
  lastSynced: string;
};

export type BankTransaction = {
  id: string;
  accountId: string;
  date: string;
  description: string;
  amount: number;
  category: string;
};

export abstract class BankingClient {
  abstract listAccounts(): Promise<BankAccount[]>;

  abstract getTransactions(
    accountId: string,
    since: string,
  ): Promise<BankTransaction[]>;

  abstract syncAccount(accountId: string): Promise<void>;
}
