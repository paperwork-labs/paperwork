from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    referral_code: str
    auth_provider: str
    email_verified: bool
    role: str
    advisor_tier: str
    created_at: datetime

    model_config = {"from_attributes": True}
