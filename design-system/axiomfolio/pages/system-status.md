# System Status Page Overrides

> **PROJECT:** AxiomFolio
> **Generated:** 2026-03-24 17:07:37
> **Page Type:** Admin / Diagnostics Dashboard

> ⚠️ **IMPORTANT:** Rules in this file **override** the Master file (`design-system/MASTER.md`).
> Only deviations from the Master are documented here. For all other rules, refer to the Master.

---

## Page-Specific Rules

### Layout Overrides

- **Max Width:** 1400px (contained)
- **Grid:** 4-column grid for dimension cards, stack on mobile
- **Sections:** 1. Composite Health Summary, 2. Dimension Cards (Data Coverage, Regime Freshness, Indicators, Snapshots), 3. Recent Auto-Ops Activity, 4. Advanced Controls (collapsible)

### Spacing Overrides

- **Content Density:** Medium — balance readability with information density
- **Card Gap:** 16px between dimension cards
- **Section Gap:** 24px between major sections

### Typography Overrides

- **Status Labels:** Use system monospace for timestamps and task IDs
- **Dimension Titles:** Bold, uppercase for card headers

### Color Overrides

- **Health Status Colors:**
  - Green: `chart.stage2a` (healthy)
  - Yellow: `chart.stage3a` (warning)
  - Red: `chart.stage4` (critical)
- **Background:** Use `bg.card` for dimension cards

### Component Overrides

- Use `StatCard` component for dimension summaries
- Use `SortableTable` for recent activity feed
- Collapsible section for Advanced controls (default collapsed)

---

## Page-Specific Components

- **HealthDimensionCard:** Card showing dimension name, status badge, metric value, and last-checked timestamp
- **AutoOpsActivityTable:** Table of recent auto-ops actions with status, dimension, timestamp columns
- **AdvancedControls:** Collapsible section with operator actions (recompute indicators, record snapshot, etc.)

---

## Recommendations

- Effects: Pulse animation on status badges when status changes, smooth collapse/expand for Advanced section
- Feedback: Show spinner during health refresh, toast on action completion
- Auto-refresh: Poll health status every 60 seconds when page is visible
- Mobile: Stack dimension cards vertically, hide Advanced section behind button
