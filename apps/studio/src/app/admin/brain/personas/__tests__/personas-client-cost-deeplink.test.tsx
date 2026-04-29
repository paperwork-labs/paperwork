import { Suspense } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonasPageClient } from "../personas-client";
import type { PersonasPageInitial } from "../personas-types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/admin/brain/personas",
  useSearchParams: () => new URLSearchParams("tab=cost"),
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="mock-chart">{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

function minimalInitial(over: Partial<PersonasPageInitial> = {}): PersonasPageInitial {
  return {
    brainConfigured: true,
    personas: [],
    cost7d: { window: "7d", personas: [], has_file: false },
    cost30d: { window: "30d", personas: [], has_file: false },
    routing: {
      derived_from_code: true,
      edit_path: "apis/brain/app/personas/routing.py",
      tag_to_persona: {},
      content_keyword_to_persona: {},
      default_persona: "ea",
    },
    activity: { events: [], has_file: false },
    modelRegistryMarkdown: "# R",
    modelRegistryLastReviewed: null,
    ...over,
  };
}

afterEach(() => {
  cleanup();
});

describe("Brain personas cost tab (deep link)", () => {
  it("shows cost empty state when no cost file", async () => {
    render(
      <Suspense fallback={null}>
        <PersonasPageClient initial={minimalInitial()} />
      </Suspense>,
    );
    expect(await screen.findByTestId("cost-empty-state", {}, { timeout: 5000 })).toBeTruthy();
  });
});
