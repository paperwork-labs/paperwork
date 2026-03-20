import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { describe, it, expect } from "vitest";
import { discoverTaxYearDirs } from "../src/engine/loader";

const srcDir = join(__dirname, "../src");
const taxRoot = join(srcDir, "tax");

const taxFiles: { year: number; state: string; path: string }[] = [];
for (const year of discoverTaxYearDirs(taxRoot)) {
  const yearDir = join(taxRoot, String(year));
  for (const file of readdirSync(yearDir).filter((f) => f.endsWith(".json") && !f.startsWith("_"))) {
    const path = join(yearDir, file);
    if (!statSync(path).isFile()) continue;
    taxFiles.push({ year, state: file.replace(".json", ""), path });
  }
}

describe("Data freshness", () => {
  const STALE_DAYS = 90;
  const now = new Date();

  it.each(taxFiles)("tax/$year/$state.json should not be ancient", ({ path, year, state }) => {
    const data = JSON.parse(readFileSync(path, "utf-8")) as { verification?: { last_verified?: string } };
    const lastVerified = new Date(data.verification?.last_verified ?? "");
    const ageMs = now.getTime() - lastVerified.getTime();
    const ageDays = ageMs / (1000 * 60 * 60 * 24);
    if (ageDays > STALE_DAYS) {
      console.warn(`STALE: ${path} — ${Math.round(ageDays)} days old`);
    }
    expect(ageDays, `${path} missing or invalid last_verified`).toBeLessThan(365);
  });
});
