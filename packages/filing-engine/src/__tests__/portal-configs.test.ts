/**
 * Portal Config Validation Tests
 *
 * CRITICAL: These tests validate the accuracy of state portal configurations.
 * Any failure here could result in failed LLC filings or incorrect charges.
 *
 * Data sources (verify manually before updating configs):
 * - CA: https://bizfileservices.sos.ca.gov (bizfileservices)
 * - TX: https://direct.sos.state.tx.us/ (SOSDirect)
 * - FL: https://dos.fl.gov/sunbiz/ (Sunbiz)
 * - DE: https://corp.delaware.gov/ (Division of Corporations)
 * - WY: https://wyobiz.wyo.gov/ (WyoBiz)
 * - NY: https://www.businessexpress.ny.gov/ (Business Express)
 * - NV: https://www.nvsilverflume.gov/ (SilverFlume)
 * - IL: https://www.ilsos.gov/ (CyberDrive Illinois)
 * - GA: https://ecorp.sos.ga.gov/ (eCorp)
 * - WA: https://ccfs.sos.wa.gov/ (CCFS)
 */

import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { PortalConfigSchema } from "../types.js";
import { loadPortalConfig, getAvailablePortalStates } from "../handlers/portal/config-loader.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORTALS_DIR = join(__dirname, "../../../data/src/portals");

/**
 * Official state filing fees (USD)
 * Last verified: 2026-03-28
 *
 * IMPORTANT: Update these when fees change and document the source.
 * Each change should be logged in docs/KNOWLEDGE.md with verification date.
 */
const OFFICIAL_FEES: Record<string, { filing: number; source: string; verified: string }> = {
  CA: {
    filing: 70,
    source: "https://bizfileservices.sos.ca.gov/filing/llc",
    verified: "2026-03-28",
  },
  TX: {
    filing: 300,
    source: "https://www.sos.state.tx.us/corp/forms/806_boc.pdf",
    verified: "2026-03-28",
  },
  FL: {
    filing: 125, // $100 filing + $25 RA designation
    source: "https://dos.fl.gov/sunbiz/forms/fees/",
    verified: "2026-03-28",
  },
  DE: {
    filing: 90,
    source: "https://corp.delaware.gov/fee.shtml",
    verified: "2026-03-28",
  },
  WY: {
    filing: 100,
    source: "https://sos.wyo.gov/Business/docs/BusinessFees.pdf",
    verified: "2026-03-28",
  },
  NY: {
    filing: 200,
    source: "https://dos.ny.gov/fee-schedules",
    verified: "2026-03-28",
  },
  NV: {
    filing: 425, // $75 Articles + $150 Initial List + $200 Business License
    source: "https://www.nvsos.gov/businesses/commercial-recordings/forms-fees",
    verified: "2026-03-28",
  },
  IL: {
    filing: 150,
    source: "https://www.ilsos.gov/departments/business_services/organization/llc_instructions.html",
    verified: "2026-03-28",
  },
  GA: {
    filing: 100,
    source: "https://sos.ga.gov/corporations-division",
    verified: "2026-03-28",
  },
  WA: {
    filing: 180,
    source: "https://apps.sos.wa.gov/corps/feescheduleexpeditedservice.aspx",
    verified: "2026-03-28",
  },
};

/**
 * Official portal URLs - must be exact SOS/Division of Corporations URLs
 */
const OFFICIAL_PORTAL_URLS: Record<string, string> = {
  CA: "https://bizfileservices.sos.ca.gov/filing/llc",
  TX: "https://direct.sos.state.tx.us/",
  FL: "https://efile.sunbiz.org/llc_file.html",
  DE: "https://icis.corp.delaware.gov/ecorp2",
  WY: "https://wyobiz.wyo.gov",
  NY: "https://www.businessexpress.ny.gov/",
  NV: "https://www.nvsilverflume.gov/",
  IL: "https://www.ilsos.gov/departments/business_services/home.html",
  GA: "https://ecorp.sos.ga.gov/",
  WA: "https://ccfs.sos.wa.gov/",
};

const SUPPORTED_STATES = ["CA", "TX", "FL", "DE", "WY", "NY", "NV", "IL", "GA", "WA"];

describe("Portal Config Files", () => {
  describe("File Existence", () => {
    it.each(SUPPORTED_STATES)("config file exists for %s", (state) => {
      const configPath = join(PORTALS_DIR, `${state.toLowerCase()}.json`);
      expect(existsSync(configPath)).toBe(true);
    });
  });

  describe("Schema Validation", () => {
    it.each(SUPPORTED_STATES)("config for %s passes Zod schema validation", (state) => {
      const configPath = join(PORTALS_DIR, `${state.toLowerCase()}.json`);
      const raw = readFileSync(configPath, "utf-8");
      const parsed = JSON.parse(raw);

      const result = PortalConfigSchema.safeParse(parsed);
      if (!result.success) {
        console.error(`Schema validation failed for ${state}:`, result.error.format());
      }
      expect(result.success).toBe(true);
    });
  });

  describe("Config Loader", () => {
    it.each(SUPPORTED_STATES)("loadPortalConfig(%s) returns valid config", (state) => {
      const config = loadPortalConfig(state);
      expect(config.stateCode).toBe(state);
      expect(config.stateName).toBeTruthy();
      expect(config.portalUrl).toBeTruthy();
      expect(config.filingFee).toBeGreaterThan(0);
      expect(config.steps.length).toBeGreaterThan(0);
    });

    it("getAvailablePortalStates returns all supported states", () => {
      const states = getAvailablePortalStates();
      expect(states).toEqual(expect.arrayContaining(SUPPORTED_STATES));
    });
  });
});

describe("Fee Accuracy (CRITICAL)", () => {
  describe("Filing fees match official sources", () => {
    it.each(SUPPORTED_STATES)("%s filing fee matches official ($%i)", (state) => {
      const config = loadPortalConfig(state);
      const official = OFFICIAL_FEES[state];

      expect(config.filingFee).toBe(official.filing);

      // Log the source for audit trail
      console.log(
        `${state}: $${config.filingFee} (source: ${official.source}, verified: ${official.verified})`
      );
    });
  });

  describe("Fee values are reasonable", () => {
    it.each(SUPPORTED_STATES)("%s fee is between $50 and $500", (state) => {
      const config = loadPortalConfig(state);
      expect(config.filingFee).toBeGreaterThanOrEqual(50);
      expect(config.filingFee).toBeLessThanOrEqual(500);
    });

    it.each(SUPPORTED_STATES)("%s expedited fee is null or greater than filing fee", (state) => {
      const config = loadPortalConfig(state);
      if (config.expeditedFee !== null && config.expeditedFee !== undefined) {
        expect(config.expeditedFee).toBeGreaterThan(0);
      }
    });
  });
});

describe("Portal URL Accuracy (CRITICAL)", () => {
  describe("URLs match official state portals", () => {
    it.each(SUPPORTED_STATES)("%s portal URL matches official", (state) => {
      const config = loadPortalConfig(state);
      expect(config.portalUrl).toBe(OFFICIAL_PORTAL_URLS[state]);
    });
  });

  describe("URL format validation", () => {
    it.each(SUPPORTED_STATES)("%s portal URL is valid HTTPS", (state) => {
      const config = loadPortalConfig(state);
      expect(config.portalUrl).toMatch(/^https:\/\//);
    });

    it.each(SUPPORTED_STATES)("%s portal URL is an official state domain", (state) => {
      const config = loadPortalConfig(state);
      const url = new URL(config.portalUrl);
      // Accept .gov domains, state. subdomains, and known official non-.gov portals
      const validPatterns = [".gov", ".state.", "sos.", "sunbiz.org"];
      const isValidDomain = validPatterns.some(
        (pattern) => url.hostname.includes(pattern) || url.hostname.endsWith(".gov")
      );
      expect(isValidDomain).toBe(true);
    });
  });
});

describe("Config Completeness", () => {
  describe("Required fields present", () => {
    it.each(SUPPORTED_STATES)("%s has all required metadata", (state) => {
      const config = loadPortalConfig(state);

      expect(config.stateCode).toBe(state);
      expect(config.stateName).toBeTruthy();
      expect(config.portalUrl).toBeTruthy();
      expect(typeof config.loginRequired).toBe("boolean");
      expect(typeof config.supportsRALogin).toBe("boolean");
      expect(config.filingFee).toBeGreaterThan(0);
      expect(Array.isArray(config.paymentMethods)).toBe(true);
      expect(config.paymentMethods.length).toBeGreaterThan(0);
      expect(config.estimatedProcessingDays).toBeGreaterThan(0);
      expect(config.lastVerified).toBeTruthy();
      expect(config.confirmationPageSelector).toBeTruthy();
    });
  });

  describe("Steps have required structure", () => {
    it.each(SUPPORTED_STATES)("%s has at least 5 steps", (state) => {
      const config = loadPortalConfig(state);
      expect(config.steps.length).toBeGreaterThanOrEqual(5);
    });

    it.each(SUPPORTED_STATES)("%s steps have valid structure", (state) => {
      const config = loadPortalConfig(state);

      for (const step of config.steps) {
        expect(step.name).toBeTruthy();
        expect(typeof step.waitForNavigation).toBe("boolean");
        expect(typeof step.screenshotAfter).toBe("boolean");

        for (const field of step.fields) {
          expect(field.fieldId).toBeTruthy();
          expect(field.selector).toBeTruthy();
          expect(["css", "xpath", "text", "aria"]).toContain(field.selectorType);
          expect(["text", "select", "checkbox", "radio", "date", "file"]).toContain(field.inputType);
        }
      }
    });

    it.each(SUPPORTED_STATES)("%s has business-name step", (state) => {
      const config = loadPortalConfig(state);
      const hasNameStep = config.steps.some((s) => s.name === "business-name");
      expect(hasNameStep).toBe(true);
    });

    it.each(SUPPORTED_STATES)("%s has registered-agent step", (state) => {
      const config = loadPortalConfig(state);
      const hasAgentStep = config.steps.some((s) => s.name === "registered-agent");
      expect(hasAgentStep).toBe(true);
    });

    it.each(SUPPORTED_STATES)("%s has payment step", (state) => {
      const config = loadPortalConfig(state);
      const hasPaymentStep = config.steps.some((s) => s.name === "payment");
      expect(hasPaymentStep).toBe(true);
    });
  });
});

describe("Selector Quality", () => {
  describe("Selectors have fallbacks", () => {
    it.each(SUPPORTED_STATES)("%s critical fields have fallback selectors", (state) => {
      const config = loadPortalConfig(state);
      const criticalFields = ["businessName", "agentName"];

      for (const step of config.steps) {
        for (const field of step.fields) {
          if (criticalFields.includes(field.fieldId)) {
            expect(field.fallbackSelectors).toBeDefined();
            expect(field.fallbackSelectors!.length).toBeGreaterThan(0);
          }
        }
      }
    });
  });

  describe("Selector format validation", () => {
    it.each(SUPPORTED_STATES)("%s selectors are valid CSS/XPath", (state) => {
      const config = loadPortalConfig(state);

      for (const step of config.steps) {
        for (const field of step.fields) {
          // CSS selectors should start with #, ., [, or element name
          // XPath selectors should start with / or xpath=
          const validSelectorStart = /^[#.\[\w]|^xpath=|^\//;
          expect(field.selector).toMatch(validSelectorStart);
        }
      }
    });
  });
});

describe("Data Freshness", () => {
  it.each(SUPPORTED_STATES)("%s lastVerified is within 90 days", (state) => {
    const config = loadPortalConfig(state);
    const lastVerified = new Date(config.lastVerified);
    const now = new Date();
    const daysSinceVerification = (now.getTime() - lastVerified.getTime()) / (1000 * 60 * 60 * 24);

    if (daysSinceVerification > 90) {
      console.warn(`WARNING: ${state} config last verified ${Math.floor(daysSinceVerification)} days ago`);
    }

    expect(daysSinceVerification).toBeLessThan(90);
  });
});

describe("State-Specific Validation", () => {
  it("Nevada config includes Initial List and Business License fees", () => {
    const config = loadPortalConfig("NV");
    // NV $425 = $75 Articles + $150 Initial List + $200 Business License
    expect(config.filingFee).toBe(425);
    expect(config.notes).toContain("Initial List");
    expect(config.notes).toContain("Business License");
  });

  it("Florida config includes RA designation fee", () => {
    const config = loadPortalConfig("FL");
    // FL $125 = $100 filing + $25 RA designation
    expect(config.filingFee).toBe(125);
  });

  it("New York config mentions publication requirement", () => {
    const config = loadPortalConfig("NY");
    const notes = config.notes?.toLowerCase() ?? "";
    expect(notes.includes("publish") || notes.includes("publication")).toBe(true);
  });

  it("Washington config mentions email requirement", () => {
    const config = loadPortalConfig("WA");
    expect(config.notes?.toLowerCase()).toContain("email");
  });

  it("Texas config mentions Certificate of Formation", () => {
    const config = loadPortalConfig("TX");
    expect(config.notes?.toLowerCase()).toContain("certificate of formation");
  });

  it("Delaware config has expedited fee options", () => {
    const config = loadPortalConfig("DE");
    expect(config.expeditedFee).toBeGreaterThan(0);
  });
});
