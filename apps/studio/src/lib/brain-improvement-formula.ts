/**
 * Brain Improvement Index composite weights — mirrors `apis/brain/app/services/self_improvement.py`.
 * Kept in a tiny module so client tabs can import without pulling filesystem helpers.
 */
export const BII_FORMULA = {
  W_ACCEPTANCE: 0.4,
  W_PROMOTION: 0.3,
  W_RULES: 0.2,
  W_RETRO: 0.1,
  RULES_CAP: 50,
  PROMOTION_THRESHOLD: 50,
  RETRO_NEUTRAL: 50.0,
  RETRO_SCALE: 2.5,
} as const;
