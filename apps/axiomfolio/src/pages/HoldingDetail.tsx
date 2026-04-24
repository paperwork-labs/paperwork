/**
 * `HoldingDetail` — dedicated full-bleed page for a single holding.
 *
 * The page is intentionally thin: it only owns the URL state binding
 * (period / overlays / stage bands / benchmark) and mounts the flagship
 * `HoldingPriceChart`. All chart logic — data fetching, theme reactivity,
 * rendering — lives in the chart component itself so this page can stay
 * trivially testable and easy to reuse from share-card / OG-image flows.
 */
import * as React from 'react';
import { Link, useParams } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';

import { HoldingPriceChart } from '@/components/charts/HoldingPriceChart';
import { useAccountContext } from '@/context/AccountContext';
import { useHoldingChartUrlState } from '@/hooks/useHoldingChartUrlState';

const HOLDING_DETAIL_DEFAULT_TITLE = 'Holding · AxiomFolio';

export function HoldingDetail() {
  const params = useParams<{ symbol?: string }>();
  const rawSymbol = params.symbol ?? '';
  const symbol = rawSymbol.trim().toUpperCase();
  const { selected } = useAccountContext();
  const accountId =
    selected && selected !== 'all' && selected !== 'taxable' && selected !== 'ira'
      ? selected
      : undefined;

  const url = useHoldingChartUrlState({
    defaultPeriod: 'since',
  });

  // Set the document title so a tab parked on this page shows the symbol.
  // Restore the previous title on unmount so we don't pollute neighbours.
  React.useEffect(() => {
    if (typeof document === 'undefined') return;
    const previous = document.title;
    document.title = symbol
      ? `${symbol} · AxiomFolio`
      : HOLDING_DETAIL_DEFAULT_TITLE;
    return () => {
      document.title = previous;
    };
  }, [symbol]);

  if (!symbol) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <Breadcrumb />
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          No symbol specified.{' '}
          <Link to="/portfolio/holdings" className="underline">
            Back to holdings
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 p-4 md:p-6">
      <Breadcrumb symbol={symbol} />
      <HoldingPriceChart
        symbol={symbol}
        accountId={accountId}
        initialPeriod={url.period}
        onPeriodChange={url.setPeriod}
        overlays={url.overlays}
        onOverlaysChange={url.setOverlays}
        showStageBands={url.stageBands}
        onShowStageBandsChange={url.setStageBands}
        benchmarkOverride={url.benchmark}
        showMetricStrip
        height={520}
      />
    </div>
  );
}

interface BreadcrumbProps {
  symbol?: string;
}

function Breadcrumb({ symbol }: BreadcrumbProps) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-2 text-sm text-muted-foreground"
    >
      <Link
        to="/portfolio/holdings"
        className="inline-flex items-center gap-1 rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronLeft className="size-4" aria-hidden />
        <span>Holdings</span>
      </Link>
      {symbol ? (
        <>
          <span aria-hidden className="text-muted-foreground/60">
            /
          </span>
          <span className="font-medium text-foreground" aria-current="page">
            {symbol}
          </span>
        </>
      ) : null}
    </nav>
  );
}

export default HoldingDetail;
