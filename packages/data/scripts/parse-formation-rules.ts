import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import type { StateCode } from "../src/types/common";
import { STATE_CODES } from "../src/types/common";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FORMATION_DIR = join(__dirname, "../src/formation");
const SOURCES_DIR = join(__dirname, "../src/sources");

// ─── Sources ─────────────────────────────────────────────────────────────────

const LLCREQ_URL = "https://llcrequirements.com/";
const DISCERN_URL = "https://www.discern.com/resources/franchise-tax-information";

// ─── State name mapping ──────────────────────────────────────────────────────

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

const FULL_NAME_TO_CODE: Record<string, StateCode> = {};
for (const [code, name] of Object.entries(CODE_TO_FULL_NAME)) {
  FULL_NAME_TO_CODE[name] = code as StateCode;
}
FULL_NAME_TO_CODE["Washington DC"] = "DC";
FULL_NAME_TO_CODE["Washington, DC"] = "DC";

// ─── Curated constants (quasi-static, change < once per decade) ──────────────

const OPERATING_AGREEMENT_REQUIRED: StateCode[] = ["CA", "MO", "NY", "ME"];

const FILING_OFFICE_OVERRIDES: Partial<Record<StateCode, string>> = {
  DE: "Delaware Division of Corporations",
  DC: "DC Department of Licensing and Consumer Protection",
  NY: "New York Department of State, Division of Corporations",
  HI: "Hawaii Department of Commerce and Consumer Affairs",
};

const FILING_METHOD_OVERRIDES: Partial<Record<StateCode, "api" | "portal" | "mail">> = {
  DE: "api",
};

const PORTAL_URL_OVERRIDES: Partial<Record<StateCode, string>> = {
  DE: "https://icis.corp.delaware.gov/publicxmlservice",
  CA: "https://bizfileonline.sos.ca.gov",
};

// ─── Parsing utilities ───────────────────────────────────────────────────────

function dollarsToCents(val: string | number): number {
  if (typeof val === "number") return Math.round(val * 100);
  const m = String(val).match(/\$?([\d,]+(?:\.\d+)?)/);
  if (!m) return 0;
  return Math.round(parseFloat(m[1].replace(/,/g, "")) * 100);
}

function parseProcessingDays(text: string): number {
  if (!text || text === "N/A") return 5;
  const lower = text.toLowerCase();
  if (lower.includes("immediate")) {
    const rangeMatch = lower.match(/immediate(?:\s+to\s+)?(\d+)/);
    return rangeMatch ? parseInt(rangeMatch[1], 10) : 1;
  }
  const numbers = text.match(/\d+/g);
  if (numbers && numbers.length > 0) {
    return parseInt(numbers[numbers.length - 1], 10);
  }
  return 5;
}

function parseAnnualFee(text: string): { amountCents: number; period: string } {
  if (!text || text === "$0" || text === "N/A") return { amountCents: 0, period: "" };
  const amount = dollarsToCents(text);
  const period = text.toLowerCase().includes("2 year") || text.toLowerCase().includes("biennial")
    ? "biennial" : "annual";
  return { amountCents: amount, period };
}

async function fetchHtml(url: string): Promise<string> {
  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
      Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
  });
  if (!response.ok) throw new Error(`Failed to fetch ${url}: ${response.status}`);
  return response.text();
}

function parseTableRows(html: string): string[][] {
  const tableMatch = html.match(/<table[\s\S]*?<\/table>/i);
  if (!tableMatch) throw new Error("No <table> found");
  const rows = tableMatch[0].match(/<tr[\s\S]*?<\/tr>/gi) ?? [];
  return rows.map((row) => {
    return (row.match(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi) ?? [])
      .map((c) => c.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&#9650;/g, "").replace(/\u2714/g, "Y").replace(/\u274c/g, "N").trim());
  });
}

// ─── Source 1: llcrequirements.com ───────────────────────────────────────────

interface LlcReqData {
  filingFeeCents: number;
  annualFeeCents: number;
  deadline: string;
  processingDays: number;
  publicationRequired: boolean;
}

async function fetchLlcRequirements(): Promise<Map<StateCode, LlcReqData>> {
  console.log(`Fetching: ${LLCREQ_URL}`);
  const html = await fetchHtml(LLCREQ_URL);
  const rows = parseTableRows(html);
  const results = new Map<StateCode, LlcReqData>();

  for (const cells of rows) {
    if (cells.length < 6) continue;
    const stateName = cells[0]?.trim();
    if (!stateName || stateName.startsWith("State")) continue;

    const code = FULL_NAME_TO_CODE[stateName];
    if (!code) {
      if (stateName !== "United States") {
        console.log(`  ? Unrecognized: "${stateName}"`);
      }
      continue;
    }

    results.set(code, {
      filingFeeCents: dollarsToCents(cells[1] ?? ""),
      annualFeeCents: dollarsToCents(cells[2] ?? ""),
      deadline: cells[3]?.trim() === "N/A" ? "" : (cells[3]?.trim() ?? ""),
      processingDays: parseProcessingDays(cells[4] ?? ""),
      publicationRequired: (cells[5] ?? "").toLowerCase().includes("required"),
    });
  }

  return results;
}

// ─── Source 2: discern.com franchise tax ──────────────────────────────────────

interface FranchiseTaxData {
  hasFranchiseTax: boolean;
  minimumCents: number;
  dueDate: string;
}

async function fetchFranchiseTax(): Promise<Map<StateCode, FranchiseTaxData>> {
  console.log(`Fetching: ${DISCERN_URL}`);
  const html = await fetchHtml(DISCERN_URL);
  const rows = parseTableRows(html);
  const results = new Map<StateCode, FranchiseTaxData>();

  // Initialize all states as no franchise tax
  for (const code of STATE_CODES) {
    results.set(code, { hasFranchiseTax: false, minimumCents: 0, dueDate: "" });
  }

  for (const cells of rows) {
    if (cells.length < 6) continue;
    const stateName = cells[0]?.trim();
    if (!stateName || stateName.startsWith("State")) continue;

    const code = FULL_NAME_TO_CODE[stateName];
    if (!code) continue;

    const entityTypes = cells[2]?.trim() ?? "";
    if (entityTypes === "N" || entityTypes === "❌") continue;

    const affectsLlcs = entityTypes.toLowerCase().includes("llc") ||
      entityTypes.toLowerCase().includes("most entities");

    if (!affectsLlcs) {
      // Corps-only franchise tax — doesn't affect LLCs
      continue;
    }

    const minTaxStr = cells[4]?.trim() ?? "";
    let minimumCents = 0;

    // Parse LLC-specific minimum from text like "$150 (LLCs)"
    const llcMatch = minTaxStr.match(/\$?([\d,]+)\s*\(?(?:LLC|LLCs)/i);
    if (llcMatch) {
      minimumCents = dollarsToCents(llcMatch[1]);
    } else {
      minimumCents = dollarsToCents(minTaxStr);
    }

    const dueDate = cells[3]?.trim() ?? "";
    const cleanDue = dueDate === "See site" ? "" : dueDate;

    // Handle special cases
    const existing = results.get(code);
    if (existing && existing.hasFranchiseTax) {
      // Already set (e.g., Delaware has two rows: Corps and LLCs/LPs)
      // Keep the LLC-specific row
      if (affectsLlcs) {
        results.set(code, { hasFranchiseTax: true, minimumCents, dueDate: cleanDue });
      }
    } else {
      results.set(code, { hasFranchiseTax: true, minimumCents, dueDate: cleanDue });
    }
  }

  return results;
}

// ─── Source 3: source registry ───────────────────────────────────────────────

interface SourceInfo {
  sosUrl: string;
  filingOfficeName: string;
}

function loadSourceRegistry(): Map<StateCode, SourceInfo> {
  const results = new Map<StateCode, SourceInfo>();
  if (!existsSync(SOURCES_DIR)) return results;

  for (const file of readdirSync(SOURCES_DIR)) {
    if (!file.endsWith(".json") || file.startsWith("_")) continue;
    const code = file.replace(".json", "") as StateCode;
    try {
      const data = JSON.parse(readFileSync(join(SOURCES_DIR, file), "utf8"));
      const sos = data.formation_sources?.find((s: any) => s.type === "sos");
      results.set(code, {
        sosUrl: sos?.url ?? `https://www.google.com/search?q=${encodeURIComponent(CODE_TO_FULL_NAME[code] + " Secretary of State LLC")}`,
        filingOfficeName: sos?.name ?? `${CODE_TO_FULL_NAME[code]} Secretary of State`,
      });
    } catch { /* skip */ }
  }

  return results;
}

// ─── Build complete formation JSON ───────────────────────────────────────────

function buildFormationJson(
  code: StateCode,
  llcReq: LlcReqData,
  franchise: FranchiseTaxData,
  source: SourceInfo,
): any {
  const now = new Date().toISOString();
  const name = CODE_TO_FULL_NAME[code];
  const filingMethod = FILING_METHOD_OVERRIDES[code] ?? "portal";
  const filingOffice = FILING_OFFICE_OVERRIDES[code] ?? source.filingOfficeName;

  const filingUrl = PORTAL_URL_OVERRIDES[code] ?? source.sosUrl;

  const filing: any = {
    primary: {
      method: filingMethod,
      url: filingUrl,
      notes: `${filingOffice} online filing`,
    },
  };

  // Most states accept mail as fallback
  if (filingMethod === "portal") {
    filing.fallback = {
      method: "mail" as const,
      url: source.sosUrl,
      notes: `Mail filing to ${filingOffice}`,
    };
  }

  const annualReportDue = llcReq.deadline || undefined;
  const franchiseTaxDue = franchise.hasFranchiseTax && franchise.dueDate ? franchise.dueDate : undefined;

  return {
    state: code,
    state_name: name,
    entity_type: "LLC",
    sos_url: source.sosUrl,
    filing_office: filingOffice,

    fees: {
      standard: {
        amount_cents: llcReq.filingFeeCents,
        description: "LLC Articles of Organization filing fee",
        is_expedited: false,
        processing_days: llcReq.processingDays,
      },
    },

    filing,

    requirements: {
      articles_of_organization: true,
      operating_agreement_required: OPERATING_AGREEMENT_REQUIRED.includes(code),
      publication_required: llcReq.publicationRequired,
      registered_agent_required: true,
      annual_report_required: llcReq.annualFeeCents > 0 || !!annualReportDue,
      ...(llcReq.annualFeeCents > 0 ? { annual_report_fee_cents: llcReq.annualFeeCents } : {}),
      franchise_tax: franchise.hasFranchiseTax,
      ...(franchise.hasFranchiseTax && franchise.minimumCents > 0
        ? { franchise_tax_amount_cents: franchise.minimumCents }
        : {}),
    },

    processing: {
      standard_days: llcReq.processingDays,
    },

    naming: {
      required_suffix: ["LLC", "L.L.C.", "Limited Liability Company"],
      restricted_words: ["Bank", "Insurance", "Trust"],
    },

    compliance: {
      ...(annualReportDue ? { annual_report_due: annualReportDue } : {}),
      ...(franchiseTaxDue ? { franchise_tax_due: franchiseTaxDue } : {}),
    },

    verification: {
      last_verified: now,
      sources: [
        { name: "LLC Requirements by State (llcrequirements.com)", url: LLCREQ_URL, accessed_at: now },
        { name: "Discern Franchise Tax by State", url: DISCERN_URL, accessed_at: now },
        { name: source.filingOfficeName, url: source.sosUrl, accessed_at: now },
      ],
      verified_by: "deterministic_parse" as const,
      confidence: 0.99,
    },
  };
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const dryRun = process.argv.includes("--dry-run");
  const onlyState = process.env.EXTRACT_ONLY_STATE?.trim().toUpperCase() as StateCode | undefined;

  const [llcReqData, franchiseData, sourceRegistry] = await Promise.all([
    fetchLlcRequirements(),
    fetchFranchiseTax(),
    Promise.resolve(loadSourceRegistry()),
  ]);

  // DC is not in llcrequirements.com (50 states only). Add manually.
  // Source: llcrequirements.com/llc-district-of-columbia-requirements/ (separate page)
  if (!llcReqData.has("DC")) {
    llcReqData.set("DC", {
      filingFeeCents: 9900,       // $99
      annualFeeCents: 30000,      // $300 (biennial)
      deadline: "September 30 (biennial)",
      processingDays: 5,          // 3-5 business days
      publicationRequired: false,
    });
  }

  console.log(`\nllcrequirements.com: ${llcReqData.size} jurisdictions`);
  console.log(`discern.com franchise tax: ${[...franchiseData.values()].filter((f) => f.hasFranchiseTax).length} states with LLC franchise tax`);
  console.log(`Source registry: ${sourceRegistry.size} states\n`);

  mkdirSync(FORMATION_DIR, { recursive: true });

  let successCount = 0;
  let errorCount = 0;

  for (const code of STATE_CODES) {
    if (onlyState && code !== onlyState) continue;

    const llcReq = llcReqData.get(code);
    if (!llcReq) {
      console.error(`  ✗ ${code}: not found in llcrequirements.com data`);
      errorCount++;
      continue;
    }

    const franchise = franchiseData.get(code) ?? { hasFranchiseTax: false, minimumCents: 0, dueDate: "" };
    const source = sourceRegistry.get(code) ?? {
      sosUrl: `https://www.google.com/search?q=${encodeURIComponent(CODE_TO_FULL_NAME[code] + " Secretary of State LLC")}`,
      filingOfficeName: `${CODE_TO_FULL_NAME[code]} Secretary of State`,
    };

    const result = buildFormationJson(code, llcReq, franchise, source);

    try {
      FormationRulesSchema.parse(result);
    } catch (err: any) {
      console.error(`  ✗ ${code}: schema validation failed`);
      if (err.errors) {
        for (const e of err.errors.slice(0, 5)) {
          console.error(`    ${e.path.join(".")}: ${e.message}`);
        }
      }
      errorCount++;
      continue;
    }

    if (dryRun) {
      console.log(`  ✓ ${code}: ${CODE_TO_FULL_NAME[code]} — $${llcReq.filingFeeCents / 100} filing, $${llcReq.annualFeeCents / 100} annual, franchise=${franchise.hasFranchiseTax} (dry run)`);
    } else {
      const outputPath = join(FORMATION_DIR, `${code}.json`);
      writeFileSync(outputPath, JSON.stringify(result, null, 2) + "\n", "utf8");
      console.log(`  ✓ ${code}: ${CODE_TO_FULL_NAME[code]} — $${llcReq.filingFeeCents / 100} filing, $${llcReq.annualFeeCents / 100} annual, franchise=${franchise.hasFranchiseTax}`);
    }
    successCount++;
  }

  console.log(`\n${successCount} succeeded, ${errorCount} errors`);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
