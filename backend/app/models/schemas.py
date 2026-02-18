from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Books ---

class BookCreate(BaseModel):
    title: str
    author: str = ""
    language: str = "both"
    madhab: str = "general"
    category: str = "general"


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
    title: str
    author: str = ""
    language: str = "both"
    madhab: str = "general"
    category: str = "general"
    chunk_type: str = "paragraph"  # ayah, hadith, paragraph


class UploadResponse(BaseModel):
    source_id: UUID
    book_id: UUID
    status: str
    message: str


# --- Query ---

class QueryRequest(BaseModel):
    question: str
    madhab: str | None = None
    category: str | None = None
    top_k: int = 10


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
    message: str
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
    title: str


# --- Health ---

class HealthResponse(BaseModel):
    status: str
    version: str
