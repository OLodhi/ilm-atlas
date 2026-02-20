from datetime import datetime
from uuid import UUID

import re

from pydantic import BaseModel, Field, field_validator


# --- Books ---

class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field(default="", max_length=300)
    language: str = Field(default="both", pattern="^(arabic|english|both)$")
    madhab: str = Field(default="general", pattern="^(hanafi|shafii|maliki|hanbali|general)$")
    category: str = Field(default="general", pattern="^(quran|hadith|fiqh|aqeedah|seerah|tafsir|general)$")


class BookResponse(BaseModel):
    id: UUID
    title: str
    author: str
    language: str
    madhab: str
    category: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Sources ---

class SourceResponse(BaseModel):
    id: UUID
    book_id: UUID
    filename: str
    file_type: str
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Upload ---

class UploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: str = Field(default="", max_length=300)
    language: str = Field(default="both", pattern="^(arabic|english|both)$")
    madhab: str = Field(default="general", pattern="^(hanafi|shafii|maliki|hanbali|general)$")
    category: str = Field(default="general", pattern="^(quran|hadith|fiqh|aqeedah|seerah|tafsir|general)$")
    chunk_type: str = Field(default="paragraph", pattern="^(ayah|hadith|paragraph)$")


class UploadResponse(BaseModel):
    source_id: UUID
    book_id: UUID
    status: str
    message: str


# --- Query ---

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    madhab: str | None = None
    category: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)


class Citation(BaseModel):
    text_arabic: str | None = None
    text_english: str | None = None
    source: str
    chunk_type: str
    metadata: dict | None = None
    auto_translated: bool = False


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]


# --- Chat ---

class ChatSessionResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    citations: list[Citation] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetailResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse]

    model_config = {"from_attributes": True}


class ChatSendRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    madhab: str | None = None
    category: str | None = None


class ChatSendResponse(BaseModel):
    message: ChatMessageResponse
    user_message: ChatMessageResponse
    session_id: UUID
    session_title: str | None


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]


class ChatSessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


# --- Auth ---

class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-zA-Z0-9 ]+$", v):
            raise ValueError("Display name can only contain letters, numbers, and spaces")
        return v


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    email_verified: bool
    display_name: str | None
    role: str
    daily_query_limit: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=100)
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-zA-Z0-9 ]+$", v):
            raise ValueError("Display name can only contain letters, numbers, and spaces")
        return v


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class UsageResponse(BaseModel):
    used: int
    limit: int
    date: str


# --- Health ---

class HealthResponse(BaseModel):
    status: str
    version: str
