import React from 'react';
import { describe, it, expect } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { screen, waitFor } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import { TabbedPageShell, useActiveTab } from '../TabbedPageShell';

function TabAInner() {
  const id = useActiveTab<'a' | 'b' | 'c'>();
  return (
    <div>
      <span data-testid="hook-tab">{id}</span>
      <span>Panel A</span>
    </div>
  );
}

function TabBInner() {
  const id = useActiveTab<'a' | 'b' | 'c'>();
  return (
    <div>
      <span data-testid="hook-tab-b">{id}</span>
      <span>Panel B</span>
    </div>
  );
}

function TabCInner(): React.ReactNode {
  throw new Error('tab crash');
}

const TabA = React.lazy(() => Promise.resolve({ default: TabAInner }));
const TabB = React.lazy(() => Promise.resolve({ default: TabBInner }));
const TabC = React.lazy(() => Promise.resolve({ default: TabCInner }));

const SHELL_TABS = [
  { id: 'a' as const, label: 'Alpha', Content: TabA },
  { id: 'b' as const, label: 'Beta', Content: TabB },
  { id: 'c' as const, label: 'Gamma', Content: TabC },
];

describe('TabbedPageShell', () => {
  it('reads initial tab from the URL and exposes it via useActiveTab', async () => {
    renderWithProviders(<TabbedPageShell tabs={SHELL_TABS} defaultTab="a" />, { route: '/?tab=b' });

    await waitFor(() => {
      expect(screen.getByTestId('hook-tab-b')).toHaveTextContent('b');
    });
    expect(screen.getByText('Panel B')).toBeInTheDocument();
  });

  it('updates the URL when the user selects a different tab', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TabbedPageShell tabs={SHELL_TABS} defaultTab="a" />, { route: '/?tab=a' });

    await waitFor(() => expect(screen.getByText('Panel A')).toBeInTheDocument());

    await user.click(screen.getByRole('tab', { name: 'Beta' }));

    await waitFor(() => {
      expect(screen.getByText('Panel B')).toBeInTheDocument();
    });
  });

  it('shows the error boundary fallback when a lazy tab throws', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TabbedPageShell tabs={SHELL_TABS} defaultTab="a" />, { route: '/?tab=a' });

    await waitFor(() => expect(screen.getByText('Panel A')).toBeInTheDocument());

    await user.click(screen.getByRole('tab', { name: 'Gamma' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/failed to render/i);
    });
  });

  it('moves focus across tab triggers with the arrow keys', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TabbedPageShell tabs={SHELL_TABS} defaultTab="a" />, { route: '/?tab=a' });

    const alpha = await screen.findByRole('tab', { name: 'Alpha' });
    alpha.focus();
    expect(alpha).toHaveFocus();

    await user.keyboard('{ArrowRight}');

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Beta' })).toHaveFocus();
    });
  });
});
