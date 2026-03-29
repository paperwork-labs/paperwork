// @vitest-environment node
/**
 * PDF generation uses @react-pdf/renderer `renderToBuffer` (Node) as the authoritative
 * “renders without errors” check.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createElement, type ComponentType } from "react";
import { describe, it, expect, expectTypeOf } from "vitest";
import { renderToBuffer } from "@react-pdf/renderer";

import * as CAM from "../ca-articles";
import * as TXM from "../tx-articles";
import * as FLM from "../fl-articles";
import * as DEM from "../de-articles";
import * as WYM from "../wy-articles";
import * as NYM from "../ny-articles";
import * as NVM from "../nv-articles";
import * as ILM from "../il-articles";
import * as GAM from "../ga-articles";
import * as WAM from "../wa-articles";

import type { CAArticlesProps } from "../ca-articles";
import type { TXArticlesProps } from "../tx-articles";
import type { FLArticlesProps } from "../fl-articles";
import type { DEArticlesProps } from "../de-articles";
import type { WYArticlesProps } from "../wy-articles";
import type { NYArticlesProps } from "../ny-articles";
import type { NVArticlesProps, NVManager } from "../nv-articles";
import type { ILArticlesProps } from "../il-articles";
import type { GAArticlesProps } from "../ga-articles";
import type { WAArticlesProps } from "../wa-articles";

import {
  mockCAArticlesProps,
  mockTXArticlesProps,
  mockFLArticlesProps,
  mockDEArticlesProps,
  mockWYArticlesProps,
  mockNYArticlesProps,
  mockNVArticlesProps,
  mockILArticlesProps,
  mockGAArticlesProps,
  mockWAArticlesProps,
} from "./fixtures";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Keys that TypeScript treats as required (non-optional) on T */
type RequiredKeysOf<T> = {
  [K in keyof T]-?: {} extends Pick<T, K> ? never : K;
}[keyof T];

function readTemplateSource(fileName: string): string {
  return readFileSync(path.join(__dirname, "..", fileName), "utf-8");
}

function assertFixtureCoversRequiredKeys(
  obj: Record<string, unknown>,
  keys: readonly string[],
  state: string
): void {
  for (const k of keys) {
    expect(obj, `${state}: fixture must include ${k}`).toHaveProperty(k);
    const v = obj[k];
    expect(v, `${state}: ${k} must be defined`).toBeDefined();
    if (k === "managers" && Array.isArray(v)) {
      expect(v.length, `${state}: managers must be non-empty`).toBeGreaterThan(0);
    } else if (typeof v === "string") {
      expect(v.trim().length, `${state}: ${k} must be non-empty string`).toBeGreaterThan(0);
    } else if (typeof v === "object" && v !== null && !Array.isArray(v)) {
      expect(Object.keys(v).length, `${state}: ${k} object must have keys`).toBeGreaterThan(0);
    }
  }
}

type TemplateModule = {
  default: ComponentType<Record<string, unknown>>;
  [key: string]: unknown;
};

interface StateTemplateEntry {
  state: string;
  fileName: string;
  module: TemplateModule;
  namedExport: string;
  fixture: Record<string, unknown>;
  requiredKeys: readonly string[];
  feeUsd: number;
  feeRegex: RegExp;
  statuteNeedles: readonly string[];
}

const STATE_TEMPLATES: readonly StateTemplateEntry[] = [
  {
    state: "CA",
    fileName: "ca-articles.tsx",
    module: CAM as unknown as TemplateModule,
    namedExport: "CAArticlesOfOrganization",
    fixture: mockCAArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: [
      "llcName",
      "purpose",
      "registeredAgent",
      "principalAddress",
      "organizer",
    ],
    feeUsd: 70,
    feeRegex: /\$70\b/,
    statuteNeedles: ["California Corporations Code"],
  },
  {
    state: "TX",
    fileName: "tx-articles.tsx",
    module: TXM as unknown as TemplateModule,
    namedExport: "TXArticlesOfOrganization",
    fixture: mockTXArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "purpose", "registeredAgent", "organizer"],
    feeUsd: 300,
    feeRegex: /\$300\b/,
    statuteNeedles: ["Texas Business Organizations Code"],
  },
  {
    state: "FL",
    fileName: "fl-articles.tsx",
    module: FLM as unknown as TemplateModule,
    namedExport: "FLArticlesOfOrganization",
    fixture: mockFLArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "principalAddress", "registeredAgent", "organizer"],
    feeUsd: 125,
    feeRegex: /\$125\b/,
    statuteNeedles: ["Florida Statutes", "605.0201"],
  },
  {
    state: "DE",
    fileName: "de-articles.tsx",
    module: DEM as unknown as TemplateModule,
    namedExport: "DEArticlesOfOrganization",
    fixture: mockDEArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "registeredAgent", "organizer"],
    feeUsd: 90,
    feeRegex: /\$90\b/,
    statuteNeedles: ["Delaware", "18-201"],
  },
  {
    state: "WY",
    fileName: "wy-articles.tsx",
    module: WYM as unknown as TemplateModule,
    namedExport: "WYArticlesOfOrganization",
    fixture: mockWYArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "registeredAgent", "organizer"],
    feeUsd: 100,
    feeRegex: /\$100\b/,
    statuteNeedles: ["Wyo. Stat", "17-29-201"],
  },
  {
    state: "NY",
    fileName: "ny-articles.tsx",
    module: NYM as unknown as TemplateModule,
    namedExport: "NYArticlesOfOrganization",
    fixture: mockNYArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "countyOfOffice", "registeredAgent", "organizer"],
    feeUsd: 200,
    feeRegex: /\$200\b/,
    statuteNeedles: ["New York", "203", "LLC"],
  },
  {
    state: "NV",
    fileName: "nv-articles.tsx",
    module: NVM as unknown as TemplateModule,
    namedExport: "NVArticlesOfOrganization",
    fixture: mockNVArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "registeredAgent", "managers", "organizer"],
    feeUsd: 425,
    feeRegex: /\$425\b/,
    statuteNeedles: ["NRS", "86"],
  },
  {
    state: "IL",
    fileName: "il-articles.tsx",
    module: ILM as unknown as TemplateModule,
    namedExport: "ILArticlesOfOrganization",
    fixture: mockILArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "principalAddress", "registeredAgent", "organizer"],
    feeUsd: 150,
    feeRegex: /\$150\b/,
    statuteNeedles: ["805 ILCS", "180/5-5"],
  },
  {
    state: "GA",
    fileName: "ga-articles.tsx",
    module: GAM as unknown as TemplateModule,
    namedExport: "GAArticlesOfOrganization",
    fixture: mockGAArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "principalAddress", "registeredAgent", "organizer"],
    feeUsd: 100,
    feeRegex: /\$100\b/,
    statuteNeedles: ["O.C.G.A.", "14-11-203"],
  },
  {
    state: "WA",
    fileName: "wa-articles.tsx",
    module: WAM as unknown as TemplateModule,
    namedExport: "WAArticlesOfOrganization",
    fixture: mockWAArticlesProps as unknown as Record<string, unknown>,
    requiredKeys: ["llcName", "officialEmail", "registeredAgent", "organizer"],
    feeUsd: 180,
    feeRegex: /\$180\b/,
    statuteNeedles: ["RCW 25.15.071"],
  },
] as const;

describe("PDF template validation", () => {
  describe.each(STATE_TEMPLATES)("$state template", (entry) => {
    it("exports named component function", () => {
      const named = entry.module[entry.namedExport];
      expect(named, `missing ${entry.namedExport}`).toBeDefined();
      expect(typeof named).toBe("function");
    });

    it("exports default component same as named export", () => {
      const named = entry.module[entry.namedExport];
      expect(entry.module.default).toBe(named);
    });

    it("lists official filing fee in source (SOS-aligned amount)", () => {
      const src = readTemplateSource(entry.fileName);
      expect(src, `fee $${entry.feeUsd}`).toMatch(entry.feeRegex);
    });

    it("references correct state statute / law in source", () => {
      const src = readTemplateSource(entry.fileName);
      for (const needle of entry.statuteNeedles) {
        expect(src, `expected statute fragment: ${needle}`).toContain(needle);
      }
    });

    it("fixture supplies every TypeScript-required prop", () => {
      assertFixtureCoversRequiredKeys(entry.fixture, entry.requiredKeys, entry.state);
    });

    it("renders PDF to buffer without throwing", async () => {
      const Named = entry.module[entry.namedExport] as ComponentType<
        Record<string, unknown>
      >;
      const element = createElement(Named, entry.fixture);
      const buffer = await renderToBuffer(element);
      expect(Buffer.isBuffer(buffer)).toBe(true);
      expect(buffer.length).toBeGreaterThan(500);
    });
  });
});

describe("Props interfaces — exported types", () => {
  it("CA exports CAArticlesProps", () => {
    expectTypeOf<CAArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<CAArticlesProps>>().toEqualTypeOf<
      | "llcName"
      | "purpose"
      | "registeredAgent"
      | "principalAddress"
      | "organizer"
    >();
  });

  it("TX exports TXArticlesProps", () => {
    expectTypeOf<TXArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<TXArticlesProps>>().toEqualTypeOf<
      "llcName" | "purpose" | "registeredAgent" | "organizer"
    >();
  });

  it("FL exports FLArticlesProps", () => {
    expectTypeOf<FLArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<FLArticlesProps>>().toEqualTypeOf<
      "llcName" | "principalAddress" | "registeredAgent" | "organizer"
    >();
  });

  it("DE exports DEArticlesProps", () => {
    expectTypeOf<DEArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<DEArticlesProps>>().toEqualTypeOf<
      "llcName" | "registeredAgent" | "organizer"
    >();
  });

  it("WY exports WYArticlesProps", () => {
    expectTypeOf<WYArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<WYArticlesProps>>().toEqualTypeOf<
      "llcName" | "registeredAgent" | "organizer"
    >();
  });

  it("NY exports NYArticlesProps", () => {
    expectTypeOf<NYArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<NYArticlesProps>>().toEqualTypeOf<
      "llcName" | "countyOfOffice" | "registeredAgent" | "organizer"
    >();
  });

  it("NV exports NVArticlesProps and NVManager", () => {
    expectTypeOf<NVArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<NVArticlesProps>>().toEqualTypeOf<
      "llcName" | "registeredAgent" | "managers" | "organizer"
    >();
    expectTypeOf<NVManager>().toBeObject();
    expectTypeOf<RequiredKeysOf<NVManager>>().toEqualTypeOf<"name">();
  });

  it("IL exports ILArticlesProps", () => {
    expectTypeOf<ILArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<ILArticlesProps>>().toEqualTypeOf<
      "llcName" | "principalAddress" | "registeredAgent" | "organizer"
    >();
  });

  it("GA exports GAArticlesProps", () => {
    expectTypeOf<GAArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<GAArticlesProps>>().toEqualTypeOf<
      "llcName" | "principalAddress" | "registeredAgent" | "organizer"
    >();
  });

  it("WA exports WAArticlesProps", () => {
    expectTypeOf<WAArticlesProps>().toBeObject();
    expectTypeOf<RequiredKeysOf<WAArticlesProps>>().toEqualTypeOf<
      "llcName" | "officialEmail" | "registeredAgent" | "organizer"
    >();
  });
});

describe("Required props — compile-time rejects incomplete objects", () => {
  it("CA: omitting organizer is a type error", () => {
    type Bad = Omit<CAArticlesProps, "organizer">;
    expectTypeOf<Bad>().not.toMatchTypeOf<CAArticlesProps>();
  });

  it("TX: omitting purpose is a type error", () => {
    type Bad = Omit<TXArticlesProps, "purpose">;
    expectTypeOf<Bad>().not.toMatchTypeOf<TXArticlesProps>();
  });

  it("NY: omitting countyOfOffice is a type error", () => {
    type Bad = Omit<NYArticlesProps, "countyOfOffice">;
    expectTypeOf<Bad>().not.toMatchTypeOf<NYArticlesProps>();
  });

  it("NV: omitting managers is a type error", () => {
    type Bad = Omit<NVArticlesProps, "managers">;
    expectTypeOf<Bad>().not.toMatchTypeOf<NVArticlesProps>();
  });

  it("WA: omitting officialEmail is a type error", () => {
    type Bad = Omit<WAArticlesProps, "officialEmail">;
    expectTypeOf<Bad>().not.toMatchTypeOf<WAArticlesProps>();
  });
});
