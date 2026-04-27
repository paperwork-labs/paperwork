import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor, cleanup } from '@/test/testing-library';
import { renderWithProviders } from '@/test/render';
import { CommandPalette } from '@/components/cmdk/CommandPalette';
import { actionRegistry, RECENT_ACTIONS_STORAGE_KEY } from '@/lib/actions';

const navigateMock = vi.hoisted(() => vi.fn());

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

function PaletteHarness(props: { initialOpen?: boolean }) {
  const [open, setOpen] = React.useState(props.initialOpen ?? false);
  return <CommandPalette open={open} onOpenChange={setOpen} />;
}

describe('CommandPalette', () => {
  beforeEach(() => {
    navigateMock.mockClear();
    actionRegistry.clear();
    localStorage.removeItem(RECENT_ACTIONS_STORAGE_KEY);
    actionRegistry.register({
      id: 'nav.home',
      label: 'Go Home',
      section: 'navigation',
      keywords: ['dashboard'],
      run: (ctx) => ctx.navigate('/'),
    });
    actionRegistry.register({
      id: 'nav.portfolio',
      label: 'Go Portfolio',
      section: 'navigation',
      keywords: ['positions'],
      run: (ctx) => ctx.navigate('/portfolio'),
    });
  });

  afterEach(() => {
    cleanup();
    actionRegistry.clear();
    localStorage.removeItem(RECENT_ACTIONS_STORAGE_KEY);
  });

  it('opens on Ctrl+K / Meta+K and closes on Escape', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaletteHarness />);
    await user.keyboard('{Control>}k{/Control}');
    expect(await screen.findByPlaceholderText(/Search pages/i)).toBeInTheDocument();
    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/Search pages/i)).not.toBeInTheDocument();
    });
  });

  it('filters when typing "port" and runs handler on Enter', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaletteHarness initialOpen />);
    const input = await screen.findByPlaceholderText(/Search pages/i);
    await user.clear(input);
    await user.type(input, 'port');
    expect(screen.getByText('Go Portfolio')).toBeInTheDocument();
    expect(screen.queryByText('Go Home')).not.toBeInTheDocument();
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith('/portfolio');
    });
  });

  it('persists recent actions and shows them when reopening', async () => {
    const user = userEvent.setup();
    renderWithProviders(<PaletteHarness initialOpen />);
    const input = await screen.findByPlaceholderText(/Search pages/i);
    await user.clear(input);
    await user.type(input, 'port');
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem(RECENT_ACTIONS_STORAGE_KEY) || '[]')).toContain('nav.portfolio');
    });
    await user.keyboard('{Control>}k{/Control}');
    expect((await screen.findAllByRole('option', { name: /Go Portfolio/i })).length).toBeGreaterThanOrEqual(1);
  });
});
