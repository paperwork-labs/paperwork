/**
 * Playwright form helpers for portal automation.
 */

import type { Page } from "playwright";

function formatActionError(action: string, selector: string, cause: unknown): Error {
  const base = `${action} failed for selector ${JSON.stringify(selector)}`;
  if (cause instanceof Error) {
    const err = new Error(`${base}: ${cause.message}`);
    err.cause = cause;
    return err;
  }
  return new Error(`${base}: ${String(cause)}`);
}

export async function fillTextField(
  page: Page,
  selector: string,
  value: string,
  options?: { clear?: boolean }
): Promise<void> {
  const clear = options?.clear ?? true;

  try {
    const locator = page.locator(selector).first();
    await locator.waitFor({ state: "visible", timeout: 30_000 });
    if (clear) {
      await locator.clear();
    }
    await locator.fill(value, { timeout: 30_000 });
  } catch (cause) {
    throw formatActionError("fillTextField", selector, cause);
  }
}

export async function selectDropdown(
  page: Page,
  selector: string,
  value: string
): Promise<void> {
  try {
    const locator = page.locator(selector).first();
    await locator.waitFor({ state: "visible", timeout: 30_000 });
    await locator.selectOption(value, { timeout: 30_000 });
  } catch (cause) {
    throw formatActionError("selectDropdown", selector, cause);
  }
}

export async function checkCheckbox(
  page: Page,
  selector: string,
  checked: boolean = true
): Promise<void> {
  try {
    const locator = page.locator(selector).first();
    await locator.waitFor({ state: "attached", timeout: 30_000 });
    await locator.setChecked(checked, { timeout: 30_000 });
  } catch (cause) {
    throw formatActionError("checkCheckbox", selector, cause);
  }
}

export async function clickButton(page: Page, selector: string): Promise<void> {
  try {
    const locator = page.locator(selector).first();
    await locator.waitFor({ state: "visible", timeout: 30_000 });
    await locator.click({ timeout: 30_000 });
  } catch (cause) {
    throw formatActionError("clickButton", selector, cause);
  }
}

/**
 * Runs `action` in parallel with waiting for navigation (e.g. form submit).
 * Uses load by default for broad portal compatibility.
 */
export async function waitForNavigation(
  page: Page,
  action: () => Promise<void>
): Promise<void> {
  try {
    await Promise.all([
      page.waitForNavigation({ waitUntil: "load", timeout: 60_000 }),
      action(),
    ]);
  } catch (cause) {
    throw formatActionError("waitForNavigation", "(page navigation)", cause);
  }
}
