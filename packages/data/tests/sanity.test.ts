import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import { z } from "zod";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import type { StateCode } from "../src/types/common";
import { discoverTaxYearDirs } from "../src/engine/loader";

type TaxRulesParsed = z.infer<typeof StateTaxRulesSchema>;
type FormationRulesParsed = z.infer<typeof FormationRulesSchema>;

const NO_INCOME_TAX_STATES: StateCode[] = ["AK", "FL", "NH", "NV", "SD", "TN", "TX", "WA", "WY"];

const MIN_STANDARD_DEDUCTION_CENTS = 100_000;
const MIN_PERSONAL_EXEMPTION_CENTS = 10_000;
const MIN_NON_FIRST_BRACKET_MIN_CENTS = 10_000;
const MAX_RATE_BPS = 1500;

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = join(__dirname, "../src");

type ParsedTaxFile = { relPath: string; data: TaxRulesParsed };
type ParsedFormationFile = { relPath: string; data: FormationRulesParsed };

function loadTaxFiles(): ParsedTaxFile[] {
  const taxRoot = join(srcDir, "tax");
  const out: ParsedTaxFile[] = [];
  for (const year of discoverTaxYearDirs(taxRoot)) {
    const yearDir = join(taxRoot, String(year));
    for (const file of readdirSync(yearDir)) {
      if (!file.endsWith(".json") || file.startsWith("_")) continue;
      const absPath = join(yearDir, file);
      if (!statSync(absPath).isFile()) continue;
      const relPath = `tax/${year}/${file}`;
      const raw: unknown = JSON.parse(readFileSync(absPath, "utf-8"));
      const data = StateTaxRulesSchema.parse(raw);
      out.push({ relPath, data });
    }
  }
  return out;
}

function loadFormationFiles(): ParsedFormationFile[] {
  const formationDir = join(srcDir, "formation");
  const out: ParsedFormationFile[] = [];
  for (const file of readdirSync(formationDir)) {
    if (!file.endsWith(".json") || file.startsWith("_")) continue;
    const absPath = join(formationDir, file);
    if (!statSync(absPath).isFile()) continue;
    const relPath = `formation/${file}`;
    const raw: unknown = JSON.parse(readFileSync(absPath, "utf-8"));
    const data = FormationRulesSchema.parse(raw);
    out.push({ relPath, data });
  }
  return out;
}

function bracketMonotonicOk(
  brackets: { min_income_cents: number; max_income_cents: number | null }[],
): boolean {
  for (let i = 1; i < brackets.length; i++) {
    const prev = brackets[i - 1]!;
    const curr = brackets[i]!;
    const prevMax = prev.max_income_cents;
    if (prevMax === null) {
      return false;
    }
    if (curr.min_income_cents < prevMax) {
      return false;
    }
  }
  return true;
}

const taxFiles = loadTaxFiles();
const formationFiles = loadFormationFiles();

const taxFlatOrProgressive = taxFiles.filter(
  (tf) => tf.data.income_tax.type === "flat" || tf.data.income_tax.type === "progressive",
);

describe("Sanity: standard deductions", () => {
  it.each(taxFlatOrProgressive)("$relPath", ({ relPath, data }) => {
    for (const d of data.standard_deductions) {
      expect(
        d.amount_cents === 0 || d.amount_cents >= MIN_STANDARD_DEDUCTION_CENTS,
        `${relPath}: standard_deduction (${d.filing_status}) amount_cents=${d.amount_cents}`,
      ).toBe(true);
    }
  });
});

describe("Sanity: personal exemptions", () => {
  it.each(taxFlatOrProgressive)("$relPath", ({ relPath, data }) => {
    const ex = data.personal_exemption.amount_cents;
    expect(
      ex === 0 || ex >= MIN_PERSONAL_EXEMPTION_CENTS,
      `${relPath}: personal_exemption.amount_cents=${ex}`,
    ).toBe(true);
  });
});

describe("Sanity: progressive bracket rates", () => {
  const progressive = taxFiles.filter((tf) => tf.data.income_tax.type === "progressive");

  it.each(progressive)("$relPath", ({ relPath, data }) => {
    const it = data.income_tax;
    if (it.type !== "progressive") return;
    for (const [status, brackets] of Object.entries(it.brackets)) {
      for (const b of brackets) {
        expect(
          b.rate_bps <= MAX_RATE_BPS,
          `${relPath}: rate_bps ${b.rate_bps} exceeds cap ${MAX_RATE_BPS} (${status})`,
        ).toBe(true);
      }
      for (let i = 1; i < brackets.length; i++) {
        const b = brackets[i]!;
        expect(
          b.min_income_cents >= MIN_NON_FIRST_BRACKET_MIN_CENTS,
          `${relPath}: bracket ${i} min_income_cents=${b.min_income_cents} for ${status} likely dollars not cents (non-first bracket < ${MIN_NON_FIRST_BRACKET_MIN_CENTS} cents)`,
        ).toBe(true);
      }
    }
  });
});

describe("Sanity: bracket monotonicity", () => {
  const progressive = taxFiles.filter((tf) => tf.data.income_tax.type === "progressive");

  it.each(progressive)("$relPath", ({ relPath, data }) => {
    const it = data.income_tax;
    if (it.type !== "progressive") return;
    for (const [status, brackets] of Object.entries(it.brackets)) {
      expect(
        bracketMonotonicOk(brackets),
        `${relPath}: progressive brackets not monotonic for filing_status=${status}`,
      ).toBe(true);
    }
  });
});

describe("Sanity: flat rate cap", () => {
  const flat = taxFiles.filter((tf) => tf.data.income_tax.type === "flat");

  it.each(flat)("$relPath", ({ relPath, data }) => {
    const it = data.income_tax;
    if (it.type !== "flat") return;
    expect(
      it.flat_rate_bps <= MAX_RATE_BPS,
      `${relPath}: flat_rate_bps ${it.flat_rate_bps} exceeds cap ${MAX_RATE_BPS}`,
    ).toBe(true);
  });
});

describe("Sanity: no-income-tax states", () => {
  const noTaxFiles = taxFiles.filter((tf) => NO_INCOME_TAX_STATES.includes(tf.data.state));

  it.each(noTaxFiles)("$relPath", ({ relPath, data }) => {
    expect(
      data.income_tax.type === "none",
      `No-income-tax state ${data.state} (${relPath}): expected income_tax.type "none", got "${data.income_tax.type}"`,
    ).toBe(true);
  });
});

describe("Sanity: formation filing fees", () => {
  it.each(formationFiles)("$relPath", ({ relPath, data }) => {
    const fee = data.fees.standard.amount_cents;
    expect(fee > 0, `${relPath}: standard filing fee must be > 0 (got ${fee})`).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Cross-year consistency: catches plausible-but-wrong AI extraction errors
// ---------------------------------------------------------------------------

const MAX_RATE_DELTA_BPS = 200;
const MAX_STD_DEDUCTION_CHANGE_PCT = 25;
const MAX_BRACKET_COUNT_DELTA = 2;

function topRateBps(data: TaxRulesParsed): number {
  const it = data.income_tax;
  if (it.type === "none") return 0;
  if (it.type === "flat") return it.flat_rate_bps;
  let max = 0;
  for (const brackets of Object.values(it.brackets)) {
    for (const b of brackets) {
      if (b.rate_bps > max) max = b.rate_bps;
    }
  }
  return max;
}

function bracketCount(data: TaxRulesParsed): number {
  const it = data.income_tax;
  if (it.type !== "progressive") return 0;
  return it.brackets.single.length;
}

function avgStdDeduction(data: TaxRulesParsed): number {
  const vals = data.standard_deductions.filter((d) => d.amount_cents > 0).map((d) => d.amount_cents);
  if (vals.length === 0) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

const taxByStateYear = new Map<string, Map<number, TaxRulesParsed>>();
for (const tf of taxFiles) {
  const st = tf.data.state;
  if (!taxByStateYear.has(st)) taxByStateYear.set(st, new Map());
  taxByStateYear.get(st)!.set(tf.data.tax_year, tf.data);
}

const crossYearPairs: { state: StateCode; yearA: number; yearB: number; dataA: TaxRulesParsed; dataB: TaxRulesParsed }[] = [];
for (const [state, byYear] of taxByStateYear) {
  const years = Array.from(byYear.keys()).sort((a, b) => a - b);
  for (let i = 0; i < years.length - 1; i++) {
    crossYearPairs.push({
      state: state as StateCode,
      yearA: years[i]!,
      yearB: years[i + 1]!,
      dataA: byYear.get(years[i]!)!,
      dataB: byYear.get(years[i + 1]!)!,
    });
  }
}

describe("Cross-year: top rate stability (advisory)", () => {
  it.each(crossYearPairs)("$state $yearA->$yearB", ({ state, yearA, yearB, dataA, dataB }) => {
    const rateA = topRateBps(dataA);
    const rateB = topRateBps(dataB);
    const delta = Math.abs(rateB - rateA);
    if (delta > MAX_RATE_DELTA_BPS) {
      console.warn(
        `${state} top rate jumped ${delta} bps (${rateA}->${rateB}) between ${yearA} and ${yearB} — verify legislation`,
      );
    }
    expect(
      delta <= 1000,
      `${state} top rate jumped ${delta} bps (${rateA}->${rateB}) between ${yearA}->${yearB} — almost certainly wrong`,
    ).toBe(true);
  });
});

describe("Cross-year: standard deduction stability (advisory)", () => {
  it.each(crossYearPairs)("$state $yearA->$yearB", ({ state, yearA, yearB, dataA, dataB }) => {
    const avgA = avgStdDeduction(dataA);
    const avgB = avgStdDeduction(dataB);
    if (avgA === 0 || avgB === 0) return;
    const changePct = (Math.abs(avgB - avgA) / avgA) * 100;
    if (changePct > MAX_STD_DEDUCTION_CHANGE_PCT) {
      console.warn(
        `${state} avg standard deduction changed ${changePct.toFixed(1)}% between ${yearA}->${yearB} (${avgA}->${avgB}) — verify`,
      );
    }
    expect(
      changePct <= 1000,
      `${state} standard deduction changed ${changePct.toFixed(1)}% between ${yearA}->${yearB} — almost certainly wrong`,
    ).toBe(true);
  });
});

describe("Cross-year: tax type stability (advisory)", () => {
  it.each(crossYearPairs)("$state $yearA->$yearB", ({ state, yearA, yearB, dataA, dataB }) => {
    if (dataA.income_tax.type !== dataB.income_tax.type) {
      console.warn(
        `${state} tax type changed: ${dataA.income_tax.type} (${yearA}) -> ${dataB.income_tax.type} (${yearB}) — verify legislation`,
      );
    }
  });
});

describe("Cross-year: bracket count stability (advisory)", () => {
  it.each(crossYearPairs)("$state $yearA->$yearB", ({ state, yearA, yearB, dataA, dataB }) => {
    const countA = bracketCount(dataA);
    const countB = bracketCount(dataB);
    if (countA === 0 && countB === 0) return;
    const delta = Math.abs(countB - countA);
    if (delta > MAX_BRACKET_COUNT_DELTA) {
      console.warn(
        `${state} bracket count changed by ${delta} (${countA}->${countB}) between ${yearA}->${yearB} — verify`,
      );
    }
    expect(
      delta <= 6,
      `${state} bracket count changed by ${delta} (${countA}->${countB}) between ${yearA}->${yearB} — almost certainly wrong`,
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Filing-status consistency: rates & bracket count must match across statuses
// ---------------------------------------------------------------------------

const progressiveTaxFiles = taxFiles.filter((tf) => tf.data.income_tax.type === "progressive");

describe("Filing-status: consistent rates across statuses", () => {
  it.each(progressiveTaxFiles)("$relPath", ({ relPath, data }) => {
    const it = data.income_tax;
    if (it.type !== "progressive") return;
    const singleRates = it.brackets.single.map((b) => b.rate_bps);
    for (const [status, brackets] of Object.entries(it.brackets)) {
      if (status === "single") continue;
      const rates = brackets.map((b) => b.rate_bps);
      expect(
        JSON.stringify(rates) === JSON.stringify(singleRates),
        `${relPath}: ${status} rates ${JSON.stringify(rates)} differ from single ${JSON.stringify(singleRates)}`,
      ).toBe(true);
    }
  });
});

describe("Filing-status: consistent bracket count across statuses", () => {
  it.each(progressiveTaxFiles)("$relPath", ({ relPath, data }) => {
    const it = data.income_tax;
    if (it.type !== "progressive") return;
    const singleCount = it.brackets.single.length;
    for (const [status, brackets] of Object.entries(it.brackets)) {
      expect(
        brackets.length === singleCount,
        `${relPath}: ${status} has ${brackets.length} brackets vs single's ${singleCount}`,
      ).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// Known-good regression anchors: canary tests for key states
// ---------------------------------------------------------------------------

type AnchorSpec = {
  state: StateCode;
  year: number;
  type: "none" | "flat" | "progressive";
  topRateMin: number;
  topRateMax: number;
  minBrackets?: number;
};

const ANCHORS: AnchorSpec[] = [
  { state: "CA", year: 2026, type: "progressive", topRateMin: 1280, topRateMax: 1380, minBrackets: 8 },
  { state: "TX", year: 2026, type: "none", topRateMin: 0, topRateMax: 0 },
  { state: "CO", year: 2026, type: "flat", topRateMin: 400, topRateMax: 480 },
  { state: "NY", year: 2026, type: "progressive", topRateMin: 1040, topRateMax: 1140, minBrackets: 6 },
  { state: "OK", year: 2026, type: "progressive", topRateMin: 425, topRateMax: 525, minBrackets: 5 },
  { state: "IL", year: 2026, type: "flat", topRateMin: 450, topRateMax: 540 },
  { state: "GA", year: 2026, type: "progressive", topRateMin: 470, topRateMax: 570 },
  { state: "ID", year: 2026, type: "progressive", topRateMin: 480, topRateMax: 580 },
];

describe("Known-good anchors", () => {
  it.each(ANCHORS)("$state $year: $type [$topRateMin-$topRateMax bps]", (anchor) => {
    const byYear = taxByStateYear.get(anchor.state);
    expect(byYear, `missing data for ${anchor.state}`).toBeDefined();
    const data = byYear!.get(anchor.year);
    expect(data, `missing ${anchor.state} ${anchor.year}`).toBeDefined();

    expect(
      data!.income_tax.type,
      `${anchor.state} ${anchor.year}: expected type ${anchor.type}, got ${data!.income_tax.type}`,
    ).toBe(anchor.type);

    const rate = topRateBps(data!);
    expect(
      rate >= anchor.topRateMin && rate <= anchor.topRateMax,
      `${anchor.state} ${anchor.year}: top rate ${rate} bps outside expected range [${anchor.topRateMin}-${anchor.topRateMax}]`,
    ).toBe(true);

    if (anchor.minBrackets && data!.income_tax.type === "progressive") {
      const count = bracketCount(data!);
      expect(
        count >= anchor.minBrackets,
        `${anchor.state} ${anchor.year}: only ${count} brackets, expected >= ${anchor.minBrackets}`,
      ).toBe(true);
    }
  });
});
