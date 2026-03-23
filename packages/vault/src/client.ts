import type {
  VaultConfig,
  VaultResponse,
  SecretMetadata,
  SecretWithValue,
  UpsertSecretParams,
} from "./types";

export class VaultClient {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(config: VaultConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, "");
    this.headers = buildAuthHeaders(config);
  }

  /**
   * Create from environment variables.
   * Reads STUDIO_URL (default: https://paperworklabs.com), SECRETS_API_KEY,
   * ADMIN_EMAILS, ADMIN_ACCESS_PASSWORD.
   */
  static fromEnv(): VaultClient {
    const baseUrl = process.env.STUDIO_URL ?? "https://paperworklabs.com";
    const apiKey = process.env.SECRETS_API_KEY?.trim();
    const adminEmail = process.env.ADMIN_EMAILS?.split(",")[0]?.trim();
    const adminPass = process.env.ADMIN_ACCESS_PASSWORD?.trim();

    return new VaultClient({
      baseUrl,
      apiKey: apiKey || undefined,
      basicAuth:
        adminEmail && adminPass
          ? { email: adminEmail, password: adminPass }
          : undefined,
    });
  }

  async list(): Promise<SecretMetadata[]> {
    const res = await this.fetch<SecretMetadata[]>("/api/secrets");
    return res.data;
  }

  async get(id: string): Promise<SecretWithValue> {
    const res = await this.fetch<SecretWithValue>(`/api/secrets/${id}`);
    return res.data;
  }

  /**
   * Retrieve a secret by name. Lists all secrets, finds by name, then fetches value.
   * Returns null if not found.
   */
  async getByName(name: string): Promise<string | null> {
    const secrets = await this.list();
    const match = secrets.find((s) => s.name === name);
    if (!match) return null;
    const full = await this.get(match.id);
    return full.value;
  }

  async upsert(params: UpsertSecretParams): Promise<SecretMetadata> {
    const res = await this.fetch<SecretMetadata>("/api/secrets", {
      method: "POST",
      body: JSON.stringify(params),
    });
    return res.data;
  }

  async delete(id: string): Promise<void> {
    await this.fetch(`/api/secrets/${id}`, { method: "DELETE" });
  }

  async export(): Promise<string> {
    const url = `${this.baseUrl}/api/secrets/export`;
    const res = await fetch(url, { headers: this.headers });
    if (!res.ok) {
      throw new VaultError(`Export failed: HTTP ${res.status}`, res.status);
    }
    return res.text();
  }

  private async fetch<T>(
    path: string,
    init?: RequestInit,
  ): Promise<VaultResponse<T>> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...init,
      headers: {
        ...this.headers,
        "Content-Type": "application/json",
        ...(init?.headers as Record<string, string>),
      },
    });

    const json = (await res.json()) as VaultResponse<T>;
    if (!res.ok || !json.success) {
      throw new VaultError(
        json.error ?? `Vault request failed: HTTP ${res.status}`,
        res.status,
      );
    }
    return json;
  }
}

export class VaultError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "VaultError";
  }
}

function buildAuthHeaders(config: VaultConfig): Record<string, string> {
  if (config.apiKey) {
    return { Authorization: `Bearer ${config.apiKey}` };
  }
  if (config.basicAuth) {
    const encoded = Buffer.from(
      `${config.basicAuth.email}:${config.basicAuth.password}`,
    ).toString("base64");
    return { Authorization: `Basic ${encoded}` };
  }
  throw new VaultError("No auth configured: set apiKey or basicAuth", 401);
}
