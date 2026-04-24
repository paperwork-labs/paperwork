import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/render';

// Hoisted mocks for the Plaid SDK and the plaid API service so the module
// factory callbacks see initialised references.
const usePlaidLinkMock = vi.hoisted(() =>
  vi.fn((_args?: unknown) => ({
    open: vi.fn() as () => void,
    ready: true,
  })),
);
const plaidApiMock = vi.hoisted(() => ({
  createLinkToken: vi.fn(),
  exchangePublicToken: vi.fn(),
  listConnections: vi.fn(),
  disconnect: vi.fn(),
}));

vi.mock('react-plaid-link', () => ({
  usePlaidLink: usePlaidLinkMock,
}));

vi.mock('@/services/plaid', () => ({
  plaidApi: plaidApiMock,
  createLinkToken: plaidApiMock.createLinkToken,
  exchangePublicToken: plaidApiMock.exchangePublicToken,
  listPlaidConnections: plaidApiMock.listConnections,
  disconnectPlaid: plaidApiMock.disconnect,
}));

// Import AFTER the mocks so PlaidLink picks up the mocked modules.
import PlaidLink from '../PlaidLink';

describe('PlaidLink', () => {
  beforeEach(() => {
    usePlaidLinkMock.mockReset();
    plaidApiMock.createLinkToken.mockReset();
    plaidApiMock.exchangePublicToken.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the connect button in the idle state', () => {
    usePlaidLinkMock.mockReturnValue({ open: vi.fn(), ready: false });
    renderWithProviders(<PlaidLink />);
    expect(
      screen.getByRole('button', { name: /connect with plaid/i }),
    ).toBeInTheDocument();
  });

  it('mints a link_token and transitions to link-ready on click', async () => {
    const openPlaidLink = vi.fn();
    usePlaidLinkMock.mockReturnValue({ open: openPlaidLink, ready: true });
    plaidApiMock.createLinkToken.mockResolvedValueOnce({
      link_token: 'link-sandbox-1',
      expiration_seconds: 14400,
    });

    const onStatusChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<PlaidLink onStatusChange={onStatusChange} />);

    await user.click(screen.getByRole('button', { name: /connect with plaid/i }));

    await waitFor(() =>
      expect(plaidApiMock.createLinkToken).toHaveBeenCalledTimes(1),
    );
    // Status should pass through preparing -> link-ready.
    await waitFor(() => expect(onStatusChange).toHaveBeenCalledWith('link-ready'));
    // And the SDK hook should be invoked to auto-open Link.
    await waitFor(() => expect(openPlaidLink).toHaveBeenCalled());
  });

  it('surfaces link_token errors without silent fallback', async () => {
    usePlaidLinkMock.mockReturnValue({ open: vi.fn(), ready: false });
    plaidApiMock.createLinkToken.mockRejectedValueOnce({
      response: { data: { detail: 'Plaid integration is not configured.' } },
    });

    const user = userEvent.setup();
    renderWithProviders(<PlaidLink />);
    await user.click(screen.getByRole('button', { name: /connect with plaid/i }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/plaid integration is not configured/i);
  });

  it('calls onConnected and shows success after exchange', async () => {
    // Drive onSuccess callback by capturing the usePlaidLink args.
    let onSuccessArg: ((t: string, m: Record<string, unknown>) => void) | null = null;
    usePlaidLinkMock.mockImplementation((args: unknown) => {
      const a = args as { onSuccess?: typeof onSuccessArg };
      onSuccessArg = a.onSuccess ?? null;
      return { open: vi.fn(), ready: true };
    });
    plaidApiMock.createLinkToken.mockResolvedValueOnce({
      link_token: 'link-token-ok',
      expiration_seconds: 14400,
    });
    plaidApiMock.exchangePublicToken.mockResolvedValueOnce({
      connection_id: 77,
      item_id: 'item-ok',
      institution_name: 'Fidelity',
      account_ids: [101],
      status: 'active',
    });

    const onConnected = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<PlaidLink onConnected={onConnected} />);
    await user.click(screen.getByRole('button', { name: /connect with plaid/i }));

    // Wait for the link_token mutation to finish so onSuccessArg is wired.
    await waitFor(() => expect(onSuccessArg).not.toBeNull());
    onSuccessArg!('public-sandbox-ok', { institution: { name: 'Fidelity' } });

    await waitFor(() =>
      expect(plaidApiMock.exchangePublicToken).toHaveBeenCalledWith({
        public_token: 'public-sandbox-ok',
        metadata: { institution: { name: 'Fidelity' } },
      }),
    );
    await waitFor(() =>
      expect(onConnected).toHaveBeenCalledWith(77, 'Fidelity'),
    );
    await waitFor(() =>
      expect(screen.getByRole('button')).toHaveTextContent(/connected/i),
    );
  });
});
