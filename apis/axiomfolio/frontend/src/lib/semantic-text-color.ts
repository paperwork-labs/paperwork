import { heatColor } from "@/constants/chart";

/**
 * Maps legacy Chakra semantic color tokens (passed as the StatCard `color` prop)
 * to Tailwind classes backed by CSS variables in index.css.
 */
const CHAKRA_TEXT_CLASS: Record<string, string> = {
  "status.success": "text-[rgb(var(--status-success)/1)]",
  "status.danger": "text-[rgb(var(--status-danger)/1)]",
  "status.warning": "text-[rgb(var(--status-warning)/1)]",
  "status.info": "text-[rgb(var(--status-info)/1)]",
  "fg.success": "text-[rgb(var(--status-success)/1)]",
  "fg.error": "text-[rgb(var(--status-danger)/1)]",
  "fg.warning": "text-[rgb(var(--status-warning)/1)]",
  "green.400": "text-green-600 dark:text-green-400",
  "green.500": "text-green-600 dark:text-green-400",
  "green.600": "text-emerald-700 dark:text-emerald-400",
  "red.400": "text-red-500 dark:text-red-400",
  "red.500": "text-red-600 dark:text-red-400",
  "red.600": "text-red-700 dark:text-red-400",
  "orange.500": "text-orange-600 dark:text-orange-400",
  "yellow.400": "text-amber-500",
  "fg.default": "text-foreground",
  "fg.muted": "text-muted-foreground",
  "fg.subtle": "text-muted-foreground/70",
};

export function semanticTextColorClass(color?: string): string | undefined {
  if (!color) return undefined;
  return CHAKRA_TEXT_CLASS[color];
}

/** Tailwind class for heat-mapped numeric values (uses `heatColor` tiers). */
export function heatTextClass(v: unknown): string | undefined {
  const key = heatColor(v);
  if (!key) return undefined;
  return CHAKRA_TEXT_CLASS[key];
}
