import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, cleanup } from '@/test/testing-library';
import DeployHealthCard from '../DeployHealthCard';
import { renderWithProviders } from '../../../test/render';
import type { DeployHealthDetailResponse } from '../../../types/adminHealth';

const mockUseDeployHealth = vi.fn();

vi.mock('../../../hooks/useDeployHealth', () => ({
  __esModule: true,
  default: (...args: unknown[]) => mockUseDeployHealth(...args),
}));

vi.mock('../../../hooks/useUserPreferences', () => ({
  __esModule: true,
  useUserPreferences: () => ({ timezone: 'UTC' }),
  default: () => ({ timezone: 'UTC' }),
}));

beforeEach(() => {
  mockUseDeployHealth.mockReset();
});

afterEach(() => cleanup());

function makeData(overrides: Partial<DeployHealthDetailResponse> = {}): DeployHealthDetailResponse {
  return {
    status: 'green',
    reason: 'all monitored Render services deployed cleanly in last 24h',
    services_configured: 2,
    consecutive_failures_max: 0,
    failures_24h_total: 0,
    services: [
      {
        service_id: 'srv-api',
        service_slug: 'axiomfolio-api',
        service_type: 'web_service',
        status: 'green',
        reason: 'all recent deploys healthy',
        last_status: 'live',
        last_deploy_sha: 'deadbeefdeadbeef',
        last_deploy_at: '2026-04-21T04:11:05Z',
        last_live_sha: 'deadbeefdeadbeef',
        last_live_at: '2026-04-21T04:12:50Z',
        consecutive_failures: 0,
        failures_24h: 0,
        deploys_24h: 1,
        in_flight: false,
      },
    ],
    events: [
      {
        id: 1,
        service_id: 'srv-api',
        service_slug: 'axiomfolio-api',
        service_type: 'web_service',
        deploy_id: 'd-1',
        status: 'live',
        trigger: 'new_commit',
        commit_sha: 'deadbeefdeadbeef',
        commit_message: 'feat: xyz',
        render_created_at: '2026-04-21T04:11:05Z',
        render_finished_at: '2026-04-21T04:12:50Z',
        duration_seconds: 105,
        is_poll_error: false,
        poll_error_message: null,
        polled_at: '2026-04-21T04:13:00Z',
      },
    ],
    checked_at: '2026-04-21T04:13:00Z',
    ...overrides,
  };
}

describe('DeployHealthCard', () => {
  it('renders loading state', () => {
    mockUseDeployHealth.mockReturnValue({
      data: null,
      isLoading: true,
      isError: false,
      error: null,
      refresh: vi.fn(),
      poll: vi.fn(),
      polling: false,
    });
    renderWithProviders(<DeployHealthCard />);
    expect(screen.getByText(/Loading deploy telemetry/i)).toBeInTheDocument();
  });

  it('renders error state', () => {
    mockUseDeployHealth.mockReturnValue({
      data: null,
      isLoading: false,
      isError: true,
      error: new Error('Network down'),
      refresh: vi.fn(),
      poll: vi.fn(),
      polling: false,
    });
    renderWithProviders(<DeployHealthCard />);
    expect(screen.getByText(/Network down/)).toBeInTheDocument();
  });

  it('renders empty state when no services configured', () => {
    mockUseDeployHealth.mockReturnValue({
      data: {
        status: 'yellow',
        reason: 'no render services configured',
        services_configured: 0,
        consecutive_failures_max: 0,
        failures_24h_total: 0,
        services: [],
        events: [],
        checked_at: '2026-04-21T04:13:00Z',
      },
      isLoading: false,
      isError: false,
      error: null,
      refresh: vi.fn(),
      poll: vi.fn(),
      polling: false,
    });
    renderWithProviders(<DeployHealthCard />);
    expect(
      screen.getByText(/No Render services configured/i),
    ).toBeInTheDocument();
  });

  it('renders green data state', () => {
    mockUseDeployHealth.mockReturnValue({
      data: makeData(),
      isLoading: false,
      isError: false,
      error: null,
      refresh: vi.fn(),
      poll: vi.fn(),
      polling: false,
    });
    renderWithProviders(<DeployHealthCard />);
    expect(screen.getByText('Deploy Health')).toBeInTheDocument();
    expect(screen.getAllByText(/GREEN/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText('axiomfolio-api').length).toBeGreaterThan(0);
    expect(screen.getByText(/Recent deploy events/i)).toBeInTheDocument();
  });

  it('renders red state when consecutive failures breach threshold', () => {
    mockUseDeployHealth.mockReturnValue({
      data: makeData({
        status: 'red',
        reason: 'axiomfolio-api: 7 consecutive failed deploys',
        consecutive_failures_max: 7,
        failures_24h_total: 7,
        services: [
          {
            service_id: 'srv-api',
            service_slug: 'axiomfolio-api',
            service_type: 'web_service',
            status: 'red',
            reason: '7 consecutive failed deploys (threshold 3)',
            last_status: 'build_failed',
            last_deploy_sha: 'beefbeefbeefbeef',
            last_deploy_at: '2026-04-21T04:11:05Z',
            last_live_sha: null,
            last_live_at: null,
            consecutive_failures: 7,
            failures_24h: 7,
            deploys_24h: 7,
            in_flight: false,
          },
        ],
      }),
      isLoading: false,
      isError: false,
      error: null,
      refresh: vi.fn(),
      poll: vi.fn(),
      polling: false,
    });
    renderWithProviders(<DeployHealthCard />);
    expect(screen.getAllByText(/RED/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/7 consecutive failed deploys/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/7 in a row/i, { exact: false })).toBeInTheDocument();
  });
});
