from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    project_type: str = Field(default="python-pytest", pattern="^python-pytest$")

    @field_validator("name")
    @classmethod
    def trim_and_validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Project name must contain at least 2 non-space characters")
        return value

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str) -> str:
        return value.strip()


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    project_type: str
    created_at: datetime


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    status: str
    content: str
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    status: str
    passed: int
    failed: int
    skipped: int
    errors: int
    duration_ms: int
    summary: str
    output: str
    created_at: datetime
    analyses: list[AnalysisOut] = []

