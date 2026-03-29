#!/usr/bin/env tsx
/**
 * Portal Config Validation Script
 *
 * Run this before committing any changes to portal configs.
 * Usage: pnpm --filter @paperwork-labs/filing-engine validate-configs
 *
 * Checks:
 * 1. All configs parse against Zod schema
 * 2. Filing fees match known values
 * 3. Portal URLs use approved official domains (.gov or state-authorized portals)
 * 4. lastVerified is within 90 days
 * 5. Critical fields have fallback selectors
 */

import { createRequire } from "node:module";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { PortalConfigSchema } from "../src/types.js";

const require = createRequire(import.meta.url);
const dataPackagePath = require.resolve("@paperwork-labs/data/package.json");
const PORTALS_DIR = join(dirname(dataPackagePath), "src/portals");

interface ValidationResult {
  state: string;
  passed: boolean;
  errors: string[];
  warnings: string[];
}

const KNOWN_FEES: Record<string, number> = {
  CA: 70,
  TX: 300,
  FL: 125,
  DE: 90,
  WY: 100,
  NY: 200,
  NV: 425,
  IL: 150,
  GA: 100,
  WA: 180,
};

function validateConfig(filePath: string): ValidationResult {
  const state = filePath.split("/").pop()?.replace(".json", "").toUpperCase() ?? "UNKNOWN";
  const result: ValidationResult = {
    state,
    passed: true,
    errors: [],
    warnings: [],
  };

  try {
    const raw = readFileSync(filePath, "utf-8");
    const parsed = JSON.parse(raw);

    // Schema validation
    const schemaResult = PortalConfigSchema.safeParse(parsed);
    if (!schemaResult.success) {
      result.passed = false;
      result.errors.push(`Schema validation failed: ${schemaResult.error.message}`);
      return result;
    }

    const config = schemaResult.data;

    // Fee validation
    if (KNOWN_FEES[state] && config.filingFee !== KNOWN_FEES[state]) {
      result.passed = false;
      result.errors.push(
        `Fee mismatch: config has $${config.filingFee}, expected $${KNOWN_FEES[state]}`
      );
    }

    // URL validation (allow known official non-.gov domains)
    const url = new URL(config.portalUrl);
    const knownOfficialDomains = ["sunbiz.org", "nvsilverflume.gov", "wyobiz.wyo.gov"];
    const isOfficialDomain =
      url.hostname.endsWith(".gov") ||
      url.hostname.includes("state.") ||
      knownOfficialDomains.some((d) => url.hostname.includes(d));
    if (!isOfficialDomain) {
      result.warnings.push(`Portal URL ${config.portalUrl} is not a recognized official domain`);
    }

    // Freshness validation
    const lastVerified = new Date(config.lastVerified);
    const daysSince = (Date.now() - lastVerified.getTime()) / (1000 * 60 * 60 * 24);
    if (daysSince > 90) {
      result.warnings.push(`Config last verified ${Math.floor(daysSince)} days ago (>90 days)`);
    }

    // Selector fallback validation
    const criticalFields = ["businessName", "agentName"];
    for (const step of config.steps) {
      for (const field of step.fields) {
        if (criticalFields.includes(field.fieldId)) {
          if (!field.fallbackSelectors || field.fallbackSelectors.length === 0) {
            result.warnings.push(`Field ${field.fieldId} has no fallback selectors`);
          }
        }
      }
    }

    // State-specific checks
    if (state === "NY" && !config.notes?.toLowerCase().match(/publish|publication/)) {
      result.warnings.push("NY config should mention publication requirement");
    }
    if (state === "NV" && config.filingFee !== 425) {
      result.errors.push("NV fee should be $425 ($75 + $150 + $200)");
      result.passed = false;
    }
    if (state === "WA" && !config.notes?.toLowerCase().includes("email")) {
      result.warnings.push("WA config should mention email requirement");
    }
  } catch (error) {
    result.passed = false;
    result.errors.push(`Failed to parse config: ${error}`);
  }

  return result;
}

function main() {
  console.log("🔍 Validating portal configs...\n");

  const files = readdirSync(PORTALS_DIR).filter((f) => f.endsWith(".json"));
  const results: ValidationResult[] = [];

  for (const file of files) {
    const result = validateConfig(join(PORTALS_DIR, file));
    results.push(result);
  }

  let hasErrors = false;
  let hasWarnings = false;

  for (const result of results) {
    const icon = result.passed ? (result.warnings.length ? "⚠️" : "✅") : "❌";
    console.log(`${icon} ${result.state}`);

    for (const error of result.errors) {
      console.log(`   ❌ ERROR: ${error}`);
      hasErrors = true;
    }
    for (const warning of result.warnings) {
      console.log(`   ⚠️  WARN: ${warning}`);
      hasWarnings = true;
    }
  }

  console.log("\n" + "=".repeat(50));

  if (hasErrors) {
    console.log("❌ VALIDATION FAILED - Fix errors before committing");
    process.exit(1);
  } else if (hasWarnings) {
    console.log("⚠️  VALIDATION PASSED WITH WARNINGS - Review before committing");
    process.exit(0);
  } else {
    console.log("✅ ALL VALIDATIONS PASSED");
    process.exit(0);
  }
}

main();
