export type AccountId = string; // e.g., "asset:cash:operating", "expense:saas:vercel"

export type Currency = "USD" | "EUR" | "INR" | (string & {});

export type Amount = { value: number; currency: Currency }; // value in minor units (cents)

export type LedgerEntry = {
  id: string; // ULID/UUID
  timestamp: string; // ISO 8601 UTC
  description: string;
  reference?: string; // external ref (invoice id, transaction id)
  metadata?: Record<string, unknown>;
  postings: Posting[]; // MUST sum to zero per currency
};

export type Posting = {
  account: AccountId;
  amount: Amount; // positive = debit, negative = credit
};

export type LedgerSnapshot = {
  asOf: string; // ISO 8601
  balances: Record<AccountId, Amount>;
};
