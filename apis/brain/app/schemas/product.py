"""Pydantic schemas for the products admin surface (WS-82).

medallion: ops
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime by Pydantic
from typing import Any

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Create a product row; ``id`` is the URL slug (e.g. ``axiomfolio``)."""

    id: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    tagline: str | None = None
    status: str = Field(default="active", max_length=50)
    domain: str | None = Field(default=None, max_length=200)
    repo_path: str | None = Field(default=None, max_length=200)
    vercel_project: str | None = Field(default=None, max_length=200)
    render_services: list[Any] = Field(default_factory=list)
    tech_stack: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    """Partial update; omitted fields are left unchanged."""

    name: str | None = Field(default=None, max_length=200)
    tagline: str | None = None
    status: str | None = Field(default=None, max_length=50)
    domain: str | None = Field(default=None, max_length=200)
    repo_path: str | None = Field(default=None, max_length=200)
    vercel_project: str | None = Field(default=None, max_length=200)
    render_services: list[Any] | None = None
    tech_stack: list[Any] | None = None
    metadata: dict[str, Any] | None = None


class ProductResponse(BaseModel):
    """Single product as returned by admin API."""

    id: str
    name: str
    tagline: str | None
    status: str
    domain: str | None
    repo_path: str | None
    vercel_project: str | None
    render_services: list[Any]
    tech_stack: list[Any]
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
