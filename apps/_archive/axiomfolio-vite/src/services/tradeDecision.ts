import api from './api';
import type { TradeDecisionExplanation } from '../types/tradeDecision';

const BASE = '/agent/trade-decisions';

export const tradeDecisionApi = {
  async get(orderId: number): Promise<TradeDecisionExplanation> {
    const res = await api.get<TradeDecisionExplanation>(`${BASE}/${orderId}`);
    return res.data;
  },

  async regenerate(orderId: number): Promise<TradeDecisionExplanation> {
    const res = await api.post<TradeDecisionExplanation>(
      `${BASE}/${orderId}/regenerate`,
    );
    return res.data;
  },
};
