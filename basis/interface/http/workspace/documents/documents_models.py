"""Pydantic models for workspace document and processing routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AppendTextVersionRequest(BaseModel):
    text: str


class IngestTextRequest(BaseModel):
    doc_id: str = Field(min_length=1)
    text: str | None = None
    url: str | None = None
    wait: bool | None = None
    chunk: bool | None = None
    chunk_size: int | None = Field(default=None, ge=200, le=100_000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=10_000)
    extract: bool | None = None
    ner_method: str | None = None
    relation_method: str | None = None
    extract_relations: bool | None = None


class StartProcessingRequest(BaseModel):
    version_id: str = Field(min_length=1)
    wait: bool = False
    chunk: bool = True
    chunk_method: str | None = Field(default=None, max_length=40)
    chunk_size: int = Field(default=1800, ge=200, le=100_000)
    chunk_overlap: int = Field(default=250, ge=0, le=10_000)
    extract: bool = True
    ner_method: str = Field(default="llm", min_length=1, max_length=40)
    relation_method: str = Field(default="llm", min_length=1, max_length=40)
    extract_relations: bool = True
    ner_model: str | None = Field(default=None, max_length=120)
    llm_model: str | None = Field(default=None, max_length=200)
    llm_endpoint_id: str | None = Field(default=None, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=128)


class RetryProcessingRequest(BaseModel):
    wait: bool = False


class CreateOntologyRequest(BaseModel):
    namespace: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
