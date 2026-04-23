import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';

import PasswordStrengthMeter, {
  computePasswordStrengthScore,
  passwordFilledBarCount,
} from '../PasswordStrengthMeter';

describe('passwordFilledBarCount', () => {
  it('shows one bar for a short password with no criteria met (e.g. abc)', () => {
    expect(passwordFilledBarCount('abc')).toBe(1);
  });

  it('shows three bars when length, mixed case, and digit are all met (e.g. abcDef12)', () => {
    expect(passwordFilledBarCount('abcDef12')).toBe(3);
  });
});

describe('computePasswordStrengthScore', () => {
  it('caps at too-short when length < 8 even with mixed case and digit', () => {
    expect(computePasswordStrengthScore('aA1')).toBe(0);
    expect(computePasswordStrengthScore('Short1!')).toBe(0);
  });

  it('scores weak for 8+ chars missing complexity', () => {
    expect(computePasswordStrengthScore('abcdefgh')).toBe(1);
  });

  it('scores okay on boundary with length + mixed case only', () => {
    expect(computePasswordStrengthScore('abcdefgH')).toBe(2);
  });

  it('scores strong with full complexity', () => {
    expect(computePasswordStrengthScore('GoodPassw0rd!')).toBe(3);
  });
});

describe('PasswordStrengthMeter', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('empty password: no live region, no visible Too short label', () => {
    const { container } = render(<PasswordStrengthMeter password="" />);
    const root = container.firstChild as HTMLElement;
    expect(root).toHaveAttribute('aria-live', 'off');
    expect(root).not.toHaveAttribute('role');
    expect(root).not.toHaveAttribute('aria-label');
    expect(screen.queryByText(/^Too short/)).toBeNull();
  });

  it('shows Too short for aA1 (weak complexity but under 8 chars)', async () => {
    render(<PasswordStrengthMeter password="aA1" />);
    expect(screen.getByText(/^Too short/)).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Password strength: Too short');
  });

  it('shows Strong for a long complex password', async () => {
    render(<PasswordStrengthMeter password="GoodPassw0rd!" />);
    expect(screen.getByText(/^Strong/)).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Password strength: Strong');
  });

  it('shows Weak for 8+ lowercase only', async () => {
    render(<PasswordStrengthMeter password="abcdefgh" />);
    expect(screen.getByText(/^Weak/)).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Password strength: Weak');
  });

  it('shows Okay for 8+ chars with mixed case', async () => {
    render(<PasswordStrengthMeter password="abcdefgH" />);
    expect(screen.getByText(/^Okay/)).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Password strength: Okay');
  });

  it('does not expose status role before a11y debounce elapses', () => {
    const { container } = render(<PasswordStrengthMeter password="x" />);
    expect(screen.queryByRole('status')).toBeNull();
    expect(container.firstChild).not.toHaveAttribute('role');
  });

  it('renders one non-muted bar for abc', () => {
    const { container } = render(<PasswordStrengthMeter password="abc" />);
    const bars = container.querySelectorAll('span.h-1.flex-1.rounded-full');
    expect(bars.length).toBe(3);
    const filled = [...bars].filter((el) => !el.classList.contains('bg-muted'));
    expect(filled.length).toBe(1);
  });

  it('renders three non-muted bars for abcDef12', () => {
    const { container } = render(<PasswordStrengthMeter password="abcDef12" />);
    const bars = container.querySelectorAll('span.h-1.flex-1.rounded-full');
    const filled = [...bars].filter((el) => !el.classList.contains('bg-muted'));
    expect(filled.length).toBe(3);
  });
});
