/// <reference types="vite/client" />
import axios, {
  AxiosResponse,
  AxiosError,
  type AxiosAdapter,
  type InternalAxiosRequestConfig,
} from 'axios';

import { normalizeRegimeCurrentBody } from './regimeCurrentNormalize';

declare module 'axios' {
  interface AxiosRequestConfig<D = any> {
    _noRetry?: boolean;
    /** When true, skip GET request coalescing (same URL + auth may run in parallel). */
    _noDedupe?: boolean;
  }

  interface InternalAxiosRequestConfig<D = any> {
    _noRetry?: boolean;
    _noDedupe?: boolean;
  }
}

// Prefer env-configured base URL; fallback to relative path with dev proxy support
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Enhanced request queue for connection optimization
class RequestQueue {
  private queue: Array<() => Promise<any>> = [];
  private processing = false;
  private maxConcurrent = 6; // Optimize for backend connection limits
  private maxQueueSize = 100;
  private activeRequests = 0;

  async add<T>(requestFn: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      if (this.queue.length >= this.maxQueueSize) {
        reject(new Error('Request queue is full'));
        return;
      }
      this.queue.push(async () => {
        try {
          this.activeRequests++;
          const result = await requestFn();
          resolve(result);
        } catch (error) {
          reject(error);
        } finally {
          this.activeRequests--;
          this.processNext();
        }
      });
      this.processNext();
    });
  }

  private processNext() {
    if (this.activeRequests >= this.maxConcurrent || this.queue.length === 0) {
      return;
    }

    const nextRequest = this.queue.shift();
    if (nextRequest) {
      nextRequest();
    }
  }

  getMetrics() {
    return {
      activeRequests: this.activeRequests,
      queueLength: this.queue.length,
      maxConcurrent: this.maxConcurrent,
    };
  }
}

const requestQueue = new RequestQueue();

// Enhanced axios instance with optimization
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // Reduced timeout for faster feedback
  // Connection optimization
  maxRedirects: 3,
});

// Coalesce concurrent identical GETs (same resolved URI + Authorization) to one network call.
const inflightGetRequests = new Map<string, Promise<unknown>>();

/** Deep-clone GET response data for deduped consumers; falls back to shallow copy if clone fails. */
export function cloneDedupedGetResponse<T>(response: AxiosResponse<T>): AxiosResponse<T> {
  try {
    const raw = response.data;
    const data =
      typeof structuredClone === 'function'
        ? structuredClone(raw)
        : raw === undefined
          ? raw
          : (JSON.parse(JSON.stringify(raw)) as T);
    return {
      ...response,
      data,
    };
  } catch {
    return { ...response };
  }
}
const baseHttpAdapter = api.defaults.adapter;
if (typeof baseHttpAdapter === 'function') {
  api.defaults.adapter = (config: InternalAxiosRequestConfig) => {
    const c = config as InternalAxiosRequestConfig & { _noDedupe?: boolean };
    const method = (c.method || 'get').toLowerCase();
    if (method !== 'get' || c._noDedupe) {
      return baseHttpAdapter(c);
    }
    let uri: string;
    try {
      uri = axios.getUri(c);
    } catch {
      const base = c.baseURL ?? '';
      const path = c.url ?? '';
      uri = `${base}${path}`;
    }
    const auth = String(
      c.headers?.get?.('Authorization') ??
        (c.headers as Record<string, string | undefined>)?.Authorization ??
        '',
    );
    const key = `${uri}::${auth}`;
    const existing = inflightGetRequests.get(key);
    if (existing) {
      return (existing as Promise<AxiosResponse>).then((response) =>
        cloneDedupedGetResponse(response),
      ) as ReturnType<AxiosAdapter>;
    }
    const promise = baseHttpAdapter(c).finally(() => {
      inflightGetRequests.delete(key);
    });
    inflightGetRequests.set(key, promise);
    return promise;
  };
}

api.interceptors.request.use(
  (config) => {
    try {
      const token = localStorage.getItem('qm_token');
      if (token) {
        config.headers = config.headers || {};
        (config.headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
      }
    } catch { }

    if (config.method === 'get') {
      config.headers['Cache-Control'] = 'max-age=30';
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

let isRefreshing = false;
let refreshSubscribers: Array<{ resolve: (token: string) => void; reject: (err: Error) => void }> = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach(sub => sub.resolve(token));
  refreshSubscribers = [];
}

function onRefreshFailed(err: Error) {
  refreshSubscribers.forEach(sub => sub.reject(err));
  refreshSubscribers = [];
}

/** Reject queued waiters, clear refresh state, then logout. Always call this (or onRefreshed + isRefreshing=false) before clearing the session. */
function finalizeAuthRefreshFailure(err: Error): Promise<never> {
  onRefreshFailed(err);
  isRefreshing = false;
  try {
    localStorage.removeItem('qm_token');
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event('auth:logout'));
  return Promise.reject(new Error('Session expired'));
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      originalRequest?.url &&
      !originalRequest.url.includes('/auth/login') &&
      !originalRequest.url.includes('/auth/register') &&
      !originalRequest.url.includes('/auth/refresh')
    ) {
      const orig = originalRequest as typeof originalRequest & { _noRetry?: boolean; _retry?: boolean };
      if (!orig._retry) {
        if (isRefreshing) {
          // Same as the leader: one refresh attempt per request; replay must not re-enter this block or we loop on repeated 401.
          orig._retry = true;
          return new Promise((resolve, reject) => {
            refreshSubscribers.push({
              resolve: (token: string) => {
                if (originalRequest.headers) {
                  (originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
                }
                resolve(api(originalRequest));
              },
              reject,
            });
          });
        }

        orig._retry = true;
        isRefreshing = true;
        try {
          const resp = await api.post('/auth/refresh', null, { withCredentials: true, _noRetry: true } as Record<string, unknown>);
          const newToken = resp.data?.access_token;
          if (newToken) {
            localStorage.setItem('qm_token', newToken);
            if (originalRequest.headers) {
              (originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`;
            }
            onRefreshed(newToken);
            isRefreshing = false;
            return api(originalRequest);
          }
          const noTokenErr = new Error('Refresh succeeded but no access_token returned');
          return finalizeAuthRefreshFailure(noTokenErr);
        } catch (refreshErr) {
          return finalizeAuthRefreshFailure(
            refreshErr instanceof Error ? refreshErr : new Error('Refresh failed')
          );
        }
      }
    }

    const orig = originalRequest as typeof originalRequest & { _noRetry?: boolean; _retry?: boolean; _retryCount?: number };
    if ((error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK') && originalRequest && !orig._noRetry) {
      if (!orig._retry) {
        orig._retry = true;
        await new Promise(resolve => setTimeout(resolve, 1000));
        return api(originalRequest);
      }
    }

    if (error.response && [500, 502, 503, 504].includes(error.response.status) && originalRequest) {
      const method = (originalRequest.method || 'get').toLowerCase();
      const isIdempotent = ['get', 'head', 'options'].includes(method);
      if (isIdempotent && !orig._noRetry) {
        const retryCount = orig._retryCount || 0;
        if (retryCount < 3) {
          orig._retryCount = retryCount + 1;
          await new Promise(resolve => setTimeout(resolve, Math.pow(2, retryCount) * 1000));
          return api(originalRequest);
        }
      }
    }

    return Promise.reject(error);
  }
);

// Optimized API call wrapper with queue
const makeOptimizedRequest = async <T>(requestFn: () => Promise<AxiosResponse<T>>) => {
  return requestQueue.add(async () => {
    const response = await requestFn();
    return response.data;
  });
};

// Portfolio API response shapes (for typing hooks and callers)
export interface StocksResponse {
  data?: { stocks?: unknown[]; holdings?: unknown[]; data?: { stocks?: unknown[] } };
  stocks?: unknown[];
  holdings?: unknown[];
}

export interface DashboardSummary {
  total_market_value?: number;
  total_cost_basis?: number;
  unrealized_pnl?: number;
  day_change?: number;
  day_change_pct?: number;
  [key: string]: unknown;
}
export interface DashboardResponse {
  status?: string;
  data?: { summary?: DashboardSummary };
  summary?: DashboardSummary;
}

/** Payload inside GET /portfolio/dashboard/pnl-summary `data` field */
export interface PnlSummaryData {
  unrealized_pnl: number;
  realized_pnl: number;
  total_dividends: number;
  total_fees: number;
  total_return: number;
  generated_at?: string;
}

/** JSON body from GET /portfolio/dashboard/pnl-summary (after axios `response.data` unwrap). */
export interface PnlSummaryResponse {
  status?: string;
  data?: PnlSummaryData;
}

export interface StatementsResponse {
  data?: { transactions?: unknown[] };
  transactions?: unknown[];
}

export interface LiveResponse {
  data?: { accounts?: Record<string, unknown> };
  accounts?: Record<string, unknown>;
}

export interface ActivityResponse {
  data?: { activity?: unknown[]; total?: number };
  activity?: unknown[];
  total?: number;
}

export interface UsersListResponse {
  users?: unknown[];
}

/**
 * Unwrap a backend response that may be double-wrapped by axios and/or the
 * `{status, data}` envelope.  Handles all three shapes:
 *   - `response.data.data[key]`   (axios + envelope)
 *   - `response.data[key]`        (axios only, or bare envelope)
 *   - `response[key]`             (already unwrapped by makeOptimizedRequest)
 * Responses are from our backend; runtime validation (e.g. zod) can be added if needed.
 */
export function unwrapResponse<T = unknown>(response: unknown, key: string): T[] {
  const r = response as Record<string, any> | undefined;
  return (r?.data?.data?.[key] ?? r?.data?.[key] ?? r?.[key] ?? []) as T[];
}

export function unwrapResponseSingle<T = unknown>(response: unknown, key: string): T | undefined {
  const r = response as Record<string, any> | undefined;
  return (r?.data?.data?.[key] ?? r?.data?.[key] ?? r?.[key]) as T | undefined;
}

export interface InvitesListResponse {
  invites?: unknown[];
}

// Portfolio API endpoints - enhanced with optimization
export const portfolioApi = {
  getLive: async (accountId?: string): Promise<LiveResponse> => {
    const url = accountId ? `/portfolio/live?account_id=${encodeURIComponent(accountId)}` : '/portfolio/live';
    return makeOptimizedRequest<LiveResponse>(() => api.get(url));
  },

  getDashboard: async (brokerage?: string): Promise<DashboardResponse> => {
    const url = brokerage ? `/portfolio/dashboard?brokerage=${brokerage}` : '/portfolio/dashboard';
    return makeOptimizedRequest<DashboardResponse>(() => api.get(url));
  },

  getPerformanceHistory: async (params?: { accountId?: string; period?: string }) => {
    const q = new URLSearchParams();
    if (params?.accountId) q.set('account_id', params.accountId);
    if (params?.period) q.set('period', params.period);
    const url = `/portfolio/performance/history${q.toString() ? `?${q.toString()}` : ''}`;
    return makeOptimizedRequest(() => api.get(url));
  },

  getCategoryViews: async () => makeOptimizedRequest(() => api.get('/portfolio/categories/views')),
  getCategories: async (categoryType?: string) => {
    const params = categoryType
      ? `?${new URLSearchParams({ category_type: categoryType })}`
      : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/categories${params}`));
  },
  getCategory: async (id: number) => makeOptimizedRequest(() => api.get(`/portfolio/categories/${id}`)),
  createCategory: async (body: { name: string; target_allocation_pct?: number; description?: string; color?: string; category_type?: string }) =>
    makeOptimizedRequest(() => api.post('/portfolio/categories', body)),
  updateCategory: async (id: number, body: { name?: string; target_allocation_pct?: number; description?: string; color?: string }) =>
    makeOptimizedRequest(() => api.put(`/portfolio/categories/${id}`, body)),
  deleteCategory: async (id: number) => makeOptimizedRequest(() => api.delete(`/portfolio/categories/${id}`)),
  reorderCategories: async (orderedIds: number[]) =>
    makeOptimizedRequest(() => api.put('/portfolio/categories/reorder', { ordered_ids: orderedIds })),
  assignPositions: async (categoryId: number, positionIds: number[]) =>
    makeOptimizedRequest(() => api.post(`/portfolio/categories/${categoryId}/positions`, { position_ids: positionIds })),
  unassignPosition: async (categoryId: number, positionId: number) =>
    makeOptimizedRequest(() => api.delete(`/portfolio/categories/${categoryId}/positions/${positionId}`)),

  sync: async () => {
    // Align to unified accounts sync-all endpoint
    return makeOptimizedRequest(() => api.post('/accounts/sync-all'));
  },

  getTaxLots: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/tax-lots'));
  },

  getAnalytics: async (accountId: number) => {
    return makeOptimizedRequest(() => api.get(`/portfolio/analytics/${accountId}`));
  },

  getTaxOptimization: async (accountId: number) => {
    return makeOptimizedRequest(() => api.get(`/portfolio/tax-optimization/${accountId}`));
  },

  getInsights: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/insights'));
  },

  getTaxSummary: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/tax-lots/tax-summary'));
  },

  getHoldingTaxLots: async (holdingId: number) => {
    // Backend route is /portfolio/stocks/{position_id}/tax-lots
    return makeOptimizedRequest(() => api.get(`/portfolio/stocks/${holdingId}/tax-lots`));
  },

  createManualTaxLot: async (body: { symbol: string; quantity: number; cost_per_share: number; acquisition_date: string; account_id?: number }) => {
    return makeOptimizedRequest(() => api.post('/portfolio/tax-lots', body));
  },

  updateManualTaxLot: async (id: number, body: { quantity?: number; cost_per_share?: number; acquisition_date?: string }) => {
    return makeOptimizedRequest(() => api.put(`/portfolio/tax-lots/${id}`, body));
  },

  deleteManualTaxLot: async (id: number) => {
    return makeOptimizedRequest(() => api.delete(`/portfolio/tax-lots/${id}`));
  },

  // New aligned stocks endpoint
  getStocks: async (accountId?: string, includeMarketData: boolean = true): Promise<StocksResponse> => {
    const params = new URLSearchParams();
    if (accountId) params.set('account_id', accountId);
    params.set('include_market_data', String(includeMarketData));
    const url = `/portfolio/stocks?${params.toString()}`;
    return makeOptimizedRequest<StocksResponse>(() => api.get(url));
  },

  // Back-compat shim for old callers
  getStocksOnly: async (accountId?: string) => {
    return portfolioApi.getStocks(accountId);
  },

  // Enhanced statements with error handling
  getStatements: async (accountId?: string, days: number = 30): Promise<StatementsResponse> => {
    const url = accountId ? `/portfolio/statements?account_id=${encodeURIComponent(accountId)}&days=${days}` : `/portfolio/statements?days=${days}`;
    try {
      return await makeOptimizedRequest<StatementsResponse>(() => api.get(url));
    } catch (error) {
      // statements unavailable, return empty
      return {
        data: {
          transactions: [],
        },
      };
    }
  },

  // Enhanced dividends with fallback
  getDividends: async (accountId?: string, days: number = 365) => {
    const url = accountId ? `/portfolio/dividends?days=${days}&account_id=${encodeURIComponent(accountId)}` : `/portfolio/dividends?days=${days}`;
    try {
      return await makeOptimizedRequest(() => api.get(url));
    } catch (error) {
      // dividends unavailable, return empty
      return {
        status: 'success',
        data: {
          dividends: [],
          summary: {},
          message: 'Dividend data unavailable'
        }
      };
    }
  },

  getBalances: async (accountId?: number) => {
    const q = accountId ? `?account_id=${accountId}` : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/balances${q}`));
  },

  getMarginInterest: async (accountId?: number, period?: string) => {
    const q = new URLSearchParams();
    if (accountId) q.set('account_id', String(accountId));
    if (period) q.set('period', period);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/margin-interest${qs}`));
  },

  getRealizedGains: async (year?: number, accountId?: string) => {
    const q = new URLSearchParams();
    if (year) q.set('year', String(year));
    if (accountId) q.set('account_id', accountId);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/realized-gains${qs}`));
  },

  getClosedPositions: async (accountId?: string) => {
    const q = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/stocks/closed${q}`));
  },

  getDividendSummary: async (accountId?: string) => {
    const q = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/dividends/summary${q}`));
  },

  getPnlSummary: async (accountId?: string): Promise<PnlSummaryData | undefined> => {
    const q = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
    const body = await makeOptimizedRequest<PnlSummaryResponse>(() =>
      api.get(`/portfolio/dashboard/pnl-summary${q}`),
    );
    return body?.data;
  },

  getLiveSummary: async (accountId?: string) => {
    const q = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/live/summary${q}`));
  },
  getLivePositions: async (accountId?: string) => {
    const q = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
    return makeOptimizedRequest(() => api.get(`/portfolio/live/positions${q}`));
  },

  getRiskMetrics: async () => {
    const r = await makeOptimizedRequest(() => api.get('/portfolio/risk-metrics'));
    return (r as any)?.data?.data ?? (r as any)?.data ?? {};
  },

  getRebalanceSuggestions: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/categories/rebalance-suggestions'));
  },

  // Batch API calls for improved performance
  getBatchData: async (endpoints: string[]) => {
    try {
      const requests = endpoints.map(endpoint => api.get(endpoint));
      const responses = await Promise.allSettled(requests);

      return responses.map((response, index) => ({
        endpoint: endpoints[index],
        success: response.status === 'fulfilled',
        data: response.status === 'fulfilled' ? response.value.data : null,
        error: response.status === 'rejected' ? response.reason : null
      }));
    } catch (error) {
      throw error;
    }
  }
};

// Options API endpoints - enhanced
export const optionsApi = {
  getPortfolio: async (accountId?: string) => {
    const url = accountId
      ? `/portfolio/options/unified/portfolio?account_id=${encodeURIComponent(accountId)}`
      : '/portfolio/options/unified/portfolio';
    return makeOptimizedRequest(() => api.get(url));
  },

  getSummary: async (accountId?: string) => {
    const url = accountId
      ? `/portfolio/options/unified/summary?account_id=${encodeURIComponent(accountId)}`
      : '/portfolio/options/unified/summary';
    return makeOptimizedRequest(() => api.get(url));
  },

  sync: async () => {
    // No dedicated route; use accounts sync-all
    return makeOptimizedRequest(() => api.post('/accounts/sync-all'));
  },

  // Batch options data
  getBatchOptionsData: async () => {
    return portfolioApi.getBatchData([
      '/portfolio/options/unified/portfolio',
      '/portfolio/options/unified/summary'
    ]);
  }
};

// Market data endpoints
export const marketDataApi = {
  getHistory: async (symbol: string, period: string = '1y', interval: string = '1d') => {
    return makeOptimizedRequest(() => api.get(`/market-data/prices/${encodeURIComponent(symbol)}/history?period=${encodeURIComponent(period)}&interval=${encodeURIComponent(interval)}`));
  },
  getDashboard: async () => {
    return makeOptimizedRequest(() => api.get('/market-data/dashboard'));
  },
  getSnapshot: async (symbol: string) => {
    return makeOptimizedRequest(() => api.get(`/market-data/snapshots/${encodeURIComponent(symbol)}`));
  },
  getVolatilityDashboard: async () => {
    return makeOptimizedRequest(() => api.get('/market-data/volatility-dashboard'));
  },
  getCurrentRegime: async (): Promise<Record<string, unknown> | null> => {
    const raw = await makeOptimizedRequest(() => api.get('/market-data/regime/current'));
    return normalizeRegimeCurrentBody(raw);
  },
  getRegimeHistory: async (days: number = 90) => {
    return makeOptimizedRequest(() => api.get(`/market-data/regime/history?days=${days}`));
  },
  getSnapshots: async (limit: number = 5000) => {
    return makeOptimizedRequest(() => api.get(`/market-data/snapshots?limit=${limit}`));
  },
  getSnapshotHistory: async (symbol: string, days: number = 200) => {
    return makeOptimizedRequest(() => api.get(`/market-data/snapshots/${encodeURIComponent(symbol)}/history?days=${days}`));
  },
  getSnapshotHistoryBatch: async (symbolsCsv: string, days: number = 90) => {
    const params = new URLSearchParams({
      symbols: symbolsCsv,
      days: String(days),
    });
    return makeOptimizedRequest(() =>
      api.get(`/market-data/snapshots/history/batch?${params.toString()}`),
    );
  },
  getLatestBrief: async (type: string = 'daily') => {
    return makeOptimizedRequest(() => api.get(`/market-data/intelligence/latest?brief_type=${type}`));
  },
  listBriefs: async (type?: string, limit: number = 20) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (type) params.set('brief_type', type);
    return makeOptimizedRequest(() => api.get(`/market-data/intelligence/briefs?${params}`));
  },
  getBrief: async (id: number) => {
    return makeOptimizedRequest(() => api.get(`/market-data/intelligence/briefs/${id}`));
  },
  triggerBrief: async (type: string = 'daily') => {
    return api.post(`/market-data/admin/intelligence/generate?brief_type=${type}`);
  },

  getPreMarketReadiness: async () => {
    return makeOptimizedRequest(() => api.get('/market-data/admin/pre-market-readiness'));
  },

  // Auto-fix endpoints for agent-powered remediation
  startAutoFix: async () => {
    return api.post('/market-data/admin/auto-fix');
  },
  getAutoFixStatus: async (jobId: string) => {
    return makeOptimizedRequest(() => api.get(`/market-data/admin/auto-fix/${jobId}/status`));
  },
};

// Unified Activity endpoints
export const activityApi = {
  getActivity: async (params: {
    accountId?: string;
    start?: string; // ISO date
    end?: string;   // ISO date
    symbol?: string;
    category?: string;
    side?: string;
    limit?: number;
    offset?: number;
  }): Promise<ActivityResponse> => {
    const q: string[] = [];
    if (params.accountId) q.push(`account_id=${encodeURIComponent(params.accountId)}`);
    if (params.start) q.push(`start=${encodeURIComponent(params.start)}`);
    if (params.end) q.push(`end=${encodeURIComponent(params.end)}`);
    if (params.symbol) q.push(`symbol=${encodeURIComponent(params.symbol)}`);
    if (params.category) q.push(`category=${encodeURIComponent(params.category)}`);
    if (params.side) q.push(`side=${encodeURIComponent(params.side)}`);
    q.push(`limit=${encodeURIComponent(String(params.limit ?? 500))}`);
    q.push(`offset=${encodeURIComponent(String(params.offset ?? 0))}`);
    const url = `/portfolio/activity?${q.join('&')}`;
    return makeOptimizedRequest<ActivityResponse>(() => api.get(url));
  },
  getDailySummary: async (params: {
    accountId?: string;
    start?: string;
    end?: string;
    symbol?: string;
  }) => {
    const q: string[] = [];
    if (params.accountId) q.push(`account_id=${encodeURIComponent(params.accountId)}`);
    if (params.start) q.push(`start=${encodeURIComponent(params.start)}`);
    if (params.end) q.push(`end=${encodeURIComponent(params.end)}`);
    if (params.symbol) q.push(`symbol=${encodeURIComponent(params.symbol)}`);
    const url = `/portfolio/activity/daily_summary?${q.join('&')}`;
    return makeOptimizedRequest(() => api.get(url));
  }
};

// TastyTrade API endpoints - enhanced
export const tastytradeApi = {
  getAccounts: async () => {
    try {
      // Align to unified accounts list
      return await makeOptimizedRequest(() => api.get('/accounts'));
    } catch (error) {
      // TastyTrade API unavailable
      return { status: 'error', message: 'TastyTrade API unavailable' };
    }
  },

  sync: async () => {
    // Align to unified accounts sync-all
    return makeOptimizedRequest(() => api.post('/accounts/sync-all'));
  }
};

// FlexQuery (IBKR Tax Optimizer) API endpoints
export const flexqueryApi = {
  getStatus: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/flexquery/status'));
  },

  syncTaxLots: async (accountId: string) => {
    return makeOptimizedRequest(() => api.post('/portfolio/flexquery/sync-tax-lots', {
      account_id: accountId
    }));
  }
};

// Tasks API endpoints - for Discord notifications and alerts
export const tasksApi = {
  sendPortfolioDigest: async () => {
    return makeOptimizedRequest(() => api.post('/tasks/portfolio-digest'));
  },

  forcePortfolioAlerts: async () => {
    return makeOptimizedRequest(() => api.post('/tasks/portfolio-alerts'));
  },

  sendSignals: async () => {
    return makeOptimizedRequest(() => api.post('/tasks/signals'));
  },

  sendMorningBrew: async () => {
    return makeOptimizedRequest(() => api.post('/tasks/morning-brew'));
  },

  sendSystemStatus: async () => {
    return makeOptimizedRequest(() => api.post('/tasks/system-status'));
  }
};

// Enhanced error handler with user-friendly messages
export const handleApiError = (error: any): string => {
  // Enhanced network error detection
  if (error.code === 'ERR_NETWORK' || error.code === 'ECONNABORTED') {
    return 'Connection failed - check if backend is running on port 8000';
  }

  if (error.response) {
    const status = error.response.status;
    const message = error.response.data?.detail || error.response.data?.message || 'Unknown error';

    switch (status) {
      case 401:
        return 'Unauthorized - please log in again';
      case 503:
        return 'Service unavailable - IBKR connection required';
      case 500:
        return 'Server error - check backend logs';
      case 502:
        return 'Bad gateway - backend service may be restarting';
      case 504:
        return 'Request timeout - try again in a moment';
      case 404:
        return 'Endpoint not found';
      case 429:
        return 'Too many requests - please wait a moment';
      default:
        return `Error ${status}: ${message}`;
    }
  } else if (error.request) {
    return 'No response from server - backend may be offline';
  } else {
    return error.message || 'Request failed';
  }
};

// Connection health checker
export const checkBackendHealth = async (): Promise<boolean> => {
  try {
    await api.get('/health', { timeout: 5000 });
    return true;
  } catch (error) {
    // health check failed
    return false;
  }
};

// Performance monitoring
export const getApiPerformanceMetrics = () => requestQueue.getMetrics();

// Export types
export interface PortfolioSummary {
  total_value: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  accounts_summary: any[];
}

export default api;

// Auth API
export const authApi = {
  register: async (payload: { username: string; email: string; password: string; full_name?: string }) => {
    return makeOptimizedRequest(() => api.post('/auth/register', payload));
  },
  login: async (payload: { email: string; password: string }) => {
    return makeOptimizedRequest(() => api.post('/auth/login', payload));
  },
  me: async () => {
    return makeOptimizedRequest(() => api.get('/auth/me'));
  },
  updateMe: async (payload: any) => {
    return makeOptimizedRequest(() => api.put('/auth/me', payload));
  },
  changePassword: async (payload: { current_password?: string; new_password: string }) => {
    return makeOptimizedRequest(() => api.post('/auth/change-password', payload));
  },
  inviteInfo: async (token: string) => {
    return makeOptimizedRequest(() => api.get(`/auth/invite/${token}`));
  },
  acceptInvite: async (payload: { token: string; password: string; full_name: string }) => {
    return makeOptimizedRequest(() => api.post('/auth/invite/accept', payload));
  },
};

export const appSettingsApi = {
  get: async () => makeOptimizedRequest(() => api.get('/app-settings')),
  update: async (payload: { market_only_mode?: boolean; portfolio_enabled?: boolean; strategy_enabled?: boolean }) =>
    makeOptimizedRequest(() => api.patch('/admin/app-settings', payload)),
};

export const adminUsersApi = {
  list: async (params?: { q?: string; role?: string }): Promise<UsersListResponse> =>
    makeOptimizedRequest<UsersListResponse>(() => api.get('/admin/users', { params })),
  invites: async (): Promise<InvitesListResponse> =>
    makeOptimizedRequest<InvitesListResponse>(() => api.get('/admin/users/invites')),
  invite: async (payload: { email: string; role: string; expires_in_days?: number }) =>
    makeOptimizedRequest(() => api.post('/admin/users/invite', payload)),
  update: async (userId: number, payload: { role?: string; is_active?: boolean }) =>
    makeOptimizedRequest(() => api.patch(`/admin/users/${userId}`, payload)),
  remove: async (userId: number) =>
    makeOptimizedRequest(() => api.delete(`/admin/users/${userId}`)),
};

/** POST /api/v1/admin/users/{userId}/approve (base URL is configured on the axios instance). */
export async function approveUser(userId: number) {
  return makeOptimizedRequest(() => api.post(`/admin/users/${userId}/approve`));
}

/** DELETE /api/v1/admin/users/{userId} */
export async function deleteUser(userId: number) {
  return makeOptimizedRequest(() => api.delete(`/admin/users/${userId}`));
}

// Accounts API
export const accountsApi = {
  list: async () => makeOptimizedRequest(() => api.get('/accounts')),
  add: async (payload: { broker: string; account_number: string; account_name?: string; account_type: string; api_credentials?: any; is_paper_trading?: boolean }) =>
    makeOptimizedRequest(() => api.post('/accounts/add', payload)),
  sync: async (accountId: number, sync_type: string = 'comprehensive') =>
    makeOptimizedRequest(() => api.post(`/accounts/${accountId}/sync`, { sync_type })),
  syncStatus: async (accountId: number) => makeOptimizedRequest(() => api.get(`/accounts/${accountId}/sync-status`)),
  syncHistory: async (accountId?: number) =>
    makeOptimizedRequest(() =>
      api.get('/accounts/sync-history', { params: accountId != null ? { account_id: accountId } : {} })
    ),
  updateAccount: async (accountId: number, payload: { account_name?: string; account_type?: string; is_enabled?: boolean }) =>
    makeOptimizedRequest(() => api.patch(`/accounts/${accountId}`, payload)),
  updateCredentials: async (
    accountId: number,
    payload: { broker: string; credentials: Record<string, string>; account_number?: string }
  ) => makeOptimizedRequest(() => api.patch(`/accounts/${accountId}/credentials`, payload)),
  remove: async (accountId: number) => makeOptimizedRequest(() => api.delete(`/accounts/${accountId}`)),
};

// Aggregator API
export const aggregatorApi = {
  brokers: async () => makeOptimizedRequest(() => api.post('/aggregator/brokers')),
  schwabLink: async (account_id: number, trading: boolean = false) =>
    makeOptimizedRequest(() => api.post('/aggregator/schwab/link', { account_id, trading })),
  config: async () => makeOptimizedRequest(() => api.get('/aggregator/config')),
  schwabProbe: async () => makeOptimizedRequest(() => api.get('/aggregator/schwab/probe')),
  tastytradeConnect: async (payload: { client_id: string; client_secret: string; refresh_token: string }) =>
    makeOptimizedRequest(() => api.post('/aggregator/tastytrade/connect', payload, { timeout: 60000, _noRetry: true })),
  tastytradeDisconnect: async () => makeOptimizedRequest(() => api.post('/aggregator/tastytrade/disconnect')),
  tastytradeStatus: async (jobId?: string) =>
    makeOptimizedRequest(() => api.get('/aggregator/tastytrade/status', { params: jobId ? { job_id: jobId } : {} })),
  ibkrFlexConnect: async (payload: { flex_token: string; query_id: string; account_number?: string }) =>
    makeOptimizedRequest(() => api.post('/aggregator/ibkr/connect', payload, { timeout: 60000, _noRetry: true })),
  ibkrFlexStatus: async (jobId?: string) =>
    makeOptimizedRequest(() =>
      api.get('/aggregator/ibkr/status', { params: jobId ? { job_id: jobId } : {} })
    ),
  ibkrFlexDisconnect: async () => makeOptimizedRequest(() => api.post('/aggregator/ibkr/disconnect')),
};