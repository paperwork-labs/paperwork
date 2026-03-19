import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import type { StateCode, StateSources } from "../src/schemas/source-registry.schema";
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

async function extractFormationData(
  stateCode: StateCode,
  stateName: string,
  sosUrl: string,
  pageContent: string,
  retryCount = 0
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
    // If validation error and we have retries left, retry with error message
    if (error.name === "ZodError" && retryCount < 2) {
      const errorDetails = error.errors.map((e: any) => `${e.path.join(".")}: ${e.message}`).join("\n");
      console.error(`${stateCode}: Validation failed, retrying (${retryCount + 1}/2)...`);
      return extractFormationData(
        stateCode,
        stateName,
        sosUrl,
        `${pageContent}\n\nPrevious attempt failed validation:\n${errorDetails}\n\nPlease fix these errors and return valid JSON.`,
        retryCount + 1
      );
    }
    throw error;
  }
}

async function main() {
  const outputDir = join(__dirname, "../src/formation");
  mkdirSync(outputDir, { recursive: true });

  const now = new Date().toISOString();

  for (const stateCode of STATE_CODES) {
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

      // Fetch page content
      let pageContent: string;
      try {
        pageContent = await fetchPageContent(sosSource.url);
      } catch (error: any) {
        console.error(`${stateCode}: Failed to fetch page:`, error.message);
        continue;
      }

      // Extract formation data
      let formationData: any;
      try {
        formationData = await extractFormationData(stateCode, sources.state_name, sosSource.url, pageContent);
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
        verified_by: "ai_extraction",
        confidence: 0.85,
      };

      // Set URLs and required fields from source registry
      formationData.state = stateCode;
      formationData.state_name = sources.state_name;
      formationData.entity_type = "LLC";
      formationData.sos_url = sosSource.url;

      // Write output file
      const outputPath = join(outputDir, `${stateCode}.json`);
      writeFileSync(outputPath, JSON.stringify(formationData, null, 2) + "\n", "utf8");

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
