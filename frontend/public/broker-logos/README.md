# Broker logos

Static SVG assets served as `/broker-logos/<slug>.svg` for the
Connect hub (`/connect`) and Manage Connections (`/accounts/manage`)
pages.

The slug must match `BrokerCatalogEntry.slug` in
`backend/services/portfolio/broker_catalog.py`. If a slug has no
matching SVG, the frontend renders a deterministic monogram circle
fallback (`<BrokerLogo>` in `frontend/src/components/connect/BrokerLogo.tsx`)
so the page never crashes.

When adding a new broker:

1. Add the catalog entry in `broker_catalog.py`.
2. Drop the official SVG here as `<slug>.svg`.
3. Any aspect ratio is fine as long as it scales cleanly with
   `object-contain` at 44px in cards.

Logos seeded today:

- `schwab.svg`
- `ibkr.svg`
- `tastytrade.svg`

Everything else falls back to a monogram until we add the asset.
