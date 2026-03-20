import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import type { StateCode } from "../src/types/common";
import type { StateSources } from "../src/schemas/source-registry.schema";
import { openai, fetchPageContent, sleep, STATE_CODES } from "./extract-utils";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load template for system prompt
const templatePath = join(__dirname, "../src/formation/_template.json");
const templateExample = JSON.parse(readFileSync(templatePath, "utf8"));

function buildSystemPrompt(stateName: string): string {
  return `You are extracting LLC formation rules for ${stateName} for the year 2026.

CRITICAL REQUIREMENTS:
- entity_type must always be "LLC" (literal string)
- All fee amounts must be in CENTS (e.g., $100.00 = 10000 cents)
- processing_days must be positive integers
- filing.primary.method must be one of: "api", "portal", or "mail"
- All requirements.* fields are booleans (true/false)
- naming.required_suffix is an array of strings (e.g., ["LLC", "L.L.C."])
- naming.restricted_words is an array of strings (can be empty)
- fees.standard is REQUIRED
- fees.expedited is optional
- fees.name_reservation is optional
- filing.fallback is optional
- compliance fields are optional strings or numbers

Here is a complete example JSON structure:

${JSON.stringify(templateExample, null, 2)}

Extract the LLC formation rules from the provided web page content and return a valid JSON object matching this structure.`;
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

async function extractFormationData(
  stateCode: StateCode,
  stateName: string,
  pageContent: string,
  validationRetryCount = 0,
  apiRetryCount = 0
): Promise<any> {
  const systemPrompt = buildSystemPrompt(stateName);
  const userPrompt = `Extract LLC formation rules for ${stateName} (${stateCode}) from the following web page content:\n\n${pageContent}`;

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
    const validated = FormationRulesSchema.parse(parsed);

    return validated;
  } catch (error: any) {
    // Handle retryable API errors (429, 5xx, timeouts) with exponential backoff
    if (isRetryableError(error) && apiRetryCount < 2) {
      const backoffMs = Math.pow(2, apiRetryCount) * 1000; // 1s, 2s, 4s
      console.error(`${stateCode}: API error (${error.status || error.code}), retrying after ${backoffMs}ms (${apiRetryCount + 1}/2)...`);
      await sleep(backoffMs);
      return extractFormationData(
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
      return extractFormationData(
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
  const outputDir = join(__dirname, "../src/formation");
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

      // Find SOS URL
      const sosSource = sources.formation_sources.find((s) => s.type === "sos");
      if (!sosSource) {
        console.error(`${stateCode}: No SOS URL found`);
        continue;
      }

      // Fetch page content (many SOS sites block bots with 403; fall back to model-only extraction)
      let pageContent: string;
      let usedFetchFallback = false;
      try {
        pageContent = await fetchPageContent(sosSource.url);
      } catch (error: any) {
        console.error(
          `${stateCode}: Failed to fetch SOS page (${error.message}); using model-only fallback (lower confidence).`,
        );
        usedFetchFallback = true;
        pageContent = `Official SOS URL: ${sosSource.url}. Live HTML was not available (403/404/timeout or bot protection). Using public knowledge only: produce schema-valid LLC formation rules for ${sources.state_name} (${stateCode}) for 2026 — typical filing fees, processing times, registered agent rules, LLC naming suffixes, and filing methods (online/portal/mail) as generally applicable for this jurisdiction.`;
      }

      // Extract formation data
      let formationData: any;
      try {
        formationData = await extractFormationData(stateCode, sources.state_name, pageContent);
      } catch (error: any) {
        console.error(`${stateCode}: Failed to extract formation data after 3 attempts:`, error.message);
        continue;
      }

      // Build verification metadata
      formationData.verification = {
        last_verified: now,
        sources: [
          {
            name: sosSource.name,
            url: sosSource.url,
            accessed_at: now,
          },
        ],
        verified_by: usedFetchFallback ? "ai_extraction_fallback" : "ai_extraction",
        confidence: usedFetchFallback ? 0.55 : 0.85,
      };

      // Set URLs and required fields from source registry
      formationData.state = stateCode;
      formationData.state_name = sources.state_name;
      formationData.entity_type = "LLC";
      formationData.sos_url = sosSource.url;

      // Validate final formation data against schema before writing
      const finalFormationData = FormationRulesSchema.parse(formationData);

      // Write output file
      const outputPath = join(outputDir, `${stateCode}.json`);
      writeFileSync(outputPath, JSON.stringify(finalFormationData, null, 2) + "\n", "utf8");

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
