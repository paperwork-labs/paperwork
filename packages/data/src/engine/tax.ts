import type { StateCode } from "../types/common";
import type { StateTaxRules, FilingStatus, TaxBracket } from "../types/tax";

const taxCache = new Map<StateCode, StateTaxRules>();

export function loadTaxData(state: StateCode, data: StateTaxRules): void {
  taxCache.set(state, data);
}

export function getStateTaxRules(state: StateCode): StateTaxRules | undefined {
  return taxCache.get(state);
}

export function getAllTaxStates(): StateCode[] {
  return Array.from(taxCache.keys()).sort();
}

/**
 * Calculate state income tax for a given income.
 * All amounts in cents. Returns tax owed in cents.
 */
export function calculateStateTax(
  state: StateCode,
  grossIncomeCents: number,
  filingStatus: FilingStatus,
): number | undefined {
  const rules = taxCache.get(state);
  if (!rules) return undefined;

  if (rules.income_tax.type === "none") return 0;

  if (rules.income_tax.type === "flat" && rules.income_tax.flat_rate_bps !== undefined) {
    const deduction = rules.standard_deductions.find(d => d.filing_status === filingStatus);
    const taxableIncome = Math.max(0, grossIncomeCents - (deduction?.amount_cents ?? 0));
    return Math.round((taxableIncome * rules.income_tax.flat_rate_bps) / 10000);
  }

  const brackets = rules.income_tax.brackets[filingStatus];
  if (!brackets || brackets.length === 0) return undefined;

  const deduction = rules.standard_deductions.find(d => d.filing_status === filingStatus);
  const taxableIncome = Math.max(0, grossIncomeCents - (deduction?.amount_cents ?? 0));

  return calculateProgressiveTax(taxableIncome, brackets);
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
