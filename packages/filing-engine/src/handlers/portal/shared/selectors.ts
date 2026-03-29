/**
 * Multi-strategy selector resolution for state portals with inconsistent markup.
 */

import type { Locator, Page } from "playwright";

export type SelectorStrategy = "css" | "xpath" | "text" | "aria" | "testid";

export interface SelectorConfig {
  css?: string;
  xpath?: string;
  text?: string;
  aria?: string;
  testid?: string;
}

/** Order: most stable / explicit first. */
const STRATEGY_ORDER: SelectorStrategy[] = [
  "testid",
  "aria",
  "css",
  "text",
  "xpath",
];

function escapeForDoubleQuotedAttr(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function configKeyForStrategy(s: SelectorStrategy): keyof SelectorConfig {
  return s;
}

function locatorForStrategy(page: Page, strategy: SelectorStrategy, raw: string): Locator {
  switch (strategy) {
    case "testid":
      return page.getByTestId(raw);
    case "aria":
      return page.locator(`[aria-label="${escapeForDoubleQuotedAttr(raw)}"]`);
    case "css":
      return page.locator(raw);
    case "text":
      return page.getByText(raw, { exact: true });
    case "xpath":
      return page.locator(`xpath=${raw}`);
    default: {
      const _exhaustive: never = strategy;
      throw new Error(`locatorForStrategy: unknown strategy ${_exhaustive}`);
    }
  }
}

/**
 * Returns a Playwright locator string for the first defined strategy (same priority as resolveSelector).
 * Useful for logs; prefer resolveSelector for interaction.
 */
export function buildSelector(strategies: SelectorConfig): string {
  const defined = STRATEGY_ORDER.map((s) => ({
    strategy: s,
    value: strategies[configKeyForStrategy(s)],
  })).find((x): x is { strategy: SelectorStrategy; value: string } => Boolean(x.value));

  if (!defined) {
    throw new Error(
      "buildSelector: SelectorConfig must define at least one of testid, aria, css, text, xpath"
    );
  }

  const { strategy, value } = defined;

  switch (strategy) {
    case "testid":
      return `[data-testid="${escapeForDoubleQuotedAttr(value)}"]`;
    case "aria":
      return `[aria-label="${escapeForDoubleQuotedAttr(value)}"]`;
    case "css":
      return value;
    case "text":
      return `text=${JSON.stringify(value)}`;
    case "xpath":
      return `xpath=${value}`;
    default: {
      const _exhaustive: never = strategy;
      throw new Error(`buildSelector: unknown strategy ${_exhaustive}`);
    }
  }
}

export interface ResolveSelectorOptions {
  /** Timeout per strategy when waiting for a match (ms). */
  timeoutPerStrategyMs?: number;
}

/**
 * Resolves the first matching strategy to a visible locator.
 * Tries strategies in order: testid → aria → css → text → xpath.
 */
export async function resolveSelector(
  page: Page,
  config: SelectorConfig,
  resolveOptions?: ResolveSelectorOptions
): Promise<Locator> {
  const timeoutMs = resolveOptions?.timeoutPerStrategyMs ?? 15_000;
  const errors: string[] = [];

  for (const strategy of STRATEGY_ORDER) {
    const raw = config[configKeyForStrategy(strategy)];
    if (raw === undefined || raw === "") {
      continue;
    }

    const locator = locatorForStrategy(page, strategy, raw).first();

    try {
      await locator.waitFor({ state: "visible", timeout: timeoutMs });
      return locator;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      errors.push(`${strategy}: ${msg}`);
    }
  }

  throw new Error(
    `resolveSelector: no strategy produced a visible element within ${timeoutMs}ms. ` +
      `Config: ${JSON.stringify(config)}. Attempts: ${errors.join(" | ")}`
  );
}
