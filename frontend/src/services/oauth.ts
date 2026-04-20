/**
 * OAuth broker API client (read/list/initiate/callback/revoke).
 *
 * Mirrors the backend FastAPI surface at `/api/v1/oauth/*`. Coordinated
 * intentionally with `feat/v1-broker-connection-hub`: that PR owns the
 * UI and re-exports / consumes these types. Keep the wire format stable.
 */
import api from './api';

export type OAuthBroker =
  | 'etrade_sandbox'
  | 'etrade'
  | 'schwab'
  | 'fidelity'
  | 'tastytrade'
  | 'ibkr'
  | 'alpaca'
  | 'robinhood';

export type OAuthConnectionStatus =
  | 'PENDING'
  | 'ACTIVE'
  | 'EXPIRED'
  | 'REVOKED'
  | 'REFRESH_FAILED'
  | 'ERROR';

export interface OAuthConnection {
  id: number;
  broker: string;
  environment: 'sandbox' | 'live';
  status: OAuthConnectionStatus;
  provider_account_id: string | null;
  token_expires_at: string | null;
  last_refreshed_at: string | null;
  last_error: string | null;
  rotation_count: number;
  created_at: string;
  updated_at: string;
}

export interface OAuthInitiateResponse {
  broker: string;
  state: string;
  authorize_url: string;
  expires_in_seconds: number;
}

export interface OAuthCallbackResponse {
  connection: OAuthConnection;
}

export interface OAuthConnectionsList {
  connections: OAuthConnection[];
}

export interface OAuthBrokersResponse {
  brokers: string[];
}

export interface OAuthRevokeResponse {
  id: number;
  status: OAuthConnectionStatus;
}

/** Discover which brokers the backend is configured to handle. */
export async function listBrokers(): Promise<OAuthBrokersResponse> {
  const res = await api.get<OAuthBrokersResponse>('/oauth/brokers');
  return res.data;
}

/** Begin an OAuth flow. The caller redirects the user to `authorize_url`. */
export async function initiate(
  broker: OAuthBroker | string,
  callbackUrl: string,
): Promise<OAuthInitiateResponse> {
  const res = await api.post<OAuthInitiateResponse>(
    `/oauth/${broker}/initiate`,
    { callback_url: callbackUrl },
  );
  return res.data;
}

/**
 * Exchange the OAuth code (or OAuth 1.0a verifier) for tokens. The backend
 * decrypts/encrypts everything; the frontend only ever sees status.
 */
export async function callback(
  broker: OAuthBroker | string,
  state: string,
  code: string,
): Promise<OAuthCallbackResponse> {
  const res = await api.post<OAuthCallbackResponse>(
    `/oauth/${broker}/callback`,
    { state, code },
  );
  return res.data;
}

/** List the current user's OAuth broker connections. */
export async function listConnections(): Promise<OAuthConnectionsList> {
  const res = await api.get<OAuthConnectionsList>('/oauth/connections');
  return res.data;
}

/** Revoke + forget a stored connection (best-effort provider revoke). */
export async function revoke(connectionId: number): Promise<OAuthRevokeResponse> {
  const res = await api.delete<OAuthRevokeResponse>(
    `/oauth/connections/${connectionId}`,
  );
  return res.data;
}

export const oauthApi = {
  listBrokers,
  initiate,
  callback,
  listConnections,
  revoke,
};

export default oauthApi;
