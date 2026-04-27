import { describe, it, expect } from 'vitest';

import {
  bucketForHour,
  dayOfYear,
  getTimeAwareGreeting,
  type GreetingBucket,
} from '../greeting';

describe('bucketForHour', () => {
  const cases: Array<[number, GreetingBucket]> = [
    [5, 'early-morning'],
    [7, 'early-morning'],
    [8, 'morning'],
    [11, 'morning'],
    [12, 'midday'],
    [13, 'midday'],
    [14, 'afternoon'],
    [16, 'afternoon'],
    [17, 'evening'],
    [20, 'evening'],
    [21, 'late'],
    [23, 'late'],
    [0, 'late'],
    [4, 'late'],
  ];

  for (const [hour, bucket] of cases) {
    it(`hour ${hour} -> ${bucket}`, () => {
      expect(bucketForHour(hour)).toBe(bucket);
    });
  }

  it('normalizes out-of-range hours', () => {
    expect(bucketForHour(-1)).toBe('late');
    expect(bucketForHour(25)).toBe('late');
    // 30 mod 24 = 6 -> early-morning
    expect(bucketForHour(30)).toBe('early-morning');
  });
});

describe('dayOfYear', () => {
  it('returns 1 for January 1', () => {
    expect(dayOfYear(new Date(2026, 0, 1, 12, 0, 0))).toBe(1);
  });

  it('increments by 1 each subsequent day', () => {
    const a = dayOfYear(new Date(2026, 5, 15, 9, 0, 0));
    const b = dayOfYear(new Date(2026, 5, 16, 9, 0, 0));
    expect(b - a).toBe(1);
  });
});

describe('getTimeAwareGreeting', () => {
  it('addresses the user by first name when full name is provided', () => {
    const { text } = getTimeAwareGreeting({
      name: 'Sankalp Arora',
      now: new Date(2026, 3, 22, 9, 0, 0),
    });
    expect(text).toContain('Sankalp');
    expect(text).not.toContain('Arora');
  });

  it('falls back to "friend" when name is missing or blank', () => {
    const a = getTimeAwareGreeting({ name: undefined, now: new Date(2026, 3, 22, 10, 0, 0) });
    const b = getTimeAwareGreeting({ name: null, now: new Date(2026, 3, 22, 10, 0, 0) });
    const c = getTimeAwareGreeting({ name: '   ', now: new Date(2026, 3, 22, 10, 0, 0) });
    expect(a.text).toContain('friend');
    expect(b.text).toContain('friend');
    expect(c.text).toContain('friend');
  });

  it('is deterministic: identical inputs yield identical greetings', () => {
    const at = new Date(2026, 3, 22, 14, 30, 0);
    const first = getTimeAwareGreeting({ name: 'Sankalp', now: at });
    const second = getTimeAwareGreeting({ name: 'Sankalp', now: at });
    expect(first).toEqual(second);
  });

  it('rotates variants across days within the same bucket', () => {
    const name = 'Sankalp';
    const texts = new Set<string>();
    for (let i = 0; i < 10; i += 1) {
      const d = new Date(2026, 0, 1 + i, 9, 0, 0);
      texts.add(getTimeAwareGreeting({ name, now: d }).text);
    }
    // Three morning variants — 10 consecutive days must see at least 2 distinct lines.
    expect(texts.size).toBeGreaterThanOrEqual(2);
  });

  it('assigns the expected bucket for each time slice', () => {
    const name = 'Sankalp';
    expect(getTimeAwareGreeting({ name, now: new Date(2026, 3, 22, 6, 0, 0) }).bucket).toBe('early-morning');
    expect(getTimeAwareGreeting({ name, now: new Date(2026, 3, 22, 9, 0, 0) }).bucket).toBe('morning');
    expect(getTimeAwareGreeting({ name, now: new Date(2026, 3, 22, 12, 30, 0) }).bucket).toBe('midday');
    expect(getTimeAwareGreeting({ name, now: new Date(2026, 3, 22, 15, 0, 0) }).bucket).toBe('afternoon');
    expect(getTimeAwareGreeting({ name, now: new Date(2026, 3, 22, 19, 0, 0) }).bucket).toBe('evening');
    expect(getTimeAwareGreeting({ name, now: new Date(2026, 3, 22, 23, 30, 0) }).bucket).toBe('late');
    expect(getTimeAwareGreeting({ name, now: new Date(2026, 3, 22, 2, 0, 0) }).bucket).toBe('late');
  });
});
