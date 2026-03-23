export interface VaultConfig {
  baseUrl: string;
  apiKey?: string;
  basicAuth?: { email: string; password: string };
}

export interface SecretMetadata {
  id: string;
  name: string;
  service: string;
  location?: string;
  description?: string;
  expires_at?: string | null;
  last_rotated_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SecretWithValue extends SecretMetadata {
  value: string;
}

export interface VaultResponse<T> {
  success: boolean;
  data: T;
  error?: string;
}

export interface UpsertSecretParams {
  name: string;
  value: string;
  service: string;
  location?: string;
  description?: string;
  expires_at?: string | null;
}
