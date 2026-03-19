import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { StateSourcesSchema } from "../src/schemas/source-registry.schema";
import { loadSources, getStateSources, getAllSourceStates, clearSourcesCache } from "../src/sources";
import { STATE_CODES } from "../src/types/common";

const __dirname = dirname(fileURLToPath(import.meta.url));

describe("StateSourcesSchema", () => {
  it("accepts valid Delaware source registry", () => {
    const deSources = JSON.parse(
      readFileSync(join(__dirname, "../src/sources/DE.json"), "utf8")
    );
    expect(() => StateSourcesSchema.parse(deSources)).not.toThrow();
    const parsed = StateSourcesSchema.parse(deSources);
    expect(parsed.state).toBe("DE");
    expect(parsed.state_name).toBe("Delaware");
    expect(parsed.tax_sources.length).toBeGreaterThanOrEqual(1);
    expect(parsed.formation_sources.length).toBeGreaterThanOrEqual(1);
  });

  it("rejects invalid state code", () => {
    const invalid = {
      state: "XX",
      state_name: "Invalid State",
      tax_sources: [
        {
          name: "Test",
          url: "https://example.com",
          type: "dor",
          scrape_method: "page_parse",
        },
      ],
      formation_sources: [
        {
          name: "Test",
          url: "https://example.com",
          type: "sos",
          scrape_method: "page_parse",
        },
      ],
      last_validated: "2026-03-19T00:00:00.000Z",
    };
    expect(() => StateSourcesSchema.parse(invalid)).toThrow();
  });
});

describe("Sources Engine", () => {
  beforeEach(() => {
    clearSourcesCache();
  });

  it("loads and retrieves sources", () => {
    const deSources = JSON.parse(
      readFileSync(join(__dirname, "../src/sources/DE.json"), "utf8")
    );
    const parsed = StateSourcesSchema.parse(deSources);

    loadSources("DE", parsed);
    const retrieved = getStateSources("DE");

    expect(retrieved).toBeDefined();
    expect(retrieved?.state).toBe(parsed.state);
    expect(retrieved?.state_name).toBe(parsed.state_name);
    expect(retrieved?.tax_sources.length).toBe(parsed.tax_sources.length);
    expect(retrieved?.formation_sources.length).toBe(parsed.formation_sources.length);
  });

  it("returns undefined for unloaded states", () => {
    expect(getStateSources("CA")).toBeUndefined();
  });

  it("lists loaded states", () => {
    const deSources = JSON.parse(
      readFileSync(join(__dirname, "../src/sources/DE.json"), "utf8")
    );
    const parsed = StateSourcesSchema.parse(deSources);

    loadSources("DE", parsed);
    const states = getAllSourceStates();

    expect(states).toContain("DE");
    expect(states.length).toBe(1);
  });

  it("returns states in sorted order", () => {
    const deSources = JSON.parse(
      readFileSync(join(__dirname, "../src/sources/DE.json"), "utf8")
    );
    const caSources = JSON.parse(
      readFileSync(join(__dirname, "../src/sources/CA.json"), "utf8")
    );

    loadSources("DE", StateSourcesSchema.parse(deSources));
    loadSources("CA", StateSourcesSchema.parse(caSources));

    const states = getAllSourceStates();
    expect(states).toEqual(["CA", "DE"]);
  });
});

describe("All 51 Source Files", () => {
  it("validates all state source JSON files", () => {
    for (const code of STATE_CODES) {
      const filePath = join(__dirname, "../src/sources", `${code}.json`);
      const content = readFileSync(filePath, "utf8");
      const parsed = JSON.parse(content);

      // Validate against schema
      expect(() => StateSourcesSchema.parse(parsed)).not.toThrow();

      // Verify state code matches filename
      expect(parsed.state).toBe(code);

      // Verify required fields
      expect(parsed.state_name).toBeTruthy();
      expect(parsed.tax_sources.length).toBeGreaterThanOrEqual(1);
      expect(parsed.formation_sources.length).toBeGreaterThanOrEqual(1);
      // Schema validation ensures last_validated is a valid datetime string

      // Verify source entries have required fields
      for (const source of [...parsed.tax_sources, ...parsed.formation_sources]) {
        expect(source.name).toBeTruthy();
        expect(source.url).toMatch(/^https?:\/\//);
        expect(["sos", "dor", "tax_foundation", "aggregator", "official"]).toContain(source.type);
        expect(["table_extract", "page_parse", "api", "manual"]).toContain(source.scrape_method);
      }
    }
  });
});
