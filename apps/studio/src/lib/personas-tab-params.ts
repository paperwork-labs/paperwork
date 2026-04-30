export const PERSONA_TAB_IDS = [
  "registry",
  "activity",
  "promotions-queue",
  "open-roles",
  "cost",
  "routing",
  "model-registry",
] as const;

export type PersonasTabId = (typeof PERSONA_TAB_IDS)[number];

export function resolvePersonasTab(raw: string | undefined): PersonasTabId {
  if (raw && (PERSONA_TAB_IDS as readonly string[]).includes(raw)) {
    return raw as PersonasTabId;
  }
  return "registry";
}

