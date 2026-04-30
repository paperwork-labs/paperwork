"""Pydantic models for vendors.json (ops vendor catalog).

Aligned with ``InfraRegistryVendor`` in ``infra_registry.json``:
``pricing_url`` ↔ ``contract_url``, ``monthly_budget`` ↔ ``monthly_estimate_usd``.

medallion: ops
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Vendor(BaseModel):
    """Third-party vendor record for Brain vendor tab + API."""

    id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1, description="Primary vendor domain (e.g. vercel.com)")
    category: str = Field(min_length=1)
    monthly_estimate_usd: float | None = Field(default=None, ge=0)
    contract_url: str = Field(
        min_length=1, description="Pricing or contract URL (infra: pricing_url)"
    )
    owner_persona: str | None = None
    organization_id: str | None = None


class VendorCreate(BaseModel):
    """Body for POST /vendors."""

    id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    category: str = Field(min_length=1)
    monthly_estimate_usd: float | None = Field(default=None, ge=0)
    contract_url: str = Field(min_length=1)
    owner_persona: str | None = None
    organization_id: str | None = None


class VendorUpdate(BaseModel):
    """Body for PUT /vendors/{id} (full replace of mutable fields; id from path)."""

    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    category: str = Field(min_length=1)
    monthly_estimate_usd: float | None = Field(default=None, ge=0)
    contract_url: str = Field(min_length=1)
    owner_persona: str | None = None
    organization_id: str | None = None


class VendorsRoot(BaseModel):
    """Root document for apis/brain/data/vendors.json."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(pattern=r"^brain_vendors/v\d+$", alias="schema")
    vendors: list[Vendor]

    @model_validator(mode="after")
    def _unique_ids(self) -> VendorsRoot:
        vids = [v.id for v in self.vendors]
        if len(vids) != len(set(vids)):
            msg = "duplicate vendor id in vendors store"
            raise ValueError(msg)
        return self
