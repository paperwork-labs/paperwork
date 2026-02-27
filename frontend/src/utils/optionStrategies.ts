export type OptionPos = {
  id: number;
  symbol: string;
  underlying_symbol: string;
  strike_price: number;
  expiration_date: string | null;
  option_type: string;
  quantity: number;
  average_open_price?: number;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  days_to_expiration?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  implied_volatility?: number;
  underlying_price?: number;
  cost_basis?: number;
  realized_pnl?: number;
  commission?: number;
  currency?: string;
  account_id?: number;
};

export type StrategyLabel =
  | 'Vertical Spread'
  | 'Straddle'
  | 'Strangle'
  | 'Iron Condor'
  | 'Iron Butterfly'
  | 'Covered Call'
  | 'Cash-Secured Put'
  | 'Calendar Spread'
  | 'Diagonal Spread'
  | 'Butterfly'
  | null;

export type CreditDebit = 'credit' | 'debit' | 'even' | null;

export interface StrategyGroup {
  label: StrategyLabel;
  positions: OptionPos[];
  netPnl: number;
  netDelta: number;
  creditDebit: CreditDebit;
  netPremium: number;
  maxProfit: number | null;
  maxLoss: number | null;
  breakevens: number[];
  combinedGreeks: {
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
  };
}

function sumGreeks(positions: OptionPos[]) {
  return {
    delta: positions.reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0),
    gamma: positions.reduce((s, p) => s + Number(p.gamma ?? 0) * p.quantity, 0),
    theta: positions.reduce((s, p) => s + Number(p.theta ?? 0) * p.quantity, 0),
    vega: positions.reduce((s, p) => s + Number(p.vega ?? 0) * p.quantity, 0),
  };
}

function netPremium(positions: OptionPos[]): number {
  return positions.reduce((s, p) => s + Number(p.cost_basis ?? 0), 0);
}

function creditDebitFromPremium(premium: number): CreditDebit {
  if (premium < -0.01) return 'credit';
  if (premium > 0.01) return 'debit';
  return 'even';
}

function makeGroup(
  label: StrategyLabel,
  positions: OptionPos[],
  extras?: { maxProfit?: number | null; maxLoss?: number | null; breakevens?: number[] },
): StrategyGroup {
  const premium = netPremium(positions);
  return {
    label,
    positions,
    netPnl: positions.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0),
    netDelta: positions.reduce((s, p) => s + Number(p.delta ?? 0) * p.quantity, 0),
    creditDebit: creditDebitFromPremium(premium),
    netPremium: premium,
    maxProfit: extras?.maxProfit ?? null,
    maxLoss: extras?.maxLoss ?? null,
    breakevens: extras?.breakevens ?? [],
    combinedGreeks: sumGreeks(positions),
  };
}

export function detectStrategies(
  positions: OptionPos[],
  stockPositions?: Array<{ symbol: string; quantity: number }>,
): StrategyGroup[] {
  const groups: StrategyGroup[] = [];
  const used = new Set<number>();

  const byUnderlying = new Map<string, OptionPos[]>();
  for (const p of positions) {
    const sym = p.underlying_symbol;
    if (!byUnderlying.has(sym)) byUnderlying.set(sym, []);
    byUnderlying.get(sym)!.push(p);
  }

  // Covered Call & Cash-Secured Put (span options + stock positions)
  if (stockPositions) {
    const stockMap = new Map<string, number>();
    for (const sp of stockPositions) {
      stockMap.set(sp.symbol, (stockMap.get(sp.symbol) ?? 0) + sp.quantity);
    }
    for (const [sym, symPositions] of byUnderlying) {
      const stockQty = stockMap.get(sym) ?? 0;
      if (stockQty <= 0) continue;
      const shortCalls = symPositions.filter(
        p => !used.has(p.id) && (p.option_type || '').toUpperCase() === 'CALL' && p.quantity < 0,
      );
      const coverable = Math.floor(stockQty / 100);
      for (let i = 0; i < Math.min(shortCalls.length, coverable); i++) {
        const call = shortCalls[i];
        used.add(call.id);
        const premium = Math.abs(Number(call.cost_basis ?? 0));
        groups.push(
          makeGroup('Covered Call', [call], {
            maxProfit: (call.strike_price - Number(call.underlying_price ?? 0)) * 100 + premium,
            breakevens: [Number(call.underlying_price ?? 0) - premium / 100],
          }),
        );
      }
    }

    for (const [, symPositions] of byUnderlying) {
      const shortPuts = symPositions.filter(
        p => !used.has(p.id) && (p.option_type || '').toUpperCase() === 'PUT' && p.quantity < 0,
      );
      for (const put of shortPuts) {
        used.add(put.id);
        const premium = Math.abs(Number(put.cost_basis ?? 0));
        groups.push(
          makeGroup('Cash-Secured Put', [put], {
            maxProfit: premium,
            maxLoss: put.strike_price * 100 - premium,
            breakevens: [put.strike_price - premium / 100],
          }),
        );
      }
    }
  }

  for (const [, symPositions] of byUnderlying) {
    const byExpiry = new Map<string, OptionPos[]>();
    for (const p of symPositions) {
      const exp = p.expiration_date?.slice(0, 10) ?? 'none';
      if (!byExpiry.has(exp)) byExpiry.set(exp, []);
      byExpiry.get(exp)!.push(p);
    }

    for (const [, expPositions] of byExpiry) {
      if (expPositions.length < 2) continue;
      const calls = expPositions.filter(p => !used.has(p.id) && (p.option_type || '').toUpperCase() === 'CALL');
      const puts = expPositions.filter(p => !used.has(p.id) && (p.option_type || '').toUpperCase() === 'PUT');

      // Iron Condor: 2 calls + 2 puts, different strikes
      if (calls.length >= 2 && puts.length >= 2) {
        const legs = [...calls.slice(0, 2), ...puts.slice(0, 2)];
        const strikes = new Set(legs.map(l => l.strike_price));
        if (strikes.size >= 3) {
          for (const l of legs) used.add(l.id);
          groups.push(makeGroup('Iron Condor', legs));
          continue;
        }
      }

      // Straddle: 1 call + 1 put, same strike
      if (calls.length >= 1 && puts.length >= 1) {
        for (const c of calls) {
          const match = puts.find(p => p.strike_price === c.strike_price && !used.has(p.id));
          if (match && !used.has(c.id)) {
            used.add(c.id);
            used.add(match.id);
            groups.push(makeGroup('Straddle', [c, match]));
          }
        }
        // Strangle: 1 call + 1 put, different strikes
        for (const c of calls) {
          if (used.has(c.id)) continue;
          const match = puts.find(p => p.strike_price !== c.strike_price && !used.has(p.id));
          if (match) {
            used.add(c.id);
            used.add(match.id);
            groups.push(makeGroup('Strangle', [c, match]));
          }
        }
      }

      // Butterfly: same type, 3 strikes, middle has 2x qty
      for (const typeBucket of [calls, puts]) {
        if (typeBucket.length < 3) continue;
        const sorted = typeBucket.slice().sort((a, b) => a.strike_price - b.strike_price);
        for (let i = 0; i < sorted.length - 2; i++) {
          const lo = sorted[i],
            mid = sorted[i + 1],
            hi = sorted[i + 2];
          if (used.has(lo.id) || used.has(mid.id) || used.has(hi.id)) continue;
          const width = mid.strike_price - lo.strike_price;
          if (
            Math.abs(hi.strike_price - mid.strike_price - width) < 0.01 &&
            Math.abs(mid.quantity) === Math.abs(lo.quantity) + Math.abs(hi.quantity)
          ) {
            used.add(lo.id);
            used.add(mid.id);
            used.add(hi.id);
            const prem = netPremium([lo, mid, hi]);
            groups.push(
              makeGroup('Butterfly', [lo, mid, hi], {
                maxProfit: prem < 0 ? Math.abs(prem) : width * 100 - prem,
                maxLoss: prem > 0 ? prem : Math.abs(prem),
                breakevens: [
                  lo.strike_price + Math.abs(prem) / 100,
                  hi.strike_price - Math.abs(prem) / 100,
                ],
              }),
            );
          }
        }
      }

      // Vertical Spread: same type, different strikes
      const remaining = expPositions.filter(p => !used.has(p.id));
      const remCalls = remaining.filter(p => (p.option_type || '').toUpperCase() === 'CALL');
      const remPuts = remaining.filter(p => (p.option_type || '').toUpperCase() === 'PUT');
      for (const bucket of [remCalls, remPuts]) {
        if (bucket.length >= 2) {
          const sorted = bucket.slice().sort((a, b) => a.strike_price - b.strike_price);
          for (let i = 0; i < sorted.length - 1; i += 1) {
            const a = sorted[i],
              b = sorted[i + 1];
            if (!used.has(a.id) && !used.has(b.id) && a.strike_price !== b.strike_price) {
              used.add(a.id);
              used.add(b.id);
              const prem = netPremium([a, b]);
              const width = Math.abs(b.strike_price - a.strike_price) * 100;
              groups.push(
                makeGroup('Vertical Spread', [a, b], {
                  maxProfit: prem < 0 ? Math.abs(prem) : width - prem,
                  maxLoss: prem > 0 ? prem : width - Math.abs(prem),
                  breakevens: [Math.min(a.strike_price, b.strike_price) + Math.abs(prem) / 100],
                }),
              );
            }
          }
        }
      }
    }

    // Calendar Spread: same underlying, same strike, different expirations
    const allByStrike = new Map<string, OptionPos[]>();
    for (const p of symPositions) {
      if (used.has(p.id)) continue;
      const key = `${p.strike_price}-${(p.option_type || '').toUpperCase()}`;
      if (!allByStrike.has(key)) allByStrike.set(key, []);
      allByStrike.get(key)!.push(p);
    }
    for (const [, strikePosns] of allByStrike) {
      if (strikePosns.length < 2) continue;
      const sorted = strikePosns.sort((a, b) =>
        (a.expiration_date ?? '').localeCompare(b.expiration_date ?? ''),
      );
      for (let i = 0; i < sorted.length - 1; i++) {
        const near = sorted[i],
          far = sorted[i + 1];
        if (used.has(near.id) || used.has(far.id)) continue;
        if (near.expiration_date !== far.expiration_date) {
          used.add(near.id);
          used.add(far.id);
          groups.push(makeGroup('Calendar Spread', [near, far]));
        }
      }
    }

    // Diagonal Spread: same underlying, different strike + different expiry, same type
    const unusedByType = new Map<string, OptionPos[]>();
    for (const p of symPositions) {
      if (used.has(p.id)) continue;
      const type = (p.option_type || '').toUpperCase();
      if (!unusedByType.has(type)) unusedByType.set(type, []);
      unusedByType.get(type)!.push(p);
    }
    for (const [, typePosns] of unusedByType) {
      if (typePosns.length < 2) continue;
      const sorted = typePosns.sort(
        (a, b) =>
          (a.expiration_date ?? '').localeCompare(b.expiration_date ?? '') ||
          a.strike_price - b.strike_price,
      );
      for (let i = 0; i < sorted.length - 1; i++) {
        const a = sorted[i],
          b = sorted[i + 1];
        if (used.has(a.id) || used.has(b.id)) continue;
        if (a.expiration_date !== b.expiration_date && a.strike_price !== b.strike_price) {
          used.add(a.id);
          used.add(b.id);
          groups.push(makeGroup('Diagonal Spread', [a, b]));
        }
      }
    }
  }

  return groups;
}
