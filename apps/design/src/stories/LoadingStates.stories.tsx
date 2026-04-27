import React from 'react';
import { useColorMode } from '@axiomfolio/theme/colorMode';
import {
  PortfolioSummarySkeleton,
  HoldingsTableSkeleton,
  TransactionsSkeleton,
  LoadingSpinner,
  LoadingOverlay,
} from '@axiomfolio/components/LoadingStates';

import type { Meta, StoryObj } from "@storybook/react";

const meta: Meta = {
  title: 'DesignSystem/LoadingStates',
};
export default meta;

type Story = StoryObj;

const pillBtn = 'rounded-[10px] border border-border px-3 py-2 text-sm';

export const Skeletons_And_Spinners: Story = {
  render: () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const [overlay, setOverlay] = React.useState(false);

  return (
    <div className="p-6">
      <div className="mb-5 flex flex-row items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-foreground">Loading states</div>
          <div className="text-sm text-muted-foreground">Mode: {colorMode}</div>
        </div>
        <div className="flex flex-row gap-2">
          <button type="button" className={pillBtn} onClick={toggleColorMode}>
            Toggle mode
          </button>
          <button type="button" className={pillBtn} onClick={() => setOverlay((v) => !v)}>
            Toggle overlay
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-6">
        <div>
          <div className="mb-3 text-sm font-semibold text-foreground">Portfolio summary</div>
          <PortfolioSummarySkeleton />
        </div>

        <div>
          <div className="mb-3 text-sm font-semibold text-foreground">Holdings table</div>
          <HoldingsTableSkeleton rows={7} />
        </div>

        <div>
          <div className="mb-3 text-sm font-semibold text-foreground">Transactions list</div>
          <TransactionsSkeleton rows={8} />
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-2 text-sm font-semibold text-foreground">Spinner</div>
          <LoadingSpinner message="Syncing data…" showProgress progress={42} />
        </div>
      </div>

      <LoadingOverlay isVisible={overlay} message="Loading overlay…" />
    </div>
  );
},
};
