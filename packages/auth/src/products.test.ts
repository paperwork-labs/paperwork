import { describe, expect, it } from "vitest";

import {
  PAPERWORK_PRODUCTS,
  formatSiblingExplainer,
  getSiblingProducts,
} from "./products";

describe("products registry", () => {
  it("includes all five customer-facing products", () => {
    const slugs = PAPERWORK_PRODUCTS.map((p) => p.slug);
    expect(slugs).toEqual([
      "filefree",
      "launchfree",
      "distill",
      "axiomfolio",
      "trinkets",
    ]);
  });

  it("excludes the current app from sibling products", () => {
    const siblings = getSiblingProducts("filefree");
    expect(siblings.map((p) => p.slug)).not.toContain("filefree");
    expect(siblings).toHaveLength(4);
  });

  it("returns all products when no current slug is provided", () => {
    expect(getSiblingProducts()).toHaveLength(PAPERWORK_PRODUCTS.length);
  });

  it("matches case-insensitively on slug", () => {
    expect(getSiblingProducts("FileFree").map((p) => p.slug)).not.toContain(
      "filefree",
    );
  });

  it("formats the explainer with Oxford comma + 'and'", () => {
    const text = formatSiblingExplainer("filefree");
    expect(text).toBe(
      "Your Paperwork ID also works on LaunchFree, Distill, AxiomFolio, and Trinkets.",
    );
  });

  it("includes all 5 products + Oxford comma when slug doesn't match any", () => {
    const text = formatSiblingExplainer("nonexistent-slug");
    expect(text).toBe(
      "Your Paperwork ID also works on FileFree, LaunchFree, Distill, AxiomFolio, and Trinkets.",
    );
  });
});
