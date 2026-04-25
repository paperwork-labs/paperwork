/**
 * GET /connections/health — aggregated broker link + sync status for the user.
 */
import api from './api';

export type ConnectionsBrokerHealthStatus = 'disconnected' | 'connected' | 'stale' | 'error';

export interface ConnectionsHealthBrokerRow {
  broker: string;
  status: ConnectionsBrokerHealthStatus;
  last_sync_at: string | null;
  error_message: string | null;
}

export interface ConnectionsHealthResponse {
  connected: number;
  total: number;
  last_sync_at: string | null;
  by_broker: ConnectionsHealthBrokerRow[];
}

export async function fetchConnectionsHealth(): Promise<ConnectionsHealthResponse> {
  const res = await api.get<ConnectionsHealthResponse>('/connections/health');
  return res.data;
}

export const connectionsApi = {
  getHealth: fetchConnectionsHealth,
};
