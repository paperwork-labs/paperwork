/**
 * Filing Handlers
 *
 * Three-tier architecture:
 * - Tier 1 (API): Direct state API integration (Delaware ICIS)
 * - Tier 2 (Portal): Playwright browser automation (~45 states)
 * - Tier 3 (Mail): Print-and-mail for ~2-3 states without online filing
 */

export * from "./portal/base.js";
export * from "./portal/config-loader.js";

export { CaliforniaPortalHandler } from "./portal/ca.js";
export { TexasPortalHandler } from "./portal/tx.js";
export { FloridaPortalHandler } from "./portal/fl.js";
export { DelawarePortalHandler } from "./portal/de.js";
export { WyomingPortalHandler } from "./portal/wy.js";
export { NewYorkPortalHandler } from "./portal/ny.js";
export { NevadaPortalHandler } from "./portal/nv.js";
export { IllinoisPortalHandler } from "./portal/il.js";
export { GeorgiaPortalHandler } from "./portal/ga.js";
export { WashingtonPortalHandler } from "./portal/wa.js";

import { CaliforniaPortalHandler } from "./portal/ca.js";
import { TexasPortalHandler } from "./portal/tx.js";
import { FloridaPortalHandler } from "./portal/fl.js";
import { DelawarePortalHandler } from "./portal/de.js";
import { WyomingPortalHandler } from "./portal/wy.js";
import { NewYorkPortalHandler } from "./portal/ny.js";
import { NevadaPortalHandler } from "./portal/nv.js";
import { IllinoisPortalHandler } from "./portal/il.js";
import { GeorgiaPortalHandler } from "./portal/ga.js";
import { WashingtonPortalHandler } from "./portal/wa.js";
import type { FilingHandler } from "../types.js";

export function createAllPortalHandlers(): FilingHandler[] {
  return [
    new CaliforniaPortalHandler(),
    new TexasPortalHandler(),
    new FloridaPortalHandler(),
    new DelawarePortalHandler(),
    new WyomingPortalHandler(),
    new NewYorkPortalHandler(),
    new NevadaPortalHandler(),
    new IllinoisPortalHandler(),
    new GeorgiaPortalHandler(),
    new WashingtonPortalHandler(),
  ];
}
