/**
 * Client-side tax estimator for the demo flow.
 * Mirrors api/app/services/tax_calculator.py — all values in integer cents.
 *
 * Only supports "single" filing status for demo estimation.
 * Full calculation (all statuses, credits, state tax) happens server-side.
 */

interface TaxBracket {
  max: number | null;
  rate: number;
}

interface TaxEstimate {
  adjustedGrossIncome: number;
  standardDeduction: number;
  taxableIncome: number;
  federalTax: number;
  totalWithheld: number;
  refundAmount: number;
  owedAmount: number;
}

const SINGLE_STANDARD_DEDUCTION = 1_575_000;

const SINGLE_BRACKETS: TaxBracket[] = [
  { max: 1_192_500, rate: 10 },
  { max: 4_847_500, rate: 12 },
  { max: 10_335_000, rate: 22 },
  { max: 19_730_000, rate: 24 },
  { max: 25_052_500, rate: 32 },
  { max: 62_635_000, rate: 35 },
  { max: null, rate: 37 },
];

function calculateFederalTax(taxableIncomeCents: number): number {
  if (taxableIncomeCents <= 0) return 0;

  let tax = 0;
  let prevMax = 0;

  for (const bracket of SINGLE_BRACKETS) {
    const bracketMax = bracket.max;

    const taxableInBracket =
      bracketMax === null
        ? taxableIncomeCents - prevMax
        : Math.min(taxableIncomeCents, bracketMax) - prevMax;

    if (taxableInBracket <= 0) break;

    tax += Math.trunc((taxableInBracket * bracket.rate) / 100);
    prevMax = bracketMax ?? taxableIncomeCents;
  }

  return tax;
}

export function estimateRefund(
  wagesCents: number,
  federalWithheldCents: number,
  stateWithheldCents: number,
): TaxEstimate {
  const agi = wagesCents;
  const taxableIncome = Math.max(0, agi - SINGLE_STANDARD_DEDUCTION);
  const federalTax = calculateFederalTax(taxableIncome);

  const totalWithheld = federalWithheldCents + stateWithheldCents;
  const net = totalWithheld - federalTax;

  return {
    adjustedGrossIncome: agi,
    standardDeduction: SINGLE_STANDARD_DEDUCTION,
    taxableIncome,
    federalTax,
    totalWithheld,
    refundAmount: Math.max(0, net),
    owedAmount: Math.max(0, -net),
  };
}
