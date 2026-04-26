/**
 * Data Privacy (GDPR) client.
 *
 * Wraps the per-tenant `/api/v1/me/data-export` and
 * `/api/v1/me/account-delete` endpoints. The plaintext delete
 * confirmation token is shown to the user exactly once and never
 * persisted client-side.
 */

import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '/api/v1';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('qm_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export type GDPRJobStatus =
  | 'pending'
  | 'confirmed'
  | 'running'
  | 'completed'
  | 'failed'
  | 'expired';

export interface ExportJob {
  id: number;
  status: GDPRJobStatus;
  requested_at: string;
  completed_at?: string | null;
  download_url?: string | null;
  expires_at?: string | null;
  bytes_written?: number | null;
  error_message?: string | null;
}

export interface DeleteJob {
  id: number;
  status: GDPRJobStatus;
  requested_at: string;
  confirmed_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface StartDeleteResponse {
  job: DeleteJob;
  confirmation_token: string;
}

export const dataPrivacyApi = {
  startExport: async (): Promise<ExportJob> => {
    const { data } = await client.post<ExportJob>('/me/data-export');
    return data;
  },

  getExportJob: async (jobId: number): Promise<ExportJob> => {
    const { data } = await client.get<ExportJob>(`/me/data-export/${jobId}`);
    return data;
  },

  /** Returns the absolute URL the user should hit to download the ZIP.
   *  For S3-published jobs this is the presigned URL. For local-storage
   *  jobs we point at the API's streaming endpoint. */
  resolveDownloadUrl: (job: ExportJob): string | null => {
    if (!job.download_url) return null;
    if (job.download_url.startsWith('local://')) {
      return `${API_BASE_URL}/me/data-export/${job.id}/download`;
    }
    return job.download_url;
  },

  startDelete: async (): Promise<StartDeleteResponse> => {
    const { data } = await client.post<StartDeleteResponse>(
      '/me/account-delete',
    );
    return data;
  },

  confirmDelete: async (
    jobId: number,
    confirmationToken: string,
  ): Promise<DeleteJob> => {
    const { data } = await client.post<DeleteJob>(
      `/me/account-delete/${jobId}/confirm`,
      { confirmation_token: confirmationToken },
    );
    return data;
  },

  getDeleteJob: async (jobId: number): Promise<DeleteJob> => {
    const { data } = await client.get<DeleteJob>(`/me/account-delete/${jobId}`);
    return data;
  },
};
