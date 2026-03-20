import type { StateCode } from "../types/common";
import type { StateTaxRules, FilingStatus, TaxBracket } from "../types/tax";

type TaxCacheKey = `${StateCode}:${number}`;

const taxCache = new Map<TaxCacheKey, StateTaxRules>();

// Intentional hardcode: tax products target a specific filing year.
// Updated annually alongside new data extraction runs.
const DEFAULT_TAX_YEAR = 2026;

function cacheKey(state: StateCode, taxYear: number): TaxCacheKey {
  return `${state}:${taxYear}`;
}

export function loadTaxData(state: StateCode, data: StateTaxRules): void {
  taxCache.set(cacheKey(state, data.tax_year), data);
}

export function getStateTaxRules(
  state: StateCode,
  taxYear: number = DEFAULT_TAX_YEAR,
): StateTaxRules | undefined {
  return taxCache.get(cacheKey(state, taxYear));
}

export function getAllTaxStates(): StateCode[] {
  const states = new Set<StateCode>();
  for (const key of taxCache.keys()) {
    states.add(key.split(":")[0] as StateCode);
  }
  return Array.from(states).sort();
}

export function getAvailableTaxYears(state?: StateCode): number[] {
  const years = new Set<number>();
  for (const [key, data] of taxCache.entries()) {
    if (!state || key.startsWith(`${state}:`)) {
      years.add(data.tax_year);
    }
  }
  return Array.from(years).sort((a, b) => a - b);
}

/**
 * Calculate state income tax for a given income.
 * All amounts in cents. Returns tax owed in cents.
 */
export function calculateStateTax(
  state: StateCode,
  grossIncomeCents: number,
  filingStatus: FilingStatus,
  taxYear: number = DEFAULT_TAX_YEAR,
): number | undefined {
  const rules = taxCache.get(cacheKey(state, taxYear));
  if (!rules) return undefined;

  if (rules.income_tax.type === "none") return 0;

  if (rules.income_tax.type === "flat") {
    const deduction = rules.standard_deductions.find(d => d.filing_status === filingStatus);
    const taxableIncome = Math.max(0, grossIncomeCents - (deduction?.amount_cents ?? 0));
    return Math.round((taxableIncome * rules.income_tax.flat_rate_bps) / 10000);
  }

  if (rules.income_tax.type === "progressive") {
    const brackets = rules.income_tax.brackets[filingStatus];
    if (!brackets || brackets.length === 0) return undefined;

    const deduction = rules.standard_deductions.find(d => d.filing_status === filingStatus);
    const taxableIncome = Math.max(0, grossIncomeCents - (deduction?.amount_cents ?? 0));
    return calculateProgressiveTax(taxableIncome, brackets);
  }

  return undefined;
}

function calculateProgressiveTax(taxableIncomeCents: number, brackets: TaxBracket[]): number {
  let taxCents = 0;

  for (const bracket of brackets) {
    if (taxableIncomeCents <= bracket.min_income_cents) break;

    const bracketMax = bracket.max_income_cents ?? Infinity;
    const taxableInBracket = Math.min(taxableIncomeCents, bracketMax) - bracket.min_income_cents;

    if (taxableInBracket <= 0) continue;

    taxCents += Math.round((taxableInBracket * bracket.rate_bps) / 10000);
  }

  return taxCents;
}

// Test helper
export function clearTaxCache(): void {
  taxCache.clear();
}
