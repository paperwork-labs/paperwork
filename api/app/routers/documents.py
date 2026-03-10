import logging

from fastapi import APIRouter, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas.base import error_response, success_response
from app.schemas.document import DemoExtractionResponse, W2FieldResult
from app.services.ocr_service import process_w2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

limiter = Limiter(key_func=get_remote_address)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/demo-upload")
@limiter.limit("3/day")
async def demo_upload(request: Request, file: UploadFile):
    """Anonymous W-2 extraction — no auth, no storage, rate limited.

    This is the try-before-signup endpoint. Image is processed in memory
    and never persisted. SSN is extracted locally and only last 4 digits
    are returned.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        return error_response("Invalid file type. Please upload a JPG, PNG, or WEBP image.", 400)

    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE:
        return error_response("File too large. Maximum size is 10MB.", 400)

    if len(image_bytes) < 1024:
        return error_response("File too small. Please upload a valid document image.", 400)

    try:
        result = await process_w2(image_bytes)
    except Exception:
        logger.exception("OCR processing failed")
        return error_response(
            "We couldn't read your W-2. Try taking another photo with better lighting.",
            422,
        )

    ssn_last_four = result.employee_ssn[-4:] if len(result.employee_ssn) >= 4 else ""

    response = DemoExtractionResponse(
        fields=W2FieldResult(
            employer_name=result.employer_name,
            employer_ein=result.employer_ein,
            employer_address=result.employer_address,
            employee_name=result.employee_name,
            employee_address=result.employee_address,
            ssn_last_four=ssn_last_four,
            wages=result.wages,
            federal_tax_withheld=result.federal_tax_withheld,
            social_security_wages=result.social_security_wages,
            social_security_tax=result.social_security_tax,
            medicare_wages=result.medicare_wages,
            medicare_tax=result.medicare_tax,
            state=result.state,
            state_wages=result.state_wages,
            state_tax_withheld=result.state_tax_withheld,
        ),
        confidence=result.confidence,
        tier_used=result.tier_used,
    )

    return success_response(response.model_dump())
