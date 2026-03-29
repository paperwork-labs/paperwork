/**
 * Shared Playwright helpers for Filing Engine portal (Tier 2) automation.
 */

export {
  checkCheckbox,
  clickButton,
  fillTextField,
  selectDropdown,
  waitForNavigation,
} from "./form-fill.js";
export type { ScreenshotResult } from "./screenshot.js";
export { captureFullPage, captureStep } from "./screenshot.js";
export { sleep, withRetry } from "./retry.js";
export type { RetryOptions } from "./retry.js";
export { buildSelector, resolveSelector } from "./selectors.js";
export type {
  ResolveSelectorOptions,
  SelectorConfig,
  SelectorStrategy,
} from "./selectors.js";
