# Brand known issues (2026 Q2)

## PNG-wrapped SVG placeholders (`paperclip-*.svg`)

The SVG files at `apps/studio/public/brand/paperclip-{mark-diagonal,mark-vertical,clipped-wordmark}.svg` are **PNG-wrapped placeholders**, not native vector paths. They embed the canonical raster renders via `<image href="renders/...">` so stable public URLs and imports keep working until a proper retrace ships.

## Source-of-truth visuals

Authoritative appearance is the founder-locked **nano-banana-pro** renders under `apps/studio/public/brand/renders/`:

- `paperclip-LOCKED-canonical-1024.png` — lockup with wordmark
- `paperclip-LOCKED-canonical-icon-1024.png` — icon (diagonal / default expressive mark in square canvas)
- `paperclip-vertical-1024-v1.png` — vertical icon
- Additional lockup variants: `paperclip-lockup-horizontal-v1.png`, `paperclip-lockup-stacked-v1.png`

## Replacement plan

**Track N** (Poe-via-Brain proxy): regenerate as native SVG, or **Figma hand-trace** from the locked PNGs. Until then, file **path** stability is preserved by editing SVG **contents** only; UI references do not need to move.
