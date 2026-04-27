import { useQuery } from '@tanstack/react-query';

import { marketDataApi } from '@/services/api';

export interface SentimentCompositeResponse {
  vix: number | null;
  aaii: { bull: number; bear: number; net: number } | null;
  fear_greed: { value: number; label: string } | null;
  regime: { state: string; score: number | null } | null;
  asof: string;
}

function normalizePayload(raw: unknown): SentimentCompositeResponse {
  if (raw == null || typeof raw !== 'object') {
    throw new Error('Invalid sentiment composite response');
  }
  const o = raw as Record<string, unknown>;
  const vix = o.vix;
  const aaii = o.aaii;
  const fearGreed = o.fear_greed;
  const regime = o.regime;
  const asof = o.asof;

  let parsedAaii: SentimentCompositeResponse['aaii'] = null;
  if (aaii != null && typeof aaii === 'object' && !Array.isArray(aaii)) {
    const bull = Number((aaii as { bull?: unknown }).bull);
    const bear = Number((aaii as { bear?: unknown }).bear);
    const net = Number((aaii as { net?: unknown }).net);
    if (Number.isFinite(bull) && Number.isFinite(bear) && Number.isFinite(net)) {
      parsedAaii = { bull, bear, net };
    }
  }

  let parsedFg: SentimentCompositeResponse['fear_greed'] = null;
  if (fearGreed != null && typeof fearGreed === 'object' && !Array.isArray(fearGreed)) {
    const value = Number((fearGreed as { value?: unknown }).value);
    const label = String((fearGreed as { label?: unknown }).label ?? '');
    if (Number.isFinite(value) && label.length > 0) {
      parsedFg = { value: Math.trunc(value), label };
    }
  }

  let parsedRegime: SentimentCompositeResponse['regime'] = null;
  if (regime != null && typeof regime === 'object' && !Array.isArray(regime)) {
    const state = String((regime as { state?: unknown }).state ?? '').trim();
    if (state.length > 0) {
      const s = (regime as { score?: unknown }).score;
      let score: number | null = null;
      if (s == null) {
        score = null;
      } else if (typeof s === 'number' && Number.isFinite(s)) {
        score = s;
      } else if (typeof s === 'string') {
        const n = Number(s);
        score = Number.isFinite(n) ? n : null;
      }
      parsedRegime = { state, score };
    }
  }

  return {
    vix: typeof vix === 'number' && Number.isFinite(vix) ? vix : null,
    aaii: parsedAaii,
    fear_greed: parsedFg,
    regime: parsedRegime,
    asof: typeof asof === 'string' ? asof : '',
  };
}

export function useSentimentComposite() {
  return useQuery({
    queryKey: ['sentiment-composite'] as const,
    queryFn: async () => {
      const raw = await marketDataApi.getSentimentComposite();
      return normalizePayload(raw);
    },
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
}
