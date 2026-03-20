import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import type { StateCode } from "../src/types/common";
import { STATE_CODES } from "../src/types/common";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FORMATION_DIR = join(__dirname, "../src/formation");

const SOURCE_URL = "https://worldpopulationreview.com/state-rankings/llc-cost-by-state";

const FULL_NAME_TO_CODE: Record<string, StateCode> = {
  "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
  "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
  "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
  "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
  "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
  "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
  "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
  "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
  "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
  "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
  "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
  "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
  "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
};

interface FeeRecord {
  code: StateCode;
  name: string;
  llcFilingFee: number;
  llcAnnualReport: number;
  notes: string;
}

function dollarsToCents(val: number): number {
  return Math.round(val * 100);
}

/**
 * Fetch the worldpopulationreview.com page and parse the LLC fee table.
 * The page has a proper HTML <table> with <tr>/<td> structure.
 * Columns: [icon], State, LLC Filing Fee, LLC Annual Report, Incorporation Filing, Corp Annual Report, Notes
 */
async function fetchAndParseTable(): Promise<Map<StateCode, FeeRecord>> {
  console.log(`Fetching: ${SOURCE_URL}`);

  const response = await fetch(SOURCE_URL, {
    headers: {
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
      Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
  });

  if (!response.ok) throw new Error(`Failed to fetch: ${response.status}`);
  const html = await response.text();

  // Extract the <table>
  const tableMatch = html.match(/<table[\s\S]*?<\/table>/i);
  if (!tableMatch) throw new Error("No <table> found in page");

  // Extract all <tr> rows
  const rows = tableMatch[0].match(/<tr[\s\S]*?<\/tr>/gi) ?? [];
  const records = new Map<StateCode, FeeRecord>();

  for (const row of rows) {
    const cells = (row.match(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi) ?? [])
      .map((c) => c.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").trim());

    if (cells.length < 3) continue;

    // Col 1 is state name, col 2 is LLC Filing Fee, col 3 is LLC Annual Report
    const stateName = cells[1]?.trim();
    if (!stateName || stateName === "State") continue;

    const code = FULL_NAME_TO_CODE[stateName];
    if (!code) {
      if (stateName !== "United States") {
        console.log(`  ? Unrecognized state: "${stateName}"`);
      }
      continue;
    }

    const parseFee = (val: string): number => {
      const m = val.match(/\$?([\d,]+)/);
      return m ? parseInt(m[1].replace(/,/g, ""), 10) : 0;
    };

    records.set(code, {
      code,
      name: stateName,
      llcFilingFee: parseFee(cells[2] ?? ""),
      llcAnnualReport: parseFee(cells[3] ?? ""),
      notes: cells[6]?.trim() ?? "",
    });
  }

  return records;
}

async function main() {
  const dryRun = process.argv.includes("--dry-run");
  const onlyState = process.env.EXTRACT_ONLY_STATE?.trim().toUpperCase() as StateCode | undefined;

  const feeData = await fetchAndParseTable();
  console.log(`Parsed fee data for ${feeData.size} jurisdictions\n`);

  if (feeData.size < 45) {
    console.error("WARNING: Expected ~50 states but only parsed " + feeData.size);
    console.error("The page format may have changed. Aborting.");
    process.exit(1);
  }

  const now = new Date().toISOString();
  let updatedCount = 0;
  let skippedCount = 0;
  const changes: string[] = [];

  for (const stateCode of STATE_CODES) {
    if (onlyState && stateCode !== onlyState) continue;

    const existingPath = join(FORMATION_DIR, `${stateCode}.json`);
    if (!existsSync(existingPath)) {
      console.log(`  ⊘ ${stateCode}: no existing JSON, skipping`);
      skippedCount++;
      continue;
    }

    const existing = JSON.parse(readFileSync(existingPath, "utf8"));
    const fees = feeData.get(stateCode);

    if (!fees) {
      console.log(`  ⊘ ${stateCode}: not found in fee table, keeping existing`);
      skippedCount++;
      continue;
    }

    const newFilingFeeCents = dollarsToCents(fees.llcFilingFee);
    const newAnnualReportCents = dollarsToCents(fees.llcAnnualReport);
    const oldFilingFeeCents = existing.fees?.standard?.amount_cents ?? 0;
    const oldAnnualReportCents = existing.requirements?.annual_report_fee_cents ?? 0;

    const filingFeeChanged = newFilingFeeCents !== oldFilingFeeCents;
    const annualReportChanged = newAnnualReportCents !== oldAnnualReportCents;

    if (filingFeeChanged) {
      changes.push(`${stateCode} filing fee: $${oldFilingFeeCents / 100} → $${newFilingFeeCents / 100}`);
    }
    if (annualReportChanged) {
      changes.push(`${stateCode} annual report: $${oldAnnualReportCents / 100} → $${newAnnualReportCents / 100}`);
    }

    if (!filingFeeChanged && !annualReportChanged) {
      console.log(`  ≡ ${stateCode}: ${fees.name} — no changes (filing=$${fees.llcFilingFee}, annual=$${fees.llcAnnualReport})`);
      continue;
    }

    // Update fees
    existing.fees.standard.amount_cents = newFilingFeeCents;
    if (existing.requirements) {
      existing.requirements.annual_report_fee_cents = newAnnualReportCents;
      existing.requirements.annual_report_required = newAnnualReportCents > 0;
    }

    // Update verification
    existing.verification = {
      last_verified: now,
      sources: [
        ...(existing.verification?.sources?.filter((s: any) =>
          !s.name?.includes("World Population") && !s.name?.includes("worldpopulation")
        ) ?? []),
        {
          name: "World Population Review LLC Cost Table",
          url: SOURCE_URL,
          accessed_at: now,
        },
      ],
      verified_by: "deterministic_parse" as const,
      confidence: 0.99,
    };

    if (dryRun) {
      console.log(`  Δ ${stateCode}: ${fees.name} — filing=$${fees.llcFilingFee}, annual=$${fees.llcAnnualReport} (dry run, not writing)`);
    } else {
      // Validate before writing
      try {
        FormationRulesSchema.parse(existing);
      } catch (err: any) {
        console.error(`  ✗ ${stateCode}: schema validation failed after update`);
        if (err.errors) {
          for (const e of err.errors.slice(0, 3)) {
            console.error(`    ${e.path.join(".")}: ${e.message}`);
          }
        }
        continue;
      }

      writeFileSync(existingPath, JSON.stringify(existing, null, 2) + "\n", "utf8");
      console.log(`  ✓ ${stateCode}: ${fees.name} — filing=$${fees.llcFilingFee}, annual=$${fees.llcAnnualReport}`);
    }
    updatedCount++;
  }

  console.log(`\nSummary: ${updatedCount} updated, ${skippedCount} skipped`);
  if (changes.length > 0) {
    console.log("\nChanges:");
    for (const c of changes) console.log(`  ${c}`);
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
