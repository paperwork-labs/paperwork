import { describe, it, expect, beforeEach } from "vitest";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import { loadAllStates, discoverTaxYearDirs } from "../src/engine/loader";
import {
  getStateTaxRules,
  calculateStateTax,
  clearTaxCache,
} from "../src/engine/tax";
import { clearFormationCache } from "../src/engine/formation";
import { STATE_CODES } from "../src/types/common";

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = join(__dirname, "../src");
const taxRoot = join(srcDir, "tax");

describe("loadAllStates", () => {
  beforeEach(() => {
    clearTaxCache();
    clearFormationCache();
  });

  it("loads all tax years and formation with no errors when data is present", () => {
    if (!existsSync(taxRoot)) {
      return;
    }
    const years = discoverTaxYearDirs(taxRoot);
    if (years.length === 0) {
      return;
    }

    const result = loadAllStates(srcDir);

    expect(result.errors, JSON.stringify(result.errors)).toEqual([]);

    for (const y of years) {
      for (const code of STATE_CODES) {
        const path = join(taxRoot, String(y), `${code}.json`);
        if (!existsSync(path)) continue;
        expect(getStateTaxRules(code, y), `${code} ${y}`).toBeDefined();
      }
    }

    const co2026 = getStateTaxRules("CO", 2026);
    if (co2026 && co2026.income_tax.type !== "none") {
      const tax = calculateStateTax("CO", 10_000_000, "single", 2026);
      expect(tax).toBeDefined();
      expect(typeof tax).toBe("number");
    }
  });

  it("returns empty tax list when tax root is missing", () => {
    clearTaxCache();
    clearFormationCache();
    const badDir = join(__dirname, "__no_data__");
    const result = loadAllStates(badDir);
    expect(result.tax).toEqual([]);
    expect(result.formation).toEqual([]);
  });
});
