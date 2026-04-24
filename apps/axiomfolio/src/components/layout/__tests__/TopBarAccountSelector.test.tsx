import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import TopBarAccountSelector from '../TopBarAccountSelector';
import { renderWithProviders } from '../../../test/render';
import type { BrokerAccount } from '../../../context/AccountContext';

type BalancesMock = {
  data: unknown[] | undefined;
  isPending: boolean;
  isError: boolean;
};

let mockedAccountContext: {
  accounts: BrokerAccount[];
  loading: boolean;
  error: string | null;
  selected: string;
  setSelected: ReturnType<typeof vi.fn>;
  refetch: ReturnType<typeof vi.fn>;
};

let mockedBalances: BalancesMock;

vi.mock('../../../context/AccountContext', async () => {
  return {
    useAccountContext: () => mockedAccountContext,
  };
});

vi.mock('@/hooks/usePortfolio', () => ({
  useAccountBalances: () => mockedBalances,
}));

vi.mock('@/hooks/useUserPreferences', () => ({
  useUserPreferences: () => ({ currency: 'USD' }),
}));

function makeAccount(overrides: Partial<BrokerAccount> = {}): BrokerAccount {
  return {
    id: 1,
    account_number: 'U1234567',
    account_name: 'Taxable Brokerage',
    account_type: 'MARGIN',
    broker: 'IBKR',
    is_enabled: true,
    ...overrides,
  };
}

function setDesktopViewport(): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe('TopBarAccountSelector', () => {
  beforeEach(() => {
    setDesktopViewport();
    mockedAccountContext = {
      accounts: [],
      loading: false,
      error: null,
      selected: 'all',
      setSelected: vi.fn(),
      refetch: vi.fn(),
    };
    mockedBalances = {
      data: [],
      isPending: false,
      isError: false,
    };
  });

  it('renders "All accounts" on the trigger when nothing is selected', () => {
    mockedAccountContext.accounts = [
      makeAccount(),
      makeAccount({ id: 2, account_number: 'U2222222', broker: 'SCHWAB' }),
    ];
    renderWithProviders(<TopBarAccountSelector />);
    const trigger = screen.getByRole('button', { name: /account filter: all accounts/i });
    expect(trigger).toBeInTheDocument();
    // Count badge shown when > 1 account.
    expect(trigger).toHaveTextContent('2');
  });

  it('shows the selected account nickname on the trigger (truncated)', () => {
    mockedAccountContext.accounts = [
      makeAccount({
        id: 7,
        account_number: 'U9999999',
        account_name: 'A Really Long Taxable Brokerage Nickname That Should Truncate',
        broker: 'IBKR',
      }),
    ];
    mockedAccountContext.selected = 'U9999999';
    renderWithProviders(<TopBarAccountSelector />);
    const trigger = screen.getByRole('button', { name: /account filter/i });
    // Truncated to 20 chars with an ellipsis.
    expect(trigger.textContent ?? '').toMatch(/A Really Long Taxab…/);
  });

  it('renders a loading skeleton row while the context is loading', async () => {
    mockedAccountContext.loading = true;
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);
    await user.click(screen.getByRole('button', { name: /account filter/i }));
    expect(await screen.findByRole('status', { name: /loading accounts/i })).toBeInTheDocument();
  });

  it('renders an inline retry for the error state', async () => {
    mockedAccountContext.error = 'Server 500';
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);
    await user.click(screen.getByRole('button', { name: /account filter/i }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/couldn’t load accounts/i);
    expect(alert).toHaveTextContent('Server 500');

    await user.click(screen.getByRole('button', { name: /retry/i }));
    expect(mockedAccountContext.refetch).toHaveBeenCalledTimes(1);
  });

  it('shows the empty state with a connect broker link when no accounts exist', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);
    await user.click(screen.getByRole('button', { name: /account filter/i }));
    expect(await screen.findByText(/no brokers connected/i)).toBeInTheDocument();
    const connectLink = screen.getByRole('link', { name: /connect broker/i });
    expect(connectLink).toHaveAttribute('href', '/settings/connections');
  });

  it('renders data rows grouped by broker and selecting one calls setSelected', async () => {
    mockedAccountContext.accounts = [
      makeAccount({ id: 1, account_number: 'U111', broker: 'IBKR', account_name: 'IBKR Margin' }),
      makeAccount({ id: 2, account_number: 'S222', broker: 'SCHWAB', account_name: 'Schwab IRA', account_type: 'IRA' }),
    ];
    mockedBalances = {
      data: [
        { account_id: 1, account_number: 'U111', broker: 'IBKR', net_liquidation: 12345 },
        { account_id: 2, account_number: 'S222', broker: 'SCHWAB', net_liquidation: 67890 },
      ],
      isPending: false,
      isError: false,
    };
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);
    await user.click(screen.getByRole('button', { name: /account filter/i }));

    expect(await screen.findByText('IBKR Margin')).toBeInTheDocument();
    expect(screen.getByText('Schwab IRA')).toBeInTheDocument();
    // NAV figures rendered as formatted currency (not "0" when loaded).
    expect(screen.getByLabelText(/net liquidation \$12,345/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/net liquidation \$67,890/i)).toBeInTheDocument();

    await user.click(screen.getByText('Schwab IRA'));
    expect(mockedAccountContext.setSelected).toHaveBeenCalledWith('S222');
  });

  it('renders em-dash for NAV while balances are pending (never silent zero)', async () => {
    mockedAccountContext.accounts = [makeAccount({ id: 1, account_number: 'U111' })];
    mockedBalances = { data: undefined, isPending: true, isError: false };
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);
    await user.click(screen.getByRole('button', { name: /account filter/i }));
    expect(await screen.findByLabelText(/balance loading/i)).toBeInTheDocument();
  });

  it('selects "All accounts" from the dropdown', async () => {
    mockedAccountContext.accounts = [makeAccount({ id: 1, account_number: 'U111' })];
    mockedAccountContext.selected = 'U111';
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);
    await user.click(screen.getByRole('button', { name: /account filter/i }));
    await user.click(await screen.findByTestId('tbas-all-accounts'));
    expect(mockedAccountContext.setSelected).toHaveBeenCalledWith('all');
  });

  it('shows a search input only when there are more than five accounts and filters the list', async () => {
    mockedAccountContext.accounts = Array.from({ length: 7 }, (_, i) =>
      makeAccount({
        id: i + 1,
        account_number: `U${100 + i}`,
        account_name: i === 3 ? 'Special Joint' : `Account ${i + 1}`,
        broker: i % 2 === 0 ? 'IBKR' : 'SCHWAB',
      })
    );
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);
    await user.click(screen.getByRole('button', { name: /account filter/i }));

    const search = await screen.findByLabelText(/search accounts/i);
    expect(search).toBeInTheDocument();

    await user.type(search, 'special');

    await waitFor(() => {
      expect(screen.getByText('Special Joint')).toBeInTheDocument();
      expect(screen.queryByText('Account 1')).not.toBeInTheDocument();
    });
  });

  it('opens and closes the dropdown via keyboard (Enter opens, Esc closes)', async () => {
    mockedAccountContext.accounts = [makeAccount({ id: 1, account_number: 'U111' })];
    const user = userEvent.setup();
    renderWithProviders(<TopBarAccountSelector />);

    const trigger = screen.getByRole('button', { name: /account filter/i });
    trigger.focus();
    await user.keyboard('{Enter}');
    expect(await screen.findByTestId('tbas-all-accounts')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByTestId('tbas-all-accounts')).not.toBeInTheDocument();
    });
  });

  it('does not render a count badge when only one account exists', () => {
    mockedAccountContext.accounts = [makeAccount()];
    renderWithProviders(<TopBarAccountSelector />);
    const trigger = screen.getByRole('button', { name: /account filter/i });
    // Only the trigger chevron icon present; no count badge text matching "1"
    // next to the label.
    expect(trigger.querySelector('[aria-label="1 accounts"]')).toBeNull();
  });
});
