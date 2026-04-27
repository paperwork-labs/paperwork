import { describe, it, expect } from 'vitest';

import {
  computeAnnualDiscount,
  formatPrice,
  parseDecimalStringToCents,
} from '../format';

describe('parseDecimalStringToCents', () => {
  it('parses standard amounts', () => {
    expect(parseDecimalStringToCents('99.99')).toBe(9999n);
    expect(parseDecimalStringToCents('0.10')).toBe(10n);
    expect(parseDecimalStringToCents('20.00')).toBe(2000n);
  });

  it('parses large values without precision loss', () => {
    expect(parseDecimalStringToCents('1234567.89')).toBe(123456789n);
  });

  it('parses negatives', () => {
    expect(parseDecimalStringToCents('-0.10')).toBe(-10n);
    expect(parseDecimalStringToCents('-99.99')).toBe(-9999n);
  });

  it('returns null for invalid input', () => {
    expect(parseDecimalStringToCents('')).toBe(null);
    expect(parseDecimalStringToCents('12.34.56')).toBe(null);
    expect(parseDecimalStringToCents('abc')).toBe(null);
  });
});

describe('formatPrice', () => {
  it('formats common USD amounts', () => {
    expect(formatPrice('99.99', 'USD')).toBe('$99.99');
    expect(formatPrice('0.10', 'USD')).toBe('$0.10');
    expect(formatPrice('20.00', 'USD')).toBe('$20');
  });

  it('groups large whole-dollar parts', () => {
    expect(formatPrice('1234567.89', 'USD')).toBe('$1,234,567.89');
  });

  it('formats negatives', () => {
    expect(formatPrice('-99.99', 'USD')).toBe('-$99.99');
  });
});

describe('computeAnnualDiscount', () => {
  it('returns rounded percent when annual is cheaper than 12× monthly', () => {
    // $10/mo × 12 = $120/yr vs $100/yr → ~16.67% → 17%
    expect(computeAnnualDiscount('10.00', '100.00')).toBe(17);
  });

  it('returns null when there is no discount', () => {
    expect(computeAnnualDiscount('10.00', '120.00')).toBe(null);
    expect(computeAnnualDiscount('0.00', '0.00')).toBe(null);
  });
});
