"""
Open Graph (1200x630) PNG for chart share links — Pillow-based raster.

medallion: ops
"""

from __future__ import annotations

import io
import logging
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

OG_WIDTH = 1200
OG_HEIGHT = 630
BG: Tuple[int, int, int] = (15, 23, 42)
FG: Tuple[int, int, int] = (241, 245, 249)
MUTED: Tuple[int, int, int] = (148, 163, 184)
SPARK: Tuple[int, int, int] = (99, 102, 241)
ACCENT: Tuple[int, int, int] = (251, 191, 36)


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    logger.warning("No system TTF for OG image; using default bitmap font (small)")
    return ImageFont.load_default()


def _sparkline_to_points(
    values: List[float], box: Tuple[int, int, int, int]
) -> List[Tuple[int, int]]:
    if len(values) < 2:
        return []
    left, top, right, bottom = box
    w = right - left
    h = bottom - top
    lo, hi = min(values), max(values)
    span = hi - lo
    if span <= 0:
        span = 1.0
    n = len(values)
    out: List[Tuple[int, int]] = []
    for i, v in enumerate(values):
        x = left + int((i / (n - 1)) * w) if n > 1 else left + w // 2
        y = bottom - int(((v - lo) / span) * h)
        y = max(top + 2, min(bottom - 2, y))
        out.append((x, y))
    return out


def render_chart_og_png(
    *,
    symbol: str,
    last_price: Optional[float],
    sparkline: List[float],
) -> bytes:
    """
    Render a 1200x630 PNG: symbol, formatted price, 30d sparkline, AxiomFolio wordmark.
    """
    img = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    font_lg = _load_font(44)
    font_sm = _load_font(24)

    price_str = f"${last_price:,.2f}" if last_price is not None and not (last_price != last_price) else "—"
    title = f"{symbol}  {price_str}"
    draw.text((48, 52), title, fill=FG, font=font_lg)

    box = (48, 160, OG_WIDTH - 48, 480)
    draw.rectangle(
        (box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2),
        outline=(51, 65, 85),
    )

    if len(sparkline) >= 2:
        pts = _sparkline_to_points(sparkline, box)
        if len(pts) >= 2:
            draw.line(pts, fill=SPARK, width=4)
            r = 6
            x1, y1 = pts[-1]
            draw.ellipse(
                (x1 - r, y1 - r, x1 + r, y1 + r),
                fill=ACCENT,
                outline=FG,
            )
    else:
        draw.text(
            (64, 300),
            "Not enough history for a sparkline — data may still be loading.",
            fill=MUTED,
            font=font_sm,
        )

    word = "AxiomFolio"
    try:
        bbox = font_sm.getbbox(word)
        text_w = bbox[2] - bbox[0]
    except Exception:
        text_w = 160
    draw.text(
        (OG_WIDTH - 48 - text_w, OG_HEIGHT - 64),
        word,
        fill=MUTED,
        font=font_sm,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
