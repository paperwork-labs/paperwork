/**
 * @paperwork/skill-ledger
 *
 * Double-entry ledger primitives for expense tracking,
 * categorization, and monthly totals.
 */

// ── Types ────────────────────────────────────────────────────────────

export interface LedgerEntry {
  id: string;
  date: string;
  description: string;
  amount: number;
  currency: string;
  category: string;
  vendor: string;
  source: string;
}

export interface LedgerFilter {
  category?: string;
  vendor?: string;
  source?: string;
  currency?: string;
  startDate?: string;
  endDate?: string;
}

// ── Ledger ───────────────────────────────────────────────────────────

export class Ledger {
  private entries: LedgerEntry[] = [];

  /** Add a new entry to the ledger. */
  addEntry(entry: LedgerEntry): void {
    this.entries.push(entry);
  }

  /** Retrieve entries, optionally filtered. */
  getEntries(filter?: LedgerFilter): LedgerEntry[] {
    if (!filter) return [...this.entries];

    return this.entries.filter((e) => {
      if (filter.category && e.category !== filter.category) return false;
      if (filter.vendor && e.vendor !== filter.vendor) return false;
      if (filter.source && e.source !== filter.source) return false;
      if (filter.currency && e.currency !== filter.currency) return false;
      if (filter.startDate && e.date < filter.startDate) return false;
      if (filter.endDate && e.date > filter.endDate) return false;
      return true;
    });
  }

  /**
   * Sum all entry amounts for a given month.
   * @param month - YYYY-MM format (e.g. "2026-04")
   */
  getMonthlyTotal(month: string): number {
    return this.entries
      .filter((e) => e.date.startsWith(month))
      .reduce((sum, e) => sum + e.amount, 0);
  }

  /**
   * Assign or re-assign a category to an entry (returns a new copy).
   * Useful for ML-based or rule-based auto-categorization pipelines.
   */
  categorize(entry: LedgerEntry, category: string): LedgerEntry {
    return { ...entry, category };
  }
}
