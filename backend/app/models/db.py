import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str] = mapped_column(String(300), default="")
    language: Mapped[str] = mapped_column(String(20), default="both")  # arabic, english, both
    madhab: Mapped[str] = mapped_column(String(50), default="general")  # hanafi, shafii, maliki, hanbali, general
    category: Mapped[str] = mapped_column(String(50), default="general")  # quran, hadith, fiqh, aqeedah, general
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sources: Mapped[list["Source"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id"))
    filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(20))  # pdf, image, text
    file_path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book: Mapped["Book"] = relationship(back_populates="sources")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    content_arabic: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_english: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_type: Mapped[str] = mapped_column(String(20))  # ayah, hadith, paragraph
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    section: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qdrant_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped["Source"] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at, ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))  # user, assistant
    content: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
