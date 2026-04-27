/**
 * API for signed public chart share links (POST) and public bars fetch (GET).
 */
import api from "./api";

export interface CreateChartShareBody {
  symbol: string;
  period?: string;
  indicators?: string[];
}

export interface CreateChartShareResponse {
  token: string;
  url: string;
}

export interface ShareChartBarsResponse {
  symbol: string;
  period: string;
  interval: string;
  data_source: string;
  bars: Array<{
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }>;
  indicators: string[];
}

export async function createChartShareLink(
  body: CreateChartShareBody,
): Promise<CreateChartShareResponse> {
  const { data } = await api.post<CreateChartShareResponse>("/share/chart", body);
  return data;
}

export async function fetchPublicShareChartBars(
  token: string,
): Promise<ShareChartBarsResponse> {
  const { data } = await api.get<ShareChartBarsResponse>(
    `/share/chart/${encodeURIComponent(token)}/bars`,
  );
  return data;
}
