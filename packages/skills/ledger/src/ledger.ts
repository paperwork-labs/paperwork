import type {
  AccountId,
  Amount,
  Currency,
  LedgerEntry,
  LedgerSnapshot,
  Posting,
} from "./types";

function generateEntryId(): string {
  const alphabet = "0123456789abcdefghijklmnopqrstuvwxyz";
  let suffix = "";
  for (let i = 0; i < 16; i += 1) {
    suffix += alphabet[Math.floor(Math.random() * alphabet.length)];
  }
  return `${Date.now().toString(36)}${suffix}`;
}

function sumPerCurrency(postings: Posting[]): Map<Currency, number> {
  const sums = new Map<Currency, number>();
  for (const p of postings) {
    const c = p.amount.currency;
    sums.set(c, (sums.get(c) ?? 0) + p.amount.value);
  }
  return sums;
}

export function assertBalanced(postings: Posting[]): void {
  for (const [currency, sum] of sumPerCurrency(postings)) {
    if (sum !== 0) {
      throw new InvalidLedgerEntryError(
        `Postings must sum to zero per currency; ${String(currency)} totals ${sum} (minor units).`,
      );
    }
  }
}

function cloneAmount(a: Amount): Amount {
  return { value: a.value, currency: a.currency };
}

function clonePosting(p: Posting): Posting {
  return { account: p.account, amount: cloneAmount(p.amount) };
}

function cloneEntry(entry: LedgerEntry): LedgerEntry {
  return {
    id: entry.id,
    timestamp: entry.timestamp,
    description: entry.description,
    ...(entry.reference !== undefined ? { reference: entry.reference } : {}),
    ...(entry.metadata !== undefined
      ? { metadata: { ...entry.metadata } }
      : {}),
    postings: entry.postings.map(clonePosting),
  };
}

export class InvalidLedgerEntryError extends Error {
  override readonly name = "InvalidLedgerEntryError";

  constructor(message?: string) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export type AppendInput = Omit<LedgerEntry, "id" | "timestamp"> & {
  id?: string;
  timestamp?: string;
};

export class Ledger {
  private readonly _entries: LedgerEntry[] = [];

  constructor(initialEntries?: LedgerEntry[]) {
    if (!initialEntries?.length) return;
    for (const e of initialEntries) {
      assertBalanced(e.postings);
      this._entries.push(cloneEntry(e));
    }
  }

  append(input: AppendInput): LedgerEntry {
    const postings = input.postings.map(clonePosting);
    assertBalanced(postings);

    const stored: LedgerEntry = {
      id: input.id ?? generateEntryId(),
      timestamp: input.timestamp ?? new Date().toISOString(),
      description: input.description,
      postings,
      ...(input.reference !== undefined ? { reference: input.reference } : {}),
      ...(input.metadata !== undefined
        ? { metadata: { ...input.metadata } }
        : {}),
    };

    this._entries.push(stored);
    return cloneEntry(stored);
  }

  entries(): readonly LedgerEntry[] {
    return this._entries.map(cloneEntry);
  }

  balance(account: AccountId, asOf?: Date): Amount {
    const cutoff = asOf?.toISOString();
    const sums = new Map<Currency, number>();

    for (const entry of this._entries) {
      if (cutoff !== undefined && entry.timestamp > cutoff) continue;
      for (const p of entry.postings) {
        if (p.account !== account) continue;
        const c = p.amount.currency;
        sums.set(c, (sums.get(c) ?? 0) + p.amount.value);
      }
    }

    if (sums.size === 0) {
      return { value: 0, currency: "USD" };
    }

    const nonZero = [...sums.entries()].filter(([, v]) => v !== 0);
    if (nonZero.length === 0) {
      const [currency] = sums.keys();
      return { value: 0, currency };
    }
    if (nonZero.length > 1) {
      throw new InvalidLedgerEntryError(
        `Account "${account}" has non-zero balances in more than one currency; inspect postings or use filter().`,
      );
    }
    const [currency, value] = nonZero[0]!;
    return { value, currency };
  }

  snapshot(asOf?: Date): LedgerSnapshot {
    const cutoff = asOf?.toISOString();
    const accounts = new Set<AccountId>();

    for (const entry of this._entries) {
      if (cutoff !== undefined && entry.timestamp > cutoff) continue;
      for (const p of entry.postings) {
        accounts.add(p.account);
      }
    }

    const asOfIso = asOf?.toISOString() ?? new Date().toISOString();
    const balances: Record<AccountId, Amount> = {};
    const asOfDate = asOf;

    for (const account of accounts) {
      balances[account] = this.balance(account, asOfDate);
    }

    return { asOf: asOfIso, balances };
  }

  filter(predicate: (entry: LedgerEntry) => boolean): LedgerEntry[] {
    return this._entries.map(cloneEntry).filter(predicate);
  }
}
