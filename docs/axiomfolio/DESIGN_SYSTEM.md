---
owner: ux
last_reviewed: 2026-04-24
doc_kind: reference
domain: design
status: active
---
# Design System

AxiomFolio’s frontend uses **Radix UI** primitives, **Tailwind CSS v4**, and shadcn-style components. Visual language is defined by **CSS custom properties** on `:root` / `.dark` in `frontend/src/index.css` (with Tailwind `@theme inline` for mapped colors). This document summarizes palettes, semantic tokens, typography, and shared components.

---

## Brand & shadcn palette

Primary UI chrome follows the shadcn-style tokens in `index.css`: `--primary`, `--secondary`, `--accent`, `--muted`, `--destructive`, `--border`, `--ring`, etc. These drive Tailwind utilities such as `bg-primary`, `text-muted-foreground`, and focus rings.

**Focus**: Use `ring-ring` / `outline-ring/50` (see `@layer base` in `index.css`) for consistent focus visibility on interactive elements.

### Status colors (semantic tokens)

Defined as RGB triples for `rgb(var(--status-*) / 1)`:

| Token | Light (approx.) | Dark (approx.) | Usage |
|-------|-----------------|----------------|--------|
| `--status-success` | green | mint | Gains, positive P&L |
| `--status-danger` | red | light red | Losses, negative P&L |
| `--status-warning` | amber | amber | Warnings, caution |
| `--status-info` | sky | sky | Informational highlights |

Components like `PnlText` map positive values to success, negative to danger, and neutral to muted foreground.

### Chart palette

| Token | Role |
|-------|------|
| `--chart-success`, `--chart-danger`, `--chart-neutral`, `--chart-warning` | Series and quadrant accents |
| `--chart-area1`, `--chart-area2` | Area fills (e.g. breadth) |
| `--chart-grid`, `--chart-axis`, `--chart-refLine` | Grid and axes |

Dark mode overrides live under `.dark { ... }` in the same file.

---

## Semantic tokens (`index.css`)

AxiomFolio-specific variables (many mirrored as Tailwind-friendly RGB triples):

### Background (`--bg-*`)

| Token | Usage |
|-------|--------|
| `--bg-canvas` | Page-level background |
| `--bg-panel` | Elevated panels / tables |
| `--bg-card` | Card surfaces (often `var(--card)`) |
| `--bg-muted`, `--bg-subtle` | Hover / selected / subtle fills |
| `--bg-header`, `--bg-sidebar` | Chrome regions |
| `--bg-input` | Input backgrounds |

### Foreground (`--fg-*`)

| Token | Usage |
|-------|--------|
| `--fg-default` | Primary text (ties to `--foreground`) |
| `--fg-muted` | Secondary text |
| `--fg-subtle` | Tertiary / placeholders |
| `--fg-accent`, `--fg-amber` | Accent callouts |

### Border (`--border-*`)

| Token | Usage |
|-------|--------|
| `--border-subtle` | Default dividers (often `var(--border)`) |
| `--border-strong` | Stronger separators |
| `--border-hover` | Hover outline emphasis |

### Stage palettes

Stage badges and bars use `--palette-stage-gray|green|yellow|orange|red` (RGB triples), aligned with `STAGE_HEX` / `constants/chart.ts`.

---

## Typography

### Font families

| Role | Source |
|------|--------|
| Body / UI | `Inter Variable` via `@fontsource-variable/inter` and `--font-sans` in `index.css` |
| Headings | Same stack unless a page opts into a display font in local styles |

### Practical guidance

- Page titles: use semantic heading classes or `text-lg` / `font-semibold` patterns consistent with `PageHeader`.
- Tables: `text-sm` for dense data; maintain minimum touch targets (~44px row height on mobile) in `SortableTable`.
- Buttons: `font-medium` / `font-semibold` per `components/ui/button.tsx` variants.

### Radii

Tailwind radius scale comes from `--radius` (default `0.625rem`) and derived `--radius-sm` … `--radius-4xl` in `@theme inline`.

---

## Component library

Shared building blocks (paths under `frontend/src/`):

| Component | Path | Purpose |
|-----------|------|---------|
| `StatCard` | `components/shared/StatCard.tsx` | KPI card, compact and full layouts |
| `PnlText` | `components/shared/PnlText.tsx` | P&L with semantic color |
| `StageBadge` | `components/shared/StageBadge.tsx` | Stage labels using stage palettes |
| `StageBar` | `components/shared/StageBar.tsx` | Stacked stage distribution |
| Skeletons | `components/shared/Skeleton.tsx` | Loading placeholders |
| `Page` / `PageHeader` | `components/ui/Page.tsx`, `PageHeader.tsx` | Layout and title rows |
| `SortableTable` | `components/SortableTable.tsx` | Sortable, filterable tables |
| `AccountSelector` | `components/ui/AccountSelector.tsx` | Account picker variants |
| `Button`, `Card`, `Dialog`, `Input`, … | `components/ui/*` | Radix + Tailwind primitives |

### Stage colors

Logical stages map to palettes in `constants/chart.ts` and `--palette-stage-*` CSS variables for badges and bars.

---

## Color usage rules

1. **Prefer semantic tokens** — `bg-background`, `text-muted-foreground`, `border-border`, or `rgb(var(--bg-panel) / 1)` instead of arbitrary hex.
2. **Status** — use `--status-success` / `--status-danger` / `--status-warning` / `--status-info` for P&L and alerts.
3. **Charts** — use `--chart-*` so series stay consistent in light and dark mode.
4. **Avoid raw hex in components** — add or extend CSS variables in `index.css` when a new meaning is needed.
5. **Brand / primary** — use `primary` / `ring` tokens for interactive emphasis and focus.

---

## Dark mode

Implemented in `frontend/src/theme/colorMode.tsx`:

- **`ColorModeProvider`** manages `"light"`, `"dark"`, or `"system"`.
- Preference persists under `qm.colorModePreference` in `localStorage`.
- **`system`** follows `prefers-color-scheme` and updates on change.
- Effective mode applies **`light` or `dark` class on `<html>`**, which switches the `.dark { ... }` variable block in `index.css`.

### Legacy compatibility

The provider migrates the old `qm.colorMode` key to `qm.colorModePreference` when present.

---

## Responsive patterns

### Breakpoints

Use Tailwind defaults (`sm`, `md`, `lg`, `xl`, `2xl`) — see Tailwind v4 docs for pixel widths.

### Layout patterns

**Two-panel layouts** (e.g. PortfolioWorkspace):

```tsx
<div className="flex flex-col gap-4 lg:flex-row">
  <aside className="w-full shrink-0 lg:w-[340px]">sidebar</aside>
  <main className="min-w-0 flex-1">main content</main>
</div>
```

**Padding**: `p-3 md:p-6`

**Chart heights**: Use responsive classes or `useMediaQuery` for numeric chart dimensions.

### Mobile dialogs

Prefer bottom-aligned sheets on small viewports using responsive classes on Radix `DialogContent` (e.g. `max-h-[90vh]`, rounded top corners, full width on `sm`).

### Tables

`SortableTable` supports `hiddenOnMobile`, `mobileRender`, and adequate row height for touch.

---

## Known issues

1. **Mixed token usage** — Some older components may still use hardcoded colors; new work should converge on CSS variables and Tailwind semantic classes.
