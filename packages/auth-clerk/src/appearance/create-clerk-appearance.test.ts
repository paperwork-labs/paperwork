import { describe, expect, it } from "vitest";

import { createClerkAppearance } from "./create-clerk-appearance";
import {
  accountsAppearance,
  axiomfolioAppearance,
  distillAppearance,
  fileFreeAppearance,
  launchFreeAppearance,
  studioAppearance,
  trinketsAppearance,
} from "./presets";

const SKY = "hsl(199 89% 48%)";

const V7_KEYS = [
  "colorPrimary",
  "colorBackground",
  "colorInput",
  "colorForeground",
  "colorInputForeground",
  "colorMutedForeground",
  "colorPrimaryForeground",
  "colorDanger",
  "colorRing",
  "borderRadius",
  "fontFamily",
] as const;

function assertNoDeprecatedClerkVars(variables: Record<string, unknown>) {
  expect(variables.colorText).toBeUndefined();
  expect(variables.colorInputBackground).toBeUndefined();
}

function assertV7Shape(variables: Record<string, unknown>) {
  for (const key of V7_KEYS) {
    expect(variables[key], `missing ${key}`).toBeDefined();
    expect(typeof variables[key]).toBe("string");
  }
  assertNoDeprecatedClerkVars(variables);
}

describe("named appearance presets (Clerk v7 variables + brand colors)", () => {
  it.each([
    ["accountsAppearance", accountsAppearance, { colorPrimary: SKY, colorRing: SKY }],
    ["fileFreeAppearance", fileFreeAppearance, { colorPrimary: "hsl(var(--primary))", colorRing: SKY }],
    ["launchFreeAppearance", launchFreeAppearance, { colorPrimary: "hsl(var(--primary))", colorRing: SKY }],
    ["distillAppearance", distillAppearance, { colorPrimary: "#0F766E", colorRing: SKY }],
    ["studioAppearance", studioAppearance, { colorPrimary: "hsl(var(--primary))", colorRing: SKY }],
    ["trinketsAppearance", trinketsAppearance, { colorPrimary: "#6366F1", colorRing: SKY }],
    ["axiomfolioAppearance", axiomfolioAppearance, { colorPrimary: "var(--primary)", colorRing: SKY }],
  ] as const)("preset %s uses v7 vars and expected primary/ring", (_name, appearance, expected) => {
    const variables = appearance.variables as Record<string, unknown>;
    assertV7Shape(variables);
    expect(variables.colorPrimary).toBe(expected.colorPrimary);
    expect(variables.colorRing).toBe(expected.colorRing);
  });

  it("accounts preset uses Paperwork sky primary (not slate gray)", () => {
    const v = accountsAppearance.variables as Record<string, string>;
    expect(v.colorPrimary).toBe(SKY);
    expect(v.colorAccent).toBe("hsl(199 89% 60%)");
  });

  it("distill preset keeps teal + amber brand (accent)", () => {
    const v = distillAppearance.variables as Record<string, string>;
    expect(v.colorAccent).toBe("#C2410C");
  });

  it("axiomfolio preset threads theme CSS variables for surfaces", () => {
    const v = axiomfolioAppearance.variables as Record<string, string>;
    expect(v.colorBackground).toBe("var(--background)");
    expect(v.colorForeground).toBe("var(--foreground)");
    expect(v.colorPrimaryForeground).toBe("var(--primary-foreground)");
    expect(v.colorNeutral).toBe("var(--muted-foreground)");
    expect(v.colorBorder).toBe("var(--border)");
  });
});

describe("createClerkAppearance", () => {
  it("hides the footer/badge slots by default (kills 'Secured by Clerk')", () => {
    const appearance = createClerkAppearance({ primary: "#000000" });
    const elements = appearance.elements as Record<string, string>;

    expect(elements.footer).toBe("hidden");
    expect(elements.footerAction).toBe("hidden");
    expect(elements.footerActionText).toBe("hidden");
    expect(elements.footerActionLink).toBe("hidden");
    expect(elements.badge).toBe("hidden");
    expect(elements.internal).toBe("hidden");
  });

  it("threads primary into colorPrimary", () => {
    const appearance = createClerkAppearance({ primary: "#0F766E" });
    const variables = appearance.variables as Record<string, string>;
    expect(variables.colorPrimary).toBe("#0F766E");
  });

  it("falls back to primary when accent is not provided", () => {
    const appearance = createClerkAppearance({ primary: "#6366F1" });
    const variables = appearance.variables as Record<string, string>;
    expect(variables.colorAccent).toBeUndefined();
  });

  it("emits colorAccent when accent differs from primary", () => {
    const appearance = createClerkAppearance({
      primary: "#6366F1",
      accent: "#38BDF8",
    });
    const variables = appearance.variables as Record<string, string>;
    expect(variables.colorAccent).toBe("#38BDF8");
  });

  it("respects elementOverrides (shallow merge)", () => {
    const appearance = createClerkAppearance({
      primary: "#000",
      elementOverrides: {
        identityPreview: "bg-test",
        userButtonAvatarBox: "h-test",
      },
    });
    const elements = appearance.elements as Record<string, string>;
    expect(elements.identityPreview).toBe("bg-test");
    expect(elements.userButtonAvatarBox).toBe("h-test");
    // unrelated default still present
    expect(elements.footer).toBe("hidden");
  });

  it("uses current Clerk variable names (not deprecated colorText / colorInputBackground)", () => {
    const appearance = createClerkAppearance({ primary: "#336699" });
    const variables = appearance.variables as Record<string, string>;
    expect(variables.colorForeground).toBe("hsl(var(--foreground))");
    expect(variables.colorInput).toBe("hsl(var(--input))");
    expect(variables.colorPrimaryForeground).toBe("hsl(var(--primary-foreground))");
    expect(variables.colorText).toBeUndefined();
    expect(variables.colorInputBackground).toBeUndefined();
  });

  it("sets colorRing from accent by default", () => {
    const appearance = createClerkAppearance({
      primary: "#336699",
      accent: "#ff00ff",
    });
    const variables = appearance.variables as Record<string, string>;
    expect(variables.colorRing).toBe("#ff00ff");
  });

  it("uses the dark base theme by default", () => {
    const appearance = createClerkAppearance({ primary: "#000" });
    expect(appearance.baseTheme).toBeDefined();
  });

  it("omits base theme when isDark is false", () => {
    const appearance = createClerkAppearance({ primary: "#000", isDark: false });
    expect(appearance.baseTheme).toBeUndefined();
  });
});
