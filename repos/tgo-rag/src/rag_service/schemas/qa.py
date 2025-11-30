"""
QA (Question-Answer) pair related Pydantic schemas.
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def compute_question_hash(question: str) -> str:
    """Compute SHA-256 hash of a question for deduplication."""
    return hashlib.sha256(question.strip().lower().encode()).hexdigest()


# ============== Request Schemas ==============

class QAPairCreateRequest(BaseModel):
    """Schema for creating a single QA pair."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The question text",
        examples=["如何重置密码？"]
    )
    answer: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="The answer text",
        examples=["您可以通过以下步骤重置密码：1. 点击登录页面的'忘记密码'..."]
    )
    category: Optional[str] = Field(
        None,
        max_length=255,
        description="Category for organizing QA pairs",
        examples=["账户管理"]
    )
    subcategory: Optional[str] = Field(
        None,
        max_length=255,
        description="Subcategory for finer organization",
        examples=["密码相关"]
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Tags for filtering and search",
        examples=[["密码", "重置", "账户"]]
    )
    qa_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata",
        examples=[{"source": "user_manual", "version": "2.0"}]
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Priority for ordering (0-100, higher = more important)"
    )


class QAPairUpdateRequest(BaseModel):
    """Schema for updating a QA pair."""

    question: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10000,
        description="Updated question text"
    )
    answer: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50000,
        description="Updated answer text"
    )
    category: Optional[str] = Field(None, max_length=255)
    subcategory: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = None
    qa_metadata: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(None, ge=0, le=100)


class QAPairBatchCreateRequest(BaseModel):
    """Schema for batch creating QA pairs."""

    qa_pairs: List[QAPairCreateRequest] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of QA pairs to create (max 1000)"
    )


class QAPairImportRequest(BaseModel):
    """Schema for importing QA pairs from JSON/CSV."""

    format: Literal["json", "csv"] = Field(
        default="json",
        description="Import format: json or csv"
    )
    data: str = Field(
        ...,
        description="JSON array string or CSV content"
    )
    category: Optional[str] = Field(
        None,
        description="Default category for all imported pairs"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Default tags for all imported pairs"
    )


# ============== Response Schemas ==============

class QAPairResponse(BaseModel):
    """Schema for QA pair API responses."""

    id: UUID = Field(..., description="QA pair unique identifier")
    collection_id: UUID = Field(..., description="Associated collection ID")
    question: str = Field(..., description="The question text")
    answer: str = Field(..., description="The answer text")
    question_hash: str = Field(..., description="Question hash for deduplication")
    category: Optional[str] = Field(None, description="Category")
    subcategory: Optional[str] = Field(None, description="Subcategory")
    tags: Optional[List[str]] = Field(None, description="Tags")
    qa_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    source_type: str = Field(..., description="Source type: manual, import, ai_generated")
    status: str = Field(..., description="Processing status")
    priority: int = Field(..., description="Priority")
    document_id: Optional[UUID] = Field(None, description="Associated document ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class QAPairListResponse(BaseModel):
    """Schema for paginated QA pair list responses."""

    data: List[QAPairResponse] = Field(..., description="List of QA pairs")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class QAPairBatchCreateResponse(BaseModel):
    """Schema for batch create response."""

    success: bool = Field(..., description="Whether operation succeeded")
    created_count: int = Field(..., description="Number of QA pairs created")
    skipped_count: int = Field(..., description="Number skipped (duplicates)")
    failed_count: int = Field(..., description="Number failed")
    created_ids: List[UUID] = Field(default_factory=list, description="Created QA pair IDs")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")
    message: str = Field(..., description="Summary message")

