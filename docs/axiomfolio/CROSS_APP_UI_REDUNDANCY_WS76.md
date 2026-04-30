# Cross-app UI redundancy (WS-76 PR-29)

This note captures **migration candidates only** — no component moves were done in PR-29.

## How duplicates are tracked

- **Brain audit** `cross_app_ui_redundancy` (`apis/brain/app/audits/cross_app_ui_redundancy.py`) now emits **info** findings when `apps/*/src/components/ui/<file>.tsx` shares a basename with a top-level file in `packages/ui/src/components/`.
- Cross-app **exported component name** collisions (same React symbol in ≥2 apps) remain **warn** findings when they match structural patterns (Tabs, Shell, etc.).

## AxiomFolio vs `@paperwork-labs/ui` (basename overlap)

These files under `apps/axiomfolio/src/components/ui/` match a primitive shipped from `packages/ui` (same filename). They are candidates to delete locally and import from `@paperwork-labs/ui` once styling/API compatibility is verified:

| Local file | Packages UI |
| --- | --- |
| `alert.tsx` | `alert.tsx` |
| `badge.tsx` | `badge.tsx` |
| `button.tsx` | `button.tsx` |
| `card.tsx` | `card.tsx` |
| `checkbox.tsx` | `checkbox.tsx` |
| `dialog.tsx` | `dialog.tsx` |
| `input.tsx` | `input.tsx` |
| `label.tsx` | `label.tsx` |
| `progress.tsx` | `progress.tsx` |
| `skeleton.tsx` | `skeleton.tsx` |
| `switch.tsx` | `switch.tsx` |
| `textarea.tsx` | `textarea.tsx` |
| `tooltip.tsx` | `tooltip.tsx` |

AxiomFolio-specific wrappers (for example `AppCard`, `ChartGlassCard`, `responsive-modal`) are **not** duplicates of shared primitives and should stay unless a deliberate abstraction lands in `packages/ui`.

## Related shipping work

- **`BrainChat`** — shared floating chat widget lives in `packages/ui/src/components/BrainChat.tsx`.
- **`BrainChatPanel`** — AxiomFolio wiring in `apps/axiomfolio/src/components/BrainChatPanel.tsx` (tier gate + Brain BFF route).
