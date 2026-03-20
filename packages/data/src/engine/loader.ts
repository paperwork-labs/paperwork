import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { StateTaxRulesSchema } from "../schemas/tax.schema";
import { FormationRulesSchema } from "../schemas/formation.schema";
import { loadTaxData } from "./tax";
import { loadFormationData } from "./formation";
import type { StateCode } from "../types/common";
import type { StateTaxRules } from "../types/tax";
import type { FormationRules } from "../types/formation";

/**
 * Discover year directories under `src/tax` (numeric names only, e.g. 2024).
 */
export function discoverTaxYearDirs(taxRootDir: string): number[] {
  try {
    const names = readdirSync(taxRootDir);
    return names
      .filter((name) => {
        if (!/^\d{4}$/.test(name)) return false;
        return statSync(join(taxRootDir, name)).isDirectory();
      })
      .map((n) => Number(n))
      .sort((a, b) => a - b);
  } catch {
    return [];
  }
}

export function loadAllStates(dataDir?: string): {
  tax: StateCode[];
  formation: StateCode[];
  errors: { file: string; error: string }[];
} {
  const baseSrc = dataDir ?? join(__dirname, "..");
  const errors: { file: string; error: string }[] = [];
  const taxStates = new Set<StateCode>();
  const formationStates = new Set<StateCode>();

  const taxRoot = join(baseSrc, "tax");
  const years = discoverTaxYearDirs(taxRoot);

  for (const year of years) {
    const yearDir = join(taxRoot, String(year));
    let files: string[] = [];
    try {
      files = readdirSync(yearDir);
    } catch (e) {
      errors.push({ file: `tax/${year}`, error: String(e) });
      continue;
    }

    for (const file of files) {
      if (!file.endsWith(".json") || file.startsWith("_")) continue;
      const rel = `tax/${year}/${file}`;
      try {
        const raw = JSON.parse(readFileSync(join(yearDir, file), "utf-8"));
        const parsed = StateTaxRulesSchema.parse(raw);
        loadTaxData(parsed.state, parsed as StateTaxRules);
        taxStates.add(parsed.state);
      } catch (e) {
        errors.push({ file: rel, error: String(e) });
      }
    }
  }

  const formationDir = join(baseSrc, "formation");
  try {
    const formationFiles = readdirSync(formationDir).filter(
      (f) => f.endsWith(".json") && !f.startsWith("_"),
    );
    for (const file of formationFiles) {
      try {
        const raw = JSON.parse(readFileSync(join(formationDir, file), "utf-8"));
        const parsed = FormationRulesSchema.parse(raw);
        loadFormationData(parsed.state, parsed as FormationRules);
        formationStates.add(parsed.state);
      } catch (e) {
        errors.push({ file: `formation/${file}`, error: String(e) });
      }
    }
  } catch {
    /* directory may not exist */
  }

  return {
    tax: Array.from(taxStates).sort(),
    formation: Array.from(formationStates).sort(),
    errors,
  };
}
