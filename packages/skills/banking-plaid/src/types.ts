export type PlaidConfig = {
  clientId: string;
  secret: string;
  env: "sandbox" | "development" | "production";
};

export type LinkTokenRequest = {
  userId: string;
  clientName?: string;
  products?: ("transactions" | "auth" | "balance" | "identity")[];
  language?: string;
  countryCodes?: string[];
};

export type LinkTokenResponse = {
  linkToken: string;
  expiration: Date;
};

export type AccessTokenResponse = {
  accessToken: string;
  itemId: string;
};

export type BankAccount = {
  accountId: string;
  itemId: string;
  name: string;
  officialName?: string;
  mask?: string;
  type: "depository" | "credit" | "loan" | "investment" | "other";
  subtype?: string;
  balances: {
    available: number | null;
    current: number;
    iso_currency_code: string;
  };
};

export type BankTransaction = {
  transactionId: string;
  accountId: string;
  date: Date;
  authorizedDate?: Date;
  amount: { value: number; currency: string };
  merchantName?: string;
  category?: string[];
  pending: boolean;
  paymentChannel?: "online" | "in store" | "other";
};
