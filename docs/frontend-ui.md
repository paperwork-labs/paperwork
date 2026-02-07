## Frontend UI (Chakra v3 + Ladle)

### What we’re using
- **React + Vite**: `frontend/`
- **Chakra UI v3**: design system + primitives via a single `system` configuration.
- **Ladle**: lightweight component explorer (Storybook alternative).

### Chakra v3 architecture in this repo

#### 1) Single source of truth: `system`
The canonical Chakra v3 system lives in:
- `frontend/src/theme/system.ts`

It defines:
- **Tokens**: core brand palette, typography, radii.
- **Semantic tokens**: `bg.*`, `fg.*`, `border.*` for consistent light/dark theming.
- **Recipes**: base styles for `button`, `input`, etc.

The app mounts Chakra like this:
- `frontend/src/App.tsx` → `<ChakraProvider value={system}>`

#### 2) App-level primitives
We build “app primitives” on top of Chakra v3 components so pages stay consistent:
- `frontend/src/components/ui/AppCard.tsx`
- `frontend/src/components/ui/Page.tsx`
- `frontend/src/components/ui/FormField.tsx`
- `frontend/src/components/ui/Pagination.tsx`

Pages should prefer **semantic tokens** like `bg.card`, `border.subtle`, `fg.muted` instead of hardcoded colors.

### Ladle (component explorer)

#### Run Ladle locally
From the repo root (Docker):

```bash
make ladle-up
```

Ladle runs on port **61000** (see `frontend/package.json`), via a dedicated compose service in `infra/compose.dev.yaml`.

#### Build Ladle

```bash
make ladle-build
```

#### Ladle provider setup
Ladle uses the same Chakra v3 system provider as the app:
- `frontend/.ladle/components.tsx`

### Keeping UI libraries current
- Frontend dependencies live in `frontend/package.json`.
- Chakra is pinned to v3 (`@chakra-ui/react`).
- Upgrades should be done by updating versions and validating:
  - `docker compose --project-name axiomfolio --env-file infra/env.dev -f infra/compose.dev.yaml exec -T frontend npm test`
  - `docker compose --project-name axiomfolio --env-file infra/env.dev -f infra/compose.dev.yaml exec -T frontend npm run build`
  - `make ladle-build`


