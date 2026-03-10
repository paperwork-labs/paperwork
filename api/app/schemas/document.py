from pydantic import BaseModel, Field


class W2FieldResult(BaseModel):
    employer_name: str = ""
    employer_ein: str = ""
    employer_address: str = ""
    employee_name: str = ""
    employee_address: str = ""
    ssn_last_four: str = Field(default="", description="Last 4 digits only")
    wages: int = Field(default=0, description="Box 1 — cents")
    federal_tax_withheld: int = Field(default=0, description="Box 2 — cents")
    social_security_wages: int = Field(default=0, description="Box 3 — cents")
    social_security_tax: int = Field(default=0, description="Box 4 — cents")
    medicare_wages: int = Field(default=0, description="Box 5 — cents")
    medicare_tax: int = Field(default=0, description="Box 6 — cents")
    state: str = ""
    state_wages: int = Field(default=0, description="Box 16 — cents")
    state_tax_withheld: int = Field(default=0, description="Box 17 — cents")


class DemoExtractionResponse(BaseModel):
    fields: W2FieldResult
    confidence: float
    tier_used: str
