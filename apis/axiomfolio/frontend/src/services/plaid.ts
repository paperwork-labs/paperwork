/**
 * Plaid Investments API client.
 *
 * Surfaces the `/api/v1/plaid` routes to the Connections page.
 * Every call except webhook is gated by the `broker.plaid_investments`
 * feature on the backend (402 Payment Required on miss) — the frontend
 * additionally wraps the UI in <TierGate feature="broker.plaid_investments">
 * to hide the controls for free users.
 */
import api from './api';

export interface PlaidLinkTokenResponse {
  link_token: string;
  expiration_seconds: number;
}

export interface PlaidExchangeRequest {
  public_token: string;
  // `metadata` is passed through as-is; the Plaid Link SDK calls shape
  // varies over time so we keep it loose. Do NOT trust any field for
  // auth — the backend scopes writes by `current_user.id`.
  metadata: Record<string, unknown>;
}

export interface PlaidExchangeResponse {
  connection_id: number;
  item_id: string;
  institution_name: string;
  account_ids: number[];
  status: string;
}

export interface PlaidConnectionOut {
  id: number;
  item_id: string;
  institution_id: string;
  institution_name: string;
  status: string;
  environment: string;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface PlaidConnectionsList {
  connections: PlaidConnectionOut[];
}

export interface PlaidDisconnectResponse {
  id: number;
  status: string;
}

export async function createLinkToken(): Promise<PlaidLinkTokenResponse> {
  const res = await api.post<PlaidLinkTokenResponse>('/plaid/link_token');
  return res.data;
}

export async function exchangePublicToken(
  body: PlaidExchangeRequest,
): Promise<PlaidExchangeResponse> {
  const res = await api.post<PlaidExchangeResponse>('/plaid/exchange', body);
  return res.data;
}

export async function listPlaidConnections(): Promise<PlaidConnectionsList> {
  const res = await api.get<PlaidConnectionsList>('/plaid/connections');
  return res.data;
}

export async function disconnectPlaid(
  connectionId: number,
): Promise<PlaidDisconnectResponse> {
  const res = await api.delete<PlaidDisconnectResponse>(
    `/plaid/connections/${connectionId}`,
  );
  return res.data;
}

export const plaidApi = {
  createLinkToken,
  exchangePublicToken,
  listConnections: listPlaidConnections,
  disconnect: disconnectPlaid,
};
