"""Tiered OCR pipeline: Cloud Vision text -> GPT-4o-mini mapping -> GPT-4o vision fallback."""

import json
import logging
import re
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.image_processor import preprocess_image

logger = logging.getLogger(__name__)

SSN_PATTERN = re.compile(r"\b(\d{3})-?(\d{2})-?(\d{4})\b")
SSN_MASK = "XXX-XX-XXXX"


class W2ExtractionResult(BaseModel):
    employer_name: str = ""
    employer_ein: str = ""
    employer_address: str = ""
    employee_name: str = ""
    employee_address: str = ""
    employee_ssn: str = Field(default="", description="Extracted locally, never sent to LLM")
    wages: int = Field(default=0, description="Box 1 — cents")
    federal_tax_withheld: int = Field(default=0, description="Box 2 — cents")
    social_security_wages: int = Field(default=0, description="Box 3 — cents")
    social_security_tax: int = Field(default=0, description="Box 4 — cents")
    medicare_wages: int = Field(default=0, description="Box 5 — cents")
    medicare_tax: int = Field(default=0, description="Box 6 — cents")
    state: str = ""
    state_wages: int = Field(default=0, description="Box 16 — cents")
    state_tax_withheld: int = Field(default=0, description="Box 17 — cents")
    confidence: float = 0.0
    tier_used: str = "mock"


def _extract_ssn(text: str) -> tuple[str, str]:
    """Extract SSN from text and return (ssn, scrubbed_text). SSN never leaves this function."""
    ssn = ""
    match = SSN_PATTERN.search(text)
    if match:
        ssn = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    scrubbed = SSN_PATTERN.sub(SSN_MASK, text)
    return ssn, scrubbed


def _dollars_to_cents(value: str | float | int) -> int:
    """Convert a dollar amount (string or number) to integer cents."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value * 100)
    cleaned = re.sub(r"[,$\s]", "", str(value))
    if not cleaned:
        return 0
    try:
        return round(float(cleaned) * 100)
    except ValueError:
        return 0


def _mock_extraction() -> W2ExtractionResult:
    """Return realistic mock data for development without API keys."""
    return W2ExtractionResult(
        employer_name="Acme Corporation",
        employer_ein="12-3456789",
        employer_address="100 Main Street, Suite 200, San Francisco, CA 94105",
        employee_name="Jane A. Doe",
        employee_address="456 Oak Avenue, Apt 3B, San Francisco, CA 94110",
        employee_ssn="123-45-6789",
        wages=7500000,
        federal_tax_withheld=1125000,
        social_security_wages=7500000,
        social_security_tax=465000,
        medicare_wages=7500000,
        medicare_tax=108750,
        state="CA",
        state_wages=7500000,
        state_tax_withheld=450000,
        confidence=0.95,
        tier_used="mock",
    )


async def _cloud_vision_ocr(image_bytes: bytes) -> dict[str, Any]:
    """Call GCP Cloud Vision DOCUMENT_TEXT_DETECTION. Returns structured text + bounding boxes."""
    from google.cloud import vision

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Cloud Vision error: {response.error.message}")

    full_text = response.full_text_annotation.text if response.full_text_annotation else ""

    blocks: list[dict[str, Any]] = []
    if response.full_text_annotation:
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                block_text = ""
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_text = "".join(s.text for s in word.symbols)
                        block_text += word_text + " "

                vertices = block.bounding_box.vertices
                blocks.append(
                    {
                        "text": block_text.strip(),
                        "bounds": {
                            "x": vertices[0].x,
                            "y": vertices[0].y,
                            "width": vertices[2].x - vertices[0].x,
                            "height": vertices[2].y - vertices[0].y,
                        },
                    }
                )

    return {"full_text": full_text, "blocks": blocks}


async def _gpt_mini_map_fields(scrubbed_text: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Use GPT-4o-mini structured output to map OCR text to W-2 fields."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    block_summary = "\n".join(
        f"[{b['bounds']['x']},{b['bounds']['y']}] {b['text']}" for b in blocks[:40]
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a W-2 form data extractor. Given OCR text from a W-2 form, "
                    "extract the fields into the specified JSON format. "
                    "Dollar amounts should be numbers (e.g., 75000.00 not '$75,000'). "
                    "SSN has been redacted as XXX-XX-XXXX — output it exactly as shown. "
                    "If a field is not found, use empty string for text or 0 for numbers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"OCR Text:\n{scrubbed_text}\n\n"
                    f"Block positions:\n{block_summary}\n\n"
                    "Extract into JSON with keys: employer_name, employer_ein, employer_address, "
                    "employee_name, employee_address, wages (Box 1), federal_tax_withheld (Box 2), "
                    "social_security_wages (Box 3), social_security_tax (Box 4), "
                    "medicare_wages (Box 5), medicare_tax (Box 6), state, "
                    "state_wages (Box 16), state_tax_withheld (Box 17), confidence (0.0-1.0)."
                ),
            },
        ],
        temperature=0,
        max_tokens=800,
    )

    content = response.choices[0].message.content or "{}"
    return json.loads(content)


async def _gpt_vision_fallback(image_bytes: bytes) -> dict[str, Any]:
    """Use GPT-4o vision for low-confidence extractions. Sends actual image."""
    import base64

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a W-2 form data extractor. Extract all fields from this W-2 image. "
                    "Dollar amounts as numbers. "
                    "SSN should be extracted but will be handled securely. "
                    "Output JSON with keys: employer_name, employer_ein, employer_address, "
                    "employee_name, employee_address, employee_ssn, wages, federal_tax_withheld, "
                    "social_security_wages, social_security_tax, medicare_wages, medicare_tax, "
                    "state, state_wages, state_tax_withheld, confidence."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all W-2 fields from this image."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
                    },
                ],
            },
        ],
        temperature=0,
        max_tokens=800,
    )

    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _build_result(fields: dict[str, Any], ssn: str, tier: str) -> W2ExtractionResult:
    """Build a validated W2ExtractionResult from raw GPT output."""
    return W2ExtractionResult(
        employer_name=str(fields.get("employer_name", "")),
        employer_ein=str(fields.get("employer_ein", "")),
        employer_address=str(fields.get("employer_address", "")),
        employee_name=str(fields.get("employee_name", "")),
        employee_address=str(fields.get("employee_address", "")),
        employee_ssn=ssn,
        wages=_dollars_to_cents(fields.get("wages", 0)),
        federal_tax_withheld=_dollars_to_cents(fields.get("federal_tax_withheld", 0)),
        social_security_wages=_dollars_to_cents(fields.get("social_security_wages", 0)),
        social_security_tax=_dollars_to_cents(fields.get("social_security_tax", 0)),
        medicare_wages=_dollars_to_cents(fields.get("medicare_wages", 0)),
        medicare_tax=_dollars_to_cents(fields.get("medicare_tax", 0)),
        state=str(fields.get("state", "")),
        state_wages=_dollars_to_cents(fields.get("state_wages", 0)),
        state_tax_withheld=_dollars_to_cents(fields.get("state_tax_withheld", 0)),
        confidence=float(fields.get("confidence", 0)),
        tier_used=tier,
    )


async def process_w2(image_bytes: bytes) -> W2ExtractionResult:
    """Run the tiered OCR pipeline on a W-2 image."""

    if not settings.OPENAI_API_KEY or not settings.GOOGLE_APPLICATION_CREDENTIALS:
        logger.info("Mock mode: returning hardcoded W2 data (no API keys)")
        return _mock_extraction()

    processed = preprocess_image(image_bytes)

    try:
        ocr_result = await _cloud_vision_ocr(processed)
    except Exception as exc:
        exc_type = type(exc).__name__
        exc_module = type(exc).__module__ or ""

        if "PermissionDenied" in exc_type or "DefaultCredentialsError" in exc_type:
            logger.error("Cloud Vision auth error (%s): %s — falling back to mock", exc_type, exc)
            return _mock_extraction()
        if "ServiceUnavailable" in exc_type or "DeadlineExceeded" in exc_type:
            logger.error("Cloud Vision unavailable: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="OCR service temporarily unavailable. Please try again.",
            ) from exc
        if "ResourceExhausted" in exc_type:
            logger.error("Cloud Vision quota exceeded: %s", exc)
            raise HTTPException(
                status_code=429,
                detail="OCR quota exceeded. Try again later.",
            ) from exc

        logger.exception("Unexpected Cloud Vision error (%s.%s)", exc_module, exc_type)
        return _mock_extraction()

    full_text = ocr_result["full_text"]

    if not full_text.strip():
        logger.warning("Cloud Vision returned empty text, trying GPT-4o vision fallback")
        try:
            fields = await _gpt_vision_fallback(processed)
            ssn = str(fields.pop("employee_ssn", ""))
            return _build_result(fields, ssn, "gpt4o-vision-empty-ocr")
        except Exception as exc:
            return _handle_openai_error(exc, "vision fallback (empty OCR)")

    ssn, scrubbed_text = _extract_ssn(full_text)

    try:
        fields = await _gpt_mini_map_fields(scrubbed_text, ocr_result["blocks"])
    except Exception as exc:
        return _handle_openai_error(exc, "GPT-4o-mini field mapping")

    confidence = float(fields.get("confidence", 0))
    tier = "cloud-vision+gpt4o-mini"

    if confidence < 0.85:
        logger.info("Low confidence (%.2f), escalating to GPT-4o vision", confidence)
        try:
            vision_fields = await _gpt_vision_fallback(processed)
            vision_ssn = str(vision_fields.pop("employee_ssn", ""))
            if not ssn and vision_ssn:
                ssn = vision_ssn
            if float(vision_fields.get("confidence", 0)) > confidence:
                fields = vision_fields
                tier = "gpt4o-vision-fallback"
        except Exception as exc:
            logger.warning(
                "GPT-4o vision fallback failed (%s), using mini results",
                type(exc).__name__,
            )

    return _build_result(fields, ssn, tier)


def _handle_openai_error(exc: Exception, context: str) -> W2ExtractionResult:
    """Handle OpenAI API errors with appropriate responses."""
    exc_type = type(exc).__name__

    if "AuthenticationError" in exc_type:
        logger.error("OpenAI auth error in %s: %s — falling back to mock", context, exc)
        return _mock_extraction()
    if "RateLimitError" in exc_type:
        logger.error("OpenAI rate limit in %s: %s", context, exc)
        raise HTTPException(
            status_code=429,
            detail="AI service rate limit exceeded. Try again in a moment.",
        ) from exc
    if "Timeout" in exc_type or "ConnectError" in exc_type:
        logger.error("OpenAI timeout in %s: %s", context, exc)
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable. Please try again.",
        ) from exc

    logger.exception("Unexpected OpenAI error in %s (%s)", context, exc_type)
    return _mock_extraction()
