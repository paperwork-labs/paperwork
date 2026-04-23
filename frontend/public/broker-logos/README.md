# Broker logos

Static SVG assets served as `/broker-logos/<slug>.svg` for the Connect hub, API
`logo_url` fields, and any inline `<img src="/broker-logos/...">` usage. Source
and licensing are summarized in
`frontend/src/assets/logos/broker-assets-README.md` (Vite also bundles the same
marks via `components/brokers/brokerLogosMap.ts`).

The slug should match `BrokerCatalogEntry.slug` in
`backend/services/portfolio/broker_catalog.py`. If a slug has no file here and
is not in the Vite map, the UI may show a monogram (remote load failed) or a
Building2 mark (unknown slug with no URL).

**Present in this directory:** `schwab.svg`, `ibkr.svg`, `tastytrade.svg`,
`etrade.svg`, `tradier.svg`, `coinbase.svg`, `fidelity.svg` (and any others you
add for new catalog entries).

When adding a new broker:

1. Add the catalog entry in `broker_catalog.py`.
2. Add the official SVG in `frontend/src/assets/logos/`, re-export in
   `brokerLogosMap.ts`, and mirror the file here as `<slug>.svg`.
3. Prefer any aspect ratio that scales with `object-contain` in cards (32–40px).
