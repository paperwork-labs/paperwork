import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen } from '@/test/testing-library';
import { renderWithProviders } from '@/test/render';
import HistoricalImportWizard from '../settings/HistoricalImportWizard';

const mocks = vi.hoisted(() => ({
  startHistoricalImport: vi.fn().mockResolvedValue({ id: 42 }),
  startHistoricalImportCsv: vi.fn().mockResolvedValue({ id: 77 }),
}));

vi.mock('@/services/api', () => ({
  accountsApi: {
    startHistoricalImport: mocks.startHistoricalImport,
    startHistoricalImportCsv: mocks.startHistoricalImportCsv,
  },
  handleApiError: (e: unknown) => String((e as { message?: string })?.message || 'error'),
}));

describe('HistoricalImportWizard', () => {
  it('completes XML happy path and shows explainer notice', async () => {
    const user = userEvent.setup();
    renderWithProviders(<HistoricalImportWizard />);

    await user.type(screen.getByLabelText(/Account ID/i), '12');
    await user.click(screen.getByRole('button', { name: /Continue/i }));
    await user.type(screen.getByLabelText(/^From$/i), '2023-01-01');
    await user.type(screen.getByLabelText(/^To$/i), '2024-01-01');
    await user.click(screen.getByRole('button', { name: /Start import/i }));

    expect(mocks.startHistoricalImport).toHaveBeenCalledWith(12, {
      date_from: '2023-01-01',
      date_to: '2024-01-01',
      xml_content: undefined,
    });
    expect(
      await screen.findByText(
        /Historical orders imported via backfill will not receive automatic AI explanations/i,
      ),
    ).toBeInTheDocument();
  });

  it('prevents submit until required values are present', async () => {
    const user = userEvent.setup();
    renderWithProviders(<HistoricalImportWizard />);

    const continueButton = screen.getByRole('button', { name: /Continue/i });
    expect(continueButton).toBeDisabled();

    await user.type(screen.getByLabelText(/Account ID/i), '7');
    expect(continueButton).toBeEnabled();

    await user.click(continueButton);
    const startButton = screen.getByRole('button', { name: /Start import/i });
    expect(startButton).toBeDisabled();
  });
});
