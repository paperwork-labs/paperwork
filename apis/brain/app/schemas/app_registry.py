from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConformanceStatus(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    missing_markers: list[str] = Field(default_factory=list)


class SizeSignals(BaseModel):
    py_files: int = Field(ge=0)
    ts_files: int = Field(ge=0)
    lines_of_code_approx: int = Field(ge=0)


class AppEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    path: str
    app_type: str = Field(alias="type")
    framework: str
    language: str
    language_version: str
    package_manager: str
    test_runner: str
    linter: str
    formatter: str
    deploy_target: str
    service_name: str | None = None
    owner_persona: str
    conformance: ConformanceStatus
    size_signals: SizeSignals
    last_modified: str
    depends_on_services: list[str] = Field(default_factory=list)

    @property
    def type(self) -> str:
        return self.app_type

    @field_validator("path")
    @classmethod
    def path_must_be_relative(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            msg = "path must be a relative monorepo path"
            raise ValueError(msg)
        return value


class AppRegistry(BaseModel):
    schema_: str = Field(alias="schema")
    description: str
    version: int
    generated_at: str
    generated_by: str
    apps: list[AppEntry]
