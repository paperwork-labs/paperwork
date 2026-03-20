/**
 * Human review CLI for batch validation + approval stamping of tax + formation JSON.
 *
 * Usage:
 *   pnpm review          — report only
 *   pnpm review:approve  — stamp verified_by / last_verified (only if all checks pass)
 */
import { readFileSync, writeFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { z } from "zod";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import { STATE_CODES, type StateCode } from "../src/types/common";
type TaxRulesParsed = z.infer<typeof StateTaxRulesSchema>;
type FormationRulesParsed = z.infer<typeof FormationRulesSchema>;
import { discoverTaxYearDirs } from "../src/engine/loader";

const NO_INCOME_TAX_STATES: StateCode[] = ["AK", "FL", "NH", "NV", "SD", "TN", "TX", "WA", "WY"];

const MIN_STANDARD_DEDUCTION_CENTS = 100_000; // $1,000 — catch dollar-as-cents mistakes
const MIN_PERSONAL_EXEMPTION_CENTS = 10_000; // $100 if non-zero
const MIN_NON_FIRST_BRACKET_MIN_CENTS = 10_000; // $100
const MAX_RATE_BPS = 1500;

type ParsedTaxFile = {
  relPath: string;
  absPath: string;
  data: TaxRulesParsed;
};

type ParsedFormationFile = {
  relPath: string;
  absPath: string;
  data: FormationRulesParsed;
};

function discoverTaxYears(taxRoot: string): number[] {
  return discoverTaxYearDirs(taxRoot);
}

function loadTaxFiles(srcDir: string): {
  taxFiles: ParsedTaxFile[];
  validationErrors: { file: string; error: string }[];
} {
  const taxRoot = join(srcDir, "tax");
  const years = discoverTaxYears(taxRoot);
  const taxFiles: ParsedTaxFile[] = [];
  const validationErrors: { file: string; error: string }[] = [];

  for (const year of years) {
    const yearDir = join(taxRoot, String(year));
    let files: string[] = [];
    try {
      files = readdirSync(yearDir);
    } catch (e) {
      validationErrors.push({ file: `tax/${year}`, error: String(e) });
      continue;
    }
    for (const file of files) {
      if (!file.endsWith(".json") || file.startsWith("_")) continue;
      const absPath = join(yearDir, file);
      if (!statSync(absPath).isFile()) continue;
      const relPath = `tax/${year}/${file}`;
      const expectedState = file.replace(".json", "");
      try {
        const raw: unknown = JSON.parse(readFileSync(absPath, "utf-8"));
        const data = StateTaxRulesSchema.parse(raw);
        if (data.state !== expectedState) {
          validationErrors.push({
            file: relPath,
            error: `state mismatch: file=${expectedState}, data=${data.state}`,
          });
          continue;
        }
        if (data.tax_year !== year) {
          validationErrors.push({
            file: relPath,
            error: `tax_year mismatch: dir=${year}, data=${data.tax_year}`,
          });
          continue;
        }
        taxFiles.push({ relPath, absPath, data });
      } catch (e) {
        validationErrors.push({ file: relPath, error: String(e) });
      }
    }
  }

  return { taxFiles, validationErrors };
}

function loadFormationFiles(srcDir: string): {
  formationFiles: ParsedFormationFile[];
  validationErrors: { file: string; error: string }[];
} {
  const formationDir = join(srcDir, "formation");
  const formationFiles: ParsedFormationFile[] = [];
  const validationErrors: { file: string; error: string }[] = [];
  try {
    for (const file of readdirSync(formationDir)) {
      if (!file.endsWith(".json") || file.startsWith("_")) continue;
      const absPath = join(formationDir, file);
      if (!statSync(absPath).isFile()) continue;
      const relPath = `formation/${file}`;
      const expectedState = file.replace(".json", "");
      try {
        const raw: unknown = JSON.parse(readFileSync(absPath, "utf-8"));
        const data = FormationRulesSchema.parse(raw);
        if (data.state !== expectedState) {
          validationErrors.push({
            file: relPath,
            error: `state mismatch: file=${expectedState}, data=${data.state}`,
          });
          continue;
        }
        formationFiles.push({ relPath, absPath, data });
      } catch (e) {
        validationErrors.push({ file: relPath, error: String(e) });
      }
    }
  } catch (e) {
    validationErrors.push({ file: "formation/", error: String(e) });
  }
  return { formationFiles, validationErrors };
}

function topTaxRateDisplay(rules: TaxRulesParsed): string {
  const it = rules.income_tax;
  if (it.type === "none") return "-";
  if (it.type === "flat") return `${(it.flat_rate_bps / 100).toFixed(2)}%`;
  let maxBps = 0;
  for (const brackets of Object.values(it.brackets)) {
    for (const b of brackets) {
      if (b.rate_bps > maxBps) maxBps = b.rate_bps;
    }
  }
  return `${(maxBps / 100).toFixed(2)}%`;
}

function taxTypeLabel(rules: TaxRulesParsed): string {
  return rules.income_tax.type;
}

function bracketMonotonicOk(brackets: { min_income_cents: number; max_income_cents: number | null }[]): boolean {
  for (let i = 1; i < brackets.length; i++) {
    const prev = brackets[i - 1]!;
    const curr = brackets[i]!;
    const prevMax = prev.max_income_cents;
    if (prevMax === null) {
      // Open-ended previous bracket must be last
      return false;
    }
    if (curr.min_income_cents < prevMax) {
      return false;
    }
  }
  return true;
}

function runSanityChecks(
  taxFiles: ParsedTaxFile[],
  formationFiles: ParsedFormationFile[],
): string[] {
  const failures: string[] = [];

  const taxByYear = new Map<number, Map<StateCode, ParsedTaxFile>>();
  for (const tf of taxFiles) {
    const year = tf.data.tax_year;
    const m = taxByYear.get(year) ?? new Map();
    m.set(tf.data.state, tf);
    taxByYear.set(year, m);
  }

  for (const [year, byState] of taxByYear) {
    for (const code of STATE_CODES) {
      if (!byState.has(code)) {
        failures.push(`Completeness: missing tax/${year}/${code}.json`);
      }
    }
  }

  const formationByState = new Map<StateCode, ParsedFormationFile>();
  for (const ff of formationFiles) {
    formationByState.set(ff.data.state, ff);
  }
  for (const code of STATE_CODES) {
    if (!formationByState.has(code)) {
      failures.push(`Completeness: missing formation/${code}.json`);
    }
  }

  for (const tf of taxFiles) {
    const { data, relPath } = tf;
    const code = data.state;

    if (NO_INCOME_TAX_STATES.includes(code) && data.income_tax.type !== "none") {
      failures.push(`No-income-tax state ${code} (${relPath}): expected income_tax.type "none", got "${data.income_tax.type}"`);
    }

    if (data.income_tax.type === "flat" || data.income_tax.type === "progressive") {
      for (const d of data.standard_deductions) {
        if (d.amount_cents > 0 && d.amount_cents < MIN_STANDARD_DEDUCTION_CENTS) {
          failures.push(
            `${relPath}: standard_deduction (${d.filing_status}) amount_cents=${d.amount_cents} looks like dollars not cents (< $${MIN_STANDARD_DEDUCTION_CENTS / 100} expected minimum)`,
          );
        }
      }

      const ex = data.personal_exemption.amount_cents;
      if (ex > 0 && ex < MIN_PERSONAL_EXEMPTION_CENTS) {
        failures.push(
          `${relPath}: personal_exemption.amount_cents=${ex} likely dollars not cents (non-zero but < ${MIN_PERSONAL_EXEMPTION_CENTS} cents)`,
        );
      }
    }

    const it = data.income_tax;
    if (it.type === "flat") {
      if (it.flat_rate_bps > MAX_RATE_BPS) {
        failures.push(`${relPath}: flat_rate_bps ${it.flat_rate_bps} exceeds cap ${MAX_RATE_BPS}`);
      }
    }
    if (it.type === "progressive") {
      for (const [status, brackets] of Object.entries(it.brackets)) {
        if (!bracketMonotonicOk(brackets)) {
          failures.push(`${relPath}: progressive brackets not monotonic for filing_status=${status}`);
        }
        for (let i = 1; i < brackets.length; i++) {
          const b = brackets[i]!;
          if (b.min_income_cents < MIN_NON_FIRST_BRACKET_MIN_CENTS) {
            failures.push(
              `${relPath}: bracket ${i} min_income_cents=${b.min_income_cents} for ${status} likely dollars not cents (non-first bracket < ${MIN_NON_FIRST_BRACKET_MIN_CENTS} cents)`,
            );
          }
        }
        for (const b of brackets) {
          if (b.rate_bps > MAX_RATE_BPS) {
            failures.push(`${relPath}: rate_bps ${b.rate_bps} exceeds cap ${MAX_RATE_BPS} (${status})`);
          }
        }
      }
    }
  }

  for (const ff of formationFiles) {
    const fee = ff.data.fees.standard.amount_cents;
    if (fee <= 0) {
      failures.push(`${ff.relPath}: standard filing fee must be > 0 (got ${fee})`);
    }
  }

  return failures;
}

function main(): void {
  const approve = process.argv.includes("--approve");
  /** Run from `packages/data` (`pnpm review` / `tsx scripts/review.ts`). */
  const srcDir = join(process.cwd(), "src");

  const { taxFiles, validationErrors: taxValErr } = loadTaxFiles(srcDir);
  const { formationFiles, validationErrors: formValErr } = loadFormationFiles(srcDir);
  const validationErrors = [...taxValErr, ...formValErr];

  const sanityFailures = runSanityChecks(taxFiles, formationFiles);

  const formationByState = new Map<StateCode, ParsedFormationFile>();
  for (const ff of formationFiles) {
    formationByState.set(ff.data.state, ff);
  }

  const rows: Record<string, string | number>[] = [];

  for (const tf of taxFiles) {
    const st = tf.data.state;
    const ff = formationByState.get(st);
    const filingFee = ff ? `$${(ff.data.fees.standard.amount_cents / 100).toFixed(0)}` : "—";
    const conf = tf.data.verification.confidence;
    const failed =
      validationErrors.some((e) => e.file === tf.relPath) ||
      sanityFailures.some((m) => m.includes(tf.relPath) || m.includes(`tax/${tf.data.tax_year}/${st}.json`));
    const globalFail = sanityFailures.some((m) => m.startsWith("Completeness:"));
    const status = failed || globalFail ? "INVALID" : "VALID";

    rows.push({
      State: st,
      Year: tf.data.tax_year,
      TaxType: taxTypeLabel(tf.data),
      TopRate: topTaxRateDisplay(tf.data),
      FilingFee: filingFee,
      Confidence: conf.toFixed(2),
      Status: status,
    });
  }

  for (const ff of formationFiles) {
    if (taxFiles.some((t) => t.data.state === ff.data.state)) {
      continue;
    }
    const conf = ff.data.verification.confidence;
    const st = ff.data.state;
    const failed =
      validationErrors.some((e) => e.file === ff.relPath) ||
      sanityFailures.some((m) => m.includes(ff.relPath));
    const globalFail = sanityFailures.some((m) => m.startsWith("Completeness:"));
    const status = failed || globalFail ? "INVALID" : "VALID";
    rows.push({
      State: st,
      Year: "—",
      TaxType: "—",
      TopRate: "—",
      FilingFee: `$${(ff.data.fees.standard.amount_cents / 100).toFixed(0)}`,
      Confidence: conf.toFixed(2),
      Status: status,
    });
  }

  rows.sort((a, b) => {
    const s = String(a.State).localeCompare(String(b.State));
    if (s !== 0) return s;
    return String(a.Year).localeCompare(String(b.Year), undefined, { numeric: true });
  });

  // eslint-disable-next-line no-console
  console.table(rows);

  if (validationErrors.length) {
    // eslint-disable-next-line no-console
    console.error("\n=== Schema / parse errors ===");
    for (const e of validationErrors) {
      // eslint-disable-next-line no-console
      console.error(`${e.file}: ${e.error}`);
    }
  }

  if (sanityFailures.length) {
    // eslint-disable-next-line no-console
    console.error("\n=== Sanity check failures ===");
    for (const m of sanityFailures) {
      // eslint-disable-next-line no-console
      console.error(m);
    }
  }

  const blocking =
    validationErrors.length > 0 ||
    sanityFailures.length > 0;

  if (approve) {
    if (blocking) {
      // eslint-disable-next-line no-console
      console.error("\n--approve refused: fix validation or sanity errors first.");
      process.exit(1);
    }
    const now = new Date().toISOString();
    for (const tf of taxFiles) {
      const raw = JSON.parse(readFileSync(tf.absPath, "utf-8")) as Record<string, unknown>;
      const ver = raw.verification as Record<string, unknown>;
      ver.verified_by = "human_review";
      ver.last_verified = now;
      writeFileSync(tf.absPath, `${JSON.stringify(raw, null, 2)}\n`, "utf-8");
    }
    for (const ff of formationFiles) {
      const raw = JSON.parse(readFileSync(ff.absPath, "utf-8")) as Record<string, unknown>;
      const ver = raw.verification as Record<string, unknown>;
      ver.verified_by = "human_review";
      ver.last_verified = now;
      writeFileSync(ff.absPath, `${JSON.stringify(raw, null, 2)}\n`, "utf-8");
    }
    // eslint-disable-next-line no-console
    console.log(`\nApproved ${taxFiles.length} tax file(s) and ${formationFiles.length} formation file(s).`);
  } else if (blocking) {
    process.exitCode = 1;
  }
}

main();
