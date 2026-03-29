/**
 * Portal Config Loader
 *
 * Loads state portal configurations from the @paperwork-labs/data package.
 * Uses createRequire for proper package resolution that works after tsc compilation.
 */

import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import type { PortalConfig } from "../../types.js";
import { PortalConfigSchema } from "../../types.js";

const require = createRequire(import.meta.url);

function getPortalsDir(): string {
  const dataPackagePath = require.resolve("@paperwork-labs/data/package.json");
  return join(dirname(dataPackagePath), "src/portals");
}

const configCache = new Map<string, PortalConfig>();

export function loadPortalConfig(stateCode: string): PortalConfig {
  const upperState = stateCode.toUpperCase();

  if (configCache.has(upperState)) {
    return configCache.get(upperState)!;
  }

  const portalsDir = getPortalsDir();
  const configPath = join(portalsDir, `${upperState.toLowerCase()}.json`);

  try {
    const raw = readFileSync(configPath, "utf-8");
    const parsed = JSON.parse(raw);
    const validated = PortalConfigSchema.parse(parsed);
    configCache.set(upperState, validated);
    return validated;
  } catch (error) {
    throw new Error(
      `Failed to load portal config for ${upperState}: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

export function getAvailablePortalStates(): string[] {
  return ["CA", "TX", "FL", "DE", "WY", "NY", "NV", "IL", "GA", "WA"];
}
