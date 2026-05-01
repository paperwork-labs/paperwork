import {
  Configuration,
  CountryCode,
  PlaidApi,
  PlaidEnvironments,
  Products,
} from "plaid";
import type { AccountBase, AccountType, Transaction } from "plaid";

import type {
  BankAccount,
  BankTransaction,
  LinkTokenRequest,
  LinkTokenResponse,
  PlaidConfig,
} from "./types.js";

const PRODUCT_MAP: Record<
  NonNullable<LinkTokenRequest["products"]>[number],
  Products
> = {
  transactions: Products.Transactions,
  auth: Products.Auth,
  balance: Products.Balance,
  identity: Products.Identity,
};

const DEFAULT_PRODUCTS: NonNullable<LinkTokenRequest["products"]> = [
  "transactions",
  "balance",
];

function plaidBasePath(env: PlaidConfig["env"]): string {
  if (env === "production") return PlaidEnvironments.production;
  if (env === "development") return "https://development.plaid.com";
  return PlaidEnvironments.sandbox;
}

/** Uppercase ISO 3166-1 alpha-2, length-bounded; must be a Plaid-supported code. */
function toCountryCode(code: string): CountryCode {
  const normalized = code.trim().toUpperCase();
  if (normalized.length !== 2) {
    throw new Error(`Invalid country code: ${code}`);
  }
  const allowed = new Set<string>(Object.values(CountryCode));
  if (!allowed.has(normalized)) {
    throw new Error(`Unsupported Plaid country code: ${normalized}`);
  }
  return normalized as CountryCode;
}

function mapAccountType(type: AccountType | null | undefined): BankAccount["type"] {
  switch (type) {
    case "depository":
    case "credit":
    case "loan":
    case "investment":
    case "other":
      return type;
    default:
      return "other";
  }
}

function mapAccount(account: AccountBase, itemId: string): BankAccount {
  const balances = account.balances;
  const iso =
    balances?.iso_currency_code ??
    balances?.unofficial_currency_code ??
    "USD";
  return {
    accountId: account.account_id ?? "",
    itemId,
    name: account.name ?? "",
    officialName: account.official_name ?? undefined,
    mask: account.mask ?? undefined,
    type: mapAccountType(account.type),
    subtype: account.subtype ?? undefined,
    balances: {
      available:
        balances?.available != null ? Number(balances.available) : null,
      current: balances?.current != null ? Number(balances.current) : 0,
      iso_currency_code: iso,
    },
  };
}

function mapPaymentChannel(
  ch: Transaction["payment_channel"] | null | undefined,
): BankTransaction["paymentChannel"] {
  if (ch === "online" || ch === "in store" || ch === "other") return ch;
  return undefined;
}

function mapTransaction(tx: Transaction): BankTransaction {
  const currency =
    tx.iso_currency_code ?? tx.unofficial_currency_code ?? "USD";
  const dateStr = tx.date;
  if (!dateStr || typeof dateStr !== "string") {
    throw new Error("Plaid transaction missing date");
  }
  const auth = tx.authorized_date;
  return {
    transactionId: tx.transaction_id ?? "",
    accountId: tx.account_id ?? "",
    date: new Date(`${dateStr}T12:00:00.000Z`),
    authorizedDate:
      auth && typeof auth === "string"
        ? new Date(`${auth}T12:00:00.000Z`)
        : undefined,
    amount: { value: Number(tx.amount), currency },
    merchantName: tx.merchant_name ?? undefined,
    category: tx.category ?? undefined,
    pending: Boolean(tx.pending),
    paymentChannel: mapPaymentChannel(tx.payment_channel),
  };
}

export class BankingPlaidClient {
  private readonly plaid: PlaidApi;

  constructor(private readonly config: PlaidConfig) {
    const configuration = new Configuration({
      basePath: plaidBasePath(config.env),
      baseOptions: {
        headers: {
          "PLAID-CLIENT-ID": config.clientId,
          "PLAID-SECRET": config.secret,
        },
      },
    });
    this.plaid = new PlaidApi(configuration);
  }

  async createLinkToken(req: LinkTokenRequest): Promise<LinkTokenResponse> {
    const products = (req.products ?? DEFAULT_PRODUCTS).map(
      (p) => PRODUCT_MAP[p],
    );
    const country_codes = (req.countryCodes ?? ["US"]).map(toCountryCode);
    const language = req.language ?? "en";

    const { data } = await this.plaid.linkTokenCreate({
      user: { client_user_id: req.userId },
      client_name: req.clientName ?? "Paperwork",
      products,
      country_codes,
      language,
    });

    return {
      linkToken: data.link_token,
      expiration: new Date(data.expiration),
    };
  }

  async exchangePublicToken(
    publicToken: string,
  ): Promise<{ accessToken: string; itemId: string }> {
    const { data } = await this.plaid.itemPublicTokenExchange({
      public_token: publicToken,
    });
    return {
      accessToken: data.access_token,
      itemId: data.item_id,
    };
  }

  async listAccounts(accessToken: string): Promise<BankAccount[]> {
    const { data } = await this.plaid.accountsGet({
      access_token: accessToken,
    });
    const itemId = data.item.item_id;
    return (data.accounts ?? []).map((a) => mapAccount(a, itemId));
  }

  async syncTransactions(
    accessToken: string,
    cursor?: string,
  ): Promise<{
    added: BankTransaction[];
    modified: BankTransaction[];
    removed: { transactionId: string }[];
    nextCursor: string;
    hasMore: boolean;
  }> {
    const { data } = await this.plaid.transactionsSync({
      access_token: accessToken,
      cursor: cursor || undefined,
    });

    return {
      added: (data.added ?? []).map(mapTransaction),
      modified: (data.modified ?? []).map(mapTransaction),
      removed: (data.removed ?? []).map((row) => ({
        transactionId:
          typeof row === "string"
            ? row
            : (row as { transaction_id?: string }).transaction_id ?? "",
      })),
      nextCursor: data.next_cursor,
      hasMore: Boolean(data.has_more),
    };
  }
}
