"""Pydantic models for workspace ingest source routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateIngestSourceRequest(BaseModel):
    kind: Literal["webhook", "http_poll", "git"] = "webhook"
    name: str = Field(min_length=1, max_length=128)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class UpdateIngestSourceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class WebhookIngestRequest(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    text: str = Field(min_length=1)
    external_key: str | None = Field(default=None, max_length=256)
    auto_process: bool = True


class SyncIngestSourceRequest(BaseModel):
    auto_process: bool = True
