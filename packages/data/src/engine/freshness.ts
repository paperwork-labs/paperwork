import type { StateCode, DataFreshness } from "../types/common";
import type { FormationRules } from "../types/formation";
import type { StateTaxRules } from "../types/tax";

const STALE_THRESHOLD_DAYS = 90;

export function checkFreshness(
  state: StateCode,
  dataset: "formation" | "tax" | "compliance",
  lastVerified: string,
): DataFreshness {
  const verifiedDate = new Date(lastVerified);
  if (Number.isNaN(verifiedDate.getTime())) {
    return {
      state,
      dataset,
      last_verified: lastVerified,
      days_since_verification: Infinity,
      is_stale: true,
    };
  }
  const now = new Date();
  const daysSince = Math.floor((now.getTime() - verifiedDate.getTime()) / (1000 * 60 * 60 * 24));

  return {
    state,
    dataset,
    last_verified: lastVerified,
    days_since_verification: daysSince,
    is_stale: daysSince > STALE_THRESHOLD_DAYS,
  };
}

export function getFormationFreshness(rules: FormationRules): DataFreshness {
  return checkFreshness(rules.state, "formation", rules.verification.last_verified);
}

export function getTaxFreshness(rules: StateTaxRules): DataFreshness {
  return checkFreshness(rules.state, "tax", rules.verification.last_verified);
}
