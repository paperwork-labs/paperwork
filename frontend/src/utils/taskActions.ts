import api from '../services/api';

export type TaskParamSchema = {
  name: string;
  type?: string;
  default?: string | number | boolean;
  min?: number;
  max?: number;
  description?: string;
};

export type TaskAction = {
  task_name: string;
  method: string;
  endpoint: string;
  description?: string;
  status_task?: string;
  params_schema?: TaskParamSchema[];
};

type TriggerOptions = {
  params?: Record<string, string | number | boolean>;
  forceRefresh?: boolean;
};

let cachedActions: TaskAction[] | null = null;
let cachedAt = 0;
const CACHE_TTL_MS = 60_000;

const loadTaskActions = async (forceRefresh = false): Promise<TaskAction[]> => {
  const now = Date.now();
  if (!forceRefresh && cachedActions && now - cachedAt < CACHE_TTL_MS) {
    return cachedActions;
  }
  const res = await api.get('/market-data/admin/tasks');
  cachedActions = (res?.data?.tasks || []) as TaskAction[];
  cachedAt = now;
  return cachedActions;
};

const buildEndpoint = (
  endpoint: string,
  params?: Record<string, string | number | boolean>,
): string => {
  if (!params || Object.keys(params).length === 0) return endpoint;
  const url = new URL(endpoint, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    url.searchParams.set(key, String(value));
  });
  return `${url.pathname}${url.search}`;
};

const runTaskAction = async (action: TaskAction, params?: Record<string, string | number | boolean>) => {
  const method = String(action.method || 'POST').toUpperCase();
  const endpoint = buildEndpoint(action.endpoint, params);
  if (method === 'POST') return api.post(endpoint);
  if (method === 'GET') return api.get(endpoint);
  throw new Error(`Unsupported task method: ${action.method}`);
};

export const triggerTaskByName = async (taskName: string, options?: TriggerOptions) => {
  const actions = await loadTaskActions(Boolean(options?.forceRefresh));
  const action = actions.find((entry) => entry.task_name === taskName);
  if (!action) {
    throw new Error(`Unsupported task: ${taskName}`);
  }
  return runTaskAction(action, options?.params);
};

export const refreshTaskActions = async (): Promise<TaskAction[]> => {
  return loadTaskActions(true);
};

