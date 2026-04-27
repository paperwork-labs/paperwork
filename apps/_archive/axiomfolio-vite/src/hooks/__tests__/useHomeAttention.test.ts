import { describe, it, expect } from 'vitest';

import { deriveAttentionItems, type AttentionInputs } from '../useHomeAttention';
import type { EnrichedPosition } from '@/types/portfolio';

function pos(overrides: Partial<EnrichedPosition>): EnrichedPosition {
  return {
    id: 1,
    symbol: 'TEST',
    account_number: 'U1',
    broker: 'IBKR',
    shares: 10,
    current_price: 100,
    market_value: 1_000,
    cost_basis: 1_000,
    average_cost: 100,
    unrealized_pnl: 0,
    unrealized_pnl_pct: 0,
    ...overrides,
  } as EnrichedPosition;
}

const BASE: Omit<AttentionInputs, 'positions'> = {
  dividendSummary: null,
  realizedPnl: null,
  now: new Date(2026, 3, 22, 12, 0, 0),
};

describe('deriveAttentionItems', () => {
  it('returns an empty list when everything is null/undefined', () => {
    expect(
      deriveAttentionItems({
        positions: undefined,
        dividendSummary: undefined,
        realizedPnl: undefined,
        now: BASE.now,
      }),
    ).toEqual([]);
  });

  it('flags stage-4 positions as crit', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [pos({ id: 11, symbol: 'AAA', stage_label: '4B', unrealized_pnl_pct: -3 })],
    });
    expect(items).toHaveLength(1);
    expect(items[0].kind).toBe('stage-4');
    expect(items[0].tone).toBe('crit');
    expect(items[0].href).toBe('/holding/AAA');
  });

  it('flags deep drawdown as crit when stage is not Stage 4', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [pos({ id: 12, symbol: 'BBB', stage_label: '2A', unrealized_pnl_pct: -20 })],
    });
    expect(items[0].kind).toBe('drawdown');
    expect(items[0].tone).toBe('crit');
  });

  it('flags approaching-stop for -7% <= pnl > -15%', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [pos({ id: 13, symbol: 'CCC', stage_label: '2A', unrealized_pnl_pct: -8 })],
    });
    expect(items[0].kind).toBe('approaching-stop');
    expect(items[0].tone).toBe('warn');
  });

  it('flags runners (>= +20%) as ok', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [pos({ id: 14, symbol: 'DDD', stage_label: '2A', unrealized_pnl_pct: 25 })],
    });
    expect(items[0].kind).toBe('runner');
    expect(items[0].tone).toBe('ok');
  });

  it('ignores positions with pnl between -7% and +20%', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [pos({ id: 15, symbol: 'EEE', stage_label: '2A', unrealized_pnl_pct: 5 })],
    });
    expect(items).toEqual([]);
  });

  it('surfaces upcoming ex-div within 7 days and skips ones outside the window', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [],
      dividendSummary: {
        upcoming_ex_dates: [
          { symbol: 'AAPL', est_ex_date: '2026-04-24' },
          { symbol: 'MSFT', est_ex_date: '2026-06-01' },
          { symbol: 'OLD', est_ex_date: '2026-01-01' },
        ],
      },
    });
    expect(items.map((i) => i.kind)).toEqual(['ex-div']);
    expect(items[0].title).toContain('AAPL');
  });

  it('surfaces non-zero realized P&L as an ok row', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [],
      realizedPnl: 1_234.56,
    });
    expect(items).toHaveLength(1);
    expect(items[0].kind).toBe('realized');
    expect(items[0].title).toContain('$1,235');
  });

  it('orders items crit → warn → ok and caps to limit', () => {
    const items = deriveAttentionItems({
      ...BASE,
      positions: [
        pos({ id: 21, symbol: 'RUN', stage_label: '2A', unrealized_pnl_pct: 25 }),
        pos({ id: 22, symbol: 'CUT', stage_label: '4A', unrealized_pnl_pct: -1 }),
        pos({ id: 23, symbol: 'TIGHT', stage_label: '2A', unrealized_pnl_pct: -9 }),
        pos({ id: 24, symbol: 'DEEP', stage_label: '2A', unrealized_pnl_pct: -30 }),
      ],
      dividendSummary: {
        upcoming_ex_dates: [{ symbol: 'KO', est_ex_date: '2026-04-24' }],
      },
      realizedPnl: 500,
      limit: 5,
    });
    expect(items).toHaveLength(5);
    expect(items[0].tone).toBe('crit');
    expect(items[1].tone).toBe('crit');
    expect(items[2].tone).toBe('warn');
    expect(items[3].tone).toBe('warn');
    expect(items[4].tone).toBe('ok');
  });

  it('respects the limit parameter', () => {
    const many: EnrichedPosition[] = Array.from({ length: 20 }, (_, i) =>
      pos({ id: 100 + i, symbol: `S${i}`, stage_label: '4B', unrealized_pnl_pct: -5 }),
    );
    const items = deriveAttentionItems({ ...BASE, positions: many, limit: 3 });
    expect(items).toHaveLength(3);
  });
});
