import type { StateCode } from "../types/common";
import type { FormationRules } from "../types/formation";

const formationCache = new Map<StateCode, FormationRules>();

export function loadFormationData(state: StateCode, data: FormationRules): void {
  formationCache.set(state, data);
}

export function getStateFormationRules(state: StateCode): FormationRules | undefined {
  return formationCache.get(state);
}

export function getAllFormationStates(): StateCode[] {
  return Array.from(formationCache.keys()).sort();
}

export function getFormationFee(state: StateCode, expedited = false): number | undefined {
  const rules = formationCache.get(state);
  if (!rules) return undefined;
  return expedited && rules.fees.expedited
    ? rules.fees.expedited.amount_cents
    : rules.fees.standard.amount_cents;
}

/** Test helper / hot reload */
export function clearFormationCache(): void {
  formationCache.clear();
}
