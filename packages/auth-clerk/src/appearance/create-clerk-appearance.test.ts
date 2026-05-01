import { describe, expect, it } from "vitest";

import { createClerkAppearance } from "./create-clerk-appearance";

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
