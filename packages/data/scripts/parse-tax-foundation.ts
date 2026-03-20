import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import * as XLSX from "xlsx";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import type { StateCode } from "../src/types/common";
import { STATE_CODES } from "../src/types/common";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = join(__dirname, "fixtures");
const XLSX_FILE = join(FIXTURES_DIR, "2026-State-Individual-Income-Tax-Rates-Brackets.xlsx");

// Tax Foundation uses abbreviated state names. Map every observed abbreviation -> state code.
const TF_NAME_TO_CODE: Record<string, StateCode> = {
  "Ala.": "AL", "Alaska": "AK", "Ariz.": "AZ", "Ark.": "AR", "Calif.": "CA",
  "Colo.": "CO", "Conn.": "CT", "Del.": "DE", "Fla.": "FL", "Ga.": "GA",
  "Hawaii": "HI", "Idaho": "ID", "Ill.": "IL", "Ind.": "IN", "Iowa": "IA",
  "Kans.": "KS", "Ky.": "KY", "La.": "LA", "Maine": "ME", "Md.": "MD",
  "Mass.": "MA", "Mich.": "MI", "Minn.": "MN", "Miss.": "MS", "Mo.": "MO",
  "Mont.": "MT", "Nebr.": "NE", "Nev.": "NV", "N.H.": "NH", "N.J.": "NJ",
  "N.M.": "NM", "N.Y.": "NY", "N.C.": "NC", "N.D.": "ND", "Ohio": "OH",
  "Okla.": "OK", "Ore.": "OR", "Pa.": "PA", "R.I.": "RI", "S.C.": "SC",
  "S.D.": "SD", "Tenn.": "TN", "Tex.": "TX", "Utah": "UT", "Vt.": "VT",
  "Va.": "VA", "Wash.": "WA", "W.Va.": "WV", "Wis.": "WI", "Wyo.": "WY",
  "D.C.": "DC", "Washington DC": "DC", "Wash., DC": "DC",
};

const CODE_TO_FULL_NAME: Record<StateCode, string> = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California",
  CO: "Colorado", CT: "Connecticut", DE: "Delaware", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa",
  KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland",
  MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi",
  MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire",
  NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina",
  ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania",
  RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee",
  TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington",
  WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming", DC: "District of Columbia",
};

// States with NO wage/salary income tax (capital gains or interest-only states treated as "none" for our purposes)
const NO_INCOME_TAX_STATES: StateCode[] = ["AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"];

// ─── Curated supplementary constants (all deterministic, no AI) ──────────────

// Source: Tax Foundation, Federation of Tax Administrators, state DOR websites
const DOR_URLS: Record<StateCode, string> = {
  AL: "https://revenue.alabama.gov", AK: "https://tax.alaska.gov",
  AZ: "https://azdor.gov", AR: "https://www.dfa.arkansas.gov/income-tax",
  CA: "https://www.ftb.ca.gov", CO: "https://tax.colorado.gov",
  CT: "https://portal.ct.gov/drs", DE: "https://revenue.delaware.gov",
  FL: "https://floridarevenue.com", GA: "https://dor.georgia.gov",
  HI: "https://tax.hawaii.gov", ID: "https://tax.idaho.gov",
  IL: "https://tax.illinois.gov", IN: "https://www.in.gov/dor",
  IA: "https://tax.iowa.gov", KS: "https://www.ksrevenue.gov",
  KY: "https://revenue.ky.gov", LA: "https://revenue.louisiana.gov",
  ME: "https://www.maine.gov/revenue", MD: "https://www.marylandtaxes.gov",
  MA: "https://www.mass.gov/orgs/department-of-revenue", MI: "https://www.michigan.gov/treasury",
  MN: "https://www.revenue.state.mn.us", MS: "https://www.dor.ms.gov",
  MO: "https://dor.mo.gov", MT: "https://mtrevenue.gov",
  NE: "https://revenue.nebraska.gov", NV: "https://tax.nv.gov",
  NH: "https://www.revenue.nh.gov", NJ: "https://www.nj.gov/treasury/taxation",
  NM: "https://www.tax.newmexico.gov", NY: "https://www.tax.ny.gov",
  NC: "https://www.ncdor.gov", ND: "https://www.tax.nd.gov",
  OH: "https://tax.ohio.gov", OK: "https://oklahoma.gov/tax.html",
  OR: "https://www.oregon.gov/dor", PA: "https://www.revenue.pa.gov",
  RI: "https://tax.ri.gov", SC: "https://dor.sc.gov",
  SD: "https://dor.sd.gov", TN: "https://www.tn.gov/revenue.html",
  TX: "https://comptroller.texas.gov", UT: "https://tax.utah.gov",
  VT: "https://tax.vermont.gov", VA: "https://www.tax.virginia.gov",
  WA: "https://dor.wa.gov", WV: "https://tax.wv.gov",
  WI: "https://www.revenue.wi.gov", WY: "https://revenue.wyo.gov",
  DC: "https://otr.cfo.dc.gov",
};

// Source: Tax Foundation "Local Income Taxes in 2025" + state DOR websites
// These states authorize cities/counties to levy local income taxes
const LOCAL_INCOME_TAX_STATES: Set<StateCode> = new Set([
  "AL", "CO", "DE", "IN", "IA", "KY", "MD", "MI", "MO", "NJ", "NY", "OH", "OR", "PA", "WV",
]);

// Source: Federation of Tax Administrators, state DOR reciprocity pages
// Maps each state to the list of states it has reciprocal agreements with
const RECIPROCITY_MAP: Partial<Record<StateCode, StateCode[]>> = {
  DC: ["MD", "VA"],
  IL: ["IA", "KY", "MI", "WI"],
  IN: ["KY", "MI", "OH", "PA", "WI"],
  IA: ["IL"],
  KY: ["IL", "IN", "MI", "OH", "VA", "WV", "WI"],
  MD: ["DC", "PA", "VA", "WV"],
  MI: ["IL", "IN", "KY", "MN", "OH", "WI"],
  MN: ["MI", "ND"],
  MT: ["ND"],
  ND: ["MN", "MT"],
  NJ: ["PA"],
  OH: ["IN", "KY", "MI", "PA", "WV"],
  PA: ["IN", "MD", "NJ", "OH", "VA", "WV"],
  VA: ["DC", "KY", "MD", "PA", "WV"],
  WV: ["KY", "MD", "OH", "PA", "VA"],
  WI: ["IL", "IN", "KY", "MI", "MN"],
};

// Source: State tax codes — states where personal exemption/credit phases out at higher incomes
const PERSONAL_EXEMPTION_PHASES_OUT: Set<StateCode> = new Set([
  "CA", "CT", "NY", "OR", "RI",
]);

type Bracket = { min_income_cents: number; max_income_cents: number | null; rate_bps: number };

interface RawStateData {
  code: StateCode;
  singleBrackets: Bracket[];
  mfjBrackets: Bracket[];
  stdDeductionSingle: number;
  stdDeductionCouple: number;
  personalExemptionSingle: number;
  personalExemptionCouple: number;
  personalExemptionDependent: number;
  personalExemptionIsCredit: boolean;
  footnotes: string;
}

function dollarsToCents(val: number): number {
  return Math.round(val * 100);
}

function rateToBps(val: number): number {
  return Math.round(val * 10000);
}

/**
 * Parse a personal exemption cell. Can be:
 * - number (e.g., 1500) -> dollar amount
 * - string "$29 credit" -> credit amount in dollars
 * - "n.a." / "n.a" / "none" -> 0
 */
function parseExemption(val: unknown): { amount: number; isCredit: boolean } {
  if (val == null || val === "" || val === "\u00a0") return { amount: 0, isCredit: false };
  if (typeof val === "number") return { amount: val, isCredit: false };
  const s = String(val).trim();
  if (s === "n.a." || s === "n.a" || s === "none") return { amount: 0, isCredit: false };
  const creditMatch = s.match(/^\$?([\d,]+)\s*credit$/i);
  if (creditMatch) {
    const num = parseInt(creditMatch[1].replace(/,/g, ""), 10);
    return { amount: isNaN(num) ? 0 : num, isCredit: true };
  }
  const numMatch = s.match(/^\$?([\d,]+)/);
  if (numMatch) {
    const num = parseInt(numMatch[1].replace(/,/g, ""), 10);
    return { amount: isNaN(num) ? 0 : num, isCredit: false };
  }
  return { amount: 0, isCredit: false };
}

function parseDeduction(val: unknown): number {
  if (val == null || val === "" || val === "\u00a0") return 0;
  if (typeof val === "number") return val;
  const s = String(val).trim();
  if (s === "n.a." || s === "n.a" || s === "none") return 0;
  // Handle credit-style deductions (e.g., Utah: "$876 credit")
  const creditMatch = s.match(/^\$?([\d,]+)\s*credit$/i);
  if (creditMatch) return parseInt(creditMatch[1].replace(/,/g, ""), 10) || 0;
  const numMatch = s.match(/^\$?([\d,]+)/);
  if (numMatch) return parseInt(numMatch[1].replace(/,/g, ""), 10) || 0;
  return 0;
}

function isBlankOrNbsp(val: unknown): boolean {
  if (val == null || val === "") return true;
  if (typeof val === "string" && val.trim() === "") return true;
  if (val === "\u00a0") return true;
  return false;
}

function resolveStateCode(rawName: string): StateCode | null {
  const cleaned = rawName.split("(")[0].trim();
  return TF_NAME_TO_CODE[cleaned] ?? null;
}

function extractFootnotes(rawName: string): string {
  const match = rawName.match(/\(([^)]+)\)/);
  return match ? match[1].trim() : "";
}

function buildBrackets(rawBrackets: Array<{ rate: number; threshold: number }>): Bracket[] {
  if (rawBrackets.length === 0) return [];
  const sorted = [...rawBrackets].sort((a, b) => a.threshold - b.threshold);
  return sorted.map((b, i) => ({
    min_income_cents: dollarsToCents(b.threshold),
    max_income_cents: i < sorted.length - 1 ? dollarsToCents(sorted[i + 1].threshold) : null,
    rate_bps: rateToBps(b.rate),
  }));
}

function parseSheet(workbook: XLSX.WorkBook, yearStr: string): Map<StateCode, RawStateData> {
  const sheet = workbook.Sheets[yearStr];
  if (!sheet) throw new Error(`Sheet "${yearStr}" not found in workbook`);

  const rows: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: null });
  const states = new Map<StateCode, RawStateData>();

  // Column mapping (consistent for 2019-2026):
  // A=0:State, B=1:SingleRate, C=2:">", D=3:SingleBracket,
  // E=4:MFJRate, F=5:">", G=6:MFJBracket,
  // H=7:StdDedSingle, I=8:StdDedCouple,
  // J=9:ExemptSingle, K=10:ExemptCouple, L=11:ExemptDependent
  const COL = { STATE: 0, S_RATE: 1, S_BRACKET: 3, MFJ_RATE: 4, MFJ_BRACKET: 6, STD_SINGLE: 7, STD_COUPLE: 8, EX_SINGLE: 9, EX_COUPLE: 10, EX_DEP: 11 };

  let currentState: RawStateData | null = null;
  let singleRaw: Array<{ rate: number; threshold: number }> = [];
  let mfjRaw: Array<{ rate: number; threshold: number }> = [];

  function flushState() {
    if (!currentState) return;
    currentState.singleBrackets = buildBrackets(singleRaw);
    currentState.mfjBrackets = buildBrackets(mfjRaw);
    states.set(currentState.code, currentState);
  }

  for (let r = 0; r < rows.length; r++) {
    const row = rows[r];
    if (!row || row.length === 0) continue;

    const colA = row[COL.STATE];
    const colB = row[COL.S_RATE];
    const colE = row[COL.MFJ_RATE];

    // Skip header rows
    if (colA === "State" || colA === "\u00a0" || (isBlankOrNbsp(colA) && isBlankOrNbsp(colB) && isBlankOrNbsp(colE))) {
      continue;
    }

    // Check if this row starts a new state
    if (colA != null && typeof colA === "string" && colA.trim() && !colA.trim().startsWith("(")) {
      const stateCode = resolveStateCode(colA);
      if (stateCode) {
        flushState();

        const exSingle = parseExemption(row[COL.EX_SINGLE]);
        const exCouple = parseExemption(row[COL.EX_COUPLE]);
        const exDep = parseExemption(row[COL.EX_DEP]);

        currentState = {
          code: stateCode,
          singleBrackets: [],
          mfjBrackets: [],
          stdDeductionSingle: parseDeduction(row[COL.STD_SINGLE]),
          stdDeductionCouple: parseDeduction(row[COL.STD_COUPLE]),
          personalExemptionSingle: exSingle.amount,
          personalExemptionCouple: exCouple.amount,
          personalExemptionDependent: exDep.amount,
          personalExemptionIsCredit: exSingle.isCredit || exCouple.isCredit || exDep.isCredit,
          footnotes: extractFootnotes(colA),
        };
        singleRaw = [];
        mfjRaw = [];

        // Handle "none" (no income tax)
        if (colB === "none" || (typeof colB === "string" && colB.toLowerCase().includes("none"))) {
          // No brackets to add
          continue;
        }

        // Handle text-only cells like "Capital gains income only" (Washington)
        if (typeof colB === "string" && isNaN(parseFloat(colB))) {
          continue;
        }

        // First bracket row for this state
        if (typeof colB === "number") {
          singleRaw.push({ rate: colB, threshold: (typeof row[COL.S_BRACKET] === "number" ? row[COL.S_BRACKET] : 0) });
        }
        if (typeof colE === "number") {
          mfjRaw.push({ rate: colE, threshold: (typeof row[COL.MFJ_BRACKET] === "number" ? row[COL.MFJ_BRACKET] : 0) });
        }
        continue;
      }
    }

    // Continuation row: footnotes (starts with "(") or additional brackets
    if (!currentState) continue;

    // Footnote-only row
    if (colA != null && typeof colA === "string" && colA.trim().startsWith("(")) {
      if (!currentState.footnotes) {
        currentState.footnotes = colA.replace(/[()]/g, "").trim();
      } else {
        currentState.footnotes += ", " + colA.replace(/[()]/g, "").trim();
      }
    }

    // Bracket data (single and/or MFJ)
    if (typeof colB === "number") {
      singleRaw.push({ rate: colB, threshold: (typeof row[COL.S_BRACKET] === "number" ? row[COL.S_BRACKET] : 0) });
    }
    if (typeof colE === "number") {
      mfjRaw.push({ rate: colE, threshold: (typeof row[COL.MFJ_BRACKET] === "number" ? row[COL.MFJ_BRACKET] : 0) });
    }
  }

  flushState();
  return states;
}

function determineTaxType(data: RawStateData): "none" | "flat" | "progressive" {
  if (NO_INCOME_TAX_STATES.includes(data.code)) return "none";
  if (data.singleBrackets.length === 0) return "none";
  if (data.singleBrackets.length === 1) return "flat";
  return "progressive";
}

function buildStateTaxJson(data: RawStateData, taxYear: number) {
  const taxType = determineTaxType(data);
  const now = new Date().toISOString();

  let incomeTax: any;
  if (taxType === "none") {
    incomeTax = { type: "none" };
  } else if (taxType === "flat") {
    incomeTax = {
      type: "flat",
      flat_rate_bps: data.singleBrackets[0].rate_bps,
    };
  } else {
    incomeTax = {
      type: "progressive",
      brackets: {
        single: data.singleBrackets,
        married_filing_jointly: data.mfjBrackets.length > 0 ? data.mfjBrackets : data.singleBrackets,
        married_filing_separately: data.singleBrackets,
        head_of_household: data.singleBrackets,
      },
    };
  }

  const stdDedSingle = dollarsToCents(data.stdDeductionSingle);
  const stdDedCouple = dollarsToCents(data.stdDeductionCouple);
  const stdDedMfs = stdDedSingle;
  const stdDedHoh = stdDedSingle;

  const standardDeductions = taxType === "none" ? [] : [
    { filing_status: "single", amount_cents: stdDedSingle },
    { filing_status: "married_filing_jointly", amount_cents: stdDedCouple },
    { filing_status: "married_filing_separately", amount_cents: stdDedMfs },
    { filing_status: "head_of_household", amount_cents: stdDedHoh },
  ];

  const personalExemptionCents = dollarsToCents(data.personalExemptionSingle);
  const hasLocalTax = LOCAL_INCOME_TAX_STATES.has(data.code);
  const reciprocityStates = RECIPROCITY_MAP[data.code];
  const phasesOut = PERSONAL_EXEMPTION_PHASES_OUT.has(data.code);

  const tfUrlBase = "https://taxfoundation.org/data/all/state/state-income-tax-rates";
  const tfUrl = taxYear === 2025 ? tfUrlBase : `${tfUrlBase}-${taxYear}`;

  const result: any = {
    state: data.code,
    state_name: CODE_TO_FULL_NAME[data.code],
    tax_year: taxYear,
    income_tax: incomeTax,
    standard_deductions: standardDeductions,
    personal_exemption: {
      amount_cents: personalExemptionCents,
      phases_out: phasesOut,
    },
    notable_credits: [],
    notable_deductions: [],
    local_taxes: { has_local_income_tax: hasLocalTax },
    reciprocity: reciprocityStates
      ? { has_reciprocity: true, states: reciprocityStates }
      : { has_reciprocity: false },
    dor_url: DOR_URLS[data.code],
    tax_foundation_url: tfUrl,
    verification: {
      last_verified: now,
      sources: [
        {
          name: `Tax Foundation ${taxYear} Rates and Brackets (XLSX)`,
          url: "https://taxfoundation.org/wp-content/uploads/2026/02/2026-State-Individual-Income-Tax-Rates-Brackets.xlsx",
          accessed_at: now,
        },
      ],
      verified_by: "tax_foundation_parse" as const,
      confidence: 0.99,
    },
  };

  return result;
}

async function main() {
  if (!existsSync(XLSX_FILE)) {
    console.error(`XLSX file not found: ${XLSX_FILE}`);
    console.error("Download from: https://taxfoundation.org/wp-content/uploads/2026/02/2026-State-Individual-Income-Tax-Rates-Brackets.xlsx");
    process.exit(1);
  }

  const targetYears = (process.env.EXTRACT_TAX_YEAR ?? "2024,2025,2026").split(",").map((s) => parseInt(s.trim(), 10));
  const onlyState = process.env.EXTRACT_ONLY_STATE?.trim().toUpperCase() as StateCode | undefined;

  console.log(`Reading XLSX: ${XLSX_FILE}`);
  const workbook = XLSX.readFile(XLSX_FILE);
  console.log(`Sheets available: ${workbook.SheetNames.join(", ")}`);

  for (const taxYear of targetYears) {
    const yearStr = String(taxYear);
    if (!workbook.SheetNames.includes(yearStr)) {
      console.error(`Sheet "${yearStr}" not found, skipping`);
      continue;
    }

    console.log(`\n=== Parsing TY${taxYear} ===`);
    const parsed = parseSheet(workbook, yearStr);
    console.log(`Parsed ${parsed.size} jurisdictions`);

    const outputDir = join(__dirname, `../src/tax/${taxYear}`);
    mkdirSync(outputDir, { recursive: true });

    let successCount = 0;
    let errorCount = 0;

    for (const stateCode of STATE_CODES) {
      if (onlyState && stateCode !== onlyState) continue;

      const data = parsed.get(stateCode);
      if (!data) {
        console.error(`  ✗ ${stateCode}: not found in TF data`);
        errorCount++;
        continue;
      }

      const existingPath = join(outputDir, `${stateCode}.json`);
      const result = buildStateTaxJson(data, taxYear);

      // Validate against schema
      try {
        StateTaxRulesSchema.parse(result);
      } catch (err: any) {
        console.error(`  ✗ ${stateCode}: schema validation failed`);
        if (err.errors) {
          for (const e of err.errors.slice(0, 5)) {
            console.error(`    ${e.path.join(".")}: ${e.message}`);
          }
        }
        errorCount++;
        continue;
      }

      writeFileSync(existingPath, JSON.stringify(result, null, 2) + "\n", "utf8");

      const taxType = determineTaxType(data);
      const bracketCount = taxType === "progressive" ? data.singleBrackets.length : 0;
      const topRate = taxType === "none" ? 0 : taxType === "flat" ? data.singleBrackets[0]?.rate_bps ?? 0 : data.singleBrackets[data.singleBrackets.length - 1]?.rate_bps ?? 0;
      console.log(`  ✓ ${stateCode}: ${CODE_TO_FULL_NAME[stateCode]} — ${taxType}${bracketCount ? ` (${bracketCount} brackets)` : ""} top=${topRate}bps`);
      successCount++;
    }

    console.log(`\nTY${taxYear}: ${successCount} succeeded, ${errorCount} errors`);
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
