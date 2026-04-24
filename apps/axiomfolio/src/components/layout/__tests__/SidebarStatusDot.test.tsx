import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, cleanup, screen } from '@/test/testing-library';

import SidebarStatusDot from '../SidebarStatusDot';
import type { AdminHealthResponse } from '@/types/adminHealth';
import { TooltipProvider } from '@/components/ui/tooltip';

type HookResult = {
  health: AdminHealthResponse | null;
  loading: boolean;
  isError: boolean;
  refresh: () => Promise<void>;
};

let mockedHealth: HookResult = {
  health: null,
  loading: true,
  isError: false,
  refresh: vi.fn().mockResolvedValue(undefined),
};

vi.mock('@/hooks/useAdminHealth', () => ({
  __esModule: true,
  default: () => mockedHealth,
}));

function renderDot(isAdmin: boolean) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TooltipProvider>
          <SidebarStatusDot isAdmin={isAdmin} />
        </TooltipProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeHealth(overrides: Partial<AdminHealthResponse> = {}): AdminHealthResponse {
  const base: AdminHealthResponse = {
    composite_status: 'green',
    composite_reason: 'ok',
    dimensions: {
      coverage: { status: 'green', category: 'market' } as any,
      stage_quality: { status: 'green', category: 'market' } as any,
      jobs: { status: 'green', category: 'infra' } as any,
      audit: { status: 'green', category: 'market' } as any,
      regime: { status: 'green', category: 'market' } as any,
      fundamentals: { status: 'green', category: 'market' } as any,
      portfolio_sync: { status: 'green', category: 'broker' } as any,
      ibkr_gateway: { status: 'green', category: 'broker' } as any,
      data_accuracy: { status: 'green', category: 'market' } as any,
    },
    task_runs: {},
    thresholds: {},
    checked_at: '2026-04-22T00:00:00Z',
  };
  return { ...base, ...overrides };
}

describe('SidebarStatusDot', () => {
  beforeEach(() => {
    cleanup();
    mockedHealth = {
      health: null,
      loading: true,
      isError: false,
      refresh: vi.fn().mockResolvedValue(undefined),
    };
  });

  it('returns null for non-admin users even when health is available', () => {
    mockedHealth = {
      health: makeHealth(),
      loading: false,
      isError: false,
      refresh: vi.fn(),
    };
    const { container } = renderDot(false);
    expect(container.querySelector('[data-testid="sidebar-status-dot"]')).toBeNull();
  });

  it('renders nothing while loading (admin + pending) — never a silent green dot', () => {
    mockedHealth = { health: null, loading: true, isError: false, refresh: vi.fn() };
    const { container } = renderDot(true);
    expect(container.querySelector('[data-testid="sidebar-status-dot"]')).toBeNull();
  });

  it('renders a green dot when every dimension is healthy', () => {
    mockedHealth = {
      health: makeHealth(),
      loading: false,
      isError: false,
      refresh: vi.fn(),
    };
    renderDot(true);
    const dot = screen.getByTestId('sidebar-status-dot');
    expect(dot.getAttribute('data-dot-color')).toBe('green');
  });

  it('renders an amber dot when at least one dimension is stale / yellow', () => {
    mockedHealth = {
      health: makeHealth({
        composite_status: 'yellow',
        dimensions: {
          ...makeHealth().dimensions,
          coverage: { status: 'yellow', category: 'market' } as any,
        },
      }),
      loading: false,
      isError: false,
      refresh: vi.fn(),
    };
    renderDot(true);
    const dot = screen.getByTestId('sidebar-status-dot');
    expect(dot.getAttribute('data-dot-color')).toBe('amber');
  });

  it('renders a red dot when any dimension is error / red', () => {
    mockedHealth = {
      health: makeHealth({
        composite_status: 'red',
        dimensions: {
          ...makeHealth().dimensions,
          jobs: { status: 'red', category: 'infra' } as any,
        },
      }),
      loading: false,
      isError: false,
      refresh: vi.fn(),
    };
    renderDot(true);
    const dot = screen.getByTestId('sidebar-status-dot');
    expect(dot.getAttribute('data-dot-color')).toBe('red');
  });

  it('renders a muted grey "status unknown" dot on fetch error — never defaults to green', () => {
    mockedHealth = {
      health: null,
      loading: false,
      isError: true,
      refresh: vi.fn(),
    };
    renderDot(true);
    const dot = screen.getByTestId('sidebar-status-dot');
    expect(dot.getAttribute('data-dot-color')).toBe('grey');
    expect(dot.getAttribute('aria-label')).toMatch(/status unknown/i);
  });

  it('advisory dimensions do not escalate the dot colour', () => {
    mockedHealth = {
      health: makeHealth({
        dimensions: {
          ...makeHealth().dimensions,
          fundamentals: { status: 'red', category: 'market', advisory: true } as any,
        },
      }),
      loading: false,
      isError: false,
      refresh: vi.fn(),
    };
    renderDot(true);
    const dot = screen.getByTestId('sidebar-status-dot');
    expect(dot.getAttribute('data-dot-color')).toBe('green');
  });
});
