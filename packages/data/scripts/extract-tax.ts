import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import type { StateCode } from "../src/types/common";
import type { StateSources } from "../src/schemas/source-registry.schema";
import { openai, fetchPageContent, sleep, STATE_CODES } from "./extract-utils";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Tax type mappings to help GPT
const NO_INCOME_TAX_STATES: StateCode[] = ["AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"];
const FLAT_TAX_STATES: StateCode[] = ["CO", "IL", "IN", "KY", "MA", "MI", "NC", "PA", "UT"];

// Load template for system prompt
const templatePath = join(__dirname, "../src/tax/_template.json");
const templateExample = JSON.parse(readFileSync(templatePath, "utf8"));

function buildSystemPrompt(stateCode: StateCode, stateName: string): string {
  const taxTypeHint = NO_INCOME_TAX_STATES.includes(stateCode)
    ? "This state has NO income tax. Use income_tax: { type: 'none' }"
    : FLAT_TAX_STATES.includes(stateCode)
    ? "This state has a FLAT income tax rate. Use income_tax: { type: 'flat', flat_rate_bps: <rate_in_basis_points> }"
    : "This state has a PROGRESSIVE income tax with brackets. Use income_tax: { type: 'progressive', brackets: { single: [...], married_filing_jointly: [...], married_filing_separately: [...], head_of_household: [...] } }";

  return `You are extracting state tax data for ${stateName} (${stateCode}) for tax year 2026.

${taxTypeHint}

CRITICAL REQUIREMENTS:
- All monetary amounts must be in CENTS (e.g., $5,000 = 500000 cents)
- All tax rates must be in BASIS POINTS (e.g., 4.40% = 440 basis points)
- tax_year must be 2026
- For progressive tax states, you MUST include brackets for all 4 filing statuses: single, married_filing_jointly, married_filing_separately, head_of_household
- Each bracket must have min_income_cents, max_income_cents (null for top bracket), and rate_bps
- standard_deductions is an array with at least one entry per filing status
- personal_exemption.amount_cents is per person
- notable_credits and notable_deductions are arrays (can be empty)
- local_taxes.has_local_income_tax is a boolean
- reciprocity.has_reciprocity is a boolean, reciprocal_states is optional array

Here is a complete example JSON structure showing all three income_tax variants:

${JSON.stringify(templateExample, null, 2)}

Extract the tax data from the provided web page content and return a valid JSON object matching this structure.`;
}

function isRetryableError(error: any): boolean {
  // Check for OpenAI API errors that are retryable
  if (error.status === 429 || error.status === 500 || error.status === 502 || error.status === 503 || error.status === 504) {
    return true;
  }
  // Check for network/timeout errors
  if (error.code === "ECONNRESET" || error.code === "ETIMEDOUT" || error.message?.includes("timeout")) {
    return true;
  }
  return false;
}

async function extractTaxData(
  stateCode: StateCode,
  stateName: string,
  pageContent: string,
  validationRetryCount = 0,
  apiRetryCount = 0
): Promise<any> {
  const systemPrompt = buildSystemPrompt(stateCode, stateName);
  const userPrompt = `Extract tax data for ${stateName} (${stateCode}) from the following web page content:\n\n${pageContent}`;

  try {
    const response = await openai.chat.completions.create({
      model: "gpt-4o",
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      response_format: { type: "json_object" },
      temperature: 0.3,
    });

    const content = response.choices[0]?.message?.content;
    if (!content) {
      throw new Error("Empty response from OpenAI");
    }

    const parsed = JSON.parse(content);

    // Validate against schema
    const validated = StateTaxRulesSchema.parse(parsed);

    return validated;
  } catch (error: any) {
    // Handle retryable API errors (429, 5xx, timeouts) with exponential backoff
    if (isRetryableError(error) && apiRetryCount < 2) {
      const backoffMs = Math.pow(2, apiRetryCount) * 1000; // 1s, 2s, 4s
      console.error(`${stateCode}: API error (${error.status || error.code}), retrying after ${backoffMs}ms (${apiRetryCount + 1}/2)...`);
      await sleep(backoffMs);
      return extractTaxData(
        stateCode,
        stateName,
        pageContent,
        validationRetryCount,
        apiRetryCount + 1
      );
    }

    // If validation error and we have retries left, retry with error message
    if (error.name === "ZodError" && validationRetryCount < 2) {
      const errorDetails = error.errors.map((e: any) => `${e.path.join(".")}: ${e.message}`).join("\n");
      console.error(`${stateCode}: Validation failed, retrying (${validationRetryCount + 1}/2)...`);
      return extractTaxData(
        stateCode,
        stateName,
        `${pageContent}\n\nPrevious attempt failed validation:\n${errorDetails}\n\nPlease fix these errors and return valid JSON.`,
        validationRetryCount + 1,
        apiRetryCount
      );
    }
    throw error;
  }
}

async function main() {
  const outputDir = join(__dirname, "../src/tax");
  mkdirSync(outputDir, { recursive: true });

  const now = new Date().toISOString();

  const onlyRaw = process.env.EXTRACT_ONLY_STATE?.trim().toUpperCase();
  const codes: StateCode[] =
    onlyRaw && (STATE_CODES as readonly string[]).includes(onlyRaw)
      ? ([onlyRaw] as StateCode[])
      : [...STATE_CODES];

  for (const stateCode of codes) {
    try {
      // Read source registry
      const sourcePath = join(__dirname, "../src/sources", `${stateCode}.json`);
      const sourceContent = readFileSync(sourcePath, "utf8");
      const sources: StateSources = JSON.parse(sourceContent);

      if (sources.state !== stateCode) {
        console.error(`${stateCode}: State code mismatch in source file`);
        continue;
      }

      // Find Tax Foundation URL
      const taxFoundationSource = sources.tax_sources.find((s) => s.type === "tax_foundation");
      if (!taxFoundationSource) {
        console.error(`${stateCode}: No Tax Foundation URL found`);
        continue;
      }

      // Find DOR URL
      const dorSource = sources.tax_sources.find((s) => s.type === "dor");

      // Fetch page content
      let pageContent: string;
      try {
        pageContent = await fetchPageContent(taxFoundationSource.url);
      } catch (error: any) {
        console.error(`${stateCode}: Failed to fetch page:`, error.message);
        continue;
      }

      // Extract tax data
      let taxData: any;
      try {
        taxData = await extractTaxData(stateCode, sources.state_name, pageContent);
      } catch (error: any) {
        console.error(`${stateCode}: Failed to extract tax data after 3 attempts:`, error.message);
        continue;
      }

      // Build verification metadata
      const verificationSources = [
        {
          name: taxFoundationSource.name,
          url: taxFoundationSource.url,
          accessed_at: now,
        },
      ];
      if (dorSource) {
        verificationSources.push({
          name: dorSource.name,
          url: dorSource.url,
          accessed_at: now,
        });
      }

      taxData.verification = {
        last_verified: now,
        sources: verificationSources,
        verified_by: "ai_extraction",
        confidence: 0.85,
      };

      // Set URLs from source registry (dor_url is required, so use a placeholder if missing)
      taxData.dor_url = dorSource?.url || taxFoundationSource.url; // Fallback to Tax Foundation URL if DOR missing
      taxData.tax_foundation_url = taxFoundationSource.url;

      // Ensure state and state_name match
      taxData.state = stateCode;
      taxData.state_name = sources.state_name;
      taxData.tax_year = 2026;

      // Validate final tax data against schema before writing
      const finalTaxData = StateTaxRulesSchema.parse(taxData);

      // Write output file
      const outputPath = join(outputDir, `${stateCode}.json`);
      writeFileSync(outputPath, JSON.stringify(finalTaxData, null, 2) + "\n", "utf8");

      console.log(`✓ ${stateCode}: ${sources.state_name}`);

      // Sleep 2 seconds before next state
      await sleep(2000);
    } catch (error: any) {
      console.error(`${stateCode}: Unexpected error:`, error.message);
      continue;
    }
  }

  console.log("\nExtraction complete!");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
