import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, screen, fireEvent } from '@testing-library/react';

import { renderWithProviders } from '../../../test/render';
import TierGate from '../TierGate';

let mockedEntitlement: any = {
  tier: 'free',
  status: 'active',
  isActive: true,
  currentPeriodEnd: null,
  isLoading: false,
  isError: false,
  can: (_: string) => false,
  requireTier: (_: string) => 'pro_plus',
  raw: null,
};

vi.mock('../../../hooks/useEntitlement', () => ({
  __esModule: true,
  default: () => mockedEntitlement,
  useEntitlement: () => mockedEntitlement,
}));

describe('TierGate', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders children when feature is allowed', () => {
    mockedEntitlement = {
      ...mockedEntitlement,
      can: (key: string) => key === 'brain.native_chat',
    };
    renderWithProviders(
      <TierGate feature="brain.native_chat">
        <div>Chat panel</div>
      </TierGate>,
    );
    expect(screen.getByText('Chat panel')).toBeInTheDocument();
  });

  it('renders the default upgrade prompt when blocked', () => {
    mockedEntitlement = {
      ...mockedEntitlement,
      can: () => false,
      requireTier: () => 'pro_plus',
    };
    renderWithProviders(
      <TierGate feature="brain.native_chat">
        <div>Chat panel</div>
      </TierGate>,
    );
    expect(screen.queryByText('Chat panel')).toBeNull();
    expect(screen.getByText('Upgrade to Pro+')).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    mockedEntitlement = {
      ...mockedEntitlement,
      can: () => false,
    };
    renderWithProviders(
      <TierGate feature="brain.native_chat" fallback={<div>Custom locked</div>}>
        <div>Chat panel</div>
      </TierGate>,
    );
    expect(screen.getByText('Custom locked')).toBeInTheDocument();
  });

  it('fires onUpgradeClick with the required tier', () => {
    const onUpgrade = vi.fn();
    mockedEntitlement = {
      ...mockedEntitlement,
      can: () => false,
      requireTier: () => 'pro_plus',
    };
    renderWithProviders(
      <TierGate feature="brain.native_chat" onUpgradeClick={onUpgrade}>
        <div>Chat panel</div>
      </TierGate>,
    );
    fireEvent.click(screen.getByText('Upgrade to Pro+'));
    expect(onUpgrade).toHaveBeenCalledWith('pro_plus');
  });

  it('renders nothing while loading by default', () => {
    mockedEntitlement = {
      ...mockedEntitlement,
      isLoading: true,
      can: () => false,
    };
    const { container } = renderWithProviders(
      <TierGate feature="brain.native_chat">
        <div>Chat panel</div>
      </TierGate>,
    );
    expect(container.textContent).toBe('');
  });

  it('hides children on entitlement error (fail closed)', () => {
    mockedEntitlement = {
      ...mockedEntitlement,
      isLoading: false,
      isError: true,
      can: () => false,
    };
    renderWithProviders(
      <TierGate feature="brain.native_chat">
        <div>Chat panel</div>
      </TierGate>,
    );
    expect(screen.queryByText('Chat panel')).toBeNull();
    // Default fallback is null on error.
    expect(screen.queryByText(/Upgrade to/)).toBeNull();
  });
});
