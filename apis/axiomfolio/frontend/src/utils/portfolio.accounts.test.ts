import { describe, it, expect } from 'vitest';

import {
  brokerAccountStableReactKey,
  normalizeBrokerAccountsForPositions,
} from './portfolio';

describe('normalizeBrokerAccountsForPositions', () => {
  it('drops rows without a finite numeric id (avoids coercing many rows to id 0)', () => {
    const malformed = [
      { broker: 'IBKR', account_number: 'U111' },
      { broker: 'CB', account_number: 'U222' },
    ] as Array<{ id?: number; account_number?: string; broker?: string }>;

    expect(normalizeBrokerAccountsForPositions(malformed)).toEqual([]);
  });

  it('never uses the literal string "undefined" as account_number', () => {
    const rows = normalizeBrokerAccountsForPositions([{ id: 7, broker: 'IBKR' }]);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.account_number).toBe('7');
    expect(rows[0]!.account_number).not.toBe('undefined');
  });

  it('produces pairwise unique stable React keys for normalized rows', () => {
    const rows = normalizeBrokerAccountsForPositions([
      { id: 1, account_number: 'A', broker: 'IBKR' },
      { id: 2, account_number: 'B', broker: 'IBKR' },
    ]);
    const keys = rows.map((r) => brokerAccountStableReactKey(r.broker, r.account_number, r.id));
    expect(new Set(keys).size).toBe(keys.length);
  });
});
