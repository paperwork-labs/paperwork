/**
 * BigInt-cents helpers for Decimal wire-format price strings.
 * Avoids JS `Number` for money values (Iron Law: no float round-trips).
 */

const EN_LOCALE = 'en-US';

/**
 * Parse a decimal string (e.g. `"99.99"`, `"-0.10"`) into integer cents as BigInt.
 * Returns `null` if the string is not a finite non-negative/negative decimal amount.
 */
export function parseDecimalStringToCents(value: string): bigint | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  const neg = trimmed.startsWith('-');
  const unsigned = neg ? trimmed.slice(1) : trimmed;
  if (!unsigned.length) return null;

  const parts = unsigned.split('.');
  if (parts.length > 2) return null;

  const wholeRaw = parts[0] ?? '';
  const fracRaw = parts[1] ?? '';

  if (!/^\d*$/.test(wholeRaw) || !/^\d*$/.test(fracRaw)) {
    return null;
  }

  const whole = wholeRaw.length > 0 ? wholeRaw : '0';
  const frac = (fracRaw + '00').slice(0, 2).padEnd(2, '0');

  let cents: bigint;
  try {
    cents = BigInt(whole) * 100n + BigInt(frac);
  } catch {
    return null;
  }

  return neg ? -cents : cents;
}

/**
 * Format a Decimal-precision price string for display using `Intl` only for
 * currency symbol and digit grouping — never for converting the amount to Number.
 */
export function formatPrice(value: string, currency: string): string {
  const cents = parseDecimalStringToCents(value);
  if (cents === null) return '';

  const negative = cents < 0n;
  const abs = negative ? -cents : cents;
  const wholeDollars = abs / 100n;
  const frac = abs % 100n;
  const showCents = frac !== 0n;

  const currencyParts = new Intl.NumberFormat(EN_LOCALE, {
    style: 'currency',
    currency,
  }).formatToParts(0n);
  const currencySymbol =
    currencyParts.find((p) => p.type === 'currency')?.value ?? '';

  const groupedWhole = new Intl.NumberFormat(EN_LOCALE, {
    useGrouping: true,
    maximumFractionDigits: 0,
  }).format(wholeDollars);

  const fracStr = showCents ? frac.toString().padStart(2, '0') : '';
  const numBody = showCents ? `${groupedWhole}.${fracStr}` : groupedWhole;

  if (negative) {
    return `-${currencySymbol}${numBody}`;
  }
  return `${currencySymbol}${numBody}`;
}

/**
 * Savings percentage for annual vs twelve monthly payments, using integer cents.
 * Returns `null` when there is no discount. Percent is rounded to nearest integer.
 */
export function computeAnnualDiscount(
  monthly: string,
  annual: string,
): number | null {
  const monthlyCents = parseDecimalStringToCents(monthly);
  const annualCents = parseDecimalStringToCents(annual);
  if (monthlyCents === null || annualCents === null) return null;
  if (monthlyCents <= 0n) return null;

  const fullPrice = monthlyCents * 12n;
  if (annualCents >= fullPrice) return null;

  const diff = fullPrice - annualCents;
  // Round half up: (diff * 100 / fullPrice) with integer arithmetic
  const pct =
    (diff * 100n * 2n + fullPrice) / (2n * fullPrice);
  return Number(pct);
}
