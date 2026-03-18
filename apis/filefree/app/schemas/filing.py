from pydantic import BaseModel, Field


class CreateFilingRequest(BaseModel):
    tax_year: int = Field(default=2025, ge=2020, le=2030)


class UpdateFilingRequest(BaseModel):
    filing_status_type: str | None = None
    status: str | None = None


class FilingResponse(BaseModel):
    id: str
    user_id: str
    tax_year: int
    filing_status_type: str | None = None
    status: str
    created_at: str
    updated_at: str
    submitted_at: str | None = None


class ConfirmDataRequest(BaseModel):
    employee_name: str | None = None
    employee_address: str | None = None
    date_of_birth: str | None = None
