"""Pydantic models for canonical infrastructure state files."""

from __future__ import annotations

from abc import ABC
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IacStateFile(BaseModel, ABC):
    """Common contract shared by all canonical infra state YAML files."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    iac_schema: dict[str, Any] = Field(alias="schema")
    version: int = 1
    last_reconciled_at: str | None = None


class VercelEnvVar(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    target: str | list[str] | None = None
    value: str | None = None


class VercelProjectState(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    envs: list[VercelEnvVar] = Field(default_factory=list)


class VercelStateFile(IacStateFile):
    projects: list[VercelProjectState] = Field(default_factory=list)


class CloudflareDNSRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: str
    content: str


class CloudflareZoneState(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    records: list[CloudflareDNSRecord] = Field(default_factory=list)


class CloudflareStateFile(IacStateFile):
    zones: list[CloudflareZoneState] = Field(default_factory=list)


class RenderEnvVar(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    value: str | None = None


class RenderServiceState(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    envs: list[RenderEnvVar] = Field(default_factory=list)


class RenderStateFile(IacStateFile):
    services: list[RenderServiceState] = Field(default_factory=list)


class ClerkDomainState(BaseModel):
    model_config = ConfigDict(extra="allow")

    domain: str
    verified: bool | None = None


class ClerkStateFile(IacStateFile):
    domains: list[ClerkDomainState] = Field(default_factory=list)
