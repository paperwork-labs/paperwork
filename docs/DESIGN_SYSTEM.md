# Design System

Axiomfolio's frontend is built on **Chakra UI v3** with a custom theme defined in `frontend/src/theme/system.ts`. This document captures the palette, semantic tokens, typography, and shared components that make up the visual language.

---

## Brand Palette

The brand scale is a blue ramp used for primary actions, active sort indicators, and focus rings.

| Token        | Hex       |
|------------- |-----------|
| `brand.50`   | `#EFF6FF` |
| `brand.100`  | `#DBEAFE` |
| `brand.200`  | `#BFDBFE` |
| `brand.300`  | `#93C5FD` |
| `brand.400`  | `#60A5FA` |
| `brand.500`  | `#3B82F6` |
| `brand.600`  | `#2563EB` |
| `brand.700`  | `#1D4ED8` |
| `brand.800`  | `#1E40AF` |
| `brand.900`  | `#1E3A8A` |

**Focus ring:** `rgba(29,78,216,0.22)` — applied via the `focusRing` token in button and input recipes.

### Status Colors (semantic tokens)

| Token             | Light       | Dark        | Usage                      |
|-------------------|-------------|-------------|----------------------------|
| `status.success`  | `#16A34A`   | `#34D399`   | Gains, positive P&L        |
| `status.danger`   | `#DC2626`   | `#F87171`   | Losses, negative P&L       |
| `status.warning`  | `#D97706`   | `#F59E0B`   | Warnings, caution states   |
| `status.info`     | `#0EA5E9`   | `#38BDF8`   | Informational highlights   |

> **Note:** The theme defines `status.success` / `status.danger` / `status.warning` / `status.info`. Components like `PnlText` map positive values to `status.success`, negative to `status.danger`, and zero to `fg.muted`.

### Chart Palette

| Token            | Light                    | Dark                     |
|------------------|--------------------------|--------------------------|
| `chart.success`  | `#16A34A`                | `#4ADE80`                |
| `chart.danger`   | `#DC2626`                | `#F87171`                |
| `chart.neutral`  | `#3B82F6`                | `#60A5FA`                |
| `chart.warning`  | `#D97706`                | `#FBBF24`                |
| `chart.area1`    | `#16A34A`                | `#34D399`                |
| `chart.area2`    | `#2563EB`                | `#60A5FA`                |
| `chart.grid`     | `rgba(15,23,42,0.08)`    | `rgba(255,255,255,0.08)` |
| `chart.axis`     | `rgba(15,23,42,0.4)`     | `rgba(255,255,255,0.45)` |
| `chart.refLine`  | `rgba(15,23,42,0.2)`     | `rgba(255,255,255,0.2)`  |

---

## Semantic Tokens

All tokens are defined in `system.ts → semanticTokens.colors` with light/dark variants.

### Background (`bg.*`)

| Token         | Light                    | Dark                       | Usage                            |
|---------------|--------------------------|----------------------------|----------------------------------|
| `bg.canvas`   | `#F8FAFC`                | `#0F172A`                  | Page-level background            |
| `bg.panel`    | `white`                  | `#1E293B`                  | Elevated surface (cards, tables) |
| `bg.card`     | `white`                  | `rgba(17,24,39,0.72)`      | Card backgrounds                 |
| `bg.muted`    | `rgba(15,23,42,0.05)`    | `rgba(255,255,255,0.06)`   | Hover / selected states          |
| `bg.subtle`   | `rgba(15,23,42,0.08)`    | `rgba(255,255,255,0.10)`   | Slightly stronger than muted     |
| `bg.header`   | `white`                  | `#1E293B`                  | App header chrome                |
| `bg.sidebar`  | `white`                  | `#1E293B`                  | Sidebar chrome                   |
| `bg.input`    | `rgba(0,0,0,0.03)`       | `rgba(0,0,0,0.25)`         | Input field backgrounds          |

### Foreground (`fg.*`)

| Token        | Light                    | Dark                       | Usage              |
|--------------|--------------------------|----------------------------|--------------------|
| `fg.default` | `#111827`                | `rgba(255,255,255,0.92)`   | Primary text       |
| `fg.muted`   | `rgba(11,18,32,0.68)`    | `rgba(255,255,255,0.70)`   | Secondary text     |
| `fg.subtle`  | `rgba(11,18,32,0.46)`    | `rgba(255,255,255,0.55)`   | Tertiary / placeholders |

### Border (`border.*`)

| Token           | Light                    | Dark                       |
|-----------------|--------------------------|----------------------------|
| `border.subtle` | `rgba(15,23,42,0.10)`    | `rgba(255,255,255,0.12)`   |
| `border.strong` | `rgba(15,23,42,0.18)`    | `rgba(255,255,255,0.18)`   |

### Status (`status.*`)

See [Status Colors](#status-colors-semantic-tokens) above.

### Chart (`chart.*`)

See [Chart Palette](#chart-palette) above.

---

## Typography

### Font Families

| Role    | Stack                                                                                             |
|---------|---------------------------------------------------------------------------------------------------|
| Heading | `'Space Grotesk', 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, …`         |
| Body    | `'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial`            |

### Sizes and Weights in Use

| Context               | Size   | Weight     | Token / example                          |
|-----------------------|--------|------------|------------------------------------------|
| Page heading          | `lg`   | default    | `PageHeader` → `<Heading size="lg">`     |
| Page subtitle         | `sm`   | normal     | `<Text fontSize="sm" color="fg.muted">`  |
| Card label            | `xs`   | normal     | StatCard compact label                   |
| Card value            | `lg`   | `bold`     | StatCard compact value                   |
| Table cells           | `sm`   | normal     | SortableTable default                    |
| Buttons               | —      | `semibold` | Button recipe, `letterSpacing: -0.01em`  |
| Headings (global)     | —      | —          | `letterSpacing: -0.02em` on PageHeader   |

### Custom Radii

| Token | Value  |
|-------|--------|
| `lg`  | `12px` |
| `xl`  | `16px` |

---

## Component Library

Shared, reusable components that form the building blocks of page layouts.

| Component          | Path                                          | Purpose                                                                                      |
|--------------------|-----------------------------------------------|----------------------------------------------------------------------------------------------|
| `StatCard`         | `components/shared/StatCard.tsx`              | KPI card with `compact` (border box) and `full` (Chakra Stat) variants. Supports trend arrows and icons. |
| `PnlText`          | `components/shared/PnlText.tsx`               | Inline P&L display with semantic color (`status.success` / `status.danger`), arrow glyphs, and currency/percent formatting. |
| `StageBadge`       | `components/shared/StageBadge.tsx`            | Colored badge for stage labels (1, 2A, 2B, 2C, 3, 4) using `STAGE_COLORS` from `constants/chart.ts`. |
| `StageBar`         | `components/shared/StageBar.tsx`              | Horizontal stacked bar showing stage distribution with legend badges.                        |
| `StatCardSkeleton` | `components/shared/Skeleton.tsx`              | Pulsing placeholder matching StatCard dimensions.                                            |
| `TableSkeleton`    | `components/shared/Skeleton.tsx`              | Pulsing row placeholders for table loading states.                                           |
| `ChartSkeleton`    | `components/shared/Skeleton.tsx`              | Rectangle placeholder for chart loading states.                                              |
| `Page`             | `components/ui/Page.tsx`                      | Centered content container (`maxW="1200px"`, responsive padding).                            |
| `PageHeader`       | `components/ui/Page.tsx` (named export)       | Title + optional subtitle + actions row. Uses `fg.default` / `fg.muted` tokens.              |
| `PageHeader`       | `components/ui/PageHeader.tsx` (default export)| Duplicate implementation with `rightContent` prop instead of `actions` slot.                  |
| `SortableTable`    | `components/SortableTable.tsx`                | Generic sortable, filterable table with column definitions, filter presets, keyboard-navigable rows, and user-preference-aware density. |
| `AccountSelector`  | `components/ui/AccountSelector.tsx`           | Account picker with `simple` (native select) and `detailed` (card + popover + summary stats) variants. |
| `StepWizard`       | *(planned — not yet implemented)*             | Multi-step wizard for guided flows.                                                          |

### Stage Colors

Defined in `constants/chart.ts` as Chakra `colorPalette` values:

| Stage | Palette  |
|-------|----------|
| `1`   | `gray`   |
| `2A`  | `green`  |
| `2B`  | `green`  |
| `2C`  | `yellow` |
| `3`   | `orange` |
| `4`   | `red`    |

---

## Color Usage Rules

1. **Always use semantic tokens** — reference `bg.canvas`, `fg.default`, `border.subtle`, etc. instead of raw Chakra palette values like `gray.100` or `blue.500`.
2. **Status colors** — use `status.success` (green) for gains, `status.danger` (red) for losses, `status.warning` (amber) for caution, `status.info` (sky blue) for informational callouts. Do not reach for `green.500` or `red.400` directly.
3. **Charts** — use `chart.*` tokens (`chart.success`, `chart.danger`, `chart.neutral`, `chart.area1`, `chart.area2`, `chart.grid`, `chart.axis`, `chart.refLine`) so series colors stay consistent across light and dark modes.
4. **Never hardcode hex values** in component code. If a new semantic meaning is needed, add a token to `system.ts` first.
5. **Brand color** — `brand.500` is used for active sort indicators and focus rings. Prefer the semantic token when possible; use the brand scale directly only for decorative accents or gradients.

---

## Dark Mode

Dark mode is implemented via a custom `ColorModeProvider` in `frontend/src/theme/colorMode.tsx`.

### How It Works

- **`ColorModeProvider`** wraps the app and manages three-state preference: `"light"`, `"dark"`, or `"system"`.
- Preference is persisted to `localStorage` under the key `qm.colorModePreference`.
- When set to `"system"`, the provider listens to `prefers-color-scheme: dark` media query changes and updates automatically.
- The effective mode is applied to `<html>` via CSS classes: `.dark` or `.light`. Chakra v3's `defaultConfig` uses `.dark &` selectors for dark-mode styles.
- **`useColorMode()`** hook exposes `colorMode`, `colorModePreference`, `setColorModePreference`, `setColorMode`, and `toggleColorMode`.

### Legacy Compatibility

The provider reads the old `qm.colorMode` localStorage key, migrates it to the new `qm.colorModePreference` key, and removes the old entry.

---

## Responsive Patterns

### Breakpoints
Following Chakra UI v3 breakpoints:
- `base`: 0px (mobile)
- `sm`: 480px
- `md`: 768px (tablet)
- `lg`: 992px (desktop)
- `xl`: 1280px

### Layout Patterns

**Two-panel layouts** (e.g., PortfolioWorkspace):
```tsx
<Flex flexDirection={{ base: 'column', lg: 'row' }}>
  <Box w={{ base: '100%', lg: '340px' }}>sidebar</Box>
  <Box flex={1}>main content</Box>
</Flex>
```

**Padding**: `p={{ base: 3, md: 6 }}`

**Chart heights**: Use responsive values or `useMediaQuery` for number-only props.

### Mobile Modal Patterns

Modals use bottom-sheet behavior on mobile:
```tsx
<DialogPositioner alignItems={{ base: 'flex-end', md: 'center' }}>
  <DialogContent
    maxW={{ base: '95vw', md: 'md' }}
    borderRadius={{ base: '16px 16px 0 0', md: 'xl' }}
    maxH={{ base: '90vh', md: 'auto' }}
  />
</DialogPositioner>
```

### Table Responsiveness

SortableTable supports:
- `hiddenOnMobile`: hides column below md breakpoint
- `mobileRender`: custom per-row rendering for mobile
- Minimum touch target: 44px row height

### Notification Menus

```tsx
<MenuContent minW={{ base: 'calc(100vw - 32px)', md: '340px' }}>
```

---

## Known Issues

1. **Inconsistent semantic token usage** — Some components use raw Chakra palette values (e.g., `StageBar` uses `${palette}.400` for bar segment backgrounds and hardcodes `color="white"` for text) instead of semantic tokens.
