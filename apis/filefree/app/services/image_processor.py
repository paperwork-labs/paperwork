"""Image preprocessing for OCR: auto-rotate, contrast normalize, resize.

medallion: ops
"""

import io
import logging

from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSION = 2048
MIN_DIMENSION = 640


def preprocess_image(image_bytes: bytes) -> bytes:
    """Prepare an image for OCR: rotate per EXIF, normalize contrast, resize."""
    base = Image.open(io.BytesIO(image_bytes))
    exif = ImageOps.exif_transpose(base)
    img: Image.Image = exif if exif is not None else base

    if img.mode != "RGB":
        img = img.convert("RGB")

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)

    w, h = img.size
    resample = Image.Resampling.LANCZOS
    if max(w, h) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), resample)
    elif max(w, h) < MIN_DIMENSION:
        scale = MIN_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), resample)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)

    logger.info(
        "Image preprocessed: %dx%d -> %dx%d (%d bytes)",
        w,
        h,
        img.size[0],
        img.size[1],
        buf.getbuffer().nbytes,
    )
    return buf.read()
