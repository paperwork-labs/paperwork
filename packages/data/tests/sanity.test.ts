import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { describe, it, expect } from "vitest";
import { z } from "zod";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import type { StateCode } from "../src/types/common";
import { discoverTaxYearDirs } from "../src/engine/loader";

type TaxRulesParsed = z.infer<typeof StateTaxRulesSchema>;
type FormationRulesParsed = z.infer<typeof FormationRulesSchema>;

const NO_INCOME_TAX_STATES: StateCode[] = ["AK", "FL", "NV", "SD", "TN", "TX", "WA", "WY"];

const MIN_STANDARD_DEDUCTION_CENTS = 100_000;
const MIN_PERSONAL_EXEMPTION_CENTS = 10_000;
const MIN_NON_FIRST_BRACKET_MIN_CENTS = 10_000;
const MAX_RATE_BPS = 1500;

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
