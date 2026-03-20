import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { describe, it, expect } from "vitest";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import { discoverTaxYearDirs } from "../src/engine/loader";
import { STATE_CODES } from "../src/types/common";

const srcDir = join(__dirname, "../src");
const taxRoot = join(srcDir, "tax");
const formationDir = join(srcDir, "formation");

const taxFiles: { year: number; state: string; path: string }[] = [];
for (const year of discoverTaxYearDirs(taxRoot)) {
  const yearDir = join(taxRoot, String(year));
  for (const file of readdirSync(yearDir).filter((f) => f.endsWith(".json") && !f.startsWith("_"))) {
    const path = join(yearDir, file);
    if (!statSync(path).isFile()) continue;
    taxFiles.push({ year, state: file.replace(".json", ""), path });
  }
}

const formationFiles = readdirSync(formationDir)
  .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
  .map((f) => {
    const path = join(formationDir, f);
    return { state: f.replace(".json", ""), path };
  })
  .filter((entry) => statSync(entry.path).isFile());

describe("Tax JSON schema validation", () => {
  it.each(taxFiles)("$path", ({ path }) => {
    const raw: unknown = JSON.parse(readFileSync(path, "utf-8"));
    expect(() => StateTaxRulesSchema.parse(raw)).not.toThrow();
  });
});

describe("Formation JSON schema validation", () => {
  it.each(formationFiles)("$path", ({ path }) => {
    const raw: unknown = JSON.parse(readFileSync(path, "utf-8"));
    expect(() => FormationRulesSchema.parse(raw)).not.toThrow();
  });
});

describe("Tax: file-content cross-check", () => {
  it.each(taxFiles)("tax/$year/$state.json", ({ year, state, path }) => {
    const raw: unknown = JSON.parse(readFileSync(path, "utf-8"));
    const parsed = StateTaxRulesSchema.parse(raw);
    expect(parsed.state).toBe(state);
    expect(parsed.tax_year).toBe(year);
  });
});

describe("Formation: file-content cross-check", () => {
  it.each(formationFiles)("formation/$state.json", ({ state, path }) => {
    const raw: unknown = JSON.parse(readFileSync(path, "utf-8"));
    const parsed = FormationRulesSchema.parse(raw);
    expect(parsed.state).toBe(state);
  });
});

describe("Completeness", () => {
  it("all STATE_CODES present per tax year", () => {
    for (const year of discoverTaxYearDirs(taxRoot)) {
      const yearDir = join(taxRoot, String(year));
      const present = new Set(
        readdirSync(yearDir)
          .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
          .map((f) => f.replace(".json", "")),
      );
      for (const code of STATE_CODES) {
        expect(present.has(code), `missing tax/${year}/${code}.json`).toBe(true);
      }
    }
  });

  it("all STATE_CODES present in formation", () => {
    const present = new Set(formationFiles.map((f) => f.state));
    for (const code of STATE_CODES) {
      expect(present.has(code), `missing formation/${code}.json`).toBe(true);
    }
  });
});
