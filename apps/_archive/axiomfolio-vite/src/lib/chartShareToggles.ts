import type { IndicatorToggles } from "@/components/charts/SymbolChartWithMarkers";
import { defaultIndicators } from "@/components/charts/SymbolChartWithMarkers";

const KEYS: (keyof IndicatorToggles)[] = [
  "trendLines",
  "gaps",
  "tdSequential",
  "emas",
  "stage",
  "supportResistance",
  "rsMansfieldRibbon",
];

/**
 * Build indicator toggles from a signed share token’s `indicators` list.
 * Empty list = same defaults as the in-app chart (all study layers on).
 */
export function indicatorTogglesFromShareList(
  list: string[] | undefined,
): IndicatorToggles {
  const base = defaultIndicators();
  if (!list || list.length === 0) {
    return base;
  }
  const allowed = new Set(
    list.filter((x): x is keyof IndicatorToggles => KEYS.includes(x as keyof IndicatorToggles)),
  );
  if (allowed.size === 0) {
    return base;
  }
  const out: IndicatorToggles = {
    trendLines: false,
    gaps: false,
    tdSequential: false,
    emas: false,
    stage: false,
    supportResistance: false,
    rsMansfieldRibbon: false,
  };
  for (const k of allowed) {
    out[k] = true;
  }
  return out;
}
