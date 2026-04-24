import { describe, it, expect } from 'vitest';
import { formatDateTime, formatMoney, formatTime } from '../format';

describe('formatMoney', () => {
  it('formats currency with requested precision', () => {
    expect(formatMoney(1234.56, 'USD', { maximumFractionDigits: 0 })).toBe('$1,235');
    expect(formatMoney(1234.56, 'USD', { minimumFractionDigits: 2, maximumFractionDigits: 2 })).toBe('$1,234.56');
  });

  it('does not throw on unknown/invalid currency codes', () => {
    expect(() => formatMoney(10, 'ZZZ', { maximumFractionDigits: 0 })).not.toThrow();
    // Some runtimes format unknown codes as "ZZZ 10"; others may throw and be caught as USD.
    expect(formatMoney(10, 'ZZZ', { maximumFractionDigits: 0 })).toMatch(/10/);
  });
});

describe('formatDateTime / formatTime', () => {
  it('formats in requested timezone when possible', () => {
    const iso = '2026-01-07T08:50:30.000Z';
    const utc = formatDateTime(iso, 'UTC');
    const ny = formatDateTime(iso, 'America/New_York');
    expect(utc).toContain('01/07/2026');
    expect(ny).toContain('01/07/2026');
    // In January, New York should differ from UTC.
    expect(ny).not.toBe(utc);
  });

  it('formats time-only in requested timezone when possible', () => {
    const iso = '2026-01-07T08:50:30.000Z';
    const utc = formatTime(iso, 'UTC');
    const ny = formatTime(iso, 'America/New_York');
    expect(utc).toMatch(/\d{2}:\d{2}:\d{2}/);
    expect(ny).toMatch(/\d{2}:\d{2}:\d{2}/);
    expect(ny).not.toBe(utc);
  });
});


