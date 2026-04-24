/**
 * Simulated GET /market-data/regime/current bodies before `normalizeRegimeCurrentBody`.
 * Axios-style double wrap — same row shape production unwraps from FastAPI `{ regime }`.
 */
export const REGIME_CURRENT_RAW_AXIOS_SHAPED = {
  data: {
    regime: {
      regime_state: 'R2',
      composite_score: 2.2,
      as_of_date: '2026-01-08',
      regime_multiplier: 0.75,
      max_equity_exposure_pct: 90,
      cash_floor_pct: 10,
      vix_spot: null,
      vix3m_vix_ratio: null,
      vvix_vix_ratio: null,
      nh_nl: null,
      pct_above_200d: null,
      pct_above_50d: null,
    },
  },
};
