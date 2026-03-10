"""Image preprocessing for OCR: auto-rotate, contrast normalize, resize."""

import io
import logging

from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

MAX_DIMENSION = 2048
MIN_DIMENSION = 640


def preprocess_image(image_bytes: bytes) -> bytes:
    """Prepare an image for OCR: rotate per EXIF, normalize contrast, resize."""
    img = Image.open(io.BytesIO(image_bytes))

    img = ImageOps.exif_transpose(img) or img

    if img.mode != "RGB":
        img = img.convert("RGB")

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)

    w, h = img.size
    if max(w, h) > MAX_DIMENSION:
        scale = MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    elif max(w, h) < MIN_DIMENSION:
        scale = MIN_DIMENSION / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)

    logger.info(
        "Image preprocessed: %dx%d -> %dx%d (%d bytes)",
        w, h, img.size[0], img.size[1], buf.getbuffer().nbytes,
    )
    return buf.read()
