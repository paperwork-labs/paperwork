import * as React from 'react';

import MarketTracked from '../MarketTracked';

/**
 * `/market/universe` — the merged Watchlist + Symbol Lookup view.
 *
 * Historically we shipped two separate sidebar entries (`/market/tracked`
 * for the watchlist and `/market/scanner` for symbol lookup). They both
 * rendered the same `MarketTracked` component in different modes, which
 * made the nav feel redundant without adding any capability. This page
 * is the one entry point — the underlying `MarketTracked` already reads
 * the ``mode`` query param to switch between watching and screening, so
 * the tab strip is expressed via URL state rather than a second component
 * tree.
 */
export default function Universe() {
  return <MarketTracked />;
}
