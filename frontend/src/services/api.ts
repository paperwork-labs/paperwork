/// <reference types="vite/client" />
import axios, { AxiosResponse, AxiosError } from 'axios';

// Prefer env-configured base URL; fallback to relative path with dev proxy support
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Enhanced request queue for connection optimization
class RequestQueue {
  private queue: Array<() => Promise<any>> = [];
  private processing = false;
  private maxConcurrent = 6; // Optimize for backend connection limits
  private activeRequests = 0;

  async add<T>(requestFn: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
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

// Enhanced request interceptor with queue and retry logic
api.interceptors.request.use(
  (config) => {
    console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url}`);

    // Attach JWT if available
    try {
      const token = localStorage.getItem('qm_token');
      if (token) {
        config.headers = config.headers || {};
        (config.headers as any)['Authorization'] = `Bearer ${token}`;
      }
    } catch { }

    // Add cache headers for GET requests
    if (config.method === 'get') {
      config.headers['Cache-Control'] = 'max-age=30';
    }

    return config;
  },
  (error) => {
    console.error('❌ Request Error:', error);
    return Promise.reject(error);
  }
);

// Enhanced response interceptor with better error handling
api.interceptors.response.use(
  (response) => {
    console.log(`✅ API Response: ${response.config.url} - ${response.status} (${response.headers['x-response-time'] || 'unknown'}ms)`);
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config;

    // Enhanced error logging
    console.error('❌ Response Error:', {
      url: error.config?.url,
      status: error.response?.status,
      message: error.message,
      data: error.response?.data
    });

    // 401 Unauthorized — token expired or invalid.
    // Clear the stored token and notify AuthContext so the app redirects to /login.
    // Skip for login/register endpoints (those return 401 for bad credentials, not expired tokens).
    if (
      error.response?.status === 401 &&
      originalRequest?.url &&
      !originalRequest.url.includes('/auth/login') &&
      !originalRequest.url.includes('/auth/register')
    ) {
      try { localStorage.removeItem('qm_token'); } catch { /* ignore */ }
      window.dispatchEvent(new Event('auth:logout'));
    }

    // Retry logic for network errors (skip when _noRetry is set)
    if ((error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK') && originalRequest && !(originalRequest as any)._noRetry) {
      if (!(originalRequest as any)._retry) {
        (originalRequest as any)._retry = true;
        console.log('🔄 Retrying request:', originalRequest.url);
        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1s before retry
        return api(originalRequest);
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

// Portfolio API endpoints - enhanced with optimization
export const portfolioApi = {
  getLive: async (accountId?: string) => {
    const url = accountId ? `/portfolio/live?account_id=${encodeURIComponent(accountId)}` : '/portfolio/live';
    return makeOptimizedRequest(() => api.get(url));
  },

  getDashboard: async (brokerage?: string) => {
    const url = brokerage ? `/portfolio/dashboard?brokerage=${brokerage}` : '/portfolio/dashboard';
    return makeOptimizedRequest(() => api.get(url));
  },

  sync: async () => {
    // Align to unified accounts sync-all endpoint
    return makeOptimizedRequest(() => api.post('/accounts/sync-all'));
  },

  getTaxLots: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/tax-lots'));
  },

  getHoldingTaxLots: async (holdingId: number) => {
    // Backend route is /portfolio/stocks/{position_id}/tax-lots
    return makeOptimizedRequest(() => api.get(`/portfolio/stocks/${holdingId}/tax-lots`));
  },

  // New aligned stocks endpoint
  getStocks: async (accountId?: string) => {
    const url = accountId ? `/portfolio/stocks?account_id=${encodeURIComponent(accountId)}` : '/portfolio/stocks';
    return makeOptimizedRequest(() => api.get(url));
  },

  // Back-compat shim for old callers
  getStocksOnly: async (accountId?: string) => {
    return portfolioApi.getStocks(accountId);
  },

  // Enhanced statements with error handling
  getStatements: async (accountId?: string, days: number = 30) => {
    const url = accountId ? `/portfolio/statements?account_id=${encodeURIComponent(accountId)}&days=${days}` : `/portfolio/statements?days=${days}`;
    try {
      return await makeOptimizedRequest(() => api.get(url));
    } catch (error) {
      console.warn('Statements API fallback to sample data');
      return {
        status: 'success',
        data: {
          transactions: [],
          summary: { total_transactions: 0 },
          message: 'IBKR connection unavailable - using sample data'
        }
      };
    }
  },

  // Enhanced dividends with fallback
  getDividends: async (accountId?: string, days: number = 365) => {
    const url = accountId ? `/portfolio/dividends?days=${days}&account_id=${encodeURIComponent(accountId)}` : `/portfolio/dividends?days=${days}`;
    try {
      return await makeOptimizedRequest(() => api.get(url));
    } catch (error) {
      console.warn('Dividends API fallback');
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
      console.error('Batch API call failed:', error);
      throw error;
    }
  }
};

// Options API endpoints - enhanced
export const optionsApi = {
  getPortfolio: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/options/unified/portfolio'));
  },

  getSummary: async () => {
    return makeOptimizedRequest(() => api.get('/portfolio/options/unified/summary'));
  },

  sync: async () => {
    // No dedicated route; use accounts sync-all
    return makeOptimizedRequest(() => api.post('/accounts/sync-all'));
  },

  // Batch options data
  getBatchOptionsData: async () => {
    return portfolioApi.getBatchData([
      '/options/unified/portfolio',
      '/options/unified/summary'
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
  }) => {
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
    return makeOptimizedRequest(() => api.get(url));
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
      console.warn('TastyTrade API not available');
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
    console.warn('Backend health check failed:', error);
    return false;
  }
};

// Performance monitoring
export const getApiPerformanceMetrics = () => {
  return {
    activeRequests: (requestQueue as any).activeRequests,
    queueLength: (requestQueue as any).queue.length,
    maxConcurrent: (requestQueue as any).maxConcurrent
  };
};

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
  login: async (payload: { username: string; password: string }) => {
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
  acceptInvite: async (payload: { token: string; username: string; password: string; full_name?: string }) => {
    return makeOptimizedRequest(() => api.post('/auth/invite/accept', payload));
  },
};

export const appSettingsApi = {
  get: async () => makeOptimizedRequest(() => api.get('/app-settings')),
  update: async (payload: { market_only_mode?: boolean; portfolio_enabled?: boolean; strategy_enabled?: boolean }) =>
    makeOptimizedRequest(() => api.patch('/admin/app-settings', payload)),
};

export const adminUsersApi = {
  list: async (params?: { q?: string; role?: string }) =>
    makeOptimizedRequest(() => api.get('/admin/users', { params })),
  invites: async () => makeOptimizedRequest(() => api.get('/admin/users/invites')),
  invite: async (payload: { email: string; role: string; expires_in_days?: number }) =>
    makeOptimizedRequest(() => api.post('/admin/users/invite', payload)),
  update: async (userId: number, payload: { role?: string; is_active?: boolean }) =>
    makeOptimizedRequest(() => api.patch(`/admin/users/${userId}`, payload)),
};

// Accounts API
export const accountsApi = {
  list: async () => makeOptimizedRequest(() => api.get('/accounts')),
  add: async (payload: { broker: string; account_number: string; account_name?: string; account_type: string; api_credentials?: any; is_paper_trading?: boolean }) =>
    makeOptimizedRequest(() => api.post('/accounts/add', payload)),
  sync: async (accountId: number, sync_type: string = 'comprehensive') =>
    makeOptimizedRequest(() => api.post(`/accounts/${accountId}/sync`, { sync_type })),
  syncStatus: async (accountId: number) => makeOptimizedRequest(() => api.get(`/accounts/${accountId}/sync-status`)),
  remove: async (accountId: number) => makeOptimizedRequest(() => api.delete(`/accounts/${accountId}`)),
};

// Aggregator API
export const aggregatorApi = {
  brokers: async () => makeOptimizedRequest(() => api.post('/aggregator/brokers')),
  schwabLink: async (account_id: number, trading: boolean = false) =>
    makeOptimizedRequest(() => api.post('/aggregator/schwab/link', { account_id, trading })),
  config: async () => makeOptimizedRequest(() => api.get('/aggregator/config')),
  schwabProbe: async () => makeOptimizedRequest(() => api.get('/aggregator/schwab/probe')),
  tastytradeConnect: async (payload: { username: string; password: string; mfa_code?: string }) =>
    makeOptimizedRequest(() => api.post('/aggregator/tastytrade/connect', payload, { timeout: 60000, _noRetry: true } as any)),
  tastytradeDisconnect: async () => makeOptimizedRequest(() => api.post('/aggregator/tastytrade/disconnect')),
  tastytradeStatus: async (jobId?: string) =>
    makeOptimizedRequest(() => api.get('/aggregator/tastytrade/status', { params: jobId ? { job_id: jobId } : {} })),
  ibkrFlexConnect: async (payload: { flex_token: string; query_id: string }) =>
    makeOptimizedRequest(() => api.post('/aggregator/ibkr/connect', payload, { timeout: 60000, _noRetry: true } as any)),
  ibkrFlexStatus: async () => makeOptimizedRequest(() => api.get('/aggregator/ibkr/status')),
  ibkrFlexDisconnect: async () => makeOptimizedRequest(() => api.post('/aggregator/ibkr/disconnect')),
};