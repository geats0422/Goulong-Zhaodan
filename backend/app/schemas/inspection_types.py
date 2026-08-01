from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InspectionTypeCreate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    dimension: str | None = None

    @field_validator("key", "name")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不得为空")
        return value


class InspectionTypeUpdate(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None

    @field_validator("key", "name")
    @classmethod
    def validate_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("不得为空")
        return value


class InspectionTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    dimension: str
    owner_type: str
    owner_user_id: str | None
    enabled: bool
    created_at: str
    updated_at: str
