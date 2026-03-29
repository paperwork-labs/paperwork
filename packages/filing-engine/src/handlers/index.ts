/**
 * Filing Handlers
 *
 * Three-tier architecture:
 * - Tier 1 (API): Direct state API integration (Delaware ICIS)
 * - Tier 2 (Portal): Playwright browser automation (~45 states)
 * - Tier 3 (Mail): Print-and-mail for ~2-3 states without online filing
 */

export * from "./portal/base.js";
