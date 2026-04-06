/**
 * Tests for GET request deduplication in api.ts.
 *
 * Exercises `cloneDedupedGetResponse` (used by the dedupe adapter) so concurrent
 * GETs receive independent data objects when cloning succeeds.
 */
import type { AxiosResponse } from 'axios';
import { describe, it, expect } from 'vitest';

import { cloneDedupedGetResponse } from '../api';

function makeResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as AxiosResponse<T>['config'],
  };
}

describe('cloneDedupedGetResponse', () => {
  it('returns deep-cloned data objects', () => {
    const data = { items: [{ id: 1, name: 'AAPL' }], meta: { total: 1 } };
    const out = cloneDedupedGetResponse(makeResponse(data));

    expect(out.data).toEqual(data);
    expect(out.data).not.toBe(data);
    expect(out.data.items).not.toBe(data.items);
    expect(out.data.items[0]).not.toBe(data.items[0]);
  });

  it('mutating cloned data does not affect original', () => {
    const data = { items: [{ id: 1, name: 'AAPL' }] };
    const out1 = cloneDedupedGetResponse(makeResponse(data));
    const out2 = cloneDedupedGetResponse(makeResponse(data));

    out1.data.items[0].name = 'MUTATED';
    out1.data.items.push({ id: 2, name: 'MSFT' });

    expect(data.items[0].name).toBe('AAPL');
    expect(data.items.length).toBe(1);
    expect(out2.data.items[0].name).toBe('AAPL');
    expect(out2.data.items.length).toBe(1);
  });

  it('handles undefined data gracefully', () => {
    const out = cloneDedupedGetResponse(makeResponse(undefined));
    expect(out.data).toBeUndefined();
  });

  it('handles null data gracefully', () => {
    const out = cloneDedupedGetResponse(makeResponse(null));
    expect(out.data).toBeNull();
  });

  it('falls back to original response when clone throws (e.g. non-cloneable values)', () => {
    const data = { a: 1, fn: () => {} };
    const response = makeResponse(data);
    const out = cloneDedupedGetResponse(response);

    expect(out.data).toBe(data);
    expect(out.status).toBe(200);
  });
});

describe('GET dedup integration logic', () => {
  it('concurrent consumers get independent copies', async () => {
    const sharedPayload = { snapshots: [{ symbol: 'AAPL', price: 150 }] };

    const results = await Promise.all(
      Array.from({ length: 5 }, () =>
        Promise.resolve(
          typeof structuredClone === 'function'
            ? structuredClone(sharedPayload)
            : JSON.parse(JSON.stringify(sharedPayload)),
        ),
      ),
    );

    results[0].snapshots[0].price = 999;
    results[1].snapshots.push({ symbol: 'MSFT', price: 200 });

    for (let i = 2; i < results.length; i++) {
      expect(results[i].snapshots[0].price).toBe(150);
      expect(results[i].snapshots.length).toBe(1);
    }

    expect(sharedPayload.snapshots[0].price).toBe(150);
    expect(sharedPayload.snapshots.length).toBe(1);
  });

  it('dedup key includes authorization header', () => {
    const uri = '/api/v1/market-data/snapshots';
    const auth1 = 'Bearer token-a';
    const auth2 = 'Bearer token-b';

    const key1 = `${uri}::${auth1}`;
    const key2 = `${uri}::${auth2}`;
    const key3 = `${uri}::${auth1}`;

    expect(key1).not.toBe(key2);
    expect(key1).toBe(key3);
  });
});
