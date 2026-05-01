import { beforeEach, describe, expect, it, vi } from "vitest";

import { BankingPlaidClient } from "../client.js";

const linkTokenCreate = vi.fn();
const itemPublicTokenExchange = vi.fn();
const accountsGet = vi.fn();
const transactionsSync = vi.fn();

vi.mock("plaid", () => ({
  Configuration: vi.fn(),
  PlaidApi: vi.fn(function PlaidApiMock() {
    return {
      linkTokenCreate,
      itemPublicTokenExchange,
      accountsGet,
      transactionsSync,
    };
  }),
  PlaidEnvironments: {
    sandbox: "https://sandbox.plaid.com",
    production: "https://production.plaid.com",
  },
  Products: {
    Transactions: "transactions",
    Auth: "auth",
    Balance: "balance",
    Identity: "identity",
  },
  CountryCode: {
    Us: "US",
    Gb: "GB",
  },
}));

const baseConfig = {
  clientId: "client-id-test",
  secret: "secret-test",
  env: "sandbox" as const,
};

describe("BankingPlaidClient", () => {
  beforeEach(() => {
    linkTokenCreate.mockReset();
    itemPublicTokenExchange.mockReset();
    accountsGet.mockReset();
    transactionsSync.mockReset();
  });

  describe("createLinkToken", () => {
    it("returns link token and expiration", async () => {
      linkTokenCreate.mockResolvedValue({
        data: {
          link_token: "link-sandbox-abc",
          expiration: "2026-06-01T12:00:00.000Z",
        },
      });

      const client = new BankingPlaidClient(baseConfig);
      const out = await client.createLinkToken({
        userId: "user-1",
        clientName: "Acme",
      });

      expect(out.linkToken).toBe("link-sandbox-abc");
      expect(out.expiration).toEqual(new Date("2026-06-01T12:00:00.000Z"));
      expect(linkTokenCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          user: { client_user_id: "user-1" },
          client_name: "Acme",
        }),
      );
    });
  });

  describe("exchangePublicToken", () => {
    it("returns access token and item id", async () => {
      itemPublicTokenExchange.mockResolvedValue({
        data: {
          access_token: "access-token-xyz",
          item_id: "item-123",
        },
      });

      const client = new BankingPlaidClient(baseConfig);
      const out = await client.exchangePublicToken("public-tok");

      expect(out).toEqual({
        accessToken: "access-token-xyz",
        itemId: "item-123",
      });
      expect(itemPublicTokenExchange).toHaveBeenCalledWith({
        public_token: "public-tok",
      });
    });
  });

  describe("listAccounts", () => {
    it("returns parsed accounts and balances", async () => {
      accountsGet.mockResolvedValue({
        data: {
          item: { item_id: "item-abc" },
          accounts: [
            {
              account_id: "acc-1",
              name: "Checking",
              official_name: "Checking ··1234",
              mask: "1234",
              type: "depository",
              subtype: "checking",
              balances: {
                available: 100.5,
                current: 100.5,
                iso_currency_code: "USD",
              },
            },
          ],
        },
      });

      const client = new BankingPlaidClient(baseConfig);
      const accounts = await client.listAccounts("access-secret");

      expect(accounts).toHaveLength(1);
      expect(accounts[0]).toMatchObject({
        accountId: "acc-1",
        itemId: "item-abc",
        name: "Checking",
        officialName: "Checking ··1234",
        mask: "1234",
        type: "depository",
        subtype: "checking",
        balances: {
          available: 100.5,
          current: 100.5,
          iso_currency_code: "USD",
        },
      });
    });
  });

  describe("syncTransactions", () => {
    it("returns added, modified, removed buckets and cursor", async () => {
      transactionsSync.mockResolvedValue({
        data: {
          added: [
            {
              transaction_id: "t-new",
              account_id: "acc-1",
              date: "2026-04-15",
              authorized_date: "2026-04-14",
              amount: 42.5,
              iso_currency_code: "USD",
              merchant_name: "Coffee Shop",
              category: ["Food and Drink", "Restaurants"],
              pending: false,
              payment_channel: "in store",
            },
          ],
          modified: [
            {
              transaction_id: "t-moved",
              account_id: "acc-1",
              date: "2026-04-10",
              amount: -10,
              iso_currency_code: "USD",
              pending: true,
              payment_channel: "online",
            },
          ],
          removed: [{ transaction_id: "t-gone" }],
          next_cursor: "cursor-next",
          has_more: false,
        },
      });

      const client = new BankingPlaidClient(baseConfig);
      const sync = await client.syncTransactions("access-secret", "cursor-prev");

      expect(sync.added).toHaveLength(1);
      expect(sync.added[0]).toMatchObject({
        transactionId: "t-new",
        accountId: "acc-1",
        amount: { value: 42.5, currency: "USD" },
        merchantName: "Coffee Shop",
        category: ["Food and Drink", "Restaurants"],
        pending: false,
        paymentChannel: "in store",
      });
      expect(sync.modified).toHaveLength(1);
      expect(sync.modified[0]?.transactionId).toBe("t-moved");
      expect(sync.removed).toEqual([{ transactionId: "t-gone" }]);
      expect(sync.nextCursor).toBe("cursor-next");
      expect(sync.hasMore).toBe(false);

      expect(transactionsSync).toHaveBeenCalledWith({
        access_token: "access-secret",
        cursor: "cursor-prev",
      });
    });

    it("omits cursor when undefined", async () => {
      transactionsSync.mockResolvedValue({
        data: {
          added: [],
          modified: [],
          removed: [],
          next_cursor: "",
          has_more: false,
        },
      });

      const client = new BankingPlaidClient(baseConfig);
      await client.syncTransactions("access-secret");

      expect(transactionsSync).toHaveBeenCalledWith({
        access_token: "access-secret",
        cursor: undefined,
      });
    });
  });
});
