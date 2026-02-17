# AxiomFolio Brand Assets

## Brand Identity

- **Brand mark (the logo):** The four-point star with amber center dot. This IS the logo.
- **Product name:** "AxiomFolio" — rendered as separate text alongside the mark. Not part of the logo itself.

## SVG Files

| File | Type | Use |
|---|---|---|
| `axiomfolio-icon-star.svg` | Brand mark | The logo at 128x128. Use for favicon, app icon, avatar, anywhere the mark appears alone. |
| `axiomfolio-lockup.svg` | Mark + name | Horizontal combo for external use (docs, marketing) on light backgrounds. |
| `axiomfolio-lockup-dark.svg` | Mark + name | Same combo with light fills for dark backgrounds. |
| `axiomfolio-lockup-surface.svg` | Mark + name | Combo on a light surface chip for dark backgrounds. |
| `axiomfolio.svg` | Legacy | Deprecated — use `axiomfolio-icon-star.svg` instead. |

## React Component

In-app, the logo is `<AppLogo />` (`components/ui/AppLogo.tsx`). It renders only the star mark with fixed brand colors (`#3274F0` petals, `#F59E0B` dot) — no theme switching.

```tsx
<AppLogo />            // 44px mark (default)
<AppLogo size={64} />  // larger mark
<AppLogo size={24} />  // compact mark

// Product name is always separate:
<HStack gap="10px" align="center">
  <AppLogo size={52} />
  <Text fontSize="md" fontWeight="semibold">AxiomFolio</Text>
</HStack>
```

### Logo Anatomy

Each petal is built from four cubic bezier curves with G1 (tangent) continuity at every junction — no kinks. The tip is an intentionally sharp point; every other transition flows smoothly.

```
       Tip (sharp point)
       /    \
      /      \      ← gentle outward curve (bezier)
     |        |
      \      /      ← smooth rounded base (bezier ≈ semicircle)
       \____/
```

Four petals arranged in a cross pattern around a center amber dot.

**Path structure (top petal example):**
```
M 64,14                          ← tip
C 69,28  75,37  75,44           ← right side: gentle curve to right base point
C 75,50  70,55  64,55           ← right quarter of base (≈ quarter circle)
C 58,55  53,50  53,44           ← left quarter of base (≈ quarter circle)
C 53,37  59,28  64,14 Z         ← left side: gentle curve back to tip
```

Other petals are 90° rotations of this path around center (64,64).

### Geometry (128x128 viewBox, center at 64,64)

| Parameter | Value | Notes |
|---|---|---|
| Petal width | 22px | Max width at base (53→75) |
| Petal length | 41px | Tip (14) to base bottom (55) |
| Base depth | 11px | Equivalent semicircle radius |
| Gap from center | ~9px | Base bottom to center dot edge |
| Center dot radius | 6px | Amber accent |

### Colors

The brand mark uses **fixed, theme-independent** colors chosen for balanced contrast on both light (~4.2:1 on `#F8FAFC`) and dark (~4.2:1 on `#0F172A`) backgrounds.

| Element | Hex | Notes |
|---|---|---|
| Petals | `#3274F0` | Fixed brand blue — balanced contrast on both canvases |
| Center dot | `#F59E0B` | Fixed amber accent |
| Wordmark (light bg) | `#111827` | `text.primary` token |
| Wordmark (dark bg) | `#E5E7EB` | `text.primary` token |

### Typography

- **Font:** Inter (fallback: system sans-serif stack)
- **Weight:** 600 (semibold)
- **Letter spacing:** 0.3
- **Case:** CamelCase `AxiomFolio`

### Dark Mode

The logo uses fixed colors that work on both light and dark backgrounds — no color switching needed. For static SVGs, all files now use the same `#3274F0` / `#F59E0B` fills. The lockup variants differ only in wordmark text color (`#111827` for light backgrounds, `#E5E7EB` for dark).

### Variant Parameters

To request changes, adjust these bezier control points:

| What | Parameter | Current |
|---|---|---|
| Petal width | Base x-span | 22px (53→75) |
| Petal length | Tip to base bottom | 41px (14→55) |
| Side curvature | Side bezier CPs | (69,28)/(75,37) |
| Base roundness | Base bezier CPs | standard ¼-circle |
| Center dot size | dot radius | 6px |
| Petal color | fill hex | #3274F0 (fixed) |
| Dot color | fill hex | #F59E0B (fixed) |

---

## Production Color Palette

Research-validated, WCAG AA accessible palette used across AxiomFolio.

### Light Theme

| Chakra token | Hex | Role |
|---|---|---|
| `bg.canvas` | `#F8FAFC` | Page background |
| `bg.panel` | `#FFFFFF` | Card/panel surface |
| `fg.default` | `#111827` | Primary text |
| `fg.muted` | `rgba(11,18,32,0.68)` | Secondary text |
| `brand.700` | `#1D4ED8` | Primary brand / CTA |
| `brand.600` | `#2563EB` | Secondary brand |
| `status.info` | `#0EA5E9` | Informational |
| `status.success` | `#16A34A` | Positive / gains |
| `status.warning` | `#D97706` | Caution / amber accent |
| `status.danger` | `#DC2626` | Error / losses |

### Dark Theme

| Chakra token | Hex | Role |
|---|---|---|
| `bg.canvas` | `#0F172A` | Page background |
| `bg.panel` | `#1E293B` | Card/panel surface |
| `fg.default` | `rgba(255,255,255,0.92)` | Primary text |
| `fg.muted` | `rgba(255,255,255,0.70)` | Secondary text |
| `brand.400` | `#60A5FA` | Primary brand / CTA |
| `brand.500` | `#3B82F6` | Secondary brand |
| `status.info` | `#38BDF8` | Informational |
| `status.success` | `#34D399` | Positive / gains |
| `status.warning` | `#F59E0B` | Caution / amber accent |
| `status.danger` | `#F87171` | Error / losses |

### Brand Scale (Chakra tokens)

| Token | Hex | Note |
|---|---|---|
| `brand.50` | `#EFF6FF` | Lightest tint |
| `brand.100` | `#DBEAFE` | |
| `brand.200` | `#BFDBFE` | |
| `brand.300` | `#93C5FD` | |
| `brand.400` | `#60A5FA` | Dark-mode primary |
| `brand.500` | `#3B82F6` | Mid-range |
| `brand.600` | `#2563EB` | brand.secondary |
| `brand.700` | `#1D4ED8` | Light-mode primary |
| `brand.800` | `#1E40AF` | |
| `brand.900` | `#1E3A8A` | Deepest shade |

### Accessibility (WCAG AA validated)

All key pairs pass WCAG AA for normal text (4.5:1 minimum):

| Foreground | Background | Contrast |
|---|---|---|
| `#111827` | `#F8FAFC` | 16.96:1 |
| `#E5E7EB` | `#0F172A` | 14.42:1 |
| `#4B5563` | `#F8FAFC` | 7.22:1 |
| `#94A3B8` | `#0F172A` | 6.96:1 |
| `#FFFFFF` | `#1D4ED8` | 6.70:1 |
| `#0F172A` | `#60A5FA` | 7.02:1 |

### Border Tokens

Two tiers of borders to meet non-text contrast requirements (3:1):

| Token | Role |
|---|---|
| `border.subtle` | Non-critical separators (dividers, section lines) |
| `border.strong` | Input borders, card edges needing clear boundary (≥3:1) |

### Color-Blind Safe Usage

- **Never rely on color alone** for status indication (gains/losses, alerts).
- Always pair color with icons, arrows, or labels (e.g. `+2.4%`, `-1.3%`).
- Success (green) and danger (red) are supplemented with up/down arrows.
- Focus rings must remain visible in both light and dark themes.
