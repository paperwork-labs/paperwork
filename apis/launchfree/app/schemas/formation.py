"""medallion: ops"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FormationStatus(str, Enum):
    DRAFT = "draft"
    DOCUMENTS_READY = "documents_ready"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class FilingTier(str, Enum):
    API = "api"
    PORTAL = "portal"
    MAIL = "mail"


class AddressSchema(BaseModel):
    street1: str = Field(description="Street address line 1")
    street2: str | None = Field(default=None, description="Street address line 2")
    city: str = Field(description="City")
    state: str = Field(description="State code (2-char)")
    zip_code: str = Field(description="ZIP code")
    country: str = Field(default="US", description="Country code")


class RegisteredAgentSchema(BaseModel):
    name: str = Field(description="Registered agent name (person or company)")
    address: AddressSchema = Field(description="Registered agent address")
    is_commercial: bool = Field(
        default=False, description="Whether this is a commercial registered agent"
    )


class MemberSchema(BaseModel):
    name: str = Field(description="Member's full legal name")
    address: AddressSchema = Field(description="Member's address")
    ownership_percentage: float | None = Field(
        default=None, description="Ownership percentage (0-100)"
    )
    is_organizer: bool = Field(default=False, description="Whether this member is the organizer")
    is_manager: bool = Field(default=False, description="Whether this member is a manager")


class FormationCreate(BaseModel):
    state_code: str = Field(min_length=2, max_length=2, description="State code (2-char)")
    business_name: str = Field(min_length=1, max_length=255, description="LLC business name")
    business_purpose: str = Field(
        default="Any lawful purpose", description="Business purpose statement"
    )
    registered_agent: RegisteredAgentSchema | None = Field(
        default=None, description="Registered agent info"
    )
    members: list[MemberSchema] = Field(default_factory=list, description="LLC members")
    principal_address: AddressSchema | None = Field(
        default=None, description="Principal place of business"
    )
    mailing_address: AddressSchema | None = Field(
        default=None, description="Mailing address (if different from principal)"
    )


class FormationUpdate(BaseModel):
    business_name: str | None = Field(default=None, max_length=255)
    business_purpose: str | None = Field(default=None)
    registered_agent: RegisteredAgentSchema | None = Field(default=None)
    members: list[MemberSchema] | None = Field(default=None)
    principal_address: AddressSchema | None = Field(default=None)
    mailing_address: AddressSchema | None = Field(default=None)
    status: FormationStatus | None = Field(default=None)
    filing_tier: FilingTier | None = Field(default=None)
    filing_number: str | None = Field(default=None)
    confirmation_number: str | None = Field(default=None)
    filed_at: datetime | None = Field(default=None)
    screenshots: list[str] | None = Field(default=None)
    error_log: dict | None = Field(default=None)


class FormationResponse(BaseModel):
    id: int
    user_id: str
    state_code: str
    business_name: str
    business_purpose: str
    registered_agent: dict | None
    members: list
    principal_address: dict | None
    mailing_address: dict | None
    status: str
    filing_tier: str
    filing_number: str | None
    confirmation_number: str | None
    filed_at: datetime | None
    screenshots: list
    error_log: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
