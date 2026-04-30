"""Pydantic models for infra_registry.json.

Validated by ``app.services.infra_registry``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InfraRegistryService(BaseModel):
    """A deployable surface (Vercel app or Render resource)."""

    id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    provider: str = Field(pattern=r"^(vercel|render)$")
    type: str = Field(
        pattern=r"^(frontend|backend|worker|database|cache)$",
    )
    url: str | None = None
    health_endpoint: str | None = None


class InfraRegistryVendor(BaseModel):
    """Third-party vendor (AI, hosting, auth, ...)."""

    id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    pricing_url: str = Field(min_length=1)
    monthly_budget: int | None = Field(default=None, ge=0)


class InfraRegistryRoot(BaseModel):
    """Root document for apis/brain/data/infra_registry.json."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(pattern=r"^infra_registry/v\d+$", alias="schema")
    description: str = Field(min_length=1)
    services: list[InfraRegistryService]
    vendors: list[InfraRegistryVendor]

    @model_validator(mode="after")
    def _unique_ids(self) -> InfraRegistryRoot:
        sids = [s.id for s in self.services]
        if len(sids) != len(set(sids)):
            msg = "duplicate service id in infra registry"
            raise ValueError(msg)
        vids = [v.id for v in self.vendors]
        if len(vids) != len(set(vids)):
            msg = "duplicate vendor id in infra registry"
            raise ValueError(msg)
        return self
