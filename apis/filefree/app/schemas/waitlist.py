from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr


class WaitlistCreate(BaseModel):
    email: EmailStr
    source: str = "landing"
    attribution: dict[str, Any] | None = None


class WaitlistResponse(BaseModel):
    id: str
    email: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
